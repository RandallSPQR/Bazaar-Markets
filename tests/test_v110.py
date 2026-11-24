"""Engine 1.1.0 (plan 2026-11-19, Stage 3A): price policies (sellers.price_policy), logit choice (buyers.choice),
checkpoint and continue (engine/checkpoint.py) and the seller options. Defaults reproducing 1.0.0 byte for byte is
checked by every reference test in the suite (tests/test_v0210.py, tests/test_reference_1_0.py and the earlier
reference files), which run at the defaults."""
import json
import math
from types import SimpleNamespace

import pytest

import engine.brands as B
from agents.rule_based import logit_pick
from engine import ENGINE_VERSION, bazaar
from engine import checkpoint as CP
from engine.config import load
from engine.jsonlog import JsonlLog

REF = "configs/reference_1_0.json"


def test_version():
    assert tuple(int(x) for x in ENGINE_VERSION.split(".")) >= (1, 1, 0)     # 1.2.0 keeps every 1.1.0 test


def _ref(*ov, seed=400, days=None):
    cfg = load(REF, list(ov) + ([f"market.days={days}"] if days else []))
    cfg.seed = seed
    return cfg


# ------------------------------------------------------------------ price policies

def _half_up(x):
    return int(math.floor(x + 0.5))


def _disp(cfg, r):
    v = B.shown(cfg, r)
    return 0.5 if v is None else v


def expected_own_price(cfg, st, stalls):
    """An independent statement of each policy (config reference, sellers.price_policy)."""
    base = cfg.pricing.base_price_cents[st.category]
    tier = B.tier_factor(cfg, st)
    ri = int(round(base * tier * (1 + cfg.brands.premium * (_disp(cfg, st.rating) - 0.5))))
    pol = cfg.sellers.price_policy
    if pol == "rating_indexed":
        return ri
    if pol == "cost_plus":
        return _half_up(st.unit_cost_cents * (1 + cfg.sellers.markup))
    if pol == "promo":
        h = st.units_hist
        return _half_up(0.85 * ri) if len(h) and h[-1] * len(h) < sum(h) else ri
    rivals = [s for s in stalls if s is not st and s.category == st.category and s.exited_day is None
              and s.yesterday is not None]
    own = _disp(cfg, st.rating)
    if pol == "match_rival":
        ps = sorted(s.yesterday["price_cents"] for s in rivals if _disp(cfg, s.rating) + 0.1 >= own - 1e-9)
        if not ps:
            return ri
        m = len(ps) // 2
        return ps[m] if len(ps) % 2 else _half_up((ps[m - 1] + ps[m]) / 2)
    assert pol == "undercut"
    ps = [s.yesterday["price_cents"] for s in rivals if _disp(cfg, s.rating) >= own - 1e-9]
    return max(min(ps) - 1, st.unit_cost_cents) if ps else ri


@pytest.mark.parametrize("policy", B.PRICE_POLICIES)
def test_each_price_policy_posts_its_formula(policy, monkeypatch):
    """Every morning of a 6-day reference market, every stall's own-name price is the policy's formula; counterfeits
    take the holder's price x counterfeit_price_factor."""
    cfg = _ref(f"sellers.price_policy={policy}", days=6)
    orig = B.morning_prices
    seen = {"stalls": 0, "copies": 0, "days": 0}

    def check(c, stalls, book):
        orig(c, stalls, book)
        seen["days"] += 1
        holder = {s.brand: s for s in stalls
                  if s.counterfeit_of is None and (s.licensed_from is None or s.white_label)}
        for st in stalls:
            if st.counterfeit_of is not None and st.counterfeit_of in holder:
                assert st.price_cents == B.counterfeit_price(c, holder[st.counterfeit_of].price_cents)
                seen["copies"] += 1
            else:
                assert st.price_cents == expected_own_price(c, st, stalls), (st.sid, policy)
                seen["stalls"] += 1
    monkeypatch.setattr(B, "morning_prices", check)
    bazaar.run(cfg)
    assert seen["days"] == 6 and seen["stalls"] > 6 * 30


def _st(sid, cat="fish", stype="genuine", rating=1.0, units_hist=(), y_price=None, unit_cost=600, exited=None):
    return SimpleNamespace(sid=sid, category=cat, stype=stype, rating=rating, units_hist=list(units_hist),
                           yesterday=None if y_price is None else {"price_cents": y_price}, unit_cost_cents=unit_cost,
                           exited_day=exited, white_label=False, licensed_from=None, counterfeit_of=None)


def test_price_policy_cases():
    c = lambda pol: load(overrides=["brands.enabled=true", "brands.premium=0.4", f"sellers.price_policy={pol}",
                                    "ratings.display=stars"], mode="bazaar")
    me = _st("a", rating=0.9, units_hist=[4, 4, 1], y_price=900)
    rivals = [_st("b", rating=0.8, y_price=700), _st("c", rating=0.77, y_price=100),      # c: shows 0.78 < own - 0.1
              _st("d", rating=1.0, y_price=1000), _st("e", rating=0.95, y_price=850),
              _st("f", cat="designer", rating=1.0, y_price=5), _st("g", rating=1.0, y_price=1, exited=3)]
    S = [me] + rivals
    ri = B.premium_price(c("rating_indexed"), me, 0.9)
    assert ri == 928                                                     # 800 x (1 + 0.4 x 0.4) = 928
    assert B.policy_price(c("rating_indexed"), me, S, 0.9) == ri
    assert B.policy_price(c("cost_plus"), me, S, 0.9) == 900             # 600 x 1.5
    assert B.policy_price(c("match_rival"), me, S, 0.9) == 850           # median of 700, 1000, 850
    assert B.policy_price(c("undercut"), me, S, 0.9) == 849              # min(1000, 850) - 1
    assert B.policy_price(c("promo"), me, S, 0.9) == _half_up(0.85 * 928)
    me.units_hist = [1, 4]                                               # rising: no promo
    assert B.policy_price(c("promo"), me, S, 0.9) == ri
    lone = _st("z", rating=0.9, y_price=900)
    for pol in ("match_rival", "undercut"):
        assert B.policy_price(c(pol), lone, [lone], 0.9) == ri           # no rival: rating_indexed
    cheap = [me, _st("h", rating=1.0, y_price=300)]
    assert B.policy_price(c("undercut"), me, cheap, 0.9) == 600          # floored at unit cost
    even = [me, _st("b", rating=0.85, y_price=701), _st("d", rating=1.0, y_price=1000)]
    assert B.policy_price(c("match_rival"), me, even, 0.9) == 851        # (701 + 1000) / 2 = 850.5, half up


def test_price_policy_validation():
    with pytest.raises(ValueError):
        bazaar.run(load(overrides=["sellers.price_policy=cost_plus"], mode="bazaar"))     # needs brands
    with pytest.raises(ValueError):
        bazaar.run(_ref("sellers.price_policy=nope", days=2))
    with pytest.raises(ValueError):
        bazaar.run(_ref("sellers.markup=-0.1", "sellers.price_policy=cost_plus", days=2))


# ------------------------------------------------------------------ logit choice

def test_logit_with_both_weights_zero_picks_uniformly():
    rows = [{"id": "a", "price_cents": 800, "rating": 1.0}, {"id": "b", "price_cents": 400},
            {"id": "c", "price_cents": 900, "rating": 0.2}, {"id": "d", "price_cents": 100, "rating": None}]
    n = len(rows)
    for i in range(1000):
        u = (i + 0.5) / 1000
        rule = {"rule": "logit", "rating_weight": 0.0, "price_weight": 0.0, "base_price_cents": 800, "u": u}
        assert logit_pick(rows, rule) == int(u * n)


def test_logit_probabilities():
    rows = [{"id": "a", "price_cents": 800, "rating": 1.0}, {"id": "b", "price_cents": 760, "rating": 1.0}]
    for w in (5.0, 20.0):
        p_b = 1 / (1 + math.exp(-w * 40 / 800))          # b is 5% cheaper
        grid = [(i + 0.5) / 10000 for i in range(10000)]
        share_a = sum(logit_pick(rows, {"rating_weight": w, "price_weight": w, "base_price_cents": 800, "u": u}) == 0
                      for u in grid) / len(grid)
        assert abs(share_a - (1 - p_b)) < 2e-4
    tourist = [{"id": "a", "price_cents": 800}, {"id": "b", "price_cents": 800}]     # no ratings: w_r = 0
    r = {"rating_weight": 1e6, "price_weight": 0.0, "base_price_cents": 800}
    assert [logit_pick(tourist, {**r, "u": u}) for u in (0.25, 0.75)] == [0, 1]


def test_logit_draw_is_one_uniform_per_buyer_and_day():
    import numpy as np
    cfg = _ref("buyers.choice=logit", days=2)
    eng = bazaar.BazaarEngine(cfg)
    p = eng.buyers[3]
    p.task = p.task or {"category": "fish"}
    a, b = eng.choice_rule(p), eng.choice_rule(p)
    assert a == b
    assert a["u"] == float(np.random.default_rng([cfg.seed, 37, 1, 3]).random())


def test_logit_changes_choices_and_lexicographic_is_the_default():
    lex = JsonlLog(keep=True)
    bazaar.run(_ref(days=2), log=lex)
    expl = JsonlLog(keep=True)
    bazaar.run(_ref("buyers.choice=lexicographic", "sellers.price_policy=rating_indexed", days=2), log=expl)
    assert lex.lines[1:] == expl.lines[1:]
    lg = JsonlLog(keep=True)
    bazaar.run(_ref("buyers.choice=logit", days=2), log=lg)
    assert lg.lines[1:] != lex.lines[1:]


# ------------------------------------------------------------------ checkpoint and continue

@pytest.mark.parametrize("seed", [400, 401, 402, 403, 404])
def test_continuation_on_the_original_streams_reproduces_the_chain(seed):
    cfg = _ref(seed=seed)
    full = JsonlLog(keep=True)
    want = bazaar.run(cfg, log=full)
    for d in (5, 10, 20):
        a, b = JsonlLog(keep=True), JsonlLog(keep=True)
        got = CP.continue_from(CP.snapshot(cfg, d, log=a), original=True, log=b)
        assert json.dumps(got, sort_keys=True) == json.dumps(want, sort_keys=True), (seed, d)
        assert a.lines + b.lines == full.lines, (seed, d)


def test_continuation_streams_differ_by_k_and_repeat():
    snap = CP.snapshot(_ref(days=8), 5)
    o1, o1b, o2 = (CP.continue_from(snap, k=k) for k in (1, 1, 2))
    assert json.dumps(o1, sort_keys=True) == json.dumps(o1b, sort_keys=True)
    assert json.dumps(o1["days"][5:], sort_keys=True) != json.dumps(o2["days"][5:], sort_keys=True)
    assert json.dumps(o1["days"][:5], sort_keys=True) == json.dumps(o2["days"][:5], sort_keys=True)
    with pytest.raises(ValueError):
        CP.continue_from(snap)                                   # neither k nor original
    with pytest.raises(ValueError):
        CP.continue_from(snap, k=1, original=True)


def _tap(rec):
    def tap(day, eng):
        rec[day] = {"agents": {sid: type(a).__name__ for sid, a in eng.seller_agents.items()},
                    "licensees": [x["stall"] for r in eng.licence_log for x in r["licensees"]],
                    "busts": [x["stall"] for x in eng.bust_log]}
    return tap


def _mornings(monkeypatch):
    """Each stall's state when the morning's prices are set (after the day's licences take effect), by call."""
    orig, seen = B.morning_prices, []

    def rec(c, stalls, book):
        seen.append({st.sid: (st.q_true, st.brand, st.stype, st.licensed_from, st.exited_day, st.busted_day, st.sign)
                     for st in stalls})
        return orig(c, stalls, book)
    monkeypatch.setattr(B, "morning_prices", rec)
    return seen


def test_every_option_changes_only_the_chosen_stall(monkeypatch):
    """Under every option, on every day from d + 1, only the chosen stall's agent differs from the honest
    continuation, only it busts out, and on the morning of day d + 1 only it (and a licence's licensees) differ."""
    cfg = _ref(days=12)
    d = 5
    snap = CP.snapshot(cfg, d)
    sid = next(s.sid for s in snap.state["stalls"] if s.stype == "genuine" and (s.rating or 0) >= 0.9)
    mornings = _mornings(monkeypatch)
    base = {}
    CP.continue_from(snap, "honest", sid, k=0, tap=_tap(base))
    base_m = mornings[0]
    for opt in CP.OPTIONS[1:]:
        rec = {}
        mornings.clear()
        out = CP.continue_from(snap, opt, sid, k=0, tap=_tap(rec))
        if opt == "switch_d10":                               # day 15 is past day 12
            assert out is None and CP.skipped(opt, d, 12)
            continue
        first = d + 1
        allowed = {sid} | set(rec[first]["licensees"])
        for day in rec:
            changed_agents = {s for s in rec[day]["agents"] if rec[day]["agents"][s] != base[day]["agents"][s]}
            assert changed_agents <= allowed, (opt, day, changed_agents)
            assert set(rec[day]["busts"]) <= {sid}
        changed = {s for s in mornings[0] if mornings[0][s] != base_m[s]}
        assert changed <= allowed, (opt, changed)
        if opt.startswith("switch"):
            assert {s for s, a in rec[first]["agents"].items() if a == "GenuineBustAtSeller"} == {sid}
            assert changed == set()                           # nothing differs before the bust-out itself
            b = CP.option_day(opt, d)
            assert rec[b]["busts"] == [sid] and all(not rec[x]["busts"] for x in rec if x < b)
        if opt.startswith("license"):
            assert len(rec[first]["licensees"]) == 6 and sid not in rec[first]["licensees"]
            assert changed == set(rec[first]["licensees"])
        if opt == "exit":
            assert changed == {sid}
            assert all(x["outcome"]["brands"]["profit_by_stall_cents"][sid] == 0 for x in out["days"][d:])


def test_options_need_an_honest_genuine_stall():
    snap = CP.snapshot(_ref(days=8), 3)
    dec = next(s.sid for s in snap.state["stalls"] if s.stype == "deceptive")
    with pytest.raises(ValueError):
        CP.continue_from(snap, "switch_now", dec, k=0)
    with pytest.raises(ValueError):
        CP.continue_from(snap, "nope", dec, k=0)
