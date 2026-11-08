"""Tempo map extraction. Runs once, on the original mix; every instrument shares the result.

Most recorded music holds one tempo, and a per-beat tracker is the wrong tool for
it: measured on real songs, ``librosa.beat.beat_track`` often locks onto the wrong
metrical level (129 instead of 97 BPM) and wanders by tens of milliseconds, which
would make every bar line wrong. So the song is analysed as a whole first:

1. The Fourier transform of the whole onset envelope gives the tempo family with a
   precision no tracker reaches, and harmonic support picks the metrical level.
2. Local tempo in 30 second windows tells whether the song really holds that tempo.
   If it does not, a tracker runs, guided by the tempo from step 1, and its beats are
   fitted with few constant segments (method ``variable``).
3. Otherwise, regressing onsets against the grid gives the exact period and phase
   (method ``constant``). A drummer playing without a click wanders by tens of
   milliseconds around that line, in which case the grid is gently bent through the
   onsets, section by section (method ``refined``).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import librosa
import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import find_peaks

from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.onsets import ENVELOPE_LATENCY_S, HOP_LENGTH, OnsetConfig, onset_envelope
from chartgen.core.timing import DEFAULT_RESOLUTION, TempoEvent, TempoMap, TimeSignatureEvent

log = logging.getLogger(__name__)

FALLBACK_BPM = 120.0
MIN_ANALYSIS_SECONDS = 5.0

MIN_BPM = 60.0
MAX_BPM = 160.0
"""Faster songs come out at half speed, which leaves note timing intact and avoids the
far more common mistake of reading a slow song's eighth notes as its beat."""
_BPM_STEP = 0.05
_FFT_SIZE = 1 << 22
HARMONIC_WEIGHTS = {1: 1.0, 2: 1.0, 3: 0.5, 4: 0.5}
"""A real beat is reinforced by the eighth and sixteenth notes played over it."""
TEMPO_PRIOR_CENTER_BPM = 110.0
TEMPO_PRIOR_WIDTH_OCTAVES = 0.6
"""Prefers tempos people count in when several metrical levels fit."""
MIN_TEMPO_STRENGTH = 0.012
"""Below this, the audio has no periodic pulse to speak of."""

LOCAL_WINDOW_S = 30.0
LOCAL_SEARCH_RATIO = 0.12
LOCAL_TEMPO_TOLERANCE = 0.015
MAX_OFF_TEMPO_SHARE = 0.15
"""More windows than this away from the main tempo mean the tempo really changes.
A few are normal: intros and breaks often have no clear pulse."""

GRID_DIVISOR = 4
"""Onsets are matched against sixteenth notes."""
GRID_MATCH_S = 0.035
_REGRESSION_ROUNDS = 4
DRIFT_WINDOW_S = 30.0
MAX_DRIFT_S = 0.012
"""A single tempo must stay this close to the onsets in every window of the song."""
_MIN_WINDOW_ONSETS = 8
REFINE_WINDOW_BEATS = 16
_REFINE_ROUNDS = 3

FIT_TOLERANCE_S = 0.04
"""A segment of a variable-tempo map ends once a beat strays further than this."""
MIN_SEGMENT_BEATS = 16
MERGE_BPM_DIFFERENCE = 0.05
_TRACKER_TIGHTNESS = 400
CURVE_WINDOW_S = 16.0
CURVE_RANGE = (0.6, 1.6)
"""Tempo changes further than this from the main tempo are not followed."""


@dataclass(frozen=True)
class TempoSegment:
    first_beat: int
    last_beat: int
    start_s: float
    period_s: float


@dataclass(frozen=True)
class TempoAnalysis:
    tempo_map: TempoMap
    bpm: float
    """The main tempo: the single tempo, or the most common one of a variable song."""
    method: str
    """``constant``, ``refined``, ``variable`` or ``fallback``."""
    segment_count: int
    on_grid_ratio: float
    """Share of strong onsets within :data:`GRID_MATCH_S` of a sixteenth note."""
    grid_error_p95_ms: float
    tempo_strength: float

    @property
    def is_fallback(self) -> bool:
        return self.method == "fallback"


def _harmonic_scores(
    envelope: np.ndarray, frame_rate: float, fft_size: int = _FFT_SIZE
) -> tuple[np.ndarray, np.ndarray, float]:
    """Return candidate BPMs, their scores, and the strength of the best raw peak."""
    centered = envelope - envelope.mean()
    energy = float(np.dot(centered, centered))
    bpms = np.arange(MIN_BPM, MAX_BPM + _BPM_STEP, _BPM_STEP)
    if energy <= 0:
        return bpms, np.zeros_like(bpms), 0.0

    spectrum = np.abs(np.fft.rfft(centered, n=fft_size)) / np.sqrt(energy * len(centered))
    bins_per_bpm = fft_size / (frame_rate * 60.0)

    def magnitude(values: np.ndarray) -> np.ndarray:
        index = np.round(values * bins_per_bpm).astype(np.int64)
        return spectrum[np.clip(index, 0, len(spectrum) - 1)]

    scores = sum(weight * magnitude(bpms * k) for k, weight in HARMONIC_WEIGHTS.items())
    prior = np.exp(
        -0.5 * (np.log2(bpms / TEMPO_PRIOR_CENTER_BPM) / TEMPO_PRIOR_WIDTH_OCTAVES) ** 2
    )
    return bpms, scores * prior, float(magnitude(bpms * 2).max())


def select_tempo(envelope: np.ndarray, frame_rate: float) -> tuple[float, float]:
    """Return the most plausible BPM of the whole song and the strength of its pulse."""
    bpms, scores, strength = _harmonic_scores(envelope, frame_rate)
    return float(bpms[int(np.argmax(scores))]), strength


def local_tempo_curve(envelope: np.ndarray, frame_rate: float, bpm: float) -> np.ndarray:
    """Return a tempo for each envelope frame, for songs whose tempo really changes."""
    length = min(int(CURVE_WINDOW_S * frame_rate), len(envelope))
    hop = max(1, length // 4)
    starts = np.arange(0, len(envelope) - length + 1, hop)
    estimates = np.empty(len(starts))
    for number, start in enumerate(starts):
        bpms, scores, _ = _harmonic_scores(envelope[start : start + length], frame_rate, 1 << 18)
        near = (bpms >= bpm * CURVE_RANGE[0]) & (bpms <= bpm * CURVE_RANGE[1])
        estimates[number] = bpms[near][int(np.argmax(scores[near]))] if near.any() else bpm
    smoothed = median_filter(estimates, size=3, mode="nearest")
    return np.interp(np.arange(len(envelope)), starts + length / 2, smoothed)


def off_tempo_share(envelope: np.ndarray, frame_rate: float, bpm: float) -> float:
    """Return the share of the song's windows whose local tempo differs from ``bpm``.

    A window must disagree at both the beat and its double, because a song often shows
    only one of them clearly. Higher multiples must stay out of this: 600 BPM is a
    harmonic of 120 and of 150 alike, so it would hide a change between those tempos.
    """
    length = min(int(LOCAL_WINDOW_S * frame_rate), len(envelope))
    fft_size = 1 << 17
    bpm_per_bin = frame_rate * 60.0 / fft_size
    taper = np.hanning(length)
    energies = np.array(
        [
            float(np.sum(np.square(envelope[start : start + length])))
            for start in range(0, len(envelope) - length + 1, length // 2)
        ]
    )
    typical = float(np.median(energies))

    def disagrees(spectrum: np.ndarray, reference: float) -> bool:
        low = int(reference * (1 - LOCAL_SEARCH_RATIO) / bpm_per_bin)
        high = int(reference * (1 + LOCAL_SEARCH_RATIO) / bpm_per_bin)
        local = (low + int(np.argmax(spectrum[low : high + 1]))) * bpm_per_bin
        return abs(local / reference - 1.0) > LOCAL_TEMPO_TOLERANCE

    off = total = 0
    for number, energy in enumerate(energies):
        if energy < 0.2 * typical:
            continue  # A break has no tempo to compare.
        start = number * (length // 2)
        segment = envelope[start : start + length]
        spectrum = np.abs(np.fft.rfft((segment - segment.mean()) * taper, n=fft_size))
        total += 1
        off += disagrees(spectrum, bpm) and disagrees(spectrum, 2 * bpm)
    return off / total if total else 0.0


def _strong_onsets(envelope: np.ndarray, frame_rate: float) -> tuple[np.ndarray, np.ndarray]:
    """Return times and heights of clear envelope peaks, corrected for latency."""
    level = float(np.percentile(envelope, 75))
    peaks, _ = find_peaks(
        envelope,
        height=max(level * 2.0, OnsetConfig.min_strength),
        distance=max(1, int(0.05 * frame_rate)),
    )
    return peaks / frame_rate - ENVELOPE_LATENCY_S, envelope[peaks]


def _beat_phase(times: np.ndarray, heights: np.ndarray, period_s: float) -> float:
    """Return the offset within a beat where the strongest onsets gather."""
    bins = max(8, int(period_s / 0.005))
    index = (np.mod(times, period_s) / period_s * bins).astype(int) % bins
    folded = np.bincount(index, weights=heights, minlength=bins)
    kernel = np.array([0.25, 0.5, 1.0, 0.5, 0.25])
    smoothed = np.convolve(np.tile(folded, 3), kernel, mode="same")[bins : 2 * bins]
    return (int(np.argmax(smoothed)) + 0.5) / bins * period_s


def _regress_grid(
    times: np.ndarray, heights: np.ndarray, period_s: float, phase_s: float
) -> tuple[float, float, np.ndarray, np.ndarray]:
    """Refine period and phase by fitting onsets to the sixteenth-note grid.

    Returns the period, the phase, and for each onset its residual and whether it
    was matched to the grid.
    """
    step = period_s / GRID_DIVISOR
    start = phase_s
    residuals = np.zeros_like(times)
    matched = np.zeros_like(times, dtype=bool)
    for _ in range(_REGRESSION_ROUNDS):
        index = np.round((times - start) / step)
        residuals = times - (start + index * step)
        matched = np.abs(residuals) <= GRID_MATCH_S
        if matched.sum() < 8:
            break
        weights = np.sqrt(heights[matched])
        step, start = np.polyfit(index[matched], times[matched], 1, w=weights)
    index = np.round((times - start) / step)
    residuals = times - (start + index * step)
    matched = np.abs(residuals) <= GRID_MATCH_S
    return float(step * GRID_DIVISOR), float(start), residuals, matched


def _max_window_drift(times: np.ndarray, residuals: np.ndarray, matched: np.ndarray) -> float:
    """Return the largest average distance from the grid over any window of the song."""
    if times.size == 0:
        return 0.0
    drift = 0.0
    start = float(times.min())
    end = float(times.max())
    while start < end:
        inside = (times >= start) & (times < start + DRIFT_WINDOW_S) & matched
        if inside.sum() >= _MIN_WINDOW_ONSETS:
            drift = max(drift, abs(float(residuals[inside].mean())))
        start += DRIFT_WINDOW_S / 2
    return drift


def _refined_segments(
    times: np.ndarray, heights: np.ndarray, period_s: float, phase_s: float, duration_s: float
) -> list[TempoSegment]:
    """Bend a constant grid through the onsets, one short constant tempo per section.

    The grid is continuous by construction, so the map only gains small tempo changes
    that follow what the band actually played.
    """
    count = int((duration_s - phase_s) / period_s) + REFINE_WINDOW_BEATS
    edges = np.arange(0, count + REFINE_WINDOW_BEATS, REFINE_WINDOW_BEATS, dtype=np.float64)
    offsets = np.zeros_like(edges)
    centers = edges[:-1] + REFINE_WINDOW_BEATS / 2

    for _ in range(_REFINE_ROUNDS):
        grid = phase_s + edges * period_s + offsets
        position = np.round(np.interp(times, grid, edges) * GRID_DIVISOR) / GRID_DIVISOR
        residuals = times - np.interp(position, edges, grid)
        matched = np.abs(residuals) <= GRID_MATCH_S

        corrections = np.full_like(centers, np.nan)
        for number, first in enumerate(edges[:-1]):
            inside = matched & (position >= first) & (position < first + REFINE_WINDOW_BEATS)
            if inside.sum() >= _MIN_WINDOW_ONSETS:
                corrections[number] = np.average(residuals[inside], weights=heights[inside])
        known = np.isfinite(corrections)
        if not known.any():
            break
        offsets = offsets + np.interp(edges, centers[known], corrections[known])

    grid = phase_s + edges * period_s + offsets
    return [
        TempoSegment(
            int(edges[number]),
            int(edges[number + 1]),
            float(grid[number]),
            float((grid[number + 1] - grid[number]) / REFINE_WINDOW_BEATS),
        )
        for number in range(len(edges) - 1)
    ]


def fit_segments(beats: np.ndarray, tolerance_s: float = FIT_TOLERANCE_S) -> list[TempoSegment]:
    """Greedily cover ``beats`` with the longest constant-tempo segments within tolerance."""
    segments: list[TempoSegment] = []
    first = 0
    anchor: float | None = None
    last_index = len(beats) - 1
    while first < last_index:
        last = min(first + MIN_SEGMENT_BEATS - 1, last_index)
        start, period, _ = _fit_line(beats[first : last + 1], anchor)
        candidate = last + 1
        while candidate <= last_index:
            fitted = _fit_line(beats[first : candidate + 1], anchor)
            if fitted[2] > tolerance_s:
                break
            start, period, _ = fitted
            last = candidate
            candidate += 1
        segments.append(TempoSegment(first, last, start, period))
        anchor = start + period * (last - first)
        first = last
    return segments


def _fit_line(beats: np.ndarray, anchor: float | None) -> tuple[float, float, float]:
    """Fit evenly spaced beats; return (start, period, largest absolute residual).

    With ``anchor``, the line must start there, which keeps neighbouring segments
    continuous.
    """
    index = np.arange(len(beats), dtype=np.float64)
    if anchor is None:
        period, start = np.polyfit(index, beats, 1)
    else:
        start = anchor
        period = float(np.dot(index, beats - anchor) / np.dot(index, index))
    residual = beats - (start + period * index)
    return float(start), float(period), float(np.abs(residual).max())


def tempo_map_from_segments(
    segments: list[TempoSegment], resolution: int = DEFAULT_RESOLUTION
) -> TempoMap:
    """Build a map whose beats land exactly on quarter-note ticks.

    Tick 0 is always audio time 0, which rarely coincides with a beat. The first
    quarter note therefore stretches from the start of the audio to the first grid
    beat at least half a period in, so the rest of the grid stays aligned.
    """
    head = segments[0]
    steps = math.ceil((0.5 * head.period_s - head.start_s) / head.period_s)
    first_grid_time = head.start_s + steps * head.period_s

    lead_in_bpm = 60.0 / first_grid_time
    head_bpm = 60.0 / head.period_s
    tempos: list[TempoEvent] = [TempoEvent(0, lead_in_bpm)]
    if abs(lead_in_bpm - head_bpm) < MERGE_BPM_DIFFERENCE:
        tempos = [TempoEvent(0, head_bpm)]
    else:
        tempos.append(TempoEvent(resolution, head_bpm))

    for segment in segments[1:]:
        bpm = 60.0 / segment.period_s
        if abs(bpm - tempos[-1].bpm) >= MERGE_BPM_DIFFERENCE:
            # Beat i of the fitted sequence sits (i - steps + 1) quarter notes in.
            tick = (segment.first_beat - steps + 1) * resolution
            tempos.append(TempoEvent(tick, bpm))
    return TempoMap(tempos, [TimeSignatureEvent(0, 4, 4)], resolution)


def fit_tempo_map(beats: np.ndarray, resolution: int = DEFAULT_RESOLUTION) -> tuple[TempoMap, int]:
    """Return the tempo map for ``beats`` and its number of constant-tempo segments."""
    segments = fit_segments(beats)
    return tempo_map_from_segments(segments, resolution), len(segments)


def _grid_statistics(tempo_map: TempoMap, times: np.ndarray) -> tuple[float, float]:
    """Return the on-grid share and the 95th percentile grid error of the given onsets."""
    usable = times[times >= 0]
    if usable.size == 0:
        return 0.0, float("nan")
    step = tempo_map.resolution / GRID_DIVISOR
    grid = np.round(tempo_map.ticks_at(usable) / step) * step
    errors = np.abs(tempo_map.seconds_at(grid) - usable)
    return float(np.mean(errors <= GRID_MATCH_S)), float(np.percentile(errors, 95) * 1000.0)


def _fallback(strength: float) -> TempoAnalysis:
    log.warning("No clear pulse in the audio, falling back to %.0f BPM", FALLBACK_BPM)
    tempo_map = TempoMap([TempoEvent(0, FALLBACK_BPM)], [TimeSignatureEvent(0, 4, 4)])
    return TempoAnalysis(tempo_map, FALLBACK_BPM, "fallback", 1, 0.0, float("nan"), strength)


def estimate_tempo_map(mono: np.ndarray, samplerate: int = ANALYSIS_SAMPLERATE) -> TempoAnalysis:
    """Estimate the song's tempo map from its mix.

    Time signature detection is not implemented yet: 4/4 is assumed, which affects
    only the bar lines drawn on the highway, not note timing.
    """
    if mono.size < MIN_ANALYSIS_SECONDS * samplerate:
        return _fallback(0.0)
    envelope = onset_envelope(mono, samplerate)
    frame_rate = samplerate / HOP_LENGTH

    base_bpm, strength = select_tempo(envelope, frame_rate)
    times, heights = _strong_onsets(envelope, frame_rate)
    if strength < MIN_TEMPO_STRENGTH or times.size < 8:
        return _fallback(strength)

    keep = times >= 0
    times, heights = times[keep], heights[keep]
    duration_s = len(mono) / samplerate

    off_share = off_tempo_share(envelope, frame_rate, base_bpm)
    log.debug("whole-song %.2f BPM, %.0f%% of windows off tempo", base_bpm, off_share * 100)
    if off_share > MAX_OFF_TEMPO_SHARE:
        _, beats = librosa.beat.beat_track(
            onset_envelope=envelope,
            sr=samplerate,
            hop_length=HOP_LENGTH,
            units="time",
            bpm=local_tempo_curve(envelope, frame_rate, base_bpm),
            tightness=_TRACKER_TIGHTNESS,
        )
        beats = np.asarray(beats, dtype=np.float64) - ENVELOPE_LATENCY_S
        beats = beats[beats >= 0]
        if len(beats) < MIN_SEGMENT_BEATS:
            return _fallback(strength)
        segments = fit_segments(beats)
        method = "variable"
        bpm = float(60.0 / np.median(np.diff(beats)))
    else:
        period = 60.0 / base_bpm
        phase = _beat_phase(times, heights, period)
        period, phase, residuals, matched = _regress_grid(times, heights, period, phase)
        phase = float(np.mod(phase, period))
        drift = _max_window_drift(times, residuals, matched)
        log.debug("regressed %.3f BPM, window drift %.1f ms", 60.0 / period, drift * 1000.0)
        bpm = 60.0 / period
        if drift <= MAX_DRIFT_S:
            last_beat = max(1, int((duration_s - phase) / period))
            segments = [TempoSegment(0, last_beat, phase, period)]
            method = "constant"
        else:
            segments = _refined_segments(times, heights, period, phase, duration_s)
            method = "refined"

    tempo_map = tempo_map_from_segments(segments)
    on_grid, error_p95 = _grid_statistics(tempo_map, times)
    return TempoAnalysis(tempo_map, bpm, method, len(segments), on_grid, error_p95, strength)
