"""Step 5c of the reference tuning: Easy drums in a fast song (SPEC 45).

Where the tempo is above 150 BPM, a kick on Easy that stands for an Expert kick + hi-hat stays only if the
previous kick is at least two beats at 150 BPM (0.8 s) before it; otherwise the position goes. A principle,
not a tuned value: train has one fast song. At 150 BPM or slower nothing changes.
"""

from dataclasses import replace

import pytest

from chartgen.chart.drum_difficulty import CONFIG_PATH, gems_by_tick, load_drum_config, reduce_drums
from chartgen.core.drums import DrumGem
from chartgen.core.model import Difficulty, Instrument, Track
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent

R = 192
NAME = {DrumGem.KICK: "K", DrumGem.RED: "S", DrumGem.YELLOW_CYMBAL: "h"}


def rock_beat(bars: int, kick_gems: tuple[DrumGem, ...] = (DrumGem.KICK, DrumGem.YELLOW_CYMBAL)) -> Track:
    """Kick on 1 and 3, snare on 2 and 4, with a hi-hat on every eighth unless the kick comes alone."""
    notes = []
    for bar in range(bars):
        for beat in range(4):
            tick = (bar * 4 + beat) * R
            gems = kick_gems if beat % 2 == 0 else (DrumGem.RED, DrumGem.YELLOW_CYMBAL)
            notes += [gem.note(tick) for gem in gems]
            if DrumGem.YELLOW_CYMBAL in kick_gems:
                notes.append(DrumGem.YELLOW_CYMBAL.note(tick + R // 2))
    return Track(Instrument.DRUMS, Difficulty.EXPERT, notes)


def tempo(*events: tuple[int, float]) -> TempoMap:
    return TempoMap([TempoEvent(tick, bpm) for tick, bpm in events], [TimeSignatureEvent(0, 4, 4)], resolution=R)


def without_rule():
    config = load_drum_config()
    return replace(config, levels={level: replace(s, fast_kick_hihat_gap_beats=None) for level, s in config.levels.items()})


def easy_bar(track: Track, bar: int) -> str:
    gems = gems_by_tick(track)
    start = bar * 4 * R
    return "".join("".join(NAME[g] for g in gems[t]) if t in gems else "." for t in range(start, start + 4 * R, R // 2))


def test_the_rule_is_set_on_easy_only():
    config = load_drum_config()
    assert config.levels[Difficulty.EASY].fast_kick_hihat_gap_beats == 2.0
    assert config.levels[Difficulty.HARD].fast_kick_hihat_gap_beats is None
    assert config.levels[Difficulty.MEDIUM].fast_kick_hihat_gap_beats is None


def test_a_fast_rock_beat_keeps_one_kick_a_bar_on_easy():
    reduced = reduce_drums(rock_beat(8), tempo((0, 183.0)))
    easy = reduced[Difficulty.EASY]
    assert easy_bar(easy.track, 2) == "K.S...S.", "the kick on 3 is 0.66 s after the one on 1, under 0.8 s"
    before = reduce_drums(rock_beat(8), tempo((0, 183.0)), None, without_rule())[Difficulty.EASY]
    assert easy_bar(before.track, 2) == "K.S.K.S.", "without the rule the test would show nothing"
    assert easy.fast_kicks_dropped == 8
    for level in (Difficulty.HARD, Difficulty.MEDIUM):
        assert reduced[level].track.notes == reduce_drums(rock_beat(8), tempo((0, 183.0)), None, without_rule())[level].track.notes


@pytest.mark.parametrize("bpm", [150.0, 140.0, 100.0])
def test_at_150_bpm_or_slower_nothing_changes(bpm):
    with_rule = reduce_drums(rock_beat(8), tempo((0, bpm)))
    plain = reduce_drums(rock_beat(8), tempo((0, bpm)), None, without_rule())
    assert {level: item.track.notes for level, item in with_rule.items()} == {
        level: item.track.notes for level, item in plain.items()
    }
    assert with_rule[Difficulty.EASY].fast_kicks_dropped == 0


def test_lone_kicks_are_not_spaced():
    expert = rock_beat(8, kick_gems=(DrumGem.KICK,))
    with_rule = reduce_drums(expert, tempo((0, 183.0)))[Difficulty.EASY]
    plain = reduce_drums(expert, tempo((0, 183.0)), None, without_rule())[Difficulty.EASY]
    assert with_rule.track.notes == plain.track.notes and with_rule.fast_kicks_dropped == 0


def test_the_tempo_is_read_where_the_kick_is():
    # 140 BPM for four bars, then 183.
    expert = rock_beat(8)
    reduced = reduce_drums(expert, tempo((0, 140.0), (16 * R, 183.0)))[Difficulty.EASY]
    assert easy_bar(reduced.track, 1) == "K.S.K.S."
    assert easy_bar(reduced.track, 6) == "K.S...S."


@pytest.mark.parametrize("value", ["0", "-1.0"])
def test_the_fast_kick_gap_must_be_positive(tmp_path, value):
    text = CONFIG_PATH.read_text(encoding="utf-8").replace(
        "fast_kick_hihat_gap_beats = 2.0", f"fast_kick_hihat_gap_beats = {value}", 1
    )
    path = tmp_path / "drum_difficulty.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="fast_kick_hihat_gap_beats"):
        load_drum_config(path)
