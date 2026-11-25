"""The editor's server (SPEC 49-51): song list, chart, info and audio, and nothing outside the song folders."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402
from test_chart_reader import every_feature  # noqa: E402

from chartgen.clonehero.chart_format import DotChartExporter  # noqa: E402
from chartgen.clonehero.package import encode_ogg  # noqa: E402
from chartgen.clonehero.song_ini import SongIni, render_song_ini  # noqa: E402
from chartgen.core.model import Instrument  # noqa: E402
from chartgen.editor.server import create_app  # noqa: E402
from chartgen.editor.songs import CYMBAL, EDIT_MARK, FORCED, TAP, SongLibrary, locate  # noqa: E402

SONG = "Mor ve Ötesi - Bir Derdim Var"
OTHER = "The Lantern Choir - Paper Satellites"


def make_song(root: Path, name: str, edited: bool = False) -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    chart = every_feature()
    DotChartExporter().export(chart, folder)
    difficulties = {Instrument.GUITAR: 3, Instrument.BASS: 2, Instrument.DRUMS: 0, Instrument.KEYS: 1}
    (folder / "song.ini").write_text(
        render_song_ini(SongIni(chart.metadata, 12_000, 2_000, 0, difficulties)), encoding="utf-8", newline="\n"
    )
    encode_ogg(np.zeros((44100, 2), dtype=np.float32), 44100, folder / "song.ogg")
    encode_ogg(np.zeros((44100, 2), dtype=np.float32), 44100, folder / "guitar.ogg")
    if edited:
        (folder / EDIT_MARK).write_text("{}", encoding="utf-8")
    return folder


@pytest.fixture
def outputs(tmp_path: Path) -> Path:
    root = tmp_path / "outputs"
    make_song(root, SONG)
    make_song(root, OTHER, edited=True)
    make_song(root, "_songs_backup")  # not a song: starts with _
    (root / "No Chart - Here").mkdir()  # not a song: no notes.chart
    (root / "loose.txt").write_text("x", encoding="utf-8")
    return root


@pytest.fixture
def client(outputs: Path) -> TestClient:
    return TestClient(create_app(SongLibrary(outputs)), base_url="http://127.0.0.1:8765")


def url(name: str, rest: str) -> str:
    from urllib.parse import quote

    return f"/api/songs/{quote(name, safe='')}/{rest}"


def test_the_list_holds_the_song_folders_only(client, outputs):
    data = client.get("/api/songs").json()
    assert data["root"] == str(outputs.resolve())
    songs = {s["id"]: s for s in data["songs"]}
    assert list(songs) == [SONG, OTHER]
    assert songs[SONG]["instruments"] == ["guitar", "bass", "drums", "keys"]
    assert songs[SONG]["length_s"] == 12.0
    assert songs[SONG]["edited"] is False
    assert songs[OTHER]["edited"] is True


def test_the_chart_comes_as_ticks_and_flags(client):
    response = client.get(url(SONG, "chart"))
    assert response.status_code == 200
    data = response.json()
    assert data["resolution"] == 192
    assert data["tempos"][0] == [0, 156.654]
    assert data["time_signatures"][-1] == [6528, 6, 8]
    assert data["sections"] == [[0, "Intro"], [768, "A1"]]
    tracks = {(t["instrument"], t["difficulty"]): t for t in data["tracks"]}
    guitar = tracks["guitar", "expert"]
    assert [864, 2, 192, 0] in guitar["notes"]
    assert [960, 3, 0, FORCED] in guitar["notes"]
    assert [1056, 4, 0, TAP] in guitar["notes"]
    assert [1152, 5, 96, 0] in guitar["notes"]
    assert guitar["star_power"] == [[768, 768]]
    assert [768, 2, 0, CYMBAL] in tracks["drums", "expert"]["notes"]


def test_info_has_the_audio_ini_and_the_validator(client):
    data = client.get(url(SONG, "info")).json()
    assert [a["file"] for a in data["audio"]] == ["guitar.ogg", "song.ogg"]
    assert data["song_ini"]["name"] == "Paper Satellites"
    assert data["preview_s"] == 2.0
    assert set(data["validation"]) == {"errors", "warnings"}
    assert data["edited"] is False


def test_audio_is_served_from_the_folder_only(client):
    response = client.get(url(SONG, "audio/song.ogg"))
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/ogg"
    assert response.content[:4] == b"OggS"
    for bad in ("audio/song.ini", "audio/..%2Fsong.ini", "audio/notes.chart", "audio/missing.ogg"):
        assert client.get(url(SONG, bad)).status_code == 404, bad


@pytest.mark.parametrize("name", ["_songs_backup", "No Chart - Here", "loose.txt", "..", "../outputs", "C:\\Windows", ""])
def test_nothing_outside_the_song_folders_is_reachable(client, name):
    response = client.get(url(name, "chart"))
    assert response.status_code == 404


def test_a_path_with_dots_cannot_climb_out(client):
    assert client.get("/api/songs/..%2F..%2Fpyproject.toml/chart").status_code == 404
    assert client.get("/api/songs/%2E%2E/chart").status_code == 404


def test_another_host_is_refused(outputs):
    for host in ("http://evil.example", "http://192.168.1.10:8765"):
        client = TestClient(create_app(SongLibrary(outputs)), base_url=host)
        assert client.get("/api/songs").status_code == 400, host
    assert TestClient(create_app(SongLibrary(outputs)), base_url="http://localhost:8765").get("/api/songs").status_code == 200


def test_responses_forbid_anything_from_outside(client):
    response = client.get("/api/songs")
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    page = client.get("/")
    assert page.status_code == 200
    assert '<script type="module" src="app.js">' in page.text
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert "access-control-allow-origin" not in response.headers


def test_the_page_and_its_fonts_are_served_locally(client):
    css = client.get("/style.css").text
    assert "http" not in css.replace("http-equiv", "")
    for name in ("fonts/barlow-semi-condensed-latin-400-normal.woff2", "fonts/cascadia-mono-latin-ext-400-normal.woff2", "tempo.js"):
        assert client.get(f"/{name}").status_code == 200, name


def test_an_unreadable_chart_says_why(client, outputs):
    path = outputs / SONG / "notes.chart"
    path.write_text(path.read_text(encoding="utf-8-sig").replace("[Events]\n{", "[Events]\n{\n  10 = E \"lyric hi\""), encoding="utf-8")
    response = client.get(url(SONG, "chart"))
    assert response.status_code == 422
    assert "only sections" in response.json()["error"]


def test_validator_messages_point_at_a_track_and_tick():
    assert locate("[HardSingle] tick 17280: a chord of 3 notes") == {"instrument": "guitar", "difficulty": "hard", "tick": 17280}
    assert locate("[ExpertDrums] tick 96: the kick with a pad") == {"instrument": "drums", "difficulty": "expert", "tick": 96}
    assert locate("[HardSingle] has tick 6160, but [ExpertSingle] does not") == {"instrument": "guitar", "difficulty": "hard", "tick": 6160}
    assert locate("song.ini has no name") is None
    assert locate("[SyncTrack] tick 5: bad") is None


def test_the_cli_has_an_edit_command():
    from chartgen.cli import _build_parser

    args = _build_parser().parse_args(["edit", "--port", "9000", "--no-browser"])
    assert (args.command, args.port, args.no_browser, args.outputs) == ("edit", 9000, True, Path("outputs"))
