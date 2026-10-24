"""Canonical records preserve the existing exact-memory identity contract."""

import hashlib
import json
import os
from dataclasses import FrozenInstanceError

import pytest

from cognitive_castle.fast_memory import MemoryStore


@pytest.mark.skipif(os.name != "posix", reason="MemoryStore parity needs private POSIX storage")
@pytest.mark.parametrize(
    ("text", "pieces"),
    [
        (" \t\r\nž😀\x00\n", [" \t\r\nž😀\x00\n"]),
        ("a" * 8191 + "😀z", ["a" * 8191, "😀z"]),
        ("😀" * 2048 + "\r\n", ["😀" * 2048, "\r\n"]),
        ("ž" * 32768, ["ž" * 4096] * 8),
    ],
    ids=["literal-unicode-nul-crlf", "multibyte-crosses-boundary", "exact-boundary", "max-text"],
)
def test_prepared_records_and_receipts_match_persisted_memory(tmp_path, text, pieces):
    from cognitive_castle.canonical_records import prepare_remember

    caller = {"role": "assistant", "revision": 2, "workspace": "/work/ž"}
    prepared = prepare_remember("request", text, caller, namespace="codex")
    store = MemoryStore(tmp_path / "memory")
    actual = store.remember("request", text, caller, namespace="codex")
    assert actual["status"] == "ok"
    assert prepared.receipt == actual
    assert [record.text for record in prepared.records] == pieces
    persisted = MemoryStore(store.directory).read_sources(actual["ids"])
    assert persisted["status"] == "ok"
    assert [record.source() for record in prepared.records] == persisted["sources"]
    assert prepared.namespace == "codex" and prepared.request_id == "request"
    with store._connect() as connection:
        digest = connection.execute(
            "SELECT digest FROM receipts WHERE namespace='codex' AND request_id='request'"
        ).fetchone()[0]
    assert prepared.digest == digest


@pytest.mark.skipif(os.name != "posix", reason="MemoryStore parity needs private POSIX storage")
def test_replay_conflict_and_namespace_digests_match_memory_store(tmp_path):
    from cognitive_castle.canonical_records import prepare_remember

    store = MemoryStore(tmp_path / "memory")
    original = prepare_remember("same", "exact", {"role": "user"})
    replay = prepare_remember("same", "exact", {"role": "user"})
    assert replay == original
    assert store.remember("same", "exact", {"role": "user"}) == original.receipt
    assert store.remember("same", "exact", {"role": "user"}) == replay.receipt
    for text, caller in [("changed", {"role": "user"}), ("exact", {"role": "assistant"})]:
        changed = prepare_remember("same", text, caller)
        assert changed.digest != original.digest
        assert changed.receipt["ids"] != original.receipt["ids"]
        assert store.remember("same", text, caller) == {"status": "conflict"}
    other = prepare_remember("same", "exact", {"role": "user"}, namespace="claude")
    assert other.digest != original.digest
    assert other.receipt["ids"] != original.receipt["ids"]
    assert store.remember("same", "exact", {"role": "user"}, namespace="claude") == other.receipt


@pytest.mark.parametrize(
    "arguments",
    [
        {"request_id": ""},
        {"request_id": "ž" * 65},
        {"namespace": ""},
        {"namespace": "😀" * 33},
        {"text": ""},
        {"text": "😀" * 16385},
        {"text": "\ud800"},
        {"provenance": []},
        {"provenance": {1: "non-string-key"}},
        {"provenance": {"x": "a" * 513}},
        {"provenance": {"x": float("nan")}},
        {"provenance": {"x": object()}},
    ],
    ids=[
        "empty-request",
        "request-byte-limit",
        "empty-namespace",
        "namespace-byte-limit",
        "empty-text",
        "text-byte-limit",
        "invalid-unicode",
        "caller-type",
        "json-key-type",
        "caller-byte-limit",
        "nonfinite-json",
        "unsupported-json-value",
    ],
)
def test_request_validation_matches_memory_store_without_creating_storage(tmp_path, arguments):
    from cognitive_castle.canonical_records import prepare_remember

    values = dict(request_id="request", text="exact", provenance=None, namespace="operator")
    values.update(arguments)
    store = MemoryStore(tmp_path / "not-created")
    with pytest.raises(ValueError):
        prepare_remember(**values)
    with pytest.raises(ValueError):
        store.remember(**values)
    assert not store.directory.exists()


def test_migration_preserves_full_provenance_and_selected_source_hash():
    from cognitive_castle.canonical_records import CanonicalRecord

    source = {
        "id": "memory:" + "a" * 64,
        "text": " exact\r\nž😀\x00 ",
        "provenance": {
            "origin": "archive",
            "local_only": True,
            "storage_format": "sqlite-fts5-utf8-v1",
            "text_hash": hashlib.sha256(" exact\r\nž😀\x00 ".encode()).hexdigest(),
            "chunk_start": 23,
            "chunk_end": 35,
            "caller": {"archive_id": "prior-archive", "version": 12, "role": "user"},
            "lineage": {"original_format": "preserved-custom-lineage"},
        },
    }
    # The literal is twelve codepoints, independent of its UTF-8 byte length.
    before = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    record = CanonicalRecord.from_source(source)
    assert record.source() == source
    assert record.provenance_json == json.dumps(
        source["provenance"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    assert record.source()["provenance"]["storage_format"] == "sqlite-fts5-utf8-v1"
    after = json.dumps(record.source(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(after.encode()).hexdigest() == hashlib.sha256(before.encode()).hexdigest()
    source["provenance"]["caller"]["role"] = "changed-input"
    exposed = record.source()
    exposed["provenance"]["caller"]["role"] = "changed-output"
    assert record.source()["provenance"]["caller"]["role"] == "user"
    with pytest.raises(FrozenInstanceError):
        record.text = "changed"


@pytest.mark.parametrize("mutation", ["hash", "offset", "boolean-offset", "id", "caller", "size"])
def test_migration_rejects_invalid_canonical_sources(mutation):
    from cognitive_castle.canonical_records import CanonicalRecord, prepare_remember

    source = prepare_remember("request", "exact", {"role": "user"}).records[0].source()
    if mutation == "hash":
        source["text"] = "other"
    elif mutation == "offset":
        source["provenance"]["chunk_end"] = 100
    elif mutation == "boolean-offset":
        source["provenance"]["chunk_start"] = False
    elif mutation == "id":
        source["id"] = "memory:not-a-hash"
    elif mutation == "caller":
        source["provenance"]["caller"] = []
    else:
        source["provenance"]["unexpected"] = "x" * 1024
    with pytest.raises(ValueError):
        CanonicalRecord.from_source(source)


def test_preparation_snapshots_caller_and_returns_independent_receipts():
    from cognitive_castle.canonical_records import prepare_remember

    caller = {"role": "user", "nested": {"revision": 1}}
    prepared = prepare_remember("request", "exact", caller)
    caller["nested"]["revision"] = 2
    assert prepared.records[0].source()["provenance"]["caller"]["nested"]["revision"] == 1
    receipt = prepared.receipt
    receipt["ids"].append("injected")
    assert len(prepared.receipt["ids"]) == 1
