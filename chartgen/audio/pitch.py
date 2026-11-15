"""What each note sounds like: where its pitch lies relative to its neighbours, whether it
repeats the previous note, and whether it is a chord.

Nothing here needs absolute accuracy, because the fret mapper only asks whether a note goes up
or down, and how far. That suits what can actually be measured. Against a human chart, the
direction of a single estimated pitch agreed with the charter's lane moves only 41% of the
time, while the direction of the center of mass of the log-compressed spectrum agreed 76% of
the time: on a chord or arpeggio no single pitch tells the story. Spectral flatness separated
the human's chords from single notes with an AUC of 0.92.

All of it is read from a constant-Q spectrum with no model behind it, which keeps the tool free
of further dependencies. Those figures come from one lightly distorted song. Heavy distortion
shifts flatness upward for every note: on such a song the median rose from 0.5 to 0.7, and a
fixed limit would call nearly everything a chord. So the limit follows the song's own median,
but whether chords can be told apart on distorted guitar at all remains unmeasured until a
distorted reference chart is available. ``chartgen evaluate`` will show it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import librosa
import numpy as np

from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.onsets import HOP_LENGTH

BINS_PER_SEMITONE = 3
_ATTACK_SKIP_S = 0.03
"""The attack itself is noise; pitch settles just after it."""
_WINDOW_S = 0.18
_MIN_WINDOW_S = 0.02
_SILENT = 1e-6


@dataclass(frozen=True)
class PitchConfig:
    fmin_hz: float = 65.4
    """C2: covers a guitar and most of a bass."""
    octaves: int = 6
    chord_flatness: float = 0.5
    """Above this spectral flatness, or the song's median if higher, more than one pitch is
    taken to be sounding."""
    triad_margin: float = 0.2
    """This far above the chord limit, the note counts as three voices."""
    repeat_similarity: float = 0.95
    """Spectra at least this similar are taken to be the same note or chord played again."""
    raw_repeat_percentile: float | None = None
    """If set, a repeat also needs the plain spectra (:attr:`NotePitch.raw_similarity`) at least as alike
    as this percentile of the song's own note-to-note values. On distorted guitar every log spectrum looks
    like the last, so ``repeat_similarity`` alone called nearly every chord change a repeat; the
    least alike plain spectra are where the chord changes. None keeps the log rule alone."""


@dataclass(frozen=True)
class NotePitch:
    contour: float
    """The log-spectrum's center of mass in semitones above ``fmin_hz``. NaN for silence."""
    similarity: float
    """How much the spectrum resembles the previous note's: 1 is identical."""
    flatness: float
    voices: int
    """Estimated number of pitches sounding: 1 to 3."""
    raw_similarity: float = 0.0
    """The same as ``similarity`` on the plain spectrum, without the log compression, so the loudest
    partials count most. 0 for the first note after silence."""

    @property
    def is_known(self) -> bool:
        return bool(np.isfinite(self.contour))


def chord_limit_for(flatness: list[float], config: PitchConfig | None = None) -> float:
    """Return the flatness above which a note counts as a chord in this song.

    This is a stopgap for heavily distorted guitar, whose every note is flat: above the fixed
    limit, the song's own median takes over. Whether that separates chords from single notes
    there is unmeasured, so callers should warn when it is in force.
    """
    cfg = config or PitchConfig()
    return max(cfg.chord_flatness, float(np.median(flatness))) if flatness else cfg.chord_flatness


def analyze_pitches(
    mono: np.ndarray,
    times: np.ndarray,
    next_times: np.ndarray,
    samplerate: int = ANALYSIS_SAMPLERATE,
    config: PitchConfig | None = None,
) -> list[NotePitch]:
    """Describe the note starting at each of ``times``.

    Args:
        mono: The stem.
        times: Note start times.
        next_times: When each note is cut off by the next one.
        samplerate: The stem's sample rate.
        config: Analysis limits.
    """
    cfg = config or PitchConfig()
    unknown = NotePitch(float("nan"), 0.0, 0.0, 1)
    if times.size == 0:
        return []
    if mono.size < HOP_LENGTH * 4:
        return [unknown] * times.size

    spectrum = np.abs(
        librosa.cqt(
            y=mono,
            sr=samplerate,
            hop_length=HOP_LENGTH,
            fmin=cfg.fmin_hz,
            n_bins=12 * cfg.octaves * BINS_PER_SEMITONE,
            bins_per_octave=12 * BINS_PER_SEMITONE,
        )
    )
    semitones = spectrum.reshape(12 * cfg.octaves, BINS_PER_SEMITONE, -1).max(axis=1)
    if float(semitones.max()) < _SILENT:
        return [unknown] * times.size

    positions = np.arange(semitones.shape[0], dtype=np.float64)
    frames_per_second = samplerate / HOP_LENGTH
    frame_total = semitones.shape[1]

    results: list[NotePitch] = []
    previous: np.ndarray | None = None
    previous_profile: np.ndarray | None = None
    for time, next_time in zip(times, next_times):
        first = min(int((time + _ATTACK_SKIP_S) * frames_per_second), frame_total - 1)
        stop = max(min(time + _WINDOW_S, next_time), time + _ATTACK_SKIP_S + _MIN_WINDOW_S)
        window = semitones[:, first : max(first + 1, int(stop * frames_per_second))]
        profile = np.median(window, axis=1)
        total = float(profile.sum())
        if total < _SILENT:
            results.append(unknown)
            previous = previous_profile = None
            continue

        flatness = float(np.exp(np.mean(np.log(profile + 1e-9))) / (profile.mean() + 1e-9))
        shape = np.log1p(100.0 * profile / profile.max())
        contour = float(np.dot(shape, positions) / shape.sum())
        similarity = raw_similarity = 0.0
        if previous is not None and previous_profile is not None:
            similarity = _cosine(shape, previous)
            raw_similarity = _cosine(profile, previous_profile)
        previous, previous_profile = shape, profile
        results.append(NotePitch(contour, similarity, flatness, 1, raw_similarity))

    known = [note.flatness for note in results if note.is_known]
    if not known:
        return results
    chord_limit = chord_limit_for(known, cfg)
    triad_limit = chord_limit + cfg.triad_margin
    return [
        replace(note, voices=3 if note.flatness >= triad_limit else 2)
        if note.is_known and note.flatness >= chord_limit
        else note
        for note in results
    ]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def contour_with_repeats(
    pitches: list[NotePitch],
    repeat_similarity: float | None = None,
    raw_percentile: float | None = None,
) -> np.ndarray:
    """Return a contour in which a repeated note has exactly the previous note's value.

    The center of mass never quite repeats, so a riff's repeated notes would otherwise look
    like tiny steps up and down.

    Args:
        pitches: The notes, in order.
        repeat_similarity: How alike two log spectra must be; by default ``PitchConfig``'s.
        raw_percentile: If set, a repeat also needs the plain spectra at least as alike as this
            percentile of the song's own values (see :attr:`PitchConfig.raw_repeat_percentile`).
    """
    threshold = PitchConfig.repeat_similarity if repeat_similarity is None else repeat_similarity
    raw_limit = -np.inf
    if raw_percentile is not None:
        raw = [
            pitch.raw_similarity
            for before, pitch in zip(pitches, pitches[1:])
            if before.is_known and pitch.is_known
        ]
        if raw:
            raw_limit = float(np.percentile(raw, raw_percentile))
    values = np.array([pitch.contour for pitch in pitches], dtype=np.float64)
    for index in range(1, len(pitches)):
        pitch = pitches[index]
        if (
            pitch.similarity >= threshold
            and pitch.raw_similarity >= raw_limit
            and np.isfinite(values[index - 1])
        ):
            values[index] = values[index - 1]
    return values
