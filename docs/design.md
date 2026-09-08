# Design and invariants

## Scope

FolioQueue is a workflow layer for repeated conversion of trusted local document collections. It implements scheduling, input snapshots, output ownership, incremental decisions and run reporting. MarkItDown performs the optional document extraction. There is no new PDF parser, OCR engine, browser service, LLM call, or public HTTP endpoint.

## Data flow

1. Validate separate roots and reject symlink/junction path components.
2. Acquire an OS-managed exclusive lock in the output directory.
3. Load a schema-versioned ledger bound to the source root; scan selected extensions.
4. Hash sources and check existing output ownership. A checksum mismatch is a conflict, including under `--force`.
5. Schedule at most `workers` jobs. Copy each input into a temporary snapshot, checking size and the planned checksum.
6. Spawn the same Python interpreter as a one-file worker. Discard converter stdout/stderr; accept a small structured status file and bounded Markdown output.
7. Recheck the live source and output, checkpoint pending ownership, atomically replace Markdown, and checkpoint success.
8. Write JSON and inert HTML reports for the completed run.

The report is relative-path-only. The private ledger contains an absolute source root to prevent accidental output reuse with an unrelated collection.

## Cache key

TXT/MD/CSV use the FolioQueue version, Python major/minor version and selected text encoding. Document formats additionally include the installed distribution names and versions, so a transitive converter dependency update invalidates document cache entries. This is deliberately conservative: installing an unrelated distribution can also cause reconversion.

Source and output SHA-256 hashes must both match. No timestamp-only fast path is used. Failed conversions are not cached as successful. Missing output is regenerated. `--force` bypasses only the unchanged-file shortcut.

## Commit interruption cases

| Interruption point | Next run |
| --- | --- |
| Before pending checkpoint | Previous ledger/output remain authoritative |
| After pending checkpoint, before output replacement | Old owned hash is accepted, and the file is reconverted |
| After output replacement, before success checkpoint | Matching new output can be reused if source and fingerprint still match |
| After success checkpoint | Normal incremental skip |

Atomic replacement is per file. The whole batch is not a transaction, and the two report files are not a transactional pair. A forced stop can leave the previous completed report and temporary snapshots. Always inspect the command exit code. Power-loss durability depends on the filesystem; `fsync` of file contents is used, but this is not a database-grade power-failure guarantee.

## Output ownership

Only checksummed output tracked by the ledger is replaced. Names retain source extensions. Source names that collide under NFC normalization and case folding are rejected before conversion for portability. Reports and the private metadata directory are reserved generated paths. Stale outputs are retained, never automatically deleted.

The output directory is an application-managed workspace; do not edit reports or the ledger. Source documents and handwritten Markdown should live elsewhere. An output file edited concurrently after the final ownership check is outside the cooperative-writer model; do not edit output during an active run.

## Resource and security limits

At most 16 worker processes can be requested (default 2). Defaults are 64 MiB input, 32 MiB output and 60 seconds per worker. DOCX archives are limited to 10,000 entries and 256 MiB declared uncompressed data. These are admission/output checks, not OS memory or disk quotas: an underlying parser can allocate substantial memory before returning output. Use an external sandbox and resource limits for hostile documents.

Time limits cover worker startup/imports and conversion. Scanning, hashing, snapshotting and commit I/O are not timed. Only direct child processes are managed; the supported conversion paths do not intentionally launch grandchildren. No protection against a compromised parser, hostile local process, filesystem race, or maliciously edited ledger is claimed.
