"""Tempo map extraction. Runs once, on the original mix; every instrument shares the result.

``librosa.beat.beat_track`` left to itself reads the wrong metrical level on real
songs (129 instead of 97 BPM). Told the right tempo, it is excellent: against the beats
a human placed in a Harmonix chart, its measure of how far a song strays from one tempo
was a median 6 ms off. So the two problems are solved separately:

1. The Fourier transform of the whole onset envelope gives the tempo, with harmonic
   support picking the metrical level.
2. A tracker guided by that tempo finds the beats. If local tempo really differs across
   the song, it follows a tempo curve instead of a single value.
3. The song starts with one tempo. Wherever the beats of a region stray further from the
   grid than ``max_beat_drift_s``, a tempo event is added there. Each event must also
   bring the song's onsets measurably closer to the grid, or it is merged away again: in
   a sparse intro the tracker can lock onto an off-beat pattern, and no event should be
   spent following that.
4. ``chartgen.audio.meter`` decides how the beats group into bars and where they begin.

``--bpm`` replaces steps 1-3 for the tempo (method ``override``), not for phase or bars.
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
from chartgen.audio.meter import MeterResult, detect_meter
from chartgen.audio.onsets import ENVELOPE_LATENCY_S, HOP_LENGTH, onset_envelope
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

TRACKER_TIGHTNESS = 400
"""Measured on one human-mapped song: 100 to 3000 all land within 7-8 ms median; 400 had
the fewest outliers."""
LOCAL_WINDOW_S = 30.0
LOCAL_SEARCH_RATIO = 0.12
LOCAL_TEMPO_TOLERANCE = 0.015
MAX_OFF_TEMPO_SHARE = 0.15
"""More windows than this away from the main tempo mean the tempo really changes.
A few are normal: intros and breaks often have no clear pulse."""
CURVE_WINDOW_S = 16.0
CURVE_RANGE = (0.6, 1.6)
"""Tempo changes further than this from the main tempo are not followed."""

DEFAULT_MAX_BEAT_DRIFT_S = 0.025
"""A region's beats may stray this far from the grid before it gets a tempo event."""
REGION_BEATS = 16
_REGION_HOP_BEATS = 8
_MIN_REGION_BEATS = 8
"""A region is averaged over this many beats, so a single late hit is not a drift."""
MIN_EVENT_GAIN_S = 0.001
"""An event must bring the onsets around it at least this much closer to the grid."""
MAX_TOTAL_FIT_LOSS = 0.02
"""Events that help locally must not cost the song as a whole more than this, counting the
share of onsets on the grid and the share of beats with an onset together. Either alone can
mislead: an abrupt tempo change costs the sixteenth grid a few notes at the change itself,
while putting half the song's beats back on real onsets."""
MIN_BEAT_SUPPORT_GAIN = 0.05
"""Or the events must put an onset under this many more of the song's beats. The sixteenth
grid can already fit a passage at another tempo while its beats are all wrong."""
_POLISH_BEATS = 4
_MOVED_S = 0.005
_MIN_KNOT_SPACING_BEATS = 8
_MAX_KNOTS = 256
_SINGLE_KNOT_PATTERNS = tuple((offset,) for offset in sorted(range(-8, 9), key=abs))
_KNOT_PAIR_PATTERNS = ((-8, 8), (-16, 8), (-8, 16), (-16, 16))
"""Breaks to try around a region's center, in beats. Pairs only if no single break will do."""
_MIN_DRIFT_IMPROVEMENT_S = 0.002
_MAIN_TEMPO_RANGE = 0.03
_FIT_ROUNDS = 3
MIN_BEATS = 16
MERGE_BPM_DIFFERENCE = 0.05

STRONG_ONSET_MIN_STRENGTH = 2.0
"""What counts as a clear onset for judging a grid. Deliberately separate from the note
detector's floor: lowering that one to catch quiet notes must not change the tempo map."""
GRID_DIVISOR = 4
GRID_MATCH_S = 0.035
"""Onsets this close to a sixteenth note count as being on the grid."""


@dataclass(frozen=True)
class TempoSegment:
    first_beat: int
    last_beat: int
    start_s: float
    period_s: float


@dataclass(frozen=True)
class DriftStats:
    """How well a grid fits the song."""

    max_ms: float
    """The worst region's average distance between beats and grid."""
    median_ms: float
    """The typical region's average distance between beats and grid."""
    on_grid: float
    """Share of strong onsets within :data:`GRID_MATCH_S` of a sixteenth note."""
    beats_with_onset: float = 0.0
    """Share of the grid's beats that have a strong onset within :data:`GRID_MATCH_S`. The
    sixteenth grid alone can be fooled: at 150 BPM it also fits every click played at 120."""

    @property
    def fit(self) -> float:
        return self.on_grid + self.beats_with_onset


@dataclass(frozen=True)
class TempoEventDetail:
    """Why one tempo event exists."""

    time_s: float
    gain_ms: float
    """How much closer this event brings the onsets around it to the grid."""
    drift_without_ms: float
    """The worst drift around it if this event were merged away."""


@dataclass(frozen=True)
class TempoAnalysis:
    tempo_map: TempoMap
    bpm: float
    """The main tempo: the single tempo, or the average one of a variable song."""
    method: str
    """``constant``, ``variable``, ``override`` or ``fallback``."""
    decision: str
    """Why this method was chosen, in words."""
    tempo_strength: float
    max_beat_drift_ms: float = DEFAULT_MAX_BEAT_DRIFT_S * 1000.0
    final: DriftStats | None = None
    """The fit of the map that was chosen."""
    one_tempo: DriftStats | None = None
    """The fit one tempo would have, for comparison."""
    event_details: tuple[TempoEventDetail, ...] = ()
    off_tempo_share: float = 0.0
    """Share of 30 second windows whose local tempo differs from the main tempo."""
    meter: MeterResult | None = None
    estimated_bpm: float | None = None
    """The whole-song estimate, also reported when ``--bpm`` overrides it."""

    @property
    def is_fallback(self) -> bool:
        return self.method == "fallback"

    @property
    def on_grid_ratio(self) -> float:
        return self.final.on_grid if self.final else 0.0

    @property
    def first_downbeat_s(self) -> float | None:
        return self.meter.first_downbeat_s if self.meter else None

    @property
    def bar_confidence(self) -> float:
        return self.meter.confidence if self.meter else 0.0

    def event_explanations(self) -> list[dict[str, object]]:
        """Explain each tempo event, in the order of ``tempo_map.tempos``."""
        tempos = self.tempo_map.tempos
        has_lead_in = len(tempos) > 1 and tempos[1].tick == self.tempo_map.resolution
        general = {
            "constant": "main tempo",
            "override": "tempo given with --bpm",
            "variable": "tempo up to the first event",
            "fallback": "default tempo: the audio has no clear pulse",
        }[self.method]
        explanations: list[dict[str, object]] = []
        for index, event in enumerate(tempos):
            time = self.tempo_map.seconds_at(float(event.tick))
            detail = next(
                (item for item in self.event_details if abs(item.time_s - time) < 0.002), None
            )
            if detail is not None:
                explanations.append(
                    {
                        "reason": (
                            f"beats stray {detail.drift_without_ms:.0f} ms from the grid here "
                            f"without this event (limit {self.max_beat_drift_ms:.0f} ms)"
                        ),
                        "gain_ms": round(detail.gain_ms, 2),
                        "drift_without_ms": round(detail.drift_without_ms, 1),
                    }
                )
            elif index == 0 and has_lead_in:
                explanations.append(
                    {"reason": "lead-in: fits the start of the audio to the first grid beat"}
                )
            else:
                explanations.append({"reason": general})
        return explanations


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


def _track_beats(envelope: np.ndarray, samplerate: int, tempo: float | np.ndarray) -> np.ndarray:
    """Return beat times from a tracker told what tempo to expect."""
    _, beats = librosa.beat.beat_track(
        onset_envelope=envelope,
        sr=samplerate,
        hop_length=HOP_LENGTH,
        units="time",
        bpm=tempo,
        tightness=TRACKER_TIGHTNESS,
        trim=False,
    )
    beats = np.asarray(beats, dtype=np.float64) - ENVELOPE_LATENCY_S
    return beats[beats >= 0]


def _strong_onsets(envelope: np.ndarray, frame_rate: float) -> tuple[np.ndarray, np.ndarray]:
    """Return the times and heights of clear envelope peaks, corrected for latency."""
    level = float(np.percentile(envelope, 75))
    peaks, _ = find_peaks(
        envelope,
        height=max(level * 2.0, STRONG_ONSET_MIN_STRENGTH),
        distance=max(1, int(0.05 * frame_rate)),
    )
    times = peaks / frame_rate - ENVELOPE_LATENCY_S
    keep = times >= 0
    return times[keep], envelope[peaks][keep]


def _beats_with_evidence(beats: np.ndarray, envelope: np.ndarray, frame_rate: float) -> np.ndarray:
    """Mark the beats that coincide with an actual onset. In a sparse intro, the tracker
    keeps placing beats with nothing to go on, and those say nothing about the tempo."""
    frames = np.round((beats + ENVELOPE_LATENCY_S) * frame_rate).astype(int)
    strength = np.array([envelope[max(0, f - 2) : f + 3].max(initial=0.0) for f in frames])
    return strength >= max(STRONG_ONSET_MIN_STRENGTH, 0.5 * float(np.median(strength)))


@dataclass(frozen=True)
class BeatGrid:
    """A continuous, piecewise-straight map from beat numbers to times. Each breakpoint
    between the first and last is a tempo change."""

    numbers: np.ndarray
    times: np.ndarray

    def time_of(self, numbers: np.ndarray) -> np.ndarray:
        return np.interp(numbers, self.numbers, self.times)

    def number_at(self, times: np.ndarray) -> np.ndarray:
        return np.interp(times, self.times, self.numbers)

    @property
    def is_increasing(self) -> bool:
        return bool(np.all(np.diff(self.times) > 0))


@dataclass(frozen=True)
class _Evidence:
    """What a grid is fitted to and judged by."""

    beats: np.ndarray
    numbers: np.ndarray
    onsets: np.ndarray
    onset_weights: np.ndarray
    first_number: int
    last_number: int
    is_sequential: bool = True
    """Whether beats are numbered along the track, not by their nearest grid line."""


def _fit_grid(evidence: _Evidence, knots: list[int]) -> BeatGrid:
    """Fit a grid with breaks at ``knots`` to the beats and to the onsets near the grid.

    The beats carry the grid across large drifts, and the onsets refine it beyond the
    tracker's frame size. The first round always uses the beats alone: onsets matched to
    a grid that is still off land on the wrong sixteenth, and hold the grid there.
    """
    breakpoints = np.array(
        [evidence.first_number, *sorted(knots), evidence.last_number], dtype=np.float64
    )

    def design(numbers: np.ndarray) -> np.ndarray:
        columns = [np.ones_like(numbers), numbers]
        columns.extend(np.maximum(0.0, numbers - knot) for knot in sorted(knots))
        return np.stack(columns, axis=1)

    grid: BeatGrid | None = None
    for _ in range(_FIT_ROUNDS):
        numbers, times, weights = evidence.numbers, evidence.beats, np.ones_like(evidence.beats)
        if grid is not None and evidence.onsets.size:
            position = np.round(grid.number_at(evidence.onsets) * GRID_DIVISOR) / GRID_DIVISOR
            near = np.abs(evidence.onsets - grid.time_of(position)) <= GRID_MATCH_S
            numbers = np.r_[numbers, position[near]]
            times = np.r_[times, evidence.onsets[near]]
            weights = np.r_[weights, evidence.onset_weights[near]]
        matrix = design(numbers)
        coefficients, *_ = np.linalg.lstsq(matrix * weights[:, None], times * weights, rcond=None)
        grid = BeatGrid(breakpoints, design(breakpoints) @ coefficients)
    assert grid is not None
    return grid


def _region_drifts(grid: BeatGrid, evidence: _Evidence) -> tuple[np.ndarray, np.ndarray]:
    """Return each region's center and how far its beats sit from the grid.

    This is the average distance, unless the beats are typically further away than that.
    Under one tempo, beats are numbered by their nearest grid line, and in a passage at
    another tempo their distances sweep from one side to the other and average to nothing.
    """
    residuals = evidence.beats - grid.time_of(evidence.numbers)
    centers: list[float] = []
    drifts: list[float] = []
    for first in range(evidence.first_number, evidence.last_number, _REGION_HOP_BEATS):
        inside = (evidence.numbers >= first) & (evidence.numbers < first + REGION_BEATS)
        if inside.sum() >= _MIN_REGION_BEATS:
            mean = float(residuals[inside].mean())
            typical = float(np.median(np.abs(residuals[inside])))
            centers.append(first + REGION_BEATS / 2)
            drifts.append(mean if evidence.is_sequential else math.copysign(max(abs(mean), typical), mean))
    return np.array(centers), np.array(drifts)


def _onset_errors(grid: BeatGrid, onsets: np.ndarray) -> np.ndarray:
    """Return each onset's distance from its nearest sixteenth note, capped at the on-grid
    limit: an onset that belongs to no grid position must not dominate the average."""
    position = np.round(grid.number_at(onsets) * GRID_DIVISOR) / GRID_DIVISOR
    return np.minimum(np.abs(onsets - grid.time_of(position)), GRID_MATCH_S)


def _stats(grid: BeatGrid, evidence: _Evidence) -> DriftStats:
    _, drifts = _region_drifts(grid, evidence)
    magnitudes = np.abs(drifts) if drifts.size else np.zeros(1)
    position = np.round(grid.number_at(evidence.onsets) * GRID_DIVISOR) / GRID_DIVISOR
    errors = np.abs(evidence.onsets - grid.time_of(position))
    on_grid = float(np.mean(errors <= GRID_MATCH_S)) if errors.size else 0.0
    supported = 0.0
    if evidence.onsets.size:
        first = math.ceil(float(grid.number_at(evidence.onsets[:1])[0]))
        last = math.floor(float(grid.number_at(evidence.onsets[-1:])[0]))
        if last > first:
            lines = grid.time_of(np.arange(first, last + 1, dtype=np.float64))
            nearest = np.searchsorted(evidence.onsets, lines)
            before = evidence.onsets[np.clip(nearest - 1, 0, evidence.onsets.size - 1)]
            after = evidence.onsets[np.clip(nearest, 0, evidence.onsets.size - 1)]
            distance = np.minimum(np.abs(lines - before), np.abs(lines - after))
            supported = float(np.mean(distance <= GRID_MATCH_S))
    return DriftStats(
        float(magnitudes.max() * 1000.0),
        float(np.median(magnitudes) * 1000.0),
        on_grid,
        supported,
    )


def _event_gain(with_event: BeatGrid, without_event: BeatGrid, onsets: np.ndarray) -> float:
    """Return how much closer an event brings the onsets it actually moves the grid for.

    Averaging over everything between neighbouring events would dilute a real local
    improvement until the event looked useless.
    """
    numbers = with_event.number_at(onsets)
    moved = np.abs(with_event.time_of(numbers) - without_event.time_of(numbers)) >= _MOVED_S
    if not moved.any():
        return 0.0
    return float(
        _onset_errors(without_event, onsets[moved]).mean()
        - _onset_errors(with_event, onsets[moved]).mean()
    )


def _event_gain_between(single: BeatGrid, grid: BeatGrid, onsets: np.ndarray) -> float:
    """Return how much closer ``grid`` brings the onsets it places differently from one tempo.

    Events can look useful against a straight line fitted through a tracker's mistake. What
    counts is whether they beat the one-tempo grid they would replace.
    """

    def residuals(candidate: BeatGrid) -> np.ndarray:
        position = np.round(candidate.number_at(onsets) * GRID_DIVISOR) / GRID_DIVISOR
        return onsets - candidate.time_of(position)

    one, chosen = residuals(single), residuals(grid)
    moved = np.abs(one - chosen) >= _MOVED_S
    if not moved.any():
        return 0.0
    capped_one = np.minimum(np.abs(one[moved]), GRID_MATCH_S)
    capped_chosen = np.minimum(np.abs(chosen[moved]), GRID_MATCH_S)
    return float(capped_one.mean() - capped_chosen.mean())


def _add_knots(evidence: _Evidence, limit_s: float) -> tuple[BeatGrid, list[int]]:
    """Break the grid at the worst region until every region is within ``limit_s``.

    One break turns a drift into a corner, which suits a slow wander. A short bump that
    returns to the old line needs a break on either side, so those are tried too, and the
    fewest breaks that solve the region win.
    """
    knots: list[int] = []
    grid = _fit_grid(evidence, knots)
    given_up: set[float] = set()

    while len(knots) < _MAX_KNOTS:
        centers, drifts = _region_drifts(grid, evidence)
        worst_index = None
        for index in np.argsort(-np.abs(drifts)):
            if abs(drifts[index]) <= limit_s:
                break
            if float(centers[index]) not in given_up:
                worst_index = int(index)
                break
        if worst_index is None:
            break
        center = float(centers[worst_index])
        worst = abs(float(drifts[worst_index]))

        best: tuple[float, list[int], BeatGrid, float] | None = None
        for patterns in (_SINGLE_KNOT_PATTERNS, _KNOT_PAIR_PATTERNS):
            for offsets in patterns:
                added = [int(center) + offset for offset in offsets]
                acceptable = all(
                    evidence.first_number < knot < evidence.last_number
                    and all(abs(knot - other) >= _MIN_KNOT_SPACING_BEATS for other in knots)
                    for knot in added
                )
                if not acceptable:
                    continue
                trial = _fit_grid(evidence, [*knots, *added])
                if not trial.is_increasing:
                    continue
                new_centers, new_drifts = _region_drifts(trial, evidence)
                here = np.abs(new_drifts[new_centers == center])
                remaining = float(here[0]) if here.size else 0.0
                if remaining > worst - _MIN_DRIFT_IMPROVEMENT_S:
                    continue
                # Judged on the whole song: the best place for a break is where the tempo
                # really changes, which may lie outside the region that showed the drift.
                misfit = float(np.sum(np.square(evidence.beats - trial.time_of(evidence.numbers))))
                if best is None or misfit < best[0]:
                    best = (misfit, added, trial, remaining)
            if best is not None and best[3] <= limit_s:
                break

        if best is None:
            given_up.add(center)
            continue
        knots.extend(best[1])
        grid = best[2]
    return grid, sorted(knots)


def _event_details(
    evidence: _Evidence, grid: BeatGrid, knots: list[int]
) -> tuple[list[TempoEventDetail], list[float]]:
    """Work out what each knot contributes, by refitting the grid without it."""
    details: list[TempoEventDetail] = []
    gains: list[float] = []
    for position, knot in enumerate(knots):
        others = knots[:position] + knots[position + 1 :]
        without = _fit_grid(evidence, others)
        low = knots[position - 1] if position > 0 else evidence.first_number
        high = knots[position + 1] if position + 1 < len(knots) else evidence.last_number
        gain = _event_gain(grid, without, evidence.onsets)
        gains.append(gain)
        centers, drifts = _region_drifts(without, evidence)
        around = (centers >= low) & (centers <= high)
        worst = float(np.abs(drifts[around]).max()) if around.any() else 0.0
        time = float(grid.time_of(np.array([float(knot)]))[0])
        details.append(TempoEventDetail(time, gain * 1000.0, worst * 1000.0))
    return details, gains


def _polish_knots(
    evidence: _Evidence, grid: BeatGrid, knots: list[int]
) -> tuple[BeatGrid, list[int]]:
    """Slide each knot a few beats to where the grid fits the beats best. Knots start at
    region centers, but an abrupt tempo change happens wherever it happens."""
    knots = list(knots)

    def misfit(candidate: BeatGrid) -> float:
        return float(np.sum(np.square(evidence.beats - candidate.time_of(evidence.numbers))))

    for position in range(len(knots)):
        best_error = misfit(grid)
        for shift in range(-_POLISH_BEATS, _POLISH_BEATS + 1):
            moved = knots[position] + shift
            neighbours = knots[:position] + knots[position + 1 :]
            if shift == 0 or not evidence.first_number < moved < evidence.last_number:
                continue
            if any(abs(moved - other) < _MIN_KNOT_SPACING_BEATS for other in neighbours):
                continue
            trial = _fit_grid(evidence, [*neighbours, moved])
            error = misfit(trial)
            if trial.is_increasing and error < best_error:
                best_error = error
                best_knots = sorted([*neighbours, moved])
                best_grid = trial
        if best_error < misfit(grid):
            knots = best_knots
            grid = best_grid
    return grid, knots


def _merge_useless_knots(
    evidence: _Evidence, grid: BeatGrid, knots: list[int]
) -> tuple[BeatGrid, list[int], list[TempoEventDetail]]:
    """Remove every knot that does not bring the onsets around it closer to the grid."""
    while True:
        details, gains = _event_details(evidence, grid, knots)
        weakest = [i for i, gain in enumerate(gains) if gain < MIN_EVENT_GAIN_S]
        if not weakest:
            return grid, knots, details
        # Removing one knot changes its neighbours' gains, so never remove two adjacent ones.
        doomed: set[int] = set()
        for index in sorted(weakest, key=lambda i: gains[i]):
            if index - 1 not in doomed and index + 1 not in doomed:
                doomed.add(index)
        knots = [knot for i, knot in enumerate(knots) if i not in doomed]
        grid = _fit_grid(evidence, knots)


def _segments_from_grid(grid: BeatGrid) -> list[TempoSegment]:
    first = int(grid.numbers[0])
    return [
        TempoSegment(
            int(grid.numbers[i]) - first,
            int(grid.numbers[i + 1]) - first,
            float(grid.times[i]),
            float((grid.times[i + 1] - grid.times[i]) / (grid.numbers[i + 1] - grid.numbers[i])),
        )
        for i in range(len(grid.numbers) - 1)
    ]


def _main_bpm(segments: list[TempoSegment]) -> float:
    """Return the song's average tempo, leaving out sections far from its typical tempo,
    such as a free intro."""
    periods = np.array([segment.period_s for segment in segments])
    lengths = np.array([segment.last_beat - segment.first_beat for segment in segments], float)
    order = np.argsort(periods)
    middle = np.searchsorted(np.cumsum(lengths[order]), lengths.sum() / 2)
    typical = periods[order[min(middle, len(order) - 1)]]
    close = np.abs(periods / typical - 1.0) <= _MAIN_TEMPO_RANGE
    return 60.0 / float(np.average(periods[close], weights=lengths[close]))


def _fit_one_tempo(
    beats: np.ndarray, onsets: np.ndarray, heights: np.ndarray, bpm: float
) -> tuple[float, float]:
    """Return (start, period) of the best single tempo.

    Beats are compared modulo the period because a tracker can add or drop a beat in a
    sparse passage: numbering them in sequence would turn that into a whole beat of drift
    for the rest of the song. Every onset on the sixteenth grid around them then refines
    period and phase, far beyond the tracker's frame size.
    """
    period = 60.0 / bpm
    start = _beat_phase(beats, period)
    step = period / GRID_DIVISOR
    for _ in range(4):
        index = np.round((onsets - start) / step)
        matched = np.abs(onsets - (start + index * step)) <= GRID_MATCH_S
        if matched.sum() < _MIN_REGION_BEATS:
            break
        step, start = np.polyfit(index[matched], onsets[matched], 1, w=np.sqrt(heights[matched]))
    return float(start), float(step * GRID_DIVISOR)


def _beat_phase(beats: np.ndarray, period_s: float) -> float:
    """Return where within a beat the given beats gather."""
    pointer = np.mean(np.exp(2j * np.pi * beats / period_s))
    return float(np.angle(pointer) * period_s / (2 * np.pi))


def _sequential_numbers(beats: np.ndarray, period_s: float) -> np.ndarray:
    """Number beats along the track, so that a skipped beat keeps its place."""
    steps = np.maximum(1, np.round(np.diff(beats) / period_s))
    return np.r_[0.0, np.cumsum(steps)]


def _one_tempo_evidence(
    beats: np.ndarray, onsets: np.ndarray, weights: np.ndarray, start: float, period: float
) -> tuple[BeatGrid, _Evidence]:
    """Express one tempo as a grid, numbering each beat by the grid line nearest to it."""
    numbers = np.round((beats - start) / period)
    low = int(numbers.min()) - 1
    high = int(numbers.max()) + 1
    grid = BeatGrid(
        np.array([low, high], dtype=np.float64),
        np.array([start + low * period, start + high * period]),
    )
    return grid, _Evidence(beats, numbers, onsets, weights, low, high, is_sequential=False)


@dataclass(frozen=True)
class GridChoice:
    """The tempo decision for one song."""

    segments: list[TempoSegment]
    bpm: float
    method: str
    decision: str
    final: DriftStats
    one_tempo: DriftStats
    details: tuple[TempoEventDetail, ...] = ()


def choose_grid(
    beats: np.ndarray,
    onsets: np.ndarray,
    heights: np.ndarray,
    bpm: float,
    duration_s: float,
    max_beat_drift_s: float = DEFAULT_MAX_BEAT_DRIFT_S,
) -> GridChoice:
    """Decide between one tempo and a grid with events.

    Args:
        beats: Tracked beats that coincide with an onset.
        onsets: Strong onsets of the song.
        heights: Their strengths.
        bpm: The whole-song tempo.
        duration_s: Length of the song.
        max_beat_drift_s: How far a region's beats may stray before it gets an event.
    """
    weights = np.sqrt(heights) / max(float(np.mean(np.sqrt(heights))), 1e-9)
    start, period = _fit_one_tempo(beats, onsets, heights, bpm)
    single_grid, single_evidence = _one_tempo_evidence(beats, onsets, weights, start, period)
    single_stats = _stats(single_grid, single_evidence)
    phase = float(np.mod(start, period))
    single_segments = [TempoSegment(0, max(1, int((duration_s - phase) / period)), phase, period)]
    limit_ms = max_beat_drift_s * 1000.0

    def one_tempo(decision: str) -> GridChoice:
        return GridChoice(
            single_segments, 60.0 / period, "constant", decision, single_stats, single_stats
        )

    if single_stats.max_ms <= limit_ms:
        return one_tempo(
            f"beats stay within {single_stats.max_ms:.0f} ms of one tempo in every region "
            f"(limit {limit_ms:.0f} ms)"
        )

    numbers = _sequential_numbers(beats, period)
    evidence = _Evidence(beats, numbers, onsets, weights, int(numbers.min()), int(numbers.max()))
    grid, knots = _add_knots(evidence, max_beat_drift_s)
    grid, knots, details = _merge_useless_knots(evidence, grid, knots)
    grid, knots = _polish_knots(evidence, grid, knots)
    # Moving knots changes what each one contributes, so judge them once more.
    grid, knots, details = _merge_useless_knots(evidence, grid, knots)
    final_stats = _stats(grid, evidence)
    harmful = final_stats.fit < single_stats.fit - MAX_TOTAL_FIT_LOSS
    helpful = (
        _event_gain_between(single_grid, grid, onsets) >= MIN_EVENT_GAIN_S
        or final_stats.beats_with_onset >= single_stats.beats_with_onset + MIN_BEAT_SUPPORT_GAIN
    )
    if not knots or harmful or not helpful or not grid.is_increasing:
        return one_tempo(
            f"beats stray {single_stats.max_ms:.0f} ms from one tempo (limit {limit_ms:.0f} ms), "
            f"but tempo events would not bring the onsets closer to the grid "
            f"(with one tempo {single_stats.on_grid:.0%} of onsets are on the grid and "
            f"{single_stats.beats_with_onset:.0%} of beats have an onset; with {len(knots)} "
            f"events {final_stats.on_grid:.0%} and {final_stats.beats_with_onset:.0%})"
        )

    _, final_drifts = _region_drifts(grid, evidence)
    over_limit = int(np.sum(np.abs(final_drifts) > max_beat_drift_s))
    decision = (
        f"beats stray {single_stats.max_ms:.0f} ms from one tempo (limit {limit_ms:.0f} ms): "
        f"{len(knots)} events bring the worst region to {final_stats.max_ms:.0f} ms and onsets "
        f"on the grid from {single_stats.on_grid:.0%} to {final_stats.on_grid:.0%}"
    )
    if over_limit:
        decision += (
            f"; {over_limit} of {final_drifts.size} regions stay over the limit because events "
            f"there would not bring the onsets closer"
        )
    segments = _segments_from_grid(grid)
    return GridChoice(
        segments,
        _main_bpm(segments),
        "variable",
        decision,
        final_stats,
        single_stats,
        tuple(details),
    )


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
        # Beat i of the fitted sequence sits (i - steps + 1) quarter notes in.
        tick = (segment.first_beat - steps + 1) * resolution
        if tick > tempos[-1].tick and abs(bpm - tempos[-1].bpm) >= MERGE_BPM_DIFFERENCE:
            tempos.append(TempoEvent(tick, bpm))
    return TempoMap(tempos, [TimeSignatureEvent(0, 4, 4)], resolution)


def fit_tempo_map(
    beats: np.ndarray,
    max_beat_drift_s: float = DEFAULT_MAX_BEAT_DRIFT_S,
    resolution: int = DEFAULT_RESOLUTION,
) -> tuple[TempoMap, GridChoice]:
    """Build a tempo map from beats alone, treating them as the song's onsets too."""
    bpm = 60.0 / float(np.median(np.diff(beats)))
    duration = float(beats[-1]) + 1.0
    choice = choose_grid(beats, beats, np.ones_like(beats), bpm, duration, max_beat_drift_s)
    return tempo_map_from_segments(choice.segments, resolution), choice


def _override_grid(
    bpm: float,
    envelope: np.ndarray,
    samplerate: int,
    frame_rate: float,
    onsets: np.ndarray,
    heights: np.ndarray,
    duration_s: float,
    estimated: float,
) -> GridChoice:
    """Keep the given tempo exactly and only look for the phase."""
    period = 60.0 / bpm
    beats = _track_beats(envelope, samplerate, bpm)
    if beats.size < _MIN_REGION_BEATS:
        stats = DriftStats(0.0, 0.0, 0.0)
        phase = 0.0
    else:
        kept = beats[_beats_with_evidence(beats, envelope, frame_rate)]
        kept = kept if kept.size >= _MIN_REGION_BEATS else beats
        phase = _beat_phase(kept, period)
        weights = np.sqrt(heights) / max(float(np.mean(np.sqrt(heights))), 1e-9) if heights.size else heights
        grid, evidence = _one_tempo_evidence(kept, onsets, weights, phase, period)
        stats = _stats(grid, evidence)
        phase = float(np.mod(phase, period))
    return GridChoice(
        [TempoSegment(0, max(1, int((duration_s - phase) / period)), phase, period)],
        bpm,
        "override",
        f"--bpm {bpm:g} given on the command line (whole-song estimate: {estimated:.2f})",
        stats,
        stats,
    )


def _fallback(strength: float) -> TempoAnalysis:
    log.warning("No clear pulse in the audio, falling back to %.0f BPM", FALLBACK_BPM)
    tempo_map = TempoMap([TempoEvent(0, FALLBACK_BPM)], [TimeSignatureEvent(0, 4, 4)])
    decision = f"no clear pulse in the audio: default {FALLBACK_BPM:.0f} BPM"
    return TempoAnalysis(tempo_map, FALLBACK_BPM, "fallback", decision, strength)


def estimate_tempo_map(
    mono: np.ndarray,
    samplerate: int = ANALYSIS_SAMPLERATE,
    bpm_override: float | None = None,
    max_beat_drift_s: float = DEFAULT_MAX_BEAT_DRIFT_S,
    drums: np.ndarray | None = None,
    harmonic: np.ndarray | None = None,
    bass: np.ndarray | None = None,
) -> TempoAnalysis:
    """Estimate the song's tempo map from its mix.

    Args:
        mono: The mix.
        samplerate: Its sample rate.
        bpm_override: Use exactly this tempo; only the phase and bars are detected.
        max_beat_drift_s: How far a region's beats may stray before it gets a tempo event.
        drums: The drum stem at the same rate, which makes the bars easier to find.
        harmonic: The pitched stems mixed together, likewise.
        bass: The bass stem, likewise.
    """
    if bpm_override is None and mono.size < MIN_ANALYSIS_SECONDS * samplerate:
        return _fallback(0.0)
    envelope = onset_envelope(mono, samplerate)
    frame_rate = samplerate / HOP_LENGTH
    duration_s = len(mono) / samplerate

    base_bpm, strength = select_tempo(envelope, frame_rate)
    onsets, heights = _strong_onsets(envelope, frame_rate)
    off_share = 0.0

    if bpm_override is not None:
        choice = _override_grid(
            bpm_override, envelope, samplerate, frame_rate, onsets, heights, duration_s, base_bpm
        )
    else:
        if strength < MIN_TEMPO_STRENGTH or onsets.size < _MIN_REGION_BEATS:
            return _fallback(strength)
        off_share = off_tempo_share(envelope, frame_rate, base_bpm)
        changes_tempo = off_share > MAX_OFF_TEMPO_SHARE
        expected = local_tempo_curve(envelope, frame_rate, base_bpm) if changes_tempo else base_bpm
        beats = _track_beats(envelope, samplerate, expected)
        if len(beats) < MIN_BEATS:
            return _fallback(strength)
        kept = beats[_beats_with_evidence(beats, envelope, frame_rate)]
        kept = kept if kept.size >= MIN_BEATS else beats
        choice = choose_grid(kept, onsets, heights, base_bpm, duration_s, max_beat_drift_s)

    meter = detect_meter(
        tempo_map_from_segments(choice.segments),
        mono,
        samplerate,
        drums,
        harmonic,
        bass,
        allow_rescaling=bpm_override is None,
    )
    return TempoAnalysis(
        tempo_map=meter.tempo_map,
        bpm=choice.bpm,
        method=choice.method,
        decision=choice.decision,
        tempo_strength=strength,
        max_beat_drift_ms=max_beat_drift_s * 1000.0,
        final=choice.final,
        one_tempo=choice.one_tempo,
        event_details=choice.details,
        off_tempo_share=off_share,
        meter=meter,
        estimated_bpm=base_bpm,
    )
