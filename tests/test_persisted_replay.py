"""Pure private replay protocol; real engines require a separate root grant."""

import importlib
import importlib.util
import os
from types import SimpleNamespace

import pytest

from cognitive_castle import migration_codec as migration
from test_migration_codec import descriptor, exported


def protocol():
    assert importlib.util.find_spec("cognitive_castle.persisted_replay") is not None, (
        "private replay protocol is missing"
    )
    return importlib.import_module("cognitive_castle.persisted_replay")


def test_nonposix_case_skips_before_creating_private_fixture(tmp_path, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(os, "name", "nt")
        with pytest.raises(pytest.skip.Exception):
            case(tmp_path)
    assert not list(tmp_path.iterdir())


def case(tmp_path):
    if os.name != "posix":
        pytest.skip("private qualified POSIX path identities")
    generation = tmp_path / "generation"
    exact = generation / "exact"
    generation.mkdir(mode=0o700)
    exact.mkdir(mode=0o700)
    reg = migration.registration(descriptor(), str(generation))
    source = exported(reg)
    intent = migration.prepare_interval(reg, source)
    arguments = dict(
        batch_id=intent["intent_id"],
        source_binding=reg["source_binding"],
        entries=source["entries"],
        finalizations=source["finalizations"],
    )
    return reg, source, intent, arguments, exact


@pytest.mark.parametrize(
    "damage",
    [
        None,
        "tag",
        "extra",
        "source",
        "batch",
        "digest",
        "ids",
        "version",
        "destination",
        "generation",
        "parent",
        "directory",
        "receipt",
        "inode_bool",
        "owner_count_bool",
        "entries_bool",
        "witness_extra",
    ],
)
def test_private_replay_witness_is_strict_and_binds_current_generation(tmp_path, damage):
    p = protocol()
    reg, source, intent, arguments, exact = case(tmp_path)
    expected = migration.expected_receipt(intent)
    ids = p.expected_ids(arguments["entries"], arguments["finalizations"])
    value = p.existing_outcome(expected, exact, reg["source_binding"], intent["intent_id"], ids, 7)
    if damage == "tag":
        value["outcome"] = "caller-asserted"
    elif damage == "extra":
        value["trusted"] = True
    elif damage == "source":
        value["witness"]["source_binding"] = "changed"
    elif damage == "batch":
        value["witness"]["batch_id"] = "b" * 64
    elif damage == "digest":
        value["witness"]["batch_digest"] = "b" * 64
    elif damage == "ids":
        value["witness"]["expected_ids_digest"] = "b" * 64
    elif damage == "version":
        value["witness"]["dataset_version"] = True
    elif damage in {"destination", "generation"}:
        value["witness"][damage] += "-changed"
    elif damage == "parent":
        value["witness"]["parent_identity"][1] += 1
    elif damage == "directory":
        value["witness"]["directory_identity"][1] += 1
    elif damage == "receipt":
        value["receipt"] = {**expected, "records": True}
    elif damage == "inode_bool":
        value["witness"]["directory_identity"][0] = True
    elif damage == "owner_count_bool":
        value["receipt"]["published_owners"] = True
    elif damage == "entries_bool":
        value["receipt"]["entries"] = True
    elif damage == "witness_extra":
        value["witness"]["trusted"] = True
    if damage is None:
        assert (
            p.validate_outcome(
                value, expected, exact, reg["source_binding"], intent["intent_id"], ids
            )
            == 7
        )
        assert p.ids_digest(ids) == p.ids_digest(reversed(sorted(ids)))
    else:
        with pytest.raises(ValueError):
            p.validate_outcome(
                value, expected, exact, reg["source_binding"], intent["intent_id"], ids
            )


@pytest.mark.parametrize(
    "outcomes",
    [("ExistingVerified",), ("FreshAppend", "ExistingVerified"), ("FreshAppend", "FreshAppend")],
)
def test_private_coordinator_uses_worker_outcome_and_pins_owner_version(tmp_path, outcomes):
    p = protocol()
    from cognitive_castle.migration_coordinator import _fixture_tick_persisted

    reg, source, intent, arguments, exact = case(tmp_path)
    calls = []
    expected = migration.expected_receipt(intent)
    ids = p.expected_ids(arguments["entries"], arguments["finalizations"])
    tags = iter(outcomes)

    class Session:
        remaining = 5

        def _ready(self):
            return None

        def sqlite_source(self, *args):
            return source

        def store(self, directory, operation, args):
            calls.append((operation, args))
            if operation == "queue_migration_open":
                return dict(
                    status="ok",
                    registration=reg,
                    state="active",
                    pending=intent,
                    staging_cursor=intent["cursor_before"],
                    counts={"orphans": 0},
                )
            return {"status": "ok"}

        def exact(self, directory, operation, args):
            calls.append((operation, args))
            if operation == "import_batch_outcome":
                return (
                    p.fresh_outcome(expected)
                    if next(tags) == "FreshAppend"
                    else p.existing_outcome(
                        expected, exact, reg["source_binding"], intent["intent_id"], ids, 7
                    )
                )
            assert operation == "bulk_owner" and args == {
                "owner": source["finalizations"][0]["owner"],
                "version": 7,
            }
            return {"status": "ok", "manifest": source["finalizations"][0], "version": 7}

    result = _fixture_tick_persisted(Session(), reg)
    names = [name for name, _ in calls]
    assert names.count("import_batch_outcome") == len(outcomes)
    if outcomes[-1] == "ExistingVerified":
        assert result["status"] == "ok" and names.count("queue_migration_ack") == 1
        ack = next(args for name, args in calls if name == "queue_migration_ack")
        assert ack["verified_summary"] == migration.verified_summary(intent, [7])
        assert "witness" not in str(ack)
    else:
        assert result["status"] != "ok" and "queue_migration_ack" not in names


@pytest.mark.parametrize("failure", [None, "proof", "source", "digest", "ids"])
def test_worker_constructs_witness_only_after_all_existing_branch_checks(
    tmp_path, monkeypatch, failure
):
    from contextlib import contextmanager
    from cognitive_castle import bulk_exact_store as stores
    from cognitive_castle.lance_exact_store import _StoreError

    p = protocol()
    reg, source, intent, arguments, exact = case(tmp_path)
    assert hasattr(stores, "_ReplayOutcomeStore"), (
        "private branch-established worker outcome is missing"
    )
    ids = p.expected_ids(arguments["entries"], arguments["finalizations"])
    receipt_id = stores.codec.key("batch", intent["intent_id"])
    manifest = {
        "state": "committed_batch",
        "source_binding": reg["source_binding"],
        "digest": stores.codec.validate_batch(**arguments),
        "proof": [[identity, "a" * 64] for identity in ids],
        "records": intent["records"],
        "published_owners": 1,
        "entries": intent["entries"],
    }
    if failure == "source":
        manifest["source_binding"] = "wrong"
    elif failure == "digest":
        manifest["digest"] = "a" * 64
    elif failure == "ids":
        manifest["proof"].pop()
    events = []

    @contextmanager
    def writer():
        events.append("locked")
        try:
            yield SimpleNamespace(version=7)
        finally:
            events.append("unlocked")

    def proof(*args):
        events.append("proof")
        if failure == "proof":
            raise _StoreError("corrupt")
        return manifest

    monkeypatch.setattr(stores, "coverage", lambda _: None)
    monkeypatch.setattr(stores, "lookup_many", lambda *a, **k: {receipt_id: {"stored": True}})
    for kind in (stores.BulkExactStore, stores._ReplayOutcomeStore):
        store = object.__new__(kind)
        store.directory = exact
        store.qualification = SimpleNamespace(
            source_binding=reg["source_binding"],
            parent_identity=tuple(p.directory_binding(exact)["parent_identity"]),
            destination_identity=tuple(p.directory_binding(exact)["directory_identity"]),
        )
        store._writer, store._verify_batch = writer, proof
        store._paths = lambda: events.append("bound_paths")
        outcome = store.import_batch(**arguments)
        if failure is not None:
            assert outcome["status"] != "ok" and "witness" not in outcome
        elif kind is stores.BulkExactStore:
            assert outcome == migration.expected_receipt(intent)
        else:
            assert (
                p.validate_outcome(
                    outcome,
                    migration.expected_receipt(intent),
                    exact,
                    reg["source_binding"],
                    intent["intent_id"],
                    ids,
                )
                == 7
            )
            assert events[-3:] == ["proof", "bound_paths", "unlocked"]
            fresh = store._fresh_import_result(manifest, receipt_id)
            assert (
                fresh == p.fresh_outcome(migration.expected_receipt(intent))
                and "witness" not in fresh
            )


@pytest.mark.parametrize(
    "fault",
    [
        "malformed",
        "lost_reply",
        "changed_pending",
        "bad_generation",
        "wrong_owner_version",
        "stale_owner",
        "wrong_manifest",
        "live_receipt",
        "expired",
    ],
)
def test_private_coordinator_refusals_never_ack_or_save_witness(tmp_path, fault):
    p = protocol()
    from cognitive_castle.migration_coordinator import _fixture_tick_persisted

    reg, source, intent, arguments, exact = case(tmp_path)
    if fault == "live_receipt":
        source = exported(reg, phase="live")
        intent = migration.prepare_interval(reg, source)
    expected = migration.expected_receipt(intent)
    ids = p.expected_ids(source["entries"], source["finalizations"])
    calls = []

    class Session:
        remaining = 5

        def _ready(self):
            return (
                {"status": "unavailable", "reason": "semantic_deadline"}
                if fault == "expired" and any(n == "bulk_owner" for n, _ in calls)
                else None
            )

        def sqlite_source(self, *args):
            return source

        def store(self, directory, operation, args):
            calls.append((operation, args))
            if operation == "queue_migration_open":
                pending = {**intent, "digest": "f" * 64} if fault == "changed_pending" else intent
                return dict(
                    status="ok",
                    registration=reg,
                    state="active",
                    pending=pending,
                    staging_cursor=intent["cursor_before"],
                    counts={"orphans": 0},
                )
            return {"status": "ok"}

        def exact(self, directory, operation, args):
            calls.append((operation, args))
            if operation == "import_batch_outcome":
                if fault == "malformed":
                    return None
                if fault == "lost_reply":
                    return {"status": "unavailable", "reason": "lost_reply"}
                result = p.existing_outcome(
                    expected, exact, reg["source_binding"], intent["intent_id"], ids, 7
                )
                if fault == "bad_generation":
                    result["witness"]["generation"] += "x"
                return result
            if operation == "receipt":
                live = source["finalizations"][0]["live"]
                return {"status": "ok", "digest": "f" * 64, "receipt": live["receipt"]}
            assert operation == "bulk_owner" and args["version"] == 7
            if fault == "stale_owner":
                return {"status": "stale"}
            return {
                "status": "ok",
                "manifest": {} if fault == "wrong_manifest" else source["finalizations"][0],
                "version": 8 if fault == "wrong_owner_version" else 7,
            }

    result = _fixture_tick_persisted(Session(), reg)
    assert result["status"] != "ok"
    assert not any(name == "queue_migration_ack" for name, _ in calls)
    assert all("witness" not in args for name, args in calls if name.startswith("queue_"))


def test_private_witness_refuses_replaced_or_symlinked_destination(tmp_path):
    p = protocol()
    reg, source, intent, arguments, exact = case(tmp_path)
    ids = p.expected_ids(arguments["entries"], arguments["finalizations"])
    expected = migration.expected_receipt(intent)
    result = p.existing_outcome(expected, exact, reg["source_binding"], intent["intent_id"], ids, 7)
    saved = exact.with_name("saved")
    exact.rename(saved)
    exact.mkdir(mode=0o700)
    with pytest.raises(ValueError):
        p.validate_outcome(result, expected, exact, reg["source_binding"], intent["intent_id"], ids)

    exact.rmdir()
    exact.symlink_to(saved, target_is_directory=True)
    with pytest.raises(ValueError):
        p.validate_outcome(result, expected, exact, reg["source_binding"], intent["intent_id"], ids)


def test_legacy_invalid_reply_never_reaches_owner_or_ack(tmp_path):
    from cognitive_castle.migration_coordinator import _fixture_tick

    reg, source, intent, arguments, exact = case(tmp_path)
    calls = []

    class Session:
        remaining = 5

        def _ready(self):
            return None

        def sqlite_source(self, *args):
            return source

        def store(self, directory, operation, args):
            calls.append(operation)
            if operation == "queue_migration_open":
                return dict(
                    status="ok",
                    registration=reg,
                    state="active",
                    pending=intent,
                    staging_cursor=intent["cursor_before"],
                    counts={"orphans": 0},
                )
            return {"status": "ok"}

        def exact(self, directory, operation, args):
            calls.append(operation)
            return (
                None
                if operation == "import_batch"
                else {"status": "ok", "manifest": source["finalizations"][0], "version": 7}
            )

    result = _fixture_tick(Session(), reg)
    assert result["status"] != "ok"
    assert "bulk_owner" not in calls and "queue_migration_ack" not in calls


def test_private_witness_does_not_turn_staging_into_owner_publication(tmp_path):
    p = protocol()
    reg, source, intent, arguments, exact = case(tmp_path)
    ids = {arguments["entries"][0]["id"]}
    expected = {
        "status": "ok",
        "state": "stage_batch",
        "receipt_id": "receipt:" + "a" * 64,
        "digest": "b" * 64,
        "records": 0,
        "published_owners": 0,
        "entries": 1,
    }
    result = p.existing_outcome(expected, exact, reg["source_binding"], intent["intent_id"], ids, 7)
    assert (
        p.validate_outcome(result, expected, exact, reg["source_binding"], intent["intent_id"], ids)
        == 7
    )
    result["receipt"]["published_owners"] = 1
    result["receipt"]["state"] = "committed_batch"
    with pytest.raises(ValueError):
        p.validate_outcome(result, expected, exact, reg["source_binding"], intent["intent_id"], ids)


def test_private_identity_hash_input_is_bounded_and_deadline_refuses(tmp_path):
    import time

    p = protocol()
    seen = []

    def unlimited():
        for index in range(514):
            seen.append(index)
            yield "memory:" + "a" * 64

    with pytest.raises(ValueError):
        p.ids_digest(unlimited())
    assert len(seen) == 513
    reg, source, intent, arguments, exact = case(tmp_path)
    ids = p.expected_ids(arguments["entries"], arguments["finalizations"])
    expected = migration.expected_receipt(intent)
    result = p.existing_outcome(expected, exact, reg["source_binding"], intent["intent_id"], ids, 7)
    with pytest.raises(ValueError):
        p.validate_outcome(
            result,
            expected,
            exact,
            reg["source_binding"],
            intent["intent_id"],
            ids,
            until=time.monotonic() - 1,
        )


def test_ordinary_worker_cannot_select_private_outcome_or_flag(tmp_path):
    import os
    from cognitive_castle.lance_exact_worker import _execute

    reg, source, intent, arguments, exact = case(tmp_path)
    for operation, fields in (
        ("import_batch_outcome", {}),
        ("import_batch", {**arguments, "outcome": "ExistingVerified"}),
    ):
        with pytest.raises(ValueError):
            _execute(
                {
                    "directory": str(tmp_path / "absent"),
                    "operation": operation,
                    "arguments": fields,
                    "_host_pid": os.getpid(),
                }
            )
    assert not (tmp_path / "absent").exists()
