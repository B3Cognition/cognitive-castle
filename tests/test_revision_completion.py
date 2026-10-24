"""A completed source revision must include its required index writes."""

import json
import pytest

from cognitive_castle import miner


def test_project_publishes_drawer_and_closet_completion(synthetic_palace, tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("A precise original decision about Atlas.\n" * 30)
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
    assert synthetic_palace.closets.count() > 0
    assert all(m.get("ingest_complete") for m in synthetic_palace.closets.get().metadatas)
    manifests = list((synthetic_palace.root / ".castle/revisions").glob("*/*.json"))
    assert len(manifests) == 1
    data = json.loads(manifests[0].read_text())
    assert data["drawer_count"] == synthetic_palace.drawers.count()
    assert data["closet_count"] == synthetic_palace.closets.count()
    assert data["complete"] is True


def test_closet_failure_never_publishes_completion(synthetic_palace, tmp_path, monkeypatch):
    source = tmp_path / "notes.md"
    source.write_text("Original valid content retained forever.\n")

    def fail(**kw):
        raise OSError("index storage unavailable")

    monkeypatch.setattr(synthetic_palace.closets, "upsert", fail)
    with pytest.raises(OSError):
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
    assert not any(m.get("ingest_complete") for m in synthetic_palace.drawers.get().metadatas)
    assert not list((synthetic_palace.root / ".castle/revisions").glob("*/*.json"))
