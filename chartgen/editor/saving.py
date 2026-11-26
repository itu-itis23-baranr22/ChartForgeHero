"""Saving an edited chart (SPEC 54, E.3.1; owner's decisions 2026-11-25 in docs/STATUS.md, "E.3 planı").

A save writes the chart as the exporter renders it, after checking it with the rest of the folder: a hard-rule
error writes nothing. A ``notes.chart`` that changed on disk since the song was opened is never overwritten.
Before anything is written, the folder's ``notes.chart`` and ``song.ini`` are copied to
``<outputs>/_editor_backups/<song>/<date_time>_<file>`` (all kept); the new files are written next to the old
ones and moved into place, so a failed save leaves the old files. ``song.ini`` changes in its ``diff_*`` lines
only, by the build's own rule (note density over the song's length), and in ``preview_start_time`` when the
preview was moved in the editor (E.4.1 d). Every save appends what it saved to
``chartgen_edits.json``, which also marks the folder as edited for ``build --force`` (SPEC 55).
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chartgen.clonehero.protection import CHART_FILE, EDIT_MARK, read_analysis
from chartgen.clonehero.song_ini import DIFFICULTY_KEYS, NOT_CHARTED, difficulty_tier
from chartgen.clonehero.validate import read_song_ini
from chartgen.core.model import Chart, Instrument
from chartgen.errors import ChartgenError

BACKUP_DIR = "_editor_backups"
SONG_INI = "song.ini"
_DIFF_LINE = re.compile(r"^(?P<key>diff_\w+|preview_start_time)(?P<sep>\s*=\s*)(?P<value>[^\r\n]*)(?P<end>\r?\n?)$")


class SaveRefusedError(ChartgenError):
    """The chart breaks a hard rule: nothing is written."""

    def __init__(self, message: str, errors: int) -> None:
        super().__init__(message)
        self.errors = errors


class DiskChangedError(ChartgenError):
    """``notes.chart`` changed on disk since the song was opened: it is not overwritten."""


def song_duration_s(folder: Path) -> float | None:
    """The song's length as the build measured it: the input's duration, else ``song.ini``'s song_length."""
    analysis = read_analysis(folder) or {}
    source = analysis.get("input")
    if isinstance(source, Mapping) and isinstance(source.get("duration_s"), (int, float)) and source["duration_s"] > 0:
        return float(source["duration_s"])
    if not (folder / SONG_INI).is_file():
        return None
    try:
        length = float(read_song_ini(folder / SONG_INI)[0].get("song_length", ""))
    except ValueError:
        return None
    return length / 1000 if length > 0 else None


def difficulties(chart: Chart, duration_s: float) -> dict[Instrument, int]:
    """The ``diff_*`` value of each instrument with notes, as the build computes it (the densest level)."""
    tiers: dict[Instrument, int] = {}
    for track in chart.tracks:
        if track.notes:
            tier = difficulty_tier(len({note.tick for note in track.notes}), duration_s)
            tiers[track.instrument] = max(tiers.get(track.instrument, 0), tier)
    return tiers


def song_ini_preview_ms(folder: Path) -> int | None:
    """``song.ini``'s preview_start_time in ms, or None when it has none (or not a whole number)."""
    path = folder / SONG_INI
    if not path.is_file():
        return None
    try:
        return int(read_song_ini(path)[0].get("preview_start_time", "").strip())
    except ValueError:
        return None


def song_ini_with(text: str, tiers: Mapping[Instrument, int], preview_ms: int | None = None) -> str:
    """``song.ini`` with new ``diff_*`` values (and ``preview_start_time`` when given) and every other byte as it
    was. An instrument without notes gets ``-1``."""
    values: dict[str, object] = {key: tiers.get(instrument, NOT_CHARTED) for instrument, key in DIFFICULTY_KEYS.items()}
    if preview_ms is not None:
        values["preview_start_time"] = preview_ms
    lines = []
    seen = set()
    for line in text.splitlines(keepends=True):
        match = _DIFF_LINE.match(line)
        if match and match["key"] in values:
            line = f"{match['key']}{match['sep']}{values[match['key']]}{match['end']}"
            seen.add(match["key"])
        lines.append(line)
    if preview_ms is not None and "preview_start_time" not in seen:  # a song.ini without one gets it at the end
        newline = "\r\n" if "\r\n" in text else "\n"
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += newline
        lines.append(f"preview_start_time = {preview_ms}{newline}")
    return "".join(lines)


def prospective_song_ini(folder: Path, chart: Chart, preview_ms: int | None = None) -> str | None:
    """The ``song.ini`` a save would write for ``chart`` (and the preview's start, when given), or None when
    there is no song.ini or no length."""
    path = folder / SONG_INI
    duration = song_duration_s(folder)
    if not path.is_file() or duration is None:
        return None
    if preview_ms is not None and preview_ms == song_ini_preview_ms(folder):
        preview_ms = None  # not moved: its line keeps its bytes (E.4 plan: written only when it changed)
    return song_ini_with(path.read_bytes().decode("utf-8"), difficulties(chart, duration), preview_ms)


def _write_atomically(path: Path, data: bytes) -> None:
    temporary = path.with_name(f".{path.name}.saving")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def back_up(folder: Path, backups: Path) -> list[Path]:
    """Copy the folder's notes.chart and song.ini under ``backups/<song>/<date_time>_<file>``; never overwrite."""
    target = backups / folder.name
    target.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H%M%S")
    suffix = ""
    number = 1
    while any((target / f"{stamp}{suffix}_{name}").exists() for name in (CHART_FILE, SONG_INI)):
        number += 1
        suffix = f"-{number}"
    copies = []
    for name in (CHART_FILE, SONG_INI):
        source = folder / name
        if source.is_file():
            copy = target / f"{stamp}{suffix}_{name}"
            copy.write_bytes(source.read_bytes())
            copies.append(copy)
    return copies


def append_edit_log(folder: Path, entry: Mapping[str, Any]) -> None:
    """Add one save to ``chartgen_edits.json`` (a list of saves): the folder's edit mark (SPEC 55)."""
    path = folder / EDIT_MARK
    try:
        saves = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    except (OSError, ValueError):
        saves = []
    if not isinstance(saves, list):
        saves = [saves]
    saves.append(dict(entry))
    _write_atomically(path, json.dumps(saves, indent=2, ensure_ascii=False).encode("utf-8"))


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
