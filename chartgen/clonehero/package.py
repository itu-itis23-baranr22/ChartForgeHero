"""Audio encoding and song folder layout.

Encoding uses libsndfile through ``soundfile`` instead of an external ffmpeg
binary: it is already a dependency for reading audio, so the tool installs with
pip alone. Every encoded file is decoded again and checked against its source.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import correlate

from chartgen.audio.io import to_mono
from chartgen.audio.presence import StemPresence
from chartgen.chart.instruments import STEM_FOR_INSTRUMENT
from chartgen.core.model import Instrument
from chartgen.errors import PackagingError

AUDIO_FILE_FOR_STEM: Mapping[str, str] = {
    "guitar": "guitar.ogg",
    "bass": "bass.ogg",
    "drums": "drums.ogg",
    "piano": "keys.ogg",
    "vocals": "vocals.ogg",
}
BACKING_FILE = "song.ogg"
BACKING_STEM = "other"

VORBIS_COMPRESSION_LEVEL = 0.3
"""libsndfile's 0 (best quality) to 1 (smallest file) scale."""
_WRITE_BLOCK_FRAMES = 65536
_PEAK_CEILING = 0.99
_LAG_WINDOW_S = 4.0
_MAX_LAG_FRAMES = 8192
_SILENT_RMS = 1e-4
PREVIEW_WINDOW_S = 30.0

_FORBIDDEN_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_WINDOWS_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


@dataclass(frozen=True)
class AudioPlan:
    """Which stems are summed into which audio file."""

    files: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class EncodedAudio:
    file_name: str
    stems: tuple[str, ...]
    frames: int
    size_bytes: int
    lag_frames: int | None
    """Measured offset against the source; None when the file is too quiet to measure."""


def folder_name(artist: str, title: str) -> str:
    """Return ``Artist - Title`` as a name that is safe on every platform."""
    cleaned = _FORBIDDEN_PATH_CHARS.sub("_", f"{artist} - {title}")
    cleaned = " ".join(cleaned.split()).rstrip(" .")
    if not cleaned or cleaned.upper() in _RESERVED_WINDOWS_NAMES:
        cleaned = f"_{cleaned}"
    return cleaned


def plan_audio(
    presence: Mapping[str, StemPresence], requested: frozenset[Instrument]
) -> AudioPlan:
    """Decide the audio files.

    A stem gets its own file when its instrument was requested and is really there
    (vocals only need to be there). All other stems go into the backing track
    rather than being dropped: otherwise a stem rejected by the presence check, such
    as a quiet piano, would vanish from the song.
    """
    instrument_of_stem = {stem: inst for inst, stem in STEM_FOR_INSTRUMENT.items()}
    files: dict[str, tuple[str, ...]] = {}
    backing = [BACKING_STEM]
    for stem, file_name in AUDIO_FILE_FOR_STEM.items():
        instrument = instrument_of_stem.get(stem)
        wanted = instrument is None or instrument in requested
        if wanted and presence[stem].present:
            files[file_name] = (stem,)
        else:
            backing.append(stem)
    files[BACKING_FILE] = tuple(backing)
    return AudioPlan(files)


def encode_ogg(samples: np.ndarray, samplerate: int, path: Path) -> None:
    """Write Ogg Vorbis in blocks. Writing a song in one call overflows the stack inside
    libsndfile on Windows, which kills the process rather than raising an error."""
    with sf.SoundFile(
        str(path),
        mode="w",
        samplerate=samplerate,
        channels=samples.shape[1],
        format="OGG",
        subtype="VORBIS",
        compression_level=VORBIS_COMPRESSION_LEVEL,
    ) as stream:
        for start in range(0, samples.shape[0], _WRITE_BLOCK_FRAMES):
            stream.write(samples[start : start + _WRITE_BLOCK_FRAMES])


def measure_lag(reference: np.ndarray, decoded: np.ndarray, samplerate: int) -> int | None:
    """Return how many frames ``decoded`` trails ``reference``, measured around the
    loudest few seconds. Returns None when there is too little signal to tell."""
    source, result = to_mono(reference), to_mono(decoded)
    if np.sqrt(np.mean(np.square(source))) < _SILENT_RMS:
        return None
    window = min(int(_LAG_WINDOW_S * samplerate), len(source))
    energy = np.convolve(np.square(source[::256]), np.ones(max(1, window // 256)), mode="same")
    center = int(np.argmax(energy)) * 256
    start = int(np.clip(center - window // 2, 0, len(source) - window))
    a = source[start : start + window]
    b = result[start : start + window]
    a = a - a.mean()
    b = b - b.mean()
    correlation = correlate(b, a, mode="full", method="fft")
    middle = len(a) - 1
    span = min(_MAX_LAG_FRAMES, middle)
    region = correlation[middle - span : middle + span + 1]
    return int(np.argmax(region)) - span


def write_audio_files(
    stems: Mapping[str, np.ndarray], samplerate: int, plan: AudioPlan, directory: Path
) -> list[EncodedAudio]:
    """Render, encode and verify every planned file.

    One shared gain keeps the balance between the files. Each result must decode to
    the source's exact length with zero lag.

    Raises:
        PackagingError: If encoding fails or a file fails its check.
    """
    rendered = {
        file_name: np.sum([stems[stem] for stem in names], axis=0)
        for file_name, names in plan.files.items()
    }
    peak = max(float(np.abs(samples).max()) for samples in rendered.values())
    gain = _PEAK_CEILING / peak if peak > _PEAK_CEILING else 1.0

    results: list[EncodedAudio] = []
    for file_name, samples in rendered.items():
        path = directory / file_name
        scaled = samples * gain
        try:
            encode_ogg(scaled, samplerate, path)
            decoded, decoded_rate = sf.read(str(path), dtype="float32", always_2d=True)
        except (sf.LibsndfileError, RuntimeError, OSError) as error:
            raise PackagingError(f"Could not encode {file_name}: {error}") from error
        if decoded_rate != samplerate or decoded.shape != scaled.shape:
            raise PackagingError(
                f"{file_name} decoded to {decoded.shape} at {decoded_rate} Hz, "
                f"expected {scaled.shape} at {samplerate} Hz"
            )
        lag = measure_lag(scaled, decoded, samplerate)
        if lag not in (0, None):
            raise PackagingError(f"{file_name} is misaligned by {lag} frames after encoding")
        results.append(
            EncodedAudio(file_name, plan.files[file_name], decoded.shape[0], path.stat().st_size, lag)
        )
    return results


def best_preview_start_ms(
    mono: np.ndarray, samplerate: int, window_s: float = PREVIEW_WINDOW_S
) -> int:
    """Return the start of the loudest window, used as the song-list preview."""
    if mono.size == 0:
        return 0
    block = max(1, samplerate // 10)
    usable = len(mono) // block
    if usable == 0:
        return 0
    energy = np.sum(np.square(mono[: usable * block].reshape(usable, block)), axis=1)
    span = int(window_s * samplerate / block)
    if span >= usable:
        return 0
    cumulative = np.concatenate(([0.0], np.cumsum(energy)))
    totals = cumulative[span:] - cumulative[:-span]
    return int(int(np.argmax(totals)) * block * 1000 / samplerate)
