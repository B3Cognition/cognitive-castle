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


def test_pipe_frames_preserve_following_partial_frame_deadline():
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b"{}\n{")
        with os.fdopen(read_fd, "rb", buffering=0) as stream:
            reader = FrameReader(stream, deadline=0.03)
            assert reader.read() == b"{}"
            with pytest.raises(FrameError, match="deadline"):
                reader.read()
    finally:
        os.close(write_fd)


def test_windows_partial_deadline_leaves_no_background_reader(monkeypatch):
    """A timed-out connection must be closable while its peer still owns the writer."""
    import select
    import threading
    from types import SimpleNamespace
    from cognitive_castle import bounded_json

    real_os = bounded_json.os
    monkeypatch.setattr(bounded_json, "os", SimpleNamespace(**(vars(real_os) | {"name": "nt"})))

    def pipe_chunk(fd, maximum):
        # Substitute only the Windows API boundary; bytes come from a real pipe.
        if not select.select([fd], [], [], 0)[0]:
            return None
        return real_os.read(fd, maximum)

    if real_os.name != "nt":
        monkeypatch.setattr(bounded_json, "_windows_pipe_chunk", pipe_chunk)
    before = set(threading.enumerate())
    read_fd, write_fd = real_os.pipe()
    stream = real_os.fdopen(read_fd, "rb", buffering=0)
    try:
        real_os.write(write_fd, b"{")
        with pytest.raises(FrameError, match="deadline"):
            FrameReader(stream, deadline=0.03).read()
        assert not [t for t in threading.enumerate() if t not in before], (
            "deadline left a reader blocked on a peer-owned pipe"
        )
    finally:
        # This cleanup also unblocks the old implementation after a RED failure.
        real_os.close(write_fd)
        stream.close()


@pytest.mark.parametrize("contents, expected", [(b"{}\n", b"{}"), (b"", None)])
def test_native_pipe_closed_peer_returns_frame_then_eof(contents, expected):
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, contents)
    finally:
        os.close(write_fd)
    with os.fdopen(read_fd, "rb", buffering=0) as stream:
        reader = FrameReader(stream)
        assert reader.read() == expected
        assert reader.read() is None


def test_native_pipe_oversized_frame_stops_while_writer_remains_open():
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b"12345\n")
        with os.fdopen(read_fd, "rb", buffering=0) as stream:
            reader = FrameReader(stream, max_bytes=4)
            with pytest.raises(FrameError, match="byte limit"):
                reader.read()
            with pytest.raises(FrameError, match="already closed"):
                reader.read()
    finally:
        os.close(write_fd)


def test_windows_character_input_is_explicitly_unavailable(monkeypatch):
    from types import SimpleNamespace
    from cognitive_castle import bounded_json

    monkeypatch.setattr(bounded_json, "os", SimpleNamespace(**(vars(os) | {"name": "nt"})))
    with open(os.devnull, "rb", buffering=0) as stream:
        with pytest.raises(FrameError, match="expected pipe or regular file"):
            FrameReader(stream).read()
