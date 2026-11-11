"""Listening files for the drum chart: the drum stem with a click on every hit of one part of the kit.

One file per part, so each can be judged on its own: every click should fall on that part, and that part
should not be heard without a click. The click times come from reading the written ``notes.chart`` back,
as for the click overlay: what you hear is what the game will read.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.clonehero.click_overlay import CLICK_DIR, _burst, tempo_map_from_chart
from chartgen.clonehero.validate import ValidationReport, parse_chart
from chartgen.core.drums import GEM_FOR_PIECE, DrumGem, DrumPiece
from chartgen.errors import PackagingError

EAR_TEST_DIR = CLICK_DIR
EAR_TEST_FILES: dict[str, tuple[DrumPiece, ...]] = {
    "drums_kick.wav": (DrumPiece.KICK,),
    "drums_snare.wav": (DrumPiece.SNARE,),
    "drums_hihat.wav": (DrumPiece.HI_HAT,),
    "drums_ride.wav": (DrumPiece.RIDE,),
    "drums_crash.wav": (DrumPiece.CRASH,),
    "drums_toms.wav": (DrumPiece.HIGH_TOM, DrumPiece.MID_TOM, DrumPiece.FLOOR_TOM),
}
"""Toms share one file: there are few of them, and which tom it is matters less than whether it is one."""

CLICK_HZ = 2500.0
"""Above the kick, snare and toms, and short enough not to hide a cymbal."""
CLICK_LEVEL = 0.5
STEM_LEVEL = 0.7
_PEAK_CEILING = 0.99
_SECTION = "ExpertDrums"
_CYMBAL_FLAGS = {66: 2, 67: 3, 68: 4}


def chart_drum_gems(text: str) -> dict[int, set[DrumGem]]:
    """Read the Expert drum gems of each tick back from a written chart."""
    parsed = parse_chart(text, ValidationReport())
    pads: dict[int, set[int]] = {}
    flags: dict[int, set[int]] = {}
    for event in parsed.sections.get(_SECTION, []):
        parts = event.args.split()
        if event.type != "N" or len(parts) != 2 or not parts[0].isdigit():
            continue
        value = int(parts[0])
        if value <= 4:
            pads.setdefault(event.tick, set()).add(value)
        elif value in _CYMBAL_FLAGS:
            flags.setdefault(event.tick, set()).add(_CYMBAL_FLAGS[value])
    return {
        tick: {DrumGem.of(lane, lane in flags.get(tick, set())) for lane in lanes}
        for tick, lanes in pads.items()
    }


def write_drum_ear_test(chart_path: Path, drums: np.ndarray, folder: Path) -> dict[str, int]:
    """Write one file per part of the kit into ``folder`` and return how many clicks each has.

    Args:
        chart_path: The written ``notes.chart``.
        drums: The drum stem, mono at :data:`ANALYSIS_SAMPLERATE`.
        folder: Where the files go, normally the song's ``debug`` folder.

    Raises:
        PackagingError: If the chart is unusable or a file cannot be written.
    """
    text = chart_path.read_text(encoding="utf-8-sig")
    tempo_map = tempo_map_from_chart(text)
    gems = chart_drum_gems(text)
    burst = _burst(CLICK_HZ, CLICK_LEVEL, ANALYSIS_SAMPLERATE)
    counts: dict[str, int] = {}
    try:
        folder.mkdir(parents=True, exist_ok=True)
        for name, pieces in EAR_TEST_FILES.items():
            wanted = {GEM_FOR_PIECE[piece] for piece in pieces}
            ticks = np.array(sorted(tick for tick, found in gems.items() if found & wanted), dtype=np.float64)
            clicks = np.zeros(drums.size, dtype=np.float32)
            for time in tempo_map.seconds_at(ticks) if ticks.size else ():
                start = int(round(time * ANALYSIS_SAMPLERATE))
                end = min(start + burst.size, clicks.size)
                if 0 <= start < clicks.size:
                    clicks[start:end] += burst[: end - start]
            mixed = drums.astype(np.float32) * STEM_LEVEL + clicks
            peak = float(np.abs(mixed).max()) if mixed.size else 0.0
            if peak > _PEAK_CEILING:
                mixed *= _PEAK_CEILING / peak
            sf.write(str(folder / name), mixed, ANALYSIS_SAMPLERATE, format="WAV", subtype="PCM_16")
            counts[name] = int(ticks.size)
    except (sf.LibsndfileError, RuntimeError, OSError) as error:
        raise PackagingError(f"Could not write the drum listening files: {error}") from error
    return counts
