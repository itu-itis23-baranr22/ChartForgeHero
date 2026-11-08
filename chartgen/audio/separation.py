"""Stem separation with Demucs, cached by the input file's hash.

Separation takes minutes on a CPU, so a song is only ever separated once. Torch
and Demucs are imported lazily: everything except real separation works, and
the default test run passes, without them.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import soundfile as sf

from chartgen.audio.io import AudioData, file_sha256
from chartgen.errors import SeparationError

log = logging.getLogger(__name__)

STEM_NAMES = ("drums", "bass", "other", "vocals", "guitar", "piano")
"""The six sources of the ``htdemucs_6s`` model."""

_MANIFEST = "manifest.json"
_CACHE_VERSION = 1


@dataclass(frozen=True)
class StemSet:
    """Separated stems, each shaped ``(frames, channels)``."""

    samplerate: int
    stems: Mapping[str, np.ndarray]
    source_sha256: str
    separator_id: str
    from_cache: bool

    @property
    def frames(self) -> int:
        return next(iter(self.stems.values())).shape[0]

    @property
    def duration_s(self) -> float:
        return self.frames / self.samplerate


class Separator(Protocol):
    """Anything that can split audio into :data:`STEM_NAMES`."""

    @property
    def cache_id(self) -> str:
        """Identifies the model and settings; a different id means a different cache entry."""
        ...

    def separate(self, audio: AudioData) -> tuple[int, dict[str, np.ndarray]]:
        """Return the output sample rate and the stems."""
        ...


def resolve_device(requested: str) -> str:
    """Return the torch device for ``requested``, preferring a GPU under ``auto``."""
    if requested != "auto":
        return requested
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class DemucsSeparator:
    """Runs a pretrained Demucs model through its Python API."""

    def __init__(
        self,
        model_name: str = "htdemucs_6s",
        device: str = "auto",
        shifts: int = 1,
        overlap: float = 0.25,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.shifts = shifts
        self.overlap = overlap

    @property
    def cache_id(self) -> str:
        return f"{self.model_name}-shifts{self.shifts}-overlap{self.overlap}"

    def separate(self, audio: AudioData) -> tuple[int, dict[str, np.ndarray]]:
        # The weights come from Hugging Face. Windows without developer mode cannot make
        # the symlinks its cache prefers; it works anyway, so the warning is only noise.
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        try:
            import torch
            from demucs.apply import apply_model
            from demucs.pretrained import get_model
        except ImportError as error:
            raise SeparationError(
                'Demucs is not installed. Run: pip install -e ".[separation]"'
            ) from error

        from chartgen.audio.io import resample

        device = resolve_device(self.device)
        log.info("Separating with %s on %s", self.model_name, device)
        try:
            model = get_model(self.model_name)
            model.eval()
            samples = audio.samples
            if samples.shape[1] == 1:
                samples = np.repeat(samples, 2, axis=1)
            elif samples.shape[1] > 2:
                samples = samples[:, :2]
            samples = resample(samples, audio.samplerate, model.samplerate)

            wave = torch.from_numpy(np.asarray(samples, dtype=np.float32).T.copy())
            reference = wave.mean(0)
            mean, std = reference.mean(), reference.std()
            if float(std) == 0.0:
                raise SeparationError("The input audio is silent")
            normalized = (wave - mean) / std
            with torch.no_grad():
                sources = apply_model(
                    model,
                    normalized[None],
                    device=device,
                    shifts=self.shifts,
                    split=True,
                    overlap=self.overlap,
                    progress=True,
                )[0]
            sources = sources * std + mean
        except SeparationError:
            raise
        except (RuntimeError, OSError, ValueError) as error:
            raise SeparationError(f"Demucs failed: {error}") from error

        names = list(model.sources)
        missing = set(STEM_NAMES) - set(names)
        if missing:
            raise SeparationError(f"{self.model_name} lacks the stems {sorted(missing)}")
        stems = {
            name: sources[names.index(name)].cpu().numpy().T.astype(np.float32)
            for name in STEM_NAMES
        }
        return int(model.samplerate), stems


def _entry_dir(cache_dir: Path, sha256: str, cache_id: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", cache_id)
    return cache_dir / f"{sha256[:24]}-{slug}"


def _load_entry(entry: Path, sha256: str, cache_id: str) -> StemSet | None:
    """Return a cached entry, or None when it is absent or does not check out."""
    manifest_path = entry / _MANIFEST
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest["cache_version"] != _CACHE_VERSION
            or manifest["sha256"] != sha256
            or manifest["separator"] != cache_id
        ):
            return None
        stems: dict[str, np.ndarray] = {}
        for name in STEM_NAMES:
            samples, rate = sf.read(str(entry / f"{name}.flac"), dtype="float32", always_2d=True)
            if rate != manifest["samplerate"] or samples.shape[0] != manifest["frames"]:
                return None
            stems[name] = samples / float(manifest["scale"])
    except (OSError, KeyError, ValueError, TypeError, sf.LibsndfileError) as error:
        log.warning("Ignoring unreadable stem cache %s: %s", entry.name, error)
        return None
    return StemSet(manifest["samplerate"], stems, sha256, cache_id, from_cache=True)


def _write_entry(entry: Path, stems: StemSet) -> None:
    """Write the entry into a temporary folder and rename it, so that an interrupted
    run never leaves a half-written entry behind."""
    entry.parent.mkdir(parents=True, exist_ok=True)
    peak = max(float(np.abs(samples).max()) for samples in stems.stems.values())
    # FLAC is integer PCM: Demucs output can exceed 1.0 and would clip without scaling.
    scale = min(1.0, 0.999 / peak) if peak > 0 else 1.0
    temporary = Path(tempfile.mkdtemp(prefix=f".{entry.name}.", dir=entry.parent))
    try:
        for name, samples in stems.stems.items():
            sf.write(
                str(temporary / f"{name}.flac"),
                samples * scale,
                stems.samplerate,
                format="FLAC",
                subtype="PCM_24",
            )
        manifest = {
            "cache_version": _CACHE_VERSION,
            "sha256": stems.source_sha256,
            "separator": stems.separator_id,
            "samplerate": stems.samplerate,
            "frames": stems.frames,
            "scale": scale,
        }
        (temporary / _MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if entry.exists():
            shutil.rmtree(entry)
        os.replace(temporary, entry)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def separate_with_cache(
    audio_path: Path, audio: AudioData, separator: Separator, cache_dir: Path
) -> StemSet:
    """Return the stems of ``audio_path``, separating only on a cache miss."""
    sha256 = file_sha256(audio_path)
    entry = _entry_dir(cache_dir, sha256, separator.cache_id)
    cached = _load_entry(entry, sha256, separator.cache_id)
    if cached is not None:
        log.info("Using cached stems from %s", entry)
        return cached

    samplerate, separated = separator.separate(audio)
    unexpected = set(separated) ^ set(STEM_NAMES)
    if unexpected:
        raise SeparationError(f"Separator returned unexpected stems: {sorted(unexpected)}")
    shapes = {samples.shape for samples in separated.values()}
    if len(shapes) != 1 or len(next(iter(shapes))) != 2:
        raise SeparationError(f"Separator returned mismatched stem shapes: {shapes}")

    stems = StemSet(samplerate, separated, sha256, separator.cache_id, from_cache=False)
    try:
        _write_entry(entry, stems)
    except (OSError, sf.LibsndfileError) as error:
        log.warning("Could not cache stems: %s", error)
    return stems
