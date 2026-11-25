"""Reader for the ``.chart`` text format: what :class:`DotChartExporter` writes, back into a :class:`Chart`.

The lines are tokenised by the validator's :func:`parse_chart` and decoded with the writer's own constants,
so the format is described in one place. Anything the writer never writes (an unknown ``[Song]`` field, a
lyric or solo event, a 5-lane drum note, a double kick) is refused rather than dropped: the editor saves
what it read, and a dropped event would be lost on the next save (SPEC 51).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from chartgen.clonehero.chart_format import (
    CYMBAL_FLAGS,
    NOTE_FORCED,
    NOTE_OPEN,
    NOTE_TAP,
    STAR_POWER_PHRASE,
    section_name,
)
from chartgen.clonehero.validate import ParsedEvent, ValidationReport, parse_chart
from chartgen.core.model import (
    OPEN_LANE,
    Chart,
    ChartNote,
    Difficulty,
    Instrument,
    Section,
    SongMetadata,
    StarPowerPhrase,
    Track,
)
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent
from chartgen.errors import ChartReadError

_TRACKS: dict[str, tuple[Instrument, Difficulty]] = {
    section_name(instrument, difficulty): (instrument, difficulty)
    for instrument in Instrument
    for difficulty in Difficulty
}
_SONG_FIELDS = frozenset({"Name", "Artist", "Album", "Genre", "Charter", "Offset", "Resolution"})
_QUOTED = re.compile(r'^"(.*)"$')
_SECTION_EVENT = re.compile(r'^"section (.+)"$')
_CYMBAL_FLAG_LANES = {flag: lane for lane, flag in CYMBAL_FLAGS.items()}
_FRET_LANES = frozenset(range(5))


def read_chart_file(path: Path) -> Chart:
    """Read ``notes.chart`` as the writer wrote it: UTF-8 with a byte order mark."""
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        raise ChartReadError(f"cannot read {path}: {error}") from error
    return read_chart(text)


def read_chart(text: str) -> Chart:
    """Turn ``.chart`` text back into a :class:`Chart`.

    Raises:
        ChartReadError: The text is malformed, or holds something the writer never writes.
    """
    report = ValidationReport()
    parsed = parse_chart(text, report)
    if report.errors:
        raise ChartReadError("the chart is malformed: " + "; ".join(report.errors))
    metadata, resolution = _song(parsed.fields)
    if "SyncTrack" not in parsed.sections:
        raise ChartReadError("the chart has no [SyncTrack]")
    tempo_map = _tempo_map(parsed.sections["SyncTrack"], resolution)
    sections = _sections(parsed.sections.get("Events", []))
    tracks = []
    for name, events in parsed.sections.items():
        if name in {"Song", "SyncTrack", "Events"}:
            continue
        instrument, difficulty = _TRACKS[name]
        tracks.append(_track(name, events, instrument, difficulty))
    try:
        return Chart(metadata, tempo_map, tracks, sections)
    except ValueError as error:
        raise ChartReadError(str(error)) from error


def _unquote(key: str, value: str) -> str:
    match = _QUOTED.match(value)
    if not match:
        raise ChartReadError(f"[Song] {key} is not a quoted string: {value!r}")
    return match[1]


def _song(fields: dict[str, str]) -> tuple[SongMetadata, int]:
    unknown = sorted(set(fields) - _SONG_FIELDS)
    if unknown:
        raise ChartReadError(f"[Song] holds fields chartgen never writes: {', '.join(unknown)}")
    for key in ("Name", "Artist", "Charter", "Offset", "Resolution"):
        if key not in fields:
            raise ChartReadError(f"[Song] has no {key}")
    if fields["Offset"] != "0":
        raise ChartReadError(f"[Song] Offset is {fields['Offset']}; chartgen writes 0 and keeps timing in the tempo map")
    try:
        resolution = int(fields["Resolution"])
    except ValueError as error:
        raise ChartReadError(f"[Song] Resolution is not a number: {fields['Resolution']!r}") from error
    text = {key: _unquote(key, fields[key]) for key in ("Name", "Artist", "Album", "Genre", "Charter") if key in fields}
    try:
        metadata = SongMetadata(
            name=text["Name"],
            artist=text["Artist"],
            album=text.get("Album", ""),
            genre=text.get("Genre", ""),
            charter=text["Charter"],
        )
    except ValueError as error:
        raise ChartReadError(f"[Song]: {error}") from error
    return metadata, resolution


def _numbers(event: ParsedEvent, where: str) -> list[int]:
    try:
        return [int(part) for part in event.args.split()]
    except ValueError as error:
        raise ChartReadError(f"{where} line {event.line_number}: {event.type} {event.args!r} is not numbers") from error


def _tempo_map(events: Iterable[ParsedEvent], resolution: int) -> TempoMap:
    tempos: list[TempoEvent] = []
    signatures: list[TimeSignatureEvent] = []
    for event in events:
        values = _numbers(event, "[SyncTrack]")
        if event.type == "B" and len(values) == 1:
            tempos.append(TempoEvent(event.tick, values[0] / 1000.0))
        elif event.type == "TS" and len(values) in (1, 2):
            denominator = 2 ** values[1] if len(values) == 2 else 4
            signatures.append(TimeSignatureEvent(event.tick, values[0], denominator))
        else:
            raise ChartReadError(f"[SyncTrack] line {event.line_number}: chartgen never writes {event.type} {event.args}")
    try:
        return TempoMap(tempos, signatures, resolution)
    except ValueError as error:
        raise ChartReadError(f"[SyncTrack]: {error}") from error


def _sections(events: Iterable[ParsedEvent]) -> list[Section]:
    sections = []
    for event in events:
        match = _SECTION_EVENT.match(event.args) if event.type == "E" else None
        if not match:
            raise ChartReadError(f"[Events] line {event.line_number}: chartgen writes only sections, not {event.type} {event.args}")
        sections.append(Section(event.tick, match[1]))
    return sections


def _track(name: str, events: Iterable[ParsedEvent], instrument: Instrument, difficulty: Difficulty) -> Track:
    drums = instrument is Instrument.DRUMS
    lanes: dict[int, list[tuple[int, int]]] = {}
    flags: dict[int, set[int]] = {}
    phrases: list[StarPowerPhrase] = []
    for event in events:
        where = f"[{name}] line {event.line_number}"
        if event.type not in ("N", "S"):
            raise ChartReadError(f"{where}: chartgen never writes {event.type} {event.args}")
        values = _numbers(event, f"[{name}]")
        if event.type == "S" and len(values) == 2 and values[0] == STAR_POWER_PHRASE:
            phrases.append(StarPowerPhrase(event.tick, values[1]))
            continue
        if event.type != "N" or len(values) != 2:
            raise ChartReadError(f"{where}: chartgen never writes {event.type} {event.args}")
        number, length = values
        flag = number in _CYMBAL_FLAG_LANES if drums else number in (NOTE_FORCED, NOTE_TAP)
        if flag:
            if length:
                raise ChartReadError(f"{where}: flag N {number} with a length")
            flags.setdefault(event.tick, set()).add(number)
        elif number in _FRET_LANES or (number == NOTE_OPEN and not drums):
            lanes.setdefault(event.tick, []).append((OPEN_LANE if number == NOTE_OPEN else number, length))
        else:
            raise ChartReadError(f"{where}: N {number} is not a note chartgen writes on {instrument.value}")
    notes = []
    for tick in sorted(set(lanes) | set(flags)):
        here = flags.get(tick, set())
        if tick not in lanes:
            raise ChartReadError(f"[{name}] tick {tick}: a flag without a note")
        cymbal_lanes = {_CYMBAL_FLAG_LANES[flag] for flag in here} if drums else set()
        missing = cymbal_lanes - {lane for lane, _ in lanes[tick]}
        if missing:
            raise ChartReadError(f"[{name}] tick {tick}: a cymbal flag without its note")
        for lane, length in lanes[tick]:
            try:
                notes.append(
                    ChartNote(
                        tick,
                        lane,
                        length,
                        forced=NOTE_FORCED in here and not drums,
                        tap=NOTE_TAP in here and not drums,
                        cymbal=lane in cymbal_lanes,
                    )
                )
            except ValueError as error:
                raise ChartReadError(f"[{name}] tick {tick}: {error}") from error
    try:
        return Track(instrument, difficulty, notes, phrases)
    except ValueError as error:
        raise ChartReadError(f"[{name}]: {error}") from error
