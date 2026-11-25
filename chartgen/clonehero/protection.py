"""Hand edits are never lost silently (SPEC 55, E.3.0): what makes a song folder count as edited.

A build records the hash of the ``notes.chart`` it wrote in ``analysis.json`` (``notes_chart_sha256``). A folder
counts as edited when it holds the editor's mark (``chartgen_edits.json``, written by every save) or when its
``notes.chart`` no longer has the recorded hash (an edit by any tool). A folder with no recorded hash (built
before E.3) is "not recorded": ``chartgen protect --record`` records it once, but only when a fresh build gives
the same chart byte for byte.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ANALYSIS_FILE = "analysis.json"
CHART_FILE = "notes.chart"
EDIT_MARK = "chartgen_edits.json"
"""Written by the editor's saves; a folder holding it counts as edited."""
HASH_KEY = "notes_chart_sha256"

PROTECTED = "protected"
EDITED = "edited"
NOT_RECORDED = "not recorded"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_analysis(folder: Path) -> dict | None:
    path = folder / ANALYSIS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def recorded_sha256(folder: Path) -> str | None:
    analysis = read_analysis(folder)
    value = analysis.get(HASH_KEY) if analysis else None
    return value if isinstance(value, str) else None


def hand_edits(folder: Path) -> str | None:
    """Why the folder counts as edited, or None. A folder whose hash is not recorded is not edited."""
    if (folder / EDIT_MARK).is_file():
        return f"it holds {EDIT_MARK}: it was saved in the editor"
    recorded = recorded_sha256(folder)
    chart = folder / CHART_FILE
    if recorded is not None and chart.is_file() and file_sha256(chart) != recorded:
        return f"its {CHART_FILE} is not the one the build wrote (changed by hand or by another tool)"
    return None


def state(folder: Path) -> tuple[str, str | None]:
    """``protected``, ``edited`` (with the reason) or ``not recorded``."""
    reason = hand_edits(folder)
    if reason:
        return EDITED, reason
    return (PROTECTED, None) if recorded_sha256(folder) is not None else (NOT_RECORDED, None)


def dump_analysis(analysis: dict) -> str:
    """``analysis.json`` as the build writes it."""
    return json.dumps(analysis, indent=2, ensure_ascii=False)


def record(folder: Path, digest: str) -> None:
    """Add the chart's hash to ``analysis.json``, changing nothing else in it (written atomically)."""
    analysis = read_analysis(folder)
    if analysis is None:
        raise ValueError(f"{folder / ANALYSIS_FILE} is missing or unreadable")
    analysis[HASH_KEY] = digest
    path = folder / ANALYSIS_FILE
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(dump_analysis(analysis), encoding="utf-8")
    os.replace(temporary, path)
