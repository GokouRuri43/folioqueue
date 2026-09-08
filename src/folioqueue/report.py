"""Content-free JSON and inert HTML run reports."""

from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path
from urllib.parse import quote

from .storage import atomic_write, json_write

HINTS = {
    "ok": "Converted and checkpointed.",
    "unchanged": "Input, converter environment and output checksums match.",
    "output_conflict": "Output is untracked or edited. Move it aside or choose a new output directory.",
    "timeout": "Conversion exceeded the per-file timeout. Retry with a larger --timeout.",
    "missing_backend": "Install folioqueue[documents] to convert PDF, DOCX and HTML.",
    "encoding_error": "Text decoding failed. Set --encoding to the source encoding.",
    "empty_output": "No text was extracted. Scanned PDFs may require a separate OCR workflow.",
    "input_too_large": "Input exceeds --max-input-mb.",
    "output_too_large": "Output exceeds --max-output-mb.",
    "archive_limit": "DOCX exceeds the archive entry or uncompressed-size limit.",
    "binary_text": "NUL bytes found in a text file; check its format and encoding.",
    "conversion_error": "Converter could not process this file. Check validity and supported features.",
    "worker_failed": "Conversion process ended without a valid result.",
    "io_error": "A file could not be read or written; check permissions and available space.",
    "source_changed": "Source changed during the run. Retry when the source is stable.",
    "unsupported_type": "Extension is outside this run's selected types.",
    "link_or_hidden": "Symlink, junction, special file or hidden-name file skipped.",
    "link_or_hidden_directory": "Symlink, junction or hidden-name directory not traversed.",
    "source_removed": "Source no longer exists in the selected scan. Prior output was retained.",
}


def finish(output: Path, report: dict) -> dict:
    report["records"].sort(key=lambda item: item["source"])
    report["summary"] = dict(sorted(Counter(r["status"] for r in report["records"]).items()))
    rows = []
    for record in report["records"]:
        record["message"] = HINTS.get(record["code"], record["code"])
        label = escape(record["source"])
        if record.get("output") and record["status"] in {"converted", "skipped"}:
            label = f'<a href="{quote(record["output"], safe="/")}">{label}</a>'
        rows.append(
            f"<tr><td>{label}</td><td>{escape(record['status'])}</td>"
            f"<td>{escape(record['message'])}</td></tr>"
        )
    summary = " · ".join(f"{count} {escape(status)}" for status, count in report["summary"].items())
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>FolioQueue · Conversion report</title>
<style>
:root{{color-scheme:light dark;font:16px/1.55 system-ui,sans-serif;background:#f4f5f0;color:#182827}}
body{{max-width:1120px;margin:0 auto;padding:48px 24px}}h1{{font-size:40px;letter-spacing:-1.5px;margin:12px 0}}
.eyebrow{{color:#316d60;letter-spacing:2px;font-size:12px;font-weight:700}}.summary{{font-size:22px;margin:24px 0}}
.meta,footer{{color:#506560;font-size:14px}}.scroll{{overflow:auto;background:#fff;border:1px solid #d6dfda;border-radius:12px}}
table{{border-collapse:collapse;width:100%;text-align:left}}th,td{{padding:16px;border-bottom:1px solid #e1e7e3;vertical-align:top}}
th{{font-size:12px;letter-spacing:1px;text-transform:uppercase;background:#eaf0ec}}td:first-child{{overflow-wrap:anywhere;min-width:180px}}
a{{color:#17644f}}footer{{margin-top:24px}}@media(prefers-color-scheme:dark){{:root{{background:#14221f;color:#edf3ee}}.scroll{{background:#1c302a;border-color:#385044}}th{{background:#223d32}}th,td{{border-color:#385044}}a,.eyebrow{{color:#94d6b7}}.meta,footer{{color:#afc2b7}}}}
</style></head><body><div class="eyebrow">FOLIOQUEUE / LOCAL DOCUMENT WORKFLOWS</div>
<h1>Conversion report</h1><p class="meta">{escape(report["started_at"])} · v{escape(report["version"])} · {report["duration_seconds"]:.2f}s</p>
<p class="summary">{summary or "No matching files"}</p><div class="scroll"><table>
<thead><tr><th>Source</th><th>Result</th><th>Details</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<footer>No document text is embedded in this report. Filenames can still be sensitive. Output links open local Markdown files; their content is untrusted.</footer>
</body></html>"""
    json_write(output / "report.json", report)
    atomic_write(output / "report.html", page.encode("utf-8"))
    return report
