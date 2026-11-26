"""Copy to game (SPEC 56, E.4.0): what goes into Clone Hero's Songs folder, what is backed up, and when nothing is
copied. A temporary folder stands in for Songs; the real one is never touched by a test."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402
from test_editor_save import SONG, make_song  # noqa: E402

from chartgen.clonehero.package import encode_ogg  # noqa: E402
from chartgen.clonehero.validate import validate_song_folder  # noqa: E402
from chartgen.editor.export import SONGS_BACKUP_DIR, default_songs_dir, same_audio  # noqa: E402
from chartgen.editor.server import WRITE_HEADER, create_app  # noqa: E402
from chartgen.editor.songs import SongLibrary  # noqa: E402

WRITE = {WRITE_HEADER: "1"}


def files(folder: Path) -> dict[str, str]:
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob("*")) if p.is_file()}


@pytest.fixture
def world(tmp_path: Path):
    outputs = tmp_path / "outputs"
    make_song(outputs)
    songs = tmp_path / "Clone Hero" / "Songs"
    songs.mkdir(parents=True)
    state = {"running": False}
    app = create_app(SongLibrary(outputs), draft_delay_s=60, songs=songs, running=lambda: state["running"])
    return {"outputs": outputs, "songs": songs, "client": TestClient(app, base_url="http://127.0.0.1:8765"), "game": state}


def url(rest: str) -> str:
    return f"/api/songs/{quote(SONG, safe='')}/{rest}"


def version(client: TestClient) -> int:
    return client.get(url("chart")).json()["edit"]["version"]


def copy(client: TestClient):
    return client.post(url("export"), json={"version": version(client)}, headers=WRITE)


def edit_and_save(client: TestClient, tick: int = 48) -> None:
    body = {"version": version(client), "instrument": "guitar", "difficulty": "expert", "op": {"kind": "add", "notes": [[tick, 1]]}}
    assert client.post(url("ops"), json=body, headers=WRITE).status_code == 200
    assert client.post(url("save"), json={"version": version(client)}, headers=WRITE).status_code == 200


def test_a_new_song_is_copied_whole(world):
    response = copy(world["client"])
    assert response.status_code == 200, response.text
    data = response.json()
    target = world["songs"] / SONG
    assert data["mode"] == "folder" and data["new"] is True and data["backup"] is None and data["errors"] == []
    assert data["backup_shown"] is None and data["target"] == str(world["songs"] / SONG)
    assert "Rescan the songs" in data["message"]
    assert files(target) == files(world["outputs"] / SONG)
    assert validate_song_folder(target).ok
    assert not list(world["songs"].glob(".*"))  # no staging folder left


def test_the_same_audio_takes_only_the_chart_and_song_ini_and_keeps_the_rest(world):
    client, songs = world["client"], world["songs"]
    assert copy(client).status_code == 200
    target = songs / SONG
    (target / "debug_click.wav").write_bytes(b"the owner's click track")  # the layout in Songs stays
    before = files(target)
    old_chart, old_ini = (target / "notes.chart").read_bytes(), (target / "song.ini").read_bytes()
    edit_and_save(client)
    data = copy(client).json()
    assert data["mode"] == "chart" and data["new"] is False
    after = files(target)
    changed = {name for name in after if after[name] != before.get(name)}
    assert changed == {"notes.chart", "song.ini"} or changed == {"notes.chart"}
    assert (target / "notes.chart").read_bytes() == (world["outputs"] / SONG / "notes.chart").read_bytes()
    backup = Path(data["backup"])
    assert backup.parent.parent == world["outputs"] / SONGS_BACKUP_DIR and backup.parent.name.endswith("_editor")
    # the page's notification writes it from the outputs folder and copies it whole
    assert data["backup_shown"] == str(backup.relative_to(world["outputs"].parent))
    assert data["backup_shown"].startswith("outputs")
    assert sorted(p.name for p in backup.iterdir()) == ["notes.chart", "song.ini"]
    assert (backup / "notes.chart").read_bytes() == old_chart and (backup / "song.ini").read_bytes() == old_ini
    assert (target / "debug_click.wav").read_bytes() == b"the owner's click track"


def test_different_audio_replaces_the_whole_folder_after_backing_it_up(world):
    client, songs = world["client"], world["songs"]
    assert copy(client).status_code == 200
    target = songs / SONG
    encode_ogg(np.full((4410, 2), 0.1, dtype=np.float32), 44100, target / "guitar.ogg")  # another build's sound
    encode_ogg(np.zeros((4410, 2), dtype=np.float32), 44100, target / "keys.ogg")  # a stem this build has not
    before = files(target)
    data = copy(client).json()
    assert data["mode"] == "folder" and data["new"] is False
    assert files(target) == files(world["outputs"] / SONG)
    assert not (target / "keys.ogg").exists()  # no stale stem left to play along
    assert files(Path(data["backup"])) == before
    assert "audio differs" in data["message"]


def test_equal_sound_in_different_bytes_counts_as_the_same_audio(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    samples = np.sin(np.linspace(0, 200, 4410, dtype=np.float32))[:, None].repeat(2, axis=1) * 0.3
    encode_ogg(samples, 44100, a / "song.ogg")
    encode_ogg(samples, 44100, b / "song.ogg")  # a new Ogg stream number, the same samples
    assert (a / "song.ogg").read_bytes() != (b / "song.ogg").read_bytes()
    assert same_audio(a, b)
    encode_ogg(samples * 0.5, 44100, b / "song.ogg")
    assert not same_audio(a, b)
    shutil.copyfile(a / "song.ogg", b / "song.ogg")
    encode_ogg(samples, 44100, b / "drums.ogg")
    assert not same_audio(a, b)  # another set of files


def test_nothing_is_copied_while_the_game_runs(world):
    world["game"]["running"] = True
    response = copy(world["client"])
    assert response.status_code == 409 and response.json()["export_refused"] is True
    assert response.json()["error"].startswith("Clone Hero is running")
    assert response.json()["reason"] == "running" and "errors" not in response.json()
    assert list(world["songs"].iterdir()) == []


def test_unsaved_edits_are_saved_first(world):
    client = world["client"]
    body = {"version": version(client), "instrument": "guitar", "difficulty": "expert", "op": {"kind": "add", "notes": [[48, 1]]}}
    client.post(url("ops"), json=body, headers=WRITE)
    response = copy(client)
    assert response.status_code == 409
    assert response.json()["error"] == "Save first: the game gets the song as it is saved, and 1 edit is not saved yet."
    assert response.json()["reason"] == "unsaved"
    assert list(world["songs"].iterdir()) == []


def test_a_chart_changed_on_disk_after_saving_is_not_copied(world):
    # saved in the editor, then rewritten by another tool: the page no longer shows what would be copied
    edit_and_save(world["client"])
    chart = world["outputs"] / SONG / "notes.chart"
    chart.write_bytes(chart.read_bytes() + b"\n")
    response = copy(world["client"])
    assert response.status_code == 409 and response.json()["export_refused"] is True
    assert response.json()["error"] == "notes.chart changed on disk after this song was opened: reload the page first."
    assert response.json()["reason"] == "disk_changed"
    assert list(world["songs"].iterdir()) == []


def test_a_folder_that_does_not_validate_is_not_copied(world):
    (world["outputs"] / SONG / "song.ini").write_text("[song]\nname = \nartist = \n", encoding="utf-8")
    response = copy(world["client"])
    assert response.status_code == 409 and "error" in response.json()["error"] and "not copied" in response.json()["error"]
    assert response.json()["reason"] == "invalid" and response.json()["errors"] >= 1
    assert list(world["songs"].iterdir()) == []


def test_without_a_songs_folder_copy_to_game_is_off(tmp_path):
    outputs = tmp_path / "outputs"
    make_song(outputs)
    client = TestClient(create_app(SongLibrary(outputs), draft_delay_s=60), base_url="http://127.0.0.1:8765")
    assert client.get(url("info")).json()["game"] == {"songs": None, "ready": False}
    response = copy(client)
    assert response.status_code == 409 and "--songs" in response.json()["error"] and response.json()["reason"] == "no_songs"
    missing = tmp_path / "nowhere"
    client = TestClient(create_app(SongLibrary(outputs), draft_delay_s=60, songs=missing), base_url="http://127.0.0.1:8765")
    assert client.get(url("info")).json()["game"] == {"songs": str(missing), "ready": False}
    assert "There is no Clone Hero Songs folder" in copy(client).json()["error"]
    assert copy(client).json()["reason"] == "no_songs"


def test_copy_to_game_needs_the_editors_header(world):
    response = world["client"].post(url("export"), json={"version": version(world["client"])})
    assert response.status_code == 403


def test_the_default_songs_folder_is_clone_heros_own():
    assert default_songs_dir().parts[-3:] == ("Documents", "Clone Hero", "Songs")
