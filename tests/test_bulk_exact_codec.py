"""Pure bulk codec boundaries; this module must never load a native engine."""

import importlib
import json
import sys

import pytest

from cognitive_castle.canonical_records import prepare_remember, _hash


def codec():
    spec = importlib.util.find_spec("cognitive_castle.bulk_exact_codec")
    assert spec is not None, "bulk codec is not implemented"
    return importlib.import_module("cognitive_castle.bulk_exact_codec")


def test_exact_pages_and_preserved_canonical_exposure():
    c = codec()
    records = prepare_remember("original", "  ž😀\x00\r\n" * 1300).records
    metadata = ' { "ž": "😀" } \n\x00' * 1400
    scopes = json.dumps({"workspace": None, "conflicting": ["a", "b"], "long": "😀" * 7000})
    rows, owner = c.prepare_owner(
        "occurrence",
        "snapshot:1",
        records,
        metadata=metadata,
        columns="\t{} \n",
        scopes=scopes,
        descriptor='{"alias":"old","cursor":42}',
        metadata_id="a" * 64,
    )
    for row in rows:
        assert c.validate_entry(row) == row
    assert c.validate_owner(owner) == owner
    for field, original in {"metadata": metadata, "columns": "\t{} \n", "scopes": scopes}.items():
        pages = [
            row
            for row in rows
            if row["kind"] == "bulk_page" and json.loads(row["receipt"])["field"] == field
        ]
        assert "".join(row["text"] for row in pages) == original
        assert owner["fields"][field]["hash"] == _hash(original)
        assert all(len(row["text"].encode()) <= c.PAGE_BYTES for row in pages)
    actual = [row for row in rows if row["kind"] == "bulk_record"]
    assert [(row["id"], row["text"], row["provenance"]) for row in actual] == [
        (r.id, r.text, r.provenance_json) for r in records
    ]
    assert "lance" not in sys.modules and "pyarrow" not in sys.modules


def test_empty_owner_and_original_live_receipt():
    c = codec()
    rows, owner = c.prepare_owner("empty", "snapshot", (), scopes="null")
    assert owner["members"] == 0 and owner["text_hash"] == _hash("")
    assert not any(r["kind"] == "bulk_record" for r in rows)
    prepared = prepare_remember("live", "\x00" * 8192 + "😀", namespace="host")
    _, live = c.prepare_owner(
        "live",
        "snapshot",
        prepared.records,
        live={
            "namespace": prepared.namespace,
            "key": prepared.request_id,
            "digest": prepared.digest,
            "receipt": prepared.receipt,
        },
    )
    assert live["live"]["receipt"] == prepared.receipt


def test_noncanonical_headers_and_ambiguous_ids_rejected():
    c = codec()
    rows, _ = c.prepare_owner("owner", "snapshot", prepare_remember("k", "hello").records)
    page = next(r for r in rows if r["kind"] == "bulk_page")
    for changed in (
        {**page, "id": "receipt:" + "f" * 64},
        {**page, "text": page["text"] + " "},
        {**page, "receipt": " " + page["receipt"]},
        {**page, "extra": "ambiguous"},
    ):
        with pytest.raises(ValueError):
            c.validate_entry(changed)


def test_byte_and_count_bounds_and_duplicate_ids():
    c = codec()
    rows, owner = c.prepare_owner("owner", "snapshot", prepare_remember("k", "hello").records)
    assert c.validate_batch("batch", "snapshot", rows, [owner])
    with pytest.raises(ValueError, match="duplicate"):
        c.validate_batch("batch", "snapshot", rows + rows, [])
    with pytest.raises(ValueError):
        c.validate_batch("batch", "snapshot", [rows[0]] * 257, [])
    many = []
    for n in range(40):
        entries, _ = c.prepare_owner(
            str(n), "snapshot", prepare_remember(str(n), "x" * 8192).records, metadata="\x00" * 8192
        )
        many.extend(entries)
    with pytest.raises(ValueError, match="(bytes|entries)"):
        c.validate_batch("large", "snapshot", many, [])


def test_small_exact_identity_lookup_uses_shared_indexed_batch_boundary():
    from cognitive_castle.lance_exact_store import LanceExactStore

    class Dataset:
        version = 7
        calls = []

        def describe_indices(self):
            return []

        def get_fragments(self):
            return []

        def scanner(self, **kwargs):
            self.calls.append(kwargs)
            assert kwargs["use_scalar_index"], "small hydration still disables indexed lookup"
            assert " IN (" in kwargs["filter"]
            return self

        def to_batches(self):
            return []

    ds = Dataset()
    assert LanceExactStore._find(ds, "memory:" + "a" * 64) is None
    assert len(ds.calls) == 1


def test_entry_batcher_accounts_for_json_escape_expansion():
    c = codec()
    assert hasattr(c, "entry_batches"), "byte-aware entry batching is missing"
    rows, _ = c.prepare_owner("pages", "snapshot", (), metadata="\x00😀" * 50000)
    batches = list(c.entry_batches(iter(rows)))
    assert len(batches) > 1
    assert [row for batch in batches for row in batch] == rows
    for n, batch in enumerate(batches):
        c.validate_batch(str(n), "snapshot", batch, [])
        envelope = {
            "directory": "/fixture",
            "operation": "import_batch",
            "arguments": {
                "batch_id": str(n),
                "source_binding": "snapshot",
                "entries": batch,
                "finalizations": [],
            },
            "_host_pid": 1234,
        }
        assert (
            len(
                json.dumps(
                    {
                        "request": envelope,
                        "command": ["python", "-I", "worker"],
                        "max_frame": 512 * 1024,
                    }
                ).encode()
            )
            < 512 * 1024
        )


def test_private_owner_guard_rejects_wrong_uid(tmp_path, monkeypatch):
    from cognitive_castle.lance_exact_store import LanceExactStore, _StoreError

    path = tmp_path / "private"
    path.touch(mode=0o600)
    monkeypatch.setattr("os.getuid", lambda: path.stat().st_uid + 1)
    with pytest.raises(_StoreError):
        LanceExactStore._private(path)


def test_membership_binds_full_scope_pages_outside_public_provenance():
    c = codec()
    rows, owner = c.prepare_owner(
        "scopes",
        "snapshot",
        prepare_remember("k", "text").records,
        scopes='{"absent":null,"conflicting":["a","b"]}',
    )
    membership = next(
        row
        for row in rows
        if row["kind"] == "bulk_page" and json.loads(row["receipt"])["field"] == "membership"
    )
    member = json.loads(membership["text"])
    assert member.get("scopes") == {
        "first_page": c.page_id(owner["owner"], "scopes", 0),
        **owner["fields"]["scopes"],
    }


def test_live_receipt_validation_is_shared_with_existing_small_api():
    from cognitive_castle.lance_exact_store import LanceExactStore, _StoreError

    assert hasattr(LanceExactStore, "_verify_receipt_records"), (
        "bulk must reuse original receipt validation"
    )
    prepared = prepare_remember("nine", "€" * 21845)
    validate = LanceExactStore._verify_receipt_records
    assert (
        validate(
            prepared.namespace,
            prepared.request_id,
            prepared.digest,
            prepared.receipt,
            prepared.records,
        )
        == prepared.receipt
    )
    with pytest.raises(_StoreError):
        validate(
            prepared.namespace, prepared.request_id, "0" * 64, prepared.receipt, prepared.records
        )
    with pytest.raises(_StoreError):
        validate(
            prepared.namespace,
            prepared.request_id,
            prepared.digest,
            {**prepared.receipt, "stored_text_bytes": 1},
            prepared.records,
        )


def test_bulk_worker_operations_keep_fixed_exact_caps(monkeypatch, tmp_path):
    from cognitive_castle.semantic_runtime import SemanticSession

    captured = []

    def stage(self, request, **limits):
        captured.append((request, limits))
        return {"status": "ok"}

    monkeypatch.setattr(SemanticSession, "_run_stage", stage)
    session = object.__new__(SemanticSession)
    for operation in ("import_batch", "build_id_index", "bulk_owner", "bulk_page", "bulk_receipt"):
        assert session.exact(tmp_path, operation, {}) == {"status": "ok"}
        request, limits = captured[-1]
        assert request["operation"] == operation
        assert limits["cap"] == (3 if operation in {"import_batch", "build_id_index"} else 2)
        assert limits["rss"] == 192 * 1024**2
        assert limits["total"] == 256 * 1024**2
