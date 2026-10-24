"""Differential adapter tests use scripted answers, never an answering model."""

from dataclasses import asdict
from types import SimpleNamespace

import pytest

from cognitive_castle._vendor.sue import sue_dialectic as vendor

SOURCE = "Only administrators may export data.\nConsent must be current.\n"
CLAIM = "Administrators export with current consent."
TYPES = dict(
    DEFINE="definition",
    DISTINGUISH="distinction",
    CAUSE_OR_CRITERION="criterion",
    DIVIDE="case-split",
    COUNTEREXAMPLE="example",
    FOLLOW_CONSEQUENCE="consequence",
    TEST_OPPOSITE="consequence",
    REVISE="revision",
)


def answer(op, result=None, **changes):
    result = result or vendor.SUCCESS_RESULT[op]
    silent = result == "UNKNOWN"
    p = dict(
        answer="An attributed interpretation, requiring review.",
        verdict={"UNKNOWN": "SILENT", "INCOMPLETE": "PARTIAL", "CONFLICT": "CONTRADICTED"}.get(
            result, "SUPPORTED"
        ),
        answer_type=TYPES[op],
        evidence_lines=[] if silent else [1],
        claim=CLAIM if op in ("DEFINE", "REVISE") and not silent else None,
        test_result=result,
        evidence=[] if silent else [{"line": 1, "quote": SOURCE.splitlines()[0]}],
        premises=[]
        if silent
        else [{"statement": SOURCE.splitlines()[0], "kind": "stated", "evidence_lines": [1]}],
        witness=None,
        open_questions=[],
        addresses=[],
        revision_reason=None,
    )
    if result in ("FOUND", "POSSIBLE", "CONFLICT"):
        p["witness"] = dict(
            situation="An export request.",
            reading_a="Export allowed.",
            reading_b="Export forbidden.",
            why_incompatible="Opposite decisions for the same request.",
            lines_a=[1],
            lines_b=[1],
        )
    p.update(changes)
    return p


@pytest.mark.parametrize("lens", list(vendor.LENSES))
@pytest.mark.parametrize("scenario", ["success", "silence", "partial", "revision", "exhaustion"])
def test_reducer_matches_unchanged_vendor(monkeypatch, tmp_path, lens, scenario):
    from cognitive_castle import brain_engine as engine

    path = vendor.LENSES[lens]["path"]
    replies = [answer(op) for op in path]
    cap = 14
    if scenario == "silence":
        replies = [answer("DEFINE", "UNKNOWN")]
    elif scenario == "partial":
        replies = [answer("DEFINE", "INCOMPLETE"), answer("DISTINGUISH", "UNKNOWN")]
    elif scenario == "exhaustion":
        cap = 2
    elif scenario == "revision":
        prefix = list(path[: path.index("COUNTEREXAMPLE")])
        replies = [answer(op) for op in prefix] + [answer("COUNTEREXAMPLE", "FOUND")]
        replies += [
            answer(
                "REVISE",
                addresses=list(range(1, len(replies) + 1)),
                revision_reason="Retain role and consent.",
            )
        ]
        replies += [answer(op) for op in path if op != "DEFINE"]
    queue = iter(replies)

    def execute(_config, _prompt, validator, **_kw):
        validated = validator(next(queue))
        assert not isinstance(validated, vendor.v1.ParseFailure)
        return validated

    monkeypatch.setattr(vendor.v1, "execute_round", execute)
    spec = SimpleNamespace(lines=SOURCE.splitlines())
    turns, terminal, error = vendor.run_dialogue(None, spec, tmp_path, lens, CLAIM, cap)
    assert error is None
    state = engine.initial_state(CLAIM, lens=lens, max_turns=cap)
    for reply in replies:
        if state["terminal"]:
            break
        state, failure = engine.advance(state, reply, spec.lines)
        assert failure is None
    assert state["turns"] == [asdict(t) for t in turns]
    assert state["terminal"] == terminal
    assert engine.coverage(state) == vendor.depth_profile(turns, lens)


def test_invalid_reducer_does_not_mutate_input():
    from cognitive_castle import brain_engine as engine

    state = engine.initial_state(CLAIM)
    other, failure = engine.advance(state, {}, SOURCE.splitlines())
    assert failure and other == state and state["turns"] == []
