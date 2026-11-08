import numpy as np
import pytest

from chartgen.core import (
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


def test_constant_tempo_converts_both_ways():
    tempo_map = TempoMap([TempoEvent(0, 120.0)])
    assert tempo_map.seconds_at(192) == pytest.approx(0.5)
    assert tempo_map.ticks_at(0.5) == pytest.approx(192)


def test_tempo_change_converts_both_ways():
    tempo_map = TempoMap([TempoEvent(0, 120.0), TempoEvent(192, 60.0)])
    assert tempo_map.seconds_at(384) == pytest.approx(0.5 + 1.0)
    assert tempo_map.ticks_at(1.5) == pytest.approx(384)


def test_conversion_round_trips_over_arrays():
    tempo_map = TempoMap([TempoEvent(0, 97.3), TempoEvent(960, 101.7), TempoEvent(4800, 88.123)])
    ticks = np.linspace(0, 20000, 500)
    assert tempo_map.ticks_at(tempo_map.seconds_at(ticks)) == pytest.approx(ticks)


def test_bpm_is_rounded_to_what_a_file_can_store():
    assert TempoEvent(0, 120.00049).bpm == 120.0
    assert TempoEvent(0, 97.12345).bpm == 97.123


@pytest.mark.parametrize(
    "tempos",
    [[], [TempoEvent(192, 120.0)], [TempoEvent(0, 120.0), TempoEvent(0, 100.0)]],
)
def test_tempo_map_rejects_invalid_events(tempos):
    with pytest.raises(ValueError):
        TempoMap(tempos)


def test_tempo_map_rejects_negative_positions():
    tempo_map = TempoMap([TempoEvent(0, 120.0)])
    with pytest.raises(ValueError):
        tempo_map.seconds_at(-1)
    with pytest.raises(ValueError):
        tempo_map.ticks_at(-0.1)


@pytest.mark.parametrize("bpm", [0, -10])
def test_tempo_event_rejects_non_positive_bpm(bpm):
    with pytest.raises(ValueError):
        TempoEvent(0, bpm)


def test_time_signature_needs_power_of_two_denominator():
    with pytest.raises(ValueError):
        TimeSignatureEvent(0, 4, 3)


@pytest.mark.parametrize(
    "kwargs",
    [{"tick": -1, "lane": 0}, {"tick": 0, "lane": 6}, {"tick": 0, "lane": 0, "length": -1}],
)
def test_note_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError):
        ChartNote(**kwargs)


def test_track_sorts_notes_and_rejects_duplicates():
    track = Track(Instrument.GUITAR, Difficulty.EXPERT, [ChartNote(96, 1), ChartNote(0, 2)])
    assert [note.tick for note in track.notes] == [0, 96]
    with pytest.raises(ValueError, match="duplicate note"):
        Track(Instrument.GUITAR, Difficulty.EXPERT, [ChartNote(0, 1), ChartNote(0, 1)])


def test_track_allows_a_chord():
    track = Track(Instrument.GUITAR, Difficulty.EXPERT, [ChartNote(0, 1), ChartNote(0, 2)])
    assert len(track.notes) == 2


@pytest.mark.parametrize("name,artist", [("", "A"), ("  ", "A"), ("T", ""), ("T", "   ")])
def test_metadata_requires_name_and_artist(name, artist):
    with pytest.raises(ValueError):
        SongMetadata(name=name, artist=artist)


def test_chart_rejects_two_tracks_for_one_slot():
    tempo_map = TempoMap([TempoEvent(0, 120.0)])
    chart = Chart(SongMetadata("T", "A"), tempo_map, [Track(Instrument.BASS, Difficulty.EASY)])
    with pytest.raises(ValueError, match="duplicate track"):
        chart.add_track(Track(Instrument.BASS, Difficulty.EASY))


def test_chart_reports_only_instruments_that_have_notes():
    tempo_map = TempoMap([TempoEvent(0, 120.0)])
    chart = Chart(
        SongMetadata("T", "A"),
        tempo_map,
        [
            Track(Instrument.BASS, Difficulty.EASY),
            Track(Instrument.GUITAR, Difficulty.EASY, [ChartNote(0, 0)]),
        ],
    )
    assert chart.instruments() == {Instrument.GUITAR}


def test_invalid_phrase_and_section_are_rejected():
    with pytest.raises(ValueError):
        StarPowerPhrase(0, 0)
    with pytest.raises(ValueError):
        Section(0, "  ")
