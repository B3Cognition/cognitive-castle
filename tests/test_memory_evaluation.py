"""Measure real bounded capture/recall without letting expected answers form queries."""

import hashlib
import importlib.util
import os
import json
from pathlib import Path

import pytest


def evaluator():
    path = Path(__file__).parents[1] / "scripts/bounded_memory_evaluation.py"
    assert path.exists(), "the bounded evidence evaluator is not implemented"
    spec = importlib.util.spec_from_file_location("bounded_memory_evaluation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(tmp_path, texts, question="What is the quasar storage contract?"):
    raw = "".join(texts).encode()
    source = tmp_path / "source.txt"
    source.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    spans, offset, line = [], 0, 1
    for index, text in enumerate(texts):
        value = text.encode()
        spans.append(
            {
                "evidence_id": f"e{index}",
                "source_id": "document",
                "source_path": str(source),
                "source_sha256": digest,
                "span_sha256": hashlib.sha256(value).hexdigest(),
                "byte_start_0based": offset,
                "byte_end_0based_exclusive": offset + len(value),
                "line_start_1based": line,
                "line_end_1based_inclusive": line + len(text.splitlines()) - 1,
                "quotation": text,
            }
        )
        offset += len(value)
        line += len(text.splitlines())
    return {
        "schema_version": 1,
        "sources": [{"source_id": "document", "path": str(source), "sha256": digest}],
        "evidence_spans": spans,
        "questions": [
            {
                "question_id": "q1",
                "question": question,
                "evidence_ids": [span["evidence_id"] for span in spans],
                "expected_evidence_relationships": ["e0 conflicts with e1"]
                if len(spans) > 1
                else [],
            }
        ],
    }


@pytest.mark.skipif(os.name != "posix", reason="evaluation requires private POSIX storage")
def test_public_evaluation_captures_exact_bytes_and_restores_completed_state(tmp_path):
    report = evaluator().evaluate(work_dir=tmp_path)
    assert report["dataset_kind"] == "public_synthetic_replay"
    assert report["historical_capture_demonstrated"] is False
    assert report["integrity"]["all_original_bytes_preserved"] is True
    assert report["restart"]["active_state_restored"] is True
    assert report["restart"]["completed_state_restored"] is True
    assert report["restart"]["unrelated_workspace_excluded"] is True
    assert report["capture"]["pending_bytes"] == 0
    assert report["capture"]["discovery"] == "not_established"
    assert report["max_response_bytes"] <= 8192
    assert all(row["returned_bytes"] <= 8192 for row in report["questions"])
    assert report["semantics"]["understanding_verified"] is False


@pytest.mark.parametrize("field", ["source_sha256", "span_sha256", "quotation"])
@pytest.mark.skipif(os.name != "posix", reason="evaluation requires private POSIX storage")
def test_fixture_tampering_is_rejected_before_replay(tmp_path, field):
    api = evaluator()
    value = fixture(tmp_path, ["quasar contract is exact.\n"])
    value["evidence_spans"][0][field] = "tampered"
    destination = tmp_path / "evaluation"
    with pytest.raises(ValueError, match="hash|quotation|source"):
        api.evaluate(value, work_dir=destination)
    assert not destination.exists(), "invalid evidence must not be ingested"


@pytest.mark.skipif(os.name != "posix", reason="evaluation requires private POSIX storage")
def test_fixture_requires_current_file_hash_and_exact_line_ranges(tmp_path):
    api = evaluator()
    value = fixture(tmp_path, ["quasar original.\n"])
    value["evidence_spans"][0]["line_end_1based_inclusive"] = 3
    with pytest.raises(ValueError, match="line"):
        api.verify_fixture(value)
    value = fixture(tmp_path, ["quasar original.\n"])
    (tmp_path / "source.txt").write_text("changed later\n")
    with pytest.raises(ValueError, match="hash"):
        api.verify_fixture(value)


@pytest.mark.skipif(os.name != "posix", reason="evaluation requires private POSIX storage")
def test_queries_use_only_the_question_not_expected_evidence(tmp_path):
    api = evaluator()
    value = fixture(tmp_path, ["oracle_secret never appears in this question.\n"])
    question = value["questions"][0]
    original = api.question_queries(question["question"])
    question["expected_answer"] = "oracle_secret"
    value["evidence_spans"][0]["quotation"] = "new_oracle_secret"
    assert api.question_queries(question["question"]) == original
    assert original == ["quasar", "storage", "contract"]
    assert "oracle" not in " ".join(original)


@pytest.mark.skipif(os.name != "posix", reason="evaluation requires private POSIX storage")
def test_missing_and_conflicting_spans_are_not_hidden_by_exact_storage(tmp_path):
    api = evaluator()
    value = fixture(
        tmp_path,
        ["quasar initial proposal.\n", "quasar corrected proposal.\n"],
        question="What does whollyabsent mean?",
    )
    report = api.evaluate(value, work_dir=tmp_path / "evaluation")
    row = report["questions"][0]
    assert report["integrity"]["all_original_bytes_preserved"] is True
    assert row["complete_evidence_recall_at_budget"] == 0
    assert row["missing_complete_evidence_ids"] == ["e0", "e1"]
    assert row["declared_tension_evidence_ids"] == ["e0", "e1"]
    assert row["missing_tension_evidence_ids"] == ["e0", "e1"]
    assert row["contradictions_resolved"] is False
    assert report["historical_capture_demonstrated"] is False


@pytest.mark.skipif(os.name != "posix", reason="evaluation requires private POSIX storage")
def test_large_unicode_span_is_preserved_but_not_claimed_fully_returned(tmp_path):
    api = evaluator()
    value = fixture(tmp_path, ["quasar " + '🙂\t"' * 1800 + "\n"])
    report = api.evaluate(value, work_dir=tmp_path / "evaluation")
    row = report["questions"][0]
    assert report["integrity"]["all_original_bytes_preserved"] is True
    assert row["complete_evidence_recall_at_budget"] == 0
    assert row["returned_bytes"] <= 8192
    assert report["restart"]["context_bytes"] <= 8192


@pytest.mark.skipif(os.name != "posix", reason="evaluation requires private POSIX storage")
def test_short_source_can_be_fully_recalled_without_oracle_query(tmp_path):
    report = evaluator().evaluate(
        fixture(tmp_path, ["quasar storage contract: retain exact originals.\n"]),
        work_dir=tmp_path / "evaluation",
    )
    row = report["questions"][0]
    assert row["complete_evidence_recall_at_budget"] == 1
    assert row["missing_complete_evidence_ids"] == []
    assert row["returned_bytes"] <= 8192


@pytest.mark.skipif(os.name != "posix", reason="evaluation requires private POSIX storage")
def test_private_cli_requires_file_output_and_does_not_echo_originals(tmp_path, capsys):
    api = evaluator()
    value = fixture(tmp_path, ["quasar unpublished-original-sentinel.\n"])
    input_path = tmp_path / "private-fixture.json"
    raw = json.dumps(value).encode()
    input_path.write_bytes(raw)
    with pytest.raises(SystemExit):
        api.main(["--fixture", str(input_path)])
    capsys.readouterr()
    output = tmp_path / "private-report.json"
    assert api.main(["--fixture", str(input_path), "--output", str(output)]) == 0
    assert capsys.readouterr().out == ""
    assert input_path.read_bytes() == raw
    assert output.stat().st_mode & 0o777 == 0o600
    assert "unpublished-original-sentinel" not in output.read_text()
    report = json.loads(output.read_text())
    assert report["dataset_kind"] == "private_selected_excerpt_replay"
    assert report["historical_capture_demonstrated"] is False


def operator_plan(value, queries):
    projection = [
        {"question_id": q["question_id"], "question": q["question"]} for q in value["questions"]
    ]
    return {
        "schema_version": 1,
        "profile": "bounded_operator_plan",
        "question_projection_sha256": hashlib.sha256(
            json.dumps(projection, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest(),
        "questions": [dict(q, queries=queries) for q in projection],
    }


@pytest.mark.skipif(os.name != "posix", reason="evaluation requires private POSIX storage")
def test_operator_profile_keeps_baseline_and_deduplicates_ranked_candidates(tmp_path):
    value = fixture(tmp_path, [f"quasar storage option {i}.\n" for i in range(6)])
    report = evaluator().evaluate(
        value,
        work_dir=tmp_path / "evaluation",
        query_plan=operator_plan(value, ["quasar", "storage"]),
    )
    baseline = report["questions"][0]
    profile = report["profiles"]["bounded_operator_plan"]
    row = profile["questions"][0]
    assert baseline["budget_bytes"] == 8192
    assert baseline["complete_evidence_recall_at_budget"] < 1
    assert row["queries"] == ["quasar", "storage"]
    assert row["complete_evidence_recall_at_budget"] == 1
    assert row["identifier_evidence_recall_at_budget"] == 1
    assert row["unique_candidates"] == 6
    assert row["duplicate_candidate_excerpts"] == 6
    assert row["recall_calls"] == 2
    assert row["page_calls"] == 0
    assert row["returned_bytes"] == sum(call["response_bytes"] for call in row["calls"])
    assert row["returned_bytes"] <= 32768
    assert all(call["response_bytes"] <= 8192 for call in row["calls"])
    assert all(call["limit"] == 8 for call in row["calls"])


@pytest.mark.skipif(os.name != "posix", reason="evaluation requires private POSIX storage")
def test_operator_profile_reports_partial_evidence_and_unissued_budgeted_queries(tmp_path):
    value = fixture(tmp_path, ["quasar " + '🙂\t"' * 1800 + "\n"])
    report = evaluator().evaluate(
        value,
        work_dir=tmp_path / "evaluation",
        query_plan=operator_plan(value, ["quasar", "storage"]),
        question_budget=8192,
    )
    row = report["profiles"]["bounded_operator_plan"]["questions"][0]
    assert row["identifier_evidence_recall_at_budget"] == 1
    assert row["complete_evidence_recall_at_budget"] == 0
    assert row["missing_complete_evidence_ids"] == ["e0"]
    assert row["unissued_queries"] == ["storage"]
    assert row["budget_exhausted"] is True
    assert row["page_calls"] > 0
    assert row["returned_bytes"] <= 8192
    assert all(call["response_bytes"] <= 8192 for call in row["calls"])
    assert all(call["limit"] <= 2048 for call in row["calls"] if call["kind"] == "page")


@pytest.mark.skipif(os.name != "posix", reason="evaluation requires private POSIX storage")
def test_operator_profile_uses_only_frozen_queries_even_when_expected_answers_change(tmp_path):
    value = fixture(tmp_path, ["quasar retained bytes.\n"], question="What is stored?")
    plan = operator_plan(value, ["whollyabsent"])
    value["questions"][0]["expected_answer"] = "quasar"
    report = evaluator().evaluate(value, work_dir=tmp_path / "evaluation", query_plan=plan)
    row = report["profiles"]["bounded_operator_plan"]["questions"][0]
    assert row["queries"] == ["whollyabsent"]
    assert row["identifier_evidence_recall_at_budget"] == 0
    assert row["complete_evidence_recall_at_budget"] == 0
    assert row["missing_identifier_evidence_ids"] == ["e0"]


@pytest.mark.parametrize("mutation", ["question", "digest", "too_many", "empty", "too_long"])
@pytest.mark.skipif(os.name != "posix", reason="evaluation requires private POSIX storage")
def test_invalid_operator_plan_is_rejected_before_replay(tmp_path, mutation):
    value = fixture(tmp_path, ["quasar retained bytes.\n"])
    plan = operator_plan(value, ["quasar"])
    if mutation == "question":
        plan["questions"][0]["question"] = "Different question"
    elif mutation == "digest":
        plan["question_projection_sha256"] = "incorrect"
    elif mutation == "too_many":
        plan["questions"][0]["queries"] *= 5
    elif mutation == "empty":
        plan["questions"][0]["queries"] = []
    else:
        plan["questions"][0]["queries"] = ["term " * 17]
    destination = tmp_path / "evaluation"
    with pytest.raises(ValueError, match="query plan"):
        evaluator().evaluate(value, work_dir=destination, query_plan=plan)
    assert not destination.exists()


@pytest.mark.skipif(os.name != "posix", reason="evaluation requires private POSIX storage")
def test_operator_plan_alone_requires_private_file_output(tmp_path, capsys):
    value = fixture(tmp_path, ["quasar retained bytes.\n"])
    path = tmp_path / "private-plan.json"
    path.write_text(json.dumps(operator_plan(value, ["quasar"])))
    with pytest.raises(SystemExit):
        evaluator().main(["--query-plan", str(path)])
    assert capsys.readouterr().out == ""


@pytest.mark.skipif(os.name != "posix", reason="evaluation requires private POSIX storage")
def test_operator_profile_keeps_native_rank_cap_visible_in_deficits(tmp_path):
    value = fixture(tmp_path, [f"quasar option {i}.\n" for i in range(9)])
    report = evaluator().evaluate(
        value,
        work_dir=tmp_path / "evaluation",
        query_plan=operator_plan(value, ["quasar"]),
    )
    row = report["profiles"]["bounded_operator_plan"]["questions"][0]
    assert row["unique_candidates"] == 8
    assert len(row["missing_identifier_evidence_ids"]) == 1
    assert len(row["missing_complete_evidence_ids"]) == 1
    assert row["budget_exhausted"] is False
    assert row["complete_evidence_recall_at_budget"] == 8 / 9


@pytest.mark.skipif(os.name != "posix", reason="evaluation requires private POSIX storage")
def test_expected_labels_do_not_select_paging_order(tmp_path):
    value = fixture(tmp_path, [f"quasar candidate {i} " + "x" * 900 + "\n" for i in range(3)])
    plan = operator_plan(value, ["quasar"])
    first = evaluator().evaluate(
        value, work_dir=tmp_path / "first1", query_plan=plan, question_budget=8192
    )["profiles"]["bounded_operator_plan"]["questions"][0]
    value["questions"][0]["evidence_ids"] = ["e2"]
    second = evaluator().evaluate(
        value, work_dir=tmp_path / "second", query_plan=plan, question_budget=8192
    )["profiles"]["bounded_operator_plan"]["questions"][0]
    assert first["unique_candidates"] == second["unique_candidates"] == 3
    assert first["complete_evidence_ids"] == ["e0"]
    assert second["complete_evidence_ids"] == []
    assert second["identified_but_incomplete_evidence_ids"] == ["e2"]
    assert first["page_calls"] == second["page_calls"]
    assert first["returned_bytes"] == second["returned_bytes"]


def test_evaluation_refuses_missing_privacy_primitives_before_writes(tmp_path, monkeypatch):
    evaluation = evaluator()
    destination = tmp_path / "must-not-exist"
    monkeypatch.delattr(evaluation.os, "O_NOFOLLOW", raising=False)
    with pytest.raises(ValueError, match="POSIX privacy"):
        evaluation.evaluate(work_dir=destination)
    assert not destination.exists()
