"""Explicit palace contexts do not mutate or borrow sibling state."""

import json
from types import SimpleNamespace

import pytest


def _cfg(**overrides):
    values = dict(
        embedder_dim=4,
        embedder_model="test/local",
        embedder_identity="test-v1",
        embedding_device="cpu",
        collection_name="castle_drawers",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _prepared_table(root, *, identity="test-v1", fts=True):
    import lancedb
    from cognitive_castle.backends.lancedb_backend import _build_metadata_schema, _build_schema

    db = lancedb.connect(str(root / "lancedb"))
    table = db.create_table("castle_drawers", schema=_build_schema(_cfg()))
    table.add(
        [
            {
                "id": "drawer-a",
                "vector": [1.0, 0.0, 0.0, 0.0],
                "text": "Tea is preferred.  \n",
                "metadata_json": '{"wing":"tea"}',
                "wing": "tea",
                "room": "day",
                "source_file": "source-a",
                "chunk_index": 0,
                "decay_score": 1.0,
            }
        ]
    )
    if fts:
        table.create_fts_index("text")
    if identity is not None:
        metadata = db.create_table("castle_metadata", schema=_build_metadata_schema())
        metadata.add([{"key": "embedder_identity", "value": identity}])
    return table


def _tree(root):
    return {
        str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns, p.stat().st_mode)
        for p in root.rglob("*")
        if p.is_file()
    }


def test_read_only_open_has_no_storage_mutation(tmp_path):
    from cognitive_castle.context import CastleContext, PalacePaths

    _prepared_table(tmp_path)
    tmp_path.chmod(0o755)
    before = _tree(tmp_path)
    paths = PalacePaths.resolve(tmp_path)
    context = CastleContext.open(paths, config=_cfg())
    collection = context.get_collection()
    assert collection.get(ids=["drawer-a"]).documents == ["Tea is preferred.  \n"]
    assert collection.vector_search([1.0, 0.0, 0.0, 0.0])[0]["id"] == "drawer-a"
    assert collection.fts_search("Tea")[0]["id"] == "drawer-a"
    assert collection.palace_path == str(tmp_path.resolve())
    context.close()
    assert _tree(tmp_path) == before
    assert tmp_path.stat().st_mode & 0o777 == 0o755


def test_sibling_palaces_do_not_share_registry(tmp_path):
    from cognitive_castle.context import CastleContext, PalacePaths

    for name, person in [("a", "Alice"), ("b", "Bob")]:
        state = tmp_path / name / ".castle"
        state.mkdir(parents=True)
        (state / "entity_registry.json").write_text(json.dumps({"people": {person: {}}}))
    contexts = [
        CastleContext.open(PalacePaths.resolve(tmp_path / name), config=_cfg())
        for name in ("a", "b")
    ]
    assert set(contexts[0].registry.people) == {"Alice"}
    assert set(contexts[1].registry.people) == {"Bob"}
    with pytest.raises(PermissionError):
        contexts[0].registry.save()
    for context in contexts:
        context.close()


def test_default_legacy_layout_remains_readable(tmp_path, monkeypatch):
    from cognitive_castle.context import PalacePaths

    monkeypatch.setenv("HOME", str(tmp_path))
    base = tmp_path / ".castle"
    (base / "palace").mkdir(parents=True)
    (base / "knowledge_graph.sqlite3").write_bytes(b"legacy")
    (base / "entity_registry.json").write_text("{}")
    paths = PalacePaths.resolve(base / "palace")
    assert paths.knowledge_graph == base / "knowledge_graph.sqlite3"
    assert paths.entity_registry == base / "entity_registry.json"


def test_ambiguous_layout_requires_migration(tmp_path):
    from cognitive_castle.context import PalacePaths

    (tmp_path / "palace").mkdir()
    (tmp_path / "knowledge_graph.sqlite3").write_bytes(b"shared legacy graph")
    with pytest.raises(ValueError, match="migration"):
        PalacePaths.resolve(tmp_path / "palace")


@pytest.mark.parametrize("target", ["../../other.sqlite3", "/tmp/other.sqlite3"])
def test_path_manifest_cannot_escape_palace(tmp_path, target):
    from cognitive_castle.context import PalacePaths

    state = tmp_path / ".castle"
    state.mkdir()
    (state / "paths.json").write_text(json.dumps({"version": 1, "knowledge_graph": target}))
    with pytest.raises(ValueError, match="manifest"):
        PalacePaths.resolve(tmp_path)


def test_paths_resolve_aliases_and_missing_context_does_not_create(tmp_path):
    from cognitive_castle.context import CastleContext, PalacePaths

    root = tmp_path / "palace"
    root.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    assert PalacePaths.resolve(alias) == PalacePaths.resolve(root)
    missing = tmp_path / "absent"
    with pytest.raises(FileNotFoundError):
        CastleContext.open(PalacePaths.resolve(missing), config=_cfg())
    assert not missing.exists()


def test_explicit_config_ignores_ambient_provider_changes(tmp_path, monkeypatch):
    from cognitive_castle.config import CognitiveCastleConfig
    from cognitive_castle.context import CastleContext, PalacePaths

    monkeypatch.setenv("CASTLE_EMBEDDER_MODEL", "first/model")
    monkeypatch.setenv("CASTLE_EMBEDDING_DEVICE", "cpu")
    config = CognitiveCastleConfig(config_dir=tmp_path / "config")
    context = CastleContext.open(PalacePaths.resolve(tmp_path), config=config)
    monkeypatch.setenv("CASTLE_EMBEDDER_MODEL", "second/model")
    monkeypatch.setenv("CASTLE_EMBEDDING_DEVICE", "cuda")
    assert context.config.embedder_model == "first/model"
    assert context.config.embedding_device == "cpu"
    context.close()


@pytest.mark.parametrize("identity", [None, "other-model"])
def test_read_only_legacy_identity_disables_dense_but_preserves_fts(tmp_path, identity):
    from cognitive_castle.backends.base import EmbedderIdentityMismatchError
    from cognitive_castle.context import CastleContext, PalacePaths

    _prepared_table(tmp_path, identity=identity)
    before = _tree(tmp_path)
    with CastleContext.open(PalacePaths.resolve(tmp_path), config=_cfg()) as context:
        collection = context.get_collection()
        with pytest.raises(EmbedderIdentityMismatchError):
            collection.vector_search([1.0, 0.0, 0.0, 0.0])
        with pytest.raises(EmbedderIdentityMismatchError):
            collection.query(query_embeddings=[[1.0, 0.0, 0.0, 0.0]])
        assert collection.fts_search("Tea")[0]["id"] == "drawer-a"
        assert collection.get(ids=["drawer-a"]).ids == ["drawer-a"]
    assert _tree(tmp_path) == before


@pytest.mark.parametrize("operation", ["add", "upsert", "update", "delete", "fts"])
def test_read_only_collection_rejects_every_mutation(tmp_path, operation):
    from cognitive_castle.context import CastleContext, PalacePaths

    _prepared_table(tmp_path)
    before = _tree(tmp_path)
    with CastleContext.open(PalacePaths.resolve(tmp_path), config=_cfg()) as context:
        collection = context.get_collection()
        with pytest.raises(PermissionError):
            if operation == "fts":
                collection._ensure_fts_index(replace=True)
            elif operation == "delete":
                collection.delete(ids=["drawer-a"])
            else:
                getattr(collection, operation)(
                    ids=["drawer-a"], documents=["changed"], embeddings=[[1.0, 0.0, 0.0, 0.0]]
                )
    assert _tree(tmp_path) == before


def test_read_only_missing_fts_reports_unavailability_without_rebuild(tmp_path):
    from cognitive_castle.backends.base import BackendError
    from cognitive_castle.context import CastleContext, PalacePaths

    _prepared_table(tmp_path, fts=False)
    before = _tree(tmp_path)
    with CastleContext.open(PalacePaths.resolve(tmp_path), config=_cfg()) as context:
        with pytest.raises(BackendError):
            context.get_collection().fts_search("Tea")
    assert _tree(tmp_path) == before


def test_read_only_missing_collection_does_not_create_table(tmp_path):
    from cognitive_castle.context import CastleContext, PalacePaths

    _prepared_table(tmp_path)
    before = _tree(tmp_path)
    with CastleContext.open(PalacePaths.resolve(tmp_path), config=_cfg()) as context:
        with pytest.raises(FileNotFoundError):
            context.get_collection("castle_closets")
    assert _tree(tmp_path) == before


def test_private_state_symlink_cannot_escape_palace(tmp_path):
    from cognitive_castle.context import PalacePaths

    root, outside = tmp_path / "palace", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / ".castle").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="migration"):
        PalacePaths.resolve(root)


def test_read_only_index_symlink_cannot_borrow_another_palace(tmp_path):
    from cognitive_castle.context import CastleContext, PalacePaths

    root, outside = tmp_path / "palace", tmp_path / "outside"
    root.mkdir()
    _prepared_table(outside)
    (root / "lancedb").symlink_to(outside / "lancedb", target_is_directory=True)
    with CastleContext.open(PalacePaths.resolve(root), config=_cfg()) as context:
        with pytest.raises(FileNotFoundError):
            context.get_collection()


def test_long_lived_read_only_context_sees_new_committed_records(tmp_path):
    from cognitive_castle.backends.lancedb_backend import LanceDBBackend
    from cognitive_castle.backends.base import PalaceRef
    from cognitive_castle.context import CastleContext, PalacePaths

    _prepared_table(tmp_path)
    with CastleContext.open(PalacePaths.resolve(tmp_path), config=_cfg()) as context:
        reader = context.get_collection()
        assert reader.get(ids=["new-record"]).ids == []
        writer = LanceDBBackend(cfg=_cfg())
        collection = writer.get_collection(
            palace=PalaceRef(id=str(tmp_path), local_path=str(tmp_path)),
            collection_name="castle_drawers",
            create=False,
        )
        collection.add(
            ids=["new-record"],
            documents=["Coffee new committed evidence"],
            metadatas=[{"wing": "tea"}],
            embeddings=[[0.0, 1.0, 0.0, 0.0]],
        )
        collection._ensure_fts_index(replace=True)
        after_write = _tree(tmp_path)
        assert reader.get(ids=["new-record"]).documents == ["Coffee new committed evidence"]
        assert reader.vector_search([0.0, 1.0, 0.0, 0.0], n_results=1)[0]["id"] == "new-record"
        assert reader.fts_search("Coffee")[0]["id"] == "new-record"
        assert context.get_collection().get(ids=["new-record"]).ids == ["new-record"]
        assert _tree(tmp_path) == after_write
        writer.close()
