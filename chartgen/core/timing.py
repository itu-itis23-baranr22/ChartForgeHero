"""Conversion between musical ticks and audio seconds."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import overload

import numpy as np

DEFAULT_RESOLUTION = 192
"""Ticks per quarter note."""

BPM_DECIMALS = 3
"""Precision kept for tempos, matching the integer BPM x 1000 stored in .chart files."""

FLOOR_BPM = 150.0
"""A rule counted in beats never allows less time than it would at this tempo. Faster songs have short
beats: once a song found at half its tempo has its beat split in two (SPEC 41), half a beat between drum
positions or three quarters of a beat of sustain would come to half the time they used to. At 150 BPM
or slower such a floor changes nothing."""


def seconds_floor(beats: float) -> float:
    """How long ``beats`` last at :data:`FLOOR_BPM`: the least time a rule of that many beats allows."""
    return beats * 60.0 / FLOOR_BPM


@dataclass(frozen=True, slots=True)
class TempoEvent:
    """A tempo that applies from ``tick`` until the next event.

    ``bpm`` is rounded on creation so that timing math always uses exactly the
    value an exporter will write.
    """

    tick: int
    bpm: float

    def __post_init__(self) -> None:
        if self.tick < 0:
            raise ValueError(f"tempo tick must be >= 0, got {self.tick}")
        rounded = round(float(self.bpm), BPM_DECIMALS)
        if rounded <= 0:
            raise ValueError(f"bpm must be > 0, got {self.bpm}")
        object.__setattr__(self, "bpm", rounded)


@dataclass(frozen=True, slots=True)
class TimeSignatureEvent:
    """A time signature that applies from ``tick`` until the next event."""

    tick: int
    numerator: int = 4
    denominator: int = 4

    def __post_init__(self) -> None:
        if self.tick < 0:
            raise ValueError(f"time signature tick must be >= 0, got {self.tick}")
        if self.numerator <= 0:
            raise ValueError(f"numerator must be > 0, got {self.numerator}")
        if self.denominator <= 0 or self.denominator & (self.denominator - 1):
            raise ValueError(f"denominator must be a power of two, got {self.denominator}")


class TempoMap:
    """An immutable, piecewise-constant tempo curve starting at tick 0."""

    def __init__(
        self,
        tempos: Sequence[TempoEvent],
        time_signatures: Sequence[TimeSignatureEvent] | None = None,
        resolution: int = DEFAULT_RESOLUTION,
    ) -> None:
        if resolution <= 0:
            raise ValueError(f"resolution must be > 0, got {resolution}")
        if not tempos:
            raise ValueError("a tempo map needs at least one tempo event")
        _require_increasing_from_zero([event.tick for event in tempos], "tempo")

        signatures = list(time_signatures) if time_signatures else [TimeSignatureEvent(0)]
        _require_increasing_from_zero([event.tick for event in signatures], "time signature")

        self._tempos = tuple(tempos)
        self._time_signatures = tuple(signatures)
        self._resolution = resolution

        self._event_ticks = np.array([event.tick for event in tempos], dtype=np.float64)
        bpms = np.array([event.bpm for event in tempos], dtype=np.float64)
        self._seconds_per_tick = 60.0 / (bpms * resolution)
        tick_spans = np.diff(self._event_ticks)
        self._event_seconds = np.concatenate(
            ([0.0], np.cumsum(tick_spans * self._seconds_per_tick[:-1]))
        )

    @property
    def tempos(self) -> tuple[TempoEvent, ...]:
        return self._tempos

    @property
    def time_signatures(self) -> tuple[TimeSignatureEvent, ...]:
        return self._time_signatures

    @property
    def resolution(self) -> int:
        return self._resolution

    @overload
    def seconds_at(self, ticks: float) -> float: ...
    @overload
    def seconds_at(self, ticks: np.ndarray) -> np.ndarray: ...
    def seconds_at(self, ticks: float | np.ndarray) -> float | np.ndarray:
        """Return the audio time of ``ticks``."""
        values = np.asarray(ticks, dtype=np.float64)
        if np.any(values < 0):
            raise ValueError("ticks must be >= 0")
        index = np.searchsorted(self._event_ticks, values, side="right") - 1
        result = self._event_seconds[index] + (values - self._event_ticks[index]) * (
            self._seconds_per_tick[index]
        )
        return float(result) if result.ndim == 0 else result

    @overload
    def ticks_at(self, seconds: float) -> float: ...
    @overload
    def ticks_at(self, seconds: np.ndarray) -> np.ndarray: ...
    def ticks_at(self, seconds: float | np.ndarray) -> float | np.ndarray:
        """Return the fractional tick position of ``seconds``."""
        values = np.asarray(seconds, dtype=np.float64)
        if np.any(values < 0):
            raise ValueError("seconds must be >= 0")
        index = np.searchsorted(self._event_seconds, values, side="right") - 1
        result = self._event_ticks[index] + (values - self._event_seconds[index]) / (
            self._seconds_per_tick[index]
        )
        return float(result) if result.ndim == 0 else result

    def bar_ticks(self, signature: TimeSignatureEvent) -> float:
        """How many ticks one bar of ``signature`` lasts."""
        return self._resolution * 4 * signature.numerator / signature.denominator

    def bar_lines(self, end_s: float) -> np.ndarray:
        """The tick of every bar line from the start to ``end_s``, each time signature from its own tick."""
        end_tick = float(self.ticks_at(end_s))
        ticks: list[float] = []
        signatures = self._time_signatures
        for index, signature in enumerate(signatures):
            # The next signature starts its own bar line; the end may fall on one.
            stop = min(signatures[index + 1].tick, end_tick + 1e-9) if index + 1 < len(signatures) else end_tick + 1e-9
            ticks.extend(np.arange(signature.tick, stop, self.bar_ticks(signature)).tolist())
        return np.round(np.array(ticks, dtype=np.float64)).astype(np.int64)


def _require_increasing_from_zero(ticks: Sequence[int], kind: str) -> None:
    if ticks[0] != 0:
        raise ValueError(f"the first {kind} event must be at tick 0, got {ticks[0]}")
    if any(later <= earlier for earlier, later in zip(ticks, ticks[1:])):
        raise ValueError(f"{kind} ticks must be strictly increasing")
