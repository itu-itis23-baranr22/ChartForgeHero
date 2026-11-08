"""Per-instrument charting: which stem feeds which instrument, and who charts it."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

import numpy as np

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

CHARTABLE_INSTRUMENTS = frozenset({Instrument.GUITAR})
"""Instruments with a chart generator so far. Later phases add the others."""


def build_tracks_for(
    instrument: Instrument,
    mono: np.ndarray,
    tempo_map: TempoMap,
    duration_s: float,
    vocals: np.ndarray | None = None,
) -> list[ChartedTrack]:
    """Return the charted tracks of ``instrument``, Expert first, then Hard, Medium and Easy.

    A stem without notes gives nothing.
    """
    expert = build_expert_track(instrument, mono, tempo_map, duration_s, vocals=vocals)
    if not expert.track.notes:
        return []
    config = load_config()
    measures = measure_track(expert.track, tempo_map, len(expert.positions))
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
