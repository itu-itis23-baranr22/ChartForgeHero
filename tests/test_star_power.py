"""Phase D, D.3: star power. Where phrases go, the hard rules in code and in the validator, a build, and
Californication against its human chart."""

import json
from dataclasses import replace

import numpy as np
import pytest
from conftest import CALIFORNICATION, FakeSeparator, song_stems

from chartgen.chart.instruments import build_tracks_for
from chartgen.chart.sections import song_section_tick
from chartgen.chart.star_power import (
    DRUM_ACTIVATION_NOT_VERIFIED,
    HARD_RULES,
    StarPowerRuleViolation,
    check_star_power,
    load_star_power_config,
    place_star_power,
)
from chartgen.clonehero.validate import validate_chart_text, validate_song_folder
from chartgen.core.model import ChartNote, Difficulty, Instrument, SongMetadata, StarPowerPhrase, Track
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent
from chartgen.pipeline import BuildConfig, build_song

RES = 192
BAR = 4 * RES
"""At 120 BPM a 4/4 bar lasts two seconds."""
TEMPO = TempoMap([TempoEvent(0, 120.0)])


def beats(start_s: float, end_s: float) -> list[int]:
    """A tick on every beat from ``start_s`` to before ``end_s``, at 120 BPM."""
    return list(range(round(start_s * 2) * RES, round(end_s * 2) * RES, RES))


def levels(expert: list[int], easy: list[int] | None = None, instrument=Instrument.GUITAR) -> list[Track]:
    """Four levels: Expert, Hard and Medium with ``expert``, Easy with ``easy`` (``expert`` if None)."""
    ticks = {Difficulty.EXPERT: expert, Difficulty.HARD: expert, Difficulty.MEDIUM: expert, Difficulty.EASY: easy if easy is not None else expert}
    return [Track(instrument, level, [ChartNote(tick, 0) for tick in ticks[level]]) for level in Difficulty]


# ---------------------------------------------------------------- where phrases go


def test_phrases_last_a_bar_about_every_twenty_five_seconds_the_same_on_every_level():
    plan = place_star_power(levels(beats(0, 120)), TEMPO, 120.0)
    # The first goes to the bar closest to 15 s, the next to the bar closest to 25 s after the last; a tie
    # goes to the earlier bar (14 s and 16 s, then 38 s and 40 s...).
    assert [phrase.start_s for phrase in plan.phrases] == pytest.approx([14.0, 38.0, 62.0, 86.0, 110.0])
    assert all(phrase.length == BAR and phrase.tick % BAR == 0 for phrase in plan.phrases)
    assert all(phrase.notes == (4, 4, 4, 4) for phrase in plan.phrases), "four beats on each level"
    assert plan.star_power_phrases() == [StarPowerPhrase(phrase.tick, BAR) for phrase in plan.phrases]
    assert plan.per_minute == pytest.approx(2.5)
    assert plan.soft_warnings() == []
    record = plan.as_dict()
    assert (record["count"], record["median_gap_s"], record["bars_per_phrase"]) == (5, 24.0, 1)
    assert record["phrases"][0]["notes_inside"] == {"expert": 4, "hard": 4, "medium": 4, "easy": 4}


def test_a_phrase_only_goes_where_every_level_has_a_note():
    even_bars = [tick for tick in beats(0, 120) if (tick // BAR) % 2 == 0]
    plan = place_star_power(levels(beats(0, 120), easy=even_bars), TEMPO, 120.0)
    assert plan.phrases and all((phrase.tick // BAR) % 2 == 0 for phrase in plan.phrases)


def test_bars_with_two_notes_on_the_easiest_level_come_first():
    one_per_bar = list(range(0, 60 * BAR, BAR))
    easy = sorted(one_per_bar + [8 * BAR + RES])  # bar 8 (16 s) has two
    plan = place_star_power(levels(beats(0, 120), easy=easy), TEMPO, 120.0)
    assert plan.phrases[0].start_s == pytest.approx(16.0), "16 s with two notes beats 14 s with one"
    assert plan.phrases[1].start_s == pytest.approx(40.0), "then the closest bar again: 16 + 25 = 41"
    sparse = [warning for warning in plan.soft_warnings() if "fewer than 2 notes on Easy" in warning]
    assert sparse and not sparse[0].startswith("star power: guitar: 1 phrases"), "counted in plain words"


def test_a_long_gap_is_reported_not_filled_with_a_bar_that_lacks_notes():
    easy = beats(0, 20) + beats(70, 120)
    plan = place_star_power(levels(beats(0, 120), easy=easy), TEMPO, 120.0)
    assert not any(20.0 <= phrase.start_s < 70.0 for phrase in plan.phrases)
    assert max(plan.gaps_s) > 30.0
    assert "star power: guitar: 1 gap longer than 30 s (longest 56.0 s): no bar in between held a note on every level" in plan.soft_warnings()


def test_no_phrase_starts_before_the_song_does():
    start = 10 * BAR  # 20 s, where Song is after an opening
    plan = place_star_power(levels(beats(0, 120)), TEMPO, 120.0, song_start_tick=start)
    assert plan.phrases[0].tick >= start
    assert plan.phrases[0].start_s == pytest.approx(34.0), "15 s after the song starts: 34 s and 36 s tie"


def test_no_bar_that_every_level_plays_means_no_star_power_and_a_warning():
    odd_bars = [tick for tick in beats(0, 120) if (tick // BAR) % 2 == 1]
    even_bars = [tick for tick in beats(0, 120) if (tick // BAR) % 2 == 0]
    plan = place_star_power(levels(even_bars, easy=odd_bars), TEMPO, 120.0)
    assert plan.phrases == ()
    assert plan.soft_warnings() == ["star power: guitar: no bar after the song starts holds a note on every level, so no phrases"]


def test_a_phrase_lasts_one_bar_in_any_meter():
    tempo = TempoMap([TempoEvent(0, 120.0)], [TimeSignatureEvent(0, 3, 4), TimeSignatureEvent(20 * 3 * RES, 4, 4)])
    ticks = list(range(0, 20 * 3 * RES + 40 * BAR, RES))
    plan = place_star_power(levels(ticks), tempo, float(tempo.seconds_at(float(ticks[-1] + RES))))
    lengths = {phrase.tick < 20 * 3 * RES: phrase.length for phrase in plan.phrases}
    assert lengths == {True: 3 * RES, False: BAR}, "three beats in 3/4, four in 4/4"


def test_the_settings_choose_the_spacing_and_the_warnings():
    config = replace(load_star_power_config(), gap_s=40.0, min_gap_s=35.0, max_gap_s=45.0, per_minute=(2.0, 3.0))
    plan = place_star_power(levels(beats(0, 120)), TEMPO, 120.0, config=config)
    assert [phrase.start_s for phrase in plan.phrases] == pytest.approx([14.0, 54.0, 94.0])
    assert any("1.5 per minute (wanted 2 to 3)" in warning for warning in plan.soft_warnings())


def test_star_power_is_placed_one_instrument_at_a_time():
    with pytest.raises(ValueError, match="one instrument"):
        place_star_power(levels(beats(0, 60))[:2] + levels(beats(0, 60), instrument=Instrument.BASS)[:2], TEMPO, 60.0)


# ---------------------------------------------------------------- hard rules in code


@pytest.mark.parametrize(
    "phrases,song_start,message",
    [
        ([StarPowerPhrase(100, BAR)], 0, "not on a bar line"),
        ([StarPowerPhrase(2 * BAR, BAR)], 5 * BAR, "before the song"),
        ([StarPowerPhrase(0, 2 * BAR), StarPowerPhrase(BAR, BAR)], 0, "overlap"),
        ([StarPowerPhrase(3 * BAR, BAR)], 0, "holds no note on guitar/easy"),
    ],
)
def test_the_hard_rules_are_held_in_code(phrases, song_start, message):
    tracks = levels(beats(0, 60), easy=[tick for tick in beats(0, 60) if tick // BAR != 3])
    with pytest.raises(StarPowerRuleViolation, match=message):
        check_star_power(phrases, tracks, TEMPO, 60.0, song_start)


def test_four_hard_rules_are_named():
    assert len(HARD_RULES) == 4


@pytest.mark.parametrize(
    "text,message",
    [
        ("[phrases]\nbars = 1\n", "expected keys"),
        ("[phrases]\nbars = 0\nfirst_after_s = 15.0\ngap_s = 25.0\nmin_gap_s = 20.0\nmax_gap_s = 30.0\n"
         "preferred_notes_on_easiest = 2\n[soft_targets]\nper_minute = [1.5, 3.0]\n", "bars must be"),
        ("[phrases]\nbars = 1\nfirst_after_s = 15.0\ngap_s = 25.0\nmin_gap_s = 26.0\nmax_gap_s = 30.0\n"
         "preferred_notes_on_easiest = 2\n[soft_targets]\nper_minute = [1.5, 3.0]\n", "min_gap_s <= gap_s"),
        ("[phrases]\nbars = 1\nfirst_after_s = 15.0\ngap_s = 25.0\nmin_gap_s = 20.0\nmax_gap_s = 30.0\n"
         "preferred_notes_on_easiest = 2\n[soft_targets]\nper_minute = [3.0, 1.5]\n", "low < high"),
        ("[phrases]\nbars = 1\nfirst_after_s = 15.0\ngap_s = 25.0\nmin_gap_s = 20.0\nmax_gap_s = 30.0\n"
         "preferred_notes_on_easiest = 2\nfills = true\n[soft_targets]\nper_minute = [1.5, 3.0]\n", "expected keys"),
    ],
)
def test_the_settings_file_refuses_what_it_does_not_know_or_cannot_use(tmp_path, text, message):
    path = tmp_path / "star_power.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_star_power_config(path)


def test_the_shipped_settings_are_the_approved_ones():
    config = load_star_power_config()
    assert (config.bars, config.min_gap_s, config.max_gap_s) == (1, 20.0, 30.0), "decision 40: one bar, every 20-30 s"


# ---------------------------------------------------------------- the validator


def chart_text(phrases: list[str], events: list[str] = (), signature: str = "4", empty_bars: tuple[int, ...] = ()) -> str:
    notes = [f"  {tick} = N 0 0" for tick in range(0, 12 * BAR, RES) if tick // BAR not in empty_bars]
    body = sorted(notes + [f"  {line}" for line in phrases], key=lambda line: int(line.split("=")[0]))
    return (
        "[Song]\n{\n  Resolution = 192\n}\n"
        f"[SyncTrack]\n{{\n  0 = TS {signature}\n  0 = B 120000\n}}\n"
        "[Events]\n{\n" + "".join(f"  {line}\n" for line in events) + "}\n"
        "[ExpertSingle]\n{\n" + "\n".join(body) + "\n}\n"
    )


def star_power_errors(text: str) -> list[str]:
    return [error for error in validate_chart_text(text)[1].errors if "star power" in error]


def test_the_validator_accepts_phrases_that_keep_the_rules():
    assert star_power_errors(chart_text([f"{BAR} = S 2 {BAR}", f"{5 * BAR} = S 2 {BAR}"])) == []


@pytest.mark.parametrize(
    "phrases,events,signature,empty,message",
    [
        (["100 = S 2 768"], [], "4", (), "is not on a bar line"),
        ([f"{BAR} = S 2 {BAR}"], [], "3", (), "is not on a bar line"),
        ([f"{BAR} = S 2 {BAR}"], [], "4", (1,), "holds no note"),
        ([f"0 = S 2 {2 * BAR}", f"{BAR} = S 2 {BAR}"], [], "4", (), "overlaps the phrase before it"),
        ([f"{BAR} = S 2 {BAR}"], ['0 = E "section Intro"', f'{2 * BAR + RES} = E "section Song"'], "4", (), "starts before the song does"),
        ([f"{BAR} = S 2 0"], [], "4", (), "has no length"),
    ],
)
def test_the_validator_holds_star_power_to_the_rules_on_its_own(phrases, events, signature, empty, message):
    errors = star_power_errors(chart_text(phrases, events, signature, empty))
    assert any(message in error for error in errors), errors


def test_drum_activation_phrases_are_not_star_power_to_the_validator():
    _, report = validate_chart_text(chart_text([f"{BAR + 1} = S 64 {BAR}"]))
    assert not [error for error in report.errors if "star power" in error]
    assert any("unusual special phrase 64" in warning for warning in report.warnings)


# ---------------------------------------------------------------- a build


@pytest.mark.heavy
def test_a_build_gives_every_level_of_an_instrument_the_same_star_power(song_file, tmp_path):
    folder = build_song(
        BuildConfig(
            input_path=song_file,
            metadata=SongMetadata("Yıldız", "Test"),
            instruments=frozenset(Instrument),
            output_dir=tmp_path / "out",
            cache_dir=tmp_path / "cache",
        ),
        FakeSeparator(song_stems()),
    ).folder
    assert validate_song_folder(folder).ok
    text = (folder / "notes.chart").read_text(encoding="utf-8-sig")
    analysis = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
    star_power = analysis["star_power"]
    assert star_power["hard_rules"] == list(HARD_RULES)
    assert {"guitar", "drums"} <= set(star_power["instruments"])
    assert star_power["not_verified_in_game"] == [DRUM_ACTIVATION_NOT_VERIFIED]
    assert "S 64" not in text, "no drum activation fills"
    for instrument, record in star_power["instruments"].items():
        section = {"guitar": "Single", "bass": "DoubleBass", "keys": "Keyboard", "drums": "Drums"}[instrument]
        per_level = []
        for level in ("Expert", "Hard", "Medium", "Easy"):
            block = text.split(f"[{level}{section}]")[1].split("}")[0]
            per_level.append([line.strip() for line in block.splitlines() if " = S " in line])
        assert per_level[0] and all(lines == per_level[0] for lines in per_level), instrument
        assert len(per_level[0]) == record["count"]
        assert [f"{phrase['tick']} = S 2 {phrase['length_ticks']}" for phrase in record["phrases"]] == per_level[0]


# ---------------------------------------------------------------- the real reference


SPARSE_ON_EASY = {Instrument.GUITAR: 1, Instrument.BASS: 0, Instrument.DRUMS: 0}
"""Phrases with fewer than two notes on Easy, at most, as measured on 2026-11-15 (guitar's 11th phrase holds
one: no bar 20 to 30 s after the 10th had two). The human chart has two or more in every phrase."""


@pytest.mark.real
@pytest.mark.parametrize("real_song", [CALIFORNICATION], indirect=True)
def test_californication_star_power_is_spaced_like_the_human_charts(real_song):
    """Californication is train: the settings were chosen with its human chart in view."""
    tempo = real_song.tempo
    human = {instrument: len(phrases) for instrument, phrases in real_song.reference.star_power.items()}
    config = load_star_power_config()
    plans = {}
    for instrument, stem in ((Instrument.GUITAR, "guitar"), (Instrument.BASS, "bass"), (Instrument.DRUMS, "drums")):
        tracks = [
            item.track
            for item in build_tracks_for(
                instrument,
                real_song.mono(stem),
                tempo.tempo_map,
                real_song.stems.duration_s,
                real_song.mono("vocals"),
                tempo.lead_in_end_s,
            )
        ]
        plans[instrument] = plan = place_star_power(tracks, tempo.tempo_map, real_song.stems.duration_s, song_section_tick(tempo))
        print(instrument.value, len(plan.phrases), "phrases, human", human[instrument], "gaps", np.round(plan.gaps_s, 1).tolist(),
              "easy notes", [phrase.notes[-1] for phrase in plan.phrases])
    for instrument, plan in plans.items():
        assert abs(len(plan.phrases) - human[instrument]) <= 2, instrument
        assert config.per_minute[0] <= plan.per_minute <= config.per_minute[1], instrument
        assert all(config.min_gap_s - 1e-6 <= gap <= config.max_gap_s + 1e-6 for gap in plan.gaps_s), instrument
        sparse = sum(phrase.notes[-1] < config.preferred_notes_on_easiest for phrase in plan.phrases)
        assert sparse <= SPARSE_ON_EASY[instrument], instrument
