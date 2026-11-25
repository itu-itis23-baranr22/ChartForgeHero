"""The editor after an update, in a browser that kept the old files (E.2 cache fix), with Playwright 1.65.1.

What happened (2026-11-25): E.1 served the page's modules with Last-Modified and no Cache-Control, so the
owner's browser kept using an old ``api.js`` it guessed was still fresh while it fetched the new ``app.js``:
"api.op is not a function". Here an old version of the page is served the way E.1 served it (plain static
files, a month old), loaded into a persistent profile, and then the current server answers on the same
address: the page must load only new files and edit, although the old ones are still in the cache.

Also: a page and a server of different API versions show a warning that says what to do, and a page whose
modules fail to start says how to recover instead of staying on "Loading".
"""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

from starlette.applications import Starlette  # noqa: E402
from starlette.routing import Mount  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402
from test_editor_edit_browser import BAR, BEAT, FOLDER, make_edit_song  # noqa: E402
from test_editor_sync import free_port, node, run_browser, serve  # noqa: E402, F401  (node is a fixture)

from chartgen.editor import server as editor_server  # noqa: E402
from chartgen.editor.server import STATIC, create_app  # noqa: E402
from chartgen.editor.songs import SongLibrary  # noqa: E402

pytestmark = pytest.mark.heavy

MONTH = 30 * 86400


def old_version(target: Path) -> Path:
    """The page as an older release had it: api.js without the editing calls, timeline.js without noteAt,
    every file a month old (so that a browser guesses it fresh for days)."""
    shutil.copytree(STATIC, target)
    api = (target / "api.js").read_text(encoding="utf-8")
    api = re.sub(r"^\s*op: .*\n", "", api, flags=re.M).replace("API_VERSION = 2", "API_VERSION = 1")
    (target / "api.js").write_text(api, encoding="utf-8")
    timeline = target / "timeline.js"
    timeline.write_text(timeline.read_text(encoding="utf-8").replace("noteAt(", "hit("), encoding="utf-8")
    then = time.time() - MONTH
    for path in target.rglob("*"):
        os.utime(path, (then, then))
    return target


def step(node_path: str, tmp_path: Path, plan: dict) -> dict:
    return run_browser(node_path, {"mode": plan["step"], **plan}, tmp_path, "cache.mjs")


def test_a_browser_with_the_old_files_cached_loads_the_new_ones(node, tmp_path):  # noqa: F811
    outputs = tmp_path / "outputs"
    make_edit_song(outputs)
    old = old_version(tmp_path / "old_static")
    profile = str(tmp_path / "profile")
    port = free_port()

    # The old release, served as E.1 served it: Last-Modified, no Cache-Control.
    with serve(None, port, Starlette(routes=[Mount("/", StaticFiles(directory=old, html=True))])) as url:
        warm = step(node, tmp_path, {"step": "warm", "url": url, "profile": profile})
    assert {s["url"] for s in warm["scripts"]} >= {"/app.js", "/api.js", "/timeline.js"}

    app = create_app(SongLibrary(outputs))
    address = f"/?v={app.state.assets.version('index.html')}"  # what chartgen edit opens
    with serve(None, port, app) as url:
        fresh = step(node, tmp_path, {"step": "fresh", "url": url, "profile": profile, "path": address,
                                      "song": FOLDER, "tick": 2 * BAR + BEAT})
        reloaded = step(node, tmp_path, {"step": "reload", "url": url, "profile": profile})

    assert not fresh["problems"], fresh["problems"]
    # The old api.js is still in the cache: there was an old copy to pick up, and it was not.
    assert fresh["cachedApi"] is not None and "op:" not in fresh["cachedApi"]
    # Every module came under a versioned address, so none of the old copies could stand in for it.
    modules = [s["url"] for s in fresh["scripts"] if s["url"] != "/api.js"]
    assert modules and all(re.search(r"\.js\?v=[0-9a-f]{12}$", u) for u in modules), modules
    assert {u.split("?")[0] for u in modules} >= {"/app.js", "/api.js", "/edit.js", "/timeline.js", "/boot.js"}
    assert fresh["unsaved"] == "1 unsaved edit", fresh
    # Later visits to the plain address get the current page as well (it is revalidated every time).
    assert reloaded["started"] and not reloaded["problems"], reloaded
    assert all("?v=" in s["url"] for s in reloaded["scripts"]), reloaded["scripts"]


@pytest.mark.parametrize(
    ("server_version", "words"),
    [
        (3, "The editor was updated after this page was opened. Reload the page"),
        (1, "This page is newer than the editor server that is running. Stop chartgen edit"),
    ],
)
def test_a_page_and_a_server_of_different_versions_say_what_to_do(node, tmp_path, monkeypatch, server_version, words):  # noqa: F811
    outputs = tmp_path / "outputs"
    make_edit_song(outputs)
    monkeypatch.setattr(editor_server, "API_VERSION", server_version)
    with serve(outputs) as url:
        out = step(node, tmp_path, {"step": "banner", "url": url, "profile": str(tmp_path / "profile")})
    assert out["banner"] and out["banner"].startswith(words), out
    assert out["button"] == "Reload the page"


def test_a_page_that_does_not_start_says_how_to_recover(node, tmp_path):  # noqa: F811
    broken = tmp_path / "static"
    shutil.copytree(STATIC, broken)
    (broken / "view.js").write_text("export const = ;\n", encoding="utf-8")  # a module that cannot load
    outputs = tmp_path / "outputs"
    make_edit_song(outputs)
    with serve(None, app=create_app(SongLibrary(outputs), static=broken)) as url:
        out = step(node, tmp_path, {"step": "boot", "url": url, "profile": str(tmp_path / "profile")})
    assert out["box"] and out["box"].startswith("The editor did not start"), out
    assert "Ctrl+Shift+R" in out["box"] and "Console" in out["box"]
