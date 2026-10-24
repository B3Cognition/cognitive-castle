"""Historical disk reservations; no source reads, SQLite opens or mutations.

The supervised per-user admission serializes writers. A writer reserves its
whole physical envelope while every other retained shard is charged at its
actual size, including orphan stores and abandoned SQLite sidecars.
"""

import os
from pathlib import Path
import re
import shutil
import time

from .fast_memory import DB_NAME, HistoryBudgetRefusal, MemoryStore, _Unavailable

HISTORY_STORE_BYTES = 2 * 1024**3
HISTORY_TOTAL_BYTES = 8 * 1024**3
FREE_HEADROOM_BYTES = 2 * 1024**3
MAX_ROOT_ENTRIES = 64
CAPACITY_POLICY = 2
_SCAN_SECONDS = 0.5
_STORE_FILES = {DB_NAME, DB_NAME + "-journal", DB_NAME + "-wal", DB_NAME + "-shm"}
_ROOT_FILES = {
    "job.json": 2 * 1024**2,
    "job.json.tmp": 2 * 1024**2,
    "catalog.json": 16384,
    "catalog.lock": 0,
}


def _free_bytes(path):
    return shutil.disk_usage(path).free


def _safe_root(root):
    root = Path(root).absolute()
    if root.name != ".memory-history" or ".." in root.parts:
        raise _Unavailable("unsafe history root")
    for parent in (root, *root.parents):
        if parent.is_symlink():
            raise _Unavailable("symlink history ancestor")
    MemoryStore(root)._private(root, True)
    return root


def audit_history_storage(root):
    """Return actual bytes per retained store under a fixed metadata-work bound."""
    root = _safe_root(root)
    private = MemoryStore(root)._private
    deadline = time.monotonic() + _SCAN_SECONDS
    sizes = {}
    total = 0
    with os.scandir(root) as entries:
        for number, entry in enumerate(entries):
            if number >= MAX_ROOT_ENTRIES:
                raise HistoryBudgetRefusal("history_scan_limit")
            if time.monotonic() >= deadline:
                raise HistoryBudgetRefusal("history_scan_deadline")
            path = root / entry.name
            if entry.is_symlink():
                raise _Unavailable("symlink history entry")
            if re.fullmatch(r"[a-f0-9]{64}", entry.name):
                private(path, True)
                size = 0
                with os.scandir(path) as children:
                    for child_number, child in enumerate(children):
                        if child_number >= len(_STORE_FILES):
                            raise HistoryBudgetRefusal("history_scan_limit")
                        if time.monotonic() >= deadline:
                            raise HistoryBudgetRefusal("history_scan_deadline")
                        if child.name not in _STORE_FILES or child.is_symlink():
                            raise _Unavailable("unexpected history store entry")
                        child_path = path / child.name
                        private(child_path)
                        size += child_path.lstat().st_size
                if size > HISTORY_STORE_BYTES:
                    raise HistoryBudgetRefusal("history_store_budget")
                sizes[entry.name] = size
                total += size
                if total > HISTORY_TOTAL_BYTES:
                    raise HistoryBudgetRefusal("history_aggregate_budget")
            elif entry.name in {"snapshots", "jobs"}:
                # Original snapshots and archived bounded job manifests have
                # their own admission; never recursively scan source data here.
                private(path, True)
            else:
                limit = _ROOT_FILES.get(entry.name)
                if re.fullmatch(r"\.catalog-[a-f0-9]{24}", entry.name):
                    limit = 16384
                if limit is None:
                    raise _Unavailable("unexpected history root entry")
                private(path)
                if path.lstat().st_size > limit:
                    raise _Unavailable("oversized history metadata")
    return sizes


def admit_history_write(directory):
    """Reserve one complete transaction envelope before any SQLite side effect."""
    directory = Path(directory).absolute()
    if not re.fullmatch(r"[a-f0-9]{64}", directory.name):
        raise _Unavailable("invalid history store identity")
    sizes = audit_history_storage(directory.parent)
    current = sizes.get(directory.name, 0)
    if sum(sizes.values()) - current + HISTORY_STORE_BYTES > HISTORY_TOTAL_BYTES:
        raise HistoryBudgetRefusal("history_aggregate_budget")
    growth = max(0, HISTORY_STORE_BYTES - current)
    if _free_bytes(directory.parent) < FREE_HEADROOM_BYTES + growth:
        raise HistoryBudgetRefusal("history_free_headroom")
    return HISTORY_STORE_BYTES


class HistoryMemoryStore(MemoryStore):
    def _write_budget(self):
        return admit_history_write(self.directory)


def capacity_policy_version(job):
    value = job.get("capacity_policy", 1)
    if type(value) is not int or value not in (1, CAPACITY_POLICY):
        raise _Unavailable("unsupported history capacity policy")
    return value


def refresh_capacity_policy(job):
    """Reconsider obsolete disk refusals once; never reset native failures."""
    if capacity_policy_version(job) == CAPACITY_POLICY:
        return False
    job["capacity_policy"] = CAPACITY_POLICY
    job.pop("capacity_cursor_key", None)
    job.pop("capacity_rejected", None)
    if job.get("reason") in {"output_capacity", "row_output_capacity"}:
        job.pop("reason", None)
        job["state"] = "indexing"
    if job.get("partial_row", {}).get("state") == "awaiting_capacity":
        job.pop("partial_row")
    return True
