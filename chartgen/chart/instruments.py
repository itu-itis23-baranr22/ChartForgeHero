"""Per-instrument charting: which stem feeds which instrument, and who charts it."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

import numpy as np

from chartgen.audio.quiet_notes import QuietNoteLimits, load_limits
from chartgen.chart.charter import ChartedTrack, build_expert_track
from chartgen.chart.difficulty import check_soft_targets, load_config, measure_track, reduce_track
from chartgen.core.model import Instrument
from chartgen.core.timing import TempoMap

STEM_FOR_INSTRUMENT: Mapping[Instrument, str] = {
    Instrument.GUITAR: "guitar",
    Instrument.BASS: "bass",
    Instrument.DRUMS: "drums",
    Instrument.KEYS: "piano",
}

CHARTABLE_INSTRUMENTS = frozenset({Instrument.GUITAR, Instrument.BASS})
"""Instruments with a chart generator so far. Later phases add the others."""
INSTRUMENTS_WITH_LOWER_LEVELS = frozenset({Instrument.GUITAR})
"""Those that also have Hard, Medium and Easy. Bass has Expert only so far, with no soft targets:
guitar's would not mean anything for it."""
VOCAL_BLEED_CHECKED = frozenset({Instrument.GUITAR})
"""Bass stays out. On the human bass chart we measured, 83% of the notes the check removed were
real, and on one song it removed 153 of 674 notes."""
QUIET_NOTES_CHECKED = frozenset({Instrument.BASS})
"""Where the kick can leak in. Whether anything is removed is set in ``quiet_notes.toml``."""


def build_tracks_for(
    instrument: Instrument,
    mono: np.ndarray,
    tempo_map: TempoMap,
    duration_s: float,
    vocals: np.ndarray | None = None,
    not_before_s: float = 0.0,
    quiet_limits: QuietNoteLimits | None = None,
) -> list[ChartedTrack]:
    """Return the charted tracks of ``instrument``, the hardest first.

    A stem without notes gives nothing.

    Args:
        instrument: What to chart.
        mono: Its stem.
        tempo_map: The song's tempo map.
        duration_s: Length of the song.
        vocals: The vocal stem, to find bleed in the instruments that are checked for it.
        not_before_s: Where an opening that is not part of the song ends. Nothing lands before it.
        quiet_limits: Replaces what ``quiet_notes.toml`` says, for the instruments it applies to.
    """
    expert = build_expert_track(
        instrument,
        mono,
        tempo_map,
        duration_s,
        vocals=vocals if instrument in VOCAL_BLEED_CHECKED else None,
        not_before_s=not_before_s,
        quiet_limits=(quiet_limits or load_limits()) if instrument in QUIET_NOTES_CHECKED else None,
    )
    if not expert.track.notes:
        return []
    config = load_config()
    measures = measure_track(expert.track, tempo_map, len(expert.positions))
    if instrument not in INSTRUMENTS_WITH_LOWER_LEVELS:
        return [replace(expert, measures=measures)]
    targets = tuple(check_soft_targets(measures, config.expert_targets))
    charted = [replace(expert, measures=measures, soft_targets=targets)]
    levels = reduce_track(instrument, expert.track, expert.positions, tempo_map, config)
    for level in levels.values():
        charted.append(
            ChartedTrack(
                level.track,
                expert.onset_count,
                measures=level.measures,
                soft_targets=level.soft_targets,
            )
        )
    return charted
