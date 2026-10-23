import hashlib
import json
from types import SimpleNamespace

import pytest

from cognitive_castle.memory import MemoryService
from cognitive_castle.memory_types import MemoryError, SourceExpectation


@pytest.fixture
def service(synthetic_palace):
    root = synthetic_palace.root
    (root / ".provider").mkdir()
    (root / ".provider/identity.json").write_text(
        json.dumps({"schema_version": 1, "namespace": "test-domain"})
    )
    text = "🙂First\r\n\x00Exact text  \n" * 700
    synthetic_palace.drawers.upsert(
        ids=["own", "foreign"],
        documents=[text, "secret"],
        metadatas=[{"wing": "allowed", "source_file": "/private/secret/path"}, {"wing": "other"}],
    )
    context = SimpleNamespace(
        paths=SimpleNamespace(root=root, provider=root / ".provider"),
        config=SimpleNamespace(embedder_model="test", embedder_dim=4),
        get_collection=lambda: synthetic_palace.drawers,
    )
    return MemoryService(
        context, namespace="test-domain", allowed_wings=frozenset({"allowed"})
    ), text


def test_slices_reconstruct_exact_stored_text(service):
    provider, text = service
    chunks, offset = [], 0
    while True:
        result = provider.fetch("own", start_char=offset)
        chunks.append(result.text)
        assert result.text_sha256 == hashlib.sha256(text.encode()).hexdigest()
        assert result.slice_sha256 == hashlib.sha256(result.text.encode()).hexdigest()
        assert "/private/secret" not in json.dumps(result.as_dict())
        if result.complete:
            break
        offset = result.next_start_char
    assert "".join(chunks) == text


def test_foreign_and_missing_ids_have_same_error(service):
    for rid in ("foreign", "missing"):
        with pytest.raises(MemoryError, match="^not_found$"):
            service[0].fetch(rid)


def test_internal_registry_sentinel_is_not_memory_evidence(service):
    provider, _ = service
    provider.context.get_collection().upsert(
        ids=["sentinel"],
        documents=["[registry] /private/internal/source"],
        metadatas=[{"wing": "allowed", "room": "_registry", "ingest_mode": "registry"}],
    )
    with pytest.raises(MemoryError, match="not_found"):
        provider.fetch("sentinel")


def test_health_refuses_store_with_no_usable_recall(service, monkeypatch):
    provider, _ = service
    collection = provider.context.get_collection()
    monkeypatch.setattr(collection, "dense_available", False)

    def failed(*args, **kwargs):
        raise OSError("FTS index absent")

    monkeypatch.setattr(collection, "fts_search", failed)
    with pytest.raises(MemoryError, match="incompatible_store"):
        provider.health()


def test_snapshot_order_expectations_and_encoded_limit(service):
    provider, text = service
    expectation = SourceExpectation(hashlib.sha256(text.encode()).hexdigest(), None)
    result = provider.snapshot(("own",), expected={"own": expectation})
    assert result.texts == (text,)
    with pytest.raises(MemoryError, match="incompatible_store"):
        provider.snapshot(("own",), expected={"own": SourceExpectation("0" * 64, None)})
    with pytest.raises(MemoryError, match="result_limit"):
        provider.snapshot(("own",), maximum_bytes=100)
    with pytest.raises(MemoryError, match="invalid_request"):
        provider.snapshot(("own", "own"))


def test_bound_identity_and_closed_inputs(service):
    provider, _ = service
    with pytest.raises(MemoryError, match="incompatible_store"):
        MemoryService(provider.context, namespace="other", allowed_wings={"allowed"})
    for kwargs in ({"start_char": -1}, {"max_chars": 8001}, {"start_char": True}):
        with pytest.raises(MemoryError, match="invalid_request"):
            provider.fetch("own", **kwargs)
    for query, limit in (("x" * 4097, 5), ("ok", 21), ("", 5)):
        with pytest.raises(MemoryError, match="invalid_request"):
            provider.search(query, limit=limit)


def test_search_postvalidates_scope_and_uses_exact_record(service, monkeypatch):
    provider, text = service

    def search(**kwargs):
        assert kwargs["profile"] == "memory-fts-v1"
        assert kwargs["allowed_wings"] == frozenset({"allowed"})
        return {
            "results": [{"id": "foreign", "score": 4}, {"id": "own", "score": 3}],
            "diagnostics": {"failed_signals": ["kg"]},
        }

    monkeypatch.setattr("cognitive_castle.searcher.search_memories", search)
    result = provider.search("decision")
    assert [hit.record_id for hit in result.hits] == ["own"]
    assert result.hits[0].text_sha256 == hashlib.sha256(text.encode()).hexdigest()
    assert result.degraded_signals == ("kg",)


@pytest.mark.parametrize("ids", [(None,), ([],), ({"id": "own"},)])
def test_snapshot_rejects_invalid_id_types_with_domain_error(service, ids):
    with pytest.raises(MemoryError, match="invalid_request"):
        service[0].snapshot(ids)


@pytest.mark.parametrize("operation", ["query", "record_id", "snapshot_id"])
def test_invalid_unicode_inputs_have_domain_errors(service, operation):
    provider = service[0]
    with pytest.raises(MemoryError, match="invalid_request"):
        if operation == "query":
            provider.search("\ud800")
        elif operation == "record_id":
            provider.fetch("\ud800")
        else:
            provider.snapshot(("\ud800",))


def test_fetch_rejects_partial_record_borrowing_completed_revision(service, synthetic_palace):
    from cognitive_castle.revisions import RevisionIdentity, RevisionManifest, publish_revision

    provider, _ = service
    meta = {
        "wing": "allowed",
        "source_file": "/source/chat",
        "representation": "project",
        "source_revision": "a" * 64,
        "completion_protocol": 1,
        "ingest_complete": False,
    }
    synthetic_palace.drawers.upsert(ids=["member"], documents=["Original"], metadatas=[meta])
    publish_revision(
        synthetic_palace.drawers,
        None,
        RevisionManifest(
            RevisionIdentity("/source/chat", "allowed", "project"), "a" * 64, ("member",)
        ),
        palace_path=synthetic_palace.root,
    )
    synthetic_palace.drawers.upsert(
        ids=["extra"], documents=["Unverified"], metadatas=[dict(meta, ingest_complete=True)]
    )
    assert provider.fetch("member").text == "Original"
    with pytest.raises(MemoryError, match="not_found"):
        provider.fetch("extra")


@pytest.mark.parametrize("field", ["source_revision", "revision", "filed_at"])
def test_metadata_provenance_cannot_reflect_filesystem_paths(service, synthetic_palace, field):
    provider, _ = service
    synthetic_palace.drawers.update(ids=["own"], metadatas=[{field: "/private/secret/path"}])
    with pytest.raises(MemoryError, match="incompatible_store"):
        provider.fetch("own")
