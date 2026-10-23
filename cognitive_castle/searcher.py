#!/usr/bin/env python3
"""
searcher.py — Find anything. Exact words.

Search routes unconditionally through the 3-stage retrieval pipeline
(dense + sparse + KG recall → weighted RRF + recency → cross-encoder rerank).
The legacy BM25 Python implementation was removed in Task 14; Tantivy FTS
via LanceDB now provides the sparse-retrieval signal.
"""

import json
import hashlib
import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

# Closet pointer line format: "topic|entities|→drawer_id_a,drawer_id_b"
# Multiple lines may join with newlines inside one closet document.
_CLOSET_DRAWER_REF_RE = re.compile(r"→([\w,]+)")

logger = logging.getLogger("castle_mcp")


class SearchError(Exception):
    """Raised when search cannot proceed (e.g. no palace found)."""


class SearchUnavailableError(SearchError):
    """No configured recall signal could complete successfully."""


@dataclass
class RetrievalDiagnostics:
    available_signals: list[str] = field(default_factory=list)
    failed_signals: list[str] = field(default_factory=list)
    disabled_signals: list[str] = field(default_factory=list)
    models: dict[str, str] = field(default_factory=dict)

    def as_dict(self):
        return {
            "available_signals": self.available_signals,
            "failed_signals": self.failed_signals,
            "disabled_signals": self.disabled_signals,
            "models": self.models,
            "degraded": bool(self.failed_signals),
        }


_TOKEN_RE = re.compile(r"\w{2,}", re.UNICODE)


def _first_or_empty(results, key: str) -> list:
    """Return the first inner list of a query result field, or [].

    Accepts both the typed :class:`QueryResult` (attribute access) and the
    plain dict shape; this polymorphism is retained so test mocks still work.
    Preserves the empty-collection semantics from issue #195: when no queries
    returned hits, the outer list may be empty and indexing ``[0]`` would raise.
    """
    outer = getattr(results, key, None) if not isinstance(results, dict) else results.get(key)
    if not outer:
        return []
    return outer[0] or []


def _tokenize(text: str) -> list:
    """Lowercase + strip to alphanumeric tokens of length ≥ 2.

    Tolerates ``None`` documents — the backend can return ``None`` in the
    ``documents`` field for drawers without text content, which would
    otherwise raise ``AttributeError`` mid-rerank.
    """
    if not text:
        return []
    return _TOKEN_RE.findall(text.lower())


def build_where_filter(wing: str = None, room: str = None) -> dict:
    """Build a metadata where-filter dict for wing/room filtering."""
    if wing and room:
        return {"$and": [{"wing": wing}, {"room": room}]}
    elif wing:
        return {"wing": wing}
    elif room:
        return {"room": room}
    return {}


def _extract_drawer_ids_from_closet(closet_doc: str) -> list:
    """Parse all `→drawer_id_a,drawer_id_b` pointers out of a closet document.

    Preserves order and dedupes.
    """
    seen: dict = {}
    for match in _CLOSET_DRAWER_REF_RE.findall(closet_doc):
        for did in match.split(","):
            did = did.strip()
            if did and did not in seen:
                seen[did] = None
    return list(seen.keys())


def _expand_with_neighbors(drawers_col, matched_doc: str, matched_meta: dict, radius: int = 1):
    """Expand a matched drawer with its ±radius sibling chunks in the same source file.

    Motivation — "drawer-grep context" feature: a closet hit returns one
    drawer, but the chunk boundary may clip mid-thought (e.g., the matched
    chunk says "here's a breakdown:" and the actual breakdown lives in the
    next chunk). Fetching the small neighborhood around the match gives
    callers enough context without forcing a follow-up ``get_drawer`` call.

    Returns a dict with:
        ``text``            combined chunks in chunk_index order
        ``drawer_index``    the matched chunk's index in the source file
        ``total_drawers``   total drawer count for the source file (or None)

    On any backend failure or missing metadata, falls back to returning the
    matched drawer alone so search never breaks because neighbor expansion
    failed.
    """
    src = matched_meta.get("source_file")
    chunk_idx = matched_meta.get("chunk_index")
    if not src or not isinstance(chunk_idx, int):
        return {"text": matched_doc, "drawer_index": chunk_idx, "total_drawers": None}

    target_indexes = [chunk_idx + offset for offset in range(-radius, radius + 1)]
    try:
        neighbors = drawers_col.get(
            where={
                "$and": [
                    {"source_file": src},
                    {"chunk_index": {"$in": target_indexes}},
                ]
            },
            include=["documents", "metadatas"],
        )
    except Exception:
        return {"text": matched_doc, "drawer_index": chunk_idx, "total_drawers": None}

    indexed_docs = []
    for doc, meta in zip(neighbors.documents, neighbors.metadatas):
        ci = meta.get("chunk_index")
        if isinstance(ci, int):
            indexed_docs.append((ci, doc))
    indexed_docs.sort(key=lambda pair: pair[0])

    if not indexed_docs:
        combined_text = matched_doc
    else:
        combined_text = "\n\n".join(doc for _, doc in indexed_docs)

    # Cheap total_drawers lookup: metadata-only scan of the source file.
    total_drawers = None
    try:
        all_meta = drawers_col.get(where={"source_file": src}, include=["metadatas"])
        total_drawers = len(all_meta.ids) if all_meta.ids else None
    except Exception:
        pass

    return {
        "text": combined_text,
        "drawer_index": chunk_idx,
        "total_drawers": total_drawers,
    }


def _print_search_results(result: dict, query: str) -> None:
    """Print search results to stdout in the standard CLI format.

    Args:
        result: Dict returned by ``search_memories()`` with keys ``results``,
            ``query``, and ``filters``.
        query: The original query string (used in the header line).
    """
    hits = result.get("results", [])
    filters = result.get("filters", {})
    wing = filters.get("wing")
    room = filters.get("room")

    if not hits:
        print(f'\n  No results found for: "{query}"')
        return

    print(f"\n{'=' * 60}")
    print(f'  Results for: "{query}"')
    if wing:
        print(f"  Wing: {wing}")
    if room:
        print(f"  Room: {room}")
    print(f"{'=' * 60}\n")

    for i, hit in enumerate(hits, 1):
        text = hit.get("text") or hit.get("document", "")
        score = round(float(hit.get("score", 0.0)), 3)
        wing_name = hit.get("wing", "?")
        room_name = hit.get("room", "?")
        source = Path(hit.get("source_file", "?")).name

        print(f"  [{i}] {wing_name} / {room_name}")
        print(f"      Source: {source}")
        print(f"      Match:  score={score}")
        soar_tags = hit.get("soar_tags") or []
        if soar_tags:
            mul = float(hit.get("soar_boost", 1.0))
            pre = round(float(hit.get("score_pre_soar", score)), 3)
            print(f"      SOAR:   {', '.join(soar_tags)} (×{mul:.3f}, {pre} → {score})")
        quality_tier = hit.get("quality_tier")
        if quality_tier is not None:
            q_score = float(hit.get("quality_score", 0.0))
            q_boost = float(hit.get("quality_boost", 1.0))
            print(f"      QUALITY: {quality_tier} (×{q_boost:.3f}, score={q_score:.2f})")
        print()
        print(f"      {text}\n")
        print(f"  {'─' * 56}")

    # JUDGE audit line — driven by judge_status stashed on hits[0] by
    # _stage_4_judge. Absent for identity-order success (no surprise to
    # surface) or when mode < max (Stage 4 didn't run).
    status = hits[0].get("judge_status") if hits else None
    if status:
        if "error" in status:
            print(f"\n  JUDGE: FAILED ({status['error']}) — identity-order fallback")
        elif status.get("reordered"):
            print(
                f"\n  JUDGE: reordered {status['n']} hits "
                f"({status['model']}, {status['elapsed_s']}s)"
            )


def search(
    query: str,
    palace_path: str,
    wing: str = None,
    room: str = None,
    n_results: int = 5,
    mode: str = "max",
    info_weight: bool = False,
):
    """CLI entry point.

    Routes through the 3-stage pipeline (dense + FTS + KG-hop → fuse → rerank),
    same as `search_memories()`. Prints results to stdout in the legacy format
    so existing scraping tests keep working. Score shown is the cross-encoder
    reranker score, not cosine distance.

    Args:
        mode: Optional-stage activation mode. One of:
            fast     — Stage 3 only (no optional stages)
            standard — Stage 3 + Stage 6 (quality rerank)
            boosted  — Stage 3 + Stage 5 (SOAR) + Stage 6
            max      — Stage 3 + Stage 5 + Stage 6 + final Stage 4 (LLM judge)

    Raises SearchError if the pipeline fails. Returns None either way (this is
    a print-only function — programmatic callers should use `search_memories`).
    """
    from .backends.base import EmbedderIdentityMismatchError

    try:
        result = search_memories(
            query=query,
            palace_path=palace_path,
            wing=wing,
            room=room,
            n_results=n_results,
            mode=mode,
            info_weight=info_weight,
        )
    except EmbedderIdentityMismatchError:
        # Surface the friendly migration prompt — don't wrap as SearchError.
        raise
    except Exception as e:
        print(f"\n  Search error: {e}")
        raise SearchError(f"Search error: {e}") from e
    _print_search_results(result, query)


def search_memories(
    query: str,
    palace_path: str,
    wing: str = None,
    room: str = None,
    n_results: int = 5,
    max_distance: float = 0.0,
    vector_disabled: bool = False,
    candidate_strategy: str = "vector",
    is_hook_call: bool = False,
    mode: str | None = None,
    info_weight: bool = False,
    *,
    context=None,
    config=None,
    profile: str | None = None,
    allowed_wings: frozenset[str] | None = None,
) -> dict:
    """Programmatic search — returns a dict instead of printing.

    Routes unconditionally through the 3-stage retrieval pipeline
    (dense + sparse + KG recall → weighted RRF + recency → cross-encoder rerank).

    The ``max_distance``, ``vector_disabled``, and ``candidate_strategy``
    parameters are accepted for API compatibility but are no longer acted on
    by the pipeline (the new pipeline handles its own recall budget internally).

    Used by the MCP server and other callers that need data.

    Args:
        query: Natural language search query.
        palace_path: Path to the palace directory.
        wing: Optional wing filter.
        room: Optional room filter.
        n_results: Max results to return.
        max_distance: Accepted for compatibility; ignored by new pipeline.
        vector_disabled: Accepted for compatibility; ignored by new pipeline.
        candidate_strategy: Accepted for compatibility; ignored by new pipeline.
        is_hook_call: When True, uses a smaller reranker K cap (hook budget).
        mode: Optional-stage activation mode. One of:
            fast     — Stage 3 only (no optional stages)
            standard — Stage 3 + Stage 6 (quality rerank)
            boosted  — Stage 3 + Stage 5 (SOAR) + Stage 6
            max      — Stage 3 + Stage 5 + Stage 6 + final Stage 4 (LLM judge)
        info_weight: When True, demotes low-novelty candidates during fusion
            (Stage 2). Also enabled unconditionally when
            cfg.info_weight_enabled is True. Defaults to False for both.
    """
    from .config import CognitiveCastleConfig as _cfg_cls

    if profile not in (None, "memory-v1"):
        raise ValueError("unknown retrieval profile")
    if profile == "memory-v1" and mode is not None:
        raise ValueError("memory-v1 cannot select a legacy mode")
    if context is not None and config is not None and config != context.config:
        raise ValueError("config conflicts with explicit context")
    cfg = context.config if context is not None else (config if config is not None else _cfg_cls())
    diagnostics = RetrievalDiagnostics()
    extra = {}
    if (
        context is not None
        or config is not None
        or profile is not None
        or allowed_wings is not None
    ):
        extra = dict(
            context=context, profile=profile, allowed_wings=allowed_wings, diagnostics=diagnostics
        )
        extra["explicit_config"] = config is not None
    results = _new_pipeline_search(
        query,
        palace_path,
        wing,
        room,
        n_results,
        cfg,
        is_hook_call=is_hook_call,
        mode=mode or "max",
        info_weight=info_weight,
        **extra,
    )

    # ``_new_pipeline_search`` returns a list. Wrap it in the legacy dict
    # shape so MCP-tool callers and tests that expect ``result["results"]`` /
    # ``result.get("results")`` keep working without changes.
    if isinstance(results, dict):
        # Propagate any error dict the pipeline may return.
        return results
    response = {
        "query": query,
        "filters": {"wing": wing, "room": room},
        "results": results if results is not None else [],
    }
    if profile is not None:
        response["diagnostics"] = diagnostics.as_dict()
    return response


# ── New 3-stage retrieval pipeline ────────────────────────────────────────────


def _extract_id(row) -> str:
    """Extract drawer id from a LanceDB row dict."""
    if isinstance(row, dict):
        return row.get("id") or ""
    return ""


def _extract_text(row) -> str:
    """Extract document text from a LanceDB row dict."""
    if isinstance(row, dict):
        return row.get("text") or row.get("document") or ""
    return ""


def _extract_ts(row) -> float:
    """Extract unix timestamp from a LanceDB row dict."""
    if isinstance(row, dict):
        # Check hoisted ts column first, then metadata_json, then nested metadata dict.
        ts = row.get("ts")
        if ts is None:
            import json as _json

            raw = row.get("metadata_json")
            if raw:
                try:
                    meta = _json.loads(raw)
                    ts = meta.get("ts")
                except (ValueError, TypeError):
                    pass
        if ts is None:
            ts = (row.get("metadata") or {}).get("ts")
        try:
            return float(ts) if ts is not None else 0.0
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _extract_novelty(row) -> float | None:
    """Novelty from a row's metadata_json. None when absent/malformed —
    untagged drawers are never punished by info-weight demotion."""
    if not isinstance(row, dict):
        return None
    raw = row.get("metadata_json")
    if not raw:
        return None
    try:
        import json as _json

        meta = _json.loads(raw)
        if not isinstance(meta, dict):
            return None
        value = float(meta.get("novelty"))
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _get_filed_at(r) -> str:
    """Extract filed_at (used as created_at in hits) from drawer metadata.

    LanceDB stores per-drawer metadata as a JSON-serialized blob in the
    metadata_json column. filed_at is set by the miner at filing time
    (miner.py:754, 900) but isn't promoted to a hoisted column, so we
    parse it on demand here.

    Returns "" if metadata_json is missing, not a string, or malformed
    JSON — gracefully degrading so missing/old drawers don't crash search.
    """
    if not isinstance(r, dict):
        return ""
    raw = r.get("metadata_json")
    if not isinstance(raw, str):
        return ""
    try:
        meta = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ""
    return str(meta.get("filed_at", ""))


def _build_where_sql(wing, room, allowed_wings=None) -> str | None:
    """Build a LanceDB SQL WHERE fragment for wing/room filtering."""
    conditions = []
    if allowed_wings is not None:
        values = ", ".join("'" + str(w).replace("'", "''") + "'" for w in sorted(allowed_wings))
        conditions.append(f"wing IN ({values})" if values else "1 = 0")
    if wing:
        escaped = str(wing).replace("'", "''")
        conditions.append(f"wing = '{escaped}'")
    if room:
        escaped = str(room).replace("'", "''")
        conditions.append(f"room = '{escaped}'")
    return " AND ".join(conditions) if conditions else None


def _stage_4_judge(
    query: str,
    reranked: list[tuple[float, dict]],
    cfg,
) -> list[tuple[float, dict]]:
    """Stage 4: LLM-as-judge re-rank.

    Asks the LLM to reorder the top ``cfg.llm_judge_top_n`` hits. The
    rest of the input list is preserved unchanged at the tail of the
    return value.

    On any LLM failure (timeout, connection error, malformed reorder),
    returns ``reranked`` unchanged in identity order and stashes
    ``{"error": "<ExceptionClass>: <msg>"}`` on the first hit's dict so
    the CLI printer can surface a JUDGE audit line.

    On successful reorder, stashes ``{"reordered": True, "n": top_n,
    "model": cfg.llm_model, "elapsed_s": <float>}`` on the first hit's
    dict. If the judge returns identity order, no dict is stashed.

    The stashed ``judge_status`` is dropped by callers unless it appears
    in the result serializer allowlist in ``search_memories``.
    """
    import time
    from .judge import judge

    if not reranked:
        return reranked

    started = time.time()
    try:
        top_n = cfg.llm_judge_top_n
        judge_pool = reranked[:top_n]
        judge_docs = [_extract_text(r) for _, r in judge_pool]
        new_order = judge(query, judge_docs, cfg)
        if len(new_order) != len(judge_pool) or sorted(new_order) != list(range(len(judge_pool))):
            raise ValueError("judge did not return a complete permutation")
        elapsed = round(time.time() - started, 2)

        if new_order != list(range(len(new_order))):
            reordered_top = [judge_pool[i] for i in new_order]
            new_reranked = reordered_top + reranked[top_n:]
            new_reranked[0][1]["judge_status"] = {
                "reordered": True,
                "n": len(judge_pool),
                "model": cfg.llm_model,
                "elapsed_s": elapsed,
            }
            return new_reranked

        # Identity order — return original list, no status stash
        return reranked

    except Exception as e:  # noqa: BLE001 — deliberate broad catch for graceful fallback
        reranked[0][1]["judge_status"] = {"error": f"{type(e).__name__}: {e}"}
        return reranked


def _stage_5_soar(
    reranked: list[tuple[float, dict]],
    cfg,
    query: str = "",
) -> list[tuple[float, dict]]:
    """Stage 5: SOAR symbolic boost-tags.

    Delegates to soar_bridge._apply_soar_to_reranked. Lazy-imports
    soar_bridge so the module is only loaded when soar_boost is on
    (preserves the "no SOAR overhead by default" invariant from PR #4a).

    The query string is threaded through to soar_bridge so the type-match
    rule (PR #4c-type-match) can classify it into a memory_type intent.
    """
    from . import soar_bridge

    return soar_bridge._apply_soar_to_reranked(reranked, cfg, query=query)


def _stage_6_quality(
    reranked: list[tuple[float, dict]],
    cfg,
) -> list[tuple[float, dict]]:
    """Stage 6: deterministic text-quality rerank.

    Delegates to quality_rerank.apply_quality_rerank. Lazy-imports
    quality_rerank so the module is only loaded when quality_rerank is on
    (preserves the "no Stage 6 overhead by default" invariant).

    Never raises. Same graceful-fallback behavior as soar_bridge.
    """
    from . import quality_rerank

    return quality_rerank.apply_quality_rerank(reranked, cfg)


def _apply_optional_stages(
    query: str,
    reranked: list[tuple[float, dict]],
    cfg,
    mode: str,
) -> list[tuple[float, dict]]:
    """Run optional Stages 4 (judge), 5 (SOAR), and 6 (quality rerank)
    according to ``mode``.

    Modes:
        fast      → Stage 3 only (returns reranked unchanged)
        standard  → Stage 6
        boosted   → Stage 5 + Stage 6
        max       → Stage 5 + Stage 6 + Stage 4  (default)

    Order in ``max`` is fixed: SOAR → quality → final judge permutation.

    Raises ValueError on unknown mode.
    """
    if mode == "fast":
        return reranked
    if mode == "standard":
        return _stage_6_quality(reranked, cfg)
    if mode == "boosted":
        reranked = _stage_5_soar(reranked, cfg, query=query)
        return _stage_6_quality(reranked, cfg)
    if mode == "max":
        reranked = _stage_5_soar(reranked, cfg, query=query)
        reranked = _stage_6_quality(reranked, cfg)
        return _stage_4_judge(query, reranked, cfg)
    raise ValueError(f"invalid mode '{mode}' (must be fast|standard|boosted|max)")


def _new_pipeline_search(
    query: str,
    palace_path: str,
    wing: str | None,
    room: str | None,
    n_results: int,
    cfg,
    is_hook_call: bool = False,
    mode: str = "max",
    info_weight: bool = False,
    *,
    context=None,
    profile: str | None = None,
    allowed_wings: frozenset[str] | None = None,
    diagnostics: RetrievalDiagnostics | None = None,
    explicit_config: bool = False,
) -> list:
    """3-stage retrieval pipeline: parallel recall → fusion → cross-encoder rerank.

    Stage 1: Recall
        1a. Dense vector search via ``LanceCollection.vector_search`` → top-100.
        1b. Tantivy FTS sparse search via ``LanceCollection.fts_search`` → top-100.
        1c. KG-hop: query → ``EntityRegistry.lookup_in_text`` → entity IDs →
            ``KnowledgeGraph.find_drawers_by_entities`` → top-N, then hydrate.

    Stage 2: Fusion
        Weighted RRF over the three recall lists, then recency boost.

    Stage 3: Rerank
        Top-K candidates fed through the cross-encoder; top-N returned.

    Args:
        query: Search query string.
        palace_path: Path to the palace directory.
        wing: Optional wing filter.
        room: Optional room filter.
        n_results: Number of results to return.
        cfg: CognitiveCastleConfig instance.
        is_hook_call: True when called from a background hook (smaller top-K).
        mode: Retrieval pipeline mode. fast=Stage 3 only; standard=+quality;
            boosted=+SOAR; max=+LLM judge (default).

    Returns a list of result dicts.
    """
    from datetime import datetime, timezone

    from .palace import get_collection as _get_collection
    from .embedding import embed_texts
    from .fusion import CandidateRef, weighted_rrf, apply_recency, apply_info_weight
    from .reranker import rerank

    # Resolve the LanceCollection from the default palace backend.
    from .backends.base import EmbedderIdentityMismatchError

    diagnostics = diagnostics if diagnostics is not None else RetrievalDiagnostics()
    diagnostics.models = {
        "embedding": str(getattr(cfg, "embedder_model", "")),
        "reranker_cpu": str(getattr(cfg, "reranker_model_cpu", "")),
        "reranker_gpu": str(getattr(cfg, "reranker_model_gpu", "")),
    }
    try:
        col = (
            context.get_collection("castle_drawers")
            if context is not None
            else _get_collection(palace_path, collection_name="castle_drawers", create=False)
        )
    except EmbedderIdentityMismatchError:
        # Surface the friendly migration prompt — don't swallow it as "no palace".
        raise
    except Exception as exc:
        if profile == "memory-v1":
            raise SearchUnavailableError("recall unavailable") from exc
        # No palace found — degrade to empty results rather than crashing.
        return []

    where_sql = _build_where_sql(wing, room, allowed_wings)

    def in_scope(row):
        return _row_in_scope(
            row,
            wing=wing,
            room=room,
            allowed_wings=allowed_wings,
            profile=profile,
            root=getattr(context.paths, "root", palace_path)
            if context is not None
            else palace_path,
        )

    # ── Stage 1a: dense vector search ──────────────────────────────────────
    try:
        if profile == "memory-v1" and not getattr(col, "dense_available", True):
            raise SearchUnavailableError("dense identity is unverified")
        [query_vec] = (
            embed_texts([query], cfg=cfg)
            if (context is not None or profile is not None or explicit_config)
            else embed_texts([query])
        )
        dense_rows = col.vector_search(query_vec, n_results=100, where=where_sql)
        diagnostics.available_signals.append("dense")
    except Exception:
        dense_rows = []
        diagnostics.failed_signals.append("dense")

    # ── Stage 1b: Tantivy FTS sparse search ────────────────────────────────
    try:
        sparse_rows = col.fts_search(query, n_results=100, where=where_sql)
        diagnostics.available_signals.append("sparse")
    except Exception:
        sparse_rows = []
        diagnostics.failed_signals.append("sparse")

    # ── Stage 1c: KG-hop ───────────────────────────────────────────────────
    kg_rows: list = []
    from .context import PalacePaths

    paths = context.paths if context is not None else PalacePaths.resolve(palace_path)
    entities_path = paths.entity_registry
    kg_path = paths.knowledge_graph
    if entities_path.exists() and kg_path.exists():
        try:
            kg_rows = _kg_recall_rows(
                query, col, cfg, paths, where_sql, in_scope, context=context, profile=profile
            )
            diagnostics.available_signals.append("kg")
        except Exception:
            # KG-hop is best-effort; degrade to dense+sparse only.
            kg_rows = []
            diagnostics.failed_signals.append("kg")
    else:
        diagnostics.disabled_signals.append("kg")

    if profile == "memory-v1" and not diagnostics.available_signals:
        raise SearchUnavailableError("all recall signals unavailable")

    # Defend the scope boundary even if a recall provider ignores its filter.
    dense_rows = [r for r in dense_rows if in_scope(r)]
    sparse_rows = [r for r in sparse_rows if in_scope(r)]
    kg_rows = [r for r in kg_rows if in_scope(r)]

    # ── Stage 2: fusion + recency boost ────────────────────────────────────
    def _to_refs(rows):
        return [
            CandidateRef(
                drawer_id=_extract_id(r),
                timestamp_unix=_extract_ts(r),
                novelty=_extract_novelty(r),
            )
            for r in rows
            if _extract_id(r)
        ]

    rank_lists = {
        "dense": _to_refs(dense_rows),
        "sparse": _to_refs(sparse_rows),
        "kg": _to_refs(kg_rows),
    }
    weights = {
        "dense": cfg.weight_dense,
        "sparse": cfg.weight_sparse,
        "kg": cfg.weight_kg,
    }

    fused = weighted_rrf(rank_lists, weights, k_rrf=cfg.k_rrf)
    fused = apply_recency(
        fused,
        now=datetime.now(timezone.utc),
        tau_days=cfg.recency_tau_days,
        max_boost=cfg.recency_max_boost,
    )
    if info_weight or cfg.info_weight_enabled:
        fused = apply_info_weight(
            fused,
            threshold=cfg.info_weight_threshold,
            min_factor=cfg.info_weight_min_factor,
        )

    fused, aliases = (
        _group_memory_candidates(fused, dense_rows + sparse_rows + kg_rows)
        if profile == "memory-v1"
        else (fused, {})
    )

    # ── Stage 3: cross-encoder rerank ──────────────────────────────────────
    k_cap = cfg.reranker_k_hook if is_hook_call else cfg.reranker_k_interactive
    top_k_ids = [s.drawer_id for s in fused[:k_cap]]
    if not top_k_ids:
        return []

    # Derive entity-match flag from fusion provenance for the top-K candidates.
    entity_match_by_id = {sc.drawer_id: "kg" in sc.contributing_signals for sc in fused[:k_cap]}

    rows_by_id = {_extract_id(r): r for r in col.get_by_ids(top_k_ids) if in_scope(r)}
    top_k_rows = [rows_by_id[i] for i in top_k_ids if i in rows_by_id]
    if not top_k_rows:
        return []

    # Attach entity-match flag to each row so SOAR can read it via _push_working_memory.
    for row in top_k_rows:
        if isinstance(row, dict):
            row["entity_match"] = entity_match_by_id.get(row.get("id"), False)

    docs = [_extract_text(r) for r in top_k_rows]
    rerank_scores = (
        rerank(
            query,
            docs,
            device="cpu" if getattr(cfg, "embedding_device", "auto") in {"cpu", "mps"} else "auto",
            cfg=cfg,
        )
        if context is not None or profile is not None
        else rerank(query, docs, cfg=cfg)
    )
    if len(rerank_scores) != len(top_k_rows) or any(
        not math.isfinite(float(s)) for s in rerank_scores
    ):
        raise SearchUnavailableError("reranker returned missing or nonfinite scores")
    for score, row in zip(rerank_scores, top_k_rows):
        row["raw_relevance_score"] = float(score)
    reranked = sorted(zip(rerank_scores, top_k_rows), key=lambda x: -x[0])

    # ── Stage 4 + Stage 5 + Stage 6 (optional, composable order) ────────────
    if profile != "memory-v1":
        reranked = _apply_optional_stages(query, reranked, cfg, mode)

    return [
        {
            "id": _extract_id(r),
            **aliases.get(_extract_id(r), {}),
            # "text" is the legacy key expected by MCP callers, tests, and
            # benchmarks; "document" is kept for forward-compat callers.
            "text": _extract_text(r),
            "document": _extract_text(r),
            "score": float(s),
            "raw_relevance_score": float(r.get("raw_relevance_score", s)),
            "adjustment_basis": r.get("adjustment_basis"),
            "rank": rank,
            "text_sha256": hashlib.sha256(_extract_text(r).encode("utf-8")).hexdigest(),
            "revision": _row_metadata(r).get("source_revision", _row_metadata(r).get("revision")),
            "representation": _row_metadata(r).get("representation"),
            "provenance": _row_metadata(r),
            "wing": r.get("wing", "") if isinstance(r, dict) else "",
            "room": r.get("room", "") if isinstance(r, dict) else "",
            # NEW (PR follow-up to #4a — unblocks SOAR recency-boost):
            "source_file": (r.get("source_file") or "") if isinstance(r, dict) else "",
            "created_at": _get_filed_at(r),
            "similarity": float(s),  # alias to score (test asserts type only)
            "entity_match": (r.get("entity_match", False) if isinstance(r, dict) else False),
            # SOAR audit trail — populated only when --soar-boost is on (Stage 5
            # ran). Always present so callers can rely on the key shape.
            "soar_tags": (list(r.get("soar_tags", [])) if isinstance(r, dict) else []),
            "soar_boost": (float(r.get("soar_boost", 1.0)) if isinstance(r, dict) else 1.0),
            "score_pre_soar": (
                float(r.get("score_pre_soar", s)) if isinstance(r, dict) else float(s)
            ),
            # Quality audit trail — populated only when --quality-rerank is on
            # (Stage 6 ran). Always present so callers can rely on the key shape.
            "quality_score": (r.get("quality_score") if isinstance(r, dict) else None),
            "quality_tier": (r.get("quality_tier") if isinstance(r, dict) else None),
            "quality_boost": (float(r.get("quality_boost", 1.0)) if isinstance(r, dict) else 1.0),
            "score_pre_quality": (
                float(r.get("score_pre_quality", s)) if isinstance(r, dict) else float(s)
            ),
            # LLM judge audit trail — populated only when Stage 4 ran AND
            # either reordered hits or hit an error. Absent otherwise (no
            # audit line emitted for identity-order success).
            "judge_status": (r.get("judge_status") if isinstance(r, dict) else None),
        }
        for rank, (s, r) in enumerate(reranked[:n_results], 1)
    ]


def _row_metadata(row):
    raw = row.get("metadata_json")
    try:
        meta = json.loads(raw) if isinstance(raw, str) else (row.get("metadata") or {})
        return meta if isinstance(meta, dict) else {}
    except (ValueError, TypeError):
        return {}


def _row_in_scope(row, *, wing, room, allowed_wings, profile, root):
    if profile == "memory-v1":
        from .revisions import revision_completed

        metadata = _row_metadata(row)
        if (
            row.get("room") == "_registry"
            or metadata.get("room") == "_registry"
            or metadata.get("ingest_mode") == "registry"
        ):
            return False
        if not revision_completed(root, metadata, record_id=_extract_id(row)):
            return False
    return (
        (allowed_wings is None or row.get("wing") in allowed_wings)
        and (wing is None or row.get("wing") == wing)
        and (room is None or row.get("room") == room)
    )


def _capture_sort_key(captured_at, record_id):
    """Newest capture first; legacy naive times assume UTC for ordering only.

    Stored/public capture values remain unchanged. Unknown or malformed values
    sort last with a stable ID fallback instead of guessing a capture time.
    """
    from datetime import datetime, timezone

    timestamp = float("-inf")
    if isinstance(captured_at, str):
        try:
            captured = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            if captured.tzinfo is None or captured.utcoffset() is None:
                captured = captured.replace(tzinfo=timezone.utc)
            timestamp = captured.timestamp()
        except (ValueError, OverflowError):
            pass
    return -timestamp, str(record_id)


def _kg_recall_rows(query, col, cfg, paths, where_sql, in_scope, *, context, profile):
    from .entity_registry import EntityRegistry
    from .knowledge_graph import KnowledgeGraph

    registry_options = {"read_only": True} if profile == "memory-v1" else {}
    reg = (
        context.registry
        if context is not None
        else EntityRegistry.load(path=paths.entity_registry, **registry_options)
    )
    kg = None
    try:
        if profile == "memory-v1":
            kg = (
                context.graph
                if context is not None
                else KnowledgeGraph(db_path=str(paths.knowledge_graph), read_only=True)
            )
            # A query with no entity matches must not disguise a broken graph
            # as a successfully available recall signal.
            kg.validate_recall()
        matches = reg.lookup_in_text(query)
        if not matches:
            return []
        if kg is None:
            kg = (
                context.graph
                if context is not None
                else KnowledgeGraph(db_path=str(paths.knowledge_graph))
            )
        rows, offset = [], 0
        while len(rows) < cfg.kg_hop_top_n:
            ids = kg.find_drawers_by_entities(
                [m.entity_id for m in matches], limit=100, offset=offset
            )
            if not ids:
                break
            by_id = {
                _extract_id(row): row
                for row in col.get_by_ids(ids, where=where_sql)
                if in_scope(row)
            }
            rows.extend(by_id[rid] for rid in ids if rid in by_id)
            offset += len(ids)
            if len(ids) < 100:
                break
        return rows[: cfg.kg_hop_top_n]
    finally:
        if context is None and kg is not None:
            kg.close()


def _group_memory_candidates(fused, rows):
    """Group exact passages before the reranker budget without summing copies.

    Alternate completeness describes the known scoped recall pool, not an
    exhaustive scan of every source occurrence in the palace.
    """
    from dataclasses import replace

    by_id = {_extract_id(row): row for row in rows if _extract_id(row)}
    groups = {}
    for candidate in fused:
        row = by_id.get(candidate.drawer_id)
        if row is not None:
            digest = hashlib.sha256(_extract_text(row).encode("utf-8")).hexdigest()
            groups.setdefault(digest, []).append(candidate)
    grouped, aliases = [], {}
    for candidates in groups.values():
        candidates.sort(
            key=lambda c: _capture_sort_key(
                _row_metadata(by_id[c.drawer_id]).get("filed_at"), c.drawer_id
            )
        )
        primary = candidates[0]
        grouped.append(
            replace(
                primary,
                score=max(c.score for c in candidates),
                contributing_signals=frozenset(
                    signal for c in candidates for signal in c.contributing_signals
                ),
            )
        )
        alternate_ids = [c.drawer_id for c in candidates[1:]]
        aliases[primary.drawer_id] = {
            "alternate_record_ids": alternate_ids[:8],
            "alternate_sources_complete": len(alternate_ids) <= 8,
        }
    grouped.sort(key=lambda c: (-c.score, c.drawer_id))
    return grouped, aliases
