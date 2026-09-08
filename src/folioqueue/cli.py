"""CLI with stable exit codes and a read-only plan command."""

from __future__ import annotations

import argparse
import codecs
import json
import math
import sys
from collections import Counter
from pathlib import Path

from . import __version__
from .engine import SUPPORTED, Options, plan, run
from .paths import QueueError


def positive(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= 1_000_000:
        raise argparse.ArgumentTypeError("must be a finite positive number, at most 1000000")
    return number


def workers(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 16:
        raise argparse.ArgumentTypeError("must be between 1 and 16")
    return number


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Restartable local document-to-Markdown batches.")
    root.add_argument("--version", action="version", version=f"folioqueue {__version__}")
    commands = root.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("convert", "Convert a directory and write reports."),
        ("plan", "Inspect pending work without writing files."),
    ):
        sub = commands.add_parser(command, help=help_text)
        sub.add_argument("source", type=Path, help="Source directory (scanned recursively).")
        sub.add_argument(
            "-o",
            "--output",
            type=Path,
            required=True,
            help="Separate output directory, outside the source tree.",
        )
        sub.add_argument(
            "--workers", type=workers, default=2, help="Parallel file processes (1–16)."
        )
        sub.add_argument(
            "--timeout", type=positive, default=60, help="Seconds allowed per converter process."
        )
        sub.add_argument(
            "--max-input-mb", type=positive, default=64, help="Per-file input limit in MiB."
        )
        sub.add_argument(
            "--max-output-mb", type=positive, default=32, help="Per-file Markdown limit in MiB."
        )
        sub.add_argument(
            "--encoding", default="utf-8-sig", help="TXT/MD/CSV encoding (default: utf-8-sig)."
        )
        sub.add_argument(
            "--types",
            default=",".join(sorted(t[1:] for t in SUPPORTED)),
            help="Comma-separated subset: txt,md,csv,html,htm,docx,pdf.",
        )
        sub.add_argument(
            "--force",
            action="store_true",
            help="Reconvert unchanged files; never overwrite edited output.",
        )
        sub.add_argument(
            "--json", action="store_true", help="Print the full machine-readable report."
        )
    return root


def main(argv: list[str] | None = None) -> int:
    cli = parser()
    args = cli.parse_args(argv)
    try:
        encoding = codecs.lookup(args.encoding).name
    except LookupError:
        cli.error("unknown text encoding")
    extensions = frozenset("." + part.strip().lower().lstrip(".") for part in args.types.split(","))
    if not extensions or not extensions <= SUPPORTED:
        cli.error("--types must contain only supported extensions")
    options = Options(
        args.source,
        args.output,
        args.workers,
        args.timeout,
        max(1, int(args.max_input_mb * 1024 * 1024)),
        max(1, int(args.max_output_mb * 1024 * 1024)),
        encoding,
        extensions,
        args.force,
    )
    try:
        report = plan(options) if args.command == "plan" else run(options)
    except KeyboardInterrupt:
        print(
            "Interrupted. Completed files are checkpointed; rerun the same command.",
            file=sys.stderr,
        )
        return 130
    except QueueError as error:
        print(f"folioqueue: {error}", file=sys.stderr)
        return 2
    except OSError:
        print(
            "folioqueue: filesystem operation failed; check permissions and disk space.",
            file=sys.stderr,
        )
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    elif args.command == "plan":
        counts = Counter(r.get("action", r["status"]) for r in report["records"])
        print("Plan: " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items())))
        print("No files written. Add --json for per-file decisions.")
    else:
        print("Finished: " + ", ".join(f"{n} {s}" for s, n in report["summary"].items()))
        print("Reports: report.html and report.json in the output directory.")
    return (
        1
        if any(
            r["status"] == "failed" or r.get("action") in {"error", "conflict"}
            for r in report["records"]
        )
        else 0
    )
