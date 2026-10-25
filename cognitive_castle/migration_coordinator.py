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


def _fixture_tick_persisted(session, registration):
    """Private qualified transport; ordinary/v1 workers never select this entry."""
    codec.validate_registration(registration)
    if registration["format"] != codec.FORMAT:
        raise ValueError("SQLite fixture registration")
    return _tick(session, registration, native=False, publish=_publish_persisted)


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


def _publish_v1(session, directory, arguments, expected):
    for phase in ("publish", "verify_replay"):
        receipt = session.exact(directory, "import_batch", arguments)
        if receipt != expected:
            if not isinstance(receipt, dict):
                receipt = dict(status="conflict", reason="migration_batch_response")
            return None, receipt, phase
    return None, None, None


def _publish_persisted(session, directory, arguments, expected):
    import time
    from .persisted_replay import expected_ids, validate_outcome

    identities = expected_ids(arguments["entries"], arguments["finalizations"])
    for phase in ("publish", "verify_replay"):
        result = session.exact(directory, "import_batch_outcome", arguments)
        if not isinstance(result, dict):
            return None, dict(status="conflict", reason="migration_replay_witness"), phase
        if result.get("status") != "ok":
            return None, result, phase
        try:
            version = validate_outcome(
                result,
                expected,
                directory,
                arguments["source_binding"],
                arguments["batch_id"],
                identities,
                until=time.monotonic() + session.remaining,
            )
        except (ValueError, KeyError, TypeError):
            return None, dict(status="conflict", reason="migration_replay_witness"), phase
        if version is not None:
            return version, None, None
    return None, dict(status="conflict", reason="migration_replay_not_persisted"), "verify_replay"


def _owner_version(observed, proof_version):
    version = codec.bulk.integer(observed["version"])
    if version == 0 or (proof_version is not None and version != proof_version):
        raise ValueError("owner proof version")
    return version


def _tick(session, registration, *, native, publish=_publish_v1):
    """Attempt exactly one interval; a refusal preserves the prepared interval.

    V1 always reopens twice. The private publisher may use a worker-established
    complete persisted proof; no remembered proof survives this tick.
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
    proof_version, failure, phase = publish(session, generation / "exact", arguments, expected)
    if failure is not None:
        return refused(
            failure
            if failure.get("status") != "ok"
            else dict(status="conflict", reason="migration_batch_response"),
            phase,
        )
    versions = []
    for owner in result["finalizations"]:
        owner_arguments = {"owner": owner["owner"]}
        if proof_version is not None:
            owner_arguments["version"] = proof_version
        observed = session.exact(generation / "exact", "bulk_owner", owner_arguments)
        if observed.get("status") != "ok":
            return refused(observed, "owner")
        if observed.get("manifest") != owner:
            return refused(dict(status="conflict", reason="migration_owner_manifest"), "owner")
        try:
            version = _owner_version(observed, proof_version)
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
