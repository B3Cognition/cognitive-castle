"""Bounded original-file enumeration, with durable last-observed sweep progress.

Each directory pass retains only a lexicographic page. A scan which cannot finish
within the entry/time cap does not advance its cursor or claim corpus coverage.
"""

from __future__ import annotations

import bisect
import os
from pathlib import Path
import stat
import time

from .fast_memory import _Missing
from .memory_capture import ERRORS, queue_source, source_key

MAX_SCAN_ENTRIES = 8192
SCAN_SECONDS = 0.15
MAX_PAGE = 64


def _ensure(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS discovery_roots (root_key TEXT PRIMARY KEY, "
        "path TEXT NOT NULL, format TEXT NOT NULL, sweep INTEGER NOT NULL, "
        "completed_sweeps INTEGER NOT NULL, complete_ns INTEGER, errors INTEGER NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS discovery_dirs (root_key TEXT NOT NULL, "
        "path TEXT NOT NULL, cursor TEXT NOT NULL, identity TEXT, done INTEGER NOT NULL, "
        "PRIMARY KEY(root_key,path))"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS discovery_pending ON discovery_dirs(root_key,done)")


def _open_directory(path):
    path = Path(path).absolute()
    if ".." in path.parts or len(str(path).encode()) > 2048:
        raise ValueError("invalid discovery path")
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in path.parts[1:]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _identity(info):
    return f"{info.st_dev}:{info.st_ino}:{info.st_mtime_ns}"


def _directory_page(path, cursor, identity, limit):
    fd = _open_directory(path)
    try:
        before = _identity(os.fstat(fd))
        if before != identity:
            cursor = ""
        names, scanned, started = [], 0, time.monotonic()
        with os.scandir(fd) as entries:
            for entry in entries:
                scanned += 1
                if scanned > MAX_SCAN_ENTRIES or time.monotonic() - started > SCAN_SECONDS:
                    return {
                        "status": "incomplete",
                        "reason": "discovery_entry_limit"
                        if scanned > MAX_SCAN_ENTRIES
                        else "discovery_deadline",
                    }
                if entry.name <= cursor:
                    continue
                bisect.insort(names, entry.name)
                if len(names) > limit:
                    names.pop()
        if before != _identity(os.fstat(fd)):
            return {"status": "incomplete", "reason": "discovery_directory_changed"}
        items = []
        for name in names:
            try:
                mode = os.stat(name, dir_fd=fd, follow_symlinks=False).st_mode
            except OSError:
                return {"status": "incomplete", "reason": "discovery_directory_changed"}
            items.append((name, stat.S_ISDIR(mode), stat.S_ISREG(mode)))
        return dict(
            status="ok",
            items=items,
            identity=before,
            cursor=names[-1] if names else cursor,
            done=len(names) < limit,
        )
    finally:
        os.close(fd)


def discover_sources(store, *, allowed_root, format, max_entries=16):
    """Queue at most 64 files from one directory page; no transcript text is read."""
    root = Path(allowed_root).absolute()
    if (
        format not in ("claude", "codex")
        or type(max_entries) is not int
        or not 1 <= max_entries <= MAX_PAGE
    ):
        raise ValueError("invalid discovery arguments")
    fd = _open_directory(root)
    os.close(fd)
    key = source_key(root, format)
    result = dict(
        status="ok",
        discovery="incomplete",
        queued_sources=0,
        source_currentness="last_observed_only",
    )
    try:
        with store._connect(True) as conn:
            _ensure(conn)
            conn.execute(
                "INSERT OR IGNORE INTO discovery_roots VALUES (?,?,?,1,0,NULL,0)",
                (key, str(root), format),
            )
            row = conn.execute(
                "SELECT * FROM discovery_dirs WHERE root_key=? AND done=0 ORDER BY rowid LIMIT 1",
                (key,),
            ).fetchone()
            if row is None:
                # Start another sweep, including names added behind an old cursor.
                conn.execute("DELETE FROM discovery_dirs WHERE root_key=?", (key,))
                conn.execute(
                    "UPDATE discovery_roots SET sweep=sweep+1,errors=0 WHERE root_key=?", (key,)
                )
                conn.execute("INSERT INTO discovery_dirs VALUES (?,?, '',NULL,0)", (key, str(root)))
                row = conn.execute(
                    "SELECT * FROM discovery_dirs WHERE root_key=?", (key,)
                ).fetchone()
        directory = Path(row["path"])
        if not directory.is_relative_to(root):
            raise ValueError("discovery directory outside root")
        try:
            page = _directory_page(directory, row["cursor"], row["identity"], max_entries)
        except (OSError, ValueError):
            page = {"status": "incomplete", "reason": "discovery_directory_unavailable"}
        if page["status"] != "ok":
            # A failed page is unfinished, not complete. Move to other directories
            # this sweep, then revisit it on the next sweep without advancing its cursor.
            with store._connect(True) as conn:
                conn.execute(
                    "UPDATE discovery_dirs SET done=-1 WHERE root_key=? AND path=?",
                    (key, str(directory)),
                )
                conn.execute("UPDATE discovery_roots SET errors=errors+1 WHERE root_key=?", (key,))
            return {**result, "reason": page["reason"]}
        children, errors = [], 0
        for name, is_dir, is_file in page["items"]:
            path = directory / name
            if len(str(path).encode()) > 2048:
                errors += 1
            elif is_dir:
                children.append(str(path))
            elif is_file and path.suffix == ".jsonl":
                try:
                    queued = queue_source(store, path, allowed_root=root, format=format)
                except (OSError, ValueError):
                    errors += 1
                    continue
                if queued["status"] != "ok":
                    return {
                        **result,
                        "status": queued["status"],
                        "reason": queued.get("reason", "queue_failed"),
                    }
                result["queued_sources"] += 1
        with store._connect(True) as conn:
            for child in children:
                conn.execute(
                    "INSERT OR IGNORE INTO discovery_dirs VALUES (?,?,'',NULL,0)", (key, child)
                )
            conn.execute(
                "UPDATE discovery_dirs SET cursor=?,identity=?,done=? WHERE root_key=? AND path=?",
                (page["cursor"], page["identity"], int(page["done"]), key, str(directory)),
            )
            conn.execute(
                "UPDATE discovery_roots SET errors=errors+? WHERE root_key=?", (errors, key)
            )
            pending = conn.execute(
                "SELECT 1 FROM discovery_dirs WHERE root_key=? AND done=0 LIMIT 1", (key,)
            ).fetchone()
            failures = conn.execute(
                "SELECT errors FROM discovery_roots WHERE root_key=?", (key,)
            ).fetchone()[0]
            if pending is None and failures == 0:
                conn.execute(
                    "UPDATE discovery_roots SET completed_sweeps=completed_sweeps+1,complete_ns=? WHERE root_key=?",
                    (time.time_ns(), key),
                )
                result["discovery"] = "complete_at_last_sweep"
            elif failures:
                result["reason"] = "discovery_source_errors"
        return result
    except ERRORS as exc:
        return store._error(exc)


def discovery_status(store):
    result = dict(status="ok", roots=[], source_currentness="last_observed_only")
    try:
        with store._connect() as conn:
            if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='discovery_roots'"
            ).fetchone():
                return result
            for row in conn.execute("SELECT * FROM discovery_roots ORDER BY root_key LIMIT 8"):
                pending = conn.execute(
                    "SELECT count(*) FROM discovery_dirs WHERE root_key=? AND done=0",
                    (row["root_key"],),
                ).fetchone()[0]
                result["roots"].append(
                    {
                        **dict(row),
                        "pending_directories": pending,
                        "discovery": "incomplete"
                        if pending or row["errors"]
                        else "complete_at_last_sweep",
                    }
                )
        return result
    except _Missing:
        return result
    except ERRORS as exc:
        return store._error(exc)
