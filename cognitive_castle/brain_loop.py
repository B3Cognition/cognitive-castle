"""Durable, bounded host-assisted interpretation examinations.

SQLite is separate from palace storage. Inline text is attributed to its caller,
not authenticated or independently corroborated. This module never invokes a
model, opens a source backend, follows a URL, or changes original memories.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import time
import uuid

from . import brain_engine as engine

PROTOCOL_VERSION = 1
POLICY_VERSION = "bounded-understanding-2026-10-23-v1"
SCHEMA_VERSION = 3
MAX_REQUESTS = 64
MAX_SESSION_BYTES = 1024 * 1024
MAX_ROOT_BYTES = 2 * MAX_SESSION_BYTES
TERMINAL_RESERVE = 16 * 1024
STORE_QUOTA_BYTES = 64 * 1024 * 1024
MIN_FREE_BYTES = 16 * 1024 * 1024
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
KINDS = {
    "sources",
    "problem",
    "interpretation",
    "obligations",
    "issues",
    "events",
    "question",
    "schema",
    "source_map",
    "corrections",
    "dispositions",
    "commitments",
}


def _json(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _bytes(value):
    return len(_json(value).encode("utf-8"))


def _digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _text(value, cap, *, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError("expected bounded text")
    try:
        if len(value) > cap or len(value.encode("utf-8")) > cap:
            raise ValueError("text limit exceeded")
    except UnicodeError:
        raise ValueError("invalid Unicode") from None
    return value


def _identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("invalid identifier")
    return value


def _fingerprint(value, *, allow_none=False):
    if value is None and allow_none:
        return None
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("invalid request fingerprint")
    return value


def _bounded(value, cap, *, depth=0):
    """Admit native JSON prospectively, before serializing any aggregate.

    Account every reference separately: shared Python containers can encode to
    much more JSON than their resident size. Active-container detection stops
    cycles; a cumulative node budget also bounds traversal of aliased graphs.
    """
    remaining = cap
    nodes = 0
    active = set()

    def charge(amount):
        nonlocal remaining
        remaining -= amount
        if remaining < 0:
            raise ValueError("payload limit exceeded")

    def string(item):
        # len is a cheap lower bound before allocating even the UTF-8 encoding.
        if len(item) + 2 > remaining:
            raise ValueError("payload limit exceeded")
        try:
            encoded_size = len(item.encode("utf-8"))
        except UnicodeError:
            raise ValueError("invalid Unicode") from None
        escaped_extra = item.count('"') + item.count("\\")
        for char in item:
            if ord(char) < 32:
                escaped_extra += 1 if char in "\b\f\n\r\t" else 5
        charge(encoded_size + escaped_extra + 2)

    def visit(item, level):
        nonlocal nodes
        nodes += 1
        if nodes > min(cap, 8192) or level > 16:
            raise ValueError("nested input or node limit exceeded")
        if isinstance(item, str):
            string(item)
        elif item is None:
            charge(4)
        elif type(item) is bool:
            charge(4 if item else 5)
        elif type(item) is int:
            if abs(item) > 2**63 - 1:
                raise ValueError("integer limit exceeded")
            charge(len(str(item)))
        elif type(item) is float:
            if not math.isfinite(item):
                raise ValueError("nonfinite number")
            charge(len(repr(item)))
        elif isinstance(item, (list, dict)):
            if len(item) > 256 or id(item) in active:
                raise ValueError("collection or cycle limit exceeded")
            charge(2 + max(0, len(item) - 1))
            active.add(id(item))
            try:
                if isinstance(item, dict):
                    charge(len(item))  # colons
                    for key, child in item.items():
                        _text(key, 128)
                        string(key)
                        visit(child, level + 1)
                else:
                    for child in item:
                        visit(child, level + 1)
            finally:
                active.remove(id(item))
        else:
            raise ValueError("unsupported JSON value")

    visit(value, depth)


def _protocol(version):
    if type(version) is not int or version != PROTOCOL_VERSION:
        raise ValueError("incompatible protocol version")


def _revision(value):
    if type(value) is not int or value < 1:
        raise ValueError("expected positive controller revision")


def source_exposure_hash(source):
    """Identity of the complete disclosed snapshot, not just its quoted text."""
    if not isinstance(source, dict) or not {"id", "text", "provenance"}.issubset(source):
        raise ValueError("invalid source snapshot")
    _identifier(source["id"])
    _text(source["text"], 65536)
    if not isinstance(source["provenance"], dict):
        raise ValueError("invalid provenance")
    _bounded(source["provenance"], 8192)
    return _digest({key: source[key] for key in ("id", "text", "provenance")})


def _pins():
    base = Path(engine.vendor.__file__).parent
    upstream = json.loads((base / "UPSTREAM.json").read_text())
    hashes = {
        name: hashlib.sha256((base / name).read_bytes()).hexdigest()
        for name in upstream["files_sha256"]
    }
    return dict(
        controller_schema=SCHEMA_VERSION,
        policy=POLICY_VERSION,
        engine_commit=upstream["commit"],
        engine_files=hashes,
        engine_schema=engine.vendor.SCHEMA_VERSION,
        engine_policy=engine.vendor.POLICY_VERSION,
        protocol=PROTOCOL_VERSION,
        max_turns=14,
        max_examinations=2,
        max_requests=MAX_REQUESTS,
    )


class _Unavailable(Exception):
    def __init__(self, status):
        self.status = status


class BrainLoop:
    """A local controller; exposure_policy is trusted configuration, never tool input.

    ``automatic=False`` is informational and does not grant a user-directed
    exemption. Only cancellation is exposed as budget-exempt inspection control.
    ``resume`` and ``purge_source`` are trusted direct-operator methods.
    """

    def __init__(self, store_dir, *, exposure_policy=None, clock=None):
        path = Path(store_dir).expanduser()
        if path.is_symlink():
            raise ValueError("unsafe controller directory")
        self.directory = path.resolve()
        self.path = self.directory / "brain.sqlite3"
        self.exposure_policy = exposure_policy
        self.clock = clock or time.time
        self.pins = _pins()
        self._directory_identity = None

    def _policy(self):
        try:
            policy = (
                self.exposure_policy() if callable(self.exposure_policy) else self.exposure_policy
            )
            if policy is None:
                return {"allow_local_sources": False, "policy_epoch": "default-deny-v1"}
            if (
                not isinstance(policy, dict)
                or not {"allow_local_sources", "policy_epoch"}.issubset(policy)
                or set(policy) - {"allow_local_sources", "policy_epoch", "allowed_source_hashes"}
                or type(policy["allow_local_sources"]) is not bool
            ):
                raise ValueError
            _text(policy["policy_epoch"], 128)
            hashes = policy.get("allowed_source_hashes", [])
            if (
                not isinstance(hashes, list)
                or len(hashes) > 16
                or any(
                    not isinstance(h, str) or not re.fullmatch(r"[0-9a-f]{64}", h) for h in hashes
                )
            ):
                raise ValueError
            return dict(policy)
        except Exception:
            return {"allow_local_sources": False, "policy_epoch": "invalid-policy-deny"}

    def _open(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise _Unavailable("unsafe_storage")
        identity = (info.st_dev, info.st_ino)
        if self._directory_identity is not None and identity != self._directory_identity:
            raise _Unavailable("unsafe_storage")
        self._directory_identity = identity
        if not self.path.exists():
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.close(fd)
        info = self.path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
        ):
            raise _Unavailable("unsafe_storage")
        for suffix in ("-journal", "-wal", "-shm"):
            auxiliary = Path(str(self.path) + suffix)
            if auxiliary.is_symlink():
                raise _Unavailable("unsafe_storage")
        connection = sqlite3.connect(str(self.path), timeout=0.2, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA secure_delete=ON")
        return connection

    def _initialize(self, db):
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        expected = {
            "metadata",
            "roots",
            "sessions",
            "artifacts",
            "dependencies",
            "receipts",
            "tombstones",
            "task_roots",
        }
        if tables:
            if (
                tables != expected
                or db.execute("SELECT value FROM metadata WHERE key='pins'").fetchone() is None
            ):
                raise _Unavailable("corrupt")
            return
        # A new file (or an interrupted first transaction rolled back to zero)
        # may initialize. An allocated, emptied database is not a new store.
        if self.path.stat().st_size:
            raise _Unavailable("corrupt")
        db.execute(
            "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS roots (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, active TEXT NOT NULL, slots INTEGER NOT NULL, requests INTEGER NOT NULL, started REAL NOT NULL, last_clock REAL NOT NULL, stale INTEGER NOT NULL DEFAULT 0)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, root TEXT NOT NULL, parent TEXT, execution TEXT NOT NULL, engine TEXT NOT NULL, accepted INTEGER NOT NULL DEFAULT 0, invalid INTEGER NOT NULL DEFAULT 0, local_only INTEGER NOT NULL, purged INTEGER NOT NULL DEFAULT 0, coverage TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS artifacts (session TEXT NOT NULL, kind TEXT NOT NULL, key TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(session,kind,key))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS dependencies (session TEXT NOT NULL, hash TEXT NOT NULL, PRIMARY KEY(session,hash))"
        )
        db.execute("CREATE INDEX IF NOT EXISTS dependency_hash ON dependencies(hash)")
        db.execute(
            "CREATE TABLE IF NOT EXISTS receipts (request TEXT PRIMARY KEY, root TEXT NOT NULL, digest TEXT NOT NULL, session TEXT NOT NULL, operation TEXT NOT NULL, revision INTEGER NOT NULL, disposition TEXT NOT NULL)"
        )
        db.execute("CREATE TABLE IF NOT EXISTS tombstones (hash TEXT PRIMARY KEY)")
        db.execute(
            "CREATE TABLE IF NOT EXISTS task_roots (problem_hash TEXT PRIMARY KEY, root TEXT NOT NULL)"
        )
        db.execute("INSERT OR IGNORE INTO metadata VALUES ('pins',?)", (_json(self.pins),))

    def _run(self, action):
        db = None
        try:
            db = self._open()
            db.execute("BEGIN IMMEDIATE")
            self._initialize(db)
            policy = self._policy()
            result = action(db, policy)
            db.commit()
            return result
        except _Unavailable as exc:
            if db is not None:
                db.rollback()
            return {
                "status": exc.status,
                "execution_state": exc.status,
                "advisory": "stop",
                "next_action": None,
            }
        except sqlite3.Error as exc:
            if db is not None:
                db.rollback()
            message = str(exc).lower()
            status = (
                "busy"
                if "locked" in message or "busy" in message
                else "corrupt"
                if "malformed" in message or "not a database" in message
                else "storage_unavailable"
            )
            return {
                "status": status,
                "execution_state": status,
                "advisory": "stop",
                "next_action": None,
            }
        except OSError:
            if db is not None:
                db.rollback()
            return {
                "status": "storage_unavailable",
                "execution_state": "storage_unavailable",
                "advisory": "stop",
                "next_action": None,
            }
        except (ValueError, KeyError, TypeError):
            if db is not None:
                db.rollback()
            return {
                "status": "corrupt",
                "execution_state": "corrupt",
                "advisory": "stop",
                "next_action": None,
            }
        finally:
            if db is not None:
                db.close()

    def _put(self, db, sid, kind, key, body):
        db.execute(
            "INSERT OR REPLACE INTO artifacts VALUES (?,?,?,?)", (sid, kind, str(key), _json(body))
        )

    def _items(self, db, sid, kind):
        return [
            json.loads(row[0])
            for row in db.execute(
                "SELECT body FROM artifacts WHERE session=? AND kind=? ORDER BY length(key),key",
                (sid, kind),
            )
        ]

    def _load(self, db, sid):
        row = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        if row is None:
            raise _Unavailable("not_found")
        session = dict(row)
        root = db.execute("SELECT * FROM roots WHERE id=?", (session["root"],)).fetchone()
        if root is None:
            raise _Unavailable("corrupt")
        session["engine"] = json.loads(session["engine"])
        session["coverage"] = json.loads(session["coverage"])
        if not session["purged"]:
            required = db.execute(
                "SELECT count(*) FROM artifacts WHERE session=? AND kind IN ('problem','interpretation','source_map','manifest')",
                (sid,),
            ).fetchone()[0]
            events = db.execute(
                "SELECT count(*) FROM artifacts WHERE session=? AND kind='events'", (sid,)
            ).fetchone()[0]
            manifest = self._items(db, sid, "manifest")
            source_count = db.execute(
                "SELECT count(*) FROM artifacts WHERE session=? AND kind='sources'", (sid,)
            ).fetchone()[0]
            if (
                required != 4
                or events != session["accepted"]
                or not manifest
                or manifest[0]["sources"] != source_count
            ):
                raise _Unavailable("corrupt")
        return session, dict(root)

    def _compatible(self, db):
        return db.execute("SELECT value FROM metadata WHERE key='pins'").fetchone()[0] == _json(
            self.pins
        )

    def _usage(self, db, root, *, exempt=False):
        if exempt:
            return True
        if root["requests"] >= MAX_REQUESTS:
            return False
        root["requests"] += 1
        db.execute("UPDATE roots SET requests=? WHERE id=?", (root["requests"], root["id"]))
        return True

    def _expired(self, root):
        now = self.clock()
        return (
            not isinstance(now, (int, float))
            or not math.isfinite(now)
            or now < root["last_clock"]
            or now - root["started"] > 1800
        )

    def _exposure_allowed(self, db, session, policy):
        if not session["local_only"] or policy["allow_local_sources"]:
            return True
        grants = set(policy.get("allowed_source_hashes", []))
        # A child's inherited issue text may quote a parent-only source. Check
        # the frozen ancestor bundles too; grants never expand to new bytes.
        current = session
        while current is not None:
            for source in self._items(db, current["id"], "sources"):
                provenance = source["provenance"]
                if (
                    provenance.get("local_only") is True or provenance.get("origin") == "archive"
                ) and source_exposure_hash(source) not in grants:
                    return False
            current = self._load(db, current["parent"])[0] if current["parent"] else None
        return True

    def _envelope(self, db, sid, policy, *, status="ok", operation=None):
        session, root = self._load(db, sid)
        compatible = self._compatible(db)
        execution = session["execution"] if compatible else "incompatible"
        if execution == "awaiting_response" and self._expired(root):
            execution = "expired"
        stale = bool(root["stale"] or session["purged"])
        issues = self._items(db, sid, "issues")
        obligations = self._items(db, sid, "obligations")
        open_count = sum(
            i["status"] in ("open", "deferred", "unresolved", "reopened") for i in issues
        )
        missing_obligations = sum(o.get("status") != "represented" for o in obligations)
        unrepresented = []
        if not session["purged"]:
            problem = self._items(db, sid, "problem")[0]
            spans = sorted(
                (o["start"], o["end"]) for o in obligations if o["source_id"] == "problem"
            )
            position = 0
            for start, end in spans + [(len(problem), len(problem))]:
                if start > position and problem[position:start].strip():
                    unrepresented.append({"start": position, "end": start})
                position = max(position, end)
        current = (
            root["active"] == sid and execution in ("awaiting_response", "terminal") and not stale
        )
        resolved = session["engine"]["terminal"] == "RESOLVED"
        advisory = (
            "proceed_with_limits"
            if current
            and resolved
            and not open_count
            and not missing_obligations
            and not unrepresented
            and not session["coverage"]["missing"]
            and bool(obligations)
            else "requires_review"
            if current
            else "stop"
        )
        allowed = self._exposure_allowed(db, session, policy)
        if not allowed:
            status, advisory = "exposure_denied", "stop"
        if session["purged"]:
            status, advisory = "source_purged", "stop"
        e = session["engine"]
        next_action = None
        if (
            allowed
            and compatible
            and current
            and execution == "awaiting_response"
            and root["requests"] < MAX_REQUESTS
        ):
            next_action = {
                "action": "respond",
                "operator": e["operator"],
                "expected_turn": session["accepted"] + 1,
                "question_ref": {
                    "kind": "question",
                    "session_id": sid,
                    "revision": root["revision"],
                },
                "schema_ref": {"kind": "schema", "session_id": sid, "revision": root["revision"]},
            }
        result = dict(
            status=status,
            session_id=sid,
            root_id=root["id"],
            revision=root["revision"],
            execution_state=execution,
            engine_terminal=e["terminal"],
            advisory=advisory,
            citation_fidelity="exact_locations_only" if session["accepted"] else "not_examined",
            asserted_support="host_attributed_unverified",
            independent_checks="not_performed",
            coverage=session["coverage"],
            freshness="known_stale" if stale else "snapshot_only",
            exposure_epoch=policy["policy_epoch"],
            execution_mode="host_assisted_self_check",
            source_authority="caller_attributed",
            examination_kind="mixed",
            counts={
                "issues": len(issues),
                "open_issues": open_count,
                "obligations": len(obligations),
                "unrepresented_obligations": missing_obligations,
            },
            budgets={
                "accepted_turns": session["accepted"],
                "turns_remaining": 14 - session["accepted"],
                "examinations_remaining": 2 - root["slots"],
                "automatic_requests_used": root["requests"],
                "automatic_requests_remaining": max(0, MAX_REQUESTS - root["requests"]),
            },
            next_action=next_action,
            protocol_version=1,
            policy_version=POLICY_VERSION,
            limitations=[
                "Interpretation and obligation coverage are assistant judgments, not completeness or truth guarantees.",
                "Empirical, factual and implementation checks remain separate.",
                "Source selection is bounded; archive completeness and live freshness are unknown.",
            ],
            operation=operation,
        )
        if not allowed or session["purged"]:
            result["coverage"] = {"status": "withheld"}
        else:
            result["coverage"] = {
                **result["coverage"],
                "unrepresented_request_ranges": unrepresented,
                "ledger_attribution": "assistant_interpretation_not_exhaustiveness_proof",
            }
        return result

    def _receipt(self, db, request_id, digest, operation, sid, disposition):
        session, root = self._load(db, sid)
        db.execute(
            "INSERT INTO receipts VALUES (?,?,?,?,?,?,?)",
            (request_id, root["id"], digest, sid, operation, root["revision"], disposition),
        )
        return {
            "request_id": request_id,
            "operation": operation,
            "committed_revision": root["revision"],
            "disposition": disposition,
        }

    def _replay(self, db, request_id, digest, policy, *, exempt=False):
        old = db.execute("SELECT * FROM receipts WHERE request=?", (request_id,)).fetchone()
        if old is None:
            return None
        session, root = self._load(db, old["session"])
        allowed = self._usage(db, root, exempt=exempt)
        status = "ok" if old["digest"] == digest else "request_conflict"
        if not allowed:
            status = "request_budget_exhausted"
        operation = {
            "request_id": request_id,
            "operation": old["operation"],
            "committed_revision": old["revision"],
            "disposition": old["disposition"],
        }
        return self._envelope(
            db,
            session["id"],
            policy,
            status=status,
            operation=operation if old["digest"] == digest else None,
        )

    def replay(self, request_id, request_fingerprint):
        """Trusted boundary lookup before reading mutable archive snapshots.

        Fingerprints must describe the exact original wire arguments, including
        the operation namespace. They are never accepted as tool parameters.
        Only a missing receipt returns None; errors and current-policy denial
        remain structured responses. No historical content envelope is cached.
        """
        _identifier(request_id)
        _fingerprint(request_fingerprint)
        return self._run(
            lambda db, policy: self._replay(db, request_id, request_fingerprint, policy)
        )

    def preflight_begin(self, problem, *, parent_id=None, expected_revision=None):
        """Trusted admission check before a potentially costly read.

        This is not a reservation: begin still serializes and rechecks admission.
        Early responses charge one automatic request; an admitted None leaves
        that charge to begin, avoiding a double debit for the same request.
        A known correction is carried into a successor's unresolved ledger; it
        cannot by itself prohibit the examination needed to address it.
        """
        _text(problem, 8192)
        if parent_id is not None:
            _identifier(parent_id)
            _revision(expected_revision)
        elif expected_revision is not None:
            raise ValueError("successor fields require parent")

        def action(db, policy):
            if not self._compatible(db):
                raise _Unavailable("incompatible")
            if parent_id is None:
                problem_hash = hashlib.sha256(problem.encode()).hexdigest()
                existing = db.execute(
                    "SELECT root FROM task_roots WHERE problem_hash=?",
                    (problem_hash,),
                ).fetchone()
                if existing is not None:
                    root_row = db.execute(
                        "SELECT active FROM roots WHERE id=?", (existing[0],)
                    ).fetchone()
                    if root_row is None:
                        raise _Unavailable("corrupt")
                    session, root = self._load(db, root_row[0])
                    status = (
                        "existing_task" if self._usage(db, root) else "request_budget_exhausted"
                    )
                    return self._envelope(db, session["id"], policy, status=status)
                if db.execute("SELECT 1 FROM tombstones WHERE hash=?", (problem_hash,)).fetchone():
                    raise _Unavailable("source_purged")
                return None
            session, root = self._load(db, parent_id)
            if root["requests"] >= MAX_REQUESTS:
                status = "request_budget_exhausted"
            elif root["revision"] != expected_revision:
                status = "revision_conflict"
            elif root["slots"] >= 2:
                status = "examination_budget_exhausted"
            else:
                status = self._parent_state(db, session, root, policy)
                if status is None:
                    return None
            if not self._usage(db, root):
                status = "request_budget_exhausted"
            return self._envelope(db, parent_id, policy, status=status)

        return self._run(action)

    def _parent_state(self, db, session, root, policy):
        if (
            session["purged"]
            or root["active"] != session["id"]
            or session["execution"] not in ("awaiting_response", "terminal")
        ):
            return "inactive"
        if self._expired(root):
            return "expired"
        if not self._exposure_allowed(db, session, policy):
            return "exposure_denied"
        return None

    def _admit(self, db, sid, *, terminal=False):
        session, root = self._load(db, sid)
        session_bytes = db.execute(
            "SELECT COALESCE(sum(length(CAST(body AS BLOB))),0) FROM artifacts WHERE session=?",
            (sid,),
        ).fetchone()[0]
        session_bytes += _bytes(session["engine"]) + _bytes(session["coverage"])
        root_bytes = db.execute(
            "SELECT COALESCE(sum(length(CAST(a.body AS BLOB))),0) FROM artifacts a JOIN sessions s ON s.id=a.session WHERE s.root=?",
            (root["id"],),
        ).fetchone()[0]
        root_bytes += db.execute(
            "SELECT COALESCE(sum(length(CAST(engine AS BLOB))+length(CAST(coverage AS BLOB))),0) FROM sessions WHERE root=?",
            (root["id"],),
        ).fetchone()[0]
        receipt_bytes = db.execute(
            "SELECT COALESCE(sum(length(request)+length(digest)+length(session)+length(operation)+length(disposition)+64),0) FROM receipts WHERE root=?",
            (root["id"],),
        ).fetchone()[0]
        reserve = 0 if terminal else TERMINAL_RESERVE
        if (
            session_bytes + receipt_bytes > MAX_SESSION_BYTES - reserve
            or root_bytes + receipt_bytes > MAX_ROOT_BYTES - reserve
        ):
            raise _Unavailable("artifact_budget_exhausted")
        page_count = db.execute("PRAGMA page_count").fetchone()[0]
        page_size = db.execute("PRAGMA page_size").fetchone()[0]
        if (
            page_count * page_size > STORE_QUOTA_BYTES
            or shutil.disk_usage(self.directory).free < MIN_FREE_BYTES
        ):
            raise _Unavailable("storage_quota_exhausted")

    def _bump(self, db, root):
        now = self.clock()
        db.execute(
            "UPDATE roots SET revision=revision+1,last_clock=? WHERE id=?", (now, root["id"])
        )

    def _reuse_task(self, db, problem, request_id, digest, policy):
        """Exact original-task identity survives retries, process exit and UUID changes.

        This cannot identify semantic paraphrases or independently authenticate
        the user's intent. Those limits remain the host's responsibility.
        """
        problem_hash = hashlib.sha256(problem.encode()).hexdigest()
        previous = db.execute(
            "SELECT root FROM task_roots WHERE problem_hash=?", (problem_hash,)
        ).fetchone()
        if previous is None:
            return None
        root = db.execute("SELECT active FROM roots WHERE id=?", (previous[0],)).fetchone()
        if root is None:
            raise _Unavailable("corrupt")
        session, root = self._load(db, root[0])
        if not self._usage(db, root):
            return self._envelope(db, session["id"], policy, status="request_budget_exhausted")
        receipt = self._receipt(db, request_id, digest, "begin", session["id"], "existing_task")
        self._admit(db, session["id"], terminal=True)
        return self._envelope(db, session["id"], policy, status="existing_task", operation=receipt)

    @staticmethod
    def _prepare_inputs(problem, sources, obligations):
        if (
            not isinstance(sources, list)
            or len(sources) > 8
            or not isinstance(obligations, list)
            or len(obligations) > 64
        ):
            raise ValueError("source or obligation count limit")
        prepared = []
        text_bytes = provenance_bytes = 0
        ids = {"problem"}
        for source in sources:
            if not isinstance(source, dict) or set(source) != {"id", "text", "provenance"}:
                raise ValueError("source fields mismatch")
            _identifier(source["id"])
            if source["id"] in ids:
                raise ValueError("duplicate source identifier")
            ids.add(source["id"])
            _text(source["text"], 65536)
            if not isinstance(source["provenance"], dict):
                raise ValueError("invalid provenance")
            _bounded(source["provenance"], 8192)
            text_bytes += len(source["text"].encode("utf-8"))
            provenance_bytes += _bytes(source["provenance"])
            prepared.append(
                {
                    **source,
                    "hash": hashlib.sha256(source["text"].encode("utf-8")).hexdigest(),
                    "exposure_hash": source_exposure_hash(source),
                    "attribution": "caller_attributed",
                }
            )
        if text_bytes > 65536 or provenance_bytes > 8192:
            raise ValueError("source bundle byte limit")
        source_texts = {s["id"]: s["text"] for s in sources} | {"problem": problem}
        parsed_obligations, obligation_ids = [], set()
        for obligation in obligations:
            if not isinstance(obligation, dict) or set(obligation) != {
                "id",
                "text",
                "source_id",
                "start",
                "end",
            }:
                raise ValueError("obligation fields mismatch")
            _identifier(obligation["id"])
            _identifier(obligation["source_id"])
            _text(obligation["text"], 8192)
            start, end = obligation["start"], obligation["end"]
            text = source_texts.get(obligation["source_id"])
            if (
                type(start) is not int
                or type(end) is not int
                or text is None
                or not 0 <= start < end <= len(text)
                or text[start:end] != obligation["text"]
                or obligation["id"] in obligation_ids
            ):
                raise ValueError("invalid exact obligation span")
            obligation_ids.add(obligation["id"])
            parsed_obligations.append(
                {**obligation, "status": "unexamined", "attribution": "assistant_interpretation"}
            )
        return prepared, parsed_obligations

    @staticmethod
    def _check_original_spans(parsed_obligations, frozen_problem):
        for obligation in parsed_obligations:
            if (
                obligation["source_id"] == "problem"
                and frozen_problem[obligation["start"] : obligation["end"]] != obligation["text"]
            ):
                raise _Unavailable("invalid_obligation_scope")

    @staticmethod
    def _correction_record(session_id, revision, text):
        identity = f"{session_id}:{revision}"
        return {
            "id": identity,
            "source_id": f"@correction:{identity}",
            "origin_session": session_id,
            "origin_revision": revision,
            "text": text,
            "hash": hashlib.sha256(text.encode()).hexdigest(),
            "attribution": "caller_attributed",
        }

    def _store_correction(self, db, session_id, correction):
        self._put(db, session_id, "corrections", correction["id"], correction)
        db.execute(
            "INSERT OR IGNORE INTO dependencies VALUES (?,?)", (session_id, correction["hash"])
        )

    def _carry_corrections(self, db, sid, parent_id, sources, issues, obligations):
        records = self._items(db, parent_id, "corrections") if parent_id else []
        # Include a proposal already recorded on this child, without replacing
        # the original request or interpreting the proposal as authoritative.
        records += self._items(db, sid, "corrections")
        if sum(len(item["text"].encode()) for item in sources + records) > 65536:
            raise _Unavailable("correction_context_budget_exhausted")
        for record in records:
            self._store_correction(db, sid, record)
            identity = record["id"]
            iid = f"{record['origin_session']}:0:correction:{record['origin_revision']}"
            issues.append(
                {
                    "id": iid,
                    "origin_session": record["origin_session"],
                    "origin_turn": 0,
                    "kind": "correction",
                    "item_index": record["origin_revision"],
                    "text": record["text"],
                    "status": "open",
                    "dependencies": [record["hash"]],
                    "attribution": "caller_attributed",
                }
            )
            oid = f"correction:{identity}"
            obligations[oid] = {
                "id": oid,
                "text": record["text"],
                "source_id": record["source_id"],
                "start": 0,
                "end": len(record["text"]),
                "status": "unexamined",
                "attribution": "assistant_interpretation_of_caller_correction",
            }
        return [{"id": record["source_id"], "text": record["text"]} for record in records]

    def begin(
        self,
        request_id,
        problem,
        interpretation,
        sources,
        obligations,
        *,
        parent_id=None,
        expected_revision=None,
        revision_reason=None,
        protocol_version=1,
        request_fingerprint=None,
    ):
        _protocol(protocol_version)
        _identifier(request_id)
        _fingerprint(request_fingerprint, allow_none=True)
        _text(problem, 8192)
        _text(interpretation, 8192)
        prepared, parsed_obligations = self._prepare_inputs(problem, sources, obligations)
        if parent_id is not None:
            _identifier(parent_id)
            _revision(expected_revision)
            _text(revision_reason, 2048)
        elif expected_revision is not None or revision_reason is not None:
            raise ValueError("successor fields require parent")
        payload = dict(
            problem=problem,
            interpretation=interpretation,
            sources=sources,
            obligations=obligations,
            parent_id=parent_id,
            expected_revision=expected_revision,
            revision_reason=revision_reason,
        )
        # Trusted adapters can bind identity to the original archive-ID request,
        # whose materialized source bytes may change between transport retries.
        digest = request_fingerprint or _digest({"operation": "begin", **payload})

        def action(db, policy):
            replay = self._replay(db, request_id, digest, policy)
            if replay is not None:
                return replay
            if not self._compatible(db):
                raise _Unavailable("incompatible")
            reuse = (
                self._reuse_task(db, problem, request_id, digest, policy)
                if parent_id is None
                else None
            )
            if reuse is not None:
                return reuse
            inherited_issues, inherited_obligations = [], []
            frozen_problem = problem
            now = self.clock()
            sid = uuid.uuid4().hex
            if parent_id is not None:
                parent, root = self._load(db, parent_id)
                if not self._usage(db, root):
                    return self._envelope(db, parent_id, policy, status="request_budget_exhausted")
                if root["revision"] != expected_revision:
                    return self._envelope(db, parent_id, policy, status="revision_conflict")
                if root["slots"] >= 2:
                    return self._envelope(
                        db, parent_id, policy, status="examination_budget_exhausted"
                    )
                parent_status = self._parent_state(db, parent, root, policy)
                if parent_status is not None:
                    return self._envelope(db, parent_id, policy, status=parent_status)
                inherited_issues = self._items(db, parent_id, "issues")
                inherited_obligations = self._items(db, parent_id, "obligations")
                frozen_problem = self._items(db, parent_id, "problem")[0]
                self._check_original_spans(parsed_obligations, frozen_problem)
                if problem != frozen_problem:
                    inherited_issues.append(
                        {
                            "id": f"{parent_id}:0:scope_change:0",
                            "kind": "scope_change",
                            "status": "open",
                            "text": "A successor proposed a different request. The original request and its obligations remain binding until an authoritative scope decision.",
                            "dependencies": [],
                        }
                    )
                for issue in inherited_issues:
                    issue["status"] = "reopened"
                old_sources = self._items(db, parent_id, "sources")
                old_hashes = {s["hash"] for s in old_sources}
                new_hashes = {s["hash"] for s in prepared}
                if old_hashes - new_hashes:
                    inherited_issues.append(
                        {
                            "id": f"{parent_id}:0:source_exclusion:0",
                            "kind": "source_exclusion",
                            "status": "open",
                            "text": "Previously examined source evidence was omitted or changed; review its relevance.",
                            "dependencies": sorted(old_hashes - new_hashes),
                        }
                    )
                db.execute("UPDATE sessions SET execution='superseded' WHERE id=?", (parent_id,))
                db.execute(
                    "UPDATE roots SET slots=slots+1,active=?,revision=revision+1,stale=0,last_clock=? WHERE id=?",
                    (sid, now, root["id"]),
                )
                root_id = root["id"]
            else:
                root_id = uuid.uuid4().hex
                db.execute(
                    "INSERT INTO roots VALUES (?,?,?,1,1,?,?,0)", (root_id, 1, sid, now, now)
                )
                db.execute(
                    "INSERT INTO task_roots VALUES (?,?)",
                    (hashlib.sha256(problem.encode()).hexdigest(), root_id),
                )
            local_only = any(
                s["provenance"].get("local_only") is True
                or s["provenance"].get("origin") == "archive"
                for s in prepared
            )
            if parent_id is not None:
                local_only = local_only or bool(parent["local_only"])
            raw = engine.initial_state(interpretation)
            coverage = {
                "claim_version": 0,
                "dimensions": engine.coverage(raw)["dimensions"],
                "missing": engine.coverage(raw)["missing"],
            }
            raw.pop("turns")
            db.execute(
                "INSERT INTO sessions (id,root,parent,execution,engine,local_only,coverage) VALUES (?,?,?,'awaiting_response',?,?,?)",
                (sid, root_id, parent_id, _json(raw), int(local_only), _json(coverage)),
            )
            self._put(db, sid, "problem", "0", frozen_problem)
            if frozen_problem != problem:
                self._store_correction(
                    db, sid, self._correction_record(sid, "successor_proposal", problem)
                )
            self._put(db, sid, "interpretation", "0", interpretation)
            self._put(db, sid, "manifest", "0", {"sources": len(prepared)})
            problem_hash = hashlib.sha256(frozen_problem.encode()).hexdigest()
            if db.execute("SELECT 1 FROM tombstones WHERE hash=?", (problem_hash,)).fetchone():
                raise _Unavailable("source_purged")
            for source in prepared:
                if db.execute(
                    "SELECT 1 FROM tombstones WHERE hash=?", (source["hash"],)
                ).fetchone():
                    raise _Unavailable("source_purged")
                self._put(db, sid, "sources", source["id"], source)
                db.execute("INSERT OR IGNORE INTO dependencies VALUES (?,?)", (sid, source["hash"]))
            db.execute("INSERT OR IGNORE INTO dependencies VALUES (?,?)", (sid, problem_hash))
            merged = {o["id"]: o for o in parsed_obligations}
            for old in inherited_obligations:
                # Original obligations cannot be overwritten or dropped by a narrower child.
                merged[old["id"]] = {**old, "status": "unexamined"}
            correction_sources = self._carry_corrections(
                db, sid, parent_id, prepared, inherited_issues, merged
            )
            if len(merged) > 64 or len(inherited_issues) > 128:
                raise _Unavailable("collection_budget_exhausted")
            for issue in inherited_issues:
                self._put(db, sid, "issues", issue["id"], issue)
            for obligation in merged.values():
                self._put(db, sid, "obligations", obligation["id"], obligation)
            self._put(
                db,
                sid,
                "source_map",
                "0",
                self._source_map(prepared + correction_sources, frozen_problem),
            )
            if parent_id:
                self._put(
                    db,
                    sid,
                    "commitments",
                    "successor",
                    {"reason": revision_reason, "parent_id": parent_id},
                )
            operation = self._receipt(db, request_id, digest, "begin", sid, "accepted")
            self._admit(db, sid)
            return self._envelope(db, sid, policy, operation=operation)

        return self._run(action)

    @staticmethod
    def _source_map(sources, problem):
        # No generated boundary is exposed as an evidence line. Offsets refer to
        # Python Unicode codepoints in the exact unnormalized source string.
        mapping, line_no = [], 1
        for source in sources + [{"id": "problem", "text": problem}]:
            offset = 0
            for line in source["text"].splitlines(keepends=True):
                content = line.rstrip("\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029")
                mapping.append(
                    {
                        "line": line_no,
                        "source_id": source["id"],
                        "start": offset,
                        "end": offset + len(content),
                        "text": content,
                    }
                )
                offset += len(line)
                line_no += 1
        return mapping

    def _mutate(self, sid, request_id, revision, payload, operation, callback, *, exempt=False):
        _identifier(sid)
        _identifier(request_id)
        _revision(revision)
        digest = _digest(
            {"operation": operation, "session_id": sid, "expected_revision": revision, **payload}
        )

        def action(db, policy):
            replay = self._replay(db, request_id, digest, policy, exempt=exempt)
            if replay is not None:
                return replay
            session, root = self._load(db, sid)
            if not self._compatible(db):
                return self._envelope(db, sid, policy, status="incompatible")
            if not self._usage(db, root, exempt=exempt):
                return self._envelope(db, sid, policy, status="request_budget_exhausted")
            if root["revision"] != revision:
                return self._envelope(db, sid, policy, status="revision_conflict")
            if operation == "respond" and (
                session["execution"] != "awaiting_response"
                or root["active"] != sid
                or root["stale"]
                or session["purged"]
            ):
                return self._envelope(db, sid, policy, status="inactive")
            if operation == "respond" and self._expired(root):
                return self._envelope(db, sid, policy, status="expired")
            if operation == "respond" and not self._exposure_allowed(db, session, policy):
                return self._envelope(db, sid, policy, status="exposure_denied")
            db.execute("SAVEPOINT semantic")
            try:
                disposition = callback(db, session, root)
                self._bump(db, root)
                receipt = self._receipt(db, request_id, digest, operation, sid, disposition)
                self._admit(
                    db,
                    sid,
                    terminal=operation in ("cancel", "correct") or disposition == "rejected",
                )
            except _Unavailable as exc:
                db.execute("ROLLBACK TO semantic")
                if operation != "respond":
                    raise
                raw = session["engine"]
                raw.pop("turns", None)
                raw["terminal"] = "BOUNDED_STOP"
                db.execute(
                    "UPDATE sessions SET execution='terminal',engine=? WHERE id=?",
                    (_json(raw), sid),
                )
                self._bump(db, root)
                receipt = self._receipt(db, request_id, digest, operation, sid, exc.status)
                self._admit(db, sid, terminal=True)
                return self._envelope(db, sid, policy, status=exc.status, operation=receipt)
            return self._envelope(
                db,
                sid,
                policy,
                status="invalid_response" if disposition == "rejected" else "ok",
                operation=receipt,
            )

        return self._run(action)

    def respond(
        self,
        session_id,
        request_id,
        expected_revision,
        response,
        *,
        dispositions=None,
        commitment_map=None,
        protocol_version=1,
    ):
        _protocol(protocol_version)
        if not isinstance(response, dict):
            raise ValueError("response must be an object")
        _bounded(response, 16384)
        _bounded(dispositions, 16384)
        _bounded(commitment_map, 16384)
        # Bound the combined semantic response, including controller additions.
        _bounded(
            {"response": response, "dispositions": dispositions, "commitment_map": commitment_map},
            16384,
        )
        payload = dict(response=response, dispositions=dispositions, commitment_map=commitment_map)

        def callback(db, session, root):
            sid = session["id"]
            state = session["engine"]
            state["turns"] = self._items(db, sid, "events")
            if len(state["turns"]) != session["accepted"]:
                raise _Unavailable("corrupt")
            source_map = self._items(db, sid, "source_map")[0]
            advanced, error = engine.advance(state, response, [line["text"] for line in source_map])
            if error is None:
                db.execute("SAVEPOINT ledger")
                try:
                    self._ledger(db, sid, state, advanced, dispositions, commitment_map)
                except (ValueError, TypeError, KeyError):
                    db.execute("ROLLBACK TO ledger")
                    error = "invalid_controller_ledger"
                finally:
                    db.execute("RELEASE ledger")
            if error is not None:
                # No rejected response body or arbitrary validation text is retained.
                state.pop("turns")
                invalid = session["invalid"] + 1
                if invalid >= 2:
                    state["terminal"] = "BOUNDED_STOP"
                db.execute(
                    "UPDATE sessions SET invalid=?,engine=?,execution=? WHERE id=?",
                    (
                        invalid,
                        _json(state),
                        "terminal" if invalid >= 2 else "awaiting_response",
                        sid,
                    ),
                )
                self._put(
                    db,
                    sid,
                    "invalid_audit",
                    f"{session['accepted']}:{invalid}",
                    {"digest": _digest(payload), "bytes": _bytes(payload), "code": error},
                )
                return "rejected"
            turn = advanced["turns"][-1]
            self._put(db, sid, "events", turn["turn_no"], turn)
            profile = engine.coverage(advanced)
            coverage = {key: profile[key] for key in ("claim_version", "dimensions", "missing")}
            advanced.pop("turns")
            if _bytes(advanced) + _bytes(coverage) > 65536:
                raise _Unavailable("projection_budget_exhausted")
            db.execute(
                "UPDATE sessions SET engine=?,coverage=?,accepted=accepted+1,invalid=0,execution=? WHERE id=?",
                (
                    _json(advanced),
                    _json(coverage),
                    "terminal" if advanced["terminal"] else "awaiting_response",
                    sid,
                ),
            )
            return "accepted"

        return self._mutate(session_id, request_id, expected_revision, payload, "respond", callback)

    def _ledger(self, db, sid, before, after, dispositions, commitment_map):
        turn = after["turns"][-1]
        issues = {i["id"]: i for i in self._items(db, sid, "issues")}
        obligations = {o["id"]: o for o in self._items(db, sid, "obligations")}
        changed = turn["operator"] == "REVISE" or turn["claim_after"] != turn["claim_before"]
        if changed and obligations and commitment_map is None:
            raise ValueError("claim revisions require commitment map")
        if commitment_map is not None:
            if not isinstance(commitment_map, list) or len(commitment_map) != len(obligations):
                raise ValueError("complete obligation map required")
            seen = set()
            for item in commitment_map:
                if not isinstance(item, dict) or set(item) != {"obligation_id", "change", "reason"}:
                    raise ValueError("invalid commitment map")
                oid = item["obligation_id"]
                if (
                    oid not in obligations
                    or oid in seen
                    or item["change"] not in ("retained", "changed", "dropped")
                ):
                    raise ValueError("invalid obligation reference")
                _text(item["reason"], 2048)
                seen.add(oid)
                obligations[oid]["status"] = (
                    "represented" if item["change"] == "retained" else "unresolved"
                )
                obligations[oid]["claim_version"] = after["version"]
            self._put(db, sid, "commitments", turn["turn_no"], commitment_map)
        if changed:
            for issue in issues.values():
                if issue["status"] not in ("open", "unresolved", "deferred", "reopened"):
                    issue["status"] = "reopened"
        additions = [("question", q) for q in turn["open_questions"]]
        additions += [
            ("assumption", p["statement"]) for p in turn["premises"] if p["kind"] == "assumption"
        ]
        if turn["verdict"] in ("PARTIAL", "SILENT") and not additions:
            additions.append(("gap", turn["question"]))
        if turn["test_result"] in ("FOUND", "CONFLICT", "POSSIBLE"):
            additions.append(
                ("counterexample" if turn["test_result"] == "FOUND" else "conflict", turn["answer"])
            )
        for index, (kind, text) in enumerate(additions):
            iid = f"{sid}:{turn['turn_no']}:{kind}:{index}"
            issues[iid] = {
                "id": iid,
                "origin_session": sid,
                "origin_turn": turn["turn_no"],
                "kind": kind,
                "item_index": index,
                "text": text,
                "status": "open",
                "claim_version": after["version"],
                "dependencies": [],
            }
        if len(issues) > 128:
            raise _Unavailable("collection_budget_exhausted")
        self._apply_dispositions(db, sid, turn, after, issues, dispositions)
        for issue in issues.values():
            self._put(db, sid, "issues", issue["id"], issue)
        for obligation in obligations.values():
            self._put(db, sid, "obligations", obligation["id"], obligation)

    def _apply_dispositions(self, db, sid, turn, after, issues, dispositions):
        if dispositions is not None:
            if not isinstance(dispositions, list) or len(dispositions) > 128:
                raise ValueError("invalid dispositions")
            seen = set()
            sources = {s["id"]: s for s in self._items(db, sid, "sources")}
            sources.update(
                {record["source_id"]: record for record in self._items(db, sid, "corrections")}
            )
            problem = self._items(db, sid, "problem")[0]
            sources["problem"] = {
                "text": problem,
                "hash": hashlib.sha256(problem.encode()).hexdigest(),
            }
            for item in dispositions:
                required = {
                    "issue_id",
                    "status",
                    "reason",
                    "author",
                    "claim_version",
                    "dependencies",
                    "citations",
                }
                if not isinstance(item, dict) or set(item) != required:
                    raise ValueError("disposition fields mismatch")
                iid = item["issue_id"]
                if (
                    iid not in issues
                    or iid in seen
                    or item["status"]
                    not in (
                        "attributed_answer",
                        "normative_decision",
                        "withdrawn_premise",
                        "deferred",
                        "unresolved",
                    )
                ):
                    raise ValueError("invalid item disposition")
                seen.add(iid)
                if item["status"] == "withdrawn_premise" and issues[iid]["kind"] != "assumption":
                    raise ValueError("only an assumption can be withdrawn as a premise")
                _text(item["reason"], 2048)
                _text(item["author"], 256)
                if (
                    type(item["claim_version"]) is not int
                    or item["claim_version"] != after["version"]
                ):
                    raise ValueError("stale disposition")
                dependencies = item["dependencies"]
                if not isinstance(dependencies, list) or any(
                    h not in {s["hash"] for s in sources.values()} for h in dependencies
                ):
                    raise ValueError("invalid dependency")
                citations = item["citations"]
                if not isinstance(citations, list) or (
                    not citations
                    and item["status"] not in ("deferred", "unresolved", "withdrawn_premise")
                ):
                    raise ValueError("citation required")
                cited_hashes = set()
                for cite in citations:
                    if not isinstance(cite, dict) or set(cite) != {
                        "source_id",
                        "start",
                        "end",
                        "quote",
                    }:
                        raise ValueError("invalid citation")
                    source = sources.get(cite["source_id"])
                    start, end = cite["start"], cite["end"]
                    if (
                        source is None
                        or type(start) is not int
                        or type(end) is not int
                        or not 0 <= start < end <= len(source["text"])
                        or source["text"][start:end] != cite["quote"]
                    ):
                        raise ValueError("citation mismatch")
                    if source["hash"] not in dependencies:
                        raise ValueError("citation dependency required")
                    cited_hashes.add(source["hash"])
                if (
                    issues[iid]["kind"] == "correction"
                    and item["status"] == "attributed_answer"
                    and not set(issues[iid]["dependencies"]).issubset(cited_hashes)
                ):
                    raise ValueError("correction resolution requires correction context")
                # A caller cannot establish authoritative assent by choosing a label.
                status = (
                    "unresolved"
                    if item["status"] == "normative_decision"
                    or issues[iid]["kind"] in ("scope_change", "source_exclusion")
                    else item["status"]
                )
                issues[iid].update(
                    status=status,
                    dependencies=dependencies,
                    claim_version=after["version"],
                    disposition_attribution="caller_attributed",
                )
                self._put(db, sid, "dispositions", f"{turn['turn_no']}:{iid}", item)

    def status(self, session_id, *, automatic=True):
        _identifier(session_id)
        if type(automatic) is not bool:
            raise ValueError("automatic must be boolean")

        def action(db, policy):
            _session, root = self._load(db, session_id)
            admitted = self._usage(db, root)
            return self._envelope(
                db, session_id, policy, status="ok" if admitted else "request_budget_exhausted"
            )

        return self._run(action)

    def page(self, session_id, kind, *, offset=0, limit=2048, automatic=True, cursor=None):
        return self._page(
            session_id, kind, offset=offset, limit=limit, automatic=automatic, cursor=cursor
        )

    def inspect(self, session_id, *, kind=None, offset=0, limit=2048, cursor=None):
        """Trusted user-directed inspection; deliberately absent from tool API."""
        _identifier(session_id)
        if kind is not None:
            return self._page(
                session_id, kind, offset=offset, limit=limit, cursor=cursor, count=False
            )
        return self._run(lambda db, policy: self._envelope(db, session_id, policy))

    def _page(
        self, session_id, kind, *, offset=0, limit=2048, automatic=True, cursor=None, count=True
    ):
        _identifier(session_id)
        if (
            not isinstance(kind, str)
            or kind not in KINDS
            or type(offset) is not int
            or offset < 0
            or type(limit) is not int
            or not 1 <= limit <= 4096
            or type(automatic) is not bool
        ):
            raise ValueError("invalid page request")
        if cursor is not None:
            _bounded(cursor, 1024)
            if not isinstance(cursor, dict) or set(cursor) != {
                "session_id",
                "kind",
                "revision",
                "exposure_epoch",
                "offset",
                "content_digest",
            }:
                raise ValueError("invalid cursor")

        def action(db, policy):
            session, root = self._load(db, session_id)
            admitted = self._usage(db, root, exempt=not count)
            envelope = self._envelope(
                db, session_id, policy, status="ok" if admitted else "request_budget_exhausted"
            )
            if envelope["status"] != "ok":
                return envelope
            if kind in ("question", "schema"):
                if not self._compatible(db):
                    envelope["status"] = "incompatible"
                    return envelope
                value = (
                    engine.question(session["engine"])
                    if kind == "question"
                    else engine.schema(session["engine"])
                )
                items = 1
            else:
                value = self._items(db, session_id, kind)
                if kind in ("problem", "interpretation", "source_map") and value:
                    value = value[0]
                items = len(value) if isinstance(value, list) else 1
            text = _json(value)
            if cursor is not None and (
                cursor["session_id"] != session_id
                or cursor["kind"] != kind
                or cursor["revision"] != root["revision"]
                or cursor["exposure_epoch"] != policy["policy_epoch"]
                or cursor["offset"] != offset
                or cursor["content_digest"] != hashlib.sha256(text.encode()).hexdigest()
            ):
                envelope["status"] = "stale_cursor"
                envelope["next_action"] = None
                return envelope
            if offset and cursor is None:
                envelope["status"] = "cursor_required"
                envelope["next_action"] = None
                return envelope
            if offset > len(text):
                raise _Unavailable("invalid_cursor")
            chunk = text[offset : offset + limit]
            # Count actual UTF-8 bytes and worst-case outer JSON escaping.
            while (
                _bytes({"content": [{"type": "text", "text": _json({**envelope, "text": chunk})}]})
                > 30000
            ):
                chunk = chunk[: len(chunk) // 2]
            next_offset = offset + len(chunk)
            next_cursor = {
                "session_id": session_id,
                "kind": kind,
                "revision": root["revision"],
                "exposure_epoch": policy["policy_epoch"],
                "offset": next_offset,
                "content_digest": hashlib.sha256(text.encode()).hexdigest(),
            }
            envelope.update(
                kind=kind,
                text=chunk,
                offset=offset,
                next_offset=next_offset if next_offset < len(text) else None,
                remaining_characters=len(text) - next_offset,
                total_characters=len(text),
                item_count=items,
                cursor=next_cursor if next_offset < len(text) else None,
            )
            return envelope

        return self._run(action)

    def cancel(
        self, session_id, request_id, expected_revision, *, reason="cancelled", protocol_version=1
    ):
        _protocol(protocol_version)
        _text(reason, 2048)

        def callback(db, session, root):
            db.execute("UPDATE sessions SET execution='cancelled' WHERE id=?", (session_id,))
            # Reason is historical data, not a receipt or status field.
            self._put(db, session_id, "lifecycle", root["revision"] + 1, {"reason": reason})
            return "cancelled"

        return self._mutate(
            session_id,
            request_id,
            expected_revision,
            {"reason": reason},
            "cancel",
            callback,
            exempt=True,
        )

    def correct(self, session_id, request_id, expected_revision, correction, *, protocol_version=1):
        _protocol(protocol_version)
        _text(correction, 8192)

        def callback(db, session, root):
            db.execute("UPDATE roots SET stale=1 WHERE id=?", (root["id"],))
            self._store_correction(
                db,
                session_id,
                self._correction_record(session_id, root["revision"] + 1, correction),
            )
            return "corrected"

        # An invalidation must remain possible after exhaustion; it never advances
        # an examination or restores a depleted semantic/operational budget.
        return self._mutate(
            session_id,
            request_id,
            expected_revision,
            {"correction": correction},
            "correct",
            callback,
            exempt=True,
        )

    def resume(self, session_id, request_id, expected_revision, *, protocol_version=1):
        """Trusted direct operator resumption; never exposed as a caller flag."""
        _protocol(protocol_version)

        def callback(db, session, root):
            if session["execution"] != "awaiting_response" or root["stale"]:
                raise _Unavailable("inactive")
            db.execute(
                "UPDATE roots SET started=?,last_clock=? WHERE id=?",
                (self.clock(), self.clock(), root["id"]),
            )
            return "resumed"

        return self._mutate(
            session_id, request_id, expected_revision, {}, "resume", callback, exempt=True
        )

    def purge_source(self, source_hash):
        """Trusted direct logical purge; no claim of forensic/backups erasure."""
        if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
            raise ValueError("invalid source hash")

        def action(db, _policy):
            db.execute("INSERT OR IGNORE INTO tombstones VALUES (?)", (source_hash,))
            affected = [
                row[0]
                for row in db.execute(
                    "SELECT DISTINCT s.root FROM dependencies d JOIN sessions s ON s.id=d.session WHERE d.hash=?",
                    (source_hash,),
                )
            ]
            for rid in affected:
                for row in db.execute(
                    "SELECT id,engine FROM sessions WHERE root=?", (rid,)
                ).fetchall():
                    raw = json.loads(row["engine"])
                    for key in ("seed", "claim", "failure"):
                        raw[key] = ""
                    db.execute("DELETE FROM artifacts WHERE session=?", (row["id"],))
                    db.execute(
                        "UPDATE sessions SET purged=1,engine=? WHERE id=?", (_json(raw), row["id"])
                    )
                db.execute("UPDATE roots SET stale=1,revision=revision+1 WHERE id=?", (rid,))
            return {
                "status": "ok",
                "affected_roots": len(affected),
                "purge_scope": "all_source_bearing_root_derivatives",
                "forensic_erasure": False,
            }

        return self._run(action)
