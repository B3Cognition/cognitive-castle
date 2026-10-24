"""Bounded safety-runner regression: a passing pytest must not leave a child.

Run directly, not inside safe_brain_tests (its serialization lock is intentional).
The only child workload is stdlib sleep; pytest itself runs under that guard.
"""

from pathlib import Path
import subprocess
import sys
import tempfile
import time
import textwrap

import psutil


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="castle-guard-proof-") as directory:
        path = Path(directory)
        marker = path / "owned-pid"
        test = path / "test_owned_cleanup.py"
        test.write_text(
            "import subprocess, sys\nfrom pathlib import Path\n"
            "def test_leave_bounded_owned_child():\n"
            "    child = subprocess.Popen([sys.executable, '-I', '-S', '-c', 'import time; time.sleep(10)'])\n"
            f"    Path({str(marker)!r}).write_text(str(child.pid))\n"
            "    assert child.poll() is None\n"
        )
        result = subprocess.run(
            [
                sys.executable,
                str(root / "scripts/safe_brain_tests.py"),
                "--timeout",
                "5",
                str(test),
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        pid = int(marker.read_text())
        try:
            child = psutil.Process(pid)
            for _ in range(20):
                if not child.is_running() or child.status() == psutil.STATUS_ZOMBIE:
                    break
                time.sleep(0.025)
            else:
                child.kill()  # Only this fixture's just-created process.
                raise AssertionError("guard left its owned child alive after pytest exit")
        except psutil.NoSuchProcess:
            pass
        print("PASS: passing pytest exited and its owned descendant was terminated")
        orphan_code = textwrap.dedent(f"""\
            import os, time
            from pathlib import Path
            if os.fork() == 0:
                Path({str(marker)!r}).write_text(str(os.getpid()))
                allocation = bytearray(48 * 1024 * 1024)
                for offset in range(0, len(allocation), 4096):
                    allocation[offset] = 1
                time.sleep(5)
            else:
                os._exit(0)
            """)
        test.write_text(
            "import subprocess, sys, time\n"
            "def test_owned_orphan_counts_toward_rss():\n"
            f"    subprocess.run([sys.executable, '-I', '-S', '-c', {orphan_code!r}], check=True)\n"
            "    time.sleep(3)\n"
        )
        result = subprocess.run(
            [
                sys.executable,
                str(root / "scripts/safe_brain_tests.py"),
                "--timeout",
                "5",
                "--rss-mib",
                "64",
                str(test),
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 125 and "aggregate RSS limit" in result.stdout, (
            result.stdout + result.stderr
        )
        try:
            child = psutil.Process(int(marker.read_text()))
            assert not child.is_running() or child.status() == psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            pass
        print("PASS: reparented owned descendant counted toward the aggregate RSS tripwire")


if __name__ == "__main__":
    main()
