"""Phase C, drums. C.2: Hard, Medium and Easy made from Expert, and the hard rules they keep."""

import random
import re
from dataclasses import replace

import numpy as np
import pytest
from conftest import CALIFORNICATION

from chartgen.chart.difficulty import HardRuleViolation
from chartgen.chart.drum_difficulty import (
    CONFIG_PATH,
    DrumDifficultyConfig,
    DrumLevelConfig,
    check_drum_levels,
    gems_by_tick,
    load_drum_config,
    reduce_drums,
)
from chartgen.chart.instruments import build_tracks_for
from chartgen.clonehero.chart_format import DotChartExporter
from chartgen.clonehero.validate import validate_chart_text
from chartgen.core import Chart, ChartNote, Difficulty, Instrument, SongMetadata, TempoEvent, TempoMap, TimeSignatureEvent, Track
from chartgen.core.drums import DrumGem
from chartgen.evaluation.drum_metrics import drum_level_metrics
from chartgen.evaluation.reference import ReferenceDrumHit
from chartgen.evaluation.run import _drum_lines

R = 192
BAR = 4 * R
TEMPO = TempoMap([TempoEvent(0, 120.0)], [TimeSignatureEvent(0, 4, 4)], resolution=R)
K, S = DrumGem.KICK, DrumGem.RED
HH, RD, CR = DrumGem.YELLOW_CYMBAL, DrumGem.BLUE_CYMBAL, DrumGem.GREEN_CYMBAL
YT, BT, GT = DrumGem.YELLOW_TOM, DrumGem.BLUE_TOM, DrumGem.GREEN_TOM
LOWER = (Difficulty.HARD, Difficulty.MEDIUM, Difficulty.EASY)


def drums(positions: dict[int, tuple[DrumGem, ...]], level: Difficulty = Difficulty.EXPERT) -> Track:
    return Track(Instrument.DRUMS, level, [gem.note(tick) for tick, gems in sorted(positions.items()) for gem in gems])


def rock_groove(bars: int = 8) -> dict[int, tuple[DrumGem, ...]]:
    """A hi-hat groove with ghost notes, then a ride groove, a fill and a crash, bar after bar."""
    positions: dict[int, tuple[DrumGem, ...]] = {}
    for bar in range(bars):
        start = bar * BAR
        cymbal = HH if bar < bars // 2 else RD
        for eighth in range(8):
            tick = start + eighth * R // 2
            gems = [cymbal]
            if eighth in (0, 4, 5):
                gems.append(K)
            if eighth in (2, 6):
                gems.append(S)
            positions[tick] = tuple(gems)
        positions[start + 3 * R + R // 4] = (S,)  # a ghost note on a sixteenth
        positions[start + R + 3 * R // 4] = (S,)
    positions[0] = (K, CR)
    positions[2 * BAR + 2 * R] = (K, S, HH)  # the kick and the snare together, under a hi-hat
    positions[6 * BAR + 2 * R] = (K, S, RD)
    fill = (bars - 1) * BAR + 3 * R
    for step, gem in enumerate((YT, YT, BT, GT)):
        positions[fill + step * R // 4] = (gem,)
    return positions


EXPERT = drums(rock_groove())


# ---------------------------------------------------------------- the settings


def test_the_settings_follow_the_human_chart():
    config = load_drum_config()
    assert [config.levels[level].position_ratio for level in LOWER] == [0.76, 0.64, 0.54]
    assert [config.levels[level].min_gap_s for level in LOWER] == [0.10, 0.20, 0.20]
    assert config.gem_order[:4] == (S, CR, RD, K), "the snare stays longest, the hi-hat gives way to the kick"
    assert K not in config.levels[Difficulty.EASY].second_gem_from
    assert config.protect_backbeat_snare


def broken_config(tmp_path, old: str, new: str):
    text = CONFIG_PATH.read_text(encoding="utf-8")
    assert old in text, old
    path = tmp_path / "drum_difficulty.toml"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "old,new,message",
    [
        ("[hard]\n", "[hard]\nmax_gems = 3\n", "unknown keys"),
        ("[medium]\n", "[medium]\nallow_sixteenths = true\n", "unknown keys"),
        ("[easy]\n", "[easy]\nkick_with_a_pad = true\n", "unknown keys"),
        ('second_gem_from = ["red"', 'second_gem_from = ["kick", "red"', "hard rule"),
        ('    "green_tom",\n', "", "every gem once"),
        ("position_ratio = 0.54", "position_ratio = 0.9", "fall from Hard to Easy"),
        ("eighth = 0.6", "eighth = -0.6", "must not be negative"),
        ("[hard.soft_targets]\n", "[hard.soft_targets]\nfun = [0, 1]\n", "unknown soft targets"),
        # Hard's kick share comes from train since reference tuning step 4 (it was 0.159, Californication's).
        ("kick = 0.231", "kick = 0.5", "adding up to one"),
        ("lone_kick_share = 0.5", "lone_kick_share = 1.5", "lone_kick_share"),
        ('"red",\n    "green_cymbal"', '"snare",\n    "green_cymbal"', "unknown gem"),
        ("protect_backbeat_snare = true\n", "", "expected keys"),
        ("min_gap_s = 0.20\n", "min_gap_s = -0.1\n", "not negative"),
    ],
)
def test_the_settings_cannot_decide_a_hard_rule_or_be_wrong(tmp_path, old, new, message):
    with pytest.raises(ValueError, match=message):
        load_drum_config(broken_config(tmp_path, old, new))


# ---------------------------------------------------------------- what each level keeps


def test_every_level_keeps_the_hard_rules_and_the_chain():
    levels = reduce_drums(EXPERT, TEMPO)
    tracks = {Difficulty.EXPERT: EXPERT, **{level: item.track for level, item in levels.items()}}
    check_drum_levels(tracks, R)
    counts = [len(gems_by_tick(tracks[level])) for level in Difficulty]
    assert counts == sorted(counts, reverse=True) and counts[-1] < counts[0]


def test_a_crowded_position_gives_way_by_the_gem_order():
    levels = {level: gems_by_tick(item.track) for level, item in reduce_drums(EXPERT, TEMPO).items()}
    together = 2 * BAR + 2 * R
    assert set(levels[Difficulty.HARD][together]) == {K, S}, "the hi-hat gives way to the kick"
    assert set(levels[Difficulty.HARD][6 * BAR + 2 * R]) == {S, RD}, "the kick gives way to the ride"
    easy = levels[Difficulty.EASY]
    assert set(easy[0]) == {CR}, "on Easy the crash wins over the kick"
    assert set(easy[together]) == {S}
    hihat_with_kick = [tick for tick, gems in gems_by_tick(EXPERT).items() if set(gems) == {K, HH}]
    assert all(easy.get(tick, (K,)) == (K,) for tick in hihat_with_kick), "the kick wins over the hi-hat"
    ride_with_kick = [tick for tick, gems in gems_by_tick(EXPERT).items() if set(gems) == {K, RD}]
    assert all(easy.get(tick, (RD,)) == (RD,) for tick in ride_with_kick), "the ride wins over the kick"
    snare_and_hihat = [tick for tick, gems in gems_by_tick(EXPERT).items() if set(gems) == {S, HH}]
    assert snare_and_hihat and all(easy[tick] == (S,) for tick in snare_and_hihat), "the hi-hat goes"
    snare_and_ride = [tick for tick, gems in gems_by_tick(EXPERT).items() if set(gems) == {S, RD}]
    assert snare_and_ride and all(set(easy[tick]) == {S, RD} for tick in snare_and_ride), "the ride stays"


def test_the_backbeat_snare_stays_whatever_the_target():
    config = load_drum_config()
    tiny = {level: replace(settings, position_ratio=0.01) for level, settings in config.levels.items()}
    levels = reduce_drums(EXPERT, TEMPO, config=replace(config, levels=tiny))
    backbeats = {tick for tick, gems in gems_by_tick(EXPERT).items() if S in gems and tick % BAR in (R, 3 * R)}
    for level, item in levels.items():
        kept = gems_by_tick(item.track)
        assert backbeats <= {tick for tick, gems in kept.items() if S in gems}, level
        assert item.protected == len(backbeats)


def test_a_flam_keeps_one_snare_on_its_beat():
    positions = dict(rock_groove(2))
    positions[R + 11] = (S,)  # 11 ticks after the snare on beat 2, too far to share its tick
    levels = reduce_drums(drums(positions), TEMPO)
    for level, item in levels.items():
        ticks = sorted(gems_by_tick(item.track))
        gaps = np.diff(ticks) / R
        assert gaps.min() >= load_drum_config().levels[level].min_gap_beats, level


def test_medium_and_easy_have_no_sixteenths_and_hard_may_keep_some():
    config = load_drum_config()
    roomy = {level: replace(settings, position_ratio=0.95) for level, settings in config.levels.items()}
    levels = reduce_drums(EXPERT, TEMPO, config=replace(config, levels=roomy))
    assert levels[Difficulty.HARD].measures.sixteenth_share > 0, "sixteenths come last, but they may come"
    for level in (Difficulty.MEDIUM, Difficulty.EASY):
        assert levels[level].measures.sixteenth_share == 0
        assert all(tick % (R // 2) == 0 for tick in gems_by_tick(levels[level].track))


def test_the_reduction_is_deterministic():
    first = reduce_drums(EXPERT, TEMPO, {tick: random.Random(tick).random() for tick in gems_by_tick(EXPERT)})
    second = reduce_drums(EXPERT, TEMPO, {tick: random.Random(tick).random() for tick in gems_by_tick(EXPERT)})
    assert {level: item.track for level, item in first.items()} == {level: item.track for level, item in second.items()}


def test_soft_targets_only_warn():
    only_kicks = drums({tick: (K,) for tick in range(0, 16 * R, R // 2)})
    levels = reduce_drums(only_kicks, TEMPO)
    missed = [target.name for target in levels[Difficulty.HARD].soft_targets if not target.in_range]
    assert "kick_share" in missed and "red_share" in missed
    assert all(item.track.notes for item in levels.values())


def random_expert(rng: random.Random) -> dict[int, tuple[DrumGem, ...]]:
    """Gems the Expert charter could write: one per lane, at most two pads, anywhere on or off the grid."""
    positions: dict[int, tuple[DrumGem, ...]] = {}
    for _ in range(rng.randint(1, 120)):
        tick = rng.choice([rng.randrange(0, 32 * R, R // 4), rng.randrange(0, 32 * R)])
        lanes: dict[int, DrumGem] = {}
        for gem in rng.sample(list(DrumGem), rng.randint(1, 3)):
            lanes.setdefault(gem.lane, gem)
        pads = [gem for gem in lanes.values() if gem.is_pad][:2]
        positions[tick] = tuple(([K] if K in lanes.values() else []) + pads) or (K,)
    return positions


def random_config(rng: random.Random) -> DrumDifficultyConfig:
    config = load_drum_config()
    order = list(DrumGem)
    rng.shuffle(order)
    ratios = sorted((rng.uniform(0.05, 1.0) for _ in LOWER), reverse=True)
    levels = {}
    for level, ratio in zip(LOWER, ratios):
        allowed = [gem for gem in DrumGem if not (level is Difficulty.EASY and gem is K) and rng.random() < 0.7]
        levels[level] = DrumLevelConfig(
            ratio,
            rng.choice([0.0, 0.125, 0.25, 0.5, 1.0]),
            {gem: rng.uniform(-1, 1) for gem in DrumGem if rng.random() < 0.5},
            frozenset(allowed),
            config.levels[level].soft_targets,
        )
    return replace(config, gem_order=tuple(order), levels=levels, protect_backbeat_snare=rng.random() < 0.5)


@pytest.mark.parametrize("seed", range(60))
def test_no_settings_and_no_expert_can_break_a_hard_rule(seed):
    rng = random.Random(seed)
    expert = drums(random_expert(rng))
    strengths = {note.tick: rng.random() for note in expert.notes}
    levels = reduce_drums(expert, TEMPO, strengths, random_config(rng))
    check_drum_levels({Difficulty.EXPERT: expert, **{level: item.track for level, item in levels.items()}}, R)
    chart = Chart(SongMetadata("T", "A"), TEMPO, [expert, *(item.track for item in levels.values())])
    _, report = validate_chart_text(DotChartExporter().render(chart).decode("utf-8-sig"))
    assert report.ok, report.errors


@pytest.mark.parametrize(
    "level,positions,message",
    [
        (Difficulty.HARD, {0: (K, S, HH)}, "3 gems at once"),
        (Difficulty.MEDIUM, {R // 4: (S,)}, "a sixteenth"),
        (Difficulty.EASY, {0: (K, HH)}, "the kick with a pad"),
        (Difficulty.HARD, {R: (S,)}, "is not in expert"),
        (Difficulty.HARD, {0: (K, RD)}, "a gem that expert does not"),
        (Difficulty.HARD, {0: (S, HH, BT)}, "3 pads at once"),
    ],
)
def test_the_rule_check_catches_each_broken_rule(level, positions, message):
    expert = drums({0: (K, S, HH)})
    with pytest.raises(HardRuleViolation, match=message):
        check_drum_levels({Difficulty.EXPERT: expert, level: drums(positions, level)}, R)


def test_the_rule_check_refuses_a_sustain():
    held = Track(Instrument.DRUMS, Difficulty.HARD, [ChartNote(0, 1, 96)])
    with pytest.raises(HardRuleViolation, match="no sustain"):
        check_drum_levels({Difficulty.HARD: held}, R)


# ---------------------------------------------------------------- against the human


def as_human(track: Track) -> list[ReferenceDrumHit]:
    return [ReferenceDrumHit(TEMPO.seconds_at(float(tick)), tick, gems) for tick, gems in gems_by_tick(track).items()]


def test_levels_equal_to_the_human_score_perfectly_and_beside_the_naive_ones():
    levels = reduce_drums(EXPERT, TEMPO)
    tracks = [EXPERT, *(item.track for item in levels.values())]
    human = {track.difficulty: as_human(track) for track in tracks}
    result = drum_level_metrics(tracks, TEMPO, human)
    assert list(result) == ["hard", "medium", "easy"]
    for value in result.values():
        assert value["position"]["f1"] == 1.0 and value["worst_gem_gap"] == 0.0
        assert 0 <= value["every_nth_f1"] <= 1 and 0 <= value["beats_first_f1"] <= 1
    assert drum_level_metrics(tracks, TEMPO, {}) == {}
    lines = _drum_lines(
        "Song",
        {
            "drums": {
                "human_is_pro": True,
                "positions_mine": 1,
                "positions_human": 1,
                **{key: {"f1": 1.0, "precision": 1.0, "recall": 1.0} for key in ("position", "kick", "snare", "cymbal", "tom")},
                "hihat_ride_same_lane": None,
                "hihat_ride_compared": 0,
                "worst_gem_gap": 0.0,
                "gem_shares": {},
            },
            "drum_levels": result,
        },
    )
    assert any(re.match(r"hard\s+\d+ mine", line) for line in lines)
    assert any("beats first" in line for line in lines)


F1_FLOORS = {"hard": 0.85, "medium": 0.85, "easy": 0.80}
"""Approved by the owner on 2026-11-11: about 0.03 under what was measured (0.880 / 0.886 / 0.833)."""


@pytest.mark.real
@pytest.mark.parametrize("real_song", [CALIFORNICATION], indirect=True)
def test_californication_lower_levels_beat_both_naive_reductions(real_song):
    """Californication is train: the reduction's numbers were taken from its human chart."""
    tempo = real_song.tempo
    charted = build_tracks_for(
        Instrument.DRUMS, real_song.mono("drums"), tempo.tempo_map, real_song.stems.duration_s, not_before_s=tempo.lead_in_end_s
    )
    result = drum_level_metrics([item.track for item in charted], tempo.tempo_map, real_song.reference.drums.levels)
    print({level: (value["position"]["f1"], value["every_nth_f1"], value["beats_first_f1"]) for level, value in result.items()})
    assert list(result) == ["hard", "medium", "easy"]
    for level, value in result.items():
        assert value["position"]["f1"] >= F1_FLOORS[level], level
        assert value["position"]["f1"] > value["beats_first_f1"], level
        assert value["position"]["f1"] > value["every_nth_f1"], level
        assert value["worst_gem_gap"] <= 0.10, level
