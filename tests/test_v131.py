"""Engine 1.3.1 (plan 2026-11-27, Randall's decision of 2026-11-26): seconds cost target and fixed cost by stall type.

Without the new keys the engine is 1.3.0 exactly (the 1.3.0 tests in tests/test_v130.py and the reference digests still
pass). seconds_cost_share puts a seconds stall's unit cost at the cheap mean quality at that share of the seconds price
at rating 1.0, and leaves genuine and deceptive stalls (bust-outs included) on the category's line.
baseline_gross_by_type_cents sizes each stall's fixed cost to its own type's baseline, floored at 0; start cash and
the credit limit stay on baseline_gross_cents.
"""
import json

import pytest

from engine import ENGINE_VERSION, bazaar
from engine import brands as B
from engine import categories as CAT
from engine.config import load

REF = "configs/reference_1_0.json"
CATS = ("fish", "electronics", "designer")
COST = {"fish": (0.70, 0.80), "electronics": (0.77, 0.55), "designer": (0.20, 0.30)}


def cfg(*ov, days=3, seed=7):
    return load(REF, [f"market.days={days}", f"seed={seed}", *ov])


def prof(d):
    return f"categories.profiles={json.dumps(d)}"


def run(c):
    return json.loads(json.dumps(bazaar.run(c)))


def costs(extra=None):
    return {c: {"cost_share": g, "cheap_share": s, **(extra(c) if extra else {})} for c, (g, s) in COST.items()}


def test_version():
    assert ENGINE_VERSION == "1.3.1"


def test_without_new_keys_is_130():
    p = costs(lambda c: {"baseline_gross_cents": 1000, "fixed_cost_share": 0.5})
    base = run(cfg(prof(p), "sellers.solvency.enabled=true"))
    # the 1.3.0 expressions, by hand, for every stall of a fresh engine
    c = cfg(prof(p), "sellers.solvency.enabled=true")
    eng = bazaar.BazaarEngine(c)
    for st in eng.stalls:
        assert st.overhead_cents == 500
        assert abs(st.unit_cost_cents - CAT.unit_cost(c, st.category, st.q_true)) <= 1
    assert base == run(cfg(prof(p), "sellers.solvency.enabled=true"))


# ------------------------------------------------------------------ seconds cost target

@pytest.mark.parametrize("cat", CATS)
def test_seconds_cost_target_to_the_cent(cat):
    g, s = COST[cat]
    c = cfg(prof(costs(lambda k: {"seconds_cost_share": COST[k][0]})))
    ql = sum(c.stalls.q_low) / 2
    qh = sum(c.stalls.q_high) / 2
    base = c.pricing.base_price_cents[cat]
    ps = CAT.seconds_price_at_top(c, cat)
    assert ps == round(base * c.pricing.seconds_price_factor * 1.2)
    assert abs(CAT.unit_cost(c, cat, ql, "seconds") - g * ps) <= 0.5
    # genuine and deceptive keep the category line (1.3.0 targets)
    p1 = CAT.genuine_price_at_top(c, cat)
    for t in ("genuine", "deceptive", None):
        assert abs(CAT.unit_cost(c, cat, qh, t) - g * p1) <= 0.5
        assert abs(CAT.unit_cost(c, cat, ql, t) - s * g * p1) <= 0.5
    # the seconds line is the category line times one factor
    m = CAT.seconds_scale(c, cat)
    for q in (0.15, 0.3, 0.45):
        line = base * sum(x * y for x, y in zip(CAT.cost_coefficients(c, cat), (1.0, q)))
        assert CAT.unit_cost(c, cat, q, "seconds") == max(0, int(round(line * m)))


def test_seconds_costs_reach_seconds_stalls_only():
    c0 = cfg(prof(costs()))
    c1 = cfg(prof(costs(lambda k: {"seconds_cost_share": COST[k][0]})))
    e0, e1 = bazaar.BazaarEngine(c0), bazaar.BazaarEngine(c1)
    changed = 0
    for a, b in zip(e0.stalls, e1.stalls):
        assert (a.sid, a.stype, a.q_true, a.price_cents) == (b.sid, b.stype, b.q_true, b.price_cents)
        if a.stype == "seconds":
            assert abs(b.unit_cost_cents - CAT.unit_cost(c1, b.category, b.q_true, "seconds")) <= 1
            changed += a.unit_cost_cents != b.unit_cost_cents
        else:
            assert a.unit_cost_cents == b.unit_cost_cents
    assert changed > 0


def test_bust_out_cost_unchanged_by_seconds_target():
    c0 = cfg(prof(costs()))
    c1 = cfg(prof(costs(lambda k: {"seconds_cost_share": COST[k][0]})))
    for st in bazaar.BazaarEngine(c1).stalls:
        if st.stype == "genuine":
            q = B.bust_quality(c1, st)
            assert B.unit_cost(c1, st, q) == B.unit_cost(c0, st, q) == CAT.unit_cost(c0, st.category, q)


def test_fish_seconds_viable_at_target():
    """At the plan's fish costs a seconds stall's unit cost at the cheap mean quality was above its price at rating 1
    (0.672 vs 0.66 of base); at seconds_cost_share 0.70 it is 70% of that price."""
    c0 = cfg(prof(costs()))
    c1 = cfg(prof(costs(lambda k: {"seconds_cost_share": COST[k][0]})))
    ql = sum(c0.stalls.q_low) / 2
    ps = CAT.seconds_price_at_top(c0, "fish")
    assert CAT.unit_cost(c0, "fish", ql, "seconds") > ps
    assert CAT.unit_cost(c1, "fish", ql, "seconds") < ps


# ------------------------------------------------------------------ fixed cost by type

BT = {"fish": {"genuine": 1800, "seconds": -47, "deceptive": 470},
      "electronics": {"genuine": 7700, "seconds": 416, "deceptive": 4700},
      "designer": {"genuine": 45500, "seconds": 3700, "deceptive": 51300}}
SHARE = {"fish": 0.9, "electronics": 0.85, "designer": 0.5}


def by_type_profile():
    return costs(lambda c: {"baseline_gross_cents": BT[c]["genuine"], "fixed_cost_share": SHARE[c],
                            "baseline_gross_by_type_cents": BT[c]})


def test_fixed_cost_by_type_and_floor():
    c = cfg(prof(by_type_profile()))
    for cat in CATS:
        for t in ("genuine", "seconds", "deceptive"):
            want = int((SHARE[cat] * max(0, BT[cat][t])) // 1 + (1 if (SHARE[cat] * max(0, BT[cat][t])) % 1 >= 0.5 else 0))
            assert CAT.fixed_cost(c, cat, t) == want
    assert CAT.fixed_cost(c, "fish", "seconds") == 0                     # negative baseline floored at 0
    assert CAT.fixed_cost(c, "fish") == CAT._half_up(0.9 * 1800)        # no type: 1.3.0 rule
    out = run(c)
    eng = bazaar.BazaarEngine(c)
    t = {st.sid: (st.category, st.stype) for st in eng.stalls}
    for dd in out["days"]:
        for s, v in dd["outcome"]["overhead_by_stall_cents"].items():
            cat, ty = t[s]
            if s not in out["liability"]["exited"] or out["liability"]["exited"][s] >= dd["day"]:
                assert v == CAT.fixed_cost(c, cat, ty)


def test_start_cash_and_credit_stay_on_genuine_baseline():
    c = cfg(prof(by_type_profile()), "sellers.solvency.enabled=true", "sellers.solvency.start_cash_days=2")
    out = run(c)
    eng = bazaar.BazaarEngine(c)
    d1 = out["days"][0]["outcome"]
    for st in eng.stalls:
        assert CAT.start_cash(c, st.category) == CAT._half_up(2 * BT[st.category]["genuine"])
        assert d1["solvency"]["cash_cents"][st.sid] == CAT.start_cash(c, st.category) \
            + d1["brands"]["profit_by_stall_cents"][st.sid]
        assert CAT.credit_floor(c, st.category) == -3 * BT[st.category]["genuine"]


def test_bust_out_stall_keeps_its_fixed_cost():
    from engine import benchmark
    c = cfg(prof(by_type_profile()), days=4)
    eng = bazaar.BazaarEngine(c)
    sid = next(st.sid for st in eng.stalls if st.stype == "genuine" and st.category == "designer")
    out = run(benchmark.bust_config(c, sid, 2))
    assert any(x["stall"] == sid for dd in out["days"] for x in dd["bust_outs"])
    fc = CAT.fixed_cost(c, "designer", "genuine")
    assert all(dd["outcome"]["overhead_by_stall_cents"][sid] == fc for dd in out["days"])


def test_validation_131():
    bad = [
        {"fish": {"seconds_cost_share": 0.7}},                                         # needs cost_share
        {"fish": {"cost_share": 0.7, "cheap_share": 0.8, "seconds_cost_share": -1}},
        {"fish": {"baseline_gross_cents": 1, "baseline_gross_by_type_cents": {"genuine": 1}}},   # all three types
        {"fish": {"baseline_gross_cents": 1, "baseline_gross_by_type_cents": {"genuine": 1, "seconds": 1,
                                                                                "deceptive": "x"}}},
    ]
    for p in bad:
        with pytest.raises(ValueError):
            bazaar.BazaarEngine(cfg(prof(p)))
