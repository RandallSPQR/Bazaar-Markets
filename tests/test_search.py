"""Engine 0.10.0: buyer search depth (buyers.search_depth) and search diagnostics (buyers.search_log)."""
import hashlib
import json
import os

import pytest

from engine import bazaar
from engine.config import load
from engine.jsonlog import JsonlLog, dumps
from engine.runner import compare_logs, replay
from tests.guard_strip import changed_in_0140, strip_lines, strip_out

REF = os.path.join(os.path.dirname(__file__), "reference", "outcomes_v090.json")
BR = ["brands.enabled=true", "brands.premium=0.4", "ratings.mode=public", "inspectors.placement=patrolling",
      "evolution.revise_prob=0", "evolution.mutation_prob=0", "market.horizon_known=true",
      "buyers.budget_factor_override=1.25", "agents.params.rule_deceptive.reopen=counterfeit"]


def depth(k, tourist=None):
    return f'buyers.search_depth={{"tourist":{k if tourist is None else tourist},"local":{k},"expert":{k}}}'


def cfg(*ov, seed=0):
    return load(overrides=[*ov, f"seed={seed}"], mode="bazaar")


def _run(c):
    log = JsonlLog(keep=True)
    out = bazaar.run(c, log=log)
    return out, log.lines


def _ref_cells():
    with open(REF, encoding="utf-8") as f:
        return sorted(json.load(f)["cells"].items())


@pytest.mark.parametrize("key,cell", _ref_cells())
def test_depth_1_reproduces_engine_090(key, cell):
    if changed_in_0140(cell):
        pytest.skip("changed on purpose by engine 0.14.0; checked in tests/test_trapped_buyers.py")
    out, lines = _run(cfg(*cell["overrides"], seed=cell["seed"]))
    assert dumps(strip_out(out)) == cell["outcome"]
    assert len(lines) == cell["log_lines"]
    assert hashlib.sha256("\n".join(strip_lines(lines[1:])).encode()).hexdigest() == cell["log_body_sha256"]


def test_explicit_depth_1_and_search_log_change_nothing_but_the_search_block():
    a, la = _run(cfg("inspectors.placement=patrolling", seed=3))
    b, lb = _run(cfg("inspectors.placement=patrolling", depth(1), seed=3))
    assert dumps(a) == dumps(b) and la[1:] == lb[1:]
    c, lc = _run(cfg("inspectors.placement=patrolling", "buyers.search_log=true", seed=3))
    s = c.pop("search")
    assert dumps(a) == dumps(c) and la[1:-1] == lc[1:-1]
    assert set(s["exposure"]) == {f"s{i:02d}" for i in range(48)}
    assert all(r["k"] == 1 and r["walk_ticks"] == 0 and not r["chosen"] for r in s["buyers"].values())


@pytest.mark.parametrize("k", [2, 3, 6])
def test_buyer_populations_do_not_depend_on_depth(k):
    w = []
    for ov in ([], [depth(k)], [depth(k, tourist=1)]):
        _, lines = _run(cfg(*ov, "market.ticks=60", seed=5))
        w.append(next(x for x in lines if '"ev":"world"' in x))
    assert w[0] == w[1] == w[2]


def _search_events(lines):
    ev = [json.loads(x) for x in lines]
    obs, acts = {}, []
    for e in ev:
        if e["ev"] == "obs" and e["role"] == "buyer":
            obs[(e["t"], e["agent"])] = e["obs"]
        elif e["ev"] == "action" and e["role"] == "buyer" and e["valid"]:
            acts.append((e, obs[(e["t"], e["agent"])]))
    return ev, acts


@pytest.mark.parametrize("k,seed", [(2, 0), (4, 1), (8, 2)])
def test_never_buys_unseen_and_only_after_k_or_route_end(k, seed):
    out, lines = _run(cfg(depth(k), "buyers.search_log=true", "inspectors.count=4",
                          "inspectors.placement=patrolling", seed=seed))
    recs = out["search"]["buyers"]
    _, acts = _search_events(lines)
    n_buy = n_choose = 0
    for e, o in acts:
        a = e["action"]
        if a["action"] == "buy":
            n_buy += 1
            assert o["search"]["phase"] == "choose"
            assert o["search"]["seen_count"] >= k or o["search"]["route_end"]
            assert a["stall"] in {s["id"] for s in o["stalls_here"]}
        elif a["action"] == "choose":
            n_choose += 1
            assert a["stall"] in {s["id"] for s in o["search"]["seen_elsewhere"]}
    assert n_buy > 20 and n_choose > 0
    for pid, r in recs.items():
        assert set(r["bought"]) <= set(r["seen"])
    assert sum(r["walk_ticks"] for r in recs.values()) > 0
    assert out["fallbacks"]["buyer"] == 0


def test_full_depth_sees_every_stall_on_its_route_before_choosing():
    c = cfg(depth(16), "buyers.search_log=true", "inspectors.count=0", seed=4)
    eng = bazaar.BazaarEngine(c)
    out = eng.run()
    r = c.market.interact_range
    checked = 0
    first: dict = {}
    for b in eng.buyers:
        rec = out["search"]["buyers"][b.pid]
        if not rec["bought"]:
            continue
        reachable = {st.sid for st in eng.stalls if st.category == b.task["category"]
                     and any(((x - st.pos[0]) ** 2 + (y - st.pos[1]) ** 2) ** 0.5 <= r for x, y in b.route)}
        first[b.pid] = reachable
        assert reachable <= set(rec["seen"])
        checked += 1
    assert checked > 20
    # and at the moment of the first buy or choose, the buyer had seen all of them
    log = JsonlLog(keep=True)
    bazaar.run(c, log=log)
    _, acts = _search_events(log.lines)
    done = set()
    for e, o in acts:
        if e["agent"] in first and e["agent"] not in done and e["action"]["action"] in ("buy", "choose"):
            assert o["search"]["seen_count"] == len(first[e["agent"]])
            done.add(e["agent"])
    assert len(done) == len(first)


def test_closed_chosen_stall_falls_through_to_the_next_candidate():
    c = cfg(depth(4), "buyers.search_log=true", "inspectors.count=0", seed=1)
    eng = bazaar.BazaarEngine(c, log=JsonlLog(keep=True))
    eng.header()
    closed, t_skip = None, None
    for t in range(c.market.ticks):
        eng.t = t
        if closed is not None and t_skip is None and closed[1] in eng.by_pid[closed[0]].skipped:
            t_skip = t
        if closed is None:
            walkers = [p for p in eng.buyers if p.target is not None and p.active]
            if walkers:
                p = walkers[0]
                closed = (p.pid, p.target)
                st = eng.by_sid[p.target]
                st.closed_until = t + 1000            # closed until the end of the day
        eng.step()
    assert closed is not None
    pid, sid = closed
    rec = eng.search_outcome()["buyers"][pid]
    assert sid in rec["skipped_closed"]
    assert sid not in rec["bought"]
    ev, acts = _search_events(eng.log.lines)
    assert t_skip is not None
    after = [(e, o) for e, o in acts if e["agent"] == pid and e["action"]["action"] in ("buy", "choose")
             and e["t"] >= t_skip - 1]
    if after:   # it chose again: the closed stall is no longer offered and the next-best is taken
        e, o = after[0]
        assert sid not in {s["id"] for s in o["search"]["seen_elsewhere"]}
        assert sid not in e["action"]["candidates"]
        assert e["action"]["stall"] == e["action"]["candidates"][0]
    else:       # nothing else acceptable: it moved on
        assert not rec["bought"] or rec["bought"][-1] != sid


def test_choose_is_invalid_for_non_searching_buyers_and_buy_invalid_while_browsing():
    from engine.interface import parse
    act, err = parse("buyer", '{"action":"choose","stall":"s01","candidates":["s01","s02"]}')
    assert err is None and act["action"] == "choose"
    eng = bazaar.BazaarEngine(cfg("market.ticks=80", seed=2))
    p = eng.buyers[0]
    st = next(s for s in eng.stalls if s.category == p.task["category"])
    calls = []
    eng.decide = lambda role, key, agent, obs, check: calls.append(check({"action": "choose", "stall": st.sid})) or {"action": "move_on"}
    eng.buyer_did(p, [st], set())
    assert "only for searching buyers" in calls[0]
    calls.clear()
    eng.decide = lambda role, key, agent, obs, check: calls.append(check({"action": "buy", "stall": st.sid, "units": 1})) or {"action": "move_on"}
    eng.buyer_did(p, [st], set(), phase="browse")
    assert "may buy only after" in calls[0]


def test_tourists_depth_1_others_searching():
    out, lines = _run(cfg(depth(4, tourist=1), "buyers.search_log=true", seed=6))
    recs = out["search"]["buyers"]
    assert all(r["walk_ticks"] == 0 and not r["chosen"] for r in recs.values() if r["profile"] == "tourist")
    assert any(r["chosen"] for r in recs.values() if r["profile"] != "tourist")
    _, acts = _search_events(lines)
    assert all("search" not in o for e, o in acts if recs[e["agent"]]["profile"] == "tourist")


def test_searching_multi_day_brands_log_replays():
    log = JsonlLog(keep=True)
    bazaar.run(cfg(*BR, depth(3, tourist=1), "buyers.search_log=true", "inspectors.count=6", "market.days=3",
                   "market.ticks=100", "agents.seller.genuine=rule_genuine_rational_v2"), log=log)
    _, new = replay(log.lines)
    assert compare_logs(log.lines, new.lines)["identical"]


def test_exposure_counts_buyers_in_reach():
    c = cfg(depth(3), "buyers.search_log=true", "market.ticks=120", seed=7)
    eng = bazaar.BazaarEngine(c)
    out = eng.run()
    ex = out["search"]["exposure"]
    sold = {st.sid: st.units_sold for st in eng.stalls}
    for sid, e in ex.items():
        assert e["in_reach_shopping"] <= e["in_reach"]
        if sold[sid]:
            assert e["in_reach_shopping"] > 0


def test_bad_depth_rejected():
    with pytest.raises(ValueError):
        bazaar.BazaarEngine(cfg('buyers.search_depth={"tourist":0,"local":1,"expert":1}'))
    with pytest.raises(ValueError):
        bazaar.BazaarEngine(cfg('buyers.search_depth={"visitor":2}'))
