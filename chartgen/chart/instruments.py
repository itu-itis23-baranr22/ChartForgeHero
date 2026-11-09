"""Per-instrument charting: which stem feeds which instrument, and who charts it."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace

import numpy as np

from chartgen.audio.quiet_notes import QuietNoteLimits, load_limits
from chartgen.chart.charter import ChartedTrack, build_expert_track
from chartgen.chart.difficulty import (
    BASS_CONFIG_PATH,
    DifficultyConfig,
    OrangePitches,
    Position,
    check_soft_targets,
    count_orange_pitches,
    load_config,
    measure_track,
    reduce_track,
)
from chartgen.chart.fret_mapping import BASS_WEIGHTS_PATH, FretWeights, load_weights
from chartgen.core.model import Instrument, Track
from chartgen.core.timing import TempoMap

STEM_FOR_INSTRUMENT: Mapping[Instrument, str] = {
    Instrument.GUITAR: "guitar",
    Instrument.BASS: "bass",
    Instrument.DRUMS: "drums",
    Instrument.KEYS: "piano",
}

CHARTABLE_INSTRUMENTS = frozenset({Instrument.GUITAR, Instrument.BASS})
"""Instruments with a chart generator so far. Later phases add the others."""
VOCAL_BLEED_CHECKED = frozenset({Instrument.GUITAR})
"""Bass stays out. On the human bass chart we measured, 83% of the notes the check removed were
real, and on one song it removed 153 of 674 notes."""
QUIET_NOTES_CHECKED = frozenset({Instrument.BASS})
"""Where the kick can leak in. Whether anything is removed is set in ``quiet_notes.toml``."""


def settings_for(instrument: Instrument) -> tuple[DifficultyConfig, FretWeights]:
    """Return an instrument's own preferences. Bass has its own files, so tuning it leaves guitar be."""
    if instrument is Instrument.BASS:
        return load_config(BASS_CONFIG_PATH), load_weights(BASS_WEIGHTS_PATH)
    return load_config(), load_weights()


def _orange_of(
    track: Track, positions: Sequence[Position], config: DifficultyConfig
) -> OrangePitches | None:
    if config.max_orange_pitch_share is None:
        return None
    return count_orange_pitches(track, positions, config.max_orange_pitch_share)


def build_tracks_for(
    instrument: Instrument,
    mono: np.ndarray,
    tempo_map: TempoMap,
    duration_s: float,
    vocals: np.ndarray | None = None,
    not_before_s: float = 0.0,
    quiet_limits: QuietNoteLimits | None = None,
) -> list[ChartedTrack]:
    """Return the charted tracks of ``instrument``, Expert first, then Hard, Medium and Easy.

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
    config, weights = settings_for(instrument)
    expert = build_expert_track(
        instrument,
        mono,
        tempo_map,
        duration_s,
        weights=weights,
        vocals=vocals if instrument in VOCAL_BLEED_CHECKED else None,
        not_before_s=not_before_s,
        quiet_limits=(quiet_limits or load_limits()) if instrument in QUIET_NOTES_CHECKED else None,
    )
    if not expert.track.notes:
        return []
    measures = measure_track(expert.track, tempo_map, len(expert.positions))
    targets = tuple(check_soft_targets(measures, config.expert_targets))
    charted = [
        replace(
            expert,
            measures=measures,
            soft_targets=targets,
            orange_pitches=_orange_of(expert.track, expert.positions, config),
        )
    ]
    levels = reduce_track(instrument, expert.track, expert.positions, tempo_map, config, weights)
    for level in levels.values():
        charted.append(
            ChartedTrack(
                level.track,
                expert.onset_count,
                measures=level.measures,
                soft_targets=level.soft_targets,
                orange_pitches=_orange_of(level.track, expert.positions, config),
            )
        )
    return charted
