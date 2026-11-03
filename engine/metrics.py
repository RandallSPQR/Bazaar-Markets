"""Across-seed statistics and reference comparisons.

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


def relative(value: float | None, random_ref: float | None, informed_ref: float | None) -> float | None:
    """(value - random_ref) / (informed_ref - random_ref).

    0 = the random reference's outcome, 1 = the informed reference's. These are
    comparison points, not bounds, so the score can be below 0 or above 1. Undefined
    (None) when any input is undefined or the references coincide."""
    if value is None or random_ref is None or informed_ref is None or informed_ref == random_ref:
        return None
    return (value - random_ref) / (informed_ref - random_ref)


def reference_configs(cfg) -> dict:
    """Same world and seed, with the buyer policy swapped for each reference agent."""
    out = {}
    for name, policy in (("random_ref", "random_reference"), ("informed_ref", "informed_reference")):
        c = copy.deepcopy(cfg)
        c.agents.buyer = policy
        out[name] = c
    return out


def relative_outcomes(out: dict, random_ref: dict, informed_ref: dict) -> dict:
    """Surplus and shortfall relative to the two references. Raw outcomes stay
    primary; report these alongside them. For shortfall, lower is better, so the
    scale is inverted (1 = as few shortfalls as the informed reference). A shortfall
    rate is undefined when there were no purchases, and then so is the score: an
    undefined rate is never treated as zero shortfall."""
    s = relative(out["buyer_surplus_mean_cents"], random_ref["buyer_surplus_mean_cents"],
                 informed_ref["buyer_surplus_mean_cents"])
    rates = (out["shortfall_rate"], random_ref["shortfall_rate"], informed_ref["shortfall_rate"])
    sf = None if any(r is None for r in rates) else relative(-rates[0], -rates[1], -rates[2])
    return {"surplus_rel": s, "shortfall_rel": sf,
            "surplus_random_ref": random_ref["buyer_surplus_mean_cents"],
            "surplus_informed_ref": informed_ref["buyer_surplus_mean_cents"],
            "shortfall_random_ref": random_ref["shortfall_rate"],
            "shortfall_informed_ref": informed_ref["shortfall_rate"]}
