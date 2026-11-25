"""The editor's editing API (SPEC 49, 50, 54; E.2): operations, undo and redo, the live check, and who may
change anything."""

from __future__ import annotations

import shutil
import statistics
import time
from pathlib import Path
from urllib.parse import quote

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from conftest import skip_missing  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from test_editor_api import SONG, make_song  # noqa: E402

from chartgen.clonehero.validate import validate_song_folder  # noqa: E402
from chartgen.editor.server import WRITE_HEADER, create_app  # noqa: E402
from chartgen.editor.songs import SongLibrary  # noqa: E402

BASE = "http://127.0.0.1:8765"
WRITE = {WRITE_HEADER: "1"}
OUTPUTS = Path(__file__).resolve().parents[1] / "outputs"


@pytest.fixture
def outputs(tmp_path: Path) -> Path:
    root = tmp_path / "outputs"
    make_song(root, SONG)
    return root


@pytest.fixture
def client(outputs: Path) -> TestClient:
    return TestClient(create_app(SongLibrary(outputs)), base_url=BASE)


def url(rest: str, name: str = SONG) -> str:
    return f"/api/songs/{quote(name, safe='')}/{rest}"


def op(client: TestClient, version: int, instrument: str, difficulty: str, operation: dict, linked: bool = True):
    body = {"version": version, "instrument": instrument, "difficulty": difficulty, "linked": linked, "op": operation}
    return client.post(url("ops"), json=body, headers=WRITE)


def track(data: dict, instrument: str, difficulty: str) -> dict:
    return next(t for t in data["tracks"] if t["instrument"] == instrument and t["difficulty"] == difficulty)


def test_the_chart_comes_with_its_edit_state(client):
    data = client.get(url("chart")).json()
    assert set(data["edit"]) == {"version", "unsaved", "undo", "redo", "draft", "set_aside"}
    assert data["edit"]["unsaved"] == 0 and data["edit"]["undo"] is None
    assert data["edit"]["draft"] is None and data["edit"]["set_aside"] == []


def test_an_operation_returns_the_tracks_it_changed(client):
    version = client.get(url("chart")).json()["edit"]["version"]
    response = op(client, version, "guitar", "hard", {"kind": "add", "notes": [[1344, 1]]})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["label"] == "Add a note"
    assert data["edit"]["unsaved"] == 1 and data["edit"]["undo"] == "Add a note" and data["edit"]["version"] > version
    assert {(t["instrument"], t["difficulty"]) for t in data["tracks"]} == {("guitar", "hard"), ("guitar", "expert")}
    assert data["cascaded"] == [{"difficulty": "expert", "tick": 1344, "lane": 1, "change": "added"}]
    assert data["selection"] == [[1344, 1]]
    assert [1344, 1, 0, 0] in track(data, "guitar", "expert")["notes"]


def test_undo_and_redo_go_through_the_api(client):
    version = client.get(url("chart")).json()["edit"]["version"]
    version = op(client, version, "guitar", "expert", {"kind": "delete", "notes": [[768, 0]]}).json()["edit"]["version"]
    undone = client.post(url("undo"), json={"version": version}, headers=WRITE).json()
    assert undone["label"] == "Delete a note" and undone["edit"]["unsaved"] == 0 and undone["edit"]["redo"] == "Delete a note"
    assert [768, 0, 0, 0] in track(undone, "guitar", "expert")["notes"]
    redone = client.post(url("redo"), json={"version": undone["edit"]["version"]}, headers=WRITE).json()
    assert [768, 0, 0, 0] not in track(redone, "guitar", "expert")["notes"]
    response = client.post(url("redo"), json={"version": redone["edit"]["version"]}, headers=WRITE)
    assert response.status_code == 409 and response.json()["error"] == "There is nothing to redo."


def test_an_old_version_is_refused(client):
    version = client.get(url("chart")).json()["edit"]["version"]
    assert op(client, version, "guitar", "expert", {"kind": "add", "notes": [[96, 0]]}).status_code == 200
    response = op(client, version, "guitar", "expert", {"kind": "add", "notes": [[192, 0]]})
    assert response.status_code == 409 and response.json()["stale"] is True
    assert "another tab" in response.json()["error"]


def test_a_refused_operation_says_why_and_changes_nothing(client):
    before = client.get(url("chart")).json()
    response = op(client, before["edit"]["version"], "drums", "expert", {"kind": "sustain", "notes": [[768, 0]], "length": 96})
    assert response.status_code == 422 and response.json()["error"] == "A drum note has no sustain."
    assert client.get(url("chart")).json() == before


def test_reloading_the_page_keeps_the_edits(client):
    version = client.get(url("chart")).json()["edit"]["version"]
    op(client, version, "guitar", "expert", {"kind": "add", "notes": [[96, 0]]})
    again = client.get(url("chart")).json()
    assert [96, 0, 0, 0] in track(again, "guitar", "expert")["notes"] and again["edit"]["unsaved"] == 1


def test_opening_the_song_in_a_second_tab_does_not_refuse_the_first(client):
    first = client.get(url("chart")).json()["edit"]["version"]
    assert client.get(url("chart")).json()["edit"]["version"] == first
    assert op(client, first, "guitar", "expert", {"kind": "add", "notes": [[96, 0]]}).status_code == 200


def test_a_song_without_edits_is_read_from_disk_again(client, outputs):
    client.get(url("chart"))
    path = outputs / SONG / "notes.chart"
    path.write_bytes(path.read_bytes().replace(b"  1536 = N 2 0", b"  1536 = N 3 0"))
    assert [1536, 3, 0, 0] in track(client.get(url("chart")).json(), "keys", "easy")["notes"]


def test_the_edit_server_keeps_a_read_chart_out_of_full_collections(outputs, monkeypatch):
    """``chartgen edit`` freezes after reading a song (full collections stalled edits by 40-100 ms); tests do not."""
    import chartgen.editor.session as session_module

    calls = []
    monkeypatch.setattr(session_module.gc, "collect", lambda: calls.append("collect"))
    monkeypatch.setattr(session_module.gc, "freeze", lambda: calls.append("freeze"))
    session_module.Sessions(SongLibrary(outputs)).open(SONG)
    assert calls == []
    sessions = session_module.Sessions(SongLibrary(outputs), freeze_gc=True)
    sessions.open(SONG)
    sessions.open(SONG)  # the same chart on disk: kept, no second freeze
    assert calls == ["collect", "freeze"]


def test_a_restarted_editor_refuses_the_old_page(outputs):
    first = TestClient(create_app(SongLibrary(outputs)), base_url=BASE)
    version = first.get(url("chart")).json()["edit"]["version"]
    second = TestClient(create_app(SongLibrary(outputs)), base_url=BASE)
    response = op(second, version, "guitar", "expert", {"kind": "add", "notes": [[96, 0]]})
    assert response.status_code == 409 and response.json()["stale"] is True


@pytest.mark.parametrize(
    ("headers", "body"),
    [
        ({}, None),  # no editor header
        ({WRITE_HEADER: "0"}, None),
        ({**WRITE, "Origin": "http://evil.example"}, None),
        ({**WRITE, "Content-Type": "text/plain"}, '{"version": 1}'),
    ],
)
def test_changes_come_from_the_editors_own_page_only(client, headers, body):
    version = client.get(url("chart")).json()["edit"]["version"]
    payload = {"version": version, "instrument": "guitar", "difficulty": "expert", "op": {"kind": "add", "notes": [[96, 0]]}}

    def send(path: str):
        if body is None:
            return client.post(url(path), json=payload, headers=headers)
        return client.post(url(path), content=body, headers=headers)

    for path in ("ops", "undo", "redo", "validate"):
        response = send(path)
        assert response.status_code == 403, (path, response.text)
        assert response.json()["error"].startswith("Refused:")
    assert client.get(url("chart")).json()["edit"]["unsaved"] == 0


def test_the_editors_own_origin_is_accepted(client):
    version = client.get(url("chart")).json()["edit"]["version"]
    response = client.post(
        url("ops"),
        json={"version": version, "instrument": "guitar", "difficulty": "expert", "op": {"kind": "add", "notes": [[96, 0]]}},
        headers={**WRITE, "Origin": BASE},
    )
    assert response.status_code == 200


def test_the_live_check_sees_the_edits_in_plain_words(client):
    version = client.get(url("chart")).json()["edit"]["version"]
    before = client.post(url("validate"), json={}, headers=WRITE).json()
    assert before["version"] == version
    assert not any("bass has single notes only" in e["message"] for e in before["errors"])
    data = op(client, version, "bass", "expert", {"kind": "add", "notes": [[768, 2]]}).json()
    after = client.post(url("validate"), json={}, headers=WRITE).json()
    assert after["version"] == data["edit"]["version"]
    chord = next(e for e in after["errors"] if e["raw"] == "[ExpertDoubleBass] tick 768: a chord of 2 notes")
    assert chord["message"] == "A chord of 2 notes: bass has single notes only."
    assert chord["where"] == {"instrument": "bass", "difficulty": "expert", "tick": 768}
    info = client.get(url("info")).json()
    assert any(e["raw"] == chord["raw"] for e in info["validation"]["errors"])


def test_the_folder_check_can_take_the_chart_as_text(outputs):
    folder = outputs / SONG
    text = (folder / "notes.chart").read_text(encoding="utf-8-sig")
    edited = text.replace("  768 = N 0 96", "  768 = N 0 96\n  768 = N 2 0")
    assert not any("a chord of 2" in e for e in validate_song_folder(folder).errors)
    assert any("[ExpertDoubleBass] tick 768: a chord of 2 notes" in e for e in validate_song_folder(folder, edited).errors)


def test_operations_on_an_unknown_song_are_not_found(client):
    response = client.post(url("ops", "Nobody - Nothing"), json={"version": 1}, headers=WRITE)
    assert response.status_code == 404


# ---------------------------------------------------------------- how fast (E.2: < 30 ms a round trip)


@pytest.mark.real
def test_an_operation_on_a_real_song_takes_less_than_30_ms(tmp_path):
    source = OUTPUTS / "Davul Testi - LastResort"
    if not (source / "notes.chart").is_file():
        skip_missing(source / "notes.chart")
    folder = tmp_path / "outputs" / source.name
    folder.mkdir(parents=True)
    for name in ("notes.chart", "song.ini", "analysis.json"):
        shutil.copy2(source / name, folder / name)
    client = TestClient(create_app(SongLibrary(folder.parent)), base_url=BASE)
    data = client.get(url("chart", source.name)).json()
    version = data["edit"]["version"]
    expert = track(data, "guitar", "expert")["notes"]
    times = []
    for k in range(30):
        note = expert[100 + 7 * k]
        kinds = [
            {"kind": "move", "notes": [[note[0], note[1]]], "ticks": 0, "rows": 1 if note[1] < 4 else -1},
            {"kind": "add", "notes": [[note[0] + 24, (note[1] + 2) % 5]]},
            {"kind": "delete", "notes": [[note[0], note[1]]]},
        ]
        start = time.perf_counter()
        response = client.post(
            url("ops", source.name),
            json={"version": version, "instrument": "guitar", "difficulty": "expert", "linked": True, "op": kinds[k % 3]},
            headers=WRITE,
        )
        times.append(time.perf_counter() - start)
        assert response.status_code in (200, 422), response.text
        if response.status_code == 200:
            version = response.json()["edit"]["version"]
    median = statistics.median(times) * 1000
    slowest = max(times) * 1000
    print(f"\nround trip on LastResort: median {median:.1f} ms, slowest {slowest:.1f} ms over {len(times)} operations")
    assert median < 30 and sorted(times)[int(0.9 * len(times))] * 1000 < 30, (median, slowest)
