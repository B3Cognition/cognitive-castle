"""Source accounting must describe what is missing as well as what was indexed."""

import json
import os

import pytest

from cognitive_castle.fast_memory import MemoryStore
from cognitive_castle.memory_ingest import ingest_slice

pytestmark = pytest.mark.skipif(os.name != "posix", reason="private local storage requires POSIX")


def line(value):
    return json.dumps(value, ensure_ascii=False).encode() + b"\n"


def message(text, *, blocks=None):
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": blocks if blocks is not None else [{"type": "input_text", "text": text}],
        },
    }


def test_ingest_accounts_for_mixed_text_and_omitted_evidence(tmp_path):
    path = tmp_path / "session.jsonl"
    rows = [
        {"type": "session_meta", "payload": {"cwd": "/project/sixth-sense"}},
        message(
            "current decision",
            blocks=[
                {"type": "input_text", "text": "current decision"},
                {"type": "input_image", "image_url": "private"},
            ],
        ),
        {
            "type": "response_item",
            "payload": {"type": "function_call_output", "output": "build passed"},
        },
        {"type": "response_item", "payload": {"type": "reasoning", "text": "internal"}},
    ]
    path.write_bytes(b"".join(map(line, rows)))
    store = MemoryStore(tmp_path / "memory")
    result = ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    assert "accounting" in result, "current coverage must expose omitted evidence"
    counts = result["accounting"]
    assert counts["processed_records"] == 4
    assert counts["indexed_records"] == 1
    assert counts["text_blocks"] == 1
    assert counts["attachment_blocks"] == 1
    assert counts["tool_records"] == 1
    assert counts["internal_records"] == 1
    assert counts["metadata_records"] == 1
    assert result["observed_size"] == path.stat().st_size
    assert result["pending_bytes"] == 0
    assert result["text_coverage"] == "gaps"
    again = ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    assert again["accounting"] == counts, "replay must not increment accounting"


def test_completed_tail_resolves_current_pending_without_erasing_history(tmp_path):
    path = tmp_path / "session.jsonl"
    path.write_bytes(line(message("one")) + line(message("two"))[:-1])
    store = MemoryStore(tmp_path / "memory")
    first = ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    assert first.get("pending_bytes", 0) > 0
    with path.open("ab") as stream:
        stream.write(b"\n")
    complete = ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    assert complete["pending_bytes"] == 0
    assert complete["text_coverage"] == "complete_supported_text"
    assert complete["accounting"]["processed_records"] == 2
    assert any(o["reason"] == "pending_tail" for o in store.status()["observations"])


def test_rotation_resets_current_counts_but_preserves_original_text(tmp_path):
    path = tmp_path / "session.jsonl"
    path.write_bytes(line(message("before")) + line(message("also before")))
    store = MemoryStore(tmp_path / "memory")
    first = ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    assert first.get("accounting", {}).get("indexed_records") == 2
    path.unlink()
    path.write_bytes(line(message("after")))
    second = ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    assert second["generation"] == first["generation"] + 1
    assert second["accounting"]["indexed_records"] == 1
    assert store.status()["indexed_chunks"] == 3


def test_unrecognized_blocks_remain_visible_even_with_supported_text(tmp_path):
    path = tmp_path / "session.jsonl"
    path.write_bytes(
        line(
            message(
                "",
                blocks=[
                    {"type": "input_text", "text": "exact"},
                    {"type": "future_payload", "data": "unknown"},
                ],
            )
        )
    )
    result = ingest_slice(
        MemoryStore(tmp_path / "memory"), path, allowed_root=tmp_path, format="codex"
    )
    assert result.get("accounting", {}).get("unsupported_blocks") == 1
    assert result["text_coverage"] == "gaps"


def test_unknown_event_is_not_disguised_as_metadata(tmp_path):
    path = tmp_path / "session.jsonl"
    path.write_bytes(
        line({"type": "event_msg", "payload": {"type": "future_evidence", "text": "important"}})
    )
    result = ingest_slice(
        MemoryStore(tmp_path / "memory"), path, allowed_root=tmp_path, format="codex"
    )
    assert result["accounting"]["unsupported_records"] == 1
    assert result["text_coverage"] == "gaps"


def test_prior_checkpoint_does_not_claim_historical_accounting(tmp_path):
    path = tmp_path / "session.jsonl"
    path.write_bytes(line(message("old")))
    store = MemoryStore(tmp_path / "memory")
    old = ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    checkpoint = store.load_checkpoint(old["source_key"])
    checkpoint.pop("accounting", None)
    checkpoint.pop("accounting_start", None)
    store.save_checkpoint(old["source_key"], checkpoint)
    result = ingest_slice(store, path, allowed_root=tmp_path, format="codex")
    assert result.get("accounting_start") == path.stat().st_size
    assert result["text_coverage"] == "accounting_incomplete"


def capture_api():
    from cognitive_castle import memory_capture

    assert hasattr(memory_capture, "queue_source"), "capture requires durable source registration"
    return memory_capture


def test_queued_source_is_visible_before_capture_and_survives_restart(tmp_path):
    api = capture_api()
    path = tmp_path / "session.jsonl"
    path.write_bytes(line(message("Sixth Sense uses an API-owned store")))
    store = MemoryStore(tmp_path / "memory")
    receipt = api.queue_source(
        store, path, allowed_root=tmp_path, format="codex", workspace="/sixth"
    )
    assert receipt["status"] == "ok"
    before = api.coverage(store)
    assert before["observed_sources"] == 1
    assert before["pending_sources"] == 1
    assert before["pending_bytes"] == path.stat().st_size
    result = api.capture_one(MemoryStore(tmp_path / "memory"), receipt["source_key"])
    assert result["status"] == "ok"
    after = api.coverage(store)
    assert after["pending_sources"] == 0
    assert after["processed_bytes"] == path.stat().st_size
    assert after["indexed_text_bytes"] == len("Sixth Sense uses an API-owned store")
    assert after["coverage"] == "complete_supported_text_at_last_observation"
    assert api.source_page(store)["sources"][0]["workspace"] == "/sixth"


def test_queue_append_retries_and_preserves_missing_source_visibility(tmp_path):
    api = capture_api()
    path = tmp_path / "session.jsonl"
    path.write_bytes(line(message("first")))
    store = MemoryStore(tmp_path / "memory")
    key = api.queue_source(store, path, allowed_root=tmp_path, format="codex")["source_key"]
    api.capture_one(store, key)
    with path.open("ab") as stream:
        stream.write(line(message("second")))
    api.queue_source(store, path, allowed_root=tmp_path, format="codex")
    assert api.coverage(store)["pending_sources"] == 1
    api.capture_one(store, key)
    assert store.status()["indexed_chunks"] == 2
    path.unlink()
    failed = api.capture_one(store, key)
    assert failed["status"] == "unavailable"
    assert api.coverage(store)["failed_sources"] == 1
    assert api.coverage(store)["coverage"] != "complete_supported_text_at_last_observation"


def test_current_coverage_exposes_omissions_and_not_old_pending_observations(tmp_path):
    api = capture_api()
    path = tmp_path / "session.jsonl"
    path.write_bytes(line(message("one"))[:-1])
    store = MemoryStore(tmp_path / "memory")
    key = api.queue_source(store, path, allowed_root=tmp_path, format="codex")["source_key"]
    api.capture_one(store, key)
    assert api.coverage(store)["pending_sources"] == 1
    with path.open("ab") as stream:
        stream.write(
            b"\n"
            + line(
                {
                    "type": "response_item",
                    "payload": {"type": "function_call_output", "output": "test passed"},
                }
            )
        )
    api.queue_source(store, path, allowed_root=tmp_path, format="codex")
    api.capture_one(store, key)
    current = api.coverage(store)
    assert current["pending_sources"] == 0
    assert current["omitted"]["tool_records"] == 1
    assert current["coverage"] == "gaps"
    assert any(o["reason"] == "pending_tail" for o in store.status()["observations"])


def test_source_queue_rejects_symlinks_and_escaping_roots(tmp_path):
    api = capture_api()
    path = tmp_path / "session.jsonl"
    path.write_bytes(line(message("one")))
    store = MemoryStore(tmp_path / "memory")
    link = tmp_path / "linked"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        api.queue_source(store, link, allowed_root=tmp_path, format="codex")
    with pytest.raises(ValueError):
        api.queue_source(store, path, allowed_root=tmp_path / "elsewhere", format="codex")
