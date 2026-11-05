"""Recognition range, full-shift disguised inspectors, and backward compatibility
with engine 0.3.0."""
import json
import os

import pytest

from engine import bazaar
from engine.config import load
from engine.jsonlog import JsonlLog, dumps

ADAPTIVE = "agents.seller.deceptive=rule_deceptive_adaptive"
REF = os.path.join(os.path.dirname(__file__), "reference", "outcomes_v030.json")


def cfg(*ov, seed=0):
    return load(overrides=[*ov, f"seed={seed}"], mode="bazaar")


def _ref_cells():
    with open(REF, encoding="utf-8") as f:
        return sorted(json.load(f)["cells"].items())


@pytest.mark.parametrize("key,cell", _ref_cells())
def test_default_config_reproduces_engine_030(key, cell):
    """Byte-identical to 0.3.0 outcomes (written at c7cf7fe), except the one field
    0.4.0 drops on purpose: reachable.shortfall_rate."""
    old = json.loads(cell["outcome"])
    del old["reachable"]["shortfall_rate"]
    new = bazaar.run(cfg(*cell["overrides"], seed=cell["seed"]))
    assert dumps(new) == dumps(old)


def test_reachable_shortfall_rate_is_gone():
    out = bazaar.run(cfg("market.ticks=60"))
    assert "shortfall_rate" not in out["reachable"]
    assert set(out["reachable"]) == {"share", "buyers", "task_complete_share", "buyer_surplus_mean_cents"}


# ---------------------------------------------------------------- recognition range

def _seller_rows(c):
    log = JsonlLog(keep=True)
    eng = bazaar.BazaarEngine(c, log=log)
    out = eng.run()
    rows = [row for x in log.lines for e in [json.loads(x)]
            if e["ev"] == "obs" and e["role"] == "seller" for row in e["obs"]["passersby"]]
    return eng, out, rows


def test_recognition_zero_never_shows_a_uniform():
    eng, out, rows = _seller_rows(cfg("inspectors.count=6", "inspectors.placement=posts", "inspectors.uniformed=true",
                                      "inspectors.recognition_range=0", ADAPTIVE))
    uni = {p.pid for p in eng.people if p.uniform}
    assert uni and any(r["id"] in uni for r in rows)          # uniformed inspectors were in earshot
    assert all(r["uniform"] is False for r in rows)           # but never recognized
    assert all(set(r) == {"id", "observed_profile", "distance", "uniform"} for r in rows)
    assert out["catches"] > 0                                 # so the adaptive seller can be caught


@pytest.mark.parametrize("r", [1.0, 2.0, 3.0])
def test_uniform_recognized_exactly_within_range(r):
    eng, _, rows = _seller_rows(cfg("inspectors.count=6", "inspectors.placement=patrolling",
                                    "inspectors.uniformed=true", f"inspectors.recognition_range={r}", ADAPTIVE,
                                    "market.ticks=120"))
    uni = {p.pid for p in eng.people if p.uniform}
    n_true = n_far = 0
    for row in rows:
        if row["id"] in uni:
            # distance is rounded to 3 places in the observation; compare with a tolerance
            if row["distance"] < r - 1e-3:
                assert row["uniform"] is True
            elif row["distance"] > r + 1e-3:
                assert row["uniform"] is False
                n_far += 1
            n_true += row["uniform"]
        else:
            assert row["uniform"] is False
    assert n_true > 0 and n_far > 0


def test_recognition_equal_to_earshot_is_the_default():
    a = bazaar.run(cfg("inspectors.count=2", "inspectors.placement=posts", "inspectors.uniformed=true", ADAPTIVE))
    b = bazaar.run(cfg("inspectors.count=2", "inspectors.placement=posts", "inspectors.uniformed=true", ADAPTIVE,
                       "inspectors.recognition_range=4.0"))
    assert dumps(a) == dumps(b)


@pytest.mark.parametrize("placement", ["posts", "patrolling"])
def test_naive_sellers_ignore_recognition_range(placement):
    outs = [dumps(bazaar.run(cfg("inspectors.count=2", f"inspectors.placement={placement}",
                                 "inspectors.uniformed=true", f"inspectors.recognition_range={r}")))
            for r in ("0", "2.0", "null")]
    assert outs[0] == outs[1] == outs[2]


def test_recognition_range_changes_adaptive_outcomes():
    """Dose matters for a seller that reads the uniform (otherwise the sweep is empty)."""
    c = ["inspectors.count=6", "inspectors.placement=patrolling", "inspectors.uniformed=true", ADAPTIVE]
    a = bazaar.run(cfg(*c, "inspectors.recognition_range=0"))
    b = bazaar.run(cfg(*c))
    assert a["catches"] > b["catches"] == 0


# ---------------------------------------------------------------- full-shift disguised

@pytest.mark.parametrize("count", [2, 6])
def test_full_shift_equals_posts_effort(count):
    ticks = 240
    fs = bazaar.BazaarEngine(cfg(f"inspectors.count={count}", "inspectors.placement=disguised",
                                 "inspectors.disguised_shift=full_shift"))
    o_fs = fs.run()
    o_posts = bazaar.run(cfg(f"inspectors.count={count}", "inspectors.placement=posts"))
    o_single = bazaar.run(cfg(f"inspectors.count={count}", "inspectors.placement=disguised"))
    assert o_fs["inspector_active_ticks"]["dedicated"] == count * ticks == o_posts["inspector_active_ticks"]["dedicated"]
    assert o_single["inspector_active_ticks"]["dedicated"] < count * ticks
    for p in fs.people:
        if p.kind == "inspector":
            assert p.arrive == 0 and len(p.route) == ticks + 1 and not p.uniform
            assert all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a, b in zip(p.route, p.route[1:]))


def test_full_shift_inspector_routes_do_not_depend_on_headcount():
    r2 = [p.route for p in bazaar.BazaarEngine(cfg("inspectors.count=2", "inspectors.placement=disguised",
                                                   "inspectors.disguised_shift=full_shift")).people
          if p.kind == "inspector"]
    r6 = [p.route for p in bazaar.BazaarEngine(cfg("inspectors.count=6", "inspectors.placement=disguised",
                                                   "inspectors.disguised_shift=full_shift")).people
          if p.kind == "inspector"]
    assert r6[:2] == r2


def test_full_shift_uniform_flag_never_applies():
    eng = bazaar.BazaarEngine(cfg("inspectors.count=3", "inspectors.placement=disguised", "inspectors.uniformed=true",
                                  "inspectors.disguised_shift=full_shift"))
    assert not any(p.uniform for p in eng.people)


def test_unknown_disguised_shift_is_rejected():
    with pytest.raises(ValueError):
        bazaar.BazaarEngine(cfg("inspectors.placement=disguised", "inspectors.disguised_shift=half"))
