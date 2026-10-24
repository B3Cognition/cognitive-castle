"""Bounded JSON ingress and MCP wire output; this module has no model/storage imports."""

from __future__ import annotations

import json
import math
import os
import select
import stat
import time

MAX_FRAME_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 32 * 1024


class FrameError(ValueError):
    """Unrecoverable framing error: close connection, never parse its trailing bytes."""


def _pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON key")
        obj[key] = value
    return obj


def _check_tree(value, depth=0):
    if depth > 32:
        raise ValueError("JSON nesting limit")
    if isinstance(value, str):
        value.encode("utf-8", errors="strict")
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("nonfinite JSON number")
    elif isinstance(value, dict):
        if len(value) > 256:
            raise ValueError("JSON object size limit")
        for key, item in value.items():
            _check_tree(key, depth + 1)
            _check_tree(item, depth + 1)
    elif isinstance(value, list):
        if len(value) > 2048:
            raise ValueError("JSON array size limit")
        for item in value:
            _check_tree(item, depth + 1)


def strict_loads(raw, *, max_bytes=MAX_FRAME_BYTES):
    if isinstance(raw, str):
        raw = raw.encode("utf-8", errors="strict")
    if not isinstance(raw, bytes) or len(raw) > max_bytes:
        raise ValueError("JSON byte limit")
    # Scan nesting before JSON decoding can recurse or allocate nested containers.
    depth = 0
    quoted = escaped = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            if depth > 32:
                raise ValueError("JSON nesting limit")
        elif byte in (93, 125):
            depth -= 1

    def bad_constant(_):
        raise ValueError("nonfinite JSON number")

    value = json.loads(
        raw.decode("utf-8", errors="strict"), object_pairs_hook=_pairs, parse_constant=bad_constant
    )
    _check_tree(value)
    return value


def encode_response(response, *, max_bytes=MAX_RESPONSE_BYTES):
    raw = json.dumps(response, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(raw) <= max_bytes:
        return raw
    identifier = response.get("id") if isinstance(response, dict) else None
    if not (type(identifier) in (int, str) and len(str(identifier)) <= 128):
        identifier = None
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": identifier,
            "error": {
                "code": -32001,
                "message": "Response exceeds wire limit; request a bounded page.",
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _windows_pipe_chunk(fd, maximum):
    """Read only bytes already present on an exclusively owned Windows pipe."""
    import _winapi
    import msvcrt

    handle = msvcrt.get_osfhandle(fd)
    try:
        available = _winapi.PeekNamedPipe(handle)[0]
        if not available:
            return None
        # Native byte reads avoid the CRT's text-mode lookahead and descriptor
        # locks. No other thread may consume this connection's input handle.
        chunk, error = _winapi.ReadFile(handle, min(available, maximum))
        if error not in (0, 234):  # ERROR_MORE_DATA is valid for a message pipe.
            raise OSError("pipe read failed")
        return chunk
    except OSError as exc:
        if getattr(exc, "winerror", None) in (109, 232, 233):
            return b""  # broken, closing, or disconnected pipe
        raise


class FrameReader:
    """One newline-delimited JSON frame with bounded bytes and first-byte deadline."""

    def __init__(self, stream, *, max_bytes=MAX_FRAME_BYTES, deadline=10):
        self.stream = getattr(stream, "buffer", stream)
        self.max_bytes = max_bytes
        self.deadline = deadline
        self.buffer = bytearray()
        self.started = None
        self.failed = False
        try:
            self.fd = self.stream.fileno()
        except (AttributeError, OSError):
            self.fd = None  # in-memory test/caller stream; no blocking native read

    def _fail(self, reason):
        self.failed = True
        self.buffer.clear()
        raise FrameError(reason)

    def _windows_read(self, remaining):
        # select() cannot wait on Windows stdio pipes. Poll the sole input
        # handle instead of leaving a daemon blocked in a CRT read after timeout.
        maximum = min(4096, self.max_bytes + 1 - len(self.buffer))
        try:
            mode = os.fstat(self.fd).st_mode
            if stat.S_ISREG(mode):
                return os.read(self.fd, maximum)
            if not stat.S_ISFIFO(mode):
                self._fail("input stream unavailable: expected pipe or regular file")
            until = None if remaining is None else time.monotonic() + remaining
            while True:
                chunk = _windows_pipe_chunk(self.fd, maximum)
                if chunk is not None:
                    return chunk
                wait = 0.01 if until is None else min(0.01, until - time.monotonic())
                if wait <= 0:
                    self._fail("frame receive deadline")
                time.sleep(wait)
        except (ImportError, OSError):
            self._fail("input stream unavailable")

    def read(self):
        if self.failed:
            raise FrameError("connection already closed after frame error")
        if self.fd is None:
            line = self.stream.readline(self.max_bytes + 2)
            if isinstance(line, str):
                line = line.encode("utf-8", errors="strict")
            if not line:
                return None
            if len(line.rstrip(b"\n")) > self.max_bytes:
                self._fail("frame byte limit")
            if not line.endswith(b"\n"):
                self._fail("incomplete frame")
            return line[:-1]
        while True:
            newline = self.buffer.find(b"\n")
            if newline >= 0:
                if newline > self.max_bytes:
                    self._fail("frame byte limit")
                result = bytes(self.buffer[:newline])
                del self.buffer[: newline + 1]
                self.started = time.monotonic() if self.buffer else None
                return result
            if len(self.buffer) > self.max_bytes:
                self._fail("frame byte limit")
            remaining = (
                None if self.started is None else self.deadline - (time.monotonic() - self.started)
            )
            if remaining is not None and remaining <= 0:
                self._fail("frame receive deadline")
            if os.name == "nt":
                chunk = self._windows_read(remaining)
            else:
                ready, _, _ = select.select([self.fd], [], [], remaining)
                if not ready:
                    self._fail("frame receive deadline")
                chunk = os.read(self.fd, min(4096, self.max_bytes + 1 - len(self.buffer)))
            if not chunk:
                if self.buffer:
                    self._fail("incomplete frame")
                return None
            if self.started is None:
                self.started = time.monotonic()
            self.buffer.extend(chunk)
