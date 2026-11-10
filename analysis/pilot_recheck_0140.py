"""Pilot recheck at engine 0.14.0 (trapped- and parked-buyer fixes), 2026-11-09. Reruns P2 (enforcement
regression) and P3 (counterfeit smoke) of the choice-set pilot (analysis/pilot_choice_set.py, committed
5ea5f24 at engine 0.12.0) on the same throwaway seeds 900-904 at 150 buyers, with the pilot's own job
and check functions, and compares with the committed numbers (runs/pilot_choice_set.json.gz). Also
reports the stuck-buyer guard of every run. Pilot numbers are pipeline checks, not results.

    .venv/bin/python -m analysis.pilot_recheck_0140     # writes runs/pilot_recheck_0140.md (+ .json.gz)
"""
from __future__ import annotations

import gzip
import json
import os
import platform
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import analysis.pilot_choice_set as P
from engine import ENGINE_VERSION, bazaar

COUNT = 150


def _guard(o):
    if "days" in o:
        return {k: o[k]["total"] for k in ("stuck_buyers", "idle_choosers")}
    return {k: o[k] for k in ("stuck_buyers", "idle_choosers")}


def _job(j):
    """The pilot's P2/P3 job, plus the guard of the same run (one extra run per job: the pilot's _job
    returns only its summaries)."""
    r = P._job(j)
    kind, count, seed, arm = j
    if kind == "p2":
        c = P.cfg(count, seed, "inspectors.count=2", f"inspectors.placement={arm}", days=1)
    else:
        c = P.cfg(count, seed, "inspectors.count=2", "inspectors.placement=patrolling",
                  "pricing.deceptive_price_factor=0.8", reopen=arm)
    r["guard"] = _guard(bazaar.run(c))
    return r


def main() -> int:
    cur = os.nice(0)
    if cur < 19:
        os.nice(19 - cur)
    t0 = time.time()
    with gzip.open("runs/pilot_choice_set.json.gz", "rt", encoding="utf-8") as f:
        old = json.load(f)
    jobs2 = [("p2", COUNT, s, pl) for s in P.SEEDS for pl in ("posts", "patrolling")]
    jobs3 = [("p3", COUNT, s, ro) for s in P.SEEDS for ro in ("fresh", "counterfeit")]
    with ProcessPoolExecutor(4) as ex:
        r2 = list(ex.map(_job, jobs2))
        r3 = list(ex.map(_job, jobs3))
    p2, p3 = P.check_p2(r2), P.check_p3(r3)
    guard = {"p2": {f"{r['key'][2]}|{r['key'][3]}": r["guard"] for r in r2},
             "p3": {f"{r['key'][2]}|{r['key'][3]}": r["guard"] for r in r3}}
    meta = {"engine": ENGINE_VERSION,
            "commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
            "wall_min": round((time.time() - t0) / 60, 1), "old_engine": old["meta"]["engine"],
            "old_commit": old["meta"]["commit"]}
    with gzip.open("runs/pilot_recheck_0140.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "p2": p2, "p3": p3, "guard": guard, "old_p2": old["p2"], "old_p3": old["p3"]}, f)
    o2, o3 = old["p2"], old["p3"]
    L = ["# Choice-set pilot P2 and P3, rechecked at engine 0.14.0", "",
         f"Engine {meta['engine']} at {meta['commit'][:7]} (trapped- and parked-buyer fixes) against the committed "
         f"pilot at engine {meta['old_engine']} ({meta['old_commit'][:7]}). Throwaway seeds 900–904, 150 buyers, "
         "the pilot's own job and check functions. Pipeline checks, not results.", "",
         f"## P2 enforcement regression: **{'pass' if p2['passed'] else 'fail'}** (was {'pass' if o2['passed'] else 'fail'})", "",
         "Single day, naive sellers, 2 inspectors; mean over 5 seeds.", "",
         "| | Engine 0.12.0 | Engine 0.14.0 |", "|---|---|---|"]
    for lab, k, f in (("Deceptive profit per stall, posts ($)", ("posts", "dec_profit"), lambda x: f"{x / 100:,.2f}"),
                      ("Deceptive profit per stall, patrolling ($)", ("patrolling", "dec_profit"), lambda x: f"{x / 100:,.2f}"),
                      ("Shortfall rate, posts", ("posts", "shortfall"), lambda x: f"{x:.3f}"),
                      ("Shortfall rate, patrolling", ("patrolling", "shortfall"), lambda x: f"{x:.3f}"),
                      ("Catches, posts", ("posts", "catches"), lambda x: f"{x:.1f}"),
                      ("Catches, patrolling", ("patrolling", "catches"), lambda x: f"{x:.1f}")):
        L.append(f"| {lab} | {f(o2[k[0]][k[1]])} | {f(p2[k[0]][k[1]])} |")
    L += [f"| Patrolling − posts, deceptive profit ($) | {o2['mean_dec_profit_diff']:+,.2f} | {p2['mean_dec_profit_diff']:+,.2f} |",
          f"| Patrolling − posts, shortfall | {o2['mean_shortfall_diff']:+.3f} | {p2['mean_shortfall_diff']:+.3f} |", "",
          f"## P3 counterfeit smoke: **{'pass' if p3['passed'] else 'fail'}** (was {'pass' if o3['passed'] else 'fail'})", "",
          "Fresh vs counterfeit reopening, deceptive price factor 0.8, 2 patrolling inspectors, 30 days, 5 seeds (totals).", "",
          "| Arm | Engine | Catches | Renames | Counterfeit units sold (to tourists) | Floors |", "|---|---|---|---|---|---|"]
    for arm in ("fresh", "counterfeit"):
        for lab, a in (("0.12.0", o3["arms"][arm]), ("0.14.0", p3["arms"][arm])):
            L.append(f"| {arm} | {lab} | {a['catches']:,} | {sum(a['renames'].values()):,} | {a['counterfeit_units_all']:,} "
                     f"({a['counterfeit_units_to_tourists']:,}) | {'; '.join(a['flags']) or 'none'} |")
    st = sum(g["stuck_buyers"] for part in guard.values() for g in part.values())
    ic = sum(g["idle_choosers"] for part in guard.values() for g in part.values())
    L += ["", f"## Stuck-buyer guard", "", f"Across all {len(r2) + len(r3)} runs: stuck_buyers {st}, idle_choosers {ic}.", "",
          f"Wall clock {meta['wall_min']} min on 4 workers at nice 19; Python {meta['python']}, numpy {meta['numpy']}, "
          f"{meta['platform']}.", ""]
    with open("runs/pilot_recheck_0140.md", "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
