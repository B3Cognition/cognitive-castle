#!/usr/bin/env python3
"""Serialize bounded, model/network-denying tests; never invoke the user's palace."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


def _sample_owned(leader, owned):
    import psutil

    for child in [leader, *leader.children(recursive=True)]:
        owned[child.pid] = child
    # Reparented descendants disappear from children(), but retain the owned
    # group. The unreaped leader reserves its group ID until final cleanup.
    for member in psutil.process_iter():
        try:
            if member.pid > 0 and os.getpgid(member.pid) == leader.pid:
                owned[member.pid] = member
        except (OSError, psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    rss = 0
    for child in owned.values():
        try:
            if child.is_running():
                rss += child.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return rss


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--rss-mib", type=int, default=700)
    parser.add_argument("tests", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.tests:
        parser.error("select explicit test files")
    import psutil
    import fcntl

    def pressure_ok():
        if sys.platform == "darwin":
            value = subprocess.check_output(
                ["sysctl", "-n", "kern.memorystatus_vm_pressure_level"], text=True, timeout=2
            )
            return int(value) == 1
        return psutil.virtual_memory().available >= 1024**3

    lock_path = Path(tempfile.gettempdir()) / f"castle-safe-tests-{os.getuid()}.lock"
    lock = lock_path.open("a")
    started_wait = time.monotonic()
    while True:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.monotonic() - started_wait > 180:
                raise SystemExit("another guarded test run still holds the lock")
            time.sleep(0.2)
    if not pressure_ok():
        raise SystemExit("tests not started: memory pressure is elevated")
    root = Path(__file__).resolve().parents[1]
    bootstrap = r"""
import importlib.abc, os, socket, sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv.pop(1))
class NoModels(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch','transformers','sentence_transformers','spacy','en_core_web_sm','Python_sml_ClientInterface','_Python_sml_ClientInterface'}:
            raise ImportError('safe_brain_tests forbids model dependency: '+fullname)
sys.meta_path.insert(0, NoModels())
# Optional backend discovery may ask about torch without importing it.
# Report unavailable for discovery; the import hook still forbids actual loads.
import importlib.util
_original_find_spec = importlib.util.find_spec
def _no_model_discovery(name, package=None):
    if name.split('.')[0] in {'torch','transformers','sentence_transformers','spacy','en_core_web_sm','Python_sml_ClientInterface','_Python_sml_ClientInterface'}:
        return None
    return _original_find_spec(name, package)
importlib.util.find_spec = _no_model_discovery
def no_network(*args, **kwargs):
    raise RuntimeError('safe_brain_tests forbids network calls')
socket.socket.connect = no_network
socket.create_connection = no_network
# conftest isolates storage again; this protects imports before its collection.
with tempfile.TemporaryDirectory(prefix='castle_brain_guard_') as isolated:
    for name in ('HOME','USERPROFILE','HF_HOME','XDG_CACHE_HOME'):
        os.environ[name] = isolated
    import pytest
    raise SystemExit(pytest.main(sys.argv[1:]+['-q','--disable-warnings']))
"""
    env = dict(os.environ)
    env.update(
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        TOKENIZERS_PARALLELISM="false",
    )
    proc = subprocess.Popen(
        [sys.executable, "-I", "-c", bootstrap, str(root), *args.tests],
        cwd=root,
        env=env,
        start_new_session=True,
    )
    leader = psutil.Process(proc.pid)
    owned = {}
    start = time.monotonic()
    peak = 0
    reason = None
    try:
        # Do not poll/reap the leader before killing its owned process group:
        # it may have exited while leaving an active test subprocess behind.
        while True:
            try:
                rss = _sample_owned(leader, owned)
            except psutil.NoSuchProcess:
                break
            peak = max(peak, rss)
            if rss > args.rss_mib * 1024**2:
                reason = "aggregate RSS limit"
            elif time.monotonic() - start > args.timeout:
                reason = "wall-clock deadline"
            elif not pressure_ok():
                reason = "elevated memory pressure"
            if reason:
                break
            if leader.status() == psutil.STATUS_ZOMBIE:
                break
            time.sleep(0.1)
    finally:
        # psutil retains process creation identity when killing observed nested
        # sessions; the unreaped leader reserves its own group identity below.
        for child in reversed(list(owned.values())):
            if child.pid != proc.pid:
                try:
                    child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass  # macOS may deny killpg for a group containing only zombies.
        proc.wait(timeout=2)
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
    print(
        f"[guard] sampled aggregate peak {peak / 1024**2:.1f} MiB; "
        f"{time.monotonic() - start:.1f}s; {reason or 'completed'}",
        flush=True,
    )
    return 125 if reason else proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
