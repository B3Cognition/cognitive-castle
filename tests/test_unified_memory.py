"""Canonical reads preserve occurrence identity and filter before bounded ranking."""

import hashlib
import json
import os
import sqlite3

import pytest

from cognitive_castle.fast_memory import MemoryStore

pytestmark = pytest.mark.skipif(os.name != "posix", reason="private POSIX persistence")


def unified(palace):
    from cognitive_castle.unified_memory import UnifiedMemoryStore

    return UnifiedMemoryStore(palace)


def historical(palace, label="history", state="complete"):
    from cognitive_castle.unified_memory import history_store_path, register_history_store

    identity = hashlib.sha256(label.encode()).hexdigest()
    directory = history_store_path(palace, identity)
    directory.parent.mkdir(mode=0o700, exist_ok=True)
    store = MemoryStore(directory)
    store.remember("first", "signal historical ž😀\x00 \r\n", {"workspace": "/work", "wing": "a"})
    result = register_history_store(
        palace, identity, archive_id=label, state=state, indexed_rows=1, total_rows=1
    )
    assert result["status"] == "ok"
    return store, identity


def exposure(source):
    # Existing public hash meaning is complete canonical source JSON.
    from cognitive_castle.brain_loop import source_exposure_hash

    return source_exposure_hash(source)


def test_live_and_history_exact_hydration_restart_and_pages(tmp_path):
    live = MemoryStore(tmp_path / ".memory")
    live_id = live.remember("fresh", "signal fresh", {"workspace": "/work"})["ids"][0]
    history, _ = historical(tmp_path)
    result = unified(tmp_path).recall("signal")
    assert result["status"] == "ok"
    assert {s["text"] for s in result["sources"]} == {
        "signal fresh",
        "signal historical ž😀\x00 \r\n",
    }
    assert live_id in {s["id"] for s in result["sources"]}
    for source in result["sources"]:
        exact = unified(tmp_path).read_sources([source["id"]])["sources"][0]
        assert exposure(exact) == exposure(source)
        page = unified(tmp_path).page(
            source["id"], offset=7, limit=6, expected_hash=source["provenance"]["text_hash"]
        )
        assert page["text"] == exact["text"][7:13]
        assert unified(tmp_path).page(source["id"], expected_hash="wrong")["status"] == "stale"
    assert history.db_path.exists()
    assert result["coverage"] == "indexed_only"


def test_authorized_low_rank_hit_is_not_displaced(tmp_path):
    live = MemoryStore(tmp_path / ".memory")
    for i in range(40):
        live.remember(str(i), "signal " * 20, {"room": "denied"})
    target = live.remember("target", "signal allowed", {"room": "allowed"})["ids"]
    source = live.read_sources(target)["sources"][0]
    result = unified(tmp_path).recall(
        "signal", limit=1, allowed_source_hashes=[exposure(source)], policy_epoch="v1"
    )
    assert [s["id"] for s in result["sources"]] == target
    assert unified(tmp_path).recall("signal", allowed_source_hashes=[])["sources"] == []


def test_scope_filter_precedes_limit_and_reads_capture_mapping(tmp_path):
    live = MemoryStore(tmp_path / ".memory")
    live.remember("outside", "signal " * 20, {"workspace": "/else", "wing": "a"})
    scoped = live.remember("inside", "signal scoped", {"wing": "a", "room": "r"})["ids"]
    with sqlite3.connect(live.db_path) as conn:
        conn.execute(
            "CREATE TABLE capture_chunk_scopes (chunk_id TEXT PRIMARY KEY, workspace TEXT)"
        )
        conn.execute("INSERT INTO capture_chunk_scopes VALUES (?,?)", (scoped[0], "/work"))
    historical(tmp_path)
    result = unified(tmp_path).recall("signal", workspace="/work", wing="a", room="r", limit=1)
    assert [s["id"] for s in result["sources"]] == scoped
    assert {s["id"] for s in unified(tmp_path).context_sources("/work")["sources"]} >= set(scoped)


def test_distinct_occurrences_interleave_deterministically(tmp_path):
    live = MemoryStore(tmp_path / ".memory")
    for i in range(5):
        live.remember(str(i), "signal same")
    history, _ = historical(tmp_path)
    history_ids = history.remember("same", "signal same")["ids"]
    result = unified(tmp_path).recall("signal", limit=2)
    assert len({s["id"] for s in result["sources"]}) == 2
    assert any(s["id"] in history_ids or "historical" in s["text"] for s in result["sources"])
    assert result["sources"] == unified(tmp_path).recall("signal", limit=2)["sources"]


def test_cursor_binds_query_scope_policy_live_and_catalog_generations(tmp_path):
    live = MemoryStore(tmp_path / ".memory")
    for i in range(5):
        live.remember(str(i), "signal same")
    store = unified(tmp_path)
    first = store.recall("signal", limit=1, policy_epoch="v1")
    cursor = first["next_cursor"]
    assert cursor
    second = store.recall("signal", limit=1, policy_epoch="v1", cursor=cursor)
    assert second["sources"][0]["id"] != first["sources"][0]["id"]
    for changed in ({"query": "same"}, {"workspace": "/work"}, {"policy_epoch": "v2"}):
        args = {"query": "signal", "limit": 1, "policy_epoch": "v1", "cursor": cursor, **changed}
        assert store.recall(**args)["status"] == "stale_cursor"
    live.remember("new", "signal new")
    assert (
        store.recall("signal", limit=1, policy_epoch="v1", cursor=cursor)["status"]
        == "stale_cursor"
    )
    next_cursor = store.recall("signal", limit=1)["next_cursor"]
    historical(tmp_path)
    assert store.recall("signal", limit=1, cursor=next_cursor)["status"] == "stale_cursor"


def test_missing_unregistered_and_corrupt_shards_never_claim_complete(tmp_path):
    live = MemoryStore(tmp_path / ".memory")
    live.remember("live", "signal live")
    result = unified(tmp_path).recall("absent")
    assert result["coverage_detail"]["complete"] is False
    assert "history_not_registered" in result["coverage_detail"]["limitations"]
    history, _ = historical(tmp_path)
    history.db_path.unlink()
    result = unified(tmp_path).recall("signal")
    assert result["sources"][0]["text"] == "signal live"
    assert result["coverage_detail"]["complete"] is False
    assert result["coverage_detail"]["stores"][1]["status"] != "ok"
    history.db_path.write_bytes(b"not SQLite")
    history.db_path.chmod(0o600)
    assert unified(tmp_path).recall("signal")["coverage_detail"]["stores"][1]["status"] == "corrupt"


def test_catalog_privacy_corruption_bounds_and_path_escape(tmp_path):
    from cognitive_castle.unified_memory import history_store_path, register_history_store

    _, identity = historical(tmp_path)
    catalog = tmp_path / ".memory-history" / "catalog.json"
    assert catalog.stat().st_mode & 0o077 == 0
    catalog.chmod(0o644)
    assert unified(tmp_path).recall("signal")["status"] == "unavailable"
    catalog.chmod(0o600)
    catalog.write_text("{}")
    assert unified(tmp_path).recall("signal")["status"] == "corrupt"
    with pytest.raises(ValueError):
        history_store_path(tmp_path, "../escape")
    catalog.unlink()
    for i in range(8):
        key = hashlib.sha256(str(i).encode()).hexdigest()
        assert (
            register_history_store(tmp_path, key, archive_id="a", state="pending")["status"] == "ok"
        )
    assert (
        register_history_store(tmp_path, identity, archive_id="b", state="pending")["status"]
        == "quota"
    )


def test_canonical_collision_fails_closed_and_does_not_create_missing_store(tmp_path):
    live = MemoryStore(tmp_path / ".memory")
    identity = live.remember("same", "signal first")["ids"][0]
    history, _ = historical(tmp_path)
    with sqlite3.connect(history.db_path) as conn:
        row = conn.execute("SELECT id FROM chunks LIMIT 1").fetchone()[0]
        conn.execute("UPDATE chunks SET id=? WHERE id=?", (identity, row))
        conn.execute("UPDATE lexical SET id=? WHERE id=?", (identity, row))
    assert unified(tmp_path).read_sources([identity])["status"] == "corrupt"
    empty = tmp_path / "empty"
    empty.mkdir()
    assert unified(empty).read_sources([identity])["status"] != "ok"
    assert not (empty / ".memory").exists()


def test_shared_deadline_and_output_limit_are_explicit(tmp_path, monkeypatch):
    import cognitive_castle.unified_memory as module

    live = MemoryStore(tmp_path / ".memory")
    for i in range(8):
        live.remember(str(i), "signal " + "😀" * 1900)
    result = unified(tmp_path).recall("signal")
    assert len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()) <= 8192
    assert "output_budget" in result["coverage_detail"]["limitations"]
    monkeypatch.setattr(module, "READ_SECONDS", 0)
    result = unified(tmp_path).recall("signal")
    assert result["status"] == "deadline"
    assert result["coverage_detail"]["complete"] is False


def test_worker_routes_only_reads_through_unified(tmp_path):
    from cognitive_castle.memory_worker import _execute

    live = MemoryStore(tmp_path / ".memory")
    live.remember("live", "signal live")
    historical(tmp_path)
    request = {"palace": str(tmp_path), "operation": "recall", "arguments": {"query": "signal"}}
    result = _execute(request)
    assert {s["text"] for s in result["sources"]} == {
        "signal live",
        "signal historical ž😀\x00 \r\n",
    }
    request.update(operation="remember", arguments={"request_id": "write", "text": "new live"})
    identity = _execute(request)["ids"][0]
    assert live.read_sources([identity])["status"] == "ok"


def test_final_response_budget_includes_nine_store_cursor(tmp_path):
    live = MemoryStore(tmp_path / ".memory")
    for number in range(8):
        live.remember(str(number), "signal " + "😀" * 1900, {"note": "x" * 400})
    for number in range(8):
        history, _ = historical(tmp_path, str(number))
        for chunk in range(8):
            history.remember(str(chunk), "signal " + "😀" * 1900, {"note": "x" * 400})
    store = unified(tmp_path)
    result = store.recall("signal")
    for _ in range(12):
        assert len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()) <= 8192
        assert result["sources"]
        if not result["next_cursor"]:
            break
        result = store.recall("signal", cursor=result["next_cursor"])


def test_full_historical_scopes_and_exact_metadata_pages(tmp_path):
    history, _ = historical(tmp_path)
    identity = history.remember("metadata", "signal registry scope", {"metadata_id": "a" * 64})[
        "ids"
    ][0]
    workspace = "/" + "very-long-workspace/" * 12
    exact = '{ "workspace" : ' + json.dumps(workspace) + ', "note": "ž😀" }\r\n'
    columns = json.dumps({"wing": "long" * 50, "room": "room" * 30}, ensure_ascii=False)
    metadata_hash = hashlib.sha256(exact.encode()).hexdigest()
    columns_hash = hashlib.sha256(columns.encode()).hexdigest()
    with sqlite3.connect(history.db_path) as conn:
        conn.execute(
            "CREATE TABLE history_occurrences (identity TEXT PRIMARY KEY, metadata_json TEXT, columns_json TEXT, metadata_hash TEXT, columns_hash TEXT, ids TEXT)"
        )
        conn.execute(
            "INSERT INTO history_occurrences VALUES (?,?,?,?,?,?)",
            ("a" * 64, exact, columns, metadata_hash, columns_hash, json.dumps([identity])),
        )
    store = unified(tmp_path)
    result = store.recall("signal", workspace=workspace, wing="long" * 50, room="room" * 30)
    assert [source["id"] for source in result["sources"]] == [identity]
    reference = result["sources"][0]["metadata"]
    assert reference["metadata_hash"] == metadata_hash
    assert reference["columns_hash"] == columns_hash
    restored = []
    offset = 0
    while True:
        page = store.page(
            identity, field="metadata", offset=offset, limit=11, expected_hash=metadata_hash
        )
        assert page["status"] == "ok"
        restored.append(page["text"])
        if page["complete"]:
            break
        offset = page["next_offset"]
    assert "".join(restored) == exact
    assert store.page(identity, field="columns", expected_hash=columns_hash)["text"] == columns
    assert store.page(identity, field="metadata", expected_hash="wrong")["status"] == "stale"
    with sqlite3.connect(history.db_path) as conn:
        conn.execute("UPDATE history_occurrences SET metadata_json='changed'")
    assert (
        store.page(identity, field="metadata", expected_hash=metadata_hash)["status"] == "corrupt"
    )
