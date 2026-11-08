"""Loading reference songs: any ``.sng``, or folder with a chart and audio, under a directory."""

from __future__ import annotations

import configparser
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import soundfile as sf

from chartgen.audio.io import AudioData
from chartgen.chart.hopo import natural_hopo_ticks
from chartgen.clonehero.validate import ParsedEvent, ValidationReport, parse_chart
from chartgen.core.model import Difficulty
from chartgen.errors import ChartgenError
from chartgen.evaluation.formats import MidiChart, SngFile, open_sng, parse_midi

SPLIT_TRAIN = "train"
SPLIT_TEST = "test"
SPLIT_UNASSIGNED = "unassigned"

AUDIO_SUFFIXES = frozenset({".opus", ".ogg", ".mp3", ".wav", ".flac"})
_NOT_THE_SONG = frozenset({"preview", "crowd"})
_MIDI_BASE = {
    Difficulty.EXPERT: 96,
    Difficulty.HARD: 84,
    Difficulty.MEDIUM: 72,
    Difficulty.EASY: 60,
}
_MIDI_FORCE_HOPO = 5
_MIDI_FORCE_STRUM = 6
"""Above each level's green, these notes mark a span in which notes are forced."""
_MAIN_TRACK = "PART GUITAR"
_CHART_SECTIONS = {
    Difficulty.EXPERT: "ExpertSingle",
    Difficulty.HARD: "HardSingle",
    Difficulty.MEDIUM: "MediumSingle",
    Difficulty.EASY: "EasySingle",
}
_CHART_FORCE = 5
_PEAK = 0.95


@dataclass(frozen=True)
class ReferenceNote:
    time_s: float
    lanes: tuple[int, ...]
    length_s: float
    tick: int = 0
    length_ticks: int = 0
    hopo: bool = False
    """Whether the game plays this note as a HOPO, force markers included."""


@dataclass(frozen=True)
class ReferenceSong:
    name: str
    source: Path
    """The file whose hash identifies this song's stems in the cache."""
    audio: AudioData
    beats: np.ndarray
    bars: np.ndarray
    notes: tuple[ReferenceNote, ...]
    """The Expert notes."""
    signatures: tuple[tuple[int, int], ...]
    resolution: int = 192
    levels: Mapping[Difficulty, tuple[ReferenceNote, ...]] = field(default_factory=dict)
    """The notes of every difficulty the chart has, Expert included."""
    is_midi: bool = False


class _Clock:
    """Converts ticks to seconds for a tempo list given as (tick, seconds per tick)."""

    def __init__(self, tempos: list[tuple[int, float]], delay_s: float) -> None:
        self.ticks = np.array([tick for tick, _ in tempos], dtype=np.float64)
        self.per_tick = np.array([value for _, value in tempos], dtype=np.float64)
        spans = np.diff(self.ticks) * self.per_tick[:-1]
        self.seconds = np.r_[0.0, np.cumsum(spans)]
        self.delay_s = delay_s

    def seconds_at(self, ticks: np.ndarray) -> np.ndarray:
        values = np.asarray(ticks, dtype=np.float64)
        index = np.searchsorted(self.ticks, values, side="right") - 1
        result = self.seconds[index] + (values - self.ticks[index]) * self.per_tick[index]
        return result + self.delay_s

    def tick_at(self, seconds: float) -> float:
        target = seconds - self.delay_s
        index = int(np.searchsorted(self.seconds, target, side="right") - 1)
        return float(self.ticks[index] + (target - self.seconds[index]) / self.per_tick[index])


def _beats_and_bars(
    clock: _Clock,
    resolution: int,
    signatures: list[tuple[int, int, int]],
    duration_s: float,
) -> tuple[np.ndarray, np.ndarray]:
    last = clock.tick_at(duration_s)
    beats = clock.seconds_at(np.arange(0, last, resolution, dtype=np.float64))
    bar_ticks: list[float] = []
    plan = signatures or [(0, 4, 4)]
    for number, (tick, numerator, denominator) in enumerate(plan):
        stop = plan[number + 1][0] if number + 1 < len(plan) else last
        bar_ticks.extend(np.arange(tick, stop, resolution * 4 / denominator * numerator))
    bars = clock.seconds_at(np.array(bar_ticks, dtype=np.float64))
    return beats[beats >= 0], bars[bars >= 0]


def _group_notes(
    gems: Iterable[tuple[int, int, int]], clock: _Clock
) -> tuple[ReferenceNote, ...]:
    by_tick: dict[int, list[tuple[int, int]]] = {}
    for tick, lane, length in gems:
        by_tick.setdefault(tick, []).append((lane, length))
    notes = []
    for tick in sorted(by_tick):
        members = by_tick[tick]
        start = float(clock.seconds_at(np.array([float(tick)]))[0])
        longest = max(length for _, length in members)
        end = float(clock.seconds_at(np.array([float(tick + longest)]))[0])
        lanes = tuple(sorted(lane for lane, _ in members))
        notes.append(ReferenceNote(start, lanes, end - start, tick, longest))
    return tuple(notes)


def _midi_level(
    midi: MidiChart, clock: _Clock, level: Difficulty, division: int
) -> tuple[ReferenceNote, ...]:
    """Read one difficulty of the main track, with its force markers applied."""
    base = _MIDI_BASE[level]
    track = midi.tracks[_MAIN_TRACK].notes
    notes = _group_notes(
        ((tick, note - base, length) for tick, note, length in track if base <= note <= base + 4),
        clock,
    )
    natural = natural_hopo_ticks(
        [(note.tick, note.lanes) for note in notes], division, midi_subset_exception=True
    )
    spans = {
        marker: [(tick, tick + length) for tick, note, length in track if note == base + marker]
        for marker in (_MIDI_FORCE_HOPO, _MIDI_FORCE_STRUM)
    }

    def inside(tick: int, marker: int) -> bool:
        return any(start <= tick < end for start, end in spans[marker])

    return tuple(
        replace(
            note,
            hopo=(note.tick in natural or inside(note.tick, _MIDI_FORCE_HOPO))
            and not inside(note.tick, _MIDI_FORCE_STRUM),
        )
        for note in notes
    )


def _mix(sources: list[tuple[np.ndarray, int]]) -> AudioData:
    if not sources:
        raise ChartgenError("a reference song has no audio")
    rate = sources[0][1]
    frames = max(samples.shape[0] for samples, _ in sources)
    mix = np.zeros((frames, 2), dtype=np.float32)
    for samples, source_rate in sources:
        if source_rate != rate:
            raise ChartgenError("a reference song mixes sample rates")
        stereo = samples if samples.shape[1] >= 2 else np.repeat(samples, 2, axis=1)
        mix[: samples.shape[0]] += stereo[:, :2]
    peak = float(np.abs(mix).max())
    if peak > _PEAK:
        mix *= _PEAK / peak
    return AudioData(mix, rate)


def _from_midi(
    name: str, source: Path, audio: AudioData, midi: MidiChart, delay_s: float
) -> ReferenceSong:
    if _MAIN_TRACK not in midi.tracks:
        raise ChartgenError(f"{name}: the chart has no {_MAIN_TRACK} track")
    clock = _Clock(
        [(tick, micros / 1e6 / midi.division) for tick, micros in midi.tempos], delay_s
    )
    beats, bars = _beats_and_bars(clock, midi.division, midi.signatures, audio.duration_s)
    levels = {
        level: notes
        for level in _MIDI_BASE
        if (notes := _midi_level(midi, clock, level, midi.division))
    }
    if Difficulty.EXPERT not in levels:
        raise ChartgenError(f"{name}: the chart has no Expert guitar notes")
    signatures = tuple(sorted({(n, d) for _, n, d in midi.signatures})) or ((4, 4),)
    return ReferenceSong(
        name,
        source,
        audio,
        beats,
        bars,
        levels[Difficulty.EXPERT],
        signatures,
        midi.division,
        levels,
        is_midi=True,
    )


def _chart_level(
    events: list[ParsedEvent], clock: _Clock, resolution: int
) -> tuple[ReferenceNote, ...]:
    """Read one difficulty of a ``.chart``. Its force flag flips what the note would naturally be."""
    gems = []
    flipped: set[int] = set()
    for event in events:
        parts = event.args.split()
        if event.type != "N" or len(parts) != 2:
            continue
        if int(parts[0]) in range(5):
            gems.append((event.tick, int(parts[0]), int(parts[1])))
        elif int(parts[0]) == _CHART_FORCE:
            flipped.add(event.tick)
    notes = _group_notes(gems, clock)
    natural = natural_hopo_ticks([(note.tick, note.lanes) for note in notes], resolution)
    return tuple(
        replace(note, hopo=(note.tick in natural) != (note.tick in flipped)) for note in notes
    )


def _from_chart(
    name: str, source: Path, audio: AudioData, text: str, delay_s: float
) -> ReferenceSong:
    report = ValidationReport()
    parsed = parse_chart(text, report)
    if not parsed.fields.get("Resolution", "").isdigit():
        raise ChartgenError(f"{name}: the chart has no Resolution")
    resolution = int(parsed.fields["Resolution"])
    tempos: list[tuple[int, float]] = []
    signatures: list[tuple[int, int, int]] = []
    for event in parsed.sections.get("SyncTrack", []):
        parts = event.args.split()
        if event.type == "B":
            tempos.append((event.tick, 60.0 / (int(parts[0]) / 1000.0) / resolution))
        elif event.type == "TS":
            exponent = int(parts[1]) if len(parts) > 1 else 2
            signatures.append((event.tick, int(parts[0]), 2**exponent))
    if not tempos:
        raise ChartgenError(f"{name}: the chart has no tempo events")
    clock = _Clock(tempos, delay_s)
    levels = {
        level: notes
        for level, section in _CHART_SECTIONS.items()
        if (notes := _chart_level(parsed.sections.get(section, []), clock, resolution))
    }
    if Difficulty.EXPERT not in levels:
        raise ChartgenError(f"{name}: the chart has no [{_CHART_SECTIONS[Difficulty.EXPERT]}] notes")
    beats, bars = _beats_and_bars(clock, resolution, signatures, audio.duration_s)
    plain = tuple(sorted({(n, d) for _, n, d in signatures})) or ((4, 4),)
    return ReferenceSong(
        name, source, audio, beats, bars, levels[Difficulty.EXPERT], plain, resolution, levels
    )


def _is_song_audio(file_name: str) -> bool:
    path = Path(file_name)
    return path.suffix.lower() in AUDIO_SUFFIXES and path.stem.lower() not in _NOT_THE_SONG


def _load_sng(path: Path) -> ReferenceSong:
    container: SngFile = open_sng(path)
    delay_s = float(container.metadata.get("delay") or 0.0) / 1000.0
    sources = []
    with tempfile.TemporaryDirectory(prefix="chartgen-reference-") as folder:
        for name in container.entries:
            if _is_song_audio(name):
                target = Path(folder) / name
                target.write_bytes(container.read(name))
                samples, rate = sf.read(str(target), dtype="float32", always_2d=True)
                sources.append((samples, rate))
    audio = _mix(sources)
    if "notes.mid" in container.entries:
        midi = parse_midi(container.read("notes.mid"))
        return _from_midi(path.stem, path, audio, midi, delay_s)
    if "notes.chart" in container.entries:
        text = container.read("notes.chart").decode("utf-8-sig")
        return _from_chart(path.stem, path, audio, text, delay_s)
    raise ChartgenError(f"{path.name} holds no chart")


def _song_ini_delay(folder: Path) -> float:
    path = folder / "song.ini"
    if not path.is_file():
        return 0.0
    parser = configparser.ConfigParser(
        delimiters=("=",), comment_prefixes=(), interpolation=None, strict=False
    )
    try:
        parser.read_string(path.read_text(encoding="utf-8-sig"))
        return parser.getfloat("song", "delay", fallback=0.0) / 1000.0
    except (configparser.Error, UnicodeDecodeError, ValueError):
        return 0.0


def _load_folder(folder: Path) -> ReferenceSong:
    sources = []
    for path in sorted(folder.iterdir()):
        if path.is_file() and _is_song_audio(path.name):
            samples, rate = sf.read(str(path), dtype="float32", always_2d=True)
            sources.append((samples, rate))
    audio = _mix(sources)
    delay_s = _song_ini_delay(folder)
    identity = folder / "notes.mid" if (folder / "notes.mid").is_file() else folder / "notes.chart"
    if identity.name == "notes.mid":
        return _from_midi(folder.name, identity, audio, parse_midi(identity.read_bytes()), delay_s)
    return _from_chart(folder.name, identity, audio, identity.read_text(encoding="utf-8-sig"), delay_s)


def find_references(root: Path) -> list[Path]:
    """Return every ``.sng`` and every folder with a chart under ``root``, sorted."""
    found: set[Path] = set()
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() == ".sng":
            found.add(path)
        elif path.is_file() and path.name in {"notes.mid", "notes.chart"}:
            found.add(path.parent)
    return sorted(found)


def split_of(path: Path, root: Path) -> str:
    """Return which split a reference belongs to, from the folder directly under ``root``."""
    parts = path.relative_to(root).parts
    first = parts[0].lower() if len(parts) > 1 else ""
    return first if first in {SPLIT_TRAIN, SPLIT_TEST} else SPLIT_UNASSIGNED


def load_reference(path: Path) -> ReferenceSong:
    """Load one result of :func:`find_references`.

    Raises:
        ChartgenError: If the reference cannot be used.
    """
    return _load_sng(path) if path.is_file() else _load_folder(path)
