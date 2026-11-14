"""Where star power goes (decision 40, step D.3).

Every charted instrument gets star power phrases one bar long, about every 25 seconds, and the same
phrases on all four of its levels, as Californication's human chart has them. The first phrase comes
about 15 seconds after the song starts; each next one in the bar closest to 25 seconds after the last,
within 20 to 30 seconds, among the bars that hold a note on every level. Bars with at least two notes on
the easiest level come first. Each instrument is placed on its own notes.

Hard rules, here in code (``check_star_power``) and in the validator: a phrase starts on a bar line,
phrases do not overlap, every phrase holds a note on every level, and no phrase starts before the song
does (``Song`` after an opening). ``star_power.toml`` chooses where phrases go and cannot loosen these.

Drums get no activation fills (``S 64``). How the game activates drum star power without them was not
checked in the game (D.3, 2026-11-15): the bot never activates star power and shows no meter.
"""

from __future__ import annotations

import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from chartgen.core.model import Difficulty, Instrument, StarPowerPhrase, Track
from chartgen.core.timing import TempoMap

CONFIG_PATH = Path(__file__).with_name("star_power.toml")
DRUM_ACTIVATION_NOT_VERIFIED = (
    "drums: no activation fills (S 64) are written; how the game activates drum star power without them "
    "was not checked in the game"
)
HARD_RULES = (
    "a phrase starts on a bar line",
    "phrases do not overlap",
    "every phrase holds a note on every level of its instrument",
    "no phrase starts before the song does",
)


class StarPowerRuleViolation(ValueError):
    """Placed star power broke a hard rule: a bug, never a matter of settings."""


@dataclass(frozen=True)
class StarPowerConfig:
    bars: int
    first_after_s: float
    gap_s: float
    min_gap_s: float
    max_gap_s: float
    preferred_notes_on_easiest: int
    per_minute: tuple[float, float]


def _take(values: dict, keys: set[str], where: str) -> dict:
    if set(values) != keys:
        raise ValueError(f"{where}: expected keys {sorted(keys)}, got {sorted(values)}")
    return values


def load_star_power_config(path: Path = CONFIG_PATH) -> StarPowerConfig:
    """Read the star power settings.

    Raises:
        ValueError: If a value is missing, unknown or out of range.
    """
    with path.open("rb") as stream:
        values = tomllib.load(stream)
    _take(values, {"phrases", "soft_targets"}, path.name)
    phrases = _take(
        dict(values["phrases"]),
        {"bars", "first_after_s", "gap_s", "min_gap_s", "max_gap_s", "preferred_notes_on_easiest"},
        f"{path.name} [phrases]",
    )
    soft = _take(dict(values["soft_targets"]), {"per_minute"}, f"{path.name} [soft_targets]")
    bars = int(phrases["bars"])
    if bars < 1 or bars != phrases["bars"]:
        raise ValueError(f"{path.name} [phrases]: bars must be a whole number of at least 1")
    first, gap = float(phrases["first_after_s"]), float(phrases["gap_s"])
    low, high = float(phrases["min_gap_s"]), float(phrases["max_gap_s"])
    if first < 0 or not 0 < low <= gap <= high:
        raise ValueError(f"{path.name} [phrases]: needs first_after_s >= 0 and 0 < min_gap_s <= gap_s <= max_gap_s")
    preferred = int(phrases["preferred_notes_on_easiest"])
    if preferred < 1:
        raise ValueError(f"{path.name} [phrases]: preferred_notes_on_easiest must be at least 1")
    per_minute = tuple(float(value) for value in soft["per_minute"])
    if len(per_minute) != 2 or not 0 <= per_minute[0] < per_minute[1]:
        raise ValueError(f"{path.name} [soft_targets]: per_minute must be [low, high] with low < high")
    return StarPowerConfig(bars, first, gap, low, high, preferred, (per_minute[0], per_minute[1]))


@dataclass(frozen=True)
class PlacedPhrase:
    tick: int
    length: int
    start_s: float
    end_s: float
    notes: tuple[int, ...]
    """Positions inside the phrase on each level, in the order of the tracks given."""


@dataclass(frozen=True)
class StarPowerPlan:
    """The star power of one instrument: the same phrases on every level."""

    instrument: Instrument
    levels: tuple[Difficulty, ...]
    phrases: tuple[PlacedPhrase, ...]
    duration_s: float
    config: StarPowerConfig

    @property
    def gaps_s(self) -> list[float]:
        starts = [phrase.start_s for phrase in self.phrases]
        return [later - earlier for earlier, later in zip(starts, starts[1:])]

    @property
    def per_minute(self) -> float | None:
        return len(self.phrases) / (self.duration_s / 60.0) if self.duration_s > 0 else None

    def star_power_phrases(self) -> list[StarPowerPhrase]:
        return [StarPowerPhrase(phrase.tick, phrase.length) for phrase in self.phrases]

    def soft_warnings(self) -> list[str]:
        """What falls outside the soft targets. Never a reason to fail a build."""
        name = self.instrument.value
        if not self.phrases:
            return [f"star power: {name}: no bar after the song starts holds a note on every level, so no phrases"]
        warnings = []
        low, high = self.config.per_minute
        if self.per_minute is not None and not low <= self.per_minute <= high:
            warnings.append(
                f"star power: {name}: {len(self.phrases)} phrases, {self.per_minute:.1f} per minute "
                f"(wanted {low:g} to {high:g})"
            )
        long_gaps = [gap for gap in self.gaps_s if gap > self.config.max_gap_s + 1e-6]
        if long_gaps:
            gaps = "1 gap" if len(long_gaps) == 1 else f"{len(long_gaps)} gaps"
            warnings.append(
                f"star power: {name}: {gaps} longer than {self.config.max_gap_s:g} s "
                f"(longest {max(long_gaps):.1f} s): no bar in between held a note on every level"
            )
        sparse = sum(phrase.notes[-1] < self.config.preferred_notes_on_easiest for phrase in self.phrases)
        if sparse:
            phrases = "1 phrase holds" if sparse == 1 else f"{sparse} phrases hold"
            warnings.append(
                f"star power: {name}: {phrases} fewer than {self.config.preferred_notes_on_easiest} "
                f"notes on {self.levels[-1].value.title()}"
            )
        return warnings

    def as_dict(self) -> dict[str, object]:
        gaps = self.gaps_s
        return {
            "phrases": [
                {
                    "tick": phrase.tick,
                    "length_ticks": phrase.length,
                    "start_s": round(phrase.start_s, 3),
                    "end_s": round(phrase.end_s, 3),
                    "notes_inside": {level.value: count for level, count in zip(self.levels, phrase.notes)},
                }
                for phrase in self.phrases
            ],
            "count": len(self.phrases),
            "per_minute": None if self.per_minute is None else round(self.per_minute, 2),
            "median_gap_s": round(float(np.median(gaps)), 1) if gaps else None,
            "shortest_gap_s": round(min(gaps), 1) if gaps else None,
            "longest_gap_s": round(max(gaps), 1) if gaps else None,
            "bars_per_phrase": self.config.bars,
        }


def _positions(track: Track) -> np.ndarray:
    return np.array(sorted({note.tick for note in track.notes}), dtype=np.int64)


def _inside(positions: np.ndarray, start: int, end: int) -> int:
    return int(np.searchsorted(positions, end, side="left") - np.searchsorted(positions, start, side="left"))


def place_star_power(
    tracks: Sequence[Track],
    tempo_map: TempoMap,
    duration_s: float,
    song_start_tick: int = 0,
    config: StarPowerConfig | None = None,
) -> StarPowerPlan:
    """Choose the star power phrases of one instrument, the same on each of its levels.

    Args:
        tracks: Every level of one instrument, the hardest first.
        duration_s: Of the song; a phrase ends at a bar line within it.
        song_start_tick: Where the song starts after an opening that is not part of it (the ``Song``
            section), 0 without one. No phrase starts before it.
    """
    config = config or load_star_power_config()
    if not tracks:
        raise ValueError("star power needs at least one track")
    instrument = tracks[0].instrument
    if any(track.instrument is not instrument for track in tracks):
        raise ValueError("star power is placed one instrument at a time")
    levels = tuple(track.difficulty for track in tracks)
    positions = [_positions(track) for track in tracks]
    bars = tempo_map.bar_lines(duration_s)
    times = tempo_map.seconds_at(bars.astype(np.float64)) if bars.size else np.empty(0)

    candidates: list[tuple[int, int, float, float, tuple[int, ...]]] = []
    for index in range(bars.size - config.bars):
        start, end = int(bars[index]), int(bars[index + config.bars])
        if start < song_start_tick:
            continue
        notes = tuple(_inside(level, start, end) for level in positions)
        if min(notes) >= 1:
            candidates.append((start, end, float(times[index]), float(times[index + config.bars]), notes))

    def preference(candidate, target_s: float) -> tuple[bool, float, float]:
        return candidate[4][-1] < config.preferred_notes_on_easiest, abs(candidate[2] - target_s), candidate[2]

    chosen: list[tuple[int, int, float, float, tuple[int, ...]]] = []
    song_start_s = float(tempo_map.seconds_at(float(song_start_tick)))
    target = song_start_s + config.first_after_s
    low, high = song_start_s, target + (config.max_gap_s - config.gap_s)
    while True:
        window = [item for item in candidates if low - 1e-6 <= item[2] <= high + 1e-6]
        if window:
            pick = min(window, key=lambda item: preference(item, target))
        else:
            later = [item for item in candidates if item[2] >= low - 1e-6]
            if not later:
                break
            pick = later[0]
        chosen.append(pick)
        target = pick[2] + config.gap_s
        low, high = pick[2] + config.min_gap_s, pick[2] + config.max_gap_s

    plan = StarPowerPlan(
        instrument,
        levels,
        tuple(PlacedPhrase(start, end - start, start_s, end_s, notes) for start, end, start_s, end_s, notes in chosen),
        duration_s,
        config,
    )
    check_star_power(plan.star_power_phrases(), tracks, tempo_map, duration_s, song_start_tick)
    return plan


def check_star_power(
    phrases: Sequence[StarPowerPhrase],
    tracks: Sequence[Track],
    tempo_map: TempoMap,
    duration_s: float,
    song_start_tick: int = 0,
) -> None:
    """Hold one instrument's star power to the hard rules, on every level given.

    Raises:
        StarPowerRuleViolation: On the first rule broken.
    """
    bar_lines = set(tempo_map.bar_lines(duration_s).tolist())
    ordered = sorted(phrases, key=lambda phrase: phrase.tick)
    for phrase in ordered:
        if phrase.tick not in bar_lines:
            raise StarPowerRuleViolation(f"a phrase at tick {phrase.tick} is not on a bar line")
        if phrase.tick < song_start_tick:
            raise StarPowerRuleViolation(
                f"a phrase at tick {phrase.tick} starts before the song does (tick {song_start_tick})"
            )
        for track in tracks:
            if not _inside(_positions(track), phrase.tick, phrase.tick + phrase.length):
                raise StarPowerRuleViolation(
                    f"the phrase at tick {phrase.tick} holds no note on {track.instrument.value}/{track.difficulty.value}"
                )
    for earlier, later in zip(ordered, ordered[1:]):
        if earlier.tick + earlier.length > later.tick:
            raise StarPowerRuleViolation(f"the phrases at ticks {earlier.tick} and {later.tick} overlap")
