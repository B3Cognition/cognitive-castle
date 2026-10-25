"""Private, ephemeral result binding for a fully proved persisted bulk batch.

These fields select no permissions. Only the worker's locked existing-receipt
branch constructs the verified outcome; no witness is stored or reused.
"""

from pathlib import Path
import time

from . import bulk_exact_codec as bulk
from .canonical_records import _hash, _json
from .lance_exact_store import LanceExactStore, _StoreError

FORMAT = "castle-private-persisted-replay-v1"
ID_DOMAIN = "castle-private-persisted-replay-ids-v1"


def expected_ids(entries, finalizations):
    result = {row["id"] for row in entries} | {owner["owner"] for owner in finalizations}
    for owner in finalizations:
        live = owner["live"]
        if live is not None:
            result.add("receipt:" + _hash(_json([live["namespace"], live["key"]])))
    return result


def ids_digest(identities):
    values = set()
    for index, identity in enumerate(identities):
        if index >= 2 * bulk.MAX_ENTRIES:
            raise ValueError("bounded replay identities")
        bulk.identity(identity, "(?:memory|receipt)")
        values.add(identity)
    if not values:
        raise ValueError("empty replay identities")
    return _hash(_json([ID_DOMAIN, sorted(values)]))


def directory_binding(directory, *, until=None):
    path = Path(directory)
    if (
        not path.is_absolute()
        or str(path) != str(directory)
        or ".." in path.parts
        or len(path.parts) > 64
    ):
        raise ValueError("canonical replay destination")
    try:
        for ancestor in [path, *path.parents]:
            if (until is not None and time.monotonic() >= until) or ancestor.is_symlink():
                raise ValueError("replay path or deadline")
        identities = []
        for current in (path.parent, path):
            LanceExactStore._private(current, directory=True)
            info = current.lstat()
            identities.append([info.st_dev, info.st_ino])
        if until is not None and time.monotonic() >= until:
            raise ValueError("replay binding deadline")
        return dict(
            generation=str(path.parent),
            destination=str(path),
            parent_identity=identities[0],
            directory_identity=identities[1],
        )
    except (OSError, _StoreError) as error:
        raise ValueError("replay destination identity") from error


def fresh_outcome(receipt):
    return {"status": "ok", "outcome": "FreshAppend", "receipt": dict(receipt)}


def existing_outcome(receipt, directory, source_binding, batch_id, identities, version):
    bulk.integer(version)
    if version == 0:
        raise ValueError("verified dataset version")
    return dict(
        status="ok",
        outcome="ExistingVerified",
        receipt=dict(receipt),
        witness={
            "format": FORMAT,
            **directory_binding(directory),
            "source_binding": source_binding,
            "batch_id": batch_id,
            "batch_digest": receipt["digest"],
            "expected_ids_digest": ids_digest(identities),
            "dataset_version": version,
        },
    )


def validate_outcome(
    value, expected, directory, source_binding, batch_id, identities, *, until=None
):
    if not isinstance(value, dict) or value.get("status") != "ok":
        raise ValueError("private replay result")
    tag = value.get("outcome")
    fields = {"status", "outcome", "receipt"}
    if tag == "ExistingVerified":
        fields.add("witness")
    elif tag != "FreshAppend":
        raise ValueError("closed replay outcome")
    receipt = value.get("receipt")
    if value.keys() != fields or not isinstance(receipt, dict) or receipt != expected:
        raise ValueError("exact replay receipt")
    if receipt.keys() != {
        "status",
        "state",
        "receipt_id",
        "digest",
        "records",
        "published_owners",
        "entries",
    }:
        raise ValueError("compact replay receipt shape")
    for key in ("records", "published_owners", "entries"):
        bulk.integer(receipt[key])
    if tag == "FreshAppend":
        return None
    witness = value["witness"]
    if not isinstance(witness, dict) or witness.keys() != {
        "format",
        "generation",
        "destination",
        "parent_identity",
        "directory_identity",
        "source_binding",
        "batch_id",
        "batch_digest",
        "expected_ids_digest",
        "dataset_version",
    }:
        raise ValueError("closed replay witness")
    for key in ("parent_identity", "directory_identity"):
        if not isinstance(witness[key], list) or len(witness[key]) != 2:
            raise ValueError("replay identity shape")
        for number in witness[key]:
            bulk.integer(number)
    version = bulk.integer(witness["dataset_version"])
    if version == 0:
        raise ValueError("verified dataset version")
    bindings = dict(
        format=FORMAT,
        **directory_binding(directory, until=until),
        source_binding=source_binding,
        batch_id=batch_id,
        batch_digest=expected["digest"],
        expected_ids_digest=ids_digest(identities),
        dataset_version=version,
    )
    if witness != bindings:
        raise ValueError("replay witness binding")
    return version
