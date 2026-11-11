"""The sections a song's ``[Events]`` holds.

So far only the opening rule (decision 30): an opening that is not part of the song starts with
``Intro``, and ``Song`` marks where the song begins after it. A song without such an opening gets no
section. Phase D adds the sections found in the song itself.
"""

from __future__ import annotations

from chartgen.audio.tempo import TempoAnalysis
from chartgen.core.model import Section

INTRO_SECTION = "Intro"
"""Marks the start of an opening that is not part of the song."""
SONG_SECTION = "Song"
"""Marks where the song begins after such an opening, or practice mode calls all of it the intro."""


def song_start_s(tempo: TempoAnalysis) -> float:
    """Where the song begins: its first clear onset after an opening, or the opening's end."""
    return tempo.song_start_s or tempo.lead_in_end_s


def opening_sections(tempo: TempoAnalysis) -> list[Section]:
    """Mark an opening that is not part of the song, and where the song begins after it."""
    if tempo.lead_in_end_s <= 0:
        return []
    sixteenth = tempo.tempo_map.resolution // 4
    tick = round(tempo.tempo_map.ticks_at(song_start_s(tempo)) / sixteenth) * sixteenth
    return [Section(0, INTRO_SECTION), Section(int(tick), SONG_SECTION)]
