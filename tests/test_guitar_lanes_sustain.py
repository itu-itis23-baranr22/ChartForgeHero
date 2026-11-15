"""Step 3 of the reference tuning: guitar lanes, sustains and direction (SPEC 43).

(a) A repeat also needs the plain spectra alike: the least alike notes of a song are no repeats.
(b) The fret mapper's register reaches orange; guitar's orange is checked for one spectral center.
(c) Medium and Easy lane maps.
(d) A guitar sustain ends at the next re-attack of the stem, charted or not.
And the vocal-bleed filter warns when it removes more than 5% of a stem's notes.
"""

import json
from dataclasses import replace

import numpy as np
import pytest
from test_vocal_bleed import SECONDS, build, place, plucked, stems_for_pipeline

from chartgen.audio.onsets import OnsetConfig, OnsetResult
from chartgen.audio.pitch import NotePitch, PitchConfig, analyze_pitches, contour_with_repeats
from chartgen.audio.sustain import REATTACK_MIN_GAP_S, cut_at_reattacks
from chartgen.audio.vocal_bleed import NoteBleed, load_thresholds, removed_share
from chartgen.chart import charter, instruments
from chartgen.chart.charter import ChartedTrack, build_expert_track
from chartgen.chart.difficulty import OrangePitches, Position, count_orange_pitches, ideal_shape, load_config
from chartgen.chart.fret_mapping import NoteInput, load_weights, map_notes
from chartgen.chart.instruments import (
    GUITAR_PITCH,
    GUITAR_REATTACKS,
    ORANGE_CONTOUR_OFFSET,
    PITCH_SETTINGS,
    REATTACK_SETTINGS,
    build_tracks_for,
    settings_for,
)
from chartgen.core.model import ChartNote, Difficulty, Instrument, Track
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent
from chartgen.evaluation.run import _level_table
from chartgen.pipeline import _report_track

SR = 22050
TEMPO = TempoMap([TempoEvent(0, 120.0)], [TimeSignatureEvent(0, 4, 4)], resolution=192)


def pitch(contour: float, similarity: float, raw: float) -> NotePitch:
    return NotePitch(contour, similarity, 0.2, 1, raw)


# ---------------------------------------------------------------- (a) the repeat rule


def test_the_least_alike_plain_spectra_are_no_repeats():
    """Every log spectrum alike, as on distorted guitar: only the raw rule tells the changes apart."""
    raws = [0.0, 0.99, 0.99, 0.80, 0.99, 0.99, 0.70, 0.99, 0.99, 0.99]
    pitches = [pitch(10.0 + i, 0.97, raw) for i, raw in enumerate(raws)]
    old = contour_with_repeats(pitches)
    assert np.all(old == 10.0), "the log rule alone calls everything a repeat"
    new = contour_with_repeats(pitches, raw_percentile=25.0)
    changes = [i for i in range(1, len(new)) if new[i] != new[i - 1]]
    assert changes == [3, 6], "the two least alike notes start new values"
    assert new[3] == 13.0 and new[6] == 16.0


def test_without_a_raw_percentile_the_log_rule_alone_decides():
    pitches = [pitch(10.0, 0.0, 0.0), pitch(12.0, 0.99, 0.1), pitch(14.0, 0.5, 0.99)]
    assert contour_with_repeats(pitches).tolist() == [10.0, 10.0, 14.0]
    assert contour_with_repeats(pitches, raw_percentile=None).tolist() == [10.0, 10.0, 14.0]


def test_the_raw_rule_never_makes_a_repeat_the_log_rule_did_not():
    pitches = [pitch(10.0, 0.0, 0.0), pitch(12.0, 0.90, 1.0), pitch(14.0, 0.90, 1.0)]
    assert contour_with_repeats(pitches, raw_percentile=0.0).tolist() == [10.0, 12.0, 14.0]


def test_unknown_notes_stay_unknown_and_do_not_count_toward_the_percentile():
    pitches = [pitch(10.0, 0.0, 0.0), NotePitch(float("nan"), 0.0, 0.0, 1), pitch(12.0, 0.0, 0.0),
               pitch(13.0, 0.99, 0.5), pitch(14.0, 0.99, 0.9)]
    values = contour_with_repeats(pitches, raw_percentile=50.0)
    assert np.isnan(values[1])
    # Only the two known pairs count, 0.5 and 0.9: limit 0.7. Counting the unknown ones (0.0, 0.0) would
    # give 0.25, and the note at 13.0 would be a repeat of 12.0.
    assert values.tolist()[3:] == [13.0, 13.0]


def tone(freq: float, seconds: float, amp: float = 0.3) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    return (amp * sum(np.sin(2 * np.pi * freq * k * t) / k for k in (1, 2, 3))).astype(np.float32)


def test_analyze_pitches_reads_the_plain_similarity():
    signal = np.concatenate([tone(110.0, 0.5), tone(110.0, 0.5), tone(165.0, 0.5)])
    times = np.array([0.0, 0.5, 1.0])
    found = analyze_pitches(signal, times, np.r_[times[1:], 1.5], SR)
    assert found[0].raw_similarity == 0.0, "nothing before the first note"
    assert found[1].raw_similarity > 0.95, "the same tone again"
    assert found[2].raw_similarity < found[1].raw_similarity, "another tone"


def test_only_guitar_reads_its_contour_with_the_raw_rule():
    assert set(PITCH_SETTINGS) == {Instrument.GUITAR}
    assert GUITAR_PITCH == replace(PitchConfig(), raw_repeat_percentile=14.0)
    assert PitchConfig().raw_repeat_percentile is None, "keys keep the log rule alone"


# ---------------------------------------------------------------- what the charter is handed


def test_each_instrument_hands_its_own_pitch_and_reattack_settings_to_the_charter(monkeypatch):
    seen = {}

    def spy(instrument, *args, pitch_config=None, reattack_config=None, **kwargs):
        seen[instrument] = (pitch_config, reattack_config)
        return build_expert_track(instrument, *args, pitch_config=pitch_config, reattack_config=reattack_config,
                                  **kwargs)

    monkeypatch.setattr(instruments, "build_expert_track", spy)
    stem = place([(1.0 + i * 0.5, plucked(110.0, 0.45, 0.3)) for i in range(16)], SECONDS)
    for instrument in (Instrument.GUITAR, Instrument.BASS, Instrument.KEYS):
        build_tracks_for(instrument, stem, TEMPO, SECONDS)
    assert seen == {
        Instrument.GUITAR: (GUITAR_PITCH, GUITAR_REATTACKS),
        Instrument.BASS: (None, None),
        Instrument.KEYS: (None, None),
    }


# ---------------------------------------------------------------- (b) lanes and the orange check


def test_the_register_reaches_orange_and_green():
    weights = load_weights()
    assert weights.register_span == (0.0, 3.5)
    assert weights.lane_shares == (0.206, 0.236, 0.237, 0.225, 0.097), "train human Expert means"
    assert weights.lane_prior == 1.0 and weights.register == 1.0


OLD_WEIGHTS = {"register_span": (0.5, 3.0), "register": 0.6, "lane_prior": 2.0,
               "lane_shares": (0.26, 0.24, 0.22, 0.22, 0.06)}


@pytest.mark.parametrize(
    "pitches",
    [[2 * i for i in range(12)], [0, 0, 7, 7, 12, 12, 7, 7, 0, 0, 7, 7, 14, 14, 7, 7]],
    ids=["rising line", "riff with a high note"],
)
def test_the_top_of_a_phrase_reaches_orange(pitches):
    """With the span ending at 3.0 the top of a phrase aimed at blue, and orange never came."""
    notes = [NoteInput(0.5 * i, float(p)) for i, p in enumerate(pitches)]
    new = [shape[0] for shape in map_notes(notes, load_weights())]
    old = [shape[0] for shape in map_notes(notes, replace(load_weights(), **OLD_WEIGHTS))]
    assert max(new) == 4 and new[0] == 0
    assert max(old) == 3, "the old weights, or the test proves nothing"
    assert new[pitches.index(max(pitches))] == 4, "orange is the highest note"


def test_guitar_orange_is_counted_by_its_spectral_center():
    track = Track(Instrument.GUITAR, Difficulty.EXPERT, [ChartNote(0, 4), ChartNote(192, 4), ChartNote(384, 4)])
    positions = [Position(0, 0.0, (4,), pitch=3.8), Position(192, 0.5, (4,), pitch=4.2),
                 Position(384, 1.0, (4,), pitch=float("nan"))]
    orange = count_orange_pitches(track, positions, 0.70, semitone_offset=ORANGE_CONTOUR_OFFSET,
                                  kind="spectral center")
    assert orange.counts == (("E2", 2),), "4 semitones above C2, rounded"
    assert orange.unknown == 1
    assert orange.as_dict()["counted"] == "spectral center"
    assert orange.is_one_pitch


def test_guitar_warns_when_its_orange_is_one_spectral_center():
    item = ChartedTrack(
        Track(Instrument.GUITAR, Difficulty.EXPERT, [ChartNote(0, 4)]),
        1,
        orange_pitches=OrangePitches((("E3", 8), ("G3", 2)), 0, 0.70, "spectral center"),
    )
    warnings: list[str] = []
    _report_track(Instrument.GUITAR, item, warnings)
    assert any("guitar/expert: orange is one spectral center: E3 is 80%" in w for w in warnings)
    lines = _level_table("Guitar", {"expert": {"orange_pitches": item.orange_pitches.as_dict()}})
    assert "expert orange notes by spectral center: E3 8, G3 2; orange is one spectral center" in lines


def test_guitar_is_checked_for_one_orange_center_and_keys_are_not():
    assert settings_for(Instrument.GUITAR)[0].max_orange_pitch_share == 0.70
    assert settings_for(Instrument.KEYS)[0].max_orange_pitch_share is None
    stem = place([(1.0 + i * 0.6, tone(110.0 * 2 ** (i / 12), 0.5)) for i in range(16)], 12.0)
    built = build_tracks_for(Instrument.GUITAR, stem, TEMPO, 12.0)
    assert all(item.orange_pitches is not None and item.orange_pitches.kind == "spectral center" for item in built)


# ---------------------------------------------------------------- (c) lower-level lanes


def test_medium_keeps_blue_and_easy_moves_red_to_green():
    config = load_config()
    assert config.levels[Difficulty.MEDIUM].lane_map == (0, 1, 2, 3, 3)
    assert config.levels[Difficulty.EASY].lane_map == (0, 0, 1, 2, 2)
    assert ideal_shape((3,), Difficulty.MEDIUM, config.levels[Difficulty.MEDIUM]) == (3,)
    assert ideal_shape((1,), Difficulty.EASY, config.levels[Difficulty.EASY]) == (0,)
    assert ideal_shape((4,), Difficulty.MEDIUM, config.levels[Difficulty.MEDIUM]) == (3,), "still no orange"


# ---------------------------------------------------------------- (d) sustains end at a re-attack


def test_a_reattack_ends_the_ring_time():
    times = np.array([1.0, 3.0, 5.0])
    durations = np.array([1.8, 1.8, 0.4])
    attacks = np.array([1.0 + REATTACK_MIN_GAP_S / 2, 2.2, 3.0, 5.2])
    cut = cut_at_reattacks(times, durations, attacks)
    assert cut[0] == pytest.approx(1.2), "the attack at 2.2 s; the one 50 ms after the onset is the onset"
    assert cut[1] == pytest.approx(1.8), "no attack before the note ends"
    assert cut[2] == pytest.approx(0.2), "a shorter ring time is cut too"
    assert np.array_equal(cut_at_reattacks(times, durations, np.empty(0)), durations)


def test_only_guitar_ends_its_sustains_at_reattacks():
    assert set(REATTACK_SETTINGS) == {Instrument.GUITAR}
    assert GUITAR_REATTACKS == replace(OnsetConfig(), threshold_mad_k=1.0, local_ratio=1.1)


def test_a_missed_strum_no_longer_makes_a_sustain(monkeypatch):
    """A chord strummed at 1.0 s and again at 1.25 s, where the chart only has 1.0 s and 3.0 s."""
    stem = np.concatenate([np.zeros(SR, np.float32), tone(110.0, 3.0, 0.3)])
    loose = replace(OnsetConfig(), threshold_mad_k=0.5)

    def fake(mono, samplerate=SR, config=None):
        found = [1.0, 1.25, 3.0] if config == loose else [1.0, 3.0]
        return OnsetResult(np.array(found), np.ones(len(found)))

    monkeypatch.setattr(charter, "detect_onsets", fake)
    plain = build_expert_track(Instrument.GUITAR, stem, TEMPO, 4.0, SR)
    cut = build_expert_track(Instrument.GUITAR, stem, TEMPO, 4.0, SR, reattack_config=loose)
    def first(built) -> int:
        return [note.length for note in built.track.notes if note.tick == 384][0]

    assert first(plain) > 0, "it rang through the missed strum"
    assert first(cut) == 0, "0.25 s to the strum is below the shortest sustain at 120 BPM (0.375 s)"


# ---------------------------------------------------------------- the vocal-bleed warning


def bleed(removed: int, total: int) -> tuple[NoteBleed, ...]:
    return tuple(NoteBleed(float(i), 20.0, -25.0, 0.1, i < removed) for i in range(total))


@pytest.mark.parametrize("removed,total,warns", [(6, 100, True), (5, 100, False), (0, 10, False), (3, 10, True)])
def test_the_filter_warns_above_five_percent(removed, total, warns):
    limits = load_thresholds()
    assert limits.warn_removed_share == 0.05
    notes = bleed(removed, total)
    assert removed_share(notes) == removed / total
    assert limits.removes_too_many(notes) == warns
    item = ChartedTrack(Track(Instrument.GUITAR, Difficulty.EXPERT, [ChartNote(0, 1)]), total, bleed=notes)
    warnings: list[str] = []
    _report_track(Instrument.GUITAR, item, warnings)
    assert any("vocal-bleed filter removed" in w for w in warnings) == warns


def test_no_notes_judged_is_no_warning():
    assert removed_share(()) == 0.0
    assert not load_thresholds().removes_too_many(())


@pytest.mark.parametrize("value", ["0.0", "1.5", "-0.1"])
def test_the_warning_limit_must_be_a_share(tmp_path, value):
    from chartgen.audio.vocal_bleed import THRESHOLDS_PATH

    text = THRESHOLDS_PATH.read_text(encoding="utf-8").replace("warn_removed_share = 0.05", f"warn_removed_share = {value}")
    path = tmp_path / "vocal_bleed.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="warn_removed_share"):
        load_thresholds(path)


@pytest.mark.heavy
def test_analysis_says_how_much_the_filter_removed(tmp_path):
    result = build(tmp_path, stems_for_pipeline())
    analysis = json.loads((result.folder / "analysis.json").read_text(encoding="utf-8"))
    entry = analysis["charts"]["guitar"]["expert"]["vocal_bleed"]
    assert entry["removed_share"] == pytest.approx(entry["removed_count"] / entry["judged_count"], abs=1e-4)
    assert entry["warn_removed_share"] == 0.05
    assert entry["removes_more_than_usual"] == (entry["removed_share"] > 0.05)
    warned = any("vocal-bleed filter removed" in w for w in analysis["warnings"])
    assert warned == entry["removes_more_than_usual"]
