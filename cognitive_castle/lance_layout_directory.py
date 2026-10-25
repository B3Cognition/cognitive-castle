"""Derived placement metadata on the queue's existing transaction.

No method commits, opens a native dataset, creates a partition or proves global
absence. Exact readers use the separate read-only path below under their exact
supervisor, without invoking the queue's smaller memory profile.
"""

from contextlib import contextmanager
import json
import os
from pathlib import Path

from . import lance_layout_codec as codec
from . import migration_codec as migration
from . import bulk_exact_codec as bulk
from .lance_exact_store import LanceExactStore, _StoreError, _require_supervision
from .semantic_profile import canonical_json

DDL = {
    "layout_jobs": "CREATE TABLE layout_jobs (job_id TEXT PRIMARY KEY, envelope TEXT NOT NULL)",
    "layout_partitions": "CREATE TABLE layout_partitions (partition_id INTEGER PRIMARY KEY, envelope_hash TEXT NOT NULL, reservation TEXT NOT NULL)",
    "layout_homes": "CREATE TABLE layout_homes (owner TEXT PRIMARY KEY, job_id TEXT NOT NULL, plan TEXT NOT NULL, plan_hash TEXT UNIQUE NOT NULL, partition_id INTEGER NOT NULL, published INTEGER NOT NULL CHECK(published IN (0,1)))",
    "layout_routes": "CREATE TABLE layout_routes (id TEXT PRIMARY KEY, kind TEXT NOT NULL, row_hash TEXT, partition_id INTEGER NOT NULL, gate TEXT NOT NULL, intent_id TEXT NOT NULL, job_id TEXT NOT NULL, version INTEGER, receipt TEXT, state TEXT NOT NULL CHECK(state IN ('reserved','staged','published')))",
}
INDEXES = {
    "layout_homes_job_gate": "CREATE INDEX layout_homes_job_gate ON layout_homes(job_id,published)",
    "layout_routes_job_state": "CREATE INDEX layout_routes_job_state ON layout_routes(job_id,state)",
}
BASE_TABLES = {
    "groups",
    "schedule",
    "acknowledgements",
    "intents",
    "migration_jobs",
    "migration_owners",
}


def require_attachment_column(conn):
    size = conn.execute(
        "SELECT length(CAST(sql AS BLOB)) FROM sqlite_master WHERE type='table' AND name='migration_jobs'"
    ).fetchone()
    if size is None or size[0] is None or size[0] > 4096:
        raise _StoreError("unavailable")
    expected = (
        (0, "job_id", "TEXT", 0, None, 1),
        (1, "registration", "TEXT", 1, None, 0),
        (2, "staging_cursor", "TEXT", 1, None, 0),
        (3, "completed_frontier", "TEXT", 1, None, 0),
        (4, "pending", "TEXT", 0, None, 0),
        (5, "counts", "TEXT", 1, None, 0),
        (6, "coverage", "TEXT", 1, None, 0),
        (7, "state", "TEXT", 1, None, 0),
        (8, "last_ack", "TEXT", 0, None, 0),
        (9, "last_refusal", "TEXT", 0, None, 0),
        (10, "owner_references", "INTEGER", 1, "0", 0),
        (11, "semantic_pending", "INTEGER", 1, "0", 0),
        (12, "layout_attachment", "TEXT", 0, None, 0),
    )
    columns = conn.execute("PRAGMA table_info(migration_jobs)").fetchmany(14)
    if [tuple(row) for row in columns] != list(expected):
        raise _StoreError("unavailable")
    sizes = conn.execute(
        "SELECT length(CAST(name AS BLOB)) FROM sqlite_master WHERE type='index' AND tbl_name='migration_jobs' LIMIT 2"
    ).fetchall()
    if len(sizes) != 1 or sizes[0][0] > 128:
        raise _StoreError("unavailable")
    indexes = conn.execute("PRAGMA index_list(migration_jobs)").fetchmany(2)
    if [tuple(row) for row in indexes] != [(0, "sqlite_autoindex_migration_jobs_1", 1, "pk", 0)]:
        raise _StoreError("unavailable")
    keys = conn.execute("PRAGMA index_xinfo(sqlite_autoindex_migration_jobs_1)").fetchmany(3)
    if [tuple(row) for row in keys] != [
        (0, 0, "job_id", 0, "BINARY", 1),
        (1, -1, None, 0, "BINARY", 0),
    ]:
        raise _StoreError("unavailable")


def validate_first_bind(row, reg):
    before = migration.initial_source_cursor(reg)
    if (
        row["pending"] is not None
        or json.loads(row["staging_cursor"]) != before
        or json.loads(row["completed_frontier"]) != before
        or migration.counts(json.loads(row["counts"])) != migration.empty_counts()
        or row["owner_references"] != 0
        or row["semantic_pending"] != 0
        or row["last_ack"] is not None
        or row["last_refusal"] is not None
        or row["state"] != "active"
        or row["coverage"] != "incomplete"
    ):
        _conflict()


def _conflict():
    # A normal conflict return would COMMIT earlier changes in SemanticQueue.
    raise _StoreError("conflict")


def _metadata(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > migration.MAX_METADATA:
        raise _StoreError("unavailable")
    return json.loads(text)


def _ids(ids):
    if not isinstance(ids, list) or not 1 <= len(ids) <= 256:
        raise ValueError("route request bound")
    for identity in ids:
        bulk.identity(
            identity,
            "memory" if isinstance(identity, str) and identity.startswith("memory:") else "receipt",
        )
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate route request")
    migration.bounded(ids)


class LayoutDirectory:
    def __init__(self, conn):
        self.conn = conn

    def _schema(self):
        lengths = self.conn.execute(
            "SELECT length(name),length(type),length(sql) FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' LIMIT 14"
        ).fetchall()
        if len(lengths) != len(BASE_TABLES) + len(DDL) + len(INDEXES) or any(
            a is None or a > 64 or b is None or b > 16 or c is None or c > 4096
            for a, b, c in lengths
        ):
            raise _StoreError("unavailable")
        rows = self.conn.execute(
            "SELECT name,type,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' LIMIT 14"
        ).fetchall()
        if len(rows) != len(BASE_TABLES) + len(DDL) + len(INDEXES):
            raise _StoreError("unavailable")
        seen = set()
        for row in rows:
            name, kind, sql = row
            expected_kind = "index" if name in INDEXES else "table"
            if (
                kind != expected_kind
                or name not in BASE_TABLES | DDL.keys() | INDEXES.keys()
                or name in seen
            ):
                raise _StoreError("unavailable")
            if name in DDL and sql != DDL[name]:
                raise _StoreError("unavailable")
            if name in INDEXES and sql != INDEXES[name]:
                raise _StoreError("unavailable")
            seen.add(name)
        if self.conn.execute("PRAGMA user_version").fetchone()[0] != 4:
            raise _StoreError("unavailable")
        require_attachment_column(self.conn)

    def attachment(self, job_id):
        """Recognize attachment before any v1 pending decode or replay shortcut."""
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        exists = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='layout_jobs'"
        ).fetchone()
        if version < 4:
            if exists:
                raise _StoreError("unavailable")
            return None
        if version != 4:
            raise _StoreError("unavailable")
        require_attachment_column(self.conn)
        marker_row = self.conn.execute(
            "SELECT length(CAST(layout_attachment AS BLOB)),CASE WHEN typeof(layout_attachment)='text' AND length(CAST(layout_attachment AS BLOB))<=512 THEN layout_attachment ELSE NULL END FROM migration_jobs WHERE job_id=?",
            (job_id,),
        ).fetchone()
        if marker_row is not None and marker_row[0] is not None and marker_row[0] > 512:
            raise _StoreError("unavailable")
        if marker_row is not None and marker_row[0] is not None and marker_row[1] is None:
            raise _StoreError("unavailable")
        if marker_row is None or marker_row[1] is None:
            if (
                exists
                and self.conn.execute(
                    "SELECT 1 FROM layout_jobs WHERE job_id=?", (job_id,)
                ).fetchone()
            ):
                raise _StoreError("unavailable")
            return None
        if marker_row[0] > 512 or not exists:
            raise _StoreError("unavailable")
        marker = codec.validate_attachment(json.loads(marker_row[1]))
        self._schema()
        row = self.conn.execute(
            "SELECT CASE WHEN typeof(envelope)='text' AND length(CAST(envelope AS BLOB))<=196608 THEN envelope ELSE NULL END FROM layout_jobs WHERE job_id=?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise _StoreError("unavailable")
        envelope = codec.validate_envelope(_metadata(row[0]))
        if marker["envelope_hash"] != migration.hashed(envelope):
            raise _StoreError("unavailable")
        self._identity(envelope)
        return migration.bounded(dict(**marker, envelope=envelope))

    def _identity(self, envelope):
        databases = self.conn.execute("PRAGMA database_list").fetchmany(2)
        if len(databases) != 1 or databases[0][1] != "main":
            raise _StoreError("unavailable")
        path = Path(databases[0][2])
        generation = Path(envelope["generation"]["path"])
        if path != generation / "coordination" / "queue.sqlite3":
            _conflict()
        _metadata_paths(generation)
        info = generation.stat()
        if (info.st_dev, info.st_ino) != (
            envelope["generation"]["device"],
            envelope["generation"]["inode"],
        ):
            _conflict()

    def _state(self, job_id):
        from .semantic_queue import SemanticQueue

        bulk.sha(job_id)
        attachment = self.attachment(job_id)
        if attachment is None:
            raise _StoreError("unavailable")
        row = SemanticQueue._migration_row(self.conn, job_id)
        state = SemanticQueue._migration_state(row, attachment)
        if state["registration"]["destination"] != attachment["envelope"]["generation"]["path"]:
            _conflict()
        return state

    def bind(self, job_id, plans, envelope):
        from .semantic_queue import SemanticQueue

        bulk.sha(job_id)
        codec.validate_envelope(envelope)
        if not isinstance(plans, list) or not 1 <= len(plans) <= codec.MAX_PLANS:
            raise ValueError("owner plan bound")
        migration.bounded(dict(job_id=job_id, plans=plans, envelope=envelope))
        row = SemanticQueue._migration_row(self.conn, job_id)
        reg = migration.validate_registration(json.loads(row["registration"]))
        self._identity(envelope)
        if reg["destination"] != envelope["generation"]["path"]:
            _conflict()
        for plan in plans:
            codec.validate_owner_plan(plan, reg)
        if len({p["owner"] for p in plans}) != len(plans):
            raise ValueError("duplicate owner plan")
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version == 4:
            require_attachment_column(self.conn)
            attached = self.attachment(job_id)
        else:
            attached = None
        if attached is None:
            validate_first_bind(row, reg)
        if version == 3:
            self.conn.execute("ALTER TABLE migration_jobs ADD COLUMN layout_attachment TEXT")
            self.conn.execute("PRAGMA user_version=4")
        elif version != 4:
            raise _StoreError("unavailable")
        require_attachment_column(self.conn)
        # Only the one initial bind creates derived tables, inside this transaction.
        present = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE name LIKE 'layout_%' LIMIT 7"
        ).fetchall()
        if present and {r[0] for r in present} != DDL.keys() | INDEXES.keys():
            raise _StoreError("unavailable")
        if not present:
            if row["pending"] is not None or json.loads(row["staging_cursor"])["owner"] is not None:
                _conflict()
            for sql in (*DDL.values(), *INDEXES.values()):
                self.conn.execute(sql)
        self._schema()
        previous = self.conn.execute(
            "SELECT CASE WHEN typeof(envelope)='text' AND length(CAST(envelope AS BLOB))<=196608 THEN envelope ELSE NULL END FROM layout_jobs WHERE job_id=?",
            (job_id,),
        ).fetchone()
        encoded = canonical_json(envelope)
        if previous and previous[0] != encoded:
            _conflict()
        # One immutable generation envelope, including across jobs.
        other = self.conn.execute(
            "SELECT CASE WHEN typeof(envelope)='text' AND length(CAST(envelope AS BLOB))<=196608 THEN envelope ELSE NULL END FROM layout_jobs LIMIT 1"
        ).fetchone()
        if other and other[0] != encoded:
            _conflict()
        if previous is None and row["pending"] is not None:
            _conflict()
        updates, homes, targets = self._placement(job_id, plans, envelope)
        response = migration.bounded(
            dict(
                status="ok",
                layout=dict(
                    format=codec.ATTACHMENT,
                    envelope_hash=migration.hashed(envelope),
                    envelope=envelope,
                ),
                targets=targets,
            )
        )
        if attached is None:
            pristine = SemanticQueue._migration_state(row)
            migration.bounded({**pristine, "layout": response["layout"]})
        # Everything, including the complete response, was validated before writes.
        if previous is None:
            self.conn.execute("INSERT INTO layout_jobs VALUES (?,?)", (job_id, encoded))
            marker = codec.validate_attachment(
                dict(format=codec.ATTACHMENT, envelope_hash=migration.hashed(envelope))
            )
            self.conn.execute(
                "UPDATE migration_jobs SET layout_attachment=? WHERE job_id=?",
                (canonical_json(marker), job_id),
            )
        for pid, reservation in updates.items():
            self.conn.execute(
                "INSERT INTO layout_partitions VALUES (?,?,?) ON CONFLICT(partition_id) DO UPDATE SET reservation=excluded.reservation",
                (pid, migration.hashed(envelope), canonical_json(reservation)),
            )
        for plan, pid in homes:
            self.conn.execute(
                "INSERT INTO layout_homes VALUES (?,?,?,?,?,0)",
                (plan["owner"], job_id, canonical_json(plan), migration.hashed(plan), pid),
            )
        return response

    def _placement(self, job_id, plans, envelope):
        last = self.conn.execute(
            "SELECT partition_id,CASE WHEN length(envelope_hash)=64 THEN envelope_hash ELSE NULL END,CASE WHEN typeof(reservation)='text' AND length(CAST(reservation AS BLOB))<=4096 THEN reservation ELSE NULL END FROM layout_partitions ORDER BY partition_id DESC LIMIT 1"
        ).fetchone()
        partition = last[0] if last else 0
        usage = self._partition(partition, envelope) if last else dict.fromkeys(codec.EXPANSION, 0)
        if last and last[1] != migration.hashed(envelope):
            _conflict()
        if usage.keys() != set(codec.EXPANSION):
            raise _StoreError("corrupt")
        for value in usage.values():
            bulk.integer(value)
        if (
            partition >= envelope["max_partitions"]
            or partition < 0
            or any(usage[k] > envelope["limits"][k] for k in codec.EXPANSION)
        ):
            raise _StoreError("unavailable")
        updates, homes, targets = {}, [], []
        for plan in plans:
            old = self.conn.execute(
                "SELECT job_id,CASE WHEN typeof(plan)='text' AND length(CAST(plan AS BLOB))<=196608 THEN plan ELSE NULL END,partition_id,CASE WHEN length(CAST(plan_hash AS BLOB))=64 THEN plan_hash ELSE NULL END FROM layout_homes WHERE owner=? AND length(CAST(job_id AS BLOB))=64 AND typeof(partition_id)='integer'",
                (plan["owner"],),
            ).fetchone()
            if old:
                if (
                    old[0] != job_id
                    or old[1] != canonical_json(plan)
                    or old[3] != migration.hashed(plan)
                ):
                    _conflict()
                reservation = self._partition(old[2], envelope)
                if any(reservation[k] < plan["expansion"][k] for k in codec.EXPANSION):
                    raise _StoreError("unavailable")
                targets.append(codec.target(envelope, old[2], [plan]))
                continue
            if any(plan["expansion"][k] > envelope["limits"][k] for k in codec.EXPANSION):
                _conflict()
            total = {k: usage[k] + plan["expansion"][k] for k in codec.EXPANSION}
            if any(total[k] > envelope["limits"][k] for k in codec.EXPANSION):
                partition += 1
                total = dict(plan["expansion"])
            if partition >= envelope["max_partitions"]:
                _conflict()
            usage = total
            updates[partition] = total
            homes.append((plan, partition))
            targets.append(codec.target(envelope, partition, [plan]))
        return updates, homes, targets

    def _target(self, state, intent):
        target = codec.validate_target(intent["target"])
        envelope = state["layout"]["envelope"]
        if (
            target["generation"] != envelope["generation"]
            or target["envelope_hash"] != migration.hashed(envelope)
            or target["partition_id"] >= envelope["max_partitions"]
        ):
            _conflict()
        # Task2 handles one owner per frame. Task4 adds a checked ordered prefix.
        if len(target["owner_plan_hashes"]) != 1:
            _conflict()
        home = self.conn.execute(
            "SELECT owner,job_id,CASE WHEN typeof(plan)='text' AND length(CAST(plan AS BLOB))<=196608 THEN plan ELSE NULL END,partition_id,published FROM layout_homes WHERE plan_hash=? AND length(CAST(owner AS BLOB))=72 AND length(CAST(job_id AS BLOB))=64 AND typeof(partition_id)='integer' AND typeof(published)='integer' AND published IN (0,1)",
            (target["owner_plan_hashes"][0],),
        ).fetchone()
        if (
            home is None
            or home[1] != state["registration"]["job_id"]
            or home[3] != target["partition_id"]
            or home[4]
        ):
            _conflict()
        plan = codec.validate_owner_plan(_metadata(home[2]), state["registration"])
        if migration.hashed(plan) != target["owner_plan_hashes"][0] or plan["owner"] != home[0]:
            raise _StoreError("unavailable")
        reservation = self._partition(home[3], envelope)
        if any(reservation[k] < plan["expansion"][k] for k in codec.EXPANSION):
            raise _StoreError("unavailable")
        if plan["source_phase"] != intent["phase"]:
            _conflict()
        if any(r["gate"] != home[0] for r in intent["routes"]):
            _conflict()
        if intent["owners"] and {k: plan[k] for k in migration.OWNER_FIELDS} != intent["owners"][0]:
            _conflict()
        owner_key = intent["cursor_after"]["owner"]
        if owner_key is not None and owner_key != plan["owner_key"]:
            _conflict()
        return home

    def _partition(self, partition_id, envelope):
        bulk.integer(partition_id)
        if partition_id >= envelope["max_partitions"]:
            raise _StoreError("unavailable")
        row = self.conn.execute(
            "SELECT CASE WHEN typeof(envelope_hash)='text' AND length(CAST(envelope_hash AS BLOB))=64 THEN envelope_hash ELSE NULL END,CASE WHEN typeof(reservation)='text' AND length(CAST(reservation AS BLOB))<=4096 THEN reservation ELSE NULL END FROM layout_partitions WHERE partition_id=?",
            (partition_id,),
        ).fetchone()
        if row is None or row[0] != migration.hashed(envelope):
            raise _StoreError("unavailable")
        reservation = codec._expansion(_metadata(row[1]))
        if any(reservation[k] > envelope["limits"][k] for k in codec.EXPANSION):
            raise _StoreError("unavailable")
        return reservation

    def prepare(self, job_id, expected_cursor, intent):
        migration.bounded(dict(job_id=job_id, expected_cursor=expected_cursor, intent=intent))
        state = self._state(job_id)
        migration.cursor(expected_cursor, state["registration"])
        codec.validate_layout_intent(intent, state["registration"])
        if (
            expected_cursor != state["staging_cursor"]
            or intent["cursor_before"] != expected_cursor
            or state["state"] == "snapshot_export_exhausted"
        ):
            _conflict()
        replay = state["pending"] is not None
        if replay:
            if state["pending"] != intent:
                _conflict()
        self._target(state, intent)
        codec.prospective_ack(intent)
        migration.bounded({**state, "pending": intent, "state": "active", "last_refusal": None})
        inserts = []
        authorities = {}
        for candidate in intent["routes"]:
            old = self._route_row(candidate["id"])
            if old:
                if old["state"] == "reserved":
                    if (
                        not replay
                        or old["intent_id"] != intent["intent_id"]
                        or old["job_id"] != job_id
                        or any(old[k] != candidate[k] for k in ("kind", "row_hash", "gate"))
                        or old["partition_id"] != intent["target"]["partition_id"]
                        or old["version"] is not None
                        or old["receipt"] is not None
                    ):
                        _conflict()
                    continue
                visible = self._route(old, authorities)
                if old["kind"] != candidate["kind"]:
                    _conflict()
                if visible is None or (
                    visible["state"] != "published" and old["gate"] != candidate["gate"]
                ):
                    _conflict()
                if candidate["kind"] != "bulk_record" and (
                    old["row_hash"] != candidate["row_hash"] or old["gate"] != candidate["gate"]
                ):
                    _conflict()
            else:
                inserts.append(candidate)
        if replay:
            if inserts:
                raise _StoreError("unavailable")
            return dict(status="ok", intent_id=intent["intent_id"])
        for candidate in inserts:
            self.conn.execute(
                "INSERT INTO layout_routes VALUES (?,?,?,?,?,?,?,NULL,NULL,'reserved')",
                (
                    candidate["id"],
                    candidate["kind"],
                    candidate["row_hash"],
                    intent["target"]["partition_id"],
                    candidate["gate"],
                    intent["intent_id"],
                    job_id,
                ),
            )
        self.conn.execute(
            "UPDATE migration_jobs SET pending=?,state='active',last_refusal=NULL WHERE job_id=?",
            (canonical_json(intent), job_id),
        )
        return dict(status="ok", intent_id=intent["intent_id"])

    def _route_row(self, identity):
        # BLOB lengths bound Python allocations before any JSON/codec validation.
        return self.conn.execute(
            "SELECT * FROM layout_routes WHERE id=? AND typeof(id)='text' AND length(CAST(id AS BLOB))<=72 AND typeof(kind)='text' AND length(CAST(kind AS BLOB))<=16 AND (row_hash IS NULL OR (typeof(row_hash)='text' AND length(CAST(row_hash AS BLOB))=64)) AND typeof(gate)='text' AND length(CAST(gate AS BLOB))=72 AND typeof(intent_id)='text' AND length(CAST(intent_id AS BLOB))=64 AND typeof(job_id)='text' AND length(CAST(job_id AS BLOB))=64 AND (receipt IS NULL OR (typeof(receipt)='text' AND length(CAST(receipt AS BLOB))=72)) AND typeof(state)='text' AND length(CAST(state AS BLOB))<=16 AND typeof(partition_id)='integer' AND (version IS NULL OR typeof(version)='integer')",
            (identity,),
        ).fetchone()

    def _route(self, row, authorities=None):
        if row["state"] == "reserved":
            return None
        gate = self.conn.execute(
            "SELECT published,partition_id,job_id,CASE WHEN typeof(plan_hash)='text' AND length(CAST(plan_hash AS BLOB))=64 THEN plan_hash ELSE NULL END,CASE WHEN typeof(plan)='text' AND length(CAST(plan AS BLOB))<=196608 THEN plan ELSE NULL END FROM layout_homes WHERE owner=? AND typeof(job_id)='text' AND length(CAST(job_id AS BLOB))=64 AND typeof(partition_id)='integer' AND typeof(published)='integer' AND published IN (0,1)",
            (row["gate"],),
        ).fetchone()
        if gate is None or gate[1] != row["partition_id"] or gate[2] != row["job_id"]:
            raise _StoreError("corrupt")
        authorities = {} if authorities is None else authorities
        if gate[2] not in authorities:
            if len(authorities) >= 256:
                raise _StoreError("unavailable")
            state = self._state(gate[2])
            authorities[gate[2]] = dict(registration=state["registration"], layout=state["layout"])
            migration.bounded(authorities)
        authority = authorities[gate[2]]
        plan = codec.validate_owner_plan(_metadata(gate[4]), authority["registration"])
        if plan["owner"] != row["gate"] or migration.hashed(plan) != gate[3]:
            raise _StoreError("unavailable")
        reservation = self._partition(row["partition_id"], authority["layout"]["envelope"])
        if any(reservation[k] < plan["expansion"][k] for k in codec.EXPANSION):
            raise _StoreError("unavailable")
        if row["state"] == "published" and not gate[0]:
            raise _StoreError("corrupt")
        return codec.validate_route(
            dict(
                format=codec.ROUTE,
                id=row["id"],
                kind=row["kind"],
                row_hash=row["row_hash"],
                partition_id=row["partition_id"],
                gate=row["gate"],
                version=row["version"],
                receipt=row["receipt"],
                state="published" if gate[0] else "staged",
            )
        )

    def routes(self, ids):
        _ids(ids)
        self._schema()
        # An envelope is required even for a hit. No attachment means unavailable.
        row = self.conn.execute(
            "SELECT CASE WHEN typeof(job_id)='text' AND length(CAST(job_id AS BLOB))=64 THEN job_id ELSE NULL END FROM layout_jobs LIMIT 1"
        ).fetchone()
        if row is None or self.attachment(row[0]) is None:
            raise _StoreError("unavailable")
        found, unavailable, authorities = [], [], {}
        for identity in ids:
            row = self._route_row(identity)
            route = self._route(row, authorities) if row is not None else None
            if route is None or route["state"] != "published":
                unavailable.append(identity)
            else:
                found.append(route)
        return migration.bounded(
            dict(
                status="ok" if not unavailable else "unavailable",
                routes=found,
                unavailable=unavailable,
            )
        )

    def ack(self, job_id, intent_id, verified_summary):
        from .semantic_queue import SemanticQueue

        if intent_id is not None:
            bulk.sha(intent_id)
        migration.bounded(
            dict(job_id=job_id, intent_id=intent_id, verified_summary=verified_summary)
        )
        state = self._state(job_id)
        summary_hash = migration.hashed(verified_summary)
        old = state["last_ack"]
        if old and old["intent_id"] == intent_id and old["summary_hash"] == summary_hash:
            return old["result"]
        if intent_id is None:
            if (
                self.conn.execute(
                    "SELECT 1 FROM layout_homes WHERE job_id=? AND published=0 LIMIT 1", (job_id,)
                ).fetchone()
                or self.conn.execute(
                    "SELECT 1 FROM layout_routes WHERE job_id=? AND state='reserved' LIMIT 1",
                    (job_id,),
                ).fetchone()
            ):
                _conflict()
            return SemanticQueue._migration_terminal_ack(
                self.conn, job_id, state, verified_summary, summary_hash
            )
        intent = state["pending"]
        if (
            intent is None
            or intent["intent_id"] != intent_id
            or intent["cursor_before"] != state["staging_cursor"]
        ):
            _conflict()
        codec.validate_layout_verified(verified_summary, intent)
        home = self._target(state, intent)
        updates = []
        authorities = {}
        for candidate, observed in zip(intent["routes"], verified_summary["batch"]["routes"]):
            row = self._route_row(candidate["id"])
            if row is None:
                _conflict()
            if row["state"] == "reserved":
                if (
                    row["intent_id"] != intent_id
                    or row["job_id"] != job_id
                    or observed["partition_id"] != row["partition_id"]
                    or observed["gate"] != row["gate"]
                    or observed["receipt"] != codec.batch_receipt_id(intent)
                    or observed["state"] != "staged"
                ):
                    _conflict()
                if (
                    candidate["row_hash"] is not None
                    and observed["row_hash"] != candidate["row_hash"]
                ):
                    _conflict()
                updates.append(observed)
            elif self._route(row, authorities) != observed:
                # Reuse accepts only an exact existing pinned route. The exact
                # worker still must compare original canonical bytes/membership.
                _conflict()
        versions = [p["version"] for p in verified_summary["owner_proofs"]]
        for proof in verified_summary["owner_proofs"]:
            receipt = next(
                r for r in verified_summary["batch"]["routes"] if r["id"] == proof["owner"]
            )
            if receipt["version"] != proof["version"]:
                _conflict()
        # Common original ACK validation happens before any route mutation.
        SemanticQueue._migration_content_values(self.conn, job_id, state, intent, versions)
        for observed in updates:
            self.conn.execute(
                "UPDATE layout_routes SET row_hash=?,version=?,receipt=?,state=? WHERE id=?",
                (
                    observed["row_hash"],
                    observed["version"],
                    observed["receipt"],
                    "published" if intent["owners"] else "staged",
                    observed["id"],
                ),
            )
        if intent["owners"]:
            self.conn.execute("UPDATE layout_homes SET published=1 WHERE owner=?", (home[0],))
        return SemanticQueue._migration_content_ack(
            self.conn, job_id, state, intent, versions, summary_hash
        )


def _metadata_paths(generation):
    for path in (generation, *generation.parents):
        if path.is_symlink():
            raise _StoreError("unavailable")
    LanceExactStore._private(generation, directory=True)
    coordination = generation / "coordination"
    LanceExactStore._private(coordination, directory=True)
    # Exactly the existing queue path and optional rollback journal, never a new DB.
    with os.scandir(coordination) as entries:
        for count, entry in enumerate(entries, 1):
            if count > 2 or entry.name not in {"queue.sqlite3", "queue.sqlite3-journal"}:
                raise _StoreError("unavailable")
            LanceExactStore._private(Path(entry.path))
    LanceExactStore._private(coordination / "queue.sqlite3")


@contextmanager
def readonly_directory(generation):
    """Exact-supervised metadata access; never the queue's 128/192MiB guard."""
    _require_supervision()
    generation = Path(generation)
    if (
        not generation.is_absolute()
        or str(generation) != str(generation.absolute())
        or ".." in generation.parts
    ):
        raise _StoreError("unavailable")
    _metadata_paths(generation)
    import sqlite3

    path = generation / "coordination" / "queue.sqlite3"
    before = path.stat()
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0)
    conn.row_factory = sqlite3.Row
    try:
        heap = conn.execute("PRAGMA hard_heap_limit=16777216").fetchone()
        if heap is None or type(heap[0]) is not int or not 0 < heap[0] <= 16777216:
            raise _StoreError("unavailable")
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA trusted_schema=OFF")
        conn.execute("PRAGMA cache_size=-512")
        conn.execute("PRAGMA mmap_size=0")
        conn.execute("BEGIN")
        directory = LayoutDirectory(conn)
        directory._schema()
        yield directory
        _metadata_paths(generation)
        after = path.stat()
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise _StoreError("unavailable")
    finally:
        conn.close()
