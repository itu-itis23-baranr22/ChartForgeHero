"""Writer for the ``.chart`` text format.

Format reference:
https://github.com/TheNathannator/GuitarGame_ChartFormats/tree/main/docs/Chart-File-Formats/chart-format
"""

from __future__ import annotations

from chartgen.core.exporter import ChartExporter
from chartgen.core.model import OPEN_LANE, Chart, ChartNote, Difficulty, Instrument, Track
from chartgen.core.timing import TempoMap

INSTRUMENT_SECTIONS: dict[Instrument, str] = {
    Instrument.GUITAR: "Single",
    Instrument.BASS: "DoubleBass",
    Instrument.DRUMS: "Drums",
    Instrument.KEYS: "Keyboard",
}
DIFFICULTY_SECTIONS: dict[Difficulty, str] = {
    Difficulty.EXPERT: "Expert",
    Difficulty.HARD: "Hard",
    Difficulty.MEDIUM: "Medium",
    Difficulty.EASY: "Easy",
}

NOTE_FORCED = 5
NOTE_TAP = 6
NOTE_OPEN = 7
STAR_POWER_PHRASE = 2


def section_name(instrument: Instrument, difficulty: Difficulty) -> str:
    """Return a track's section name, for example ``ExpertSingle``."""
    return f"{DIFFICULTY_SECTIONS[difficulty]}{INSTRUMENT_SECTIONS[instrument]}"


def _quoted(value: str) -> str:
    """Return ``value`` as a quoted .chart string.

    The format has no escape characters, so a quote inside the value cannot be
    represented and is replaced.
    """
    cleaned = " ".join(value.replace('"', "'").split())
    return f'"{cleaned}"'


def _song_section(chart: Chart) -> list[str]:
    meta = chart.metadata
    lines = [f"  Name = {_quoted(meta.name)}", f"  Artist = {_quoted(meta.artist)}"]
    if meta.album:
        lines.append(f"  Album = {_quoted(meta.album)}")
    if meta.genre:
        lines.append(f"  Genre = {_quoted(meta.genre)}")
    lines.append(f"  Charter = {_quoted(meta.charter)}")
    lines.append("  Offset = 0")
    lines.append(f"  Resolution = {chart.tempo_map.resolution}")
    return lines


def _sync_section(tempo_map: TempoMap) -> list[str]:
    """Render tempo and time signature events; signatures come first on a shared tick."""
    events: list[tuple[int, int, str]] = []
    for signature in tempo_map.time_signatures:
        if signature.denominator == 4:
            value = f"TS {signature.numerator}"
        else:
            exponent = signature.denominator.bit_length() - 1
            value = f"TS {signature.numerator} {exponent}"
        events.append((signature.tick, 0, value))
    for tempo in tempo_map.tempos:
        events.append((tempo.tick, 1, f"B {round(tempo.bpm * 1000)}"))
    return [f"  {tick} = {value}" for tick, _, value in sorted(events)]


def _note_number(note: ChartNote, instrument: Instrument) -> int:
    if note.lane == OPEN_LANE:
        if instrument is Instrument.DRUMS:
            raise ValueError("drum tracks cannot contain open notes")
        return NOTE_OPEN
    return note.lane


def _track_section(track: Track) -> list[str]:
    """Render a track: on a shared tick, notes come first, then flags, then phrases."""
    events: list[tuple[int, int, int, str]] = []
    for note in track.notes:
        number = _note_number(note, track.instrument)
        events.append((note.tick, 0, number, f"N {number} {note.length}"))
        if note.forced:
            events.append((note.tick, 1, NOTE_FORCED, f"N {NOTE_FORCED} 0"))
        if note.tap:
            events.append((note.tick, 1, NOTE_TAP, f"N {NOTE_TAP} 0"))
    for phrase in track.star_power:
        events.append((phrase.tick, 2, STAR_POWER_PHRASE, f"S {STAR_POWER_PHRASE} {phrase.length}"))
    unique_events = sorted(set(events))
    return [f"  {tick} = {value}" for tick, _, _, value in unique_events]


def _block(name: str, body: list[str]) -> list[str]:
    return [f"[{name}]", "{", *body, "}"]


class DotChartExporter(ChartExporter):
    """Writes ``notes.chart``: UTF-8 with a byte order mark and CRLF line endings,
    the form charting tools such as Moonscraper produce."""

    file_name = "notes.chart"

    def render(self, chart: Chart) -> bytes:
        lines = [
            *_block("Song", _song_section(chart)),
            *_block("SyncTrack", _sync_section(chart.tempo_map)),
            *_block(
                "Events",
                [f'  {s.tick} = E {_quoted("section " + s.name)}' for s in chart.sections],
            ),
        ]
        for track in chart.tracks:
            if track.notes:
                name = section_name(track.instrument, track.difficulty)
                lines.extend(_block(name, _track_section(track)))
        return ("\r\n".join(lines) + "\r\n").encode("utf-8-sig")
