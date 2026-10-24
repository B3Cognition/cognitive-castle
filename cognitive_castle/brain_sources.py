"""Bounded, model-free source access. Native imports occur only in an owned worker.

Ordinary variable-width Lance drawers deliberately fail closed. The supported
fixed-v1 schema is documented in brain_reader; no archive is upgraded implicitly.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

from .brain_reader_guardian import _group_rss, _pressure_ok

MAX_TEXT = 64 * 1024
MAX_PROVENANCE = 8 * 1024
MAX_SOURCES = 8
MAX_QUERY = 1024
MAX_FRAME = 512 * 1024
RSS_LIMIT = 512 * 1024**2
DEADLINE = 10


def _unavailable(reason):
    return {"status": "unavailable", "reason": reason}


def capabilities() -> dict:
    """Report conditional capability without opening storage or importing models."""
    supported = (
        sys.platform == "darwin"
        and hasattr(os, "getuid")
        and importlib.util.find_spec("psutil") is not None
        and importlib.util.find_spec("lancedb") is not None
    )
    return {
        "status": "available" if supported else "unavailable",
        "reason": None if supported else "platform_supervision_unavailable",
        "validated_platforms": ["darwin"],
        "model_free": True,
        "read_only": True,
        "format": "castle_brain_fixed-v1",
        "legacy_variable_width": "unavailable",
        "existing_fts_required": True,
        "limits": {
            "sources": MAX_SOURCES,
            "text_bytes": MAX_TEXT,
            "provenance_bytes": MAX_PROVENANCE,
            "query_bytes": MAX_QUERY,
            "native_rss_bytes": RSS_LIMIT,
            "native_deadline_seconds": DEADLINE,
            "readers_per_os_user": 1,
        },
        "memory_guarantee": "sampled aggregate RSS tripwire; transient peaks are possible",
        "provenance_limit": "snapshot identity is not truth or currentness",
    }


def _bounded_string(value, maximum):
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError("invalid bounded string")
    try:
        if len(value.encode("utf-8")) > maximum:
            raise ValueError("invalid bounded string")
    except UnicodeError as exc:
        raise ValueError("invalid bounded string") from exc


def recall(palace_path: str, query: str, *, limit: int = 8) -> dict:
    """Lexical recall using an existing index, never dense/model fallback."""
    _bounded_string(query, MAX_QUERY)
    if not query.strip() or type(limit) is not int or not 1 <= limit <= MAX_SOURCES:
        raise ValueError("invalid query or limit")
    return _run(palace_path, {"operation": "recall", "query": query, "limit": limit})


def read_sources(palace_path: str, ids: list[str]) -> dict:
    """Read exact selected sources from one pinned, bounded snapshot."""
    if not isinstance(ids, list) or not 1 <= len(ids) <= MAX_SOURCES:
        raise ValueError("select between one and eight source IDs")
    for source_id in ids:
        _bounded_string(source_id, 128)
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate source IDs")
    return _run(palace_path, {"operation": "read", "ids": ids})


def _archive_path(palace_path):
    _bounded_string(palace_path, 4096)
    path = Path(palace_path).absolute()
    if not path.exists():
        return None, "source_unavailable"
    if path.resolve() != path or not path.is_dir():
        return None, "unsafe_source_path"
    return path, None


def _admission():
    """The inherited flock is released by the kernel after the last reader exits."""
    import fcntl

    # Stable across palaces and HOME overrides. Never unlink an admission inode.
    base = (
        Path("/private/tmp" if sys.platform == "darwin" else "/tmp")
        / f"castle-brain-reader-{os.getuid()}"
    )
    try:
        base.mkdir(mode=0o700)
    except FileExistsError:
        pass
    st = base.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise OSError("unsafe admission directory")
    fd = os.open(base / "admission.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        os.close(fd)
        raise OSError("unsafe admission file")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _run(palace_path, request):
    path, reason = _archive_path(palace_path)
    if reason:
        return _unavailable(reason)
    if capabilities()["status"] != "available":
        return _unavailable("platform_supervision_unavailable")
    try:
        admission = _admission()
    except BlockingIOError:
        return _unavailable("reader_busy")
    except OSError:
        return _unavailable("admission_unavailable")
    try:
        request = {**request, "palace_path": str(path)}
        return _supervise(request, admission)
    finally:
        # Do not LOCK_UN: the worker may still be exiting and owns this same lock.
        os.close(admission)


def _supervise(request, admission, *, worker_command=None, deadline=DEADLINE):
    """Mutually supervise host and guardian, retaining guardian PID until group kill.

    The guardian is an unreaped session leader until cleanup. Its PID therefore
    cannot be reused while the host kills that owned group. A host death closes
    the control pipe; a guardian death is observed by the host. The reader and
    guardian inherit admission, so no replacement is admitted ahead of exit.
    """
    import psutil

    if not _pressure_ok():
        return _unavailable("system_pressure_unavailable")
    next_pressure_check = time.monotonic() + 0.25
    guardian = Path(__file__).with_name("brain_reader_guardian.py")
    reader = Path(__file__).with_name("brain_reader.py")
    command = worker_command or [sys.executable, "-I", str(reader)]
    snapshot_dir = tempfile.mkdtemp(prefix="castle-brain-snapshot-")
    request = {**request, "snapshot_dir": snapshot_dir}
    config = {
        "request": request,
        "command": command,
        "admission": admission,
        "deadline": deadline,
        "rss_limit": RSS_LIMIT,
        "max_frame": MAX_FRAME,
    }
    proc = None
    selector = selectors.DefaultSelector()
    result = bytearray()
    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            [sys.executable, "-I", str(guardian)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            pass_fds=(admission,),
            start_new_session=True,
        )
        proc.stdin.write(json.dumps(config).encode() + b"\n")
        proc.stdin.flush()  # Kept open as the host-death channel.
        selector.register(proc.stdout, selectors.EVENT_READ)
        leader = psutil.Process(proc.pid)
        while time.monotonic() - started < deadline + 1:
            if time.monotonic() >= next_pressure_check:
                if not _pressure_ok():
                    return _unavailable("system_pressure_unavailable")
                next_pressure_check = time.monotonic() + 0.25
            for key, _ in selector.select(0.025):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    if result:
                        value = json.loads(result)
                        if isinstance(value, dict) and value.get("status") in {"ok", "unavailable"}:
                            return value
                    return _unavailable("reader_stopped")
                result.extend(chunk)
                if len(result) > MAX_FRAME:
                    return _unavailable("reader_output_limit")
            # Never poll()/wait() here: retain the PID even if the guardian dies.
            try:
                if _group_rss(proc.pid) > RSS_LIMIT:
                    return _unavailable("reader_memory_limit")
                if leader.status() == psutil.STATUS_ZOMBIE:
                    # Drain any completed result before teardown.
                    chunk = os.read(proc.stdout.fileno(), MAX_FRAME + 1 - len(result))
                    result.extend(chunk)
                    if result and len(result) <= MAX_FRAME:
                        return json.loads(result)
                    return _unavailable("reader_stopped")
            except psutil.NoSuchProcess:
                return _unavailable("reader_stopped")
        return _unavailable("reader_deadline")
    except (OSError, ValueError, psutil.Error):
        return _unavailable("reader_failed")
    finally:
        selector.close()
        if proc is not None:
            # Ownership is anchored by the still-unreaped session leader.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError:
                # macOS reports EPERM for a group containing only zombies.
                for member in psutil.process_iter(["pid", "status"]):
                    try:
                        if (
                            member.info["status"] != psutil.STATUS_ZOMBIE
                            and os.getpgid(member.pid) == proc.pid
                        ):
                            raise
                    except ProcessLookupError:
                        pass
            proc.wait(timeout=2)
            proc.stdin.close()
            proc.stdout.close()
        shutil.rmtree(snapshot_dir, ignore_errors=True)
