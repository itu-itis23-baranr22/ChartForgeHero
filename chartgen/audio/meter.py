"""Time signature and bar phase: how the beats group into bars and where a bar begins.

The first beat of a bar tends to carry a bass drum, a chord change and a new bass note,
while the backbeat carries the snare. Those signals are read at every beat, and the grouping
and phase under which they line up best win. The bass note is the strongest of them: in one
measured song, kick and chords could not tell beat 2 from beat 4, while the bass could. These
signals are far easier to read apart in separated stems, which are used when the caller has
them; otherwise they come from a harmonic/percussive split of the mix.

A song does not always say clearly where its bars begin. Rather than guess silently, the
result says how confident it is, and how many sections of the song agree.

Before any of that, :func:`check_beat_phase` asks whether the grid's beats are the song's beats
at all, or the notes halfway between them.
"""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np
from scipy.signal import butter, sosfiltfilt

from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.onsets import HOP_LENGTH, onset_envelope
from chartgen.audio.presence import DEFAULT_THRESHOLDS
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent

MIN_BEATS = 16
SNARE_WEIGHT = 0.5
"""A backbeat is good evidence against a downbeat, but drummers vary it more than the kick."""
MIN_CONFIDENCE = 2.0
"""How many standard errors the best bar phase must lead by. Below this, the phases cannot be
told apart statistically."""
MIN_SECTION_AGREEMENT = 0.5
"""Share of the song's sections that must prefer the chosen phase on their own."""
TIED_PHASES = 1.0
"""Two bar phases closer than this many standard errors are tied, and the kick decides between
them. A groove that repeats every two beats leaves chords and bass to tell bars apart, which is
not always enough, while its first beat still carries the harder kick."""
SECTION_COUNT = 8
BASS_CUTOFF_HZ = 250.0
THREE_BEAT_ADVANTAGE = 1.25
"""4/4 is far more common, so three-beat bars must fit clearly better to be chosen."""
MID_BAR_ADVANTAGE = 1.3
"""How much louder than the other eighths the two main hits of a 6/8 bar must be."""
TRIPLE_ADVANTAGE = 2.0
TWO_BEAT_ADVANTAGE = 1.5
"""If beats clearly split into three and group in twos, the tracked beat is a dotted quarter.
Both are required: a shuffle in 4/4 also splits its beats into three, and reading that as 6/8
would be far worse than missing a real 6/8."""
OFF_BEAT_KICK_ADVANTAGE = 2.0
"""How much harder the kick must land between the grid's beats for those to be the real beats.
The one measured song whose grid was half a beat off reached 3.8, the four others at most 1.4."""
SNARE_MARKS_THE_BEAT = 0.8
"""If the snare's off-beats fall below this share of its beats, the grid is right whatever the kick
does: a syncopated kick lands between beats the snare still marks. Measured 0.93 on the song whose
grid was off, at most 0.58 on the others."""


@dataclass(frozen=True)
class MeterResult:
    tempo_map: TempoMap
    """The tempo map with its time signature events set."""
    numerator: int
    denominator: int
    first_downbeat_s: float | None
    confidence: float
    """How many standard errors the chosen bar phase leads the runner-up by."""
    section_agreement: float
    """Share of the song's sections that prefer the chosen phase on their own."""
    low_confidence: bool

    @property
    def label(self) -> str:
        return f"{self.numerator}/{self.denominator}"


@dataclass(frozen=True)
class BeatPhaseCheck:
    """Whether the grid's beats are the song's beats, or the notes halfway between them.

    A tracker follows the strongest hits. In a 3-3-2 groove those are snares between the kicks,
    so it can settle half a beat from the pulse. Every note still lands on a sixteenth, so no
    onset measure can see this; only the beat lines, the bars and the click are wrong.
    """

    kick_ratio: float
    """How much harder the kick lands between the grid's beats than on them."""
    snare_ratio: float
    """The same for the snare, whose backbeat shows where the beats are if it has one."""
    section_agreement: float
    """Share of the song's sections where the kick lands harder between the beats."""
    confidence: float
    """How many standard errors the kick's off-beats lead its beats by."""
    half_beat_off: bool


def _z_scored(values: np.ndarray) -> np.ndarray:
    spread = float(values.std())
    return (values - values.mean()) / spread if spread > 0 else np.zeros_like(values)


def _at_beats(envelope: np.ndarray, frames: np.ndarray) -> np.ndarray:
    return np.array([envelope[max(0, f - 2) : f + 3].max(initial=0.0) for f in frames])


def _harmony_changes(signal: np.ndarray, frames: np.ndarray, samplerate: int, n_fft: int) -> np.ndarray:
    """Return, for each beat, how much the pitch content differs from the previous beat."""
    chroma = librosa.feature.chroma_stft(y=signal, sr=samplerate, hop_length=HOP_LENGTH * 4, n_fft=n_fft)
    edges = np.clip(frames // 4, 0, chroma.shape[1] - 1)
    ends = np.r_[edges[1:], edges[-1] + 1]
    profiles = np.stack([chroma[:, a : max(a + 1, b)].mean(axis=1) for a, b in zip(edges, ends)])
    norms = np.linalg.norm(profiles, axis=1) + 1e-9
    similarity = np.sum(profiles[1:] * profiles[:-1], axis=1) / (norms[1:] * norms[:-1])
    return np.r_[0.0, 1.0 - similarity]


def _kick_and_snare(percussive: np.ndarray, samplerate: int) -> tuple[np.ndarray, np.ndarray]:
    """Return onset envelopes of the low band, where the kick is, and the high band."""
    kick = librosa.onset.onset_strength(
        y=percussive, sr=samplerate, hop_length=HOP_LENGTH, n_fft=2048, fmax=150.0
    )
    snare = librosa.onset.onset_strength(
        y=percussive, sr=samplerate, hop_length=HOP_LENGTH, n_fft=1024, fmin=1500.0
    )
    return kick, snare


def _beat_evidence(
    frames: np.ndarray,
    percussive: np.ndarray,
    harmonic: np.ndarray,
    bass: np.ndarray,
    samplerate: int,
) -> np.ndarray:
    """Return, for each beat, how much it looks like the first beat of a bar."""
    kick, snare = _kick_and_snare(percussive, samplerate)
    return (
        _z_scored(_at_beats(kick, frames))
        - SNARE_WEIGHT * _z_scored(_at_beats(snare, frames))
        + _z_scored(_harmony_changes(harmonic, frames, samplerate, 4096))
        + _z_scored(_harmony_changes(bass, frames, samplerate, 8192))
    )


def _phase_scores(evidence: np.ndarray, beats: np.ndarray, length: int) -> np.ndarray:
    return np.array([evidence[beats % length == phase].mean() for phase in range(length)])


def _confidence(evidence: np.ndarray, beats: np.ndarray, length: int, phase: int, other: int) -> float:
    """Return the lead of ``phase`` over ``other`` in standard errors."""
    first = evidence[beats % length == phase]
    second = evidence[beats % length == other]
    error = np.sqrt(first.var() / max(1, first.size) + second.var() / max(1, second.size))
    return float((first.mean() - second.mean()) / error) if error > 0 else 0.0


def _section_agreement(evidence: np.ndarray, beats: np.ndarray, length: int, phase: int) -> float:
    agreeing = total = 0
    for section in np.array_split(np.arange(beats.size), SECTION_COUNT):
        if section.size < 2 * length:
            continue
        scores = _phase_scores(evidence[section], beats[section], length)
        total += 1
        agreeing += int(np.argmax(scores)) == phase
    return agreeing / total if total else 0.0


def _subdivision_ratio(envelope: np.ndarray, frames: np.ndarray) -> float:
    """Return how much more strongly beats split into three than into two."""
    gaps = np.diff(frames)
    starts = frames[:-1]
    third = np.r_[starts + gaps / 3, starts + 2 * gaps / 3].astype(int)
    half = (starts + gaps / 2).astype(int)
    triple = float(_at_beats(envelope, third).mean())
    binary = float(_at_beats(envelope, half).mean())
    return triple / binary if binary > 0 else 0.0


def _six_eight_start(drums: np.ndarray, frames: np.ndarray, samplerate: int) -> int | None:
    """Look for 6/8 in a three-beat cycle; return the eighth note that starts the bar.

    A 6/8 bar has two strong hits three eighth notes apart, which may fall between tracked
    beats. So loudness is folded over the six eighths of the cycle, and both of the strongest
    hits three apart must stand out on their own: a 3/4 bar has only one. Plain loudness is used: the onset envelope is in decibels,
    where a snare and a hi-hat look nearly alike. The bass drum then says which hit comes first.
    """
    level = librosa.feature.rms(y=drums, frame_length=1024, hop_length=HOP_LENGTH)[0]
    kick = librosa.onset.onset_strength(
        y=drums, sr=samplerate, hop_length=HOP_LENGTH, n_fft=2048, fmax=150.0
    )
    middles = ((frames[:-1] + frames[1:]) / 2).astype(int)
    eighths = np.empty(2 * middles.size, dtype=int)
    eighths[0::2] = frames[:-1]
    eighths[1::2] = middles
    loudness = _at_beats(level, eighths)
    bass = _at_beats(kick, eighths)
    position = np.arange(eighths.size) % 6
    fold = np.array([loudness[position == p].mean() for p in range(6)])
    low = np.array([bass[position == p].mean() for p in range(6)])
    pairs = fold[:3] + fold[3:]
    best = int(np.argmax(pairs))
    others = (fold.sum() - pairs[best]) / 4
    weaker_hit = min(fold[best], fold[best + 3])
    if others <= 0 or weaker_hit <= MID_BAR_ADVANTAGE * others:
        return None
    return best if low[best] >= low[best + 3] else best + 3


def _as_dotted_quarters(tempo_map: TempoMap) -> TempoMap:
    """Reinterpret each tracked beat as a dotted quarter note: same times, more ticks."""
    scaled = [TempoEvent(event.tick * 3 // 2, event.bpm * 1.5) for event in tempo_map.tempos]
    return TempoMap(scaled, tempo_map.time_signatures, tempo_map.resolution)


def _with_bars(
    tempo_map: TempoMap, first_tick: int, bar_ticks: int, numerator: int, denominator: int
) -> TempoMap:
    """Start the bars at ``first_tick``, with a pickup measure before it if needed."""
    resolution = tempo_map.resolution
    if first_tick % bar_ticks == 0:
        signatures = [TimeSignatureEvent(0, numerator, denominator)]
    else:
        eighth = resolution // 2
        pickup = (
            TimeSignatureEvent(0, first_tick // resolution, 4)
            if first_tick % resolution == 0
            else TimeSignatureEvent(0, first_tick // eighth, 8)
        )
        signatures = [pickup, TimeSignatureEvent(first_tick, numerator, denominator)]
    return TempoMap(tempo_map.tempos, signatures, resolution)


def _kick_decides(
    kick: np.ndarray, beats: np.ndarray, length: int, phase: int, other: int
) -> tuple[int, int]:
    """Return two tied bar phases, the one with the harder kick first."""
    scores = _phase_scores(kick, beats, length)
    return (other, phase) if scores[other] > scores[phase] else (phase, other)


def _level_ratio(off_beats: np.ndarray, beats: np.ndarray) -> float:
    """Return off-beats over beats. A band that is silent on both says nothing either way."""
    if beats.mean() <= 0 and off_beats.mean() <= 0:
        return 1.0
    return float(off_beats.mean() / max(beats.mean(), 1e-9))


def check_beat_phase(
    tempo_map: TempoMap,
    drums: np.ndarray,
    mono: np.ndarray,
    samplerate: int = ANALYSIS_SAMPLERATE,
) -> BeatPhaseCheck | None:
    """Check whether the kick says the beats are halfway between the grid's beats.

    Args:
        tempo_map: Its quarter-note ticks must be the song's tracked beats.
        drums: The drum stem. A mix cannot answer this: its onsets are the snares that misled
            the tracker in the first place.
        mono: The mix, to judge whether the drums are loud enough to be drums and not bleed.
        samplerate: Sample rate of both signals.

    Returns:
        The check, or None if the song has too few beats to tell.
    """
    resolution = tempo_map.resolution
    last = int(tempo_map.ticks_at(len(drums) / samplerate) // resolution)
    if last < MIN_BEATS:
        return None

    ticks = np.arange(1, last, dtype=np.float64) * resolution
    to_frames = lambda seconds: np.round(seconds * samplerate / HOP_LENGTH).astype(int)
    on_frames = to_frames(tempo_map.seconds_at(ticks))
    off_frames = to_frames(tempo_map.seconds_at(ticks + resolution / 2))
    kick, snare = _kick_and_snare(drums, samplerate)
    kick_on, kick_off = _at_beats(kick, on_frames), _at_beats(kick, off_frames)
    snare_on, snare_off = _at_beats(snare, on_frames), _at_beats(snare, off_frames)

    sections = [s for s in np.array_split(np.arange(ticks.size), SECTION_COUNT) if s.size]
    agreement = float(np.mean([kick_off[s].mean() > kick_on[s].mean() for s in sections]))
    error = np.sqrt(kick_on.var() / kick_on.size + kick_off.var() / kick_off.size)
    confidence = float((kick_off.mean() - kick_on.mean()) / error) if error > 0 else 0.0

    frames = min(len(drums), len(mono))
    drum_energy = float(np.sum(np.square(drums[:frames])))
    mix_energy = float(np.sum(np.square(mono[:frames])))
    limit = 10.0 ** (DEFAULT_THRESHOLDS["drums"].min_energy_ratio_db / 10.0)
    has_drums = drum_energy > 0 and drum_energy >= limit * mix_energy

    kick_ratio = _level_ratio(kick_off, kick_on)
    snare_ratio = _level_ratio(snare_off, snare_on)
    return BeatPhaseCheck(
        kick_ratio,
        snare_ratio,
        agreement,
        confidence,
        bool(
            has_drums
            and kick_ratio >= OFF_BEAT_KICK_ADVANTAGE
            and snare_ratio >= SNARE_MARKS_THE_BEAT
            and agreement >= MIN_SECTION_AGREEMENT
            and confidence >= MIN_CONFIDENCE
        ),
    )


def detect_meter(
    tempo_map: TempoMap,
    mono: np.ndarray,
    samplerate: int = ANALYSIS_SAMPLERATE,
    drums: np.ndarray | None = None,
    harmonic: np.ndarray | None = None,
    bass: np.ndarray | None = None,
    allow_rescaling: bool = True,
) -> MeterResult:
    """Find the time signature and where the bars begin.

    Args:
        tempo_map: Its quarter-note ticks must be the song's tracked beats.
        mono: The mix.
        samplerate: Sample rate of all signals.
        drums: The drum stem, if separated.
        harmonic: The pitched stems mixed together, if separated.
        bass: The bass stem, if separated.
        allow_rescaling: Whether the tracked beat may turn out to be a dotted quarter, which
            changes the tempo written to the chart. Off when the tempo was given by the user.

    Returns:
        A result whose tempo map has time signature events. Too little audio leaves the
        map as it is and reports no downbeat.
    """
    resolution = tempo_map.resolution
    last = int(tempo_map.ticks_at(len(mono) / samplerate) // resolution)
    if last < MIN_BEATS:
        return MeterResult(tempo_map, 4, 4, None, 0.0, 0.0, True)

    beats = np.arange(1, last + 1)
    seconds = tempo_map.seconds_at(beats.astype(np.float64) * resolution)
    frames = np.round(seconds * samplerate / HOP_LENGTH).astype(int)

    if drums is None or harmonic is None:
        split_harmonic, split_percussive = librosa.effects.hpss(mono)
        drums = split_percussive if drums is None else drums
        harmonic = split_harmonic if harmonic is None else harmonic
    if bass is None:
        low_pass = butter(4, BASS_CUTOFF_HZ, fs=samplerate, output="sos")
        bass = sosfiltfilt(low_pass, harmonic).astype(np.float32)
    evidence = _beat_evidence(frames, drums, harmonic, bass, samplerate)
    envelope = onset_envelope(mono, samplerate)

    fours = _phase_scores(evidence, beats, 4)
    threes = _phase_scores(evidence, beats, 3)
    length, numerator, denominator = 4, 4, 4
    scores = fours
    three_phase = int(np.argmax(threes))
    three_other = int(np.argsort(threes)[-2])
    if (
        threes.max() > max(fours.max(), 0.0) * THREE_BEAT_ADVANTAGE
        and _confidence(evidence, beats, 3, three_phase, three_other) >= MIN_CONFIDENCE
    ):
        length, numerator, denominator = 3, 3, 4
        scores = threes

    phase = int(np.argmax(scores))
    other = int(np.argsort(scores)[-2])
    confidence = _confidence(evidence, beats, length, phase, other)
    if abs(confidence) < TIED_PHASES:
        kick = _at_beats(_kick_and_snare(drums, samplerate)[0], frames)
        phase, other = _kick_decides(kick, beats, length, phase, other)
        confidence = _confidence(evidence, beats, length, phase, other)
    agreement = _section_agreement(evidence, beats, length, phase)

    bar_map = tempo_map
    ticks_per_beat = resolution
    if length == 3 and (start := _six_eight_start(drums, frames, samplerate)) is not None:
        # Eighth number 0 is the first tracked beat, which sits one quarter note into the map.
        first_tick = resolution + start * (resolution // 2)
        aligned = _with_bars(tempo_map, first_tick, 3 * resolution, 6, 8)
        return MeterResult(
            aligned,
            6,
            8,
            float(tempo_map.seconds_at(float(first_tick))),
            confidence,
            agreement,
            confidence < MIN_CONFIDENCE or agreement < MIN_SECTION_AGREEMENT,
        )
    if allow_rescaling and _subdivision_ratio(envelope, frames) > TRIPLE_ADVANTAGE:
        twos = _phase_scores(evidence, beats, 2)
        if twos.max() > max(fours.max(), 0.0) * TWO_BEAT_ADVANTAGE:
            length, numerator, denominator = 2, 6, 8
            phase = int(np.argmax(twos))
            other = 1 - phase
            confidence = _confidence(evidence, beats, length, phase, other)
            agreement = _section_agreement(evidence, beats, length, phase)
            bar_map = _as_dotted_quarters(tempo_map)
            ticks_per_beat = resolution * 3 // 2

    first = phase if phase > 0 else length
    aligned = _with_bars(
        bar_map, first * ticks_per_beat, length * ticks_per_beat, numerator, denominator
    )
    return MeterResult(
        aligned,
        numerator,
        denominator,
        float(tempo_map.seconds_at(float(first * resolution))),
        confidence,
        agreement,
        confidence < MIN_CONFIDENCE or agreement < MIN_SECTION_AGREEMENT,
    )
