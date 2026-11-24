"""``scripts\\check.ps1 -Full`` must not pass when a real song or reference is missing (owner, 2026-11-24).

Such tests skip, naming the file; ``--require-real-files``, which only ``-Full`` passes, turns those skips
into a failed run. Each case runs pytest in a folder of its own, with a copy of this conftest.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = """
import pytest
from conftest import skip_missing


def test_present():
    pass


def test_not_about_a_file():
    pytest.skip("for another reason")
"""

A_MISSING_FILE = """

def test_missing():
    skip_missing("musica/Gone.mp3")
"""


def run_pytest(folder: Path, tests: str, *options: str) -> subprocess.CompletedProcess[str]:
    shutil.copy(Path(__file__).with_name("conftest.py"), folder / "conftest.py")
    (folder / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (folder / "test_songs.py").write_text(tests, encoding="utf-8")
    command = [sys.executable, "-X", "utf8", "-m", "pytest", "-q", "-p", "no:cacheprovider", *options]
    return subprocess.run(command, cwd=folder, capture_output=True, text=True, encoding="utf-8", check=False)


@pytest.mark.heavy
def test_a_missing_file_fails_the_run_when_real_files_are_required(tmp_path):
    result = run_pytest(tmp_path, TESTS + A_MISSING_FILE, "--require-real-files")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "real files missing" in result.stdout
    assert "musica/Gone.mp3: 1 test skipped" in result.stdout
    assert "another reason" not in result.stdout.split("real files missing")[1]
    assert "1 passed, 2 skipped" in result.stdout


@pytest.mark.heavy
def test_other_skips_do_not_fail_the_run(tmp_path):
    result = run_pytest(tmp_path, TESTS, "--require-real-files")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "real files missing" not in result.stdout


@pytest.mark.heavy
def test_without_the_option_a_missing_file_is_listed_and_only_skips(tmp_path):
    """The quick and -Mid checks do not pass the option; they also leave out every real test."""
    result = run_pytest(tmp_path, TESTS + A_MISSING_FILE)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "musica/Gone.mp3: 1 test skipped" in result.stdout
