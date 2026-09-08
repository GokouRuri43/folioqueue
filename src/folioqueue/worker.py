"""One-file subprocess. No cloud clients, external plugins, or shell invocation."""

from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from pathlib import Path

MAX_ARCHIVE_ENTRIES = 10000
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024


def cell(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("&", "&amp;")
        .replace("|", "\\|")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\r\n", "<br>")
        .replace("\n", "<br>")
        .replace("\r", "<br>")
    )


def convert(path: Path, encoding: str) -> str:
    if path.suffix.lower() in {".txt", ".md", ".csv"}:
        text = path.read_text(encoding=encoding)
        if "\x00" in text:
            raise ValueError("binary_text")
        if path.suffix.lower() != ".csv":
            return text
        # Fixed comma dialect is explicit; quoted commas/newlines use the stdlib CSV parser.
        rows = list(csv.reader(io.StringIO(text), strict=True))
        if not rows:
            return ""
        width = max(map(len, rows))
        if width == 0:
            return ""
        lines = [
            "| " + " | ".join(cell(v) for v in row + [""] * (width - len(row))) + " |"
            for row in rows
        ]
        lines.insert(1, "| " + " | ".join(["---"] * width) + " |")
        return "\n".join(lines) + "\n"
    if path.suffix.lower() == ".docx":
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if (
                len(members) > MAX_ARCHIVE_ENTRIES
                or sum(m.file_size for m in members) > MAX_ARCHIVE_BYTES
            ):
                raise ValueError("archive_limit")
    from markitdown import MissingDependencyException, StreamInfo
    from markitdown.converters import DocxConverter, HtmlConverter, PdfConverter

    converter = {
        ".pdf": PdfConverter,
        ".docx": DocxConverter,
        ".html": HtmlConverter,
        ".htm": HtmlConverter,
    }[path.suffix.lower()]()
    # Use only the intended public converter. Automatic type fallback can otherwise
    # turn a malformed PDF into a successful plain-text result.
    try:
        with path.open("rb") as stream:
            return converter.convert(stream, StreamInfo(extension=path.suffix.lower())).markdown
    except MissingDependencyException as error:
        raise ModuleNotFoundError("Install the documents extra") from error


def main() -> int:
    source, target, status, encoding, limit = sys.argv[1:]
    result = {}
    try:
        markdown = convert(Path(source), encoding)
        if not markdown.strip():
            result = {"code": "empty_output"}
        elif len(markdown.encode("utf-8")) > int(limit):
            result = {"code": "output_too_large"}
        else:
            Path(target).write_text(markdown, encoding="utf-8", newline="\n")
            result = {"code": "ok"}
    except UnicodeError:
        result = {"code": "encoding_error"}
    except ModuleNotFoundError:
        result = {"code": "missing_backend"}
    except ValueError as error:
        result = {
            "code": str(error)
            if str(error) in {"archive_limit", "binary_text"}
            else "conversion_error"
        }
    except Exception:
        # Do not leak document contents, credentials, or absolute paths through library errors.
        result = {"code": "conversion_error"}
    Path(status).write_text(json.dumps(result), encoding="utf-8")
    return 0 if result["code"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
