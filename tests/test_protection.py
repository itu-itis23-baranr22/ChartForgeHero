"""Hand edits are never lost silently (SPEC 55, E.3.0): the build's chart hash, ``build --force`` refusing an
edited folder, ``--discard-edits``, and ``chartgen protect --record`` for folders built before."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from conftest import FakeSeparator, song_stems
from test_pipeline import config

from chartgen.cli import main
from chartgen.clonehero.protection import (
    EDIT_MARK,
    EDITED,
    HASH_KEY,
    NOT_RECORDED,
    PROTECTED,
    dump_analysis,
    file_sha256,
    hand_edits,
    record,
    state,
)
from chartgen.pipeline import EDITED_BACKUP_DIR, HandEditsError, build_song
from chartgen.protect import DIFFERENT, NO_INPUT, RECORDED, find_input, record_folder, song_folders


def folder_digest(folder: Path) -> dict[str, str]:
    """Every file of a folder and its hash: what must not change when a rebuild is refused."""
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob("*")) if p.is_file()}


def fake_folder(root: Path, chart: str = "chart", analysis: dict | None = None) -> Path:
    folder = root / "Artist - Song"
    folder.mkdir(parents=True)
    (folder / "notes.chart").write_text(chart, encoding="utf-8")
    if analysis is not None:
        (folder / "analysis.json").write_text(dump_analysis(analysis), encoding="utf-8")
    return folder


@pytest.fixture
def built(song_file, tmp_path):
    """One build of the fake song; its separator is reused so that rebuilds come from the same stems."""
    separator = FakeSeparator(song_stems())
    folder = build_song(config(song_file, tmp_path), separator).folder
    return folder, separator


# ---------------------------------------------------------------- what counts as edited


def test_a_folder_is_edited_by_the_editors_mark_or_by_a_changed_chart(tmp_path):
    folder = fake_folder(tmp_path, analysis={"input": {}})
    assert state(folder) == (NOT_RECORDED, None)
    record(folder, file_sha256(folder / "notes.chart"))
    assert state(folder) == (PROTECTED, None)
    (folder / "notes.chart").write_text("chart, changed by another tool", encoding="utf-8")
    status, reason = state(folder)
    assert status == EDITED and "not the one the build wrote" in reason
    (folder / "notes.chart").write_text("chart", encoding="utf-8")
    (folder / EDIT_MARK).write_text("{}", encoding="utf-8")
    assert state(folder)[0] == EDITED and EDIT_MARK in hand_edits(folder)


def test_recording_adds_only_the_hash_to_analysis_json(tmp_path):
    analysis = {"schema_version": 1, "input": {"file_name": "a.wav", "sha256": "0" * 64}, "tempo": {"bpm": 120.123456789}, "warnings": ["ş"]}
    folder = fake_folder(tmp_path, analysis=analysis)
    before = (folder / "analysis.json").read_text(encoding="utf-8")
    record(folder, "ab" * 32)
    after = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
    assert after == {**analysis, HASH_KEY: "ab" * 32}
    assert (folder / "analysis.json").read_text(encoding="utf-8").startswith(before[:-2])
    assert not list(folder.glob(".*.tmp"))


# ---------------------------------------------------------------- the build


def test_a_build_records_its_charts_hash(built):
    folder, _ = built
    analysis = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
    assert analysis[HASH_KEY] == file_sha256(folder / "notes.chart")
    assert state(folder) == (PROTECTED, None)


@pytest.mark.heavy
@pytest.mark.parametrize("edit", ["editor", "other tool"])
def test_force_refuses_an_edited_folder_and_leaves_it_as_it_was(song_file, tmp_path, built, edit):
    folder, separator = built
    if edit == "editor":
        (folder / EDIT_MARK).write_text("[]", encoding="utf-8")
    else:
        chart = folder / "notes.chart"
        chart.write_bytes(chart.read_bytes().replace(b"N 0 0", b"N 1 0", 1))
    before = folder_digest(folder)
    with pytest.raises(HandEditsError, match="has hand edits .*--discard-edits"):
        build_song(config(song_file, tmp_path, force=True), separator)
    assert folder_digest(folder) == before
    out = tmp_path / "out"
    assert sorted(p.name for p in out.iterdir()) == [folder.name]  # no backup, no half-built folder


@pytest.mark.heavy
def test_the_cli_says_why_and_exits_with_an_error(song_file, tmp_path, built, caplog, monkeypatch):
    folder, separator = built
    (folder / EDIT_MARK).write_text("[]", encoding="utf-8")
    monkeypatch.setattr("chartgen.audio.separation.DemucsSeparator", lambda device="auto": separator)
    args = ["build", str(song_file), "--artist", "Sanatçı", "--title", "Şarkı", "--genre", "Rock",
            "--output-dir", str(tmp_path / "out"), "--cache-dir", str(tmp_path / "cache"), "--force"]
    assert main(args) == 2
    assert "has hand edits" in caplog.text and "--discard-edits" in caplog.text


@pytest.mark.heavy
def test_discard_edits_moves_the_edited_folder_aside_and_builds_anew(song_file, tmp_path, built):
    folder, separator = built
    (folder / EDIT_MARK).write_text("[]", encoding="utf-8")
    before = folder_digest(folder)
    cfg = config(song_file, tmp_path)
    result = build_song(type(cfg)(**{**cfg.__dict__, "discard_edits": True}), separator)
    backups = list((tmp_path / "out" / EDITED_BACKUP_DIR).iterdir())
    assert len(backups) == 1 and backups[0].name.startswith(f"{folder.name}_")
    assert folder_digest(backups[0]) == before
    assert state(result.folder) == (PROTECTED, None)


@pytest.mark.heavy
def test_an_edit_saved_while_the_build_runs_is_not_lost(song_file, tmp_path, built):
    """The check runs again right before the folder is replaced: an editor save mid-build stops the build."""
    folder, _ = built

    class EditingSeparator(FakeSeparator):
        def separate(self, audio):
            (folder / EDIT_MARK).write_text("[]", encoding="utf-8")
            return super().separate(audio)

    cfg = config(song_file, tmp_path, force=True)
    cfg = type(cfg)(**{**cfg.__dict__, "cache_dir": tmp_path / "other-cache"})  # separation must run
    with pytest.raises(HandEditsError):
        build_song(cfg, EditingSeparator(song_stems()))
    assert (folder / EDIT_MARK).is_file()
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == [folder.name]


@pytest.mark.heavy
def test_a_folder_built_before_the_hash_is_replaced_as_before(song_file, tmp_path, built):
    folder, separator = built
    analysis = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
    del analysis[HASH_KEY]
    (folder / "analysis.json").write_text(dump_analysis(analysis), encoding="utf-8")
    assert state(folder) == (NOT_RECORDED, None)
    build_song(config(song_file, tmp_path, force=True), separator)
    assert state(folder) == (PROTECTED, None)


# ---------------------------------------------------------------- chartgen protect --record


def unrecord(folder: Path) -> None:
    analysis = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
    del analysis[HASH_KEY]
    (folder / "analysis.json").write_text(dump_analysis(analysis), encoding="utf-8")


@pytest.mark.heavy
def test_record_protects_a_folder_whose_fresh_build_is_the_same(song_file, tmp_path, built):
    folder, separator = built
    unrecord(folder)
    before = (folder / "analysis.json").read_text(encoding="utf-8")
    chart = (folder / "notes.chart").read_bytes()
    outcome = record_folder(folder, [song_file.parent], tmp_path / "cache", separator)
    assert outcome.status == RECORDED, outcome
    after = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
    assert after == {**json.loads(before), HASH_KEY: hashlib.sha256(chart).hexdigest()}
    assert (folder / "notes.chart").read_bytes() == chart
    assert record_folder(folder, [song_file.parent], tmp_path / "cache", separator).status == PROTECTED


@pytest.mark.heavy
def test_record_lists_a_folder_whose_chart_differs_and_leaves_it(song_file, tmp_path, built):
    folder, separator = built
    unrecord(folder)
    chart = folder / "notes.chart"
    chart.write_bytes(chart.read_bytes().replace(b"N 0 0", b"N 1 0", 1))
    before = folder_digest(folder)
    outcome = record_folder(folder, [song_file.parent], tmp_path / "cache", separator)
    assert outcome.status == DIFFERENT and "lines differ" in outcome.detail
    assert folder_digest(folder) == before


def test_record_lists_a_folder_whose_input_is_not_found(tmp_path):
    folder = fake_folder(tmp_path / "out", analysis={"input": {"file_name": "gone.wav", "sha256": "1" * 64}})
    outcome = record_folder(folder, [tmp_path], tmp_path / "cache", FakeSeparator(song_stems()))
    assert outcome.status == NO_INPUT and "gone.wav" in outcome.detail
    assert HASH_KEY not in json.loads((folder / "analysis.json").read_text(encoding="utf-8"))


def test_the_input_is_found_by_name_and_hash_only(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b" / "deep").mkdir(parents=True)
    (tmp_path / "a" / "song.wav").write_bytes(b"other")
    (tmp_path / "b" / "deep" / "song.wav").write_bytes(b"right")
    right = hashlib.sha256(b"right").hexdigest()
    assert find_input("song.wav", right, [tmp_path / "a", tmp_path / "b"]) == tmp_path / "b" / "deep" / "song.wav"
    assert find_input("song.wav", "0" * 64, [tmp_path]) is None


def test_protect_lists_the_folders_and_their_state(tmp_path, caplog):
    outputs = tmp_path / "outputs"
    folder = fake_folder(outputs, analysis={"input": {}})
    (outputs / "_editor_backups").mkdir()
    assert [f.name for f in song_folders(outputs)] == [folder.name]
    assert main(["protect", "--outputs", str(outputs)]) == 0
    assert f"not recorded   {folder.name}" in caplog.text
