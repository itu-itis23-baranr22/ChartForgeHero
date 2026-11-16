"""Phase D, D.0: reading and measuring a song's structure. Sections, star power and the preview of a
human chart, and the measures our own will be held to. No audio is analysed here."""

import struct

import numpy as np
import pytest
from conftest import CALIFORNICATION, SR, clicks_at, stereo
from test_evaluation import BPM, DIVISION, SECONDS, TIMES, midi_track, separator_for, sng_bytes, wav_bytes

from chartgen.clonehero.package import encode_ogg
from chartgen.core.model import Instrument
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent
from chartgen.evaluation.reference import load_reference
from chartgen.evaluation.run import (
    _structure_lines,
    analysis_signals,
    compare_structure,
    evaluate_folder,
    format_report,
)
from chartgen.evaluation.structure_metrics import (
    bar_lines_s,
    boundary_scores,
    chorus_in_window,
    is_chorus,
    match_within,
    naive_section_baselines,
    preview_comparison,
    section_at,
    star_power_summary,
)

BAR_S = 4 * 60 / BPM
"""Two seconds at 120 BPM in 4/4."""


def text_event(text: str) -> bytes:
    data = text.encode("latin-1")
    return b"\xff\x01" + bytes([len(data)]) + data


def note(tick: int, number: int, length: int) -> list[tuple[int, bytes]]:
    return [(tick, bytes([0x90, number, 100])), (tick + length, bytes([0x80, number, 0]))]


def structured_midi() -> bytes:
    """Guitar notes on every beat, two sections, star power on guitar and drums, and other events."""
    tempo = midi_track([(0, b"\xff\x51\x03" + int(60e6 / BPM).to_bytes(3, "big")), (0, b"\xff\x58\x04\x04\x02\x18\x08")])
    first_beat = int(0.5 / (60 / BPM) * DIVISION)
    guitar = [(0, b"\xff\x03\x0bPART GUITAR")]
    for index, _ in enumerate(TIMES):
        guitar += note(first_beat + index * DIVISION, 96 + index % 5, DIVISION // 4)
    guitar += note(4 * DIVISION, 116, 4 * DIVISION) + note(16 * DIVISION, 116, 4 * DIVISION)
    drums = [(0, b"\xff\x03\x0aPART DRUMS")] + note(4 * DIVISION, 96, 10) + note(4 * DIVISION, 116, 4 * DIVISION)
    events = [
        (0, b"\xff\x03\x06EVENTS"),
        (0, text_event("[music_start]")),
        (4 * DIVISION, text_event("[prc_verse_1]")),
        (20 * DIVISION, text_event("[section chorus 1]")),
        (36 * DIVISION, text_event("[end]")),
    ]
    tracks = [tempo, midi_track(guitar), midi_track(drums), midi_track(events)]
    return b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), DIVISION) + b"".join(tracks)


def structured_sng(folder, metadata=None):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "structured.sng"
    files = {"notes.mid": structured_midi(), "song.wav": wav_bytes(folder)}
    path.write_bytes(sng_bytes(files, metadata or {"name": "S", "artist": "A", "preview_start_time": "12500"}))
    return path


# ---------------------------------------------------------------- reading a human chart


def test_a_midi_chart_gives_its_sections_star_power_and_preview(tmp_path):
    song = load_reference(structured_sng(tmp_path))
    assert [(section.name, section.tick) for section in song.sections] == [("verse_1", 4 * DIVISION), ("chorus 1", 20 * DIVISION)]
    assert song.sections[0].time_s == pytest.approx(2.0), "four beats at 120 BPM"
    assert set(song.star_power) == {Instrument.GUITAR, Instrument.DRUMS}
    guitar = song.star_power[Instrument.GUITAR]
    assert [(phrase.tick, phrase.length_ticks) for phrase in guitar] == [(4 * DIVISION, 4 * DIVISION), (16 * DIVISION, 4 * DIVISION)]
    assert guitar[0].start_s == pytest.approx(2.0) and guitar[0].end_s == pytest.approx(4.0)
    assert song.preview_start_s == pytest.approx(12.5)


@pytest.mark.parametrize("value", [None, "-1", "", "soon"])
def test_a_missing_or_unset_preview_is_none(tmp_path, value):
    metadata = {"name": "S", "artist": "A"}
    if value is not None:
        metadata["preview_start_time"] = value
    assert load_reference(structured_sng(tmp_path, metadata)).preview_start_s is None


def test_a_chart_folder_gives_its_sections_star_power_and_preview(tmp_path):
    folder = tmp_path / "song"
    folder.mkdir()
    notes = "\n".join(f"  {384 + index * 192} = N {index % 5} 0" for index in range(len(TIMES)))
    (folder / "notes.chart").write_text(
        "[Song]\n{\n  Resolution = 192\n}\n[SyncTrack]\n{\n  0 = TS 4\n  0 = B 120000\n}\n"
        '[Events]\n{\n  768 = E "section Verse 1"\n  1536 = E "lyric hello"\n  3072 = E "section Chorus"\n}\n'
        f"[ExpertSingle]\n{{\n  768 = S 2 768\n{notes}\n}}\n"
        "[ExpertDrums]\n{\n  768 = N 0 0\n  768 = S 2 384\n  1536 = S 64 192\n}\n",
        encoding="utf-8",
    )
    (folder / "song.ini").write_text("[song]\nname = S\nartist = A\npreview_start_time = 30000\n", encoding="utf-8")
    encode_ogg(stereo(clicks_at(TIMES, SECONDS, SR)), SR, folder / "guitar.ogg")
    song = load_reference(folder)
    assert [(section.name, section.time_s) for section in song.sections] == [
        ("Verse 1", pytest.approx(2.0)),
        ("Chorus", pytest.approx(8.0)),
    ], "a lyric is not a section"
    assert [(phrase.tick, phrase.length_ticks) for phrase in song.star_power[Instrument.GUITAR]] == [(768, 768)]
    assert [(phrase.tick, phrase.length_ticks) for phrase in song.star_power[Instrument.DRUMS]] == [(768, 384)], "S 64 is not star power"
    assert song.preview_start_s == pytest.approx(30.0)


def test_a_chart_without_structure_reads_as_empty(tmp_path):
    from test_evaluation import make_sng

    song = load_reference(make_sng(tmp_path))
    assert song.sections == () and song.star_power == {} and song.preview_start_s is None


# ---------------------------------------------------------------- the measures


TEMPO = TempoMap([TempoEvent(0, 120.0)], [TimeSignatureEvent(0, 4, 4)])
BARS = bar_lines_s(TEMPO, 100.0)


def test_bar_lines_follow_the_time_signatures():
    assert BARS[:3] == pytest.approx([0.0, 2.0, 4.0])
    waltz = TempoMap([TempoEvent(0, 120.0)], [TimeSignatureEvent(0, 3, 4), TimeSignatureEvent(3 * 192 * 2, 4, 4)])
    assert bar_lines_s(waltz, 9.0) == pytest.approx([0.0, 1.5, 3.0, 5.0, 7.0, 9.0])


def test_a_boundary_matches_within_its_bar_and_only_once():
    assert boundary_scores([10.0, 20.0], [10.0, 20.0], BARS)["f1"] == 1.0
    assert boundary_scores([11.9], [10.0], BARS)["f1"] == 1.0, "1.9 s is within a two-second bar"
    assert boundary_scores([12.1], [10.0], BARS)["f1"] == 0.0
    two_near_one = boundary_scores([9.5, 10.5], [10.0], BARS)
    assert (two_near_one["precision"], two_near_one["recall"]) == (0.5, 1.0)
    assert match_within(np.array([10.0, 11.0]), np.array([10.5, 12.0]), np.array([2.0, 2.0])) == 2, "closest first"
    assert boundary_scores([], [10.0], BARS)["f1"] == 0.0


def test_naive_boundaries_every_n_bars_and_the_best_offset():
    human = [8.0 + 16.0 * index for index in range(6)]  # every 8 bars from bar 4, to the end of BARS
    naive = naive_section_baselines(human, BARS, 0.0)
    assert naive["every_8_bars"] == 0.0, "from the start of the map the phase is four bars off"
    assert naive["best_naive"] == {"f1": 1.0, "every_bars": 8, "offset_bars": 3}, (
        "a boundary one bar early still matches, and offset 3 comes before 4"
    )
    assert naive_section_baselines(human, BARS, 8.0)["every_8_bars"] == 1.0, "starting where the song does"
    assert naive_section_baselines(human[:5], BARS, 8.0)["every_8_bars"] == pytest.approx(0.909, abs=0.001), (
        "one boundary too many past the last human one"
    )


def test_star_power_numbers():
    summary = star_power_summary([(2.0, 4.0), (22.0, 24.0), (40.5, 42.0)], BARS, 60.0, np.array([2.5, 3.0, 23.0, 50.0]))
    assert summary == {
        "phrases": 3,
        "per_minute": 3.0,
        "median_length_bars": 1.0,
        "on_a_bar_line": pytest.approx(2 / 3, abs=0.001),
        "median_gap_s": 19.2,
        "median_notes_inside": 1.0,
        "fewest_notes_inside": 0,
    }
    assert star_power_summary([], BARS, 60.0) == {"phrases": 0}


def test_the_preview_is_placed_in_the_human_sections():
    sections = [(5.0, "intro"), (25.0, "verse"), (95.0, "chorus")]
    assert section_at(4.0, sections) is None and section_at(25.0, sections) == "verse"
    assert preview_comparison(100.0, 90.0, sections) == {
        "mine_s": 100.0,
        "mine_section": "chorus",
        "human_s": 90.0,
        "human_section": "verse",
        "apart_s": 10.0,
    }
    assert preview_comparison(100.0, None, sections) == {"mine_s": 100.0, "mine_section": "chorus"}


def test_a_chorus_is_what_the_human_charts_call_one():
    assert all(is_chorus(name) for name in ("chorus_1", "Chorus 2", "chorus", "chorus_2a"))
    assert not any(
        is_chorus(name) for name in ("prechorus_2", "Pre-Chorus 1", "postchorus_1", "Post-Chorus 2", "verse_1", "gtr_solo")
    )


def test_a_human_chorus_in_a_preview_counts_from_one_bar_before_it():
    bars = np.arange(0.0, 200.0, 2.0)
    sections = [(10.0, "verse_1"), (50.0, "prechorus_1"), (60.0, "chorus_1"), (120.0, "chorus_2")]
    assert chorus_in_window(45.0, sections, bars) == 15.0
    assert chorus_in_window(30.0, sections, bars) == 30.0 and chorus_in_window(29.0, sections, bars) is None
    assert chorus_in_window(62.0, sections, bars) == -2.0, "a bar late, the preview still holds almost all of it"
    assert chorus_in_window(62.5, sections, bars) is None
    assert chorus_in_window(100.0, sections, bars) == 20.0
    result = preview_comparison(45.0, 58.0, sections, bars)
    assert (result["chorus_in_window_s"], result["human_chorus_in_window_s"], result["apart_s"]) == (15.0, 2.0, 13.0)
    # Without a chorus in the human chart, or without its bar lines, nothing is said about one.
    assert "chorus_in_window_s" not in preview_comparison(45.0, 58.0, [(10.0, "verse"), (40.0, "bridge")], bars)
    assert "chorus_in_window_s" not in preview_comparison(45.0, 58.0, sections)


# ---------------------------------------------------------------- in evaluate


@pytest.mark.heavy
def test_evaluate_reports_the_structure(tmp_path):
    structured_sng(tmp_path / "train")
    report = evaluate_folder(tmp_path, separator_for(), tmp_path / "cache")
    structure = report.songs["structured"]["structure"]
    assert [section["name"] for section in structure["sections"]["human"]] == ["verse_1", "chorus 1"]
    assert structure["sections"]["mine"] == [], "a click track that never changes gets no section"
    assert structure["sections"]["match"]["f1"] == 0.0
    assert {"every_4_bars", "every_8_bars", "every_16_bars", "best_naive"} <= set(structure["sections"]["naive"])
    assert set(structure["star_power"]["human"]) == {"guitar", "drums"}
    assert structure["star_power"]["human"]["guitar"]["phrases"] == 2
    # D.3: our star power, placed as a build places it, on the instruments the human chart has and we chart.
    mine = structure["star_power"]["mine"]
    assert set(mine) == {"guitar"}
    assert (mine["guitar"]["phrases"], mine["guitar"]["median_length_bars"], mine["guitar"]["on_a_bar_line"]) == (1, 1.0, 1.0)
    assert mine["guitar"]["fewest_notes_inside"] >= 1
    assert structure["preview"]["human_s"] == pytest.approx(12.5)
    assert {"chorus_in_window_s", "human_chorus_in_window_s", "lead_bars"} <= set(structure["preview"])
    text = format_report(report)
    assert "Structure of structured" in text and "best naive" in text and "star power, human: guitar 2" in text
    assert "star power, mine: guitar 1 (" in text


@pytest.mark.parametrize(
    "rule,leads_into,lead_bars,shown",
    [
        ("repeated part", "F1", 6, "(prechorus_2, 6 bars before F1)"),
        ("loudest window", None, None, "(prechorus_2, loudest window)"),
    ],
)
def test_the_preview_line_says_how_the_preview_was_chosen(rule, leads_into, lead_bars, shown):
    preview = {"mine_s": 174.6, "mine_section": "prechorus_2", "human_s": 174.4, "human_section": "prechorus_2",
               "apart_s": 0.2, "rule": rule, "leads_into": leads_into, "lead_bars": lead_bars}
    structure = {"sections": {"human": [], "mine": []}, "star_power": {"human": {}, "mine": {}}, "preview": preview}
    lines = _structure_lines("S", {"structure": structure})
    assert f"preview: mine 174.6 s {shown}, human 174.4 s (prechorus_2): 0.2 s apart" in lines
    # Decision 48: whether a human chorus starts in each preview.
    preview.update({"chorus_in_window_s": 14.7, "human_chorus_in_window_s": None})
    lines = _structure_lines("S", {"structure": structure})
    assert any(
        line.endswith("0.2 s apart; a human chorus 14.7 s into mine, no human chorus in the human's") for line in lines
    )


def test_the_structure_lines_hold_up_without_a_human_structure():
    lines = _structure_lines(
        "S",
        {
            "structure": {
                "sections": {"human": [], "mine": [{"time_s": 0.0, "name": "Intro"}]},
                "star_power": {"human": {"keys": {"phrases": 1, "per_minute": 0.2, "median_length_bars": 1.0,
                                                  "on_a_bar_line": 1.0, "median_gap_s": None}}, "mine": {}},
                "preview": {"mine_s": 10.0, "mine_section": None},
            }
        },
    )
    assert "sections: the human chart has none; mine 1 (Intro)" in lines
    assert any("keys 1 (0.2/min, 1.0 bar, 100% on a bar line, gap -)" in line for line in lines)
    assert any(line.startswith("preview: mine 10.0 s (-); the human chart sets none") for line in lines)


# ---------------------------------------------------------------- the real reference


@pytest.mark.real
@pytest.mark.parametrize("real_song", [CALIFORNICATION], indirect=True)
def test_californication_structure_is_read_and_measured(real_song):
    song = real_song.reference
    assert len(song.sections) == 15
    assert (song.sections[0].name, song.sections[-1].name) == ("intro", "chorus_3")
    assert song.sections[0].time_s == pytest.approx(5.11, abs=0.01)
    assert {instrument.value: len(phrases) for instrument, phrases in song.star_power.items()} == {
        "guitar": 13,
        "bass": 12,
        "keys": 1,
        "drums": 11,
    }
    assert song.preview_start_s == pytest.approx(174.428)
    structure = compare_structure(song, real_song.tempo, analysis_signals(song, real_song.stems))
    naive = structure["sections"]["naive"]
    assert naive["best_naive"]["f1"] == pytest.approx(0.385, abs=0.001), "what D.1 has to beat, with room to spare"
    assert naive["every_4_bars"] == pytest.approx(0.25, abs=0.001)
    assert all(value["on_a_bar_line"] == 1.0 for value in structure["star_power"]["human"].values())
    # Decision 48: six bars (the bar line closest to 14 s) before F1, chorus_1 in the human chart, as built.
    # D.2 led into F2 at 174.61 s, 0.2 s from the human's; the loudest window was 285.1 s.
    preview = structure["preview"]
    assert (preview["rule"], preview["leads_into"], preview["lead_bars"]) == ("repeated part", "F1", 6)
    assert preview["mine_s"] == pytest.approx(80.44, abs=0.05)
    assert (preview["mine_section"], preview["human_section"]) == ("prechorus_1", "prechorus_2")
    # The owner's acceptance criterion (2026-11-16, it replaced "at most one bar from the human's preview",
    # which held only for the rule tuned on this song): a human chorus starts in our 30 s, as one does in
    # the human's. Here chorus_1, 14.7 s in; in the human's, chorus_2, 10.0 s in.
    assert preview["chorus_in_window_s"] == pytest.approx(14.72, abs=0.05)
    assert preview["human_chorus_in_window_s"] == pytest.approx(9.97, abs=0.05)
