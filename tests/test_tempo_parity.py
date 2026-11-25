"""The page converts ticks and seconds itself (chartgen/editor/static/tempo.js). This keeps it equal to Python's
TempoMap: the values here are the fixture tests/js/tempo.test.mjs checks the JavaScript against (SPEC 57).

Regenerate the fixture after a deliberate change to TempoMap with CHARTGEN_WRITE_FIXTURES=1.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from conftest import skip_missing

from chartgen.clonehero.chart_reader import read_chart_file
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "js" / "tempo_fixture.json"
JS_TEST = ROOT / "tests" / "js" / "tempo.test.mjs"

SYNTHETIC = [
    ("steady 120", TempoMap([TempoEvent(0, 120.0)]), 30.0),
    (
        "LastResort-like opening",
        TempoMap(
            [TempoEvent(0, 156.654), TempoEvent(192, 171.244), TempoEvent(3456, 180.102), TempoEvent(10752, 181.194)],
            [TimeSignatureEvent(0, 2), TimeSignatureEvent(384, 4)],
        ),
        120.0,
    ),
    (
        "odd meters and a slow fractional tempo",
        TempoMap(
            [TempoEvent(0, 81.3), TempoEvent(100, 119.0), TempoEvent(4000, 97.531)],
            [TimeSignatureEvent(0, 4), TimeSignatureEvent(1536, 6, 8), TimeSignatureEvent(3840, 7, 8), TimeSignatureEvent(5184, 3)],
        ),
        90.0,
    ),
    ("resolution 480", TempoMap([TempoEvent(0, 90.8), TempoEvent(5760, 92.0)], resolution=480), 60.0),
]


def case(name: str, tempo_map: TempoMap, end_s: float) -> dict[str, object]:
    end_tick = float(tempo_map.ticks_at(end_s))
    ticks = sorted({0.0, 1.0, 95.5, *np.linspace(0, end_tick, 37).round(3).tolist(), *[float(t.tick) for t in tempo_map.tempos]})
    seconds = np.linspace(0, end_s, 41).round(4).tolist()
    return {
        "name": name,
        "resolution": tempo_map.resolution,
        "tempos": [[t.tick, t.bpm] for t in tempo_map.tempos],
        "signatures": [[s.tick, s.numerator, s.denominator] for s in tempo_map.time_signatures],
        "end_s": end_s,
        "seconds_at": [[t, float(tempo_map.seconds_at(t))] for t in ticks],
        "ticks_at": [[s, float(tempo_map.ticks_at(s))] for s in seconds],
        "bar_lines": tempo_map.bar_lines(end_s).tolist(),
    }


def synthetic_cases() -> list[dict[str, object]]:
    return [case(*item) for item in SYNTHETIC]


def test_the_fixture_matches_python():
    cases = synthetic_cases()
    if os.environ.get("CHARTGEN_WRITE_FIXTURES"):
        FIXTURE.write_text(json.dumps(cases, indent=1) + "\n", encoding="utf-8")
    assert json.loads(FIXTURE.read_text(encoding="utf-8")) == cases, "TempoMap changed: regenerate with CHARTGEN_WRITE_FIXTURES=1"


@pytest.mark.real
def test_the_page_agrees_with_python_on_every_song_in_outputs(tmp_path):
    folders = sorted(p for p in (ROOT / "outputs").glob("*/notes.chart") if not p.parent.name.startswith("_"))
    if not folders:
        skip_missing(f"song folders in {ROOT / 'outputs'}")
    node = shutil.which("node")
    if node is None:
        skip_missing("node (Node.js on PATH)")
    cases = []
    for path in folders:
        tempo_map = read_chart_file(path).tempo_map
        end_s = float(tempo_map.seconds_at(float(tempo_map.tempos[-1].tick))) + 240.0
        cases.append(case(path.parent.name, tempo_map, end_s))
    fixture = tmp_path / "tempo_outputs.json"
    fixture.write_text(json.dumps(cases), encoding="utf-8")
    result = subprocess.run(
        [node, "--test", str(JS_TEST)],
        env={**os.environ, "CHARTGEN_TEMPO_FIXTURE": str(fixture)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
