"""M0 compatibility: exact port of the prototype, and the regression targets."""
import os
import sys

import numpy as np
import pytest

from engine import m0
from engine.config import M0Config
from engine.jsonlog import JsonlLog
from engine.metrics import mean_ci
from engine.runner import compare_logs, replay

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "reference"))
import sim_prototype as proto  # noqa: E402  (v0: original idle rule)
import sim_prototype_v1 as proto1  # noqa: E402  (v1: corrected idle rule, doc results)

SEEDS = range(6)


COMPAT = dict(tie_break="numpy_default")          # prototypes' tie order (platform-specific)
V0 = dict(selection="prototype_v0", **COMPAT)


# ---- compatibility: exact agreement with each bundled prototype version

@pytest.mark.parametrize("seed", [0, 1, 2])
def test_port_matches_prototype_v0_exactly_short(seed):
    assert m0.run(M0Config(seed=seed, gens=60, **V0)) == proto.run(seed=seed, gens=60)


def test_port_matches_prototype_v0_exactly_full_run():
    a, b = m0.run(M0Config(seed=4, **V0)), proto.run(seed=4)
    assert a == b
    assert m0.summary(a) == proto.summary(b)


def test_port_matches_prototype_v0_with_other_parameters():
    kw = dict(f_enf=0.02, r_min=0.05, P=3.0, cap_mult=2.0, gens=40)
    assert m0.run(M0Config(seed=7, **V0, **kw)) == proto.run(seed=7, **kw)


@pytest.mark.parametrize("seed", [0, 3])
def test_port_matches_prototype_v1_exactly(seed):
    a, b = m0.run(M0Config(seed=seed, gens=80, **COMPAT)), proto1.run(seed=seed, gens=80)
    assert a == b


def test_redraw_main_matches_prototype_v1_redraw_exactly():
    a = m0.run(M0Config(seed=2, gens=80, enforcer_mode="redraw_main", **COMPAT))
    b = proto1.run(seed=2, gens=80, enf_mode="redraw")
    assert a == b


def test_v0_and_v1_differ():
    # The two selection rules must not silently coincide.
    assert m0.run(M0Config(seed=0, gens=80, **COMPAT)) != m0.run(M0Config(seed=0, gens=80, **V0))


def test_stable_tie_break_is_platform_independent():
    # Pinned values, checked identical on x86 (numpy 2.5.3) and arm64 (numpy 2.2.6).
    got = [round(m0.summary(m0.run(M0Config(seed=s, gens=120))), 6) for s in range(3)]
    assert got == [0.459907, 0.371982, 0.616487]


# ---- impression cap

def test_strict_cap_is_never_exceeded():
    import json
    log = JsonlLog()
    m0.run(M0Config(seed=1, gens=12, cap_mode="strict"), log=log)
    assert all(json.loads(l).get("cap_overflow", 0) == 0 for l in log.lines)
    # and the strict auction itself never assigns beyond remaining capacity
    rng = np.random.default_rng(0)
    b = np.where(rng.random((200, 10)) < 0.7, rng.random((200, 10)), -1.0)
    rem = rng.integers(1, 15, 10)
    w, ok = m0._strict_auction(b, rem)
    assert (np.bincount(w[ok], minlength=10) <= rem).all()
    # every impression with any eligible bidder left is filled
    assert ok.sum() == min(int(((b > 0).any(1)).sum()), int(rem.sum())) or ok.sum() <= rem.sum()


def test_batch_cap_overflow_is_reported():
    import json
    log = JsonlLog()
    m0.run(M0Config(seed=1, gens=12), log=log)
    gens = [json.loads(l) for l in log.lines if json.loads(l)["ev"] == "generation"]
    assert all("cap_overflow" in g for g in gens)


# ---- realized sales use the same definition as accounting

def test_logged_sales_match_revenue():
    import json
    log = JsonlLog()
    m0.run(M0Config(seed=3, gens=10), log=log)
    for line in log.lines:
        e = json.loads(line)
        if e["ev"] == "generation":
            # revenue = honest sales * m + deceptive sales * m(1+delta); bounds check
            assert e["revenue"] <= e["sales"] * 1.2 + 1e-9
            assert e["revenue"] >= e["sales"] * 1.0 - 1e-9


# ---- regression pins (default config: stable ties, platform-independent)
# Exact values, so any change to the default model shows up here. The scientific
# check against the published numbers needs more seeds than a unit test should
# run; it lives in `python -m cli.m0_regression` (30 seeds, tolerance 0.05).
PIN_BASELINE_6 = 0.61752     # seeds 0-5, fixed enforcers, 5%
PIN_REDRAW_6 = 0.00607    # seeds 0-5, separate-stream redraw, 5%


@pytest.fixture(scope="module")
def headline():
    fixed = [m0.summary(m0.run(M0Config(seed=s))) for s in SEEDS]
    redraw = [m0.summary(m0.run(M0Config(seed=s, enforcer_mode="redraw"))) for s in SEEDS]
    return mean_ci(fixed), mean_ci(redraw)


def test_default_baseline_pinned(headline):
    st, _ = headline
    assert round(st["mean"], 5) == PIN_BASELINE_6, st


def test_default_redraw_pinned_and_near_zero(headline):
    _, st = headline
    assert round(st["mean"], 5) == PIN_REDRAW_6, st
    assert st["mean"] < 0.05, st


def test_break_even_formula():
    assert m0.break_even() == pytest.approx(0.2 / 6.2)
    assert round(m0.break_even(), 3) == 0.032


def test_m0_log_is_deterministic_and_replays():
    logs = []
    for _ in range(2):
        log = JsonlLog()
        m0.run(M0Config(seed=11, gens=15), log=log)
        logs.append(log.lines)
    assert logs[0] == logs[1]
    _, new = replay(logs[0])
    assert compare_logs(logs[0], new.lines)["identical"]


def test_m0_accounting():
    log = JsonlLog()
    m0.run(M0Config(seed=2, gens=10), log=log)
    import json
    for line in log.lines:
        e = json.loads(line)
        if e["ev"] == "generation":
            assert e["profit"] == pytest.approx(e["revenue"] - e["penalties"] - e["ad_spend"])
            assert e["catches"] * 5.0 == pytest.approx(e["penalties"])


def test_redraw_does_not_disturb_main_stream():
    # Paired design: the redraw draws come from a separate stream, so the
    # first generation's impressions go to the same customers in both conditions.
    a = m0.run(M0Config(seed=0, gens=1, f_enf=0.0))
    b = m0.run(M0Config(seed=0, gens=1, f_enf=0.0, enforcer_mode="redraw"))
    assert a == b
    assert np.isfinite(a[0]["dec_share_imp"])
