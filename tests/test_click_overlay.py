import numpy as np
import pytest
import soundfile as sf
from conftest import SR, FakeSeparator, dominant_frequency, sine, song_stems, stereo

from chartgen.audio.io import AudioData
from chartgen.cli import main
from chartgen.clonehero.chart_format import DotChartExporter
from chartgen.clonehero.click_overlay import (
    BEAT_HZ,
    CLICK_FILE,
    CLICK_SECONDS,
    DOWNBEAT_HZ,
    ClickSchedule,
    click_schedule,
    render_click_overlay,
    tempo_map_from_chart,
    write_click_overlay,
)
from chartgen.core import Chart, ChartNote, Difficulty, Instrument, SongMetadata, TempoEvent, TempoMap
from chartgen.core import TimeSignatureEvent, Track
from chartgen.errors import PackagingError


def chart_text(tempo_map: TempoMap) -> str:
    chart = Chart(
        SongMetadata("T", "A"),
        tempo_map,
        [Track(Instrument.GUITAR, Difficulty.EXPERT, [ChartNote(0, 0)])],
    )
    return DotChartExporter().render(chart).decode("utf-8-sig")


def test_tempo_map_survives_the_trip_through_a_chart_file():
    original = TempoMap(
        [TempoEvent(0, 83.758), TempoEvent(192, 97.083), TempoEvent(4800, 96.5)],
        [TimeSignatureEvent(0, 3, 4), TimeSignatureEvent(576, 6, 8)],
    )
    parsed = tempo_map_from_chart(chart_text(original))
    assert parsed.tempos == original.tempos
    assert parsed.time_signatures == original.time_signatures
    assert parsed.resolution == original.resolution


@pytest.mark.parametrize(
    "text",
    [
        "",
        "[Song]\n{\n  Resolution = 192\n}\n",
        "[Song]\n{\n}\n[SyncTrack]\n{\n  0 = TS 4\n  0 = B 120000\n}\n",
        "[Song]\n{\n  Resolution = 192\n}\n[SyncTrack]\n{\n  0 = B abc\n}\n",
        "[Song]\n{\n  Resolution = 192\n}\n[SyncTrack]\n{\n  0 = TS 4\n}\n",
    ],
    ids=["empty", "no sync track", "no resolution", "bad tempo", "no tempo"],
)
def test_unusable_chart_gives_a_clear_error(text):
    with pytest.raises(PackagingError):
        tempo_map_from_chart(text)


def test_schedule_lists_beats_and_marks_every_fourth_as_downbeat():
    schedule = click_schedule(TempoMap([TempoEvent(0, 120.0)]), 10.0)
    assert schedule.times[:3] == pytest.approx([0.5, 1.0, 1.5])
    assert schedule.times[-1] < 10.0
    # Tick 0 is left out, so the first downbeat is beat four at 2.0 s.
    assert list(schedule.is_downbeat[:8]) == [False, False, False, True, False, False, False, True]
    assert schedule.times[schedule.is_downbeat][0] == pytest.approx(2.0)


def test_pickup_measure_moves_the_downbeats():
    tempo_map = TempoMap(
        [TempoEvent(0, 120.0)],
        [TimeSignatureEvent(0, 3, 4), TimeSignatureEvent(3 * 192, 4, 4)],
    )
    schedule = click_schedule(tempo_map, 10.0)
    assert schedule.times[schedule.is_downbeat][:2] == pytest.approx([1.5, 3.5])


def test_three_four_has_downbeats_every_three_beats():
    tempo_map = TempoMap([TempoEvent(0, 120.0)], [TimeSignatureEvent(0, 3, 4)])
    schedule = click_schedule(tempo_map, 10.0)
    assert schedule.times[schedule.is_downbeat][:2] == pytest.approx([1.5, 3.0])


def test_six_eight_counts_eighth_notes():
    tempo_map = TempoMap([TempoEvent(0, 120.0)], [TimeSignatureEvent(0, 6, 8)])
    schedule = click_schedule(tempo_map, 5.0)
    assert schedule.times[:2] == pytest.approx([0.25, 0.5])
    assert schedule.times[schedule.is_downbeat][0] == pytest.approx(1.5)


def test_tempo_change_moves_the_clicks():
    tempo_map = TempoMap([TempoEvent(0, 120.0), TempoEvent(384, 60.0)])
    schedule = click_schedule(tempo_map, 5.0)
    assert schedule.times[:3] == pytest.approx([0.5, 1.0, 2.0])


def test_clicks_land_on_the_exact_sample_with_the_right_tone():
    audio = AudioData(np.zeros((SR * 4, 2), dtype=np.float32), SR)
    schedule = ClickSchedule(np.array([1.0, 2.0]), np.array([True, False]))
    rendered = render_click_overlay(audio, schedule)

    assert rendered.shape == audio.samples.shape
    nonzero = np.flatnonzero(np.abs(rendered[:, 0]) > 1e-6)
    assert nonzero[0] == pytest.approx(SR, abs=2)
    click_frames = int(CLICK_SECONDS * SR)
    downbeat = rendered[SR : SR + click_frames, 0]
    beat = rendered[2 * SR : 2 * SR + click_frames, 0]
    assert dominant_frequency(downbeat) == pytest.approx(DOWNBEAT_HZ, abs=60)
    assert dominant_frequency(beat) == pytest.approx(BEAT_HZ, abs=60)
    assert np.abs(downbeat).max() > np.abs(beat).max()


def test_overlay_keeps_the_mix_audible_and_never_clips():
    samples = stereo(sine(220, 5, amp=1.0))
    audio = AudioData(samples, SR)
    schedule = ClickSchedule(np.arange(0.5, 4.5, 0.5), np.zeros(8, dtype=bool))
    rendered = render_click_overlay(audio, schedule)
    assert np.abs(rendered).max() <= 0.99 + 1e-6
    assert dominant_frequency(rendered[:, 0]) == pytest.approx(220, abs=2)


def test_click_past_the_end_is_ignored():
    audio = AudioData(np.zeros((SR, 2), dtype=np.float32), SR)
    rendered = render_click_overlay(audio, ClickSchedule(np.array([0.99, 5.0]), np.array([False, True])))
    assert rendered.shape == audio.samples.shape


def test_overlay_reads_the_chart_file_not_the_map_in_memory(tmp_path):
    """Hand-edit the written file: the clicks must follow the edit."""
    chart_path = tmp_path / "notes.chart"
    chart_path.write_text(chart_text(TempoMap([TempoEvent(0, 120.0)])).replace("B 120000", "B 60000"), encoding="utf-8")
    audio = AudioData(np.zeros((SR * 10, 2), dtype=np.float32), SR)
    schedule = write_click_overlay(chart_path, audio, tmp_path / CLICK_FILE)
    assert schedule.times[:2] == pytest.approx([1.0, 2.0])
    written, rate = sf.read(str(tmp_path / CLICK_FILE), always_2d=True)
    assert rate == SR
    assert written.shape == audio.samples.shape


def cli_arguments(song_file, tmp_path, *extra: str) -> list[str]:
    return [
        "build",
        str(song_file),
        "--artist",
        "A",
        "--title",
        "T",
        "--output-dir",
        str(tmp_path / "out"),
        "--cache-dir",
        str(tmp_path / "cache"),
        *extra,
    ]


@pytest.fixture
def fake_demucs(monkeypatch):
    monkeypatch.setattr(
        "chartgen.audio.separation.DemucsSeparator",
        lambda device="auto": FakeSeparator(song_stems()),
    )


def test_cli_click_overlay_flag_writes_the_file(song_file, tmp_path, fake_demucs):
    assert main(cli_arguments(song_file, tmp_path, "--click-overlay")) == 0
    folder = tmp_path / "out" / "A - T"
    written, rate = sf.read(str(folder / CLICK_FILE), always_2d=True)
    assert rate == SR
    assert written.shape[0] == SR * 20
    assert main(["validate", str(folder)]) == 0, "the extra file must not break the song"


def test_no_click_file_without_the_flag(song_file, tmp_path, fake_demucs):
    assert main(cli_arguments(song_file, tmp_path)) == 0
    assert not (tmp_path / "out" / "A - T" / CLICK_FILE).exists()


def test_cli_bpm_flag_reaches_the_chart(song_file, tmp_path, fake_demucs):
    assert main(cli_arguments(song_file, tmp_path, "--bpm", "133.5")) == 0
    chart = (tmp_path / "out" / "A - T" / "notes.chart").read_text(encoding="utf-8-sig")
    assert "B 133500" in chart


@pytest.mark.parametrize("value", ["0", "-5", "abc", "1000"])
def test_cli_rejects_a_bad_bpm(song_file, tmp_path, value):
    with pytest.raises(SystemExit):
        main(cli_arguments(song_file, tmp_path, "--bpm", value))
