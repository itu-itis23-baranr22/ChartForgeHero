"""The page's files under content-named addresses and the cache headers (E.2 cache fix; see assets.py)."""

from __future__ import annotations

import re
import shutil
import threading
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from chartgen.editor.assets import PageAssets  # noqa: E402
from chartgen.editor.server import API_HEADER, API_VERSION, STATIC, create_app  # noqa: E402
from chartgen.editor.songs import SongLibrary  # noqa: E402

PLAIN_IMPORT = re.compile(r"""from\s*["']\./[\w.-]+\.js["']""")
VERSIONED = r"\?v=[0-9a-f]{12}"


@pytest.fixture
def static(tmp_path: Path) -> Path:
    return shutil.copytree(STATIC, tmp_path / "static")


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    (tmp_path / "outputs").mkdir()
    return TestClient(create_app(SongLibrary(tmp_path / "outputs")), base_url="http://127.0.0.1:8765")


def test_every_local_link_names_the_version_of_its_file(static):
    assets = PageAssets(static)
    for module in sorted(p.name for p in static.glob("*.js")):
        text = assets.render(module).decode("utf-8")
        assert not PLAIN_IMPORT.search(text), module
    app = assets.render("app.js").decode("utf-8")
    assert f'from "./api.js?v={assets.version("api.js")}"' in app
    page = assets.render("index.html").decode("utf-8")
    for name in ("app.js", "boot.js", "style.css"):
        assert re.search(rf'"{re.escape(name)}{VERSIONED}"', page), name


def test_a_changed_file_changes_the_address_of_everything_that_leads_to_it(static):
    assets = PageAssets(static)
    before = {name: assets.version(name) for name in ("api.js", "app.js", "timeline.js", "edit.js", "index.html")}
    api = static / "api.js"
    api.write_text(api.read_text(encoding="utf-8") + "\n// changed\n", encoding="utf-8")
    after = {name: assets.version(name) for name in before}
    assert after["api.js"] != before["api.js"]
    assert after["app.js"] != before["app.js"]  # app.js imports api.js
    assert after["index.html"] != before["index.html"]  # the page loads app.js
    assert after["timeline.js"] == before["timeline.js"] and after["edit.js"] == before["edit.js"]
    css = static / "style.css"
    css.write_text(css.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert assets.version("index.html") != after["index.html"]


@pytest.mark.parametrize("name", ["../api.js", "fonts/x.js", ".hidden.js", "style.css", "missing.js", "OFL.txt"])
def test_only_the_pages_own_files_are_rendered(static, name):
    with pytest.raises(FileNotFoundError):
        PageAssets(static).render(name)


def test_the_page_is_revalidated_and_versioned_files_are_kept(client):
    page = client.get("/")
    assert page.status_code == 200 and page.headers["cache-control"] == "no-cache"
    assert page.headers["content-type"].startswith("text/html")
    etag = page.headers["etag"]
    assert client.get("/", headers={"If-None-Match": etag}).status_code == 304
    app_url = re.search(rf'src="(app\.js{VERSIONED})"', page.text).group(1)
    module = client.get(f"/{app_url}")
    assert module.status_code == 200 and module.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert module.headers["content-type"].startswith("text/javascript")
    assert client.get("/app.js").headers["cache-control"] == "no-cache"
    assert client.get("/style.css").headers["cache-control"] == "no-cache"
    assert client.get("/fonts/barlow-semi-condensed-latin-400-normal.woff2").headers["cache-control"] == "no-cache"
    assert client.get("/api/songs").headers["cache-control"] == "no-store"
    assert client.get("/nothing.js").status_code == 404


def test_every_answer_names_the_api_version(client):
    for path in ("/", "/app.js", "/style.css", "/api/songs", "/api/songs/nobody/chart"):
        assert client.get(path).headers[API_HEADER] == str(API_VERSION), path


def test_the_page_and_the_server_speak_the_same_api_version():
    text = (STATIC / "api.js").read_text(encoding="utf-8")
    assert re.search(r"export const API_VERSION = (\d+);", text).group(1) == str(API_VERSION)


def test_chartgen_edit_opens_the_address_of_this_page_version(tmp_path, monkeypatch):
    uvicorn = pytest.importorskip("uvicorn")
    from chartgen.cli import _build_parser, _run_edit

    opened = []

    class Timer:
        def __init__(self, _delay, function, args):
            self.call = (function, args)

        def start(self):
            opened.append(self.call[1][0])

    monkeypatch.setattr(threading, "Timer", Timer)
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: None)
    (tmp_path / "outputs").mkdir()
    _run_edit(_build_parser().parse_args(["edit", "--outputs", str(tmp_path / "outputs")]))
    version = PageAssets(STATIC).version("index.html")
    assert opened == [f"http://127.0.0.1:8765/?v={version}"]
