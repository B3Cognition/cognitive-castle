"""Closed, body-free metadata for the inactive bounded Lance layout.

These values describe reservations and current-tick proof references. They do
not grant production authority or replace an actual exact-row comparison.
Original registration, source and v1 interval identities remain unchanged.
"""

import json
from pathlib import PurePosixPath

from . import bulk_exact_codec as bulk
from . import migration_codec as migration
from .canonical_records import _hash, _json, _string

OWNER_PLAN = "lance-owner-plan-v1"
ENVELOPE = "lance-layout-envelope-v1"
TARGET = "lance-layout-target-v1"
INTENT = "lance-layout-interval-v1"
SOURCE_WINDOW = "lance-layout-source-v1"
ATTACHMENT = "lance-layout-attachment-v1"
ROUTE = "lance-layout-route-v1"
VERIFIED = "lance-layout-verified-v1"
BATCH_RESULT = "lance-layout-batch-result-v1"
PACKING = "bulk-v1-ascii-layout-1"
EXPANSION = (
    "physical_rows",
    "encoded_bytes",
    "retained_bytes",
    "batches",
    "fragments",
    "versions",
    "artifacts",
    "index_outputs",
    "index_bytes",
    "temp_bytes",
)
MAX_PLANS = 256
MAX_ROUTES = 513
KINDS = {"bulk_record", "bulk_page", "bulk_receipt", "receipt"}
CANDIDATE_FIELDS = {"id", "kind", "row_hash", "gate"}


def positive(value):
    if bulk.integer(value) == 0:
        raise ValueError("positive layout count")
    return value


def _fields(value, names, label):
    if not isinstance(value, dict) or value.keys() != set(names):
        raise ValueError(label)


def _expansion(value):
    _fields(value, EXPANSION, "layout expansion")
    for number in value.values():
        positive(number)
    return value


def owner_plan(reg, reference, expansion):
    return validate_owner_plan(
        dict(
            reference, format=OWNER_PLAN, source_binding=reg["source_binding"], expansion=expansion
        ),
        reg,
    )


def validate_owner_plan(value, reg):
    migration.validate_registration(reg)
    _fields(value, migration.OWNER_FIELDS | {"format", "source_binding", "expansion"}, "owner plan")
    if value["format"] != OWNER_PLAN or value["source_binding"] != reg["source_binding"]:
        raise ValueError("owner plan binding")
    migration.validate_owner_reference({k: value[k] for k in migration.OWNER_FIELDS}, reg)
    _expansion(value["expansion"])
    return migration.bounded(value)


def validate_generation(value):
    _fields(value, {"path", "device", "inode"}, "generation identity")
    path = _string(value["path"], 4096, "generation path")
    if (
        not PurePosixPath(path).is_absolute()
        or str(PurePosixPath(path)) != path
        or ".." in PurePosixPath(path).parts
    ):
        raise ValueError("generation path")
    bulk.integer(value["device"])
    positive(value["inode"])
    return value


def validate_envelope(value):
    _fields(
        value,
        {"format", "generation", "qualification_hash", "max_partitions", "limits"},
        "layout envelope",
    )
    if value["format"] != ENVELOPE:
        raise ValueError("layout envelope version")
    validate_generation(value["generation"])
    bulk.sha(value["qualification_hash"])
    positive(value["max_partitions"])
    _expansion(value["limits"])
    return migration.bounded(value)


def validate_attachment(value):
    _fields(value, {"format", "envelope_hash"}, "layout attachment marker")
    if value["format"] != ATTACHMENT:
        raise ValueError("layout attachment version")
    bulk.sha(value["envelope_hash"])
    return value


def target(envelope, partition_id, plans):
    validate_envelope(envelope)
    bulk.integer(partition_id)
    if (
        partition_id >= envelope["max_partitions"]
        or not isinstance(plans, list)
        or not 1 <= len(plans) <= MAX_PLANS
    ):
        raise ValueError("layout placement bound")
    hashes = [migration.hashed(plan) for plan in plans]
    value = dict(
        format=TARGET,
        generation=envelope["generation"],
        envelope_hash=migration.hashed(envelope),
        partition_id=partition_id,
        owner_plan_hashes=hashes,
    )
    value["reservation_id"] = migration.hashed([TARGET, value])
    return validate_target(value)


def validate_target(value):
    _fields(
        value,
        {
            "format",
            "generation",
            "envelope_hash",
            "partition_id",
            "owner_plan_hashes",
            "reservation_id",
        },
        "layout target",
    )
    if value["format"] != TARGET:
        raise ValueError("layout target version")
    validate_generation(value["generation"])
    bulk.sha(value["envelope_hash"])
    bulk.integer(value["partition_id"])
    hashes = value["owner_plan_hashes"]
    if not isinstance(hashes, list) or not 1 <= len(hashes) <= MAX_PLANS:
        raise ValueError("target plans")
    for item in hashes:
        bulk.sha(item)
    if len(set(hashes)) != len(hashes):
        raise ValueError("duplicate target plan")
    expected = migration.hashed([TARGET, {k: v for k, v in value.items() if k != "reservation_id"}])
    if value["reservation_id"] != expected:
        raise ValueError("target identity")
    return migration.bounded(value)


def partition_path(value):
    validate_target(value)
    return str(
        PurePosixPath(value["generation"]["path"])
        / "exact"
        / "partitions"
        / str(value["partition_id"])
    )


def _window(reg, before, fixed_target):
    return dict(
        format=SOURCE_WINDOW,
        action="export",
        descriptor=reg["descriptor"],
        cursor=before,
        allowed_plan_hashes=fixed_target["owner_plan_hashes"],
        packing=PACKING,
    )


def interval_id(reg, before, fixed_target, window):
    return migration.hashed(
        [
            INTENT,
            reg["format"],
            reg["job_id"],
            reg["source_binding"],
            reg["destination"],
            PACKING,
            before,
            fixed_target,
            window,
        ]
    )


def batch_receipt_id(intent):
    return bulk.key("batch", intent["intent_id"])


def expected_receipt(intent):
    return migration.expected_receipt(intent)


def _candidate(row, gate):
    return dict(id=row["id"], kind=row["kind"], row_hash=migration.hashed(row), gate=gate)


def prepare_layout_interval(reg, exported, fixed_target):
    migration.validate_registration(reg)
    validate_target(fixed_target)
    migration.validate_export(exported, reg, exported["cursor_before"])
    if (
        exported["status"] != "ok"
        or exported["complete"]
        or fixed_target["generation"]["path"] != reg["destination"]
    ):
        raise ValueError("not a layout content interval")
    window = _window(reg, exported["cursor_before"], fixed_target)
    identity = interval_id(reg, exported["cursor_before"], fixed_target, window)
    # Reuse the original strict source/owner/counter contract without changing its domain.
    original = migration.prepare_interval(reg, exported)
    value = {
        **original,
        "format": INTENT,
        "registration_format": reg["format"],
        "packing": PACKING,
        "intent_id": identity,
        "target": fixed_target,
        "window": window,
        "digest": bulk.validate_batch(
            identity, reg["source_binding"], exported["entries"], exported["finalizations"]
        ),
    }
    gates = set()
    routes = []
    for row in exported["entries"]:
        gate = (
            row["digest"] if row["kind"] == "bulk_record" else json.loads(row["receipt"])["owner"]
        )
        gates.add(gate)
        routes.append(_candidate(row, gate))
    for owner in exported["finalizations"]:
        gates.add(owner["owner"])
        routes.append(_candidate(bulk.receipt_row(owner, owner["owner"]), owner["owner"]))
        if owner["live"] is not None:
            live = owner["live"]
            if [live["namespace"], live["key"]] != exported["cursor_after"]["key"]:
                raise ValueError("original live receipt source key")
            row = dict(
                id="receipt:" + _hash(_json([live["namespace"], live["key"]])),
                kind="receipt",
                text="",
                provenance="",
                digest=live["digest"],
                receipt=_json(live["receipt"]),
            )
            routes.append(_candidate(row, owner["owner"]))
    if len(gates) != 1:
        raise ValueError("one admitted owner per layout frame")
    routes.append(
        dict(id=batch_receipt_id(value), kind="bulk_receipt", row_hash=None, gate=next(iter(gates)))
    )
    value["routes"] = routes
    return validate_layout_intent(value, reg)


def _candidates(values, intent, reg):
    if not isinstance(values, list) or not 1 <= len(values) <= MAX_ROUTES:
        raise ValueError("layout route bound")
    ids, gates = set(), set()
    for value in values:
        _fields(value, CANDIDATE_FIELDS, "layout candidate")
        bulk.identity(value["id"], "memory" if value["kind"] == "bulk_record" else "receipt")
        bulk.identity(value["gate"])
        if value["kind"] not in KINDS or value["id"] in ids:
            raise ValueError("layout route kind/duplicate")
        ids.add(value["id"])
        gates.add(value["gate"])
        if value["row_hash"] is None:
            if value["id"] != batch_receipt_id(intent) or value["kind"] != "bulk_receipt":
                raise ValueError("unknown row hash")
        else:
            bulk.sha(value["row_hash"])
    if (
        len(gates) != 1
        or values[-1]["id"] != batch_receipt_id(intent)
        or values[-1]["row_hash"] is not None
    ):
        raise ValueError("layout batch route")
    if intent["owners"] and next(iter(gates)) != intent["owners"][0]["owner"]:
        raise ValueError("layout owner gate")
    gate = (
        intent["owners"][0]["owner"]
        if intent["owners"]
        else bulk.owner_id(intent["cursor_after"]["owner"], reg["source_binding"])
    )
    if gates != {gate}:
        raise ValueError("layout source owner gate")
    expected_kinds = dict(
        bulk_record=intent["records"],
        bulk_page=intent["entries"] - intent["records"],
        bulk_receipt=len(intent["owners"]) + 1,
        receipt=sum(o["classification"] == "live" for o in intent["owners"]),
    )
    if any(
        sum(v["kind"] == kind for v in values) != count for kind, count in expected_kinds.items()
    ):
        raise ValueError("complete layout route cardinality")
    by_id = {v["id"]: v for v in values}
    for owner in intent["owners"]:
        if owner["owner"] not in by_id or by_id[owner["owner"]]["kind"] != "bulk_receipt":
            raise ValueError("owner receipt candidate")
        if owner["classification"] == "live":
            identity = "receipt:" + migration.hashed(owner["source_key"])
            if identity not in by_id or by_id[identity]["kind"] != "receipt":
                raise ValueError("original live receipt candidate")
    return values


def validate_layout_intent(value, reg):
    original_keys = {
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
    }
    _fields(
        value,
        original_keys | {"registration_format", "target", "window", "routes"},
        "layout intent",
    )
    if (
        value["format"] != INTENT
        or value["registration_format"] != reg["format"]
        or value["packing"] != PACKING
    ):
        raise ValueError("layout intent version")
    # Validate unchanged original cursor/counter/owner rules using its own identity.
    original = {k: value[k] for k in original_keys}
    original.update(
        format=reg["format"],
        packing=reg["packing"],
        intent_id=migration.interval_id(reg, value["cursor_before"]),
    )
    migration.validate_interval(original, reg)
    validate_target(value["target"])
    if value["target"]["generation"]["path"] != reg["destination"] or value["window"] != _window(
        reg, value["cursor_before"], value["target"]
    ):
        raise ValueError("layout source window")
    if value["intent_id"] != interval_id(
        reg, value["cursor_before"], value["target"], value["window"]
    ):
        raise ValueError("layout intent identity")
    _candidates(value["routes"], value, reg)
    return migration.bounded(value)


def validate_route(value):
    _fields(
        value,
        CANDIDATE_FIELDS | {"format", "partition_id", "version", "receipt", "state"},
        "layout route",
    )
    if (
        value["format"] != ROUTE
        or value["kind"] not in KINDS
        or value["state"] not in {"staged", "published"}
    ):
        raise ValueError("layout route version/state")
    bulk.identity(value["id"], "memory" if value["kind"] == "bulk_record" else "receipt")
    bulk.identity(value["gate"])
    bulk.sha(value["row_hash"])
    bulk.integer(value["partition_id"])
    positive(value["version"])
    bulk.identity(value["receipt"])
    return migration.bounded(value)


def verified_summary(intent, batch, owner_proofs):
    return validate_layout_verified(
        dict(
            format=VERIFIED,
            intent_hash=migration.hashed(intent),
            proof_version=migration.PROOF_VERSION,
            batch=batch,
            owner_proofs=owner_proofs,
        ),
        intent,
    )


def validate_layout_verified(value, intent):
    _fields(
        value,
        {"format", "intent_hash", "proof_version", "batch", "owner_proofs"},
        "layout verified",
    )
    if (
        value["format"] != VERIFIED
        or value["intent_hash"] != migration.hashed(intent)
        or value["proof_version"] != migration.PROOF_VERSION
    ):
        raise ValueError("layout proof binding")
    batch = value["batch"]
    _fields(batch, {"format", "outcome", "receipt", "routes"}, "layout batch result")
    _fields(batch["receipt"], expected_receipt(intent).keys(), "layout bulk receipt")
    for key in ("records", "published_owners", "entries"):
        bulk.integer(batch["receipt"][key])
    if (
        batch["format"] != BATCH_RESULT
        or batch["outcome"] != "existing_verified"
        or batch["receipt"] != expected_receipt(intent)
    ):
        raise ValueError("identical persisted replay required")
    routes = batch["routes"]
    if not isinstance(routes, list) or len(routes) != len(intent["routes"]):
        raise ValueError("complete route observations")
    home_version = positive(routes[-1]["version"])
    for route, candidate in zip(routes, intent["routes"]):
        validate_route(route)
        if route["id"] != candidate["id"] or route["kind"] != candidate["kind"]:
            raise ValueError("route observation identity/order")
        # A record reused from an earlier owner keeps its original physical row.
        # The directory must match that observation to an already published route.
        if (
            candidate["kind"] != "bulk_record"
            and candidate["row_hash"] is not None
            and route["row_hash"] != candidate["row_hash"]
        ):
            raise ValueError("route observation hash")
        if (
            route["partition_id"] != intent["target"]["partition_id"]
            and candidate["kind"] != "bulk_record"
        ):
            raise ValueError("route home")
        if route["gate"] != candidate["gate"] and candidate["kind"] != "bulk_record":
            raise ValueError("route gate")
        if route["receipt"] != batch_receipt_id(intent) and candidate["kind"] != "bulk_record":
            raise ValueError("route receipt")
        reused = candidate["kind"] == "bulk_record" and route["state"] == "published"
        if not reused and (
            route["version"] != home_version
            or route["partition_id"] != intent["target"]["partition_id"]
            or route["gate"] != candidate["gate"]
            or route["receipt"] != batch_receipt_id(intent)
        ):
            raise ValueError("current pinned home observation")
    proofs = value["owner_proofs"]
    if not isinstance(proofs, list) or len(proofs) != len(intent["owners"]):
        raise ValueError("owner observations")
    for proof, owner in zip(proofs, intent["owners"]):
        _fields(
            proof,
            {"owner", "manifest_hash", "partition_id", "version", "live_receipt_ids"},
            "owner observation",
        )
        bulk.integer(proof["partition_id"])
        if (
            any(proof[k] != owner[k] for k in ("owner", "manifest_hash", "live_receipt_ids"))
            or proof["partition_id"] != intent["target"]["partition_id"]
        ):
            raise ValueError("owner observation binding")
        if positive(proof["version"]) != home_version:
            raise ValueError("owner pinned home version")
    return migration.bounded(value)


def prospective_ack(intent):
    """Reject a prepare whose complete maximum-width success proof cannot fit."""
    version = 2**63 - 1
    routes = [
        {
            **r,
            "format": ROUTE,
            "row_hash": r["row_hash"] or "f" * 64,
            "partition_id": version,
            "version": version,
            "receipt": batch_receipt_id(intent),
            "state": "published",
        }
        for r in intent["routes"]
    ]
    proofs = [
        dict(
            owner=o["owner"],
            manifest_hash=o["manifest_hash"],
            partition_id=version,
            version=version,
            live_receipt_ids=o["live_receipt_ids"],
        )
        for o in intent["owners"]
    ]
    summary = dict(
        format=VERIFIED,
        intent_hash=migration.hashed(intent),
        proof_version=migration.PROOF_VERSION,
        batch=dict(
            format=BATCH_RESULT,
            outcome="existing_verified",
            receipt=expected_receipt(intent),
            routes=routes,
        ),
        owner_proofs=proofs,
    )
    return migration.bounded(
        dict(job_id=intent["job_id"], intent_id=intent["intent_id"], verified_summary=summary)
    )
