"""Layout transaction contracts; pure nodes never open a storage engine."""

import copy
import json
import os
from pathlib import Path
import sys


def _fixture_worker():
    """Fixed metadata-only fault injection, exclusively under the real guardian."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from cognitive_castle import semantic_store_worker as worker
    from cognitive_castle.lance_layout_directory import LayoutDirectory, readonly_directory
    from cognitive_castle.lance_exact_store import _StoreError
    from cognitive_castle.semantic_profile import decode_frame, canonical_json
    from cognitive_castle.semantic_queue import SemanticQueue

    os.umask(0o077)
    request = decode_frame(sys.stdin.buffer.read(worker.MAX_FRAME + 1))
    actions = {
        "rollback_ack",
        "lost_ack_reply",
        "snapshot",
        "readonly_routes",
        "lose_routes",
        "lose_partition",
        "change_plan",
        "lose_attachment",
        "change_envelope",
        "unknown_schema",
        "oversized_attachment",
    }
    if (
        request.keys() != {"directory", "operation", "arguments", "_host_pid"}
        or request["operation"] not in actions
    ):
        raise ValueError("fixed fixture action")
    worker._install_guards("queue")
    refused = worker._admit(request, "queue")
    if refused:
        return refused
    import sqlite3

    with sqlite3.connect(":memory:") as conn:
        assert 0 < conn.execute("PRAGMA hard_heap_limit=16777216").fetchone()[0] <= 16777216
    directory, action, args = Path(request["directory"]), request["operation"], request["arguments"]
    if not directory.is_absolute():
        raise ValueError("fixture generation")
    if action == "readonly_routes":
        if args.keys() != {"ids"}:
            raise ValueError("fixture routes")
        try:
            with readonly_directory(directory) as layout:
                assert 0 < layout.conn.execute("PRAGMA hard_heap_limit").fetchone()[0] <= 16777216
                return layout.routes(args["ids"])
        except (OSError, ValueError, sqlite3.DatabaseError, _StoreError):
            return {"status": "unavailable"}
    store = SemanticQueue(directory, writable=True)
    if action == "lost_ack_reply":
        if args.keys() != {"job_id", "intent_id", "verified_summary"}:
            raise ValueError("fixture lost reply")
        committed = store.layout_ack(**args)
        return {"status": "reply_lost"} if committed["status"] == "ok" else committed

    def operation(conn):
        if action == "rollback_ack":
            if args.keys() != {"job_id", "intent_id", "verified_summary"}:
                raise ValueError("fixture ack")
            LayoutDirectory(conn).ack(**args)
            raise _StoreError("injected_rollback")
        if args.keys() != {"job_id"}:
            raise ValueError("fixture job")
        job_id = args["job_id"]
        if action == "snapshot":
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            objects = conn.execute(
                "SELECT count(*) FROM sqlite_master WHERE name LIKE 'layout_%'"
            ).fetchone()[0]
            return {"status": "ok", "version": version, "layout_objects": objects}
        if action == "lose_routes":
            conn.execute("DROP TABLE layout_routes")
        elif action == "unknown_schema":
            conn.execute("CREATE TABLE unexpected_probe (value TEXT)")
        elif action == "lose_partition":
            conn.execute("DELETE FROM layout_partitions")
        elif action == "lose_attachment":
            conn.execute(
                "UPDATE migration_jobs SET layout_attachment=NULL WHERE job_id=?", (job_id,)
            )
        elif action == "change_envelope":
            value = json.loads(
                conn.execute(
                    "SELECT envelope FROM layout_jobs WHERE job_id=?", (job_id,)
                ).fetchone()[0]
            )
            value["qualification_hash"] = "f" * 64
            conn.execute(
                "UPDATE layout_jobs SET envelope=? WHERE job_id=?", (canonical_json(value), job_id)
            )
        elif action == "oversized_attachment":
            marker = conn.execute(
                "SELECT layout_attachment FROM migration_jobs WHERE job_id=?", (job_id,)
            ).fetchone()[0]
            conn.execute(
                "UPDATE migration_jobs SET layout_attachment=? WHERE job_id=?",
                (marker + "\0" + "x" * 1024, job_id),
            )
        elif action == "change_plan":
            value = json.loads(
                conn.execute(
                    "SELECT plan FROM layout_homes WHERE job_id=? LIMIT 1", (job_id,)
                ).fetchone()[0]
            )
            value["expansion"]["physical_rows"] += 1
            conn.execute(
                "UPDATE layout_homes SET plan=? WHERE job_id=?", (canonical_json(value), job_id)
            )
        return {"status": "ok"}

    return store._run(action != "snapshot", operation)


if __name__ == "__main__":
    try:
        output = _fixture_worker()
    except Exception as exc:
        output = {"status": "unavailable", "reason": "fixture_" + type(exc).__name__}
    raw = json.dumps(output, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode()
    if len(raw) > 512 * 1024:
        raw = b'{"status":"unavailable"}'
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()
    raise SystemExit

import pytest  # noqa: E402 - guarded script exits before pytest/test-fixture imports.

from test_lance_layout_codec import fixture  # noqa: E402


def test_protocol_layout_routes_is_read_only_pure(monkeypatch):
    from cognitive_castle import semantic_runtime, semantic_store_worker

    names = {
        "queue_layout_bind": {"job_id", "plans", "envelope"},
        "queue_layout_prepare": {"job_id", "expected_cursor", "intent"},
        "queue_layout_ack": {"job_id", "intent_id", "verified_summary"},
        "queue_layout_routes": {"ids"},
    }
    for name, fields in names.items():
        assert semantic_store_worker._FIELDS[name] == (fields, set())
    session = semantic_runtime.SemanticSession(Path("/private/profile"))
    monkeypatch.setattr(session, "_run_stage", lambda request, **kwargs: kwargs)
    result = session.store(Path("/private/generation"), "queue_layout_routes", {"ids": []})
    assert result["cap"] == 2 and result["rss"] == 128 * 1024**2
    assert semantic_store_worker.QUEUE_READS == {"status", "migration_state", "layout_routes"}


def test_layout_guard_precedes_v1_decode_and_ack_replay_pure(monkeypatch):
    from cognitive_castle import semantic_queue as queue
    from cognitive_castle.lance_layout_directory import LayoutDirectory
    from cognitive_castle.lance_exact_store import _StoreError

    layout, migration, reg, _, _, _, _ = fixture()
    row = dict(registration=json.dumps(reg), pending="NOT V1 JSON")
    store = queue.SemanticQueue(Path(reg["destination"]), writable=True)
    monkeypatch.setattr(store, "_run", lambda write, operation: operation(object()))
    monkeypatch.setattr(store, "_migration_row", lambda conn, identity: row)
    monkeypatch.setattr(
        LayoutDirectory, "attachment", lambda self, identity: {"format": layout.ATTACHMENT}
    )
    for method, args in (
        (store.migration_prepare, (reg["job_id"], migration.initial_source_cursor(reg), {})),
        (store.migration_ack, (reg["job_id"], "a" * 64, {})),
    ):
        with pytest.raises(_StoreError) as exc:
            method(*args)
        assert exc.value.status == "conflict"


def test_incomplete_directory_never_proves_absence_pure(monkeypatch):
    from cognitive_castle.lance_layout_directory import LayoutDirectory
    from cognitive_castle.lance_exact_store import _StoreError

    directory = LayoutDirectory(object())
    monkeypatch.setattr(
        directory, "_schema", lambda: (_ for _ in ()).throw(_StoreError("unavailable"))
    )
    with pytest.raises(_StoreError) as exc:
        directory.routes(["memory:" + "a" * 64])
    assert exc.value.status == "unavailable"
    for ids in ([], ["memory:" + "a" * 64] * 257, ["not-an-id"]):
        with pytest.raises(ValueError):
            directory.routes(ids)


def test_frozen_pending_conflict_has_no_mutation_pure(monkeypatch):
    from cognitive_castle.lance_layout_directory import LayoutDirectory
    from cognitive_castle.lance_exact_store import _StoreError

    layout, migration, reg, result, _, _, target = fixture()
    intent = layout.prepare_layout_interval(reg, result, target)
    state = dict(
        registration=reg, pending=intent, staging_cursor=intent["cursor_before"], state="active"
    )
    directory = LayoutDirectory(object())
    monkeypatch.setattr(directory, "_state", lambda job_id: state)
    changed = copy.deepcopy(intent)
    changed["digest"] = "b" * 64
    with pytest.raises(_StoreError) as exc:
        directory.prepare(reg["job_id"], intent["cursor_before"], changed)
    assert exc.value.status == "conflict"
    assert state["pending"] == intent
    assert migration.validate_registration(reg) == reg


def test_first_bind_refuses_legacy_progress_pure():
    from cognitive_castle.lance_layout_directory import validate_first_bind
    from cognitive_castle.lance_exact_store import _StoreError

    _, migration, reg, result, _, _, _ = fixture()
    before = migration.initial_source_cursor(reg)
    row = dict(
        staging_cursor=json.dumps(before),
        completed_frontier=json.dumps(before),
        counts=json.dumps(migration.empty_counts()),
        pending=None,
        owner_references=0,
        semantic_pending=0,
        last_ack=None,
        last_refusal=None,
        state="active",
        coverage="incomplete",
    )
    validate_first_bind(row, reg)
    for field, value in (
        ("staging_cursor", json.dumps(result["cursor_after"])),
        ("completed_frontier", json.dumps(result["cursor_after"])),
        ("owner_references", 1),
        ("semantic_pending", 1),
        ("last_ack", "{}"),
        ("pending", "{}"),
        ("state", "snapshot_export_exhausted"),
        ("counts", json.dumps(result["counts"])),
    ):
        with pytest.raises(_StoreError) as exc:
            validate_first_bind({**row, field: value}, reg)
        assert exc.value.status == "conflict"


def test_authoritative_marker_blocks_decode_without_derived_authority_pure():
    from cognitive_castle.semantic_queue import SemanticQueue
    from cognitive_castle.lance_exact_store import _StoreError

    layout, _, _, _, _, _, _ = fixture()
    row = dict(
        layout_attachment=json.dumps(dict(format=layout.ATTACHMENT, envelope_hash="a" * 64)),
        registration="NOT REGISTRATION JSON",
        pending="NOT V1 JSON",
    )
    with pytest.raises(_StoreError) as exc:
        SemanticQueue._migration_state(row)
    assert exc.value.status == "unavailable"


def test_version4_requires_exact_attachment_column_pure():
    from cognitive_castle.lance_layout_directory import require_attachment_column
    from cognitive_castle.lance_exact_store import _StoreError

    names = [
        "job_id",
        "registration",
        "staging_cursor",
        "completed_frontier",
        "pending",
        "counts",
        "coverage",
        "state",
        "last_ack",
        "last_refusal",
        "owner_references",
        "semantic_pending",
        "layout_attachment",
    ]
    nullable = {"job_id", "pending", "last_ack", "last_refusal", "layout_attachment"}
    columns = [
        (
            i,
            name,
            "INTEGER" if name in {"owner_references", "semantic_pending"} else "TEXT",
            int(name not in nullable),
            "0" if name in {"owner_references", "semantic_pending"} else None,
            int(name == "job_id"),
        )
        for i, name in enumerate(names)
    ]

    class Conn:
        rows = columns
        indexes = [(0, "sqlite_autoindex_migration_jobs_1", 1, "pk", 0)]
        keys = [(0, 0, "job_id", 0, "BINARY", 1), (1, -1, None, 0, "BINARY", 0)]

        def execute(self, sql):
            self.sql = sql
            return self

        def fetchone(self):
            return (1000,)

        def fetchall(self):
            return [(34,)]

        def fetchmany(self, count):
            if self.sql == "PRAGMA table_info(migration_jobs)":
                return self.rows
            if self.sql == "PRAGMA index_list(migration_jobs)":
                return self.indexes
            assert self.sql == "PRAGMA index_xinfo(sqlite_autoindex_migration_jobs_1)"
            return self.keys

    conn = Conn()
    require_attachment_column(conn)
    for ordinal, part, bad in (
        (0, 5, 0),
        (0, 2, "INTEGER"),
        (1, 3, 0),
        (10, 4, None),
        (12, 2, "BLOB"),
    ):
        mutant = [list(row) for row in columns]
        mutant[ordinal][part] = bad
        conn.rows = mutant
        with pytest.raises(_StoreError) as exc:
            require_attachment_column(conn)
        assert exc.value.status == "unavailable"
    conn.rows = columns
    conn.indexes = [(0, "sqlite_autoindex_migration_jobs_1", 0, "pk", 0)]
    with pytest.raises(_StoreError):
        require_attachment_column(conn)
    conn.indexes = Conn.indexes
    conn.keys = [(0, 1, "registration", 0, "BINARY", 1), (1, -1, None, 0, "BINARY", 0)]
    with pytest.raises(_StoreError):
        require_attachment_column(conn)


def test_route_requires_its_own_job_authority_pure(monkeypatch):
    from cognitive_castle.lance_layout_directory import LayoutDirectory
    from cognitive_castle.lance_exact_store import _StoreError

    layout, migration, _, result, plan, _, target = fixture()
    owner = plan["owner"]

    class Conn:
        def execute(self, sql, arguments):
            assert "FROM layout_homes" in sql and arguments == (owner,)
            return self

        def fetchone(self):
            return (1, 0, "b" * 64, migration.hashed(plan), json.dumps(plan))

    directory = LayoutDirectory(Conn())
    called = []

    def missing(identity):
        called.append(identity)
        raise _StoreError("unavailable")

    monkeypatch.setattr(directory, "_state", missing)
    row = dict(state="staged", gate=owner, partition_id=target["partition_id"], job_id="b" * 64)
    with pytest.raises(_StoreError) as exc:
        directory._route(row, {"a" * 64: True})
    assert exc.value.status == "unavailable" and called == ["b" * 64]


def test_pending_binds_authoritative_envelope_pure():
    layout, migration, reg, result, _, envelope, target = fixture()
    intent = layout.prepare_layout_interval(reg, result, target)
    attachment = dict(
        format=layout.ATTACHMENT, envelope_hash=migration.hashed(envelope), envelope=envelope
    )
    assert migration.validate_pending(intent, reg, attachment) == intent
    other = {**envelope, "qualification_hash": "e" * 64}
    attachment = dict(
        format=layout.ATTACHMENT, envelope_hash=migration.hashed(other), envelope=other
    )
    with pytest.raises(ValueError):
        migration.validate_pending(intent, reg, attachment)


def test_layout_terminal_ack_preserves_original_progress_pure(monkeypatch):
    from cognitive_castle.lance_layout_directory import LayoutDirectory
    from cognitive_castle.lance_exact_store import _StoreError

    _, migration, reg, _, _, _, _ = fixture()
    before = migration.initial_source_cursor(reg)
    state = dict(
        registration=reg,
        staging_cursor=before,
        completed_frontier=before,
        counts=migration.empty_counts(),
        state="active",
        pending=None,
        last_ack=None,
    )
    summary = dict(
        state="snapshot_export_exhausted",
        cursor_before=before,
        cursor_after={**before, "phase": "done", "key": None},
        coverage="incomplete",
    )

    class Conn:
        unresolved = False
        writes = 0

        def execute(self, sql, arguments):
            if sql.startswith("UPDATE"):
                self.writes += 1
            return self

        def fetchone(self):
            return (1,) if self.unresolved else None

    conn = Conn()
    directory = LayoutDirectory(conn)
    monkeypatch.setattr(directory, "_state", lambda identity: state)
    conn.unresolved = True
    with pytest.raises(_StoreError) as exc:
        directory.ack(reg["job_id"], None, summary)
    assert exc.value.status == "conflict" and conn.writes == 0
    conn.unresolved = False
    result = directory.ack(reg["job_id"], None, summary)
    assert result["staging_cursor"] == summary["cursor_after"]
    assert result["completed_frontier"] == before and conn.writes == 1
    state["last_ack"] = dict(intent_id=None, summary_hash=migration.hashed(summary), result=result)
    assert directory.ack(reg["job_id"], None, summary) == result and conn.writes == 1


def test_home_plan_hash_and_partition_reservation_pure(monkeypatch):
    from cognitive_castle.lance_layout_directory import LayoutDirectory
    from cognitive_castle.lance_exact_store import _StoreError

    layout, migration, reg, result, plan, envelope, target = fixture()
    intent = layout.prepare_layout_interval(reg, result, target)
    state = dict(registration=reg, layout=dict(envelope=envelope))

    class Conn:
        value = (plan["owner"], reg["job_id"], json.dumps(plan), 0, 0)

        def execute(self, sql, arguments):
            return self

        def fetchone(self):
            return self.value

    conn = Conn()
    directory = LayoutDirectory(conn)
    monkeypatch.setattr(directory, "_partition", lambda pid, env: plan["expansion"])
    assert directory._target(state, intent) == conn.value
    changed = copy.deepcopy(plan)
    changed["expansion"]["physical_rows"] += 1
    conn.value = (plan["owner"], reg["job_id"], json.dumps(changed), 0, 0)
    with pytest.raises(_StoreError) as exc:
        directory._target(state, intent)
    assert exc.value.status == "unavailable"


def test_missing_or_excess_partition_reservation_pure():
    from cognitive_castle.lance_layout_directory import LayoutDirectory
    from cognitive_castle.lance_exact_store import _StoreError

    _, migration, _, _, plan, envelope, _ = fixture()

    class Conn:
        value = None

        def execute(self, sql, arguments):
            assert "length(CAST(reservation AS BLOB))<=4096" in sql
            return self

        def fetchone(self):
            return self.value

    conn = Conn()
    directory = LayoutDirectory(conn)
    with pytest.raises(_StoreError):
        directory._partition(0, envelope)
    conn.value = (migration.hashed(envelope), json.dumps(plan["expansion"]))
    assert directory._partition(0, envelope) == plan["expansion"]
    over = {**plan["expansion"], "physical_rows": envelope["limits"]["physical_rows"] + 1}
    conn.value = (migration.hashed(envelope), json.dumps(over))
    with pytest.raises(_StoreError) as exc:
        directory._partition(0, envelope)
    assert exc.value.status == "unavailable"


@pytest.mark.parametrize("damage", ["symlink", "hardlink", "unknown_entry"])
def test_metadata_paths_refuse_untrusted_files_pure(tmp_path, damage):
    from cognitive_castle.lance_layout_directory import _metadata_paths
    from cognitive_castle.lance_exact_store import _StoreError

    generation = tmp_path.resolve() / "generation"
    generation.mkdir(mode=0o700)
    coordination = generation / "coordination"
    coordination.mkdir(mode=0o700)
    queue = coordination / "queue.sqlite3"
    queue.touch(mode=0o600)
    _metadata_paths(generation)
    if damage == "symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(generation, target_is_directory=True)
        generation = alias
    elif damage == "hardlink":
        os.link(queue, tmp_path / "extra-link")
    else:
        (coordination / "unexpected").touch(mode=0o600)
    with pytest.raises(_StoreError) as exc:
        _metadata_paths(generation)
    assert exc.value.status == "unavailable"


def test_version4_loss_refuses_before_legacy_creation_pure(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from cognitive_castle.lance_layout_directory import LayoutDirectory
    from cognitive_castle.lance_exact_store import _StoreError
    from cognitive_castle.semantic_queue import SemanticQueue

    class Conn:
        def execute(self, sql):
            assert not sql.startswith("CREATE"), "must validate schema4 before legacy repair"
            return self

        def fetchone(self):
            return (4,)

        def close(self):
            pass

    monkeypatch.setitem(
        sys.modules, "sqlite3", SimpleNamespace(connect=lambda *a, **k: Conn(), Row=object)
    )
    store = SemanticQueue(tmp_path / "generation", writable=True)
    monkeypatch.setattr(store, "_paths", lambda write: None)
    monkeypatch.setattr(
        LayoutDirectory, "_schema", lambda self: (_ for _ in ()).throw(_StoreError("unavailable"))
    )
    with pytest.raises(_StoreError) as exc, store._connection(True):
        pytest.fail("missing schema must not yield a transaction")
    assert exc.value.status == "unavailable"


_NATIVE_CALLS = 0


def _invoke(generation, operation, arguments, *, fixture_action=False):
    """One bounded metadata operation; no retry and no native exact/source store."""
    from cognitive_castle.semantic_runtime import SemanticSession

    global _NATIVE_CALLS
    _NATIVE_CALLS += 1
    assert _NATIVE_CALLS <= 96
    session = SemanticSession(Path("/private/unused-layout-fixture-profile"), interactive=False)
    result = {}
    try:
        with session:
            if fixture_action:
                read = operation in {"snapshot", "readonly_routes"}
                result = session._run_stage(
                    dict(directory=str(generation), operation=operation, arguments=arguments),
                    worker_command=[sys.executable, "-I", str(Path(__file__).resolve())],
                    cap=2 if read else 3,
                    rss=128 * 1024**2,
                    total=192 * 1024**2,
                )
            else:
                result = session.store(generation, operation, arguments)
    finally:
        assert len(session.resources) <= 1
        current = session.resources[0] if session.resources else None
        metrics = (
            None
            if current is None
            else {
                k: current[k]
                for k in ("peak_task_rss_bytes", "peak_total_rss_bytes", "elapsed_seconds")
            }
        )
        line = json.dumps(
            dict(
                call=_NATIVE_CALLS,
                operation=operation,
                status=result.get("status", "host_exception"),
                reason=result.get("reason"),
                stage_metrics=metrics,
            ),
            separators=(",", ":"),
        )
        assert len(line.encode()) <= 512
        print("LAYOUT_META_STAGE " + line, flush=True)
    # Negative protocol cases must actually reach a fresh supervised stage;
    # pressure/admission/deadline refusals cannot masquerade as expected failures.
    assert len(session.resources) == 1, result
    assert result.get("reason") is None, result
    assert result.get("status") in {
        "ok",
        "conflict",
        "unavailable",
        "injected_rollback",
        "reply_lost",
    }, result
    return result


def _native_fixture(tmp_path):
    from cognitive_castle import migration_codec as migration
    from test_migration_codec import descriptor, exported

    generation = tmp_path / "generation"
    generation.mkdir(mode=0o700)
    reg = migration.registration(descriptor(), str(generation))
    result = exported(reg)
    layout = fixture()[0]
    plan = layout.owner_plan(
        reg,
        migration.owner_reference(
            result["finalizations"][0], result["phase"], result["cursor_after"]["key"]
        ),
        {k: 100000 for k in layout.EXPANSION},
    )
    info = generation.stat()
    envelope = dict(
        format=layout.ENVELOPE,
        generation=dict(path=str(generation), device=info.st_dev, inode=info.st_ino),
        qualification_hash="a" * 64,
        max_partitions=4,
        limits={k: 1000000 for k in layout.EXPANSION},
    )
    opened = _invoke(generation, "queue_migration_open", dict(registration=reg))
    assert opened["status"] == "ok", opened
    return generation, layout, migration, reg, result, plan, envelope


def _bind(data):
    generation, _, _, reg, _, plan, envelope = data
    result = _invoke(
        generation, "queue_layout_bind", dict(job_id=reg["job_id"], plans=[plan], envelope=envelope)
    )
    assert result["status"] == "ok", result
    assert not (generation / "exact").exists()
    return result


def _proof(layout, intent, version):
    """Synthetic metadata proof for queue atomicity, never a Lance proof claim."""
    routes = [
        {
            **r,
            "format": layout.ROUTE,
            "row_hash": r["row_hash"] or "c" * 64,
            "partition_id": intent["target"]["partition_id"],
            "version": version,
            "receipt": layout.batch_receipt_id(intent),
            "state": "staged",
        }
        for r in intent["routes"]
    ]
    proofs = [
        dict(
            owner=o["owner"],
            manifest_hash=o["manifest_hash"],
            partition_id=intent["target"]["partition_id"],
            version=version,
            live_receipt_ids=o["live_receipt_ids"],
        )
        for o in intent["owners"]
    ]
    return layout.verified_summary(
        intent,
        dict(
            format=layout.BATCH_RESULT,
            outcome="existing_verified",
            receipt=layout.expected_receipt(intent),
            routes=routes,
        ),
        proofs,
    )


def _prepare(generation, reg, intent):
    return _invoke(
        generation,
        "queue_layout_prepare",
        dict(job_id=reg["job_id"], expected_cursor=intent["cursor_before"], intent=intent),
    )


@pytest.mark.skipif(sys.platform != "darwin", reason="owned queue supervision")
def test_layout_bind_prepare_ack_is_atomic_and_idempotent(tmp_path):
    data = _native_fixture(tmp_path)
    generation, layout, migration, reg, exported, _, _ = data
    bound = _bind(data)
    assert _bind(data) == bound
    intent = layout.prepare_layout_interval(reg, exported, bound["targets"][0])
    assert _prepare(generation, reg, intent)["status"] == "ok"
    assert _prepare(generation, reg, intent)["status"] == "ok"
    assert _prepare(generation, reg, {**intent, "digest": "d" * 64})["status"] == "conflict"
    state_before = _invoke(generation, "queue_migration_state", dict(job_id=reg["job_id"]))
    ack = dict(
        job_id=reg["job_id"],
        intent_id=intent["intent_id"],
        verified_summary=_proof(layout, intent, 7),
    )
    assert (
        _invoke(generation, "rollback_ack", ack, fixture_action=True)["status"]
        == "injected_rollback"
    )
    assert _invoke(generation, "queue_migration_state", dict(job_id=reg["job_id"])) == state_before
    ids = [r["id"] for r in intent["routes"]]
    assert _invoke(generation, "queue_layout_routes", dict(ids=ids))["routes"] == []
    # The caller can lose the first real reply; a repeated ACK must not recount.
    assert _invoke(generation, "lost_ack_reply", ack, fixture_action=True)["status"] == "reply_lost"
    committed = _invoke(generation, "queue_layout_ack", ack)
    assert committed["status"] == "ok", committed
    state = _invoke(generation, "queue_migration_state", dict(job_id=reg["job_id"]))
    assert state["pending"] is None and state["owner_references"] == state["semantic_pending"] == 1
    assert (
        state["counts"] == exported["counts"]
        and state["completed_frontier"] == intent["cursor_after"]
    )
    assert _invoke(generation, "queue_migration_ack", ack)["status"] == "conflict"
    routes = _invoke(generation, "readonly_routes", dict(ids=ids), fixture_action=True)
    assert routes["status"] == "ok" and len(routes["routes"]) == len(ids)
    before = state["staging_cursor"]
    terminal = dict(
        job_id=reg["job_id"],
        intent_id=None,
        verified_summary=dict(
            state="snapshot_export_exhausted",
            cursor_before=before,
            cursor_after={**migration.initial_source_cursor(reg), "phase": "done", "key": None},
            coverage="incomplete",
        ),
    )
    assert (
        _invoke(generation, "lost_ack_reply", terminal, fixture_action=True)["status"]
        == "reply_lost"
    )
    done = _invoke(generation, "queue_layout_ack", terminal)
    assert done["status"] == "ok" and done["state"] == "snapshot_export_exhausted", done
    final = _invoke(generation, "queue_migration_state", dict(job_id=reg["job_id"]))
    assert final["semantic_pending"] == final["owner_references"] == 1
    assert not (generation / "exact").exists()
    path = generation / "coordination" / "queue.sqlite3"
    assert path.stat().st_size < 2 * 1024**2
    raw = path.read_bytes()
    for sentinel in (
        b"BODY_SENTINEL",
        b"METADATA_SENTINEL",
        b"SCOPE_SENTINEL",
        b"DESCRIPTOR_SENTINEL",
    ):
        assert sentinel not in raw
    assert not {"sqlite3", "lance", "pyarrow", "numpy"}.intersection(sys.modules)
    alias = tmp_path / "symlink-generation"
    alias.symlink_to(generation, target_is_directory=True)
    assert (
        _invoke(alias, "readonly_routes", dict(ids=ids), fixture_action=True)["status"]
        == "unavailable"
    )
    assert (
        _invoke(
            generation / ".." / "generation", "readonly_routes", dict(ids=ids), fixture_action=True
        )["status"]
        == "unavailable"
    )
    empty = tmp_path / "empty-generation"
    empty.mkdir(mode=0o700)
    (empty / "coordination").mkdir(mode=0o700)
    empty_db = empty / "coordination" / "queue.sqlite3"
    empty_db.touch(mode=0o600)
    assert (
        _invoke(empty, "readonly_routes", dict(ids=ids), fixture_action=True)["status"]
        == "unavailable"
    )
    os.link(empty_db, tmp_path / "extra-link")
    assert (
        _invoke(empty, "readonly_routes", dict(ids=ids), fixture_action=True)["status"]
        == "unavailable"
    )


@pytest.mark.skipif(sys.platform != "darwin", reason="owned queue supervision")
def test_stage_gate_and_unresolved_absence(tmp_path):
    data = _native_fixture(tmp_path)
    generation, layout, migration, reg, exported, _, _ = data
    target = _bind(data)["targets"][0]
    staged = copy.deepcopy(exported)
    staged.update(finalizations=[], counts=migration.empty_counts(), phase_complete=False)
    staged["cursor_after"].update(owner="owner", entry=len(staged["entries"]), field="finalization")
    for _ in range(3):
        staged["frame_bytes"] = len(migration.frame_bytes(staged))
    intent = layout.prepare_layout_interval(reg, staged, target)
    assert _prepare(generation, reg, intent)["status"] == "ok"
    ack = dict(
        job_id=reg["job_id"],
        intent_id=intent["intent_id"],
        verified_summary=_proof(layout, intent, 1),
    )
    assert _invoke(generation, "queue_layout_ack", ack)["status"] == "ok"
    ids = [intent["routes"][0]["id"], "memory:" + "f" * 64]
    hidden = _invoke(generation, "queue_layout_routes", dict(ids=ids))
    assert hidden == dict(status="unavailable", routes=[], unavailable=ids)
    final = copy.deepcopy(exported)
    final.update(cursor_before=staged["cursor_after"], entries=[])
    for _ in range(3):
        final["frame_bytes"] = len(migration.frame_bytes(final))
    intent = layout.prepare_layout_interval(reg, final, target)
    assert _prepare(generation, reg, intent)["status"] == "ok"
    ack = dict(
        job_id=reg["job_id"],
        intent_id=intent["intent_id"],
        verified_summary=_proof(layout, intent, 2),
    )
    assert _invoke(generation, "queue_layout_ack", ack)["status"] == "ok"
    visible = _invoke(generation, "queue_layout_routes", dict(ids=ids))
    assert len(visible["routes"]) == 1 and visible["routes"][0]["version"] == 1
    assert visible["unavailable"] == ids[1:] and visible["status"] == "unavailable"


@pytest.mark.skipif(sys.platform != "darwin", reason="owned queue supervision")
def test_failed_reservation_never_creates_partition(tmp_path):
    data = _native_fixture(tmp_path)
    generation, _, _, reg, _, plan, envelope = data
    too_large = copy.deepcopy(plan)
    too_large["expansion"]["physical_rows"] = envelope["limits"]["physical_rows"] + 1
    result = _invoke(
        generation,
        "queue_layout_bind",
        dict(job_id=reg["job_id"], plans=[too_large], envelope=envelope),
    )
    assert result["status"] == "conflict", result
    assert _invoke(generation, "snapshot", dict(job_id=reg["job_id"]), fixture_action=True) == dict(
        status="ok", version=3, layout_objects=0
    )
    wrong = copy.deepcopy(envelope)
    wrong["generation"]["inode"] += 1
    assert (
        _invoke(
            generation,
            "queue_layout_bind",
            dict(job_id=reg["job_id"], plans=[plan], envelope=wrong),
        )["status"]
        == "conflict"
    )
    _bind(data)
    assert not (generation / "exact").exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="owned queue supervision")
@pytest.mark.parametrize(
    "damage",
    [
        "lose_routes",
        "lose_partition",
        "change_plan",
        "lose_attachment",
        "change_envelope",
        "unknown_schema",
        "oversized_attachment",
    ],
)
def test_v1_queue_and_pending_compatibility(tmp_path, damage):
    data = _native_fixture(tmp_path)
    generation, layout, _, reg, exported, _, _ = data
    target = _bind(data)["targets"][0]
    intent = layout.prepare_layout_interval(reg, exported, target)
    assert _prepare(generation, reg, intent)["status"] == "ok"
    ack = dict(
        job_id=reg["job_id"],
        intent_id=intent["intent_id"],
        verified_summary=_proof(layout, intent, 1),
    )
    assert _invoke(generation, "queue_layout_ack", ack)["status"] == "ok"
    assert (
        _invoke(generation, damage, dict(job_id=reg["job_id"]), fixture_action=True)["status"]
        == "ok"
    )
    ids = [intent["routes"][0]["id"]]
    assert _invoke(generation, "queue_layout_routes", dict(ids=ids))["status"] != "ok"
    # Even its matching old ACK must not fall through to the v1 replay shortcut.
    assert _invoke(generation, "queue_migration_ack", ack)["status"] != "ok"


@pytest.mark.skipif(sys.platform != "darwin", reason="owned queue supervision")
def test_v1_pending_survives_other_job_layout_upgrade(tmp_path):
    data = _native_fixture(tmp_path)
    generation, layout, migration, reg, exported, plan, envelope = data
    intent = migration.prepare_interval(reg, exported)
    assert (
        _invoke(
            generation,
            "queue_migration_prepare",
            dict(job_id=reg["job_id"], expected_cursor=intent["cursor_before"], intent=intent),
        )["status"]
        == "ok"
    )
    # Upgrade the SAME queue while the original legacy pending interval survives.
    from test_migration_codec import descriptor, exported as source_export

    second_descriptor = descriptor()
    second_descriptor["snapshot_id"] = "second-snapshot"
    second = migration.registration(second_descriptor, str(generation))
    second_export = source_export(second)
    second_plan = layout.owner_plan(
        second,
        migration.owner_reference(
            second_export["finalizations"][0],
            second_export["phase"],
            second_export["cursor_after"]["key"],
        ),
        plan["expansion"],
    )
    assert _invoke(generation, "queue_migration_open", dict(registration=second))["status"] == "ok"
    assert (
        _invoke(
            generation,
            "queue_layout_bind",
            dict(job_id=second["job_id"], plans=[second_plan], envelope=envelope),
        )["status"]
        == "ok"
    )
    pending = _invoke(generation, "queue_migration_state", dict(job_id=reg["job_id"]))
    assert pending["pending"] == intent and "layout" not in pending
    ack = dict(
        job_id=reg["job_id"],
        intent_id=intent["intent_id"],
        verified_summary=migration.verified_summary(intent, [1]),
    )
    result = _invoke(generation, "queue_migration_ack", ack)
    assert result["status"] == "ok" and _invoke(generation, "queue_migration_ack", ack) == result
    assert (
        _invoke(
            generation,
            "queue_layout_bind",
            dict(job_id=reg["job_id"], plans=[plan], envelope=envelope),
        )["status"]
        == "conflict"
    )
    assert _invoke(generation, "snapshot", dict(job_id=reg["job_id"]), fixture_action=True) == dict(
        status="ok", version=4, layout_objects=6
    )
    final = _invoke(generation, "queue_migration_state", dict(job_id=reg["job_id"]))
    assert (
        "layout" not in final and final["pending"] is None and final["counts"] == exported["counts"]
    )
    assert final["last_ack"]["result"] == result
