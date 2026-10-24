"""Tests for cognitive_castle.quality_rerank (Stage 6 of mine())."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────


def _mock_cfg(
    *,
    threshold_medium=0.53,
    threshold_high=0.60,
    boost_medium=1.15,
    boost_high=1.25,
    quality_enabled=True,
):
    """Minimal cfg exposing only the fields quality_rerank reads."""
    cfg = MagicMock()
    cfg.quality_threshold_medium = threshold_medium
    cfg.quality_threshold_high = threshold_high
    cfg.quality_boost_medium = boost_medium
    cfg.quality_boost_high = boost_high
    cfg.quality_enabled = quality_enabled
    return cfg


# ── Tier classification (pure function, no external deps) ───────────


def test_classify_tier_score_above_high_threshold():
    from cognitive_castle.quality_rerank import _classify_tier

    tier, multiplier = _classify_tier(0.75, _mock_cfg())
    assert tier == "high"
    assert multiplier == 1.25


def test_classify_tier_score_at_high_threshold_boundary_inclusive():
    from cognitive_castle.quality_rerank import _classify_tier

    tier, multiplier = _classify_tier(0.60, _mock_cfg())
    assert tier == "high"
    assert multiplier == 1.25


def test_classify_tier_score_in_medium_range():
    from cognitive_castle.quality_rerank import _classify_tier

    tier, multiplier = _classify_tier(0.55, _mock_cfg())
    assert tier == "medium"
    assert multiplier == 1.15


def test_classify_tier_score_at_medium_threshold_boundary_inclusive():
    from cognitive_castle.quality_rerank import _classify_tier

    tier, multiplier = _classify_tier(0.53, _mock_cfg())
    assert tier == "medium"
    assert multiplier == 1.15


def test_classify_tier_score_below_medium_threshold():
    from cognitive_castle.quality_rerank import _classify_tier

    tier, multiplier = _classify_tier(0.40, _mock_cfg())
    assert tier is None
    assert multiplier == 1.0


def test_classify_tier_non_default_thresholds():
    from cognitive_castle.quality_rerank import _classify_tier

    cfg = _mock_cfg(threshold_medium=0.30, threshold_high=0.70)
    assert _classify_tier(0.75, cfg) == ("high", 1.25)
    assert _classify_tier(0.50, cfg) == ("medium", 1.15)
    assert _classify_tier(0.20, cfg) == (None, 1.0)


# ── apply_quality_rerank (mocked analyze_with_enhanced_metrics) ────


def test_apply_quality_rerank_empty_input(monkeypatch):
    """Empty input → empty output, no crash."""
    from cognitive_castle import quality_rerank as qr

    qr._reset_for_test()

    result = qr.apply_quality_rerank([], _mock_cfg())
    assert result == []


def test_apply_quality_rerank_all_high_tier(monkeypatch):
    """All hits above high threshold → all ×1.25, all "high"."""
    from cognitive_castle import quality_rerank as qr

    qr._reset_for_test()

    # Stub the metric function to always return high score
    monkeypatch.setattr(
        "cognitive_castle.understanding.analyze_with_enhanced_metrics",
        lambda text, **kwargs: {"enhanced_metrics": {"overall_weighted_average": 0.75}},
    )

    hits = [
        (
            1.0,
            {
                "quality_profile": "requirements",
                "id": "a",
                "text": "text a",
                "wing": "w",
                "room": "r",
            },
        ),
        (
            0.8,
            {
                "quality_profile": "requirements",
                "id": "b",
                "text": "text b",
                "wing": "w",
                "room": "r",
            },
        ),
    ]
    result = qr.apply_quality_rerank(hits, _mock_cfg())

    assert len(result) == 2
    for new_score, row in result:
        assert row["quality_score"] == 0.75
        assert row["quality_tier"] == "high"
        assert row["quality_boost"] == 1.25
    # Top hit (originally 1.0) is now 1.25; second hit (0.8) is now 1.0
    assert result[0][0] == 1.25
    assert result[1][0] == 1.0


def test_apply_quality_rerank_all_below_medium(monkeypatch):
    """All hits below medium → all tier=None, quality_score set, boost=1.0,
    score_pre_quality == original score."""
    from cognitive_castle import quality_rerank as qr

    qr._reset_for_test()

    monkeypatch.setattr(
        "cognitive_castle.understanding.analyze_with_enhanced_metrics",
        lambda text, **kwargs: {"enhanced_metrics": {"overall_weighted_average": 0.40}},
    )

    hits = [
        (
            0.5,
            {
                "quality_profile": "requirements",
                "id": "a",
                "text": "text a",
                "wing": "w",
                "room": "r",
            },
        ),
        (
            0.4,
            {
                "quality_profile": "requirements",
                "id": "b",
                "text": "text b",
                "wing": "w",
                "room": "r",
            },
        ),
    ]
    result = qr.apply_quality_rerank(hits, _mock_cfg())

    for new_score, row in result:
        assert row["quality_score"] == 0.40
        assert row["quality_tier"] is None
        assert row["quality_boost"] == 1.0
        assert row["score_pre_quality"] == new_score


def test_apply_quality_rerank_mixed_tiers(monkeypatch):
    """Mixed input → correct tier per hit."""
    from cognitive_castle import quality_rerank as qr

    qr._reset_for_test()

    # Different scores per hit-id — use unique non-overlapping markers
    score_map = {"hit_alpha": 0.75, "hit_beta": 0.55, "hit_gamma": 0.40}

    def fake_analyze(text, *, use_spacy):
        assert use_spacy is False
        # text is hit's text field; we map by what's in the text
        for marker, score in score_map.items():
            if marker in text:
                return {"enhanced_metrics": {"overall_weighted_average": score}}
        return {"enhanced_metrics": {"overall_weighted_average": 0.5}}

    monkeypatch.setattr(
        "cognitive_castle.understanding.analyze_with_enhanced_metrics",
        fake_analyze,
    )

    hits = [
        (
            1.0,
            {
                "quality_profile": "requirements",
                "id": "a",
                "text": "hit_alpha text",
                "wing": "w",
                "room": "r",
            },
        ),
        (
            1.0,
            {
                "quality_profile": "requirements",
                "id": "b",
                "text": "hit_beta text",
                "wing": "w",
                "room": "r",
            },
        ),
        (
            1.0,
            {
                "quality_profile": "requirements",
                "id": "c",
                "text": "hit_gamma text",
                "wing": "w",
                "room": "r",
            },
        ),
    ]
    result = qr.apply_quality_rerank(hits, _mock_cfg())

    by_id = {row["id"]: row for _, row in result}
    assert by_id["a"]["quality_tier"] == "high"
    assert by_id["b"]["quality_tier"] == "medium"
    assert by_id["c"]["quality_tier"] is None


def test_apply_quality_rerank_all_fields_always_present(monkeypatch):
    """Every hit dict has all 4 quality_* fields regardless of tier."""
    from cognitive_castle import quality_rerank as qr

    qr._reset_for_test()

    monkeypatch.setattr(
        "cognitive_castle.understanding.analyze_with_enhanced_metrics",
        lambda text, **kwargs: {"enhanced_metrics": {"overall_weighted_average": 0.30}},
    )

    hits = [
        (
            1.0,
            {
                "quality_profile": "requirements",
                "id": "a",
                "text": "test",
                "wing": "w",
                "room": "r",
            },
        )
    ]
    result = qr.apply_quality_rerank(hits, _mock_cfg())

    _, row = result[0]
    assert "quality_score" in row
    assert "quality_tier" in row
    assert "quality_boost" in row
    assert "score_pre_quality" in row


def test_apply_quality_rerank_score_equals_pre_times_boost(monkeypatch):
    """hit["score"] (in output tuple) == score_pre_quality × quality_boost."""
    from cognitive_castle import quality_rerank as qr

    qr._reset_for_test()

    monkeypatch.setattr(
        "cognitive_castle.understanding.analyze_with_enhanced_metrics",
        lambda text, **kwargs: {"enhanced_metrics": {"overall_weighted_average": 0.75}},
    )

    hits = [
        (
            0.8,
            {
                "quality_profile": "requirements",
                "id": "a",
                "text": "test",
                "wing": "w",
                "room": "r",
            },
        )
    ]
    result = qr.apply_quality_rerank(hits, _mock_cfg())

    new_score, row = result[0]
    assert row["score_pre_quality"] == 0.8
    assert row["quality_boost"] == 1.25
    assert new_score == 0.8 * 1.25  # 1.0


def test_apply_quality_rerank_sorted_descending(monkeypatch):
    """Output sorted by boosted score descending — re-rank may reorder."""
    from cognitive_castle import quality_rerank as qr

    qr._reset_for_test()

    # Lower-scored hit gets a bigger boost; should jump to top after rerank
    score_map = {"low_quality_high_relevance": 0.30, "high_quality_low_relevance": 0.75}

    def fake_analyze(text, *, use_spacy):
        assert use_spacy is False
        for k, score in score_map.items():
            if k in text:
                return {"enhanced_metrics": {"overall_weighted_average": score}}
        return {"enhanced_metrics": {"overall_weighted_average": 0.5}}

    monkeypatch.setattr(
        "cognitive_castle.understanding.analyze_with_enhanced_metrics",
        fake_analyze,
    )

    hits = [
        (
            0.9,
            {
                "quality_profile": "requirements",
                "id": "a",
                "text": "low_quality_high_relevance text",
                "wing": "w",
                "room": "r",
            },
        ),
        (
            0.8,
            {
                "quality_profile": "requirements",
                "id": "b",
                "text": "high_quality_low_relevance text",
                "wing": "w",
                "room": "r",
            },
        ),
    ]
    result = qr.apply_quality_rerank(hits, _mock_cfg())

    # Hit b: 0.8 × 1.25 = 1.0 — should be top
    # Hit a: 0.9 × 1.0  = 0.9
    assert result[0][1]["id"] == "b"
    assert result[1][1]["id"] == "a"
    # Sorted descending:
    assert result[0][0] >= result[1][0]


# ── Failure modes (mocked) ───────────────────────────────────────────


def test_apply_quality_rerank_import_fails(monkeypatch, capsys):
    """understanding import fails → all hits get default fields, warn once."""
    from cognitive_castle import quality_rerank as qr

    qr._reset_for_test()

    # Stub the import to raise
    import sys

    monkeypatch.setitem(sys.modules, "cognitive_castle.understanding", None)

    hits = [
        (
            1.0,
            {
                "quality_profile": "requirements",
                "id": "a",
                "text": "test",
                "wing": "w",
                "room": "r",
            },
        ),
        (
            0.5,
            {
                "quality_profile": "requirements",
                "id": "b",
                "text": "test",
                "wing": "w",
                "room": "r",
            },
        ),
    ]
    result = qr.apply_quality_rerank(hits, _mock_cfg())

    assert len(result) == 2
    for _, row in result:
        assert row["quality_score"] is None
        assert row["quality_tier"] is None
        assert row["quality_boost"] == 1.0
        assert "score_pre_quality" in row

    captured = capsys.readouterr()
    assert "understanding import failed" in captured.err


def test_apply_quality_rerank_per_hit_failure(monkeypatch, capsys):
    """analyze_with_enhanced_metrics raises on a hit → that hit defaults,
    others continue. Warning printed once per exception class."""
    from cognitive_castle import quality_rerank as qr

    qr._reset_for_test()

    def fake_analyze(text, *, use_spacy):
        assert use_spacy is False
        if "bad" in text:
            raise RuntimeError("simulated metric failure")
        return {"enhanced_metrics": {"overall_weighted_average": 0.75}}

    monkeypatch.setattr(
        "cognitive_castle.understanding.analyze_with_enhanced_metrics",
        fake_analyze,
    )

    hits = [
        (
            1.0,
            {
                "quality_profile": "requirements",
                "id": "a",
                "text": "good text",
                "wing": "w",
                "room": "r",
            },
        ),
        (
            1.0,
            {
                "quality_profile": "requirements",
                "id": "b",
                "text": "bad text",
                "wing": "w",
                "room": "r",
            },
        ),
        (
            1.0,
            {
                "quality_profile": "requirements",
                "id": "c",
                "text": "good text",
                "wing": "w",
                "room": "r",
            },
        ),
    ]
    result = qr.apply_quality_rerank(hits, _mock_cfg())

    by_id = {row["id"]: row for _, row in result}
    assert by_id["a"]["quality_tier"] == "high"
    assert by_id["b"]["quality_tier"] is None  # defaulted
    assert by_id["b"]["quality_score"] is None
    assert by_id["c"]["quality_tier"] == "high"


def test_apply_quality_rerank_missing_enhanced_metrics_key(monkeypatch):
    """Result missing 'enhanced_metrics' key → per-hit skip with defaults."""
    from cognitive_castle import quality_rerank as qr

    qr._reset_for_test()

    monkeypatch.setattr(
        "cognitive_castle.understanding.analyze_with_enhanced_metrics",
        lambda text, **kwargs: {"some_other_key": "value"},
    )

    hits = [
        (
            1.0,
            {
                "quality_profile": "requirements",
                "id": "a",
                "text": "test",
                "wing": "w",
                "room": "r",
            },
        )
    ]
    result = qr.apply_quality_rerank(hits, _mock_cfg())

    _, row = result[0]
    assert row["quality_score"] is None
    assert row["quality_tier"] is None
    assert row["quality_boost"] == 1.0


def test_apply_quality_rerank_missing_overall_weighted_average_key(monkeypatch):
    """Result missing 'overall_weighted_average' key → per-hit skip."""
    from cognitive_castle import quality_rerank as qr

    qr._reset_for_test()

    monkeypatch.setattr(
        "cognitive_castle.understanding.analyze_with_enhanced_metrics",
        lambda text, **kwargs: {"enhanced_metrics": {"some_other": 0.5}},
    )

    hits = [
        (
            1.0,
            {
                "quality_profile": "requirements",
                "id": "a",
                "text": "test",
                "wing": "w",
                "room": "r",
            },
        )
    ]
    result = qr.apply_quality_rerank(hits, _mock_cfg())

    _, row = result[0]
    assert row["quality_score"] is None


def test_apply_quality_rerank_nan_overall_weighted_average(monkeypatch):
    """overall_weighted_average is NaN → per-hit skip."""
    from cognitive_castle import quality_rerank as qr

    qr._reset_for_test()

    monkeypatch.setattr(
        "cognitive_castle.understanding.analyze_with_enhanced_metrics",
        lambda text, **kwargs: {"enhanced_metrics": {"overall_weighted_average": float("nan")}},
    )

    hits = [
        (
            1.0,
            {
                "quality_profile": "requirements",
                "id": "a",
                "text": "test",
                "wing": "w",
                "room": "r",
            },
        )
    ]
    result = qr.apply_quality_rerank(hits, _mock_cfg())

    _, row = result[0]
    assert row["quality_score"] is None
    assert row["quality_tier"] is None


def test_apply_quality_rerank_keyboard_interrupt_propagates(monkeypatch):
    """KeyboardInterrupt must propagate, NOT be swallowed."""
    from cognitive_castle import quality_rerank as qr

    qr._reset_for_test()

    def raising_analyze(text, *, use_spacy):
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        "cognitive_castle.understanding.analyze_with_enhanced_metrics",
        raising_analyze,
    )

    hits = [
        (
            1.0,
            {
                "quality_profile": "requirements",
                "id": "a",
                "text": "test",
                "wing": "w",
                "room": "r",
            },
        )
    ]
    with pytest.raises(KeyboardInterrupt):
        qr.apply_quality_rerank(hits, _mock_cfg())


# ── Smoke (real package, slow marker) ────────────────────────────────


def test_apply_quality_rerank_smoke():
    """Real understanding package + real apply_quality_rerank on fixture
    prose. Catches vendored import-graph + wiring regressions."""
    from cognitive_castle import quality_rerank as qr

    qr._reset_for_test()

    fixture_text = (
        "The verbatim memory palace stores user data exactly as written. "
        "The retrieval pipeline combines dense vectors, full-text search, "
        "and knowledge-graph traversal, fused via Reciprocal Rank Fusion "
        "weighted by configurable signals. The cross-encoder reranker "
        "produces relevance scores; optional stages 4 and 5 compose "
        "deterministically."
    )  # ~370 chars of well-formed prose

    hits = [
        (
            0.5,
            {
                "quality_profile": "requirements",
                "id": "h1",
                "text": fixture_text,
                "wing": "w",
                "room": "r",
            },
        ),
    ]
    result = qr.apply_quality_rerank(hits, _mock_cfg())

    assert len(result) == 1
    new_score, row = result[0]
    # Shape, not exact values (real scores vary)
    assert isinstance(row["quality_score"], float)
    assert 0.0 <= row["quality_score"] <= 1.0
    assert row["quality_tier"] in (None, "medium", "high")
    assert row["quality_boost"] in (1.0, 1.15, 1.25)
    assert "score_pre_quality" in row
    assert row["score_pre_quality"] == 0.5


def test_mixed_profiles_only_explicit_requirements_receive_existing_boost(monkeypatch):
    from cognitive_castle import quality_rerank as qr

    def requirements_only(text, *, use_spacy):
        assert text == "Selected requirements."
        assert use_spacy is False
        return {"enhanced_metrics": {"overall_weighted_average": 0.75}}

    monkeypatch.setattr(
        "cognitive_castle.understanding.analyze_with_enhanced_metrics", requirements_only
    )
    hits = [
        (0.9, {"id": "legacy", "text": "Conversation with shall and must."}),
        (0.8, {"id": "article", "text": "A readable article.", "quality_profile": "article"}),
        (
            0.8,
            {
                "id": "req",
                "text": "Selected requirements.",
                "metadata": {"quality_profile": "requirements"},
            },
        ),
        (0.7, {"id": "unknown", "text": "Other text.", "quality_profile": "invented"}),
    ]
    result = qr.apply_quality_rerank(hits, _mock_cfg())
    assert [(score, row["id"]) for score, row in result] == [
        (1.0, "req"),
        (0.9, "legacy"),
        (0.8, "article"),
        (0.7, "unknown"),
    ]
    rows = {row["id"]: row for _, row in result}
    assert rows["req"]["quality_profile"] == "requirements-v3.7.0"
    assert rows["req"]["quality_status"] == "assessed"
    assert rows["article"]["quality_profile"] == "article-v1"
    assert rows["article"]["quality_status"] == "assessed"
    assert rows["article"]["quality_score"] is None
    assert rows["legacy"]["quality_status"] == "not_assessed"
    assert rows["unknown"]["quality_status"] == "not_assessed"


def test_untyped_drawers_do_not_even_import_analyzers(monkeypatch):
    import sys
    from cognitive_castle import quality_rerank as qr

    monkeypatch.setitem(sys.modules, "cognitive_castle.understanding", None)
    result = qr.apply_quality_rerank(
        [(0.7, {"text": "FR-001: must not imply a profile"})], _mock_cfg()
    )
    assert result[0][0] == 0.7
    assert result[0][1]["quality_status"] == "not_assessed"
    assert result[0][1]["quality_boost"] == 1.0


@pytest.mark.parametrize("score", [float("inf"), -0.1, 1.1, True])
def test_invalid_requirement_score_never_boosts(score, monkeypatch):
    from cognitive_castle import quality_rerank as qr

    monkeypatch.setattr(
        "cognitive_castle.understanding.analyze_with_enhanced_metrics",
        lambda text, **kwargs: {"enhanced_metrics": {"overall_weighted_average": score}},
    )
    result = qr.apply_quality_rerank(
        [(0.8, {"text": "Requirements.", "quality_profile": "requirements"})], _mock_cfg()
    )
    assert result[0][0] == 0.8
    assert result[0][1]["quality_score"] is None
    assert result[0][1]["quality_status"] == "unavailable"


@pytest.mark.parametrize("profile", [[], {}, 7, True])
def test_malformed_profile_metadata_stays_unassessed(profile):
    from cognitive_castle import quality_rerank as qr

    result = qr.apply_quality_rerank(
        [(0.5, {"text": "Some text.", "quality_profile": profile})], _mock_cfg()
    )
    assert result[0][0] == 0.5
    assert result[0][1]["quality_status"] == "not_assessed"


def test_requirement_profile_is_available_after_prior_assessment():
    from cognitive_castle import quality_rerank as qr

    row = {
        "text": "The system must keep the original audit record.",
        "quality_profile": "requirements",
    }
    first = qr.apply_quality_rerank([(0.5, row)], _mock_cfg())
    result = qr.apply_quality_rerank([(0.5, row)], _mock_cfg())
    assert result[0][1]["quality_status"] == "assessed"
    assert result[0][0] == first[0][0]


def test_explicit_profile_reads_lancedb_metadata_json():
    from cognitive_castle import quality_rerank as qr

    row = {
        "text": "The system must keep the audit record.",
        "metadata_json": '{"quality_profile":"requirements"}',
    }
    result = qr.apply_quality_rerank([(0.5, row)], _mock_cfg())
    assert result[0][1]["quality_status"] == "assessed"
    assert result[0][1]["quality_profile"] == "requirements-v3.7.0"


@pytest.mark.parametrize(
    "metadata",
    [
        "[",
        "[]",
        '{"quality_profile":"requirements","extra":"' + "x" * 8192 + '"}',
        "[" * 4096 + "]" * 4096,
    ],
)
def test_malformed_or_oversized_lancedb_metadata_cannot_select_profile(metadata):
    from cognitive_castle import quality_rerank as qr

    result = qr.apply_quality_rerank(
        [(0.5, {"text": "Some text.", "metadata_json": metadata})], _mock_cfg()
    )
    assert result[0][1]["quality_status"] == "not_assessed"
