"""Turns a stem into an Expert track: onsets, pitch, sustains and fret mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from chartgen.audio.bass_pitch import note_semitones
from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.onsets import OnsetConfig, detect_onsets
from chartgen.audio.pitch import (
    NotePitch,
    PitchConfig,
    analyze_pitches,
    chord_limit_for,
    contour_with_repeats,
)
from chartgen.audio.quiet_notes import QuietNote, QuietNoteLimits, levels_below_median
from chartgen.audio.sustain import SustainConfig, note_durations
from chartgen.audio.vocal_bleed import BleedThresholds, NoteBleed, analyze_bleed
from chartgen.chart.difficulty import (
    SINGLE_NOTE_INSTRUMENTS,
    LevelMeasures,
    OrangePitches,
    Position,
    SoftTargetResult,
    check_single_notes,
)
from chartgen.chart.fret_mapping import FretWeights, NoteInput, map_notes, single_notes_only
from chartgen.core.model import ChartNote, Difficulty, Instrument, Track
from chartgen.core.timing import TempoMap, seconds_floor

if TYPE_CHECKING:
    from chartgen.chart.drum_charter import DrumChart
    from chartgen.chart.drum_difficulty import DrumLevelMeasures

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
MIN_SUSTAIN_S = seconds_floor(MIN_SUSTAIN_BEATS)
"""A sustain also lasts at least this long, however many beats that is (0.30 s). Without it, a fast song
whose beat was split in two (SPEC 41) sustained its quarter notes: First Date went from 18% to 46%
sustained notes on guitar Expert, against the human's 1%."""
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
    positions: tuple[Position, ...] = ()
    """What the reduction to lower difficulties works from. Expert only."""
    measures: LevelMeasures | None = None
    soft_targets: tuple[SoftTargetResult, ...] = ()
    """How this level compares with its soft targets."""
    quiet_limits: QuietNoteLimits | None = None
    """The limits this stem was checked against, if it was checked for quiet notes."""
    quiet: tuple[QuietNote, ...] = ()
    """The notes under that limit, whether or not the rule is in force."""
    orange_pitches: OrangePitches | None = None
    """Which pitches this level's orange notes are, for instruments whose pitch can be read."""
    drum_chart: DrumChart | None = None
    """What became of a drum stem's hits. Drums, Expert only."""
    drum_measures: DrumLevelMeasures | None = None
    """Plain numbers about a drum level, every level. ``soft_targets`` holds what they are compared with."""


def _quantize(times: np.ndarray, tempo_map: TempoMap) -> np.ndarray:
    """Return integer ticks, on the sixteenth-note grid wherever that is close enough.

    Where a sixteenth lasts less than it does at 150 BPM (:func:`seconds_floor`, 0.1 s), the grid is the
    eighth note instead. Sixteenths 78 ms apart (191 BPM) are so close that an onset a few tens of
    milliseconds late lands on the wrong one: after the beat of First Date was split in two (SPEC 41),
    its bass Expert F1 fell from 0.892 to 0.859 for that reason alone. An onset far from every eighth
    keeps its own time, as it always did.
    """
    if times.size == 0:
        return np.empty(0, dtype=np.int64)
    exact = tempo_map.ticks_at(times)
    sixteenth = tempo_map.resolution // GRID_DIVISOR
    lasts = tempo_map.seconds_at(exact + sixteenth) - tempo_map.seconds_at(exact)
    grid = np.where(lasts >= seconds_floor(1.0 / GRID_DIVISOR) - 1e-6, sixteenth, 2 * sixteenth)
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
        lasts = tempo_map.seconds_at(float(tick + max(length, 0))) - tempo_map.seconds_at(float(tick))
        if length >= MIN_SUSTAIN_BEATS * resolution and lasts >= MIN_SUSTAIN_S - 1e-6:
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
    not_before_s: float = 0.0,
    quiet_limits: QuietNoteLimits | None = None,
) -> ChartedTrack:
    """Build an Expert track from a mono stem. No onsets gives a track without notes.

    With ``vocals``, notes that look like the singer leaking into this stem are removed. Nothing
    lands before ``not_before_s``, where an opening that is not part of the song ends. With
    ``quiet_limits``, notes far below the stem's median note are reported, and removed if the rule
    is in force.
    """
    onsets = detect_onsets(mono, samplerate, onset_config)
    keep = onsets.times < duration_s - END_MARGIN_S
    times, strengths = onsets.times[keep], onsets.strengths[keep]
    ticks = _quantize(times, tempo_map)
    if not_before_s > 0:
        # Judged where each note lands: snapping can carry one across the line.
        allowed = tempo_map.seconds_at(ticks.astype(np.float64)) >= not_before_s
        times, strengths, ticks = times[allowed], strengths[allowed], ticks[allowed]
    if times.size == 0:
        return ChartedTrack(Track(instrument, Difficulty.EXPERT), int(onsets.times.size))

    chosen = _thin_out(ticks, strengths, tempo_map)
    times, ticks, strengths = times[chosen], ticks[chosen], strengths[chosen]
    next_times = np.r_[times[1:], duration_s]

    bleed: tuple[NoteBleed, ...] = ()
    if vocals is not None:
        bleed = tuple(
            analyze_bleed(mono, vocals, times, next_times, samplerate, bleed_thresholds)
        )
        kept = np.array([not note.removed for note in bleed], dtype=bool)
        times, ticks, strengths = times[kept], ticks[kept], strengths[kept]
        next_times = np.r_[times[1:], duration_s]
        if times.size == 0:
            return ChartedTrack(
                Track(instrument, Difficulty.EXPERT), int(onsets.times.size), bleed=bleed
            )

    quiet: tuple[QuietNote, ...] = ()
    if quiet_limits is not None:
        below = levels_below_median(mono, times, next_times, samplerate)
        flagged = below >= quiet_limits.below_median_db
        quiet = tuple(
            QuietNote(float(time), float(value), quiet_limits.enabled)
            for time, value in zip(times[flagged], below[flagged])
        )
        if quiet_limits.enabled and flagged.any():
            times, ticks, strengths = times[~flagged], ticks[~flagged], strengths[~flagged]
            next_times = np.r_[times[1:], duration_s]
            if times.size == 0:
                return ChartedTrack(
                    Track(instrument, Difficulty.EXPERT),
                    int(onsets.times.size),
                    quiet_limits=quiet_limits,
                    quiet=quiet,
                )

    durations = note_durations(mono, times, next_times, samplerate, sustain_config)
    lengths = _sustain_ticks(ticks, durations, tempo_map)
    placed = tempo_map.seconds_at(ticks.astype(np.float64))

    cfg = pitch_config or PitchConfig()
    pitches: list[NotePitch] = []
    limit = 0.0
    if instrument in SINGLE_NOTE_INSTRUMENTS:
        contour = note_semitones(mono, times, next_times, samplerate)
        inputs = [NoteInput(float(time), float(value)) for time, value in zip(placed, contour)]
        shapes = map_notes(inputs, weights, single_notes_only(len(inputs)))
    else:
        pitches = analyze_pitches(mono, times, next_times, samplerate, pitch_config)
        contour = contour_with_repeats(pitches, cfg.repeat_similarity)
        inputs = [
            NoteInput(float(time), float(value), pitch.voices)
            for time, value, pitch in zip(placed, contour, pitches)
        ]
        shapes = map_notes(inputs, weights)
        limit = chord_limit_for([pitch.flatness for pitch in pitches if pitch.is_known], cfg)
    notes = [
        ChartNote(int(tick), lane, int(length))
        for tick, length, shape in zip(ticks, lengths, shapes)
        for lane in shape
    ]
    positions = tuple(
        Position(int(tick), float(time), shape, int(length), float(strength), float(value))
        for tick, time, shape, length, strength, value in zip(
            ticks, placed, shapes, lengths, strengths, contour
        )
    )
    track = Track(instrument, Difficulty.EXPERT, notes)
    check_single_notes(track)
    return ChartedTrack(
        track,
        int(onsets.times.size),
        tuple(pitches),
        bleed,
        limit,
        limit > cfg.chord_flatness,
        positions,
        quiet_limits=quiet_limits,
        quiet=quiet,
    )
