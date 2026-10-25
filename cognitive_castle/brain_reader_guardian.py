"""Stdlib/psutil-only guardian; native packages are imported by its child only."""

from __future__ import annotations

import json
import os
import selectors
import shutil
import signal
import subprocess
import sys
import time


def _pressure_ok(*, deadline=None):
    """Fail closed if the supported OS cannot report normal memory pressure."""
    if sys.platform != "darwin":
        return False
    timeout = 0.5 if deadline is None else min(0.5, deadline - time.monotonic())
    if timeout <= 0:
        return False
    try:
        value = subprocess.check_output(
            ["/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level"],
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
        return (deadline is None or time.monotonic() < deadline) and value.strip() == b"1"
    except (OSError, subprocess.SubprocessError):
        return False


def _owned_group_members(group_id):
    """Enumerate the retained process group, including reparented descendants.

    Its session leader stays alive or unreaped throughout supervision, so the
    numeric group identity cannot be reused by an unrelated new process group.
    Process objects also retain start identity for psutil's checked signalling.
    """
    import psutil

    for pid in psutil.pids():
        # macOS exposes kernel PID0; getpgid(0) means *our* group, not PID0.
        if pid == 0:
            continue
        try:
            if os.getpgid(pid) != group_id:
                continue
            member = psutil.Process(pid)
            # A PID can be reused between filtering and identity capture.
            # Check the captured process still belongs to our retained group.
            if os.getpgid(pid) == group_id:
                yield member
        except (ProcessLookupError, psutil.NoSuchProcess):
            pass


def _group_rss(group_id):
    import psutil

    rss = 0
    for member in _owned_group_members(group_id):
        try:
            rss += member.memory_info().rss
        except psutil.NoSuchProcess:
            pass
    return rss


def _write_ready(selector, stream, pending, *, close=False):
    """Advance one nonblocking IPC write without leaving supervision."""
    try:
        written = os.write(stream.fileno(), pending[:65536])
    except BlockingIOError:
        return pending
    pending = pending[written:]
    if not pending:
        selector.unregister(stream)
        if close:
            stream.close()
    return pending


def _resource_reason(config):
    """Account guardian and owned descendants, plus an optional trusted host."""
    import psutil

    group_rss = _group_rss(os.getpgrp())
    if group_rss > config["rss_limit"]:
        return "worker_memory_limit"
    if "total_rss_limit" in config:
        parent_rss = psutil.Process(config["parent_pid"]).memory_info().rss
        if group_rss + parent_rss > config["total_rss_limit"]:
            return "total_memory_limit"
    return None


class _PressureUnavailable(Exception):
    pass


def _read_config(selector, started):
    """Receive a bounded first frame while retaining its one-second deadline."""
    frame = bytearray()
    while b"\n" not in frame:
        if time.monotonic() - started > 1:
            return None
        for key, _ in selector.select(0.025):
            chunk = os.read(key.fd, 16384)
            if not chunk or len(frame) + len(chunk) > 512 * 1024:
                return None
            frame.extend(chunk)
    return json.loads(frame)


def main():
    import psutil

    selector = selectors.DefaultSelector()
    selector.register(sys.stdin.buffer, selectors.EVENT_READ, "host")
    started = time.monotonic()
    child = None
    config = None

    def unavailable(reason):
        if config and "total_rss_limit" in config:
            sys.stdout.write(json.dumps({"status": "unavailable", "reason": reason}))
            sys.stdout.flush()

    try:
        config = _read_config(selector, started)
        if config is None:
            return
        if not _pressure_ok():
            raise _PressureUnavailable
        next_pressure_check = time.monotonic() + 0.25
        child = subprocess.Popen(
            config["command"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            pass_fds=(config["admission"],),
        )
        pending = memoryview(json.dumps(config["request"]).encode())
        os.set_blocking(child.stdin.fileno(), False)
        selector.register(child.stdin, selectors.EVENT_WRITE, "request")
        selector.register(child.stdout, selectors.EVENT_READ, "reader")
        output = bytearray()
        output_done = False
        while time.monotonic() - started < config["deadline"]:
            if time.monotonic() >= next_pressure_check:
                if not _pressure_ok():
                    raise _PressureUnavailable
                next_pressure_check = time.monotonic() + 0.25
            for key, _ in selector.select(0.025):
                if key.data == "request":
                    pending = _write_ready(selector, child.stdin, pending, close=True)
                    continue
                chunk = os.read(key.fd, 65536)
                if key.data == "host":
                    if not chunk:  # Host died; no orphaned native reader.
                        return
                elif not chunk:
                    output_done = True
                    selector.unregister(child.stdout)
                else:
                    output.extend(chunk)
                    if len(output) > config["max_frame"]:
                        unavailable("worker_output_limit")
                        return
            reason = _resource_reason(config)
            if reason:
                unavailable(reason)
                return
            # Reaping the child cannot recycle the guardian's process-group ID.
            if output_done and child.poll() is not None:
                if child.returncode == 0:
                    sys.stdout.buffer.write(output)
                    sys.stdout.buffer.flush()
                return
        unavailable("worker_deadline")
    except _PressureUnavailable:
        sys.stdout.write(
            json.dumps({"status": "unavailable", "reason": "system_pressure_unavailable"})
        )
        sys.stdout.flush()
    except Exception as exc:
        sys.stdout.write(
            json.dumps({"status": "unavailable", "reason": "guardian_" + type(exc).__name__})
        )
        sys.stdout.flush()
    finally:
        selector.close()
        try:
            # psutil checks start identity before signalling reused PIDs.
            for member in _owned_group_members(os.getpgrp()):
                if member.pid == os.getpid():
                    continue
                try:
                    member.kill()
                except psutil.NoSuchProcess:
                    pass
            if config is not None:
                shutil.rmtree(config["request"].get("snapshot_dir", ""), ignore_errors=True)
        finally:
            # Kill every member of our owned group even if cleanup failed.
            # The kernel closes admission only when its last owner exits.
            os.killpg(os.getpgrp(), signal.SIGKILL)


if __name__ == "__main__":
    main()
