"""The fret mapper. These tests use no audio: notes go in, frets come out."""

import math
import random
from dataclasses import fields, replace
from pathlib import Path

import numpy as np
import pytest

from chartgen.chart.fret_mapping import (
    CHORD_CHANGE_GAP_S,
    FAST_GAP_S,
    MAX_CHORD_MOVE_FAST,
    MAX_MOVE_FAST,
    MAX_MOVE_MEDIUM,
    MEDIUM_GAP_S,
    SHAPES,
    WEIGHTS_PATH,
    FretWeights,
    NoteInput,
    allowed_moves,
    is_playable,
    load_weights,
    map_notes,
)


def melody(pitches, spacing=0.3, start=0.0, voices=1):
    return [
        NoteInput(start + index * spacing, float(pitch), voices)
        for index, pitch in enumerate(pitches)
    ]


def lowest(shapes):
    return [min(shape) for shape in shapes]


def random_weights(rng: random.Random) -> FretWeights:
    """Anything a future tuning might choose, including extreme and zero values."""

    def value() -> float:
        return rng.choice([0.0, 0.01, 0.5, 1.0, 5.0, 50.0, 1000.0])

    return FretWeights(
        contour=value(),
        hold=value(),
        repeat=value(),
        magnitude=value(),
        semitones_per_lane=rng.choice([0.5, 1.5, 7.0]),
        register=value(),
        register_span=(rng.uniform(0, 2), rng.uniform(2, 4)),
        speed=value(),
        voices=value(),
        lane_prior=value(),
        lane_shares=tuple(rng.uniform(0.01, 1.0) for _ in range(5)),
        consistency=value(),
        phrase_gap_s=rng.choice([0.1, 0.9, 5.0]),
    )


def random_notes(rng: random.Random, count: int = 200):
    time = 0.0
    notes = []
    for _ in range(count):
        time += rng.choice([0.09, 0.1, 0.12, 0.14, 0.2, 0.28, 0.35, 0.6, 1.2, 3.0])
        pitch = float("nan") if rng.random() < 0.05 else rng.uniform(0, 72)
        notes.append(NoteInput(time, pitch, rng.choice([1, 1, 2, 3])))
    return notes


# ---------------------------------------------------------------- what must always hold


@pytest.mark.parametrize("seed", range(25))
def test_no_forbidden_transition_under_any_weights(seed):
    """The hard rules hold whatever the weights say: this test knows no weight values."""
    rng = random.Random(seed)
    weights = random_weights(rng)
    notes = random_notes(rng)
    shapes = map_notes(notes, weights)
    assert len(shapes) == len(notes)
    assert is_playable(shapes, [note.time_s for note in notes])


@pytest.mark.parametrize("seed", range(10))
def test_hard_rules_stated_directly_under_any_weights(seed):
    """The same rules, written out without using the module's own checker."""
    rng = random.Random(100 + seed)
    notes = random_notes(rng)
    shapes = map_notes(notes, random_weights(rng))
    for shape in shapes:
        assert 1 <= len(shape) <= 3
        assert all(0 <= lane <= 4 for lane in shape)
        assert list(shape) == sorted(set(shape))
    for index in range(1, len(shapes)):
        gap = notes[index].time_s - notes[index - 1].time_s
        move = abs(np.mean(shapes[index]) - np.mean(shapes[index - 1]))
        if gap < FAST_GAP_S:
            assert move <= MAX_MOVE_FAST + 1e-9
        elif gap < MEDIUM_GAP_S:
            assert move <= MAX_MOVE_MEDIUM + 1e-9
        if gap < CHORD_CHANGE_GAP_S and len(shapes[index]) > 1 and len(shapes[index - 1]) > 1:
            assert move <= MAX_CHORD_MOVE_FAST + 1e-9


def test_checker_recognises_a_forbidden_jump():
    assert not is_playable([(0,), (4,)], [0.0, 0.1])
    assert is_playable([(0,), (4,)], [0.0, 1.0])
    assert is_playable([(0,), (2,)], [0.0, 0.1])


def test_checker_rejects_an_unknown_shape():
    assert not is_playable([(0, 4)], [0.0])
    assert not is_playable([(0, 1, 2, 3)], [0.0])


def test_staying_put_is_always_allowed_so_a_path_always_exists():
    for gap in (0.01, 0.1, 0.13, 0.2, 0.5, 5.0):
        assert np.all(np.diag(allowed_moves(gap)))


def test_shapes_are_unique_and_valid():
    assert len(set(SHAPES)) == len(SHAPES)
    assert all(tuple(sorted(shape)) == shape for shape in SHAPES)
    assert all(0 <= lane <= 4 for shape in SHAPES for lane in shape)


def test_mapping_is_deterministic():
    notes = random_notes(random.Random(7))
    assert map_notes(notes) == map_notes(notes)


def test_empty_and_single_note():
    assert map_notes([]) == []
    assert len(map_notes([NoteInput(0.0, 40.0)])) == 1
    assert len(map_notes([NoteInput(0.0)])) == 1


def test_notes_without_any_pitch_still_get_frets():
    notes = [NoteInput(index * 0.3) for index in range(20)]
    assert is_playable(map_notes(notes), [note.time_s for note in notes])


# ---------------------------------------------------------------- preferences


def test_ascending_scale_climbs_the_frets():
    lanes = lowest(map_notes(melody(range(40, 60, 2))))
    assert all(b >= a for a, b in zip(lanes, lanes[1:]))
    assert lanes[-1] > lanes[0]


def test_descending_scale_descends_the_frets():
    lanes = lowest(map_notes(melody(range(60, 40, -2))))
    assert all(b <= a for a, b in zip(lanes, lanes[1:]))
    assert lanes[-1] < lanes[0]


def test_repeated_pitch_stays_on_the_same_fret():
    shapes = map_notes(melody([50, 50, 50, 50, 55, 55, 55, 55]))
    assert len(set(shapes[:4])) == 1
    assert len(set(shapes[4:])) == 1


def test_repeated_riff_repeats_its_frets():
    riff = [40, 43, 45, 43, 48, 45]
    shapes = map_notes(melody(riff * 6))
    groups = [shapes[i : i + len(riff)] for i in range(0, len(shapes), len(riff))]
    assert groups[2] == groups[3] == groups[4]


def test_transposed_riff_in_another_phrase_keeps_its_shape():
    """This is what makes the mapping relative and not one pitch to one fret."""
    riff = [40, 43, 45, 43, 48, 45, 43, 40]
    first = melody(riff)
    second = melody([pitch + 7 for pitch in riff], start=first[-1].time_s + 5.0)
    shapes = map_notes(first + second)
    assert shapes[: len(riff)] == shapes[len(riff) :]


def test_same_pitch_can_land_on_different_frets_in_different_phrases():
    """A global pitch table could never do this."""
    low_phrase = melody([50, 53, 56, 59, 62])
    high_phrase = melody([38, 41, 44, 47, 50], start=low_phrase[-1].time_s + 5.0)
    shapes = map_notes(low_phrase + high_phrase)
    assert shapes[0] != shapes[-1], "pitch 50 starts one phrase low and ends the other high"


def test_chords_follow_the_voices_heard():
    shapes = map_notes(melody([40, 45, 50, 45] * 4, voices=2))
    assert all(len(shape) >= 2 for shape in shapes)
    shapes = map_notes(melody([40, 45, 50, 45] * 4, voices=1))
    assert all(len(shape) == 1 for shape in shapes)


def test_long_melody_uses_most_of_the_neck():
    rng = random.Random(3)
    pitches = [rng.uniform(40, 70) for _ in range(200)]
    shapes = map_notes(melody(pitches))
    assert len({lane for shape in shapes for lane in shape}) >= 4


# ---------------------------------------------------------------- weights file


def test_all_weights_live_in_one_file():
    weights = load_weights()
    assert WEIGHTS_PATH.suffix == ".toml"
    assert {field.name for field in fields(FretWeights)} == set(
        __import__("tomllib").loads(WEIGHTS_PATH.read_text(encoding="utf-8"))
    )
    assert math.isclose(weights.contour, weights.contour)


def write_weights(tmp_path: Path, **changes) -> Path:
    text = WEIGHTS_PATH.read_text(encoding="utf-8")
    lines = []
    for line in text.splitlines():
        key = line.split("=")[0].strip()
        if key in changes:
            if changes[key] is not None:
                lines.append(f"{key} = {changes[key]}")
            continue
        lines.append(line)
    path = tmp_path / "weights.toml"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"contour": None}, "expected keys"),
        ({"contour": -1.0}, "must not be negative"),
        ({"lane_shares": "[1.0, 1.0]"}, "five positive"),
        ({"lane_shares": "[1.0, 1.0, 0.0, 1.0, 1.0]"}, "five positive"),
        ({"register_span": "[3.0, 1.0]"}, "register_span"),
        ({"semitones_per_lane": 0.0}, "must be positive"),
    ],
)
def test_invalid_weights_are_refused(tmp_path, changes, message):
    with pytest.raises(ValueError, match=message):
        load_weights(write_weights(tmp_path, **changes))


def test_changing_a_weight_changes_preferences_but_never_the_rules():
    notes = random_notes(random.Random(11))
    times = [note.time_s for note in notes]
    base = load_weights()
    for change in ({"contour": 0.0}, {"lane_prior": 100.0}, {"speed": 0.0}, {"register": 50.0}):
        assert is_playable(map_notes(notes, replace(base, **change)), times)
