"""Step 1 of the reference tuning: a song faster than the tempo search's 160 BPM is found at half its
tempo, and the snare says when each beat is two. Drum levels then also keep a floor in seconds.

The kit is the synthetic one of the drum classifier's tests, so the classifier hears its snares.
"""

from dataclasses import replace

import numpy as np
import pytest
from test_drum_hits import SR, render

from chartgen.audio import meter
from chartgen.audio.drum_hits import DrumAnalysis, DrumHit
from chartgen.audio.meter import BOTH_PARITIES_SHARE, MAX_DOUBLED_BPM, SNARE_WITH_KICK_LIMIT, check_double_time
from chartgen.audio.tempo import MAX_BPM, estimate_tempo_map
from chartgen.chart.charter import MIN_SUSTAIN_S, _sustain_ticks
from chartgen.chart.difficulty import Position, _build_level, load_config, select_positions
from chartgen.chart.drum_difficulty import load_drum_config, reduce_drums
from chartgen.core import Difficulty, Instrument, TempoEvent, TempoMap, TimeSignatureEvent, Track
from chartgen.core.drums import DrumGem, DrumPiece
from chartgen.core.timing import seconds_floor

LOWER = (Difficulty.HARD, Difficulty.MEDIUM, Difficulty.EASY)


def rock(bpm: float, bars: int, start: float) -> list[tuple[float, DrumPiece]]:
    """A backbeat at ``bpm``: kick on 1 and 3, snare on 2 and 4, eighth hi-hats."""
    beat = 60.0 / bpm
    events = []
    for bar in range(bars):
        for number in range(4):
            time = start + (4 * bar + number) * beat
            if number in (0, 2):
                events.append((time, DrumPiece.KICK))
            if number in (1, 3):
                events.append((time, DrumPiece.SNARE))
            events += [(time, DrumPiece.HI_HAT), (time + beat / 2, DrumPiece.HI_HAT)]
    return events


def grid(bpm: float) -> TempoMap:
    return TempoMap([TempoEvent(0, bpm)], [TimeSignatureEvent(0, 4, 4)])


def on_grid_beats(bpm: float, beats: int = 2) -> float:
    """A start time that falls on a beat of :func:`grid`, so the pattern lines up with it."""
    return beats * 60.0 / bpm


# ---------------------------------------------------------------- what the snare says


@pytest.mark.heavy
def test_a_backbeat_on_every_beat_of_the_grid_splits_it_in_two():
    drums = render(rock(190.0, 40, on_grid_beats(95.0)))
    check = check_double_time(grid(95.0), drums, drums, 95.0, SR)
    assert check.double, check.reason
    assert check.doubled_bpm == pytest.approx(190.0)
    assert check.both_parities_share >= BOTH_PARITIES_SHARE
    assert check.snare_with_kick <= SNARE_WITH_KICK_LIMIT


def test_a_backbeat_every_second_beat_is_left_alone():
    drums = render(rock(95.0, 24, on_grid_beats(95.0)))
    check = check_double_time(grid(95.0), drums, drums, 95.0, SR)
    assert not check.double
    assert check.both_parities_share < BOTH_PARITIES_SHARE
    assert "below" in check.reason


def test_a_kick_under_every_snare_is_taken_for_the_kick_in_the_snare_band(monkeypatch):
    """A kick on every beat leaks into the snare's band and looks like a snare on every beat, as in
    Toca Toca. What the classifier hears is given here, because the synthetic kit is too clean to leak."""
    beat = 60.0 / 95.0
    heard = tuple(
        DrumHit(2 * beat + number * beat, (DrumPiece.KICK, DrumPiece.SNARE), 1.0) for number in range(4 * 40)
    )
    monkeypatch.setattr(meter, "detect_drum_hits", lambda drums: DrumAnalysis(heard, {}, {}, 0.0))
    drums = render(rock(95.0, 40, on_grid_beats(95.0)))
    check = check_double_time(grid(95.0), drums, drums, 95.0, SR)
    assert check.windows >= 8 and check.both_parities_share == 1.0
    assert not check.double
    assert check.snare_with_kick > SNARE_WITH_KICK_LIMIT
    assert "hears the kick" in check.reason


def test_a_split_never_goes_past_the_ceiling():
    drums = render(rock(240.0, 40, on_grid_beats(120.0)))
    check = check_double_time(grid(120.0), drums, drums, 120.0, SR)
    assert 2 * 120.0 > MAX_DOUBLED_BPM
    assert not check.double
    assert "faster than" in check.reason


def test_too_few_snares_say_nothing():
    drums = render(rock(190.0, 2, on_grid_beats(95.0)))
    check = check_double_time(grid(95.0), drums, drums, 95.0, SR)
    assert not check.double
    assert "enough snares" in check.reason


def test_silent_drums_are_not_asked():
    silence = np.zeros(20 * SR, dtype=np.float32)
    noise = np.random.default_rng(1).standard_normal(20 * SR).astype(np.float32)
    assert check_double_time(grid(95.0), silence, noise, 95.0, SR) is None


# ---------------------------------------------------------------- the whole tempo analysis


@pytest.fixture(scope="module")
def fast_backbeat() -> np.ndarray:
    return render(rock(190.0, 40, 1.0))


@pytest.mark.heavy
def test_a_fast_song_comes_out_at_its_own_tempo(fast_backbeat):
    analysis = estimate_tempo_map(fast_backbeat, SR, drums=fast_backbeat)
    assert 190.0 > MAX_BPM, "the search alone cannot reach it"
    assert analysis.double_time is not None and analysis.double_time.double
    assert analysis.bpm == pytest.approx(190.0, abs=1.0)
    assert "split in two" in analysis.decision
    beats = 1.0 + np.arange(4 * 40) * 60.0 / 190.0
    tempo_map = analysis.tempo_map
    last = int(tempo_map.ticks_at(beats[-1] + 0.1) // tempo_map.resolution)
    grid_beats = tempo_map.seconds_at(np.arange(1, last + 1, dtype=np.float64) * tempo_map.resolution)
    distance = np.abs(grid_beats[None, :] - beats[2:-2, None]).min(axis=1)
    assert np.median(distance) < 0.02, "every beat of the song is a beat of the grid"


@pytest.mark.heavy
def test_a_slow_backbeat_keeps_its_tempo():
    drums = render(rock(95.0, 24, 1.0))
    analysis = estimate_tempo_map(drums, SR, drums=drums)
    assert analysis.double_time is not None and not analysis.double_time.double
    assert analysis.bpm == pytest.approx(95.0, abs=1.0)


@pytest.mark.heavy
def test_a_given_tempo_is_never_split(fast_backbeat):
    analysis = estimate_tempo_map(fast_backbeat, SR, bpm_override=95.0, drums=fast_backbeat)
    assert analysis.bpm == 95.0
    assert analysis.double_time is None


@pytest.mark.heavy
def test_without_drums_nothing_is_split(fast_backbeat):
    assert estimate_tempo_map(fast_backbeat, SR).double_time is None


# ---------------------------------------------------------------- drum levels in a fast song


R = 192


def eighth_groove(bars: int) -> Track:
    """Kick on 1 and 3, snare on 2 and 4, a hi-hat on every eighth; the hi-hat alone between beats."""
    notes = []
    for tick in range(0, bars * 4 * R, R // 2):
        beat, on_beat = divmod(tick, R)
        notes.append(DrumGem.YELLOW_CYMBAL.note(tick))
        if on_beat == 0:
            notes.append((DrumGem.KICK if beat % 2 == 0 else DrumGem.RED).note(tick))
    return Track(Instrument.DRUMS, Difficulty.EXPERT, notes)


def gaps_s(track: Track, tempo_map: TempoMap) -> np.ndarray:
    ticks = np.array(sorted({note.tick for note in track.notes}), dtype=np.float64)
    return np.diff(tempo_map.seconds_at(ticks))


def test_drum_levels_keep_their_floor_in_seconds_in_a_fast_song():
    tempo_map = TempoMap([TempoEvent(0, 190.0)], [TimeSignatureEvent(0, 4, 4)], resolution=R)
    config = load_drum_config()
    levels = reduce_drums(eighth_groove(16), tempo_map)
    for level in LOWER:
        floor = config.levels[level].min_gap_s
        assert floor > 0
        assert gaps_s(levels[level].track, tempo_map).min() >= floor - 1e-9, level
    assert gaps_s(levels[Difficulty.EASY].track, tempo_map).min() == pytest.approx(60.0 / 190.0), "a whole beat"


def test_the_floor_changes_nothing_at_150_bpm_or_slower():
    config = load_drum_config()
    without = replace(config, levels={level: replace(item, min_gap_s=0.0) for level, item in config.levels.items()})
    for bpm in (90.0, 120.0, 150.0):
        tempo_map = TempoMap([TempoEvent(0, bpm)], [TimeSignatureEvent(0, 4, 4)], resolution=R)
        expert = eighth_groove(16)
        with_floor = reduce_drums(expert, tempo_map, config=config)
        no_floor = reduce_drums(expert, tempo_map, config=without)
        for level in LOWER:
            assert with_floor[level].track.notes == no_floor[level].track.notes, (bpm, level)


def test_the_floor_holds_whatever_the_ticks_allow():
    times = np.array([0.0, 0.1, 0.25, 0.3])
    ticks = np.array([0, 48, 96, 144])
    everything = np.arange(4)
    scores = np.array([1.0, 0.9, 0.8, 0.7])
    protected = np.zeros(4, dtype=bool)
    loose = select_positions(everything, times, scores, protected, 4, np.inf, ticks, 48)
    floored = select_positions(everything, times, scores, protected, 4, np.inf, ticks, 48, floor_s=0.2)
    assert loose.tolist() == [0, 1, 2, 3]
    assert floored.tolist() == [0, 2]


# ---------------------------------------------------------------- sustains in a fast song


def tempo_at(bpm: float) -> TempoMap:
    return TempoMap([TempoEvent(0, bpm)], [TimeSignatureEvent(0, 4, 4)], resolution=R)


def test_a_sustain_lasts_at_least_what_three_quarters_of_a_beat_last_at_150_bpm():
    ticks = np.array([0, R, 2 * R + R // 4, 4 * R])
    ringing = np.full(ticks.size, 5.0)
    assert MIN_SUSTAIN_S == pytest.approx(0.30)
    fast = _sustain_ticks(ticks, ringing, tempo_at(191.0))
    assert fast[0] == 0, "three quarters of a beat at 191 BPM is 0.24 s: no sustain"
    assert fast[1] == R, "a whole beat is 0.31 s: a sustain"
    slow = _sustain_ticks(ticks, ringing, tempo_at(120.0))
    assert slow[0] == 3 * R // 4, "at 120 BPM three quarters of a beat stay a sustain"
    for bpm in (90.0, 120.0, 150.0):
        assert _sustain_ticks(ticks, ringing, tempo_at(bpm))[0] == 3 * R // 4, bpm


def test_a_level_keeps_its_sustain_floor_in_seconds():
    medium = load_config().levels[Difficulty.MEDIUM]
    assert medium.min_sustain_beats == 1.0
    positions = [Position(0, 0.0, (0,), R), Position(4 * R, 2.0, (1,), 0)]
    for bpm, kept in ((191.0, 0), (150.0, R), (120.0, R)):
        track = _build_level(Instrument.GUITAR, Difficulty.MEDIUM, positions, [(0,), (1,)], medium, tempo_at(bpm))
        assert track.notes[0].length == kept, bpm


def test_the_drum_floors_are_what_their_beats_last_at_150_bpm():
    for level, settings in load_drum_config().levels.items():
        assert settings.min_gap_s == pytest.approx(seconds_floor(settings.min_gap_beats)), level
