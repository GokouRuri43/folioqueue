import dataclasses
import json
import os
import subprocess
import sys

import pytest

from folioqueue.engine import Processes, execute, plan, prepare, run
from folioqueue.paths import QueueError
from folioqueue.storage import Ledger, OutputLock, atomic_write, digest


def test_incremental_change_and_output_edit(options):
    file = options.source / "notes.txt"
    file.write_text("first version", encoding="utf-8")
    assert run(options)["summary"] == {"converted": 1}
    assert run(options)["summary"] == {"skipped": 1}
    file.write_text("second version", encoding="utf-8")
    assert run(options)["summary"] == {"converted": 1}
    output = options.output / "documents/notes.txt.md"
    assert output.read_text() == "second version"
    output.write_text("manual edit", encoding="utf-8")
    report = run(dataclasses.replace(options, force=True))
    assert report["records"][0]["code"] == "output_conflict"
    assert output.read_text() == "manual edit"


def test_same_mtime_and_size_still_detected(options):
    file = options.source / "notes.txt"
    file.write_text("aaaa", encoding="utf-8")
    run(options)
    before = file.stat()
    file.write_text("bbbb", encoding="utf-8")
    os.utime(file, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert run(options)["summary"] == {"converted": 1}


def test_failures_do_not_stop_batch_and_retry(options):
    (options.source / "ok.txt").write_text("good", encoding="utf-8")
    broken = options.source / "broken.txt"
    broken.write_bytes(b"\xff\xff")
    (options.source / "empty.md").write_text("  ", encoding="utf-8")
    report = run(options)
    assert report["summary"] == {"converted": 1, "failed": 2}
    broken.write_text("fixed", encoding="utf-8")
    report = run(options)
    assert report["summary"] == {"converted": 1, "failed": 1, "skipped": 1}


def test_paths_unicode_and_source_extension(options):
    nested = options.source / "资料 空格"
    nested.mkdir()
    (nested / "report.txt").write_text("中文正文", encoding="utf-8")
    (nested / "report.md").write_text("# Other", encoding="utf-8")
    assert run(options)["summary"] == {"converted": 2}
    assert (options.output / "documents/资料 空格/report.txt.md").read_text(
        encoding="utf-8"
    ) == "中文正文"
    assert (options.output / "documents/资料 空格/report.md.md").exists()


def test_dry_plan_does_not_create_output(options):
    (options.source / "one.txt").write_text("hi", encoding="utf-8")
    assert plan(options)["records"][0]["action"] == "convert"
    assert not options.output.exists()


def test_stale_outputs_retained_and_filters_not_stale(options):
    file = options.source / "one.txt"
    file.write_text("keep me", encoding="utf-8")
    run(options)
    report = run(dataclasses.replace(options, extensions=frozenset({".csv"})))
    assert report["summary"] == {"ignored": 1}
    file.unlink()
    assert run(options)["summary"] == {"stale": 1}
    assert (options.output / "documents/one.txt.md").read_text() == "keep me"


def test_limits_and_force(options):
    (options.source / "one.txt").write_text("abcd", encoding="utf-8")
    assert (
        run(dataclasses.replace(options, max_input_bytes=2))["records"][0]["code"]
        == "input_too_large"
    )
    assert (
        run(dataclasses.replace(options, max_output_bytes=2))["records"][0]["code"]
        == "output_too_large"
    )
    assert run(options)["summary"] == {"converted": 1}
    assert run(dataclasses.replace(options, force=True))["summary"] == {"converted": 1}


def test_untracked_output_not_overwritten(options):
    (options.source / "a.txt").write_text("source", encoding="utf-8")
    target = options.output / "documents/a.txt.md"
    target.parent.mkdir(parents=True)
    target.write_text("unrelated", encoding="utf-8")
    assert run(options)["records"][0]["code"] == "output_conflict"
    assert target.read_text() == "unrelated"


def test_untracked_report_not_overwritten(options):
    options.output.mkdir()
    target = options.output / "report.html"
    target.write_text("keep", encoding="utf-8")
    with pytest.raises(QueueError, match="Untracked report"):
        run(options)
    assert target.read_text() == "keep"


def test_missing_output_is_regenerated(options):
    (options.source / "a.txt").write_text("source", encoding="utf-8")
    run(options)
    (options.output / "documents/a.txt.md").unlink()
    assert run(options)["summary"] == {"converted": 1}


def test_config_change_invalidates_cache(options):
    (options.source / "a.txt").write_text("ascii", encoding="utf-8")
    run(options)
    assert run(dataclasses.replace(options, encoding="ascii"))["summary"] == {"converted": 1}


def test_pending_checkpoint_adopted_or_retried(options):
    file = options.source / "a.txt"
    file.write_text("original", encoding="utf-8")
    run(options)
    ledger = Ledger(options.output, options.source)
    ledger.entries["a.txt"]["status"] = "pending"
    ledger.save()
    assert run(options)["summary"] == {"skipped": 1}
    target = options.output / "documents/a.txt.md"
    ledger = Ledger(options.output, options.source)
    ledger.entries["a.txt"].update(
        status="pending", previous_output_sha256=digest(target), output_sha256="f" * 64
    )
    ledger.save()
    assert run(options)["summary"] == {"converted": 1}


def test_atomic_write_does_not_damage_existing_file(tmp_path, monkeypatch):
    file = tmp_path / "test"
    file.write_bytes(b"old")

    def fail(*_):
        raise OSError("simulated disk error")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        atomic_write(file, b"new")
    assert file.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [file]


def test_real_subprocess_timeout(options, monkeypatch):
    (options.source / "a.txt").write_text("hi", encoding="utf-8")
    original = Processes.start

    def slow(self, command):
        return original(self, [sys.executable, "-c", "import time; time.sleep(20)"])

    monkeypatch.setattr(Processes, "start", slow)
    report = run(dataclasses.replace(options, timeout=0.05))
    assert report["records"][0]["code"] == "timeout"
    assert not list((options.output / ".folioqueue/work").iterdir())


def test_worker_crash_isolated(options, monkeypatch):
    (options.source / "a.txt").write_text("hi", encoding="utf-8")
    original = Processes.start
    monkeypatch.setattr(
        Processes,
        "start",
        lambda self, cmd: original(self, [sys.executable, "-c", "raise SystemExit(7)"]),
    )
    assert run(options)["records"][0]["code"] == "worker_failed"


def test_source_changes_after_plan(options, tmp_path):
    source = options.source / "a.txt"
    source.write_text("before", encoding="utf-8")
    _, _, _, tasks, _ = prepare(options)
    source.write_text("after", encoding="utf-8")
    code, _ = execute(options.source, tmp_path, tasks[0], options, Processes())
    assert code == "source_changed"


def test_lock_excludes_another_process_and_releases(options):
    code = (
        "from pathlib import Path; from folioqueue.storage import OutputLock; import sys;\n"
        "with OutputLock(Path(sys.argv[1])): pass"
    )
    with OutputLock(options.output):
        result = subprocess.run(
            [sys.executable, "-c", code, str(options.output)], capture_output=True
        )
        assert result.returncode != 0
        assert b"Another FolioQueue process" in result.stderr
    result = subprocess.run([sys.executable, "-c", code, str(options.output)], capture_output=True)
    assert result.returncode == 0


def test_reports_escape_names_and_exclude_text(options):
    # HTML-special characters valid on Windows as well as POSIX.
    (options.source / "a&b'.txt").write_text("PRIVATE CONTENT MUST NOT APPEAR", encoding="utf-8")
    run(options)
    html = (options.output / "report.html").read_text(encoding="utf-8")
    assert "a&amp;b&#x27;.txt" in html
    assert "Content-Security-Policy" in html
    assert "a%26b%27.txt.md" in html
    raw = (options.output / "report.json").read_text(encoding="utf-8")
    assert "PRIVATE CONTENT" not in raw + html
    assert str(options.source) not in raw + html
    assert json.loads(raw)["summary"] == {"converted": 1}


def test_lower_output_limit_revalidates_cache_and_allows_smaller_update(options):
    source = options.source / "a.txt"
    source.write_text("longer text", encoding="utf-8")
    run(options)
    smaller = dataclasses.replace(options, max_output_bytes=3)
    assert run(smaller)["records"][0]["code"] == "output_too_large"
    source.write_text("ok", encoding="utf-8")
    assert run(smaller)["summary"] == {"converted": 1}


def test_interruption_preserves_completed_checkpoint(options, monkeypatch):
    import folioqueue.engine as engine

    (options.source / "a.txt").write_text("first", encoding="utf-8")
    (options.source / "b.txt").write_text("second", encoding="utf-8")
    original = engine.execute

    def interrupt_second(source, scratch, record, opts, processes):
        if record["source"] == "b.txt":
            raise KeyboardInterrupt
        return original(source, scratch, record, opts, processes)

    monkeypatch.setattr(engine, "execute", interrupt_second)
    with pytest.raises(KeyboardInterrupt):
        run(dataclasses.replace(options, workers=1))
    assert (options.output / "documents/a.txt.md").read_text() == "first"
    monkeypatch.setattr(engine, "execute", original)
    assert run(options)["summary"] == {"converted": 1, "skipped": 1}


def test_cancel_stops_tracked_child():
    processes = Processes()
    child = processes.start([sys.executable, "-c", "import time; time.sleep(30)"])
    processes.cancel()
    child.wait(timeout=5)
    assert child.returncode != 0
    with pytest.raises(InterruptedError):
        processes.start([sys.executable, "-c", "pass"])


def test_commit_rechecks_source_and_output(options, monkeypatch):
    import folioqueue.engine as engine

    file = options.source / "a.txt"
    file.write_text("before", encoding="utf-8")
    original = engine.execute

    def changed_source(source, scratch, record, opts, processes):
        result = original(source, scratch, record, opts, processes)
        file.write_text("after", encoding="utf-8")
        return result

    monkeypatch.setattr(engine, "execute", changed_source)
    assert run(options)["records"][0]["code"] == "source_changed"
    assert not (options.output / "documents/a.txt.md").exists()
