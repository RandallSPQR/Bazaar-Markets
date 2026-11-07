"""The shared floor check (analysis/floors.py)."""
import gzip
import json
import os

from analysis.floors import floor_flags, floor_series
from engine import bazaar
from engine.config import load

LATE = list(range(26, 31))
ALL = list(range(1, 31))
RUN = os.path.join(os.path.dirname(__file__), "..", "runs", "search_counterfeit.json.gz")


def _run(values, m="task_complete", early=0.0):
    days = [{m: early} for _ in range(25)] + [{m: x} for x in values]
    return {"days": days}


def test_flags_zero_in_every_seed_and_says_whether_earlier_days_were_zero():
    v = {"a": [_run([0] * 5), _run([0] * 5)], "b": [_run([0] * 5, early=0.3), _run([0] * 5)]}
    f = floor_flags(v, LATE, ALL)
    assert len(f) == 2
    assert "a: task completion is 0 in every seed (2)" in f[0] and "also 0 on every day" in f[0]
    assert "b:" in f[1] and "not 0 on every earlier day" in f[1]


def test_no_flag_when_any_seed_is_nonzero_or_values_are_missing():
    v = {"a": [_run([0] * 5), _run([0, 0, 0, 0, 0.1])],
         "b": [_run([None] * 5), _run([None] * 5)],
         "c": [_run([0] * 5), _run([None] * 5)]}
    assert floor_flags(v, LATE, ALL) == []


def test_purchases_and_sales_are_checked():
    runs = [{"days": [{"purchases": 0, "sales_genuine": 0, "sales_deceptive": 3}] * 30} for _ in range(3)]
    f = floor_flags({"x": runs}, LATE)
    assert [x.split(" is 0")[0] for x in f] == ["x: purchases", "x: units sold by genuine stalls"]


def test_floor_series_reads_an_engine_outcome():
    o = bazaar.run(load(None, ["market.ticks=80", "seed=3"], mode="bazaar"))
    s = floor_series(o)
    assert s["purchases"] == o["purchases"] and s["task_complete"] == o["task_complete_share"]
    for t in ("genuine", "deceptive"):
        assert s[f"sales_{t}"] == o["seller_by_type"][t]["units_sold"]


def test_catches_the_floor_the_old_check_missed():
    """Task completion was 0 late in every seed at budgets 1.0 and 1.1 in the 2026-11-06 run."""
    with gzip.open(RUN, "rt", encoding="utf-8") as fh:
        d = json.load(fh)
    v: dict = {}
    for r in d["runs"]:
        v.setdefault(r["cond"], []).append(r)
    f = floor_flags(v, LATE, ALL)
    flagged = {x.split(":")[0] for x in f if "task completion" in x}
    assert {"1|fresh|t40|honest|2-2-2", "1.1|fresh|t40|honest|2-2-2"} <= flagged
    assert not any(c.startswith("1.25|") or c.startswith("1.5|") for c in flagged)
