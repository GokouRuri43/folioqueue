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

Two rounds were run against real, publicly available documents downloaded for local validation. The files are not committed to this repository.

Round 1 — PDFs (15 files) from the [Mozilla pdf.js test corpus](https://github.com/mozilla/pdf.js/tree/master/test/pdfs): 13 converted, 2 failed, both isolated without a batch crash.
- Converted: real-world forms, CJK fonts (XiaoBiaoSong, SimFang variant), Arabic CID fonts, embedded fonts, AcroForm, Type3 fonts, transparency and shading.
- `GHOSTSCRIPT-698804-1-fuzzed.pdf` → `empty_output` (fuzzed file with no text layer).
- `PDFBOX-4352-0.pdf` → `conversion_error` (upstream pdfminer raises `PDFEncryptionError: Unknown filter: param={}`).

Round 2 — DOCX / HTML / TXT (13 files): 12 converted, 1 failed.
- DOCX from [python-docx test fixtures](https://github.com/python-openxml/python-docx) (tables, comments, headers/footers, hyperlinks, page breaks, numbering, styles): 8 of 9 converted; `doc-default.docx` → `empty_output` (a blank default Word document with no text).
- HTML from live pages (Wikipedia Markdown in English and Chinese, PEP 8) and TXT from [Project Gutenberg](https://www.gutenberg.org/) (The Adventures of Sherlock Holmes, public domain): all converted.

License note: the pdf.js repository is Apache-2.0 but individual test PDFs have heterogeneous origins; python-docx is MIT; the Gutenberg text is public domain; Wikipedia pages are CC BY-SA. Attribution and redistribution would need per-file review before any of these could become bundled fixtures.

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
