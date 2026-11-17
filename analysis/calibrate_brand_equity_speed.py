"""Calibration of the rating-speed dial for Brand Equity speed (engine 0.19.0, ratings.prior_scope "new", 60 days).
Seeds 900-904 only, before any pilot or main run.

For each prior_n on the grid: R and W_g chains (contract, t40, N 6 from day 10) for the 3 sampled owners of each
seed, as analysis.brand_equity_speed.job runs them. Measured: days from day 10 (= 1) until each W_g white label's
end-of-day rating first reaches 0.9, pooled over labels, owners and seeds: mean, 10th and 90th percentile, the share
that reach it by day 60, and the per-seed means with a 95% t interval; the owner-level catch-up day (mean label rating
>= 0.9); the owner's rating at the end of day 10; the mean day-20 rating of deceptive stalls' reopened names.

Levels target about 1 (prior_n 0), 5, 10 and 20 days. A level passes the spread rule when its 10th-90th percentile
range lies within its mean +-50%. Choose by the calibration; refine the grid where a level fails.

    PYTHONPATH=. .venv/bin/python -m analysis.calibrate_brand_equity_speed --grid 0,1,2,3,5,10,25,50,100,200,400
    PYTHONPATH=. .venv/bin/python -m analysis.calibrate_brand_equity_speed --grid ... --choose d5=X,d10=Y,d20=Z
"""
from __future__ import annotations

import argparse
import json
import os
import time
from types import SimpleNamespace

import numpy as np

import analysis.brand_equity_speed as S
import analysis.chainrun as CR
import analysis.licensing as L
from analysis.counterfeit import _git, _load
from engine import ENGINE_VERSION
from engine.metrics import mean_ci

SEEDS = [900, 901, 902, 903, 904]
OUT = "runs/calibration_brand_equity_speed"
T = "t40"


def jobs(grid):
    return [(arm, T, sd, s, S.ROYALTY, pn, S.DAYS, S.SCOPE) for pn in grid for sd in SEEDS for s in L.sample_stalls(sd)
            for arm in ("R", "Wg")]


def summarise(runs, grid):
    idx = {(r["arm"], r["seed"], r["owner"], S._pk(r["prior_n"])): r for r in runs}
    rows = []
    for pn in grid:
        pooled, reached, owner_days, per_seed, own10, reo = [], [], [], [], {"R": [], "Wg": []}, {"R": [], "Wg": []}
        for sd in SEEDS:
            ds = []
            for s in L.sample_stalls(sd):
                W = idx[("Wg", sd, s, S._pk(pn))]
                for l in W["licensees"]:
                    x = S.days_to(W["rating"][l])
                    reached.append(x is not None)
                    if x is not None:
                        pooled.append(x)
                        ds.append(x)
                cd = S.catch_day(W, W["licensees"])
                owner_days.append(None if cd is None else cd - S.B_DAY + 1)
                for arm in ("R", "Wg"):
                    rec = idx[(arm, sd, s, S._pk(pn))]
                    own10[arm].append(S._r(rec["rating"][s][S.B_DAY - 1]))
                    reo[arm].append(rec["reopen_d20"]["mean"])
            per_seed.append(float(np.mean(ds)) if ds else None)
        m = float(np.mean(pooled)) if pooled else None
        p10, p90 = (float(np.percentile(pooled, 10)), float(np.percentile(pooled, 90))) if pooled else (None, None)
        od = [x for x in owner_days if x is not None]
        rows.append({"prior_n": float(pn), "mean": m, "p10": p10, "p90": p90,
                     "spread_ok": m is not None and p10 >= 0.5 * m and p90 <= 1.5 * m,
                     "share_reaching": float(np.mean(reached)), "per_seed": per_seed, "seed_ci": mean_ci(per_seed),
                     "median": float(np.median(pooled)) if pooled else None,
                     "range": [min(pooled), max(pooled)] if pooled else None, "labels": len(reached),
                     "owner_catch_days": float(np.mean(od)) if od else None,
                     "owners_reaching": len(od) / len(owner_days),
                     "owner_rating_day10": {a: float(np.mean(v)) for a, v in own10.items()},
                     "reopen_d20": {a: (float(np.mean([x for x in v if x is not None])) if any(x is not None for x in v)
                                        else None) for a, v in reo.items()}})
    return rows


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
    log(f"calibration: engine {ENGINE_VERSION}, commit {_git()['commit'][:7]}, grid {grid}, seeds {SEEDS}, "
        f"load {_load()}")
    ns = SimpleNamespace(workers=a.workers, min_swap_mb=512, min_free_pct=15)
    runs, _ = CR.run_chains(ns, jobs(grid), os.path.join(OUT, "calibration_cache.jsonl"), log, S.job, S.key)
    rows = summarise(runs, grid)
    chosen = dict(x.split("=") for x in a.choose.split(",")) if a.choose else {}
    flags = []
    for r in runs:
        g = r["guard"]
        if g["stuck_buyers"] or g["parked"] or g["idle_choosers"] or g["fallbacks"] or r["profit_mismatch"] \
                or r.get("tier_price_miss"):
            flags.append(r["key"])
    res = {"engine_version": ENGINE_VERSION, "git": _git(), "seeds": SEEDS, "grid": grid, "rows": rows,
           "chosen": {k: float(v) for k, v in chosen.items()}, "wall_s": time.time() - t0, "chains": len(runs),
           "flags": flags, "load_end": _load()}
    with open(os.path.join(OUT, "calibration.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    for r in rows:
        log(f"prior_n {r['prior_n']:g}: days to 0.9 mean {r['mean']}, p10-p90 {r['p10']}-{r['p90']} "
            f"(spread {'ok' if r['spread_ok'] else 'WIDE'}), reach {r['share_reaching']:.2f}, owner catch-up "
            f"{r['owner_catch_days']}, owner d10 {r['owner_rating_day10']}, reopened d20 {r['reopen_d20']}")
    log(f"done; {len(runs)} chains; {len(flags)} flagged; wall {(time.time() - t0) / 60:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
