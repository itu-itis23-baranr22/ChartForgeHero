"""``chartgen protect`` (E.3.0): which song folders a rebuild may replace, and a one-time record for the
folders built before the build recorded its chart's hash (owner, 2026-11-25).

``--record`` rebuilds each such folder with today's code into a scratch folder, from the same input file (found by
name and SHA-256 under the folders given) and the options its ``analysis.json`` and ``song.ini`` hold. Only when
the fresh ``notes.chart`` is the folder's byte for byte is the hash added to ``analysis.json``; any other folder is
listed with the reason and left as it is. Stems come from the cache, so no separation runs again.
"""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from chartgen.audio.separation import Separator
from chartgen.clonehero.protection import (
    CHART_FILE,
    NOT_RECORDED,
    file_sha256,
    read_analysis,
    record,
    state,
)
from chartgen.clonehero.validate import read_song_ini
from chartgen.core.model import Instrument, SongMetadata
from chartgen.errors import ChartgenError

RECORDED = "recorded"
DIFFERENT = "different"
NO_INPUT = "input not found"
FAILED = "rebuild failed"


@dataclass(frozen=True)
class Outcome:
    folder: Path
    status: str
    detail: str = ""


def song_folders(outputs: Path) -> list[Path]:
    """The song folders: those holding a ``notes.chart``, not starting with ``_`` or ``.``."""
    if not outputs.is_dir():
        return []
    return sorted(
        (p for p in outputs.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")) and (p / CHART_FILE).is_file()),
        key=lambda p: p.name.casefold(),
    )


def find_input(file_name: str, sha256: str, inputs: list[Path]) -> Path | None:
    """The input file of a build: a file of that name and that hash under one of ``inputs``."""
    for root in inputs:
        candidates = [root] if root.is_file() else (root.rglob(file_name) if root.is_dir() else [])
        for path in candidates:
            if path.is_file() and path.name == file_name and file_sha256(path) == sha256:
                return path
    return None


def rebuild_config(folder: Path, input_path: Path, output_dir: Path, cache_dir: Path):
    """The build that made ``folder``, as far as its files say: the options it records and its metadata."""
    from chartgen.pipeline import BuildConfig

    analysis = read_analysis(folder) or {}
    ini = read_song_ini(folder / "song.ini")[0]
    tempo = analysis.get("tempo") if isinstance(analysis.get("tempo"), dict) else {}
    metadata = SongMetadata(
        name=ini.get("name", ""),
        artist=ini.get("artist", ""),
        album=ini.get("album", ""),
        genre=ini.get("genre", ""),
        year=ini.get("year", ""),
        charter=ini.get("charter", "chartgen"),
    )
    return BuildConfig(
        input_path=input_path,
        metadata=metadata,
        instruments=frozenset(Instrument(name) for name in analysis.get("charts", {})),
        output_dir=output_dir,
        cache_dir=cache_dir,
        bpm_override=float(tempo["bpm"]) if tempo.get("method") == "override" else None,
        click_overlay=analysis.get("click_overlay") is not None,
        drum_ear_test=analysis.get("drum_ear_test") is not None,
        max_beat_drift_ms=float(tempo.get("max_beat_drift_limit_ms", 25.0)),
    )


@contextmanager
def _quiet_builds() -> Iterator[None]:
    """The rebuilds' stage reports and chart warnings (soft targets, preview, ...) would drown the summary and
    are not what --record checks: only errors pass."""
    names = ["chartgen.pipeline", "chartgen.audio", "chartgen.chart", "chartgen.clonehero"]
    loggers = [logging.getLogger(name) for name in names]
    levels = [logger.level for logger in loggers]
    for logger in loggers:
        logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        for logger, level in zip(loggers, levels):
            logger.setLevel(level)


def _difference(fresh: bytes, current: bytes) -> str:
    new = fresh.decode("utf-8-sig", errors="replace").splitlines()
    old = current.decode("utf-8-sig", errors="replace").splitlines()
    changed = sum(a != b for a, b in zip(new, old)) + abs(len(new) - len(old))
    return f"a fresh build writes a different {CHART_FILE} ({changed} of {max(len(new), len(old))} lines differ)"


def record_folder(folder: Path, inputs: list[Path], cache_dir: Path, separator: Separator) -> Outcome:
    """Record the chart's hash of one folder if a fresh build gives the same chart; otherwise say why not."""
    from chartgen.pipeline import build_song

    status, reason = state(folder)
    if status != NOT_RECORDED:
        return Outcome(folder, status, reason or "")
    analysis = read_analysis(folder)
    source = analysis.get("input") if analysis else None
    if not isinstance(source, dict) or not source.get("file_name") or not source.get("sha256"):
        return Outcome(folder, NO_INPUT, "analysis.json does not name the input file")
    path = find_input(source["file_name"], source["sha256"], inputs)
    if path is None:
        where = ", ".join(str(p) for p in inputs) or "no folder given (--inputs)"
        return Outcome(folder, NO_INPUT, f"{source['file_name']} (SHA-256 {source['sha256'][:12]}...) is not under {where}")
    current = (folder / CHART_FILE).read_bytes()
    with tempfile.TemporaryDirectory(prefix="chartgen-protect-") as scratch:
        try:
            with _quiet_builds():
                result = build_song(rebuild_config(folder, path, Path(scratch), cache_dir), separator)
        except (ChartgenError, ValueError) as error:
            return Outcome(folder, FAILED, str(error))
        fresh = (result.folder / CHART_FILE).read_bytes()
    if fresh != current:
        return Outcome(folder, DIFFERENT, _difference(fresh, current))
    if (folder / CHART_FILE).read_bytes() != current:
        return Outcome(folder, DIFFERENT, f"{CHART_FILE} changed while it was being checked")
    record(folder, file_sha256(folder / CHART_FILE))
    return Outcome(folder, RECORDED, f"built from {path}")
