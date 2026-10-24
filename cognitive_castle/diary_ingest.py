"""
diary_ingest.py — Ingest daily summary files into the palace.

Architecture:
- One immutable full-text drawer per source, wing and content revision.
- Closets pack topics up to CLOSET_CHAR_LIMIT, never split mid-topic.
- Each changed revision indexes its complete day and retains prior closets.
- Content hashes detect corrections and growth. State lives under
  ``~/.castle/state/``, never inside the user's diary directory.
- Per-file ``mine_lock`` so concurrent ingest from two terminals can't race.
- Entities extracted and stamped on metadata for filterable search.

Usage:
    python -m cognitive_castle.diary_ingest --dir ~/daily_summaries --palace ~/.castle/palace
    python -m cognitive_castle.diary_ingest --dir ~/daily_summaries --palace ~/.castle/palace --force
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from .miner import _extract_entities_for_metadata
from .palace import (
    build_closet_lines,
    get_closets_collection,
    get_collection,
    mine_lock,
    mutation_operation,
    upsert_closet_lines,
)
from .revisions import RevisionIdentity, RevisionManifest, atomic_json, publish_revision

DIARY_ENTRY_RE = re.compile(r"^## .+", re.MULTILINE)


def _state_file_for(palace_path: str, diary_dir: Path) -> Path:
    """Return the per-(palace, diary-dir) state-file path under ~/.castle/state.

    Keyed by sha256 of (palace_path, diary_dir) so multiple diary folders
    pointing at the same palace each get an independent state file. The
    state file is *never* written inside the user's diary directory.
    """
    state_root = Path(os.path.expanduser("~")) / ".castle" / "state"
    state_root.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{palace_path}|{diary_dir}".encode()).hexdigest()[:24]
    return state_root / f"diary_ingest_{key}.json"


def _split_entries(text):
    """Split diary text into (header, body) pairs per ## entry."""
    parts = DIARY_ENTRY_RE.split(text)
    headers = DIARY_ENTRY_RE.findall(text)
    entries = []
    for i, header in enumerate(headers):
        body = parts[i + 1] if i + 1 < len(parts) else ""
        entries.append((header.strip(), body.strip()))
    return entries


def _diary_drawer_id(wing: str, date_str: str, source_file="", revision="") -> str:
    """Stable, wing-scoped drawer ID. Two diaries (e.g. 'work' vs 'personal')
    sharing the same date never collide."""
    identity = (
        f"{wing}|{date_str}" if not source_file else f"{wing}|{date_str}|{source_file}|{revision}"
    )
    suffix = hashlib.sha256(identity.encode()).hexdigest()[:24]
    return f"drawer_diary_{suffix}"


def _diary_closet_id_base(wing: str, date_str: str) -> str:
    suffix = hashlib.sha256(f"{wing}|{date_str}".encode()).hexdigest()[:24]
    return f"closet_diary_{suffix}"


@mutation_operation()
def ingest_diaries(
    diary_dir,
    palace_path,
    wing="diary",
    force=False,
):
    """Ingest daily summary files into the palace.

    Each exact source revision gets its own drawer and complete topic index.
    ``force=True`` bypasses state hints, but reuses a verified complete revision
    without rewriting evidence. Earlier revisions are always retained.
    """
    diary_dir = Path(diary_dir).expanduser().resolve()
    if not diary_dir.exists():
        print(f"Diary directory not found: {diary_dir}")
        return {"days_updated": 0, "closets_created": 0}

    diary_files = sorted(diary_dir.glob("*.md"))
    if not diary_files:
        print(f"No .md files in {diary_dir}")
        return {"days_updated": 0, "closets_created": 0}

    state_file = _state_file_for(str(palace_path), diary_dir)
    if force or not state_file.exists():
        state: dict = {}
    else:
        try:
            state = json.loads(state_file.read_text())
        except Exception:
            state = {}

    drawers_col = get_collection(palace_path)
    closets_col = get_closets_collection(palace_path)

    days_updated = 0
    closets_created = 0

    for diary_path in diary_files:
        with diary_path.open(encoding="utf-8", errors="strict", newline="") as stream:
            text = stream.read()
        if len(text.strip()) < 50:
            continue

        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", diary_path.stem)
        if not date_match:
            continue
        date_str = date_match.group(1)

        # Skip if content hasn't changed
        state_key = f"{wing}|{diary_path.name}"
        revision = hashlib.sha256(text.encode("utf-8")).hexdigest()
        curr_size = len(text)
        if revision == state.get(state_key, {}).get("text_sha256") and not force:
            continue

        now_iso = datetime.now(timezone.utc).isoformat()
        drawer_id = _diary_drawer_id(wing, date_str, str(diary_path), revision)
        entities = _extract_entities_for_metadata(text)
        source_file = str(diary_path)

        # Serialize per source — two terminals running ingest at once must
        # not interleave the upsert + closet-rebuild.
        with mine_lock(source_file):
            from .revisions import reuse_completed_revision

            if reuse_completed_revision(
                drawers_col, closets_col, RevisionIdentity(source_file, wing, "diary"), revision
            ):
                state[state_key] = {
                    "size": curr_size,
                    "entry_count": len(_split_entries(text)),
                    "ingested_at": now_iso,
                    "text_sha256": revision,
                }
                continue
            drawer_meta = {
                "date": date_str,
                "wing": wing,
                "room": "daily",
                "source_file": source_file,
                "source_session": "daily_diary",
                "filed_at": now_iso,
                "representation": "diary",
                "source_revision": revision,
                "completion_protocol": 1,
                "ingest_complete": False,
            }
            if entities:
                drawer_meta["entities"] = entities
            drawers_col.upsert(
                documents=[text],
                ids=[drawer_id],
                metadatas=[drawer_meta],
            )

            entries = _split_entries(text)
            new_entries = entries
            closet_ids = []

            if new_entries:
                all_lines = []
                for header, body in new_entries:
                    entry_text = f"{header}\n{body}"
                    entry_lines = build_closet_lines(
                        source_file, [drawer_id], entry_text, wing, "daily"
                    )
                    all_lines.extend(entry_lines)

                if all_lines:
                    closet_id_base = drawer_id.replace("drawer_", "closet_", 1)
                    closet_meta = {
                        "date": date_str,
                        "wing": wing,
                        "room": "daily",
                        "source_file": source_file,
                        "filed_at": now_iso,
                        "representation": "diary",
                        "source_revision": revision,
                        "completion_protocol": 1,
                        "ingest_complete": False,
                    }
                    if entities:
                        closet_meta["entities"] = entities
                    n = upsert_closet_lines(closets_col, closet_id_base, all_lines, closet_meta)
                    closet_ids = [f"{closet_id_base}_{i:02d}" for i in range(1, n + 1)]
                    closets_created += n

            publish_revision(
                drawers_col,
                closets_col,
                RevisionManifest(
                    RevisionIdentity(source_file, wing, "diary"),
                    revision,
                    (drawer_id,),
                    tuple(closet_ids),
                ),
                palace_path=palace_path,
            )
            state[state_key] = {
                "size": curr_size,
                "entry_count": len(entries),
                "ingested_at": now_iso,
                "text_sha256": revision,
            }
        days_updated += 1

    atomic_json(state_file, state)
    if days_updated:
        print(f"Diary: {days_updated} days updated, {closets_created} new closets")

    return {"days_updated": days_updated, "closets_created": closets_created}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest daily summaries into the palace")
    parser.add_argument("--dir", required=True, help="Path to daily_summaries directory")
    parser.add_argument("--palace", default=os.path.expanduser("~/.castle/palace"))
    parser.add_argument("--wing", default="diary")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    ingest_diaries(args.dir, args.palace, wing=args.wing, force=args.force)
