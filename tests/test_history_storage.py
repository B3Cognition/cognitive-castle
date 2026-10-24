"""History disk reservations, without models, native readers or large files."""

import importlib
import os
import time

import pytest

from cognitive_castle.fast_memory import MemoryStore, _Quota, _Unavailable

pytestmark = pytest.mark.skipif(os.name != "posix", reason="private POSIX stores")


def _root(tmp_path):
    root = tmp_path / ".memory-history"
    root.mkdir(mode=0o700)
    return root


def _file(path, size=0):
    path.parent.mkdir(mode=0o700, exist_ok=True)
    with path.open("wb") as stream:
        stream.truncate(size)
    path.chmod(0o600)
    return path


@pytest.fixture
def policy(monkeypatch):
    module = importlib.import_module("cognitive_castle.history_storage")
    monkeypatch.setattr(module, "HISTORY_STORE_BYTES", 2000)
    monkeypatch.setattr(module, "HISTORY_TOTAL_BYTES", 8000)
    monkeypatch.setattr(module, "FREE_HEADROOM_BYTES", 200)
    monkeypatch.setattr(module, "_free_bytes", lambda path: 100_000)
    return module


def test_importer_uses_history_room_without_expanding_live_quota(tmp_path, monkeypatch):
    from cognitive_castle import fast_memory, memory_history

    monkeypatch.setattr(fast_memory, "MAX_STORE_BYTES", 384 * 1024)
    try:
        storage = importlib.import_module("cognitive_castle.history_storage")
    except ModuleNotFoundError:
        storage = None  # Baseline importer still uses the live allowance.
    if storage is not None:
        monkeypatch.setattr(storage, "HISTORY_STORE_BYTES", 768 * 1024)
        monkeypatch.setattr(storage, "_free_bytes", lambda path: 10**12)
    _root(tmp_path)
    history = memory_history._store(tmp_path, {"store_id": "a" * 64})
    live = MemoryStore(tmp_path / ".memory")
    text = "verbatim " + "x" * 7991
    live_statuses = []
    for number in range(8):
        result = history.remember(str(number), text)
        assert result["status"] == "ok", result
        live_statuses.append(live.remember(str(number), text)["status"])
    assert "quota" in live_statuses
    with history._connect() as connection:
        count, size = (
            connection.execute("PRAGMA page_count").fetchone()[0],
            connection.execute("PRAGMA page_size").fetchone()[0],
        )
        assert 128 * 1024 < count * size <= 256 * 1024
    assert history.recall("verbatim")["sources"]


def test_reservation_counts_unregistered_retained_stores(policy, tmp_path):
    root = _root(tmp_path)
    target = root / ("a" * 64)
    for number in range(1, 7):
        _file(root / f"{number:064x}" / "memory.sqlite3", 1000)
    assert policy.admit_history_write(target) == 2000
    _file(root / ("7" * 64) / "memory.sqlite3", 1)
    with pytest.raises(_Quota):
        policy.admit_history_write(target)
    assert not target.exists()


def test_current_bytes_are_not_double_counted_and_headroom_is_reserved(
    policy, tmp_path, monkeypatch
):
    root = _root(tmp_path)
    target = root / ("a" * 64)
    _file(target / "memory.sqlite3", 1500)
    for number in range(6):
        _file(root / f"{number:064x}" / "memory.sqlite3", 1000)
    monkeypatch.setattr(policy, "_free_bytes", lambda path: 700)
    assert policy.admit_history_write(target) == 2000
    monkeypatch.setattr(policy, "_free_bytes", lambda path: 699)
    with pytest.raises(_Quota):
        policy.admit_history_write(target)


@pytest.mark.parametrize(
    "sidecar", ["memory.sqlite3-journal", "memory.sqlite3-wal", "memory.sqlite3-shm"]
)
def test_retained_sidecars_consume_aggregate_budget(policy, tmp_path, sidecar):
    root = _root(tmp_path)
    for number in range(6):
        _file(root / f"{number:064x}" / "memory.sqlite3", 1000)
    _file(root / ("0" * 64) / sidecar, 1)
    with pytest.raises(_Quota):
        policy.admit_history_write(root / ("a" * 64))


def test_oversized_retained_store_is_refused_even_with_aggregate_room(policy, tmp_path):
    root = _root(tmp_path)
    _file(root / ("b" * 64) / "memory.sqlite3", 2001)
    with pytest.raises(_Quota):
        policy.admit_history_write(root / ("a" * 64))


@pytest.mark.parametrize("hazard", ["symlink", "hardlink", "nested", "unknown_file"])
def test_unsafe_retained_entries_fail_before_target_creation(policy, tmp_path, hazard):
    root = _root(tmp_path)
    old = root / ("b" * 64)
    old.mkdir(mode=0o700)
    outside = _file(tmp_path / "outside", 10)
    if hazard == "symlink":
        (old / "memory.sqlite3").symlink_to(outside)
    elif hazard == "hardlink":
        os.link(outside, old / "memory.sqlite3")
    elif hazard == "nested":
        (old / "nested").mkdir(mode=0o700)
    else:
        _file(old / "unbudgeted-data", 10)
    target = root / ("a" * 64)
    with pytest.raises(_Unavailable):
        policy.admit_history_write(target)
    assert not target.exists()
    assert outside.stat().st_size == 10


def test_metadata_traversal_has_a_fixed_entry_bound(policy, tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setattr(policy, "MAX_ROOT_ENTRIES", 2)
    for name in ("job.json", "catalog.json", "catalog.lock"):
        _file(root / name)
    with pytest.raises(_Quota):
        policy.admit_history_write(root / ("a" * 64))


def test_catalog_counts_orphans_and_keeps_independent_aggregate_limit(policy, tmp_path):
    from cognitive_castle.unified_memory import register_history_store

    root = _root(tmp_path)
    for number in range(5):
        _file(root / f"{number:064x}" / "memory.sqlite3", 1700)
    result = register_history_store(tmp_path, "a" * 64, archive_id="archive", state="pending")
    assert result["status"] == "quota"
    assert not (root / "catalog.json").exists()


def test_history_refusal_precedes_sqlite_open_or_database_creation(policy, tmp_path, monkeypatch):
    import cognitive_castle.fast_memory as fast_memory

    root = _root(tmp_path)
    monkeypatch.setattr(policy, "_free_bytes", lambda path: 0)
    opened = []

    def must_not_open(*args, **kwargs):
        opened.append(True)
        pytest.fail("SQLite opened before historical write reservation")

    monkeypatch.setattr(fast_memory.sqlite3, "connect", must_not_open)
    target = root / ("a" * 64)
    assert policy.HistoryMemoryStore(target).remember("id", "exact text")["status"] == "quota"
    assert opened == []
    assert not target.exists()


def test_history_reads_do_not_run_write_admission(tmp_path, monkeypatch):
    storage = importlib.import_module("cognitive_castle.history_storage")
    _root(tmp_path)
    store = storage.HistoryMemoryStore(tmp_path / ".memory-history" / ("a" * 64))
    monkeypatch.setattr(storage, "_free_bytes", lambda path: 10**12)
    identity = store.remember("id", "continuous exact text")["ids"][0]

    def no_admission(*args, **kwargs):
        pytest.fail("read invoked historical write admission")

    monkeypatch.setattr(storage, "admit_history_write", no_admission)
    assert store.page(identity)["text"] == "continuous exact text"


def test_scope_upgrade_reserves_before_raw_sqlite_open(policy, tmp_path, monkeypatch):
    from cognitive_castle import memory_scope_indexes

    root = _root(tmp_path)
    target = root / ("a" * 64)
    _file(target / "memory.sqlite3", 10)
    monkeypatch.setattr(policy, "_free_bytes", lambda path: 0)
    monkeypatch.setattr(
        memory_scope_indexes, "_store_paths", lambda palace: [("a" * 64, target, True)]
    )
    opened = []

    def must_not_open(*args, **kwargs):
        opened.append(True)
        pytest.fail("scope upgrade opened SQLite before reservation")

    monkeypatch.setattr(memory_scope_indexes, "_connect", must_not_open)
    result = memory_scope_indexes.index_workspace_scope(tmp_path, deadline=time.monotonic() + 6)
    assert result["status"] == "quota"
    assert opened == []


@pytest.mark.parametrize("reason", ["output_capacity", "row_output_capacity"])
def test_policy_upgrade_reconsiders_only_obsolete_capacity_refusal(policy, reason):
    job = {
        "state": "blocked",
        "reason": reason,
        "cursor": {"fragment": 7, "offset": 9},
        "capacity_rejected": ["a" * 64],
        "capacity_cursor_key": "b" * 64,
        "partial_row": {"state": "awaiting_capacity"},
        "retry_cursor": "native-retry",
        "retry_count": 1,
    }
    assert policy.refresh_capacity_policy(job)
    assert job["state"] == "indexing"
    assert "reason" not in job
    assert "capacity_rejected" not in job
    assert "partial_row" not in job
    assert job["cursor"] == {"fragment": 7, "offset": 9}
    assert job["retry_cursor"] == "native-retry" and job["retry_count"] == 1
    job.update(state="blocked", reason=reason, capacity_rejected=["a" * 64])
    assert not policy.refresh_capacity_policy(job)
    assert job["reason"] == reason and job["capacity_rejected"] == ["a" * 64]


def test_policy_upgrade_preserves_native_failure_and_existing_stage(policy):
    stage = {"state": "copying", "store_id": "a" * 64, "processed_characters": 128}
    job = {"state": "blocked", "reason": "interrupted_native_projection", "partial_row": stage}
    assert policy.refresh_capacity_policy(job)
    assert job["state"] == "blocked" and job["reason"] == "interrupted_native_projection"
    assert job["partial_row"] is stage
