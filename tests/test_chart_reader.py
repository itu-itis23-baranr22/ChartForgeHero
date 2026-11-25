"""The ``.chart`` reader (SPEC 51): what the writer writes comes back byte for byte, anything else is refused."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import skip_missing

from chartgen.clonehero.chart_format import DotChartExporter
from chartgen.clonehero.chart_reader import read_chart, read_chart_file
from chartgen.core.model import (
    OPEN_LANE,
    Chart,
    ChartNote,
    Difficulty,
    Instrument,
    Section,
    SongMetadata,
    StarPowerPhrase,
    Track,
)
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent
from chartgen.errors import ChartReadError

OUTPUTS = Path(__file__).resolve().parents[1] / "outputs"


def every_feature() -> Chart:
    """A chart with everything the writer can write."""
    tempo_map = TempoMap(
        [TempoEvent(0, 156.654), TempoEvent(192, 171.244), TempoEvent(3456, 181.194)],
        [TimeSignatureEvent(0, 2), TimeSignatureEvent(384, 4), TimeSignatureEvent(6528, 6, 8)],
    )
    guitar = Track(
        Instrument.GUITAR,
        Difficulty.EXPERT,
        [
            ChartNote(768, 0),
            ChartNote(768, 1),
            ChartNote(864, 2, length=192),
            ChartNote(960, 3, forced=True),
            ChartNote(1056, 4, tap=True),
            ChartNote(1152, OPEN_LANE, length=96),
            ChartNote(1248, 1, forced=True),
            ChartNote(1248, 2, forced=True),
        ],
        [StarPowerPhrase(768, 768)],
    )
    hard = Track(Instrument.GUITAR, Difficulty.HARD, [ChartNote(768, 0), ChartNote(960, 2)])
    bass = Track(Instrument.BASS, Difficulty.EXPERT, [ChartNote(768, 0, length=96), ChartNote(864, 4)])
    drums = Track(
        Instrument.DRUMS,
        Difficulty.EXPERT,
        [
            ChartNote(768, 0),
            ChartNote(768, 2, cymbal=True),
            ChartNote(864, 1),
            ChartNote(864, 3),
            ChartNote(960, 4, cymbal=True),
            ChartNote(960, 3, cymbal=True),
        ],
        [StarPowerPhrase(768, 768)],
    )
    keys = Track(Instrument.KEYS, Difficulty.EASY, [ChartNote(1536, 2)])
    metadata = SongMetadata("Paper Satellites", "The Lantern Choir", album="Night Bus", genre="Rock", charter="chartgen")
    return Chart(metadata, tempo_map, [guitar, hard, bass, drums, keys], [Section(0, "Intro"), Section(768, "A1")])


def test_every_feature_comes_back_byte_for_byte():
    data = DotChartExporter().render(every_feature())
    chart = read_chart(data.decode("utf-8-sig"))
    assert DotChartExporter().render(chart) == data
    assert [(t.instrument, t.difficulty) for t in chart.tracks] == [
        (Instrument.GUITAR, Difficulty.EXPERT),
        (Instrument.GUITAR, Difficulty.HARD),
        (Instrument.BASS, Difficulty.EXPERT),
        (Instrument.DRUMS, Difficulty.EXPERT),
        (Instrument.KEYS, Difficulty.EASY),
    ]
    guitar = chart.tracks[0]
    assert guitar.notes == every_feature().tracks[0].notes
    assert chart.tracks[3].notes == every_feature().tracks[3].notes
    assert chart.metadata == every_feature().metadata
    assert [(s.tick, s.name) for s in chart.sections] == [(0, "Intro"), (768, "A1")]
    assert chart.tempo_map.time_signatures[-1] == TimeSignatureEvent(6528, 6, 8)


def test_a_file_is_read_as_the_writer_wrote_it(tmp_path):
    DotChartExporter().export(every_feature(), tmp_path)
    path = tmp_path / "notes.chart"
    assert DotChartExporter().render(read_chart_file(path)) == path.read_bytes()


def replaced(old: str, new: str) -> str:
    text = DotChartExporter().render(every_feature()).decode("utf-8-sig")
    assert old in text, old
    return text.replace(old, new, 1)


@pytest.mark.parametrize(
    "old,new,message",
    [
        ("  Offset = 0", "  Offset = 0\r\n  MusicStream = \"song.ogg\"", "MusicStream"),
        ("  Offset = 0", "  Offset = 120", "Offset is 120"),
        ("  0 = B 156654", "  0 = B 156654\r\n  96 = A 500000", "never writes A"),
        ('  768 = E "section A1"', '  768 = E "section A1"\r\n  800 = E "lyric hello"', "only sections"),
        ("[ExpertSingle]\r\n{", "[ExpertSingle]\r\n{\r\n  700 = E solo", "never writes E solo"),
        ("[ExpertDrums]\r\n{", "[ExpertDrums]\r\n{\r\n  700 = N 32 0", "N 32"),
        ("[ExpertDrums]\r\n{", "[ExpertDrums]\r\n{\r\n  700 = N 5 0", "N 5"),
        ("[ExpertDrums]\r\n{", "[ExpertDrums]\r\n{\r\n  700 = N 0 0\r\n  700 = N 67 0", "cymbal flag without its note"),
        ("[ExpertSingle]\r\n{", "[ExpertSingle]\r\n{\r\n  700 = N 5 0", "flag without a note"),
        ("[ExpertSingle]\r\n{", "[ExpertSingle]\r\n{\r\n  700 = N 1 0\r\n  700 = N 1 0", "duplicate note"),
        ("[ExpertSingle]\r\n{", "[ExpertSingle]\r\n{\r\n  700 = N 5 12\r\n  700 = N 1 0", "flag N 5 with a length"),
        ("  Resolution = 192", "  Resolution = x", "Resolution is not a number"),
        ('  Name = "Paper Satellites"', "  Name = Paper Satellites", "not a quoted string"),
        ("[Events]\r\n{", "[Events]", "malformed"),
    ],
)
def test_what_the_writer_never_writes_is_refused(old, new, message):
    with pytest.raises(ChartReadError, match=message):
        read_chart(replaced(old, new))


def test_a_file_that_is_not_utf8_is_refused(tmp_path):
    path = tmp_path / "notes.chart"
    path.write_bytes(b"\xff\xfe[Song]")
    with pytest.raises(ChartReadError, match="cannot read"):
        read_chart_file(path)


def song_folders() -> list[Path]:
    if not OUTPUTS.is_dir():
        return []
    return sorted(p for p in OUTPUTS.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")))


@pytest.mark.real
def test_every_song_folder_in_outputs_comes_back_byte_for_byte():
    folders = song_folders()
    if not folders:
        skip_missing(f"song folders in {OUTPUTS}")
    different = []
    for folder in folders:
        path = folder / "notes.chart"
        if DotChartExporter().render(read_chart_file(path)) != path.read_bytes():
            different.append(folder.name)
    assert not different, different
