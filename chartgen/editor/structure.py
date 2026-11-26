"""Editing a song's structure (E.4.1 d): sections, star power phrases and the preview's start.

Each change is one undo step, like a note operation (SPEC 50); everything lands on a bar line, as the validator
wants. Star power changes all levels of the instrument by default, the build's rule (the same phrases on every
level, SPEC 40); a phrase is the same phrase on another level when it starts on the same tick. What the model
cannot hold is refused (a blank name, a second section on one bar, a phrase or section before the start, a
phrase shorter than a bar); what only breaks a validator rule (a section shorter than four bars, a phrase that
holds no note) is allowed and shown by the live check. The preview's start belongs to ``song.ini``
(``preview_start_time``), which a save then writes as well.
"""

from __future__ import annotations

import bisect
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from chartgen.core.model import Chart, Difficulty, Instrument, Section, StarPowerPhrase
from chartgen.editor.ops import LEVELS, OpError

KINDS = frozenset({
    "section_add", "section_rename", "section_move", "section_delete",
    "sp_add", "sp_move", "sp_resize", "sp_delete", "preview_set",
})


@dataclass
class Change:
    """What a structure operation changes: new sections, new star power per track, a new preview (ms)."""

    label: str
    sections: list[Section] | None = None
    star_power: dict[tuple[Instrument, Difficulty], list[StarPowerPhrase]] = field(default_factory=dict)
    preview_ms: int | None = None
    selected: dict[str, Any] | None = None
    """The item to keep selected on the page afterwards: {"kind": ..., "tick": ...}."""


def _int(value: Any, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise OpError(f"{what} must be a whole number, not {value!r}")
    return value


def _bar_index(bars: Sequence[int], tick: int) -> int:
    """The index of the bar line at ``tick``; a tick between bar lines is refused."""
    index = bisect.bisect_left(bars, tick)
    if index >= len(bars) or bars[index] != tick:
        raise OpError(f"Tick {tick} is not on a bar line.")
    return index


def _shift(bars: Sequence[int], tick: int, by: int) -> int:
    index = _bar_index(bars, tick) + by
    if index < 0:
        raise OpError("There is no bar before the first one.")
    if index >= len(bars):
        raise OpError("There is no bar after the song's end.")
    return bars[index]


def _bar_number(bars: Sequence[int], tick: int) -> int:
    return bisect.bisect_right(bars, tick)


def _name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OpError("A section needs a name.")
    name = " ".join(value.split())
    if '"' in name:
        raise OpError('A section name cannot hold a double quote (").')
    if len(name) > 60:
        raise OpError("A section name is at most 60 characters.")
    return name


def _sections(chart: Chart, op: Mapping[str, Any], kind: str, bars: Sequence[int]) -> Change:
    sections = list(chart.sections)
    at = {s.tick: s for s in sections}
    tick = _int(op.get("tick"), "a section's tick")
    if kind == "section_add":
        _bar_index(bars, tick)
        if tick in at:
            raise OpError(f"Bar {_bar_number(bars, tick)} already has a section ({at[tick].name}).")
        name = _name(op.get("name"))
        sections.append(Section(tick, name))
        label = f"Add section {name}"
    else:
        if tick not in at:
            raise OpError(f"There is no section at tick {tick} any more: reload the page.")
        old = at[tick]
        sections.remove(old)
        if kind == "section_rename":
            name = _name(op.get("name"))
            if name == old.name:
                return Change("Rename section")
            sections.append(Section(tick, name))
            label = f"Rename section {old.name} to {name}"
        elif kind == "section_move":
            to = _shift(bars, tick, _int(op.get("bars"), "the bars to move by"))
            if to in at and to != tick:
                raise OpError(f"Bar {_bar_number(bars, to)} already has a section ({at[to].name}).")
            sections.append(Section(to, old.name))
            tick = to
            label = f"Move section {old.name}"
        else:
            label = f"Delete section {old.name}"
            tick = None
    sections.sort(key=lambda s: s.tick)
    return Change(label, sections=sections, selected={"kind": "section", "tick": tick} if tick is not None else None)


def _levels(chart: Chart, instrument: Instrument, difficulty: Difficulty, all_levels: bool):
    tracks = {t.difficulty: t for t in chart.tracks if t.instrument is instrument}
    if difficulty not in tracks:
        raise OpError(f"This song has no {difficulty.value} {instrument.value} chart.")
    if not all_levels:
        return [tracks[difficulty]]
    # Every level with notes, and the edited one in any case.
    return [tracks[d] for d in LEVELS if d in tracks and (tracks[d].notes or d is difficulty)]


def _star_power(chart: Chart, op: Mapping[str, Any], kind: str, bars: Sequence[int],
                instrument: Instrument, difficulty: Difficulty) -> Change:
    all_levels = op.get("all_levels", True)
    if not isinstance(all_levels, bool):
        raise OpError("all_levels must be true or false")
    tick = _int(op.get("tick"), "a phrase's tick")
    levels = _levels(chart, instrument, difficulty, all_levels)
    edited = next(t for t in levels if t.difficulty is difficulty)
    phrase = next((p for p in edited.star_power if p.tick == tick), None)
    change = Change("")
    if kind == "sp_add":
        _bar_index(bars, tick)
        bar_count = _int(op.get("bars", 1), "a phrase's length in bars")
        if bar_count < 1:
            raise OpError("A star power phrase is at least one bar long.")
        end = _shift(bars, tick, bar_count)
        if phrase is not None:
            raise OpError(f"Bar {_bar_number(bars, tick)} already starts a star power phrase.")
        for track in levels:
            kept = [p for p in track.star_power if p.tick != tick]
            change.star_power[(instrument, track.difficulty)] = sorted([*kept, StarPowerPhrase(tick, end - tick)], key=lambda p: p.tick)
        change.label = "Add star power"
        change.selected = {"kind": "sp", "tick": tick}
        return change
    if phrase is None:
        raise OpError(f"There is no star power phrase at tick {tick} any more: reload the page.")
    start_index = _bar_index(bars, tick)
    end_index = bisect.bisect_left(bars, tick + phrase.length)
    if kind == "sp_delete":
        new = None
        change.label = "Delete star power"
    elif kind == "sp_move":
        by = _int(op.get("bars"), "the bars to move by")
        start, end = start_index + by, end_index + by
        if start < 0 or end >= len(bars):
            raise OpError("The phrase cannot move past the song's first or last bar.")
        new = StarPowerPhrase(bars[start], bars[end] - bars[start])
        change.label = "Move star power"
    else:
        by = _int(op.get("bars"), "the bars to lengthen by")
        end = end_index + by
        if end <= start_index:
            raise OpError("A star power phrase is at least one bar long.")
        if end >= len(bars):
            raise OpError("The phrase cannot run past the song's last bar.")
        new = StarPowerPhrase(tick, bars[end] - tick)
        change.label = "Lengthen star power" if by > 0 else "Shorten star power"
    for track in levels:
        if track is not edited and not any(p.tick == tick for p in track.star_power):
            continue  # this level has no phrase here: nothing of it to change
        kept = [p for p in track.star_power if p.tick != tick]
        if new is not None:
            if any(p.tick == new.tick for p in kept):
                raise OpError(f"Bar {_bar_number(bars, new.tick)} already starts a star power phrase.")
            kept.append(new)
        change.star_power[(instrument, track.difficulty)] = sorted(kept, key=lambda p: p.tick)
    change.selected = {"kind": "sp", "tick": new.tick} if new is not None else None
    return change


def apply(chart: Chart, request: Mapping[str, Any], bars: Sequence[int], seconds_at) -> Change:
    """One structure operation on a copy of the chart's sections and phrases; see the module.

    ``bars`` are the song's bar-line ticks (to the end of the song); ``seconds_at`` turns a tick into seconds.
    """
    op = request.get("op")
    kind = op.get("kind") if isinstance(op, Mapping) else None
    if kind not in KINDS:
        raise OpError(f"no such operation: {kind!r}")
    if kind.startswith("section_"):
        return _sections(chart, op, kind, bars)
    if kind == "preview_set":
        tick = _int(op.get("tick"), "the preview's tick")
        _bar_index(bars, tick)
        return Change("Set the preview", preview_ms=round(seconds_at(tick) * 1000), selected={"kind": "preview", "tick": tick})
    try:
        instrument = Instrument(request.get("instrument"))
        difficulty = Difficulty(request.get("difficulty"))
    except ValueError:
        raise OpError("a star power change names an instrument and a level") from None
    return _star_power(chart, op, kind, bars, instrument, difficulty)
