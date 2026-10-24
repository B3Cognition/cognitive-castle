"""Representation-aware source identity; missing legacy evidence is never invented."""

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile


@dataclass(frozen=True)
class RevisionIdentity:
    source_file: str
    wing: str
    representation: str


def source_representation(metadata: dict) -> str | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get("representation")
    if isinstance(value, str) and value in {"project", "exchange", "general", "diary", "sweep"}:
        return value
    if metadata.get("ingest_mode") == "convos":
        value = metadata.get("extract_mode")
        return value if isinstance(value, str) and value in {"exchange", "general"} else None
    if isinstance(metadata.get("ingest_mode"), str) and metadata["ingest_mode"] in {
        "diary",
        "sweep",
    }:
        return metadata["ingest_mode"]
    return None


def revision_identity(source_file: str, metadata: dict) -> RevisionIdentity | None:
    if not isinstance(metadata, dict):
        return None
    representation = source_representation(metadata)
    wing = metadata.get("wing")
    if (
        not isinstance(source_file, str)
        or not source_file
        or not isinstance(wing, str)
        or not wing
        or representation is None
    ):
        return None
    canonical = metadata.get("canonical_source_file")
    if canonical is not None:
        if not isinstance(canonical, str) or not os.path.isabs(canonical) or "\x00" in canonical:
            return None
    else:
        canonical = os.path.realpath(source_file)
    return RevisionIdentity(canonical, wing, representation)


def atomic_json(path: Path, value: dict) -> None:
    """Publish one fsynced JSON document without exposing partial contents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def collection_palace_path(collection) -> Path | None:
    """Resolve a real Lance handle; external/mock backends retain legacy APIs."""
    value = getattr(collection, "palace_path", None)
    if isinstance(value, (str, Path)):
        return Path(value).resolve()
    uri = getattr(getattr(collection, "_table", None), "uri", None)
    if isinstance(uri, str) and uri.endswith(".lance"):
        return Path(uri).resolve().parent.parent
    return None


@dataclass(frozen=True)
class RevisionManifest:
    identity: RevisionIdentity
    revision: str
    drawer_ids: tuple[str, ...]
    closet_ids: tuple[str, ...] = ()


def _digest_ids(ids) -> str:
    return hashlib.sha256(json.dumps(sorted(ids), separators=(",", ":")).encode()).hexdigest()


_REVISION_BATCH_SIZE = 1000


def _revision_rows(table, ids):
    """Bound verification below backend scan and request-size limits."""
    for start in range(0, len(ids), _REVISION_BATCH_SIZE):
        batch = list(ids[start : start + _REVISION_BATCH_SIZE])
        records = table.get(ids=batch, include=["metadatas"])
        stored_ids, metas = records.get("ids") or [], records.get("metadatas") or []
        if (
            len(stored_ids) != len(batch)
            or set(stored_ids) != set(batch)
            or len(metas) != len(batch)
        ):
            raise OSError("revision writes are incomplete")
        yield from zip(stored_ids, metas)


def _update_revision_hints(table, ids, metadata):
    for start in range(0, len(ids), _REVISION_BATCH_SIZE):
        batch = list(ids[start : start + _REVISION_BATCH_SIZE])
        table.update(ids=batch, metadatas=[dict(metadata) for _ in batch])


def revision_manifest_path(palace_path, identity, revision) -> Path:
    key = hashlib.sha256(json.dumps(asdict(identity), sort_keys=True).encode()).hexdigest()
    # Revision keys must never become path components supplied by an untrusted record.
    if (
        not isinstance(revision, str)
        or not revision
        or any(c not in "0123456789abcdef" for c in revision)
    ):
        raise ValueError("invalid revision digest")
    return Path(palace_path) / ".castle" / "revisions" / key / f"{revision}.json"


def publish_revision(collection, closets, manifest: RevisionManifest, *, palace_path) -> None:
    """Verify writes, then publish the sole authority for new revision completion.

    The caller holds the palace mutation session. Row hints support old readers;
    a failed hint write or manifest publish leaves the revision retryable.
    """
    if palace_path is None:
        # Caller-owned collections predate local manifests and may offer only
        # upsert/update. Keep their last-row marker without claiming protocol 1.
        for table, ids in ((collection, manifest.drawer_ids), (closets, manifest.closet_ids)):
            if ids:
                table.update(
                    ids=[ids[-1]], metadatas=[{"ingest_complete": True, "completion_protocol": 0}]
                )
        return
    target = revision_manifest_path(palace_path, manifest.identity, manifest.revision)
    for table, ids in ((collection, manifest.drawer_ids), (closets, manifest.closet_ids)):
        if not ids:
            continue
        if len(set(ids)) != len(ids):
            raise OSError("revision writes are incomplete")
        for _rid, metadata in _revision_rows(table, ids):
            if (
                revision_identity(metadata.get("source_file", ""), metadata) != manifest.identity
                or metadata.get("source_revision") != manifest.revision
            ):
                raise OSError("revision identity differs")
    # No marker changes until every required table passed verification.
    for table, ids in ((collection, manifest.drawer_ids), (closets, manifest.closet_ids)):
        if ids:
            _update_revision_hints(
                table,
                ids,
                {"ingest_complete": True, "canonical_source_file": manifest.identity.source_file},
            )
    value = {
        "schema_version": 1,
        "identity": asdict(manifest.identity),
        "revision": manifest.revision,
        "drawer_count": len(manifest.drawer_ids),
        "closet_count": len(manifest.closet_ids),
        "drawer_ids_sha256": _digest_ids(manifest.drawer_ids),
        "closet_ids_sha256": _digest_ids(manifest.closet_ids),
        "drawer_ids": sorted(manifest.drawer_ids),
        "closet_ids": sorted(manifest.closet_ids),
        "complete": True,
    }
    value["checksum"] = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    atomic_json(target, value)


def revision_completed(
    palace_path, metadata: dict, *, record_id=None, record_kind="drawer"
) -> bool:
    """New writes require a valid manifest; legacy/manual rows stay readable."""
    if not isinstance(metadata, dict) or metadata.get("ingest_complete") is False:
        return False
    protocol = metadata.get("completion_protocol")
    if protocol is None or (type(protocol) is int and protocol == 0):
        return metadata.get("ingest_complete") is not False
    if type(protocol) is not int or protocol != 1:
        return False
    identity = revision_identity(metadata.get("source_file", ""), metadata)
    if identity is None:
        return False
    try:
        value = json.loads(
            revision_manifest_path(palace_path, identity, metadata["source_revision"]).read_text()
        )
        checksum = value.pop("checksum")
        valid = (
            value.get("schema_version") == 1
            and value.get("complete") is True
            and value.get("identity") == asdict(identity)
            and value.get("revision") == metadata["source_revision"]
            and checksum == hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        )
        if not valid:
            return False
        for kind in ("drawer", "closet"):
            members = value.get(f"{kind}_ids")
            if members is None:
                if record_id is not None:
                    return False  # Legacy manifests did not certify membership.
                continue
            if (
                not isinstance(members, list)
                or any(not isinstance(item, str) for item in members)
                or len(set(members)) != len(members)
                or type(value.get(f"{kind}_count")) is not int
                or len(members) != value[f"{kind}_count"]
                or _digest_ids(members) != value.get(f"{kind}_ids_sha256")
            ):
                return False
        return record_id is None or (
            record_kind in {"drawer", "closet"} and record_id in value.get(f"{record_kind}_ids", [])
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def completed_revision_ids(collection, identity, *, palace_path) -> frozenset[str]:
    result, offset = set(), 0
    while True:
        page = collection.get(
            where={"source_file": identity.source_file},
            include=["metadatas"],
            limit=1000,
            offset=offset,
        )
        for metadata in page.get("metadatas") or []:
            if revision_identity(
                metadata.get("source_file", ""), metadata
            ) == identity and revision_completed(palace_path, metadata):
                if metadata.get("source_revision"):
                    result.add(metadata["source_revision"])
        if len(page.get("ids") or []) < 1000:
            return frozenset(result)
        offset += 1000


def reuse_completed_revision(collection, closets, identity, revision, *, signature=None) -> bool:
    """A timestamp-only change or forced retry must not unpublish exact evidence.

    Once published, existing record IDs are immutable. Reuse only a verified,
    fully present revision; interrupted first writes remain repairable. Updating
    incremental signatures never changes completion, text, capture time or IDs.
    Caller holds the palace mutation session and source lock.
    """
    root = collection_palace_path(collection)
    if root is None:
        return False
    try:
        manifest = json.loads(revision_manifest_path(root, identity, revision).read_text())
        groups = ((collection, "drawer"), (closets, "closet"))
        updates = []
        for table, kind in groups:
            ids = manifest.get(f"{kind}_ids")
            if not isinstance(ids, list):
                return False
            if not ids:
                continue
            if table is None:
                # Project callers may omit closets; still verify stored targets.
                from .palace import get_closets_collection

                table = get_closets_collection(str(root), create=False)
            first = True
            for rid, meta in _revision_rows(table, ids):
                if (
                    revision_identity(meta.get("source_file", ""), meta) != identity
                    or meta.get("source_revision") != revision
                    or meta.get("ingest_complete") is not True
                    or meta.get("completion_protocol") != 1
                ):
                    return False
                if first and not revision_completed(root, meta, record_id=rid, record_kind=kind):
                    return False
                first = False
            if kind == "drawer":
                updates.append((table, ids))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False
    if signature:
        for table, ids in updates:
            _update_revision_hints(table, ids, signature)
    return True
