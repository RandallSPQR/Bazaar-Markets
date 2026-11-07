"""Floor check shared by the run scripts.

A cell (condition) is at a floor for a metric when that metric is exactly 0 in every seed over the
window the results are reported on (default: late days 26-30). The metrics checked are task
completion, purchases, and units sold by each seller type present (genuine, deceptive, seconds).

Added after the 2026-11-06 search-depth run, where task completion was 0 late in every seed at
budgets 1.0x and 1.1x and the old check (shortfall and invalid actions only) did not flag it.
A metric that is missing (None) in a seed counts as not observed, not as 0; a cell with no observed
value is not flagged.
"""
from __future__ import annotations

TYPES = ("genuine", "deceptive", "seconds")
FLOOR_METRICS = {"task_complete": "task completion", "purchases": "purchases",
                 **{f"sales_{t}": f"units sold by {t} stalls" for t in TYPES}}


def floor_series(o: dict) -> dict:
    """Per-day values for the floor check, from one day's outcome. Sales by a seller type that has
    no stalls that day are None."""
    by = o.get("seller_by_type", {})
    return {"task_complete": o.get("task_complete_share"), "purchases": o.get("purchases"),
            **{f"sales_{t}": (by[t]["units_sold"] if t in by and by[t].get("stalls") else None) for t in TYPES}}


def _total(run: dict, m: str, days: list[int]):
    xs = [run["days"][d - 1].get(m) for d in days]
    xs = [x for x in xs if x is not None]
    return sum(xs) if xs else None


def floor_flags(v: dict, days: list[int], all_days: list[int] | None = None, window: str = "days 26–30") -> list[str]:
    """v: {cond: [run per seed]}, each run with run["days"][i] holding the FLOOR_METRICS keys.
    Returns one message per (cond, metric) that is 0 in every seed over `days`."""
    flags = []
    for cond, runs in v.items():
        for m, label in FLOOR_METRICS.items():
            tot = [_total(r, m, days) for r in runs]
            seen = [x for x in tot if x is not None]
            if not seen or len(seen) < len(tot) or any(x != 0 for x in seen):
                continue
            msg = f"{cond}: {label} is 0 in every seed ({len(seen)}) over {window}"
            if all_days is not None:
                whole = [_total(r, m, all_days) for r in runs]
                msg += ("; also 0 on every day" if all(x == 0 for x in whole if x is not None)
                        else "; not 0 on every earlier day")
            flags.append(msg)
    return flags
