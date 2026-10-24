import json

import pytest

from cognitive_castle.fast_memory import MemoryStore
from cognitive_castle import memory_ingest as ingest


def record(text, role="user", **extra):
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": role,
            "content": [{"type": "input_text", "text": text}],
            **extra,
        },
    }


def line(value):
    return json.dumps(value, ensure_ascii=False).encode() + b"\n"


def test_extract_exact_and_exclusions():
    text = "  hé\n\t🙂  "
    assert ingest.extract_messages(record(text), "codex")[0]["text"] == text
    assert ingest.extract_messages(record(text, "assistant", channel="analysis"), "codex") == []
    assert (
        ingest.extract_messages(
            {"type": "event_msg", "payload": {"type": "user_message", "message": text}}, "codex"
        )
        == []
    )
    blocks = ingest.extract_messages(
        {
            "type": "human",
            "message": {
                "content": [
                    {"type": "tool_result", "content": "secret"},
                    {"type": "text", "text": text},
                ]
            },
        },
        "claude",
    )
    assert len(blocks) == 1 and blocks[0]["role"] == "human" and blocks[0]["block"] == 1


def test_append_tail_and_dedup(tmp_path):
    path = tmp_path / "session.jsonl"
    path.write_bytes(line(record("first apple")) + line(record("second pear"))[:-1])
    store = MemoryStore(tmp_path / "memory")
    first = ingest.ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    assert first["coverage"] == "pending_tail"
    assert store.status()["indexed_chunks"] == 1
    with path.open("ab") as out:
        out.write(b"\n")
    ingest.ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    ingest.ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    assert store.status()["indexed_chunks"] == 2


def test_replacement_retains_history_and_paths_refused(tmp_path):
    path = tmp_path / "session"
    path.write_bytes(line(record("oldword")))
    store = MemoryStore(tmp_path / "memory")
    ingest.ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    path.unlink()
    path.write_bytes(line(record("newword")))
    ingest.ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    assert store.status()["indexed_chunks"] == 2
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        ingest.ingest_slice(store, link, allowed_root=tmp_path, format="codex")
    with pytest.raises(ValueError):
        ingest.ingest_slice(store, path, allowed_root=tmp_path / "other", format="codex")


def test_failed_piece_retry_and_large_text(tmp_path, monkeypatch):
    path = tmp_path / "session"
    text = "🙂" * 20000
    path.write_bytes(line(record(text)))
    store = MemoryStore(tmp_path / "memory")
    original = store.remember
    calls = []

    def fail_second(*args, **kwargs):
        calls.append(args[0])
        return {"status": "busy"} if len(calls) == 2 else original(*args, **kwargs)

    monkeypatch.setattr(store, "remember", fail_second)
    assert (
        ingest.ingest_slice(store, path, allowed_root=tmp_path, format="codex")["status"] == "busy"
    )
    receipts = []

    def capture(*args, **kwargs):
        receipt = original(*args, **kwargs)
        receipts.append(receipt)
        return receipt

    monkeypatch.setattr(store, "remember", capture)
    result = ingest.ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    assert result["status"] == "ok"
    assert store.status()["indexed_chunks"] == 10
    restored = "".join(
        source["text"]
        for receipt in receipts
        for source in store.read_sources(receipt["ids"])["sources"]
    )
    assert restored == text


def test_oversized_record_is_gap_without_json_decode(tmp_path, monkeypatch):
    path = tmp_path / "session"
    path.write_bytes(b"x" * (ingest.MAX_RECORD_BYTES + 10) + b"\n" + line(record("aftergap")))
    store = MemoryStore(tmp_path / "memory")
    decode = json.loads

    def bounded_decode(value, *args, **kwargs):
        assert len(value) <= ingest.MAX_RECORD_BYTES
        assert not isinstance(value, bytes) or not value.startswith(b"x")
        return decode(value, *args, **kwargs)

    monkeypatch.setattr(ingest.json, "loads", bounded_decode)
    result = ingest.ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    assert result["gaps"] >= 1
    assert store.recall("aftergap")["sources"]
    assert result["coverage"] == "partial"


def test_checkpoint_failure_visible(tmp_path, monkeypatch):
    path = tmp_path / "session"
    path.write_bytes(line(record("apple")))
    store = MemoryStore(tmp_path / "memory")

    def fail(*args):
        raise OSError("storage unavailable")

    monkeypatch.setattr(store, "save_checkpoint", fail)
    with pytest.raises(OSError):
        ingest.ingest_slice(store, path, allowed_root=tmp_path, format="codex")


def test_claude_internal_channels_excluded():
    assert (
        ingest.extract_messages(
            {"type": "assistant", "message": {"channel": "analysis", "content": "hidden"}}, "claude"
        )
        == []
    )


def test_segmented_oversize_and_truncation(tmp_path, monkeypatch):
    path = tmp_path / "session"
    path.write_bytes(b"x" * (ingest.MAX_SLICE_BYTES + 100) + b"\n" + line(record("after")))
    store = MemoryStore(tmp_path / "memory")
    first = ingest.ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    assert first["offset"] <= ingest.MAX_SLICE_BYTES and first["gaps"] == 1
    second = ingest.ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    assert second["gaps"] == 1 and store.recall("after")["sources"]
    path.write_bytes(line(record("short")))
    third = ingest.ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    assert third["generation"] == 1
    assert store.recall("after")["sources"]


def test_load_checkpoint_failure_propagates(tmp_path, monkeypatch):
    path = tmp_path / "session"
    path.write_bytes(line(record("apple")))
    store = MemoryStore(tmp_path / "memory")

    def fail(*args):
        raise OSError("unsafe store")

    monkeypatch.setattr(store, "load_checkpoint", fail)
    with pytest.raises(OSError):
        ingest.ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    assert not store.directory.exists()
