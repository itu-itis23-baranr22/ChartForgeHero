import json
import subprocess
import sys

import numpy as np
import pytest
import soundfile as sf
from conftest import SR, FakeSeparator, sine, song_stems, stereo

from chartgen.audio.io import AudioData, load_audio
from chartgen.audio.separation import (
    STEM_NAMES,
    DemucsSeparator,
    resolve_device,
    separate_with_cache,
)
from chartgen.errors import AudioLoadError, SeparationError


def test_separator_runs_once_for_the_same_file(song_file, tmp_path):
    audio = load_audio(song_file)
    separator = FakeSeparator(song_stems())
    cache = tmp_path / "cache"

    first = separate_with_cache(song_file, audio, separator, cache)
    second = separate_with_cache(song_file, audio, separator, cache)

    assert separator.calls == 1
    assert not first.from_cache
    assert second.from_cache
    assert second.frames == first.frames
    for name in STEM_NAMES:
        assert second.stems[name] == pytest.approx(first.stems[name], abs=1e-4)


def test_cache_key_follows_file_content(song_file, tmp_path):
    separator = FakeSeparator(song_stems())
    cache = tmp_path / "cache"
    separate_with_cache(song_file, load_audio(song_file), separator, cache)

    other = tmp_path / "other.wav"
    sf.write(str(other), stereo(sine(100, 1)), SR)
    separate_with_cache(other, load_audio(other), separator, cache)
    assert separator.calls == 2


def test_stems_louder_than_full_scale_survive_the_cache(song_file, tmp_path):
    stems = song_stems()
    stems["guitar"] = stems["guitar"] * 3.0
    assert np.abs(stems["guitar"]).max() > 1.0
    separator = FakeSeparator(stems)
    audio = load_audio(song_file)
    separate_with_cache(song_file, audio, separator, tmp_path / "c")
    cached = separate_with_cache(song_file, audio, separator, tmp_path / "c")
    assert cached.stems["guitar"] == pytest.approx(stems["guitar"], abs=1e-3)


@pytest.mark.parametrize("damage", ["manifest", "stem", "wrong_hash"])
def test_damaged_cache_entry_is_separated_again(song_file, tmp_path, damage):
    separator = FakeSeparator(song_stems())
    audio = load_audio(song_file)
    cache = tmp_path / "cache"
    separate_with_cache(song_file, audio, separator, cache)
    entry = next(cache.iterdir())

    if damage == "manifest":
        (entry / "manifest.json").write_text("{not json", encoding="utf-8")
    elif damage == "stem":
        (entry / "guitar.flac").write_bytes(b"not audio")
    else:
        manifest = json.loads((entry / "manifest.json").read_text(encoding="utf-8"))
        manifest["sha256"] = "0" * 64
        (entry / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = separate_with_cache(song_file, audio, separator, cache)
    assert separator.calls == 2
    assert not result.from_cache


def test_failed_cache_write_does_not_fail_the_build(song_file, tmp_path):
    blocked = tmp_path / "file-not-folder"
    blocked.write_text("x", encoding="utf-8")
    result = separate_with_cache(
        song_file, load_audio(song_file), FakeSeparator(song_stems()), blocked
    )
    assert not result.from_cache


def test_wrong_stem_names_are_rejected(song_file, tmp_path):
    stems = song_stems()
    del stems["piano"]
    with pytest.raises(SeparationError, match="unexpected stems"):
        separate_with_cache(song_file, load_audio(song_file), FakeSeparator(stems), tmp_path)


def test_mismatched_stem_lengths_are_rejected(song_file, tmp_path):
    stems = song_stems()
    stems["bass"] = stems["bass"][:100]
    with pytest.raises(SeparationError, match="mismatched"):
        separate_with_cache(song_file, load_audio(song_file), FakeSeparator(stems), tmp_path)


def test_missing_demucs_gives_an_actionable_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "demucs.apply", None)
    audio = AudioData(stereo(sine(100, 1)), SR)
    with pytest.raises(SeparationError, match="pip install"):
        DemucsSeparator().separate(audio)


def test_explicit_device_is_used_as_given():
    assert resolve_device("cpu") == "cpu"


def test_cache_id_changes_with_settings():
    assert DemucsSeparator(shifts=1).cache_id != DemucsSeparator(shifts=2).cache_id


def test_normal_use_never_imports_the_model_stack():
    code = (
        "import sys, chartgen.cli, chartgen.pipeline, chartgen.audio.separation\n"
        "loaded = {'torch', 'demucs'} & set(sys.modules)\n"
        "assert not loaded, loaded\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


@pytest.mark.parametrize(
    "name,content,message",
    [
        ("absent.mp3", None, "not found"),
        ("song.m4a", b"xxx", "Unsupported"),
        ("broken.mp3", b"not really audio", "Could not decode"),
    ],
)
def test_load_audio_errors(tmp_path, name, content, message):
    path = tmp_path / name
    if content is not None:
        path.write_bytes(content)
    with pytest.raises(AudioLoadError, match=message):
        load_audio(path)


def test_load_audio_rejects_an_empty_file(tmp_path):
    path = tmp_path / "empty.wav"
    sf.write(str(path), np.zeros((0, 2), dtype=np.float32), SR)
    with pytest.raises(AudioLoadError, match="no audio"):
        load_audio(path)


@pytest.mark.slow
def test_real_demucs_returns_six_aligned_stems():
    audio = AudioData(stereo(sine(220, 6) + sine(880, 6)), SR)
    samplerate, stems = DemucsSeparator(device="cpu").separate(audio)
    assert samplerate == 44100
    assert set(stems) == set(STEM_NAMES)
    assert {samples.shape for samples in stems.values()} == {audio.samples.shape}
