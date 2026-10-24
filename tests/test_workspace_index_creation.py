"""Empty-table index creation; legacy upgrades remain explicit operator work."""

import hashlib
import json
import os

import pytest

from cognitive_castle.fast_memory import MemoryStore
from cognitive_castle.memory_history import _schema
from cognitive_castle.unified_memory import UnifiedMemoryStore, workspace_index_specs

pytestmark = pytest.mark.skipif(os.name != "posix", reason="private POSIX storage")


def spec_for(table):
    return next(spec for spec in workspace_index_specs() if spec["table"] == table)


def index_sql(conn, table):
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name=?",
        (spec_for(table)["name"],),
    ).fetchone()
    return row[0] if row is not None else None


def test_new_live_store_installs_exact_workspace_index_on_empty_chunks(tmp_path):
    store = MemoryStore(tmp_path / ".memory")
    with store._connect(True) as conn:
        assert conn.execute("SELECT count(*) FROM chunks").fetchone()[0] == 0
        assert index_sql(conn, "chunks") == spec_for("chunks")["sql"]
    receipt = store.remember("fresh", "fresh exact workspace evidence", {"workspace": "/work"})
    assert receipt["status"] == "ok"
    result = UnifiedMemoryStore(tmp_path).context_sources("/work")
    assert [source["id"] for source in result["sources"]] == receipt["ids"]
    assert "scope_index_pending" not in result["coverage_detail"]["limitations"]


def test_new_history_registry_installs_exact_index_before_first_occurrence(tmp_path):
    store = MemoryStore(tmp_path / "history")
    with store._connect(True) as conn:
        _schema(conn)
        assert conn.execute("SELECT count(*) FROM history_occurrences").fetchone()[0] == 0
        for table in ("chunks", "history_occurrences"):
            assert index_sql(conn, table) == spec_for(table)["sql"]


def test_legacy_chunk_reads_and_writes_never_install_workspace_index(tmp_path):
    store = MemoryStore(tmp_path / ".memory")
    original = store.remember("legacy", "legacy exact evidence", {"workspace": "/work"})
    assert original["status"] == "ok"
    with store._connect(True) as conn:
        conn.execute("DROP INDEX IF EXISTS " + spec_for("chunks")["name"])
    assert store.read_sources(original["ids"])["sources"][0]["text"] == "legacy exact evidence"
    assert store.recall("legacy")["sources"]
    pending = UnifiedMemoryStore(tmp_path).context_sources("/work")
    assert pending["sources"] == []
    assert "scope_index_pending" in pending["coverage_detail"]["limitations"]
    assert store.remember("later", "later exact evidence", {"workspace": "/work"})["status"] == "ok"
    with store._connect() as conn:
        assert index_sql(conn, "chunks") is None
        assert conn.execute("SELECT count(*) FROM chunks").fetchone()[0] == 2


@pytest.mark.parametrize("populated", [False, True])
def test_existing_history_registry_is_never_implicitly_indexed(tmp_path, populated):
    store = MemoryStore(tmp_path / "history")
    with store._connect(True) as conn:
        _schema(conn)
        conn.execute("DROP INDEX IF EXISTS " + spec_for("history_occurrences")["name"])
        if populated:
            metadata = json.dumps({"workspace": "/work"})
            conn.execute(
                "INSERT INTO history_occurrences VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    "a" * 64,
                    "b" * 64,
                    0,
                    "old",
                    metadata,
                    "{}",
                    "c" * 64,
                    "[]",
                    hashlib.sha256(metadata.encode()).hexdigest(),
                    hashlib.sha256(b"{}").hexdigest(),
                ),
            )
        before = conn.execute("PRAGMA schema_version").fetchone()[0]
        _schema(conn)
        assert index_sql(conn, "history_occurrences") is None
        assert conn.execute("PRAGMA schema_version").fetchone()[0] == before
        assert conn.execute("SELECT count(*) FROM history_occurrences").fetchone()[0] == int(
            populated
        )


def test_new_registry_index_does_not_backfill_legacy_chunks(tmp_path):
    store = MemoryStore(tmp_path / "history")
    assert store.remember("legacy", "preserve old chunk", {"workspace": "/work"})["status"] == "ok"
    with store._connect(True) as conn:
        conn.execute("DROP INDEX IF EXISTS " + spec_for("chunks")["name"])
        _schema(conn)
        assert index_sql(conn, "history_occurrences") == spec_for("history_occurrences")["sql"]
        assert index_sql(conn, "chunks") is None
        assert conn.execute("SELECT text FROM chunks").fetchone()[0] == "preserve old chunk"
