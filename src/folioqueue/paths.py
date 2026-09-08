"""Conservative path handling. Symlinks and Windows junctions are not traversed."""

from __future__ import annotations

import os
import stat
import unicodedata
from pathlib import Path


class QueueError(Exception):
    """A user-actionable configuration or filesystem error."""


def linked(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & 0x400  # FILE_ATTRIBUTE_REPARSE_POINT
    )


def no_links(path: Path) -> None:
    for part in (path, *path.parents):
        if linked(part):
            raise QueueError("Symlinks and junctions are not supported in input/output paths.")


def roots(source: Path, output: Path) -> tuple[Path, Path]:
    source = Path(os.path.abspath(source))
    output = Path(os.path.abspath(output))
    no_links(source)
    no_links(output)
    if not source.is_dir():
        raise QueueError("Source must be an existing directory.")
    if source == output or source in output.parents or output in source.parents:
        raise QueueError("Source and output must be separate, non-overlapping directories.")
    if output.exists() and not output.is_dir():
        raise QueueError("Output must be a directory.")
    return source, output


def destination(output: Path, relative: str) -> Path:
    """Never trust paths loaded from a ledger."""
    parts = relative.split("/")
    if not parts or any(p in {"", ".", ".."} or "\\" in p or ":" in p for p in parts):
        raise QueueError("Invalid relative path in the ledger.")
    target = output / "documents" / Path(*parts[:-1]) / (parts[-1] + ".md")
    no_links(target)
    return target


def scan(source: Path, extensions: set[str]) -> tuple[list[Path], list[dict]]:
    files: list[Path] = []
    ignored: list[dict] = []

    def onerror(error: OSError) -> None:
        raise QueueError(
            "A source directory could not be read; no partial scan was accepted."
        ) from error

    for directory, dirs, names in os.walk(source, followlinks=False, onerror=onerror):
        base = Path(directory)
        kept = []
        for name in sorted(dirs):
            path = base / name
            if linked(path) or name.startswith("."):
                ignored.append(
                    {
                        "source": path.relative_to(source).as_posix(),
                        "status": "ignored",
                        "code": "link_or_hidden_directory",
                    }
                )
            else:
                kept.append(name)
        dirs[:] = kept
        for name in sorted(names):
            path = base / name
            relative = path.relative_to(source).as_posix()
            if linked(path) or name.startswith(".") or not path.is_file():
                ignored.append({"source": relative, "status": "ignored", "code": "link_or_hidden"})
            elif path.suffix.lower() not in extensions:
                ignored.append(
                    {"source": relative, "status": "ignored", "code": "unsupported_type"}
                )
            else:
                files.append(path)
    seen: set[str] = set()
    for path in files:
        relative = path.relative_to(source).as_posix()
        key = unicodedata.normalize("NFC", relative).casefold()
        if key in seen:
            raise QueueError("Source paths collide under case-insensitive Unicode normalization.")
        seen.add(key)
        # Reject names that cannot be safely represented by the ledger on all platforms.
        destination(Path("output"), relative)
    return sorted(files, key=lambda p: p.relative_to(source).as_posix()), ignored
