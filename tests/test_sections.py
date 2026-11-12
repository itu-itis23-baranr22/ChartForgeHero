"""Phase D, D.1: finding a song's sections. Boundaries on bar lines, at least four bars apart, named by
structure in ASCII; a song that hardly changes gets none rather than forced ones."""

import json
from dataclasses import replace

import numpy as np
import pytest
import soundfile as sf
from conftest import CALIFORNICATION, FakeSeparator, click_track, stereo

from chartgen.audio.io import ANALYSIS_SAMPLERATE, resample
from chartgen.audio.sections import (
    CONFIG_PATH,
    FoundSection,
    SectionAnalysis,
    SectionRuleViolation,
    check_found_sections,
    find_sections,
    load_section_config,
)
from chartgen.clonehero.validate import validate_chart_text, validate_song_folder
from chartgen.core.model import Instrument, SongMetadata
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent
from chartgen.evaluation.run import compare_structure
from chartgen.pipeline import BuildConfig, build_song

SR = ANALYSIS_SAMPLERATE
BAR_S = 2.0
TEMPO = TempoMap([TempoEvent(0, 120.0)], [TimeSignatureEvent(0, 4, 4)])
BAR_TICKS = 4 * TEMPO.resolution
CHORDS = {"A": (261.63, 329.63, 392.0), "B": (369.99, 466.16, 554.37), "C": (220.0, 277.18, 329.63)}


def part(kind: str, bars: int, sr: int = SR) -> dict[str, np.ndarray]:
    """``bars`` bars of one part: its own chord on every beat, its own voice and its own hiss."""
    seconds = bars * BAR_S
    t = np.arange(int(seconds * sr)) / sr
    envelope = np.exp(-((t % 0.5) / 0.25))
    pitched = sum(0.2 * np.sin(2 * np.pi * f * t) for f in CHORDS[kind]) * envelope
    vocals = 0.3 * np.sin(2 * np.pi * 600 * t + 3 * np.sin(2 * np.pi * 5 * t)) if kind == "B" else np.zeros_like(t)
    rng = np.random.default_rng(len(kind) + ord(kind[0]))
    hiss = (0.05 if kind == "B" else 0.005) * rng.standard_normal(t.size)
    return {"pitched": pitched.astype(np.float32), "vocals": vocals.astype(np.float32), "hiss": hiss.astype(np.float32)}


def song(plan: str, bars: int = 8, sr: int = SR) -> dict[str, np.ndarray]:
    parts = [part(kind, bars, sr) for kind in plan]
    joined = {key: np.concatenate([item[key] for item in parts]) for key in parts[0]}
    seconds = len(plan) * bars * BAR_S
    joined["drums"] = click_track(120, seconds, sr=sr, amp=0.4)[: joined["pitched"].size]
    joined["mix"] = joined["pitched"] + joined["vocals"] + joined["hiss"] + joined["drums"]
    return joined


def found_for(signals: dict[str, np.ndarray], **kwargs) -> SectionAnalysis:
    duration = signals["mix"].size / SR
    return find_sections(signals["mix"], signals["pitched"], signals["vocals"], TEMPO, duration, **kwargs)


def named(analysis: SectionAnalysis) -> list[tuple[str, float]]:
    return [(section.name, round(section.time_s, 3)) for section in analysis.sections]


# ---------------------------------------------------------------- finding them


def test_two_alternating_parts_get_their_boundaries_and_letters():
    analysis = found_for(song("ABAB"))
    assert named(analysis) == [("A1", 0.0), ("B1", 16.0), ("A2", 32.0), ("B2", 48.0)]
    assert analysis.sections[0].change is None, "no change starts the first section"
    assert all(section.change >= analysis.threshold for section in analysis.sections[1:])
    assert all(section.tick % BAR_TICKS == 0 for section in analysis.sections)


def test_a_third_part_gets_a_new_letter():
    assert [name for name, _ in named(found_for(song("ABAC")))] == ["A1", "B1", "A2", "C1"]


def test_a_song_that_never_changes_gets_no_section():
    analysis = found_for(song("AAAA"))
    assert analysis.sections == () and not analysis.found
    assert analysis.strongest_change < analysis.threshold


def test_after_an_opening_the_sections_start_after_song():
    # An opening (C) to 16 s, then the song: A, B, A.
    opening = found_for(song("CABA"), song_start_s=16.0, after_opening=True)
    assert opening.after_opening
    # Song is the A part from 16 s, written as Song but lettered: it is A1, so its return is A2.
    assert opening.song_part == "A1"
    assert named(opening) == [("B1", 32.0), ("A2", 48.0)]
    assert all(section.time_s >= 16.0 + 4 * BAR_S for section in opening.sections)
    assert found_for(song("ABAB")).song_part is None, "without an opening the first part is written as A1"


def test_sections_last_at_least_four_bars_whatever_the_music_does():
    # A narrow kernel and a low threshold fire on every change, here every two bars.
    eager = replace(load_section_config(), kernel_bars=2, novelty_threshold=0.05)
    analysis = found_for(song("ABABABAB", bars=2), config=eager)
    ticks = [section.tick for section in analysis.sections]
    assert ticks and all(later - earlier >= 4 * BAR_TICKS for earlier, later in zip(ticks, ticks[1:]))
    duration = 16 * 2 * BAR_S
    assert duration - analysis.sections[-1].time_s >= 4 * BAR_S - 0.5


def test_finding_sections_is_deterministic():
    signals = song("ABAC")
    assert found_for(signals).sections == found_for(signals).sections


def test_a_song_too_short_for_two_sections_gets_none():
    assert found_for(song("AB", bars=3)).sections == ()


# ---------------------------------------------------------------- the settings and the hard rules


def broken_config(tmp_path, old: str, new: str):
    text = CONFIG_PATH.read_text(encoding="utf-8")
    assert old in text, old
    path = tmp_path / "sections.toml"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return path


def test_the_settings_load():
    config = load_section_config()
    assert (config.kernel_bars, config.novelty_threshold, config.min_section_bars) == (8, 0.18, 4)
    assert config.same_part_similarity == 0.6


@pytest.mark.parametrize(
    "old,new,message",
    [
        ("min_section_bars = 4", "min_section_bars = 3", "hard rule"),
        ("kernel_bars = 8", "kernel_bars = 7", "even"),
        ("novelty_threshold = 0.18", "novelty_threshold = 0", "between 0 and 1"),
        ("harmony = 1.0", "harmony = -1.0", "negative"),
        ("[letters]\n", "[letters]\nmax_sections = 3\n", "expected keys"),
        ("[boundaries]\n", "[boundaries]\nsnap_to_beats = true\n", "expected keys"),
    ],
)
def test_the_settings_cannot_loosen_a_hard_rule_or_be_wrong(tmp_path, old, new, message):
    with pytest.raises(ValueError, match=message):
        load_section_config(broken_config(tmp_path, old, new))


def section(bar: float, name: str) -> FoundSection:
    tick = int(bar * BAR_TICKS)
    return FoundSection(tick, TEMPO.seconds_at(float(tick)), name, name.rstrip("0123456789"), 0.3)


@pytest.mark.parametrize(
    "sections,message",
    [
        ((section(0, "A1"), section(4.5, "B1")), "not on a bar line"),
        ((section(0, "A1"), section(3, "B1")), "shorter than 4 bars"),
        ((section(0, "A1"), section(4, "Ä1")), "ASCII"),
        ((section(0, "A1"), section(29, "B1")), "last section is shorter"),
    ],
)
def test_the_rule_check_catches_each_broken_rule(sections, message):
    with pytest.raises(SectionRuleViolation, match=message):
        check_found_sections(SectionAnalysis(sections, 0.4, 0.18, False, 0.0), TEMPO, 64.0)


def test_the_rule_check_wants_four_bars_after_song():
    with pytest.raises(SectionRuleViolation, match="after Song"):
        check_found_sections(SectionAnalysis((section(10, "A1"),), 0.4, 0.18, True, 0.0), TEMPO, 64.0, song_start_s=16.0)


# ---------------------------------------------------------------- the validator


def chart_with_sections(events: str) -> str:
    return (
        "[Song]\n{\n  Resolution = 192\n}\n[SyncTrack]\n{\n  0 = TS 4\n  0 = B 120000\n}\n"
        f"[Events]\n{{\n{events}}}\n[ExpertSingle]\n{{\n  0 = N 0 0\n}}\n"
    )


@pytest.mark.parametrize(
    "events,message",
    [
        ('  0 = E "section A1"\n  1000 = E "section B1"\n', "not on a bar line"),
        ('  0 = E "section A1"\n  2304 = E "section B1"\n', "lasts less than 4 bars"),
        ('  0 = E "section Ä1"\n', "not plain ASCII"),
    ],
)
def test_the_validator_checks_sections_on_its_own(events, message):
    _, report = validate_chart_text(chart_with_sections(events))
    assert any(message in error for error in report.errors), report.errors


def test_the_validator_lets_the_opening_be():
    # Song falls on the song's first onset; A1 is the first bar line four bars after it.
    events = '  0 = E "section Intro"\n  1000 = E "section Song"\n  4608 = E "section A1"\n  7680 = E "section B1"\n'
    _, report = validate_chart_text(chart_with_sections(events))
    assert report.ok, report.errors


# ---------------------------------------------------------------- whole builds


def built_stems(plan: str) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """The stems of ``plan`` at 44.1 kHz, as a separator would give them, and their mix."""
    signals = song(plan, sr=44100)
    silence = np.zeros_like(signals["mix"])
    stems = {
        "guitar": stereo(signals["pitched"]),
        "bass": stereo(silence),
        "drums": stereo(signals["drums"]),
        "other": stereo(signals["hiss"]),
        "vocals": stereo(signals["vocals"]),
        "piano": stereo(silence),
    }
    return stems, stereo(signals["mix"])


@pytest.mark.heavy
def test_a_build_writes_its_sections_and_says_how_it_found_them(tmp_path):
    stems, mix = built_stems("ABAB")
    path = tmp_path / "song.wav"
    sf.write(str(path), mix, 44100)
    result = build_song(
        BuildConfig(
            input_path=path,
            metadata=SongMetadata("Parts", "Test"),
            instruments=frozenset({Instrument.GUITAR, Instrument.DRUMS}),
            output_dir=tmp_path / "out",
            cache_dir=tmp_path / "cache",
        ),
        FakeSeparator(stems),
    )
    assert validate_song_folder(result.folder).ok
    text = (result.folder / "notes.chart").read_text(encoding="utf-8-sig")
    for name in ("A1", "B1", "A2", "B2"):
        assert f'E "section {name}"' in text
    analysis = json.loads((result.folder / "analysis.json").read_text(encoding="utf-8"))
    assert [section["name"] for section in analysis["sections"]["written"]] == ["A1", "B1", "A2", "B2"]
    assert [section["letter"] for section in analysis["sections"]["found"]] == ["A", "B", "A", "B"]
    assert not any(warning.startswith("sections:") for warning in analysis["warnings"])


@pytest.mark.heavy
def test_a_build_of_a_song_that_never_changes_warns_and_forces_nothing(tmp_path):
    stems, mix = built_stems("AAAA")
    path = tmp_path / "song.wav"
    sf.write(str(path), mix, 44100)
    result = build_song(
        BuildConfig(
            input_path=path,
            metadata=SongMetadata("Flat", "Test"),
            instruments=frozenset({Instrument.GUITAR}),
            output_dir=tmp_path / "out",
            cache_dir=tmp_path / "cache",
        ),
        FakeSeparator(stems),
    )
    text = (result.folder / "notes.chart").read_text(encoding="utf-8-sig")
    assert 'E "section' not in text
    analysis = json.loads((result.folder / "analysis.json").read_text(encoding="utf-8"))
    assert analysis["sections"]["written"] == []
    assert any(warning.startswith("sections: none found in the song") for warning in analysis["warnings"])


# ---------------------------------------------------------------- the real reference


@pytest.mark.real
@pytest.mark.parametrize("real_song", [CALIFORNICATION], indirect=True)
def test_californication_sections_beat_the_naive_boundaries(real_song):
    """Californication is train: the settings were chosen on it."""
    structure = compare_structure(real_song.reference, real_song.tempo, real_song.stems)
    sections = structure["sections"]
    print(sections["match"], sections["naive"])
    f1 = sections["match"]["f1"]
    # The owner's floor is 0.55; 0.70 is 0.05 below the 0.750 measured at D.1 (owner, 2026-11-12).
    assert f1 >= 0.70, "approved threshold"
    for period in (4, 8, 16):
        assert f1 > sections["naive"][f"every_{period}_bars"], period
    assert f1 > sections["naive"]["best_naive"]["f1"], "even the naive one the human chart chose"
    names = [section["name"] for section in sections["mine"]]
    assert all(name.isascii() and name[0].isalpha() and name[-1].isdigit() for name in names)
