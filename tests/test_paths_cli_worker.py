import dataclasses
import json

import pytest

from folioqueue.cli import main
from folioqueue.engine import run
from folioqueue.paths import QueueError, destination, roots, scan
from folioqueue.storage import Ledger
from folioqueue.worker import convert


@pytest.mark.parametrize(
    "relative", ["../escape", "/absolute", "a/../../b", "C:/escape", "a\\b", "a//b"]
)
def test_ledger_traversal_rejected(tmp_path, relative):
    with pytest.raises(QueueError):
        destination(tmp_path, relative)


def test_overlapping_and_invalid_roots(collection):
    source, output = collection
    for target in (source, source / "out", source.parent):
        with pytest.raises(QueueError, match="overlapping"):
            roots(source, target)
    with pytest.raises(QueueError, match="existing directory"):
        roots(source / "missing", output)


def test_hidden_and_unsupported_are_reported(options):
    (options.source / ".private.txt").write_text("secret", encoding="utf-8")
    (options.source / ".git").mkdir()
    (options.source / ".git/notes.txt").write_text("secret", encoding="utf-8")
    (options.source / "image.png").write_bytes(b"image")
    assert run(options)["summary"] == {"ignored": 3}


def test_symlinks_do_not_escape(collection, tmp_path):
    source, output = collection
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    try:
        (source / "linked.txt").symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation not available to this Windows account")
    files, ignored = scan(source, {".txt"})
    assert not files
    assert ignored[0]["code"] == "link_or_hidden"
    output.symlink_to(source, target_is_directory=True)
    with pytest.raises(QueueError, match="Symlinks"):
        roots(source, output)


def test_case_collision(collection):
    source, _ = collection
    (source / "A.txt").write_text("A")
    if (source / "a.txt").exists():
        pytest.skip("Case collision needs a case-sensitive filesystem")
    (source / "a.txt").write_text("a")
    with pytest.raises(QueueError, match="collide"):
        scan(source, {".txt"})


def test_corrupt_or_rebound_ledger(options):
    run(options)
    file = options.output / ".folioqueue/state.json"
    file.write_text("not json", encoding="utf-8")
    with pytest.raises(QueueError, match="Ledger"):
        Ledger(options.output, options.source)
    file.write_text(json.dumps({"schema": 1, "source_root": "other", "entries": {}}))
    with pytest.raises(QueueError, match="Ledger"):
        Ledger(options.output, options.source)


def test_csv_quoted_newline_and_markdown_escaping(tmp_path):
    file = tmp_path / "a.csv"
    file.write_text('Name,Notes\nAda,"pipe | and\na comma, <tag>"\n', encoding="utf-8")
    result = convert(file, "utf-8")
    assert "| Name | Notes |" in result
    assert "pipe \\| and<br>a comma, &lt;tag&gt;" in result


def test_bom_and_non_utf8(options):
    (options.source / "bom.txt").write_bytes(b"\xef\xbb\xbfhello")
    run(options)
    assert (options.output / "documents/bom.txt.md").read_bytes() == b"hello"
    (options.source / "bom.txt").write_bytes("中文".encode("gb18030"))
    assert run(dataclasses.replace(options, encoding="gb18030"))["summary"] == {"converted": 1}


def test_binary_and_empty_csv(options):
    (options.source / "a.txt").write_bytes(b"null\x00here")
    (options.source / "b.csv").write_bytes(b"")
    codes = {r["code"] for r in run(options)["records"]}
    assert codes == {"binary_text", "empty_output"}


def test_cli_exit_codes_and_plan(options, capsys):
    args = [str(options.source), "-o", str(options.output)]
    (options.source / "a.txt").write_text("hi", encoding="utf-8")
    assert main(["plan", *args, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["records"][0]["action"] == "convert"
    assert main(["convert", *args]) == 0
    (options.source / "empty.txt").write_text("", encoding="utf-8")
    assert main(["convert", *args]) == 1
    assert main(["convert", str(options.source), "-o", str(options.source)]) == 2


@pytest.mark.parametrize(
    "flag,value",
    [
        ("--workers", "0"),
        ("--timeout", "nan"),
        ("--timeout", "0"),
        ("--types", "exe"),
        ("--encoding", "nonsense-encoding"),
    ],
)
def test_invalid_cli_options(options, flag, value):
    with pytest.raises(SystemExit) as error:
        main(["convert", str(options.source), "-o", str(options.output), flag, value])
    assert error.value.code == 2


def test_invalid_previous_checksum_rejected(options):
    (options.source / "a.txt").write_text("hello", encoding="utf-8")
    run(options)
    file = options.output / ".folioqueue/state.json"
    data = json.loads(file.read_text(encoding="utf-8"))
    data["entries"]["a.txt"]["previous_output_sha256"] = []
    file.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(QueueError, match="Ledger"):
        run(options)


def test_docx_archive_preflight(tmp_path, monkeypatch):
    from conftest import make_docx

    from folioqueue import worker

    file = tmp_path / "a.docx"
    make_docx(file)
    monkeypatch.setattr(worker, "MAX_ARCHIVE_BYTES", 10)
    with pytest.raises(ValueError, match="archive_limit"):
        convert(file, "utf-8")


def test_cli_interrupt_and_filesystem_failure(options, monkeypatch):
    import folioqueue.cli as cli

    args = ["convert", str(options.source), "-o", str(options.output)]

    def interrupt(_):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run", interrupt)
    assert main(args) == 130

    def io_error(_):
        raise OSError("private path must not be displayed")

    monkeypatch.setattr(cli, "run", io_error)
    assert main(args) == 2


def test_generated_html_never_embeds_filename_markup(tmp_path):
    from folioqueue.report import finish

    report = {
        "started_at": "2026-09-08",
        "version": "0.1.0",
        "duration_seconds": 0,
        "records": [
            {
                "source": '<script>alert("x")</script>.txt',
                "status": "failed",
                "code": "conversion_error",
            }
        ],
    }
    finish(tmp_path, report)
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
