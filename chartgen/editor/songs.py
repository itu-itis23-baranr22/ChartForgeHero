"""The song folders the editor can open: listing, safe lookup, and what the page reads from each.

A folder is only ever found by its exact name among the listed folders of the output directory, so no path
the page sends can reach outside it (`..`, an absolute path, `_songs_backup`, a file).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from chartgen.clonehero.chart_format import section_name
from chartgen.clonehero.song_ini import DIFFICULTY_KEYS
from chartgen.clonehero.validate import ValidationReport, read_song_ini, validate_song_folder
from chartgen.core.model import Chart, Difficulty, Instrument, Track
from chartgen.editor.messages import explain
from chartgen.errors import ChartgenError

EDIT_MARK = "chartgen_edits.json"
"""Written by the editor's first save (E.3); a folder holding it counts as edited (SPEC 55)."""

FORCED, TAP, CYMBAL = 1, 2, 4
"""Bits of a note's flags in the chart JSON (the same as ``ops``)."""

_TRACK_OF_SECTION = {section_name(i, d): (i, d) for i in Instrument for d in Difficulty}
_WHERE = re.compile(r"\[(?P<section>\w+)\] (?:has )?tick (?P<tick>\d+)")
"""``[HardSingle] tick 96: ...`` and the level chain's ``[HardSingle] has tick 96, but [ExpertSingle] does not``."""


class SongNotFoundError(ChartgenError):
    """No song folder of that name, or no file of that name in it."""


@dataclass(frozen=True)
class SongLibrary:
    """The song folders under ``root``: every folder holding a ``notes.chart`` whose name does not start
    with ``_`` or ``.`` (``_songs_backup``, ``_experiments`` and the like are not songs)."""

    root: Path

    def folders(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        return sorted(
            (p for p in self.root.iterdir()
             if p.is_dir() and not p.name.startswith(("_", ".")) and (p / "notes.chart").is_file()),
            key=lambda p: p.name.casefold(),
        )

    def folder(self, name: str) -> Path:
        for path in self.folders():
            if path.name == name:
                return path
        raise SongNotFoundError(f"no song folder named {name!r} in {self.root}")

    def audio_file(self, name: str, file_name: str) -> Path:
        folder = self.folder(name)
        for path in folder.glob("*.ogg"):
            if path.name == file_name:
                return path
        raise SongNotFoundError(f"no audio file {file_name!r} in {name!r}")


def _ini(folder: Path) -> dict[str, str]:
    path = folder / "song.ini"
    return read_song_ini(path)[0] if path.is_file() else {}


def _analysis(folder: Path) -> dict[str, object]:
    path = folder / "analysis.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        return {}


def _number(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def song_summary(folder: Path) -> dict[str, object]:
    """One row of the song list, from ``song.ini`` alone so that the list opens quickly."""
    ini = _ini(folder)
    length_ms = _number(ini.get("song_length"))
    tiers = {i: _number(ini.get(key)) for i, key in DIFFICULTY_KEYS.items()}
    charted = [i.value for i, tier in tiers.items() if tier is not None and tier >= 0]
    return {
        "id": folder.name,
        "name": ini.get("name") or folder.name,
        "artist": ini.get("artist", ""),
        "instruments": charted,
        "length_s": round(length_ms / 1000, 3) if length_ms else None,
        "edited": (folder / EDIT_MARK).is_file(),
    }


def track_json(track: Track) -> dict[str, object]:
    """One track as the page draws it: notes as [tick, lane, length, flags], star power as [tick, length]."""
    return {
        "instrument": track.instrument.value,
        "difficulty": track.difficulty.value,
        "notes": [
            [n.tick, n.lane, n.length, (FORCED if n.forced else 0) | (TAP if n.tap else 0) | (CYMBAL if n.cymbal else 0)]
            for n in track.notes
        ],
        "star_power": [[p.tick, p.length] for p in track.star_power],
    }


def chart_json(chart: Chart) -> dict[str, object]:
    """The chart as the page draws it: ticks, never seconds; the page converts with the same tempo map."""
    tracks = [track_json(track) for track in chart.tracks]
    tempo_map = chart.tempo_map
    return {
        "name": chart.metadata.name,
        "artist": chart.metadata.artist,
        "resolution": tempo_map.resolution,
        "tempos": [[t.tick, t.bpm] for t in tempo_map.tempos],
        "time_signatures": [[s.tick, s.numerator, s.denominator] for s in tempo_map.time_signatures],
        "sections": [[s.tick, s.name] for s in chart.sections],
        "tracks": tracks,
    }


def locate(message: str) -> dict[str, object] | None:
    """Where a validator message points, when it names a track and a tick: for the page's markers."""
    match = _WHERE.search(message)
    if not match or match["section"] not in _TRACK_OF_SECTION:
        return None
    instrument, difficulty = _TRACK_OF_SECTION[match["section"]]
    return {"instrument": instrument.value, "difficulty": difficulty.value, "tick": int(match["tick"])}


def validation_json(report: ValidationReport) -> dict[str, list[dict[str, object]]]:
    """The validator's verdict for the problem list: each message in plain words, the validator's own
    words and where it points."""
    def entry(message: str) -> dict[str, object]:
        return {"message": explain(message), "raw": message, "where": locate(message)}

    return {"errors": [entry(m) for m in report.errors], "warnings": [entry(m) for m in report.warnings]}


def song_info(folder: Path, chart_text: str | None = None) -> dict[str, object]:
    """What the side panels show: ``song.ini``, the build's analysis in brief, the audio, the validator's
    verdict (on ``chart_text`` when the editor holds edits, else on the folder's ``notes.chart``)."""
    ini = _ini(folder)
    analysis = _analysis(folder)
    audio = analysis.get("audio_files") if isinstance(analysis.get("audio_files"), dict) else {}
    files = sorted(p.name for p in folder.glob("*.ogg"))
    report = validate_song_folder(folder, chart_text)
    tempo = analysis.get("tempo") if isinstance(analysis.get("tempo"), dict) else {}
    length_ms = _number(ini.get("song_length"))
    return {
        "id": folder.name,
        "song_ini": ini,
        "length_s": round(length_ms / 1000, 3) if length_ms else None,
        "preview_s": (_number(ini.get("preview_start_time")) or 0) / 1000,
        "bpm": tempo.get("bpm"),
        "audio": [{"file": name, "stems": (audio.get(name) or {}).get("stems", [])} for name in files],
        "build_warnings": [w for w in analysis.get("warnings", []) if isinstance(w, str)],
        "validation": validation_json(report),
        "edited": (folder / EDIT_MARK).is_file(),
    }
