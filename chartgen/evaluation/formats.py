"""Just enough reading of ``.sng`` containers and MIDI charts to use them as references."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from chartgen.errors import ChartgenError

_SNG_MAGIC = b"SNGPKG"


class ReferenceFormatError(ChartgenError):
    """A reference file is damaged or not in the expected format."""


@dataclass(frozen=True)
class SngFile:
    """An opened ``.sng``: metadata plus file contents read on demand."""

    path: Path
    metadata: dict[str, str]
    entries: dict[str, tuple[int, int]]
    mask: bytes

    def read(self, name: str) -> bytes:
        size, start = self.entries[name]
        with self.path.open("rb") as stream:
            stream.seek(start)
            data = np.frombuffer(stream.read(size), dtype=np.uint8)
        if data.size != size:
            raise ReferenceFormatError(f"{self.path.name}: {name} is truncated")
        key = np.frombuffer(self.mask, dtype=np.uint8)
        index = np.arange(size, dtype=np.uint64)
        pattern = key[(index % 16).astype(np.int64)] ^ (index & 0xFF).astype(np.uint8)
        return (data ^ pattern).tobytes()


def open_sng(path: Path) -> SngFile:
    """Read the header of a ``.sng`` container.

    Raises:
        ReferenceFormatError: If the file is not a readable container. A copy that was once
            saved as text is a common cause: it grows and its header no longer parses.
    """
    raw = path.read_bytes()
    try:
        if raw[:6] != _SNG_MAGIC:
            raise ReferenceFormatError(f"{path.name} is not an SNG file")
        mask = raw[10:26]
        position = 26
        position += 8
        count = struct.unpack_from("<Q", raw, position)[0]
        position += 8
        metadata: dict[str, str] = {}
        for _ in range(count):
            size = struct.unpack_from("<i", raw, position)[0]
            position += 4
            key = raw[position : position + size].decode("utf-8")
            position += size
            size = struct.unpack_from("<i", raw, position)[0]
            position += 4
            metadata[key] = raw[position : position + size].decode("utf-8")
            position += size
        position += 8
        count = struct.unpack_from("<Q", raw, position)[0]
        position += 8
        entries: dict[str, tuple[int, int]] = {}
        for _ in range(count):
            size = raw[position]
            position += 1
            # Only the file name: a path in here must never reach outside anything.
            name = Path(raw[position : position + size].decode("utf-8")).name
            position += size
            length, start = struct.unpack_from("<QQ", raw, position)
            position += 16
            if start + length > len(raw):
                raise ReferenceFormatError(f"{path.name}: {name} lies past the end of the file")
            entries[name] = (length, start)
    except (struct.error, UnicodeDecodeError, IndexError) as error:
        raise ReferenceFormatError(f"{path.name} has a damaged header: {error}") from error
    return SngFile(path, metadata, entries, mask)


@dataclass
class MidiTrack:
    name: str = ""
    notes: list[tuple[int, int, int]] = field(default_factory=list)
    """Start tick, note number, length in ticks."""
    texts: list[tuple[int, str]] = field(default_factory=list)
    """Tick and text of each text event, such as a drum mix event."""


@dataclass
class MidiChart:
    division: int
    tempos: list[tuple[int, int]]
    """Tick and microseconds per quarter note."""
    signatures: list[tuple[int, int, int]]
    """Tick, numerator, denominator."""
    tracks: dict[str, MidiTrack]


def _variable_length(data: bytes, position: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[position]
        position += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, position


def parse_midi(data: bytes) -> MidiChart:
    """Read tempo, time signatures and notes of a standard MIDI file.

    Raises:
        ReferenceFormatError: If the data is not a readable MIDI file.
    """
    if data[:4] != b"MThd":
        raise ReferenceFormatError("not a MIDI file")
    try:
        division = struct.unpack(">H", data[12:14])[0]
        chart = MidiChart(division, [], [], {})
        position = 8 + struct.unpack(">I", data[4:8])[0]
        while position < len(data):
            if data[position : position + 4] != b"MTrk":
                raise ReferenceFormatError("expected a track header")
            length = struct.unpack(">I", data[position + 4 : position + 8])[0]
            cursor = position + 8
            end = cursor + length
            track = MidiTrack()
            active: dict[int, int] = {}
            tick = 0
            status = 0
            while cursor < end:
                delta, cursor = _variable_length(data, cursor)
                tick += delta
                byte = data[cursor]
                if byte == 0xFF:
                    kind = data[cursor + 1]
                    size, start = _variable_length(data, cursor + 2)
                    payload = data[start : start + size]
                    if kind == 0x03:
                        track.name = payload.decode("latin-1")
                    elif kind == 0x01:
                        track.texts.append((tick, payload.decode("latin-1")))
                    elif kind == 0x51 and size == 3:
                        chart.tempos.append((tick, int.from_bytes(payload, "big")))
                    elif kind == 0x58 and size >= 2:
                        chart.signatures.append((tick, payload[0], 2 ** payload[1]))
                    cursor = start + size
                elif byte in (0xF0, 0xF7):
                    size, start = _variable_length(data, cursor + 1)
                    cursor = start + size
                else:
                    if byte & 0x80:
                        status = byte
                        cursor += 1
                    kind = status & 0xF0
                    if kind in (0xC0, 0xD0):
                        cursor += 1
                        continue
                    note, velocity = data[cursor], data[cursor + 1]
                    cursor += 2
                    if kind == 0x90 and velocity > 0:
                        active[note] = tick
                    elif kind in (0x80, 0x90) and note in active:
                        begin = active.pop(note)
                        track.notes.append((begin, note, tick - begin))
            if track.name:
                chart.tracks[track.name] = track
            position = end
    except (IndexError, struct.error) as error:
        raise ReferenceFormatError(f"damaged MIDI data: {error}") from error
    chart.tempos.sort()
    chart.signatures.sort()
    if not chart.tempos:
        raise ReferenceFormatError("the MIDI file has no tempo events")
    return chart
