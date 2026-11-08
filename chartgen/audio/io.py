"""Loading local audio files."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from chartgen.errors import AudioLoadError

SUPPORTED_EXTENSIONS = frozenset({".mp3", ".wav", ".flac", ".ogg"})
ANALYSIS_SAMPLERATE = 22050
"""Rate analysis runs at. Beat and onset detection need nothing above 11 kHz."""


@dataclass(frozen=True)
class AudioData:
    """Decoded audio shaped ``(frames, channels)``."""

    samples: np.ndarray
    samplerate: int

    @property
    def frames(self) -> int:
        return self.samples.shape[0]

    @property
    def duration_s(self) -> float:
        return self.frames / self.samplerate


def load_audio(path: Path) -> AudioData:
    """Decode a local audio file.

    Raises:
        AudioLoadError: If the file is missing, unsupported, unreadable or empty.
    """
    if not path.is_file():
        raise AudioLoadError(f"Input file not found: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise AudioLoadError(f"Unsupported format {path.suffix!r}. Supported: {supported}")
    try:
        samples, samplerate = sf.read(str(path), dtype="float32", always_2d=True)
    except (sf.LibsndfileError, RuntimeError) as error:
        raise AudioLoadError(f"Could not decode {path.name}: {error}") from error
    if samples.shape[0] == 0:
        raise AudioLoadError(f"{path.name} contains no audio")
    return AudioData(samples=samples, samplerate=samplerate)


def file_sha256(path: Path) -> str:
    """Return the file's SHA-256, used as the identity of an input song."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def to_mono(samples: np.ndarray) -> np.ndarray:
    """Downmix ``(frames, channels)`` audio. One-dimensional input passes through."""
    return samples if samples.ndim == 1 else samples.mean(axis=1)


def resample(samples: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    """Resample along the time axis; returns the input when the rates match."""
    if from_rate == to_rate:
        return samples
    return librosa.resample(
        samples, orig_sr=from_rate, target_sr=to_rate, res_type="soxr_hq", axis=0
    )


def analysis_mono(samples: np.ndarray, samplerate: int) -> np.ndarray:
    """Return mono audio at :data:`ANALYSIS_SAMPLERATE`."""
    return resample(to_mono(samples), samplerate, ANALYSIS_SAMPLERATE)
