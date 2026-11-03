"""Sweep a grid of conditions over seeds; report mean and 95% t-CI per
condition, plus paired differences against the first condition.

    python -m cli.sweep --mode m0 --grid enforcer_mode=fixed,redraw --grid f_enf=0.02,0.03,0.05 --seeds 6
    python -m cli.sweep --mode bazaar --grid inspectors.count=0,2,6 --seeds 0-9 --normalize --out runs/insp.json

Seeds are the replication unit. Every condition runs on the same seed list,
so differences are paired by seed.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import os
from concurrent.futures import ProcessPoolExecutor

from engine.config import _parse_value, load
from engine.metrics import mean_ci, paired_diff
from engine.runner import run_config

M0_METRICS = ["dec_share_imp_last", "final_dec_pop"]
BAZAAR_METRICS = ["buyer_surplus_mean_cents", "shortfall_rate", "task_complete_share",
                  "quantity_fulfilled_share", "empty_handed_share",
                  "deceptive_share_impressions", "deceptive_share_sales_units", "inspections", "catches",
                  "profit_per_stall.genuine", "profit_per_stall.seconds", "profit_per_stall.deceptive",
                  "inspector_active_ticks.dedicated", "inspector_active_ticks.inspector_buyers",
                  "surplus_rel", "shortfall_rel"]


def parse_seeds(s: str) -> list[int]:
    if "-" in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    if "," in s:
        return [int(x) for x in s.split(",")]
    return list(range(int(s)))


def flatten(out: dict) -> dict:
    flat = dict(out)
    for t, d in out.get("seller_by_type", {}).items():
        flat[f"profit_per_stall.{t}"] = d["profit_per_stall_cents"]
    return flat


def _job(args):
    config, overrides, normalize = args
    cfg = load(config["path"], overrides, mode=config["mode"])
    out, _ = run_config(cfg, log_path=None, normalize=normalize)
    return flatten(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--mode", choices=["m0", "bazaar"])
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--grid", action="append", default=[], metavar="KEY=V1,V2,...")
    ap.add_argument("--seeds", default="6", help="N (0..N-1), A-B, or a comma list")
    ap.add_argument("--normalize", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--metrics", help="comma list; default depends on mode")
    ap.add_argument("--out", help="write JSON results here (and a .csv of per-seed rows next to it)")
    args = ap.parse_args(argv)

    seeds = parse_seeds(args.seeds)
    axes = []
    for g in args.grid:
        k, _, vals = g.partition("=")
        axes.append([(k, v) for v in vals.split(",")])
    conditions = [list(c) for c in itertools.product(*axes)] if axes else [[]]
    mode = args.mode or load(args.config).mode
    metrics = args.metrics.split(",") if args.metrics else (M0_METRICS if mode == "m0" else BAZAAR_METRICS)

    jobs = []
    for cond in conditions:
        for s in seeds:
            ov = list(args.set) + [f"{k}={v}" for k, v in cond] + [f"seed={s}"]
            jobs.append(({"path": args.config, "mode": args.mode}, ov, args.normalize))
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as ex:
        results = list(ex.map(_job, jobs))

    rows, summary = [], []
    per_cond: list[dict] = []
    for ci, cond in enumerate(conditions):
        res = results[ci * len(seeds):(ci + 1) * len(seeds)]
        vals = {m: [r.get(m) for r in res] for m in metrics}
        per_cond.append(vals)
        label = {k: _parse_value(v) for k, v in cond}
        entry = {"condition": label, "seeds": seeds, "metrics": {m: mean_ci(vals[m]) for m in metrics}}
        if ci > 0:
            entry["paired_vs_first"] = {m: paired_diff(per_cond[0][m], vals[m]) for m in metrics}
        summary.append(entry)
        for s, r in zip(seeds, res):
            rows.append({**label, "seed": s, **{m: r.get(m) for m in metrics}})

    for e in summary:
        print(json.dumps(e["condition"]))
        for m, st in e["metrics"].items():
            if st["mean"] is None:
                continue
            ci = f"[{st['lo']:.4g}, {st['hi']:.4g}]" if st["lo"] is not None else ""
            line = f"  {m:32s} {st['mean']:.4g} {ci}"
            pd = e.get("paired_vs_first", {}).get(m)
            if pd and pd["mean"] is not None and pd["lo"] is not None:
                line += f"   diff vs first {pd['mean']:+.4g} [{pd['lo']:+.4g}, {pd['hi']:+.4g}]"
            print(line)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"mode": mode, "overrides": args.set, "summary": summary}, f, indent=1)
        with open(os.path.splitext(args.out)[0] + ".csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader(); w.writerows(rows)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
