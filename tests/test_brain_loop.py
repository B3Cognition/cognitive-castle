"""Synthetic, bounded, offline persistence and controller contract tests."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from test_brain_engine import CLAIM, SOURCE, answer


def begin(loop, request_id="begin", **kw):
    return loop.begin(
        request_id,
        SOURCE,
        CLAIM,
        [{"id": "s1", "text": SOURCE, "provenance": {"issuer": "caller"}}],
        [
            {
                "id": "roles",
                "text": SOURCE.splitlines()[0],
                "source_id": "problem",
                "start": 0,
                "end": len(SOURCE.splitlines()[0]),
            }
        ],
        **kw,
    )


@pytest.fixture
def loop(tmp_path):
    from cognitive_castle.brain_loop import BrainLoop

    return BrainLoop(tmp_path / "controller")


def test_begin_returns_action_and_restart_pages(tmp_path, loop):
    from cognitive_castle.brain_loop import BrainLoop

    state = begin(loop)
    assert state["execution_state"] == "awaiting_response"
    assert state["next_action"]["operator"] == "DEFINE"
    assert state["independent_checks"] == "not_performed"
    restored = BrainLoop(tmp_path / "controller").status(state["session_id"])
    assert restored["revision"] == state["revision"]
    page = loop.page(state["session_id"], "sources")
    assert json.loads(page["text"])[0]["text"] == SOURCE
    assert "caller_attributed" in page["text"]


def test_two_questions_do_not_close_via_engine_addresses(loop):
    state = begin(loop)
    state = loop.respond(
        state["session_id"],
        "r1",
        state["revision"],
        answer("DEFINE", open_questions=["Which roles?", "When does consent expire?"]),
    )
    state = loop.respond(
        state["session_id"], "r2", state["revision"], answer("DISTINGUISH", addresses=[1])
    )
    assert state["counts"]["open_issues"] == 2
    assert "expiry" not in json.dumps(state)  # issue content is paged
    issues = json.loads(loop.page(state["session_id"], "issues")["text"])
    assert len({i["id"] for i in issues}) == 2


def test_idempotent_invalid_replay_then_second_invalid_stops(loop):
    state = begin(loop)
    sid, revision = state["session_id"], state["revision"]
    first = loop.respond(sid, "bad1", revision, {})
    retry = loop.respond(sid, "bad1", revision, {})
    assert retry["operation"] == first["operation"]
    assert retry["revision"] == first["revision"]
    second = loop.respond(sid, "bad2", first["revision"], {"bad": "other"})
    assert second["execution_state"] == "terminal"
    assert second["engine_terminal"] == "BOUNDED_STOP"
    assert second["budgets"]["accepted_turns"] == 0
    late = loop.respond(sid, "late", second["revision"], answer("DEFINE"))
    assert late["status"] == "inactive"


def test_replay_after_cancel_is_current_and_content_free(loop):
    state = begin(loop)
    sid, rev = state["session_id"], state["revision"]
    state = loop.respond(sid, "r1", rev, answer("DEFINE"))
    loop.cancel(sid, "cancel", state["revision"])
    replay = loop.respond(sid, "r1", rev, answer("DEFINE"))
    assert replay["operation"]["disposition"] == "accepted"
    assert replay["execution_state"] == "cancelled"
    assert replay["advisory"] != "proceed_with_limits"
    assert replay["next_action"] is None


def test_same_request_different_payload_conflicts_without_turn(loop):
    state = begin(loop)
    sid, rev = state["session_id"], state["revision"]
    loop.respond(sid, "same", rev, answer("DEFINE"))
    conflict = loop.respond(sid, "same", rev, {})
    assert conflict["status"] == "request_conflict"
    assert conflict["budgets"]["accepted_turns"] == 1


def test_two_concurrent_responses_commit_exactly_one(loop):
    state = begin(loop)
    barrier = Barrier(2)

    def respond(i):
        barrier.wait()
        return loop.respond(state["session_id"], f"race{i}", state["revision"], answer("DEFINE"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(respond, range(2)))
    assert sorted(r["status"] for r in results) == ["ok", "revision_conflict"]
    assert loop.status(state["session_id"])["budgets"]["accepted_turns"] == 1


def test_successor_keeps_obligations_and_slots_correction_invalidates(loop):
    state = begin(loop)
    child = begin(
        loop,
        "child",
        parent_id=state["session_id"],
        expected_revision=state["revision"],
        revision_reason="Clarification",
    )
    assert child["budgets"]["examinations_remaining"] == 0
    assert loop.status(state["session_id"])["execution_state"] == "superseded"
    exhausted = begin(
        loop,
        "third",
        parent_id=child["session_id"],
        expected_revision=child["revision"],
        revision_reason="Another clarification",
    )
    assert exhausted["status"] == "examination_budget_exhausted"
    correction = loop.correct(child["session_id"], "fix", child["revision"], "Consent was revoked.")
    assert correction["freshness"] == "known_stale"
    assert correction["next_action"] is None


def test_revocation_and_purge_block_all_source_bearing_pages(tmp_path):
    from cognitive_castle.brain_loop import BrainLoop

    policy = {"allow_local_sources": True, "policy_epoch": "one"}
    loop = BrainLoop(tmp_path / "state", exposure_policy=lambda: policy)
    state = loop.begin(
        "b",
        "Review",
        "Claim",
        [{"id": "secret", "text": "A private secret.", "provenance": {"local_only": True}}],
        [],
    )
    page = loop.page(state["session_id"], "sources")
    source_hash = json.loads(page["text"])[0]["hash"]
    policy.update(allow_local_sources=False, policy_epoch="two")
    denied = loop.page(state["session_id"], "sources")
    assert denied["status"] == "exposure_denied" and "private" not in json.dumps(denied)
    replay = loop.begin(
        "b",
        "Review",
        "Claim",
        [{"id": "secret", "text": "A private secret.", "provenance": {"local_only": True}}],
        [],
    )
    assert replay["status"] == "exposure_denied"
    policy.update(allow_local_sources=True, policy_epoch="three")
    loop.purge_source(source_hash)
    assert "private" not in json.dumps(loop.page(state["session_id"], "events"))
    assert loop.status(state["session_id"])["freshness"] == "known_stale"


def test_limits_and_obligation_spans_fail_before_mutation(loop):
    with pytest.raises(ValueError):
        loop.begin("bad", "x" * 8193, CLAIM, [], [])
    with pytest.raises(ValueError):
        loop.begin(
            "bad",
            SOURCE,
            CLAIM,
            [],
            [{"id": "wrong", "text": "invented", "source_id": "problem", "start": 0, "end": 8}],
        )
    with pytest.raises(ValueError):
        begin(loop, "bad", protocol_version=True)
    assert begin(loop)["revision"] == 1


def test_automatic_budget_cannot_be_bypassed_by_false_flag(loop):
    state = begin(loop)
    for _ in range(63):
        loop.status(state["session_id"], automatic=False)
    stopped = loop.status(state["session_id"])
    assert stopped["status"] == "request_budget_exhausted"
    cancelled = loop.cancel(state["session_id"], "c", state["revision"])
    assert cancelled["execution_state"] == "cancelled"


def test_busy_and_corrupt_storage_are_fail_closed(tmp_path, loop):
    state = begin(loop)
    db = sqlite3.connect(tmp_path / "controller" / "brain.sqlite3")
    db.execute("BEGIN IMMEDIATE")
    try:
        assert (
            loop.respond(state["session_id"], "r", state["revision"], answer("DEFINE"))["status"]
            == "busy"
        )
    finally:
        db.rollback()
        db.close()
    (tmp_path / "controller" / "brain.sqlite3").write_bytes(b"not a database")
    assert loop.status(state["session_id"])["status"] == "corrupt"


def test_ledger_invalid_submission_leaves_no_partial_artifacts(loop):
    state = begin(loop)
    before = loop.page(state["session_id"], "commitments")["text"]
    state = loop.respond(
        state["session_id"],
        "badledger",
        state["revision"],
        answer("DEFINE"),
        commitment_map=[{"obligation_id": "roles", "change": "retained", "reason": "Included"}],
        dispositions=[{}],
    )
    assert state["status"] == "invalid_response"
    assert loop.page(state["session_id"], "commitments")["text"] == before
    assert state["counts"]["unrepresented_obligations"] == 1


def test_explicit_item_disposition_closes_one_question_only(loop):
    import hashlib

    state = begin(loop)
    state = loop.respond(
        state["session_id"],
        "r1",
        state["revision"],
        answer("DEFINE", open_questions=["Which roles?", "When does consent expire?"]),
    )
    issues = json.loads(loop.page(state["session_id"], "issues")["text"])
    quote = SOURCE.splitlines()[0]
    disposition = {
        "issue_id": issues[0]["id"],
        "status": "attributed_answer",
        "reason": "The cited line names administrators.",
        "author": "active_host",
        "claim_version": 1,
        "dependencies": [hashlib.sha256(SOURCE.encode()).hexdigest()],
        "citations": [{"source_id": "s1", "start": 0, "end": len(quote), "quote": quote}],
    }
    state = loop.respond(
        state["session_id"],
        "r2",
        state["revision"],
        answer("DISTINGUISH", addresses=[1]),
        dispositions=[disposition],
    )
    assert state["counts"]["open_issues"] == 1
    assert state["independent_checks"] == "not_performed"


def test_missing_map_rejects_revision_and_never_drops_obligation(loop):
    state = begin(loop)
    rejected = loop.respond(
        state["session_id"], "r1", state["revision"], answer("DEFINE", claim="Everyone may export.")
    )
    assert rejected["status"] == "invalid_response"
    assert rejected["counts"]["obligations"] == 1
    assert rejected["budgets"]["accepted_turns"] == 0


def test_old_page_cursor_cannot_cross_revision_or_exposure_epoch(loop):
    state = begin(loop)
    page = loop.page(state["session_id"], "sources", limit=32)
    assert page["cursor"]
    state = loop.respond(state["session_id"], "r1", state["revision"], answer("DEFINE"))
    continuation = loop.page(
        state["session_id"], "sources", offset=page["next_offset"], limit=32, cursor=page["cursor"]
    )
    assert continuation["status"] == "stale_cursor"
    assert "text" not in continuation


def test_selected_grant_does_not_authorize_successor_expansion(tmp_path):
    from cognitive_castle.brain_loop import BrainLoop

    from cognitive_castle.brain_loop import source_exposure_hash

    permitted_hash = source_exposure_hash(
        {"id": "local", "text": "allowed", "provenance": {"local_only": True}}
    )
    loop = BrainLoop(
        tmp_path / "state",
        exposure_policy={
            "allow_local_sources": False,
            "policy_epoch": "1",
            "allowed_source_hashes": [permitted_hash],
        },
    )
    sources = [{"id": "local", "text": "allowed", "provenance": {"local_only": True}}]
    first = loop.begin("b", "Review", "Claim", sources, [])
    assert first["status"] == "ok"
    second = loop.begin(
        "s",
        "Review",
        "Claim",
        sources + [{"id": "new", "text": "not granted", "provenance": {"local_only": True}}],
        [],
        parent_id=first["session_id"],
        expected_revision=first["revision"],
        revision_reason="More context",
    )
    assert second["status"] == "exposure_denied"
    assert "not granted" not in json.dumps(second)


def test_expiry_and_backward_clock_resume_retains_budgets(tmp_path):
    from cognitive_castle.brain_loop import BrainLoop

    now = [10000.0]
    loop = BrainLoop(tmp_path / "state", clock=lambda: now[0])
    state = begin(loop)
    now[0] -= 1
    expired = loop.respond(state["session_id"], "r1", state["revision"], answer("DEFINE"))
    assert expired["execution_state"] == "expired"
    resumed = loop.resume(state["session_id"], "resume", state["revision"])
    assert resumed["budgets"]["accepted_turns"] == 0
    assert resumed["budgets"]["examinations_remaining"] == 1
    now[0] += 1801
    assert loop.status(state["session_id"])["execution_state"] == "expired"


def test_version_change_allows_bounded_inspection_but_no_response(loop, tmp_path):
    state = begin(loop)
    db = sqlite3.connect(tmp_path / "controller" / "brain.sqlite3")
    db.execute("UPDATE metadata SET value='{}' WHERE key='pins'")
    db.commit()
    db.close()
    result = loop.respond(state["session_id"], "r1", state["revision"], answer("DEFINE"))
    assert result["execution_state"] == "incompatible"
    assert result["budgets"]["accepted_turns"] == 0
    assert json.loads(loop.page(state["session_id"], "problem")["text"]) == SOURCE


def test_symlink_store_fails_without_touching_target(tmp_path):
    from cognitive_castle.brain_loop import BrainLoop

    target = tmp_path / "target"
    target.mkdir()
    path = tmp_path / "link"
    path.symlink_to(target)
    with pytest.raises(ValueError):
        BrainLoop(path)
    assert list(target.iterdir()) == []


def test_committed_receipts_contain_no_response_or_source_text(loop, tmp_path):
    state = begin(loop)
    loop.respond(state["session_id"], "r1", state["revision"], answer("DEFINE"))
    db = sqlite3.connect(tmp_path / "controller" / "brain.sqlite3")
    rows = db.execute("SELECT * FROM receipts").fetchall()
    db.close()
    assert len(rows) == 2 and SOURCE not in str(rows) and CLAIM not in str(rows)


def test_prospective_artifact_exhaustion_stops_before_accepting(loop, monkeypatch):
    from cognitive_castle import brain_loop

    state = begin(loop)
    monkeypatch.setattr(brain_loop, "MAX_SESSION_BYTES", 17000)
    result = loop.respond(state["session_id"], "r1", state["revision"], answer("DEFINE"))
    assert result["status"] == "artifact_budget_exhausted"
    assert result["engine_terminal"] == "BOUNDED_STOP"
    assert result["budgets"]["accepted_turns"] == 0


def test_successor_freezes_original_request_and_keeps_original_spans(loop):
    state = begin(loop)
    child = loop.begin(
        "child",
        "Only a prototype now.",
        CLAIM,
        [{"id": "s1", "text": SOURCE, "provenance": {}}],
        [],
        parent_id=state["session_id"],
        expected_revision=state["revision"],
        revision_reason="Narrowed proposal",
    )
    frozen = json.loads(loop.page(child["session_id"], "problem")["text"])
    assert frozen == SOURCE
    assert child["counts"]["obligations"] == 2
    assert child["counts"]["open_issues"] >= 1


def test_unrepresented_request_remains_visible_despite_resolved_engine(loop):
    from cognitive_castle._vendor.sue import sue_dialectic

    state = begin(loop)
    for number, op in enumerate(sue_dialectic.LENSES["euthyphro"]["path"]):
        state = loop.respond(
            state["session_id"],
            f"t{number}",
            state["revision"],
            answer(op),
            commitment_map=[
                {"obligation_id": "roles", "change": "retained", "reason": "Role retained"}
            ]
            if number == 0
            else None,
        )
    assert state["engine_terminal"] == "RESOLVED"
    assert state["advisory"] != "proceed_with_limits"
    assert state["coverage"]["unrepresented_request_ranges"]


def test_full_represented_request_resolves_with_explicit_limits(loop):
    from cognitive_castle._vendor.sue import sue_dialectic

    state = loop.begin(
        "b",
        SOURCE,
        CLAIM,
        [{"id": "s1", "text": SOURCE, "provenance": {}}],
        [{"id": "all", "text": SOURCE, "source_id": "problem", "start": 0, "end": len(SOURCE)}],
    )
    for number, op in enumerate(sue_dialectic.LENSES["euthyphro"]["path"]):
        state = loop.respond(
            state["session_id"],
            f"t{number}",
            state["revision"],
            answer(op),
            commitment_map=[
                {
                    "obligation_id": "all",
                    "change": "retained",
                    "reason": "Both role and consent retained",
                }
            ]
            if number == 0
            else None,
        )
    assert state["engine_terminal"] == "RESOLVED"
    assert state["advisory"] == "proceed_with_limits"
    assert state["independent_checks"] == "not_performed"


def test_collection_excess_stops_instead_of_silently_dropping_issues(loop):
    state = begin(loop)
    result = loop.respond(
        state["session_id"],
        "r1",
        state["revision"],
        answer("DEFINE", open_questions=[f"Gap {n}?" for n in range(129)]),
    )
    assert result["status"] == "collection_budget_exhausted"
    assert result["engine_terminal"] == "BOUNDED_STOP"
    assert result["budgets"]["accepted_turns"] == 0


def test_original_request_is_a_citable_source_with_other_evidence(loop):
    state = begin(loop)
    mapping = json.loads(loop.page(state["session_id"], "source_map")["text"])
    assert any(line["source_id"] == "problem" for line in mapping)


def test_storage_commit_failure_never_acknowledges_success(loop, monkeypatch):
    state = begin(loop)
    original = loop._open

    class FailingCommit:
        def __init__(self, db):
            self.db = db

        def __getattr__(self, name):
            return getattr(self.db, name)

        def commit(self):
            raise sqlite3.OperationalError("disk full")

    with monkeypatch.context() as patch:
        patch.setattr(loop, "_open", lambda: FailingCommit(original()))
        result = loop.respond(state["session_id"], "r1", state["revision"], answer("DEFINE"))
    assert result["status"] == "storage_unavailable"
    restored = loop.status(state["session_id"])
    assert restored["revision"] == state["revision"]
    assert restored["budgets"]["accepted_turns"] == 0
    retry = loop.respond(state["session_id"], "r1", state["revision"], answer("DEFINE"))
    assert retry["budgets"]["accepted_turns"] == 1


def test_trusted_inspection_still_works_after_automatic_cap(loop):
    state = begin(loop)
    for _ in range(63):
        loop.status(state["session_id"])
    assert loop.status(state["session_id"])["status"] == "request_budget_exhausted"
    assert loop.inspect(state["session_id"])["budgets"]["automatic_requests_used"] == 64
    page = loop.inspect(state["session_id"], kind="problem")
    assert json.loads(page["text"]) == SOURCE


def test_successor_race_reserves_only_one_slot(loop):
    state = begin(loop)
    barrier = Barrier(2)

    def make_child(number):
        barrier.wait()
        return begin(
            loop,
            f"child{number}",
            parent_id=state["session_id"],
            expected_revision=state["revision"],
            revision_reason="New examination",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(make_child, range(2)))
    assert sorted(r["status"] for r in results) == ["ok", "revision_conflict"]
    winner = next(r for r in results if r["status"] == "ok")
    assert winner["budgets"]["examinations_remaining"] == 0


def test_cancel_response_race_never_reactivates_cancelled_session(loop):
    state = begin(loop)
    barrier = Barrier(2)

    def run(operation):
        barrier.wait()
        if operation == "cancel":
            return loop.cancel(state["session_id"], "cancel", state["revision"])
        return loop.respond(state["session_id"], "reply", state["revision"], answer("DEFINE"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, ["cancel", "response"]))
    assert sum(r["status"] == "ok" for r in results) == 1
    current = loop.status(state["session_id"])
    if current["execution_state"] != "cancelled":
        current = loop.cancel(state["session_id"], "cancel-again", current["revision"])
    late = loop.respond(state["session_id"], "late", current["revision"], answer("DEFINE"))
    assert late["execution_state"] == "cancelled"
    assert late["next_action"] is None


@pytest.mark.parametrize("boundary", ["receipt", "after_commit"])
def test_process_crash_exposes_complete_old_or_new_state(loop, tmp_path, boundary):
    import subprocess
    import sys
    from pathlib import Path

    state = begin(loop)
    script = """
import importlib.abc, json, os, socket, sys
class NoModels(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch','transformers','sentence_transformers','spacy'}:
            raise ImportError('models forbidden')
sys.meta_path.insert(0, NoModels())
def deny(*a, **k):
    raise RuntimeError('network forbidden')
socket.socket.connect = deny
socket.create_connection = deny
sys.path.insert(0, sys.argv[1])
from cognitive_castle.brain_loop import BrainLoop
loop = BrainLoop(sys.argv[2])
if sys.argv[3] == 'receipt':
    original = loop._receipt
    def stop(*a, **k):
        original(*a, **k)
        os._exit(73)
    loop._receipt = stop
payload = json.loads(sys.argv[4])
loop.respond(payload['sid'], 'crash', payload['revision'], payload['answer'])
os._exit(74)
"""
    payload = json.dumps(
        {"sid": state["session_id"], "revision": state["revision"], "answer": answer("DEFINE")}
    )
    child = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            script,
            str(Path(__file__).parents[1]),
            str(tmp_path / "controller"),
            boundary,
            payload,
        ],
        timeout=5,
        capture_output=True,
    )
    assert child.returncode == (73 if boundary == "receipt" else 74), child.stderr.decode()
    restored = loop.status(state["session_id"])
    assert restored["budgets"]["accepted_turns"] == (0 if boundary == "receipt" else 1)
    replay = loop.respond(state["session_id"], "crash", state["revision"], answer("DEFINE"))
    assert replay["budgets"]["accepted_turns"] == 1


def test_missing_committed_event_is_corrupt_not_ready(loop, tmp_path):
    state = begin(loop)
    state = loop.respond(state["session_id"], "r1", state["revision"], answer("DEFINE"))
    db = sqlite3.connect(tmp_path / "controller" / "brain.sqlite3")
    db.execute("DELETE FROM artifacts WHERE kind='events'")
    db.commit()
    db.close()
    assert loop.status(state["session_id"])["status"] == "corrupt"


def test_purge_problem_hash_prevents_reintroduction_as_a_new_root(loop):
    import hashlib

    begin(loop)
    loop.purge_source(hashlib.sha256(SOURCE.encode()).hexdigest())
    denied = loop.begin("new", SOURCE, CLAIM, [], [])
    assert denied["status"] == "source_purged"


def test_many_quoted_unicode_pages_fit_actual_mcp_envelope(loop):
    from cognitive_castle import brain_loop

    source = '\\"😀' * 3000
    state = loop.begin("b", "Request", "Claim", [{"id": "s", "text": source, "provenance": {}}], [])
    chunks, offset, cursor = [], 0, None
    for _ in range(16):
        page = loop.page(state["session_id"], "sources", offset=offset, limit=4096, cursor=cursor)
        wire = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"type": "text", "text": brain_loop._json(page)}]},
        }
        assert len(brain_loop._json(wire).encode()) <= 32768
        chunks.append(page["text"])
        offset, cursor = page["next_offset"], page["cursor"]
        if offset is None:
            break
    assert json.loads("".join(chunks))[0]["text"] == source


def test_withdrawn_premise_cannot_erase_a_question_without_evidence(loop):
    state = begin(loop)
    state = loop.respond(
        state["session_id"],
        "r1",
        state["revision"],
        answer("DEFINE", open_questions=["When does consent expire?"]),
    )
    issue = json.loads(loop.page(state["session_id"], "issues")["text"])[0]
    disposition = {
        "issue_id": issue["id"],
        "status": "withdrawn_premise",
        "reason": "Ignore it",
        "author": "host",
        "claim_version": 1,
        "dependencies": [],
        "citations": [],
    }
    result = loop.respond(
        state["session_id"],
        "r2",
        state["revision"],
        answer("DISTINGUISH"),
        dispositions=[disposition],
    )
    assert result["status"] == "invalid_response"
    assert result["counts"]["open_issues"] == 1


def test_changed_claim_reopens_individually_answered_dependency(loop):
    import hashlib

    state = begin(loop)
    state = loop.respond(
        state["session_id"],
        "d",
        state["revision"],
        answer("DEFINE", open_questions=["Which role?"]),
    )
    issue = json.loads(loop.page(state["session_id"], "issues")["text"])[0]
    quote = SOURCE.splitlines()[0]
    disposition = {
        "issue_id": issue["id"],
        "status": "attributed_answer",
        "reason": "Role cited",
        "author": "host",
        "claim_version": 1,
        "dependencies": [hashlib.sha256(SOURCE.encode()).hexdigest()],
        "citations": [{"source_id": "s1", "start": 0, "end": len(quote), "quote": quote}],
    }
    state = loop.respond(
        state["session_id"],
        "dist",
        state["revision"],
        answer("DISTINGUISH", addresses=[1]),
        dispositions=[disposition],
    )
    assert state["counts"]["open_issues"] == 0
    for number in range(8):
        op = state["next_action"]["operator"]
        if op == "COUNTEREXAMPLE":
            break
        state = loop.respond(state["session_id"], f"step{number}", state["revision"], answer(op))
    state = loop.respond(
        state["session_id"], "counter", state["revision"], answer("COUNTEREXAMPLE", "FOUND")
    )
    state = loop.respond(
        state["session_id"],
        "revise",
        state["revision"],
        answer(
            "REVISE",
            addresses=list(range(1, state["budgets"]["accepted_turns"] + 1)),
            revision_reason="Narrow the interpreted claim.",
        ),
        commitment_map=[
            {
                "obligation_id": "roles",
                "change": "retained",
                "reason": "Keep original role requirement",
            }
        ],
    )
    assert state["counts"]["open_issues"] >= 2
    issues = json.loads(loop.page(state["session_id"], "issues")["text"])
    assert next(i for i in issues if i["id"] == issue["id"])["status"] == "reopened"


@pytest.mark.parametrize("kind", ["question", "schema"])
def test_incompatible_engine_cannot_regenerate_historical_prompt(loop, tmp_path, kind):
    state = begin(loop)
    db = sqlite3.connect(tmp_path / "controller" / "brain.sqlite3")
    db.execute("UPDATE metadata SET value='{}' WHERE key='pins'")
    db.commit()
    db.close()
    result = loop.page(state["session_id"], kind)
    assert result["status"] == "incompatible"
    assert "text" not in result


def test_same_exact_task_cannot_mint_new_root_budget_after_restart(loop, tmp_path):
    from cognitive_castle.brain_loop import BrainLoop

    first = begin(loop)
    child = begin(
        loop,
        "successor",
        parent_id=first["session_id"],
        expected_revision=first["revision"],
        revision_reason="Re-examine same task",
    )
    restored = BrainLoop(tmp_path / "controller")
    reused = begin(restored, "fresh-uuid")
    assert reused["status"] == "existing_task"
    assert reused["session_id"] == child["session_id"]
    assert reused["root_id"] == first["root_id"]
    assert reused["budgets"]["examinations_remaining"] == 0
    replayed = begin(restored, "fresh-uuid")
    assert replayed["operation"] == reused["operation"]


def test_native_json_bounds_reject_aggregate_before_serializing(monkeypatch):
    from cognitive_castle import brain_loop

    payload = {"repeated": ["x" * 1024] * 8}

    def forbidden(*args, **kwargs):
        raise AssertionError("oversized aggregate reached serialization")

    monkeypatch.setattr(brain_loop, "_bytes", forbidden)
    with pytest.raises(ValueError, match="limit"):
        brain_loop._bounded(payload, 4096)


def test_native_json_bounds_reject_cycles_and_shared_graph_expansion():
    from cognitive_castle import brain_loop

    cycle = []
    cycle.append(cycle)
    with pytest.raises(ValueError):
        brain_loop._bounded(cycle, 4096)
    repeated = ["x" * 32]
    for _ in range(3):
        repeated = [repeated] * 16
    with pytest.raises(ValueError):
        brain_loop._bounded(repeated, 4096)


def test_trusted_wire_fingerprint_replays_without_resnapshotting(loop):
    fingerprint = "a" * 64
    assert loop.replay("archive-begin", fingerprint) is None
    first = begin(loop, "archive-begin", request_fingerprint=fingerprint)
    replayed = loop.replay("archive-begin", fingerprint)
    assert replayed["operation"] == first["operation"]
    assert replayed["budgets"]["automatic_requests_used"] == 2
    changed_snapshot = loop.begin(
        "archive-begin",
        SOURCE,
        CLAIM,
        [{"id": "s1", "text": "Archive changed after acceptance.", "provenance": {}}],
        [],
        request_fingerprint=fingerprint,
    )
    assert changed_snapshot["operation"] == first["operation"]
    assert changed_snapshot["session_id"] == first["session_id"]
    assert json.loads(loop.page(first["session_id"], "sources")["text"])[0]["text"] == SOURCE
    conflict = loop.replay("archive-begin", "b" * 64)
    assert conflict["status"] == "request_conflict"


def test_trusted_wire_replay_uses_current_revocation_cancel_and_purge(tmp_path):
    import hashlib
    from cognitive_castle.brain_loop import BrainLoop

    policy = {"allow_local_sources": True, "policy_epoch": "1"}
    loop = BrainLoop(tmp_path / "state", exposure_policy=lambda: policy)
    fingerprint = "c" * 64
    first = loop.begin(
        "b",
        "Review archive",
        "Claim",
        [{"id": "local", "text": "Secret source", "provenance": {"local_only": True}}],
        [],
        request_fingerprint=fingerprint,
    )
    policy.update(allow_local_sources=False, policy_epoch="2")
    denied = loop.replay("b", fingerprint)
    assert denied["status"] == "exposure_denied"
    assert "Secret source" not in json.dumps(denied)
    policy.update(allow_local_sources=True, policy_epoch="3")
    loop.cancel(first["session_id"], "cancel", first["revision"])
    cancelled = loop.replay("b", fingerprint)
    assert cancelled["execution_state"] == "cancelled" and cancelled["next_action"] is None
    loop.purge_source(hashlib.sha256(b"Secret source").hexdigest())
    purged = loop.replay("b", fingerprint)
    assert purged["status"] == "source_purged"
    assert purged["operation"] == first["operation"]


@pytest.mark.parametrize("fingerprint", [True, "short", "g" * 64, "A" * 64, []])
def test_trusted_fingerprint_rejects_malformed_values_before_mutation(loop, fingerprint):
    with pytest.raises(ValueError):
        loop.replay("b", fingerprint)
    with pytest.raises(ValueError):
        begin(loop, request_fingerprint=fingerprint)
    assert begin(loop)["revision"] == 1


def test_concurrent_same_wire_fingerprint_commits_one_snapshot(loop):
    barrier = Barrier(2)

    def submit(number):
        barrier.wait()
        return loop.begin(
            "archive-begin",
            "Same original request",
            CLAIM,
            [{"id": "s", "text": f"Archive version {number}", "provenance": {}}],
            [],
            request_fingerprint="d" * 64,
        )

    # Initialize the schema so this specifically exercises receipt concurrency.
    assert loop.replay("absent", "d" * 64) is None
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(submit, range(2))
    assert first["operation"] == second["operation"]
    assert first["session_id"] == second["session_id"]
    assert (
        first["budgets"]["examinations_remaining"]
        == second["budgets"]["examinations_remaining"]
        == 1
    )


def test_successor_carries_exact_correction_and_cannot_ignore_it(loop):
    from cognitive_castle._vendor.sue import sue_dialectic

    correction = "Consent expires after 24 hours.\r\nRevoked consent prohibits export."
    obligations = [
        {"id": "all", "text": SOURCE, "source_id": "problem", "start": 0, "end": len(SOURCE)}
    ]
    sources = [{"id": "s1", "text": SOURCE, "provenance": {}}]
    first = loop.begin("b", SOURCE, CLAIM, sources, obligations)
    corrected = loop.correct(first["session_id"], "correct", first["revision"], correction)
    child = loop.begin(
        "child",
        SOURCE,
        CLAIM,
        sources,
        obligations,
        parent_id=first["session_id"],
        expected_revision=corrected["revision"],
        revision_reason="Try again",
    )
    records = json.loads(loop.page(child["session_id"], "corrections")["text"])
    assert records[0]["text"] == correction
    assert records[0]["attribution"] == "caller_attributed"
    assert child["counts"]["open_issues"] >= 1
    ledger = json.loads(loop.page(child["session_id"], "obligations")["text"])
    assert any(item["text"] == correction for item in ledger)
    source_map = json.loads(loop.page(child["session_id"], "source_map")["text"])
    assert any(item["text"] == "Consent expires after 24 hours." for item in source_map)
    for number, op in enumerate(sue_dialectic.LENSES["euthyphro"]["path"]):
        child = loop.respond(
            child["session_id"],
            f"t{number}",
            child["revision"],
            answer(op),
            commitment_map=[
                {"obligation_id": item["id"], "change": "retained", "reason": "Claimed retained"}
                for item in ledger
            ]
            if number == 0
            else None,
        )
    assert child["engine_terminal"] == "RESOLVED"
    assert child["advisory"] != "proceed_with_limits"
    assert child["counts"]["open_issues"] >= 1
    assert json.loads(loop.page(child["session_id"], "problem")["text"]) == SOURCE


def test_correction_is_a_purge_dependency_before_a_successor_exists(loop):
    import hashlib

    first = begin(loop)
    correction = "Private correction text that must be forgotten."
    loop.correct(first["session_id"], "correct", first["revision"], correction)
    purged = loop.purge_source(hashlib.sha256(correction.encode()).hexdigest())
    assert purged["affected_roots"] == 1
    assert correction not in json.dumps(loop.page(first["session_id"], "corrections"))
    assert loop.status(first["session_id"])["status"] == "source_purged"


def test_successor_proposed_problem_is_immediately_a_purge_dependency(loop):
    import hashlib

    first = begin(loop)
    proposal = "A private different proposed problem."
    child = loop.begin(
        "child",
        proposal,
        CLAIM,
        [],
        [],
        parent_id=first["session_id"],
        expected_revision=first["revision"],
        revision_reason="Changed proposal",
    )
    result = loop.purge_source(hashlib.sha256(proposal.encode()).hexdigest())
    assert result["affected_roots"] == 1
    assert loop.status(child["session_id"])["status"] == "source_purged"


@pytest.mark.parametrize("change", ["id", "provenance"])
def test_exposure_grant_binds_source_identity_and_metadata(tmp_path, change):
    from cognitive_castle.brain_loop import BrainLoop, source_exposure_hash

    source = {
        "id": "archive1",
        "text": "Identical public words",
        "provenance": {"local_only": True, "uri": "private://first"},
    }
    policy = {
        "allow_local_sources": False,
        "policy_epoch": "1",
        "allowed_source_hashes": [source_exposure_hash(source)],
    }
    loop = BrainLoop(tmp_path / "state", exposure_policy=policy)
    first = loop.begin("b", "Review", "Claim", [source], [])
    assert first["status"] == "ok"
    changed = dict(source)
    if change == "id":
        changed["id"] = "archive2"
    else:
        changed["provenance"] = {"local_only": True, "uri": "private://new-secret-metadata"}
    child = loop.begin(
        "child",
        "Review",
        "Claim",
        [changed],
        [],
        parent_id=first["session_id"],
        expected_revision=first["revision"],
        revision_reason="Changed archive snapshot",
    )
    assert child["status"] == "exposure_denied"
    assert "new-secret" not in json.dumps(child)


@pytest.mark.parametrize(
    "damage",
    ["DROP TABLE metadata", "DELETE FROM metadata WHERE key='pins'", "DROP TABLE task_roots"],
)
def test_existing_store_missing_schema_or_pins_is_not_reinitialized(loop, tmp_path, damage):
    state = begin(loop)
    db = sqlite3.connect(tmp_path / "controller" / "brain.sqlite3")
    db.execute(damage)
    db.commit()
    db.close()
    result = loop.status(state["session_id"])
    assert result["status"] in {"corrupt", "incompatible"}
    retry = begin(loop, "new-request")
    assert retry["status"] in {"corrupt", "incompatible"}
    db = sqlite3.connect(tmp_path / "controller" / "brain.sqlite3")
    if damage.startswith("DROP TABLE"):
        table = damage.split()[-1]
        assert (
            db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            is None
        )
    else:
        assert db.execute("SELECT value FROM metadata WHERE key='pins'").fetchone() is None
    assert db.execute("SELECT count(*) FROM roots").fetchone()[0] == 1
    db.close()


def test_correction_issue_resolution_must_cite_its_exact_correction(loop):
    import hashlib

    first = begin(loop)
    text = "Consent expires after one day."
    corrected = loop.correct(first["session_id"], "correct", first["revision"], text)
    child = begin(
        loop,
        "child",
        parent_id=first["session_id"],
        expected_revision=corrected["revision"],
        revision_reason="Address the correction",
    )
    record = json.loads(loop.page(child["session_id"], "corrections")["text"])[0]
    issues = json.loads(loop.page(child["session_id"], "issues")["text"])
    correction_issue = next(issue for issue in issues if issue["kind"] == "correction")
    quote = SOURCE.splitlines()[0]
    disposition = {
        "issue_id": correction_issue["id"],
        "status": "attributed_answer",
        "reason": "Account for the expiry constraint",
        "author": "host",
        "claim_version": 1,
        "dependencies": [hashlib.sha256(SOURCE.encode()).hexdigest()],
        "citations": [{"source_id": "s1", "start": 0, "end": len(quote), "quote": quote}],
    }
    rejected = loop.respond(
        child["session_id"],
        "irrelevant",
        child["revision"],
        answer("DEFINE"),
        dispositions=[disposition],
    )
    assert rejected["status"] == "invalid_response"
    assert rejected["counts"]["open_issues"] == 1
    disposition.update(
        dependencies=[record["hash"]],
        citations=[{"source_id": record["source_id"], "start": 0, "end": len(text), "quote": text}],
    )
    accepted = loop.respond(
        child["session_id"],
        "attributed",
        rejected["revision"],
        answer("DEFINE"),
        dispositions=[disposition],
    )
    assert accepted["status"] == "ok"
    assert accepted["counts"]["open_issues"] == 0
    assert accepted["independent_checks"] == "not_performed"


def test_archive_begin_preflight_rejects_spent_parent_with_one_request_charge(loop):
    first = begin(loop)
    child = begin(
        loop,
        "child",
        parent_id=first["session_id"],
        expected_revision=first["revision"],
        revision_reason="Use second slot",
    )
    before = loop.inspect(child["session_id"])
    result = loop.preflight_begin(
        SOURCE, parent_id=child["session_id"], expected_revision=child["revision"]
    )
    assert result["status"] == "examination_budget_exhausted"
    assert (
        result["budgets"]["automatic_requests_used"]
        == before["budgets"]["automatic_requests_used"] + 1
    )
    assert loop.preflight_begin(SOURCE)["root_id"] == first["root_id"]
    assert loop.preflight_begin(SOURCE)["status"] == "existing_task"


def test_archive_begin_preflight_reuses_exact_task_and_allows_admissible_successor(loop):
    assert loop.preflight_begin("A genuinely new request") is None
    first = begin(loop)
    used = first["budgets"]["automatic_requests_used"]
    existing = loop.preflight_begin(SOURCE)
    assert existing["status"] == "existing_task"
    assert existing["session_id"] == first["session_id"]
    assert existing["budgets"]["automatic_requests_used"] == used + 1
    assert (
        loop.preflight_begin(
            SOURCE, parent_id=first["session_id"], expected_revision=first["revision"]
        )
        is None
    )
    corrected = loop.correct(
        first["session_id"], "c", first["revision"], "An additional binding constraint."
    )
    assert (
        loop.preflight_begin(
            SOURCE, parent_id=first["session_id"], expected_revision=corrected["revision"]
        )
        is None
    )
    stale = loop.preflight_begin(
        SOURCE, parent_id=first["session_id"], expected_revision=first["revision"]
    )
    assert stale["status"] == "revision_conflict"


def test_archive_begin_preflight_obeys_current_exposure_expiry_and_request_cap(tmp_path):
    from cognitive_castle.brain_loop import BrainLoop

    now = [1000.0]
    policy = {"allow_local_sources": True, "policy_epoch": "1"}
    loop = BrainLoop(tmp_path / "state", exposure_policy=lambda: policy, clock=lambda: now[0])
    first = loop.begin(
        "b", SOURCE, CLAIM, [{"id": "s", "text": SOURCE, "provenance": {"local_only": True}}], []
    )
    policy.update(allow_local_sources=False, policy_epoch="2")
    denied = loop.preflight_begin(
        SOURCE, parent_id=first["session_id"], expected_revision=first["revision"]
    )
    assert denied["status"] == "exposure_denied"
    policy.update(allow_local_sources=True, policy_epoch="3")
    now[0] += 1801
    assert (
        loop.preflight_begin(
            SOURCE, parent_id=first["session_id"], expected_revision=first["revision"]
        )["status"]
        == "expired"
    )
    now[0] = 1000
    for _ in range(63):
        loop.status(first["session_id"])
    stopped = loop.preflight_begin(
        SOURCE, parent_id=first["session_id"], expected_revision=first["revision"]
    )
    assert stopped["status"] == "request_budget_exhausted"
    assert stopped["budgets"]["automatic_requests_used"] == 64


@pytest.mark.parametrize("change", ["expiry", "revocation"])
def test_successor_rechecks_admission_after_preflight(tmp_path, change):
    from cognitive_castle.brain_loop import BrainLoop

    now = [1000.0]
    policy = {"allow_local_sources": True, "policy_epoch": "1"}
    loop = BrainLoop(tmp_path / "state", exposure_policy=lambda: policy, clock=lambda: now[0])
    sources = [{"id": "s", "text": SOURCE, "provenance": {"local_only": True}}]
    first = loop.begin("b", SOURCE, CLAIM, sources, [])
    assert (
        loop.preflight_begin(
            SOURCE, parent_id=first["session_id"], expected_revision=first["revision"]
        )
        is None
    )
    if change == "expiry":
        now[0] += 1801
    else:
        policy.update(allow_local_sources=False, policy_epoch="2")
    child = loop.begin(
        "child",
        SOURCE,
        CLAIM,
        sources,
        [],
        parent_id=first["session_id"],
        expected_revision=first["revision"],
        revision_reason="Read finished",
    )
    assert child["status"] == ("expired" if change == "expiry" else "exposure_denied")
    assert child["session_id"] == first["session_id"]
    assert child["budgets"]["examinations_remaining"] == 1
