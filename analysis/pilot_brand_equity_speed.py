"""Pilot gate for Brand Equity speed (engine 0.19.0). Seeds 900-902, every cell. Writes
runs/pilot_brand_equity_speed/pilot_gates.json; the gate report is runs/pilot_brand_equity_speed.md.

  G1: the pipeline runs end to end and the summary renders.
  G2: identities. (a) Scope "all", 30 days, prior_n 50: never, R and W_g chains for seeds 300-301 (both
      verifications, the 3 owners of each seed) equal the 0.18.0 slow15 chains (runs/brand_equity_tier_cache.jsonl)
      by full-outcome digest and every ledger, to the cent. (b) J identity to the cent; the split and the windows add
      up. (c) Genuine-tier prices match the formula. (d) The royalty no-decision replay passes.
  G3: timing: the main run's wall clock projected on 4 workers at nice 19 from the pilot's throughput (60-day chains
      only); limit 6 h. If over, first drop t100 to two levels (current and slowest), then cut seeds to 15; if still
      over, stop and report.
  G4: under scope "new", day-1 brands' ratings equal the prior_n 0 chain's (same arm, verification, seed and owner)
      on every day to day 10, in every pilot chain.
  G5: stuck / parked / idle guard 0 (and no invalid actions) in every pilot chain.

    PYTHONPATH=. .venv/bin/python -m analysis.pilot_brand_equity_speed --tests "..."
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import time
from types import SimpleNamespace

import analysis.brand_equity_speed as S
import analysis.chainrun as CR
import analysis.licensing as L
from analysis.counterfeit import _git, _load
from engine import ENGINE_VERSION
from engine.jsonlog import dumps

SEEDS = "900-902"
LIMIT_H = 6.0
OUT = "runs/pilot_brand_equity_speed"
MAIN_SEEDS = 20
G2_SEEDS = (300, 301)
G2_PRIOR = 50.0


def g2_jobs():
    out = []
    for sd in G2_SEEDS:
        for t in S.VERS:
            out.append(("never", t, sd, None, S.ROYALTY, G2_PRIOR, 30, "all"))
            for s in L.sample_stalls(sd):
                for arm in ("R", "Wg"):
                    out.append((arm, t, sd, s, S.ROYALTY, G2_PRIOR, 30, "all"))
    return out


def n_chains(n_seeds, t100_levels):
    keep = S.T100_LEVELS
    S.T100_LEVELS = t100_levels
    try:
        sm = {sd: ["a", "b", "c"] for sd in range(n_seeds)}
        main = len(S.jobs_for(list(range(n_seeds)), sm, S.LEVELS))
    finally:
        S.T100_LEVELS = keep
    return main + 2 * 3 * len(S.CHECK_RATES)          # royalty-check chains at 0.05 and 0.25


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", default="")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    os.makedirs(OUT, exist_ok=True)
    log = CR.file_logger(os.path.join(OUT, "pilot_run.log"))
    log(f"pilot: engine {ENGINE_VERSION}, commit {_git()['commit'][:7]}, seeds {SEEDS}, levels {S.LEVELS}, "
        f"load {_load()}")
    G = {}
    # the pilot run (60-day chains), timed for G3
    t0 = time.time()
    rc_ = S.main(["--pilot", "--seeds", SEEDS, "--outdir", os.path.join(OUT, "run"), "--workers", str(a.workers),
                  "--tests", a.tests, "--gate", "pilot (this is the pilot)"])
    wall = time.time() - t0
    log(f"pilot run: exit {rc_}, wall {wall:.0f} s, load {_load()}")
    with open(os.path.join(OUT, "run", "brand_equity_speed_cache.jsonl"), encoding="utf-8") as f:
        runs = [json.loads(x) for x in f]
    with gzip.open(os.path.join(OUT, "run", "brand_equity_speed.json.gz"), "rt", encoding="utf-8") as f:
        out = json.load(f)
    res, roy = out["results"], out["royalty_check"]
    summ = open(os.path.join(OUT, "run", "brand_equity_speed_summary.md"), encoding="utf-8").read()
    G["G1"] = {"pass": rc_ in (0, 2) and "## Predictions" in summ and "READING_PLACEHOLDER" in summ
               and all(p in summ for p in S.PREDICTIONS), "exit": rc_, "chains": len(runs), "flags": res["flags"]}
    # G2 (a): the 0.18.0 chains, scope "all", 30 days
    t1 = time.time()
    ns = SimpleNamespace(workers=a.workers, min_swap_mb=512, min_free_pct=15)
    g2, _ = CR.run_chains(ns, g2_jobs(), os.path.join(OUT, "g2_cache.jsonl"), log, S.job, S.key)
    g2_wall = time.time() - t1
    ref = {}
    with open(S.OLD_CACHE, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["seed"] in G2_SEEDS and abs(r["prior_n"] - G2_PRIOR) < 1e-12:
                ref[r["key"]] = r
    eq, bad = 0, []
    for r in g2:
        o = ref.get(S.old_key(r))
        same = o is not None and o["digest"] == r["digest"] and o["win"] == r["win"] and o["all30"] == r["all"] \
            and o["totals"] == r["totals"]
        eq += same
        if not same:
            bad.append(r["key"])
    idn = res["identity"]
    G["G2"] = {"pass": eq == len(g2) == len(g2_jobs()) and not bad and idn["J_mismatch"] == 0
               and abs(idn["split_resid_max_abs"]) < 1e-6 and idn["window_resid_max_abs"] == 0
               and idn["tier_price_miss"] == 0 and idn["tier_price_chains"] > 0 and roy["pass"],
               "ref_0180": {"chains": len(g2), "equal": eq, "reference_chains": len(ref), "unequal": bad,
                            "wall_s": g2_wall},
               "J": idn, "royalty_check": roy["pass"], "royalty_rows": len(roy["rows"])}
    # G3: timing from the 60-day pilot chains
    n_pilot = len(runs)
    per = wall / n_pilot
    steps = [("all levels at t100, 20 seeds", MAIN_SEEDS, None)]
    lv = list(S.LEVELS)
    steps += [(f"t100 at {lv[0]} and {lv[-1]} only, 20 seeds", MAIN_SEEDS, [lv[0], lv[-1]]),
              (f"t100 at {lv[0]} and {lv[-1]} only, 15 seeds", 15, [lv[0], lv[-1]])]
    proj = [{"design": d, "seeds": n, "t100_levels": t1_, "chains": n_chains(n, t1_),
             "hours": per * n_chains(n, t1_) / 3600} for d, n, t1_ in steps]
    choice = next((p for p in proj if p["hours"] <= LIMIT_H), None)
    G["G3"] = {"pass": choice is not None, "per_chain_s": per, "pilot_chains": n_pilot, "pilot_wall_s": wall,
               "projections": proj, "choice": choice, "load": _load()}
    # G4: day-1 brands under scope "new" equal the prior_n 0 chain to day 10
    idx = {(r["arm"], r["t"], r["seed"], r["owner"], S._rk(r["royalty"])): {} for r in runs}
    for r in runs:
        idx[(r["arm"], r["t"], r["seed"], r["owner"], S._rk(r["royalty"]))][S._pk(r["prior_n"])] = r
    p0 = S._pk(S.LEVELS[S.CURRENT])
    checked, fails = 0, []
    for k, by in idx.items():
        base = by.get(p0)
        if base is None:
            continue
        for pk, r in by.items():
            if pk == p0:
                continue
            checked += 1
            names = sorted(set(base["d1_ratings"]) | set(r["d1_ratings"]))
            if any(dumps(base["d1_ratings"].get(n)) != dumps(r["d1_ratings"].get(n)) for n in names):
                fails.append(r["key"])
    G["G4"] = {"pass": checked > 0 and not fails, "chains_checked": checked, "fails": fails}
    # G5
    badg = [r["key"] for r in runs + g2 if r["guard"]["stuck_buyers"] or r["guard"]["parked"]
            or r["guard"]["idle_choosers"] or r["guard"]["fallbacks"]]
    G["G5"] = {"pass": not badg, "chains": len(runs) + len(g2), "bad": badg}
    with open(os.path.join(OUT, "pilot_gates.json"), "w", encoding="utf-8") as f:
        json.dump(G, f, indent=1)
    log("gates: " + ", ".join(f"{k} {'pass' if v['pass'] else 'FAIL'}" for k, v in G.items()))
    return 0 if all(v["pass"] for v in G.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
