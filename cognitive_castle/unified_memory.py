"""Private bounded federation of exact SQLite memory stores.

Ranks are interleaved by local ordinal, then stable store ID and canonical ID;
FTS scores from unrelated corpora are deliberately never compared. All scopes
and complete-source exposure grants are applied before assigning ordinals.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time

from .fast_memory import (
    MAX_STORE_BYTES,
    MemoryStore,
    _Corrupt,
    _Quota,
    _Unavailable,
    _hash,
    _json,
    _string,
)

READ_SECONDS = 2
_COLUMNS = "c.id,CAST(substr(CAST(c.text AS BLOB),1,8193) AS TEXT) AS text,CAST(substr(CAST(c.provenance AS BLOB),1,513) AS TEXT) AS provenance,c.text_hash,c.start,c.end"
MAX_CATALOG_BYTES = 16384
MAX_HISTORY_STORES = 8
MAX_OUTPUT_BYTES = 8192
_STATES = {
    "pending",
    "indexing",
    "indexed",
    "complete",
    "changed",
    "unsupported",
    "blocked",
    "failed",
}
_ERRORS = (OSError, sqlite3.Error, _Unavailable, _Quota, _Corrupt)


def workspace_index_specs():
    """Derived workspace indexes, installed only by bounded operator writes."""
    chunk = "CASE WHEN json_valid(provenance) THEN json_extract(provenance,'$.workspace') END"
    history = (
        "COALESCE(CASE WHEN json_valid(columns_json) THEN json_extract(columns_json,'$.workspace') END,"
        "CASE WHEN json_valid(metadata_json) THEN json_extract(metadata_json,'$.workspace') END)"
    )
    return tuple(
        {
            "name": name,
            "table": table,
            "expression": expression,
            "sql": f"CREATE INDEX {name} ON {table}({expression}) WHERE {expression} IS NOT NULL",
        }
        for name, table, expression in (
            ("unified_chunk_workspace_v1", "chunks", chunk),
            ("unified_history_workspace_v1", "history_occurrences", history),
        )
    )


def _index_sql(sql):
    # Keep JSON paths case-sensitive: uppercasing SQL would equate different scopes.
    return re.sub(r"\s+", " ", sql.strip()).replace("CREATE INDEX IF NOT EXISTS ", "CREATE INDEX ")


def history_store_path(palace: Path, store_id: str) -> Path:
    if not isinstance(store_id, str) or not re.fullmatch(r"[a-f0-9]{64}", store_id):
        raise ValueError("store_id must be lowercase SHA256")
    return Path(palace).absolute() / ".memory-history" / store_id


def _history_root(palace, *, create=False):
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "getuid"):
        raise _Unavailable("privacy primitives unavailable")
    directory = Path(palace).absolute() / ".memory-history"
    # Reuse the live store's strict owner/mode/link checks without creating a DB.
    store = MemoryStore(directory)
    for parent in [directory, *directory.parents]:
        if parent.is_symlink():
            raise _Unavailable("symlink ancestor")
    if create and not directory.exists():
        directory.mkdir(mode=0o700)
    if directory.exists():
        store._private(directory, True)
    return directory


def _catalog(palace):
    directory = _history_root(palace)
    path = directory / "catalog.json"
    if not path.exists() and not path.is_symlink():
        return {"version": 1, "generation": 0, "stores": []}, "unregistered"
    MemoryStore(directory)._private(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        raw = handle.read(MAX_CATALOG_BYTES + 1)
    if len(raw) > MAX_CATALOG_BYTES:
        raise _Corrupt("catalog size")
    try:
        value = json.loads(raw)
        if (
            not isinstance(value, dict)
            or set(value) != {"version", "generation", "stores"}
            or value["version"] != 1
            or type(value["generation"]) is not int
            or not 0 <= value["generation"] <= 2**63 - 1
            or not isinstance(value["stores"], list)
            or len(value["stores"]) > MAX_HISTORY_STORES
        ):
            raise ValueError("catalog schema")
        seen = set()
        for entry in value["stores"]:
            if not isinstance(entry, dict) or set(entry) != {
                "store_id",
                "archive_id",
                "state",
                "indexed_rows",
                "total_rows",
            }:
                raise ValueError("catalog entry")
            _entry(palace, **entry)
            if entry["store_id"] in seen:
                raise ValueError("duplicate catalog store")
            seen.add(entry["store_id"])
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise _Corrupt("invalid catalog") from exc
    return value, hashlib.sha256(raw).hexdigest()


def _entry(palace, store_id, archive_id, state, indexed_rows=0, total_rows=None):
    history_store_path(palace, store_id)
    _string(archive_id, 512, "archive_id")
    if not isinstance(state, str) or state not in _STATES:
        raise ValueError("history state")
    if type(indexed_rows) is not int or not 0 <= indexed_rows <= 2**63 - 1:
        raise ValueError("indexed_rows")
    if total_rows is not None and (
        type(total_rows) is not int or not indexed_rows <= total_rows <= 2**63 - 1
    ):
        raise ValueError("total_rows")
    if state == "complete" and total_rows != indexed_rows:
        raise ValueError("complete history requires reconciled inventory")
    return dict(
        store_id=store_id,
        archive_id=archive_id,
        state=state,
        indexed_rows=indexed_rows,
        total_rows=total_rows,
    )


def register_history_store(palace, store_id, *, archive_id, state, indexed_rows=0, total_rows=None):
    """Atomically publish a bounded private catalog; never open native archives."""
    entry = _entry(palace, store_id, archive_id, state, indexed_rows, total_rows)
    return _publish_history_entry(palace, entry)


def supersede_history_store(
    palace,
    old_store_id,
    new_store_id,
    *,
    archive_id,
    previous_archive_id=None,
    state="pending",
    indexed_rows=0,
    total_rows=None,
):
    """Replace only a verified empty failed pin; retain every original file.

    Catalog comparison and replacement share one lock and one atomic publish.
    Repeating an already committed replacement is safe after a checkpoint crash.
    Importers use the common admission lock before writing stores.
    """
    history_store_path(palace, old_store_id)
    if old_store_id == new_store_id:
        raise ValueError("distinct replacement store required")
    entry = _entry(palace, new_store_id, archive_id, state, indexed_rows, total_rows)
    if indexed_rows or total_rows is not None or state not in {"pending", "changed", "failed"}:
        raise ValueError("replacement must be an unindexed pin")
    if previous_archive_id is None:
        previous_archive_id = archive_id
    _string(previous_archive_id, 512, "previous_archive_id")
    return _publish_history_entry(
        palace, entry, replaced=old_store_id, previous_archive_id=previous_archive_id
    )


def _empty_history_store(palace, identity):
    store = MemoryStore(history_store_path(palace, identity))
    if not store.directory.exists():
        return True
    store._private(store.directory, True)
    if not store.db_path.exists():
        return not any(
            (store.directory / ("memory.sqlite3" + suffix)).exists()
            for suffix in ("-journal", "-wal", "-shm")
        )
    with store._connect() as conn:
        conn.execute("BEGIN")
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='chunks'").fetchone():
            return False
        for table in ("chunks", "history_occurrences"):
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone():
                if conn.execute("SELECT 1 FROM " + table + " LIMIT 1").fetchone():
                    return False
    return True


def _publish_history_entry(palace, entry, *, replaced=None, previous_archive_id=None):
    temporary = None
    store_id, archive_id = entry["store_id"], entry["archive_id"]
    retirement = None
    try:
        directory = _history_root(palace, create=True)
        import fcntl

        lock_path = directory / "catalog.lock"
        if lock_path.exists() or lock_path.is_symlink():
            MemoryStore(directory)._private(lock_path)
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "rb") as lock:
            MemoryStore(directory)._private(lock_path)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            catalog, _ = _catalog(palace)
            entries = {item["store_id"]: item for item in catalog["stores"]}
            previous = entries.get(store_id)
            if replaced is not None:
                old = entries.get(replaced)
                if old is None:
                    return (
                        {"status": "ok", "generation": catalog["generation"]}
                        if previous == entry
                        else {"status": "conflict"}
                    )
                if (
                    previous is not None
                    or old["archive_id"] != previous_archive_id
                    or old["indexed_rows"] != 0
                    or old["total_rows"] is not None
                    or old["state"] not in {"pending", "changed", "failed"}
                ):
                    return {"status": "conflict"}
                old_store = MemoryStore(history_store_path(palace, replaced))
                before = _fingerprint(old_store)
                if not _empty_history_store(palace, replaced) or before != _fingerprint(old_store):
                    return {"status": "conflict"}
                retirement = (old_store, before)
                del entries[replaced]
            if previous and previous["archive_id"] != archive_id:
                raise _Corrupt("archive identity changed")
            if previous == entry:
                return {"status": "ok", "generation": catalog["generation"]}
            entries[store_id] = entry
            if len(entries) > MAX_HISTORY_STORES:
                raise _Quota()
            total_bytes = 0
            for identity in entries:
                store_directory = history_store_path(palace, identity)
                if store_directory.exists():
                    MemoryStore(store_directory)._private(store_directory, True)
                    size = 0
                    for child in store_directory.iterdir():
                        if child.is_symlink():
                            raise _Unavailable("symlink history file")
                        if child.is_file():
                            size += child.stat().st_size
                    if size > MAX_STORE_BYTES:
                        raise _Quota()
                    total_bytes += size
            if total_bytes > MAX_HISTORY_STORES * MAX_STORE_BYTES:
                raise _Quota()
            value = {
                "version": 1,
                "generation": catalog["generation"] + 1,
                "stores": [entries[key] for key in sorted(entries)],
            }
            encoded = _json(value).encode()
            if len(encoded) > MAX_CATALOG_BYTES:
                raise _Quota()
            temporary = directory / (".catalog-" + os.urandom(12).hex())
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            if retirement is not None and _fingerprint(retirement[0]) != retirement[1]:
                return {"status": "conflict"}
            os.replace(temporary, directory / "catalog.json")
            temporary = None
            directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            return {"status": "ok", "generation": value["generation"]}
    except _ERRORS as exc:
        return MemoryStore._error(exc)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _fingerprint(store):
    values = []
    for name in (
        "memory.sqlite3",
        "memory.sqlite3-journal",
        "memory.sqlite3-wal",
        "memory.sqlite3-shm",
    ):
        path = store.directory / name
        try:
            value = path.lstat()
            values.append(
                [
                    name,
                    value.st_dev,
                    value.st_ino,
                    value.st_size,
                    value.st_mtime_ns,
                    value.st_ctime_ns,
                ]
            )
        except FileNotFoundError:
            values.append([name, None])
    return values


def _exposure(source):
    # Exact existing source_exposure_hash encoding; import no controller state.
    return _hash(_json({key: source[key] for key in ("id", "text", "provenance")}))


class UnifiedMemoryStore:
    def __init__(self, palace: Path):
        self.palace = Path(palace).absolute()

    @contextmanager
    def _snapshot(self, deadline):
        catalog, catalog_hash = _catalog(self.palace)
        entries = [("live", MemoryStore(self.palace / ".memory"), None)]
        entries += [
            (item["store_id"], MemoryStore(history_store_path(self.palace, item["store_id"])), item)
            for item in catalog["stores"]
        ]
        coverage = {"complete": False, "limitations": [], "stores": []}
        if catalog_hash == "unregistered":
            coverage["limitations"].append("history_not_registered")
        opened, generations = [], []
        with ExitStack() as stack:
            for identity, store, entry in entries:
                if time.monotonic() >= deadline:
                    raise TimeoutError()
                before = _fingerprint(store)
                detail = {"store_id": identity, "status": "ok"}
                if entry:
                    detail.update(
                        state=entry["state"],
                        indexed_rows=entry["indexed_rows"],
                        total_rows=entry["total_rows"],
                    )
                    if entry["state"] != "complete":
                        coverage["limitations"].append("history_" + entry["state"])
                try:
                    conn = stack.enter_context(store._connect())
                    conn.set_progress_handler(lambda: int(time.monotonic() >= deadline), 100)
                    conn.execute("BEGIN")
                    # Establish a read snapshot before recording the generation.
                    conn.execute("SELECT rootpage FROM sqlite_master LIMIT 1").fetchone()
                    if before != _fingerprint(store):
                        raise _Unavailable("store changed while opening")
                    opened.append((identity, store, conn))
                except _ERRORS as exc:
                    detail["status"] = MemoryStore._error(exc)["status"]
                    coverage["limitations"].append("store_" + detail["status"])
                generations.append([identity, before])
                coverage["stores"].append(detail)
            generation = _hash(_json([catalog_hash, generations]))
            yield opened, coverage, generation
            if time.monotonic() >= deadline:
                raise TimeoutError()
            if _catalog(self.palace)[1] != catalog_hash or any(
                before != _fingerprint(store)
                for (_, store, _), (_, before) in zip(entries, generations)
            ):
                raise _Unavailable("generation_changed")

    @staticmethod
    def _failure(exc):
        if isinstance(exc, TimeoutError):
            result = {"status": "deadline"}
        else:
            result = MemoryStore._error(exc)
        result["coverage"] = "indexed_only"
        result["coverage_detail"] = {"complete": False, "limitations": [result["status"]]}
        return result

    @staticmethod
    def _scopes(workspace, wing, room):
        for name, value in (("workspace", workspace), ("wing", wing), ("room", room)):
            if value is not None:
                _string(value, 2048 if name == "workspace" else 512, name)

    @staticmethod
    def _selection(conn, *, literal, workspace, wing, room, allowed):
        clauses, parameters = [], []
        join = ""
        if literal is not None:
            join = " JOIN lexical ON lexical.id=c.id"
            clauses.append("lexical MATCH ?")
            parameters.append(literal)
        historical = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='history_occurrences'"
        ).fetchone()
        for field, value in (("workspace", workspace), ("wing", wing), ("room", room)):
            if value is None:
                continue
            expression = "json_extract(c.provenance,'$." + field + "')"
            if historical:
                expression = (
                    "COALESCE((SELECT COALESCE("
                    "CASE WHEN json_valid(h.columns_json) THEN json_extract(h.columns_json,'$."
                    + field
                    + "') END,"
                    "CASE WHEN json_valid(h.metadata_json) THEN json_extract(h.metadata_json,'$."
                    + field
                    + "') END) "
                    "FROM history_occurrences h WHERE h.identity=json_extract(c.provenance,'$.metadata_id')),"
                    + expression
                    + ")"
                )
            scope = expression + "=?"
            parameters.append(value)
            if (
                field == "workspace"
                and conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='capture_chunk_scopes'"
                ).fetchone()
            ):
                scope = (
                    "("
                    + scope
                    + " OR EXISTS (SELECT 1 FROM capture_chunk_scopes s WHERE s.chunk_id=c.id AND s.workspace=?))"
                )
                parameters.append(value)
            clauses.append(scope)
        if allowed is not None:

            def permitted(identity, text, provenance, text_hash, start, end):
                source = MemoryStore._source(
                    dict(
                        id=identity,
                        text=text,
                        provenance=provenance,
                        text_hash=text_hash,
                        start=start,
                        end=end,
                    )
                )
                return int(_exposure(source) in allowed)

            conn.create_function("source_allowed", 6, permitted, deterministic=True)
            clauses.append(
                "source_allowed(c.id,CAST(substr(CAST(c.text AS BLOB),1,8193) AS TEXT),CAST(substr(CAST(c.provenance AS BLOB),1,513) AS TEXT),c.text_hash,c.start,c.end)=1"
            )
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        order = "rank,c.id" if literal is not None else "c.id"
        # SQLite limits persisted values before Python allocates them; _source validates lengths.
        columns = _COLUMNS
        return columns + " FROM chunks c" + join + where + " ORDER BY " + order, parameters

    def recall(
        self,
        query,
        *,
        limit=8,
        match="all",
        workspace=None,
        wing=None,
        room=None,
        allowed_source_hashes=None,
        policy_epoch=None,
        cursor=None,
    ):
        _string(query, 1024, "query")
        terms = re.findall(r"\w+", query, re.UNICODE)
        if not terms or len(terms) > 16 or match not in ("all", "any"):
            raise ValueError("query or match")
        literal = (" AND " if match == "all" else " OR ").join('"' + term + '"' for term in terms)
        return self._query(
            literal,
            query,
            limit,
            match,
            workspace,
            wing,
            room,
            allowed_source_hashes,
            policy_epoch,
            cursor,
            preview=True,
        )

    def scoped_source(self, source_id, workspace):
        """Hydrate one canonical occurrence only if its authoritative scope matches."""
        if not isinstance(source_id, str) or not re.fullmatch(r"memory:[a-f0-9]{64}", source_id):
            raise ValueError("source_id")
        self._scopes(workspace, None, None)
        if workspace is None:
            raise ValueError("workspace")
        try:
            with self._snapshot(time.monotonic() + READ_SECONDS) as (stores, coverage, _):
                matched = False
                for _, _, conn in stores:
                    selection, parameters = self._selection(
                        conn, literal=None, workspace=workspace, wing=None, room=None, allowed=None
                    )
                    before_order, order = selection.rsplit(" ORDER BY ", 1)
                    row = conn.execute(
                        "SELECT " + before_order + " AND c.id=? ORDER BY " + order + " LIMIT 1",
                        [*parameters, source_id],
                    ).fetchone()
                    matched = matched or row is not None
                if not matched:
                    return {"status": "not_found", "coverage_detail": coverage}
                source = self._hydrate(stores, source_id)
                return {"status": "ok", "source": source, "coverage_detail": coverage}
        except (*_ERRORS, TimeoutError) as exc:
            return self._failure(exc)

    def context_sources(self, workspace, *, limit=8):
        return self._query(
            None, None, limit, "all", workspace, None, None, None, None, None, preview=False
        )

    @staticmethod
    def _context_selection(conn, workspace):
        """Seek workspace candidates before hydrating; old stores stay explicitly partial."""
        specs = workspace_index_specs()
        names = [spec["name"] for spec in specs] + [
            "history_occurrences",
            "history_occurrence_chunks",
            "capture_chunk_scopes",
            "capture_chunk_workspace",
        ]
        objects = {
            row["name"]: dict(row)
            for row in conn.execute(
                "SELECT name,type,tbl_name,sql FROM sqlite_master WHERE name IN ("
                + ",".join("?" for _ in names)
                + ")",
                names,
            )
        }
        historical = "history_occurrences" in objects
        ready, missing = {}, []
        for spec in specs:
            if spec["table"] == "history_occurrences" and not historical:
                continue
            actual = objects.get(spec["name"])
            valid = (
                actual is not None
                and actual["type"] == "index"
                and actual["tbl_name"] == spec["table"]
                and isinstance(actual["sql"], str)
                and _index_sql(actual["sql"]) == _index_sql(spec["sql"])
            )
            if valid:
                ready[spec["table"]] = spec
            else:
                missing.append(spec["name"])
        branches, parameters = [], []
        history_expression = (
            specs[1]["expression"]
            .replace("columns_json", "h.columns_json")
            .replace("metadata_json", "h.metadata_json")
        )
        if "chunks" in ready:
            spec = ready["chunks"]
            expression = spec["expression"].replace("provenance", "c0.provenance")
            branch = (
                f"SELECT c0.id FROM chunks AS c0 INDEXED BY {spec['name']} WHERE {expression}=?"
            )
            if historical:
                # Registry scope is authoritative, including long values not
                # copied into the small caller-provenance envelope.
                branch += (
                    " AND (SELECT "
                    + history_expression
                    + " FROM history_occurrences h WHERE h.identity=json_extract(c0.provenance,'$.metadata_id')) IS NULL"
                )
            branches.append(branch)
            parameters.append(workspace)
        if "history_occurrences" in ready:
            spec = ready["history_occurrences"]
            branches.append(
                f"SELECT member.value FROM history_occurrences AS h INDEXED BY {spec['name']} "
                + "JOIN json_each(h.ids) AS member WHERE "
                + history_expression
                + "=?"
            )
            parameters.append(workspace)
            if "history_occurrence_chunks" in objects:
                branches.append(
                    f"SELECT member.chunk_id FROM history_occurrences AS h INDEXED BY {spec['name']} "
                    + "JOIN history_occurrence_chunks AS member ON member.identity=h.identity WHERE "
                    + history_expression
                    + "=?"
                )
                parameters.append(workspace)
        if "capture_chunk_scopes" in objects:
            index = objects.get("capture_chunk_workspace")
            valid = (
                index is not None
                and index["type"] == "index"
                and index["tbl_name"] == "capture_chunk_scopes"
            )
            if valid:
                columns = conn.execute("PRAGMA index_info('capture_chunk_workspace')").fetchall()
                indexes = conn.execute("PRAGMA index_list('capture_chunk_scopes')").fetchall()
                valid = (
                    bool(columns)
                    and columns[0][2] == "workspace"
                    and any(row[1] == "capture_chunk_workspace" and not row[4] for row in indexes)
                )
            if valid:
                branches.append(
                    "SELECT chunk_id FROM capture_chunk_scopes INDEXED BY capture_chunk_workspace WHERE workspace=?"
                )
                parameters.append(workspace)
            else:
                missing.append("capture_chunk_workspace")
        if not branches:
            return _COLUMNS + " FROM chunks c WHERE 0 ORDER BY c.id", [], missing
        # Revalidate the original scope predicate on the indexed candidate IDs.
        # A malformed occurrence membership must not cross workspace boundaries.
        selection, scope_parameters = UnifiedMemoryStore._selection(
            conn, literal=None, workspace=workspace, wing=None, room=None, allowed=None
        )
        before_order, order = selection.rsplit(" ORDER BY ", 1)
        return (
            before_order + " AND c.id IN (" + " UNION ".join(branches) + ") ORDER BY " + order,
            [*scope_parameters, *parameters],
            missing,
        )

    def _query(
        self, literal, query, limit, match, workspace, wing, room, grants, epoch, cursor, *, preview
    ):
        if type(limit) is not int or not 1 <= limit <= 8:
            raise ValueError("limit")
        self._scopes(workspace, wing, room)
        if epoch is not None:
            _string(epoch, 128, "policy_epoch")
        if grants is not None and (
            not isinstance(grants, list)
            or len(grants) > 256
            or any(
                not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value)
                for value in grants
            )
        ):
            raise ValueError("allowed_source_hashes")
        allowed = set(grants) if grants is not None else None
        binding = _hash(
            _json(
                [
                    query,
                    match,
                    workspace,
                    wing,
                    room,
                    sorted(allowed) if allowed is not None else None,
                    epoch,
                ]
            )
        )
        positions = {}
        old_generation = None
        if cursor is not None:
            _string(cursor, 2048, "cursor")
            try:
                token = json.loads(base64.urlsafe_b64decode(cursor.encode()))
                if (
                    not isinstance(token, dict)
                    or set(token) != {"binding", "generation", "positions"}
                    or not isinstance(token["positions"], dict)
                    or len(token["positions"]) > 9
                    or any(
                        not isinstance(key, str)
                        or type(value) is not int
                        or not 0 <= value <= 2**63 - 1
                        for key, value in token["positions"].items()
                    )
                ):
                    raise ValueError("cursor")
                if token["binding"] != binding:
                    return {"status": "stale_cursor", "restart_required": True}
                old_generation, positions = token["generation"], token["positions"]
            except (ValueError, TypeError, KeyError, UnicodeError) as exc:
                raise ValueError("cursor") from exc
        deadline = time.monotonic() + READ_SECONDS
        try:
            with self._snapshot(deadline) as (stores, coverage, generation):
                if old_generation is not None and generation != old_generation:
                    return {"status": "stale_cursor", "restart_required": True}
                result = {
                    "status": "ok",
                    "sources": [],
                    "coverage": "indexed_only",
                    "coverage_detail": coverage,
                    "matching": match,
                    "generation": generation,
                    "next_cursor": None,
                }
                if not stores:
                    result["status"] = "unavailable"
                    return result
                candidates = []
                # Only one ordinal prefix per store is retained; no corpus-wide collection.
                for identity, _, conn in stores:
                    if literal is None and workspace is not None:
                        selection, parameters, missing = self._context_selection(conn, workspace)
                        if missing:
                            if "scope_index_pending" not in coverage["limitations"]:
                                coverage["limitations"].append("scope_index_pending")
                            coverage["complete"] = False
                            for detail in coverage["stores"]:
                                if detail["store_id"] == identity:
                                    detail["scope_indexes_missing"] = missing
                    else:
                        selection, parameters = self._selection(
                            conn,
                            literal=literal,
                            workspace=workspace,
                            wing=wing,
                            room=room,
                            allowed=allowed,
                        )
                    offset = positions.get(identity, 0)
                    for ordinal, row in enumerate(
                        conn.execute(
                            "SELECT " + selection + " LIMIT ? OFFSET ?",
                            [*parameters, limit + 1, offset],
                        ),
                        start=offset,
                    ):
                        candidates.append((ordinal, identity, row["id"], MemoryStore._source(row)))
                candidates.sort(key=lambda candidate: candidate[:3])
                selected = candidates[:limit]
                consumed = 0
                for _, identity, source_id, source in selected:
                    source = self._hydrate(stores, source_id)
                    if source is None:
                        raise _Corrupt("missing canonical source")
                    exact_hash = _exposure(source)
                    if preview and len(source["text"]) > 256:
                        source["text_bytes"] = len(source["text"].encode())
                        source["text"] = source["text"][:256]
                        source["provenance"]["preview"] = True
                        source["exposure_hash"] = exact_hash
                        if "output_budget" not in coverage["limitations"]:
                            coverage["limitations"].append("output_budget")
                    next_positions = dict(positions)
                    next_positions[identity] = next_positions.get(identity, 0) + 1
                    more = len(candidates) > consumed + 1
                    previous_cursor = result["next_cursor"]
                    if more and "result_limit" not in coverage["limitations"]:
                        coverage["limitations"].append("result_limit")
                    result["next_cursor"] = (
                        self._cursor(binding, generation, next_positions) if more else None
                    )
                    result["sources"].append(source)
                    # Size the actual cursor and envelope, reserving only a final
                    # limitation marker should this exact candidate not fit.
                    if preview and len(_json(result).encode()) > MAX_OUTPUT_BYTES - 64:
                        result["sources"].pop()
                        result["next_cursor"] = previous_cursor
                        if "output_budget" not in coverage["limitations"]:
                            coverage["limitations"].append("output_budget")
                        break
                    consumed += 1
                    positions = next_positions
                return result
        except (*_ERRORS, TimeoutError) as exc:
            return self._failure(exc)

    @staticmethod
    def _cursor(binding, generation, positions):
        return base64.urlsafe_b64encode(
            _json({"binding": binding, "generation": generation, "positions": positions}).encode()
        ).decode()

    @staticmethod
    def _hydrate(stores, identity):
        if not isinstance(identity, str) or not re.fullmatch(r"memory:[a-f0-9]{64}", identity):
            raise _Corrupt("invalid canonical identity")
        found = None
        for _, _, conn in stores:
            row = conn.execute(
                "SELECT " + _COLUMNS + " FROM chunks c WHERE c.id=?", (identity,)
            ).fetchone()
            if row is not None:
                source = MemoryStore._source(row)
                if found is not None and any(
                    source[key] != found[key] for key in ("id", "text", "provenance")
                ):
                    raise _Corrupt("canonical identity collision")
                found = source
                reference = UnifiedMemoryStore._metadata_reference(conn, source)
                if reference is not None:
                    found["metadata"] = reference
        return found

    @staticmethod
    def _metadata_reference(conn, source):
        metadata_id = source["provenance"]["caller"].get("metadata_id")
        if (
            metadata_id is None
            or not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='history_occurrences'"
            ).fetchone()
        ):
            return None
        if not isinstance(metadata_id, str) or not re.fullmatch(r"[a-f0-9]{64}", metadata_id):
            raise _Corrupt("metadata identity")
        membership = "EXISTS (SELECT 1 FROM json_each(history_occurrences.ids) WHERE value=?)"
        parameters = [metadata_id, source["id"]]
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='history_occurrence_chunks'"
        ).fetchone():
            membership += (
                " OR EXISTS (SELECT 1 FROM history_occurrence_chunks WHERE "
                "identity=history_occurrences.identity AND chunk_id=?)"
            )
            parameters.append(source["id"])
        row = conn.execute(
            "SELECT substr(metadata_hash,1,65) AS metadata_hash,substr(columns_hash,1,65) AS columns_hash,"
            "length(CAST(metadata_json AS BLOB)) AS metadata_bytes,length(CAST(columns_json AS BLOB)) AS columns_bytes "
            "FROM history_occurrences WHERE identity=? AND (" + membership + ")",
            parameters,
        ).fetchone()
        if row is None or any(
            not isinstance(row[key], str) or not re.fullmatch(r"[a-f0-9]{64}", row[key])
            for key in ("metadata_hash", "columns_hash")
        ):
            raise _Corrupt("missing metadata reference")
        if any(
            type(row[key]) is not int or not 0 <= row[key] <= MAX_STORE_BYTES
            for key in ("metadata_bytes", "columns_bytes")
        ):
            raise _Corrupt("metadata bounds")
        return {"id": metadata_id, **dict(row)}

    def read_sources(self, ids):
        if not isinstance(ids, list) or not 1 <= len(ids) <= 8:
            raise ValueError("ids")
        if any(
            not isinstance(identity, str) or not re.fullmatch(r"memory:[a-f0-9]{64}", identity)
            for identity in ids
        ):
            raise ValueError("ids")
        deadline = time.monotonic() + READ_SECONDS
        try:
            with self._snapshot(deadline) as (stores, coverage, _):
                sources = []
                for identity in ids:
                    found = self._hydrate(stores, identity)
                    if found is None:
                        return {
                            "status": "not_found",
                            "sources": [],
                            "coverage": "indexed_only",
                            "coverage_detail": coverage,
                        }
                    sources.append(found)
                return {
                    "status": "ok",
                    "sources": sources,
                    "coverage": "indexed_only",
                    "coverage_detail": coverage,
                }
        except (*_ERRORS, TimeoutError) as exc:
            return self._failure(exc)

    def page(self, source_id, *, offset=0, limit=2048, expected_hash=None, field="text"):
        if (
            type(offset) is not int
            or offset < 0
            or type(limit) is not int
            or not 1 <= limit <= 2048
        ):
            raise ValueError("page bounds")
        if expected_hash is not None:
            _string(expected_hash, 128, "expected_hash")
        if field not in {"text", "metadata", "columns"}:
            raise ValueError("page field")
        if field != "text":
            return self._metadata_page(source_id, field, offset, limit, expected_hash)
        result = self.read_sources([source_id])
        if result["status"] != "ok":
            return result
        source = result["sources"][0]
        if expected_hash is not None and source["provenance"]["text_hash"] != expected_hash:
            return {"status": "stale"}
        text = source["text"]
        source.update(
            status="ok",
            text_hash=source["provenance"]["text_hash"],
            text=text[offset : offset + limit],
            offset=offset,
            next_offset=min(len(text), offset + limit),
            complete=offset + limit >= len(text),
            coverage="indexed_only",
            coverage_detail=result["coverage_detail"],
        )
        return source

    def _metadata_page(self, source_id, field, offset, limit, expected_hash):
        if not isinstance(source_id, str) or not re.fullmatch(r"memory:[a-f0-9]{64}", source_id):
            raise ValueError("source_id")
        deadline = time.monotonic() + READ_SECONDS
        try:
            with self._snapshot(deadline) as (stores, coverage, _):
                source = self._hydrate(stores, source_id)
                if source is None or "metadata" not in source:
                    return {"status": "not_found"}
                reference = source["metadata"]
                digest = reference[field + "_hash"]
                if expected_hash is not None and expected_hash != digest:
                    return {"status": "stale"}
                column = "metadata_json" if field == "metadata" else "columns_json"
                result = None
                for _, _, conn in stores:
                    if not conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE name='history_occurrences'"
                    ).fetchone():
                        continue
                    row = conn.execute(
                        "SELECT length(CAST("
                        + column
                        + " AS BLOB)) AS size FROM history_occurrences WHERE identity=? AND EXISTS (SELECT 1 FROM chunks c WHERE c.id=?)",
                        (reference["id"], source_id),
                    ).fetchone()
                    if row is None:
                        continue
                    hasher = hashlib.sha256()
                    # Hash the exact registry bytes in bounded pieces before returning any page.
                    for start in range(0, row["size"], 8192):
                        if time.monotonic() >= deadline:
                            raise TimeoutError()
                        block = conn.execute(
                            "SELECT substr(CAST("
                            + column
                            + " AS BLOB),?,8192) FROM history_occurrences WHERE identity=?",
                            (start + 1, reference["id"]),
                        ).fetchone()[0]
                        hasher.update(block)
                    if hasher.hexdigest() != digest:
                        raise _Corrupt("metadata checksum")
                    page = conn.execute(
                        "SELECT substr("
                        + column
                        + ",?,?),length("
                        + column
                        + ") FROM history_occurrences WHERE identity=?",
                        (offset + 1, limit, reference["id"]),
                    ).fetchone()
                    candidate = {
                        "status": "ok",
                        "id": source_id,
                        "metadata_id": reference["id"],
                        "field": field,
                        "text": page[0],
                        "text_hash": digest,
                        "offset": offset,
                        "next_offset": min(page[1], offset + limit),
                        "complete": offset + limit >= page[1],
                        "provenance": source["provenance"],
                        "coverage": "indexed_only",
                        "coverage_detail": coverage,
                    }
                    if result is not None and candidate != result:
                        raise _Corrupt("metadata collision")
                    result = candidate
                if result is None:
                    raise _Corrupt("missing metadata occurrence")
                return result
        except (*_ERRORS, TimeoutError) as exc:
            return self._failure(exc)

    def status(self, *, after=0, limit=16):
        result = MemoryStore(self.palace / ".memory").status(after=after, limit=limit)
        try:
            with self._snapshot(time.monotonic() + READ_SECONDS) as (stores, coverage, generation):
                counts = []
                for identity, _, conn in stores:
                    counts.append(
                        {
                            "store_id": identity,
                            "indexed_chunks": conn.execute(
                                "SELECT count(*) FROM chunks"
                            ).fetchone()[0],
                        }
                    )
                result.update(
                    status="ok" if stores else "unavailable",
                    coverage="indexed_only",
                    coverage_detail=coverage,
                    generation=generation,
                    stores=counts,
                    indexed_chunks=sum(item["indexed_chunks"] for item in counts),
                )
                return result
        except (*_ERRORS, TimeoutError) as exc:
            return self._failure(exc)
