"""Runs the real analysis on every reference song and reports per song and per split.

References live in ``train/`` and ``test/`` under the reference folder. Thresholds and weights
may only ever be tuned on ``train``: a score on ``test`` is only honest if the test songs
played no part in choosing anything. New references go to ``test`` and are measured first.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from chartgen.audio.io import ANALYSIS_SAMPLERATE, analysis_mono
from chartgen.audio.separation import Separator, separate_with_cache
from chartgen.audio.tempo import estimate_tempo_map
from chartgen.chart.charter import ChartedTrack
from chartgen.chart.difficulty import LANE_NAMES, LevelMeasures, load_config
from chartgen.chart.instruments import STEM_FOR_INSTRUMENT, build_tracks_for
from chartgen.core.model import Difficulty, Instrument
from chartgen.core.timing import TempoMap
from chartgen.errors import ChartgenError
from chartgen.evaluation.metrics import (
    average,
    chart_metrics,
    human_level_measures,
    naive_reductions,
    position_f1,
    tempo_metrics,
)
from chartgen.evaluation.reference import (
    SPLIT_TEST,
    SPLIT_TRAIN,
    SPLIT_UNASSIGNED,
    ReferenceNote,
    ReferenceSong,
    find_references,
    load_reference,
    split_of,
)

log = logging.getLogger(__name__)

SPLIT_TITLES = {
    SPLIT_TRAIN: "TRAIN: used for tuning, so these scores flatter the result",
    SPLIT_TEST: "TEST: never tune on these",
    SPLIT_UNASSIGNED: "NOT IN train/ OR test/: move these into one of them",
}
_SPLIT_ORDER = (SPLIT_TEST, SPLIT_TRAIN, SPLIT_UNASSIGNED)

_SHOWN = (
    ("bpm", "BPM"),
    ("human_bpm", "human"),
    ("tempo_events", "tempo events"),
    ("time_signature", "meter"),
    ("meter_confidence", "meter conf"),
    ("beats_within_35ms", "beats <35ms"),
    ("bars_agreeing", "bars agree"),
    ("note_precision", "note P"),
    ("note_recall", "note R"),
    ("note_f1", "note F1"),
    ("direction_when_human_moves", "dir moves"),
    ("direction_all_steps", "dir all"),
    ("chord_agreement", "chord"),
    ("chord_share_mine", "chords mine"),
    ("chord_share_human", "chords human"),
    ("sustain_f1", "sustain F1"),
    ("sustain_share_mine", "sust mine"),
    ("sustain_share_human", "sust human"),
    ("removed_as_vocal", "vocal notes"),
)

_LEVEL_ORDER = (Difficulty.EXPERT, Difficulty.HARD, Difficulty.MEDIUM, Difficulty.EASY)
_LEVEL_SHOWN = (
    ("positions", "positions"),
    ("position_ratio", "share of Expert"),
    ("chord_share", "chords"),
    ("three_note_share", "3-note chords"),
    ("green_share", "green"),
    ("red_share", "red"),
    ("yellow_share", "yellow"),
    ("blue_share", "blue"),
    ("orange_share", "orange"),
    ("on_beat_share", "on the beat"),
    ("sixteenth_share", "on sixteenths"),
    ("min_gap_s", "shortest gap s"),
    ("sustain_share", "sustains"),
    ("auto_hopo_share", "auto HOPO"),
    ("final_hopo_share", "final HOPO"),
)
_MATCH_SHOWN = (
    ("note_f1", "note F1"),
    ("every_nth_f1", "F1 every Nth"),
    ("beats_first_f1", "F1 beats first"),
    ("worst_lane_gap", "worst lane gap"),
    ("lanes_over_limit", "lanes over limit"),
    ("direction_when_human_moves", "dir moves"),
    ("direction_all_steps", "direction"),
    ("chord_agreement", "chord agreement"),
    ("sustain_f1", "sustain F1"),
)


@dataclass(frozen=True)
class EvaluationReport:
    songs: dict[str, dict[str, object]]
    """Metrics of each song, by name."""
    splits: dict[str, str]
    """The split each song belongs to, by name."""
    averages: dict[str, dict[str, float]]
    """Average metrics of each split that has songs."""
    failures: dict[str, str]
    level_averages: dict[str, dict[str, dict[str, dict[str, float]]]] = field(default_factory=dict)
    """Of each split, per difficulty: the average of mine, human and match."""
    bass_level_averages: dict[str, dict[str, dict[str, dict[str, float]]]] = field(default_factory=dict)
    """The same for bass, on the songs that have it."""


def _measures_dict(measures: LevelMeasures) -> dict[str, float | None]:
    """Plain numbers for the report. A level with one note has no gap, which JSON cannot hold."""
    return {
        key: value if math.isfinite(value) else None for key, value in asdict(measures).items()
    }


def _lane_gaps(mine: dict[str, object], human: dict[str, object], limit: float) -> dict[str, object]:
    """How far each lane's share is from the human's on this level. Beyond the limit only warns."""
    gaps = [abs(mine[f"{name}_share"] - human[f"{name}_share"]) for name in LANE_NAMES]
    return {
        "worst_lane_gap": round(max(gaps), 3),
        "lanes_over_limit": sum(gap > limit + 1e-9 for gap in gaps),
    }


def compare_levels(
    charted: Sequence[ChartedTrack],
    tempo_map: TempoMap,
    song: ReferenceSong,
    levels: Mapping[Difficulty, tuple[ReferenceNote, ...]] | None = None,
) -> dict[str, dict[str, dict[str, object]]]:
    """Compare every difficulty with the human's, next to what naive reductions would score.

    Args:
        charted: The generated tracks of one instrument, the hardest first.
        tempo_map: The song's tempo map.
        song: The reference song.
        levels: The human's notes for that instrument. By default, the guitar's.
    """
    human_levels = song.levels if levels is None else levels
    limit = load_config().lane_tolerance
    human_expert = len(human_levels.get(Difficulty.EXPERT, song.notes))
    my_expert = np.array(sorted({note.tick for note in charted[0].track.notes}), dtype=np.int64)
    results: dict[str, dict[str, dict[str, object]]] = {}
    for item in charted:
        level = item.track.difficulty
        entry: dict[str, dict[str, object]] = {}
        if item.measures is not None:
            entry["mine"] = _measures_dict(item.measures)
            entry["missed_targets"] = {
                target.name: {"value": target.value, "low": target.low, "high": target.high}
                for target in item.soft_targets
                if not target.in_range
            }
        human = human_levels.get(level, ())
        if human:
            measures = human_level_measures(human, song.resolution, human_expert, song.is_midi)
            entry["human"] = _measures_dict(measures)
            match = dict(chart_metrics(item.track, tempo_map, human))
            if "mine" in entry:
                match.update(_lane_gaps(entry["mine"], entry["human"], limit))
            human_times = np.array([note.time_s for note in human])
            target = round(my_expert.size * len(human) / human_expert)
            if level is not Difficulty.EXPERT:
                for name, ticks in naive_reductions(
                    my_expert, tempo_map.resolution, target
                ).items():
                    times = tempo_map.seconds_at(ticks.astype(np.float64))
                    match[f"{name}_f1"] = position_f1(times, human_times)
            entry["match"] = match
        results[level.value] = entry
    return results


def _average_levels(
    results: Sequence[dict[str, object]], key: str = "levels"
) -> dict[str, dict[str, dict[str, float]]]:
    averages: dict[str, dict[str, dict[str, float]]] = {}
    for level in _LEVEL_ORDER:
        for source in ("mine", "human", "match"):
            found = [
                entry[level.value][source]
                for entry in (result.get(key, {}) for result in results)
                if source in entry.get(level.value, {})
            ]
            if found:
                averages.setdefault(level.value, {})[source] = average(found)
    return averages


def evaluate_song(
    song: ReferenceSong, separator: Separator, cache_dir: Path
) -> dict[str, object]:
    """Run the analysis on one reference song and compare it with the human chart."""
    stems = separate_with_cache(song.source, song.audio, separator, cache_dir)
    mono = analysis_mono(song.audio.samples, song.audio.samplerate)
    pitched = np.sum([stems.stems[name] for name in ("bass", "guitar", "piano", "other")], axis=0)
    tempo = estimate_tempo_map(
        mono,
        drums=analysis_mono(stems.stems["drums"], stems.samplerate),
        harmonic=analysis_mono(pitched, stems.samplerate),
        bass=analysis_mono(stems.stems["bass"], stems.samplerate),
    )
    stem = analysis_mono(stems.stems[STEM_FOR_INSTRUMENT[Instrument.GUITAR]], stems.samplerate)
    vocals = analysis_mono(stems.stems["vocals"], stems.samplerate)
    charted = build_tracks_for(
        Instrument.GUITAR,
        stem,
        tempo.tempo_map,
        stems.duration_s,
        vocals=vocals,
        not_before_s=tempo.lead_in_end_s,
    )

    duration = len(mono) / ANALYSIS_SAMPLERATE
    result: dict[str, object] = {
        "bpm": round(tempo.bpm, 2),
        "tempo_method": tempo.method,
        "tempo_events": len(tempo.tempo_map.tempos),
        "time_signature": tempo.meter.label if tempo.meter else None,
        "human_time_signatures": [f"{n}/{d}" for n, d in song.signatures],
        "meter_confidence": round(tempo.bar_confidence, 2),
    }
    result.update(tempo_metrics(tempo.tempo_map, song.beats, song.bars, duration))
    if charted:
        result.update(chart_metrics(charted[0].track, tempo.tempo_map, song.notes))
        result["removed_as_vocal"] = sum(note.removed for note in charted[0].bleed)
        result["chord_limit_adjusted"] = charted[0].chord_limit_adjusted
        result["levels"] = compare_levels(charted, tempo.tempo_map, song)
    if song.bass_levels:
        bass = build_tracks_for(
            Instrument.BASS,
            analysis_mono(stems.stems[STEM_FOR_INSTRUMENT[Instrument.BASS]], stems.samplerate),
            tempo.tempo_map,
            stems.duration_s,
            not_before_s=tempo.lead_in_end_s,
        )
        if bass:
            result["bass"] = compare_levels(bass, tempo.tempo_map, song, song.bass_levels)
    return result


def evaluate_folder(
    root: Path, separator: Separator, cache_dir: Path, split: str | None = None
) -> EvaluationReport:
    """Evaluate every reference under ``root``. A broken reference is reported, not fatal.

    Args:
        root: Folder holding ``train/`` and ``test/``.
        separator: Runs stem separation.
        cache_dir: Stem cache.
        split: Evaluate only this split.

    Raises:
        ChartgenError: If the folder holds no matching reference at all.
    """
    references = [
        path for path in find_references(root) if split is None or split_of(path, root) == split
    ]
    if not references:
        wanted = f"in {split}/ " if split else ""
        raise ChartgenError(f"No .sng files or chart folders found {wanted}under {root}")
    songs: dict[str, dict[str, object]] = {}
    splits: dict[str, str] = {}
    failures: dict[str, str] = {}
    for path in references:
        log.info("Evaluating %s ...", path.name)
        try:
            song = load_reference(path)
            songs[song.name] = evaluate_song(song, separator, cache_dir)
            splits[song.name] = split_of(path, root)
        except ChartgenError as error:
            log.warning("Skipping %s: %s", path.name, error)
            failures[path.name] = str(error)
    averages = {
        name: average([songs[song] for song in songs if splits[song] == name])
        for name in _SPLIT_ORDER
        if name in splits.values()
    }
    level_averages = {
        name: _average_levels([songs[song] for song in songs if splits[song] == name])
        for name in averages
    }
    bass_level_averages = {
        name: _average_levels([songs[song] for song in songs if splits[song] == name], "bass")
        for name in averages
    }
    return EvaluationReport(songs, splits, averages, failures, level_averages, bass_level_averages)


def _cell(mine: object, human: object) -> str:
    return f"{'-' if mine is None else mine} / {'-' if human is None else human}"


def _level_table(title: str, levels: dict[str, dict[str, dict[str, object]]]) -> list[str]:
    """Show each difficulty side by side: mine / human, and how close the notes come."""
    present = [level.value for level in _LEVEL_ORDER if level.value in levels]
    if not present:
        return []
    lines = [title, f"{'mine / human':18s}" + "".join(f"{name:>16s}" for name in present)]
    for key, label in _LEVEL_SHOWN:
        cells = [
            _cell(levels[name].get("mine", {}).get(key), levels[name].get("human", {}).get(key))
            for name in present
        ]
        lines.append(f"{label:18s}" + "".join(f"{cell:>16s}" for cell in cells))
    lines.append(f"{'against the human':18s}")
    for key, label in _MATCH_SHOWN:
        cells = [str(levels[name].get("match", {}).get(key, "-")) for name in present]
        lines.append(f"{label:18s}" + "".join(f"{cell:>16s}" for cell in cells))
    for name in present:
        missed = levels[name].get("missed_targets") or {}
        if missed:
            lines.append(
                f"{name} misses its soft targets: "
                + ", ".join(
                    f"{key} {value['value']:.2f} (wanted {value['low']:g} to {value['high']:g})"
                    for key, value in missed.items()
                )
            )
    lines.append("")
    return lines


def format_report(report: EvaluationReport) -> str:
    """Render one table per split, test first: it is the score that counts."""
    lines: list[str] = []
    for split in _SPLIT_ORDER:
        names = [name for name in report.songs if report.splits[name] == split]
        if not names:
            continue
        width = max(14, *(len(name) + 2 for name in names))
        lines.append(SPLIT_TITLES[split])
        lines.append(f"{'':14s}" + "".join(f"{name:>{width}s}" for name in names) + f"{'average':>10s}")
        for key, label in _SHOWN:
            cells = [str(report.songs[name].get(key, "-")) for name in names]
            mean = report.averages[split].get(key, "-")
            lines.append(
                f"{label:14s}" + "".join(f"{cell:>{width}s}" for cell in cells) + f"{mean!s:>10s}"
            )
        lines.append("")
        for name in names:
            lines.extend(_level_table(f"Difficulties of {name}", report.songs[name].get("levels", {})))
            lines.extend(_level_table(f"Bass of {name}", report.songs[name].get("bass", {})))
        if len(names) > 1:
            lines.extend(
                _level_table("Difficulties, average", report.level_averages.get(split, {}))
            )
            lines.extend(_level_table("Bass, average", report.bass_level_averages.get(split, {})))
    for name, reason in report.failures.items():
        lines.append(f"Skipped {name}: {reason}")
    if SPLIT_TEST not in report.averages:
        lines.append("No test references were scored: these numbers say little about new songs.")
    return "\n".join(lines).rstrip()


def write_report(report: EvaluationReport, path: Path) -> None:
    grouped = {
        split: {
            "songs": {name: report.songs[name] for name in report.songs if report.splits[name] == split},
            "average": report.averages[split],
            "average_by_difficulty": report.level_averages.get(split, {}),
            **(
                {"bass_average_by_difficulty": report.bass_level_averages[split]}
                if report.bass_level_averages.get(split)
                else {}
            ),
        }
        for split in report.averages
    }
    path.write_text(
        json.dumps({**grouped, "failures": report.failures}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
