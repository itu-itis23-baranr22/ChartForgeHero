"""Turns a stem into an Expert track: onsets, pitch, sustains and fret mapping."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.onsets import OnsetConfig, detect_onsets
from chartgen.audio.pitch import (
    NotePitch,
    PitchConfig,
    analyze_pitches,
    chord_limit_for,
    contour_with_repeats,
)
from chartgen.audio.sustain import SustainConfig, note_durations
from chartgen.audio.vocal_bleed import BleedThresholds, NoteBleed, analyze_bleed
from chartgen.chart.fret_mapping import FretWeights, NoteInput, map_notes
from chartgen.core.model import ChartNote, Difficulty, Instrument, Track
from chartgen.core.timing import TempoMap

GRID_DIVISOR = 4
"""Snap to sixteenth notes: a quarter note divided by this."""
SNAP_TOLERANCE_S = 0.035
"""An onset further than this from the grid keeps its exact position."""
MIN_NOTE_GAP_S = 0.09
"""Closer notes are not reliably playable on a guitar controller."""
END_MARGIN_S = 0.1
MIN_SUSTAIN_BEATS = 0.75
"""Human charts leave shorter notes unsustained: in one measured chart, no note lasted
between a sixteenth and an eighth note."""
SUSTAIN_GAP_BEATS = 0.25
"""A sustain ends this long before the next note, so the hand can change position."""


@dataclass(frozen=True)
class ChartedTrack:
    track: Track
    onset_count: int
    pitches: tuple[NotePitch, ...] = ()
    bleed: tuple[NoteBleed, ...] = ()
    """Every detected note compared with the vocals, including the ones removed."""
    chord_limit: float = 0.0
    chord_limit_adjusted: bool = False
    """Whether the song is so flat that the temporary median-based chord limit is in force."""


def _quantize(times: np.ndarray, tempo_map: TempoMap) -> np.ndarray:
    """Return integer ticks, on the sixteenth-note grid wherever that is close enough."""
    if times.size == 0:
        return np.empty(0, dtype=np.int64)
    exact = tempo_map.ticks_at(times)
    grid = tempo_map.resolution // GRID_DIVISOR
    snapped = np.round(exact / grid) * grid
    close = np.abs(tempo_map.seconds_at(snapped) - times) <= SNAP_TOLERANCE_S
    return np.where(close, snapped, np.round(exact)).astype(np.int64)


def _thin_out(ticks: np.ndarray, strengths: np.ndarray, tempo_map: TempoMap) -> np.ndarray:
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


def _sustain_ticks(
    ticks: np.ndarray, durations: np.ndarray, tempo_map: TempoMap
) -> np.ndarray:
    """Convert ring times into chart lengths: zero for short notes, on the sixteenth grid for
    long ones, and always ending before the next note."""
    resolution = tempo_map.resolution
    grid = resolution // GRID_DIVISOR
    gap = int(SUSTAIN_GAP_BEATS * resolution)
    lengths = np.zeros(ticks.size, dtype=np.int64)
    for index, (tick, duration) in enumerate(zip(ticks, durations)):
        end_tick = tempo_map.ticks_at(float(tempo_map.seconds_at(float(tick)) + duration))
        length = int(end_tick - tick)
        if index + 1 < ticks.size:
            length = min(length, int(ticks[index + 1] - tick) - gap)
        if length >= MIN_SUSTAIN_BEATS * resolution:
            lengths[index] = length - length % grid
    return lengths


def build_expert_track(
    instrument: Instrument,
    mono: np.ndarray,
    tempo_map: TempoMap,
    duration_s: float,
    samplerate: int = ANALYSIS_SAMPLERATE,
    onset_config: OnsetConfig | None = None,
    pitch_config: PitchConfig | None = None,
    sustain_config: SustainConfig | None = None,
    weights: FretWeights | None = None,
    vocals: np.ndarray | None = None,
    bleed_thresholds: BleedThresholds | None = None,
) -> ChartedTrack:
    """Build an Expert track from a mono stem. No onsets gives a track without notes.

    With ``vocals``, notes that look like the singer leaking into this stem are removed.
    """
    onsets = detect_onsets(mono, samplerate, onset_config)
    keep = onsets.times < duration_s - END_MARGIN_S
    times, strengths = onsets.times[keep], onsets.strengths[keep]
    if times.size == 0:
        return ChartedTrack(Track(instrument, Difficulty.EXPERT), int(onsets.times.size))

    ticks = _quantize(times, tempo_map)
    chosen = _thin_out(ticks, strengths, tempo_map)
    times, ticks = times[chosen], ticks[chosen]
    next_times = np.r_[times[1:], duration_s]

    bleed: tuple[NoteBleed, ...] = ()
    if vocals is not None:
        bleed = tuple(
            analyze_bleed(mono, vocals, times, next_times, samplerate, bleed_thresholds)
        )
        kept = np.array([not note.removed for note in bleed], dtype=bool)
        times, ticks = times[kept], ticks[kept]
        next_times = np.r_[times[1:], duration_s]
        if times.size == 0:
            return ChartedTrack(
                Track(instrument, Difficulty.EXPERT), int(onsets.times.size), bleed=bleed
            )

    pitches = analyze_pitches(mono, times, next_times, samplerate, pitch_config)
    durations = note_durations(mono, times, next_times, samplerate, sustain_config)
    lengths = _sustain_ticks(ticks, durations, tempo_map)

    placed = tempo_map.seconds_at(ticks.astype(np.float64))
    contour = contour_with_repeats(pitches, (pitch_config or PitchConfig()).repeat_similarity)
    inputs = [
        NoteInput(float(time), float(value), pitch.voices)
        for time, value, pitch in zip(placed, contour, pitches)
    ]
    shapes = map_notes(inputs, weights)
    notes = [
        ChartNote(int(tick), lane, int(length))
        for tick, length, shape in zip(ticks, lengths, shapes)
        for lane in shape
    ]
    cfg = pitch_config or PitchConfig()
    limit = chord_limit_for([pitch.flatness for pitch in pitches if pitch.is_known], cfg)
    return ChartedTrack(
        Track(instrument, Difficulty.EXPERT, notes),
        int(onsets.times.size),
        tuple(pitches),
        bleed,
        limit,
        limit > cfg.chord_flatness,
    )
