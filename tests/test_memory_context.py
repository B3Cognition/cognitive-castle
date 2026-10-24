"""Restore exact workspace evidence and explicitly attributed work state."""

import json
import os
import sys

import pytest

from cognitive_castle.fast_memory import MemoryStore
from cognitive_castle.memory_capture import queue_source, capture_one

pytestmark = pytest.mark.skipif(os.name != "posix", reason="private storage requires POSIX")


def seed(tmp_path, workspace, texts, name="conversation"):
    path = tmp_path / (name + ".jsonl")
    rows = [
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": role,
                "content": [
                    {"type": "input_text" if role == "user" else "output_text", "text": text}
                ],
            },
        }
        for role, text in texts
    ]
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    store = MemoryStore(tmp_path / "memory")
    key = queue_source(store, path, allowed_root=tmp_path, format="codex", workspace=workspace)[
        "source_key"
    ]
    for _ in range(20):
        result = capture_one(store, key)
        if not result.get("pending_bytes"):
            break
    return store


def context_api():
    from cognitive_castle import memory_context

    assert hasattr(memory_context, "restore_context"), "startup needs a bounded evidence packet"
    return memory_context


def test_cold_start_restores_same_workspace_exact_words_with_roles(tmp_path):
    api = context_api()
    source = "Sixth Sense: API owns persistence; preserve the original event."
    store = seed(
        tmp_path, "/sixth", [("user", source), ("assistant", "Contract verification passed.")]
    )
    seed(tmp_path, "/other", [("user", "Different workspace secret")], "other")
    packet = api.restore_context(MemoryStore(store.directory), "/sixth", namespace="codex")
    assert packet["status"] == "ok"
    assert any(item["text"] == source and item["role"] == "user" for item in packet["sources"])
    assert "Different workspace secret" not in json.dumps(packet)
    assert all(
        item["source_id"].startswith("memory:") and len(item["expected_hash"]) == 64
        for item in packet["sources"]
    )
    assert packet["authority"] == "historical_evidence_not_current_instructions"


def test_later_correction_preserves_both_evidence_versions(tmp_path):
    api = context_api()
    store = seed(
        tmp_path,
        "/sixth",
        [
            ("user", "Initial proposal: PostgreSQL."),
            ("user", "Revision four: API-owned MySQL supersedes that proposal."),
        ],
    )
    packet = api.restore_context(store, "/sixth", namespace="codex")
    assert [s["text"] for s in packet["sources"]] == [
        "Revision four: API-owned MySQL supersedes that proposal.",
        "Initial proposal: PostgreSQL.",
    ]
    assert packet["work_state"] is None, "a correction is not an inferred completed task"


def test_source_backed_work_state_survives_restart_and_completion(tmp_path):
    api = context_api()
    store = seed(tmp_path, "/sixth", [("user", "Verify revision four API contract.")])
    source = api.restore_context(store, "/sixth", namespace="codex")["sources"][0]
    result = api.update_context(
        store,
        "/sixth",
        namespace="codex",
        request_id="work-1",
        expected_revision=0,
        status="active",
        source_ids=[source["source_id"]],
    )
    assert result["status"] == "ok" and result["revision"] == 1
    assert (
        api.restore_context(MemoryStore(store.directory), "/sixth", namespace="codex")[
            "work_state"
        ]["status"]
        == "active"
    )
    complete = api.update_context(
        store,
        "/sixth",
        namespace="codex",
        request_id="work-2",
        expected_revision=1,
        status="completed",
        source_ids=[source["source_id"]],
    )
    assert complete["status"] == "ok"
    packet = api.restore_context(store, "/sixth", namespace="codex")
    assert packet["work_state"]["status"] == "completed"
    assert packet["work_state"]["attribution"] == "host_recorded_not_independently_verified"
    assert api.restore_context(store, "/sixth", namespace="claude")["work_state"] is None


def test_work_state_retries_and_revision_conflicts(tmp_path):
    api = context_api()
    store = seed(tmp_path, "/sixth", [("user", "Verify contract")])
    sid = api.restore_context(store, "/sixth", namespace="codex")["sources"][0]["source_id"]
    kwargs = dict(
        namespace="codex", request_id="r1", expected_revision=0, status="active", source_ids=[sid]
    )
    first = api.update_context(store, "/sixth", **kwargs)
    assert api.update_context(store, "/sixth", **kwargs) == first
    assert (
        api.update_context(store, "/sixth", **(kwargs | {"status": "cancelled"}))["status"]
        == "conflict"
    )
    assert (
        api.update_context(store, "/sixth", **(kwargs | {"request_id": "r2"}))["status"] == "stale"
    )


def test_context_and_pinned_work_obey_wire_budget(tmp_path):
    api = context_api()
    store = seed(tmp_path, "/sixth", [("user", "🙂" * 2500) for _ in range(12)])
    packet = api.restore_context(store, "/sixth", namespace="codex")
    assert 0 < len(packet["sources"]) <= 8
    assert len(json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode()) <= 8192
    assert any(item["truncated"] for item in packet["sources"])


def test_work_references_cannot_cross_workspace(tmp_path):
    api = context_api()
    store = seed(tmp_path, "/other", [("user", "Other project")])
    sid = api.restore_context(store, "/other", namespace="codex")["sources"][0]["source_id"]
    result = api.update_context(
        store,
        "/sixth",
        namespace="codex",
        request_id="bad",
        expected_revision=0,
        status="active",
        source_ids=[sid],
    )
    assert result["status"] == "scope_mismatch"


def test_empty_workspace_reports_no_context_not_complete_history(tmp_path):
    api = context_api()
    packet = api.restore_context(MemoryStore(tmp_path / "missing"), "/sixth", namespace="codex")
    assert packet["status"] == "ok"
    assert packet["sources"] == []
    assert packet["coverage"]["discovery"] == "not_established"


def test_exact_read_detects_modified_persisted_source(tmp_path):
    store = seed(tmp_path, "/sixth", [("user", "Original API contract")])
    source_id = store.recall("Original")["sources"][0]["id"]
    with store._connect(True) as conn:
        conn.execute("UPDATE chunks SET text='Tampered API contract' WHERE id=?", (source_id,))
    assert store.read_sources([source_id])["status"] == "corrupt"


@pytest.mark.parametrize("bad_state", ["[]", '{"sources":null}', '{"sources":[{}]}'])
def test_malformed_saved_work_state_returns_corruption(tmp_path, bad_state):
    api = context_api()
    store = seed(tmp_path, "/sixth", [("user", "Original API contract")])
    with store._connect(True) as conn:
        api._ensure(conn)
        conn.execute("INSERT INTO work_context VALUES ('codex','/sixth',1,?)", (bad_state,))
    assert api.restore_context(store, "/sixth", namespace="codex")["status"] == "corrupt"


@pytest.mark.skipif(sys.platform != "darwin", reason="supervised memory runtime requires macOS")
def test_actual_api_context_restart_and_policy_revocation(tmp_path, monkeypatch):
    from cognitive_castle.brain_api import BrainAPI, SPECS

    assert "castle_memory_context" in SPECS, "context must cross the real host boundary"
    store = seed(tmp_path, "/sixth", [("user", "Preserve the Sixth Sense event contract.")])
    palace = tmp_path
    # seed's store deliberately uses a named directory; production uses .memory.
    store.directory.rename(palace / ".memory")
    monkeypatch.setenv("CASTLE_BRAIN_HOST", "codex")
    api = BrainAPI(palace)
    api.policy_path.parent.mkdir(parents=True, mode=0o700)
    api.policy_path.write_text('{"allow_local_sources":true}')
    api.policy_path.chmod(0o600)
    request = dict(protocol_version=1, workspace="/sixth")
    packet = api.call("castle_memory_context", request)
    assert packet["status"] == "ok", packet
    assert packet["sources"][0]["text"] == "Preserve the Sixth Sense event contract."
    changed = api.call(
        "castle_memory_context_update",
        dict(
            protocol_version=1,
            workspace="/sixth",
            request_id="active-work",
            expected_revision=0,
            status="active",
            source_ids=[packet["sources"][0]["source_id"]],
        ),
    )
    assert changed["status"] == "ok", changed
    assert (
        BrainAPI(palace).call("castle_memory_context", request)["work_state"]["status"] == "active"
    )
    api.policy_path.write_text('{"allow_local_sources":false}')
    assert api.call("castle_memory_context", request)["status"] == "exposure_blocked"


@pytest.mark.skipif(sys.platform != "darwin", reason="supervised memory runtime requires macOS")
def test_session_start_delivers_actual_context_with_legacy_capture_paused(tmp_path, monkeypatch):
    from cognitive_castle.brain_api import BrainAPI, _root_registry
    from cognitive_castle.codex_hooks import handle_hook
    from cognitive_castle.memory_coordinator import configure_capture

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    store = seed(tmp_path, "/sixth", [("user", "Resume Sixth Sense contract verification.")])
    store.directory.rename(tmp_path / ".memory")
    monkeypatch.setenv("CASTLE_BRAIN_HOST", "codex")
    monkeypatch.setattr(
        "cognitive_castle.config.CognitiveCastleConfig",
        lambda: type("Cfg", (), {"palace_path": str(tmp_path)})(),
    )
    _root_registry(tmp_path, ("codex", tmp_path, "codex"))
    configure_capture(tmp_path, enabled=True)
    api = BrainAPI(tmp_path)
    api.policy_path.parent.mkdir(parents=True, mode=0o700)
    api.policy_path.write_text('{"allow_local_sources":true}')
    api.policy_path.chmod(0o600)
    from pathlib import Path

    paused = Path.home() / ".castle/codex-capture.disabled"
    paused.parent.mkdir(parents=True, exist_ok=True)
    paused.touch()
    response = handle_hook("session-start", {"cwd": "/sixth", "session_id": "new-process"})
    context = response["hookSpecificOutput"]["additionalContext"]
    assert "Resume Sixth Sense contract verification." in context
    assert "historical_evidence_not_current_instructions" in context
    assert paused.exists()
