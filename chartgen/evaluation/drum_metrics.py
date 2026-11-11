"""How close a generated drum chart is to a human one, and to the kit's own recorded channels.

Per-part F1 is the measure that counts: position F1 cannot see which pad a hit is on. Direction, HOPOs
and sustains mean nothing on drums and are not measured.

The channels inside a ``.sng`` (``drums_1`` the kick, ``drums_2`` the snare, ``drums_3`` and any
``drums_4`` the rest) are what the drummer really played, before a human charter left anything out.
Comparing with them is diagnosis only, never an acceptance criterion: each microphone also hears the
other drums.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import numpy as np

from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.onsets import detect_onsets
from chartgen.core.drums import DrumGem
from chartgen.core.model import Track
from chartgen.core.timing import TempoMap
from chartgen.evaluation.metrics import NOTE_TOLERANCE_S, match_notes
from chartgen.evaluation.reference import ReferenceDrumHit

_PARTS: Mapping[str, Callable[[DrumGem], bool]] = {
    "kick": lambda gem: gem is DrumGem.KICK,
    "snare": lambda gem: gem is DrumGem.RED,
    "cymbal": lambda gem: gem.cymbal,
    "tom": lambda gem: gem.is_pad and gem is not DrumGem.RED and not gem.cymbal,
}
_HIHAT_OR_RIDE = frozenset({DrumGem.YELLOW_CYMBAL, DrumGem.BLUE_CYMBAL})
CHANNEL_PARTS: Mapping[str, str] = {"drums_1": "kick", "drums_2": "snare", "drums_3": "rest", "drums_4": "rest"}


def _f1(mine: np.ndarray, human: np.ndarray, tolerance_s: float) -> dict[str, float]:
    pairs = match_notes(np.sort(mine), np.sort(human), tolerance_s)
    precision = len(pairs) / mine.size if mine.size else 0.0
    recall = len(pairs) / human.size if human.size else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"f1": round(f1, 3), "precision": round(precision, 3), "recall": round(recall, 3)}


def chart_positions(track: Track, tempo_map: TempoMap) -> list[tuple[float, tuple[DrumGem, ...]]]:
    """The track's positions as (seconds, gems), in order."""
    by_tick: dict[int, list[DrumGem]] = {}
    for note in track.notes:
        by_tick.setdefault(note.tick, []).append(DrumGem.of_note(note))
    ticks = sorted(by_tick)
    times = tempo_map.seconds_at(np.array(ticks, dtype=np.float64)) if ticks else np.empty(0)
    return [(float(time), tuple(by_tick[tick])) for tick, time in zip(ticks, times)]


def _shares(positions: Sequence[tuple[float, Sequence[DrumGem]]]) -> dict[str, float]:
    counts = {gem: 0 for gem in DrumGem}
    for _, gems in positions:
        for gem in gems:
            counts[gem] += 1
    total = sum(counts.values()) or 1
    return {gem.value: counts[gem] / total for gem in DrumGem}


def drum_metrics(
    track: Track,
    tempo_map: TempoMap,
    human: Sequence[ReferenceDrumHit],
    tolerance_s: float = NOTE_TOLERANCE_S,
) -> dict[str, object]:
    """Compare a drum track with the human's hits of the same level."""
    mine = chart_positions(track, tempo_map)
    theirs = [(hit.time_s, hit.gems) for hit in human]
    result: dict[str, object] = {
        "positions_mine": len(mine),
        "positions_human": len(theirs),
        "position": _f1(np.array([t for t, _ in mine]), np.array([t for t, _ in theirs]), tolerance_s),
    }
    for part, wanted in _PARTS.items():
        result[part] = _f1(
            np.array([t for t, gems in mine if any(wanted(gem) for gem in gems)]),
            np.array([t for t, gems in theirs if any(wanted(gem) for gem in gems)]),
            tolerance_s,
        )
    # Hi-hat against ride: where both charts have a yellow or blue cymbal at the same time.
    mine_cymbals = [(t, gems) for t, gems in mine if _HIHAT_OR_RIDE & set(gems)]
    their_cymbals = [(t, gems) for t, gems in theirs if _HIHAT_OR_RIDE & set(gems)]
    pairs = match_notes(
        np.array([t for t, _ in mine_cymbals]), np.array([t for t, _ in their_cymbals]), tolerance_s
    )
    same = sum(bool(set(mine_cymbals[i][1]) & set(their_cymbals[j][1]) & _HIHAT_OR_RIDE) for i, j in pairs)
    result["hihat_ride_compared"] = len(pairs)
    result["hihat_ride_same_lane"] = round(same / len(pairs), 3) if pairs else None
    shares_mine, shares_human = _shares(mine), _shares(theirs)
    result["gem_shares"] = {
        gem: {"mine": round(shares_mine[gem], 3), "human": round(shares_human[gem], 3)} for gem in shares_mine
    }
    result["worst_gem_gap"] = round(max(abs(shares_mine[gem] - shares_human[gem]) for gem in shares_mine), 3)
    return result


def channel_metrics(
    track: Track,
    tempo_map: TempoMap,
    human: Sequence[ReferenceDrumHit],
    channels: Mapping[str, np.ndarray],
    tolerance_s: float = NOTE_TOLERANCE_S,
) -> dict[str, object]:
    """Diagnosis: the onsets of each recorded kit channel against our parts and the human's.

    Args:
        channels: Each channel mono at :data:`ANALYSIS_SAMPLERATE`, by its stem name (``drums_1``...).
    """
    mine = chart_positions(track, tempo_map)
    theirs = [(hit.time_s, hit.gems) for hit in human]
    wanted: Mapping[str, Callable[[DrumGem], bool]] = {
        "kick": _PARTS["kick"],
        "snare": _PARTS["snare"],
        "rest": lambda gem: gem.cymbal or _PARTS["tom"](gem),
    }
    onsets: dict[str, list[np.ndarray]] = {}
    for name, signal in sorted(channels.items()):
        part = CHANNEL_PARTS.get(name)
        if part is not None:
            onsets.setdefault(part, []).append(detect_onsets(signal, ANALYSIS_SAMPLERATE).times)
    result: dict[str, object] = {}
    for part, found in onsets.items():
        heard = np.sort(np.concatenate(found))
        result[part] = {
            "channel_onsets": int(heard.size),
            "mine": _f1(np.array([t for t, gems in mine if any(wanted[part](g) for g in gems)]), heard, tolerance_s),
            "human": _f1(np.array([t for t, gems in theirs if any(wanted[part](g) for g in gems)]), heard, tolerance_s),
        }
    return result
