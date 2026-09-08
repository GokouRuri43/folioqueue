# Contributing

FolioQueue welcomes reproducible bug reports, documentation corrections, compatibility tests and focused changes to the local conversion workflow.

## Before contributing

Read the README and `docs/design.md`. Discuss large features before implementation; the initial scope intentionally excludes OCR, cloud services, desktop UI, RAG chunking and an HTTP API.

For a bug report, include your OS, Python and FolioQueue/MarkItDown versions, command flags, expected behavior and the report's error code. Attach only synthetic or non-sensitive samples you are authorized to share. Filenames and reports can be sensitive. Do not attach your private ledger or real customer documents.

## Development checks

```bash
python -m pip install -e ".[test,documents]"
python -m pytest --cov=folioqueue --cov-report=term-missing
python -m ruff check .
python -m ruff format --check .
python -m build
python -m twine check dist/*
```

Tests should demonstrate an observable contract or failure recovery, not repeat the implementation. Parser fixes need a small redistributable fixture. Please identify which platforms you actually tested.

Keep changes focused, describe the problem and final behavior, and include validation. Preserve existing output-ownership guarantees. Contributions are accepted under the repository's MIT license; preserve third-party notices when appropriate.

## AI-assisted contributions

AI assistance is welcome. The contributor is responsible for understanding the change, verifying behavior and checking attribution.

## Maintenance

The repository owner, GokouRuri43, is the initial maintainer. Release review covers tests, package install smoke checks, documentation accuracy and known limitations. No response-time SLA is offered.
