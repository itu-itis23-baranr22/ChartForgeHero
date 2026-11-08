"""Note onset detection on a single stem.

Stems contain bleed from other instruments, which an ordinary onset detector
turns into false notes. Two defences work together:

* a noise gate relative to the stem's own loud level, which removes quiet bleed;
* an adaptive threshold following local activity, which removes small peaks that
  ride on a busy passage.
"""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np
from scipy.ndimage import maximum_filter1d, median_filter
from scipy.signal import find_peaks

from chartgen.audio.io import ANALYSIS_SAMPLERATE

HOP_LENGTH = 256
N_FFT = 1024
ENVELOPE_LATENCY_S = 0.014
"""Envelope peaks trail the attack: measured 9 ms on clicks, 17-20 ms on plucked tones."""
_SILENT_RMS = 1e-4


@dataclass(frozen=True)
class OnsetConfig:
    gate_db: float = -32.0
    """Frames quieter than this, relative to the stem's 95th percentile RMS, are gated."""
    threshold_window_s: float = 1.5
    """Length of the sliding window the adaptive threshold looks at."""
    threshold_mad_k: float = 3.0
    """How many median absolute deviations above the local median a peak must reach."""
    floor_ratio: float = 0.08
    """Peaks below this fraction of the stem's strongest onsets are always rejected."""
    min_strength: float = 2.0
    """Absolute envelope floor. The envelope is level-independent, so sustained sounds
    leave ripple that a purely relative threshold would accept. Measured on synthetic
    audio: steady tones stay below 0.1, white noise below 3.1, real attacks reach 4 or more."""
    min_gap_s: float = 0.05
    """Minimum distance between two detected onsets."""
    latency_s: float = ENVELOPE_LATENCY_S
    """Subtracted from every detected time."""


@dataclass(frozen=True)
class OnsetResult:
    times: np.ndarray
    strengths: np.ndarray


def onset_envelope(mono: np.ndarray, samplerate: int = ANALYSIS_SAMPLERATE) -> np.ndarray:
    """Return the spectral-flux onset strength, one value per :data:`HOP_LENGTH` samples."""
    return librosa.onset.onset_strength(
        y=mono, sr=samplerate, hop_length=HOP_LENGTH, n_fft=N_FFT
    )


def detect_onsets(
    mono: np.ndarray,
    samplerate: int = ANALYSIS_SAMPLERATE,
    config: OnsetConfig | None = None,
) -> OnsetResult:
    """Detect onsets in a mono stem. A silent stem yields no onsets."""
    cfg = config or OnsetConfig()
    empty = OnsetResult(np.empty(0), np.empty(0))
    if mono.size < N_FFT:
        return empty

    rms = librosa.feature.rms(y=mono, frame_length=N_FFT, hop_length=HOP_LENGTH)[0]
    level = float(np.percentile(rms, 95))
    if level < _SILENT_RMS:
        return empty

    envelope = onset_envelope(mono, samplerate)
    frames = min(len(envelope), len(rms))
    envelope, rms = envelope[:frames].copy(), rms[:frames]

    # Look a few frames ahead so that the gate does not cut off the attack itself.
    gate_open = maximum_filter1d(rms, size=5, origin=-2) >= level * 10.0 ** (cfg.gate_db / 20.0)
    envelope[~gate_open] = 0.0

    window = max(3, int(cfg.threshold_window_s * samplerate / HOP_LENGTH)) | 1
    local_median = median_filter(envelope, size=window, mode="nearest")
    local_mad = median_filter(np.abs(envelope - local_median), size=window, mode="nearest")
    strong = envelope[envelope > 0]
    if strong.size == 0:
        return empty
    floor = max(cfg.floor_ratio * float(np.percentile(strong, 99)), cfg.min_strength)
    threshold = np.maximum(local_median + cfg.threshold_mad_k * local_mad, floor)

    distance = max(1, int(cfg.min_gap_s * samplerate / HOP_LENGTH))
    peaks, _ = find_peaks(envelope, height=threshold, distance=distance)
    times = librosa.frames_to_time(peaks, sr=samplerate, hop_length=HOP_LENGTH) - cfg.latency_s
    keep = times >= 0
    return OnsetResult(times[keep], envelope[peaks][keep])
