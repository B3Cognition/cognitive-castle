"""Supervised bounded bulk exact publication on the canonical Lance dataset."""

from __future__ import annotations

import hashlib
import json

from . import bulk_exact_codec as codec
from .canonical_records import _hash, _json, _string
from .lance_exact_store import COLUMNS, DATASET, LanceExactStore, _StoreError, _schema

LOOKUP_IDS = 32
MAX_TAIL_ROWS = 1024
MAX_TAIL_FRAGMENTS = 32
MAX_INDEX_ROWS = 16384
INDEX_NAME = "castle_exact_id"


def coverage(dataset):
    """Inspect manifest coverage, never build/optimize an index during a read."""
    if dataset is None:
        return {
            "version": 0,
            "index_version": None,
            "indexed_fragments": 0,
            "tail_fragments": 0,
            "tail_rows": 0,
        }
    indices = [index for index in dataset.describe_indices() if index.name == INDEX_NAME]
    if len(indices) > 1:
        raise _StoreError("corrupt")
    covered, index_version = set(), None
    if indices:
        index = indices[0]
        if index.field_names != ["id"] or index.index_type.lower() != "btree":
            raise _StoreError("corrupt")
        for segment in index.segments:
            covered.update(segment.fragment_ids)
            index_version = max(index_version or 0, segment.dataset_version_at_last_update)
    tail_rows = tail_fragments = indexed_fragments = 0
    for fragment in dataset.get_fragments():
        if fragment.fragment_id in covered:
            indexed_fragments += 1
        else:
            tail_fragments += 1
            tail_rows += fragment.physical_rows
    if tail_rows > MAX_TAIL_ROWS or tail_fragments > MAX_TAIL_FRAGMENTS:
        raise _StoreError("index_required")
    return {
        "version": dataset.version,
        "index_version": index_version,
        "indexed_fragments": indexed_fragments,
        "tail_fragments": tail_fragments,
        "tail_rows": tail_rows,
    }


def lookup_many(dataset, ids, *, checked=False):
    """Bounded IN scans include both BTREE and its unindexed tail, detecting duplicates."""
    ids = list(dict.fromkeys(ids))
    for value in ids:
        codec.identity(value, "(?:memory|receipt)")
    if not checked:
        coverage(dataset)
    if dataset is None:
        return {}
    found = {}
    for start in range(0, len(ids), LOOKUP_IDS):
        group = ids[start : start + LOOKUP_IDS]
        scanner = dataset.scanner(
            columns=COLUMNS,
            filter="id IN (" + ",".join("'" + i + "'" for i in group) + ")",
            limit=len(group) + 1,
            batch_size=LOOKUP_IDS,
            strict_batch_size=True,
            batch_readahead=0,
            fragment_readahead=0,
            io_buffer_size=1024**2,
            use_scalar_index=True,
        )
        for batch in scanner.to_batches():
            for row in batch.to_pylist():
                if row["id"] not in group or row["id"] in found:
                    raise _StoreError("corrupt")
                found[row["id"]] = row
    return found


def decode_receipt(row):
    if (
        row is None
        or row["kind"] != "bulk_receipt"
        or row["text"]
        or row["provenance"]
        or row["digest"] != _hash(row["receipt"])
    ):
        raise _StoreError("corrupt")
    try:
        manifest = codec.decode(row["receipt"], 128 * 1024)
        if manifest["format"] != codec.FORMAT:
            raise ValueError("bulk format")
        if manifest["state"] == "published_owner":
            codec.validate_owner(manifest)
            if row["id"] != manifest["owner"]:
                raise ValueError("owner identity")
        elif manifest["state"] in {"stage_batch", "committed_batch"}:
            if manifest.keys() != {
                "format",
                "state",
                "batch_id",
                "source_binding",
                "digest",
                "proof",
                "records",
                "published_owners",
                "entries",
            }:
                raise ValueError("batch receipt")
            _string(manifest["batch_id"], 128, "batch id")
            _string(manifest["source_binding"], 1024, "binding")
            codec.sha(manifest["digest"])
            if row["id"] != codec.key("batch", manifest["batch_id"]):
                raise ValueError("batch identity")
            for name in ("records", "published_owners", "entries"):
                codec.integer(manifest[name])
            if (manifest["state"] == "committed_batch") != bool(manifest["published_owners"]):
                raise ValueError("batch state")
            proof = manifest["proof"]
            if not isinstance(proof, list) or not 1 <= len(proof) <= 2 * codec.MAX_ENTRIES:
                raise ValueError("batch proof")
            seen = set()
            for item in proof:
                if not isinstance(item, list) or len(item) != 2:
                    raise ValueError("batch proof entry")
                codec.identity(item[0], "(?:memory|receipt)")
                codec.sha(item[1])
                if item[0] in seen:
                    raise ValueError("duplicate proof")
                seen.add(item[0])
        else:
            raise ValueError("bulk state")
        return manifest
    except (KeyError, TypeError, ValueError, RecursionError):
        raise _StoreError("corrupt") from None


def checked_page(row, owner, field, ordinal):
    try:
        codec.validate_entry(row)
        h = json.loads(row["receipt"])
        if row["kind"] != "bulk_page" or (h["owner"], h["field"], h["ordinal"]) != (
            owner,
            field,
            ordinal,
        ):
            raise ValueError("page binding")
        return h
    except (KeyError, TypeError, ValueError, RecursionError):
        raise _StoreError("corrupt") from None


def check_member(record, member, manifest):
    source = record.source()
    p = source["provenance"]
    if {k: member["scopes"][k] for k in ("hash", "bytes", "chars", "pages")} != manifest["fields"][
        "scopes"
    ]:
        raise _StoreError("corrupt")
    if (
        member["id"] != record.id
        or member["hash"] != p["text_hash"]
        or member["exposure"] != _hash(_json(source))
        or member["start"] != p["chunk_start"]
        or member["end"] != p["chunk_end"]
        or member["bytes"] != len(record.text.encode())
    ):
        raise _StoreError("corrupt")


def visible_source(store, dataset, row):
    """Common exact/page/receipt/semantic hydration gate on a pinned dataset."""
    record = store._record(row)
    if row["kind"] == "record":
        return record.source()
    owner = row["digest"]
    pointer = json.loads(row["receipt"])
    found = lookup_many(dataset, [owner, pointer["page"]])
    if owner not in found:
        raise _StoreError("not_found")
    manifest = decode_receipt(found[owner])
    if manifest["state"] != "published_owner" or pointer["ordinal"] >= manifest["members"]:
        raise _StoreError("corrupt")
    membership = found.get(pointer["page"])
    checked_page(membership, owner, "membership", pointer["ordinal"])
    member = json.loads(membership["text"])
    check_member(record, member, manifest)
    source = record.source()
    if manifest["metadata_id"] is not None:
        source["metadata"] = {
            "id": manifest["metadata_id"],
            "metadata_hash": manifest["fields"]["metadata"]["hash"],
            "columns_hash": manifest["fields"]["columns"]["hash"],
            "metadata_bytes": manifest["fields"]["metadata"]["bytes"],
            "columns_bytes": manifest["fields"]["columns"]["bytes"],
        }
    return source


class BulkExactStore(LanceExactStore):
    def _verify_owner(self, dataset, manifest, pending):
        """Stream original text/field SHA256, never digest-of-page-digests."""

        def fetch(ids):
            found = lookup_many(dataset, [i for i in ids if i not in pending], checked=True)
            found.update({i: pending[i] for i in ids if i in pending})
            if any(i not in found for i in ids):
                raise _StoreError("corrupt")
            return found

        owner = manifest["owner"]
        whole, membership_hash = hashlib.sha256(), hashlib.sha256()
        text_chars = text_bytes = 0
        live_records = []
        if manifest["live"] is not None and not 1 <= manifest["members"] <= 9:
            raise _StoreError("corrupt")
        for start in range(0, manifest["members"], LOOKUP_IDS):
            ordinals = range(start, min(start + LOOKUP_IDS, manifest["members"]))
            pages = fetch([codec.page_id(owner, "membership", n) for n in ordinals])
            members = []
            for n in ordinals:
                row = pages[codec.page_id(owner, "membership", n)]
                h = checked_page(row, owner, "membership", n)
                if h["offset"] != n or h["byte_offset"] != n:
                    raise _StoreError("corrupt")
                members.append(json.loads(row["text"]))
                membership_hash.update(row["text"].encode())
            records = fetch([member["id"] for member in members])
            for member in members:
                row = records[member["id"]]
                record = self._record(row)
                check_member(record, member, manifest)
                if row["kind"] == "bulk_record":
                    if row["digest"] == owner:
                        if json.loads(row["receipt"])["ordinal"] != member["ordinal"]:
                            raise _StoreError("corrupt")
                    else:
                        # Reuse already visible content, never a staged other owner.
                        visible_source(self, dataset, row)
                if member["start"] != text_chars:
                    raise _StoreError("corrupt")
                whole.update(record.text.encode())
                text_chars += len(record.text)
                text_bytes += len(record.text.encode())
                if manifest["live"] is not None:
                    live_records.append(record)
        if (whole.hexdigest(), text_chars, text_bytes, membership_hash.hexdigest()) != (
            manifest["text_hash"],
            manifest["text_chars"],
            manifest["text_bytes"],
            manifest["membership_hash"],
        ):
            raise _StoreError("corrupt")
        for field, descriptor in manifest["fields"].items():
            digest = hashlib.sha256()
            chars = size = 0
            for start in range(0, descriptor["pages"], LOOKUP_IDS):
                ordinals = range(start, min(start + LOOKUP_IDS, descriptor["pages"]))
                pages = fetch([codec.page_id(owner, field, n) for n in ordinals])
                for n in ordinals:
                    row = pages[codec.page_id(owner, field, n)]
                    h = checked_page(row, owner, field, n)
                    if h["offset"] != chars or h["byte_offset"] != size:
                        raise _StoreError("corrupt")
                    digest.update(row["text"].encode())
                    chars += len(row["text"])
                    size += len(row["text"].encode())
            if (digest.hexdigest(), chars, size) != (
                descriptor["hash"],
                descriptor["chars"],
                descriptor["bytes"],
            ):
                raise _StoreError("corrupt")
        if manifest["live"] is not None:
            live = manifest["live"]
            self._verify_receipt_records(
                live["namespace"], live["key"], live["digest"], live["receipt"], live_records
            )

    def _verify_batch(self, dataset, row):
        manifest = decode_receipt(row)
        if manifest["state"] not in {"stage_batch", "committed_batch"}:
            raise _StoreError("corrupt")
        counts = {"records": 0, "pages": 0, "owners": 0}
        live_ids, expected_live_ids = set(), set()
        for start in range(0, len(manifest["proof"]), LOOKUP_IDS):
            proof = manifest["proof"][start : start + LOOKUP_IDS]
            found = lookup_many(dataset, [i for i, _ in proof], checked=True)
            for identity, digest in proof:
                prior = found.get(identity)
                if prior is None or _hash(_json(prior)) != digest:
                    raise _StoreError("corrupt")
                if prior["kind"] == "bulk_receipt":
                    owner = decode_receipt(prior)
                    if owner["state"] != "published_owner":
                        raise _StoreError("corrupt")
                    if owner["source_binding"] != manifest["source_binding"]:
                        raise _StoreError("corrupt")
                    counts["owners"] += 1
                    if owner["live"] is not None:
                        live = owner["live"]
                        expected_live_ids.add(
                            "receipt:" + _hash(_json([live["namespace"], live["key"]]))
                        )
                    self._verify_owner(dataset, owner, {})
                elif prior["kind"] in {"bulk_record", "bulk_page"}:
                    try:
                        codec.validate_entry(prior)
                    except (TypeError, ValueError):
                        raise _StoreError("corrupt") from None
                    counts["records" if prior["kind"] == "bulk_record" else "pages"] += 1
                elif prior["kind"] == "record":
                    self._record(prior)
                    counts["records"] += 1
                elif prior["kind"] == "receipt":
                    live_ids.add(identity)
                else:
                    raise _StoreError("corrupt")
        if (
            counts["records"] != manifest["records"]
            or counts["records"] + counts["pages"] != manifest["entries"]
            or counts["owners"] != manifest["published_owners"]
            or live_ids != expected_live_ids
        ):
            raise _StoreError("corrupt")
        return manifest

    @staticmethod
    def _compact(manifest, receipt_id):
        return {
            "status": "ok",
            "state": manifest["state"],
            "receipt_id": receipt_id,
            **{key: manifest[key] for key in ("digest", "records", "published_owners", "entries")},
        }

    def import_batch(self, batch_id, source_binding, entries, finalizations):
        # All body/count/frame validation precedes _writer/path creation/native IO.
        digest = codec.validate_batch(batch_id, source_binding, entries, finalizations)
        receipt_id = codec.key("batch", batch_id)
        try:
            with self._writer() as dataset:
                coverage(dataset)
                old = lookup_many(dataset, [receipt_id], checked=True).get(receipt_id)
                if old is not None:
                    manifest = self._verify_batch(dataset, old)
                    if manifest["digest"] != digest or manifest["source_binding"] != source_binding:
                        return {"status": "conflict"}
                    expected_ids = {row["id"] for row in entries} | {
                        owner["owner"] for owner in finalizations
                    }
                    for owner in finalizations:
                        live = owner["live"]
                        if live is not None:
                            expected_ids.add(
                                "receipt:" + _hash(_json([live["namespace"], live["key"]]))
                            )
                    if expected_ids != {item[0] for item in manifest["proof"]}:
                        raise _StoreError("corrupt")
                    return self._compact(manifest, receipt_id)
                candidates = {r["id"]: r for r in entries}
                for owner in finalizations:
                    candidates[owner["owner"]] = codec.receipt_row(owner, owner["owner"])
                    live = owner["live"]
                    if live is not None:
                        legacy_id = "receipt:" + _hash(_json([live["namespace"], live["key"]]))
                        row = {
                            "id": legacy_id,
                            "kind": "receipt",
                            "text": "",
                            "provenance": "",
                            "digest": live["digest"],
                            "receipt": _json(live["receipt"]),
                        }
                        if legacy_id in candidates and candidates[legacy_id] != row:
                            raise _StoreError("conflict")
                        candidates[legacy_id] = row
                found = lookup_many(dataset, candidates, checked=True)
                pending = {}
                for identity, row in candidates.items():
                    prior = found.get(identity)
                    if prior is None:
                        pending[identity] = row
                    elif row["kind"] == "bulk_record":
                        if self._record(prior) != self._record(row):
                            raise _StoreError("conflict")
                        if prior["kind"] == "bulk_record" and prior["digest"] != row["digest"]:
                            try:
                                visible_source(self, dataset, prior)
                            except _StoreError as exc:
                                if exc.status == "not_found":
                                    raise _StoreError("conflict") from None
                                raise
                        elif prior["kind"] == "bulk_record" and prior != row:
                            raise _StoreError("conflict")
                    elif prior != row:
                        raise _StoreError("conflict")
                for owner in finalizations:
                    self._verify_owner(dataset, owner, pending)
                proof = [
                    [identity, _hash(_json(found.get(identity, row)))]
                    for identity, row in candidates.items()
                ]
                manifest = {
                    "format": codec.FORMAT,
                    "state": "committed_batch" if finalizations else "stage_batch",
                    "batch_id": batch_id,
                    "source_binding": source_binding,
                    "digest": digest,
                    "proof": proof,
                    "records": sum(r["kind"] == "bulk_record" for r in entries),
                    "published_owners": len(finalizations),
                    "entries": len(entries),
                }
                rows = [*pending.values(), codec.receipt_row(manifest, receipt_id)]
                import lance
                import pyarrow as pa

                lance.write_dataset(
                    pa.Table.from_pylist(rows, schema=_schema()),
                    str(self.directory / DATASET),
                    mode="create" if dataset is None else "append",
                    max_rows_per_file=1024,
                    max_rows_per_group=1024,
                )
            return self._compact(manifest, receipt_id)
        except _StoreError as exc:
            return {"status": exc.status}
        except (OSError, RuntimeError):
            return {"status": "unavailable"}

    def build_id_index(self):
        try:
            with self._writer() as dataset:
                if dataset is None:
                    raise _StoreError("not_initialized")
                if dataset.count_rows() > MAX_INDEX_ROWS:
                    raise _StoreError("maintenance_limit")
                dataset.create_scalar_index("id", "BTREE", name=INDEX_NAME, replace=True)
                result = coverage(self._open())
            return {"status": "ok", "lookup": result}
        except _StoreError as exc:
            return {"status": exc.status}
        except (OSError, RuntimeError):
            return {"status": "unavailable"}

    def _read(self, *, version=None):
        if version is not None:
            codec.integer(version)
        self._paths()
        dataset = self._open()
        if dataset is None:
            raise _StoreError("not_initialized")
        if version is not None and dataset.version != version:
            raise _StoreError("stale")
        info = coverage(dataset)
        return dataset, info

    def bulk_owner(self, owner, *, version=None):
        codec.identity(owner)
        try:
            dataset, info = self._read(version=version)
            row = lookup_many(dataset, [owner], checked=True).get(owner)
            if row is None:
                raise _StoreError("not_found")
            manifest = decode_receipt(row)
            if manifest["state"] != "published_owner":
                raise _StoreError("corrupt")
            return {
                "status": "ok",
                "manifest": manifest,
                "version": dataset.version,
                "lookup": info,
            }
        except _StoreError as exc:
            return {"status": exc.status}
        except (OSError, RuntimeError):
            return {"status": "unavailable"}

    def bulk_page(self, owner, field, ordinal, *, version=None):
        identity = codec.page_id(owner, field, ordinal)
        try:
            dataset, info = self._read(version=version)
            found = lookup_many(dataset, [owner, identity], checked=True)
            if owner not in found:
                raise _StoreError("not_found")
            manifest = decode_receipt(found[owner])
            if manifest["state"] != "published_owner":
                raise _StoreError("corrupt")
            count = (
                manifest["members"] if field == "membership" else manifest["fields"][field]["pages"]
            )
            if ordinal >= count:
                raise _StoreError("not_found")
            row = found.get(identity)
            header = checked_page(row, owner, field, ordinal)
            return {
                "status": "ok",
                "text": row["text"],
                "hash": row["digest"],
                "header": header,
                "version": dataset.version,
                "lookup": info,
            }
        except _StoreError as exc:
            return {"status": exc.status}
        except (OSError, RuntimeError):
            return {"status": "unavailable"}

    def bulk_receipt(self, batch_id, source_binding, *, offset=0, version=None):
        _string(batch_id, 128, "batch id")
        _string(source_binding, 1024, "source binding")
        codec.integer(offset)
        try:
            dataset, info = self._read(version=version)
            identity = codec.key("batch", batch_id)
            row = lookup_many(dataset, [identity], checked=True).get(identity)
            if row is None:
                raise _StoreError("not_found")
            manifest = self._verify_batch(dataset, row)
            if manifest["source_binding"] != source_binding:
                raise _StoreError("conflict")
            end = min(len(manifest["proof"]), offset + 16)
            return {
                **self._compact(manifest, identity),
                "proof": manifest["proof"][offset:end],
                "next_offset": end,
                "complete": end == len(manifest["proof"]),
                "version": dataset.version,
                "lookup": info,
            }
        except _StoreError as exc:
            return {"status": exc.status}
        except (OSError, RuntimeError):
            return {"status": "unavailable"}
