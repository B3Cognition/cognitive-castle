"""Exact Lance qualification: native dependencies live only in supervised children."""

import hashlib
import json
import os
from pathlib import Path
import sys


def _fixture_main():
    # This explicit disposable fixture is not a production operation/command.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from cognitive_castle.lance_exact_worker import _install_guards, _admit_storage

    _install_guards()
    os.umask(0o077)
    request = json.load(sys.stdin)
    refusal = _admit_storage(request)
    if refusal:
        print(json.dumps(refusal))
        return
    from cognitive_castle.lance_exact_store import LanceExactStore

    directory = Path(request["directory"])
    store = LanceExactStore(directory, writable=True)
    action = request["fixture"]
    if action == "guards":
        denied = []
        for name in ("pandas", "torch", "requests", "lancedb", "cognitive_castle.backends"):
            try:
                __import__(name)
            except ModuleNotFoundError:
                denied.append(name)
        import socket
        import subprocess

        for name, attempt in (
            ("network", socket.socket),
            ("child", lambda: subprocess.Popen([sys.executable, "-c", "pass"])),
        ):
            try:
                attempt()
            except PermissionError:
                denied.append(name)
        readonly = LanceExactStore(directory).remember("x", "x")
        print(json.dumps({"status": "ok", "denied": denied, "readonly": readonly}))
        return
    import lance
    import pyarrow as pa

    if action == "lost_response":
        assert store.remember(**request["arguments"])["status"] == "ok"
        # Commit succeeded; deliberately emit no response before the child exits.
        return
    dataset = lance.dataset(str(directory / "records.lance"))
    if action == "count":
        print(json.dumps({"status": "ok", "rows": dataset.count_rows()}))
        return
    row = dataset.scanner(limit=1).to_table().to_pylist()[0]
    if action == "duplicate_record":
        pass
    elif action == "duplicate_receipt":
        row = dataset.scanner(filter="kind = 'receipt'", limit=1).to_table().to_pylist()[0]
    elif action == "bad_text":
        dataset.delete("id = '" + row["id"] + "'")
        row["text"] = "tampered"
    elif action == "missing_record":
        dataset.delete("id = '" + row["id"] + "'")
        print('{"status":"ok"}')
        return
    elif action == "bad_receipt":
        row = dataset.scanner(filter="kind = 'receipt'", limit=1).to_table().to_pylist()[0]
        dataset.delete("id = '" + row["id"] + "'")
        row["receipt"] = "{}"
    elif action == "bad_digest":
        row = dataset.scanner(filter="kind = 'receipt'", limit=1).to_table().to_pylist()[0]
        dataset.delete("id = '" + row["id"] + "'")
        row["digest"] = "0" * 64
    elif action == "bad_schema":
        lance.write_dataset(
            pa.table({"bad": ["schema"]}), str(directory / "records.lance"), mode="overwrite"
        )
        print('{"status":"ok"}')
        return
    else:
        raise ValueError(action)
    lance.write_dataset(
        pa.Table.from_pylist([row], schema=dataset.schema),
        str(directory / "records.lance"),
        mode="append",
    )
    print('{"status":"ok"}')


if __name__ == "__main__":
    _fixture_main()
    raise SystemExit(0)

import pytest  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS owned-group supervision")
ROOT = Path(__file__).resolve().parents[1]


def invoke(directory, operation=None, arguments=None, *, fixture=None):
    from cognitive_castle import memory_runtime as runtime

    request = {"directory": str(directory)}
    if fixture:
        request.update(fixture=fixture, arguments=arguments or {})
        worker = Path(__file__).resolve()
    else:
        request.update(operation=operation, arguments=arguments or {})
        worker = ROOT / "cognitive_castle" / "lance_exact_worker.py"
    # Coordinate with the existing live capture without weakening runtime guards.
    import time

    wait_until = time.monotonic() + 8
    while True:
        try:
            admission = runtime._admission()
            break
        except BlockingIOError:
            print("ADMISSION REFUSAL: global memory admission busy", flush=True)
            if time.monotonic() >= wait_until:
                pytest.fail("native fixture deferred: admission busy for 8 seconds")
            time.sleep(0.1)
    try:
        result = runtime._supervise(
            request,
            admission,
            worker_command=[sys.executable, "-I", str(worker)],
            deadline=3 if fixture or operation in {"remember", "import_sources"} else 2,
            rss_limit=192 * 1024**2,
            total_rss_limit=256 * 1024**2,
        )
    finally:
        os.close(admission)
    if result.get("reason") in {
        "worker_memory_limit",
        "total_memory_limit",
        "parent_memory_limit",
        "system_pressure_unavailable",
        "worker_deadline",
    }:
        pytest.fail("RESOURCE REFUSAL: " + json.dumps(result))
    return {key: value for key, value in result.items() if key != "resources"}


def remember(directory, text="exact ž😀\x00\r\n", **kwargs):
    return invoke(directory, "remember", {"request_id": "request", "text": text, **kwargs})


def test_create_append_reopen_replay_and_conflict(tmp_path):
    directory = tmp_path / "exact"
    first = remember(directory)
    assert first["status"] == "ok", first
    assert first["stored_text_bytes"] == 15
    assert first["text_sha256"] == hashlib.sha256("exact ž😀\x00\r\n".encode()).hexdigest()
    assert remember(directory) == first
    assert remember(directory, text="changed") == {"status": "conflict"}
    second = invoke(directory, "remember", {"request_id": "two", "text": "second"})
    assert second["status"] == "ok", second
    assert (
        invoke(directory, "read_sources", {"ids": first["ids"]})["sources"][0]["text"]
        == "exact ž😀\x00\r\n"
    )
    assert invoke(directory, fixture="count")["rows"] == 4


def test_unicode_nul_chunk_pages_and_hash_binding(tmp_path):
    directory = tmp_path / "exact"
    text = "😀" * 2048 + "ž\x00\r\ntail"
    result = remember(directory, text)
    assert result["status"] == "ok", result
    assert len(result["ids"]) == 2
    sources = invoke(directory, "read_sources", {"ids": result["ids"]})
    assert "".join(source["text"] for source in sources["sources"]) == text
    first, second = sources["sources"]
    assert first["provenance"]["chunk_end"] == second["provenance"]["chunk_start"] == 2048
    page = invoke(
        directory,
        "page",
        {
            "source_id": second["id"],
            "offset": 1,
            "limit": 3,
            "expected_hash": second["provenance"]["text_hash"],
        },
    )
    assert page["text"] == "\x00\r\n" and page["next_offset"] == 4 and not page["complete"]
    assert invoke(directory, "page", {"source_id": first["id"], "expected_hash": "0" * 64}) == {
        "status": "stale"
    }
    end = invoke(directory, "page", {"source_id": first["id"], "offset": 9999})
    assert end["text"] == "" and end["complete"] and end["next_offset"] == 2048


def test_commit_with_lost_response_replays_durable_receipt(tmp_path):
    directory = tmp_path / "exact"
    arguments = {"request_id": "request", "text": "survives lost response"}
    assert (
        invoke(directory, fixture="lost_response", arguments=arguments)["reason"]
        == "worker_invalid_frame"
    )
    receipt = invoke(directory, "remember", arguments)
    assert receipt["status"] == "ok", receipt
    assert invoke(directory, fixture="count")["rows"] == 2


def test_import_preserves_provenance_reuses_records_and_checks_replay(tmp_path):
    from cognitive_castle.canonical_records import prepare_remember

    directory = tmp_path / "exact"
    sources = [
        record.source()
        for record in prepare_remember(
            "prior", "original", {"source": "old", "nested": {"n": 1}}
        ).records
    ]
    sources[0]["provenance"]["historical_descriptor"] = "retain exactly"
    arguments = {"batch_id": "batch", "sources": sources}
    first = invoke(directory, "import_sources", arguments)
    assert first["status"] == "ok", first
    assert invoke(directory, "import_sources", arguments) == first
    assert invoke(directory, "import_sources", {**arguments, "batch_id": "other"}) == first
    assert invoke(directory, fixture="count")["rows"] == 3
    assert invoke(directory, "read_sources", {"ids": first["ids"]})["sources"] == sources
    changed = json.loads(json.dumps(sources))
    changed[0]["provenance"]["historical_descriptor"] = "changed"
    assert invoke(directory, "import_sources", {**arguments, "sources": changed}) == {
        "status": "conflict"
    }
    assert invoke(directory, "import_sources", {"batch_id": "third", "sources": changed}) == {
        "status": "corrupt"
    }


@pytest.mark.parametrize(
    "damage",
    [
        "duplicate_record",
        "duplicate_receipt",
        "bad_text",
        "missing_record",
        "bad_receipt",
        "bad_digest",
        "bad_schema",
    ],
)
def test_replay_refuses_duplicate_or_corrupt_committed_state(tmp_path, damage):
    directory = tmp_path / "exact"
    receipt = remember(directory)
    assert receipt["status"] == "ok", receipt
    assert invoke(directory, fixture=damage)["status"] == "ok"
    assert remember(directory) == {"status": "corrupt"}


def test_readonly_missing_store_and_existing_store_create_or_stamp_nothing(tmp_path):
    directory = tmp_path / "missing"
    source_id = "memory:" + "a" * 64
    assert invoke(directory, "read_sources", {"ids": [source_id]}) == {"status": "not_initialized"}
    assert not directory.exists()
    receipt = remember(directory)
    assert receipt["status"] == "ok", receipt
    before = {
        str(path): (path.stat().st_mtime_ns, path.stat().st_size, path.stat().st_mode)
        for path in directory.rglob("*")
    }
    assert invoke(directory, "read_sources", {"ids": receipt["ids"]})["status"] == "ok"
    after = {
        str(path): (path.stat().st_mtime_ns, path.stat().st_size, path.stat().st_mode)
        for path in directory.rglob("*")
    }
    assert before == after


@pytest.mark.parametrize(
    "unsafe", ["store_symlink", "ancestor_symlink", "public_mode", "lock_symlink", "data_symlink"]
)
def test_unsafe_storage_paths_are_refused(tmp_path, unsafe):
    directory = tmp_path / "exact"
    if unsafe in {"public_mode", "lock_symlink", "data_symlink"}:
        assert remember(directory)["status"] == "ok"
        if unsafe == "public_mode":
            directory.chmod(0o755)
        elif unsafe == "lock_symlink":
            (directory / ".write.lock").unlink()
            (directory / ".write.lock").symlink_to(tmp_path / "target")
        else:
            (directory / "records.lance" / "evil").symlink_to(tmp_path)
    else:
        real = tmp_path / "real"
        real.mkdir(mode=0o700)
        if unsafe == "store_symlink":
            directory.symlink_to(real)
        else:
            directory.symlink_to(real, target_is_directory=True)
            directory = directory / "child"
    assert remember(directory)["status"] == "unavailable"


def test_unsupervised_worker_refuses_before_creating_store(tmp_path):
    import subprocess

    directory = tmp_path / "exact"
    request = {
        "directory": str(directory),
        "operation": "remember",
        "arguments": {"request_id": "x", "text": "x"},
        "_host_pid": os.getpid(),
    }
    result = subprocess.run(
        [sys.executable, "-I", str(ROOT / "cognitive_castle/lance_exact_worker.py")],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        timeout=3,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "unavailable"
    assert not directory.exists()


@pytest.mark.parametrize(
    "operation,arguments",
    [
        ("__getattribute__", {}),
        ("remember", {"request_id": "x", "text": "x", "writable": True}),
        ("read_sources", {"ids": ["memory:' OR true"]}),
        ("page", {"source_id": "memory:" + "a" * 64, "offset": True}),
        ("import_sources", {"batch_id": "x", "sources": []}),
        ("import_sources", {"batch_id": "x", "sources": [{}] * 9}),
    ],
)
def test_invalid_requests_are_bounded_and_create_nothing(tmp_path, operation, arguments):
    directory = tmp_path / "exact"
    result = invoke(directory, operation, arguments)
    assert result == {"status": "unavailable", "reason": "invalid_exact_request"}, result
    assert not directory.exists()


def test_private_writer_lock_is_nonblocking_and_readers_do_not_create_it(tmp_path):
    import fcntl

    directory = tmp_path / "exact"
    receipt = remember(directory)
    assert receipt["status"] == "ok", receipt
    with (directory / ".write.lock").open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert remember(directory) == {"status": "busy"}
        assert invoke(directory, "read_sources", {"ids": receipt["ids"]})["status"] == "ok"
    (directory / ".write.lock").unlink()
    assert invoke(directory, "read_sources", {"ids": receipt["ids"]})["status"] == "ok"
    assert not (directory / ".write.lock").exists()


def test_host_has_no_native_dependencies_and_direct_store_requires_supervision(tmp_path):
    from cognitive_castle.lance_exact_store import LanceExactStore

    directory = tmp_path / "exact"
    assert LanceExactStore(directory, writable=True).remember("x", "x") == {"status": "unavailable"}
    assert LanceExactStore(directory).read_sources(["memory:" + "a" * 64]) == {
        "status": "unavailable"
    }
    assert not directory.exists()
    assert not {"lance", "pyarrow", "pandas", "torch"}.intersection(sys.modules)


def test_worker_denies_optional_dependencies_network_children_and_readonly_writes(tmp_path):
    directory = tmp_path / "exact"
    result = invoke(directory, fixture="guards")
    assert result == {
        "status": "ok",
        "denied": [
            "pandas",
            "torch",
            "requests",
            "lancedb",
            "cognitive_castle.backends",
            "network",
            "child",
        ],
        "readonly": {"status": "unavailable"},
    }
    assert not directory.exists()


def test_worker_rejects_oversized_json_frame_before_storage(tmp_path):
    import subprocess

    directory = tmp_path / "exact"
    request = {"directory": str(directory), "padding": "x" * (512 * 1024)}
    result = subprocess.run(
        [sys.executable, "-I", str(ROOT / "cognitive_castle/lance_exact_worker.py")],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        timeout=3,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"status": "unavailable", "reason": "invalid_exact_request"}
    assert not directory.exists()


@pytest.mark.parametrize("lost_response", [False, True])
def test_nine_chunk_remember_reopens_replays_and_recovers_lost_response(tmp_path, lost_response):
    directory = tmp_path / "exact"
    text = "€" * 21845  # 65,535 bytes: eight 8,190-byte chunks plus five euro signs.
    arguments = {"request_id": "request", "text": text}
    if lost_response:
        assert (
            invoke(directory, fixture="lost_response", arguments=arguments)["reason"]
            == "worker_invalid_frame"
        )
    first = invoke(directory, "remember", arguments)
    assert first["status"] == "ok", first
    assert len(first["ids"]) == 9
    assert first["stored_text_bytes"] == 65535
    assert first["text_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    # Every invocation reopens in a fresh supervised child.
    assert invoke(directory, "remember", arguments) == first
    assert remember(directory, text="changed") == {"status": "conflict"}
    sources = []
    for ids in (first["ids"][:8], first["ids"][8:]):
        read = invoke(directory, "read_sources", {"ids": ids})
        assert read["status"] == "ok", read
        sources.extend(read["sources"])
    assert "".join(source["text"] for source in sources) == text
    assert [len(source["text"]) for source in sources] == [2730] * 8 + [5]
    # Supporting all remember chunks never widens import or individual read limits.
    assert invoke(directory, "read_sources", {"ids": first["ids"]}) == {
        "status": "unavailable",
        "reason": "invalid_exact_request",
    }
    assert invoke(directory, "import_sources", {"batch_id": "nine", "sources": sources}) == {
        "status": "unavailable",
        "reason": "invalid_exact_request",
    }
    assert invoke(directory, fixture="count")["rows"] == 10
