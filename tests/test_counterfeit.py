"""Engine 0.9.0: "look-alike" renamed "counterfeit" (with the old name as an alias), the budget
dial (buyers.budget_factor_override) and rule_genuine_rational_v2 (penalty-aware benchmark)."""
import gzip
import hashlib
import json
import os

import numpy as np
import pytest

from agents.rule_based import GenuineRationalSeller, GenuineRationalSellerV2
from engine import bazaar
from engine import brands as B
from engine.config import load
from engine.interface import parse
from engine.jsonlog import JsonlLog, dumps
from engine.runner import compare_logs, replay

HERE = os.path.dirname(__file__)
REF = os.path.join(HERE, "reference", "outcomes_v080.json")
LOG080 = os.path.join(HERE, "reference", "log_v080_brands.jsonl.gz")

BR = ["brands.enabled=true", "brands.premium=0.4", "ratings.mode=public", "inspectors.placement=patrolling",
      "evolution.revise_prob=0", "evolution.mutation_prob=0", "market.horizon_known=true"]
V1 = "agents.seller.genuine=rule_genuine_rational"
V2 = "agents.seller.genuine=rule_genuine_rational_v2"


def cfg(*ov, seed=0):
    return load(overrides=[*ov, f"seed={seed}"], mode="bazaar")


def _run(c):
    log = JsonlLog(keep=True)
    out = bazaar.run(c, log=log)
    return out, log.lines


def _ref_cells():
    with open(REF, encoding="utf-8") as f:
        return sorted(json.load(f)["cells"].items())


# ------------------------------------------------------------ defaults = 0.8.0

@pytest.mark.parametrize("key,cell", _ref_cells())
def test_defaults_reproduce_engine_080(key, cell):
    """Every 0.8.0 reference cell, outcome and log body (header aside). Brands cells differ only
    in the renamed word, so they are compared with "counterfeit" mapped back to "lookalike"."""
    out, lines = _run(cfg(*cell["overrides"], seed=cell["seed"]))
    o, body = dumps(out), "\n".join(lines[1:])
    if "brands.enabled=true" in cell["overrides"]:
        assert "lookalike" not in o and "lookalike" not in body
        back = lambda x: dumps(json.loads(x.replace("counterfeit", "lookalike"))) if "counterfeit" in x else x
        o, body = back(o), "\n".join(back(x) for x in lines[1:])
    else:
        assert "counterfeit" not in body
    assert o == cell["outcome"]
    assert len(lines) == cell["log_lines"]
    assert hashlib.sha256(body.encode()).hexdigest() == cell["log_body_sha256"]


def test_engine_080_log_replays():
    with gzip.open(LOG080, "rt", encoding="utf-8") as f:
        old = [x.rstrip("\n") for x in f if x.strip()]
    assert json.loads(old[0])["engine_version"] == "0.8.0" and any('"rename":"lookalike"' in x for x in old)
    _, new = replay(old)
    res = compare_logs(old, new.lines)
    assert res["identical"], res
    assert any("0.8.0" in w for w in res["warnings"])


# ------------------------------------------------------------ alias

def test_lookalike_alias_resolves():
    assert B.canonical_reopen("lookalike") == "counterfeit" and B.canonical_reopen("fresh") == "fresh"
    a, la = _run(cfg(*BR, "agents.params.rule_deceptive.reopen=lookalike", "market.days=3", "market.ticks=120",
                     "inspectors.count=6"))
    b, lb = _run(cfg(*BR, "agents.params.rule_deceptive.reopen=counterfeit", "market.days=3", "market.ticks=120",
                     "inspectors.count=6"))
    assert dumps(a) == dumps(b) and la[1:] == lb[1:]
    assert sum(len(d["renames"]) for d in a["days"]) > 0
    assert all(r["how"] == "counterfeit" for d in a["days"] for r in d["renames"])
    # the action schema still accepts the old word, and the engine treats it as a counterfeit
    act, err = parse("seller", '{"yell":null,"whisper":null,"answers":[],"rename":"lookalike"}')
    assert err is None and act["rename"] == "lookalike"
    act, err = parse("seller", '{"yell":null,"whisper":null,"answers":[],"rename":"counterfeit"}')
    assert err is None


def test_engine_080_log_keeps_old_word_in_raw_but_logs_counterfeit():
    with gzip.open(LOG080, "rt", encoding="utf-8") as f:
        old = [x.rstrip("\n") for x in f if x.strip()]
    _, new = replay(old)
    hows = [r["how"] for x in new.lines if '"ev":"day_end"' in x for r in json.loads(x)["renames"]]
    assert hows and set(hows) == {"counterfeit"}


# ------------------------------------------------------------ budget dial

@pytest.mark.parametrize("level", ["at", "below", "mixed"])
def test_budget_override_sets_every_budget(level):
    c = cfg(f"buyers.budget_level={level}", "buyers.budget_factor_override=1.1", seed=4)
    eng = bazaar.BazaarEngine(c)
    base = c.pricing.base_price_cents
    buyers = [p for p in eng.people if p.kind == "buyer"]
    assert len(buyers) == c.buyers.count
    for p in buyers:
        t = p.task
        assert t["budget_cents"] == int(round(t["units"] * base[t["category"]] * 1.1))
        assert t["budget_factor"] == 1.1
    # everything else about the population is unchanged
    ref = bazaar.BazaarEngine(cfg(f"buyers.budget_level={level}", seed=4))
    strip = lambda p: (p.pid, p.profile, p.route, p.arrive, {k: v for k, v in (p.task or {}).items()
                                                             if k not in ("budget_cents", "budget_factor")})
    assert [strip(p) for p in eng.people] == [strip(p) for p in ref.people]


def test_budget_override_equal_to_level_matches_level():
    a, _ = _run(cfg("buyers.budget_level=above", seed=2))
    b, _ = _run(cfg("buyers.budget_factor_override=1.25", seed=2))
    assert dumps(a) == dumps(b)


# ------------------------------------------------------------ v2

def _obs(day=5, days=10, U=10, c=400, A=20, N=800, profit=3000, rating=0.9, E=0.5, F=1200, premium=0.4,
         memory=0.7, close=40, ticks=240, first=True):
    return {"stall": {"price_cents": N}, "costs": {"penalty_cents_if_caught": F},
            "brand": {"rating": rating, "neutral_price_cents": N, "bust_out_unit_cost_cents": c,
                      "first_decision_today": first, "busted_day": None},
            "horizon": {"day": day, "days": days},
            "yesterday": {"units_sold": U, "ad_spend_cents": A, "profit_cents": profit},
            "privileged": {"deceptive_catch_rate_yesterday": E, "premium": premium, "rating_memory": memory,
                           "ticks_per_day": ticks, "close_ticks": close}}


def test_v2_values_match_hand_calculation_at_penalty_0():
    # L = 3; ratings 0.9, 0.63, 0.441 -> prices 928, 842 (841.6), 781 (781.12); margins 5280, 4420, 3810;
    # closed share = 0.5 x 40 / 240 = 1/12; bust = 13510 x 11/12 - 3 x 20; honest = 3 x 3000.
    honest, bust = GenuineRationalSellerV2.values(_obs(day=8, days=10, F=0))
    assert honest == 9000
    assert bust == pytest.approx(13510 * 11 / 12 - 60)
    # unrated today: neutral price, then rated 0 after one day of bad reviews
    _, bust = GenuineRationalSellerV2.values(_obs(day=9, days=10, F=0, E=0, rating=None, A=0))
    assert bust == pytest.approx(10 * (800 - 400) + 10 * (640 - 400))
    # no sales yesterday: the rating does not move
    _, bust = GenuineRationalSellerV2.values(_obs(day=9, days=10, F=0, E=0, U=0, A=0))
    assert bust == 0


def test_v2_never_busts_when_expected_penalty_exceeds_harvest_gain_every_day():
    rng = np.random.default_rng(0)
    checked = 0
    for _ in range(3000):
        o = _obs(day=int(rng.integers(2, 31)), days=30, U=int(rng.integers(0, 40)), c=int(rng.integers(100, 600)),
                 A=int(rng.integers(0, 200)), N=800, profit=int(rng.integers(-2000, 8000)),
                 rating=None if rng.random() < 0.2 else float(rng.random()), E=float(rng.random() * 3),
                 F=int(rng.integers(0, 20000)), close=40, ticks=240)
        L = o["horizon"]["days"] - o["horizon"]["day"] + 1
        y, pv, b = o["yesterday"], o["privileged"], o["brand"]
        closed = min(1.0, pv["deceptive_catch_rate_yesterday"] * 40 / 240)
        r, every = b["rating"], True
        for _ in range(L):
            P = int(round(800 * (1 + 0.4 * ((0.5 if r is None else r) - 0.5))))
            gain = y["units_sold"] * (P - b["bust_out_unit_cost_cents"]) * (1 - closed) - y["ad_spend_cents"] \
                - y["profit_cents"]
            if not pv["deceptive_catch_rate_yesterday"] * o["costs"]["penalty_cents_if_caught"] > gain:
                every = False
            if y["units_sold"] > 0:
                r = 0.0 if r is None else 0.7 * r
        if every:
            checked += 1
            assert not GenuineRationalSellerV2.should_bust(o)
    assert checked > 200


def test_v2_never_busts_in_a_run_with_a_ruinous_penalty_while_v1_does():
    ov = [*BR, "agents.params.rule_deceptive.reopen=fresh", "market.days=4", "market.ticks=120",
          "inspectors.count=4", "pricing.penalty_mult=200"]
    o1, _ = _run(cfg(*ov, V1))
    o2, _ = _run(cfg(*ov, V2))
    assert sum(len(d["bust_outs"]) for d in o1["days"]) > 0
    assert sum(len(d["bust_outs"]) for d in o2["days"]) == 0


def test_v2_privileged_input_is_yesterdays_market_catch_rate_and_only_v2_sees_it():
    ov = [*BR, "agents.params.rule_deceptive.reopen=counterfeit", "market.days=4", "market.ticks=120",
          "inspectors.count=4"]
    out, lines = _run(cfg(*ov, V2))
    ev = [json.loads(x) for x in lines]
    head = ev[0]
    assert head["agents"]["seller:rule_genuine_rational_v2"]["privileged"] is True
    rate = {}
    for d in out["days"]:
        liars = sum(t == "deceptive" for t in d["stall_types"].values()) + len(d["busted"])
        rate[d["day"] + 1] = d["outcome"]["catches"] / liars
    day, seen = 1, 0
    gen = {sid for sid, t in out["days"][0]["stall_types"].items() if t == "genuine"}
    for e in ev:
        if e["ev"] == "day_start":
            day = e["day"]
        elif e["ev"] == "obs" and e["role"] == "seller":
            pv = e["obs"].get("privileged")
            if e["agent"] in gen:
                assert pv is not None
                assert pv["deceptive_catch_rate_yesterday"] == (None if day == 1 else pytest.approx(rate[day]))
                seen += 1
            else:
                assert pv is None
    assert seen > 0
    _, lines1 = _run(cfg(*ov, V1))
    assert not any('"privileged"' in x for x in lines1 if '"ev":"obs"' in x)


def test_v2_is_honest_on_day_one_and_v1_is_unchanged():
    ov = [*BR, "agents.params.rule_deceptive.reopen=fresh", "market.days=3", "market.ticks=120"]
    out, _ = _run(cfg(*ov, V2))
    assert not out["days"][0]["bust_outs"]
    assert GenuineRationalSeller.VERSION == "rule_genuine_rational-1"
    assert GenuineRationalSellerV2.should_bust(_obs(first=False)) is False


def test_v2_log_replays():
    log = JsonlLog(keep=True)
    bazaar.run(cfg(*BR, V2, "agents.params.rule_deceptive.reopen=counterfeit", "inspectors.count=6",
                   "market.days=3", "market.ticks=100", "buyers.budget_factor_override=1.25"), log=log)
    _, new = replay(log.lines)
    assert compare_logs(log.lines, new.lines)["identical"]
