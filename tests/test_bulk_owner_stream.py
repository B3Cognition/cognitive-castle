"""Pure ordered owner proofs; no native engine or fixture access."""

from copy import deepcopy
import importlib.util
import json

import pytest

from cognitive_castle import bulk_exact_codec as codec
from cognitive_castle.canonical_records import _hash, _json, prepare_remember
from cognitive_castle.lance_exact_store import _StoreError


def verify(*args, **kwargs):
    assert importlib.util.find_spec("cognitive_castle.bulk_owner_stream") is not None, (
        "the bounded single-pass owner verifier is missing"
    )
    from cognitive_castle.bulk_owner_stream import verify_owner_rows

    return verify_owner_rows(*args, **kwargs)


class SinglePass:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.count = 0

    def __iter__(self):
        return self

    def __next__(self):
        self.count += 1
        return next(self.rows)

    def __length_hint__(self):
        raise AssertionError("owner stream must not be materialized")


def unit():
    text = "ž😀\x00\r\n" * 2000 + "last"
    prepared = prepare_remember("ordered", text)
    fields = {
        "metadata": " \x00ž😀\n" * 3000,
        "columns": "",
        "scopes": "null\x00 ",
        "descriptor": "{}\n",
    }
    rows, manifest = codec.prepare_owner("ordered", "snapshot", prepared.records, **fields)
    return rows, manifest, prepared, text, fields


def no_reuse(ids):
    assert len(ids) <= 32
    return {}


def decoded_store_proof(rows, manifest, pending, monkeypatch):
    from types import SimpleNamespace
    from cognitive_castle.bulk_exact_store import OrderedBulkExactStore

    store = object.__new__(OrderedBulkExactStore)
    store.qualification = SimpleNamespace(
        owner=manifest["owner"],
        source_binding=manifest["source_binding"],
        max_physical_rows=128,
        max_batch_receipts=8,
    )
    monkeypatch.setattr(store, "_geometry", lambda _: {"physical_rows": len(rows)})

    def scanner(**options):
        assert options["strict_batch_size"] and options["batch_size"] == 32
        return SimpleNamespace(
            to_batches=lambda: (
                SimpleNamespace(to_pylist=lambda row=row: [row]) for row in SinglePass(rows)
            )
        )

    return store, SimpleNamespace(scanner=scanner)


@pytest.mark.parametrize("tail", [0, 3])
def test_decoded_ordered_proof_validates_each_canonical_once_per_proof(monkeypatch, tail):
    from cognitive_castle.canonical_records import CanonicalRecord

    rows, manifest, _, _, _ = unit()
    split = len(rows) - tail
    store, dataset = decoded_store_proof(rows[:split], manifest, {}, monkeypatch)
    pending = {row["id"]: row for row in rows[split:]}
    calls, original = [], CanonicalRecord.__post_init__

    def validated(record):
        calls.append(record.id)
        original(record)

    monkeypatch.setattr(CanonicalRecord, "__post_init__", validated)
    for _ in range(2):  # Independent replays must each redo the original proof.
        before = len(calls)
        assert store._verify_owner(dataset, manifest, pending) is None
        assert len(calls) - before == 3
    assert len(calls) == 6


def test_decoded_row_snapshot_cannot_trust_fields_or_raw_mutation():
    from cognitive_castle import bulk_owner_stream as ordered

    rows, _, _, _, _ = unit()
    raw = next(row for row in rows if row["kind"] == "bulk_record")
    assert hasattr(ordered, "_DecodedOwnerRow"), "strict private row decoder is missing"
    decoded = ordered._DecodedOwnerRow(raw)
    original_text = raw["text"]
    raw["text"] = "changed after decoding"
    assert decoded["text"] == original_text and decoded.record.text == original_text
    with pytest.raises(TypeError):
        decoded["text"] = "mutated"
    with pytest.raises(TypeError):
        ordered._DecodedOwnerRow(raw, record=decoded.record)
    with pytest.raises(_StoreError):
        ordered._DecodedOwnerRow(raw)


@pytest.mark.parametrize("source", ["missing", "raising"])
def test_decoded_public_iterable_errors_still_normalize_to_corrupt(source):
    _, manifest, _, _, _ = unit()

    class BrokenIterator:
        def __iter__(self):
            raise ValueError("malformed row iterable")

    rows = None if source == "missing" else BrokenIterator()
    with pytest.raises(_StoreError) as error:
        verify(rows, manifest, {}, resolve_reused=no_reuse)
    assert error.value.status == "corrupt"


def test_decoded_pages_and_receipts_are_validated_once_without_legacy_change(monkeypatch):
    from collections import Counter
    from cognitive_castle import bulk_owner_stream as ordered

    rows, manifest, _, _, _ = unit()
    for row in rows:
        assert codec.validate_entry(row) is row  # Public identity/validation contract.
    rows.insert(1, stage_receipt("single-decode"))
    rows.append(codec.receipt_row(manifest, manifest["owner"]))
    entries, receipts = [], []
    decode_entry, decode_receipt = codec._decode_entry, ordered.decode_receipt

    def entry(row):
        entries.append(row["id"])
        return decode_entry(row)

    def receipt(row):
        receipts.append(row["id"])
        return decode_receipt(row)

    monkeypatch.setattr(codec, "_decode_entry", entry)
    monkeypatch.setattr(ordered, "decode_receipt", receipt)
    store, dataset = decoded_store_proof(rows, manifest, {}, monkeypatch)
    assert store._verify_owner(dataset, manifest, {}) is None
    assert Counter(entries) == Counter(
        {row["id"]: 1 for row in rows if row["kind"] != "bulk_receipt"}
    )
    assert Counter(receipts) == Counter({rows[1]["id"]: 1, manifest["owner"]: 1})


@pytest.mark.parametrize(
    "damage", [None, "text", "pointer", "page", "exposure", "owner", "receipt", "after_marker"]
)
def test_decoded_private_and_public_raw_proofs_reject_same_corruption(monkeypatch, damage):
    from cognitive_castle import bulk_owner_stream as ordered

    rows, manifest, _, _, _ = unit()
    rows = deepcopy(rows)
    record = next(row for row in rows if row["kind"] == "bulk_record")
    member = next(
        row
        for row in rows
        if row["kind"] == "bulk_page" and json.loads(row["receipt"])["field"] == "membership"
    )
    marker = codec.receipt_row(manifest, manifest["owner"])
    if damage == "text":
        record["text"] += "changed"
    elif damage == "pointer":
        record["receipt"] = _json({**json.loads(record["receipt"]), "ordinal": 1})
    elif damage == "page":
        rows[0]["digest"] = "0" * 64
    elif damage == "exposure":
        changed = {**json.loads(member["text"]), "exposure": "0" * 64}
        member.update(codec.page(manifest["owner"], "membership", 0, _json(changed), 0, 0))
    elif damage == "owner":
        record["digest"] = "receipt:" + "0" * 64
    elif damage == "receipt":
        marker["digest"] = "0" * 64
    rows.append(marker)
    if damage == "after_marker":
        rows.append(rows[0])
    store, dataset = decoded_store_proof(rows, manifest, {}, monkeypatch)
    for operation in (
        lambda: verify(SinglePass(rows), manifest, {}, resolve_reused=no_reuse),
        lambda: store._verify_owner(dataset, manifest, {}),
    ):
        if damage is None:
            assert operation() is None
        else:
            with pytest.raises(_StoreError) as error:
                operation()
            assert error.value.status == "corrupt"
    if damage is None:
        # Public raw entry never accepts an already-decoded carrier as authority.
        with pytest.raises(_StoreError):
            verify(
                (ordered._DecodedOwnerRow(row) for row in rows),
                manifest,
                {},
                resolve_reused=no_reuse,
            )


def test_stream_checks_original_bytes_and_pending_tail():
    rows, manifest, _, text, fields = unit()
    assert manifest["text_hash"] == _hash(text)
    assert manifest["text_bytes"] == len(text.encode())
    for field, original in fields.items():
        assert manifest["fields"][field]["hash"] == _hash(original)
        assert manifest["fields"][field]["chars"] == len(original)
        assert manifest["fields"][field]["bytes"] == len(original.encode())
    membership = [
        r["text"]
        for r in rows
        if r["kind"] == "bulk_page" and json.loads(r["receipt"])["field"] == "membership"
    ]
    assert manifest["membership_hash"] == _hash("".join(membership))
    for tail in (0, 1, 3, len(rows)):
        split = len(rows) - tail
        stream = SinglePass(rows[:split])
        assert (
            verify(stream, manifest, {r["id"]: r for r in rows[split:]}, resolve_reused=no_reuse)
            is None
        )
        assert stream.count == split + 1
    empty_rows, empty = codec.prepare_owner(
        "empty", "snapshot", (), metadata="", columns="", scopes="", descriptor=""
    )
    assert verify(SinglePass(empty_rows), empty, {}, resolve_reused=no_reuse) is None
    assert not {"lance", "pyarrow", "sqlite3"}.intersection(__import__("sys").modules)


def test_stream_rejects_missing_duplicate_reordered_or_foreign_pages():
    rows, manifest, _, _, _ = unit()
    changes = [
        rows[1:],
        rows + [rows[-1]],
        rows[:1] + [rows[0]] + rows[1:],
        [rows[1], rows[0], *rows[2:]],
    ]
    foreign, _ = codec.prepare_owner("foreign", "snapshot", (), metadata="foreign")
    changes.append([foreign[0], *rows])
    membership_index = next(
        i
        for i, r in enumerate(rows)
        if r["kind"] == "bulk_page" and json.loads(r["receipt"])["field"] == "membership"
    )
    for damage in ("offset", "id", "exposure", "bytes", "missing_text"):
        changed = deepcopy(rows)
        row = changed[membership_index]
        if damage == "offset":
            header = json.loads(row["receipt"])
            header["offset"] += 1
            row["receipt"] = _json(header)
        elif damage == "missing_text":
            changed[membership_index + 1]["text"] = ""
        else:
            member = json.loads(row["text"])
            member[damage] = (
                "memory:" + "f" * 64
                if damage == "id"
                else "f" * 64
                if damage == "exposure"
                else member["bytes"] - 1
            )
            row.update(codec.page(manifest["owner"], "membership", 0, _json(member), 0, 0))
        changes.append(changed)
    for changed in changes:
        with pytest.raises(_StoreError) as error:
            verify(SinglePass(changed), manifest, {}, resolve_reused=no_reuse)
        assert error.value.status == "corrupt"
    for key in ("text_hash", "membership_hash", "text_bytes", "members"):
        altered = deepcopy(manifest)
        altered[key] = "0" * 64 if key.endswith("hash") else altered[key] + 1
        with pytest.raises(_StoreError):
            verify(SinglePass(rows), altered, {}, resolve_reused=no_reuse)
    for field in codec.FIELDS:
        altered = deepcopy(manifest)
        altered["fields"][field]["hash"] = "0" * 64
        with pytest.raises(_StoreError):
            verify(SinglePass(rows), altered, {}, resolve_reused=no_reuse)


def test_stream_uses_actual_reused_bytes():
    rows, manifest, _, _, _ = unit()
    record_rows = {
        r["id"]: {**r, "kind": "record", "digest": "", "receipt": ""}
        for r in rows
        if r["kind"] == "bulk_record"
    }
    pages = [r for r in rows if r["kind"] != "bulk_record"]
    calls = []

    def resolve(ids):
        assert len(ids) <= 32
        calls.extend(ids)
        return {identity: record_rows[identity] for identity in ids}

    assert verify(SinglePass(pages), manifest, {}, resolve_reused=resolve) is None
    assert calls == list(record_rows)
    identity = next(iter(record_rows))
    record_rows[identity] = {**record_rows[identity], "text": "changed exact bytes"}
    with pytest.raises(_StoreError) as error:
        verify(SinglePass(pages), manifest, {}, resolve_reused=resolve)
    assert error.value.status == "corrupt"


def qualification_manifest(directory, owner):
    return {
        "format": "ordered-owner-qualification-v1",
        "destination": str(directory),
        "parent_identity": [directory.parent.stat().st_dev, directory.parent.stat().st_ino],
        "destination_identity": [directory.stat().st_dev, directory.stat().st_ino],
        "owner": owner["owner"],
        "source_binding": owner["source_binding"],
        "schema": "castle-exact-six-string-v1",
        "storage_mode": "2.0",
        "expected_states": [{"version": 0, "physical_rows": 0, "fragments": 0}],
        "max_physical_rows": 128,
        "max_fragments": 8,
        "max_versions": 16,
        "max_artifact_entries": 32,
        "max_artifact_depth": 5,
        "max_logical_bytes": 2 * 1024**2,
        "max_allocated_bytes": 2 * 1024**2,
        "max_file_bytes": 1024**2,
        "max_batch_receipts": 8,
        "reservations": {
            operation: {
                "physical_rows": 32,
                "fragments": 1,
                "versions": 1,
                "artifact_entries": 8,
                "logical_bytes": 512 * 1024,
                "allocated_bytes": 512 * 1024,
                "file_bytes": 256 * 1024,
            }
            for operation in ("append", "maintenance")
        },
    }


def qualification(value):
    from cognitive_castle import bulk_owner_stream as ordered

    assert hasattr(ordered, "OrderedQualification"), "strict frozen qualification is missing"
    return ordered.OrderedQualification.from_manifest(value, expected_digest=_hash(_json(value)))


def test_qualification_is_strict_frozen_and_refuses_before_path_access(tmp_path, monkeypatch):
    from cognitive_castle import bulk_exact_store as stores

    assert hasattr(stores, "OrderedBulkExactStore"), "qualified ordered subclass is missing"
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    _, owner = codec.prepare_owner("owner", "snapshot", ())
    value = qualification_manifest(directory, owner)
    bound = qualification(value)
    value["destination"] = str(tmp_path / "replacement")
    assert bound.destination == str(directory)
    with pytest.raises((ValueError, _StoreError)):
        qualification({**qualification_manifest(directory, owner), "extra": 1})
    monkeypatch.setattr(
        "os.scandir", lambda *_: pytest.fail("qualification refusal enumerated artifacts")
    )
    with pytest.raises((ValueError, _StoreError)):
        stores.OrderedBulkExactStore(directory, qualification=None, writable=True)
    with pytest.raises((ValueError, _StoreError)):
        stores.OrderedBulkExactStore(tmp_path / "replacement", qualification=bound, writable=True)


def test_qualified_artifact_walk_rejects_first_extra_depth_and_file(tmp_path, monkeypatch):
    from cognitive_castle import bulk_exact_store as stores
    from cognitive_castle import lance_exact_store as exact

    assert hasattr(stores, "OrderedBulkExactStore"), "bounded ordered path admission is missing"
    monkeypatch.setattr(exact, "_require_supervision", lambda: None)
    _, owner = codec.prepare_owner("owner", "snapshot", ())
    for case in ("entries", "depth", "file"):
        directory = tmp_path / case
        directory.mkdir(mode=0o700)
        native = directory / "records.lance"
        native.mkdir(mode=0o700)
        value = qualification_manifest(directory, owner)
        if case == "entries":
            value["max_artifact_entries"] = 2
            for n in range(4):
                path = native / str(n)
                path.write_text("x")
                path.chmod(0o600)
        elif case == "depth":
            value["max_artifact_depth"] = 1
            (native / "nested").mkdir(mode=0o700)
        else:
            value["max_file_bytes"] = 8
            path = native / "oversize.manifest"
            path.write_bytes(b"x" * 9)
            path.chmod(0o600)
        for reserve in value["reservations"].values():
            reserve["artifact_entries"] = min(
                reserve["artifact_entries"], value["max_artifact_entries"]
            )
            reserve["file_bytes"] = min(reserve["file_bytes"], value["max_file_bytes"])
        store = stores.OrderedBulkExactStore(directory, qualification=qualification(value))
        monkeypatch.setattr(
            type(directory), "iterdir", lambda *_: pytest.fail("unbounded base walk called")
        )
        with pytest.raises(_StoreError) as error:
            store._paths()
        assert error.value.status == "unavailable"


def test_stream_receipts_preserve_split_pair_and_publication_boundary():
    rows, manifest, _, _, _ = unit()
    split = next(i for i, row in enumerate(rows) if row["kind"] == "bulk_record")
    receipt = codec.receipt_row(
        {
            "format": codec.FORMAT,
            "state": "stage_batch",
            "batch_id": "stage",
            "source_binding": "snapshot",
            "digest": "a" * 64,
            "proof": [[rows[0]["id"], _hash(_json(rows[0]))]],
            "records": 0,
            "published_owners": 0,
            "entries": 1,
        },
        codec.key("batch", "stage"),
    )
    marker = codec.receipt_row(manifest, manifest["owner"])
    assert (
        verify(
            SinglePass([*rows[:split], receipt, *rows[split:], marker]),
            manifest,
            {},
            resolve_reused=no_reuse,
        )
        is None
    )
    for changed in ([marker, *rows], [*rows, marker, marker]):
        with pytest.raises(_StoreError):
            verify(SinglePass(changed), manifest, {}, resolve_reused=no_reuse)


def test_append_reservation_rejects_individual_file_overshoot(tmp_path, monkeypatch):
    from cognitive_castle.bulk_exact_store import OrderedBulkExactStore
    from cognitive_castle import lance_exact_store as exact

    monkeypatch.setattr(exact, "_require_supervision", lambda: None)
    directory = tmp_path / "reserved"
    directory.mkdir(mode=0o700)
    rows, owner = codec.prepare_owner("reserve", "snapshot", (), metadata="original")
    store = OrderedBulkExactStore(
        directory,
        qualification=qualification(qualification_manifest(directory, owner)),
        writable=True,
    )
    store._paths()
    store._before_append(None, rows)
    native = directory / "records.lance"
    native.mkdir(mode=0o700)
    path = native / "unreserved-file.lance"
    path.write_bytes(b"x" * (256 * 1024 + 1))
    path.chmod(0o600)
    with pytest.raises(_StoreError) as error:
        store._after_append(None)
    assert error.value.status == "unavailable"
    assert path.exists()  # An overshoot remains charged; no cleanup/retry.
    # The same conservative charge covers retained files too. A subsequent
    # append must refuse before mutation even if its own output would be tiny.
    store._paths()
    with pytest.raises(_StoreError) as error:
        store._before_append(None, rows)
    assert error.value.status == "unavailable"


def maintenance_fixture(tmp_path, monkeypatch, *, physical_rows=1, **changes):
    from types import SimpleNamespace
    from cognitive_castle import lance_exact_store as exact
    from cognitive_castle.bulk_exact_store import OrderedBulkExactStore

    monkeypatch.setattr(exact, "_require_supervision", lambda: None)
    directory = tmp_path / "maintenance"
    directory.mkdir(mode=0o700)
    _, owner = codec.prepare_owner("maintenance", "snapshot", ())
    manifest = qualification_manifest(directory, owner)
    manifest.update(
        expected_states=[{"version": 1, "physical_rows": physical_rows, "fragments": 1}],
        max_physical_rows=max(128, physical_rows),
    )
    manifest.update(changes)
    metadata = SimpleNamespace(
        deletion_file=None,
        row_id_meta=None,
        created_at_version_meta=None,
        last_updated_at_version_meta=None,
    )
    fragment = SimpleNamespace(fragment_id=0, physical_rows=physical_rows, metadata=metadata)
    dataset = SimpleNamespace(
        version=1,
        data_storage_version="2.0",
        get_fragments=lambda: [fragment],
        scanner=lambda **_kwargs: SimpleNamespace(to_batches=lambda: iter(())),
    )
    store = OrderedBulkExactStore(directory, qualification=qualification(manifest), writable=True)
    store._paths()
    assert hasattr(store, "_before_maintenance"), "qualified maintenance reservation is missing"
    return store, dataset, fragment


def test_maintenance_reserves_before_creation_and_preserves_geometry(tmp_path, monkeypatch):
    store, dataset, fragment = maintenance_fixture(tmp_path, monkeypatch)
    store._before_maintenance(dataset)
    dataset.version = 2
    assert store._after_maintenance(dataset) is None
    fragment.physical_rows += 1
    with pytest.raises(_StoreError) as error:
        store._after_maintenance(dataset)
    assert error.value.status == "corrupt"


def test_maintenance_keeps_index_limit_and_charged_file_bound(tmp_path, monkeypatch):
    too_many = tmp_path / "too-many"
    too_many.mkdir(mode=0o700)
    store, dataset, _ = maintenance_fixture(too_many, monkeypatch, physical_rows=16385)
    with pytest.raises(_StoreError) as error:
        store._before_maintenance(dataset)
    assert error.value.status == "maintenance_limit"
    bounded = tmp_path / "bounded"
    bounded.mkdir(mode=0o700)
    store, dataset, _ = maintenance_fixture(bounded, monkeypatch)
    store._before_maintenance(dataset)
    native = store.directory / "records.lance"
    native.mkdir(mode=0o700)
    path = native / "unreserved-index.idx"
    path.write_bytes(b"x" * (256 * 1024 + 1))
    path.chmod(0o600)
    dataset.version = 2
    with pytest.raises(_StoreError) as error:
        store._after_maintenance(dataset)
    assert error.value.status == "unavailable" and path.exists()
    store._paths()
    dataset.version = 1
    with pytest.raises(_StoreError) as error:
        store._before_maintenance(dataset)
    assert error.value.status == "unavailable"


def stage_receipt(batch):
    return codec.receipt_row(
        {
            "format": codec.FORMAT,
            "state": "stage_batch",
            "batch_id": batch,
            "source_binding": "snapshot",
            "digest": "a" * 64,
            "proof": [["memory:" + "a" * 64, "b" * 64]],
            "records": 1,
            "published_owners": 0,
            "entries": 1,
        },
        codec.key("batch", batch),
    )


def receipt_scanner(dataset, rows):
    from types import SimpleNamespace

    dataset.describe_indices = lambda: []
    dataset.scanner = lambda **_kwargs: SimpleNamespace(
        to_batches=lambda: iter([SimpleNamespace(to_pylist=lambda: rows)])
    )


def test_append_reserves_resulting_batch_receipts_at_exact_boundary(tmp_path, monkeypatch):
    refused = tmp_path / "refused"
    refused.mkdir(mode=0o700)
    store, dataset, _ = maintenance_fixture(refused, monkeypatch, max_batch_receipts=1)
    receipt_scanner(dataset, [stage_receipt("first")])
    with pytest.raises(_StoreError) as error:
        store._before_append(dataset, [stage_receipt("second")])
    assert error.value.status == "unavailable"
    admitted = tmp_path / "admitted"
    admitted.mkdir(mode=0o700)
    store, dataset, _ = maintenance_fixture(admitted, monkeypatch, max_batch_receipts=2)
    receipt_scanner(dataset, [stage_receipt("first")])
    assert store._before_append(dataset, [stage_receipt("second")]) is None


def test_maintenance_refuses_existing_receipt_overflow(tmp_path, monkeypatch):
    store, dataset, _ = maintenance_fixture(tmp_path, monkeypatch, max_batch_receipts=1)
    receipt_scanner(dataset, [stage_receipt("first"), stage_receipt("second")])
    with pytest.raises(_StoreError) as error:
        store._before_maintenance(dataset)
    assert error.value.status == "unavailable"


def test_reconciliation_after_state_refuses_both_mutators(tmp_path, monkeypatch):
    store, dataset, _ = maintenance_fixture(
        tmp_path,
        monkeypatch,
        expected_states=[
            {"version": 0, "physical_rows": 0, "fragments": 0},
            {"version": 1, "physical_rows": 1, "fragments": 1},
        ],
    )
    receipt_scanner(dataset, [stage_receipt("first")])
    for mutate in (
        lambda: store._before_append(dataset, [stage_receipt("second")]),
        lambda: store._before_maintenance(dataset),
    ):
        with pytest.raises(_StoreError) as error:
            mutate()
        assert error.value.status == "stale"


def test_reconciliation_before_state_preserves_mutating_semantics(tmp_path, monkeypatch):
    store, dataset, _ = maintenance_fixture(
        tmp_path,
        monkeypatch,
        expected_states=[
            {"version": 1, "physical_rows": 1, "fragments": 1},
            {"version": 2, "physical_rows": 2, "fragments": 2},
        ],
    )
    receipt_scanner(dataset, [stage_receipt("first")])
    assert store._before_append(dataset, [stage_receipt("second")]) is None
    assert store._before_maintenance(dataset) is None


def test_published_owner_refuses_new_pending_content_but_allows_receipt_only(tmp_path, monkeypatch):
    store, dataset, _ = maintenance_fixture(tmp_path, monkeypatch, physical_rows=2)
    _, published = codec.prepare_owner(
        "maintenance", "snapshot", (), metadata="", columns="", scopes="", descriptor=""
    )
    receipt_scanner(
        dataset, [stage_receipt("first"), codec.receipt_row(published, published["owner"])]
    )
    late = codec.page(published["owner"], "descriptor", 0, "late original field", 0, 0)
    with pytest.raises(_StoreError) as error:
        store._before_append(dataset, [late, stage_receipt("late-content")])
    assert error.value.status == "conflict"
    assert store._before_append(dataset, [stage_receipt("equivalent")]) is None
