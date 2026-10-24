"""Fixed-budget, model-free memory subprocess supervision.

Only the trusted host calls this module. Namespace and registered ingest roots
are host decisions, never permissions granted by a memory tool argument.
RSS limits are sampled tripwires, not kernel allocation ceilings.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import time

from .brain_reader_guardian import _group_rss, _pressure_ok, _write_ready

WORKER_RSS = 128 * 1024**2
TOTAL_RSS = 192 * 1024**2
MAX_FRAME = 512 * 1024
DEADLINES = dict(remember=3, recall=2, read_sources=2, page=2, status=2, ingest_slice=3)
_FIELDS = {
    "remember": ({"request_id", "text"}, {"provenance", "namespace"}),
    "recall": ({"query"}, {"limit"}),
    "read_sources": ({"ids"}, set()),
    "page": ({"source_id"}, {"offset", "limit", "expected_hash"}),
    "status": (set(), set()),
    "ingest_slice": ({"path", "allowed_root", "format"}, set()),
}


def _unavailable(reason):
    return {"status": "unavailable", "reason": reason}


def _admission():
    """One inherited admission inode for all palaces and HOME overrides."""
    import fcntl

    base = (
        Path("/private/tmp" if sys.platform == "darwin" else "/tmp")
        / f"castle-memory-{os.getuid()}"
    )
    try:
        base.mkdir(mode=0o700)
    except FileExistsError:
        pass
    info = base.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise OSError("unsafe admission directory")
    fd = os.open(base / "admission.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
        ):
            raise OSError("unsafe admission file")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BaseException:
        os.close(fd)
        raise


def run_memory(palace: Path, operation: str, arguments: dict) -> dict:
    """Execute one bounded operation; caller supplies trusted paths/namespace."""
    if operation not in _FIELDS or not isinstance(arguments, dict):
        raise ValueError("invalid memory operation")
    required, optional = _FIELDS[operation]
    if not required <= arguments.keys() or arguments.keys() - required - optional:
        raise ValueError("invalid memory arguments")
    request = {
        "palace": str(Path(palace).absolute()),
        "operation": operation,
        "arguments": arguments,
    }
    try:
        frame = json.dumps(request, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise ValueError("invalid memory frame") from exc
    if len(frame) > MAX_FRAME:
        raise ValueError("memory request limit")
    if sys.platform != "darwin" or importlib.util.find_spec("psutil") is None:
        return _unavailable("platform_supervision_unavailable")
    path = Path(request["palace"])
    if not path.is_dir() or path.resolve() != path:
        return _unavailable("unsafe_palace_path")
    try:
        fd = _admission()
    except BlockingIOError:
        return _unavailable("memory_busy")
    except OSError:
        return _unavailable("admission_unavailable")
    try:
        return _supervise(request, fd, deadline=DEADLINES[operation])
    finally:
        # Never unlock explicitly: descendants retain admission until they exit.
        os.close(fd)


def _supervise(request, admission, *, worker_command=None, deadline=2):
    """Keep the guardian unreaped until killing its owned process group."""
    import psutil

    if not _pressure_ok():
        return _unavailable("system_pressure_unavailable")
    parent = psutil.Process()
    try:
        parent_rss = parent.memory_info().rss
    except psutil.Error:
        return _unavailable("resource_measurement_unavailable")
    if parent_rss >= TOTAL_RSS:
        return _unavailable("parent_memory_limit")
    worker = Path(__file__).with_name("memory_worker.py")
    config = {
        "request": {**request, "_host_pid": os.getpid()},
        "command": worker_command or [sys.executable, "-I", str(worker)],
        "admission": admission,
        "deadline": deadline,
        "rss_limit": WORKER_RSS,
        "max_frame": MAX_FRAME,
        "parent_pid": os.getpid(),
        "total_rss_limit": TOTAL_RSS,
    }
    proc = None
    selector = selectors.DefaultSelector()
    output = bytearray()
    started = time.monotonic()
    peak_task, peak_total = 0, parent_rss
    next_pressure = started + 0.25

    def finish(value):
        if not isinstance(value, dict) or not isinstance(value.get("status"), str):
            return _unavailable("worker_invalid_frame")
        value["resources"] = {
            "peak_task_rss_bytes": peak_task,
            "peak_total_rss_bytes": peak_total,
            "elapsed_seconds": round(time.monotonic() - started, 4),
            "memory_guarantee": "sampled RSS tripwire; transient peaks are possible",
        }
        return value

    try:
        proc = subprocess.Popen(
            [sys.executable, "-I", str(worker.with_name("brain_reader_guardian.py"))],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            pass_fds=(admission,),
            start_new_session=True,
        )
        pending = memoryview(json.dumps(config).encode() + b"\n")
        os.set_blocking(proc.stdin.fileno(), False)
        selector.register(proc.stdin, selectors.EVENT_WRITE, "config")
        selector.register(proc.stdout, selectors.EVENT_READ, "response")
        leader = psutil.Process(proc.pid)
        while time.monotonic() - started < deadline:
            task_rss = _group_rss(proc.pid)
            total_rss = task_rss + parent.memory_info().rss
            peak_task = max(peak_task, task_rss)
            peak_total = max(peak_total, total_rss)
            if task_rss > WORKER_RSS:
                return finish(_unavailable("worker_memory_limit"))
            if total_rss > TOTAL_RSS:
                return finish(_unavailable("total_memory_limit"))
            if time.monotonic() >= next_pressure:
                if not _pressure_ok():
                    return finish(_unavailable("system_pressure_unavailable"))
                next_pressure = time.monotonic() + 0.25
            for key, _ in selector.select(0.01):
                if key.data == "config":
                    # Keep the pipe open after transmission as host-death channel.
                    pending = _write_ready(selector, proc.stdin, pending)
                    continue
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    try:
                        return finish(json.loads(output))
                    except (ValueError, UnicodeError, RecursionError):
                        return finish(_unavailable("worker_invalid_frame"))
                output.extend(chunk)
                if len(output) > MAX_FRAME:
                    return finish(_unavailable("worker_output_limit"))
            if leader.status() == psutil.STATUS_ZOMBIE:
                # Pipe EOF is observed on the next selector iteration; no reap.
                continue
        return finish(_unavailable("worker_deadline"))
    except (OSError, ValueError, psutil.Error):
        return finish(_unavailable("worker_failed"))
    finally:
        selector.close()
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError:
                # macOS may report EPERM for groups containing only zombies.
                from .brain_reader_guardian import _owned_group_members

                if any(p.status() != psutil.STATUS_ZOMBIE for p in _owned_group_members(proc.pid)):
                    raise
            proc.wait(timeout=2)
            proc.stdin.close()
            proc.stdout.close()
