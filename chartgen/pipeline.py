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
from chartgen.audio.tempo import DEFAULT_MAX_BEAT_DRIFT_S, TempoAnalysis, estimate_tempo_map
from chartgen.chart.charter import ChartedTrack
from chartgen.chart.difficulty import HARD_RULES, HardRuleViolation
from chartgen.chart.drum_charter import DRUM_HARD_RULES, UNVERIFIED_GEMS, UNVERIFIED_PIECES, DrumChart
from chartgen.chart.drum_difficulty import LEVEL_HARD_RULES
from chartgen.chart.sections import opening_sections, song_start_s
from chartgen.core.drums import DrumGem
from chartgen.chart.instruments import (
    CHARTABLE_INSTRUMENTS,
    STEM_FOR_INSTRUMENT,
    UNVERIFIED_INSTRUMENTS,
    build_tracks_for,
)
from chartgen.clonehero.chart_format import DotChartExporter
from chartgen.clonehero.drum_ear_test import EAR_TEST_DIR, write_drum_ear_test
from chartgen.clonehero.click_overlay import (
    CLICK_DIR,
    CLICK_FILE,
    ClickSchedule,
    write_click_overlay,
)
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
from chartgen.core.model import Chart, Difficulty, Instrument, SongMetadata, Track
from chartgen.errors import ChartValidationError, NoPlayableInstrumentError, PackagingError

log = logging.getLogger(__name__)

ANALYSIS_FILE = "analysis.json"
_BASE_STAGE_COUNT = 7


@dataclass(frozen=True)
class BuildConfig:
    input_path: Path
    metadata: SongMetadata
    instruments: frozenset[Instrument]
    output_dir: Path = Path("outputs")
    cache_dir: Path = Path(".cache/stems")
    force: bool = False
    bpm_override: float | None = None
    click_overlay: bool = False
    drum_ear_test: bool = False
    """Write one listening file per part of the kit into ``debug``."""
    max_beat_drift_ms: float = DEFAULT_MAX_BEAT_DRIFT_S * 1000.0


@dataclass
class BuildResult:
    folder: Path
    analysis: dict[str, object] = field(default_factory=dict)


class _Stages:
    """Logs each stage and records how long it took."""

    def __init__(self, count: int) -> None:
        self.timings_s: dict[str, float] = {}
        self._count = count
        self._number = 0

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        self._number += 1
        log.info("[%d/%d] %s ...", self._number, self._count, name)
        started = time.perf_counter()
        yield
        elapsed = time.perf_counter() - started
        self.timings_s[name] = round(elapsed, 3)
        log.info("[%d/%d] %s done in %.2f s", self._number, self._count, name, elapsed)


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
) -> list[ChartedTrack]:
    charted: list[ChartedTrack] = []
    vocals = analysis_mono(stems.stems["vocals"], stems.samplerate)
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
        built = build_tracks_for(
            instrument, mono, tempo.tempo_map, stems.duration_s, vocals, tempo.lead_in_end_s
        )
        if not built:
            warnings.append(f"{instrument.value}: no notes detected in the {stem} stem")
        elif instrument in UNVERIFIED_INSTRUMENTS:
            warnings.append(
                f"{instrument.value}: not verified on real data: this chart generator has only been "
                f"tested on synthetic audio"
            )
        elif instrument is Instrument.DRUMS:
            warnings.append(_unverified_drums(built[0]))
        for item in built:
            _report_track(instrument, item, warnings)
        charted.extend(built)
    return charted


def _check_opening_is_empty(tracks: list[Track], tempo: TempoAnalysis) -> None:
    """Hold every instrument to the rule, whichever generator it comes from.

    Raises:
        HardRuleViolation: If a track has a note in an opening that is not part of the song.
    """
    if tempo.lead_in_end_s <= 0:
        return
    for track in tracks:
        for note in track.notes:
            if tempo.tempo_map.seconds_at(float(note.tick)) < tempo.lead_in_end_s:
                raise HardRuleViolation(
                    f"{track.instrument.value}/{track.difficulty.value} has a note at tick "
                    f"{note.tick}, in the opening that ends at {tempo.lead_in_end_s:.1f} s"
                )


def _report_track(instrument: Instrument, item: ChartedTrack, warnings: list[str]) -> None:
    """Say what was removed as vocal bleed, and whether the temporary chord limit is on."""
    if item.quiet and item.quiet_limits is not None:
        log.info(
            "    %s: %d notes are %g dB or more below the median note%s, at %s s",
            instrument.value,
            len(item.quiet),
            item.quiet_limits.below_median_db,
            " and were removed" if item.quiet_limits.enabled else "; the rule is off, so they stay",
            ", ".join(f"{note.time_s:.1f}" for note in item.quiet),
        )
    removed = [note for note in item.bleed if note.removed]
    if removed:
        log.info(
            "    %s: removed %d notes as vocal bleed, at %s s",
            instrument.value,
            len(removed),
            ", ".join(f"{note.time_s:.1f}" for note in removed),
        )
    for note in item.bleed:
        if note.vocal_dominant:
            log.debug(
                "    %8.2f s %s %s",
                note.time_s,
                "removed" if note.removed else "kept   ",
                note.reason(),
            )
    if item.chord_limit_adjusted:
        warnings.append(
            f"{instrument.value}: this stem is unusually flat, probably heavy distortion, so the "
            f"temporary chord limit is in force ({item.chord_limit:.2f} instead of the fixed "
            f"limit). Chords and single notes may be mixed up here."
        )
    _report_level(instrument, item, warnings)
    _report_drums(item)
    _report_drum_level(item, warnings)


def _unverified_drums(item: ChartedTrack) -> str:
    """Say that toms and crash are not verified, and how many of them this chart has."""
    counts = item.drum_chart.unverified_counts(item.track) if item.drum_chart else {}
    toms = sum(count for gem, count in counts.items() if gem.endswith("_tom"))
    return (
        "drums: toms and crash are not verified on real data, the one reference has too few of "
        f"them (this chart: {toms} tom gems, {counts.get('green_cymbal', 0)} crashes)"
    )


def _report_drums(item: ChartedTrack) -> None:
    """Say what the drum stem was heard to hold, and what had to give way."""
    drum = item.drum_chart
    if drum is None:
        return
    log.info(
        "    drums/%s: %d positions from %d hits found in %.1f s (detectors: %s); %d hits shared a "
        "tick, %d pads left out for two hands",
        item.track.difficulty.value,
        len({note.tick for note in item.track.notes}),
        len(drum.analysis.hits),
        drum.analysis.seconds,
        ", ".join(f"{name} {count}" for name, count in drum.analysis.detector_hits.items()),
        drum.merged_on_one_tick,
        drum.pads_dropped,
    )
    log.info(
        "    drums/%s gems: %s",
        item.track.difficulty.value,
        ", ".join(f"{name} {count}" for name, count in drum.gem_counts(item.track).items() if count),
    )


def _report_drum_level(item: ChartedTrack, warnings: list[str]) -> None:
    """Say what a drum level came to, and warn about every soft target it misses."""
    measures = item.drum_measures
    if measures is None:
        return
    level = item.track.difficulty.value
    log.info(
        "    drums/%s: %d positions (%.0f%% of Expert), %.2f gems each, on the beat %.0f%%, "
        "sixteenths %.0f%%, shortest gap %.2f beats; gems %s",
        level,
        measures.positions,
        measures.position_ratio * 100,
        measures.gems_per_position,
        measures.on_beat_share * 100,
        measures.sixteenth_share * 100,
        measures.min_gap_beats,
        ", ".join(f"{gem} {share:.0%}" for gem, share in measures.gem_shares.items() if share),
    )
    missed = [target for target in item.soft_targets if not target.in_range]
    if missed:
        warnings.append(
            f"drums/{level} is outside its soft targets: "
            + ", ".join(
                f"{target.name} {target.value:.2f} (wanted {target.low:g} to {target.high:g})"
                for target in missed
            )
        )


def _drum_analysis(item: ChartedTrack) -> dict[str, object]:
    """What ``analysis.json`` says about a drum level beyond the common numbers."""
    counts = DrumChart.gem_counts(item.track)
    common: dict[str, object] = {
        "gems_by_kind": counts,
        "not_verified": {
            "parts": sorted(piece.value for piece in UNVERIFIED_PIECES),
            "gems": {gem.value: counts[gem.value] for gem in DrumGem if gem in UNVERIFIED_GEMS},
        },
    }
    drum = item.drum_chart
    if drum is None:
        return common
    return {
        **common,
        "hits_heard": len(drum.analysis.hits),
        "detector_hits": dict(drum.analysis.detector_hits),
        "strong_hit_levels": {key: round(value, 4) for key, value in drum.analysis.strong_levels.items()},
        "hits_sharing_a_tick": drum.merged_on_one_tick,
        "pads_left_out_for_two_hands": drum.pads_dropped,
        "analysis_seconds": round(drum.analysis.seconds, 3),
    }


def _report_orange(instrument: Instrument, item: ChartedTrack, warnings: list[str]) -> None:
    """Say which pitches a level's orange notes are, and warn if nearly all are the same one."""
    orange = item.orange_pitches
    level = item.track.difficulty.value
    if orange is None or orange.notes == 0:
        return
    log.info(
        "    %s/%s: orange notes by pitch: %s",
        instrument.value,
        level,
        ", ".join(f"{name} {count}" for name, count in orange.counts),
    )
    if orange.is_one_pitch:
        warnings.append(
            f"{instrument.value}/{level}: orange is one pitch: {orange.counts[0][0]} is "
            f"{orange.top_share:.0%} of its {orange.notes} orange notes (limit {orange.limit:.0%})"
        )


def _report_level(instrument: Instrument, item: ChartedTrack, warnings: list[str]) -> None:
    """Say what a difficulty came to, and warn about every soft target it misses."""
    _report_orange(instrument, item, warnings)
    measures = item.measures
    level = item.track.difficulty.value
    if measures is None:
        return
    log.info(
        "    %s/%s: %d positions (%.0f%% of Expert), chords %.0f%%, on the beat %.0f%%, "
        "sustains %.0f%%, shortest gap %.2f s, auto HOPO %.1f%%, forced to strum %d, "
        "hand travel %.2f",
        instrument.value,
        level,
        measures.positions,
        measures.position_ratio * 100,
        measures.chord_share * 100,
        measures.on_beat_share * 100,
        measures.sustain_share * 100,
        measures.min_gap_s,
        measures.auto_hopo_share * 100,
        measures.forced_strums,
        measures.hand_travel,
    )
    missed = [target for target in item.soft_targets if not target.in_range]
    if missed:
        warnings.append(
            f"{instrument.value}/{level} is outside its soft targets: "
            + ", ".join(
                f"{target.name} {target.value:.2f} (wanted {target.low:g} to {target.high:g})"
                for target in missed
            )
        )


def _finite_or_none(value: float) -> float | None:
    return value if math.isfinite(value) else None


def _level_analysis(item: ChartedTrack) -> dict[str, object]:
    """What ``analysis.json`` says about a difficulty: its numbers and its soft targets."""
    if item.measures is not None:
        measures = asdict(item.measures)
    elif item.drum_measures is not None:
        measures = asdict(item.drum_measures)
        measures["min_gap_beats"] = _finite_or_none(measures["min_gap_beats"])
    else:
        return {}
    measures["min_gap_s"] = _finite_or_none(measures["min_gap_s"])
    return {
        "measures": measures,
        "soft_targets": {
            target.name: {
                "value": _finite_or_none(target.value),
                "low": target.low,
                "high": _finite_or_none(target.high),
                "in_range": target.in_range,
            }
            for target in item.soft_targets
        },
    }


def _analysis(
    config: BuildConfig,
    audio: AudioData,
    stems: StemSet,
    presence: dict[str, StemPresence],
    tempo: TempoAnalysis,
    charted: list[ChartedTrack],
    encoded: list[EncodedAudio],
    difficulties: dict[Instrument, int],
    preview_start_ms: int,
    warnings: list[str],
    timings_s: dict[str, float],
    click_schedule: ClickSchedule | None,
    ear_test: dict[str, int] | None = None,
) -> dict[str, object]:
    charts: dict[str, dict[str, dict[str, object]]] = {}
    for item in charted:
        track = item.track
        per_tick: dict[int, int] = {}
        for note in track.notes:
            per_tick[note.tick] = per_tick.get(note.tick, 0) + 1
        sustained = {note.tick for note in track.notes if note.length > 0}
        entry: dict[str, object] = {
            "gems": len(track.notes),
            "positions": len(per_tick),
            "chord_positions": sum(count > 1 for count in per_tick.values()),
            "sustained_positions": len(sustained),
            "positions_per_second": round(len(per_tick) / stems.duration_s, 3),
            **_level_analysis(item),
        }
        # An instrument that may not have chords has no chord limit, and bass is not checked for bleed.
        if track.difficulty is Difficulty.EXPERT and item.chord_limit > 0:
            entry["chord_limit"] = {
                "used": round(item.chord_limit, 3),
                "temporary_distortion_limit_in_force": item.chord_limit_adjusted,
            }
            entry["vocal_bleed"] = {
                "removed_count": sum(note.removed for note in item.bleed),
                "vocal_dominant_notes": [
                    {
                        "time_s": round(note.time_s, 3),
                        "vocal_over_stem_db": round(note.vocal_over_stem_db, 1),
                        "stem_level_db": round(note.stem_level_db, 1),
                        "stem_sustain": round(note.stem_sustain, 2),
                        "removed": note.removed,
                        "reason": note.reason() if note.removed else None,
                    }
                    for note in item.bleed
                    if note.vocal_dominant
                ],
            }
        if item.orange_pitches is not None:
            entry["orange_pitches"] = item.orange_pitches.as_dict()
        if item.quiet_limits is not None:
            entry["quiet_notes"] = {
                "enabled": item.quiet_limits.enabled,
                "below_median_db": item.quiet_limits.below_median_db,
                "notes": [
                    {
                        "time_s": round(note.time_s, 3),
                        "below_median_db": round(note.below_median_db, 1),
                        "removed": note.removed,
                    }
                    for note in item.quiet
                ],
            }
        if track.instrument is Instrument.DRUMS:
            entry["drums"] = _drum_analysis(item)
        charts.setdefault(track.instrument.value, {})[track.difficulty.value] = entry
    return {
        "schema_version": 2,
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
            "estimated_bpm": tempo.estimated_bpm and round(tempo.estimated_bpm, 3),
            "method": tempo.method,
            "decision": tempo.decision,
            "max_beat_drift_limit_ms": tempo.max_beat_drift_ms,
            "tempo_event_count": len(tempo.tempo_map.tempos),
            "tempo_events": [
                {**asdict(event), **explanation}
                for event, explanation in zip(tempo.tempo_map.tempos, tempo.event_explanations())
            ],
            "fit": tempo.final and asdict(tempo.final),
            "one_tempo_fit": tempo.one_tempo and asdict(tempo.one_tempo),
            "off_tempo_share": round(tempo.off_tempo_share, 3),
            "tempo_strength": round(tempo.tempo_strength, 4),
            "beat_phase": tempo.beat_phase
            and {
                "kick_ratio": round(tempo.beat_phase.kick_ratio, 2),
                "snare_ratio": round(tempo.beat_phase.snare_ratio, 2),
                "section_agreement": round(tempo.beat_phase.section_agreement, 2),
                "confidence": round(tempo.beat_phase.confidence, 1),
                "moved_half_a_beat": tempo.beat_phase.half_beat_off,
            },
            "unfit_lead_in": {
                "end_s": round(tempo.lead_in_end_s, 3),
                "onsets_on_grid": round(tempo.lead_in_on_grid, 3),
                "song_start_s": round(song_start_s(tempo), 3),
            }
            if tempo.lead_in_end_s > 0
            else None,
            "time_signature_events": [asdict(s) for s in tempo.tempo_map.time_signatures],
            "meter": tempo.meter
            and {
                "time_signature": tempo.meter.label,
                "first_downbeat_s": tempo.meter.first_downbeat_s
                and round(tempo.meter.first_downbeat_s, 3),
                "confidence": round(tempo.meter.confidence, 2),
                "section_agreement": round(tempo.meter.section_agreement, 2),
                "low_confidence": tempo.meter.low_confidence,
            },
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
        "not_verified_on_real_data": sorted(
            instrument.value for instrument in UNVERIFIED_INSTRUMENTS if instrument.value in charts
        ),
        "difficulty_hard_rules": list(HARD_RULES),
        **({"drum_hard_rules": [*DRUM_HARD_RULES, *LEVEL_HARD_RULES]} if "drums" in charts else {}),
        "song_ini": {
            "preview_start_time_ms": preview_start_ms,
            "difficulty": {inst.value: tier for inst, tier in difficulties.items()},
        },
        "click_overlay": click_schedule
        and {
            "file": f"{CLICK_DIR}/{CLICK_FILE}",
            "clicks": int(click_schedule.times.size),
            "downbeats": int(click_schedule.is_downbeat.sum()),
        },
        "drum_ear_test": ear_test
        and {"folder": EAR_TEST_DIR, "clicks_per_file": ear_test},
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

    stages = _Stages(_BASE_STAGE_COUNT + int(config.click_overlay) + int(config.drum_ear_test))
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
        pitched = np.sum(
            [stems.stems[name] for name in ("bass", "guitar", "piano", "other")], axis=0
        )
        tempo = estimate_tempo_map(
            analysis_mono(audio.samples, audio.samplerate),
            bpm_override=config.bpm_override,
            max_beat_drift_s=config.max_beat_drift_ms / 1000.0,
            drums=analysis_mono(stems.stems["drums"], stems.samplerate),
            harmonic=analysis_mono(pitched, stems.samplerate),
            bass=analysis_mono(stems.stems["bass"], stems.samplerate),
        )
        if tempo.is_fallback:
            warnings.append("beat tracking failed; the chart uses a fixed fallback tempo")
        log.info(
            "    %.2f BPM (%s), %d tempo events, %.0f%% of onsets on the sixteenth grid",
            tempo.bpm,
            tempo.method,
            len(tempo.tempo_map.tempos),
            tempo.on_grid_ratio * 100,
        )
        log.info("    why: %s", tempo.decision)
        if tempo.lead_in_end_s > 0:
            warnings.append(
                f"the first {tempo.lead_in_end_s:.1f} s do not fit the song's grid (only "
                f"{tempo.lead_in_on_grid:.0%} of their onsets are on it): they are taken not to be "
                f"part of the song, and no instrument gets a note there"
            )
        meter = tempo.meter
        if meter is not None and meter.first_downbeat_s is not None:
            log.info(
                "    %s, first downbeat at %.3f s (confidence %.2f, %.0f%% of sections agree)",
                meter.label,
                meter.first_downbeat_s,
                meter.confidence,
                meter.section_agreement * 100,
            )
            if meter.low_confidence:
                warnings.append(
                    f"bar lines are uncertain (confidence {meter.confidence:.2f}, "
                    f"{meter.section_agreement:.0%} of sections agree): check where the first "
                    f"downbeat falls with --click-overlay"
                )

    with stages.stage("Chart instruments"):
        charted = _build_tracks(config, stems, presence, tempo, warnings)
        tracks = [item.track for item in charted]
        _check_opening_is_empty(tracks, tempo)
        if not tracks:
            raise NoPlayableInstrumentError(
                "No requested instrument produced a chart, so the song would be unplayable. "
                + " ".join(warnings)
            )

    config.output_dir.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".build-", dir=config.output_dir))
    try:
        with stages.stage("Package song folder"):
            chart = Chart(config.metadata, tempo.tempo_map, tracks, opening_sections(tempo))
            DotChartExporter().export(chart, temporary)

            plan = plan_audio(presence, config.instruments)
            encoded = write_audio_files(stems.stems, stems.samplerate, plan, temporary)

            song_length_ms = round(stems.duration_s * 1000)
            preview_start_ms = preview_start_ms_of(stems)
            difficulties: dict[Instrument, int] = {}
            for track in tracks:
                difficulties[track.instrument] = max(
                    difficulties.get(track.instrument, 0),
                    difficulty_tier(len({note.tick for note in track.notes}), stems.duration_s),
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

        schedule: ClickSchedule | None = None
        if config.click_overlay:
            with stages.stage("Write click overlay"):
                schedule = write_click_overlay(
                    temporary / DotChartExporter.file_name,
                    audio,
                    temporary / CLICK_DIR / CLICK_FILE,
                )

        ear_test: dict[str, int] | None = None
        if config.drum_ear_test:
            with stages.stage("Write drum listening files"):
                if any(track.instrument is Instrument.DRUMS for track in tracks):
                    ear_test = write_drum_ear_test(
                        temporary / DotChartExporter.file_name,
                        analysis_mono(stems.stems["drums"], stems.samplerate),
                        temporary / EAR_TEST_DIR,
                    )
                else:
                    warnings.append("--drum-ear-test: there is no drum chart to listen to")

        analysis = _analysis(
            config,
            audio,
            stems,
            presence,
            tempo,
            charted,
            encoded,
            difficulties,
            preview_start_ms,
            warnings,
            stages.timings_s,
            schedule,
            ear_test,
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


def preview_start_ms_of(stems: StemSet) -> int:
    """Where the song list's preview starts: the loudest window of the stems together."""
    return best_preview_start_ms(analysis_mono(_full_mix(stems), stems.samplerate), ANALYSIS_SAMPLERATE)
