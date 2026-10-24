import json
import os
import sqlite3
import time

import pytest

from cognitive_castle.unified_memory import workspace_index_specs

pytestmark = pytest.mark.skipif(os.name != "posix", reason="private memory stores require POSIX")


def _database(directory, *, history=False):
    directory.mkdir(mode=0o700, parents=True)
    path = directory / "memory.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE chunks (id TEXT PRIMARY KEY, text TEXT NOT NULL, provenance TEXT NOT NULL, "
        "text_hash TEXT NOT NULL, start INTEGER NOT NULL, end INTEGER NOT NULL)"
    )
    connection.execute(
        "INSERT INTO chunks VALUES ('memory:one','exact text','{\"workspace\":\"/work\"}',"
        "'hash',0,10)"
    )
    if history:
        connection.execute(
            "CREATE TABLE history_occurrences (identity TEXT PRIMARY KEY, columns_json TEXT NOT NULL, "
            "metadata_json TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO history_occurrences VALUES ('occurrence','{\"workspace\":\"/work\"}','{}')"
        )
    connection.commit()
    connection.close()
    os.chmod(path, 0o600)
    return path


def _insert_many(path, count):
    with sqlite3.connect(path) as connection:
        connection.executemany(
            "INSERT INTO chunks VALUES (?,?,?,?,?,?)",
            [
                (
                    f"memory:{index:064x}",
                    f"exact text {index}",
                    '{"workspace":"/work"}',
                    "hash",
                    0,
                    1,
                )
                for index in range(2, count + 2)
            ],
        )


def _capture_spool(directory, files=()):
    spool = directory / "capture-spool"
    spool.mkdir(mode=0o700)
    os.chmod(spool, 0o700)
    for name, content in files:
        path = spool / name
        path.write_bytes(content)
        os.chmod(path, 0o600)
    return spool


def _setup_catalog(palace, store_id):
    root = palace / ".memory-history"
    root.mkdir(mode=0o700, exist_ok=True)
    os.chmod(root, 0o700)
    catalog = root / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "version": 1,
                "generation": 0,
                "stores": [
                    {
                        "store_id": store_id,
                        "archive_id": "fixture-archive",
                        "state": "pending",
                        "indexed_rows": 0,
                        "total_rows": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    os.chmod(catalog, 0o600)


def test_workspace_index_upgrade_builds_one_index_per_call_and_resumes(tmp_path, monkeypatch):
    from cognitive_castle.memory_scope_indexes import index_workspace_scope

    _database(tmp_path / ".memory")
    store_id = "a" * 64
    history_path = tmp_path / ".memory-history" / store_id
    _database(history_path, history=True)
    _setup_catalog(tmp_path, store_id)
    import cognitive_castle.memory_scope_indexes as scope_indexes

    monkeypatch.setattr(scope_indexes, "FREE_HEADROOM_BYTES", 0)
    monkeypatch.setattr(scope_indexes, "_free_bytes", lambda path: 10**12)

    results = [index_workspace_scope(tmp_path) for _ in range(4)]

    assert [item["state"] for item in results] == [
        "pending",
        "pending",
        "pending",
        "complete",
    ], results
    assert [item["index"] for item in results[:3]] == [
        "unified_chunk_workspace_v1",
        "unified_chunk_workspace_v1",
        "unified_history_workspace_v1",
    ]
    assert [item["store_id"] for item in results[:3]] == ["live", store_id, store_id]

    expected = {spec["name"]: spec["sql"] for spec in workspace_index_specs()}
    for path in (tmp_path / ".memory" / "memory.sqlite3", history_path / "memory.sqlite3"):
        with sqlite3.connect(path) as connection:
            indexes = dict(
                connection.execute(
                    "SELECT name,sql FROM sqlite_master WHERE type='index' AND name LIKE 'unified_%_workspace_v1'"
                )
            )
            count = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]
        assert count == 1
        for name, sql in indexes.items():
            assert sql == expected[name]


def test_workspace_index_upgrade_deadline_is_explicit_and_does_not_create_index(
    tmp_path, monkeypatch
):
    from cognitive_castle.memory_scope_indexes import index_workspace_scope

    path = _database(tmp_path / ".memory")
    import cognitive_castle.memory_scope_indexes as scope_indexes

    monkeypatch.setattr(scope_indexes, "FREE_HEADROOM_BYTES", 0)
    monkeypatch.setattr(scope_indexes, "_free_bytes", lambda path: 10**12)

    result = index_workspace_scope(tmp_path, deadline=time.monotonic() - 1)

    assert result["status"] == "deadline"
    assert result["state"] == "pending"
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='unified_chunk_workspace_v1'"
            ).fetchone()
            is None
        )


def test_workspace_index_upgrade_respects_existing_logical_page_limit(tmp_path, monkeypatch):
    from cognitive_castle import memory_scope_indexes

    path = _database(tmp_path / ".memory")
    with sqlite3.connect(path) as connection:
        page_size = connection.execute("PRAGMA page_size").fetchone()[0]
        page_count = connection.execute("PRAGMA page_count").fetchone()[0]
    monkeypatch.setattr(memory_scope_indexes, "MAX_STORE_BYTES", page_size * 3 * (page_count - 1))
    before = path.stat().st_size

    result = memory_scope_indexes.index_workspace_scope(tmp_path)

    assert result["status"] == "quota"
    assert result["state"] == "pending"
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='unified_chunk_workspace_v1'"
            ).fetchone()
            is None
        )
    assert path.stat().st_size == before


def test_workspace_index_upgrade_refuses_when_store_byte_headroom_is_exhausted(
    tmp_path, monkeypatch
):
    from cognitive_castle import memory_scope_indexes

    path = _database(tmp_path / ".memory")
    monkeypatch.setattr(memory_scope_indexes, "MAX_STORE_BYTES", path.stat().st_size)
    before = path.stat().st_size

    result = memory_scope_indexes.index_workspace_scope(tmp_path)

    assert result["status"] == "quota"
    assert result["state"] == "pending"
    assert result["reason"] == "store_byte_limit"
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='unified_chunk_workspace_v1'"
            ).fetchone()
            is None
        )
    assert path.stat().st_size == before


def test_workspace_index_upgrade_rolls_back_when_index_exceeds_page_cap(tmp_path, monkeypatch):
    from cognitive_castle import memory_scope_indexes

    path = _database(tmp_path / ".memory")
    with sqlite3.connect(path) as connection:
        page_size = connection.execute("PRAGMA page_size").fetchone()[0]
        page_count = connection.execute("PRAGMA page_count").fetchone()[0]
    monkeypatch.setattr(memory_scope_indexes, "MAX_STORE_BYTES", page_size * 3 * page_count)
    monkeypatch.setattr(memory_scope_indexes, "FREE_HEADROOM_BYTES", 0)
    monkeypatch.setattr(memory_scope_indexes, "_free_bytes", lambda path: 10**12)
    before_size = path.stat().st_size

    result = memory_scope_indexes.index_workspace_scope(tmp_path)

    assert result["status"] == "quota"
    assert result["state"] == "pending"
    assert result["reason"] == "quota"
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='unified_chunk_workspace_v1'"
            ).fetchone()
            is None
        )
        assert connection.execute("PRAGMA page_count").fetchone()[0] == page_count
    assert path.stat().st_size == before_size


def test_workspace_index_upgrade_yields_and_rolls_back_for_interactive_waiter(
    tmp_path, monkeypatch
):
    from cognitive_castle import memory_scope_indexes

    path = _database(tmp_path / ".memory")
    _insert_many(path, 10_000)
    monkeypatch.setattr(memory_scope_indexes, "FREE_HEADROOM_BYTES", 0)
    monkeypatch.setattr(memory_scope_indexes, "_free_bytes", lambda path: 10**12)
    monkeypatch.setattr(memory_scope_indexes, "_SQL_PROGRESS_STEPS", 1)
    original_index_sql = memory_scope_indexes._index_sql
    state = {"index_sql_calls": 0, "armed": False, "polls": 0}

    def track_index_sql(connection, name):
        state["index_sql_calls"] += 1
        value = original_index_sql(connection, name)
        if state["index_sql_calls"] >= 2:
            state["armed"] = True
        return value

    def interactive_waiting():
        if not state["armed"]:
            return False
        state["polls"] += 1
        return state["polls"] >= 3

    monkeypatch.setattr(memory_scope_indexes, "_index_sql", track_index_sql)
    before = path.stat().st_size

    result = memory_scope_indexes.index_workspace_scope(
        tmp_path, interactive_waiting=interactive_waiting
    )

    assert result["status"] == "pending"
    assert result["state"] == "pending"
    assert result["reason"] == "interactive_waiting"
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='unified_chunk_workspace_v1'"
            ).fetchone()
            is None
        )
        assert connection.execute("SELECT count(*) FROM chunks").fetchone()[0] == 10_001
    assert path.stat().st_size == before


def test_workspace_index_upgrade_refuses_low_free_disk_before_begin(tmp_path, monkeypatch):
    from cognitive_castle import memory_scope_indexes

    path = _database(tmp_path / ".memory")
    monkeypatch.setattr(memory_scope_indexes, "FREE_HEADROOM_BYTES", 0)
    monkeypatch.setattr(memory_scope_indexes, "_free_bytes", lambda directory: 0)
    before = path.stat().st_size

    result = memory_scope_indexes.index_workspace_scope(tmp_path)

    assert result["status"] == "quota"
    assert result["state"] == "pending"
    assert result["reason"] == "free_headroom"
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='unified_chunk_workspace_v1'"
            ).fetchone()
            is None
        )
    assert path.stat().st_size == before


def test_workspace_index_upgrade_reports_bounded_heap_refusal(tmp_path, monkeypatch):
    from cognitive_castle import memory_scope_indexes

    path = _database(tmp_path / ".memory")
    monkeypatch.setattr(memory_scope_indexes, "FREE_HEADROOM_BYTES", 0)
    monkeypatch.setattr(memory_scope_indexes, "_free_bytes", lambda directory: 10**12)

    def exhaust_bounded_heap(*args, **kwargs):
        raise MemoryError

    monkeypatch.setattr(memory_scope_indexes, "_create_index", exhaust_bounded_heap)
    before = path.stat().st_size

    result = memory_scope_indexes.index_workspace_scope(tmp_path)

    assert result == {
        "status": "unavailable",
        "state": "pending",
        "reason": "sqlite_heap_limit",
        "store_id": "live",
        "index": "unified_chunk_workspace_v1",
    }
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='unified_chunk_workspace_v1'"
            ).fetchone()
            is None
        )
    assert path.stat().st_size == before


def test_workspace_index_upgrade_accepts_and_accounts_private_capture_spool(tmp_path, monkeypatch):
    from cognitive_castle import memory_scope_indexes

    store_dir = tmp_path / ".memory"
    path = _database(store_dir)
    first = b'{"path":"/workspace/one.jsonl"}'
    second = b'{"path":"/workspace/two.jsonl"}'
    spool = _capture_spool(
        store_dir,
        [
            ("a" * 64 + ".json", first),
            ("b" * 64 + ".claimed", second),
        ],
    )
    monkeypatch.setattr(memory_scope_indexes, "FREE_HEADROOM_BYTES", 0)
    monkeypatch.setattr(memory_scope_indexes, "_free_bytes", lambda directory: 10**12)

    result = memory_scope_indexes.index_workspace_scope(tmp_path)
    _, total_bytes = memory_scope_indexes._validate_store(store_dir)

    assert result["status"] == "pending"
    assert result["store_id"] == "live"
    assert total_bytes == path.stat().st_size + len(first) + len(second)
    assert sorted(child.name for child in spool.iterdir()) == [
        "a" * 64 + ".json",
        "b" * 64 + ".claimed",
    ]


def test_workspace_index_upgrade_accepts_empty_capture_spool(tmp_path):
    from cognitive_castle import memory_scope_indexes

    store_dir = tmp_path / ".memory"
    path = _database(store_dir)
    spool = _capture_spool(store_dir)

    _, total_bytes = memory_scope_indexes._validate_store(store_dir)

    assert list(spool.iterdir()) == []
    assert total_bytes == path.stat().st_size


def test_workspace_index_upgrade_rejects_nested_capture_spool_directory(tmp_path):
    from cognitive_castle.memory_scope_indexes import index_workspace_scope

    store_dir = tmp_path / ".memory"
    path = _database(store_dir)
    nested = _capture_spool(store_dir) / "nested"
    nested.mkdir(mode=0o700)

    result = index_workspace_scope(tmp_path)

    assert result["status"] == "unavailable"
    assert result["state"] == "pending"
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='unified_chunk_workspace_v1'"
            ).fetchone()
            is None
        )


def test_workspace_index_upgrade_rejects_symlink_in_capture_spool(tmp_path):
    from cognitive_castle.memory_scope_indexes import index_workspace_scope

    store_dir = tmp_path / ".memory"
    path = _database(store_dir)
    spool = _capture_spool(store_dir)
    target = tmp_path / "outside.json"
    target.write_text("{}", encoding="utf-8")
    os.chmod(target, 0o600)
    (spool / ("c" * 64 + ".json")).symlink_to(target)

    result = index_workspace_scope(tmp_path)

    assert result["status"] == "unavailable"
    assert result["state"] == "pending"
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='unified_chunk_workspace_v1'"
            ).fetchone()
            is None
        )
