"""Across-seed statistics and reference normalisation.

The replication unit is the seed. Intervals are t-intervals over per-seed
values. Condition comparisons use paired seeds: the same seed list in both
conditions, with the interval taken over per-seed differences.
"""
from __future__ import annotations

import copy
import math

import numpy as np

# Two-sided 95% t critical values for df = 1..30 (beyond 30, 1.96 is close enough).
_T95 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145,
        2.131, 2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048,
        2.045, 2.042]


def t95(df: int) -> float:
    return _T95[df - 1] if 1 <= df <= len(_T95) else 1.96


def mean_ci(xs) -> dict:
    x = np.array([v for v in xs if v is not None and not (isinstance(v, float) and math.isnan(v))], float)
    n = len(x)
    if n == 0:
        return {"n": 0, "mean": None, "lo": None, "hi": None}
    m = float(x.mean())
    if n == 1:
        return {"n": 1, "mean": m, "lo": None, "hi": None}
    h = t95(n - 1) * float(x.std(ddof=1)) / math.sqrt(n)
    return {"n": n, "mean": m, "lo": m - h, "hi": m + h}


def paired_diff(a: list, b: list) -> dict:
    """Mean and 95% CI of b - a over seeds where both are defined."""
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    return mean_ci([y - x for x, y in pairs])


def normalise(value: float | None, floor: float | None, ceiling: float | None) -> float | None:
    """(value - floor) / (ceiling - floor). 0 = random buyer, 1 = perfect-information buyer."""
    if value is None or floor is None or ceiling is None or ceiling == floor:
        return None
    return (value - floor) / (ceiling - floor)


def reference_configs(cfg) -> dict:
    """Same world and seed, with the buyer policy swapped for each reference agent."""
    out = {}
    for name, policy in (("floor", "random_buyer"), ("ceiling", "perfect_buyer")):
        c = copy.deepcopy(cfg)
        c.agents.buyer = policy
        out[name] = c
    return out


def normalised_outcomes(out: dict, floor: dict, ceiling: dict) -> dict:
    """Normalised surplus and shortfall. For shortfall, lower is better, so the
    scale is inverted: 1 means as few shortfalls as the perfect buyer."""
    s = normalise(out["buyer_surplus_mean_cents"], floor["buyer_surplus_mean_cents"],
                  ceiling["buyer_surplus_mean_cents"])
    sf = None
    if out["shortfall_rate"] is not None and floor["shortfall_rate"] is not None:
        c = ceiling["shortfall_rate"] or 0.0
        sf = normalise(-out["shortfall_rate"], -floor["shortfall_rate"], -c)
    return {"surplus_norm": s, "shortfall_norm": sf,
            "surplus_floor": floor["buyer_surplus_mean_cents"], "surplus_ceiling": ceiling["buyer_surplus_mean_cents"],
            "shortfall_floor": floor["shortfall_rate"], "shortfall_ceiling": ceiling["shortfall_rate"]}
