"""Engine 0.14.0 adds the stuck-buyer guard to every outcome (stuck_buyers, idle_choosers; multi-day
results add per-day and total counts). Reference tests written for earlier engines compare outcomes
and logs with these keys removed; everything else must match byte for byte."""
import json
import os

from engine.jsonlog import dumps

GUARD = ("stuck_buyers", "idle_choosers")


def strip_out(out: dict) -> dict:
    o = {k: v for k, v in out.items() if k not in GUARD}
    if "days" in o:
        o["days"] = [{**d, "outcome": {k: v for k, v in d["outcome"].items() if k not in GUARD}} for d in o["days"]]
    return o


def strip_line(line: str) -> str:
    if '"ev":"outcome"' not in line:
        return line
    e = json.loads(line)
    return dumps({k: v for k, v in e.items() if k not in GUARD})


def strip_lines(lines) -> list:
    return [strip_line(x) for x in lines]


_V0140 = os.path.join(os.path.dirname(__file__), "reference", "outcomes_v0140.json")
CHANGED_0140 = set()
if os.path.exists(_V0140):
    with open(_V0140, encoding="utf-8") as f:
        CHANGED_0140 = {(tuple(c["overrides"]), c["seed"]) for c in json.load(f)["cells"].values()}


def changed_in_0140(cell: dict) -> bool:
    """A reference cell that engine 0.14.0 changes on purpose (trapped- or parked-buyer fix); older
    reference tests skip it, and tests/test_trapped_buyers.py checks it against its 0.14.0 reference."""
    return (tuple(cell["overrides"]), cell["seed"]) in CHANGED_0140
