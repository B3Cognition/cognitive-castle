"""Exact passage grouping preserves current and alternate scoped provenance."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    from cognitive_castle.config import CognitiveCastleConfig
    from cognitive_castle.searcher import search_memories

    def run(rows, *, cap=2, mode=None, profile="memory-v1"):
        cfg = CognitiveCastleConfig(config_dir=tmp_path / "configuration")
        cfg._file_config["reranker_k_interactive"] = cap
        by_id = {row["id"]: row for row in rows}
        col = Mock()
        col.vector_search.return_value = rows
        col.fts_search.return_value = []
        col.get_by_ids.side_effect = lambda ids, **kw: [by_id[i].copy() for i in ids]
        monkeypatch.setattr("cognitive_castle.palace.get_collection", lambda *a, **kw: col)
        monkeypatch.setattr("cognitive_castle.embedding.embed_texts", lambda *a, **kw: [[0.0]])
        reranker = Mock(
            side_effect=lambda q, docs, **kw: [
                10.0 if doc == "Same exact passage." else 1.0 for doc in docs
            ]
        )
        monkeypatch.setattr("cognitive_castle.reranker.rerank", reranker)
        result = search_memories(
            "query",
            str(tmp_path / "palace"),
            config=cfg,
            profile=profile,
            mode=mode,
            allowed_wings=frozenset({"allowed"}),
            n_results=20,
        )
        return result["results"], reranker

    return run


def row(rid, text="Same exact passage.", *, captured=None, wing="allowed", source=None, **metadata):
    meta = {
        "wing": wing,
        "filed_at": captured,
        "source_file": source or f"/source/{rid}",
        "source_revision": rid,
        **metadata,
    }
    return {"id": rid, "text": text, "wing": wing, "room": "r", "metadata_json": json.dumps(meta)}


@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_versions_do_not_fill_reranker_budget(pipeline, reverse):
    rows = [
        row("old", captured="2026-10-23T12:00:00+02:00", source="/source/shared"),
        row("new", captured="2026-10-23T11:00:00Z", source="/source/shared"),
        row("other", text="A contradictory distinct passage."),
    ]
    hits, reranker = pipeline(list(reversed(rows)) if reverse else rows)
    assert [hit["id"] for hit in hits] == ["new", "other"]
    assert hits[0]["alternate_record_ids"] == ["old"]
    assert hits[0]["alternate_sources_complete"] is True
    assert len(reranker.call_args.args[1]) == 2


def test_group_preserves_different_origins_and_bounds_alternates(pipeline):
    rows = [
        row(
            f"copy{i:02}",
            captured=f"2026-10-{i + 1:02}T12:00:00+00:00",
            source=f"/different/origin/{i}",
        )
        for i in range(12)
    ]
    rows += [
        row("foreign", captured="2026-10-30T12:00:00Z", wing="foreign"),
        row("partial", captured="2026-10-31T12:00:00Z", ingest_complete=False),
    ]
    hits, _ = pipeline(rows)
    assert len(hits) == 1
    assert hits[0]["id"] == "copy11"
    assert len(hits[0]["alternate_record_ids"]) == 8
    assert hits[0]["alternate_sources_complete"] is False
    assert "foreign" not in hits[0]["alternate_record_ids"]
    assert "partial" not in hits[0]["alternate_record_ids"]


def test_unknown_or_malformed_capture_uses_stable_id_fallback(pipeline):
    hits, _ = pipeline([row("z", captured="unknown-date"), row("a", captured=None)])
    assert hits[0]["id"] == "a"
    assert hits[0]["alternate_record_ids"] == ["z"]


@pytest.mark.parametrize("older", ["2026-10-23T10:00:00", "2026-10-23T12:00:00+02:00"])
def test_legacy_naive_capture_is_ordered_as_utc_and_preserved(pipeline, older):
    hits, _ = pipeline([row("a-old", captured=older), row("z-new", captured="2026-10-23T11:00:00")])
    assert hits[0]["id"] == "z-new"
    assert hits[0]["created_at"] == "2026-10-23T11:00:00"


def test_legacy_fast_keeps_duplicate_versions(pipeline):
    hits, _ = pipeline([row("old"), row("new")], profile=None, mode="fast")
    assert len(hits) == 2
    assert all("alternate_record_ids" not in hit for hit in hits)


def test_group_retains_best_fusion_score_without_summing_copies():
    from cognitive_castle.fusion import ScoredCandidate
    from cognitive_castle.searcher import _group_memory_candidates

    rows = [
        row("old", captured="2026-10-22T00:00:00Z"),
        row("new", captured="2026-10-23T00:00:00Z"),
    ]
    scores = [
        ScoredCandidate("old", 0.0, 0.8, frozenset({"dense"})),
        ScoredCandidate("new", 0.0, 0.2, frozenset({"sparse"})),
    ]
    grouped, _ = _group_memory_candidates(scores, rows)
    assert grouped[0].drawer_id == "new"
    assert grouped[0].score == 0.8
    assert grouped[0].contributing_signals == frozenset({"dense", "sparse"})


@pytest.mark.parametrize("metadata", [{"room": "_registry"}, {"ingest_mode": "registry"}])
def test_profile_ignores_internal_registry_records(pipeline, metadata):
    registry = row("registry", text="[registry] /private/source", **metadata)
    if "room" in metadata:
        registry["room"] = metadata["room"]
    hits, _ = pipeline([registry, row("own", text="The user's literal /private/source reference.")])
    assert [hit["id"] for hit in hits] == ["own"]


@pytest.fixture
def service(synthetic_palace, monkeypatch):
    from cognitive_castle.memory import MemoryService

    root = synthetic_palace.root
    (root / ".provider").mkdir()
    (root / ".provider/identity.json").write_text(
        json.dumps({"schema_version": 1, "namespace": "dedup-test"})
    )
    specs = [
        row("old", captured="2026-10-23T12:00:00+02:00"),
        row("new", captured="2026-10-23T11:00:00Z"),
        row("origin", captured="2026-10-22T11:00:00Z", source="/independent/origin"),
        row("foreign", captured="2026-10-30T11:00:00Z", wing="other"),
        row("different", text="A conflicting statement.", captured="2026-10-24T11:00:00Z"),
    ]
    synthetic_palace.drawers.upsert(
        ids=[r["id"] for r in specs],
        documents=[r["text"] for r in specs],
        metadatas=[json.loads(r["metadata_json"]) for r in specs],
    )
    context = SimpleNamespace(
        paths=SimpleNamespace(root=root, provider=root / ".provider"),
        config=SimpleNamespace(),
        get_collection=lambda: synthetic_palace.drawers,
    )
    provider = MemoryService(context, namespace="dedup-test", allowed_wings=frozenset({"allowed"}))

    def results(rows):
        monkeypatch.setattr(
            "cognitive_castle.searcher.search_memories", lambda **kw: {"results": rows}
        )

    return provider, results


@pytest.mark.parametrize("reverse", [False, True])
def test_service_selects_newest_and_keeps_best_score_and_alternate_origins(service, reverse):
    provider, results = service
    rows = [
        {"id": "old", "score": 8.0},
        {"id": "new", "score": 2.0, "alternate_record_ids": ["origin"]},
        {"id": "different", "score": 1.0},
    ]
    results(list(reversed(rows)) if reverse else rows)
    response = provider.search("query", limit=2)
    shared = next(hit for hit in response.hits if hit.record_id == "new")
    assert shared.score == 8.0
    assert {source.record_id for source in shared.alternate_sources} == {"old", "origin"}
    assert shared.alternate_sources_complete is True
    assert len({source.source_id for source in shared.alternate_sources}) == 2
    assert [hit.rank for hit in response.hits] == [1, 2]
    assert "/source/" not in json.dumps(response.as_dict())
    assert {hit.record_id for hit in response.hits} == {"new", "different"}


def test_service_revalidates_foreign_and_changed_alternate_records(service):
    provider, results = service
    results(
        [
            {
                "id": "old",
                "score": 8.0,
                "alternate_record_ids": ["foreign", "different", "missing", "new"],
            }
        ]
    )
    hit = provider.search("query").hits[0]
    assert hit.record_id == "new"
    assert [source.record_id for source in hit.alternate_sources] == ["old"]
    assert hit.alternate_sources_complete is False


def test_service_exposes_pipeline_alternate_truncation(service):
    provider, results = service
    results(
        [
            {
                "id": "new",
                "score": 1.0,
                "alternate_record_ids": ["old"],
                "alternate_sources_complete": False,
            }
        ]
    )
    hit = provider.search("query").hits[0]
    assert [source.record_id for source in hit.alternate_sources] == ["old"]
    assert hit.alternate_sources_complete is False


def test_alternate_provenance_still_obeys_public_payload_limit(service, synthetic_palace):
    from cognitive_castle.memory_types import MemoryError

    provider, results = service
    ids, documents, metadata, hits = [], [], [], []
    for group in range(20):
        copies = [f"record-{group}-{copy}-" + "r" * 470 for copy in range(9)]
        ids.extend(copies)
        documents.extend([f"Distinct exact passage {group}."] * len(copies))
        metadata.extend([{"wing": "allowed", "source_revision": "v" * 256}] * len(copies))
        hits.append({"id": copies[0], "score": 20.0 - group, "alternate_record_ids": copies[1:]})
    synthetic_palace.drawers.upsert(ids=ids, documents=documents, metadatas=metadata)
    results(hits)
    with pytest.raises(MemoryError, match="^result_limit$"):
        provider.search("query", limit=20)
