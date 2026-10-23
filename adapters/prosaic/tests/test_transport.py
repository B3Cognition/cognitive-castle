from concurrent.futures import ThreadPoolExecutor
import os
import subprocess
import threading
import time

import pytest


def context(*, timeout=10, cancelled=lambda: False):
    from prosaic_runtime import ToolExecutionContext, InvocationScope

    return ToolExecutionContext(
        InvocationScope("invocation"),
        "memory_search",
        "v1",
        0,
        "0" * 64,
        time.monotonic() + timeout,
        cancelled,
    )


def test_constructor_is_lazy_and_reads_reuse_bound_worker(provider):
    memory, marker = provider()
    assert not marker.exists()
    assert memory.health() == {"healthy": True}
    pid = marker.read_text()
    assert memory.search("exact query")["hits"][0]["excerpt"] == "exact query"

    assert memory.fetch("one")["text"] == "exact source"
    assert memory.snapshot(["one"])["texts"] == ["exact source"]
    assert marker.read_text() == pid
    assert marker.with_suffix(".calls").read_text().splitlines() == [
        "hello",
        "health",
        "search",
        "fetch",
        "snapshot",
    ]


@pytest.mark.parametrize("profile", ["memory-fts-v1", "memory-v1"])
def test_host_selected_profile_is_bound_and_mismatch_is_rejected(provider, profile):
    from prosaic_memory_castle import MemoryProviderError

    memory, _ = provider(profile=profile)
    assert memory.health() == {"healthy": True}
    assert memory._transport.hello["profile"] == profile
    wrong, _ = provider("profile_mismatch", profile=profile)
    with pytest.raises(MemoryProviderError, match="incompatible_store"):
        wrong.health()


@pytest.mark.parametrize(
    "argv", [(), ("python",), ("/absolute/python", 1), ("/absolute/python", "")]
)
def test_worker_command_never_uses_path_lookup(argv):
    from prosaic_memory_castle import WorkerCommand

    with pytest.raises(ValueError):
        WorkerCommand(argv)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(palace_path="relative"),
        dict(config_path="relative"),
        dict(namespace=""),
        dict(allowed_wings=()),
        dict(allowed_wings=("all", "all")),
        dict(operation_timeout=0),
        dict(startup_timeout=float("inf")),
        dict(profile="max"),
    ],
)
def test_invalid_host_grants_are_rejected_without_spawn(worker, tmp_path, kwargs):
    from prosaic_memory_castle import CastleMemoryProvider

    command, marker = worker()
    options = dict(
        palace_path=tmp_path / "palace",
        namespace="tenant",
        config_path=tmp_path / "cfg",
        allowed_wings=("all",),
    )
    with pytest.raises(ValueError):
        CastleMemoryProvider(command, **(options | kwargs))
    assert not marker.exists()


@pytest.mark.parametrize(
    "mode",
    [
        "bad_hello",
        "bad_fingerprint",
        "bad_id",
        "oversize",
        "eof",
        "raw_error",
        "duplicate",
        "nonfinite",
    ],
)
def test_invalid_worker_output_is_bounded_safe_and_process_terminates(provider, mode):
    from prosaic_memory_castle import MemoryProviderError

    memory, marker = provider(mode, operation_timeout=0.8, startup_timeout=0.8)
    started = time.monotonic()
    with pytest.raises(MemoryProviderError) as failure:
        memory.search("never in argv")
    assert failure.value.code in {"incompatible_store", "unavailable", "result_limit"}
    assert str(failure.value) == failure.value.code
    assert time.monotonic() - started < 2
    with pytest.raises(ProcessLookupError):
        os.kill(int(marker.read_text()), 0)


def test_large_stderr_does_not_deadlock_or_leak(provider):
    memory, marker = provider("stderr")
    assert memory.search("needle")["hits"][0]["excerpt"] == "needle"
    assert len(memory._transport.stderr_tail) <= 65536


def test_domain_error_stays_failure_and_does_not_poison_worker(provider):
    from prosaic_memory_castle import MemoryProviderError

    memory, marker = provider("error")
    for _ in range(2):
        with pytest.raises(MemoryProviderError, match="^not_found$"):
            memory.fetch("one")
    assert marker.with_suffix(".calls").read_text().splitlines() == ["hello", "fetch", "fetch"]


@pytest.mark.parametrize("mode", ["hang_start", "hang_read"])
def test_local_timeout_includes_cold_start_and_tears_down_worker(provider, mode):
    from prosaic_memory_castle import MemoryProviderError

    memory, marker = provider(mode, operation_timeout=0.2, startup_timeout=10)
    started = time.monotonic()
    with pytest.raises(MemoryProviderError, match="^timeout$"):
        memory.search("needle")
    assert time.monotonic() - started < 1.5
    with pytest.raises(ProcessLookupError):
        os.kill(int(marker.read_text()), 0)


def test_configured_startup_timeout_can_narrow_read_operation_timeout(provider):
    from prosaic_memory_castle import MemoryProviderError

    memory, _ = provider("hang_start", startup_timeout=0.05, operation_timeout=0.4)
    started = time.monotonic()
    with pytest.raises(MemoryProviderError, match="^timeout$"):
        memory.search("needle")
    assert time.monotonic() - started < 0.25


@pytest.mark.parametrize("kind", ["cancel", "deadline"])
def test_parent_control_path_survives_cold_start(provider, kind):
    from prosaic_runtime.events import Cancelled
    from prosaic_runtime.tools import ToolDeadlineExceeded

    memory, marker = provider("hang_start", operation_timeout=10)
    stopped = threading.Event()
    timer = threading.Timer(0.1, stopped.set)
    ctx = context(
        timeout=0.1 if kind == "deadline" else 10,
        cancelled=stopped.is_set if kind == "cancel" else lambda: False,
    )
    timer.start()
    try:
        with pytest.raises(Cancelled if kind == "cancel" else ToolDeadlineExceeded):
            memory.search("needle", _context=ctx)
    finally:
        timer.cancel()
    with pytest.raises(ProcessLookupError):
        os.kill(int(marker.read_text()), 0)


def test_queued_cancellation_dispatches_nothing_and_keeps_active_request(provider):
    from prosaic_runtime.events import Cancelled

    memory, marker = provider("slow")
    memory.health()
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(memory.search, "first")
        end = time.monotonic() + 2
        while "search" not in marker.with_suffix(".calls").read_text() and time.monotonic() < end:
            time.sleep(0.005)
        stopped = threading.Event()
        timer = threading.Timer(0.03, stopped.set)
        timer.start()
        try:
            with pytest.raises(Cancelled):
                memory.search("second", _context=context(cancelled=stopped.is_set))
        finally:
            timer.cancel()
        assert first.result(timeout=2)["hits"][0]["excerpt"] == "first"
    assert marker.with_suffix(".calls").read_text().splitlines().count("search") == 1


def test_parent_deadline_while_queued_keeps_active_request(provider):
    from prosaic_runtime.tools import ToolDeadlineExceeded

    memory, marker = provider("slow")
    memory.health()
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(memory.search, "first")
        end = time.monotonic() + 2
        while "search" not in marker.with_suffix(".calls").read_text() and time.monotonic() < end:
            time.sleep(0.005)
        with pytest.raises(ToolDeadlineExceeded):
            memory.search("second", _context=context(timeout=0.03))
        assert first.result(timeout=2)["hits"][0]["excerpt"] == "first"
    assert marker.with_suffix(".calls").read_text().splitlines().count("search") == 1


def test_timeout_kills_worker_descendants(provider):
    from prosaic_memory_castle import MemoryProviderError

    memory, marker = provider("descendant", operation_timeout=0.3)
    with pytest.raises(MemoryProviderError, match="^timeout$"):
        memory.search("needle")
    child = int(marker.with_suffix(".child").read_text())
    until = time.monotonic() + 1
    while time.monotonic() < until:
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            break
        time.sleep(0.01)
    else:
        pytest.fail("worker descendant survived timeout")


def test_query_is_pipe_data_and_host_grants_are_fixed(provider):
    memory, marker = provider()
    memory.search("secret-query")
    args = memory._transport._process.args
    assert "secret-query" not in args
    assert "--namespace" in args and args[args.index("--namespace") + 1] == "tenant-a"
    assert args[args.index("--wing") + 1] == "project"


def test_independent_read_can_restart_worker_after_a_timeout(provider):
    from prosaic_memory_castle import MemoryProviderError

    memory, marker = provider("recover", operation_timeout=0.1)
    with pytest.raises(MemoryProviderError, match="^timeout$"):
        memory.search("first")
    old_pid = marker.read_text()
    assert memory.search("second")["hits"][0]["excerpt"] == "second"
    assert marker.read_text() != old_pid


def test_close_racing_process_creation_cannot_leave_a_new_worker_running(provider, monkeypatch):
    from prosaic_memory_castle import MemoryProviderError

    memory, marker = provider()
    spawned, proceed = threading.Event(), threading.Event()
    original = subprocess.Popen

    def controlled_spawn(*args, **kwargs):
        process = original(*args, **kwargs)
        spawned.set()
        assert proceed.wait(timeout=2)
        return process

    monkeypatch.setattr(subprocess, "Popen", controlled_spawn)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(memory.health)
        assert spawned.wait(timeout=2)
        memory.close()
        proceed.set()
        with pytest.raises(MemoryProviderError, match="^unavailable$"):
            pending.result(timeout=2)
    if marker.exists():
        with pytest.raises(ProcessLookupError):
            os.kill(int(marker.read_text()), 0)


def test_snapshot_enforces_returned_encoded_bundle_limit(provider):
    from prosaic_memory_castle import MemoryProviderError

    memory, _ = provider()
    with pytest.raises(MemoryProviderError, match="^result_limit$"):
        memory.snapshot(["one"], maximum_bytes=8)


@pytest.mark.parametrize(
    "expected",
    [
        {"one": {}},
        {"one": {"text_sha256": "wrong", "revision": None}},
        {"one": {"text_sha256": "a" * 64, "revision": []}},
        {"one": {"text_sha256": "a" * 64, "revision": None, "namespace": "other"}},
    ],
)
def test_invalid_snapshot_expectations_never_start_worker(provider, expected):
    from prosaic_memory_castle import MemoryProviderError

    memory, marker = provider()
    with pytest.raises(MemoryProviderError, match="^invalid_request$"):
        memory.snapshot(["one"], expected=expected)
    assert not marker.exists()


def test_parent_cancellation_takes_precedence_over_worker_domain_error(provider, monkeypatch):
    from prosaic_memory_castle import MemoryProviderError
    from prosaic_runtime.events import Cancelled

    memory, _ = provider("error")
    stopped = threading.Event()
    original = memory._transport._response

    def receive(*args):
        try:
            return original(*args)
        except MemoryProviderError:
            stopped.set()
            raise

    monkeypatch.setattr(memory._transport, "_response", receive)
    with pytest.raises(Cancelled):
        memory.fetch("one", _context=context(cancelled=stopped.is_set))
