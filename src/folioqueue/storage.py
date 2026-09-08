"""Atomic checkpoints, output ownership and a kernel-released exclusive writer lock."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
from pathlib import Path

from .paths import QueueError, no_links


def digest(path: Path) -> str:
    no_links(path)
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    no_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    no_links(path)
    fd, name = tempfile.mkstemp(prefix=".fq-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(name)


def json_write(path: Path, value: dict) -> None:
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


class Ledger:
    def __init__(self, output: Path, source: Path):
        self.path = output / ".folioqueue" / "state.json"
        no_links(self.path)
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
                if (
                    self.data["schema"] != 1
                    or self.data["source_root"] != str(source)
                    or not isinstance(self.data["entries"], dict)
                ):
                    raise ValueError
                for key, entry in self.data["entries"].items():
                    if not isinstance(key, str) or not isinstance(entry, dict):
                        raise ValueError
                    for field in ("source_sha256", "output_sha256", "fingerprint", "status"):
                        if not isinstance(entry[field], str):
                            raise ValueError
                    for field in ("source_sha256", "output_sha256"):
                        if len(entry[field]) != 64 or any(
                            c not in "0123456789abcdef" for c in entry[field]
                        ):
                            raise ValueError
                    if entry["status"] not in {"pending", "success"}:
                        raise ValueError
                    previous = entry.get("previous_output_sha256")
                    if previous is not None and (
                        not isinstance(previous, str)
                        or len(previous) != 64
                        or any(c not in "0123456789abcdef" for c in previous)
                    ):
                        raise ValueError
            except (ValueError, KeyError, TypeError) as error:
                raise QueueError(
                    "Ledger is invalid or belongs to another source. Use a new output directory."
                ) from error
        else:
            self.data = {"schema": 1, "source_root": str(source), "entries": {}}

    @property
    def entries(self) -> dict:
        return self.data["entries"]

    def save(self) -> None:
        json_write(self.path, self.data)


class OutputLock:
    """OS advisory lock; remains safe after a process crash (no stale PID guessing)."""

    def __init__(self, output: Path):
        self.path = output / ".folioqueue" / "writer.lock"

    def __enter__(self):
        no_links(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+b")
        self.stream.seek(0, os.SEEK_END)
        if self.stream.tell() == 0:
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.stream.close()
            raise QueueError(
                "Another FolioQueue process is using this output directory."
            ) from error
        return self

    def __exit__(self, *_):
        self.stream.close()
