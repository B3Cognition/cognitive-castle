"""Synthetic vector qualification; native imports stay in supervised children."""

import copy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def _fixture_main():
    sys.path.insert(0, str(ROOT))
    from cognitive_castle.semantic_store_worker import _admit, _install_guards

    request = json.load(sys.stdin)
    phase = request.get("phase", "vector")
    _install_guards(phase)
    refusal = _admit(request, phase)
    if refusal:
        print(json.dumps(refusal))
        return
    os.umask(0o077)
    from cognitive_castle.lance_vector_store import LanceVectorStore
    from cognitive_castle.lance_exact_store import LanceExactStore

    directory = Path(request["directory"])
    action = request["fixture"]
    if action == "seed":
        result = LanceExactStore(directory / "exact", writable=True).import_sources(
            request["sources"][0]["id"], request["sources"]
        )
    elif action == "lost_response":
        assert (
            LanceVectorStore(directory, writable=True).publish(**request["arguments"])["status"]
            == "ok"
        )
        return
    elif action == "oversized_proof":
        from cognitive_castle import lance_vector_store

        prepare = lance_vector_store.prepare_publication

        def oversized(*args, **kwargs):
            rows, proof = prepare(*args, **kwargs)
            proof["handoff_hash"] = "x" * 200000
            return rows, proof

        lance_vector_store.prepare_publication = oversized
        try:
            result = LanceVectorStore(directory, writable=True).publish(**request["arguments"])
        except ValueError:
            result = {"status": "rejected"}
    elif action == "guards":
        denied = []
        for name in ("pandas", "torch", "onnxruntime", "tokenizers", "requests", "lancedb") + (
            ("lance", "pyarrow", "numpy") if phase == "queue" else ()
        ):
            try:
                __import__(name)
            except ModuleNotFoundError:
                denied.append(name)
        import socket
        import subprocess

        for name, attempt in (
            ("network", socket.socket),
            ("child", lambda: subprocess.Popen([sys.executable, "-c", "pass"])),
        ):
            try:
                attempt()
            except PermissionError:
                denied.append(name)
        result = {"status": "ok", "denied": denied}
    elif action == "cleanup":
        result = {"status": "ok", "worker_pid": os.getpid(), "group_pid": os.getpgrp()}
    else:
        import lance
        import pyarrow as pa

        dataset = lance.dataset(str(directory / "vectors" / "units.lance"))
        if action == "count":
            result = {"status": "ok", "rows": dataset.count_rows(), "columns": dataset.schema.names}
        elif action == "bad_schema":
            lance.write_dataset(
                pa.table({"bad": ["schema"]}),
                str(directory / "vectors" / "units.lance"),
                mode="overwrite",
            )
            result = {"status": "ok"}
        elif action in {"bad_vector", "bad_receipt", "missing_unit", "duplicate_receipt"}:
            kind = "receipt" if "receipt" in action else "unit"
            row = dataset.scanner(filter="kind = '" + kind + "'", limit=1).to_table().to_pylist()[0]
            if action != "duplicate_receipt":
                dataset.delete("id = '" + row["id"] + "'")
            if action == "bad_vector":
                row["vector"] = [0.0] * 384
            if action == "bad_receipt":
                row["receipt"] = "{}"
            if action != "missing_unit":
                lance.write_dataset(
                    pa.Table.from_pylist([row], schema=dataset.schema),
                    str(directory / "vectors" / "units.lance"),
                    mode="append",
                )
            result = {"status": "ok"}
        else:
            raise ValueError(action)
    print(json.dumps(result))


if __name__ == "__main__":
    _fixture_main()
    raise SystemExit(0)

import pytest  # noqa: E402

from test_semantic_queue import SCOPE, invoke  # noqa: E402


def fixture(directory, action, **kwargs):
    from cognitive_castle import memory_runtime as runtime

    admission = runtime._admission()
    try:
        result = runtime._supervise(
            {"directory": str(directory), "fixture": action, **kwargs},
            admission,
            worker_command=[sys.executable, "-I", str(Path(__file__).resolve())],
            deadline=3,
            rss_limit=(128 if kwargs.get("phase") == "queue" else 192) * 1024**2,
            total_rss_limit=(192 if kwargs.get("phase") == "queue" else 256) * 1024**2,
        )
    finally:
        os.close(admission)
    assert result.get("reason") not in {
        "worker_memory_limit",
        "total_memory_limit",
        "parent_memory_limit",
        "system_pressure_unavailable",
        "worker_deadline",
    }, result
    return {key: value for key, value in result.items() if key != "resources"}


def publication(key="batch", text="exact source", vector=None, *, nonsemantic=False, scope=None):
    from cognitive_castle.canonical_records import prepare_remember
    from cognitive_castle.semantic_profile import PROFILE_ID
    from cognitive_castle.semantic_windows import make_unit, page_units
    from cognitive_castle.unified_memory import _exposure

    source = prepare_remember("fixture-" + text, text).records[0].source()
    sources = [{"source": source, "expected_hash": source["provenance"]["text_hash"]}]
    tokens = {"input_ids": [0, 42, 2], "attention_mask": [1, 1, 1], "token_type_ids": [0, 0, 0]}
    unit = make_unit(
        source, 0, 0 if nonsemantic else 1, 0, len(text), tokens, [[0, 0], [0, len(text)], [0, 0]]
    )
    page = page_units(sources, [unit])
    inference = {
        key: page[key]
        for key in (
            "status",
            "profile",
            "handoff_hash",
            "input_binding",
            "start_window",
            "total_units",
            "next_continuation",
            "complete",
        )
    }
    inference.update(
        vectors=[{"unit_id": unit["unit_id"], "vector": vector or [1.0] + [0.0] * 383}],
        runtime={
            "onnxruntime": "1.25.1",
            "providers": ["CPUExecutionProvider"],
            "tokenizer_loaded": False,
        },
    )
    assert inference["profile"] == PROFILE_ID
    return {
        "batch_key": key,
        "references": [
            {
                "canonical_id": source["id"],
                "source_hash": source["provenance"]["text_hash"],
                "exposure_hash": _exposure(source),
                "scope": scope or SCOPE,
            }
        ],
        "page": page,
        "inference": inference,
    }, source


def test_publication_contract_rejects_changed_inference_and_stabilizes_float32():
    from cognitive_castle.lance_vector_store import prepare_publication

    args, _ = publication()
    prepared = prepare_publication(**args)
    changed = copy.deepcopy(args)
    changed["inference"]["vectors"][0]["vector"][0] = 1.000000001
    assert prepare_publication(**changed) == prepared
    changed["inference"]["input_binding"] = "f" * 64
    with pytest.raises(ValueError):
        prepare_publication(**changed)


@pytest.mark.skipif(sys.platform != "darwin", reason="owned guardian supervision")
def test_atomic_publish_reopen_replay_shared_units_and_receipt_recovery(tmp_path):
    directory = tmp_path / "generation"
    directory.mkdir(mode=0o700)
    args, source = publication()
    assert fixture(directory, "seed", sources=[source])["status"] == "ok"
    assert fixture(directory, "lost_response", arguments=args)["reason"] == "worker_invalid_frame"
    first = invoke(directory, "vector_receipt", {"batch_key": "batch", "start_window": 0})
    assert first["status"] == "ok" and first["count"] == 1
    assert invoke(directory, "vector_publish", args) == first
    shared = {**args, "batch_key": "another"}
    assert invoke(directory, "vector_publish", shared)["receipt_id"] != first["receipt_id"]
    count = fixture(directory, "count")
    assert count["rows"] == 3
    assert not {"text", "tokens", "token_offsets"}.intersection(count["columns"])
    changed = copy.deepcopy(args)
    changed["inference"]["vectors"][0]["vector"] = [0.0, 1.0] + [0.0] * 382
    assert invoke(directory, "vector_publish", changed) == {"status": "conflict"}


@pytest.mark.skipif(sys.platform != "darwin", reason="owned guardian supervision")
@pytest.mark.parametrize(
    "damage", ["bad_vector", "bad_receipt", "missing_unit", "duplicate_receipt", "bad_schema"]
)
def test_corrupt_receipts_and_vectors_refuse_replay(tmp_path, damage):
    directory = tmp_path / "generation"
    directory.mkdir(mode=0o700)
    args, source = publication()
    assert fixture(directory, "seed", sources=[source])["status"] == "ok"
    assert invoke(directory, "vector_publish", args)["status"] == "ok"
    assert fixture(directory, damage)["status"] == "ok"
    assert invoke(directory, "vector_receipt", {"batch_key": "batch", "start_window": 0}) == {
        "status": "corrupt"
    }


@pytest.mark.skipif(sys.platform != "darwin", reason="owned guardian supervision")
def test_missing_stale_exact_source_refuses_without_creating_exact(tmp_path):
    directory = tmp_path / "generation"
    directory.mkdir(mode=0o700)
    args, source = publication()
    assert invoke(directory, "vector_publish", args)["status"] == "stale"
    assert not (directory / "exact").exists()
    assert fixture(directory, "seed", sources=[source])["status"] == "ok"
    args["references"][0]["exposure_hash"] = "f" * 64
    assert invoke(directory, "vector_publish", args) == {"status": "stale"}


@pytest.mark.skipif(sys.platform != "darwin", reason="owned guardian supervision")
def test_prefilter_full_scopes_grants_nonsemantic_and_pinned_generation(tmp_path):
    from cognitive_castle.semantic_profile import PROFILE_ID

    directory = tmp_path / "generation"
    directory.mkdir(mode=0o700)
    target = {"workspace": "workspace' OR true --", "wing": "wing'", "room": "room' OR 1=1"}
    authorized = None
    for key, vector, scope, marker in [
        ("blocked", [1.0] + [0.0] * 383, target, False),
        ("allowed", [0.0, 1.0] + [0.0] * 382, target, False),
        ("wrongscope", [1.0] + [0.0] * 383, SCOPE, False),
        ("marker", [1.0] + [0.0] * 383, target, True),
    ]:
        args, source = publication(key, key, vector, nonsemantic=marker, scope=scope)
        assert fixture(directory, "seed", sources=[source])["status"] == "ok"
        assert invoke(directory, "vector_publish", args)["status"] == "ok"
        if key == "allowed":
            authorized = args["references"][0]
    query = {
        "vector": [1.0] + [0.0] * 383,
        "profile": PROFILE_ID,
        "generation": 4,
        "scope": target,
        "allowed_source_hashes": [authorized["source_hash"]],
        "limit": 1,
    }
    result = invoke(directory, "vector_nearest", query)
    assert result["status"] == "ok", result
    assert (
        result["generation"] == 4
        and result["candidates"][0]["canonical_id"] == authorized["canonical_id"]
    )
    assert result["candidates"][0]["distance"] > 1
    assert (
        invoke(directory, "vector_nearest", {**query, "allowed_source_hashes": []})["candidates"]
        == []
    )
    assert (
        len(
            invoke(
                directory, "vector_nearest", {**query, "allowed_source_hashes": None, "limit": 100}
            )["candidates"]
        )
        == 2
    )
    assert invoke(directory, "vector_nearest", {**query, "generation": 3}) == {"status": "stale"}
    assert (
        invoke(directory, "vector_nearest", {**query, "profile": "f" * 64})["status"]
        == "unavailable"
    )


def test_host_native_imports_absent_and_unsupervised_store_refuses(tmp_path):
    from cognitive_castle.lance_vector_store import LanceVectorStore

    args, _ = publication()
    assert LanceVectorStore(tmp_path, writable=True).publish(**args) == {"status": "unavailable"}
    assert not {"lance", "pyarrow", "numpy", "pandas", "torch"}.intersection(sys.modules)


@pytest.mark.skipif(sys.platform != "darwin", reason="owned guardian supervision")
def test_entire_ordered_source_group_and_per_source_scopes_are_bound(tmp_path):
    from cognitive_castle.semantic_windows import page_units

    directory = tmp_path / "generation"
    directory.mkdir(mode=0o700)
    first, source1 = publication("group", "first")
    second, source2 = publication("group", "second", scope={**SCOPE, "room": "second room"})
    references = first["references"] + second["references"]
    envelopes = [
        {"source": source, "expected_hash": source["provenance"]["text_hash"]}
        for source in (source1, source2)
    ]
    page = page_units(envelopes, first["page"]["units"] + second["page"]["units"])
    inference = {
        **first["inference"],
        **{key: value for key, value in page.items() if key != "units"},
        "vectors": first["inference"]["vectors"] + second["inference"]["vectors"],
    }
    args = {"batch_key": "group", "references": references, "page": page, "inference": inference}
    assert fixture(directory, "seed", sources=[source1, source2])["status"] == "ok"
    result = invoke(directory, "vector_publish", args)
    assert result["status"] == "ok" and result["count"] == 2
    assert invoke(directory, "vector_publish", {**args, "references": references[::-1]}) == {
        "status": "stale"
    }
    changed = copy.deepcopy(args)
    changed["references"][1]["scope"]["room"] = "different trusted room"
    assert invoke(directory, "vector_publish", changed) == {"status": "conflict"}


def test_publication_rejects_duplicate_unit_records_within_page():
    from cognitive_castle.lance_vector_store import prepare_publication
    from cognitive_castle.semantic_windows import page_units

    args, source = publication()
    unit = args["page"]["units"][0]
    args["page"] = page_units(
        [{"source": source, "expected_hash": source["provenance"]["text_hash"]}], [unit, unit]
    )
    args["inference"].update({key: value for key, value in args["page"].items() if key != "units"})
    args["inference"]["vectors"] *= 2
    with pytest.raises(ValueError):
        prepare_publication(**args)


@pytest.mark.skipif(sys.platform != "darwin", reason="owned guardian supervision")
def test_first_page_binds_later_sources_and_complete_group_acknowledges_contiguously(tmp_path):
    from cognitive_castle.semantic_profile import digest
    from cognitive_castle.semantic_windows import make_unit, page_units
    from test_semantic_queue import registration

    directory = tmp_path / "generation"
    directory.mkdir(mode=0o700)
    first, source1 = publication("group", "x" * 40)
    second, source2 = publication("group", "later", scope={**SCOPE, "room": "later room"})
    references = first["references"] + second["references"]
    envelopes = [
        {"source": source, "expected_hash": source["provenance"]["text_hash"]}
        for source in (source1, source2)
    ]
    units = [
        make_unit(
            source1,
            index,
            index + 1,
            index,
            index + 1,
            {"input_ids": [0, 42, 2], "attention_mask": [1, 1, 1], "token_type_ids": [0, 0, 0]},
            [[0, 0], [index, index + 1], [0, 0]],
        )
        for index in range(32)
    ] + second["page"]["units"]
    page1 = page_units(envelopes, units)
    assert len({unit["canonical_id"] for unit in page1["units"]}) == 1
    inference = {
        **first["inference"],
        **{key: value for key, value in page1.items() if key != "units"},
        "vectors": [
            {"unit_id": unit["unit_id"], "vector": [1.0] + [0.0] * 383} for unit in page1["units"]
        ],
    }
    args = {"batch_key": "group", "references": references, "page": page1, "inference": inference}
    assert fixture(directory, "seed", sources=[source1])["status"] == "ok"
    assert invoke(directory, "vector_publish", args) == {"status": "stale"}
    assert fixture(directory, "seed", sources=[source2])["status"] == "ok"
    registered = {
        **registration("group"),
        "references": references,
        "input_binding": page1["input_binding"],
    }
    assert invoke(directory, "queue_register", registered)["status"] == "ok"
    first_receipt = invoke(directory, "vector_publish", args)
    assert first_receipt["reference_binding"] == digest(references)
    assert first_receipt["count"] == 32
    assert (
        invoke(directory, "queue_acknowledge", {"batch_key": "group", "receipt": first_receipt})[
            "position"
        ]
        == 32
    )
    page2 = page_units(envelopes, units, page1["next_continuation"])
    inference = {
        **first["inference"],
        **{key: value for key, value in page2.items() if key != "units"},
        "vectors": [
            {"unit_id": unit["unit_id"], "vector": [1.0] + [0.0] * 383} for unit in page2["units"]
        ],
    }
    second_receipt = invoke(
        directory, "vector_publish", {**args, "page": page2, "inference": inference}
    )
    assert second_receipt["count"] == 1
    assert (
        invoke(directory, "queue_acknowledge", {"batch_key": "group", "receipt": second_receipt})[
            "state"
        ]
        == "complete"
    )


def escaped_scope_publication():
    from cognitive_castle.semantic_windows import make_unit, page_units

    scope = {"workspace": "\x00" * 2048, "wing": "\x00" * 512, "room": "\x00" * 512}
    references, sources, units = [], [], []
    template = None
    for ordinal in range(8):
        template, source = publication("\x00" * 128, "source-" + str(ordinal), scope=scope)
        references.extend(template["references"])
        sources.append(source)
        for index in range(4):
            units.append(
                make_unit(
                    source,
                    index,
                    index + 1,
                    index,
                    index + 1,
                    {
                        "input_ids": [0, 42, 2],
                        "attention_mask": [1, 1, 1],
                        "token_type_ids": [0, 0, 0],
                    },
                    [[0, 0], [index, index + 1], [0, 0]],
                )
            )
    page = page_units(
        [
            {"source": source, "expected_hash": source["provenance"]["text_hash"]}
            for source in sources
        ],
        units,
    )
    inference = {
        **template["inference"],
        **{key: value for key, value in page.items() if key != "units"},
        "vectors": [{"unit_id": unit["unit_id"], "vector": [1.0] + [0.0] * 383} for unit in units],
    }
    return {
        "batch_key": "\x00" * 128,
        "references": references,
        "page": page,
        "inference": inference,
    }, sources


@pytest.mark.skipif(sys.platform != "darwin", reason="owned guardian supervision")
@pytest.mark.parametrize("lost_response", [False, True])
def test_maximally_escaped_scopes_publish_reopen_replay_and_lost_response(tmp_path, lost_response):
    from cognitive_castle.lance_vector_store import prepare_publication
    from cognitive_castle.semantic_profile import canonical_json

    directory = tmp_path / "generation"
    directory.mkdir(mode=0o700)
    args, sources = escaped_scope_publication()
    _, proof = prepare_publication(**args)
    assert len(canonical_json(proof).encode("utf-8")) > 49152
    assert fixture(directory, "seed", sources=sources)["status"] == "ok"
    if lost_response:
        assert (
            fixture(directory, "lost_response", arguments=args)["reason"] == "worker_invalid_frame"
        )
    else:
        assert invoke(directory, "vector_publish", args)["status"] == "ok"
    recovered = invoke(
        directory, "vector_receipt", {"batch_key": args["batch_key"], "start_window": 0}
    )
    assert recovered["status"] == "ok" and recovered["count"] == 32, recovered
    assert invoke(directory, "vector_publish", args) == recovered
    assert fixture(directory, "count")["rows"] == 33


def test_oversized_receipt_proof_rejects_before_storage(tmp_path):
    from cognitive_castle.lance_vector_store import _encode_proof, MAX_PROOF_BYTES

    with pytest.raises(ValueError):
        _encode_proof({"padding": "x" * MAX_PROOF_BYTES})


@pytest.mark.skipif(sys.platform != "darwin", reason="owned guardian supervision")
def test_oversized_precommit_proof_leaves_no_publication(tmp_path):
    directory = tmp_path / "generation"
    directory.mkdir(mode=0o700)
    args, _ = publication()
    assert fixture(directory, "oversized_proof", arguments=args) == {"status": "rejected"}
    assert list(directory.iterdir()) == []
