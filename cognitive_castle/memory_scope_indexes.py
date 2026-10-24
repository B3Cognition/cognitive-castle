"""Bounded, operator-only installation of unified workspace scope indexes.

Each call commits at most one exact SQLite partial index. Index presence is the
durable checkpoint, so retries resume without a separate migration cursor.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sqlite3
import stat
import time

from .fast_memory import DB_NAME, MAX_STORE_BYTES, MemoryStore, _Unavailable
from .history_storage import HistoryBudgetRefusal, admit_history_write
from .unified_memory import (
    _catalog,
    _index_sql as _normalize_index_sql,
    history_store_path,
    workspace_index_specs,
)

FREE_HEADROOM_BYTES = 2 * 1024**3
_SQL_PROGRESS_STEPS = 1000


class _QuotaExceeded(Exception):
    def __init__(self, reason):
        self.reason = reason


class _UnsupportedStore(Exception):
    def __init__(self, reason):
        self.reason = reason


class _OperationDeadline(Exception):
    pass


class _SpoolScanLimit(Exception):
    pass


def _pending(status="pending", reason=None, *, store_id=None, index=None):
    result = {"status": status, "state": "pending"}
    if reason is not None:
        result["reason"] = reason
    if store_id is not None:
        result["store_id"] = store_id
    if index is not None:
        result["index"] = index
    return result


def _free_bytes(path):
    return shutil.disk_usage(path).free


def _store_paths(palace):
    palace = Path(palace).absolute()
    live = palace / ".memory"
    if live.is_symlink():
        raise OSError("unsafe store path")
    database = live / DB_NAME
    if database.is_symlink():
        raise OSError("unsafe database path")
    if live.is_dir() and database.exists():
        yield "live", live, False

    catalog, _ = _catalog(palace)
    for entry in catalog["stores"]:
        store_id = entry["store_id"]
        directory = history_store_path(palace, store_id)
        yield store_id, directory, True


def _capture_spool_bytes(path, store, deadline):
    from .memory_coordinator import MAX_METADATA, MAX_SPOOL_SCAN

    if not path.is_dir() or path.is_symlink():
        raise OSError("unsafe capture spool")
    store._private(path, True)
    started = time.monotonic()
    count = 0
    total_bytes = 0
    with os.scandir(path) as entries:
        for entry in entries:
            if count >= MAX_SPOOL_SCAN or time.monotonic() - started > 0.1:
                raise _SpoolScanLimit
            if time.monotonic() >= deadline:
                raise _OperationDeadline
            count += 1
            if entry.is_symlink():
                raise OSError("unsafe capture spool entry")
            info = entry.stat(follow_symlinks=False)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077
                or info.st_nlink != 1
            ):
                raise OSError("unsafe capture spool file")
            name = entry.name
            if name.endswith((".json", ".claimed")):
                stem = name.rsplit(".", 1)[0]
                if len(stem) != 64 or any(char not in "0123456789abcdef" for char in stem):
                    raise OSError("unsafe capture spool filename")
            elif not (name.startswith(".capture-") and len(name) <= 128):
                raise OSError("unexpected capture spool entry")
            if info.st_size > MAX_METADATA:
                raise _QuotaExceeded("capture_spool_file_limit")
            total_bytes += info.st_size
    return total_bytes


def _validate_store(directory, deadline=None, *, budget=None):
    directory = Path(directory)
    if deadline is None:
        deadline = time.monotonic() + 6
    if not directory.is_dir() or directory.is_symlink():
        raise OSError("registered store unavailable")
    for parent in [directory, *directory.parents]:
        if parent.is_symlink():
            raise OSError("symlink store ancestor")
    store = MemoryStore(directory)
    store._private(directory, True)
    database = directory / DB_NAME
    store._private(database)
    total_bytes = 0
    children = 0
    for child in directory.iterdir():
        children += 1
        if children > 64:
            raise _QuotaExceeded("store_file_limit")
        if child.is_symlink():
            raise OSError("unsafe store sidecar")
        info = child.lstat()
        if child.name == "capture-spool":
            total_bytes += _capture_spool_bytes(child, store, deadline)
            continue
        if not stat.S_ISREG(info.st_mode):
            raise OSError("unsafe store file")
        store._private(child)
        total_bytes += info.st_size
        if time.monotonic() >= deadline:
            raise _OperationDeadline
    if total_bytes >= (MAX_STORE_BYTES if budget is None else budget):
        raise _QuotaExceeded("store_byte_limit")
    return database, total_bytes


def _connect(database, deadline, interactive_waiting, interrupted):
    connection = sqlite3.connect(database.as_uri() + "?mode=rw", uri=True, timeout=0.05)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA cache_size=-4096")
        connection.execute("PRAGMA mmap_size=0")
        # The supervised history worker applies SQLite's existing 32 MiB
        # hard_heap_limit. Keep CREATE INDEX sorter runs in that bounded heap.
        connection.execute("PRAGMA temp_store=MEMORY")

        def progress():
            if time.monotonic() >= deadline:
                interrupted["reason"] = "sql_deadline"
                return 1
            if interactive_waiting is not None and interactive_waiting():
                interrupted["reason"] = "interactive_waiting"
                return 1
            return 0

        connection.set_progress_handler(progress, _SQL_PROGRESS_STEPS)
    except BaseException:
        connection.close()
        raise
    return connection


def _index_sql(connection, name):
    row = connection.execute(
        "SELECT type,tbl_name,sql FROM sqlite_master WHERE name=?", (name,)
    ).fetchone()
    if row is None:
        return None
    if row["type"] != "index" or not isinstance(row["sql"], str):
        return "conflict"
    return row["sql"]


def _tables(connection):
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
            "('chunks','history_occurrences')"
        )
    }


def _verify_bounded_sorter(connection):
    options = [
        row[0]
        for row in connection.execute("PRAGMA compile_options")
        if isinstance(row[0], str) and row[0].startswith("TEMP_STORE=")
    ]
    if len(options) != 1 or options[0] not in {
        "TEMP_STORE=1",
        "TEMP_STORE=2",
        "TEMP_STORE=3",
    }:
        raise _UnsupportedStore("bounded_sorter_unavailable")
    if options[0] == "TEMP_STORE=3":
        return
    value = connection.execute("PRAGMA temp_store").fetchone()[0]
    if value != 2:
        raise _UnsupportedStore("bounded_sorter_unavailable")


def _database_indexes(directory, is_history, deadline, interactive_waiting, interrupted):
    budget = admit_history_write(directory) if is_history else None
    database, _ = _validate_store(directory, deadline, budget=budget)
    try:
        connection = _connect(database, deadline, interactive_waiting, interrupted)
    except sqlite3.Error:
        raise
    try:
        tables = _tables(connection)
        if "chunks" not in tables:
            raise ValueError("chunks table missing")
        for spec in workspace_index_specs():
            if spec["table"] not in tables:
                if spec["table"] == "history_occurrences" and not is_history:
                    continue
                if spec["table"] == "history_occurrences":
                    continue
                raise ValueError("index table missing")
            actual = _index_sql(connection, spec["name"])
            if actual is None:
                connection.close()
                return spec, database
            if actual == "conflict" or _normalize_index_sql(actual) != _normalize_index_sql(
                spec["sql"]
            ):
                raise ValueError("index definition conflict")
        return None, database
    finally:
        if connection:
            connection.close()


def _create_index(directory, spec, deadline, interactive_waiting, interrupted, *, is_history=False):
    budget = admit_history_write(directory) if is_history else MAX_STORE_BYTES
    database, _ = _validate_store(directory, deadline, budget=budget)
    connection = _connect(database, deadline, interactive_waiting, interrupted)
    try:
        _verify_bounded_sorter(connection)
        journal_mode = connection.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
        if journal_mode.lower() != "delete":
            return _pending("busy", "journal_mode", index=spec["name"])
        database, total_bytes = _validate_store(directory, deadline, budget=budget)
        page_size = connection.execute("PRAGMA page_size").fetchone()[0]
        page_count = connection.execute("PRAGMA page_count").fetchone()[0]
        max_pages = max(1, budget // (3 * page_size))
        if page_count > max_pages:
            return _pending("quota", "page_limit", index=spec["name"])
        database_bytes = database.stat().st_size
        # Reserve twice the current DB size for rollback data plus page/header
        # framing before spending the remaining store-byte budget on growth.
        store_growth_bytes = budget - total_bytes - 2 * database_bytes
        if store_growth_bytes < 0:
            return _pending("quota", "store_headroom", index=spec["name"])
        max_pages = min(max_pages, page_count + store_growth_bytes // page_size)
        result = connection.execute(f"PRAGMA max_page_count={max_pages}").fetchone()[0]
        if result > max_pages:
            return _pending("quota", "page_limit", index=spec["name"])

        free_bytes = _free_bytes(directory)
        # Preserve room for the existing physical headroom and a worst-case
        # rollback journal that reuses pages throughout the capped database.
        reserved_bytes = (
            FREE_HEADROOM_BYTES + 2 * database_bytes + (result - page_count) * page_size
        )
        if free_bytes < reserved_bytes + page_size:
            return _pending("quota", "free_headroom", index=spec["name"])
        if time.monotonic() >= deadline:
            return _pending("deadline", "sql_deadline", index=spec["name"])

        connection.execute("BEGIN IMMEDIATE")
        actual = _index_sql(connection, spec["name"])
        if actual is not None:
            if actual != "conflict" and _normalize_index_sql(actual) == _normalize_index_sql(
                spec["sql"]
            ):
                connection.rollback()
                return None
            connection.rollback()
            return _pending("corrupt", "index_definition_conflict", index=spec["name"])
        connection.execute(spec["sql"])
        if time.monotonic() >= deadline:
            connection.rollback()
            return _pending("deadline", "sql_deadline", index=spec["name"])
        connection.commit()
        return {"status": "pending", "state": "pending", "index": spec["name"]}
    finally:
        connection.close()


def index_workspace_scope(palace, *, deadline=None, interactive_waiting=None):
    """Commit one index, or report bounded pending/quota/error progress."""
    if deadline is None:
        deadline = time.monotonic() + 6
    interrupted = {}
    current_store_id = None
    current_index = None
    try:
        for store_id, directory, is_history in _store_paths(palace):
            current_store_id = store_id
            if time.monotonic() >= deadline:
                return _pending("deadline", "sql_deadline", store_id=store_id)
            if interactive_waiting is not None and interactive_waiting():
                return _pending("pending", "interactive_waiting", store_id=store_id)
            spec, _ = _database_indexes(
                directory, is_history, deadline, interactive_waiting, interrupted
            )
            if spec is None:
                continue
            current_index = spec["name"]
            if time.monotonic() >= deadline:
                return _pending("deadline", "sql_deadline", store_id=store_id, index=spec["name"])
            result = _create_index(
                directory, spec, deadline, interactive_waiting, interrupted, is_history=is_history
            )
            if result is None:
                return _pending(
                    "pending", "index_already_present", store_id=store_id, index=spec["name"]
                )
            result["store_id"] = store_id
            return result
        return {"status": "ok", "state": "complete"}
    except sqlite3.Error as exc:
        reason = interrupted.get("reason")
        if reason == "interactive_waiting":
            return _pending("pending", reason, store_id=current_store_id, index=current_index)
        if reason == "sql_deadline":
            return _pending("deadline", reason, store_id=current_store_id, index=current_index)
        status = MemoryStore._error(exc)["status"]
        return _pending(status, status, store_id=current_store_id, index=current_index)
    except HistoryBudgetRefusal as exc:
        return _pending("quota", exc.reason, store_id=current_store_id, index=current_index)
    except _QuotaExceeded as exc:
        return _pending("quota", exc.reason, store_id=current_store_id, index=current_index)
    except _UnsupportedStore as exc:
        return _pending("unavailable", exc.reason, store_id=current_store_id, index=current_index)
    except _OperationDeadline:
        return _pending("deadline", "sql_deadline", store_id=current_store_id, index=current_index)
    except _SpoolScanLimit:
        return _pending(
            "unavailable",
            "capture_spool_scan_limit",
            store_id=current_store_id,
            index=current_index,
        )
    except MemoryError:
        return _pending(
            "unavailable",
            "sqlite_heap_limit",
            store_id=current_store_id,
            index=current_index,
        )
    except _Unavailable:
        return _pending(
            "unavailable", "unavailable", store_id=current_store_id, index=current_index
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        status = "unavailable" if isinstance(exc, OSError) else "corrupt"
        return _pending(status, status, store_id=current_store_id, index=current_index)
