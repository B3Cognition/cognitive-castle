import json

import pytest

from cognitive_castle.sweeper import sweep


def record(uuid, text="A preserved decision", timestamp="2026-10-23T12:00:00Z"):
    return {
        "type": "user",
        "timestamp": timestamp,
        "uuid": uuid,
        "sessionId": "session",
        "message": {"role": "user", "content": text},
    }


def test_unchanged_sweep_does_not_embed_or_change_capture(synthetic_palace, tmp_path, monkeypatch):
    path = tmp_path / "session.jsonl"
    path.write_text(json.dumps(record("one")))
    sweep(str(path), synthetic_palace.root, wing="project")
    before = synthetic_palace.drawers.get().metadatas

    def forbidden(**kw):
        pytest.fail("unchanged sweep attempted to rewrite")

    monkeypatch.setattr(synthetic_palace.drawers, "upsert", forbidden)
    result = sweep(str(path), synthetic_palace.root, wing="project")
    assert result["drawers_upserted"] == 0
    assert synthetic_palace.drawers.get().metadatas == before


def test_late_and_changed_messages_preserve_every_version(synthetic_palace, tmp_path):
    path = tmp_path / "session.jsonl"
    path.write_text(json.dumps(record("one")))
    sweep(str(path), synthetic_palace.root)
    path.write_text(
        "\n".join(
            json.dumps(r)
            for r in [
                record("one", "A corrected decision"),
                record("late", timestamp="2026-10-23T10:00:00Z"),
            ]
        )
    )
    sweep(str(path), synthetic_palace.root)
    assert set(synthetic_palace.drawers.get().documents) == {
        "USER: A preserved decision",
        "USER: A corrected decision",
        "USER: A preserved decision",
    }
    assert synthetic_palace.drawers.count() == 3
