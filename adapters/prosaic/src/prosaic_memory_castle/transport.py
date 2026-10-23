"""Bounded private process transport; worker grants are host-owned argv."""

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import threading
import time
import unicodedata
import uuid

from prosaic_runtime.events import Cancelled
from prosaic_runtime.tools import ToolDeadlineExceeded

MAX_FRAME_BYTES = 1048576
STDERR_BYTES = 65536
ERROR_CODES = frozenset(
    {
        "not_found",
        "unavailable",
        "invalid_request",
        "result_limit",
        "incompatible_store",
        "deadline_exceeded",
        "cancelled",
        "timeout",
    }
)
WIRE_ERROR_CODES = ERROR_CODES - {"timeout"}


class MemoryProviderError(RuntimeError):
    """A closed domain error. Worker diagnostics are never its message."""

    def __init__(self, code):
        if type(code) is not str or code not in ERROR_CODES:
            raise ValueError("unknown memory error code")
        self.code = code
        super().__init__(code)


class _ProtocolFailure(MemoryProviderError):
    pass


def _reference(value, maximum=128):
    return (
        type(value) is str
        and bool(value)
        and len(value.encode("utf-8")) <= maximum
        and not any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in value)
    )


def _absolute_path(value):
    try:
        path = os.fspath(value)
    except TypeError:
        raise ValueError("absolute path required") from None
    if type(path) is not str or "\x00" in path or not Path(path).is_absolute():
        raise ValueError("absolute path required")
    return path


@dataclass(frozen=True)
class WorkerCommand:
    argv: tuple[str, ...]

    def __post_init__(self):
        if (
            type(self.argv) is not tuple
            or not self.argv
            or any(type(arg) is not str or not arg or "\x00" in arg for arg in self.argv)
        ):
            raise ValueError("worker command must be a nonempty tuple of arguments")
        _absolute_path(self.argv[0])


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("nonfinite number")


def _strict_json(frame):
    value = json.loads(frame, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
    pending = [(value, 0)]
    while pending:
        child, level = pending.pop()
        if level > 64:
            raise ValueError("JSON depth")
        if type(child) is float and not math.isfinite(child):
            raise ValueError("nonfinite number")
        if type(child) in (list, dict):
            pending.extend(
                (item, level + 1) for item in (child.values() if type(child) is dict else child)
            )
    return value


class WorkerTransport:
    def __init__(
        self,
        command,
        *,
        palace_path,
        namespace,
        config_path,
        allowed_wings,
        startup_timeout,
        operation_timeout,
    ):
        if type(command) is not WorkerCommand:
            raise ValueError("WorkerCommand required")
        palace_path, config_path = _absolute_path(palace_path), _absolute_path(config_path)
        if not _reference(namespace):
            raise ValueError("invalid namespace")
        if isinstance(allowed_wings, (str, bytes)):
            raise ValueError("explicit nonempty wing scope required")
        try:
            wings = tuple(allowed_wings)
        except TypeError:
            raise ValueError("explicit nonempty wing scope required") from None
        if (
            not wings
            or any(not _reference(wing, 256) for wing in wings)
            or len(set(wings)) != len(wings)
        ):
            raise ValueError("explicit nonempty unique wing scope required")
        for timeout in (startup_timeout, operation_timeout):
            if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
                raise ValueError("positive finite timeout required")
        self.argv = (
            command.argv
            + ("--palace", palace_path, "--namespace", namespace, "--config", config_path)
            + tuple(part for wing in wings for part in ("--wing", wing))
        )
        self.startup_timeout, self.operation_timeout = startup_timeout, operation_timeout
        self._lock = threading.Lock()
        self._process = None
        self._closed = False
        self.stderr_tail = b""
        self.hello = None

    def _check(self, deadline, context):
        if context is not None:
            if context.cancelled():
                raise Cancelled()
            if context.deadline <= time.monotonic():
                raise ToolDeadlineExceeded()
        if time.monotonic() >= deadline:
            raise MemoryProviderError("timeout")

    def _start(self):
        try:
            process = subprocess.Popen(
                self.argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                start_new_session=True,
                close_fds=True,
            )
            self._process = process
            if self._closed:
                self._shutdown()
                raise MemoryProviderError("unavailable")
            for pipe in (process.stdin, process.stdout, process.stderr):
                os.set_blocking(pipe.fileno(), False)
        except (OSError, ValueError):
            self._shutdown()
            raise MemoryProviderError("unavailable") from None
        self.stderr_tail = b""

    def _exchange(self, op, args, deadline, context):
        request_id = uuid.uuid4().hex
        try:
            outgoing = (
                json.dumps(
                    {"version": 1, "id": request_id, "op": op, "args": args},
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError):
            raise MemoryProviderError("invalid_request") from None
        if len(outgoing) > MAX_FRAME_BYTES:
            raise MemoryProviderError("result_limit")
        process = self._process
        if process is None or self._closed:
            raise MemoryProviderError("unavailable")
        received = bytearray()
        sent = 0
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while True:
                self._check(deadline, context)
                for key, _ in selector.select(min(0.025, max(0, deadline - time.monotonic()))):
                    self._check(deadline, context)
                    if key.data == "stdin":
                        try:
                            sent += os.write(key.fd, outgoing[sent : sent + 65536])
                        except BlockingIOError:
                            continue
                        if sent == len(outgoing):
                            selector.unregister(key.fileobj)
                        continue
                    try:
                        chunk = os.read(key.fd, 65536)
                    except BlockingIOError:
                        continue
                    if key.data == "stderr":
                        if chunk:
                            self.stderr_tail = (self.stderr_tail + chunk)[-STDERR_BYTES:]
                        else:
                            selector.unregister(key.fileobj)
                        continue
                    if not chunk:
                        raise _ProtocolFailure("unavailable")
                    received.extend(chunk)
                    if len(received) > MAX_FRAME_BYTES:
                        raise _ProtocolFailure("result_limit")
                    if b"\n" in received:
                        line, trailing = bytes(received).split(b"\n", 1)
                        if trailing:
                            raise _ProtocolFailure("incompatible_store")
                        return self._response(line, request_id)

    @staticmethod
    def _response(line, request_id):
        try:
            response = _strict_json(line)
            if (
                type(response) is not dict
                or response.get("version") != 1
                or type(response.get("version")) is not int
                or response.get("id") != request_id
                or type(response.get("ok")) is not bool
            ):
                raise ValueError("invalid envelope")
            if response["ok"]:
                if (
                    set(response) != {"version", "id", "ok", "result"}
                    or type(response["result"]) is not dict
                ):
                    raise ValueError("invalid result")
                return response["result"]
            if (
                set(response) != {"version", "id", "ok", "error"}
                or type(response["error"]) is not dict
                or set(response["error"]) != {"code"}
                or type(response["error"]["code"]) is not str
                or response["error"]["code"] not in WIRE_ERROR_CODES
            ):
                raise ValueError("invalid error")
        except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
            raise _ProtocolFailure("incompatible_store") from None
        raise MemoryProviderError(response["error"]["code"])

    def request(self, op, args, *, context=None):
        if op not in {"health", "search", "fetch", "snapshot"} or type(args) is not dict:
            raise MemoryProviderError("invalid_request")
        maximum = self.startup_timeout if op == "health" else self.operation_timeout
        deadline = time.monotonic() + maximum
        if context is not None:
            deadline = min(deadline, context.deadline)
        self._check(deadline, context)
        while not self._lock.acquire(timeout=min(0.025, max(0, deadline - time.monotonic()))):
            self._check(deadline, context)
        try:
            self._check(deadline, context)
            if self._closed:
                raise MemoryProviderError("unavailable")
            if self._process is None:
                self._start()
                try:
                    hello = self._exchange(
                        "hello", {}, min(deadline, time.monotonic() + self.startup_timeout), context
                    )
                    if (
                        type(hello.get("schema_version")) is not int
                        or hello["schema_version"] != 1
                        or hello.get("profile") != "memory-v1"
                        or type(hello.get("fingerprint")) is not str
                        or not re.fullmatch(r"[0-9a-f]{64}", hello["fingerprint"])
                        or type(hello.get("capabilities")) is not list
                        or not {"health", "search", "fetch", "snapshot"}
                        <= set(hello["capabilities"])
                    ):
                        raise _ProtocolFailure("incompatible_store")
                except MemoryProviderError:
                    self._shutdown()
                    raise
                self.hello = hello
            result = self._exchange(op, args, deadline, context)
            self._check(deadline, context)
            return result
        except (Cancelled, ToolDeadlineExceeded, _ProtocolFailure):
            self._shutdown()
            raise
        except MemoryProviderError as failure:
            try:
                self._check(deadline, context)
            except (Cancelled, ToolDeadlineExceeded, MemoryProviderError):
                self._shutdown()
                raise
            if failure.code in {"timeout", "deadline_exceeded", "cancelled"}:
                self._shutdown()
            raise
        except (OSError, ValueError, TypeError):
            self._shutdown()
            raise MemoryProviderError("unavailable") from None
        finally:
            self._lock.release()

    def _shutdown(self):
        process, self._process = self._process, None
        self.hello = None
        if process is None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            # Some POSIX sandboxes report EPERM for a group already exiting.
            # Always reap the owned direct child even when group signalling fails.
            try:
                process.terminate()
            except (ProcessLookupError, PermissionError):
                pass
        try:
            process.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            pass
        # The group may retain children after the direct worker exited.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                process.kill()
            except (ProcessLookupError, PermissionError):
                pass
        try:
            process.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            pass
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()

    def close(self):
        self._closed = True
        self._shutdown()
