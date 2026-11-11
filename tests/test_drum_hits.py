"""Phase C, drums. C.1: hearing the drum stem and writing the Expert drum chart.

The synthetic kit is made here: a kick sweeping down to 50 Hz, a snare with a 190 Hz body and wire
noise up to 6 kHz, a closed hi-hat dying in 20 ms, a ride ringing for 300 ms, a crash for 1.2 s and three
pitched toms. Its pattern is known, so every part can be scored on its own.
"""

import json
from dataclasses import replace

import numpy as np
import pytest
import soundfile as sf
from conftest import SR as STEM_SR
from conftest import CALIFORNICATION, FakeSeparator, song_stems, stereo

from chartgen.audio.drum_hits import DrumAnalysis, DrumHit, detect_drum_hits, load_config
from chartgen.audio.io import ANALYSIS_SAMPLERATE, resample
from chartgen.chart.difficulty import HardRuleViolation
from chartgen.chart.drum_charter import UNVERIFIED_PIECES, build_drum_expert_track, check_drum_track
from chartgen.chart.instruments import CHARTABLE_INSTRUMENTS, build_tracks_for
from chartgen.clonehero.chart_format import DotChartExporter
from chartgen.clonehero.drum_ear_test import EAR_TEST_FILES, chart_drum_gems, write_drum_ear_test
from chartgen.clonehero.validate import validate_song_folder
from chartgen.core import (
    Chart,
    ChartNote,
    Difficulty,
    DrumGem,
    DrumPiece,
    Instrument,
    SongMetadata,
    TempoEvent,
    TempoMap,
    TimeSignatureEvent,
    Track,
)
from chartgen.evaluation.drum_metrics import drum_metrics
from chartgen.evaluation.reference import ReferenceDrumHit
from chartgen.pipeline import BuildConfig, build_song

SR = ANALYSIS_SAMPLERATE
BEAT = 0.5
TEMPO = TempoMap([TempoEvent(0, 120.0)], [TimeSignatureEvent(0, 4, 4)])
TOLERANCE = 0.03


# ---------------------------------------------------------------- a synthetic kit


def band_noise(n: int, low: float, high: float, rng: np.random.Generator) -> np.ndarray:
    spectrum = np.fft.rfft(rng.standard_normal(n))
    freqs = np.fft.rfftfreq(n, 1 / SR)
    spectrum[(freqs < low) | (freqs > high)] = 0
    noise = np.fft.irfft(spectrum, n)
    return noise / (np.abs(noise).max() + 1e-12)


def sound_of(piece: DrumPiece, rng: np.random.Generator, eight_o_eight: bool = False) -> np.ndarray:
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    if piece is DrumPiece.KICK and eight_o_eight:
        return 0.9 * np.sin(2 * np.pi * (48 * t + 40 * 0.05 * (1 - np.exp(-t / 0.05)))) * np.exp(-t / 0.8)
    if piece is DrumPiece.KICK:
        return 0.9 * np.sin(2 * np.pi * (50 * t + 70 * 0.03 * (1 - np.exp(-t / 0.03)))) * np.exp(-t / 0.15)
    if piece is DrumPiece.SNARE:
        body = 0.5 * np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.08)
        return body + 0.5 * band_noise(n, 1500, 6000, rng) * np.exp(-t / 0.06)
    if piece is DrumPiece.HI_HAT:
        return 0.35 * band_noise(n, 7000, 10500, rng) * np.exp(-t / 0.02)
    if piece is DrumPiece.RIDE:
        return 0.3 * band_noise(n, 6000, 10500, rng) * np.exp(-t / 0.3)
    if piece is DrumPiece.CRASH:
        return 0.6 * band_noise(n, 4000, 10500, rng) * np.exp(-t / 1.2)
    pitch = {DrumPiece.HIGH_TOM: 240.0, DrumPiece.MID_TOM: 160.0, DrumPiece.FLOOR_TOM: 100.0}[piece]
    return 0.7 * np.sin(2 * np.pi * pitch * t) * np.exp(-t / 0.25)


def kit_pattern() -> list[tuple[float, DrumPiece]]:
    """16 bars at 120 BPM: kick on 1 and 3, snare on 2 and 4, eighth hi-hats for six bars, quarter
    rides for six, a crash every four bars, and a high, mid or floor tom ending the last four."""
    events = []
    for bar in range(16):
        start = 1.0 + bar * 4 * BEAT
        for eighth in range(8):
            time = start + eighth * BEAT / 2
            if eighth in (0, 4):
                events.append((time, DrumPiece.KICK))
            if eighth in (2, 6):
                events.append((time, DrumPiece.SNARE))
            if bar < 6:
                events.append((time, DrumPiece.HI_HAT))
            elif bar < 12 and eighth % 2 == 0:
                events.append((time, DrumPiece.RIDE))
        if bar % 4 == 0:
            events.append((start, DrumPiece.CRASH))
        if bar >= 12:
            tom = (DrumPiece.HIGH_TOM, DrumPiece.MID_TOM, DrumPiece.FLOOR_TOM)[bar % 3]
            events.append((start + 7 * BEAT / 2, tom))
    return events


def render(events: list[tuple[float, DrumPiece]], level: float = 1.0, eight_o_eight: bool = False) -> np.ndarray:
    """The pattern over a faint noise floor, as a stem always has one.

    An 808 is one voice: each note cuts the one before, as a drum machine does.
    """
    rng = np.random.default_rng(0)
    seconds = max(time for time, _ in events) + 2.0
    signal = 0.002 * band_noise(int(seconds * SR), 30, 10500, rng)
    starts = sorted(int(round(time * SR)) for time, _ in events)
    for time, piece in events:
        sound = sound_of(piece, rng, eight_o_eight)
        start = int(round(time * SR))
        stop = min(signal.size, start + sound.size)
        if eight_o_eight:
            later = [other for other in starts if other > start]
            if later and later[0] < stop:
                stop = later[0]
                fade = min(int(0.005 * SR), stop - start)
                sound = sound.copy()
                sound[stop - start - fade : stop - start] *= np.linspace(1.0, 0.0, fade)
        signal[start:stop] += sound[: stop - start]
    return (signal * level).astype(np.float32)


def scores(hits, events, piece: DrumPiece) -> tuple[float, float]:
    """Precision and recall of one part within 30 ms."""
    truth = [time for time, kind in events if kind is piece]
    found = [hit.time_s for hit in hits if piece in hit.pieces]
    right = sum(any(abs(time - t) <= TOLERANCE for t in truth) for time in found)
    heard = sum(any(abs(time - t) <= TOLERANCE for time in found) for t in truth)
    return (right / len(found) if found else 0.0), (heard / len(truth) if truth else 0.0)


@pytest.fixture(scope="module")
def kit():
    events = kit_pattern()
    return events, detect_drum_hits(render(events))


# ---------------------------------------------------------------- hearing the kit


@pytest.mark.heavy
def test_a_known_kit_is_heard_part_by_part(kit):
    events, analysis = kit
    expected = {
        # part: (least precision, least recall). Masked parts are measured, not wished for: hi-hats under
        # a ringing crash and rides on a kick or snare hide part of their rise.
        DrumPiece.KICK: (0.95, 0.95),
        DrumPiece.SNARE: (0.95, 0.95),
        DrumPiece.HI_HAT: (0.85, 0.65),
        DrumPiece.RIDE: (0.8, 0.6),
        DrumPiece.CRASH: (0.5, 0.5),
        DrumPiece.HIGH_TOM: (1.0, 1.0),
        DrumPiece.MID_TOM: (1.0, 1.0),
    }
    for piece, (least_precision, least_recall) in expected.items():
        precision, recall = scores(analysis.hits, events, piece)
        assert precision >= least_precision and recall >= least_recall, (piece, precision, recall)


@pytest.mark.heavy
def test_kick_and_snare_are_never_mixed_up(kit):
    """The specification's own test: kick and snare told apart on a synthetic pattern."""
    events, analysis = kit
    for time, piece in events:
        if piece in (DrumPiece.KICK, DrumPiece.SNARE):
            near = [hit for hit in analysis.hits if abs(hit.time_s - time) <= TOLERANCE]
            assert len(near) == 1, time
            other = DrumPiece.SNARE if piece is DrumPiece.KICK else DrumPiece.KICK
            assert piece in near[0].pieces and other not in near[0].pieces, (time, near[0].pieces)


@pytest.mark.heavy
def test_parts_hit_together_are_all_found(kit):
    events, analysis = kit
    for partner in (DrumPiece.KICK, DrumPiece.SNARE):
        together = [
            time
            for time, piece in events
            if piece is DrumPiece.HI_HAT and any(abs(time - t) < 1e-9 and p is partner for t, p in events)
        ]
        both = [
            time
            for time in together
            if any(abs(hit.time_s - time) <= TOLERANCE and {partner, DrumPiece.HI_HAT} <= set(hit.pieces) for hit in analysis.hits)
        ]
        assert len(both) >= 0.6 * len(together), (partner, len(both), len(together))


@pytest.mark.heavy
@pytest.mark.parametrize("level", [0.3, 0.05])
def test_the_same_pattern_at_another_level_gives_the_same_hits(kit, level):
    """Acceptance criterion: thresholds follow the stem's own strong hits, so loudness changes nothing."""
    events, analysis = kit
    other = detect_drum_hits(render(events, level))
    assert [(hit.time_s, hit.pieces) for hit in other.hits] == [
        (hit.time_s, hit.pieces) for hit in analysis.hits
    ]


@pytest.mark.heavy
def test_a_busy_pattern_keeps_every_hit():
    """No threshold fixes the density: four times as many kicks, all of them found."""
    sparse = [(1.0 + index * 2 * BEAT, DrumPiece.KICK) for index in range(16)]
    busy = [(1.0 + index * BEAT / 2, DrumPiece.KICK) for index in range(64)]
    for events in (sparse, busy):
        hits = detect_drum_hits(render(events)).hits
        assert scores(hits, events, DrumPiece.KICK) == (1.0, 1.0), len(events)


@pytest.mark.heavy
def test_an_808_kick_is_a_kick_and_no_tom():
    events = [(1.0 + index * BEAT, DrumPiece.KICK) for index in range(24)]
    hits = detect_drum_hits(render(events, eight_o_eight=True)).hits
    assert scores(hits, events, DrumPiece.KICK) == (1.0, 1.0)
    assert not any(set(hit.pieces) & UNVERIFIED_PIECES for hit in hits)


@pytest.mark.heavy
def test_known_limit_a_floor_tom_is_lost():
    """A floor tom's 100 Hz lies in the kick's band, and noiseless low hits are taken for a kick's body.
    Without a reference that has floor toms there is nothing to tune a better rule on (STATUS, C.1)."""
    events = [(1.0 + index * BEAT, DrumPiece.FLOOR_TOM) for index in range(16)]
    hits = detect_drum_hits(render(events)).hits
    assert not any(DrumPiece.FLOOR_TOM in hit.pieces for hit in hits)


def test_silence_has_no_hits():
    assert detect_drum_hits(np.zeros(SR * 5, dtype=np.float32)).hits == ()
    assert detect_drum_hits(np.zeros(100, dtype=np.float32)).hits == ()


@pytest.mark.heavy
def test_hearing_is_deterministic(kit):
    events, analysis = kit
    again = detect_drum_hits(render(events))
    assert again.hits == analysis.hits


# ---------------------------------------------------------------- the settings file


@pytest.mark.parametrize(
    "old,new,message",
    [
        ("merge_window_s = 0.035", "merge_window_s = 0.035\nmax_pads = 3", "expected"),
        ("ratio = 0.5", "ratio = 1.5", "ratio"),
        ("strong_percentile = 99.0", "strong_percentile = 10.0", "strong_percentile"),
        ("hihat_max_ring = 0.4", "", "expects keys"),
        ("gate_db = -40.0", "gate_db = 3.0", "gate_db"),
        ("floor_tom_max_hz = 120.0", "floor_tom_max_hz = 300.0", "floor_tom_max_hz"),
    ],
)
def test_the_settings_file_is_checked_and_cannot_add_a_rule(tmp_path, old, new, message):
    """Nothing in drum_hits.toml decides what a position may hold: a key for it is refused."""
    from chartgen.audio.drum_hits import CONFIG_PATH

    text = CONFIG_PATH.read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "drum_hits.toml"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_config(path)


def test_the_settings_file_loads():
    config = load_config()
    assert config.cymbal.ratio == 0.25
    assert config.kick.latency_s == config.snare.latency_s == config.cymbal.latency_s == 0.0


# ---------------------------------------------------------------- writing the chart


def hit(time_s: float, *pieces: DrumPiece, strength: float = 1.0) -> DrumHit:
    return DrumHit(time_s, tuple(pieces), strength)


def analysis_of(*hits: DrumHit) -> DrumAnalysis:
    return DrumAnalysis(tuple(hits), {}, {}, 0.0)


def gems_by_tick(track: Track) -> dict[int, set[DrumGem]]:
    found: dict[int, set[DrumGem]] = {}
    for note in track.notes:
        found.setdefault(note.tick, set()).add(DrumGem.of_note(note))
    return found


def test_hits_land_on_the_grid_as_gems():
    charted = build_drum_expert_track(
        analysis_of(hit(1.0, DrumPiece.KICK, DrumPiece.HI_HAT), hit(1.252, DrumPiece.SNARE, DrumPiece.RIDE)),
        TEMPO,
        10.0,
    )
    assert gems_by_tick(charted.track) == {
        384: {DrumGem.KICK, DrumGem.YELLOW_CYMBAL},
        480: {DrumGem.RED, DrumGem.BLUE_CYMBAL},
    }
    assert charted.track.instrument is Instrument.DRUMS and charted.track.difficulty is Difficulty.EXPERT


def test_two_hands_hold_when_hits_share_a_tick():
    """Hits that snap to one tick may add up to more pads than two hands: the snare stays, then the
    louder cymbal. The tom lost its lane to the hi-hat before hands were counted: a cymbal wins a lane."""
    charted = build_drum_expert_track(
        analysis_of(
            hit(1.0, DrumPiece.KICK, DrumPiece.SNARE, DrumPiece.HI_HAT, strength=0.5),
            hit(1.01, DrumPiece.RIDE, strength=0.9),
            hit(1.02, DrumPiece.HIGH_TOM, strength=1.0),
        ),
        TEMPO,
        10.0,
    )
    assert gems_by_tick(charted.track) == {384: {DrumGem.KICK, DrumGem.RED, DrumGem.BLUE_CYMBAL}}
    assert charted.drum_chart.pads_dropped == 1
    assert charted.drum_chart.merged_on_one_tick == 2


def test_a_cymbal_takes_its_lane_from_a_tom():
    charted = build_drum_expert_track(
        analysis_of(hit(1.0, DrumPiece.HIGH_TOM, strength=1.0), hit(1.01, DrumPiece.HI_HAT, strength=0.2)),
        TEMPO,
        10.0,
    )
    assert gems_by_tick(charted.track) == {384: {DrumGem.YELLOW_CYMBAL}}


@pytest.mark.parametrize("seed", range(8))
def test_no_hits_can_break_two_hands(seed):
    rng = np.random.default_rng(seed)
    pieces = list(DrumPiece)
    hits = [
        hit(
            float(time),
            *(pieces[index] for index in rng.choice(len(pieces), size=int(rng.integers(1, 4)), replace=False)),
            strength=float(rng.random()),
        )
        for time in np.sort(rng.uniform(0.5, 9.0, size=80))
    ]
    charted = build_drum_expert_track(analysis_of(*hits), TEMPO, 10.0)
    check_drum_track(charted.track)
    for gems in gems_by_tick(charted.track).values():
        assert sum(gem.is_pad for gem in gems) <= 2


@pytest.mark.parametrize(
    "notes,message",
    [
        ([ChartNote(0, 1), ChartNote(0, 2, cymbal=True), ChartNote(0, 3)], "more than 2 pads"),
        ([ChartNote(0, 1, length=96)], "no sustain"),
        ([ChartNote(0, 2, forced=True)], "no sustain"),
    ],
)
def test_a_drum_track_that_breaks_a_rule_is_refused(notes, message):
    with pytest.raises(HardRuleViolation, match=message):
        check_drum_track(Track(Instrument.DRUMS, Difficulty.EXPERT, notes))


def test_nothing_lands_in_the_opening():
    charted = build_drum_expert_track(
        analysis_of(hit(1.0, DrumPiece.KICK), hit(4.9, DrumPiece.SNARE), hit(6.0, DrumPiece.SNARE)),
        TEMPO,
        10.0,
        not_before_s=5.0,
    )
    assert set(gems_by_tick(charted.track)) == {round(6.0 / BEAT * 192)}


def test_drums_are_charted_now():
    assert Instrument.DRUMS in CHARTABLE_INSTRUMENTS


@pytest.mark.heavy
def test_a_drum_stem_becomes_an_expert_drum_track(kit):
    events, _ = kit
    charted = build_tracks_for(Instrument.DRUMS, render(events), TEMPO, 36.0)
    assert [item.track.difficulty for item in charted] == list(Difficulty), "Expert, then the levels of C.2"
    check_drum_track(charted[0].track)
    assert charted[0].drum_chart is not None
    assert all(item.drum_chart is None for item in charted[1:]), "what was heard belongs to Expert"
    assert all(item.drum_measures is not None for item in charted)
    assert build_tracks_for(Instrument.DRUMS, np.zeros(SR * 5, dtype=np.float32), TEMPO, 5.0) == []


# ---------------------------------------------------------------- listening files


def test_the_listening_files_click_on_each_part(tmp_path):
    track = Track(
        Instrument.DRUMS,
        Difficulty.EXPERT,
        [
            DrumGem.KICK.note(384),
            DrumGem.YELLOW_CYMBAL.note(384),
            DrumGem.RED.note(576),
            DrumGem.BLUE_CYMBAL.note(768),
            DrumGem.GREEN_CYMBAL.note(960),
            DrumGem.KICK.note(960),
            DrumGem.BLUE_TOM.note(1152),
        ],
    )
    chart = Chart(SongMetadata("T", "A"), TEMPO, [track])
    path = DotChartExporter().export(chart, tmp_path)
    assert chart_drum_gems(path.read_text(encoding="utf-8-sig"))[384] == {DrumGem.KICK, DrumGem.YELLOW_CYMBAL}
    drums = np.zeros(SR * 5, dtype=np.float32)
    counts = write_drum_ear_test(path, drums, tmp_path / "debug")
    assert counts == {
        "drums_kick.wav": 2,
        "drums_snare.wav": 1,
        "drums_hihat.wav": 1,
        "drums_ride.wav": 1,
        "drums_crash.wav": 1,
        "drums_toms.wav": 1,
    }
    assert set(counts) == set(EAR_TEST_FILES)
    samples, rate = sf.read(str(tmp_path / "debug" / "drums_snare.wav"))
    assert rate == SR and samples.size == drums.size
    loud = np.flatnonzero(np.abs(samples) > 0.05)
    assert abs(loud[0] / SR - 1.5) < 0.005, "the snare's click is where its tick is: 576 ticks at 120 BPM"


# ---------------------------------------------------------------- whole builds


def stems_with_a_kit() -> dict[str, np.ndarray]:
    stems = song_stems(seconds=36.0)
    kit = resample(render(kit_pattern())[: 36 * SR], SR, STEM_SR)
    stems["drums"] = stereo(np.pad(kit, (0, 36 * STEM_SR - kit.size)).astype(np.float32))
    return stems


@pytest.mark.heavy
def test_a_build_charts_drums_says_what_is_not_verified_and_writes_listening_files(song_file, tmp_path):
    result = build_song(
        BuildConfig(
            input_path=song_file,
            metadata=SongMetadata("Kit", "Test"),
            instruments=frozenset({Instrument.DRUMS}),
            output_dir=tmp_path / "out",
            cache_dir=tmp_path / "cache",
            drum_ear_test=True,
        ),
        FakeSeparator(stems_with_a_kit()),
    )
    assert validate_song_folder(result.folder).ok
    ini = (result.folder / "song.ini").read_text(encoding="utf-8")
    assert "pro_drums = True" in ini.splitlines()
    text = (result.folder / "notes.chart").read_text(encoding="utf-8-sig")
    for level in ("Expert", "Hard", "Medium", "Easy"):
        assert f"[{level}Drums]" in text
    assert "N 66 0" in text and "N 67 0" in text, "hi-hats and rides are written as cymbals"
    analysis = json.loads((result.folder / "analysis.json").read_text(encoding="utf-8"))
    assert set(analysis["charts"]["drums"]) == {"expert", "hard", "medium", "easy"}
    for level in ("hard", "medium", "easy"):
        entry = analysis["charts"]["drums"][level]
        assert 0 < entry["measures"]["position_ratio"] <= 1
        assert "kick_share" in entry["soft_targets"] and "position_ratio" in entry["soft_targets"]
        assert set(entry["drums"]["not_verified"]["gems"]) == {"yellow_tom", "blue_tom", "green_tom", "green_cymbal"}
    assert len(analysis["drum_hard_rules"]) == 6, "three for every level, three between levels"
    drums = analysis["charts"]["drums"]["expert"]["drums"]
    assert drums["not_verified"]["parts"] == sorted(piece.value for piece in UNVERIFIED_PIECES)
    assert set(drums["not_verified"]["gems"]) == {"yellow_tom", "blue_tom", "green_tom", "green_cymbal"}
    assert drums["gems_by_kind"]["kick"] >= 30
    assert analysis["drum_hard_rules"]
    assert any("toms and crash are not verified" in warning for warning in analysis["warnings"])
    assert set(analysis["drum_ear_test"]["clicks_per_file"]) == set(EAR_TEST_FILES)
    for name in EAR_TEST_FILES:
        assert (result.folder / "debug" / name).is_file()


# ---------------------------------------------------------------- against the human


def test_a_chart_equal_to_the_human_scores_perfectly():
    human = [
        ReferenceDrumHit(TEMPO.seconds_at(float(tick)), tick, gems)
        for tick, gems in (
            (384, (DrumGem.KICK, DrumGem.YELLOW_CYMBAL)),
            (480, (DrumGem.RED, DrumGem.YELLOW_CYMBAL)),
            (576, (DrumGem.KICK, DrumGem.BLUE_CYMBAL)),
            (672, (DrumGem.RED, DrumGem.BLUE_TOM)),
        )
    ]
    track = Track(Instrument.DRUMS, Difficulty.EXPERT, [gem.note(hit.tick) for hit in human for gem in hit.gems])
    result = drum_metrics(track, TEMPO, human)
    for part in ("position", "kick", "snare", "cymbal", "tom"):
        assert result[part]["f1"] == 1.0, part
    assert result["hihat_ride_same_lane"] == 1.0
    assert result["worst_gem_gap"] == 0.0

    swapped = Track(
        Instrument.DRUMS,
        Difficulty.EXPERT,
        [
            (DrumGem.BLUE_CYMBAL if gem is DrumGem.YELLOW_CYMBAL else gem).note(hit.tick)
            for hit in human
            for gem in hit.gems
        ],
    )
    worse = drum_metrics(swapped, TEMPO, human)
    assert worse["cymbal"]["f1"] == 1.0, "a cymbal is a cymbal"
    assert worse["hihat_ride_same_lane"] == 0.333, "but two of the three yellow or blue ones on the wrong lane"


# ---------------------------------------------------------------- the real reference


@pytest.mark.real
@pytest.mark.parametrize("real_song", [CALIFORNICATION], indirect=True)
def test_californication_drums_meet_the_acceptance_targets(real_song):
    """Expert against the human chart. Californication is train: the settings were chosen on it."""
    from chartgen.evaluation.drum_metrics import channel_metrics
    from chartgen.evaluation.reference import load_drum_channels

    tempo = real_song.tempo
    charted = build_tracks_for(
        Instrument.DRUMS,
        real_song.mono("drums"),
        tempo.tempo_map,
        real_song.stems.duration_s,
        not_before_s=tempo.lead_in_end_s,
    )
    song = real_song.reference
    human = song.drums.levels[Difficulty.EXPERT]
    result = drum_metrics(charted[0].track, tempo.tempo_map, human)
    channels = channel_metrics(charted[0].track, tempo.tempo_map, human, load_drum_channels(song.source))
    print(json.dumps({**result, "channels": channels}, indent=1))
    assert set(channels) == {"kick", "snare", "rest"}, "diagnosis only: nothing about it is asserted"
    assert result["position"]["f1"] >= 0.85
    assert result["kick"]["f1"] >= 0.80
    assert result["snare"]["f1"] >= 0.70
    assert result["cymbal"]["f1"] >= 0.80
    assert result["hihat_ride_same_lane"] >= 0.75
    assert result["worst_gem_gap"] <= 0.12
