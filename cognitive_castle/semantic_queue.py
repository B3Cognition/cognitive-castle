"""Private durable reference queue. References alone do not prove exact publication.

Only the trusted coordinator may acknowledge a receipt after verifying it against
LanceVectorStore.receipt; model responses are never acknowledgement receipts.
No bodies, token arrays or vectors are accepted or persisted here.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re

from .canonical_records import _string
from .lance_exact_store import LanceExactStore, _StoreError, _identity, _require_supervision
from .semantic_profile import PROFILE_ID, canonical_json, digest

TASK_RSS = 128 * 1024**2
TOTAL_RSS = 192 * 1024**2
SCOPE_LIMITS = (("workspace", 2048), ("wing", 512), ("room", 512))


def validate_hash(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("hash")
    return value


def validate_scope(scope):
    if not isinstance(scope, dict) or set(scope) != {"workspace", "wing", "room"}:
        raise ValueError("full trusted scope required")
    for name, maximum in SCOPE_LIMITS:
        _string(scope[name], maximum, name)
    return scope


def validate_references(references):
    if not isinstance(references, list) or not 1 <= len(references) <= 8:
        raise ValueError("references")
    identities = set()
    for reference in references:
        if not isinstance(reference, dict) or set(reference) != {
            "canonical_id",
            "source_hash",
            "exposure_hash",
            "scope",
        }:
            raise ValueError("reference signature")
        validate_scope(reference["scope"])
        _identity(reference["canonical_id"])
        validate_hash(reference["source_hash"])
        validate_hash(reference["exposure_hash"])
        identities.add(reference["canonical_id"])
    if len(identities) != len(references):
        raise ValueError("duplicate references")
    return references


def validate_receipt(receipt):
    fields = {
        "status",
        "receipt_id",
        "batch_key",
        "profile",
        "input_binding",
        "reference_binding",
        "start_window",
        "total_units",
        "count",
        "next_continuation",
        "unit_ids",
        "vector_digests",
    }
    if (
        not isinstance(receipt, dict)
        or set(receipt) != fields
        or receipt["status"] != "ok"
        or receipt["profile"] != PROFILE_ID
    ):
        raise ValueError("publication receipt signature")
    _string(receipt["batch_key"], 128, "batch key")
    if not isinstance(receipt["receipt_id"], str) or not re.fullmatch(
        r"vector-receipt:[a-f0-9]{64}", receipt["receipt_id"]
    ):
        raise ValueError("receipt identity")
    validate_hash(receipt["input_binding"])
    validate_hash(receipt["reference_binding"])
    start, total, count = (receipt[name] for name in ("start_window", "total_units", "count"))
    if (
        any(type(v) is not int for v in (start, total, count))
        or not 0 <= start < total <= 1048576
        or start % 32
        or count != min(32, total - start)
    ):
        raise ValueError("receipt bounds")
    end = start + count
    expected = {"binding": receipt["input_binding"], "next_window": end} if end < total else None
    if receipt["next_continuation"] != expected:
        raise ValueError("receipt continuation")
    for name in ("unit_ids", "vector_digests"):
        if not isinstance(receipt[name], list) or len(receipt[name]) != count:
            raise ValueError("receipt records")
        for value in receipt[name]:
            validate_hash(value)
    return receipt


class SemanticQueue:
    def __init__(self, directory: Path, *, writable=False):
        if type(writable) is not bool:
            raise ValueError("writable")
        self.generation = Path(directory).absolute()
        self.directory = self.generation / "coordination"
        self.writable = writable

    def _paths(self, create):
        _require_supervision()
        # Queue-only limits are stricter than the shared native store ceiling.
        import psutil
        from .brain_reader_guardian import _group_rss

        task = _group_rss(os.getpgrp())
        if task > TASK_RSS:
            raise _StoreError("worker_memory_limit")
        if task + psutil.Process(os.getppid()).parent().memory_info().rss > TOTAL_RSS:
            raise _StoreError("total_memory_limit")
        for path in (self.generation, *self.generation.parents):
            if path.is_symlink():
                raise _StoreError("unavailable")
        LanceExactStore._private(self.generation, directory=True)
        if not self.directory.exists():
            if not create:
                raise _StoreError("not_initialized")
            self.directory.mkdir(mode=0o700)
        LanceExactStore._private(self.directory, directory=True)
        for path in self.directory.iterdir():
            if path.name not in {"queue.sqlite3", "queue.sqlite3-journal"}:
                raise _StoreError("unavailable")
            LanceExactStore._private(path)

    @contextmanager
    def _connection(self, write=False):
        if write and not self.writable:
            raise _StoreError("unavailable")
        self._paths(write)
        import sqlite3

        path = self.directory / "queue.sqlite3"
        if not write and not path.exists():
            raise _StoreError("not_initialized")
        conn = sqlite3.connect(
            path.as_uri()
            + ("?mode=rw" if path.exists() and write else "?mode=rwc" if write else "?mode=ro"),
            uri=True,
            timeout=0,
        )
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA trusted_schema=OFF")
            conn.execute("PRAGMA cache_size=-512")
            conn.execute("PRAGMA mmap_size=0")
            if write:
                conn.execute("PRAGMA synchronous=FULL")
                conn.execute("BEGIN IMMEDIATE")
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                if version == 0:
                    conn.execute(
                        "CREATE TABLE groups (seq INTEGER PRIMARY KEY, batch_key TEXT UNIQUE NOT NULL, binding TEXT NOT NULL, references_json TEXT NOT NULL, profile TEXT NOT NULL, input_binding TEXT NOT NULL, lane TEXT NOT NULL, state TEXT NOT NULL, position INTEGER NOT NULL, total INTEGER, last_receipt TEXT)"
                    )
                    conn.execute(
                        "CREATE TABLE schedule (id INTEGER PRIMARY KEY CHECK(id=1), new_pages INTEGER NOT NULL)"
                    )
                    conn.execute("INSERT INTO schedule VALUES (1,0)")
                    conn.execute(
                        "CREATE TABLE acknowledgements (batch_key TEXT NOT NULL, start INTEGER NOT NULL, receipt TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(batch_key,start))"
                    )
                    conn.execute("PRAGMA user_version=1")
                elif version not in (1, 2, 3):
                    raise _StoreError("corrupt")
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS intents (seq INTEGER PRIMARY KEY, intent_id TEXT UNIQUE NOT NULL, binding TEXT NOT NULL, intent_json TEXT NOT NULL, complete INTEGER NOT NULL DEFAULT 0)"
                )
                if "intent_cursor" not in {
                    row[1] for row in conn.execute("PRAGMA table_info(schedule)")
                }:
                    conn.execute(
                        "ALTER TABLE schedule ADD COLUMN intent_cursor INTEGER NOT NULL DEFAULT 0"
                    )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS migration_jobs (job_id TEXT PRIMARY KEY, registration TEXT NOT NULL, staging_cursor TEXT NOT NULL, completed_frontier TEXT NOT NULL, pending TEXT, counts TEXT NOT NULL, coverage TEXT NOT NULL, state TEXT NOT NULL, last_ack TEXT, last_refusal TEXT, owner_references INTEGER NOT NULL DEFAULT 0, semantic_pending INTEGER NOT NULL DEFAULT 0)"
                )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS migration_owners (job_id TEXT NOT NULL, owner TEXT NOT NULL, reference TEXT NOT NULL, PRIMARY KEY(job_id,owner))"
                )
                conn.execute("PRAGMA user_version=3")
            elif conn.execute("PRAGMA user_version").fetchone()[0] not in (1, 2, 3):
                raise _StoreError("corrupt")
            yield conn
            if write:
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _group(row):
        return {
            "batch_key": row["batch_key"],
            "references": json.loads(row["references_json"]),
            "profile": row["profile"],
            "input_binding": row["input_binding"],
            "lane": row["lane"],
            "reference_binding": digest(json.loads(row["references_json"])),
            "state": row["state"],
            "position": row["position"],
            "total_units": row["total"],
            "last_receipt": json.loads(row["last_receipt"]) if row["last_receipt"] else None,
        }

    def _run(self, write, operation):
        try:
            _require_supervision()
        except _StoreError as exc:
            return {"status": exc.status}
        import sqlite3

        try:
            with self._connection(write) as conn:
                return operation(conn)
        except _StoreError as exc:
            return {"status": exc.status}
        except sqlite3.OperationalError as exc:
            return {"status": "busy" if "locked" in str(exc) else "corrupt"}
        except (OSError, sqlite3.DatabaseError, ValueError, KeyError, TypeError):
            return {"status": "unavailable"}

    def register(self, batch_key, references, profile, input_binding, lane):
        _string(batch_key, 128, "batch key")
        validate_references(references)
        validate_hash(input_binding)
        if profile != PROFILE_ID or lane not in {"new", "history"}:
            raise ValueError("profile or lane")
        binding = digest([references, profile, input_binding, lane])

        def register(conn):
            old = conn.execute("SELECT * FROM groups WHERE batch_key=?", (batch_key,)).fetchone()
            if old:
                return (
                    {"status": "conflict"}
                    if old["binding"] != binding
                    else {"status": "ok", **self._group(old)}
                )
            conn.execute(
                "INSERT INTO groups(batch_key,binding,references_json,profile,input_binding,lane,state,position) VALUES (?,?,?,?,?,?,'pending',0)",
                (
                    batch_key,
                    binding,
                    canonical_json(references),
                    profile,
                    input_binding,
                    lane,
                ),
            )
            return {
                "status": "ok",
                **self._group(
                    conn.execute("SELECT * FROM groups WHERE batch_key=?", (batch_key,)).fetchone()
                ),
            }

        return self._run(True, register)

    def select(self):
        def select(conn):
            streak = conn.execute("SELECT new_pages FROM schedule WHERE id=1").fetchone()[0]
            lanes = {
                lane: conn.execute(
                    "SELECT * FROM groups WHERE lane=? AND state IN ('pending','inflight') ORDER BY CASE state WHEN 'inflight' THEN 0 ELSE 1 END,seq LIMIT 1",
                    (lane,),
                ).fetchone()
                for lane in ("new", "history")
            }
            lane = (
                "history"
                if lanes["history"] is not None and (streak >= 3 or lanes["new"] is None)
                else "new"
            )
            row = lanes[lane]
            if row is None:
                return {"status": "idle"}
            conn.execute(
                "UPDATE groups SET state='inflight' WHERE batch_key=?", (row["batch_key"],)
            )
            conn.execute(
                "UPDATE schedule SET new_pages=? WHERE id=1",
                (min(streak + 1, 3) if lane == "new" else 0,),
            )
            group = self._group(row)
            group["state"] = "inflight"
            return {"status": "ok", "group": group}

        return self._run(True, select)

    def acknowledge(self, batch_key, receipt):
        _string(batch_key, 128, "batch key")
        validate_receipt(receipt)

        def acknowledge(conn):
            row = conn.execute("SELECT * FROM groups WHERE batch_key=?", (batch_key,)).fetchone()
            if row is None:
                return {"status": "not_found"}
            old = conn.execute(
                "SELECT receipt,result FROM acknowledgements WHERE batch_key=? AND start=?",
                (batch_key, receipt["start_window"]),
            ).fetchone()
            encoded = canonical_json(receipt)
            if old:
                return (
                    json.loads(old["result"])
                    if old["receipt"] == encoded
                    else {"status": "conflict"}
                )
            if (
                receipt["batch_key"] != batch_key
                or receipt["profile"] != row["profile"]
                or receipt["input_binding"] != row["input_binding"]
                or receipt["reference_binding"] != digest(json.loads(row["references_json"]))
                or receipt["start_window"] != row["position"]
                or row["state"] not in {"pending", "inflight"}
                or row["total"] not in (None, receipt["total_units"])
            ):
                return {"status": "conflict"}
            position = receipt["start_window"] + receipt["count"]
            state = "complete" if position == receipt["total_units"] else "pending"
            conn.execute(
                "UPDATE groups SET state=?,position=?,total=?,last_receipt=? WHERE batch_key=?",
                (state, position, receipt["total_units"], encoded, batch_key),
            )
            result = {
                "status": "ok",
                "state": state,
                "position": position,
                "total_units": receipt["total_units"],
                "receipt_id": receipt["receipt_id"],
            }
            conn.execute(
                "INSERT INTO acknowledgements VALUES (?,?,?,?)",
                (batch_key, receipt["start_window"], encoded, canonical_json(result)),
            )
            return result

        return self._run(True, acknowledge)

    def retry(self, batch_key, *, refused=False):
        _string(batch_key, 128, "batch key")
        if type(refused) is not bool:
            raise ValueError("refused")

        def retry(conn):
            row = conn.execute("SELECT * FROM groups WHERE batch_key=?", (batch_key,)).fetchone()
            if row is None:
                return {"status": "not_found"}
            if row["state"] != "complete":
                conn.execute(
                    "UPDATE groups SET state=? WHERE batch_key=?",
                    ("refused" if refused else "pending", batch_key),
                )
            return {
                "status": "ok",
                **self._group(
                    conn.execute("SELECT * FROM groups WHERE batch_key=?", (batch_key,)).fetchone()
                ),
            }

        return self._run(True, retry)

    def status(self):
        def status(conn):
            counts = {name: 0 for name in ("pending", "inflight", "complete", "refused")}
            for row in conn.execute("SELECT state,count(*) AS n FROM groups GROUP BY state"):
                counts[row["state"]] = row["n"]
            rows = conn.execute("SELECT * FROM groups ORDER BY seq LIMIT 64").fetchall()
            return {
                "status": "ok",
                "counts": counts,
                "groups": [
                    {
                        "batch_key": row["batch_key"],
                        "lane": row["lane"],
                        "state": row["state"],
                        "position": row["position"],
                        "total_units": row["total"],
                        "receipt_id": json.loads(row["last_receipt"])["receipt_id"]
                        if row["last_receipt"]
                        else None,
                    }
                    for row in rows
                ],
                "positions_truncated": sum(counts.values()) > len(rows),
                "coverage_complete": False,
            }

        return self._run(False, status)

    def intent_prepare(self, intent):
        from .semantic_intents import validate_intent

        validate_intent(intent)
        encoded = canonical_json(intent)

        def prepare(conn):
            old = conn.execute(
                "SELECT binding FROM intents WHERE intent_id=?", (intent["intent_id"],)
            ).fetchone()
            if old:
                return {"status": "ok" if old["binding"] == digest(intent) else "conflict"}
            conn.execute(
                "INSERT INTO intents(intent_id,binding,intent_json) VALUES (?,?,?)",
                (intent["intent_id"], digest(intent), encoded),
            )
            return {"status": "ok"}

        return self._run(True, prepare)

    def intents(self):
        def pending(conn):
            cursor = conn.execute("SELECT intent_cursor FROM schedule WHERE id=1").fetchone()[0]
            rows = conn.execute(
                "SELECT seq,intent_json FROM intents WHERE complete=0 ORDER BY CASE WHEN seq>? THEN 0 ELSE 1 END,seq LIMIT 2",
                (cursor,),
            ).fetchall()
            if rows:
                conn.execute("UPDATE schedule SET intent_cursor=? WHERE id=1", (rows[-1]["seq"],))
            return {"status": "ok", "intents": [json.loads(row["intent_json"]) for row in rows]}

        return self._run(True, pending)

    def intent_complete(self, intent_id, binding):
        validate_hash(intent_id)
        validate_hash(binding)

        def complete(conn):
            row = conn.execute("SELECT * FROM intents WHERE intent_id=?", (intent_id,)).fetchone()
            if row is None:
                return {"status": "not_found"}
            if row["binding"] != binding:
                return {"status": "conflict"}
            intent = json.loads(row["intent_json"])
            from .semantic_intents import validate_intent

            validate_intent(intent)
            for group in intent["groups"]:
                group_binding = digest(
                    [group[key] for key in ("references", "profile", "input_binding", "lane")]
                )
                old = conn.execute(
                    "SELECT binding FROM groups WHERE batch_key=?", (group["batch_key"],)
                ).fetchone()
                if old and old[0] != group_binding:
                    raise _StoreError("conflict")
                conn.execute(
                    "INSERT OR IGNORE INTO groups(batch_key,binding,references_json,profile,input_binding,lane,state,position) VALUES (?,?,?,?,?,?, 'pending',0)",
                    (
                        group["batch_key"],
                        group_binding,
                        canonical_json(group["references"]),
                        group["profile"],
                        group["input_binding"],
                        group["lane"],
                    ),
                )
            conn.execute("UPDATE intents SET complete=1 WHERE intent_id=?", (intent_id,))
            return {"status": "ok"}

        return self._run(True, complete)

    @staticmethod
    def _migration_row(conn, job_id):
        if conn.execute("PRAGMA user_version").fetchone()[0] < 3:
            raise _StoreError("not_found")
        row = conn.execute("SELECT * FROM migration_jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            raise _StoreError("not_found")
        return row

    @staticmethod
    def _migration_state(row):
        from . import migration_codec as codec

        reg = codec.validate_registration(json.loads(row["registration"]))
        staging = codec.cursor(json.loads(row["staging_cursor"]), reg)
        frontier = codec.cursor(json.loads(row["completed_frontier"]), reg)
        pending = json.loads(row["pending"]) if row["pending"] else None
        if pending:
            codec.validate_interval(pending, reg)
            if pending["cursor_before"] != staging:
                raise _StoreError("corrupt")
        return dict(
            status="ok",
            registration=reg,
            staging_cursor=staging,
            completed_frontier=frontier,
            pending=pending,
            counts=codec.counts(json.loads(row["counts"])),
            coverage=row["coverage"],
            state=row["state"],
            last_ack=json.loads(row["last_ack"]) if row["last_ack"] else None,
            last_refusal=json.loads(row["last_refusal"]) if row["last_refusal"] else None,
            owner_references=row["owner_references"],
            semantic_pending=row["semantic_pending"],
        )

    def migration_open(self, registration):
        from . import migration_codec as codec
        from .sqlite_export_codec import empty_counts, initial_cursor

        try:
            codec.validate_registration(registration)
        except codec.RegistrationConflict:
            return {"status": "conflict"}
        if registration["destination"] != str(self.generation):
            return {"status": "conflict"}
        encoded = canonical_json(registration)

        def operation(conn):
            old = conn.execute(
                "SELECT * FROM migration_jobs WHERE job_id=?", (registration["job_id"],)
            ).fetchone()
            if old and old["registration"] != encoded:
                return {"status": "conflict"}
            if old is None:
                before = canonical_json(
                    initial_cursor(
                        registration["source_binding"], registration["descriptor"]["store_id"]
                    )
                )
                conn.execute(
                    "INSERT INTO migration_jobs(job_id,registration,staging_cursor,completed_frontier,counts,coverage,state) VALUES (?,?,?,?,?,'incomplete','active')",
                    (
                        registration["job_id"],
                        encoded,
                        before,
                        before,
                        canonical_json(empty_counts()),
                    ),
                )
            return self._migration_state(self._migration_row(conn, registration["job_id"]))

        return self._run(True, operation)

    def migration_state(self, job_id):
        validate_hash(job_id)
        return self._run(
            False, lambda conn: self._migration_state(self._migration_row(conn, job_id))
        )

    def migration_prepare(self, job_id, expected_cursor, intent):
        from . import migration_codec as codec

        validate_hash(job_id)

        def operation(conn):
            row = self._migration_row(conn, job_id)
            state = self._migration_state(row)
            codec.cursor(expected_cursor, state["registration"])
            codec.validate_interval(intent, state["registration"])
            if (
                expected_cursor != state["staging_cursor"]
                or intent["cursor_before"] != expected_cursor
                or state["state"] == "snapshot_export_exhausted"
            ):
                return {"status": "conflict"}
            if state["pending"] is not None and state["pending"] != intent:
                return {"status": "conflict"}
            conn.execute(
                "UPDATE migration_jobs SET pending=?,state='active',last_refusal=NULL WHERE job_id=?",
                (canonical_json(intent), job_id),
            )
            return {"status": "ok", "intent_id": intent["intent_id"]}

        return self._run(True, operation)

    def migration_refuse(self, job_id, expected_cursor, refusal):
        from . import migration_codec as codec

        validate_hash(job_id)
        if not isinstance(refusal, dict) or refusal.keys() != {
            "status",
            "reason",
            "phase",
            "refused_operation",
            "refused_field",
            "orphans",
        }:
            raise ValueError("migration refusal")
        for name in ("status", "reason", "phase", "refused_operation", "refused_field"):
            if refusal[name] is not None:
                _string(refusal[name], 128, name)
        if (
            refusal["status"] == "ok"
            or type(refusal["orphans"]) is not int
            or refusal["orphans"] not in (0, 1)
        ):
            raise ValueError("migration refusal status")
        codec.bounded(refusal)

        def operation(conn):
            state = self._migration_state(self._migration_row(conn, job_id))
            codec.cursor(expected_cursor, state["registration"])
            if (
                expected_cursor != state["staging_cursor"]
                or state["state"] == "snapshot_export_exhausted"
            ):
                return {"status": "conflict"}
            counters = state["counts"]
            counters["orphans"] = max(counters["orphans"], refusal["orphans"])
            conn.execute(
                "UPDATE migration_jobs SET state='refused',last_refusal=?,counts=?,coverage='incomplete' WHERE job_id=?",
                (canonical_json(refusal), canonical_json(counters), job_id),
            )
            return {"status": "ok"}

        return self._run(True, operation)

    def migration_ack(self, job_id, intent_id, verified_summary):
        """Private ACK trusts current-tick coordinator proof, never queue rows."""
        from . import migration_codec as codec
        from .sqlite_export_codec import initial_cursor

        validate_hash(job_id)
        if intent_id is not None:
            validate_hash(intent_id)
        codec.bounded(verified_summary)

        def operation(conn):
            state = self._migration_state(self._migration_row(conn, job_id))
            summary_hash = codec.hashed(verified_summary)
            old = state["last_ack"]
            if old and old["intent_id"] == intent_id and old["summary_hash"] == summary_hash:
                return old["result"]
            intent = state["pending"]
            if intent_id is None:
                reg = state["registration"]
                done = initial_cursor(reg["source_binding"], reg["descriptor"]["store_id"])
                done["phase"] = "done"
                if (
                    intent is not None
                    or state["staging_cursor"]["owner"] is not None
                    or state["counts"]["orphans"]
                    or state["staging_cursor"] != state["completed_frontier"]
                    or not isinstance(verified_summary, dict)
                    or verified_summary
                    != dict(
                        state="snapshot_export_exhausted",
                        cursor_before=state["staging_cursor"],
                        cursor_after=done,
                        coverage=verified_summary.get("coverage"),
                    )
                    or verified_summary["coverage"] not in {"indexed-only", "incomplete"}
                    or state["state"] == "snapshot_export_exhausted"
                ):
                    return {"status": "conflict"}
                after, frontier, terminal = (
                    done,
                    state["completed_frontier"],
                    "snapshot_export_exhausted",
                )
                coverage = verified_summary["coverage"]
                counters, references, pending_semantic = state["counts"], 0, 0
            else:
                if (
                    intent is None
                    or intent["intent_id"] != intent_id
                    or intent["cursor_before"] != state["staging_cursor"]
                ):
                    return {"status": "conflict"}
                codec.validate_verified(verified_summary, intent)
                after = intent["cursor_after"]
                frontier = after if intent["owners"] else state["completed_frontier"]
                terminal, coverage = "active", intent["coverage"]
                counters = {
                    name: state["counts"][name] + value for name, value in intent["counts"].items()
                }
                codec.counts(counters)
                references, pending_semantic = len(intent["owners"]), 0
                for owner, version in zip(intent["owners"], verified_summary["owner_versions"]):
                    reference = dict(
                        job_id=job_id,
                        source_binding=intent["source_binding"],
                        destination=intent["destination"],
                        **owner,
                        proof_version=codec.PROOF_VERSION,
                        dataset_version=version,
                    )
                    if conn.execute(
                        "SELECT 1 FROM migration_owners WHERE job_id=? AND owner=?",
                        (job_id, owner["owner"]),
                    ).fetchone():
                        raise _StoreError("conflict")
                    conn.execute(
                        "INSERT INTO migration_owners VALUES (?,?,?)",
                        (job_id, owner["owner"], canonical_json(reference)),
                    )
                    pending_semantic += int(owner["semantic_disposition"] == "pending")
            result = dict(
                status="ok",
                job_id=job_id,
                intent_id=intent_id,
                state=terminal,
                staging_cursor=after,
                completed_frontier=frontier,
                counts=counters,
            )
            last_ack = dict(intent_id=intent_id, summary_hash=summary_hash, result=result)
            conn.execute(
                "UPDATE migration_jobs SET staging_cursor=?,completed_frontier=?,pending=NULL,counts=?,coverage=?,state=?,last_ack=?,last_refusal=NULL,owner_references=owner_references+?,semantic_pending=semantic_pending+? WHERE job_id=?",
                (
                    canonical_json(after),
                    canonical_json(frontier),
                    canonical_json(counters),
                    coverage,
                    terminal,
                    canonical_json(last_ack),
                    references,
                    pending_semantic,
                    job_id,
                ),
            )
            return result

        return self._run(True, operation)
