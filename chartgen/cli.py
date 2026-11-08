"""Command line interface.

Heavy modules are imported inside the commands, so ``--help`` stays instant and
nothing but a real ``build`` ever touches torch or Demucs.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from chartgen.core.model import Instrument, SongMetadata
from chartgen.errors import ChartgenError

log = logging.getLogger("chartgen")

_INSTRUMENT_NAMES = ", ".join(instrument.value for instrument in Instrument)
_DEFAULT_INSTRUMENTS = "guitar,bass,drums,keys"
_BPM_RANGE = (20.0, 400.0)


def _parse_instruments(value: str) -> frozenset[Instrument]:
    names = [name.strip().lower() for name in value.split(",") if name.strip()]
    if not names:
        raise argparse.ArgumentTypeError(f"name at least one of: {_INSTRUMENT_NAMES}")
    try:
        return frozenset(Instrument(name) for name in names)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"{error}; choose from: {_INSTRUMENT_NAMES}") from error


def _parse_bpm(value: str) -> float:
    try:
        bpm = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"not a number: {value!r}") from error
    low, high = _BPM_RANGE
    if not low <= bpm <= high:
        raise argparse.ArgumentTypeError(f"BPM must be between {low:g} and {high:g}, got {bpm:g}")
    return bpm


def _parse_drift_ms(value: str) -> float:
    try:
        drift = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"not a number: {value!r}") from error
    if not 1.0 <= drift <= 1000.0:
        raise argparse.ArgumentTypeError(f"must be between 1 and 1000 ms, got {drift:g}")
    return drift


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chartgen",
        description="Generate Clone Hero song folders from local audio files you own.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logging")
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="build a song folder from an audio file")
    build.add_argument("input", type=Path, help="local .mp3, .wav, .flac or .ogg file")
    build.add_argument("--artist", required=True)
    build.add_argument("--title", required=True)
    build.add_argument("--album", default="")
    build.add_argument("--genre", default="")
    build.add_argument("--year", default="")
    build.add_argument("--charter", default="chartgen")
    build.add_argument(
        "--instruments",
        type=_parse_instruments,
        default=_parse_instruments(_DEFAULT_INSTRUMENTS),
        help=f"comma-separated, from: {_INSTRUMENT_NAMES} (default: {_DEFAULT_INSTRUMENTS})",
    )
    build.add_argument("--output-dir", type=Path, default=Path("outputs"))
    build.add_argument("--cache-dir", type=Path, default=Path(".cache/stems"))
    build.add_argument("--device", default="auto", help="auto, cpu, cuda, mps (default: auto)")
    build.add_argument("--force", action="store_true", help="replace an existing song folder")
    build.add_argument(
        "--bpm",
        type=_parse_bpm,
        help="use exactly this constant tempo; the first downbeat is still detected",
    )
    build.add_argument(
        "--max-beat-drift-ms",
        type=_parse_drift_ms,
        default=25.0,
        help="how far a region's beats may stray from one tempo before it gets a tempo event "
        "(default: 25)",
    )
    build.add_argument(
        "--click-overlay",
        action="store_true",
        help="also write debug_click.wav: the mix with a metronome taken from the written chart",
    )

    validate = commands.add_parser("validate", help="check existing song folders")
    validate.add_argument("folders", type=Path, nargs="+", metavar="folder")

    evaluate = commands.add_parser(
        "evaluate", help="compare generated charts with human-made references in a folder"
    )
    evaluate.add_argument(
        "folder", type=Path, help="holds train/ and test/, searched for .sng files and chart folders"
    )
    evaluate.add_argument(
        "--split", choices=("train", "test"), help="evaluate only this split (default: all)"
    )
    evaluate.add_argument("--cache-dir", type=Path, default=Path(".cache/stems"))
    evaluate.add_argument("--device", default="auto", help="auto, cpu, cuda, mps (default: auto)")
    evaluate.add_argument("--output", type=Path, help="also write the results as JSON")
    return parser


def _run_build(args: argparse.Namespace) -> int:
    from chartgen.audio.separation import DemucsSeparator
    from chartgen.pipeline import BuildConfig, build_song

    try:
        metadata = SongMetadata(
            name=args.title,
            artist=args.artist,
            album=args.album,
            genre=args.genre,
            year=args.year,
            charter=args.charter,
        )
    except ValueError as error:
        log.error("Error: %s", error)
        return 2

    result = build_song(
        BuildConfig(
            input_path=args.input,
            metadata=metadata,
            instruments=args.instruments,
            output_dir=args.output_dir,
            cache_dir=args.cache_dir,
            force=args.force,
            bpm_override=args.bpm,
            click_overlay=args.click_overlay,
            max_beat_drift_ms=args.max_beat_drift_ms,
        ),
        DemucsSeparator(device=args.device),
    )
    executable = os.environ.get("CLONE_HERO_EXE", "<path to Clone Hero.exe>")
    log.info("Song folder: %s", result.folder.resolve())
    log.info(
        'Preview with: "%s" --song "%s" --player Guitar,Expert -i',
        executable,
        result.folder.resolve(),
    )
    return 0


def _run_validate(args: argparse.Namespace) -> int:
    from chartgen.clonehero.validate import validate_song_folder

    failed = False
    for folder in args.folders:
        report = validate_song_folder(folder)
        for warning in report.warnings:
            log.warning("Warning: %s", warning)
        for error in report.errors:
            log.error("Error: %s", error)
        log.info("%s: %s", folder, "OK" if report.ok else "FAILED")
        failed = failed or not report.ok
    return 1 if failed else 0


def _run_evaluate(args: argparse.Namespace) -> int:
    from chartgen.audio.separation import DemucsSeparator
    from chartgen.evaluation.run import evaluate_folder, format_report, write_report

    report = evaluate_folder(
        args.folder, DemucsSeparator(device=args.device), args.cache_dir, args.split
    )
    log.info("%s", format_report(report))
    if args.output:
        write_report(report, args.output)
    return 0 if report.songs else 1


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return the process exit code."""
    args = _build_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    # Only chartgen's own logger is configured: libraries' request logs would drown the
    # stage reports. Handlers are replaced so repeated calls never print a line twice.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    log.handlers[:] = [handler]
    log.setLevel(logging.DEBUG if args.verbose else logging.INFO)

    try:
        if args.command == "build":
            return _run_build(args)
        if args.command == "evaluate":
            return _run_evaluate(args)
        return _run_validate(args)
    except ChartgenError as error:
        log.error("Error: %s", error)
        return 2
    except KeyboardInterrupt:
        log.error("Interrupted.")
        return 130
