"""Fixture-only history tests: no native imports or real archive access."""

import hashlib
import importlib
import json
import os
from pathlib import Path
import sqlite3
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="private POSIX storage")


@pytest.fixture
def history(monkeypatch):
    module = importlib.import_module("cognitive_castle.memory_history")
    # Small, deterministic slices exercise actual copy/checkpoint code.
    monkeypatch.setattr(module, "COPY_SLICE_BYTES", 4)
    monkeypatch.setattr(module, "COPY_BLOCK_BYTES", 4)
    return module


@pytest.fixture
def archive(tmp_path):
    source = tmp_path / "drawers.lance"
    (source / "_versions").mkdir(parents=True)
    (source / "_versions" / "1.manifest").write_bytes(b"manifest")
    (source / "data").mkdir()
    (source / "data" / "rows.lance").write_bytes(b"original data bytes")
    return source


def prepared(history, palace, archive):
    for _ in range(100):
        result = history.history_operation(palace, "prepare", {"source": str(archive)})
        if result["state"] == "prepared":
            return result
        assert result["status"] == "ok", result
    pytest.fail("snapshot failed to make bounded progress")


def test_snapshot_is_private_pinned_and_resumable(history, tmp_path, archive):
    palace = tmp_path / "palace"
    palace.mkdir()
    result = history.history_operation(palace, "prepare", {"source": str(archive)})
    assert result["state"] == "copying"
    first = result["copied_bytes"]
    assert 0 < first <= 4
    result = prepared(history, palace, archive)
    assert result["version"] == 1
    job = history._load_job(palace)
    snapshot = Path(job["snapshot"])
    assert (snapshot / "data/rows.lance").read_bytes() == b"original data bytes"
    assert snapshot.stat().st_mode & 0o077 == 0
    assert (snapshot / "data/rows.lance").stat().st_mode & 0o222 == 0
    assert (
        os.stat(snapshot / "data/rows.lance").st_ino != os.stat(archive / "data/rows.lance").st_ino
    )
    (archive / "data/rows.lance").write_bytes(b"later history")
    assert (snapshot / "data/rows.lance").read_bytes() == b"original data bytes"
    status = history.history_operation(palace, "status", {})
    assert "original data bytes" not in json.dumps(status)


def test_source_change_mid_copy_is_visible_and_cannot_publish(history, tmp_path, archive):
    palace = tmp_path / "palace"
    palace.mkdir()
    history.history_operation(palace, "prepare", {"source": str(archive)})
    (archive / "data/rows.lance").write_bytes(b"changed")
    result = history.history_operation(palace, "prepare", {"source": str(archive)})
    assert result["status"] == "changed"
    assert result["state"] == "changed"


def test_symlink_source_is_rejected(history, tmp_path, archive):
    palace = tmp_path / "palace"
    palace.mkdir()
    (archive / "escape").symlink_to(tmp_path)
    result = history.history_operation(palace, "prepare", {"source": str(archive)})
    assert result["status"] == "unsafe_source"


def test_snapshot_admission_checks_total_and_free_headroom(history, tmp_path, archive, monkeypatch):
    palace = tmp_path / "palace"
    palace.mkdir()
    monkeypatch.setattr(history, "MAX_SNAPSHOT_BYTES", 2)
    assert (
        history.history_operation(palace, "prepare", {"source": str(archive)})["status"] == "quota"
    )
    monkeypatch.setattr(history, "MAX_SNAPSHOT_BYTES", 1024**3)
    monkeypatch.setattr(history, "_free_bytes", lambda path: 0)
    assert (
        history.history_operation(palace, "prepare", {"source": str(archive)})["status"] == "quota"
    )


class FixtureScanner:
    """Immutable native-adapter fixture; checkpoints are physical row addresses."""

    def __init__(self, rows):
        self.rows = rows
        self.starts = []

    def __call__(self, snapshot, version, cursor):
        self.starts.append(dict(cursor))
        for number, row in enumerate(self.rows):
            if number < cursor.get("offset", 0):
                continue
            yield {
                "fragment": 7,
                "row_address": (7 << 32) + number,
                "offset": number + 1,
                "values": row,
            }


def use_rows(history, monkeypatch, rows):
    scanner = FixtureScanner(rows)
    monkeypatch.setattr(history, "_scan_rows", scanner)
    return scanner


def db_rows(history, palace, result, sql):
    from cognitive_castle.unified_memory import history_store_path

    path = history_store_path(palace, result["store_id"]) / "memory.sqlite3"
    with sqlite3.connect(path) as conn:
        return conn.execute(sql).fetchall()


def test_duplicate_old_ids_equal_text_and_exact_metadata_survive(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    text = "  Žluťoučký\x00\n😀 "
    metadata = '{ "large": "' + "x" * 1200 + '", "wing": "People" }'
    use_rows(
        history,
        monkeypatch,
        [
            {"id": "old", "text": text, "metadata_json": metadata, "wing": "People"},
            {"id": "old", "text": text, "metadata_json": metadata, "wing": "People"},
        ],
    )
    result = history.history_operation(palace, "index", {})
    assert result["state"] == "complete"
    rows = db_rows(history, palace, result, "SELECT id,text,text_hash FROM chunks ORDER BY id")
    assert len(rows) == 2 and rows[0][0] != rows[1][0]
    assert all(row[1:] == (text, hashlib.sha256(text.encode()).hexdigest()) for row in rows)
    assert db_rows(history, palace, result, "SELECT metadata_json FROM history_occurrences") == [
        (metadata,),
        (metadata,),
    ]
    assert db_rows(history, palace, result, "SELECT alias FROM history_aliases") == [
        ("old",),
        ("old",),
    ]


def test_committed_row_retry_is_idempotent_after_checkpoint_interruption(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    scanner = use_rows(
        history, monkeypatch, [{"id": "old", "text": "exact", "metadata_json": "{}"}]
    )
    original = history._save_job
    fired = []

    def interrupted(palace, job):
        if job.get("indexed_rows") == 1 and not fired:
            fired.append(True)
            raise OSError("fixture interruption after row commit")
        original(palace, job)

    monkeypatch.setattr(history, "_save_job", interrupted)
    result = history.history_operation(palace, "index", {})
    assert result["status"] == "unavailable"
    monkeypatch.setattr(history, "_save_job", original)
    result = history.history_operation(palace, "index", {})
    assert result["state"] == "complete"
    assert len(db_rows(history, palace, result, "SELECT * FROM chunks")) == 1
    assert len(db_rows(history, palace, result, "SELECT * FROM history_occurrences")) == 1
    assert scanner.starts[-1]["offset"] == 1


def test_rejected_row_has_durable_gap_and_other_occurrences_progress(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    monkeypatch.setattr(history, "MAX_ROW_BYTES", 32)
    scanner = use_rows(
        history,
        monkeypatch,
        [
            {"id": "huge", "text": "x" * 33, "metadata_json": "{}"},
            {"id": "small", "text": "yes", "metadata_json": "{}"},
        ],
    )
    result = history.history_operation(palace, "index", {})
    assert result["state"] == "blocked" and result["gaps"] == 1 and result["indexed_rows"] == 1
    assert db_rows(history, palace, result, "SELECT reason FROM history_gaps") == [("row_size",)]
    assert history.history_operation(palace, "index", {})["gaps"] == 1
    assert scanner.starts[-1]["offset"] == 2


def test_snapshot_mutation_prevents_native_open(history, tmp_path, archive, monkeypatch):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    snapshot = Path(history._load_job(palace)["snapshot"])
    target = snapshot / "data/rows.lance"
    target.chmod(0o600)
    target.write_bytes(b"tampered")
    scanner = use_rows(history, monkeypatch, [])
    assert history.history_operation(palace, "index", {})["status"] == "changed"
    assert not scanner.starts


def test_streaming_adapter_passes_explicit_native_bounds(history, monkeypatch):
    import sys
    from types import SimpleNamespace

    calls = {}

    class Dataset:
        version = 1
        schema = SimpleNamespace(names=["id", "text", "metadata_json", "vector"])

        def get_fragments(self):
            return [SimpleNamespace(fragment_id=7)]

        def scanner(self, **kwargs):
            calls["scanner"] = kwargs
            return SimpleNamespace(to_batches=lambda: iter(()))

    def dataset(path, **kwargs):
        calls["dataset"] = kwargs
        return Dataset()

    monkeypatch.setitem(sys.modules, "lance", SimpleNamespace(dataset=dataset))
    assert (
        list(history._scan_rows(Path("/private/fixture"), 1, {"fragment": 7, "offset": 12})) == []
    )
    assert calls["dataset"]["version"] == 1
    assert calls["dataset"]["metadata_cache_size_bytes"] <= 4 * 1024**2
    assert calls["dataset"]["index_cache_size_bytes"] <= 1024**2
    assert calls["dataset"]["read_params"]["cache_repetition_index"] is False
    assert "vector" not in calls["scanner"]["columns"]
    assert calls["scanner"]["offset"] == 12
    assert 0 < calls["scanner"]["io_buffer_size"] <= 32 * 1024**2
    assert calls["scanner"]["batch_readahead"] == 0
    assert calls["scanner"]["fragment_readahead"] == 0


def test_quota_rolls_into_bounded_second_store_without_losing_occurrences(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    pin = prepared(history, palace, archive)
    use_rows(
        history,
        monkeypatch,
        [
            {"id": "one", "text": "first", "metadata_json": "{}"},
            {"id": "two", "text": "second", "metadata_json": "{}"},
        ],
    )
    commit = history._commit_row

    def limited(store, job, row, cursor):
        if store.directory.name == pin["store_id"] and row["offset"] == 2:
            raise history._Quota()
        return commit(store, job, row, cursor)

    monkeypatch.setattr(history, "_commit_row", limited)
    result = history.history_operation(palace, "index", {})
    assert result["state"] == "complete" and result["indexed_rows"] == 2
    job = history._load_job(palace)
    assert len(job["stores"]) == 2
    from cognitive_castle.unified_memory import UnifiedMemoryStore

    # Both shards are part of the ordinary query service, with the same exact IDs.
    recalled = UnifiedMemoryStore(palace).recall("first second", match="any")
    assert {hit["text"] for hit in recalled["sources"]} == {"first", "second"}


def test_transient_decode_death_has_one_durable_retry_then_visible_gap(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    job = history._load_job(palace)
    job["inflight"] = dict(job["cursor"])
    history._save_job(palace, job)
    scanner = use_rows(
        history, monkeypatch, [{"id": "one", "text": "recovered", "metadata_json": "{}"}]
    )
    assert history.history_operation(palace, "index", {})["state"] == "complete"
    assert scanner.starts[0]["offset"] == 0

    # A repeatedly killed immutable cursor is recorded once and never spun.
    job = history._load_job(palace)
    job["state"] = "indexing"
    job["inflight"] = dict(job["cursor"])
    job["retry_cursor"] = history._cursor_key(job["cursor"])
    job["retry_count"] = 1
    history._save_job(palace, job)
    result = history.history_operation(palace, "index", {})
    assert result["state"] == "blocked" and result["gaps"] == 1
    assert result["reason"] == "interrupted_native_decode"
    starts = len(scanner.starts)
    assert history.history_operation(palace, "index", {})["state"] == "blocked"
    assert len(scanner.starts) == starts


def test_copying_inventory_is_already_registered_as_pending(history, tmp_path, archive):
    palace = tmp_path / "palace"
    palace.mkdir()
    result = history.history_operation(palace, "prepare", {"source": str(archive)})
    catalog = json.loads((palace / ".memory-history/catalog.json").read_text())
    assert catalog["stores"][0]["store_id"] == result["store_id"]
    assert catalog["stores"][0]["state"] == "pending"
