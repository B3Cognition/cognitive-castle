"""Ranking regressions through the legacy, native-free compatibility API."""

from copy import deepcopy
import time
from types import SimpleNamespace

import pytest

from cognitive_castle import soar_bridge as bridge


@pytest.fixture(autouse=True)
def isolated_context(monkeypatch):
    monkeypatch.delenv("CASTLE_PROJECT", raising=False)
    monkeypatch.delenv("CASTLE_SOAR_RULES_PATH", raising=False)
    # 2026-10-24T00:00:00Z; literal dates below independently define boundaries.
    monkeypatch.setattr(time, "time", lambda: 1792800000.0)


@pytest.fixture
def cfg():
    return SimpleNamespace(soar_rules_path=None)


@pytest.mark.parametrize(
    "hit,query,tags,boost",
    [
        ({"created_at": "2026-10-23T00:00:00Z"}, "", ["recency-boost"], 1.25),
        ({"wing": "default"}, "", ["same-project"], 1.15),
        ({"entity_match": True}, "", ["entity-match"], 1.3),
        ({"room": "decisions"}, "what did we decide", ["type-match"], 1.25),
        ({"wing": "elsewhere", "room": "decisions"}, "a bug", [], 1.0),
    ],
)
def test_rules_adjust_scores_and_name_the_evidence(hit, query, tags, boost, cfg):
    result = bridge.apply_soar_boosts([{"score": 2.0, **hit}], cfg, query=query)[0]
    assert result["score"] == pytest.approx(2.0 * boost)
    assert result["score_pre_soar"] == 2.0
    assert result["soar_boost"] == boost
    assert result["soar_tags"] == tags
    assert result["symbolic_status"] == ("applied" if tags else "no_match")


def test_all_four_rules_compound_once_in_stable_order(cfg, monkeypatch):
    monkeypatch.setenv("CASTLE_PROJECT", "sixth-sense")
    hits = [
        {
            "score": 2.0,
            "wing": "sixth-sense",
            "room": "decisions",
            "entity_match": True,
            "created_at": "2026-10-23T00:00:00Z",
        }
    ]
    result = bridge.apply_soar_boosts(hits, cfg, query="what did we decide")[0]
    assert result["soar_tags"] == ["recency-boost", "same-project", "entity-match", "type-match"]
    assert result["soar_boost"] == pytest.approx(2.3359375)
    assert result["score"] == pytest.approx(4.671875)


@pytest.mark.parametrize(
    "timestamp,recent",
    [
        (None, False),
        ("", False),
        ("not-a-date", False),
        (42, False),
        ({}, False),
        ("2026-10-17T00:00:00Z", False),
        ("2026-10-17T00:00:01Z", True),
        ("2026-10-17T01:00:00+01:00", False),
        ("2026-10-25T00:00:00Z", True),
    ],
)
def test_recency_boundary_and_invalid_dates(timestamp, recent, cfg):
    result = bridge.apply_soar_boosts([{"score": 1.0, "created_at": timestamp}], cfg)[0]
    assert result["soar_tags"] == (["recency-boost"] if recent else [])
    assert result["score"] == (1.25 if recent else 1.0)


def test_current_project_replaces_default_project(cfg, monkeypatch):
    monkeypatch.setenv("CASTLE_PROJECT", "current")
    result = bridge.apply_soar_boosts(
        [{"score": 1.0, "wing": wing} for wing in ["default", "current", "Current", ""]], cfg
    )
    assert [hit["score"] for hit in result] == [1.0, 1.15, 1.0, 1.0]


@pytest.mark.parametrize(
    "room",
    [
        "decision",
        "decisions",
        "preference",
        "preferences",
        "milestone",
        "milestones",
        "problem",
        "problems",
        "emotional",
    ],
)
def test_singular_and_plural_rooms_follow_query_intent(room, cfg):
    query = {
        "decision": "what did we decide",
        "preference": "my preference",
        "milestone": "when did we ship",
        "problem": "the bug",
        "emotional": "how I feel",
    }
    result = bridge.apply_soar_boosts(
        [{"score": 1.0, "room": room}], cfg, query=query[room.rstrip("s")]
    )[0]
    assert result["score"] == 1.25
    assert result["soar_tags"] == ["type-match"]


def test_duplicate_source_identities_receive_only_their_own_tags(cfg):
    common = {"id": "same", "wing": "x", "room": "r", "source_file": "same.md", "score": 1.0}
    result = bridge.apply_soar_boosts(
        [{**common, "entity_match": True}, {**common, "entity_match": False}], cfg
    )
    assert [hit["score"] for hit in result] == [1.3, 1.0]
    assert [hit["soar_tags"] for hit in result] == [["entity-match"], []]


def test_inputs_and_repeated_calls_do_not_share_audit_state(cfg):
    hits = [{"score": 2.0, "entity_match": True, "soar_tags": ["stale"], "soar_boost": 9.0}]
    before = deepcopy(hits)
    first = bridge.apply_soar_boosts(hits, cfg)
    second = bridge.apply_soar_boosts(hits, cfg)
    assert hits == before
    assert first == second
    first[0]["soar_tags"].append("changed")
    assert second[0]["soar_tags"] == ["entity-match"]


@pytest.mark.parametrize("score,expected", [(2.0, 2.6), (0.0, 0.0), (-2.0, -2.6)])
def test_multiplication_preserves_legacy_negative_score_semantics(score, expected, cfg):
    result = bridge.apply_soar_boosts([{"score": score, "entity_match": True}], cfg)[0]
    assert result["score"] == expected
    assert result["score_pre_soar"] == score


def test_tuple_adapter_uses_authoritative_score_and_does_not_mutate_rows(cfg):
    rows = [
        (1.0, {"id": "a", "score": 99.0, "entity_match": True}),
        (1.2, {"id": "b"}),
        (-1.0, {"id": "c", "entity_match": True}),
    ]
    before = deepcopy(rows)
    result = bridge._apply_soar_to_reranked(rows, cfg)
    assert [(score, row["id"]) for score, row in result] == [(1.3, "a"), (1.2, "b"), (-1.3, "c")]
    assert result[0][1]["score_pre_soar"] == 1.0
    assert rows == before


@pytest.mark.parametrize(
    "metadata,boost",
    [
        ('{"filed_at":"2026-10-23T00:00:00Z"}', 1.25),
        ("{}", 1.0),
        ("[]", 1.0),
        ("null", 1.0),
        ("broken", 1.0),
        (None, 1.0),
        ('{"filed_at":42}', 1.0),
    ],
)
def test_tuple_adapter_handles_filed_at_metadata(metadata, boost, cfg):
    rows = [(1.0, {"metadata_json": metadata})]
    assert bridge._apply_soar_to_reranked(rows, cfg)[0][0] == boost


def test_equal_scores_keep_input_order_and_empty_input_is_supported(cfg):
    rows = [(1.0, {"id": "b"}), (1.0, {"id": "a"})]
    assert [row["id"] for _, row in bridge._apply_soar_to_reranked(rows, cfg)] == ["b", "a"]
    assert bridge.apply_soar_boosts([], cfg) == []
    assert bridge._apply_soar_to_reranked([], cfg) == []


def test_legacy_candidate_limit_keeps_remainder_neutral(cfg, capsys):
    hits = [{"score": 1.0, "entity_match": True} for _ in range(51)]
    result = bridge.apply_soar_boosts(hits, cfg)
    assert len(result) == 51
    assert all(hit["score"] == 1.3 for hit in result[:50])
    assert result[-1]["score"] == 1.0
    assert result[-1]["soar_tags"] == []
    assert result[-1]["symbolic_status"] == "candidate_limit"
    assert "50" in capsys.readouterr().err


def test_no_match_replaces_stale_audits_without_mutating_input(cfg):
    hits = [
        {
            "score": 2.0,
            "soar_tags": ["entity-match"],
            "soar_boost": 1.3,
            "score_pre_soar": 4.0,
            "symbolic_status": "applied",
        }
    ]
    original = deepcopy(hits)
    result = bridge.apply_soar_boosts(hits, cfg)[0]
    assert result["score_pre_soar"] == 2.0
    assert result["soar_boost"] == 1.0
    assert result["soar_tags"] == []
    assert result["symbolic_status"] == "no_match"
    assert hits == original
