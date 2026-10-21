"""Cross-palace comparison of ``castle info-stats --export`` files.

The paper's measurements come from one palace. Other users can run
``castle info-stats --export`` on theirs and share the file; this module
puts several such files side by side so the structural claims can be
checked on palaces nobody else has seen:

- per-wing novelty distributions (medians, pooled histogram) and the
  Kruskal-Wallis heterogeneity across wings,
- the saturation shape: which decay model wins per wing and its parameter,
- how far the pooled novelty histograms of two palaces are from each other
  (Jensen-Shannon distance).

What an export cannot reproduce is ρ(A, B), the correlation between the
nearest-neighbour novelty and the LLE reconstruction residual: estimator B
needs the vectors. That comparison still requires running the full
pipeline on a snapshot of the other palace.
"""

from __future__ import annotations

import json
import math
from pathlib import Path


def load_exports(paths) -> dict:
    """``{label: stats}``; the label is the file stem."""
    exports = {}
    for path in paths:
        path = Path(path)
        stats = json.loads(path.read_text())
        if not str(stats.get("schema", "")).startswith("castle-info-stats/"):
            raise ValueError(f"{path}: not a castle info-stats export")
        exports[path.stem] = stats
    return exports


def pooled_histogram(stats: dict) -> tuple[list, list]:
    """Sum the per-wing novelty histograms of one palace; ``(edges, counts)``."""
    edges, counts = None, None
    for wing in stats["wings"].values():
        nov = wing.get("novelty")
        if not nov:
            continue
        if counts is None:
            edges, counts = nov["edges"], list(nov["counts"])
        elif nov["edges"] == edges:
            counts = [a + b for a, b in zip(counts, nov["counts"])]
    return edges or [], counts or []


def jensen_shannon(p_counts, q_counts) -> float | None:
    """Jensen-Shannon distance (base 2, in [0, 1]) between two histograms."""
    if not p_counts or not q_counts or len(p_counts) != len(q_counts):
        return None
    sp, sq = sum(p_counts), sum(q_counts)
    if not sp or not sq:
        return None
    p = [c / sp for c in p_counts]
    q = [c / sq for c in q_counts]
    m = [(a + b) / 2 for a, b in zip(p, q)]

    def kl(x, y):
        return sum(a * math.log2(a / b) for a, b in zip(x, y) if a > 0)

    return math.sqrt(max((kl(p, m) + kl(q, m)) / 2, 0.0))


def summarise(label: str, stats: dict) -> dict:
    wings = stats["wings"]
    medians = [
        w["novelty"]["median"]
        for w in wings.values()
        if w.get("novelty") and w["novelty"].get("median") is not None
    ]
    winners = {}
    taus, alphas = [], []
    for w in wings.values():
        fit = w.get("decay_fit") or {}
        winner = fit.get("winner")
        if winner:
            winners[winner] = winners.get(winner, 0) + 1
            if winner == "exponential":
                taus.append(fit["exponential"]["tau"])
            elif winner == "powerlaw":
                alphas.append(fit["powerlaw"]["alpha"])
    het = stats.get("heterogeneity") or {}
    return {
        "palace": label,
        "castle_version": stats.get("castle_version"),
        "embedder": (stats.get("embedder") or {}).get("model"),
        "drawers": stats["palace"]["drawers"],
        "wings": stats["palace"]["wings"],
        "wings_scored": len(medians),
        "novelty_median_of_wing_medians": _median(medians),
        "novelty_median_min": min(medians) if medians else None,
        "novelty_median_max": max(medians) if medians else None,
        "decay_winners": winners,
        "tau_median": _median(taus),
        "alpha_median": _median(alphas),
        "heterogeneity_epsilon_squared": het.get("epsilon_squared"),
        "heterogeneity_p": het.get("p_value"),
    }


def _median(values):
    vals = sorted(values)
    if not vals:
        return None
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def compare(exports: dict) -> dict:
    """Per-palace summaries plus pairwise distances between pooled histograms."""
    summaries = [summarise(label, stats) for label, stats in exports.items()]
    hists = {label: pooled_histogram(stats)[1] for label, stats in exports.items()}
    labels = list(exports)
    pairs = []
    for i, a in enumerate(labels):
        for b in labels[i + 1 :]:
            pairs.append(
                {"a": a, "b": b, "novelty_js_distance": jensen_shannon(hists[a], hists[b])}
            )
    return {"palaces": summaries, "pairs": pairs}


def format_markdown(result: dict) -> str:
    cols = [
        ("palace", "palace"),
        ("drawers", "drawers"),
        ("wings", "wings"),
        ("scored", "wings_scored"),
        ("novelty med", "novelty_median_of_wing_medians"),
        ("min", "novelty_median_min"),
        ("max", "novelty_median_max"),
        ("decay winners", "decay_winners"),
        ("τ med", "tau_median"),
        ("ε²", "heterogeneity_epsilon_squared"),
    ]
    lines = ["| " + " | ".join(h for h, _ in cols) + " |", "|" + "---|" * len(cols)]
    for s in result["palaces"]:
        cells = []
        for _, key in cols:
            v = s.get(key)
            if isinstance(v, float):
                cells.append(f"{v:.3f}")
            elif isinstance(v, dict):
                cells.append(", ".join(f"{k} {n}" for k, n in sorted(v.items())) or "-")
            else:
                cells.append("-" if v is None else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    if result["pairs"]:
        lines += ["", "| a | b | JS distance of pooled novelty |", "|---|---|---|"]
        for p in result["pairs"]:
            d = p["novelty_js_distance"]
            lines.append(f"| {p['a']} | {p['b']} | {'-' if d is None else f'{d:.3f}'} |")
    return "\n".join(lines)


def run(paths, out: Path | None = None) -> dict:
    result = compare(load_exports(paths))
    print(format_markdown(result))
    if out is not None:
        out.write_text(json.dumps(result, indent=2))
        print(f"\nWrote {out}")
    return result
