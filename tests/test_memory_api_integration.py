"""Synthetic trusted host integration; no native archive or models."""

import json
import os
import sys
import pytest
from cognitive_castle.brain_api import BrainAPI


requires_macos_runtime = pytest.mark.skipif(
    sys.platform != "darwin", reason="Supervised memory runtime requires macOS"
)
requires_posix_private_storage = pytest.mark.skipif(
    os.name != "posix", reason="Private policy and registry storage requires POSIX"
)


def admitted(tmp_path, monkeypatch, host="codex"):
    monkeypatch.setenv("CASTLE_BRAIN_HOST", host)
    api = BrainAPI(tmp_path)
    api.policy_path.parent.mkdir(parents=True, mode=0o700)
    api.policy_path.write_text('{"allow_local_sources":true}')
    api.policy_path.chmod(0o600)
    return api


def test_launch_host_validated_before_mutation(tmp_path, monkeypatch):
    monkeypatch.setenv("CASTLE_BRAIN_HOST", "../escape")
    with pytest.raises(ValueError):
        BrainAPI(tmp_path)
    assert not list(tmp_path.iterdir())


def test_host_policy_isolation(tmp_path, monkeypatch):
    api = admitted(tmp_path, monkeypatch)
    assert api.policy_path == tmp_path / ".brain/hosts/codex/policy.json"
    monkeypatch.setenv("CASTLE_BRAIN_HOST", "claude")
    other = BrainAPI(tmp_path)
    assert not other.policy()["allow_local_sources"]
    assert (
        other.call("castle_memory_status", {"protocol_version": 1})["status"] == "exposure_blocked"
    )
    assert not (tmp_path / ".memory").exists()


@requires_macos_runtime
def test_exact_remember_recall_page_restart(tmp_path, monkeypatch):
    api = admitted(tmp_path, monkeypatch)
    text = "synthetic kiwi consent 🥝\n" * 15
    receipt = api.call(
        "castle_memory_remember", dict(protocol_version=1, request_id="r1", text=text)
    )
    assert receipt["status"] == "ok", receipt
    api = BrainAPI(tmp_path)
    result = api.call("castle_brain_recall", {"query": "kiwi"})
    assert result["status"] == "ok", result
    assert len(json.dumps(result, ensure_ascii=False).encode()) <= 8192
    source = result["sources"][0]
    page = api.call(
        "castle_memory_read",
        dict(
            protocol_version=1,
            source_id=source["id"],
            offset=0,
            limit=2048,
            expected_hash=source["hash"],
        ),
    )
    assert page["text"] == text
    api.policy_path.write_text('{"allow_local_sources":false}')
    assert (
        api.call(
            "castle_memory_read",
            dict(protocol_version=1, source_id=source["id"], expected_hash=source["hash"]),
        )["status"]
        == "exposure_blocked"
    )


def test_tools_cannot_select_host(tmp_path, monkeypatch):
    api = admitted(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="Unknown parameter"):
        api.call("castle_memory_status", {"protocol_version": 1, "host": "claude"})


@requires_macos_runtime
def test_sue_binding_host_restart_and_revocation(tmp_path, monkeypatch):
    api = admitted(tmp_path, monkeypatch)
    receipt = api.call(
        "castle_memory_remember",
        dict(protocol_version=1, request_id="remember", text="Keep the exact consent record."),
    )
    assert receipt["status"] == "ok", receipt
    args = dict(
        protocol_version=1,
        request_id="begin",
        problem="Require consent.",
        interpretation="Consent is required.",
        sources=[],
        archive_ids=receipt["ids"],
        obligations=[
            dict(id="consent", text="Require consent.", source_id="problem", start=0, end=16)
        ],
    )
    begun = api.call("castle_problem_begin", args)
    assert begun["status"] == "ok", begun
    assert (
        BrainAPI(tmp_path).call("castle_problem_begin", args)["session_id"] == begun["session_id"]
    )
    api.policy_path.write_text('{"allow_local_sources":false}')
    assert BrainAPI(tmp_path).call("castle_problem_begin", args)["status"] != "ok"
    monkeypatch.setenv("CASTLE_BRAIN_HOST", "claude")
    assert (
        BrainAPI(tmp_path).call(
            "castle_problem_status", dict(protocol_version=1, session_id=begun["session_id"])
        )["status"]
        != "ok"
    )


@requires_macos_runtime
def test_wire_control_unicode_bound(tmp_path, monkeypatch):
    api = admitted(tmp_path, monkeypatch)
    for i in range(8):
        api.call(
            "castle_memory_remember",
            dict(protocol_version=1, request_id=str(i), text="kiwi " + ("\x00🥝" * 800) + str(i)),
        )
    result = api.call("castle_brain_recall", {"query": "kiwi", "limit": 8})
    assert result["status"] == "ok", result
    assert len(json.dumps(result, ensure_ascii=False).encode()) <= 8192
    for source in result["sources"]:
        assert source["preview_end_offset"] == len(source["preview"])


@requires_posix_private_storage
def test_operator_registry_private_bounded_and_symlink(tmp_path):
    from cognitive_castle.brain_api import _root_registry

    root = tmp_path / "original"
    root.mkdir()
    roots = _root_registry(tmp_path, ("codex", str(root), "codex"))
    assert roots["codex"]["path"] == str(root)
    assert (tmp_path / ".memory/roots.json").stat().st_mode & 0o777 == 0o600
    assert _root_registry(tmp_path) == roots
    with pytest.raises(ValueError):
        _root_registry(tmp_path, ("../bad", str(root), "codex"))
    link = tmp_path / "link"
    link.symlink_to(root)
    with pytest.raises(ValueError):
        _root_registry(tmp_path, ("linked", str(link), "codex"))


@requires_posix_private_storage
def test_operator_ingest_rejects_escape_before_worker(tmp_path, monkeypatch, capsys):
    from argparse import Namespace
    from cognitive_castle.brain_api import _root_registry, cmd_memory
    from cognitive_castle import memory_runtime

    root = tmp_path / "original"
    root.mkdir()
    _root_registry(tmp_path, ("codex", str(root), "codex"))
    monkeypatch.setattr(
        memory_runtime, "run_memory", lambda *a: pytest.fail("worker called for escaped path")
    )
    with pytest.raises(SystemExit):
        cmd_memory(
            Namespace(
                palace=str(tmp_path),
                memory_action="ingest",
                root="codex",
                path=str(root / ".." / "escape.jsonl"),
            )
        )
    assert "invalid_request" in capsys.readouterr().out


def test_memory_transport_registry_strict_schema_and_cli_alias():
    import argparse
    from cognitive_castle.brain_api import configure_memory_parser, tool_registry

    registry = tool_registry(lambda: None)
    for name in ("castle_memory_remember", "castle_memory_read", "castle_memory_status"):
        assert registry[name]["strict_arguments"] is True
        assert registry[name]["input_schema"]["additionalProperties"] is False
        assert "protocol_version" in registry[name]["input_schema"]["required"]
        assert "host" not in registry[name]["input_schema"]["properties"]
    parser = argparse.ArgumentParser()
    configure_memory_parser(parser.add_subparsers())
    parsed = parser.parse_args(["memory", "recall", "--input", "query.json"])
    assert parsed.memory_action == "recall"


@requires_macos_runtime
def test_policy_revocation_during_runtime_read_suppresses_text(tmp_path, monkeypatch):
    from cognitive_castle import memory_runtime

    api = admitted(tmp_path, monkeypatch)
    original = memory_runtime.run_memory
    api.call(
        "castle_memory_remember", dict(protocol_version=1, request_id="r", text="kiwi private text")
    )

    def revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        api.policy_path.write_text('{"allow_local_sources":false}')
        return result

    monkeypatch.setattr(memory_runtime, "run_memory", revoke)
    result = api.call("castle_brain_recall", {"query": "kiwi"})
    assert result["status"] == "exposure_blocked", result
    assert "kiwi" not in json.dumps(result)


@requires_macos_runtime
def test_memory_mcp_real_transport(tmp_path, monkeypatch):
    from cognitive_castle import mcp_server
    from cognitive_castle.brain_api import tool_registry
    from cognitive_castle.bounded_json import encode_response

    api = admitted(tmp_path, monkeypatch)
    monkeypatch.setattr(mcp_server, "TOOLS", tool_registry(lambda: api))

    def call(name, arguments):
        return mcp_server.handle_request(
            dict(
                jsonrpc="2.0",
                id=1,
                method="tools/call",
                params=dict(name=name, arguments=arguments),
            )
        )

    invalid = call(
        "castle_memory_remember",
        dict(protocol_version=1, request_id="mcp", text="kiwi", host="other"),
    )
    assert invalid["error"]["code"] == -32602
    result = call(
        "castle_memory_remember", dict(protocol_version=1, request_id="mcp", text="kiwi exact 🥝")
    )
    assert json.loads(result["result"]["content"][0]["text"])["status"] == "ok", result
    recall = call("castle_brain_recall", dict(query="kiwi"))
    assert len(encode_response(recall)) <= 32768
    assert (
        json.loads(recall["result"]["content"][0]["text"])["sources"][0]["preview"]
        == "kiwi exact 🥝"
    )


@pytest.mark.parametrize("configured", [True, False])
def test_capabilities_select_reader_without_storage(tmp_path, monkeypatch, configured):
    from cognitive_castle import brain_sources

    if configured:
        monkeypatch.setenv("CASTLE_BRAIN_HOST", "codex")
        monkeypatch.setattr(
            brain_sources, "capabilities", lambda: pytest.fail("native discovery called")
        )
    else:
        monkeypatch.delenv("CASTLE_BRAIN_HOST", raising=False)
        monkeypatch.setattr(brain_sources, "capabilities", lambda: {"reader": "legacy-sentinel"})
    result = BrainAPI(tmp_path).call("castle_brain_capabilities", {})
    reader = result["source_reader"]
    if configured:
        assert reader["storage_format"] == "sqlite-fts5-utf8-v1"
        assert reader["coverage"] == "indexed_only"
        assert reader["model_required"] is False
        assert reader["platform"] == "darwin"
        assert reader["limits"]["recall_deadline_seconds"] == 2
        assert reader["limits"]["worker_rss_tripwire_bytes"] == 128 * 1024**2
    else:
        assert reader == {"reader": "legacy-sentinel"}
    assert not list(tmp_path.iterdir())


@requires_posix_private_storage
def test_operator_ingest_passes_expanded_validated_path(tmp_path, monkeypatch, capsys):
    from argparse import Namespace
    from cognitive_castle import memory_runtime
    from cognitive_castle.brain_api import _root_registry, cmd_memory

    root = tmp_path / "original"
    root.mkdir()
    source = root / "synthetic.jsonl"
    source.write_text("{}\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    _root_registry(tmp_path, ("codex", str(root), "codex"))

    def capture(palace, operation, arguments):
        assert operation == "ingest_slice"
        assert arguments["path"] == str(source)
        return {"status": "ok"}

    monkeypatch.setattr(memory_runtime, "run_memory", capture)
    cmd_memory(
        Namespace(
            palace=str(tmp_path),
            memory_action="ingest",
            root="codex",
            path="~/original/synthetic.jsonl",
        )
    )
    assert json.loads(capsys.readouterr().out)["status"] == "ok"


@requires_posix_private_storage
def test_unsupported_runtime_fails_closed_without_sidecar(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from cognitive_castle import memory_runtime

    api = admitted(tmp_path, monkeypatch)
    monkeypatch.setattr(memory_runtime, "sys", SimpleNamespace(platform="unsupported"))
    result = api.call(
        "castle_memory_remember",
        dict(protocol_version=1, request_id="unsupported", text="exact synthetic text"),
    )
    assert result == {"status": "unavailable", "reason": "platform_supervision_unavailable"}
    assert not (tmp_path / ".memory").exists()


def test_configured_capabilities_report_unsupported_platform(tmp_path, monkeypatch):
    monkeypatch.setenv("CASTLE_BRAIN_HOST", "codex")
    monkeypatch.setattr(sys, "platform", "unsupported")
    result = BrainAPI(tmp_path).call("castle_brain_capabilities", {})
    assert result["source_reader"]["status"] == "unavailable"
    assert result["source_reader"]["reason"] == "platform_supervision_unavailable"
    assert result["source_reader"]["coverage"] == "indexed_only"
    assert not list(tmp_path.iterdir())


@requires_posix_private_storage
def test_status_observation_pages_through_real_mcp_envelope(tmp_path, monkeypatch):
    from cognitive_castle import mcp_server, memory_runtime
    from cognitive_castle.brain_api import tool_registry
    from cognitive_castle.bounded_json import encode_response
    from cognitive_castle.fast_memory import MemoryStore

    api = admitted(tmp_path, monkeypatch)
    store = MemoryStore(tmp_path / ".memory")
    # Bypass platform supervision only: exercise actual policy/schema/forwarding,
    # persistence and MCP serializers with synthetic metadata and no source reopen.
    monkeypatch.setattr(
        memory_runtime,
        "run_memory",
        lambda palace, operation, args: getattr(store, operation)(**args),
    )
    monkeypatch.setattr(mcp_server, "TOOLS", tool_registry(lambda: api))
    for i in range(20):
        store.save_checkpoint(
            "a" * 128,
            {"offset": i},
            observations=[
                {
                    "generation": 2**63 - 1,
                    "reason": "failed",
                    "start": i,
                    "end": 2**63 - 1,
                    "record_start": 0,
                    "hash_scope": "record",
                    "sha256": "f" * 64,
                    "outcome": "unknown_or_interrupted",
                }
            ],
        )
    seen, after = [], 0
    while True:
        response = mcp_server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": "synthetic-status-request-1234567890",
                "method": "tools/call",
                "params": {
                    "name": "castle_memory_status",
                    "arguments": {"protocol_version": 1, "after": after, "limit": 16},
                },
            }
        )
        assert len(encode_response(response)) <= 32768
        result = json.loads(response["result"]["content"][0]["text"])
        assert result["status"] == "ok", result
        assert result["observation_currentness"] == "recorded_only_source_not_reopened"
        seen.extend(result["observations"])
        if result["next_after"] is None:
            break
        after = result["next_after"]
    assert len(seen) == len({o["sequence"] for o in seen}) == 20


@requires_macos_runtime
def test_context_actual_transport_budget(tmp_path, monkeypatch):
    from cognitive_castle.fast_memory import MemoryStore
    from cognitive_castle.memory_capture import queue_source, capture_one

    monkeypatch.setenv("CASTLE_BRAIN_HOST", "codex")
    path = tmp_path / "session.jsonl"
    rows = [
        {"type": "assistant" if i % 2 else "user", "message": {"content": "🙂" * 512}}
        for i in range(8)
    ]
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    store = MemoryStore(tmp_path / ".memory")
    key = queue_source(store, path, allowed_root=tmp_path, format="claude", workspace="/project-a")[
        "source_key"
    ]
    while capture_one(store, key).get("pending_bytes"):
        pass
    api = BrainAPI(tmp_path)
    api.policy_path.parent.mkdir(parents=True, mode=0o700)
    api.policy_path.write_text('{"allow_local_sources":true}')
    api.policy_path.chmod(0o600)
    packet = api.call(
        "castle_memory_context", dict(protocol_version=1, workspace="/project-a", limit=8)
    )
    compact = len(json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode())
    normal = len(json.dumps(packet, ensure_ascii=False).encode())
    assert packet["status"] == "ok", packet
    assert compact <= 8192
    assert normal <= 8192
    from cognitive_castle.brain_api import _root_registry
    from cognitive_castle.memory_coordinator import configure_capture
    from cognitive_castle.codex_hooks import handle_hook

    _root_registry(tmp_path, ("source", str(tmp_path), "claude"))
    configure_capture(tmp_path, enabled=True)
    monkeypatch.setattr(
        "cognitive_castle.config.CognitiveCastleConfig",
        lambda: type("Cfg", (), {"palace_path": str(tmp_path)})(),
    )
    hook = handle_hook("session-start", {"cwd": "/project-a"})
    assert len(hook["hookSpecificOutput"]["additionalContext"].encode()) <= 8192


@requires_macos_runtime
def test_public_recall_explicit_any_mode_crosses_supervised_boundary(tmp_path, monkeypatch):
    api = admitted(tmp_path, monkeypatch)
    for identity, text in (
        ("a", "Persistence belongs to the API."),
        ("b", "Architecture remains a proposal."),
    ):
        result = api.call(
            "castle_memory_remember", dict(protocol_version=1, request_id=identity, text=text)
        )
        assert result["status"] == "ok"
    assert api.call("castle_brain_recall", {"query": "persistence architecture"})["sources"] == []
    result = api.call("castle_brain_recall", {"query": "persistence architecture", "match": "any"})
    assert result["status"] == "ok", result
    assert result["matching"] == "any" and len(result["sources"]) == 2
    assert len(json.dumps(result, ensure_ascii=False).encode()) <= 8192
    with pytest.raises(ValueError):
        api.call("castle_brain_recall", {"query": "persistence", "match": "unsafe"})
