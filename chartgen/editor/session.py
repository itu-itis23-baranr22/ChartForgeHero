"""The songs open in the editor: undo and redo (SPEC 50; E.2), saving (SPEC 54; E.3.1) and drafts (E.3.2).

A session holds the chart in memory while the server runs, so reloading the page keeps the edits. A session
with no history is read from disk again when the song is opened and its ``notes.chart`` has changed, so a chart
changed by another tool is seen.

Every change gives the session a new version number, unique for the server's life: a page that sends an
operation with an older number was looking at an older chart (another tab, a restarted server) and is
refused instead of editing notes it cannot see.

Unsaved edits are counted from the last save (or from reading the chart): undoing back to it counts none.
About a second after each change the chart is written as a draft to ``<outputs>/_editor_drafts/<song>.json``
with the hash of the ``notes.chart`` it is based on; a save, or undoing every edit, removes it. When a song is
opened and a draft is there, the page offers to restore it if its base is the chart on disk; a draft whose base
changed (a rebuild, another tool) is never restored but renamed ``<song>.<date_time>.stale.json`` and named to
the user (owner's decision 1, 2026-11-25).
"""

from __future__ import annotations

import gc
import hashlib
import itertools
import json
import logging
import os
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chartgen.clonehero.chart_format import DotChartExporter
from chartgen.clonehero.chart_reader import read_chart
from chartgen.clonehero.protection import CHART_FILE
from chartgen.clonehero.validate import validate_song_folder
from chartgen.core.model import Chart, ChartNote, Difficulty, Instrument
from chartgen.editor import ops, saving
from chartgen.editor.songs import SongLibrary, track_json
from chartgen.errors import ChartgenError, ChartReadError

log = logging.getLogger(__name__)

MAX_STEPS = 1000
"""Undo steps kept; older ones are dropped (the edits stay, only their undo goes)."""
DRAFT_DIR = "_editor_drafts"
DRAFT_DELAY_S = 1.0

Key = tuple[Instrument, Difficulty]
_VERSIONS = itertools.count(1)
_STEP_IDS = itertools.count(1)


class StaleError(ChartgenError):
    """The page asked about a chart version that is not the session's any more."""


class NothingToDoError(ChartgenError):
    """Undo with no step to undo, redo with none to redo, a save with nothing to save, no draft."""


@dataclass
class Step:
    label: str
    before: dict[Key, list[ChartNote]]
    after: dict[Key, list[ChartNote]]
    request: Mapping[str, Any] | None = None
    """What the page asked for, kept for the edit log (``chartgen_edits.json``)."""
    id: int = field(default_factory=lambda: next(_STEP_IDS))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class EditSession:
    """One open song: its chart, its version, its undo and redo steps, its draft. Thread-safe."""

    def __init__(self, name: str, folder: Path, chart: Chart, disk_sha256: str = "", outputs: Path | None = None,
                 draft_delay_s: float = DRAFT_DELAY_S) -> None:
        self.name = name
        self.folder = folder
        self.chart = chart
        self.disk_sha256 = disk_sha256
        """The hash of the ``notes.chart`` on disk that the chart was read from or last saved as."""
        self.outputs = outputs
        """The song library's folder: backups and drafts live there. None: no drafts (tests of the model)."""
        self.draft_delay_s = draft_delay_s
        self.version = next(_VERSIONS)
        self.undo_stack: list[Step] = []
        self.redo_stack: list[Step] = []
        self.saved_id: int | None = None
        """The top undo step when the chart was last saved; None: as it was read."""
        self.dropped = False
        """Undo steps were dropped (MAX_STEPS) since the save point None: that state is out of reach."""
        self.pending_draft: dict[str, Any] | None = None
        """A draft of this chart from an earlier run, offered to the page until restored or discarded."""
        self.set_aside: list[dict[str, str]] = []
        """Drafts moved aside (stale, or not restored before editing): their paths, for the page."""
        self.lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._tracks = {(t.instrument, t.difficulty): t for t in chart.tracks}

    # ---------------------------------------------------------------- state

    @property
    def unsaved(self) -> int:
        """Steps between the chart now and the chart as last saved (or read): the page's count."""
        ids = [s.id for s in self.undo_stack]
        top = ids[-1] if ids else None
        if self.saved_id is None:
            return len(ids) + (1 if self.dropped else 0)
        if top == self.saved_id:
            return 0
        if self.saved_id in ids:
            return len(ids) - 1 - ids.index(self.saved_id)
        redo = [s.id for s in self.redo_stack]
        if self.saved_id in redo:
            return len(redo) - redo.index(self.saved_id)
        return max(1, len(ids))  # undone past the save and edited anew: the saved chart is out of reach

    @property
    def has_history(self) -> bool:
        return bool(self.undo_stack or self.redo_stack or self.unsaved)

    def state(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "unsaved": self.unsaved,
            "undo": self.undo_stack[-1].label if self.undo_stack else None,
            "redo": self.redo_stack[-1].label if self.redo_stack else None,
            "draft": self.pending_draft and {k: self.pending_draft[k] for k in ("saved_at", "unsaved")},
            "set_aside": list(self.set_aside),
        }

    def _check(self, version: Any) -> None:
        if version != self.version:
            raise StaleError("This chart was changed in another tab or window, or the editor was restarted: reload the page.")

    def _put(self, notes: Mapping[Key, list[ChartNote]]) -> None:
        for key, value in notes.items():
            self._tracks[key].notes = list(value)

    def _tracks_json(self, keys: list[Key]) -> list[dict[str, Any]]:
        return [track_json(self._tracks[key]) for key in keys]

    def _push(self, step: Step) -> None:
        self.undo_stack.append(step)
        if len(self.undo_stack) > MAX_STEPS:
            del self.undo_stack[:-MAX_STEPS]
            # Read-and-never-saved: the chart as read is out of reach now. A dropped save point needs no flag:
            # `unsaved` finds it in neither stack.
            if self.saved_id is None:
                self.dropped = True
        self.redo_stack.clear()

    # ---------------------------------------------------------------- edits

    def apply(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """One operation (``ops.apply``) as one undo step; an operation that changes nothing is no step."""
        with self.lock:
            self._check(request.get("version"))
            result = ops.apply(self.chart, request)
            notices = list(result.notices)
            if result.changed:
                if self.pending_draft is not None:
                    notices.append(self._set_draft_aside("not restored before editing again"))
                before = {key: list(self._tracks[key].notes) for key in result.changed}
                self._put(result.changed)
                self._push(Step(result.label, before, result.changed, {k: v for k, v in request.items() if k != "version"}))
                self.version = next(_VERSIONS)
                self._schedule_draft()
            return {
                "edit": self.state(),
                "label": result.label,
                "tracks": self._tracks_json(list(result.changed)),
                "selection": [list(p) for p in result.selection],
                "cascaded": result.cascaded,
                "notices": notices,
            }

    def undo(self, version: Any) -> dict[str, Any]:
        with self.lock:
            self._check(version)
            if not self.undo_stack:
                raise NothingToDoError("There is nothing to undo.")
            step = self.undo_stack.pop()
            self._put(step.before)
            self.redo_stack.append(step)
            self.version = next(_VERSIONS)
            self._schedule_draft()
            return {"edit": self.state(), "label": step.label, "tracks": self._tracks_json(list(step.before))}

    def redo(self, version: Any) -> dict[str, Any]:
        with self.lock:
            self._check(version)
            if not self.redo_stack:
                raise NothingToDoError("There is nothing to redo.")
            step = self.redo_stack.pop()
            self._put(step.after)
            self.undo_stack.append(step)
            self.version = next(_VERSIONS)
            self._schedule_draft()
            return {"edit": self.state(), "label": step.label, "tracks": self._tracks_json(list(step.after))}

    def render(self) -> bytes:
        return DotChartExporter().render(self.chart)

    def chart_text(self) -> tuple[int, str]:
        """The chart as it would be saved, and the version it belongs to."""
        with self.lock:
            return self.version, self.render().decode("utf-8-sig")

    def check_texts(self) -> tuple[int, str, str | None]:
        """What the live check validates: the chart and the ``song.ini`` a save would write."""
        with self.lock:
            return self.version, self.render().decode("utf-8-sig"), saving.prospective_song_ini(self.folder, self.chart)

    # ---------------------------------------------------------------- saving (E.3.1)

    def _steps_since_save(self) -> tuple[list[Step], bool]:
        """The steps the next save adds, and whether they are exactly the way from the last save."""
        ids = [s.id for s in self.undo_stack]
        if self.saved_id is None and not self.dropped:
            return list(self.undo_stack), True
        if self.saved_id in ids:
            return self.undo_stack[ids.index(self.saved_id) + 1:], True
        return list(self.undo_stack), False

    def save(self, version: Any) -> dict[str, Any]:
        """Write the chart and the new ``diff_*`` values after a backup; see ``saving``."""
        with self.lock:
            self._check(version)
            if self.unsaved == 0:
                raise NothingToDoError("There is nothing to save.")
            started = time.perf_counter()
            data = self.render()
            text = data.decode("utf-8-sig")
            ini = saving.prospective_song_ini(self.folder, self.chart)
            report = validate_song_folder(self.folder, text, ini)
            if report.errors:
                count = len(report.errors)
                raise saving.SaveRefusedError(
                    f"The chart has {count} error{'s' if count != 1 else ''}: fix {'them' if count != 1 else 'it'} "
                    f"before saving (see Problems). Nothing was written.",
                    count,
                )
            chart_path = self.folder / CHART_FILE
            on_disk = chart_path.read_bytes() if chart_path.is_file() else b""
            if _sha256(on_disk) != self.disk_sha256:
                self._write_draft()
                where = self._draft_path()
                raise saving.DiskChangedError(
                    f"{CHART_FILE} changed on disk after this song was opened (a rebuild, or another tool), so it was "
                    f"not overwritten. Your edits are kept{f' in the draft {where}' if where else ' in this session'}."
                )
            backups = saving.back_up(self.folder, self.outputs / saving.BACKUP_DIR if self.outputs else self.folder.parent / saving.BACKUP_DIR)
            old_ini = (self.folder / saving.SONG_INI).read_bytes() if (self.folder / saving.SONG_INI).is_file() else None
            saving._write_atomically(chart_path, data)
            if ini is not None and ini.encode("utf-8") != old_ini:
                saving._write_atomically(self.folder / saving.SONG_INI, ini.encode("utf-8"))
            steps, exact = self._steps_since_save()
            new_sha = _sha256(data)
            saving.append_edit_log(self.folder, {
                "saved_at": saving.now_iso(),
                "notes_chart_sha256_before": self.disk_sha256,
                "notes_chart_sha256": new_sha,
                "backups": [p.name for p in backups],
                "edits": [{"label": s.label, "request": s.request} for s in steps],
                "edits_are_the_whole_way": exact,
            })
            self.disk_sha256 = new_sha
            self.saved_id = self.undo_stack[-1].id if self.undo_stack else None
            self.dropped = False
            self._remove_draft()
            took = time.perf_counter() - started
            root = self.outputs or self.folder.parent
            shown = backups[0].parent.relative_to(root.parent) if backups else None
            return {
                "edit": self.state(),
                "saved_ms": round(took * 1000, 1),
                "backups": [str(p) for p in backups],
                "message": f"Saved. The files before this save are in {shown}" if shown else "Saved.",
            }

    # ---------------------------------------------------------------- drafts (E.3.2)

    def _draft_path(self) -> Path | None:
        return self.outputs / DRAFT_DIR / f"{self.name}.json" if self.outputs else None

    def _schedule_draft(self) -> None:
        if self.outputs is None:
            return
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self.draft_delay_s, self._write_draft_later)
        self._timer.daemon = True
        self._timer.start()

    def _write_draft_later(self) -> None:
        with self.lock:
            try:
                self._write_draft()
            except OSError as error:  # a deleted folder, a full disk: the session still holds the edits
                log.warning("The draft of %s could not be written: %s", self.name, error)

    def flush_draft(self) -> None:
        """Write (or remove) the draft now instead of after the delay."""
        if self._timer is not None:
            self._timer.cancel()
        self._write_draft_later()

    def _write_draft(self) -> None:
        """With the lock held: the draft of the chart now, or none when nothing is unsaved."""
        path = self._draft_path()
        if path is None or self.pending_draft is not None:
            return
        if self.unsaved == 0:
            self._remove_draft()
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        steps, _ = self._steps_since_save()
        draft = {
            "song": self.name,
            "base_sha256": self.disk_sha256,
            "saved_at": saving.now_iso(),
            "unsaved": self.unsaved,
            "edits": [s.label for s in steps],
            "chart": self.render().decode("utf-8-sig"),
        }
        saving._write_atomically(path, json.dumps(draft, ensure_ascii=False, indent=1).encode("utf-8"))

    def _remove_draft(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        path = self._draft_path()
        if path is not None and self.pending_draft is None and path.is_file():
            path.unlink()

    def _set_draft_aside(self, reason: str) -> str:
        """Rename the draft ``<song>.<date_time>.stale.json`` and remember it for the page; return the words."""
        path = self._draft_path()
        target = path.with_name(f"{self.name}.{time.strftime('%Y-%m-%d_%H%M%S')}.stale.json")
        number = 1
        while target.exists():
            number += 1
            target = path.with_name(f"{self.name}.{time.strftime('%Y-%m-%d_%H%M%S')}-{number}.stale.json")
        os.replace(path, target)
        saved_at = (self.pending_draft or {}).get("saved_at", "")
        self.pending_draft = None
        words = f"Unsaved edits from an earlier session ({reason}) were kept aside in {target}"
        self.set_aside.append({"path": str(target), "reason": reason, "saved_at": saved_at, "message": words})
        return words

    def check_draft(self) -> None:
        """At opening: offer a draft based on the chart on disk; set aside one based on another chart."""
        path = self._draft_path()
        if path is None or not path.is_file():
            return
        try:
            draft = json.loads(path.read_text(encoding="utf-8"))
            base, saved_at, unsaved = draft["base_sha256"], draft["saved_at"], int(draft["unsaved"])
            read_chart(draft["chart"])
        except (OSError, ValueError, KeyError, TypeError, ChartReadError):
            self.pending_draft = {"saved_at": ""}
            self._set_draft_aside("it could not be read")
            return
        self.pending_draft = {"saved_at": saved_at, "unsaved": unsaved}
        if base != self.disk_sha256:
            self._set_draft_aside(f"made on a {CHART_FILE} that has changed since")

    def restore_draft(self, version: Any) -> dict[str, Any]:
        """Put the draft's chart in place as one undo step."""
        with self.lock:
            self._check(version)
            path = self._draft_path()
            if self.pending_draft is None or path is None or not path.is_file():
                raise NothingToDoError("There is no draft to restore.")
            draft = read_chart(json.loads(path.read_text(encoding="utf-8"))["chart"])
            restored = {(t.instrument, t.difficulty): t.notes for t in draft.tracks}
            after = {key: list(restored.get(key, [])) for key, track in self._tracks.items() if restored.get(key, []) != track.notes}
            before = {key: list(self._tracks[key].notes) for key in after}
            label = f"Restore {self.pending_draft.get('unsaved', '')} unsaved edits".replace("  ", " ")
            self.pending_draft = None
            if after:
                self._put(after)
                self._push(Step(label, before, after, {"restore_draft": True}))
                self.version = next(_VERSIONS)
            self._schedule_draft()
            return {"edit": self.state(), "label": label, "tracks": self._tracks_json(list(after))}

    def discard_draft(self, version: Any) -> dict[str, Any]:
        with self.lock:
            self._check(version)
            path = self._draft_path()
            if self.pending_draft is None:
                raise NothingToDoError("There is no draft to discard.")
            self.pending_draft = None
            if path is not None and path.is_file():
                path.unlink()
            return {"edit": self.state()}


class Sessions:
    """The open songs of one server, by folder name.

    With ``freeze_gc`` (the ``chartgen edit`` server), every song read is followed by one garbage collection
    and ``gc.freeze()``: the chart's tens of thousands of notes are then left out of later full collections,
    which otherwise stalled an edit now and then by 40-100 ms (measured on LastResort, 2026-11-25). Notes
    dropped later are still freed by reference counting; only garbage in reference cycles would stay. Tests
    leave it off, as a frozen test process would keep such garbage for the rest of the run.
    """

    def __init__(self, library: SongLibrary, freeze_gc: bool = False, draft_delay_s: float = DRAFT_DELAY_S) -> None:
        self.library = library
        self.freeze_gc = freeze_gc
        self.draft_delay_s = draft_delay_s
        self._open: dict[str, EditSession] = {}
        self._lock = threading.Lock()

    def open(self, name: str) -> EditSession:
        """The song's session. One with edits or undo history is kept as it is; one without is read again
        when its ``notes.chart`` changed on disk (another tool edited it), and kept, version and all, when
        it did not, so that opening the song in a second tab does not refuse the first."""
        folder = self.library.folder(name)
        path = folder / CHART_FILE
        try:
            data = path.read_bytes()
        except OSError as error:
            raise ChartReadError(f"cannot read {path}: {error}") from error
        digest = _sha256(data)
        with self._lock:
            session = self._open.get(name)
            if session is None or (not session.has_history and session.disk_sha256 != digest):
                try:
                    text = data.decode("utf-8-sig")
                except UnicodeDecodeError as error:
                    raise ChartReadError(f"cannot read {path}: {error}") from error
                session = EditSession(name, folder, read_chart(text), digest, self.library.root, self.draft_delay_s)
                with session.lock:
                    session.check_draft()
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
