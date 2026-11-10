"""Engine 0.14.0: the trapped-buyer fix (a searching buyer stays in "choose" once there), the
parked-buyer fix (a searching buyer that decides not to buy at the stall it chose drops the target and
carries on) and the end-of-day stuck-buyer guard (outcome stuck_buyers, idle_choosers).

Reference: outcomes_v0130.json (86 cells, engine 0.13.0 at 56f0574). Every cell must reproduce 0.13.0
byte for byte with the guard keys removed, except the cells in outcomes_v0140.json, which 0.14.0
changes on purpose: choice-set cells with closures ("trapped") and walk-mode search cells in which a
buyer rejected its chosen stall on arrival ("parked"). Those are checked against their 0.14.0
regeneration. The guard must read 0 in every cell."""
import copy
import hashlib
import json
import os

import pytest

from analysis.verification import overrides as verification_overrides
from engine import bazaar
from engine.bazaar import BazaarEngine, _dist
from engine.config import load
from engine.jsonlog import JsonlLog, dumps
from tests.guard_strip import strip_liability, strip_liability_lines, strip_lines, strip_out

HERE = os.path.join(os.path.dirname(__file__), "reference")
with open(os.path.join(HERE, "outcomes_v0130.json"), encoding="utf-8") as f:
    V0130 = json.load(f)["cells"]
with open(os.path.join(HERE, "outcomes_v0140.json"), encoding="utf-8") as f:
    V0140 = json.load(f)["cells"]


def _total(o, k):
    return o[k]["total"] if "days" in o else o[k]


@pytest.mark.parametrize("key", sorted(V0130))
def test_reproduces_0130_except_on_purpose(key):
    c = V0130[key]
    log = JsonlLog(keep=True)
    o = bazaar.run(load(overrides=[*c["overrides"], f"seed={c['seed']}"], mode="bazaar"), log=log)
    assert _total(o, "stuck_buyers") == 0 and _total(o, "idle_choosers") == 0
    if key in V0140:
        r = V0140[key]
        # engine 0.15.0 adds the outcome key "liability"; compare without it
        assert dumps(strip_liability(o)) == r["outcome"] and len(log.lines) == r["log_lines"]
        assert hashlib.sha256("\n".join(strip_liability_lines(log.lines[1:])).encode()).hexdigest() == r["log_body_sha256"]
        assert dumps(strip_out(o)) != c["outcome"]                      # it did change
        searching = "buyers.demand_mode=choice_set" in c["overrides"] or \
            any(x.startswith("buyers.search_depth=") for x in c["overrides"])
        assert searching
        if r["why"] == "trapped":
            assert "buyers.demand_mode=choice_set" in c["overrides"] and c["catches"] > 0
    else:
        assert dumps(strip_out(o)) == c["outcome"] and len(log.lines) == c["log_lines"]
        assert hashlib.sha256("\n".join(strip_lines(log.lines[1:])).encode()).hexdigest() == c["log_body_sha256"]


def test_on_purpose_changes_are_listed():
    """The 18 cells 0.14.0 changes: 12 choice-set cells with closures, 6 walk-mode parked-buyer cells."""
    why = {k: v["why"] for k, v in V0140.items()}
    assert sum(w == "trapped" for w in why.values()) == 12 and sum(w == "parked" for w in why.values()) == 6
    assert all(k in V0130 for k in why)


# ------------------------------------------------------------------ the diagnostic's reproduction

def _repro(close: bool):
    cfg = load(None, [*verification_overrides("A|t100"), "market.days=1", "seed=200"], mode="bazaar")
    eng = BazaarEngine(copy.deepcopy(cfg))
    if close:
        eng.by_sid["s22"].closed_until = eng.cfg.market.ticks
    return eng, eng.run()


def test_closed_set_stall_traps_no_buyer():
    """runs/honest_profit_diagnostic.md: one day, tourists only, choice-set demand (m 3), no
    inspectors; s22 (in 17 buyers' sets) closed all day by hand. At 0.13.0: 16 buyers stuck and 131
    purchases against 148. At 0.14.0: none stuck. The only buyers who lose a purchase bought at s22
    in the control and have no other set stall whose claim meets their Q_req (no buyer's set is fully
    closed: sets hold 3 distinct stalls)."""
    e0, o0 = _repro(False)
    e1, o1 = _repro(True)
    assert sum("s22" in p.consider for p in e1.buyers) == 17
    assert o0["stuck_buyers"] == o1["stuck_buyers"] == 0 and o1["idle_choosers"] == 0
    assert not any(p.active and not p.done and p.target is not None for p in e1.buyers)
    units = lambda e: {p.pid: p.units for p in e.buyers}
    u0, u1 = units(e0), units(e1)
    changed = [pid for pid in u0 if u0[pid] != u1[pid]]
    assert all("s22" in e0.by_pid[pid].consider for pid in changed)
    lost = [pid for pid in changed if u1[pid] < u0[pid]]
    for pid in lost:
        p = e1.by_pid[pid]
        assert any(b["buyer"] == pid and b["stall"] == "s22" for b in e0.purchases)
        others = [e1.by_sid[s] for s in p.consider if s != "s22"]
        claim = lambda st: st.q_pitch if st.stype == "deceptive" else st.q_true
        assert all(claim(st) < p.task["q_req"] for st in others)
    assert o1["purchases"] == o0["purchases"] - len(lost)


def test_parked_buyer_moves_on():
    """Walk-mode search (tourists k 1, others k 3), brands, seed 0: at 0.13.0 a local chose s45 on
    its claim, inspected it on arrival (below Q_req) and stood there for the rest of day 4. At 0.14.0
    no buyer ends a day standing at its chosen stall with units still needed."""
    c = V0140["v0100_t1_others3_brands|0"]
    parked = []
    orig = BazaarEngine.run

    def run(e, *a, **k):
        out = orig(e, *a, **k)
        r = e.cfg.market.interact_range
        parked.extend(p.pid for p in e.buyers if p.active and not p.done and p.target is not None
                      and p.units < p.task["units"] and _dist(p.pos, e.by_sid[p.target].pos) <= r)
        return out

    BazaarEngine.run = run
    try:
        bazaar.run(load(overrides=[*c["overrides"], f"seed={c['seed']}"], mode="bazaar"))
    finally:
        BazaarEngine.run = orig
    assert parked == []


# ------------------------------------------------------------------ the guard

def test_guard_counts_a_stuck_buyer():
    """Put a buyer by hand where the bug left them: in the market at the end of the day, within reach
    of the open stall it chose, needing units, with budget for one."""
    eng = BazaarEngine(load(None, [*verification_overrides("A|t100"), "market.days=1", "seed=201"], mode="bazaar"))
    eng.run()
    p = eng.buyers[0]
    st = eng.by_sid[sorted(p.consider)[0]]
    r = eng.cfg.market.interact_range
    p.step = next(i for i, cell in enumerate(p.route) if _dist(cell, st.pos) <= r)
    p.active, p.done, p.units, p.paid_cents, p.inspect_spent_cents = True, False, 0, 0, 0
    p.target, p.choosing = st.sid, True
    assert eng.stuck_guard() == {"stuck_buyers": 1, "idle_choosers": 1}
    st.closed_until = eng.t + 10
    g = eng.stuck_guard()
    assert g["stuck_buyers"] == 0
    p.task = {**p.task, "budget_cents": st.price_cents - 1}
    st.closed_until = 0
    assert eng.stuck_guard()["stuck_buyers"] == 0               # cannot afford a unit there


def test_guard_in_multi_day_results():
    o = bazaar.run(load(None, [*verification_overrides("B|t40|l1"), "market.days=2", "seed=3"], mode="bazaar"))
    for k in ("stuck_buyers", "idle_choosers"):
        assert o[k]["by_day"] == [d["outcome"][k] for d in o["days"]]
        assert o[k]["total"] == sum(o[k]["by_day"]) == 0
