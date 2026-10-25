"""Engine-free scheduling regressions; native process proofs require a slot."""

import json
import os
import pytest

from cognitive_castle import memory_runtime as runtime


@pytest.fixture
def admission(tmp_path, monkeypatch):
    if os.name != "posix":
        pytest.skip("POSIX flock admission only")
    directory = tmp_path / "admission"
    directory.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "_admission_directory", lambda: directory)
    monkeypatch.setattr(runtime.sys, "platform", "darwin")
    return directory


def test_background_capture_busy_never_signals_or_waits(tmp_path, admission, monkeypatch):
    held = runtime._admission()
    monkeypatch.setattr(runtime.time, "sleep", lambda *_: pytest.fail("background waited"))
    monkeypatch.setattr(runtime, "_supervise", lambda *a, **k: pytest.fail("spawned worker"))
    try:
        assert runtime.run_memory(tmp_path, "status", {}, background=True) == {
            "status": "unavailable",
            "reason": "memory_busy",
        }
        assert not (admission / "interactive.waiting").exists()
        with pytest.raises(BlockingIOError):
            runtime._admission()
    finally:
        os.close(held)


def test_background_capture_yields_to_live_waiter_before_admission(
    tmp_path, admission, monkeypatch
):
    waiter = runtime._waiting_marker()
    monkeypatch.setattr(runtime, "_admission", lambda: pytest.fail("acquired ahead of waiter"))
    try:
        assert (
            runtime.run_memory(tmp_path, "status", {}, background=True)["reason"] == "memory_busy"
        )
    finally:
        os.close(waiter)


def test_background_capture_rechecks_waiter_after_acquiring(tmp_path, admission, monkeypatch):
    acquire, waiting = runtime._admission, []

    def raced_acquire():
        fd = acquire()
        waiting.append(runtime._waiting_marker())
        return fd

    monkeypatch.setattr(runtime, "_admission", raced_acquire)
    monkeypatch.setattr(
        runtime, "_supervise", lambda *a, **k: pytest.fail("spawned ahead of waiter")
    )
    try:
        assert (
            runtime.run_memory(tmp_path, "status", {}, background=True)["reason"] == "memory_busy"
        )
        probe = acquire()  # Refusal closed the acquired admission descriptor.
        os.close(probe)
    finally:
        for waiter in waiting:
            os.close(waiter)


def test_foreground_default_still_signals_and_waits_for_background(
    tmp_path, admission, monkeypatch
):
    held = [runtime._admission()]

    def yield_background(_seconds):
        assert runtime.interactive_waiting()
        os.close(held.pop())

    def supervise(request, fd, **kwargs):
        assert not kwargs.get("background_preempt", False)
        assert request["operation"] == "status"
        with pytest.raises(BlockingIOError):
            runtime._admission()
        return {"status": "ok"}

    monkeypatch.setattr(runtime.time, "sleep", yield_background)
    monkeypatch.setattr(runtime, "_supervise", supervise)
    try:
        assert runtime.run_memory(tmp_path, "status", {}) == {"status": "ok"}
        assert not runtime.interactive_waiting()
    finally:
        for fd in held:
            os.close(fd)


def test_background_capture_enables_supervisor_priority_checks(tmp_path, admission, monkeypatch):
    def supervise(request, fd, **kwargs):
        assert kwargs["background_preempt"] is True
        assert 0 < kwargs["deadline"] <= 2
        return {"status": "ok"}

    monkeypatch.setattr(runtime, "_supervise", supervise)
    assert runtime.run_memory(tmp_path, "status", {}, background=True) == {"status": "ok"}


def test_background_capture_supervisor_refuses_waiter_before_spawn(admission, monkeypatch):
    waiter = runtime._waiting_marker()
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *a, **k: pytest.fail("spawned"))
    try:
        assert (
            runtime._supervise({}, -1, background_preempt=True)["reason"] == "background_preempted"
        )
    finally:
        os.close(waiter)


def test_background_capture_coordinator_preserves_spool_when_admission_busy(
    tmp_path, admission, monkeypatch
):
    from cognitive_castle import memory_coordinator as coordinator
    from cognitive_castle.brain_api import _root_registry

    palace, originals = tmp_path / "palace", tmp_path / "originals"
    palace.mkdir()
    originals.mkdir()
    _root_registry(palace, ("test", str(originals), "claude"))
    coordinator.configure_capture(palace, enabled=True)
    source = originals / "capture.jsonl"
    source.write_text(
        json.dumps({"type": "user", "message": {"content": "preserve exactly"}}) + "\n"
    )
    lock = coordinator._coordinator_lock(palace)
    try:
        assert coordinator.handle_capture_event(palace, source, str(tmp_path), "claude")["queued"]
    finally:
        os.close(lock)
    spool = palace / ".memory/capture-spool"
    before = {p.name: p.read_bytes() for p in spool.iterdir()}
    held = runtime._admission()
    monkeypatch.setattr(runtime.time, "sleep", lambda *_: pytest.fail("capture waited"))
    monkeypatch.setattr(runtime, "_supervise", lambda *a, **k: pytest.fail("spawned worker"))
    try:
        assert coordinator.capture_tick(palace, discover=False)["reason"] == "memory_busy"
        assert not runtime.interactive_waiting()
        # The durable claim rename is allowed; its exact event remains pending.
        assert sorted(p.read_bytes() for p in spool.iterdir()) == sorted(before.values())
        assert not list((palace / ".memory").glob("*.sqlite*"))
    finally:
        os.close(held)


@pytest.mark.parametrize("background", [None, 1, "true"])
def test_background_capture_policy_is_trusted_boolean(tmp_path, background):
    with pytest.raises(ValueError):
        runtime.run_memory(tmp_path, "status", {}, background=background)


@pytest.mark.parametrize("late", [False, True])
def test_bounded_probe_preserves_feature_bool_and_rejects_late_stage(monkeypatch, late):
    from cognitive_castle import brain_reader_guardian as guardian

    now, timeouts = [100.0], []
    monkeypatch.setattr(guardian.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(guardian.sys, "platform", "darwin")

    def probe(*args, **kwargs):
        timeouts.append(kwargs["timeout"])
        if late:
            now[0] += 1
        return b"1\n"

    monkeypatch.setattr(guardian.subprocess, "check_output", probe)
    assert guardian._pressure_ok() is True
    assert timeouts == [0.5]
    until = now[0] + 0.02
    assert guardian._pressure_reason(until, guardian._pressure_ok) == (
        "worker_deadline" if late else None
    )
    assert 0 < timeouts[-1] <= 0.021


def test_background_probe_yields_to_waiter_even_when_probe_times_out(admission, monkeypatch):
    waiting = []

    def slow_probe(until, diagnostic, site, sample_resources=None):
        assert 0 < until - runtime.time.monotonic() <= 2.001
        waiting.append(runtime._waiting_marker())
        return "system_pressure_unavailable"

    monkeypatch.setattr(runtime, "_background_pressure_refusal", slow_probe)
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *a, **k: pytest.fail("spawned"))
    try:
        assert (
            runtime._supervise({}, -1, background_preempt=True)["reason"] == "background_preempted"
        )
    finally:
        for fd in waiting:
            os.close(fd)
