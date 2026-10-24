"""Qualification on real native files, with no native import in the host process."""

import json
import hashlib
import os
from pathlib import Path
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS owned-group supervision")


@pytest.mark.parametrize("oversized", [False, True])
def test_real_native_snapshot_conversion_and_deletion_resume(tmp_path, oversized, monkeypatch):
    from cognitive_castle import memory_runtime as runtime
    from cognitive_castle.brain_api import BrainAPI
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
    monkeypatch.setenv("CASTLE_BRAIN_HOST", "qualification")
    api = BrainAPI(palace)
    api.policy_path.parent.mkdir(mode=0o700, parents=True)
    api.policy_path.write_text('{"allow_local_sources":true}')
    api.policy_path.chmod(0o600)
    fresh = api.call(
        "castle_memory_remember",
        {"protocol_version": 1, "request_id": "fresh", "text": "sharedneedle freshly captured"},
    )
    assert fresh["status"] == "ok"
    recall = UnifiedMemoryStore(palace).recall("sharedneedle", limit=8)
    assert recall["status"] == "ok", recall
    assert len(recall["sources"]) == (5 if oversized else 6), recall
    for found in recall["sources"]:
        page = UnifiedMemoryStore(palace).page(found["id"])
        assert page["status"] == "ok", page
        assert "sharedneedle" in page["text"]
    assert "vector" not in json.dumps(recall)
    public = BrainAPI(palace).call("castle_brain_recall", {"query": "sharedneedle", "limit": 8})
    assert public["status"] == "ok", public
    assert {s["id"] for s in public["sources"]} == {s["id"] for s in recall["sources"]}
    for source in public["sources"]:
        exact = api.call(
            "castle_memory_read",
            {"protocol_version": 1, "source_id": source["id"], "expected_hash": source["hash"]},
        )
        assert exact["status"] == "ok", exact
        assert exact["text"].startswith("sharedneedle")
    # A second process invocation must reconcile receipts rather than duplicate.
    again = runtime.run_history(palace, "index", {})
    assert again["status"] == "ok", again
    assert again["indexed_rows"] == indexed["indexed_rows"], again


@pytest.mark.parametrize("streamed", [False, True])
def test_native_large_text_preserves_every_chunk_under_existing_guard(tmp_path, streamed):
    from cognitive_castle import memory_runtime as runtime
    from cognitive_castle.fast_memory import MemoryStore
    from cognitive_castle.memory_history import _load_job
    from cognitive_castle.unified_memory import UnifiedMemoryStore, history_store_path

    source = tmp_path / "source.lance"
    palace = tmp_path / "palace"
    palace.mkdir(mode=0o700)
    writer = Path(__file__).parent / "fixtures" / "history_native_fixture.py"
    admission = runtime._admission()
    try:
        result = runtime._supervise(
            {"source": str(source), "stream_text" if streamed else "large_text": True},
            admission,
            worker_command=[sys.executable, "-I", str(writer)],
            deadline=8,
            rss_limit=runtime.HISTORY_RSS,
            total_rss_limit=runtime.HISTORY_TOTAL_RSS,
        )
    finally:
        os.close(admission)
    assert result["status"] == "ok", result
    assert runtime.run_history(palace, "prepare", {"source": str(source)})["state"] == "prepared"
    pending_states = set()
    previous_projected_character = 0
    for _ in range(20):
        result = runtime.run_history(palace, "index", {})
        assert result["status"] == "ok", result
        if result.get("partial_row"):
            pending_states.add(result["partial_row"]["state"])
            progress = result["partial_row"]["processed_characters"]
            assert 0 <= progress - previous_projected_character <= 4 * 131072
            previous_projected_character = progress
            job = _load_job(palace)
            store = MemoryStore(history_store_path(palace, job["store_id"]))
            with store._connect() as conn:
                assert not conn.execute(
                    "SELECT 1 FROM history_occurrences WHERE alias='third'"
                ).fetchone()
            assert not UnifiedMemoryStore(palace).recall("streamed")["sources"]
        if result["state"] != "indexing" and result.get("yielded") != "source_counted":
            break
    assert result["state"] == "complete" and result["gaps"] == 0, result
    assert result["indexed_rows"] == 5
    expected = (
        "sharedneedle streamed ž😀\x00\r\n" + ("sample ž😀\x00\n" * 300000)
        if streamed
        else "sharedneedle large exact ž😀\x00\r\n" + ("sample ž😀\n" * 154000)
    )
    if streamed:
        assert {"hash_pending", "publication_pending"} <= pending_states
    job = _load_job(palace)
    store = MemoryStore(history_store_path(palace, job["store_id"]))
    digest = hashlib.sha256()
    characters = 0
    edge_chunks = {}
    with store._connect() as conn:
        row = conn.execute(
            "SELECT identity,text_hash,ids FROM history_occurrences WHERE alias='third'"
        ).fetchone()
        assert row["text_hash"] == hashlib.sha256(expected.encode()).hexdigest()
        identities = (
            [
                found[0]
                for found in conn.execute(
                    "SELECT c.id FROM history_occurrence_chunks m JOIN chunks c ON c.id=m.chunk_id WHERE m.identity=? ORDER BY c.start",
                    (row["identity"],),
                )
            ]
            if streamed
            else json.loads(row["ids"])
        )
        if streamed:
            assert row["ids"] == "[]"
            assert not conn.execute("SELECT 1 FROM history_staged_rows").fetchone()
            assert not conn.execute("SELECT 1 FROM history_staged_chunks").fetchone()
        assert len(identities) > 128
        for identity in identities:
            chunk = conn.execute(
                "SELECT text,start,end FROM chunks WHERE id=?", (identity,)
            ).fetchone()
            assert chunk["start"] == characters
            assert chunk["text"] == expected[chunk["start"] : chunk["end"]]
            digest.update(chunk["text"].encode())
            characters = chunk["end"]
            if identity in (identities[0], identities[-1]):
                edge_chunks[identity] = chunk["text"]
    assert characters == len(expected)
    assert digest.hexdigest() == hashlib.sha256(expected.encode()).hexdigest()
    unified = UnifiedMemoryStore(palace)
    for identity in (identities[0], identities[-1]):
        page = unified.page(
            identity, expected_hash=hashlib.sha256(edge_chunks[identity].encode()).hexdigest()
        )
        assert page["status"] == "ok", page
        assert page["text"] == edge_chunks[identity][:2048]
        metadata = unified.page(identity, field="metadata")
        assert metadata["status"] == "ok", metadata
        assert metadata["text"] == '{ "workspace": "/qualification", "revision": 3 }'
    assert runtime.run_history(palace, "index", {})["indexed_rows"] == 5


def test_source_row_count_uses_pinned_version_and_bounded_lance_open(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from cognitive_castle import memory_history

    calls = {}

    class Dataset:
        version = 7

        def count_rows(self):
            calls["count_rows"] = calls.get("count_rows", 0) + 1
            return 5

    dataset = Dataset()

    def open_dataset(path, **kwargs):
        calls["path"] = path
        calls["kwargs"] = kwargs
        return dataset

    monkeypatch.setitem(sys.modules, "lance", SimpleNamespace(dataset=open_dataset))
    count_source = getattr(memory_history, "_source_row_count", None)
    assert callable(count_source), "history adapter must expose independent count acquisition"
    result = count_source(tmp_path, 7)
    assert result == 5
    assert calls["path"] == str(tmp_path)
    assert calls["count_rows"] == 1
    assert calls["kwargs"] == {
        "version": 7,
        "metadata_cache_size_bytes": 4 * 1024**2,
        "index_cache_size_bytes": 1024**2,
        "read_params": {"cache_repetition_index": False, "validate_on_decode": True},
    }


@pytest.mark.parametrize("count", [True, -1, 1.5, "5", 2**63])
def test_source_row_count_rejects_invalid_native_count(monkeypatch, tmp_path, count):
    from types import SimpleNamespace

    from cognitive_castle import memory_history

    class Dataset:
        version = 7

        def count_rows(self):
            return count

    monkeypatch.setitem(
        sys.modules,
        "lance",
        SimpleNamespace(dataset=lambda *args, **kwargs: Dataset()),
    )
    count_source = getattr(memory_history, "_source_row_count", None)
    assert callable(count_source), "history adapter must expose independent count acquisition"
    with pytest.raises(memory_history._HistoryError):
        count_source(tmp_path, 7)


def test_native_projection_preserves_unicode_nul_windows_and_row_identity(tmp_path):
    from cognitive_castle import memory_runtime as runtime

    writer = Path(__file__).parent / "fixtures" / "history_native_fixture.py"
    admission = runtime._admission()
    try:
        result = runtime._supervise(
            {
                "source": str(tmp_path / "source.lance"),
                "large_text": True,
                "projection_proof": True,
            },
            admission,
            worker_command=[sys.executable, "-I", str(writer)],
            deadline=8,
            rss_limit=runtime.HISTORY_RSS,
            total_rss_limit=runtime.HISTORY_TOTAL_RSS,
        )
    finally:
        os.close(admission)
    assert result["status"] == "ok" and result["projection_exact"], result.get("detail", result)
