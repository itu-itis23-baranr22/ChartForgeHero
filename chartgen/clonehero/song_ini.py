"""Writer for ``song.ini``, the file Clone Hero reads song metadata from."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from chartgen.core.model import Instrument, SongMetadata

DIFFICULTY_KEYS: dict[Instrument, str] = {
    Instrument.GUITAR: "diff_guitar",
    Instrument.BASS: "diff_bass",
    Instrument.DRUMS: "diff_drums",
    Instrument.KEYS: "diff_keys",
}
NOT_CHARTED = -1
"""``diff_*`` value that tells Clone Hero an instrument has no chart."""
PRO_DRUMS = "pro_drums"
"""Every drum chart here is 4-lane Pro. The tag tells the game so instead of letting it guess from the
notes; ``five_lane_drums`` is never written (SPEC decision 2)."""

_TIER_NOTES_PER_SECOND = (1.0, 2.0, 3.0, 4.0, 5.5, 7.5)


def difficulty_tier(note_count: int, duration_s: float) -> int:
    """Estimate the 0-6 difficulty shown in the song list from note density."""
    if duration_s <= 0:
        raise ValueError(f"duration must be > 0, got {duration_s}")
    density = note_count / duration_s
    return sum(density >= limit for limit in _TIER_NOTES_PER_SECOND)


@dataclass(frozen=True)
class SongIni:
    metadata: SongMetadata
    song_length_ms: int
    preview_start_ms: int = 0
    delay_ms: int = 0
    difficulties: Mapping[Instrument, int] = field(default_factory=dict)


def _value(value: object) -> str:
    return " ".join(str(value).split())


def render_song_ini(ini: SongIni) -> str:
    """Render the file. Instruments missing from ``difficulties`` get ``diff_* = -1``.

    A song with a drum chart also gets ``pro_drums = True``; a song without one is unchanged.
    """
    meta = ini.metadata
    entries: list[tuple[str, object]] = [
        ("name", meta.name),
        ("artist", meta.artist),
        ("album", meta.album),
        ("genre", meta.genre),
        ("year", meta.year),
        ("charter", meta.charter),
        ("song_length", ini.song_length_ms),
        ("preview_start_time", ini.preview_start_ms),
        ("delay", ini.delay_ms),
    ]
    entries.extend(
        (key, ini.difficulties.get(instrument, NOT_CHARTED))
        for instrument, key in DIFFICULTY_KEYS.items()
    )
    if ini.difficulties.get(Instrument.DRUMS, NOT_CHARTED) != NOT_CHARTED:
        entries.append((PRO_DRUMS, "True"))
    body = "\n".join(f"{key} = {_value(value)}" for key, value in entries)
    return f"[song]\n{body}\n"
