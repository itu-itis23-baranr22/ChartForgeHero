"""Editing in a real browser (E.2): Playwright 1.65.1 drives the editor's page in Chromium.

The smoke test draws, selects, deletes, undoes, drags, draws a sustain, box-selects, turns a cymbal into a
tom and breaks a level rule on purpose, on a small synthetic song with Expert and Hard; Python checks what
the chart and the page show after each step. The timing test moves a note of a real song (LastResort) with
the arrow keys and checks that each request takes less than 30 ms as the browser sees it.

Needs Node.js and ``npm ci`` in ``tests/browser``, like the sync tests; under ``-Full`` a missing one fails.
"""

from __future__ import annotations

import shutil
import statistics
from pathlib import Path

import numpy as np
import pytest
from conftest import SR, sine, skip_missing, stereo

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

from test_editor_sync import node, run_browser, serve  # noqa: E402, F401  (node is a fixture)

from chartgen.clonehero.chart_format import DotChartExporter  # noqa: E402
from chartgen.clonehero.package import encode_ogg  # noqa: E402
from chartgen.clonehero.song_ini import SongIni, render_song_ini  # noqa: E402
from chartgen.core.model import Chart, ChartNote, Difficulty, Instrument, Section, SongMetadata, Track  # noqa: E402
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent  # noqa: E402

pytestmark = pytest.mark.heavy

TITLE = "Edit Sheet"
FOLDER = f"Edit Test - {TITLE}"
BAR = 768  # 4/4 at 192 ticks a beat
BEAT = BAR // 4
SECONDS = 34.0
OUTPUTS = Path(__file__).resolve().parents[1] / "outputs"


def make_edit_song(outputs: Path) -> Path:
    """16 bars at 120 BPM. Guitar Expert on beats 1 and 3 of bars 2-15, Hard on beat 1; drums Expert and Hard
    a kick and a yellow cymbal on every beat 1."""
    folder = outputs / FOLDER
    folder.mkdir(parents=True)
    expert = []
    hard = []
    drums = []
    for i in range(1, 15):
        expert += [ChartNote(i * BAR, i % 5), ChartNote(i * BAR + 2 * BEAT, (i + 2) % 5)]
        hard.append(ChartNote(i * BAR, i % 5))
        drums += [ChartNote(i * BAR, 0), ChartNote(i * BAR, 2, cymbal=True)]
    tracks = [
        Track(Instrument.GUITAR, Difficulty.EXPERT, expert),
        Track(Instrument.GUITAR, Difficulty.HARD, hard),
        Track(Instrument.DRUMS, Difficulty.EXPERT, drums),
        Track(Instrument.DRUMS, Difficulty.HARD, list(drums)),
    ]
    tempo = TempoMap([TempoEvent(0, 120.0)], [TimeSignatureEvent(0, 4)])
    chart = Chart(SongMetadata(TITLE, "Edit Test", charter="chartgen"), tempo, tracks, [Section(0, "Intro")])
    DotChartExporter().export(chart, folder)
    ini = SongIni(chart.metadata, int(SECONDS * 1000), 0, 0, {Instrument.GUITAR: 2, Instrument.DRUMS: 2})
    (folder / "song.ini").write_text(render_song_ini(ini), encoding="utf-8", newline="\n")
    quiet = stereo(sine(220, SECONDS, amp=0.02))
    encode_ogg(quiet, SR, folder / "song.ogg")
    encode_ogg(np.copy(quiet), SR, folder / "guitar.ogg")
    return folder


def test_editing_in_the_browser(node, tmp_path):  # noqa: F811
    outputs = tmp_path / "outputs"
    make_edit_song(outputs)
    with serve(outputs) as url:
        out = run_browser(node, {"mode": "smoke", "url": url, "title": TITLE, "barTicks": BAR}, tmp_path, "edit.mjs")
    assert not out["problems"], out["problems"]

    # Draw: a yellow note on bar 3, beat 2, selected; one unsaved edit.
    assert [2 * BAR + BEAT, 2, 0, 0] in out["drawn"]["expert"]
    assert out["drawn"]["selection"] == [f"{2 * BAR + BEAT}:2"]
    assert out["drawn"]["unsaved"] == "1 unsaved edit"
    # Select, delete, undo.
    assert out["selected"] == [f"{2 * BAR + BEAT}:2"]
    assert [2 * BAR + BEAT, 2, 0, 0] not in out["deleted"]
    assert [2 * BAR + BEAT, 2, 0, 0] in out["undone"]["expert"]
    assert out["undone"]["notice"] == "Undid: Delete a note"
    # Drag one eighth to the right; Hard follows and is ringed for a moment.
    moved = 3 * BAR + BEAT // 2
    assert [moved, 3, 0, 0] in out["dragged"]["expert"] and [3 * BAR, 3, 0, 0] not in out["dragged"]["expert"]
    assert [moved, 3, 0, 0] in out["dragged"]["hard"] and [3 * BAR, 3, 0, 0] not in out["dragged"]["hard"]
    assert out["dragged"]["notice"] == "Also changed: Hard 1 note"
    assert out["dragged"]["flashes"] == 1
    # A sustain drawn over two beats is cut at the note on beat 3.
    assert [4 * BAR + BEAT, 1, BEAT, 0] in out["sustain"]["expert"]
    assert "cut to end on the next note" in out["sustain"]["notice"]
    # A box over bars 6 and 7 takes their four notes.
    assert out["boxed"] == sorted(f"{t}:{lane}" for t, lane in [(5 * BAR, 0), (5 * BAR + 2 * BEAT, 2), (6 * BAR, 1), (6 * BAR + 2 * BEAT, 3)])
    # The cymbal key makes the yellow cymbal a tom, on Hard too.
    assert out["drumSelected"] == [f"{BAR}:2"]
    assert [BAR, 2, 0, 0] in out["drums"]["expert"] and [BAR, 2, 0, 0] in out["drums"]["hard"]
    # The level rule broken on purpose shows in the problem list, in plain words and with its place.
    assert out["linkedOff"].split() == ["Other", "levels", "Off"]
    assert "Hard has a note here and Expert has none" in out["problemList"]
    assert "Bar 9.2 · Hard guitar" in out["problemList"]
    assert out["problemListAfterUndo"].startswith("Problems") and "none" in out["problemListAfterUndo"]
    # draw, delete, undo, drag, sustain, cymbal, the Hard note, undo
    assert out["unsaved"] == "4 unsaved edits"
    print(f"\nbrowser round trips (ms): {', '.join(f'{t:.0f}' for t in out['timings'])}")


@pytest.mark.real
def test_an_edit_on_a_real_song_takes_less_than_30_ms_in_the_browser(node, tmp_path):  # noqa: F811
    source = OUTPUTS / "Davul Testi - LastResort"
    if not (source / "notes.chart").is_file():
        skip_missing(source / "notes.chart")
    folder = tmp_path / "outputs" / source.name
    folder.mkdir(parents=True)
    for name in ("notes.chart", "song.ini", "analysis.json", "song.ogg"):
        shutil.copy2(source / name, folder / name)
    with serve(folder.parent) as url:
        out = run_browser(node, {"mode": "timing", "url": url, "title": "LastResort", "moves": 20}, tmp_path, "edit.mjs")
    assert not out["problems"], out["problems"]
    timings = sorted(out["timings"])
    assert len(timings) == 20, timings
    median = statistics.median(timings)
    p90 = timings[int(0.9 * len(timings))]
    print(
        f"\nLastResort in the browser: median {median:.1f} ms, 90th percentile {p90:.1f} ms, slowest {timings[-1]:.1f} ms"
        f"\nin order (ms): {', '.join(f'{t:.0f}' for t in out['timings'])}"
    )
    assert median < 30 and p90 < 30, timings
