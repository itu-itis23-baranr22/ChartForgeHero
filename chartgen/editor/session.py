"""The songs open in the editor, each with its undo and redo history (SPEC 50; E.2).

A session holds the chart in memory while the server runs, so reloading the page keeps the edits; they are
lost when the server stops until saving and drafts arrive (E.3). A session with no history is read from disk
again when the song is opened and its ``notes.chart`` has changed, so a chart changed by another tool is seen.

Every change gives the session a new version number, unique for the server's life: a page that sends an
operation with an older number was looking at an older chart (another tab, a restarted server) and is
refused instead of editing notes it cannot see.
"""

from __future__ import annotations

import gc
import hashlib
import itertools
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chartgen.clonehero.chart_format import DotChartExporter
from chartgen.clonehero.chart_reader import read_chart
from chartgen.core.model import Chart, ChartNote, Difficulty, Instrument
from chartgen.editor import ops
from chartgen.editor.songs import SongLibrary, track_json
from chartgen.errors import ChartgenError, ChartReadError

MAX_STEPS = 1000
"""Undo steps kept; older ones are dropped (the edits stay, only their undo goes)."""

Key = tuple[Instrument, Difficulty]
_VERSIONS = itertools.count(1)


class StaleError(ChartgenError):
    """The page asked about a chart version that is not the session's any more."""


class NothingToDoError(ChartgenError):
    """Undo with no step to undo, or redo with none to redo."""


@dataclass
class Step:
    label: str
    before: dict[Key, list[ChartNote]]
    after: dict[Key, list[ChartNote]]


class EditSession:
    """One open song: its chart, its version and its undo and redo steps. Thread-safe."""

    def __init__(self, name: str, folder: Path, chart: Chart, disk_sha256: str = "") -> None:
        self.name = name
        self.folder = folder
        self.chart = chart
        self.disk_sha256 = disk_sha256
        """The hash of the ``notes.chart`` the chart was read from."""
        self.version = next(_VERSIONS)
        self.unsaved = 0
        """Steps since the chart was read: the page's count of unsaved edits."""
        self.undo_stack: list[Step] = []
        self.redo_stack: list[Step] = []
        self.lock = threading.Lock()
        self._tracks = {(t.instrument, t.difficulty): t for t in chart.tracks}

    @property
    def has_history(self) -> bool:
        return bool(self.undo_stack or self.redo_stack or self.unsaved)

    def state(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "unsaved": self.unsaved,
            "undo": self.undo_stack[-1].label if self.undo_stack else None,
            "redo": self.redo_stack[-1].label if self.redo_stack else None,
        }

    def _check(self, version: Any) -> None:
        if version != self.version:
            raise StaleError("This chart was changed in another tab or window, or the editor was restarted: reload the page.")

    def _put(self, notes: Mapping[Key, list[ChartNote]]) -> None:
        for key, value in notes.items():
            self._tracks[key].notes = list(value)

    def _tracks_json(self, keys: list[Key]) -> list[dict[str, Any]]:
        return [track_json(self._tracks[key]) for key in keys]

    def apply(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """One operation (``ops.apply``) as one undo step; an operation that changes nothing is no step."""
        with self.lock:
            self._check(request.get("version"))
            result = ops.apply(self.chart, request)
            if result.changed:
                before = {key: list(self._tracks[key].notes) for key in result.changed}
                self._put(result.changed)
                self.undo_stack.append(Step(result.label, before, result.changed))
                del self.undo_stack[:-MAX_STEPS]
                self.redo_stack.clear()
                self.unsaved += 1
                self.version = next(_VERSIONS)
            return {
                "edit": self.state(),
                "label": result.label,
                "tracks": self._tracks_json(list(result.changed)),
                "selection": [list(p) for p in result.selection],
                "cascaded": result.cascaded,
                "notices": result.notices,
            }

    def undo(self, version: Any) -> dict[str, Any]:
        with self.lock:
            self._check(version)
            if not self.undo_stack:
                raise NothingToDoError("There is nothing to undo.")
            step = self.undo_stack.pop()
            self._put(step.before)
            self.redo_stack.append(step)
            self.unsaved -= 1
            self.version = next(_VERSIONS)
            return {"edit": self.state(), "label": step.label, "tracks": self._tracks_json(list(step.before))}

    def redo(self, version: Any) -> dict[str, Any]:
        with self.lock:
            self._check(version)
            if not self.redo_stack:
                raise NothingToDoError("There is nothing to redo.")
            step = self.redo_stack.pop()
            self._put(step.after)
            self.undo_stack.append(step)
            self.unsaved += 1
            self.version = next(_VERSIONS)
            return {"edit": self.state(), "label": step.label, "tracks": self._tracks_json(list(step.after))}

    def chart_text(self) -> tuple[int, str]:
        """The chart as it would be saved, and the version it belongs to."""
        with self.lock:
            return self.version, DotChartExporter().render(self.chart).decode("utf-8-sig")


class Sessions:
    """The open songs of one server, by folder name.

    With ``freeze_gc`` (the ``chartgen edit`` server), every song read is followed by one garbage collection
    and ``gc.freeze()``: the chart's tens of thousands of notes are then left out of later full collections,
    which otherwise stalled an edit now and then by 40-100 ms (measured on LastResort, 2026-11-25). Notes
    dropped later are still freed by reference counting; only garbage in reference cycles would stay. Tests
    leave it off, as a frozen test process would keep such garbage for the rest of the run.
    """

    def __init__(self, library: SongLibrary, freeze_gc: bool = False) -> None:
        self.library = library
        self.freeze_gc = freeze_gc
        self._open: dict[str, EditSession] = {}
        self._lock = threading.Lock()

    def open(self, name: str) -> EditSession:
        """The song's session. One with edits or undo history is kept as it is; one without is read again
        when its ``notes.chart`` changed on disk (another tool edited it), and kept, version and all, when
        it did not, so that opening the song in a second tab does not refuse the first."""
        folder = self.library.folder(name)
        path = folder / "notes.chart"
        try:
            data = path.read_bytes()
        except OSError as error:
            raise ChartReadError(f"cannot read {path}: {error}") from error
        digest = hashlib.sha256(data).hexdigest()
        with self._lock:
            session = self._open.get(name)
            if session is None or (not session.has_history and session.disk_sha256 != digest):
                try:
                    text = data.decode("utf-8-sig")
                except UnicodeDecodeError as error:
                    raise ChartReadError(f"cannot read {path}: {error}") from error
                session = EditSession(name, folder, read_chart(text), digest)
                self._open[name] = session
                if self.freeze_gc:
                    gc.collect()
                    gc.freeze()
            return session

    def current(self, name: str) -> EditSession | None:
        """The song's session if it is open, without reading anything."""
        self.library.folder(name)
        with self._lock:
            return self._open.get(name)
