"""Tempo map extraction. Runs once, on the original mix; every instrument shares the result.

``librosa.beat.beat_track`` left to itself reads the wrong metrical level on real
songs (129 instead of 97 BPM). Told the right tempo, it is excellent: against the beats
a human placed in a Harmonix chart, the guided tracker was a median 8 ms away and within
35 ms for 97% of them. So the two problems are solved separately:

1. The Fourier transform of the whole onset envelope gives the tempo, with harmonic
   support picking the metrical level.
2. A tracker guided by that tempo finds the beats. If local tempo really differs across
   the song, it follows a tempo curve instead of a single value.
3. Tempo events must earn their place. The song gets one tempo (method ``constant``)
   if that fits its onsets as well as following the beats does, or if no section differs
   meaningfully and little is lost. Otherwise it gets constant segments (method
   ``variable``): that same Harmonix song wanders between 94 and 99 BPM, and one tempo
   would be a median 160 ms off.
4. Bass accents and chord changes decide where the bars begin.

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

NO_BENEFIT_ON_GRID_GAIN = 0.03
"""Segments must put this much more of the onsets on the grid to be worth any events."""
MAX_TEMPO_DEVIATION = 0.015
"""Sections closer than this to the main tempo count as performance, not a tempo change."""
MAX_PERFORMANCE_ON_GRID_LOSS = 0.15
"""Even without a meaningful tempo change, one tempo may not cost more than this."""
SECTION_BEATS = 32
_MIN_SECTION_EVIDENCE = 0.75
DRIFT_WINDOW_S = 30.0
_MIN_WINDOW_BEATS = 8
_REGRESSION_ROUNDS = 4

FIT_TOLERANCE_S = 0.025
"""A segment ends once a beat strays further than this from its line. Measured against
a human tempo map: 25 ms and 8 beats gave 43 events with 94% of beats within 35 ms of the
human's, while 40 ms and 16 beats gave 29 events but only 80%."""
MIN_SEGMENT_BEATS = 8
MERGE_BPM_DIFFERENCE = 0.05

GRID_DIVISOR = 4
GRID_MATCH_S = 0.035
"""Onsets this close to a sixteenth note count as being on the grid."""

BEATS_PER_BAR = 4
"""Bars are assumed to be 4/4 until time signature detection exists."""
_MIN_BEATS_FOR_BARS = 16


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
    """The main tempo: the single tempo, or the typical one of a variable song."""
    method: str
    """``constant``, ``variable``, ``override`` or ``fallback``."""
    decision: str
    """Why this method was chosen, in words."""
    segment_count: int
    on_grid_ratio: float
    """Share of strong onsets within :data:`GRID_MATCH_S` of a sixteenth note."""
    grid_error_p95_ms: float
    tempo_strength: float
    off_tempo_share: float = 0.0
    """Share of 30 second windows whose local tempo differs from the main tempo."""
    max_window_drift_ms: float = 0.0
    """Largest average distance between the beats and one straight tempo in any window."""
    max_section_deviation: float = 0.0
    """Largest relative tempo difference of any section from the main tempo."""
    one_tempo_on_grid: float | None = None
    """Share of strong onsets on the grid if the song had one tempo."""
    segments_on_grid: float | None = None
    """Share of strong onsets on the grid if the map followed the tracked beats."""
    first_downbeat_s: float | None = None
    bar_confidence: float = 0.0
    """How far the chosen bar phase stands out from the runner-up, in standard deviations."""
    estimated_bpm: float | None = None
    """The whole-song estimate, also reported when ``--bpm`` overrides it."""

    @property
    def is_fallback(self) -> bool:
        return self.method == "fallback"

    def event_reasons(self) -> list[str]:
        """Explain each tempo event, in the order of ``tempo_map.tempos``."""
        tempos = self.tempo_map.tempos
        has_lead_in = len(tempos) > 1 and tempos[1].tick == self.tempo_map.resolution
        general = {
            "constant": "main tempo",
            "override": "tempo given with --bpm",
            "variable": "the beats moved too far from the previous tempo",
            "fallback": "default tempo: the audio has no clear pulse",
        }[self.method]
        reasons = [general] * len(tempos)
        if has_lead_in:
            reasons[0] = "lead-in: fits the start of the audio to the first grid beat"
        return reasons


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
        height=max(level * 2.0, OnsetConfig.min_strength),
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
    return strength >= max(OnsetConfig.min_strength, 0.5 * float(np.median(strength)))


def _max_window_mean(times: np.ndarray, residuals: np.ndarray) -> float:
    """Return the largest absolute average of ``residuals`` in any window of the song."""
    largest = 0.0
    start = float(times[0])
    while start < times[-1]:
        inside = (times >= start) & (times < start + DRIFT_WINDOW_S)
        if inside.sum() >= _MIN_WINDOW_BEATS:
            largest = max(largest, abs(float(residuals[inside].mean())))
        start += DRIFT_WINDOW_S / 2
    return largest


def _beat_phase(beats: np.ndarray, period_s: float) -> float:
    """Return where within a beat the given beats gather. Positions are compared modulo the
    period because a tracker can add or drop a beat in a sparse passage: numbering beats
    in sequence would turn that into a whole beat of apparent drift for the rest of the song."""
    pointer = np.mean(np.exp(2j * np.pi * beats / period_s))
    return float(np.angle(pointer) * period_s / (2 * np.pi))


def _beat_residuals(beats: np.ndarray, period_s: float, phase_s: float) -> np.ndarray:
    return np.mod(beats - phase_s + period_s / 2, period_s) - period_s / 2


def _fit_one_tempo(
    beats: np.ndarray, onsets: np.ndarray, heights: np.ndarray, bpm: float
) -> tuple[float, float]:
    """Return (start, period) of the best single tempo.

    The tracker's beats say which onsets are on the beat; every onset on the sixteenth
    grid around them then refines period and phase, far beyond the tracker's frame size.
    """
    period = 60.0 / bpm
    start = _beat_phase(beats, period)
    step = period / GRID_DIVISOR
    for _ in range(_REGRESSION_ROUNDS):
        index = np.round((onsets - start) / step)
        matched = np.abs(onsets - (start + index * step)) <= GRID_MATCH_S
        if matched.sum() < _MIN_WINDOW_BEATS:
            break
        step, start = np.polyfit(index[matched], onsets[matched], 1, w=np.sqrt(heights[matched]))
    return float(start), float(step * GRID_DIVISOR)


def _section_deviation(beats: np.ndarray, period_s: float) -> float:
    """Return the largest difference between a section's own tempo and ``period_s``.

    Sections are long enough that frame-sized jitter in the tracker's beats cannot
    masquerade as a tempo change. ``beats`` should hold only beats with evidence.
    """
    largest = 0.0
    for first in range(0, max(1, len(beats) - SECTION_BEATS + 1), SECTION_BEATS // 2):
        section = beats[first : first + SECTION_BEATS]
        if len(section) < SECTION_BEATS // 2:
            continue
        count = np.round((section - section[0]) / period_s)
        local_period = float(np.polyfit(count, section, 1)[0])
        largest = max(largest, abs(local_period / period_s - 1.0))
    return largest


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
    if times.size == 0:
        return 0.0, float("nan")
    step = tempo_map.resolution / GRID_DIVISOR
    grid = np.round(tempo_map.ticks_at(times) / step) * step
    errors = np.abs(tempo_map.seconds_at(grid) - times)
    return float(np.mean(errors <= GRID_MATCH_S)), float(np.percentile(errors, 95) * 1000.0)


def _z_scored(values: np.ndarray) -> np.ndarray:
    spread = float(values.std())
    return (values - values.mean()) / spread if spread > 0 else np.zeros_like(values)


def align_bars(
    tempo_map: TempoMap, mono: np.ndarray, samplerate: int = ANALYSIS_SAMPLERATE
) -> tuple[TempoMap, float | None, float]:
    """Find where the 4/4 bars begin and start them there.

    Bass drums and chord changes favour the first beat of a bar. If the first downbeat
    is not a whole number of bars after tick 0, a short pickup measure at the start
    shifts the bar lines onto it.

    Returns:
        The tempo map with bar lines moved, the first downbeat's time, and the
        confidence. Too little audio returns the map unchanged and no downbeat.
    """
    resolution = tempo_map.resolution
    last = int(tempo_map.ticks_at(len(mono) / samplerate) // resolution)
    if last < _MIN_BEATS_FOR_BARS:
        return tempo_map, None, 0.0

    beats = np.arange(1, last + 1)
    frames = np.round(tempo_map.seconds_at(beats * resolution) * samplerate / HOP_LENGTH).astype(int)

    low = librosa.onset.onset_strength(
        y=mono, sr=samplerate, hop_length=HOP_LENGTH, n_fft=2048, fmax=200.0
    )
    accents = np.array([low[max(0, f - 2) : f + 3].max(initial=0.0) for f in frames])

    chroma_hop = HOP_LENGTH * 4
    chroma = librosa.feature.chroma_stft(y=mono, sr=samplerate, hop_length=chroma_hop, n_fft=4096)
    edges = np.clip(frames // 4, 0, chroma.shape[1] - 1)
    ends = np.r_[edges[1:], edges[-1] + 1]
    profiles = np.stack([chroma[:, a : max(a + 1, b)].mean(axis=1) for a, b in zip(edges, ends)])
    norms = np.linalg.norm(profiles, axis=1) + 1e-9
    similarity = np.sum(profiles[1:] * profiles[:-1], axis=1) / (norms[1:] * norms[:-1])
    changes = np.r_[0.0, 1.0 - similarity]

    evidence = _z_scored(accents) + _z_scored(changes)
    scores = np.array([evidence[beats % BEATS_PER_BAR == p].mean() for p in range(BEATS_PER_BAR)])
    phase = int(np.argmax(scores))
    confidence = float(scores[phase] - np.sort(scores)[-2])

    first = phase if phase > 0 else BEATS_PER_BAR
    signatures = [TimeSignatureEvent(0, BEATS_PER_BAR, 4)]
    if first != BEATS_PER_BAR:
        signatures = [
            TimeSignatureEvent(0, first, 4),
            TimeSignatureEvent(first * resolution, BEATS_PER_BAR, 4),
        ]
    aligned = TempoMap(tempo_map.tempos, signatures, resolution)
    return aligned, float(tempo_map.seconds_at(first * resolution)), confidence


@dataclass(frozen=True)
class _Choice:
    """The tempo decision, before bars and statistics are worked out."""

    segments: list[TempoSegment]
    bpm: float
    method: str
    decision: str
    off_share: float = 0.0
    drift_s: float = 0.0
    deviation: float = 0.0
    one_tempo_on_grid: float | None = None
    segments_on_grid: float | None = None


def _single_segment(start_s: float, period_s: float, duration_s: float) -> list[TempoSegment]:
    phase = float(np.mod(start_s, period_s))
    return [TempoSegment(0, max(1, int((duration_s - phase) / period_s)), phase, period_s)]


def _choose_override(
    bpm: float, envelope: np.ndarray, samplerate: int, duration_s: float, estimated: float
) -> _Choice:
    """Keep the given tempo exactly and only look for the phase."""
    period = 60.0 / bpm
    beats = _track_beats(envelope, samplerate, bpm)
    phase = 0.0
    drift = 0.0
    if beats.size >= _MIN_WINDOW_BEATS:
        phase = _beat_phase(beats, period)
        drift = _max_window_mean(beats, _beat_residuals(beats, period, phase))
    return _Choice(
        _single_segment(phase, period, duration_s),
        bpm,
        "override",
        f"--bpm {bpm:g} given on the command line (whole-song estimate: {estimated:.2f})",
        drift_s=drift,
    )


def _choose_automatically(
    envelope: np.ndarray,
    samplerate: int,
    frame_rate: float,
    base_bpm: float,
    onsets: np.ndarray,
    heights: np.ndarray,
    duration_s: float,
) -> _Choice | None:
    """Prefer one tempo; return None when the tracker finds no usable beats."""
    off_share = off_tempo_share(envelope, frame_rate, base_bpm)
    changes_tempo = off_share > MAX_OFF_TEMPO_SHARE
    expected = local_tempo_curve(envelope, frame_rate, base_bpm) if changes_tempo else base_bpm
    beats = _track_beats(envelope, samplerate, expected)
    if len(beats) < MIN_SEGMENT_BEATS:
        return None

    segments = fit_segments(beats)
    lengths = np.array([segment.last_beat - segment.first_beat for segment in segments], float)
    periods = np.array([segment.period_s for segment in segments])
    typical_bpm = 60.0 / float(np.average(periods, weights=lengths))
    segments_grid, _ = _grid_statistics(tempo_map_from_segments(segments), onsets)

    if changes_tempo:
        decision = (
            f"{off_share:.0%} of the 30 s windows hold another tempo "
            f"(limit {MAX_OFF_TEMPO_SHARE:.0%}): {len(segments)} constant sections"
        )
        return _Choice(
            segments, typical_bpm, "variable", decision, off_share, segments_on_grid=segments_grid
        )

    evidence = beats[_beats_with_evidence(beats, envelope, frame_rate)]
    usable = evidence if evidence.size >= _MIN_WINDOW_BEATS else beats
    start, period = _fit_one_tempo(usable, onsets, heights, base_bpm)
    single = _single_segment(start, period, duration_s)
    single_grid, _ = _grid_statistics(tempo_map_from_segments(single), onsets)
    drift = _max_window_mean(usable, _beat_residuals(usable, period, start))
    deviation = _section_deviation(usable, period)
    gain = segments_grid - single_grid
    comparison = (
        f"{single_grid:.0%} of onsets on the grid with one tempo, "
        f"{segments_grid:.0%} with {len(segments)} sections"
    )

    if gain <= NO_BENEFIT_ON_GRID_GAIN:
        decision = f"{comparison}: tempo changes would not help"
        chosen, bpm, method = single, 60.0 / period, "constant"
    elif deviation <= MAX_TEMPO_DEVIATION and gain <= MAX_PERFORMANCE_ON_GRID_LOSS:
        decision = (
            f"{comparison}, but sections differ at most {deviation:.2%} from the main tempo "
            f"(limit {MAX_TEMPO_DEVIATION:.1%}): treated as performance, one tempo kept"
        )
        chosen, bpm, method = single, 60.0 / period, "constant"
    else:
        decision = (
            f"{comparison}, and sections differ up to {deviation:.2%} from the main tempo "
            f"(limit {MAX_TEMPO_DEVIATION:.1%}): following the beats"
        )
        chosen, bpm, method = segments, typical_bpm, "variable"
    return _Choice(chosen, bpm, method, decision, off_share, drift, deviation, single_grid, segments_grid)


def _fallback(strength: float) -> TempoAnalysis:
    log.warning("No clear pulse in the audio, falling back to %.0f BPM", FALLBACK_BPM)
    tempo_map = TempoMap([TempoEvent(0, FALLBACK_BPM)], [TimeSignatureEvent(0, 4, 4)])
    decision = f"no clear pulse in the audio: default {FALLBACK_BPM:.0f} BPM"
    return TempoAnalysis(
        tempo_map, FALLBACK_BPM, "fallback", decision, 1, 0.0, float("nan"), strength
    )


def estimate_tempo_map(
    mono: np.ndarray,
    samplerate: int = ANALYSIS_SAMPLERATE,
    bpm_override: float | None = None,
) -> TempoAnalysis:
    """Estimate the song's tempo map from its mix.

    Args:
        mono: The mix.
        samplerate: Its sample rate.
        bpm_override: Use exactly this tempo; only the phase and bars are detected.

    Bars are assumed to be 4/4 until time signature detection exists.
    """
    if bpm_override is None and mono.size < MIN_ANALYSIS_SECONDS * samplerate:
        return _fallback(0.0)
    envelope = onset_envelope(mono, samplerate)
    frame_rate = samplerate / HOP_LENGTH
    duration_s = len(mono) / samplerate

    base_bpm, strength = select_tempo(envelope, frame_rate)
    onsets, heights = _strong_onsets(envelope, frame_rate)

    if bpm_override is not None:
        choice = _choose_override(bpm_override, envelope, samplerate, duration_s, base_bpm)
    else:
        if strength < MIN_TEMPO_STRENGTH or onsets.size < _MIN_WINDOW_BEATS:
            return _fallback(strength)
        automatic = _choose_automatically(
            envelope, samplerate, frame_rate, base_bpm, onsets, heights, duration_s
        )
        if automatic is None:
            return _fallback(strength)
        choice = automatic

    tempo_map = tempo_map_from_segments(choice.segments)
    tempo_map, first_downbeat, bar_confidence = align_bars(tempo_map, mono, samplerate)
    on_grid, error_p95 = _grid_statistics(tempo_map, onsets)
    return TempoAnalysis(
        tempo_map=tempo_map,
        bpm=choice.bpm,
        method=choice.method,
        decision=choice.decision,
        segment_count=len(choice.segments),
        on_grid_ratio=on_grid,
        grid_error_p95_ms=error_p95,
        tempo_strength=strength,
        off_tempo_share=choice.off_share,
        max_window_drift_ms=choice.drift_s * 1000.0,
        max_section_deviation=choice.deviation,
        one_tempo_on_grid=choice.one_tempo_on_grid,
        segments_on_grid=choice.segments_on_grid,
        first_downbeat_s=first_downbeat,
        bar_confidence=bar_confidence,
        estimated_bpm=base_bpm,
    )
