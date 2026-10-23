import json
import pytest
from cognitive_castle.provider_protocol import decode_request, MAX_FRAME_BYTES
from cognitive_castle.memory_types import MemoryError


@pytest.mark.parametrize(
    "frame",
    [
        b"[]\n",
        b'{"version":1,"version":1}\n',
        b"NaN\n",
        b"x" * (MAX_FRAME_BYTES + 1),
        b"{}",
        b'{"version":true,"id":"a","op":"hello","args":{}}\n',
    ],
)
def test_invalid_frames_are_closed_errors(frame):
    with pytest.raises(MemoryError, match="invalid_request"):
        decode_request(frame)


def test_unknown_grants_rejected_before_dispatch():
    for args in (
        {"query": "ok", "namespace": "other"},
        {"query": "ok", "palace_path": "/tmp"},
        {"query": "ok", "recency_boost": True},
        {"query": "ok", "profile": "memory-v1"},
    ):
        with pytest.raises(MemoryError):
            decode_request(
                json.dumps({"version": 1, "id": "a", "op": "search", "args": args}).encode() + b"\n"
            )
