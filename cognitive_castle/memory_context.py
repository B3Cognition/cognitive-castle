"""Bounded exact context and explicitly attributed work references."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .fast_memory import _Corrupt, _Missing, _json, _string
from .memory_capture import ERRORS, coverage

MAX_CONTEXT_BYTES = 8192
_JOIN = " FROM capture_chunk_scopes a JOIN chunks c ON c.id=a.chunk_id JOIN capture_sources s ON s.source_key=a.source_key "
_COLUMNS = "c.id,substr(c.text,1,8193) AS text,substr(c.provenance,1,513) AS provenance,c.text_hash,c.start,c.end,json_extract(s.value,'$.generation') AS current_generation,a.source_time AS source_time"
_WORKSPACE = "a.workspace"


def _scope(workspace, namespace):
    _string(workspace, 2048, "workspace")
    if not Path(workspace).is_absolute() or ".." in Path(workspace).parts:
        raise ValueError("absolute workspace required")
    if not isinstance(namespace, str) or not re.fullmatch(r"[a-z0-9_-]{1,32}", namespace):
        raise ValueError("trusted namespace required")


def _table(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone()


def _ensure(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS work_context (namespace TEXT,workspace TEXT,revision INTEGER NOT NULL,value TEXT NOT NULL,PRIMARY KEY(namespace,workspace))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS work_context_receipts (namespace TEXT,workspace TEXT,request_id TEXT,digest TEXT NOT NULL,result TEXT NOT NULL,PRIMARY KEY(namespace,workspace,request_id))"
    )


def _source_row(conn, source_id, workspace):
    if not _table(conn, "capture_chunk_scopes"):
        return None
    return conn.execute(
        "SELECT " + _COLUMNS + _JOIN + " WHERE c.id=? AND " + _WORKSPACE + "=?",
        (source_id, workspace),
    ).fetchone()


def _excerpt(row):
    try:
        text = _string(row["text"], 8192, "persisted chunk")
        if hashlib.sha256(text.encode()).hexdigest() != row["text_hash"]:
            raise ValueError("source checksum mismatch")
        caller = json.loads(_string(row["provenance"], 512, "provenance"))
        if not isinstance(caller, dict):
            raise ValueError("provenance")
        return {
            "source_id": row["id"],
            "expected_hash": row["text_hash"],
            "role": caller.get("role", "unknown"),
            "text": text[:512],
            "offset": 0,
            "next_offset": min(512, len(text)),
            "truncated": len(text) > 512,
            "source_key": caller.get("source"),
            "generation": caller.get("generation"),
            "current_generation": row["current_generation"],
            "record_start": caller.get("record_start"),
            "record_end": caller.get("record_end"),
        }
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise _Corrupt("invalid context source") from exc


def update_context(
    store, workspace, *, namespace, request_id, expected_revision, status, source_ids
):
    """Record host-attributed work status against exact, workspace-scoped evidence."""
    _scope(workspace, namespace)
    _string(request_id, 128, "request_id")
    if type(expected_revision) is not int or not 0 <= expected_revision < 2**63 - 1:
        raise ValueError("revision")
    if status not in ("active", "completed", "cancelled"):
        raise ValueError("work status")
    if (
        not isinstance(source_ids, list)
        or not 1 <= len(source_ids) <= 8
        or any(
            not isinstance(i, str) or not re.fullmatch(r"memory:[a-f0-9]{64}", i)
            for i in source_ids
        )
        or len(set(source_ids)) != len(source_ids)
    ):
        raise ValueError("source references")
    digest = hashlib.sha256(
        _json([workspace, expected_revision, status, source_ids]).encode()
    ).hexdigest()
    try:
        with store._connect(True) as conn:
            _ensure(conn)
            prior = conn.execute(
                "SELECT digest,result FROM work_context_receipts WHERE namespace=? AND workspace=? AND request_id=?",
                (namespace, workspace, request_id),
            ).fetchone()
            if prior:
                return (
                    json.loads(prior["result"])
                    if prior["digest"] == digest
                    else {"status": "conflict"}
                )
            old = conn.execute(
                "SELECT revision FROM work_context WHERE namespace=? AND workspace=?",
                (namespace, workspace),
            ).fetchone()
            revision = old["revision"] if old else 0
            if revision != expected_revision:
                return {"status": "stale", "revision": revision}
            refs = []
            for identity in source_ids:
                row = _source_row(conn, identity, workspace)
                if row is None:
                    return {"status": "scope_mismatch"}
                item = _excerpt(row)
                refs.append({"source_id": identity, "expected_hash": item["expected_hash"]})
            value = {
                "status": status,
                "revision": revision + 1,
                "sources": refs,
                "attribution": "host_recorded_not_independently_verified",
            }
            conn.execute(
                "INSERT INTO work_context VALUES (?,?,?,?) ON CONFLICT(namespace,workspace) DO UPDATE SET revision=excluded.revision,value=excluded.value",
                (namespace, workspace, revision + 1, _json(value)),
            )
            result = {"status": "ok", "revision": revision + 1}
            conn.execute(
                "INSERT INTO work_context_receipts VALUES (?,?,?,?,?)",
                (namespace, workspace, request_id, digest, _json(result)),
            )
        return result
    except ERRORS as exc:
        return store._error(exc)


def _fit(result, item):
    result["sources"].append(item)
    while len(_json(result).encode()) > MAX_CONTEXT_BYTES:
        if not item["text"]:
            result["sources"].pop()
            return False
        item["text"] = item["text"][: len(item["text"]) // 2]
        item["next_offset"] = len(item["text"])
        item["truncated"] = True
    return True


def _work_state(raw):
    try:
        state = json.loads(_string(raw, 4096, "work state"))
        if (
            not isinstance(state, dict)
            or state.get("status") not in ("active", "completed", "cancelled")
            or type(state.get("revision")) is not int
            or state["revision"] < 1
            or state.get("attribution") != "host_recorded_not_independently_verified"
            or not isinstance(state.get("sources"), list)
            or not 1 <= len(state["sources"]) <= 8
        ):
            raise ValueError("work state")
        for ref in state["sources"]:
            if (
                not isinstance(ref, dict)
                or not re.fullmatch(r"memory:[a-f0-9]{64}", ref.get("source_id", ""))
                or not re.fullmatch(r"[a-f0-9]{64}", ref.get("expected_hash", ""))
            ):
                raise ValueError("work reference")
        return state
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise _Corrupt("invalid work state") from exc


def restore_context(store, workspace, *, namespace, limit=8):
    """Restore references plus recent user/assistant evidence under a fixed byte cap."""
    _scope(workspace, namespace)
    if type(limit) is not int or not 1 <= limit <= 8:
        raise ValueError("limit")
    observed = coverage(store)
    if observed["status"] != "ok":
        return observed
    result = {
        "status": "ok",
        "workspace": workspace,
        "sources": [],
        "work_state": None,
        "authority": "historical_evidence_not_current_instructions",
        "coverage": observed,
        "coverage_scope": "all_observed_sources",
        "selection": "bounded_workspace_context",
    }
    try:
        with store._connect() as conn:
            if _table(conn, "work_context"):
                row = conn.execute(
                    "SELECT substr(value,1,4097) FROM work_context WHERE namespace=? AND workspace=?",
                    (namespace, workspace),
                ).fetchone()
                if row:
                    result["work_state"] = _work_state(row[0])
            if not _table(conn, "capture_chunk_scopes"):
                if result["work_state"]:
                    return {"status": "unavailable", "reason": "work_source_scope_unverified"}
                return result
            selected = []
            if result["work_state"]:
                for ref in result["work_state"]["sources"]:
                    row = _source_row(conn, ref["source_id"], workspace)
                    if row is None or row["text_hash"] != ref["expected_hash"]:
                        return {"status": "corrupt", "reason": "work_source_missing"}
                    selected.append(row)
            # Reserve slots for user intent so a burst of assistant commentary cannot
            # evict all user requirements. Both groups are bounded before materializing.
            recent = []
            for roles in (("user", "human"), ("assistant", "assistant")):
                recent.extend(
                    conn.execute(
                        "SELECT "
                        + _COLUMNS
                        + _JOIN
                        + " WHERE "
                        + _WORKSPACE
                        + "=? AND a.generation=json_extract(s.value,'$.generation') AND json_extract(c.provenance,'$.role') IN (?,?) ORDER BY source_time DESC,CAST(json_extract(c.provenance,'$.record_start') AS INTEGER) DESC,c.start DESC LIMIT ?",
                        (
                            workspace,
                            *roles,
                            max(1, limit // 2) if roles[0] == "assistant" else limit,
                        ),
                    ).fetchall()
                )
            # Give up to half the packet to recent user intent, then use chronological
            # order for remaining space; pinned explicit work references come first.
            users = [
                r for r in recent if json.loads(r["provenance"]).get("role") in ("user", "human")
            ]
            selected.extend(users[: max(1, limit // 2)])
            selected.extend(
                sorted(
                    recent,
                    key=lambda r: (
                        r["source_time"] or 0,
                        json.loads(r["provenance"]).get("record_start", 0),
                        r["start"],
                    ),
                    reverse=True,
                )
            )
            seen = set()
            for row in selected:
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                if len(result["sources"]) >= limit or not _fit(result, _excerpt(row)):
                    break
        if len(_json(result).encode()) > MAX_CONTEXT_BYTES:
            return {"status": "unavailable", "reason": "context_output_limit"}
        return result
    except _Missing:
        return result
    except ERRORS as exc:
        return store._error(exc)
