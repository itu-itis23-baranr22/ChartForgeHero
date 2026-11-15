"""Reduces an Expert track to Hard, Medium and Easy.

Each level is a subset of the level above it. Which notes stay is decided by how much each one
matters: where it falls in the bar, how hard it is struck, whether it is held, where it sits in its
phrase. It is never "delete every Nth note". The chosen notes then get new frets from the same
Viterbi mapper as Expert, limited to what the level allows.

**The chord rule.** Lanes are read low to high. Hard and Medium keep a chord's lowest two notes, and
Easy keeps its lowest note. The human chart we measured keeps the lowest two in 84% of its reduced
chords, against 16% for lowest plus highest, which would also need shapes like green plus blue that
this project does not allow. The kept notes never change their distance from each other. The chord
may slide along the neck, and that is all Viterbi can do to it.

**Where chords sit.** Humans write wide chords on Expert, such as green, red and blue, whose lowest two
notes sit low. Our analysis mostly hears two voices and writes narrow chords higher up, such as yellow
and blue, with no third note for the rule to drop. So chords have their own ``chord_lane_map``, which
prefers low frets, with a ``chord_fidelity`` weak enough to let the melody move them. A strong one
makes most chords the same shape: note F1 cannot see that, but a player can.

As in the fret mapper, two things are kept strictly apart:

* **Hard rules** are structural and live here, in :func:`check_hard_rules`. No value in the
  configuration can weaken them, and a result that breaks one raises an error.
* **Preferences and soft targets** are in ``difficulty.toml``. Missing a soft target only warns.
"""

from __future__ import annotations

import math
import tomllib
from bisect import bisect_left
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

import numpy as np

from chartgen.chart.fret_mapping import (
    SHAPES,
    FretWeights,
    NoteInput,
    load_weights,
    map_notes,
    phrase_labels,
)
from chartgen.chart.hopo import natural_hopo_ticks, positions_of
from chartgen.core.model import LANE_COUNT, ChartNote, Difficulty, Instrument, Track
from chartgen.core.timing import TempoMap, seconds_floor

CONFIG_PATH = Path(__file__).with_name("difficulty.toml")
BASS_CONFIG_PATH = Path(__file__).with_name("bass_difficulty.toml")

REDUCED_LEVELS = (Difficulty.HARD, Difficulty.MEDIUM, Difficulty.EASY)
"""From the top down: each level is chosen from the one before it."""

ORANGE = 4
LANE_NAMES = ("green", "red", "yellow", "blue", "orange")
_TOP_LANE_LIMIT = {Difficulty.HARD: ORANGE, Difficulty.MEDIUM: ORANGE - 1, Difficulty.EASY: ORANGE - 1}
"""Hard rule: neither Medium nor Easy may ever use orange."""
_CHORD_SIZE_LIMIT = {Difficulty.HARD: 3, Difficulty.MEDIUM: 2, Difficulty.EASY: 1}
"""Hard rule: Medium has chords of at most two notes, and Easy has none."""
_MIN_TOP_LANE = 2
"""Two-note chords span up to two frets, so a level needs at least three frets."""
_WIDEST_CHORD = 3
"""A three-note chord spans up to three frets, so it needs at least four."""
_LONG_PHRASE = 4
"""Hard rule: a phrase with more notes than this keeps at least one on Easy."""

_SOFT_TARGET_NAMES = frozenset(
    {
        "position_ratio",
        "chord_share",
        "orange_share",
        "blue_share",
        "on_beat_share",
        "sixteenth_share",
        "min_gap_s",
        "sustain_share",
        "auto_hopo_share",
        "busiest_lane_share",
    }
)

HARD_RULES = (
    "positions form a chain: Easy, Medium, Hard, Expert, each a subset of the next",
    "Easy has no chords and no orange",
    "Medium has no orange and chords of at most two notes",
    "a sustain never runs into the next note",
    "every phrase of more than four notes keeps at least one note on Easy",
    "bass has no chords on any level",
    "no instrument has a note in an opening that is not part of the song",
)
"""Listed in ``analysis.json``. The result is also deterministic, which the tests check."""

SINGLE_NOTE_INSTRUMENTS = frozenset({Instrument.BASS})
"""Hard rule: the human bass chart we measured has no chord in 918 positions, and our analysis can
hear one where there is none."""


class HardRuleViolation(ValueError):
    """A reduced chart broke a rule that must always hold: a bug, never a matter of settings."""


def check_single_notes(track: Track) -> None:
    """Raise if a track that may only hold single notes has a chord."""
    if track.instrument not in SINGLE_NOTE_INSTRUMENTS:
        return
    seen: set[int] = set()
    for note in track.notes:
        if note.tick in seen:
            raise HardRuleViolation(
                f"{track.instrument.value}/{track.difficulty.value} has a chord at tick {note.tick}"
            )
        seen.add(note.tick)


@dataclass(frozen=True)
class Importance:
    """Weights of the note score."""

    downbeat: float
    strong_beat: float
    beat: float
    eighth: float
    sixteenth: float
    onset_strength: float
    sustain: float
    phrase_end: float


@dataclass(frozen=True)
class SoftTargets:
    """What a level aims for. Missing any of it only warns."""

    ranges: Mapping[str, tuple[float, float]] = field(default_factory=dict)
    """A low and a high limit for a value of :class:`LevelMeasures`."""
    lane_shares: tuple[float, ...] = ()
    """The share of each lane in the human chart measured so far."""
    lane_tolerance: float = 0.0
    """How far each lane's share may stray from ``lane_shares``."""


@dataclass(frozen=True)
class LevelConfig:
    position_ratio: float
    min_gap_s: float
    top_lane: int
    lane_map: tuple[int, int, int, int, int]
    chord_lane_map: tuple[int, int, int, int, int]
    fidelity: float
    chord_fidelity: float
    min_sustain_beats: float
    keep_auto_hopos: bool
    three_note_chords: bool
    importance: Importance
    soft_targets: SoftTargets
    min_gap_beats: float | None = None
    """Notes this many beats apart are far enough apart whatever ``min_gap_s`` says, which keeps a
    fixed gap in seconds from thinning out a fast song. None: only the seconds count."""


@dataclass(frozen=True)
class DifficultyConfig:
    levels: Mapping[Difficulty, LevelConfig]
    expert_targets: SoftTargets = SoftTargets()
    lane_tolerance: float = 0.1
    """Also how far ``chartgen evaluate`` lets a lane stray from the human chart of that song."""
    max_orange_pitch_share: float | None = None
    """More of a level's orange notes than this on one pitch warns. None: orange is not looked at,
    because a guitar's notes have no pitch to read."""


def _load_importance(values: Mapping[str, float], where: str) -> Importance:
    names = {field.name for field in fields(Importance)}
    if set(values) != names:
        raise ValueError(f"{where}: expected keys {sorted(names)}, got {sorted(values)}")
    if any(float(weight) < 0 for weight in values.values()):
        raise ValueError(f"{where}: weights must not be negative")
    return Importance(**values)


def _load_targets(values: dict[str, object], tolerance: float, where: str) -> SoftTargets:
    """Take the soft targets out of a section of the configuration."""
    ranges = values.pop("soft_targets", {})
    unknown = set(ranges) - _SOFT_TARGET_NAMES  # type: ignore[arg-type]
    if unknown:
        raise ValueError(f"{where}: unknown soft targets {sorted(unknown)}")
    for key, value in ranges.items():  # type: ignore[attr-defined]
        if len(value) != 2 or value[0] > value[1]:
            raise ValueError(f"{where}: soft target {key} needs [low, high]")
    lanes = tuple(float(share) for share in values.pop("lane_shares", ()))  # type: ignore[attr-defined]
    if lanes and (
        len(lanes) != LANE_COUNT
        or any(not 0 <= share <= 1 for share in lanes)
        or abs(sum(lanes) - 1) > 0.02
    ):
        raise ValueError(f"{where}: lane_shares needs five shares that add up to one")
    return SoftTargets(
        {key: (float(value[0]), float(value[1])) for key, value in ranges.items()},  # type: ignore[attr-defined]
        lanes,
        tolerance,
    )


def _load_lane_map(values: object, top_lane: int, where: str) -> tuple[int, int, int, int, int]:
    lanes = tuple(int(lane) for lane in values)  # type: ignore[attr-defined]
    if (
        len(lanes) != LANE_COUNT
        or any(not 0 <= lane <= top_lane for lane in lanes)
        or list(lanes) != sorted(lanes)
    ):
        raise ValueError(f"{where} needs five rising frets up to top_lane")
    return lanes  # type: ignore[return-value]


def _load_level(
    name: str,
    level: Difficulty,
    values: dict[str, object],
    shared: Mapping[str, float],
    tolerance: float,
    file_name: str = CONFIG_PATH.name,
) -> LevelConfig:
    values = dict(values)
    where = f"{file_name} [{name}]"
    three_note = bool(values.pop("three_note_chords", False))
    if three_note and level is not Difficulty.HARD:
        raise ValueError(f"{where}: only Hard may keep three-note chords")
    importance = _load_importance({**shared, **values.pop("importance", {})}, where)
    chord_lanes = values.pop("chord_lane_map", values.get("lane_map", ()))
    chord_fidelity = float(values.pop("chord_fidelity", values.get("fidelity", 0.0)))
    min_gap_beats = values.pop("min_gap_beats", None)
    if min_gap_beats is not None and float(min_gap_beats) <= 0:
        raise ValueError(f"{where}: min_gap_beats must be positive")
    targets = _load_targets(values, tolerance, where)
    expected = {
        "position_ratio",
        "min_gap_s",
        "top_lane",
        "lane_map",
        "fidelity",
        "min_sustain_beats",
        "keep_auto_hopos",
    }
    if set(values) != expected:
        raise ValueError(f"{where}: expected keys {sorted(expected)}, got {sorted(values)}")

    top_lane = int(values["top_lane"])
    if not _MIN_TOP_LANE <= top_lane <= _TOP_LANE_LIMIT[level]:
        raise ValueError(
            f"{where}: top_lane must be from {_MIN_TOP_LANE} to {_TOP_LANE_LIMIT[level]}, "
            f"got {top_lane}"
        )
    if three_note and top_lane < _WIDEST_CHORD:
        raise ValueError(f"{where}: three_note_chords needs top_lane of at least {_WIDEST_CHORD}")
    lane_map = _load_lane_map(values["lane_map"], top_lane, f"{where}: lane_map")
    chord_map = _load_lane_map(chord_lanes, top_lane, f"{where}: chord_lane_map")
    ratio, gap, fidelity, min_sustain = (
        float(values["position_ratio"]),
        float(values["min_gap_s"]),
        float(values["fidelity"]),
        float(values["min_sustain_beats"]),
    )
    if not 0 < ratio <= 1 or gap < 0 or fidelity < 0 or chord_fidelity < 0 or min_sustain < 0:
        raise ValueError(
            f"{where}: position_ratio, min_gap_s, fidelity or min_sustain_beats is out of range"
        )
    return LevelConfig(
        ratio,
        gap,
        top_lane,
        lane_map,
        chord_map,
        fidelity,
        chord_fidelity,
        min_sustain,
        bool(values["keep_auto_hopos"]),
        three_note,
        importance,
        targets,
        None if min_gap_beats is None else float(min_gap_beats),
    )


def load_config(path: Path = CONFIG_PATH) -> DifficultyConfig:
    """Read the configuration file.

    Raises:
        ValueError: If a value is missing, unknown, out of range or would weaken a hard rule.
    """
    with path.open("rb") as stream:
        values = tomllib.load(stream)
    orange = dict(values.pop("orange_pitches", {}))
    orange_limit = orange.pop("max_single_pitch_share", None)
    if orange or (orange_limit is not None and not 0 < orange_limit <= 1):
        raise ValueError(f"{path.name} [orange_pitches]: needs max_single_pitch_share from 0 to 1")
    expected = {
        "importance",
        "lane_targets",
        Difficulty.EXPERT.value,
        *(level.value for level in REDUCED_LEVELS),
    }
    if set(values) != expected:
        raise ValueError(f"{path.name}: expected sections {sorted(expected)}, got {sorted(values)}")
    tolerance = float(values["lane_targets"]["tolerance"])
    if tolerance < 0:
        raise ValueError(f"{path.name} [lane_targets]: tolerance must not be negative")
    expert_section = dict(values[Difficulty.EXPERT.value])
    expert_targets = _load_targets(expert_section, tolerance, f"{path.name} [expert]")
    if expert_section:
        raise ValueError(f"{path.name} [expert]: only holds soft targets, got {sorted(expert_section)}")
    levels = {
        level: _load_level(
            level.value, level, values[level.value], values["importance"], tolerance, path.name
        )
        for level in REDUCED_LEVELS
    }
    chain = [levels[level].position_ratio for level in REDUCED_LEVELS]
    if chain != sorted(chain, reverse=True):
        raise ValueError(f"{path.name}: position_ratio must fall from Hard to Easy")
    return DifficultyConfig(
        levels,
        expert_targets,
        tolerance,
        None if orange_limit is None else float(orange_limit),
    )


@dataclass(frozen=True)
class Position:
    """One Expert position and what the reduction may use about it."""

    tick: int
    time_s: float
    shape: tuple[int, ...]
    length: int = 0
    strength: float = 1.0
    pitch: float = float("nan")


# ---------------------------------------------------------------- the chord rule


def reduce_voices(shape: Sequence[int], max_size: int) -> tuple[int, ...]:
    """Return the notes of a chord that a level keeps: its lowest ``max_size`` lanes."""
    return tuple(sorted(shape)[:max_size])


def place_voices(voices: Sequence[int], lane_map: Sequence[int], top_lane: int) -> tuple[int, ...]:
    """Move kept notes to where the level wants them, keeping their distance from each other.

    The lowest note goes where ``lane_map`` sends it, and the chord slides down if it would then
    reach above ``top_lane``.
    """
    low = voices[0]
    span = voices[-1] - low
    start = min(lane_map[low], top_lane - span)
    return tuple(start + voice - low for voice in voices)


def _max_chord_size(level: Difficulty, config: LevelConfig) -> int:
    if level is Difficulty.HARD:
        return 3 if config.three_note_chords else 2
    return _CHORD_SIZE_LIMIT[level]


def _lanes_for(voices: Sequence[int], config: LevelConfig) -> Sequence[int]:
    return config.chord_lane_map if len(voices) > 1 else config.lane_map


def ideal_shape(shape: Sequence[int], level: Difficulty, config: LevelConfig) -> tuple[int, ...]:
    """Apply the chord rule: what an Expert shape becomes on ``level`` if nothing moves it."""
    voices = reduce_voices(shape, _max_chord_size(level, config))
    return place_voices(voices, _lanes_for(voices, config), config.top_lane)


def _slides(voices: Sequence[int], top_lane: int) -> list[tuple[int, ...]]:
    """Every position on the neck of the same notes that a level allows."""
    low = voices[0]
    span = voices[-1] - low
    return [tuple(start + voice - low for voice in voices) for start in range(top_lane - span + 1)]


# ---------------------------------------------------------------- choosing notes


def nearest_sixteenth(ticks: np.ndarray, resolution: int) -> np.ndarray:
    """Round ticks to the sixteenth grid.

    A note too far from the grid to be snapped keeps its exact tick, but it is still a late beat or
    an early eighth rather than a rhythm of its own: on the one human chart we can compare with,
    people keep most of the ones next to a beat and few of the ones next to a sixteenth.
    """
    grid = resolution // 4
    return np.round(ticks / grid).astype(np.int64) * grid


def metric_levels(ticks: Sequence[int], tempo_map: TempoMap) -> list[str]:
    """Name where each tick falls in its bar, using the time signature in force there."""
    signatures = tempo_map.time_signatures
    starts = np.array([signature.tick for signature in signatures])
    rounded = nearest_sixteenth(np.asarray(ticks, dtype=np.float64), tempo_map.resolution)
    names: list[str] = []
    for tick in rounded:
        signature = signatures[max(int(np.searchsorted(starts, tick, side="right")) - 1, 0)]
        beat = tempo_map.resolution * 4 // signature.denominator
        compound = signature.denominator == 8 and signature.numerator % 3 == 0
        pulse = beat * 3 if compound else beat
        bar = beat * signature.numerator
        offset = (int(tick) - signature.tick) % bar
        if offset == 0:
            names.append("downbeat")
        elif bar % (2 * pulse) == 0 and offset == bar // 2:
            names.append("strong_beat")
        elif offset % pulse == 0:
            names.append("beat")
        elif offset % (pulse // (3 if compound else 2)) == 0:
            names.append("eighth")
        else:
            names.append("sixteenth")
    return names


def _percentile_ranks(values: np.ndarray) -> np.ndarray:
    """Return each value's place among the others, from 0 to 1. Ties share a place."""
    if values.size < 2:
        return np.ones(values.size)
    return np.searchsorted(np.sort(values), values, side="left") / (values.size - 1)


def importance_scores(
    positions: Sequence[Position],
    labels: np.ndarray,
    tempo_map: TempoMap,
    weights: Importance,
) -> np.ndarray:
    """Score how much each Expert position matters."""
    metric = metric_levels([position.tick for position in positions], tempo_map)
    scores = np.array([getattr(weights, name) for name in metric], dtype=np.float64)
    strengths = np.array([position.strength for position in positions], dtype=np.float64)
    scores += weights.onset_strength * _percentile_ranks(strengths)
    scores += weights.sustain * np.array([position.length > 0 for position in positions])
    is_last = np.r_[labels[1:] != labels[:-1], True]
    scores += weights.phrase_end * is_last
    return scores


def _phrase_starts(labels: np.ndarray) -> np.ndarray:
    return np.r_[True, labels[1:] != labels[:-1]]


def select_positions(
    candidates: np.ndarray,
    times: np.ndarray,
    scores: np.ndarray,
    protected: np.ndarray,
    target: int,
    min_gap_s: float,
    ticks: np.ndarray | None = None,
    min_gap_ticks: int | None = None,
    floor_s: float = 0.0,
) -> np.ndarray:
    """Choose indices among ``candidates``, best score first, keeping notes apart.

    Protected notes always stay, whatever the target says. Others are added until ``target`` is
    reached or nothing fits, so a level can end up short of its target, which then warns.

    Two notes are far enough apart if they are ``min_gap_s`` apart or, when ``ticks`` and
    ``min_gap_ticks`` are given, that many ticks apart; and in any case at least ``floor_s`` apart,
    which needs ``times`` in seconds.
    """

    def apart(earlier: int, later: int) -> bool:
        if times[later] - times[earlier] < floor_s - 1e-6:  # a floor met exactly is met
            return False
        if times[later] - times[earlier] >= min_gap_s:
            return True
        return ticks is not None and min_gap_ticks is not None and ticks[later] - ticks[earlier] >= min_gap_ticks

    chosen = sorted(int(index) for index in candidates if protected[index])
    others = [int(index) for index in candidates if not protected[index]]
    # Best score first; between equals, the earlier note.
    others.sort(key=lambda index: (-scores[index], index))
    for index in others:
        if len(chosen) >= target:
            break
        place = bisect_left(chosen, index)
        before_ok = place == 0 or apart(chosen[place - 1], index)
        after_ok = place == len(chosen) or apart(index, chosen[place])
        if before_ok and after_ok:
            chosen.insert(place, index)
    return np.array(chosen, dtype=np.int64)


# ---------------------------------------------------------------- frets


def _level_weights(weights: FretWeights, config: LevelConfig) -> FretWeights:
    """Fewer frets cover the same melody: each fret stands for more of it, and a phrase should
    use all of them, or a narrow level piles up on its middle fret."""
    return replace(
        weights,
        register_span=(0.0, float(config.top_lane)),
        semitones_per_lane=weights.semitones_per_lane * ORANGE / config.top_lane,
    )


def _assign_shapes(
    positions: Sequence[Position],
    phrases: np.ndarray,
    level: Difficulty,
    config: LevelConfig,
    weights: FretWeights,
) -> list[tuple[int, ...]]:
    """Run Viterbi over only the shapes the chord rule leaves open for each note."""
    index = {shape: number for number, shape in enumerate(SHAPES)}
    centers = np.array([float(np.mean(shape)) for shape in SHAPES])
    extra = np.full((len(positions), len(SHAPES)), np.inf)
    max_size = _max_chord_size(level, config)
    for row, position in enumerate(positions):
        voices = reduce_voices(position.shape, max_size)
        ideal = float(np.mean(place_voices(voices, _lanes_for(voices, config), config.top_lane)))
        fidelity = config.chord_fidelity if len(voices) > 1 else config.fidelity
        for shape in _slides(voices, config.top_lane):
            extra[row, index[shape]] = fidelity * abs(centers[index[shape]] - ideal)
    inputs = [
        NoteInput(position.time_s, position.pitch, len(position.shape)) for position in positions
    ]
    return map_notes(inputs, _level_weights(weights, config), extra, phrases)


# ---------------------------------------------------------------- what a level looks like


@dataclass(frozen=True)
class LevelMeasures:
    """Plain numbers about one level, the same for a generated chart and a human one."""

    positions: int
    position_ratio: float
    chord_share: float
    three_note_share: float
    green_share: float
    red_share: float
    yellow_share: float
    blue_share: float
    orange_share: float
    on_beat_share: float
    sixteenth_share: float
    min_gap_s: float
    sustain_share: float
    auto_hopo_share: float
    """Notes the game would turn into HOPOs by itself, before any force flag."""
    final_hopo_share: float
    """Notes that end up as HOPOs, after force flags."""
    forced_strums: int
    hand_travel: float = 0.0
    """How many frets the hand moves per note on average, going by the lowest fret. Note F1 cannot
    see frets at all, and a chart can match its lane shares with a hand that never moves."""

    @property
    def busiest_lane_share(self) -> float:
        return max(
            self.green_share, self.red_share, self.yellow_share, self.blue_share, self.orange_share
        )


def measure_level(
    positions: Sequence[tuple[int, Sequence[int]]],
    sustained: Sequence[bool],
    times: Sequence[float],
    resolution: int,
    expert_positions: int,
    final_hopos: int | None = None,
    forced_strums: int = 0,
    midi_subset_exception: bool = False,
) -> LevelMeasures:
    """Measure a level from its ``(tick, lanes)`` positions.

    ``final_hopos`` is how many notes end up as HOPOs. Left out, it is the natural count.
    """
    count = len(positions)
    if count == 0:
        return LevelMeasures(0, *[0.0] * 14, 0)  # type: ignore[arg-type]
    ticks = nearest_sixteenth(np.array([tick for tick, _ in positions]), resolution)
    gems = np.concatenate([np.asarray(lanes) for _, lanes in positions])
    shares = np.bincount(gems[gems < LANE_COUNT], minlength=LANE_COUNT) / gems.size
    sizes = np.array([len(lanes) for _, lanes in positions])
    natural = len(natural_hopo_ticks(positions, resolution, midi_subset_exception))
    final = natural if final_hopos is None else final_hopos
    gaps = np.diff(np.asarray(times, dtype=np.float64))
    lowest = np.array([min(lanes) for _, lanes in positions])
    return LevelMeasures(
        count,
        round(count / max(1, expert_positions), 3),
        round(float(np.mean(sizes > 1)), 3),
        round(float(np.mean(sizes > 2)), 3),
        *[round(float(share), 3) for share in shares],  # type: ignore[arg-type]
        round(float(np.mean(ticks % resolution == 0)), 3),
        round(float(np.mean(ticks % (resolution // 2) != 0)), 3),
        round(float(gaps.min()), 3) if gaps.size else math.inf,
        round(float(np.mean(sustained)), 3),
        round(natural / count, 3),
        round(final / count, 3),
        forced_strums,
        round(float(np.mean(np.abs(np.diff(lowest)))), 3) if count > 1 else 0.0,
    )


def measure_track(track: Track, tempo_map: TempoMap, expert_positions: int) -> LevelMeasures:
    """Measure a generated track, whose force flags can only have turned HOPOs into strums."""
    positions = positions_of(track.notes)
    sustained_ticks = {note.tick for note in track.notes if note.length > 0}
    forced = {note.tick for note in track.notes if note.forced}
    ticks = [tick for tick, _ in positions]
    natural = natural_hopo_ticks(positions, tempo_map.resolution)
    return measure_level(
        positions,
        [tick in sustained_ticks for tick in ticks],
        tempo_map.seconds_at(np.array(ticks, dtype=np.float64)) if ticks else [],
        tempo_map.resolution,
        expert_positions,
        final_hopos=len(natural ^ forced),
        forced_strums=len(natural & forced),
    )


@dataclass(frozen=True)
class SoftTargetResult:
    name: str
    value: float
    low: float
    high: float

    @property
    def in_range(self) -> bool:
        return self.low <= self.value <= self.high


def check_soft_targets(measures: LevelMeasures, targets: SoftTargets) -> list[SoftTargetResult]:
    """Compare a level with its soft targets. Being outside only ever warns."""
    results = [
        SoftTargetResult(name, float(getattr(measures, name)), low, high)
        for name, (low, high) in targets.ranges.items()
    ]
    for name, share in zip(LANE_NAMES, targets.lane_shares):
        results.append(
            SoftTargetResult(
                f"{name}_lane",
                float(getattr(measures, f"{name}_share")),
                round(max(share - targets.lane_tolerance, 0.0), 3),
                round(min(share + targets.lane_tolerance, 1.0), 3),
            )
        )
    return results


_NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


@dataclass(frozen=True)
class OrangePitches:
    """Which pitches a level's orange notes are.

    Orange is the top of the neck, so if nearly all of it is one pitch, it marks that pitch and says
    little about where the melody goes. With few pitches in a song that is hard to avoid.
    """

    counts: tuple[tuple[str, int], ...]
    """Each pitch's name and how many orange notes it has, the commonest first."""
    unknown: int = 0
    """Orange notes whose pitch could not be read. They do not count towards the shares."""
    limit: float = 1.0

    @property
    def notes(self) -> int:
        return sum(count for _, count in self.counts)

    @property
    def top_share(self) -> float:
        return self.counts[0][1] / self.notes if self.notes else 0.0

    @property
    def is_one_pitch(self) -> bool:
        return self.top_share > self.limit

    def as_dict(self) -> dict[str, object]:
        return {
            "notes": self.notes,
            "pitch_unknown": self.unknown,
            "pitches": {name: count for name, count in self.counts},
            "top_pitch_share": round(self.top_share, 3),
            "max_single_pitch_share": self.limit,
            "one_pitch": self.is_one_pitch,
        }


def count_orange_pitches(
    track: Track, positions: Sequence[Position], limit: float
) -> OrangePitches:
    """Count the pitches of ``track``'s orange notes, read from the Expert positions at their ticks."""
    pitch_at = {position.tick: position.pitch for position in positions}
    counts: dict[str, int] = {}
    unknown = 0
    for note in track.notes:
        if note.lane != ORANGE:
            continue
        pitch = pitch_at.get(note.tick, float("nan"))
        if math.isnan(pitch):
            unknown += 1
            continue
        number = int(pitch)
        name = f"{_NOTE_NAMES[number % 12]}{number // 12 - 1}"
        counts[name] = counts.get(name, 0) + 1
    ordered = tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
    return OrangePitches(ordered, unknown, limit)


# ---------------------------------------------------------------- the hard rules


def _shape_violations(level: Difficulty, positions: Sequence[tuple[int, Sequence[int]]]) -> list[str]:
    limits = {
        Difficulty.EASY: (1, "Easy has a chord or orange"),
        Difficulty.MEDIUM: (2, "Medium has orange or a chord of more than two notes"),
    }
    if level not in limits:
        return []
    size, message = limits[level]
    return [
        f"{message} at tick {tick}: {tuple(lanes)}"
        for tick, lanes in positions
        if len(lanes) > size or max(lanes) >= ORANGE
    ]


def check_hard_rules(
    tracks: Mapping[Difficulty, Track], expert: Sequence[Position], labels: np.ndarray
) -> list[str]:
    """Return every way the finished tracks break a hard rule."""
    problems: list[str] = []
    order = (Difficulty.EXPERT, *REDUCED_LEVELS)
    grouped = {level: positions_of(tracks[level].notes) for level in order}
    ticks = {level: {tick for tick, _ in grouped[level]} for level in order}
    for upper, lower in zip(order, order[1:]):
        for tick in sorted(ticks[lower] - ticks[upper]):
            problems.append(f"{lower.value} has tick {tick}, which {upper.value} does not")
    for level in REDUCED_LEVELS:
        problems.extend(_shape_violations(level, grouped[level]))
    for level in order:
        if tracks[level].instrument in SINGLE_NOTE_INSTRUMENTS:
            problems.extend(
                f"{level.value} has a chord at tick {tick}" for tick, lanes in grouped[level] if len(lanes) > 1
            )
        ordered = sorted(ticks[level])
        following = dict(zip(ordered, ordered[1:]))
        for note in tracks[level].notes:
            next_tick = following.get(note.tick)
            if next_tick is not None and note.tick + note.length > next_tick:
                problems.append(f"{level.value}: the sustain at tick {note.tick} runs into the next note")
    expert_ticks = np.array([position.tick for position in expert])
    for label in np.unique(labels):
        members = expert_ticks[labels == label]
        if members.size > _LONG_PHRASE and not ticks[Difficulty.EASY] & set(members.tolist()):
            problems.append(f"the phrase at tick {members[0]} has no note on Easy")
    return problems


# ---------------------------------------------------------------- the reduction


@dataclass(frozen=True)
class ReducedLevel:
    track: Track
    measures: LevelMeasures
    soft_targets: tuple[SoftTargetResult, ...]

    def missed_targets(self) -> tuple[SoftTargetResult, ...]:
        return tuple(result for result in self.soft_targets if not result.in_range)


def _build_level(
    instrument: Instrument,
    level: Difficulty,
    chosen: Sequence[Position],
    shapes: Sequence[tuple[int, ...]],
    config: LevelConfig,
    tempo_map: TempoMap,
) -> Track:
    resolution = tempo_map.resolution
    forced: set[int] = set()
    if not config.keep_auto_hopos:
        forced = natural_hopo_ticks(
            [(position.tick, shape) for position, shape in zip(chosen, shapes)], resolution
        )
    shortest = config.min_sustain_beats * resolution
    shortest_s = seconds_floor(config.min_sustain_beats) - 1e-6

    def sustained(position: Position) -> bool:
        if position.length < shortest:
            return False
        start = tempo_map.seconds_at(float(position.tick))
        return tempo_map.seconds_at(float(position.tick + position.length)) - start >= shortest_s

    notes = [
        ChartNote(
            position.tick,
            lane,
            position.length if sustained(position) else 0,
            forced=position.tick in forced,
        )
        for position, shape in zip(chosen, shapes)
        for lane in shape
    ]
    return Track(instrument, level, notes)


def reduce_track(
    instrument: Instrument,
    expert_track: Track,
    expert: Sequence[Position],
    tempo_map: TempoMap,
    config: DifficultyConfig | None = None,
    weights: FretWeights | None = None,
) -> dict[Difficulty, ReducedLevel]:
    """Build Hard, Medium and Easy from Expert.

    Raises:
        HardRuleViolation: If the result breaks a hard rule, which would be a bug.
    """
    settings = config or load_config()
    fret_weights = weights or load_weights()
    if not expert:
        return {}
    ordered = sorted(expert, key=lambda position: position.tick)
    inputs = [NoteInput(position.time_s) for position in ordered]
    labels = phrase_labels(inputs, fret_weights.phrase_gap_s)
    times = np.array([position.time_s for position in ordered], dtype=np.float64)
    ticks = np.array([position.tick for position in ordered], dtype=np.int64)
    protected = _phrase_starts(labels)

    candidates = np.arange(len(ordered))
    levels: dict[Difficulty, ReducedLevel] = {}
    for level in REDUCED_LEVELS:
        cfg = settings.levels[level]
        target = round(cfg.position_ratio * len(ordered))
        scores = importance_scores(ordered, labels, tempo_map, cfg.importance)
        gap_ticks = None if cfg.min_gap_beats is None else round(cfg.min_gap_beats * tempo_map.resolution)
        candidates = select_positions(
            candidates, times, scores, protected, target, cfg.min_gap_s, ticks, gap_ticks
        )
        chosen = [ordered[int(index)] for index in candidates]
        shapes = _assign_shapes(chosen, labels[candidates], level, cfg, fret_weights)
        track = _build_level(instrument, level, chosen, shapes, cfg, tempo_map)
        measures = measure_track(track, tempo_map, len(ordered))
        levels[level] = ReducedLevel(
            track, measures, tuple(check_soft_targets(measures, cfg.soft_targets))
        )

    all_tracks = {Difficulty.EXPERT: expert_track, **{key: item.track for key, item in levels.items()}}
    problems = check_hard_rules(all_tracks, ordered, labels)
    if problems:
        raise HardRuleViolation("; ".join(problems[:5]))
    return levels
