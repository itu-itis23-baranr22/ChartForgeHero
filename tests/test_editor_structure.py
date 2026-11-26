"""Editing sections, star power and the preview (E.4.1 d): each change on a bar line, one undo step, refused when
the model cannot hold it, shown by the live check when it only breaks a validator rule; a save writes
``preview_start_time`` only when the preview moved."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402
from test_editor_save import SONG, make_song  # noqa: E402

from chartgen.editor.server import WRITE_HEADER, create_app  # noqa: E402
from chartgen.editor.session import DRAFT_DIR  # noqa: E402
from chartgen.editor.songs import SongLibrary  # noqa: E402

WRITE = {WRITE_HEADER: "1"}
BAR = 768  # the levelled chart: 4/4 at 192 ticks a beat


@pytest.fixture
def outputs(tmp_path: Path) -> Path:
    root = tmp_path / "outputs"
    make_song(root)
    return root


@pytest.fixture
def client(outputs: Path) -> TestClient:
    return TestClient(create_app(SongLibrary(outputs), draft_delay_s=60), base_url="http://127.0.0.1:8765")


def url(rest: str) -> str:
    return f"/api/songs/{quote(SONG, safe='')}/{rest}"


def chart(client: TestClient) -> dict:
    return client.get(url("chart")).json()


def op(client: TestClient, operation: dict, instrument: str = "guitar", difficulty: str = "expert"):
    body = {"version": chart(client)["edit"]["version"], "instrument": instrument, "difficulty": difficulty, "op": operation}
    return client.post(url("ops"), json=body, headers=WRITE)


def ok(client: TestClient, operation: dict, **kwargs) -> dict:
    response = op(client, operation, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()


def star_power(data: dict, level: str) -> list:
    return next(t for t in data["tracks"] if t["instrument"] == "guitar" and t["difficulty"] == level)["star_power"]


def render(client: TestClient) -> tuple[bytes, int | None]:
    chart(client)  # opens the song if it is not open yet
    session = client.app.state.sessions.current(SONG)
    return session.render(), session.preview_ms


# ---------------------------------------------------------------- sections


def test_sections_are_added_renamed_moved_and_deleted_on_bar_lines(client):
    out = ok(client, {"kind": "section_add", "tick": 8 * BAR, "name": "  Verse   one "})
    assert out["sections"] == [[8 * BAR, "Verse one"]] and out["structure"] == {"kind": "section", "tick": 8 * BAR}
    assert out["label"] == "Add section Verse one"
    out = ok(client, {"kind": "section_rename", "tick": 8 * BAR, "name": "V1"})
    assert out["sections"] == [[8 * BAR, "V1"]]
    out = ok(client, {"kind": "section_move", "tick": 8 * BAR, "bars": -2})
    assert out["sections"] == [[6 * BAR, "V1"]] and out["structure"]["tick"] == 6 * BAR
    out = ok(client, {"kind": "section_delete", "tick": 6 * BAR})
    assert out["sections"] == [] and out["structure"] is None


@pytest.mark.parametrize(
    ("operation", "message"),
    [
        ({"kind": "section_add", "tick": 100, "name": "A"}, "not on a bar line"),
        ({"kind": "section_add", "tick": BAR, "name": "  "}, "needs a name"),
        ({"kind": "section_add", "tick": BAR, "name": 'say "hi"'}, "double quote"),
        ({"kind": "section_rename", "tick": BAR, "name": "B"}, "no section at tick"),
        ({"kind": "preview_set", "tick": 50}, "not on a bar line"),
        ({"kind": "sp_add", "tick": BAR, "bars": 0}, "at least one bar"),
        ({"kind": "sp_delete", "tick": 0}, "no star power phrase"),
        ({"kind": "sp_resize", "tick": 4 * BAR, "bars": -1}, "at least one bar"),
    ],
)
def test_what_the_model_cannot_hold_is_refused(client, operation, message):
    before = render(client)
    response = op(client, operation)
    assert response.status_code == 422 and message in response.json()["error"], response.text
    assert render(client) == before


def test_a_second_section_on_a_bar_is_refused(client):
    ok(client, {"kind": "section_add", "tick": BAR, "name": "A"})
    assert "already has a section (A)" in op(client, {"kind": "section_add", "tick": BAR, "name": "B"}).json()["error"]
    ok(client, {"kind": "section_add", "tick": 5 * BAR, "name": "B"})
    assert "already has a section" in op(client, {"kind": "section_move", "tick": 5 * BAR, "bars": -4}).json()["error"]


def test_a_section_shorter_than_four_bars_is_allowed_and_shown(client):
    ok(client, {"kind": "section_add", "tick": BAR, "name": "A1"})
    ok(client, {"kind": "section_add", "tick": 3 * BAR, "name": "B1"})
    errors = client.post(url("validate"), json={}, headers=WRITE).json()["errors"]
    short = next(e for e in errors if "lasts less than" in e["raw"])
    assert short["message"] == "The section A1 lasts less than 4 bars: a section is at least 4 bars long."
    assert short["where"] == {"instrument": None, "difficulty": None, "tick": 3 * BAR}


# ---------------------------------------------------------------- star power


def test_star_power_changes_every_level_by_default(client):
    # The levelled chart has one phrase at bar 5 on Expert and Hard; Medium and Easy have none.
    out = ok(client, {"kind": "sp_add", "tick": 10 * BAR, "bars": 2})
    for level in ("expert", "hard", "medium", "easy"):
        assert [10 * BAR, 2 * BAR] in star_power(out, level), level
    out = ok(client, {"kind": "sp_move", "tick": 4 * BAR, "bars": 1})
    assert star_power(out, "expert")[0] == [5 * BAR, BAR] and star_power(out, "hard")[0] == [5 * BAR, BAR]
    out = ok(client, {"kind": "sp_resize", "tick": 5 * BAR, "bars": 2})
    assert star_power(out, "expert")[0] == [5 * BAR, 3 * BAR] and star_power(out, "hard")[0] == [5 * BAR, 3 * BAR]
    out = ok(client, {"kind": "sp_delete", "tick": 10 * BAR})
    assert all([10 * BAR, 2 * BAR] not in star_power(out, level) for level in ("expert", "hard"))


def test_star_power_on_one_level_only(client):
    out = ok(client, {"kind": "sp_add", "tick": 12 * BAR, "bars": 1, "all_levels": False}, difficulty="hard")
    tracks = {t["difficulty"]: t["star_power"] for t in out["tracks"]}
    assert list(tracks) == ["hard"] and [12 * BAR, BAR] in tracks["hard"]
    assert [12 * BAR, BAR] not in star_power(chart(client), "expert")


# ---------------------------------------------------------------- the preview and saving


def test_the_preview_moves_to_a_bar_and_a_save_writes_it(client, outputs):
    folder = outputs / SONG
    old = (folder / "song.ini").read_text(encoding="utf-8").splitlines()
    out = ok(client, {"kind": "preview_set", "tick": 8 * BAR})
    assert out["preview_s"] == 16.0 and out["structure"] == {"kind": "preview", "tick": 8 * BAR}
    assert client.get(url("info")).json()["preview_s"] == 16.0
    assert client.post(url("save"), json={"version": chart(client)["edit"]["version"]}, headers=WRITE).status_code == 200
    new = (folder / "song.ini").read_text(encoding="utf-8").splitlines()
    assert [(a, b) for a, b in zip(old, new) if a != b] == [("preview_start_time = 0", "preview_start_time = 16000")]


def test_a_save_leaves_an_unmoved_preview_line_as_it_was(client, outputs):
    # written its own way ("00000"): a save that did not move the preview keeps the line's bytes
    ini = outputs / SONG / "song.ini"
    ini.write_bytes(ini.read_bytes().replace(b"preview_start_time = 0\n", b"preview_start_time=00000\n"))
    ok(client, {"kind": "add", "notes": [[48, 1]]})
    assert client.post(url("save"), json={"version": chart(client)["edit"]["version"]}, headers=WRITE).status_code == 200
    assert b"preview_start_time=00000\n" in ini.read_bytes()


def test_a_song_ini_without_a_preview_line_gets_one(client, outputs):
    ini = outputs / SONG / "song.ini"
    ini.write_bytes(ini.read_bytes().replace(b"preview_start_time = 0\n", b""))
    ok(client, {"kind": "preview_set", "tick": 8 * BAR})
    assert client.post(url("save"), json={"version": chart(client)["edit"]["version"]}, headers=WRITE).status_code == 200
    assert ini.read_bytes().endswith(b"preview_start_time = 16000\n")


def test_structure_edits_undo_and_redo_to_the_byte(client):
    states = [render(client)]
    for operation in (
        {"kind": "section_add", "tick": BAR, "name": "A1"},
        {"kind": "sp_add", "tick": 12 * BAR, "bars": 2},
        {"kind": "preview_set", "tick": 6 * BAR},
        {"kind": "section_move", "tick": BAR, "bars": 3},
        {"kind": "sp_resize", "tick": 12 * BAR, "bars": -1},
    ):
        ok(client, operation)
        states.append(render(client))
    for expected in reversed(states[:-1]):
        version = chart(client)["edit"]["version"]
        assert client.post(url("undo"), json={"version": version}, headers=WRITE).status_code == 200
        assert render(client) == expected
    for expected in states[1:]:
        version = chart(client)["edit"]["version"]
        client.post(url("redo"), json={"version": version}, headers=WRITE)
        assert render(client) == expected


def test_a_draft_keeps_sections_star_power_and_the_preview(client, outputs):
    ok(client, {"kind": "section_add", "tick": BAR, "name": "A1"})
    ok(client, {"kind": "sp_add", "tick": 12 * BAR, "bars": 1})
    ok(client, {"kind": "preview_set", "tick": 6 * BAR})
    session = client.app.state.sessions.current(SONG)
    session.flush_draft()
    assert json.loads((outputs / DRAFT_DIR / f"{SONG}.json").read_text(encoding="utf-8"))["preview_ms"] == 12000
    edited = render(client)
    again = TestClient(create_app(SongLibrary(outputs), draft_delay_s=60), base_url="http://127.0.0.1:8765")
    version = again.get(url("chart")).json()["edit"]["version"]
    restored = again.post(url("draft/restore"), json={"version": version}, headers=WRITE).json()
    assert restored["sections"] == [[BAR, "A1"]] and restored["preview_s"] == 12.0
    assert render(again) == edited
