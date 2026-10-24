"""Inactive private source read, with fixed existing SQLite supervision."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

from . import memory_runtime
from .sqlite_export_codec import (
    empty_counts,
    frame_bytes,
    initial_cursor,
    source_binding,
    validate_cursor,
)


def source_request(descriptor, cursor=None):
    binding = source_binding(descriptor)
    cursor = initial_cursor(binding, descriptor["store_id"]) if cursor is None else cursor
    validate_cursor(cursor, binding, descriptor["store_id"])
    request = {"descriptor": descriptor, "cursor": cursor}
    frame_bytes(request)
    return request


def source_refusal(request, result):
    """Normalize supervisor failures without allowing cursor/completion claims."""
    cursor = request["cursor"]
    return dict(
        status=result.get("status", "unavailable"),
        reason=result.get("reason", "source_invalid_response"),
        source_binding=cursor["source_binding"],
        cursor_before=cursor,
        cursor_after=cursor,
        entries=[],
        finalizations=[],
        complete=False,
        phase_complete=False,
        phase=cursor["phase"],
        coverage="incomplete",
        counts=empty_counts(),
        frame_bytes=0,
        **({"resources": result["resources"]} if "resources" in result else {}),
    )


def source_result(request, result):
    if "cursor_before" not in result:
        return source_refusal(request, result)
    frame_bytes({key: value for key, value in result.items() if key != "resources"})
    return result


def export_slice(descriptor, cursor=None):
    request = source_request(descriptor, cursor)

    def refusal(reason):
        return source_refusal(request, {"status": "unavailable", "reason": reason})

    if sys.platform != "darwin" or importlib.util.find_spec("psutil") is None:
        return refusal("platform_supervision_unavailable")
    if memory_runtime.interactive_waiting():
        return refusal("memory_busy")
    try:
        admission = memory_runtime._admission()
    except BlockingIOError:
        return refusal("memory_busy")
    except OSError:
        return refusal("admission_unavailable")
    try:
        if memory_runtime.interactive_waiting():
            return refusal("memory_busy")
        result = memory_runtime._supervise(
            request,
            admission,
            worker_command=[
                sys.executable,
                "-I",
                str(Path(__file__).with_name("sqlite_source_worker.py")),
            ],
            deadline=2,
            rss_limit=128 * 1024**2,
            total_rss_limit=192 * 1024**2,
            background_preempt=True,
        )
        return source_result(request, result)
    finally:
        os.close(admission)
