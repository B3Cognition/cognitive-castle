"""Immutable attribution must not move old evidence when a source is requeued."""

import json
import os

import pytest

from cognitive_castle.fast_memory import MemoryStore
from cognitive_castle.memory_capture import capture_one, queue_source, source_page
from cognitive_castle.memory_context import restore_context, update_context

pytestmark = pytest.mark.skipif(os.name != "posix", reason="private storage requires POSIX")


def rows(workspace, text):
    return [
        {"type": "session_meta", "payload": {"cwd": workspace}},
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            },
        },
    ]


def write(path, records, mode="w"):
    with path.open(mode) as stream:
        stream.write("".join(json.dumps(record) + "\n" for record in records))


def queued(tmp_path, records, workspace=None):
    path = tmp_path / "source.jsonl"
    write(path, records)
    store = MemoryStore(tmp_path / "memory")
    key = queue_source(store, path, allowed_root=tmp_path, format="codex", workspace=workspace)[
        "source_key"
    ]
    assert capture_one(store, key)["status"] == "ok"
    return store, path, key


def packet(store, workspace):
    return restore_context(store, workspace, namespace="codex")


def texts(store, workspace):
    value = packet(store, workspace)
    assert value["status"] == "ok", value
    return [item["text"] for item in value["sources"]]


def pin(store, workspace):
    identity = packet(store, workspace)["sources"][0]["source_id"]
    assert (
        update_context(
            store,
            workspace,
            namespace="codex",
            request_id="pin",
            expected_revision=0,
            status="completed",
            source_ids=[identity],
        )["status"]
        == "ok"
    )
    return identity


def test_changed_host_hint_cannot_reassign_old_chunks_or_break_pins(tmp_path):
    store, path, key = queued(tmp_path, rows("/unused", "Only project A secret")[1:], "/project-a")
    original = pin(store, "/project-a")
    queue_source(store, path, allowed_root=tmp_path, format="codex", workspace="/project-b")
    assert texts(store, "/project-b") == []
    restored = packet(store, "/project-a")
    assert restored["status"] == "ok"
    assert restored["work_state"]["status"] == "completed"
    assert restored["sources"][0]["source_id"] == original
    assert capture_one(store, key)["status"] == "ok"
    assert texts(store, "/project-b") == []


def test_rotation_uses_new_metadata_without_reassigning_old_pins(tmp_path):
    store, path, key = queued(tmp_path, rows("/project-a", "Only A"))
    original = pin(store, "/project-a")
    path.unlink()
    write(path, rows("/project-b", "Only B"))
    queue_source(store, path, allowed_root=tmp_path, format="codex")
    assert capture_one(store, key)["status"] == "ok"
    assert texts(store, "/project-b") == ["Only B"]
    assert texts(store, "/project-a") == ["Only A"]
    assert packet(store, "/project-a")["sources"][0]["source_id"] == original
    with store._connect(True) as conn:
        conn.execute("DELETE FROM work_context")
    assert texts(store, "/project-a") == []


def test_transcript_metadata_wins_over_host_hint(tmp_path):
    store, _, _ = queued(tmp_path, rows("/project-b", "Metadata owns this scope"), "/project-a")
    assert texts(store, "/project-a") == []
    assert texts(store, "/project-b") == ["Metadata owns this scope"]
    observed = source_page(store)["sources"][0]
    assert observed["workspace_attribution"] == "transcript_metadata"


def test_mixed_metadata_in_one_slice_does_not_assign_new_text_to_first_workspace(tmp_path):
    store, _, _ = queued(tmp_path, rows("/project-a", "Only A") + rows("/project-b", "Only B"))
    assert texts(store, "/project-a") == ["Only A"]
    assert texts(store, "/project-b") == []
    assert source_page(store)["sources"][0]["workspace_scope"] == "conflict"


def test_later_metadata_conflict_preserves_pins_but_quarantines_new_chunks(tmp_path):
    store, path, key = queued(tmp_path, rows("/project-a", "Only A"))
    original = pin(store, "/project-a")
    write(path, rows("/project-b", "Only B"), "a")
    queue_source(store, path, allowed_root=tmp_path, format="codex")
    result = capture_one(store, key)
    assert result["workspace_conflict"] is True
    assert texts(store, "/project-a") == ["Only A"]
    assert texts(store, "/project-b") == []
    assert packet(store, "/project-a")["sources"][0]["source_id"] == original
    assert store.recall("Only B")["sources"], "unscoped text still stays exact in the archive"


def test_host_only_scope_change_does_not_label_appended_text_as_old_project(tmp_path):
    store, path, key = queued(tmp_path, rows("/unused", "Only A")[1:], "/project-a")
    pin(store, "/project-a")
    write(path, rows("/unused", "Only B")[1:], "a")
    queue_source(store, path, allowed_root=tmp_path, format="codex", workspace="/project-b")
    capture_one(store, key)
    assert texts(store, "/project-a") == ["Only A"]
    assert texts(store, "/project-b") == []
    assert source_page(store)["sources"][0]["workspace_scope"] == "conflict"


def test_existing_unmapped_chunks_are_not_assigned_from_later_hint(tmp_path):
    from cognitive_castle.memory_ingest import ingest_slice

    path = tmp_path / "legacy.jsonl"
    write(path, rows("/unused", "Previously unscoped secret")[1:])
    store = MemoryStore(tmp_path / "memory")
    assert ingest_slice(store, path, allowed_root=tmp_path, format="codex")["status"] == "ok"
    key = queue_source(store, path, allowed_root=tmp_path, format="codex", workspace="/project-b")[
        "source_key"
    ]
    capture_one(store, key)
    assert texts(store, "/project-b") == []
    assert store.recall("Previously")["sources"]


def test_rotated_source_without_metadata_does_not_inherit_old_host_hint(tmp_path):
    store, path, key = queued(tmp_path, rows("/unused", "Only A")[1:], "/project-a")
    path.unlink()
    write(path, rows("/unused", "Unknown new scope")[1:])
    queue_source(store, path, allowed_root=tmp_path, format="codex")
    capture_one(store, key)
    assert texts(store, "/project-a") == []


def test_crash_after_ingest_retries_durable_mapping_without_reassigning_scope(
    tmp_path, monkeypatch
):
    import cognitive_castle.memory_capture as capture

    path = tmp_path / "source.jsonl"
    write(path, rows("/unused", "Only A")[1:])
    store = MemoryStore(tmp_path / "memory")
    key = queue_source(store, path, allowed_root=tmp_path, format="codex", workspace="/project-a")[
        "source_key"
    ]
    ingest = capture.ingest_slice

    def interrupted(*args, **kwargs):
        result = ingest(*args, **kwargs)
        assert result["status"] == "ok"
        raise RuntimeError("simulated worker termination before mapping")

    monkeypatch.setattr(capture, "ingest_slice", interrupted)
    with pytest.raises(RuntimeError):
        capture_one(store, key)
    assert store.recall("Only A")["sources"]
    write(path, rows("/unused", "Only B")[1:], "a")
    queue_source(store, path, allowed_root=tmp_path, format="codex", workspace="/project-b")
    monkeypatch.setattr(capture, "ingest_slice", ingest)
    assert capture_one(store, key)["status"] == "ok"
    assert texts(store, "/project-a") == ["Only A"]
    assert texts(store, "/project-b") == []
    assert source_page(store)["sources"][0]["unscoped_chunks"] == 1


def test_first_claude_record_crash_after_remember_recovers_same_chunk_scope(tmp_path, monkeypatch):
    path = tmp_path / "claude.jsonl"
    write(
        path, [{"type": "user", "cwd": "/project-a", "message": {"content": "First Claude scope"}}]
    )
    store = MemoryStore(tmp_path / "memory")
    key = queue_source(store, path, allowed_root=tmp_path, format="claude")["source_key"]
    remember = store.remember

    def crash_after_remember(*args, **kwargs):
        receipt = remember(*args, **kwargs)
        assert receipt["status"] == "ok"
        raise RuntimeError("terminated before record checkpoint")

    monkeypatch.setattr(store, "remember", crash_after_remember)
    with pytest.raises(RuntimeError):
        capture_one(store, key)
    old_id = store.recall("First Claude")["sources"][0]["id"]
    assert store.load_checkpoint(key)["offset"] == 0, "record has not committed its offset"
    restarted = MemoryStore(store.directory)
    assert capture_one(restarted, key)["status"] == "ok"
    restored = packet(restarted, "/project-a")
    assert restored["status"] == "ok"
    assert restored["sources"][0]["source_id"] == old_id
    assert restored["sources"][0]["text"] == "First Claude scope"
    assert source_page(restarted)["sources"][0]["unscoped_chunks"] == 0
    with restarted._connect() as conn:
        assert conn.execute("SELECT count(*) FROM chunks").fetchone()[0] == 1
