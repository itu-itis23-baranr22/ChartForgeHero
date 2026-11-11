"""Keys: charted like a guitar, and tested on synthetic audio only.

None of the songs measured so far has a piano stem that counts as present, so none of this says how
keys do on real music. Builds and reports say so too.
"""

import json
import re
from pathlib import Path

import librosa
import numpy as np
import pytest
from conftest import SR as STEM_SR
from conftest import FakeSeparator, clicks_at, song_stems, stereo

from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.pitch import analyze_pitches
from chartgen.audio.presence import DEFAULT_THRESHOLDS, analyze_presence
from chartgen.audio.separation import STEM_NAMES
from chartgen.chart.difficulty import load_config
from chartgen.chart.fret_mapping import load_weights
from chartgen.chart.instruments import build_tracks_for, settings_for
from chartgen.clonehero.validate import validate_song_folder
from chartgen.core.model import Difficulty, Instrument, SongMetadata
from chartgen.core.timing import TempoEvent, TempoMap
from chartgen.errors import NoPlayableInstrumentError
from chartgen.evaluation.reference import load_reference
from chartgen.evaluation.run import evaluate_folder, format_report
from chartgen.pipeline import BuildConfig, build_song

SR = ANALYSIS_SAMPLERATE
ALL = frozenset(Instrument)
TEMPO = TempoMap([TempoEvent(0, 120.0)])
SECONDS = 20
START = 0.5
SPACING = 0.5
COUNT = 38


def piano_note(midi: float, seconds: float, sr: int, level: float = 0.5) -> np.ndarray:
    frequency = float(librosa.midi_to_hz(midi))
    t = np.arange(int(seconds * sr)) / sr
    wave = sum((0.5**k) * np.sin(2 * np.pi * frequency * (k + 1) * t) for k in range(4))
    return (level * wave * np.minimum(t / 0.002, 1.0) * np.exp(-t / 0.5)).astype(np.float32)


def piano_stem(sr: int = STEM_SR, seconds: int = SECONDS, level: float = 0.5) -> np.ndarray:
    """A strong line of single notes, rising and falling."""
    line = (60, 64, 67, 72, 76, 72, 67, 64)
    signal = np.zeros(seconds * sr, dtype=np.float32)
    for index in range(COUNT):
        wave = piano_note(line[index % len(line)], SPACING, sr, level)
        first = int((START + SPACING * index) * sr)
        last = min(first + wave.size, signal.size)
        signal[first:last] += wave[: last - first]
    return signal


def chord_stem() -> tuple[np.ndarray, np.ndarray]:
    """Tones over noise: flat enough for the analysis to hear more than one voice."""
    times = START + SPACING * np.arange(COUNT)
    signal = np.zeros(SECONDS * SR, dtype=np.float32)
    rng = np.random.default_rng(6)
    for time in times:
        first = int(time * SR)
        wave = sum(piano_note(midi, SPACING, SR, 0.12) for midi in (48, 52, 55, 60, 64, 67, 72))
        noise = rng.standard_normal(wave.size) * np.exp(-np.arange(wave.size) / (0.4 * SR))
        piece = wave + 0.3 * noise.astype(np.float32)
        last = min(first + piece.size, signal.size)
        signal[first:last] += piece[: last - first].astype(np.float32)
    return signal, times


def config(song_file, tmp_path, instruments=ALL) -> BuildConfig:
    return BuildConfig(
        input_path=song_file,
        metadata=SongMetadata("Şarkı", "Sanatçı"),
        instruments=instruments,
        output_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
    )


def stems_with_piano(guitar: bool = True, bass: bool = True) -> dict[str, np.ndarray]:
    stems = song_stems()
    stems["piano"] = stereo(piano_stem())
    if not guitar:
        stems["guitar"] = stems["guitar"] * 0.0
    if bass:
        stems["bass"] = stereo(_bass_line())
    else:
        stems["bass"] = stems["bass"] * 0.0
    return stems


def _bass_line() -> np.ndarray:
    line = (40, 43, 45, 47)
    signal = np.zeros(SECONDS * STEM_SR, dtype=np.float32)
    for index in range(COUNT):
        wave = piano_note(line[index % len(line)], SPACING, STEM_SR, 0.4)
        first = int((START + SPACING * index) * STEM_SR)
        last = min(first + wave.size, signal.size)
        signal[first:last] += wave[: last - first]
    return signal


def read_ini(folder: Path) -> dict[str, str]:
    lines = (folder / "song.ini").read_text(encoding="utf-8").splitlines()[1:]
    return dict(line.split(" = ", 1) for line in lines)


def gems_of(track) -> dict[int, list[int]]:
    found: dict[int, list[int]] = {}
    for note in track.notes:
        found.setdefault(note.tick, []).append(note.lane)
    return found


# ---------------------------------------------------------------- is it there?


@pytest.mark.heavy
def test_a_strong_piano_stem_gets_all_four_levels_and_its_own_audio(song_file, tmp_path):
    result = build_song(config(song_file, tmp_path), FakeSeparator(stems_with_piano()))
    assert validate_song_folder(result.folder).ok
    text = (result.folder / "notes.chart").read_text(encoding="utf-8-sig")
    for level in ("Expert", "Hard", "Medium", "Easy"):
        assert f"[{level}Keyboard]" in text
    assert (result.folder / "keys.ogg").exists()
    assert int(read_ini(result.folder)["diff_keys"]) >= 0
    assert "piano" not in result.analysis["audio_files"]["song.ogg"]["stems"]


@pytest.mark.heavy
def test_a_faint_piano_stem_gets_no_chart_and_its_sound_stays_in_the_song(song_file, tmp_path):
    result = build_song(config(song_file, tmp_path), FakeSeparator(song_stems()))
    assert validate_song_folder(result.folder).ok
    assert "Keyboard]" not in (result.folder / "notes.chart").read_text(encoding="utf-8-sig")
    assert not (result.folder / "keys.ogg").exists()
    assert read_ini(result.folder)["diff_keys"] == "-1"
    assert "piano" in result.analysis["audio_files"]["song.ogg"]["stems"]
    assert any("keys: the piano stem is below" in w for w in result.analysis["warnings"])
    assert result.analysis["not_verified_on_real_data"] == []


def test_the_piano_presence_limit_stays_as_it_was():
    limits = DEFAULT_THRESHOLDS["piano"]
    assert (limits.min_energy_ratio_db, limits.min_active_ratio) == (-18.0, 0.25)


@pytest.mark.heavy
def test_a_song_can_build_on_keys_alone(song_file, tmp_path):
    stems = stems_with_piano(guitar=False, bass=False)
    stems["drums"] = stems["drums"] * 0.0
    result = build_song(config(song_file, tmp_path), FakeSeparator(stems))
    assert validate_song_folder(result.folder).ok
    assert set(result.analysis["charts"]) == {"keys"}
    text = (result.folder / "notes.chart").read_text(encoding="utf-8-sig")
    assert "Single]" not in text and "DoubleBass]" not in text


@pytest.mark.heavy
def test_with_nothing_to_play_the_build_still_stops(song_file, tmp_path):
    stems = song_stems()
    for name in ("guitar", "bass", "piano", "drums"):
        stems[name] = stems[name] * 0.0
    with pytest.raises(NoPlayableInstrumentError):
        build_song(config(song_file, tmp_path), FakeSeparator(stems))


# ---------------------------------------------------------------- it says what it is


@pytest.mark.heavy
def test_a_keys_chart_says_it_is_not_verified_on_real_data(song_file, tmp_path):
    result = build_song(config(song_file, tmp_path), FakeSeparator(stems_with_piano()))
    assert any("keys: not verified on real data" in w for w in result.analysis["warnings"])
    assert result.analysis["not_verified_on_real_data"] == ["keys"]
    stored = json.loads((result.folder / "analysis.json").read_text(encoding="utf-8"))
    assert stored["not_verified_on_real_data"] == ["keys"]


# ---------------------------------------------------------------- the rules


@pytest.mark.heavy
def test_keys_may_have_chords_but_keep_the_rules_of_every_level():
    signal, times = chord_stem()
    next_times = np.r_[times[1:], float(SECONDS)]
    assert any(pitch.voices > 1 for pitch in analyze_pitches(signal, times, next_times, SR)), (
        "or this test proves nothing"
    )
    charted = build_tracks_for(Instrument.KEYS, signal, TEMPO, float(SECONDS))
    by_level = {item.track.difficulty: gems_of(item.track) for item in charted}
    assert list(by_level) == [Difficulty.EXPERT, Difficulty.HARD, Difficulty.MEDIUM, Difficulty.EASY]
    assert any(len(lanes) > 1 for lanes in by_level[Difficulty.EXPERT].values()), "unlike bass"
    assert set(by_level[Difficulty.EASY]) <= set(by_level[Difficulty.MEDIUM])
    assert set(by_level[Difficulty.MEDIUM]) <= set(by_level[Difficulty.HARD])
    assert set(by_level[Difficulty.HARD]) <= set(by_level[Difficulty.EXPERT])
    assert all(len(lanes) <= 2 and max(lanes) < 4 for lanes in by_level[Difficulty.MEDIUM].values())
    assert all(len(lanes) == 1 and max(lanes) < 4 for lanes in by_level[Difficulty.EASY].values())


@pytest.mark.heavy
def test_nothing_of_keys_lands_in_the_opening():
    stem = piano_stem(SR)
    charted = build_tracks_for(Instrument.KEYS, stem, TEMPO, float(SECONDS), not_before_s=10.0)
    assert charted
    for item in charted:
        placed = TEMPO.seconds_at(np.array([note.tick for note in item.track.notes], dtype=float))
        assert placed.min() >= 10.0


def test_keys_use_guitars_files_without_guitars_soft_targets():
    keys_config, keys_weights = settings_for(Instrument.KEYS)
    guitar_config, guitar_weights = settings_for(Instrument.GUITAR)
    assert keys_weights == guitar_weights == load_weights()
    assert guitar_config == load_config()
    assert not keys_config.expert_targets.ranges and not keys_config.expert_targets.lane_shares
    for level, settings in keys_config.levels.items():
        assert not settings.soft_targets.ranges and not settings.soft_targets.lane_shares
        assert settings.top_lane == guitar_config.levels[level].top_lane
        assert settings.position_ratio == guitar_config.levels[level].position_ratio
    assert keys_config.max_orange_pitch_share is None


@pytest.mark.heavy
def test_three_instruments_share_one_sync_track(song_file, tmp_path):
    result = build_song(config(song_file, tmp_path), FakeSeparator(stems_with_piano()))
    assert validate_song_folder(result.folder).ok
    text = (result.folder / "notes.chart").read_text(encoding="utf-8-sig")
    assert text.count("[SyncTrack]") == 1
    assert set(result.analysis["charts"]) == {"guitar", "bass", "keys", "drums"}
    events = result.analysis["tempo"]["tempo_events"]
    written = TempoMap([TempoEvent(event["tick"], event["bpm"]) for event in events])
    played = np.arange(START, SECONDS, SPACING)
    # All four play on the half second from START. Read through the one tempo map, they must agree.
    for section in ("ExpertSingle", "ExpertDoubleBass", "ExpertKeyboard", "ExpertDrums"):
        body = re.search(rf"\[{section}\]\s*\{{(.*?)\}}", text, flags=re.S).group(1)
        ticks = np.array(sorted({int(tick) for tick in re.findall(r"(\d+) = N", body)}), dtype=float)
        assert ticks.size >= COUNT - 3, section
        times = written.seconds_at(ticks)
        assert np.abs(times[:, None] - played[None, :]).min(axis=1).max() < 0.03, section
    audio = {path.name for path in result.folder.glob("*.ogg")}
    assert {"guitar.ogg", "bass.ogg", "keys.ogg", "song.ogg"} <= audio


# ---------------------------------------------------------------- against the human


def keys_reference(folder: Path, with_keys: bool = True) -> Path:
    from chartgen.clonehero.package import encode_ogg

    folder.mkdir(parents=True)
    times = START + SPACING * np.arange(COUNT)
    ticks = np.round(times * 2 * 192).astype(int)
    notes = "\n".join(f"  {tick} = N {index % 4} 0" for index, tick in enumerate(ticks))
    keys = f"[ExpertKeyboard]\n{{\n{notes}\n}}\n" if with_keys else ""
    (folder / "notes.chart").write_text(
        "[Song]\n{\n  Resolution = 192\n}\n[SyncTrack]\n{\n  0 = TS 4\n  0 = B 120000\n}\n"
        f"[ExpertSingle]\n{{\n{notes}\n}}\n{keys}",
        encoding="utf-8",
    )
    encode_ogg(stereo(clicks_at(times, SECONDS, STEM_SR)), STEM_SR, folder / "guitar.ogg")
    return folder


def separator_with(piano: np.ndarray) -> FakeSeparator:
    silence = np.zeros((SECONDS * STEM_SR, 2), dtype=np.float32)
    stems = {name: silence.copy() for name in STEM_NAMES}
    times = START + SPACING * np.arange(COUNT)
    stems["guitar"] = stereo(clicks_at(times, SECONDS, STEM_SR, amp=0.2))
    stems["piano"] = stereo(piano)
    return FakeSeparator(stems)


@pytest.mark.heavy
def test_evaluate_reports_keys_apart_when_the_stem_is_there(tmp_path):
    folder = keys_reference(tmp_path / "train" / "song")
    assert set(load_reference(folder).keys_levels) == {Difficulty.EXPERT}
    report = evaluate_folder(tmp_path, separator_with(piano_stem()), tmp_path / "cache")
    song = report.songs["song"]
    assert song["keys_stem"] == "present"
    assert song["keys"]["expert"]["match"]["note_f1"] >= 0.9
    assert "levels" in song, "guitar is still there, on its own"
    assert "Keys of song" in format_report(report)


@pytest.mark.heavy
def test_evaluate_scores_no_keys_when_the_stem_is_absent(tmp_path):
    keys_reference(tmp_path / "train" / "song")
    faint = piano_stem() * 0.0005
    report = evaluate_folder(tmp_path, separator_with(faint), tmp_path / "cache")
    song = report.songs["song"]
    assert song["keys_stem"] == "absent"
    assert "keys" not in song
    assert "the piano stem is absent: no chart" in format_report(report)


@pytest.mark.heavy
def test_a_reference_without_keys_keeps_its_report(tmp_path):
    folder = keys_reference(tmp_path / "train" / "song", with_keys=False)
    assert load_reference(folder).keys_levels == {}
    report = evaluate_folder(tmp_path, separator_with(piano_stem()), tmp_path / "cache")
    assert "keys" not in report.songs["song"]
    assert "keys_stem" not in report.songs["song"]
    assert "Keys of" not in format_report(report)


# ---------------------------------------------------------------- real songs


@pytest.mark.real
@pytest.mark.parametrize("real_song", ["TocaToca.mp3"], indirect=True)
def test_the_piano_of_toca_stays_absent(real_song):
    stems = real_song.stems
    mix = np.sum([stems.stems[name] for name in STEM_NAMES], axis=0)
    presence = analyze_presence("piano", stems.stems["piano"], mix, stems.samplerate)
    assert not presence.present
    assert presence.energy_ratio_db == pytest.approx(-19.3, abs=0.5)
