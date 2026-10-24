"""Explicit, source-retaining copies of selected legacy auxiliary state.

This operator action never discovers or merges sibling data. Publication of
the path manifest is last, after independent copy verification and evidence.
"""

from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from .palace import mutation_session
from .revisions import atomic_json


def _sha256(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _read_sqlite(path):
    return sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True, timeout=10)


def _graph_summary(conn):
    """Hash schema and every ordinary table row within the current snapshot."""
    schema = conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    tables = [row[1] for row in schema if row[0] == "table"]
    if not {"entities", "triples"} <= set(tables):
        raise ValueError("selected graph does not have a compatible schema")
    hasher = hashlib.sha256(json.dumps(schema, ensure_ascii=False).encode())
    counts = {}
    for table in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        cursor = conn.execute(f"SELECT * FROM {quoted} LIMIT 0")
        columns = [column[0] for column in cursor.description]
        order = ", ".join('"' + name.replace('"', '""') + '"' for name in columns)
        counts[table] = 0
        for row in conn.execute(f"SELECT * FROM {quoted} ORDER BY {order}"):
            # Preserve SQLite value types, including any future BLOB columns.
            values = [
                {"blob_hex": value.hex()} if isinstance(value, bytes) else value for value in row
            ]
            hasher.update(json.dumps([table, values], ensure_ascii=False, allow_nan=False).encode())
            hasher.update(b"\n")
            counts[table] += 1
    return {"logical_sha256": hasher.hexdigest(), "counts": counts}


def _backup_graph(source, destination):
    with closing(_read_sqlite(source)) as original:
        # Pin the same committed view for source verification and backup. A
        # live source's WAL is part of this snapshot; immutable reads are wrong.
        original.execute("BEGIN")
        summary = _graph_summary(original)
        with closing(sqlite3.connect(destination)) as copy:
            original.backup(copy)
            copy.execute("PRAGMA journal_mode=DELETE")
    with closing(_read_sqlite(destination)) as verified:
        if _graph_summary(verified) != summary:
            raise OSError("graph copy verification failed")
        if verified.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise OSError("graph copy integrity verification failed")
    destination.chmod(0o600)
    return summary


def _registry_summary(raw):
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError()
        people, projects = value.get("people", {}), value.get("projects", [])
        if not isinstance(people, dict) or any(
            not isinstance(info, dict) for info in people.values()
        ):
            raise ValueError()
        if not isinstance(projects, list) or any(not isinstance(name, str) for name in projects):
            raise ValueError()
    except (ValueError, UnicodeError, TypeError):
        raise ValueError("selected registry does not have a compatible JSON schema") from None
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "people_count": len(people),
        "project_count": len(projects),
    }


def _check_json_target(path, expected):
    if not path.exists():
        return
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise FileExistsError("existing migration state differs") from None
    if existing != expected:
        raise FileExistsError("existing migration state differs")


def migrate_auxiliary_state(palace_path, *, legacy_graph=None, legacy_registry=None) -> dict:
    """Copy only selected state, retaining originals and all existing targets.

    Exact retries are accepted. A different existing target, evidence record,
    or path manifest is never overwritten. Preparation remains a separate
    operator action; this helper does not stamp embedder/provider identity.
    """
    if legacy_graph is None and legacy_registry is None:
        raise ValueError("select at least one legacy auxiliary source")
    root = Path(palace_path).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError("palace root is not a directory")
    sources = {}
    for name, source in (("graph", legacy_graph), ("registry", legacy_registry)):
        if source is not None:
            selected = Path(source).expanduser().resolve(strict=True)
            if not selected.is_file():
                raise ValueError("selected auxiliary source is not a file")
            sources[name] = selected
    state = root / ".castle"
    if not state.resolve().is_relative_to(root):
        raise ValueError("private migration state escapes palace root")
    names = {"graph": "knowledge_graph.sqlite3", "registry": "entity_registry.json"}
    targets = {name: state / filename for name, filename in names.items()}
    manifest_path, evidence_path = state / "paths.json", state / "auxiliary-migration.json"
    for path in (*targets.values(), manifest_path, evidence_path):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("migration target must be a private palace file")
    manifest = {
        "version": 1,
        "knowledge_graph": ".castle/knowledge_graph.sqlite3",
        "entity_registry": ".castle/entity_registry.json",
    }
    with mutation_session(root):
        # Selecting one component does not authorize rebinding the other.
        # Preserve its unambiguous in-palace location; shared sibling files
        # are deliberately excluded because they were not selected for copy.
        for name, filename in names.items():
            if name in sources:
                continue
            candidates = {
                candidate.resolve()
                for candidate in (targets[name], root / filename)
                if candidate.exists() or candidate.is_symlink()
            }
            if any(not path.is_relative_to(root) or not path.is_file() for path in candidates):
                raise ValueError("unselected auxiliary binding is not a private palace file")
            if len(candidates) > 1:
                raise ValueError("ambiguous unselected auxiliary binding; select it explicitly")
            if candidates:
                key = "knowledge_graph" if name == "graph" else "entity_registry"
                manifest[key] = str(next(iter(candidates)).relative_to(root))
        _check_json_target(manifest_path, manifest)
        state.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".auxiliary-migration-", dir=state) as temporary:
            stage = Path(temporary)
            evidence = {"schema_version": 1, "operation": "auxiliary-state-copy"}
            for name, source in sources.items():
                staged = stage / names[name]
                if name == "graph":
                    summary = _backup_graph(source, staged)
                else:
                    raw = source.read_bytes()
                    summary = _registry_summary(raw)
                    staged.write_bytes(raw)
                    staged.chmod(0o600)
                    if _sha256(staged) != summary["sha256"]:
                        raise OSError("registry copy verification failed")
                target = targets[name]
                if target.exists():
                    if name == "graph":
                        with closing(_read_sqlite(target)) as current:
                            equal = _graph_summary(current) == summary
                    else:
                        equal = _sha256(target) == summary["sha256"]
                    if not equal:
                        raise FileExistsError("existing auxiliary target differs")
                evidence[name] = {
                    "source": str(source),
                    "target": str(target.relative_to(root)),
                    **summary,
                    "sha256": _sha256(target if target.exists() else staged),
                }
            evidence["checksum"] = hashlib.sha256(
                json.dumps(evidence, sort_keys=True).encode()
            ).hexdigest()
            _check_json_target(evidence_path, evidence)
            # A hard link publishes each complete staged file atomically and
            # refuses overwrite even if an unsupported external writer races.
            for name in sources:
                if not targets[name].exists():
                    os.link(stage / names[name], targets[name])
            if not evidence_path.exists():
                atomic_json(evidence_path, evidence)
            if not manifest_path.exists():
                atomic_json(manifest_path, manifest)
            return evidence
