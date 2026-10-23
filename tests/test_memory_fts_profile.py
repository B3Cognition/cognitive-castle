"""The default provider serves scoped evidence without neural dependencies."""

import json
import subprocess
import sys

import pytest

from cognitive_castle.memory import MemoryService
from cognitive_castle.memory_types import MemoryError


def test_fts_search_in_fresh_process_never_imports_models_or_optional_engines(tmp_path):
    script = r"""
import importlib.abc, sys
from types import SimpleNamespace
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(("torch", "sentence_transformers", "cognitive_castle.embedding",
            "cognitive_castle.reranker", "cognitive_castle.soar", "cognitive_castle.sue",
            "cognitive_castle.quality", "cognitive_castle.understanding", "spacy")):
            raise AssertionError("forbidden import: " + fullname)
sys.meta_path.insert(0, Guard())
from cognitive_castle.config import CognitiveCastleConfig
from cognitive_castle.context import PalacePaths
from cognitive_castle.searcher import search_memories, SearchUnavailableError
rows = [
    {"id":"foreign", "text":"secret", "wing":"denied"},
    {"id":"incomplete", "text":"draft", "wing":"allowed", "metadata_json":'{"ingest_complete":false}'},
    {"id":"a", "text":"SQLite exact evidence", "wing":"allowed"},
    {"id":"b", "text":"Other evidence", "wing":"allowed"},
]
class Collection:
    def fts_search(self, query, **kwargs): return rows
    def vector_search(self, *args, **kwargs): raise AssertionError("dense invoked")
    def get_by_ids(self, ids): return [r.copy() for r in rows if r["id"] in ids]
col = Collection()
context = SimpleNamespace(config=CognitiveCastleConfig(), paths=PalacePaths.resolve(sys.argv[1]), get_collection=lambda name:col)
result = search_memories("SQLite", sys.argv[1], context=context, profile="memory-fts-v1", allowed_wings=frozenset({"allowed"}))
assert [r["id"] for r in result["results"]] == ["a", "b"]
assert result["diagnostics"]["available_signals"] == ["sparse"]
assert result["diagnostics"]["failed_signals"] == []
assert set(result["diagnostics"]["disabled_signals"]) == {"dense", "kg"}
assert result["diagnostics"]["models"] == {}
rows[:] = [
    {"id":"old", "text":"Old decision", "wing":"allowed", "metadata_json":'{"filed_at":"2000-01-01T00:00:00Z"}'},
    {"id":"recent", "text":"New decision", "wing":"allowed", "metadata_json":'{"filed_at":"2099-01-01T00:00:00Z"}'},
]
result = search_memories("decision", sys.argv[1], context=context, profile="memory-fts-v1", allowed_wings=frozenset({"allowed"}))
assert [r["id"] for r in result["results"]] == ["recent", "old"], "capture recency was ignored"
def fail(*args, **kwargs): raise OSError("FTS broken")
col.fts_search = fail
try:
    search_memories("SQLite", sys.argv[1], context=context, profile="memory-fts-v1")
except SearchUnavailableError: pass
else: raise AssertionError("failed FTS silently fell back")
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr


def test_default_health_requires_fts_and_does_not_degrade_for_unverified_dense(synthetic_palace):
    from cognitive_castle.config import CognitiveCastleConfig
    from cognitive_castle.context import CastleContext, PalacePaths
    from cognitive_castle.provider_setup import prepare_provider

    paths = PalacePaths.resolve(synthetic_palace.root)
    cfg = CognitiveCastleConfig()
    cfg._file_config = {"embedder_dim": 4, "embedder_model": "unverified"}
    prepare_provider(paths, namespace="fts", config=cfg)
    with CastleContext.open(paths, config=cfg, read_only=True) as context:
        provider = MemoryService(context, namespace="fts", allowed_wings={"allowed"})
        assert not context.get_collection().dense_available
        assert provider.health().profile == "memory-fts-v1"
        assert provider.health().status == "ready"
        dense = MemoryService(
            context, namespace="fts", allowed_wings={"allowed"}, profile="memory-v1"
        )
        assert dense.health().profile == "memory-v1"
        assert dense.health().degraded_signals == ("dense",)
        assert provider.health().fingerprint != dense.health().fingerprint
        with pytest.raises(MemoryError, match="invalid_request"):
            MemoryService(context, namespace="fts", allowed_wings={"allowed"}, profile="max")


def test_default_worker_starts_and_searches_with_models_forbidden(synthetic_palace, tmp_path):
    from cognitive_castle.config import CognitiveCastleConfig
    from cognitive_castle.context import PalacePaths
    from cognitive_castle.provider_setup import prepare_provider

    config = tmp_path / "config.json"
    config.write_text(json.dumps({"embedder_dim": 4, "embedder_model": "unverified"}))
    prepare_provider(
        PalacePaths.resolve(synthetic_palace.root),
        namespace="fts",
        config=CognitiveCastleConfig(config_dir=tmp_path),
    )
    script = r"""
import importlib.abc, importlib.machinery, runpy, sys
attempts = []
class ForbiddenLoader(importlib.abc.Loader):
    def create_module(self, spec): return None
    def exec_module(self, module):
        attempts.append(module.__name__)
        raise AssertionError("model imported: " + module.__name__)
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(("torch", "sentence_transformers", "cognitive_castle.embedding", "cognitive_castle.reranker")):
            return importlib.machinery.ModuleSpec(fullname, ForbiddenLoader())
sys.meta_path.insert(0, Guard())
sys.argv = ["worker"] + sys.argv[1:]
runpy.run_module("cognitive_castle.provider_worker", run_name="__main__")
assert not attempts, attempts
assert not {"torch", "sentence_transformers", "cognitive_castle.embedding", "cognitive_castle.reranker"}.intersection(sys.modules)
"""
    frames = [
        {"version": 1, "id": "1", "op": "hello", "args": {}},
        {"version": 1, "id": "2", "op": "search", "args": {"query": "SQLite"}},
        {"version": 1, "id": "3", "op": "close", "args": {}},
    ]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            "--palace",
            str(synthetic_palace.root),
            "--namespace",
            "fts",
            "--config",
            str(config),
            "--wing",
            "allowed",
        ],
        input="".join(json.dumps(frame) + "\n" for frame in frames),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    replies = [json.loads(line) for line in result.stdout.splitlines()]
    if not replies[0]["ok"]:
        pytest.fail(result.stderr)
    assert replies[0]["result"]["profile"] == "memory-fts-v1"
    assert replies[1]["ok"], replies


def test_fts_groups_exact_copies_preserves_conflicts_and_ignores_neural_budget(
    synthetic_palace, tmp_path
):
    from cognitive_castle.config import CognitiveCastleConfig
    from cognitive_castle.context import CastleContext, PalacePaths
    from cognitive_castle.provider_setup import prepare_provider

    synthetic_palace.drawers.upsert(
        ids=["old", "new", "conflict", "foreign"],
        documents=[
            "SQLite decision approved",
            "SQLite decision approved",
            "SQLite decision rejected",
            "SQLite secret",
        ],
        metadatas=[
            {"wing": "allowed", "filed_at": "2026-10-21T00:00:00Z"},
            {"wing": "allowed", "filed_at": "2026-10-22T00:00:00Z"},
            {"wing": "allowed"},
            {"wing": "denied"},
        ],
    )
    cfg = CognitiveCastleConfig(config_dir=tmp_path / "config")
    cfg._file_config = {"embedder_dim": 4, "reranker_k_interactive": 1}
    paths = PalacePaths.resolve(synthetic_palace.root)
    prepare_provider(paths, namespace="fts", config=cfg)
    with CastleContext.open(paths, config=cfg, read_only=True) as context:
        service = MemoryService(context, namespace="fts", allowed_wings={"allowed"})
        hits = service.search("SQLite").hits
        assert {hit.record_id for hit in hits} == {"new", "conflict"}
        primary = next(hit for hit in hits if hit.record_id == "new")
        assert [source.record_id for source in primary.alternate_sources] == ["old"]
        assert primary.alternate_sources_complete


def test_fts_health_refuses_broken_fts_even_with_valid_dense(synthetic_palace, monkeypatch):
    from types import SimpleNamespace
    from cognitive_castle.memory import recall_health

    col = synthetic_palace.drawers
    monkeypatch.setattr(col, "dense_available", True)

    def failed(*args, **kwargs):
        raise OSError("index failure")

    monkeypatch.setattr(col, "fts_search", failed)
    with pytest.raises(MemoryError, match="incompatible_store"):
        recall_health(SimpleNamespace(), col, profile="memory-fts-v1")


def test_fts_fingerprint_tracks_ranking_settings_without_neural_settings():
    from types import SimpleNamespace
    from cognitive_castle.memory import config_fingerprint

    first = SimpleNamespace(embedder_model="one", reranker_model_cpu="one", recency_tau_days=30)
    changed_models = SimpleNamespace(
        embedder_model="two", reranker_model_cpu="two", recency_tau_days=30
    )
    changed_rank = SimpleNamespace(
        embedder_model="one", reranker_model_cpu="one", recency_tau_days=60
    )
    assert config_fingerprint(first, "memory-fts-v1") == config_fingerprint(
        changed_models, "memory-fts-v1"
    )
    assert config_fingerprint(first, "memory-fts-v1") != config_fingerprint(
        changed_rank, "memory-fts-v1"
    )
