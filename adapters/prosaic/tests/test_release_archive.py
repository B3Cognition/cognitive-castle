"""A source release must reproduce its checks without the parent checkout."""

from pathlib import Path
import subprocess
import sys
import tarfile


def test_adapter_sdist_contains_its_test_and_smoke_materials(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--no-isolation", "--outdir", str(tmp_path)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    archives = list(tmp_path.glob("*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0]) as archive:
        contents = {str(Path(name).relative_to(Path(name).parts[0])) for name in archive.getnames()}
    assert {
        "tests/conftest.py",
        "tests/test_native_snapshot.py",
        "examples/native_snapshot.py",
        "examples/prose/memory-reader.md",
        "scripts/wheel_smoke.py",
        "docs/verification-2026-10-23.md",
        "LICENSE",
        "NOTICE.md",
    } <= contents
