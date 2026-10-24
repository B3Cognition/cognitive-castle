"""Supervised, resumable exact-text conversion of immutable private Lance copies.

This module never spawns, opens a live native archive, or imports a native library
at module import time. The caller supplies admission, pressure and RSS supervision.
The native adapter remains subject to installed-stack/corpus qualification.
"""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import time

from cognitive_castle.fast_memory import (
    MAX_STORE_BYTES,
    MemoryStore,
    _Corrupt,
    _Quota,
    _Unavailable,
    _hash,
    _json,
)

MAX_SNAPSHOT_BYTES = 4 * 1024**3
FREE_HEADROOM_BYTES = 2 * 1024**3
MAX_FILES = 4096
MAX_HISTORY_STORES = 8
COPY_BLOCK_BYTES = 1024**2
COPY_SLICE_BYTES = 64 * 1024**2
# Freeze the existing native acceptance envelope independently of the exact
# text limit. A text already admitted by that scanner can use many 8 KiB chunks.
MAX_NATIVE_BATCH_BYTES = 2 * 1024**2 + 65536
MAX_ROW_BYTES = MAX_NATIVE_BATCH_BYTES
MAX_METADATA_BYTES = 1024**2
JOB_BYTES = 2 * 1024**2
SLICE_SECONDS = 6
IO_BUFFER_BYTES = 32 * 1024**2
PROJECTED_PAGE_CHARACTERS = 131072
MIN_FINAL_PHASE_SECONDS = 1


class _HistoryError(Exception):
    def __init__(self, status):
        self.status = status


def _identity(info):
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def _safe_ancestors(path):
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise _HistoryError("unsafe_source")


def _private(path, directory=False):
    info = path.lstat()
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise _HistoryError("unavailable")
    if not directory and info.st_nlink != 1:
        raise _HistoryError("unavailable")
    return info


def _root(palace, create=False):
    palace = Path(palace).absolute()
    _safe_ancestors(palace)
    root = palace / ".memory-history"
    if create:
        root.mkdir(mode=0o700, exist_ok=True)
    if root.exists():
        _private(root, True)
    return root


def _atomic_json(path, value):
    raw = _json(value).encode()
    if len(raw) > JOB_BYTES:
        raise _HistoryError("quota")
    if path.exists() or path.is_symlink():
        _private(path)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists() or temporary.is_symlink():
        _private(temporary)
        temporary.unlink()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()


def _save_job(palace, job):
    _atomic_json(_root(palace, True) / "job.json", job)


def _load_job(palace):
    root = _root(palace)
    path = root / "job.json"
    if not path.exists():
        return None
    info = _private(path)
    if info.st_size > JOB_BYTES:
        raise _HistoryError("corrupt")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "r", encoding="utf-8") as stream:
        job = json.load(stream)
    if not isinstance(job, dict) or job.get("format") != 1:
        raise _HistoryError("corrupt")
    identity = job.get("store_id", "")
    if len(identity) != 64 or any(c not in "0123456789abcdef" for c in identity):
        raise _HistoryError("corrupt")
    snapshot_id = job.get("snapshot_id", identity)
    if len(snapshot_id) != 64 or any(c not in "0123456789abcdef" for c in snapshot_id):
        raise _HistoryError("corrupt")
    snapshot = root / "snapshots" / snapshot_id
    if job.get("snapshot") != str(snapshot):
        raise _HistoryError("corrupt")
    stores = job.get("stores")
    if not isinstance(stores, list) or not 1 <= len(stores) <= MAX_HISTORY_STORES:
        raise _HistoryError("corrupt")
    seen = set()
    for shard in stores:
        value = shard.get("store_id", "")
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value) or value in seen:
            raise _HistoryError("corrupt")
        seen.add(value)
        if any(
            type(shard.get(key)) is not int or shard[key] < 0 for key in ("indexed_rows", "gaps")
        ):
            raise _HistoryError("corrupt")
    if identity not in seen:
        raise _HistoryError("corrupt")
    for cursor in (job.get("cursor"), job.get("inflight", job.get("cursor"))):
        if not isinstance(cursor, dict) or any(
            type(cursor.get(key)) is not int or not 0 <= cursor[key] < 2**63
            for key in ("fragment", "offset")
        ):
            raise _HistoryError("corrupt")
    if not isinstance(job.get("inventory"), list) or len(job["inventory"]) > MAX_FILES:
        raise _HistoryError("corrupt")
    for item in job["inventory"]:
        name = Path(item["path"])
        if name.is_absolute() or ".." in name.parts or str(name) != item["path"]:
            raise _HistoryError("corrupt")
    return job


def _mkdir_private(path, base):
    relative = path.relative_to(base)
    current = base
    _private(current, True)
    for part in relative.parts:
        current = current / part
        current.mkdir(mode=0o700, exist_ok=True)
        _private(current, True)


def _free_bytes(path):
    return shutil.disk_usage(path).free


def _tree_bytes(root):
    total = 0
    count = 0
    if not root.exists():
        return 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in [*dirs, *files]:
            path = Path(directory) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not (
                stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)
            ):
                raise _HistoryError("unsafe_source")
            count += 1
            if count > MAX_FILES * 10:
                raise _HistoryError("quota")
            if stat.S_ISREG(info.st_mode):
                total += info.st_size
    return total


def _inventory(source):
    _safe_ancestors(source)
    root_info = source.lstat()
    if not stat.S_ISDIR(root_info.st_mode):
        raise _HistoryError("unsafe_source")
    entries = []
    count = 0
    total = 0
    for directory, dirs, files in os.walk(source, followlinks=False):
        dirs.sort()
        files.sort()
        for name in [*dirs, *files]:
            path = Path(directory) / name
            info = path.lstat()
            count += 1
            if count > MAX_FILES:
                raise _HistoryError("quota")
            if stat.S_ISDIR(info.st_mode):
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise _HistoryError("unsafe_source")
            total += info.st_size
            if total > MAX_SNAPSHOT_BYTES:
                raise _HistoryError("quota")
            entries.append(
                {"path": str(path.relative_to(source)), "identity": _identity(info), "copied": 0}
            )
    entries.sort(key=lambda entry: entry["path"])
    versions = []
    for entry in entries:
        path = Path(entry["path"])
        if path.parent == Path("_versions") and path.suffix == ".manifest" and path.stem.isdigit():
            value = int(path.stem)
            # Lance v2 manifest names use inverse u64 version ordering.
            version = (2**64 - 1 - value) if value > 2**63 else value
            if version > 0:
                versions.append(version)
    if not versions:
        raise _HistoryError("unsupported")
    return root_info, entries, total, max(versions)


def _validate_original(job):
    source = Path(job["source"])
    info, current, total, version = _inventory(source)
    if (
        [info.st_dev, info.st_ino] != job["source_identity"]
        or total != job["source_bytes"]
        or version != job["version"]
    ):
        raise _HistoryError("changed")
    if [(i["path"], i["identity"]) for i in current] != [
        (i["path"], i["identity"]) for i in job["inventory"]
    ]:
        raise _HistoryError("changed")


def _interactive_waiting():
    # Advisory priority only: pressure/admission remain the supervisor's job.
    from cognitive_castle.memory_runtime import interactive_waiting

    return interactive_waiting()


def _yielded(job):
    return {**_summary(job), "yielded": "interactive_waiting"}


def _summary(job):
    if not job:
        return {"status": "ok", "state": "not_registered", "coverage_complete": False}
    return {
        "status": "ok",
        "state": job["state"],
        "store_id": job["store_id"],
        "archive_id": job["archive_id"],
        "version": job["version"],
        "source_bytes": job["source_bytes"],
        "copied_bytes": sum(item["copied"] for item in job["inventory"]),
        "indexed_rows": job.get("indexed_rows", 0),
        "gaps": job.get("gaps", 0),
        "total_rows": job.get("total_rows"),
        "coverage_complete": job["state"] == "complete" and not job.get("gaps"),
        **({"reason": job["reason"]} if job.get("reason") else {}),
        **({"partial_row": job["partial_row"]} if job.get("partial_row") else {}),
    }


def _prepare_decision(job, source):
    if not job:
        return "new", None
    if job["source"] != str(source):
        if job["state"] != "complete":
            raise _HistoryError("conflict")
        return "new", None
    if job["state"] == "changed":
        return "new", None
    if job["state"] == "copying":
        return "resume", None
    if job["state"] != "complete":
        return "reuse", None
    inventory_state = _inventory(source)
    info, inventory, total, version = inventory_state
    unchanged = (
        [info.st_dev, info.st_ino] == job["source_identity"]
        and total == job["source_bytes"]
        and version == job["version"]
        and [(i["path"], i["identity"]) for i in inventory]
        == [(i["path"], i["identity"]) for i in job["inventory"]]
    )
    return ("reuse" if unchanged else "new"), inventory_state


def _snapshot_directory(palace, snapshot, previous):
    try:
        snapshot.mkdir(mode=0o700)
        return
    except FileExistsError:
        pass
    # A crash before the first durable job write can leave exactly this empty
    # directory. Adopt only a private, stable directory with no catalog/job
    # reference; populated copies always require their existing durable ledger.
    before = _private(snapshot, True)
    if stat.S_IMODE(before.st_mode) != 0o700 or any(snapshot.iterdir()):
        raise _HistoryError("conflict")
    if previous and previous["snapshot_id"] == snapshot.name:
        raise _HistoryError("conflict")
    from cognitive_castle.unified_memory import _catalog

    catalog, _ = _catalog(palace)
    if any(entry["store_id"] == snapshot.name for entry in catalog["stores"]):
        raise _HistoryError("conflict")
    archived = _root(palace) / "jobs" / (snapshot.name + ".json")
    if archived.exists() or archived.is_symlink():
        raise _HistoryError("conflict")
    if _identity(snapshot.lstat()) != _identity(before):
        raise _HistoryError("conflict")


def _prepare(palace, source, deadline):
    root = _root(palace, True)
    job = _load_job(palace)
    source = Path(source).absolute()
    previous = job
    decision, fresh_inventory = _prepare_decision(job, source)
    if decision == "reuse":
        return _summary(job)
    if decision == "new":
        info, inventory, total, version = fresh_inventory or _inventory(source)
        snapshots = root / "snapshots"
        snapshots.mkdir(mode=0o700, exist_ok=True)
        _private(snapshots, True)
        if (
            _tree_bytes(snapshots) + total > MAX_SNAPSHOT_BYTES
            or _free_bytes(root) < FREE_HEADROOM_BYTES + total
        ):
            raise _HistoryError("quota")
        archive_id = _hash(_json([str(source), info.st_dev, info.st_ino]))
        store_id = _hash(_json([archive_id, version, inventory]))
        snapshot = snapshots / store_id
        _snapshot_directory(palace, snapshot, previous)
        job = {
            "format": 1,
            "source": str(source),
            "source_identity": [info.st_dev, info.st_ino],
            "archive_id": archive_id,
            "store_id": store_id,
            "snapshot_id": store_id,
            "stores": [{"store_id": store_id, "indexed_rows": 0, "gaps": 0}],
            "version": version,
            "snapshot": str(snapshot),
            "inventory": inventory,
            "source_bytes": total,
            "state": "copying",
            "cursor": {"fragment": 0, "offset": 0},
            "indexed_rows": 0,
            "gaps": 0,
        }
        if previous:
            jobs = root / "jobs"
            jobs.mkdir(mode=0o700, exist_ok=True)
            _private(jobs, True)
            _atomic_json(jobs / (previous["snapshot_id"] + ".json"), previous)
        if previous and previous["state"] == "changed" and not previous["indexed_rows"]:
            # Only never-indexed invalid pins are superseded. Their private
            # files remain counted in snapshot admission; committed stores are
            # retained as distinct historical versions.
            job["supersedes"] = {
                "store_id": previous["store_id"],
                "archive_id": previous["archive_id"],
            }
        _save_job(palace, job)
    try:
        _publish(palace, job)
        _validate_original(job)
        snapshot = Path(job["snapshot"])
        _private(snapshot, True)
        admitted = 0
        for item in job["inventory"]:
            if item["copied"] >= item["identity"][2]:
                continue
            destination = snapshot / item["path"]
            _mkdir_private(destination.parent, snapshot)
            _safe_ancestors(destination)
            if destination.exists():
                _private(destination)
            source_path = source / item["path"]
            _safe_ancestors(source_path)
            incoming = os.open(source_path, os.O_RDONLY | os.O_NOFOLLOW)
            outgoing = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            try:
                if _identity(os.fstat(incoming)) != item["identity"]:
                    raise _HistoryError("changed")
                if os.fstat(outgoing).st_size < item["copied"]:
                    raise _HistoryError("corrupt")
                os.ftruncate(outgoing, item["copied"])
                os.lseek(incoming, item["copied"], os.SEEK_SET)
                os.lseek(outgoing, item["copied"], os.SEEK_SET)
                while item["copied"] < item["identity"][2]:
                    if _interactive_waiting():
                        return _yielded(job)
                    if admitted >= COPY_SLICE_BYTES or time.monotonic() >= deadline:
                        return _summary(job)
                    if _free_bytes(root) < FREE_HEADROOM_BYTES + COPY_BLOCK_BYTES:
                        raise _HistoryError("quota")
                    block = os.read(incoming, min(COPY_BLOCK_BYTES, COPY_SLICE_BYTES - admitted))
                    if not block:
                        raise _HistoryError("changed")
                    view = memoryview(block)
                    while view:
                        written = os.write(outgoing, view)
                        if not written:
                            raise OSError("snapshot write failed")
                        view = view[written:]
                    os.fsync(outgoing)
                    if _identity(os.fstat(incoming)) != item["identity"]:
                        raise _HistoryError("changed")
                    item["copied"] += len(block)
                    admitted += len(block)
                    _save_job(palace, job)
            finally:
                os.close(incoming)
                os.close(outgoing)
        if _interactive_waiting():
            return _yielded(job)
        _validate_original(job)
        # Copy-time descriptors prove source identity; destination identity pins
        # the read-only working files, including ctime, for every future slice.
        for item in job["inventory"]:
            destination = snapshot / item["path"]
            if not destination.exists():  # zero-length source
                _mkdir_private(destination.parent, snapshot)
                descriptor = os.open(
                    destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                )
                os.close(descriptor)
            destination.chmod(0o400)
            item["snapshot_identity"] = _identity(destination.lstat())
        for directory, _, _ in os.walk(snapshot, topdown=False):
            Path(directory).chmod(0o500)
        job["state"] = "prepared"
        _save_job(palace, job)
        return _summary(job)
    except _HistoryError as exc:
        if exc.status == "changed":
            job["state"] = "changed"
            _save_job(palace, job)
            _publish(palace, job)
        raise


def _validate_snapshot(job):
    snapshot = Path(job["snapshot"])
    _safe_ancestors(snapshot)
    _private(snapshot, True)
    expected = {item["path"]: item for item in job["inventory"]}
    seen = set()
    for directory, dirs, files in os.walk(snapshot, followlinks=False):
        for name in dirs:
            path = Path(directory) / name
            if path.is_symlink():
                raise _HistoryError("changed")
            _private(path, True)
        for name in files:
            path = Path(directory) / name
            info = _private(path)
            relative = str(path.relative_to(snapshot))
            if (
                relative not in expected
                or _identity(info) != expected[relative].get("snapshot_identity")
                or info.st_mode & 0o222
            ):
                raise _HistoryError("changed")
            seen.add(relative)
    if seen != set(expected):
        raise _HistoryError("changed")


def _scan_rows(snapshot, version, cursor):
    """Streaming pinned-version adapter; no table/Arrow materialization fallback.

    offset is deletion-aware within an immutable physical fragment. _rowaddr is
    retained and checked independently; efficient offset pushdown and oversized
    decoding still require the supervised installed-stack qualification.
    """
    import lance

    dataset = lance.dataset(
        str(snapshot),
        version=version,
        metadata_cache_size_bytes=4 * 1024**2,
        index_cache_size_bytes=1024**2,
        read_params={"cache_repetition_index": False, "validate_on_decode": True},
    )
    if dataset.version != version:
        raise _HistoryError("changed")
    names = dataset.schema.names
    if any(name not in names for name in ("id", "text", "metadata_json")):
        raise _HistoryError("unsupported")
    columns = [name for name in names if name != "vector"]
    if len(columns) > 32:
        raise _HistoryError("unsupported")
    fragments = sorted(dataset.get_fragments(), key=lambda fragment: fragment.fragment_id)
    if len(fragments) > MAX_FILES:
        raise _HistoryError("quota")
    for fragment in fragments:
        fragment_id = fragment.fragment_id
        if fragment_id < cursor["fragment"]:
            continue
        offset = cursor["offset"] if fragment_id == cursor["fragment"] else 0
        scanner = dataset.scanner(
            columns=columns,
            fragments=[fragment],
            offset=offset,
            batch_size=1,
            strict_batch_size=True,
            batch_readahead=0,
            fragment_readahead=0,
            scan_in_order=True,
            with_row_address=True,
            io_buffer_size=IO_BUFFER_BYTES,
            use_scalar_index=False,
        )
        for batch in scanner.to_batches():
            if batch.nbytes > MAX_NATIVE_BATCH_BYTES:
                raise _HistoryError("native_batch_size")
            for row_number in range(batch.num_rows):
                values = {
                    name: batch.column(batch.schema.get_field_index(name))[row_number].as_py()
                    for name in columns
                }
                address = batch.column(batch.schema.get_field_index("_rowaddr"))[row_number].as_py()
                if (
                    type(address) is not int
                    or address >> 32 != fragment_id
                    or (
                        fragment_id == cursor["fragment"]
                        and address <= cursor.get("row_address", -1)
                    )
                ):
                    raise _HistoryError("corrupt")
                offset += 1
                yield {
                    "fragment": fragment_id,
                    "row_address": address,
                    "offset": offset,
                    "values": values,
                }


def _store(palace, job, store_id=None):
    from cognitive_castle.unified_memory import history_store_path

    return MemoryStore(history_store_path(palace, store_id or job["store_id"]))


def _schema(conn):
    for statement in [
        "CREATE TABLE IF NOT EXISTS history_occurrences (identity TEXT PRIMARY KEY, cursor_key TEXT UNIQUE NOT NULL, row_address INTEGER NOT NULL, alias TEXT, metadata_json TEXT NOT NULL, columns_json TEXT NOT NULL, text_hash TEXT NOT NULL, ids TEXT NOT NULL, metadata_hash TEXT NOT NULL, columns_hash TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS history_aliases (alias TEXT NOT NULL, identity TEXT NOT NULL, PRIMARY KEY(alias,identity))",
        "CREATE TABLE IF NOT EXISTS history_gaps (cursor_key TEXT PRIMARY KEY, identity TEXT NOT NULL, reason TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS history_attempts (cursor_key TEXT PRIMARY KEY, next_cursor TEXT NOT NULL, outcome TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS history_gap_resolutions (cursor_key TEXT PRIMARY KEY, identity TEXT NOT NULL, reason TEXT NOT NULL, next_cursor TEXT NOT NULL, snapshot_id TEXT NOT NULL, text_hash TEXT NOT NULL, metadata_hash TEXT NOT NULL, columns_hash TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS history_staged_rows (cursor_key TEXT PRIMARY KEY, identity TEXT UNIQUE NOT NULL, snapshot_id TEXT NOT NULL, source_cursor TEXT NOT NULL, next_cursor TEXT NOT NULL, metadata_json TEXT NOT NULL, columns_json TEXT NOT NULL, text_bytes INTEGER NOT NULL, text_characters INTEGER NOT NULL, next_character INTEGER NOT NULL, chunk_start INTEGER NOT NULL, carry TEXT NOT NULL, processed_bytes INTEGER NOT NULL, state TEXT NOT NULL, inflight_character INTEGER, retry_character INTEGER, retry_count INTEGER NOT NULL DEFAULT 0, text_hash TEXT, expected_hash TEXT, reason TEXT, phase_inflight TEXT, hash_failures INTEGER NOT NULL DEFAULT 0, publication_failures INTEGER NOT NULL DEFAULT 0, final_deferrals INTEGER NOT NULL DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS history_staged_chunks (cursor_key TEXT NOT NULL,start INTEGER NOT NULL,end INTEGER NOT NULL,id TEXT UNIQUE NOT NULL,text TEXT NOT NULL,text_hash TEXT NOT NULL,PRIMARY KEY(cursor_key,start))",
        "CREATE TABLE IF NOT EXISTS history_occurrence_chunks (identity TEXT NOT NULL,chunk_id TEXT NOT NULL,PRIMARY KEY(identity,chunk_id))",
    ]:
        conn.execute(statement)


def _cursor_key(cursor):
    return _hash(_json(cursor))


def _counts(conn):
    return (
        conn.execute("SELECT count(*) FROM history_occurrences").fetchone()[0],
        conn.execute("SELECT count(*) FROM history_gaps").fetchone()[0],
    )


def _chunks(text):
    start, part, size = 0, [], 0
    for character in text:
        width = len(character.encode())
        if size + width > 8192:
            value = "".join(part)
            yield start, value
            start += len(value)
            part, size = [], 0
        part.append(character)
        size += width
    if part:
        yield start, "".join(part)


def _commit_row(store, job, row, cursor, *, repair=False):
    values = row["values"]
    address = row["row_address"]
    fragment = row["fragment"]
    if (
        type(address) is not int
        or not 0 <= address < 2**63
        or type(fragment) is not int
        or address >> 32 != fragment
    ):
        raise _HistoryError("corrupt")
    next_cursor = {"fragment": fragment, "offset": row["offset"], "row_address": address}
    occurrence = _hash(
        _json([job["archive_id"], job["snapshot_id"], job["version"], fragment, address])
    )
    key = _cursor_key(cursor)
    text = values.get("text")
    metadata = values.get("metadata_json")
    alias = values.get("id")
    reason = None
    if not isinstance(text, str) or not isinstance(metadata, str) or not isinstance(alias, str):
        reason = "invalid_metadata"
    else:
        try:
            if len(text.encode()) > MAX_ROW_BYTES:
                reason = "row_size"
            elif len(metadata.encode()) > MAX_METADATA_BYTES or len(alias.encode()) > 4096:
                reason = "metadata_size"
            elif not isinstance(json.loads(metadata), dict):
                reason = "invalid_metadata"
            columns = _json(
                {k: v for k, v in values.items() if k not in ("text", "metadata_json", "vector")}
            )
            if len(columns.encode()) > MAX_METADATA_BYTES:
                reason = "metadata_size"
        except (UnicodeError, ValueError, TypeError, RecursionError):
            reason = "invalid_metadata"
    if _free_bytes(store.directory.parent) < FREE_HEADROOM_BYTES + 16 * (
        MAX_ROW_BYTES + MAX_METADATA_BYTES
    ):
        raise _HistoryError("quota")
    with store._connect(True) as conn:
        _schema(conn)
        previous = conn.execute(
            "SELECT next_cursor,outcome FROM history_attempts WHERE cursor_key=?", (key,)
        ).fetchone()
        if previous:
            if json.loads(previous[0]) != next_cursor:
                if repair:
                    raise _HistoryError("repair_refused")
                raise _Corrupt("changed occurrence cursor")
            if not repair:
                return next_cursor, *_counts(conn)
        if repair:
            gap = conn.execute(
                "SELECT identity,reason FROM history_gaps WHERE cursor_key=?", (key,)
            ).fetchone()
            if (
                not previous
                or previous["outcome"] != "gap"
                or gap is None
                or gap["identity"] != occurrence
                or gap["reason"] != "row_size"
                or reason is not None
            ):
                raise _HistoryError("repair_refused")
        if reason:
            conn.execute("INSERT INTO history_gaps VALUES (?,?,?)", (key, occurrence, reason))
        else:
            # Exact metadata/hoisted fields are registered separately; only bounded
            # references and explicit scopes enter the public provenance envelope.
            caller = {
                "archive_id": job["archive_id"],
                "version": job["version"],
                "metadata_id": occurrence,
            }
            for scope in ("workspace", "wing", "room"):
                value = values.get(scope)
                if value is None:
                    value = json.loads(metadata).get(scope)
                if isinstance(value, str) and value and len(value.encode()) <= 64:
                    candidate = {**caller, scope: value}
                    if len(_json(candidate).encode()) <= 512:
                        caller = candidate
            provenance = _json(caller)
            identities = []
            for offset, chunk in _chunks(text):
                identity = "memory:" + _hash(_json([occurrence, offset]))
                identities.append(identity)
                MemoryStore._provenance(caller, _hash(chunk), offset, offset + len(chunk))
                conn.execute(
                    "INSERT INTO chunks VALUES (?,?,?,?,?,?)",
                    (identity, chunk, provenance, _hash(chunk), offset, offset + len(chunk)),
                )
                conn.execute("INSERT INTO lexical VALUES (?,?)", (identity, chunk))
            conn.execute(
                "INSERT INTO history_occurrences (identity,cursor_key,row_address,alias,metadata_json,columns_json,text_hash,ids,metadata_hash,columns_hash) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    occurrence,
                    key,
                    address,
                    alias,
                    metadata,
                    columns,
                    _hash(text),
                    _json(identities),
                    _hash(metadata),
                    _hash(columns),
                ),
            )
            conn.execute("INSERT INTO history_aliases VALUES (?,?)", (alias, occurrence))
        if repair:
            conn.execute(
                "INSERT INTO history_gap_resolutions VALUES (?,?,?,?,?,?,?,?)",
                (
                    key,
                    occurrence,
                    gap["reason"],
                    _json(next_cursor),
                    job["snapshot_id"],
                    _hash(text),
                    _hash(metadata),
                    _hash(columns),
                ),
            )
            conn.execute("DELETE FROM history_gaps WHERE cursor_key=?", (key,))
            conn.execute("UPDATE history_attempts SET outcome='indexed' WHERE cursor_key=?", (key,))
        else:
            conn.execute(
                "INSERT INTO history_attempts VALUES (?,?,?)",
                (key, _json(next_cursor), "gap" if reason else "indexed"),
            )
        indexed, gaps = _counts(conn)
    return next_cursor, indexed, gaps


def _update_counts(job, indexed, gaps):
    for shard in job["stores"]:
        if shard["store_id"] == job["store_id"]:
            shard["indexed_rows"], shard["gaps"] = indexed, gaps
    job["indexed_rows"] = sum(shard["indexed_rows"] for shard in job["stores"])
    job["gaps"] = sum(shard["gaps"] for shard in job["stores"])


def _publish(palace, job):
    from cognitive_castle.unified_memory import register_history_store, supersede_history_store

    previous = job.get("supersedes")
    if previous:
        result = supersede_history_store(
            palace,
            previous["store_id"],
            job["store_id"],
            archive_id=job["archive_id"],
            previous_archive_id=previous["archive_id"],
            state="pending",
        )
        if result.get("status") != "ok":
            raise _HistoryError(result.get("status", "unavailable"))
        job.pop("supersedes")
        _save_job(palace, job)
    for shard in job["stores"]:
        complete = job["state"] == "complete"
        state = (
            "complete"
            if complete
            else (
                "pending"
                if job["state"] in ("copying", "prepared")
                else (
                    "changed"
                    if job["state"] == "changed"
                    else ("blocked" if shard["gaps"] or job.get("reason") else "indexing")
                )
            )
        )
        result = register_history_store(
            palace,
            shard["store_id"],
            archive_id=job["archive_id"],
            state=state,
            indexed_rows=shard["indexed_rows"],
            total_rows=shard["indexed_rows"] if complete else None,
        )
        if result.get("status") != "ok":
            raise _HistoryError(result.get("status", "unavailable"))


def _rollover(palace, job):
    if len(job["stores"]) >= MAX_HISTORY_STORES:
        job["state"], job["reason"] = "blocked", "output_capacity"
        _save_job(palace, job)
        _publish(palace, job)
        raise _HistoryError("quota")
    store_id = _hash(_json([job["snapshot_id"], "shard", len(job["stores"])]))
    job["stores"].append({"store_id": store_id, "indexed_rows": 0, "gaps": 0})
    job["store_id"] = store_id
    # Publish the pending store before acknowledging rollover; a crash cannot
    # make the exhausted earlier shards appear like complete archive coverage.
    _publish(palace, job)
    _save_job(palace, job)
    return _store(palace, job)


def _physical_quota(exc):
    return isinstance(exc, _Quota) or (
        isinstance(exc, sqlite3.Error) and getattr(exc, "sqlite_errorcode", 0) & 255 == 13
    )


def _projected_row(snapshot, version, cursor):
    from .history_projection import NativeProjectedRow

    return NativeProjectedRow(snapshot, version, cursor)


def _stage_header(header, job, cursor):
    required = {
        "fragment",
        "offset",
        "row_address",
        "values",
        "text_bytes",
        "text_characters",
        "text_hash",
    }
    if not isinstance(header, dict) or set(header) != required:
        raise _HistoryError("corrupt")
    following = {field: header[field] for field in ("fragment", "offset", "row_address")}
    if (
        not _valid_repair_cursor(following)
        or following["fragment"] < cursor["fragment"]
        or following["offset"]
        != (cursor["offset"] + 1 if following["fragment"] == cursor["fragment"] else 1)
        or (
            following["fragment"] == cursor["fragment"]
            and following["row_address"] <= cursor.get("row_address", -1)
        )
        or any(
            type(header[name]) is not int or not 0 <= header[name] < 2**63
            for name in ("text_bytes", "text_characters")
        )
        or not header["text_characters"] <= header["text_bytes"] <= 4 * header["text_characters"]
        or not isinstance(header["text_hash"], str)
        or len(header["text_hash"]) != 64
        or any(character not in "0123456789abcdef" for character in header["text_hash"])
    ):
        raise _HistoryError("corrupt")
    values = header["values"]
    if not isinstance(values, dict) or len(values) > 32 or "text" in values or "vector" in values:
        raise _HistoryError("corrupt")
    metadata = values.get("metadata_json")
    alias = values.get("id")
    if not isinstance(metadata, str) or not isinstance(alias, str):
        raise _HistoryError("invalid_metadata")
    columns = _json({key: value for key, value in values.items() if key != "metadata_json"})
    if (
        len(metadata.encode()) > MAX_METADATA_BYTES
        or len(columns.encode()) > MAX_METADATA_BYTES
        or len(alias.encode()) > 4096
    ):
        raise _HistoryError("metadata_size")
    if not isinstance(json.loads(metadata), dict):
        raise _HistoryError("invalid_metadata")
    occurrence = _hash(
        _json(
            [
                job["archive_id"],
                job["snapshot_id"],
                job["version"],
                following["fragment"],
                following["row_address"],
            ]
        )
    )
    return following, occurrence, metadata, columns


def _stage_record(store, job):
    with store._connect() as conn:
        row = conn.execute(
            "SELECT * FROM history_staged_rows WHERE cursor_key=?", (_cursor_key(job["cursor"]),)
        ).fetchone()
        if row is None:
            return None
        value = dict(row)
    if value["snapshot_id"] != job["snapshot_id"] or value["source_cursor"] != _json(job["cursor"]):
        raise _HistoryError("corrupt")
    following = json.loads(value["next_cursor"])
    header = {
        **following,
        "values": {**json.loads(value["columns_json"]), "metadata_json": value["metadata_json"]},
        "text_bytes": value["text_bytes"],
        "text_characters": value["text_characters"],
        "text_hash": value["expected_hash"],
    }
    _, identity, _, _ = _stage_header(header, job, job["cursor"])
    if (
        value["identity"] != identity
        or type(value["next_character"]) is not int
        or not 0 <= value["chunk_start"] <= value["next_character"] <= value["text_characters"]
        or not isinstance(value["carry"], str)
        or len(value["carry"].encode()) >= 8192
        or value["chunk_start"] + len(value["carry"]) != value["next_character"]
        or not 0 <= value["processed_bytes"] <= value["text_bytes"]
        or value["state"] not in ("copying", "hash_pending", "publication_pending", "blocked")
        or (value["text_hash"] is not None and value["text_hash"] != value["expected_hash"])
    ):
        raise _HistoryError("corrupt")
    value["header"] = header
    return value


def _stage_progress(job, store, staged):
    job["partial_row"] = {
        "store_id": store.directory.name,
        "cursor_key": staged["cursor_key"],
        "processed_characters": staged["next_character"],
        "total_characters": staged["text_characters"],
        "staged_bytes": staged["processed_bytes"],
        "state": staged["state"],
        **({"reason": staged["reason"]} if staged.get("reason") else {}),
    }


def _stage_begin(palace, job, store, header):
    following, occurrence, metadata, columns = _stage_header(header, job, job["cursor"])
    # Stage and publication coexist until the atomic handoff. This conservative
    # estimate reserves their text, lexical overhead and per-chunk records inside
    # the existing one-third SQLite page quota; it never enlarges that quota.
    estimate = (
        4 * header["text_bytes"]
        + 2 * (len(metadata.encode()) + len(columns.encode()))
        + (header["text_bytes"] // 8192 + 1) * 2048
        + 65536
    )
    if _free_bytes(store.directory.parent) < FREE_HEADROOM_BYTES + 3 * estimate:
        raise _HistoryError("quota")
    if estimate > MAX_STORE_BYTES // 3:
        job["state"], job["reason"] = "blocked", "row_output_capacity"
        job["partial_row"] = {
            "store_id": store.directory.name,
            "cursor_key": _cursor_key(job["cursor"]),
            "processed_characters": 0,
            "total_characters": header["text_characters"],
            "staged_bytes": 0,
            "state": "awaiting_capacity",
        }
        _save_job(palace, job)
        _publish(palace, job)
        raise _HistoryError("quota")
    with store._connect() as conn:
        used = (
            conn.execute("PRAGMA page_count").fetchone()[0]
            - conn.execute("PRAGMA freelist_count").fetchone()[0]
        ) * conn.execute("PRAGMA page_size").fetchone()[0]
    if used + estimate > MAX_STORE_BYTES // 3:
        store = _rollover(palace, job)
    with store._connect(True) as conn:
        _schema(conn)
        conn.execute(
            "INSERT INTO history_staged_rows (cursor_key,identity,snapshot_id,source_cursor,next_cursor,metadata_json,columns_json,text_bytes,text_characters,next_character,chunk_start,carry,processed_bytes,state,expected_hash) VALUES (?,?,?,?,?,?,?,?,?,0,0,'',0,?,?)",
            (
                _cursor_key(job["cursor"]),
                occurrence,
                job["snapshot_id"],
                _json(job["cursor"]),
                _json(following),
                metadata,
                columns,
                header["text_bytes"],
                header["text_characters"],
                "copying" if header["text_characters"] else "hash_pending",
                header["text_hash"],
            ),
        )
    return store


def _stage_page(store, staged, page):
    expected = min(PROJECTED_PAGE_CHARACTERS, staged["text_characters"] - staged["next_character"])
    if (
        not isinstance(page, str)
        or len(page) != expected
        or len(page.encode()) > 4 * PROJECTED_PAGE_CHARACTERS
    ):
        raise _HistoryError("corrupt")
    following = staged["next_character"] + len(page)
    processed = staged["processed_bytes"] + len(page.encode())
    if processed > staged["text_bytes"] or (
        following == staged["text_characters"] and processed != staged["text_bytes"]
    ):
        raise _HistoryError("corrupt")
    base = staged["chunk_start"]
    carry = ""
    chunk_start = base
    combined = staged["carry"] + page
    with store._connect(True) as conn:
        for offset, text in _chunks(combined):
            if (
                following != staged["text_characters"]
                and offset + len(text) == len(combined)
                and len(text.encode()) < 8192
            ):
                carry = text
                break
            start = base + offset
            identity = "memory:" + _hash(_json([staged["identity"], start]))
            conn.execute(
                "INSERT INTO history_staged_chunks VALUES (?,?,?,?,?,?)",
                (staged["cursor_key"], start, start + len(text), identity, text, _hash(text)),
            )
            chunk_start = start + len(text)
        conn.execute(
            "UPDATE history_staged_rows SET next_character=?,chunk_start=?,carry=?,processed_bytes=?,state=?,inflight_character=NULL,retry_character=NULL,retry_count=0 WHERE cursor_key=? AND next_character=?",
            (
                following,
                chunk_start,
                carry,
                processed,
                "hash_pending" if following == staged["text_characters"] else "copying",
                staged["cursor_key"],
                staged["next_character"],
            ),
        )


def _stage_caller(job, staged):
    values = json.loads(staged["columns_json"])
    metadata = json.loads(staged["metadata_json"])
    caller = {
        "archive_id": job["archive_id"],
        "version": job["version"],
        "metadata_id": staged["identity"],
    }
    for scope in ("workspace", "wing", "room"):
        value = values.get(scope)
        if value is None:
            value = metadata.get(scope)
        if (
            isinstance(value, str)
            and value
            and len(value.encode()) <= 64
            and len(_json({**caller, scope: value}).encode()) <= 512
        ):
            caller[scope] = value
    return values["id"], caller


def _stage_hash(store, staged, deadline):
    digest = hashlib.sha256()
    position = size = 0
    with store._connect() as conn:
        for row in conn.execute(
            "SELECT * FROM history_staged_chunks WHERE cursor_key=? ORDER BY start",
            (staged["cursor_key"],),
        ):
            if _interactive_waiting():
                raise _HistoryError("interactive_waiting")
            if time.monotonic() >= deadline:
                return None
            text = row["text"]
            if (
                row["start"] != position
                or row["end"] != position + len(text)
                or len(text.encode()) > 8192
                or row["text_hash"] != _hash(text)
                or row["id"] != "memory:" + _hash(_json([staged["identity"], position]))
            ):
                raise _HistoryError("corrupt")
            digest.update(text.encode())
            size += len(text.encode())
            position = row["end"]
    value = digest.hexdigest()
    if (
        position != staged["text_characters"]
        or size != staged["text_bytes"]
        or value != staged["expected_hash"]
    ):
        raise _HistoryError("corrupt")
    return value


def _stage_publish(store, job, staged, deadline):
    alias, caller = _stage_caller(job, staged)
    provenance = _json(caller)
    with store._connect(True) as conn:
        for row in conn.execute(
            "SELECT * FROM history_staged_chunks WHERE cursor_key=? ORDER BY start",
            (staged["cursor_key"],),
        ):
            if _interactive_waiting():
                raise _HistoryError("interactive_waiting")
            if time.monotonic() >= deadline:
                raise _HistoryError("deadline")
            MemoryStore._provenance(caller, row["text_hash"], row["start"], row["end"])
            conn.execute(
                "INSERT INTO chunks VALUES (?,?,?,?,?,?)",
                (row["id"], row["text"], provenance, row["text_hash"], row["start"], row["end"]),
            )
            conn.execute("INSERT INTO lexical VALUES (?,?)", (row["id"], row["text"]))
            conn.execute(
                "INSERT INTO history_occurrence_chunks VALUES (?,?)",
                (staged["identity"], row["id"]),
            )
        following = json.loads(staged["next_cursor"])
        conn.execute(
            "INSERT INTO history_occurrences VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                staged["identity"],
                staged["cursor_key"],
                following["row_address"],
                alias,
                staged["metadata_json"],
                staged["columns_json"],
                staged["text_hash"],
                "[]",
                _hash(staged["metadata_json"]),
                _hash(staged["columns_json"]),
            ),
        )
        conn.execute("INSERT INTO history_aliases VALUES (?,?)", (alias, staged["identity"]))
        conn.execute(
            "INSERT INTO history_attempts VALUES (?,?,'indexed')",
            (staged["cursor_key"], staged["next_cursor"]),
        )
        conn.execute(
            "DELETE FROM history_staged_chunks WHERE cursor_key=?", (staged["cursor_key"],)
        )
        conn.execute("DELETE FROM history_staged_rows WHERE cursor_key=?", (staged["cursor_key"],))
        indexed, gaps = _counts(conn)
    job["cursor"] = following
    job.pop("inflight", None)
    job.pop("partial_row", None)
    job.pop("retry_cursor", None)
    job.pop("retry_count", None)
    _update_counts(job, indexed, gaps)


def _stage_index(palace, job, store, deadline):
    reader = None
    try:
        staged = _stage_record(store, job)
        if staged is None:
            reader = _projected_row(Path(job["snapshot"]), job["version"], job["cursor"])
            header = reader.header()
            store = _stage_begin(palace, job, store, header)
            staged = _stage_record(store, job)
            _stage_progress(job, store, staged)
            _save_job(palace, job)
        if staged["state"] == "blocked":
            job["state"], job["reason"] = (
                "blocked",
                staged["reason"] or "interrupted_native_projection",
            )
            _stage_progress(job, store, staged)
            _save_job(palace, job)
            _publish(palace, job)
            return _summary(job)
        if staged["inflight_character"] is not None:
            blocked = (
                staged["retry_character"] == staged["inflight_character"]
                and staged["retry_count"] >= 1
            )
            with store._connect(True) as conn:
                conn.execute(
                    "UPDATE history_staged_rows SET state=?,reason=?,retry_character=inflight_character,retry_count=1,inflight_character=NULL WHERE cursor_key=?",
                    (
                        "blocked" if blocked else staged["state"],
                        "interrupted_native_projection" if blocked else None,
                        staged["cursor_key"],
                    ),
                )
            if blocked:
                return _stage_index(palace, job, store, deadline)
            staged = _stage_record(store, job)
        if staged["phase_inflight"] is not None:
            phase = staged["phase_inflight"]
            staged = _stage_phase_failure(store, job, staged, phase, "interrupted_staged_" + phase)
            if staged["state"] == "blocked":
                return _stage_index(palace, job, store, deadline)
        while staged["next_character"] < staged["text_characters"] and time.monotonic() < deadline:
            if _interactive_waiting():
                _stage_progress(job, store, staged)
                _save_job(palace, job)
                _publish(palace, job)
                return _yielded(job)
            if reader is None:
                reader = _projected_row(Path(job["snapshot"]), job["version"], job["cursor"])
                reader.bind_header(staged["header"])
            with store._connect(True) as conn:
                conn.execute(
                    "UPDATE history_staged_rows SET inflight_character=next_character WHERE cursor_key=?",
                    (staged["cursor_key"],),
                )
            page = reader.page(staged["next_character"], PROJECTED_PAGE_CHARACTERS)
            _stage_page(store, staged, page)
            staged = _stage_record(store, job)
            _stage_progress(job, store, staged)
            _save_job(palace, job)
        # Header/pages, complete-source hashing and atomic publication each get
        # their own fresh slice. Tiny leftovers and interactive yields are never
        # counted as failed full-budget finalization attempts.
        if reader is None and staged["next_character"] == staged["text_characters"]:
            phase = "hash" if staged["text_hash"] is None else "publication"
            if _interactive_waiting():
                return _stage_interactive_yield(palace, job, store, staged)
            if deadline - time.monotonic() < MIN_FINAL_PHASE_SECONDS:
                deferrals = staged["final_deferrals"] + 1
                with store._connect(True) as conn:
                    conn.execute(
                        "UPDATE history_staged_rows SET final_deferrals=?,reason=?,state=? WHERE cursor_key=?",
                        (
                            deferrals,
                            "staged_" + phase + "_admission_deadline",
                            "blocked" if deferrals >= 2 else staged["state"],
                            staged["cursor_key"],
                        ),
                    )
                return _stage_checkpoint(palace, job, store, _stage_record(store, job))
            with store._connect(True) as conn:
                conn.execute(
                    "UPDATE history_staged_rows SET phase_inflight=?,final_deferrals=0 WHERE cursor_key=?",
                    (phase, staged["cursor_key"]),
                )
            if phase == "hash":
                try:
                    digest = _stage_hash(store, staged, deadline)
                except _HistoryError as exc:
                    if exc.status != "interactive_waiting":
                        raise
                    return _stage_interactive_yield(palace, job, store, staged)
                if digest is None:
                    staged = _stage_phase_failure(store, job, staged, phase, "staged_hash_deadline")
                else:
                    with store._connect(True) as conn:
                        conn.execute(
                            "UPDATE history_staged_rows SET text_hash=?,state='publication_pending',phase_inflight=NULL,reason=NULL WHERE cursor_key=?",
                            (digest, staged["cursor_key"]),
                        )
                    staged = _stage_record(store, job)
            else:
                try:
                    _stage_publish(store, job, staged, deadline)
                except _HistoryError as exc:
                    if exc.status == "interactive_waiting":
                        return _stage_interactive_yield(palace, job, store, staged)
                    if exc.status != "deadline":
                        raise
                    staged = _stage_phase_failure(
                        store, job, staged, phase, "staged_publication_deadline"
                    )
                except (sqlite3.Error, _Quota) as exc:
                    if not _physical_quota(exc):
                        raise
                    staged = _stage_phase_failure(
                        store, job, staged, phase, "staged_publication_quota"
                    )
                    _stage_checkpoint(palace, job, store, staged)
                    raise
                else:
                    _save_job(palace, job)
                    _publish(palace, job)
                    return _summary(job)
        return _stage_checkpoint(palace, job, store, staged)
    finally:
        if reader is not None:
            reader.close()


def _stage_phase_failure(store, job, staged, phase, reason):
    if phase not in ("hash", "publication"):
        raise _HistoryError("corrupt")
    field = phase + "_failures"
    failures = staged[field] + 1
    with store._connect(True) as conn:
        conn.execute(
            "UPDATE history_staged_rows SET "
            + field
            + "=?,phase_inflight=NULL,reason=?,state=? WHERE cursor_key=?",
            (
                failures,
                reason,
                "blocked" if failures >= 2 else staged["state"],
                staged["cursor_key"],
            ),
        )
    return _stage_record(store, job)


def _stage_interactive_yield(palace, job, store, staged):
    with store._connect(True) as conn:
        conn.execute(
            "UPDATE history_staged_rows SET phase_inflight=NULL WHERE cursor_key=?",
            (staged["cursor_key"],),
        )
    staged = _stage_record(store, job)
    return {**_stage_checkpoint(palace, job, store, staged), "yielded": "interactive_waiting"}


def _stage_checkpoint(palace, job, store, staged):
    if staged["state"] == "blocked":
        job["state"], job["reason"] = "blocked", staged["reason"]
    _stage_progress(job, store, staged)
    _save_job(palace, job)
    _publish(palace, job)
    return _summary(job)


def _index(palace, deadline):
    job = _load_job(palace)
    if not job or job["state"] in ("copying", "changed"):
        return {**_summary(job), "status": "not_prepared"}
    if _interactive_waiting():
        return _yielded(job)
    _validate_snapshot(job)
    if job.get("reason") in ("output_capacity", "row_output_capacity"):
        return _summary(job)
    store = _store(palace, job)
    # Reconcile durable receipts before moving a checkpoint. A killed native
    # decode has no receipt: keep that precise immutable cursor blocked, visible,
    # and unadvanced rather than retrying a poison row forever.
    if _free_bytes(store.directory.parent) < FREE_HEADROOM_BYTES + 16 * (
        MAX_ROW_BYTES + MAX_METADATA_BYTES
    ):
        raise _HistoryError("quota")
    with store._connect(True) as conn:
        _schema(conn)
        staged = conn.execute(
            "SELECT 1 FROM history_staged_rows WHERE cursor_key=?", (_cursor_key(job["cursor"]),)
        ).fetchone()
        inflight = job.get("inflight")
        if inflight:
            key = _cursor_key(inflight)
            receipt = conn.execute(
                "SELECT next_cursor FROM history_attempts WHERE cursor_key=?", (key,)
            ).fetchone()
            if receipt:
                if staged:
                    raise _HistoryError("corrupt")
                job["cursor"] = json.loads(receipt[0])
                job.pop("inflight", None)
                job.pop("partial_row", None)
            elif staged:
                # Page receipts supersede the coarse native-row retry counter.
                # A successfully committed page must survive host/worker death.
                pass
            elif job.get("retry_cursor") != key or job.get("retry_count", 0) < 1:
                # One explicit durable retry allows transient pressure/parent
                # death to recover. A second death at this cursor stays blocked.
                job["retry_cursor"] = key
                job["retry_count"] = 1
                job.pop("inflight", None)
            else:
                conn.execute(
                    "INSERT OR IGNORE INTO history_gaps VALUES (?,?,?)",
                    (key, key, "interrupted_native_decode"),
                )
                job["state"] = "blocked"
                job["reason"] = "interrupted_native_decode"
        _update_counts(job, *_counts(conn))
    _save_job(palace, job)
    if job.get("reason") == "interrupted_native_decode":
        _publish(palace, job)
        return _summary(job)
    if staged:
        return _stage_index(palace, job, store, deadline)
    job["state"] = "indexing"
    _publish(palace, job)
    rows = iter(_scan_rows(Path(job["snapshot"]), job["version"], job["cursor"]))
    while time.monotonic() < deadline:
        if _interactive_waiting():
            _publish(palace, job)
            return _yielded(job)
        job["inflight"] = dict(job["cursor"])
        _save_job(palace, job)
        projected = False
        try:
            row = next(rows)
        except _HistoryError as exc:
            if exc.status != "native_batch_size":
                raise
            projected = True
        except StopIteration:
            job.pop("inflight", None)
            job["total_rows"] = job["indexed_rows"] + job["gaps"]
            job["state"] = "blocked" if job["gaps"] else "complete"
            _save_job(palace, job)
            _publish(palace, job)
            return _summary(job)
        if projected:
            # Leave the exception handler before opening another native reader:
            # its traceback owns the rejected batch and dataset until then.
            close = getattr(rows, "close", None)
            if close is not None:
                close()
            rows = None
            row = None
            return _stage_index(palace, job, store, deadline)
        while True:
            try:
                next_cursor, indexed, gaps = _commit_row(store, job, row, job["cursor"])
                job["cursor"] = next_cursor
                _update_counts(job, indexed, gaps)
                break
            except (sqlite3.Error, _Quota) as exc:
                if not _physical_quota(exc):
                    raise
                store = _rollover(palace, job)
                if time.monotonic() >= deadline:
                    # No row committed; leave the cursor pending for the next
                    # slice rather than retain decoded native data indefinitely.
                    job.pop("inflight", None)
                    _save_job(palace, job)
                    return _summary(job)
        job.pop("inflight", None)
        job.pop("retry_cursor", None)
        job.pop("retry_count", None)
        _save_job(palace, job)
    _publish(palace, job)
    return _summary(job)


def _valid_repair_cursor(cursor):
    return (
        isinstance(cursor, dict)
        and {"fragment", "offset"} <= cursor.keys()
        and not cursor.keys() - {"fragment", "offset", "row_address"}
        and all(type(value) is int and 0 <= value < 2**63 for value in cursor.values())
        and ("row_address" not in cursor or cursor["row_address"] >> 32 == cursor["fragment"])
    )


def _repair(palace, store_id, cursor, deadline):
    """Resolve one pinned row_size receipt atomically, without moving the scan."""
    job = _load_job(palace)
    if (
        not job
        or job["state"] in ("copying", "changed")
        or not any(shard["store_id"] == store_id for shard in job["stores"])
    ):
        raise _HistoryError("repair_refused")
    if _interactive_waiting():
        return _yielded(job)
    _validate_snapshot(job)
    store = _store(palace, job, store_id)
    key = _cursor_key(cursor)
    with store._connect() as conn:
        gap = conn.execute(
            "SELECT substr(identity,1,65) AS identity,substr(reason,1,65) AS reason FROM history_gaps WHERE cursor_key=?",
            (key,),
        ).fetchone()
        attempt = conn.execute(
            "SELECT substr(next_cursor,1,513) AS next_cursor,substr(outcome,1,32) AS outcome FROM history_attempts WHERE cursor_key=?",
            (key,),
        ).fetchone()
        has_audit = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='history_gap_resolutions'"
        ).fetchone()
        audit = (
            conn.execute(
                "SELECT * FROM history_gap_resolutions WHERE cursor_key=?", (key,)
            ).fetchone()
            if has_audit
            else None
        )
        if attempt is None:
            raise _HistoryError("repair_refused")
        try:
            next_cursor = json.loads(attempt["next_cursor"])
        except (ValueError, TypeError, RecursionError) as exc:
            raise _HistoryError("repair_refused") from exc
        if not _valid_repair_cursor(next_cursor):
            raise _HistoryError("repair_refused")
        occurrence = _hash(
            _json(
                [
                    job["archive_id"],
                    job["snapshot_id"],
                    job["version"],
                    next_cursor["fragment"],
                    next_cursor.get("row_address"),
                ]
            )
        )
        if audit is not None:
            registered = conn.execute(
                "SELECT identity,text_hash,metadata_hash,columns_hash FROM history_occurrences WHERE identity=? AND cursor_key=?",
                (occurrence, key),
            ).fetchone()
            if (
                gap is not None
                or attempt["outcome"] != "indexed"
                or audit["identity"] != occurrence
                or audit["reason"] != "row_size"
                or audit["snapshot_id"] != job["snapshot_id"]
                or audit["next_cursor"] != attempt["next_cursor"]
                or registered is None
                or any(
                    audit[field] != registered[field]
                    for field in ("text_hash", "metadata_hash", "columns_hash")
                )
            ):
                raise _HistoryError("repair_refused")
            indexed, gaps = _counts(conn)
            repair_status = "already_resolved"
        else:
            if (
                gap is None
                or gap["reason"] != "row_size"
                or gap["identity"] != occurrence
                or attempt["outcome"] != "gap"
            ):
                raise _HistoryError("repair_refused")
            repair_status = "resolved"
    if repair_status == "resolved":
        rows = iter(_scan_rows(Path(job["snapshot"]), job["version"], cursor))
        try:
            try:
                row = next(rows)
            except StopIteration as exc:
                raise _HistoryError("repair_refused") from exc
            actual = {
                "fragment": row["fragment"],
                "offset": row["offset"],
                "row_address": row["row_address"],
            }
            if actual != next_cursor:
                raise _HistoryError("repair_refused")
            if time.monotonic() >= deadline:
                raise _HistoryError("deadline")
            _, indexed, gaps = _commit_row(store, job, row, cursor, repair=True)
        finally:
            close = getattr(rows, "close", None)
            if close is not None:
                close()
    # A repair can target an older shard. Reconcile it even on a retry following
    # death after the SQLite commit but before the job/catalog publication.
    for shard in job["stores"]:
        if shard["store_id"] == store_id:
            shard["indexed_rows"], shard["gaps"] = indexed, gaps
    job["indexed_rows"] = sum(shard["indexed_rows"] for shard in job["stores"])
    job["gaps"] = sum(shard["gaps"] for shard in job["stores"])
    if not job["gaps"] and not job.get("reason") and job.get("total_rows") == job["indexed_rows"]:
        job["state"] = "complete"
    _save_job(palace, job)
    _publish(palace, job)
    return {
        **_summary(job),
        "repair": {"store_id": store_id, "cursor_key": key, "status": repair_status},
    }


def history_operation(palace: Path, operation: str, arguments: dict) -> dict:
    """Perform one bounded operator slice. Status contains no source content."""
    if operation not in ("prepare", "index", "status", "repair") or not isinstance(arguments, dict):
        raise ValueError("history operation")
    if (
        (
            operation == "prepare"
            and (
                set(arguments) != {"source"}
                or not isinstance(arguments["source"], str)
                or not arguments["source"]
            )
        )
        or (
            operation == "repair"
            and (
                set(arguments) != {"store_id", "cursor"}
                or not isinstance(arguments["store_id"], str)
                or len(arguments["store_id"]) != 64
                or any(character not in "0123456789abcdef" for character in arguments["store_id"])
                or not _valid_repair_cursor(arguments["cursor"])
            )
        )
        or (operation not in ("prepare", "repair") and arguments)
    ):
        raise ValueError("history arguments")
    deadline = time.monotonic() + SLICE_SECONDS
    try:
        if operation == "status":
            return _summary(_load_job(palace))
        if operation == "prepare":
            if _interactive_waiting():
                return _yielded(_load_job(palace))
            return _prepare(palace, arguments["source"], deadline)
        if operation == "repair":
            return _repair(palace, arguments["store_id"], arguments["cursor"], deadline)
        return _index(palace, deadline)
    except _HistoryError as exc:
        result = {"status": exc.status, "coverage_complete": False}
        try:
            job = _load_job(palace)
            if job:
                result = {**_summary(job), "status": exc.status, "coverage_complete": False}
        except (OSError, ValueError, _HistoryError):
            pass
        return result
    except (OSError, sqlite3.Error, _Unavailable, _Quota, _Corrupt) as exc:
        return {**MemoryStore._error(exc), "coverage_complete": False}
    except (ValueError, TypeError, KeyError, ImportError, RecursionError):
        return {"status": "corrupt", "coverage_complete": False}
