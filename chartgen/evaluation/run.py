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
from chartgen.audio.presence import analyze_presence
from chartgen.audio.sections import find_sections
from chartgen.audio.separation import STEM_NAMES, Separator, StemSet, separate_with_cache
from chartgen.audio.tempo import TempoAnalysis, estimate_tempo_map
from chartgen.chart.charter import ChartedTrack
from chartgen.chart.difficulty import LANE_NAMES, LevelMeasures, load_config
from chartgen.chart.instruments import STEM_FOR_INSTRUMENT, build_tracks_for
from chartgen.chart.preview import LOUDEST_WINDOW, PREVIEW_LEAD_BARS, choose_preview
from chartgen.chart.sections import section_search_start_s, song_section_tick, song_sections, song_start_s
from chartgen.chart.star_power import place_star_power
from chartgen.core.model import Difficulty, Instrument, Track
from chartgen.core.timing import TempoMap
from chartgen.errors import ChartgenError
from chartgen.evaluation.drum_metrics import channel_metrics, drum_level_metrics, drum_metrics
from chartgen.evaluation.structure_metrics import (
    NAIVE_EVERY_BARS,
    bar_lines_s,
    boundary_scores,
    naive_section_baselines,
    preview_comparison,
    star_power_summary,
)
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
    load_drum_channels,
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
    ("hand_travel", "hand travel"),
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


_PITCHED_STEMS = ("bass", "guitar", "piano", "other")
"""The stems that carry chords, summed in this order, as a build sums them."""


@dataclass(frozen=True)
class AnalysisSignals:
    """What the evaluation reads from a reference's audio and stems: mono signals at the analysis rate.

    The stereo stems of a five-minute song take about 750 MB, these about 200 MB, so an evaluation
    makes these first and lets the stems go before anything else runs.
    """

    duration_s: float
    """Of the stems."""
    mix: np.ndarray
    """The whole song."""
    pitched: np.ndarray
    """The sum of :data:`_PITCHED_STEMS`, made mono."""
    stems: Mapping[str, np.ndarray]
    """Each stem the evaluation charts or listens to, by stem name."""
    keys_present: bool | None = None
    """Whether the keys stem passes the presence threshold, as in a build. None if not asked."""


def _summed(stems: StemSet, names: Sequence[str]) -> np.ndarray:
    """The sum of these stems, added into one array one stem at a time.

    The same additions in the same order as ``np.sum`` over the list, so the same samples, without
    first stacking every stem into one array of four or six times a stem's size.
    """
    total = stems.stems[names[0]].copy()
    for name in names[1:]:
        total += stems.stems[name]
    return total


def analysis_signals(song: ReferenceSong, stems: StemSet, keys: bool = False) -> AnalysisSignals:
    """Make the mono signals of ``song`` and its ``stems``. With ``keys``, also decide whether the keys
    stem is present, which needs the stereo stems."""
    names = {STEM_FOR_INSTRUMENT[instrument] for instrument in Instrument} | {"vocals"}
    keys_stem = STEM_FOR_INSTRUMENT[Instrument.KEYS]
    keys_present = None
    if keys:
        # As in a build, an absent stem gets no chart: scoring its bleed would mean nothing.
        everything = _summed(stems, STEM_NAMES)
        keys_present = analyze_presence(keys_stem, stems.stems[keys_stem], everything, stems.samplerate).present
        del everything
    if not keys_present:
        names.discard(keys_stem)
    pitched = _summed(stems, _PITCHED_STEMS)
    pitched_mono = analysis_mono(pitched, stems.samplerate)
    del pitched
    return AnalysisSignals(
        duration_s=stems.duration_s,
        mix=analysis_mono(song.audio.samples, song.audio.samplerate),
        pitched=pitched_mono,
        stems={name: analysis_mono(stems.stems[name], stems.samplerate) for name in sorted(names)},
        keys_present=keys_present,
    )


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
        if item.orange_pitches is not None:
            entry["orange_pitches"] = item.orange_pitches.as_dict()
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


def compare_structure(
    song: ReferenceSong,
    tempo: TempoAnalysis,
    signals: AnalysisSignals,
    ours: Mapping[Instrument, Sequence[Track]] | None = None,
) -> dict[str, object]:
    """Sections, star power and the preview against the human chart's, where it has them.

    Args:
        ours: Our levels of each charted instrument, the hardest first: their star power is placed as a
            build places it and measured as the human chart's is. Without them, ours is not measured.
    """
    tempo_map = tempo.tempo_map
    bars = bar_lines_s(tempo_map, signals.duration_s)
    mix = signals.mix
    found = find_sections(
        mix,
        signals.pitched,
        signals.stems["vocals"],
        tempo_map,
        signals.duration_s,
        song_start_s=section_search_start_s(tempo),
        after_opening=tempo.lead_in_end_s > 0,
    )
    mine = [(float(tempo_map.seconds_at(float(section.tick))), section.name) for section in song_sections(tempo, found)]
    human = [(section.time_s, section.name) for section in song.sections]
    sections: dict[str, object] = {
        "human": [{"time_s": round(time, 3), "name": name} for time, name in human],
        "mine": [{"time_s": round(time, 3), "name": name} for time, name in mine],
    }
    if human:
        human_times = [time for time, _ in human]
        sections["match"] = boundary_scores([time for time, _ in mine], human_times, bars)
        sections["naive"] = naive_section_baselines(human_times, bars, song_start_s(tempo))
    notes = {
        Instrument.GUITAR: [note.time_s for note in song.levels.get(Difficulty.EXPERT, ())],
        Instrument.BASS: [note.time_s for note in song.bass_levels.get(Difficulty.EXPERT, ())],
        Instrument.KEYS: [note.time_s for note in song.keys_levels.get(Difficulty.EXPERT, ())],
        Instrument.DRUMS: [hit.time_s for hit in song.drums.levels.get(Difficulty.EXPERT, ())],
    }
    star_power = {
        "human": {
            instrument.value: star_power_summary(
                [(phrase.start_s, phrase.end_s) for phrase in phrases],
                song.bars,
                song.audio.duration_s,
                np.array(notes[instrument]),
            )
            for instrument, phrases in song.star_power.items()
        },
        "mine": {},
    }
    for instrument, levels in (ours or {}).items():
        if not levels:
            continue
        plan = place_star_power(levels, tempo_map, signals.duration_s, song_section_tick(tempo))
        expert = levels[0].notes
        # Counted as the human chart's are: every gem on fretted instruments, every hit on drums.
        ticks = sorted({note.tick for note in expert}) if instrument is Instrument.DRUMS else [note.tick for note in expert]
        star_power["mine"][instrument.value] = star_power_summary(
            [(phrase.start_s, phrase.end_s) for phrase in plan.phrases],
            bars,
            signals.duration_s,
            tempo_map.seconds_at(np.array(ticks, dtype=np.float64)),
        )
    choice = choose_preview(found, mix, tempo_map, signals.duration_s, song_section_tick(tempo))
    preview = preview_comparison(choice.start_s, song.preview_start_s, human)
    preview.update({"rule": choice.rule, "leads_into": choice.leads_into})
    sections["strongest_change"] = round(found.strongest_change, 3)
    return {"sections": sections, "star_power": star_power, "preview": preview}


def evaluate_song(
    song: ReferenceSong, separator: Separator, cache_dir: Path
) -> dict[str, object]:
    """Run the analysis on one reference song and compare it with the human chart."""
    stems = separate_with_cache(song.source, song.audio, separator, cache_dir)
    signals = analysis_signals(song, stems, keys=bool(song.keys_levels))
    del stems  # the stereo stems are three quarters of an evaluation's memory and nothing needs them now
    mono = signals.mix
    tempo = estimate_tempo_map(
        mono,
        drums=signals.stems["drums"],
        harmonic=signals.pitched,
        bass=signals.stems["bass"],
    )
    vocals = signals.stems["vocals"]
    charted = build_tracks_for(
        Instrument.GUITAR,
        signals.stems[STEM_FOR_INSTRUMENT[Instrument.GUITAR]],
        tempo.tempo_map,
        signals.duration_s,
        vocals=vocals,
        not_before_s=tempo.lead_in_end_s,
    )

    duration = len(mono) / ANALYSIS_SAMPLERATE
    ours: dict[Instrument, list[Track]] = {}  # our levels of each instrument the human chart has, for star power
    result: dict[str, object] = {
        "bpm": round(tempo.bpm, 2),
        "tempo_method": tempo.method,
        "tempo_events": len(tempo.tempo_map.tempos),
        "time_signature": tempo.meter.label if tempo.meter else None,
        "human_time_signatures": [f"{n}/{d}" for n, d in song.signatures],
        "meter_confidence": round(tempo.bar_confidence, 2),
        "beat_split_in_two": bool(tempo.double_time and tempo.double_time.double),
        "snare_on_every_beat_share": tempo.double_time and round(tempo.double_time.both_parities_share, 3),
    }
    result.update(tempo_metrics(tempo.tempo_map, song.beats, song.bars, duration))
    if charted:
        result.update(chart_metrics(charted[0].track, tempo.tempo_map, song.notes))
        result["removed_as_vocal"] = sum(note.removed for note in charted[0].bleed)
        result["chord_limit_adjusted"] = charted[0].chord_limit_adjusted
        result["levels"] = compare_levels(charted, tempo.tempo_map, song)
        ours[Instrument.GUITAR] = [item.track for item in charted]
    if song.bass_levels:
        bass = build_tracks_for(
            Instrument.BASS,
            signals.stems[STEM_FOR_INSTRUMENT[Instrument.BASS]],
            tempo.tempo_map,
            signals.duration_s,
            not_before_s=tempo.lead_in_end_s,
        )
        if bass:
            result["bass"] = compare_levels(bass, tempo.tempo_map, song, song.bass_levels)
            ours[Instrument.BASS] = [item.track for item in bass]
    if song.keys_levels:
        result["keys_stem"] = "present" if signals.keys_present else "absent"
        if signals.keys_present:
            keys = build_tracks_for(
                Instrument.KEYS,
                signals.stems[STEM_FOR_INSTRUMENT[Instrument.KEYS]],
                tempo.tempo_map,
                signals.duration_s,
                vocals=vocals,
                not_before_s=tempo.lead_in_end_s,
            )
            if keys:
                result["keys"] = compare_levels(keys, tempo.tempo_map, song, song.keys_levels)
                ours[Instrument.KEYS] = [item.track for item in keys]
    human_drums = song.drums.levels.get(Difficulty.EXPERT)
    if human_drums:
        drums = build_tracks_for(
            Instrument.DRUMS,
            signals.stems[STEM_FOR_INSTRUMENT[Instrument.DRUMS]],
            tempo.tempo_map,
            signals.duration_s,
            not_before_s=tempo.lead_in_end_s,
        )
        if drums:
            entry = drum_metrics(drums[0].track, tempo.tempo_map, human_drums)
            entry["human_is_pro"] = song.drums.pro
            channels = load_drum_channels(song.source)
            if channels:
                entry["channels"] = channel_metrics(
                    drums[0].track, tempo.tempo_map, human_drums, channels
                )
            result["drums"] = entry
            ours[Instrument.DRUMS] = [item.track for item in drums]
            levels = drum_level_metrics(
                [item.track for item in drums], tempo.tempo_map, song.drums.levels
            )
            if levels:
                result["drum_levels"] = levels
    elif song.drums.skipped:
        result["drums_skipped"] = song.drums.skipped
    result["structure"] = compare_structure(song, tempo, signals, ours)
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
        song = None
        try:
            song = load_reference(path)
            songs[song.name] = evaluate_song(song, separator, cache_dir)
            splits[song.name] = split_of(path, root)
        except ChartgenError as error:
            log.warning("Skipping %s: %s", path.name, error)
            failures[path.name] = str(error)
        finally:
            # One reference in memory at a time: this one goes before the next is decoded.
            del song
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
        orange = levels[name].get("orange_pitches")
        if orange and orange["notes"]:
            pitches = ", ".join(f"{pitch} {count}" for pitch, count in orange["pitches"].items())
            counted = orange.get("counted", "pitch")
            warning = f"; orange is one {counted}" if orange["one_pitch"] else ""
            lines.append(f"{name} orange notes by {counted}: {pitches}{warning}")
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


def _keys_lines(name: str, song: dict[str, object]) -> list[str]:
    """Show a song's keys, or say why there is nothing to show."""
    if song.get("keys_stem") == "absent":
        return [f"Keys of {name}: the human chart has keys, but the piano stem is absent: no chart.", ""]
    return _level_table(f"Keys of {name}", song.get("keys", {}))  # type: ignore[arg-type]


def _drum_lines(name: str, song: dict[str, object]) -> list[str]:
    """Show a song's Expert drums against the human's, and the channels as diagnosis."""
    drums = song.get("drums")
    if not isinstance(drums, dict):
        skipped = song.get("drums_skipped")
        return [f"Drums of {name}: not compared: {skipped}", ""] if skipped else []
    pro = "" if drums["human_is_pro"] else "; the human chart is not Pro, so cymbals mean nothing"
    lines = [
        f"Drums of {name}, Expert ({drums['positions_mine']} positions mine, "
        f"{drums['positions_human']} human{pro})"
    ]
    for key, label in _DRUM_SHOWN:
        score = drums[key]
        lines.append(
            f"{label:20s} F1 {score['f1']:.3f}  P {score['precision']:.3f}  R {score['recall']:.3f}"
        )
    lane = drums["hihat_ride_same_lane"]
    lane_text = "-" if lane is None else f"{lane:.3f}"
    lines.append(f"{'hi-hat / ride':20s} same lane {lane_text} of {drums['hihat_ride_compared']} compared")
    lines.append(f"{'worst gem gap':20s} {drums['worst_gem_gap']:.3f}")
    shares = ", ".join(
        f"{gem} {value['mine']:.2f}/{value['human']:.2f}"
        for gem, value in drums["gem_shares"].items()
        if value["mine"] or value["human"]
    )
    lines.append(f"gem shares mine / human: {shares}")
    for part, value in drums.get("channels", {}).items():
        lines.append(
            f"channel {part} (diagnosis only): {value['channel_onsets']} onsets; "
            f"F1 mine {value['mine']['f1']:.3f}, human {value['human']['f1']:.3f}"
        )
    levels = song.get("drum_levels", {})
    if isinstance(levels, dict) and levels:
        lines.append("Lower levels: position F1 against the human, next to every Nth and beats first")
    for level, value in levels.items() if isinstance(levels, dict) else ():
        lines.append(
            f"{level:8s} {value['positions_mine']:5d} mine / {value['positions_human']:5d} human  "
            f"position {value['position']['f1']:.3f} (every Nth {value['every_nth_f1']:.3f}, "
            f"beats first {value['beats_first_f1']:.3f})  kick {value['kick']['f1']:.3f}  "
            f"snare {value['snare']['f1']:.3f}  cymbal {value['cymbal']['f1']:.3f}  "
            f"worst gem gap {value['worst_gem_gap']:.3f}"
        )
    lines.append("")
    return lines


def _structure_lines(name: str, song: dict[str, object]) -> list[str]:
    """Show a song's sections, star power and preview against the human chart's."""
    structure = song.get("structure")
    if not isinstance(structure, dict):
        return []
    sections = structure["sections"]
    lines = [f"Structure of {name}"]
    mine_names = ", ".join(section["name"] for section in sections["mine"]) or "none"
    if "match" in sections:
        match, naive = sections["match"], sections["naive"]
        best = naive["best_naive"]
        lines.append(
            f"sections: human {match['human']}, mine {match['mine']} ({mine_names}); boundary F1 within a bar "
            f"{match['f1']:.3f} (P {match['precision']:.3f}, R {match['recall']:.3f})"
        )
        lines.append(
            "naive from the song start: "
            + ", ".join(f"every {period} bars {naive[f'every_{period}_bars']:.3f}" for period in NAIVE_EVERY_BARS)
            + f"; best naive {best['f1']:.3f} (every {best['every_bars']} bars from bar {best['offset_bars']}, "
            "chosen by the human chart)"
        )
    else:
        lines.append(f"sections: the human chart has none; mine {len(sections['mine'])} ({mine_names})")
    for source in ("human", "mine"):
        summaries = structure["star_power"][source]
        parts = [
            f"{instrument} {value['phrases']} ({value['per_minute']}/min, {value['median_length_bars']} bar, "
            f"{value['on_a_bar_line']:.0%} on a bar line, gap "
            + (f"{value['median_gap_s']} s" if value["median_gap_s"] is not None else "-")
            + (f", notes inside {value['median_notes_inside']:g} median, {value['fewest_notes_inside']} fewest" if "median_notes_inside" in value else "")
            + ")"
            for instrument, value in summaries.items()
            if value["phrases"]
        ]
        lines.append(f"star power, {source}: " + ("; ".join(parts) if parts else "none"))
    preview = structure["preview"]
    led = f", {PREVIEW_LEAD_BARS} bars before {preview['leads_into']}" if preview.get("leads_into") else ""
    fallback = f", {preview['rule']}" if preview.get("rule") == LOUDEST_WINDOW else ""
    mine_text = f"mine {preview['mine_s']:.1f} s ({preview['mine_section'] or '-'}{led}{fallback})"
    if "human_s" in preview:
        lines.append(
            f"preview: {mine_text}, human {preview['human_s']:.1f} s ({preview['human_section'] or '-'}): "
            f"{preview['apart_s']:.1f} s apart"
        )
    else:
        lines.append(f"preview: {mine_text}; the human chart sets none")
    lines.append("")
    return lines


_DRUM_SHOWN = (
    ("position", "position"),
    ("kick", "kick"),
    ("snare", "snare"),
    ("cymbal", "cymbal"),
    ("tom", "tom (not verified)"),
)


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
            lines.extend(_keys_lines(name, report.songs[name]))
            lines.extend(_drum_lines(name, report.songs[name]))
            lines.extend(_structure_lines(name, report.songs[name]))
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
