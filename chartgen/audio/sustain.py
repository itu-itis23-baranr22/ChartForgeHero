"""How long each note rings.

A note lasts until its level has fallen far enough from its own peak, or until the next note
takes over. A distorted guitar hardly decays at all, so the next onset often decides.
"""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np

from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.onsets import HOP_LENGTH, N_FFT

_SILENT_RMS = 1e-5


@dataclass(frozen=True)
class SustainConfig:
    release_db: float = 12.0
    """A note has ended once it is this far below its peak."""
    peak_window_s: float = 0.08
    """Where to look for the note's peak after its onset."""
    hold_frames: int = 3
    """How long the level must stay down, so that a tremolo does not end the note."""


def note_durations(
    mono: np.ndarray,
    times: np.ndarray,
    next_times: np.ndarray,
    samplerate: int = ANALYSIS_SAMPLERATE,
    config: SustainConfig | None = None,
) -> np.ndarray:
    """Return how many seconds each note rings before fading or being cut off.

    Args:
        mono: The stem.
        times: Note start times.
        next_times: When each note is cut off by the next one.
        samplerate: The stem's sample rate.
        config: Detection limits.
    """
    cfg = config or SustainConfig()
    if times.size == 0:
        return np.empty(0)
    if mono.size < N_FFT:
        return np.zeros(times.size)

    rms = librosa.feature.rms(y=mono, frame_length=N_FFT, hop_length=HOP_LENGTH)[0]
    level = 20.0 * np.log10(np.maximum(rms, _SILENT_RMS))
    per_second = samplerate / HOP_LENGTH
    peak_frames = max(1, int(cfg.peak_window_s * per_second))

    durations = np.zeros(times.size)
    for index, (time, next_time) in enumerate(zip(times, next_times)):
        start = int(time * per_second)
        stop = min(int(next_time * per_second), len(level))
        if start >= stop:
            continue
        peak = float(level[start : min(start + peak_frames, stop)].max())
        below = level[start:stop] < peak - cfg.release_db
        end = stop
        run = 0
        for offset, is_below in enumerate(below):
            run = run + 1 if is_below else 0
            if run >= cfg.hold_frames:
                end = start + offset - cfg.hold_frames + 1
                break
        durations[index] = (end - start) / per_second
    return durations
