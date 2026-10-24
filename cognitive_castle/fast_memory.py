"""Bounded, exact UTF-8 memory. No legacy backend or model dependencies."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time

MAX_STORE_BYTES = 1024**3
DB_NAME = "memory.sqlite3"


def _json(value):
    def validate(item, depth=0):
        if depth > 32:
            raise ValueError("JSON nesting")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError("JSON keys must be strings")
                validate(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                validate(child, depth + 1)
        elif item is not None and type(item) not in (str, int, float, bool):
            raise ValueError("invalid JSON value")

    try:
        validate(value)
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("invalid JSON") from exc


def _string(value, maximum, name, *, empty=False):
    if not isinstance(value, str) or (not empty and not value):
        raise ValueError(name)
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise ValueError(name) from exc
    if size > maximum:
        raise ValueError(name)
    return value


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _Unavailable(Exception):
    pass


class _Quota(Exception):
    pass


class MemoryStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory).absolute()
        self.db_path = self.directory / DB_NAME

    def _private(self, path, directory=False):
        info = path.lstat()
        expected = stat.S_ISDIR if directory else stat.S_ISREG
        if not expected(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise _Unavailable("unsafe permissions or file type")
        if not directory and info.st_nlink != 1:
            raise _Unavailable("hard-linked storage")

    @contextmanager
    def _connect(self, write=False):
        if os.name != "posix" or not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "getuid"):
            raise _Unavailable("privacy primitives unavailable")
        # Do not resolve paths: every existing ancestor must reject symlinks.
        for path in reversed([self.directory, *self.directory.parents]):
            if path.is_symlink():
                raise _Unavailable("symlink ancestor")
        if not self.directory.exists():
            if not write:
                raise _Unavailable("not initialized")
            self.directory.mkdir(mode=0o700)
        self._private(self.directory, True)
        for name in [DB_NAME, DB_NAME + "-journal", DB_NAME + "-wal", DB_NAME + "-shm"]:
            path = self.directory / name
            if path.exists() or path.is_symlink():
                self._private(path)
        if not self.db_path.exists():
            if not write:
                raise _Unavailable("not initialized")
            fd = os.open(self.db_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            os.close(fd)
        if write and sum(p.stat().st_size for p in self.directory.iterdir()) >= MAX_STORE_BYTES:
            raise _Quota()
        conn = sqlite3.connect(
            self.db_path.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True, timeout=0.05
        )
        conn.row_factory = sqlite3.Row
        deadline = time.monotonic() + (3 if write else 2)
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        try:
            conn.execute("PRAGMA cache_size=-4096")
            conn.execute("PRAGMA mmap_size=0")
            conn.execute("PRAGMA temp_store=FILE")
            if write:
                conn.execute("PRAGMA journal_mode=DELETE")
                # Reserve room for rollback journal and disk-backed temporary work.
                # This deliberately admits less data than the total sidecar budget.
                page_size = conn.execute("PRAGMA page_size").fetchone()[0]
                conn.execute(f"PRAGMA max_page_count={max(1, MAX_STORE_BYTES // (3 * page_size))}")
                conn.execute("BEGIN IMMEDIATE")
                for sql in [
                    "CREATE TABLE IF NOT EXISTS chunks (id TEXT PRIMARY KEY, text TEXT NOT NULL, provenance TEXT NOT NULL, text_hash TEXT NOT NULL, start INTEGER NOT NULL, end INTEGER NOT NULL)",
                    "CREATE VIRTUAL TABLE IF NOT EXISTS lexical USING fts5(id UNINDEXED, text)",
                    "CREATE TABLE IF NOT EXISTS receipts (namespace TEXT, request_id TEXT, digest TEXT, ids TEXT, PRIMARY KEY(namespace, request_id))",
                    "CREATE TABLE IF NOT EXISTS checkpoints (source_key TEXT PRIMARY KEY, value TEXT NOT NULL)",
                ]:
                    conn.execute(sql)
            yield conn
            if write:
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _error(exc):
        if isinstance(exc, _Quota):
            status = "quota"
        elif isinstance(exc, sqlite3.Error):
            code = getattr(exc, "sqlite_errorcode", 0) & 255
            status = {
                sqlite3.SQLITE_BUSY: "busy",
                sqlite3.SQLITE_LOCKED: "busy",
                sqlite3.SQLITE_FULL: "quota",
                sqlite3.SQLITE_INTERRUPT: "deadline",
                sqlite3.SQLITE_CORRUPT: "corrupt",
                sqlite3.SQLITE_NOTADB: "corrupt",
            }.get(code, "unavailable")
        else:
            status = "unavailable"
        return {"status": status}

    def remember(
        self,
        request_id: str,
        text: str,
        provenance: dict | None = None,
        *,
        namespace: str = "operator",
    ) -> dict:
        _string(request_id, 128, "request_id")
        _string(namespace, 128, "namespace")
        _string(text, 65536, "text")
        if provenance is not None and not isinstance(provenance, dict):
            raise ValueError("provenance")
        provenance_json = _json(provenance or {})
        _string(provenance_json, 512, "provenance")
        digest = _hash(_json([namespace, request_id, text, provenance or {}]))
        chunks, start, pending, size = [], 0, "", 0
        for character in text:
            width = len(character.encode())
            if size + width > 8192:
                chunks.append((start, pending))
                start += len(pending)
                pending, size = "", 0
            pending += character
            size += width
        if pending:
            chunks.append((start, pending))
        ids = ["memory:" + _hash(f"{digest}:{i}") for i in range(len(chunks))]
        receipt = {
            "status": "ok",
            "ids": ids,
            "stored_text_bytes": len(text.encode()),
            "text_sha256": _hash(text),
        }
        try:
            with self._connect(True) as conn:
                old = conn.execute(
                    "SELECT digest, ids FROM receipts WHERE namespace=? AND request_id=?",
                    (namespace, request_id),
                ).fetchone()
                if old:
                    return (
                        dict(receipt, ids=json.loads(old["ids"]))
                        if old["digest"] == digest
                        else {"status": "conflict"}
                    )
                for identity, (offset, chunk) in zip(ids, chunks):
                    conn.execute(
                        "INSERT INTO chunks VALUES (?,?,?,?,?,?)",
                        (
                            identity,
                            chunk,
                            provenance_json,
                            _hash(chunk),
                            offset,
                            offset + len(chunk),
                        ),
                    )
                    conn.execute("INSERT INTO lexical VALUES (?,?)", (identity, chunk))
                conn.execute(
                    "INSERT INTO receipts VALUES (?,?,?,?)",
                    (namespace, request_id, digest, _json(ids)),
                )
            return receipt
        except (OSError, sqlite3.Error, _Unavailable, _Quota) as exc:
            return self._error(exc)

    @staticmethod
    def _source(row):
        return {
            "id": row["id"],
            "text": row["text"],
            "provenance": json.loads(row["provenance"]),
            "origin": "archive",
            "local_only": True,
            "storage_format": "sqlite-fts5-utf8-v1",
            "text_hash": row["text_hash"],
            "chunk_start": row["start"],
            "chunk_end": row["end"],
        }

    def recall(self, query: str, *, limit: int = 8) -> dict:
        _string(query, 1024, "query")
        terms = re.findall(r"\w+", query, re.UNICODE)
        if not terms or len(terms) > 16 or type(limit) is not int or not 1 <= limit <= 8:
            raise ValueError("query or limit")
        literal = " AND ".join('"' + term.replace('"', '""') + '"' for term in terms)
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT c.* FROM lexical JOIN chunks c ON c.id=lexical.id WHERE lexical MATCH ? ORDER BY rank LIMIT ?",
                    (literal, limit),
                ).fetchall()
                result = {"status": "ok", "sources": [], "coverage": "indexed_only"}
                for row in rows:
                    source = self._source(row)
                    source["text"] = source["text"][:256]
                    source["preview"] = True
                    result["sources"].append(source)
                    if len(_json(result).encode()) > 8192:
                        result["sources"].pop()
                        break
                return result
        except (OSError, sqlite3.Error, _Unavailable, _Quota) as exc:
            return self._error(exc)

    def read_sources(self, ids: list[str]) -> dict:
        if not isinstance(ids, list) or not 1 <= len(ids) <= 8:
            raise ValueError("ids")
        for identity in ids:
            _string(identity, 128, "id")
            if not identity.startswith("memory:"):
                raise ValueError("id")
        try:
            with self._connect() as conn:
                sources = []
                for identity in ids:
                    row = conn.execute("SELECT * FROM chunks WHERE id=?", (identity,)).fetchone()
                    if row is None:
                        return {"status": "not_found", "sources": []}
                    sources.append(self._source(row))
                return {"status": "ok", "sources": sources}
        except (OSError, sqlite3.Error, _Unavailable, _Quota) as exc:
            return self._error(exc)

    def page(
        self,
        source_id: str,
        *,
        offset: int = 0,
        limit: int = 2048,
        expected_hash: str | None = None,
    ) -> dict:
        if (
            type(offset) is not int
            or offset < 0
            or type(limit) is not int
            or not 1 <= limit <= 2048
        ):
            raise ValueError("page bounds")
        if expected_hash is not None:
            _string(expected_hash, 128, "expected_hash")
        result = self.read_sources([source_id])
        if result["status"] != "ok":
            return result
        source = result["sources"][0]
        if expected_hash is not None and expected_hash != source["text_hash"]:
            return {"status": "stale"}
        text = source["text"]
        source.update(
            status="ok",
            text=text[offset : offset + limit],
            offset=offset,
            next_offset=min(len(text), offset + limit),
            complete=offset + limit >= len(text),
        )
        return source

    def status(self) -> dict:
        try:
            with self._connect() as conn:
                count = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
                return {
                    "status": "ok",
                    "indexed_chunks": count,
                    "coverage": "indexed_only",
                    "storage_format": "sqlite-fts5-utf8-v1",
                }
        except (OSError, sqlite3.Error, _Unavailable, _Quota) as exc:
            return self._error(exc)

    def load_checkpoint(self, source_key: str) -> dict | None:
        _string(source_key, 128, "source_key")
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT value FROM checkpoints WHERE source_key=?", (source_key,)
                ).fetchone()
                if row is None:
                    return None
                try:
                    value = json.loads(_string(row[0], 8192, "checkpoint"))
                    self._checkpoint(value)
                    return value
                except (ValueError, TypeError, RecursionError) as exc:
                    raise ValueError("corrupt checkpoint") from exc
        except _Unavailable:
            return None

    @staticmethod
    def _checkpoint(checkpoint):
        if not isinstance(checkpoint, dict):
            raise ValueError("checkpoint")
        return _string(_json(checkpoint), 8192, "checkpoint")

    def save_checkpoint(self, source_key: str, checkpoint: dict) -> None:
        _string(source_key, 128, "source_key")
        value = self._checkpoint(checkpoint)
        with self._connect(True) as conn:
            conn.execute(
                "INSERT INTO checkpoints VALUES (?,?) ON CONFLICT(source_key) DO UPDATE SET value=excluded.value",
                (source_key, value),
            )
