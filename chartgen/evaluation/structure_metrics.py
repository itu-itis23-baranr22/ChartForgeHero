"""How a song's structure compares with a human chart: sections, star power and the preview.

A section boundary matches a human one within one bar, measured on our tempo map; a whole bar off still
counts. Two bars would be too lenient: on Californication a boundary every 4 bars scores F1 0.62 within two bars, against 0.38 at
most within one. Naive boundaries every N bars are reported next to ours, as the reductions are.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np

from chartgen.core.timing import TempoMap

NAIVE_EVERY_BARS = (4, 8, 16)
"""Naive boundaries every N bars from where the song starts: the baselines a method has to beat."""
NAIVE_SEARCH_BARS = (4, 6, 8, 12, 16)
"""For the best naive score, these periods at every offset. Choosing the offset by the human chart
flatters the naive method, so this is reported, not required."""
_ON_A_LINE_S = 0.01


def bar_lines_s(tempo_map: TempoMap, end_s: float) -> np.ndarray:
    """The time of every bar line of ``tempo_map`` from its start to ``end_s``."""
    ticks = tempo_map.bar_lines(end_s)
    return tempo_map.seconds_at(ticks.astype(np.float64)) if ticks.size else np.empty(0)


def _bar_lengths(bars_s: np.ndarray, times: np.ndarray) -> np.ndarray:
    """The length of the bar that holds each time; past the last bar line, the last bar's length."""
    if bars_s.size < 2:
        return np.full(times.shape, np.inf)
    lengths = np.diff(bars_s)
    index = np.clip(np.searchsorted(bars_s, times, side="right") - 1, 0, lengths.size - 1)
    return lengths[index]


def match_within(mine: np.ndarray, human: np.ndarray, tolerances: np.ndarray) -> int:
    """How many pairs match one to one, each human time with its own tolerance, closest first."""
    pairs = sorted(
        (abs(m - h), i, j)
        for i, m in enumerate(mine)
        for j, h in enumerate(human)
        if abs(m - h) <= tolerances[j] + 1e-9
    )
    used_mine: set[int] = set()
    used_human: set[int] = set()
    for _, i, j in pairs:
        if i not in used_mine and j not in used_human:
            used_mine.add(i)
            used_human.add(j)
    return len(used_mine)


def boundary_scores(mine_s: Iterable[float], human_s: Iterable[float], bars_s: np.ndarray) -> dict[str, float]:
    """Precision, recall and F1 of section starts, each human start matched within its bar."""
    mine = np.array(sorted(mine_s), dtype=np.float64)
    human = np.array(sorted(human_s), dtype=np.float64)
    hits = match_within(mine, human, _bar_lengths(bars_s, human))
    precision = hits / mine.size if mine.size else 0.0
    recall = hits / human.size if human.size else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3), "mine": int(mine.size), "human": int(human.size)}


def naive_section_baselines(human_s: Sequence[float], bars_s: np.ndarray, start_s: float) -> dict[str, object]:
    """F1 of boundaries every N bars, from the first bar line at or after ``start_s``, and the best
    period and offset when the human chart is allowed to choose them."""
    lines = bars_s[bars_s >= start_s - _ON_A_LINE_S]
    result: dict[str, object] = {
        f"every_{period}_bars": boundary_scores(lines[::period], human_s, bars_s)["f1"] for period in NAIVE_EVERY_BARS
    }
    best = (0.0, 0, 0)
    for period in NAIVE_SEARCH_BARS:
        for offset in range(period):
            score = boundary_scores(lines[offset::period], human_s, bars_s)["f1"]
            if score > best[0]:
                best = (score, period, offset)
    result["best_naive"] = {"f1": best[0], "every_bars": best[1], "offset_bars": best[2]}
    return result


def star_power_summary(
    phrases: Sequence[tuple[float, float]],
    bars_s: np.ndarray,
    duration_s: float,
    notes_s: np.ndarray | None = None,
) -> dict[str, float | int | None]:
    """Plain numbers about star power phrases given as (start, end) in seconds, on a chart's bars."""
    if not phrases:
        return {"phrases": 0}
    starts = np.array([start for start, _ in phrases])
    ends = np.array([end for _, end in phrases])
    lengths = (ends - starts) / _bar_lengths(bars_s, starts)
    on_a_line = [bars_s.size and np.min(np.abs(bars_s - start)) <= _ON_A_LINE_S for start in starts]
    summary: dict[str, float | int | None] = {
        "phrases": len(phrases),
        "per_minute": round(len(phrases) / (duration_s / 60.0), 2) if duration_s > 0 else None,
        "median_length_bars": round(float(np.median(lengths)), 2),
        "on_a_bar_line": round(float(np.mean(on_a_line)), 3),
        "median_gap_s": round(float(np.median(np.diff(starts))), 1) if starts.size > 1 else None,
    }
    if notes_s is not None:
        inside = [int(np.sum((notes_s >= start) & (notes_s < end))) for start, end in phrases]
        summary["median_notes_inside"] = float(np.median(inside))
        summary["fewest_notes_inside"] = int(min(inside))
    return summary


def section_at(time_s: float, sections: Sequence[tuple[float, str]]) -> str | None:
    """The name of the section that holds ``time_s``, or None before the first one."""
    name = None
    for start, section in sorted(sections):
        if start <= time_s + 1e-9:
            name = section
    return name


def preview_comparison(
    mine_s: float, human_s: float | None, human_sections: Sequence[tuple[float, str]]
) -> dict[str, object]:
    """Where our preview starts against the human's, and in which human section each lies."""
    result: dict[str, object] = {"mine_s": round(mine_s, 3), "mine_section": section_at(mine_s, human_sections)}
    if human_s is not None:
        result.update(
            {
                "human_s": round(human_s, 3),
                "human_section": section_at(human_s, human_sections),
                "apart_s": round(abs(mine_s - human_s), 1),
            }
        )
    return result
