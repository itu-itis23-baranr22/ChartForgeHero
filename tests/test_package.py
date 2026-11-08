import numpy as np
import pytest
import soundfile as sf
from conftest import SR, dominant_frequency, sine, stereo

from chartgen.audio.presence import PresenceThreshold, StemPresence
from chartgen.clonehero.package import (
    AudioPlan,
    best_preview_start_ms,
    encode_ogg,
    folder_name,
    measure_lag,
    plan_audio,
    write_audio_files,
)
from chartgen.core.model import Instrument
from chartgen.errors import PackagingError


def presence(**present: bool) -> dict[str, StemPresence]:
    limits = PresenceThreshold(-25, 0.1)
    names = ("guitar", "bass", "drums", "piano", "vocals")
    return {
        name: StemPresence(name, present.get(name, True), -10.0, 0.5, limits) for name in names
    }


ALL = frozenset(Instrument)


def test_plan_gives_each_present_stem_its_own_file():
    plan = plan_audio(presence(), ALL)
    assert plan.files == {
        "guitar.ogg": ("guitar",),
        "bass.ogg": ("bass",),
        "drums.ogg": ("drums",),
        "keys.ogg": ("piano",),
        "vocals.ogg": ("vocals",),
        "song.ogg": ("other",),
    }


def test_rejected_stem_moves_to_backing_instead_of_vanishing():
    plan = plan_audio(presence(piano=False), ALL)
    assert "keys.ogg" not in plan.files
    assert plan.files["song.ogg"] == ("other", "piano")


def test_unrequested_instrument_moves_to_backing():
    plan = plan_audio(presence(), frozenset({Instrument.GUITAR}))
    assert set(plan.files) == {"guitar.ogg", "vocals.ogg", "song.ogg"}
    assert set(plan.files["song.ogg"]) == {"other", "bass", "drums", "piano"}


def test_every_stem_is_used_exactly_once():
    for flags in ({}, {"guitar": False}, {"vocals": False, "piano": False}):
        plan = plan_audio(presence(**flags), frozenset({Instrument.BASS}))
        used = [stem for stems in plan.files.values() for stem in stems]
        assert sorted(used) == sorted(["guitar", "bass", "drums", "piano", "vocals", "other"])


def test_two_sine_stems_stay_separate_through_encoding(tmp_path):
    """Spec test: a mix of two sine stems, each must come back as its own file."""
    stems = {"guitar": stereo(sine(880, 5)), "other": stereo(sine(220, 5))}
    plan = AudioPlan({"guitar.ogg": ("guitar",), "song.ogg": ("other",)})
    encoded = write_audio_files(stems, SR, plan, tmp_path)

    assert {item.file_name for item in encoded} == {"guitar.ogg", "song.ogg"}
    for item in encoded:
        assert item.frames == stems["guitar"].shape[0]
        assert item.lag_frames == 0
    guitar, _ = sf.read(str(tmp_path / "guitar.ogg"), always_2d=True)
    backing, _ = sf.read(str(tmp_path / "song.ogg"), always_2d=True)
    assert dominant_frequency(guitar[:, 0]) == pytest.approx(880, abs=2)
    assert dominant_frequency(backing[:, 0]) == pytest.approx(220, abs=2)


def test_backing_track_sums_its_stems(tmp_path):
    stems = {"other": stereo(sine(220, 3)), "piano": stereo(sine(1000, 3))}
    plan = AudioPlan({"song.ogg": ("other", "piano")})
    write_audio_files(stems, SR, plan, tmp_path)
    decoded, _ = sf.read(str(tmp_path / "song.ogg"), always_2d=True)
    spectrum = np.abs(np.fft.rfft(decoded[:, 0]))
    frequencies = np.fft.rfftfreq(len(decoded), 1 / SR)
    for target in (220, 1000):
        band = (frequencies > target - 5) & (frequencies < target + 5)
        assert spectrum[band].max() > 0.2 * spectrum.max()


def test_shared_gain_prevents_clipping_and_keeps_balance(tmp_path):
    stems = {"guitar": stereo(sine(440, 2, amp=1.6)), "other": stereo(sine(220, 2, amp=0.4))}
    plan = AudioPlan({"guitar.ogg": ("guitar",), "song.ogg": ("other",)})
    write_audio_files(stems, SR, plan, tmp_path)
    guitar, _ = sf.read(str(tmp_path / "guitar.ogg"), always_2d=True)
    backing, _ = sf.read(str(tmp_path / "song.ogg"), always_2d=True)
    assert np.abs(guitar).max() <= 1.02
    ratio = np.sqrt(np.mean(guitar**2)) / np.sqrt(np.mean(backing**2))
    assert ratio == pytest.approx(4.0, rel=0.05)


@pytest.mark.heavy
def test_long_audio_encodes_to_the_exact_length(tmp_path):
    rng = np.random.default_rng(0)
    frames = SR * 200 + 137
    samples = (rng.normal(0, 0.1, (frames, 2))).astype(np.float32)
    path = tmp_path / "long.ogg"
    encode_ogg(samples, SR, path)
    assert sf.info(str(path)).frames == frames


@pytest.mark.parametrize("shift", [-200, 37, 1500])
def test_lag_measurement_detects_a_shift(shift):
    rng = np.random.default_rng(1)
    source = rng.normal(0, 0.2, SR * 6).astype(np.float32)
    shifted = np.roll(source, shift)
    assert measure_lag(source, shifted, SR) == shift


def test_lag_measurement_is_zero_when_aligned_and_none_when_silent():
    source = sine(330, 5)
    assert measure_lag(source, source, SR) == 0
    silence = np.zeros_like(source)
    assert measure_lag(silence, silence, SR) is None


def test_misaligned_encoder_output_is_refused(tmp_path, monkeypatch):
    rng = np.random.default_rng(2)
    samples = stereo(rng.normal(0, 0.2, SR * 5).astype(np.float32))

    def broken_encoder(data, samplerate, path):
        sf.write(str(path), np.roll(data, 500, axis=0), samplerate, format="OGG", subtype="VORBIS")

    monkeypatch.setattr("chartgen.clonehero.package.encode_ogg", broken_encoder)
    with pytest.raises(PackagingError, match="misaligned"):
        write_audio_files({"other": samples}, SR, AudioPlan({"song.ogg": ("other",)}), tmp_path)


def test_truncated_encoder_output_is_refused(tmp_path, monkeypatch):
    samples = stereo(sine(440, 2))

    def broken_encoder(data, samplerate, path):
        sf.write(str(path), data[:1000], samplerate, format="OGG", subtype="VORBIS")

    monkeypatch.setattr("chartgen.clonehero.package.encode_ogg", broken_encoder)
    with pytest.raises(PackagingError, match="decoded to"):
        write_audio_files({"other": samples}, SR, AudioPlan({"song.ogg": ("other",)}), tmp_path)


@pytest.mark.parametrize(
    "artist,title,expected",
    [
        ("Artist", "Title", "Artist - Title"),
        ("AC/DC", "T.N.T.", "AC_DC - T.N.T"),
        ('A:B*C?', 'D"E<F>G|H', "A_B_C_ - D_E_F_G_H"),
        ("Sanatçı", "Şarkı", "Sanatçı - Şarkı"),
        ("  Spaced   Out ", " Song. ", "Spaced Out - Song"),
    ],
)
def test_folder_name_is_safe(artist, title, expected):
    assert folder_name(artist, title) == expected


def test_preview_starts_at_the_loudest_part():
    quiet = sine(220, 60, sr=22050, amp=0.01)
    loud_from = 40 * 22050
    quiet[loud_from:loud_from + 15 * 22050] = sine(220, 15, sr=22050, amp=0.8)
    start = best_preview_start_ms(quiet, 22050)
    assert 25000 <= start <= 40000


def test_preview_of_a_short_song_starts_at_zero():
    assert best_preview_start_ms(sine(220, 10, sr=22050), 22050) == 0
    assert best_preview_start_ms(np.empty(0, dtype=np.float32), 22050) == 0
