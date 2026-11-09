"""Bass Expert, songs without a guitar, and the opening where no instrument may have a note."""

import hashlib
import json
import os
import re
from dataclasses import replace
from pathlib import Path

import librosa
import numpy as np
import pytest
from conftest import SR as STEM_SR
from conftest import FakeSeparator, click_times, clicks_at, song_stems, stereo

import chartgen
import chartgen.pipeline
from chartgen.audio.bass_pitch import note_semitones
from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.pitch import analyze_pitches
from chartgen.audio.quiet_notes import QuietNoteLimits, levels_below_median, load_limits
from chartgen.audio.separation import STEM_NAMES
from chartgen.chart.charter import ChartedTrack
from chartgen.chart.difficulty import (
    BASS_CONFIG_PATH,
    HardRuleViolation,
    OrangePitches,
    Position,
    check_hard_rules,
    check_single_notes,
    count_orange_pitches,
    load_config,
    measure_level,
    reduce_track,
    select_positions,
)
from chartgen.chart.fret_mapping import (
    BASS_WEIGHTS_PATH,
    NoteInput,
    is_playable,
    load_weights,
    map_notes,
    single_notes_only,
)
from chartgen.chart.instruments import VOCAL_BLEED_CHECKED, build_tracks_for, settings_for
from chartgen.clonehero.chart_format import DotChartExporter
from chartgen.clonehero.validate import validate_chart_text, validate_song_folder
from chartgen.core.model import Chart, ChartNote, Difficulty, Instrument, SongMetadata, Track
from chartgen.core.timing import TempoEvent, TempoMap
from chartgen.errors import NoPlayableInstrumentError
from chartgen.evaluation.metrics import chart_metrics
from chartgen.evaluation.reference import find_references, load_reference
from chartgen.evaluation.run import _level_table, evaluate_folder, format_report, write_report
from chartgen.pipeline import _check_opening_is_empty, _report_track, build_song, BuildConfig

SR = ANALYSIS_SAMPLERATE
TEMPO = TempoMap([TempoEvent(0, 120.0)])
ALL = frozenset(Instrument)
LINE = (40, 43, 45, 47, 50, 47, 45, 43, 40, 40, 38, 40)
"""Up, down, a repeat and one step below where it began."""


def bass_note(midi: float, seconds: float, sr: int = SR, level: float = 0.5) -> np.ndarray:
    frequency = float(librosa.midi_to_hz(midi))
    t = np.arange(int(seconds * sr)) / sr
    wave = sum(
        (0.5**k) * np.sin(2 * np.pi * frequency * (k + 1) * t) for k in range(3)
    )
    envelope = np.minimum(t / 0.003, 1.0) * np.exp(-t / 0.8)
    return (level * wave * envelope).astype(np.float32)


def bass_line(
    pitches=LINE, start: float = 0.5, spacing: float = 0.5, seconds: float = 8.0, sr: int = SR
) -> tuple[np.ndarray, np.ndarray]:
    """A stem and the time each of its notes starts."""
    signal = np.zeros(int(seconds * sr), dtype=np.float32)
    times = start + spacing * np.arange(len(pitches))
    for time, midi in zip(times, pitches):
        wave = bass_note(midi, spacing, sr)
        index = int(time * sr)
        end = min(index + wave.size, signal.size)
        signal[index:end] += wave[: end - index]
    return signal, times


def next_times(times: np.ndarray, end: float) -> np.ndarray:
    return np.r_[times[1:], end]


def positions(track: Track) -> dict[int, list[int]]:
    found: dict[int, list[int]] = {}
    for note in track.notes:
        found.setdefault(note.tick, []).append(note.lane)
    return found


# ---------------------------------------------------------------- reading the pitch


@pytest.mark.heavy
def test_a_known_line_is_read_note_for_note():
    signal, times = bass_line()
    assert note_semitones(signal, times, next_times(times, 8.0), SR).tolist() == list(LINE)


@pytest.mark.heavy
def test_silence_has_no_pitch():
    silence = np.zeros(4 * SR, dtype=np.float32)
    times = np.array([1.0, 2.0])
    assert np.isnan(note_semitones(silence, times, np.array([2.0, 3.0]), SR)).all()


def test_too_little_audio_has_no_pitch():
    assert np.isnan(note_semitones(np.zeros(100, dtype=np.float32), np.array([0.0]), np.array([1.0]), SR)).all()


def test_no_notes_is_fine():
    assert note_semitones(np.zeros(4 * SR, dtype=np.float32), np.empty(0), np.empty(0), SR).size == 0


# ---------------------------------------------------------------- frets


@pytest.mark.heavy
def test_a_line_that_rises_and_falls_goes_the_right_way():
    signal, times = bass_line()
    track = build_tracks_for(Instrument.BASS, signal, TEMPO, 8.0)[0].track
    found = positions(track)
    lanes = np.array([found[tick][0] for tick in sorted(found)])
    assert lanes.size == len(LINE)
    pitch_steps = np.sign(np.diff(LINE))
    lane_steps = np.sign(np.diff(lanes))
    moving = pitch_steps != 0
    assert np.mean(lane_steps[moving] == pitch_steps[moving]) >= 0.8
    assert not (lane_steps[moving] == -pitch_steps[moving]).any(), "never the wrong way"
    assert (lane_steps[~moving] == 0).all(), "a repeated note stays on its fret"


@pytest.mark.heavy
def test_a_quiet_passage_falls_back_and_stays_playable():
    """No pitch can be read in the middle of this line: the notes must still land somewhere."""
    signal, times = bass_line()
    middle = (times >= 2.0) & (times < 4.0)
    noise = np.random.default_rng(3).standard_normal(signal.size).astype(np.float32)
    for time in times[middle]:
        index = int(time * SR)
        signal[index : index + SR // 2] = noise[index : index + SR // 2] * 0.3 * np.exp(
            -np.arange(SR // 2) / (0.05 * SR)
        )
    charted = build_tracks_for(Instrument.BASS, signal, TEMPO, 8.0)[0]
    pitches = [position.pitch for position in charted.positions]
    assert np.isnan(pitches).any(), "the noise bursts must not be given a pitch"
    assert np.isfinite(pitches).any()
    assert is_playable(
        [position.shape for position in charted.positions],
        [position.time_s for position in charted.positions],
    )


def test_no_pitch_at_all_still_maps_every_note():
    notes = [NoteInput(0.5 * index) for index in range(12)]
    shapes = map_notes(notes, extra_cost=single_notes_only(len(notes)))
    assert len(shapes) == 12
    assert all(len(shape) == 1 for shape in shapes)


# ---------------------------------------------------------------- no chords, ever


@pytest.mark.parametrize("seed", range(12))
def test_no_weights_can_bring_a_chord_back(seed):
    rng = np.random.default_rng(seed)
    weights = replace(
        load_weights(),
        voices=float(rng.uniform(0, 50)),
        contour=float(rng.uniform(0, 10)),
        lane_prior=float(rng.uniform(0, 10)),
        speed=float(rng.uniform(0, 1)),
    )
    # The input insists on chords as loudly as it can.
    notes = [NoteInput(0.2 * i, float(rng.integers(30, 60)), 3) for i in range(40)]
    shapes = map_notes(notes, weights, single_notes_only(len(notes)))
    assert all(len(shape) == 1 for shape in shapes)
    assert is_playable(shapes, [note.time_s for note in notes])


@pytest.mark.heavy
def test_a_stem_the_analysis_hears_as_chords_still_gets_single_notes():
    """Tones over noise, flat enough for the analysis to call it more than one voice."""
    times = 0.5 + 0.5 * np.arange(12)
    signal = np.zeros(8 * SR, dtype=np.float32)
    rng = np.random.default_rng(4)
    for time in times:
        index = int(time * SR)
        wave = sum(bass_note(midi, 0.5, level=0.12) for midi in (40, 44, 47, 52, 56, 59, 63))
        wave = wave + 0.3 * rng.standard_normal(wave.size).astype(np.float32) * np.exp(
            -np.arange(wave.size) / (0.4 * SR)
        )
        signal[index : index + wave.size] += wave.astype(np.float32)
    heard = analyze_pitches(signal, times, next_times(times, 8.0), SR)
    assert any(pitch.voices > 1 for pitch in heard), "or this test proves nothing"
    track = build_tracks_for(Instrument.BASS, signal, TEMPO, 8.0)[0].track
    assert track.notes
    assert all(len(lanes) == 1 for lanes in positions(track).values())


def test_a_chord_on_bass_is_an_error_that_settings_cannot_reach():
    chord = [ChartNote(0, 0), ChartNote(0, 1)]
    with pytest.raises(HardRuleViolation, match="bass/expert has a chord at tick 0"):
        check_single_notes(Track(Instrument.BASS, Difficulty.EXPERT, chord))
    check_single_notes(Track(Instrument.GUITAR, Difficulty.EXPERT, chord))


CHART = "[Song]\n{{\n  Resolution = 192\n}}\n[SyncTrack]\n{{\n  0 = TS 4\n  0 = B 120000\n}}\n{body}"


@pytest.mark.parametrize(
    "section,fails",
    [
        ("ExpertDoubleBass", True),
        ("HardDoubleBass", True),
        ("ExpertSingle", False),
        ("ExpertKeyboard", False),
    ],
)
def test_the_validator_rejects_a_bass_chord_from_the_file_alone(section, fails):
    body = f"[{section}]\n{{\n  0 = N 0 0\n  0 = N 1 0\n}}\n"
    _, report = validate_chart_text(CHART.format(body=body))
    assert any("a chord of 2 notes" in error for error in report.errors) == fails


# ---------------------------------------------------------------- the vocal check


def test_the_vocal_check_stays_off_for_bass_and_on_for_guitar():
    assert Instrument.BASS not in VOCAL_BLEED_CHECKED
    assert Instrument.GUITAR in VOCAL_BLEED_CHECKED


@pytest.mark.heavy
def test_loud_vocals_cost_bass_no_note():
    signal, _ = bass_line()
    vocals = bass_line(tuple(p + 24 for p in LINE))[0] * 2.0
    with_vocals = build_tracks_for(Instrument.BASS, signal, TEMPO, 8.0, vocals=vocals)[0]
    without = build_tracks_for(Instrument.BASS, signal, TEMPO, 8.0)[0]
    assert with_vocals.bleed == ()
    assert with_vocals.track.notes == without.track.notes


# ---------------------------------------------------------------- the lower levels


def bass_positions(count: int = 120, seed: int = 0) -> list[Position]:
    """A bass line of quarter notes at 120 BPM, as a charter would hand it to the reduction."""
    rng = np.random.default_rng(seed)
    pitches = np.cumsum(rng.integers(-5, 6, count)) % 24 + 30
    lanes = rng.integers(0, 5, count)
    return [
        Position(index * 192, TEMPO.seconds_at(float(index * 192)), (int(lanes[index]),), 0, float(rng.random()), float(pitches[index]))
        for index in range(count)
    ]


def expert_of(positions: list[Position]) -> Track:
    return Track(
        Instrument.BASS,
        Difficulty.EXPERT,
        [ChartNote(p.tick, p.shape[0], p.length) for p in positions],
    )


@pytest.mark.heavy
def test_bass_has_four_levels_with_its_own_soft_targets():
    signal, _ = bass_line(tuple(LINE[i % len(LINE)] for i in range(90)), seconds=50.0)
    charted = build_tracks_for(Instrument.BASS, signal, TEMPO, 50.0)
    assert [item.track.difficulty for item in charted] == [
        Difficulty.EXPERT,
        Difficulty.HARD,
        Difficulty.MEDIUM,
        Difficulty.EASY,
    ]
    assert charted[0].chord_limit == 0.0
    names = {target.name for target in charted[0].soft_targets}
    assert {"orange_share", "busiest_lane_share", "auto_hopo_share", "green_lane"} <= names
    targets = {target.name: target for target in charted[1].soft_targets}
    assert targets["orange_share"].low == 0.10, "Hard's guitar table only has an upper limit"
    ticks = [set(positions(item.track)) for item in charted]
    assert ticks[3] <= ticks[2] <= ticks[1] <= ticks[0]
    for item in charted:
        assert all(len(lanes) == 1 for lanes in positions(item.track).values())
    for item in charted[2:]:
        assert max(note.lane for note in item.track.notes) < 4, "no orange on Medium or Easy"


@pytest.mark.parametrize("seed", range(6))
def test_no_settings_can_bring_a_chord_or_medium_orange_back(seed):
    rng = np.random.default_rng(seed)
    weights = replace(
        load_weights(BASS_WEIGHTS_PATH),
        voices=float(rng.uniform(0, 50)),
        contour=float(rng.uniform(0, 10)),
        lane_prior=float(rng.uniform(0, 10)),
    )
    config = load_config(BASS_CONFIG_PATH)
    allowing = {
        level: replace(value, three_note_chords=level is Difficulty.HARD, fidelity=float(rng.uniform(0, 10)))
        for level, value in config.levels.items()
    }
    ordered = bass_positions(seed=seed)
    levels = reduce_track(
        Instrument.BASS, expert_of(ordered), ordered, TEMPO, replace(config, levels=allowing), weights
    )
    for level, result in levels.items():
        assert all(len(lanes) == 1 for lanes in positions(result.track).values())
        if level is not Difficulty.HARD:
            assert max(note.lane for note in result.track.notes) < 4


def test_eighth_notes_stay_on_hard_however_fast_the_song():
    """At 130 BPM an eighth note is 0.23 s, under the 0.25 s that Hard otherwise keeps."""
    fast = TempoMap([TempoEvent(0, 130.0)])
    ticks = np.arange(0, 96 * 40, 96)
    times = fast.seconds_at(ticks.astype(np.float64))
    candidates = np.arange(ticks.size)
    keep_all = np.zeros(ticks.size, dtype=bool)
    scores = np.ones(ticks.size)
    in_seconds = select_positions(candidates, times, scores, keep_all, ticks.size, 0.25)
    in_beats = select_positions(candidates, times, scores, keep_all, ticks.size, 0.25, ticks, 96)
    assert in_seconds.size == ticks.size // 2, "every other eighth note goes"
    assert in_beats.size == ticks.size


def test_sixteenth_notes_stay_apart_however_fast_the_song():
    fast = TempoMap([TempoEvent(0, 130.0)])
    ticks = np.arange(0, 48 * 40, 48)
    times = fast.seconds_at(ticks.astype(np.float64))
    chosen = select_positions(
        np.arange(ticks.size), times, np.ones(ticks.size), np.zeros(ticks.size, dtype=bool), ticks.size, 0.25, ticks, 96
    )
    assert np.diff(ticks[chosen]).min() >= 96


def test_only_hard_on_bass_counts_beats_as_well_as_seconds():
    assert load_config(BASS_CONFIG_PATH).levels[Difficulty.HARD].min_gap_beats == 0.5
    assert load_config(BASS_CONFIG_PATH).levels[Difficulty.MEDIUM].min_gap_beats is None
    assert load_config(BASS_CONFIG_PATH).levels[Difficulty.EASY].min_gap_beats is None
    assert all(level.min_gap_beats is None for level in load_config().levels.values()), "not guitar"


def test_a_chord_on_a_lower_level_of_bass_is_a_hard_rule_problem():
    ordered = bass_positions(8)
    expert = expert_of(ordered)
    easy = Track(Instrument.BASS, Difficulty.EASY, [ChartNote(0, 0)])
    medium = Track(Instrument.BASS, Difficulty.MEDIUM, [ChartNote(0, 0), ChartNote(192, 1)])
    hard = Track(Instrument.BASS, Difficulty.HARD, [ChartNote(0, 0), ChartNote(0, 1), ChartNote(192, 1)])
    problems = check_hard_rules(
        {Difficulty.EXPERT: expert, Difficulty.HARD: hard, Difficulty.MEDIUM: medium, Difficulty.EASY: easy},
        ordered,
        np.zeros(8, dtype=int),
    )
    assert any("hard has a chord at tick 0" in problem for problem in problems)


@pytest.mark.parametrize(
    "old,new,message",
    [
        ("top_lane = 3", "top_lane = 4", "top_lane must be"),
        ("position_ratio = 0.27", "position_ratio = 0.9", "must fall from Hard to Easy"),
        ("max_single_pitch_share = 0.70", "max_single_pitch_share = 1.5", "from 0 to 1"),
    ],
    ids=["medium orange", "the chain", "orange limit"],
)
def test_the_bass_file_cannot_weaken_a_hard_rule(tmp_path, old, new, message):
    text = BASS_CONFIG_PATH.read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "bass_difficulty.toml"
    path.write_text(text.replace(old, new), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_config(path)


# ---------------------------------------------------------------- bass has its own files


GUITAR_CONFIG_SHA256 = {
    "chart/fret_weights.toml": "01a75c2aa14fbb26d55363ff9ebd13b8ed611474bf88f5015591ee3376bab023",
    "chart/difficulty.toml": "30d3bf5456f61e292d1ec66208034751703de23b8f94e1fe378f99250b1f61c8",
    "audio/vocal_bleed.toml": "2dd061dd4341c0d750f203cfd9d3e106d3cf563cae43652b64665f073aca2e33",
}


@pytest.mark.parametrize("name", GUITAR_CONFIG_SHA256)
def test_tuning_bass_leaves_guitars_settings_alone(name):
    data = (Path(chartgen.__file__).parent / name).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(data).hexdigest() == GUITAR_CONFIG_SHA256[name]


def test_each_instrument_reads_its_own_files():
    guitar_config, guitar_weights = settings_for(Instrument.GUITAR)
    bass_config, bass_weights = settings_for(Instrument.BASS)
    assert guitar_weights == load_weights()
    assert bass_weights == load_weights(BASS_WEIGHTS_PATH)
    assert guitar_weights != bass_weights
    assert guitar_config.max_orange_pitch_share is None, "a guitar's notes have no pitch to read"
    assert bass_config.max_orange_pitch_share == 0.70


# ---------------------------------------------------------------- which pitches are orange


def orange_track(ticks_and_lanes: list[tuple[int, int]]) -> Track:
    return Track(Instrument.BASS, Difficulty.EXPERT, [ChartNote(t, lane) for t, lane in ticks_and_lanes])


def test_orange_notes_are_counted_by_pitch():
    positions_ = [
        Position(0, 0.0, (4,), pitch=46.0),
        Position(192, 0.5, (4,), pitch=46.0),
        Position(384, 1.0, (4,), pitch=39.0),
        Position(576, 1.5, (4,), pitch=float("nan")),
        Position(768, 2.0, (0,), pitch=46.0),
    ]
    track = orange_track([(0, 4), (192, 4), (384, 4), (576, 4), (768, 0)])
    orange = count_orange_pitches(track, positions_, 0.70)
    assert orange.counts == (("A#2", 2), ("D#2", 1))
    assert orange.unknown == 1
    assert orange.notes == 3
    assert orange.top_share == pytest.approx(2 / 3)
    assert not orange.is_one_pitch
    report = orange.as_dict()
    assert report["pitches"] == {"A#2": 2, "D#2": 1}
    assert report["pitch_unknown"] == 1
    assert report["one_pitch"] is False


def test_no_orange_notes_are_no_warning():
    orange = count_orange_pitches(orange_track([(0, 1)]), [Position(0, 0.0, (1,), pitch=40.0)], 0.70)
    assert orange.notes == 0
    assert orange.top_share == 0.0
    assert not orange.is_one_pitch


@pytest.mark.parametrize(
    "counts,warns",
    [((("A#1", 71), ("C2", 29)), True), ((("A#1", 70), ("C2", 30)), False)],
    ids=["over the limit", "at the limit"],
)
def test_one_pitch_above_the_limit_warns_without_failing(counts, warns):
    item = ChartedTrack(
        Track(Instrument.BASS, Difficulty.EXPERT, [ChartNote(0, 4)]),
        1,
        orange_pitches=OrangePitches(counts, 0, 0.70),
    )
    warnings: list[str] = []
    _report_track(Instrument.BASS, item, warnings)
    assert any("orange is one pitch: A#1 is 71%" in warning for warning in warnings) == warns


def test_evaluate_shows_the_orange_pitches_and_says_when_they_are_one():
    orange = OrangePitches((("A#1", 9), ("C2", 1)), 0, 0.70).as_dict()
    lines = _level_table("Bass", {"expert": {"orange_pitches": orange}})
    assert "expert orange notes by pitch: A#1 9, C2 1; orange is one pitch" in lines
    empty = OrangePitches(()).as_dict()
    lines = _level_table("Bass", {"easy": {"orange_pitches": empty}})
    assert not any("orange notes by pitch" in line for line in lines)


def test_hand_travel_and_the_busiest_lane_are_measured():
    measures = measure_level(
        [(0, (0,)), (192, (2,)), (384, (2,)), (576, (1,))],
        [False] * 4,
        [0.0, 0.5, 1.0, 1.5],
        192,
        4,
    )
    assert measures.hand_travel == pytest.approx(1.0)
    assert measures.busiest_lane_share == 0.5


# ---------------------------------------------------------------- quiet notes


def quiet_line() -> tuple[np.ndarray, np.ndarray]:
    """A line in which the note at index 5 is about 20 dB under the others, after a short silence.
    Straight after a loud note the onset detector would take it for that note's end, and no rule
    would get to see it."""
    signal, times = bass_line()
    first = int(times[5] * SR)
    last = int(times[6] * SR)
    signal[first - SR // 4 : first] = 0.0
    signal[first:last] *= 10 ** (-20 / 20)
    return signal, times


def test_a_note_is_measured_against_the_median_note():
    signal, times = quiet_line()
    below = levels_below_median(signal, times, next_times(times, 8.0), SR)
    assert below[5] == pytest.approx(20, abs=4)
    assert np.delete(np.abs(below), 5).max() < 4


def test_no_notes_is_nothing_below_the_median():
    assert levels_below_median(np.zeros(SR, dtype=np.float32), np.empty(0), np.empty(0), SR).size == 0


@pytest.mark.parametrize(
    "text,message",
    [
        ("enabled = true", "expected keys"),
        ("enabled = true\nbelow_median_db = 18\nextra = 1", "expected keys"),
        ('enabled = "yes"\nbelow_median_db = 18', "true or false"),
        ("enabled = true\nbelow_median_db = 0", "positive"),
    ],
)
def test_broken_limits_are_refused(tmp_path, text, message):
    path = tmp_path / "limits.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_limits(path)


@pytest.mark.heavy
def test_the_rule_only_reports_while_it_is_off():
    signal, times = quiet_line()
    limits = QuietNoteLimits(False, 15.0)
    charted = build_tracks_for(Instrument.BASS, signal, TEMPO, 8.0, quiet_limits=limits)[0]
    assert [note.removed for note in charted.quiet] == [False]
    assert charted.quiet[0].time_s == pytest.approx(times[5], abs=0.03)
    assert len(positions(charted.track)) == len(LINE)


@pytest.mark.heavy
def test_the_rule_removes_the_note_while_it_is_on():
    signal, times = quiet_line()
    limits = QuietNoteLimits(True, 15.0)
    charted = build_tracks_for(Instrument.BASS, signal, TEMPO, 8.0, quiet_limits=limits)[0]
    assert [note.removed for note in charted.quiet] == [True]
    placed = TEMPO.seconds_at(np.array(sorted(positions(charted.track)), dtype=np.float64))
    assert len(placed) == len(LINE) - 1
    assert np.abs(placed - times[5]).min() > 0.2


def test_guitar_is_not_checked_for_quiet_notes():
    stem = clicks_at(click_times(120, 20, 0.5), 20, SR)
    charted = build_tracks_for(Instrument.GUITAR, stem, TEMPO, 20.0, quiet_limits=QuietNoteLimits(True, 0.1))[0]
    assert charted.quiet_limits is None
    assert charted.quiet == ()


def test_the_rule_is_off_as_the_owner_decided():
    assert load_limits().enabled is False


# ---------------------------------------------------------------- the opening


@pytest.mark.heavy
@pytest.mark.parametrize("instrument", [Instrument.GUITAR, Instrument.BASS])
def test_no_level_of_any_instrument_has_a_note_in_the_opening(instrument):
    times = click_times(120, 20, 0.5)
    stem = clicks_at(times, 20, SR)
    limit = 10.0
    charted = build_tracks_for(instrument, stem, TEMPO, 20.0, not_before_s=limit)
    assert charted
    for item in charted:
        placed = TEMPO.seconds_at(np.array([note.tick for note in item.track.notes], dtype=float))
        assert placed.min() >= limit
    expert = sorted(positions(charted[0].track))
    assert TEMPO.seconds_at(float(expert[0])) == pytest.approx(10.0, abs=0.5), "the song stays"


def test_snapping_cannot_carry_a_note_over_the_line():
    """The note at 10.012 s starts after the line, but the sixteenth it snaps to lies before it."""
    limit = 10.005
    times = np.r_[np.arange(0.5, 10.0, 0.5), 10.012, np.arange(10.5, 14.0, 0.5)]
    stem = clicks_at(times, 14, SR)
    track = build_tracks_for(Instrument.GUITAR, stem, TEMPO, 14.0, not_before_s=limit)[0].track
    first = min(TEMPO.seconds_at(float(note.tick)) for note in track.notes)
    assert first == pytest.approx(10.5, abs=0.02)


def test_a_song_whose_notes_all_lie_in_the_opening_gives_nothing():
    stem = clicks_at(click_times(120, 8, 0.5), 20, SR)
    assert build_tracks_for(Instrument.GUITAR, stem, TEMPO, 20.0, not_before_s=10.0) == []


class Opening:
    tempo_map = TEMPO
    lead_in_end_s = 10.0


@pytest.mark.parametrize("instrument", list(Instrument))
def test_any_instrument_that_breaks_the_rule_stops_the_build(instrument):
    """Whichever generator it comes from: this also holds for the ones not written yet."""
    inside = Track(instrument, Difficulty.EASY, [ChartNote(1920, 0)])
    with pytest.raises(HardRuleViolation, match="in the opening"):
        _check_opening_is_empty([inside], Opening)
    _check_opening_is_empty([Track(instrument, Difficulty.EASY, [ChartNote(3840, 0)])], Opening)


def config(song_file, tmp_path, instruments=ALL) -> BuildConfig:
    return BuildConfig(
        input_path=song_file,
        metadata=SongMetadata("Şarkı", "Sanatçı"),
        instruments=instruments,
        output_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
    )


def stems_without_guitar() -> dict[str, np.ndarray]:
    stems = song_stems()
    stems["guitar"] = stems["guitar"] * 0.0
    pitches = tuple(LINE[index % len(LINE)] for index in range(38))
    stems["bass"] = stereo(bass_line(pitches, seconds=20.0, sr=STEM_SR)[0])
    return stems


def with_an_opening(monkeypatch, end_s: float) -> None:
    real = chartgen.pipeline.estimate_tempo_map

    def patched(*args, **kwargs):
        return replace(real(*args, **kwargs), lead_in_end_s=end_s, lead_in_on_grid=0.3)

    monkeypatch.setattr(chartgen.pipeline, "estimate_tempo_map", patched)


@pytest.mark.heavy
def test_the_opening_gets_a_section_mark_and_no_notes(song_file, tmp_path, monkeypatch):
    with_an_opening(monkeypatch, 5.0)
    result = build_song(config(song_file, tmp_path), FakeSeparator(stems_without_guitar()))
    text = (result.folder / "notes.chart").read_text(encoding="utf-8-sig")
    events = re.search(r"\[Events\]\s*\{(.*?)\}", text, flags=re.S).group(1)
    marks = re.findall(r'(\d+) = E "section (\w+)"', events)
    assert [name for _, name in marks] == ["Intro", "Song"]
    assert marks[0][0] == "0"
    assert validate_song_folder(result.folder).ok
    bass = re.search(r"\[ExpertDoubleBass\]\s*\{(.*?)\}", text, flags=re.S).group(1)
    ticks = [int(tick) for tick in re.findall(r"(\d+) = N", bass)]
    assert ticks
    tempo = json.loads((result.folder / "analysis.json").read_text(encoding="utf-8"))["tempo"]
    written = TempoMap([TempoEvent(event["tick"], event["bpm"]) for event in tempo["tempo_events"]])
    assert written.seconds_at(float(min(ticks))) >= 5.0
    assert written.seconds_at(float(marks[1][0])) == pytest.approx(5.0, abs=0.1)
    assert int(marks[1][0]) % 48 == 0, "the song's mark sits on a sixteenth"


@pytest.mark.heavy
def test_a_song_without_an_opening_gets_no_section_mark(song_file, tmp_path):
    result = build_song(config(song_file, tmp_path), FakeSeparator(song_stems()))
    text = (result.folder / "notes.chart").read_text(encoding="utf-8-sig")
    assert re.search(r"\[Events\]\s*\{\s*\}", text)


@pytest.mark.heavy
def test_the_validator_catches_a_note_in_the_opening_from_the_files(song_file, tmp_path):
    result = build_song(config(song_file, tmp_path), FakeSeparator(song_stems()))
    assert validate_song_folder(result.folder).ok
    path = result.folder / "analysis.json"
    analysis = json.loads(path.read_text(encoding="utf-8"))
    analysis["tempo"]["unfit_lead_in"] = {"end_s": 10.0, "onsets_on_grid": 0.3}
    path.write_text(json.dumps(analysis), encoding="utf-8")
    report = validate_song_folder(result.folder)
    assert any("a note in the opening" in error for error in report.errors)


# ---------------------------------------------------------------- without a guitar


@pytest.mark.heavy
def test_a_song_without_a_guitar_builds_on_its_bass(song_file, tmp_path):
    result = build_song(config(song_file, tmp_path), FakeSeparator(stems_without_guitar()))
    assert validate_song_folder(result.folder).ok
    text = (result.folder / "notes.chart").read_text(encoding="utf-8-sig")
    for level in ("Expert", "Hard", "Medium", "Easy"):
        assert f"[{level}DoubleBass]" in text
    assert "Single]" not in text, "no guitar section of any level"
    lines = (result.folder / "song.ini").read_text(encoding="utf-8").splitlines()[1:]
    ini = dict(line.split(" = ", 1) for line in lines)
    assert ini["diff_guitar"] == "-1"
    assert int(ini["diff_bass"]) >= 0
    assert not (result.folder / "guitar.ogg").exists()
    assert (result.folder / "bass.ogg").exists()
    assert "guitar" in result.analysis["audio_files"]["song.ogg"]["stems"], "its audio is not lost"
    assert set(result.analysis["charts"]) == {"bass"}
    assert "chord_limit" not in result.analysis["charts"]["bass"]["expert"]
    assert "orange_pitches" in result.analysis["charts"]["bass"]["expert"]
    quiet = result.analysis["charts"]["bass"]["expert"]["quiet_notes"]
    assert quiet["enabled"] is False
    assert quiet["below_median_db"] == load_limits().below_median_db


@pytest.mark.heavy
def test_no_instrument_to_play_stops_with_an_explanation_and_no_folder(song_file, tmp_path):
    stems = song_stems()
    stems["guitar"] = stems["guitar"] * 0.0
    stems["bass"] = stems["bass"] * 0.0
    with pytest.raises(NoPlayableInstrumentError, match="unplayable"):
        build_song(config(song_file, tmp_path), FakeSeparator(stems))
    out = tmp_path / "out"
    assert not out.exists() or list(out.iterdir()) == []


# ---------------------------------------------------------------- against the human


def bass_reference(folder: Path, with_bass: bool = True) -> tuple[Path, np.ndarray]:
    """A reference folder whose bass plays the line above, and a stem that plays the same."""
    from chartgen.clonehero.package import encode_ogg

    folder.mkdir(parents=True)
    pitches = tuple(LINE[index % len(LINE)] for index in range(38))
    stem, times = bass_line(pitches, seconds=20.0, sr=STEM_SR)
    ticks = np.round(times * 2 * 192).astype(int)
    lanes = [[0, 1, 2, 3, 4, 3, 2, 1][index % 8] for index in range(len(ticks))]
    notes = "\n".join(f"  {tick} = N {lane} 0" for tick, lane in zip(ticks, lanes))
    bass = f"[ExpertDoubleBass]\n{{\n{notes}\n}}\n" if with_bass else ""
    (folder / "notes.chart").write_text(
        "[Song]\n{\n  Resolution = 192\n}\n[SyncTrack]\n{\n  0 = TS 4\n  0 = B 120000\n}\n"
        f"[ExpertSingle]\n{{\n{notes}\n}}\n{bass}",
        encoding="utf-8",
    )
    encode_ogg(stereo(clicks_at(times, 20, STEM_SR)), STEM_SR, folder / "guitar.ogg")
    return folder, stem


def bass_separator(stem: np.ndarray, times: np.ndarray) -> FakeSeparator:
    silence = np.zeros((stem.size, 2), dtype=np.float32)
    stems = {name: silence.copy() for name in STEM_NAMES}
    stems["guitar"] = stereo(clicks_at(times, 20, STEM_SR))
    stems["bass"] = stereo(stem)
    return FakeSeparator(stems)


@pytest.mark.heavy
def test_evaluate_reports_bass_apart_from_guitar(tmp_path):
    folder, stem = bass_reference(tmp_path / "train" / "song")
    times = 0.5 + 0.5 * np.arange(38)
    assert set(load_reference(folder).bass_levels) == {Difficulty.EXPERT}
    report = evaluate_folder(tmp_path, bass_separator(stem, times), tmp_path / "cache")
    bass = report.songs["song"]["bass"]["expert"]
    assert bass["match"]["note_f1"] >= 0.9
    assert bass["human"]["chord_share"] == 0.0
    assert "levels" in report.songs["song"], "guitar is still there, on its own"
    text = format_report(report)
    assert "Bass of song" in text
    assert "dir moves" in text
    output = tmp_path / "report.json"
    write_report(report, output)
    assert "bass_average_by_difficulty" in json.loads(output.read_text(encoding="utf-8"))["train"]


@pytest.mark.heavy
def test_a_reference_without_bass_keeps_its_report(tmp_path):
    folder, stem = bass_reference(tmp_path / "train" / "song", with_bass=False)
    times = 0.5 + 0.5 * np.arange(38)
    assert load_reference(folder).bass_levels == {}
    report = evaluate_folder(tmp_path, bass_separator(stem, times), tmp_path / "cache")
    assert "bass" not in report.songs["song"]
    assert "Bass of" not in format_report(report)
    output = tmp_path / "report.json"
    write_report(report, output)
    assert set(json.loads(output.read_text(encoding="utf-8"))["train"]) == {
        "songs",
        "average",
        "average_by_difficulty",
    }


# ---------------------------------------------------------------- real songs


def music_folder() -> Path:
    folder = os.environ.get("CHARTGEN_MUSIC_DIR")
    if not folder:
        pytest.skip("CHARTGEN_MUSIC_DIR is not set")
    return Path(folder)


def real_song(path: Path):
    from chartgen.audio.io import analysis_mono, load_audio
    from chartgen.audio.separation import DemucsSeparator, separate_with_cache
    from chartgen.audio.tempo import estimate_tempo_map

    if not path.is_file():
        pytest.skip(f"{path} is not here")
    audio = load_audio(path)
    stems = separate_with_cache(path, audio, DemucsSeparator(), Path(".cache/stems"))
    pitched = np.sum([stems.stems[name] for name in ("bass", "guitar", "piano", "other")], axis=0)
    tempo = estimate_tempo_map(
        analysis_mono(audio.samples, audio.samplerate),
        drums=analysis_mono(stems.stems["drums"], stems.samplerate),
        harmonic=analysis_mono(pitched, stems.samplerate),
        bass=analysis_mono(stems.stems["bass"], stems.samplerate),
    )
    return stems, tempo


@pytest.mark.slow
@pytest.mark.parametrize(
    "file_name,lead_in",
    [("DanzaKuduro.mp3", 36.93), ("TocaToca.mp3", 0.0)],
)
def test_real_songs_without_a_guitar_build(tmp_path, file_name, lead_in):
    from chartgen.audio.separation import DemucsSeparator

    path = music_folder() / file_name
    if not path.is_file():
        pytest.skip(f"{path} is not here")
    result = build_song(
        BuildConfig(
            input_path=path,
            metadata=SongMetadata(file_name, "Test"),
            instruments=ALL,
            output_dir=tmp_path / "out",
            cache_dir=Path(".cache/stems"),
        ),
        DemucsSeparator(),
    )
    report = validate_song_folder(result.folder)
    assert report.ok, report.errors
    text = (result.folder / "notes.chart").read_text(encoding="utf-8-sig")
    assert "Single]" not in text
    assert "Keyboard]" not in text
    for level in ("Expert", "Hard", "Medium", "Easy"):
        assert f"[{level}DoubleBass]" in text
    assert "guitar" in result.analysis["audio_files"]["song.ogg"]["stems"]
    assert "piano" in result.analysis["audio_files"]["song.ogg"]["stems"]
    assert set(result.analysis["song_ini"]["difficulty"]) == {"bass"}
    for level in ("expert", "hard", "medium", "easy"):
        assert result.analysis["charts"]["bass"][level]["chord_positions"] == 0
        assert "orange_pitches" in result.analysis["charts"]["bass"][level]
    assert ('section Intro' in text) == (lead_in > 0)
    assert ('section Song' in text) == (lead_in > 0)
    opening = result.analysis["tempo"]["unfit_lead_in"]
    assert (opening["end_s"] if opening else 0.0) == pytest.approx(lead_in, abs=0.5)
    if opening:
        assert opening["song_start_s"] == pytest.approx(37.1, abs=0.05)


TOCA_NOTES_THE_OWNER_HEARD = (36.02, 47.45, 54.12, 56.02, 58.88, 61.74, 63.64, 67.01, 108.40, 112.21, 114.12)
"""Checked by ear: real bass notes, which no rule may remove."""


@pytest.mark.slow
def test_the_configured_limit_keeps_every_toca_note_the_owner_heard():
    """One of the owner's two conditions for turning the rule on. The other is the test below."""
    from chartgen.audio.io import analysis_mono

    stems, tempo = real_song(music_folder() / "TocaToca.mp3")
    limits = replace(load_limits(), enabled=True)
    charted = build_tracks_for(
        Instrument.BASS,
        analysis_mono(stems.stems["bass"], stems.samplerate),
        tempo.tempo_map,
        stems.duration_s,
        quiet_limits=limits,
    )[0]
    removed = np.array([note.time_s for note in charted.quiet])
    assert removed.size, "or this test proves nothing"
    assert min(abs(removed - heard).min() for heard in TOCA_NOTES_THE_OWNER_HEARD) > 0.03


@pytest.mark.slow
def test_the_configured_limit_costs_the_human_bass_chart_at_most_0_005():
    from chartgen.audio.io import analysis_mono
    from chartgen.audio.separation import DemucsSeparator, separate_with_cache
    from chartgen.audio.tempo import estimate_tempo_map

    folder = os.environ.get("CHARTGEN_REFERENCE_DIR")
    if not folder:
        pytest.skip("CHARTGEN_REFERENCE_DIR is not set")
    path = find_references(Path(folder) / "train")[0]
    song = load_reference(path)
    stems = separate_with_cache(song.source, song.audio, DemucsSeparator(), Path(".cache/stems"))
    tempo = estimate_tempo_map(analysis_mono(song.audio.samples, song.audio.samplerate))
    bass = analysis_mono(stems.stems["bass"], stems.samplerate)

    def note_f1(enabled: bool) -> float:
        limits = replace(load_limits(), enabled=enabled)
        track = build_tracks_for(
            Instrument.BASS, bass, tempo.tempo_map, stems.duration_s, quiet_limits=limits
        )[0].track
        return chart_metrics(track, tempo.tempo_map, song.bass_levels[Difficulty.EXPERT])["note_f1"]

    assert note_f1(True) >= note_f1(False) - 0.005


@pytest.mark.slow
@pytest.mark.parametrize(
    "path_from_music,sha256",
    [
        ("LastResort.wav", "f0c93106e922560ef6b1db3a7ec04bfdb1db17968f6dac409898314e94a3d84f"),
        ("../cloneH/audio.mp3", "fa099c6ccb0a29634dacba71a6556ef99785b821ea118f7fdc70946b8b9f6deb"),
    ],
)
def test_the_guitar_the_owner_played_stays_byte_for_byte(path_from_music, sha256):
    """The hash covers [SyncTrack] and all four guitar levels, as they were when played."""
    from chartgen.audio.io import analysis_mono

    stems, tempo = real_song(music_folder() / path_from_music)
    stem = analysis_mono(stems.stems["guitar"], stems.samplerate)
    vocals = analysis_mono(stems.stems["vocals"], stems.samplerate)
    charted = build_tracks_for(
        Instrument.GUITAR, stem, tempo.tempo_map, stems.duration_s, vocals, tempo.lead_in_end_s
    )
    chart = Chart(SongMetadata("T", "A"), tempo.tempo_map, [item.track for item in charted])
    text = DotChartExporter().render(chart).decode("utf-8-sig")
    assert hashlib.sha256(text[text.index("[SyncTrack]") :].encode("utf-8")).hexdigest() == sha256
