"""Completion authority cannot be borrowed by partial or unrelated records."""

import hashlib
import json

import pytest

from cognitive_castle.revisions import (
    RevisionIdentity,
    RevisionManifest,
    publish_revision,
    revision_completed,
    revision_manifest_path,
)


IDENTITY = RevisionIdentity("/source/chat", "allowed", "project")
REVISION = "a" * 64


def _metadata():
    return {
        "source_file": "/source/chat",
        "wing": "allowed",
        "representation": "project",
        "source_revision": REVISION,
        "completion_protocol": 1,
        "ingest_complete": False,
    }


def _publish(store, *, closet_ids=()):
    publish_revision(
        store.drawers,
        store.closets,
        RevisionManifest(IDENTITY, REVISION, ("member",), closet_ids),
        palace_path=store.root,
    )


def test_all_tables_are_verified_before_any_completion_hints(synthetic_palace):
    store = synthetic_palace
    store.drawers.upsert(ids=["member"], documents=["Original"], metadatas=[_metadata()])
    with pytest.raises(OSError, match="incomplete"):
        _publish(store, closet_ids=("missing-closet",))
    assert store.drawers.get(ids=["member"]).metadatas[0]["ingest_complete"] is False


def test_completed_revision_does_not_certify_extra_records(synthetic_palace):
    store = synthetic_palace
    store.drawers.upsert(ids=["member"], documents=["Original"], metadatas=[_metadata()])
    _publish(store)
    meta = store.drawers.get(ids=["member"]).metadatas[0]
    assert revision_completed(store.root, meta, record_id="member")
    assert not revision_completed(store.root, meta, record_id="extra-partial-record")


def test_retry_in_progress_is_not_visible_through_existing_manifest(synthetic_palace):
    store = synthetic_palace
    store.drawers.upsert(ids=["member"], documents=["Original"], metadatas=[_metadata()])
    _publish(store)
    store.drawers.update(ids=["member"], metadatas=[{"ingest_complete": False}])
    meta = store.drawers.get(ids=["member"]).metadatas[0]
    assert not revision_completed(store.root, meta)


def test_manifest_counts_and_digests_must_agree(synthetic_palace):
    store = synthetic_palace
    store.drawers.upsert(ids=["member"], documents=["Original"], metadatas=[_metadata()])
    _publish(store)
    meta = store.drawers.get(ids=["member"]).metadatas[0]
    path = revision_manifest_path(store.root, IDENTITY, REVISION)
    value = json.loads(path.read_text())
    value.pop("checksum")
    value["drawer_count"] = 2
    value["checksum"] = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    path.write_text(json.dumps(value))
    assert not revision_completed(store.root, meta)


def test_external_collection_uses_legacy_completion_without_get():
    class ExternalCollection:
        def __init__(self):
            self.complete = False

        def update(self, *, ids, metadatas):
            assert ids == ["last"]
            self.complete = metadatas == [{"ingest_complete": True, "completion_protocol": 0}]

    external = ExternalCollection()
    publish_revision(
        external,
        None,
        RevisionManifest(IDENTITY, REVISION, ("first", "last")),
        palace_path=None,
    )
    assert external.complete


@pytest.mark.parametrize("table_name", ["castle_drawers", "castle_closets"])
def test_derived_pruning_rejects_hints_without_published_completion(synthetic_palace, table_name):
    from cognitive_castle.prune_revisions import plan_table

    store = synthetic_palace
    identity = RevisionIdentity("/source/chat", "allowed", "general")
    old_meta = dict(_metadata(), representation="general", filed_at="2026-01-01")
    for table, rid in ((store.drawers, "old-drawer"), (store.closets, "old-closet")):
        table.upsert(ids=[rid], documents=["Old verified extraction"], metadatas=[old_meta])
    publish_revision(
        store.drawers,
        store.closets,
        RevisionManifest(identity, REVISION, ("old-drawer",), ("old-closet",)),
        palace_path=store.root,
    )
    # All row hints can have been written before atomic manifest publication
    # failed. They cannot authorize pruning the last verified derived view.
    newer = dict(old_meta, source_revision="b" * 64, filed_at="2026-02-01", ingest_complete=True)
    for table, rid in ((store.drawers, "new-drawer"), (store.closets, "new-closet")):
        table.upsert(ids=[rid], documents=["Partial newer extraction"], metadatas=[newer])
    collection = store.drawers if table_name == "castle_drawers" else store.closets
    plans, _ = plan_table(collection, table_name)
    assert plans == []


def test_completed_source_remains_readable_after_original_symlink_disappears(
    synthetic_palace, tmp_path
):
    target, alias = tmp_path / "source.md", tmp_path / "alias.md"
    target.write_text("Original source")
    alias.symlink_to(target)
    store = synthetic_palace
    meta = dict(_metadata(), source_file=str(alias))
    store.drawers.upsert(ids=["member"], documents=["Original source"], metadatas=[meta])
    publish_revision(
        store.drawers,
        None,
        RevisionManifest(
            RevisionIdentity(str(target), "allowed", "project"), REVISION, ("member",)
        ),
        palace_path=store.root,
    )
    alias.unlink()
    published_meta = store.drawers.get(ids=["member"]).metadatas[0]
    assert revision_completed(store.root, published_meta, record_id="member")


def test_completion_and_reuse_respect_bounded_backend_requests(synthetic_palace, monkeypatch):
    from cognitive_castle import revisions

    ids = tuple(f"member-{i}" for i in range(6))
    collection = synthetic_palace.drawers
    collection.upsert(
        ids=list(ids),
        documents=[f"Original {i}" for i in range(6)],
        metadatas=[_metadata() for _ in ids],
    )
    monkeypatch.setattr(revisions, "_REVISION_BATCH_SIZE", 2, raising=False)
    original_get, original_update = collection.get, collection.update

    def get(**kwargs):
        if len(kwargs.get("ids") or []) > 2:
            raise OSError("backend read request limit")
        return original_get(**kwargs)

    def update(**kwargs):
        if len(kwargs.get("ids") or []) > 2:
            raise OSError("backend update request limit")
        return original_update(**kwargs)

    monkeypatch.setattr(collection, "get", get)
    monkeypatch.setattr(collection, "update", update)
    publish_revision(
        collection,
        None,
        RevisionManifest(IDENTITY, REVISION, ids),
        palace_path=synthetic_palace.root,
    )
    assert revisions.reuse_completed_revision(
        collection, None, IDENTITY, REVISION, signature={"source_size": 6}
    )
    assert all(
        revision_completed(synthetic_palace.root, meta, record_id=rid)
        for rid, meta in zip(collection.get().ids, collection.get().metadatas)
    )
