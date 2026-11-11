"""Phase C, drums. C.0: the 4-lane Pro layout, the writer, the validator and the reference reader.

No audio is analysed here: every chart is written by hand or by the writer.
"""

import struct
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from conftest import CALIFORNICATION
from test_evaluation import BPM, DIVISION, make_chart_folder, midi_track, sng_bytes, wav_bytes

from chartgen.clonehero.chart_format import DotChartExporter
from chartgen.clonehero.song_ini import SongIni, render_song_ini
from chartgen.clonehero.validate import validate_chart_text, validate_song_folder
from chartgen.core import (
    GEM_FOR_PIECE,
    OPEN_LANE,
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
from chartgen.evaluation.formats import parse_midi
from chartgen.evaluation.reference import load_reference

LEVELS = ("Expert", "Hard", "Medium", "Easy")
GOOD_HEADER = "[Song]\n{\n  Resolution = 192\n}\n[SyncTrack]\n{\n  0 = TS 4\n  0 = B 120000\n}\n"


def chart_of(*tracks: Track) -> Chart:
    tempo_map = TempoMap([TempoEvent(0, 120.0)], [TimeSignatureEvent(0, 4, 4)])
    return Chart(SongMetadata("Song", "Artist"), tempo_map, list(tracks))


def render(*tracks: Track) -> str:
    return DotChartExporter().render(chart_of(*tracks)).decode("utf-8-sig")


def body_lines(text: str, section: str) -> list[str]:
    body = text.split(f"[{section}]")[1].split("}")[0]
    return [line.strip() for line in body.splitlines() if "=" in line]


def drums(level: Difficulty, *hits: tuple[int, DrumGem]) -> Track:
    return Track(Instrument.DRUMS, level, [gem.note(tick) for tick, gem in hits])


def drum_chart(**sections: str) -> str:
    """A chart with the given drum sections, each body written as .chart lines."""
    blocks = "".join(f"[{name}]\n{{\n{body}\n}}\n" for name, body in sections.items())
    return GOOD_HEADER + blocks


# ---------------------------------------------------------------- the layout


def test_every_gem_is_a_lane_and_a_cymbal_flag():
    assert [(gem.lane, gem.cymbal) for gem in DrumGem] == [
        (0, False),
        (1, False),
        (2, False),
        (3, False),
        (4, False),
        (2, True),
        (3, True),
        (4, True),
    ]
    for gem in DrumGem:
        assert DrumGem.of(gem.lane, gem.cymbal) is gem
        assert DrumGem.of_note(gem.note(96)) is gem
    assert [gem.is_pad for gem in DrumGem].count(False) == 1


@pytest.mark.parametrize("lane", [0, 1])
def test_neither_the_kick_nor_red_can_be_a_cymbal(lane):
    with pytest.raises(ValueError, match="cannot be a cymbal"):
        DrumGem.of(lane, cymbal=True)
    with pytest.raises(ValueError, match="cymbal"):
        ChartNote(0, lane, cymbal=True)


def test_there_is_no_fifth_lane():
    with pytest.raises(ValueError, match="0..4"):
        DrumGem.of(5)
    with pytest.raises(ValueError, match="cymbal"):
        ChartNote(0, OPEN_LANE, cymbal=True)


@pytest.mark.parametrize(
    "note", [ChartNote(0, 2, length=96), ChartNote(0, 2, forced=True), ChartNote(0, 2, tap=True)]
)
def test_a_drum_note_has_no_sustain_force_or_tap(note):
    with pytest.raises(ValueError, match="no sustain, force or tap"):
        DrumGem.of_note(note)


def test_the_kit_maps_to_the_approved_gems():
    assert dict(GEM_FOR_PIECE) == {
        DrumPiece.KICK: DrumGem.KICK,
        DrumPiece.SNARE: DrumGem.RED,
        DrumPiece.HI_HAT: DrumGem.YELLOW_CYMBAL,
        DrumPiece.RIDE: DrumGem.BLUE_CYMBAL,
        DrumPiece.CRASH: DrumGem.GREEN_CYMBAL,
        DrumPiece.HIGH_TOM: DrumGem.YELLOW_TOM,
        DrumPiece.MID_TOM: DrumGem.BLUE_TOM,
        DrumPiece.FLOOR_TOM: DrumGem.GREEN_TOM,
    }


# ---------------------------------------------------------------- the writer


@pytest.mark.parametrize(
    "piece,lines",
    [
        (DrumPiece.KICK, ["0 = N 0 0"]),
        (DrumPiece.SNARE, ["0 = N 1 0"]),
        (DrumPiece.HI_HAT, ["0 = N 2 0", "0 = N 66 0"]),
        (DrumPiece.RIDE, ["0 = N 3 0", "0 = N 67 0"]),
        (DrumPiece.CRASH, ["0 = N 4 0", "0 = N 68 0"]),
        (DrumPiece.HIGH_TOM, ["0 = N 2 0"]),
        (DrumPiece.MID_TOM, ["0 = N 3 0"]),
        (DrumPiece.FLOOR_TOM, ["0 = N 4 0"]),
    ],
)
def test_each_piece_of_the_kit_is_written_exactly(piece, lines):
    text = render(drums(Difficulty.EXPERT, (0, GEM_FOR_PIECE[piece])))
    assert body_lines(text, "ExpertDrums") == lines


def test_a_position_writes_its_notes_then_its_flags():
    text = render(
        drums(
            Difficulty.EXPERT,
            (0, DrumGem.KICK),
            (0, DrumGem.RED),
            (0, DrumGem.YELLOW_CYMBAL),
            (96, DrumGem.BLUE_CYMBAL),
            (96, DrumGem.GREEN_TOM),
        )
    )
    assert body_lines(text, "ExpertDrums") == [
        "0 = N 0 0",
        "0 = N 1 0",
        "0 = N 2 0",
        "0 = N 66 0",
        "96 = N 3 0",
        "96 = N 4 0",
        "96 = N 67 0",
    ]
    _, report = validate_chart_text(text)
    assert report.ok, report.errors


def test_one_lane_cannot_be_tom_and_cymbal_at_once():
    with pytest.raises(ValueError, match="duplicate"):
        drums(Difficulty.EXPERT, (0, DrumGem.YELLOW_TOM), (0, DrumGem.YELLOW_CYMBAL))


@pytest.mark.parametrize(
    "note,message",
    [
        (ChartNote(0, 4, forced=True), "5-lane"),
        (ChartNote(0, 1, tap=True), "tap"),
        (ChartNote(0, 0, length=96), "sustain"),
        (ChartNote(0, OPEN_LANE), "open"),
    ],
)
def test_the_writer_refuses_what_drums_cannot_have(note, message):
    with pytest.raises(ValueError, match=message):
        render(Track(Instrument.DRUMS, Difficulty.EXPERT, [note]))


@pytest.mark.parametrize("instrument", [Instrument.GUITAR, Instrument.BASS, Instrument.KEYS])
def test_only_drums_have_cymbals(instrument):
    with pytest.raises(ValueError, match="only drums"):
        render(Track(instrument, Difficulty.EXPERT, [ChartNote(0, 2, cymbal=True)]))


def test_a_guitar_chart_is_written_as_before():
    """The cymbal field must leave every other instrument's lines alone."""
    track = Track(
        Instrument.GUITAR,
        Difficulty.EXPERT,
        [ChartNote(0, 4, length=48, forced=True), ChartNote(96, OPEN_LANE, tap=True)],
    )
    assert body_lines(render(track), "ExpertSingle") == [
        "0 = N 4 48",
        "0 = N 5 0",
        "96 = N 7 0",
        "96 = N 6 0",
    ]


# ---------------------------------------------------------------- song.ini


def ini_lines(difficulties: dict[Instrument, int]) -> list[str]:
    text = render_song_ini(SongIni(SongMetadata("N", "A"), 1000, difficulties=difficulties))
    return text.splitlines()


def test_a_drum_chart_is_declared_pro_and_never_five_lane():
    lines = ini_lines({Instrument.DRUMS: 3})
    assert "diff_drums = 3" in lines
    assert "pro_drums = True" in lines
    assert not any(line.startswith("five_lane_drums") for line in lines)


def test_no_drum_chart_no_pro_drums_tag():
    lines = ini_lines({Instrument.GUITAR: 2, Instrument.BASS: 1})
    assert not any(line.startswith(("pro_drums", "five_lane_drums")) for line in lines)
    assert lines[-1] == "diff_keys = -1", "the file of a song without drums is as it was"


# ---------------------------------------------------------------- the validator: values


def test_the_validator_accepts_every_drum_value_the_writer_uses():
    text = render(
        drums(Difficulty.EXPERT, *[(index * 192, gem) for index, gem in enumerate(DrumGem)])
    )
    _, report = validate_chart_text(text)
    assert report.ok, report.errors


@pytest.mark.parametrize(
    "body,message",
    [
        ("  0 = N 5 0", "5-lane"),
        ("  0 = N 32 0", "out of range"),
        ("  0 = N 34 0", "out of range"),
        ("  0 = N 40 0", "out of range"),
        ("  0 = N 65 0", "out of range"),
        ("  0 = N 66 0", "yellow cymbal flag without a yellow note"),
        ("  0 = N 3 0\n  0 = N 68 0", "green cymbal flag without a green note"),
        ("  0 = N 2 96", "sustain"),
        ("  0 = N 1 0\n  0 = N 2 0\n  0 = N 3 0", "3 pads at once"),
        ("  0 = N 1 0\n  0 = N 2 0\n  0 = N 66 0\n  0 = N 4 0\n  0 = N 68 0", "3 pads at once"),
    ],
)
def test_the_validator_rejects_what_these_drums_never_have(body, message):
    _, report = validate_chart_text(drum_chart(ExpertDrums=body))
    assert any(message in error for error in report.errors), report.errors


def test_two_pads_and_a_kick_are_fine_on_expert():
    _, report = validate_chart_text(
        drum_chart(ExpertDrums="  0 = N 0 0\n  0 = N 1 0\n  0 = N 2 0\n  0 = N 66 0")
    )
    assert report.ok, report.errors


# ---------------------------------------------------------------- the validator: levels


EXPERT = "\n".join(
    [
        "  0 = N 0 0",
        "  0 = N 2 0",
        "  0 = N 66 0",
        "  48 = N 2 0",
        "  48 = N 66 0",
        "  96 = N 1 0",
        "  96 = N 2 0",
        "  96 = N 66 0",
        "  192 = N 0 0",
        "  192 = N 1 0",
        "  192 = N 3 0",
    ]
)


def test_a_chain_of_levels_passes():
    _, report = validate_chart_text(
        drum_chart(
            ExpertDrums=EXPERT,
            HardDrums="  0 = N 0 0\n  0 = N 2 0\n  0 = N 66 0\n  48 = N 2 0\n  48 = N 66 0\n  96 = N 1 0\n  192 = N 1 0",
            MediumDrums="  0 = N 0 0\n  0 = N 2 0\n  0 = N 66 0\n  96 = N 1 0\n  192 = N 1 0",
            EasyDrums="  0 = N 0 0\n  96 = N 1 0\n  192 = N 1 0",
        )
    )
    assert report.ok, report.errors


def test_the_chain_runs_through_every_written_level():
    """Medium is checked against Hard, not only against Expert."""
    _, report = validate_chart_text(
        drum_chart(
            ExpertDrums=EXPERT,
            HardDrums="  0 = N 0 0\n  96 = N 1 0",
            MediumDrums="  0 = N 0 0\n  96 = N 1 0\n  192 = N 1 0",
        )
    )
    assert any("[MediumDrums] has tick 192, but [HardDrums] does not" in e for e in report.errors)


@pytest.mark.parametrize(
    "sections,message",
    [
        (
            {"ExpertDrums": EXPERT, "EasyDrums": "  0 = N 2 0"},
            "[EasyDrums] tick 0: yellow tom is not in [ExpertDrums]",
        ),
        (
            {"ExpertDrums": EXPERT, "HardDrums": "  192 = N 3 0\n  192 = N 67 0"},
            "[HardDrums] tick 192: blue cymbal is not in [ExpertDrums]",
        ),
        (
            {"ExpertDrums": EXPERT, "MediumDrums": "  24 = N 1 0"},
            "[MediumDrums] has tick 24, but [ExpertDrums] does not",
        ),
        (
            {"ExpertDrums": EXPERT, "HardDrums": "  0 = N 0 0\n  0 = N 1 0\n  0 = N 2 0"},
            "[HardDrums] tick 0: 3 gems at once",
        ),
        (
            {"ExpertDrums": EXPERT, "MediumDrums": "  192 = N 0 0\n  192 = N 1 0\n  192 = N 3 0"},
            "[MediumDrums] tick 192: 3 gems at once",
        ),
        (
            {"ExpertDrums": EXPERT, "EasyDrums": "  0 = N 0 0\n  0 = N 2 0\n  0 = N 66 0"},
            "[EasyDrums] tick 0: the kick with a pad",
        ),
        (
            {"ExpertDrums": EXPERT, "MediumDrums": "  48 = N 2 0\n  48 = N 66 0"},
            "[MediumDrums] tick 48: a sixteenth",
        ),
        (
            {"ExpertDrums": EXPERT, "EasyDrums": "  48 = N 2 0\n  48 = N 66 0"},
            "[EasyDrums] tick 48: a sixteenth",
        ),
    ],
)
def test_the_validator_catches_a_broken_level_from_the_file_alone(sections, message):
    _, report = validate_chart_text(drum_chart(**sections))
    assert any(message in error for error in report.errors), report.errors


def test_a_sixteenth_is_fine_on_hard_and_an_eighth_on_easy():
    _, report = validate_chart_text(
        drum_chart(
            ExpertDrums=EXPERT,
            HardDrums="  48 = N 2 0\n  48 = N 66 0\n  96 = N 1 0\n  192 = N 1 0\n  192 = N 3 0",
            EasyDrums="  96 = N 1 0\n  192 = N 1 0\n  192 = N 3 0",
        )
    )
    assert report.ok, report.errors


def test_two_pads_without_the_kick_are_fine_on_easy():
    _, report = validate_chart_text(
        drum_chart(ExpertDrums=EXPERT, EasyDrums="  96 = N 1 0\n  96 = N 2 0\n  96 = N 66 0")
    )
    assert report.ok, report.errors


def test_the_written_levels_are_checked_by_the_same_rules():
    """What the writer produces from tracks that break a rule, the validator catches."""
    text = render(
        drums(Difficulty.EXPERT, (0, DrumGem.KICK), (0, DrumGem.YELLOW_CYMBAL)),
        drums(Difficulty.EASY, (0, DrumGem.KICK), (0, DrumGem.YELLOW_TOM)),
    )
    _, report = validate_chart_text(text)
    assert any("the kick with a pad" in error for error in report.errors)
    assert any("yellow tom is not in [ExpertDrums]" in error for error in report.errors)


# ---------------------------------------------------------------- the validator: the folder


def drum_folder(folder: Path, ini_extra: str = "", pro: bool = True) -> Path:
    DotChartExporter().export(chart_of(drums(Difficulty.EXPERT, (0, DrumGem.KICK))), folder)
    ini = render_song_ini(SongIni(SongMetadata("N", "A"), 1000, difficulties={Instrument.DRUMS: 1}))
    if not pro:
        ini = ini.replace("pro_drums = True\n", "")
    (folder / "song.ini").write_text(ini + ini_extra, encoding="utf-8")
    sf.write(str(folder / "song.ogg"), np.zeros((4410, 2), dtype=np.float32), 44100, format="OGG")
    return folder


def test_a_drum_folder_validates(tmp_path):
    report = validate_song_folder(drum_folder(tmp_path))
    assert report.ok, report.errors


def test_a_drum_folder_without_pro_drums_fails(tmp_path):
    report = validate_song_folder(drum_folder(tmp_path, pro=False))
    assert any("pro_drums" in error for error in report.errors), report.errors


@pytest.mark.parametrize("value", ["True", "1", "true"])
def test_five_lane_drums_is_never_set(tmp_path, value):
    report = validate_song_folder(drum_folder(tmp_path, f"five_lane_drums = {value}\n"))
    assert any("five_lane_drums" in error for error in report.errors), report.errors


# ---------------------------------------------------------------- the reference reader: .mid


def drum_midi_bytes(
    hits: list[tuple[int, int]],
    toms: list[tuple[int, int, int]] = (),
    texts: list[tuple[int, str]] = (),
) -> bytes:
    """A MIDI file with a one-note guitar part and a drum part.

    ``hits`` are (tick, note), ``toms`` are (marker, start, length), ``texts`` are text events.
    """
    tempo = midi_track([(0, b"\xff\x51\x03" + int(60e6 / BPM).to_bytes(3, "big"))])
    guitar = midi_track(
        [(0, b"\xff\x03\x0bPART GUITAR"), (DIVISION, b"\x90\x60\x64"), (DIVISION + 60, b"\x80\x60\x00")]
    )
    events: list[tuple[int, bytes]] = [(0, b"\xff\x03\x0aPART DRUMS")]
    for tick, note in hits:
        events.append((tick, bytes([0x99, note, 100])))
        events.append((tick + 30, bytes([0x89, note, 0])))
    for marker, start, length in toms:
        events.append((start, bytes([0x99, marker, 100])))
        events.append((start + length, bytes([0x89, marker, 0])))
    for tick, text in texts:
        data = text.encode("latin-1")
        events.append((tick, b"\xff\x01" + bytes([len(data)]) + data))
    header = b"MThd" + struct.pack(">IHHH", 6, 1, 3, DIVISION)
    return header + tempo + guitar + midi_track(events)


def drum_sng(tmp_path: Path, midi: bytes, **metadata: str) -> Path:
    path = tmp_path / "drums.sng"
    tags = {"name": "T", "artist": "A", **metadata}
    path.write_bytes(sng_bytes({"notes.mid": midi, "song.wav": wav_bytes(tmp_path)}, tags))
    return path


B = DIVISION
PRO_HITS = [
    (B, 96),  # kick
    (B, 98),  # yellow: a cymbal by default
    (2 * B, 97),  # red
    (2 * B, 99),  # blue, inside its tom marker
    (3 * B, 100),  # green: a cymbal
    (3 * B, 95),  # Expert+ kick: not part of Expert
    (B, 84),  # Hard kick
    (2 * B, 87),  # Hard blue, inside the marker
]


def gems_at(levels, level: Difficulty) -> dict[int, tuple[DrumGem, ...]]:
    return {hit.tick: hit.gems for hit in levels[level]}


def test_midi_drums_are_cymbals_unless_a_tom_marker_says_otherwise(tmp_path):
    midi = drum_midi_bytes(PRO_HITS, toms=[(111, 2 * B, B // 2)])
    song = load_reference(drum_sng(tmp_path, midi, pro_drums="True"))
    assert song.drums.pro
    assert song.drums.skipped == ""
    assert song.drums.double_kicks == 1
    assert gems_at(song.drums.levels, Difficulty.EXPERT) == {
        B: (DrumGem.KICK, DrumGem.YELLOW_CYMBAL),
        2 * B: (DrumGem.RED, DrumGem.BLUE_TOM),
        3 * B: (DrumGem.GREEN_CYMBAL,),
    }
    assert gems_at(song.drums.levels, Difficulty.HARD) == {
        B: (DrumGem.KICK,),
        2 * B: (DrumGem.BLUE_TOM,),
    }
    assert set(song.drums.levels) == {Difficulty.EXPERT, Difficulty.HARD}
    first = song.drums.levels[Difficulty.EXPERT][0]
    assert first.time_s == pytest.approx(60 / BPM)


def test_tom_markers_alone_make_a_midi_chart_pro(tmp_path):
    midi = drum_midi_bytes(PRO_HITS, toms=[(111, 2 * B, B // 2)])
    song = load_reference(drum_sng(tmp_path, midi))
    assert song.drums.pro
    assert gems_at(song.drums.levels, Difficulty.EXPERT)[B] == (DrumGem.KICK, DrumGem.YELLOW_CYMBAL)


def test_a_midi_chart_that_is_not_pro_has_no_cymbals(tmp_path):
    song = load_reference(drum_sng(tmp_path, drum_midi_bytes(PRO_HITS)))
    assert not song.drums.pro
    assert gems_at(song.drums.levels, Difficulty.EXPERT)[B] == (DrumGem.KICK, DrumGem.YELLOW_TOM)


@pytest.mark.parametrize(
    "hits,texts,tags,message",
    [
        ([(B, 101)], [], {}, "5-lane"),
        ([(B, 96)], [], {"five_lane_drums": "True"}, "5-lane"),
        ([(B, 96)], [(0, "[mix 3 drums0d]")], {"pro_drums": "True"}, "disco flip"),
    ],
)
def test_midi_drums_that_would_be_misread_are_left_out(tmp_path, hits, texts, tags, message):
    song = load_reference(drum_sng(tmp_path, drum_midi_bytes(hits, texts=texts), **tags))
    assert song.drums.levels == {}
    assert message in song.drums.skipped
    assert len(song.notes) == 1, "the guitar is still read"


def test_a_mix_event_without_a_flip_is_read(tmp_path):
    midi = drum_midi_bytes(PRO_HITS, texts=[(0, "[mix 3 drums0]"), (0, "[mix 2 drums0dnoflip]")])
    song = load_reference(drum_sng(tmp_path, midi, pro_drums="True"))
    assert song.drums.skipped == ""
    assert Difficulty.EXPERT in song.drums.levels


def test_text_events_are_kept_by_the_midi_reader():
    midi = parse_midi(drum_midi_bytes([(B, 96)], texts=[(0, "[mix 3 drums0]"), (B, "[idle]")]))
    assert midi.tracks["PART DRUMS"].texts == [(0, "[mix 3 drums0]"), (B, "[idle]")]


def test_a_reference_without_drums_says_so(tmp_path):
    from test_evaluation import make_sng

    song = load_reference(make_sng(tmp_path))
    assert song.drums.levels == {}
    assert "PART DRUMS" in song.drums.skipped


# ---------------------------------------------------------------- the reference reader: .chart


def drum_chart_folder(tmp_path: Path, sections: dict[str, str], ini: str = "") -> Path:
    folder = make_chart_folder(tmp_path / "song")
    path = folder / "notes.chart"
    blocks = "".join(f"[{name}]\n{{\n{body}\n}}\n" for name, body in sections.items())
    path.write_text(path.read_text(encoding="utf-8") + blocks, encoding="utf-8")
    if ini:
        (folder / "song.ini").write_text(f"[song]\n{ini}\n", encoding="utf-8")
    return folder


def test_chart_drums_are_toms_unless_a_cymbal_flag_says_otherwise(tmp_path):
    folder = drum_chart_folder(
        tmp_path,
        {
            "ExpertDrums": "  192 = N 0 0\n  192 = N 2 0\n  192 = N 66 0\n  192 = N 32 0\n"
            "  384 = N 1 0\n  384 = N 3 0\n  576 = N 4 0\n  576 = N 68 0",
            "EasyDrums": "  384 = N 3 0",
        },
    )
    song = load_reference(folder)
    assert song.drums.pro
    assert song.drums.double_kicks == 1
    assert gems_at(song.drums.levels, Difficulty.EXPERT) == {
        192: (DrumGem.KICK, DrumGem.YELLOW_CYMBAL),
        384: (DrumGem.RED, DrumGem.BLUE_TOM),
        576: (DrumGem.GREEN_CYMBAL,),
    }
    assert gems_at(song.drums.levels, Difficulty.EASY) == {384: (DrumGem.BLUE_TOM,)}
    assert song.drums.levels[Difficulty.EXPERT][0].time_s == pytest.approx(0.5)


def test_a_chart_without_cymbal_flags_is_plain_four_lane(tmp_path):
    song = load_reference(drum_chart_folder(tmp_path, {"ExpertDrums": "  192 = N 2 0\n  192 = N 4 0"}))
    assert not song.drums.pro
    assert gems_at(song.drums.levels, Difficulty.EXPERT)[192] == (DrumGem.YELLOW_TOM, DrumGem.GREEN_TOM)


def test_pro_drums_in_song_ini_makes_a_flagless_chart_pro_with_toms(tmp_path):
    folder = drum_chart_folder(tmp_path, {"ExpertDrums": "  192 = N 2 0"}, "pro_drums = True")
    song = load_reference(folder)
    assert song.drums.pro
    assert gems_at(song.drums.levels, Difficulty.EXPERT)[192] == (DrumGem.YELLOW_TOM,)


@pytest.mark.parametrize(
    "body,ini",
    [
        ("  192 = N 5 0", ""),
        ("  192 = N 2 96", ""),
        ("  192 = N 2 0\n  192 = N 66 0", "five_lane_drums = True"),
    ],
    ids=["fifth lane", "sustain", "song.ini"],
)
def test_chart_drums_that_are_five_lane_are_left_out(tmp_path, body, ini):
    song = load_reference(drum_chart_folder(tmp_path, {"ExpertDrums": body}, ini))
    assert song.drums.levels == {}
    assert "5-lane" in song.drums.skipped


def test_our_own_chart_reads_back_as_written(tmp_path):
    """The writer and the reader agree on every gem, and the reader shares no code with the writer."""
    written = [(index * 96, gem) for index, gem in enumerate(DrumGem)]
    text = render(drums(Difficulty.EXPERT, *written))
    folder = make_chart_folder(tmp_path / "song")
    drum_part = ("[ExpertDrums]" + text.split("[ExpertDrums]")[1]).replace("\r\n", "\n")
    path = folder / "notes.chart"
    path.write_text(path.read_text(encoding="utf-8") + drum_part, encoding="utf-8")
    song = load_reference(folder)
    assert [(hit.tick, hit.gems) for hit in song.drums.levels[Difficulty.EXPERT]] == [
        (tick, (gem,)) for tick, gem in written
    ]


# ---------------------------------------------------------------- the real reference


@pytest.mark.real
@pytest.mark.parametrize("real_song", [CALIFORNICATION], indirect=True)
def test_the_human_drum_chart_is_read_as_the_prototype_counted(real_song):
    """Californication's drums, counted again by this reader. The prototype was a separate script."""
    song = real_song.reference
    drums_of = song.drums
    assert drums_of.pro and drums_of.skipped == ""
    assert drums_of.double_kicks == 0
    levels = drums_of.levels
    expert = levels[Difficulty.EXPERT]
    gems = [gem for hit in expert for gem in hit.gems]
    assert len(gems) == 1942
    assert sum(not gem.cymbal and gem.lane >= 2 for gem in gems) == 16, "only 16 toms"
    assert [len(levels[level]) for level in Difficulty] == [1426, 1081, 910, 766]

    # The human keeps our hard rules, except that 1% of Hard's gems differ from Expert's.
    sixteenth = song.resolution // 4
    for level in Difficulty:
        hits = levels[level]
        assert all(sum(gem.is_pad for gem in hit.gems) <= 2 for hit in hits), "two hands"
        if level in (Difficulty.HARD, Difficulty.MEDIUM):
            assert all(len(hit.gems) <= 2 for hit in hits)
        if level in (Difficulty.MEDIUM, Difficulty.EASY):
            assert not any(round(hit.tick / sixteenth) % 2 for hit in hits), "no sixteenths"
    assert not any(DrumGem.KICK in hit.gems and len(hit.gems) > 1 for hit in levels[Difficulty.EASY])
    order = list(Difficulty)
    for upper, lower in zip(order, order[1:]):
        above = {hit.tick: set(hit.gems) for hit in levels[upper]}
        assert all(hit.tick in above for hit in levels[lower]), "every position is in the level above"
