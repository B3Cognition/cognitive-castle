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
from contextlib import ExitStack

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
# Repeated native projections can retain decoder buffers for a worker's
# lifetime. Bound their count as well as elapsed time; durable pages resume in
# another disposable worker without raising any resource ceiling.
MAX_PROJECTED_PAGES_PER_SLICE = 4
PROJECTED_SOURCE_BYTES_PER_SLICE = 32 * 1024**2
MIN_FINAL_PHASE_SECONDS = 1
INVENTORY_AUDIT_BATCH = 256
INVENTORY_AUDIT_CHECKPOINT = 1024
INVENTORY_AUDIT_WAIT_INTERVAL = 128


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
    rejected = job.get("capacity_rejected", [])
    if (
        not isinstance(rejected, list)
        or len(rejected) > MAX_HISTORY_STORES
        or any(not isinstance(value, str) or value not in seen for value in rejected)
        or len(set(rejected)) != len(rejected)
        or (
            "capacity_cursor_key" in job
            and (
                not isinstance(job["capacity_cursor_key"], str)
                or len(job["capacity_cursor_key"]) != 64
                or any(c not in "0123456789abcdef" for c in job["capacity_cursor_key"])
            )
        )
    ):
        raise _HistoryError("corrupt")
    if identity not in seen:
        raise _HistoryError("corrupt")
    if "expected_rows" in job and (
        type(job["expected_rows"]) is not int or not 0 <= job["expected_rows"] < 2**63
    ):
        raise _HistoryError("corrupt")
    proof = job.get("inventory_proof")
    if proof is not None:
        positions = proof.get("positions") if isinstance(proof, dict) else None
        previous = proof.get("previous") if isinstance(proof, dict) else None
        consumed_positions = (
            [value for value in positions if value is not None]
            if isinstance(positions, list)
            else []
        )
        if (
            not isinstance(proof, dict)
            or set(proof) != {"binding", "phase", "positions", "previous", "count"}
            or "expected_rows" not in job
            or not isinstance(proof["binding"], str)
            or len(proof["binding"]) != 64
            or any(character not in "0123456789abcdef" for character in proof["binding"])
            or not isinstance(proof["phase"], str)
            or proof["phase"] not in {"attempts", "identities"}
            or not isinstance(proof["positions"], list)
            or len(proof["positions"]) != len(stores)
            or any(
                value is not None
                and (
                    not isinstance(value, str)
                    or len(value) != 64
                    or any(character not in "0123456789abcdef" for character in value)
                )
                for value in proof["positions"]
            )
            or (
                proof["previous"] is not None
                and (
                    not isinstance(proof["previous"], str)
                    or len(proof["previous"]) != 64
                    or any(character not in "0123456789abcdef" for character in proof["previous"])
                )
            )
            or type(proof["count"]) is not int
            or not 0 <= proof["count"] <= job.get("expected_rows", -1)
            or (proof["count"] == 0 and (previous is not None or consumed_positions))
            or (proof["count"] > 0 and (previous is None or not consumed_positions))
            or (consumed_positions and previous != max(consumed_positions))
            or (proof["count"] < len(consumed_positions))
        ):
            raise _HistoryError("corrupt")
    for cursor in (job.get("cursor"), job.get("inflight", job.get("cursor"))):
        if not isinstance(cursor, dict) or any(
            type(cursor.get(key)) is not int or not 0 <= cursor[key] < 2**63
            for key in ("fragment", "offset")
        ):
            raise _HistoryError("corrupt")
    if "capacity_cursor_key" in job and (
        not rejected or job["capacity_cursor_key"] != _cursor_key(job["cursor"])
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
        "coverage_complete": (
            job["state"] == "complete"
            and not job.get("gaps")
            and type(job.get("expected_rows")) is int
            and job.get("total_rows") == job.get("expected_rows")
        ),
        **({"expected_rows": job["expected_rows"]} if "expected_rows" in job else {}),
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


def _source_row_count(snapshot, version):
    """Count rows independently from the pinned native snapshot/version."""
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
    count = dataset.count_rows()
    if type(count) is not int or not 0 <= count < 2**63:
        raise _HistoryError("unsupported")
    return count


def _store(palace, job, store_id=None):
    from cognitive_castle.unified_memory import history_store_path

    return MemoryStore(history_store_path(palace, store_id or job["store_id"]))


def _store_used(store):
    if not store.directory.exists():
        return 0
    with store._connect() as conn:
        staged = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='history_staged_rows'"
        ).fetchone()
        if staged and conn.execute("SELECT 1 FROM history_staged_rows LIMIT 1").fetchone():
            return None
        return (
            conn.execute("PRAGMA page_count").fetchone()[0]
            - conn.execute("PRAGMA freelist_count").fetchone()[0]
        ) * conn.execute("PRAGMA page_size").fetchone()[0]


def _capacity_candidates(palace, job, estimate, *, rejected=(), deadline=None):
    """Return fitting existing shards, preferring the tightest fit."""
    from cognitive_castle.unified_memory import history_store_path

    rejected = set(rejected)
    cap = MAX_STORE_BYTES // 3
    candidates = []
    for shard in job["stores"]:
        if _interactive_waiting():
            raise _HistoryError("interactive_waiting")
        if deadline is not None and time.monotonic() >= deadline:
            raise _HistoryError("deadline")
        identity = shard["store_id"]
        path = history_store_path(palace, identity)
        if identity == job["store_id"] or identity in rejected or not path.is_dir():
            continue
        used = _store_used(MemoryStore(path))
        if used is None:
            continue
        if used + estimate <= cap:
            candidates.append((cap - used - estimate, identity))
    return [identity for _, identity in sorted(candidates)]


def _switch_capacity_target(palace, job, store_id):
    if store_id == job["store_id"]:
        return _store(palace, job)
    job["store_id"] = store_id
    if job.get("reason") == "output_capacity":
        job.pop("reason", None)
        job["state"] = "indexing"
    _save_job(palace, job)
    _publish(palace, job)
    return _store(palace, job)


def _row_output_estimate(row):
    values = row["values"]
    text = values.get("text")
    metadata = values.get("metadata_json")
    try:
        columns = _json(
            {k: v for k, v in values.items() if k not in ("text", "metadata_json", "vector")}
        )
        columns_bytes = len(columns.encode())
        text_bytes = len(text.encode()) if isinstance(text, str) else 0
        metadata_bytes = len(metadata.encode()) if isinstance(metadata, str) else 0
    except (UnicodeError, ValueError, TypeError, RecursionError):
        # _commit_row records malformed metadata as a bounded gap receipt.
        return 65536
    return (
        4 * text_bytes
        + 2 * (metadata_bytes + columns_bytes)
        + (text_bytes // 8192 + 1) * 2048
        + 65536
    )


def _schema(conn):
    new_occurrences = (
        conn.execute("SELECT 1 FROM sqlite_master WHERE name='history_occurrences'").fetchone()
        is None
    )
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
    if new_occurrences:
        # The registry is empty here. Never backfill populated legacy stores
        # during an ordinary conversion write or a context read.
        from .unified_memory import workspace_index_specs

        for spec in workspace_index_specs():
            if spec["table"] == "history_occurrences":
                conn.execute(spec["sql"])


def _cursor_key(cursor):
    return _hash(_json(cursor))


def _counts(conn):
    return (
        conn.execute("SELECT count(*) FROM history_occurrences").fetchone()[0],
        conn.execute("SELECT count(*) FROM history_gaps").fetchone()[0],
    )


def _inventory_fingerprint(store):
    values = []
    for name in (
        "memory.sqlite3",
        "memory.sqlite3-journal",
        "memory.sqlite3-wal",
        "memory.sqlite3-shm",
    ):
        path = store.directory / name
        try:
            info = _private(path)
        except FileNotFoundError:
            values.append([name, None])
        else:
            values.append(
                [name, info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]
            )
    return _hash(_json(values))


def _inventory_binding(job, fingerprints):
    return _hash(
        _json(
            {
                "archive_id": job["archive_id"],
                "snapshot_id": job["snapshot_id"],
                "version": job["version"],
                "expected_rows": job["expected_rows"],
                "cursor": job["cursor"],
                "stores": [shard["store_id"] for shard in job["stores"]],
                "fingerprints": fingerprints,
            }
        )
    )


def _initial_inventory_proof(binding, stores, phase="attempts"):
    return {
        "binding": binding,
        "phase": phase,
        "positions": [None] * len(stores),
        "previous": None,
        "count": 0,
    }


def _inventory_table_exists(conn, table):
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _inventory_batch(conn, phase, position):
    if phase == "attempts":
        if not _inventory_table_exists(conn, "history_attempts"):
            return []
        return conn.execute(
            "SELECT a.cursor_key,length(a.cursor_key) AS cursor_key_length,"
            "substr(a.next_cursor,1,513) AS next_cursor,length(a.next_cursor) AS next_cursor_length,"
            "substr(a.outcome,1,17) AS outcome,length(a.outcome) AS outcome_length,"
            "substr(o.identity,1,65) AS occurrence_identity,length(o.identity) AS occurrence_identity_length,"
            "o.row_address,substr(g.identity,1,65) AS gap_identity,length(g.identity) AS gap_identity_length "
            "FROM history_attempts a "
            "LEFT JOIN history_occurrences o ON o.cursor_key=a.cursor_key "
            "LEFT JOIN history_gaps g ON g.cursor_key=a.cursor_key "
            "WHERE length(a.cursor_key)=64 AND a.cursor_key>COALESCE(?, '') "
            "ORDER BY a.cursor_key LIMIT ?",
            (position, INVENTORY_AUDIT_BATCH),
        ).fetchall()
    if not _inventory_table_exists(conn, "history_occurrences"):
        return []
    return conn.execute(
        "SELECT substr(identity,1,65) AS identity FROM history_occurrences "
        "WHERE length(identity)=64 AND identity>COALESCE(?, '') "
        "ORDER BY identity LIMIT ?",
        (position, INVENTORY_AUDIT_BATCH),
    ).fetchall()


def _validate_inventory_receipt(job, row):
    key = row["cursor_key"]
    try:
        following = json.loads(row["next_cursor"])
    except (ValueError, TypeError, RecursionError) as exc:
        raise _HistoryError("source_receipt_mismatch") from exc
    if (
        not _valid_repair_cursor(following)
        or "row_address" not in following
        or following["offset"] <= 0
    ):
        raise _HistoryError("source_receipt_mismatch")
    identity = _hash(
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
    if row["outcome"] == "indexed":
        if (
            row["occurrence_identity"] != identity
            or row["row_address"] != following["row_address"]
            or row["gap_identity"] is not None
        ):
            raise _HistoryError("source_receipt_mismatch")
    elif row["outcome"] == "gap":
        if row["gap_identity"] != identity or row["occurrence_identity"] is not None:
            raise _HistoryError("source_receipt_mismatch")
    else:
        raise _HistoryError("source_receipt_mismatch")
    if (
        not isinstance(key, str)
        or len(key) != 64
        or any(character not in "0123456789abcdef" for character in key)
    ):
        raise _HistoryError("source_receipt_mismatch")


def _run_inventory_proof(palace, job, deadline, fingerprints, indexed, gaps):
    store_ids = [shard["store_id"] for shard in job["stores"]]
    binding = _inventory_binding(job, fingerprints)
    proof = job.get("inventory_proof")
    if not isinstance(proof, dict) or proof.get("binding") != binding:
        proof = _initial_inventory_proof(binding, store_ids)
        job["inventory_proof"] = proof
        _save_job(palace, job)
    stores = [_store(palace, job, identity) for identity in store_ids]
    with ExitStack() as stack:
        connections = []
        for store in stores:
            if time.monotonic() >= deadline or _interactive_waiting():
                job["inventory_proof"] = proof
                _save_job(palace, job)
                return False
            connections.append(stack.enter_context(store._connect()))
        for conn in connections:
            conn.execute("PRAGMA cache_size=-1024")
            conn.set_progress_handler(
                lambda: int(time.monotonic() >= deadline or _interactive_waiting()), 1000
            )
        buffers = [[] for _ in connections]
        offsets = [0] * len(connections)
        exhausted = [False] * len(connections)
        while True:
            if time.monotonic() >= deadline or (
                proof["count"] % INVENTORY_AUDIT_WAIT_INTERVAL == 0 and _interactive_waiting()
            ):
                job["inventory_proof"] = proof
                _save_job(palace, job)
                return False
            for index, conn in enumerate(connections):
                if not exhausted[index] and offsets[index] >= len(buffers[index]):
                    buffers[index] = _inventory_batch(
                        conn, proof["phase"], proof["positions"][index]
                    )
                    offsets[index] = 0
                    exhausted[index] = not buffers[index]
            heads = [
                (
                    buffers[index][offsets[index]][
                        "cursor_key" if proof["phase"] == "attempts" else "identity"
                    ],
                    index,
                )
                for index in range(len(connections))
                if offsets[index] < len(buffers[index])
            ]
            if not heads:
                if proof["phase"] == "attempts":
                    if proof["count"] != job["expected_rows"]:
                        raise _HistoryError("source_receipt_mismatch")
                    if gaps:
                        if [_inventory_fingerprint(store) for store in stores] != fingerprints:
                            job["inventory_proof"] = _initial_inventory_proof(binding, store_ids)
                            _save_job(palace, job)
                            return False
                        job.pop("inventory_proof", None)
                        return True
                    proof.update(
                        phase="identities",
                        positions=[None] * len(connections),
                        previous=None,
                        count=0,
                    )
                    job["inventory_proof"] = proof
                    _save_job(palace, job)
                    buffers = [[] for _ in connections]
                    offsets = [0] * len(connections)
                    exhausted = [False] * len(connections)
                    continue
                if proof["count"] != indexed:
                    raise _HistoryError("source_receipt_mismatch")
                if [_inventory_fingerprint(store) for store in stores] != fingerprints:
                    job["inventory_proof"] = _initial_inventory_proof(binding, store_ids)
                    _save_job(palace, job)
                    return False
                job.pop("inventory_proof", None)
                return True
            key, index = min(heads)
            if proof["previous"] is not None and key <= proof["previous"]:
                raise _HistoryError("source_receipt_mismatch")
            row = buffers[index][offsets[index]]
            if proof["phase"] == "attempts":
                _validate_inventory_receipt(job, row)
            proof["positions"][index] = key
            proof["previous"] = key
            proof["count"] += 1
            offsets[index] += 1
            if proof["count"] % INVENTORY_AUDIT_CHECKPOINT == 0:
                job["inventory_proof"] = proof
                _save_job(palace, job)


def _reconcile_inventory(palace, job, deadline):
    """Reconcile every shard's actual receipts before publishing completion."""
    if "expected_rows" not in job:
        raise _HistoryError("source_count_missing")
    actual_indexed = actual_gaps = 0
    store_objects = [_store(palace, job, shard["store_id"]) for shard in job["stores"]]
    fingerprints = [_inventory_fingerprint(store) for store in store_objects]
    for shard in job["stores"]:
        if time.monotonic() >= deadline:
            raise _HistoryError("deadline")
        if _interactive_waiting():
            raise _HistoryError("interactive_waiting")
        store = _store(palace, job, shard["store_id"])
        if not store.directory.exists():
            raise _HistoryError("source_receipt_mismatch")
        try:
            with store._connect() as conn:
                conn.set_progress_handler(
                    lambda: int(time.monotonic() >= deadline or _interactive_waiting()), 1000
                )
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='history_attempts'"
                ).fetchone()

                def table_exists(name):
                    return conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
                    ).fetchone()

                has_occurrences = table_exists("history_occurrences")
                has_gaps = table_exists("history_gaps")
                indexed = (
                    conn.execute("SELECT count(*) FROM history_occurrences").fetchone()[0]
                    if has_occurrences
                    else 0
                )
                gaps = (
                    conn.execute("SELECT count(*) FROM history_gaps").fetchone()[0]
                    if has_gaps
                    else 0
                )
                if exists:
                    attempts, indexed_attempts, gap_attempts = conn.execute(
                        "SELECT count(*),sum(outcome='indexed'),sum(outcome='gap') FROM history_attempts"
                    ).fetchone()
                    attempts = attempts or 0
                    indexed_attempts = indexed_attempts or 0
                    gap_attempts = gap_attempts or 0
                    has_stages = conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='history_staged_rows'"
                    ).fetchone()
                    has_staged_chunks = table_exists("history_staged_chunks")
                    stages = (
                        conn.execute("SELECT count(*) FROM history_staged_rows").fetchone()[0]
                        if has_stages
                        else 0
                    )
                    staged_chunks = (
                        conn.execute("SELECT count(*) FROM history_staged_chunks").fetchone()[0]
                        if has_staged_chunks
                        else 0
                    )
                else:
                    attempts = indexed_attempts = gap_attempts = 0
                    has_stages = table_exists("history_staged_rows")
                    has_staged_chunks = table_exists("history_staged_chunks")
                    stages = (
                        conn.execute("SELECT count(*) FROM history_staged_rows").fetchone()[0]
                        if has_stages
                        else 0
                    )
                    staged_chunks = (
                        conn.execute("SELECT count(*) FROM history_staged_chunks").fetchone()[0]
                        if has_staged_chunks
                        else 0
                    )
        except sqlite3.OperationalError as exc:
            if "interrupted" in str(exc).lower():
                raise _HistoryError(
                    "interactive_waiting" if _interactive_waiting() else "deadline"
                ) from exc
            raise
        if stages or staged_chunks:
            raise _HistoryError("source_stage_pending")
        if (indexed, gaps) != (shard["indexed_rows"], shard["gaps"]):
            raise _HistoryError("source_count_mismatch")
        if (attempts, indexed_attempts, gap_attempts) != (indexed + gaps, indexed, gaps):
            raise _HistoryError("source_receipt_mismatch")
        actual_indexed += indexed
        actual_gaps += gaps
    job["indexed_rows"], job["gaps"] = actual_indexed, actual_gaps
    actual_total = actual_indexed + actual_gaps
    if (
        actual_total != job["expected_rows"]
        or actual_total != job.get("total_rows")
        or actual_indexed != sum(shard["indexed_rows"] for shard in job["stores"])
        or actual_gaps != sum(shard["gaps"] for shard in job["stores"])
    ):
        raise _HistoryError("source_count_mismatch")
    if [_inventory_fingerprint(store) for store in store_objects] != fingerprints:
        raise _HistoryError("source_inventory_pending")
    try:
        complete = _run_inventory_proof(
            palace, job, deadline, fingerprints, actual_indexed, actual_gaps
        )
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise _HistoryError("source_inventory_pending") from exc
        raise
    if not complete:
        raise _HistoryError("source_inventory_pending")


def _finish_inventory(palace, job, deadline):
    try:
        _reconcile_inventory(palace, job, deadline)
    except _HistoryError as exc:
        if exc.status not in {
            "source_count_mismatch",
            "source_count_missing",
            "source_receipt_mismatch",
            "source_stage_pending",
        }:
            if exc.status not in {"source_inventory_pending", "deadline", "interactive_waiting"}:
                raise
            job["state"] = "indexing"
            job["reason"] = "source_inventory_pending"
            return False
        job["state"] = "blocked"
        job["reason"] = exc.status
    else:
        job["state"] = "blocked" if job["gaps"] else "complete"
        job.pop("reason", None)
    return True


def _acquire_source_count(palace, job, deadline):
    if "expected_rows" in job:
        return False
    if time.monotonic() >= deadline:
        raise _HistoryError("deadline")
    job["expected_rows"] = _source_row_count(Path(job["snapshot"]), job["version"])
    if job["state"] in {"prepared", "complete"}:
        job["state"] = "indexing"
        job.pop("reason", None)
    _save_job(palace, job)
    if job["state"] == "indexing":
        _publish(palace, job)
    return True


def _resume_inventory_proof(palace, job, deadline):
    if job.get("reason") != "source_inventory_pending" or job.get("total_rows") is None:
        return None
    job["state"] = "indexing"
    finished = _finish_inventory(palace, job, deadline)
    _save_job(palace, job)
    _publish(palace, job)
    result = _summary(job)
    return result if finished else {**result, "yielded": "proof_pending"}


def _index_setup(palace, deadline):
    job = _load_job(palace)
    if not job or job["state"] in ("copying", "changed"):
        return None, {**_summary(job), "status": "not_prepared"}
    if _interactive_waiting():
        return None, _yielded(job)
    _validate_snapshot(job)
    if _acquire_source_count(palace, job, deadline):
        return None, {**_summary(job), "yielded": "source_counted"}
    resumed_proof = _resume_inventory_proof(palace, job, deadline)
    if resumed_proof is not None:
        return None, resumed_proof
    if job.get("reason") == "row_output_capacity":
        return None, _summary(job)
    return job, None


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


def _rollover(palace, job, *, estimate=0, deadline=None):
    active = _store(palace, job)
    with active._connect() as conn:
        has_stage = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='history_staged_rows'"
        ).fetchone()
        if has_stage and conn.execute("SELECT 1 FROM history_staged_rows LIMIT 1").fetchone():
            raise _HistoryError("quota")
    cursor_key = _cursor_key(job["cursor"])
    if job.get("capacity_cursor_key") != cursor_key:
        job["capacity_cursor_key"] = cursor_key
        job["capacity_rejected"] = []
    rejected = set(job.get("capacity_rejected", []))
    rejected.add(job["store_id"])
    job["capacity_rejected"] = sorted(rejected)
    job["capacity_cursor_key"] = cursor_key
    # The row has already decoded successfully. Do not let a crash during this
    # capacity retry turn that known row into an interrupted-native gap.
    job.pop("inflight", None)
    _save_job(palace, job)
    candidates = _capacity_candidates(palace, job, estimate, rejected=rejected, deadline=deadline)
    if candidates:
        return _switch_capacity_target(palace, job, candidates[0])
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


def _stage_begin(palace, job, store, header, deadline):
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
    used = _store_used(store)
    if used is None:
        raise _HistoryError("quota")
    if used + estimate > MAX_STORE_BYTES // 3:
        store = _rollover(palace, job, estimate=estimate, deadline=deadline)
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
    job.pop("capacity_cursor_key", None)
    job.pop("capacity_rejected", None)
    job.pop("partial_row", None)
    job.pop("retry_cursor", None)
    job.pop("retry_count", None)
    _update_counts(job, indexed, gaps)
    if job.get("reason") == "output_capacity":
        job.pop("reason", None)
        job["state"] = "indexing"


def _stage_recover_interrupted_page(store, job, staged):
    blocked = (
        staged["retry_character"] == staged["inflight_character"] and staged["retry_count"] >= 1
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
    return _stage_record(store, job)


def _stage_index(palace, job, store, deadline):
    reader = None
    pages = 0
    try:
        staged = _stage_record(store, job)
        if staged is None:
            reader = _projected_row(Path(job["snapshot"]), job["version"], job["cursor"])
            header = reader.header()
            # A complete projected header establishes that the row was read.
            # Clear the coarse native marker before stage-creation SQL can fail.
            job.pop("inflight", None)
            _save_job(palace, job)
            store = _stage_begin(palace, job, store, header, deadline)
            staged = _stage_record(store, job)
            _stage_progress(job, store, staged)
            _save_job(palace, job)
            if staged["text_bytes"] > PROJECTED_SOURCE_BYTES_PER_SLICE:
                # Release raw decoding and header allocations before opening a
                # page worker for a large source. No original text is discarded.
                result = _stage_checkpoint(palace, job, store, staged)
                result["yielded"] = "projected_header_limit"
                return result
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
            staged = _stage_recover_interrupted_page(store, job, staged)
        if staged["state"] != "blocked" and staged["phase_inflight"] is not None:
            phase = staged["phase_inflight"]
            staged = _stage_phase_failure(store, job, staged, phase, "interrupted_staged_" + phase)
        if staged["state"] == "blocked":
            return _stage_index(palace, job, store, deadline)
        page_limit = min(
            MAX_PROJECTED_PAGES_PER_SLICE,
            max(1, PROJECTED_SOURCE_BYTES_PER_SLICE // max(1, staged["text_bytes"])),
        )
        while (
            staged["next_character"] < staged["text_characters"]
            and time.monotonic() < deadline
            and pages < page_limit
        ):
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
            pages += 1
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
        result = _stage_checkpoint(palace, job, store, staged)
        if pages == page_limit and staged["next_character"] < staged["text_characters"]:
            result["yielded"] = "projected_page_limit"
        return result
    finally:
        if reader is not None:
            reader.close()


def _reconcile_current_receipt(conn, job, staged, inflight):
    key = _cursor_key(job["cursor"])
    receipt = conn.execute(
        "SELECT next_cursor FROM history_attempts WHERE cursor_key=?", (key,)
    ).fetchone()
    if not receipt:
        return staged, inflight
    if staged:
        raise _HistoryError("corrupt")
    try:
        following = json.loads(receipt[0])
    except (ValueError, TypeError, RecursionError) as exc:
        raise _HistoryError("corrupt") from exc
    if not _valid_repair_cursor(following) or "row_address" not in following:
        raise _HistoryError("corrupt")
    if inflight is not None and inflight != job["cursor"]:
        raise _HistoryError("corrupt")
    job["cursor"] = following
    job.pop("inflight", None)
    job.pop("partial_row", None)
    job.pop("capacity_cursor_key", None)
    job.pop("capacity_rejected", None)
    _update_counts(job, *_counts(conn))
    return None, None


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
    job, result = _index_setup(palace, deadline)
    if result is not None:
        return result
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
        staged, inflight = _reconcile_current_receipt(conn, job, staged, inflight)
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
                job.pop("capacity_cursor_key", None)
                job.pop("capacity_rejected", None)
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
            job["state"] = "indexing"
            job["reason"] = "source_inventory_pending"
            _save_job(palace, job)
            _publish(palace, job)
            finished = _finish_inventory(palace, job, deadline)
            _save_job(palace, job)
            _publish(palace, job)
            result = _summary(job)
            return result if finished else {**result, "yielded": "proof_pending"}
        if projected:
            # Leave the exception handler before opening another native reader:
            # its traceback owns the rejected batch and dataset until then.
            close = getattr(rows, "close", None)
            if close is not None:
                close()
            rows = None
            row = None
            return _stage_index(palace, job, store, deadline)
        # The native iterator returned a complete row. A subsequent SQLite
        # refusal or worker death is a storage retry, not a native decode gap.
        job.pop("inflight", None)
        _save_job(palace, job)
        while True:
            try:
                next_cursor, indexed, gaps = _commit_row(store, job, row, job["cursor"])
                job["cursor"] = next_cursor
                _update_counts(job, indexed, gaps)
                job.pop("capacity_cursor_key", None)
                job.pop("capacity_rejected", None)
                if job.get("reason") == "output_capacity":
                    job.pop("reason", None)
                    job["state"] = "indexing"
                break
            except (sqlite3.Error, _Quota) as exc:
                if not _physical_quota(exc):
                    raise
                store = _rollover(
                    palace, job, estimate=_row_output_estimate(row), deadline=deadline
                )
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
    if job.get("reason") == "source_count_mismatch":
        job.pop("reason", None)
    finished = True
    if not job["gaps"] and not job.get("reason") and job.get("total_rows") == job["indexed_rows"]:
        job["state"] = "indexing"
        job["reason"] = "source_inventory_pending"
        _save_job(palace, job)
        _publish(palace, job)
        finished = _finish_inventory(palace, job, deadline)
    _save_job(palace, job)
    _publish(palace, job)
    return {
        **_summary(job),
        **({"yielded": "proof_pending"} if not finished else {}),
        "repair": {"store_id": store_id, "cursor_key": key, "status": repair_status},
    }


def history_operation(palace: Path, operation: str, arguments: dict) -> dict:
    """Perform one bounded operator slice. Status contains no source content."""
    if operation not in ("prepare", "index", "index-scopes", "status", "repair") or not isinstance(
        arguments, dict
    ):
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
        if operation == "index-scopes":
            from .memory_scope_indexes import index_workspace_scope

            return index_workspace_scope(
                palace,
                deadline=deadline,
                interactive_waiting=_interactive_waiting,
            )
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
