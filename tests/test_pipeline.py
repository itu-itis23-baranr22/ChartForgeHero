"""End-to-end builds with separation mocked, so no model is downloaded."""

import json
import logging

import numpy as np
import pytest
import soundfile as sf
from conftest import SR, FakeSeparator, click_times, song_stems

from chartgen.chart.charter import build_expert_track
from chartgen.cli import main
from chartgen.clonehero.validate import validate_chart_text, validate_song_folder
from chartgen.core.model import Difficulty, Instrument, SongMetadata
from chartgen.core.timing import TempoEvent, TempoMap
from chartgen.errors import AudioLoadError, NoPlayableInstrumentError, PackagingError
from chartgen.pipeline import BuildConfig, build_song

ALL = frozenset(Instrument)


def config(song_file, tmp_path, instruments=ALL, force=False) -> BuildConfig:
    return BuildConfig(
        input_path=song_file,
        metadata=SongMetadata("Şarkı", "Sanatçı", genre="Rock"),
        instruments=instruments,
        output_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
        force=force,
    )


def read_ini(folder) -> dict[str, str]:
    lines = (folder / "song.ini").read_text(encoding="utf-8").splitlines()[1:]
    return dict(line.split(" = ", 1) for line in lines)


def test_build_produces_a_valid_folder(song_file, tmp_path):
    result = build_song(config(song_file, tmp_path), FakeSeparator(song_stems()))

    assert result.folder.name == "Sanatçı - Şarkı"
    report = validate_song_folder(result.folder)
    assert report.ok, report.errors
    names = {path.name for path in result.folder.iterdir()}
    assert {"notes.chart", "song.ini", "song.ogg", "guitar.ogg", "analysis.json"} <= names


@pytest.mark.heavy
def test_absent_stems_get_no_file_and_no_chart(song_file, tmp_path):
    folder = build_song(config(song_file, tmp_path), FakeSeparator(song_stems())).folder
    names = {path.name for path in folder.iterdir()}
    assert "keys.ogg" not in names, "the piano stem is only faint bleed"
    assert "vocals.ogg" not in names, "the vocal stem is silent"

    ini = read_ini(folder)
    assert int(ini["diff_guitar"]) >= 0
    assert int(ini["diff_drums"]) >= 0, "the drum stem is there, and drums are charted now"
    for key in ("diff_bass", "diff_keys"):
        assert ini[key] == "-1"
    chart = (folder / "notes.chart").read_text(encoding="utf-8-sig")
    assert "[ExpertSingle]" in chart
    assert "[ExpertKeyboard]" not in chart


@pytest.mark.heavy
def test_present_stems_keep_their_audio_and_drums_are_charted(song_file, tmp_path):
    result = build_song(config(song_file, tmp_path), FakeSeparator(song_stems()))
    names = {path.name for path in result.folder.iterdir()}
    assert {"bass.ogg", "drums.ogg"} <= names
    assert not any("not implemented" in w for w in result.analysis["warnings"])
    assert "[ExpertDrums]" in (result.folder / "notes.chart").read_text(encoding="utf-8-sig")


@pytest.mark.heavy
def test_all_audio_files_share_the_exact_length(song_file, tmp_path):
    folder = build_song(config(song_file, tmp_path), FakeSeparator(song_stems())).folder
    lengths = {sf.info(str(path)).frames for path in folder.glob("*.ogg")}
    assert lengths == {SR * 20}


@pytest.mark.heavy
def test_guitar_notes_follow_the_clicks(song_file, tmp_path):
    folder = build_song(config(song_file, tmp_path), FakeSeparator(song_stems())).folder
    analysis = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
    expected = len(click_times(120, 20, 0.5))
    assert analysis["charts"]["guitar"]["expert"]["positions"] == pytest.approx(expected, abs=2)
    assert analysis["tempo"]["bpm"] == pytest.approx(120, abs=0.1)
    assert analysis["tempo"]["method"] == "constant"


def test_analysis_records_the_whole_build(song_file, tmp_path):
    folder = build_song(config(song_file, tmp_path), FakeSeparator(song_stems())).folder
    analysis = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))

    assert analysis["input"]["duration_s"] == pytest.approx(20.0)
    assert analysis["stems"]["guitar"]["present"] is True
    assert analysis["stems"]["piano"]["present"] is False
    assert analysis["stems"]["vocals"]["energy_ratio_db"] is None, "silence must stay valid JSON"
    assert analysis["audio_files"]["song.ogg"]["lag_frames"] == 0
    assert analysis["tempo"]["decision"]
    assert analysis["tempo"]["tempo_event_count"] == len(analysis["tempo"]["tempo_events"])
    assert all(event["reason"] for event in analysis["tempo"]["tempo_events"])
    assert analysis["tempo"]["fit"]["on_grid"] > 0.9
    assert analysis["tempo"]["one_tempo_fit"]["max_ms"] >= 0
    assert analysis["tempo"]["max_beat_drift_limit_ms"] == 25.0
    assert analysis["click_overlay"] is None
    assert analysis["song_ini"]["difficulty"]["guitar"] >= 0
    assert set(analysis["charts"]["guitar"]) == {"expert", "hard", "medium", "easy"}
    assert len(analysis["difficulty_hard_rules"]) == 7
    for level in ("hard", "medium", "easy"):
        assert analysis["charts"]["guitar"][level]["soft_targets"]
        assert "auto_hopo_share" in analysis["charts"]["guitar"][level]["measures"]
    assert "auto_hopo_share" in analysis["charts"]["guitar"]["expert"]["measures"]
    assert "soft_targets" in analysis["charts"]["guitar"]["hard"]
    assert set(analysis["timings_s"]) == {
        "Load audio",
        "Separate stems",
        "Check stem presence",
        "Track tempo on the mix",
        "Find sections",
        "Chart instruments",
        "Package song folder",
        "Validate",
    }
    assert set(analysis["sections"]) == {
        "written", "found", "song_part", "strongest_change", "threshold", "after_opening", "bar_step", "seconds"
    }
    assert analysis["sections"]["song_part"] is None, "no opening, so no part is written as Song"


@pytest.mark.heavy
def test_build_writes_four_difficulties_in_their_chain(song_file, tmp_path):
    folder = build_song(config(song_file, tmp_path), FakeSeparator(song_stems())).folder
    chart = (folder / "notes.chart").read_text(encoding="utf-8-sig")
    _, report = validate_chart_text(chart)
    assert report.ok, report.errors
    for name in ("ExpertSingle", "HardSingle", "MediumSingle", "EasySingle"):
        assert f"[{name}]" in chart


@pytest.mark.heavy
def test_a_missed_soft_target_warns_but_the_build_succeeds(song_file, tmp_path, caplog):
    """The click song has no chords at all, so it cannot reach the chord share of Hard."""
    with caplog.at_level(logging.INFO, logger="chartgen"):
        result = build_song(config(song_file, tmp_path), FakeSeparator(song_stems()))
    warnings = result.analysis["warnings"]
    assert any("guitar/hard is outside its soft targets" in warning for warning in warnings)
    assert "guitar/hard is outside its soft targets" in caplog.text
    chord_share = result.analysis["charts"]["guitar"]["hard"]["soft_targets"]["chord_share"]
    assert chord_share["in_range"] is False
    assert validate_song_folder(result.folder).ok


@pytest.mark.heavy
def test_rebuild_uses_the_cache_and_requires_force(song_file, tmp_path):
    separator = FakeSeparator(song_stems())
    build_song(config(song_file, tmp_path), separator)

    with pytest.raises(PackagingError, match="already exists"):
        build_song(config(song_file, tmp_path), separator)
    assert separator.calls == 1

    result = build_song(config(song_file, tmp_path, force=True), separator)
    assert separator.calls == 1
    assert result.analysis["separation"]["from_cache"] is True


@pytest.mark.heavy
def test_only_guitar_requested_moves_the_rest_to_backing(song_file, tmp_path):
    cfg = config(song_file, tmp_path, frozenset({Instrument.GUITAR}))
    folder = build_song(cfg, FakeSeparator(song_stems())).folder
    assert {p.name for p in folder.glob("*.ogg")} == {"guitar.ogg", "song.ogg"}


def test_song_without_guitar_stops_with_an_explanation_and_no_folder(song_file, tmp_path):
    stems = song_stems()
    stems["guitar"] = stems["guitar"] * 0.0
    cfg = config(song_file, tmp_path, frozenset({Instrument.GUITAR}))
    with pytest.raises(NoPlayableInstrumentError, match="below the presence threshold"):
        build_song(cfg, FakeSeparator(stems))
    out = tmp_path / "out"
    assert not out.exists() or list(out.iterdir()) == []


@pytest.mark.heavy
def test_failed_packaging_leaves_no_partial_folder(song_file, tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise PackagingError("disk full")

    monkeypatch.setattr("chartgen.pipeline.write_audio_files", fail)
    with pytest.raises(PackagingError):
        build_song(config(song_file, tmp_path), FakeSeparator(song_stems()))
    assert list((tmp_path / "out").iterdir()) == []


@pytest.mark.heavy
def test_failed_rebuild_keeps_the_previous_song(song_file, tmp_path, monkeypatch):
    separator = FakeSeparator(song_stems())
    folder = build_song(config(song_file, tmp_path), separator).folder

    def fail(*args, **kwargs):
        raise PackagingError("disk full")

    monkeypatch.setattr("chartgen.pipeline.write_audio_files", fail)
    with pytest.raises(PackagingError):
        build_song(config(song_file, tmp_path, force=True), separator)
    assert validate_song_folder(folder).ok


@pytest.mark.heavy
def test_stages_are_reported_with_durations(song_file, tmp_path, caplog):
    with caplog.at_level(logging.INFO, logger="chartgen"):
        build_song(config(song_file, tmp_path), FakeSeparator(song_stems()))
    assert "[1/8] Load audio done in" in caplog.text
    assert "[5/8] Find sections done in" in caplog.text
    assert "[8/8] Validate done in" in caplog.text


# ---------------------------------------------------------------- charter


def test_track_snaps_clicks_to_the_grid_and_stays_playable():
    from conftest import clicks_at

    truth = click_times(120, 20, 0.5)
    tempo_map = TempoMap([TempoEvent(0, 120.0)])
    result = build_expert_track(
        Instrument.GUITAR, clicks_at(truth, 20, 22050), tempo_map, 20.0, samplerate=22050
    )
    ticks = np.array([note.tick for note in result.track.notes])
    assert result.track.difficulty is Difficulty.EXPERT
    assert len(set(ticks)) == len(truth)
    assert np.all(ticks % 48 == 0), "every click at 120 BPM lies on the sixteenth grid"
    lanes = [note.lane for note in result.track.notes]
    assert all(0 <= lane <= 4 for lane in lanes)


def test_track_enforces_a_minimum_note_gap():
    from conftest import clicks_at

    truth = np.arange(0.5, 10, 0.06)
    tempo_map = TempoMap([TempoEvent(0, 120.0)])
    result = build_expert_track(
        Instrument.GUITAR, clicks_at(truth, 10, 22050), tempo_map, 10.0, samplerate=22050
    )
    ticks = sorted({note.tick for note in result.track.notes})
    times = tempo_map.seconds_at(np.array(ticks, dtype=float))
    assert np.diff(times).min() >= 0.09 - 1e-6


def test_track_on_silence_has_no_notes():
    tempo_map = TempoMap([TempoEvent(0, 120.0)])
    result = build_expert_track(
        Instrument.GUITAR, np.zeros(22050 * 5, dtype=np.float32), tempo_map, 5.0, samplerate=22050
    )
    assert result.track.notes == []


# ---------------------------------------------------------------- CLI


@pytest.mark.heavy
def test_cli_validate_reports_ok_and_failure(song_file, tmp_path, capsys):
    folder = build_song(config(song_file, tmp_path), FakeSeparator(song_stems())).folder
    assert main(["validate", str(folder)]) == 0
    assert main(["validate", str(tmp_path / "nothing")]) == 1
    assert main(["validate", str(folder), str(folder)]) == 0
    assert main(["validate", str(tmp_path / "nothing"), str(folder)]) == 1, "one bad folder is enough"


def test_cli_build_turns_expected_failures_into_a_message(tmp_path):
    missing = tmp_path / "missing.mp3"
    code = main(
        [
            "build",
            str(missing),
            "--artist",
            "A",
            "--title",
            "T",
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    assert code == 2


def test_cli_rejects_blank_artist(song_file):
    assert main(["build", str(song_file), "--artist", "  ", "--title", "T"]) == 2


def test_cli_build_asks_for_every_instrument_unless_told_otherwise(song_file, monkeypatch):
    """Without --instruments a build charts every instrument whose stem is there; the stem presence
    check, not the command line, leaves an instrument out."""
    asked = []

    def stop_after_reading_the_config(config, separator):
        asked.append(config.instruments)
        raise NoPlayableInstrumentError("stopped by the test")

    monkeypatch.setattr("chartgen.audio.separation.DemucsSeparator", lambda device="auto": None)
    monkeypatch.setattr("chartgen.pipeline.build_song", stop_after_reading_the_config)
    assert main(["build", str(song_file), "--artist", "A", "--title", "T"]) == 2
    assert asked == [frozenset(Instrument)]
    assert {instrument.value for instrument in Instrument} == {"guitar", "bass", "drums", "keys"}


@pytest.mark.parametrize("value", ["kazoo", "guitar,kazoo", ""])
def test_cli_rejects_unknown_instruments(song_file, value):
    with pytest.raises(SystemExit):
        main(["build", str(song_file), "--artist", "A", "--title", "T", "--instruments", value])


@pytest.mark.heavy
def test_generated_chart_text_validates_alone(song_file, tmp_path):
    folder = build_song(config(song_file, tmp_path), FakeSeparator(song_stems())).folder
    text = (folder / "notes.chart").read_text(encoding="utf-8-sig")
    _, report = validate_chart_text(text)
    assert report.ok, report.errors


def test_load_errors_reach_the_caller(tmp_path):
    cfg = config(tmp_path / "missing.wav", tmp_path)
    with pytest.raises(AudioLoadError):
        build_song(cfg, FakeSeparator(song_stems()))
