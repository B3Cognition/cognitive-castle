"""Native worker for explicitly bounded immutable Lance snapshots.

Supported ``castle_brain_format=fixed-v1`` Arrow schema: id:int64;
text:fixed_size_binary(1..65536); metadata_json:fixed_size_binary(1..8192);
text_bytes:int32; metadata_bytes:int32; text_sha256:fixed_size_binary(32).
Lengths select the exact UTF-8 prefix (including any original trailing NULs).
Recall additionally needs search_text:utf8 with an existing native FTS index.
Extra fields (including supplied vectors) are never projected. Fixed widths,
not caller size claims or SQL length expressions, prove payload decoder bounds.
This module does not create or upgrade this format in any archive.
"""

from __future__ import annotations

import hashlib
import importlib.abc
import json
import os
from pathlib import Path
import socket
import stat
import sys

MAX_FILES = 512
MAX_SNAPSHOT = 64 * 1024**2
MAX_TEXT = 64 * 1024
MAX_PROVENANCE = 8 * 1024
ADMISSION_COLUMNS = ["id", "text_bytes", "metadata_bytes", "text_sha256"]


class Unavailable(Exception):
    pass


def _inventory(root):
    found = {}
    directories = [root]
    visited = 0
    while directories:
        directory = directories.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                visited += 1
                if visited > MAX_FILES:
                    raise Unavailable("snapshot_file_limit")
                st = entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(st.st_mode):
                    raise Unavailable("unsafe_source_path")
                if stat.S_ISDIR(st.st_mode):
                    directories.append(Path(entry.path))
                elif stat.S_ISREG(st.st_mode):
                    relative = str(Path(entry.path).relative_to(root))
                    found[relative] = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
                else:
                    raise Unavailable("unsafe_source_path")
    if sum(item[2] for item in found.values()) > MAX_SNAPSHOT:
        raise Unavailable("snapshot_byte_limit")
    return found


def _snapshot(palace_path, destination):
    source = Path(palace_path) / "lancedb" / "castle_drawers.lance"
    if not source.is_dir():
        raise Unavailable("source_unavailable")
    if source.resolve() != source:
        raise Unavailable("unsafe_source_path")
    inventory = _inventory(source)
    if not inventory or not any(name.startswith("_versions/") for name in inventory):
        raise Unavailable("table_version_unavailable")
    target = Path(destination) / "castle_drawers.lance"
    target.mkdir()
    digest = hashlib.sha256()
    for name, identity in sorted(inventory.items()):
        output = target / name
        output.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(source / name, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            st = os.fstat(fd)
            if (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns) != identity:
                raise Unavailable("source_changed")
            file_hash = hashlib.sha256()
            remaining = identity[2]
            with output.open("xb") as out:
                while remaining:
                    chunk = os.read(fd, min(65536, remaining))
                    if not chunk:
                        raise Unavailable("source_changed")
                    out.write(chunk)
                    file_hash.update(chunk)
                    remaining -= len(chunk)
                if os.read(fd, 1):
                    raise Unavailable("source_changed")
            st = os.fstat(fd)
            if (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns) != identity:
                raise Unavailable("source_changed")
            digest.update(name.encode() + b"\0" + file_hash.digest())
        finally:
            os.close(fd)
    if _inventory(source) != inventory:
        raise Unavailable("source_changed")
    return digest.hexdigest()


def _bounded_schema(schema):
    import pyarrow as pa

    if (schema.metadata or {}).get(b"castle_brain_format") != b"fixed-v1":
        raise Unavailable("legacy_size_unprovable")
    try:
        text_type = schema.field("text").type
        metadata_type = schema.field("metadata_json").type
        valid = (
            pa.types.is_fixed_size_binary(text_type)
            and 0 < text_type.byte_width <= MAX_TEXT
            and pa.types.is_fixed_size_binary(metadata_type)
            and 0 < metadata_type.byte_width <= MAX_PROVENANCE
            and schema.field("id").type == pa.int64()
            and schema.field("text_bytes").type == pa.int32()
            and schema.field("metadata_bytes").type == pa.int32()
            and schema.field("text_sha256").type == pa.binary(32)
        )
    except (KeyError, AttributeError):
        valid = False
    if not valid:
        raise Unavailable("bounded_schema_unsupported")
    return text_type.byte_width, metadata_type.byte_width


def _metadata(raw):
    # Bound depth before JSON decoding (including braces inside strings).
    depth = 0
    quoted = escaped = False
    for character in raw:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "{[":
            depth += 1
            if depth > 32:
                raise Unavailable("source_metadata_invalid")
        elif character in "}]":
            depth -= 1

    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate metadata key")
            value[key] = item
        return value

    def nonfinite(value):
        raise ValueError("nonfinite metadata")

    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
        if not isinstance(value, dict):
            raise ValueError("metadata must be an object")
        # Reject escaped lone surrogates before exposing source metadata.
        json.dumps(value, ensure_ascii=False).encode("utf-8")
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise Unavailable("source_metadata_invalid") from exc


def _read_table(table, request, snapshot_hash):
    """Project bounded candidate fields before touching payload buffers."""
    widths = _bounded_schema(table.schema)
    version = table.version
    table.checkout(version)
    if request["operation"] == "recall":
        indices = list(table.list_indices())
        if not any(
            "search_text" in index.columns and str(index.index_type).lower() in {"fts", "inverted"}
            for index in indices
        ):
            raise Unavailable("fts_index_missing")
        candidate_query = table.search(
            request["query"], query_type="fts", fts_columns="search_text"
        ).limit(request["limit"])
    else:
        ids = request["ids"]
        if any(
            not value.isascii()
            or not value.isdecimal()
            or len(value) > 19
            or int(value) > 2**63 - 1
            or str(int(value)) != value
            for value in ids
        ):
            raise Unavailable("source_unavailable")
        candidate_query = table.search().where("id IN (" + ",".join(ids) + ")").limit(9)
    candidates = candidate_query.select(ADMISSION_COLUMNS).to_list()
    if len(candidates) > 8:
        raise Unavailable("source_count_limit")
    if request["operation"] == "read" and {str(row["id"]) for row in candidates} != set(
        request["ids"]
    ):
        raise Unavailable("source_unavailable")
    if len({row["id"] for row in candidates}) != len(candidates):
        raise Unavailable("source_identity_ambiguous")
    for row in candidates:
        if (
            type(row["text_bytes"]) is not int
            or type(row["metadata_bytes"]) is not int
            or not 0 <= row["text_bytes"] <= widths[0]
            or not 0 <= row["metadata_bytes"] <= widths[1]
            or not isinstance(row["text_sha256"], bytes)
            or len(row["text_sha256"]) != 32
        ):
            raise Unavailable("source_size_invalid")
    if sum(row["text_bytes"] for row in candidates) > MAX_TEXT:
        raise Unavailable("text_byte_limit")
    if sum(row["metadata_bytes"] for row in candidates) > MAX_PROVENANCE:
        raise Unavailable("provenance_byte_limit")
    if table.version != version:
        raise Unavailable("source_changed")
    sources = []
    provenance_bytes = 0
    for admitted in candidates:
        rows = (
            table.search()
            .where(f"id = {admitted['id']}")
            .limit(2)
            .select(ADMISSION_COLUMNS + ["text", "metadata_json"])
            .to_list()
        )
        if len(rows) != 1 or any(rows[0][key] != admitted[key] for key in ADMISSION_COLUMNS):
            raise Unavailable("source_changed")
        row = rows[0]
        # Native decoding is bounded by fixed Arrow widths, regardless of lengths.
        text_bytes = row["text"][: row["text_bytes"]]
        metadata_bytes = row["metadata_json"][: row["metadata_bytes"]]
        if hashlib.sha256(text_bytes).digest() != row["text_sha256"]:
            raise Unavailable("source_hash_mismatch")
        try:
            text = text_bytes.decode("utf-8")
            metadata = _metadata(metadata_bytes.decode("utf-8"))
        except UnicodeError as exc:
            raise Unavailable("source_encoding_invalid") from exc
        provenance = {
            "origin": "archive",
            "local_only": True,
            "provenance_confidence": "backend_verified_snapshot",
            "table": "castle_drawers",
            "table_version": version,
            "snapshot_hash": snapshot_hash,
            "text_sha256": row["text_sha256"].hex(),
            "source_metadata": metadata,
        }
        provenance_bytes += len(json.dumps(provenance, ensure_ascii=False).encode())
        if provenance_bytes > MAX_PROVENANCE:
            raise Unavailable("provenance_byte_limit")
        sources.append({"id": str(row["id"]), "text": text, "provenance": provenance})
    if table.version != version:
        raise Unavailable("source_changed")
    return {
        "status": "ok",
        "sources": sources,
        "selection": {
            "method": "existing_fts" if request["operation"] == "recall" else "explicit_ids",
            "exhaustive": False,
            "table_version": version,
            "source_count": len(sources),
        },
        "limits": {"text_bytes": MAX_TEXT, "provenance_bytes": MAX_PROVENANCE},
    }


def read(request):
    temporary = request["snapshot_dir"]
    snapshot_hash = _snapshot(request["palace_path"], temporary)
    # Original storage is never passed to any native backend, including connect.
    import lancedb

    table = lancedb.connect(temporary).open_table("castle_drawers")
    return _read_table(table, request, snapshot_hash)


class _NoModels(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"torch", "transformers", "sentence_transformers", "spacy"}:
            raise ModuleNotFoundError("models are forbidden in the source reader")


def main():
    sys.meta_path.insert(0, _NoModels())

    def no_network(*args, **kwargs):
        raise OSError("network is forbidden in the source reader")

    socket.socket.connect = no_network
    socket.create_connection = no_network
    try:
        raw = sys.stdin.buffer.read(16385)
        if len(raw) > 16384:
            raise Unavailable("reader_input_limit")
        result = read(json.loads(raw))
    except Unavailable as exc:
        result = {"status": "unavailable", "reason": str(exc)}
    except Exception:
        # Never return native exceptions: they can include source text or paths.
        result = {"status": "unavailable", "reason": "native_read_failed"}
    sys.stdout.write(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
