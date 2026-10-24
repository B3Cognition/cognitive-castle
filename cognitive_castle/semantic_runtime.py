"""Inactive trusted semantic coordinator sharing the existing memory admission.

Only host preparation supplies the artifact manifest. The fixed worker and limits
are not public tool arguments. One session owns a single absolute deadline and
admission across all stages; callers must use the context manager.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import time

from . import memory_runtime
from .semantic_profile import MAX_FRAME, canonical_json, validate_vector
from .semantic_windows import input_binding, validate_page, validate_sources

TASK_RSS = 512 * 1024**2
TOTAL_RSS = 640 * 1024**2
DEADLINE = 5


class SemanticSession:
    def __init__(self, trusted_profile: Path, *, interactive=True):
        self._until = time.monotonic() + DEADLINE
        self._profile = Path(trusted_profile).absolute()
        self._interactive = interactive
        self._fd = self._waiter = None
        self._entered = False
        self._refusal = None
        self._issued = set()
        self.resources = []

    @property
    def remaining(self):
        return max(0, self._until - time.monotonic())

    def __enter__(self):
        if self._entered:
            raise ValueError("semantic session cannot be reused")
        self._entered = True
        if sys.platform != "darwin" or importlib.util.find_spec("psutil") is None:
            self._refusal = "platform_supervision_unavailable"
            return self
        try:
            if not self._interactive and memory_runtime.interactive_waiting():
                self._refusal = "memory_busy"
                return self
            try:
                self._fd = memory_runtime._admission()
            except BlockingIOError:
                if not self._interactive:
                    self._refusal = "memory_busy"
                    return self
                self._waiter = memory_runtime._waiting_marker()
                until = min(self._until, time.monotonic() + 0.5)
                while time.monotonic() < until:
                    try:
                        self._fd = memory_runtime._admission()
                        break
                    except BlockingIOError:
                        time.sleep(min(0.025, max(0, until - time.monotonic())))
                if self._fd is None:
                    self._refusal = "memory_busy"
            if not self._interactive and memory_runtime.interactive_waiting():
                self._refusal = "memory_busy"
        except OSError:
            self._refusal = "admission_unavailable"
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *args):
        for name in ("_fd", "_waiter"):
            fd = getattr(self, name)
            if fd is not None:
                os.close(fd)
                setattr(self, name, None)
        self._issued.clear()

    def _ready(self):
        if not self._entered:
            raise ValueError("semantic session requires context manager")
        if self._refusal:
            return {"status": "unavailable", "reason": self._refusal}
        if self._fd is None:
            return {"status": "unavailable", "reason": "semantic_session_closed"}
        if self.remaining <= 0:
            return {"status": "unavailable", "reason": "semantic_deadline"}
        if not self._interactive and memory_runtime.interactive_waiting():
            return {"status": "unavailable", "reason": "memory_busy"}
        return None

    def _run_stage(self, request, *, worker_command):
        """Internal extension point for a later fixed Lance stage under this lease."""
        refusal = self._ready()
        if refusal is not None:
            return refusal
        if len(canonical_json(request).encode("utf-8")) > MAX_FRAME:
            raise ValueError("semantic request limit")
        remaining = self.remaining
        if remaining <= 0:
            return {"status": "unavailable", "reason": "semantic_deadline"}
        result = memory_runtime._supervise(
            request,
            self._fd,
            worker_command=worker_command,
            deadline=remaining,
            rss_limit=TASK_RSS,
            total_rss_limit=TOTAL_RSS,
        )
        resources = result.pop("resources", None)
        if resources is not None:
            self.resources.append(resources)
        if result.get("status") == "ok" and self.remaining <= 0:
            return {"status": "unavailable", "reason": "semantic_deadline"}
        return result

    def _semantic(self, operation, arguments):
        return self._run_stage(
            {"operation": operation, "arguments": arguments},
            worker_command=[
                sys.executable,
                "-I",
                str(Path(__file__).with_name("semantic_worker.py")),
                "--profile",
                str(self._profile),
            ],
        )

    def tokenize(self, sources, continuation=None):
        refusal = self._ready()
        if refusal is not None:
            return refusal
        validate_sources(sources)
        result = self._semantic("tokenize", {"sources": sources, "continuation": continuation})
        if result.get("status") == "ok":
            try:
                validate_page(result)
                start = 0 if continuation is None else continuation["next_window"]
                if (
                    result["input_binding"] != input_binding(sources)
                    or result["start_window"] != start
                ):
                    raise ValueError("tokenizer response binding")
            except (ValueError, TypeError, KeyError):
                return {"status": "unavailable", "reason": "semantic_invalid_response"}
            if self.remaining <= 0:
                return {"status": "unavailable", "reason": "semantic_deadline"}
            self._issued.add(result["handoff_hash"])
        return result

    def infer(self, page):
        refusal = self._ready()
        if refusal is not None:
            return refusal
        validate_page(page)
        if page["handoff_hash"] not in self._issued:
            raise ValueError("unissued semantic handoff")
        result = self._semantic("infer", {"page": page, "expected_handoff": page["handoff_hash"]})
        if result.get("status") != "ok":
            return result
        try:
            fields = {
                "status",
                "profile",
                "handoff_hash",
                "input_binding",
                "start_window",
                "total_units",
                "next_continuation",
                "complete",
                "vectors",
                "runtime",
            }
            if set(result) != fields:
                raise ValueError("inference response signature")
            for key in fields - {"vectors", "runtime"}:
                if result[key] != page[key]:
                    raise ValueError("inference response binding")
            if not isinstance(result["vectors"], list) or len(result["vectors"]) != len(
                page["units"]
            ):
                raise ValueError("inference vector count")
            for row, unit in zip(result["vectors"], page["units"]):
                if (
                    not isinstance(row, dict)
                    or set(row) != {"unit_id", "vector"}
                    or row["unit_id"] != unit["unit_id"]
                ):
                    raise ValueError("inference vector identity")
                validate_vector(row["vector"])
        except (ValueError, TypeError, KeyError):
            return {"status": "unavailable", "reason": "semantic_invalid_response"}
        if self.remaining <= 0:
            return {"status": "unavailable", "reason": "semantic_deadline"}
        return result
