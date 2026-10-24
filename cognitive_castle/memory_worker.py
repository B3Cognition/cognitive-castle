"""One private memory operation, isolated from models, networking and host SQLite.

Executed by absolute file path with Python isolation. No legacy backend imports.
"""

from __future__ import annotations

import importlib.abc
import json
import os
from pathlib import Path
import sqlite3
import sys

MAX_FRAME = 512 * 1024
SQLITE_HEAP_BYTES = 32 * 1024**2


class _ForbiddenImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split(".")[0]
        if root in {
            "torch",
            "transformers",
            "sentence_transformers",
            "lancedb",
            "pyarrow",
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
            raise ImportError("memory worker forbids model, provider and native backends")
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
            raise PermissionError("memory worker forbids network and child processes")

    sys.addaudithook(audit)


def _sqlite_heap_limit():
    # This is process-global SQLite configuration: never call in the host.
    with sqlite3.connect(":memory:") as conn:
        row = conn.execute(f"PRAGMA hard_heap_limit={SQLITE_HEAP_BYTES}").fetchone()
        if row is None or not 0 < row[0] <= SQLITE_HEAP_BYTES:
            raise RuntimeError("SQLite hard heap limit unavailable")


def _admit_storage(request):
    """Measure the complete live chain before touching the sidecar."""
    import psutil
    from cognitive_castle.brain_reader_guardian import _group_rss
    from cognitive_castle.memory_runtime import TOTAL_RSS, WORKER_RSS

    guardian = psutil.Process(os.getppid())
    host = psutil.Process(request["_host_pid"])
    if guardian.ppid() != host.pid or sys.platform != "darwin":
        return {"status": "unavailable", "reason": "resource_measurement_unavailable"}
    task_rss = _group_rss(os.getpgrp())
    if task_rss > WORKER_RSS:
        return {"status": "unavailable", "reason": "worker_memory_limit"}
    if task_rss + host.memory_info().rss > TOTAL_RSS:
        return {"status": "unavailable", "reason": "total_memory_limit"}
    return None


def _execute(request):
    from cognitive_castle.fast_memory import MemoryStore

    store = MemoryStore(Path(request["palace"]) / ".memory")
    operation = request["operation"]
    arguments = request["arguments"]
    if operation in {"restore_context", "update_context"}:
        from cognitive_castle import memory_context

        return getattr(memory_context, operation)(store, **arguments)
    if operation in {"queue_source", "capture_one", "coverage", "source_page"}:
        from cognitive_castle import memory_capture

        return getattr(memory_capture, operation)(store, **arguments)
    if operation in {"discover_sources", "discovery_status"}:
        from cognitive_castle import memory_discovery

        return getattr(memory_discovery, operation)(store, **arguments)
    if operation == "ingest_slice":
        from cognitive_castle.memory_ingest import ingest_slice

        return ingest_slice(
            store,
            Path(arguments["path"]),
            allowed_root=Path(arguments["allowed_root"]),
            format=arguments["format"],
        )
    result = getattr(store, operation)(**arguments)
    if operation == "recall" and result.get("status") == "ok":
        ids = [source["id"] for source in result["sources"]]
        if ids:
            exact = store.read_sources(ids)
            if exact["status"] != "ok":
                return exact
            result["sources"] = exact["sources"]
    return result


def main():
    os.umask(0o077)
    _install_guards()
    # -I removes cwd; this root comes from the installed worker path, not input.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        frame = sys.stdin.buffer.read(MAX_FRAME + 1)
        if len(frame) > MAX_FRAME:
            raise ValueError("request limit")
        request = json.loads(frame)
        result = _admit_storage(request)
        if result is None:
            _sqlite_heap_limit()
            result = _execute(request)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        result = {"status": "unavailable", "reason": "invalid_memory_request"}
    except Exception as exc:
        result = {"status": "unavailable", "reason": "memory_" + type(exc).__name__}
    output = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(output) > MAX_FRAME:
        output = b'{"status":"unavailable","reason":"worker_output_limit"}'
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
