"""Pure, metadata-only contracts for inactive protected-export coordination.

Neither registration nor an intent grants production movement authority. Bodies
are regenerated from the registered immutable source, never serialized here.
"""

from pathlib import PurePosixPath

from . import bulk_exact_codec as bulk
from .canonical_records import _hash, _json, _string
from .sqlite_export_codec import (
    PACKING,
    empty_counts,
    frame_bytes,
    initial_cursor,
    source_binding,
    validate_cursor,
)

FORMAT = "sqlite-migration-v1"
MAX_METADATA = 192 * 1024
PROOF_VERSION = "bulk-v1-identical-replay"
OWNER_FIELDS = {
    "owner",
    "owner_key",
    "manifest_hash",
    "members",
    "membership_hash",
    "text_hash",
    "text_bytes",
    "text_chars",
    "fields",
    "classification",
    "semantic_disposition",
    "source_phase",
    "source_key",
    "live_receipt_ids",
}


class RegistrationConflict(ValueError):
    """A complete registration attempts to change its immutable identity."""


def hashed(value):
    return _hash(_json(value))


def bounded(value):
    if len(frame_bytes(value)) > MAX_METADATA:
        raise ValueError("migration metadata limit")
    return value


def registration(descriptor, destination):
    binding = source_binding(descriptor)
    if (
        not isinstance(destination, str)
        or not PurePosixPath(destination).is_absolute()
        or str(PurePosixPath(destination)) != destination
        or ".." in PurePosixPath(destination).parts
    ):
        raise ValueError("destination generation")
    _string(destination, 4096, "destination")
    result = dict(
        format=FORMAT,
        packing=PACKING,
        source_binding=binding,
        descriptor=descriptor,
        destination=destination,
    )
    result["job_id"] = hashed([FORMAT, "job", result])
    return bounded(result)


def validate_registration(value):
    if not isinstance(value, dict) or value.keys() != {
        "format",
        "packing",
        "source_binding",
        "descriptor",
        "destination",
        "job_id",
    }:
        raise ValueError("migration registration")
    if value != registration(value["descriptor"], value["destination"]):
        raise RegistrationConflict("migration immutable binding")
    return value


def cursor(value, reg):
    return validate_cursor(value, reg["source_binding"], reg["descriptor"]["store_id"])


def counts(value):
    if not isinstance(value, dict) or value.keys() != empty_counts().keys():
        raise ValueError("migration counters")
    for item in value.values():
        bulk.integer(item)
    return value


def owner_reference(manifest, phase, source_key):
    bulk.validate_owner(manifest)
    if phase not in {"live", "history", "audit"}:
        raise ValueError("owner classification")
    live = manifest["live"]
    if (phase == "live") != (live is not None) or (
        phase == "audit" and (manifest["members"] or manifest["metadata_id"] is not None)
    ):
        raise ValueError("owner classification")
    ids = [] if live is None else live["receipt"]["ids"]
    result = {
        key: manifest[key]
        for key in (
            "owner",
            "owner_key",
            "members",
            "membership_hash",
            "text_hash",
            "text_bytes",
            "text_chars",
            "fields",
        )
    }
    result.update(
        manifest_hash=hashed(manifest),
        classification=phase,
        source_phase=phase,
        source_key=source_key,
        live_receipt_ids=ids,
        semantic_disposition="audit_only"
        if phase == "audit"
        else "pending"
        if manifest["members"]
        else "no_members",
    )
    return result


def validate_owner_reference(value, reg):
    if not isinstance(value, dict) or value.keys() != OWNER_FIELDS:
        raise ValueError("owner reference")
    if value["owner"] != bulk.owner_id(value["owner_key"], reg["source_binding"]):
        raise ValueError("owner reference binding")
    for name in ("manifest_hash", "membership_hash", "text_hash"):
        bulk.sha(value[name])
    for name in ("members", "text_bytes", "text_chars"):
        bulk.integer(value[name])
    if not isinstance(value["fields"], dict) or value["fields"].keys() != set(bulk.FIELDS):
        raise ValueError("owner summaries")
    for summary in value["fields"].values():
        bulk.validate_summary(summary)
    phase = value["classification"]
    if phase not in {"live", "history", "audit"} or value["source_phase"] != phase:
        raise ValueError("owner classification")
    expected = "audit_only" if phase == "audit" else "pending" if value["members"] else "no_members"
    if value["semantic_disposition"] != expected or (phase == "audit" and value["members"]):
        raise ValueError("semantic disposition")
    key_cursor = initial_cursor(reg["source_binding"], reg["descriptor"]["store_id"])
    cursor({**key_cursor, "phase": phase, "key": value["source_key"]}, reg)
    if value["source_key"] is None:
        raise ValueError("source owner key")
    ids = value["live_receipt_ids"]
    if (
        not isinstance(ids, list)
        or len(ids) > 9
        or len(set(ids)) != len(ids)
        or (phase != "live" and ids)
    ):
        raise ValueError("live receipt references")
    for identity in ids:
        bulk.identity(identity, "memory")
    return value


def validate_export(result, reg, before):
    """Validate the one fixed source boundary; refusal carries no progress."""
    required = {
        "status",
        "reason",
        "source_binding",
        "cursor_before",
        "cursor_after",
        "entries",
        "finalizations",
        "counts",
        "phase",
        "phase_complete",
        "complete",
        "coverage",
        "frame_bytes",
    }
    if (
        not isinstance(result, dict)
        or not required <= result.keys()
        or result.keys() - required - {"resources", "refused_operation", "refused_field"}
    ):
        raise ValueError("source response schema")
    if result["source_binding"] != reg["source_binding"] or result["cursor_before"] != before:
        raise ValueError("source response binding")
    cursor(before, reg)
    cursor(result["cursor_after"], reg)
    counts(result["counts"])
    if (
        type(result["complete"]) is not bool
        or type(result["phase_complete"]) is not bool
        or result["coverage"] not in {"indexed-only", "incomplete"}
        or result["phase"] not in {"live", "history", "audit", "orphans", "done"}
    ):
        raise ValueError("source response state")
    bulk.integer(result["frame_bytes"])
    actual_frame = len(frame_bytes({k: v for k, v in result.items() if k != "resources"}))
    if result["status"] == "ok" and result["frame_bytes"] != actual_frame:
        raise ValueError("source frame accounting")
    if result["status"] != "ok":
        if (
            result["cursor_after"] != before
            or result["entries"]
            or result["finalizations"]
            or result["complete"]
            or result["phase_complete"]
            or any(v for k, v in result["counts"].items() if k != "orphans")
        ):
            raise ValueError("refusal progress")
        return result
    if result["reason"] is not None or result["cursor_after"] == before:
        raise ValueError("source progress")
    final = result["finalizations"]
    if not isinstance(final, list) or len(final) > 1:
        raise ValueError("one owner interval")
    expected_counts = empty_counts()
    if result["complete"]:
        if (
            result["phase"] != "done"
            or result["cursor_after"]["phase"] != "done"
            or result["entries"]
            or final
            or not result["phase_complete"]
            or before["owner"] is not None
        ):
            raise ValueError("scan exhaustion")
    else:
        bulk.validate_batch("export", reg["source_binding"], result["entries"], final)
        phase, after = result["phase"], result["cursor_after"]
        if phase not in {"live", "history", "audit"} or after["phase"] != phase:
            raise ValueError("source phase")
        if bool(final) != result["phase_complete"] or bool(final) == (after["owner"] is not None):
            raise ValueError("source finalization cursor")
        if before["owner"] is not None and (
            before["phase"] != phase or before["key"] != after["key"]
        ):
            raise ValueError("staged owner changed")
        if final:
            owner_reference(final[0], phase, after["key"])
            if final[0]["source_binding"] != reg["source_binding"]:
                raise ValueError("source owner binding")
            expected_counts[
                {
                    "live": "live_owners",
                    "history": "historical_occurrences",
                    "audit": "audit_owners",
                }[phase]
            ] = 1
            expected_counts["members"] = final[0]["members"]
            if phase == "audit":
                for table, counter in (
                    ("history_gaps", "gaps"),
                    ("history_gap_resolutions", "repaired_gaps"),
                    ("history_staged_rows", "pending_stages"),
                ):
                    expected_counts[counter] = int(after["key"][0] == table)
        else:
            for row in result["entries"]:
                owner = (
                    row["digest"]
                    if row["kind"] == "bulk_record"
                    else bulk.decode(row["receipt"], 2048)["owner"]
                )
                if owner != bulk.owner_id(after["owner"], reg["source_binding"]):
                    raise ValueError("staged entry owner")
    if expected_counts != result["counts"]:
        raise ValueError("source classification counters")
    return result


def interval_id(reg, before):
    return hashed(
        [
            FORMAT,
            "interval",
            reg["job_id"],
            reg["source_binding"],
            reg["destination"],
            PACKING,
            before,
        ]
    )


def prepare_interval(reg, result):
    validate_registration(reg)
    validate_export(result, reg, result["cursor_before"])
    if result["status"] != "ok" or result["complete"]:
        raise ValueError("not a content interval")
    batch = interval_id(reg, result["cursor_before"])
    value = dict(
        format=FORMAT,
        packing=PACKING,
        job_id=reg["job_id"],
        source_binding=reg["source_binding"],
        destination=reg["destination"],
        intent_id=batch,
        cursor_before=result["cursor_before"],
        cursor_after=result["cursor_after"],
        digest=bulk.validate_batch(
            batch, reg["source_binding"], result["entries"], result["finalizations"]
        ),
        entries=len(result["entries"]),
        records=sum(row["kind"] == "bulk_record" for row in result["entries"]),
        owners=[
            owner_reference(owner, result["phase"], result["cursor_after"]["key"])
            for owner in result["finalizations"]
        ],
        counts=result["counts"],
        coverage=result["coverage"],
        phase=result["phase"],
    )
    return validate_interval(value, reg)


def validate_interval(value, reg):
    if not isinstance(value, dict) or value.keys() != {
        "format",
        "packing",
        "job_id",
        "source_binding",
        "destination",
        "intent_id",
        "cursor_before",
        "cursor_after",
        "digest",
        "entries",
        "records",
        "owners",
        "counts",
        "coverage",
        "phase",
    }:
        raise ValueError("migration interval schema")
    for key in ("format", "packing", "job_id", "source_binding", "destination"):
        if value[key] != reg[key]:
            raise ValueError("migration interval binding")
    cursor(value["cursor_before"], reg)
    cursor(value["cursor_after"], reg)
    if value["intent_id"] != interval_id(reg, value["cursor_before"]):
        raise ValueError("migration interval identity")
    bulk.sha(value["digest"])
    for key in ("entries", "records"):
        bulk.integer(value[key])
    counts(value["counts"])
    if not isinstance(value["owners"], list) or len(value["owners"]) > 1:
        raise ValueError("migration owners")
    for owner in value["owners"]:
        validate_owner_reference(owner, reg)
        if (
            owner["classification"] != value["phase"]
            or owner["source_key"] != value["cursor_after"]["key"]
        ):
            raise ValueError("migration owner phase")
    if (
        not 1 <= value["entries"] + len(value["owners"]) <= 256
        or value["records"] > value["entries"]
        or value["coverage"] not in {"indexed-only", "incomplete"}
        or value["phase"] not in {"live", "history", "audit"}
        or value["cursor_after"]["phase"] != value["phase"]
        or value["cursor_before"] == value["cursor_after"]
        or bool(value["owners"]) == (value["cursor_after"]["owner"] is not None)
    ):
        raise ValueError("migration interval state")
    expected = empty_counts()
    if value["owners"]:
        owner = value["owners"][0]
        expected[
            {"live": "live_owners", "history": "historical_occurrences", "audit": "audit_owners"}[
                value["phase"]
            ]
        ] = 1
        expected["members"] = owner["members"]
        if value["phase"] == "audit":
            for table, counter in (
                ("history_gaps", "gaps"),
                ("history_gap_resolutions", "repaired_gaps"),
                ("history_staged_rows", "pending_stages"),
            ):
                expected[counter] = int(owner["source_key"][0] == table)
    if value["counts"] != expected:
        raise ValueError("migration interval counters")
    return bounded(value)


def expected_receipt(intent):
    return dict(
        status="ok",
        state="committed_batch" if intent["owners"] else "stage_batch",
        receipt_id=bulk.key("batch", intent["intent_id"]),
        digest=intent["digest"],
        records=intent["records"],
        published_owners=len(intent["owners"]),
        entries=intent["entries"],
    )


def verified_summary(intent, owner_versions):
    return dict(
        intent_hash=hashed(intent),
        proof_version=PROOF_VERSION,
        receipt=expected_receipt(intent),
        owner_versions=owner_versions,
    )


def validate_verified(summary, intent):
    if (
        not isinstance(summary, dict)
        or summary.keys() != {"intent_hash", "proof_version", "receipt", "owner_versions"}
        or summary["intent_hash"] != hashed(intent)
        or summary["proof_version"] != PROOF_VERSION
        or summary["receipt"] != expected_receipt(intent)
        or not isinstance(summary["owner_versions"], list)
        or len(summary["owner_versions"]) != len(intent["owners"])
    ):
        raise ValueError("migration verification summary")
    for version in summary["owner_versions"]:
        if bulk.integer(version) == 0:
            raise ValueError("owner dataset version")
    return bounded(summary)
