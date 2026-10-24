"""Single-pass proofs for explicitly qualified, dedicated ordered owner datasets.

This module imports no native engine. Hashes always consume the original bytes;
no persisted hash progress or page-digest substitution is accepted.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from types import MappingProxyType

from . import bulk_exact_codec as codec
from .bulk_exact_store import check_member, checked_page, decode_receipt
from .canonical_records import _hash, _json
from .lance_exact_store import LanceExactStore, _StoreError


def verify_owner_rows(rows, manifest, pending, *, resolve_reused) -> None:
    """Prove one owner in source order with one-row lookahead and bounded reuse.

    ``pending`` contains only genuinely absent rows from the current frame, in
    append order. ``resolve_reused`` must return already visible original rows;
    this verifier additionally checks their canonical bytes and exposure.
    """
    try:
        codec.validate_owner(manifest)
        if not isinstance(pending, dict) or len(pending) > 2 * codec.MAX_ENTRIES:
            raise ValueError("pending frame")
        if any(identity != row["id"] for identity, row in pending.items()):
            raise ValueError("pending identity")
        _verify_owner_rows(iter(rows), manifest, pending, resolve_reused)
    except (KeyError, TypeError, ValueError, RecursionError):
        raise _StoreError("corrupt") from None


def _content_rows(rows, manifest, pending):
    live = manifest["live"]
    live_id = "receipt:" + _hash(_json([live["namespace"], live["key"]])) if live else None

    def combined():
        for row in rows:
            if row["id"] in pending:
                raise _StoreError("corrupt")
            yield row
        yield from pending.values()

    marker_seen = live_seen = False
    for row in combined():
        if row["kind"] == "bulk_receipt":
            receipt = decode_receipt(row)
            if receipt["source_binding"] != manifest["source_binding"]:
                raise _StoreError("corrupt")
            if receipt["state"] == "published_owner":
                if marker_seen or receipt != manifest:
                    raise _StoreError("corrupt")
                marker_seen = True
            continue
        if row["kind"] == "receipt":
            if (
                live_seen
                or not marker_seen
                or live is None
                or row
                != {
                    "id": live_id,
                    "kind": "receipt",
                    "text": "",
                    "provenance": "",
                    "digest": live["digest"],
                    "receipt": _json(live["receipt"]),
                }
            ):
                raise _StoreError("corrupt")
            live_seen = True
            continue
        if marker_seen:
            raise _StoreError("corrupt")
        yield row


def _verify_owner_rows(rows, manifest, pending, resolve_reused):
    owner = manifest["owner"]
    live = manifest["live"]
    if live is not None and not 1 <= manifest["members"] <= 9:
        raise _StoreError("corrupt")
    stream = iter(_content_rows(rows, manifest, pending))
    end = object()
    head = next(stream, end)

    def take():
        nonlocal head
        result = head
        if result is end:
            raise _StoreError("corrupt")
        head = next(stream, end)
        return result

    # Exporters emit descriptor fields before membership/record pairs. Iterating
    # the fixed FIELDS tuple rejects nonconforming physical field order.
    for field in codec.FIELDS:
        descriptor = manifest["fields"][field]
        digest = hashlib.sha256()
        chars = size = 0
        for ordinal in range(descriptor["pages"]):
            row = take()
            header = checked_page(row, owner, field, ordinal)
            if (header["offset"], header["byte_offset"]) != (chars, size):
                raise _StoreError("corrupt")
            encoded = row["text"].encode()
            digest.update(encoded)
            chars += len(row["text"])
            size += len(encoded)
        if (digest.hexdigest(), chars, size) != (
            descriptor["hash"],
            descriptor["chars"],
            descriptor["bytes"],
        ):
            raise _StoreError("corrupt")

    whole, membership = hashlib.sha256(), hashlib.sha256()
    chars = size = 0
    live_records = []
    for ordinal in range(manifest["members"]):
        row = take()
        header = checked_page(row, owner, "membership", ordinal)
        if (header["offset"], header["byte_offset"]) != (ordinal, ordinal):
            raise _StoreError("corrupt")
        member = json.loads(row["text"])
        membership.update(row["text"].encode())
        if head is not end and head["id"] == member["id"]:
            record_row = take()
            if record_row["kind"] != "bulk_record" or record_row["digest"] != owner:
                raise _StoreError("corrupt")
            if json.loads(record_row["receipt"])["ordinal"] != ordinal:
                raise _StoreError("corrupt")
        else:
            reused = resolve_reused([member["id"]])
            if not isinstance(reused, dict) or reused.keys() != {member["id"]}:
                raise _StoreError("corrupt")
            record_row = reused[member["id"]]
            if record_row["kind"] == "bulk_record" and record_row["digest"] == owner:
                raise _StoreError("corrupt")
        record = LanceExactStore._record(record_row)
        check_member(record, member, manifest)
        if member["start"] != chars:
            raise _StoreError("corrupt")
        encoded = record.text.encode()
        whole.update(encoded)
        chars += len(record.text)
        size += len(encoded)
        if live is not None:
            live_records.append(record)
    if head is not end or (whole.hexdigest(), chars, size, membership.hexdigest()) != (
        manifest["text_hash"],
        manifest["text_chars"],
        manifest["text_bytes"],
        manifest["membership_hash"],
    ):
        raise _StoreError("corrupt")
    if live is not None:
        LanceExactStore._verify_receipt_records(
            live["namespace"], live["key"], live["digest"], live["receipt"], live_records
        )


# Kept private to the fixture/operator route. Ordinary exact callers cannot pick
# this layout or replace its resource envelope through a request body.


@dataclass(frozen=True)
class OrderedQualification:
    """A digest-frozen dedicated destination and numerical resource envelope."""

    manifest_json: str
    manifest_hash: str
    _data: object = dataclass_field(init=False, repr=False, compare=False)

    def __post_init__(self):
        codec.sha(self.manifest_hash)
        if _hash(self.manifest_json) != self.manifest_hash:
            raise ValueError("qualification digest")
        value = codec.decode(self.manifest_json, 64 * 1024)
        maxima = {
            "max_physical_rows",
            "max_fragments",
            "max_versions",
            "max_artifact_entries",
            "max_artifact_depth",
            "max_logical_bytes",
            "max_allocated_bytes",
            "max_file_bytes",
            "max_batch_receipts",
        }
        if not isinstance(value, dict) or value.keys() != maxima | {
            "format",
            "destination",
            "parent_identity",
            "destination_identity",
            "owner",
            "source_binding",
            "schema",
            "storage_mode",
            "expected_states",
            "reservations",
        }:
            raise ValueError("qualification fields")
        if (
            value["format"] != "ordered-owner-qualification-v1"
            or value["schema"] != "castle-exact-six-string-v1"
            or value["storage_mode"] != "2.0"
        ):
            raise ValueError("qualification format/storage")
        from .canonical_records import _string

        _string(value["destination"], 4096, "destination")
        destination = Path(value["destination"])
        if (
            not destination.is_absolute()
            or str(destination) != value["destination"]
            or ".." in destination.parts
        ):
            raise ValueError("qualification destination")
        codec.identity(value["owner"])
        _string(value["source_binding"], 1024, "binding")
        for name in ("parent_identity", "destination_identity"):
            identity = value[name]
            if not isinstance(identity, list) or len(identity) != 2:
                raise ValueError("qualification identity")
            for number in identity:
                codec.integer(number)
        for name in maxima:
            if not codec.integer(value[name]):
                raise ValueError("qualification ceiling")
        states = value["expected_states"]
        if not isinstance(states, list) or not 1 <= len(states) <= 2:
            raise ValueError("qualification states")
        for state in states:
            if not isinstance(state, dict) or state.keys() != {
                "version",
                "physical_rows",
                "fragments",
            }:
                raise ValueError("qualification state")
            for name, maximum in (
                ("version", "max_versions"),
                ("physical_rows", "max_physical_rows"),
                ("fragments", "max_fragments"),
            ):
                codec.integer(state[name])
                if state[name] > value[maximum]:
                    raise ValueError("qualification state ceiling")
            if bool(state["version"]) != bool(state["fragments"]) or bool(
                state["physical_rows"]
            ) != bool(state["fragments"]):
                raise ValueError("qualification empty state")
        if len(states) == 2 and states[1]["version"] != states[0]["version"] + 1:
            raise ValueError("qualification reconciliation pair")
        reservations = value["reservations"]
        names = {
            "physical_rows",
            "fragments",
            "versions",
            "artifact_entries",
            "logical_bytes",
            "allocated_bytes",
            "file_bytes",
        }
        if not isinstance(reservations, dict) or reservations.keys() != {"append", "maintenance"}:
            raise ValueError("qualification reservations")
        for reservation in reservations.values():
            if not isinstance(reservation, dict) or reservation.keys() != names:
                raise ValueError("qualification reservation")
            for name, number in reservation.items():
                codec.integer(number)
                if number > value["max_" + name]:
                    raise ValueError("qualification reservation ceiling")

        def freeze(item):
            if isinstance(item, dict):
                return MappingProxyType({key: freeze(part) for key, part in item.items()})
            if isinstance(item, list):
                return tuple(freeze(part) for part in item)
            return item

        object.__setattr__(self, "_data", freeze(value))

    @classmethod
    def from_manifest(cls, manifest, *, expected_digest):
        return cls(_json(manifest), expected_digest)

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name) from None
