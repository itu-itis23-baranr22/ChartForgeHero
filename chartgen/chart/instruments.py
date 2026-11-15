"""Per-instrument charting: which stem feeds which instrument, and who charts it."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace

import numpy as np

from chartgen.audio.drum_hits import DrumHitConfig, detect_drum_hits
from chartgen.audio.onsets import OnsetConfig
from chartgen.audio.pitch import PitchConfig
from chartgen.audio.quiet_notes import QuietNoteLimits, load_limits
from chartgen.chart.charter import ChartedTrack, build_expert_track
from chartgen.chart.difficulty import (
    BASS_CONFIG_PATH,
    DifficultyConfig,
    OrangePitches,
    Position,
    SoftTargets,
    check_soft_targets,
    count_orange_pitches,
    load_config,
    measure_track,
    reduce_track,
)
from chartgen.chart.drum_charter import build_drum_expert_track
from chartgen.chart.drum_difficulty import (
    DrumDifficultyConfig,
    gems_by_tick,
    measure_positions,
    reduce_drums,
)
from chartgen.chart.fret_mapping import BASS_WEIGHTS_PATH, FretWeights, load_weights
from chartgen.core.model import Instrument, Track
from chartgen.core.timing import TempoMap

STEM_FOR_INSTRUMENT: Mapping[Instrument, str] = {
    Instrument.GUITAR: "guitar",
    Instrument.BASS: "bass",
    Instrument.DRUMS: "drums",
    Instrument.KEYS: "piano",
}

CHARTABLE_INSTRUMENTS = frozenset(
    {Instrument.GUITAR, Instrument.BASS, Instrument.KEYS, Instrument.DRUMS}
)
"""Instruments with a chart generator, each at all four difficulties."""
UNVERIFIED_INSTRUMENTS = frozenset({Instrument.KEYS})
"""Charted, but only ever tested on synthetic audio: none of the songs measured so far has a piano
stem that counts as present, and the one human keyboard chart has 17 positions."""
VOCAL_BLEED_CHECKED = frozenset({Instrument.GUITAR, Instrument.KEYS})
"""Bass stays out. On the human bass chart we measured, 83% of the notes the check removed were
real, and on one song it removed 153 of 674 notes. Keys simply follow guitar: nothing was measured."""
QUIET_NOTES_CHECKED = frozenset({Instrument.BASS})
"""Where the kick can leak in. Whether anything is removed is set in ``quiet_notes.toml``."""
GUITAR_ONSETS = replace(OnsetConfig(), threshold_mad_k=2.5, local_ratio=1.5)
"""Guitar hears onsets with a lower local threshold than the defaults (3.0 and 1.75), which bass and keys
keep. A strummed, distorted guitar keeps its spectral flux high between attacks, so in dense passages the
defaults rejected most real notes: on the train references every missed human note had an envelope peak
within 70 ms, and the local threshold rejected 15 to 54% of them. Chosen on train (reference tuning step
2) as the best mean F1 that costs at most 0.03 of precision: with the vocal-bleed limits of that step,
recall 0.540 to 0.721, precision 0.849 to 0.822, F1 0.643 to 0.762 (Californication 0.794 to 0.801)."""
ONSET_SETTINGS: Mapping[Instrument, OnsetConfig] = {Instrument.GUITAR: GUITAR_ONSETS}
"""Instruments not listed use :class:`OnsetConfig` as it is."""
GUITAR_PITCH = replace(PitchConfig(), raw_repeat_percentile=14.0)
"""Guitar calls a note a repeat only if its plain spectrum is also alike enough (reference tuning step 3,
SPEC 43). On distorted guitar the log spectra of different chords are as alike as a chord played again,
so the fixed 0.95 made the contour flat on 74% of the lane changes of the human charts outside RHCP, and
the chart stood still. Chosen on train as the lightest setting that brings direction when the human moves
back above where it was before step 2 (0.315): 0.269 to 0.318, holding where the human holds 0.844 to
0.830 (the owner allows 0.03 less); Californication unchanged. Keys keep the default."""
PITCH_SETTINGS: Mapping[Instrument, PitchConfig] = {Instrument.GUITAR: GUITAR_PITCH}
"""Instruments not listed use :class:`PitchConfig` as it is. Bass reads its pitch elsewhere."""
GUITAR_REATTACKS = replace(OnsetConfig(), threshold_mad_k=1.0, local_ratio=1.1)
"""How guitar hears re-attacks that end a sustain, charted or not (reference tuning step 3, SPEC 43). The
12 dB release never fires on a distorted guitar before the next onset, so every note with room after it
was sustained, including those whose next strum the chart missed: 13.3% sustained on train against the
humans' 8.7%. With this, 9.2%, sustain F1 0.358 to 0.382. Bass and keys keep their ring times."""
REATTACK_SETTINGS: Mapping[Instrument, OnsetConfig] = {Instrument.GUITAR: GUITAR_REATTACKS}
"""Instruments listed here end a sustain at the next re-attack; others only at their release."""
ORANGE_CONTOUR_OFFSET = 36
"""Guitar's contour counts semitones above C2 (MIDI 36), :attr:`PitchConfig.fmin_hz`."""


def settings_for(instrument: Instrument) -> tuple[DifficultyConfig, FretWeights]:
    """Return an instrument's own preferences. Bass has its own files, so tuning it leaves guitar be.

    Keys use guitar's, with nothing to tune them on, and no soft targets: guitar's numbers would only
    warn about a guitar chart that keys need not resemble.
    """
    if instrument is Instrument.BASS:
        return load_config(BASS_CONFIG_PATH), load_weights(BASS_WEIGHTS_PATH)
    config = load_config()
    if instrument is Instrument.KEYS:
        config = replace(
            config,
            max_orange_pitch_share=None,
            expert_targets=SoftTargets(),
            levels={
                level: replace(settings, soft_targets=SoftTargets())
                for level, settings in config.levels.items()
            },
        )
    return config, load_weights()


def _orange_of(
    track: Track, positions: Sequence[Position], config: DifficultyConfig
) -> OrangePitches | None:
    if config.max_orange_pitch_share is None:
        return None
    if track.instrument is Instrument.GUITAR:
        # Guitar's "pitch" is the spectral center of a note or chord, not the note played.
        return count_orange_pitches(
            track,
            positions,
            config.max_orange_pitch_share,
            semitone_offset=ORANGE_CONTOUR_OFFSET,
            kind="spectral center",
        )
    return count_orange_pitches(track, positions, config.max_orange_pitch_share)


def drum_levels_for(
    expert: ChartedTrack, tempo_map: TempoMap, config: DrumDifficultyConfig | None = None
) -> list[ChartedTrack]:
    """Expert drums with their measures, then Hard, Medium and Easy made from them."""
    count = len({note.tick for note in expert.track.notes})
    strengths = expert.drum_chart.strengths if expert.drum_chart is not None else {}
    charted = [
        replace(expert, drum_measures=measure_positions(gems_by_tick(expert.track), tempo_map, count))
    ]
    for level in reduce_drums(expert.track, tempo_map, strengths, config).values():
        charted.append(
            ChartedTrack(
                level.track,
                expert.onset_count,
                soft_targets=level.soft_targets,
                drum_measures=level.measures,
            )
        )
    return charted


def build_tracks_for(
    instrument: Instrument,
    mono: np.ndarray,
    tempo_map: TempoMap,
    duration_s: float,
    vocals: np.ndarray | None = None,
    not_before_s: float = 0.0,
    quiet_limits: QuietNoteLimits | None = None,
    drum_config: DrumHitConfig | None = None,
    drum_levels: DrumDifficultyConfig | None = None,
) -> list[ChartedTrack]:
    """Return the charted tracks of ``instrument``, Expert first, then Hard, Medium and Easy.

    A stem without notes gives nothing.

    Args:
        instrument: What to chart.
        mono: Its stem.
        tempo_map: The song's tempo map.
        duration_s: Length of the song.
        vocals: The vocal stem, to find bleed in the instruments that are checked for it.
        not_before_s: Where an opening that is not part of the song ends. Nothing lands before it.
        quiet_limits: Replaces what ``quiet_notes.toml`` says, for the instruments it applies to.
        drum_config: Replaces what ``drum_hits.toml`` says.
        drum_levels: Replaces what ``drum_difficulty.toml`` says.
    """
    if instrument is Instrument.DRUMS:
        expert = build_drum_expert_track(
            detect_drum_hits(mono, drum_config), tempo_map, duration_s, not_before_s
        )
        return drum_levels_for(expert, tempo_map, drum_levels) if expert.track.notes else []
    config, weights = settings_for(instrument)
    expert = build_expert_track(
        instrument,
        mono,
        tempo_map,
        duration_s,
        onset_config=ONSET_SETTINGS.get(instrument),
        pitch_config=PITCH_SETTINGS.get(instrument),
        weights=weights,
        vocals=vocals if instrument in VOCAL_BLEED_CHECKED else None,
        not_before_s=not_before_s,
        quiet_limits=(quiet_limits or load_limits()) if instrument in QUIET_NOTES_CHECKED else None,
        reattack_config=REATTACK_SETTINGS.get(instrument),
    )
    if not expert.track.notes:
        return []
    measures = measure_track(expert.track, tempo_map, len(expert.positions))
    targets = tuple(check_soft_targets(measures, config.expert_targets))
    charted = [
        replace(
            expert,
            measures=measures,
            soft_targets=targets,
            orange_pitches=_orange_of(expert.track, expert.positions, config),
        )
    ]
    levels = reduce_track(instrument, expert.track, expert.positions, tempo_map, config, weights)
    for level in levels.values():
        charted.append(
            ChartedTrack(
                level.track,
                expert.onset_count,
                measures=level.measures,
                soft_targets=level.soft_targets,
                orange_pitches=_orange_of(level.track, expert.positions, config),
            )
        )
    return charted
