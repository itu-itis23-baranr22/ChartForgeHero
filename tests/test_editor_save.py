"""Saving (SPEC 54, E.3.1) and drafts (E.3.2): what a save writes, backs up and refuses, and how unsaved edits
survive a stopped editor."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from conftest import skip_missing  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from test_editor_ops import levelled  # noqa: E402

from chartgen.clonehero.chart_format import DotChartExporter  # noqa: E402
from chartgen.clonehero.package import encode_ogg  # noqa: E402
from chartgen.clonehero.protection import EDIT_MARK, EDITED, dump_analysis, state  # noqa: E402
from chartgen.clonehero.song_ini import SongIni, render_song_ini  # noqa: E402
from chartgen.clonehero.validate import validate_song_folder  # noqa: E402
from chartgen.editor.saving import BACKUP_DIR, difficulties, song_ini_with  # noqa: E402
from chartgen.editor.server import WRITE_HEADER, create_app  # noqa: E402
from chartgen.editor.session import DRAFT_DIR  # noqa: E402
from chartgen.editor.songs import SongLibrary  # noqa: E402

SONG = "The Test Rig - Level Sheet"
WRITE = {WRITE_HEADER: "1"}
SECONDS = 60.0
OUTPUTS = Path(__file__).resolve().parents[1] / "outputs"


def make_song(outputs: Path) -> Path:
    """A valid folder as a build would write it: the levelled chart, song.ini with the build's diff_* values,
    analysis.json with the input's length, two audio files."""
    chart = levelled()
    folder = outputs / SONG
    folder.mkdir(parents=True)
    DotChartExporter().export(chart, folder)
    ini = SongIni(chart.metadata, int(SECONDS * 1000), 0, 0, difficulties(chart, SECONDS))
    (folder / "song.ini").write_text(render_song_ini(ini), encoding="utf-8", newline="\n")
    (folder / "analysis.json").write_text(dump_analysis({"input": {"file_name": "x.wav", "sha256": "0" * 64, "duration_s": SECONDS}}), encoding="utf-8")
    quiet = np.zeros((4410, 2), dtype=np.float32)
    encode_ogg(quiet, 44100, folder / "song.ogg")
    encode_ogg(quiet, 44100, folder / "guitar.ogg")
    assert validate_song_folder(folder).ok, validate_song_folder(folder).errors
    return folder


def files(folder: Path) -> dict[str, str]:
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob("*")) if p.is_file()}


@pytest.fixture
def outputs(tmp_path: Path) -> Path:
    root = tmp_path / "outputs"
    make_song(root)
    return root


def client_for(outputs: Path, delay: float = 0.05) -> TestClient:
    return TestClient(create_app(SongLibrary(outputs), draft_delay_s=delay), base_url="http://127.0.0.1:8765")


@pytest.fixture
def client(outputs: Path) -> TestClient:
    return client_for(outputs)


def url(rest: str, name: str = SONG) -> str:
    return f"/api/songs/{quote(name, safe='')}/{rest}"


def version(client: TestClient) -> int:
    return client.get(url("chart")).json()["edit"]["version"]


def op(client: TestClient, operation: dict, instrument: str = "guitar", difficulty: str = "expert", linked: bool = True) -> dict:
    body = {"version": version(client), "instrument": instrument, "difficulty": difficulty, "linked": linked, "op": operation}
    response = client.post(url("ops"), json=body, headers=WRITE)
    assert response.status_code == 200, response.text
    return response.json()


def post(client: TestClient, rest: str, body: dict | None = None):
    return client.post(url(rest), json={"version": version(client), **(body or {})}, headers=WRITE)


def session(client: TestClient):
    return client.app.state.sessions.current(SONG)


# ---------------------------------------------------------------- saving


def test_a_save_writes_the_chart_backs_up_the_old_files_and_marks_the_folder(client, outputs):
    folder = outputs / SONG
    old_chart = (folder / "notes.chart").read_bytes()
    old_ini = (folder / "song.ini").read_bytes()
    old_analysis = (folder / "analysis.json").read_bytes()
    op(client, {"kind": "add", "notes": [[48, 1]]})
    response = post(client, "save")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["edit"]["unsaved"] == 0 and data["saved_ms"] < 1000
    assert data["message"].startswith("Saved. The files before this save are in outputs")
    assert (folder / "notes.chart").read_bytes() == session(client).render()
    backups = sorted((outputs / BACKUP_DIR / SONG).iterdir())
    assert [p.name.split("_", 2)[-1] for p in backups] == ["notes.chart", "song.ini"]
    assert backups[0].read_bytes() == old_chart and backups[1].read_bytes() == old_ini
    assert (folder / "analysis.json").read_bytes() == old_analysis
    log = json.loads((folder / EDIT_MARK).read_text(encoding="utf-8"))
    assert len(log) == 1 and [e["label"] for e in log[0]["edits"]] == ["Add a note"]
    assert log[0]["edits"][0]["request"]["op"] == {"kind": "add", "notes": [[48, 1]]}
    assert log[0]["edits_are_the_whole_way"] is True
    assert state(folder)[0] == EDITED
    assert client.get("/api/songs").json()["songs"][0]["edited"] is True
    assert not list(folder.glob(".*.saving"))


def test_song_ini_changes_in_its_diff_lines_only(client, outputs):
    folder = outputs / SONG
    old = (folder / "song.ini").read_text(encoding="utf-8").splitlines()
    for level in ("expert", "hard", "medium", "easy"):
        notes = [t for t in client.get(url("chart")).json()["tracks"] if t["instrument"] == "bass" and t["difficulty"] == level][0]["notes"]
        op(client, {"kind": "delete", "notes": [[n[0], n[1]] for n in notes]}, "bass", level, linked=False)
    # The live check looks at the song.ini a save would write: no "bass has no notes but diff_bass" here.
    checked = post(client, "validate").json()
    assert not any("diff_bass" in e["raw"] for e in checked["errors"]), checked["errors"]
    assert post(client, "save").status_code == 200
    new = (folder / "song.ini").read_text(encoding="utf-8").splitlines()
    changed = [(a, b) for a, b in zip(old, new) if a != b]
    assert len(old) == len(new) and [b for _, b in changed] == ["diff_bass = -1"]


def test_an_invalid_chart_writes_nothing(client, outputs):
    folder = outputs / SONG
    before = files(folder)
    op(client, {"kind": "add", "notes": [[0, 2]]}, "guitar", "easy")  # an Easy chord
    response = post(client, "save")
    assert response.status_code == 422
    assert response.json()["errors"] == 1
    assert response.json()["error"] == "The chart has 1 error: fix it before saving (see Problems). Nothing was written."
    assert files(folder) == before and not (outputs / BACKUP_DIR).exists()


def test_a_chart_changed_on_disk_is_not_overwritten_and_the_edits_stay_in_a_draft(client, outputs):
    folder = outputs / SONG
    op(client, {"kind": "add", "notes": [[48, 1]]})
    chart = folder / "notes.chart"
    chart.write_bytes(chart.read_bytes() + b"\r\n")  # a rebuild or another tool
    other = chart.read_bytes()
    response = post(client, "save")
    assert response.status_code == 409 and response.json()["disk_changed"] is True
    assert "not overwritten" in response.json()["error"] and DRAFT_DIR in response.json()["error"]
    assert chart.read_bytes() == other and not (outputs / BACKUP_DIR).exists()
    draft = json.loads((outputs / DRAFT_DIR / f"{SONG}.json").read_text(encoding="utf-8"))
    assert draft["unsaved"] == 1 and draft["chart"] == session(client).render().decode("utf-8-sig")


def test_unsaved_edits_count_from_the_last_save(client):
    op(client, {"kind": "add", "notes": [[48, 1]]})
    op(client, {"kind": "add", "notes": [[144, 1]]})
    assert post(client, "save").status_code == 200
    assert post(client, "undo").json()["edit"]["unsaved"] == 1
    assert post(client, "undo").json()["edit"]["unsaved"] == 2
    assert post(client, "redo").json()["edit"]["unsaved"] == 1
    assert post(client, "redo").json()["edit"]["unsaved"] == 0
    response = post(client, "save")
    assert response.status_code == 409 and response.json()["error"] == "There is nothing to save."


def test_every_save_keeps_its_own_backup(client, outputs):
    for tick in (48, 144, 240):
        op(client, {"kind": "add", "notes": [[tick, 1]]})
        assert post(client, "save").status_code == 200
    backups = sorted(p.name for p in (outputs / BACKUP_DIR / SONG).iterdir())
    assert len(backups) == 6 and len(set(backups)) == 6
    log = json.loads((outputs / SONG / EDIT_MARK).read_text(encoding="utf-8"))
    assert [len(entry["edits"]) for entry in log] == [1, 1, 1]


def test_the_ini_rewrite_keeps_every_other_byte():
    text = "[song]\r\nname = A\r\ndiff_guitar = 3\r\ndiff_bass=2\r\nicon = x\r\ndiff_drums   =   -1\r\n"
    from chartgen.core.model import Instrument

    assert song_ini_with(text, {Instrument.GUITAR: 5, Instrument.DRUMS: 1}) == (
        "[song]\r\nname = A\r\ndiff_guitar = 5\r\ndiff_bass=-1\r\nicon = x\r\ndiff_drums   =   1\r\n"
    )


@pytest.mark.real
def test_saving_a_real_song_after_an_edit_and_its_undo_gives_the_same_files(tmp_path):
    """Each folder in outputs (copied, with silent stand-ins for its audio): two edits that cancel out, a save;
    the files come back byte for byte, diff_* included, and the folder passes the validator."""
    folders = [p for p in sorted(OUTPUTS.iterdir()) if p.is_dir() and not p.name.startswith(("_", ".")) and (p / "notes.chart").is_file()] if OUTPUTS.is_dir() else []
    if not folders:
        skip_missing(f"song folders in {OUTPUTS}")
    root = tmp_path / "outputs"
    quiet = np.zeros((441, 2), dtype=np.float32)
    timings = {}
    for source in folders:
        folder = root / source.name
        folder.mkdir(parents=True)
        for name in ("notes.chart", "song.ini", "analysis.json"):
            shutil.copy2(source / name, folder / name)
        for ogg in source.glob("*.ogg"):
            encode_ogg(quiet, 44100, folder / ogg.name)
        before = {name: (folder / name).read_bytes() for name in ("notes.chart", "song.ini")}
        client = client_for(root, delay=60)
        tracks = client.get(url("chart", folder.name)).json()["tracks"]
        track = next(t for t in tracks if t["instrument"] in ("guitar", "bass", "keys") and t["notes"])
        first = track["notes"][0]
        for on in (True, False):
            body = {"version": client.get(url("chart", folder.name)).json()["edit"]["version"], "instrument": track["instrument"],
                    "difficulty": track["difficulty"], "op": {"kind": "flag", "notes": [first[:2]], "flag": "forced", "on": on}}
            assert client.post(url("ops", folder.name), json=body, headers=WRITE).status_code == 200
        start = time.perf_counter()
        response = client.post(url("save", folder.name), json={"version": client.get(url("chart", folder.name)).json()["edit"]["version"]}, headers=WRITE)
        timings[folder.name] = (time.perf_counter() - start) * 1000
        assert response.status_code == 200, (folder.name, response.text)
        for name, data in before.items():
            assert (folder / name).read_bytes() == data, (folder.name, name)
        assert validate_song_folder(folder).ok
    print("\nsave (ms): " + ", ".join(f"{name} {ms:.0f}" for name, ms in timings.items()))
    assert timings["Davul Testi - LastResort"] < 300, timings


# ---------------------------------------------------------------- drafts


def draft_path(outputs: Path) -> Path:
    return outputs / DRAFT_DIR / f"{SONG}.json"


def wait_for(predicate, seconds: float = 3.0) -> None:
    deadline = time.monotonic() + seconds
    while not predicate():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.02)


def test_a_draft_follows_the_edits_and_goes_with_a_save_or_a_full_undo(client, outputs):
    op(client, {"kind": "add", "notes": [[48, 1]]})
    wait_for(draft_path(outputs).is_file)
    draft = json.loads(draft_path(outputs).read_text(encoding="utf-8"))
    assert draft["unsaved"] == 1 and draft["edits"] == ["Add a note"]
    assert draft["base_sha256"] == hashlib.sha256((outputs / SONG / "notes.chart").read_bytes()).hexdigest()
    post(client, "undo")
    wait_for(lambda: not draft_path(outputs).exists())
    op(client, {"kind": "add", "notes": [[48, 1]]})
    wait_for(draft_path(outputs).is_file)
    assert post(client, "save").status_code == 200
    assert not draft_path(outputs).exists()


def test_a_draft_is_offered_after_a_restart_and_restored_as_one_step(client, outputs):
    op(client, {"kind": "add", "notes": [[48, 1]]})
    op(client, {"kind": "add", "notes": [[144, 1]]})
    session(client).flush_draft()
    edited = session(client).render()
    again = client_for(outputs)  # the editor started anew
    chart = again.get(url("chart")).json()
    assert chart["edit"]["draft"]["unsaved"] == 2 and chart["edit"]["draft"]["saved_at"]
    assert chart["edit"]["unsaved"] == 0
    restored = post(again, "draft/restore").json()
    assert restored["label"] == "Restore 2 unsaved edits" and restored["edit"]["unsaved"] == 1
    assert restored["edit"]["draft"] is None
    assert session(again).render() == edited
    assert post(again, "undo").status_code == 200 and session(again).render() == (outputs / SONG / "notes.chart").read_bytes()


def test_a_discarded_draft_is_deleted(client, outputs):
    op(client, {"kind": "add", "notes": [[48, 1]]})
    session(client).flush_draft()
    again = client_for(outputs)
    assert again.get(url("chart")).json()["edit"]["draft"] is not None
    assert post(again, "draft/discard").status_code == 200
    assert not draft_path(outputs).exists()
    assert post(again, "draft/discard").status_code == 409


def test_a_draft_made_on_another_chart_is_set_aside_with_its_path(client, outputs):
    op(client, {"kind": "add", "notes": [[48, 1]]})
    session(client).flush_draft()
    chart = outputs / SONG / "notes.chart"
    chart.write_bytes(chart.read_bytes() + b"\r\n")  # rebuilt meanwhile
    again = client_for(outputs)
    edit = again.get(url("chart")).json()["edit"]
    assert edit["draft"] is None
    aside = edit["set_aside"][0]
    assert aside["path"].endswith(".stale.json") and Path(aside["path"]).is_file()
    assert "has changed since" in aside["message"] and aside["path"] in aside["message"]
    assert not draft_path(outputs).exists()


def test_editing_without_restoring_sets_the_draft_aside_and_says_where(client, outputs):
    op(client, {"kind": "add", "notes": [[48, 1]]})
    session(client).flush_draft()
    again = client_for(outputs)
    answer = op(again, {"kind": "add", "notes": [[240, 1]]})
    assert any("not restored before editing again" in n and ".stale.json" in n for n in answer["notices"])
    assert answer["edit"]["draft"] is None and answer["edit"]["set_aside"]


def test_an_unreadable_draft_is_set_aside(outputs):
    draft_path(outputs).parent.mkdir(parents=True)
    draft_path(outputs).write_text("{not json", encoding="utf-8")
    edit = client_for(outputs).get(url("chart")).json()["edit"]
    assert edit["draft"] is None and "could not be read" in edit["set_aside"][0]["message"]


def test_save_and_drafts_need_the_editors_header(client):
    for path in ("save", "draft/restore", "draft/discard"):
        assert client.post(url(path), json={"version": version(client)}).status_code == 403, path
