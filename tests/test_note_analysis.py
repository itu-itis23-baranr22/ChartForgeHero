"""Pitch, chords, sustains and meter, on synthetic audio with known answers."""

import numpy as np
import pytest
from conftest import sine

from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.meter import MIN_CONFIDENCE, detect_meter
from chartgen.audio.pitch import NotePitch, analyze_pitches, contour_with_repeats
from chartgen.audio.sustain import note_durations
from chartgen.audio.tempo import estimate_tempo_map
from chartgen.chart.charter import MIN_SUSTAIN_BEATS, SUSTAIN_GAP_BEATS, build_expert_track
from chartgen.chart.fret_mapping import is_playable
from chartgen.core.model import Instrument
from chartgen.core.timing import TempoEvent, TempoMap

SR = ANALYSIS_SAMPLERATE


def midi_hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def plucked(midi: float, seconds: float, decay: float = 0.6, partials: int = 10) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    freq = midi_hz(midi)
    wave = sum(
        np.sin(2 * np.pi * freq * k * t) / k for k in range(1, partials + 1) if freq * k < SR / 2
    )
    return (0.4 * wave * np.exp(-t / decay) * np.minimum(1, t / 0.002)).astype(np.float32)


def tone(freq, seconds, amp=0.5):
    """A sine with short fades. A wave cut off dead would be a click that no real instrument
    makes, and would rightly count as a note of its own."""
    wave = sine(freq, seconds, SR, amp=amp)
    fade = min(int(0.01 * SR), len(wave) // 2)
    ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
    wave[:fade] *= ramp
    wave[-fade:] *= ramp[::-1]
    return wave


def place(events, seconds):
    """Mix (time, wave) events into one signal."""
    out = np.zeros(int(seconds * SR), dtype=np.float32)
    for time, wave in events:
        start = int(time * SR)
        end = min(start + len(wave), len(out))
        out[start:end] += wave[: end - start]
    return out


def sequence(midis, spacing=0.5, start=0.5, chord=None):
    events = []
    for index, midi in enumerate(midis):
        wave = plucked(midi, spacing)
        if chord:
            wave = sum(plucked(midi + interval, spacing) for interval in chord) + wave
        events.append((start + index * spacing, wave))
    times = np.array([time for time, _ in events])
    seconds = times[-1] + spacing + 0.5
    return place(events, seconds), times


def analyze(signal, times):
    next_times = np.r_[times[1:], len(signal) / SR]
    return analyze_pitches(signal, times, next_times, SR)


# ---------------------------------------------------------------- pitch contour


def test_contour_rises_and_falls_with_the_melody():
    up, times = sequence(range(40, 64, 3))
    values = [p.contour for p in analyze(up, times)]
    assert all(b > a for a, b in zip(values, values[1:]))

    down, times = sequence(range(64, 40, -3))
    values = [p.contour for p in analyze(down, times)]
    assert all(b < a for a, b in zip(values, values[1:]))


def test_contour_distance_grows_with_the_interval():
    signal, times = sequence([45, 47, 45, 57])
    values = [p.contour for p in analyze(signal, times)]
    assert abs(values[3] - values[2]) > abs(values[1] - values[0])


def test_repeated_note_is_recognised_and_different_note_is_not():
    signal, times = sequence([50, 50, 50, 57])
    pitches = analyze(signal, times)
    assert pitches[1].similarity >= 0.95
    assert pitches[2].similarity >= 0.95
    assert pitches[3].similarity < pitches[2].similarity
    contour = contour_with_repeats(pitches)
    assert contour[0] == contour[1] == contour[2]
    assert contour[3] != contour[2]


def test_silence_gives_no_pitch_and_does_not_fail():
    times = np.array([0.5, 1.0])
    pitches = analyze_pitches(np.zeros(SR * 2, dtype=np.float32), times, np.array([1.0, 2.0]), SR)
    assert not any(p.is_known for p in pitches)


def test_no_notes_and_short_audio_do_not_fail():
    assert analyze_pitches(np.zeros(SR, dtype=np.float32), np.empty(0), np.empty(0), SR) == []
    short = analyze_pitches(np.zeros(10, dtype=np.float32), np.array([0.0]), np.array([1.0]), SR)
    assert len(short) == 1 and not short[0].is_known


def test_contour_with_repeats_keeps_unknown_notes_unknown():
    pitches = [
        NotePitch(10.0, 0.0, 0.2, 1),
        NotePitch(float("nan"), 0.0, 0.0, 1),
        NotePitch(12.0, 0.99, 0.2, 1),
    ]
    values = contour_with_repeats(pitches)
    assert values[0] == 10.0 and np.isnan(values[1]) and values[2] == 12.0


# ---------------------------------------------------------------- chords


def test_chords_are_flatter_than_single_notes():
    singles, times = sequence([45, 48, 52, 55])
    chords, chord_times = sequence([45, 48, 52, 55], chord=(4, 7, 11))
    single_flatness = np.mean([p.flatness for p in analyze(singles, times)])
    chord_flatness = np.mean([p.flatness for p in analyze(chords, chord_times)])
    assert chord_flatness > single_flatness


def test_clean_single_notes_count_as_one_voice():
    signal, times = sequence([45, 48, 52, 55], chord=None)
    assert all(p.voices == 1 for p in analyze(signal, times))


def test_chord_limit_follows_a_distorted_song():
    """Regression test: distortion raised every note's flatness above the fixed limit, so a
    real song came out as 94% chords."""
    rng = np.random.default_rng(4)
    events = []
    for index in range(40):
        wave = plucked(45 + (index % 5) * 2, 0.4)
        noise = (0.5 * rng.standard_normal(wave.size) * (np.abs(wave) + 0.1)).astype(np.float32)
        events.append((0.5 + index * 0.4, wave + noise))
    times = np.array([time for time, _ in events])
    signal = place(events, float(times[-1] + 1.0))
    pitches = analyze(signal, times)
    assert np.median([p.flatness for p in pitches]) > 0.5, "the test sound must be this flat"
    assert np.mean([p.voices > 1 for p in pitches]) <= 0.55


# ---------------------------------------------------------------- sustains


def test_long_note_rings_for_about_its_length():
    signal = place([(1.0, tone(330, 2.0))], 5.0)
    durations = note_durations(signal, np.array([1.0]), np.array([5.0]), SR)
    assert durations[0] == pytest.approx(2.0, abs=0.1)


def test_short_note_ends_early():
    signal = place([(1.0, tone(330, 0.1))], 5.0)
    assert note_durations(signal, np.array([1.0]), np.array([5.0]), SR)[0] < 0.25


def test_next_note_cuts_a_note_off():
    signal = place([(1.0, tone(330, 3.0))], 5.0)
    assert note_durations(signal, np.array([1.0]), np.array([2.0]), SR)[0] == pytest.approx(1.0, abs=0.03)


def test_natural_decay_ends_the_note():
    signal = place([(1.0, plucked(50, 3.0, decay=0.2))], 5.0)
    duration = note_durations(signal, np.array([1.0]), np.array([5.0]), SR)[0]
    assert 0.1 < duration < 0.8


def test_silence_and_empty_input_have_no_duration():
    assert note_durations(np.zeros(SR, dtype=np.float32), np.array([0.1]), np.array([0.9]), SR)[0] < 0.9
    assert note_durations(np.zeros(SR, dtype=np.float32), np.empty(0), np.empty(0), SR).size == 0
    assert note_durations(np.zeros(5, dtype=np.float32), np.array([0.0]), np.array([1.0]), SR)[0] == 0


TEMPO = TempoMap([TempoEvent(0, 120.0)])


def long_and_short_track():
    """At 120 BPM, one beat is 0.5 s. Long notes ring for 1.5 s, short ones for 0.1 s."""
    events = []
    for index in range(8):
        length = 1.5 if index % 2 == 0 else 0.1
        events.append((1.0 + index * 2.0, tone(330 + 40 * index, length)))
    signal = place(events, 20.0)
    return build_expert_track(Instrument.GUITAR, signal, TEMPO, 20.0).track


def test_track_sustains_long_notes_only():
    positions = {}
    for note in long_and_short_track().notes:
        positions[note.tick] = max(positions.get(note.tick, 0), note.length)
    ticks = sorted(positions)
    assert len(ticks) == 8
    for index, tick in enumerate(ticks):
        if index % 2 == 0:
            assert positions[tick] == pytest.approx(3 * 192, abs=96)
        else:
            assert positions[tick] == 0


def test_sustains_stay_on_the_grid_and_never_reach_the_next_note():
    signal = place([(1.0 + i * 0.75, tone(300 + 30 * i, 3.0, amp=0.4)) for i in range(16)], 20.0)
    track = build_expert_track(Instrument.GUITAR, signal, TEMPO, 20.0).track
    by_tick = {}
    for note in track.notes:
        by_tick[note.tick] = max(by_tick.get(note.tick, 0), note.length)
    ticks = sorted(by_tick)
    assert any(by_tick[tick] > 0 for tick in ticks)
    for tick, following in zip(ticks, ticks[1:]):
        assert tick + by_tick[tick] <= following - SUSTAIN_GAP_BEATS * 192
    for length in by_tick.values():
        assert length == 0 or (length % 48 == 0 and length >= MIN_SUSTAIN_BEATS * 192)


def test_built_track_obeys_the_hard_rules():
    signal, _ = sequence([40, 44, 47, 52, 47, 44, 40, 52] * 4, spacing=0.25)
    track = build_expert_track(Instrument.GUITAR, signal, TEMPO, len(signal) / SR).track
    by_tick: dict[int, list[int]] = {}
    for note in track.notes:
        by_tick.setdefault(note.tick, []).append(note.lane)
    ticks = sorted(by_tick)
    assert len(ticks) > 20
    shapes = [tuple(sorted(by_tick[tick])) for tick in ticks]
    times = [TEMPO.seconds_at(float(tick)) for tick in ticks]
    assert is_playable(shapes, times)


# ---------------------------------------------------------------- meter


def groove(beats_per_bar, bpm, bars, pickup=0, start=0.3):
    """Kick on the first beat, snares on the others, a new bass note and chord each bar."""
    rng = np.random.default_rng(21)
    beat = 60.0 / bpm
    first = start + pickup * beat
    seconds = first + bars * beats_per_bar * beat + 1
    t = np.arange(int(0.2 * SR)) / SR
    kick = (0.9 * np.sin(2 * np.pi * 60 * t) * np.exp(-t / 0.05)).astype(np.float32)
    snare = (0.5 * rng.standard_normal(len(t)) * np.exp(-t / 0.05)).astype(np.float32)
    events = []
    roots = [110.0, 146.8, 123.5, 98.0]
    for index in range(pickup + bars * beats_per_bar):
        position = (index - pickup) % beats_per_bar
        events.append((start + index * beat, kick if position == 0 else snare))
    bar_seconds = beats_per_bar * beat
    for bar in range(bars):
        root = roots[bar % len(roots)]
        span = np.arange(int(bar_seconds * SR)) / SR
        harmony = sum(0.1 * np.sin(2 * np.pi * root * ratio * span) for ratio in (1.0, 1.26, 1.5, 2.0))
        events.append((first + bar * bar_seconds, harmony.astype(np.float32)))
    return place(events, seconds), first, bar_seconds


def downbeat_error(found, truth, bar):
    difference = (found - truth) % bar
    return min(difference, bar - difference)


@pytest.mark.parametrize("pickup", [0, 1, 3])
def test_four_four_is_detected_with_its_downbeat(pickup):
    signal, first, bar = groove(4, 110.0, 40, pickup)
    analysis = estimate_tempo_map(signal, SR)
    assert analysis.meter.label == "4/4"
    assert downbeat_error(analysis.first_downbeat_s, first, bar) < 0.03
    assert analysis.meter.confidence >= MIN_CONFIDENCE
    assert not analysis.meter.low_confidence


@pytest.mark.parametrize("pickup", [0, 1, 2])
def test_three_four_is_detected_with_its_downbeat(pickup):
    signal, first, bar = groove(3, 110.0, 50, pickup)
    analysis = estimate_tempo_map(signal, SR)
    assert analysis.meter.label == "3/4"
    assert downbeat_error(analysis.first_downbeat_s, first, bar) < 0.03


def six_eight(pulse_bpm, bars, start=0.3):
    """Two groups of three eighth notes: kick on the first eighth, snare on the fourth."""
    rng = np.random.default_rng(5)
    eighth = 60.0 / pulse_bpm / 3
    t = np.arange(int(0.15 * SR)) / SR
    kick = (0.9 * np.sin(2 * np.pi * 60 * t) * np.exp(-t / 0.05)).astype(np.float32)
    snare = (0.7 * rng.standard_normal(len(t)) * np.exp(-t / 0.05)).astype(np.float32)
    hat = (0.2 * rng.standard_normal(len(t)) * np.exp(-t / 0.006)).astype(np.float32)
    events = []
    for bar in range(bars):
        at = start + bar * 6 * eighth
        events.append((at, kick))
        events.append((at + 3 * eighth, snare))
        events.extend((at + index * eighth, hat) for index in range(6))
        span = np.arange(int(6 * eighth * SR)) / SR
        root = (110.0, 146.8)[bar % 2]
        events.append((at, (0.15 * np.sin(2 * np.pi * root * span)).astype(np.float32)))
    return place(events, start + bars * 6 * eighth + 1)


def test_six_eight_is_detected_with_its_downbeat():
    analysis = estimate_tempo_map(six_eight(70.0, 50), SR)
    assert analysis.meter.label == "6/8"
    bar = 6 * 60.0 / 70.0 / 3
    assert downbeat_error(analysis.first_downbeat_s, 0.3, bar) < 0.04
    last = analysis.tempo_map.time_signatures[-1]
    assert (last.numerator, last.denominator) == (6, 8)
    first_bar_line = analysis.tempo_map.time_signatures[-1].tick
    assert analysis.tempo_map.seconds_at(float(first_bar_line)) == pytest.approx(
        analysis.first_downbeat_s
    )


def test_shuffle_in_four_is_not_mistaken_for_six_eight():
    """A shuffle also splits its beats in three, but its bars have four beats."""
    rng = np.random.default_rng(9)
    beat = 60.0 / 100.0
    t = np.arange(int(0.15 * SR)) / SR
    kick = (0.9 * np.sin(2 * np.pi * 60 * t) * np.exp(-t / 0.05)).astype(np.float32)
    snare = (0.7 * rng.standard_normal(len(t)) * np.exp(-t / 0.05)).astype(np.float32)
    hat = (0.2 * rng.standard_normal(len(t)) * np.exp(-t / 0.006)).astype(np.float32)
    events = []
    for bar in range(40):
        at = 0.3 + bar * 4 * beat
        for position in range(4):
            events.append((at + position * beat, kick if position in (0, 2) else snare))
            events.append((at + position * beat, hat))
            events.append((at + (position + 2 / 3) * beat, hat))
        span = np.arange(int(4 * beat * SR)) / SR
        root = (110.0, 146.8, 123.5, 98.0)[bar % 4]
        events.append((at, (0.15 * np.sin(2 * np.pi * root * span)).astype(np.float32)))
    analysis = estimate_tempo_map(place(events, 0.3 + 160 * beat + 1), SR)
    assert analysis.meter.label == "4/4"


def test_uncertain_bars_are_flagged():
    """Identical beats give no way to tell where a bar begins."""
    from conftest import click_times, clicks_at

    signal = clicks_at(click_times(120, 60, 0.3), 60, SR)
    analysis = estimate_tempo_map(signal, SR)
    assert analysis.meter.label == "4/4", "with no evidence, 4/4 is the safe answer"
    assert analysis.meter.low_confidence


def test_too_little_audio_reports_no_downbeat():
    tempo_map = TempoMap([TempoEvent(0, 120.0)])
    result = detect_meter(tempo_map, np.zeros(SR * 3, dtype=np.float32), SR)
    assert result.first_downbeat_s is None
    assert result.low_confidence
    assert result.tempo_map is tempo_map


def test_stems_are_used_when_given():
    signal, first, bar = groove(4, 110.0, 40, 1)
    rng = np.random.default_rng(1)
    noise = (0.001 * rng.standard_normal(signal.size)).astype(np.float32)
    plain = estimate_tempo_map(signal, SR)
    fed = estimate_tempo_map(signal, SR, drums=signal, harmonic=signal, bass=noise)
    assert fed.meter.confidence != plain.meter.confidence


def test_bpm_override_is_not_rescaled_by_the_meter():
    analysis = estimate_tempo_map(six_eight(70.0, 40), SR, bpm_override=70.0)
    assert analysis.tempo_map.tempos[-1].bpm == 70.0
