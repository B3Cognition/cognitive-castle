"""Disposable history converter. Native decoding belongs only in this worker."""

from __future__ import annotations

import importlib.abc
import json
import os
from pathlib import Path
import sys

MAX_FRAME = 512 * 1024


class _ForbiddenImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {
            "torch",
            "transformers",
            "sentence_transformers",
            "tensorflow",
            "mlx",
            "ollama",
            "openai",
            "anthropic",
            "requests",
            "httpx",
        } or fullname.startswith(
            (
                "cognitive_castle.embedding",
                "cognitive_castle.backends",
                "cognitive_castle.searcher",
                "cognitive_castle.reranker",
                "cognitive_castle.llm",
            )
        ):
            # Optional native-library discovery catches ModuleNotFoundError;
            # advertise forbidden dependencies as absent without importing them.
            raise ModuleNotFoundError("history worker forbids models and providers")
        return None


def _install_guards():
    sys.meta_path.insert(0, _ForbiddenImports())

    def audit(event, args):
        if event.startswith("socket.") or event in {
            "subprocess.Popen",
            "os.system",
            "os.fork",
            "os.posix_spawn",
        }:
            raise PermissionError("history worker forbids network and child processes")

    sys.addaudithook(audit)


def _admit_storage(request):
    import psutil
    from cognitive_castle.brain_reader_guardian import _group_rss
    from cognitive_castle.memory_runtime import HISTORY_RSS, HISTORY_TOTAL_RSS

    guardian = psutil.Process(os.getppid())
    host = psutil.Process(request["_host_pid"])
    if guardian.ppid() != host.pid or sys.platform != "darwin":
        return {"status": "unavailable", "reason": "resource_measurement_unavailable"}
    task_rss = _group_rss(os.getpgrp())
    if task_rss > HISTORY_RSS:
        return {"status": "unavailable", "reason": "worker_memory_limit"}
    if task_rss + host.memory_info().rss > HISTORY_TOTAL_RSS:
        return {"status": "unavailable", "reason": "total_memory_limit"}
    return None


def main():
    os.umask(0o077)
    _install_guards()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        frame = sys.stdin.buffer.read(MAX_FRAME + 1)
        if len(frame) > MAX_FRAME:
            raise ValueError("request limit")
        request = json.loads(frame)
        result = _admit_storage(request)
        if result is None:
            from cognitive_castle.memory_worker import _sqlite_heap_limit
            from cognitive_castle.memory_history import history_operation

            _sqlite_heap_limit()
            result = history_operation(
                Path(request["palace"]), request["operation"], request["arguments"]
            )
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        result = {"status": "unavailable", "reason": "invalid_history_request"}
    except Exception as exc:
        result = {"status": "unavailable", "reason": "history_" + type(exc).__name__}
    output = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(output) > MAX_FRAME:
        output = b'{"status":"unavailable","reason":"worker_output_limit"}'
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
