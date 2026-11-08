"""How close a generated chart is to a human one. Every metric is a plain number per song."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from chartgen.core.model import Track
from chartgen.core.timing import TempoMap
from chartgen.evaluation.reference import ReferenceNote

NOTE_TOLERANCE_S = 0.07
"""Clone Hero's own hit window is about this wide."""
BEAT_TOLERANCE_S = 0.035
BAR_TOLERANCE_S = 0.06
HUMAN_SUSTAIN_BEATS = 0.5
"""Human charts write unsustained notes as a sixteenth, so longer notes count as sustained."""


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0


def match_notes(mine: np.ndarray, human: np.ndarray, tolerance: float) -> list[tuple[int, int]]:
    """Pair each of my notes with the closest unclaimed human note within ``tolerance``."""
    pairs: list[tuple[int, int]] = []
    used = np.zeros(human.size, dtype=bool)
    if human.size == 0:
        return pairs
    for index, time in enumerate(mine):
        order = np.argsort(np.abs(human - time))
        for candidate in order[:4]:
            if abs(human[candidate] - time) > tolerance:
                break
            if not used[candidate]:
                used[candidate] = True
                pairs.append((index, int(candidate)))
                break
    return pairs


def tempo_metrics(
    tempo_map: TempoMap, human_beats: np.ndarray, human_bars: np.ndarray, duration_s: float
) -> dict[str, float]:
    """Compare beats and bars with the human tempo map."""
    resolution = tempo_map.resolution
    last = int(tempo_map.ticks_at(duration_s) // resolution)
    beats = tempo_map.seconds_at(np.arange(1, last + 1, dtype=np.float64) * resolution)
    usable = human_beats[(human_beats > beats[0] - 1) & (human_beats < beats[-1] + 1)]
    errors = np.abs(beats[np.abs(beats[None, :] - usable[:, None]).argmin(axis=1)] - usable)

    bars: list[float] = []
    signatures = tempo_map.time_signatures
    end_tick = tempo_map.ticks_at(duration_s)
    for index, signature in enumerate(signatures):
        stop = signatures[index + 1].tick if index + 1 < len(signatures) else end_tick
        step = resolution * 4 / signature.denominator * signature.numerator
        bars.extend(np.arange(signature.tick, stop, step))
    mine_bars = tempo_map.seconds_at(np.array(bars[1:] or [0.0], dtype=np.float64))
    middle = human_bars[(human_bars > 1.0) & (human_bars < duration_s - 1.0)]
    nearest = np.abs(mine_bars[None, :] - middle[:, None]).min(axis=1)
    human_bpm = 60.0 / float(np.median(np.diff(human_beats)))
    return {
        "human_bpm": round(human_bpm, 2),
        "beat_error_median_ms": round(float(np.median(errors)) * 1000.0, 1),
        "beats_within_35ms": round(float(np.mean(errors <= BEAT_TOLERANCE_S)), 3),
        "bars_agreeing": round(float(np.mean(nearest <= BAR_TOLERANCE_S)), 3),
    }


def chart_metrics(
    track: Track,
    tempo_map: TempoMap,
    human: Sequence[ReferenceNote],
    tolerance_s: float = NOTE_TOLERANCE_S,
) -> dict[str, float]:
    """Compare note positions, direction, chords and sustains with the human chart."""
    by_tick: dict[int, list[int]] = {}
    lengths: dict[int, int] = {}
    for note in track.notes:
        by_tick.setdefault(note.tick, []).append(note.lane)
        lengths[note.tick] = max(lengths.get(note.tick, 0), note.length)
    ticks = sorted(by_tick)
    if not ticks:
        return {"note_f1": 0.0, "note_precision": 0.0, "note_recall": 0.0, "positions": 0}
    mine_times = tempo_map.seconds_at(np.array(ticks, dtype=np.float64))
    human_times = np.array([note.time_s for note in human])
    pairs = match_notes(mine_times, human_times, tolerance_s)

    precision = len(pairs) / len(ticks)
    recall = len(pairs) / max(1, len(human))
    result: dict[str, float] = {
        "positions": len(ticks),
        "human_positions": len(human),
        "note_precision": round(precision, 3),
        "note_recall": round(recall, 3),
        "note_f1": round(_f1(precision, recall), 3),
    }
    if len(pairs) < 2:
        return result

    pairs.sort()
    mine_centers = np.array([np.mean(by_tick[ticks[i]]) for i, _ in pairs])
    human_centers = np.array([np.mean(human[j].lanes) for _, j in pairs])
    # Direction is measured on the lowest lane, as human chords share their bottom note.
    mine_low = np.array([min(by_tick[ticks[i]]) for i, _ in pairs])
    human_low = np.array([min(human[j].lanes) for _, j in pairs])
    mine_step = np.sign(np.diff(mine_low))
    human_step = np.sign(np.diff(human_low))
    moving = human_step != 0
    result["direction_when_human_moves"] = (
        round(float(np.mean(mine_step[moving] == human_step[moving])), 3) if moving.any() else 0.0
    )
    result["direction_all_steps"] = round(float(np.mean(mine_step == human_step)), 3)
    result["lane_center_correlation"] = (
        round(float(np.corrcoef(mine_centers, human_centers)[0, 1]), 3)
        if mine_centers.std() > 0 and human_centers.std() > 0
        else 0.0
    )

    mine_chord = np.array([len(by_tick[ticks[i]]) > 1 for i, _ in pairs])
    human_chord = np.array([len(human[j].lanes) > 1 for _, j in pairs])
    result["chord_agreement"] = round(float(np.mean(mine_chord == human_chord)), 3)
    result["chord_share_mine"] = round(float(mine_chord.mean()), 3)
    result["chord_share_human"] = round(float(human_chord.mean()), 3)

    resolution = tempo_map.resolution
    beat_lengths = []
    for _, j in pairs:
        at = human[j].time_s
        ticks_start = tempo_map.ticks_at(float(at))
        ticks_end = tempo_map.ticks_at(float(at + human[j].length_s))
        beat_lengths.append((ticks_end - ticks_start) / resolution)
    human_sustained = np.array(beat_lengths) > HUMAN_SUSTAIN_BEATS
    mine_sustained = np.array([lengths[ticks[i]] > 0 for i, _ in pairs])
    both = float(np.sum(human_sustained & mine_sustained))
    sustain_precision = both / max(1.0, float(mine_sustained.sum()))
    sustain_recall = both / max(1.0, float(human_sustained.sum()))
    result["sustain_f1"] = round(_f1(sustain_precision, sustain_recall), 3)
    result["sustain_share_mine"] = round(float(mine_sustained.mean()), 3)
    result["sustain_share_human"] = round(float(human_sustained.mean()), 3)
    return result


def average(results: Sequence[dict[str, float]]) -> dict[str, float]:
    """Average every numeric metric that the songs report."""
    keys = {key for result in results for key in result}
    averages: dict[str, float] = {}
    for key in sorted(keys):
        values = [result[key] for result in results if isinstance(result.get(key), (int, float))]
        if values:
            averages[key] = round(float(np.mean(values)), 3)
    return averages
