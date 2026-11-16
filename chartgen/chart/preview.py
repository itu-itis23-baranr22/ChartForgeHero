"""Where the song list's preview starts (decision 39, step D.2; decision 48, after reference tuning).

On the bar line closest to 14 seconds before a start of the most energetic part that comes back: its first
start when that is at least 16 bars into the song, its second otherwise. The most energetic part is the
letter that comes back whose bars are loudest in the mix on average; it is often the chorus. The eight train
human charts start the preview early (seven of them 24 to 58 s after the first note) and a chorus begins in
every one of their 30 seconds, a median 12 s in; usually the first chorus, the second when the first comes
early. When no part comes back, or the song has no sections, the preview is the loudest 30 seconds of the
song after any opening, moved to the nearest bar line.

Hard rules, here in code (``check_preview``): the preview starts on a bar line, not in an opening that
is not part of the song, and its 30 seconds fit in the song; only a song too short for that after its
opening starts the preview with the song. The validator checks the last two on its own.
"""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np

from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.sections import FoundSection, SectionAnalysis
from chartgen.clonehero.package import PREVIEW_WINDOW_S, best_preview_start_ms
from chartgen.core.timing import TempoMap

PREVIEW_LEAD_S = 14.0
"""The preview starts on the bar line closest to this many seconds before the part it leads into."""
FIRST_START_MIN_BARS = 16
"""The preview leads into the first start of the loudest part that comes back when that start is at least
this many bars after the song's first part, and into its second start otherwise."""
REPEATED_PART = "repeated part"
LOUDEST_WINDOW = "loudest window"
_HOP = 512


class PreviewRuleViolation(ValueError):
    """A chosen preview broke a hard rule: a bug, never a matter of settings."""


@dataclass(frozen=True)
class PreviewChoice:
    tick: int
    start_s: float
    rule: str
    """``REPEATED_PART`` or ``LOUDEST_WINDOW``."""
    leads_into: str | None
    """For ``REPEATED_PART``, the part whose start the preview leads into (``F2``)."""
    loudness_db: dict[str, float]
    """Each letter that comes back, with how loud the mix is over its bars, loudest first."""
    fallback_reason: str | None
    """For ``LOUDEST_WINDOW``, why no part was used."""
    moved_earlier_bars: int
    """How many bars the preview moved earlier so that its 30 seconds fit in the song."""
    too_short: bool
    """The song after any opening is shorter than the preview, which then starts with the song."""
    lead_bars: int | None = None
    """For ``REPEATED_PART``, how many bars before the part it leads into the preview starts."""

    @property
    def start_ms(self) -> int:
        return round(self.start_s * 1000)


def _letter_loudness(parts: tuple[FoundSection, ...], mix: np.ndarray, duration_s: float) -> dict[str, float]:
    """How loud the mix is, in dB averaged over time, across every bar of each letter that comes back."""
    letters = [part.letter for part in parts]
    repeated = [letter for letter in dict.fromkeys(letters) if letters.count(letter) > 1]
    if not repeated:
        return {}
    frames_db = librosa.amplitude_to_db(librosa.feature.rms(y=mix, hop_length=_HOP), ref=1.0)[0]
    frame_times = librosa.frames_to_time(np.arange(frames_db.size), sr=ANALYSIS_SAMPLERATE, hop_length=_HOP)
    ends = [part.time_s for part in parts[1:]] + [duration_s]
    loudness: dict[str, float] = {}
    for letter in repeated:
        inside = np.zeros(frames_db.size, dtype=bool)
        for part, end in zip(parts, ends):
            if part.letter == letter:
                inside |= (frame_times >= part.time_s) & (frame_times < end)
        loudness[letter] = round(float(np.mean(frames_db[inside])), 2) if inside.any() else -np.inf
    # Loudest first; a tie goes to the letter heard first (sorting is stable).
    return dict(sorted(loudness.items(), key=lambda item: -item[1]))


def choose_preview(
    found: SectionAnalysis | None,
    mix: np.ndarray,
    tempo_map: TempoMap,
    duration_s: float,
    song_start_tick: int = 0,
    window_s: float = PREVIEW_WINDOW_S,
) -> PreviewChoice:
    """Choose where the preview starts.

    Args:
        found: The song's sections, or None if they were not looked for.
        mix: The whole song, mono at the analysis rate.
        song_start_tick: Where the song starts after an opening that is not part of it (the ``Song``
            section), 0 without one. The preview never starts before it.
    """
    bars = tempo_map.bar_lines(duration_s)
    times = tempo_map.seconds_at(bars.astype(np.float64))
    allowed = min(int(np.searchsorted(bars, song_start_tick)), bars.size - 1)
    fitting = np.nonzero(times[allowed:] + window_s <= duration_s + 1e-9)[0]
    too_short = fitting.size == 0
    latest = allowed if too_short else allowed + int(fitting[-1])

    parts = found.parts if found is not None else ()
    loudness = _letter_loudness(parts, mix, duration_s)
    part_bar = None
    if loudness:
        letter = next(iter(loudness))
        starts = [part for part in parts if part.letter == letter]
        into_song = int(np.searchsorted(bars, starts[0].tick)) - int(np.searchsorted(bars, parts[0].tick))
        part = starts[0] if into_song >= FIRST_START_MIN_BARS else starts[1]
        part_bar = int(np.searchsorted(bars, part.tick))
        # The closest bar line; halfway between two, the earlier one.
        lead = int(np.argmin(np.abs(times[: part_bar + 1] - (times[part_bar] - PREVIEW_LEAD_S))))
        target = max(lead, allowed)
        rule, leads_into, reason = REPEATED_PART, part.name, None
    else:
        offset = int(round(times[allowed] * ANALYSIS_SAMPLERATE))
        loudest_s = times[allowed] + best_preview_start_ms(mix[offset:], ANALYSIS_SAMPLERATE, window_s) / 1000.0
        target = allowed + int(np.argmin(np.abs(times[allowed : latest + 1] - loudest_s)))
        rule, leads_into = LOUDEST_WINDOW, None
        reason = "no part comes back" if parts else "no sections were found"
    index = min(target, latest)
    choice = PreviewChoice(
        int(bars[index]),
        float(times[index]),
        rule,
        leads_into,
        loudness,
        reason,
        max(0, target - latest),
        too_short,
        None if part_bar is None else part_bar - index,
    )
    check_preview(choice, tempo_map, duration_s, song_start_tick, window_s)
    return choice


def check_preview(
    choice: PreviewChoice,
    tempo_map: TempoMap,
    duration_s: float,
    song_start_tick: int = 0,
    window_s: float = PREVIEW_WINDOW_S,
) -> None:
    """Hold a chosen preview to the hard rules.

    Raises:
        PreviewRuleViolation: On the first rule broken.
    """
    bars = tempo_map.bar_lines(duration_s)
    if choice.tick not in set(bars.tolist()):
        raise PreviewRuleViolation(f"the preview at tick {choice.tick} is not on a bar line")
    if choice.tick < song_start_tick:
        raise PreviewRuleViolation(
            f"the preview at tick {choice.tick} starts in the opening (the song starts at tick {song_start_tick})"
        )
    if choice.start_s + window_s > duration_s + 1e-9:
        # Only a song too short for the preview after its opening may start it with the song.
        first = int(bars[min(int(np.searchsorted(bars, song_start_tick)), bars.size - 1)])
        too_short = float(tempo_map.seconds_at(float(first))) + window_s > duration_s + 1e-9
        if not (too_short and choice.tick == first):
            raise PreviewRuleViolation(
                f"the preview's {window_s:.0f} s from {choice.start_s:.1f} s do not fit in the {duration_s:.1f} s song"
            )
