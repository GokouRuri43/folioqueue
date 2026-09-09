# Validation record

This document is updated from actual release checks. Test source is in `tests/`; published CI results are available in [Actions](https://github.com/GokouRuri43/folioqueue/actions).

## Test scope

- Real local subprocess conversion for TXT, Markdown, CSV, Unicode paths and alternate text encodings.
- Synthetic valid PDF, DOCX and HTML conversion through the optional MarkItDown backend, plus a corrupt PDF.
- Repeat runs, same-size/same-mtime content changes, missing outputs, converter fingerprint changes and forced reconversion.
- Failed files retried without rerunning successful unchanged files.
- Manual edits and untracked output protected; stale output retained.
- Pending checkpoint recovery on either side of output replacement.
- Real subprocess timeout and process crash; output writer lock contention across processes.
- Path traversal validation, symlink exclusion where supported, source/output overlap, hidden files and case collisions on case-sensitive filesystems.
- Report escaping and absence of document body text and absolute source paths.

Fixtures are small, synthetic and MIT-licensed. They establish regression behavior; they are not a representative real-world extraction corpus. A skipped platform-specific test is not counted as a successful execution of that behavior.

## Local execution — 2026-09-08

Windows, Python 3.12.14, MarkItDown 0.1.7, pytest 9.1.1:

- `python -m pytest --cov=folioqueue --cov-report=term-missing`: **46 passed, 2 skipped**, 94% measured statement coverage, including worker subprocesses. The skips are local symlink creation privileges and a case-sensitive-filesystem test.
- `python -m ruff check .` and `python -m ruff format --check .`: passed.
- `python -m build`: wheel and source archive built successfully.
- Documented example: 3 converted / 1 ignored, then 3 skipped / 1 ignored.

The source-change and interrupted-run recovery tests inject controlled failures. The timeout, worker crash, cancellation and writer-lock checks use actual subprocesses. These are not power-loss or arbitrary OS-signal tests.

## Synthetic collection smoke check

Run `python scripts/validate_release.py --output docs/evidence` from the installed development checkout. Machine-readable result: [synthetic-batch.json](evidence/synthetic-batch.json).

56 small synthetic inputs (40 TXT, 10 CSV, 2 DOCX, 2 PDF, 2 HTML), two workers:

| Scenario | Observed result | Local wall time |
| --- | --- | --- |
| Initial conversion | 56 converted | 4.031 s |
| Unchanged rerun | 56 skipped | 0.219 s |
| One source changed | 1 converted, 55 skipped | 0.250 s |
| One output manually edited | 1 failed conflict, 55 skipped; manual edit retained | 0.203 s |

Times are observations on this machine with a tiny generated corpus. They are not a comparative throughput benchmark or a prediction for real PDFs.

## Public-document corpus check — 2026-09-08

Real, publicly available documents downloaded for local validation; not committed to this repository. 76 files across three rounds; every failure was isolated per file with no batch crash.

Round 1 — PDFs (15 files) from the [Mozilla pdf.js test corpus](https://github.com/mozilla/pdf.js/tree/master/test/pdfs): 13 converted, 2 failed.
- Converted: real-world forms, CJK fonts (XiaoBiaoSong, SimFang variant), Arabic CID fonts, embedded fonts, AcroForm, Type3 fonts, transparency and shading.
- `GHOSTSCRIPT-698804-1-fuzzed.pdf` → `empty_output` (fuzzed file with no text layer).
- `PDFBOX-4352-0.pdf` → `conversion_error` (the file carries an `/Encrypt` dictionary; pdfminer raises `PDFEncryptionError: Unknown filter: param={}`). Encrypted PDFs are outside the v0.1 scope, so this is an expected, isolated failure rather than a FolioQueue defect.

Round 2 — DOCX / HTML / TXT (45 files) from [python-docx test fixtures](https://github.com/python-openxml/python-docx), live pages and [Project Gutenberg](https://www.gutenberg.org/): 37 converted, 8 failed.
- All 8 failures are `empty_output` on python-docx fixtures whose body contains no text (blank/default documents, core-properties-only, settings-only, styles-only). Table structure and cell text are preserved in the converted Markdown.
- HTML from live pages (Wikipedia Markdown in English and Chinese, PEP 8) and TXT (The Adventures of Sherlock Holmes, public domain): all converted.

Round 3 — DOCX (16 files) from [LibreOffice core ooxmlexport test data](https://github.com/LibreOffice/core/tree/master/sw/qa/extras/ooxmlexport/data): 13 converted, 3 failed.
- `Encrypted_MSO2007_abc.docx` and `Encrypted_MSO2010_abc.docx` → `conversion_error` (real encrypted Word documents; out of scope, expected).
- `090716_Studentische_Arbeit_VWS.docx` → `conversion_error` (upstream MarkItDown `DocxConverter` raises `IndexError: pop from empty list` on this real document; a known mammoth bug, [python-mammoth #168](https://github.com/mwilliamson/python-mammoth/issues/168), independently reproduced here and supplemented with a real-world document and a regression test).

Conversion status vs extraction quality: a `converted` result means the backend returned non-empty text; it does not assert correctness. Two real examples where status and quality diverge (both upstream MarkItDown/pdfminer behavior, not FolioQueue logic):
- `XiaoBiaoSong.pdf` (a CJK font without a proper ToUnicode CMap) converts but yields mojibake glyph codes instead of Chinese characters.
- `ArabicCIDTrueType.pdf` converts but returns Arabic in visual order with presentation-form glyphs.

License note: the pdf.js repository is Apache-2.0 but individual test PDFs have heterogeneous origins; python-docx is MIT; LibreOffice core is MPL-2.0; the Gutenberg text is public domain; Wikipedia pages are CC BY-SA. Attribution and redistribution would need per-file review before any of these could become bundled fixtures.

These are real, publicly available documents rather than generated fixtures, but they are still a curated sample and not a substitute for a specific user's own document collection.

## CI and installation

- `python -m twine check dist/*`: wheel and source archive metadata passed. Core metadata is explicitly set to 2.4 for validator compatibility.
- Wheel installed with `--no-deps` into a clean Windows virtual environment containing only FolioQueue and pip. `python -m folioqueue --version` and conversion of the included examples passed from outside the source package directory.
- Cross-platform results are provided by the linked Actions workflow; see the exact commit and job status rather than inferring a passing run from the presence of CI configuration.
- Release commit `22ac669a9ad8e52cb614d8f0da9ee1cdb58cfbb9`: CI run [34196346416](https://github.com/GokouRuri43/folioqueue/actions/runs/34196346416) finished with all four jobs green (Windows/Python 3.12, Linux/Python 3.11, macOS/Python 3.13, packaging). The packaging job built the wheel and source archive, ran `twine check`, installed the wheel dependency-free into a clean environment, and ran a conversion smoke test.
- Published as a prerelease: [v0.1.0](https://github.com/GokouRuri43/folioqueue/releases/tag/v0.1.0), with `folioqueue-0.1.0-py3-none-any.whl`, `folioqueue-0.1.0.tar.gz` and `SHA256SUMS` attached. The release targets commit `22ac669a9ad8e52cb614d8f0da9ee1cdb58cfbb9`; downloaded artifact SHA-256 values match `SHA256SUMS`. The clean-wheel example ran twice: 3 converted / 1 ignored, then 3 skipped / 1 ignored.

The package is distributed through GitHub Releases only; it is not published to PyPI.

## Practical limits

Not yet covered: performance comparison, full Unicode/filesystem portability audit, long-running soak, power-loss simulation, hostile parser sandbox audit, scanned-document OCR evaluation and complex-table fidelity evaluation.
