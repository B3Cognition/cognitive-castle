"""Regression checks for the CI process supervisor, without running models."""

import os
from pathlib import Path
import re
import subprocess
import sys
import time

import psutil
import pytest


# Copy this file to tests/ and the supervisor to scripts/ in the repository.
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_ci_pytest.py"
if not SCRIPT.is_file():
    SCRIPT = Path(__file__).with_name("run_ci_pytest.py")


def run_fixture(tmp_path, code, *, timeout=3):
    fixture = tmp_path / "pytest.py"
    fixture.write_text(code, encoding="utf-8")
    log = tmp_path / "pytest.log"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--timeout",
            str(timeout),
            "--log",
            str(log),
            "--",
            "fixture-argument",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        timeout=20,
    )
    return result, log.read_bytes()


@pytest.mark.parametrize("status", [0, 7])
def test_preserves_pytest_status_and_streams_both_output_channels(tmp_path, status):
    result, log = run_fixture(
        tmp_path,
        f"""
import sys
assert sys.argv[1:] == ['fixture-argument']
print('stdout evidence', flush=True)
print('stderr evidence', file=sys.stderr, flush=True)
raise SystemExit({status})
""",
    )
    assert result.returncode == status
    assert b"stdout evidence" in result.stdout and b"stderr evidence" in result.stdout
    assert result.stdout == log


def test_deadline_stops_hung_pytest_and_its_descendant(tmp_path):
    started = time.monotonic()
    result, log = run_fixture(
        tmp_path,
        """
import subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
print(f'descendant={child.pid}', flush=True)
time.sleep(60)
""",
        timeout=1,
    )
    assert result.returncode == 124
    assert time.monotonic() - started < 15
    assert b"WALL-CLOCK DEADLINE EXCEEDED" in log
    assert result.stdout == log
    pid = int(re.search(rb"descendant=(\d+)", log).group(1))
    try:
        child = psutil.Process(pid)
        assert not child.is_running() or child.status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        pass


def test_undrained_stdout_cannot_block_deadline_or_retained_output(tmp_path):
    payload = b"complete output evidence\n" * 65536
    (tmp_path / "pytest.py").write_text(
        "import sys, time\n"
        "sys.stdout.buffer.write(b'complete output evidence\\n' * 65536)\n"
        "sys.stdout.buffer.flush()\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    log = tmp_path / "pytest.log"
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), "--timeout", "2", "--log", str(log)],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    started = time.monotonic()
    try:
        # Deliberately do not drain the external stdout pipe before exit.
        assert proc.wait(timeout=8) == 124
        assert time.monotonic() - started < 8
        retained = log.read_bytes()
        assert payload in retained
        assert b"WALL-CLOCK DEADLINE EXCEEDED" in retained
        assert b"supervisor exit=124" in retained
        pid = int(re.search(rb"pytest PID=(\d+)", retained).group(1))
        try:
            child = psutil.Process(pid)
            assert not child.is_running() or child.status() == psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            pass
    finally:
        if proc.poll() is None:
            for child in reversed(psutil.Process(proc.pid).children(recursive=True)):
                try:
                    child.kill()
                except psutil.Error:
                    pass
            proc.kill()
        proc.communicate(timeout=5)


@pytest.mark.skipif(os.name == "nt", reason="POSIX separate-session escape path")
def test_deadline_also_stops_descendant_in_separate_session(tmp_path):
    result, log = run_fixture(
        tmp_path,
        """
import subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
print(f'descendant={child.pid}', flush=True)
time.sleep(60)
""",
        timeout=1,
    )
    assert result.returncode == 124
    pid = int(re.search(rb"descendant=(\d+)", log).group(1))
    try:
        child = psutil.Process(pid)
        assert not child.is_running() or child.status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        pass
