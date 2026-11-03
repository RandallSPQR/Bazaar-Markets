"""M0 regression against the prototype's reported results.

    python -m cli.m0_regression            # baseline + redraw at 5%, seeds 0-5
    python -m cli.m0_regression --sweep    # also the redraw enforcer-rate sweep

Prototype results (sim.py; 6 seeds; mean over generations 221-250):
  baseline, fixed enforcers, 5%, r_min 0.02 : 70% deceptive share [60, 79]
  redraw (independent per impression), 5%  : ~0%
  redraw majority ends between 2% and 3%; analytic e* = 3.2%

Pass criteria:
  baseline : 6-seed mean inside [0.60, 0.79], and its 95% CI overlaps [0.60, 0.79]
  redraw   : 6-seed mean < 0.05
"""
from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor

from engine import m0
from engine.config import M0Config
from engine.metrics import mean_ci

PROTO_BASELINE = (0.70, 0.60, 0.79)


def _one(a):
    mode, f_enf, seed = a
    return m0.summary(m0.run(M0Config(seed=seed, f_enf=f_enf, enforcer_mode=mode)))


def run_cells(cells, seeds, workers):
    jobs = [(mode, f, s) for mode, f in cells for s in seeds]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        r = list(ex.map(_one, jobs))
    return {cell: r[i * len(seeds):(i + 1) * len(seeds)] for i, cell in enumerate(cells)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = ap.parse_args(argv)
    seeds = list(range(args.seeds))
    cells = [("fixed", 0.05), ("redraw", 0.05)]
    if args.sweep:
        cells += [(mode, f) for mode in ("fixed", "redraw") for f in (0.01, 0.02, 0.03, 0.04)]
    res = run_cells(cells, seeds, args.workers)

    def fmt(cell):
        st = mean_ci(res[cell])
        return st, f"{st['mean']:.3f} [{st['lo']:.3f}, {st['hi']:.3f}]  per seed {[round(x, 3) for x in res[cell]]}"

    ok = True
    st, line = fmt(("fixed", 0.05))
    _, plo, phi = PROTO_BASELINE
    base_ok = plo <= st["mean"] <= phi and st["lo"] <= phi and st["hi"] >= plo
    ok &= base_ok
    print(f"baseline fixed 5%   {line}   prototype 0.70 [0.60, 0.79]   {'PASS' if base_ok else 'FAIL'}")
    st, line = fmt(("redraw", 0.05))
    red_ok = st["mean"] < 0.05
    ok &= red_ok
    print(f"redraw 5%           {line}   prototype ~0                  {'PASS' if red_ok else 'FAIL'}")
    if args.sweep:
        print(f"\nanalytic break-even e* = {m0.break_even():.4f}")
        for mode in ("fixed", "redraw"):
            for f in (0.01, 0.02, 0.03, 0.04, 0.05):
                print(f"  {mode:6s} f_enf={f:.2f}  {fmt((mode, f))[1]}")
    print("\nM0 REGRESSION", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
