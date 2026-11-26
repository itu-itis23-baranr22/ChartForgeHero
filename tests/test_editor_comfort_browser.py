"""E.4.1 in a real browser, with Playwright 1.65.1: triplet grids, the keyboard alone, sections, star power and
the preview, and Keep pitch, on the synthetic edit song (120 BPM, 4/4, guitar Expert and Hard)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

from test_editor_edit_browser import BAR, FOLDER, make_edit_song  # noqa: E402
from test_editor_sync import node, run_browser, serve  # noqa: E402, F401  (node is a fixture)

from chartgen.editor.server import create_app  # noqa: E402
from chartgen.editor.songs import SongLibrary  # noqa: E402

pytestmark = pytest.mark.heavy

SHOTS = Path(__file__).resolve().parents[1] / ".impeccable" / "review" / "e4"


def test_the_comfort_features_in_the_browser(node, tmp_path):  # noqa: F811
    outputs = tmp_path / "outputs"
    make_edit_song(outputs)
    SHOTS.mkdir(parents=True, exist_ok=True)
    with serve(None, app=create_app(SongLibrary(outputs), draft_delay_s=60)) as url:
        out = run_browser(node, {"mode": "comfort", "url": url, "song": FOLDER, "shots": str(SHOTS), "bar3": 2 * BAR},
                          tmp_path, "comfort.mjs")
    assert not out["problems"], out["problems"]
    # no Songs folder (tests never get the real one): Copy to game looks passive and a click says why
    assert out["copyMissing"] is True
    assert out["copyNotice"]["tone"] == "warning" and out["copyNotice"]["title"] == "No Songs folder"
    assert out["copyNotice"]["text"] == "No Clone Hero Songs folder is set: start chartgen edit with --songs <folder>."
    # c) the grids, triplets included
    assert out["grids"] == ["1/4", "1/8", "1/12", "1/16", "1/24"]
    # b) the keyboard: the first notes after the playhead (bar 2: a single note, then beat 3), back, and a note
    # added with "2" (red) on the 1/12 grid two steps from the start
    assert out["firstNext"] == [f"{BAR}:1"] and out["secondNext"] == [f"{BAR + 384}:3"] and out["back"] == [f"{BAR}:1"]
    assert out["playheadTick"] == 128
    assert out["added"] == [[128, 1, 0, 0]]
    # d) on bar 3 (bar 1 has the Intro): a section named by typing, star power on every level, the preview, the
    # section selected on the ruler and deleted
    bar3 = 2 * BAR
    assert out["focusedName"] is True and out["sections"] == [[0, "Intro"], [bar3, "Verse"]]
    assert dict((level, phrases) for level, phrases in out["starPower"]) == {"expert": [[bar3, BAR]], "hard": [[bar3, BAR]]}
    assert out["preview"] == 4.0
    assert "Sections\n2" in out["facts"] and "Preview\n0:04.000" in out["facts"]
    assert out["selectedStructure"] == {"kind": "section", "tick": bar3}
    assert "Verse" in out["inspector"] and "One bar later" in out["inspector"]
    assert out["afterDelete"] == [[0, "Intro"]]
    # a) keep pitch at 0.75x: every stem's stretched copy in place
    assert out["keepPitch"]["on"] is True and out["keepPitch"]["slow"] == [0.75, 0.75]
    assert out["keepPitch"]["notice"] == "Keep pitch is on at 0.75×."
