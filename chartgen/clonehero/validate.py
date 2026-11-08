"""Independent checks of generated files.

The parser here deliberately shares no code with the writer, so a bug in the
writer cannot hide itself by being read back the same wrong way.
"""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass, field
from pathlib import Path

import soundfile as sf

from chartgen.clonehero.chart_format import DIFFICULTY_SECTIONS, INSTRUMENT_SECTIONS
from chartgen.clonehero.song_ini import DIFFICULTY_KEYS, NOT_CHARTED
from chartgen.core.model import Instrument

_SECTION_RE = re.compile(r"^\[(?P<name>[^\]]+)\]$")
_EVENT_RE = re.compile(r"^(?P<tick>\d+)\s*=\s*(?P<type>[A-Za-z]+)\s*(?P<args>.*)$")
_NUMERIC_ARGS_RE = re.compile(r"^\d+(\s+\d+)*$")

_FRET_NOTES = frozenset(range(8))
_DRUM_NOTES = frozenset({0, 1, 2, 3, 4, 5, 32, *range(34, 39), *range(40, 45), 66, 67, 68})
_STAR_POWER = 2

_PLAYABLE_SECTIONS: dict[str, Instrument] = {
    f"{difficulty}{section}": instrument
    for instrument, section in INSTRUMENT_SECTIONS.items()
    for difficulty in DIFFICULTY_SECTIONS.values()
}
_KNOWN_SECTIONS = frozenset({"Song", "SyncTrack", "Events", *_PLAYABLE_SECTIONS})


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, other: "ValidationReport") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


@dataclass(frozen=True)
class ParsedEvent:
    line_number: int
    tick: int
    type: str
    args: str


@dataclass
class ParsedChart:
    fields: dict[str, str] = field(default_factory=dict)
    sections: dict[str, list[ParsedEvent]] = field(default_factory=dict)

    def note_count(self, section: str) -> int:
        return sum(event.type == "N" for event in self.sections.get(section, []))


def parse_chart(text: str, report: ValidationReport) -> ParsedChart:
    """Parse .chart text, recording structural problems in ``report``."""
    parsed = ParsedChart()
    current: str | None = None
    inside = False
    for line_number, raw_line in enumerate(text.lstrip("﻿").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        section_match = _SECTION_RE.match(line)
        if section_match:
            if inside:
                report.errors.append(f"line {line_number}: section opened before '}}'")
            current = section_match["name"]
            if current in parsed.sections or (current == "Song" and parsed.fields):
                report.errors.append(f"line {line_number}: duplicate section [{current}]")
            if current not in _KNOWN_SECTIONS:
                report.errors.append(f"line {line_number}: unknown section [{current}]")
            parsed.sections.setdefault(current, [])
        elif line == "{":
            if current is None or inside:
                report.errors.append(f"line {line_number}: unexpected '{{'")
            inside = True
        elif line == "}":
            if not inside:
                report.errors.append(f"line {line_number}: unexpected '}}'")
            inside = False
        elif not inside or current is None:
            report.errors.append(f"line {line_number}: content outside a section")
        elif current == "Song":
            key, separator, value = line.partition("=")
            if not separator:
                report.errors.append(f"line {line_number}: malformed [Song] line")
            else:
                parsed.fields[key.strip()] = value.strip()
        else:
            event_match = _EVENT_RE.match(line)
            if not event_match:
                report.errors.append(f"line {line_number}: malformed event: {line!r}")
                continue
            parsed.sections[current].append(
                ParsedEvent(
                    line_number,
                    int(event_match["tick"]),
                    event_match["type"],
                    event_match["args"].strip(),
                )
            )
    if inside:
        report.errors.append("file ends inside a section")
    return parsed


def _check_tick_order(name: str, events: list[ParsedEvent], report: ValidationReport) -> None:
    for earlier, later in zip(events, events[1:]):
        if later.tick < earlier.tick:
            report.errors.append(
                f"[{name}] line {later.line_number}: tick {later.tick} after {earlier.tick}"
            )


def _check_sync_track(events: list[ParsedEvent], report: ValidationReport) -> None:
    has_tempo = has_signature = False
    for event in events:
        if event.type == "B":
            valid = event.args.isdigit() and int(event.args) > 0
            if not valid:
                report.errors.append(f"[SyncTrack] line {event.line_number}: bad tempo")
            has_tempo = has_tempo or (valid and event.tick == 0)
        elif event.type == "TS":
            parts = event.args.split()
            valid = 1 <= len(parts) <= 2 and all(p.isdigit() for p in parts) and int(parts[0]) > 0
            if not valid:
                report.errors.append(f"[SyncTrack] line {event.line_number}: bad time signature")
            has_signature = has_signature or (valid and event.tick == 0)
        elif event.type != "A":
            report.errors.append(
                f"[SyncTrack] line {event.line_number}: unexpected event {event.type!r}"
            )
    if not has_tempo:
        report.errors.append("[SyncTrack] has no tempo (B) at tick 0")
    if not has_signature:
        report.errors.append("[SyncTrack] has no time signature (TS) at tick 0")


def _check_track(name: str, events: list[ParsedEvent], report: ValidationReport) -> None:
    allowed = _DRUM_NOTES if _PLAYABLE_SECTIONS[name] is Instrument.DRUMS else _FRET_NOTES
    for event in events:
        where = f"[{name}] line {event.line_number}"
        parts = event.args.split()
        if event.type not in {"N", "S"} or len(parts) != 2 or not _NUMERIC_ARGS_RE.match(event.args):
            report.errors.append(f"{where}: malformed event {event.type} {event.args!r}")
        elif event.type == "N" and int(parts[0]) not in allowed:
            report.errors.append(f"{where}: note value {parts[0]} out of range")
        elif event.type == "S" and int(parts[0]) != _STAR_POWER:
            report.warnings.append(f"{where}: unusual special phrase {parts[0]}")
    if not any(event.type == "N" for event in events):
        report.warnings.append(f"[{name}] has no notes")


def validate_chart_text(text: str) -> tuple[ParsedChart, ValidationReport]:
    """Check tick order, section names, note ranges and the mandatory fields."""
    report = ValidationReport()
    parsed = parse_chart(text, report)

    resolution = parsed.fields.get("Resolution", "")
    if not (resolution.isdigit() and int(resolution) > 0):
        report.errors.append("[Song] needs a positive Resolution")

    if "SyncTrack" not in parsed.sections:
        report.errors.append("missing [SyncTrack] section")
    else:
        _check_sync_track(parsed.sections["SyncTrack"], report)

    for name, events in parsed.sections.items():
        _check_tick_order(name, events, report)
        if name in _PLAYABLE_SECTIONS:
            _check_track(name, events, report)

    if not any(parsed.note_count(name) for name in _PLAYABLE_SECTIONS):
        report.errors.append("no playable section contains notes")
    return parsed, report


def _read_song_ini(path: Path, report: ValidationReport) -> dict[str, str]:
    parser = configparser.ConfigParser(
        delimiters=("=",), comment_prefixes=(), interpolation=None, strict=False
    )
    try:
        parser.read_string(path.read_text(encoding="utf-8-sig"))
    except (configparser.Error, UnicodeDecodeError) as error:
        report.errors.append(f"song.ini is unreadable: {error}")
        return {}
    sections = {name.lower(): name for name in parser.sections()}
    if "song" not in sections:
        report.errors.append("song.ini has no [song] section")
        return {}
    return dict(parser[sections["song"]])


def _check_audio_lengths(folder: Path, report: ValidationReport) -> None:
    audio_files = sorted(folder.glob("*.ogg"))
    if not audio_files:
        report.errors.append("no .ogg audio file in the song folder")
        return
    if not any(path.name in {"song.ogg", "guitar.ogg"} for path in audio_files):
        report.errors.append("needs song.ogg or guitar.ogg as the main audio stream")
    frames: dict[str, int] = {}
    for path in audio_files:
        try:
            frames[path.name] = sf.info(str(path)).frames
        except (sf.LibsndfileError, RuntimeError) as error:
            report.errors.append(f"{path.name} is not readable audio: {error}")
    if len(set(frames.values())) > 1:
        report.errors.append(f"audio files differ in length: {frames}")


def validate_song_folder(folder: Path) -> ValidationReport:
    """Check that ``folder`` holds what Clone Hero needs to accept a song."""
    report = ValidationReport()
    if not folder.is_dir():
        report.errors.append(f"not a folder: {folder}")
        return report

    chart_path = folder / "notes.chart"
    parsed: ParsedChart | None = None
    if chart_path.is_file():
        parsed, chart_report = validate_chart_text(chart_path.read_text(encoding="utf-8-sig"))
        report.extend(chart_report)
    else:
        report.errors.append("missing notes.chart")

    ini_path = folder / "song.ini"
    ini: dict[str, str] = {}
    if ini_path.is_file():
        ini = _read_song_ini(ini_path, report)
    else:
        report.errors.append("missing song.ini")
    if ini_path.is_file() and ini:
        for key in ("name", "artist"):
            if not ini.get(key, "").strip():
                report.errors.append(f"song.ini has no {key}: Clone Hero would call it a bad song")

    if parsed is not None and ini:
        for instrument, key in DIFFICULTY_KEYS.items():
            charted = any(
                parsed.note_count(f"{difficulty}{INSTRUMENT_SECTIONS[instrument]}")
                for difficulty in DIFFICULTY_SECTIONS.values()
            )
            try:
                declared = int(ini.get(key, str(NOT_CHARTED)))
            except ValueError:
                report.errors.append(f"song.ini {key} is not a number: {ini[key]!r}")
                continue
            if charted and declared == NOT_CHARTED:
                report.errors.append(f"{instrument.value} has notes but {key} = -1")
            if not charted and declared != NOT_CHARTED:
                report.errors.append(f"{instrument.value} has no notes but {key} = {declared}")

    _check_audio_lengths(folder, report)
    return report
