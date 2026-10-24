"""History jobs share admission, with fixed budgets distinct from ordinary reads."""

import argparse
import importlib
import os
from pathlib import Path
import sys

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

    monkeypatch.setattr(runtime, "_pressure_ok", lambda: False)
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
    with pytest.raises(SystemExit):
        parser.parse_args(["history", "index", "--rss-limit", "999999"])
