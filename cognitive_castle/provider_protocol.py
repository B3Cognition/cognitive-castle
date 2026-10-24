"""Strict bounded JSON framing shared by the private worker and its tests."""

import json

from .memory_types import MemoryError

MAX_FRAME_BYTES = 1048576
OPERATIONS = {
    "hello": (set(), set()),
    "health": (set(), set()),
    "close": (set(), set()),
    "search": ({"query"}, {"query", "limit"}),
    "fetch": ({"record_id"}, {"record_id", "start_char", "max_chars"}),
    "snapshot": ({"record_ids"}, {"record_ids", "expected", "maximum_bytes"}),
}


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate key")
        value[key] = item
    return value


def decode_request(frame):
    try:
        if len(frame) > MAX_FRAME_BYTES or not frame.endswith(b"\n"):
            raise ValueError()
        value = json.loads(
            frame,
            object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
        if not isinstance(value, dict) or set(value) != {"version", "id", "op", "args"}:
            raise ValueError()
        if type(value["version"]) is not int or value["version"] != 1:
            raise ValueError()
        if not isinstance(value["id"], str) or not value["id"] or len(value["id"].encode()) > 128:
            raise ValueError()
        op, args = value["op"], value["args"]
        if not isinstance(op, str) or op not in OPERATIONS or not isinstance(args, dict):
            raise ValueError()
        required, allowed = OPERATIONS[op]
        if not required <= set(args) <= allowed:
            raise ValueError()
        return value
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise MemoryError("invalid_request") from None


def response(request_id, *, result=None, error=None):
    value = {"version": 1, "id": request_id, "ok": error is None}
    value.update({"result": result} if error is None else {"error": {"code": error}})
    frame = (
        json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
        + b"\n"
    )
    if len(frame) > MAX_FRAME_BYTES:
        return response(request_id, error="result_limit")
    return frame
