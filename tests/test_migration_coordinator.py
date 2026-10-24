"""Inactive fixture-only coordination; engines stay in supervised workers."""

import copy
import json
import sys
from pathlib import Path

import pytest

from test_migration_codec import descriptor, exported


def test_coordinator_module_is_inactive_and_engine_free():
    from cognitive_castle.migration_coordinator import _fixture_tick

    assert callable(_fixture_tick)
    assert not {"sqlite3", "lance", "pyarrow", "numpy", "torch"}.intersection(sys.modules)


@pytest.mark.skipif(sys.platform != "darwin", reason="owned supervision")
def test_queue_prepare_restart_ack_is_atomic_body_free_and_task2_compatible(tmp_path):
    from cognitive_castle import migration_codec as codec
    from test_semantic_queue import invoke, registration as task2_registration

    generation = tmp_path / "generation"
    generation.mkdir(mode=0o700)
    reg = codec.registration(descriptor(), str(generation))
    intent = codec.prepare_interval(reg, exported(reg))
    first = invoke(generation, "queue_migration_open", {"registration": reg})
    assert first["status"] == "ok", first
    assert first["pending"] is None and first["counts"]["members"] == 0
    assert invoke(generation, "queue_migration_open", {"registration": reg}) == first
    changed = {**reg, "destination": str(tmp_path / "other")}
    assert invoke(generation, "queue_migration_open", {"registration": changed})["status"] != "ok"
    arguments = dict(job_id=reg["job_id"], expected_cursor=first["staging_cursor"], intent=intent)
    assert invoke(generation, "queue_migration_prepare", arguments)["status"] == "ok"
    assert invoke(generation, "queue_migration_prepare", arguments)["status"] == "ok"
    assert (
        invoke(
            generation,
            "queue_migration_prepare",
            {**arguments, "intent": {**intent, "digest": "b" * 64}},
        )["status"]
        == "conflict"
    )
    state = invoke(generation, "queue_migration_state", {"job_id": reg["job_id"]})
    assert state["pending"] == intent and state["staging_cursor"] == first["staging_cursor"]
    summary = codec.verified_summary(intent, [1])
    ack = dict(job_id=reg["job_id"], intent_id=intent["intent_id"], verified_summary=summary)
    committed = invoke(generation, "queue_migration_ack", ack)
    assert committed["status"] == "ok", committed
    assert invoke(generation, "queue_migration_ack", ack) == committed
    assert (
        invoke(generation, "queue_migration_ack", {**ack, "intent_id": "e" * 64})["status"]
        == "conflict"
    )
    state = invoke(generation, "queue_migration_state", {"job_id": reg["job_id"]})
    assert state["pending"] is None
    assert state["staging_cursor"] == state["completed_frontier"] == intent["cursor_after"]
    assert state["counts"]["historical_occurrences"] == 1
    assert state["last_ack"]["result"] == committed
    assert state["owner_references"] == 1
    assert invoke(generation, "queue_register", task2_registration())["status"] == "ok"
    assert invoke(generation, "queue_status")["counts"]["pending"] == 1
    raw = (generation / "coordination/queue.sqlite3").read_bytes()
    for forbidden in (
        b"BODY_SENTINEL",
        b"METADATA_SENTINEL",
        b"SCOPE_SENTINEL",
        b"DESCRIPTOR_SENTINEL",
    ):
        assert forbidden not in raw
    assert not {"sqlite3", "lance", "pyarrow", "numpy"}.intersection(sys.modules)


def test_append_requires_checked_existing_replay_before_ack_and_reuses_export():
    """A fake boundary is limited to protocol ordering; real workers below prove IO."""
    from cognitive_castle import migration_codec as codec
    from cognitive_castle.migration_coordinator import _fixture_tick
    from cognitive_castle.sqlite_export_codec import initial_cursor, empty_counts

    reg = codec.registration(descriptor(), "/private/generation")
    result = exported(reg)
    intent = codec.prepare_interval(reg, result)
    calls = []

    class Session:
        remaining = 5

        def _ready(self):
            return None

        def sqlite_source(self, *args):
            calls.append("source")
            return result

        def store(self, directory, op, args):
            calls.append(op)
            if op == "queue_migration_open":
                start = initial_cursor(reg["source_binding"], "store")
                return dict(
                    status="ok",
                    registration=reg,
                    pending=None,
                    staging_cursor=start,
                    completed_frontier=start,
                    counts=empty_counts(),
                    state="active",
                )
            if op == "queue_migration_prepare":
                return dict(status="ok", intent_id=intent["intent_id"])
            if op == "queue_migration_ack":
                return dict(status="ok", intent_id=intent["intent_id"])
            return {"status": "ok"}

        def exact(self, directory, op, args):
            calls.append(op)
            if op == "import_batch":
                assert args["entries"] is result["entries"]
                return codec.expected_receipt(intent)
            assert op == "bulk_owner"
            return dict(status="ok", manifest=result["finalizations"][0], version=1)

    assert _fixture_tick(Session(), reg)["status"] == "ok"
    assert calls == [
        "queue_migration_open",
        "source",
        "queue_migration_prepare",
        "import_batch",
        "import_batch",
        "bulk_owner",
        "queue_migration_ack",
    ]


class FixtureInterruption(Exception):
    pass


class ObservedSession:
    """Test-only fault boundary around an actual owned SemanticSession."""

    def __init__(self, session, *, stop=None, loss=None):
        self.session, self.stop, self.loss = session, stop, loss
        self.calls = []
        self.arguments = {}
        self.counts = {}

    def _ready(self):
        return self.session._ready()

    def call(self, name, function, *args):
        self.counts[name] = self.counts.get(name, 0) + 1
        point = name + ":" + str(self.counts[name])
        if self.stop == "before:" + point:
            raise FixtureInterruption(point)
        result = function(*args)
        self.calls.append(name)
        self.arguments[point] = args
        print(
            "MIGRATION_STAGE",
            json.dumps(
                dict(
                    operation=point,
                    status=result.get("status"),
                    reason=result.get("reason"),
                    resources=self.session.resources[-1] if self.session.resources else None,
                    frame_bytes=result.get("frame_bytes"),
                )
            ),
            flush=True,
        )
        if self.stop == "after:" + point:
            raise FixtureInterruption(point)
        if self.loss == point:
            return dict(status="unavailable", reason="fixture_lost_response")
        return result

    def store(self, directory, operation, arguments):
        return self.call(operation, self.session.store, directory, operation, arguments)

    def exact(self, directory, operation, arguments):
        return self.call(operation, self.session.exact, directory, operation, arguments)

    def sqlite_source(self, descriptor, cursor):
        return self.call("source", self.session.sqlite_source, descriptor, cursor)


def fixture_tick(reg, *, stop=None, loss=None):
    import time
    from cognitive_castle.semantic_runtime import SemanticSession
    from cognitive_castle.migration_coordinator import _fixture_tick

    started = time.monotonic()
    with SemanticSession(Path(reg["destination"]) / "unused-profile", interactive=False) as session:
        observed = ObservedSession(session, stop=stop, loss=loss)
        try:
            result = _fixture_tick(observed, reg)
        except FixtureInterruption:
            result = {"status": "fixture_interruption"}
        print(
            "MIGRATION_TICK",
            json.dumps(
                dict(
                    status=result.get("status"),
                    reason=result.get("reason"),
                    phase=result.get("phase"),
                    elapsed=time.monotonic() - started,
                    resources=session.resources,
                )
            ),
            flush=True,
        )
        assert time.monotonic() - started < 5.5
    return result, observed


def queue_state(reg):
    from test_semantic_queue import invoke

    return invoke(Path(reg["destination"]), "queue_migration_state", {"job_id": reg["job_id"]})


@pytest.mark.skipif(sys.platform != "darwin", reason="owned supervision")
def test_real_worker_restart_export_prepare_commit_owner_live_and_lost_ack(tmp_path):
    from cognitive_castle import migration_codec as codec
    from test_sqlite_source_export import fixture
    from test_semantic_queue import invoke
    from test_bulk_exact_store import invoke as exact

    source = fixture(tmp_path)
    generation = tmp_path / "generation"
    generation.mkdir(mode=0o700)
    reg = codec.registration(source["descriptor"], str(generation))
    assert fixture_tick(reg, stop="after:source:1")[0]["status"] == "fixture_interruption"
    initial = queue_state(reg)
    assert initial["pending"] is None and initial["counts"]["live_owners"] == 0
    assert fixture_tick(reg, stop="before:import_batch:1")[0]["status"] == "fixture_interruption"
    prepared = queue_state(reg)
    pending = prepared["pending"]
    assert pending is not None
    assert prepared["staging_cursor"] == initial["staging_cursor"]
    assert not (generation / "exact").exists()
    lost, _ = fixture_tick(reg, loss="import_batch:1")
    assert lost["status"] == "unavailable" and lost["phase"] == "publish", lost
    assert queue_state(reg)["pending"] == pending
    assert fixture_tick(reg, stop="after:bulk_owner:1")[0]["status"] == "fixture_interruption"
    assert queue_state(reg)["counts"]["live_owners"] == 0
    assert fixture_tick(reg, stop="after:receipt:1")[0]["status"] == "fixture_interruption"
    assert queue_state(reg)["completed_frontier"] == initial["completed_frontier"]
    lost, observed = fixture_tick(reg, loss="queue_migration_ack:1")
    assert lost["status"] == "unavailable", lost
    committed = queue_state(reg)
    assert committed["pending"] is None and committed["counts"]["live_owners"] == 1
    assert committed["counts"]["members"] == 9
    assert committed["owner_references"] == committed["semantic_pending"] == 1
    ack_args = observed.arguments["queue_migration_ack:1"][-1]
    assert invoke(generation, "queue_migration_ack", ack_args) == committed["last_ack"]["result"]
    assert queue_state(reg)["counts"] == committed["counts"]
    receipt = exact(
        generation / "exact",
        "receipt",
        {"namespace": pending["cursor_after"]["key"][0], "key": pending["cursor_after"]["key"][1]},
    )
    assert receipt["receipt"] == source["receipt"]
    text = ("a" * 8191 + "€") * 7 + "b" * 8178
    assert (
        exact(
            generation / "exact",
            "remember",
            {
                "request_id": "nine",
                "namespace": pending["cursor_after"]["key"][0],
                "text": text,
                "provenance": {"workspace": "original", "note": "\x00"},
            },
        )
        == source["receipt"]
    )
    raw = (generation / "coordination/queue.sqlite3").read_bytes()
    for forbidden in (
        b"a" * 256,
        b"DESCRIPTOR_SENTINEL",
        b"conflict_offset",
        b"original_primary_key",
    ):
        assert forbidden not in raw
    assert not {"sqlite3", "lance", "pyarrow", "numpy"}.intersection(sys.modules)


def test_retained_original_receipt_retry_and_body_sentinels():
    """Only explicitly selected disposable output of the interrupted fixture."""
    import os
    from cognitive_castle.canonical_records import prepare_remember
    from test_bulk_exact_store import invoke as exact

    selected = os.environ.get("CASTLE_TEST_MIGRATION_RETAINED")
    if not selected:
        pytest.skip("requires explicit retained disposable generation")
    generation = Path(selected)
    text = ("a" * 8191 + "€") * 7 + "b" * 8178
    prepared = prepare_remember(
        "nine", text, {"workspace": "original", "note": "\x00"}, namespace="operator"
    )
    receipt = exact(
        generation / "exact",
        "receipt",
        {"namespace": prepared.namespace, "key": prepared.request_id},
    )
    assert receipt == dict(status="ok", digest=prepared.digest, receipt=prepared.receipt)
    assert (
        exact(
            generation / "exact",
            "remember",
            {
                "request_id": prepared.request_id,
                "namespace": prepared.namespace,
                "text": text,
                "provenance": {"workspace": "original", "note": "\x00"},
            },
        )
        == prepared.receipt
    )
    raw = (generation / "coordination/queue.sqlite3").read_bytes()
    for forbidden in (
        b"a" * 256,
        b"DESCRIPTOR_SENTINEL",
        b"conflict_offset",
        b"original_primary_key",
    ):
        assert forbidden not in raw
    assert not {"sqlite3", "lance", "pyarrow", "numpy"}.intersection(sys.modules)


@pytest.mark.skipif(sys.platform != "darwin", reason="owned supervision")
@pytest.mark.parametrize("inventory", ["empty", "orphan"])
def test_real_no_content_exhaustion_and_orphan_refusal(tmp_path, inventory):
    from cognitive_castle import migration_codec as codec
    from test_sqlite_source_export import fixture

    source = fixture(tmp_path, migration_inventory=inventory)
    generation = tmp_path / "generation"
    generation.mkdir(mode=0o700)
    reg = codec.registration(source["descriptor"], str(generation))
    result, observed = fixture_tick(reg)
    state = queue_state(reg)
    assert "import_batch" not in observed.calls and not (generation / "exact").exists()
    if inventory == "empty":
        assert result["status"] == "ok" and result["state"] == "snapshot_export_exhausted", result
        assert state["staging_cursor"]["phase"] == "done"
        assert state["completed_frontier"]["phase"] == "live"
        assert state["owner_references"] == 0
    else:
        assert result["status"] != "ok" and result["reason"].startswith("orphan"), result
        assert state["state"] == "refused" and state["pending"] is None
        assert state["staging_cursor"] == state["completed_frontier"]
        assert state["counts"]["orphans"] == 1
    assert state["counts"]["historical_occurrences"] == state["counts"]["audit_owners"] == 0
    assert not {"sqlite3", "lance", "pyarrow", "numpy"}.intersection(sys.modules)


@pytest.mark.skipif(sys.platform != "darwin", reason="owned supervision")
def test_real_multibatch_staging_visibility_and_completed_frontier(tmp_path):
    from cognitive_castle import migration_codec as codec
    from test_sqlite_source_export import fixture
    from test_bulk_exact_store import invoke as exact

    source = fixture(tmp_path, migration_inventory="staging", large=45000)
    generation = tmp_path / "generation"
    generation.mkdir(mode=0o700)
    reg = codec.registration(source["descriptor"], str(generation))
    result, observed = fixture_tick(reg, loss="import_batch:1")
    assert result["status"] == "unavailable", result
    state = queue_state(reg)
    pending = state["pending"]
    assert pending and not pending["owners"]
    assert state["staging_cursor"] == state["completed_frontier"]
    owner = pending["cursor_after"]["owner"]
    assert (
        exact(
            generation / "exact",
            "bulk_owner",
            {"owner": codec.bulk.owner_id(owner, reg["source_binding"])},
        )["status"]
        == "not_found"
    )
    assert (
        exact(generation / "exact", "read_sources", {"ids": source["history"][0]["ids"]})["status"]
        == "not_found"
    )
    first, _ = fixture_tick(reg)
    assert first["status"] == "ok", first
    state = queue_state(reg)
    assert state["staging_cursor"] == pending["cursor_after"]
    assert state["completed_frontier"] == pending["cursor_before"]
    assert state["counts"]["historical_occurrences"] == state["owner_references"] == 0
    for _ in range(8):
        if state["counts"]["historical_occurrences"]:
            break
        result, observed = fixture_tick(reg)
        assert result["status"] == "ok", result
        state = queue_state(reg)
    assert state["counts"]["historical_occurrences"] == state["owner_references"] == 1
    assert state["semantic_pending"] == 1
    assert state["staging_cursor"] == state["completed_frontier"]
    read = exact(generation / "exact", "read_sources", {"ids": source["history"][0]["ids"]})
    assert read["status"] == "ok" and read["sources"][0]["text"] == source["history"][0]["text"]
    assert not {"sqlite3", "lance", "pyarrow", "numpy"}.intersection(sys.modules)


@pytest.mark.skipif(sys.platform != "darwin", reason="owned supervision")
def test_real_empty_history_audit_gap_repair_pending_and_exhaustion(tmp_path):
    from cognitive_castle import migration_codec as codec
    from test_sqlite_source_export import fixture

    source = fixture(tmp_path, migration_inventory="protocol", mode="repaired")
    generation = tmp_path / "generation"
    generation.mkdir(mode=0o700)
    reg = codec.registration(source["descriptor"], str(generation))
    dispositions = []
    for _ in range(18):
        result, observed = fixture_tick(reg)
        assert result["status"] == "ok", result
        for name, args in observed.arguments.items():
            if name == "queue_migration_prepare:1":
                dispositions.extend(args[-1]["intent"]["owners"])
        state = queue_state(reg)
        if state["state"] == "snapshot_export_exhausted":
            break
    assert state["state"] == "snapshot_export_exhausted"
    assert state["counts"] == dict(
        live_owners=0,
        historical_occurrences=3,
        audit_owners=10,
        members=2,
        gaps=1,
        repaired_gaps=1,
        pending_stages=1,
        orphans=0,
    )
    assert state["owner_references"] == 13 and state["semantic_pending"] == 2
    empty = [o for o in dispositions if o["classification"] == "history" and o["members"] == 0]
    audit = [o for o in dispositions if o["classification"] == "audit"]
    assert len(empty) == 1 and empty[0]["semantic_disposition"] == "no_members"
    assert len(audit) == 10 and all(o["semantic_disposition"] == "audit_only" for o in audit)
    assert state["coverage"] == "incomplete"
    assert (
        state["staging_cursor"]["phase"] == "done"
        and state["completed_frontier"]["phase"] == "audit"
    )
    assert b"z" * 256 not in (generation / "coordination/queue.sqlite3").read_bytes()
    assert not {"sqlite3", "lance", "pyarrow", "numpy"}.intersection(sys.modules)


def test_retained_protocol_continues_only_pending_after_real_preemption():
    import os
    import hashlib
    from cognitive_castle import memory_runtime, migration_codec as codec
    from cognitive_castle.sqlite_export_codec import file_identity, FORMAT

    selected = os.environ.get("CASTLE_TEST_MIGRATION_PROTOCOL")
    if not selected:
        pytest.skip("requires explicit retained disposable fixture")
    assert not memory_runtime.interactive_waiting()
    root = Path(selected)
    source = root / "source"
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    # Reconstruct the same registered metadata, never reseal or modify files.
    descriptor = dict(
        format=FORMAT,
        store_id=manifest["store_id"],
        snapshot_id=manifest["snapshot_id"],
        path=str(source / "memory.sqlite3"),
        identity=manifest["identity"],
        manifest_path=str(manifest_path),
        manifest_identity=file_identity(manifest_path.stat()),
        manifest_hash=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    )
    reg = codec.registration(descriptor, str(root / "generation"))
    state = queue_state(reg)
    assert state["status"] == "ok", state
    assert state["pending"] is not None
    assert state["counts"]["historical_occurrences"] == 3 and state["counts"]["audit_owners"] == 5
    prior_cursor = state["staging_cursor"]
    pending = state["pending"]
    for _ in range(7):
        result, observed = fixture_tick(reg)
        assert result["status"] == "ok", result
        state = queue_state(reg)
        if state["state"] == "snapshot_export_exhausted":
            break
    assert state["counts"] == dict(
        live_owners=0,
        historical_occurrences=3,
        audit_owners=10,
        members=2,
        gaps=1,
        repaired_gaps=1,
        pending_stages=1,
        orphans=0,
    )
    assert state["state"] == "snapshot_export_exhausted" and state["pending"] is None
    assert state["owner_references"] == 13 and state["semantic_pending"] == 2
    assert state["coverage"] == "incomplete"
    assert (
        state["staging_cursor"]["phase"] == "done"
        and state["completed_frontier"]["phase"] == "audit"
    )
    assert pending["cursor_before"] == prior_cursor
    raw = (root / "generation/coordination/queue.sqlite3").read_bytes()
    assert b"z" * 256 not in raw
    print("FINAL_PROTOCOL_STATE", json.dumps(state), flush=True)
    assert not {"sqlite3", "lance", "pyarrow", "numpy"}.intersection(sys.modules)


class ProtocolSession:
    """Pure host decision testing, without pretending to qualify durable IO."""

    def __init__(self, reg, result, *, pending=None, failure=None, late=False):
        from cognitive_castle import migration_codec as codec
        from cognitive_castle.sqlite_export_codec import empty_counts, initial_cursor

        self.reg, self.result = reg, result
        self.intent = pending or codec.prepare_interval(reg, result)
        start = initial_cursor(reg["source_binding"], "store")
        self.state = dict(
            status="ok",
            registration=reg,
            pending=pending,
            staging_cursor=start,
            completed_frontier=start,
            counts=empty_counts(),
            state="active",
        )
        self.failure, self.late, self.expired = failure, late, False
        self.calls = []
        self.imports = 0

    def _ready(self):
        return dict(status="unavailable", reason="semantic_deadline") if self.expired else None

    def sqlite_source(self, *args):
        self.calls.append("source")
        return self.result

    def store(self, directory, op, args):
        self.calls.append(op)
        if op == "queue_migration_open":
            return self.state
        if op == "queue_migration_prepare":
            return (
                self.failure[1]
                if self.failure and self.failure[0] == "prepare"
                else dict(status="ok", intent_id=self.intent["intent_id"])
            )
        return dict(status="ok")

    def exact(self, directory, op, args):
        from cognitive_castle import migration_codec as codec

        self.calls.append(op)
        if op == "import_batch":
            self.imports += 1
            if self.failure and self.failure[0] == str(self.imports):
                return self.failure[1]
            return codec.expected_receipt(self.intent)
        if op == "bulk_owner":
            self.expired = self.late
            return (
                self.failure[1]
                if self.failure and self.failure[0] == "owner"
                else dict(status="ok", manifest=self.result["finalizations"][0], version=1)
            )
        if op == "receipt":
            live = self.result["finalizations"][0]["live"]
            return (
                self.failure[1]
                if self.failure and self.failure[0] == "live"
                else dict(status="ok", digest=live["digest"], receipt=live["receipt"])
            )
        raise AssertionError(op)


@pytest.mark.parametrize(
    "phase,status",
    [
        ("prepare", "unavailable"),
        ("1", "index_required"),
        ("2", "corrupt"),
        ("2", "not_found"),
        ("2", "not_initialized"),
        ("2", "maintenance_limit"),
        ("owner", "stale"),
    ],
)
def test_refusals_never_ack_or_build_indexes_or_start_new_sessions(phase, status):
    from cognitive_castle import migration_codec as codec
    from cognitive_castle.migration_coordinator import _fixture_tick

    reg = codec.registration(descriptor(), "/private/generation")
    boundary = ProtocolSession(reg, exported(reg), failure=(phase, dict(status=status)))
    result = _fixture_tick(boundary, reg)
    assert result["status"] == status
    assert result["cursor_after"] == result["cursor_before"]
    assert "queue_migration_ack" not in boundary.calls
    assert "build_id_index" not in boundary.calls
    assert boundary.calls.count("source") == 1
    if phase == "prepare":
        assert boundary.imports == 0


def test_late_owner_success_cannot_authorize_ack_or_cleanup_lease():
    from cognitive_castle import migration_codec as codec
    from cognitive_castle.migration_coordinator import _fixture_tick

    reg = codec.registration(descriptor(), "/private/generation")
    boundary = ProtocolSession(reg, exported(reg), late=True)
    result = _fixture_tick(boundary, reg)
    assert result["reason"] == "semantic_deadline"
    assert "queue_migration_ack" not in boundary.calls
    assert "queue_migration_refuse" not in boundary.calls


@pytest.mark.parametrize("change", ["body", "manifest", "packing", "binding"])
def test_pending_regeneration_changes_stop_before_destination_writes(change):
    from cognitive_castle import migration_codec as codec
    from cognitive_castle.migration_coordinator import _fixture_tick

    reg = codec.registration(descriptor(), "/private/generation")
    original = exported(reg)
    pending = codec.prepare_interval(reg, original)
    result = copy.deepcopy(original)
    if change == "body":
        result = exported(reg, text="changed body")
    elif change == "manifest":
        result["finalizations"][0]["text_hash"] = "f" * 64
    elif change == "packing":
        result["cursor_after"]["packing"] = "other"
    else:
        result["source_binding"] = "d" * 64
    boundary = ProtocolSession(reg, result, pending=pending)
    refused = _fixture_tick(boundary, reg)
    assert refused["status"] == "conflict"
    assert boundary.imports == 0 and "queue_migration_ack" not in boundary.calls
    assert boundary.state["pending"] == pending


@pytest.mark.skipif(sys.platform != "darwin", reason="owned supervision")
@pytest.mark.parametrize("damage", ["delete", "drop_proof", "replace_proof"])
def test_real_proof_damage_blocks_ack_and_reused_legacy_semantics(tmp_path, damage):
    from cognitive_castle import migration_codec as codec
    from test_sqlite_source_export import fixture
    from test_bulk_exact_store import invoke as exact

    source = fixture(tmp_path)
    generation = tmp_path / "generation"
    generation.mkdir(mode=0o700)
    reg = codec.registration(source["descriptor"], str(generation))
    if damage == "replace_proof":
        text = ("a" * 8191 + "€") * 7 + "b" * 8178
        assert (
            exact(
                generation / "exact",
                "remember",
                {
                    "request_id": "nine",
                    "text": text,
                    "provenance": {"workspace": "original", "note": "\x00"},
                },
            )
            == source["receipt"]
        )
        result, observed = fixture_tick(reg, stop="before:queue_migration_ack:1")
        assert result["status"] == "fixture_interruption"
        assert (
            observed.calls[-1] == "receipt"
        )  # Actual replay/owner/live checks completed against legacy record rows.
    else:
        result, observed = fixture_tick(reg, loss="import_batch:1")
        assert result["status"] == "unavailable", result
    before = queue_state(reg)
    pending = before["pending"]
    identity = (
        source["receipt"]["ids"][0]
        if damage == "delete"
        else codec.bulk.key("batch", pending["intent_id"])
    )
    assert exact(generation / "exact", fixture=damage, arguments={"id": identity})["status"] == "ok"
    result, observed = fixture_tick(reg)
    assert result["status"] == "corrupt", result
    assert "queue_migration_ack" not in observed.calls
    after = queue_state(reg)
    assert after["pending"] == pending
    assert after["staging_cursor"] == before["staging_cursor"]
    assert after["completed_frontier"] == before["completed_frontier"]
    assert after["counts"]["live_owners"] == after["owner_references"] == 0
    assert (generation / "exact/records.lance").exists()
    assert not {"sqlite3", "lance", "pyarrow", "numpy"}.intersection(sys.modules)


@pytest.mark.skipif(sys.platform != "darwin", reason="owned supervision")
def test_real_source_replacement_preserves_pending_without_destination_write(tmp_path):
    import os
    import shutil
    from cognitive_castle import migration_codec as codec
    from test_sqlite_source_export import fixture

    source = fixture(tmp_path)
    generation = tmp_path / "generation"
    generation.mkdir(mode=0o700)
    reg = codec.registration(source["descriptor"], str(generation))
    assert fixture_tick(reg, stop="before:import_batch:1")[0]["status"] == "fixture_interruption"
    before = queue_state(reg)
    # Deliberate fixture tampering, never bless/reseal a changed protected view.
    path = Path(source["descriptor"]["path"])
    replacement = path.with_name("replacement")
    shutil.copyfile(path, replacement)
    replacement.chmod(0o600)
    with replacement.open("rb") as handle:
        os.fsync(handle.fileno())
    replacement.replace(path)
    result, observed = fixture_tick(reg)
    assert result["status"] == "stale", result
    assert result["reason"] == "source_identity_changed"
    assert "import_batch" not in observed.calls
    after = queue_state(reg)
    assert after["pending"] == before["pending"]
    assert after["staging_cursor"] == after["completed_frontier"] == before["staging_cursor"]
    assert not (generation / "exact").exists()


def test_changed_original_live_receipt_and_owner_manifest_refuse_before_ack():
    from cognitive_castle import migration_codec as codec
    from cognitive_castle.migration_coordinator import _fixture_tick

    reg = codec.registration(descriptor(), "/private/generation")
    original = exported(reg, phase="live")
    pending = codec.prepare_interval(reg, original)
    changed = copy.deepcopy(original)
    changed["finalizations"][0]["live"]["digest"] = "e" * 64
    # Account honestly for the changed ephemeral response; the pending request
    # digest/owner manifest still binds the original live receipt.
    from cognitive_castle.sqlite_export_codec import frame_bytes

    for _ in range(3):
        changed["frame_bytes"] = len(frame_bytes(changed))
    boundary = ProtocolSession(reg, changed, pending=pending)
    assert _fixture_tick(boundary, reg)["status"] == "conflict"
    assert boundary.imports == 0
    for failure in (
        (
            "live",
            dict(
                status="ok",
                digest="e" * 64,
                receipt=original["finalizations"][0]["live"]["receipt"],
            ),
        ),
        (
            "owner",
            dict(
                status="ok",
                version=1,
                manifest={**original["finalizations"][0], "text_hash": "f" * 64},
            ),
        ),
    ):
        boundary = ProtocolSession(reg, original, failure=failure)
        assert _fixture_tick(boundary, reg)["status"] == "conflict"
        assert "queue_migration_ack" not in boundary.calls


def test_immutable_registration_rebind_conflicts_before_storage_or_admission():
    from cognitive_castle import migration_codec as codec
    from cognitive_castle.semantic_queue import SemanticQueue
    from cognitive_castle.sqlite_export_codec import source_binding

    reg = codec.registration(descriptor(), "/private/generation")
    changed = copy.deepcopy(reg)
    changed["descriptor"]["manifest_hash"] = "b" * 64
    changed["source_binding"] = source_binding(changed["descriptor"])
    assert SemanticQueue(Path(reg["destination"]), writable=True).migration_open(changed) == {
        "status": "conflict"
    }


def test_orphan_refusal_return_retains_observed_orphan_counter():
    from cognitive_castle import migration_codec as codec
    from cognitive_castle.migration_coordinator import _fixture_tick
    from cognitive_castle.sqlite_export_codec import empty_counts

    reg = codec.registration(descriptor(), "/private/generation")
    boundary = ProtocolSession(reg, exported(reg))
    before = boundary.state["staging_cursor"]
    boundary.result = dict(
        status="incomplete",
        reason="orphan_chunk",
        source_binding=reg["source_binding"],
        cursor_before=before,
        cursor_after=before,
        entries=[],
        finalizations=[],
        counts={**empty_counts(), "orphans": 1},
        phase="orphans",
        phase_complete=False,
        complete=False,
        coverage="incomplete",
        frame_bytes=0,
    )
    result = _fixture_tick(boundary, reg)
    assert result["counts"]["orphans"] == 1


@pytest.mark.skipif(sys.platform != "darwin", reason="owned supervision")
def test_queue_orphan_scan_exhaustion_ack_conflicts_without_advancing(tmp_path):
    from cognitive_castle import migration_codec as codec
    from cognitive_castle.sqlite_export_codec import initial_cursor
    from test_semantic_queue import invoke

    generation = tmp_path / "generation"
    generation.mkdir(mode=0o700)
    reg = codec.registration(descriptor(), str(generation))
    state = invoke(generation, "queue_migration_open", {"registration": reg})
    before = state["staging_cursor"]
    refusal = dict(
        status="incomplete",
        reason="orphan_chunk",
        phase="orphans",
        refused_operation="orphan_scan",
        refused_field=None,
        orphans=1,
    )
    assert (
        invoke(
            generation,
            "queue_migration_refuse",
            dict(job_id=reg["job_id"], expected_cursor=before, refusal=refusal),
        )["status"]
        == "ok"
    )
    done = {**initial_cursor(reg["source_binding"], "store"), "phase": "done"}
    ack = dict(
        job_id=reg["job_id"],
        intent_id=None,
        verified_summary=dict(
            state="snapshot_export_exhausted",
            cursor_before=before,
            cursor_after=done,
            coverage="incomplete",
        ),
    )
    assert invoke(generation, "queue_migration_ack", ack) == {"status": "conflict"}
    state = queue_state(reg)
    assert state["state"] == "refused" and state["counts"]["orphans"] == 1
    assert state["staging_cursor"] == state["completed_frontier"] == before
    assert state["last_ack"] is None and state["pending"] is None
