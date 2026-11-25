"""The editor's operations on a chart (SPEC 50; E.2 plan in docs/STATUS.md).

An operation edits one level of one instrument and is one undo step: ``add``, ``delete``, ``move``,
``sustain``, ``flag`` (forced, tap, cymbal) and ``paste``. :func:`apply` never changes the chart it is given;
it returns the new note lists of the tracks that change, and the session puts them in place.

What the model cannot hold is refused with a message and changes nothing: two notes on one lane at one tick,
a note before the start, a drum note with a sustain, an open note, a forced flag or a tap, a cymbal anywhere
but on a drum's yellow, blue or green. What only breaks a rule of the validator (an Easy chord, a Hard note
that Expert lacks, three pads at once) is allowed: the editor's live check shows it, and a chart with such an
error is never saved (owner, 2026-11-25).

With linked levels (the default) changes flow down and additions flow up, so that each level keeps the notes
of the level below it, as the validator wants. A note deleted or moved away on one level is deleted or moved
on the levels below it at the same place: on guitar, bass and keys a place is a tick, and the levels below
follow only once no note of this level is left at that tick; on drums a place is a pad at a tick, and a
cymbal stays a cymbal. A note that arrives at a new place (added, pasted, moved there) is copied to the
levels above that lack that place. A fret change does not flow on guitar, bass and keys, whose lower levels
use their own frets; a pad change on drums does. Sustains, forced and tap belong to their level. Only levels
that have notes take part, as only those are checked.

After every operation a sustain that now runs into the next note is cut to end on it (owner, 2026-11-25); a
sustain that ran into the next note before the operation is left alone.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from chartgen.core.model import CYMBAL_LANES, OPEN_LANE, Chart, ChartNote, Difficulty, Instrument
from chartgen.errors import ChartgenError

LEVELS = (Difficulty.EXPERT, Difficulty.HARD, Difficulty.MEDIUM, Difficulty.EASY)
FORCED, TAP, CYMBAL = 1, 2, 4
"""Bits of a note's flags, as in the chart JSON the page reads (``songs.chart_json``)."""

DRUM_ROWS = (1, 2, 3, 4, 0)
"""Drum lanes in the rows the page draws, top to bottom: red, yellow, blue, green, then the kick."""
_DRUM_ROW = {lane: row for row, lane in enumerate(DRUM_ROWS)}
_FRET_NAMES = ("green", "red", "yellow", "blue", "orange", "open")
_DRUM_NAMES = {0: "kick", 1: "red", 2: "yellow", 3: "blue", 4: "green"}
_MAX_NOTES = 50_000
_MAX_TICK = 10**9

Key = tuple[Instrument, Difficulty]
Place = tuple[int, int]
"""A note's place: (tick, lane)."""


class OpError(ChartgenError):
    """An operation the editor refuses; the chart is left as it was."""


@dataclass
class Result:
    """What an operation did. ``changed`` holds the new, sorted note list of every track that changed; an
    operation that changes nothing has none and is not an undo step."""

    label: str
    changed: dict[Key, list[ChartNote]] = field(default_factory=dict)
    selection: list[Place] = field(default_factory=list)
    """Where the edited notes are now, on the edited level."""
    cascaded: list[dict[str, Any]] = field(default_factory=list)
    """Notes changed on other levels: difficulty, tick, lane and what happened (added, removed, moved,
    changed), at the note's new place (its old one for removed)."""
    notices: list[str] = field(default_factory=list)


class _Level:
    """One level's notes by tick and lane, recording which ticks were touched."""

    def __init__(self, notes: Iterable[ChartNote]) -> None:
        self.by_tick: dict[int, dict[int, ChartNote]] = {}
        for note in notes:
            self.by_tick.setdefault(note.tick, {})[note.lane] = note
        self.touched: set[int] = set()

    def get(self, place: Place) -> ChartNote | None:
        return self.by_tick.get(place[0], {}).get(place[1])

    def at(self, tick: int) -> list[ChartNote]:
        return list(self.by_tick.get(tick, {}).values())

    def put(self, note: ChartNote) -> None:
        self.by_tick.setdefault(note.tick, {})[note.lane] = note
        self.touched.add(note.tick)

    def remove(self, place: Place) -> ChartNote:
        lanes = self.by_tick[place[0]]
        note = lanes.pop(place[1])
        if not lanes:
            del self.by_tick[place[0]]
        self.touched.add(place[0])
        return note

    def take(self, tick: int) -> list[ChartNote]:
        """Remove and return every note at a tick."""
        notes = list(self.by_tick.pop(tick, {}).values())
        if notes:
            self.touched.add(tick)
        return notes

    def ticks(self) -> set[int]:
        return set(self.by_tick)

    def gems(self) -> dict[Place, bool]:
        """Every place and whether its note is a cymbal: a drum gem is its pad and its cymbal flag."""
        return {(t, lane): n.cymbal for t, lanes in self.by_tick.items() for lane, n in lanes.items()}

    def notes(self) -> list[ChartNote]:
        return sorted(n for lanes in self.by_tick.values() for n in lanes.values())


# ---------------------------------------------------------------- reading the request


def _int(value: Any, what: str, low: int = -_MAX_TICK, high: int = _MAX_TICK) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise OpError(f"{what} must be a whole number from {low} to {high}, not {value!r}")
    return value


def _rows(op: Mapping[str, Any], width: int) -> list[Sequence[Any]]:
    rows = op.get("notes")
    if not isinstance(rows, list) or not rows:
        raise OpError("the operation names no notes")
    if len(rows) > _MAX_NOTES:
        raise OpError(f"at most {_MAX_NOTES} notes in one operation")
    for row in rows:
        if not isinstance(row, list) or len(row) < width:
            raise OpError(f"a note must be a list of at least {width} numbers, not {row!r}")
    return rows


def _places(op: Mapping[str, Any]) -> list[Place]:
    places = [(_int(r[0], "a tick", 0), _int(r[1], "a lane", 0, OPEN_LANE)) for r in _rows(op, 2)]
    if len(set(places)) != len(places):
        raise OpError("the operation names a note twice")
    return places


def _name(drums: bool, lane: int) -> str:
    return _DRUM_NAMES[lane] if drums else _FRET_NAMES[lane]


def _note(drums: bool, tick: int, lane: int, length: int = 0, forced: bool = False, tap: bool = False,
          cymbal: bool = False) -> ChartNote:
    """A note the model and the .chart format can hold, or the reason it cannot be one."""
    if tick < 0:
        raise OpError("A note cannot go before the start of the song.")
    if length < 0:
        raise OpError("A sustain cannot be shorter than nothing.")
    if drums:
        if lane == OPEN_LANE:
            raise OpError("Drums have no open notes.")
        if length:
            raise OpError("A drum note has no sustain.")
        if forced or tap:
            raise OpError("A drum note cannot be forced or a tap.")
        if cymbal and lane not in CYMBAL_LANES:
            raise OpError("Only yellow, blue and green can be cymbals: make it a tom first (C).")
    elif cymbal:
        raise OpError("Only drums have cymbals.")
    return ChartNote(tick, lane, length, forced=forced, tap=tap, cymbal=cymbal)


def _new_notes(op: Mapping[str, Any], drums: bool) -> list[ChartNote]:
    notes = []
    for row in _rows(op, 2):
        tick = _int(row[0], "a tick", 0)
        lane = _int(row[1], "a lane", 0, OPEN_LANE)
        length = _int(row[2], "a sustain", 0) if len(row) > 2 else 0
        flags = _int(row[3], "flags", 0, 7) if len(row) > 3 else 0
        notes.append(_note(drums, tick, lane, length, bool(flags & FORCED), bool(flags & TAP), bool(flags & CYMBAL)))
    places = [(n.tick, n.lane) for n in notes]
    if len(set(places)) != len(places):
        raise OpError("Two of these notes are on the same lane at the same tick.")
    return notes


def _existing(level: _Level, places: list[Place], drums: bool) -> list[ChartNote]:
    notes = []
    for place in places:
        note = level.get(place)
        if note is None:
            raise OpError(f"There is no {_name(drums, place[1])} note at tick {place[0]} any more: reload the page.")
        notes.append(note)
    return notes


def _plural(count: int, word: str) -> str:
    return f"a {word}" if count == 1 else f"{count} {word}s"


# ---------------------------------------------------------------- the operations on the edited level


@dataclass
class _Edit:
    label: str
    selection: list[Place]
    move: tuple[int, int] | None = None
    """(ticks, rows) of a move, and the places it moved notes from."""
    sources: list[Place] = field(default_factory=list)


def _put_new(level: _Level, notes: list[ChartNote], drums: bool) -> None:
    for note in notes:
        if level.get((note.tick, note.lane)) is not None:
            raise OpError(f"There is already a {_name(drums, note.lane)} note at tick {note.tick}.")
        level.put(note)


def _add(level: _Level, op: Mapping[str, Any], drums: bool) -> _Edit:
    notes = _new_notes(op, drums)
    _put_new(level, notes, drums)
    return _Edit(f"Add {_plural(len(notes), 'note')}", [(n.tick, n.lane) for n in notes])


def _delete(level: _Level, op: Mapping[str, Any], drums: bool) -> _Edit:
    places = _places(op)
    _existing(level, places, drums)
    for place in places:
        level.remove(place)
    return _Edit(f"Delete {_plural(len(places), 'note')}", [])


def _moved_lane(note: ChartNote, rows: int, drums: bool) -> int:
    if not rows:
        return note.lane
    if drums:
        row = _DRUM_ROW[note.lane] + rows
        if not 0 <= row < len(DRUM_ROWS):
            raise OpError("There is no row above red." if row < 0 else "There is no row below the kick.")
        return DRUM_ROWS[row]
    if note.lane == OPEN_LANE:
        raise OpError("An open note has no lane to move up or down.")
    lane = note.lane + rows
    if not 0 <= lane <= 4:
        raise OpError("There is no lane above green." if lane < 0 else "There is no lane below orange.")
    return lane


def _move(level: _Level, op: Mapping[str, Any], drums: bool) -> _Edit:
    places = _places(op)
    ticks = _int(op.get("ticks", 0), "the ticks to move by")
    rows = _int(op.get("rows", 0), "the rows to move by", -4, 4)
    notes = _existing(level, places, drums)
    if not ticks and not rows:
        return _Edit("Move", places)
    moved = []
    for note in notes:
        lane = _moved_lane(note, rows, drums)
        moved.append(_note(drums, note.tick + ticks, lane, note.length, note.forced, note.tap, note.cymbal))
    for place in places:
        level.remove(place)
    _put_new(level, moved, drums)
    return _Edit(f"Move {_plural(len(places), 'note')}", [(n.tick, n.lane) for n in moved], (ticks, rows), places)


def _sustain(level: _Level, op: Mapping[str, Any], drums: bool) -> _Edit:
    places = _places(op)
    notes = _existing(level, places, drums)
    if drums:
        raise OpError("A drum note has no sustain.")
    if ("length" in op) == ("delta" in op):
        raise OpError("a sustain change gives either a length or a delta")
    for note in notes:
        length = _int(op["length"], "a sustain", 0) if "length" in op else max(0, note.length + _int(op["delta"], "a sustain change"))
        if length != note.length:
            level.put(replace(note, length=length))
    return _Edit(f"Change {_plural(len(places), 'sustain')}", places)


def _flag(level: _Level, op: Mapping[str, Any], drums: bool) -> _Edit:
    places = _places(op)
    notes = _existing(level, places, drums)
    flag = op.get("flag")
    on = op.get("on")
    if not isinstance(on, bool):
        raise OpError("a flag change says on (true) or off (false)")
    if flag in ("forced", "tap"):
        if drums:
            raise OpError("A drum note cannot be forced or a tap.")
        # A forced or tap flag belongs to a tick in the .chart format: it changes the whole chord.
        for tick in sorted({n.tick for n in notes}):
            for note in level.at(tick):
                if getattr(note, flag) != on:
                    level.put(replace(note, **{flag: on}))
        label = f"{'Forced' if flag == 'forced' else 'Tap'} {'on' if on else 'off'}"
    elif flag == "cymbal":
        if not drums:
            raise OpError("Only drums have cymbals.")
        pads = [n for n in notes if n.lane in CYMBAL_LANES]
        if not pads:
            raise OpError("Only yellow, blue and green can be cymbals.")
        for note in pads:
            if note.cymbal != on:
                level.put(replace(note, cymbal=on))
        label = "Make cymbal" if on else "Make tom"
    else:
        raise OpError(f"no such flag: {flag!r}")
    return _Edit(label, places)


def _paste(level: _Level, op: Mapping[str, Any], drums: bool) -> _Edit:
    notes = _new_notes(op, drums)
    first = min(n.tick for n in notes)
    last = max(n.tick for n in notes)
    # Pasting writes over its range, as charting tools do: what was there goes first.
    for tick in [t for t in level.ticks() if first <= t <= last]:
        level.take(tick)
    _put_new(level, notes, drums)
    return _Edit(f"Paste {_plural(len(notes), 'note')}", [(n.tick, n.lane) for n in notes])


_OPERATIONS = {"add": _add, "delete": _delete, "move": _move, "sustain": _sustain, "flag": _flag, "paste": _paste}


# ---------------------------------------------------------------- linked levels


def _same_flags_per_tick(level: _Level) -> None:
    """Forced and tap belong to a tick in the .chart format; a chord whose notes disagree would read back
    with the flag on every note, so it is given to every note now."""
    for tick in sorted(level.touched):
        notes = level.at(tick)
        for flag in ("forced", "tap"):
            if any(getattr(n, flag) for n in notes) and not all(getattr(n, flag) for n in notes):
                for note in notes:
                    if not getattr(note, flag):
                        level.put(replace(note, **{flag: True}))
                notes = level.at(tick)


def _record(cascaded: list[dict[str, Any]], difficulty: Difficulty, note_or_place: ChartNote | Place, change: str) -> None:
    tick, lane = (note_or_place.tick, note_or_place.lane) if isinstance(note_or_place, ChartNote) else note_or_place
    cascaded.append({"difficulty": difficulty.value, "tick": tick, "lane": lane, "change": change})


def _cascade_frets(edited: _Level, before: _Level, edit: _Edit, below: list[tuple[Difficulty, _Level]],
                   above: list[tuple[Difficulty, _Level]], cascaded: list[dict[str, Any]]) -> None:
    after_ticks = edited.ticks()
    before_ticks = before.ticks()
    if edit.move:
        ticks, _ = edit.move
        moved: dict[int, list[Place]] = {}
        for place in edit.sources:
            moved.setdefault(place[0], []).append(place)
        # A tick follows a move once every note this level had there has moved. A fret change alone
        # (no ticks) does not flow: the levels below keep their own frets.
        sources = sorted(t for t, places in moved.items() if len(places) == len(before.at(t))) if ticks else []
        for difficulty, level in below:
            taken = [(t, level.take(t)) for t in sources]
            for tick, notes in taken:
                for note in notes:
                    if level.get((tick + ticks, note.lane)) is None:
                        level.put(replace(note, tick=tick + ticks))
                        _record(cascaded, difficulty, (tick + ticks, note.lane), "moved")
                    else:
                        _record(cascaded, difficulty, note, "removed")
    else:
        for difficulty, level in below:
            for tick in sorted(before_ticks - after_ticks):
                for note in level.take(tick):
                    _record(cascaded, difficulty, note, "removed")
    for difficulty, level in above:
        for tick in sorted(after_ticks - before_ticks):
            if tick not in level.by_tick:
                for note in edited.at(tick):
                    level.put(note)
                    _record(cascaded, difficulty, note, "added")


def _cascade_drums(edited: _Level, before: _Level, edit: _Edit, below: list[tuple[Difficulty, _Level]],
                   above: list[tuple[Difficulty, _Level]], cascaded: list[dict[str, Any]]) -> None:
    after = edited.gems()
    old = before.gems()
    changed = sorted(p for p in after.keys() & old.keys() if after[p] != old[p])
    for difficulty, level in below:
        if edit.move:
            ticks, rows = edit.move
            taken = [level.remove(p) for p in edit.sources if level.get(p) is not None]
            for note in taken:
                lane = DRUM_ROWS[_DRUM_ROW[note.lane] + rows]
                place = (note.tick + ticks, lane)
                if level.get(place) is None:
                    # The gem follows the moved gem above it, cymbal flag included.
                    level.put(ChartNote(place[0], lane, cymbal=after.get(place, False)))
                    _record(cascaded, difficulty, place, "moved")
                else:
                    _record(cascaded, difficulty, note, "removed")
        else:
            for place in sorted(old.keys() - after.keys()):
                if level.get(place) is not None:
                    _record(cascaded, difficulty, level.remove(place), "removed")
        for place in changed:
            note = level.get(place)
            if note is not None and note.cymbal != after[place]:
                level.put(replace(note, cymbal=after[place]))
                _record(cascaded, difficulty, place, "changed")
    for difficulty, level in above:
        for place in sorted((after.keys() - old.keys()) | set(changed)):
            note = level.get(place)
            if note is None:
                level.put(ChartNote(place[0], place[1], cymbal=after[place]))
                _record(cascaded, difficulty, place, "added")
            elif note.cymbal != after[place]:
                level.put(replace(note, cymbal=after[place]))
                _record(cascaded, difficulty, place, "changed")


# ---------------------------------------------------------------- sustains


def _overruns(by_tick: Mapping[int, Mapping[int, ChartNote]]) -> set[int]:
    """The ticks whose longest sustain runs into the next note, as the validator measures it."""
    ticks = sorted(by_tick)
    return {
        tick for tick, following in zip(ticks, ticks[1:])
        if tick + max(n.length for n in by_tick[tick].values()) > following
    }


def _cut_sustains(level: _Level, before: _Level) -> int:
    """Cut every sustain that runs into the next note now and did not before; return how many."""
    new = _overruns(level.by_tick) - _overruns(before.by_tick)
    if not new:
        return 0
    ticks = sorted(level.by_tick)
    following = dict(zip(ticks, ticks[1:]))
    cut = 0
    for tick in new:
        for note in level.at(tick):
            if tick + note.length > following[tick]:
                level.put(replace(note, length=following[tick] - tick))
                cut += 1
    return cut


# ---------------------------------------------------------------- one operation


def _enum(kind: type, value: Any, what: str):
    try:
        return kind(value)
    except ValueError:
        raise OpError(f"no such {what}: {value!r}") from None


def apply(chart: Chart, request: Mapping[str, Any]) -> Result:
    """Do one operation on a copy of the chart's notes and say what changed.

    ``request``: ``instrument``, ``difficulty``, ``linked`` (whether other levels follow; default true) and
    ``op``, an object with ``kind`` and the kind's fields (see the module's operations).

    Raises:
        OpError: The operation is malformed or would make notes the model cannot hold.
    """
    instrument = _enum(Instrument, request.get("instrument"), "instrument")
    difficulty = _enum(Difficulty, request.get("difficulty"), "level")
    linked = request.get("linked", True)
    if not isinstance(linked, bool):
        raise OpError("linked must be true or false")
    op = request.get("op")
    if not isinstance(op, Mapping) or op.get("kind") not in _OPERATIONS:
        raise OpError(f"no such operation: {op.get('kind') if isinstance(op, Mapping) else op!r}")
    tracks = {t.difficulty: t for t in chart.tracks if t.instrument is instrument}
    if difficulty not in tracks:
        raise OpError(f"This song has no {difficulty.value} {instrument.value} chart.")
    drums = instrument is Instrument.DRUMS

    old = {d: _Level(t.notes) for d, t in tracks.items()}
    work = {d: _Level(t.notes) for d, t in tracks.items()}
    edited = work[difficulty]
    edit = _OPERATIONS[op["kind"]](edited, op, drums)
    result = Result(edit.label, selection=edit.selection)

    if linked:
        # Only levels with notes are checked against each other, so only they follow.
        written = [d for d in LEVELS if d in tracks and tracks[d].notes and d is not difficulty]
        below = [(d, work[d]) for d in written if LEVELS.index(d) > LEVELS.index(difficulty)]
        above = [(d, work[d]) for d in written if LEVELS.index(d) < LEVELS.index(difficulty)]
        cascade = _cascade_drums if drums else _cascade_frets
        cascade(edited, old[difficulty], edit, below, above, result.cascaded)

    cut: dict[Difficulty, int] = {}
    for d, level in work.items():
        if not drums:
            _same_flags_per_tick(level)
            count = _cut_sustains(level, old[d])
            if count:
                cut[d] = count
    if cut:
        where = ", ".join(f"{d.value.capitalize()} {n}" for d, n in cut.items())
        total = sum(cut.values())
        result.notices.append(
            f"{'A sustain was' if total == 1 else f'{total} sustains were'} cut to end on the next note ({where})."
        )

    for d, level in work.items():
        notes = level.notes()
        if notes != tracks[d].notes:
            result.changed[(instrument, d)] = notes
    if not result.changed:
        result.cascaded.clear()
    return result
