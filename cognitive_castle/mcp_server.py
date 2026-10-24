#!/usr/bin/env python3
"""
Cognitive Castle MCP Server — read/write palace access for Claude Code
================================================================
Install: claude mcp add castle -- castle-mcp [--palace /path/to/palace]

Tools (read):
  castle_status          — total drawers, wing/room breakdown
  castle_list_wings      — all wings with drawer counts
  castle_list_rooms      — rooms within a wing
  castle_get_taxonomy    — full wing → room → count tree
  castle_search          — exact live and historical memory, optional scopes
  castle_check_duplicate — check if content already exists before filing
  castle_wake_up         — L0 + L1 wake-up context (~600–900 tokens)
  castle_info_score      — nn_novelty score for arbitrary text (v3.4.0 research)
  castle_prune_suggest   — flag low-info drawers as pruning candidates (read-only)

Tools (write):
  castle_memory_remember — store exact text for unified recall under trusted policy
  castle_add_drawer      — legacy-only write; use castle_memory_remember for unified recall
  castle_delete_drawer   — remove a drawer by ID

Tools (maintenance):
  castle_reconnect       — force cache invalidation and reconnect after external writes
"""

import os
import sys

# --- MCP stdio protection (issue #225) -----------------------------------
# The MCP protocol multiplexes JSON-RPC over stdio: stdout MUST carry only
# valid JSON-RPC messages, stderr is for human-readable logs. Some
# transitive dependencies (sentence-transformers, torch, lancedb) may print
# banners and error messages directly to stdout — sometimes at C level —
# which breaks Claude Desktop's JSON parser. Redirect stdout → stderr at
# both the Python and file-descriptor level before heavy imports, then
# restore the real stdout in main() before entering the protocol loop.
_REAL_STDOUT = sys.stdout
_REAL_STDOUT_FD = None
try:
    _REAL_STDOUT_FD = os.dup(1)
    os.dup2(2, 1)
except (OSError, AttributeError):
    # Environments without fd-level stdio (embedded interpreters, some test
    # harnesses). The Python-level redirect below still applies.
    pass
sys.stdout = sys.stderr

import argparse  # noqa: E402  (deferred until after stdio protection above)
import json  # noqa: E402
import logging  # noqa: E402
import hashlib  # noqa: E402
import time  # noqa: E402
from datetime import date, datetime  # noqa: E402
from pathlib import Path  # noqa: E402

from .config import (  # noqa: E402
    CognitiveCastleConfig,
    sanitize_kg_value,
    sanitize_name,
    sanitize_content,
)
from .version import __version__  # noqa: E402
from .query_sanitizer import sanitize_query  # noqa: E402
from .searcher import search_memories  # noqa: E402

from .knowledge_graph import KnowledgeGraph  # noqa: E402


def _get_palace_collection(*args, **kwargs):
    from .palace import get_collection

    return get_collection(*args, **kwargs)


def _graph_call(name):
    def call(*args, **kwargs):
        from . import palace_graph

        return getattr(palace_graph, name)(*args, **kwargs)

    return call


traverse = _graph_call("traverse")
find_tunnels = _graph_call("find_tunnels")
graph_stats = _graph_call("graph_stats")
create_tunnel = _graph_call("create_tunnel")
list_tunnels = _graph_call("list_tunnels")
delete_tunnel = _graph_call("delete_tunnel")
follow_tunnels = _graph_call("follow_tunnels")

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
logger = logging.getLogger("castle_mcp")


def _parse_args():
    parser = argparse.ArgumentParser(description="Cognitive Castle MCP Server")
    parser.add_argument(
        "--palace",
        metavar="PATH",
        help="Path to the palace directory (overrides config file and env var)",
    )
    args, unknown = parser.parse_known_args()
    if unknown:
        logger.debug("Ignoring unknown args: %s", unknown)
    return args


_args = _parse_args()

if _args.palace:
    os.environ["CASTLE_PALACE_PATH"] = os.path.abspath(_args.palace)

_config = CognitiveCastleConfig()
# Only override KG path when --palace is explicitly provided; otherwise use
# KnowledgeGraph's default (~/.castle/knowledge_graph.sqlite3).
if _args.palace:
    _kg = KnowledgeGraph(db_path=os.path.join(_config.palace_path, "knowledge_graph.sqlite3"))
else:
    _kg = KnowledgeGraph()


_collection_cache = None


# ==================== WRITE-AHEAD LOG ====================
# Every write operation is logged to a JSONL file before execution.
# This provides an audit trail for detecting memory poisoning and
# enables review/rollback of writes from external or untrusted sources.

_WAL_DIR = Path(os.path.expanduser("~/.castle/wal"))
_WAL_DIR.mkdir(parents=True, exist_ok=True)
try:
    _WAL_DIR.chmod(0o700)
except (OSError, NotImplementedError):
    pass
_WAL_FILE = _WAL_DIR / "write_log.jsonl"
# Atomically create WAL file with restricted permissions (no TOCTOU race).
# os.open with O_CREAT|O_WRONLY and mode 0o600 creates the file if absent
# or opens it if present, both in a single syscall.
try:
    _fd = os.open(str(_WAL_FILE), os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(_fd)
except (OSError, NotImplementedError):
    pass

# Keys whose values should be redacted in WAL entries to avoid logging sensitive content
_WAL_REDACT_KEYS = frozenset(
    {"content", "content_preview", "document", "entry", "entry_preview", "query", "text"}
)


def _wal_log(operation: str, params: dict, result: dict = None):
    """Append a write operation to the write-ahead log."""
    # Redact sensitive content from params before logging
    safe_params = {}
    for k, v in params.items():
        if k in _WAL_REDACT_KEYS:
            safe_params[k] = f"[REDACTED {len(v)} chars]" if isinstance(v, str) else "[REDACTED]"
        else:
            safe_params[k] = v
    entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation,
        "params": safe_params,
        "result": result,
    }
    try:
        fd = os.open(str(_WAL_FILE), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception as e:
        logger.error(f"WAL write failed: {e}")


def _get_collection(create=False):
    """Return the LanceDB collection, caching between calls."""
    global _collection_cache, _metadata_cache, _metadata_cache_time, _counts_cache
    if _collection_cache is None:
        try:
            _collection_cache = _get_palace_collection(
                _config.palace_path,
                collection_name=_config.collection_name,
                create=create,
            )
            _metadata_cache = None
            _counts_cache = None
            _metadata_cache_time = 0
        except Exception:
            logger.debug("_get_collection failed", exc_info=True)
            return None
    return _collection_cache


def _no_palace():
    return {
        "error": "No palace found",
        "hint": "Run: castle init <dir> && castle mine <dir>",
    }


# ==================== HELPERS ====================


def _fetch_all_metadata(col, where=None):
    """Fetch every matching row's metadata in one call, bounded by an explicit limit.

    This used to page in 1000-row chunks with ``offset``. The LanceDB backend
    implements ``offset`` by scanning ``offset + limit`` rows and slicing the
    head off in Python, so every page re-scanned the table from the start:
    quadratic, roughly 44 minutes for a full pass over a 278K-drawer palace.
    One call with ``limit=count`` is a single linear scan; the explicit limit
    is what keeps the backend's 100 000-row default from silently truncating.
    """
    total = col.count()
    if not total:
        return []
    kwargs = {"include": ["metadatas"], "limit": total}
    if where:
        kwargs["where"] = where
    batch = col.get(**kwargs)
    return batch["metadatas"] or []


_metadata_cache = None
_metadata_cache_time = 0
_METADATA_CACHE_TTL = 5.0  # seconds
_MAX_RESULTS = 100  # upper bound for search/list limit params


def _get_cached_metadata(col, where=None):
    """Return cached metadata if fresh, else fetch and cache."""
    global _metadata_cache, _metadata_cache_time
    now = time.time()
    if (
        where is None
        and _metadata_cache is not None
        and (now - _metadata_cache_time) < _METADATA_CACHE_TTL
    ):
        return _metadata_cache
    result = _fetch_all_metadata(col, where=where)
    if where is None:
        _metadata_cache = result
        _metadata_cache_time = now
    return result


_counts_cache = None
_counts_cache_key = None
_counts_cache_time = 0


def _wing_room_counts(col, wing: str = None) -> dict:
    """Count drawers per wing, per room and per (wing, room) without loading rows.

    Backends that can stream columns (``iter_columns``) supply just ``wing``
    and ``room``: two short strings per drawer, no text, vector or metadata
    JSON. Fetching full metadata for a status call held every row of the
    palace in this long-lived server process. Other backends fall back to
    the metadata rows.
    """
    global _counts_cache, _counts_cache_key, _counts_cache_time
    wings: dict = {}
    rooms: dict = {}
    taxonomy: dict = {}
    if hasattr(col, "iter_columns"):
        now = time.time()
        key = (id(col), col.count())
        if (
            _counts_cache is not None
            and _counts_cache_key == key
            and (now - _counts_cache_time) < _METADATA_CACHE_TTL
        ):
            pairs = _counts_cache
        else:
            pairs = {}
            for batch in col.iter_columns(["wing", "room"]):
                for w, r in zip(batch.get("wing", ()), batch.get("room", ())):
                    pair = (w or "unknown", r or "unknown")
                    pairs[pair] = pairs.get(pair, 0) + 1
            _counts_cache, _counts_cache_key, _counts_cache_time = pairs, key, now
        for (w, r), n in pairs.items():
            if wing and w != wing:
                continue
            wings[w] = wings.get(w, 0) + n
            rooms[r] = rooms.get(r, 0) + n
            by_room = taxonomy.setdefault(w, {})
            by_room[r] = by_room.get(r, 0) + n
        return {"wings": wings, "rooms": rooms, "taxonomy": taxonomy}
    where = {"wing": wing} if wing else None
    for m in _get_cached_metadata(col, where=where):
        m = m or {}
        w = m.get("wing", "unknown")
        r = m.get("room", "unknown")
        wings[w] = wings.get(w, 0) + 1
        rooms[r] = rooms.get(r, 0) + 1
        by_room = taxonomy.setdefault(w, {})
        by_room[r] = by_room.get(r, 0) + 1
    return {"wings": wings, "rooms": rooms, "taxonomy": taxonomy}


def _sanitize_optional_name(value: str = None, field_name: str = "name") -> str:
    """Validate optional wing/room-style filters."""
    if value is None or not value.strip():
        return None
    return sanitize_name(value, field_name)


# ==================== READ TOOLS ====================


def tool_status():
    # create=True when the palace directory exists so an initialized-but-unmined
    # palace shows total_drawers=0 instead of "No palace found".
    palace_exists = os.path.isdir(_config.palace_path)
    col = _get_collection(create=palace_exists)
    if not col:
        return _no_palace()
    count = col.count()
    wings = {}
    rooms = {}
    result = {
        "total_drawers": count,
        "wings": wings,
        "rooms": rooms,
        "protocol": PALACE_PROTOCOL,
        "aaak_dialect": AAAK_SPEC,
    }
    try:
        counts = _wing_room_counts(col)
        wings.update(counts["wings"])
        rooms.update(counts["rooms"])
    except Exception as e:
        logger.exception("tool_status metadata fetch failed")
        result["error"] = str(e)
        result["partial"] = True
    return result


# ── AAAK Dialect Spec ─────────────────────────────────────────────────────────
# Injected into the MCP `initialize` response's `instructions` field at
# session start, so MCP-compliant clients (Claude Code, etc.) bake it
# into the system prompt automatically. Also returned by castle_status
# and castle_get_aaak_spec for legacy/explicit callers.

PALACE_PROTOCOL = """Castle is a local verbatim memory palace storing this user's past
conversations, decisions, and entity facts. The palace is on the
user's machine. Core memory stays local; optional external SUE processing
sends only an explicitly selected bundle to the chosen provider.

Behavioral protocol:
- Discover castle_brain_capabilities before the bounded brain workflow. For
  substantial ambiguous work, use castle_brain_recall under trusted local
  exposure policy, then castle_problem_begin with the original request, your
  interpretation and exact obligation spans. Protocol version 1 is required.
  Read question/schema/source_map pages; answer as the active assistant through
  castle_problem_respond. Preserve its root/session IDs, revision and budgets;
  never create a fresh root to evade a stop. Record new corrections before
  advancing. Status and pages allow restart without a model or re-search.
  Skip examination for trivial edits and simple recall. Local source exposure
  requires operator configuration; tool arguments cannot grant it. Unavailable
  safe recall is an explicit limitation, not permission to use dense search.
- castle_article_assess measures article form/readability separately from SUE.
  Article scores do not establish truth, and host-assisted SUE is an attributed
  structured self-check, not independent verification. Neither enables hooks.
- Before answering about a person, project, design decision, or past
  event: retrieve evidence FIRST. Never guess. Default castle_search and
  castle_brain_recall use the same bounded live/history catalog under trusted
  host policy. Read exact pages with castle_memory_read and the source hash;
  incomplete coverage is explicit. Selected legacy search modes can load models.
- Do not automatically file design rationale, write diary summaries, mutate
  knowledge-graph facts, or start capture. Preserve existing paused hooks.
  When explicitly asked to remember content, preserve it verbatim with
  castle_memory_remember under trusted host policy. Explicit legacy writes using
  castle_add_drawer require the authorized model and exposure scope and may load
  embedding models; they are not immediately visible in unified recall.
- A separately configured provider can examine selected requirements through
  castle_sue_review / castle_sue_status when explicitly requested. It is not an
  automatic fallback for the host-assisted problem loop or unavailable recall.
  External processing requires authorization for that selected source bundle.
  Findings remain attributed interpretations, not truth or implementation proof.

Core memory preserves exact source words. A stored statement is evidence of
what was said, not a guarantee of factual truth. Tool availability and trusted
policy determine which operations this host can actually perform."""

AAAK_SPEC = """AAAK is a compressed memory dialect that Cognitive Castle uses for efficient storage.
It is designed to be readable by both humans and LLMs without decoding.

FORMAT:
  ENTITIES: 3-letter uppercase codes. ENT1=PersonAlpha, ENT2=PersonBeta, ENT3=PersonGamma.
  EMOTIONS: *action markers* before/during text. *warm*=joy, *fierce*=determined, *raw*=vulnerable, *bloom*=tenderness.
  STRUCTURE: Pipe-separated fields. FAM: family | PROJ: projects | ⚠: warnings/reminders.
  DATES: ISO format (2026-03-31). COUNTS: Nx = N mentions (e.g., 570x).
  IMPORTANCE: ★ to ★★★★★ (1-5 scale).
  HALLS: hall_facts, hall_events, hall_discoveries, hall_preferences, hall_advice.
  WINGS: wing_user, wing_agent, wing_team, wing_code, wing_myproject, wing_hardware, wing_ue5, wing_ai_research.
  ROOMS: Hyphenated slugs representing named ideas (e.g., lancedb-setup, gpu-pricing).

EXAMPLE:
  FAM: ENT1→♡ENT2 | 2D(kids): ENT3(18,sports) ENT4(11,chess+swim) | ENT5(contributor)

Read AAAK naturally — expand codes mentally, treat *markers* as emotional context.
When WRITING AAAK: use entity codes, mark emotions, keep structure tight."""


def _build_instructions() -> str:
    """Build startup context without opening or scanning the palace.

    MCP clients enforce a short handshake deadline. Live statistics belong
    in castle_status: even a metadata-only scan can exceed that deadline
    on a large palace or block on storage I/O.
    """
    return "\n".join(
        [PALACE_PROTOCOL, "", AAAK_SPEC, "", "Use castle_status for current palace statistics."]
    )


def tool_list_wings():
    col = _get_collection()
    if not col:
        return _no_palace()
    wings = {}
    result = {"wings": wings}
    try:
        wings.update(_wing_room_counts(col)["wings"])
    except Exception as e:
        logger.exception("tool_list_wings metadata fetch failed")
        result["error"] = str(e)
        result["partial"] = True
    return result


def tool_list_rooms(wing: str = None):
    try:
        wing = _sanitize_optional_name(wing, "wing")
    except ValueError as e:
        return {"error": str(e)}
    col = _get_collection()
    if not col:
        return _no_palace()
    rooms = {}
    result = {"wing": wing or "all", "rooms": rooms}
    try:
        rooms.update(_wing_room_counts(col, wing=wing)["rooms"])
    except Exception as e:
        logger.exception("tool_list_rooms metadata fetch failed")
        result["error"] = str(e)
        result["partial"] = True
    return result


def tool_get_taxonomy():
    col = _get_collection()
    if not col:
        return _no_palace()
    taxonomy = {}
    result = {"taxonomy": taxonomy}
    try:
        taxonomy.update(_wing_room_counts(col)["taxonomy"])
    except Exception as e:
        logger.exception("tool_get_taxonomy metadata fetch failed")
        result["error"] = str(e)
        result["partial"] = True
    return result


def tool_search(
    query: str,
    limit: int = 5,
    wing: str = None,
    room: str = None,
    max_distance: float = None,
    min_similarity: float = None,
    context: str = None,
    mode: str = None,
    workspace: str = None,
    match: str = "all",
    cursor: str = None,
):
    # Mode validation in the function body (not the JSON schema) so the
    # error message is specific to Castle.
    if mode is not None and mode not in ("fast", "standard", "boosted", "max"):
        return {"error": (f"invalid mode '{mode}'. Must be one of: fast, standard, boosted, max")}

    limit = max(1, min(limit, _MAX_RESULTS))
    try:
        wing = _sanitize_optional_name(wing, "wing")
        room = _sanitize_optional_name(room, "room")
    except ValueError as e:
        return {"error": str(e)}

    # Backwards compat: convert old similarity scale (higher=stricter) to
    # distance scale (lower=stricter). Similarity 0.8 → distance 0.2.
    if mode is None and (max_distance is not None or min_similarity is not None):
        return {
            "status": "invalid_request",
            "error": "Similarity options require an explicit legacy mode",
        }
    dist = (1.0 - min_similarity) if min_similarity is not None else max_distance
    if dist is None:
        dist = None if mode is None else 1.5
    # Mitigate system prompt contamination (Issue #333)
    sanitized = sanitize_query(query)

    result = search_memories(
        sanitized["clean_query"],
        palace_path=_config.palace_path,
        wing=wing,
        room=room,
        n_results=limit,
        max_distance=dist,
        mode=mode,
        workspace=workspace,
        match=match,
        cursor=cursor,
    )

    # Attach sanitizer metadata for transparency
    if sanitized["was_sanitized"]:
        result["query_sanitized"] = True
        result["sanitizer"] = {
            "method": sanitized["method"],
            "original_length": sanitized["original_length"],
            "clean_length": sanitized["clean_length"],
            "clean_query": sanitized["clean_query"],
        }
    if context:
        result["context_received"] = True

    # Strip internal metadata field before returning to the caller.
    hits = result.get("results")
    if hits and mode is not None:
        for h in hits:
            h.pop("metadata", None)
        result["results"] = hits

    return result


def tool_check_duplicate(content: str, threshold: float = 0.9):
    col = _get_collection()
    if not col:
        return _no_palace()
    try:
        results = col.query(
            query_texts=[content],
            n_results=5,
            include=["metadatas", "documents", "distances"],
        )
        duplicates = []
        if results["ids"] and results["ids"][0]:
            for i, drawer_id in enumerate(results["ids"][0]):
                dist = results["distances"][0][i]
                similarity = round(1 - dist, 3)
                if similarity >= threshold:
                    meta = results["metadatas"][0][i]
                    doc = results["documents"][0][i]
                    duplicates.append(
                        {
                            "id": drawer_id,
                            "wing": meta.get("wing", "?"),
                            "room": meta.get("room", "?"),
                            "similarity": similarity,
                            "content": doc[:200] + "..." if len(doc) > 200 else doc,
                        }
                    )
        return {
            "is_duplicate": len(duplicates) > 0,
            "matches": duplicates,
        }
    except Exception:
        logger.exception("check_duplicate failed")
        return {"error": "Duplicate check failed"}


def tool_get_aaak_spec():
    """Return the AAAK dialect specification."""
    return {"aaak_spec": AAAK_SPEC}


def tool_info_score(text: str, wing: str = None, top_k: int = 5):
    """Score how novel `text` is against the palace via nn_novelty.

    Practical use of the v3.4.0 research finding: on a 65k-drawer palace,
    rho(nn_novelty, LLE_recon_residual) = 0.982 — so this cheap O(1)
    score is a strong proxy for information content.

    Returns novelty in [0, 2] plus a coarse band (`low` < 0.10 / `medium`
    < 0.50 / `high` >= 0.50) calibrated against the empirical palace
    distribution.
    """
    from .info_score import score_novelty

    try:
        result = score_novelty(text=text, top_k=top_k, wing=wing)
    except ValueError as e:
        return {"error": str(e)}
    except Exception:
        logger.exception("info_score failed")
        return {"error": "info-score failed"}
    return result.as_dict()


def tool_wake_up(wing: str = None):
    """Return the L0 + L1 wake-up context (~600–900 tokens).

    Practical use: at session start, an AI agent calls this once and
    receives the palace's identity + essential story layers as a single
    text block — a fast, cheap way to remind the model what it knows
    about the user and their projects without a full search.

    Optional `wing` filter scopes the wake-up to a single project.
    """
    from .layers import MemoryStack
    from .config import CognitiveCastleConfig

    try:
        cfg = CognitiveCastleConfig()
        stack = MemoryStack(palace_path=cfg.palace_path)
        text = stack.wake_up(wing=wing)
    except Exception:
        logger.exception("wake_up failed")
        return {"error": "wake-up failed"}

    tokens = len(text) // 4  # rough estimate — same as the CLI
    return {"text": text, "estimated_tokens": tokens, "wing": wing}


def tool_prune_suggest(
    sample: int = 200, threshold: float = 0.10, wing: str = None, seed: int = 42
):
    """Flag low-information drawers as pruning candidates. Read-only.

    Samples `sample` drawers, computes nn_novelty against each drawer's
    nearest same-wing prior, and returns those below `threshold` sorted
    by novelty ascending (most duplicate-y first).

    Never touches the palace. AI agents can use this to surface
    near-duplicate content for human review — the design principle is
    "verbatim always", so nothing is auto-pruned.

    Threshold 0.10 = "low" band from the v3.4.0 research paper.
    """
    from .prune_suggest import suggest_candidates

    try:
        result = suggest_candidates(sample=sample, threshold=threshold, wing=wing, seed=seed)
    except Exception:
        logger.exception("prune_suggest failed")
        return {"error": "prune-suggest failed"}
    return result.as_dict()


def tool_traverse_graph(start_room: str, max_hops: int = 2):
    """Walk the palace graph from a room. Find connected ideas across wings."""
    max_hops = max(1, min(max_hops, 10))
    col = _get_collection()
    if not col:
        return _no_palace()
    return traverse(start_room, col=col, max_hops=max_hops)


def tool_find_tunnels(wing_a: str = None, wing_b: str = None):
    """Find rooms that bridge two wings — the hallways connecting domains."""
    try:
        wing_a = _sanitize_optional_name(wing_a, "wing_a")
        wing_b = _sanitize_optional_name(wing_b, "wing_b")
    except ValueError as e:
        return {"error": str(e)}
    col = _get_collection()
    if not col:
        return _no_palace()
    return find_tunnels(wing_a, wing_b, col=col)


def tool_graph_stats():
    """Palace graph overview: nodes, tunnels, edges, connectivity."""
    col = _get_collection()
    if not col:
        return _no_palace()
    return graph_stats(col=col)


def tool_create_tunnel(
    source_wing: str,
    source_room: str,
    target_wing: str,
    target_room: str,
    label: str = "",
    source_drawer_id: str = None,
    target_drawer_id: str = None,
):
    """Create an explicit cross-wing tunnel between two palace locations.

    Use when you notice content in one project relates to another project.
    Example: an API design discussion in project_api connects to the
    database schema in project_database.
    """
    try:
        source_wing = sanitize_name(source_wing, "source_wing")
        source_room = sanitize_name(source_room, "source_room")
        target_wing = sanitize_name(target_wing, "target_wing")
        target_room = sanitize_name(target_room, "target_room")
    except ValueError as e:
        return {"error": str(e)}
    return create_tunnel(
        source_wing,
        source_room,
        target_wing,
        target_room,
        label=label,
        source_drawer_id=source_drawer_id,
        target_drawer_id=target_drawer_id,
    )


def tool_list_tunnels(wing: str = None):
    """List all explicit cross-wing tunnels, optionally filtered by wing."""
    try:
        wing = _sanitize_optional_name(wing, "wing")
    except ValueError as e:
        return {"error": str(e)}
    return list_tunnels(wing)


def tool_delete_tunnel(tunnel_id: str):
    """Delete an explicit tunnel by its ID."""
    if not tunnel_id or not isinstance(tunnel_id, str):
        return {"error": "tunnel_id is required"}
    return delete_tunnel(tunnel_id)


def tool_follow_tunnels(wing: str, room: str):
    """Follow explicit tunnels from a room to see connected drawers in other wings."""
    try:
        wing = sanitize_name(wing, "wing")
        room = sanitize_name(room, "room")
    except ValueError as e:
        return {"error": str(e)}
    col = _get_collection()
    return follow_tunnels(wing, room, col=col)


# ==================== WRITE TOOLS ====================


def tool_add_drawer(
    wing: str, room: str, content: str, source_file: str = None, added_by: str = "mcp"
):
    """Write verbatim content only to the legacy index, checking duplicates.

    These writes are not immediately visible in unified recall. Ordinary
    remember requests should use castle_memory_remember under trusted policy.
    """
    global _metadata_cache, _counts_cache
    try:
        wing = sanitize_name(wing, "wing")
        room = sanitize_name(room, "room")
        content = sanitize_content(content)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    col = _get_collection(create=True)
    if not col:
        return _no_palace()

    drawer_id = (
        f"drawer_{wing}_{room}_{hashlib.sha256((wing + room + content).encode()).hexdigest()[:24]}"
    )

    _wal_log(
        "add_drawer",
        {
            "drawer_id": drawer_id,
            "wing": wing,
            "room": room,
            "added_by": added_by,
            "content_length": len(content),
            "content_preview": content[:200],
        },
    )

    # Idempotency: if the deterministic ID already exists, return success as a no-op.
    try:
        existing = col.get(ids=[drawer_id])
        if existing and existing["ids"]:
            return {"success": True, "reason": "already_exists", "drawer_id": drawer_id}
    except Exception:
        pass

    try:
        col.upsert(
            ids=[drawer_id],
            documents=[content],
            metadatas=[
                {
                    "wing": wing,
                    "room": room,
                    "source_file": source_file or "",
                    "chunk_index": 0,
                    "added_by": added_by,
                    "filed_at": datetime.now().isoformat(),
                }
            ],
        )
        _metadata_cache = None
        _counts_cache = None
        logger.info(f"Filed drawer: {drawer_id} → {wing}/{room}")
        return {"success": True, "drawer_id": drawer_id, "wing": wing, "room": room}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_delete_drawer(drawer_id: str):
    """Delete a single drawer by ID."""
    global _metadata_cache, _counts_cache
    col = _get_collection()
    if not col:
        return _no_palace()
    existing = col.get(ids=[drawer_id])
    if not existing["ids"]:
        return {"success": False, "error": f"Drawer not found: {drawer_id}"}

    # Log the deletion with the content being removed for audit trail
    deleted_content = existing.get("documents", [""])[0] if existing.get("documents") else ""
    deleted_meta = existing.get("metadatas", [{}])[0] if existing.get("metadatas") else {}
    _wal_log(
        "delete_drawer",
        {
            "drawer_id": drawer_id,
            "deleted_meta": deleted_meta,
            "content_preview": deleted_content[:200],
        },
    )

    try:
        col.delete(ids=[drawer_id])
        _metadata_cache = None
        _counts_cache = None
        logger.info(f"Deleted drawer: {drawer_id}")
        return {"success": True, "drawer_id": drawer_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_get_drawer(drawer_id: str):
    """Fetch a single drawer by ID. Returns full content and metadata."""
    col = _get_collection()
    if not col:
        return _no_palace()
    try:
        result = col.get(ids=[drawer_id], include=["documents", "metadatas"])
        if not result["ids"]:
            return {"error": f"Drawer not found: {drawer_id}"}
        meta = result["metadatas"][0]
        doc = result["documents"][0]
        # source_file is the absolute filesystem path written by the
        # miners. Reduce to its basename before handing it to the MCP
        # client — same threat model as the palace_path leak fix:
        # nested-agent / multi-server topologies treat the client as a
        # separate trust domain. Basename preserves citation utility.
        # Mirrors the searcher.search_memories() return shape.
        safe_meta = dict(meta) if meta else {}
        if safe_meta.get("source_file"):
            safe_meta["source_file"] = Path(safe_meta["source_file"]).name
        return {
            "drawer_id": drawer_id,
            "content": doc,
            "wing": safe_meta.get("wing", ""),
            "room": safe_meta.get("room", ""),
            "metadata": safe_meta,
        }
    except Exception as e:
        return {"error": str(e)}


def tool_list_drawers(wing: str = None, room: str = None, limit: int = 20, offset: int = 0):
    """List drawers with pagination. Optional wing/room filter."""
    limit = max(1, min(limit, _MAX_RESULTS))
    offset = max(0, offset)
    try:
        wing = _sanitize_optional_name(wing, "wing")
        room = _sanitize_optional_name(room, "room")
    except ValueError as e:
        return {"error": str(e)}
    col = _get_collection()
    if not col:
        return _no_palace()
    try:
        where = None
        conditions = []
        if wing:
            conditions.append({"wing": wing})
        if room:
            conditions.append({"room": room})
        if len(conditions) == 1:
            where = conditions[0]
        elif len(conditions) > 1:
            where = {"$and": conditions}

        kwargs = {"include": ["documents", "metadatas"], "limit": limit, "offset": offset}
        if where:
            kwargs["where"] = where
        result = col.get(**kwargs)

        drawers = []
        for i, did in enumerate(result["ids"]):
            meta = result["metadatas"][i]
            doc = result["documents"][i]
            drawers.append(
                {
                    "drawer_id": did,
                    "wing": meta.get("wing", ""),
                    "room": meta.get("room", ""),
                    "content_preview": doc[:200] + "..." if len(doc) > 200 else doc,
                }
            )
        return {
            "drawers": drawers,
            "count": len(drawers),
            "offset": offset,
            "limit": limit,
        }
    except Exception as e:
        return {"error": str(e)}


def tool_update_drawer(drawer_id: str, content: str = None, wing: str = None, room: str = None):
    """Update an existing drawer's content and/or metadata."""
    global _metadata_cache, _counts_cache

    if content is None and wing is None and room is None:
        return {"success": True, "drawer_id": drawer_id, "noop": True}

    col = _get_collection()
    if not col:
        return _no_palace()
    try:
        existing = col.get(ids=[drawer_id], include=["documents", "metadatas"])
        if not existing["ids"]:
            return {"success": False, "error": f"Drawer not found: {drawer_id}"}

        old_meta = existing["metadatas"][0]
        old_doc = existing["documents"][0]

        new_doc = old_doc
        if content is not None:
            try:
                new_doc = sanitize_content(content)
            except ValueError as e:
                return {"success": False, "error": str(e)}

        new_meta = dict(old_meta)
        if wing is not None:
            try:
                new_meta["wing"] = sanitize_name(wing, "wing")
            except ValueError as e:
                return {"success": False, "error": str(e)}
        if room is not None:
            try:
                new_meta["room"] = sanitize_name(room, "room")
            except ValueError as e:
                return {"success": False, "error": str(e)}

        _wal_log(
            "update_drawer",
            {
                "drawer_id": drawer_id,
                "old_wing": old_meta.get("wing", ""),
                "old_room": old_meta.get("room", ""),
                "new_wing": new_meta.get("wing", ""),
                "new_room": new_meta.get("room", ""),
                "content_changed": content is not None,
                "content_preview": new_doc[:200] if content is not None else None,
            },
        )

        update_kwargs = {"ids": [drawer_id]}
        if content is not None:
            update_kwargs["documents"] = [new_doc]
        update_kwargs["metadatas"] = [new_meta]
        col.update(**update_kwargs)

        _metadata_cache = None

        _counts_cache = None

        logger.info(f"Updated drawer: {drawer_id}")
        return {
            "success": True,
            "drawer_id": drawer_id,
            "wing": new_meta.get("wing", ""),
            "room": new_meta.get("room", ""),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== KNOWLEDGE GRAPH ====================


def tool_kg_query(entity: str, as_of: str = None, direction: str = "both"):
    """Query the knowledge graph for an entity's relationships."""
    try:
        entity = sanitize_kg_value(entity, "entity")
    except ValueError as e:
        return {"error": str(e)}
    if direction not in ("outgoing", "incoming", "both"):
        return {"error": "direction must be 'outgoing', 'incoming', or 'both'"}
    results = _kg.query_entity(entity, as_of=as_of, direction=direction)
    return {"entity": entity, "as_of": as_of, "facts": results, "count": len(results)}


def tool_kg_add(
    subject: str,
    predicate: str,
    object: str,
    valid_from: str = None,
    valid_to: str = None,
    source_closet: str = None,
    source_file: str = None,
    source_drawer_id: str = None,
):
    """Add a relationship to the knowledge graph.

    All temporal and provenance fields are optional. ``valid_to`` lets callers
    backfill historical facts with a known end date in a single call (instead
    of a separate ``kg_invalidate``). ``source_file`` and ``source_drawer_id``
    are RFC 002 provenance fields populated by adapters / bulk importers.

    TODO(#1283): once the ISO-8601 validation PR lands, wire ``validate_iso_date``
    over ``valid_from`` / ``valid_to`` here so malformed dates fail fast at the
    MCP boundary instead of silently producing empty query results.
    """
    try:
        subject = sanitize_kg_value(subject, "subject")
        predicate = sanitize_name(predicate, "predicate")
        object = sanitize_kg_value(object, "object")
    except ValueError as e:
        return {"success": False, "error": str(e)}

    _wal_log(
        "kg_add",
        {
            "subject": subject,
            "predicate": predicate,
            "object": object,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "source_closet": source_closet,
            "source_file": source_file,
            "source_drawer_id": source_drawer_id,
        },
    )
    triple_id = _kg.add_triple(
        subject,
        predicate,
        object,
        valid_from=valid_from,
        valid_to=valid_to,
        source_closet=source_closet,
        source_file=source_file,
        source_drawer_id=source_drawer_id,
    )
    return {"success": True, "triple_id": triple_id, "fact": f"{subject} → {predicate} → {object}"}


def tool_kg_invalidate(subject: str, predicate: str, object: str, ended: str = None):
    """Mark a fact as no longer true (set end date).

    Returns the actual ``ended`` date that was stored — when the caller omits
    ``ended``, the underlying graph stamps ``date.today()``, and the response
    reflects that resolved value (instead of the literal string ``"today"``)
    so callers can verify what was persisted.

    TODO(#1283): apply ``validate_iso_date`` to ``ended`` once that PR lands.
    """
    try:
        subject = sanitize_kg_value(subject, "subject")
        predicate = sanitize_name(predicate, "predicate")
        object = sanitize_kg_value(object, "object")
    except ValueError as e:
        return {"success": False, "error": str(e)}
    resolved_ended = ended or date.today().isoformat()
    _wal_log(
        "kg_invalidate",
        {
            "subject": subject,
            "predicate": predicate,
            "object": object,
            "ended": resolved_ended,
        },
    )
    _kg.invalidate(subject, predicate, object, ended=resolved_ended)
    return {
        "success": True,
        "fact": f"{subject} → {predicate} → {object}",
        "ended": resolved_ended,
    }


def tool_kg_timeline(entity: str = None):
    """Get chronological timeline of facts, optionally for one entity."""
    if entity is not None:
        try:
            entity = sanitize_kg_value(entity, "entity")
        except ValueError as e:
            return {"error": str(e)}
    results = _kg.timeline(entity)
    return {"entity": entity or "all", "timeline": results, "count": len(results)}


def tool_kg_stats():
    """Knowledge graph overview: entities, triples, relationship types."""
    return _kg.stats()


# ==================== AGENT DIARY ====================


def tool_diary_write(agent_name: str, entry: str, topic: str = "general", wing: str = ""):
    """
    Write a diary entry for this agent. Entries are timestamped and
    accumulate over time in a diary room.

    This is the agent's personal journal — observations, thoughts,
    what it worked on, what it noticed, what it thinks matters.

    Note: ``agent_name`` is normalized to lowercase before storage so
    that diary reads are case-insensitive (see #1243). "Claude",
    "claude", and "CLAUDE" all resolve to the same agent.
    """
    try:
        agent_name = sanitize_name(agent_name, "agent_name").lower()
        entry = sanitize_content(entry)
        topic = sanitize_name(topic, "topic")
    except ValueError as e:
        return {"success": False, "error": str(e)}

    if wing:
        wing = sanitize_name(wing)
    else:
        wing = f"wing_{agent_name.replace(' ', '_')}"
    room = "diary"
    col = _get_collection(create=True)
    if not col:
        return _no_palace()

    now = datetime.now()
    entry_id = (
        f"diary_{wing}_{now.strftime('%Y%m%d_%H%M%S%f')}_"
        f"{hashlib.sha256(entry.encode()).hexdigest()[:12]}"
    )

    _wal_log(
        "diary_write",
        {
            "agent_name": agent_name,
            "topic": topic,
            "entry_id": entry_id,
            "entry_preview": entry[:200],
        },
    )

    try:
        # TODO: Future versions should expand AAAK before embedding to improve
        # semantic search quality. For now, store raw AAAK in metadata so it's
        # preserved, and keep the document as-is for embedding (even though
        # compressed AAAK degrades embedding quality).
        col.add(
            ids=[entry_id],
            documents=[entry],
            metadatas=[
                {
                    "wing": wing,
                    "room": room,
                    "hall": "hall_diary",
                    "topic": topic,
                    "type": "diary_entry",
                    "agent": agent_name,
                    "filed_at": now.isoformat(),
                    "date": now.strftime("%Y-%m-%d"),
                }
            ],
        )
        logger.info(f"Diary entry: {entry_id} → {wing}/diary/{topic}")
        return {
            "success": True,
            "entry_id": entry_id,
            "agent": agent_name,
            "topic": topic,
            "timestamp": now.isoformat(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_diary_read(agent_name: str, last_n: int = 10, wing: str = ""):
    """
    Read an agent's recent diary entries. Returns the last N entries
    in chronological order — the agent's personal journal.

    When ``wing`` is provided, reads only from that wing. When ``wing``
    is empty or omitted, returns entries from every wing this agent has
    written to. Diary writes from hooks land in project-derived wings
    (``wing_<project>``), so requiring a specific wing on read would
    silo those entries from agent-initiated reads.

    Note: ``agent_name`` is normalized to lowercase before filtering so
    that reads are case-insensitive (see #1243). Entries written under
    pre-fix mixed-case agent names will not match the lowercase filter;
    use ``castle repair`` to migrate legacy data if needed.
    """
    try:
        agent_name = sanitize_name(agent_name, "agent_name").lower()
        if wing:
            wing = sanitize_name(wing)
    except ValueError as e:
        return {"error": str(e)}
    last_n = max(1, min(last_n, 100))
    col = _get_collection()
    if not col:
        return _no_palace()

    # Filter by room=diary (hoisted column) and optionally wing.
    # Agent is stored in metadata_json — not a hoisted column — so filter
    # it in Python after the DB fetch rather than in the WHERE clause.
    try:
        db_where: dict = {"room": "diary"}
        if wing:
            db_where = {"$and": [{"wing": wing}, {"room": "diary"}]}

        results = col.get(
            where=db_where,
            include=["documents", "metadatas"],
            limit=10000,
        )

        if not results["ids"]:
            return {"agent": agent_name, "entries": [], "message": "No diary entries yet."}

        # Combine, filter by agent in Python, and sort by timestamp.
        all_entries = []
        for doc, meta in zip(results["documents"], results["metadatas"]):
            meta = meta or {}
            if meta.get("agent") != agent_name:
                continue
            all_entries.append(
                {
                    "date": meta.get("date", ""),
                    "timestamp": meta.get("filed_at", ""),
                    "topic": meta.get("topic", ""),
                    "content": doc,
                }
            )

        all_entries.sort(key=lambda x: x["timestamp"], reverse=True)
        entries = all_entries[:last_n]

        return {
            "agent": agent_name,
            "entries": entries,
            "total": len(all_entries),
            "showing": len(entries),
        }
    except Exception:
        logger.exception("diary_read failed")
        return {"error": "Failed to read diary entries"}


def tool_hook_settings(silent_save: bool = None, desktop_toast: bool = None):
    """
    Get or set hook behavior settings.

    - silent_save: True = stop hook saves directly (no MCP clutter),
      False = legacy blocking MCP calls. Default: True.
    - desktop_toast: True = show notify-send desktop toast on save,
      False = terminal-only notification. Default: False.

    Call with no arguments to see current settings.
    """
    from .config import CognitiveCastleConfig

    try:
        config = CognitiveCastleConfig()
    except Exception as e:
        return {"success": False, "error": str(e)}

    changed = []
    if silent_save is not None:
        config.set_hook_setting("silent_save", silent_save)
        changed.append(f"silent_save → {silent_save}")
    if desktop_toast is not None:
        config.set_hook_setting("desktop_toast", desktop_toast)
        changed.append(f"desktop_toast → {desktop_toast}")

    # Re-read to return current state
    try:
        config = CognitiveCastleConfig()
    except Exception:
        pass

    result = {
        "success": True,
        "settings": {
            "silent_save": config.hook_silent_save,
            "desktop_toast": config.hook_desktop_toast,
        },
    }
    if changed:
        result["updated"] = changed
    return result


def tool_memories_filed_away():
    """Acknowledge the latest silent checkpoint. Returns a short summary."""
    state_dir = Path.home() / ".castle" / "hook_state"
    ack_file = state_dir / "last_checkpoint"
    if not ack_file.is_file():
        return {
            "status": "quiet",
            "message": "No recent journal entry",
            "count": 0,
            "timestamp": None,
        }
    try:
        data = json.loads(ack_file.read_text(encoding="utf-8"))
        ack_file.unlink(missing_ok=True)
        msgs = data.get("msgs", 0)
        return {
            "status": "ok",
            "message": f"\u2726 {msgs} messages tucked into drawers",
            "count": msgs,
            "timestamp": data.get("ts", None),
        }
    except (json.JSONDecodeError, OSError):
        ack_file.unlink(missing_ok=True)
        return {
            "status": "error",
            "message": "\u2726 Journal entry filed in the palace",
            "count": 0,
            "timestamp": None,
        }


# ==================== SETTINGS TOOLS ====================


def tool_reconnect():
    """Force the MCP server to drop the cached collection and reconnect.

    Use after external scripts or CLI commands modify the palace database
    directly, which can leave the in-memory collection handle stale.
    """
    global _collection_cache, _metadata_cache, _metadata_cache_time, _counts_cache
    _collection_cache = None
    _metadata_cache = None
    _counts_cache = None
    _metadata_cache_time = 0
    try:
        col = _get_collection()
        if col is None:
            return {
                "success": False,
                "message": "No palace found after reconnect",
                "drawers": 0,
            }
        return {
            "success": True,
            "message": "Reconnected to palace",
            "drawers": col.count(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_sue_review(
    drawer_ids,
    decision,
    provider="ollama",
    model=None,
    lens="euthyphro",
    max_turns=7,
    timeout=120,
):
    """Snapshot selected requirements and enqueue a bounded, isolated SUE dialogue."""
    from .sue import start_review

    try:
        col = _get_collection()
        if col is None:
            return _no_palace()
        return start_review(
            _config.palace_path,
            drawer_ids,
            decision,
            collection_name=_config.collection_name,
            collection=col,
            provider=provider,
            model=model,
            lens=lens,
            max_turns=max_turns,
            timeout=timeout,
        )
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}


def tool_sue_status(run_id=None):
    """Read derived findings and source links without another model call."""
    from .sue import review_status

    try:
        return review_status(_config.palace_path, run_id)
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}


# ==================== MCP PROTOCOL ====================

TOOLS = {
    "castle_sue_review": {
        "description": "Start a background SUE dialogue about selected requirement drawers and a stated decision. Preserves exact sources; stores derived findings separately in this palace. Default Ollama runs on localhost. Explicit provider=codex or provider=claude sends the selected text/context to that external provider (claude runs an isolated `claude -p`, default claude-opus-5-5). Does not verify truth or implementation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "drawer_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 2000,
                    "description": "Exact IDs of requirements and context, including exceptions/revisions",
                },
                "decision": {
                    "type": "string",
                    "description": "Requirement or interpretation to examine",
                },
                "provider": {
                    "type": "string",
                    "enum": ["ollama", "codex", "claude"],
                    "default": "ollama",
                },
                "model": {
                    "type": "string",
                    "description": "Default qwen3.5:latest for Ollama; gpt-5.6-luna / low for Codex",
                },
                "lens": {
                    "type": "string",
                    "default": "euthyphro",
                    "description": "One of the nine SUE lenses; castle_sue_status lists them",
                },
                "max_turns": {"type": "integer", "minimum": 1, "maximum": 14, "default": 7},
                "timeout": {"type": "integer", "minimum": 1, "maximum": 900, "default": 120},
            },
            "required": ["drawer_ids", "decision"],
        },
        "handler": tool_sue_review,
    },
    "castle_sue_status": {
        "description": "List the palace's recent SUE runs and available lenses, or get a run's full dialogue, understanding profile, questions, exact source references and report. No model call. Findings concern frozen source revisions and remain model interpretations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "string",
                    "description": "Run ID returned by castle_sue_review; omit to list",
                }
            },
        },
        "handler": tool_sue_status,
    },
    "castle_status": {
        "description": "Palace overview — total drawers, wing and room counts",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_status,
    },
    "castle_list_wings": {
        "description": "List all wings with drawer counts",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_list_wings,
    },
    "castle_list_rooms": {
        "description": "List rooms within a wing (or all rooms if no wing given)",
        "input_schema": {
            "type": "object",
            "properties": {
                "wing": {"type": "string", "description": "Wing to list rooms for (optional)"},
            },
        },
        "handler": tool_list_rooms,
    },
    "castle_get_taxonomy": {
        "description": "Full taxonomy: wing → room → drawer count",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_get_taxonomy,
    },
    "castle_get_aaak_spec": {
        "description": "Get the AAAK dialect specification — the compressed memory format Cognitive Castle uses. Call this if you need to read or write AAAK-compressed memories.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_get_aaak_spec,
    },
    "castle_kg_query": {
        "description": "Query the knowledge graph for an entity's relationships. Returns typed facts with temporal validity. E.g. 'Max' → child_of Alice, loves chess, does swimming. Filter by date with as_of to see what was true at a point in time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity": {
                    "type": "string",
                    "description": "Entity to query (e.g. 'Max', 'MyProject', 'Alice')",
                },
                "as_of": {
                    "type": "string",
                    "description": "Date filter — only facts valid at this date (YYYY-MM-DD, optional)",
                },
                "direction": {
                    "type": "string",
                    "description": "outgoing (entity→?), incoming (?→entity), or both (default: both)",
                },
            },
            "required": ["entity"],
        },
        "handler": tool_kg_query,
    },
    "castle_kg_add": {
        "description": "Add a fact to the knowledge graph. Subject → predicate → object with optional time window. E.g. ('Max', 'started_school', 'Year 7', valid_from='2026-09-01'). Pass valid_to to backfill an already-ended historical fact in a single call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "The entity doing/being something"},
                "predicate": {
                    "type": "string",
                    "description": "The relationship type (e.g. 'loves', 'works_on', 'daughter_of')",
                },
                "object": {"type": "string", "description": "The entity being connected to"},
                "valid_from": {
                    "type": "string",
                    "description": "When this became true (YYYY-MM-DD, optional)",
                },
                "valid_to": {
                    "type": "string",
                    "description": "When this stopped being true (YYYY-MM-DD, optional). Use for backfilling already-ended historical facts.",
                },
                "source_closet": {
                    "type": "string",
                    "description": "Closet ID where this fact appears (optional)",
                },
                "source_file": {
                    "type": "string",
                    "description": "Source file path the fact was extracted from (optional)",
                },
                "source_drawer_id": {
                    "type": "string",
                    "description": "Drawer ID the fact was extracted from (optional, RFC 002 provenance)",
                },
            },
            "required": ["subject", "predicate", "object"],
        },
        "handler": tool_kg_add,
    },
    "castle_kg_invalidate": {
        "description": "Mark a fact as no longer true. E.g. ankle injury resolved, job ended, moved house.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Entity"},
                "predicate": {"type": "string", "description": "Relationship"},
                "object": {"type": "string", "description": "Connected entity"},
                "ended": {
                    "type": "string",
                    "description": "When it stopped being true (YYYY-MM-DD, default: today)",
                },
            },
            "required": ["subject", "predicate", "object"],
        },
        "handler": tool_kg_invalidate,
    },
    "castle_kg_timeline": {
        "description": "Chronological timeline of facts. Shows the story of an entity (or everything) in order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity": {
                    "type": "string",
                    "description": "Entity to get timeline for (optional — omit for full timeline)",
                },
            },
        },
        "handler": tool_kg_timeline,
    },
    "castle_kg_stats": {
        "description": "Knowledge graph overview: entities, triples, current vs expired facts, relationship types.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_kg_stats,
    },
    "castle_traverse": {
        "description": "Walk the palace graph from a room. Shows connected ideas across wings — the tunnels. Like following a thread through the palace: start at 'lancedb-setup' in wing_code, discover it connects to wing_myproject (planning) and wing_user (feelings about it).",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_room": {
                    "type": "string",
                    "description": "Room to start from (e.g. 'lancedb-setup', 'riley-school')",
                },
                "max_hops": {
                    "type": "integer",
                    "description": "How many connections to follow (default: 2)",
                },
            },
            "required": ["start_room"],
        },
        "handler": tool_traverse_graph,
    },
    "castle_find_tunnels": {
        "description": "Find rooms that bridge two wings — the hallways connecting different domains. E.g. what topics connect wing_code to wing_team?",
        "input_schema": {
            "type": "object",
            "properties": {
                "wing_a": {"type": "string", "description": "First wing (optional)"},
                "wing_b": {"type": "string", "description": "Second wing (optional)"},
            },
        },
        "handler": tool_find_tunnels,
    },
    "castle_graph_stats": {
        "description": "Palace graph overview: total rooms, tunnel connections, edges between wings.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_graph_stats,
    },
    "castle_create_tunnel": {
        "description": "Create a cross-wing tunnel linking two palace locations. Use when content in one project relates to another — e.g., an API design in project_api connects to a database schema in project_database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_wing": {"type": "string", "description": "Wing of the source"},
                "source_room": {"type": "string", "description": "Room in the source wing"},
                "target_wing": {"type": "string", "description": "Wing of the target"},
                "target_room": {"type": "string", "description": "Room in the target wing"},
                "label": {"type": "string", "description": "Description of the connection"},
                "source_drawer_id": {
                    "type": "string",
                    "description": "Optional specific drawer ID",
                },
                "target_drawer_id": {
                    "type": "string",
                    "description": "Optional specific drawer ID",
                },
            },
            "required": ["source_wing", "source_room", "target_wing", "target_room"],
        },
        "handler": tool_create_tunnel,
    },
    "castle_list_tunnels": {
        "description": "List all explicit cross-wing tunnels. Optionally filter by wing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "wing": {
                    "type": "string",
                    "description": "Filter tunnels by wing (shows tunnels where wing is source or target)",
                },
            },
        },
        "handler": tool_list_tunnels,
    },
    "castle_delete_tunnel": {
        "description": "Delete an explicit tunnel by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tunnel_id": {"type": "string", "description": "Tunnel ID to delete"},
            },
            "required": ["tunnel_id"],
        },
        "handler": tool_delete_tunnel,
    },
    "castle_follow_tunnels": {
        "description": "Follow tunnels from a room to see what it connects to in other wings. Returns connected rooms with drawer previews.",
        "input_schema": {
            "type": "object",
            "properties": {
                "wing": {"type": "string", "description": "Wing to start from"},
                "room": {"type": "string", "description": "Room to follow tunnels from"},
            },
            "required": ["wing", "room"],
        },
        "handler": tool_follow_tunnels,
    },
    "castle_search": {
        "description": "Default model-free exact search across live and registered historical memory under trusted host policy. Coverage and continuation are explicit. Explicit modes select the legacy model-backed index only.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Short search query ONLY — keywords or a question. Max 250 chars.",
                    "maxLength": 250,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 5; unified route caps at 8, explicit legacy modes at 100)",
                    "minimum": 1,
                    "maximum": 100,
                },
                "wing": {"type": "string", "description": "Filter by wing (optional)"},
                "room": {"type": "string", "description": "Filter by room (optional)"},
                "workspace": {"type": "string", "maxLength": 2048},
                "match": {"type": "string", "enum": ["all", "any"]},
                "cursor": {"type": "string", "maxLength": 4096},
                "max_distance": {
                    "type": "number",
                    "description": "Legacy compatibility option requiring an explicit mode; the current legacy pipeline does not apply a distance threshold.",
                },
                "context": {
                    "type": "string",
                    "description": "Background context for the search (optional). NOT used for embedding — only for future re-ranking.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["fast", "standard", "boosted", "max"],
                    "description": (
                        "Explicit legacy-index-only diagnostic mode; omit for unified exact memory. "
                        "fast=Stage 3 only (lowest latency); "
                        "standard=+quality rerank; "
                        "boosted=+Python symbolic boost-tags; "
                        "max=+LLM judge."
                    ),
                },
            },
            "required": ["query"],
        },
        "handler": tool_search,
    },
    "castle_check_duplicate": {
        "description": "Check if content already exists in the palace before filing",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Content to check"},
                "threshold": {
                    "type": "number",
                    "description": "Similarity threshold 0-1 (default 0.9)",
                },
            },
            "required": ["content"],
        },
        "handler": tool_check_duplicate,
    },
    "castle_wake_up": {
        "description": (
            "Return the L0 + L1 wake-up context (~600–900 tokens): "
            "the palace's identity + essential story layers as a single text "
            "block. Cheap, no LLM calls. Use at session start to remind the "
            "model what it already knows about the user and their projects."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "wing": {
                    "type": "string",
                    "description": "Optional wing (project) to scope the wake-up to",
                },
            },
            "required": [],
        },
        "handler": tool_wake_up,
    },
    "castle_info_score": {
        "description": (
            "Score how novel a piece of text is against the palace using nn_novelty "
            "(Estimator A from the v3.4.0 info-theory research). Returns novelty in "
            "[0, 2] plus a low/medium/high band and the top-k closest drawers. "
            "Cheap enough to call per-drawer; rho(nn_novelty, LLE_residual) = 0.982 "
            "on the full palace so this is a strong information-content proxy."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to score (e.g. a candidate drawer before filing)",
                },
                "wing": {
                    "type": "string",
                    "description": "Optional wing filter — restrict search to same wing",
                },
                "top_k": {
                    "type": "integer",
                    "description": "How many neighbours to return (default 5)",
                },
            },
            "required": ["text"],
        },
        "handler": tool_info_score,
    },
    "castle_prune_suggest": {
        "description": (
            "Flag low-information drawers as pruning candidates via nn_novelty. "
            "READ-ONLY — never touches the palace. Samples N drawers, scores each, "
            "returns those below the novelty threshold sorted most-duplicate-y first. "
            "Use to surface near-duplicate content (session metadata, encoded API "
            "blobs, tool_use records) for human review — respects Castle's "
            "verbatim-always principle by never auto-pruning."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sample": {
                    "type": "integer",
                    "description": "How many drawers to sample (default 200)",
                },
                "threshold": {
                    "type": "number",
                    "description": (
                        "Novelty below this = pruning candidate "
                        "(default 0.10 = 'low' band from the v3.4.0 research)"
                    ),
                },
                "wing": {
                    "type": "string",
                    "description": "Optional wing filter — restrict sample to one wing",
                },
                "seed": {
                    "type": "integer",
                    "description": "RNG seed for reproducible sampling (default 42)",
                },
            },
            "required": [],
        },
        "handler": tool_prune_suggest,
    },
    "castle_add_drawer": {
        "description": "Legacy-index-only write with duplicate checks; not immediately visible in unified recall. Use castle_memory_remember for ordinary exact-text storage under trusted host policy.",
        "input_schema": {
            "type": "object",
            "properties": {
                "wing": {"type": "string", "description": "Wing (project name)"},
                "room": {
                    "type": "string",
                    "description": "Room (aspect: backend, decisions, meetings...)",
                },
                "content": {
                    "type": "string",
                    "description": "Verbatim content to store — exact words, never summarized",
                },
                "source_file": {"type": "string", "description": "Where this came from (optional)"},
                "added_by": {"type": "string", "description": "Who is filing this (default: mcp)"},
            },
            "required": ["wing", "room", "content"],
        },
        "handler": tool_add_drawer,
    },
    "castle_delete_drawer": {
        "description": "Delete a drawer by ID. Irreversible.",
        "input_schema": {
            "type": "object",
            "properties": {
                "drawer_id": {"type": "string", "description": "ID of the drawer to delete"},
            },
            "required": ["drawer_id"],
        },
        "handler": tool_delete_drawer,
    },
    "castle_get_drawer": {
        "description": "Fetch a single drawer by ID — returns full content and metadata.",
        "input_schema": {
            "type": "object",
            "properties": {
                "drawer_id": {"type": "string", "description": "ID of the drawer to fetch"},
            },
            "required": ["drawer_id"],
        },
        "handler": tool_get_drawer,
    },
    "castle_list_drawers": {
        "description": "List drawers with pagination. Optional wing/room filter. Returns IDs, wings, rooms, and content previews.",
        "input_schema": {
            "type": "object",
            "properties": {
                "wing": {"type": "string", "description": "Filter by wing (optional)"},
                "room": {"type": "string", "description": "Filter by room (optional)"},
                "limit": {
                    "type": "integer",
                    "description": "Max results per page (default 20, max 100)",
                    "minimum": 1,
                    "maximum": 100,
                },
                "offset": {
                    "type": "integer",
                    "description": "Offset for pagination (default 0)",
                    "minimum": 0,
                },
            },
        },
        "handler": tool_list_drawers,
    },
    "castle_update_drawer": {
        "description": "Update an existing drawer's content and/or metadata (wing, room). Fetches existing drawer first; returns error if not found.",
        "input_schema": {
            "type": "object",
            "properties": {
                "drawer_id": {"type": "string", "description": "ID of the drawer to update"},
                "content": {
                    "type": "string",
                    "description": "New content (optional — omit to keep existing)",
                },
                "wing": {
                    "type": "string",
                    "description": "New wing (optional — omit to keep existing)",
                },
                "room": {
                    "type": "string",
                    "description": "New room (optional — omit to keep existing)",
                },
            },
            "required": ["drawer_id"],
        },
        "handler": tool_update_drawer,
    },
    "castle_diary_write": {
        "description": "Write to your personal agent diary in AAAK format. Your observations, thoughts, what you worked on, what matters. Each agent has their own diary with full history. Write in AAAK for compression — e.g. 'SESSION:2026-04-04|built.palace.graph+diary.tools|ALC.req:agent.diaries.in.aaak|★★★'. Use entity codes from the AAAK spec.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Your name — each agent gets their own diary wing",
                },
                "entry": {
                    "type": "string",
                    "description": "Your diary entry in AAAK format — compressed, entity-coded, emotion-marked",
                },
                "topic": {
                    "type": "string",
                    "description": "Topic tag (optional, default: general)",
                },
                "wing": {
                    "type": "string",
                    "description": "Target wing for this diary entry (optional). If omitted, uses wing_{agent_name}. Use this to write diary entries to a project wing instead of an agent-specific wing.",
                },
            },
            "required": ["agent_name", "entry"],
        },
        "handler": tool_diary_write,
    },
    "castle_diary_read": {
        "description": "Read your recent diary entries (in AAAK). See what past versions of yourself recorded — your journal across sessions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Your name — each agent gets their own diary wing",
                },
                "last_n": {
                    "type": "integer",
                    "description": "Number of recent entries to read (default: 10)",
                },
                "wing": {
                    "type": "string",
                    "description": "Wing to read diary entries from (optional). If omitted, reads from wing_{agent_name}.",
                },
            },
            "required": ["agent_name"],
        },
        "handler": tool_diary_read,
    },
    "castle_hook_settings": {
        "description": (
            "Get or set hook behavior. silent_save: True = save directly "
            "(no MCP clutter), False = legacy blocking. desktop_toast: "
            "True = show desktop notification. Call with no args to view."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "silent_save": {
                    "type": "boolean",
                    "description": "True = silent direct save, False = blocking MCP calls",
                },
                "desktop_toast": {
                    "type": "boolean",
                    "description": "True = show desktop toast via notify-send",
                },
            },
        },
        "handler": tool_hook_settings,
    },
    "castle_memories_filed_away": {
        "description": "Check if a recent palace checkpoint was saved. Returns message count and timestamp.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_memories_filed_away,
    },
    "castle_reconnect": {
        "description": (
            "Force reconnect to the palace database. Use after external scripts or CLI commands"
            " modified the palace directly, which can leave the in-memory collection handle stale."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
        "handler": tool_reconnect,
    },
}


from .brain_api import BrainAPI, tool_registry  # noqa: E402

TOOLS.update(tool_registry(lambda: BrainAPI(_config.palace_path)))


SUPPORTED_PROTOCOL_VERSIONS = [
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
]


def handle_request(request):
    if isinstance(request, dict) and "id" in request:
        identifier = request["id"]
        if identifier is not None and (
            type(identifier) not in (str, int)
            or (
                type(identifier) is str
                and (
                    len(identifier) > 128 or len(identifier.encode("utf-8", errors="replace")) > 128
                )
            )
            or (type(identifier) is int and abs(identifier) > 2**63 - 1)
        ):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid bounded request ID"},
            }
    if (
        not isinstance(request, dict)
        or not isinstance(request.get("method"), str)
        or not isinstance(request.get("params", {}), dict)
    ):
        return {
            "jsonrpc": "2.0",
            "id": request.get("id") if isinstance(request, dict) else None,
            "error": {"code": -32600, "message": "Invalid request"},
        }
    method = request.get("method") or ""
    params = request.get("params") or {}
    req_id = request.get("id")

    if method == "initialize":
        client_version = params.get("protocolVersion", SUPPORTED_PROTOCOL_VERSIONS[-1])
        negotiated = (
            client_version
            if client_version in SUPPORTED_PROTOCOL_VERSIONS
            else SUPPORTED_PROTOCOL_VERSIONS[0]
        )
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": negotiated,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "cognitive-castle", "version": __version__},
                "instructions": _build_instructions(),
            },
        }
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    elif method.startswith("notifications/"):
        # Notifications (no id) never get a response per JSON-RPC spec
        return None
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {"name": n, "description": t["description"], "inputSchema": t["input_schema"]}
                    for n, t in TOOLS.items()
                ]
            },
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        if (
            tool_args is None
            and isinstance(tool_name, str)
            and not TOOLS.get(tool_name, {}).get("strict_arguments")
        ):
            tool_args = {}  # Existing no-argument clients used null.
        if not isinstance(tool_name, str) or not isinstance(tool_args, dict):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": "Invalid tool call"},
            }
        if tool_name not in TOOLS:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }
        if TOOLS[tool_name].get("strict_arguments"):
            try:
                # Do not filter or coerce: unknown keys and bool-as-integer must fail.
                from .brain_api import validate

                validate(tool_args, TOOLS[tool_name]["input_schema"])
                result = TOOLS[tool_name]["handler"](**tool_args)
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    result,
                                    ensure_ascii=False,
                                    allow_nan=False,
                                    separators=(",", ":"),
                                ),
                            }
                        ]
                    },
                }
                from .bounded_json import encode_response

                return json.loads(encode_response(response))
            except (ValueError, TypeError):
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": "Invalid bounded tool arguments"},
                }
            except Exception:
                logger.exception("Bounded tool failed: %s", tool_name)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32000, "message": "Bounded tool unavailable"},
                }
        # Whitelist arguments to declared schema properties only.
        # Prevents callers from spoofing internal params like added_by/source_file.
        # Skip filtering if handler explicitly accepts **kwargs (pass-through).
        # Default to filtering on inspect failure (safe fallback).
        import inspect

        schema_props = TOOLS[tool_name]["input_schema"].get("properties", {})
        try:
            handler = TOOLS[tool_name]["handler"]
            sig = inspect.signature(handler)
            accepts_var_keyword = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            )
        except (ValueError, TypeError):
            accepts_var_keyword = False
        if not accepts_var_keyword:
            tool_args = {k: v for k, v in tool_args.items() if k in schema_props}
        # Coerce argument types based on input_schema.
        # MCP JSON transport may deliver integers as floats or strings;
        # MCP JSON transport and Python slicing require native int.
        for key, value in list(tool_args.items()):
            prop_schema = schema_props.get(key, {})
            declared_type = prop_schema.get("type")
            try:
                if declared_type == "integer" and not isinstance(value, int):
                    tool_args[key] = int(value)
                elif declared_type == "number" and not isinstance(value, (int, float)):
                    tool_args[key] = float(value)
            except (ValueError, TypeError):
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": f"Invalid value for parameter '{key}'"},
                }
        try:
            tool_args.pop("wait_for_previous", None)
            result = TOOLS[tool_name]["handler"](**tool_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
            }
        except Exception:
            logger.exception(f"Tool error in {tool_name}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": "Internal tool error"},
            }

    # Notifications (missing id) must never get a response
    if req_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


def _restore_stdout():
    """Restore real stdout for MCP JSON-RPC output (see issue #225)."""
    global _REAL_STDOUT, _REAL_STDOUT_FD
    if _REAL_STDOUT_FD is not None:
        try:
            os.dup2(_REAL_STDOUT_FD, 1)
            os.close(_REAL_STDOUT_FD)
        except OSError:
            pass
        _REAL_STDOUT_FD = None
    sys.stdout = _REAL_STDOUT


def main():
    _restore_stdout()
    from .bounded_json import (
        FrameReader,
        FrameError,
        strict_loads,
        encode_response,
        MAX_FRAME_BYTES,
    )

    reader = FrameReader(sys.stdin)
    logger.info("Cognitive Castle MCP Server starting...")
    while True:
        try:
            line = reader.read()
            if line is None:
                break
            line = line.strip()
            if not line:
                continue
            try:
                request = strict_loads(line)
            except ValueError:
                response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Invalid bounded JSON"},
                }
                sys.stdout.write(encode_response(response).decode("utf-8") + "\n")
                sys.stdout.flush()
                continue
            response = handle_request(request)
            if response is not None:
                # New brain tools already enforce their 32KiB double envelope.
                # Discovery and existing tools retain a bounded 1MiB envelope.
                sys.stdout.write(
                    encode_response(response, max_bytes=MAX_FRAME_BYTES).decode("utf-8") + "\n"
                )
                sys.stdout.flush()
        except KeyboardInterrupt:
            break
        except (FrameError, OSError) as exc:
            logger.error("Closing invalid input stream: %s", exc)
            break
        except Exception as e:
            logger.error(f"Server error: {e}")


if __name__ == "__main__":
    main()
