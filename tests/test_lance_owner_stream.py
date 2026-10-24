"""Hash-bound dedicated fixtures; native imports only in guarded child workers."""

import json
import os
from pathlib import Path
import sys
import time


def _ordered_execute(request):
    from cognitive_castle import bulk_exact_codec as codec
    from cognitive_castle.bulk_exact_store import OrderedBulkExactStore
    from cognitive_castle.bulk_owner_stream import OrderedQualification
    from cognitive_castle.lance_exact_store import LanceExactStore

    if len(sys.argv) != 3 or request.keys() != {
        "directory",
        "operation",
        "arguments",
        "qualification",
        "qualification_hash",
        "_host_pid",
    }:
        raise ValueError("ordered request")
    reference, digest = sys.argv[1:]
    if request["qualification"] != reference or request["qualification_hash"] != digest:
        raise ValueError("frozen binding")
    arguments = request["arguments"]
    operation = request["operation"]
    fields = {
        "ordered_import_batch": {"batch_id", "source_binding", "entries", "finalizations"},
        "ordered_build_id_index": set(),
    }
    if (
        operation not in fields
        or not isinstance(arguments, dict)
        or arguments.keys() != fields[operation]
    ):
        raise ValueError("ordered arguments")
    if operation == "ordered_import_batch":
        codec.validate_batch(**arguments)
    # This fixed executable's argv binds the qualification; its request cannot
    # replace the path, digest, destination or ceilings. Read at most 64 KiB.
    path = Path(reference)
    if not path.is_absolute() or any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError("qualification path")
    LanceExactStore._private(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if os.fstat(descriptor).st_size > 64 * 1024:
            raise ValueError("qualification bytes")
        raw = os.read(descriptor, 64 * 1024 + 1)
    finally:
        os.close(descriptor)
    qualification = OrderedQualification(raw.decode("utf-8"), digest)
    if request["directory"] != qualification.destination:
        raise ValueError("qualification destination")
    store = OrderedBulkExactStore(
        Path(request["directory"]), qualification=qualification, writable=True
    )
    if operation == "ordered_build_id_index":
        return store.build_id_index()
    if arguments["source_binding"] != qualification.source_binding:
        raise ValueError("qualification source")
    for row in arguments["entries"]:
        store._bound_row(row)
    for owner in arguments["finalizations"]:
        if (owner["owner"], owner["source_binding"]) != (
            qualification.owner,
            qualification.source_binding,
        ):
            raise ValueError("qualification owner")
    return store.import_batch(**arguments)


def _fixture_main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from cognitive_castle.lance_exact_worker import (
        MAX_FRAME,
        _admit_storage,
        _execute,
        _install_guards,
    )
    from cognitive_castle.lance_exact_store import _StoreError

    _install_guards()
    os.umask(0o077)
    try:
        frame = sys.stdin.buffer.read(MAX_FRAME + 1)
        if len(frame) > MAX_FRAME:
            raise ValueError("frame")
        request = json.loads(frame)
        if not isinstance(request, dict):
            raise ValueError("request")
        result = _admit_storage(request)
        if result is None:
            if request.get("operation") in {"ordered_import_batch", "ordered_build_id_index"}:
                result = _ordered_execute(request)
            elif len(sys.argv) == 1:
                result = _execute(request)
            else:
                raise ValueError("fixture operation")
    except _StoreError as error:
        result = {"status": error.status}
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        result = {"status": "unavailable", "reason": "invalid_exact_request"}
    except Exception as error:
        result = {"status": "unavailable", "reason": "fixture_" + type(error).__name__}
    result["fixture_native_imported"] = bool({"lance", "pyarrow"}.intersection(sys.modules))
    output = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(output) > MAX_FRAME:
        output = b'{"status":"unavailable","reason":"worker_output_limit"}'
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    _fixture_main()
    raise SystemExit(0)

import pytest  # noqa: E402
from cognitive_castle import bulk_exact_codec as codec  # noqa: E402
from cognitive_castle.canonical_records import _hash, _json, prepare_remember  # noqa: E402
from test_bulk_owner_stream import qualification_manifest  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="owned-group supervision")
ROOT = Path(__file__).resolve().parents[1]
WORKER = Path(__file__).resolve()


def freeze(directory, owner, version, physical_rows, fragments, **changes):
    manifest = qualification_manifest(directory, owner)
    manifest.update(
        expected_states=[
            {"version": version, "physical_rows": physical_rows, "fragments": fragments}
        ],
        max_physical_rows=256,
        max_fragments=16,
        max_versions=32,
        max_artifact_entries=128,
        max_artifact_depth=6,
        max_logical_bytes=8 * 1024**2,
        max_allocated_bytes=8 * 1024**2,
        max_file_bytes=1024**2,
        max_batch_receipts=16,
        reservations={
            operation: {
                "physical_rows": 32,
                "fragments": 1,
                "versions": 1,
                "artifact_entries": 16,
                "logical_bytes": 1024**2,
                "allocated_bytes": 1024**2,
                "file_bytes": 512 * 1024,
            }
            for operation in ("append", "maintenance")
        },
    )
    manifest.update(changes)
    digest = _hash(_json(manifest))
    reference = directory.parent / (directory.name + "-" + digest + ".qualification.json")
    reference.write_text(_json(manifest))
    reference.chmod(0o600)
    return reference, digest


def invoke(
    directory, arguments, bound=None, *, operation="ordered_import_batch", request_changes=None
):
    from cognitive_castle import memory_runtime as runtime

    request = {"directory": str(directory), "operation": operation, "arguments": arguments}
    command = [sys.executable, "-I", str(WORKER)]
    if bound:
        reference, digest = bound
        command.extend([str(reference), digest])
        request.update(qualification=str(reference), qualification_hash=digest)
    request.update(request_changes or {})
    budget = (
        3
        if operation
        in {
            "ordered_import_batch",
            "ordered_build_id_index",
            "import_batch",
            "build_id_index",
            "remember",
            "import_sources",
        }
        else 2
    )
    admission = runtime._admission()
    try:
        result = runtime._supervise(
            request,
            admission,
            worker_command=command,
            deadline=budget,
            absolute_deadline=time.monotonic() + budget,
            background_preempt=True,
            rss_limit=192 * 1024**2,
            total_rss_limit=256 * 1024**2,
        )
    finally:
        os.close(admission)
    print(
        "ORDERED_STAGE",
        json.dumps(
            {
                "operation": operation,
                **{key: value for key, value in result.items() if key != "sources"},
            }
        ),
        flush=True,
    )
    return {key: value for key, value in result.items() if key != "resources"}


def arguments(rows, owners=(), batch="batch"):
    return {
        "batch_id": batch,
        "source_binding": "snapshot",
        "entries": rows,
        "finalizations": list(owners),
    }


def canonical_files(directory):
    return {
        str(path.relative_to(directory)): (
            path.stat().st_size,
            path.stat().st_mtime_ns,
            _hash(path.read_bytes().hex()),
        )
        for path in directory.rglob("*")
        if path.is_file()
    }


def test_pinned_stream_finalization_and_replay(tmp_path):
    directory = tmp_path / "ordered"
    directory.mkdir(mode=0o700)
    original = "ž😀\x00\r\n" * 2000 + "late"
    prepared = prepare_remember("ordered-native", original)
    rows, owner = codec.prepare_owner(
        "ordered",
        "snapshot",
        prepared.records,
        metadata="ž😀\x00 " * 1500,
        live={
            "namespace": prepared.namespace,
            "key": prepared.request_id,
            "digest": prepared.digest,
            "receipt": prepared.receipt,
        },
    )
    split = (
        next(
            i
            for i, row in enumerate(rows)
            if row["kind"] == "bulk_page" and json.loads(row["receipt"])["field"] == "membership"
        )
        + 1
    )
    staged = arguments(rows[:split], batch="split-membership")
    first = invoke(directory, staged, freeze(directory, owner, 0, 0, 0))
    assert first["status"] == "ok", first
    count = split + 1
    middle = arguments(rows[split:-1], batch="middle")
    assert invoke(directory, middle, freeze(directory, owner, 1, count, 1))["status"] == "ok"
    count += len(rows[split:-1]) + 1
    final_args = arguments(rows[-1:], [owner], "finish")
    final = invoke(directory, final_args, freeze(directory, owner, 2, count, 2))
    assert final["status"] == "ok", final
    count += 4  # Last record, owner marker, original live receipt, batch receipt.
    before = canonical_files(directory)
    assert invoke(directory, final_args, freeze(directory, owner, 3, count, 3)) == final
    assert invoke(directory, staged, freeze(directory, owner, 3, count, 3)) == first
    assert canonical_files(directory) == before
    # Reconciliation admits exactly the paired version/geometry records. An
    # acknowledged retry still runs inherited full batch and owner proofs.
    reconciliation = freeze(
        directory,
        owner,
        3,
        count,
        3,
        expected_states=[
            {"version": 2, "physical_rows": count - 4, "fragments": 2},
            {"version": 3, "physical_rows": count, "fragments": 3},
        ],
    )
    assert invoke(directory, final_args, reconciliation) == final
    assert canonical_files(directory) == before
    for change in (
        {"expected_states": [{"version": 2, "physical_rows": count - 4, "fragments": 2}]},
        {"expected_states": [{"version": 3, "physical_rows": count, "fragments": 4}]},
    ):
        assert (
            invoke(directory, final_args, freeze(directory, owner, 3, count, 3, **change))["status"]
            == "stale"
        )
        assert canonical_files(directory) == before
    read = invoke(
        directory, {"ids": [record.id for record in prepared.records]}, operation="read_sources"
    )
    assert read["status"] == "ok" and "".join(row["text"] for row in read["sources"]) == original
    assert not {"lance", "pyarrow", "sqlite3"}.intersection(sys.modules)


def test_stream_layout_corruption_refuses(tmp_path):
    prepared = prepare_remember("layout", "unchanged original")
    rows, owner = codec.prepare_owner("layout", "snapshot", prepared.records)
    missing = tmp_path / "missing"
    refusal = invoke(missing, arguments(rows, [owner]))
    assert refusal["status"] == "unavailable" and not refusal["fixture_native_imported"]
    assert not missing.exists()
    directory = tmp_path / "ordered"
    directory.mkdir(mode=0o700)
    bound = freeze(directory, owner, 0, 0, 0)
    refusal = invoke(
        directory,
        arguments(rows, [owner]),
        bound,
        request_changes={"qualification_hash": "0" * 64},
    )
    assert refusal["status"] == "unavailable" and not refusal["fixture_native_imported"]
    assert not (directory / "records.lance").exists()
    changed_reference = directory.parent / "changed.qualification.json"
    changed_manifest = json.loads(bound[0].read_text())
    changed_manifest["source_binding"] = "changed-after-freeze"
    changed_reference.write_text(_json(changed_manifest))
    changed_reference.chmod(0o600)
    refusal = invoke(
        directory,
        arguments(rows, [owner]),
        (changed_reference, bound[1]),
    )
    assert refusal["status"] == "unavailable" and not refusal["fixture_native_imported"]
    assert not (directory / "records.lance").exists()
    # The unchanged legacy store accepts arbitrary valid entry order.
    shuffled = [rows[-1], *rows[:-1]]
    legacy = invoke(directory, arguments(shuffled, [owner]), operation="import_batch")
    assert legacy["status"] == "ok", legacy
    count = len(rows) + 2
    before = canonical_files(directory)
    assert (
        invoke(
            directory,
            arguments([], [owner], "ordered-claim"),
            freeze(directory, owner, 1, count, 1),
        )["status"]
        == "corrupt"
    )
    assert canonical_files(directory) == before

    # A lower frozen physical ceiling refuses the real legacy fixture after
    # bounded native open; it cannot claim the smaller registered geometry.
    reduced = json.loads(bound[0].read_text())
    for reservation in reduced["reservations"].values():
        reservation["physical_rows"] = count - 1
    physical_bound = freeze(
        directory,
        owner,
        1,
        count - 1,
        1,
        max_physical_rows=count - 1,
        reservations=reduced["reservations"],
    )
    refusal = invoke(directory, arguments([], [owner], "row-ceiling"), physical_bound)
    assert refusal["status"] == "unavailable" and refusal["fixture_native_imported"]
    assert canonical_files(directory) == before

    foreign_directory = tmp_path / "foreign"
    foreign_directory.mkdir(mode=0o700)
    foreign_rows, _ = codec.prepare_owner("foreign", "snapshot", prepared.records)
    foreign_stage = invoke(
        foreign_directory,
        arguments(foreign_rows, batch="foreign-stage"),
        operation="import_batch",
    )
    assert foreign_stage["status"] == "ok", foreign_stage
    before = canonical_files(foreign_directory)
    refusal = invoke(
        foreign_directory,
        arguments([], [owner], "foreign-claim"),
        freeze(foreign_directory, owner, 1, len(foreign_rows) + 1, 1),
    )
    assert refusal["status"] == "corrupt" and refusal["fixture_native_imported"]
    assert canonical_files(foreign_directory) == before

    _assert_artifact_refusals(tmp_path, owner)
    assert not {"lance", "pyarrow", "sqlite3"}.intersection(sys.modules)


def _assert_artifact_refusals(tmp_path, owner):
    for case in ("first-extra-artifact", "depth", "oversize-manifest"):
        directory = tmp_path / case
        directory.mkdir(mode=0o700)
        bound = freeze(directory, owner, 0, 0, 0)
        native = directory / "records.lance"
        native.mkdir(mode=0o700)
        if case == "first-extra-artifact":
            # Root + dataset directory +127 files is the first129th artifact.
            for ordinal in range(127):
                path = native / (str(ordinal) + ".orphan")
                path.write_bytes(b"")
                path.chmod(0o600)
        elif case == "depth":
            nested = native
            for ordinal in range(6):
                nested = nested / str(ordinal)
                nested.mkdir(mode=0o700)
        else:
            versions = native / "_versions"
            versions.mkdir(mode=0o700)
            path = versions / "99.manifest"
            path.write_bytes(b"x" * (1024**2 + 1))
            path.chmod(0o600)
        before = canonical_files(directory)
        refusal = invoke(directory, arguments([], [owner], case), bound)
        assert refusal["status"] == "unavailable", refusal
        assert not refusal["fixture_native_imported"]
        assert canonical_files(directory) == before


def test_pinned_stream_qualified_maintenance(tmp_path):
    directory = tmp_path / "maintenance"
    directory.mkdir(mode=0o700)
    prepared = prepare_remember("maintenance", "original ž😀\x00\r\n")
    rows, owner = codec.prepare_owner("maintenance", "snapshot", prepared.records)
    original = arguments(rows, [owner], "maintenance-owner")
    assert invoke(directory, original, freeze(directory, owner, 0, 0, 0))["status"] == "ok"
    count = len(rows) + 2
    before = canonical_files(directory)
    refused_bound = freeze(directory, owner, 1, count, 1)
    reduced = json.loads(refused_bound[0].read_text())["reservations"]
    reduced["maintenance"]["versions"] = 0
    refused_bound = freeze(directory, owner, 1, count, 1, reservations=reduced)
    refusal = invoke(directory, {}, refused_bound, operation="ordered_build_id_index")
    assert refusal["status"] == "unavailable"
    assert canonical_files(directory) == before
    index_bound = freeze(
        directory,
        owner,
        1,
        count,
        1,
        expected_states=[
            {"version": 1, "physical_rows": count, "fragments": 1},
            {"version": 2, "physical_rows": count, "fragments": 1},
        ],
    )
    indexed = invoke(
        directory,
        {},
        index_bound,
        operation="ordered_build_id_index",
    )
    assert indexed["status"] == "ok", indexed
    assert indexed["lookup"]["version"] == 2
    assert indexed["lookup"]["tail_rows"] == 0
    assert indexed["lookup"]["indexed_fragments"] == 1
    after_index = canonical_files(directory)
    refusal = invoke(directory, {}, index_bound, operation="ordered_build_id_index")
    assert refusal["status"] == "stale", refusal
    assert canonical_files(directory) == after_index
    # A fresh fixed worker proves persisted index visibility, then real replay
    # verifies all original batch and owner bytes under the new exact pin.
    fresh = invoke(directory, {"owner": owner["owner"]}, operation="bulk_owner")
    assert fresh["status"] == "ok" and fresh["manifest"] == owner
    assert fresh["lookup"]["version"] == 2 and fresh["lookup"]["tail_rows"] == 0
    assert fresh["lookup"]["indexed_fragments"] == 1
    replay = invoke(directory, original, freeze(directory, owner, 2, count, 1))
    assert replay["status"] == "ok", replay
    assert canonical_files(directory) == after_index
    assert not {"lance", "pyarrow", "sqlite3"}.intersection(sys.modules)


@pytest.mark.parametrize(
    ("operation", "budget"),
    [
        ("read_sources", 2),
        ("bulk_owner", 2),
        ("ordered_import_batch", 3),
        ("ordered_build_id_index", 3),
        ("import_batch", 3),
    ],
)
def test_fixture_supervisor_budget_is_fixed(operation, budget, tmp_path, monkeypatch):
    from cognitive_castle import memory_runtime as runtime

    calls = []
    monkeypatch.setattr(runtime, "_admission", lambda: os.open(os.devnull, os.O_RDONLY))
    monkeypatch.setattr(
        runtime,
        "_supervise",
        lambda *args, **kwargs: calls.append((args, kwargs)) or {"status": "ok"},
    )
    monkeypatch.setattr(time, "monotonic", lambda: 100.0)
    assert invoke(tmp_path / "unused", {}, operation=operation) == {"status": "ok"}
    assert len(calls) == 1
    _, supervision = calls[0]
    assert supervision["deadline"] == budget
    assert supervision["absolute_deadline"] == 100.0 + budget
    assert supervision["background_preempt"] is True
    assert supervision["rss_limit"] == 192 * 1024**2
    assert supervision["total_rss_limit"] == 256 * 1024**2
    assert not {"lance", "pyarrow", "sqlite3"}.intersection(sys.modules)


def test_pinned_stream_receipt_ceiling_refuses_before_append_and_replays_boundary(tmp_path):
    directory = tmp_path / "receipt-ceiling"
    directory.mkdir(mode=0o700)
    prepared = prepare_remember("receipt-ceiling", "original exact bytes")
    rows, owner = codec.prepare_owner("receipt-ceiling", "snapshot", prepared.records)
    staged = arguments(rows, batch="stage")
    assert (
        invoke(directory, staged, freeze(directory, owner, 0, 0, 0, max_batch_receipts=1))["status"]
        == "ok"
    )
    count = len(rows) + 1
    before = canonical_files(directory)
    for attempt in (arguments([], [owner], "finish"), arguments(rows[:1], batch="extra-stage")):
        refusal = invoke(
            directory, attempt, freeze(directory, owner, 1, count, 1, max_batch_receipts=1)
        )
        assert refusal["status"] == "unavailable", refusal
        assert canonical_files(directory) == before
    final_args = arguments([], [owner], "finish")
    final = invoke(
        directory, final_args, freeze(directory, owner, 1, count, 1, max_batch_receipts=2)
    )
    assert final["status"] == "ok", final
    count += 2
    before = canonical_files(directory)
    # The exact resulting receipt ceiling admits full real final-batch replay.
    assert (
        invoke(directory, final_args, freeze(directory, owner, 2, count, 2, max_batch_receipts=2))
        == final
    )
    assert canonical_files(directory) == before
    refusal = invoke(
        directory,
        {},
        freeze(directory, owner, 2, count, 2, max_batch_receipts=1),
        operation="ordered_build_id_index",
    )
    assert refusal["status"] == "unavailable"
    assert canonical_files(directory) == before


def test_pinned_stream_reconciliation_after_state_is_replay_only(tmp_path):
    directory = tmp_path / "reconciliation"
    directory.mkdir(mode=0o700)
    prepared = prepare_remember("reconciliation", "original exact bytes")
    rows, owner = codec.prepare_owner("reconciliation", "snapshot", prepared.records)
    original = arguments(rows, [owner], "original")
    count = len(rows) + 2
    bound = freeze(
        directory,
        owner,
        0,
        0,
        0,
        expected_states=[
            {"version": 0, "physical_rows": 0, "fragments": 0},
            {"version": 1, "physical_rows": count, "fragments": 1},
        ],
    )
    # The registered before-state still permits the original real mutation.
    first = invoke(directory, original, bound)
    assert first["status"] == "ok", first
    before = canonical_files(directory)
    assert invoke(directory, original, bound) == first
    assert canonical_files(directory) == before
    refusal = invoke(directory, arguments([], [owner], "new-finalization"), bound)
    assert refusal["status"] == "stale", refusal
    assert canonical_files(directory) == before
    refusal = invoke(directory, {}, bound, operation="ordered_build_id_index")
    assert refusal["status"] == "stale", refusal
    assert canonical_files(directory) == before
    fresh = invoke(directory, {"owner": owner["owner"]}, operation="bulk_owner")
    assert fresh["status"] == "ok" and fresh["manifest"] == owner
    assert canonical_files(directory) == before


def test_pinned_stream_published_owner_rejects_late_content_preserves_replay(tmp_path):
    directory = tmp_path / "published"
    directory.mkdir(mode=0o700)
    prepared = prepare_remember("published", "original exact bytes")
    rows, owner = codec.prepare_owner(
        "published", "snapshot", prepared.records, descriptor="", scopes=""
    )
    original = arguments(rows, [owner], "original")
    first = invoke(directory, original, freeze(directory, owner, 0, 0, 0))
    assert first["status"] == "ok", first
    count = len(rows) + 2
    before = canonical_files(directory)
    late = codec.page(owner["owner"], "descriptor", 0, "new valid own-owner page", 0, 0)
    refusal = invoke(
        directory, arguments([late], batch="late-content"), freeze(directory, owner, 1, count, 1)
    )
    assert refusal["status"] == "conflict", refusal
    assert canonical_files(directory) == before
    assert invoke(directory, original, freeze(directory, owner, 1, count, 1)) == first
    assert canonical_files(directory) == before
    # A new receipt for equivalent already-present entries adds no content.
    equivalent = arguments(rows, batch="equivalent")
    assert invoke(directory, equivalent, freeze(directory, owner, 1, count, 1))["status"] == "ok"
    assert invoke(directory, original, freeze(directory, owner, 2, count + 1, 2)) == first
