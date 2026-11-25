"""The editor's playback in a real browser (SPEC 53, 57): measured with Playwright 1.65.1 in Chromium.

A synthetic song with tempo changes, odd metres and click stems is served by the editor's own server; the page
renders it offline with its own modules and Python checks where every click landed against the chart's beats
(``click_overlay.click_schedule`` on the written chart): the metronome and the click stems within 1 ms, at 1x
and 0.5x, at 44.1 and 48 kHz, through seeks and speed changes. Live, every drawn frame's playhead must come
from the audio clock and stay within one frame of it; the same run is the smoke test (list, open, play, seek,
speed, pause, no console errors).

Needs Node.js and ``npm ci`` in ``tests/browser`` (Playwright and its Chromium); under ``-Full`` a missing one
fails the run like a missing song file.
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from conftest import SR, clicks_at, sine, skip_missing, stereo

pytest.importorskip("fastapi")
uvicorn = pytest.importorskip("uvicorn")

from chartgen.clonehero.chart_format import DotChartExporter  # noqa: E402
from chartgen.clonehero.click_overlay import click_schedule, tempo_map_from_chart  # noqa: E402
from chartgen.clonehero.package import encode_ogg  # noqa: E402
from chartgen.clonehero.song_ini import SongIni, render_song_ini  # noqa: E402
from chartgen.core.model import Chart, ChartNote, Difficulty, Instrument, Section, SongMetadata, Track  # noqa: E402
from chartgen.core.timing import TempoEvent, TempoMap, TimeSignatureEvent  # noqa: E402
from chartgen.editor.server import create_app  # noqa: E402
from chartgen.editor.songs import SongLibrary  # noqa: E402

pytestmark = pytest.mark.heavy

ROOT = Path(__file__).resolve().parents[1]
BROWSER = ROOT / "tests" / "browser"
TITLE = "Click Sheet"
FOLDER = f"Sync Test - {TITLE}"
SECONDS = 45.0
LEAD = 0.05  # audio.js LEAD: a start, seek or speed change takes effect this long after it is asked for
TOLERANCE = 0.001  # SPEC 53: within 1 ms of the chart's beats
THRESHOLD = 0.1
REFRACTORY = 0.045
"""Onset finding: the first sample at or above THRESHOLD after REFRACTORY seconds below it. The clicks are
decaying bursts at 0.45 to 0.8, so the threshold is crossed within a few samples of a click's start."""


def tempo_map() -> TempoMap:
    """Fractional tempos, a tempo change in mid-bar, and 2/4, 4/4, 6/8, 7/8 and 3/4."""
    return TempoMap(
        [
            TempoEvent(0, 156.654),
            TempoEvent(192, 171.244),
            TempoEvent(3456, 181.194),
            TempoEvent(9984, 120.19),
            TempoEvent(14592, 97.531),
        ],
        [
            TimeSignatureEvent(0, 2),
            TimeSignatureEvent(384, 4),
            TimeSignatureEvent(6528, 6, 8),
            TimeSignatureEvent(8832, 7, 8),
            TimeSignatureEvent(10176, 3),
        ],
    )


def make_sync_song(outputs: Path) -> tuple[Path, list[tuple[float, bool]]]:
    """Writes the song folder and returns the beats the clicks were placed on, read back from its chart."""
    folder = outputs / FOLDER
    folder.mkdir(parents=True)
    tempo = tempo_map()
    bars = tempo.bar_lines(SECONDS - 1).tolist()
    guitar = Track(Instrument.GUITAR, Difficulty.EXPERT, [ChartNote(int(t), i % 5) for i, t in enumerate(bars[1:])])
    chart = Chart(SongMetadata(TITLE, "Sync Test", charter="chartgen"), tempo, [guitar], [Section(0, "Intro")])
    DotChartExporter().export(chart, folder)
    (folder / "song.ini").write_text(
        render_song_ini(SongIni(chart.metadata, int(SECONDS * 1000), 0, 0, {Instrument.GUITAR: 2})),
        encoding="utf-8",
        newline="\n",
    )
    # What the page reads is the written chart, so the clicks come from reading it back too.
    schedule = click_schedule(tempo_map_from_chart((folder / "notes.chart").read_text(encoding="utf-8-sig")), SECONDS)
    beats = [(float(s), bool(d)) for s, d in zip(schedule.times, schedule.is_downbeat)]
    every = np.array([s for s, _ in beats])
    downbeats = np.array([s for s, d in beats if d])
    encode_ogg(stereo(clicks_at(every, SECONDS)), SR, folder / "drums.ogg")
    encode_ogg(stereo(clicks_at(downbeats, SECONDS)), SR, folder / "guitar.ogg")
    encode_ogg(stereo(sine(220, SECONDS, amp=0.02)), SR, folder / "song.ogg")
    return folder, beats


def onsets(samples: np.ndarray, samplerate: int) -> np.ndarray:
    """The same onset finding as sync.mjs, for checking the encoded files themselves."""
    loud = np.flatnonzero(np.abs(samples) >= THRESHOLD)
    if not len(loud):
        return np.array([])
    starts = loud[np.concatenate(([True], np.diff(loud) > round(REFRACTORY * samplerate)))]
    return starts / samplerate


@pytest.fixture(scope="module")
def node() -> str:
    path = shutil.which("node")
    if path is None:
        skip_missing("node (Node.js on PATH) for the browser tests")
    if not (BROWSER / "node_modules" / "playwright").is_dir():
        skip_missing(f"Playwright for the browser tests (run: npm ci --prefix {BROWSER})")
    return path


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@contextmanager
def serve(outputs: Path | None, port: int | None = None, app=None) -> Iterator[str]:
    """The editor's server (or ``app``) on 127.0.0.1, for the song folders in ``outputs``; yields its URL."""
    port = port or free_port()
    app = app or create_app(SongLibrary(outputs))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 20
    while not server.started:
        if time.monotonic() > deadline or not thread.is_alive():
            pytest.fail("the editor's server did not start")
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


@pytest.fixture(scope="module")
def served(tmp_path_factory: pytest.TempPathFactory):
    """The editor's server serving one synthetic song."""
    outputs = tmp_path_factory.mktemp("sync") / "outputs"
    folder, beats = make_sync_song(outputs)
    with serve(outputs) as url:
        yield {"url": url, "folder": folder, "beats": beats}


def run_browser(node: str, plan: dict, tmp_path: Path, script: str = "sync.mjs") -> dict:
    path = tmp_path / f"{plan['mode']}_plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    result = subprocess.run(
        [node, str(BROWSER / script), str(path)],
        cwd=BROWSER, capture_output=True, text=True, encoding="utf-8", timeout=600, check=False,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-4000:]
    return json.loads(result.stdout)


# ---------------------------------------------------------------- the song itself


def test_the_click_stems_hold_their_clicks_where_the_chart_has_its_beats(served):
    """Ogg Vorbis keeps the clicks' starts: otherwise the browser measurement would measure the encoder."""
    beats = served["beats"]
    for file, expected in (("drums.ogg", [s for s, _ in beats]), ("guitar.ogg", [s for s, d in beats if d])):
        samples, samplerate = sf.read(str(served["folder"] / file), dtype="float32")
        found = onsets(samples[:, 0], samplerate)
        assert len(found) == len(expected), file
        assert np.max(np.abs(found - np.array(expected))) < 0.00025, file


# ---------------------------------------------------------------- offline renders

# Song times to seek to sit between beats, so that no click falls on a segment's first sample.
CASES = [
    {"name": "44.1 kHz, 1x", "sampleRate": 44100, "rate": 1, "from": 0.0, "seconds": 18,
     "actions": [{"at": 6.0, "seek": 21.337}, {"at": 12.0, "seek": 3.213}]},
    {"name": "44.1 kHz, 0.5x", "sampleRate": 44100, "rate": 0.5, "from": 0.0, "seconds": 18,
     "actions": [{"at": 6.0, "seek": 21.337}, {"at": 12.0, "seek": 33.117}]},
    {"name": "48 kHz, 1x", "sampleRate": 48000, "rate": 1, "from": 1.111, "seconds": 18,
     "actions": [{"at": 6.0, "seek": 28.871}, {"at": 12.0, "seek": 3.213}]},
    {"name": "48 kHz, 0.5x", "sampleRate": 48000, "rate": 0.5, "from": 0.0, "seconds": 18,
     "actions": [{"at": 6.0, "seek": 15.517}, {"at": 12.0, "seek": 37.07}]},
    {"name": "48 kHz, speed changes", "sampleRate": 48000, "rate": 1, "from": 0.0, "seconds": 18,
     "actions": [{"at": 5.0, "rate": 0.5}, {"at": 10.0, "seek": 30.031}, {"at": 14.0, "rate": 0.75}]},
]
SOURCES = ["metronome", "drums.ogg", "guitar.ogg"]


def expected_clicks(result: dict, beats: list[tuple[float, bool]]) -> tuple[list[float], list[float]]:
    """The render times each beat must sound at under the player's segments, and the segment boundaries."""
    source = result["source"]
    times = [s for s, d in beats if d or source != "guitar.ogg"]
    end_of_audio = result["durations"].get(source, float("inf"))
    segments = result["segments"]
    expected = []
    bounds = [segment["ctx"] for segment in segments] + [result["seconds"]]
    for k, segment in enumerate(segments):
        stop = bounds[k + 1]
        for s in times:
            if s < segment["song"] or s >= end_of_audio:
                continue
            when = segment["ctx"] + (s - segment["song"]) / segment["rate"]
            if when < stop - 0.002:  # a click due right at the next segment is cut there
                expected.append(when)
    return expected, bounds


def match(expected: list[float], found: list[float], bounds: list[float]) -> dict:
    found_array = np.array(found)
    errors, missing = [], []
    used = set()
    for when in expected:
        i = int(np.argmin(np.abs(found_array - when))) if len(found_array) else -1
        if i < 0 or abs(found_array[i] - when) > 0.02:
            missing.append(when)
            continue
        used.add(i)
        errors.append(float(found_array[i] - when))
    extra = [f for i, f in enumerate(found) if i not in used and min(abs(f - b) for b in bounds) > 0.003]
    return {"errors": errors, "missing": missing, "extra": extra}


def test_metronome_and_click_stems_land_on_the_chart_beats_offline(served, node, tmp_path):
    plan = {
        "mode": "offline", "url": served["url"], "song": FOLDER, "files": ["drums.ogg", "guitar.ogg", "song.ogg"],
        "cases": [{**case, "sources": SOURCES} for case in CASES], "threshold": THRESHOLD, "refractory": REFRACTORY,
    }
    out = run_browser(node, plan, tmp_path)
    assert not out["problems"], out["problems"]
    assert len(out["results"]) == len(CASES) * len(SOURCES)
    lines, failures = [], []
    for result in out["results"]:
        case = next(c for c in CASES if c["name"] == result["name"])
        assert result["sampleRate"] == case["sampleRate"]
        segments = result["segments"]
        # The plan, as the player carried it out: every start LEAD after it was asked for, seeks where asked.
        assert segments[0]["ctx"] == pytest.approx(LEAD, abs=1e-9) and segments[0]["song"] == pytest.approx(case["from"])
        assert len(segments) == 1 + len(case["actions"])
        for segment, action in zip(segments[1:], result["actions"]):
            assert segment["ctx"] == pytest.approx(action["at"] + LEAD, abs=1e-9)
            assert action["when"] == pytest.approx(segment["ctx"], abs=1e-12)
            if "seek" in action:
                assert segment["song"] == pytest.approx(action["seek"], abs=1e-9)
            else:
                assert segment["rate"] == action["rate"]
        expected, bounds = expected_clicks(result, served["beats"])
        found = match(expected, result["onsets"], bounds)
        worst = max((abs(e) for e in found["errors"]), default=float("nan"))
        lines.append(
            f"{result['name']:<24} {result['source']:<10} {len(found['errors']):>3} clicks, "
            f"worst {worst * 1000:.3f} ms, mean {np.mean(found['errors']) * 1000:+.3f} ms, "
            f"missing {len(found['missing'])}, extra {len(found['extra'])}"
        )
        if found["missing"] or found["extra"] or not found["errors"] or worst > TOLERANCE:
            failures.append(lines[-1] + f" (missing at {found['missing'][:5]}, extra at {found['extra'][:5]})")
    print("\n" + "\n".join(lines))
    assert not failures, "\n".join(failures)


# ---------------------------------------------------------------- live


def song_at(segments: list[dict], ctx_time: float) -> float:
    segment = segments[0]
    for s in segments:
        if s["ctx"] <= ctx_time:
            segment = s
    return segment["song"] + max(0.0, ctx_time - segment["ctx"]) * segment["rate"]


def test_the_page_plays_and_its_playhead_follows_the_audio_clock(served, node, tmp_path):
    plan = {"mode": "live", "url": served["url"], "song": FOLDER, "title": TITLE, "liveSeconds": 2.5}
    out = run_browser(node, plan, tmp_path)
    steps = "\n".join(out["steps"])
    assert not out["problems"], out["problems"]
    assert out["audio"]["status"] == "ready", steps
    assert "playing after Space: true" in steps and "paused by the play button: true" in steps, steps
    frames = out["frames"]
    segments = out["segments"]
    assert len(segments) == 3, segments  # play, the seek from the ruler, the speed change
    assert segments[2]["rate"] == 0.5
    assert len(frames) > 200, f"only {len(frames)} frames drawn"
    # Every drawn playhead is the audio clock's song time at the time being heard, less the latency setting.
    for frame in frames:
        assert frame["playhead"] == pytest.approx(song_at(segments, frame["heard"] - frame["latency"] / 1000), abs=1e-9)
    # The time being heard is read from the output timestamp each frame; it stays a constant output
    # latency behind the context's own clock, wobbling by less than one frame.
    frame_s = float(np.median(np.diff([f["at"] for f in frames]))) / 1000
    behind = np.array([f["contextTime"] - f["heard"] for f in frames[10:]])
    wobble = float(np.max(np.abs(behind - np.median(behind))))
    print(
        f"\nlive: {len(frames)} frames of {frame_s * 1000:.1f} ms, heard {np.median(behind) * 1000:.1f} ms behind "
        f"the context clock (output latency {out['outputLatency'] * 1000:.0f} ms, base {out['baseLatency'] * 1000:.0f} ms), "
        f"wobble at most {wobble * 1000:.2f} ms, {out['sampleRate']} Hz context\n{steps}"
    )
    assert wobble <= frame_s, f"the playhead's clock wobbles {wobble * 1000:.2f} ms, more than a frame"
