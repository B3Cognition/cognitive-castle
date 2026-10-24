"""Deterministic Stage 5 ranking without a native engine or model.

The legacy ``soar_*`` audit keys and multiplicative score semantics remain
compatible. Each call returns copied rows; source IDs never key rule state.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
import sys
import time

from .query_intent import classify_query


BOOST_MULTIPLIERS: dict[str, float] = {
    "recency-boost": 1.25,
    "same-project": 1.15,
    "entity-match": 1.30,
    "type-match": 1.25,
}
BOOST_CLAMP = (0.1, 10.0)
MAX_RULE_HITS = 50
RECENCY_THRESHOLD_SEC = 7 * 24 * 3600
_ROOM_TO_MEMORY_TYPE = {
    "decisions": "decision",
    "preferences": "preference",
    "milestones": "milestone",
    "problems": "problem",
    "decision": "decision",
    "preference": "preference",
    "milestone": "milestone",
    "problem": "problem",
    "emotional": "emotional",
}


def _is_recent(created_at: object, now: float) -> bool:
    """Use ISO offsets, or the host timezone for legacy naive timestamps."""
    if not isinstance(created_at, str) or not created_at:
        return False
    try:
        # Explicit conversion also supports Python 3.10's ISO parser.
        timestamp = datetime.fromisoformat(
            created_at[:-1] + "+00:00" if created_at.endswith("Z") else created_at
        ).timestamp()
    except (ValueError, TypeError, OverflowError, OSError):
        return False
    return max(0.0, now - timestamp) < RECENCY_THRESHOLD_SEC


def apply_symbolic_boosts(hits: list[dict], cfg, query: str = "") -> list[dict]:
    """Return copied hits with four built-in rule boosts and fresh audit fields.

    Score multiplication intentionally preserves the legacy behavior for negative
    scores: a multiplier greater than one makes them more negative. Input order
    is preserved here; ``apply_to_reranked`` sorts the tuple pipeline afterward.

    Explicit legacy rule paths cannot be executed. They disable this stage with
    an actionable stderr diagnostic and ``unsupported_custom_rules`` status.
    """
    if not hits:
        return []

    custom_rules = getattr(cfg, "soar_rules_path", None)
    if custom_rules:
        print(
            "[symbolic] custom .soar rules are unsupported; Stage 5 scores are unchanged. "
            "Remove CASTLE_SOAR_RULES_PATH / soar_rules_path to use the built-in Python rules.",
            file=sys.stderr,
        )
    elif len(hits) > MAX_RULE_HITS:
        print(
            f"[symbolic] limited rules to {MAX_RULE_HITS} candidates; remainder unboosted",
            file=sys.stderr,
        )

    project = os.environ.get("CASTLE_PROJECT", "default")
    query_type = classify_query(query)
    now = time.time()
    result = []
    for index, hit in enumerate(hits):
        row = dict(hit)
        score = row.get("score", 0.0)
        tags = []
        if custom_rules:
            status = "unsupported_custom_rules"
        elif index >= MAX_RULE_HITS:
            status = "candidate_limit"
        else:
            if _is_recent(row.get("created_at"), now):
                tags.append("recency-boost")
            if row.get("wing", "") == project:
                tags.append("same-project")
            if row.get("entity_match"):
                tags.append("entity-match")
            room = row.get("room")
            if (
                query_type
                and isinstance(room, str)
                and _ROOM_TO_MEMORY_TYPE.get(room) == query_type
            ):
                tags.append("type-match")
            status = "applied" if tags else "no_match"

        multiplier = 1.0
        for tag in tags:
            multiplier *= BOOST_MULTIPLIERS[tag]
        multiplier = max(BOOST_CLAMP[0], min(BOOST_CLAMP[1], multiplier))
        row.update(
            score=score * multiplier,
            score_pre_soar=score,
            soar_boost=multiplier,
            soar_tags=tags,
            symbolic_status=status,
        )
        result.append(row)
    return result


def _filed_at(row: dict) -> str:
    raw = row.get("metadata_json")
    if not isinstance(raw, str):
        return ""
    try:
        metadata = json.loads(raw)
    except (ValueError, TypeError):
        return ""
    timestamp = metadata.get("filed_at") if isinstance(metadata, dict) else None
    return timestamp if isinstance(timestamp, str) else ""


def apply_to_reranked(
    reranked: list[tuple[float, dict]], cfg, query: str = ""
) -> list[tuple[float, dict]]:
    """Use authoritative tuple scores, then stably sort new rows by adjusted score."""
    hits = [
        {**row, "score": score, "created_at": row.get("created_at") or _filed_at(row)}
        for score, row in reranked
    ]
    boosted = apply_symbolic_boosts(hits, cfg, query=query)
    return sorted(((hit["score"], hit) for hit in boosted), key=lambda item: -item[0])
