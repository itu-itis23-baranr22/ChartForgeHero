"""The validator's messages in plain words for the editor's problem list (E.2).

The validator speaks the file's language ("[HardSingle] has tick 6160, but [ExpertSingle] does not"); the
page shows where a problem is (bar, beat, instrument, level) next to what :func:`explain` says about it. A
message no rule here knows is shown as the validator wrote it.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from chartgen.clonehero.chart_format import section_name
from chartgen.core.model import Difficulty, Instrument

_TRACKS = {section_name(i, d): (i, d) for i in Instrument for d in Difficulty}
_INSTRUMENT = {Instrument.GUITAR: "guitar", Instrument.BASS: "bass", Instrument.DRUMS: "drums", Instrument.KEYS: "keys"}


def _level(section: str) -> str:
    track = _TRACKS.get(section)
    return track[1].value.capitalize() if track else section


def _instrument(section: str) -> Instrument | None:
    track = _TRACKS.get(section)
    return track[0] if track else None


def _chord(m: re.Match[str]) -> str:
    count = m["count"]
    if _instrument(m["section"]) is Instrument.BASS:
        return f"A chord of {count} notes: bass has single notes only."
    level = _level(m["section"])
    if level == "Easy":
        return f"A chord of {count} notes: Easy has single notes only."
    return f"A chord of {count} notes: {level} has chords of at most two notes."


_RULES: list[tuple[re.Pattern[str], Callable[[re.Match[str]], str]]] = [
    (
        re.compile(r"^\[(?P<lower>\w+)\] has tick \d+, but \[(?P<upper>\w+)\] does not$"),
        lambda m: f"{_level(m['lower'])} has a note here and {_level(m['upper'])} has none: every note of a level "
                  f"must also be on the level above it.",
    ),
    (re.compile(r"^\[(?P<section>\w+)\] tick \d+: a chord of (?P<count>\d+) notes$"), _chord),
    (
        re.compile(r"^\[(?P<section>\w+)\] tick \d+: orange is not allowed here$"),
        lambda m: f"Orange on {_level(m['section'])}: Medium and Easy have no orange.",
    ),
    (
        re.compile(r"^\[\w+\] tick \d+: the sustain runs into the next note$"),
        lambda m: "This sustain runs into the next note.",
    ),
    (
        re.compile(r"^\[\w+\] tick \d+: (?P<count>\d+) pads at once, more than two hands$"),
        lambda m: f"{m['count']} pads at once: two hands play at most two.",
    ),
    (
        re.compile(r"^\[(?P<section>\w+)\] tick \d+: (?P<count>\d+) gems at once, at most (?P<limit>\d+) here$"),
        lambda m: f"{m['count']} notes at once: {_level(m['section'])} drums have at most {m['limit']}.",
    ),
    (
        re.compile(r"^\[\w+\] tick \d+: the kick with a pad$"),
        lambda m: "The kick together with a pad: Easy drums never have both at once.",
    ),
    (
        re.compile(r"^\[(?P<section>\w+)\] tick \d+: a sixteenth$"),
        lambda m: f"A note on a sixteenth: {_level(m['section'])} drums have nothing between the eighths.",
    ),
    (
        re.compile(r"^\[(?P<lower>\w+)\] tick \d+: (?P<gem>.+) is not in \[(?P<upper>\w+)\]$"),
        lambda m: f"The {m['gem']} is not on {_level(m['upper'])}: every note of a level must also be on the level "
                  f"above it, a cymbal as a cymbal.",
    ),
    (
        re.compile(r"^\[\w+\] tick \d+: a (?P<colour>\w+) cymbal flag without a \w+ note$"),
        lambda m: f"A {m['colour']} cymbal mark with no {m['colour']} note under it.",
    ),
    (
        re.compile(r"^\[\w+\] tick \d+: star power is not on a bar line$"),
        lambda m: "A star power phrase starts here, off the bar line.",
    ),
    (
        re.compile(r"^\[\w+\] tick \d+: star power holds no note$"),
        lambda m: "A star power phrase starts here and holds no note.",
    ),
    (
        re.compile(r"^\[\w+\] tick \d+: star power overlaps the phrase before it$"),
        lambda m: "A star power phrase starts here, inside the phrase before it.",
    ),
    (
        re.compile(r"^\[\w+\] tick \d+: star power starts before the song does \(Song at tick \d+\)$"),
        lambda m: "A star power phrase starts here, before the song does.",
    ),
    (
        re.compile(r"^\[\w+\] tick \d+: a note in the opening that ends at (?P<end>[\d.]+) s$"),
        lambda m: f"A note in the opening, which is not part of the song (it ends at {m['end']} s).",
    ),
    (
        re.compile(r"^\[Events\] tick \d+: section name (?P<name>.+) is not plain ASCII$"),
        lambda m: f"The section name {m['name']} is not plain ASCII (no accents or other scripts).",
    ),
    (
        re.compile(r"^\[Events\] tick \d+: section (?P<name>.+) is not on a bar line$"),
        lambda m: f"The section {m['name']} starts off the bar line.",
    ),
    (
        re.compile(r"^\[Events\] tick \d+: section (?P<name>.+) lasts less than (?P<bars>\d+) bars$"),
        lambda m: f"The section {m['name']} lasts less than {m['bars']} bars: a section is at least {m['bars']} bars long.",
    ),
    (
        re.compile(r"^song\.ini preview_start_time \d+ ms is in the opening: the song starts at \d+ ms$"),
        lambda m: "The preview starts in the opening, before the song does.",
    ),
    (
        re.compile(r"^song\.ini preview_start_time \d+ ms is past the song's end \(\d+ ms\)$"),
        lambda m: "The preview starts after the song has ended.",
    ),
    (
        re.compile(r"^song\.ini preview_start_time \d+ ms: its (?P<s>\d+) s do not fit in the \d+ ms song$"),
        lambda m: f"The preview's {m['s']} seconds run past the song's end: start it earlier.",
    ),
    (
        re.compile(r"^\[(?P<section>\w+)\] has no notes$"),
        lambda m: f"{_level(m['section'])} {_INSTRUMENT.get(_instrument(m['section']), m['section'])} has no notes.",
    ),
    (
        re.compile(r"^(?P<instrument>\w+) has no notes but (?P<key>diff_\w+) = -?\d+$"),
        lambda m: f"No {m['instrument']} notes are left, but song.ini still gives {m['instrument']} a difficulty "
                  f"({m['key']}).",
    ),
    (
        re.compile(r"^(?P<instrument>\w+) has notes but (?P<key>diff_\w+) = -1$"),
        lambda m: f"The {m['instrument']} chart has notes, but song.ini says it has none ({m['key']} = -1).",
    ),
]


def explain(message: str) -> str:
    """The validator's message in plain words, without the track and tick the page shows beside it."""
    for pattern, words in _RULES:
        match = pattern.match(message)
        if match:
            return words(match)
    return message
