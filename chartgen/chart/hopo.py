"""Which notes the game plays as hammer-ons and pull-offs, without a strum.

Nothing in a ``.chart`` file marks a natural HOPO: the game derives it from the spacing. A note is
one when it is a single note, the previous position is close enough, and it is not the same single
fret as that position. A single note after a chord counts even if the chord contains its fret. The
force flag (``N 5``) flips the result, so on a natural HOPO it means a strum.

Checked against the open-source parsers of Moonscraper and YARG (``isNaturalHopo``). The one
difference in ``.mid``: a note inside the previous chord is not a natural HOPO there, which only
matters when reading a human reference.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from chartgen.core.model import ChartNote

_THRESHOLD_TICKS = 65
_THRESHOLD_RESOLUTION = 192


def hopo_threshold(resolution: int) -> int:
    """Return the largest distance in ticks at which a note still becomes a natural HOPO."""
    return _THRESHOLD_TICKS * resolution // _THRESHOLD_RESOLUTION


def natural_hopo_ticks(
    positions: Sequence[tuple[int, Sequence[int]]],
    resolution: int,
    midi_subset_exception: bool = False,
) -> set[int]:
    """Return the ticks of the natural HOPOs among ``(tick, lanes)`` positions sorted by tick."""
    threshold = hopo_threshold(resolution)
    found: set[int] = set()
    for (before, previous), (tick, lanes) in zip(positions, positions[1:]):
        if len(lanes) != 1 or tick - before > threshold:
            continue
        if len(previous) == 1:
            if lanes[0] != previous[0]:
                found.add(tick)
        elif not (midi_subset_exception and lanes[0] in previous):
            found.add(tick)
    return found


def positions_of(notes: Iterable[ChartNote]) -> list[tuple[int, tuple[int, ...]]]:
    """Group gems into ``(tick, lanes)`` positions sorted by tick."""
    by_tick: dict[int, list[int]] = {}
    for note in notes:
        by_tick.setdefault(note.tick, []).append(note.lane)
    return [(tick, tuple(sorted(by_tick[tick]))) for tick in sorted(by_tick)]
