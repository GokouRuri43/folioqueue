"""Reproducible synthetic smoke batch; run from an installed development environment."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from folioqueue.engine import Options, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, required=True, help="Directory for public-safe results."
    )
    args = parser.parse_args()
    # Fixtures are synthetic and MIT-licensed; this script requires the test extra.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
    from conftest import make_docx, make_pdf

    with tempfile.TemporaryDirectory(prefix="fq-release-") as directory:
        root = Path(directory)
        source = root / "source"
        source.mkdir()
        for index in range(40):
            (source / f"note-{index:02d}.txt").write_text(
                f"Synthetic note {index}\n" + "Local collection maintenance.\n" * 100,
                encoding="utf-8",
            )
        for index in range(10):
            (source / f"table-{index:02d}.csv").write_text(
                "Name,Value\nAlpha,1\nBeta,2\n", encoding="utf-8"
            )
        for index in range(2):
            make_docx(source / f"document-{index}.docx")
            make_pdf(source / f"document-{index}.pdf")
            (source / f"page-{index}.html").write_text(
                "<h1>Synthetic heading</h1><p>Release check.</p>", encoding="utf-8"
            )
        options = Options(source, root / "output", timeout=60)
        first = run(options)
        assert first["summary"] == {"converted": 56}, first["summary"]
        second = run(options)
        assert second["summary"] == {"skipped": 56}, second["summary"]
        (source / "note-00.txt").write_text("A changed source", encoding="utf-8")
        third = run(options)
        assert third["summary"] == {"converted": 1, "skipped": 55}, third["summary"]
        (options.output / "documents/note-01.txt.md").write_text("Manual edit", encoding="utf-8")
        fourth = run(options)
        assert fourth["summary"] == {"failed": 1, "skipped": 55}, fourth["summary"]
        result = {
            "executed_at": datetime.now(UTC).isoformat(),
            "platform": platform.system(),
            "python": platform.python_version(),
            "folioqueue": importlib.metadata.version("folioqueue"),
            "markitdown": importlib.metadata.version("markitdown"),
            "workers": options.workers,
            "corpus": {"txt": 40, "csv": 10, "docx": 2, "pdf": 2, "html": 2},
            "runs": [
                {
                    "scenario": scenario,
                    "summary": report["summary"],
                    "duration_seconds": report["duration_seconds"],
                }
                for scenario, report in (
                    ("initial", first),
                    ("unchanged", second),
                    ("one_source_changed", third),
                    ("one_output_edited", fourth),
                )
            ],
            "limitations": (
                "Small synthetic smoke corpus; not an extraction-quality "
                "or comparative throughput benchmark."
            ),
        }
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "synthetic-batch.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
