"""Legacy CLI/MCP/search entry points agree on private auxiliary paths."""

from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from cognitive_castle.kg_enricher import enrich_palace as real_enrich_palace


def _seed_registry(root, person):
    from cognitive_castle.entity_registry import EntityRegistry

    registry = EntityRegistry.load(root / ".castle")
    registry._data["people"][person] = {
        "aliases": [],
        "confidence": 1.0,
        "source": "test",
        "contexts": [],
        "relationship": "",
    }
    registry.save()


def test_custom_palace_cli_mcp_search_share_graph(synthetic_palace, tmp_path, monkeypatch):
    from cognitive_castle import cli, kg_enricher, palace
    from cognitive_castle.config import CognitiveCastleConfig
    from cognitive_castle.searcher import search_memories

    root = synthetic_palace.root

    def get_collection(
        path=None, *, palace_path=None, collection_name="castle_drawers", create=True
    ):
        return synthetic_palace.get(path or palace_path, collection_name, create)

    monkeypatch.setattr(palace, "get_collection", get_collection)
    _seed_registry(root, "Alice")
    source = tmp_path / "project"
    source.mkdir()
    (source / "notes.md").write_text("Alice selected Tea for this exact original project.\n")
    monkeypatch.setattr(kg_enricher, "enrich_palace", real_enrich_palace)
    monkeypatch.setattr(
        kg_enricher,
        "_walk_corpus",
        lambda col, **kw: ({"Alice": set(col.list_drawer_ids())}, Counter({"Alice": 1})),
    )
    monkeypatch.setattr(kg_enricher, "_classify_and_promote", lambda **kw: [])
    cli.cmd_mine(
        SimpleNamespace(
            palace=str(root),
            dir=str(source),
            mode="project",
            wing="allowed",
            agent="test",
            limit=0,
            dry_run=False,
            include_ignored=[],
            no_gitignore=False,
            skip_kg=False,
        )
    )
    expected = root / ".castle/knowledge_graph.sqlite3"
    assert expected.exists()
    assert not (root.parent / "knowledge_graph.sqlite3").exists()
    code = """
import json
from cognitive_castle import mcp_server
result = {'path': mcp_server._kg.db_path, 'facts': mcp_server._kg.query_entity('Alice')}
mcp_server._restore_stdout()
print(json.dumps(result))
"""
    process = subprocess.run(
        [sys.executable, "-c", code, "--palace", str(root)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert process.returncode == 0, process.stderr
    mcp = json.loads(process.stdout)
    assert Path(mcp["path"]) == expected
    assert mcp["facts"]
    monkeypatch.setattr(synthetic_palace.drawers, "vector_search", lambda *a, **kw: [])
    monkeypatch.setattr(synthetic_palace.drawers, "fts_search", lambda *a, **kw: [])
    monkeypatch.setattr("cognitive_castle.reranker.rerank", lambda q, docs, **kw: [1.0] * len(docs))
    result = search_memories("Alice", str(root), mode="fast", config=CognitiveCastleConfig())
    assert result["results"]
    assert all(row["entity_match"] for row in result["results"])


def test_sibling_custom_enrichment_keeps_graphs_and_registries_private(tmp_path, monkeypatch):
    from cognitive_castle import kg_enricher, palace
    from cognitive_castle.backends.lancedb_backend import LanceDBBackend
    from cognitive_castle.config import CognitiveCastleConfig
    from cognitive_castle.context import PalacePaths
    from cognitive_castle.knowledge_graph import KnowledgeGraph

    config = SimpleNamespace(embedder_dim=4, embedder_identity="test")
    backend = LanceDBBackend(cfg=config)
    for name, person in (("one", "Alice"), ("two", "Bob")):
        root = tmp_path / name
        collection = backend.get_collection(str(root), "castle_drawers", create=True)
        collection.add(
            ids=[f"{name}-drawer"], documents=[person], embeddings=[[1.0, 0.0, 0.0, 0.0]]
        )
        _seed_registry(root, person)
        monkeypatch.setattr(palace, "get_collection", lambda *a, **kw: collection)
        monkeypatch.setattr(
            kg_enricher,
            "_walk_corpus",
            lambda *a, **kw: ({person: {f"{name}-drawer"}}, Counter({person: 1})),
        )
        monkeypatch.setattr(kg_enricher, "_classify_and_promote", lambda **kw: [])
        real_enrich_palace(str(root), CognitiveCastleConfig())
        graph = KnowledgeGraph(str(PalacePaths.resolve(root).knowledge_graph))
        assert graph.find_drawers_by_entities([person]) == [f"{name}-drawer"]
        assert graph.find_drawers_by_entities(["Bob" if person == "Alice" else "Alice"]) == []
        graph.close()
    assert not (tmp_path / "knowledge_graph.sqlite3").exists()
    assert not (tmp_path / "entity_registry.json").exists()
    backend.close()
