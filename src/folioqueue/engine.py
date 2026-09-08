"""Bounded conversion with per-file isolation and conservative output ownership."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .paths import QueueError, destination, no_links, roots, scan
from .report import finish
from .storage import Ledger, OutputLock, atomic_write, digest

SUPPORTED = {".txt", ".md", ".csv", ".html", ".htm", ".docx", ".pdf"}
TEXT_TYPES = {".txt", ".md", ".csv"}


@dataclass(frozen=True)
class Options:
    source: Path
    output: Path
    workers: int = 2
    timeout: float = 60
    max_input_bytes: int = 64 * 1024 * 1024
    max_output_bytes: int = 32 * 1024 * 1024
    encoding: str = "utf-8-sig"
    extensions: frozenset[str] = frozenset(SUPPORTED)
    force: bool = False


def fingerprint(encoding: str, documents: bool) -> str:
    environment = []
    if documents:
        # Converters are transitive dependencies. Upgrades must invalidate cached output.
        environment = sorted(
            {
                (d.metadata.get("Name", "").lower(), d.version)
                for d in importlib.metadata.distributions()
            }
        )
    value = [__version__, list(sys.version_info[:2]), encoding, environment]
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def owned(target: Path, entry: dict | None) -> bool:
    if not target.exists():
        return True
    if not target.is_file() or not entry:
        return False
    return digest(target) in {entry.get("output_sha256"), entry.get("previous_output_sha256")}


def prepare(options: Options) -> tuple[Path, Path, Ledger, list[dict], list[dict]]:
    source, output = roots(options.source, options.output)
    ledger = Ledger(output, source)
    files, ignored = scan(source, set(options.extensions))
    fingerprints = {False: fingerprint(options.encoding, False)}
    if any(p.suffix.lower() not in TEXT_TYPES for p in files):
        fingerprints[True] = fingerprint(options.encoding, True)
    tasks = []
    for path in files:
        relative = path.relative_to(source).as_posix()
        target = destination(output, relative)
        record = {
            "source": relative,
            "output": target.relative_to(output).as_posix(),
            "status": "planned",
            "code": "ok",
            "action": "convert",
            "fingerprint": fingerprints[path.suffix.lower() not in TEXT_TYPES],
        }
        entry = ledger.entries.get(relative)
        try:
            if path.stat().st_size > options.max_input_bytes:
                record.update(action="error", code="input_too_large")
            else:
                record["source_sha256"] = digest(path)
                if not owned(target, entry):
                    record.update(action="conflict", code="output_conflict")
                elif (
                    not options.force
                    and entry
                    and target.is_file()
                    and target.stat().st_size <= options.max_output_bytes
                    and entry["source_sha256"] == record["source_sha256"]
                    and entry["fingerprint"] == record["fingerprint"]
                    and digest(target) == entry["output_sha256"]
                ):
                    record.update(action="skip", code="unchanged")
                    record["output_sha256"] = entry["output_sha256"]
        except OSError:
            record.update(action="error", code="io_error")
        tasks.append(record)
    # Only absent sources are stale; selecting fewer types does not imply deletion.
    for relative in ledger.entries:
        destination(output, relative)  # validate even stale, untrusted ledger keys
        path = source / Path(relative)
        if not path.exists():
            ignored.append({"source": relative, "status": "stale", "code": "source_removed"})
    return source, output, ledger, tasks, ignored


def plan(options: Options) -> dict:
    _, _, _, tasks, ignored = prepare(options)
    return {"schema": 1, "version": __version__, "records": tasks + ignored}


class Processes:
    """Track only our direct children so Ctrl+C never waits for all queued timeouts."""

    def __init__(self):
        self.lock = threading.Lock()
        self.children: set[subprocess.Popen] = set()
        self.cancelled = False

    def start(self, command: list[str]) -> subprocess.Popen:
        with self.lock:
            if self.cancelled:
                raise InterruptedError
            child = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self.children.add(child)
            return child

    def remove(self, child: subprocess.Popen) -> None:
        with self.lock:
            self.children.discard(child)

    def cancel(self) -> None:
        with self.lock:
            self.cancelled = True
            for child in self.children:
                with contextlib.suppress(OSError):
                    child.kill()


def execute(
    source: Path, scratch: Path, record: dict, options: Options, processes: Processes
) -> tuple[str, bytes | None]:
    path = source / Path(record["source"])
    try:
        no_links(path)
        # Snapshot ensures the converter sees precisely the bytes whose hash was planned.
        with tempfile.TemporaryDirectory(prefix="job-", dir=scratch) as temp:
            folder = Path(temp)
            snapshot = folder / ("input" + path.suffix.lower())
            result, status = folder / "result.md", folder / "status.json"
            checksum = hashlib.sha256()
            total = 0
            with path.open("rb") as src, snapshot.open("wb") as dst:
                for chunk in iter(lambda: src.read(1024 * 1024), b""):
                    total += len(chunk)
                    if total > options.max_input_bytes:
                        return "input_too_large", None
                    checksum.update(chunk)
                    dst.write(chunk)
            if checksum.hexdigest() != record["source_sha256"]:
                return "source_changed", None
            command = [
                sys.executable,
                "-m",
                "folioqueue.worker",
                str(snapshot),
                str(result),
                str(status),
                options.encoding,
                str(options.max_output_bytes),
            ]
            child = processes.start(command)
            try:
                try:
                    child.wait(timeout=options.timeout)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                    return "timeout", None
            finally:
                processes.remove(child)
            if not status.is_file() or status.stat().st_size > 1024:
                return "worker_failed", None
            details = json.loads(status.read_text(encoding="utf-8"))
            if details.get("code") != "ok":
                code = details.get("code")
                allowed = {
                    "empty_output",
                    "output_too_large",
                    "encoding_error",
                    "missing_backend",
                    "archive_limit",
                    "binary_text",
                    "conversion_error",
                }
                return code if code in allowed else "worker_failed", None
            if child.returncode != 0 or not result.is_file():
                return "worker_failed", None
            if result.stat().st_size > options.max_output_bytes:
                return "output_too_large", None
            return "ok", result.read_bytes()
    except (OSError, QueueError):
        return "io_error", None
    except (ValueError, TypeError, AttributeError):
        return "worker_failed", None


def commit(source: Path, output: Path, ledger: Ledger, record: dict, data: bytes) -> str:
    target = destination(output, record["source"])
    previous = ledger.entries.get(record["source"])
    if digest(source / Path(record["source"])) != record["source_sha256"]:
        return "source_changed"
    if not owned(target, previous):
        return "output_conflict"
    # Write-ahead ownership covers interruption between output replacement and checkpoint.
    entry = {
        "source_sha256": record["source_sha256"],
        "output_sha256": hashlib.sha256(data).hexdigest(),
        "previous_output_sha256": digest(target) if target.exists() else None,
        "fingerprint": record["fingerprint"],
        "status": "pending",
    }
    ledger.entries[record["source"]] = entry
    ledger.save()
    atomic_write(target, data)
    entry["status"] = "success"
    entry["previous_output_sha256"] = None
    ledger.save()
    record["output_sha256"] = entry["output_sha256"]
    return "ok"


def run(options: Options) -> dict:
    started = time.monotonic()
    started_at = datetime.now(UTC).isoformat()
    source, output = roots(options.source, options.output)
    with OutputLock(output):
        for name in ("report.json", "report.html"):
            no_links(output / name)
            if (output / name).exists() and not (output / ".folioqueue/state.json").exists():
                raise QueueError("Untracked report exists in output. Use a new output directory.")
        source, output, ledger, tasks, records = prepare(options)
        ledger.save()
        scratch = output / ".folioqueue" / "work"
        no_links(scratch)
        scratch.mkdir(exist_ok=True)
        queue = []
        for record in tasks:
            action = record.pop("action")
            if action == "convert":
                queue.append(record)
            else:
                record["status"] = {"skip": "skipped", "error": "failed", "conflict": "failed"}[
                    action
                ]
                records.append(record)
        processes = Processes()
        pool = ThreadPoolExecutor(max_workers=options.workers)
        pending = {}
        iterator = iter(queue)

        def enqueue() -> None:
            item = next(iterator, None)
            if item is not None:
                pending[pool.submit(execute, source, scratch, item, options, processes)] = item

        try:
            for _ in range(options.workers):
                enqueue()
            while pending:
                completed, _ = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
                for future in completed:
                    record = pending.pop(future)
                    code, data = future.result()
                    if code == "ok" and data is not None:
                        try:
                            code = commit(source, output, ledger, record, data)
                        except (OSError, QueueError):
                            code = "io_error"
                    record.update(status="converted" if code == "ok" else "failed", code=code)
                    records.append(record)
                    enqueue()
        except BaseException:
            processes.cancel()
            raise
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
        return finish(
            output,
            {
                "schema": 1,
                "version": __version__,
                "started_at": started_at,
                "duration_seconds": round(time.monotonic() - started, 3),
                "records": records,
            },
        )
