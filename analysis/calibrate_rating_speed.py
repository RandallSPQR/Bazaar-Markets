"""Calibration of the rating-speed dial (ratings.prior_n, engine 0.18.0) for Brand Equity at the genuine tier.
Pilot seeds 900-902 only, before any main run.

For each prior_n on the grid: W_g chains (contract white labels at the genuine tier, N 6 from day 10) for the 3
sampled owners of each seed at t40 and t100, and the never chain. Measured: days from day 10 (= 1) until a fresh
contract white label's end-of-day rating first reaches 0.9 (mean over the labels that reach it; the share that reach
it by day 30), and the owner's own rating at the end of day 10 (it builds under the same prior). Levels are chosen
from these measurements to give about 1 (the current market, prior_n 0), 5 and 15 days at t40.

    PYTHONPATH=. .venv/bin/python -m analysis.calibrate_rating_speed --grid 0,25,50,100,200,400,800,1600
    PYTHONPATH=. .venv/bin/python -m analysis.calibrate_rating_speed --grid ... --choose slow5=X,slow15=Y
"""
from __future__ import annotations

import argparse
import json
import os
import time
from types import SimpleNamespace

import numpy as np

import analysis.brand_equity_tier as T
import analysis.chainrun as CR
import analysis.licensing as L
from analysis.counterfeit import _git, _load
from engine import ENGINE_VERSION
from engine.metrics import mean_ci

SEEDS = [900, 901, 902]
OUT = "runs/calibration_rating_speed"


def jobs(grid):
    out = []
    for pn in grid:
        for sd in SEEDS:
            for t in T.VERS:
                out.append(("never", "-", t, sd, None, T.ROYALTY, pn))
                for s in L.sample_stalls(sd):
                    out.append(("Wg", "contract", t, sd, s, T.ROYALTY, pn))
    return out


def summarise(runs, grid):
    idx = {(r["arm"], r["t"], r["seed"], r["owner"], T._pk(r["prior_n"])): r for r in runs}
    rows = []
    for pn in grid:
        for t in T.VERS:
            days, share, own_nv, own_wg, all_days = [], [], [], [], []
            for sd in SEEDS:
                nv = idx[("never", t, sd, None, T._pk(pn))]
                d_s, sh_s, ow_s = [], [], []
                for s in L.sample_stalls(sd):
                    W = idx[("Wg", t, sd, s, T._pk(pn))]
                    dd = [T.days_to(W["rating"][l]) for l in W["licensees"]]
                    got = [x for x in dd if x is not None]
                    all_days += got
                    if got:
                        d_s.append(float(np.mean(got)))
                    sh_s.append(len(got) / len(dd))
                    ow_s.append(T._r(W["rating"][s][T.B_DAY - 1]))
                days.append(float(np.mean(d_s)) if d_s else None)
                share.append(float(np.mean(sh_s)))
                own_nv.append(float(np.mean([T._r(nv["rating"][s][T.B_DAY - 1]) for s in L.sample_stalls(sd)])))
                own_wg.append(float(np.mean(ow_s)))
            rows.append({"prior_n": float(pn), "t": t, "days_to_0.9": mean_ci(days), "share_reaching": mean_ci(share),
                         "median_days": float(np.median(all_days)) if all_days else None,
                         "range_days": [min(all_days), max(all_days)] if all_days else None,
                         "owner_rating_day10_never": mean_ci(own_nv), "owner_rating_day10_Wg": mean_ci(own_wg),
                         "per_seed_days": days})
    return rows


def _f(st, dp=1):
    if st is None or st.get("mean") is None:
        return "–"
    s = f"{st['mean']:.{dp}f}"
    if st.get("lo") is not None:
        s += f" [{st['lo']:.{dp}f}, {st['hi']:.{dp}f}]"
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True, help="comma-separated prior_n values")
    ap.add_argument("--choose", default="", help="label=prior_n,... the chosen levels")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    grid = [float(x) for x in a.grid.split(",")]
    os.makedirs(OUT, exist_ok=True)
    log = CR.file_logger(os.path.join(OUT, "calibration_run.log"))
    t0 = time.time()
    log(f"calibration: engine {ENGINE_VERSION}, commit {_git()['commit'][:7]}, grid {grid}, load {_load()}")
    ns = SimpleNamespace(workers=a.workers, min_swap_mb=512, min_free_pct=15)
    runs, _ = CR.run_chains(ns, jobs(grid), os.path.join(OUT, "calibration_cache.jsonl"), log, T.job, T.key)
    rows = summarise(runs, grid)
    chosen = dict(x.split("=") for x in a.choose.split(",")) if a.choose else {}
    res = {"engine_version": ENGINE_VERSION, "git": _git(), "seeds": SEEDS, "grid": grid, "rows": rows,
           "chosen": {k: float(v) for k, v in chosen.items()}, "wall_s": time.time() - t0, "chains": len(runs)}
    with open(os.path.join(OUT, "calibration.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    for r in rows:
        log(f"prior_n {r['prior_n']:g} {r['t']}: days to 0.9 {_f(r['days_to_0.9'])}, reach "
            f"{_f(r['share_reaching'], 2)}, median {r['median_days']}, range {r['range_days']}, owner day 10 never "
            f"{_f(r['owner_rating_day10_never'], 3)}, W_g {_f(r['owner_rating_day10_Wg'], 3)}")
    log(f"done; {len(runs)} chains; wall {(time.time() - t0) / 60:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
