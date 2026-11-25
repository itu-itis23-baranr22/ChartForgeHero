"""The editor's local HTTP server (SPEC 49): JSON under ``/api``, the page from ``static/``.

Bound to 127.0.0.1 by ``chartgen edit``. A request naming any other host is refused (a web page elsewhere
cannot reach this server through DNS rebinding), there is no CORS, and every response forbids loading
anything from outside the machine. A request that changes anything must be JSON and carry the
``X-Chartgen-Editor`` header: a page on another site cannot send that header without a CORS preflight,
which this server never answers, and a request whose Origin is another site is refused as well.

Caching (the E.2 cache fix): the page and its modules are served with their links named by content
(``assets.PageAssets``), so a browser can never mix an old module with a new one. A versioned URL may be kept
for good; everything else is revalidated on every load (no-cache: a 304 when unchanged); the API is never
stored. Every response says which API the server speaks (``X-Chartgen-Api``): a page from another version
tells the user to reload it, or to restart the editor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import Body, Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from chartgen.clonehero.validate import validate_song_folder
from chartgen.editor.assets import PageAssets
from chartgen.editor.ops import OpError
from chartgen.editor.session import NothingToDoError, Sessions, StaleError
from chartgen.editor.songs import (
    SongLibrary,
    SongNotFoundError,
    chart_json,
    song_info,
    song_summary,
    validation_json,
)
from chartgen.errors import ChartReadError

STATIC = Path(__file__).with_name("static")
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
WRITE_HEADER = "X-Chartgen-Editor"
API_HEADER = "X-Chartgen-Api"
API_VERSION = 2
"""The API this server speaks; ``static/api.js`` has the same number (a test checks). Raise both when the page
and the server must change together. 2: E.2 (editing); E.1 and before sent no number."""
KEEP = "public, max-age=31536000, immutable"
REVALIDATE = "no-cache"
_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
    "media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
)


class WriteRefusedError(Exception):
    """A request to change something that did not come from the editor's own page."""


def writable(request: Request) -> None:
    """A change is taken only as JSON with the editor's header, and never from another site's page."""
    if request.headers.get(WRITE_HEADER) != "1":
        raise WriteRefusedError(f"changes need the {WRITE_HEADER} header")
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise WriteRefusedError("changes are sent as JSON")
    origin = request.headers.get("origin")
    if origin and urlsplit(origin).hostname not in ALLOWED_HOSTS:
        raise WriteRefusedError("changes are taken from the editor's own page only")


def create_app(library: SongLibrary, freeze_gc: bool = False, static: Path = STATIC) -> FastAPI:
    """The editor's app. ``freeze_gc`` is for the ``chartgen edit`` process only (see ``Sessions``); ``static``
    is the page's folder (tests give a changed copy)."""
    app = FastAPI(title="chartgen editor", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
    sessions = Sessions(library, freeze_gc)
    assets = PageAssets(static)
    app.state.sessions = sessions
    app.state.assets = assets

    @app.middleware("http")
    async def headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers[API_HEADER] = str(API_VERSION)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        elif "v" in request.query_params:
            response.headers["Cache-Control"] = KEEP
        else:
            response.headers["Cache-Control"] = REVALIDATE
        return response

    @app.exception_handler(SongNotFoundError)
    async def not_found(_: Request, error: SongNotFoundError) -> JSONResponse:
        return JSONResponse({"error": str(error)}, status_code=404)

    @app.exception_handler(ChartReadError)
    async def unreadable(_: Request, error: ChartReadError) -> JSONResponse:
        return JSONResponse({"error": f"The chart cannot be opened: {error}"}, status_code=422)

    @app.exception_handler(OpError)
    async def refused(_: Request, error: OpError) -> JSONResponse:
        return JSONResponse({"error": str(error)}, status_code=422)

    @app.exception_handler(NothingToDoError)
    async def nothing(_: Request, error: NothingToDoError) -> JSONResponse:
        return JSONResponse({"error": str(error)}, status_code=409)

    @app.exception_handler(StaleError)
    async def stale(_: Request, error: StaleError) -> JSONResponse:
        return JSONResponse({"error": str(error), "stale": True}, status_code=409)

    @app.exception_handler(WriteRefusedError)
    async def forbidden(_: Request, error: WriteRefusedError) -> JSONResponse:
        return JSONResponse({"error": f"Refused: {error}."}, status_code=403)

    def session_of(name: str):
        session = sessions.current(name)
        if session is None:
            raise StaleError("This song is not open in the editor any more (was the editor restarted?): reload the page.")
        return session

    @app.get("/api/songs")
    def songs() -> dict[str, object]:
        return {"root": str(library.root.resolve()), "songs": [song_summary(f) for f in library.folders()]}

    @app.get("/api/songs/{name}/chart")
    def chart(name: str) -> dict[str, object]:
        session = sessions.open(name)
        with session.lock:
            return {**chart_json(session.chart), "edit": session.state()}

    @app.get("/api/songs/{name}/info")
    def info(name: str) -> dict[str, object]:
        folder = library.folder(name)
        session = sessions.current(name)
        text = session.chart_text()[1] if session is not None and session.has_history else None
        return song_info(folder, text)

    @app.get("/api/songs/{name}/audio/{file_name}")
    def audio(name: str, file_name: str) -> FileResponse:
        return FileResponse(library.audio_file(name, file_name), media_type="audio/ogg")

    @app.post("/api/songs/{name}/ops", dependencies=[Depends(writable)])
    def operation(name: str, body: dict[str, Any] = Body(...)) -> dict[str, object]:
        return session_of(name).apply(body)

    @app.post("/api/songs/{name}/undo", dependencies=[Depends(writable)])
    def undo(name: str, body: dict[str, Any] = Body(...)) -> dict[str, object]:
        return session_of(name).undo(body.get("version"))

    @app.post("/api/songs/{name}/redo", dependencies=[Depends(writable)])
    def redo(name: str, body: dict[str, Any] = Body(...)) -> dict[str, object]:
        return session_of(name).redo(body.get("version"))

    @app.post("/api/songs/{name}/validate", dependencies=[Depends(writable)])
    def validate(name: str) -> dict[str, object]:
        """The live check: the session's chart as it would be saved, with the rest of the folder."""
        version, text = session_of(name).chart_text()
        return {"version": version, **validation_json(validate_song_folder(library.folder(name), text))}

    def page_file(name: str, request: Request) -> Response:
        """The page or one of its modules, its links versioned; a 304 when the browser has this version."""
        try:
            body = assets.render(name)
            etag = f'"{assets.version(name)}"'
        except FileNotFoundError:
            return JSONResponse({"error": f"no such file: {name}"}, status_code=404)
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag})
        return Response(body, media_type=assets.media_type(name), headers={"ETag": etag})

    @app.get("/", include_in_schema=False)
    def page(request: Request) -> Response:
        return page_file("index.html", request)

    @app.get("/index.html", include_in_schema=False)
    def page_by_name(request: Request) -> Response:
        return page_file("index.html", request)

    @app.get("/{name}.js", include_in_schema=False)
    def module(name: str, request: Request) -> Response:
        return page_file(f"{name}.js", request)

    app.mount("/", StaticFiles(directory=static, html=True), name="static")
    return app
