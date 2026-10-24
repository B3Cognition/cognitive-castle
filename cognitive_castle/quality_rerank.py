"""quality_rerank.py — Stage 6 of Castle's retrieval pipeline.

ON by default. Opt-out via --mode fast (or mode:fast MCP).
Only explicitly selected requirements use the historical requirements thresholds.
Explicit articles receive descriptive assessment without a ranking boost; unknown
profiles and historical untyped conversations remain not_assessed. No model loads.

Two-tier threshold-and-boost rule with defaults calibrated to the user's
palace on 2026-05-14:
  - score >= cfg.quality_threshold_high (0.60)   → tier="high",   ×1.25
  - score >= cfg.quality_threshold_medium (0.53) → tier="medium", ×1.15
  - otherwise                                    → tier=None,     ×1.0

Per-hit audit-trail fields added to each row:
  - quality_score: float | None       (None when Stage 6 didn't run or
                                       per-hit failure occurred)
  - quality_tier:  "high" | "medium" | None
  - quality_boost: float (default 1.0)
  - score_pre_quality: float (hit's score before Stage 6 ran)

The audit-line printer in searcher._print_search_results only emits a
QUALITY line when quality_tier is not None.

Graceful degradation: if the vendored package fails to import or a
per-hit call raises, the affected hit(s) get default fields and a
warning is logged once per failure class.

See spec: docs/superpowers/specs/2026-05-14-quality-rerank-design.md
"""

from __future__ import annotations

import json
import math
import sys
from typing import Optional


ADAPTER_NAME = "quality-rerank"

# Module-level state. Cleared by _reset_for_test() in test runs.
_WARNED: set[str] = set()


def _warn_once(key: str, message: str) -> None:
    """Print a stderr warning ONCE per process for the given key."""
    if key in _WARNED:
        return
    _WARNED.add(key)
    print(f"[quality_rerank] {message}", file=sys.stderr)


def _reset_for_test() -> None:
    """Test-only: clear module-level state to enable test isolation."""
    _WARNED.clear()


def _classify_tier(score: float, cfg) -> tuple[Optional[str], float]:
    """Apply the two-tier threshold rule. Returns (tier, multiplier).

    >= cfg.quality_threshold_high → ("high",   cfg.quality_boost_high)
    >= cfg.quality_threshold_medium → ("medium", cfg.quality_boost_medium)
    otherwise                       → (None,     1.0)
    """
    if score >= cfg.quality_threshold_high:
        return "high", cfg.quality_boost_high
    if score >= cfg.quality_threshold_medium:
        return "medium", cfg.quality_boost_medium
    return None, 1.0


def apply_quality_rerank(
    reranked: list[tuple[float, dict]],
    cfg,
) -> list[tuple[float, dict]]:
    """Stage 6: deterministic text-quality rerank.

    Select the profile from row or metadata quality_profile. Requirements use
    model-free enhanced metrics; articles have no calibrated aggregate. Mutate
    audit fields with quality_status, versioned quality_profile and quality_reason.

    Returns a NEW list of (score, row) tuples sorted by boosted score
    descending. Each row dict is mutated in place with:
      - quality_score (float, or None on per-hit failure)
      - quality_tier ("high" | "medium" | None)
      - quality_boost (float, 1.0 if no boost)
      - score_pre_quality (float, hit's score going into Stage 6)

    Graceful degradation:
      - If `cognitive_castle.understanding` import fails, all hits get
        default fields (None, None, 1.0, original score). Warns once.
      - If per-hit metric call raises, that hit gets default fields.
        Warns once per exception class.

    Never raises. Quality failures retain the entering scores.
    """
    if not reranked:
        return reranked

    out: list[tuple[float, dict]] = []
    for original_score, row in reranked:
        metadata = row.get("metadata")
        if not isinstance(metadata, dict):
            metadata = _profile_metadata(row.get("metadata_json"))
        selected = row.get("quality_profile", metadata.get("quality_profile"))
        _set_defaults(row, original_score=original_score)
        if type(selected) is not str or selected not in {
            "requirements",
            "requirements-v3.7.0",
            "article",
            "article-v1",
        }:
            out.append((original_score, row))
            continue
        text = row.get("text") or row.get("document") or ""
        try:
            if selected in {"article", "article-v1"}:
                from cognitive_castle.understanding import analyze_article_quality

                result = analyze_article_quality(
                    text,
                    language=row.get("language", metadata.get("language", "unknown")),
                    scope=row.get("scope", metadata.get("scope", "article")),
                )
                row["quality_profile"] = "article-v1"
                row["quality_status"] = result["status"]
                row["quality_reason"] = result.get("reason", result["quality_reason"])
                out.append((original_score, row))
                continue

            from cognitive_castle.understanding import analyze_with_enhanced_metrics

            result = analyze_with_enhanced_metrics(text, use_spacy=False)
            score = result["enhanced_metrics"]["overall_weighted_average"]
            if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("invalid overall_weighted_average")
            tier, multiplier = _classify_tier(float(score), cfg)
        except ImportError as exc:
            _warn_once(
                "import-failed",
                f"understanding import failed ({type(exc).__name__}); per-hit default",
            )
            row["quality_status"] = "unavailable"
            row["quality_reason"] = "profile_unavailable"
            out.append((original_score, row))
            continue
        except Exception as exc:
            _warn_once(
                f"analyze-failed-{type(exc).__name__}",
                f"quality analysis raised ({type(exc).__name__}); per-hit default",
            )
            row["quality_status"] = "unavailable"
            row["quality_reason"] = "assessment_failed"
            out.append((original_score, row))
            continue

        row["quality_profile"] = "requirements-v3.7.0"
        row["quality_status"] = "assessed"
        row["quality_reason"] = None
        row["quality_score"] = float(score)
        row["quality_tier"] = tier
        row["quality_boost"] = multiplier
        out.append((original_score * multiplier, row))

    # Sort by boosted score descending
    out.sort(key=lambda t: -t[0])
    return out


def _profile_metadata(raw) -> dict:
    """Read explicit selectors from the bounded LanceDB metadata column."""
    if type(raw) is not str or len(raw) > 8192:
        return {}
    try:
        if len(raw.encode("utf-8")) > 8192:
            return {}
        value = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError):
        return {}
    return value if isinstance(value, dict) else {}


def _set_defaults(row: dict, *, original_score: float) -> dict:
    """Mutate the row dict with default quality_* fields (used on failure
    paths). Returns the same dict for fluent chaining."""
    row["quality_profile"] = None
    row["quality_status"] = "not_assessed"
    row["quality_reason"] = "explicit_profile_required"
    row["quality_score"] = None
    row["quality_tier"] = None
    row["quality_boost"] = 1.0
    row["score_pre_quality"] = original_score
    return row
