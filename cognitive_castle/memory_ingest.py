"""Bounded original JSONL ingestion; roles are attribution, never authorization."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import time

MAX_RECORD_BYTES = 1024 * 1024
MAX_SLICE_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 128


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def extract_messages(record: dict, format: str) -> list[dict]:
    """Keep individual decoded text fields exact, excluding internal/tool blocks."""
    if format not in ("codex", "claude"):
        raise ValueError("unsupported transcript format")
    if not isinstance(record, dict):
        return []
    kind = record.get("type")
    if format == "codex":
        message = record.get("payload")
        if kind != "response_item" or not isinstance(message, dict):
            return []
        if message.get("type") != "message":
            return []
        role = message.get("role")
        if role not in ("user", "assistant"):
            return []
        if role == "assistant" and message.get("channel") not in (None, "final", "commentary"):
            return []
        accepted = ("input_text", "output_text", "text")
    else:
        role = kind
        message = record.get("message")
        if role not in ("user", "human", "assistant") or not isinstance(message, dict):
            return []
        if role == "assistant" and message.get("channel", record.get("channel")) not in (
            None,
            "final",
            "commentary",
        ):
            return []
        accepted = ("text",)
    content = message.get("content")
    if isinstance(content, str) and format == "claude":
        return (
            [{"text": content, "role": role, "kind": kind, "block": "content"}] if content else []
        )
    if not isinstance(content, list):
        return []
    return [
        {"text": block["text"], "role": role, "kind": kind, "block": index}
        for index, block in enumerate(content)
        if isinstance(block, dict)
        and block.get("type") in accepted
        and isinstance(block.get("text"), str)
        and block["text"]
    ]


def _open_source(path, root):
    path, root = Path(path).absolute(), Path(root).absolute()
    if not path.is_relative_to(root):
        raise ValueError("source outside registered root")
    for part in [path, *path.parents, root, *root.parents]:
        if part.is_symlink():
            raise ValueError("symlink source or ancestor")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):
        os.close(fd)
        raise ValueError("source must be regular file")
    return os.fdopen(fd, "rb"), info, path


def _anchor(source, offset):
    source.seek(0)
    first = source.read(min(offset, 4096))
    source.seek(max(0, offset - 4096))
    last = source.read(min(offset, 4096))
    return _hash(first + last)


def _pieces(text):
    start, size, pending = 0, 0, []
    for char in text:
        width = len(char.encode("utf-8"))
        if size + width > 65536:
            yield start, "".join(pending)
            start += len(pending)
            size, pending = 0, []
        pending.append(char)
        size += width
    if pending:
        yield start, "".join(pending)


def ingest_slice(store, path: Path, *, allowed_root: Path, format: str) -> dict:
    """Read one bounded slice. Caller must obtain allowed_root from trusted registry.

    Anchors detect some edits but cannot establish unchanged historical prefixes.
    Append checkpoints describe indexed prefixes, never exhaustive archive coverage.
    """
    if format not in ("codex", "claude"):
        raise ValueError("unsupported transcript format")
    deadline = time.monotonic() + 0.250
    source, info, path = _open_source(path, allowed_root)
    with source:
        key = _hash((str(path) + "\0" + format).encode())
        old = store.load_checkpoint(key)
        identity = [
            info.st_dev,
            info.st_ino,
            info.st_birthtime_ns if hasattr(info, "st_birthtime_ns") else 0,
        ]
        generation = 0 if old is None else old["generation"]
        offset = 0 if old is None else old["offset"]
        if old and (
            old["identity"] != identity
            or info.st_size < offset
            or _anchor(source, offset) != old["anchor"]
        ):
            generation += 1
            old, offset = None, 0
        checkpoint = dict(
            old
            or {
                "generation": generation,
                "offset": 0,
                "identity": identity,
                "gaps": 0,
                "unsupported": 0,
                "skipping": False,
            }
        )
        source.seek(offset)
        consumed = records = 0
        coverage = "indexed_prefix"
        while consumed < MAX_SLICE_BYTES and records < MAX_RECORDS and time.monotonic() < deadline:
            start = source.tell()
            raw = source.readline(min(MAX_RECORD_BYTES + 1, MAX_SLICE_BYTES - consumed))
            consumed += len(raw)
            if not raw:
                break
            terminated = raw.endswith(b"\n")
            if checkpoint["skipping"] or len(raw) > MAX_RECORD_BYTES:
                if not checkpoint["skipping"]:
                    checkpoint["gaps"] += 1
                checkpoint["skipping"] = not terminated
                checkpoint["offset"] = source.tell()
            elif not terminated:
                # A budget-limited read must not be mislabelled an oversized record.
                coverage = "pending_tail" if source.tell() >= info.st_size else "partial"
                break
            else:
                records += 1
                try:
                    record = json.loads(raw)
                    messages = extract_messages(record, format)
                    for block in messages:
                        block_hash = _hash(block["text"].encode())
                        for piece_start, piece in _pieces(block["text"]):
                            provenance = {
                                "source": key,
                                "generation": generation,
                                "record_start": start,
                                "record_end": source.tell(),
                                "record_hash": _hash(raw),
                                "role": block["role"],
                                "kind": block["kind"],
                                "block": block["block"],
                                "block_hash": block_hash,
                                "block_start": piece_start,
                                "block_end": piece_start + len(piece),
                            }
                            request = _hash(
                                f"{key}:{generation}:{start}:{_hash(raw)}:{block['block']}:{piece_start}".encode()
                            )
                            receipt = store.remember(
                                request, piece, provenance, namespace="transcript"
                            )
                            if receipt.get("status") != "ok":
                                return {
                                    "status": receipt.get("status", "unavailable"),
                                    "coverage": "partial",
                                    "source_key": key,
                                }
                    if not messages:
                        checkpoint["unsupported"] += 1
                except (UnicodeError, json.JSONDecodeError, RecursionError):
                    checkpoint["gaps"] += 1
                checkpoint["offset"] = source.tell()
            checkpoint["anchor"] = _anchor(source, checkpoint["offset"])
            store.save_checkpoint(key, checkpoint)
            source.seek(checkpoint["offset"])
        if (
            checkpoint["gaps"]
            or checkpoint["unsupported"]
            or checkpoint["skipping"]
            or checkpoint["offset"] < info.st_size
            and coverage != "pending_tail"
        ):
            coverage = "partial"
        return {
            "status": "ok",
            "source_key": key,
            "offset": checkpoint["offset"],
            "generation": generation,
            "records": records,
            "gaps": checkpoint["gaps"],
            "coverage": coverage,
            "representation": format + ("_response_item" if format == "codex" else "_text"),
            "currentness": "anchor_checked_only",
        }
