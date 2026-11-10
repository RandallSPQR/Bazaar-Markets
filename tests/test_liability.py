"""Engine 0.15.0: the liability dials. inspectors.detect_scale (enforcement intensity),
pricing.penalty_lag_days (fines fall due later; uncollectible after an exit), the seller action "exit"
(rule_genuine_bust_at exit_at; benchmark exit candidates) and the outcome key "liability".

Reference: outcomes_v0140_all.json (90 cells at engine 0.14.0, 445c654): every cell of
outcomes_v0130.json plus four verification-run markets with 2 patrolling inspectors and a genuine stall
busting out on day 2. Defaults must reproduce every cell byte for byte with "liability" removed."""
import hashlib
import json
import os

import pytest

from analysis.verification import overrides as vov
from engine import bazaar, benchmark
from engine.bazaar import BazaarEngine
from engine.config import load
from engine.jsonlog import JsonlLog, dumps
from tests.guard_strip import strip_liability, strip_liability_lines

HERE = os.path.join(os.path.dirname(__file__), "reference")
with open(os.path.join(HERE, "outcomes_v0140_all.json"), encoding="utf-8") as f:
    REF = json.load(f)
CELLS = REF["cells"]


def _run(ov, seed):
    log = JsonlLog(keep=True)
    return bazaar.run(load(overrides=[*ov, f"seed={seed}"], mode="bazaar"), log=log), log.lines


def _check(o, lines, c):
    assert dumps(strip_liability(o)) == c["outcome"]
    assert len(lines) == c["log_lines"]
    assert hashlib.sha256("\n".join(strip_liability_lines(lines[1:])).encode()).hexdigest() == c["log_body_sha256"]


def test_reference_is_0140():
    assert REF["engine_version"] == "0.14.0" and REF["commit"] == "445c654" and len(CELLS) == 90


@pytest.mark.parametrize("key", sorted(CELLS))
def test_defaults_reproduce_0140(key):
    c = CELLS[key]
    o, lines = _run(c["overrides"], c["seed"])
    _check(o, lines, c)
    L = o["liability"] if "days" in o else o["liability"]
    assert L["fines_uncollectible"] == 0 and L["fines_outstanding"] == 0


@pytest.mark.parametrize("key", ["v0140_bust_t100|0", "v0140_bust_t40|1"])
def test_explicit_defaults_are_the_defaults(key):
    """detect_scale 1 and lag 0 written out reproduce the 0.14.0 cell."""
    c = CELLS[key]
    o, lines = _run([*c["overrides"], "inspectors.detect_scale=1.0", "pricing.penalty_lag_days=0"], c["seed"])
    _check(o, lines, c)


# ------------------------------------------------------------------ helpers for the new dials

def _bust_cfg(cond="B|t100", seed=0, days=4, cand=2, extra=()):
    base = load(overrides=[*vov(cond), f"market.days={days}", *extra, f"seed={seed}"], mode="bazaar")
    sid = next(st.sid for st in sorted(BazaarEngine(base).stalls, key=lambda s: s.idx) if st.stype == "genuine")
    return benchmark.bust_config(base, sid, cand), sid


def _days_total(o, sid, k):
    return [d["outcome"]["brands"][k][sid] for d in o["days"]]


def _fine_total(o):
    return sum(d["outcome"]["catches"] for d in o["days"])


# ------------------------------------------------------------------ detect_scale

def test_detect_scale_zero_never_catches():
    c, _ = _bust_cfg(extra=["inspectors.detect_scale=0"])
    o = bazaar.run(c)
    assert _fine_total(o) == 0
    L = o["liability"]
    assert L["fines_charged"] == 0 and L["deceptive_catches"] == 0 and L["catches_per_deceptive_stall_day"] == 0
    assert all(d["outcome"]["seller_by_type"].get("deceptive", {}).get("penalties_cents", 0) == 0 for d in o["days"])
    assert o["stuck_buyers"]["total"] == 0


def test_detect_scale_lowers_catches():
    full = bazaar.run(_bust_cfg(extra=[])[0])
    low = bazaar.run(_bust_cfg(extra=["inspectors.detect_scale=0.1"])[0])
    assert 0 < _fine_total(low) < _fine_total(full)


@pytest.mark.parametrize("bad", ["inspectors.detect_scale=-0.1", "pricing.penalty_lag_days=1.5",
                                 "pricing.penalty_lag_days=-1"])
def test_bad_values_rejected(bad):
    with pytest.raises(ValueError):
        bazaar.run(load(overrides=[bad, "seed=0"], mode="bazaar"))


# ------------------------------------------------------------------ penalty lag

def test_lag_zero_charges_every_fine_at_the_catch():
    """With lag 0 no fine is ever uncollectible or outstanding, exit or not; fines charged = catches x P."""
    for cand in (2, (2, 1)):
        c, sid = _bust_cfg(cand=cand)
        o = bazaar.run(c)
        L = o["liability"]
        assert L["fines_uncollectible"] == 0 and L["fines_outstanding"] == 0
        assert L["fines_charged"] == _fine_total(o)
        pen = sum(v["penalties_cents"] for d in o["days"] for v in d["outcome"]["seller_by_type"].values())
        assert L["fines_charged_cents"] == pen


def test_lagged_fines_fall_due_later():
    """Lag 1: each day's fines are charged the next day; the last day's are outstanding at close; the
    stall's penalties on day d are its fines from catches on day d - 1."""
    c, _ = _bust_cfg(extra=["pricing.penalty_lag_days=1"])
    o = bazaar.run(c)
    days = [d["outcome"]["liability"] for d in o["days"]]
    assert days[0]["fines_charged"] == 0 and days[0]["fines_deferred"] == o["days"][0]["outcome"]["catches"]
    for k in range(1, len(days)):
        assert days[k]["fines_charged"] == days[k - 1]["fines_deferred"]
        assert days[k]["fines_charged_cents"] == days[k - 1]["fines_deferred_cents"]
    L = o["liability"]
    assert L["fines_outstanding"] == days[-1]["fines_deferred"] > 0
    assert L["fines_charged"] + L["fines_outstanding"] + L["fines_uncollectible"] == _fine_total(o)


def test_fine_due_after_exit_is_uncollectible():
    """Lag 3, bust out on day 2 and exit at its end: every fine from the busted stall's catches is
    uncollectible, none is charged, and the stall earns nothing after day 2."""
    c, sid = _bust_cfg(cand=(2, 1), extra=["pricing.penalty_lag_days=3"])
    o = bazaar.run(c)
    L = o["liability"]
    assert L["exited"] == {sid: 2}
    caught = sum(1 for d in o["days"] for e in d["outcome"]["liability"]["by_stall"] if e == sid)
    assert caught > 0                                          # the busted stall was caught
    s = L["by_stall"][sid]
    assert s["charged_cents"] == 0 and s["outstanding_cents"] == 0 and s["uncollectible_cents"] > 0
    assert o["days"][1]["outcome"]["liability"]["fines_uncollectible_cents"] == s["uncollectible_cents"]
    assert _days_total(o, sid, "profit_by_stall_cents")[2:] == [0, 0]
    assert o["stuck_buyers"]["total"] == 0 and o["idle_choosers"]["total"] == 0


def test_lag_does_not_change_trading():
    """The lag moves fines in time and nothing else: units sold by every stall on every day are
    unchanged (no rule policy reads penalties)."""
    a = bazaar.run(_bust_cfg()[0])
    b = bazaar.run(_bust_cfg(extra=["pricing.penalty_lag_days=3"])[0])
    assert [d["outcome"]["brands"]["units_by_stall"] for d in a["days"]] == \
           [d["outcome"]["brands"]["units_by_stall"] for d in b["days"]]
    assert [d["outcome"]["catches"] for d in a["days"]] == [d["outcome"]["catches"] for d in b["days"]]


# ------------------------------------------------------------------ exit

def test_exited_stall_sells_nothing_and_is_in_no_choice_set():
    c, sid = _bust_cfg(cand=(2, 1), days=4)
    seen = {}
    orig = BazaarEngine.run

    def run(e, *a, **k):
        seen[e.day] = (sum(sid in p.consider for p in e.buyers), e.is_open(e.by_sid[sid]))
        return orig(e, *a, **k)

    BazaarEngine.run = run
    try:
        o = bazaar.run(c)
    finally:
        BazaarEngine.run = orig
    assert o["liability"]["exited"] == {sid: 2}
    assert seen[1][0] > 0 and seen[2][0] > 0
    assert seen[3] == (0, False) and seen[4] == (0, False)
    for d in o["days"][2:]:
        assert d["outcome"]["brands"]["units_by_stall"][sid] == 0
        assert d["outcome"]["demand"]["inclusion"][sid] == 0
        assert d["outcome"]["brands"]["profit_by_stall_cents"][sid] == 0
    assert o["stuck_buyers"]["total"] == 0 and o["idle_choosers"]["total"] == 0


def test_exit_on_the_last_day_changes_nothing_that_day():
    """Exit at the end of day 4 of 4 (b 3, h 2): days 1-4 match busting out on day 3 without exit."""
    a = bazaar.run(_bust_cfg(cand=3)[0])
    b = bazaar.run(_bust_cfg(cand=(3, 2))[0])
    sid = _bust_cfg()[1]
    assert _days_total(a, sid, "profit_by_stall_cents") == _days_total(b, sid, "profit_by_stall_cents")
    assert b["liability"]["exited"] == {sid: 4}


def test_exit_candidates():
    assert benchmark.exit_candidates([20, 25, 28], [1, 3], 30) == \
        (benchmark.NEVER, (20, 1), (20, 3), (25, 1), (25, 3), (28, 1), (28, 3))
    with pytest.raises(ValueError):
        benchmark.exit_candidates([29], [3], 30)
    g = benchmark.gain({benchmark.NEVER: 10, (20, 1): 5, (25, 3): 12})
    assert g["best_day"] == (25, 3) and g["gain_unfloored"] == 2


def test_exit_run_is_deterministic_and_replays():
    from engine.runner import compare_logs, replay
    c, _ = _bust_cfg(cand=(2, 1), days=3, extra=["pricing.penalty_lag_days=3", "inspectors.detect_scale=0.3"])
    la, lb = JsonlLog(keep=True), JsonlLog(keep=True)
    a, b = bazaar.run(c, log=la), bazaar.run(c, log=lb)
    assert dumps(a) == dumps(b) and la.lines == lb.lines
    _, new = replay(la.lines)
    assert compare_logs(la.lines, new.lines)["identical"]
