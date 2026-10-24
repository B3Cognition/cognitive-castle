"""Storage workers reject hostile frames and paths before mutation."""

import json
import os
import subprocess
import sys

import pytest

from test_semantic_queue import ROOT, invoke, registration
from test_lance_vector_store import fixture, publication


def test_unsupervised_unknown_duplicate_and_oversized_frames_create_nothing(tmp_path):
    directory = tmp_path / "absent"
    valid = {
        "directory": str(directory),
        "operation": "queue_register",
        "arguments": registration(),
        "_host_pid": os.getpid(),
    }
    frames = [
        json.dumps(valid),
        '{"operation":"queue_status","operation":"vector_publish"}',
        json.dumps({"operation": "__getattribute__"}),
        "x" * (512 * 1024 + 1),
    ]
    for frame in frames:
        result = subprocess.run(
            [sys.executable, "-I", str(ROOT / "cognitive_castle/semantic_store_worker.py")],
            input=frame,
            text=True,
            capture_output=True,
            timeout=3,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["status"] == "unavailable"
        assert not directory.exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="owned guardian supervision")
def test_worker_guards_native_phase_denies_models_network_and_children(tmp_path):
    assert fixture(tmp_path, "guards") == {
        "status": "ok",
        "denied": [
            "pandas",
            "torch",
            "onnxruntime",
            "tokenizers",
            "requests",
            "lancedb",
            "network",
            "child",
        ],
    }


@pytest.mark.skipif(sys.platform != "darwin", reason="owned guardian supervision")
@pytest.mark.parametrize(
    "kind",
    [
        "generation_symlink",
        "generation_public",
        "coordination_symlink",
        "queue_hardlink",
        "queue_public",
    ],
)
def test_queue_unsafe_private_paths_refuse(tmp_path, kind):
    directory = tmp_path / "generation"
    directory.mkdir(mode=0o700)
    if kind == "generation_symlink":
        link = tmp_path / "link"
        link.symlink_to(directory)
        directory = link
    elif kind == "generation_public":
        directory.chmod(0o755)
    elif kind == "coordination_symlink":
        (directory / "coordination").symlink_to(tmp_path)
    else:
        assert invoke(directory, "queue_register", registration())["status"] == "ok"
        database = directory / "coordination" / "queue.sqlite3"
        if kind == "queue_hardlink":
            os.link(database, tmp_path / "hardlink")
        else:
            database.chmod(0o644)
    assert invoke(directory, "queue_register", registration())["status"] == "unavailable"


@pytest.mark.skipif(sys.platform != "darwin", reason="owned guardian supervision")
def test_vector_readonly_lock_and_mutation_free_reads(tmp_path):
    import fcntl

    directory = tmp_path / "generation"
    directory.mkdir(mode=0o700)
    assert invoke(directory, "vector_receipt", {"batch_key": "batch", "start_window": 0}) == {
        "status": "not_initialized"
    }
    assert list(directory.iterdir()) == []
    args, source = publication()
    assert fixture(directory, "seed", sources=[source])["status"] == "ok"
    first = invoke(directory, "vector_publish", args)
    assert first["status"] == "ok"
    with (directory / "vectors" / ".write.lock").open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert invoke(directory, "vector_publish", args) == {"status": "busy"}
        before = {
            str(path): (path.stat().st_size, path.stat().st_mtime_ns, path.stat().st_mode)
            for path in directory.rglob("*")
        }
        assert (
            invoke(directory, "vector_receipt", {"batch_key": "batch", "start_window": 0}) == first
        )
        after = {
            str(path): (path.stat().st_size, path.stat().st_mtime_ns, path.stat().st_mode)
            for path in directory.rglob("*")
        }
        assert before == after


@pytest.mark.skipif(sys.platform != "darwin", reason="owned guardian supervision")
def test_queue_phase_denies_native_imports_and_guardian_reaps_owned_group(tmp_path):
    import psutil

    result = fixture(tmp_path, "guards", phase="queue")
    assert result["denied"] == [
        "pandas",
        "torch",
        "onnxruntime",
        "tokenizers",
        "requests",
        "lancedb",
        "lance",
        "pyarrow",
        "numpy",
        "network",
        "child",
    ]
    result = fixture(tmp_path, "cleanup", phase="queue")
    assert result["status"] == "ok"
    assert not psutil.pid_exists(result["worker_pid"])
    assert not psutil.pid_exists(result["group_pid"])


@pytest.mark.skipif(sys.platform != "darwin", reason="owned guardian supervision")
@pytest.mark.parametrize(
    "kind", ["vectors_public", "lock_symlink", "artifact_hardlink", "artifact_symlink"]
)
def test_vector_private_native_artifact_boundaries(tmp_path, kind):
    directory = tmp_path / "generation"
    directory.mkdir(mode=0o700)
    args, source = publication()
    assert fixture(directory, "seed", sources=[source])["status"] == "ok"
    assert invoke(directory, "vector_publish", args)["status"] == "ok"
    vectors = directory / "vectors"
    if kind == "vectors_public":
        vectors.chmod(0o755)
    elif kind == "lock_symlink":
        (vectors / ".write.lock").unlink()
        (vectors / ".write.lock").symlink_to(tmp_path / "outside")
    else:
        artifact = next(path for path in (vectors / "units.lance").rglob("*") if path.is_file())
        if kind == "artifact_hardlink":
            os.link(artifact, tmp_path / "linked")
        else:
            (vectors / "units.lance" / "outside").symlink_to(tmp_path)
    assert (
        invoke(directory, "vector_receipt", {"batch_key": "batch", "start_window": 0})["status"]
        == "unavailable"
    )
