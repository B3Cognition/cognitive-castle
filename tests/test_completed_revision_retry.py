import os

import pytest

from cognitive_castle import convo_miner, diary_ingest, miner
from cognitive_castle.revisions import revision_completed


@pytest.mark.parametrize("kind", ["project", "convos", "diary"])
def test_unchanged_completed_revision_is_never_rewritten_during_retry(
    synthetic_palace, tmp_path, monkeypatch, kind
):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    source = source_dir / ("2026-10-23.md" if kind == "diary" else "notes.md")
    source.write_bytes(
        b"## A precise decision\r\nOriginal source content stays available through every failed retry.\r\n"
        * 20
    )

    def ingest():
        if kind == "project":
            return miner.process_file(
                source,
                source_dir,
                synthetic_palace.drawers,
                "project",
                [],
                "test",
                False,
                closets_col=synthetic_palace.closets,
            )
        if kind == "convos":
            return convo_miner.mine_convos(
                str(source_dir), str(synthetic_palace.root), wing="project"
            )
        return diary_ingest.ingest_diaries(
            source_dir, synthetic_palace.root, wing="project", force=True
        )

    ingest()
    before = synthetic_palace.drawers.get()
    assert all(
        revision_completed(synthetic_palace.root, m, record_id=rid)
        for rid, m in zip(before.ids, before.metadatas)
    )
    os.utime(source, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns + 1000000000))

    def forbidden(**kwargs):
        raise OSError("retry must never overwrite an already completed revision")

    original_upsert = synthetic_palace.drawers.upsert
    before_by_id = dict(zip(before.ids, before.documents))

    def completed_metadata_only(**kwargs):
        assert all(meta.get("ingest_complete") is True for meta in kwargs["metadatas"])
        assert all(
            before_by_id[rid] == text for rid, text in zip(kwargs["ids"], kwargs["documents"])
        )
        assert kwargs.get("embeddings") is not None
        return original_upsert(**kwargs)

    monkeypatch.setattr(synthetic_palace.drawers, "upsert", completed_metadata_only)
    monkeypatch.setattr(synthetic_palace.closets, "upsert", forbidden)
    ingest()
    after = synthetic_palace.drawers.get()
    assert dict(zip(after.ids, after.documents)) == before_by_id
    assert all(
        revision_completed(synthetic_palace.root, m, record_id=rid)
        for rid, m in zip(after.ids, after.metadatas)
    )


def test_failed_signature_refresh_preserves_published_visibility(
    synthetic_palace, tmp_path, monkeypatch
):
    source = tmp_path / "notes.md"
    source.write_text(
        "An unchanged exact source remains available after failed bookkeeping.\n" * 20
    )

    def ingest():
        miner.process_file(
            source,
            tmp_path,
            synthetic_palace.drawers,
            "project",
            [],
            "test",
            False,
            closets_col=synthetic_palace.closets,
        )

    ingest()
    original = synthetic_palace.drawers.get()
    os.utime(source, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns + 1000000000))

    def fail(**kwargs):
        raise OSError("metadata update interrupted")

    monkeypatch.setattr(synthetic_palace.drawers, "update", fail)
    with pytest.raises(OSError):
        ingest()
    after = synthetic_palace.drawers.get()
    assert dict(zip(after.ids, after.documents)) == dict(zip(original.ids, original.documents))
    assert all(
        revision_completed(synthetic_palace.root, m, record_id=rid)
        for rid, m in zip(after.ids, after.metadatas)
    )
