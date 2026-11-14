"""Loading reference songs: any ``.sng``, or folder with a chart and audio, under a directory."""

from __future__ import annotations

import configparser
import re
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import soundfile as sf

from chartgen.audio.io import AudioData, analysis_mono
from chartgen.chart.hopo import natural_hopo_ticks
from chartgen.clonehero.validate import ParsedChart, ParsedEvent, ValidationReport, parse_chart
from chartgen.core.drums import DrumGem
from chartgen.core.model import CYMBAL_LANES, Difficulty, Instrument
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
_BASS_TRACK = "PART BASS"
_KEYS_TRACK = "PART KEYS"
_CHART_SECTIONS = {
    Difficulty.EXPERT: "ExpertSingle",
    Difficulty.HARD: "HardSingle",
    Difficulty.MEDIUM: "MediumSingle",
    Difficulty.EASY: "EasySingle",
}
_BASS_CHART_SECTIONS = {
    Difficulty.EXPERT: "ExpertDoubleBass",
    Difficulty.HARD: "HardDoubleBass",
    Difficulty.MEDIUM: "MediumDoubleBass",
    Difficulty.EASY: "EasyDoubleBass",
}
_KEYS_CHART_SECTIONS = {
    Difficulty.EXPERT: "ExpertKeyboard",
    Difficulty.HARD: "HardKeyboard",
    Difficulty.MEDIUM: "MediumKeyboard",
    Difficulty.EASY: "EasyKeyboard",
}
_CHART_FORCE = 5
_PEAK = 0.95

_DRUM_TRACK = "PART DRUMS"
_MIDI_DRUM_BASE = {
    Difficulty.EXPERT: 96,
    Difficulty.HARD: 84,
    Difficulty.MEDIUM: 72,
    Difficulty.EASY: 60,
}
"""Each level's kick. Red, yellow, blue and green follow it, and one above green is 5-lane green."""
_MIDI_DOUBLE_KICK = 95
_MIDI_TOM_MARKERS = {110: 2, 111: 3, 112: 4}
_DISCO_FLIP = re.compile(r"\[mix\s+\d+\s+drums\d+d\]")
"""A mix event whose flag is ``d`` alone. ``dnoflip`` leaves Pro notes as they are."""
_DRUM_CHART_SECTIONS = {
    Difficulty.EXPERT: "ExpertDrums",
    Difficulty.HARD: "HardDrums",
    Difficulty.MEDIUM: "MediumDrums",
    Difficulty.EASY: "EasyDrums",
}
_CHART_DOUBLE_KICK = 32
_CHART_FIVE_LANE_GREEN = 5
_CHART_CYMBAL_FLAGS = {66: 2, 67: 3, 68: 4}
_TRUE_TAGS = frozenset({"true", "1"})
_FIVE_LANE = "5-lane drums, which this project does not chart"

_EVENTS_TRACK = "EVENTS"
_MIDI_SECTION = re.compile(r"^\[(?:section[ _]+|prc_)(.+?)\]$")
"""``[section verse 1]`` in older charts, ``[prc_verse_1]`` in Rock Band 3's."""
_CHART_SECTION = re.compile(r'^"?section (.+?)"?$')
_STAR_POWER_NOTE = 116
"""In a MIDI track, a star power phrase spans every difficulty at once."""
_CHART_STAR_POWER = "2"
"""``tick = S 2 length`` in one difficulty of a ``.chart``."""
_STAR_POWER_TRACKS = {
    Instrument.GUITAR: _MAIN_TRACK,
    Instrument.BASS: _BASS_TRACK,
    Instrument.KEYS: _KEYS_TRACK,
    Instrument.DRUMS: _DRUM_TRACK,
}
_STAR_POWER_CHART_SECTIONS = {
    Instrument.GUITAR: _CHART_SECTIONS[Difficulty.EXPERT],
    Instrument.BASS: _BASS_CHART_SECTIONS[Difficulty.EXPERT],
    Instrument.KEYS: _KEYS_CHART_SECTIONS[Difficulty.EXPERT],
    Instrument.DRUMS: _DRUM_CHART_SECTIONS[Difficulty.EXPERT],
}
"""A ``.chart`` may give each level its own phrases; Expert's are the ones read."""


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
class ReferenceDrumHit:
    """One position of a human drum chart: every gem hit at one tick."""

    time_s: float
    tick: int
    gems: tuple[DrumGem, ...]
    """Ordered by lane, the kick first."""


@dataclass(frozen=True)
class ReferenceDrums:
    """The drums of a human chart, read the way the game reads them."""

    levels: Mapping[Difficulty, tuple[ReferenceDrumHit, ...]] = field(default_factory=dict)
    pro: bool = False
    """Whether cymbals are told apart from toms. If not, every pad reads as a tom."""
    double_kicks: int = 0
    """Expert+ kicks. They are not part of Expert, so they are left out of it."""
    skipped: str = ""
    """Why there are no levels, when there are none."""


@dataclass(frozen=True)
class ReferenceSection:
    """Where a human-marked section of the song starts, and its name as written."""

    time_s: float
    tick: int
    name: str


@dataclass(frozen=True)
class ReferencePhrase:
    """A star power phrase of a human chart."""

    start_s: float
    end_s: float
    tick: int
    length_ticks: int


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
    bass_levels: Mapping[Difficulty, tuple[ReferenceNote, ...]] = field(default_factory=dict)
    """The same for bass. Empty if the chart has none."""
    keys_levels: Mapping[Difficulty, tuple[ReferenceNote, ...]] = field(default_factory=dict)
    """The same for keys. Empty if the chart has none."""
    drums: ReferenceDrums = field(default_factory=ReferenceDrums)
    """The drums, with no levels and a reason if the chart has none that can be read."""
    sections: tuple[ReferenceSection, ...] = ()
    """The sections the human marked, in order. Empty if the chart has none."""
    star_power: Mapping[Instrument, tuple[ReferencePhrase, ...]] = field(default_factory=dict)
    """The star power phrases of each instrument that has any."""
    preview_start_s: float | None = None
    """Where the song list's preview starts, from ``preview_start_time``. None if it is not set."""


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
    midi: MidiChart, clock: _Clock, level: Difficulty, division: int, track_name: str = _MAIN_TRACK
) -> tuple[ReferenceNote, ...]:
    """Read one difficulty of a track, with its force markers applied."""
    base = _MIDI_BASE[level]
    track = midi.tracks[track_name].notes
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


def _mix(paths: Sequence[Path]) -> AudioData:
    """Mix a reference's audio files into one stereo song, reading one file at a time.

    A ``.sng`` holds up to eight stems of five minutes, about 125 MB each once decoded: decoding them
    all before mixing took a gigabyte. The additions are the same, in the same order.
    """
    if not paths:
        raise ChartgenError("a reference song has no audio")
    infos = [sf.info(str(path)) for path in paths]
    rate = infos[0].samplerate
    if any(info.samplerate != rate for info in infos):
        raise ChartgenError("a reference song mixes sample rates")
    mix = np.zeros((max(info.frames for info in infos), 2), dtype=np.float32)
    longest = 0
    for path in paths:
        samples, _ = sf.read(str(path), dtype="float32", always_2d=True)
        frames = samples.shape[0]
        if frames > mix.shape[0]:  # a header that counts short: the decoded length is what counts
            mix = np.concatenate([mix, np.zeros((frames - mix.shape[0], 2), dtype=np.float32)])
        stereo = samples if samples.shape[1] >= 2 else np.repeat(samples, 2, axis=1)
        mix[:frames] += stereo[:, :2]
        longest = max(longest, frames)
        del samples, stereo
    if longest < mix.shape[0]:
        mix = np.ascontiguousarray(mix[:longest])
    peak = float(np.abs(mix).max())
    if peak > _PEAK:
        mix *= _PEAK / peak
    return AudioData(mix, rate)


def _is_true(tags: Mapping[str, str], key: str) -> bool:
    return str(tags.get(key, "")).strip().lower() in _TRUE_TAGS


def _drum_hits(gems: Iterable[tuple[int, DrumGem]], clock: _Clock) -> tuple[ReferenceDrumHit, ...]:
    by_tick: dict[int, set[DrumGem]] = {}
    for tick, gem in gems:
        by_tick.setdefault(tick, set()).add(gem)
    ticks = sorted(by_tick)
    times = clock.seconds_at(np.array(ticks, dtype=np.float64))
    return tuple(
        ReferenceDrumHit(
            float(time_s), tick, tuple(sorted(by_tick[tick], key=lambda gem: (gem.lane, gem.cymbal)))
        )
        for tick, time_s in zip(ticks, times)
    )


def _midi_drums(midi: MidiChart, clock: _Clock, tags: Mapping[str, str]) -> ReferenceDrums:
    """Read ``PART DRUMS`` the way the game does: song.ini tags first, then the notes.

    In ``.mid``, yellow, blue and green are cymbals unless a tom marker covers them, and red never is.
    Tom markers alone make a chart Pro. A chart that is not Pro has no cymbals: its pads read as toms.
    5-lane charts and disco flip are left out rather than read wrong; the format describes how a flip
    changes Pro notes too loosely to follow. The format also calls sustained notes 5-lane without saying
    how long, and every MIDI note has a length, so length decides nothing here.
    """
    track = midi.tracks.get(_DRUM_TRACK)
    if track is None:
        return ReferenceDrums(skipped=f"the chart has no {_DRUM_TRACK} track")
    numbers = {number for _, number, _ in track.notes}
    markers = {
        lane: [(start, start + max(length, 1)) for start, number, length in track.notes if number == marker]
        for marker, lane in _MIDI_TOM_MARKERS.items()
    }
    pro = _is_true(tags, "pro_drums") or any(markers.values())
    five_lane_notes = any(base + 5 in numbers for base in _MIDI_DRUM_BASE.values())
    if _is_true(tags, "five_lane_drums") or (five_lane_notes and not pro):
        return ReferenceDrums(skipped=_FIVE_LANE)
    if any(_DISCO_FLIP.fullmatch(text.strip()) for _, text in track.texts):
        return ReferenceDrums(skipped="disco flip, which swaps red and yellow and is not read here")

    def cymbal(lane: int, tick: int) -> bool:
        if not pro or lane not in CYMBAL_LANES:
            return False
        return not any(start <= tick < end for start, end in markers[lane])

    levels = {}
    for level, base in _MIDI_DRUM_BASE.items():
        gems = [
            (tick, DrumGem.of(number - base, cymbal(number - base, tick)))
            for tick, number, _ in track.notes
            if base <= number <= base + 4
        ]
        if gems:
            levels[level] = _drum_hits(gems, clock)
    double_kicks = sum(number == _MIDI_DOUBLE_KICK for _, number, _ in track.notes)
    return ReferenceDrums(levels, pro, double_kicks, "" if levels else "PART DRUMS has no notes")


def _chart_drums(parsed: ParsedChart, clock: _Clock, tags: Mapping[str, str]) -> ReferenceDrums:
    """Read the drum sections of a ``.chart`` the way the game does: song.ini tags first, then the notes.

    In ``.chart`` a pad is a tom unless a cymbal flag on the same tick marks it. Cymbal flags or the
    ``pro_drums`` tag make a chart Pro. Without either, ``N 5`` or a sustained note means 5-lane, which is
    left out.
    """
    notes: list[tuple[Difficulty, int, int, int]] = []
    for level, section in _DRUM_CHART_SECTIONS.items():
        for event in parsed.sections.get(section, []):
            parts = event.args.split()
            if event.type == "N" and len(parts) == 2 and all(part.isdigit() for part in parts):
                notes.append((level, event.tick, int(parts[0]), int(parts[1])))
    if not notes:
        return ReferenceDrums(skipped="the chart has no drum sections")
    flagged = {
        (level, tick, _CHART_CYMBAL_FLAGS[value])
        for level, tick, value, _ in notes
        if value in _CHART_CYMBAL_FLAGS
    }
    pro = _is_true(tags, "pro_drums") or bool(flagged)
    five_lane_notes = any(
        value == _CHART_FIVE_LANE_GREEN or (value <= _CHART_FIVE_LANE_GREEN and length > 0)
        for _, _, value, length in notes
    )
    if _is_true(tags, "five_lane_drums") or (five_lane_notes and not pro):
        return ReferenceDrums(skipped=_FIVE_LANE)
    levels = {}
    for level in _DRUM_CHART_SECTIONS:
        gems = [
            (tick, DrumGem.of(value, pro and (level, tick, value) in flagged))
            for at, tick, value, _ in notes
            if at is level and value in range(5)
        ]
        if gems:
            levels[level] = _drum_hits(gems, clock)
    double_kicks = sum(
        value == _CHART_DOUBLE_KICK for level, _, value, _ in notes if level is Difficulty.EXPERT
    )
    return ReferenceDrums(levels, pro, double_kicks, "" if levels else "the drum sections have no notes")


def _seconds(clock: _Clock, tick: int) -> float:
    return float(clock.seconds_at(np.array([float(tick)]))[0])


def _sections_from(marks: Iterable[tuple[int, str]], clock: _Clock) -> tuple[ReferenceSection, ...]:
    return tuple(
        ReferenceSection(_seconds(clock, tick), tick, name.strip()) for tick, name in sorted(marks, key=lambda mark: mark[0])
    )


def _midi_sections(midi: MidiChart, clock: _Clock) -> tuple[ReferenceSection, ...]:
    track = midi.tracks.get(_EVENTS_TRACK)
    if track is None:
        return ()
    return _sections_from(
        ((tick, match.group(1)) for tick, text in track.texts if (match := _MIDI_SECTION.match(text.strip()))),
        clock,
    )


def _chart_sections(parsed: ParsedChart, clock: _Clock) -> tuple[ReferenceSection, ...]:
    return _sections_from(
        (
            (event.tick, match.group(1))
            for event in parsed.sections.get("Events", [])
            if event.type == "E" and (match := _CHART_SECTION.match(event.args.strip()))
        ),
        clock,
    )


def _phrases(spans: Iterable[tuple[int, int]], clock: _Clock) -> tuple[ReferencePhrase, ...]:
    return tuple(
        ReferencePhrase(_seconds(clock, tick), _seconds(clock, tick + length), tick, length)
        for tick, length in sorted(spans)
    )


def _midi_star_power(midi: MidiChart, clock: _Clock) -> dict[Instrument, tuple[ReferencePhrase, ...]]:
    phrases = {}
    for instrument, track_name in _STAR_POWER_TRACKS.items():
        track = midi.tracks.get(track_name)
        spans = [(start, length) for start, number, length in track.notes if number == _STAR_POWER_NOTE] if track else []
        if spans:
            phrases[instrument] = _phrases(spans, clock)
    return phrases


def _chart_star_power(parsed: ParsedChart, clock: _Clock) -> dict[Instrument, tuple[ReferencePhrase, ...]]:
    phrases = {}
    for instrument, section in _STAR_POWER_CHART_SECTIONS.items():
        spans = []
        for event in parsed.sections.get(section, []):
            parts = event.args.split()
            if event.type == "S" and len(parts) == 2 and parts[0] == _CHART_STAR_POWER and parts[1].isdigit():
                spans.append((event.tick, int(parts[1])))
        if spans:
            phrases[instrument] = _phrases(spans, clock)
    return phrases


def _preview_start(tags: Mapping[str, str]) -> float | None:
    """``preview_start_time`` in seconds. A missing, negative or unreadable value means none is set."""
    try:
        value = float(str(tags.get("preview_start_time", "")).strip())
    except ValueError:
        return None
    return value / 1000.0 if value >= 0 else None


def _from_midi(
    name: str,
    source: Path,
    audio: AudioData,
    midi: MidiChart,
    delay_s: float,
    tags: Mapping[str, str] | None = None,
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
    bass_levels, keys_levels = (
        {
            level: notes
            for level in _MIDI_BASE
            if track_name in midi.tracks
            and (notes := _midi_level(midi, clock, level, midi.division, track_name))
        }
        for track_name in (_BASS_TRACK, _KEYS_TRACK)
    )
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
        bass_levels=bass_levels,
        keys_levels=keys_levels,
        drums=_midi_drums(midi, clock, tags or {}),
        sections=_midi_sections(midi, clock),
        star_power=_midi_star_power(midi, clock),
        preview_start_s=_preview_start(tags or {}),
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
    name: str,
    source: Path,
    audio: AudioData,
    text: str,
    delay_s: float,
    tags: Mapping[str, str] | None = None,
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
    bass_levels, keys_levels = (
        {
            level: notes
            for level, section in sections.items()
            if (notes := _chart_level(parsed.sections.get(section, []), clock, resolution))
        }
        for sections in (_BASS_CHART_SECTIONS, _KEYS_CHART_SECTIONS)
    )
    beats, bars = _beats_and_bars(clock, resolution, signatures, audio.duration_s)
    plain = tuple(sorted({(n, d) for _, n, d in signatures})) or ((4, 4),)
    return ReferenceSong(
        name,
        source,
        audio,
        beats,
        bars,
        levels[Difficulty.EXPERT],
        plain,
        resolution,
        levels,
        bass_levels=bass_levels,
        keys_levels=keys_levels,
        drums=_chart_drums(parsed, clock, tags or {}),
        sections=_chart_sections(parsed, clock),
        star_power=_chart_star_power(parsed, clock),
        preview_start_s=_preview_start(tags or {}),
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
                sources.append(target)
        audio = _mix(sources)
    tags = container.metadata
    if "notes.mid" in container.entries:
        midi = parse_midi(container.read("notes.mid"))
        return _from_midi(path.stem, path, audio, midi, delay_s, tags)
    if "notes.chart" in container.entries:
        text = container.read("notes.chart").decode("utf-8-sig")
        return _from_chart(path.stem, path, audio, text, delay_s, tags)
    raise ChartgenError(f"{path.name} holds no chart")


def _song_ini_tags(folder: Path) -> dict[str, str]:
    """Return the ``[song]`` entries of a folder's song.ini, or nothing if it has none that can be read."""
    path = folder / "song.ini"
    if not path.is_file():
        return {}
    parser = configparser.ConfigParser(
        delimiters=("=",), comment_prefixes=(), interpolation=None, strict=False
    )
    try:
        parser.read_string(path.read_text(encoding="utf-8-sig"))
    except (configparser.Error, UnicodeDecodeError):
        return {}
    sections = {name.lower(): name for name in parser.sections()}
    return dict(parser[sections["song"]]) if "song" in sections else {}


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
    sources = [path for path in sorted(folder.iterdir()) if path.is_file() and _is_song_audio(path.name)]
    audio = _mix(sources)
    delay_s = _song_ini_delay(folder)
    tags = _song_ini_tags(folder)
    identity = folder / "notes.mid" if (folder / "notes.mid").is_file() else folder / "notes.chart"
    if identity.name == "notes.mid":
        midi = parse_midi(identity.read_bytes())
        return _from_midi(folder.name, identity, audio, midi, delay_s, tags)
    text = identity.read_text(encoding="utf-8-sig")
    return _from_chart(folder.name, identity, audio, text, delay_s, tags)


_DRUM_CHANNEL = re.compile(r"drums_\d")


def load_drum_channels(source: Path) -> dict[str, np.ndarray]:
    """Return the separately recorded drum channels of a reference, mono at the analysis rate.

    A ``.sng`` or song folder may hold ``drums_1`` (kick), ``drums_2`` (snare), ``drums_3`` and
    ``drums_4`` instead of one ``drums`` file. ``source`` is a :class:`ReferenceSong`'s ``source``: the
    ``.sng``, or the chart file inside a folder. Returns nothing if there are none.
    """
    channels: dict[str, np.ndarray] = {}
    if source.suffix.lower() == ".sng":
        container = open_sng(source)
        with tempfile.TemporaryDirectory(prefix="chartgen-channels-") as folder:
            for name in container.entries:
                path = Path(name)
                if path.suffix.lower() in AUDIO_SUFFIXES and _DRUM_CHANNEL.fullmatch(path.stem.lower()):
                    target = Path(folder) / path.name
                    target.write_bytes(container.read(name))
                    samples, rate = sf.read(str(target), dtype="float32", always_2d=True)
                    channels[path.stem.lower()] = analysis_mono(samples, rate)
        return channels
    for path in sorted(source.parent.iterdir()):
        if path.suffix.lower() in AUDIO_SUFFIXES and _DRUM_CHANNEL.fullmatch(path.stem.lower()):
            samples, rate = sf.read(str(path), dtype="float32", always_2d=True)
            channels[path.stem.lower()] = analysis_mono(samples, rate)
    return channels


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
