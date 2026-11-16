"""Pilot gate for Brand Equity at the genuine tier, with rating speed (engine 0.18.0). Seeds 900-902, every
condition and level. Writes runs/pilot_brand_equity_tier/pilot_gates.json; the gate report is
runs/pilot_brand_equity_tier.md.

  G1: the pipeline runs end to end and the summary renders.
  G2: identities. (a) At current speed, never, R and W_t chains equal the 0.17.0 Brand Equity pilot chains
      (runs/pilot_canal_equity/equity/brand_equity_cache.jsonl) by full-outcome digest and every ledger, to the
      cent. (b) J identity to the cent; the reputation split adds up. (c) The royalty no-decision replay passes
      (current speed, both qualities; slowest speed, contract). (d) Every W_g white label posts base x (1 + premium
      x (rating - 0.5)) on every day from 10.
  G3: timing: the main run's wall clock projected on 4 workers at nice 19 from the pilot's throughput; <= 5.5 h.
      If over, cut the 5-day level first, then seeds (to 20).
  G4: contract seconds-type W_g white labels price above unit cost on > 90% of stall-days (reported, design
      unchanged), with the share for every cell.
  G5: stuck / parked / idle guard 0 in every pilot chain.

    PYTHONPATH=. .venv/bin/python -m analysis.pilot_brand_equity_tier --tests "..."
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import time

import analysis.brand_equity_tier as T
import analysis.chainrun as CR
from analysis.counterfeit import _git, _load
from engine import ENGINE_VERSION

SEEDS = "900-902"
LIMIT_H = 5.5
OUT = "runs/pilot_brand_equity_tier"
REF = "runs/pilot_canal_equity/equity/brand_equity_cache.jsonl"
MAIN_SEEDS = 30


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", default="")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    os.makedirs(OUT, exist_ok=True)
    log = CR.file_logger(os.path.join(OUT, "pilot_run.log"))
    log(f"pilot: engine {ENGINE_VERSION}, commit {_git()['commit'][:7]}, seeds {SEEDS}, levels {T.LEVELS}, load {_load()}")
    G = {}
    t0 = time.time()
    rc = T.main(["--pilot", "--seeds", SEEDS, "--outdir", os.path.join(OUT, "run"), "--workers", str(a.workers),
                 "--tests", a.tests, "--gate", "pilot (this is the pilot)", "--ref-cache", REF])
    wall = time.time() - t0
    log(f"pilot run: exit {rc}, wall {wall:.0f} s, load {_load()}")
    with open(os.path.join(OUT, "run", "brand_equity_tier_cache.jsonl"), encoding="utf-8") as f:
        runs = [json.loads(x) for x in f]
    with gzip.open(os.path.join(OUT, "run", "brand_equity_tier.json.gz"), "rt", encoding="utf-8") as f:
        out = json.load(f)
    res, roy = out["results"], out["royalty_check"]
    summ = open(os.path.join(OUT, "run", "brand_equity_tier_summary.md"), encoding="utf-8").read()
    G["G1"] = {"pass": rc in (0, 2) and "## Predictions" in summ and "READING_PLACEHOLDER" in summ,
               "exit": rc, "chains": len(runs), "flags": res["flags"]}
    # G2
    expect = sum(1 for r in runs if r["prior_n"] == T.LEVELS[T.CURRENT] and r["arm"] in ("never", "R", "Wt")
                 and abs(r["royalty"] - T.ROYALTY) < 1e-12)
    idn = res["identity"]
    G["G2"] = {"pass": res["ref"].get("compared") == expect and res["ref"].get("equal") == expect
               and idn["J_mismatch"] == 0 and abs(idn["split_resid_max_abs"]) < 1e-6 and roy["pass"]
               and idn["tier_price_miss"] == 0 and idn["tier_price_chains"] > 0,
               "ref_017": res["ref"], "expected": expect, "J": idn, "royalty_check": roy["pass"],
               "royalty_rows": len(roy["rows"])}
    # G3
    def n_chains(levels, n_seeds=MAIN_SEEDS):
        sm = {sd: ["a", "b", "c"] for sd in range(n_seeds)}
        extra = [j for j in T.check_jobs_for(0, sm, levels) if abs(j[5] - T.ROYALTY) > 1e-12]
        return len(T.jobs_for(list(range(n_seeds)), sm, levels)) + len(extra)
    n_pilot = n_chains(T.LEVELS, 3)
    n_main = n_chains(T.LEVELS)
    per = wall / n_pilot
    h = per * n_main / 3600
    cut = None
    if h > LIMIT_H:
        lv = {k: v for k, v in T.LEVELS.items() if k != "slow5"}
        cut = {"levels": list(lv), "chains": n_chains(lv), "hours": per * n_chains(lv) / 3600}
        if cut["hours"] > LIMIT_H:
            cut["seeds20"] = {"chains": n_chains(lv, 20), "hours": per * n_chains(lv, 20) / 3600}
    G["G3"] = {"pass": h <= LIMIT_H or (cut is not None and min(cut["hours"], cut.get("seeds20", {}).get("hours", 1e9))
                                        <= LIMIT_H),
               "per_chain_s": per, "pilot_chains": n_pilot, "pilot_cached": len(runs), "pilot_wall_s": wall,
               "main_chains": n_main, "hours": h, "cut": cut, "load": _load()}
    # G4
    cells = {}
    for r in runs:
        if r["arm"] != "Wg" or "above_cost" not in r:
            continue
        k = f"p{T._pk(r['prior_n'])}|{r['quality']}|{r['t']}"
        for st, (n_above, n) in r["above_cost"].items():
            c = cells.setdefault(f"{k}|{st}", [0, 0])
            c[0] += n_above
            c[1] += n
    share = {k: (v[0] / v[1] if v[1] else None) for k, v in sorted(cells.items())}
    key4 = [k for k in share if k.endswith("|seconds") and "|contract|" in k]
    G["G4"] = {"pass": bool(key4) and all(share[k] is not None and share[k] > 0.90 for k in key4), "share": share,
               "checked": key4}
    # G5
    bad = [r["key"] for r in runs if r["guard"]["stuck_buyers"] or r["guard"]["parked"] or r["guard"]["idle_choosers"]]
    G["G5"] = {"pass": not bad, "chains": len(runs), "bad": bad, "fallbacks": sum(r["guard"]["fallbacks"] for r in runs)}
    with open(os.path.join(OUT, "pilot_gates.json"), "w", encoding="utf-8") as f:
        json.dump(G, f, indent=1)
    log("gates: " + ", ".join(f"{k} {'pass' if v['pass'] else 'FAIL'}" for k, v in G.items()))
    return 0 if all(v["pass"] for v in G.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
