"""Randall's G4 decision (2026-11-26, D3): exits by stall type x cell x day, with exit reasons.

Reruns the pilot's never chains (every Run A, B and C cell on seeds 900-902) with the exit-reason field added to
`aisles_1_3.job` as instrumentation only, and checks that every field already in the pilot cache comes out identical
(the digest check: same outcome, only the new field added). Then tabulates exits per cell by type (genuine, seconds,
deceptive), by reason (insolvency, other) and by day (before day 10, by day 30), and the calibration chains' exits
(no fixed cost, solvency off, alpha 0) for comparison. Writes runs/pilot_aisles/exits_by_type.json.
"""
import hashlib
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor

from analysis import aisles_1_3 as AS

OUT = "runs/pilot_aisles/exits_by_type.json"
TYPES = ("genuine", "seconds", "deceptive")


def _digest(r: dict) -> str:
    r = {k: v for k, v in r.items() if k not in ("secs", "exit_reason")}
    return hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()


def table(r: dict, reasons: bool) -> dict:
    types = {s: a["stype"] for s, a in r["stall_agg"].items()}
    t = {ty: {"stalls": sum(1 for v in types.values() if v == ty), "before10": 0, "by30": 0} for ty in TYPES}
    if reasons:
        for ty in TYPES:
            t[ty].update({"before10_insolvency": 0, "by30_insolvency": 0})
    for s, d in r["exited"].items():
        ty = types[s]
        t[ty]["by30"] += 1
        t[ty]["before10"] += d < 10
        if reasons and r["exit_reason"][s] == "insolvency":
            t[ty]["by30_insolvency"] += 1
            t[ty]["before10_insolvency"] += d < 10
    return t


def add(a: dict, b: dict) -> dict:
    return {ty: {k: a.get(ty, {}).get(k, 0) + v for k, v in b[ty].items()} for ty in TYPES}


def main():
    t0 = time.time()
    cache = [json.loads(line) for line in open(f"{AS.PILOT_DIR}/aisles_pilot_cache.jsonl", encoding="utf-8")]
    never = {r["key"]: r for r in cache if r["kind"] == "bench" and r["b"] == AS.NEVER}
    cal = json.load(open(AS.CAL_FILE, encoding="utf-8"))["groups"]
    samples = {sd: AS.sample_stalls(sd) for sd in AS.PILOT}
    runs = ["A", "B", "C"]
    jobs = [j for j in AS.jobs_for(runs, {r: AS.PILOT for r in runs}, cal, samples) if j[0] == "bench" and j[5] == AS.NEVER]
    assert len(jobs) == len(never) == 90, (len(jobs), len(never))
    with ProcessPoolExecutor(7, initializer=AS._init_worker) as ex:
        new = list(ex.map(AS.job, jobs))
    same = {r["key"]: _digest(r) == _digest(never[r["key"]]) for r in new}
    print(f"rerun {len(new)} never chains in {time.time() - t0:.0f} s; identical apart from exit_reason: "
          f"{sum(same.values())}/{len(same)}", flush=True)
    cells: dict = {}
    for r in new:
        cells[r["name"]] = add(cells.get(r["name"], {}), table(r, True))
    calx: dict = {}
    for r in cache:
        if r["kind"] == "cal":
            calx[r["name"]] = add(calx.get(r["name"], {}), table(r, False))
    out = {"made": time.strftime("%Y-%m-%d %H:%M:%S"), "seeds": AS.PILOT, "script_sha256": AS._script_sha(),
           "digest_check": {"chains": len(same), "identical": sum(same.values()), "pass": all(same.values()),
                            "differ": sorted(k for k, v in same.items() if not v)},
           "cells": dict(sorted(cells.items())), "calibration_chains": dict(sorted(calx.items())),
           "wall_s": round(time.time() - t0, 1)}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(f"written {OUT}", flush=True)
    return 0 if out["digest_check"]["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
