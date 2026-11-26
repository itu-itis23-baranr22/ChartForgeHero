"""Copy to game in a real browser (E.4.0), with Playwright 1.65.1 and a temporary folder standing in for Clone
Hero's Songs: an unsaved edit asks to save first; saved, the song is copied and the page says where."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

from test_editor_edit_browser import BAR, BEAT, FOLDER, make_edit_song  # noqa: E402
from test_editor_sync import node, run_browser, serve  # noqa: E402, F401  (node is a fixture)

from chartgen.clonehero.validate import validate_song_folder  # noqa: E402
from chartgen.editor.server import create_app  # noqa: E402
from chartgen.editor.songs import SongLibrary  # noqa: E402

pytestmark = pytest.mark.heavy

SHOTS = Path(__file__).resolve().parents[1] / ".impeccable" / "review" / "e4"


def test_copy_to_game_in_the_browser(node, tmp_path):  # noqa: F811
    outputs = tmp_path / "outputs"
    folder = make_edit_song(outputs)
    songs = tmp_path / "Clone Hero" / "Songs"
    songs.mkdir(parents=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    app = create_app(SongLibrary(outputs), draft_delay_s=60, songs=songs, running=lambda: False)
    plan = {"song": FOLDER, "ticks": [2 * BAR + BEAT, 3 * BAR + BEAT], "shots": str(SHOTS)}
    with serve(None, app=app) as url:
        out = run_browser(node, {"mode": "copy", "step": "copy", "url": url, **plan}, tmp_path, "save.mjs")
    assert not out["problems"], out["problems"]
    assert out["copyEnabledAtFirst"] is True and str(songs) in out["copyTitle"]
    first = out["saveFirst"]
    assert first["tone"] == "warning" and first["role"] == "alert" and first["icon"] == "Warning" and first["title"] == "Save first"
    assert first["text"] == "The game gets the song as it is saved, and 1 edit is not saved yet."
    assert first["actions"] == ["Save"]
    assert out["afterSaveAction"]["copy"] is None and out["afterSaveAction"]["save"]["title"] == "Saved"
    new = out["copiedNew"]
    assert new["tone"] == "success" and new["title"] == "Copied to game"
    assert new["text"] == "A new song: rescan the songs in Clone Hero's settings to see it in the list."
    assert new["pathLabel"] == "In the game" and new["path"] == str(songs / FOLDER)
    again = out["copiedAgain"]
    assert again["tone"] == "success" and again["title"] == "Copied to game"
    assert again["text"] == "Only notes.chart and song.ini were replaced; the audio in the game is the same."
    assert again["pathLabel"] == "The game's previous files are backed up in"
    backup = Path(again["path"])
    assert backup.parent.parent == outputs / "_songs_backup" and backup.name == FOLDER
    assert sorted(p.name for p in backup.iterdir()) == ["notes.chart", "song.ini"]
    assert again["pathShown"] == str(backup.relative_to(tmp_path)) and again["pathShown"].startswith("outputs\\")
    assert out["copyPathLabel"] == "Copied" and out["clipboard"] == str(backup)  # the whole path, ready to paste
    assert out["lightStill"] is True
    for toast in (first, new, again):
        assert toast["titlePx"] >= 16 and toast["textPx"] >= 15
        assert toast["inView"] and not toast["overProblems"] and not toast["overTransport"] and not toast["overHeader"]
    target = songs / FOLDER
    assert (target / "notes.chart").read_bytes() == (folder / "notes.chart").read_bytes()
    assert validate_song_folder(target).ok
