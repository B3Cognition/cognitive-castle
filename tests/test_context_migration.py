"""Explicit auxiliary migration copies evidence without changing its sources."""

import hashlib
import json

import pytest

from cognitive_castle.knowledge_graph import KnowledgeGraph


def _registry(path, name="Alice"):
    raw = (
        json.dumps(
            {"version": 1, "people": {name: {"aliases": []}}, "projects": []},
            ensure_ascii=False,
            indent=3,
        ).encode()
        + b"\n"
    )
    path.write_bytes(raw)
    return raw


def test_explicit_migration_copies_live_wal_and_registry_without_deleting_originals(tmp_path):
    from cognitive_castle.context import CastleContext, PalacePaths
    from cognitive_castle.context_migration import migrate_auxiliary_state
    from types import SimpleNamespace

    root = tmp_path / "palace"
    root.mkdir()
    source = tmp_path / "knowledge_graph.sqlite3"
    graph = KnowledgeGraph(str(source))
    triple_id = graph.add_triple("Alice", "likes", "Tea", source_drawer_id="drawer-a")
    raw_registry = _registry(tmp_path / "entity_registry.json")
    graph_bytes = source.read_bytes()
    evidence = migrate_auxiliary_state(
        root, legacy_graph=source, legacy_registry=tmp_path / "entity_registry.json"
    )
    assert source.read_bytes() == graph_bytes
    assert (tmp_path / "entity_registry.json").read_bytes() == raw_registry
    paths = PalacePaths.resolve(root)
    assert paths.knowledge_graph == root / ".castle/knowledge_graph.sqlite3"
    assert paths.entity_registry.read_bytes() == raw_registry
    config = SimpleNamespace(embedder_dim=4)
    with CastleContext.open(paths, config=config) as context:
        assert context.graph.sources_for_triple(triple_id)[0]["source_drawer_id"] == "drawer-a"
        assert context.graph.query_entity("Alice")[0]["object"] == "Tea"
        assert set(context.registry.people) == {"Alice"}
    assert evidence["graph"]["counts"]["triples"] == 1
    assert evidence["graph"]["logical_sha256"]
    assert evidence["registry"]["sha256"] == hashlib.sha256(raw_registry).hexdigest()
    assert evidence["registry"]["people_count"] == 1
    stored = json.loads((root / ".castle/auxiliary-migration.json").read_text())
    checksum = stored.pop("checksum")
    assert checksum == hashlib.sha256(json.dumps(stored, sort_keys=True).encode()).hexdigest()
    graph.close()


def test_migration_is_idempotent_for_identical_selected_sources(tmp_path):
    from cognitive_castle.context_migration import migrate_auxiliary_state

    root = tmp_path / "palace"
    root.mkdir()
    source = tmp_path / "registry.json"
    _registry(source)
    first = migrate_auxiliary_state(root, legacy_registry=source)
    before = {
        str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in root.rglob("*")
        if p.is_file()
    }
    assert migrate_auxiliary_state(root, legacy_registry=source) == first
    assert {
        str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in root.rglob("*")
        if p.is_file()
    } == before


def test_migration_never_overwrites_a_different_private_target(tmp_path):
    from cognitive_castle.context_migration import migrate_auxiliary_state

    root = tmp_path / "palace"
    state = root / ".castle"
    state.mkdir(parents=True)
    existing = _registry(state / "entity_registry.json", "Bob")
    source = tmp_path / "registry.json"
    _registry(source, "Alice")
    with pytest.raises(FileExistsError):
        migrate_auxiliary_state(root, legacy_registry=source)
    assert (state / "entity_registry.json").read_bytes() == existing
    assert not (state / "paths.json").exists()


def test_migration_never_overwrites_an_existing_different_manifest(tmp_path):
    from cognitive_castle.context_migration import migrate_auxiliary_state

    root = tmp_path / "palace"
    state = root / ".castle"
    state.mkdir(parents=True)
    original = b'{"version":1,"knowledge_graph":"other.sqlite3"}'
    (state / "paths.json").write_bytes(original)
    source = tmp_path / "registry.json"
    _registry(source)
    with pytest.raises(FileExistsError):
        migrate_auxiliary_state(root, legacy_registry=source)
    assert (state / "paths.json").read_bytes() == original
    assert not (state / "entity_registry.json").exists()


def test_migration_validates_all_inputs_before_publication(tmp_path):
    from cognitive_castle.context_migration import migrate_auxiliary_state

    root = tmp_path / "palace"
    root.mkdir()
    graph_path = tmp_path / "graph.sqlite3"
    graph = KnowledgeGraph(str(graph_path))
    graph.add_triple("Alice", "likes", "Tea")
    invalid = tmp_path / "registry.json"
    invalid.write_text('["invalid registry"]')
    with pytest.raises(ValueError):
        migrate_auxiliary_state(root, legacy_graph=graph_path, legacy_registry=invalid)
    assert not (root / ".castle/knowledge_graph.sqlite3").exists()
    assert not (root / ".castle/paths.json").exists()
    graph.close()


def test_manifest_failure_is_retryable_and_never_changes_legacy_bytes(tmp_path, monkeypatch):
    from cognitive_castle import context_migration

    root = tmp_path / "palace"
    root.mkdir()
    source = tmp_path / "registry.json"
    original = _registry(source)
    publish = context_migration.atomic_json

    def fail_manifest(path, value):
        if path.name == "paths.json":
            raise OSError("manifest publication failed")
        return publish(path, value)

    monkeypatch.setattr(context_migration, "atomic_json", fail_manifest)
    with pytest.raises(OSError, match="manifest publication"):
        context_migration.migrate_auxiliary_state(root, legacy_registry=source)
    assert source.read_bytes() == original
    assert not (root / ".castle/paths.json").exists()
    monkeypatch.setattr(context_migration, "atomic_json", publish)
    context_migration.migrate_auxiliary_state(root, legacy_registry=source)
    assert (root / ".castle/entity_registry.json").read_bytes() == original


def test_migration_rejects_escaping_private_state(tmp_path):
    from cognitive_castle.context_migration import migrate_auxiliary_state

    root, outside = tmp_path / "palace", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / ".castle").symlink_to(outside, target_is_directory=True)
    source = tmp_path / "registry.json"
    _registry(source)
    with pytest.raises(ValueError):
        migrate_auxiliary_state(root, legacy_registry=source)
    assert list(outside.iterdir()) == []


def test_migration_requires_explicit_sources_and_existing_root(tmp_path):
    from cognitive_castle.context_migration import migrate_auxiliary_state

    with pytest.raises(ValueError):
        migrate_auxiliary_state(tmp_path)
    source = tmp_path / "registry.json"
    _registry(source)
    with pytest.raises(FileNotFoundError):
        migrate_auxiliary_state(tmp_path / "missing", legacy_registry=source)
    assert not (tmp_path / "missing").exists()


def test_graph_only_migration_does_not_import_unselected_shared_registry(tmp_path):
    from cognitive_castle.context import PalacePaths
    from cognitive_castle.context_migration import migrate_auxiliary_state

    root = tmp_path / "palace"
    root.mkdir()
    source = tmp_path / "knowledge_graph.sqlite3"
    graph = KnowledgeGraph(str(source))
    graph.add_triple("Alice", "likes", "Tea")
    _registry(tmp_path / "entity_registry.json", "Unselected")
    migrate_auxiliary_state(root, legacy_graph=source)
    assert not PalacePaths.resolve(root).entity_registry.exists()
    graph.close()


@pytest.mark.parametrize("unselected_kind", ["graph", "registry"])
def test_partial_migration_preserves_existing_in_palace_binding(tmp_path, unselected_kind):
    from cognitive_castle.context import CastleContext, PalacePaths
    from cognitive_castle.context_migration import migrate_auxiliary_state
    from types import SimpleNamespace

    root = tmp_path / "palace"
    root.mkdir()
    if unselected_kind == "graph":
        existing = root / "knowledge_graph.sqlite3"
        graph = KnowledgeGraph(str(existing))
        graph.add_triple("Alice", "likes", "Tea")
        selected = tmp_path / "selected-registry.json"
        _registry(selected, "Bob")
        arguments = {"legacy_registry": selected}
    else:
        existing = root / "entity_registry.json"
        _registry(existing, "Alice")
        selected = tmp_path / "selected-graph.sqlite3"
        graph = KnowledgeGraph(str(selected))
        graph.add_triple("Alice", "likes", "Tea")
        arguments = {"legacy_graph": selected}
    before = existing.read_bytes()
    evidence = migrate_auxiliary_state(root, **arguments)
    assert migrate_auxiliary_state(root, **arguments) == evidence
    paths = PalacePaths.resolve(root)
    bound = paths.knowledge_graph if unselected_kind == "graph" else paths.entity_registry
    assert bound == existing
    assert existing.read_bytes() == before
    with CastleContext.open(paths, config=SimpleNamespace(embedder_dim=4)) as context:
        assert context.graph.query_entity("Alice")[0]["object"] == "Tea"
        assert set(context.registry.people) == {"Bob" if unselected_kind == "graph" else "Alice"}
    graph.close()


def test_registry_only_migration_does_not_import_unselected_shared_graph(tmp_path):
    from cognitive_castle.context import PalacePaths
    from cognitive_castle.context_migration import migrate_auxiliary_state

    root = tmp_path / "palace"
    root.mkdir()
    shared = KnowledgeGraph(str(tmp_path / "knowledge_graph.sqlite3"))
    shared.add_triple("Unselected", "likes", "Tea")
    source = tmp_path / "selected-registry.json"
    _registry(source)
    migrate_auxiliary_state(root, legacy_registry=source)
    assert not PalacePaths.resolve(root).knowledge_graph.exists()
    assert shared.query_entity("Unselected")[0]["object"] == "Tea"
    shared.close()


def test_ambiguous_unselected_private_bindings_fail_before_publication(tmp_path):
    from cognitive_castle.context_migration import migrate_auxiliary_state

    root = tmp_path / "palace"
    state = root / ".castle"
    state.mkdir(parents=True)
    direct = _registry(root / "entity_registry.json", "Alice")
    private = _registry(state / "entity_registry.json", "Bob")
    graph = KnowledgeGraph(str(tmp_path / "selected-graph.sqlite3"))
    graph.add_triple("Alice", "likes", "Tea")
    with pytest.raises(ValueError, match="ambiguous"):
        migrate_auxiliary_state(root, legacy_graph=graph.db_path)
    assert (root / "entity_registry.json").read_bytes() == direct
    assert (state / "entity_registry.json").read_bytes() == private
    assert not (state / "knowledge_graph.sqlite3").exists()
    assert not (state / "paths.json").exists()
    graph.close()
