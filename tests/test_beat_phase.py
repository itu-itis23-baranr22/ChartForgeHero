"""Half a beat off the kick, and openings that are not part of the song.

Every note lands on a sixteenth whichever eighth is called the beat, so no onset measure can see
the first problem. The second makes a tracker wander, which looks like a tempo drift but is not.
"""

import dataclasses
import json

import numpy as np
import pytest
from conftest import FakeSeparator, song_stems

import chartgen.pipeline
from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.meter import (
    OFF_BEAT_KICK_ADVANTAGE,
    SNARE_MARKS_THE_BEAT,
    _kick_decides,
    check_beat_phase,
)
from chartgen.audio.tempo import _unfit_lead_in, choose_grid, estimate_tempo_map
from chartgen.core.model import Instrument, SongMetadata
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent
from chartgen.pipeline import BuildConfig, build_song

SR = ANALYSIS_SAMPLERATE
BPM = 130.0
BEAT = 60.0 / BPM
SECONDS = 60.0


class Kit:
    """Three sounds from fixed noise, so every run hears the same."""

    def __init__(self, seconds: float = SECONDS) -> None:
        self.signal = np.zeros(int(seconds * SR), dtype=np.float32)
        t = np.arange(int(0.15 * SR)) / SR
        noise = np.random.default_rng(5).standard_normal(t.size)
        self.kick = (np.sin(2 * np.pi * 60 * t) * np.exp(-t / 0.04)).astype(np.float32)
        self.snare = (noise * np.exp(-t / 0.05)).astype(np.float32)
        self.hat = (noise * np.exp(-t / 0.008)).astype(np.float32)

    def hit(self, times: np.ndarray, wave: np.ndarray, level: float) -> None:
        for time in times:
            index = int(time * SR)
            end = min(index + wave.size, self.signal.size)
            if 0 <= index < self.signal.size:
                self.signal[index:end] += level * wave[: end - index]


def bars(start: float, seconds: float) -> np.ndarray:
    return np.arange(start, seconds, 4 * BEAT)


def kick_times(start: float, seconds: float = SECONDS) -> np.ndarray:
    return np.sort(np.concatenate([bars(start, seconds) + beat * BEAT for beat in range(4)]))


def dembow(start: float, seconds: float = SECONDS, hats: bool = True, weak_snares: float = 0.3) -> np.ndarray:
    """A 3-3-2 groove: a kick on every beat, snares between. The hits on 1.5 and 3.5 are the
    loudest in the song and lead a tracker half a beat astray. Danza's kick stem also has
    something up high on its beats, which is what the hats stand for."""
    kit = Kit(seconds)
    kicks = kick_times(start, seconds)
    kit.hit(kicks, kit.kick, 0.9)
    if hats:
        kit.hit(kicks, kit.hat, 0.3)
    kit.hit(np.sort(np.r_[bars(start, seconds) + 1.5 * BEAT, bars(start, seconds) + 3.5 * BEAT]), kit.snare, 1.0)
    if weak_snares:
        kit.hit(np.sort(np.r_[bars(start, seconds) + 0.75 * BEAT, bars(start, seconds) + 2.75 * BEAT]), kit.snare, weak_snares)
    return kit.signal


def steady_map() -> TempoMap:
    """A map whose beats fall on 0, 1, 2, ... beats of audio time."""
    return TempoMap([TempoEvent(0, BPM)], [TimeSignatureEvent(0, 4, 4)])


def beats_of(tempo_map: TempoMap, until: float = SECONDS - 1) -> np.ndarray:
    last = int(tempo_map.ticks_at(until) // tempo_map.resolution)
    return tempo_map.seconds_at(np.arange(1, last, dtype=np.float64) * tempo_map.resolution)


def distance_to_kicks(tempo_map: TempoMap, start: float) -> float:
    beats = beats_of(tempo_map)
    return float(np.median(np.abs(beats[None, :] - kick_times(start)[:, None]).min(axis=0)))


# ---------------------------------------------------------------- the beat phase


def test_kick_between_the_grid_beats_means_the_grid_is_half_a_beat_off():
    drums = dembow(BEAT / 2)
    check = check_beat_phase(steady_map(), drums, drums, SR)
    assert check.half_beat_off
    assert check.kick_ratio >= OFF_BEAT_KICK_ADVANTAGE
    assert check.snare_ratio >= SNARE_MARKS_THE_BEAT
    assert check.section_agreement == 1.0


def test_kick_on_the_grid_beats_is_left_alone():
    drums = dembow(0.0)
    check = check_beat_phase(steady_map(), drums, drums, SR)
    assert not check.half_beat_off
    assert check.kick_ratio < 1.0


def test_syncopated_kick_is_left_alone_while_the_snare_marks_the_beats():
    """The rule needs both: a kick may land between beats that a backbeat still marks."""
    kit = Kit()
    grid = kick_times(0.0)
    kit.hit(grid + BEAT / 2, kit.kick, 0.9)
    kit.hit(np.sort(np.r_[bars(0.0, SECONDS) + BEAT, bars(0.0, SECONDS) + 3 * BEAT]), kit.snare, 0.6)
    check = check_beat_phase(steady_map(), kit.signal, kit.signal, SR)
    assert check.kick_ratio >= OFF_BEAT_KICK_ADVANTAGE, "the kick alone would have moved the grid"
    assert check.snare_ratio < SNARE_MARKS_THE_BEAT
    assert not check.half_beat_off


def test_known_limit_a_bare_three_three_two_stays_half_a_beat_off():
    """With nothing but the snare up high, this looks just like a backbeat over a syncopated
    kick. Moving a song that really is one would be worse, so it stays as the tracker left it:
    still a correct chart to play, with the beat lines on the off-beats."""
    drums = dembow(1.0, hats=False, weak_snares=0.0)
    analysis = estimate_tempo_map(drums, SR, drums=drums)
    assert analysis.beat_phase.kick_ratio >= OFF_BEAT_KICK_ADVANTAGE
    assert not analysis.beat_phase.half_beat_off
    assert distance_to_kicks(analysis.tempo_map, 1.0) == pytest.approx(BEAT / 2, abs=0.01)


def test_bleed_in_the_drum_stem_cannot_move_the_grid():
    """Onset envelopes do not depend on level, so the check must look at it separately."""
    faint = dembow(BEAT / 2) * 0.01
    check = check_beat_phase(steady_map(), faint, np.full_like(faint, 0.3), SR)
    assert check.kick_ratio >= OFF_BEAT_KICK_ADVANTAGE, "the ratio alone would have moved the grid"
    assert not check.half_beat_off


def test_silent_drum_stem_says_nothing():
    silence = np.zeros(int(SECONDS) * SR, dtype=np.float32)
    assert not check_beat_phase(steady_map(), silence, np.full_like(silence, 0.3), SR).half_beat_off


def test_too_few_beats_cannot_be_judged():
    drums = dembow(0.0, seconds=4.0)
    assert check_beat_phase(steady_map(), drums, drums, SR) is None


@pytest.mark.heavy
def test_grid_ends_up_on_the_kicks_of_a_three_three_two_groove():
    drums = dembow(1.0)
    without_stem = estimate_tempo_map(drums, SR)
    assert distance_to_kicks(without_stem.tempo_map, 1.0) == pytest.approx(BEAT / 2, abs=0.01), (
        "the tracker must be half a beat off here, or this test proves nothing"
    )

    analysis = estimate_tempo_map(drums, SR, drums=drums)
    assert analysis.beat_phase.half_beat_off
    assert "Grid moved half a beat" in analysis.decision
    assert distance_to_kicks(analysis.tempo_map, 1.0) < 0.01
    assert analysis.tempo_map.tempos[-1].bpm == without_stem.tempo_map.tempos[-1].bpm
    assert analysis.final.beats_with_onset > 0.9


@pytest.mark.heavy
def test_moved_grid_keeps_every_note_on_a_sixteenth():
    drums = dembow(1.0)
    moved = estimate_tempo_map(drums, SR, drums=drums).tempo_map
    original = estimate_tempo_map(drums, SR).tempo_map
    # From the second beat: the first quarter note stretches from the start of the audio to the
    # first grid beat, so nothing before that is on a sixteenth, moved or not.
    times = beats_of(original)[1:60] + BEAT / 4
    ticks = moved.ticks_at(times)
    sixteenth = moved.resolution / 4
    assert np.abs(ticks / sixteenth - np.round(ticks / sixteenth)).max() < 0.05


@pytest.mark.heavy
def test_bpm_override_keeps_its_tempo_when_the_grid_moves():
    drums = dembow(1.0)
    analysis = estimate_tempo_map(drums, SR, bpm_override=BPM, drums=drums)
    assert analysis.beat_phase.half_beat_off
    assert analysis.tempo_map.tempos[-1].bpm == BPM
    assert distance_to_kicks(analysis.tempo_map, 1.0) < 0.01


def test_without_a_drum_stem_nothing_is_checked():
    drums = dembow(1.0, seconds=30.0)
    assert estimate_tempo_map(drums, SR, bpm_override=BPM).beat_phase is None


# ---------------------------------------------------------------- tied bars


def test_tied_bar_phases_go_to_the_harder_kick():
    beats = np.arange(1, 65)
    kick = np.where(beats % 4 == 2, 5.0, 1.0)
    assert _kick_decides(kick, beats, 4, phase=1, other=2) == (2, 1)
    assert _kick_decides(kick, beats, 4, phase=2, other=1) == (2, 1)


# ---------------------------------------------------------------- the opening


def sixteenths(first: float, last: float, bpm: float, every: int = 1) -> np.ndarray:
    return np.arange(first, last, 60.0 / bpm / 4 * every)


def test_opening_at_another_tempo_is_found():
    onsets = np.r_[sixteenths(3.0, 30.0, 100.0, every=3), sixteenths(30.0, 200.0, BPM)]
    end, on_grid = _unfit_lead_in(onsets, 0.0, BEAT)
    assert 26.0 <= end <= 33.0
    assert on_grid < 0.6


def test_song_that_fits_from_the_start_has_no_opening():
    assert _unfit_lead_in(sixteenths(1.0, 200.0, BPM), 0.0, BEAT) == (0.0, 1.0)


def test_silence_before_the_song_is_not_an_opening():
    assert _unfit_lead_in(sixteenths(30.0, 200.0, BPM), 0.0, BEAT) == (0.0, 1.0)


def test_grid_that_fits_nothing_has_no_opening():
    """That is a wrong grid, and calling the whole song an opening would hide it."""
    assert _unfit_lead_in(sixteenths(0.0, 200.0, 97.0, every=3), 0.0, BEAT) == (0.0, 1.0)


def test_windows_that_fit_by_chance_do_not_end_the_opening():
    onsets = np.r_[
        sixteenths(0.0, 15.0, 100.0, every=3),
        sixteenths(15.0, 20.0, BPM, every=4),
        sixteenths(20.0, 39.0, 100.0, every=3),
        sixteenths(39.0, 200.0, BPM),
    ]
    end, _ = _unfit_lead_in(onsets, 0.0, BEAT)
    assert 35.0 <= end <= 43.0


def danza_shaped_beats() -> tuple[np.ndarray, np.ndarray]:
    """Beats that wander over an opening, sit on the off-beat for a while, then settle."""
    onsets = np.r_[sixteenths(2.0, 37.0, 100.0, every=3), sixteenths(37.0, 200.0, BPM)]
    numbers = np.arange(int(35 / BEAT))
    wander = 2.0 + numbers * BEAT + 0.1 * np.abs(((numbers / 20) % 2) - 1)
    off_beats = np.arange(37.0 + BEAT / 2, 52.0, BEAT)
    beats = np.r_[wander[wander < 36.5], off_beats, np.arange(52.0, 200.0, BEAT)]
    return beats, onsets


def test_beats_on_the_off_beat_and_a_foreign_opening_are_not_drift():
    beats, onsets = danza_shaped_beats()
    choice = choose_grid(beats, onsets, np.ones_like(onsets), BPM, 200.0)
    assert choice.method == "constant"
    assert choice.one_tempo.max_ms > 25, "what the tracker did must stay on record"
    assert 33.0 <= choice.lead_in_end_s <= 41.0
    assert choice.lead_in_on_grid < 0.6
    assert choice.final.max_ms <= 25
    assert "not part of this grid" in choice.decision
    assert choice.song_start_s == onsets[onsets >= choice.lead_in_end_s][0]


def test_opening_and_moved_grid_reach_the_analysis_and_the_warnings(song_file, tmp_path, monkeypatch):
    real = chartgen.pipeline.estimate_tempo_map

    def with_an_opening(*args, **kwargs):
        return dataclasses.replace(real(*args, **kwargs), lead_in_end_s=5.5, lead_in_on_grid=0.31)

    monkeypatch.setattr(chartgen.pipeline, "estimate_tempo_map", with_an_opening)
    config = BuildConfig(
        input_path=song_file,
        metadata=SongMetadata("Şarkı", "Sanatçı"),
        instruments=frozenset({Instrument.GUITAR}),
        output_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
    )
    folder = build_song(config, FakeSeparator(song_stems())).folder
    analysis = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
    assert analysis["tempo"]["unfit_lead_in"] == {
        "end_s": 5.5,
        "onsets_on_grid": 0.31,
        "song_start_s": 5.5,
    }
    assert analysis["tempo"]["beat_phase"]["moved_half_a_beat"] is False
    assert any("first 5.5 s do not fit" in warning for warning in analysis["warnings"])


# ---------------------------------------------------------------- real songs


@pytest.mark.real
@pytest.mark.parametrize("real_song", ["DanzaKuduro.mp3"], indirect=True)
def test_danza_real_grid(real_song):
    analysis = real_song.tempo
    assert analysis.method == "constant"
    assert analysis.bpm == pytest.approx(129.975, abs=0.01)
    assert analysis.beat_phase.half_beat_off
    assert analysis.lead_in_end_s == pytest.approx(36.93, abs=0.5)
    assert analysis.final.max_ms <= 25
    assert analysis.final.beats_with_onset >= 0.85
    assert analysis.first_downbeat_s == pytest.approx(1.114, abs=0.01)
    assert analysis.meter.low_confidence, "the bar phase was a tie and must say so"
    assert analysis.song_start_s == pytest.approx(37.1, abs=0.05)


@pytest.mark.real
@pytest.mark.parametrize("real_song", ["TocaToca.mp3"], indirect=True)
def test_toca_real_grid_did_not_move(real_song):
    analysis = real_song.tempo
    assert not analysis.beat_phase.half_beat_off
    assert analysis.lead_in_end_s == 0.0
    assert analysis.method == "constant"
    assert analysis.final.max_ms <= 25


@pytest.mark.real
@pytest.mark.parametrize("real_song", ["LastResort.wav"], indirect=True)
def test_last_resort_real_grid_did_not_move(real_song):
    analysis = real_song.tempo
    assert not analysis.beat_phase.half_beat_off
    assert [(e.tick, e.bpm) for e in analysis.tempo_map.tempos] == [
        (0, 81.812),
        (192, 85.622),
        (1728, 90.051),
        (5376, 90.597),
    ]
