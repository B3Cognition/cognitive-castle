"""Drop superseded derived revisions: ``castle prune-revisions``.

Every time a source file changes, the miners append a complete new
revision of its drawers and keep the old ones (``_file_chunks_locked``:
"historical drawers are never removed"). For a project file that is the
history you want. For a *live transcript* it is not: the Stop hook re-mines
the growing session file after every turn, and each pass stores a full
copy of everything mined before. One palace held 339k such copies — 40% of
its rows — for 30 source files; one session had been filed 13 times.

Drawers filed before the current chunker (``normalize_version`` < 3, no
``source_revision``) are superseded the same way once the file has a
complete current revision: they are the whole-file "giant drawers" of the
old exchange chunker (344 of them held 12 of 13.5 GB of text on that
palace).

This module groups by canonical source, wing and representation. Only explicit
derived ``general`` revisions can be removed: keep the newest verified complete
revision and any newer incomplete work. Original project, exchange, diary and
sweep records and unclassified legacy records are always retained. Protocol-1
completion requires its checksummed manifest, not just a row hint.

Planning is read-only. Applying deletes rows, which is the one thing the
palace otherwise never does, so it is opt-in (``--apply``), refuses to run
while a hook miner is alive, and tells the user that Lance only frees the
space on the next ``castle optimize --prune-older-than``.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .config import CognitiveCastleConfig
from .revisions import revision_identity

#: Tables that carry ``source_revision`` metadata, in processing order.
TABLES = ("castle_closets", "castle_drawers")
DELETE_BATCH = 1000


class PruneRevisionsError(RuntimeError):
    pass


@dataclass
class SourcePlan:
    """What one source file holds in one table and what would go."""

    source_file: str
    table: str
    wing: str
    revisions: int
    kept_revision: Optional[str]
    kept_rows: int
    superseded_rows: int
    superseded_chars: int
    legacy_rows: int  # drawers without a revision key, counted in superseded_rows
    delete_ids: list = field(default_factory=list, repr=False)


@dataclass
class PrunePlan:
    palace: str
    sources: list  # of SourcePlan with superseded rows, largest first
    rows_total: int
    superseded_rows: int
    superseded_chars: int
    by_wing: dict
    applied: bool = False
    deleted_rows: int = 0

    def as_dict(self) -> dict:
        return {
            "palace": self.palace,
            "rows_total": self.rows_total,
            "superseded_rows": self.superseded_rows,
            "superseded_chars": self.superseded_chars,
            "by_wing": dict(sorted(self.by_wing.items(), key=lambda kv: -kv[1])),
            "sources": [
                {
                    "source_file": s.source_file,
                    "table": s.table,
                    "wing": s.wing,
                    "revisions": s.revisions,
                    "kept_revision": s.kept_revision,
                    "kept_rows": s.kept_rows,
                    "superseded_rows": s.superseded_rows,
                    "superseded_chars": s.superseded_chars,
                    "legacy_rows": s.legacy_rows,
                }
                for s in self.sources
            ],
            "applied": self.applied,
            "deleted_rows": self.deleted_rows,
        }


def _parse_meta(raw) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {}


def _iter_rows(col, batch_size: int):
    """Yield dict batches of id / wing / source_file / metadata_json / chars."""
    columns = {
        "id": "id",
        "wing": "wing",
        "source_file": "source_file",
        "metadata_json": "metadata_json",
        "chars": "length(text)",
    }
    try:
        for batch in col.iter_columns(columns, batch_size):
            yield batch
        return
    except Exception:  # SQL projection unsupported: measure the text here
        pass
    for batch in col.iter_columns(
        ["id", "wing", "source_file", "metadata_json", "text"], batch_size
    ):
        batch["chars"] = [len(t or "") for t in batch.pop("text")]
        yield batch


class _Revision:
    __slots__ = ("ids", "complete", "filed_at", "chars")

    def __init__(self):
        self.ids: list = []
        self.complete = False
        self.filed_at = ""
        self.chars = 0


def plan_table(col, table: str, *, wing: Optional[str] = None, batch_size: int = 10_000):
    """Return ``(SourcePlan list, rows_seen)`` for one collection."""
    # source_file -> revision key -> _Revision ; legacy rows under key None
    by_source: dict = defaultdict(lambda: defaultdict(_Revision))
    wing_of: dict = {}
    rows_seen = 0
    for batch in _iter_rows(col, batch_size):
        for drawer_id, w, source_file, raw, chars in zip(
            batch["id"], batch["wing"], batch["source_file"], batch["metadata_json"], batch["chars"]
        ):
            rows_seen += 1
            if wing is not None and (w or "") != wing:
                continue
            if not source_file:
                continue
            meta = _parse_meta(raw)
            identity = revision_identity(source_file, {**meta, "wing": w or ""})
            # Source history is irreplaceable; only explicitly derived views
            # are eligible. Unknown legacy rows are retained conservatively.
            if identity is None or identity.representation != "general":
                continue
            rev_key = meta.get("source_revision") or None
            rev = by_source[identity][rev_key]
            rev.ids.append(drawer_id)
            rev.chars += int(chars or 0)
            if meta.get("ingest_complete"):
                from .revisions import collection_palace_path, revision_completed

                if meta.get("completion_protocol") == 1:
                    root = collection_palace_path(col)
                    kind = "closet" if table == "castle_closets" else "drawer"
                    if root is not None and revision_completed(
                        root, meta, record_id=drawer_id, record_kind=kind
                    ):
                        rev.complete = True
                else:
                    rev.complete = True
            filed_at = meta.get("filed_at") or ""
            if filed_at > rev.filed_at:
                rev.filed_at = filed_at
            wing_of.setdefault(identity, w or "")

    plans = []
    for identity, revisions in by_source.items():
        complete = [(r.filed_at, key) for key, r in revisions.items() if key and r.complete]
        if not complete:
            continue
        kept_at, kept_key = max(complete)
        delete_ids: list = []
        superseded_chars = legacy_rows = 0
        for key, r in revisions.items():
            if key == kept_key:
                continue
            if key is None:
                legacy_rows += len(r.ids)
            elif not r.complete and r.filed_at > kept_at:
                continue  # newer and still being written: leave it alone
            delete_ids.extend(r.ids)
            superseded_chars += r.chars
        if not delete_ids:
            continue
        plans.append(
            SourcePlan(
                source_file=identity.source_file,
                table=table,
                wing=wing_of[identity],
                revisions=sum(1 for key in revisions if key),
                kept_revision=kept_key,
                kept_rows=len(revisions[kept_key].ids),
                superseded_rows=len(delete_ids),
                superseded_chars=superseded_chars,
                legacy_rows=legacy_rows,
                delete_ids=delete_ids,
            )
        )
    plans.sort(key=lambda p: -p.superseded_rows)
    return plans, rows_seen


def _miner_alive() -> Optional[str]:
    """Name of a hook pid file whose process is alive, if any."""
    from .hooks_cli import STATE_DIR, _pid_alive

    for name in ("mine.pid", "mine_transcript.pid"):
        try:
            pid = int((STATE_DIR / name).read_text().strip())
        except (OSError, ValueError):
            continue
        if _pid_alive(pid):
            return f"{name} (pid {pid})"
    return None


def prune_revisions(
    palace_path: Optional[str] = None,
    *,
    apply: bool = False,
    wing: Optional[str] = None,
    force: bool = False,
    batch_size: int = 10_000,
) -> PrunePlan:
    from contextlib import nullcontext
    from .palace import mutation_session

    palace = os.path.expanduser(palace_path) if palace_path else CognitiveCastleConfig().palace_path
    with mutation_session(palace) if apply else nullcontext():
        return _prune_revisions_locked(
            palace, apply=apply, wing=wing, force=force, batch_size=batch_size
        )


def _prune_revisions_locked(palace_path, *, apply, wing, force, batch_size):
    """Plan (and with ``apply``, perform) the removal of superseded revisions.

    ``force`` applies even while a hook miner's pid file names a live
    process. Without it, applying next to a running miner is refused: the
    miner may be writing the very revision this would keep.
    """
    from .palace import get_collection

    cfg = CognitiveCastleConfig()
    palace = os.path.expanduser(palace_path) if palace_path else cfg.palace_path
    if apply and not force:
        alive = _miner_alive()
        if alive:
            raise PruneRevisionsError(f"a miner is running ({alive}); wait for it or pass --force")

    sources: list = []
    collections = {}
    rows_total = 0
    for table in TABLES:
        try:
            col = get_collection(palace, collection_name=table, create=False)
        except Exception:
            continue
        if col is None or not hasattr(col, "iter_columns"):
            continue
        plans, seen = plan_table(col, table, wing=wing, batch_size=batch_size)
        rows_total += seen
        collections[table] = col
        sources.extend(plans)

    if apply:
        from .revisions import atomic_json
        from pathlib import Path
        import hashlib

        body = {
            "schema_version": 1,
            "complete": False,
            "tables": [{"table": p.table, "delete_ids": p.delete_ids} for p in sources],
        }
        body["checksum"] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        intent = Path(palace) / ".castle" / "prune-apply.json"
        atomic_json(intent, body)
        for p in sources:  # Closets before their drawer targets.
            for start in range(0, len(p.delete_ids), DELETE_BATCH):
                collections[p.table].delete(ids=p.delete_ids[start : start + DELETE_BATCH])
        body.pop("checksum")
        body["complete"] = True
        body["checksum"] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        atomic_json(intent, body)

    sources.sort(key=lambda p: -p.superseded_rows)
    by_wing: dict = defaultdict(int)
    for p in sources:
        by_wing[p.wing] += p.superseded_rows
    superseded = sum(p.superseded_rows for p in sources)
    return PrunePlan(
        palace=palace,
        sources=sources,
        rows_total=rows_total,
        superseded_rows=superseded,
        superseded_chars=sum(p.superseded_chars for p in sources),
        by_wing=dict(by_wing),
        applied=apply,
        deleted_rows=superseded if apply else 0,
    )


def format_plan(plan: PrunePlan, *, top: int = 10) -> str:
    lines = [
        f"Palace: {plan.palace}",
        f"  rows:       {plan.rows_total:,}",
        f"  superseded: {plan.superseded_rows:,} rows in {len(plan.sources)} source files "
        f"({plan.superseded_chars / 1e9:.2f} GB of text)",
    ]
    if plan.by_wing:
        wings = ", ".join(
            f"{w or '(none)'} {n:,}" for w, n in sorted(plan.by_wing.items(), key=lambda kv: -kv[1])
        )
        lines.append(f"  by wing:    {wings}")
    for p in plan.sources[:top]:
        legacy = f", {p.legacy_rows:,} legacy" if p.legacy_rows else ""
        lines.append(
            f"    {p.superseded_rows:>8,} rows  {p.revisions:>3} revisions  "
            f"keep {p.kept_rows:,}{legacy}  {p.table}  {p.source_file}"
        )
    if len(plan.sources) > top:
        lines.append(f"    … and {len(plan.sources) - top} more source files")
    lines.append("")
    if plan.applied:
        lines.append(
            f"  Deleted {plan.deleted_rows:,} rows. Lance keeps them in old versions until "
            "`castle optimize --prune-older-than 0` reclaims the disk."
        )
    elif plan.superseded_rows:
        lines.append("  Dry run: nothing deleted. Re-run with --apply to remove these rows.")
    else:
        lines.append("  Nothing to prune: every source file holds a single current revision.")
    return "\n".join(lines)
