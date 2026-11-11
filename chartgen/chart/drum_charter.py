"""Turns the hits of a drum stem into an Expert drum track, and holds drums to their hard rules.

The hard rules live here, in code. ``drum_hits.toml`` decides what is heard, never what a position may
hold, so no setting can loosen them. Hard, Medium and Easy are made from Expert in ``drum_difficulty``,
under the same rules and their own.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

from chartgen.audio.drum_hits import DrumAnalysis, DrumHit
from chartgen.chart.charter import END_MARGIN_S, ChartedTrack, _quantize
from chartgen.chart.difficulty import HardRuleViolation
from chartgen.core.drums import GEM_FOR_PIECE, DrumGem, DrumPiece
from chartgen.core.model import Difficulty, Instrument, Track
from chartgen.core.timing import TempoMap

MAX_PADS = 2
"""Two hands. The kick is the foot and comes on top."""

DRUM_HARD_RULES = (
    "drums: at most two pads at once on every level, for two hands, plus the kick",
    "drums: no sustain and no force or tap flag; only yellow, blue and green can be cymbals",
    "drums: no note in an opening that is not part of the song",
)
"""Listed in ``analysis.json``. The result is also deterministic, which the tests check."""

UNVERIFIED_PIECES = frozenset(
    {DrumPiece.HIGH_TOM, DrumPiece.MID_TOM, DrumPiece.FLOOR_TOM, DrumPiece.CRASH}
)
"""The one reference has 16 tom gems and 41 green cymbals: too few to measure either."""
UNVERIFIED_GEMS = frozenset(GEM_FOR_PIECE[piece] for piece in UNVERIFIED_PIECES)

_PAD_PRIORITY = {DrumGem.RED: 2}
"""Which pads stay when more than two land on one tick: the snare, then cymbals, then toms."""


def _priority(gem: DrumGem) -> int:
    return _PAD_PRIORITY.get(gem, 1 if gem.cymbal else 0)


@dataclass(frozen=True)
class DrumChart:
    """What became of the hits: kept in ``analysis.json``."""

    analysis: DrumAnalysis
    merged_on_one_tick: int
    """Hits that snapped to a tick another hit had already taken."""
    pads_dropped: int
    """Pads left out to keep to two hands."""
    strengths: Mapping[int, float] = field(default_factory=dict)
    """How hard each tick was struck: its strongest hit. The lower levels use only their order."""

    @staticmethod
    def gem_counts(track: Track) -> dict[str, int]:
        """How many gems of each kind the track has, every kind listed."""
        counts = {gem.value: 0 for gem in DrumGem}
        for note in track.notes:
            counts[DrumGem.of_note(note).value] += 1
        return counts

    def unverified_counts(self, track: Track) -> dict[str, int]:
        """The same for the kinds that could not be measured: toms and the crash."""
        counts = self.gem_counts(track)
        return {gem.value: counts[gem.value] for gem in DrumGem if gem in UNVERIFIED_GEMS}


def check_drum_track(track: Track) -> None:
    """Hold a drum track to the rules a single level must keep.

    Raises:
        HardRuleViolation: If a note is not a drum gem, or a tick holds more than two pads.
    """
    pads: dict[int, int] = {}
    for note in track.notes:
        try:
            gem = DrumGem.of_note(note)
        except ValueError as error:
            raise HardRuleViolation(f"drums/{track.difficulty.value}: {error}") from error
        if gem.is_pad:
            pads[note.tick] = pads.get(note.tick, 0) + 1
    crowded = sorted(tick for tick, count in pads.items() if count > MAX_PADS)
    if crowded:
        raise HardRuleViolation(
            f"drums/{track.difficulty.value}: more than {MAX_PADS} pads at once at tick {crowded[0]}"
        )


def _gems_of_tick(hits: Sequence[DrumHit]) -> tuple[list[DrumGem], int]:
    """The gems of the hits that share a tick, at most one per lane and two pads.

    A cymbal wins its lane over a tom: toms are not verified. Of two gems of a kind, the louder hit's
    stays. Returns the gems and how many pads had to go.
    """
    best: dict[int, tuple[DrumGem, float]] = {}
    for hit in hits:
        for gem in hit.gems:
            current = best.get(gem.lane)
            key = (gem.cymbal, hit.strength)
            if current is None or key > (current[0].cymbal, current[1]):
                best[gem.lane] = (gem, hit.strength)
    pads = sorted(
        ((gem, strength) for gem, strength in best.values() if gem.is_pad),
        key=lambda item: (_priority(item[0]), item[1]),
        reverse=True,
    )
    kept = [gem for gem, _ in pads[:MAX_PADS]]
    if DrumGem.KICK.lane in best:
        kept.append(DrumGem.KICK)
    return sorted(kept, key=lambda gem: (gem.lane, gem.cymbal)), max(0, len(pads) - MAX_PADS)


def build_drum_expert_track(
    analysis: DrumAnalysis,
    tempo_map: TempoMap,
    duration_s: float,
    not_before_s: float = 0.0,
) -> ChartedTrack:
    """Place the hits on the song's grid as an Expert drum track.

    Nothing lands before ``not_before_s``, where an opening that is not part of the song ends; a hit is
    judged by where it lands, since snapping can carry it across the line.
    """
    hits = [hit for hit in analysis.hits if hit.time_s < duration_s - END_MARGIN_S]
    times = np.array([hit.time_s for hit in hits], dtype=np.float64)
    ticks = _quantize(times, tempo_map)
    by_tick: dict[int, list[DrumHit]] = {}
    for hit, tick in zip(hits, ticks):
        if not_before_s > 0 and tempo_map.seconds_at(float(tick)) < not_before_s:
            continue
        by_tick.setdefault(int(tick), []).append(hit)
    notes = []
    dropped = 0
    for tick in sorted(by_tick):
        gems, lost = _gems_of_tick(by_tick[tick])
        dropped += lost
        notes.extend(gem.note(tick) for gem in gems)
    track = Track(Instrument.DRUMS, Difficulty.EXPERT, notes)
    check_drum_track(track)
    merged = sum(len(group) - 1 for group in by_tick.values())
    strengths = {tick: max(hit.strength for hit in group) for tick, group in by_tick.items()}
    return ChartedTrack(
        track, len(analysis.hits), drum_chart=DrumChart(analysis, merged, dropped, strengths)
    )
