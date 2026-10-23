"""Boundary regressions use tiny synthetic frames, never model or palace data."""

import io
import os

import pytest

from cognitive_castle.bounded_json import FrameReader, FrameError, strict_loads, encode_response


def test_duplicate_keys_nonfinite_and_surrogate_are_rejected():
    for text in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}', '"\\ud800"']:
        with pytest.raises(ValueError):
            strict_loads(text)


def test_depth_and_bytes_are_checked_even_for_unknown_fields():
    with pytest.raises(ValueError):
        strict_loads("[" * 33 + "0" + "]" * 33)
    with pytest.raises(ValueError):
        strict_loads('{"unknown":"' + "é" * 20 + '"}', max_bytes=32)
    assert strict_loads('{"text":"[[[\\""}') == {"text": '[[["'}


def test_frames_do_not_execute_oversized_tail_as_another_request():
    reader = FrameReader(io.BytesIO(b"123456789\n{}\n"), max_bytes=8)
    with pytest.raises(FrameError):
        reader.read()
    with pytest.raises(FrameError):
        reader.read()


def test_complete_frames_and_eof():
    reader = FrameReader(io.BytesIO(b'{}\n{"x":1}\n'))
    assert reader.read() == b"{}"
    assert reader.read() == b'{"x":1}'
    assert reader.read() is None


def test_partial_frame_has_receive_deadline():
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b"{")
        with os.fdopen(read_fd, "rb", buffering=0) as stream:
            with pytest.raises(FrameError, match="deadline"):
                FrameReader(stream, deadline=0.03).read()
    finally:
        os.close(write_fd)


def test_actual_encoded_envelope_is_bounded():
    reply = {"id": 1, "result": {"content": [{"type": "text", "text": '\\"' * 20000}]}}
    raw = encode_response(reply)
    assert len(raw) <= 32768
    assert strict_loads(raw)["error"]["code"] == -32001


def test_bounded_syntax_error_does_not_corrupt_next_frame():
    reader = FrameReader(io.BytesIO(b'{broken}\n{"ok":true}\n'))
    with pytest.raises(ValueError):
        strict_loads(reader.read())
    assert strict_loads(reader.read()) == {"ok": True}


def test_threaded_pipe_fallback_has_the_same_deadline_and_frame_bounds():
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b"{}\n{")
        with os.fdopen(read_fd, "rb", buffering=0) as stream:
            reader = FrameReader(stream, deadline=0.03, threaded=True)
            assert reader.read() == b"{}"
            with pytest.raises(FrameError, match="deadline"):
                reader.read()
    finally:
        os.close(write_fd)
