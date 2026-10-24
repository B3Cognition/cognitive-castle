"""Durable coordination, using supervised workers without native dependencies."""

import copy
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCOPE = {"workspace": "/trusted/full/workspace", "wing": "wing", "room": "room"}
REFS = [
    {
        "canonical_id": "memory:" + "a" * 64,
        "source_hash": "b" * 64,
        "exposure_hash": "c" * 64,
        "scope": SCOPE,
    }
]


def invoke(directory, operation, arguments=None):
    from cognitive_castle import memory_runtime as runtime

    admission = runtime._admission()
    try:
        result = runtime._supervise(
            {"directory": str(directory), "operation": operation, "arguments": arguments or {}},
            admission,
            worker_command=[
                sys.executable,
                "-I",
                str(ROOT / "cognitive_castle/semantic_store_worker.py"),
            ],
            deadline=2 if operation in {"queue_status", "vector_receipt", "vector_nearest"} else 3,
            rss_limit=(128 if operation.startswith("queue_") else 192) * 1024**2,
            total_rss_limit=(192 if operation.startswith("queue_") else 256) * 1024**2,
        )
    finally:
        os.close(admission)
    assert result.get("reason") not in {
        "worker_memory_limit",
        "total_memory_limit",
        "parent_memory_limit",
        "system_pressure_unavailable",
        "worker_deadline",
    }, result
    return {key: value for key, value in result.items() if key != "resources"}


def registration(key="one", lane="new"):
    from cognitive_castle.semantic_profile import PROFILE_ID

    return {
        "batch_key": key,
        "references": copy.deepcopy(REFS),
        "profile": PROFILE_ID,
        "input_binding": "d" * 64,
        "lane": lane,
    }


def receipt(start=0, total=40, **changes):
    from cognitive_castle.semantic_profile import PROFILE_ID, digest

    count = min(32, total - start)
    result = {
        "status": "ok",
        "receipt_id": "vector-receipt:" + str(start // 32 + 1) * 64,
        "batch_key": "one",
        "profile": PROFILE_ID,
        "input_binding": "d" * 64,
        "reference_binding": digest(REFS),
        "start_window": start,
        "total_units": total,
        "count": count,
        "next_continuation": {"binding": "d" * 64, "next_window": start + count}
        if start + count < total
        else None,
        "unit_ids": ["e" * 64] * count,
        "vector_digests": ["f" * 64] * count,
    }
    result.update(changes)
    return result


def test_reference_contract_is_compact_strict_and_bounds_scope():
    from cognitive_castle.semantic_queue import validate_references, validate_scope

    assert validate_references(REFS) == REFS
    for value in [
        [],
        REFS * 9,
        [{**REFS[0], "text": "forbidden"}],
        [{**REFS[0], "source_hash": "B" * 64}],
    ]:
        with pytest.raises(ValueError):
            validate_references(value)
    for value in [
        {**SCOPE, "room": "x" * 513},
        {**SCOPE, "workspace": "😀" * 513},
        {"workspace": "short"},
    ]:
        with pytest.raises(ValueError):
            validate_scope(value)


@pytest.mark.skipif(sys.platform != "darwin", reason="owned guardian supervision")
def test_registration_restart_conflict_status_and_readonly(tmp_path):
    directory = tmp_path / "generation"
    directory.mkdir(mode=0o700)
    assert invoke(directory, "queue_status") == {"status": "not_initialized"}
    assert list(directory.iterdir()) == []
    first = invoke(directory, "queue_register", registration())
    assert first["status"] == "ok" and first["position"] == 0 and first["state"] == "pending"
    assert invoke(directory, "queue_register", registration()) == first
    changed = registration()
    changed["references"][0]["exposure_hash"] = "f" * 64
    assert invoke(directory, "queue_register", changed) == {"status": "conflict"}
    status = invoke(directory, "queue_status")
    assert status["counts"] == {"pending": 1, "inflight": 0, "complete": 0, "refused": 0}
    assert status["groups"][0]["position"] == 0
    raw = (directory / "coordination" / "queue.sqlite3").read_bytes()
    assert b"forbidden body" not in raw


@pytest.mark.skipif(sys.platform != "darwin", reason="owned guardian supervision")
def test_contiguous_ack_survives_restart_and_terminal_page_alone_refuses(tmp_path):
    directory = tmp_path / "generation"
    directory.mkdir(mode=0o700)
    assert invoke(directory, "queue_register", registration())["status"] == "ok"
    selected = invoke(directory, "queue_select")
    assert selected["group"]["position"] == 0
    assert invoke(directory, "queue_acknowledge", {"batch_key": "one", "receipt": receipt(32)}) == {
        "status": "conflict"
    }
    assert invoke(
        directory,
        "queue_acknowledge",
        {"batch_key": "one", "receipt": receipt(reference_binding="f" * 64)},
    ) == {"status": "conflict"}
    first = invoke(directory, "queue_acknowledge", {"batch_key": "one", "receipt": receipt()})
    assert first["position"] == 32 and first["state"] == "pending"
    assert (
        invoke(directory, "queue_acknowledge", {"batch_key": "one", "receipt": receipt()}) == first
    )
    assert invoke(
        directory, "queue_acknowledge", {"batch_key": "one", "receipt": receipt(32, 41)}
    ) == {"status": "conflict"}
    assert invoke(directory, "queue_select")["group"]["position"] == 32
    last = invoke(directory, "queue_acknowledge", {"batch_key": "one", "receipt": receipt(32)})
    assert last["position"] == 40 and last["state"] == "complete"
    assert invoke(directory, "queue_status")["counts"]["complete"] == 1


@pytest.mark.skipif(sys.platform != "darwin", reason="owned guardian supervision")
def test_fair_selection_persisted_and_inflight_replay_retry(tmp_path):
    directory = tmp_path / "generation"
    directory.mkdir(mode=0o700)
    for key, lane in [
        ("n1", "new"),
        ("n2", "new"),
        ("n3", "new"),
        ("n4", "new"),
        ("h1", "history"),
    ]:
        assert invoke(directory, "queue_register", registration(key, lane))["status"] == "ok"
    # An unavailable step retains its durable position and can be selected again.
    assert invoke(directory, "queue_select")["group"]["batch_key"] == "n1"
    assert (
        invoke(directory, "queue_retry", {"batch_key": "n1", "refused": True})["state"] == "refused"
    )
    assert invoke(directory, "queue_retry", {"batch_key": "n1"})["position"] == 0
    for key in ["n1", "n2", "h1", "n3"]:
        selected = invoke(directory, "queue_select")["group"]
        assert selected["batch_key"] == key
        assert (
            invoke(
                directory,
                "queue_acknowledge",
                {"batch_key": key, "receipt": receipt(0, 1, batch_key=key)},
            )["state"]
            == "complete"
        )
    assert invoke(directory, "queue_select")["group"]["batch_key"] == "n4"


def test_host_store_refuses_unsupervised_and_has_no_native_imports(tmp_path):
    from cognitive_castle.semantic_queue import SemanticQueue

    assert SemanticQueue(tmp_path, writable=True).register(**registration()) == {
        "status": "unavailable"
    }
    assert SemanticQueue(tmp_path).status() == {"status": "unavailable"}
    assert not {"lance", "pyarrow", "numpy", "pandas", "torch"}.intersection(sys.modules)
