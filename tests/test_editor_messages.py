"""The validator's messages in plain words (E.2): every message an edit can cause has its own words."""

from __future__ import annotations

from test_editor_ops import levelled, render, run

from chartgen.clonehero.validate import validate_chart_text
from chartgen.core.model import Instrument
from chartgen.editor.messages import explain


def broken_chart_messages() -> list[str]:
    """Edits a level by level chart into every validator error an edit can make."""
    chart = levelled()
    run(chart, "guitar", "easy", {"kind": "add", "notes": [[0, 1]]})  # an Easy chord
    run(chart, "guitar", "medium", {"kind": "add", "notes": [[0, 4], [0, 2]]})  # orange, a chord of 3
    run(chart, "bass", "expert", {"kind": "add", "notes": [[0, 3]]})  # a bass chord
    run(chart, "guitar", "hard", {"kind": "add", "notes": [[48, 1]]}, linked=False)  # Hard without Expert
    guitar = next(t for t in chart.tracks if t.instrument is Instrument.GUITAR and t.difficulty.value == "expert")
    guitar.notes = [n if n.tick != 96 else n.__class__(n.tick, n.lane, 500) for n in guitar.notes]  # runs into the next
    run(chart, "drums", "expert", {"kind": "add", "notes": [[96, 3], [96, 4]]})  # three pads
    run(chart, "drums", "hard", {"kind": "add", "notes": [[192, 3]]}, linked=False)  # three gems on Hard; not on Expert
    run(chart, "drums", "easy", {"kind": "add", "notes": [[384, 0]]}, linked=False)  # the kick with a pad
    run(chart, "drums", "medium", {"kind": "add", "notes": [[48, 1]]}, linked=False)  # a sixteenth; not on Hard
    sp = next(t for t in chart.tracks if t.instrument is Instrument.GUITAR and t.difficulty.value == "hard")
    sp.star_power = [sp.star_power[0].__class__(100, 50), sp.star_power[0].__class__(130, 900)]
    _, report = validate_chart_text(render(chart).decode("utf-8-sig"))
    return report.errors + report.warnings


def test_every_message_an_edit_can_cause_is_put_in_plain_words():
    messages = broken_chart_messages()
    kinds = {
        "a chord of", "orange is not allowed", "has tick", "the sustain runs into", "pads at once", "gems at once",
        "the kick with a pad", "a sixteenth", "is not in [", "star power is not on a bar line", "star power holds no note",
        "star power overlaps",
    }
    for kind in kinds:
        assert any(kind in m for m in messages), f"the broken chart has no {kind!r} message"
    raw = [m for m in messages if explain(m) == m]
    assert raw == [], raw


def test_the_words_name_the_levels():
    assert explain("[HardSingle] has tick 6160, but [ExpertSingle] does not") == (
        "Hard has a note here and Expert has none: every note of a level must also be on the level above it."
    )
    assert explain("[EasySingle] tick 0: a chord of 2 notes") == "A chord of 2 notes: Easy has single notes only."
    assert explain("[MediumSingle] tick 0: a chord of 3 notes") == "A chord of 3 notes: Medium has chords of at most two notes."
    assert explain("[MediumSingle] tick 0: orange is not allowed here") == "Orange on Medium: Medium and Easy have no orange."
    assert explain("[MediumDrums] tick 4: yellow cymbal is not in [HardDrums]") == (
        "The yellow cymbal is not on Hard: every note of a level must also be on the level above it, a cymbal as a cymbal."
    )
    assert explain("guitar has no notes but diff_guitar = 3") == (
        "No guitar notes are left, but song.ini still gives guitar a difficulty (diff_guitar)."
    )
    assert explain("[ExpertSingle] tick 10: a note in the opening that ends at 4.2 s") == (
        "A note in the opening, which is not part of the song (it ends at 4.2 s)."
    )


def test_a_message_no_rule_knows_is_kept_as_it_is():
    assert explain("audio files differ in length: {'song.ogg': 1, 'guitar.ogg': 2}") == (
        "audio files differ in length: {'song.ogg': 1, 'guitar.ogg': 2}"
    )
