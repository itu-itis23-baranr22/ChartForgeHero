"""Keeping the singer out of the guitar chart.

Stem separation is imperfect: quiet traces of the vocals reach the guitar stem, and their
consonants look like note attacks. Each note is compared with the vocals at the same moment,
and removed if it looks like such a trace. Thresholds live in ``vocal_bleed.toml``.
"""

from __future__ import annotations

import tomllib
from collections.abc import Sequence
from dataclasses import dataclass, fields
from pathlib import Path

import librosa
import numpy as np

from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.onsets import HOP_LENGTH, N_FFT

THRESHOLDS_PATH = Path(__file__).with_name("vocal_bleed.toml")
_FLOOR = 1e-6


@dataclass(frozen=True)
class BleedThresholds:
    min_vocal_over_stem_db: float
    max_stem_level_db: float
    max_stem_sustain: float
    level_window_s: float
    sustain_start_s: float
    sustain_end_s: float
    warn_removed_share: float
    """Removing more than this share of a stem's notes is reported as a warning; it removes nothing."""

    def removes_too_many(self, notes: Sequence[NoteBleed]) -> bool:
        """Whether ``notes``, every note the filter judged, lost more than ``warn_removed_share``."""
        return bool(notes) and removed_share(notes) > self.warn_removed_share


def removed_share(notes: Sequence[NoteBleed]) -> float:
    """The share of the judged notes that the filter removed."""
    return sum(note.removed for note in notes) / len(notes) if notes else 0.0


def load_thresholds(path: Path = THRESHOLDS_PATH) -> BleedThresholds:
    """Read the thresholds file.

    Raises:
        ValueError: If a value is missing, unknown or out of range.
    """
    with path.open("rb") as stream:
        values = tomllib.load(stream)
    expected = {field.name for field in fields(BleedThresholds)}
    if set(values) != expected:
        raise ValueError(f"{path.name}: expected keys {sorted(expected)}, got {sorted(values)}")
    if values["max_stem_sustain"] < 0 or values["level_window_s"] <= 0:
        raise ValueError(f"{path.name}: max_stem_sustain and level_window_s are out of range")
    if not 0 <= values["sustain_start_s"] < values["sustain_end_s"]:
        raise ValueError(f"{path.name}: sustain_start_s must come before sustain_end_s")
    if not 0 < values["warn_removed_share"] <= 1:
        raise ValueError(f"{path.name}: warn_removed_share must be above 0 and at most 1")
    return BleedThresholds(**{key: float(value) for key, value in values.items()})


@dataclass(frozen=True)
class NoteBleed:
    """How one note compares with the vocals at the same moment."""

    time_s: float
    vocal_over_stem_db: float
    stem_level_db: float
    """Relative to the stem's usual loud level."""
    stem_sustain: float
    """The stem's level just after the note, as a share of its usual loud level."""
    removed: bool

    @property
    def vocal_dominant(self) -> bool:
        return self.vocal_over_stem_db > 0

    def reason(self) -> str:
        return (
            f"vocals {self.vocal_over_stem_db:.1f} dB over a stem {-self.stem_level_db:.1f} dB "
            f"below its usual level, keeping {self.stem_sustain:.0%} of it afterwards"
        )


def analyze_bleed(
    stem: np.ndarray,
    vocals: np.ndarray,
    times: np.ndarray,
    next_times: np.ndarray,
    samplerate: int = ANALYSIS_SAMPLERATE,
    thresholds: BleedThresholds | None = None,
) -> list[NoteBleed]:
    """Compare every note of ``stem`` with ``vocals`` and mark those that look like a leak.

    Args:
        stem: The stem the notes were found on.
        vocals: The vocal stem, at the same sample rate.
        times: Note start times.
        next_times: When each note is cut off by the next one.
        samplerate: Sample rate of both signals.
        thresholds: Limits; by default those in ``vocal_bleed.toml``.
    """
    limits = thresholds or load_thresholds()
    if times.size == 0:
        return []
    stem_rms = librosa.feature.rms(y=stem, frame_length=N_FFT, hop_length=HOP_LENGTH)[0]
    vocal_rms = librosa.feature.rms(y=vocals, frame_length=N_FFT, hop_length=HOP_LENGTH)[0]
    frames = min(stem_rms.size, vocal_rms.size)
    stem_rms, vocal_rms = stem_rms[:frames], vocal_rms[:frames]
    usual = max(float(np.percentile(stem_rms, 95)), _FLOOR)
    per_second = samplerate / HOP_LENGTH

    results: list[NoteBleed] = []
    for time, next_time in zip(times, next_times):
        first = min(int(time * per_second), frames - 1)
        end_time = max(min(time + limits.level_window_s, next_time), time + 0.05)
        last = max(first + 1, min(frames, int(end_time * per_second)))
        stem_level = float(stem_rms[first:last].mean())
        vocal_level = float(vocal_rms[first:last].mean())
        over = 20.0 * np.log10((vocal_level + _FLOOR) / (stem_level + _FLOOR))
        relative = 20.0 * np.log10((stem_level + _FLOOR) / usual)

        after_first = min(frames - 1, first + int(limits.sustain_start_s * per_second))
        after_last = max(after_first + 1, min(frames, first + int(limits.sustain_end_s * per_second)))
        sustain = float(stem_rms[after_first:after_last].mean()) / usual

        removed = (
            over >= limits.min_vocal_over_stem_db
            and relative <= limits.max_stem_level_db
            and sustain <= limits.max_stem_sustain
        )
        results.append(NoteBleed(float(time), float(over), float(relative), sustain, bool(removed)))
    return results
