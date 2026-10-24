"""Synthetic trusted host integration; no native archive or models."""

import json
import pytest
from cognitive_castle.brain_api import BrainAPI


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


def test_exact_remember_recall_page_restart(tmp_path, monkeypatch):
    api = admitted(tmp_path, monkeypatch)
    text = "synthetic kiwi consent 🥝\n" * 15
    receipt = api.call(
        "castle_memory_remember", dict(protocol_version=1, request_id="r1", text=text)
    )
    assert receipt["status"] == "ok"
    api = BrainAPI(tmp_path)
    result = api.call("castle_brain_recall", {"query": "kiwi"})
    assert result["status"] == "ok"
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


def test_sue_binding_host_restart_and_revocation(tmp_path, monkeypatch):
    api = admitted(tmp_path, monkeypatch)
    receipt = api.call(
        "castle_memory_remember",
        dict(protocol_version=1, request_id="remember", text="Keep the exact consent record."),
    )
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
    assert begun["status"] == "ok"
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


def test_wire_control_unicode_bound(tmp_path, monkeypatch):
    api = admitted(tmp_path, monkeypatch)
    for i in range(8):
        api.call(
            "castle_memory_remember",
            dict(protocol_version=1, request_id=str(i), text="kiwi " + ("\x00🥝" * 800) + str(i)),
        )
    result = api.call("castle_brain_recall", {"query": "kiwi", "limit": 8})
    assert result["status"] == "ok"
    assert len(json.dumps(result, ensure_ascii=False).encode()) <= 8192
    for source in result["sources"]:
        assert source["preview_end_offset"] == len(source["preview"])


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
    assert result["status"] == "exposure_blocked"
    assert "kiwi" not in json.dumps(result)


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
    assert json.loads(result["result"]["content"][0]["text"])["status"] == "ok"
    recall = call("castle_brain_recall", dict(query="kiwi"))
    assert len(encode_response(recall)) <= 32768
    assert (
        json.loads(recall["result"]["content"][0]["text"])["sources"][0]["preview"]
        == "kiwi exact 🥝"
    )
