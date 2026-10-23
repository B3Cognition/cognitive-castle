import io
import json

from cognitive_castle.memory_types import ProviderHealth
from cognitive_castle.provider_worker import serve


class Service:
    def health(self):
        return ProviderHealth("ready", fingerprint="test")

    def search(self, query, *, limit=5):
        raise RuntimeError("private path and source contents must never escape")


def test_worker_closed_errors_and_orderly_close():
    messages = [
        {"version": 1, "id": str(i), "op": op, "args": args}
        for i, (op, args) in enumerate(
            [("hello", {}), ("search", {"query": "find"}), ("close", {})]
        )
    ]
    source = io.BytesIO(b"".join(json.dumps(m).encode() + b"\n" for m in messages))
    output = io.BytesIO()
    serve(Service(), source, output)
    replies = [json.loads(line) for line in output.getvalue().splitlines()]
    assert replies[0]["result"]["profile"] == "memory-fts-v1"
    assert replies[1]["error"] == {"code": "unavailable"}
    assert replies[2]["ok"] is True
    assert b"private" not in output.getvalue()


def test_oversized_input_is_read_boundedly_and_terminates():
    from cognitive_castle.provider_protocol import MAX_FRAME_BYTES

    source, output = io.BytesIO(b"x" * (MAX_FRAME_BYTES * 2)), io.BytesIO()
    serve(Service(), source, output)
    assert source.tell() == MAX_FRAME_BYTES + 1
    assert json.loads(output.getvalue())["error"]["code"] == "invalid_request"
