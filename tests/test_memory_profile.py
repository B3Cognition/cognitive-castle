"""Provider recall is scoped, explicit about failures and relevance-only."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cognitive_castle import searcher
from cognitive_castle.config import CognitiveCastleConfig


@pytest.fixture
def recall(monkeypatch, tmp_path):
    rows = [
        {
            "id": "a",
            "text": "exact α words",
            "wing": "approved",
            "metadata_json": '{"revision":"r1"}',
        },
        {"id": "b", "text": "other words", "wing": "approved"},
    ]
    col = Mock()
    col.vector_search.return_value = rows
    col.fts_search.return_value = []
    col.get_by_ids.side_effect = lambda ids, **kw: [r.copy() for r in rows if r["id"] in ids]
    monkeypatch.setattr("cognitive_castle.palace.get_collection", lambda *a, **kw: col)
    monkeypatch.setattr("cognitive_castle.embedding.embed_texts", lambda *a, **kw: [[0.0]])
    monkeypatch.setattr("cognitive_castle.reranker.rerank", lambda *a, **kw: [-1.0, -2.0])
    return col, tmp_path, CognitiveCastleConfig()


def run(recall, **kw):
    _, path, cfg = recall
    return searcher.search_memories("query", str(path), config=cfg, profile="memory-v1", **kw)


def test_memory_profile_forbids_optional_engines(recall, monkeypatch):
    monkeypatch.setattr(
        searcher, "_apply_optional_stages", Mock(side_effect=AssertionError("optional engine"))
    )
    result = run(recall, allowed_wings=frozenset({"approved"}))
    assert [r["id"] for r in result["results"]] == ["a", "b"]
    assert [r["raw_relevance_score"] for r in result["results"]] == [-1.0, -2.0]
    assert [r["rank"] for r in result["results"]] == [1, 2]
    import hashlib

    assert (
        result["results"][0]["text_sha256"] == hashlib.sha256("exact α words".encode()).hexdigest()
    )
    assert result["results"][0]["revision"] == "r1"
    assert "wing IN ('approved')" in recall[0].vector_search.call_args.kwargs["where"]


def test_all_recall_failures_are_unavailable(recall):
    recall[0].vector_search.side_effect = RuntimeError("private backend detail")
    recall[0].fts_search.side_effect = RuntimeError("private backend detail")
    with pytest.raises(searcher.SearchError, match="unavailable"):
        run(recall)


def test_one_signal_failure_is_explicit_degradation(recall):
    recall[0].vector_search.side_effect = RuntimeError("private backend detail")
    result = run(recall)
    assert result["results"] == []
    assert result["diagnostics"]["failed_signals"] == ["dense"]
    assert result["diagnostics"]["available_signals"] == ["sparse"]
    assert result["diagnostics"]["degraded"] is True


def test_profile_rejects_explicit_advanced_mode(recall):
    with pytest.raises(ValueError, match="mode"):
        run(recall, mode="max")


def test_judge_order_survives_final_serialization(recall, monkeypatch):
    monkeypatch.setattr(searcher, "_stage_4_judge", lambda q, rows, cfg: list(reversed(rows)))
    monkeypatch.setattr(
        searcher,
        "_stage_5_soar",
        lambda rows, cfg, query="": sorted(rows, reverse=True, key=lambda x: x[0]),
    )
    monkeypatch.setattr(
        searcher,
        "_stage_6_quality",
        lambda rows, cfg: sorted(rows, reverse=True, key=lambda x: x[0]),
    )
    _, path, cfg = recall
    result = searcher.search_memories("query", str(path), config=cfg)
    assert [r["id"] for r in result["results"]] == ["b", "a"]


def test_nonfinite_reranker_is_unavailable(recall, monkeypatch):
    monkeypatch.setattr("cognitive_castle.reranker.rerank", lambda *a, **kw: [float("nan"), 1.0])
    with pytest.raises(searcher.SearchError, match="nonfinite"):
        run(recall)


def test_explicit_context_does_not_resolve_ambient_palace(recall, monkeypatch):
    from cognitive_castle.context import PalacePaths

    col, path, cfg = recall
    monkeypatch.setattr(
        "cognitive_castle.palace.get_collection", Mock(side_effect=AssertionError("ambient palace"))
    )
    context = SimpleNamespace(
        config=cfg,
        get_collection=lambda name: col,
        paths=PalacePaths.resolve(path),
        registry=None,
        graph=None,
    )
    result = searcher.search_memories("query", str(path), context=context, profile="memory-v1")
    assert len(result["results"]) == 2


def test_quality_boost_cannot_demote_signed_hit(monkeypatch):
    import sys
    from cognitive_castle.quality_rerank import apply_quality_rerank

    monkeypatch.setitem(
        sys.modules,
        "cognitive_castle.understanding",
        SimpleNamespace(
            analyze_with_enhanced_metrics=lambda text, **kwargs: {
                "enhanced_metrics": {"overall_weighted_average": 1.0 if text == "boost" else 0.0}
            }
        ),
    )
    # Current develop requires an explicit requirements profile before applying
    # quality multipliers. Keep this signed-score regression on that path.
    rows = [
        (-1.0, {"id": "a", "text": "boost", "quality_profile": "requirements"}),
        (-1.1, {"id": "b", "text": "plain", "quality_profile": "requirements"}),
    ]
    result = apply_quality_rerank(rows, CognitiveCastleConfig())
    assert result[0][1]["id"] == "a"
    assert result[0][0] > 0
    assert result[0][1]["raw_relevance_score"] == -1.0


def test_memory_profile_forbids_optional_engines_in_fresh_process(tmp_path):
    import os
    import subprocess
    import sys

    script = """
import importlib.abc
import sys
class Forbid(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + ".") for name in (
            "cognitive_castle.soar_bridge", "cognitive_castle.quality_rerank",
            "cognitive_castle.understanding", "cognitive_castle.sue",
            "cognitive_castle.judge", "cognitive_castle.llm_client", "spacy")):
            raise AssertionError("optional engine imported: " + fullname)
sys.meta_path.insert(0, Forbid())
from unittest.mock import patch
from cognitive_castle.config import CognitiveCastleConfig
from cognitive_castle.searcher import search_memories
class Collection:
    def vector_search(self, *a, **kw): return [{"id":"a", "wing":"approved", "text":"exact"}]
    def fts_search(self, *a, **kw): return []
    def get_by_ids(self, *a, **kw): return [{"id":"a", "wing":"approved", "text":"exact"}]
with patch("cognitive_castle.palace.get_collection", return_value=Collection()), patch("cognitive_castle.embedding.embed_texts", return_value=[[0.0]]), patch("cognitive_castle.reranker.rerank", return_value=[-1.0]):
    result = search_memories("query", sys.argv[1], config=CognitiveCastleConfig(), profile="memory-v1", allowed_wings=frozenset({"approved"}))
    assert result["results"][0]["text"] == "exact"
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("scores", [[0.0, 0.0], [-1.0, -1.0], [2.0, 2.0]])
def test_neutral_adjustments_preserve_order_and_raw_scores(recall, monkeypatch, scores):
    monkeypatch.setattr("cognitive_castle.reranker.rerank", lambda *a, **kw: scores)
    monkeypatch.setattr(searcher, "_stage_5_soar", lambda rows, cfg, query="": rows)
    monkeypatch.setattr(searcher, "_stage_6_quality", lambda rows, cfg: rows)
    monkeypatch.setattr(searcher, "_stage_4_judge", lambda q, rows, cfg: rows)
    _, path, cfg = recall
    result = searcher.search_memories("query", str(path), config=cfg)
    assert [r["id"] for r in result["results"]] == ["a", "b"]
    assert [r["raw_relevance_score"] for r in result["results"]] == scores


def test_recall_and_hydration_defend_allowed_wings(recall, monkeypatch):
    col, _, _ = recall
    col.vector_search.return_value.insert(0, {"id": "wrong", "wing": "denied", "text": "private"})
    original = col.get_by_ids.side_effect
    col.get_by_ids.side_effect = lambda ids, **kw: (
        original(ids) + [{"id": "injected", "wing": "denied", "text": "private"}]
    )
    result = run(recall, allowed_wings=frozenset({"approved"}))
    assert [r["id"] for r in result["results"]] == ["a", "b"]


def test_explicit_config_reaches_query_embedding(recall, monkeypatch):
    _, path, cfg = recall
    embed = Mock(return_value=[[0.0]])
    monkeypatch.setattr("cognitive_castle.embedding.embed_texts", embed)
    searcher.search_memories("query", str(path), config=cfg, mode="fast")
    assert embed.call_args.kwargs["cfg"] is cfg


def test_unverified_dense_does_not_load_embedding_model(recall, monkeypatch):
    col, _, _ = recall
    col.dense_available = False
    embed = Mock(side_effect=AssertionError("disabled embedding model loaded"))
    monkeypatch.setattr("cognitive_castle.embedding.embed_texts", embed)
    result = run(recall)
    embed.assert_not_called()
    col.vector_search.assert_not_called()
    assert result["diagnostics"]["failed_signals"] == ["dense"]
    assert result["diagnostics"]["degraded"] is True


@pytest.mark.parametrize(
    "metadata",
    [
        '{"ingest_complete":false}',
        '{"completion_protocol":1,"ingest_complete":true,"source_file":"/source","source_revision":"abc123","wing":"approved","representation":"project"}',
    ],
)
def test_memory_profile_excludes_incomplete_revision_before_rerank_budget(
    recall, monkeypatch, metadata
):
    col, _, cfg = recall
    col.vector_search.return_value[0]["metadata_json"] = metadata
    cfg._file_config["reranker_k_interactive"] = 1
    monkeypatch.setattr("cognitive_castle.reranker.rerank", lambda q, docs, **kw: [1.0] * len(docs))
    result = run(recall, n_results=1)
    assert [r["id"] for r in result["results"]] == ["b"]


def test_memory_profile_validates_graph_before_empty_entity_lookup(recall):
    col, path, cfg = recall
    col.dense_available = False
    col.fts_search.side_effect = RuntimeError("sparse unavailable")
    entities, graph_path = path / "entity_registry.json", path / "knowledge_graph.sqlite3"
    entities.write_text("{}")
    graph_path.write_bytes(b"unreadable graph")
    graph = Mock()
    graph.validate_recall.side_effect = RuntimeError("bad recall schema")
    registry = Mock()
    registry.lookup_in_text.return_value = []
    context = SimpleNamespace(
        config=cfg,
        get_collection=lambda name: col,
        paths=SimpleNamespace(root=path, entity_registry=entities, knowledge_graph=graph_path),
        graph=graph,
        registry=registry,
    )
    with pytest.raises(searcher.SearchUnavailableError):
        searcher.search_memories("unknown entity", str(path), context=context, profile="memory-v1")
    graph.validate_recall.assert_called_once_with()
    registry.lookup_in_text.assert_not_called()
