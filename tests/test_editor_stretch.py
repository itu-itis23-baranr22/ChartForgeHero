"""Keep pitch on the server (E.4.1 a, SPEC 53): a speed the page does not offer is refused, a stretched copy is made
once (in a child process) and read from the cache after, it lasts the song's length over the speed, audio that
cannot be read is refused, and the cache is not a song."""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pytest
import soundfile as sf

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("librosa")

from fastapi.testclient import TestClient  # noqa: E402
from test_editor_save import SONG, make_song  # noqa: E402

from chartgen.clonehero.package import encode_ogg  # noqa: E402
from chartgen.editor.server import create_app  # noqa: E402
from chartgen.editor.songs import SongLibrary  # noqa: E402
from chartgen.editor.stretch import CACHE_DIR  # noqa: E402

SR = 44100
SECONDS = 3.0


@pytest.fixture
def outputs(tmp_path: Path) -> Path:
    outputs = tmp_path / "outputs"
    folder = make_song(outputs)
    t = np.arange(int(SECONDS * SR)) / SR
    tone = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    encode_ogg(np.stack([tone, tone], axis=1), SR, folder / "guitar.ogg")
    return outputs


@pytest.fixture
def client(outputs: Path) -> TestClient:
    return TestClient(create_app(SongLibrary(outputs), draft_delay_s=60), base_url="http://127.0.0.1:8765")


def audio(file_name: str, speed: float) -> str:
    return f"/api/songs/{quote(SONG, safe='')}/audio/{file_name}?keep_pitch={speed}"


def test_a_speed_the_page_does_not_offer_is_refused(client, outputs):
    response = client.get(audio("guitar.ogg", 0.65))
    assert response.status_code == 422
    assert "0.65" in response.json()["error"] and "0.75x" in response.json()["error"]
    assert not (outputs / CACHE_DIR).exists()


def test_the_stretched_copy_is_made_once_and_lasts_longer(client, outputs):
    first = client.get(audio("guitar.ogg", 0.5))
    assert first.status_code == 200 and first.headers["content-type"] == "audio/ogg"
    samples, samplerate = sf.read(io.BytesIO(first.content), always_2d=True)
    assert samplerate == SR and samples.shape[1] == 1  # mono (stretch.py says why)
    assert abs(len(samples) / SR - SECONDS / 0.5) < 0.05
    cached = list((outputs / CACHE_DIR / "stretch").glob("*.ogg"))
    assert len(cached) == 1
    made = cached[0].stat().st_mtime_ns
    again = client.get(audio("guitar.ogg", 0.5))
    assert again.content == first.content and cached[0].stat().st_mtime_ns == made
    assert list((outputs / CACHE_DIR / "stretch").glob("*.ogg")) == cached
    # the cache folder is not a song
    assert [s["id"] for s in client.get("/api/songs").json()["songs"]] == [SONG]


def test_audio_that_cannot_be_read_is_refused_and_leaves_nothing(client, outputs):
    (outputs / SONG / "guitar.ogg").write_bytes(b"not audio at all")
    response = client.get(audio("guitar.ogg", 0.5))
    assert response.status_code == 422 and response.json()["error"].startswith("guitar.ogg cannot be read")
    assert [p.name for p in (outputs / CACHE_DIR / "stretch").iterdir()] == []


@pytest.mark.heavy  # two Python processes and a librosa import: about 6 s
def test_the_stretch_runs_outside_the_editors_process(outputs, tmp_path):
    # librosa (with scipy and numba) in the editor's heap made full garbage collections stall edits
    script = (
        "import sys; from pathlib import Path; from chartgen.editor.stretch import stretched; "
        f"stretched(Path(sys.argv[1]), 0.5, Path(sys.argv[2])); print(sorted(m for m in ('librosa', 'numba') if m in sys.modules))"
    )
    done = subprocess.run([sys.executable, "-X", "utf8", "-c", script, str(outputs / SONG / "guitar.ogg"), str(tmp_path / "cache")],
                          capture_output=True, text=True, check=True)
    assert done.stdout.strip() == "[]"
    assert len(list((tmp_path / "cache").glob("*.ogg"))) == 1
