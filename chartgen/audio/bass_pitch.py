"""The pitch of each bass note.

A guitar plays chords, so all that can be read from it is where its spectrum lies. A bass line is
one note at a time, so its real pitch can be measured, and ``librosa.pyin`` needs nothing new to be
installed. Against the one human bass chart we can compare with, the direction of the moves agreed
44% of the time from the spectrum and 61% from this.
"""

from __future__ import annotations

import librosa
import numpy as np

from chartgen.audio.io import ANALYSIS_SAMPLERATE

FMIN_HZ = 30.0
"""Below the low B of a five-string bass."""
FMAX_HZ = 400.0
"""Above anything but a solo. A wider range only gives the tracker more octaves to mistake."""
FRAME_LENGTH = 2048
"""Holds at least two periods of ``FMIN_HZ``, which pyin needs."""
HOP_LENGTH = 512
_ATTACK_SKIP_S = 0.03
"""The attack itself is noise; pitch settles just after it."""
_WINDOW_S = 0.18
_MIN_WINDOW_S = 0.02


def note_semitones(
    mono: np.ndarray,
    times: np.ndarray,
    next_times: np.ndarray,
    samplerate: int = ANALYSIS_SAMPLERATE,
) -> np.ndarray:
    """Return each note's pitch in whole semitones, NaN where no pitch could be heard.

    Whole semitones, because the fret mapper takes two equal values to be the same note played
    again, and a held note's pitch never measures exactly the same twice.

    Args:
        mono: The bass stem.
        times: Note start times.
        next_times: When each note is cut off by the next one.
        samplerate: The stem's sample rate.
    """
    values = np.full(times.size, np.nan)
    if times.size == 0 or mono.size < FRAME_LENGTH:
        return values
    frequency, voiced, _ = librosa.pyin(
        mono,
        fmin=FMIN_HZ,
        fmax=FMAX_HZ,
        sr=samplerate,
        frame_length=FRAME_LENGTH,
        hop_length=HOP_LENGTH,
    )
    frames_per_second = samplerate / HOP_LENGTH
    for index, (time, next_time) in enumerate(zip(times, next_times)):
        first = int((time + _ATTACK_SKIP_S) * frames_per_second)
        stop = max(min(time + _WINDOW_S, next_time), time + _ATTACK_SKIP_S + _MIN_WINDOW_S)
        window = slice(first, max(first + 1, int(stop * frames_per_second)))
        heard = frequency[window][voiced[window]]
        if heard.size:
            values[index] = float(np.round(librosa.hz_to_midi(float(np.median(heard)))))
    return values
