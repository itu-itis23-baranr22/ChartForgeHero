import json
import random
import subprocess
import sys

import numpy as np
import pytest
import soundfile as sf
from conftest import SR, FakeSeparator, click_track, sine, song_stems, stereo

from chartgen.audio.io import AudioData, load_audio
from chartgen.audio.separation import (
    STEM_NAMES,
    DemucsSeparator,
    fixed_python_random,
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
        assert np.allclose(second.stems[name], first.stems[name], atol=1e-4)


def test_first_build_and_cached_build_see_identical_samples(song_file, tmp_path):
    """FLAC rounds to 24 bits, so without reading back these would differ a little."""
    audio = load_audio(song_file)
    separator = FakeSeparator(song_stems())
    first = separate_with_cache(song_file, audio, separator, tmp_path / "cache")
    second = separate_with_cache(song_file, audio, separator, tmp_path / "cache")
    for name in STEM_NAMES:
        assert np.array_equal(first.stems[name], second.stems[name])


def test_fixed_random_repeats_and_leaves_no_trace():
    random.seed(7)
    expected_next = random.Random(7).random()
    with fixed_python_random(42):
        first = [random.randint(0, 22050) for _ in range(5)]
    with fixed_python_random(42):
        second = [random.randint(0, 22050) for _ in range(5)]
    with fixed_python_random(43):
        third = [random.randint(0, 22050) for _ in range(5)]
    assert first == second
    assert first != third
    assert random.random() == expected_next, "the global generator must be put back"


def test_fixed_random_restores_after_a_failure():
    random.seed(7)
    expected_next = random.Random(7).random()
    with pytest.raises(RuntimeError):
        with fixed_python_random(42):
            raise RuntimeError("Demucs failed")
    assert random.random() == expected_next


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
    assert np.allclose(cached.stems["guitar"], stems["guitar"], atol=1e-3)


@pytest.mark.parametrize("damage", ["manifest", "stem", "wrong_hash"])
@pytest.mark.heavy
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
    def key(**settings) -> str:
        return DemucsSeparator(**{"device": "cpu", **settings}).cache_id

    assert key(shifts=1) != key(shifts=2)
    assert key(seed=1) != key(seed=2)
    assert key(model_name="a") != key(model_name="b")
    assert key(device="cpu") != key(device="cuda")


def test_cache_id_names_model_device_seed_and_shifts():
    cache_id = DemucsSeparator(model_name="htdemucs_6s", device="cpu", seed=42, shifts=1).cache_id
    assert all(part in cache_id for part in ("htdemucs_6s", "cpu", "seed42", "shifts1"))


def test_cache_id_names_the_kind_of_device_not_which_one():
    assert DemucsSeparator(device="cuda:0").cache_id == DemucsSeparator(device="cuda:1").cache_id
    assert "cuda" in DemucsSeparator(device="cuda:1").cache_id


def test_auto_device_is_resolved_for_the_cache_key(monkeypatch):
    monkeypatch.setattr("chartgen.audio.separation.resolve_device", lambda requested: "cuda")
    assert DemucsSeparator(device="auto").cache_id == DemucsSeparator(device="cuda").cache_id


def test_cache_key_works_without_torch(monkeypatch):
    """Cached stems stay usable where torch is missing; only a miss needs it, and says so."""
    monkeypatch.setitem(sys.modules, "torch", None)
    assert DemucsSeparator(device="auto").cache_id == DemucsSeparator(device="cpu").cache_id


def test_a_changed_seed_is_separated_again(song_file, tmp_path):
    audio = load_audio(song_file)

    class Seeded(FakeSeparator):
        def __init__(self, stems, seed):
            super().__init__(stems)
            self.cache_id = f"fake-seed{seed}"

    one, two = Seeded(song_stems(), 1), Seeded(song_stems(), 2)
    separate_with_cache(song_file, audio, one, tmp_path)
    separate_with_cache(song_file, audio, two, tmp_path)
    assert (one.calls, two.calls) == (1, 1)


def test_normal_use_never_imports_the_model_stack():
    code = (
        "import sys, chartgen.cli, chartgen.pipeline, chartgen.audio.separation\n"
        "import importlib.util\n"
        "if importlib.util.find_spec('fastapi'):\n"
        "    import chartgen.editor.server  # the editor too (SPEC 49)\n"
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
def test_real_demucs_returns_six_aligned_stems(demucs_loaded_once):
    audio = AudioData(stereo(sine(220, 6) + sine(880, 6)), SR)
    samplerate, stems = DemucsSeparator(device="cpu").separate(audio)
    assert samplerate == 44100
    assert set(stems) == set(STEM_NAMES)
    assert {samples.shape for samples in stems.values()} == {audio.samples.shape}


@pytest.mark.slow
def test_real_demucs_gives_identical_stems_for_the_same_seed(demucs_loaded_once):
    """With shifts on, Demucs moves the audio by a random amount, so stems used to differ."""
    audio = AudioData(stereo(sine(220, 12) + sine(880, 12) + click_track(120, 12)), SR)
    _, first = DemucsSeparator(device="cpu", seed=42).separate(audio)
    _, second = DemucsSeparator(device="cpu", seed=42).separate(audio)
    _, other = DemucsSeparator(device="cpu", seed=43).separate(audio)
    for name in STEM_NAMES:
        assert np.array_equal(first[name], second[name]), name
    assert not all(np.array_equal(first[name], other[name]) for name in STEM_NAMES)
    assert demucs_loaded_once == ["htdemucs_6s"], "three separations, one model load"
