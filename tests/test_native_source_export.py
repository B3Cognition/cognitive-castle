"""Disposable native fixtures; the pytest host imports no storage engine."""

import hashlib
import json
import os
from pathlib import Path
import sys

import pytest


def fixture_main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from cognitive_castle.memory_history_worker import _install_guards, _admit_storage

    _install_guards()
    os.umask(0o077)
    request = json.load(sys.stdin)
    refusal = _admit_storage(request)
    if refusal:
        print(json.dumps(refusal))
        return
    if request.get("action") == "mutate":
        mutate_fixture(request)
        return
    import lance
    import pyarrow as pa
    from cognitive_castle.canonical_records import _json, _hash
    from cognitive_castle.native_export_codec import FORMAT, file_identity

    directory = Path(request["directory"])
    directory.mkdir(mode=0o700)
    path = directory / "archive.lance"
    # Three physical fragments: deleted row, entirely deleted fragment, two
    # repeated aliases and a real zero-text occurrence in later fragments.
    text = "a" * 8189 + "€🙂\x00e\u0301" + "z" * 8200
    bodies = [text, "deleted", "deleted", "deleted", text, ""]
    aliases = ["duplicate", "gone", "gone", "gone", "duplicate", ""]
    metadata = [' { "workspace": "meta", "wing":"meta-wing", "n":"\\u0000" }\n'] * 6
    table = pa.table(
        {
            "id": aliases,
            "text": bodies,
            "metadata_json": metadata,
            "workspace": ["Ω" * 100] * 6,
            "wing": [None] * 6,
            "room": [""] * 6,
            "select": ["reserved"] * 6,
            "field with spaces": ["exact ž"] * 6,
            "nested": [{"number": 3, "values": [1, 2]}] * 6,
            "vector": pa.array([[1.0, 2.0]] * 6, type=pa.list_(pa.float32(), 2)),
        }
    )
    mode = request.get("mode", "small")
    if mode in {"empty", "single"}:
        table = table.slice(0, 0 if mode == "empty" else 1)
    elif mode == "multibatch":
        import struct

        data = bytearray()
        for _ in range(100):
            data.extend(b"\x00" * 1000)
        text_array = pa.Array.from_buffers(
            pa.string(),
            1,
            [None, pa.py_buffer(struct.pack("<ii", 0, len(data))), pa.py_buffer(data)],
        )
        table = table.slice(0, 1).set_column(1, "text", text_array)
    elif mode == "oversized":
        table = table.slice(0, 1).set_column(
            2, "metadata_json", pa.array(['{"large":"' + "x" * 1048576 + '"}'])
        )
    elif mode == "types":
        table = table.slice(0, 1).set_column(3, "workspace", pa.array([123]))
        table = table.set_column(4, "wing", pa.array([False]))
        table = table.set_column(5, "room", pa.nulls(1))
    elif mode == "invalid_metadata":
        table = table.slice(0, 1).set_column(2, "metadata_json", pa.array(['{"workspace":NaN}']))
    dataset = lance.write_dataset(table, path, max_rows_per_file=2, max_rows_per_group=2)
    dataset.delete("id = 'gone'")
    version = dataset.version
    from cognitive_castle.memory_history import _scan_rows, _stage_header, _stage_caller, _chunks
    from cognitive_castle.fast_memory import MemoryStore
    from cognitive_castle.history_projection import NativeProjectedRow
    from cognitive_castle.canonical_records import CanonicalRecord

    rows, raw = [], {"fragment": 0, "offset": 0}
    job = dict(archive_id="original-archive", snapshot_id="original-snapshot", version=version)
    for row in () if mode in {"multibatch", "oversized"} else _scan_rows(path, version, raw):
        reader = NativeProjectedRow(path, version, raw)
        header = reader.header()
        following, occurrence, meta, columns = _stage_header(header, job, raw)
        assert following == {k: row[k] for k in ("fragment", "offset", "row_address")}
        assert header["values"] == {k: v for k, v in row["values"].items() if k != "text"}
        alias, caller = _stage_caller(
            job, dict(columns_json=columns, metadata_json=meta, identity=occurrence)
        )
        expected = []
        for start, chunk in _chunks(row["values"]["text"]):
            record = CanonicalRecord.from_source(
                dict(
                    id="memory:" + _hash(_json([occurrence, start])),
                    text=chunk,
                    provenance=MemoryStore._provenance(
                        caller, _hash(chunk), start, start + len(chunk)
                    ),
                )
            )
            expected.append(record.source())
        if mode not in {"multibatch", "oversized"}:
            rows.append(
                dict(
                    before=raw,
                    following=following,
                    occurrence=occurrence,
                    alias=alias,
                    metadata=meta,
                    columns=columns,
                    records=expected,
                    text_hash=_hash(row["values"]["text"]),
                )
            )
        reader.close()
        raw = following
    schema_raw = dataset.schema.serialize().to_pybytes()
    fragments = [
        f.metadata.to_json() for f in sorted(dataset.get_fragments(), key=lambda f: f.fragment_id)
    ]
    dataset = None
    inventory = []
    for filename in sorted(p for p in path.rglob("*") if p.is_file()):
        with filename.open("rb") as handle:
            os.fsync(handle.fileno())
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        filename.chmod(0o400)
        inventory.append(
            dict(
                path=str(filename.relative_to(path)),
                snapshot_identity=file_identity(filename.stat()),
                content_hash=digest,
            )
        )
    for directory_path in sorted((p for p in path.rglob("*") if p.is_dir()), reverse=True):
        directory_path.chmod(0o500)
    path.chmod(0o500)
    snapshot_identity = file_identity(path.stat())
    manifest = dict(
        format=FORMAT,
        state="complete",
        store_id="native-fixture",
        snapshot_identity=snapshot_identity,
        original=job,
        start_cursor={"fragment": 0, "offset": 0},
        schema=dict(hash=hashlib.sha256(schema_raw).hexdigest(), bytes=len(schema_raw)),
        fragments=fragments,
        inventory=inventory,
        lineage={"kind": "disposable-synthetic", "coverage": "pending-reconciliation"},
    )
    manifest_path = directory / "native.json"
    manifest_path.write_text(_json(manifest))
    with manifest_path.open("rb") as handle:
        os.fsync(handle.fileno())
    manifest_path.chmod(0o400)
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(fd)
    os.close(fd)
    descriptor = dict(
        format=FORMAT,
        store_id="native-fixture",
        snapshot_path=str(path),
        snapshot_identity=snapshot_identity,
        manifest_path=str(manifest_path),
        manifest_identity=file_identity(manifest_path.stat()),
        manifest_hash=_hash(manifest_path.read_text()),
        archive_id=job["archive_id"],
        original_snapshot_id=job["snapshot_id"],
        version=version,
        start_cursor=manifest["start_cursor"],
    )
    print(json.dumps(dict(status="ok", descriptor=descriptor, rows=rows, files=len(inventory))))


def mutate_fixture(request):
    descriptor = request["descriptor"]
    path = Path(descriptor["snapshot_path"])
    filename = next(p for p in sorted(path.rglob("*")) if p.is_file())
    mutation = request["mutation"]
    if mutation == "writable":
        filename.chmod(0o600)
    elif mutation == "extra":
        path.chmod(0o700)
        (path / "extra").write_text("unregistered")
        path.chmod(0o500)
    elif mutation in {"symlink", "hardlink"}:
        filename.parent.chmod(0o700)
        alias = filename.parent / "alias"
        if mutation == "symlink":
            alias.symlink_to(filename.name)
        else:
            os.link(filename, alias)
        filename.parent.chmod(0o500)
    elif mutation == "manifest":
        manifest = Path(descriptor["manifest_path"])
        manifest.unlink()
        manifest.write_text("{}")
        manifest.chmod(0o400)
    elif mutation == "snapshot":
        path.rename(path.with_name("retained.lance"))
        path.mkdir(mode=0o500)
    print(json.dumps({"status": "ok"}))


def fixture_call(arguments):
    from cognitive_castle import memory_runtime as runtime

    admission = runtime._admission()
    try:
        result = runtime._supervise(
            arguments,
            admission,
            worker_command=[sys.executable, "-I", str(Path(__file__).resolve()), "fixture"],
            deadline=5,
            rss_limit=512 * 1024**2,
            total_rss_limit=640 * 1024**2,
            background_preempt=True,
        )
    finally:
        os.close(admission)
    print("fixture", result.get("resources"))
    assert result["status"] == "ok", result
    return result


def make_fixture(directory, mode="small"):
    return fixture_call({"directory": str(directory), "mode": mode})


def artifact_fingerprint(descriptor):
    paths = [
        Path(descriptor["manifest_path"]),
        *sorted(Path(descriptor["snapshot_path"]).rglob("*")),
    ]
    return [
        (str(p), p.lstat(), hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
        for p in paths
    ]


def source_slice(descriptor, cursor=None):
    from cognitive_castle.semantic_runtime import SemanticSession

    with SemanticSession("/private/unused", interactive=False) as session:
        result = session.native_source(descriptor, cursor)
        print("source", session.resources)
    return result


@pytest.mark.skipif(sys.platform != "darwin", reason="owned supervision")
def test_small_source_identity_pages_and_eof(tmp_path):
    from cognitive_castle import migration_codec as migration

    fixture = make_fixture(tmp_path / "source")
    descriptor = fixture["descriptor"]
    before_files = artifact_fingerprint(descriptor)
    cursor = None
    seen = []
    reg = migration.registration(descriptor, str(tmp_path / "destination"))
    for expected in fixture["rows"]:
        result = source_slice(descriptor, cursor)
        assert result["status"] == "ok", result
        migration.validate_export(
            result, reg, migration.initial_source_cursor(reg) if cursor is None else cursor
        )
        assert result["phase"] == "history" and result["phase_complete"] and not result["complete"]
        assert result["counts"]["historical_occurrences"] == 1
        assert result["counts"]["members"] == len(expected["records"])
        owner = result["finalizations"][0]
        assert owner["owner_key"] == owner["metadata_id"] == expected["occurrence"]
        assert owner["text_hash"] == expected["text_hash"] and owner["live"] is None
        records = [
            dict(id=e["id"], text=e["text"], provenance=json.loads(e["provenance"]))
            for e in result["entries"]
            if e["kind"] == "bulk_record"
        ]
        assert records == expected["records"]
        fields = {
            name: "".join(
                e["text"]
                for e in result["entries"]
                if e["kind"] == "bulk_page" and json.loads(e["receipt"])["field"] == name
            )
            for name in ("metadata", "columns", "scopes", "descriptor")
        }
        assert (
            fields["metadata"] == expected["metadata"] and fields["columns"] == expected["columns"]
        )
        scopes = json.loads(fields["scopes"])
        assert scopes["selection"]["workspace"]["selected_origin"] == "columns"
        assert scopes["selection"]["wing"]["selected_origin"] == "metadata"
        assert scopes["selection"]["room"]["selected_origin"] == "columns"
        assert json.loads(scopes["columns"])["workspace"] == "Ω" * 100
        evidence = json.loads(fields["descriptor"])
        assert evidence["raw_before"] == expected["before"]
        assert evidence["following"] == expected["following"]
        assert evidence["alias"] == expected["alias"]
        assert result["cursor_after"]["key"] == [
            json.dumps(expected["following"], sort_keys=True, separators=(",", ":"))
        ]
        replay = source_slice(descriptor, cursor)
        assert replay == result
        seen.append(owner["owner_key"])
        cursor = result["cursor_after"]
    assert len(seen) == len(set(seen)) == 3
    exhausted = source_slice(descriptor, cursor)
    assert exhausted["status"] == "ok" and exhausted["complete"]
    assert exhausted["entries"] == exhausted["finalizations"] == []
    assert exhausted["cursor_after"]["phase"] == "done"
    migration.validate_export(exhausted, reg, cursor)
    assert artifact_fingerprint(descriptor) == before_files
    assert not {"sqlite3", "lance", "pyarrow", "numpy", "torch"}.intersection(sys.modules)


@pytest.mark.skipif(sys.platform != "darwin", reason="owned supervision")
def test_native_empty_snapshot_is_genuine_eof(tmp_path):
    from cognitive_castle import migration_codec as migration

    fixture = make_fixture(tmp_path / "empty", "empty")
    d = fixture["descriptor"]
    original = artifact_fingerprint(d)
    result = source_slice(d)
    reg = migration.registration(d, str(tmp_path / "destination"))
    migration.validate_export(result, reg, migration.initial_source_cursor(reg))
    assert result["status"] == "ok" and result["complete"]
    assert not result["entries"] and not result["finalizations"]
    assert not any(result["counts"].values())
    assert artifact_fingerprint(d) == original


@pytest.mark.skipif(sys.platform != "darwin", reason="owned supervision")
@pytest.mark.parametrize(
    "mutation", ["writable", "extra", "symlink", "hardlink", "manifest", "snapshot"]
)
def test_native_changed_artifacts_refuse_without_progress(tmp_path, mutation):
    from cognitive_castle import migration_codec as migration

    fixture = make_fixture(tmp_path / "changed", "single")
    d = fixture["descriptor"]
    before = migration.initial_source_cursor(
        migration.registration(d, str(tmp_path / "destination"))
    )
    fixture_call(dict(action="mutate", descriptor=d, mutation=mutation))
    result = source_slice(d, before)
    assert result["status"] != "ok", result
    assert result["cursor_after"] == before
    assert not result["entries"] and not result["finalizations"]
    assert not result["complete"] and not result["phase_complete"]
    assert not any(result["counts"].values())


@pytest.mark.skipif(sys.platform != "darwin", reason="owned supervision")
def test_native_multibatch_ascii_frames_replay_exact_text(tmp_path):
    from cognitive_castle import migration_codec as migration

    fixture = make_fixture(tmp_path / "large", "multibatch")
    d = fixture["descriptor"]
    original = artifact_fingerprint(d)
    reg = migration.registration(d, str(tmp_path / "destination"))
    cursor = migration.initial_source_cursor(reg)
    whole, expected = hashlib.sha256(), hashlib.sha256()
    for _ in range(100):
        expected.update(b"\x00" * 1000)
    chunks = size = slices = 0
    for _ in range(6):
        result = source_slice(d, cursor)
        assert result["status"] == "ok", result
        migration.validate_export(result, reg, cursor)
        assert (
            result["frame_bytes"]
            == len(json.dumps(result, allow_nan=False).encode("ascii"))
            <= 512 * 1024
        )
        assert source_slice(d, cursor) == result
        for entry in result["entries"]:
            assert len(entry["text"].encode()) <= 8192
            if entry["kind"] == "bulk_record":
                provenance = json.loads(entry["provenance"])
                assert provenance["chunk_start"] == size
                size += len(entry["text"])
                whole.update(entry["text"].encode())
                chunks += 1
        slices += 1
        if result["finalizations"]:
            owner = result["finalizations"][0]
            assert owner["text_chars"] == owner["text_bytes"] == size == 100000
            assert owner["text_hash"] == whole.hexdigest() == expected.hexdigest()
            assert owner["members"] == chunks == 13
            break
        assert not any(result["counts"].values())
        assert result["cursor_after"]["key"] == cursor["key"]
        assert result["cursor_after"]["owner"] is not None
        cursor = result["cursor_after"]
    else:
        pytest.fail("bounded fixture did not finish")
    assert slices > 1
    assert artifact_fingerprint(d) == original


def native_tick(reg, *, stop=None, loss=None):
    import time
    from cognitive_castle.semantic_runtime import SemanticSession
    from cognitive_castle.migration_coordinator import _native_fixture_tick
    from test_migration_coordinator import ObservedSession, FixtureInterruption

    class ObservedNative(ObservedSession):
        def native_source(self, d, cursor):
            return self.call("source", self.session.native_source, d, cursor)

    started = time.monotonic()
    with SemanticSession("/private/unused", interactive=False) as session:
        observed = ObservedNative(session, stop=stop, loss=loss)
        try:
            result = _native_fixture_tick(observed, reg)
        except FixtureInterruption:
            result = {"status": "fixture_interruption"}
        print("NATIVE_TICK", time.monotonic() - started, session.resources)
        assert time.monotonic() - started < 5.5
    return result, observed


@pytest.mark.skipif(sys.platform != "darwin", reason="owned supervision")
def test_native_coordinator_staging_restart_final_owner_and_lost_ack(tmp_path):
    from cognitive_castle import migration_codec as migration
    from cognitive_castle.canonical_records import _hash, _json
    from test_migration_coordinator import queue_state
    from test_semantic_queue import invoke as queue
    from test_bulk_exact_store import invoke as exact

    fixture = make_fixture(tmp_path / "staged-source", "multibatch")
    d = fixture["descriptor"]
    original = artifact_fingerprint(d)
    generation = tmp_path / "generation"
    generation.mkdir(mode=0o700)
    reg = migration.registration(d, str(generation))
    assert native_tick(reg, stop="before:source:1")[0]["status"] == "fixture_interruption"
    initial = queue_state(reg)
    assert initial["pending"] is None
    assert native_tick(reg, stop="after:source:1")[0]["status"] == "fixture_interruption"
    assert queue_state(reg)["pending"] is None
    assert native_tick(reg, stop="after:import_batch:1")[0]["status"] == "fixture_interruption"
    staged = queue_state(reg)
    pending = staged["pending"]
    assert pending is not None and not pending["owners"]
    assert staged["staging_cursor"] == staged["completed_frontier"] == initial["staging_cursor"]
    occurrence = pending["cursor_after"]["owner"]
    owner_id = migration.bulk.owner_id(occurrence, reg["source_binding"])
    first_id = "memory:" + _hash(_json([occurrence, 0]))
    assert exact(generation / "exact", "bulk_owner", {"owner": owner_id})["status"] == "not_found"
    assert exact(generation / "exact", "read_sources", {"ids": [first_id]})["status"] == "not_found"
    restarted, observed = native_tick(reg)
    assert restarted["status"] == "ok", restarted
    assert observed.calls.count("source") == 1 and observed.calls.count("import_batch") == 2
    assert "queue_migration_prepare:1" not in observed.arguments
    state = queue_state(reg)
    assert state["pending"] is None and state["staging_cursor"] == pending["cursor_after"]
    assert state["completed_frontier"] == initial["completed_frontier"]
    assert not any(state["counts"].values())
    lost, observed = native_tick(reg, loss="queue_migration_ack:1")
    assert lost["status"] == "unavailable" and lost["reason"] == "fixture_lost_response", lost
    assert observed.calls.count("source") == 1 and observed.calls.count("import_batch") == 2
    state = queue_state(reg)
    assert state["pending"] is None and state["counts"]["historical_occurrences"] == 1
    assert state["counts"]["members"] == 13 and state["owner_references"] == 1
    assert state["staging_cursor"] == state["completed_frontier"]
    ack_args = observed.arguments["queue_migration_ack:1"][-1]
    assert queue(generation, "queue_migration_ack", ack_args) == state["last_ack"]["result"]
    assert queue_state(reg)["counts"] == state["counts"]
    found = exact(generation / "exact", "read_sources", {"ids": [first_id]})
    assert found["status"] == "ok" and len(found["sources"][0]["text"]) == 8192
    assert found["sources"][0]["metadata"]["id"] == occurrence
    owner = exact(generation / "exact", "bulk_owner", {"owner": owner_id})
    assert owner["status"] == "ok" and owner["manifest"]["metadata_id"] == occurrence
    # Exhaustion has its own ACK; it never invents another owner/count/frontier.
    completed, _ = native_tick(reg)
    assert completed["status"] == "ok", completed
    exhausted = queue_state(reg)
    assert exhausted["state"] == "snapshot_export_exhausted"
    assert exhausted["staging_cursor"]["phase"] == "done"
    assert exhausted["completed_frontier"] == state["completed_frontier"]
    assert exhausted["counts"] == state["counts"] and exhausted["coverage"] == "incomplete"
    raw = (generation / "coordination/queue.sqlite3").read_bytes()
    assert b"pending-reconciliation" not in raw and b"field with spaces" not in raw
    assert artifact_fingerprint(d) == original
    assert not {"sqlite3", "lance", "pyarrow", "numpy", "torch"}.intersection(sys.modules)


@pytest.mark.skipif(sys.platform != "darwin", reason="owned supervision")
def test_native_type_conflicts_and_oversized_header_preserve_boundary(tmp_path):
    from cognitive_castle import migration_codec as migration

    fixture = make_fixture(tmp_path / "typed", "types")
    d = fixture["descriptor"]
    original = artifact_fingerprint(d)
    result = source_slice(d)
    assert result["status"] == "ok", result
    scopes = json.loads(
        "".join(
            e["text"]
            for e in result["entries"]
            if e["kind"] == "bulk_page" and json.loads(e["receipt"])["field"] == "scopes"
        )
    )
    assert scopes["selection"]["workspace"] == {
        "columns": "integer",
        "metadata": "text",
        "selected_origin": "columns",
    }
    assert scopes["selection"]["wing"] == {
        "columns": "false",
        "metadata": "text",
        "selected_origin": "columns",
    }
    assert scopes["selection"]["room"] == {
        "columns": "null",
        "metadata": None,
        "selected_origin": "caller",
    }
    for entry in result["entries"]:
        if entry["kind"] == "bulk_record":
            caller = json.loads(entry["provenance"])["caller"]
            assert not {"workspace", "wing", "room"}.intersection(caller)
    assert artifact_fingerprint(d) == original
    oversized = make_fixture(tmp_path / "oversized", "oversized")
    d = oversized["descriptor"]
    original = artifact_fingerprint(d)
    before = migration.initial_source_cursor(
        migration.registration(d, str(tmp_path / "destination"))
    )
    result = source_slice(d, before)
    assert (
        result["status"] == "qualification_required" and result["reason"] == "native_metadata_size"
    ), result
    assert (
        result["cursor_after"] == before and not result["entries"] and not result["finalizations"]
    )
    assert not any(result["counts"].values())
    assert artifact_fingerprint(d) == original


@pytest.mark.skipif(sys.platform != "darwin", reason="owned supervision")
def test_native_canonical_reuse_keeps_original_exposure_across_bindings(tmp_path):
    from cognitive_castle import migration_codec as migration
    from test_bulk_exact_store import invoke as exact

    generation = tmp_path / "generation"
    generation.mkdir(mode=0o700)
    first = make_fixture(tmp_path / "first", "single")
    second = make_fixture(tmp_path / "second", "single")
    assert first["rows"][0]["records"] == second["rows"][0]["records"]
    original = artifact_fingerprint(first["descriptor"]), artifact_fingerprint(second["descriptor"])
    registrations = [
        migration.registration(f["descriptor"], str(generation)) for f in (first, second)
    ]
    assert registrations[0]["source_binding"] != registrations[1]["source_binding"]
    for reg in registrations:
        result, observed = native_tick(reg)
        assert result["status"] == "ok", result
        assert observed.calls.count("import_batch") == 2
    ids = [r["id"] for r in first["rows"][0]["records"]]
    found = exact(generation / "exact", "read_sources", {"ids": ids})
    assert found["status"] == "ok" and len(found["sources"]) == len(ids)
    for source, expected in zip(found["sources"], first["rows"][0]["records"]):
        assert {k: source[k] for k in ("id", "text", "provenance")} == expected
    for reg in registrations:
        owner = migration.bulk.owner_id(first["rows"][0]["occurrence"], reg["source_binding"])
        result = exact(
            generation / "exact", "bulk_page", {"owner": owner, "field": "descriptor", "ordinal": 0}
        )
        assert result["status"] == "ok" and json.loads(result["text"])["alias"] == "duplicate"
    assert (
        artifact_fingerprint(first["descriptor"]),
        artifact_fingerprint(second["descriptor"]),
    ) == original


@pytest.mark.skipif(sys.platform != "darwin", reason="owned supervision")
def test_native_invalid_json_metadata_refuses_with_fixed_worker_chain(tmp_path):
    from cognitive_castle import migration_codec as migration

    fixture = make_fixture(tmp_path / "invalid", "invalid_metadata")
    d = fixture["descriptor"]
    original = artifact_fingerprint(d)
    before = migration.initial_source_cursor(
        migration.registration(d, str(tmp_path / "destination"))
    )
    result = source_slice(d, before)
    assert result["status"] == "corrupt" and result["reason"] == "native_source_contract", result
    assert result["cursor_after"] == before and result["entries"] == result["finalizations"] == []
    assert not result["complete"] and not result["phase_complete"]
    assert artifact_fingerprint(d) == original


if __name__ == "__main__":
    fixture_main()
