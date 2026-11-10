"""Drum gems of a 4-lane Pro chart, and the kit pieces that become them.

Format independent: a gem is a lane and whether that lane is played as a cymbal. How a cymbal is
written is the exporter's business. The layout is 4-lane Pro (SPEC decisions 2 and 32): the kick,
then red, yellow, blue and green pads. Red is the snare and is always a drum; yellow, blue and green
are each a tom or a cymbal. Nothing here is 5-lane.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType

from chartgen.core.model import ChartNote

KICK_LANE = 0
RED_LANE = 1
PAD_LANES = frozenset({1, 2, 3, 4})
"""Everything a hand plays. The kick is the foot."""

LANE_NAMES: Mapping[int, str] = MappingProxyType(
    {0: "kick", 1: "red", 2: "yellow", 3: "blue", 4: "green"}
)


class DrumGem(str, Enum):
    """One gem the player hits: a lane, and for yellow, blue and green whether it is a cymbal."""

    KICK = "kick"
    RED = "red"
    YELLOW_TOM = "yellow_tom"
    BLUE_TOM = "blue_tom"
    GREEN_TOM = "green_tom"
    YELLOW_CYMBAL = "yellow_cymbal"
    BLUE_CYMBAL = "blue_cymbal"
    GREEN_CYMBAL = "green_cymbal"

    @property
    def lane(self) -> int:
        return _LANE_OF[self]

    @property
    def cymbal(self) -> bool:
        return self in _CYMBALS

    @property
    def is_pad(self) -> bool:
        """Whether a hand plays it, which is everything but the kick."""
        return self is not DrumGem.KICK

    def note(self, tick: int) -> ChartNote:
        """Return this gem as a note at ``tick``. Drum notes have no length and no flags."""
        return ChartNote(tick, self.lane, cymbal=self.cymbal)

    @classmethod
    def of(cls, lane: int, cymbal: bool = False) -> DrumGem:
        """Return the gem of ``lane``.

        Raises:
            ValueError: If the lane is not 0-4, or a cymbal is asked of the kick or of red.
        """
        try:
            return _GEM_AT[(lane, cymbal)]
        except KeyError:
            if lane in LANE_NAMES:
                raise ValueError(f"{LANE_NAMES[lane]} cannot be a cymbal") from None
            raise ValueError(f"drum lane must be in 0..4, got {lane}") from None

    @classmethod
    def of_note(cls, note: ChartNote) -> DrumGem:
        """Return the gem a drum note stands for.

        Raises:
            ValueError: If the note has a length or a force or tap flag, none of which a drum note may have.
        """
        if note.length or note.forced or note.tap:
            raise ValueError(f"tick {note.tick}: a drum note has no sustain, force or tap")
        return cls.of(note.lane, note.cymbal)


_LANE_OF: Mapping[DrumGem, int] = MappingProxyType(
    {
        DrumGem.KICK: 0,
        DrumGem.RED: 1,
        DrumGem.YELLOW_TOM: 2,
        DrumGem.BLUE_TOM: 3,
        DrumGem.GREEN_TOM: 4,
        DrumGem.YELLOW_CYMBAL: 2,
        DrumGem.BLUE_CYMBAL: 3,
        DrumGem.GREEN_CYMBAL: 4,
    }
)
_CYMBALS = frozenset({DrumGem.YELLOW_CYMBAL, DrumGem.BLUE_CYMBAL, DrumGem.GREEN_CYMBAL})
_GEM_AT: Mapping[tuple[int, bool], DrumGem] = MappingProxyType(
    {(gem.lane, gem.cymbal): gem for gem in DrumGem}
)


class DrumPiece(str, Enum):
    """A part of the kit, as a classifier hears it."""

    KICK = "kick"
    SNARE = "snare"
    HI_HAT = "hi_hat"
    RIDE = "ride"
    CRASH = "crash"
    HIGH_TOM = "high_tom"
    MID_TOM = "mid_tom"
    FLOOR_TOM = "floor_tom"


GEM_FOR_PIECE: Mapping[DrumPiece, DrumGem] = MappingProxyType(
    {
        DrumPiece.KICK: DrumGem.KICK,
        DrumPiece.SNARE: DrumGem.RED,
        DrumPiece.HI_HAT: DrumGem.YELLOW_CYMBAL,
        DrumPiece.RIDE: DrumGem.BLUE_CYMBAL,
        DrumPiece.CRASH: DrumGem.GREEN_CYMBAL,
        DrumPiece.HIGH_TOM: DrumGem.YELLOW_TOM,
        DrumPiece.MID_TOM: DrumGem.BLUE_TOM,
        DrumPiece.FLOOR_TOM: DrumGem.GREEN_TOM,
    }
)
"""The approved layout: hi-hat yellow, ride blue, crash green, toms high to low on the same pads."""
