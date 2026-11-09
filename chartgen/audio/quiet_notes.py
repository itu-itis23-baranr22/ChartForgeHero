"""Bass notes far quieter than the song's typical bass note.

The kick leaks into the bass stem, and a leak is quiet. So a note far below the song's median bass
note may be no note at all. This is the project owner's rule. Whether it is in force is set in
``quiet_notes.toml``, along with how it measured. Either way, ``analysis.json`` lists the notes it
points at.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np

from chartgen.audio.io import ANALYSIS_SAMPLERATE

LIMITS_PATH = Path(__file__).with_name("quiet_notes.toml")
_WINDOW_S = 0.18
_MIN_WINDOW_S = 0.02
_FLOOR = 1e-6


@dataclass(frozen=True)
class QuietNoteLimits:
    enabled: bool
    below_median_db: float


def load_limits(path: Path = LIMITS_PATH) -> QuietNoteLimits:
    """Read the limits file.

    Raises:
        ValueError: If a value is missing, unknown or out of range.
    """
    with path.open("rb") as stream:
        values = tomllib.load(stream)
    expected = {field.name for field in fields(QuietNoteLimits)}
    if set(values) != expected:
        raise ValueError(f"{path.name}: expected keys {sorted(expected)}, got {sorted(values)}")
    if not isinstance(values["enabled"], bool):
        raise ValueError(f"{path.name}: enabled must be true or false")
    if values["below_median_db"] <= 0:
        raise ValueError(f"{path.name}: below_median_db must be positive")
    return QuietNoteLimits(values["enabled"], float(values["below_median_db"]))


@dataclass(frozen=True)
class QuietNote:
    """A note the rule points at."""

    time_s: float
    below_median_db: float
    removed: bool


def levels_below_median(
    stem: np.ndarray,
    times: np.ndarray,
    next_times: np.ndarray,
    samplerate: int = ANALYSIS_SAMPLERATE,
) -> np.ndarray:
    """Return how many decibels each note lies below the median note of the stem.

    A note's level is its RMS over its first moments, up to when the next note cuts it off. The
    result is negative for a note louder than the median.

    Args:
        stem: The stem the notes were found on.
        times: Note start times.
        next_times: When each note is cut off by the next one.
        samplerate: The stem's sample rate.
    """
    if times.size == 0:
        return np.empty(0)
    levels = np.empty(times.size)
    for index, (time, next_time) in enumerate(zip(times, next_times)):
        first = int(time * samplerate)
        stop = max(first + int(_MIN_WINDOW_S * samplerate), int(min(time + _WINDOW_S, next_time) * samplerate))
        piece = stem[first:stop]
        rms = float(np.sqrt(np.mean(np.square(piece)))) if piece.size else 0.0
        levels[index] = 20.0 * np.log10(max(rms, _FLOOR))
    return float(np.median(levels)) - levels
