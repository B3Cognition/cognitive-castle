"""Source representations must not overwrite, skip or prune each other."""

from types import SimpleNamespace

import lancedb
import pytest

from cognitive_castle import convo_miner, miner
from cognitive_castle.backends.lancedb_backend import LanceCollection, _build_schema
from cognitive_castle.prune_revisions import plan_table


@pytest.fixture
def revision_store(tmp_path, monkeypatch):
    cfg = SimpleNamespace(embedder_dim=4)
    db = lancedb.connect(str(tmp_path / "db"))
    col = LanceCollection(db.create_table("drawers", schema=_build_schema(cfg)), cfg)
    monkeypatch.setattr(
        "cognitive_castle.embedding.embed_texts",
        lambda texts, **kw: [[1.0, 0.0, 0.0, 0.0] for _ in texts],
    )
    monkeypatch.setattr(miner, "compute_novelty", lambda *a, **kw: None)
    monkeypatch.setattr(miner, "_extract_entities_for_metadata", lambda text: "")
    monkeypatch.setattr(convo_miner, "get_collection", lambda *a, **kw: col)
    monkeypatch.setattr("cognitive_castle.kg_enricher.enrich_palace", lambda *a, **kw: {})
    return col


def _seed(col, rid, representation, revision, date, wing="project"):
    meta = {
        "wing": wing,
        "source_file": "/source/chat",
        "source_revision": revision,
        "ingest_complete": True,
        "filed_at": date,
        "normalize_version": 3,
    }
    if representation is not None:
        meta["representation"] = representation
    col.upsert(
        ids=[rid],
        documents=["VIOLET MARBLE 23817"],
        metadatas=[meta],
        embeddings=[[1.0, 0.0, 0.0, 0.0]],
    )


def test_general_extraction_never_prunes_exchange(revision_store):
    _seed(revision_store, "original", "exchange", "r1", "2026-01-01")
    _seed(revision_store, "extracted", "general", "r2", "2026-01-02")
    plans, _ = plan_table(revision_store, "castle_drawers")
    assert not any("original" in plan.delete_ids for plan in plans)


@pytest.mark.parametrize("representation", [None, "project", "exchange", "diary", "sweep"])
def test_unknown_and_original_revisions_are_preserved(revision_store, representation):
    _seed(revision_store, "old", representation, "r1", "2026-01-01")
    _seed(revision_store, "new", representation, "r2", "2026-01-02")
    assert plan_table(revision_store, "castle_drawers")[0] == []


def test_same_source_in_other_wing_is_not_skipped(revision_store, tmp_path):
    source = tmp_path / "source.md"
    source.write_text("Exact original project source.\n")
    miner.process_file(source, tmp_path, revision_store, "one", [], "test", False)
    count, _ = miner.process_file(source, tmp_path, revision_store, "two", [], "test", False)
    assert count > 0
    assert {m["wing"] for m in revision_store.get().metadatas} == {"one", "two"}


def test_same_source_in_other_representation_is_not_skipped(revision_store, tmp_path):
    source = tmp_path / "chat.txt"
    source.write_text(
        "> VIOLET MARBLE 23817\nWe decided to use SQLite because this architecture needs local persistence.\n"
    )
    convo_miner.mine_convos(
        str(source), str(tmp_path / "palace"), wing="project", extract_mode="exchange", skip_kg=True
    )
    convo_miner.mine_convos(
        str(source), str(tmp_path / "palace"), wing="project", extract_mode="general", skip_kg=True
    )
    assert {m.get("extract_mode") for m in revision_store.get().metadatas} == {
        "exchange",
        "general",
    }


def test_derived_pruning_is_scoped_to_wing(revision_store):
    _seed(revision_store, "one-old", "general", "r1", "2026-01-01", wing="one")
    _seed(revision_store, "two-new", "general", "r2", "2026-01-02", wing="two")
    assert plan_table(revision_store, "castle_drawers")[0] == []
