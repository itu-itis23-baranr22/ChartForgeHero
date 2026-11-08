from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from chartgen.clonehero.chart_format import DotChartExporter, section_name
from chartgen.clonehero.song_ini import SongIni, difficulty_tier, render_song_ini
from chartgen.clonehero.validate import parse_chart, validate_chart_text, validate_song_folder, ValidationReport
from chartgen.core import (
    OPEN_LANE,
    Chart,
    ChartNote,
    Difficulty,
    Instrument,
    Section,
    SongMetadata,
    StarPowerPhrase,
    TempoEvent,
    TempoMap,
    TimeSignatureEvent,
    Track,
)

GOOD_HEADER = """[Song]
{
  Resolution = 192
}
[SyncTrack]
{
  0 = TS 4
  0 = B 120000
}
"""


def make_chart(*tracks: Track) -> Chart:
    tempo_map = TempoMap(
        [TempoEvent(0, 120.0), TempoEvent(768, 97.5)],
        [TimeSignatureEvent(0, 4, 4), TimeSignatureEvent(768, 6, 8)],
    )
    return Chart(SongMetadata("Şarkı", "Sanatçı"), tempo_map, list(tracks))


def render(chart: Chart) -> str:
    return DotChartExporter().render(chart).decode("utf-8-sig")


@pytest.mark.parametrize(
    "instrument,difficulty,expected",
    [
        (Instrument.GUITAR, Difficulty.EXPERT, "ExpertSingle"),
        (Instrument.GUITAR, Difficulty.EASY, "EasySingle"),
        (Instrument.BASS, Difficulty.HARD, "HardDoubleBass"),
        (Instrument.DRUMS, Difficulty.MEDIUM, "MediumDrums"),
        (Instrument.KEYS, Difficulty.EXPERT, "ExpertKeyboard"),
    ],
)
def test_section_names_match_the_format(instrument, difficulty, expected):
    assert section_name(instrument, difficulty) == expected


def test_rendered_chart_passes_the_independent_validator():
    track = Track(
        Instrument.GUITAR,
        Difficulty.EXPERT,
        [ChartNote(0, 0), ChartNote(192, 1, length=96), ChartNote(192, 3), ChartNote(384, 2)],
    )
    _, report = validate_chart_text(render(make_chart(track)))
    assert report.ok, report.errors


def test_file_has_bom_crlf_and_turkish_text():
    data = DotChartExporter().render(
        make_chart(Track(Instrument.GUITAR, Difficulty.EXPERT, [ChartNote(0, 0)]))
    )
    assert data.startswith(b"\xef\xbb\xbf[Song]\r\n")
    assert '  Name = "Şarkı"'.encode() in data
    assert b"\n" not in data.replace(b"\r\n", b"")


def test_sync_track_values_and_order():
    text = render(make_chart(Track(Instrument.GUITAR, Difficulty.EXPERT, [ChartNote(0, 0)])))
    sync = text.split("[SyncTrack]")[1].split("}")[0]
    lines = [line.strip() for line in sync.splitlines() if "=" in line]
    assert lines == ["0 = TS 4", "0 = B 120000", "768 = TS 6 3", "768 = B 97500"]


def test_track_lines_cover_notes_modifiers_open_and_star_power():
    track = Track(
        Instrument.GUITAR,
        Difficulty.EXPERT,
        [ChartNote(0, 4, length=48, forced=True), ChartNote(96, OPEN_LANE, tap=True)],
        [StarPowerPhrase(0, 192)],
    )
    text = render(make_chart(track))
    body = text.split("[ExpertSingle]")[1].split("}")[0]
    lines = [line.strip() for line in body.splitlines() if "=" in line]
    assert lines == ["0 = N 4 48", "0 = N 5 0", "0 = S 2 192", "96 = N 7 0", "96 = N 6 0"]


def test_forced_chord_writes_the_modifier_once():
    track = Track(
        Instrument.GUITAR,
        Difficulty.EXPERT,
        [ChartNote(0, 1, forced=True), ChartNote(0, 2, forced=True)],
    )
    assert render(make_chart(track)).count("0 = N 5 0") == 1


def test_section_markers_are_written_as_events():
    chart = make_chart(Track(Instrument.GUITAR, Difficulty.EXPERT, [ChartNote(0, 0)]))
    chart.sections.append(Section(192, "Chorus 1"))
    assert '192 = E "section Chorus 1"' in render(chart)


def test_quotes_cannot_break_a_value():
    tempo_map = TempoMap([TempoEvent(0, 120.0)])
    chart = Chart(
        SongMetadata('A "B" C', "D\nE"),
        tempo_map,
        [Track(Instrument.GUITAR, Difficulty.EXPERT, [ChartNote(0, 0)])],
    )
    text = render(chart)
    assert "Name = \"A 'B' C\"" in text
    assert 'Artist = "D E"' in text


def test_tracks_without_notes_are_not_written():
    text = render(
        make_chart(
            Track(Instrument.BASS, Difficulty.EXPERT),
            Track(Instrument.GUITAR, Difficulty.EXPERT, [ChartNote(0, 0)]),
        )
    )
    assert "ExpertDoubleBass" not in text


def test_drums_cannot_have_open_notes():
    track = Track(Instrument.DRUMS, Difficulty.EXPERT, [ChartNote(0, OPEN_LANE)])
    with pytest.raises(ValueError, match="open"):
        render(make_chart(track))


@pytest.mark.parametrize(
    "body,expected",
    [
        ("[ExpertSingle]\n{\n  192 = N 0 0\n  0 = N 1 0\n}\n", "tick 0 after 192"),
        ("[ExpertSingle]\n{\n  0 = N 8 0\n}\n", "out of range"),
        ("[ExpertSingle]\n{\n  0 = N 0\n}\n", "malformed"),
        ("[ExpertSingle]\n{\n  0 = N 0 -5\n}\n", "malformed"),
        ("[ExpertSingle]\n{\n  garbage\n}\n", "malformed"),
        ("[ExpertGuitar]\n{\n  0 = N 0 0\n}\n", "unknown section"),
        ("[ExpertSingle]\n{\n  0 = N 0 0\n}\n[ExpertSingle]\n{\n}\n", "duplicate section"),
        ("[ExpertSingle]\n{\n  0 = N 0 0\n", "ends inside"),
        ("", "no playable section"),
    ],
)
def test_validator_catches_bad_tracks(body, expected):
    _, report = validate_chart_text(GOOD_HEADER + body)
    assert not report.ok
    assert any(expected in error for error in report.errors), report.errors


@pytest.mark.parametrize(
    "header,expected",
    [
        ("[SyncTrack]\n{\n  0 = TS 4\n  0 = B 120000\n}\n", "Resolution"),
        ("[Song]\n{\n  Resolution = 192\n}\n", "missing [SyncTrack]"),
        ("[Song]\n{\n  Resolution = 192\n}\n[SyncTrack]\n{\n  0 = TS 4\n}\n", "no tempo"),
        ("[Song]\n{\n  Resolution = 192\n}\n[SyncTrack]\n{\n  0 = B 120000\n}\n", "no time signature"),
        ("[Song]\n{\n  Resolution = 192\n}\n[SyncTrack]\n{\n  0 = TS 4\n  0 = B 0\n}\n", "bad tempo"),
    ],
)
def test_validator_requires_song_and_sync_data(header, expected):
    _, report = validate_chart_text(header + "[ExpertSingle]\n{\n  0 = N 0 0\n}\n")
    assert any(expected in error for error in report.errors), report.errors


def test_validator_accepts_drum_only_values_on_drums():
    _, report = validate_chart_text(GOOD_HEADER + "[ExpertDrums]\n{\n  0 = N 32 0\n  0 = N 66 0\n}\n")
    assert report.ok, report.errors
    _, report = validate_chart_text(GOOD_HEADER + "[ExpertSingle]\n{\n  0 = N 32 0\n}\n")
    assert not report.ok


def test_parser_ignores_byte_order_mark():
    report = ValidationReport()
    parsed = parse_chart("﻿" + GOOD_HEADER, report)
    assert parsed.fields["Resolution"] == "192"
    assert report.ok


@pytest.mark.parametrize(
    "notes,duration,expected",
    [(0, 100, 0), (100, 100, 1), (350, 100, 3), (1000, 100, 6)],
)
def test_difficulty_tier_follows_note_density(notes, duration, expected):
    assert difficulty_tier(notes, duration) == expected


def test_song_ini_lists_required_fields_and_marks_missing_instruments():
    text = render_song_ini(
        SongIni(
            SongMetadata("Name", "Artist", album="Album", genre="Rock", year="2004"),
            song_length_ms=1234,
            preview_start_ms=500,
            difficulties={Instrument.GUITAR: 3},
        )
    )
    assert text.startswith("[song]\n")
    for line in (
        "name = Name",
        "artist = Artist",
        "album = Album",
        "genre = Rock",
        "year = 2004",
        "charter = chartgen",
        "song_length = 1234",
        "preview_start_time = 500",
        "delay = 0",
        "diff_guitar = 3",
        "diff_bass = -1",
        "diff_drums = -1",
        "diff_keys = -1",
    ):
        assert line in text.splitlines()


def write_valid_folder(folder: Path) -> None:
    track = Track(Instrument.GUITAR, Difficulty.EXPERT, [ChartNote(0, 0)])
    DotChartExporter().export(make_chart(track), folder)
    (folder / "song.ini").write_text(
        render_song_ini(
            SongIni(SongMetadata("N", "A"), 1000, difficulties={Instrument.GUITAR: 1})
        ),
        encoding="utf-8",
    )
    silence = np.zeros((44100, 2), dtype=np.float32)
    sf.write(str(folder / "song.ogg"), silence, 44100, format="OGG", subtype="VORBIS")


def test_folder_validator_accepts_a_complete_song(tmp_path):
    write_valid_folder(tmp_path)
    report = validate_song_folder(tmp_path)
    assert report.ok, report.errors


def test_folder_validator_finds_missing_files(tmp_path):
    report = validate_song_folder(tmp_path)
    joined = " ".join(report.errors)
    assert "missing notes.chart" in joined
    assert "missing song.ini" in joined
    assert "no .ogg" in joined


def test_folder_validator_requires_artist(tmp_path):
    write_valid_folder(tmp_path)
    (tmp_path / "song.ini").write_text("[song]\nname = N\ndiff_guitar = 1\n", encoding="utf-8")
    report = validate_song_folder(tmp_path)
    assert any("no artist" in error for error in report.errors)


def test_folder_validator_compares_difficulty_with_chart(tmp_path):
    write_valid_folder(tmp_path)
    text = (tmp_path / "song.ini").read_text(encoding="utf-8")
    (tmp_path / "song.ini").write_text(
        text.replace("diff_guitar = 1", "diff_guitar = -1").replace("diff_bass = -1", "diff_bass = 2"),
        encoding="utf-8",
    )
    joined = " ".join(validate_song_folder(tmp_path).errors)
    assert "guitar has notes but diff_guitar = -1" in joined
    assert "bass has no notes but diff_bass = 2" in joined


def test_folder_validator_rejects_differing_audio_lengths(tmp_path):
    write_valid_folder(tmp_path)
    shorter = np.zeros((22050, 2), dtype=np.float32)
    sf.write(str(tmp_path / "guitar.ogg"), shorter, 44100, format="OGG", subtype="VORBIS")
    report = validate_song_folder(tmp_path)
    assert any("differ in length" in error for error in report.errors)
