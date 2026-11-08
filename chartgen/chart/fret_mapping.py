"""Playability-aware fret mapping with the Viterbi algorithm.

A guitar has far more pitches than a controller has frets, so pitch cannot map to frets one to
one: a charter mimics the shape of the melody. This module does the same. It follows the
contour between notes and the note's place within its own phrase, so a riff played a fifth
higher elsewhere gets the same shape, and it never looks at absolute pitch.

Two things are kept strictly apart:

* **Hard rules** are in this module. A path that breaks one is never considered, whatever
  the weights say. Tests check them under random weights.
* **Preferences** are the weights in ``fret_weights.toml``, the only place to tune them.
"""

from __future__ import annotations

import tomllib
from collections.abc import Sequence
from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np

WEIGHTS_PATH = Path(__file__).with_name("fret_weights.toml")

SHAPES: tuple[tuple[int, ...], ...] = (
    (0,), (1,), (2,), (3,), (4,),
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 2), (1, 3), (2, 4),
    (0, 1, 2), (1, 2, 3), (2, 3, 4),
    (0, 1, 3), (0, 2, 3), (1, 2, 4), (1, 3, 4),
)  # fmt: skip
"""Every fret combination a chart may use. Human charts use the gapped triads a lot."""

FAST_GAP_S = 0.15
MEDIUM_GAP_S = 0.30
MAX_MOVE_FAST = 2.0
"""With less than ``FAST_GAP_S`` between notes, the hand moves at most this many frets."""
MAX_MOVE_MEDIUM = 3.0
"""With less than ``MEDIUM_GAP_S`` between notes, the hand moves at most this many frets."""
CHORD_CHANGE_GAP_S = 0.12
MAX_CHORD_MOVE_FAST = 1.0
"""Between two chords in very quick succession, the hand moves at most this far."""

_CENTERS = np.array([float(np.mean(shape)) for shape in SHAPES])
_ANCHORS = np.array([float(min(shape)) for shape in SHAPES])
"""Melody follows a chord's lowest fret: human chords share their bottom note far more than
their center, and following it agrees better with human charts."""
_SIZES = np.array([len(shape) for shape in SHAPES])
_MOVES = np.abs(_CENTERS[None, :] - _CENTERS[:, None])
_BOTH_CHORDS = (_SIZES[None, :] > 1) & (_SIZES[:, None] > 1)


@dataclass(frozen=True)
class FretWeights:
    contour: float
    hold: float
    repeat: float
    magnitude: float
    semitones_per_lane: float
    register: float
    register_span: tuple[float, float]
    speed: float
    voices: float
    lane_prior: float
    lane_shares: tuple[float, float, float, float, float]
    consistency: float
    phrase_gap_s: float


def load_weights(path: Path = WEIGHTS_PATH) -> FretWeights:
    """Read the weights file.

    Raises:
        ValueError: If a value is missing, unknown, negative or malformed.
    """
    with path.open("rb") as stream:
        values = tomllib.load(stream)
    expected = {field.name for field in fields(FretWeights)}
    if set(values) != expected:
        raise ValueError(f"{path.name}: expected keys {sorted(expected)}, got {sorted(values)}")
    shares = values["lane_shares"]
    if len(shares) != 5 or any(share <= 0 for share in shares):
        raise ValueError(f"{path.name}: lane_shares needs five positive values")
    values["lane_shares"] = tuple(float(share) for share in shares)
    span = values["register_span"]
    if len(span) != 2 or not 0 <= span[0] <= span[1] <= 4:
        raise ValueError(f"{path.name}: register_span needs low and high frets between 0 and 4")
    values["register_span"] = (float(span[0]), float(span[1]))
    for name, value in values.items():
        if name not in {"lane_shares", "register_span"} and float(value) < 0:
            raise ValueError(f"{path.name}: {name} must not be negative")
    if values["semitones_per_lane"] <= 0 or values["phrase_gap_s"] <= 0:
        raise ValueError(f"{path.name}: semitones_per_lane and phrase_gap_s must be positive")
    return FretWeights(**values)


@dataclass(frozen=True)
class NoteInput:
    """What the mapper knows about one note."""

    time_s: float
    pitch: float = float("nan")
    """Any scale where one unit is about a semitone, used only relative to other notes. Two
    notes with exactly the same value are the same note. NaN when unknown."""
    voices: int = 1


def allowed_moves(gap_s: float) -> np.ndarray:
    """Return which shape may follow which after a pause of ``gap_s``, the hard rules."""
    if gap_s < FAST_GAP_S:
        limit = MAX_MOVE_FAST
    elif gap_s < MEDIUM_GAP_S:
        limit = MAX_MOVE_MEDIUM
    else:
        return np.ones_like(_MOVES, dtype=bool)
    allowed = _MOVES <= limit + 1e-9
    if gap_s < CHORD_CHANGE_GAP_S:
        allowed &= ~_BOTH_CHORDS | (_MOVES <= MAX_CHORD_MOVE_FAST + 1e-9)
    return allowed


def is_playable(shapes: Sequence[tuple[int, ...]], times: Sequence[float]) -> bool:
    """Check a finished mapping against the hard rules."""
    index = {shape: number for number, shape in enumerate(SHAPES)}
    if any(shape not in index for shape in shapes):
        return False
    for position in range(1, len(shapes)):
        gap = times[position] - times[position - 1]
        if not allowed_moves(gap)[index[shapes[position - 1]], index[shapes[position]]]:
            return False
    return True


def _phrases(notes: Sequence[NoteInput], gap_s: float) -> np.ndarray:
    labels = np.zeros(len(notes), dtype=int)
    for index in range(1, len(notes)):
        new_phrase = notes[index].time_s - notes[index - 1].time_s >= gap_s
        labels[index] = labels[index - 1] + int(new_phrase)
    return labels


def _relative_pitch(notes: Sequence[NoteInput], labels: np.ndarray, known: np.ndarray) -> np.ndarray:
    """Return each note's place within its phrase, from 0 to 1. NaN when unknown."""
    pitches = np.array([note.pitch for note in notes], dtype=np.float64)
    relative = np.full(len(notes), np.nan)
    for label in np.unique(labels):
        members = (labels == label) & known
        if not members.any():
            continue
        low, high = float(pitches[members].min()), float(pitches[members].max())
        if high > low:
            relative[members] = (pitches[members] - low) / (high - low)
        else:
            relative[members] = 0.5
    return relative


def _viterbi(
    notes: Sequence[NoteInput],
    weights: FretWeights,
    labels: np.ndarray,
    known: np.ndarray,
    relative: np.ndarray,
    preferred: np.ndarray | None,
) -> np.ndarray:
    pitches = np.array([note.pitch for note in notes], dtype=np.float64)
    shares = np.array(weights.lane_shares)
    shares = shares / shares.sum()
    prior = np.array([-np.log(shares[list(shape)]).mean() for shape in SHAPES])
    states = len(SHAPES)
    count = len(notes)

    def node_cost(index: int) -> np.ndarray:
        cost = weights.lane_prior * prior
        note = notes[index]
        cost = cost + weights.voices * np.abs(_SIZES - note.voices)
        if known[index]:
            low, high = weights.register_span
            target = low + (high - low) * relative[index]
            cost = cost + weights.register * np.abs(_CENTERS - target)
        if preferred is not None and np.isfinite(preferred[index]):
            cost = cost + weights.consistency * np.abs(_CENTERS - preferred[index])
        return cost

    scores = node_cost(0)
    back = np.zeros((count, states), dtype=np.int32)
    for index in range(1, count):
        gap = notes[index].time_s - notes[index - 1].time_s
        hand_move = _MOVES  # [previous, current]
        step = _ANCHORS[None, :] - _ANCHORS[:, None]
        transition = weights.speed * hand_move / max(gap, 0.08)
        same_phrase = labels[index] == labels[index - 1]
        if same_phrase and known[index] and known[index - 1]:
            interval = float(pitches[index] - pitches[index - 1])
            if abs(interval) < 0.5:
                transition = transition + weights.repeat * (np.abs(step) > 1e-9)
            else:
                backwards = np.sign(step) == -np.sign(interval)
                holding = np.abs(step) <= 1e-9
                expected = np.clip(interval / weights.semitones_per_lane, -4.0, 4.0)
                transition = (
                    transition
                    + weights.contour * backwards
                    + weights.hold * holding
                    + weights.magnitude * np.abs(step - expected)
                )
        transition = np.where(allowed_moves(gap), transition, np.inf)
        total = scores[:, None] + transition
        back[index] = np.argmin(total, axis=0)
        scores = total[back[index], np.arange(states)] + node_cost(index)

    path = np.zeros(count, dtype=np.int32)
    path[-1] = int(np.argmin(scores))
    for index in range(count - 1, 0, -1):
        path[index - 1] = back[index, path[index]]
    return path


def map_notes(
    notes: Sequence[NoteInput], weights: FretWeights | None = None
) -> list[tuple[int, ...]]:
    """Choose a fret shape for every note, in order.

    A second pass runs with a preference for keeping each pitch of a phrase on the fret that
    the first pass mostly gave it, so that a repeated riff repeats its frets.
    """
    if not notes:
        return []
    chosen = weights or load_weights()
    labels = _phrases(notes, chosen.phrase_gap_s)
    known = np.array([np.isfinite(note.pitch) for note in notes])
    relative = _relative_pitch(notes, labels, known)
    first = _viterbi(notes, chosen, labels, known, relative, None)

    preferred = np.full(len(notes), np.nan)
    rounded = np.round([note.pitch if np.isfinite(note.pitch) else -1.0 for note in notes])
    for label in np.unique(labels):
        members = np.flatnonzero((labels == label) & known)
        for pitch in np.unique(rounded[members]):
            same = members[rounded[members] == pitch]
            if same.size >= 2:
                preferred[same] = float(np.median(_CENTERS[first[same]]))
    final = _viterbi(notes, chosen, labels, known, relative, preferred)
    return [SHAPES[state] for state in final]
