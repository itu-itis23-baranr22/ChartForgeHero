"""The page's own files, each linked under a URL that names its content (E.2, the cache fix).

E.1 served the page's modules with Last-Modified and no Cache-Control, so a browser could keep using an old
copy of one module for hours (a tenth of the file's age) without asking, while it fetched a newer one of
another: after the E.2 update a new ``app.js`` ran against an old ``api.js`` ("api.op is not a function").

Now the page (``index.html``) and every module are served with their local links rewritten to
``name.js?v=<version>``, where the version is a hash of the file and of the versions of everything it imports.
A changed file therefore gets a new URL, and so does every file that leads to it, up to the page itself: no
old copy can be picked up again, whatever a browser stored before. Versioned URLs may be kept for good; the page
and anything else are revalidated on every load (``server.py`` sets the headers).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

_IMPORT = re.compile(rb"""(\b(?:from|import)\s*)(["'])\./([\w.-]+\.js)\2""")
"""``from "./api.js"`` and ``import "./x.js"``: the only way the page's modules load each other."""
_REFERENCE = re.compile(rb"""(\b(?:src|href)=")([\w.-]+\.(?:js|css))(")""")
"""``src="app.js"`` and ``href="style.css"`` in the page."""
_TYPES = {".js": "text/javascript; charset=utf-8", ".html": "text/html; charset=utf-8"}


class PageAssets:
    """The page and its modules in one folder (``chartgen/editor/static``), read from disk on every request."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def media_type(self, name: str) -> str:
        return _TYPES[Path(name).suffix]

    def _read(self, name: str) -> bytes:
        """A file directly in the folder; nothing else (no path, no other kind of file)."""
        if "/" in name or "\\" in name or name.startswith(".") or Path(name).suffix not in _TYPES:
            raise FileNotFoundError(name)
        return (self.root / name).read_bytes()

    def _links(self, name: str, data: bytes) -> list[str]:
        pattern = _IMPORT if name.endswith(".js") else _REFERENCE
        group = 3 if name.endswith(".js") else 2
        return [m.group(group).decode("ascii") for m in pattern.finditer(data)]

    def version(self, name: str, _path: tuple[str, ...] = ()) -> str:
        """12 hex digits naming the file's content and, through their versions, all the files it links to."""
        data = self._read(name)
        digest = hashlib.sha256(data)
        for link in self._links(name, data):
            if link in _path or link == name or not (self.root / link).is_file():
                continue  # a cycle or a missing file: the link's text is already in the hash
            if Path(link).suffix in _TYPES:
                digest.update(self.version(link, (*_path, name)).encode("ascii"))
            else:
                digest.update(hashlib.sha256((self.root / link).read_bytes()).digest())
        return digest.hexdigest()[:12]

    def _file_version(self, link: str) -> str | None:
        if not (self.root / link).is_file():
            return None
        if Path(link).suffix in _TYPES:
            return self.version(link)
        return hashlib.sha256((self.root / link).read_bytes()).hexdigest()[:12]

    def render(self, name: str) -> bytes:
        """The file as served: every local link carries the version of the file it names."""
        data = self._read(name)
        if name.endswith(".js"):
            def module(m: re.Match[bytes]) -> bytes:
                version = self._file_version(m.group(3).decode("ascii"))
                url = m.group(3) + (f"?v={version}".encode("ascii") if version else b"")
                return m.group(1) + m.group(2) + b"./" + url + m.group(2)

            return _IMPORT.sub(module, data)

        def reference(m: re.Match[bytes]) -> bytes:
            version = self._file_version(m.group(2).decode("ascii"))
            return m.group(1) + m.group(2) + (f"?v={version}".encode("ascii") if version else b"") + m.group(3)

        return _REFERENCE.sub(reference, data)
