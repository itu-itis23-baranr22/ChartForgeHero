"""The editor's operations and undo (SPEC 50, E.2 plan in docs/STATUS.md).

Every operation on its own; what the model cannot hold is refused and changes nothing; linked levels (changes
flow down, additions flow up) keep the validator's level chain intact; a sustain that an operation runs into
the next note is cut; and undo and redo give back the exact bytes, also over seeded random sequences.
"""

from __future__ import annotations

import random
import re
from pathlib import Path

import pytest
from conftest import skip_missing
from test_chart_reader import every_feature

from chartgen.clonehero.chart_format import DotChartExporter
from chartgen.clonehero.chart_reader import read_chart, read_chart_file
from chartgen.clonehero.validate import validate_chart_text
from chartgen.core.model import Chart, ChartNote, Difficulty, Instrument, SongMetadata, StarPowerPhrase, Track
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent
from chartgen.editor import ops
from chartgen.editor.ops import CYMBAL, FORCED, TAP, OpError
from chartgen.editor.session import EditSession, NothingToDoError, StaleError

E, H, M, Z = Difficulty.EXPERT, Difficulty.HARD, Difficulty.MEDIUM, Difficulty.EASY
OUTPUTS = Path(__file__).resolve().parents[1] / "outputs"
CHAIN = re.compile(r"has tick \d+, but|is not in \[")
"""The validator's level chain: every note of a level must also be on the level above it."""


def render(chart: Chart) -> bytes:
    return DotChartExporter().render(chart)


def notes_of(chart: Chart, instrument: Instrument, difficulty: Difficulty) -> list[tuple[int, int, int, bool, bool, bool]]:
    track = next(t for t in chart.tracks if t.instrument is instrument and t.difficulty is difficulty)
    return [(n.tick, n.lane, n.length, n.forced, n.tap, n.cymbal) for n in track.notes]


def levelled() -> Chart:
    """32 bars of guitar, bass and drums on all four levels, each level inside the one above it: valid."""
    expert, hard, medium, easy = [], [], [], []
    for k in range(256):
        tick = 96 * k
        lane = (k * 7 + k // 5) % 5
        length = 96 if k % 9 == 0 else 0
        expert.append(ChartNote(tick, lane, length))
        if k % 4 == 2:
            expert.append(ChartNote(tick, (lane + 2) % 5))
        if k % 2 == 0:
            hard.append(ChartNote(tick, lane, length))
        if k % 4 == 0:
            medium.append(ChartNote(tick, min(lane, 3)))
        if k % 8 == 0:
            easy.append(ChartNote(tick, min(lane, 3)))
    bass = [[ChartNote(96 * k, k % 4) for k in range(0, 256, step)] for step in (1, 2, 4, 8)]
    drums_e, drums_h, drums_m, drums_z = [], [], [], []
    for k in range(256):
        tick = 96 * k
        beat = k % 8
        gems = [ChartNote(tick, 2, cymbal=True)]
        if beat in (0, 4):
            gems.append(ChartNote(tick, 0))
        if beat in (2, 6):
            gems.append(ChartNote(tick, 1))
        drums_e += gems
        if k % 2 == 0:
            drums_h += gems
            drums_m += gems
            drums_z += [g for g in gems if g.lane != 0] or gems
    tracks = [
        Track(Instrument.GUITAR, E, expert, [StarPowerPhrase(768 * 4, 768)]),
        Track(Instrument.GUITAR, H, hard, [StarPowerPhrase(768 * 4, 768)]),
        Track(Instrument.GUITAR, M, medium),
        Track(Instrument.GUITAR, Z, easy),
        *[Track(Instrument.BASS, d, notes) for d, notes in zip((E, H, M, Z), bass)],
        Track(Instrument.DRUMS, E, drums_e),
        Track(Instrument.DRUMS, H, drums_h),
        Track(Instrument.DRUMS, M, drums_m),
        Track(Instrument.DRUMS, Z, drums_z),
    ]
    tempo = TempoMap([TempoEvent(0, 120.0), TempoEvent(768 * 16, 150.0)], [TimeSignatureEvent(0, 4)])
    return Chart(SongMetadata("Level Sheet", "The Test Rig"), tempo, tracks)


def request(instrument: str, difficulty: str, op: dict, linked: bool = True) -> dict:
    return {"instrument": instrument, "difficulty": difficulty, "linked": linked, "op": op}


def run(chart: Chart, instrument: str, difficulty: str, op: dict, linked: bool = True) -> ops.Result:
    """Apply an operation and put its result in place, as the session does."""
    result = ops.apply(chart, request(instrument, difficulty, op, linked))
    for (i, d), notes in result.changed.items():
        next(t for t in chart.tracks if t.instrument is i and t.difficulty is d).notes = notes
    return result


def chain_errors(chart: Chart) -> list[str]:
    return [m for m in validate_chart_text(render(chart).decode("utf-8-sig"))[1].errors if CHAIN.search(m)]


# ---------------------------------------------------------------- the operations one by one


def test_the_levelled_chart_is_valid_to_start_with():
    report = validate_chart_text(render(levelled()).decode("utf-8-sig"))[1]
    assert report.errors == []


def test_add_puts_notes_on_their_lanes():
    chart = every_feature()
    result = run(chart, "guitar", "expert", {"kind": "add", "notes": [[1344, 2, 96, 0], [1344, 4, 96, 0]]}, linked=False)
    assert result.label == "Add 2 notes"
    assert result.selection == [(1344, 2), (1344, 4)]
    assert (1344, 2, 96, False, False, False) in notes_of(chart, Instrument.GUITAR, E)
    assert list(result.changed) == [(Instrument.GUITAR, E)]


def test_delete_removes_exactly_the_named_notes():
    chart = every_feature()
    run(chart, "guitar", "expert", {"kind": "delete", "notes": [[768, 0]]}, linked=False)
    assert (768, 0, 0, False, False, False) not in notes_of(chart, Instrument.GUITAR, E)
    assert (768, 1, 0, False, False, False) in notes_of(chart, Instrument.GUITAR, E)


def test_move_shifts_in_time_and_across_lanes():
    chart = every_feature()
    result = run(chart, "guitar", "expert", {"kind": "move", "notes": [[864, 2]], "ticks": -48, "rows": 1}, linked=False)
    assert result.selection == [(816, 3)]
    # Its 192-tick sustain now runs into the note at 960, so it is cut to end there.
    assert (816, 3, 144, False, False, False) in notes_of(chart, Instrument.GUITAR, E)
    assert result.notices == ["A sustain was cut to end on the next note (Expert 1)."]


def test_moving_drums_up_and_down_follows_the_rows_on_screen():
    """The rows are red, yellow, blue, green, then the kick: down from green is the kick."""
    chart = every_feature()
    result = run(chart, "drums", "expert", {"kind": "move", "notes": [[864, 1]], "rows": 1}, linked=False)
    assert result.selection == [(864, 2)]
    chart = every_feature()
    with pytest.raises(OpError, match="Only yellow, blue and green"):  # a green cymbal cannot become a kick
        run(chart, "drums", "expert", {"kind": "move", "notes": [[960, 4]], "rows": 1}, linked=False)
    result = run(chart, "drums", "expert", {"kind": "move", "notes": [[768, 0]], "rows": -1}, linked=False)
    assert result.selection == [(768, 4)]


def test_sustain_takes_a_length_or_a_change():
    chart = every_feature()
    run(chart, "guitar", "expert", {"kind": "sustain", "notes": [[1248, 1], [1248, 2]], "length": 48}, linked=False)
    assert [n[2] for n in notes_of(chart, Instrument.GUITAR, E) if n[0] == 1248] == [48, 48]
    run(chart, "guitar", "expert", {"kind": "sustain", "notes": [[1248, 1]], "delta": -96}, linked=False)
    assert [n[2] for n in notes_of(chart, Instrument.GUITAR, E) if n[0] == 1248] == [0, 48]


def test_forced_and_tap_belong_to_the_whole_chord():
    chart = every_feature()
    result = run(chart, "guitar", "expert", {"kind": "flag", "notes": [[768, 0]], "flag": "forced", "on": True}, linked=False)
    assert result.label == "Forced on"
    assert [n[3] for n in notes_of(chart, Instrument.GUITAR, E) if n[0] == 768] == [True, True]
    run(chart, "guitar", "expert", {"kind": "flag", "notes": [[1248, 1]], "flag": "forced", "on": False}, linked=False)
    assert [n[3] for n in notes_of(chart, Instrument.GUITAR, E) if n[0] == 1248] == [False, False]


def test_a_note_added_to_a_forced_chord_is_forced_as_the_file_would_read_it():
    chart = every_feature()
    run(chart, "guitar", "expert", {"kind": "add", "notes": [[1248, 3]]}, linked=False)
    assert [n[3] for n in notes_of(chart, Instrument.GUITAR, E) if n[0] == 1248] == [True, True, True]
    assert render(read_chart(render(chart).decode("utf-8-sig"))) == render(chart)


def test_cymbals_change_only_on_yellow_blue_and_green():
    chart = every_feature()
    result = run(chart, "drums", "expert", {"kind": "flag", "notes": [[864, 1], [864, 3]], "flag": "cymbal", "on": True}, linked=False)
    assert result.label == "Make cymbal"
    assert (864, 3, 0, False, False, True) in notes_of(chart, Instrument.DRUMS, E)
    assert (864, 1, 0, False, False, False) in notes_of(chart, Instrument.DRUMS, E)


def test_paste_writes_over_its_range():
    chart = every_feature()
    result = run(chart, "guitar", "expert", {"kind": "paste", "notes": [[960, 0, 0, 0], [1056, 1, 0, 0]]}, linked=False)
    assert result.label == "Paste 2 notes"
    ticks = {n[0]: n for n in notes_of(chart, Instrument.GUITAR, E)}
    assert ticks[960][1] == 0 and ticks[1056][1] == 1
    assert ticks[1056][4] is False  # the old tap note was written over
    assert 1152 in ticks  # after the range: untouched


def test_an_operation_that_changes_nothing_is_no_step():
    chart = every_feature()
    session = EditSession("x", Path("."), chart)
    before = session.version
    out = session.apply({"version": before, **request("guitar", "expert", {"kind": "move", "notes": [[768, 0]], "ticks": 0, "rows": 0})})
    assert out["tracks"] == [] and out["edit"]["version"] == before and out["edit"]["undo"] is None


# ---------------------------------------------------------------- refused: the model cannot hold it


@pytest.mark.parametrize(
    ("instrument", "difficulty", "op", "message"),
    [
        ("guitar", "expert", {"kind": "add", "notes": [[768, 0]]}, "already a green note at tick 768"),
        ("guitar", "expert", {"kind": "add", "notes": [[100, 1], [100, 1]]}, "same lane at the same tick"),
        ("guitar", "expert", {"kind": "move", "notes": [[768, 0]], "ticks": -800}, "before the start"),
        ("guitar", "expert", {"kind": "move", "notes": [[768, 0]], "rows": -1}, "no lane above green"),
        ("guitar", "expert", {"kind": "move", "notes": [[1152, 5]], "rows": 1}, "open note has no lane"),
        ("guitar", "expert", {"kind": "move", "notes": [[768, 1]], "ticks": 480}, "already a red note at tick 1248"),
        ("guitar", "expert", {"kind": "flag", "notes": [[768, 0]], "flag": "cymbal", "on": True}, "Only drums have cymbals"),
        ("guitar", "expert", {"kind": "add", "notes": [[96, 2, 0, CYMBAL]]}, "Only drums have cymbals"),
        ("drums", "expert", {"kind": "add", "notes": [[96, 5]]}, "no open notes"),
        ("drums", "expert", {"kind": "add", "notes": [[96, 1, 48, 0]]}, "no sustain"),
        ("drums", "expert", {"kind": "add", "notes": [[96, 1, 0, FORCED]]}, "forced or a tap"),
        ("drums", "expert", {"kind": "add", "notes": [[96, 1, 0, CYMBAL]]}, "Only yellow, blue and green"),
        ("drums", "expert", {"kind": "sustain", "notes": [[768, 0]], "length": 96}, "no sustain"),
        ("drums", "expert", {"kind": "flag", "notes": [[768, 0]], "flag": "tap", "on": True}, "forced or a tap"),
        ("drums", "expert", {"kind": "flag", "notes": [[768, 0]], "flag": "cymbal", "on": True}, "Only yellow, blue and green"),
        ("drums", "expert", {"kind": "move", "notes": [[768, 0]], "rows": 1}, "no row below the kick"),
        ("guitar", "expert", {"kind": "delete", "notes": [[769, 0]]}, "no green note at tick 769 any more"),
        ("guitar", "expert", {"kind": "sustain", "notes": [[768, 0]], "length": 5, "delta": 1}, "either a length or a delta"),
        ("guitar", "expert", {"kind": "explode", "notes": [[768, 0]]}, "no such operation"),
        ("guitar", "expert", {"kind": "add", "notes": []}, "names no notes"),
        ("guitar", "expert", {"kind": "add", "notes": [["768", 0]]}, "whole number"),
        ("guitar", "expert", {"kind": "add", "notes": [[768, 6]]}, "whole number from 0 to 5"),
        ("guitar", "expert", {"kind": "flag", "notes": [[768, 0]], "flag": "glow", "on": True}, "no such flag"),
        ("guitar", "medium", {"kind": "add", "notes": [[96, 0]]}, "no medium guitar chart"),
        ("lute", "expert", {"kind": "add", "notes": [[96, 0]]}, "no such instrument"),
    ],
)
def test_what_the_model_cannot_hold_is_refused_and_nothing_changes(instrument, difficulty, op, message):
    chart = every_feature()
    session = EditSession("x", Path("."), chart)
    before = render(chart)
    version = session.version
    with pytest.raises(OpError, match=message):
        session.apply({"version": version, **request(instrument, difficulty, op)})
    assert render(chart) == before
    assert session.version == version and session.undo_stack == []


def test_what_only_breaks_a_validator_rule_is_allowed():
    """An Easy chord, orange on Medium, three pads at once: the live check shows them."""
    chart = levelled()
    run(chart, "guitar", "easy", {"kind": "add", "notes": [[0, 1]]})
    run(chart, "guitar", "medium", {"kind": "add", "notes": [[0, 4]]})
    run(chart, "drums", "expert", {"kind": "add", "notes": [[96, 3], [96, 4]]})
    errors = validate_chart_text(render(chart).decode("utf-8-sig"))[1].errors
    assert any("[EasySingle] tick 0: a chord of" in e for e in errors)
    assert any("[MediumSingle] tick 0: orange" in e for e in errors)
    assert any("[ExpertDrums] tick 96: 3 pads at once" in e for e in errors)


# ---------------------------------------------------------------- linked levels


def test_deleting_a_whole_tick_takes_it_from_the_levels_below():
    chart = levelled()
    result = run(chart, "guitar", "expert", {"kind": "delete", "notes": [[0, 0]]})
    for d in (H, M, Z):
        assert all(n[0] != 0 for n in notes_of(chart, Instrument.GUITAR, d)), d
    assert {c["difficulty"] for c in result.cascaded} == {"hard", "medium", "easy"}
    assert all(c["change"] == "removed" and c["tick"] == 0 for c in result.cascaded)


def test_deleting_part_of_a_chord_leaves_the_levels_below_alone():
    chart = levelled()  # k = 2: tick 192 is a chord on Expert, a single note on Hard
    lanes = [n[1] for n in notes_of(chart, Instrument.GUITAR, E) if n[0] == 192]
    result = run(chart, "guitar", "expert", {"kind": "delete", "notes": [[192, lanes[0]]]})
    assert result.cascaded == []
    assert any(n[0] == 192 for n in notes_of(chart, Instrument.GUITAR, H))


def test_moving_a_tick_moves_it_on_the_levels_below_and_a_fret_change_does_not():
    chart = levelled()
    expert0 = [n for n in notes_of(chart, Instrument.GUITAR, E) if n[0] == 0]
    result = run(chart, "guitar", "expert", {"kind": "move", "notes": [[0, n[1]] for n in expert0], "ticks": 48})
    for d in (H, M, Z):
        ticks = [n[0] for n in notes_of(chart, Instrument.GUITAR, d)]
        assert 48 in ticks and 0 not in ticks, d
    assert {c["change"] for c in result.cascaded} == {"moved"}
    hard_before = notes_of(chart, Instrument.GUITAR, H)
    result = run(chart, "guitar", "expert", {"kind": "move", "notes": [[48, expert0[0][1]]], "rows": 1})
    assert result.cascaded == [] and notes_of(chart, Instrument.GUITAR, H) == hard_before


def test_a_note_added_below_is_copied_to_the_levels_above_that_lack_its_tick():
    chart = levelled()
    result = run(chart, "guitar", "medium", {"kind": "add", "notes": [[48, 1]]})
    assert (48, 1, 0, False, False, False) in notes_of(chart, Instrument.GUITAR, E)
    assert (48, 1, 0, False, False, False) in notes_of(chart, Instrument.GUITAR, H)
    assert all(n[0] != 48 for n in notes_of(chart, Instrument.GUITAR, Z))
    assert sorted(c["difficulty"] for c in result.cascaded) == ["expert", "hard"]
    # A tick the levels above already have needs nothing there (Medium has blue at 384, Expert and Hard 384).
    result = run(chart, "guitar", "medium", {"kind": "add", "notes": [[384, 0]]})
    assert result.cascaded == [] and list(result.changed) == [(Instrument.GUITAR, M)]


def test_drum_changes_flow_pad_by_pad():
    chart = levelled()
    result = run(chart, "drums", "expert", {"kind": "delete", "notes": [[0, 2]]})
    for d in (H, M, Z):
        gems = [(n[0], n[1]) for n in notes_of(chart, Instrument.DRUMS, d)]
        assert (0, 2) not in gems, d
    assert (0, 0) in [(n[0], n[1]) for n in notes_of(chart, Instrument.DRUMS, H)]  # the kick stays
    assert {c["difficulty"] for c in result.cascaded} == {"hard", "medium", "easy"}
    result = run(chart, "drums", "expert", {"kind": "move", "notes": [[192, 2]], "rows": 1})
    for d in (H, M, Z):
        assert (192, 3, 0, False, False, True) in notes_of(chart, Instrument.DRUMS, d), d
    result = run(chart, "drums", "expert", {"kind": "flag", "notes": [[192, 3]], "flag": "cymbal", "on": False})
    for d in (H, M, Z):
        assert (192, 3, 0, False, False, False) in notes_of(chart, Instrument.DRUMS, d), d
    result = run(chart, "drums", "hard", {"kind": "flag", "notes": [[192, 3]], "flag": "cymbal", "on": True})
    assert (192, 3, 0, False, False, True) in notes_of(chart, Instrument.DRUMS, E)
    assert {c["difficulty"]: c["change"] for c in result.cascaded}["expert"] == "changed"
    assert chain_errors(chart) == []


def test_unlinked_edits_stay_on_their_level():
    chart = levelled()
    hard = notes_of(chart, Instrument.GUITAR, H)
    result = run(chart, "guitar", "expert", {"kind": "delete", "notes": [[0, n[1]] for n in notes_of(chart, Instrument.GUITAR, E) if n[0] == 0]}, linked=False)
    assert result.cascaded == [] and notes_of(chart, Instrument.GUITAR, H) == hard
    assert any("[HardSingle] has tick 0, but [ExpertSingle] does not" in e for e in chain_errors(chart))


def test_a_level_without_notes_takes_no_part():
    chart = every_feature()  # keys has Easy only; guitar has Expert and Hard
    result = run(chart, "keys", "easy", {"kind": "add", "notes": [[96, 0]]})
    assert result.cascaded == [] and list(result.changed) == [(Instrument.KEYS, Z)]


# ---------------------------------------------------------------- sustains


def test_a_sustain_run_into_the_next_note_is_cut_with_a_notice():
    chart = every_feature()
    result = run(chart, "guitar", "expert", {"kind": "sustain", "notes": [[960, 3]], "length": 400}, linked=False)
    assert (960, 3, 96, True, False, False) in notes_of(chart, Instrument.GUITAR, E)
    assert result.notices == ["A sustain was cut to end on the next note (Expert 1)."]


def test_a_note_added_inside_a_sustain_cuts_it():
    chart = every_feature()  # 864 yellow holds 192 ticks, to 1056
    result = run(chart, "guitar", "expert", {"kind": "delete", "notes": [[960, 3]]}, linked=False)
    assert result.notices == []
    result = run(chart, "guitar", "expert", {"kind": "add", "notes": [[912, 0]]}, linked=False)
    assert (864, 2, 48, False, False, False) in notes_of(chart, Instrument.GUITAR, E)
    assert result.notices and "cut to end on the next note" in result.notices[0]


def test_a_sustain_that_ran_into_the_next_note_before_is_left_alone():
    chart = every_feature()
    guitar = chart.tracks[0]
    guitar.notes = sorted([*guitar.notes[:2], ChartNote(864, 2, length=500), *guitar.notes[3:]])
    result = run(chart, "guitar", "expert", {"kind": "add", "notes": [[96, 0]]}, linked=False)
    assert result.notices == []
    assert (864, 2, 500, False, False, False) in notes_of(chart, Instrument.GUITAR, E)


# ---------------------------------------------------------------- undo and redo


def test_undo_and_redo_step_through_the_history():
    chart = every_feature()
    session = EditSession("x", Path("."), chart)
    start = render(chart)
    session.apply({"version": session.version, **request("guitar", "expert", {"kind": "add", "notes": [[96, 0]]})})
    after = render(chart)
    assert session.state()["unsaved"] == 1 and session.state()["undo"] == "Add a note"
    out = session.undo(session.version)
    assert render(chart) == start and out["label"] == "Add a note" and session.state()["redo"] == "Add a note"
    session.redo(session.version)
    assert render(chart) == after and session.unsaved == 1
    with pytest.raises(StaleError):
        session.undo(session.version - 1)
    session.undo(session.version)
    with pytest.raises(NothingToDoError):
        session.undo(session.version)
    session.apply({"version": session.version, **request("guitar", "expert", {"kind": "add", "notes": [[192, 1]]})})
    assert session.redo_stack == []  # a new edit ends the redo history


def random_request(rng: random.Random, chart: Chart) -> dict:
    """A plausible edit: most can be done, some are refused (a lane taken, a cymbal on red, ...)."""
    tracks = [t for t in chart.tracks if t.notes and t.instrument is not Instrument.KEYS]
    track = rng.choice(tracks)
    drums = track.instrument is Instrument.DRUMS
    last = max(n.tick for n in track.notes)
    picks = rng.sample(track.notes, min(len(track.notes), rng.choice((1, 1, 2, 3))))
    places = [[n.tick, n.lane] for n in picks]
    kind = rng.choice(("add", "add", "delete", "move", "move", "sustain", "flag", "paste"))
    if kind == "add":
        lane = rng.randrange(5)
        cymbal = drums and lane in (2, 3, 4) and rng.random() < 0.5
        op = {"kind": "add", "notes": [[48 * rng.randrange(last // 48 + 8), lane, 0 if drums else rng.choice((0, 0, 96, 400)), CYMBAL if cymbal else 0]]}
    elif kind == "delete":
        op = {"kind": "delete", "notes": places}
    elif kind == "move":
        op = {"kind": "move", "notes": places, "ticks": rng.choice((-96, -48, 0, 48, 96, 192)), "rows": rng.choice((-1, 0, 0, 1))}
    elif kind == "sustain":
        op = {"kind": "sustain", "notes": places, **({"length": rng.choice((0, 96, 300))} if rng.random() < 0.5 else {"delta": rng.choice((-48, 48))})}
    elif kind == "flag":
        op = {"kind": "flag", "notes": places, "flag": "cymbal" if drums else rng.choice(("forced", "tap")), "on": rng.random() < 0.6}
    else:
        start = rng.choice(track.notes).tick
        source = [n for n in track.notes if start <= n.tick < start + 768][:8]
        shift = 192 * rng.randrange(1, 8)
        op = {"kind": "paste", "notes": [[n.tick + shift, n.lane, n.length, (CYMBAL if n.cymbal else 0)] for n in source]}
    return request(track.instrument.value, track.difficulty.value, op, linked=rng.random() < 0.85)


def walk(chart: Chart, seed: int, steps: int) -> tuple[EditSession, list[bytes], int]:
    """Random edits through a session; the bytes after every step taken, and how many were refused."""
    rng = random.Random(seed)
    session = EditSession("x", Path("."), chart)
    renders = [render(chart)]
    refused = 0
    for _ in range(steps):
        version = session.version
        try:
            out = session.apply({"version": version, **random_request(rng, chart)})
        except OpError:
            refused += 1
            assert render(chart) == renders[-1] and session.version == version
            continue
        if out["tracks"]:
            renders.append(render(chart))
        else:
            assert render(chart) == renders[-1]
    return session, renders, refused


def undo_redo_all(session: EditSession, chart: Chart, renders: list[bytes]) -> None:
    for expected in reversed(renders[:-1]):
        session.undo(session.version)
        assert render(chart) == expected
    assert session.unsaved == 0
    for expected in renders[1:]:
        session.redo(session.version)
        assert render(chart) == expected


@pytest.mark.parametrize("seed", range(12))
def test_random_edits_undo_and_redo_to_the_byte(seed):
    chart = levelled()
    session, renders, refused = walk(chart, seed, 60)
    assert len(renders) > 25, f"only {len(renders) - 1} steps taken, {refused} refused"
    undo_redo_all(session, chart, renders)


@pytest.mark.parametrize("seed", range(12))
def test_linked_edits_keep_every_level_inside_the_one_above(seed):
    rng = random.Random(1000 + seed)
    chart = levelled()
    for _ in range(60):
        req = random_request(rng, chart)
        req["linked"] = True
        try:
            run(chart, req["instrument"], req["difficulty"], req["op"])
        except OpError:
            continue
        assert chain_errors(chart) == [], req


@pytest.mark.real
def test_random_edits_on_a_real_song_undo_to_the_byte():
    path = OUTPUTS / "Davul Testi - LastResort" / "notes.chart"
    if not path.is_file():
        skip_missing(path)
    chart = read_chart_file(path)
    session, renders, _ = walk(chart, 7, 80)
    assert renders[0] == path.read_bytes()
    undo_redo_all(session, chart, renders)
    assert render(chart) == renders[-1]
