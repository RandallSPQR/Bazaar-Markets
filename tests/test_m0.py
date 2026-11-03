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
import sim_prototype as proto  # noqa: E402

SEEDS = range(6)


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_port_matches_prototype_exactly_short(seed):
    assert m0.run(M0Config(seed=seed, gens=60)) == proto.run(seed=seed, gens=60)


def test_port_matches_prototype_exactly_full_run():
    a, b = m0.run(M0Config(seed=4)), proto.run(seed=4)
    assert a == b
    assert m0.summary(a) == proto.summary(b)


def test_port_matches_prototype_with_other_parameters():
    kw = dict(f_enf=0.02, r_min=0.05, P=3.0, cap_mult=2.0, gens=40)
    assert m0.run(M0Config(seed=7, **kw)) == proto.run(seed=7, **kw)


@pytest.fixture(scope="module")
def headline():
    fixed = [m0.summary(m0.run(M0Config(seed=s))) for s in SEEDS]
    redraw = [m0.summary(m0.run(M0Config(seed=s, enforcer_mode="redraw"))) for s in SEEDS]
    return mean_ci(fixed), mean_ci(redraw)


def test_baseline_reproduces_prototype(headline):
    st, _ = headline
    # Prototype: 70% [60, 79] over 6 seeds. Mean must land inside that interval
    # and the intervals must overlap.
    assert 0.60 <= st["mean"] <= 0.79, st
    assert st["lo"] <= 0.79 and st["hi"] >= 0.60, st


def test_redraw_removes_deception_at_5pct(headline):
    _, st = headline
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
