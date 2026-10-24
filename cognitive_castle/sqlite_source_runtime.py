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


def export_slice(descriptor, cursor=None):
    binding = source_binding(descriptor)
    cursor = initial_cursor(binding, descriptor["store_id"]) if cursor is None else cursor
    validate_cursor(cursor, binding, descriptor["store_id"])
    request = {"descriptor": descriptor, "cursor": cursor}
    frame_bytes(request)

    def refusal(reason):
        return dict(
            status="unavailable",
            reason=reason,
            source_binding=binding,
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
        )

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
        if "cursor_before" not in result:
            return {**refusal(result.get("reason", "source_invalid_response")), **result}
        frame_bytes({key: value for key, value in result.items() if key != "resources"})
        return result
    finally:
        os.close(admission)
