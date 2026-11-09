"""Multi-day entry and exit (market.days): D = 1 is the single-day engine, the revision rule
behaves as specified, and revision draws use only their own stream."""
import copy
import hashlib
import json
import os

import numpy as np
import pytest

from engine import bazaar
from engine.config import load
from engine.days import SWITCHABLE, day_root, reset_for_day, revise
from engine.jsonlog import JsonlLog, dumps
from engine.runner import compare_logs, replay
from tests.guard_strip import changed_in_0140, strip_lines, strip_out

REF = os.path.join(os.path.dirname(__file__), "reference", "outcomes_v050.json")
ADAPTIVE = "agents.seller.deceptive=rule_deceptive_adaptive"


def cfg(*ov, seed=0):
    return load(overrides=[*ov, f"seed={seed}"], mode="bazaar")


def _ref_cells():
    with open(REF, encoding="utf-8") as f:
        return sorted(json.load(f)["cells"].items())


@pytest.mark.parametrize("key,cell", _ref_cells())
def test_one_day_reproduces_engine_050(key, cell):
    """Outcome and every log line after the header byte-identical to 0.5.0."""
    if changed_in_0140(cell):
        pytest.skip("changed on purpose by engine 0.14.0; checked in tests/test_trapped_buyers.py")
    log = JsonlLog(keep=True)
    out = bazaar.run(cfg(*cell["overrides"], seed=cell["seed"]), log=log)
    assert dumps(strip_out(out)) == cell["outcome"]
    assert len(log.lines) == cell["log_lines"]
    assert hashlib.sha256("\n".join(strip_lines(log.lines[1:])).encode()).hexdigest() == cell["log_body_sha256"]


def test_day_one_equals_single_day_run():
    for ov in (["inspectors.placement=posts"], ["inspectors.placement=disguised", "inspectors.disguised_shift=full_shift",
                                                 ADAPTIVE], ["inspectors.count=0"]):
        single = bazaar.run(cfg(*ov, "market.ticks=120", seed=3))
        multi = bazaar.run(cfg(*ov, "market.ticks=120", "market.days=3", seed=3))
        assert dumps(multi["days"][0]["outcome"]) == dumps(single)
        assert len(multi["days"]) == 3


def test_day_streams_are_fresh_and_condition_independent():
    """Day-2 buyers differ from day 1, and are the same whatever the inspectors do."""
    a = bazaar.BazaarEngine(cfg("market.ticks=60"), root=day_root(0, 2))
    b = bazaar.BazaarEngine(cfg("market.ticks=60", "inspectors.count=6", "inspectors.placement=patrolling"),
                            root=day_root(0, 2))
    c = bazaar.BazaarEngine(cfg("market.ticks=60"))
    key = lambda e: [(p.pid, p.profile, p.task, p.route, p.arrive) for p in e.buyers]
    assert key(a) == key(b)
    assert key(a) != key(c)


def _stalls_profits(seed=0):
    eng = bazaar.BazaarEngine(cfg(seed=seed))
    return eng.cfg, eng.stalls


def test_equal_profits_and_no_mutation_never_switch():
    c, stalls = _stalls_profits()
    c.evolution.mutation_prob = 0.0
    c.evolution.revise_prob = 1.0
    before = [(s.stype, s.q_true, s.price_cents) for s in stalls]
    for day in range(1, 40):
        assert revise(c, stalls, {s.sid: 12345 for s in stalls}, day) == []
    assert [(s.stype, s.q_true, s.price_cents) for s in stalls] == before


def test_seconds_never_switch_and_types_follow_rules():
    c, stalls = _stalls_profits()
    c.evolution.mutation_prob = 0.5
    c.evolution.revise_prob = 1.0
    sec = {s.sid for s in stalls if s.stype == "seconds"}
    rng = np.random.default_rng(1)
    n_sw = 0
    for day in range(1, 30):
        recs = revise(c, stalls, {s.sid: int(rng.integers(-5000, 5000)) for s in stalls}, day)
        n_sw += len(recs)
        assert not ({r["stall"] for r in recs} & sec)
        assert {s.sid for s in stalls if s.stype == "seconds"} == sec
    assert n_sw > 50
    lo, hi = c.stalls.q_low, c.stalls.q_high
    for s in stalls:
        base = c.pricing.base_price_cents[s.category]
        if s.stype == "genuine":
            assert s.q_true == s.q_pitch and hi[0] <= s.q_true <= hi[1] and s.price_cents == base and s.sign == "truth"
        if s.stype == "deceptive":
            assert lo[0] <= s.q_true <= lo[1] and hi[0] <= s.q_pitch <= hi[1]
            assert s.price_cents == round(base * c.pricing.deceptive_price_factor)
        # unit cost is computed from the unrounded Q, as in world.build_stalls
        assert abs(s.unit_cost_cents - base * (c.pricing.unit_cost[0] + c.pricing.unit_cost[1] * s.q_true)) <= 1


def test_imitation_moves_toward_the_more_profitable_type():
    c, stalls = _stalls_profits()
    c.evolution.mutation_prob = 0.0
    c.evolution.revise_prob = 1.0
    prof = {s.sid: (1000 if s.stype == "genuine" else 0) for s in stalls}
    n_dec = sum(s.stype == "deceptive" for s in stalls)
    recs = revise(c, stalls, prof, 1)
    assert recs and all(r["from"] == "deceptive" and r["to"] == "genuine" for r in recs)
    assert sum(s.stype == "deceptive" for s in stalls) == n_dec - len(recs)


def test_revision_uses_only_its_own_stream():
    """The six draws for stall i after day d are default_rng([seed, 10, d, i]).random(6),
    whatever else happened, so they never shift with buyers, inspectors or other stalls."""
    c, stalls = _stalls_profits(seed=5)
    c.evolution.mutation_prob = 1.0       # every switchable stall flips: draws 5 and 6 set the new Q
    c.evolution.revise_prob = 0.0
    revise(c, stalls, {s.sid: 0 for s in stalls}, 7)
    for s in stalls:
        if s.stype in SWITCHABLE:
            u = np.random.default_rng([5, 10, 7, s.idx]).random(6)
            hi = c.stalls.q_high[0] + (c.stalls.q_high[1] - c.stalls.q_high[0]) * u[4]
            lo = c.stalls.q_low[0] + (c.stalls.q_low[1] - c.stalls.q_low[0]) * u[5]
            assert s.q_true == round(hi if s.stype == "genuine" else lo, 4)
    # the multi-day run gives the same day-2 types whatever the engine streams drew on day 1,
    # given the same day-1 profits: revision reads profits and its own stream only
    c2, st2 = _stalls_profits(seed=5)
    np.random.default_rng([5, 3]).random(1000)   # unrelated draws elsewhere change nothing
    c2.evolution.mutation_prob, c2.evolution.revise_prob = 1.0, 0.0
    revise(c2, st2, {s.sid: 0 for s in st2}, 7)
    assert [(s.stype, s.q_true) for s in st2] == [(s.stype, s.q_true) for s in stalls]


def test_reset_for_day_clears_state_and_resets_signs():
    eng = bazaar.BazaarEngine(cfg("inspectors.count=6", "inspectors.placement=patrolling", ADAPTIVE))
    eng.run()
    assert any(s.catches for s in eng.stalls)
    fresh = reset_for_day(eng.cfg, eng.stalls)
    for s in fresh:
        assert (s.revenue_cents, s.cost_cents, s.ad_spend_cents, s.penalties_cents, s.catches, s.units_sold) == (0,) * 6
        assert s.closed_until == -1 and s.epoch == 0
        assert s.sign == ("pitch" if s.stype == "deceptive" else "truth")


def test_multi_day_summary_and_switch_logging():
    log = JsonlLog(keep=True)
    out = bazaar.run(cfg("market.days=4", "market.ticks=100", "evolution.mutation_prob=0.3"), log=log)
    assert [d["day"] for d in out["days"]] == [1, 2, 3, 4]
    for d in out["days"]:
        assert sum(d["types"].values()) == 48
        assert d["types"]["seconds"] == out["days"][0]["types"]["seconds"]
    ev = [json.loads(x) for x in log.lines]
    assert sum(e["ev"] == "header" for e in ev) == 1
    ends = [e for e in ev if e["ev"] == "day_end"]
    assert [e["day"] for e in ends] == [1, 2, 3, 4]
    assert sum(len(e["switches"]) for e in ends) > 0
    for e in ends:
        assert set(e) >= {"types", "profit_by_type", "shortfall_rate", "catches", "switches"}
    # the switches in day_end d produce day d+1's types
    for a, b in zip(out["days"], out["days"][1:]):
        t = dict(a["types"])
        for s in a["switches"]:
            t[s["from"]] -= 1
            t[s["to"]] += 1
        assert t == b["types"]


def test_multi_day_log_replays():
    log_path = None
    log = JsonlLog(keep=True)
    bazaar.run(cfg("market.days=3", "market.ticks=60", "evolution.mutation_prob=0.3", ADAPTIVE,
                   "inspectors.placement=patrolling"), log=log)
    _, new = replay(log.lines)
    assert compare_logs(log.lines, new.lines)["identical"]
