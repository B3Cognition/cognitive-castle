"""Stored evidence survives reindex and every directory-promotion interruption."""

from contextlib import nullcontext
from types import SimpleNamespace

import pytest


@pytest.fixture
def stored_palace(tmp_path, monkeypatch):
    import lancedb
    import pyarrow as pa
    from cognitive_castle import palace

    monkeypatch.setattr(palace, "mutation_session", lambda path: nullcontext(), raising=False)
    root = tmp_path / "palace"
    root.mkdir()
    db = lancedb.connect(str(root / "lancedb"))
    schema = pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), 2)),
            pa.field("text", pa.string()),
            pa.field("metadata_json", pa.string()),
        ]
    )
    original = [
        {
            "id": "manual",
            "vector": [1.0, 0.0],
            "text": "manual α\r\n  exact",
            "metadata_json": '{"odd":null,"wing":"project"}',
        },
        {
            "id": "historic",
            "vector": [0.0, 1.0],
            "text": "old revision\n",
            "metadata_json": '{"source_revision":"old", "complete":false}',
        },
    ]
    db.create_table("castle_drawers", data=pa.Table.from_pylist(original, schema=schema))
    db.create_table(
        "castle_closets",
        data=pa.Table.from_pylist(
            [dict(original[0], id="closet", text="→historic")], schema=schema
        ),
    )
    db.create_table(
        "castle_metadata",
        [
            {"key": "embedder_identity", "value": "old-model"},
            {"key": "custom", "value": "retained"},
        ],
    )
    (root / "knowledge_graph.sqlite3").write_bytes(b"graph evidence")
    (root / ".sue").mkdir()
    (root / ".sue" / "review.json").write_text("historical review")
    (root / "lancedb.backup-existing").mkdir()
    (root / "lancedb.backup-existing" / "keep").write_text("older backup")
    cfg = SimpleNamespace(
        embedder_dim=3,
        embedder_identity="new-model",
        embedder_model="synthetic",
        embedding_device="cpu",
    )
    monkeypatch.setattr(
        "cognitive_castle.embedding.embed_texts",
        lambda texts, **kw: [[1.0, 0.0, 0.0] for _ in texts],
    )
    return root, cfg, original


def assert_preserved(root, original):
    import lancedb

    db = lancedb.connect(str(root / "lancedb"))
    rows = sorted(db.open_table("castle_drawers").to_arrow().to_pylist(), key=lambda r: r["id"])
    assert [{k: v for k, v in r.items() if k != "vector"} for r in rows] == [
        {k: v for k, v in r.items() if k != "vector"}
        for r in sorted(original, key=lambda r: r["id"])
    ]
    assert db.open_table("castle_closets").to_arrow().to_pylist()[0]["text"] == "→historic"
    assert (root / "knowledge_graph.sqlite3").read_bytes() == b"graph evidence"
    assert (root / ".sue" / "review.json").read_text() == "historical review"
    assert (root / "lancedb.backup-existing" / "keep").read_text() == "older backup"


def test_reindex_preserves_stored_historical_and_manual_records(stored_palace):
    from cognitive_castle.reindex import reindex_palace

    root, cfg, original = stored_palace
    result = reindex_palace(root, config=cfg)
    assert result.status == "complete"
    assert result.record_count == 3
    assert_preserved(root, original)
    import lancedb

    db = lancedb.connect(str(root / "lancedb"))
    assert db.open_table("castle_drawers").schema.field("vector").type.list_size == 3
    assert {
        r["key"]: r["value"] for r in db.open_table("castle_metadata").to_arrow().to_pylist()
    } == {"embedder_identity": "new-model", "custom": "retained"}
    assert result.backup_path and (root / result.backup_path).exists()


@pytest.mark.parametrize(
    "checkpoint", ["before_staging", "before_move", "after_move", "after_promotion"]
)
def test_reindex_interruption_is_recoverable(stored_palace, monkeypatch, checkpoint):
    from cognitive_castle import reindex

    root, cfg, original = stored_palace

    def interrupt(name):
        if name == checkpoint:
            raise RuntimeError("injected crash")

    monkeypatch.setattr(reindex, "_checkpoint", interrupt)
    with pytest.raises(RuntimeError, match="injected crash"):
        reindex.reindex_palace(root, config=cfg)
    monkeypatch.setattr(reindex, "_checkpoint", lambda name: None)
    result = reindex.recover_reindex(root)
    assert result.status in {"complete", "nothing_to_recover"}
    assert_preserved(root, original)


def test_missing_source_fails_before_mutation(stored_palace):
    from cognitive_castle.reindex import reindex_palace

    root, cfg, original = stored_palace
    before = set(root.iterdir())
    with pytest.raises(FileNotFoundError):
        reindex_palace(root, config=cfg, source_paths=(root / "missing",))
    assert set(root.iterdir()) == before
    assert_preserved(root, original)


def test_cancelled_reindex_keeps_active_evidence(stored_palace):
    from cognitive_castle.reindex import ReindexCancelled, reindex_palace

    root, cfg, original = stored_palace
    with pytest.raises(ReindexCancelled):
        reindex_palace(root, config=cfg, cancelled=lambda: True)
    assert_preserved(root, original)


def test_recovery_rejects_tampered_intent(stored_palace, monkeypatch):
    import json
    from cognitive_castle import reindex

    root, cfg, original = stored_palace
    monkeypatch.setattr(
        reindex,
        "_checkpoint",
        lambda name: (_ for _ in ()).throw(RuntimeError("stop")) if name == "before_move" else None,
    )
    with pytest.raises(RuntimeError):
        reindex.reindex_palace(root, config=cfg)
    journal = root / ".reindex-intent.json"
    intent = json.loads(journal.read_text())
    intent["payload"]["operation"] = "../../elsewhere"
    journal.write_text(json.dumps(intent))
    with pytest.raises(reindex.ReindexError, match="checksum"):
        reindex.recover_reindex(root)
    assert_preserved(root, original)


def test_corrupt_stage_restores_original_and_retains_backup(stored_palace, monkeypatch):
    import shutil
    from cognitive_castle import reindex

    root, cfg, original = stored_palace

    def interrupt(name):
        if name == "after_move":
            raise RuntimeError("crashed")

    monkeypatch.setattr(reindex, "_checkpoint", interrupt)
    with pytest.raises(RuntimeError):
        reindex.reindex_palace(root, config=cfg)
    stage = next(root.glob(".reindex-stage-*"))
    shutil.rmtree(stage / "lancedb")
    result = reindex.recover_reindex(root)
    assert result.status == "rolled_back"
    assert result.backup_path and (root / result.backup_path).exists()
    assert_preserved(root, original)


def test_second_reindex_retains_every_previous_backup(stored_palace):
    from cognitive_castle.reindex import reindex_palace

    root, cfg, original = stored_palace
    first = reindex_palace(root, config=cfg)
    second = reindex_palace(root, config=cfg)
    assert first.backup_path != second.backup_path
    assert (root / first.backup_path).is_dir()
    assert (root / second.backup_path).is_dir()
    assert_preserved(root, original)


def test_reindex_embedding_receives_explicit_config(stored_palace, monkeypatch):
    from unittest.mock import Mock
    from cognitive_castle.reindex import reindex_palace

    root, cfg, _ = stored_palace
    embed = Mock(side_effect=lambda texts, **kw: [[0.0, 1.0, 0.0] for _ in texts])
    monkeypatch.setattr("cognitive_castle.embedding.embed_texts", embed)
    reindex_palace(root, config=cfg)
    assert all(call.kwargs["cfg"] is cfg for call in embed.call_args_list)


def test_existing_backup_collision_is_never_overwritten(stored_palace, monkeypatch):
    from cognitive_castle import reindex

    root, cfg, original = stored_palace
    operation = "a" * 32
    backup = root / f"lancedb.backup-{operation}"
    backup.mkdir()
    monkeypatch.setattr(reindex.uuid, "uuid4", lambda: SimpleNamespace(hex=operation))
    with pytest.raises(reindex.ReindexError, match="already exists"):
        reindex.reindex_palace(root, config=cfg)
    assert backup.is_dir() and list(backup.iterdir()) == []
    assert_preserved(root, original)
