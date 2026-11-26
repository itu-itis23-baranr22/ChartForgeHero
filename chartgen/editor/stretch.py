"""Slowed-down audio that keeps its pitch (E.4.1 a; SPEC 53 left it to E.4).

The page's speed control slows the audio through the playback rate, so the pitch drops with it. For "Keep pitch"
each stem is stretched in time here instead, once per file and speed, with librosa's phase vocoder (already a
dependency), and kept in ``<outputs>/_editor_cache/stretch/``. The page plays the stretched file at full rate
from ``song time / speed``; its clock and metronome stay as they are, so the sync of E.1 holds.

The stretch runs in a child Python process (``python -m chartgen.editor.stretch``), not in the editor's own:
librosa brings scipy and numba with it, and once they were in the editor's heap every full garbage collection
walked them, stalling an edit by 100-130 ms now and then (measured on LastResort, 2026-11-26). The child also
gives its memory back when it ends.

The stretched copy is mono: the browser holds every stem decoded, and a stereo copy at half speed would add
about 150 MB per stem to a three-minute song; for listening slowly the stereo image does not matter.

The vocoder's window is 512 samples (hop 128): a stretch spreads a hit over about half a window, and 512 keeps a
click's start within 8 ms of its beat where librosa's default 2048 moved it by up to 30 ms (measured on the sync
test's click stems, 2026-11-25). The price is a grainier low end, which matters less here than the timing.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import threading
from pathlib import Path

from chartgen.errors import ChartgenError

CACHE_DIR = "_editor_cache"
SPEEDS = (0.5, 0.6, 0.7, 0.75, 0.8, 0.9)
"""The page's speeds below 1x (transport.js SPEEDS)."""
N_FFT = 512
HOP = 128
TIMEOUT_S = 600
CANNOT_READ = 3
"""The child's exit code for audio it cannot read."""

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


class StretchError(ChartgenError):
    """A speed the page does not offer, or audio that cannot be read or stretched."""


def _lock(key: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def stretched(source: Path, speed: float, cache: Path) -> Path:
    """The stretched (mono) copy of ``source`` at ``speed``, made once in a child process and then read from
    ``cache``."""
    if speed not in SPEEDS:
        raise StretchError(f"Keep pitch works at {', '.join(f'{s:.2f}x' for s in SPEEDS)}, not at {speed}.")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:20]
    target = cache / f"{digest}_{int(round(speed * 100))}_n{N_FFT}.ogg"
    with _lock(str(target)):
        if target.is_file():
            return target
        cache.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.writing")
        command = [sys.executable, "-X", "utf8", "-m", "chartgen.editor.stretch", str(source), repr(speed), str(temporary)]
        try:
            done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=TIMEOUT_S, check=False)
        except subprocess.TimeoutExpired as error:
            temporary.unlink(missing_ok=True)
            raise StretchError(f"{source.name} took longer than {TIMEOUT_S} s to stretch.") from error
        if done.returncode != 0 or not temporary.is_file():
            temporary.unlink(missing_ok=True)
            lines = [line for line in done.stderr.splitlines() if line.strip()]
            reason = lines[-1] if lines else f"exit code {done.returncode}"
            if done.returncode == CANNOT_READ:
                raise StretchError(f"{source.name} cannot be read: {reason}")
            raise StretchError(f"{source.name} could not be stretched: {reason}")
        os.replace(temporary, target)
        return target


def stretch_file(source: Path, speed: float, out: Path) -> None:
    """The child's work: ``source`` stretched to ``speed``, mono, written as Ogg Vorbis to ``out``."""
    import librosa
    import numpy as np
    import soundfile as sf

    from chartgen.clonehero.package import encode_ogg

    samples, samplerate = sf.read(str(source), dtype="float32", always_2d=True)
    mono = np.ascontiguousarray(samples.mean(axis=1))
    slow = librosa.effects.time_stretch(mono, rate=speed, n_fft=N_FFT, hop_length=HOP).astype(np.float32)
    encode_ogg(np.clip(slow, -1.0, 1.0)[:, None], samplerate, out)


def main(argv: list[str]) -> int:
    source, speed, out = Path(argv[0]), float(argv[1]), Path(argv[2])
    try:
        import soundfile as sf

        sf.info(str(source))
    except (OSError, RuntimeError) as error:  # LibsndfileError is a RuntimeError
        print(error, file=sys.stderr)
        return CANNOT_READ
    stretch_file(source, speed, out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
