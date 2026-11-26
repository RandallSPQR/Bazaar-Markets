"""Engine 1.3.0 (plan 2026-11-27, Stage 1): category profiles, solvency, the rent gradient and gamma by profile.

The plan's tests: v1.2.0 reference cells reproduce with defaults (tests/test_reference_1_0.py, with the 1.3.0 keys
stripped at their defaults); each profile hits its cost targets to the cent at mean quality; inspection noise 0
reproduces exact inspection; review accuracy 1 reproduces exact reviews; solvency off reproduces and a forced exit
works; alpha 0 reproduces and rent is charged exactly from the table.
"""
import json
import math

import pytest

from engine import ENGINE_VERSION, bazaar
from engine import categories as CAT
from engine.config import load

REF = "configs/reference_1_0.json"
CATS = ("fish", "electronics", "designer")
# The plan's Stage 1 table (PLACEHOLDER values).
PLAN = {"fish": {"cost_share": 0.70, "cheap_share": 0.80, "fixed_cost_share": 0.90, "inspect_sigma": 0.15,
                 "inspect_cost_mult": 1.0, "review_accuracy": 0.95},
        "electronics": {"cost_share": 0.77, "cheap_share": 0.55, "fixed_cost_share": 0.85, "inspect_sigma": 0.02,
                        "inspect_cost_mult": 0.5, "review_accuracy": 0.90},
        "designer": {"cost_share": 0.20, "cheap_share": 0.30, "fixed_cost_share": 0.50, "inspect_sigma": 0.25,
                     "inspect_cost_mult": 3.0, "review_accuracy": 0.60}}


def cfg(*ov, days=3, seed=7):
    return load(REF, [f"market.days={days}", f"seed={seed}", *ov])


def prof(d):
    return f"categories.profiles={json.dumps(d)}"


def run(c):
    return json.loads(json.dumps(bazaar.run(c)))


def test_version():
    assert ENGINE_VERSION == "1.3.0"


def test_defaults_add_nothing():
    out = run(cfg())
    o = out["days"][0]["outcome"]
    assert "solvency" not in o and "overhead_by_stall_cents" not in o
    assert all("overhead_cents" not in d for d in o["seller_by_type"].values())
    assert '"judged_honest_units"' not in json.dumps(out)


def test_empty_profiles_and_neutral_values_reproduce():
    base = run(cfg())
    neutral = {c: {"inspect_sigma": 0.0, "inspect_cost_mult": 1.0, "review_accuracy": 1.0, "fixed_cost_share": 0.0,
                   "baseline_gross_cents": 1234} for c in CATS}
    assert run(cfg(prof(neutral))) == base
    assert run(cfg("market.rent.alpha=0", 'market.rent.table={"s00": 500}')) == base
    assert run(cfg("sellers.solvency.enabled=false", "sellers.solvency.start_cash_days=0.5")) == base
    assert run(cfg('buyers.gamma_by_profile={}')) == base


# ------------------------------------------------------------------ costs

@pytest.mark.parametrize("cat", CATS)
def test_cost_targets_to_the_cent(cat):
    c = cfg(prof({cat: {k: PLAN[cat][k] for k in ("cost_share", "cheap_share")}}))
    qh = sum(c.stalls.q_high) / 2
    ql = sum(c.stalls.q_low) / 2
    p1 = CAT.genuine_price_at_top(c, cat)
    assert p1 == round(c.pricing.base_price_cents[cat] * 1.2)            # premium 0.4 at rating 1.0
    g = PLAN[cat]["cost_share"] * p1
    assert abs(CAT.unit_cost(c, cat, qh) - g) <= 0.5
    assert abs(CAT.unit_cost(c, cat, ql) - PLAN[cat]["cheap_share"] * g) <= 0.5
    # other categories keep the 1.2.0 relation
    for o in CATS:
        if o != cat:
            base = c.pricing.base_price_cents[o]
            assert CAT.unit_cost(c, o, 0.8) == int(round(base * (0.3 + 0.5 * 0.8)))


def test_costs_reach_every_stall_and_the_bust_quality():
    c = cfg(prof({k: {"cost_share": v["cost_share"], "cheap_share": v["cheap_share"]} for k, v in PLAN.items()}))
    eng = bazaar.BazaarEngine(c)
    for st in eng.stalls:       # world.build_stalls costs the unrounded quality (as since 0.1.0); q_true is rounded
        assert abs(st.unit_cost_cents - CAT.unit_cost(c, st.category, st.q_true)) <= 1
    from engine import brands as B
    st = next(s for s in eng.stalls if s.stype == "genuine")
    assert B.unit_cost(c, st, B.bust_quality(c, st)) == CAT.unit_cost(c, st.category, B.bust_quality(c, st))


# ------------------------------------------------------------------ inspection and reviews

def _inspected(out):
    return [(b["stall"], b["q_true"], b["inspected_q"]) for d in out["days"] for b in d.get("purchases", [])]


def test_inspection_noise_zero_is_exact_and_positive_is_noisy():
    base = run(cfg())
    assert run(cfg(prof({c: {"inspect_sigma": 0.0} for c in CATS}))) == base
    c = cfg(prof({c: {"inspect_sigma": 0.25} for c in CATS}), days=2)
    eng = bazaar.BazaarEngine(c)
    eng.run()
    seen = [p.info[s]["inspected_q"] for p in eng.buyers for s in p.info if p.info[s]["inspected_q"] is not None]
    true = [eng.by_sid[s].q_true for p in eng.buyers for s in p.info if p.info[s]["inspected_q"] is not None]
    assert seen and any(abs(a - b) > 1e-9 for a, b in zip(seen, true))
    assert all(0.0 <= a <= 1.0 for a in seen)
    # the draw is the specified stream
    p = next(p for p in eng.buyers if any(v["inspected_q"] is not None for v in p.info.values()))
    sid = next(s for s, v in p.info.items() if v["inspected_q"] is not None)
    st = eng.by_sid[sid]
    import numpy as np
    z = np.random.default_rng([7, 41, 1, eng.buyer_idx[p.pid], st.idx]).standard_normal()
    assert p.info[sid]["inspected_q"] == round(min(1.0, max(0.0, st.q_true + 0.25 * z)), 4)


def test_inspection_cost_multiplier():
    c = cfg(prof({"designer": {"inspect_cost_mult": 3.0}}))
    eng = bazaar.BazaarEngine(c)
    for p in eng.buyers:
        cat = p.task["category"]
        base = c.pricing.base_price_cents[cat]
        want = int(round(base * c.buyers.inspect_cost_frac[p.profile] * (3.0 if cat == "designer" else 1.0)))
        assert p.inspect_cost_cents == want


def test_review_accuracy_one_is_exact_and_below_one_flips():
    base = run(cfg())
    assert run(cfg(prof({c: {"review_accuracy": 1.0} for c in CATS}))) == base
    noisy = run(cfg(prof({c: {"review_accuracy": 0.6} for c in CATS})))
    assert noisy["days"][-1]["brand_ratings"] != base["days"][-1]["brand_ratings"]


def test_review_flip_stream():
    from engine import days as D
    c = cfg(prof({"fish": {"review_accuracy": 0.5}}), days=1)
    eng = bazaar.BazaarEngine(c)
    eng.run()
    CAT.judge_reviews(c, eng.sroot, 1, eng.purchases, eng.by_sid)
    import numpy as np
    gens = {}
    for b in eng.purchases:
        if not b["known_claims"]:
            assert "judged_honest_units" not in b
            continue
        st = eng.by_sid[b["stall"]]
        honest = b["q_true"] >= b["known_claims"][-1] - 1e-12
        if st.category != "fish":
            assert b["judged_honest_units"] == (b["units"] if honest else 0)
            continue
        g = gens.setdefault(st.sid, np.random.default_rng([7, 43, 1, st.idx]))
        u = g.random(b["units"])
        assert b["judged_honest_units"] == sum((honest if x < 0.5 else not honest) for x in u)


# ------------------------------------------------------------------ solvency

def test_forced_exit():
    p = {c: {"baseline_gross_cents": 1000, "fixed_cost_share": 4.0} for c in CATS}
    c = cfg(prof(p), "sellers.solvency.enabled=true", "sellers.solvency.start_cash_days=0",
            "sellers.solvency.credit_limit_days=3", days=3)
    out = run(c)
    d1 = out["days"][0]["outcome"]
    cash = d1["solvency"]["cash_cents"]
    profit = d1["brands"]["profit_by_stall_cents"]
    for sid, v in cash.items():
        assert v == profit[sid]                         # cash 0 + day 1's profit, fixed cost 4000 included
    gone = sorted(s for s, v in cash.items() if v < -3000)
    assert gone and d1["solvency"]["exits"] == gone
    assert sorted(set(d1["liability"]["exits"])) == gone
    assert {s: out["liability"]["exited"][s] for s in gone} == {s: 1 for s in gone}
    for dd in out["days"][1:]:
        o = dd["outcome"]
        for s in gone:
            assert o["brands"]["units_by_stall"][s] == 0
            assert o["overhead_by_stall_cents"][s] == 0
    kept = [s for s in cash if s not in gone]
    for s in kept:
        assert out["days"][1]["outcome"]["overhead_by_stall_cents"][s] == 4000


def test_solvency_starts_with_cash_and_tracks_profit():
    p = {c: {"baseline_gross_cents": 500} for c in CATS}
    out = run(cfg(prof(p), "sellers.solvency.enabled=true", days=3))
    cash0 = 10 * 500
    run_cash = {}
    for dd in out["days"]:
        o = dd["outcome"]
        for s, prof_ in o["brands"]["profit_by_stall_cents"].items():
            run_cash[s] = run_cash.get(s, cash0) + prof_
        assert o["solvency"]["cash_cents"] == run_cash


# ------------------------------------------------------------------ rent and gamma

def test_rent_charged_exactly_from_the_table():
    table = {f"s{i:02d}": (i * 37) % 900 - 300 for i in range(48)}
    t = json.dumps(table)
    base = run(cfg(f"market.rent.table={t}"))
    out = run(cfg("market.rent.alpha=0.5", f"market.rent.table={t}"))
    for d0, d1 in zip(base["days"], out["days"]):
        p0, p1 = d0["outcome"]["brands"]["profit_by_stall_cents"], d1["outcome"]["brands"]["profit_by_stall_cents"]
        for s in p0:
            r = math.floor(0.5 * table[s] + 0.5)
            assert d1["outcome"]["overhead_by_stall_cents"][s] == r
            assert p0[s] - p1[s] == r
        assert d0["outcome"]["purchases"] == d1["outcome"]["purchases"]


def test_rent_needs_a_full_table():
    with pytest.raises(ValueError):
        bazaar.BazaarEngine(cfg("market.rent.alpha=1", 'market.rent.table={"s00": 1}'))


def test_gamma_by_profile():
    g = run(cfg("buyers.position_rent=0.7"))
    assert run(cfg('buyers.gamma_by_profile={"tourist":0.7,"local":0.7,"expert":0.7}')) == g
    assert run(cfg("buyers.position_rent=0.7", 'buyers.gamma_by_profile={"tourist":0.7}')) == g
    other = run(cfg('buyers.gamma_by_profile={"tourist":1.0,"local":0.2}'))
    assert other != g


def test_validation():
    for ov in (prof({"fish": {"cost_share": 0.5}}), prof({"fish": {"bogus": 1}}), prof({"meat": {}}),
               prof({"fish": {"fixed_cost_share": 0.5}}), prof({"fish": {"review_accuracy": 1.5}}),
               "sellers.solvency.enabled=true", "market.rent.alpha=2", 'buyers.gamma_by_profile={"bargain":1}'):
        with pytest.raises(ValueError):
            bazaar.BazaarEngine(cfg(ov))
