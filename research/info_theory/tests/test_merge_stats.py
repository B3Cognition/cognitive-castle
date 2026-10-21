"""merge-stats: cross-palace comparison of castle info-stats exports."""

from __future__ import annotations

import json

from analysis import merge_stats


def _export(drawers, median, tau, counts):
    edges = [round(i * 0.05, 2) for i in range(21)] + [2.0]
    return {
        "schema": "castle-info-stats/1",
        "castle_version": "3.4.1",
        "embedder": {"model": "m", "dim": 4},
        "palace": {"drawers": drawers, "wings": 2, "without_filed_at": 0},
        "wings": {
            "w01": {
                "drawers": drawers - 10,
                "rooms": 2,
                "novelty": {"edges": edges, "counts": counts, "median": median, "n": sum(counts)},
                "decay_fit": {"winner": "exponential", "exponential": {"tau": tau}},
            },
            "w02": {"drawers": 10, "rooms": 1, "novelty": None, "decay_fit": None},
        },
        "heterogeneity": {"epsilon_squared": 0.08, "p_value": 0.0},
    }


def test_compare_two_exports(tmp_path):
    low = [20] + [0] * 20
    high = [0] * 20 + [20]
    a = tmp_path / "palace_a.json"
    b = tmp_path / "palace_b.json"
    a.write_text(json.dumps(_export(100, 0.05, 30.0, low)))
    b.write_text(json.dumps(_export(500, 0.60, 90.0, high)))

    result = merge_stats.run([a, b], out=tmp_path / "merged.json")

    palaces = {p["palace"]: p for p in result["palaces"]}
    assert palaces["palace_a"]["drawers"] == 100
    assert palaces["palace_a"]["novelty_median_of_wing_medians"] == 0.05
    assert palaces["palace_b"]["tau_median"] == 90.0
    assert palaces["palace_b"]["decay_winners"] == {"exponential": 1}
    [pair] = result["pairs"]
    assert pair["novelty_js_distance"] == 1.0  # disjoint histograms
    assert (tmp_path / "merged.json").exists()
    md = merge_stats.format_markdown(result)
    assert "palace_a" in md and "palace_b" in md


def test_identical_histograms_have_zero_distance():
    assert merge_stats.jensen_shannon([1, 2, 3], [2, 4, 6]) == 0.0
    assert merge_stats.jensen_shannon([], []) is None


def test_rejects_other_json(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{}")
    try:
        merge_stats.load_exports([p])
    except ValueError as e:
        assert "not a castle info-stats export" in str(e)
    else:
        raise AssertionError("expected ValueError")
