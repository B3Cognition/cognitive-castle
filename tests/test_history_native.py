"""Qualification on real native files, with no native import in the host process."""

import json
import os
from pathlib import Path
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS owned-group supervision")


@pytest.mark.parametrize("oversized", [False, True])
def test_real_native_snapshot_conversion_and_deletion_resume(tmp_path, oversized):
    from cognitive_castle import memory_runtime as runtime
    from cognitive_castle.fast_memory import MemoryStore
    from cognitive_castle.unified_memory import UnifiedMemoryStore

    source = tmp_path / "source.lance"
    palace = tmp_path / "palace"
    palace.mkdir(mode=0o700)
    writer = Path(__file__).parent / "fixtures" / "history_native_fixture.py"
    admission = runtime._admission()
    try:
        result = runtime._supervise(
            {"source": str(source), "oversized": oversized},
            admission,
            worker_command=[sys.executable, "-I", str(writer)],
            deadline=8,
            rss_limit=runtime.HISTORY_RSS,
            total_rss_limit=runtime.HISTORY_TOTAL_RSS,
        )
    finally:
        os.close(admission)
    assert result["status"] == "ok", result
    assert result["rows"] == 5
    pinned = runtime.run_history(palace, "prepare", {"source": str(source)})
    assert pinned["status"] == "ok" and pinned["state"] == "prepared", pinned
    for _ in range(10):
        indexed = runtime.run_history(palace, "index", {})
        if indexed.get("state") in {"complete", "blocked"}:
            break
        assert indexed["status"] == "ok", indexed
    assert indexed["state"] == ("blocked" if oversized else "complete"), indexed
    assert indexed["indexed_rows"] == (4 if oversized else 5), indexed
    assert indexed["gaps"] == int(oversized), indexed
    fresh = MemoryStore(palace / ".memory").remember("fresh", "sharedneedle freshly captured")
    assert fresh["status"] == "ok"
    recall = UnifiedMemoryStore(palace).recall("sharedneedle", limit=8)
    assert recall["status"] == "ok", recall
    assert len(recall["sources"]) == (5 if oversized else 6), recall
    for found in recall["sources"]:
        page = UnifiedMemoryStore(palace).page(found["id"])
        assert page["status"] == "ok", page
        assert "sharedneedle" in page["text"]
    assert "vector" not in json.dumps(recall)
    # A second process invocation must reconcile receipts rather than duplicate.
    again = runtime.run_history(palace, "index", {})
    assert again["indexed_rows"] == indexed["indexed_rows"], again
