"""Per-instrument charting: which stem feeds which instrument, and who charts it."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from chartgen.chart.charter import ChartedTrack, build_expert_track
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
    """Return the charted tracks of ``instrument``, or nothing when its stem has no notes."""
    result = build_expert_track(instrument, mono, tempo_map, duration_s, vocals=vocals)
    return [result] if result.track.notes else []
