"""Runs the real analysis on every reference song and reports per song and per split.

References live in ``train/`` and ``test/`` under the reference folder. Thresholds and weights
may only ever be tuned on ``train``: a score on ``test`` is only honest if the test songs
played no part in choosing anything. New references go to ``test`` and are measured first.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from chartgen.audio.io import ANALYSIS_SAMPLERATE, analysis_mono
from chartgen.audio.separation import Separator, separate_with_cache
from chartgen.audio.tempo import estimate_tempo_map
from chartgen.chart.instruments import STEM_FOR_INSTRUMENT, build_tracks_for
from chartgen.core.model import Instrument
from chartgen.errors import ChartgenError
from chartgen.evaluation.metrics import average, chart_metrics, tempo_metrics
from chartgen.evaluation.reference import (
    SPLIT_TEST,
    SPLIT_TRAIN,
    SPLIT_UNASSIGNED,
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


@dataclass(frozen=True)
class EvaluationReport:
    songs: dict[str, dict[str, object]]
    """Metrics of each song, by name."""
    splits: dict[str, str]
    """The split each song belongs to, by name."""
    averages: dict[str, dict[str, float]]
    """Average metrics of each split that has songs."""
    failures: dict[str, str]


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
        Instrument.GUITAR, stem, tempo.tempo_map, stems.duration_s, vocals=vocals
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
    return EvaluationReport(songs, splits, averages, failures)


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
        }
        for split in report.averages
    }
    path.write_text(
        json.dumps({**grouped, "failures": report.failures}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
