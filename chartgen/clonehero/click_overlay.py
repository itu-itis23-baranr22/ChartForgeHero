"""A metronome over the original mix, to check a tempo map by ear.

The click times come from reading the written ``notes.chart`` back, not from the
tempo map in memory: what you hear is what the game will read.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from chartgen.audio.io import AudioData
from chartgen.clonehero.validate import ValidationReport, parse_chart
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent
from chartgen.errors import PackagingError

CLICK_FILE = "debug_click.wav"

BEAT_HZ = 1000.0
DOWNBEAT_HZ = 2000.0
"""An octave higher, so that bar lines stand out without looking at a screen."""
CLICK_SECONDS = 0.035
CLICK_DECAY_SECONDS = 0.008
BEAT_LEVEL = 0.45
DOWNBEAT_LEVEL = 0.7
MIX_LEVEL = 0.6
_PEAK_CEILING = 0.99


@dataclass(frozen=True)
class ClickSchedule:
    times: np.ndarray
    is_downbeat: np.ndarray


def tempo_map_from_chart(text: str) -> TempoMap:
    """Rebuild a tempo map from the [Song] and [SyncTrack] sections of .chart text.

    Raises:
        PackagingError: If those sections are missing or malformed.
    """
    report = ValidationReport()
    parsed = parse_chart(text, report)
    if "Resolution" not in parsed.fields or "SyncTrack" not in parsed.sections:
        raise PackagingError("The chart has no [SyncTrack] or Resolution to build clicks from")
    tempos: list[TempoEvent] = []
    signatures: list[TimeSignatureEvent] = []
    try:
        for event in parsed.sections["SyncTrack"]:
            parts = event.args.split()
            if event.type == "B":
                tempos.append(TempoEvent(event.tick, int(parts[0]) / 1000.0))
            elif event.type == "TS":
                exponent = int(parts[1]) if len(parts) > 1 else 2
                signatures.append(TimeSignatureEvent(event.tick, int(parts[0]), 2**exponent))
        return TempoMap(tempos, signatures, int(parsed.fields["Resolution"]))
    except (ValueError, IndexError) as error:
        raise PackagingError(f"The chart's [SyncTrack] is not usable: {error}") from error


def click_schedule(tempo_map: TempoMap, duration_s: float) -> ClickSchedule:
    """List every beat up to ``duration_s`` and mark the first beat of each bar.

    Tick 0 is left out: it is the start of the audio, not a beat that was detected.
    """
    end_tick = tempo_map.ticks_at(duration_s)
    signatures = tempo_map.time_signatures
    ticks: list[int] = []
    downbeats: list[bool] = []
    for index, signature in enumerate(signatures):
        stop = signatures[index + 1].tick if index + 1 < len(signatures) else end_tick
        ticks_per_beat = tempo_map.resolution * 4 // signature.denominator
        beat = 0
        while signature.tick + beat * ticks_per_beat < stop:
            ticks.append(signature.tick + beat * ticks_per_beat)
            downbeats.append(beat % signature.numerator == 0)
            beat += 1
    tick_array = np.array(ticks, dtype=np.float64)
    is_downbeat = np.array(downbeats, dtype=bool)
    keep = tick_array > 0
    return ClickSchedule(tempo_map.seconds_at(tick_array[keep]), is_downbeat[keep])


def _burst(frequency: float, level: float, samplerate: int) -> np.ndarray:
    t = np.arange(int(CLICK_SECONDS * samplerate)) / samplerate
    wave = level * np.sin(2 * np.pi * frequency * t) * np.exp(-t / CLICK_DECAY_SECONDS)
    return wave.astype(np.float32)


def render_click_overlay(audio: AudioData, schedule: ClickSchedule) -> np.ndarray:
    """Return the mix with clicks on top, in the mix's shape and never clipping."""
    clicks = np.zeros(audio.frames, dtype=np.float32)
    beat = _burst(BEAT_HZ, BEAT_LEVEL, audio.samplerate)
    downbeat = _burst(DOWNBEAT_HZ, DOWNBEAT_LEVEL, audio.samplerate)
    for time, is_downbeat in zip(schedule.times, schedule.is_downbeat):
        burst = downbeat if is_downbeat else beat
        start = int(round(time * audio.samplerate))
        end = min(start + len(burst), audio.frames)
        if start < audio.frames:
            clicks[start:end] += burst[: end - start]
    mixed = audio.samples * MIX_LEVEL + clicks[:, None]
    peak = float(np.abs(mixed).max())
    return mixed * (_PEAK_CEILING / peak) if peak > _PEAK_CEILING else mixed


def write_click_overlay(chart_path: Path, audio: AudioData, destination: Path) -> ClickSchedule:
    """Write ``destination`` from the chart file at ``chart_path`` and the original mix.

    Raises:
        PackagingError: If the chart is unusable or the file cannot be written.
    """
    tempo_map = tempo_map_from_chart(chart_path.read_text(encoding="utf-8-sig"))
    schedule = click_schedule(tempo_map, audio.duration_s)
    try:
        sf.write(
            str(destination),
            render_click_overlay(audio, schedule),
            audio.samplerate,
            format="WAV",
            subtype="PCM_16",
        )
    except (sf.LibsndfileError, RuntimeError, OSError) as error:
        raise PackagingError(f"Could not write {destination.name}: {error}") from error
    return schedule
