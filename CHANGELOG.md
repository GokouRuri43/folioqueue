# Changelog

## 0.1.1 — 2026-09-09

- Published to PyPI as `folioqueue` with a trusted-publishing release workflow.
- Documentation and validation record updates.

## 0.1.0 — 2026-09-08

Initial alpha release.

- Local recursive TXT/Markdown/CSV conversion with optional MarkItDown PDF/DOCX/HTML extraction.
- Bounded one-file worker processes and timeout/error isolation.
- Input snapshots, checksum-based incremental decisions and per-file write-ahead checkpoints.
- Conservative output ownership and source-extension-preserving names.
- Read-only plan command, JSON/HTML reports and stable exit codes.
- Synthetic regression fixtures, cross-platform CI and English/Chinese documentation.

Known limits: no OCR, no packaged desktop app, no hostile-document sandbox. See the README and validation record.
