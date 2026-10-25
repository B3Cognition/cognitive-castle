"""Pure bulk-v1 envelopes inside the existing six-string exact schema.

A physical batch is not an occurrence checkpoint. Only a verified published
owner grants visibility. These helpers prepare bounded entries, not a mover.
Original descriptor/scopes are supplied verbatim by a trusted adapter; no scope
is inferred from public (possibly truncated) provenance.
"""

from __future__ import annotations

import hashlib
import json
import re

from .canonical_records import CanonicalRecord, _hash, _json, _string

FORMAT = "bulk-v1"
PAGE_BYTES = 8192
MAX_ENTRIES = 256
MAX_DECODED_BYTES = 384 * 1024
MAX_ENCODED_BYTES = 480 * 1024  # Leave room for the fixed worker envelope.
FIELDS = ("metadata", "columns", "scopes", "descriptor")
COLUMNS = {"id", "kind", "text", "provenance", "digest", "receipt"}


def identity(value, prefix="receipt"):
    if not isinstance(value, str) or not re.fullmatch(prefix + r":[a-f0-9]{64}", value):
        raise ValueError("bulk identity")
    return value


def sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("hash")
    return value


def integer(value):
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise ValueError("offset/count")
    return value


def key(domain, *parts):
    return "receipt:" + _hash(_json([FORMAT, domain, *parts]))


def owner_id(owner_key, source_binding):
    _string(owner_key, 256, "owner key")
    _string(source_binding, 1024, "source binding")
    return key("owner", source_binding, owner_key)


def page_id(owner, field, ordinal):
    identity(owner)
    if field not in (*FIELDS, "membership"):
        raise ValueError("field")
    integer(ordinal)
    return key("page", owner, field, ordinal)


def decode(text, maximum):
    value = json.loads(_string(text, maximum, "envelope"))
    if _json(value) != text:
        raise ValueError("noncanonical envelope")
    return value


def split_text(text):
    """UTF8-bounded slices, preserving every character including NUL/whitespace."""
    if not isinstance(text, str):
        raise ValueError("page text")
    pending, size = [], 0
    for character in text:
        width = len(character.encode("utf-8"))
        if size + width > PAGE_BYTES:
            yield "".join(pending)
            pending, size = [], 0
        pending.append(character)
        size += width
    if pending:
        yield "".join(pending)


def page(owner, field, ordinal, text, offset, byte_offset):
    header = {
        "format": FORMAT,
        "owner": owner,
        "field": field,
        "ordinal": ordinal,
        "offset": offset,
        "byte_offset": byte_offset,
        "chars": len(text),
        "bytes": len(text.encode("utf-8")),
    }
    row = {
        "id": page_id(owner, field, ordinal),
        "kind": "bulk_page",
        "text": text,
        "provenance": "",
        "digest": _hash(text),
        "receipt": _json(header),
    }
    return validate_entry(row)


def validate_entry(row):
    _decode_entry(row)
    return row


def _decode_entry(row):
    """Validate raw entry bytes and retain results for one internal proof."""
    if (
        not isinstance(row, dict)
        or row.keys() != COLUMNS
        or any(type(v) is not str for v in row.values())
    ):
        raise ValueError("bulk columns")
    record = header = member = None
    if row["kind"] == "bulk_record":
        record = CanonicalRecord(row["id"], row["text"], row["provenance"])
        identity(row["digest"])
        pointer = decode(row["receipt"], 1024)
        if (
            not isinstance(pointer, dict)
            or pointer.keys() != {"format", "page", "ordinal"}
            or pointer["format"] != FORMAT
        ):
            raise ValueError("membership pointer")
        integer(pointer["ordinal"])
        if pointer["page"] != page_id(row["digest"], "membership", pointer["ordinal"]):
            raise ValueError("membership identity")
        header = pointer
    elif row["kind"] == "bulk_page":
        h = decode(row["receipt"], 2048)
        if not isinstance(h, dict) or h.keys() != {
            "format",
            "owner",
            "field",
            "ordinal",
            "offset",
            "byte_offset",
            "chars",
            "bytes",
        }:
            raise ValueError("page header")
        if h["format"] != FORMAT or row["id"] != page_id(h["owner"], h["field"], h["ordinal"]):
            raise ValueError("page identity")
        for field in ("offset", "byte_offset", "chars", "bytes"):
            integer(h[field])
        if (
            row["provenance"] != ""
            or row["digest"] != _hash(row["text"])
            or h["chars"] != len(row["text"])
            or h["bytes"] != len(row["text"].encode("utf-8"))
            or not 1 <= h["bytes"] <= PAGE_BYTES
        ):
            raise ValueError("page content")
        if h["field"] == "membership":
            member = decode(row["text"], PAGE_BYTES)
            validate_member(member, h["ordinal"], h["owner"])
        header = h
    else:
        raise ValueError("bulk entry kind")
    return record, header, member


def validate_member(member, ordinal, owner):
    if not isinstance(member, dict) or member.keys() != {
        "id",
        "ordinal",
        "start",
        "end",
        "bytes",
        "hash",
        "exposure",
        "scopes",
    }:
        raise ValueError("membership")
    identity(member["id"], "memory")
    if member["ordinal"] != ordinal:
        raise ValueError("membership order")
    for field in ("ordinal", "start", "end", "bytes"):
        integer(member[field])
    if member["end"] <= member["start"] or not 1 <= member["bytes"] <= 8192:
        raise ValueError("membership bounds")
    sha(member["hash"])
    sha(member["exposure"])
    scopes = member["scopes"]
    if not isinstance(scopes, dict) or scopes.keys() != {
        "first_page",
        "hash",
        "bytes",
        "chars",
        "pages",
    }:
        raise ValueError("scope reference")
    validate_summary({name: scopes[name] for name in ("hash", "bytes", "chars", "pages")})
    expected = page_id(owner, "scopes", 0) if scopes["pages"] else None
    if scopes["first_page"] != expected:
        raise ValueError("scope page identity")
    return member


def summary(text, pages):
    return {
        "hash": _hash(text),
        "bytes": len(text.encode("utf-8")),
        "chars": len(text),
        "pages": pages,
    }


def validate_summary(descriptor):
    if not isinstance(descriptor, dict) or descriptor.keys() != {"hash", "bytes", "chars", "pages"}:
        raise ValueError("field descriptor")
    sha(descriptor["hash"])
    for name in ("bytes", "chars", "pages"):
        integer(descriptor[name])
    if (
        not descriptor["chars"] <= descriptor["bytes"] <= 4 * descriptor["chars"]
        or descriptor["pages"] > descriptor["chars"]
    ):
        raise ValueError("field lengths")


def validate_owner(manifest):
    if not isinstance(manifest, dict) or manifest.keys() != {
        "format",
        "state",
        "owner",
        "owner_key",
        "source_binding",
        "members",
        "membership_hash",
        "text_hash",
        "text_bytes",
        "text_chars",
        "fields",
        "metadata_id",
        "live",
    }:
        raise ValueError("owner manifest")
    if (
        manifest["format"] != FORMAT
        or manifest["state"] != "published_owner"
        or manifest["owner"] != owner_id(manifest["owner_key"], manifest["source_binding"])
    ):
        raise ValueError("owner identity")
    for field in ("members", "text_bytes", "text_chars"):
        integer(manifest[field])
    for field in ("text_hash", "membership_hash"):
        sha(manifest[field])
    if not isinstance(manifest["fields"], dict) or manifest["fields"].keys() != set(FIELDS):
        raise ValueError("owner fields")
    for descriptor in manifest["fields"].values():
        validate_summary(descriptor)
    if manifest["metadata_id"] is not None:
        sha(manifest["metadata_id"])
    live = manifest["live"]
    if live is not None:
        if not isinstance(live, dict) or live.keys() != {"namespace", "key", "digest", "receipt"}:
            raise ValueError("live request")
        _string(live["namespace"], 128, "namespace")
        _string(live["key"], 128, "key")
        sha(live["digest"])
        _string(_json(live["receipt"]), 4096, "original receipt")
    _string(_json(manifest), 8192, "owner manifest")
    return manifest


def receipt_row(manifest, identity_value):
    text = _json(manifest)
    return {
        "id": identity_value,
        "kind": "bulk_receipt",
        "text": "",
        "provenance": "",
        "digest": _hash(text),
        "receipt": text,
    }


def prepare_owner(
    owner_key,
    source_binding,
    records,
    *,
    metadata="",
    columns="",
    scopes="null",
    descriptor="null",
    metadata_id=None,
    live=None,
):
    """Convenience codec for one in-memory fixture/adapter unit; no storage IO.

    Large adapters can produce pages with page() incrementally and assemble the
    same constant-size manifest from streaming hashes; no whole-owner IPC exists.
    """
    owner = owner_id(owner_key, source_binding)
    rows, fields = [], {}
    for field, text in zip(FIELDS, (metadata, columns, scopes, descriptor)):
        offset = byte_offset = count = 0
        for ordinal, piece in enumerate(split_text(text)):
            rows.append(page(owner, field, ordinal, piece, offset, byte_offset))
            offset += len(piece)
            byte_offset += len(piece.encode("utf-8"))
            count += 1
        fields[field] = summary(text, count)
    whole, members = hashlib.sha256(), hashlib.sha256()
    text_chars = text_bytes = count = 0
    for ordinal, record in enumerate(records):
        if not isinstance(record, CanonicalRecord):
            raise ValueError("canonical record")
        source = record.source()
        p = source["provenance"]
        member = {
            "id": record.id,
            "ordinal": ordinal,
            "start": p["chunk_start"],
            "end": p["chunk_end"],
            "bytes": len(record.text.encode()),
            "hash": p["text_hash"],
            "exposure": _hash(_json(source)),
            "scopes": {
                "first_page": page_id(owner, "scopes", 0) if fields["scopes"]["pages"] else None,
                **fields["scopes"],
            },
        }
        text = _json(member)
        rows.append(page(owner, "membership", ordinal, text, ordinal, ordinal))
        rows.append(
            validate_entry(
                {
                    "id": record.id,
                    "kind": "bulk_record",
                    "text": record.text,
                    "provenance": record.provenance_json,
                    "digest": owner,
                    "receipt": _json(
                        {
                            "format": FORMAT,
                            "page": page_id(owner, "membership", ordinal),
                            "ordinal": ordinal,
                        }
                    ),
                }
            )
        )
        members.update(text.encode())
        whole.update(record.text.encode())
        text_chars += len(record.text)
        text_bytes += len(record.text.encode())
        count += 1
    manifest = {
        "format": FORMAT,
        "state": "published_owner",
        "owner": owner,
        "owner_key": owner_key,
        "source_binding": source_binding,
        "members": count,
        "membership_hash": members.hexdigest(),
        "text_hash": whole.hexdigest(),
        "text_bytes": text_bytes,
        "text_chars": text_chars,
        "fields": fields,
        "metadata_id": metadata_id,
        "live": live,
    }
    return rows, validate_owner(manifest)


def validate_batch(batch_id, source_binding, entries, finalizations):
    _string(batch_id, 128, "batch id")
    _string(source_binding, 1024, "source binding")
    if (
        not isinstance(entries, list)
        or not isinstance(finalizations, list)
        or not 1 <= len(entries) + len(finalizations) <= MAX_ENTRIES
    ):
        raise ValueError("bulk entries")
    body = [batch_id, source_binding, entries, finalizations]
    # The guardian serializes its outer config with default ensure_ascii=True.
    # Budget that actual escaping (including JSON strings nested in rows).
    encoded = json.dumps(body, allow_nan=False).encode()
    if len(encoded) > MAX_ENCODED_BYTES:
        raise ValueError("bulk encoded bytes")
    ids = set()
    decoded = 0
    for row in entries:
        validate_entry(row)
        if row["id"] in ids:
            raise ValueError("duplicate incoming id")
        ids.add(row["id"])
        decoded += sum(len(value.encode()) for value in row.values())
    for owner in finalizations:
        validate_owner(owner)
        if owner["source_binding"] != source_binding or owner["owner"] in ids:
            raise ValueError("duplicate owner or source binding")
        ids.add(owner["owner"])
        decoded += len(_json(owner).encode())
    if decoded > MAX_DECODED_BYTES:
        raise ValueError("bulk decoded bytes")
    return _hash(_json(body))


def entry_batches(entries):
    """Pack a stream of validated entries by encoded AND decoded bytes/count.

    The caller supplies stable batch keys and publishes finalizations separately.
    Reserve envelope space rather than assuming UTF8 size bounds JSON escaping.
    validate_batch and the fixed worker independently enforce their ceilings.
    """
    batch, encoded, decoded = [], 2, 0
    for row in entries:
        validate_entry(row)
        wire = len(json.dumps(row, allow_nan=False).encode()) + 2
        size = sum(len(value.encode()) for value in row.values())
        if batch and (
            len(batch) == MAX_ENTRIES
            or encoded + wire > MAX_ENCODED_BYTES - 16 * 1024
            or decoded + size > MAX_DECODED_BYTES
        ):
            yield batch
            batch, encoded, decoded = [], 2, 0
        if wire > MAX_ENCODED_BYTES - 16 * 1024 or size > MAX_DECODED_BYTES:
            raise ValueError("bulk entry bytes")
        batch.append(row)
        encoded += wire
        decoded += size
    if batch:
        yield batch
