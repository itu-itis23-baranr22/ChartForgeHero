"""Phase D, D.2, and decision 48: where the song list's preview starts. On the bar line closest to 14 s
before a start of the loudest part that comes back, its first start if that is at least 16 bars into the
song, its second otherwise; without one, the loudest 30 seconds on a bar line. Never in an opening, and the
30 seconds fit in the song."""

import numpy as np
import pytest

from chartgen.audio.io import ANALYSIS_SAMPLERATE
from chartgen.audio.sections import FoundSection, SectionAnalysis
from chartgen.chart.preview import (
    FIRST_START_MIN_BARS,
    LOUDEST_WINDOW,
    PREVIEW_LEAD_S,
    REPEATED_PART,
    PreviewChoice,
    PreviewRuleViolation,
    check_preview,
    choose_preview,
)
from chartgen.clonehero.validate import ValidationReport, _check_preview, validate_chart_text
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent

SR = ANALYSIS_SAMPLERATE
BAR_S = 2.0
TEMPO = TempoMap([TempoEvent(0, 120.0)], [TimeSignatureEvent(0, 4, 4)])
BAR_TICKS = 4 * TEMPO.resolution


def noise(seconds: float, level: float, seed: int) -> np.ndarray:
    return (level * np.random.default_rng(seed).standard_normal(int(round(seconds * SR)))).astype(np.float32)


def parts_song(
    plan: str,
    loudness: dict[str, float],
    bars: int = 8,
    opening_bars: int = 0,
    opening_level: float = 0.0,
    bar_s: float = BAR_S,
) -> tuple[np.ndarray, SectionAnalysis, float]:
    """A song of ``plan``'s parts, ``bars`` bars each, each letter at its own level, after an optional
    opening; and the sections a finder would give it. After an opening the first part is ``Song``'s.
    Bars last ``bar_s`` (``TEMPO``'s by default)."""
    pieces = [noise(opening_bars * bar_s, opening_level, 0)] if opening_bars else []
    parts, counts = [], {}
    for index, letter in enumerate(plan):
        bar = opening_bars + index * bars
        counts[letter] = counts.get(letter, 0) + 1
        parts.append(FoundSection(bar * BAR_TICKS, bar * bar_s, f"{letter}{counts[letter]}", letter, None if index == 0 else 0.3))
        pieces.append(noise(bars * bar_s, loudness[letter], index + 1))
    mix = np.concatenate(pieces)
    duration = mix.size / SR
    if opening_bars:
        found = SectionAnalysis(tuple(parts[1:]), 0.4, 0.18, True, 0.0, parts[0])
    else:
        found = SectionAnalysis(tuple(parts), 0.4, 0.18, False, 0.0)
    return mix, found, duration


def bar_of(choice: PreviewChoice) -> float:
    return choice.tick / BAR_TICKS


# ---------------------------------------------------------------- the part it leads into


def test_the_settings_are_the_approved_ones():
    assert (PREVIEW_LEAD_S, FIRST_START_MIN_BARS) == (14.0, 16)


def test_the_preview_leads_into_the_first_start_of_the_loudest_part_that_comes_back():
    # B1 starts 16 bars into the song; 14 s before it is 7 bars at 120 BPM.
    mix, found, duration = parts_song("AABAB", {"A": 0.05, "B": 0.3})
    choice = choose_preview(found, mix, TEMPO, duration)
    assert (choice.rule, choice.leads_into, choice.lead_bars) == (REPEATED_PART, "B1", 7)
    assert bar_of(choice) == 16 - 7 and choice.start_s == pytest.approx(18.0)
    assert list(choice.loudness_db) == ["B", "A"], "only parts that come back, loudest first"
    assert choice.moved_earlier_bars == 0 and not choice.too_short and choice.fallback_reason is None


def test_a_first_start_early_in_the_song_gives_way_to_the_second():
    # B1 starts 8 bars into the song, too early: the preview leads into B2 (bar 24) instead.
    mix, found, duration = parts_song("ABABC", {"A": 0.05, "B": 0.3, "C": 0.05})
    choice = choose_preview(found, mix, TEMPO, duration)
    assert (choice.leads_into, choice.lead_bars) == ("B2", 7) and bar_of(choice) == 24 - 7
    # One bar short of 16 is still too early.
    mix, found, duration = parts_song("AAABABA", {"A": 0.05, "B": 0.3}, bars=5)
    choice = choose_preview(found, mix, TEMPO, duration)
    assert choice.leads_into == "B2" and bar_of(choice) == 25 - 7


def test_the_lead_is_the_bar_line_closest_to_14_seconds_before():
    # At 100 BPM a bar lasts 2.4 s: 14 s is 5.8 bars, so 6 bars (14.4 s) before B1 at bar 16.
    tempo = TempoMap([TempoEvent(0, 100.0)], [TimeSignatureEvent(0, 4, 4)])
    mix, found, duration = parts_song("AABAB", {"A": 0.05, "B": 0.3}, bar_s=2.4)
    choice = choose_preview(found, mix, tempo, duration)
    assert (choice.leads_into, choice.lead_bars) == ("B1", 6)
    assert choice.start_s == pytest.approx((16 - 6) * 2.4)


def test_a_louder_part_leads_and_the_quieter_one_is_passed_over():
    # A is the first part, so its first start is not 16 bars into the song: A2.
    mix, found, duration = parts_song("ABABC", {"A": 0.3, "B": 0.05, "C": 0.05})
    choice = choose_preview(found, mix, TEMPO, duration)
    assert choice.leads_into == "A2" and bar_of(choice) == 16 - 7


def test_a_loud_part_that_never_comes_back_is_not_chosen():
    mix, found, duration = parts_song("ABACD", {"A": 0.05, "B": 0.05, "C": 0.5, "D": 0.05})
    choice = choose_preview(found, mix, TEMPO, duration)
    assert choice.leads_into == "A2" and list(choice.loudness_db) == ["A"]


def test_the_part_song_starts_counts_as_the_first_of_its_letter():
    # After a quiet opening, Song starts A1; A comes back as A2 and is the only part that does.
    mix, found, duration = parts_song("ABAC", {"A": 0.2, "B": 0.05, "C": 0.05}, opening_bars=6, opening_level=0.01)
    song_tick = 6 * BAR_TICKS + 96
    choice = choose_preview(found, mix, TEMPO, duration, song_start_tick=song_tick)
    assert choice.leads_into == "A2" and bar_of(choice) == 6 + 16 - 7


def test_near_the_end_it_moves_earlier_until_its_30_seconds_fit():
    # B2 starts at 36 s of 48: 14 s before it is 22 s, and 22 + 30 > 48. The last bar line that fits is
    # 18 s, two bars earlier, nine bars before B2.
    mix, found, duration = parts_song("ABAB", {"A": 0.05, "B": 0.3}, bars=6)
    choice = choose_preview(found, mix, TEMPO, duration)
    assert choice.leads_into == "B2" and choice.start_s == pytest.approx(18.0)
    assert choice.moved_earlier_bars == 2 and choice.lead_bars == 9 and choice.start_s + 30 <= duration


# ---------------------------------------------------------------- the loudest window


def test_with_no_part_coming_back_it_is_the_loudest_window_on_a_bar_line():
    mix, found, duration = parts_song("ABCD", {"A": 0.05, "B": 0.3, "C": 0.05, "D": 0.05})
    choice = choose_preview(found, mix, TEMPO, duration)
    assert (choice.rule, choice.fallback_reason, choice.leads_into) == (LOUDEST_WINDOW, "no part comes back", None)
    assert choice.tick % BAR_TICKS == 0
    # The loud part (16 s to 32 s) lies inside the 30 seconds.
    assert choice.start_s <= 16.0 and choice.start_s + 30 >= 32.0


@pytest.mark.parametrize("found", [None, SectionAnalysis((), 0.01, 0.18, False, 0.0)])
def test_without_sections_it_is_the_loudest_window(found):
    mix, _, duration = parts_song("ABCD", {"A": 0.05, "B": 0.05, "C": 0.3, "D": 0.05})
    choice = choose_preview(found, mix, TEMPO, duration)
    assert (choice.rule, choice.fallback_reason) == (LOUDEST_WINDOW, "no sections were found")
    assert choice.start_s <= 32.0 and choice.start_s + 30 >= 48.0


def test_the_loudest_window_is_never_in_the_opening():
    # The opening is far louder than the song, which has no part that comes back; of the song, its
    # first part is loudest, so the window wants to start as early as it may.
    mix, found, duration = parts_song("ABCD", {"A": 0.1, "B": 0.05, "C": 0.05, "D": 0.05}, opening_bars=10, opening_level=0.8)
    song_tick = 10 * BAR_TICKS + 96
    choice = choose_preview(found, mix, TEMPO, duration, song_start_tick=song_tick)
    assert choice.rule == LOUDEST_WINDOW
    assert choice.tick >= song_tick and choice.tick == 11 * BAR_TICKS, "the first bar line of the song"


def test_a_song_shorter_than_the_preview_starts_it_with_the_song():
    mix, found, duration = parts_song("AB", {"A": 0.05, "B": 0.3}, bars=4)
    choice = choose_preview(found, mix, TEMPO, duration)
    assert choice.too_short and choice.tick == 0
    # After an opening, with the song itself shorter than 30 s.
    mix, found, duration = parts_song("AB", {"A": 0.05, "B": 0.3}, bars=4, opening_bars=6, opening_level=0.05)
    choice = choose_preview(found, mix, TEMPO, duration, song_start_tick=6 * BAR_TICKS)
    assert choice.too_short and choice.tick == 6 * BAR_TICKS


def test_choosing_is_deterministic():
    mix, found, duration = parts_song("ABABC", {"A": 0.05, "B": 0.3, "C": 0.05})
    assert choose_preview(found, mix, TEMPO, duration) == choose_preview(found, mix, TEMPO, duration)


# ---------------------------------------------------------------- the hard rules


def choice_at(tick: int) -> PreviewChoice:
    return PreviewChoice(tick, TEMPO.seconds_at(float(tick)), REPEATED_PART, "B2", {}, None, 0, False)


@pytest.mark.parametrize(
    "tick,song_tick,message",
    [
        (BAR_TICKS + 96, 0, "not on a bar line"),
        (4 * BAR_TICKS, 5 * BAR_TICKS, "in the opening"),
        (20 * BAR_TICKS, 0, "do not fit"),
    ],
)
def test_the_rule_check_catches_each_broken_rule(tick, song_tick, message):
    with pytest.raises(PreviewRuleViolation, match=message):
        check_preview(choice_at(tick), TEMPO, 64.0, song_tick)


def test_the_rule_check_lets_a_short_song_start_with_its_preview():
    check_preview(choice_at(6 * BAR_TICKS), TEMPO, 28.0, 6 * BAR_TICKS)
    with pytest.raises(PreviewRuleViolation, match="do not fit"):
        check_preview(choice_at(7 * BAR_TICKS), TEMPO, 28.0, 6 * BAR_TICKS)


# ---------------------------------------------------------------- the validator, on its own


def preview_errors(preview: str, length: int, song_tick: int | None = None) -> list[str]:
    events = f'  0 = E "section Intro"\n  {song_tick} = E "section Song"\n' if song_tick is not None else ""
    text = (
        "[Song]\n{\n  Resolution = 192\n}\n[SyncTrack]\n{\n  0 = TS 4\n  0 = B 120000\n}\n"
        f"[Events]\n{{\n{events}}}\n[ExpertSingle]\n{{\n  0 = N 0 0\n}}\n"
    )
    parsed, _ = validate_chart_text(text)
    report = ValidationReport()
    _check_preview(parsed, {"preview_start_time": preview, "song_length": str(length)}, report)
    return report.errors


def test_the_validator_accepts_a_preview_that_fits_after_the_opening():
    # Song at tick 3840: 10 s at 120 BPM.
    assert preview_errors("12000", 120_000, song_tick=3840) == []
    assert preview_errors("90000", 120_000) == []


@pytest.mark.parametrize(
    "preview,length,song_tick,message",
    [
        ("8000", 120_000, 3840, "in the opening"),
        ("100000", 120_000, None, "do not fit"),
        ("130000", 120_000, None, "past the song's end"),
        ("soon", 120_000, None, "not a whole number"),
    ],
)
def test_the_validator_catches_a_misplaced_preview(preview, length, song_tick, message):
    errors = preview_errors(preview, length, song_tick)
    assert any(message in error for error in errors), errors


def test_the_validator_lets_be_an_unset_preview_and_a_short_song():
    assert preview_errors("-1", 120_000) == []
    assert preview_errors("10000", 30_000, song_tick=3840) == [], "20 s of song after the opening"
