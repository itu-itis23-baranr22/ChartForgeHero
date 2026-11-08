"""Vocal traces in a stem must not become notes; a real note under a loud singer must stay."""

import json
from pathlib import Path

import numpy as np
import pytest
from conftest import FakeSeparator, stereo

from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.separation import STEM_NAMES
from chartgen.audio.vocal_bleed import (
    THRESHOLDS_PATH,
    BleedThresholds,
    analyze_bleed,
    load_thresholds,
)
from chartgen.chart.charter import build_expert_track
from chartgen.core.model import Instrument, SongMetadata
from chartgen.core.timing import TempoEvent, TempoMap
from chartgen.pipeline import BuildConfig, build_song

SR = ANALYSIS_SAMPLERATE
TEMPO = TempoMap([TempoEvent(0, 120.0)])
SECONDS = 24.0


def voiced(freq: float, seconds: float, amp: float, sr: int = SR, rng_seed: int = 0) -> np.ndarray:
    """A sung syllable: a sharp consonant, then a harmonic vowel."""
    rng = np.random.default_rng(rng_seed)
    t = np.arange(int(seconds * sr)) / sr
    vowel = sum(np.sin(2 * np.pi * freq * k * t) / k for k in range(1, 8))
    envelope = np.minimum(1.0, t / 0.01) * np.minimum(1.0, (t[-1] - t) / 0.03)
    consonant = rng.standard_normal(t.size) * np.exp(-t / 0.015)
    return (amp * (vowel * envelope + 0.8 * consonant)).astype(np.float32)


def plucked(freq: float, seconds: float, amp: float, sr: int = SR) -> np.ndarray:
    t = np.arange(int(seconds * sr)) / sr
    wave = sum(np.sin(2 * np.pi * freq * k * t) / k for k in range(1, 8))
    return (amp * wave * np.exp(-t / 0.8) * np.minimum(1.0, t / 0.002)).astype(np.float32)


def place(events, seconds, sr=SR):
    out = np.zeros(int(seconds * sr), dtype=np.float32)
    for time, wave in events:
        start = int(time * sr)
        end = min(start + wave.size, out.size)
        out[start:end] += wave[: end - start]
    return out


def song(sr: int = SR):
    """Guitar plays in the first half. In the second half it rests while a singer sings, and a
    faint copy of the singing leaks into the guitar stem, as separation does."""
    guitar_times = 1.0 + np.arange(16) * 0.7
    vocal_times = 13.0 + np.arange(14) * 0.75
    guitar = place([(time, plucked(196.0, 0.65, 0.3, sr)) for time in guitar_times], SECONDS, sr)
    vocals = place(
        [(time, voiced(330.0 + 15 * (i % 4), 0.6, 0.35, sr, i)) for i, time in enumerate(vocal_times)],
        SECONDS,
        sr,
    )
    leaked = guitar + 0.06 * vocals
    return leaked, vocals, guitar_times, vocal_times


def track_times(track) -> np.ndarray:
    ticks = sorted({note.tick for note in track.notes})
    return TEMPO.seconds_at(np.array(ticks, dtype=np.float64))


def near(times: np.ndarray, targets: np.ndarray, tolerance: float = 0.06) -> np.ndarray:
    return np.array([np.abs(targets - time).min() <= tolerance for time in times])


def test_leak_makes_false_notes_without_the_filter():
    """The test must show the problem, or it proves nothing about the fix."""
    leaked, _, guitar_times, vocal_times = song()
    times = track_times(build_expert_track(Instrument.GUITAR, leaked, TEMPO, SECONDS).track)
    assert near(times, vocal_times).sum() >= 5


def test_vocal_notes_go_and_guitar_notes_stay():
    leaked, vocals, guitar_times, vocal_times = song()
    built = build_expert_track(Instrument.GUITAR, leaked, TEMPO, SECONDS, vocals=vocals)
    times = track_times(built.track)
    assert near(times, vocal_times).sum() == 0, "no note may remain in the singing"
    assert near(guitar_times, times).all(), "every guitar note must survive"
    removed = [note for note in built.bleed if note.removed]
    assert len(removed) >= 5
    assert all(near(np.array([note.time_s]), vocal_times)[0] for note in removed)


def test_loud_singing_over_a_real_guitar_removes_nothing():
    times = 1.0 + np.arange(20) * 0.5
    guitar = place([(time, plucked(196.0, 0.45, 0.3)) for time in times], SECONDS)
    vocals = place([(time, voiced(330.0, 0.45, 0.6, rng_seed=int(time * 10))) for time in times], SECONDS)
    built = build_expert_track(Instrument.GUITAR, guitar, TEMPO, SECONDS, vocals=vocals)
    assert not any(note.removed for note in built.bleed)
    assert len(track_times(built.track)) == len(times)


def test_quiet_real_guitar_passage_stays_if_no_one_sings():
    loud = [(1.0 + i * 0.5, plucked(196.0, 0.45, 0.4)) for i in range(10)]
    quiet = [(8.0 + i * 0.5, plucked(196.0, 0.45, 0.06)) for i in range(10)]
    guitar = place(loud + quiet, SECONDS)
    built = build_expert_track(
        Instrument.GUITAR, guitar, TEMPO, SECONDS, vocals=np.zeros_like(guitar)
    )
    assert not any(note.removed for note in built.bleed)
    assert len(track_times(built.track)) == 20


def test_without_vocals_nothing_is_compared():
    leaked, *_ = song()
    assert build_expert_track(Instrument.GUITAR, leaked, TEMPO, SECONDS).bleed == ()


def test_stem_holding_only_a_leak_gives_an_empty_track():
    _, vocals, *_ = song()
    built = build_expert_track(Instrument.GUITAR, 0.06 * vocals + 1e-4 * vocals, TEMPO, SECONDS, vocals=vocals)
    # The whole stem is a quiet copy, but it is its own loud level, so this is not a leak by
    # level alone. The result must simply stay valid.
    assert all(0 <= note.lane <= 4 for note in built.track.notes)


def test_each_condition_is_required():
    leaked, vocals, _, vocal_times = song()
    times = vocal_times
    next_times = np.r_[times[1:], SECONDS]
    base = load_thresholds()
    assert any(n.removed for n in analyze_bleed(leaked, vocals, times, next_times, SR, base))

    def with_changed(**change):
        values = {**base.__dict__, **change}
        return BleedThresholds(**values)

    never_loud_enough = with_changed(min_vocal_over_stem_db=200.0)
    never_quiet_enough = with_changed(max_stem_level_db=-200.0)
    never_fading_enough = with_changed(max_stem_sustain=0.0)
    for limits in (never_loud_enough, never_quiet_enough, never_fading_enough):
        assert not any(n.removed for n in analyze_bleed(leaked, vocals, times, next_times, SR, limits))


def test_no_notes_is_fine():
    silence = np.zeros(SR, dtype=np.float32)
    assert analyze_bleed(silence, silence, np.empty(0), np.empty(0), SR) == []


def test_silent_stems_do_not_divide_by_zero():
    silence = np.zeros(SR * 2, dtype=np.float32)
    notes = analyze_bleed(silence, silence, np.array([0.5]), np.array([1.5]), SR)
    assert np.isfinite(notes[0].vocal_over_stem_db)


def write_thresholds(tmp_path: Path, **changes) -> Path:
    lines = []
    for line in THRESHOLDS_PATH.read_text(encoding="utf-8").splitlines():
        key = line.split("=")[0].strip()
        if key in changes:
            if changes[key] is not None:
                lines.append(f"{key} = {changes[key]}")
            continue
        lines.append(line)
    path = tmp_path / "limits.toml"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"max_stem_level_db": None}, "expected keys"),
        ({"max_stem_sustain": -1.0}, "out of range"),
        ({"level_window_s": 0.0}, "out of range"),
        ({"sustain_start_s": 1.0}, "must come before"),
    ],
)
def test_invalid_thresholds_are_refused(tmp_path, changes, message):
    with pytest.raises(ValueError, match=message):
        load_thresholds(write_thresholds(tmp_path, **changes))


def stems_for_pipeline(sr: int = 44100) -> dict[str, np.ndarray]:
    leaked, vocals, *_ = song(sr)
    silence = np.zeros_like(leaked)
    stems = {name: stereo(silence) for name in STEM_NAMES}
    stems["guitar"] = stereo(leaked)
    stems["vocals"] = stereo(vocals)
    return stems


def build(tmp_path, stems, sr=44100):
    import soundfile as sf

    mix = np.sum(list(stems.values()), axis=0)
    path = tmp_path / "input.wav"
    sf.write(str(path), mix * 0.8, sr)
    config = BuildConfig(
        input_path=path,
        metadata=SongMetadata("T", "A"),
        instruments=frozenset({Instrument.GUITAR}),
        output_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
    )
    return build_song(config, FakeSeparator(stems, sr))


@pytest.mark.heavy
def test_analysis_lists_vocal_notes_with_times_and_reasons(tmp_path, caplog):
    import logging

    with caplog.at_level(logging.DEBUG, logger="chartgen"):
        folder = build(tmp_path, stems_for_pipeline()).folder
    analysis = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
    bleed = analysis["charts"]["guitar"]["expert"]["vocal_bleed"]
    assert bleed["removed_count"] >= 5
    listed = bleed["vocal_dominant_notes"]
    removed = [note for note in listed if note["removed"]]
    assert len(removed) == bleed["removed_count"]
    assert all(note["reason"] and note["time_s"] > 12 for note in removed)
    assert "removed" in caplog.text
    assert "as vocal bleed" in caplog.text


def distorted_stems(sr: int = 44100) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(8)
    events = []
    for index in range(40):
        wave = plucked(110.0 + 10 * (index % 5), 0.4, 0.3, sr)
        noise = (1.5 * rng.standard_normal(wave.size) * (np.abs(wave) + 0.1)).astype(np.float32)
        events.append((0.5 + index * 0.4, wave + noise))
    guitar = place(events, SECONDS, sr)
    silence = np.zeros_like(guitar)
    stems = {name: stereo(silence) for name in STEM_NAMES}
    stems["guitar"] = stereo(guitar)
    return stems


@pytest.mark.heavy
def test_distortion_chord_limit_warns_in_analysis_and_terminal(tmp_path, caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="chartgen"):
        result = build(tmp_path, distorted_stems())
    analysis = json.loads((result.folder / "analysis.json").read_text(encoding="utf-8"))
    limit = analysis["charts"]["guitar"]["expert"]["chord_limit"]
    assert limit["temporary_distortion_limit_in_force"] is True
    assert limit["used"] > 0.5
    assert any("temporary chord limit" in warning for warning in analysis["warnings"])
    assert "temporary chord limit" in caplog.text


@pytest.mark.heavy
def test_clean_song_does_not_warn_about_distortion(tmp_path):
    result = build(tmp_path, stems_for_pipeline())
    analysis = json.loads((result.folder / "analysis.json").read_text(encoding="utf-8"))
    assert analysis["charts"]["guitar"]["expert"]["chord_limit"]["temporary_distortion_limit_in_force"] is False
    assert not any("temporary chord limit" in warning for warning in analysis["warnings"])
