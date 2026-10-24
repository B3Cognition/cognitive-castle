"""Graph evidence survives repeat observations and read-only legacy access."""

import sqlite3

import pytest

from cognitive_castle.knowledge_graph import KnowledgeGraph


def test_repeated_fact_retains_both_sources(tmp_path):
    graph = KnowledgeGraph(str(tmp_path / "graph.sqlite3"))
    first = graph.add_triple(
        "Alice", "likes", "Tea", source_file="source-a", source_drawer_id="drawer-a"
    )
    second = graph.add_triple(
        "Alice", "likes", "Tea", source_file="source-b", source_drawer_id="drawer-b"
    )
    assert first == second
    assert set(graph.find_drawers_by_entities(["Tea"])) == {"drawer-a", "drawer-b"}
    sources = graph.sources_for_triple(first)
    assert {(s["source_file"], s["source_drawer_id"]) for s in sources} == {
        ("source-a", "drawer-a"),
        ("source-b", "drawer-b"),
    }
    # Repeating the same observation is idempotent, preserving old source columns.
    graph.add_triple("Alice", "likes", "Tea", source_file="source-b", source_drawer_id="drawer-b")
    assert len(graph.sources_for_triple(first)) == 2
    row = graph._conn().execute("SELECT * FROM triples WHERE id=?", (first,)).fetchone()
    assert row["source_file"] == "source-a"
    graph.close()


def test_distinct_queried_entities_control_kg_rank(tmp_path):
    graph = KnowledgeGraph(str(tmp_path / "graph.sqlite3"))
    # Two different subjects mention only Tea in drawer-a; drawer-z has both
    # queried endpoints on a single edge. The latter must rank first.
    graph.add_triple("Alice", "likes", "Tea", source_drawer_id="drawer-a")
    graph.add_triple("Bob", "likes", "Tea", source_drawer_id="drawer-a")
    graph.add_triple("Tea", "alternative_to", "Coffee", source_drawer_id="drawer-z")
    assert graph.find_drawers_by_entities(["Tea", "Coffee"]) == ["drawer-z", "drawer-a"]
    assert graph.find_drawers_by_entities(["Tea", "Coffee"], limit=1, offset=1) == ["drawer-a"]
    graph.close()


@pytest.mark.parametrize(
    ("valid_from", "valid_to"),
    [("2026-02-01", None), ("2026-01-01", "2026-02-01")],
)
def test_new_temporal_claim_does_not_silently_overwrite_old_interval(
    tmp_path, valid_from, valid_to
):
    graph = KnowledgeGraph(str(tmp_path / "graph.sqlite3"))
    old_id = graph.add_triple("Alice", "likes", "Tea", valid_from="2026-01-01")
    new_id = graph.add_triple("Alice", "likes", "Tea", valid_from=valid_from, valid_to=valid_to)
    assert old_id != new_id
    assert {(r["valid_from"], r["valid_to"]) for r in graph.query_entity("Alice")} == {
        ("2026-01-01", None),
        (valid_from, valid_to),
    }
    assert (
        graph.add_triple("Alice", "likes", "Tea", valid_from=valid_from, valid_to=valid_to)
        == new_id
    )
    graph.close()


def _legacy_graph(path):
    """A pre-adapter graph, using its original columns and triple ID."""
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE entities (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT DEFAULT 'unknown',
                properties TEXT DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE triples (
                id TEXT PRIMARY KEY, subject TEXT NOT NULL, predicate TEXT NOT NULL,
                object TEXT NOT NULL, valid_from TEXT, valid_to TEXT,
                confidence REAL DEFAULT 1.0, source_closet TEXT, source_file TEXT,
                extracted_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO entities (id, name) VALUES ('alice', 'Alice'), ('tea', 'Tea');
            INSERT INTO triples (id, subject, predicate, object, source_closet, source_file)
                VALUES ('original-id', 'alice', 'likes', 'tea', 'closet-a', 'source-a');
        """)


def test_writable_migration_backfills_original_evidence_once(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    _legacy_graph(path)
    for _ in range(2):
        graph = KnowledgeGraph(str(path))
        sources = graph.sources_for_triple("original-id")
        assert len(sources) == 1
        assert sources[0]["source_file"] == "source-a"
        assert sources[0]["source_closet"] == "closet-a"
        assert graph.add_triple("Alice", "likes", "Tea") == "original-id"
        assert graph.query_entity("Alice")[0]["object"] == "Tea"
        graph.close()


def test_read_only_legacy_graph_has_no_storage_mutation(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    _legacy_graph(path)
    tmp_path.chmod(0o755)
    before = path.read_bytes()
    names = set(tmp_path.iterdir())
    graph = KnowledgeGraph(str(path), read_only=True)
    assert graph.query_entity("Alice")[0]["object"] == "Tea"
    assert graph.stats()["triples"] == 1
    assert graph.find_drawers_by_entities(["Tea"]) == []
    sources = graph.sources_for_triple("original-id")
    assert len(sources) == 1
    assert sources[0]["source_file"] == "source-a"
    assert sources[0]["source_drawer_id"] is None
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        graph.add_triple("Alice", "likes", "Coffee")
    graph.close()
    assert path.read_bytes() == before
    assert set(tmp_path.iterdir()) == names
    assert tmp_path.stat().st_mode & 0o777 == 0o755


def test_read_only_missing_database_does_not_create_parent(tmp_path):
    path = tmp_path / "absent" / "graph.sqlite3"
    with pytest.raises(sqlite3.OperationalError):
        KnowledgeGraph(str(path), read_only=True)
    assert not path.parent.exists()


def test_read_only_modern_graph_reads_all_sources(tmp_path):
    path = tmp_path / "graph #?.sqlite3"
    graph = KnowledgeGraph(str(path))
    triple_id = graph.add_triple("Alice", "likes", "Tea", source_drawer_id="drawer-a")
    graph.add_triple("Alice", "likes", "Tea", source_drawer_id="drawer-b")
    graph.close()
    # Explicit operator preparation makes a closed graph readable without WAL
    # housekeeping. Read-only access must never change its journal mode itself.
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=DELETE")
    graph = KnowledgeGraph(str(path), read_only=True)
    assert set(graph.find_drawers_by_entities(["Tea"])) == {"drawer-a", "drawer-b"}
    assert len(graph.sources_for_triple(triple_id)) == 2
    graph.close()


def test_read_only_closed_wal_graph_refuses_sidecar_creation(tmp_path):
    path = tmp_path / "graph.sqlite3"
    graph = KnowledgeGraph(str(path))
    graph.add_triple("Alice", "likes", "Tea")
    graph.close()
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(sqlite3.OperationalError, match="read-only WAL.*sidecars"):
        KnowledgeGraph(str(path), read_only=True)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_read_only_live_wal_graph_sees_committed_evidence(tmp_path):
    path = tmp_path / "graph.sqlite3"
    writer = KnowledgeGraph(str(path))
    writer.add_triple("Alice", "likes", "Tea", source_drawer_id="drawer-a")
    reader = KnowledgeGraph(str(path), read_only=True)
    assert reader.find_drawers_by_entities(["Tea"]) == ["drawer-a"]
    # The second observation lives in the active WAL; immutable readers would
    # miss committed evidence (or even the schema) while appearing to succeed.
    writer.add_triple("Alice", "likes", "Tea", source_drawer_id="drawer-b")
    assert set(reader.find_drawers_by_entities(["Tea"])) == {"drawer-a", "drawer-b"}
    reader.close()
    writer.close()
