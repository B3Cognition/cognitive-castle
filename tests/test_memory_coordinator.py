"""Bounded model-free capture, using synthetic originals and private stores only."""

import importlib
import json
import os
from pathlib import Path
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from cognitive_castle.brain_api import _root_registry
from cognitive_castle.fast_memory import MemoryStore
from cognitive_castle.memory_capture import coverage, source_page

pytestmark = pytest.mark.skipif(os.name != "posix", reason="owner-private POSIX capture")


def setup_root(tmp_path):
    palace = tmp_path / "palace"
    root = tmp_path / "originals"
    palace.mkdir()
    root.mkdir()
    _root_registry(palace, ("test", str(root), "claude"))
    return palace, root


def original(path, text="durable exact words", *, tail=False):
    raw = json.dumps({"type": "user", "message": {"content": text}})
    path.write_text(raw + ("" if tail else "\n"))
    return path


def coordinator():
    return importlib.import_module("cognitive_castle.memory_coordinator")


def local_workers(monkeypatch):
    # Exercise real worker dispatch/storage without pytest's RSS in the production chain.
    from cognitive_castle.memory_worker import _execute

    monkeypatch.setattr(
        coordinator(),
        "run_memory",
        lambda palace, operation, arguments, **kw: _execute(
            dict(palace=str(palace), operation=operation, arguments=arguments)
        ),
    )


def test_capture_defaults_disabled_and_pause_preserves_legacy_marker(tmp_path, monkeypatch):
    c = coordinator()
    local_workers(monkeypatch)
    palace, root = setup_root(tmp_path)
    marker = tmp_path / "codex-capture.disabled"
    marker.write_text("legacy")
    source = original(root / "one.jsonl")
    assert c.capture_status(palace)["enabled"] is False
    assert c.handle_capture_event(palace, source, str(tmp_path), "claude")["status"] == "paused"
    c.configure_capture(palace, enabled=True)
    c.configure_capture(palace, enabled=False)
    assert c.capture_tick(palace)["status"] == "paused"
    assert marker.read_text() == "legacy"
    assert not (palace / ".memory" / "capture-spool").exists()


def test_busy_hooks_persist_then_resume_with_workspace(tmp_path, monkeypatch):
    c = coordinator()
    palace, root = setup_root(tmp_path)
    c.configure_capture(palace, enabled=True)
    fd = c._coordinator_lock(palace)
    try:
        source = original(root / "one.jsonl")
        started = time.monotonic()
        result = c.handle_capture_event(palace, source, str(tmp_path), "claude")
        assert time.monotonic() - started < 0.5
        assert result["queued"] is True
        assert result["catch_up"]["reason"] == "coordinator_busy"
    finally:
        os.close(fd)
    local_workers(monkeypatch)
    result = c.capture_tick(palace, discover=False)
    assert result["successful_slices"] == 1
    store = MemoryStore(palace / ".memory")
    assert store.recall("durable")["sources"]
    assert source_page(store)["sources"][0]["workspace"] == str(tmp_path)
    assert c.capture_status(palace)["spooled_events"] == 0


@pytest.mark.parametrize(
    "reason", ["memory_busy", "system_pressure_unavailable", "worker_deadline"]
)
def test_worker_refusal_keeps_metadata_for_next_tick(tmp_path, monkeypatch, reason):
    c = coordinator()
    palace, root = setup_root(tmp_path)
    c.configure_capture(palace, enabled=True)
    fd = c._coordinator_lock(palace)
    try:
        c.handle_capture_event(palace, original(root / "one.jsonl"), str(tmp_path), "claude")
    finally:
        os.close(fd)
    monkeypatch.setattr(
        c,
        "run_memory",
        lambda *a, **kw: {"status": "unavailable", "reason": reason},
    )
    assert c.capture_tick(palace, discover=False)["reason"] == reason
    assert c.capture_status(palace)["spooled_events"] == 1
    local_workers(monkeypatch)
    assert c.capture_tick(palace, discover=False)["successful_slices"] == 1


def test_concurrent_duplicate_hooks_and_partial_tail_do_not_spin(tmp_path, monkeypatch):
    c = coordinator()
    palace, root = setup_root(tmp_path)
    c.configure_capture(palace, enabled=True)
    source = original(root / "tail.jsonl", tail=True)
    fd = c._coordinator_lock(palace)
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(
                pool.map(
                    lambda _: c.handle_capture_event(palace, source, str(tmp_path), "claude"),
                    range(8),
                )
            )
        assert all(item["queued"] for item in results)
    finally:
        os.close(fd)
    local_workers(monkeypatch)
    assert c.capture_status(palace)["spooled_events"] == 1
    first = c.capture_tick(palace, discover=False)
    assert first["successful_slices"] == 1
    store = MemoryStore(palace / ".memory")
    assert coverage(store)["pending_sources"] == 1
    with source.open("a") as stream:
        stream.write("\n")
    assert c.capture_tick(palace, discover=False)["successful_slices"] == 1
    assert coverage(store)["pending_sources"] == 0


@pytest.mark.parametrize("kind", ["outside", "file_symlink", "dir_symlink", "wrong_format"])
def test_hook_rejects_unregistered_or_symlink_original(tmp_path, kind):
    c = coordinator()
    palace, root = setup_root(tmp_path)
    c.configure_capture(palace, enabled=True)
    source = original(root / "one.jsonl")
    fmt = "claude"
    if kind == "outside":
        source = original(tmp_path / "outside.jsonl")
    elif kind == "file_symlink":
        link = root / "link.jsonl"
        link.symlink_to(source)
        source = link
    elif kind == "dir_symlink":
        link = root / "linked"
        link.symlink_to(root, target_is_directory=True)
        source = link / "one.jsonl"
    else:
        fmt = "codex"
    with pytest.raises(ValueError):
        c.handle_capture_event(palace, source, str(tmp_path), fmt)
    assert not (palace / ".memory" / "capture-spool").exists()


def test_discovery_pages_restart_resweep_and_ignore_symlinks(tmp_path):
    from cognitive_castle.memory_discovery import discover_sources, discovery_status

    palace, root = setup_root(tmp_path)
    for name in ("b", "c", "d", "e", "f"):
        original(root / (name + ".jsonl"), name)
    (root / "ignored.jsonl").symlink_to(root / "b.jsonl")
    (root / "nested").mkdir()
    original(root / "nested" / "one.jsonl", "nested")
    store = MemoryStore(palace / ".memory")
    first = discover_sources(store, allowed_root=root, format="claude", max_entries=2)
    assert first["queued_sources"] <= 2
    assert first["discovery"] == "incomplete"
    assert discovery_status(store)["roots"][0]["completed_sweeps"] == 0
    for _ in range(12):
        # Reopen the store to prove progress is durable rather than iterator-local.
        result = discover_sources(
            MemoryStore(palace / ".memory"), allowed_root=root, format="claude", max_entries=2
        )
        if result["discovery"] == "complete_at_last_sweep":
            break
    assert result["discovery"] == "complete_at_last_sweep"
    assert coverage(store)["observed_sources"] == 6
    original(root / "a.jsonl", "new behind cursor")
    for _ in range(12):
        result = discover_sources(store, allowed_root=root, format="claude", max_entries=2)
        if result["discovery"] == "complete_at_last_sweep":
            break
    assert coverage(store)["observed_sources"] == 7


def test_discovery_entry_cap_is_visible_and_never_advances_incomplete_scan(tmp_path, monkeypatch):
    import cognitive_castle.memory_discovery as d

    palace, root = setup_root(tmp_path)
    for number in range(8):
        original(root / f"{number}.jsonl")
    monkeypatch.setattr(d, "MAX_SCAN_ENTRIES", 3)
    store = MemoryStore(palace / ".memory")
    result = d.discover_sources(store, allowed_root=root, format="claude")
    assert result["reason"] == "discovery_entry_limit"
    assert result["discovery"] == "incomplete"
    assert coverage(store)["observed_sources"] == 0
    monkeypatch.setattr(d, "MAX_SCAN_ENTRIES", 32)
    assert d.discover_sources(store, allowed_root=root, format="claude")["queued_sources"] == 8


def test_tick_bounds_and_cli_operator_only(tmp_path, monkeypatch, capsys):
    import argparse
    from cognitive_castle.brain_api import SPECS, cmd_memory, configure_memory_parser

    c = coordinator()
    palace, _ = setup_root(tmp_path)
    parser = argparse.ArgumentParser()
    parser.add_argument("--palace")
    configure_memory_parser(parser.add_subparsers(dest="command"))
    args = parser.parse_args(["--palace", str(palace), "memory", "capture", "enable"])
    cmd_memory(args)
    assert json.loads(capsys.readouterr().out)["enabled"] is True
    local_workers(monkeypatch)
    args = parser.parse_args(["--palace", str(palace), "memory", "capture", "status"])
    cmd_memory(args)
    output = capsys.readouterr().out
    assert len(output.encode()) < 32768
    assert json.loads(output)["coverage"]["source_currentness"] == "last_observed_only"
    assert not any("capture" in name or "register" in name for name in SPECS)
    for bound in (0, -1, float("inf"), float("nan"), 31, True):
        with pytest.raises(ValueError):
            c.capture_tick(palace, max_seconds=bound)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS worker supervision")
def test_capture_roundtrip_through_guarded_worker(tmp_path):
    from tests.test_memory_runtime import parent

    palace, root = setup_root(tmp_path)
    source = original(root / "one.jsonl", "roundtrip evidence")
    value = parent(
        "from pathlib import Path;from cognitive_castle.memory_runtime import run_memory as run;"
        'p=Path(sys.argv[1]);a=run(p,"queue_source",dict(path=sys.argv[2],allowed_root=sys.argv[3],format="claude"));'
        'b=run(p,"capture_one",dict(key=a["source_key"]));'
        'c=run(p,"coverage",{});d=run(p,"recall",dict(query="roundtrip"));'
        'print(__import__("json").dumps(dict(a=a,b=b,c=c,d=d)))',
        str(palace),
        str(source),
        str(root),
    )
    print(
        "CAPTURE_WORKER_MEASUREMENTS "
        + json.dumps({name: value[name]["resources"] for name in ("a", "b", "c", "d")})
    )
    assert value["b"]["status"] == "ok", value
    assert value["c"]["pending_sources"] == 0
    assert value["d"]["sources"][0]["text"] == "roundtrip evidence"


def test_disappeared_directory_does_not_starve_other_directories(tmp_path):
    from cognitive_castle.memory_discovery import discover_sources

    palace, root = setup_root(tmp_path)
    (root / "a").mkdir()
    (root / "b").mkdir()
    original(root / "b" / "one.jsonl")
    store = MemoryStore(palace / ".memory")
    discover_sources(store, allowed_root=root, format="claude")
    (root / "a").rmdir()
    first = discover_sources(store, allowed_root=root, format="claude")
    assert first["discovery"] == "incomplete"
    assert first["reason"] == "discovery_directory_unavailable"
    second = discover_sources(store, allowed_root=root, format="claude")
    assert second["queued_sources"] == 1
    assert second["discovery"] == "incomplete"


def test_new_event_during_queueing_survives_for_next_tick(tmp_path, monkeypatch):
    from cognitive_castle.memory_worker import _execute

    c = coordinator()
    palace, root = setup_root(tmp_path)
    c.configure_capture(palace, enabled=True)
    source = original(root / "one.jsonl")
    fd = c._coordinator_lock(palace)
    try:
        c.handle_capture_event(palace, source, str(tmp_path / "old"), "claude")
    finally:
        os.close(fd)
    first = True

    def worker(palace, operation, arguments, **kw):
        nonlocal first
        value = _execute(dict(palace=str(palace), operation=operation, arguments=arguments))
        if operation == "queue_source" and first:
            first = False
            c.handle_capture_event(palace, source, str(tmp_path / "new"), "claude")
        return value

    monkeypatch.setattr(c, "run_memory", worker)
    c.capture_tick(palace, discover=False)
    assert c.capture_status(palace)["spooled_events"] == 1
    c.capture_tick(palace, discover=False)
    assert c.capture_status(palace)["spooled_events"] == 0
    assert source_page(MemoryStore(palace / ".memory"))["sources"][0]["workspace"] == str(
        tmp_path / "new"
    )


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS worker supervision")
def test_hook_launches_short_lived_coordinator_and_catches_up(tmp_path):
    from tests.test_memory_runtime import parent

    palace, root = setup_root(tmp_path)
    source = original(root / "one.jsonl", "detached coordinator")
    value = parent(
        "from pathlib import Path;import time,json;"
        "from cognitive_castle.memory_coordinator import configure_capture,handle_capture_event;"
        "p=Path(sys.argv[1]);configure_capture(p,enabled=True);t=time.monotonic();"
        'event=handle_capture_event(p,sys.argv[2],sys.argv[3],"claude");elapsed=time.monotonic()-t;'
        'last=p/".memory"/"capture-last.json";end=time.monotonic()+7;'
        "\nwhile not last.exists() and time.monotonic()<end: time.sleep(.02)\n"
        "print(json.dumps(dict(event=event,elapsed=elapsed,last=json.loads(last.read_text()) if last.exists() else None)))",
        str(palace),
        str(source),
        str(tmp_path),
    )
    print("CAPTURE_HOOK_SECONDS " + str(value["elapsed"]))
    assert value["elapsed"] < 0.5
    assert value["event"]["catch_up"]["status"] == "scheduled"
    assert value["last"]["successful_slices"] == 1, value


def test_event_arriving_at_spool_acknowledgement_is_not_deleted(tmp_path, monkeypatch):
    c = coordinator()
    palace, root = setup_root(tmp_path)
    c.configure_capture(palace, enabled=True)
    source = original(root / "one.jsonl")
    fd = c._coordinator_lock(palace)
    try:
        c.handle_capture_event(palace, source, str(tmp_path / "old"), "claude")
    finally:
        os.close(fd)
    local_workers(monkeypatch)
    unlink = Path.unlink
    first = True

    def concurrent_delivery(path, *args, **kw):
        nonlocal first
        if path.parent.name == "capture-spool" and first:
            first = False
            c.handle_capture_event(palace, source, str(tmp_path / "new"), "claude")
        return unlink(path, *args, **kw)

    monkeypatch.setattr(Path, "unlink", concurrent_delivery)
    c.capture_tick(palace, discover=False)
    assert c.capture_status(palace)["spooled_events"] == 1
    c.capture_tick(palace, discover=False)
    assert source_page(MemoryStore(palace / ".memory"))["sources"][0]["workspace"] == str(
        tmp_path / "new"
    )


def test_status_requires_every_registered_root_before_sweep_completion(tmp_path, monkeypatch):
    c = coordinator()
    palace, root = setup_root(tmp_path)
    second = tmp_path / "second"
    second.mkdir()
    _root_registry(palace, ("second", str(second), "claude"))
    c.configure_capture(palace, enabled=True)
    local_workers(monkeypatch)
    first = c.capture_tick(palace)
    assert first["discovery_scope"] == "one_registered_root"
    status = c.capture_status(palace)["discovery"]
    assert status["coverage"] == "incomplete"
    assert len(status["roots"]) == 2
    c.capture_tick(palace)
    status = c.capture_status(palace)["discovery"]
    assert status["coverage"] == "complete_at_last_sweep"
    assert status["source_currentness"] == "last_observed_only"


def test_tick_resumes_after_first_source_page_and_counts_permanent_error(tmp_path, monkeypatch):
    from cognitive_castle.memory_capture import queue_source

    c = coordinator()
    palace, root = setup_root(tmp_path)
    c.configure_capture(palace, enabled=True)
    local_workers(monkeypatch)
    store = MemoryStore(palace / ".memory")
    sources = []
    for number in range(18):
        source = original(root / f"{number}.jsonl", tail=True)
        queued = queue_source(store, source, allowed_root=root, format="claude")
        sources.append((queued["source_key"], source))
    # One permanently missing original stays visible without starving later sources.
    sorted(sources)[0][1].unlink()
    first = c.capture_tick(palace, discover=False)
    second = c.capture_tick(palace, discover=False)
    assert first["failed_sources"] == 1
    assert first["successful_slices"] == 15
    assert second["successful_slices"] == 2
    assert coverage(store)["pending_sources"] == 17
    assert coverage(store)["failed_sources"] == 1


def test_revoked_registered_root_cannot_capture_already_queued_source(tmp_path, monkeypatch):
    from cognitive_castle.memory_capture import queue_source

    c = coordinator()
    palace, root = setup_root(tmp_path)
    c.configure_capture(palace, enabled=True)
    local_workers(monkeypatch)
    store = MemoryStore(palace / ".memory")
    source = original(root / "one.jsonl", "revoked original")
    queue_source(store, source, allowed_root=root, format="claude")
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    _root_registry(palace, ("test", str(replacement), "claude"))
    result = c.capture_tick(palace, discover=False)
    assert result["successful_slices"] == 0
    assert result["unauthorized_sources"] == 1
    assert coverage(store)["pending_sources"] == 1
    assert not store.recall("revoked")["sources"]
    _root_registry(palace, ("test", str(root), "claude"))
    assert c.capture_tick(palace, discover=False)["successful_slices"] == 1


def test_malformed_spool_metadata_is_visible_without_starving_valid_event(tmp_path, monkeypatch):
    c = coordinator()
    palace, root = setup_root(tmp_path)
    c.configure_capture(palace, enabled=True)
    local_workers(monkeypatch)
    fd = c._coordinator_lock(palace)
    try:
        c.handle_capture_event(palace, original(root / "one.jsonl"), str(tmp_path), "claude")
    finally:
        os.close(fd)
    bad = palace / ".memory" / "capture-spool" / "000.json"
    bad.write_text("{broken")
    bad.chmod(0o600)
    value = c.capture_tick(palace, discover=False)
    assert value["spool_errors"] == 1
    assert value["successful_slices"] == 1
    assert c.capture_status(palace)["spooled_events"] == 1


@pytest.mark.parametrize("raw", ["{broken", "[]", '{"source_after": {}}', '{"discovery_due": 1}'])
def test_malformed_progress_refuses_safely_and_remains_retryable(tmp_path, monkeypatch, raw):
    c = coordinator()
    palace, root = setup_root(tmp_path)
    c.configure_capture(palace, enabled=True)
    local_workers(monkeypatch)
    fd = c._coordinator_lock(palace)
    try:
        c.handle_capture_event(palace, original(root / "one.jsonl"), str(tmp_path), "claude")
    finally:
        os.close(fd)
    progress = palace / ".memory" / "capture-progress.json"
    progress.write_text(raw)
    progress.chmod(0o600)
    assert c.capture_tick(palace, discover=False)["reason"] == "invalid_capture_progress"
    assert c.capture_status(palace)["spooled_events"] == 1
    progress.unlink()
    assert c.capture_tick(palace, discover=False)["successful_slices"] == 1


def test_unsupported_capture_platform_fails_before_metadata_mutation(tmp_path, monkeypatch):
    c = coordinator()
    with monkeypatch.context() as patch:
        patch.setattr(c.os, "name", "nt")
        with pytest.raises(ValueError, match="unsupported"):
            c.configure_capture(tmp_path, enabled=True)
    assert not (tmp_path / ".memory").exists()


def priority_fixture(tmp_path, monkeypatch):
    from cognitive_castle.memory_capture import queue_source

    c = coordinator()
    palace, root = setup_root(tmp_path)
    c.configure_capture(palace, enabled=True)
    local_workers(monkeypatch)
    store = MemoryStore(palace / ".memory")
    sources = []
    for number in range(4):
        path = original(root / f"priority-{number}.jsonl", f"exact source {number}")
        queued = queue_source(store, path, allowed_root=root, format="claude")
        sources.append((queued["source_key"], path))
    sources.sort()
    active, old = sources[0], sources[-1]
    c._atomic(palace / ".memory" / "capture-progress.json", {"source_after": sources[1][0]})
    fd = c._coordinator_lock(palace)
    try:
        c.handle_capture_event(palace, active[1], str(tmp_path), "claude")
    finally:
        os.close(fd)
    return c, palace, root, store, active, old


def test_hook_source_behind_cursor_is_captured_before_old_backlog(tmp_path, monkeypatch):
    from cognitive_castle.memory_worker import _execute

    c, palace, _, store, active, old = priority_fixture(tmp_path, monkeypatch)
    first = True

    def worker(palace, operation, arguments, **kw):
        nonlocal first
        if operation == "capture_one" and first:
            first = False
            # The first actual committed source must be the host event, even
            # though the ordinary cursor is lexicographically beyond its key.
            value = _execute(dict(palace=str(palace), operation=operation, arguments=arguments))
            assert store.load_checkpoint(active[0]) is not None
            assert store.load_checkpoint(old[0]) is None
            return value
        return _execute(dict(palace=str(palace), operation=operation, arguments=arguments))

    monkeypatch.setattr(c, "run_memory", worker)
    assert c.capture_tick(palace, discover=False)["status"] == "ok"
    assert store.load_checkpoint(active[0])["offset"] == active[1].stat().st_size
    assert store.load_checkpoint(old[0]) is not None


def test_fresh_priority_survives_worker_refusal_after_queue_ack(tmp_path, monkeypatch):
    from cognitive_castle.memory_worker import _execute

    c, palace, _, store, active, _ = priority_fixture(tmp_path, monkeypatch)

    def worker(palace, operation, arguments, **kw):
        if operation == "capture_one":
            return {"status": "unavailable", "reason": "system_pressure_unavailable"}
        return _execute(dict(palace=str(palace), operation=operation, arguments=arguments))

    monkeypatch.setattr(c, "run_memory", worker)
    assert c.capture_tick(palace, discover=False)["reason"] == "system_pressure_unavailable"
    assert not list((palace / ".memory" / "capture-spool").glob("*.claimed"))
    local_workers(monkeypatch)
    assert c.capture_tick(palace, discover=False)["status"] == "ok"
    assert store.load_checkpoint(active[0]) is not None


def test_fresh_slices_resume_original_prefix_without_skipping_and_remain_fair(
    tmp_path, monkeypatch
):
    import cognitive_castle.memory_ingest as ingest

    c, palace, _, store, active, old = priority_fixture(tmp_path, monkeypatch)
    records = [
        json.dumps({"type": "user", "message": {"content": text}}) + "\n"
        for text in ("first exact žluťoučký", "second exact 😀", "third exact final")
    ]
    active[1].write_text("".join(records))
    monkeypatch.setattr(ingest, "MAX_RECORDS", 1)
    result = c.capture_tick(palace, discover=False)
    assert result["status"] == "ok"
    assert store.load_checkpoint(active[0])["offset"] == active[1].stat().st_size
    assert store.load_checkpoint(old[0])["offset"] == old[1].stat().st_size
    assert store.recall("žluťoučký")["sources"][0]["text"] == "first exact žluťoučký"
    assert store.recall("second")["sources"][0]["text"] == "second exact 😀"


def test_expensive_fresh_slices_cannot_starve_old_sources_or_discovery(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import cognitive_castle.memory_ingest as ingest
    from cognitive_castle.memory_worker import _execute

    c, palace, root, store, active, old = priority_fixture(tmp_path, monkeypatch)
    active[1].write_text(
        (json.dumps({"type": "user", "message": {"content": "fresh"}}) + "\n") * 20
    )
    unseen = original(root / "discover-me.jsonl", "new discovery evidence")
    clock = [0.0]
    monkeypatch.setattr(
        c, "time", SimpleNamespace(monotonic=lambda: clock[0], time_ns=time.time_ns)
    )
    monkeypatch.setattr(ingest, "MAX_RECORDS", 1)

    def worker(palace, operation, arguments, **kw):
        value = _execute(dict(palace=str(palace), operation=operation, arguments=arguments))
        if operation == "capture_one" and arguments["key"] == active[0]:
            clock[0] += 5.1
        return value

    monkeypatch.setattr(c, "run_memory", worker)
    # Discovery can insert its new source ahead of the last old key. Allow four
    # ordinary opportunities so this assertion does not depend on path hashes.
    for _ in range(8):
        c.capture_tick(palace)
    assert store.load_checkpoint(old[0]) is not None
    observed = source_page(store, limit=16)["sources"]
    assert str(unseen) in {item["path"] for item in observed}
    assert 0 < store.load_checkpoint(active[0])["offset"] < active[1].stat().st_size


def test_priority_commit_before_event_ack_recovers_after_crash(tmp_path, monkeypatch):
    c, palace, _, store, active, _ = priority_fixture(tmp_path, monkeypatch)
    unlink = Path.unlink

    def crash(path, *args, **kwargs):
        if path.suffix == ".claimed":
            raise SystemExit("crash before spool acknowledgement")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", crash)
        with pytest.raises(SystemExit, match="acknowledgement"):
            c.capture_tick(palace, discover=False)
    assert store.load_checkpoint(active[0]) is None
    assert c.capture_tick(palace, discover=False)["status"] == "ok"
    assert store.load_checkpoint(active[0])["offset"] == active[1].stat().st_size


def test_priority_capture_commit_before_scheduler_save_is_idempotent(tmp_path, monkeypatch):
    from cognitive_castle.memory_worker import _execute

    c, palace, _, store, active, _ = priority_fixture(tmp_path, monkeypatch)

    def crash(palace, operation, arguments, **kw):
        value = _execute(dict(palace=str(palace), operation=operation, arguments=arguments))
        if operation == "capture_one" and arguments["key"] == active[0]:
            raise SystemExit("crash after capture commit")
        return value

    with monkeypatch.context() as patch:
        patch.setattr(c, "run_memory", crash)
        with pytest.raises(SystemExit, match="capture commit"):
            c.capture_tick(palace, discover=False)
    before = store.load_checkpoint(active[0])
    local_workers(monkeypatch)
    c.capture_tick(palace, discover=False)
    assert store.load_checkpoint(active[0]) == before
    assert store.recall("exact")["sources"]


def test_priority_queue_full_retains_event_until_a_slot_is_available(tmp_path, monkeypatch):
    import cognitive_castle.memory_ingest as ingest

    c, palace, _, store, active, old = priority_fixture(tmp_path, monkeypatch)
    old[1].write_text(
        (json.dumps({"type": "user", "message": {"content": "still catching up"}}) + "\n") * 100
    )
    monkeypatch.setattr(c, "MAX_FRESH_SOURCES", 1)
    monkeypatch.setattr(ingest, "MAX_RECORDS", 1)
    c._atomic(palace / ".memory" / "capture-progress.json", {"fresh_keys": [old[0]]})
    first = c.capture_tick(palace, discover=False)
    assert first["fresh_priority_pending"] is True
    assert list((palace / ".memory" / "capture-spool").glob("*.claimed"))
    monkeypatch.setattr(ingest, "MAX_RECORDS", 128)
    c.capture_tick(palace, discover=False)
    assert store.load_checkpoint(active[0]) is not None
    assert not list((palace / ".memory" / "capture-spool").glob("*.claimed"))


@pytest.mark.parametrize("stalled", ["tail", "tail_after_gap", "missing"])
def test_stalled_priority_releases_slot_but_keeps_ordinary_pending_work(
    tmp_path, monkeypatch, stalled
):
    c, palace, _, store, active, old = priority_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(c, "MAX_FRESH_SOURCES", 1)
    if stalled == "missing":
        old[1].unlink()
    else:
        original(old[1], "unfinished tail", tail=True)
        if stalled == "tail_after_gap":
            old[1].write_text("{malformed}\n" + old[1].read_text())
    c._atomic(palace / ".memory" / "capture-progress.json", {"fresh_keys": [old[0]]})
    c.capture_tick(palace, discover=False)
    c.capture_tick(palace, discover=False)
    assert not list((palace / ".memory" / "capture-spool").glob("*.claimed"))
    assert store.load_checkpoint(active[0]) is not None
    observed = {row["source_key"]: row for row in source_page(store, limit=16)["sources"]}
    assert observed[old[0]]["state"] in {"pending", "failed"}
    assert observed[old[0]]["pending_bytes"] > 0


def test_several_hook_sources_are_enrolled_in_one_tick_without_starving_old_work(
    tmp_path, monkeypatch
):
    from cognitive_castle.memory_capture import source_key

    c, palace, root, store, active, old = priority_fixture(tmp_path, monkeypatch)
    fresh = [active]
    fd = c._coordinator_lock(palace)
    try:
        for number in range(4):
            path = original(root / f"new-hook-{number}.jsonl", f"new hook exact {number}")
            fresh.append((source_key(path, "claude"), path))
            c.handle_capture_event(palace, path, str(tmp_path), "claude")
    finally:
        os.close(fd)
    result = c.capture_tick(palace, discover=False)
    assert result["status"] == "ok"
    assert result["queued_sources"] == 5
    assert not list((palace / ".memory" / "capture-spool").glob("*.json"))
    for key, path in [*fresh, old]:
        assert store.load_checkpoint(key)["offset"] == path.stat().st_size


def test_priority_append_preserves_old_generation_receipt_and_exact_new_text(tmp_path, monkeypatch):
    from cognitive_castle.memory_capture import capture_one

    c, palace, _, store, active, _ = priority_fixture(tmp_path, monkeypatch)
    first = capture_one(store, active[0])
    assert first["status"] == "ok"
    before = store.load_checkpoint(active[0])
    prior_preview = store.recall("exact")["sources"][0]
    prior = store.read_sources([prior_preview["id"]])["sources"][0]
    exact = "fresh appended verbatim: žluťoučký 😀\nline two"
    with active[1].open("a") as stream:
        stream.write(json.dumps({"type": "user", "message": {"content": exact}}) + "\n")
    assert c.capture_tick(palace, discover=False)["status"] == "ok"
    after = store.load_checkpoint(active[0])
    assert after["generation"] == before["generation"]
    assert after["offset"] == active[1].stat().st_size > before["offset"]
    found = store.recall("appended")["sources"][0]
    assert found["text"] == exact
    assert found["provenance"]["caller"]["record_start"] == before["offset"]
    assert store.read_sources([prior["id"]])["sources"][0] == prior


def test_hook_only_ticks_cannot_erase_discovery_owed_by_reconciliation(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import cognitive_castle.memory_ingest as ingest
    from cognitive_castle.memory_worker import _execute

    c, palace, root, store, active, _ = priority_fixture(tmp_path, monkeypatch)
    active[1].write_text(
        (json.dumps({"type": "user", "message": {"content": "fresh"}}) + "\n") * 30
    )
    unseen = original(root / "not-yet-discovered.jsonl")
    c._atomic(
        palace / ".memory" / "capture-progress.json",
        {"fresh_keys": [active[0]], "turn": 2, "source_after": active[0]},
    )
    clock = [0.0]
    monkeypatch.setattr(
        c, "time", SimpleNamespace(monotonic=lambda: clock[0], time_ns=time.time_ns)
    )
    monkeypatch.setattr(ingest, "MAX_RECORDS", 1)

    def worker(palace, operation, arguments, **kw):
        value = _execute(dict(palace=str(palace), operation=operation, arguments=arguments))
        if operation == "capture_one" and arguments["key"] == active[0]:
            clock[0] += 5.1
        return value

    monkeypatch.setattr(c, "run_memory", worker)
    for _ in range(3):
        c.capture_tick(palace, discover=True)
        c.capture_tick(palace, discover=False)
    assert str(unseen) in {item["path"] for item in source_page(store, limit=16)["sources"]}


def test_owed_discovery_is_serviced_only_once_per_tick(tmp_path, monkeypatch):
    from cognitive_castle.memory_discovery import discovery_status

    c, palace, _, store, _, _ = priority_fixture(tmp_path, monkeypatch)
    c._atomic(palace / ".memory" / "capture-progress.json", {"discovery_due": True})
    assert c.capture_tick(palace)["status"] == "ok"
    assert discovery_status(store)["roots"][0]["completed_sweeps"] == 1
