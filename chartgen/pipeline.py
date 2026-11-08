"""The whole build, stage by stage."""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import chartgen
from chartgen.audio.io import ANALYSIS_SAMPLERATE, AudioData, analysis_mono, load_audio, to_mono
from chartgen.audio.presence import StemPresence, analyze_presence
from chartgen.audio.separation import STEM_NAMES, Separator, StemSet, separate_with_cache
from chartgen.audio.tempo import TempoAnalysis, estimate_tempo_map
from chartgen.chart.instruments import (
    CHARTABLE_INSTRUMENTS,
    STEM_FOR_INSTRUMENT,
    build_tracks_for,
)
from chartgen.clonehero.chart_format import DotChartExporter
from chartgen.clonehero.package import (
    BACKING_STEM,
    EncodedAudio,
    best_preview_start_ms,
    folder_name,
    plan_audio,
    write_audio_files,
)
from chartgen.clonehero.song_ini import SongIni, difficulty_tier, render_song_ini
from chartgen.clonehero.validate import validate_song_folder
from chartgen.core.model import Chart, Instrument, SongMetadata, Track
from chartgen.errors import ChartValidationError, NoPlayableInstrumentError, PackagingError

log = logging.getLogger(__name__)

ANALYSIS_FILE = "analysis.json"
_STAGE_COUNT = 7


@dataclass(frozen=True)
class BuildConfig:
    input_path: Path
    metadata: SongMetadata
    instruments: frozenset[Instrument]
    output_dir: Path = Path("outputs")
    cache_dir: Path = Path(".cache/stems")
    force: bool = False


@dataclass
class BuildResult:
    folder: Path
    analysis: dict[str, object] = field(default_factory=dict)


class _Stages:
    """Logs each stage and records how long it took."""

    def __init__(self) -> None:
        self.timings_s: dict[str, float] = {}
        self._number = 0

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        self._number += 1
        log.info("[%d/%d] %s ...", self._number, _STAGE_COUNT, name)
        started = time.perf_counter()
        yield
        elapsed = time.perf_counter() - started
        self.timings_s[name] = round(elapsed, 3)
        log.info("[%d/%d] %s done in %.2f s", self._number, _STAGE_COUNT, name, elapsed)


def _analyze_all_presence(stems: StemSet) -> dict[str, StemPresence]:
    # The sum of the stems is sample-aligned with them by construction, which the
    # original mix is not when separation resampled the audio.
    mix = np.sum([stems.stems[name] for name in STEM_NAMES], axis=0)
    return {
        name: analyze_presence(name, stems.stems[name], mix, stems.samplerate)
        for name in STEM_NAMES
        if name != BACKING_STEM
    }


def _build_tracks(
    config: BuildConfig,
    stems: StemSet,
    presence: dict[str, StemPresence],
    tempo: TempoAnalysis,
    warnings: list[str],
) -> list[Track]:
    tracks: list[Track] = []
    for instrument in sorted(config.instruments, key=lambda item: item.value):
        stem = STEM_FOR_INSTRUMENT[instrument]
        if not presence[stem].present:
            warnings.append(
                f"{instrument.value}: the {stem} stem is below the presence threshold "
                f"({presence[stem].energy_ratio_db:.1f} dB, "
                f"{presence[stem].active_ratio:.0%} active); no chart, audio moved to song.ogg"
            )
            continue
        if instrument not in CHARTABLE_INSTRUMENTS:
            warnings.append(
                f"{instrument.value}: chart generation is not implemented yet; audio only"
            )
            continue
        mono = analysis_mono(stems.stems[stem], stems.samplerate)
        built = build_tracks_for(instrument, mono, tempo.tempo_map, stems.duration_s)
        if not built:
            warnings.append(f"{instrument.value}: no notes detected in the {stem} stem")
        tracks.extend(built)
    return tracks


def _finite_or_none(value: float) -> float | None:
    return value if math.isfinite(value) else None


def _analysis(
    config: BuildConfig,
    audio: AudioData,
    stems: StemSet,
    presence: dict[str, StemPresence],
    tempo: TempoAnalysis,
    tracks: list[Track],
    encoded: list[EncodedAudio],
    difficulties: dict[Instrument, int],
    preview_start_ms: int,
    warnings: list[str],
    timings_s: dict[str, float],
) -> dict[str, object]:
    charts: dict[str, dict[str, dict[str, float]]] = {}
    for track in tracks:
        ticks = {note.tick for note in track.notes}
        charts.setdefault(track.instrument.value, {})[track.difficulty.value] = {
            "notes": len(track.notes),
            "chords": len(track.notes) - len(ticks),
            "notes_per_second": round(len(track.notes) / stems.duration_s, 3),
        }
    return {
        "schema_version": 1,
        "chartgen_version": chartgen.__version__,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input": {
            "file_name": config.input_path.name,
            "sha256": stems.source_sha256,
            "duration_s": round(audio.duration_s, 3),
            "samplerate": audio.samplerate,
            "channels": audio.samples.shape[1],
        },
        "separation": {
            "separator": stems.separator_id,
            "samplerate": stems.samplerate,
            "from_cache": stems.from_cache,
        },
        "tempo": {
            "bpm": round(tempo.bpm, 3),
            "method": tempo.method,
            "tempo_events": [asdict(event) for event in tempo.tempo_map.tempos],
            "segments": tempo.segment_count,
            "on_grid_ratio": round(tempo.on_grid_ratio, 3),
            "grid_error_p95_ms": _finite_or_none(round(tempo.grid_error_p95_ms, 2)),
            "tempo_strength": round(tempo.tempo_strength, 4),
            "time_signature": "4/4 (assumed, not detected)",
        },
        "stems": {
            name: {
                "present": result.present,
                "energy_ratio_db": _finite_or_none(round(result.energy_ratio_db, 2)),
                "active_ratio": round(result.active_ratio, 3),
                "min_energy_ratio_db": result.threshold.min_energy_ratio_db,
                "min_active_ratio": result.threshold.min_active_ratio,
            }
            for name, result in presence.items()
        },
        "audio_files": {
            item.file_name: {
                "stems": list(item.stems),
                "frames": item.frames,
                "size_bytes": item.size_bytes,
                "lag_frames": item.lag_frames,
            }
            for item in encoded
        },
        "charts": charts,
        "song_ini": {
            "preview_start_time_ms": preview_start_ms,
            "difficulty": {inst.value: tier for inst, tier in difficulties.items()},
        },
        "timings_s": timings_s,
        "warnings": warnings,
    }


def _publish(temporary: Path, destination: Path, force: bool) -> None:
    """Move the finished folder into place; a failed build leaves nothing behind."""
    if destination.exists():
        if not force:
            raise PackagingError(f"{destination} already exists; use --force to replace it")
        shutil.rmtree(destination)
    os.replace(temporary, destination)


def build_song(config: BuildConfig, separator: Separator) -> BuildResult:
    """Build one song folder.

    Raises:
        ChartgenError: On any expected failure. The output folder is then untouched.
    """
    destination = config.output_dir / folder_name(config.metadata.artist, config.metadata.name)
    if destination.exists() and not config.force:
        raise PackagingError(f"{destination} already exists; use --force to replace it")

    stages = _Stages()
    warnings: list[str] = []

    with stages.stage("Load audio"):
        audio = load_audio(config.input_path)
        log.info(
            "    %s: %.1f s, %d Hz, %d channels",
            config.input_path.name,
            audio.duration_s,
            audio.samplerate,
            audio.samples.shape[1],
        )

    with stages.stage("Separate stems"):
        stems = separate_with_cache(config.input_path, audio, separator, config.cache_dir)

    with stages.stage("Check stem presence"):
        presence = _analyze_all_presence(stems)
        for result in presence.values():
            log.info(
                "    %-7s %s  energy %6.1f dB  active %3.0f%%",
                result.stem,
                "present" if result.present else "absent ",
                result.energy_ratio_db,
                result.active_ratio * 100,
            )

    with stages.stage("Track tempo on the mix"):
        tempo = estimate_tempo_map(analysis_mono(audio.samples, audio.samplerate))
        if tempo.is_fallback:
            warnings.append("beat tracking failed; the chart uses a fixed fallback tempo")
        log.info(
            "    %.2f BPM (%s), %d tempo events, %.0f%% of onsets on the sixteenth grid",
            tempo.bpm,
            tempo.method,
            len(tempo.tempo_map.tempos),
            tempo.on_grid_ratio * 100,
        )

    with stages.stage("Chart instruments"):
        tracks = _build_tracks(config, stems, presence, tempo, warnings)
        for track in tracks:
            log.info(
                "    %s/%s: %d notes",
                track.instrument.value,
                track.difficulty.value,
                len(track.notes),
            )
        if not tracks:
            raise NoPlayableInstrumentError(
                "No requested instrument produced a chart, so the song would be unplayable. "
                + " ".join(warnings)
            )

    config.output_dir.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".build-", dir=config.output_dir))
    try:
        with stages.stage("Package song folder"):
            chart = Chart(config.metadata, tempo.tempo_map, tracks)
            DotChartExporter().export(chart, temporary)

            plan = plan_audio(presence, config.instruments)
            encoded = write_audio_files(stems.stems, stems.samplerate, plan, temporary)

            song_length_ms = round(stems.duration_s * 1000)
            preview_start_ms = best_preview_start_ms(
                analysis_mono(_full_mix(stems), stems.samplerate),
                ANALYSIS_SAMPLERATE,
            )
            difficulties: dict[Instrument, int] = {}
            for track in tracks:
                difficulties[track.instrument] = max(
                    difficulties.get(track.instrument, 0),
                    difficulty_tier(len(track.notes), stems.duration_s),
                )
            (temporary / "song.ini").write_text(
                render_song_ini(
                    SongIni(config.metadata, song_length_ms, preview_start_ms, 0, difficulties)
                ),
                encoding="utf-8",
                newline="\n",
            )

        with stages.stage("Validate"):
            report = validate_song_folder(temporary)
            warnings.extend(report.warnings)
            if not report.ok:
                raise ChartValidationError(
                    "The generated song failed validation:\n  " + "\n  ".join(report.errors)
                )

        analysis = _analysis(
            config,
            audio,
            stems,
            presence,
            tempo,
            tracks,
            encoded,
            difficulties,
            preview_start_ms,
            warnings,
            stages.timings_s,
        )
        (temporary / ANALYSIS_FILE).write_text(
            json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        _publish(temporary, destination, config.force)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    for warning in warnings:
        log.warning("Warning: %s", warning)
    return BuildResult(destination, analysis)


def _full_mix(stems: StemSet) -> np.ndarray:
    return to_mono(np.sum([stems.stems[name] for name in STEM_NAMES], axis=0))
