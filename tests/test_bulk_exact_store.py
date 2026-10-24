"""Disposable supervised bulk fixtures, never native imports in the pytest host."""

import hashlib
import json
import os
from pathlib import Path
import sys


def _fixture_main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from cognitive_castle.lance_exact_worker import _install_guards, _admit_storage

    _install_guards()
    os.umask(0o077)
    request = json.load(sys.stdin)
    refusal = _admit_storage(request)
    if refusal:
        print(json.dumps(refusal))
        return
    from cognitive_castle.bulk_exact_store import BulkExactStore
    from cognitive_castle.lance_exact_store import _schema
    import lance
    import pyarrow as pa

    directory = Path(request["directory"])
    store = BulkExactStore(directory, writable=True)
    action = request["fixture"]
    if action in {"lost_response", "before_publish"}:
        if action == "lost_response":
            assert store.import_batch(**request["arguments"])["status"] == "ok"
        return
    dataset = lance.dataset(str(directory / "records.lance"))
    if action == "stats":
        print(
            json.dumps(
                {
                    "status": "ok",
                    "version": dataset.version,
                    "rows": dataset.count_rows(),
                    "fragments": len(dataset.get_fragments()),
                }
            )
        )
        return
    if action in {"drop_proof", "replace_proof"}:
        from cognitive_castle.canonical_records import _hash, _json

        identity = request["arguments"]["id"]
        row = dataset.scanner(filter=f"id = '{identity}'", limit=1).to_table().to_pylist()[0]
        manifest = json.loads(row["receipt"])
        extra = []
        if action == "drop_proof":
            manifest["proof"].pop()
        else:
            from cognitive_castle.bulk_exact_codec import page

            # Same proof kind/count and valid physical hash, but a different ID
            # from the regenerated request. Full replay must compare ID sets.
            original_id = next(
                identity
                for identity, _ in manifest["proof"]
                if dataset.scanner(filter=f"id = '{identity}'", limit=1)
                .to_table()
                .to_pylist()[0]["kind"]
                == "bulk_page"
            )
            original = (
                dataset.scanner(filter=f"id = '{original_id}'", limit=1).to_table().to_pylist()[0]
            )
            header = json.loads(original["receipt"])
            unexpected = page(header["owner"], "metadata", 777, "unexpected proof", 0, 0)
            extra = [unexpected]
            manifest["proof"] = [
                [unexpected["id"], _hash(_json(unexpected))]
                if identity == original_id
                else [identity, digest]
                for identity, digest in manifest["proof"]
            ]
        row["receipt"] = _json(manifest)
        row["digest"] = _hash(row["receipt"])
        dataset.delete(f"id = '{identity}'")
        lance.write_dataset(
            pa.Table.from_pylist([*extra, row], schema=_schema()),
            str(directory / "records.lance"),
            mode="append",
        )
    elif action == "duplicate":
        identity = request["arguments"]["id"]
        rows = dataset.scanner(filter=f"id = '{identity}'", limit=1).to_table().to_pylist()
        lance.write_dataset(
            pa.Table.from_pylist(rows, schema=_schema()),
            str(directory / "records.lance"),
            mode="append",
        )
    elif action == "delete":
        dataset.delete("id = '" + request["arguments"]["id"] + "'")
    else:
        raise ValueError(action)
    print('{"status":"ok"}')


if __name__ == "__main__":
    _fixture_main()
    raise SystemExit(0)

import pytest  # noqa: E402
from cognitive_castle.bulk_exact_codec import prepare_owner, page_id, entry_batches  # noqa: E402
from cognitive_castle.canonical_records import prepare_remember  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="owned-group supervision")
ROOT = Path(__file__).resolve().parents[1]


def invoke(directory, operation=None, arguments=None, *, fixture=None):
    from cognitive_castle import memory_runtime as runtime

    request = {"directory": str(directory)}
    if fixture:
        request.update(fixture=fixture, arguments=arguments or {})
        worker = Path(__file__).resolve()
    else:
        request.update(operation=operation, arguments=arguments or {})
        worker = ROOT / "cognitive_castle" / "lance_exact_worker.py"
    admission = runtime._admission()
    try:
        result = runtime._supervise(
            request,
            admission,
            worker_command=[sys.executable, "-I", str(worker)],
            deadline=3
            if fixture
            or operation in {"import_batch", "build_id_index", "remember", "import_sources"}
            else 2,
            rss_limit=192 * 1024**2,
            total_rss_limit=256 * 1024**2,
        )
    finally:
        os.close(admission)
    print(
        "BULK_STAGE",
        json.dumps(
            {
                "operation": operation or fixture,
                **{
                    k: v
                    for k, v in result.items()
                    if k
                    in {"status", "reason", "resources", "lookup", "version", "rows", "fragments"}
                },
            }
        ),
        flush=True,
    )
    return {key: value for key, value in result.items() if key != "resources"}


def unit(key="owner", text="exact ž😀\x00\r\n", **kwargs):
    prepared = prepare_remember(key, text)
    rows, owner = prepare_owner(key, "snapshot", prepared.records, **kwargs)
    return rows, owner, prepared


def publish(directory, rows, owners, key="batch"):
    return invoke(
        directory,
        "import_batch",
        {"batch_id": key, "source_binding": "snapshot", "entries": rows, "finalizations": owners},
    )


def test_more_than_eight_in_one_append_replay_and_reuse(tmp_path):
    directory = tmp_path / "bulk"
    rows, owners, prepared = [], [], []
    for n in range(12):
        r, o, p = unit(str(n))
        rows.extend(r)
        owners.append(o)
        prepared.append(p)
    first = publish(directory, rows, owners)
    assert first["status"] == "ok", first
    assert first["published_owners"] == 12 and first["records"] == 12
    assert "ids" not in first
    before = invoke(directory, fixture="stats")
    assert before["version"] == 1
    assert publish(directory, rows, owners) == first
    assert publish(directory, rows, owners, "reuse")["status"] == "ok"
    after = invoke(directory, fixture="stats")
    assert after["rows"] == before["rows"] + 1
    assert publish(directory, rows[:-1], owners) == {"status": "conflict"}
    result = invoke(directory, "read_sources", {"ids": [prepared[-1].records[0].id]})
    assert result["sources"] == [prepared[-1].records[0].source()]


def test_staging_visibility_finalization_and_original_receipt(tmp_path):
    directory = tmp_path / "bulk"
    p = prepare_remember("original", "😀" * 3000, namespace="original-host")
    rows, owner = prepare_owner(
        "occ",
        "snapshot",
        p.records,
        metadata=' { "ž": "😀" }\n\x00' * 1000,
        columns="\t{}\n",
        scopes=json.dumps({"absent": None, "conflict": ["one", "two"], "long": "x" * 20000}),
        descriptor='{"identity":"original","alias":"a","cursor":123}',
        metadata_id="a" * 64,
        live={
            "namespace": p.namespace,
            "key": p.request_id,
            "digest": p.digest,
            "receipt": p.receipt,
        },
    )
    assert publish(directory, rows, [], "stage")["state"] == "stage_batch"
    ids = [r.id for r in p.records]
    assert invoke(directory, "read_sources", {"ids": ids})["status"] == "not_found"
    assert invoke(directory, "page", {"source_id": ids[0]})["status"] == "not_found"
    assert (
        invoke(directory, "receipt", {"namespace": p.namespace, "key": p.request_id})["status"]
        == "not_found"
    )
    args = {
        "batch_id": "final",
        "source_binding": "snapshot",
        "entries": [],
        "finalizations": [owner],
    }
    assert (
        invoke(directory, fixture="before_publish", arguments=args)["reason"]
        == "worker_invalid_frame"
    )
    assert invoke(directory, "read_sources", {"ids": ids})["status"] == "not_found"
    assert (
        invoke(directory, fixture="lost_response", arguments=args)["reason"]
        == "worker_invalid_frame"
    )
    final = invoke(directory, "import_batch", args)
    assert final["state"] == "committed_batch"
    receipt = invoke(
        directory,
        "remember",
        {
            "request_id": p.request_id,
            "namespace": p.namespace,
            "text": "".join(r.text for r in p.records),
        },
    )
    assert receipt == p.receipt
    result = invoke(directory, "read_sources", {"ids": ids})
    assert result["sources"][0]["metadata"]["metadata_hash"] == owner["fields"]["metadata"]["hash"]
    for original, actual in zip(p.records, result["sources"]):
        assert {k: actual[k] for k in ("id", "text", "provenance")} == original.source()
    got = invoke(
        directory, "bulk_page", {"owner": owner["owner"], "field": "metadata", "ordinal": 0}
    )
    assert got["status"] == "ok" and got["text"].startswith(' { "ž": "😀" }\n\x00')
    assert (
        invoke(
            directory,
            "bulk_page",
            {
                "owner": owner["owner"],
                "field": "metadata",
                "ordinal": 0,
                "version": got["version"] - 1,
            },
        )["status"]
        == "stale"
    )
    assert (
        "lance" not in sys.modules and "pyarrow" not in sys.modules and "sqlite3" not in sys.modules
    )


def test_byte_refusal_before_artifacts_and_empty_owner(tmp_path):
    directory = tmp_path / "bulk"
    rows, owner, _ = unit()
    giant = {**rows[0], "text": "\x00" * 100000}
    result = publish(directory, [giant], [])
    assert result["status"] != "ok" and not directory.exists()
    empty_rows, empty = prepare_owner("empty", "snapshot", ())
    assert publish(directory, empty_rows, [empty])["status"] == "ok"
    result = invoke(directory, "bulk_owner", {"owner": empty["owner"]})
    assert result["manifest"]["members"] == 0


def test_missing_membership_duplicate_and_staged_rebinding(tmp_path):
    directory = tmp_path / "bulk"
    rows, owner, p = unit()
    membership = page_id(owner["owner"], "membership", 0)
    assert (
        publish(directory, [r for r in rows if r["id"] != membership], [], "incomplete")["status"]
        == "ok"
    )
    assert publish(directory, [], [owner], "final")["status"] == "corrupt"
    other_rows, other = prepare_owner("different", "snapshot", p.records)
    assert publish(directory, other_rows, [other], "rebind")["status"] == "conflict"
    assert (
        publish(directory, [r for r in rows if r["id"] == membership], [owner], "complete")[
            "status"
        ]
        == "ok"
    )
    assert (
        invoke(directory, fixture="duplicate", arguments={"id": p.records[0].id})["status"] == "ok"
    )
    assert publish(directory, rows, [owner])["status"] == "corrupt"


def test_explicit_index_many_commits_late_tail_and_duplicate(tmp_path):
    directory = tmp_path / "indexed"
    last = None
    for commit in range(9):
        rows, owners = [], []
        for n in range(24):
            r, o, p = unit(f"{commit}-{n}")
            rows.extend(r)
            owners.append(o)
            last = p
        result = publish(directory, rows, owners, f"commit-{commit}")
        assert result["status"] == "ok", result
    # Nine real commits cross the qualified unindexed-tail row allowance.
    assert invoke(directory, "bulk_owner", {"owner": owners[-1]["owner"]}) == {
        "status": "index_required"
    }
    indexed = invoke(directory, "build_id_index")
    assert indexed["status"] == "ok", indexed
    assert indexed["lookup"]["tail_rows"] == 0 and indexed["lookup"]["indexed_fragments"] == 9
    assert (
        invoke(directory, "read_sources", {"ids": [last.records[0].id]})["sources"][0]
        == last.records[0].source()
    )
    r, o, p = unit("late-tail")
    assert publish(directory, r, [o], "tail")["status"] == "ok"
    tail = invoke(directory, "bulk_owner", {"owner": o["owner"]})
    assert tail["lookup"]["tail_rows"] > 0 and tail["lookup"]["index_version"] is not None
    # A duplicate spanning indexed data and an appended tail must not be hidden.
    assert (
        invoke(directory, fixture="duplicate", arguments={"id": last.records[0].id})["status"]
        == "ok"
    )
    assert publish(directory, rows, owners, "duplicate-check") == {"status": "corrupt"}


def test_multibatch_original_whole_hash_and_paged_receipt(tmp_path):
    from cognitive_castle.canonical_records import CanonicalRecord, _hash, _json

    directory = tmp_path / "large"
    piece = " ž😀\x00\r\n" * 680  # 6800 UTF8 bytes, preserving Unicode boundaries.
    records = []
    offset = 0
    whole = hashlib.sha256()
    for n in range(128):
        p = prepare_remember(f"large-{n}", piece).records[0].source()["provenance"]
        p.update(chunk_start=offset, chunk_end=offset + len(piece))
        records.append(CanonicalRecord("memory:" + _hash(f"large:{n}"), piece, _json(p)))
        offset += len(piece)
        whole.update(piece.encode())
    rows, owner = prepare_owner(
        "large",
        "snapshot",
        records,
        metadata=" \tž😀\x00\n" * 20000,
        columns='{ "columns": [] }\n',
        scopes="null" + " " * 40000,
        descriptor='{"alias":"original","cursor":{"start":0,"end":128}}',
    )
    for start, batch in enumerate(entry_batches(rows)):
        result = publish(directory, batch, [], f"part-{start}")
        assert result["status"] == "ok", result
    before = invoke(directory, fixture="stats")
    final = publish(directory, [], [owner], "finish")
    assert final["status"] == "ok", final
    after = invoke(directory, fixture="stats")
    assert after["rows"] == before["rows"] + 2  # Marker and receipt, no text copy.
    assert owner["text_hash"] == whole.hexdigest()
    assert invoke(directory, "read_sources", {"ids": [records[-1].id]})["sources"] == [
        records[-1].source()
    ]
    receipt = invoke(
        directory, "bulk_receipt", {"batch_id": "part-0", "source_binding": "snapshot"}
    )
    assert len(receipt["proof"]) == 16 and not receipt["complete"]
    tail = invoke(
        directory,
        "bulk_receipt",
        {
            "batch_id": "part-0",
            "source_binding": "snapshot",
            "offset": receipt["next_offset"],
            "version": receipt["version"],
        },
    )
    assert tail["next_offset"] > receipt["next_offset"]
    print(
        "BULK_WHOLE_HASH",
        json.dumps(
            {
                "text_bytes": owner["text_bytes"],
                "text_chars": owner["text_chars"],
                "chunks": owner["members"],
                "staged_entries": len(rows),
                "before": before,
                "after": after,
            }
        ),
        flush=True,
    )


def test_semantic_hydration_stays_pending_until_bulk_owner_published(tmp_path):
    from cognitive_castle.semantic_indexer import _hydrate
    from cognitive_castle.semantic_intents import prepare_intent
    from cognitive_castle.semantic_runtime import SemanticSession

    rows, owner, prepared = unit("semantic")
    directory = tmp_path / "generation"
    directory.mkdir(mode=0o700)
    assert publish(directory / "exact", rows, [], "stage")["status"] == "ok"
    group = prepare_intent(
        prepared, [{"workspace": "fixture", "wing": "w", "room": "r"}], "history"
    )["groups"][0]
    with SemanticSession(tmp_path / "unused", interactive=False) as session:
        staged = _hydrate(session, directory, group)
    assert staged["status"] == "not_found"
    assert publish(directory / "exact", [], [owner], "final")["status"] == "ok"
    with SemanticSession(tmp_path / "unused", interactive=False) as session:
        visible = _hydrate(session, directory, group)
    assert visible["status"] == "ok"
    assert visible["sources"][0]["source"] == prepared.records[0].source()


@pytest.mark.parametrize(
    "damage",
    [
        "membership_offset",
        "membership_hash",
        "text_hash",
        "metadata_hash",
        "columns_hash",
        "scope_hash",
    ],
)
def test_finalization_refuses_malformed_or_reordered_content(tmp_path, damage):
    from cognitive_castle.canonical_records import _json, _hash

    directory = tmp_path / "bulk"
    rows, owner, _ = unit(
        text="a" * 8192 + "tail", metadata="exact\x00 ", columns="{}", scopes="null"
    )
    if damage.startswith("membership"):
        row = next(
            r
            for r in rows
            if r["kind"] == "bulk_page" and json.loads(r["receipt"])["field"] == "membership"
        )
        if damage == "membership_offset":
            header = json.loads(row["receipt"])
            header["offset"] = 1
            row["receipt"] = _json(header)
        else:
            member = json.loads(row["text"])
            member["hash"] = "0" * 64
            row["text"] = _json(member)
            row["digest"] = _hash(row["text"])
    elif damage == "text_hash":
        owner["text_hash"] = "0" * 64
    else:
        owner["fields"][
            {"metadata_hash": "metadata", "columns_hash": "columns", "scope_hash": "scopes"}[damage]
        ]["hash"] = "0" * 64
    assert publish(directory, rows, [], "stage")["status"] == "ok"
    assert publish(directory, [], [owner], "final") == {"status": "corrupt"}


def test_bulk_reads_are_readonly_and_unsafe_hardlink_is_rejected(tmp_path):
    directory = tmp_path / "bulk"
    rows, owner, prepared = unit(metadata=" \t😀\x00\n", columns="{} ")
    assert publish(directory, rows, [owner])["status"] == "ok"

    def inventory():
        return {
            str(p): (p.stat().st_mtime_ns, p.stat().st_size, p.stat().st_mode)
            for p in directory.rglob("*")
        }

    before = inventory()
    for operation, arguments in (
        ("bulk_owner", {"owner": owner["owner"]}),
        ("bulk_page", {"owner": owner["owner"], "field": "metadata", "ordinal": 0}),
        ("bulk_receipt", {"batch_id": "batch", "source_binding": "snapshot"}),
        ("read_sources", {"ids": [prepared.records[0].id]}),
    ):
        assert invoke(directory, operation, arguments)["status"] == "ok"
    assert inventory() == before
    os.link(directory / ".write.lock", tmp_path / "external-link")
    assert invoke(directory, "bulk_owner", {"owner": owner["owner"]}) == {"status": "unavailable"}


def test_visible_legacy_record_reused_without_exposure_or_kind_change(tmp_path):
    directory = tmp_path / "bulk"
    rows, owner, prepared = unit()
    assert (
        invoke(
            directory,
            "remember",
            {"request_id": prepared.request_id, "text": "".join(r.text for r in prepared.records)},
        )
        == prepared.receipt
    )
    assert publish(directory, rows, [], "stage")["status"] == "ok"
    assert invoke(directory, "read_sources", {"ids": [prepared.records[0].id]})["sources"] == [
        prepared.records[0].source()
    ]
    assert publish(directory, [], [owner], "final")["status"] == "ok"
    assert invoke(directory, "read_sources", {"ids": [prepared.records[0].id]})["sources"] == [
        prepared.records[0].source()
    ]


def test_migrated_ninth_live_chunk_uses_original_receipt(tmp_path):
    directory = tmp_path / "bulk"
    prepared = prepare_remember("ninth", "€" * 21845)
    rows, owner = prepare_owner(
        "ninth",
        "snapshot",
        prepared.records,
        live={
            "namespace": prepared.namespace,
            "key": prepared.request_id,
            "digest": prepared.digest,
            "receipt": prepared.receipt,
        },
    )
    assert len(prepared.records) == 9
    assert publish(directory, rows, [owner])["status"] == "ok"
    assert (
        invoke(directory, "remember", {"request_id": prepared.request_id, "text": "€" * 21845})
        == prepared.receipt
    )
    assert (
        invoke(directory, "receipt", {"namespace": prepared.namespace, "key": prepared.request_id})[
            "receipt"
        ]
        == prepared.receipt
    )


def test_replay_refuses_incomplete_durable_batch_proof(tmp_path):
    directory = tmp_path / "bulk"
    rows, owner, _ = unit()
    receipt = publish(directory, rows, [owner])
    assert receipt["status"] == "ok"
    assert (
        invoke(directory, fixture="drop_proof", arguments={"id": receipt["receipt_id"]})["status"]
        == "ok"
    )
    assert publish(directory, rows, [owner]) == {"status": "corrupt"}


def test_decoded_byte_refusal_and_256_entry_ceiling(tmp_path):
    from cognitive_castle import bulk_exact_codec as c

    directory = tmp_path / "refused"
    rows, _ = c.prepare_owner("too-big", "snapshot", (), metadata="x" * (50 * 8192))
    assert len(json.dumps(rows).encode()) < 480 * 1024
    assert publish(directory, rows, [])["reason"] == "invalid_exact_request"
    assert not directory.exists()
    rows = [
        c.page(c.owner_id("tiny-pages", "snapshot"), "metadata", n, "x", n, n) for n in range(256)
    ]
    assert publish(directory, rows, [], "256")["status"] == "ok"
    assert invoke(directory, fixture="stats")["rows"] == 257
    assert (
        publish(tmp_path / "count-refused", rows + [rows[0]], [], "257")["reason"]
        == "invalid_exact_request"
    )
    assert not (tmp_path / "count-refused").exists()


def test_exact_full_scope_pages_include_absence_conflict_and_unicode(tmp_path):
    directory = tmp_path / "bulk"
    scope_text = ' { "workspace": null, "room": ["one", "two"], "path": "' + "ž😀" * 3000 + '" } \n'
    rows, owner, _ = unit(scopes=scope_text)
    assert publish(directory, rows, [owner])["status"] == "ok"
    stored = invoke(directory, "bulk_owner", {"owner": owner["owner"]})
    pages = []
    for n in range(owner["fields"]["scopes"]["pages"]):
        result = invoke(
            directory,
            "bulk_page",
            {
                "owner": owner["owner"],
                "field": "scopes",
                "ordinal": n,
                "version": stored["version"],
            },
        )
        assert result["status"] == "ok"
        pages.append(result["text"])
    assert "".join(pages) == scope_text
