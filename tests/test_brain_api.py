"""Actual host boundary: synthetic data, no models or user archive."""

import json
import os

import pytest

requires_private_storage = pytest.mark.skipif(
    os.name != "posix", reason="Controller privacy requires POSIX owner/mode/no-follow checks"
)


@pytest.fixture
def api(tmp_path):
    from cognitive_castle.brain_api import BrainAPI

    return BrainAPI(tmp_path / "palace")


def payload():
    return dict(
        protocol_version=1,
        request_id="b",
        problem="Require consent.",
        interpretation="Consent must be obtained.",
        sources=[],
        obligations=[
            dict(id="consent", text="Require consent.", source_id="problem", start=0, end=16)
        ],
    )


@pytest.mark.parametrize("missing", ["getuid", "O_NOFOLLOW", "O_NONBLOCK"])
def test_missing_private_file_primitives_are_advertised_and_block_access(api, monkeypatch, missing):
    from types import SimpleNamespace
    from cognitive_castle import brain_api, brain_loop, brain_sources

    unsupported_os = SimpleNamespace(
        **{name: value for name, value in vars(brain_loop.os).items() if name != missing}
    )
    monkeypatch.setattr(brain_loop, "os", unsupported_os)
    monkeypatch.setattr(brain_api, "os", unsupported_os)
    monkeypatch.setattr(
        brain_sources, "recall", lambda *a, **k: pytest.fail("unsupported native access")
    )
    capabilities = api.call("castle_brain_capabilities", {})
    assert capabilities["problem_controller"] == {
        "status": "unavailable",
        "reason": "platform_private_storage_unavailable",
    }
    assert api.call("castle_brain_recall", {"query": "consent"}) == {
        "status": "unavailable",
        "reason": "platform_private_storage_unavailable",
    }
    assert api.call("castle_problem_begin", payload())["status"] == (
        "platform_private_storage_unavailable"
    )
    assert not api.palace.exists()


@pytest.mark.parametrize("missing", ["getuid", "O_NOFOLLOW", "O_NONBLOCK"])
def test_missing_private_file_primitives_never_accept_policy(api, monkeypatch, missing):
    from types import SimpleNamespace
    from cognitive_castle import brain_api, brain_loop

    api.policy_path.parent.mkdir(parents=True, mode=0o700)
    api.policy_path.write_text('{"allow_local_sources":true}')
    api.policy_path.chmod(0o600)
    unsupported_os = SimpleNamespace(
        **{name: value for name, value in vars(brain_loop.os).items() if name != missing}
    )
    monkeypatch.setattr(brain_loop, "os", unsupported_os)
    monkeypatch.setattr(brain_api, "os", unsupported_os)
    assert api.policy()["allow_local_sources"] is False


def test_cli_input_file_fails_explicitly_without_private_file_primitives(
    tmp_path, monkeypatch, capsys
):
    from types import SimpleNamespace
    from cognitive_castle import brain_api, brain_loop

    path = tmp_path / "request.json"
    path.write_text('{"text":"A short article."}')
    unsupported_os = SimpleNamespace(
        **{name: value for name, value in vars(brain_loop.os).items() if name != "O_NOFOLLOW"}
    )
    monkeypatch.setattr(brain_loop, "os", unsupported_os)
    monkeypatch.setattr(brain_api, "os", unsupported_os)
    with pytest.raises(SystemExit) as stopped:
        brain_api.cmd_brain(
            SimpleNamespace(
                brain_action="article", input=str(path), palace=str(tmp_path / "palace")
            )
        )
    assert stopped.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "invalid_request"
    assert "standard input" in result["reason"]
    assert not (tmp_path / "palace").exists()


def test_capability_and_denied_recall_have_no_storage_side_effect(api, monkeypatch):
    from cognitive_castle import brain_sources

    monkeypatch.setattr(
        brain_sources, "recall", lambda *a, **k: pytest.fail("unauthorized native read")
    )
    capabilities = api.call("castle_brain_capabilities", {})
    assert capabilities["model_required"] is False
    recall = api.call("castle_brain_recall", {"query": "consent"})
    if os.name == "posix":
        assert capabilities["problem_controller"]["status"] == "available"
        assert recall["status"] == "exposure_blocked"
    else:
        assert capabilities["problem_controller"]["status"] == "unavailable"
        assert recall == {
            "status": "unavailable",
            "reason": "platform_private_storage_unavailable",
        }
    assert not api.palace.exists()


def test_server_instructions_do_not_override_bounded_workflow_with_automatic_writes():
    from cognitive_castle.mcp_server import PALACE_PROTOCOL

    assert "Do not automatically file" in PALACE_PROTOCOL
    assert "After significant work" not in PALACE_PROTOCOL
    assert "When making non-obvious design decisions" not in PALACE_PROTOCOL
    assert "separately configured provider" in PALACE_PROTOCOL


@pytest.mark.parametrize(
    "change",
    [
        dict(protocol_version=2),
        dict(protocol_version=True),
        dict(allow_local_sources=True),
        dict(extra="ignored?"),
    ],
)
def test_strict_problem_schema_rejects_before_effect(api, change):
    with pytest.raises(ValueError):
        api.call("castle_problem_begin", payload() | change)
    assert not api.palace.exists()


@requires_private_storage
def test_missing_protocol_and_coerced_page_rejected(api):
    request = payload()
    request.pop("protocol_version")
    with pytest.raises(ValueError):
        api.call("castle_problem_begin", request)
    state = api.call("castle_problem_begin", payload())
    for offset in (True, "0", 0.0):
        with pytest.raises(ValueError):
            api.call(
                "castle_problem_page",
                dict(
                    protocol_version=1,
                    session_id=state["session_id"],
                    kind="problem",
                    offset=offset,
                ),
            )


@requires_private_storage
def test_resume_from_status_and_pages(api):
    state = api.call("castle_problem_begin", payload())
    common = dict(protocol_version=1, session_id=state["session_id"])
    assert api.call("castle_problem_status", common)["revision"] == state["revision"]
    page = api.call("castle_problem_page", common | {"kind": "problem"})
    assert json.loads(page["text"]) == "Require consent."
    cancelled = api.call(
        "castle_problem_cancel",
        common | dict(request_id="cancel", expected_revision=state["revision"]),
    )
    assert cancelled["execution_state"] == "cancelled"


@requires_private_storage
def test_cursor_passes_unchanged_through_host_api(api):
    state = api.call("castle_problem_begin", payload())
    common = dict(protocol_version=1, session_id=state["session_id"], kind="problem", limit=4)
    first = api.call("castle_problem_page", common)
    second = api.call(
        "castle_problem_page", common | dict(offset=first["next_offset"], cursor=first["cursor"])
    )
    assert second["status"] == "ok"
    assert first["text"] + second["text"] == '"Require'


@requires_private_storage
def test_policy_is_local_private_and_reloaded(api, tmp_path):
    api.policy_path.parent.mkdir(parents=True, mode=0o700)
    api.policy_path.write_text('{"allow_local_sources": true}')
    api.policy_path.chmod(0o600)
    assert api.policy()["allow_local_sources"] is True
    first = api.policy()["policy_epoch"]
    api.policy_path.write_text('{"allow_local_sources": false}')
    assert api.policy()["allow_local_sources"] is False
    assert api.policy()["policy_epoch"] != first
    api.policy_path.chmod(0o644)
    assert api.policy()["allow_local_sources"] is False
    api.policy_path.unlink()
    target = tmp_path / "grant.json"
    target.write_text('{"allow_local_sources": true}')
    target.chmod(0o600)
    api.policy_path.symlink_to(target)
    assert api.policy()["allow_local_sources"] is False


@requires_private_storage
def test_recall_requires_launch_host_even_with_native_source_grant(api, monkeypatch):
    from cognitive_castle import brain_sources
    from cognitive_castle.brain_loop import source_exposure_hash

    text = "allowed " * 6000
    source = {"id": "s1", "text": text, "provenance": {"local_only": True}}
    api.policy_path.parent.mkdir(parents=True, mode=0o700)
    api.policy_path.write_text(
        json.dumps(
            {"allow_local_sources": False, "allowed_source_hashes": [source_exposure_hash(source)]}
        )
    )
    api.policy_path.chmod(0o600)
    monkeypatch.setattr(
        brain_sources,
        "recall",
        lambda *a, **k: {
            "status": "ok",
            "sources": [
                source,
                {"id": "s2", "text": "private excluded", "provenance": {"local_only": True}},
            ],
        },
    )
    result = api.call("castle_brain_recall", {"query": "allowed"})
    assert result["status"] == "exposure_blocked"
    assert "sources" not in result
    assert "private excluded" not in json.dumps(result)


@requires_private_storage
def test_cli_roundtrip_uses_same_strict_api(tmp_path, monkeypatch, capsys):
    import io
    from cognitive_castle.cli import main

    monkeypatch.setattr(
        "sys.argv", ["castle", "--palace", str(tmp_path / "palace"), "brain", "begin"]
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload())))
    main()
    state = json.loads(capsys.readouterr().out)
    assert state["execution_state"] == "awaiting_response"


@requires_private_storage
def test_mcp_strict_dispatch_and_actual_envelope(api, monkeypatch):
    from cognitive_castle import mcp_server
    from cognitive_castle.brain_api import tool_registry
    from cognitive_castle.bounded_json import encode_response

    monkeypatch.setattr(mcp_server, "TOOLS", tool_registry(lambda: api))

    def request(arguments):
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "castle_problem_begin", "arguments": arguments},
        }

    invalid = mcp_server.handle_request(request(payload() | {"unexpected": True}))
    assert invalid["error"]["code"] == -32602
    assert not api.palace.exists()
    valid = mcp_server.handle_request(request(payload()))
    assert len(encode_response(valid)) <= 32768
    assert (
        json.loads(valid["result"]["content"][0]["text"])["execution_state"] == "awaiting_response"
    )


@requires_private_storage
def test_actual_mcp_loop_recovers_syntax_error_and_closes_invalid_tail(api, monkeypatch):
    import io
    from cognitive_castle import mcp_server
    from cognitive_castle.brain_api import tool_registry
    from cognitive_castle.bounded_json import MAX_FRAME_BYTES

    monkeypatch.setattr(mcp_server, "TOOLS", tool_registry(lambda: api))
    monkeypatch.setattr(mcp_server, "_restore_stdout", lambda: None)
    valid = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "castle_problem_begin", "arguments": payload()},
        }
    ).encode()
    output = io.StringIO()
    monkeypatch.setattr("sys.stdin", io.BytesIO(b"{bad}\n" + valid + b"\n"))
    monkeypatch.setattr("sys.stdout", output)
    mcp_server.main()
    responses = [json.loads(line) for line in output.getvalue().splitlines()]
    assert responses[0]["error"]["code"] == -32700
    assert (
        json.loads(responses[1]["result"]["content"][0]["text"])["execution_state"]
        == "awaiting_response"
    )
    output = io.StringIO()
    monkeypatch.setattr(
        "sys.stdin", io.BytesIO(b"x" * (MAX_FRAME_BYTES + 1) + b"\n" + valid + b"\n")
    )
    monkeypatch.setattr("sys.stdout", output)
    mcp_server.main()
    assert output.getvalue() == ""


@requires_private_storage
def test_archive_bind_checks_current_policy_and_has_exact_snapshots(api, monkeypatch):
    from cognitive_castle import brain_sources
    from cognitive_castle.brain_loop import source_exposure_hash

    source = {
        "id": "one",
        "text": "source text",
        "provenance": {"origin": "archive", "local_only": True},
    }
    api.policy_path.parent.mkdir(parents=True, mode=0o700)
    api.policy_path.write_text(
        json.dumps({"allowed_source_hashes": [source_exposure_hash(source)]})
    )
    api.policy_path.chmod(0o600)
    monkeypatch.setattr(
        brain_sources, "read_sources", lambda *a, **k: {"status": "ok", "sources": [source]}
    )
    result = api.call("castle_problem_begin", payload() | {"archive_ids": ["one"]})
    common = dict(protocol_version=1, session_id=result["session_id"], kind="sources")
    page = api.call("castle_problem_page", common)
    assert json.loads(page["text"])[0]["text"] == "source text"
    api.policy_path.write_text('{"allow_local_sources":false}')
    denied = api.call("castle_problem_page", common)
    assert "source text" not in json.dumps(denied)
    assert denied["status"] == "exposure_denied"


@requires_private_storage
def test_archive_begin_exact_wire_retry_never_reopens_changed_or_missing_archive(api, monkeypatch):
    from cognitive_castle import brain_sources

    api.policy_path.parent.mkdir(parents=True, mode=0o700)
    api.policy_path.write_text('{"allow_local_sources":true}')
    api.policy_path.chmod(0o600)
    source = {
        "id": "one",
        "text": "frozen original",
        "provenance": {"origin": "archive", "local_only": True, "version": 1},
    }
    monkeypatch.setattr(
        brain_sources, "read_sources", lambda *a, **k: {"status": "ok", "sources": [source]}
    )
    request = payload() | {"archive_ids": ["one"]}
    first = api.call("castle_problem_begin", request)
    monkeypatch.setattr(
        brain_sources,
        "read_sources",
        lambda *a, **k: pytest.fail("committed replay reopened archive"),
    )
    replay = api.call("castle_problem_begin", request)
    assert replay["session_id"] == first["session_id"]
    assert replay["revision"] == first["revision"]
    api.policy_path.write_text('{"allow_local_sources":false}')
    revoked = api.call("castle_problem_begin", request)
    assert revoked["status"] == "exposure_denied"
    assert "frozen original" not in json.dumps(revoked)


def test_large_rpc_id_cannot_bypass_strict_error_wire_limit(monkeypatch):
    from cognitive_castle import mcp_server

    response = mcp_server.handle_request(
        {
            "id": "x" * 40000,
            "method": "tools/call",
            "params": {"name": "castle_problem_begin", "arguments": {"invalid": True}},
        }
    )
    assert len(json.dumps(response).encode()) < 32768
    assert response["id"] is None


@requires_private_storage
def test_scoped_recall_counts_root_budget_before_native_access(api, monkeypatch):
    from cognitive_castle import brain_sources

    state = api.call("castle_problem_begin", payload())
    common = dict(protocol_version=1, session_id=state["session_id"])
    monkeypatch.setattr(
        brain_sources, "recall", lambda *a, **k: pytest.fail("native access after cap")
    )
    for _ in range(64):
        api.call("castle_problem_status", common)
    result = api.call("castle_brain_recall", common | {"query": "irrelevant"})
    assert result["status"] == "request_budget_exhausted"


@pytest.mark.parametrize("failure", ["unavailable", "invalid"])
@requires_private_storage
def test_failed_archive_successor_attempts_count_once_and_stop(api, monkeypatch, failure):
    from cognitive_castle import brain_sources

    state = api.call("castle_problem_begin", payload())
    api.policy_path.write_text('{"allow_local_sources":true}')
    api.policy_path.chmod(0o600)
    reads = []

    def read(*a, **k):
        reads.append(1)
        if failure == "invalid":
            raise ValueError("invalid native source selection")
        return {"status": "unavailable", "reason": "missing synthetic archive"}

    monkeypatch.setattr(brain_sources, "read_sources", read)
    request = payload() | dict(
        archive_ids=["missing"],
        parent_id=state["session_id"],
        expected_revision=state["revision"],
        revision_reason="Need evidence",
    )
    for i in range(70):
        try:
            result = api.call("castle_problem_begin", request | {"request_id": f"failed{i}"})
        except ValueError:
            assert failure == "invalid"
    assert len(reads) == 63
    assert result["status"] == "request_budget_exhausted"


@requires_private_storage
def test_same_text_with_different_private_provenance_is_not_granted(api, monkeypatch):
    from cognitive_castle import brain_sources
    from cognitive_castle.brain_loop import source_exposure_hash

    approved = {
        "id": "one",
        "text": "identical text",
        "provenance": {"local_only": True, "owner": "approved"},
    }
    different = {
        **approved,
        "provenance": {"local_only": True, "owner": "confidential different tenant"},
    }
    api.policy_path.parent.mkdir(parents=True, mode=0o700)
    api.policy_path.write_text(
        json.dumps({"allowed_source_hashes": [source_exposure_hash(approved)]})
    )
    api.policy_path.chmod(0o600)
    monkeypatch.setattr(
        brain_sources, "read_sources", lambda *a, **k: {"status": "ok", "sources": [different]}
    )
    result = api.call("castle_problem_begin", payload() | {"archive_ids": ["one"]})
    assert result["status"] == "exposure_blocked"
    assert "confidential" not in json.dumps(result)


@pytest.mark.parametrize("successor", [False, True])
@requires_private_storage
def test_spent_root_begin_never_materializes_archive_before_budget_check(
    api, monkeypatch, successor
):
    from cognitive_castle import brain_sources

    state = api.call("castle_problem_begin", payload())
    common = dict(protocol_version=1, session_id=state["session_id"])
    for _ in range(64):
        api.call("castle_problem_status", common)
    monkeypatch.setattr(
        brain_sources,
        "read_sources",
        lambda *a, **k: pytest.fail("native materialization after spent budget"),
    )
    api.policy_path.write_text('{"allow_local_sources":true}')
    api.policy_path.chmod(0o600)
    request = payload() | {"request_id": "new", "archive_ids": ["one"]}
    if successor:
        request.update(
            parent_id=state["session_id"],
            expected_revision=state["revision"],
            revision_reason="Changed context",
        )
    result = api.call("castle_problem_begin", request)
    assert result["status"] == "request_budget_exhausted"


@pytest.mark.parametrize("input_option", [[], ["--input", "-"]])
def test_memory_status_cli_honors_piped_pages(tmp_path, monkeypatch, capsys, input_option):
    import argparse
    import io
    from cognitive_castle import brain_api

    parser = argparse.ArgumentParser()
    brain_api.configure_parser(parser.add_subparsers())
    args = parser.parse_args(["brain", "memory_status", *input_option])
    args.palace = str(tmp_path)
    calls = []
    monkeypatch.setattr(
        brain_api.BrainAPI,
        "call",
        lambda self, name, request: calls.append((name, request)) or {"status": "ok"},
    )
    monkeypatch.setattr("sys.stdin", io.StringIO('{"protocol_version":1,"after":17,"limit":2}'))
    brain_api.cmd_brain(args)
    assert calls == [("castle_memory_status", {"protocol_version": 1, "after": 17, "limit": 2})]
    assert json.loads(capsys.readouterr().out)["status"] == "ok"


def test_memory_status_cli_rejects_malformed_and_accepts_eof(tmp_path, monkeypatch, capsys):
    import argparse
    import io
    from cognitive_castle import brain_api

    args = argparse.Namespace(brain_action="memory_status", input="-", palace=str(tmp_path))
    calls = []
    monkeypatch.setattr(
        brain_api.BrainAPI,
        "call",
        lambda self, name, request: calls.append(request) or {"status": "ok"},
    )
    monkeypatch.setattr("sys.stdin", io.StringIO("{bad}"))
    with pytest.raises(SystemExit) as exc:
        brain_api.cmd_brain(args)
    assert exc.value.code == 2
    assert calls == []
    assert json.loads(capsys.readouterr().out)["status"] == "invalid_request"
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    brain_api.cmd_brain(args)
    assert calls == [{"protocol_version": 1}]


def test_memory_status_cli_interactive_no_input(tmp_path, monkeypatch, capsys):
    import argparse
    from cognitive_castle import brain_api

    class Interactive:
        def isatty(self):
            return True

        def read(self, *args):
            pytest.fail("interactive no-input status must not wait for stdin")

    calls = []
    monkeypatch.setattr("sys.stdin", Interactive())
    monkeypatch.setattr(
        brain_api.BrainAPI,
        "call",
        lambda self, name, request: calls.append(request) or {"status": "ok"},
    )
    brain_api.cmd_brain(
        argparse.Namespace(brain_action="memory_status", input="-", palace=str(tmp_path))
    )
    assert calls == [{"protocol_version": 1}]
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
