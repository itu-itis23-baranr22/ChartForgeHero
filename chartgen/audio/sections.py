"""Finding a song's sections: where its texture changes, and which parts come back.

Each bar of the song is described by the harmony of the pitched stems, the timbre and loudness of the
mix and the loudness of the vocals, standardised over the song. Where the bars before a bar line differ
from the bars after it (Foote's checkerboard novelty on the bars' self-similarity), a section starts. A
section is then given the letter of an earlier one whose bars, side by side from the start, are
similar enough, or a new letter.

Hard rules, here in code; ``sections.toml`` cannot loosen them:

- a section starts on a bar line and lasts at least four bars, the last one included;
- names are ASCII letters and digits (``A1``, ``B1``, ``A2``...);
- after an opening that is not part of the song, the found sections start after ``Song``, at least four
  bars after it; nothing is placed in the opening;
- a song whose texture hardly changes gets no section at all rather than forced ones.

Above 150 BPM (``FLOOR_BPM``, SPEC 41) the bars are taken two by two, from the first bar that is not silent:
a song found at its true fast tempo has bars half as long as at half tempo, and the kernel and the shortest
section, counted in bars, would halve in seconds (SPEC 46).
"""

from __future__ import annotations

import math
import re
import time
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

import librosa
import numpy as np

from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.core.timing import FLOOR_BPM, TempoMap

CONFIG_PATH = Path(__file__).with_name("sections.toml")
MIN_SECTION_BARS = 4
"""Hard rule: a section lasts at least this many bars."""
SECTION_NAME = re.compile(r"^[A-Z]+[0-9]+$")
_HOP = 512
_END_MARGIN_S = 0.5
"""A bar line this close to the end starts no bar of its own."""
_SPREAD_FLOORS = (0.05, 2.0, 1.0, 1.0)
"""The smallest spread over the song that counts, for chroma (0 to 1), MFCC, loudness in dB and vocal
loudness in dB. Four real songs spread at least 0.10, 2.0, 3.1 and 8.0; a loop that never changes
0.003, 0.73, 0.05 and 0."""
_MIN_NORM = 1.0
"""A standardised bar this close to the song's average is not stretched to unit length. Bars of a real
song lie around 1.6 from it, those of a loop that never changes around 0.3."""


class SectionRuleViolation(ValueError):
    """Found sections broke a hard rule: a bug, never a matter of settings."""


@dataclass(frozen=True)
class SectionWeights:
    harmony: float
    timbre: float
    loudness: float
    vocals: float


@dataclass(frozen=True)
class SectionConfig:
    weights: SectionWeights
    kernel_bars: int
    novelty_threshold: float
    min_section_bars: int
    silence_below_loud_db: float
    same_part_similarity: float


def _take(values: dict, keys: set[str], where: str) -> dict:
    if set(values) != keys:
        raise ValueError(f"{where}: expected keys {sorted(keys)}, got {sorted(values)}")
    return values


def load_section_config(path: Path = CONFIG_PATH) -> SectionConfig:
    """Read the section settings.

    Raises:
        ValueError: If a value is missing, unknown or out of range, or would loosen a hard rule.
    """
    with path.open("rb") as stream:
        values = tomllib.load(stream)
    _take(values, {"weights", "boundaries", "letters"}, path.name)
    weights = _take(dict(values["weights"]), {item.name for item in fields(SectionWeights)}, f"{path.name} [weights]")
    if any(float(weight) < 0 for weight in weights.values()) or not any(float(weight) > 0 for weight in weights.values()):
        raise ValueError(f"{path.name} [weights]: weights must not be negative, and one must be positive")
    boundaries = _take(
        dict(values["boundaries"]),
        {"kernel_bars", "novelty_threshold", "min_section_bars", "silence_below_loud_db"},
        f"{path.name} [boundaries]",
    )
    letters = _take(dict(values["letters"]), {"same_part_similarity"}, f"{path.name} [letters]")
    kernel = int(boundaries["kernel_bars"])
    if kernel < 2 or kernel % 2:
        raise ValueError(f"{path.name} [boundaries]: kernel_bars must be even and at least 2")
    minimum = int(boundaries["min_section_bars"])
    if minimum < MIN_SECTION_BARS:
        raise ValueError(f"{path.name} [boundaries]: min_section_bars below {MIN_SECTION_BARS} would break a hard rule")
    threshold = float(boundaries["novelty_threshold"])
    if not 0 < threshold < 1:
        raise ValueError(f"{path.name} [boundaries]: novelty_threshold must be between 0 and 1")
    return SectionConfig(
        SectionWeights(**{key: float(value) for key, value in weights.items()}),
        kernel,
        threshold,
        minimum,
        float(boundaries["silence_below_loud_db"]),
        float(letters["same_part_similarity"]),
    )


@dataclass(frozen=True)
class FoundSection:
    tick: int
    time_s: float
    name: str
    letter: str
    change: float | None
    """How strong the change that starts it was. None for the first one, which no change starts."""


@dataclass(frozen=True)
class SectionAnalysis:
    sections: tuple[FoundSection, ...]
    """The sections found, in order. Empty if the song's texture hardly changes."""
    strongest_change: float
    """The strongest change anywhere in the song, which a boundary needs to reach the threshold."""
    threshold: float
    after_opening: bool
    """Whether the song has an opening that is not part of it, so ``Song`` starts the first part."""
    seconds: float
    song_part: FoundSection | None = None
    """After an opening, the part that ``Song`` starts (``A1``), from its first bar line: it is written
    as ``Song`` but lettered like any other part, so a later return of it is ``A2``."""
    bar_step: int = 1
    """How many of the map's bars count as one: 2 above 150 BPM, else 1."""

    @property
    def parts(self) -> tuple[FoundSection, ...]:
        """Every lettered part in order: the one ``Song`` starts, if any, then the written sections."""
        return ((self.song_part,) if self.song_part is not None else ()) + self.sections

    @property
    def found(self) -> bool:
        return bool(self.sections)


def _frame_features(mix: np.ndarray, pitched: np.ndarray, vocals: np.ndarray) -> tuple[np.ndarray, ...]:
    """Chroma of the pitched stems, MFCC and loudness of the mix, loudness of the vocals, frame by frame."""
    sr = ANALYSIS_SAMPLERATE
    chroma = librosa.feature.chroma_stft(y=pitched, sr=sr, hop_length=_HOP)
    mfcc = librosa.feature.mfcc(y=mix, sr=sr, hop_length=_HOP, n_mfcc=13)[1:]
    loudness = librosa.amplitude_to_db(librosa.feature.rms(y=mix, hop_length=_HOP), ref=1.0)
    voice = librosa.amplitude_to_db(librosa.feature.rms(y=vocals, hop_length=_HOP), ref=1.0)
    return chroma, mfcc, loudness, voice


def _bar_features(
    frame_features: tuple[np.ndarray, ...], bar_times: np.ndarray, weights: SectionWeights
) -> tuple[np.ndarray, np.ndarray]:
    """One row per bar: the weighted, standardised features, scaled to unit length. Also each bar's
    loudness in dB."""
    sr = ANALYSIS_SAMPLERATE
    chroma, mfcc, loudness, voice = frame_features
    frames = min(chroma.shape[1], mfcc.shape[1], loudness.shape[1], voice.shape[1])
    edges = np.append(librosa.time_to_frames(bar_times, sr=sr, hop_length=_HOP), frames).clip(0, frames)

    def per_bar(block: np.ndarray) -> np.ndarray:
        return np.stack(
            [block[:, a:b].mean(axis=1) if b > a else block[:, min(a, frames - 1)] for a, b in zip(edges[:-1], edges[1:])],
            axis=1,
        )

    rows = []
    for weight, block, floor in zip(
        (weights.harmony, weights.timbre, weights.loudness, weights.vocals),
        (chroma[:, :frames], mfcc[:, :frames], loudness[:, :frames], voice[:, :frames]),
        _SPREAD_FLOORS,
    ):
        synced = per_bar(block)
        # Standardised over the song, but a spread below what can be heard counts as that much: a song
        # that hardly changes must not have its smallest wobbles blown up into sections.
        spread = np.maximum(synced.std(axis=1, keepdims=True), floor)
        rows.append(weight * (synced - synced.mean(axis=1, keepdims=True)) / spread / math.sqrt(block.shape[0]))
    features = np.vstack(rows).T
    # Unit length, except for bars that hardly differ from the song's average: those stay short, so they
    # are similar to nothing in particular rather than to a direction made of noise.
    norms = np.linalg.norm(features, axis=1, keepdims=True)
    features = features / np.maximum(norms, _MIN_NORM)
    return features, per_bar(loudness[:, :frames])[0]


def _median_bpm(tempo_map: TempoMap, ticks: np.ndarray) -> float:
    """The tempo in force at the median bar line."""
    starts = np.array([event.tick for event in tempo_map.tempos])
    bpms = np.array([event.bpm for event in tempo_map.tempos])
    return float(np.median(bpms[np.searchsorted(starts, ticks, side="right") - 1]))


def _first_sounding(loudness: np.ndarray, config: SectionConfig) -> int:
    """The first bar that is not silent: within ``silence_below_loud_db`` of the song's loud level."""
    return int(np.argmax(loudness > np.percentile(loudness, 95) - config.silence_below_loud_db))


def _novelty(similarity: np.ndarray, kernel_bars: int) -> np.ndarray:
    """Foote's novelty: a Gaussian-tapered checkerboard along the diagonal, scaled so that two parts with
    nothing in common score 0.5 and a song that never changes scores 0."""
    half = kernel_bars // 2
    offsets = np.arange(kernel_bars) - half + 0.5
    taper = np.exp(-0.5 * (offsets / half) ** 2)
    kernel = np.outer(np.sign(offsets), np.sign(offsets)) * np.outer(taper, taper)
    kernel /= np.abs(kernel).sum()
    padded = np.pad(similarity, half, mode="edge")
    return np.array([np.sum(kernel * padded[i : i + kernel_bars, i : i + kernel_bars]) for i in range(len(similarity))])


def _letter(index: int) -> str:
    """A, B, ... Z, AA, AB, ...: ASCII however many parts there are."""
    name = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(ord("A") + rest) + name
    return name


def _letters(similarity: np.ndarray, segments: list[tuple[int, int]], same_part: float) -> list[str]:
    """Give each segment the letter of the most similar earlier one, bar by bar from the start, if that is
    similar enough; otherwise a new letter."""
    letters: list[str] = []
    for index, (start, end) in enumerate(segments):
        best, best_similarity = None, -math.inf
        for earlier, (other_start, other_end) in enumerate(segments[:index]):
            length = min(end - start, other_end - other_start)
            value = float(np.mean([similarity[start + k, other_start + k] for k in range(length)]))
            if value > best_similarity:
                best, best_similarity = letters[earlier], value
        if best is not None and best_similarity >= same_part:
            letters.append(best)
        else:
            letters.append(_letter(len(set(letters))))
    return letters


def find_sections(
    mix: np.ndarray,
    pitched: np.ndarray,
    vocals: np.ndarray,
    tempo_map: TempoMap,
    duration_s: float,
    song_start_s: float = 0.0,
    after_opening: bool = False,
    config: SectionConfig | None = None,
) -> SectionAnalysis:
    """Find the sections of a song from mono signals at the analysis rate.

    Args:
        mix: The whole song.
        pitched: The pitched stems together (bass, guitar, piano, other).
        vocals: The vocal stem.
        song_start_s: Where the song starts. Nothing before it is looked at.
        after_opening: Whether an opening that is not part of the song comes first. Then the part that
            starts at ``song_start_s`` is written as ``Song``; it is lettered like the others (it is
            ``A1``, see ``song_part``) and the found sections follow it.
    """
    started = time.perf_counter()
    config = config or load_section_config()
    bar_ticks = tempo_map.bar_lines(duration_s)
    bar_times = tempo_map.seconds_at(bar_ticks.astype(np.float64)) if bar_ticks.size else np.empty(0)
    keep = (bar_times >= song_start_s - 1e-6) & (bar_times < duration_s - _END_MARGIN_S)
    bar_ticks, bar_times = bar_ticks[keep], bar_times[keep]
    minimum = config.min_section_bars
    if bar_ticks.size < 2 * minimum:
        return SectionAnalysis((), 0.0, config.novelty_threshold, after_opening, time.perf_counter() - started)
    frame_features = _frame_features(mix, pitched, vocals)
    step = 1
    if _median_bpm(tempo_map, bar_ticks) > FLOOR_BPM:
        # Two bars count as one, paired from the first bar that sounds, where the first section starts: at
        # half tempo that bar would be a downbeat. Pairing from the map's first bar instead put First Date's
        # boundaries a bar off (train boundary F1 0.25).
        _, loudness = _bar_features(frame_features, bar_times, config.weights)
        step = 2
        phase = _first_sounding(loudness, config) % 2
        bar_ticks, bar_times = bar_ticks[phase::2], bar_times[phase::2]
        if bar_ticks.size < 2 * minimum:
            return SectionAnalysis((), 0.0, config.novelty_threshold, after_opening, time.perf_counter() - started, bar_step=step)
    features, loudness = _bar_features(frame_features, bar_times, config.weights)
    first = _first_sounding(loudness, config)
    similarity = features @ features.T
    novelty = _novelty(similarity, config.kernel_bars)
    # Only where a section could start: at the edges the checkerboard half looks at padding.
    eligible = novelty[first + minimum : novelty.size - minimum + 1]
    strongest = float(eligible.max()) if eligible.size else 0.0
    candidates = [
        index
        for index in range(first + 1, novelty.size - 1)
        if novelty[index] >= novelty[index - 1]
        and novelty[index] > novelty[index + 1]
        and novelty[index] >= config.novelty_threshold
    ]
    starts = [first]
    for index in sorted(candidates, key=lambda item: (-novelty[item], item)):
        if index - first < minimum or bar_ticks.size - index < minimum:
            continue
        if all(abs(index - other) >= minimum for other in starts):
            starts.append(index)
    starts.sort()
    if len(starts) == 1:
        return SectionAnalysis(
            (), strongest, config.novelty_threshold, after_opening, time.perf_counter() - started, bar_step=step
        )
    segments = list(zip(starts, starts[1:] + [int(bar_ticks.size)]))
    letters = _letters(similarity, segments, config.same_part_similarity)
    counts: dict[str, int] = {}
    sections = []
    song_part = None
    for (start, _), letter in zip(segments, letters):
        counts[letter] = counts.get(letter, 0) + 1
        part = FoundSection(
            int(bar_ticks[start]),
            float(bar_times[start]),
            f"{letter}{counts[letter]}",
            letter,
            float(novelty[start]) if start != first else None,
        )
        if after_opening and song_part is None:
            # After an opening the first part is written as ``Song``, but it counts as its letter's first.
            song_part = part
        else:
            sections.append(part)
    analysis = SectionAnalysis(
        tuple(sections), strongest, config.novelty_threshold, after_opening, time.perf_counter() - started, song_part,
        step,
    )
    check_found_sections(analysis, tempo_map, duration_s, song_start_s, minimum)
    return analysis


def check_found_sections(
    analysis: SectionAnalysis,
    tempo_map: TempoMap,
    duration_s: float,
    song_start_s: float = 0.0,
    minimum: int = MIN_SECTION_BARS,
) -> None:
    """Hold found sections to the hard rules.

    Raises:
        SectionRuleViolation: On the first rule broken.
    """
    lines = tempo_map.bar_lines(duration_s)
    index_of = {int(tick): index for index, tick in enumerate(lines)}
    start_tick = float(tempo_map.ticks_at(song_start_s))
    previous = None
    for section in analysis.sections:
        if not SECTION_NAME.match(section.name):
            raise SectionRuleViolation(f"section {section.name!r} is not ASCII letters and digits")
        if section.tick not in index_of:
            raise SectionRuleViolation(f"section {section.name} at tick {section.tick} is not on a bar line")
        if section.tick < start_tick - 1e-6:
            raise SectionRuleViolation(f"section {section.name} starts before the song does")
        index = index_of[section.tick]
        if previous is not None and index - previous < minimum:
            raise SectionRuleViolation(f"section before {section.name} is shorter than {minimum} bars")
        if analysis.after_opening and previous is None:
            # The first found section follows ``Song``, which starts at the song's start.
            song_bar = int(np.searchsorted(lines, start_tick - 1e-6))
            if index - song_bar < minimum:
                raise SectionRuleViolation(f"{section.name} comes less than {minimum} bars after Song")
        previous = index
    if previous is not None and int(np.sum(tempo_map.seconds_at(lines.astype(np.float64)) < duration_s - _END_MARGIN_S)) - previous < minimum:
        raise SectionRuleViolation(f"the last section is shorter than {minimum} bars")
