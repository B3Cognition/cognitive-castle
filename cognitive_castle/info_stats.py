"""Distributional statistics of a palace, safe to share: ``castle info-stats``.

The v3.4.x information-theory research was measured on one palace. Its
claims (novelty distribution per wing, wing heterogeneity, the shape of the
saturation curve) can only be checked against a *second*, structurally
different palace, and nobody should have to hand over their memories for
that. This module computes statistics that describe the palace without
containing it:

- per-wing drawer and room counts,
- a histogram of drawer text lengths,
- a histogram and quantiles of nearest-neighbour novelty (estimator A of the
  paper: ``1 - max cosine`` against the drawers filed *before* each sampled
  drawer, within its wing),
- decay fits of novelty over filing order (exponential vs power law, AIC),
- a Kruskal-Wallis test of novelty across wings.

Nothing else leaves the machine: no text, no vectors, no drawer ids, no
source paths, and wing names only when the user keeps or aliases them. The
export is a JSON file the user can read before sharing it by hand; the
research pipeline's ``merge-stats`` command compares several such files.

The sample is read in two streaming passes over the LanceDB table (ids and
metadata, then vectors), so the memory needed is that of one batch plus
the sample, not of the palace.
"""

from __future__ import annotations

import json
import math
import os
import random
import time
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from .config import CognitiveCastleConfig
from .version import __version__

SCHEMA = "castle-info-stats/1"

#: Novelty bins: 0.05 wide up to 1.0, one tail bin to the theoretical max of 2.
NOVELTY_EDGES = [round(i * 0.05, 2) for i in range(21)] + [2.0]
#: Drawer text length bins (characters).
TEXT_EDGES = [0, 100, 200, 400, 800, 1600, 3200, 10_000, 100_000, 1_000_000, math.inf]
#: Wings with fewer drawers get counts only: a novelty sample this small
#: says nothing and a decay fit on it would be noise.
MIN_WING_ROWS = 20
#: Minimum non-first novelty points for a decay fit.
MIN_FIT_POINTS = 30


class InfoStatsError(RuntimeError):
    """The palace cannot be read the way the statistics need."""


# ---------------------------------------------------------------------------
# Small numeric helpers (no numpy needed for these)
# ---------------------------------------------------------------------------


def histogram(values, edges) -> dict:
    """Counts per bin ``[edges[i], edges[i+1])``; the last bin is closed."""
    counts = [0] * (len(edges) - 1)
    for v in values:
        i = bisect_left(edges, v)
        # bisect_left gives the first edge >= v; the bin is the one before it,
        # except when v sits exactly on an edge, which belongs to the bin after.
        if i < len(edges) and edges[i] == v:
            i += 1
        i -= 1
        if i < 0:
            i = 0
        if i >= len(counts):
            i = len(counts) - 1
        counts[i] += 1
    return {"edges": [e if math.isfinite(e) else None for e in edges], "counts": counts}


def quantiles(values) -> dict:
    vals = sorted(values)
    n = len(vals)
    if n == 0:
        return {"n": 0, "mean": None, "p25": None, "median": None, "p75": None, "p90": None}

    def q(p: float) -> float:
        pos = p * (n - 1)
        lo = int(pos)
        hi = min(lo + 1, n - 1)
        return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)

    return {
        "n": n,
        "mean": sum(vals) / n,
        "p25": q(0.25),
        "median": q(0.5),
        "p75": q(0.75),
        "p90": q(0.9),
    }


def _parse_meta(raw) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {}


# ---------------------------------------------------------------------------
# Pass 1: counts, text lengths, filing order, the sample
# ---------------------------------------------------------------------------


class _WingPass1:
    __slots__ = ("drawers", "rooms", "text_lengths", "filed_at", "sample", "seen")

    def __init__(self):
        self.drawers = 0
        self.rooms: set = set()
        self.text_lengths: list = []
        self.filed_at: list = []  # of drawers that have one
        self.sample: list = []  # (id, filed_at) reservoir
        self.seen = 0  # drawers with filed_at seen so far (reservoir counter)


def _iter_pass1(col, batch_size: int):
    """Yield dict batches of id / wing / room / metadata_json / text_len.

    The text length is computed by LanceDB (``length(text)``) so the text
    column never reaches Python; versions without SQL projections fall back
    to reading the text and measuring it here.
    """
    columns = {
        "id": "id",
        "wing": "wing",
        "room": "room",
        "metadata_json": "metadata_json",
        "text_len": "length(text)",
    }
    try:
        for batch in col.iter_columns(columns, batch_size):
            yield batch
        return
    except Exception:  # SQL projection unsupported: fall back below
        pass
    for batch in col.iter_columns(["id", "wing", "room", "metadata_json", "text"], batch_size):
        batch["text_len"] = [len(t or "") for t in batch.pop("text")]
        yield batch


def _pass1(col, *, sample: int, seed: int, batch_size: int) -> tuple[dict, int]:
    wings: dict[str, _WingPass1] = defaultdict(_WingPass1)
    rng = random.Random(seed)
    without_filed_at = 0
    for batch in _iter_pass1(col, batch_size):
        for drawer_id, wing, room, raw, text_len in zip(
            batch["id"], batch["wing"], batch["room"], batch["metadata_json"], batch["text_len"]
        ):
            w = wings[wing or ""]
            w.drawers += 1
            w.rooms.add(room or "")
            w.text_lengths.append(int(text_len or 0))
            filed_at = _parse_meta(raw).get("filed_at")
            if not filed_at:
                without_filed_at += 1
                continue
            w.filed_at.append(filed_at)
            # Reservoir sampling (Algorithm R): every drawer with a filing
            # time has the same chance to be sampled, in one pass.
            w.seen += 1
            if len(w.sample) < sample:
                w.sample.append((drawer_id, filed_at))
            else:
                j = rng.randrange(w.seen)
                if j < sample:
                    w.sample[j] = (drawer_id, filed_at)
    return dict(wings), without_filed_at


# ---------------------------------------------------------------------------
# Pass 2: nearest prior neighbour of every sampled drawer, within its wing
# ---------------------------------------------------------------------------


def _unit(matrix):
    import numpy as np

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def _sample_vectors(col, wings: dict) -> dict:
    """``{wing: (ids, filed_ats, unit vectors)}`` for every wing's sample."""
    import numpy as np

    out = {}
    for wing, w in wings.items():
        if not w.sample:
            continue
        ids = [i for i, _ in w.sample]
        rows = {}
        for start in range(0, len(ids), 500):
            for row in col.get_by_ids(ids[start : start + 500]):
                rows[row["id"]] = row.get("vector")
        kept = [(i, f) for i, f in w.sample if rows.get(i) is not None]
        if not kept:
            continue
        vectors = np.asarray([rows[i] for i, _ in kept], dtype=np.float32)
        out[wing] = ([i for i, _ in kept], [f for _, f in kept], _unit(vectors))
    return out


def _pass2(col, samples: dict, *, batch_size: int) -> dict:
    """``{wing: [max prior cosine per sampled drawer]}``, -inf when no prior."""
    import numpy as np

    best = {wing: np.full(len(ids), -np.inf) for wing, (ids, _, _) in samples.items()}
    sample_ids = {wing: {i: k for k, i in enumerate(ids)} for wing, (ids, _, _) in samples.items()}
    sample_filed = {wing: np.array(filed) for wing, (_, filed, _) in samples.items()}

    for batch in col.iter_columns(["id", "wing", "vector", "metadata_json"], batch_size):
        by_wing: dict[str, list[int]] = defaultdict(list)
        for k, wing in enumerate(batch["wing"]):
            if (wing or "") in samples:
                by_wing[wing or ""].append(k)
        for wing, rows in by_wing.items():
            filed = [_parse_meta(batch["metadata_json"][k]).get("filed_at") for k in rows]
            keep = [k for k, f in zip(rows, filed) if f]
            if not keep:
                continue
            filed_arr = np.array([f for f in filed if f])
            vectors = _unit(np.asarray([batch["vector"][k] for k in keep], dtype=np.float32))
            sims = vectors @ samples[wing][2].T  # rows × sample
            # Prior only: a drawer counts as a neighbour of a sampled drawer
            # when it was filed strictly before it; a drawer is never its own
            # neighbour (ties on filed_at are excluded with it).
            prior = filed_arr[:, None] < sample_filed[wing][None, :]
            ids_here = [batch["id"][k] for k in keep]
            for r, drawer_id in enumerate(ids_here):
                pos = sample_ids[wing].get(drawer_id)
                if pos is not None:
                    prior[r, pos] = False
            sims = np.where(prior, sims, -np.inf)
            best[wing] = np.maximum(best[wing], sims.max(axis=0))
    return best


# ---------------------------------------------------------------------------
# Fits and tests (scipy is optional: without it the fields are null)
# ---------------------------------------------------------------------------


def fit_decay(order, novelty) -> Optional[dict]:
    """Exponential ``c + (a - c) exp(-N/tau)`` vs power law ``a N^-alpha`` by AIC."""
    if len(novelty) < MIN_FIT_POINTS:
        return None
    try:
        import numpy as np
        from scipy.optimize import curve_fit
    except ImportError:
        return None

    N = np.asarray(order, dtype=float)
    y = np.asarray(novelty, dtype=float)
    n = len(y)
    result: dict = {}

    def aic(resid, k):
        rss = float(np.sum(resid**2))
        return n * math.log(max(rss, 1e-12) / n) + 2 * k

    try:

        def exponential(N, a, c, tau):
            return c + (a - c) * np.exp(-N / tau)

        (a, c, tau), _ = curve_fit(
            exponential, N, y, p0=[y[:5].mean(), y[-5:].mean(), max(N.max() / 4, 1.0)], maxfev=5000
        )
        result["exponential"] = {
            "a": float(a),
            "c": float(c),
            "tau": float(tau),
            "aic": aic(y - exponential(N, a, c, tau), 3),
        }
    except (RuntimeError, ValueError):
        result["exponential"] = None
    try:

        def powerlaw(N, a, alpha):
            return a * N ** (-alpha)

        (a, alpha), _ = curve_fit(powerlaw, N, y, p0=[max(y.mean(), 1e-3), 0.1], maxfev=5000)
        result["powerlaw"] = {
            "a": float(a),
            "alpha": float(alpha),
            "aic": aic(y - powerlaw(N, a, alpha), 2),
        }
    except (RuntimeError, ValueError):
        result["powerlaw"] = None

    fitted = {k: v for k, v in result.items() if v is not None}
    result["winner"] = min(fitted, key=lambda k: fitted[k]["aic"]) if fitted else None
    result["n"] = n
    return result


def heterogeneity(groups: dict) -> Optional[dict]:
    """Kruskal-Wallis across wings with epsilon-squared effect size."""
    groups = {k: v for k, v in groups.items() if len(v) >= MIN_WING_ROWS}
    if len(groups) < 2:
        return None
    try:
        from scipy import stats
    except ImportError:
        return None
    H, p = stats.kruskal(*groups.values())
    n = sum(len(v) for v in groups.values())
    k = len(groups)
    return {
        "H": float(H),
        "p_value": float(p),
        "epsilon_squared": float(max((H - k + 1) / max(n - k, 1), 0.0)),
        "wings": sorted(groups),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _aliases(wings: dict, aliases: Optional[dict], keep_names: bool) -> dict:
    """Wing name → published name. Unnamed wings become ``w01``… by size."""
    aliases = dict(aliases or {})
    out = {}
    by_size = sorted(wings, key=lambda w: (-wings[w].drawers, w))
    for k, wing in enumerate(by_size, start=1):
        if wing in aliases:
            out[wing] = aliases[wing]
        elif keep_names:
            out[wing] = wing
        else:
            out[wing] = f"w{k:02d}"
    return out


def collect_stats(
    palace_path: Optional[str] = None,
    *,
    sample: int = 200,
    seed: int = 42,
    wing_aliases: Optional[dict] = None,
    keep_wing_names: bool = False,
    batch_size: int = 10_000,
) -> dict:
    """Compute the shareable statistics of the palace at ``palace_path``.

    ``sample`` drawers per wing are scored (reservoir sample over the drawers
    that carry a filing time; ``seed`` makes it reproducible). Wings are
    published under ``wing_aliases`` when given, under their own name with
    ``keep_wing_names``, and as ``w01``, ``w02``… (largest first) otherwise.
    """
    from .palace import get_collection

    started = time.time()
    cfg = CognitiveCastleConfig()
    palace = os.path.expanduser(palace_path) if palace_path else cfg.palace_path
    col = get_collection(palace, collection_name="castle_drawers", create=False)
    if not hasattr(col, "iter_columns"):
        raise InfoStatsError("info-stats needs the LanceDB backend (streaming column reads)")

    wings, without_filed_at = _pass1(col, sample=sample, seed=seed, batch_size=batch_size)
    scored = {w: p for w, p in wings.items() if p.drawers >= MIN_WING_ROWS}
    samples = _sample_vectors(col, scored)
    best = _pass2(col, samples, batch_size=batch_size) if samples else {}

    names = _aliases(wings, wing_aliases, keep_wing_names)
    report_wings: dict = {}
    novelty_by_wing: dict = {}
    for wing, p in wings.items():
        entry: dict = {
            "drawers": p.drawers,
            "rooms": len(p.rooms),
            "with_filed_at": len(p.filed_at),
            "text_chars": {**histogram(p.text_lengths, TEXT_EDGES), **quantiles(p.text_lengths)},
            "novelty": None,
            "decay_fit": None,
        }
        if wing in best:
            ids, filed, _ = samples[wing]
            order_index = sorted(p.filed_at)
            novelty, order, first = [], [], 0
            for k, max_cos in enumerate(best[wing]):
                if not math.isfinite(max_cos):
                    first += 1  # nothing filed before it: novelty 1 by definition
                    continue
                novelty.append(1.0 - float(max_cos))
                order.append(bisect_left(order_index, filed[k]) + 1)
            entry["novelty"] = {
                "sampled": len(ids),
                "first_in_wing": first,
                **histogram(novelty, NOVELTY_EDGES),
                **quantiles(novelty),
            }
            entry["decay_fit"] = fit_decay(order, novelty)
            novelty_by_wing[names[wing]] = novelty
        report_wings[names[wing]] = entry

    return {
        "schema": SCHEMA,
        "castle_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "embedder": {"model": cfg.embedder_model, "dim": cfg.embedder_dim},
        "sampling": {"per_wing": sample, "seed": seed, "prior_only": True, "within_wing": True},
        "palace": {
            "drawers": sum(p.drawers for p in wings.values()),
            "wings": len(wings),
            "without_filed_at": without_filed_at,
        },
        "wings": dict(sorted(report_wings.items())),
        "heterogeneity": heterogeneity(novelty_by_wing),
        "elapsed_s": round(time.time() - started, 2),
    }


def format_report(stats: dict) -> str:
    """Human-readable summary of ``collect_stats`` output."""
    lines = [
        f"Palace: {stats['palace']['drawers']:,} drawers in {stats['palace']['wings']} wings "
        f"({stats['sampling']['per_wing']} sampled per wing, seed {stats['sampling']['seed']})",
        "",
        f"  {'wing':<28} {'drawers':>9} {'rooms':>6} {'novelty med':>12} {'p75':>6} {'decay':>12}",
    ]
    for name, w in stats["wings"].items():
        nov = w["novelty"]
        fit = w["decay_fit"] or {}
        winner = fit.get("winner")
        decay = "-"
        if winner == "exponential":
            decay = f"exp τ={fit['exponential']['tau']:.0f}"
        elif winner == "powerlaw":
            decay = f"pow α={fit['powerlaw']['alpha']:.2f}"
        med = f"{nov['median']:.3f}" if nov and nov["median"] is not None else "-"
        p75 = f"{nov['p75']:.3f}" if nov and nov["p75"] is not None else "-"
        lines.append(
            f"  {name[:28]:<28} {w['drawers']:>9,} {w['rooms']:>6} {med:>12} {p75:>6} {decay:>12}"
        )
    het = stats.get("heterogeneity")
    if het:
        lines += [
            "",
            f"  Wing heterogeneity (Kruskal-Wallis): H={het['H']:.1f}, p={het['p_value']:.2g}, "
            f"ε²={het['epsilon_squared']:.3f}",
        ]
    lines += [
        "",
        "  Nothing above identifies a drawer: no text, vectors, ids or paths are included.",
    ]
    return "\n".join(lines)
