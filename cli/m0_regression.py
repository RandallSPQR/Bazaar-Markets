"""M0 regression: compatibility with the prototypes, and a scientific check.

    python -m cli.m0_regression                 # both parts
    python -m cli.m0_regression --compat-only   # exact agreement only (fast)
    python -m cli.m0_regression --seeds 50      # more seeds for the scientific part

Part 1, compatibility (exact). With tie_break="numpy_default", the port must
reproduce each bundled prototype's per-generation history bit for bit, seed by
seed: v0 (tests/reference/sim_prototype.py, selection="prototype_v0") and v1
(tests/reference/sim_prototype_v1.py, the default selection). Exactness holds on
the platform where both run; it says nothing about outcomes.

Part 2, scientific check (tolerance). The default config (stable ties,
separate-stream redraw) is compared with the published numbers:
  baseline, fixed enforcers, 5%, r_min 0.02 : 0.695 (doc; prototype v1, 6 seeds)
  redraw, 5%                                 : ~0
Pass rules, prespecified:
  baseline : |mean over N seeds - 0.695| <= 0.05
  redraw   : mean over N seeds < 0.05
0.05 is the smallest difference treated as substantive. It is only testable
with enough seeds: the across-seed SD is about 0.10, so N = 30 gives a 95%
half-width of about 0.04. Below 20 seeds the script warns that the check is
underpowered. The published 0.695 is itself a 6-seed estimate (95% CI roughly
0.60-0.79), so a pass means "consistent with", not "equal to".
"""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor

from engine import m0
from engine.config import M0Config
from engine.metrics import mean_ci

REF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "reference")
PUBLISHED_BASELINE = 0.695
TOL = 0.05
COMPAT_GENS = 80


def _compat(seed: int):
    sys.path.insert(0, REF)
    import sim_prototype as v0
    import sim_prototype_v1 as v1
    ok0 = m0.run(M0Config(seed=seed, gens=COMPAT_GENS, selection="prototype_v0", tie_break="numpy_default")) \
        == v0.run(seed=seed, gens=COMPAT_GENS)
    ok1 = m0.run(M0Config(seed=seed, gens=COMPAT_GENS, tie_break="numpy_default")) == v1.run(seed=seed, gens=COMPAT_GENS)
    return ok0, ok1


def _one(a):
    mode, seed = a
    return m0.summary(m0.run(M0Config(seed=seed, enforcer_mode=mode)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=30, help="seeds for the scientific check")
    ap.add_argument("--compat-seeds", type=int, default=3)
    ap.add_argument("--compat-only", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = ap.parse_args(argv)
    ok = True
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        res = list(ex.map(_compat, range(args.compat_seeds)))
        for s, (a, b) in enumerate(res):
            print(f"compat seed {s}: v0 {'EXACT' if a else 'MISMATCH'}   v1 {'EXACT' if b else 'MISMATCH'}")
            ok &= a and b
        if not args.compat_only:
            if args.seeds < 20:
                print(f"warning: {args.seeds} seeds cannot resolve a {TOL} tolerance; use 20 or more")
            seeds = list(range(args.seeds))
            r = list(ex.map(_one, [(m, s) for m in ("fixed", "redraw") for s in seeds]))
            base, red = mean_ci(r[:len(seeds)]), mean_ci(r[len(seeds):])
            b_ok = abs(base["mean"] - PUBLISHED_BASELINE) <= TOL
            r_ok = red["mean"] < TOL
            print(f"baseline fixed 5%  {base['mean']:.3f} [{base['lo']:.3f}, {base['hi']:.3f}] n={base['n']}   "
                  f"published {PUBLISHED_BASELINE} +/- {TOL}   {'PASS' if b_ok else 'FAIL'}")
            print(f"redraw 5%          {red['mean']:.3f} [{red['lo']:.3f}, {red['hi']:.3f}] n={red['n']}   "
                  f"< {TOL}   {'PASS' if r_ok else 'FAIL'}")
            ok &= b_ok and r_ok
    print("\nM0 REGRESSION", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
