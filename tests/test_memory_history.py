"""Fixture-only history tests: no native imports or real archive access."""

import hashlib
import importlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import weakref

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


def use_rows(history, monkeypatch, rows, *, palace=None):
    scanner = FixtureScanner(rows)
    monkeypatch.setattr(history, "_scan_rows", scanner)
    if palace is not None:
        job = history._load_job(palace)
        job["expected_rows"] = len(rows)
        history._save_job(palace, job)
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
        palace=palace,
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
        history, monkeypatch, [{"id": "old", "text": "exact", "metadata_json": "{}"}], palace=palace
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
        palace=palace,
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
    scanner = use_rows(history, monkeypatch, [], palace=palace)
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
        palace=palace,
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
        history,
        monkeypatch,
        [{"id": "one", "text": "recovered", "metadata_json": "{}"}],
        palace=palace,
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
        history,
        monkeypatch,
        [{"id": "old", "text": "previous version", "metadata_json": "{}"}],
        palace=palace,
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
        use_rows(
            history,
            monkeypatch,
            [{"id": "old", "text": "preserved", "metadata_json": "{}"}],
            palace=palace,
        )
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
        palace=palace,
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
        history,
        monkeypatch,
        [{"id": "one", "text": "pending", "metadata_json": "{}"}],
        palace=palace,
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
        palace=palace,
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


def test_repair_does_not_complete_when_independent_source_count_disagrees(
    history, tmp_path, archive, monkeypatch
):
    palace, arguments, _ = repair_fixture(history, tmp_path, archive, monkeypatch)
    job = history._load_job(palace)
    assert job["state"] == "blocked" and job["total_rows"] == 2
    job["expected_rows"] = 3
    history._save_job(palace, job)
    result = history.history_operation(palace, "repair", arguments)
    assert result["status"] == "ok"
    assert result["gaps"] == 0 and result["indexed_rows"] == 2
    assert result["state"] != "complete" and result["coverage_complete"] is False
    assert result["reason"] == "source_count_mismatch"


def test_rollover_reuses_best_fitting_prior_shard_at_eight_store_limit(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    job = history._load_job(palace)
    # Seed the durable catalog/job with eight real private shard directories.
    for index in range(1, history.MAX_HISTORY_STORES):
        store_id = history._hash(history._json([job["snapshot_id"], "shard", index]))
        job["stores"].append({"store_id": store_id, "indexed_rows": 0, "gaps": 0})
        history._save_job(palace, job)
        with history._store(palace, job, store_id)._connect(True) as conn:
            history._schema(conn)
    job["store_id"] = job["stores"][-1]["store_id"]
    job["inflight"] = dict(job["cursor"])
    history._save_job(palace, job)

    # Inject deterministic logical usage: shard 2 has the tightest fitting
    # residual, shard 1 has more room, and all other shards are full.
    cap = history.MAX_STORE_BYTES // 3
    usage = {item["store_id"]: cap for item in job["stores"]}
    usage[job["stores"][1]["store_id"]] = cap - 1900
    usage[job["stores"][2]["store_id"]] = cap - 1700
    monkeypatch.setattr(history, "_store_used", lambda store: usage[store.directory.name])
    reopened = history._rollover(palace, job, estimate=1000)
    assert reopened.directory.name == job["stores"][2]["store_id"]
    assert len(job["stores"]) == history.MAX_HISTORY_STORES
    assert job["store_id"] == job["stores"][2]["store_id"]
    assert "inflight" not in history._load_job(palace)

    # A new worker resumes the durable rejection set and cannot cycle back to
    # the shard whose physical commit failed.
    resumed = history._load_job(palace)
    next_store = history._rollover(palace, resumed, estimate=1000)
    assert next_store.directory.name == job["stores"][1]["store_id"]
    assert resumed["store_id"] == job["stores"][1]["store_id"]


def test_rollover_does_not_switch_a_shard_with_an_active_stage(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    job = history._load_job(palace)
    active = job["store_id"]
    # Existing staged work is owned by the active shard. Capacity selection
    # must not move it, even when an older shard would otherwise fit.
    with history._store(palace, job)._connect(True) as conn:
        history._schema(conn)
        conn.execute(
            "INSERT INTO history_staged_rows (cursor_key,identity,snapshot_id,source_cursor,next_cursor,metadata_json,columns_json,text_bytes,text_characters,next_character,chunk_start,carry,processed_bytes,state) VALUES ('k','i','s','{}','{}','{}','{}',1,1,0,0,'',0,'copying')"
        )
    monkeypatch.setattr(history, "_store_used", lambda store: 0)
    with pytest.raises(history._HistoryError):
        history._rollover(palace, job, estimate=1)
    assert job["store_id"] == active


def test_reused_target_receipt_recovers_after_job_checkpoint_crash(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    job = history._load_job(palace)
    original = job["store_id"]
    with history._store(palace, job, original)._connect(True) as conn:
        history._schema(conn)
    reused = history._hash(history._json([job["snapshot_id"], "shard", 1]))
    job["stores"].append({"store_id": reused, "indexed_rows": 0, "gaps": 0})
    job["store_id"] = reused
    history._save_job(palace, job)
    with history._store(palace, job)._connect(True) as conn:
        history._schema(conn)
    history._publish(palace, job)
    use_rows(
        history,
        monkeypatch,
        [{"id": "row", "text": "decoded row", "metadata_json": "{}"}],
        palace=palace,
    )
    cap = history.MAX_STORE_BYTES // 3
    usage = {original: cap - 100_000, reused: cap}
    monkeypatch.setattr(history, "_store_used", lambda store: usage[store.directory.name])
    commit = history._commit_row
    calls = 0

    def fail_first_commit(*args, **kwargs):
        nonlocal calls
        if calls == 0:
            calls += 1
            raise history._Quota()
        return commit(*args, **kwargs)

    monkeypatch.setattr(history, "_commit_row", fail_first_commit)
    save = history._save_job

    def crash_after_receipt(path, current):
        if current["cursor"].get("offset") == 1:
            raise OSError("fixture crash after row receipt")
        return save(path, current)

    monkeypatch.setattr(history, "_save_job", crash_after_receipt)
    assert history.history_operation(palace, "index", {})["status"] == "unavailable"
    durable = history._load_job(palace)
    assert durable["store_id"] == original
    assert durable["cursor"] == {"fragment": 0, "offset": 0}
    assert "inflight" not in durable

    monkeypatch.setattr(history, "_save_job", save)
    recovered = history.history_operation(palace, "index", {})
    assert recovered["indexed_rows"] == 1
    assert history._load_job(palace)["cursor"]["offset"] == 1
    assert db_rows(history, palace, recovered, "SELECT count(*) FROM history_occurrences") == [(1,)]


def test_output_capacity_job_resumes_when_an_existing_shard_fits(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    job = history._load_job(palace)
    for index in range(1, history.MAX_HISTORY_STORES):
        store_id = history._hash(history._json([job["snapshot_id"], "shard", index]))
        job["stores"].append({"store_id": store_id, "indexed_rows": 0, "gaps": 0})
        history._save_job(palace, job)
        with history._store(palace, job, store_id)._connect(True) as conn:
            history._schema(conn)
    job["store_id"] = job["stores"][-1]["store_id"]
    history._save_job(palace, job)
    history._publish(palace, job)
    cap = history.MAX_STORE_BYTES // 3
    usage = {item["store_id"]: cap for item in job["stores"]}
    monkeypatch.setattr(history, "_store_used", lambda store: usage[store.directory.name])
    with pytest.raises(history._HistoryError, match="quota"):
        history._rollover(palace, job, estimate=1000)
    assert job["reason"] == "output_capacity"
    use_rows(
        history,
        monkeypatch,
        [{"id": "row", "text": "resume", "metadata_json": "{}"}],
        palace=palace,
    )
    usage[job["stores"][1]["store_id"]] = cap - 100_000
    commit = history._commit_row
    calls = 0

    def fail_first_commit(*args, **kwargs):
        nonlocal calls
        if calls == 0:
            calls += 1
            raise history._Quota()
        return commit(*args, **kwargs)

    monkeypatch.setattr(history, "_commit_row", fail_first_commit)
    result = history.history_operation(palace, "index", {})
    assert result["status"] == "ok"
    assert result["indexed_rows"] == 1
    assert "reason" not in result
    assert history._load_job(palace)["store_id"] == job["stores"][1]["store_id"]


def test_capacity_retry_metadata_must_match_registered_current_cursor(history, tmp_path, archive):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    job = history._load_job(palace)
    job["capacity_cursor_key"] = history._cursor_key(job["cursor"])
    job["capacity_rejected"] = ["not-a-registered-store"]
    history._save_job(palace, job)
    with pytest.raises(history._HistoryError, match="corrupt"):
        history._load_job(palace)


@pytest.mark.parametrize("bad_value", [object(), "\ud800"])
def test_capacity_retry_records_invalid_hoisted_value_as_gap(
    history, tmp_path, archive, monkeypatch, bad_value
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    job = history._load_job(palace)
    original = job["store_id"]
    with history._store(palace, job, original)._connect(True) as conn:
        history._schema(conn)
    reused = history._hash(history._json([job["snapshot_id"], "shard", 1]))
    job["stores"].append({"store_id": reused, "indexed_rows": 0, "gaps": 0})
    job["store_id"] = reused
    history._save_job(palace, job)
    with history._store(palace, job)._connect(True) as conn:
        history._schema(conn)
    history._publish(palace, job)
    use_rows(
        history,
        monkeypatch,
        [{"id": "bad", "text": "bad metadata", "metadata_json": "{}", "odd": bad_value}],
        palace=palace,
    )
    cap = history.MAX_STORE_BYTES // 3
    usage = {original: cap - 100_000, reused: cap}
    monkeypatch.setattr(history, "_store_used", lambda store: usage[store.directory.name])
    commit = history._commit_row
    calls = 0

    def fail_first_commit(*args, **kwargs):
        nonlocal calls
        if calls == 0:
            calls += 1
            raise history._Quota()
        return commit(*args, **kwargs)

    monkeypatch.setattr(history, "_commit_row", fail_first_commit)
    result = history.history_operation(palace, "index", {})
    assert result["status"] == "ok"
    assert result["indexed_rows"] == 0 and result["gaps"] == 1
    assert history._load_job(palace)["store_id"] == original
    assert db_rows(history, palace, result, "SELECT reason FROM history_gaps") == [
        ("invalid_metadata",)
    ]


@pytest.mark.parametrize("expected_rows", [True, -1, 1.5, "2", 2**63])
def test_job_rejects_invalid_independent_source_count(history, tmp_path, archive, expected_rows):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    job = history._load_job(palace)
    job["expected_rows"] = expected_rows
    history._save_job(palace, job)
    with pytest.raises(history._HistoryError, match="corrupt"):
        history._load_job(palace)


def test_legacy_complete_checkpoint_is_not_complete_without_independent_count(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    job = history._load_job(palace)
    job.pop("expected_rows", None)
    job["state"] = "complete"
    job["indexed_rows"] = 1
    job["total_rows"] = 1
    history._save_job(palace, job)
    calls = []

    def count_must_not_run(*args):
        calls.append(args)
        raise AssertionError("status must not open the pinned source")

    monkeypatch.setattr(history, "_source_row_count", count_must_not_run, raising=False)
    result = history.history_operation(palace, "status", {})
    assert result["status"] == "ok"
    assert result["coverage_complete"] is False
    assert calls == []


def test_legacy_job_persists_source_count_before_scanning(history, tmp_path, archive, monkeypatch):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    rows = [{"id": "one", "text": "exact", "metadata_json": "{}"}]
    scanner = FixtureScanner(rows)
    monkeypatch.setattr(history, "_scan_rows", scanner)
    calls = []

    def count_snapshot(snapshot, version):
        calls.append((snapshot, version))
        return 1

    monkeypatch.setattr(history, "_source_row_count", count_snapshot, raising=False)
    result = history.history_operation(palace, "index", {})
    assert result["status"] == "ok"
    assert result.get("yielded") == "source_counted"
    assert scanner.starts == []
    assert calls == [(Path(history._load_job(palace)["snapshot"]), 1)]
    assert history._load_job(palace)["expected_rows"] == 1


def test_legacy_complete_count_slice_downgrades_before_hidden_stage_reconciliation(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    job = history._load_job(palace)
    job["state"] = "complete"
    job["indexed_rows"] = 0
    job["total_rows"] = 0
    history._save_job(palace, job)
    store = history._store(palace, job)
    with store._connect(True) as conn:
        history._schema(conn)
        conn.execute(
            "INSERT INTO history_staged_rows (cursor_key,identity,snapshot_id,source_cursor,next_cursor,metadata_json,columns_json,text_bytes,text_characters,next_character,chunk_start,carry,processed_bytes,state) VALUES ('pending-stage','staged','snapshot','{}','{}','{}','{}',1,1,0,0,'',0,'copying')"
        )
    monkeypatch.setattr(history, "_source_row_count", lambda snapshot, version: 0)

    result = history.history_operation(palace, "index", {})

    assert result["yielded"] == "source_counted"
    assert result["state"] == "indexing"
    assert result["coverage_complete"] is False
    assert result["expected_rows"] == 0
    assert history._load_job(palace)["state"] == "indexing"


def test_premature_eof_does_not_claim_independent_source_coverage(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    use_rows(
        history,
        monkeypatch,
        [{"id": "present", "text": "preserved", "metadata_json": "{}"}],
        palace=palace,
    )
    job = history._load_job(palace)
    job["expected_rows"] = 2
    history._save_job(palace, job)
    result = history.history_operation(palace, "index", {})
    assert result["state"] != "complete"
    assert result["coverage_complete"] is False
    assert result["reason"] == "source_count_mismatch"
    assert result["expected_rows"] == 2
    assert result["indexed_rows"] == 1 and result["gaps"] == 0
    assert history._load_job(palace)["cursor"]["offset"] == 1


def test_completion_rejects_stored_shard_counter_that_disagrees_with_sqlite(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    job = history._load_job(palace)
    original = job["store_id"]
    old_store = history._store(palace, job)
    with old_store._connect(True) as conn:
        history._schema(conn)
    row = {
        "fragment": 7,
        "row_address": 7 << 32,
        "offset": 1,
        "values": {"id": "one", "text": "exact", "metadata_json": "{}"},
    }
    following, actual_rows, actual_gaps = history._commit_row(old_store, job, row, job["cursor"])
    history._update_counts(job, actual_rows, actual_gaps)
    job["cursor"] = following
    job["stores"][0]["indexed_rows"] = 0
    job["indexed_rows"] = 1
    job["expected_rows"] = 1
    second = history._hash(history._json([job["snapshot_id"], "shard", 1]))
    job["stores"].append({"store_id": second, "indexed_rows": 0, "gaps": 0})
    job["store_id"] = second
    history._save_job(palace, job)
    with history._store(palace, job)._connect(True) as conn:
        history._schema(conn)
    history._publish(palace, job)
    scanner = use_rows(history, monkeypatch, [], palace=palace)
    job = history._load_job(palace)
    job["expected_rows"] = 1
    history._save_job(palace, job)
    result = history.history_operation(palace, "index", {})
    assert result["state"] != "complete" and result["coverage_complete"] is False
    assert result["reason"] == "source_count_mismatch"
    assert result["indexed_rows"] == 0 and result["gaps"] == 0
    assert scanner.starts[-1]["offset"] == 1
    assert db_rows(
        history, palace, {"store_id": original}, "SELECT count(*) FROM history_occurrences"
    ) == [(1,)]


def test_completion_rejects_occurrence_without_attempt_receipt(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    job = history._load_job(palace)
    store = history._store(palace, job)
    with store._connect(True) as conn:
        history._schema(conn)
    row = {
        "fragment": 7,
        "row_address": 7 << 32,
        "offset": 1,
        "values": {"id": "one", "text": "exact", "metadata_json": "{}"},
    }
    following, indexed, gaps = history._commit_row(store, job, row, job["cursor"])
    with store._connect(True) as conn:
        conn.execute("DELETE FROM history_attempts")
    job["cursor"] = following
    job["expected_rows"] = 1
    job["stores"][0]["indexed_rows"] = indexed
    job["stores"][0]["gaps"] = gaps
    job["indexed_rows"], job["gaps"] = indexed, gaps
    history._save_job(palace, job)
    scanner = use_rows(history, monkeypatch, [], palace=palace)
    result = history.history_operation(palace, "index", {})
    assert result["state"] != "complete" and result["coverage_complete"] is False
    assert result["reason"] == "source_receipt_mismatch"
    assert scanner.starts[-1]["offset"] == 1


def test_completion_rejects_occurrence_when_attempt_table_is_missing(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    job = history._load_job(palace)
    store = history._store(palace, job)
    with store._connect(True) as conn:
        history._schema(conn)
    row = {
        "fragment": 7,
        "row_address": 7 << 32,
        "offset": 1,
        "values": {"id": "one", "text": "exact", "metadata_json": "{}"},
    }
    _, indexed, gaps = history._commit_row(store, job, row, job["cursor"])
    with store._connect(True) as conn:
        conn.execute("DROP TABLE history_attempts")
    job["expected_rows"] = 1
    job["total_rows"] = 1
    job["stores"][0]["indexed_rows"] = indexed
    job["stores"][0]["gaps"] = gaps

    with pytest.raises(history._HistoryError, match="source_receipt_mismatch"):
        history._reconcile_inventory(palace, job, float("inf"))


def test_completion_rejects_orphan_staged_chunks(history, tmp_path, archive, monkeypatch):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    job = history._load_job(palace)
    store = history._store(palace, job)
    with store._connect(True) as conn:
        history._schema(conn)
        conn.execute(
            "INSERT INTO history_staged_chunks VALUES ('orphan-stage',0,1,'orphan-id','x','hash')"
        )
    job["expected_rows"] = 0
    job["total_rows"] = 0

    with pytest.raises(history._HistoryError, match="source_stage_pending"):
        history._reconcile_inventory(palace, job, float("inf"))


def test_completion_rejects_pending_stage_in_any_shard(history, tmp_path, archive, monkeypatch):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    store = history._store(palace, history._load_job(palace))
    with store._connect(True) as conn:
        history._schema(conn)
        conn.execute(
            "INSERT INTO history_staged_rows (cursor_key,identity,snapshot_id,source_cursor,next_cursor,metadata_json,columns_json,text_bytes,text_characters,next_character,chunk_start,carry,processed_bytes,state) VALUES ('pending-stage','staged','snapshot','{}','{}','{}','{}',1,1,0,0,'',0,'copying')"
        )
    scanner = use_rows(history, monkeypatch, [], palace=palace)
    result = history.history_operation(palace, "index", {})
    assert result["state"] != "complete" and result["coverage_complete"] is False
    assert result["reason"] == "source_stage_pending"
    assert scanner.starts[-1]["offset"] == 0


def test_sqlite_busy_retries_do_not_turn_decoded_row_into_native_gap(
    history, tmp_path, archive, monkeypatch
):
    palace = tmp_path / "palace"
    palace.mkdir()
    prepared(history, palace, archive)
    scanner = use_rows(
        history,
        monkeypatch,
        [{"id": "row", "text": "retry me", "metadata_json": "{}"}],
        palace=palace,
    )
    commit = history._commit_row
    attempts = 0

    def busy_twice(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            raise sqlite3.OperationalError("database is locked")
        return commit(*args, **kwargs)

    monkeypatch.setattr(history, "_commit_row", busy_twice)
    first = history.history_operation(palace, "index", {})
    second = history.history_operation(palace, "index", {})
    assert first["status"] == second["status"] == "busy"
    job = history._load_job(palace)
    assert job["cursor"] == {"fragment": 0, "offset": 0}
    assert "inflight" not in job
    assert job.get("gaps", 0) == 0
    finished = history.history_operation(palace, "index", {})
    assert finished["state"] == "complete" and finished["indexed_rows"] == 1
    assert len(scanner.starts) == 3
    assert db_rows(history, palace, finished, "SELECT count(*) FROM history_gaps") == [(0,)]


def test_projected_header_sql_busy_does_not_become_interrupted_decode_gap(
    history, tmp_path, archive, monkeypatch
):
    palace, pin, _ = projected_fixture(history, tmp_path, archive, monkeypatch)
    stage_begin = history._stage_begin
    attempts = 0

    def busy_stage_begin(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(history, "_stage_begin", busy_stage_begin)
    first = history.history_operation(palace, "index", {})
    second = history.history_operation(palace, "index", {})
    assert first["status"] == second["status"] == "busy"
    job = history._load_job(palace)
    assert job["cursor"] == {"fragment": 0, "offset": 0}
    assert "inflight" not in job
    assert db_rows(history, palace, pin, "SELECT count(*) FROM history_gaps") == [(0,)]

    monkeypatch.setattr(history, "_stage_begin", stage_begin)
    result = finish_projected(history, palace)
    assert result["state"] == "complete" and result["indexed_rows"] == 1
    assert attempts == 2

    job["capacity_rejected"] = [job["store_id"]]
    job["capacity_cursor_key"] = "0" * 64
    history._save_job(palace, job)
    with pytest.raises(history._HistoryError, match="corrupt"):
        history._load_job(palace)


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


class ProjectedFixture:
    def __init__(self, text, values):
        self.text = text
        self.values = values
        self.starts = []
        self.pages = []
        self.closed = 0
        self.headers = 0
        self.binds = 0

    def __call__(self, snapshot, version, cursor):
        self.starts.append(dict(cursor))
        owner = self

        class Reader:
            def header(self):
                owner.headers += 1
                return {
                    "fragment": 7,
                    "offset": 1,
                    "row_address": 7 << 32,
                    "values": owner.values,
                    "text_bytes": len(owner.text.encode()),
                    "text_characters": len(owner.text),
                    "text_hash": hashlib.sha256(owner.text.encode()).hexdigest(),
                }

            def bind_header(self, header):
                owner.binds += 1
                assert header["text_hash"] == hashlib.sha256(owner.text.encode()).hexdigest()

            def page(self, start, limit=131072):
                owner.pages.append(start)
                return owner.text[start : start + limit]

            def close(self):
                owner.closed += 1

        return Reader()


def projected_fixture(history, tmp_path, archive, monkeypatch, text=None):
    palace = tmp_path / "palace"
    palace.mkdir()
    pin = prepared(history, palace, archive)
    job = history._load_job(palace)
    job["expected_rows"] = 1
    history._save_job(palace, job)
    value = text if text is not None else "ž😀\x00\r\n" * 1600 + " needle tail "
    values = {"id": "projected", "metadata_json": '{ "wing": "exact" }', "workspace": "/projected"}
    reader = ProjectedFixture(value, values)

    def oversized(*args):
        if args[2]["offset"] == 0:
            raise history._HistoryError("native_batch_size")
        return
        yield

    monkeypatch.setattr(history, "_scan_rows", oversized)
    monkeypatch.setattr(history, "_projected_row", reader, raising=False)
    monkeypatch.setattr(history, "PROJECTED_PAGE_CHARACTERS", 1025, raising=False)
    return palace, pin, reader


def staged_progress(history, palace):
    job = history._load_job(palace)
    store = history._store(palace, job)
    try:
        with store._connect() as conn:
            return conn.execute("SELECT next_character FROM history_staged_rows").fetchone()
    except (sqlite3.OperationalError, history._Unavailable):
        return None


def finish_projected(history, palace):
    for _ in range(8):
        result = history.history_operation(palace, "index", {})
        if result["status"] != "ok" or result["state"] in ("complete", "blocked"):
            return result
    pytest.fail("fixture did not finish in bounded page/hash/publication slices")


def prepare_projected_phase(history, palace, phase):
    """Reach a durable phase without assuming how many pages a worker admits."""
    expected = "hash_pending" if phase == "hash" else "publication_pending"
    for _ in range(12):
        store = history._store(palace, history._load_job(palace))
        try:
            with store._connect() as conn:
                staged = conn.execute("SELECT state FROM history_staged_rows").fetchone()
        except (sqlite3.OperationalError, history._Unavailable):
            staged = None
        if staged is not None and staged[0] == expected:
            return
        result = history.history_operation(palace, "index", {})
        assert result["status"] == "ok" and result["state"] == "indexing", result
    pytest.fail("fixture did not reach its requested durable final phase")


def test_projected_slice_caps_pages_and_resumes_from_exact_committed_position(
    history, tmp_path, archive, monkeypatch
):
    text = "x" * (1025 * 10 + 17)
    palace, pin, reader = projected_fixture(history, tmp_path, archive, monkeypatch, text)
    first = history.history_operation(palace, "index", {})
    assert reader.pages == [0, 1025, 2050, 3075]
    assert first["yielded"] == "projected_page_limit"
    assert first["partial_row"]["processed_characters"] == 4100
    assert reader.headers == 1 and reader.closed == 1
    assert history._load_job(palace)["cursor"] == {"fragment": 0, "offset": 0}
    assert db_rows(
        history,
        palace,
        pin,
        "SELECT inflight_character,retry_count,hash_failures,publication_failures FROM history_staged_rows",
    ) == [(None, 0, 0, 0)]
    assert db_rows(history, palace, pin, "SELECT count(*) FROM chunks") == [(0,)]
    second = history.history_operation(palace, "index", {})
    assert reader.pages[4:] == [4100, 5125, 6150, 7175]
    assert second["yielded"] == "projected_page_limit"
    assert reader.headers == 1 and reader.binds == 1 and reader.closed == 2
    assert finish_projected(history, palace)["state"] == "complete"
    assert reader.pages == list(range(0, len(text), 1025))
    assert (
        "".join(
            row[0]
            for row in db_rows(history, palace, pin, "SELECT text FROM chunks ORDER BY start")
        )
        == text
    )


def test_projected_row_windows_preserve_greedy_chunks_unicode_nul_and_canonical_ids(
    history, tmp_path, archive, monkeypatch
):
    palace, pin, reader = projected_fixture(history, tmp_path, archive, monkeypatch)
    result = finish_projected(history, palace)
    assert result["status"] == "ok" and result["state"] == "complete"
    job = history._load_job(palace)
    occurrence = history._hash(
        history._json([job["archive_id"], job["snapshot_id"], job["version"], 7, 7 << 32])
    )
    expected = list(history._chunks(reader.text))
    rows = db_rows(
        history, palace, pin, "SELECT id,text,start,end,text_hash FROM chunks ORDER BY start"
    )
    assert [(row[2], row[1]) for row in rows] == expected
    assert "".join(row[1] for row in rows) == reader.text
    for identity, text, start, end, digest in rows:
        assert identity == "memory:" + history._hash(history._json([occurrence, start]))
        assert end == start + len(text) and digest == hashlib.sha256(text.encode()).hexdigest()
        assert len(text.encode()) <= 8192
    registered = db_rows(history, palace, pin, "SELECT text_hash,ids FROM history_occurrences")
    assert registered == [(hashlib.sha256(reader.text.encode()).hexdigest(), "[]")]
    assert len(db_rows(history, palace, pin, "SELECT * FROM history_occurrence_chunks")) == len(
        rows
    )
    assert db_rows(history, palace, pin, "SELECT count(*) FROM history_staged_rows") == [(0,)]
    assert reader.closed >= 1


def test_large_projected_source_separates_header_and_limits_repeated_native_work(
    history, tmp_path, archive, monkeypatch
):
    text = "ž😀" * 1200 + " final exact tail "
    palace, pin, reader = projected_fixture(history, tmp_path, archive, monkeypatch, text)
    monkeypatch.setattr(history, "PROJECTED_SOURCE_BYTES_PER_SLICE", 4096, raising=False)
    first = history.history_operation(palace, "index", {})
    assert reader.pages == []
    assert first["partial_row"]["processed_characters"] == 0
    assert first["yielded"] == "projected_header_limit"
    assert reader.headers == reader.closed == 1
    second = history.history_operation(palace, "index", {})
    assert reader.pages == [0]
    assert second["partial_row"]["processed_characters"] == 1025
    assert second["yielded"] == "projected_page_limit"
    third = history.history_operation(palace, "index", {})
    assert reader.pages == [0, 1025]
    assert third["partial_row"]["processed_characters"] == 2050
    assert reader.headers == 1 and reader.binds == 2
    assert finish_projected(history, palace)["state"] == "complete"
    assert (
        "".join(
            row[0]
            for row in db_rows(history, palace, pin, "SELECT text FROM chunks ORDER BY start")
        )
        == text
    )


def test_staged_pages_are_private_and_resume_without_repeating_committed_windows(
    history, tmp_path, archive, monkeypatch
):
    from cognitive_castle.unified_memory import UnifiedMemoryStore

    palace, pin, reader = projected_fixture(history, tmp_path, archive, monkeypatch)

    def waiting():
        row = staged_progress(history, palace)
        return row is not None and row[0] >= 1025

    monkeypatch.setattr(history, "_interactive_waiting", waiting)
    first = history.history_operation(palace, "index", {})
    assert first["yielded"] == "interactive_waiting"
    assert first["partial_row"]["processed_characters"] == 1025
    assert history._load_job(palace)["cursor"] == {"fragment": 0, "offset": 0}
    for table in ("chunks", "lexical", "history_occurrences"):
        assert db_rows(history, palace, pin, "SELECT count(*) FROM " + table) == [(0,)]
    assert UnifiedMemoryStore(palace).recall("needle")["sources"] == []
    monkeypatch.setattr(history, "_interactive_waiting", lambda: False)
    resumed = finish_projected(history, palace)
    assert resumed["status"] == "ok" and resumed["gaps"] == 0
    assert reader.pages.count(0) == 1 and 1025 in reader.pages
    assert db_rows(history, palace, pin, "SELECT count(*) FROM history_occurrences") == [(1,)]
    assert history._load_job(palace)["cursor"]["offset"] == 1
    complete = UnifiedMemoryStore(palace).recall("needle")
    assert complete["status"] == "ok" and complete["sources"]


def test_projected_header_checkpoint_can_resume_pages_without_another_native_header(
    history, tmp_path, archive, monkeypatch
):
    palace, _, reader = projected_fixture(history, tmp_path, archive, monkeypatch)
    monkeypatch.setattr(history, "_interactive_waiting", lambda: reader.headers > 0)
    first = history.history_operation(palace, "index", {})
    assert first["yielded"] == "interactive_waiting"
    assert first["partial_row"]["processed_characters"] == 0
    assert reader.pages == []
    monkeypatch.setattr(history, "_interactive_waiting", lambda: False)
    assert finish_projected(history, palace)["state"] == "complete"
    assert reader.headers == 1
    # Every resumed reader binds the durable header instead of repeating the
    # native header query, including resumes required by the per-slice page cap.
    assert reader.binds == reader.closed - 1 and reader.binds >= 1


def test_projected_source_hash_mismatch_never_publishes_staged_text(
    history, tmp_path, archive, monkeypatch
):
    palace, pin, reader = projected_fixture(history, tmp_path, archive, monkeypatch)
    factory = history._projected_row

    def changed(*args):
        instance = factory(*args)
        page = instance.page

        def wrong(start, limit=131072):
            value = page(start, limit)
            return value.replace("needle", "xxxxxx")

        instance.page = wrong
        return instance

    monkeypatch.setattr(history, "_projected_row", changed)
    result = finish_projected(history, palace)
    assert result["status"] == "corrupt"
    assert history._load_job(palace)["cursor"] == {"fragment": 0, "offset": 0}
    for table in ("chunks", "lexical", "history_occurrences"):
        assert db_rows(history, palace, pin, "SELECT count(*) FROM " + table) == [(0,)]
    assert db_rows(history, palace, pin, "SELECT count(*) FROM history_staged_rows") == [(1,)]


def test_projected_publication_rolls_back_all_public_tables_and_keeps_stage(
    history, tmp_path, archive, monkeypatch
):
    palace, pin, reader = projected_fixture(history, tmp_path, archive, monkeypatch)
    monkeypatch.setattr(history, "_interactive_waiting", lambda: reader.headers > 0)
    assert history.history_operation(palace, "index", {})["yielded"] == "interactive_waiting"
    store = history._store(palace, history._load_job(palace))
    with store._connect(True) as conn:
        conn.execute(
            "CREATE TRIGGER reject_staged_publication BEFORE INSERT ON history_occurrences BEGIN SELECT RAISE(ABORT,'fixture publication fault'); END"
        )
    monkeypatch.setattr(history, "_interactive_waiting", lambda: False)
    assert finish_projected(history, palace)["status"] != "ok"
    for table in (
        "chunks",
        "lexical",
        "history_occurrences",
        "history_occurrence_chunks",
        "history_attempts",
    ):
        assert db_rows(history, palace, pin, "SELECT count(*) FROM " + table) == [(0,)]
    assert db_rows(history, palace, pin, "SELECT count(*) FROM history_staged_rows") == [(1,)]
    with store._connect(True) as conn:
        conn.execute("DROP TRIGGER reject_staged_publication")
    pages = list(reader.pages)
    assert finish_projected(history, palace)["state"] == "complete"
    assert reader.pages == pages
    assert db_rows(history, palace, pin, "SELECT count(*) FROM history_occurrences") == [(1,)]


@pytest.mark.parametrize("boundary", ["page", "publication"])
def test_projected_row_restarts_after_data_commit_before_job_checkpoint(
    history, tmp_path, archive, monkeypatch, boundary
):
    palace, pin, reader = projected_fixture(history, tmp_path, archive, monkeypatch)
    save = history._save_job
    fired = []

    def interrupted(palace, job):
        row = staged_progress(history, palace)
        public = (
            db_rows(history, palace, pin, "SELECT count(*) FROM history_occurrences")[0][0]
            if history._store(palace, job).db_path.exists()
            else 0
        )
        if not fired and (
            (boundary == "page" and row is not None and row[0] >= 1025)
            or (boundary == "publication" and public == 1)
        ):
            fired.append(True)
            raise OSError("fixture crash after durable staged data")
        return save(palace, job)

    monkeypatch.setattr(history, "_save_job", interrupted)
    assert finish_projected(history, palace)["status"] == "unavailable"
    assert fired
    monkeypatch.setattr(history, "_save_job", save)
    result = finish_projected(history, palace)
    assert result["state"] == "complete" and result["gaps"] == 0
    assert reader.pages.count(0) == 1
    assert db_rows(history, palace, pin, "SELECT count(*) FROM history_occurrences") == [(1,)]
    assert db_rows(history, palace, pin, "SELECT count(*) FROM history_attempts") == [(1,)]


def test_reused_stage_target_recovers_publication_receipt_after_crash(
    history, tmp_path, archive, monkeypatch
):
    palace, pin, reader = projected_fixture(history, tmp_path, archive, monkeypatch)
    job = history._load_job(palace)
    original = pin["store_id"]
    with history._store(palace, job, original)._connect(True) as conn:
        history._schema(conn)
    active = history._hash(history._json([job["snapshot_id"], "shard", 1]))
    job["stores"].append({"store_id": active, "indexed_rows": 0, "gaps": 0})
    job["store_id"] = active
    history._save_job(palace, job)
    with history._store(palace, job)._connect(True) as conn:
        history._schema(conn)
    history._publish(palace, job)
    cap = history.MAX_STORE_BYTES // 3
    usage = {original: cap - 200_000, active: cap}
    monkeypatch.setattr(history, "_store_used", lambda store: usage[store.directory.name])
    save = history._save_job
    fired = []

    def interrupted(path, current):
        store = history._store(palace, current)
        public = (
            db_rows(history, palace, current, "SELECT count(*) FROM history_occurrences")[0][0]
            if store.db_path.exists()
            else 0
        )
        if not fired and public == 1:
            fired.append(True)
            raise OSError("fixture crash after staged publication receipt")
        return save(path, current)

    monkeypatch.setattr(history, "_save_job", interrupted)
    assert finish_projected(history, palace)["status"] == "unavailable"
    assert fired
    durable = history._load_job(palace)
    assert durable["store_id"] == original and durable["cursor"]["offset"] == 0
    assert "inflight" not in durable
    monkeypatch.setattr(history, "_save_job", save)
    result = finish_projected(history, palace)
    assert result["state"] == "complete" and result["indexed_rows"] == 1
    assert reader.pages.count(0) == 1
    assert db_rows(history, palace, result, "SELECT count(*) FROM history_occurrences") == [(1,)]


def test_repeated_projected_page_death_stops_at_visible_durable_pending_row(
    history, tmp_path, archive, monkeypatch
):
    palace, pin, reader = projected_fixture(history, tmp_path, archive, monkeypatch)
    factory = history._projected_row

    def failing(*args):
        instance = factory(*args)

        def page(*args):
            raise OSError("fixture decode death")

        instance.page = page
        return instance

    monkeypatch.setattr(history, "_projected_row", failing)
    assert history.history_operation(palace, "index", {})["status"] == "unavailable"
    assert history.history_operation(palace, "index", {})["status"] == "unavailable"
    stopped = history.history_operation(palace, "index", {})
    assert stopped["state"] == "blocked"
    assert stopped["partial_row"]["state"] == "blocked"
    assert stopped["reason"] == "interrupted_native_projection"
    starts = len(reader.starts)
    assert history.history_operation(palace, "index", {})["state"] == "blocked"
    assert len(reader.starts) == starts
    assert history._load_job(palace)["cursor"] == {"fragment": 0, "offset": 0}
    assert db_rows(history, palace, pin, "SELECT count(*) FROM history_occurrences") == [(0,)]


def test_projected_row_capacity_refusal_keeps_original_cursor_and_no_public_text(
    history, tmp_path, archive, monkeypatch
):
    palace, pin, reader = projected_fixture(history, tmp_path, archive, monkeypatch)
    factory = history._projected_row

    def impossible(*args):
        instance = factory(*args)
        header = instance.header

        def declared():
            return {**header(), "text_bytes": 1024**3, "text_characters": 1024**3}

        instance.header = declared
        return instance

    monkeypatch.setattr(history, "_projected_row", impossible)
    # Exercise the per-store capacity refusal independently of the test host's
    # changing free disk space; low-disk admission has separate coverage.
    monkeypatch.setattr(history, "_free_bytes", lambda path: 1024**4)
    result = history.history_operation(palace, "index", {})
    assert result["status"] == "quota" and not result["coverage_complete"]
    assert history._load_job(palace)["cursor"] == {"fragment": 0, "offset": 0}
    assert reader.pages == []
    assert db_rows(history, palace, pin, "SELECT count(*) FROM chunks") == [(0,)]
    starts = len(reader.starts)
    assert history.history_operation(palace, "index", {})["reason"] == "row_output_capacity"
    assert len(reader.starts) == starts


def test_failed_native_batch_is_released_before_opening_projected_reader(
    history, tmp_path, archive, monkeypatch
):
    palace, _, reader = projected_fixture(history, tmp_path, archive, monkeypatch)
    references = []

    class NativeBatch:
        pass

    def oversized(*args):
        batch = NativeBatch()
        references.append(weakref.ref(batch))
        raise history._HistoryError("native_batch_size")
        yield

    factory = history._projected_row

    def admitted(*args):
        assert references[-1]() is None, "failed native traceback retained its batch"
        return factory(*args)

    monkeypatch.setattr(history, "_scan_rows", oversized)
    monkeypatch.setattr(history, "_projected_row", admitted)
    assert history.history_operation(palace, "index", {})["status"] == "ok"


@pytest.mark.parametrize(
    "phase,failure",
    [
        ("hash", "deadline"),
        ("hash", "death"),
        ("publication", "deadline"),
        ("publication", "death"),
        ("publication", "quota"),
    ],
)
def test_full_staged_final_phase_failures_are_bounded_and_retain_pending_data(
    history, tmp_path, archive, monkeypatch, phase, failure
):
    palace, pin, reader = projected_fixture(history, tmp_path, archive, monkeypatch)
    prepare_projected_phase(history, palace, phase)
    monkeypatch.setattr(
        history, "_projected_row", lambda *a: pytest.fail("ready row reopened native reader")
    )

    class WorkerDeath(BaseException):
        pass

    def failed(*args):
        if failure == "death":
            raise WorkerDeath()
        if failure == "quota":
            raise history._Quota()
        if phase == "hash":
            return None
        raise history._HistoryError("deadline")

    monkeypatch.setattr(history, "_stage_hash" if phase == "hash" else "_stage_publish", failed)
    for _ in range(2):
        if failure == "death":
            with pytest.raises(WorkerDeath):
                history.history_operation(palace, "index", {})
        else:
            history.history_operation(palace, "index", {})
    stopped = history.history_operation(palace, "index", {})
    assert stopped["state"] == "blocked"
    assert stopped["partial_row"]["state"] == "blocked"
    assert phase in stopped["reason"]
    assert history._load_job(palace)["cursor"] == {"fragment": 0, "offset": 0}
    assert db_rows(history, palace, pin, "SELECT count(*) FROM history_staged_rows") == [(1,)]
    assert db_rows(history, palace, pin, "SELECT count(*) FROM history_staged_chunks")[0][0] > 0
    for table in ("chunks", "lexical", "history_occurrences"):
        assert db_rows(history, palace, pin, "SELECT count(*) FROM " + table) == [(0,)]


@pytest.mark.parametrize("phase", ["hash", "publication"])
def test_interactive_yield_during_staged_final_phase_does_not_consume_failure_budget(
    history, tmp_path, archive, monkeypatch, phase
):
    palace, pin, reader = projected_fixture(history, tmp_path, archive, monkeypatch)
    prepare_projected_phase(history, palace, phase)
    name = "_stage_hash" if phase == "hash" else "_stage_publish"
    original = getattr(history, name)
    waiting = []

    def interrupted(*args):
        waiting.append(True)
        return original(*args)

    with monkeypatch.context() as midway:
        midway.setattr(history, name, interrupted)
        midway.setattr(history, "_interactive_waiting", lambda: bool(waiting))
        result = history.history_operation(palace, "index", {})
    assert result["yielded"] == "interactive_waiting" and result["state"] == "indexing"
    assert db_rows(
        history,
        palace,
        pin,
        "SELECT hash_failures,publication_failures,phase_inflight FROM history_staged_rows",
    ) == [(0, 0, None)]
    assert db_rows(history, palace, pin, "SELECT count(*) FROM chunks") == [(0,)]
    assert finish_projected(history, palace)["state"] == "complete"


@pytest.mark.parametrize("phase", ["hash", "publication"])
def test_staged_final_phase_admission_deferrals_cannot_loop_forever(
    history, tmp_path, archive, monkeypatch, phase
):
    palace, pin, reader = projected_fixture(history, tmp_path, archive, monkeypatch)
    prepare_projected_phase(history, palace, phase)
    monkeypatch.setattr(history, "SLICE_SECONDS", 0.2)
    monkeypatch.setattr(
        history, "_projected_row", lambda *args: pytest.fail("final phase reopened native data")
    )
    first = history.history_operation(palace, "index", {})
    assert first["state"] == "indexing"
    second = history.history_operation(palace, "index", {})
    assert second["state"] == "blocked"
    assert second["reason"] == "staged_" + phase + "_admission_deadline"
    assert db_rows(
        history,
        palace,
        pin,
        "SELECT final_deferrals,hash_failures,publication_failures FROM history_staged_rows",
    ) == [(2, 0, 0)]
    assert db_rows(history, palace, pin, "SELECT count(*) FROM chunks") == [(0,)]
    assert history._load_job(palace)["cursor"] == {"fragment": 0, "offset": 0}
