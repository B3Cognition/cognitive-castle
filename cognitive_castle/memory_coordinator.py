"""Short-lived operator capture orchestration; hooks persist metadata then return.

The atomic spool is independent of worker admission: refusal cannot lose an event.
Only registered original roots are accepted. Nothing here imports legacy mining.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "cognitive_castle"

from .bounded_json import strict_loads
from .memory_runtime import run_memory

MAX_METADATA = 16384
MAX_SPOOL_SCAN = 8192


def _directory(palace, create=False):
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("Private capture unsupported")
    palace = Path(palace).expanduser().absolute()
    directory = palace / ".memory"
    if not palace.is_dir() or ".." in palace.parts:
        raise ValueError("Invalid palace")
    if any(path.is_symlink() for path in (directory, *directory.parents)):
        raise ValueError("Symlink capture directory")
    if create:
        directory.mkdir(mode=0o700, exist_ok=True)
    if directory.exists():
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("Capture directory must be owner-private")
    return directory


def _read(path, default):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return default
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
            or info.st_size > MAX_METADATA
        ):
            raise ValueError("Unsafe capture metadata")
        return strict_loads(stream.read(MAX_METADATA + 1), max_bytes=MAX_METADATA)


def _atomic(path, value):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
    if len(raw) > MAX_METADATA:
        raise ValueError("Capture metadata limit")
    fd, temporary = tempfile.mkstemp(prefix=".capture-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _config(palace):
    value = _read(_directory(palace) / "capture.json", {"version": 1, "enabled": False})
    if (
        not isinstance(value, dict)
        or value.get("version") != 1
        or type(value.get("enabled")) is not bool
    ):
        raise ValueError("Invalid capture configuration")
    return value


def configure_capture(palace, *, enabled):
    """Operator-only enable/pause; the legacy capture marker is independent."""
    if type(enabled) is not bool:
        raise ValueError("enabled must be boolean")
    directory = _directory(palace, True)
    if enabled:
        from .brain_api import _root_registry

        if not _root_registry(palace):
            raise ValueError("Register an original root before enabling capture")
    value = dict(version=1, enabled=enabled, updated_at_ns=time.time_ns())
    _atomic(directory / "capture.json", value)
    return {"status": "ok", **value}


def _coordinator_lock(palace):
    directory = _directory(palace, True)
    import fcntl

    fd = os.open(directory / "capture.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
        ):
            raise ValueError("Unsafe capture lock")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _registered_root(palace, source, format):
    from .brain_api import _root_registry

    source = Path(source).absolute()
    if ".." in source.parts or len(str(source).encode()) > 2048:
        raise ValueError("Invalid capture source path")
    candidates = [
        entry
        for entry in _root_registry(palace).values()
        if entry["format"] == format and source.is_relative_to(Path(entry["path"]))
    ]
    if not candidates:
        raise ValueError("Capture source outside matching registered roots")
    return max(candidates, key=lambda item: len(item["path"]))


def _event(palace, transcript_path, cwd, format):
    source = Path(transcript_path).expanduser().absolute()
    workspace = str(Path(cwd).expanduser().absolute()) if cwd is not None else None
    if (
        ".." in source.parts
        or len(str(source).encode()) > 2048
        or any(path.is_symlink() for path in (source, *source.parents))
        or not source.is_file()
        or source.suffix != ".jsonl"
    ):
        raise ValueError("Capture requires an original JSONL file")
    if workspace is not None and (".." in Path(workspace).parts or len(workspace.encode()) > 2048):
        raise ValueError("Invalid capture workspace")
    entry = _registered_root(palace, source, format)
    info = source.stat()
    return dict(
        path=str(source),
        allowed_root=entry["path"],
        format=format,
        workspace=workspace,
        observed_size=info.st_size,
        observed_mtime_ns=info.st_mtime_ns,
        event_at_ns=time.time_ns(),
    )


def _spool(directory, create=False):
    path = directory / "capture-spool"
    if create:
        path.mkdir(mode=0o700, exist_ok=True)
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("Unsafe capture spool")
    return path


def _spool_page(directory, after="", limit=16):
    path = _spool(directory)
    if not path.exists():
        return [], False
    names, more, started = [], False, time.monotonic()
    with os.scandir(path) as entries:
        for count, entry in enumerate(entries):
            if count >= MAX_SPOOL_SCAN or time.monotonic() - started > 0.1:
                raise ValueError("capture_spool_scan_limit")
            if not entry.name.endswith((".json", ".claimed")) or entry.name <= after:
                continue
            bisect.insort(names, entry.name)
            if len(names) > limit:
                names.pop()
                more = True
    return [path / name for name in names], more


def _launch(palace):
    try:
        fd = _coordinator_lock(palace)
    except BlockingIOError:
        return {"status": "unavailable", "reason": "coordinator_busy"}
    try:
        # The inherited flock bridges launch and child startup; competing hooks
        # never create another active coordinator. No wait occurs in the hook.
        subprocess.Popen(
            [
                sys.executable,
                "-I",
                str(Path(__file__).absolute()),
                str(Path(palace).absolute()),
                str(fd),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=(fd,),
            start_new_session=True,
        )
        return {"status": "scheduled"}
    except OSError:
        return {"status": "unavailable", "reason": "coordinator_launch_failed"}
    finally:
        os.close(fd)


def handle_capture_event(palace, transcript_path, cwd, format):
    """Persist one authorized original's metadata and schedule bounded catch-up."""
    if not _config(palace)["enabled"]:
        return {"status": "paused", "queued": False}
    event = _event(palace, transcript_path, cwd, format)
    directory = _directory(palace, True)
    spool = _spool(directory, True)
    key = hashlib.sha256((event["path"] + "\0" + format).encode()).hexdigest()
    _atomic(spool / (key + ".json"), event)
    return {"status": "ok", "queued": True, "source_key": key, "catch_up": _launch(palace)}


def capture_status(palace):
    """Private configuration, bounded spool count and worker coverage; no text."""
    config = _config(palace)
    directory = _directory(palace)
    spool = _spool(directory)
    count, complete = 0, True
    if spool.exists():
        started = time.monotonic()
        with os.scandir(spool) as entries:
            for seen, entry in enumerate(entries):
                if seen >= MAX_SPOOL_SCAN or time.monotonic() - started > 0.1:
                    complete = False
                    break
                count += entry.name.endswith((".json", ".claimed"))
    result = dict(
        status="ok",
        enabled=config["enabled"],
        spooled_events=count,
        spool_count_complete=complete,
        last_tick=_read(directory / "capture-last.json", None),
    )
    result["coverage"] = run_memory(palace, "coverage", {})
    result["discovery"] = run_memory(palace, "discovery_status", {})
    if result["discovery"]["status"] == "ok":
        from .brain_api import _root_registry

        roots = _root_registry(palace) if directory.exists() else {}
        observed = {(item["path"], item["format"]): item for item in result["discovery"]["roots"]}
        registered = []
        for name, entry in sorted(roots.items()):
            observation = observed.get((entry["path"], entry["format"]))
            registered.append(
                {
                    "name": name,
                    **(observation or {"discovery": "not_started", "completed_sweeps": 0}),
                }
            )
        result["discovery"]["roots"] = registered
        result["discovery"]["coverage"] = (
            "complete_at_last_sweep"
            if registered
            and all(item["discovery"] == "complete_at_last_sweep" for item in registered)
            else "incomplete"
            if registered
            else "no_registered_roots"
        )
    return result


def capture_tick(palace, *, max_seconds=5, discover=True):
    """One bounded fair pass; pending tails/errors are retried on a later tick."""
    if (
        type(max_seconds) not in (int, float)
        or not math.isfinite(max_seconds)
        or not 0 < max_seconds <= 30
        or type(discover) is not bool
    ):
        raise ValueError("capture tick requires 0 < max_seconds <= 30")
    if not _config(palace)["enabled"]:
        return {"status": "paused"}
    try:
        fd = _coordinator_lock(palace)
    except BlockingIOError:
        return {"status": "unavailable", "reason": "coordinator_busy"}
    try:
        return _tick(palace, max_seconds=max_seconds, discover=discover)
    finally:
        os.close(fd)


def _drain_spool(palace, directory, state, result, run):
    try:
        paths, more = _spool_page(directory, state.get("spool_after", ""))
        if not paths and state.get("spool_after"):
            paths, more = _spool_page(directory)
    except ValueError as exc:
        return {"status": "unavailable", "reason": str(exc)}
    for path in paths:
        if not path.exists():
            continue
        # Claim before reading. Hooks publish only .json, so acknowledgement can
        # never unlink an event arriving between a stat check and unlink. A crash
        # leaves .claimed metadata for the next invocation to resume.
        claimed = path.with_suffix(".claimed")
        if path != claimed:
            os.replace(path, claimed)
        try:
            event = _read(claimed, None)
            validated = _event(palace, event["path"], event.get("workspace"), event["format"])
        except (ValueError, OSError, TypeError, KeyError):
            result["spool_errors"] += 1
            result["failed_sources"] += 1
            state["spool_after"] = path.name
            continue
        arguments = {key: validated[key] for key in ("path", "allowed_root", "format", "workspace")}
        queued = run("queue_source", arguments)
        if queued["status"] != "ok":
            return queued
        result["queued_sources"] += 1
        claimed.unlink()
        state["spool_after"] = path.name
    if not more:
        state["spool_after"] = ""
    return None


def _tick(palace, *, max_seconds=5, discover=True):
    from .brain_api import _root_registry

    started = time.monotonic()
    directory = _directory(palace, True)
    try:
        state = _read(directory / "capture-progress.json", {})
        if (
            not isinstance(state, dict)
            or state.keys() - {"source_after", "spool_after", "root_index"}
            or any(
                not isinstance(state.get(key, ""), str) or len(state.get(key, "")) > 128
                for key in ("source_after", "spool_after")
            )
            or type(state.get("root_index", 0)) is not int
            or not 0 <= state.get("root_index", 0) < 8
        ):
            raise ValueError("invalid progress")
    except (ValueError, OSError, TypeError):
        failure = {"status": "unavailable", "reason": "invalid_capture_progress"}
        _atomic(directory / "capture-last.json", failure)
        return failure
    result = dict(
        status="ok",
        queued_sources=0,
        successful_slices=0,
        failed_sources=0,
        spool_errors=0,
        unauthorized_sources=0,
        discovery="not_run",
        discovery_scope="one_registered_root",
        source_currentness="last_observed_only",
    )

    def run(operation, arguments):
        remaining = max_seconds - (time.monotonic() - started)
        if remaining <= 0.02:
            return {"status": "unavailable", "reason": "capture_deadline"}
        if not _config(palace)["enabled"]:
            return {"status": "paused", "reason": "capture_paused"}
        return run_memory(palace, operation, arguments, max_seconds=remaining)

    def finish(failure=None):
        if failure is not None:
            result.update(status=failure["status"], reason=failure.get("reason", failure["status"]))
        result["elapsed_seconds"] = round(time.monotonic() - started, 4)
        result["finished_at_ns"] = time.time_ns()
        _atomic(directory / "capture-progress.json", state)
        _atomic(directory / "capture-last.json", result)
        return result

    refusal = _drain_spool(palace, directory, state, result, run)
    if refusal is not None:
        return finish(refusal)
    if discover:
        roots = sorted(_root_registry(palace).items())
        if roots:
            index = int(state.get("root_index", 0)) % len(roots)
            result["discovery_root"] = roots[index][0]
            entry = roots[index][1]
            discovered = run(
                "discover_sources", dict(allowed_root=entry["path"], format=entry["format"])
            )
            state["root_index"] = (index + 1) % len(roots)
            if discovered["status"] != "ok":
                return finish(discovered)
            result["discovery"] = discovered["discovery"]
            if discovered.get("reason"):
                result["discovery_reason"] = discovered["reason"]
            result["queued_sources"] += discovered["queued_sources"]
    page = run(
        "source_page", dict(after=state.get("source_after", ""), limit=16, pending_only=True)
    )
    if page["status"] != "ok":
        return finish(page)
    if not page["sources"] and state.get("source_after"):
        state["source_after"] = ""
        page = run("source_page", dict(limit=16, pending_only=True))
        if page["status"] != "ok":
            return finish(page)
    for source in page["sources"]:
        try:
            # Persisted queue entries are observations, never lasting authority.
            _registered_root(palace, source["path"], source["format"])
        except (ValueError, OSError, TypeError, KeyError):
            result["unauthorized_sources"] += 1
            result["failed_sources"] += 1
            state["source_after"] = source["source_key"]
            continue
        value = run("capture_one", dict(key=source["source_key"]))
        state["source_after"] = source["source_key"]
        if value["status"] != "ok":
            result["failed_sources"] += 1
            if value.get("reason") != "source_unavailable":
                return finish(value)
        else:
            result["successful_slices"] += 1
    if page["next_after"] is None:
        state["source_after"] = ""
    return finish()


def main():
    palace, inherited = sys.argv[1], int(sys.argv[2])
    try:
        if _config(palace)["enabled"]:
            _tick(palace, max_seconds=5, discover=False)
    finally:
        os.close(inherited)


if __name__ == "__main__":
    main()
