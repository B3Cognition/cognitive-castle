import json
import os
import sqlite3

import pytest

from cognitive_castle.fast_memory import MemoryStore, _Unavailable

persistence = pytest.mark.skipif(os.name != "posix", reason="private POSIX persistence")


@persistence
def test_exact_restart_and_receipts(tmp_path):
    store = MemoryStore(tmp_path / "memory")
    text = " \t\r\nž😀\n" * 1600
    result = store.remember("req", text, {"role": "user"})
    assert result["status"] == "ok"
    ids = result["ids"]
    sources = MemoryStore(store.directory).read_sources(ids)["sources"]
    assert "".join(s["text"] for s in sources) == text
    assert all(len(s["text"].encode()) <= 8192 for s in sources)
    assert all(
        s["provenance"]["origin"] == "archive" and s["provenance"]["local_only"] for s in sources
    )
    assert store.remember("req", text, {"role": "user"})["ids"] == ids
    assert store.remember("req", text + "x")["status"] == "conflict"
    other = store.remember("changed-revision", text)["ids"]
    assert other != ids


@persistence
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


@persistence
def test_literal_recall_and_bounded_page(tmp_path):
    store = MemoryStore(tmp_path / "memory")
    ids = store.remember("a", "alpha " + "😀" * 3000)["ids"]
    store.remember("b", "beta")
    result = store.recall("alpha OR beta")
    assert result["sources"] == []
    result = store.recall("alpha")
    assert len(json.dumps(result, ensure_ascii=False).encode()) <= 8192
    source = store.read_sources([ids[0]])["sources"][0]
    page = store.page(ids[0], limit=2048, expected_hash=source["provenance"]["text_hash"])
    assert page["text"] == source["text"][:2048]
    assert store.page(ids[0], expected_hash="wrong")["status"] == "stale"
    assert len(json.dumps(page, ensure_ascii=False).encode()) <= 32768


@persistence
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


@persistence
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


@persistence
def test_busy_and_quota_preserve_commits(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / "memory")
    ids = store.remember("a", "first")["ids"]
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        assert store.remember("b", "second")["status"] == "busy"
    monkeypatch.setattr("cognitive_castle.fast_memory.MAX_STORE_BYTES", 1)
    assert store.remember("c", "third")["status"] == "quota"
    assert store.read_sources(ids)["sources"][0]["text"] == "first"


@persistence
def test_checkpoint_rejects_non_json_keys(tmp_path):
    store = MemoryStore(tmp_path / "memory")
    with pytest.raises(ValueError):
        store.save_checkpoint("source", {1: "silently coerced"})
    assert not store.directory.exists()


@persistence
def test_exact_chunk_boundary_and_corrupt_database(tmp_path):
    store = MemoryStore(tmp_path / "memory")
    text = "x" * 8191 + "😀" + "\r\n"
    ids = store.remember("boundary", text)["ids"]
    sources = store.read_sources(ids)["sources"]
    assert [s["text"] for s in sources] == ["x" * 8191, "😀\r\n"]
    assert [s["provenance"]["chunk_start"] for s in sources] == [0, 8191]
    store.db_path.write_bytes(b"invalid SQLite")
    assert store.status()["status"] == "corrupt"


@persistence
def test_database_symlink(tmp_path):
    directory = tmp_path / "memory"
    directory.mkdir(mode=0o700)
    target = tmp_path / "target"
    target.write_text("secret")
    (directory / "memory.sqlite3").symlink_to(target)
    assert MemoryStore(directory).remember("a", "hello")["status"] == "unavailable"


@persistence
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


@persistence
def test_sqlite_full_rolls_back_partial_write(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / "memory")
    first = store.remember("first", "original exact words")
    monkeypatch.setattr(
        "cognitive_castle.fast_memory.MAX_STORE_BYTES", store.db_path.stat().st_size + 4096
    )
    assert store.remember("large", "z" * 65536)["status"] == "quota"
    assert store.read_sources(first["ids"])["sources"][0]["text"] == "original exact words"
    assert store.status()["indexed_chunks"] == 1


@pytest.mark.parametrize("unsupported", ["platform", "nofollow"])
def test_unsupported_privacy_never_mutates(tmp_path, monkeypatch, unsupported):
    from types import SimpleNamespace
    import cognitive_castle.fast_memory as module

    store = MemoryStore(tmp_path / "fresh")
    if unsupported == "platform":
        monkeypatch.setattr(module, "os", SimpleNamespace(name="unsupported"))
    else:
        monkeypatch.delattr(os, "O_NOFOLLOW", raising=False)
    assert store.remember("a", "hello")["status"] == "unavailable"
    assert not store.directory.exists()
    with pytest.raises(_Unavailable):
        store.load_checkpoint("source")
    assert not store.directory.exists()


@persistence
def test_source_contract_trusted_provenance_and_brain_binding(tmp_path):
    from cognitive_castle.brain_loop import BrainLoop

    store = MemoryStore(tmp_path / "memory")
    caller = {"origin": "external", "local_only": False, "text_hash": "forged", "label": "ž" * 195}
    ids = store.remember("a", "exact quotation", caller)["ids"]
    source = store.read_sources(ids)["sources"][0]
    assert set(source) == {"id", "text", "provenance"}
    provenance = source["provenance"]
    assert provenance["origin"] == "archive"
    assert provenance["local_only"] is True
    assert provenance["caller"] == caller
    assert provenance["text_hash"] != "forged"
    assert len(json.dumps(provenance, ensure_ascii=False, separators=(",", ":")).encode()) <= 1024
    prepared, _ = BrainLoop._prepare_inputs("problem", [source], [])
    assert prepared[0]["provenance"]["local_only"] is True


@persistence
@pytest.mark.parametrize("unsafe", ["permissions", "symlink"])
def test_checkpoint_untrusted_storage_is_visible(tmp_path, unsafe):
    store = MemoryStore(tmp_path / "memory")
    store.save_checkpoint("source", {"offset": 42})
    original = store.db_path.read_bytes()
    if unsafe == "permissions":
        store.db_path.chmod(0o644)
    else:
        target = store.db_path.with_name("original")
        store.db_path.rename(target)
        store.db_path.symlink_to(target)
    with pytest.raises(_Unavailable, match="unsafe|symlink"):
        store.load_checkpoint("source")
    assert store.db_path.read_bytes() == original


@persistence
@pytest.mark.parametrize("field", ["provenance", "receipt"])
def test_corrupt_persisted_json_returns_corrupt(tmp_path, field):
    store = MemoryStore(tmp_path / "memory")
    ids = store.remember("a", "exact quotation")["ids"]
    with sqlite3.connect(store.db_path) as conn:
        if field == "provenance":
            conn.execute("UPDATE chunks SET provenance='not-json'")
        else:
            conn.execute("UPDATE receipts SET ids='not-json'")
    result = (
        store.read_sources(ids) if field == "provenance" else store.remember("a", "exact quotation")
    )
    assert result["status"] == "corrupt"


@persistence
def test_eight_candidate_recall_is_compact_wire_bounded(tmp_path):
    store = MemoryStore(tmp_path / "memory")
    caller = {"x": "ž" * 252}
    for index in range(8):
        assert store.remember(str(index), "needle " + "😀\n\t" * 1000, caller)["status"] == "ok"
    result = store.recall("needle", limit=8)
    assert result["status"] == "ok"
    assert 1 < len(result["sources"]) < 8
    assert len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()) <= 8192
    assert all(set(source) == {"id", "text", "provenance"} for source in result["sources"])


@persistence
def test_observation_validation_atomicity_and_paging(tmp_path):
    store = MemoryStore(tmp_path / "memory")
    checkpoint = {"offset": 0}
    observation = {
        "generation": 0,
        "reason": "pending_tail",
        "start": 0,
        "end": 10,
        "record_start": 0,
        "hash_scope": "segment",
        "sha256": "a" * 64,
    }
    store.save_checkpoint("source", checkpoint, observations=[observation])
    store.save_checkpoint("source", checkpoint, observations=[observation])
    assert len(store.status()["observations"]) == 1
    with pytest.raises(ValueError):
        store.save_checkpoint(
            "source", {"offset": 10}, observations=[dict(observation, text="forbidden")]
        )
    assert store.load_checkpoint("source") == checkpoint
    with pytest.raises(ValueError):
        store.status(after=-1)
    with pytest.raises(ValueError):
        store.status(limit=17)


@persistence
def test_observations_rollback_with_checkpoint_transaction(tmp_path):
    store = MemoryStore(tmp_path / "memory")
    store.save_checkpoint("source", {"offset": 0})
    with store._connect(True) as conn:
        conn.execute(
            "CREATE TRIGGER reject_advance BEFORE UPDATE ON checkpoints BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END"
        )
    observation = {
        "generation": 0,
        "reason": "unsupported",
        "start": 0,
        "end": 5,
        "record_start": 0,
        "hash_scope": "record",
        "sha256": "a" * 64,
    }
    with pytest.raises(sqlite3.IntegrityError):
        store.save_checkpoint("source", {"offset": 5}, observations=[observation])
    assert store.load_checkpoint("source") == {"offset": 0}
    assert store.status()["observations"] == []


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("database is locked", "busy"),
        ("database table is locked", "busy"),
        ("database or disk is full", "quota"),
        ("interrupted", "deadline"),
        ("database disk image is malformed", "corrupt"),
        ("file is not a database", "corrupt"),
        ("user text: database is locked", "unavailable"),
    ],
)
def test_python310_sqlite_error_without_codes(monkeypatch, message, expected):
    for name in ["BUSY", "LOCKED", "FULL", "INTERRUPT", "CORRUPT", "NOTADB"]:
        monkeypatch.delattr(sqlite3, "SQLITE_" + name, raising=False)
    exc = sqlite3.OperationalError(message)
    assert not hasattr(exc, "sqlite_errorcode")
    assert MemoryStore._error(exc) == {"status": expected}
    assert MemoryStore._error(ValueError(message)) == {"status": "unavailable"}
    assert MemoryStore._error(sqlite3.IntegrityError(message)) == {"status": "unavailable"}


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (5, "busy"),
        (6, "busy"),
        (13, "quota"),
        (9, "deadline"),
        (11, "corrupt"),
        (26, "corrupt"),
        (1, "unavailable"),
    ],
)
def test_sqlite_primary_codes_take_precedence(code, expected):
    exc = sqlite3.DatabaseError("database is locked")
    exc.sqlite_errorcode = code | (2 << 8)
    assert MemoryStore._error(exc) == {"status": expected}


@persistence
def test_explicit_any_match_broadens_candidates_without_changing_default(tmp_path):
    from cognitive_castle.fast_memory import MemoryStore

    store = MemoryStore(tmp_path / "matching")
    store.remember("one", "Storage persistence uses the API.")
    store.remember("two", "Architecture revision supersedes an older proposal.")
    assert store.recall("persistence architecture")["sources"] == []
    result = store.recall("persistence architecture", match="any")
    assert result["status"] == "ok"
    assert len(result["sources"]) == 2
    assert result["matching"] == "any"
    assert store.recall("unseenword", match="any")["sources"] == []
