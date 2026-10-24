"""Metric definitions for the independently runnable actual-model pilot."""

import pytest
import importlib.util
from pathlib import Path


@pytest.fixture
def retrieval_metrics():
    source = Path(__file__).resolve().parents[2] / "benchmarks/memory_provider_bench.py"
    spec = importlib.util.spec_from_file_location("memory_provider_pilot", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.retrieval_metrics


def test_ndcg_normalizes_against_full_relevant_set(retrieval_metrics):
    metrics = retrieval_metrics(["a", "noise", "b"], {"a", "b", "c"}, k=5)
    assert metrics["recall_at_5"] == pytest.approx(2 / 3)
    assert metrics["mrr_at_5"] == 1.0
    assert metrics["recall_any"] == 1.0
    assert metrics["recall_all"] == 0.0
    assert metrics["precision_at_5"] == pytest.approx(2 / 5)
    assert metrics["ndcg_at_5"] == pytest.approx(1.5 / (1 + 1 / __import__("math").log2(3) + 0.5))


def test_unanswerable_questions_have_separate_abstention_measure(retrieval_metrics):
    metrics = retrieval_metrics(["irrelevant"], set(), k=5)
    assert metrics["recall_at_5"] is None
    assert metrics["mrr_at_5"] is None
    assert metrics["empty_for_unanswerable"] == 0.0


def test_duplicate_hits_cannot_inflate_recall(retrieval_metrics):
    assert retrieval_metrics(["a", "a"], {"a", "b"})["recall_at_5"] == 0.5


def test_optional_engine_guard_blocks_fromlist_imports():
    import subprocess
    import sys

    source = Path(__file__).resolve().parents[2] / "benchmarks/memory_provider_bench.py"
    script = f"""
import importlib.util
spec = importlib.util.spec_from_file_location("pilot", {str(source)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
attempts = module._forbid_network_and_optional_engines()
try:
    from cognitive_castle import soar_bridge
except ImportError:
    assert attempts["optional_import"]
else:
    raise AssertionError("fromlist import bypassed optional-engine guard")
"""
    run = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr


def test_v1_fixture_and_heldout_labels_are_frozen():
    import hashlib
    import json

    source = Path(__file__).resolve().parents[1] / "fixtures/memory_eval/coding_decisions_v1.json"
    data = source.read_bytes()
    assert (
        hashlib.sha256(data).hexdigest()
        == "96e8092bc96f7f1a46ff67072f59f19f59cbca3d1912aeadf83f91eb3726f111"
    )
    fixture = json.loads(data)
    docs = {doc["id"]: doc for doc in fixture["documents"]}
    questions = fixture["questions"]
    assert len(docs) == len(fixture["documents"]) == 36
    assert len({question["id"] for question in questions}) == 40
    assert sum(question["split"] == "dev" for question in questions) == 10
    assert sum(question["split"] == "heldout" for question in questions) == 30
    for question in questions:
        assert (question["kind"] == "unanswerable") == (not question["relevant"])
        assert all(
            docs[rid].get("wing", "atlas") in fixture["allowed_wings"]
            for rid in question["relevant"]
        )
