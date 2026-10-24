"""Pure, model-free incremental adapter to the unchanged bundled SUE engine.

Only the vendor's deterministic question/schema/validation/transition functions
are used. No process-global transport replacement and no provider invocation.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from types import SimpleNamespace

from ._vendor.sue import sue_dialectic as vendor


def initial_state(seed: str, *, lens: str = "euthyphro", max_turns: int = 14) -> dict:
    if lens not in vendor.LENSES or type(max_turns) is not int or not 1 <= max_turns <= 14:
        raise ValueError("invalid engine configuration")
    return dict(
        lens=lens,
        seed=seed,
        claim=seed,
        version=0,
        revisions_used=0,
        failure="",
        operator="DEFINE",
        terminal=None,
        max_turns=max_turns,
        turns=[],
    )


def question(state: dict) -> str | None:
    if state["terminal"]:
        return None
    return vendor.build_question(
        state["operator"], state["seed"], state["claim"], state["failure"], state["lens"]
    )


def schema(state: dict) -> dict | None:
    return None if state["terminal"] else vendor.build_output_schema(state["operator"])


def coverage(state: dict) -> dict:
    return vendor.depth_profile([vendor.Turn(**t) for t in state["turns"]], state["lens"])


def advance(state: dict, response: dict, lines: list[str]) -> tuple[dict, str | None]:
    """Return a fresh projection or the unchanged state plus a bounded error code."""
    if state["terminal"]:
        return state, "engine_terminal"
    turns = [vendor.Turn(**t) for t in state["turns"]]
    operator = state["operator"]
    established = any(
        t.claim_version == state["version"]
        and t.operator in ("DEFINE", "REVISE")
        and t.verdict == "SUPPORTED"
        and t.answer_type in ("definition", "revision")
        for t in turns
    )
    try:
        result = vendor.validate_turn(
            response,
            operator,
            SimpleNamespace(lines=lines),
            turns=turns,
            current_claim=state["claim"] if established else None,
        )
    except (TypeError, ValueError, KeyError):
        return state, "invalid_turn"
    if isinstance(result, vendor.v1.ParseFailure):
        return state, "invalid_turn"
    new = deepcopy(state)
    before = new["claim"]
    if result["claim"] is not None:
        if not new["version"] or operator == "REVISE" or result["claim"] != before:
            new["version"] += 1
        new["claim"] = result["claim"]
    if operator == "REVISE":
        new["revisions_used"] += 1
    turn = vendor.Turn(
        turn_no=len(turns) + 1,
        operator=operator,
        question=question(state),
        claim_version=new["version"],
        claim_before=before,
        claim_after=new["claim"],
        **result,
    )
    turns.append(turn)
    profile = vendor.depth_profile(turns, new["lens"])
    completed = [d["operator"] for d in profile["dimensions"] if d["turn"] is not None]
    step = vendor.next_step(
        new["lens"],
        operator,
        turn.verdict,
        turn.answer_type,
        new["revisions_used"],
        turn.test_result,
        completed,
    )
    if turn.test_result == "FOUND":
        new["failure"] = turn.answer
    if step == "RESOLVED" and (profile["missing"] or profile["open_issues"]):
        step = "APORIA_UNDERDETERMINED"
    if step in vendor.TERMINALS:
        why = (
            "revision_budget_exhausted"
            if step == "BOUNDED_STOP"
            else "all_dimensions_examined_for_current_claim"
            if step == "RESOLVED"
            else "source_conflict_candidate"
            if step == "APORIA_CONTRADICTED"
            else "open_questions_or_insufficient_source"
        )
        turns[-1] = replace(turn, stop_reason=why)
        new["terminal"] = step
    elif len(turns) >= new["max_turns"]:
        turns[-1] = replace(turn, stop_reason="turn_budget_exhausted")
        new["terminal"] = "BOUNDED_STOP"
    else:
        new["operator"] = step
    new["turns"] = [asdict(t) for t in turns]
    return new, None
