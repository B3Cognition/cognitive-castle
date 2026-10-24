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
    monkeypatch.setattr(module, "_interactive_waiting", lambda: False)
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


def test_valid_row_atomically_commits_registry_hashes_chunks_and_receipt(history, tmp_path):
    from cognitive_castle.fast_memory import MemoryStore

    store = MemoryStore(tmp_path / "history-shard")
    job = {"archive_id": "a" * 64, "snapshot_id": "b" * 64, "version": 1}
    cursor = {"fragment": 0, "offset": 0}
    metadata = '{ "wing": "exact metadata" }'
    row = {
        "fragment": 7,
        "row_address": 7 << 32,
        "offset": 1,
        "values": {
            "id": "legacy",
            "text": "verbatim\n\x00Ž",
            "metadata_json": metadata,
        },
    }
    next_cursor, indexed, gaps = history._commit_row(store, job, row, cursor)
    assert next_cursor == {"fragment": 7, "row_address": 7 << 32, "offset": 1}
    assert (indexed, gaps) == (1, 0)
    with sqlite3.connect(store.db_path) as conn:
        assert conn.execute("SELECT text FROM chunks").fetchone()[0] == row["values"]["text"]
        saved = conn.execute(
            "SELECT metadata_json,metadata_hash,columns_json,columns_hash FROM history_occurrences"
        ).fetchone()
        assert saved[0] == metadata
        assert saved[1] == hashlib.sha256(metadata.encode()).hexdigest()
        assert saved[3] == hashlib.sha256(saved[2].encode()).hexdigest()
        assert conn.execute("SELECT count(*) FROM history_attempts").fetchone()[0] == 1


def test_changed_copy_can_pin_new_inventory_without_replacing_originals(history, tmp_path, archive):
    palace = tmp_path / "palace"
    palace.mkdir()
    old = history.history_operation(palace, "prepare", {"source": str(archive)})
    (archive / "data/rows.lance").write_bytes(b"new inventory")
    assert (
        history.history_operation(palace, "prepare", {"source": str(archive)})["state"] == "changed"
    )
    new = prepared(history, palace, archive)
    assert new["store_id"] != old["store_id"]
    assert (archive / "data/rows.lance").read_bytes() == b"new inventory"
    catalog = json.loads((palace / ".memory-history/catalog.json").read_text())
    assert [entry["store_id"] for entry in catalog["stores"]] == [new["store_id"]]
    assert (palace / ".memory-history/snapshots" / old["store_id"]).exists()


def test_completed_source_new_version_creates_new_pin_preserving_committed_store(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    use_rows(
        history, monkeypatch, [{"id": "old", "text": "previous version", "metadata_json": "{}"}]
    )
    old = history.history_operation(palace, "index", {})
    assert old["state"] == "complete"
    (archive / "_versions/2.manifest").write_bytes(b"second manifest")
    (archive / "data/rows.lance").write_bytes(b"revised rows")
    new = prepared(history, palace, archive)
    assert new["version"] == 2 and new["store_id"] != old["store_id"]
    assert db_rows(history, palace, old, "SELECT text FROM chunks") == [("previous version",)]
    catalog = json.loads((palace / ".memory-history/catalog.json").read_text())
    assert {entry["store_id"]: entry["state"] for entry in catalog["stores"]} == {
        old["store_id"]: "complete",
        new["store_id"]: "pending",
    }


@pytest.mark.parametrize("previous_complete", [False, True])
def test_prepare_recovers_empty_orphan_after_crash_before_job_save(
    history, tmp_path, archive, monkeypatch, previous_complete
):
    palace = tmp_path / "palace"
    palace.mkdir()
    if previous_complete:
        prepared(history, palace, archive)
        use_rows(history, monkeypatch, [{"id": "old", "text": "preserved", "metadata_json": "{}"}])
        old = history.history_operation(palace, "index", {})
        assert old["state"] == "complete"
        (archive / "_versions/2.manifest").write_bytes(b"new version")
    save = history._save_job

    def interrupted(palace, job):
        # The mkdir has happened, but no pending job/catalog publication exists.
        assert Path(job["snapshot"]).is_dir()
        raise OSError("fixture crash before durable job save")

    monkeypatch.setattr(history, "_save_job", interrupted)
    assert (
        history.history_operation(palace, "prepare", {"source": str(archive)})["status"]
        == "unavailable"
    )
    monkeypatch.setattr(history, "_save_job", save)
    resumed = history.history_operation(palace, "prepare", {"source": str(archive)})
    assert resumed["status"] == "ok", resumed
    result = prepared(history, palace, archive)
    assert result["state"] == "prepared"
    if previous_complete:
        assert result["version"] == 2
        assert db_rows(history, palace, old, "SELECT text FROM chunks") == [("preserved",)]


@pytest.mark.parametrize("forged", ["populated", "symlink", "permissions", "referenced"])
def test_prepare_rejects_unsafe_or_referenced_orphan(
    history, tmp_path, archive, monkeypatch, forged
):
    palace = tmp_path / "palace"
    palace.mkdir()
    save = history._save_job
    captured = {}

    def interrupted(palace, job):
        captured.update(job)
        raise OSError("fixture orphan")

    monkeypatch.setattr(history, "_save_job", interrupted)
    assert (
        history.history_operation(palace, "prepare", {"source": str(archive)})["status"]
        == "unavailable"
    )
    monkeypatch.setattr(history, "_save_job", save)
    orphan = Path(captured["snapshot"])
    if forged == "populated":
        (orphan / "unrecognized").write_bytes(b"keep me")
    elif forged == "symlink":
        orphan.rmdir()
        orphan.symlink_to(archive, target_is_directory=True)
    elif forged == "permissions":
        orphan.chmod(0o755)
    else:
        from cognitive_castle.unified_memory import register_history_store

        assert (
            register_history_store(
                palace, captured["store_id"], archive_id=captured["archive_id"], state="pending"
            )["status"]
            == "ok"
        )
    result = history.history_operation(palace, "prepare", {"source": str(archive)})
    assert result["status"] in {"conflict", "unsafe_source", "unavailable"}
    assert (archive / "data/rows.lance").read_bytes() == b"original data bytes"


def test_waiting_interactive_read_yields_after_durable_row_and_next_slice_resumes(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    scanner = use_rows(
        history,
        monkeypatch,
        [
            {"id": "one", "text": "first exact", "metadata_json": "{}"},
            {"id": "two", "text": "second exact", "metadata_json": "{}"},
        ],
    )

    def waiting():
        return history._load_job(palace).get("indexed_rows", 0) >= 1

    monkeypatch.setattr(history, "_interactive_waiting", waiting, raising=False)
    result = history.history_operation(palace, "index", {})
    assert result["state"] == "indexing" and result["indexed_rows"] == 1
    assert result["yielded"] == "interactive_waiting"
    job = history._load_job(palace)
    assert job["cursor"]["offset"] == 1 and "inflight" not in job
    assert db_rows(history, palace, result, "SELECT text FROM chunks") == [("first exact",)]
    monkeypatch.setattr(history, "_interactive_waiting", lambda: False)
    resumed = history.history_operation(palace, "index", {})
    assert resumed["state"] == "complete" and resumed["indexed_rows"] == 2
    assert scanner.starts[-1]["offset"] == 1
    assert len(db_rows(history, palace, resumed, "SELECT * FROM history_occurrences")) == 2


def test_waiting_interactive_read_preserves_prior_inflight_before_native_setup(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    job = history._load_job(palace)
    job["inflight"] = dict(job["cursor"])
    history._save_job(palace, job)
    scanner = use_rows(
        history, monkeypatch, [{"id": "one", "text": "pending", "metadata_json": "{}"}]
    )
    monkeypatch.setattr(history, "_interactive_waiting", lambda: True, raising=False)
    yielded = history.history_operation(palace, "index", {})
    assert yielded["yielded"] == "interactive_waiting"
    assert history._load_job(palace) == job
    assert not scanner.starts
    monkeypatch.setattr(history, "_interactive_waiting", lambda: False)
    assert history.history_operation(palace, "index", {})["state"] == "complete"


def test_waiting_interactive_read_yields_copy_at_durable_block(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()

    def waiting():
        job = history._load_job(palace)
        return bool(job and sum(item["copied"] for item in job["inventory"]) >= 4)

    monkeypatch.setattr(history, "_interactive_waiting", waiting, raising=False)
    result = history.history_operation(palace, "prepare", {"source": str(archive)})
    assert result["state"] == "copying" and result["copied_bytes"] == 4
    assert result["yielded"] == "interactive_waiting"
    monkeypatch.setattr(history, "_interactive_waiting", lambda: False)
    complete = prepared(history, palace, archive)
    assert complete["state"] == "prepared"
    assert (
        Path(history._load_job(palace)["snapshot"]) / "data/rows.lance"
    ).read_bytes() == b"original data bytes"


def test_exact_text_above_old_limit_uses_chunks_without_raising_native_batch_cap(history, tmp_path):
    from cognitive_castle.fast_memory import MemoryStore

    accepted = 2 * 1024**2 + 65536
    assert history.MAX_NATIVE_BATCH_BYTES == accepted
    store = MemoryStore(tmp_path / "large-row")
    text = "ž😀\x00\r\n" * 160000
    assert 1024**2 < len(text.encode()) < accepted
    job = {"archive_id": "a" * 64, "snapshot_id": "b" * 64, "version": 1}
    row = {
        "fragment": 7,
        "row_address": 7 << 32,
        "offset": 1,
        "values": {"id": "large", "text": text, "metadata_json": "{}"},
    }
    _, indexed, gaps = history._commit_row(store, job, row, {"fragment": 0, "offset": 0})
    assert (indexed, gaps) == (1, 0)
    with sqlite3.connect(store.db_path) as conn:
        chunks = conn.execute("SELECT text FROM chunks ORDER BY start").fetchall()
        assert "".join(chunk[0] for chunk in chunks) == text
        assert all(len(chunk[0].encode()) <= 8192 for chunk in chunks)
        assert (
            conn.execute("SELECT text_hash FROM history_occurrences").fetchone()[0]
            == hashlib.sha256(text.encode()).hexdigest()
        )
    outside = {
        **row,
        "row_address": (7 << 32) + 1,
        "offset": 2,
        "values": {"id": "outside", "text": "x" * (accepted + 1), "metadata_json": "{}"},
    }
    assert history._commit_row(
        store, job, outside, {"fragment": 7, "offset": 1, "row_address": 7 << 32}
    )[1:] == (1, 1)
    assert history.IO_BUFFER_BYTES == 32 * 1024**2
    assert history.MAX_METADATA_BYTES == 1024**2


def repair_fixture(history, tmp_path, archive, monkeypatch, *, older_shard=False):
    palace = tmp_path / "palace"
    palace.mkdir()
    pin = prepared(history, palace, archive)
    scanner = use_rows(
        history,
        monkeypatch,
        [
            {"id": "large", "text": "x" * 33, "metadata_json": "{}"},
            {"id": "later", "text": "preserve later text", "metadata_json": "{}"},
        ],
    )
    commit = history._commit_row

    def limited(store, job, row, cursor):
        if older_shard and store.directory.name == pin["store_id"] and row["offset"] == 2:
            raise history._Quota()
        return commit(store, job, row, cursor)

    with monkeypatch.context() as old_policy:
        old_policy.setattr(history, "MAX_ROW_BYTES", 32)
        old_policy.setattr(history, "_commit_row", limited)
        result = history.history_operation(palace, "index", {})
    assert result["gaps"] == 1 and result["indexed_rows"] == 1
    return palace, {"store_id": pin["store_id"], "cursor": {"fragment": 0, "offset": 0}}, scanner


@pytest.mark.parametrize("older_shard", [False, True])
def test_repair_resolves_one_known_gap_without_replaying_or_advancing_main_cursor(
    history, tmp_path, archive, monkeypatch, older_shard
):
    palace, arguments, scanner = repair_fixture(
        history, tmp_path, archive, monkeypatch, older_shard=older_shard
    )
    before = history._load_job(palace)
    result = history.history_operation(palace, "repair", arguments)
    assert result["status"] == "ok" and result["repair"]["status"] == "resolved"
    after = history._load_job(palace)
    assert after["cursor"] == before["cursor"]
    assert after["store_id"] == before["store_id"]
    assert after["indexed_rows"] == 2 and after["gaps"] == 0
    assert scanner.starts[-1] == arguments["cursor"]
    target = {"store_id": arguments["store_id"]}
    assert db_rows(history, palace, target, "SELECT count(*) FROM history_gaps") == [(0,)]
    assert db_rows(history, palace, target, "SELECT reason FROM history_gap_resolutions") == [
        ("row_size",)
    ]
    assert db_rows(
        history, palace, target, "SELECT outcome FROM history_attempts ORDER BY cursor_key"
    ).count(("indexed",)) == (1 if older_shard else 2)
    assert db_rows(
        history, palace, target, "SELECT count(*) FROM history_occurrences WHERE alias='large'"
    ) == [(1,)]
    starts = len(scanner.starts)
    duplicate = history.history_operation(palace, "repair", arguments)
    assert duplicate["repair"]["status"] == "already_resolved"
    assert len(scanner.starts) == starts
    assert history._load_job(palace)["cursor"] == before["cursor"]


@pytest.mark.parametrize("mismatch", ["store", "cursor", "reason", "occurrence", "next_cursor"])
def test_repair_refuses_unknown_or_changed_gap_receipts(
    history, tmp_path, archive, monkeypatch, mismatch
):
    palace, arguments, scanner = repair_fixture(history, tmp_path, archive, monkeypatch)
    before = history._load_job(palace)
    store = history._store(palace, before, arguments["store_id"])
    if mismatch == "store":
        arguments["store_id"] = "f" * 64
    elif mismatch == "cursor":
        arguments["cursor"] = {"fragment": 1, "offset": 0}
    elif mismatch == "reason":
        with store._connect(True) as conn:
            conn.execute("UPDATE history_gaps SET reason='metadata_size'")
    else:
        scan = history._scan_rows

        def changed(*args):
            row = next(iter(scan(*args)))
            if mismatch == "occurrence":
                row["row_address"] += 1
            else:
                row["offset"] += 1
            yield row

        monkeypatch.setattr(history, "_scan_rows", changed)
    result = history.history_operation(palace, "repair", arguments)
    assert result["status"] == "repair_refused"
    assert history._load_job(palace)["cursor"] == before["cursor"]
    with store._connect() as conn:
        assert conn.execute("SELECT count(*) FROM history_gaps").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM history_occurrences").fetchone()[0] == 1


def test_repair_rollback_preserves_gap_and_original_attempt(
    history, tmp_path, archive, monkeypatch
):
    palace, arguments, _ = repair_fixture(history, tmp_path, archive, monkeypatch)
    job = history._load_job(palace)
    store = history._store(palace, job, arguments["store_id"])
    with store._connect(True) as conn:
        history._schema(conn)
        conn.execute(
            "CREATE TRIGGER reject_resolution BEFORE INSERT ON history_gap_resolutions BEGIN SELECT RAISE(ABORT,'fixture transaction fault'); END"
        )
    result = history.history_operation(palace, "repair", arguments)
    assert result["status"] != "ok"
    with store._connect() as conn:
        assert conn.execute("SELECT count(*) FROM history_gaps").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM history_gap_resolutions").fetchone()[0] == 0
        assert (
            conn.execute("SELECT count(*) FROM history_occurrences WHERE alias='large'").fetchone()[
                0
            ]
            == 0
        )
        assert (
            conn.execute(
                "SELECT outcome FROM history_attempts WHERE cursor_key=?",
                (history._cursor_key(arguments["cursor"]),),
            ).fetchone()[0]
            == "gap"
        )
        assert conn.execute("SELECT count(*) FROM chunks").fetchone()[0] == 1
    assert history._load_job(palace)["cursor"] == job["cursor"]


def test_repair_retry_reconciles_counts_after_commit_before_job_save(
    history, tmp_path, archive, monkeypatch
):
    palace, arguments, scanner = repair_fixture(
        history, tmp_path, archive, monkeypatch, older_shard=True
    )
    before = history._load_job(palace)
    save = history._save_job

    def interrupted(*args):
        raise OSError("fixture crash after durable repair")

    monkeypatch.setattr(history, "_save_job", interrupted)
    assert history.history_operation(palace, "repair", arguments)["status"] == "unavailable"
    assert history._load_job(palace)["gaps"] == 1
    monkeypatch.setattr(history, "_save_job", save)
    starts = len(scanner.starts)
    retried = history.history_operation(palace, "repair", arguments)
    assert retried["repair"]["status"] == "already_resolved"
    assert len(scanner.starts) == starts
    after = history._load_job(palace)
    assert after["gaps"] == 0 and after["indexed_rows"] == 2
    assert after["cursor"] == before["cursor"]
    from cognitive_castle.unified_memory import UnifiedMemoryStore

    # The common reader never claims whole-memory completeness. Verify the
    # repaired declared shards were actually republished with reconciled counts.
    catalog = UnifiedMemoryStore(palace).status()["coverage_detail"]["stores"]
    published = [item for item in catalog if item["store_id"] != "live"]
    assert len(published) == 2
    assert all(item["state"] == "complete" and item["status"] == "ok" for item in published)
    assert sum(item["indexed_rows"] for item in published) == 2


def test_repair_quota_preserves_gap_without_rollover(history, tmp_path, archive, monkeypatch):
    palace, arguments, _ = repair_fixture(history, tmp_path, archive, monkeypatch)
    before = history._load_job(palace)
    monkeypatch.setattr(history, "_free_bytes", lambda path: 0)
    result = history.history_operation(palace, "repair", arguments)
    assert result["status"] == "quota"
    after = history._load_job(palace)
    assert after["stores"] == before["stores"] and after["cursor"] == before["cursor"]
    store = history._store(palace, after, arguments["store_id"])
    with store._connect() as conn:
        assert conn.execute("SELECT count(*) FROM history_gaps").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM history_gap_resolutions").fetchone()[0] == 0


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"store_id": "x", "cursor": {"fragment": 0, "offset": 0}},
        {"store_id": "a" * 64, "cursor": {"fragment": True, "offset": 0}},
        {"store_id": "a" * 64, "cursor": {"fragment": 0, "offset": 0, "command": "bad"}},
    ],
)
def test_repair_rejects_invalid_arguments_before_storage(history, tmp_path, arguments):
    with pytest.raises(ValueError):
        history.history_operation(tmp_path, "repair", arguments)
    assert not list(tmp_path.iterdir())
