"""History jobs share admission, with fixed budgets distinct from ordinary reads."""

import argparse
import importlib
import os
from pathlib import Path
import sys
import subprocess
import threading
import time

import pytest


def test_history_limits_do_not_change_fast_limits():
    from cognitive_castle import memory_runtime as runtime

    assert runtime.HISTORY_RSS == 512 * 1024**2
    assert runtime.HISTORY_TOTAL_RSS == 640 * 1024**2
    assert runtime.HISTORY_DEADLINE == 10
    assert runtime.WORKER_RSS == 128 * 1024**2
    assert runtime.TOTAL_RSS == 192 * 1024**2


def test_history_rejects_untrusted_budget_or_operation(tmp_path):
    from cognitive_castle import memory_runtime as runtime

    for operation, arguments in [
        ("prepare", {}),
        ("index", {"rss_limit": 2**40}),
        ("index-scopes", {"rss_limit": 2**40}),
        ("status", {"command": ["sh"]}),
        ("recall", {"query": "x"}),
    ]:
        with pytest.raises(ValueError):
            runtime.run_history(tmp_path, operation, arguments)
    assert not list(tmp_path.iterdir())


def test_history_unsupported_platform_before_storage(tmp_path, monkeypatch):
    from cognitive_castle import memory_runtime as runtime

    monkeypatch.setattr(runtime.sys, "platform", "linux")
    assert runtime.run_history(tmp_path, "status", {}) == {
        "status": "unavailable",
        "reason": "platform_supervision_unavailable",
    }
    assert not list(tmp_path.iterdir())


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS supervision only")
def test_history_same_admission_and_fixed_supervisor_configuration(tmp_path, monkeypatch):
    from cognitive_castle import memory_runtime as runtime

    seen = {}

    def supervise(request, admission, **kwargs):
        assert os.fstat(admission)
        seen.update(request=request, **kwargs)
        return {"status": "ok"}

    monkeypatch.setattr(runtime, "_supervise", supervise)
    held = runtime._admission()
    try:
        assert runtime.run_history(tmp_path, "index", {})["reason"] == "memory_busy"
    finally:
        os.close(held)
    assert runtime.run_history(tmp_path, "index", {})["status"] == "ok"
    assert seen["rss_limit"] == 512 * 1024**2
    assert seen["total_rss_limit"] == 640 * 1024**2
    assert seen["deadline"] == 8  # Reserve two seconds for process cleanup.
    assert Path(seen["worker_command"][-1]).name == "memory_history_worker.py"
    assert seen["request"]["operation"] == "index"
    # Admission was released after return.
    os.close(runtime._admission())


def test_pressure_rejection_happens_before_launch(monkeypatch):
    from cognitive_castle import memory_runtime as runtime

    monkeypatch.setattr(runtime, "_pressure_ok", lambda **kwargs: False)
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *a, **k: pytest.fail("launched"))
    assert (
        runtime._supervise({}, -1, rss_limit=512 * 1024**2, total_rss_limit=640 * 1024**2)["reason"]
        == "system_pressure_unavailable"
    )


def test_history_worker_lazy_imports():
    module = importlib.import_module("cognitive_castle.memory_history_worker")
    assert callable(module.main)
    guard = module._ForbiddenImports()
    for dependency in ("torch", "sentence_transformers", "requests", "openai"):
        with pytest.raises(ModuleNotFoundError):
            guard.find_spec(dependency, None)
    assert guard.find_spec("lance", None) is None


def test_history_parser_does_not_accept_resource_overrides():
    from cognitive_castle.history_cli import configure_history_parser

    parser = argparse.ArgumentParser()
    actions = parser.add_subparsers(dest="memory_action", required=True)
    configure_history_parser(actions)
    args = parser.parse_args(["history", "prepare", "--source", "/tmp/archive.lance"])
    assert args.history_action == "prepare"
    assert args.source == "/tmp/archive.lance"
    args = parser.parse_args(["history", "index-scopes"])
    assert args.history_action == "index-scopes"
    with pytest.raises(SystemExit):
        parser.parse_args(["history", "index", "--rss-limit", "999999"])


def test_history_scope_index_cli_dispatches_operator_action(tmp_path, monkeypatch):
    from cognitive_castle import memory_runtime as runtime
    from cognitive_castle.history_cli import cmd_history, configure_history_parser

    parser = argparse.ArgumentParser()
    configure_history_parser(parser.add_subparsers(dest="memory_action", required=True))
    args = parser.parse_args(["history", "index-scopes"])
    seen = {}

    def run_history(palace, operation, arguments):
        seen.update(palace=palace, operation=operation, arguments=arguments)
        return {"status": "pending", "state": "pending"}

    monkeypatch.setattr(runtime, "run_history", run_history)
    result = cmd_history(tmp_path, args)

    assert result == {"status": "pending", "state": "pending"}
    assert seen == {"palace": tmp_path, "operation": "index-scopes", "arguments": {}}


def test_history_operation_routes_scope_index_without_native_reader(monkeypatch, tmp_path):
    from cognitive_castle import memory_history, memory_scope_indexes

    expected = {"status": "pending", "state": "pending", "index": "unified_chunk_workspace_v1"}
    seen = {}

    def index_workspace_scope(palace, *, deadline, interactive_waiting):
        seen.update(palace=palace, deadline=deadline, interactive_waiting=interactive_waiting)
        return expected

    monkeypatch.setattr(memory_scope_indexes, "index_workspace_scope", index_workspace_scope)
    monkeypatch.setattr(memory_history, "_interactive_waiting", lambda: False)

    result = memory_history.history_operation(tmp_path, "index-scopes", {})

    assert result == expected
    assert seen["palace"] == tmp_path
    assert callable(seen["interactive_waiting"])


def test_history_runtime_accepts_scope_index_action_without_budget_fields(tmp_path, monkeypatch):
    from cognitive_castle import memory_runtime as runtime

    monkeypatch.setattr(runtime.sys, "platform", "linux")

    result = runtime.run_history(tmp_path, "index-scopes", {})

    assert result == {
        "status": "unavailable",
        "reason": "platform_supervision_unavailable",
    }
    assert not list(tmp_path.iterdir())


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS supervision only")
def test_operator_repair_parses_exact_cursor_and_uses_history_supervision(tmp_path, monkeypatch):
    from cognitive_castle import memory_runtime as runtime
    from cognitive_castle.history_cli import cmd_history, configure_history_parser

    seen = {}

    def supervise(request, admission, **kwargs):
        assert os.fstat(admission)
        seen.update(request=request, **kwargs)
        return {"status": "repair_refused", "reason": "no_eligible_gap"}

    monkeypatch.setattr(runtime, "_supervise", supervise)
    parser = argparse.ArgumentParser()
    configure_history_parser(parser.add_subparsers(dest="memory_action", required=True))
    args = parser.parse_args(
        [
            "history",
            "repair",
            "--store-id",
            "a" * 64,
            "--fragment",
            "18006",
            "--offset",
            "142997",
            "--row-address",
            "77335181274772",
        ]
    )
    assert cmd_history(tmp_path, args)["status"] == "repair_refused"
    assert seen["request"]["arguments"] == {
        "store_id": "a" * 64,
        "cursor": {"fragment": 18006, "offset": 142997, "row_address": 77335181274772},
    }
    assert seen["request"]["operation"] == "repair"
    assert seen["rss_limit"] == 512 * 1024**2
    assert seen["total_rss_limit"] == 640 * 1024**2
    assert seen["deadline"] == 8


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"store_id": "../escape", "cursor": {}},
        {"store_id": "a" * 64, "cursor": []},
        {"store_id": "a" * 64, "cursor": {}, "rss_limit": 2**40},
    ],
)
def test_repair_invalid_parent_envelope_never_launches(tmp_path, monkeypatch, arguments):
    from cognitive_castle import memory_runtime as runtime

    monkeypatch.setattr(runtime, "_supervise", lambda *a, **k: pytest.fail("launched"))
    with pytest.raises(ValueError):
        runtime.run_history(tmp_path, "repair", arguments)
    assert not list(tmp_path.iterdir())


@pytest.fixture
def priority_runtime(tmp_path, monkeypatch):
    from cognitive_castle import memory_runtime as runtime

    if os.name != "posix":
        pytest.skip("private POSIX admission")
    directory = tmp_path / "admission"
    directory.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "_admission_directory", lambda: directory, raising=False)
    return runtime, directory


def test_priority_marker_live_waiters_release_on_close_and_stale_file_is_inert(priority_runtime):
    runtime, directory = priority_runtime
    assert runtime.interactive_waiting() is False
    first = runtime._waiting_marker()
    second = runtime._waiting_marker()
    try:
        assert runtime.interactive_waiting() is True
        os.close(first)
        first = None
        assert runtime.interactive_waiting() is True
        # Priority is scheduling, never authority or a replacement admission lock.
        os.close(runtime._admission())
    finally:
        if first is not None:
            os.close(first)
        os.close(second)
    assert (directory / "interactive.waiting").exists()
    assert runtime.interactive_waiting() is False


@pytest.mark.parametrize("unsafe", ["symlink", "content", "public", "hardlink"])
def test_unsafe_priority_markers_fail_closed(priority_runtime, tmp_path, unsafe):
    runtime, directory = priority_runtime
    marker = directory / "interactive.waiting"
    if unsafe == "symlink":
        target = tmp_path / "target"
        target.write_bytes(b"")
        marker.symlink_to(target)
    else:
        marker.touch(mode=0o600)
        if unsafe == "content":
            marker.write_text("forged process request")
        elif unsafe == "public":
            marker.chmod(0o644)
        else:
            os.link(marker, directory / "alias")
    assert runtime.interactive_waiting() is True
    with pytest.raises(OSError):
        runtime._waiting_marker()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS supervision only")
def test_history_yields_admission_to_active_fast_waiter(priority_runtime, tmp_path, monkeypatch):
    runtime, _ = priority_runtime
    seen = []
    monkeypatch.setattr(runtime, "_supervise", lambda *a, **kw: seen.append(kw) or {"status": "ok"})
    marker = runtime._waiting_marker()
    try:
        assert runtime.run_history(tmp_path, "index", {})["reason"] == "memory_busy"
        assert seen == []
    finally:
        os.close(marker)
    assert runtime.run_history(tmp_path, "index", {})["status"] == "ok"


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS supervision only")
@pytest.mark.parametrize("failed", [False, True])
def test_fast_waiter_gets_released_slow_admission_and_preserves_remaining_budget(
    priority_runtime, tmp_path, monkeypatch, failed
):
    runtime, _ = priority_runtime
    held = runtime._admission()
    yielded = threading.Event()
    deadline = []

    def slow_checkpoint():
        try:
            end = time.monotonic() + 0.4
            while time.monotonic() < end and not runtime.interactive_waiting():
                time.sleep(0.005)
            if runtime.interactive_waiting():
                yielded.set()
        finally:
            os.close(held)

    def supervise(request, fd, **kwargs):
        assert yielded.is_set()
        assert os.fstat(fd)
        deadline.append(kwargs["deadline"])
        if failed:
            raise RuntimeError("synthetic supervisor failure")
        return {"status": "ok"}

    monkeypatch.setattr(runtime, "_supervise", supervise)
    slow = threading.Thread(target=slow_checkpoint)
    slow.start()
    try:
        if failed:
            with pytest.raises(RuntimeError, match="synthetic"):
                runtime.run_memory(tmp_path, "recall", {"query": "needle"})
        else:
            assert runtime.run_memory(tmp_path, "recall", {"query": "needle"})["status"] == "ok"
    finally:
        slow.join(timeout=1)
    assert yielded.is_set()
    assert 1.4 < deadline[0] < 2
    assert runtime.interactive_waiting() is False
    os.close(runtime._admission())


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS supervision only")
@pytest.mark.parametrize("max_seconds, wait_cap", [(None, 0.5), (0.075, 0.075)])
def test_fast_admission_wait_is_bounded_by_original_deadline_and_cleans_marker(
    priority_runtime, tmp_path, monkeypatch, max_seconds, wait_cap
):
    runtime, _ = priority_runtime
    held = runtime._admission()
    monkeypatch.setattr(
        runtime, "_supervise", lambda *a, **kw: pytest.fail("admission not acquired")
    )
    started = time.monotonic()
    try:
        result = runtime.run_memory(
            tmp_path, "recall", {"query": "needle"}, max_seconds=max_seconds
        )
        assert result["reason"] == "memory_busy"
        assert time.monotonic() - started < wait_cap + 0.15
        assert runtime.interactive_waiting() is False
        with pytest.raises(BlockingIOError):
            runtime._admission()
    finally:
        os.close(held)
    assert not (tmp_path / ".memory").exists()


def test_dead_waiter_does_not_leave_active_priority(priority_runtime):
    runtime, directory = priority_runtime
    root = str(Path(__file__).resolve().parents[1])
    script = (
        f"import sys;sys.path.insert(0,{root!r});"
        "from pathlib import Path;"
        "from cognitive_castle import memory_runtime as r;"
        "r._admission_directory=lambda:Path(sys.argv[1]);"
        "fd=r._waiting_marker();print('ready',flush=True);sys.stdin.read()"
    )
    process = subprocess.Popen(
        [sys.executable, "-I", "-c", script, str(directory)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        import selectors

        with selectors.DefaultSelector() as ready:
            ready.register(process.stdout, selectors.EVENT_READ)
            assert ready.select(timeout=3), "waiter failed to start"
            assert process.stdout.readline() == "ready\n"
        assert runtime.interactive_waiting() is True
        process.kill()
        process.wait(timeout=3)
        assert runtime.interactive_waiting() is False
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=3)
