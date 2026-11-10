"""Never-bust-out honest-stall profit with and without inspectors, after the trapped-buyer fix
(spec 2026-11-09, Stage B rerun). Reads the committed CSVs only: the sampled genuine stall's 30-day
never-chain total, averaged over the 3 sampled stalls per seed; seeds 200-219 paired; unadjusted
95% t-intervals (engine.metrics). Stage A at 0.13.0 (no closures, unaffected), Stage B at 0.14.0, and
the superseded Stage B at 0.13.0 for comparison.

    .venv/bin/python -m analysis.never_profit_0140
"""
import collections
import csv

import numpy as np

from engine.metrics import mean_ci, paired_diff

FILES = {"A": "runs/verification_A.csv", "B": "runs/verification_B.csv", "B_v0130": "runs/verification_B_v0130.csv"}
CONDS = ["t40|l1", "t40|l0", "t70|l1", "t70|l0", "t100"]


def load(p):
    d = collections.defaultdict(lambda: collections.defaultdict(list))
    with open(p, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d[r["condition"].split("|", 1)[1]][int(r["seed"])].append(int(r["never_total_cents"]) / 100)
    return {c: {s: float(np.mean(v)) for s, v in x.items()} for c, x in d.items()}


def fmt(c):
    return f"{c['mean']:,.0f} [{c['lo']:,.0f}, {c['hi']:,.0f}]"


def main():
    D = {k: load(p) for k, p in FILES.items()}
    print("| Condition | Stage A, no inspectors ($) | Stage B, 2 inspectors, 0.14.0 ($) | B − A ($) | "
          "Stage B at 0.13.0, superseded ($) | 0.14.0 − 0.13.0 ($) |")
    print("|---|---:|---:|---:|---:|---:|")
    for c in CONDS:
        seeds = sorted(D["A"][c])
        a, b, b0 = ([D[k][c][s] for s in seeds] for k in ("A", "B", "B_v0130"))
        print(f"| {c} | {fmt(mean_ci(a))} | {fmt(mean_ci(b))} | {fmt(paired_diff(a, b))} | {fmt(mean_ci(b0))} | "
              f"{fmt(paired_diff(b0, b))} |")


if __name__ == "__main__":
    main()
