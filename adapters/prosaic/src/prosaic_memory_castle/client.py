"""Scoped source-preserving client; no model installation or Castle imports."""

import json
import re

from .transport import MemoryProviderError, WorkerTransport


class CastleMemoryProvider:
    def __init__(
        self,
        command,
        *,
        palace_path,
        namespace,
        config_path,
        allowed_wings,
        profile="memory-fts-v1",
        startup_timeout=120,
        operation_timeout=30,
    ):
        self._transport = WorkerTransport(
            command,
            palace_path=palace_path,
            namespace=namespace,
            config_path=config_path,
            allowed_wings=allowed_wings,
            profile=profile,
            startup_timeout=startup_timeout,
            operation_timeout=operation_timeout,
        )

    def _read(self, op, args, context):
        result = self._transport.request(op, args, context=context)
        if (
            op in {"search", "fetch"}
            and len(
                json.dumps(
                    result, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                ).encode("utf-8")
            )
            > 49152
        ):
            raise MemoryProviderError("result_limit")
        return result

    def health(self, *, _context=None):
        return self._read("health", {}, _context)

    def search(self, query, limit=5, *, _context=None):
        if (
            type(query) is not str
            or not query.strip()
            or len(query.encode("utf-8")) > 4096
            or type(limit) is not int
            or not 1 <= limit <= 20
        ):
            raise MemoryProviderError("invalid_request")
        return self._read("search", {"query": query, "limit": limit}, _context)

    def fetch(self, record_id, start_char=0, max_chars=8000, *, _context=None):
        if (
            type(record_id) is not str
            or not record_id
            or len(record_id.encode("utf-8")) > 512
            or type(start_char) is not int
            or start_char < 0
            or type(max_chars) is not int
            or not 1 <= max_chars <= 8000
        ):
            raise MemoryProviderError("invalid_request")
        return self._read(
            "fetch",
            {"record_id": record_id, "start_char": start_char, "max_chars": max_chars},
            _context,
        )

    def snapshot(self, record_ids, *, expected=None, maximum_bytes=262144, _context=None):
        if (
            type(record_ids) not in (list, tuple)
            or not record_ids
            or len(record_ids) > 128
            or any(
                type(item) is not str or not item or len(item.encode("utf-8")) > 512
                for item in record_ids
            )
            or len(set(record_ids)) != len(record_ids)
            or type(maximum_bytes) is not int
            or not 1 <= maximum_bytes <= 1048576
        ):
            raise MemoryProviderError("invalid_request")
        if expected is not None and (
            type(expected) is not dict or set(expected) != set(record_ids)
        ):
            raise MemoryProviderError("invalid_request")
        if expected is not None:
            for value in expected.values():
                if (
                    type(value) is not dict
                    or set(value) != {"text_sha256", "revision"}
                    or type(value["text_sha256"]) is not str
                    or re.fullmatch(r"[0-9a-f]{64}", value["text_sha256"]) is None
                    or (
                        value["revision"] is not None
                        and (
                            type(value["revision"]) is not str
                            or len(value["revision"].encode("utf-8")) > 256
                            or re.fullmatch(r"[A-Za-z0-9_.-]+", value["revision"]) is None
                        )
                    )
                ):
                    raise MemoryProviderError("invalid_request")
        args = {"record_ids": list(record_ids), "maximum_bytes": maximum_bytes}
        if expected is not None:
            args["expected"] = expected
        result = self._read("snapshot", args, _context)
        if (
            len(
                json.dumps(
                    result, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                ).encode("utf-8")
            )
            > maximum_bytes
        ):
            raise MemoryProviderError("result_limit")
        return result

    def close(self):
        self._transport.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
