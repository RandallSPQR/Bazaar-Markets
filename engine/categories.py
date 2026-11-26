"""Engine 1.3.0 (plan 2026-11-27, Stage 1): category profiles, solvency and the rent gradient.

Everything here is off by default: with categories.profiles {}, sellers.solvency.enabled false and market.rent.alpha
0 the engine is 1.2.0 byte for byte (no extra draw, no extra field in any outcome or log).

Category profiles (categories.profiles.<cat>; config.CategoriesCfg documents the keys):
  - unit cost: with cost_share g and cheap_share s set, a stall of the category with true quality q has unit cost
    round(base x (c0 + c1 q)), never below 0, where c0 + c1 qh = g P1 / base and c0 + c1 ql = s g P1 / base, qh and ql
    the means of stalls.q_high and stalls.q_low and P1 the genuine posted price at rating 1.0 (base x (1 + premium x
    0.5) with brands on, else base, rounded to the cent as the price rule does). The price rule is unchanged.
  - fixed cost: round half up(fixed_cost_share x baseline_gross_cents) every morning the stall is in the market.
  - inspection: noise sigma (stream [seed, 41, day, buyer index, stall index]) and a cost multiplier on kappa.
  - reviews: review_accuracy (stream [seed, 43, day, stall index], one uniform per rated unit in purchase order).
Solvency (sellers.solvency): cash from start_cash_days x baseline; a stall below -credit_limit_days x baseline at a day's
end leaves the market at the end of that day (the 0.15.0 exit rule).
Rent (market.rent): alpha x table[stall id] every morning.
Fixed cost and rent are charged together in Stall.overhead_cents, part of the stall's profit.

1.3.1 (plan 2026-11-27, Randall's decision of 2026-11-26): seconds_cost_share gives seconds stalls their own cost target
(the category's cost line scaled for seconds only), and baseline_gross_by_type_cents sizes each stall's fixed cost to
its own type's baseline, floored at 0. Without these keys the engine is 1.3.0 exactly.
"""
from __future__ import annotations

import math

import numpy as np

PROFILE_KEYS = ("cost_share", "cheap_share", "baseline_gross_cents", "fixed_cost_share", "inspect_sigma",
                "inspect_cost_mult", "review_accuracy", "seconds_cost_share", "baseline_gross_by_type_cents")
STALL_TYPES = ("genuine", "seconds", "deceptive")
INSPECT_STREAM, REVIEW_STREAM = 41, 43


def _half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def _num(v, name, lo=None, hi=None):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f"{name} must be a finite number, got {v!r}")
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise ValueError(f"{name} must be in [{lo}, {hi}], got {v!r}")
    return float(v)


def profile(cfg, category: str) -> dict:
    return (cfg.categories.profiles or {}).get(category) or {}


def validate(cfg) -> None:
    profs = cfg.categories.profiles or {}
    if not isinstance(profs, dict):
        raise ValueError("categories.profiles must map categories to profiles")
    for cat, p in profs.items():
        if cat not in cfg.market.categories:
            raise ValueError(f"categories.profiles: unknown category {cat!r}")
        if not isinstance(p, dict) or set(p) - set(PROFILE_KEYS):
            raise ValueError(f"categories.profiles.{cat}: keys must be among {PROFILE_KEYS}, got {p!r}")
        if ("cost_share" in p) != ("cheap_share" in p):
            raise ValueError(f"categories.profiles.{cat}: cost_share and cheap_share go together")
        if "cost_share" in p:
            _num(p["cost_share"], f"{cat}.cost_share", 0.0)
            _num(p["cheap_share"], f"{cat}.cheap_share", 0.0)
        if "baseline_gross_cents" in p:
            _num(p["baseline_gross_cents"], f"{cat}.baseline_gross_cents")
        if "fixed_cost_share" in p:
            _num(p["fixed_cost_share"], f"{cat}.fixed_cost_share", 0.0)
            if p["fixed_cost_share"] and "baseline_gross_cents" not in p:
                raise ValueError(f"categories.profiles.{cat}: fixed_cost_share needs baseline_gross_cents")
        if "inspect_sigma" in p:
            _num(p["inspect_sigma"], f"{cat}.inspect_sigma", 0.0)
        if "inspect_cost_mult" in p:
            _num(p["inspect_cost_mult"], f"{cat}.inspect_cost_mult", 0.0)
        if "review_accuracy" in p:
            _num(p["review_accuracy"], f"{cat}.review_accuracy", 0.0, 1.0)
        if "seconds_cost_share" in p:
            if "cost_share" not in p:
                raise ValueError(f"categories.profiles.{cat}: seconds_cost_share needs cost_share and cheap_share")
            _num(p["seconds_cost_share"], f"{cat}.seconds_cost_share", 0.0)
        if "baseline_gross_by_type_cents" in p:
            bt = p["baseline_gross_by_type_cents"]
            if not isinstance(bt, dict) or set(bt) != set(STALL_TYPES):
                raise ValueError(f"categories.profiles.{cat}.baseline_gross_by_type_cents must map exactly "
                                 f"{STALL_TYPES} to cents, got {bt!r}")
            for k, v in bt.items():
                _num(v, f"{cat}.baseline_gross_by_type_cents.{k}")
    sv = cfg.sellers.solvency
    if sv.enabled:
        _num(sv.start_cash_days, "sellers.solvency.start_cash_days")
        _num(sv.credit_limit_days, "sellers.solvency.credit_limit_days", 0.0)
        for cat in cfg.market.categories:
            if "baseline_gross_cents" not in profile(cfg, cat):
                raise ValueError(f"sellers.solvency needs categories.profiles.{cat}.baseline_gross_cents")
    rc = cfg.market.rent
    a = _num(rc.alpha, "market.rent.alpha", 0.0, 1.0)
    if not isinstance(rc.table, dict):
        raise ValueError("market.rent.table must map stall ids to cents")
    for k, v in rc.table.items():
        _num(v, f"market.rent.table[{k!r}]")
    if a > 0:
        n = 2 * int(cfg.market.slots_per_side) * len(cfg.market.categories)
        missing = [f"s{i:02d}" for i in range(n) if f"s{i:02d}" not in rc.table]
        if missing:
            raise ValueError(f"market.rent.alpha > 0 needs a table entry for every stall; missing {missing[:3]}")
    g = cfg.buyers.gamma_by_profile or {}
    if not isinstance(g, dict) or set(g) - {"tourist", "local", "expert"}:
        raise ValueError(f"buyers.gamma_by_profile must map tourist / local / expert to numbers, got {g!r}")
    for k, v in g.items():
        _num(v, f"buyers.gamma_by_profile.{k}", 0.0)


# ------------------------------------------------------------------ unit cost

def genuine_price_at_top(cfg, category: str) -> int:
    base = cfg.pricing.base_price_cents[category]
    if not cfg.brands.enabled:
        return int(base)
    return int(round(base * 1.0 * (1 + cfg.brands.premium * (1.0 - 0.5))))


def cost_coefficients(cfg, category: str) -> tuple[float, float] | None:
    """(c0, c1) of the rescaled quality -> cost relation for a category with cost_share and cheap_share, else None."""
    p = profile(cfg, category)
    if "cost_share" not in p:
        return None
    base = cfg.pricing.base_price_cents[category]
    qh = (cfg.stalls.q_high[0] + cfg.stalls.q_high[1]) / 2
    ql = (cfg.stalls.q_low[0] + cfg.stalls.q_low[1]) / 2
    top = float(p["cost_share"]) * genuine_price_at_top(cfg, category) / base
    low = float(p["cheap_share"]) * top
    c1 = (top - low) / (qh - ql)
    return top - c1 * qh, c1


def seconds_price_at_top(cfg, category: str) -> int:
    """The seconds posted price at rating 1.0 (brands.premium_price with the seconds tier), else the neutral price."""
    base = cfg.pricing.base_price_cents[category]
    f = cfg.pricing.seconds_price_factor
    if not cfg.brands.enabled:
        return int(round(base * f))
    return int(round(base * f * (1 + cfg.brands.premium * (1.0 - 0.5))))


def seconds_scale(cfg, category: str) -> float | None:
    """1.3.1: the factor on the category's cost line that puts a seconds stall's unit cost at the cheap mean quality at
    seconds_cost_share x the seconds price at rating 1.0; None without seconds_cost_share."""
    p = profile(cfg, category)
    if "seconds_cost_share" not in p:
        return None
    c0, c1 = cost_coefficients(cfg, category)
    base = cfg.pricing.base_price_cents[category]
    ql = (cfg.stalls.q_low[0] + cfg.stalls.q_low[1]) / 2
    at_ql = base * (c0 + c1 * ql)
    target = float(p["seconds_cost_share"]) * seconds_price_at_top(cfg, category)
    return target / at_ql if at_ql > 0 else math.inf


def unit_cost(cfg, category: str, q: float, stype: str | None = None) -> int:
    """Unit cost in cents of a stall of `category` (and type `stype`) with true quality q. Without a cost profile this
    is exactly the 1.2.0 expression round(base x (unit_cost[0] + unit_cost[1] x q)). 1.3.1: a seconds stall of a
    category with seconds_cost_share has the category's line times seconds_scale (flat at the target if the line is 0
    at the cheap mean quality)."""
    pr = cfg.pricing
    base = pr.base_price_cents[category]
    cc = cost_coefficients(cfg, category) if cfg.categories.profiles else None
    if cc is None:
        return int(round(base * (pr.unit_cost[0] + pr.unit_cost[1] * float(q))))
    line = base * (cc[0] + cc[1] * float(q))
    if stype == "seconds":
        m = seconds_scale(cfg, category)
        if m is not None:
            if math.isinf(m):
                return max(0, int(round(float(profile(cfg, category)["seconds_cost_share"])
                                        * seconds_price_at_top(cfg, category))))
            line *= m
    return max(0, int(round(line)))


# ------------------------------------------------------------------ overhead and solvency

def fixed_cost(cfg, category: str, stype: str | None = None) -> int:
    """Daily fixed cost of a stall of `category`; 1.3.1: with baseline_gross_by_type_cents and a stall type, sized to
    that type's own baseline, floored at 0."""
    p = profile(cfg, category)
    if not p.get("fixed_cost_share"):
        return 0
    bt = p.get("baseline_gross_by_type_cents")
    if bt is not None and stype is not None:
        return _half_up(float(p["fixed_cost_share"]) * max(0.0, float(bt[stype])))
    return _half_up(float(p["fixed_cost_share"]) * float(p["baseline_gross_cents"]))


def rent(cfg, sid: str) -> int:
    a = float(cfg.market.rent.alpha)
    if a == 0:
        return 0
    return _half_up(a * float(cfg.market.rent.table[sid]))


def overhead_on(cfg) -> bool:
    return bool(float(cfg.market.rent.alpha) > 0 or any(fixed_cost(cfg, c, t) for c in cfg.market.categories
                                                        for t in (None, *STALL_TYPES)))


def solvency_on(cfg) -> bool:
    return bool(cfg.sellers.solvency.enabled)


def baseline(cfg, category: str) -> float:
    return float(profile(cfg, category)["baseline_gross_cents"])


def start_cash(cfg, category: str) -> int:
    return _half_up(float(cfg.sellers.solvency.start_cash_days) * baseline(cfg, category))


def credit_floor(cfg, category: str) -> float:
    return -float(cfg.sellers.solvency.credit_limit_days) * baseline(cfg, category)


# ------------------------------------------------------------------ inspection and reviews

def inspect_cost_cents(cfg, category: str, profile_name: str) -> int:
    """Inspection cost of a buyer of this profile at a stall of this category. Without a multiplier this is exactly the
    1.2.0 expression."""
    bc, base = cfg.buyers, cfg.pricing.base_price_cents[category]
    m = profile(cfg, category).get("inspect_cost_mult") if cfg.categories.profiles else None
    if m is None:
        return int(round(base * bc.inspect_cost_frac[profile_name]))
    return int(round(base * bc.inspect_cost_frac[profile_name] * float(m)))


def inspect_sigma(cfg, category: str) -> float:
    return float(profile(cfg, category).get("inspect_sigma", 0.0)) if cfg.categories.profiles else 0.0


def inspected_quality(cfg, sroot: tuple, day: int, buyer_index: int, stall, q: float) -> float:
    s = inspect_sigma(cfg, stall.category)
    if s == 0:
        return q
    z = float(np.random.default_rng([*sroot, INSPECT_STREAM, int(day), int(buyer_index), int(stall.idx)]).standard_normal())
    return round(min(1.0, max(0.0, float(q) + s * z)), 4)


def reviews_noisy(cfg) -> bool:
    return any(float(profile(cfg, c).get("review_accuracy", 1.0)) < 1.0 for c in cfg.market.categories) \
        if cfg.categories.profiles else False


def judge_reviews(cfg, sroot: tuple, day: int, purchases: list[dict], stalls_by_sid: dict) -> None:
    """Mark each rated purchase with judged_honest_units: per unit, the true honesty (q_true met the latest claim) kept
    with probability review_accuracy, else flipped; one uniform per unit in purchase order, per stall from
    default_rng([seed, 43, day, stall index]). Categories with accuracy 1 draw nothing and keep the truth."""
    gens: dict = {}
    for b in purchases:
        if not b["known_claims"]:
            continue
        st = stalls_by_sid[b["stall"]]
        acc = float(profile(cfg, st.category).get("review_accuracy", 1.0))
        honest = b["q_true"] >= b["known_claims"][-1] - 1e-12
        if acc >= 1.0:
            b["judged_honest_units"] = b["units"] if honest else 0
            continue
        g = gens.get(st.sid)
        if g is None:
            g = gens[st.sid] = np.random.default_rng([*sroot, REVIEW_STREAM, int(day), int(st.idx)])
        u = g.random(int(b["units"]))
        b["judged_honest_units"] = int(sum((honest if x < acc else not honest) for x in u))
