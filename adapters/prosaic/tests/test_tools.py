import json
import time

import pytest

from prosaic_runtime import InvocationScope
from prosaic_runtime.tools import execute_custom_tool


def execute(tool, arguments, *, scope=None, deadline=None):
    return execute_custom_tool(
        tool,
        json.dumps(arguments, ensure_ascii=False),
        check_boundary=lambda: None,
        scope=scope or InvocationScope("invocation"),
        deadline=deadline or time.monotonic() + 5,
    )


def test_tools_are_contextual_closed_and_authorized_before_worker_dispatch(provider):
    from prosaic_memory_castle import memory_tools

    memory, marker = provider()
    seen = []
    tools = memory_tools(memory, authorize=lambda ctx: seen.append(ctx) or False)
    assert set(tools) == {"memory_search", "memory_fetch"}
    assert tools["memory_search"].with_context and tools["memory_fetch"].with_context
    assert execute(tools["memory_search"], {"query": "needle"}) == {
        "status": "error",
        "error": "authorization_denied",
    }
    assert seen[0].scope.run_id is None
    assert not marker.exists()


@pytest.mark.parametrize(
    "arguments",
    [
        {"query": "x", "namespace": "other"},
        {"query": "x", "path": "/other"},
        {"query": "x", "limit": 21},
        {"query": "x", "limit": 0},
        {"query": ""},
        {"query": "x", "limit": True},
    ],
)
def test_model_cannot_change_grants_or_escape_search_bounds(provider, arguments):
    from prosaic_memory_castle import memory_tools

    memory, marker = provider()
    tools = memory_tools(memory, authorize=lambda ctx: True)
    assert execute(tools["memory_search"], arguments)["error"] == "invalid_arguments"
    assert not marker.exists()


def test_multibyte_query_limit_is_utf8_bytes_and_valid_context_has_no_run_id(provider):
    from prosaic_memory_castle import memory_tools

    memory, marker = provider()
    scopes = []
    tools = memory_tools(memory, authorize=lambda ctx: scopes.append(ctx.scope) or True)
    assert execute(tools["memory_search"], {"query": "é" * 2048})["status"] == "ok"
    assert execute(tools["memory_search"], {"query": "é" * 2048 + "x"}) == {
        "status": "error",
        "error": "tool_invalid_request",
    }
    assert all(scope.run_id is None for scope in scopes)
    assert marker.with_suffix(".calls").read_text().splitlines().count("search") == 1


@pytest.mark.parametrize(
    "code,want",
    [
        ("not_found", "tool_not_found"),
        ("unavailable", "tool_unavailable"),
        ("invalid_request", "tool_invalid_request"),
        ("result_limit", "tool_result_limit"),
        ("incompatible_store", "tool_incompatible"),
        ("deadline_exceeded", "tool_timeout"),
        ("cancelled", "tool_unavailable"),
    ],
)
def test_domain_failures_are_runtime_errors_not_successful_result_envelopes(provider, code, want):
    from prosaic_memory_castle import memory_tools

    memory, _ = provider("error:" + code)
    tools = memory_tools(memory, authorize=lambda ctx: True)
    assert execute(tools["memory_fetch"], {"record_id": "guessed"}) == {
        "status": "error",
        "error": want,
    }


def test_required_authorizer_and_runtime_capability(provider, monkeypatch):
    from prosaic_memory_castle import memory_tools
    from prosaic_runtime import ProsaicRuntime

    memory, marker = provider()
    with pytest.raises(ValueError):
        memory_tools(memory, authorize=None)
    monkeypatch.setattr(ProsaicRuntime, "capabilities", frozenset({"custom_tools_v1"}))
    with pytest.raises(ValueError, match="custom_tool_errors_v1"):
        memory_tools(memory, authorize=lambda ctx: True)
    assert not marker.exists()


def test_shorter_tool_timeout_is_safe_error_but_parent_deadline_propagates(provider):
    from prosaic_memory_castle import memory_tools
    from prosaic_runtime.tools import ToolDeadlineExceeded

    memory, _ = provider("hang_read", operation_timeout=0.1)
    tools = memory_tools(memory, authorize=lambda ctx: True)
    assert execute(tools["memory_search"], {"query": "x"}) == {
        "status": "error",
        "error": "tool_timeout",
    }
    memory, _ = provider("hang_start", operation_timeout=10)
    tools = memory_tools(memory, authorize=lambda ctx: True)
    with pytest.raises(ToolDeadlineExceeded):
        execute(tools["memory_search"], {"query": "x"}, deadline=time.monotonic() + 0.1)
