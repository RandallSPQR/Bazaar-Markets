"""Engine 0.12.0: choice-set demand (buyers.demand_mode, consider, position_rent) and the wider
bust-out benchmark candidates. Walk mode (the default) must reproduce engine 0.11.0 byte for byte."""
import hashlib
import json
import math
import os

import numpy as np
import pytest

from engine import bazaar, benchmark
from engine import world as W
from engine.config import load
from engine.jsonlog import JsonlLog, dumps
from engine.runner import compare_logs, replay
from tests.guard_strip import changed_in_0140, strip_lines, strip_out

REF = os.path.join(os.path.dirname(__file__), "reference", "outcomes_v0110.json")
CS = ["buyers.demand_mode=choice_set"]
BR = ["brands.enabled=true", "brands.premium=0.4", "ratings.mode=public", "inspectors.placement=patrolling",
      "evolution.revise_prob=0", "evolution.mutation_prob=0", "market.horizon_known=true",
      "buyers.budget_factor_override=1.25", "market.ticks=160", "agents.params.rule_deceptive.reopen=fresh"]


def cfg(*ov, seed=0):
    return load(overrides=[*ov, f"seed={seed}"], mode="bazaar")


def _run(c):
    log = JsonlLog(keep=True)
    return bazaar.run(c, log=log), log.lines


def _ref_cells():
    with open(REF, encoding="utf-8") as f:
        return sorted(json.load(f)["cells"].items())


@pytest.mark.parametrize("key,cell", _ref_cells())
def test_walk_reproduces_engine_0110(key, cell):
    if changed_in_0140(cell):
        pytest.skip("changed on purpose by engine 0.14.0; checked in tests/test_trapped_buyers.py")
    out, lines = _run(cfg(*cell["overrides"], seed=cell["seed"]))
    assert dumps(strip_out(out)) == cell["outcome"]
    assert len(lines) == cell["log_lines"]
    assert hashlib.sha256("\n".join(strip_lines(lines[1:])).encode()).hexdigest() == cell["log_body_sha256"]


def test_walk_mode_ignores_choice_knobs():
    a, la = _run(cfg("inspectors.count=2", seed=4))
    b, lb = _run(cfg("inspectors.count=2", "buyers.consider=5", "buyers.position_rent=1.5", seed=4))
    assert dumps(a) == dumps(b) and la[1:] == lb[1:]
    assert "demand" not in a


# ------------------------------------------------------------------ sets and routes

def _engine(*ov, seed=0):
    return bazaar.BazaarEngine(cfg(*CS, *ov, seed=seed))


@pytest.mark.parametrize("m", [1, 3, 5])
def test_set_members_are_stalls_of_the_buyers_category(m):
    e = _engine(f"buyers.consider={m}", "buyers.position_rent=0.7", seed=1)
    for p in e.buyers:
        cat = p.task["category"]
        n = sum(st.category == cat for st in e.stalls)
        assert len(p.consider) == min(m, n) == len(p.task["consider"]) == p.search_k
        assert all(e.by_sid[s].category == cat for s in p.consider)
        assert set(p.task["consider"]) == p.consider


def test_route_passes_every_set_member_in_walking_order():
    e = _engine("buyers.consider=4", "market.scale=2", seed=2)
    r = e.cfg.market.interact_range
    for p in e.buyers:
        first = []
        for sid in p.task["consider"]:
            st = e.by_sid[sid]
            hits = [i for i, cell in enumerate(p.route) if math.dist(cell, st.pos) <= r]
            assert hits, (p.pid, sid)
            first.append(hits[0])
        assert first == sorted(first)
        # the walk is along the buyer's category aisle
        ys = {cell[1] for cell in p.route}
        assert len(ys) == 1


def test_buyers_buy_only_from_their_set():
    c = cfg(*CS, *BR, "market.days=2", "inspectors.count=1", seed=3)
    with_sets = {}
    orig = bazaar.BazaarEngine.run

    def run(eng, *a, **k):
        out = orig(eng, *a, **k)
        sets = {p.pid: p.consider for p in eng.buyers}
        with_sets[eng.day] = all(b["stall"] in sets[b["buyer"]] for b in eng.purchases) and len(eng.purchases) > 0
        return out

    bazaar.BazaarEngine.run = run
    try:
        bazaar.run(c)
    finally:
        bazaar.BazaarEngine.run = orig
    assert with_sets == {1: True, 2: True}


def test_gamma_zero_gives_equal_expected_inclusion():
    """Successive sampling with equal weights: every stall of a category is in a buyer's set with
    probability m / n. 20,000 draws; tolerance 5 standard errors."""
    c = cfg(*CS, "buyers.consider=3", seed=11)
    e = bazaar.BazaarEngine(c)
    cat = e.cfg.market.categories[0]
    stalls = [st for st in e.stalls if st.category == cat]
    n, m, N = len(stalls), 3, 20000
    counts = {st.sid: 0 for st in stalls}
    for i in range(N):
        _, members = W.consideration_set(c, (c.seed, 99), i, stalls)
        for s in members:
            counts[s] += 1
    p = m / n
    se = math.sqrt(p * (1 - p) / N)
    for s, k in counts.items():
        assert abs(k / N - p) < 5 * se, (s, k / N, p)


def test_position_rent_favours_stalls_near_the_entrance():
    c = cfg(*CS, "buyers.consider=3", "buyers.position_rent=1.0", seed=11)
    e = bazaar.BazaarEngine(c)
    stalls = [st for st in e.stalls if st.category == e.cfg.market.categories[0]]
    by_rank = np.zeros(8)
    for i in range(4000):
        left, members = W.consideration_set(c, (c.seed, 98), i, stalls)
        ranks = W.position_ranks(stalls, left)
        for s in members:
            by_rank[ranks[s]] += 1
    assert all(np.diff(by_rank) < 0)          # strictly fewer inclusions further from the entrance
    ranks = W.position_ranks(stalls, True)
    assert sorted(set(ranks.values())) == list(range(8)) and sum(v == 0 for v in ranks.values()) == 2


def _population(e):
    return [(p.pid, p.kind, p.profile, p.arrive, p.is_inspector,
             {k: v for k, v in (p.task or {}).items() if k != "consider"},
             p.route if p.kind == "inspector" else None) for p in e.people]


def test_buyer_populations_stable_across_gamma_and_m():
    base = _population(_engine("buyers.consider=3", "inspectors.count=3", seed=5))
    for ov in (["buyers.consider=1"], ["buyers.consider=6", "buyers.position_rent=2.5"],
               ["buyers.position_rent=0.3"]):
        assert _population(_engine(*ov, "inspectors.count=3", seed=5)) == base
    # and the same buyers (and inspectors) as walk mode with the same bargain share
    walk = _population(bazaar.BazaarEngine(cfg("buyers.bargain_share=0.2", "inspectors.count=3", seed=5)))
    assert walk == base


def test_bargain_default_depends_on_mode():
    walk = bazaar.BazaarEngine(cfg(seed=6))
    assert not any(p.task.get("bargain") for p in walk.buyers)
    cs = _engine(seed=6)
    share = np.mean([bool(p.task.get("bargain")) for p in cs.buyers])
    assert 0.1 < share < 0.3
    off = _engine("buyers.bargain_share=0", seed=6)
    assert not any(p.task.get("bargain") for p in off.buyers)


def test_choice_set_outcome_and_replay():
    out, lines = _run(cfg(*CS, *BR, "market.days=3", "inspectors.count=2", seed=7))
    d = out["days"][0]["outcome"]["demand"]
    assert sum(d["inclusion"].values()) == sum(len(p["task"]["consider"]) for p in
                                               json.loads(next(x for x in lines if '"ev":"world"' in x))["people"]
                                               if p["kind"] == "buyer")
    assert sum(d["customers"].values()) >= 1
    _, new = replay(lines)
    assert compare_logs(lines, new.lines)["identical"]


def test_consider_one_uses_the_plain_rule():
    out, _ = _run(cfg(*CS, "buyers.consider=1", "inspectors.count=2", seed=8))
    assert out["purchases"] > 0 and "search" not in out


@pytest.mark.parametrize("ov", [["buyers.demand_mode=browse"], [*CS, "buyers.consider=0"],
                                [*CS, "buyers.consider=2.5"], [*CS, "buyers.position_rent=-1"],
                                [*CS, "market.clustering=0.5"]])
def test_bad_settings_rejected(ov):
    with pytest.raises(ValueError):
        bazaar.BazaarEngine(cfg(*ov))


def test_benchmark_candidates():
    assert benchmark.CANDIDATES == (benchmark.NEVER, 10, 20, 25, 27, 28, 29)
    import inspect
    assert inspect.signature(benchmark.best_response).parameters["candidates"].default == benchmark.CANDIDATES
