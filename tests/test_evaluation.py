"""The reference evaluation, on small references built here: no real song is involved."""

import json
import os
import shutil
import struct
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from conftest import SR, FakeSeparator, californication_reference, click_times, clicks_at, sine, stereo

from chartgen.audio.separation import STEM_NAMES
from chartgen.chart.fret_mapping import is_playable
from chartgen.cli import main
from chartgen.clonehero.package import encode_ogg
from chartgen.core.model import ChartNote, Difficulty, Instrument, Track
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent
from chartgen.errors import ChartgenError
from chartgen.evaluation.formats import ReferenceFormatError, open_sng, parse_midi
from chartgen.evaluation.metrics import (
    average,
    chart_metrics,
    human_level_measures,
    match_notes,
    naive_reductions,
    position_f1,
    tempo_metrics,
)
from chartgen.evaluation.reference import (
    ReferenceNote,
    find_references,
    load_reference,
    split_of,
)
from chartgen.evaluation.run import _lane_gaps, evaluate_folder, format_report, write_report

SECONDS = 20
BPM = 120
DIVISION = 480
TIMES = click_times(BPM, SECONDS, 0.5)


def vlq(value: int) -> bytes:
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(out))


def midi_track(events: list[tuple[int, bytes]]) -> bytes:
    body = b""
    last = 0
    for tick, data in sorted(events, key=lambda item: item[0]):
        body += vlq(tick - last) + data
        last = tick
    body += vlq(0) + b"\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + body


def midi_bytes(lanes=(0, 1, 2, 3, 4), track_name=b"PART GUITAR") -> bytes:
    micros = int(60e6 / BPM)
    first_beat = int(0.5 / (60 / BPM) * DIVISION)
    tempo = midi_track(
        [
            (0, b"\xff\x51\x03" + micros.to_bytes(3, "big")),
            (0, b"\xff\x58\x04\x04\x02\x18\x08"),
        ]
    )
    notes: list[tuple[int, bytes]] = [(0, b"\xff\x03" + bytes([len(track_name)]) + track_name)]
    for index, _ in enumerate(TIMES):
        tick = first_beat + index * DIVISION
        lane = lanes[index % len(lanes)]
        notes.append((tick, bytes([0x90, 96 + lane, 100])))
        notes.append((tick + DIVISION // 4, bytes([0x80, 96 + lane, 0])))
    header = b"MThd" + struct.pack(">IHHH", 6, 1, 2, DIVISION)
    return header + tempo + midi_track(notes)


def sng_bytes(files: dict[str, bytes], metadata: dict[str, str] | None = None) -> bytes:
    mask = bytes(range(200, 216))
    meta = b""
    entries = metadata or {"name": "Test", "artist": "Test"}
    for key, value in entries.items():
        meta += struct.pack("<i", len(key)) + key.encode()
        meta += struct.pack("<i", len(value)) + value.encode()
    head = b"SNGPKG" + struct.pack("<I", 1) + mask
    head += struct.pack("<QQ", len(meta) + 8, len(entries)) + meta
    index_size = sum(1 + len(name) + 16 for name in files) + 8
    offset = len(head) + 8 + index_size + 8
    index = b""
    payload = b""
    for name, data in files.items():
        index += bytes([len(name)]) + name.encode() + struct.pack("<QQ", len(data), offset)
        positions = np.arange(len(data), dtype=np.uint64)
        key = np.frombuffer(mask, dtype=np.uint8)
        pattern = key[(positions % 16).astype(np.int64)] ^ (positions & 0xFF).astype(np.uint8)
        payload += (np.frombuffer(data, dtype=np.uint8) ^ pattern).tobytes()
        offset += len(data)
    return head + struct.pack("<QQ", index_size, len(files)) + index + struct.pack("<Q", len(payload)) + payload


def wav_bytes(tmp_path: Path) -> bytes:
    path = tmp_path / "temp.wav"
    sf.write(str(path), stereo(clicks_at(TIMES, SECONDS, SR)), SR)
    data = path.read_bytes()
    path.unlink()
    return data


def make_sng(folder: Path, name="song.sng", **kwargs) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    files = {"notes.mid": midi_bytes(**kwargs), "song.wav": wav_bytes(folder)}
    path.write_bytes(sng_bytes(files))
    return path


def make_chart_folder(folder: Path) -> Path:
    folder.mkdir(parents=True)
    ticks = [int(0.5 / (60 / BPM) * 192) + index * 192 for index in range(len(TIMES))]
    notes = "\n".join(f"  {tick} = N {index % 5} 48" for index, tick in enumerate(ticks))
    (folder / "notes.chart").write_text(
        f"[Song]\n{{\n  Resolution = 192\n}}\n[SyncTrack]\n{{\n  0 = TS 4\n  0 = B {BPM * 1000}\n}}\n"
        f"[ExpertSingle]\n{{\n{notes}\n}}\n",
        encoding="utf-8",
    )
    encode_ogg(stereo(clicks_at(TIMES, SECONDS, SR)), SR, folder / "guitar.ogg")
    (folder / "preview.ogg").write_bytes(b"not audio, must be ignored")
    return folder


def separator_for(frames: int = SR * SECONDS) -> FakeSeparator:
    silence = np.zeros((frames, 2), dtype=np.float32)
    stems = {name: silence.copy() for name in STEM_NAMES}
    stems["guitar"] = stereo(clicks_at(TIMES, SECONDS, SR))
    stems["bass"] = stereo(sine(82, SECONDS, amp=0.1))
    return FakeSeparator(stems)


# ---------------------------------------------------------------- reading references


def test_midi_is_read_correctly():
    midi = parse_midi(midi_bytes())
    assert midi.division == DIVISION
    assert midi.tempos == [(0, 500000)]
    assert midi.signatures == [(0, 4, 4)]
    track = midi.tracks["PART GUITAR"]
    assert len(track.notes) == len(TIMES)
    assert track.notes[0][1] == 96
    assert track.notes[0][2] == DIVISION // 4


@pytest.mark.parametrize("data", [b"", b"nonsense", b"MThd\x00\x00"], ids=["empty", "text", "cut off"])
def test_broken_midi_gives_a_clear_error(data):
    with pytest.raises(ReferenceFormatError):
        parse_midi(data)


def test_sng_container_round_trip(tmp_path):
    path = tmp_path / "a.sng"
    path.write_bytes(sng_bytes({"notes.mid": b"hello world", "x.txt": bytes(range(200))}, {"delay": "120"}))
    container = open_sng(path)
    assert container.metadata == {"delay": "120"}
    assert container.read("notes.mid") == b"hello world"
    assert container.read("x.txt") == bytes(range(200))


def test_sng_entry_names_cannot_escape_the_folder(tmp_path):
    path = tmp_path / "a.sng"
    path.write_bytes(sng_bytes({"../../evil.txt": b"x"}))
    assert list(open_sng(path).entries) == ["evil.txt"]


def test_text_mangled_sng_gives_a_clear_error(tmp_path):
    """Regression test: a real copy had been saved as text, which breaks the header."""
    original = sng_bytes({"notes.mid": b"hello"})
    path = tmp_path / "broken.sng"
    path.write_bytes(original.decode("utf-8", errors="replace").encode("utf-8"))
    with pytest.raises(ReferenceFormatError):
        open_sng(path)
    other = tmp_path / "other.sng"
    other.write_bytes(b"not an sng at all")
    with pytest.raises(ReferenceFormatError):
        open_sng(other)


def test_references_are_found_recursively(tmp_path):
    make_sng(tmp_path / "a")
    make_sng(tmp_path / "b" / "deep", name="other.sng")
    make_chart_folder(tmp_path / "c")
    (tmp_path / "unrelated.txt").write_text("x", encoding="utf-8")
    found = find_references(tmp_path)
    assert {path.name for path in found} == {"song.sng", "other.sng", "c"}


def test_sng_reference_holds_the_human_chart(tmp_path):
    song = load_reference(make_sng(tmp_path))
    assert len(song.notes) == len(TIMES)
    assert song.notes[0].time_s == pytest.approx(0.5)
    assert song.notes[0].lanes == (0,)
    assert song.notes[0].length_s == pytest.approx(60 / BPM / 4)
    assert np.median(np.diff(song.beats)) == pytest.approx(0.5)
    assert np.median(np.diff(song.bars)) == pytest.approx(2.0)
    assert song.audio.duration_s == pytest.approx(SECONDS)


def test_chart_folder_reference_ignores_previews(tmp_path):
    song = load_reference(make_chart_folder(tmp_path / "song"))
    assert len(song.notes) == len(TIMES)
    assert song.notes[0].time_s == pytest.approx(0.5)
    assert song.notes[1].lanes == (1,)


def test_delay_shifts_the_human_chart(tmp_path):
    path = tmp_path / "d.sng"
    files = {"notes.mid": midi_bytes(), "song.wav": wav_bytes(tmp_path)}
    path.write_bytes(sng_bytes(files, {"delay": "100"}))
    assert load_reference(path).notes[0].time_s == pytest.approx(0.6)


def level_midi_bytes() -> bytes:
    """Expert on every beat, Hard on every second, Easy on every fourth; no Medium.

    Hard also has a close pair of notes, one a natural HOPO, and a forced HOPO and forced strum.
    """
    tempo = midi_track([(0, b"\xff\x51\x03" + int(60e6 / BPM).to_bytes(3, "big"))])
    notes: list[tuple[int, bytes]] = [(0, b"\xff\x03\x0bPART GUITAR")]

    def add(tick: int, note: int, length: int = DIVISION // 8) -> None:
        notes.append((tick, bytes([0x90, note, 100])))
        notes.append((tick + length, bytes([0x80, note, 0])))

    for index in range(32):
        tick = DIVISION + index * DIVISION
        add(tick, 96 + index % 4)
        if index % 2 == 0:
            add(tick, 84 + index % 4)
        if index % 4 == 0:
            add(tick, 60 + index % 3)
    add(DIVISION + DIVISION // 4, 84 + 3)  # 120 ticks after the first Hard note: a natural HOPO.
    add(DIVISION * 5, 84 + 5, DIVISION // 8)  # Force the Hard note on this tick to a HOPO.
    add(DIVISION * 7, 84 + 6, DIVISION // 8)  # Force this one to a strum: it changes nothing.
    header = b"MThd" + struct.pack(">IHHH", 6, 1, 2, DIVISION)
    return header + tempo + midi_track(notes)


def test_all_levels_and_their_force_markers_are_read_from_midi(tmp_path):
    path = tmp_path / "levels.sng"
    path.write_bytes(sng_bytes({"notes.mid": level_midi_bytes(), "song.wav": wav_bytes(tmp_path)}))
    song = load_reference(path)
    assert song.is_midi
    assert song.resolution == DIVISION
    assert set(song.levels) == {Difficulty.EXPERT, Difficulty.HARD, Difficulty.EASY}
    assert len(song.levels[Difficulty.EXPERT]) == 32
    assert song.notes == song.levels[Difficulty.EXPERT]
    assert len(song.levels[Difficulty.EASY]) == 8

    hard = {note.tick: note for note in song.levels[Difficulty.HARD]}
    assert hard[DIVISION + DIVISION // 4].hopo, "close to the previous note, on another fret"
    assert hard[DIVISION * 5].hopo, "the force marker"
    assert not hard[DIVISION * 7].hopo
    assert sum(note.hopo for note in hard.values()) == 2


def test_all_levels_and_their_force_flags_are_read_from_a_chart(tmp_path):
    folder = make_chart_folder(tmp_path / "song")
    path = folder / "notes.chart"
    text = path.read_text(encoding="utf-8").replace(
        "[ExpertSingle]",
        "[HardSingle]\n{\n  192 = N 0 0\n  240 = N 1 0\n  384 = N 2 0\n  432 = N 3 0\n  432 = N 5 0\n}\n"
        "[ExpertSingle]",
    )
    path.write_text(text, encoding="utf-8")
    song = load_reference(folder)
    assert not song.is_midi
    assert song.resolution == 192
    hard = {note.tick: note for note in song.levels[Difficulty.HARD]}
    assert set(hard) == {192, 240, 384, 432}
    assert hard[240].hopo, "48 ticks after another fret"
    assert not hard[432].hopo, "the flag flips what would have been a HOPO"
    assert not hard[192].hopo and not hard[384].hopo


def test_reference_without_guitar_part_is_refused(tmp_path):
    with pytest.raises(ChartgenError, match="PART GUITAR"):
        load_reference(make_sng(tmp_path, track_name=b"PART DRUMS"))


# ---------------------------------------------------------------- metrics


def perfect_track(lanes=(0, 1, 2, 3, 4)) -> tuple[Track, TempoMap, list[ReferenceNote]]:
    tempo_map = TempoMap([TempoEvent(0, 120.0)], [TimeSignatureEvent(0, 4, 4)])
    notes = []
    human = []
    for index in range(40):
        tick = 192 + index * 192
        lane = lanes[index % len(lanes)]
        notes.append(ChartNote(tick, lane))
        human.append(ReferenceNote(tempo_map.seconds_at(float(tick)), (lane,), 0.1))
    return Track(Instrument.GUITAR, Difficulty.EXPERT, notes), tempo_map, human


def test_naive_reductions_keep_what_they_say():
    ticks = np.arange(0, 192 * 8, 48)
    result = naive_reductions(ticks, 192, 8)
    assert np.array_equal(result["every_nth"], ticks[np.round(np.linspace(0, 31, 8)).astype(int)])
    assert np.array_equal(result["beats_first"], ticks[ticks % 192 == 0])
    assert naive_reductions(ticks, 192, 12)["beats_first"].size == 12
    assert np.all(np.isin(ticks[ticks % 192 == 0], naive_reductions(ticks, 192, 12)["beats_first"]))
    assert naive_reductions(ticks, 192, 99)["every_nth"].size == ticks.size


def test_lane_gaps_compare_each_lane_with_the_human():
    mine = dict(green_share=0.5, red_share=0.2, yellow_share=0.2, blue_share=0.1, orange_share=0.0)
    human = dict(green_share=0.3, red_share=0.2, yellow_share=0.2, blue_share=0.2, orange_share=0.1)
    assert _lane_gaps(mine, human, 0.1) == {"worst_lane_gap": 0.2, "lanes_over_limit": 1}
    assert _lane_gaps(mine, mine, 0.1) == {"worst_lane_gap": 0.0, "lanes_over_limit": 0}


def test_position_f1():
    times = np.array([1.0, 2.0, 3.0, 4.0])
    assert position_f1(times, times) == 1.0
    assert position_f1(times[:2], times) == pytest.approx(2 * 1.0 * 0.5 / 1.5, abs=0.001)
    assert position_f1(times, times + 1.5) == 0.0


def test_human_level_measures_use_the_human_tempo_and_sustain_rule():
    notes = [
        ReferenceNote(0.0, (0, 1), 1.0, tick=0, length_ticks=480, hopo=False),
        ReferenceNote(0.5, (2,), 0.05, tick=480, length_ticks=48, hopo=False),
        ReferenceNote(0.75, (3,), 0.05, tick=720, length_ticks=48, hopo=True),
    ]
    measures = human_level_measures(notes, 480, expert_positions=6, is_midi=True)
    assert measures.positions == 3
    assert measures.position_ratio == 0.5
    assert measures.chord_share == pytest.approx(1 / 3, abs=0.001)
    assert measures.on_beat_share == pytest.approx(2 / 3, abs=0.001)
    assert measures.sustain_share == pytest.approx(1 / 3, abs=0.001)
    assert measures.final_hopo_share == pytest.approx(1 / 3, abs=0.001)
    assert measures.min_gap_s == 0.25


@pytest.mark.heavy
def test_every_difficulty_is_reported_next_to_the_human_and_the_baselines(tmp_path):
    path = tmp_path / "train" / "levels.sng"
    path.parent.mkdir()
    path.write_bytes(sng_bytes({"notes.mid": level_midi_bytes(), "song.wav": wav_bytes(tmp_path)}))
    report = evaluate_folder(tmp_path, separator_for(), tmp_path / "cache")
    levels = report.songs["levels"]["levels"]
    assert set(levels) == {"expert", "hard", "medium", "easy"}
    assert {"mine", "human", "match"} <= set(levels["hard"])
    assert "human" not in levels["medium"], "this chart has no Medium"
    assert {"note_f1", "every_nth_f1", "beats_first_f1"} <= set(levels["easy"]["match"])
    assert "every_nth_f1" not in levels["expert"]["match"]
    assert levels["hard"]["mine"]["auto_hopo_share"] >= 0
    assert levels["hard"]["human"]["final_hopo_share"] > 0
    text = format_report(report)
    for label in (
        "Difficulties of levels",
        "F1 every Nth",
        "F1 beats first",
        "auto HOPO",
        "final HOPO",
        "worst lane gap",
        "lanes over limit",
        "misses its soft targets",
    ):
        assert label in text
    assert levels["hard"]["match"]["worst_lane_gap"] >= 0
    assert 0 <= levels["hard"]["match"]["lanes_over_limit"] <= 5
    assert levels["hard"]["missed_targets"], "single notes on a click cannot reach any chord share"
    assert report.level_averages["train"]["hard"]["human"]["positions"] == levels["hard"]["human"]["positions"]
    output = tmp_path / "report.json"
    write_report(report, output)
    stored = json.loads(output.read_text(encoding="utf-8"))
    assert stored["train"]["songs"]["levels"]["levels"]["easy"]["match"]["beats_first_f1"] >= 0
    assert "average_by_difficulty" in stored["train"]


def test_identical_chart_scores_perfectly():
    track, tempo_map, human = perfect_track()
    metrics = chart_metrics(track, tempo_map, human)
    assert metrics["note_f1"] == 1.0
    assert metrics["direction_when_human_moves"] == 1.0
    assert metrics["direction_all_steps"] == 1.0
    assert metrics["chord_agreement"] == 1.0


def test_opposite_direction_scores_zero_on_moves():
    track, tempo_map, human = perfect_track((0, 1, 2, 3, 4))
    flipped = [ChartNote(note.tick, 4 - note.lane) for note in track.notes]
    metrics = chart_metrics(Track(track.instrument, track.difficulty, flipped), tempo_map, human)
    assert metrics["note_f1"] == 1.0
    assert metrics["direction_when_human_moves"] < 0.3


def test_missing_notes_lower_recall_extra_notes_lower_precision():
    track, tempo_map, human = perfect_track()
    half = Track(track.instrument, track.difficulty, track.notes[::2])
    metrics = chart_metrics(half, tempo_map, human)
    assert metrics["note_precision"] == 1.0
    assert metrics["note_recall"] == 0.5
    metrics = chart_metrics(track, tempo_map, human[::2])
    assert metrics["note_recall"] == 1.0
    assert metrics["note_precision"] == 0.5


def test_chord_and_sustain_agreement():
    tempo_map = TempoMap([TempoEvent(0, 120.0)])
    notes = [ChartNote(192, 0, 192), ChartNote(192, 1, 192), ChartNote(384, 2), ChartNote(576, 3)]
    human = [
        ReferenceNote(0.5, (0, 1), 0.5),
        ReferenceNote(1.0, (2,), 0.0625),
        ReferenceNote(1.5, (3,), 0.0625),
    ]
    metrics = chart_metrics(Track(Instrument.GUITAR, Difficulty.EXPERT, notes), tempo_map, human)
    assert metrics["chord_agreement"] == 1.0
    assert metrics["sustain_f1"] == 1.0
    assert metrics["sustain_share_human"] == pytest.approx(1 / 3, abs=0.01)


def test_empty_chart_scores_zero_without_failing():
    track, tempo_map, human = perfect_track()
    metrics = chart_metrics(Track(track.instrument, track.difficulty), tempo_map, human)
    assert metrics["note_f1"] == 0.0


def test_a_human_note_is_matched_only_once():
    pairs = match_notes(np.array([1.0, 1.01, 1.02]), np.array([1.0]), 0.07)
    assert len(pairs) == 1


def test_tempo_metrics_notice_a_shifted_grid():
    beats = 0.5 + np.arange(100) * 0.5
    bars = 0.5 + np.arange(25) * 2.0
    exact = TempoMap([TempoEvent(0, 120.0)], [TimeSignatureEvent(0, 2, 4), TimeSignatureEvent(384, 4, 4)])
    good = tempo_metrics(exact, beats, bars, 50.0)
    assert good["beats_within_35ms"] == 1.0
    assert good["human_bpm"] == 120.0
    shifted = TempoMap([TempoEvent(0, 100.0), TempoEvent(192, 120.0)])
    bad = tempo_metrics(shifted, beats, bars, 50.0)
    assert bad["beats_within_35ms"] < 0.2


def test_average_covers_every_song():
    assert average([{"a": 1.0, "b": 2.0}, {"a": 3.0}]) == {"a": 2.0, "b": 2.0}


# ---------------------------------------------------------------- whole runs


def test_folder_gives_a_result_per_song_and_an_average(tmp_path):
    make_sng(tmp_path / "refs" / "one", name="first.sng")
    make_chart_folder(tmp_path / "refs" / "second")
    report = evaluate_folder(tmp_path / "refs", separator_for(), tmp_path / "cache")
    assert set(report.songs) == {"first", "second"}
    for result in report.songs.values():
        assert result["note_f1"] > 0.9
        assert result["bpm"] == pytest.approx(120, abs=0.2)
        assert result["beats_within_35ms"] > 0.9
    first, second = report.songs["first"], report.songs["second"]
    assert report.averages["unassigned"]["note_f1"] == pytest.approx(
        (first["note_f1"] + second["note_f1"]) / 2, abs=0.001
    )
    text = format_report(report)
    assert "first" in text and "second" in text and "average" in text
    assert "move these into one of them" in text


@pytest.mark.heavy
def test_broken_reference_does_not_stop_the_others(tmp_path):
    make_sng(tmp_path / "refs" / "good", name="good.sng")
    (tmp_path / "refs" / "bad.sng").write_bytes(b"corrupt")
    report = evaluate_folder(tmp_path / "refs", separator_for(), tmp_path / "cache")
    assert set(report.songs) == {"good"}
    assert "bad.sng" in report.failures


def test_empty_folder_gives_a_clear_error(tmp_path):
    with pytest.raises(ChartgenError, match="No .sng"):
        evaluate_folder(tmp_path, separator_for(), tmp_path / "cache")


@pytest.mark.heavy
def test_report_can_be_written_as_json(tmp_path):
    make_sng(tmp_path / "refs")
    report = evaluate_folder(tmp_path / "refs", separator_for(), tmp_path / "cache")
    output = tmp_path / "report.json"
    write_report(report, output)
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert set(saved) == {"unassigned", "failures"}
    assert set(saved["unassigned"]) == {"songs", "average", "average_by_difficulty"}


def train_test_folder(tmp_path) -> Path:
    make_sng(tmp_path / "refs" / "train", name="tuned.sng")
    make_sng(tmp_path / "refs" / "test", name="unseen.sng")
    make_sng(tmp_path / "refs" / "test" / "nested", name="unseen2.sng")
    return tmp_path / "refs"


def test_splits_come_from_the_folder_under_the_root(tmp_path):
    root = train_test_folder(tmp_path)
    assert split_of(root / "train" / "tuned.sng", root) == "train"
    assert split_of(root / "test" / "nested" / "unseen2.sng", root) == "test"
    assert split_of(root / "song.sng", root) == "unassigned"
    assert split_of(root / "other" / "song.sng", root) == "unassigned"
    assert split_of(root / "TEST" / "song.sng", root) == "test"


@pytest.mark.heavy
def test_train_and_test_are_reported_separately(tmp_path):
    root = train_test_folder(tmp_path)
    report = evaluate_folder(root, separator_for(), tmp_path / "cache")
    assert report.splits == {"tuned": "train", "unseen": "test", "unseen2": "test"}
    assert set(report.averages) == {"train", "test"}
    text = format_report(report)
    assert text.index("TEST: never tune") < text.index("TRAIN: used for tuning")
    assert "No test references" not in text


@pytest.mark.heavy
def test_train_songs_never_count_toward_the_test_average(tmp_path):
    root = train_test_folder(tmp_path)
    report = evaluate_folder(root, separator_for(), tmp_path / "cache")
    report.songs["unseen"]["note_f1"] = 0.5
    report.songs["unseen2"]["note_f1"] = 0.7
    report.songs["tuned"]["note_f1"] = 1.0
    from chartgen.evaluation.metrics import average as mean

    test_only = mean([report.songs[n] for n in report.songs if report.splits[n] == "test"])
    assert test_only["note_f1"] == pytest.approx(0.6)


@pytest.mark.parametrize("split,expected", [("train", {"tuned"}), ("test", {"unseen", "unseen2"})])
@pytest.mark.heavy
def test_one_split_can_be_evaluated_alone(tmp_path, split, expected):
    root = train_test_folder(tmp_path)
    report = evaluate_folder(root, separator_for(), tmp_path / "cache", split)
    assert set(report.songs) == expected


@pytest.mark.heavy
def test_missing_test_references_are_pointed_out(tmp_path):
    make_sng(tmp_path / "refs" / "train", name="tuned.sng")
    report = evaluate_folder(tmp_path / "refs", separator_for(), tmp_path / "cache")
    assert "No test references" in format_report(report)
    with pytest.raises(ChartgenError, match="in test/"):
        evaluate_folder(tmp_path / "refs", separator_for(), tmp_path / "cache", "test")


@pytest.mark.heavy
def test_json_report_keeps_the_splits_apart(tmp_path):
    root = train_test_folder(tmp_path)
    report = evaluate_folder(root, separator_for(), tmp_path / "cache")
    output = tmp_path / "report.json"
    write_report(report, output)
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert set(saved["train"]["songs"]) == {"tuned"}
    assert set(saved["test"]["songs"]) == {"unseen", "unseen2"}


@pytest.mark.heavy
def test_cli_evaluate(tmp_path, monkeypatch):
    make_sng(tmp_path / "refs")
    monkeypatch.setattr("chartgen.audio.separation.DemucsSeparator", lambda device="auto": separator_for())
    assert main(["evaluate", str(tmp_path / "refs"), "--cache-dir", str(tmp_path / "cache")]) == 0
    assert main(["evaluate", str(tmp_path / "nothing"), "--cache-dir", str(tmp_path / "cache")]) == 2


def test_generated_charts_are_playable_on_a_reference(tmp_path):
    from chartgen.chart.charter import build_expert_track

    song = load_reference(make_sng(tmp_path))
    mono = song.audio.samples.mean(axis=1)
    from chartgen.audio.io import analysis_mono

    tempo_map = TempoMap([TempoEvent(0, 120.0)])
    track = build_expert_track(
        Instrument.GUITAR, analysis_mono(song.audio.samples, song.audio.samplerate), tempo_map, SECONDS
    ).track
    assert mono.size > 0
    by_tick: dict[int, list[int]] = {}
    for note in track.notes:
        by_tick.setdefault(note.tick, []).append(note.lane)
    ticks = sorted(by_tick)
    assert is_playable([tuple(sorted(by_tick[t])) for t in ticks], [tempo_map.seconds_at(float(t)) for t in ticks])


@pytest.mark.real
def test_real_references_when_available(tmp_path):
    """Set CHARTGEN_REFERENCE_DIR to a folder of .sng files or chart folders to run this.

    Only Californication is evaluated: the floors below were set on it, so it is train. Every other
    reference is measured with ``chartgen evaluate`` and held to no floor here; a test song held to a
    floor would be tuned on. The stem cache is keyed by the file's contents, so the linked copy finds
    the same stems.
    """
    from chartgen.audio.separation import DemucsSeparator

    source = californication_reference()
    (tmp_path / "train").mkdir()
    target = tmp_path / "train" / source.name
    if source.is_file():
        try:
            os.link(source, target)
        except OSError:
            shutil.copyfile(source, target)
    else:
        shutil.copytree(source, target)
    report = evaluate_folder(tmp_path, DemucsSeparator(), Path(".cache/stems"))
    assert list(report.songs) == [source.stem if source.is_file() else source.name]
    assert set(report.averages) == {"train"}
    for averages in report.averages.values():
        assert averages["bars_agreeing"] >= 0.8
    # The targets for bass approved by the owner. Its settings were chosen on this song, so it is train.
    floors = {"expert": 0.81, "hard": 0.77, "medium": 0.76, "easy": 0.64}
    direction = {"expert": 0.65, "hard": 0.60, "medium": 0.60, "easy": 0.60}
    worst_lane = {"expert": 0.12, "hard": 0.10, "medium": 0.10, "easy": 0.10}
    for averages in report.bass_level_averages.values():
        for level, floor in floors.items():
            match = averages[level]["match"]
            assert match["note_f1"] >= floor, level
            assert match["direction_when_human_moves"] >= direction[level], level
            assert match["worst_lane_gap"] <= worst_lane[level], level
            if level != "expert":
                assert match["note_f1"] > match["beats_first_f1"], level
        assert 0.60 <= averages["expert"]["mine"]["hand_travel"] <= 1.00
        for level in ("expert", "hard"):
            assert 0.10 <= averages[level]["mine"]["orange_share"] <= 0.25, level
