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


def _pressure_ok():
    """Fail closed if the supported OS cannot report normal memory pressure."""
    if sys.platform != "darwin":
        return False
    try:
        value = subprocess.check_output(
            ["/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level"],
            stderr=subprocess.DEVNULL,
            timeout=0.5,
        )
        return value.strip() == b"1"
    except (OSError, subprocess.SubprocessError):
        return False


def _owned_group_members(group_id):
    """Enumerate the retained process group, including reparented descendants.

    Its session leader stays alive or unreaped throughout supervision, so the
    numeric group identity cannot be reused by an unrelated new process group.
    Process objects also retain start identity for psutil's checked signalling.
    """
    import psutil

    for member in psutil.process_iter():
        # macOS exposes kernel PID0; getpgid(0) means *our* group, not PID0.
        if member.pid == 0:
            continue
        try:
            if os.getpgid(member.pid) == group_id:
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


class _PressureUnavailable(Exception):
    pass


def main():
    import psutil

    selector = selectors.DefaultSelector()
    selector.register(sys.stdin.buffer, selectors.EVENT_READ, "host")
    config_bytes = bytearray()
    started = time.monotonic()
    child = None
    config = None
    try:
        # Even an incomplete first IPC frame has a deadline.
        while b"\n" not in config_bytes:
            if time.monotonic() - started > 1:
                return
            for key, _ in selector.select(0.025):
                chunk = os.read(key.fd, 16384)
                if not chunk or len(config_bytes) + len(chunk) > 16384:
                    return
                config_bytes.extend(chunk)
        config = json.loads(config_bytes)
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
        child.stdin.write(json.dumps(config["request"]).encode())
        child.stdin.close()
        selector.register(child.stdout, selectors.EVENT_READ, "reader")
        output = bytearray()
        output_done = False
        while time.monotonic() - started < config["deadline"]:
            if time.monotonic() >= next_pressure_check:
                if not _pressure_ok():
                    raise _PressureUnavailable
                next_pressure_check = time.monotonic() + 0.25
            for key, _ in selector.select(0.025):
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
                        return
            if _group_rss(os.getpgrp()) > config["rss_limit"]:
                return
            # Reaping the child cannot recycle the guardian's process-group ID.
            if output_done and child.poll() is not None:
                if child.returncode == 0:
                    sys.stdout.buffer.write(output)
                    sys.stdout.buffer.flush()
                return
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
