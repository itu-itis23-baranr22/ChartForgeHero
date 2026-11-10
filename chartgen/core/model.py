"""Format-independent chart representation.

Nothing here knows about Clone Hero's file formats. Exporters translate these
objects into a concrete format, so a new output format needs no changes here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from chartgen.core.timing import TempoMap

LANE_COUNT = 5
"""Lanes 0-4 are the five frets (or the kick and four drum pads)."""

OPEN_LANE = 5
"""Lane value of an open note, played without fretting."""

CYMBAL_LANES = frozenset({2, 3, 4})
"""On drums, the pads that can be a cymbal: yellow, blue and green. Red is always the snare."""


class Instrument(str, Enum):
    GUITAR = "guitar"
    BASS = "bass"
    DRUMS = "drums"
    KEYS = "keys"


class Difficulty(str, Enum):
    EXPERT = "expert"
    HARD = "hard"
    MEDIUM = "medium"
    EASY = "easy"


@dataclass(frozen=True, slots=True, order=True)
class ChartNote:
    """One gem. A chord is several notes that share a tick.

    ``cymbal`` is for drums only: it makes yellow, blue or green a cymbal instead of a tom.
    """

    tick: int
    lane: int
    length: int = 0
    forced: bool = False
    tap: bool = False
    cymbal: bool = False

    def __post_init__(self) -> None:
        if self.tick < 0:
            raise ValueError(f"note tick must be >= 0, got {self.tick}")
        if self.length < 0:
            raise ValueError(f"note length must be >= 0, got {self.length}")
        if not 0 <= self.lane <= OPEN_LANE:
            raise ValueError(f"note lane must be in 0..{OPEN_LANE}, got {self.lane}")
        if self.cymbal and self.lane not in CYMBAL_LANES:
            raise ValueError(f"only lanes 2-4 can be a cymbal, got lane {self.lane}")


@dataclass(frozen=True, slots=True)
class StarPowerPhrase:
    tick: int
    length: int

    def __post_init__(self) -> None:
        if self.tick < 0 or self.length <= 0:
            raise ValueError(f"invalid star power phrase: {self.tick}, {self.length}")


@dataclass(frozen=True, slots=True)
class Section:
    """A named part of the song, such as a chorus."""

    tick: int
    name: str

    def __post_init__(self) -> None:
        if self.tick < 0:
            raise ValueError(f"section tick must be >= 0, got {self.tick}")
        if not self.name.strip():
            raise ValueError("section name must not be blank")


@dataclass(slots=True)
class Track:
    """All notes of one instrument at one difficulty, kept sorted by tick."""

    instrument: Instrument
    difficulty: Difficulty
    notes: list[ChartNote] = field(default_factory=list)
    star_power: list[StarPowerPhrase] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.notes = sorted(self.notes)
        seen: set[tuple[int, int]] = set()
        for note in self.notes:
            key = (note.tick, note.lane)
            if key in seen:
                raise ValueError(f"duplicate note at tick {note.tick}, lane {note.lane}")
            seen.add(key)
        self.star_power = sorted(self.star_power, key=lambda phrase: phrase.tick)


@dataclass(frozen=True, slots=True)
class SongMetadata:
    """Song information. ``name`` and ``artist`` are mandatory: Clone Hero rejects
    a song that lacks either of them."""

    name: str
    artist: str
    album: str = ""
    genre: str = ""
    year: str = ""
    charter: str = "chartgen"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("song name must not be blank")
        if not self.artist.strip():
            raise ValueError("artist must not be blank")


@dataclass(slots=True)
class Chart:
    """A whole song: metadata, one shared tempo map and any number of tracks."""

    metadata: SongMetadata
    tempo_map: TempoMap
    tracks: list[Track] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)

    def __post_init__(self) -> None:
        seen: set[tuple[Instrument, Difficulty]] = set()
        for track in self.tracks:
            self._check_unique(track, seen)
            seen.add((track.instrument, track.difficulty))
        self.sections = sorted(self.sections, key=lambda section: section.tick)

    def add_track(self, track: Track) -> None:
        self._check_unique(track, {(t.instrument, t.difficulty) for t in self.tracks})
        self.tracks.append(track)

    def instruments(self) -> set[Instrument]:
        """Return the instruments that have at least one note."""
        return {track.instrument for track in self.tracks if track.notes}

    @staticmethod
    def _check_unique(track: Track, seen: set[tuple[Instrument, Difficulty]]) -> None:
        if (track.instrument, track.difficulty) in seen:
            raise ValueError(
                f"duplicate track: {track.instrument.value}/{track.difficulty.value}"
            )
