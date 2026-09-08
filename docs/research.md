# Selection research — 2026-09-08

The following are public demand signals, not customer endorsements and not independently reproduced upstream bug findings.

## Upstream signals

- [MarkItDown #1371](https://github.com/microsoft/markitdown/issues/1371), “Feature Request: Add batch processing capability for directory conversion”: an open request to convert all supported files in a directory (recursively) in one operation, e.g. `markitdown --batch ./documents --output ./converted`. This is the direct scope FolioQueue implements, plus incremental and ownership behavior.
- [MarkItDown #1166](https://github.com/microsoft/markitdown/issues/1166), “Process multiple files”: an open request to batch-convert a list of files in one invocation. FolioQueue covers this through recursive collection scanning rather than a repeated flag list.
- [MarkItDown #135](https://github.com/microsoft/markitdown/issues/135), “Support for Parallel Processing of files”: a request and discussion around document-processing throughput. Some comments make unsupported general claims about Python parallelism; FolioQueue does not adopt those claims. A bounded one-file process model is used for failure isolation and scheduling.
- [MarkItDown #1234](https://github.com/microsoft/markitdown/issues/1234), “Magika Dependency Optional”: a browser/Pyodide use case affected by ONNX dependencies. FolioQueue does **not** solve that upstream browser issue; it keeps its own text/CSV core dependency-free and makes the complete document backend optional.
- The upstream single-file CLI was inspected at commit [`b6e8bbdce628d564c6af031b5f26cda6e818ea10`](https://github.com/microsoft/markitdown/tree/b6e8bbdce628d564c6af031b5f26cda6e818ea10). FolioQueue implements a separate collection workflow using the published Python package, without copying upstream implementation code.

## Related projects inspected

- [MarkItDown Plus](https://github.com/lamguo/markitdown-plus): folder conversion, workers, manifests, assets, RAG chunking and JSONL. Stronger choice when chunking and assets are central. Its README was reviewed; no claim is made that it lacks an unmentioned capability.
- [kuma90/markitdown-batch](https://github.com/kuma90/markitdown-batch): Windows GUI/CLI for folder conversion through a LAN API.
- [shubhankarreddy/markitdown-gui](https://github.com/shubhankarreddy/markitdown-gui): Windows desktop conversion workflow, discovered through repository metadata.

FolioQueue's v0.1 contract focuses on checksum-based resume, conservative output ownership, write-ahead recovery, per-file timeout isolation and read-only planning. These are concrete, testable behaviors.

## Next steps

- Gather external usage on representative, non-sensitive collections.
- Identify workflows where checkpointing and output-conflict detection materially help.
- Measure overhead against a simple sequential MarkItDown loop using the same corpus, backend version and hardware.
- Turn real failure reports into minimal fixtures and fixes.
