"""`castle info-stats`: shareable statistics without any drawer content."""

from __future__ import annotations

import json
import math
from unittest.mock import patch

from cognitive_castle import info_stats


def _dim(collection) -> int:
    return collection._table.schema.field("vector").type.list_size


def _unit(vec, dim):
    v = list(vec) + [0.0] * (dim - len(vec))
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _seed(collection, wing, rows, *, room="r"):
    """``rows`` = list of (id, filed_at, vector_prefix, text)."""
    dim = _dim(collection)
    collection.add(
        documents=[text for _, _, _, text in rows],
        ids=[i for i, _, _, _ in rows],
        metadatas=[
            {"wing": wing, "room": room, "source_file": f"/s/{wing}", "filed_at": filed_at}
            for _, filed_at, _, _ in rows
        ],
        embeddings=[_unit(v, dim) for _, _, v, _ in rows],
    )


def test_histogram_bins_and_edges():
    h = info_stats.histogram([0.0, 0.04, 0.05, 0.99, 1.0, 1.7, 2.0], info_stats.NOVELTY_EDGES)
    assert sum(h["counts"]) == 7
    assert h["counts"][0] == 2  # 0.0 and 0.04 in [0, 0.05)
    assert h["counts"][1] == 1  # 0.05 in [0.05, 0.10)
    assert h["counts"][-1] == 3  # 1.0, 1.7 and 2.0 in the closed tail bin
    assert h["edges"][-1] == 2.0
    assert info_stats.histogram([5, 10**9], info_stats.TEXT_EDGES)["edges"][-1] is None


def test_quantiles():
    q = info_stats.quantiles([3, 1, 2, 4])
    assert q == {"n": 4, "mean": 2.5, "p25": 1.75, "median": 2.5, "p75": 3.25, "p90": 3.7}
    assert info_stats.quantiles([])["median"] is None


def test_collect_stats_contains_no_content(collection, palace_path):
    rows_a = [
        (f"a{i}", f"2026-01-{i + 1:02d}T00:00:00", [1.0, 0.01 * i], f"alpha {i}") for i in range(25)
    ]
    rows_b = [
        (f"b{i}", f"2026-02-{i + 1:02d}T00:00:00", [0.0, 1.0, 0.1 * i], f"beta {i}")
        for i in range(25)
    ]
    _seed(collection, "wing_alpha", rows_a)
    _seed(collection, "wing_beta", rows_b)
    _seed(collection, "tiny", [("t0", "2026-03-01T00:00:00", [0.0, 0.0, 1.0], "secret text")])

    stats = info_stats.collect_stats(palace_path, sample=10, seed=1)

    assert stats["schema"] == info_stats.SCHEMA
    assert stats["palace"] == {"drawers": 51, "wings": 3, "without_filed_at": 0}
    # Wings are aliased by size; nothing names the wing, a drawer or a path.
    assert set(stats["wings"]) == {"w01", "w02", "w03"}
    dumped = json.dumps(stats)
    for forbidden in ("wing_alpha", "wing_beta", "tiny", "secret", "alpha 3", "/s/", "a0", "b1"):
        assert forbidden not in dumped
    big = [w for w in stats["wings"].values() if w["drawers"] == 25]
    assert len(big) == 2
    for w in big:
        nov = w["novelty"]
        assert nov["sampled"] == 10
        assert sum(nov["counts"]) + nov["first_in_wing"] == 10
        assert 0.0 <= nov["median"] <= 2.0
        assert w["text_chars"]["n"] == 25
        assert w["rooms"] == 1
    small = stats["wings"]["w03"]
    assert small["drawers"] == 1 and small["novelty"] is None and small["decay_fit"] is None


def test_novelty_uses_only_prior_drawers_of_the_same_wing(collection, palace_path):
    """The first drawer of a wing has no prior neighbour; a later duplicate
    of it has novelty 0, even though an identical vector sits in another wing."""
    _seed(collection, "one", [("o0", "2026-01-01T00:00:00", [1.0], "x")])
    rows = [("d0", "2026-01-01T00:00:00", [1.0], "x")] + [
        (f"d{i}", f"2026-01-{i + 1:02d}T00:00:00", [1.0], "x") for i in range(1, 20)
    ]
    _seed(collection, "two", rows)

    stats = info_stats.collect_stats(palace_path, sample=20, keep_wing_names=True)

    nov = stats["wings"]["two"]["novelty"]
    assert nov["first_in_wing"] == 1
    assert nov["n"] == 19
    assert nov["median"] < 1e-5
    assert stats["wings"]["one"]["novelty"] is None  # below MIN_WING_ROWS


def test_wing_aliases_and_kept_names(collection, palace_path):
    _seed(collection, "secret_project", [("s0", "2026-01-01T00:00:00", [1.0], "x")])
    _seed(collection, "other", [("x0", "2026-01-01T00:00:00", [1.0], "x")])

    aliased = info_stats.collect_stats(palace_path, wing_aliases={"secret_project": "proj"})
    # Equal sizes: "other" sorts first and keeps its number; the alias replaces w02.
    assert set(aliased["wings"]) == {"w01", "proj"}

    named = info_stats.collect_stats(palace_path, keep_wing_names=True)
    assert set(named["wings"]) == {"secret_project", "other"}


def test_fit_decay_recovers_an_exponential():
    order = list(range(1, 201))
    novelty = [0.1 + 0.6 * math.exp(-n / 40) for n in order]
    fit = info_stats.fit_decay(order, novelty)
    if fit is None:  # scipy absent
        return
    assert fit["winner"] == "exponential"
    assert abs(fit["exponential"]["tau"] - 40) < 2
    assert info_stats.fit_decay([1, 2, 3], [0.5, 0.4, 0.3]) is None


def test_heterogeneity_needs_two_wings():
    assert info_stats.heterogeneity({"a": [0.1] * 25}) is None
    het = info_stats.heterogeneity(
        {"a": [0.1 + i * 0.001 for i in range(25)], "b": [0.5 + i * 0.001 for i in range(25)]}
    )
    if het is not None:
        assert het["p_value"] < 0.01 and het["wings"] == ["a", "b"]


def test_format_report_mentions_every_wing():
    stats = {
        "palace": {"drawers": 3, "wings": 1},
        "sampling": {"per_wing": 5, "seed": 1},
        "wings": {
            "w01": {
                "drawers": 3,
                "rooms": 1,
                "novelty": {"median": 0.2, "p75": 0.3},
                "decay_fit": {"winner": "exponential", "exponential": {"tau": 12.0}},
            }
        },
        "heterogeneity": None,
    }
    text = info_stats.format_report(stats)
    assert "w01" in text and "exp τ=12" in text and "0.200" in text


def test_cli_info_stats_exports_a_file(tmp_path, capsys):
    from cognitive_castle import cli

    fake = {
        "schema": info_stats.SCHEMA,
        "palace": {"drawers": 1, "wings": 1},
        "sampling": {"per_wing": 5, "seed": 1},
        "wings": {"w01": {"drawers": 1, "rooms": 1, "novelty": None, "decay_fit": None}},
        "heterogeneity": None,
    }
    out = tmp_path / "stats.json"
    with patch("cognitive_castle.info_stats.collect_stats", return_value=fake) as run:
        with patch(
            "sys.argv",
            [
                "castle",
                "info-stats",
                "--export",
                str(out),
                "--sample",
                "5",
                "--seed",
                "1",
                "--wing-alias",
                "a=b",
                "--keep-wing-names",
            ],
        ):
            cli.main()

    run.assert_called_once_with(
        None, sample=5, seed=1, wing_aliases={"a": "b"}, keep_wing_names=True
    )
    assert json.loads(out.read_text())["schema"] == info_stats.SCHEMA
    assert str(out) in capsys.readouterr().out
