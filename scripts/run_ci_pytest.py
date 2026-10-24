"""Run pytest with a real wall-clock deadline and retained process diagnostics."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time


def _heartbeat(proc, note) -> None:
    try:
        import psutil

        parent = psutil.Process(proc.pid)
        records = []
        for item in [parent, *parent.children(recursive=True)]:
            try:
                cpu = item.cpu_times()
                records.append(
                    {
                        "pid": item.pid,
                        "ppid": item.ppid(),
                        "name": item.name(),
                        "status": item.status(),
                        "rss": item.memory_info().rss,
                        "cpu_seconds": round(cpu.user + cpu.system, 2),
                    }
                )
            except psutil.Error:
                continue
        note("processes=" + json.dumps(records, sort_keys=True))
    except Exception as exc:
        note(f"process diagnostics unavailable: {type(exc).__name__}")


def _terminate(proc, note, emit) -> None:
    # Tests can create their own sessions; retain process identities before
    # terminating the parent so those descendants cannot escape.
    descendants = []
    try:
        import psutil

        descendants = psutil.Process(proc.pid).children(recursive=True)
    except Exception as exc:
        note(f"descendant snapshot unavailable: {type(exc).__name__}")
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=10,
            )
            emit(result.stdout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            note(f"taskkill unavailable: {type(exc).__name__}")
    else:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if descendants:
        for child in reversed(descendants):
            try:
                child.terminate()
            except psutil.Error:
                pass
        _, alive = psutil.wait_procs(descendants, timeout=2)
        for child in alive:
            try:
                child.kill()
            except psutil.Error:
                pass
    if proc.poll() is None:
        proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        note("test process did not reap within the bounded cleanup interval")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    pytest_args = args.pytest_args
    if pytest_args[:1] == ["--"]:
        pytest_args = pytest_args[1:]
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    # A process-wide watchdog also covers module import, collection and teardown.
    bootstrap = (
        "import faulthandler, runpy; "
        "faulthandler.enable(); "
        "faulthandler.dump_traceback_later(60, repeat=True); "
        "runpy.run_module('pytest', run_name='__main__')"
    )
    command = [sys.executable, "-u", "-c", bootstrap, *pytest_args]
    options = (
        {"start_new_session": True}
        if os.name != "nt"
        else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    )
    started = time.monotonic()
    lock = threading.Lock()
    with args.log.open("wb") as log:

        def emit(data: bytes) -> None:
            with lock:
                log.write(data)
                log.flush()
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()

        def note(message: str) -> None:
            elapsed = time.monotonic() - started
            emit(f"\n[ci-supervisor {elapsed:.1f}s] {message}\n".encode())

        note(f"starting {command!r}; wall-clock deadline={args.timeout}s")
        proc = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **options
        )
        note(f"pytest PID={proc.pid}")

        def relay() -> None:
            try:
                while data := proc.stdout.read1(8192):
                    emit(data)
            except (OSError, ValueError):
                pass

        reader = threading.Thread(target=relay, daemon=True)
        reader.start()

        next_heartbeat = started + 30
        timed_out = False
        while proc.poll() is None:
            now = time.monotonic()
            if now >= started + args.timeout:
                timed_out = True
                note("WALL-CLOCK DEADLINE EXCEEDED; terminating owned test process tree")
                _heartbeat(proc, note)
                break
            if now >= next_heartbeat:
                _heartbeat(proc, note)
                next_heartbeat = now + 30
            time.sleep(min(0.1, max(0, started + args.timeout - now)))

        if timed_out:
            _terminate(proc, note, emit)

        reader.join(timeout=2)
        if reader.is_alive():
            note("output pipe remains open after test process exit")
        code = 124 if timed_out else proc.returncode
        note(f"pytest exit={proc.returncode}; supervisor exit={code}")
        return code


if __name__ == "__main__":
    raise SystemExit(main())
