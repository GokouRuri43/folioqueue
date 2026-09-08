import importlib.util

import pytest
from conftest import make_docx, make_pdf

from folioqueue.engine import run

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        importlib.util.find_spec("markitdown") is None, reason="documents extra is not installed"
    ),
]


def test_real_document_formats_and_corrupt_file(options):
    make_docx(options.source / "sample.docx", "A real Word fixture 中文")
    make_pdf(options.source / "sample.pdf")
    (options.source / "sample.html").write_text(
        "<html><body><h1>Useful heading</h1><p>Local document.</p></body></html>", encoding="utf-8"
    )
    (options.source / "broken.pdf").write_bytes(b"not a pdf")
    report = run(options)
    assert report["summary"] == {"converted": 3, "failed": 1}
    docs = options.output / "documents"
    assert "A real Word fixture" in (docs / "sample.docx.md").read_text(encoding="utf-8")
    assert "FolioQueue PDF fixture" in (docs / "sample.pdf.md").read_text(encoding="utf-8")
    assert "Useful heading" in (docs / "sample.html.md").read_text(encoding="utf-8")
    assert run(options)["summary"] == {"failed": 1, "skipped": 3}
