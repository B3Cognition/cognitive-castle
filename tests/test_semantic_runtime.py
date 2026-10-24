"""Coordinator behavior; native work remains in guarded disposable workers."""

import os
import sys

import pytest


@pytest.fixture(autouse=True)
def isolated_admission(monkeypatch, tmp_path):
    from cognitive_castle import memory_runtime

    monkeypatch.setattr(memory_runtime, "_admission_directory", lambda: tmp_path)


def test_shared_deadline_expiry_and_admission_release(monkeypatch, tmp_path):
    from cognitive_castle import semantic_runtime as runtime

    clock = [100.0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: clock[0])
    with runtime.SemanticSession(tmp_path / "profile.json") as session:
        clock[0] = 105.0
        assert session.tokenize([]) == {"status": "unavailable", "reason": "semantic_deadline"}
    fd = runtime.memory_runtime._admission()
    os.close(fd)


def test_background_yields_to_interactive_and_host_has_no_native_imports(monkeypatch, tmp_path):
    from cognitive_castle import semantic_runtime as runtime

    monkeypatch.setattr(runtime.memory_runtime, "interactive_waiting", lambda: True)
    with runtime.SemanticSession(tmp_path / "profile.json", interactive=False) as session:
        assert session.tokenize([])["reason"] == "memory_busy"
    assert not {"tokenizers", "numpy", "onnxruntime", "lancedb", "torch"} & sys.modules.keys()


def test_deadline_consumes_validation_and_both_stages(monkeypatch, tmp_path):
    from cognitive_castle import semantic_runtime as runtime
    from cognitive_castle.canonical_records import prepare_remember
    from cognitive_castle.semantic_windows import make_unit, page_units

    clock = [0.0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: clock[0])
    source = prepare_remember("fixture", "x").records[0].source()
    sources = [{"source": source, "expected_hash": source["provenance"]["text_hash"]}]
    unit = make_unit(
        source,
        0,
        1,
        0,
        1,
        {"input_ids": [0, 42, 2], "attention_mask": [1, 1, 1], "token_type_ids": [0, 0, 0]},
        [[0, 0], [0, 1], [0, 0]],
    )
    page = page_units(sources, [unit])
    deadlines = []

    def supervise(request, admission, **kwargs):
        deadlines.append(kwargs["deadline"])
        clock[0] += 2.0
        if request["operation"] == "tokenize":
            return page.copy()
        return {
            "status": "ok",
            "profile": page["profile"],
            "handoff_hash": page["handoff_hash"],
            "input_binding": page["input_binding"],
            "start_window": 0,
            "total_units": 1,
            "next_continuation": None,
            "complete": True,
            "vectors": [{"unit_id": unit["unit_id"], "vector": [1.0] + [0.0] * 383}],
            "runtime": {},
        }

    monkeypatch.setattr(runtime.memory_runtime, "_supervise", supervise)
    with runtime.SemanticSession(tmp_path / "profile.json") as session:
        result = session.tokenize(sources)
        assert session.infer(result)["status"] == "ok"
        clock[0] = 5.0
        assert session.infer(result)["reason"] == "semantic_deadline"
    assert deadlines == [5.0, 3.0]


def test_infer_rejects_unissued_handoff_and_malformed_worker_vector(monkeypatch, tmp_path):
    import pytest
    from cognitive_castle import semantic_runtime as runtime
    from cognitive_castle.canonical_records import prepare_remember
    from cognitive_castle.semantic_windows import make_unit, page_units

    source = prepare_remember("fixture", "x").records[0].source()
    sources = [{"source": source, "expected_hash": source["provenance"]["text_hash"]}]
    unit = make_unit(
        source,
        0,
        1,
        0,
        1,
        {"input_ids": [0, 42, 2], "attention_mask": [1, 1, 1], "token_type_ids": [0, 0, 0]},
        [[0, 0], [0, 1], [0, 0]],
    )
    page = page_units(sources, [unit])
    monkeypatch.setattr(
        runtime.memory_runtime,
        "_supervise",
        lambda request, fd, **kw: (
            page.copy() if request["operation"] == "tokenize" else {"status": "ok", "vectors": []}
        ),
    )
    with runtime.SemanticSession(tmp_path / "profile.json") as session:
        with pytest.raises(ValueError, match="unissued"):
            session.infer(page)
        session.tokenize(sources)
        assert session.infer(page) == {
            "status": "unavailable",
            "reason": "semantic_invalid_response",
        }


def test_success_arriving_after_absolute_deadline_is_unavailable(monkeypatch, tmp_path):
    from cognitive_castle import semantic_runtime as runtime
    from cognitive_castle.canonical_records import prepare_remember
    from cognitive_castle.semantic_windows import make_unit, page_units

    clock = [0.0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: clock[0])
    source = prepare_remember("fixture", "x").records[0].source()
    sources = [{"source": source, "expected_hash": source["provenance"]["text_hash"]}]
    unit = make_unit(
        source,
        0,
        1,
        0,
        1,
        {"input_ids": [0, 42, 2], "attention_mask": [1, 1, 1], "token_type_ids": [0, 0, 0]},
        [[0, 0], [0, 1], [0, 0]],
    )
    page = page_units(sources, [unit])

    def supervise(*args, **kwargs):
        clock[0] = 5.1
        return page.copy()

    monkeypatch.setattr(runtime.memory_runtime, "_supervise", supervise)
    with runtime.SemanticSession(tmp_path / "profile.json") as session:
        assert session.tokenize(sources) == {"status": "unavailable", "reason": "semantic_deadline"}


def test_tokenizer_response_must_bind_requested_source_set(monkeypatch, tmp_path):
    from cognitive_castle import semantic_runtime as runtime
    from cognitive_castle.canonical_records import prepare_remember
    from cognitive_castle.semantic_windows import make_unit, page_units

    records = [prepare_remember(name, name).records[0].source() for name in ("first", "other")]
    envelopes = [
        [{"source": source, "expected_hash": source["provenance"]["text_hash"]}]
        for source in records
    ]
    unit = make_unit(
        records[1],
        0,
        1,
        0,
        5,
        {"input_ids": [0, 42, 2], "attention_mask": [1, 1, 1], "token_type_ids": [0, 0, 0]},
        [[0, 0], [0, 5], [0, 0]],
    )
    wrong = page_units(envelopes[1], [unit])
    monkeypatch.setattr(runtime.memory_runtime, "_supervise", lambda *args, **kwargs: wrong.copy())
    with runtime.SemanticSession(tmp_path / "profile.json") as session:
        assert session.tokenize(envelopes[0]) == {
            "status": "unavailable",
            "reason": "semantic_invalid_response",
        }
