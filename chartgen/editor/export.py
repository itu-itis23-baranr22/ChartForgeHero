"""Copying a song folder to the game (SPEC 56, E.4.0; owner's decisions 2026-11-25 in docs/STATUS.md, "E.4 planı").

Refused while Clone Hero runs, while the song has unsaved edits ("Save first") and when the folder does not pass
the validator. When the game's ``Songs`` folder has the song and its audio is the same (the same ``.ogg`` names,
and each file the same bytes or, after a rebuild, the same decoded samples), only ``notes.chart`` and ``song.ini``
are copied and everything else there stays (a ``debug_click.wav``, the layout the owner chose); otherwise the
whole folder is replaced, so no stem of an older build is left to play along. What will be replaced is backed up
first to ``<outputs>/_songs_backup/<date_time>_editor/<song>/``: the two files, or the whole folder when the
whole folder goes. The copy in ``Songs`` is validated afterwards.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from chartgen.clonehero.protection import CHART_FILE
from chartgen.clonehero.validate import validate_song_folder
from chartgen.errors import ChartgenError

GAME = "Clone Hero.exe"
SONGS_BACKUP_DIR = "_songs_backup"
SONG_INI = "song.ini"


class ExportRefusedError(ChartgenError):
    """The song is not copied: the game runs, edits are unsaved, or the folder is not valid.

    ``reason`` names the case for the page's notification (``no_songs``, ``running``, ``unknown_game``,
    ``invalid``, ``unsaved``, ``disk_changed``); ``errors`` is the validator's error count for ``invalid``.
    """

    def __init__(self, message: str, reason: str, errors: int = 0) -> None:
        super().__init__(message)
        self.reason = reason
        self.errors = errors


def default_songs_dir() -> Path:
    """Where Clone Hero keeps its songs on Windows: ``Documents\\Clone Hero\\Songs``."""
    return Path.home() / "Documents" / "Clone Hero" / "Songs"


def game_running() -> bool:
    """Whether Clone Hero runs now (``tasklist`` on Windows, ``ps`` elsewhere; no extra package)."""
    try:
        if sys.platform == "win32":
            listing = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {GAME}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=15, check=False,
            ).stdout
        else:
            listing = subprocess.run(["ps", "-A", "-o", "comm="], capture_output=True, text=True, timeout=15, check=False).stdout
    except (OSError, subprocess.SubprocessError) as error:
        raise ExportRefusedError(f"Could not tell whether Clone Hero is running ({error}), so nothing was copied.", "unknown_game") from error
    return GAME.lower() in listing.lower() or "clone hero" in listing.lower()


def _decoded_equal(a: Path, b: Path) -> bool:
    try:
        left, left_rate = sf.read(str(a), dtype="float32", always_2d=True)
        right, right_rate = sf.read(str(b), dtype="float32", always_2d=True)
    except (sf.LibsndfileError, RuntimeError):
        return False
    return left_rate == right_rate and left.shape == right.shape and bool(np.array_equal(left, right))


def same_audio(source: Path, target: Path) -> bool:
    """The same ``.ogg`` names, and each file the same bytes or the same decoded samples (owner's decision 3).
    A rebuild writes new Ogg stream numbers, so equal sound can come in different bytes."""
    names = sorted(p.name for p in source.glob("*.ogg"))
    if not names or names != sorted(p.name for p in target.glob("*.ogg")):
        return False
    for name in names:
        if (source / name).read_bytes() != (target / name).read_bytes() and not _decoded_equal(source / name, target / name):
            return False
    return True


def _copy_file(source: Path, target: Path) -> None:
    temporary = target.with_name(f".{target.name}.copying")
    shutil.copyfile(source, temporary)
    os.replace(temporary, target)


def copy_to_game(source: Path, songs: Path, backups: Path, running: Callable[[], bool] = game_running) -> dict[str, Any]:
    """Copy the saved song folder ``source`` into ``songs``; see the module. Returns what was done."""
    if not songs.is_dir():
        raise ExportRefusedError(f"There is no Clone Hero Songs folder at {songs}: start chartgen edit with --songs <folder>.", "no_songs")
    if running():
        raise ExportRefusedError("Clone Hero is running: close it, then copy the song (the game keeps its files open).", "running")
    report = validate_song_folder(source)
    if report.errors:
        count = len(report.errors)
        raise ExportRefusedError(f"The song folder has {count} error{'s' if count != 1 else ''}, so it was not copied (see Problems).", "invalid", count)
    target = songs / source.name
    backup = backups / f"{time.strftime('%Y-%m-%d_%H%M%S')}_editor" / source.name
    existed = target.is_dir()
    if existed and same_audio(source, target):
        backup.mkdir(parents=True, exist_ok=True)
        for name in (CHART_FILE, SONG_INI):
            if (target / name).is_file():
                shutil.copy2(target / name, backup / name)
        for name in (CHART_FILE, SONG_INI):
            _copy_file(source / name, target / name)
        mode = "chart"
        message = (f"Copied notes.chart and song.ini to {target}; the audio there is the same. "
                   f"The game's previous files are in {backup}.")
    else:
        staging = songs / f".{source.name}.copying"
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(source, staging)
        if existed:
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(target, backup)
            old = songs / f".{source.name}.old"
            if old.exists():
                shutil.rmtree(old)
            os.replace(target, old)
            os.replace(staging, target)
            shutil.rmtree(old, ignore_errors=True)
            message = (f"Copied the whole folder to {target}: its audio differs from the game's copy. "
                       f"The game's previous folder is in {backup}.")
        else:
            os.replace(staging, target)
            message = f"Copied the song to {target}. Rescan the songs in Clone Hero's settings to see it in the list."
        mode = "folder"
    after = validate_song_folder(target)
    return {
        "mode": mode,
        "new": not existed,
        "target": str(target),
        "backup": str(backup) if existed else None,
        "message": message,
        "errors": after.errors,
    }
