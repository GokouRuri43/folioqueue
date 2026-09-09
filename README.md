# FolioQueue

**Restartable local document-to-Markdown batches, with a checksum ledger and inspectable failures.**

[![CI](https://github.com/GokouRuri43/folioqueue/actions/workflows/ci.yml/badge.svg)](https://github.com/GokouRuri43/folioqueue/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[简体中文](README.zh-CN.md) · [Design](docs/design.md) · [Validation](docs/validation.md) · [Contributing](CONTRIBUTING.md)

FolioQueue helps maintain a Markdown copy of a **local document collection**. It snapshots each input, converts files in separate processes, checkpoints completed work, and checks both source and output hashes before skipping an unchanged file. A broken document can fail while the rest of the batch finishes.

**Status: 0.1.0 alpha.** See the validation record for what has actually been tested.

## Who is this for?

- **Note / knowledge-base maintainers** folding PDFs, Word and HTML into a Markdown vault, and keeping it in sync as sources change.
- **Local RAG / LLM corpus builders** who need a reproducible, incremental Markdown mirror of a document folder to index.
- **Self-hosted archive keepers** who want failures isolated per file and edited output protected, instead of a one-shot bulk convert.

## Why use it?

- **Resume by rerunning.** Completed files are checkpointed individually; failed files are retried on the next run.
- **Detect real changes.** SHA-256 checksums, rather than timestamps alone, determine whether to convert. Converter dependency changes invalidate document caches.
- **Protect edits.** Untracked or manually changed output is a conflict, even with `--force`.
- **Keep names distinct.** `report.pdf` → `documents/report.pdf.md`; `report.docx` → `documents/report.docx.md`.
- **Contain ordinary failures.** Bounded parallel file processes, per-file timeouts, input/output size checks, and a DOCX expansion preflight.
- **Inspect every outcome.** Local HTML and JSON reports list converted, skipped, failed, ignored and stale files. Reports omit extracted text and raw converter exceptions.
- **Plan first.** `plan` shows per-file decisions without creating files.

This is an independently implemented workflow layer. PDF/DOCX/HTML extraction is delegated to [Microsoft MarkItDown](https://github.com/microsoft/markitdown); this project is not affiliated with Microsoft or OpenAI. It does not claim to improve PDF extraction fidelity. [Alternatives and research](docs/research.md).

## Install

Python 3.11 or later is required. Use a virtual environment. On Windows, the Python launcher may be `py` instead of `python`.

```bash
python -m pip install "folioqueue[documents]"
```

`pip install folioqueue` installs the dependency-free TXT/Markdown/CSV core. The `documents` extra adds PDF, DOCX and HTML through MarkItDown. To install from source, clone the repository and run `python -m pip install ".[documents]"`:

```bash
git clone https://github.com/GokouRuri43/folioqueue.git
cd folioqueue
python -m pip install ".[documents]"
```

## Try it on the included examples

Run these commands from the repository directory:

```bash
folioqueue plan examples/documents -o demo-output --json
folioqueue convert examples/documents -o demo-output
folioqueue convert examples/documents -o demo-output
```

The first conversion produces three Markdown files and ignores one unsupported fixture. The second skips all three unchanged files. Open `demo-output/report.html` to inspect the latest run.

For your own collection:

```bash
folioqueue convert ./documents -o ./markdown-output --workers 2 --timeout 60
```

On Windows:

```powershell
folioqueue convert 'C:\My Documents' -o 'C:\Markdown Output' --workers 2
```

Source and output directories must not overlap. Hidden-name files/directories, symlinks and Windows junctions are skipped. No URL inputs, cloud services, LLM API calls, third-party MarkItDown plugins, or shell commands are used by the conversion workflow. Dependencies must be installed beforehand.

## Supported formats

| Input | Backend | Boundaries |
| --- | --- | --- |
| `.txt`, `.md` | Standard library | Strict UTF-8 with optional BOM by default; `--encoding` selects another encoding |
| `.csv` | Standard library | Comma-separated, first row as header; quoted commas/newlines supported; Markdown cell escaping |
| `.html`, `.htm` | MarkItDown | Text extraction; no browser, script execution or asset downloading is requested |
| `.docx` | MarkItDown | Extraction quality follows upstream; no visual layout preservation |
| `.pdf` | MarkItDown | Text-based PDFs; no OCR, no guarantee of correct reading order or tables |

Empty extracted text is a failure, including a scanned PDF with no text layer. Legacy `.doc`, spreadsheets, slides, images, media, archives and encrypted documents are outside the v0.1 support scope. Source documents remain the authoritative copy.

## Controls and exit codes

```bash
folioqueue convert ./documents -o ./markdown-output --types txt,csv,docx
folioqueue convert ./documents -o ./markdown-output --encoding gb18030
folioqueue convert ./documents -o ./markdown-output --max-input-mb 64 --max-output-mb 32
folioqueue convert ./documents -o ./markdown-output --force --json
```

`--workers` is 1–16 (default 2). `--timeout` covers each converter subprocess, including imports, but not scanning, hashing, copying or committing. `--force` reconverts owned, unedited output; it never authorizes overwriting a conflict. Move conflicting output aside or use a new output directory.

| Exit | Meaning |
| --- | --- |
| `0` | No failed files / no blocking plan decisions; ignored and stale entries are informational |
| `1` | At least one failed conversion or planned conflict/error |
| `2` | Invalid arguments, invalid ledger, overlapping roots, lock contention or a run-level filesystem error |
| `130` | Interrupted; rerun to continue from completed checkpoints |

Deleted source files are reported as **stale**; their output is retained. A failed updated source can leave the previous Markdown in place. Consumers must check `report.json` and must not assume every existing Markdown file is current. The report describes the most recent completed run, not a global corpus validity certificate.

## Output

```text
markdown-output/
  documents/
    report.pdf.md
    subfolder/notes.txt.md
  report.html
  report.json
  .folioqueue/
    state.json
    writer.lock
    work/
```

The private ledger binds an output directory to one absolute source path. Do not edit it or share it as a public artifact. Moving the source requires a new output directory in v0.1. A kernel-managed exclusive writer lock is automatically released on process exit; the lock file may remain and should not be deleted while a run is active.

Interrupted conversions may leave temporary source snapshots in `.folioqueue/work`. Once no run is active, you may remove that directory to reclaim space. A subprocess is **failure isolation, not a security sandbox**; process only trusted documents or use an external sandbox for untrusted inputs. See [SECURITY.md](SECURITY.md).

## Development

```bash
python -m pip install -e ".[test,documents]"
python -m pytest --cov=folioqueue --cov-report=term-missing
python -m ruff check .
python -m ruff format --check .
python -m build
python -m twine check dist/*
```

The test suite includes synthetic, redistributable PDF/DOCX/HTML fixtures and actual subprocess conversions. CI tests Windows, Linux and macOS. The workflow result, rather than this sentence, is the authority for current pass/fail status.

## Roadmap

1. Collect reproducible reports from document-collection maintainers and improve format diagnostics.
2. Publish larger, redistributable corpus results and measure overhead, failure behavior and memory use.
3. Consider an explicit stale-output review command and portable ledger migration after the core behavior is exercised.

Requests for unsupported features belong in issues with a concrete workflow and a minimal non-sensitive sample. No telemetry is collected by FolioQueue.
