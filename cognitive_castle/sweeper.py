#!/usr/bin/env python3
"""
sweeper.py — Message-granular miner that catches what the file-level
primary miners dropped.

Algorithm, per session:

    cursor = max(timestamp of sweeper-written drawers for this session_id)
    For each user/assistant message in the jsonl:
        check deterministic ID and exact text; skip identical records
        preserve changed text at a new versioned ID; ingest unseen late IDs

Properties:

  - Idempotent on its own writes: rerunning is a no-op because drawer
    IDs are deterministic and existence is pre-checked before counting.
  - Resume-safe: deterministic IDs and text comparisons recover partial runs.
  - Timestamps are diagnostics; they never exclude an unseen late message.
  - No size caps: each drawer holds one exchange, ~1-5 KB.

Coordination with the primary file-level miners (``miner.py`` /
``convo_miner.py``) is limited: those miners chunk at a fixed char size
and do not currently stamp ``session_id``/``timestamp`` metadata that
the sweeper can key off. In practice the sweeper coordinates with its
own prior runs, and may ingest content that also got chunked into
primary-miner drawers (under different IDs). Follow-up: add uniform
``ingest_mode`` + message metadata to the primary miners so dedup spans
both paths.

Usage:
    from cognitive_castle.sweeper import sweep
    result = sweep("/path/to/session.jsonl", "/path/to/palace")
"""

from __future__ import annotations

import json
import hashlib
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from .palace import get_collection, mutation_operation

logger = logging.getLogger(__name__)


# ── JSONL parsing ────────────────────────────────────────────────────


def _flatten_content(content) -> str:
    """Normalize Claude Code's message content to a plain string.

    User messages are strings already; assistant messages are a list of
    content blocks like [{"type": "text", "text": "..."}, {"type":
    "tool_use", ...}]. All blocks are preserved verbatim — the design
    principle is "verbatim always", so tool inputs and results are
    serialized in full, never truncated.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type", "")
            if btype == "text":
                parts.append(block.get("text", ""))
            elif btype == "tool_use":
                parts.append(
                    f"[tool_use: {block.get('name', '?')} "
                    f"input={json.dumps(block.get('input', {}), default=str)}]"
                )
            elif btype == "tool_result":
                parts.append(f"[tool_result: {json.dumps(block.get('content', ''), default=str)}]")
            else:
                parts.append(f"[{btype}: {json.dumps(block, default=str)}]")
        return "\n".join(p for p in parts if p)
    return str(content)


def parse_claude_jsonl(path: str) -> Iterator[dict]:
    """Yield user/assistant records from a Claude Code .jsonl file.

    Each yield is:
        {
          "session_id": str,
          "uuid":       str,   # per-message UUID
          "timestamp":  str,   # ISO 8601
          "role":       "user" | "assistant",
          "content":    str,   # flattened text
        }

    Non-message records (progress, file-history-snapshot, system,
    queue-operation, last-prompt) are filtered out. Malformed lines are
    skipped silently — data quality is the transcript writer's problem,
    not ours.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            rtype = record.get("type")
            if rtype not in ("user", "assistant"):
                continue
            msg = record.get("message") or {}
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            timestamp = record.get("timestamp")
            if not timestamp:
                continue
            uuid = record.get("uuid")
            if not uuid:
                continue
            session_id = record.get("sessionId") or record.get("session_id")
            if not session_id:
                continue
            content = _flatten_content(msg.get("content", ""))
            if not content.strip():
                continue
            yield {
                "session_id": session_id,
                "uuid": uuid,
                "timestamp": timestamp,
                "role": role,
                "content": content,
            }


# ── Cursor resolution ────────────────────────────────────────────────


def get_palace_cursor(collection, session_id: str, *, source_file=None) -> Optional[str]:
    """Return the max timestamp of drawers for this session_id, or None.

    Parse timestamps as UTC instants, including explicit offsets. Use the
    supported source-file filter and paginated session metadata selection.

    Backend errors are logged at WARNING and surface as a `None` cursor —
    which makes the caller treat the session as empty and ingest every
    message. That's intentional: a no-cursor sweep is recovered from on
    the next run by deterministic drawer IDs, so a degraded cursor never
    causes silent data loss.
    """
    try:
        metas, offset = [], 0
        while True:
            data = collection.get(
                where={"source_file": source_file} if source_file else None,
                include=["metadatas"],
                limit=1000,
                offset=offset,
            )
            metas.extend(
                m for m in (data.get("metadatas") or []) if m and m.get("session_id") == session_id
            )
            if len(data.get("ids") or []) < 1000:
                break
            offset += 1000
    except Exception as exc:
        logger.warning(
            "sweeper: cursor lookup failed for session_id=%s (%s); "
            "treating as empty — drawers will be re-upserted idempotently.",
            session_id,
            exc,
        )
        return None
    timestamps = [m.get("timestamp") for m in metas if m and m.get("timestamp")]
    if not timestamps:
        return None

    def instant(value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (
            parsed.replace(tzinfo=timezone.utc)
            if parsed.tzinfo is None
            else parsed.astimezone(timezone.utc)
        )

    valid = []
    for value in timestamps:
        try:
            valid.append((instant(value), value))
        except (TypeError, ValueError):
            continue
    return max(valid)[1] if valid else None


# ── Sweep ────────────────────────────────────────────────────────────


def _drawer_id_for_message(session_id: str, message_uuid: str) -> str:
    """Deterministic drawer ID so upserts at the same message are no-ops.

    Uses the full session_id (not a prefix) to avoid any cross-session
    collision risk if a transcript source ever uses non-UUID session
    identifiers or shares prefixes across sessions.
    """
    return f"sweep_{session_id}_{message_uuid}"


@mutation_operation()
def sweep(
    jsonl_path: str, palace_path: str, source_label: Optional[str] = None, *, wing=None
) -> dict:
    """Ingest every user/assistant message not already represented.

    For each message in the jsonl:
      - Compare existing deterministic message IDs and exact content.
      - Skip identical rows without embedding or changing capture timestamps.
      - Keep changed text under a new ID and ingest all unseen late messages.

    Returns ``{drawers_added, drawers_already_present, drawers_skipped,
    drawers_upserted, cursor_by_session}``:

    * ``drawers_added`` — rows that did not exist before this sweep.
    * ``drawers_already_present`` — rows whose deterministic ID was
      already in the palace and were left unchanged.
    * ``drawers_skipped`` — retained compatibility counter, always zero.
    * ``drawers_updated`` — corrected messages preserved as new versions.
    * ``drawers_upserted`` — actual writes = added + updated.
    """
    collection = get_collection(palace_path, create=True)
    cursors: dict = {}

    drawers_added = 0
    drawers_already_present = 0
    drawers_skipped = 0
    drawers_upserted = 0
    drawers_updated = 0

    batch_ids: list[str] = []
    batch_docs: list[str] = []
    batch_metas: list[dict] = []
    BATCH_SIZE = 64

    def _flush():
        nonlocal drawers_added, drawers_already_present, drawers_upserted, drawers_updated
        if not batch_ids:
            return
        # Pre-flight: which IDs in this batch are already present?
        # Upsert is idempotent on data but counts as "added" would lie;
        # this pre-query makes the metric honest (Copilot PR 998 review).
        existing = collection.get(ids=list(batch_ids), include=["documents", "metadatas"])
        present = dict(zip(existing.get("ids") or [], existing.get("documents") or []))
        writes = {}
        for rid, doc, meta in zip(batch_ids, batch_docs, batch_metas):
            if present.get(rid) == doc:
                drawers_already_present += 1
                continue
            if rid in present:
                rid += "_" + hashlib.sha256(doc.encode()).hexdigest()[:24]
                version = collection.get(ids=[rid], include=["documents"])
                if version.get("documents") == [doc]:
                    drawers_already_present += 1
                    continue
                drawers_updated += 1
            else:
                drawers_added += 1
            writes[rid] = (doc, meta)
        if writes:
            collection.upsert(
                ids=list(writes),
                documents=[v[0] for v in writes.values()],
                metadatas=[v[1] for v in writes.values()],
            )
            drawers_upserted += len(writes)
        batch_ids.clear()
        batch_docs.clear()
        batch_metas.clear()

    for rec in parse_claude_jsonl(jsonl_path):
        sid = rec["session_id"]
        if sid not in cursors:
            cursors[sid] = get_palace_cursor(
                collection, sid, source_file=source_label or jsonl_path
            )

        drawer_id = _drawer_id_for_message(sid, rec["uuid"])
        if wing:
            drawer_id += (
                "_"
                + hashlib.sha256(f"{Path(jsonl_path).resolve()}|{wing}".encode()).hexdigest()[:24]
            )
        document = f"{rec['role'].upper()}: {rec['content']}"
        metadata = {
            "session_id": sid,
            "timestamp": rec["timestamp"],
            "message_uuid": rec["uuid"],
            "role": rec["role"],
            "source_file": source_label or jsonl_path,
            "filed_at": datetime.now(timezone.utc).isoformat(),
            "ingest_mode": "sweep",
            "representation": "sweep",
            "source_revision": hashlib.sha256(document.encode()).hexdigest(),
            "ingest_complete": True,
        }
        if wing:
            metadata["wing"] = wing

        batch_ids.append(drawer_id)
        batch_docs.append(document)
        batch_metas.append(metadata)

        if len(batch_ids) >= BATCH_SIZE:
            _flush()

    _flush()

    return {
        "drawers_added": drawers_added,
        "drawers_already_present": drawers_already_present,
        "drawers_upserted": drawers_upserted,
        "drawers_updated": drawers_updated,
        "drawers_skipped": drawers_skipped,
        "cursor_by_session": cursors,
    }


def sweep_directory(dir_path: str, palace_path: str) -> dict:
    """Sweep every .jsonl file in a directory (recursive).

    Returns aggregated summary across all files. ``files_attempted``
    includes files that raised, so the count reflects discovery rather
    than only successes; ``files_succeeded`` is the subset that
    completed without error.
    """
    dir_p = Path(dir_path).expanduser().resolve()
    files = sorted(dir_p.rglob("*.jsonl"))

    total_added = 0
    total_already_present = 0
    total_skipped = 0
    per_file = []

    failures: list[dict] = []
    for f in files:
        try:
            result = sweep(str(f), palace_path, source_label=str(f))
        except Exception as exc:
            logger.error("sweeper: sweep failed on %s: %s", f, exc)
            print(f"  WARNING: sweep failed on {f}: {exc}", file=sys.stderr)
            failures.append({"file": str(f), "error": str(exc)})
            continue
        total_added += result["drawers_added"]
        total_already_present += result.get("drawers_already_present", 0)
        total_skipped += result["drawers_skipped"]
        per_file.append(
            {
                "file": str(f),
                "added": result["drawers_added"],
                "already_present": result.get("drawers_already_present", 0),
                "skipped": result["drawers_skipped"],
            }
        )

    return {
        "files_attempted": len(files),
        "files_succeeded": len(per_file),
        "drawers_added": total_added,
        "drawers_already_present": total_already_present,
        "drawers_skipped": total_skipped,
        "per_file": per_file,
        "failures": failures,
    }
