"""Shared helpers: synthetic audio and a separator that needs no model."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from chartgen.audio.separation import STEM_NAMES

SR = 44100


def click_times(bpm: float, seconds: float, start: float = 0.0) -> np.ndarray:
    return np.arange(start, seconds - 0.05, 60.0 / bpm)


def clicks_at(times: np.ndarray, seconds: float, sr: int = SR, amp: float = 0.8) -> np.ndarray:
    """A decaying 2 kHz burst at each time: a sharp, unambiguous attack."""
    signal = np.zeros(int(seconds * sr), dtype=np.float32)
    length = int(0.03 * sr)
    t = np.arange(length) / sr
    burst = amp * np.sin(2 * np.pi * 2000 * t) * np.exp(-t / 0.008)
    for time in times:
        start = int(round(time * sr))
        end = min(start + length, len(signal))
        signal[start:end] += burst[: end - start].astype(np.float32)
    return signal


def click_track(
    bpm: float, seconds: float, start: float = 0.0, sr: int = SR, amp: float = 0.8
) -> np.ndarray:
    return clicks_at(click_times(bpm, seconds, start), seconds, sr, amp)


def sine(freq: float, seconds: float, sr: int = SR, amp: float = 0.3) -> np.ndarray:
    return (amp * np.sin(2 * np.pi * freq * np.arange(int(seconds * sr)) / sr)).astype(np.float32)


def stereo(mono: np.ndarray) -> np.ndarray:
    return np.stack([mono, mono], axis=1)


def dominant_frequency(mono: np.ndarray, sr: int = SR) -> float:
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
    return float(np.fft.rfftfreq(len(mono), 1 / sr)[np.argmax(spectrum)])


class FakeSeparator:
    """Returns prepared stems and counts how often it was asked."""

    cache_id = "fake-separator"

    def __init__(self, stems: dict[str, np.ndarray], samplerate: int = SR) -> None:
        self.stems = stems
        self.samplerate = samplerate
        self.calls = 0

    def separate(self, audio) -> tuple[int, dict[str, np.ndarray]]:
        self.calls += 1
        return self.samplerate, {name: samples.copy() for name, samples in self.stems.items()}


def song_stems(seconds: float = 20.0) -> dict[str, np.ndarray]:
    """A small rock song: clicks on guitar and drums, a sine on bass, faint piano bleed."""
    frames = int(seconds * SR)
    guitar = click_track(120, seconds, start=0.5) + sine(330, seconds, amp=0.02)
    silence = np.zeros(frames, dtype=np.float32)
    stems = {
        "guitar": guitar,
        "bass": sine(82, seconds, amp=0.25),
        "drums": click_track(120, seconds, start=0.5, amp=0.5),
        "other": sine(220, seconds, amp=0.05),
        "vocals": silence,
        "piano": sine(440, seconds, amp=0.0005),
    }
    assert set(stems) == set(STEM_NAMES)
    return {name: stereo(samples) for name, samples in stems.items()}


@pytest.fixture
def song_file(tmp_path: Path) -> Path:
    """A WAV holding the mix of :func:`song_stems`."""
    mix = np.sum(list(song_stems().values()), axis=0)
    path = tmp_path / "input.wav"
    sf.write(str(path), mix * 0.8, SR)
    return path
