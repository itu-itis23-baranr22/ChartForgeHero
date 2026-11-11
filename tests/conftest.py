"""Shared helpers: synthetic audio, a separator that needs no model, and real songs loaded once."""

from __future__ import annotations

import gc
import os
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from chartgen.audio.separation import STEM_NAMES

SR = 44100


def click_times(bpm: float, seconds: float, start: float = 0.0) -> np.ndarray:
    return np.arange(start, seconds - 0.05, 60.0 / bpm)


def clicks_at(times: np.ndarray, seconds: float, sr: int = SR, amp: float = 0.8) -> np.ndarray:
    """A decaying 2 kHz burst at each time: a sharp, unambiguous attack."""
    signal = np.zeros(int(seconds * sr), dtype=np.float32)
    length = int(0.03 * sr)
    t = np.arange(length) / sr
    burst = amp * np.sin(2 * np.pi * 2000 * t) * np.exp(-t / 0.008)
    for time in times:
        start = int(round(time * sr))
        end = min(start + length, len(signal))
        signal[start:end] += burst[: end - start].astype(np.float32)
    return signal


def click_track(
    bpm: float, seconds: float, start: float = 0.0, sr: int = SR, amp: float = 0.8
) -> np.ndarray:
    return clicks_at(click_times(bpm, seconds, start), seconds, sr, amp)


def sine(freq: float, seconds: float, sr: int = SR, amp: float = 0.3) -> np.ndarray:
    return (amp * np.sin(2 * np.pi * freq * np.arange(int(seconds * sr)) / sr)).astype(np.float32)


def stereo(mono: np.ndarray) -> np.ndarray:
    return np.stack([mono, mono], axis=1)


def dominant_frequency(mono: np.ndarray, sr: int = SR) -> float:
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
    return float(np.fft.rfftfreq(len(mono), 1 / sr)[np.argmax(spectrum)])


class FakeSeparator:
    """Returns prepared stems and counts how often it was asked."""

    cache_id = "fake-separator"

    def __init__(self, stems: dict[str, np.ndarray], samplerate: int = SR) -> None:
        self.stems = stems
        self.samplerate = samplerate
        self.calls = 0

    def separate(self, audio) -> tuple[int, dict[str, np.ndarray]]:
        self.calls += 1
        return self.samplerate, {name: samples.copy() for name, samples in self.stems.items()}


def song_stems(seconds: float = 20.0) -> dict[str, np.ndarray]:
    """A small rock song: clicks on guitar and drums, a sine on bass, faint piano bleed."""
    frames = int(seconds * SR)
    guitar = click_track(120, seconds, start=0.5) + sine(330, seconds, amp=0.02)
    silence = np.zeros(frames, dtype=np.float32)
    stems = {
        "guitar": guitar,
        "bass": sine(82, seconds, amp=0.25),
        "drums": click_track(120, seconds, start=0.5, amp=0.5),
        "other": sine(220, seconds, amp=0.05),
        "vocals": silence,
        "piano": sine(440, seconds, amp=0.0005),
    }
    assert set(stems) == set(STEM_NAMES)
    return {name: stereo(samples) for name, samples in stems.items()}


@pytest.fixture
def song_file(tmp_path: Path) -> Path:
    """A WAV holding the mix of :func:`song_stems`."""
    mix = np.sum(list(song_stems().values()), axis=0)
    path = tmp_path / "input.wav"
    sf.write(str(path), mix * 0.8, SR)
    return path


# ---------------------------------------------------------------- real Demucs


@pytest.fixture(scope="module")
def demucs_loaded_once() -> Iterator[list[str]]:
    """Demucs loads each model once for the tests that use this, not once per separation, and lets
    go of it when they are done. Yields the names of the models loaded so far.

    Every test that runs Demucs on purpose lives in ``test_separation.py``, so module scope means once
    per session and the model leaves memory as soon as that module is done.
    """
    pretrained = pytest.importorskip("demucs.pretrained")
    original = pretrained.get_model
    models: dict[tuple[str, object], object] = {}
    loaded: list[str] = []

    def get_model(name: str, repo=None):
        if (name, repo) not in models:
            models[name, repo] = original(name, repo)
            loaded.append(name)
        return models[name, repo]

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(pretrained, "get_model", get_model)
        yield loaded
    models.clear()
    gc.collect()


# ---------------------------------------------------------------- real songs, loaded once

MUSIC_ENV = "CHARTGEN_MUSIC_DIR"
REFERENCE_ENV = "CHARTGEN_REFERENCE_DIR"
CALIFORNICATION = "references/train:Californication"
"""The one song with a human chart. Other keys of :func:`real_song` are paths in ``CHARTGEN_MUSIC_DIR``."""


def _read_only(array: np.ndarray) -> np.ndarray:
    array.flags.writeable = False
    return array


class RealSong:
    """A real song, loaded once and shared by every test that asks for it.

    Everything is computed the way each test used to compute it for itself, so sharing changes
    nothing a test sees. The arrays are read-only: a test writing into one would change it for every
    test after it. Each part is computed when first asked for.
    """

    def __init__(self, key: str) -> None:
        from chartgen.audio.io import load_audio
        from chartgen.evaluation.reference import find_references, load_reference

        self.key = key
        self.reference = None
        if key == CALIFORNICATION:
            folder = os.environ.get(REFERENCE_ENV)
            if not folder:
                pytest.skip(f"{REFERENCE_ENV} is not set")
            found = [path for path in find_references(Path(folder) / "train") if "Californication" in path.name]
            if not found:
                pytest.skip("Californication is not among the references")
            self.reference = load_reference(found[0])
            self.path, self.audio = self.reference.source, self.reference.audio
        else:
            folder = os.environ.get(MUSIC_ENV)
            if not folder:
                pytest.skip(f"{MUSIC_ENV} is not set")
            self.path = Path(folder) / key
            if not self.path.is_file():
                pytest.skip(f"{self.path} is not here")
            self.audio = load_audio(self.path)
        _read_only(self.audio.samples)
        self._stems = None
        self._mono: dict[str, np.ndarray] = {}
        self._tempo = None
        self._tempo_from_mix = None

    @property
    def stems(self):
        """The Demucs stems, from ``.cache/stems`` as a build reads them."""
        if self._stems is None:
            from chartgen.audio.separation import DemucsSeparator, separate_with_cache

            self._stems = separate_with_cache(self.path, self.audio, DemucsSeparator(), Path(".cache/stems"))
            for samples in self._stems.stems.values():
                _read_only(samples)
        return self._stems

    def mono(self, name: str) -> np.ndarray:
        """``analysis_mono`` of one stem, or of the whole song for ``"mix"``."""
        if name not in self._mono:
            from chartgen.audio.io import analysis_mono

            if name == "mix":
                mono = analysis_mono(self.audio.samples, self.audio.samplerate)
            elif name == "pitched":
                pitched = np.sum([self.stems.stems[stem] for stem in ("bass", "guitar", "piano", "other")], axis=0)
                mono = analysis_mono(pitched, self.stems.samplerate)
            else:
                mono = analysis_mono(self.stems.stems[name], self.stems.samplerate)
            self._mono[name] = _read_only(mono)
        return self._mono[name]

    @property
    def tempo(self):
        """The tempo analysis a build makes: from the mix, the drums, the pitched stems and the bass."""
        if self._tempo is None:
            from chartgen.audio.tempo import estimate_tempo_map

            self._tempo = estimate_tempo_map(
                self.mono("mix"), drums=self.mono("drums"), harmonic=self.mono("pitched"), bass=self.mono("bass")
            )
        return self._tempo

    @property
    def tempo_from_mix_only(self):
        """The tempo analysis from the mix alone, without the stems."""
        if self._tempo_from_mix is None:
            from chartgen.audio.tempo import estimate_tempo_map

            self._tempo_from_mix = estimate_tempo_map(self.mono("mix"))
        return self._tempo_from_mix

    def release(self) -> None:
        self.audio = self.reference = self._stems = self._tempo = self._tempo_from_mix = None
        self._mono.clear()
        gc.collect()


_real_song_loads: list[str] = []
"""Every song :func:`real_song` loaded, in order; the summary says if one was loaded twice."""


@pytest.fixture(scope="session")
def real_song(request: pytest.FixtureRequest) -> Iterator[RealSong]:
    """A real song, chosen by indirect parametrization: a path in ``CHARTGEN_MUSIC_DIR`` or
    :data:`CALIFORNICATION`. Skips when the song is not on this machine.

    When ``real_song`` is parametrized together with a plain value, pass ``scope="session"`` to
    ``parametrize``, or pytest tears the song down after every test.

    The tests of one song run one after another (see :func:`pytest_collection_modifyitems`), and a song is
    torn down before the next one loads, so one song at most is in memory.
    """
    _real_song_loads.append(request.param)
    song = RealSong(request.param)
    yield song
    song.release()


def _uses_real_song(item: pytest.Item) -> bool:
    return "real_song" in getattr(getattr(item, "callspec", None), "params", {})


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Run the tests of each real song together, so that each song loads once, and real Demucs last.

    Pytest groups by a parameter's place in its list, not by its value, and each of these tests lists
    one song, so it cannot do this itself. Real Demucs comes after the songs because torch keeps about
    1.4 GB in the process once it has run a model, even after the model is gone: before the songs it
    raised the peak of ``-Full`` from 3.2 to 4.4 GB.

    A test on a real song must also be marked ``real``, or the quick checks would try to run it.
    """
    unmarked = [item.nodeid for item in items if _uses_real_song(item) and item.get_closest_marker("real") is None]
    if unmarked:
        raise pytest.UsageError(f"uses real_song but is not marked real: {', '.join(unmarked)}")
    songs: dict[str, list[pytest.Item]] = {}
    for item in items:
        if _uses_real_song(item):
            songs.setdefault(item.callspec.params["real_song"], []).append(item)
    demucs = [item for item in items if not _uses_real_song(item) and item.get_closest_marker("slow")]
    rest = [item for item in items if not _uses_real_song(item) and not item.get_closest_marker("slow")]
    items[:] = rest + [item for group in songs.values() for item in group] + demucs


def pytest_terminal_summary(terminalreporter) -> None:
    if not _real_song_loads:
        return
    twice = sorted({key for key in _real_song_loads if _real_song_loads.count(key) > 1})
    line = f"real songs: {len(set(_real_song_loads))} loaded, {len(_real_song_loads)} loads"
    terminalreporter.write_line(line + (f"; loaded more than once: {', '.join(twice)}" if twice else ", each once"))
