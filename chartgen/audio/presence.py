"""Decide whether a separated stem really holds its instrument.

A separation model always outputs every stem. For a song without a piano, the
piano stem still contains faint bleed from other instruments. Charting that
would produce notes for an instrument the song does not have.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from chartgen.audio.io import to_mono

FRAME_SECONDS = 0.1
ACTIVE_WITHIN_DB = 20.0
"""A frame counts as active when the stem is within this distance of the mix."""
SILENCE_RMS = 1e-4


@dataclass(frozen=True)
class PresenceThreshold:
    min_energy_ratio_db: float
    min_active_ratio: float


DEFAULT_THRESHOLDS: Mapping[str, PresenceThreshold] = {
    "guitar": PresenceThreshold(-25.0, 0.10),
    "bass": PresenceThreshold(-25.0, 0.10),
    "drums": PresenceThreshold(-25.0, 0.10),
    "vocals": PresenceThreshold(-25.0, 0.05),
    # The piano stem of htdemucs_6s is the model's weakest, so it must prove more.
    "piano": PresenceThreshold(-18.0, 0.25),
}


@dataclass(frozen=True)
class StemPresence:
    stem: str
    present: bool
    energy_ratio_db: float
    active_ratio: float
    threshold: PresenceThreshold


def _frame_rms(mono: np.ndarray, frame_length: int) -> np.ndarray:
    count = len(mono) // frame_length
    if count == 0:
        return np.sqrt(np.mean(np.square(mono), keepdims=True))
    frames = mono[: count * frame_length].reshape(count, frame_length)
    return np.sqrt(np.mean(np.square(frames), axis=1))


def analyze_presence(
    stem_name: str,
    stem: np.ndarray,
    mix: np.ndarray,
    samplerate: int,
    threshold: PresenceThreshold | None = None,
) -> StemPresence:
    """Compare a stem's energy with the mix, overall and frame by frame.

    Args:
        stem_name: Key into :data:`DEFAULT_THRESHOLDS` when ``threshold`` is not given.
        stem: The stem's audio.
        mix: The mix the stem belongs to, sample-aligned with ``stem``.
        samplerate: Sample rate shared by both signals.
        threshold: Overrides the default limits.
    """
    limits = threshold or DEFAULT_THRESHOLDS[stem_name]
    stem_mono, mix_mono = to_mono(stem), to_mono(mix)
    if stem_mono.shape != mix_mono.shape:
        raise ValueError(f"stem and mix differ in shape: {stem_mono.shape}, {mix_mono.shape}")

    mix_energy = float(np.sum(np.square(mix_mono)))
    stem_energy = float(np.sum(np.square(stem_mono)))
    if mix_energy <= 0 or stem_energy <= 0:
        return StemPresence(stem_name, False, float("-inf"), 0.0, limits)
    energy_ratio_db = 10.0 * np.log10(stem_energy / mix_energy)

    frame_length = max(1, int(FRAME_SECONDS * samplerate))
    stem_rms = _frame_rms(stem_mono, frame_length)
    mix_rms = _frame_rms(mix_mono, frame_length)
    audible = mix_rms > SILENCE_RMS
    within_mix = stem_rms >= mix_rms * 10.0 ** (-ACTIVE_WITHIN_DB / 20.0)
    active_ratio = float(np.mean(within_mix[audible])) if audible.any() else 0.0

    present = (
        energy_ratio_db >= limits.min_energy_ratio_db and active_ratio >= limits.min_active_ratio
    )
    return StemPresence(stem_name, bool(present), float(energy_ratio_db), active_ratio, limits)
