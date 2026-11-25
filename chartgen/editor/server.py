"""The editor's local HTTP server (SPEC 49): JSON under ``/api``, the page from ``static/``.

Bound to 127.0.0.1 by ``chartgen edit``. A request naming any other host is refused (a web page elsewhere
cannot reach this server through DNS rebinding), there is no CORS, and every response forbids loading
anything from outside the machine.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from chartgen.editor.songs import SongLibrary, SongNotFoundError, chart_json, load_chart, song_info, song_summary
from chartgen.errors import ChartReadError

STATIC = Path(__file__).with_name("static")
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
    "media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
)


def create_app(library: SongLibrary) -> FastAPI:
    app = FastAPI(title="chartgen editor", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

    @app.middleware("http")
    async def headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(SongNotFoundError)
    async def not_found(_: Request, error: SongNotFoundError) -> JSONResponse:
        return JSONResponse({"error": str(error)}, status_code=404)

    @app.exception_handler(ChartReadError)
    async def unreadable(_: Request, error: ChartReadError) -> JSONResponse:
        return JSONResponse({"error": f"The chart cannot be opened: {error}"}, status_code=422)

    @app.get("/api/songs")
    def songs() -> dict[str, object]:
        return {"root": str(library.root.resolve()), "songs": [song_summary(f) for f in library.folders()]}

    @app.get("/api/songs/{name}/chart")
    def chart(name: str) -> dict[str, object]:
        return chart_json(load_chart(library.folder(name)))

    @app.get("/api/songs/{name}/info")
    def info(name: str) -> dict[str, object]:
        return song_info(library.folder(name))

    @app.get("/api/songs/{name}/audio/{file_name}")
    def audio(name: str, file_name: str) -> FileResponse:
        return FileResponse(library.audio_file(name, file_name), media_type="audio/ogg")

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app
