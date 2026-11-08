"""Engine 0.13.0: the verification dial (rule_buyer local_inspect_prob / expert_inspect_prob), a
validated bust-out candidate list, and the bargain_q_req range check. Defaults reproduce 0.12.0."""
import hashlib
import json
import os

import numpy as np
import pytest

from agents.rule_based import RuleBuyer
from engine import bazaar, benchmark
from engine.config import load
from engine.jsonlog import JsonlLog, dumps

REF = os.path.join(os.path.dirname(__file__), "reference", "outcomes_v0120.json")
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
def test_defaults_reproduce_engine_0120(key, cell):
    out, lines = _run(cfg(*cell["overrides"], seed=cell["seed"]))
    assert dumps(out) == cell["outcome"]
    assert len(lines) == cell["log_lines"]
    assert hashlib.sha256("\n".join(lines[1:]).encode()).hexdigest() == cell["log_body_sha256"]


def P(local=None, expert=None):
    out = []
    if local is not None:
        out.append(f"agents.params.rule_buyer.local_inspect_prob={local}")
    if expert is not None:
        out.append(f"agents.params.rule_buyer.expert_inspect_prob={expert}")
    return out


# ------------------------------------------------------------------ verification dial

@pytest.mark.parametrize("mode", [[], CS])
def test_probability_one_is_the_default(mode):
    a, la = _run(cfg(*mode, "inspectors.count=2", seed=3))
    b, lb = _run(cfg(*mode, "inspectors.count=2", *P(1.0, 1.0), seed=3))
    assert dumps(a) == dumps(b) and la[1:] == lb[1:]


@pytest.mark.parametrize("mode", [[], CS])
def test_probability_zero_never_inspects(mode):
    a, _ = _run(cfg(*mode, seed=4))
    z, _ = _run(cfg(*mode, *P(0, 0), seed=4))
    assert a["inspections"] > 0 and z["inspections"] == 0


def test_expert_only_and_local_only():
    """Experts inspect before buying; locals only at advertising stalls. Turning one off removes
    only that profile's inspections."""
    def by_profile(*ov):
        e = bazaar.BazaarEngine(cfg(*CS, *ov, seed=5))
        prof = {p.pid: p.profile for p in e.buyers}
        e.run()
        n = {"local": 0, "expert": 0, "tourist": 0}
        for p in e.buyers:
            n[prof[p.pid]] += p.inspect_spent_cents // max(1, p.inspect_cost_cents)
        return n
    base, no_local, no_expert = by_profile(), by_profile(*P(local=0)), by_profile(*P(expert=0))
    assert base["local"] > 0 and base["expert"] > 0 and base["tourist"] == 0
    assert no_local["local"] == 0 and no_local["expert"] > 0
    assert no_expert["expert"] == 0 and no_expert["local"] > 0


def test_intermediate_probability_is_between():
    n = {p: _run(cfg(*CS, *P(p, p), seed=6))[0]["inspections"] for p in (0, 0.5, 1)}
    assert n[0] < n[0.5] < n[1]


def test_draws_use_only_the_buyers_own_stream():
    """The dial draws from each buyer agent's own generator ([root, 7, role, idx]), once per stall
    that needs a decision, and never from an engine stream; the world and population are unchanged."""
    e1 = bazaar.BazaarEngine(cfg(*CS, *BR, *P(0.5, 0.5), seed=7))
    e0 = bazaar.BazaarEngine(cfg(*CS, *BR, seed=7))
    w = lambda e: [(p.pid, p.profile, p.task, p.route, p.arrive) for p in e.people]
    assert w(e1) == w(e0)
    assert [st.truth() for st in e1.stalls] == [st.truth() for st in e0.stalls]
    engine_rngs = [e1.rng_world, e1.rng_routes, e1.rng_people, e1.rng_detect, e1.rng_treat, e1.rng_insp]
    agents = list(e1.buyer_agents.values())
    assert all(isinstance(a, RuleBuyer) for a in agents)
    assert all(all(a.rng is not r for r in engine_rngs) for a in agents)
    assert len({id(a.rng) for a in agents}) == len(agents)
    e1.run()
    assert sum(len(a._checks) for a in agents) > 0
    for a in agents:
        # one draw per stall decided, nothing else: replaying the draws reproduces the decisions
        if not a._checks:
            continue
        fresh = np.random.default_rng(a.rng.bit_generator.seed_seq)
        assert list(a._checks.values()) == [bool(fresh.random() < 0.5) for _ in a._checks]


def test_dial_is_deterministic_and_replays():
    from engine.runner import compare_logs, replay
    c = cfg(*CS, *BR, "market.days=2", "inspectors.count=1", *P(0.4, 0.6), seed=8)
    a, la = _run(c)
    b, lb = _run(c)
    assert dumps(a) == dumps(b) and la == lb
    _, new = replay(la)
    assert compare_logs(la, new.lines)["identical"]


@pytest.mark.parametrize("bad", [P(local=1.5), P(expert=-0.1)])
def test_bad_probabilities_rejected(bad):
    with pytest.raises(ValueError):
        bazaar.BazaarEngine(cfg(*bad))


# ------------------------------------------------------------------ candidates and bargain range

def test_candidate_list_is_respected():
    c = cfg(*BR, "market.days=4", seed=9)
    sid = next(st.sid for st in bazaar.BazaarEngine(c).stalls if st.stype == "genuine")
    ran = []

    def run(cc):
        sched = cc.agents.params[benchmark.POLICY]["schedule"]
        ran.append(sched.get(sid, benchmark.NEVER))
        return bazaar.run(cc)

    cands = benchmark.candidates([4, 2], horizon=4)
    assert cands == (benchmark.NEVER, 2, 4)
    g = benchmark.best_response(c, sid, candidates=cands, run=run)
    assert ran == [benchmark.NEVER, 2, 4]
    assert set(g["totals"]) == {benchmark.NEVER, 2, 4} and g["best_day"] in (2, 4)
    assert benchmark.candidates([20, 25, 28, 29, 30], 30) == (benchmark.NEVER, 20, 25, 28, 29, 30)


@pytest.mark.parametrize("days", [[1, 5], [5, 5], [31], [2.5]])
def test_bad_candidates_rejected(days):
    with pytest.raises(ValueError):
        benchmark.candidates(days, 30)


def test_bargain_range():
    e = bazaar.BazaarEngine(cfg(*CS, "buyers.bargain_q_req=[0.15,0.40]", seed=10))
    qs = [p.task["q_req"] for p in e.buyers if p.task.get("bargain")]
    assert qs and all(0.15 <= q <= 0.40 for q in qs)
    with pytest.raises(ValueError):
        bazaar.BazaarEngine(cfg(*CS, "buyers.bargain_q_req=[0.5,0.4]"))
