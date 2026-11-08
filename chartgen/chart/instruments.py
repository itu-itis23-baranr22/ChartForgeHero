"""Per-instrument charting: which stem feeds which instrument, and who charts it."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from chartgen.chart.simple import build_simple_track
from chartgen.core.model import Instrument, Track
from chartgen.core.timing import TempoMap

STEM_FOR_INSTRUMENT: Mapping[Instrument, str] = {
    Instrument.GUITAR: "guitar",
    Instrument.BASS: "bass",
    Instrument.DRUMS: "drums",
    Instrument.KEYS: "piano",
}

CHARTABLE_INSTRUMENTS = frozenset({Instrument.GUITAR})
"""Instruments with a chart generator so far. Phases B and C add the others."""


def build_tracks_for(
    instrument: Instrument, mono: np.ndarray, tempo_map: TempoMap, duration_s: float
) -> list[Track]:
    """Return the tracks of ``instrument``, or nothing when its stem produced no notes."""
    result = build_simple_track(instrument, mono, tempo_map, duration_s)
    return [result.track] if result.track.notes else []
