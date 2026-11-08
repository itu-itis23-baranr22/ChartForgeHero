import numpy as np
import pytest
from conftest import click_times, click_track, clicks_at, sine

from chartgen.audio.io import ANALYSIS_SAMPLERATE, resample
from chartgen.audio.onsets import detect_onsets
from chartgen.audio.presence import PresenceThreshold, analyze_presence
from chartgen.audio.tempo import (
    MIN_EVENT_GAIN_S,
    choose_grid,
    estimate_tempo_map,
    fit_tempo_map,
)

SR = ANALYSIS_SAMPLERATE


def nearest_error(detected: np.ndarray, truth: np.ndarray) -> np.ndarray:
    """For each true time, the distance to the closest detected time."""
    return np.abs(detected[None, :] - truth[:, None]).min(axis=1)


# ---------------------------------------------------------------- tempo


def drum_groove(bpm: float, seconds: float, pattern: str = "rock", start: float = 0.2) -> np.ndarray:
    """A synthetic drum loop. Hi-hats outnumber everything, which is what tempts a tracker
    into the wrong metrical level."""
    rng = np.random.default_rng(3)
    frames = int(seconds * SR)
    signal = np.zeros(frames, dtype=np.float32)

    def hit(time: float, wave: np.ndarray) -> None:
        index = int(time * SR)
        end = min(index + len(wave), frames)
        if 0 <= index < frames:
            signal[index:end] += wave[: end - index]

    t = np.arange(int(0.15 * SR)) / SR
    kick = (0.9 * np.sin(2 * np.pi * 60 * t) * np.exp(-t / 0.04)).astype(np.float32)
    snare = (0.6 * rng.standard_normal(len(t)) * np.exp(-t / 0.05)).astype(np.float32)
    hat = (0.25 * rng.standard_normal(len(t)) * np.exp(-t / 0.008)).astype(np.float32)

    beat = 60.0 / bpm
    bar = 0
    while start + bar * 4 * beat < seconds:
        at = start + bar * 4 * beat
        if pattern == "rock":
            for position in (0, 2):
                hit(at + position * beat, kick)
            for position in (1, 3):
                hit(at + position * beat, snare)
            for eighth in range(8):
                hit(at + eighth * beat / 2, hat)
        else:  # The 3-3-2 pattern of reggaeton: its strongest period is 3/2 of the beat.
            for position in (0, 1, 2, 3):
                hit(at + position * beat, kick)
            for position in (0.75, 1.5, 2.75, 3.5):
                hit(at + position * beat, snare)
        bar += 1
    return signal


def resampled(signal: np.ndarray) -> np.ndarray:
    from chartgen.audio.io import resample

    return resample(signal, 44100, SR)


@pytest.mark.parametrize("start", [0.0, 0.11, 0.25, 0.4, 1.3])
def test_120_bpm_click_gives_one_tempo_and_aligned_beats(start):
    truth = click_times(120, 30, start)
    analysis = estimate_tempo_map(clicks_at(truth, 30, SR), SR)
    assert analysis.method == "constant"
    assert analysis.bpm == pytest.approx(120, abs=0.1)
    assert len(analysis.tempo_map.tempos) <= 2
    # A click before the first grid beat falls in the lead-in, which is not on the grid.
    assert analysis.on_grid_ratio >= 0.98
    # Every other click sits on a quarter-note tick of the fitted map.
    ticks = analysis.tempo_map.ticks_at(truth)
    distance = np.abs(ticks / 192 - np.round(ticks / 192))
    assert np.max(distance[1:]) * 0.5 < 0.02, "more than 20 ms off the beat grid"


@pytest.mark.parametrize("bpm", [85.0, 97.08, 128.0, 155.0])
def test_rock_groove_finds_the_quarter_note_not_a_faster_level(bpm):
    """Regression test: the beat tracker reported 129 for a 97 BPM song."""
    analysis = estimate_tempo_map(resampled(drum_groove(bpm, 60)), SR)
    assert analysis.method == "constant"
    assert analysis.bpm == pytest.approx(bpm, abs=0.1)
    assert len(analysis.tempo_map.tempos) <= 2


def test_very_fast_song_comes_out_at_half_speed():
    analysis = estimate_tempo_map(resampled(drum_groove(180.0, 60)), SR)
    assert analysis.bpm == pytest.approx(90.0, abs=0.1)


def test_three_three_two_groove_finds_the_quarter_note():
    """Regression test: this pattern's strongest period is 3/2 of the real beat."""
    analysis = estimate_tempo_map(resampled(drum_groove(126.0, 60, "dembow")), SR)
    assert analysis.bpm == pytest.approx(126.0, abs=0.1)


def test_long_song_does_not_drift_off_the_grid():
    bpm = 97.08
    truth = click_times(bpm, 240, 0.3)
    analysis = estimate_tempo_map(clicks_at(truth, 240, SR), SR)
    assert analysis.method == "constant"
    ticks = analysis.tempo_map.ticks_at(truth[-20:])
    grid = np.round(ticks / 192) * 192
    assert np.abs(analysis.tempo_map.seconds_at(grid) - truth[-20:]).max() < 0.015


def test_human_jitter_stays_a_single_tempo():
    rng = np.random.default_rng(0)
    truth = click_times(100, 120, 0.3)
    played = truth + rng.uniform(-0.008, 0.008, len(truth))
    analysis = estimate_tempo_map(clicks_at(played, 120, SR), SR)
    assert analysis.method == "constant"
    assert analysis.bpm == pytest.approx(100, abs=0.1)


def wandering_clicks(amplitude_s: float, bpm: float = 97.0, seconds: float = 240.0) -> np.ndarray:
    nominal = click_times(bpm, seconds, 0.3)
    return nominal + amplitude_s * np.sin(2 * np.pi * nominal / 120.0)


def test_wander_within_the_limit_keeps_one_tempo():
    played = wandering_clicks(0.012)
    analysis = estimate_tempo_map(clicks_at(played, 240, SR), SR)
    assert analysis.method == "constant"
    assert analysis.bpm == pytest.approx(97.0, abs=0.2)
    assert len(analysis.tempo_map.tempos) <= 2
    assert analysis.final.max_ms <= 25
    assert "one tempo" in analysis.decision


def test_wander_over_the_limit_gets_events_until_every_region_is_within_it():
    """The owner's rule is in milliseconds: this is only 0.3 % of tempo deviation, yet the
    beats stray 50 ms, and that is what counts."""
    played = wandering_clicks(0.05)
    analysis = estimate_tempo_map(clicks_at(played, 240, SR), SR)
    assert analysis.method == "variable"
    assert analysis.one_tempo.max_ms > 25
    assert analysis.final.max_ms <= 25
    assert analysis.final.on_grid >= analysis.one_tempo.on_grid
    assert analysis.bpm == pytest.approx(97.0, abs=1.0)


@pytest.mark.parametrize("limit_s,expected", [(0.005, "variable"), (0.2, "constant")])
def test_drift_limit_is_a_parameter(limit_s, expected):
    played = wandering_clicks(0.05)
    analysis = estimate_tempo_map(clicks_at(played, 240, SR), SR, max_beat_drift_s=limit_s)
    assert analysis.method == expected
    assert analysis.max_beat_drift_ms == pytest.approx(limit_s * 1000)


def test_stricter_limit_never_means_fewer_events():
    played = wandering_clicks(0.05)
    counts = [
        len(estimate_tempo_map(clicks_at(played, 240, SR), SR, max_beat_drift_s=limit).tempo_map.tempos)
        for limit in (0.2, 0.04, 0.015)
    ]
    assert counts == sorted(counts)


def test_every_event_earns_its_place():
    played = wandering_clicks(0.05)
    analysis = estimate_tempo_map(clicks_at(played, 240, SR), SR)
    assert analysis.event_details
    for detail in analysis.event_details:
        assert detail.gain_ms >= MIN_EVENT_GAIN_S * 1000
    explanations = analysis.event_explanations()
    assert len(explanations) == len(analysis.tempo_map.tempos)
    explained = [item for item in explanations if "gain_ms" in item]
    assert len(explained) == len(analysis.event_details)
    assert all("limit 25 ms" in item["reason"] for item in explained)


def test_short_bump_gets_events_only_around_it():
    """One tempo fits all but 16 s of this song, which runs 60 ms late and then returns.
    Bending the rest of the song would be wasted events."""
    nominal = click_times(97, 240, 0.3)
    truth = nominal + np.interp(nominal, [0, 100, 104, 116, 120, 240], [0, 0, 0.06, 0.06, 0, 0])
    analysis = estimate_tempo_map(clicks_at(truth, 241, SR), SR)
    assert analysis.method == "variable"
    assert analysis.final.max_ms <= 25
    assert len(analysis.event_details) <= 6
    times = [detail.time_s for detail in analysis.event_details]
    assert min(times) > 70 and max(times) < 150


def test_tracker_mistake_cannot_spend_events():
    """Regression test: in a sparse intro, the tracker locked onto an off-beat pattern and
    strayed 223 ms from a song whose onsets fit one tempo perfectly."""
    period = 60 / 130
    grid = 0.2 + np.arange(400) * period
    beats = grid.copy()
    beats[:60] += period / 4  # The first beats sit one sixteenth late.
    onsets = 0.2 + np.arange(1600) * period / 4
    choice = choose_grid(beats, onsets, np.ones_like(onsets), 130.0, float(grid[-1] + 1))
    assert choice.method == "constant"
    assert choice.final.on_grid == pytest.approx(1.0)
    assert choice.one_tempo.max_ms > 25, "the stray beats must still be reported"
    assert "would not bring" in choice.decision


def test_section_that_moves_the_song_away_from_one_tempo_is_followed():
    """The middle of this song sits 70 ms late, which no single tempo can explain, although
    the tempo itself hardly differs."""
    nominal = click_times(97, 240, 0.3)
    truth = nominal + np.interp(nominal, [0, 80, 90, 160, 170, 240], [0, 0, 0.07, 0.07, 0, 0])
    analysis = estimate_tempo_map(clicks_at(truth, 241, SR), SR)
    assert analysis.method == "variable"
    assert analysis.one_tempo.max_ms > 25
    assert analysis.final.max_ms <= 25
    assert analysis.on_grid_ratio > 0.9


def test_short_faster_section_keeps_every_beat_on_the_grid():
    """A 6 % faster section gains almost exactly one beat, so the song returns to the same
    grid 58 ms off: whatever the method, no beat may end up far from a grid line."""
    periods = np.full(390, 60 / 97)
    periods[190:206] = 60 / (97 * 1.06)
    truth = 0.3 + np.concatenate(([0.0], np.cumsum(periods)))
    analysis = estimate_tempo_map(clicks_at(truth, float(truth[-1] + 1), SR), SR)
    grid = np.round(analysis.tempo_map.ticks_at(truth[2:]) / 192) * 192
    errors = np.abs(analysis.tempo_map.seconds_at(grid) - truth[2:])
    assert np.percentile(errors, 95) < 0.05


def test_decision_explains_every_tempo_event():
    analysis = estimate_tempo_map(clicks_at(click_times(120, 30, 0.2), 30, SR), SR)
    assert analysis.decision
    explanations = analysis.event_explanations()
    assert len(explanations) == len(analysis.tempo_map.tempos)
    assert explanations[-1]["reason"] == "main tempo"


def test_bpm_override_is_used_exactly_even_when_it_is_wrong():
    truth = click_times(120, 40, 0.3)
    analysis = estimate_tempo_map(clicks_at(truth, 40, SR), SR, bpm_override=129.2)
    assert analysis.method == "override"
    assert analysis.bpm == 129.2
    assert analysis.tempo_map.tempos[-1].bpm == 129.2
    assert len(analysis.tempo_map.tempos) <= 2
    assert analysis.estimated_bpm == pytest.approx(120, abs=0.1)
    assert "129.2" in analysis.decision


def test_bpm_override_still_finds_the_phase():
    truth = click_times(90, 60, 0.47)
    analysis = estimate_tempo_map(clicks_at(truth, 60, SR), SR, bpm_override=90.0)
    ticks = analysis.tempo_map.ticks_at(truth[1:])
    grid = np.round(ticks / 192) * 192
    assert np.abs(analysis.tempo_map.seconds_at(grid) - truth[1:]).max() < 0.02


def test_bpm_override_works_on_audio_without_onsets():
    analysis = estimate_tempo_map(np.zeros(SR * 10, dtype=np.float32), SR, bpm_override=100.0)
    assert analysis.method == "override"
    assert analysis.tempo_map.tempos[0].bpm == 100.0


def band_song(bpm: float, bars: int, pickup_beats: int, start: float = 0.2) -> tuple[np.ndarray, float]:
    """Kick on 1 and 3, snare on 2 and 4, and a new chord each bar. Before the first full bar
    comes a pickup of 0-3 beats of the same drums, so the bars do not begin where sound does.

    Returns the audio at the analysis rate and the time of the first downbeat.
    """
    rng = np.random.default_rng(11)
    beat = 60.0 / bpm
    first_downbeat = start + pickup_beats * beat
    seconds = first_downbeat + bars * 4 * beat + 1
    frames = int(seconds * SR)
    signal = np.zeros(frames, dtype=np.float32)
    t = np.arange(int(0.2 * SR)) / SR
    kick = (0.9 * np.sin(2 * np.pi * 70 * t) * np.exp(-t / 0.05)).astype(np.float32)
    snare = (0.5 * rng.standard_normal(len(t)) * np.exp(-t / 0.05)).astype(np.float32)

    def add(time: float, wave: np.ndarray) -> None:
        index = int(time * SR)
        end = min(index + len(wave), frames)
        if 0 <= index < frames:
            signal[index:end] += wave[: end - index]

    chords = [(220.0, 277.2, 329.6), (293.7, 370.0, 440.0), (246.9, 311.1, 370.0), (196.0, 246.9, 293.7)]
    total_beats = pickup_beats + bars * 4
    for index in range(total_beats):
        position = (index - pickup_beats) % 4
        add(start + index * beat, kick if position in (0, 2) else snare)
    bar_length = 4 * beat
    span = np.arange(int(bar_length * SR)) / SR
    for bar in range(bars):
        tones = chords[bar % len(chords)]
        wave = sum(np.sin(2 * np.pi * f * span) for f in tones) * 0.08 * np.exp(-span / (bar_length * 2))
        add(first_downbeat + bar * bar_length, wave.astype(np.float32))
    return signal, first_downbeat


@pytest.mark.parametrize("pickup", [0, 1, 2, 3])
def test_bars_begin_on_the_real_downbeat(pickup):
    signal, first_downbeat = band_song(110.0, 40, pickup)
    analysis = estimate_tempo_map(signal, SR)
    assert analysis.bpm == pytest.approx(110.0, abs=0.2)
    assert analysis.first_downbeat_s is not None
    bar = 4 * 60.0 / 110.0
    difference = (analysis.first_downbeat_s - first_downbeat) % bar
    assert min(difference, bar - difference) < 0.03
    assert analysis.bar_confidence > 0


@pytest.mark.parametrize("pickup", [1, 3])
def test_bpm_override_still_finds_the_downbeat(pickup):
    signal, first_downbeat = band_song(110.0, 40, pickup)
    analysis = estimate_tempo_map(signal, SR, bpm_override=110.0)
    bar = 4 * 60.0 / 110.0
    difference = (analysis.first_downbeat_s - first_downbeat) % bar
    assert min(difference, bar - difference) < 0.03


def test_real_tempo_change_uses_a_variable_map():
    first = 0.3 + np.arange(80) * 0.5
    second = first[-1] + np.arange(1, 100) * (60 / 150)
    truth = np.concatenate([first, second])
    seconds = float(truth[-1] + 1)
    analysis = estimate_tempo_map(clicks_at(truth, seconds, SR), SR)
    assert analysis.method == "variable"
    bpms = [event.bpm for event in analysis.tempo_map.tempos]
    assert min(abs(bpm - 120) for bpm in bpms) < 2
    assert min(abs(bpm - 150) for bpm in bpms) < 2
    assert analysis.on_grid_ratio > 0.8


def test_slow_drift_uses_a_variable_map():
    periods = np.linspace(60 / 96, 60 / 108, 260)
    truth = 0.3 + np.concatenate(([0.0], np.cumsum(periods)))
    analysis = estimate_tempo_map(clicks_at(truth, float(truth[-1] + 1), SR), SR)
    assert analysis.method == "variable"
    assert analysis.on_grid_ratio > 0.8


def test_beats_alone_can_build_a_map_across_a_tempo_change():
    first = 0.3 + np.arange(40) * 0.5
    second = first[-1] + np.arange(1, 41) * (60 / 150)
    beats = np.concatenate([first, second])
    tempo_map, choice = fit_tempo_map(beats)
    assert choice.method == "variable"
    assert 150 == pytest.approx(tempo_map.tempos[-1].bpm, abs=1.0)
    ticks = tempo_map.ticks_at(beats)
    assert np.abs(ticks - np.round(ticks / 192) * 192).max() < 8


def test_small_jitter_is_not_a_tempo_change():
    beats = 0.2 + np.arange(200) * 0.5 + np.random.default_rng(0).uniform(-0.012, 0.012, 200)
    _, choice = fit_tempo_map(beats)
    assert choice.method == "constant"


def test_lead_in_never_exceeds_twice_the_song_tempo():
    for start in (0.001, 0.05, 0.2, 0.26, 0.49, 0.7, 5.03):
        beats = start + np.arange(30) * 0.5
        tempo_map, _ = fit_tempo_map(beats)
        assert tempo_map.tempos[0].bpm <= 240.5
        assert tempo_map.tempos[0].tick == 0


@pytest.mark.parametrize(
    "signal",
    [
        np.zeros(SR * 10, dtype=np.float32),
        np.zeros(100, dtype=np.float32),
        (0.1 * np.random.default_rng(5).standard_normal(SR * 30)).astype(np.float32),
    ],
    ids=["silence", "too short", "noise without a pulse"],
)
def test_audio_without_a_pulse_falls_back_to_a_default_tempo(signal):
    analysis = estimate_tempo_map(signal, SR)
    assert analysis.is_fallback
    assert analysis.tempo_map.tempos[0].bpm == 120.0


# ---------------------------------------------------------------- onsets


def test_onsets_find_every_click_within_15_ms():
    truth = click_times(120, 20, 0.5)
    result = detect_onsets(clicks_at(truth, 20, SR), SR)
    assert len(result.times) == len(truth)
    assert nearest_error(result.times, truth).max() < 0.015


def test_onset_timing_has_no_systematic_bias():
    truth = click_times(100, 30, 0.37)
    result = detect_onsets(clicks_at(truth, 30, SR), SR)
    assert np.mean(result.times - truth) == pytest.approx(0.0, abs=0.006)


def test_quiet_bleed_does_not_become_notes():
    loud = click_times(120, 20, 0.5)
    bleed = click_times(120, 20, 0.75)
    signal = clicks_at(loud, 20, SR, amp=0.8) + clicks_at(bleed, 20, SR, amp=0.008)
    result = detect_onsets(signal, SR)
    assert len(result.times) == len(loud)
    assert nearest_error(result.times, loud).max() < 0.015


def test_passage_with_only_bleed_stays_empty():
    loud = click_times(120, 10, 0.5)
    bleed = click_times(120, 20, 10.25)
    signal = clicks_at(loud, 20, SR, amp=0.8) + clicks_at(bleed, 20, SR, amp=0.005)
    assert detect_onsets(signal, SR).times.max() < 10.1


def test_steady_tone_has_no_false_onsets():
    # The tone starts abruptly at time zero, which is a real attack; nothing may follow it.
    assert len(detect_onsets(sine(440, 10, SR), SR).times) <= 1


def test_stationary_noise_has_few_false_onsets():
    noise = (0.1 * np.random.default_rng(0).standard_normal(SR * 20)).astype(np.float32)
    assert len(detect_onsets(noise, SR).times) <= 5


def test_notes_are_found_under_a_sustained_tone():
    truth = click_times(120, 20, 0.5)
    signal = clicks_at(truth, 20, SR, amp=0.8) + sine(220, 20, SR, amp=0.2)
    result = detect_onsets(signal, SR)
    assert nearest_error(result.times, truth).max() < 0.02
    assert len(result.times) == len(truth)


def test_silence_has_no_onsets():
    assert detect_onsets(np.zeros(SR * 5, dtype=np.float32), SR).times.size == 0


def test_very_short_audio_has_no_onsets():
    assert detect_onsets(np.zeros(10, dtype=np.float32), SR).times.size == 0


# ---------------------------------------------------------------- presence


def test_strong_stem_is_present():
    stem, other = sine(440, 10), sine(110, 10)
    result = analyze_presence("guitar", stem, stem + other, 44100)
    assert result.present
    assert result.energy_ratio_db == pytest.approx(-3.0, abs=0.5)
    assert result.active_ratio > 0.9


def test_faint_bleed_is_absent():
    loud = sine(110, 10, amp=0.5)
    bleed = sine(440, 10, amp=0.001)
    result = analyze_presence("guitar", bleed, loud + bleed, 44100)
    assert not result.present
    assert result.energy_ratio_db < -40


def test_silent_stem_is_absent():
    loud = sine(110, 10)
    result = analyze_presence("guitar", np.zeros_like(loud), loud, 44100)
    assert not result.present
    assert result.energy_ratio_db == float("-inf")


def test_piano_must_clear_a_higher_bar_than_guitar():
    loud = sine(110, 10, amp=0.5)
    medium = sine(440, 10, amp=0.06)  # about -18.5 dB against the mix: passes -25, fails -18
    mix = loud + medium
    assert analyze_presence("guitar", medium, mix, 44100).present
    assert not analyze_presence("piano", medium, mix, 44100).present


def test_brief_loud_stem_is_rejected_by_the_active_ratio():
    frames = 44100 * 10
    loud = sine(110, 10)
    brief = np.zeros(frames, dtype=np.float32)
    brief[:22050] = sine(440, 0.5, amp=0.9)
    result = analyze_presence("guitar", brief, loud + brief, 44100)
    assert result.active_ratio < 0.1
    assert not result.present


def test_custom_threshold_overrides_the_default():
    loud = sine(110, 10, amp=0.5)
    medium = sine(440, 10, amp=0.05)
    result = analyze_presence("guitar", medium, loud + medium, 44100, PresenceThreshold(-5.0, 0.5))
    assert not result.present


def test_presence_rejects_unaligned_signals():
    with pytest.raises(ValueError):
        analyze_presence("guitar", sine(440, 1), sine(440, 2), 44100)


# ---------------------------------------------------------------- resampling


def test_resample_keeps_duration_and_returns_same_array_at_equal_rate():
    samples = sine(440, 1)
    assert resample(samples, 44100, 44100) is samples
    assert len(resample(samples, 44100, 22050)) == pytest.approx(22050, abs=2)


def test_click_track_helper_builds_expected_length():
    assert len(click_track(120, 2)) == 88200
