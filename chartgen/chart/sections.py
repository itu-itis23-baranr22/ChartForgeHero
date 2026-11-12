"""The sections a song's ``[Events]`` holds.

The opening rule (decision 30): an opening that is not part of the song starts with ``Intro``, and
``Song`` marks where the song begins after it. Then come the sections found in the song itself
(decision 37), named by structure: ``A1``, ``B1``, ``A2``... The part ``Song`` starts is lettered too
(it is ``A1``), so its return is ``A2``; it stays written as ``Song``. A song whose texture hardly
changes gets none of those, only the opening's two if it has one.
"""

from __future__ import annotations

from chartgen.audio.sections import SectionAnalysis
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


def song_sections(tempo: TempoAnalysis, found: SectionAnalysis | None) -> list[Section]:
    """The opening's sections, if any, then the sections found in the song."""
    return opening_sections(tempo) + [Section(section.tick, section.name) for section in (found.sections if found else ())]


def section_search_start_s(tempo: TempoAnalysis) -> float:
    """Where section finding starts: at ``Song`` after an opening, otherwise at the start."""
    return song_start_s(tempo) if tempo.lead_in_end_s > 0 else 0.0
