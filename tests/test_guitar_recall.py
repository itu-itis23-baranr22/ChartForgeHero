"""Step 2 of the reference tuning: guitar Expert recall.

(a) In a fast song the snapping grid is the eighth note, not a sixteenth shorter than 0.1 s.
(b) Guitar hears onsets with its own, lower local threshold; bass and keys keep the defaults.
(c) The vocal-bleed filter leaves a guitar mixed under the singer alone.
"""

from dataclasses import replace

import numpy as np
from test_vocal_bleed import SECONDS, SR, TEMPO, place, plucked, track_times, voiced

from chartgen.audio.onsets import OnsetConfig
from chartgen.audio.vocal_bleed import load_thresholds
from chartgen.chart import instruments
from chartgen.chart.charter import _quantize, build_expert_track
from chartgen.chart.instruments import GUITAR_ONSETS, ONSET_SETTINGS, build_tracks_for
from chartgen.core.model import Instrument
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent

R = 192


def tempo(bpm: float) -> TempoMap:
    return TempoMap([TempoEvent(0, bpm)], [TimeSignatureEvent(0, 4, 4)], resolution=R)


# ---------------------------------------------------------------- (a) the snapping grid


def test_a_fast_song_snaps_to_eighths_and_keeps_an_onset_between_them():
    fast = tempo(191.0)
    eighth = 60.0 / 191.0 / 2
    late = 10 * eighth + 0.046  # 46 ms after an eighth, 32 ms before the sixteenth after it
    on_time = 12 * eighth + 0.02
    ticks = _quantize(np.array([late, on_time]), fast)
    assert abs(fast.seconds_at(float(ticks[0])) - late) < 0.002, "too far from every eighth: its own time"
    assert ticks[1] == 12 * R // 2, "close to an eighth: on it"


def test_at_150_bpm_or_slower_the_sixteenth_grid_stays():
    for bpm in (90.0, 120.0, 150.0):
        tm = tempo(bpm)
        sixteenth = 60.0 / bpm / 4
        times = np.array([5 * sixteenth + 0.01, 7 * sixteenth - 0.012])
        assert _quantize(times, tm).tolist() == [5 * R // 4, 7 * R // 4], bpm


# ---------------------------------------------------------------- (b) guitar's onsets


def test_only_guitar_has_its_own_onset_settings():
    assert set(ONSET_SETTINGS) == {Instrument.GUITAR}
    assert GUITAR_ONSETS == replace(OnsetConfig(), threshold_mad_k=2.5, local_ratio=1.5)
    assert OnsetConfig().threshold_mad_k == 3.0 and OnsetConfig().local_ratio == 1.75, "bass and keys"


def test_each_instrument_hands_its_own_onset_settings_to_the_charter(monkeypatch):
    seen = {}

    def spy(instrument, *args, onset_config=None, **kwargs):
        seen[instrument] = onset_config
        return build_expert_track(instrument, *args, onset_config=onset_config, **kwargs)

    monkeypatch.setattr(instruments, "build_expert_track", spy)
    stem = place([(1.0 + i * 0.5, plucked(110.0, 0.45, 0.3)) for i in range(16)], SECONDS)
    for instrument in (Instrument.GUITAR, Instrument.BASS, Instrument.KEYS):
        build_tracks_for(instrument, stem, TEMPO, SECONDS)
    assert seen == {Instrument.GUITAR: GUITAR_ONSETS, Instrument.BASS: None, Instrument.KEYS: None}


# ---------------------------------------------------------------- (c) a guitar under the singer


def under_the_singer():
    """A loud guitar part sets the stem's usual level; then the guitar plays 10 dB below it while a
    singer sings 7 dB over it, as in a verse mixed around the voice."""
    loud = [(1.0 + i * 0.5, plucked(196.0, 0.45, 0.3)) for i in range(12)]
    under_times = 9.0 + np.arange(16) * 0.5
    under = [(time, plucked(196.0, 0.45, 0.095)) for time in under_times]
    singing = [(time - 0.15, voiced(330.0, 0.5, 0.2, rng_seed=i)) for i, time in enumerate(under_times)]
    return place(loud + under, SECONDS), place(singing, SECONDS), under_times


def test_a_guitar_mixed_under_the_singer_stays():
    guitar, vocals, under_times = under_the_singer()
    built = build_expert_track(Instrument.GUITAR, guitar, TEMPO, SECONDS, vocals=vocals)
    times = track_times(built.track)
    assert all(np.abs(times - time).min() <= 0.06 for time in under_times)
    assert not any(note.removed for note in built.bleed)


def test_the_old_limits_took_that_guitar_out():
    """The test must show what the old limits did, or it proves nothing about the new ones."""
    guitar, vocals, under_times = under_the_singer()
    old = replace(load_thresholds(), min_vocal_over_stem_db=3.0, max_stem_level_db=-8.0)
    built = build_expert_track(Instrument.GUITAR, guitar, TEMPO, SECONDS, vocals=vocals, bleed_thresholds=old)
    removed = [note for note in built.bleed if note.removed]
    assert len(removed) >= 8
    assert all(np.abs(under_times - note.time_s).min() <= 0.06 for note in removed)
