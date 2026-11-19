"""Engine 0.21.0: buyers.profile_overrides. Per profile (tourist, local, expert) or "bargain", optional reads_ratings
(replaces ratings.visible_to for those buyers; false = rank as a tourist does, never see ratings) and inspect_prob
(replaces the profile's default inspection probability; a tourist given one follows the local rule).

Reference: outcomes_v0200_all.json (174 cells at engine 0.20.0, generated at 7bc8142): every cell of
outcomes_v0190_all.json plus 0.20.0 cells under stars display and random tie-break. With no overrides every cell must
reproduce byte for byte (outcome and log body)."""
import copy
import hashlib
import json
import os

import numpy as np
import pytest

from agents.rule_based import RuleBuyer
from analysis.verification import overrides as vov
from engine import bazaar
from engine.bazaar import BazaarEngine
from engine.config import load
from engine.jsonlog import JsonlLog, dumps

HERE = os.path.join(os.path.dirname(__file__), "reference")
with open(os.path.join(HERE, "outcomes_v0200_all.json"), encoding="utf-8") as f:
    REF = json.load(f)
CELLS = REF["cells"]
STARS = ["ratings.display=stars", "ratings.display_step=0.02", "buyers.tie_break=random"]


def _run(ov, seed):
    log = JsonlLog(keep=True)
    return bazaar.run(load(overrides=[*ov, f"seed={seed}"], mode="bazaar"), log=log), log.lines


def _body(lines, strip_inspect_prob=False):
    """The log body; with strip_inspect_prob, every line parsed and re-serialised the same way, with the
    you.inspect_prob field (added by an override) removed from observations."""
    if not strip_inspect_prob:
        return "\n".join(lines[1:])
    out = []
    for ln in lines[1:]:
        d = json.loads(ln)
        if isinstance(d.get("obs"), dict):
            d["obs"].get("you", {}).pop("inspect_prob", None)
        out.append(json.dumps(d, sort_keys=True, separators=(",", ":")))
    return "\n".join(out)


def _check(o, lines, c):
    assert dumps(o) == c["outcome"]
    assert len(lines) == c["log_lines"]
    assert hashlib.sha256("\n".join(lines[1:]).encode()).hexdigest() == c["log_body_sha256"]


def _ov(d):
    return "buyers.profile_overrides=" + json.dumps(d, separators=(",", ":"))


def test_reference_is_0200():
    assert REF["engine_version"] == "0.20.0" and REF["commit"] == "7bc8142" and len(CELLS) == 174


@pytest.mark.parametrize("key", sorted(CELLS))
def test_defaults_reproduce_0200(key):
    c = CELLS[key]
    o, lines = _run(c["overrides"], c["seed"])
    _check(o, lines, c)


def test_empty_overrides_change_nothing():
    c = CELLS["v0200_stars_t40_ds1|0"]
    o, lines = _run([*c["overrides"], _ov({})], c["seed"])
    _check(o, lines, c)


@pytest.mark.parametrize("key", ["v0200_stars_t40_ds1|0", "v0200_stars_t100_ds0|1", "v0200_stars_new400_wlg_t40|1",
                                 "v0190_new10_R_t40|0"])
def test_overrides_at_profile_defaults_reproduce(key):
    """G2: every profile's override set to its default (who reads ratings under ratings.visible_to; locals and
    experts inspect with probability 1 in these cells) gives the same outcome byte for byte, and the same log once
    the you.inspect_prob field, which the override adds to the buyer's observation, is removed."""
    c = CELLS[key]
    cfg = load(overrides=[*c["overrides"], f"seed={c['seed']}"], mode="bazaar")
    vis = cfg.ratings.visible_to
    lp = cfg.agents.params.get("rule_buyer", {}).get("local_inspect_prob", 1.0)
    ep = cfg.agents.params.get("rule_buyer", {}).get("expert_inspect_prob", 1.0)
    ov = {"tourist": {"reads_ratings": "tourist" in vis},
          "local": {"reads_ratings": "local" in vis, "inspect_prob": lp},
          "expert": {"reads_ratings": "expert" in vis, "inspect_prob": ep}}
    o, lines = _run([*c["overrides"], _ov(ov)], c["seed"])
    assert dumps(o) == c["outcome"]
    assert len(lines) == c["log_lines"]
    ref_o, ref_lines = _run(c["overrides"], c["seed"])
    assert _body(lines, True) == _body(ref_lines, True)
    assert any('"inspect_prob"' in ln for ln in lines)


# ------------------------------------------------------------------ the rule buyer

def _stall(sid, price, claim, channel="sign", rating=None, inspected=None):
    row = {"id": sid, "price_cents": price, "inspected_quality": inspected, "ask_pending": False,
           "messages": [{"claimed_quality": claim, "channel": channel}] if claim is not None else []}
    if rating is not None:
        row["rating"] = rating
    return row


def _me(profile, left=5000, need=1, q=0.6, ip=None):
    me = {"profile": profile, "inspect_cost_cents": 40,
          "task": {"budget_left_cents": left, "units_needed": need, "q_req": q}}
    if ip is not None:
        me["inspect_prob"] = ip
    return me


def _random_obs(rng, search):
    n = int(rng.integers(1, 5))
    rows = []
    for i in range(n):
        claim = None if rng.random() < 0.15 else round(float(rng.uniform(0.2, 0.95)), 2)
        ch = ["sign", "yell", "whisper", "answer"][int(rng.integers(4))]
        insp = round(float(rng.uniform(0.1, 0.95)), 2) if rng.random() < 0.2 else None
        rows.append(_stall(f"s{i}", int(rng.integers(300, 1500)), claim, ch, None, insp))
    obs = {"stalls_here": rows}
    if search:
        seen = [dict(_stall(f"e{i}", int(rng.integers(300, 1500)), round(float(rng.uniform(0.4, 0.95)), 2)),
                     steps_away=1) for i in range(int(rng.integers(0, 3)))]
        obs["search"] = {"phase": ["browse", "choose"][int(rng.integers(2))], "seen_elsewhere": seen}
    return obs


@pytest.mark.parametrize("search", [False, True])
def test_local_not_reading_not_inspecting_acts_as_tourist(search):
    """G4 at the agent level: in a fixed choice set (the same rows, which carry no rating for either), a local with
    reads_ratings false and inspect_prob 0 takes exactly the tourist's action, over 3,000 random situations."""
    rng = np.random.default_rng(7)
    for _ in range(3000):
        obs = _random_obs(rng, search)
        left = int(rng.integers(200, 4000))
        need = int(rng.integers(1, 3))
        q = round(float(rng.uniform(0.15, 0.7)), 2)
        a_t = RuleBuyer(np.random.default_rng(1)).act({**copy.deepcopy(obs), "you": _me("tourist", left, need, q)})
        a_l = RuleBuyer(np.random.default_rng(1)).act({**copy.deepcopy(obs), "you": _me("local", left, need, q, 0.0)})
        assert a_t == a_l


def test_inspect_prob_replaces_the_default():
    obs = {"stalls_here": [_stall("s0", 500, 0.8, "yell")]}
    assert '"inspect"' in RuleBuyer().act({**obs, "you": _me("local")})                 # default: locals check
    assert '"buy"' in RuleBuyer().act({**obs, "you": _me("local", ip=0.0)})
    assert '"buy"' in RuleBuyer().act({**obs, "you": _me("tourist")})                   # tourists never check
    assert '"inspect"' in RuleBuyer().act({**obs, "you": _me("tourist", ip=1.0)})       # ... unless given a prob
    assert '"buy"' in RuleBuyer().act({"stalls_here": [_stall("s0", 500, 0.8, "sign")],
                                        "you": _me("tourist", ip=1.0)})                 # local rule: pushy stalls only
    assert '"inspect"' in RuleBuyer(local_inspect_prob=0.0).act({**obs, "you": _me("local", ip=1.0)})


# ------------------------------------------------------------------ the engine

T40 = [*vov("B|t40|l1"), "market.days=2", "inspectors.detect_scale=1.0", *STARS]


def _rows(cfg_ov, seed=3):
    eng = BazaarEngine(load(overrides=[*cfg_ov, f"seed={seed}"], mode="bazaar"))
    return eng


def test_reads_ratings_controls_the_rating_field():
    eng = _rows([*T40, _ov({"local": {"reads_ratings": False}, "tourist": {"reads_ratings": True}})])
    prof = {}
    for p in eng.buyers:
        prof.setdefault(p.profile, p)
    st = eng.stalls[:2]
    assert all("rating" not in r for r in eng.buyer_obs(prof["local"], st, 1000, 1, False)["stalls_here"])
    assert all("rating" in r for r in eng.buyer_obs(prof["tourist"], st, 1000, 1, False)["stalls_here"])
    assert all("rating" in r for r in eng.buyer_obs(prof["expert"], st, 1000, 1, False)["stalls_here"])
    assert "inspect_prob" not in eng.buyer_obs(prof["local"], st, 1000, 1, False)["you"]
    eng0 = _rows(T40)
    p0 = {p.profile: p for p in eng0.buyers}
    assert all("rating" in r for r in eng0.buyer_obs(p0["local"], eng0.stalls[:2], 1000, 1, False)["stalls_here"])
    assert all("rating" not in r for r in eng0.buyer_obs(p0["tourist"], eng0.stalls[:2], 1000, 1, False)["stalls_here"])


def test_bargain_keys_win_over_the_profile():
    eng = _rows([*T40, _ov({"local": {"inspect_prob": 0.3, "reads_ratings": True},
                            "bargain": {"inspect_prob": 0.9, "reads_ratings": False}})])
    loc = [p for p in eng.buyers if p.profile == "local"]
    barg = [p for p in loc if p.task.get("bargain")]
    plain = [p for p in loc if not p.task.get("bargain")]
    assert barg and plain
    assert eng.profile_override(barg[0], "inspect_prob") == 0.9 and not eng.sees_ratings(barg[0])
    assert eng.profile_override(plain[0], "inspect_prob") == 0.3 and eng.sees_ratings(plain[0])
    tour_b = [p for p in eng.buyers if p.profile == "tourist" and p.task.get("bargain")]
    assert eng.profile_override(tour_b[0], "inspect_prob") == 0.9


def test_overrides_change_nothing_else():
    """Budgets, Q_req, units, consideration sets, search depth and inspection costs are the same with overrides."""
    a = _rows(T40)
    b = _rows([*T40, _ov({"local": {"reads_ratings": False, "inspect_prob": 0.0},
                          "expert": {"inspect_prob": 0.5}, "tourist": {"reads_ratings": True}})])
    assert len(a.buyers) == len(b.buyers)
    for p, q in zip(a.buyers, b.buyers):
        assert (p.profile, p.task, p.inspect_cost_cents, p.arrive, p.route, p.consider, p.search_k) == \
               (q.profile, q.task, q.inspect_cost_cents, q.arrive, q.route, q.consider, q.search_k)
    assert [(s.sid, s.price_cents, s.q_true) for s in a.stalls] == [(s.sid, s.price_cents, s.q_true) for s in b.stalls]


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_tourist_equivalence_in_the_market(seed):
    """G4 in a market: every buyer a local with reads_ratings false and inspect_prob 0, against every buyer a tourist,
    in the same choice-set market (no counterfeits): the same trades, stall by stall, and the same buyer outcomes."""
    base = [*vov("B|t40|l1"), "market.days=3", "inspectors.detect_scale=1.0", *STARS]
    o_t, _ = _run([*base, 'buyers.profile_shares={"tourist":1.0}'], seed)
    o_l, _ = _run([*base, 'buyers.profile_shares={"local":1.0}',
                   _ov({"local": {"reads_ratings": False, "inspect_prob": 0.0}})], seed)
    k = ("purchases", "units_bought", "payments_total_cents", "seller_revenue_total_cents", "buyer_surplus_total_cents",
         "shortfall_rate", "task_complete_share", "empty_handed_share", "deceptive_share_sales_units", "catches",
         "inspections", "seller_by_type")
    for dt, dl in zip(o_t["days"], o_l["days"]):
        assert {x: dt["outcome"][x] for x in k} == {x: dl["outcome"][x] for x in k}
        assert (dt["prices"], dt["ratings"], dt["brand_ratings"]) == (dl["prices"], dl["ratings"], dl["brand_ratings"])
    assert o_t["days"][-1]["outcome"]["purchases"] > 0


def test_overrides_are_deterministic():
    ov = [*T40, _ov({"local": {"reads_ratings": False, "inspect_prob": 0.5}})]
    a, la = _run(ov, 5)
    b, lb = _run(ov, 5)
    assert dumps(a) == dumps(b) and la == lb
    c, _ = _run(T40, 5)
    assert dumps(a) != dumps(c)


@pytest.mark.parametrize("bad", [{"merchant": {"inspect_prob": 0.5}}, {"local": {"inspect_prob": 1.5}},
                                 {"local": {"inspect_prob": True}}, {"local": {"reads_ratings": 1}},
                                 {"local": {"walks": 2}}, {"local": 0.5}])
def test_bad_overrides_rejected(bad):
    with pytest.raises(ValueError):
        BazaarEngine(load(overrides=[*T40, _ov(bad), "seed=0"], mode="bazaar"))
