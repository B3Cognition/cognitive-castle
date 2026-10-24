"""Palace maintenance: compact fragments and rebuild the full-text index.

Every Stop-hook ingest commits a handful of drawers as its own LanceDB
fragment, and the Tantivy FTS index is only built once, at table creation.
Months of background filing therefore leave a palace with thousands of
one-row fragments and an FTS index that covers a fraction of the rows.
LanceDB then falls back to scanning every unindexed row on each sparse
query, which is where a two-minute ``castle search`` comes from.

``optimize_palace`` repairs that without touching a single drawer, using
only LanceDB's own table API (no ``pylance`` dependency):

1. ``create_fts_index(replace=True)`` rebuilds the FTS index over every row.
   It runs first on purpose: Lance only merges fragments that share index
   coverage, so compacting before the rebuild leaves the old indexed rows
   in a fragment of their own. With ``fts_incremental`` the rebuild is
   skipped and step 2 adds the unindexed rows to the existing index instead.
2. ``Table.optimize()`` is Lance's single maintenance pass: it merges small
   fragments into large ones, adds new rows to existing indices, and prunes
   old versions — the latter only past the horizon we give it, which by
   default lies a century away, so nothing is removed. Lance writes the
   merged data as a *new* version; the old versions stay readable, so a
   crash mid-way leaves the palace exactly as it was (incremental only).
3. Only with an explicit ``prune_older_than_days`` does that horizon move
   to the present and old versions are removed to reclaim disk. The latest
   version is never removed. This step is the one irreversible action here,
   so it is opt-in and never the default.
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from typing import Optional
from .palace import mutation_operation

#: Tables a palace holds, in the order they are optimized.
PALACE_TABLES = ("castle_drawers", "castle_closets")

#: Column the Tantivy FTS index covers; the index LanceDB names ``text_idx``.
FTS_COLUMN = "text"
FTS_INDEX = "text_idx"

#: Cleanup horizon that keeps every version: Lance's ``optimize`` always
#: prunes versions older than its horizon, so "no prune" is a horizon no
#: version can be older than.
KEEP_VERSIONS = timedelta(days=365 * 100)


def _table_names(db) -> list[str]:
    """Table names across LanceDB versions: ``list_tables()`` wraps them, ``table_names()`` is flat."""
    if hasattr(db, "list_tables"):
        result = db.list_tables()
        names = getattr(result, "tables", result)
        return list(names)
    return list(db.table_names())


def _stat(stats, *path, default=None):
    """Read a nested field from ``Table.stats()``, a dict in some LanceDB versions, a dataclass in others."""
    node = stats
    for key in path:
        if node is None:
            return default
        node = node.get(key) if isinstance(node, dict) else getattr(node, key, None)
    return default if node is None else node


def _fragment_count(table) -> Optional[int]:
    try:
        return int(_stat(table.stats(), "fragment_stats", "num_fragments"))
    except Exception:
        return None


def _fts_coverage(table) -> tuple[Optional[int], Optional[int]]:
    """Return ``(indexed_rows, unindexed_rows)`` or ``(None, None)`` without an index."""
    try:
        stats = table.index_stats(FTS_INDEX)
    except Exception:
        return None, None
    if stats is None:
        return None, None
    return stats.num_indexed_rows, stats.num_unindexed_rows


def table_stats(table) -> dict:
    """Read-only snapshot of what makes a table slow: fragments, versions, FTS coverage."""
    # A table handle stays pinned to the version it opened; commits made by
    # ``optimize()`` are only visible after moving to the latest.
    table.checkout_latest()
    indexed, unindexed = _fts_coverage(table)
    try:
        total_bytes = int(_stat(table.stats(), "total_bytes", default=0))
    except Exception:
        total_bytes = 0
    return {
        "rows": table.count_rows(),
        "fragments": _fragment_count(table),
        "versions": len(table.list_versions()),
        "bytes": total_bytes,
        "fts_indexed_rows": indexed,
        "fts_unindexed_rows": unindexed,
    }


#: How many times a commit is retried when another writer (the Stop hook,
#: a concurrent ``castle mine``) lands a version in between.
COMMIT_ATTEMPTS = 5


def _is_retryable_conflict(exc: Exception) -> bool:
    text = str(exc)
    return "Retryable commit conflict" in text or "commit conflict" in text.lower()


def _commit_with_retry(table, operation, what: str):
    """Run ``operation()`` against the table's latest version, retrying on commit conflicts.

    Lance resolves most concurrent writes on its own; the cases it refuses
    (a ``CreateIndex`` preempted by a ``Rewrite``) are safe to retry once the
    table is checked out at the newest version, which is what
    ``checkout_latest`` does. A palace with a background miner appending
    rows mid-optimize must not turn a maintenance run into a crash.
    """
    last_exc: Optional[Exception] = None
    for _attempt in range(COMMIT_ATTEMPTS):
        table.checkout_latest()
        try:
            return operation()
        except Exception as exc:
            if not _is_retryable_conflict(exc):
                raise
            last_exc = exc
    raise RuntimeError(f"{what} kept conflicting with concurrent writers") from last_exc


def optimize_table(
    table,
    *,
    prune_older_than_days: Optional[int] = None,
    fts_heap_mb: Optional[int] = None,
    skip_fts: bool = False,
    skip_compact: bool = False,
    prune_unverified: bool = False,
    fts_incremental: bool = False,
) -> dict:
    """Rebuild one table's FTS index, run Lance's optimize pass, optionally prune.

    ``fts_heap_mb`` bounds the FTS writer heap (Lance default: 1 GB) for the
    full rebuild. ``skip_fts`` leaves the index alone; ``fts_incremental``
    adds only the rows the index does not cover yet (a fraction of the
    memory of a rebuild — a full rebuild over 800k rows needs >10 GB) and
    falls back to the full build without an index.

    ``skip_compact`` leaves out the Lance optimize pass. That pass is also
    what applies the incremental index update and the prune, so it cannot
    be combined with ``fts_incremental`` or ``prune_older_than_days``.

    ``prune_unverified`` also removes files that no version references but
    that are younger than Lance's 7-day grace period: the leftovers of a
    compaction or index build that was killed mid-way. Lance keeps them by
    default because they look like an in-progress write, so this is only
    safe when no other process (Stop hook, ``castle mine``) is writing.

    Returns ``before`` / ``after`` stats, the FTS action taken, the
    compaction fragment counts (``None`` when skipped), and the number of
    versions pruned (``None`` when pruning was not requested).
    """
    if skip_compact and (fts_incremental or prune_older_than_days is not None):
        raise ValueError(
            "--skip-compact leaves out the Lance optimize pass, which is what applies "
            "--fts-incremental and --prune-older-than; drop one of them"
        )

    before = table_stats(table)

    fts_kwargs: dict = {"replace": True}
    if fts_heap_mb is not None:
        fts_kwargs["writer_heap_size"] = fts_heap_mb * 1024 * 1024

    # FTS first, the optimize pass second: see the module docstring for why the order matters.
    fts = "skipped"
    if not skip_fts:
        indexed, _unindexed = _fts_coverage(table)
        if fts_incremental and indexed is not None:
            fts = "incremental"  # applied by the optimize pass below
        else:
            _commit_with_retry(
                table, lambda: table.create_fts_index(FTS_COLUMN, **fts_kwargs), "FTS index rebuild"
            )
            fts = "rebuilt"

    compaction: Optional[dict] = None
    pruned_versions: Optional[int] = None
    if not skip_compact:
        horizon = (
            timedelta(days=prune_older_than_days)
            if prune_older_than_days is not None
            else KEEP_VERSIONS
        )
        _commit_with_retry(
            table,
            lambda: table.optimize(cleanup_older_than=horizon, delete_unverified=prune_unverified),
            "optimize pass",
        )
        table.checkout_latest()
        compaction = {
            "fragments_before": before["fragments"],
            "fragments_after": _fragment_count(table),
        }
        if prune_older_than_days is not None:
            pruned_versions = before["versions"] - len(table.list_versions())

    return {
        "before": before,
        "after": table_stats(table),
        "fts": fts,
        "compaction": compaction,
        "pruned_versions": pruned_versions,
    }


@mutation_operation()
def optimize_palace(
    palace_path: str,
    *,
    dry_run: bool = False,
    prune_older_than_days: Optional[int] = None,
    fts_heap_mb: Optional[int] = None,
    skip_fts: bool = False,
    skip_compact: bool = False,
    prune_unverified: bool = False,
    fts_incremental: bool = False,
) -> dict:
    """Optimize every known table of the palace at ``palace_path``.

    ``dry_run`` only reports the current stats. The report's ``status`` is
    ``"unknown"`` without a palace, ``"dry-run"``, ``"ok"``, or ``"error"``
    when any table failed (the others are still processed).
    """
    report: dict = {"palace": palace_path, "status": "ok", "tables": {}}
    db_dir = os.path.join(palace_path, "lancedb")
    if not os.path.isdir(db_dir):
        report["status"] = "unknown"
        return report

    import lancedb

    db = lancedb.connect(db_dir)
    existing = set(_table_names(db))

    for name in PALACE_TABLES:
        if name not in existing:
            report["tables"][name] = {"status": "missing"}
            continue
        try:
            table = db.open_table(name)
            if dry_run:
                report["tables"][name] = {"status": "dry-run", "before": table_stats(table)}
                continue
            result = optimize_table(
                table,
                prune_older_than_days=prune_older_than_days,
                fts_heap_mb=fts_heap_mb,
                skip_fts=skip_fts,
                skip_compact=skip_compact,
                prune_unverified=prune_unverified,
                fts_incremental=fts_incremental,
            )
            result["status"] = "ok"
            report["tables"][name] = result
        except Exception as exc:  # one broken table must not hide the others
            report["tables"][name] = {"status": "error", "message": str(exc)}
            report["status"] = "error"

    if dry_run and report["status"] == "ok":
        report["status"] = "dry-run"
    return report


def _fmt_count(value: Optional[int]) -> str:
    return "?" if value is None else f"{value:,}"


def _fmt_stats(stats: dict) -> str:
    indexed = stats["fts_indexed_rows"]
    unindexed = stats["fts_unindexed_rows"]
    fts = (
        "no FTS index"
        if indexed is None
        else f"FTS {_fmt_count(indexed)} indexed / {_fmt_count(unindexed)} unindexed"
    )
    return (
        f"{stats['rows']:,} rows, {_fmt_count(stats['fragments'])} fragments, "
        f"{stats['versions']:,} versions, {stats['bytes'] / 1e9:.2f} GB, {fts}"
    )


def print_report(report: dict, file=None) -> None:
    """Human-readable rendering of an ``optimize_palace`` report."""
    out = file or sys.stdout
    print(f"\n{'=' * 55}", file=out)
    print("  Cognitive Castle — Optimize", file=out)
    print(f"{'=' * 55}\n", file=out)
    print(f"  Palace: {report['palace']}", file=out)
    if report["status"] == "unknown":
        print("  No palace found.\n", file=out)
        return
    for name, entry in report["tables"].items():
        print(f"\n  [{name}]", file=out)
        status = entry["status"]
        if status == "missing":
            print("    status:  missing (nothing to do)", file=out)
            continue
        if status == "error":
            print(f"    status:  ERROR — {entry['message']}", file=out)
            continue
        print(f"    before:  {_fmt_stats(entry['before'])}", file=out)
        if status == "dry-run":
            print("    status:  dry run, nothing changed", file=out)
            continue
        print(f"    fts:     {entry.get('fts', 'rebuilt')}", file=out)
        c = entry["compaction"]
        if c is None:
            print("    compact: skipped", file=out)
        else:
            print(
                f"    compact: {_fmt_count(c['fragments_before'])} fragments → "
                f"{_fmt_count(c['fragments_after'])}",
                file=out,
            )
        if entry["pruned_versions"] is not None:
            print(f"    pruned:  {entry['pruned_versions']:,} old versions", file=out)
        print(f"    after:   {_fmt_stats(entry['after'])}", file=out)
        print("    status:  OK", file=out)
    print(file=out)
    if report["status"] != "dry-run":
        print(
            "  Drawers are untouched: compaction rewrites files, never content. "
            "Old versions stay until you pass --prune-older-than.",
            file=out,
        )
        print(file=out)
