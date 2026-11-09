"""Reduction of Expert to Hard, Medium and Easy, on synthetic note lists: no audio is involved."""

from __future__ import annotations

import random
import re
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from test_fret_mapping import random_weights

from chartgen.chart.difficulty import (
    HARD_RULES,
    REDUCED_LEVELS,
    DifficultyConfig,
    HardRuleViolation,
    Importance,
    LevelConfig,
    Position,
    SoftTargets,
    check_hard_rules,
    check_soft_targets,
    ideal_shape,
    load_config,
    measure_level,
    measure_track,
    metric_levels,
    place_voices,
    reduce_track,
    reduce_voices,
)
from chartgen.chart.fret_mapping import (
    SHAPES,
    NoteInput,
    is_playable,
    load_weights,
    map_notes,
    phrase_labels,
)
from chartgen.chart.hopo import hopo_threshold, natural_hopo_ticks, positions_of
from chartgen.clonehero.chart_format import DotChartExporter
from chartgen.clonehero.validate import validate_chart_text
from chartgen.core.model import Chart, ChartNote, Difficulty, Instrument, SongMetadata, Track
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent

TEMPO = TempoMap([TempoEvent(0, 120.0)])
"""One beat lasts half a second, a sixteenth 0.125 s."""
HARD, MEDIUM, EASY = Difficulty.HARD, Difficulty.MEDIUM, Difficulty.EASY
BAR = 192 * 4


def make_positions(
    ticks,
    tempo_map: TempoMap = TEMPO,
    shapes=None,
    strengths=None,
    lengths=None,
    pitches=None,
) -> list[Position]:
    count = len(ticks)
    return [
        Position(
            int(tick),
            float(tempo_map.seconds_at(float(tick))),
            tuple(shapes[index]) if shapes is not None else ((index % 4),),
            int(lengths[index]) if lengths is not None else 0,
            float(strengths[index]) if strengths is not None else 1.0,
            float(pitches[index]) if pitches is not None else float(index % 7),
        )
        for index, tick in enumerate(ticks)
    ] if count else []


def expert_track(positions) -> Track:
    notes = [
        ChartNote(position.tick, lane, position.length)
        for position in positions
        for lane in position.shape
    ]
    return Track(Instrument.GUITAR, Difficulty.EXPERT, notes)


def reduce(positions, tempo_map=TEMPO, config=None, weights=None):
    return reduce_track(
        Instrument.GUITAR, expert_track(positions), positions, tempo_map, config, weights
    )


def ticks_of(level) -> list[int]:
    return sorted({note.tick for note in level.track.notes})


def with_levels(config: DifficultyConfig, **changes) -> DifficultyConfig:
    """Change the same setting on all three levels."""
    return replace(
        config, levels={key: replace(value, **changes) for key, value in config.levels.items()}
    )


def random_song(rng: random.Random, count: int = 240) -> list[Position]:
    tick = 192
    positions = []
    for _ in range(count):
        gap = rng.choice([48, 48, 96, 96, 192, 192, 384, 768])
        sustain = gap - 48 if gap >= 192 and rng.random() < 0.4 else 0
        positions.append((tick, rng.choice(SHAPES), sustain, rng.random()))
        tick += gap
    return make_positions(
        [p[0] for p in positions],
        shapes=[p[1] for p in positions],
        lengths=[p[2] for p in positions],
        strengths=[p[3] for p in positions],
        pitches=[rng.choice([float("nan"), rng.uniform(40, 80)]) for _ in positions],
    )


def random_config(rng: random.Random) -> DifficultyConfig:
    def value() -> float:
        return rng.choice([0.0, 0.01, 0.5, 1.0, 5.0, 50.0])

    ratios = sorted((rng.uniform(0.05, 1.0) for _ in range(3)), reverse=True)
    levels = {}
    for level, ratio, tops in zip(REDUCED_LEVELS, ratios, ((2, 3, 4), (2, 3), (2, 3))):
        top = rng.choice(tops)
        levels[level] = LevelConfig(
            ratio,
            rng.choice([0.0, 0.1, 0.3, 0.6, 2.0]),
            top,
            tuple(sorted(rng.randint(0, top) for _ in range(5))),
            tuple(sorted(rng.randint(0, top) for _ in range(5))),
            value(),
            value(),
            rng.choice([0.0, 0.75, 1.0, 4.0]),
            rng.random() < 0.5,
            level is HARD and top >= 3 and rng.random() < 0.5,
            Importance(*(value() for _ in range(8))),
            SoftTargets(),
        )
    return DifficultyConfig(levels)


# ---------------------------------------------------------------- which notes stay


def sixteenth_song(bars: int = 16) -> list[Position]:
    return make_positions(range(BAR, BAR + bars * BAR, 48))


def test_downbeats_stay_on_every_level_and_weak_sixteenths_go():
    positions = sixteenth_song()
    levels = reduce(positions)
    downbeats = {p.tick for p in positions if p.tick % BAR == 0}
    for level in REDUCED_LEVELS:
        assert downbeats <= set(ticks_of(levels[level])), level
    hard = np.array(ticks_of(levels[HARD]))
    assert np.all(hard % 96 == 0), "at this tempo no sixteenth fits between its neighbours on Hard"


def test_accented_notes_outlast_weak_ones_in_the_same_metric_place():
    ticks = np.arange(BAR, BAR + 32 * BAR, 96)
    rng = np.random.default_rng(3)
    strengths = rng.uniform(0.5, 1.0, ticks.size)
    off_beat = ticks % 192 == 96
    accented = off_beat & (rng.random(ticks.size) < 0.25)
    strengths[accented] = 50.0
    # Hard keeps every beat and has room for some of the off-beat eighths.
    kept = set(ticks_of(reduce(make_positions(ticks, strengths=strengths))[HARD]))
    keep_accented = np.mean([tick in kept for tick in ticks[accented]])
    keep_plain = np.mean([tick in kept for tick in ticks[off_beat & ~accented]])
    assert keep_accented > keep_plain + 0.4


def test_irregular_accents_give_an_irregular_pattern():
    """This is what sets it apart from deleting every Nth note."""
    ticks = np.arange(BAR, BAR + 32 * BAR, 96)
    rng = np.random.default_rng(5)
    strengths = rng.uniform(0.1, 1.0, ticks.size)
    strengths[rng.random(ticks.size) < 0.3] = 40.0
    positions = make_positions(ticks, strengths=strengths)
    levels = reduce(positions)
    for level in REDUCED_LEVELS:
        kept = np.array(ticks_of(levels[level]))
        every_nth = ticks[np.round(np.linspace(0, ticks.size - 1, kept.size)).astype(int)]
        bar_patterns = {
            tuple(kept[(kept >= start) & (kept < start + BAR)] - start)
            for start in range(BAR, BAR + 32 * BAR, BAR)
        }
        assert len(bar_patterns) >= 3, level
        assert np.isin(kept, every_nth).mean() < 0.9, level


def test_every_phrase_start_stays_on_easy():
    """Each phrase begins on a weak, quiet sixteenth, the note least likely to stay otherwise."""
    ticks: list[int] = []
    strengths: list[float] = []
    start = BAR + 48
    for _ in range(12):
        phrase = [start + index * 96 for index in range(8)]
        ticks += phrase
        strengths += [0.01] + [1.0] * 7
        start = phrase[-1] + 2 * BAR + 48  # A silence of far more than the 0.9 s phrase gap.
    positions = make_positions(ticks, strengths=strengths)
    labels = phrase_labels([NoteInput(p.time_s) for p in positions], load_weights().phrase_gap_s)
    firsts = {ticks[index] for index in np.flatnonzero(np.r_[True, labels[1:] != labels[:-1]])}
    assert len(firsts) == 12
    assert firsts <= set(ticks_of(reduce(positions)[EASY]))


@pytest.mark.parametrize("seed", range(5))
def test_long_phrases_keep_a_note_on_easy_even_when_the_budget_is_tiny(seed):
    rng = random.Random(seed)
    positions = random_song(rng)
    config = load_config()
    config = replace(
        config, levels={**config.levels, EASY: replace(config.levels[EASY], position_ratio=0.0001)}
    )
    easy = set(ticks_of(reduce(positions, config=config)[EASY]))
    labels = phrase_labels([NoteInput(p.time_s) for p in positions], load_weights().phrase_gap_s)
    ticks = np.array([p.tick for p in positions])
    for label in np.unique(labels):
        members = ticks[labels == label]
        if members.size > 4:
            assert easy & set(members.tolist())


# ---------------------------------------------------------------- hard rules


def assert_hard_rules(levels, positions, config: DifficultyConfig, fret_weights=None) -> None:
    """Checks written apart from the code under test."""
    chain = [{p.tick for p in positions}, *(set(ticks_of(levels[key])) for key in REDUCED_LEVELS)]
    for upper, lower in zip(chain, chain[1:]):
        assert lower <= upper

    for level in REDUCED_LEVELS:
        grouped = positions_of(levels[level].track.notes)
        times = [TEMPO.seconds_at(float(tick)) for tick, _ in grouped]
        assert is_playable([lanes for _, lanes in grouped], times), level
        for tick, lanes in grouped:
            if level is EASY:
                assert len(lanes) == 1 and max(lanes) < 4, (tick, lanes)
            if level is MEDIUM:
                assert len(lanes) <= 2 and max(lanes) < 4, (tick, lanes)
            if level is HARD and not config.levels[HARD].three_note_chords:
                assert len(lanes) <= 2, (tick, lanes)
        ordered = [tick for tick, _ in grouped]
        following = dict(zip(ordered, ordered[1:]))
        for note in levels[level].track.notes:
            if note.tick in following:
                assert note.tick + note.length <= following[note.tick], (level, note)


@pytest.mark.parametrize("seed", range(4))
def test_hard_rules_hold_with_the_real_settings(seed):
    positions = random_song(random.Random(seed))
    config = load_config()
    assert_hard_rules(reduce(positions, config=config), positions, config)


@pytest.mark.parametrize("seed", range(30))
def test_hard_rules_hold_under_random_weights(seed):
    """Whatever a future tuning chooses, these never break."""
    rng = random.Random(seed)
    positions = random_song(rng)
    config = random_config(rng)
    weights = random_weights(rng)
    levels = reduce(positions, config=config, weights=weights)
    assert_hard_rules(levels, positions, config)
    labels = phrase_labels([NoteInput(p.time_s) for p in positions], weights.phrase_gap_s)
    tracks = {
        Difficulty.EXPERT: expert_track(positions),
        **{key: value.track for key, value in levels.items()},
    }
    assert check_hard_rules(tracks, positions, labels) == []


@pytest.mark.parametrize("seed", range(10))
def test_each_level_reaches_the_density_it_asks_for_under_random_weights(seed):
    """The selection obeys the ratio whenever nothing stops it. On a real song a missed range
    only warns, so this checks the mechanism and no build or real song can fail on it."""
    rng = random.Random(seed)
    ticks = np.arange(BAR, BAR + 64 * BAR, 48)
    positions = make_positions(ticks, strengths=[rng.random() for _ in ticks])
    config = with_levels(load_config(), min_gap_s=0.0)
    config = replace(
        config,
        levels={
            key: replace(value, importance=level.importance)
            for (key, value), level in zip(config.levels.items(), random_config(rng).levels.values())
        },
    )
    levels = reduce(positions, config=config, weights=replace(random_weights(rng), phrase_gap_s=5.0))
    for level in REDUCED_LEVELS:
        wanted = round(config.levels[level].position_ratio * len(positions))
        assert len(ticks_of(levels[level])) == wanted, level


def test_result_is_deterministic():
    positions = random_song(random.Random(11))
    first, second = reduce(positions), reduce(positions)
    for level in REDUCED_LEVELS:
        assert first[level].track.notes == second[level].track.notes


def test_ties_are_broken_the_same_way_whatever_the_input_order():
    positions = sixteenth_song(4)
    shuffled = list(positions)
    random.Random(1).shuffle(shuffled)
    for level in REDUCED_LEVELS:
        assert (
            reduce(positions)[level].track.notes
            == reduce_track(
                Instrument.GUITAR, expert_track(positions), shuffled, TEMPO
            )[level].track.notes
        )


def test_a_single_note_survives_on_every_level():
    levels = reduce(make_positions([192]))
    for level in REDUCED_LEVELS:
        assert ticks_of(levels[level]) == [192]
        assert levels[level].measures.min_gap_s == float("inf"), "one note has no gap"


def test_nothing_in_gives_nothing_out():
    assert reduce([]) == {}


def test_a_broken_result_raises_instead_of_being_written(monkeypatch):
    monkeypatch.setattr("chartgen.chart.difficulty.check_hard_rules", lambda *a: ["broken"])
    with pytest.raises(HardRuleViolation, match="broken"):
        reduce(sixteenth_song(2))


def test_check_hard_rules_notices_each_kind_of_break():
    positions = make_positions(range(0, 192 * 8, 192), shapes=[(0,)] * 8)
    labels = np.zeros(8, dtype=int)

    def track(level, notes):
        return Track(Instrument.GUITAR, level, notes)

    def tracks(**changes):
        base = {
            Difficulty.EXPERT: expert_track(positions),
            HARD: track(HARD, [ChartNote(0, 0)]),
            MEDIUM: track(MEDIUM, [ChartNote(0, 0)]),
            EASY: track(EASY, [ChartNote(0, 0)]),
        }
        base.update({Difficulty(key): value for key, value in changes.items()})
        return base

    assert check_hard_rules(tracks(), positions, labels) == []
    broken = {
        "chain": tracks(easy=track(EASY, [ChartNote(96, 0)])),
        "chord": tracks(easy=track(EASY, [ChartNote(0, 0), ChartNote(0, 1)])),
        "orange": tracks(medium=track(MEDIUM, [ChartNote(0, 4)])),
        "three": tracks(medium=track(MEDIUM, [ChartNote(0, 0), ChartNote(0, 1), ChartNote(0, 2)])),
        "sustain": tracks(hard=track(HARD, [ChartNote(0, 0, 500), ChartNote(192, 0)])),
    }
    for name, value in broken.items():
        assert check_hard_rules(value, positions, labels), name
    no_easy = tracks(easy=track(EASY, []))
    assert any("phrase" in problem for problem in check_hard_rules(no_easy, positions, labels))


def test_the_rules_are_listed_for_the_report():
    assert len(HARD_RULES) == 7


# ---------------------------------------------------------------- the chord rule


@pytest.mark.parametrize(
    "expert,level,expected",
    [
        # Hard keeps the lowest two notes at their distance, and chords prefer low frets.
        ((0, 1, 3), HARD, (0, 1)),
        ((0, 2, 3), HARD, (0, 2)),
        ((1, 2, 3), HARD, (0, 1)),
        ((1, 2, 4), HARD, (0, 1)),
        ((1, 3, 4), HARD, (0, 2)),
        ((2, 3, 4), HARD, (0, 1)),
        ((3, 4), HARD, (1, 2)),
        # Single notes stay where they are on Hard.
        ((2,), HARD, (2,)),
        ((4,), HARD, (4,)),
        # Medium keeps the same notes the same way, with no orange for single notes either.
        ((0, 1, 3), MEDIUM, (0, 1)),
        ((1, 3, 4), MEDIUM, (0, 2)),
        ((2, 3, 4), MEDIUM, (0, 1)),
        ((3, 4), MEDIUM, (1, 2)),
        ((2, 4), MEDIUM, (0, 2)),
        ((4,), MEDIUM, (3,)),
        ((3,), MEDIUM, (2,)),
        # Easy keeps the lowest note, moved into green, red and yellow.
        ((0, 1, 3), EASY, (0,)),
        ((1, 2, 4), EASY, (1,)),
        ((2, 3, 4), EASY, (1,)),
        ((3, 4), EASY, (2,)),
        ((4,), EASY, (2,)),
    ],
)
def test_chord_rule(expert, level, expected):
    assert ideal_shape(expert, level, load_config().levels[level]) == expected


def test_every_chord_rule_result_is_an_allowed_shape():
    config = load_config()
    for level in REDUCED_LEVELS:
        for shape in SHAPES:
            assert ideal_shape(shape, level, config.levels[level]) in SHAPES, (level, shape)


def test_lowest_notes_are_kept_and_their_distance_survives_the_move():
    assert reduce_voices((1, 3, 4), 2) == (1, 3)
    assert reduce_voices((1, 3, 4), 1) == (1,)
    assert place_voices((1, 3), (0, 0, 1, 1, 2), 2) == (0, 2)
    assert place_voices((2, 4), (0, 1, 2, 3, 3), 3) == (1, 3), "it slides down rather than shrink"


def test_single_notes_and_chords_have_separate_maps():
    config = replace(
        load_config().levels[HARD], lane_map=(0, 1, 2, 3, 4), chord_lane_map=(0, 0, 0, 1, 2)
    )
    assert ideal_shape((2,), HARD, config) == (2,)
    assert ideal_shape((2, 3), HARD, config) == (0, 1)


def test_chord_map_defaults_to_the_lane_map(tmp_path):
    def change(text: str) -> str:
        text = in_section("medium", "chord_lane_map = [0, 0, 0, 1, 2]\n", "")(text)
        return in_section("medium", "chord_fidelity = 1.5\n", "")(text)

    level = load_config(write_config(tmp_path, change)).levels[MEDIUM]
    assert level.chord_lane_map == level.lane_map
    assert level.chord_fidelity == level.fidelity


def test_chords_keep_moving_with_the_melody_instead_of_all_becoming_one_shape():
    """A strong pull to low frets would pass every lane target and flatten every chord change."""
    ticks = range(0, 192 * 64, 192)
    shapes = [(0, 1), (1, 2), (2, 3), (1, 3)] * 16
    pitches = [40.0, 42.0, 44.0, 42.0] * 16
    positions = make_positions(ticks, shapes=shapes, pitches=pitches)
    config = with_levels(load_config(), position_ratio=1.0, min_gap_s=0.0)
    grouped = positions_of(reduce(positions, config=config)[HARD].track.notes)
    assert len({lanes for _, lanes in grouped}) >= 2
    assert sum(a != b for (_, a), (_, b) in zip(grouped, grouped[1:])) >= len(grouped) / 4


def test_chords_arrive_as_the_rule_says_in_a_finished_track():
    """With no melody to follow and no hurry, every note lands exactly on the rule's result."""
    shapes = [shape for shape in SHAPES for _ in range(2)]
    config = with_levels(load_config(), position_ratio=1.0, min_gap_s=0.0)
    ticks = range(0, len(shapes) * 960, 960)
    positions = make_positions(ticks, shapes=shapes, pitches=[float("nan")] * len(shapes))
    levels = reduce(positions, config=config)
    for level in REDUCED_LEVELS:
        grouped = dict(positions_of(levels[level].track.notes))
        for position in positions:
            assert grouped[position.tick] == ideal_shape(
                position.shape, level, config.levels[level]
            ), (level, position.shape)


@pytest.mark.parametrize("seed", range(6))
def test_viterbi_can_only_slide_a_reduced_chord_never_change_it(seed):
    rng = random.Random(seed)
    positions = random_song(rng)
    config = with_levels(random_config(rng), position_ratio=1.0, min_gap_s=0.0)
    levels = reduce(positions, config=config, weights=random_weights(rng))
    by_tick = {p.tick: p.shape for p in positions}
    for level in REDUCED_LEVELS:
        size = {HARD: 3 if config.levels[HARD].three_note_chords else 2, MEDIUM: 2, EASY: 1}[level]
        for tick, lanes in positions_of(levels[level].track.notes):
            voices = reduce_voices(by_tick[tick], size)
            assert [lane - lanes[0] for lane in lanes] == [v - voices[0] for v in voices]
            assert max(lanes) <= config.levels[level].top_lane


def test_three_note_chords_on_hard_are_a_setting():
    shapes = [(0, 1, 3), (0, 2, 3), (1, 2, 4)] * 8
    positions = make_positions(range(0, 24 * 960, 960), shapes=shapes, pitches=[float("nan")] * 24)
    config = load_config()
    assert not config.levels[HARD].three_note_chords, "the default is no three-note chords"
    allowing = with_levels(config, position_ratio=1.0, min_gap_s=0.0)
    forbidding = reduce(positions, config=allowing)
    assert max(len(lanes) for _, lanes in positions_of(forbidding[HARD].track.notes)) == 2

    allowing = replace(
        allowing,
        levels={
            **allowing.levels,
            HARD: replace(
                allowing.levels[HARD],
                three_note_chords=True,
                chord_lane_map=(0, 1, 2, 3, 4),
                chord_fidelity=8.0,
            ),
        },
    )
    levels = reduce(positions, config=allowing)
    assert dict(positions_of(levels[HARD].track.notes)) == {p.tick: p.shape for p in positions}
    assert max(len(lanes) for _, lanes in positions_of(levels[MEDIUM].track.notes)) == 2


def test_any_two_shapes_can_follow_each_other_on_every_level():
    """Infinite costs must never leave Viterbi without a path, however fast the notes are."""
    pairs = [shape for first in SHAPES for second in SHAPES for shape in (first, second)]
    for three_note in (False, True):
        config = with_levels(load_config(), position_ratio=1.0, min_gap_s=0.0)
        config = replace(
            config,
            levels={
                **config.levels,
                HARD: replace(config.levels[HARD], three_note_chords=three_note),
            },
        )
        positions = make_positions(
            range(0, len(pairs) * 24, 24), shapes=pairs, pitches=[float("nan")] * len(pairs)
        )
        levels = reduce(positions, config=config)
        assert_hard_rules(levels, positions, config)


# ---------------------------------------------------------------- bars


def signature_map(numerator: int, denominator: int) -> TempoMap:
    return TempoMap([TempoEvent(0, 120.0)], [TimeSignatureEvent(0, numerator, denominator)])


@pytest.mark.parametrize(
    "numerator,denominator,tick,expected",
    [
        (4, 4, 0, "downbeat"),
        (4, 4, 384, "strong_beat"),
        (4, 4, 192, "beat"),
        (4, 4, 576, "beat"),
        (4, 4, 96, "eighth"),
        (4, 4, 48, "sixteenth"),
        (4, 4, 32, "sixteenth"),
        (4, 4, 186, "beat"),
        (4, 4, 760, "downbeat"),
        (3, 4, 0, "downbeat"),
        (3, 4, 192, "beat"),
        (3, 4, 384, "beat"),
        (6, 8, 0, "downbeat"),
        (6, 8, 288, "strong_beat"),
        (6, 8, 96, "eighth"),
        (6, 8, 48, "sixteenth"),
        (12, 8, 576, "strong_beat"),
        (12, 8, 288, "beat"),
    ],
)
def test_metric_levels_follow_the_time_signature(numerator, denominator, tick, expected):
    assert metric_levels([tick], signature_map(numerator, denominator)) == [expected]


def test_metric_levels_change_with_the_signature_event():
    tempo_map = TempoMap(
        [TempoEvent(0, 120.0)], [TimeSignatureEvent(0, 4, 4), TimeSignatureEvent(768, 3, 4)]
    )
    assert metric_levels([768, 768 + 384, 768 + 576], tempo_map) == ["downbeat", "beat", "downbeat"]


# ---------------------------------------------------------------- HOPOs


def test_hopo_threshold_scales_with_the_resolution():
    assert hopo_threshold(192) == 65
    assert hopo_threshold(480) == 162


@pytest.mark.parametrize(
    "positions,expected",
    [
        ([(0, (0,)), (65, (1,))], {65}),
        ([(0, (0,)), (66, (1,))], set()),
        ([(0, (0,)), (48, (0,))], set()),
        ([(0, (0,)), (48, (0, 1))], set()),
        ([(0, (0, 1)), (48, (2,))], {48}),
        ([(0, (0, 1)), (48, (1,))], {48}),
        ([(0, (0,)), (48, (1,)), (96, (2,))], {48, 96}),
    ],
    ids=["at limit", "past limit", "same fret", "chord", "after chord", "inside chord", "run"],
)
def test_natural_hopos(positions, expected):
    assert natural_hopo_ticks(positions, 192) == expected


def test_midi_does_not_count_a_note_inside_the_previous_chord():
    positions = [(0, (0, 1)), (48, (1,))]
    assert natural_hopo_ticks(positions, 192) == {48}
    assert natural_hopo_ticks(positions, 192, midi_subset_exception=True) == set()


def close_pairs() -> tuple[list[Position], TempoMap]:
    """Pairs of notes a sixteenth apart, at a tempo so slow they also pass the minimum gaps."""
    tempo_map = TempoMap([TempoEvent(0, 40.0)])
    ticks = [tick for start in range(0, 192 * 32, 192) for tick in (start, start + 48)]
    shapes = [(0,) if index % 2 == 0 else (2,) for index in range(len(ticks))]
    return make_positions(ticks, tempo_map, shapes, pitches=[float("nan")] * len(ticks)), tempo_map


def test_unwanted_hopos_become_strums_on_medium_and_easy_but_stay_on_hard():
    positions, tempo_map = close_pairs()
    config = with_levels(load_config(), position_ratio=1.0, min_gap_s=0.0)
    levels = reduce(positions, tempo_map, config)

    assert levels[HARD].measures.auto_hopo_share > 0.4
    assert levels[HARD].measures.final_hopo_share == levels[HARD].measures.auto_hopo_share
    assert levels[HARD].measures.forced_strums == 0
    assert not any(note.forced for note in levels[HARD].track.notes)

    for level in (MEDIUM, EASY):
        measures = levels[level].measures
        natural = natural_hopo_ticks(positions_of(levels[level].track.notes), tempo_map.resolution)
        assert natural, level
        assert {note.tick for note in levels[level].track.notes if note.forced} == natural
        assert measures.auto_hopo_share > 0.4, "the report still says what would have happened"
        assert measures.final_hopo_share == 0.0
        assert measures.forced_strums == len(natural)


def test_a_force_flag_only_lands_on_a_note_that_would_be_a_hopo():
    positions = make_positions(range(0, 192 * 32, 192))
    levels = reduce(positions, config=with_levels(load_config(), position_ratio=1.0, min_gap_s=0.0))
    for level in REDUCED_LEVELS:
        assert levels[level].measures.auto_hopo_share == 0.0
        assert not any(note.forced for note in levels[level].track.notes)


def test_measures_count_final_hopos_after_flags():
    tempo_map = TEMPO
    notes = [ChartNote(0, 0), ChartNote(48, 1), ChartNote(96, 2, forced=True)]
    measures = measure_track(Track(Instrument.GUITAR, MEDIUM, notes), tempo_map, 3)
    assert measures.auto_hopo_share == pytest.approx(2 / 3, abs=0.001)
    assert measures.final_hopo_share == pytest.approx(1 / 3, abs=0.001)
    assert measures.forced_strums == 1


def test_a_flag_on_a_strum_would_make_a_hopo_so_the_measures_do_not_call_it_a_fix():
    notes = [ChartNote(0, 0), ChartNote(192, 1, forced=True)]
    measures = measure_track(Track(Instrument.GUITAR, MEDIUM, notes), TEMPO, 2)
    assert measures.auto_hopo_share == 0.0
    assert measures.final_hopo_share == 0.5
    assert measures.forced_strums == 0


def what_the_game_reads(section: str, resolution: int = 192) -> tuple[set[int], set[int], set[int]]:
    """Read a written track as the game does, sharing no code with the writer or the reducer.

    Returns the natural HOPOs, the ticks with a force flag, and the ticks holding a chord.
    """
    lanes: dict[int, set[int]] = {}
    flagged: set[int] = set()
    for tick, number in re.findall(r"(\d+) = N (\d+) \d+", section):
        if int(number) == 5:
            flagged.add(int(tick))
        else:
            lanes.setdefault(int(tick), set()).add(int(number))
    limit = 65 * resolution // 192
    ticks = sorted(lanes)
    natural = {
        after
        for before, after in zip(ticks, ticks[1:])
        if len(lanes[after]) == 1
        and after - before <= limit
        and (len(lanes[before]) > 1 or lanes[before] != lanes[after])
    }
    return natural, flagged, {tick for tick in ticks if len(lanes[tick]) > 1}


@pytest.mark.parametrize(
    "section,expected_natural,expected_flagged,expected_chords",
    [
        ("0 = N 0 0\n48 = N 1 0\n48 = N 5 0", {48}, {48}, set()),
        ("0 = N 0 0\n192 = N 1 0\n192 = N 5 0", set(), {192}, set()),
        ("0 = N 0 0\n0 = N 1 0\n48 = N 2 0\n48 = N 3 0\n48 = N 5 0", set(), {48}, {0, 48}),
    ],
    ids=["flag on a hopo", "flag on a strum", "flag on a chord"],
)
def test_the_reader_in_these_tests_tells_good_flags_from_bad(
    section, expected_natural, expected_flagged, expected_chords
):
    """So the test below would fail if a flag ever landed on a strum or a chord."""
    assert what_the_game_reads(section) == (expected_natural, expected_flagged, expected_chords)


@pytest.mark.parametrize("seed", range(20))
def test_force_flags_only_ever_land_on_natural_hopos(seed):
    """The flag flips a note. On anything but a natural HOPO it would create the very HOPO it is
    meant to remove, so the written file must hold no flag anywhere else, on any song or setting."""
    rng = random.Random(seed)
    tempo_map = TempoMap([TempoEvent(0, rng.choice([40.0, 60.0, 120.0, 180.0]))])
    positions = random_song(rng)
    positions = make_positions(
        [p.tick for p in positions],
        tempo_map,
        shapes=[p.shape for p in positions],
        lengths=[p.length for p in positions],
        strengths=[p.strength for p in positions],
    )
    config = random_config(rng)
    config = replace(
        config,
        levels={
            key: replace(value, keep_auto_hopos=key is HARD and rng.random() < 0.5)
            for key, value in config.levels.items()
        },
    )
    levels = reduce(positions, tempo_map, config, replace(random_weights(rng), phrase_gap_s=0.9))
    tracks = [expert_track(positions), *(levels[level].track for level in REDUCED_LEVELS)]
    text = DotChartExporter().render(
        Chart(SongMetadata("Song", "Artist"), tempo_map, tracks)
    ).decode("utf-8-sig")
    sections = dict(re.findall(r"\[(\w+)\]\s*\{(.*?)\}", text, flags=re.S))

    assert "N 5 0" not in sections["ExpertSingle"]
    for name, level in (("HardSingle", HARD), ("MediumSingle", MEDIUM), ("EasySingle", EASY)):
        natural, flagged, chords = what_the_game_reads(sections[name])
        assert flagged <= natural, (name, sorted(flagged - natural))
        assert not flagged & chords, name
        if config.levels[level].keep_auto_hopos:
            assert not flagged, name
        else:
            assert flagged == natural, (name, "every natural HOPO becomes a strum")


# ---------------------------------------------------------------- soft targets


def test_missing_a_soft_target_warns_and_never_fails():
    """Single notes cannot reach any chord share."""
    levels = reduce(sixteenth_song())
    missed = {result.name for result in levels[HARD].missed_targets()}
    assert "chord_share" in missed
    assert set(levels) == set(REDUCED_LEVELS)


def test_soft_target_results_say_where_the_value_lies():
    measures = measure_level(
        [(0, (0,)), (192, (4,))], [False, True], [0.0, 0.5], 192, expert_positions=2
    )
    (result,) = check_soft_targets(measures, SoftTargets({"orange_share": (0.0, 0.1)}))
    assert result.value == 0.5 and not result.in_range


def test_each_lane_may_stray_from_the_human_by_the_tolerance():
    measures = measure_level(
        [(0, (0,)), (192, (0,)), (384, (1,)), (576, (3,))],
        [False] * 4,
        [0.0, 0.5, 1.0, 1.5],
        192,
        expert_positions=4,
    )
    targets = SoftTargets({}, (0.5, 0.25, 0.0, 0.0, 0.25), 0.10)
    results = {result.name: result for result in check_soft_targets(measures, targets)}
    assert set(results) == {"green_lane", "red_lane", "yellow_lane", "blue_lane", "orange_lane"}
    assert results["green_lane"].in_range
    assert (results["green_lane"].low, results["green_lane"].high) == (0.4, 0.6)
    assert not results["blue_lane"].in_range, "0.25 is more than 0.10 above 0.0"
    assert not results["orange_lane"].in_range, "0.0 is more than 0.10 below 0.25"
    assert results["yellow_lane"].low == 0.0, "a share cannot go below zero"


def test_automatic_hopos_are_a_soft_target_on_every_level():
    config = load_config()
    assert "auto_hopo_share" in config.expert_targets.ranges
    for level in REDUCED_LEVELS:
        assert "auto_hopo_share" in config.levels[level].soft_targets.ranges


def test_too_many_automatic_hopos_only_warn_and_change_nothing():
    """On Hard they stay, whatever the target says: the target does not steer the result."""
    positions, tempo_map = close_pairs()
    config = with_levels(load_config(), position_ratio=1.0, min_gap_s=0.0)
    level = reduce(positions, tempo_map, config)[HARD]
    assert "auto_hopo_share" in {result.name for result in level.missed_targets()}
    assert level.measures.final_hopo_share == level.measures.auto_hopo_share


def test_short_sustains_become_plain_notes_where_the_level_says_so():
    ticks = range(0, 192 * 64, 192 * 4)
    lengths = [144 if index % 2 else 384 for index in range(len(ticks))]
    positions = make_positions(ticks, lengths=lengths)
    levels = reduce(positions, config=with_levels(load_config(), position_ratio=1.0, min_gap_s=0.0))
    assert {note.length for note in levels[HARD].track.notes} == {144, 384}
    assert {note.length for note in levels[EASY].track.notes} == {0, 384}


def test_a_note_just_off_the_grid_counts_where_it_nearly_is():
    measures = measure_level(
        [(6, (0,)), (198, (1,)), (390, (2,)), (582, (3,))],
        [False] * 4,
        [0.0, 0.5, 1.0, 1.5],
        192,
        expert_positions=4,
    )
    assert measures.on_beat_share == 1.0
    assert measures.sixteenth_share == 0.0


def test_measures_of_a_level():
    measures = measure_level(
        [(0, (0, 1)), (96, (2,)), (144, (3,)), (192, (4,))],
        [True, False, False, False],
        [0.0, 0.25, 0.375, 0.5],
        192,
        expert_positions=8,
    )
    assert measures.positions == 4
    assert measures.position_ratio == 0.5
    assert measures.chord_share == 0.25
    assert measures.green_share == 0.2
    assert measures.orange_share == 0.2
    assert measures.on_beat_share == 0.5
    assert measures.sixteenth_share == 0.25
    assert measures.min_gap_s == 0.125
    assert measures.sustain_share == 0.25


# ---------------------------------------------------------------- the configuration


def write_config(tmp_path: Path, change) -> Path:
    from chartgen.chart.difficulty import CONFIG_PATH

    text = CONFIG_PATH.read_text(encoding="utf-8")
    path = tmp_path / "difficulty.toml"
    path.write_text(change(text), encoding="utf-8")
    return path


def in_section(section: str, old: str, new: str):
    def change(text: str) -> str:
        head, body = text.split(f"[{section}]\n", 1)
        return f"{head}[{section}]\n{body.replace(old, new, 1)}"

    return change


def test_shipped_configuration_loads():
    config = load_config()
    assert set(config.levels) == set(REDUCED_LEVELS)


@pytest.mark.parametrize(
    "change",
    [
        in_section("medium", "top_lane = 3", "top_lane = 4"),
        in_section("easy", "top_lane = 2", "top_lane = 4"),
        in_section("medium", "keep_auto_hopos = false", "keep_auto_hopos = false\nthree_note_chords = true"),
        in_section("easy", "keep_auto_hopos = false", "keep_auto_hopos = false\nthree_note_chords = true"),
    ],
    ids=["orange on medium", "orange on easy", "triads on medium", "triads on easy"],
)
def test_configuration_cannot_weaken_a_hard_rule(tmp_path, change):
    with pytest.raises(ValueError):
        load_config(write_config(tmp_path, change))


def test_three_note_chords_need_room_on_the_neck(tmp_path):
    """A chord can span three frets, so a level limited to green, red, yellow cannot hold it."""

    def change(text: str) -> str:
        text = in_section("hard", "three_note_chords = false", "three_note_chords = true")(text)
        text = in_section("hard", "top_lane = 4", "top_lane = 2")(text)
        return in_section("hard", "lane_map = [0, 1, 2, 3, 4]", "lane_map = [0, 1, 1, 2, 2]")(text)

    with pytest.raises(ValueError, match="three_note_chords"):
        load_config(write_config(tmp_path, change))


def test_viterbi_never_silently_gives_up_when_no_shape_is_left():
    notes = [NoteInput(0.0), NoteInput(1.0)]
    extra = np.full((2, len(SHAPES)), np.inf)
    with pytest.raises(ValueError, match="no allowed"):
        map_notes(notes, load_weights(), extra)


@pytest.mark.parametrize(
    "change",
    [
        in_section("hard", "lane_map = [0, 1, 2, 3, 4]", "lane_map = [0, 1, 2]"),
        in_section("medium", "lane_map = [0, 1, 1, 2, 3]", "lane_map = [0, 1, 1, 2, 4]"),
        in_section("easy", "lane_map = [0, 1, 1, 2, 2]", "lane_map = [2, 1, 1, 0, 0]"),
        in_section("hard", "position_ratio = 0.67", "position_ratio = 0.2"),
        in_section("hard", "position_ratio = 0.67", "position_ratio = 1.5"),
        in_section("hard", "fidelity = 8.0", "fidelity = -1.0"),
        in_section("hard", "fidelity = 8.0", "unknown_setting = 1"),
        in_section("hard", "min_sustain_beats = 0.75", "min_sustain_beats = -1.0"),
        in_section("easy.importance", "beat = 0.2", "typo = 0.2"),
        in_section("hard.soft_targets", "chord_share", "typo_share"),
        in_section("expert.soft_targets", "auto_hopo_share", "typo_share"),
        in_section("hard", "chord_lane_map = [0, 0, 0, 1, 2]", "chord_lane_map = [0, 0, 0, 1]"),
        in_section("medium", "chord_lane_map = [0, 0, 0, 1, 2]", "chord_lane_map = [0, 0, 0, 1, 4]"),
        in_section("hard", "chord_fidelity = 1.5", "chord_fidelity = -1.5"),
        in_section("hard", "lane_shares = [0.318, 0.287, 0.223, 0.110, 0.062]", "lane_shares = [0.5, 0.2]"),
        in_section("hard", "lane_shares = [0.318, 0.287, 0.223, 0.110, 0.062]", "lane_shares = [0.9, 0.9, 0.0, 0.0, 0.0]"),
        in_section("lane_targets", "tolerance = 0.10", "tolerance = -0.10"),
        in_section("expert", "lane_shares", "unknown_setting = 1\nlane_shares"),
        in_section("hard.soft_targets", "chord_share = [0.40, 0.70]", "chord_share = [0.70, 0.40]"),
        in_section("importance", "downbeat = 1.0", "downbeat = -1.0"),
        in_section("importance", "downbeat = 1.0", ""),
    ],
    ids=[
        "short map",
        "map above top",
        "map falls",
        "ratio order",
        "ratio range",
        "negative fidelity",
        "unknown key",
        "negative sustain",
        "unknown level weight",
        "unknown target",
        "unknown expert target",
        "short chord map",
        "chord map above top",
        "negative chord fidelity",
        "short lane shares",
        "lane shares over one",
        "negative tolerance",
        "expert setting",
        "backwards target",
        "negative weight",
        "missing weight",
    ],
)
def test_bad_configuration_is_refused(tmp_path, change):
    with pytest.raises(ValueError):
        load_config(write_config(tmp_path, change))


# ---------------------------------------------------------------- the written file


def written_chart(levels, positions) -> str:
    tracks = [expert_track(positions), *(levels[level].track for level in REDUCED_LEVELS)]
    chart = Chart(SongMetadata("Song", "Artist"), TEMPO, tracks)
    return DotChartExporter().render(chart).decode("utf-8-sig")


def test_all_four_levels_are_written_and_pass_the_validator():
    positions = random_song(random.Random(2))
    text = written_chart(reduce(positions), positions)
    _, report = validate_chart_text(text)
    assert report.ok, report.errors
    for name in ("ExpertSingle", "HardSingle", "MediumSingle", "EasySingle"):
        assert f"[{name}]" in text


def test_force_flags_reach_the_file_on_the_right_ticks():
    positions, tempo_map = close_pairs()
    config = with_levels(load_config(), position_ratio=1.0, min_gap_s=0.0)
    levels = reduce(positions, tempo_map, config)
    tracks = [expert_track(positions), *(levels[level].track for level in REDUCED_LEVELS)]
    text = DotChartExporter().render(
        Chart(SongMetadata("Song", "Artist"), tempo_map, tracks)
    ).decode("utf-8-sig")
    sections = dict(re.findall(r"\[(\w+)\]\s*\{(.*?)\}", text, flags=re.S))
    assert "N 5 0" not in sections["HardSingle"]
    for name, level in (("MediumSingle", MEDIUM), ("EasySingle", EASY)):
        flagged = {int(tick) for tick in re.findall(r"(\d+) = N 5 0", sections[name])}
        assert flagged == {note.tick for note in levels[level].track.notes if note.forced}
        assert flagged


def chart_text(**sections: str) -> str:
    body = "".join(f"[{name}]\n{{\n{notes}\n}}\n" for name, notes in sections.items())
    return f"[Song]\n{{\n  Resolution = 192\n}}\n[SyncTrack]\n{{\n  0 = TS 4\n  0 = B 120000\n}}\n{body}"


GOOD_EXPERT = "  0 = N 0 0\n  0 = N 1 0\n  192 = N 2 0"


@pytest.mark.parametrize(
    "sections,message",
    [
        ({"ExpertSingle": GOOD_EXPERT, "EasySingle": "  96 = N 0 0"}, "EasySingle.*tick 96"),
        (
            {"ExpertSingle": GOOD_EXPERT, "HardSingle": "  0 = N 0 0", "EasySingle": "  192 = N 0 0"},
            "EasySingle.*tick 192",
        ),
        ({"ExpertSingle": GOOD_EXPERT, "EasySingle": "  0 = N 0 0\n  0 = N 1 0"}, "chord"),
        ({"ExpertSingle": GOOD_EXPERT, "EasySingle": "  0 = N 4 0"}, "orange"),
        ({"ExpertSingle": GOOD_EXPERT, "MediumSingle": "  0 = N 4 0"}, "orange"),
        (
            {"ExpertSingle": GOOD_EXPERT, "MediumSingle": "  0 = N 0 0\n  0 = N 1 0\n  0 = N 2 0"},
            "chord",
        ),
        ({"ExpertSingle": "  0 = N 0 200\n  192 = N 1 0"}, "sustain"),
    ],
    ids=["not on expert", "not on the next level up", "easy chord", "easy orange", "medium orange", "medium triad", "sustain"],
)
def test_validator_catches_a_broken_difficulty_from_the_file_alone(sections, message):
    _, report = validate_chart_text(chart_text(**sections))
    assert any(re.search(message, error) for error in report.errors), report.errors


def test_validator_accepts_flags_and_a_sustain_that_ends_on_the_next_note():
    text = chart_text(
        ExpertSingle="  0 = N 0 192\n  192 = N 1 0\n  192 = N 5 0",
        EasySingle="  0 = N 0 0\n  192 = N 1 0\n  192 = N 5 0",
    )
    _, report = validate_chart_text(text)
    assert report.ok, report.errors


def test_bass_and_keys_follow_the_same_structure():
    _, report = validate_chart_text(
        chart_text(ExpertDoubleBass=GOOD_EXPERT, EasyDoubleBass="  0 = N 0 0\n  0 = N 1 0")
    )
    assert any("chord" in error for error in report.errors)


def test_drums_are_left_alone():
    """On drums, lane 4 is a pad and two lanes together are normal."""
    _, report = validate_chart_text(
        chart_text(ExpertDrums="  0 = N 0 0\n  0 = N 4 0", EasyDrums="  0 = N 0 0\n  0 = N 4 0")
    )
    assert report.ok, report.errors
