"""kg_enricher.py — Phase 2 of `castle mine` / `castle reindex`.

Walks the un-indexed drawer set, extracts entity candidates, classifies
+ promotes high-confidence ones to the registry, and writes
``(entity, mentioned_in, drawer_id)`` triples to the knowledge graph.

Opt-in by virtue of being called from the miner's end-of-pipeline hook.
Local-only — regex + signal-counting (no LLM, no network). Append-only,
idempotent, self-healing on interrupt.

See spec: docs/superpowers/specs/2026-05-14-kg-enrichment-design.md
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from collections import Counter, defaultdict
from itertools import islice
from pathlib import Path
from typing import Iterable

from . import entity_detector
from . import palace as palace_mod


ADAPTER_NAME = "entity-mention-indexer"

# Entities are read from the first MAX_DRAWER_CHARS of a drawer. Most drawers
# are under 1 KB, but a whole session file filed as one drawer can run to
# 100+ MB: on one palace 344 such drawers held 12 of its 13.5 GB of text, and
# every stage spent its time in them.
MAX_DRAWER_CHARS = 200_000


def _batched(iterable, size):
    """Yield bounded batches, including the tail, on Python 3.10 and later."""
    if size < 1:
        raise ValueError("batch size must be at least one")
    iterator = iter(iterable)
    while batch := tuple(islice(iterator, size)):
        yield batch


@palace_mod.mutation_operation()
def enrich_palace(palace_path: str, cfg, *, context=None) -> dict:
    """Public entry point. Runs all four steps of Phase 2.

    Returns ``{"drawers_scanned", "entities_promoted", "triples_written",
    "elapsed_s"}``. Never raises — caller catches at miner boundary.
    """
    started = time.time()
    from .context import PalacePaths

    paths = context.paths if context is not None else PalacePaths.resolve(palace_path)
    col = (
        context.get_collection()
        if context is not None
        else palace_mod.get_collection(palace_path=palace_path)
    )

    all_ids = col.list_drawer_ids()
    if not all_ids:
        return _result(0, 0, 0, started)

    kg_path = str(paths.knowledge_graph)
    max_drawers = _max_drawers(cfg)
    pending = _pending_ids(all_ids=all_ids, kg_path=kg_path)
    work_ids = pending[:max_drawers] if max_drawers > 0 else pending
    remaining = len(pending) - len(work_ids)
    if not work_ids:
        return _result(0, 0, 0, started, remaining=0)

    mention_map, freq_by_name = _walk_corpus(col, work_ids=work_ids, cfg=cfg)

    # ── Stage B: load registry, classify, promote ────────────────────
    from .entity_registry import EntityRegistry

    registry = (
        context.registry if context is not None else EntityRegistry.load(path=paths.entity_registry)
    )

    # Determine which drawer_ids are needed for Stage B scoring
    candidates_to_score = [
        name for name in freq_by_name if registry.lookup(name).get("type") == "unknown"
    ]
    sample_n = cfg.entity_score_sample_drawers
    score_drawer_ids: set[str] = set()
    for name in candidates_to_score:
        score_drawer_ids.update(sorted(mention_map.get(name, ()))[:sample_n])

    text_by_id = _build_text_cache(col, drawer_ids=score_drawer_ids, cfg=cfg)

    promoted = _classify_and_promote(
        mention_map=mention_map,
        freq_by_name=freq_by_name,
        text_by_id=text_by_id,
        registry=registry,
        cfg=cfg,
    )
    registry.save()

    # ── Stage C: write triples for everything remaining in mention_map ─
    from .knowledge_graph import KnowledgeGraph

    kg = context.graph if context is not None else KnowledgeGraph(db_path=kg_path)
    try:
        triples_written = _write_triples(mention_map=mention_map, registry=registry, kg=kg)
    finally:
        if context is None:
            kg.close()

    # Only after the triples landed: a run killed mid-way must retry these drawers.
    _mark_scanned(kg_path=kg_path, drawer_ids=work_ids)

    return _result(
        drawers_scanned=len(work_ids),
        entities_promoted=len(promoted),
        triples_written=triples_written,
        started=started,
        remaining=remaining,
    )


def is_disabled(explicit: bool = False) -> bool:
    """Whether Phase 2 should be skipped: an explicit ``--skip-kg`` or
    ``CASTLE_SKIP_KG_ENRICH=1`` in the environment (hooks, bulk backfills)."""
    if explicit:
        return True
    return os.environ.get("CASTLE_SKIP_KG_ENRICH", "").strip().lower() in ("1", "true", "yes")


def _max_drawers(cfg) -> int:
    try:
        return max(0, int(getattr(cfg, "kg_enrich_max_drawers", 0) or 0))
    except (TypeError, ValueError):
        return 0


def _pending_ids(*, all_ids: list[str], kg_path: str) -> list[str]:
    """all_ids minus drawers already covered: those with this adapter's triples
    and those walked before without any mention (progress table). Order
    matches all_ids, so a capped run always continues where the last stopped."""
    covered = _query_done_ids(kg_path=kg_path) | _query_scanned_ids(kg_path=kg_path)
    return [i for i in all_ids if i not in covered]


def _select_work_ids(*, all_ids: list[str], kg_path: str, max_drawers: int = 0) -> list[str]:
    """Pending drawers for one run, the first ``max_drawers`` of them when capped.

    One unbounded walk over a palace of hundreds of thousands of drawers
    builds a mention map of every capitalized word in it — tens of GB on a
    real palace, which is what used to get the Stop-hook miner killed. The
    cap turns the backlog into bounded increments across runs."""
    pending = _pending_ids(all_ids=all_ids, kg_path=kg_path)
    return pending[:max_drawers] if max_drawers > 0 else pending


_SCANNED_TABLE = "enrich_scanned"


def _mark_scanned(*, kg_path: str, drawer_ids: Iterable[str]) -> None:
    """Record drawers this adapter has walked, whether or not they yielded a triple."""
    ids = list(drawer_ids)
    if not ids:
        return
    Path(kg_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(kg_path, timeout=10) as conn:
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {_SCANNED_TABLE} ("
            " drawer_id TEXT NOT NULL, adapter_name TEXT NOT NULL, scanned_at TEXT NOT NULL,"
            " PRIMARY KEY (drawer_id, adapter_name))"
        )
        now = datetime.now(timezone.utc).isoformat()
        conn.executemany(
            f"INSERT OR IGNORE INTO {_SCANNED_TABLE} (drawer_id, adapter_name, scanned_at)"
            " VALUES (?, ?, ?)",
            [(i, ADAPTER_NAME, now) for i in ids],
        )


def _query_scanned_ids(*, kg_path: str) -> set[str]:
    if not Path(kg_path).exists():
        return set()
    try:
        with sqlite3.connect(kg_path, timeout=10) as conn:
            rows = conn.execute(
                f"SELECT drawer_id FROM {_SCANNED_TABLE} WHERE adapter_name = ?",
                (ADAPTER_NAME,),
            ).fetchall()
        return {row[0] for row in rows}
    except sqlite3.Error:
        # Table absent before the first capped run completes.
        return set()


def _query_done_ids(*, kg_path: str) -> set[str]:
    """Pull source_drawer_ids of triples written by this adapter."""
    if not Path(kg_path).exists():
        return set()
    try:
        with sqlite3.connect(kg_path) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT source_drawer_id
                FROM triples
                WHERE adapter_name = ?
                  AND source_drawer_id IS NOT NULL
                """,
                (ADAPTER_NAME,),
            ).fetchall()
        return {row[0] for row in rows}
    except sqlite3.Error:
        # Missing table on first run is normal — KnowledgeGraph creates schema
        # on its own first write. Treat any read error here as "nothing done".
        return set()


def _walk_corpus(col, *, work_ids: Iterable[str], cfg) -> tuple[dict, Counter]:
    """Stage A: single regex pass per drawer. Returns
    ``(mention_map, freq_by_name)`` where mention_map is
    ``name → set[drawer_id]`` and freq_by_name is corpus-wide name counts."""
    mention_map: dict[str, set[str]] = defaultdict(set)
    freq_by_name: Counter = Counter()

    for drawer_id, text in _iter_texts(col, work_ids, batch_size=1000):
        per_drawer = entity_detector.extract_candidates(text, cfg.entity_languages)
        for name, count in per_drawer.items():
            mention_map[name].add(drawer_id)
            freq_by_name[name] += count

    return dict(mention_map), freq_by_name


def _build_text_cache(col, *, drawer_ids: set[str], cfg) -> dict[str, str]:
    """Batched bulk fetch. Returns ``{drawer_id: text}`` for the requested
    ids. Skips the LanceDB vector + metadata columns by reading text only
    from each returned row."""
    if not drawer_ids:
        return {}
    return dict(_iter_texts(col, sorted(drawer_ids), batch_size=cfg.entity_fetch_batch_size))


def _iter_texts(col, ids: Iterable[str], *, batch_size: int):
    """Yield ``(drawer_id, text)`` for each of ``ids`` present in ``col``.

    A collection with ``iter_id_text`` is read in one sequential pass of the
    ``id`` and ``text`` columns, filtered here, and left as soon as every
    wanted drawer was seen. ``get_by_ids`` is an unindexed ``id IN (...)``
    query: on LanceDB each batch scans the whole table, so fetching a large
    palace batch by batch took hours where one pass takes seconds.
    Collections without ``iter_id_text`` keep the batched fetch.

    Texts are cut at ``MAX_DRAWER_CHARS``.
    """
    if hasattr(col, "iter_id_text"):
        wanted = set(ids)
        if not wanted:
            return
        seen = 0
        for drawer_id, text in col.iter_id_text():
            if drawer_id in wanted:
                yield drawer_id, (text or "")[:MAX_DRAWER_CHARS]
                seen += 1
                if seen == len(wanted):
                    return
        return
    for batch in _batched(ids, batch_size):
        for row in col.get_by_ids(batch):
            yield row["id"], (row["text"] or "")[:MAX_DRAWER_CHARS]


def _classify_and_promote(
    *,
    mention_map: dict,
    freq_by_name: Counter,
    text_by_id: dict,
    registry,
    cfg,
) -> set[str]:
    """Stage B: score each unregistered candidate against a per-candidate
    sample of ~SAMPLE_N drawer texts. Classify. Promote if confident,
    else drop from mention_map.

    Returns the set of names newly added to the registry by this call.
    Mutates ``mention_map`` (deletes rejected entries) and ``registry``
    (adds learned entries). Caller is responsible for ``registry.save()``.
    """
    sample_n = cfg.entity_score_sample_drawers
    threshold = cfg.entity_promote_threshold
    languages = cfg.entity_languages

    candidates_to_score = [
        name for name in freq_by_name if registry.lookup(name).get("type") == "unknown"
    ]

    promoted: set[str] = set()
    for name in candidates_to_score:
        sample_ids = sorted(mention_map.get(name, ()))[:sample_n]
        sample_texts = [text_by_id[did] for did in sample_ids if did in text_by_id]
        if not sample_texts:
            # Defensive: no usable sample → reject
            if name in mention_map:
                del mention_map[name]
            continue
        sample = "\n".join(sample_texts)
        scores = entity_detector.score_entity(
            name, _near_name(name, sample), sample.splitlines(), languages
        )
        cls = entity_detector.classify_entity(name, freq_by_name[name], scores)

        if cls["type"] in ("person", "project") and cls["confidence"] >= threshold:
            registry.add_learned(name, type=cls["type"], confidence=cls["confidence"])
            promoted.add(name)
        else:
            if name in mention_map:
                del mention_map[name]

    return promoted


# Every scoring pattern embeds the name and reaches at most a few words past
# it (``pip install NAME``, ``the NAME architecture``), so only the text
# around each occurrence can match. Scanning whole 20-drawer samples with ~40
# regexes per candidate made Stage B take hours on a large palace.
_NAME_WINDOW_CHARS = 80
# Every window reaches _NAME_WINDOW_CHARS past each occurrence it holds, so
# no pattern can start in one window and finish in the next, and a window
# never starts at the name itself (no false ``^NAME``).
_WINDOW_SEPARATOR = "\n"


def _near_name(name: str, text: str) -> str:
    """The text around each occurrence of ``name``, as scoring sees it.

    Windows are widened to whole words (so ``\\b`` behaves as in the full
    text) and through whitespace runs (so ``\\s+`` is not cut short), then
    merged.
    """
    n = len(text)
    spans: list[list[int]] = []
    for m in re.finditer(re.escape(name), text, re.IGNORECASE):
        lo = _widen_left(text, max(0, m.start() - _NAME_WINDOW_CHARS))
        hi = _widen_right(text, min(n, m.end() + _NAME_WINDOW_CHARS))
        if spans and lo <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], hi)
        else:
            spans.append([lo, hi])
    return _WINDOW_SEPARATOR.join(text[lo:hi] for lo, hi in spans)


def _widen_left(text: str, lo: int) -> int:
    """Move a window start off a cut word, and back over a cut whitespace
    run plus the word before it."""
    while 0 < lo < len(text) and _is_word(text[lo - 1]) and _is_word(text[lo]):
        lo -= 1
    if lo > 0 and text[lo - 1].isspace():
        while lo > 0 and text[lo - 1].isspace():
            lo -= 1
        while lo > 0 and _is_word(text[lo - 1]):
            lo -= 1
    return lo


def _widen_right(text: str, hi: int) -> int:
    """Mirror of ``_widen_left`` for a window end (exclusive)."""
    n = len(text)
    while 0 < hi < n and _is_word(text[hi - 1]) and _is_word(text[hi]):
        hi += 1
    if hi < n and text[hi].isspace():
        while hi < n and text[hi].isspace():
            hi += 1
        while hi < n and _is_word(text[hi]):
            hi += 1
    return hi


def _is_word(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _write_triples(*, mention_map: dict, registry, kg) -> int:
    """Stage C: write one triple per (name, drawer_id) pair. Returns the
    count attempted (DB de-duplicates via INSERT OR IGNORE — re-runs are
    safe even though this counter doesn't know about no-ops).

    Skips entries where the registry lookup returns ``"unknown"`` — a
    defensive safety net that shouldn't fire in normal Stage B flow but
    guards against logic regressions.
    """
    count = 0
    for name, drawer_ids in mention_map.items():
        if registry.lookup(name).get("type") == "unknown":
            continue
        for drawer_id in drawer_ids:
            kg.add_triple(
                name,
                "mentioned_in",
                drawer_id,
                source_drawer_id=drawer_id,
                adapter_name=ADAPTER_NAME,
            )
            count += 1
    return count


def _result(
    drawers_scanned: int,
    entities_promoted: int,
    triples_written: int,
    started: float,
    remaining: int = 0,
) -> dict:
    return {
        "drawers_remaining": remaining,
        "drawers_scanned": drawers_scanned,
        "entities_promoted": entities_promoted,
        "triples_written": triples_written,
        "elapsed_s": round(time.time() - started, 2),
    }
