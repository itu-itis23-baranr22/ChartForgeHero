"""A simple onset-based track generator.

This is the Phase A charter: notes come from detected onsets and lanes from the
brightness of each attack. It proves the pipeline end to end but is not a real
fret mapper. Phase B replaces it with playability-aware Viterbi mapping and
difficulty reduction.
"""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np

from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.onsets import HOP_LENGTH, OnsetConfig, detect_onsets
from chartgen.core.model import LANE_COUNT, ChartNote, Difficulty, Instrument, Track
from chartgen.core.timing import TempoMap

GRID_DIVISOR = 4
"""Snap to sixteenth notes: a quarter note divided by this."""
SNAP_TOLERANCE_S = 0.035
"""An onset further than this from the grid keeps its exact position."""
MIN_NOTE_GAP_S = 0.09
"""Closer notes are not reliably playable on a guitar controller."""
MAX_LANE_JUMP = 2
END_MARGIN_S = 0.1
_CENTROID_WINDOW_S = 0.06


@dataclass(frozen=True)
class SimpleTrackResult:
    track: Track
    onset_count: int


def _lanes_from_brightness(mono: np.ndarray, samplerate: int, times: np.ndarray) -> np.ndarray:
    """Bucket each onset's spectral centroid into lanes by the song's own quantiles,
    then limit jumps so that the result stays playable."""
    if times.size == 0:
        return np.empty(0, dtype=int)
    centroid = librosa.feature.spectral_centroid(
        y=mono, sr=samplerate, n_fft=2048, hop_length=HOP_LENGTH
    )[0]
    start = librosa.time_to_frames(times, sr=samplerate, hop_length=HOP_LENGTH)
    span = max(1, int(_CENTROID_WINDOW_S * samplerate / HOP_LENGTH))
    values = np.array(
        [centroid[frame : frame + span].mean() if frame < len(centroid) else 0.0 for frame in start]
    )
    edges = np.quantile(values, np.linspace(0, 1, LANE_COUNT + 1)[1:-1])
    raw = np.digitize(values, edges)

    lanes = np.empty_like(raw)
    previous = int(raw[0])
    for index, lane in enumerate(raw):
        previous = int(np.clip(lane, previous - MAX_LANE_JUMP, previous + MAX_LANE_JUMP))
        lanes[index] = previous
    return lanes


def _quantize(times: np.ndarray, tempo_map: TempoMap) -> np.ndarray:
    """Return integer ticks, on the sixteenth-note grid wherever that is close enough."""
    if times.size == 0:
        return np.empty(0, dtype=np.int64)
    exact = tempo_map.ticks_at(times)
    grid = tempo_map.resolution // GRID_DIVISOR
    snapped = np.round(exact / grid) * grid
    close = np.abs(tempo_map.seconds_at(snapped) - times) <= SNAP_TOLERANCE_S
    return np.where(close, snapped, np.round(exact)).astype(np.int64)


def _thin_out(
    ticks: np.ndarray, strengths: np.ndarray, tempo_map: TempoMap
) -> np.ndarray:
    """Return indices of the notes to keep: of two notes that are too close, the stronger."""
    kept: list[int] = []
    for index in np.argsort(ticks, kind="stable"):
        if kept:
            gap = tempo_map.seconds_at(float(ticks[index])) - tempo_map.seconds_at(
                float(ticks[kept[-1]])
            )
            if gap < MIN_NOTE_GAP_S:
                if strengths[index] > strengths[kept[-1]]:
                    kept[-1] = int(index)
                continue
        kept.append(int(index))
    return np.array(kept, dtype=np.int64)


def build_simple_track(
    instrument: Instrument,
    mono: np.ndarray,
    tempo_map: TempoMap,
    duration_s: float,
    samplerate: int = ANALYSIS_SAMPLERATE,
    onset_config: OnsetConfig | None = None,
) -> SimpleTrackResult:
    """Build an Expert track from a mono stem. No onsets gives a track without notes."""
    onsets = detect_onsets(mono, samplerate, onset_config)
    keep = onsets.times < duration_s - END_MARGIN_S
    times, strengths = onsets.times[keep], onsets.strengths[keep]

    lanes = _lanes_from_brightness(mono, samplerate, times)
    ticks = _quantize(times, tempo_map)
    chosen = _thin_out(ticks, strengths, tempo_map) if ticks.size else np.empty(0, dtype=np.int64)
    notes = [ChartNote(int(ticks[i]), int(lanes[i])) for i in chosen]
    return SimpleTrackResult(Track(instrument, Difficulty.EXPERT, notes), int(onsets.times.size))
