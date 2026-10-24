"""Inactive private fixture driver for protected SQLite export coordination.

There is deliberately no public, CLI, scheduler or production mover wiring.
The fixture harness owns creation/sealing/lifetime of source and destination.
An open registration is metadata, never a production capacity/snapshot permit.
Every call uses its caller's one SemanticSession and absolute deadline; bodies
exist only for this tick. A pending interval always regenerates from its start.
"""

from pathlib import Path

from . import migration_codec as codec


def _fixture_tick(session, registration):
    codec.validate_registration(registration)
    if registration["format"] != codec.FORMAT:
        raise ValueError("SQLite fixture registration")
    return _tick(session, registration, native=False)


def _native_fixture_tick(session, registration):
    """The one explicit native fixture entry; never a caller-selected provider."""
    codec.validate_registration(registration)
    if registration["format"] != codec.NATIVE_FORMAT:
        raise ValueError("native fixture registration")
    return _tick(session, registration, native=True)


def _source(session, registration, cursor, *, native):
    if native:
        return session.native_source(registration["descriptor"], cursor)
    return session.sqlite_source(registration["descriptor"], cursor)


def _tick(session, registration, *, native):
    """Attempt exactly one interval; a refusal preserves the prepared interval.

    The only independent batch-verification boundary is the second identical
    actual import_batch: the first successful call established the batch, so its
    following replay must execute 3a's full proof and expected-ID-set checks.
    No remembered partial proof survives a tick, and no proof paging occurs.
    """
    codec.validate_registration(registration)
    generation = Path(registration["destination"])
    job_id = registration["job_id"]
    state = session.store(generation, "queue_migration_open", {"registration": registration})
    if state.get("status") != "ok":
        return {**state, "phase": "open"}
    if state.get("registration") != registration:
        return {"status": "conflict", "reason": "migration_registration", "phase": "open"}
    if state["state"] == "snapshot_export_exhausted":
        return state["last_ack"]["result"]
    pending, before = state["pending"], state["staging_cursor"]

    def refused(result, phase):
        # Recording is another ordinary bounded stage, never a cleanup lease.
        # If budget/preemption is exhausted, the existing pending row is enough
        # to resume; the refusal remains in this compact return value.
        refusal = dict(
            status=result.get("status", "unavailable"),
            reason=result.get("reason"),
            phase=result.get("phase", phase),
            refused_operation=result.get("refused_operation", phase),
            refused_field=result.get("refused_field"),
            orphans=result.get("counts", {}).get("orphans", 0),
        )
        saved = None
        if session._ready() is None:
            saved = session.store(
                generation,
                "queue_migration_refuse",
                dict(job_id=job_id, expected_cursor=before, refusal=refusal),
            )
        return dict(
            status=refusal["status"],
            reason=refusal["reason"],
            phase=phase,
            source_phase=refusal["phase"],
            refused_operation=refusal["refused_operation"],
            refused_field=refusal["refused_field"],
            cursor_before=before,
            cursor_after=before,
            intent_id=pending["intent_id"] if pending else None,
            counts={
                **state["counts"],
                "orphans": max(state["counts"]["orphans"], refusal["orphans"]),
            },
            coverage="incomplete",
            refusal_record=saved,
        )

    source_cursor = pending["cursor_before"] if pending else before
    result = _source(session, registration, source_cursor, native=native)
    try:
        codec.validate_export(result, registration, before)
    except (ValueError, KeyError, TypeError):
        return refused(dict(status="conflict", reason="migration_source_contract"), "source")
    if result["status"] != "ok":
        return refused(result, "source")
    if result["complete"]:
        if pending is not None:
            return refused(
                dict(status="conflict", reason="migration_pending_exhaustion"), "regenerate"
            )
        ready = session._ready()
        if ready is not None:
            return refused(ready, "scan_ack")
        return session.store(
            generation,
            "queue_migration_ack",
            dict(
                job_id=job_id,
                intent_id=None,
                verified_summary=dict(
                    state="snapshot_export_exhausted",
                    cursor_before=before,
                    cursor_after=result["cursor_after"],
                    coverage=result["coverage"],
                ),
            ),
        )
    try:
        regenerated = codec.prepare_interval(registration, result)
    except (ValueError, KeyError, TypeError):
        return refused(dict(status="conflict", reason="migration_interval_contract"), "regenerate")
    if pending is not None and pending != regenerated:
        return refused(
            dict(status="conflict", reason="migration_regeneration_conflict"), "regenerate"
        )
    if pending is None:
        prepared = session.store(
            generation,
            "queue_migration_prepare",
            dict(job_id=job_id, expected_cursor=before, intent=regenerated),
        )
        if prepared != dict(status="ok", intent_id=regenerated["intent_id"]):
            return refused(
                prepared
                if prepared.get("status") != "ok"
                else dict(status="conflict", reason="migration_prepare_response"),
                "prepare",
            )
        pending = regenerated
    arguments = dict(
        batch_id=pending["intent_id"],
        source_binding=registration["source_binding"],
        entries=result["entries"],
        finalizations=result["finalizations"],
    )
    expected = codec.expected_receipt(pending)
    for phase in ("publish", "verify_replay"):
        receipt = session.exact(generation / "exact", "import_batch", arguments)
        if receipt != expected:
            return refused(
                receipt
                if receipt.get("status") != "ok"
                else dict(status="conflict", reason="migration_batch_response"),
                phase,
            )
    versions = []
    for owner in result["finalizations"]:
        observed = session.exact(generation / "exact", "bulk_owner", {"owner": owner["owner"]})
        if observed.get("status") != "ok":
            return refused(observed, "owner")
        if observed.get("manifest") != owner:
            return refused(dict(status="conflict", reason="migration_owner_manifest"), "owner")
        try:
            version = codec.bulk.integer(observed["version"])
            if version == 0:
                raise ValueError("owner version")
        except (ValueError, KeyError, TypeError):
            return refused(dict(status="conflict", reason="migration_owner_version"), "owner")
        versions.append(version)
        live = owner["live"]
        if live is not None:
            # The established receipt API has no pinned-version argument; it
            # independently validates the original namespace/key and records.
            receipt = session.exact(
                generation / "exact",
                "receipt",
                {"namespace": live["namespace"], "key": live["key"]},
            )
            if receipt != dict(status="ok", digest=live["digest"], receipt=live["receipt"]):
                return refused(
                    receipt
                    if receipt.get("status") != "ok"
                    else dict(status="conflict", reason="migration_live_receipt"),
                    "live_receipt",
                )
    summary = codec.verified_summary(pending, versions)
    codec.validate_verified(summary, pending)
    ready = session._ready()
    if ready is not None:
        return refused(ready, "ack")
    return session.store(
        generation,
        "queue_migration_ack",
        dict(job_id=job_id, intent_id=pending["intent_id"], verified_summary=summary),
    )
