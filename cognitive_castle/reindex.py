"""Recoverable index-only rebuilds from stored records, including historic evidence.

Directory promotion uses two separately recoverable renames. The original index
is retained under a unique backup name; graph, registry and review files stay in
place. Source paths are preflight checks only: importing new content is a separate
operation. Callers must discard open collection handles after maintenance.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path


class ReindexError(RuntimeError):
    """Reindex or recovery cannot safely activate a verified index."""


class ReindexCancelled(ReindexError):
    """Cancellation stopped maintenance while retaining recoverable evidence."""


@dataclass(frozen=True)
class ReindexResult:
    status: str
    palace_path: str
    backup_path: str | None
    record_count: int
    recovered: bool = False


def _checkpoint(name: str) -> None:
    """Fault-injection seam for directory-promotion crash regressions."""


def _encoded(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def _digest(value) -> str:
    return hashlib.sha256(_encoded(value)).hexdigest()


def _sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_json(path: Path, payload) -> None:
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with temporary.open("xb") as stream:
            stream.write(_encoded({"payload": payload, "sha256": _digest(payload)}))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        _sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path):
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        payload = envelope["payload"]
        if envelope["sha256"] != _digest(payload):
            raise ValueError("checksum mismatch")
        return payload
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ReindexError("reindex intent checksum or format is invalid") from exc


def _connect(index: Path):
    import lancedb

    if not index.is_dir() or index.is_symlink():
        raise ReindexError("index directory is absent or is a symlink")
    return lancedb.connect(str(index))


def _signature(index: Path) -> dict:
    """Hash schema and complete raw rows, independent of physical file layout."""
    db = _connect(index)
    tables = {}
    for name in sorted(db.table_names()):
        table = db.open_table(name)
        rows = table.to_arrow().to_pylist()
        # Some tables have no ID; sorting canonical row bytes preserves duplicates.
        row_hashes = sorted(_digest(row) for row in rows)
        tables[name] = {
            "schema": str(table.schema),
            "rows": len(rows),
            "sha256": _digest(row_hashes),
        }
    return tables


def _matches(index: Path, signature: dict) -> bool:
    try:
        return _signature(index) == signature
    except Exception:
        return False


def _cancel_if_requested(cancelled) -> None:
    if cancelled():
        raise ReindexCancelled("reindex cancelled; original index retained")


def _stage_index(active: Path, staging: Path, config, cancelled) -> tuple[dict, dict, int]:
    import lancedb
    import pyarrow as pa
    from .embedding import embed_texts

    source = _connect(active)
    staging.mkdir(parents=True)
    target = lancedb.connect(str(staging))
    count = 0
    names = source.table_names()
    for name in names:
        _cancel_if_requested(cancelled)
        table = source.open_table(name)
        schema = table.schema
        rows = table.to_arrow().to_pylist()
        if name == "castle_metadata":
            rows = [r for r in rows if r.get("key") != "embedder_identity"]
            rows.append({"key": "embedder_identity", "value": config.embedder_identity})
        elif "vector" in schema.names:
            if "text" not in schema.names:
                raise ReindexError("vector table has no stored text")
            vector_field = schema.field("vector")
            schema = schema.set(
                schema.get_field_index("vector"),
                pa.field(
                    "vector",
                    pa.list_(pa.float32(), config.embedder_dim),
                    nullable=vector_field.nullable,
                    metadata=vector_field.metadata,
                ),
            )
            for start in range(0, len(rows), 128):
                _cancel_if_requested(cancelled)
                batch = rows[start : start + 128]
                vectors = embed_texts([r["text"] for r in batch], cfg=config)
                if len(vectors) != len(batch):
                    raise ReindexError("embedder did not return one vector per stored record")
                for row, vector in zip(batch, vectors):
                    if len(vector) != config.embedder_dim or any(
                        not math.isfinite(float(v)) for v in vector
                    ):
                        raise ReindexError("embedder returned invalid vectors")
                    row["vector"] = vector
            count += len(rows)
        rebuilt = target.create_table(name, pa.Table.from_pylist(rows, schema=schema))
        if "vector" in schema.names and "text" in schema.names:
            rebuilt.create_fts_index("text", replace=True)
        # Verify preservation using raw metadata, not the compatibility API's
        # normalized/hoisted metadata representation.
        copied = rebuilt.to_arrow().to_pylist()
        if name != "castle_metadata":
            original = table.to_arrow().to_pylist()

            def strip(row):
                return {k: v for k, v in row.items() if k != "vector"}

            if sorted(_digest(strip(r)) for r in original) != sorted(
                _digest(strip(r)) for r in copied
            ):
                raise ReindexError("staged index changed stored evidence")
    if "castle_metadata" not in names:
        target.create_table(
            "castle_metadata", [{"key": "embedder_identity", "value": config.embedder_identity}]
        )
    _sync_directory(staging)
    _sync_directory(staging.parent)
    _sync_directory(staging.parent.parent)
    return _signature(active), _signature(staging), count


def reindex_palace(
    palace_path, *, config, source_paths=(), cancelled=lambda: False
) -> ReindexResult:
    """Re-embed stored rows and promote a verified index under the palace lock.

    Existing backups are never overwritten. A failed promotion leaves a
    checksummed intent for ``recover_reindex``; no failure is reported as success.
    """
    from .palace import mutation_session

    root = Path(palace_path).expanduser().resolve()
    for source in source_paths:
        if not Path(source).expanduser().exists():
            raise FileNotFoundError(source)
    _cancel_if_requested(cancelled)
    with mutation_session(root):
        intent_path = root / ".reindex-intent.json"
        if intent_path.exists():
            raise ReindexError("pending reindex requires recover_reindex before another rebuild")
        active = root / "lancedb"
        _connect(active)
        _checkpoint("before_staging")
        operation = uuid.uuid4().hex
        staging = root / f".reindex-stage-{operation}" / "lancedb"
        backup = root / f"lancedb.backup-{operation}"
        if backup.exists() or backup.is_symlink() or staging.parent.exists():
            raise ReindexError("reindex backup or staging operation already exists")
        source, target, count = _stage_index(active, staging, config, cancelled)
        intent = {
            "version": 1,
            "root": str(root),
            "operation": operation,
            "source": source,
            "target": target,
            "record_count": count,
        }
        _atomic_json(intent_path, intent)
        _cancel_if_requested(cancelled)
        _checkpoint("before_move")
        if not _matches(active, source) or not _matches(staging, target):
            raise ReindexError("index verification failed before promotion")
        if backup.exists() or backup.is_symlink():
            raise ReindexError("reindex backup already exists")
        active.rename(backup)
        _sync_directory(root)
        _checkpoint("after_move")
        staging.rename(active)
        _sync_directory(root)
        _checkpoint("after_promotion")
        if not _matches(active, target) or not _matches(backup, source):
            raise ReindexError("index verification failed after promotion; recovery required")
        intent_path.unlink()
        _sync_directory(root)
        return ReindexResult("complete", str(root), str(backup), count)


def recover_reindex(palace_path) -> ReindexResult:
    """Finish a verified staged promotion, or restore from a retained backup.

    Corrupt/unknown active data is retained under a unique quarantine name before
    recovery. An unverifiable source and target are never claimed to be repaired.
    """
    from .palace import mutation_session

    root = Path(palace_path).expanduser().resolve()
    with mutation_session(root):
        intent_path = root / ".reindex-intent.json"
        if not intent_path.exists():
            return ReindexResult("nothing_to_recover", str(root), None, 0, True)
        intent = _read_json(intent_path)
        operation = intent.get("operation")
        if (
            intent.get("version") != 1
            or intent.get("root") != str(root)
            or not isinstance(operation, str)
            or not re.fullmatch(r"[a-f0-9]{32}", operation)
        ):
            raise ReindexError("invalid reindex intent binding")
        active = root / "lancedb"
        staging = root / f".reindex-stage-{operation}" / "lancedb"
        backup = root / f"lancedb.backup-{operation}"
        # Never follow an operator-modified symlink out of the bound root.
        if any(p.is_symlink() for p in (active, staging.parent, staging, backup)):
            raise ReindexError("reindex recovery refuses symlink paths")
        source, target = intent["source"], intent["target"]
        active_target = _matches(active, target)
        backup_source = _matches(backup, source)
        if active_target:
            if not backup_source:
                raise ReindexError("promoted index has no verified original backup")
            status = "complete"
        elif _matches(staging, target):
            if not backup_source:
                if not _matches(active, source) or backup.exists():
                    raise ReindexError("original index cannot be verified for promotion")
                active.rename(backup)
                _sync_directory(root)
            elif active.exists():
                active.rename(root / f"lancedb.incomplete-{uuid.uuid4().hex}")
                _sync_directory(root)
            staging.rename(active)
            _sync_directory(root)
            if not _matches(active, target):
                raise ReindexError("recovered index verification failed")
            status = "complete"
        elif backup_source:
            if active.exists():
                active.rename(root / f"lancedb.incomplete-{uuid.uuid4().hex}")
                _sync_directory(root)
            shutil.copytree(backup, active)
            if not _matches(active, source):
                raise ReindexError("restored original verification failed")
            status = "rolled_back"
        elif _matches(active, source) and not backup.exists():
            status = "rolled_back"
        else:
            raise ReindexError("no verified index available for recovery")
        intent_path.unlink()
        _sync_directory(root)
        return ReindexResult(
            status,
            str(root),
            str(backup) if backup.exists() else None,
            intent["record_count"],
            True,
        )
