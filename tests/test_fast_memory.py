import json
import os
import sqlite3

import pytest

from cognitive_castle.fast_memory import MemoryStore

pytestmark = pytest.mark.skipif(os.name != "posix", reason="private POSIX persistence")


def test_exact_restart_and_receipts(tmp_path):
    store = MemoryStore(tmp_path / "memory")
    text = " \t\r\nž😀\n" * 1600
    result = store.remember("req", text, {"role": "user"})
    assert result["status"] == "ok"
    ids = result["ids"]
    sources = MemoryStore(store.directory).read_sources(ids)["sources"]
    assert "".join(s["text"] for s in sources) == text
    assert all(len(s["text"].encode()) <= 8192 for s in sources)
    assert all(s["origin"] == "archive" and s["local_only"] for s in sources)
    assert store.remember("req", text, {"role": "user"})["ids"] == ids
    assert store.remember("req", text + "x")["status"] == "conflict"
    other = store.remember("changed-revision", text)["ids"]
    assert other != ids


def test_reads_and_validation_do_not_create(tmp_path):
    store = MemoryStore(tmp_path / "missing")
    assert store.status()["status"] == "unavailable"
    assert store.recall("hello")["status"] == "unavailable"
    assert not store.directory.exists()
    for fn in [
        lambda: store.remember("x", "x" * 65537),
        lambda: store.recall("x " * 17),
        lambda: store.page("memory:x", limit=2049),
        lambda: store.read_sources(["memory:x"] * 9),
        lambda: store.remember("x", "ok", {"x": "a" * 513}),
    ]:
        with pytest.raises(ValueError):
            fn()
    assert not store.directory.exists()


def test_literal_recall_and_bounded_page(tmp_path):
    store = MemoryStore(tmp_path / "memory")
    ids = store.remember("a", "alpha " + "😀" * 3000)["ids"]
    store.remember("b", "beta")
    result = store.recall("alpha OR beta")
    assert result["sources"] == []
    result = store.recall("alpha")
    assert len(json.dumps(result, ensure_ascii=False).encode()) <= 8192
    source = store.read_sources([ids[0]])["sources"][0]
    page = store.page(ids[0], limit=2048, expected_hash=source["text_hash"])
    assert page["text"] == source["text"][:2048]
    assert store.page(ids[0], expected_hash="wrong")["status"] == "stale"
    assert len(json.dumps(page, ensure_ascii=False).encode()) <= 32768


def test_private_files_and_symlinks(tmp_path):
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    assert MemoryStore(link).remember("a", "secret")["status"] == "unavailable"
    store = MemoryStore(target)
    assert store.remember("a", "secret")["status"] == "ok"
    assert all(p.stat().st_mode & 0o077 == 0 for p in target.iterdir())
    store.db_path.chmod(0o644)
    assert store.recall("secret")["status"] == "unavailable"


def test_checkpoint_restart_and_corruption(tmp_path):
    store = MemoryStore(tmp_path / "memory")
    assert store.load_checkpoint("source") is None
    store.save_checkpoint("source", {"offset": 42, "tail": "ž"})
    assert MemoryStore(store.directory).load_checkpoint("source") == {"offset": 42, "tail": "ž"}
    for checkpoint in [{"x": "x" * 8192}, {"x": float("nan")}, {"x": object()}]:
        with pytest.raises(ValueError):
            store.save_checkpoint("source", checkpoint)
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("UPDATE checkpoints SET value='not-json'")
    with pytest.raises(ValueError):
        store.load_checkpoint("source")


def test_busy_and_quota_preserve_commits(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / "memory")
    ids = store.remember("a", "first")["ids"]
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        assert store.remember("b", "second")["status"] == "busy"
    monkeypatch.setattr("cognitive_castle.fast_memory.MAX_STORE_BYTES", 1)
    assert store.remember("c", "third")["status"] == "quota"
    assert store.read_sources(ids)["sources"][0]["text"] == "first"


def test_checkpoint_rejects_non_json_keys(tmp_path):
    store = MemoryStore(tmp_path / "memory")
    with pytest.raises(ValueError):
        store.save_checkpoint("source", {1: "silently coerced"})
    assert not store.directory.exists()


def test_exact_chunk_boundary_and_corrupt_database(tmp_path):
    store = MemoryStore(tmp_path / "memory")
    text = "x" * 8191 + "😀" + "\r\n"
    ids = store.remember("boundary", text)["ids"]
    sources = store.read_sources(ids)["sources"]
    assert [s["text"] for s in sources] == ["x" * 8191, "😀\r\n"]
    assert [s["chunk_start"] for s in sources] == [0, 8191]
    store.db_path.write_bytes(b"invalid SQLite")
    assert store.status()["status"] == "corrupt"


def test_database_symlink_and_unsupported_privacy(tmp_path, monkeypatch):
    directory = tmp_path / "memory"
    directory.mkdir(mode=0o700)
    target = tmp_path / "target"
    target.write_text("secret")
    (directory / "memory.sqlite3").symlink_to(target)
    assert MemoryStore(directory).remember("a", "hello")["status"] == "unavailable"
    fresh = MemoryStore(tmp_path / "fresh")
    monkeypatch.delattr(os, "O_NOFOLLOW")
    assert fresh.remember("a", "hello")["status"] == "unavailable"
    assert not fresh.directory.exists()


def test_receipt_snapshot_and_namespace(tmp_path):
    import hashlib

    store = MemoryStore(tmp_path / "memory")
    text = "ž😀\r\n"
    first = store.remember("request", text)
    assert first["stored_text_bytes"] == len(text.encode())
    assert first["text_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert store.remember("request", text) == first
    assert store.remember("request", text, namespace="other")["ids"] != first["ids"]
    assert store.remember("request", text, {"role": "changed"})["status"] == "conflict"


def test_sqlite_full_rolls_back_partial_write(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / "memory")
    first = store.remember("first", "original exact words")
    monkeypatch.setattr(
        "cognitive_castle.fast_memory.MAX_STORE_BYTES", store.db_path.stat().st_size + 4096
    )
    assert store.remember("large", "z" * 65536)["status"] == "quota"
    assert store.read_sources(first["ids"])["sources"][0]["text"] == "original exact words"
    assert store.status()["indexed_chunks"] == 1
