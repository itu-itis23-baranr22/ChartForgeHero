"""Reduces Expert drums to Hard, Medium and Easy, and holds every level to the hard rules.

The hard rules live here, in code, and ``drum_difficulty.toml`` cannot loosen them:

- Each level is made of the positions and gems of the level above. A kick stays a kick and a cymbal
  a cymbal; a gem is only ever left out.
- No position holds more than two pads, on any level.
- Hard and Medium hold at most two gems at once. Easy never has the kick together with a pad.
- Medium and Easy have nothing on a sixteenth.
- No drum note has a sustain. Nothing lands in an opening that is not part of the song, because
  every level comes from Expert, which keeps to that. The result is deterministic.

The file only decides what is worth keeping: which gem gives way first, how much of Expert each level
aims for, and how far apart its positions are. It was set from the one human drum chart we have.
"""

from __future__ import annotations

import math
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np

from chartgen.chart.difficulty import (
    REDUCED_LEVELS,
    HardRuleViolation,
    SoftTargetResult,
    metric_levels,
    nearest_sixteenth,
    select_positions,
)
from chartgen.core.drums import DrumGem
from chartgen.core.model import Difficulty, Instrument, Track
from chartgen.core.timing import TempoMap

CONFIG_PATH = Path(__file__).with_name("drum_difficulty.toml")

MAX_PADS = 2
"""Two hands, on every level. The kick is the foot and comes on top."""
MAX_GEMS: Mapping[Difficulty, int] = {Difficulty.HARD: 2, Difficulty.MEDIUM: 2}
NO_KICK_WITH_A_PAD = frozenset({Difficulty.EASY})
NO_SIXTEENTHS = frozenset({Difficulty.MEDIUM, Difficulty.EASY})

LEVEL_HARD_RULES = (
    "drums: each level is made of the positions and gems of the level above, a kick stays a kick "
    "and a cymbal a cymbal",
    "drums: Hard and Medium have at most two gems at once, Easy never the kick with a pad",
    "drums: Medium and Easy have nothing on a sixteenth",
)
"""Listed in ``analysis.json`` with the rules every level keeps."""

_METRIC_NAMES = ("downbeat", "strong_beat", "beat", "eighth", "sixteenth")
_SOFT_TARGET_NAMES = frozenset(
    {"position_ratio", "gems_per_position", "on_beat_share", "sixteenth_share", "min_gap_beats", "min_gap_s"}
)


# ---------------------------------------------------------------- settings


@dataclass(frozen=True)
class DrumImportance:
    """Weights of a position's score."""

    downbeat: float
    strong_beat: float
    beat: float
    eighth: float
    sixteenth: float
    hit_strength: float


@dataclass(frozen=True)
class DrumSoftTargets:
    """What a level aims for. Missing any of it only warns."""

    ranges: Mapping[str, tuple[float, float]]
    """A low and a high limit for a value of :class:`DrumLevelMeasures`."""
    gem_shares: Mapping[DrumGem, float]
    """The share of each gem in the human chart measured so far."""
    gem_tolerance: float


@dataclass(frozen=True)
class DrumLevelConfig:
    position_ratio: float
    min_gap_beats: float
    gem_weights: Mapping[DrumGem, float]
    second_gem_from: frozenset[DrumGem]
    """Which gems may join the first one at a position. Every gem, unless the level says otherwise."""
    soft_targets: DrumSoftTargets
    min_gap_s: float = 0.0
    """Positions are also never closer than this in seconds, however many beats apart: in a fast song
    the beat rule alone would let through what a player cannot keep up with."""
    lone_kick_share: float = 1.0
    """The share of the level above's lone kicks (positions holding only the kick) that may stay, the best
    by score; the rest are no candidates. A preference, not a hard rule: 1.0 keeps them all. A lower score
    alone does not do it, since the gap rule often leaves a lone kick alone in its slot."""


@dataclass(frozen=True)
class DrumDifficultyConfig:
    gem_order: tuple[DrumGem, ...]
    """The first gives way last."""
    protect_backbeat_snare: bool
    importance: DrumImportance
    levels: Mapping[Difficulty, DrumLevelConfig]


def _gem(name: object, where: str) -> DrumGem:
    try:
        return DrumGem(str(name))
    except ValueError:
        raise ValueError(f"{where}: unknown gem {name!r}, expected one of {[gem.value for gem in DrumGem]}") from None


def _range(name: str, value: object, where: str) -> tuple[float, float]:
    low, high = (float(item) for item in value)  # type: ignore[attr-defined]
    if low > high:
        raise ValueError(f"{where}: soft target {name} needs [low, high]")
    return low, high


def _load_level(name: str, level: Difficulty, values: Mapping[str, object], tolerance: float, file: str) -> DrumLevelConfig:
    where = f"{file} [{name}]"
    values = dict(values)
    known = {
        "position_ratio", "min_gap_beats", "min_gap_s", "gem_weights", "gem_shares", "soft_targets", "second_gem_from",
        "lone_kick_share",
    }
    unknown = set(values) - known
    if unknown:
        raise ValueError(f"{where}: unknown keys {sorted(unknown)}; the hard rules are not settings")
    missing = {"position_ratio", "min_gap_beats"} - set(values)
    if missing:
        raise ValueError(f"{where}: missing {sorted(missing)}")
    ratio, gap = float(values["position_ratio"]), float(values["min_gap_beats"])  # type: ignore[arg-type]
    floor = float(values.get("min_gap_s", 0.0))  # type: ignore[arg-type]
    if not 0 < ratio <= 1 or gap < 0 or floor < 0:
        raise ValueError(f"{where}: position_ratio must be in (0, 1], min_gap_beats and min_gap_s not negative")
    lone_kicks = float(values.get("lone_kick_share", 1.0))  # type: ignore[arg-type]
    if not 0 <= lone_kicks <= 1:
        raise ValueError(f"{where}: lone_kick_share must be from 0 to 1")
    weights = {_gem(gem, where): float(weight) for gem, weight in dict(values.get("gem_weights", {})).items()}  # type: ignore[call-overload]
    second = frozenset(_gem(gem, where) for gem in values.get("second_gem_from", [gem.value for gem in DrumGem]))  # type: ignore[union-attr]
    if level in NO_KICK_WITH_A_PAD and DrumGem.KICK in second:
        raise ValueError(f"{where}: the kick cannot join a pad on {level.value}, that is a hard rule")
    shares = {_gem(gem, where): float(share) for gem, share in dict(values.get("gem_shares", {})).items()}  # type: ignore[call-overload]
    if shares and (set(shares) != set(DrumGem) or abs(sum(shares.values()) - 1) > 0.02):
        raise ValueError(f"{where}: gem_shares needs every gem, adding up to one")
    ranges = {key: _range(key, value, where) for key, value in dict(values.get("soft_targets", {})).items()}  # type: ignore[call-overload]
    unknown_targets = set(ranges) - _SOFT_TARGET_NAMES
    if unknown_targets:
        raise ValueError(f"{where}: unknown soft targets {sorted(unknown_targets)}")
    return DrumLevelConfig(ratio, gap, weights, second, DrumSoftTargets(ranges, shares, tolerance), floor, lone_kicks)


def load_drum_config(path: Path = CONFIG_PATH) -> DrumDifficultyConfig:
    """Read the drum reduction settings.

    Raises:
        ValueError: If a value is missing, unknown or out of range, or would decide a hard rule.
    """
    with path.open("rb") as stream:
        values = tomllib.load(stream)
    expected = {"gem_order", "protect_backbeat_snare", "gem_tolerance", "importance", *(level.value for level in REDUCED_LEVELS)}
    if set(values) != expected:
        raise ValueError(f"{path.name}: expected keys {sorted(expected)}, got {sorted(values)}")
    order = tuple(_gem(gem, f"{path.name} gem_order") for gem in values["gem_order"])
    if sorted(order, key=lambda gem: gem.value) != sorted(DrumGem, key=lambda gem: gem.value):
        raise ValueError(f"{path.name}: gem_order must list every gem once")
    importance = dict(values["importance"])
    names = {item.name for item in fields(DrumImportance)}
    if set(importance) != names:
        raise ValueError(f"{path.name} [importance]: expected keys {sorted(names)}, got {sorted(importance)}")
    if any(float(weight) < 0 for weight in importance.values()):
        raise ValueError(f"{path.name} [importance]: weights must not be negative")
    tolerance = float(values["gem_tolerance"])
    if tolerance < 0:
        raise ValueError(f"{path.name}: gem_tolerance must not be negative")
    levels = {
        level: _load_level(level.value, level, values[level.value], tolerance, path.name) for level in REDUCED_LEVELS
    }
    ratios = [levels[level].position_ratio for level in REDUCED_LEVELS]
    if ratios != sorted(ratios, reverse=True):
        raise ValueError(f"{path.name}: position_ratio must fall from Hard to Easy")
    return DrumDifficultyConfig(
        order,
        bool(values["protect_backbeat_snare"]),
        DrumImportance(**{key: float(value) for key, value in importance.items()}),
        levels,
    )


# ---------------------------------------------------------------- measures


@dataclass(frozen=True)
class DrumLevelMeasures:
    """Plain numbers about one drum level, the same for a generated chart and a human one."""

    positions: int
    position_ratio: float
    gems_per_position: float
    on_beat_share: float
    sixteenth_share: float
    min_gap_beats: float
    min_gap_s: float
    gem_shares: Mapping[str, float]
    """Every kind of gem, in :class:`DrumGem` order."""


def measure_positions(
    positions: Mapping[int, Sequence[DrumGem]], tempo_map: TempoMap, expert_positions: int
) -> DrumLevelMeasures:
    """Measure a level from its gems by tick."""
    ticks = np.array(sorted(positions), dtype=np.int64)
    gems = [gem for tick in ticks for gem in positions[int(tick)]]
    counts = {gem: 0 for gem in DrumGem}
    for gem in gems:
        counts[gem] += 1
    shares = {gem.value: round(counts[gem] / max(1, len(gems)), 3) for gem in DrumGem}
    if ticks.size == 0:
        return DrumLevelMeasures(0, 0.0, 0.0, 0.0, 0.0, math.inf, math.inf, shares)
    resolution = tempo_map.resolution
    rounded = nearest_sixteenth(ticks.astype(np.float64), resolution)
    times = tempo_map.seconds_at(ticks.astype(np.float64))
    return DrumLevelMeasures(
        int(ticks.size),
        round(ticks.size / max(1, expert_positions), 3),
        round(len(gems) / ticks.size, 3),
        round(float(np.mean(rounded % resolution == 0)), 3),
        round(float(np.mean(rounded % (resolution // 2) != 0)), 3),
        round(float(np.diff(ticks).min() / resolution), 3) if ticks.size > 1 else math.inf,
        round(float(np.diff(times).min()), 3) if ticks.size > 1 else math.inf,
        shares,
    )


def gems_by_tick(track: Track) -> dict[int, tuple[DrumGem, ...]]:
    """A drum track's gems by tick, each tick's in lane order."""
    by_tick: dict[int, list[DrumGem]] = {}
    for note in track.notes:
        by_tick.setdefault(note.tick, []).append(DrumGem.of_note(note))
    return {tick: tuple(sorted(gems, key=lambda gem: (gem.lane, gem.cymbal))) for tick, gems in sorted(by_tick.items())}


def check_drum_soft_targets(measures: DrumLevelMeasures, targets: DrumSoftTargets) -> list[SoftTargetResult]:
    """Compare a level with its soft targets. Being outside only ever warns."""
    results = [
        SoftTargetResult(name, float(getattr(measures, name)), low, high) for name, (low, high) in targets.ranges.items()
    ]
    for gem, share in targets.gem_shares.items():
        results.append(
            SoftTargetResult(
                f"{gem.value}_share",
                float(measures.gem_shares[gem.value]),
                round(max(share - targets.gem_tolerance, 0.0), 3),
                round(min(share + targets.gem_tolerance, 1.0), 3),
            )
        )
    return results


# ---------------------------------------------------------------- hard rules


def _on_a_sixteenth(tick: int, resolution: int) -> bool:
    """Whether the nearest sixteenth lies between two eighths, as the validator counts it."""
    return round(tick / (resolution / 4)) % 2 == 1


def check_drum_levels(levels: Mapping[Difficulty, Track], resolution: int) -> None:
    """Hold the drum levels to every hard rule, together and one by one.

    Raises:
        HardRuleViolation: On the first rule a level breaks.
    """
    order = [level for level in Difficulty if level in levels]
    by_level: dict[Difficulty, dict[int, tuple[DrumGem, ...]]] = {}
    for level in order:
        try:
            by_level[level] = gems_by_tick(levels[level])
        except ValueError as error:
            raise HardRuleViolation(f"drums/{level.value}: {error}") from error
    for level in order:
        name = f"drums/{level.value}"
        for tick, gems in by_level[level].items():
            pads = sum(gem.is_pad for gem in gems)
            if pads > MAX_PADS:
                raise HardRuleViolation(f"{name}: {pads} pads at once at tick {tick}")
            if level in MAX_GEMS and len(gems) > MAX_GEMS[level]:
                raise HardRuleViolation(f"{name}: {len(gems)} gems at once at tick {tick}")
            if level in NO_KICK_WITH_A_PAD and pads and DrumGem.KICK in gems:
                raise HardRuleViolation(f"{name}: the kick with a pad at tick {tick}")
            if level in NO_SIXTEENTHS and _on_a_sixteenth(tick, resolution):
                raise HardRuleViolation(f"{name}: a sixteenth at tick {tick}")
    for upper, lower in zip(order, order[1:]):
        for tick, gems in by_level[lower].items():
            above = by_level[upper].get(tick)
            if above is None:
                raise HardRuleViolation(f"drums/{lower.value}: tick {tick} is not in {upper.value}")
            if not set(gems) <= set(above):
                raise HardRuleViolation(f"drums/{lower.value}: tick {tick} has a gem that {upper.value} does not")


# ---------------------------------------------------------------- reduction


def _gems_for(level: Difficulty, gems: Sequence[DrumGem], config: DrumDifficultyConfig) -> tuple[DrumGem, ...]:
    """The gems of one position on ``level``: the first by ``gem_order`` and what may join it."""
    rank = {gem: index for index, gem in enumerate(config.gem_order)}
    ordered = sorted(gems, key=rank.__getitem__)
    allowed = config.levels[level].second_gem_from
    limit = MAX_GEMS.get(level, 2)
    kept = [ordered[0]]
    for gem in ordered[1:]:
        if len(kept) >= limit:
            break
        if gem not in allowed:
            continue
        if level in NO_KICK_WITH_A_PAD and (gem is DrumGem.KICK or DrumGem.KICK in kept):
            continue
        if gem.is_pad and sum(item.is_pad for item in kept) >= MAX_PADS:
            continue
        kept.append(gem)
    return tuple(sorted(kept, key=lambda gem: (gem.lane, gem.cymbal)))


def _keep_lone_kicks(
    ticks: np.ndarray, scores: np.ndarray, metric: list[str], upper: Mapping[int, tuple[DrumGem, ...]], share: float
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Leave only the best ``share`` of the level above's lone kicks among the candidates, by score.

    The human charts of train keep 46% of Expert's lone kicks on Hard and 2% on Medium and Easy.
    """
    lone = np.array([tuple(upper[int(tick)]) == (DrumGem.KICK,) for tick in ticks], dtype=bool)
    if share >= 1.0 or not lone.any():
        return ticks, scores, metric
    best_first = np.flatnonzero(lone)[np.argsort(-scores[lone], kind="stable")]
    keep = set(best_first[: int(round(share * best_first.size))].tolist())
    stay = np.array([not lone[index] or index in keep for index in range(ticks.size)], dtype=bool)
    return ticks[stay], scores[stay], [name for name, kept in zip(metric, stay) if kept]


def _percentile_ranks(values: np.ndarray) -> np.ndarray:
    if values.size < 2:
        return np.ones(values.size)
    return np.searchsorted(np.sort(values), values, side="left") / (values.size - 1)


@dataclass(frozen=True)
class ReducedDrumLevel:
    track: Track
    measures: DrumLevelMeasures
    soft_targets: tuple[SoftTargetResult, ...]
    protected: int
    """Positions kept whatever the target said: the snare on beats 2 and 4."""


def reduce_drums(
    expert: Track,
    tempo_map: TempoMap,
    strengths: Mapping[int, float] | None = None,
    config: DrumDifficultyConfig | None = None,
) -> dict[Difficulty, ReducedDrumLevel]:
    """Make Hard, Medium and Easy from an Expert drum track, each from the level above.

    Args:
        strengths: How hard each Expert tick was struck, on any scale; only their order counts.

    Raises:
        HardRuleViolation: If a level breaks a hard rule, which would be a bug.
    """
    config = config or load_drum_config()
    strengths = strengths or {}
    resolution = tempo_map.resolution
    upper = gems_by_tick(expert)
    expert_count = len(upper)
    weights = config.importance
    reduced: dict[Difficulty, ReducedDrumLevel] = {}
    tracks: dict[Difficulty, Track] = {Difficulty.EXPERT: expert}
    for level in REDUCED_LEVELS:
        settings = config.levels[level]
        candidates = {
            tick: _gems_for(level, gems, config)
            for tick, gems in upper.items()
            if not (level in NO_SIXTEENTHS and _on_a_sixteenth(tick, resolution))
        }
        ticks = np.array(sorted(candidates), dtype=np.int64)
        metric = metric_levels(ticks.tolist(), tempo_map) if ticks.size else []
        rank = {gem: index for index, gem in enumerate(config.gem_order)}
        scores = np.array([getattr(weights, name) for name in metric], dtype=np.float64)
        scores += weights.hit_strength * _percentile_ranks(
            np.array([strengths.get(int(tick), 0.0) for tick in ticks], dtype=np.float64)
        )
        scores += np.array(
            [settings.gem_weights.get(min(candidates[int(tick)], key=rank.__getitem__), 0.0) for tick in ticks]
        )
        ticks, scores, metric = _keep_lone_kicks(ticks, scores, metric, upper, settings.lone_kick_share)
        protected = np.array(
            [
                config.protect_backbeat_snare and name == "beat" and DrumGem.RED in candidates[int(tick)]
                for tick, name in zip(ticks, metric)
            ],
            dtype=bool,
        )
        target = min(ticks.size, round(settings.position_ratio * expert_count))
        gap = round(settings.min_gap_beats * resolution)
        times = tempo_map.seconds_at(ticks.astype(np.float64)) if ticks.size else ticks.astype(np.float64)
        floor = settings.min_gap_s
        # A flam puts two snares next to one beat. Only the better of them is protected, so the
        # protected ones keep the gap too.
        backbeats = select_positions(
            np.flatnonzero(protected), times, scores, np.zeros(ticks.size, dtype=bool), ticks.size, math.inf, ticks, gap,
            floor,
        )
        protected = np.zeros(ticks.size, dtype=bool)
        protected[backbeats] = True
        chosen = select_positions(
            np.arange(ticks.size), times, scores, protected, target, math.inf, ticks=ticks, min_gap_ticks=gap,
            floor_s=floor,
        )
        kept = {int(ticks[index]): candidates[int(ticks[index])] for index in chosen}
        notes = [gem.note(tick) for tick, gems in kept.items() for gem in gems]
        track = Track(Instrument.DRUMS, level, notes)
        tracks[level] = track
        measures = measure_positions(kept, tempo_map, expert_count)
        reduced[level] = ReducedDrumLevel(
            track,
            measures,
            tuple(check_drum_soft_targets(measures, settings.soft_targets)),
            int(protected[chosen].sum()) if chosen.size else 0,
        )
        upper = kept
    check_drum_levels(tracks, resolution)
    return reduced
