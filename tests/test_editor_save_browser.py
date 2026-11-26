"""Saving and drafts in a real browser (E.3), with Playwright 1.65.1: Ctrl+S writes the chart and backs up the old
files; Save with an error says so and sends you to Problems; an unsaved edit survives a restarted editor as a
draft that the page offers to restore."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

from test_editor_edit_browser import BAR, BEAT, FOLDER, make_edit_song  # noqa: E402
from test_editor_sync import free_port, node, run_browser, serve  # noqa: E402, F401  (node is a fixture)

from chartgen.clonehero.protection import EDIT_MARK  # noqa: E402
from chartgen.editor.saving import BACKUP_DIR  # noqa: E402
from chartgen.editor.server import create_app  # noqa: E402
from chartgen.editor.session import DRAFT_DIR  # noqa: E402
from chartgen.editor.songs import SongLibrary  # noqa: E402

pytestmark = pytest.mark.heavy

SHOTS = Path(__file__).resolve().parents[1] / ".impeccable" / "review" / "e3"


def test_save_and_restore_a_draft_in_the_browser(node, tmp_path):  # noqa: F811
    outputs = tmp_path / "outputs"
    folder = make_edit_song(outputs)
    SHOTS.mkdir(parents=True, exist_ok=True)
    port = free_port()
    ticks = [2 * BAR + BEAT, 8 * BAR + BEAT, 3 * BAR + BEAT]
    plan = {"song": FOLDER, "ticks": ticks, "shots": str(SHOTS)}

    with serve(None, port, create_app(SongLibrary(outputs), draft_delay_s=0.2)) as url:
        saved = run_browser(node, {"mode": "save", "step": "save", "url": url, **plan}, tmp_path, "save.mjs")
    assert not saved["problems"], saved["problems"]
    assert saved["saveDisabledAtFirst"] is True and saved["saveDisabledAfter"] is True
    assert saved["beforeSave"] == "1 unsaved edit" and saved["afterSave"] == "No unsaved edits"
    # Notifications (toast.js): a success that goes by itself, an error that stays and offers Problems.
    done = saved["saved"]
    assert done["tone"] == "success" and done["role"] == "status" and done["icon"] == "Done" and done["title"] == "Saved"
    assert done["pathLabel"] == "The files before this save are backed up in"
    assert done["path"] == str(outputs / BACKUP_DIR / FOLDER) and done["pathShown"] == str(Path("outputs") / BACKUP_DIR / FOLDER)
    assert done["actions"] == [] and done["closable"] is True
    assert 1300 <= saved["savedGoneAfterMs"] < 4000  # shortened to 1.5 s by the test (+ 150 ms fade)
    refused = saved["refused"]
    assert refused["tone"] == "error" and refused["role"] == "alert" and refused["icon"] == "Error"
    assert refused["title"] == "Not saved: 1 error"
    assert refused["text"] == "Fix it first (see Problems). Nothing was written."
    assert refused["actions"] == ["Go to Problems"]
    for toast in (done, refused):  # readable, and over the timeline only
        assert toast["titlePx"] >= 16 and (toast["textPx"] or 15) >= 15 and toast["width"] >= 400
        assert toast["inView"] and not toast["overProblems"] and not toast["overTransport"] and not toast["overHeader"]
    assert saved["focused"] and saved["focused"].startswith("Problems")
    assert saved["refusedStays"] is True
    assert saved["afterGoTo"]["focused"].startswith("Problems") and saved["afterGoTo"]["toast"] is None
    assert saved["again"] is True and saved["closed"] is True
    assert saved["leftUnsaved"] == "1 unsaved edit"
    # On disk: the first note saved, two backups, the edit mark; the last note only in the draft.
    assert f"  {ticks[0]} = N 2 0" in (folder / "notes.chart").read_text(encoding="utf-8-sig")
    assert f"  {ticks[2]} = N 2 0" not in (folder / "notes.chart").read_text(encoding="utf-8-sig")
    assert len(list((outputs / BACKUP_DIR / FOLDER).iterdir())) == 2
    assert len(json.loads((folder / EDIT_MARK).read_text(encoding="utf-8"))) == 1
    draft = json.loads((outputs / DRAFT_DIR / f"{FOLDER}.json").read_text(encoding="utf-8"))
    assert draft["unsaved"] == 1 and f"  {ticks[2]} = N 2 0" in draft["chart"]

    # The editor started anew: the page offers the draft and restores it.
    with serve(None, port, create_app(SongLibrary(outputs), draft_delay_s=0.2)) as url:
        restored = run_browser(node, {"mode": "restore", "step": "restore", "url": url, **plan}, tmp_path, "save.mjs")
    assert not restored["problems"], restored["problems"]
    assert "1 unsaved edit of this song from" in restored["offer"] and "was kept in a draft" in restored["offer"]
    assert restored["afterRestore"] == "1 unsaved edit" and restored["restoredNotice"].startswith("Restored")
    assert restored["boxGone"] is True
    assert [ticks[2], 2, 0, 0] in restored["notes"]
