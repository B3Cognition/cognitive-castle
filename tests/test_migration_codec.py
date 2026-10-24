"""Pure body-free migration intent contracts, without engine imports."""

import copy
import json
import sys

import pytest


def descriptor():
    ident = dict(
        device=1, inode=2, size=3, mtime_ns=4, ctime_ns=5, mode=0o100600, uid=1000, links=1
    )
    return dict(
        format="protected-sqlite-export-v1",
        store_id="store",
        snapshot_id="snap",
        path="/private/source.db",
        identity=ident,
        manifest_path="/private/manifest.json",
        manifest_identity=ident,
        manifest_hash="a" * 64,
    )


def exported(registration, *, phase="history", text="BODY_SENTINEL_Ω"):
    from cognitive_castle.bulk_exact_codec import prepare_owner
    from cognitive_castle.canonical_records import prepare_remember
    from cognitive_castle.sqlite_export_codec import empty_counts, frame_bytes, initial_cursor

    binding = registration["source_binding"]
    prepared = prepare_remember("fixture", text)
    record = prepared.records[0]
    live = (
        dict(
            namespace=prepared.namespace,
            key=prepared.request_id,
            digest=prepared.digest,
            receipt=prepared.receipt,
        )
        if phase == "live"
        else None
    )
    entries, owner = prepare_owner(
        "owner",
        binding,
        [record],
        metadata="METADATA_SENTINEL",
        scopes='{"workspace":"SCOPE_SENTINEL"}',
        descriptor="DESCRIPTOR_SENTINEL",
        live=live,
    )
    if phase == "audit":
        entries, owner = prepare_owner("audit-owner", binding, [], descriptor="AUDIT_SENTINEL")
    before = initial_cursor(binding, "store")
    after = {
        **before,
        "phase": phase,
        "key": ["owner"]
        if phase == "history"
        else [prepared.namespace, prepared.request_id]
        if phase == "live"
        else ["history_gaps", '["pk"]'],
    }
    counts = empty_counts()
    counts[
        {"history": "historical_occurrences", "live": "live_owners", "audit": "audit_owners"}[phase]
    ] = 1
    counts["members"] = owner["members"]
    if phase == "audit":
        counts["gaps"] = 1
    result = dict(
        status="ok",
        reason=None,
        source_binding=binding,
        cursor_before=before,
        cursor_after=after,
        entries=entries,
        finalizations=[owner],
        counts=counts,
        phase=phase,
        phase_complete=True,
        complete=False,
        coverage="incomplete",
        frame_bytes=0,
    )
    for _ in range(3):
        result["frame_bytes"] = len(frame_bytes(result))
    return result


def test_intent_is_deterministic_body_free_and_uses_actual_batch_digest():
    from cognitive_castle import migration_codec as codec
    from cognitive_castle.bulk_exact_codec import validate_batch

    reg = codec.registration(descriptor(), "/private/generation")
    result = exported(reg)
    intent = codec.prepare_interval(reg, result)
    assert intent == codec.prepare_interval(reg, copy.deepcopy(result))
    assert codec.validate_interval(intent, reg) == intent
    assert intent["digest"] == validate_batch(
        intent["intent_id"], reg["source_binding"], result["entries"], result["finalizations"]
    )
    encoded = json.dumps(intent)
    for sentinel in ("BODY_SENTINEL", "METADATA_SENTINEL", "SCOPE_SENTINEL", "DESCRIPTOR_SENTINEL"):
        assert sentinel not in encoded
    changed = codec.prepare_interval(reg, exported(reg, text="different"))
    assert changed["intent_id"] == intent["intent_id"] and changed["digest"] != intent["digest"]
    assert codec.registration(descriptor(), "/private/other")["job_id"] != reg["job_id"]
    assert not {"sqlite3", "lance", "pyarrow", "numpy"}.intersection(sys.modules)


def test_intent_strict_schema_binding_counts_and_classification():
    from cognitive_castle import migration_codec as codec

    reg = codec.registration(descriptor(), "/private/generation")
    result = exported(reg)
    intent = codec.prepare_interval(reg, result)
    for change in (
        {"entries": result["entries"]},
        {"packing": "new"},
        {"destination": "/other"},
        {"digest": "no"},
        {"counts": {**intent["counts"], "members": True}},
    ):
        with pytest.raises(ValueError):
            codec.validate_interval({**intent, **change}, reg)
    for change in (
        {"source_binding": "b" * 64},
        {"counts": {**result["counts"], "audit_owners": 1}},
        {"phase": "audit"},
        {"phase_complete": False},
        {"cursor_after": result["cursor_before"]},
    ):
        with pytest.raises(ValueError):
            codec.prepare_interval(reg, {**result, **change})
    audit = codec.prepare_interval(reg, exported(reg, phase="audit"))
    assert audit["owners"][0]["classification"] == "audit"
    assert audit["owners"][0]["semantic_disposition"] == "audit_only"
    bad = copy.deepcopy(intent)
    bad["owners"][0]["fields"]["scopes"]["text"] = "forbidden"
    with pytest.raises(ValueError):
        codec.validate_interval(bad, reg)


def test_source_response_frame_accounting_cannot_understate_wire_bytes():
    from cognitive_castle import migration_codec as codec

    reg = codec.registration(descriptor(), "/private/generation")
    result = exported(reg)
    with pytest.raises(ValueError, match="frame"):
        codec.prepare_interval(reg, {**result, "frame_bytes": 1})
