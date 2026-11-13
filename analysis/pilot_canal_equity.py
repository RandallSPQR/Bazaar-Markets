"""Pilot gate for Canal Street and Brand Equity (engine 0.17.0). Seeds 900-902, both runs, every condition.
Writes runs/pilot_canal_equity.md; the pilot outputs go to runs/pilot_canal_equity/{canal,equity}.

  G1: both pipelines run end to end and their summaries render.
  G2: identities. (a) Canal Street counterfeits-off chains equal the 0.16.0 never chains for the same seeds and
      config (full-outcome digest; 0.16.0 run from a git worktree at --ref). (b) Brand Equity never chains equal the
      licensing run's never chains at seeds 250-252 (saved totals, day units and ratings of the sampled stalls in
      runs/licensing_cache.jsonl, and the 0.16.0 full-outcome digest). (c) The J identity holds to the cent.
  G3: timing: each main run's wall clock projected on 4 workers at nice 19 from the pilot's throughput; each must be
      <= 5.5 h. If one is over, cut its seeds to 20 (not conditions) and say so; if still over, stop and report.
  G4: counterfeits trade: at phi 1.0, t100, every seed has counterfeit sales; units per counterfeit stall-day by
      phi; any phi cell with counterfeits priced below unit cost on > 10% of stall-days is reported (design
      unchanged).
  G5: stuck / parked / idle guard 0 in every pilot chain.

    PYTHONPATH=. .venv/bin/python -m analysis.pilot_canal_equity --ref 60f1ddf --tests "..."
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import sys
import time

import numpy as np

import analysis.brand_equity as E
import analysis.canal_street as K
import analysis.chainrun as CR
import analysis.licensing as L
from analysis.capture import memory_state
from analysis.counterfeit import _git, _load
from engine import ENGINE_VERSION

SEEDS = [900, 901, 902]
G2B_SEEDS = [250, 251, 252]
LIMIT_H = 5.5
OUT = "runs/pilot_canal_equity"
MAIN = {"canal": (K, 30, len(K.CONDS)), "equity": (E, 30, 2 + len(E.QUALS) * len(E.VERS) * 3 * 2)}

OLD_SCRIPT = r'''
import hashlib, json, sys
from concurrent.futures import ProcessPoolExecutor
import analysis.licensing as L
from engine import ENGINE_VERSION, bazaar, benchmark
from engine.jsonlog import dumps

def one(j):
    t, ds, seed = j
    out = bazaar.run(benchmark.licence_config(L.config(t, ds, seed), None, benchmark.NEVER))
    return {"t": t, "ds": ds, "seed": seed, "digest": hashlib.sha256(dumps(out).encode()).hexdigest(),
            "version": ENGINE_VERSION}

if __name__ == "__main__":
    jobs = json.loads(sys.argv[1])
    with ProcessPoolExecutor(4) as ex:
        print(json.dumps(list(ex.map(one, [tuple(j) for j in jobs]))))
'''


def _old_digests(ref: str, jobs: list, log) -> list[dict]:
    """Full-outcome digests of 0.16.0 never chains, from a detached git worktree at `ref` (removed after)."""
    wt = os.path.abspath(os.path.join(OUT, "wt_0160"))
    if os.path.exists(wt):
        subprocess.run(["git", "worktree", "remove", "--force", wt], check=True)
    subprocess.run(["git", "worktree", "add", "--detach", wt, ref], check=True, capture_output=True)
    try:
        with open(os.path.join(wt, "_digest.py"), "w") as f:
            f.write(OLD_SCRIPT)
        env = {**os.environ, "PYTHONPATH": wt}
        r = subprocess.run(["nice", "-n", "19", os.path.abspath(".venv/bin/python"), "_digest.py", json.dumps(jobs)],
                           cwd=wt, env=env, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(r.stderr[-2000:])
        out = json.loads(r.stdout.strip().splitlines()[-1])
        log(f"0.16.0 digests: {len(out)} chains at {ref}, engine {out[0]['version']}")
        return out
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", wt], check=True)


def _read_cache(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="commit with engine 0.16.0 for the G2 identities")
    ap.add_argument("--tests", default="")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--min-swap-mb", type=float, default=512)
    ap.add_argument("--min-free-pct", type=float, default=15)
    a = ap.parse_args(argv)
    os.makedirs(OUT, exist_ok=True)
    log = CR.file_logger(os.path.join(OUT, "pilot_run.log"))
    log(f"pilot: engine {ENGINE_VERSION}, commit {_git()['commit'][:7]}, seeds {SEEDS}, load {_load()}")
    G = {}
    wall = {}
    # G1: both pipelines, timed
    for name, mod in (("canal", K), ("equity", E)):
        t0 = time.time()
        rc = mod.main(["--pilot", "--seeds", "900-902", "--outdir", os.path.join(OUT, name), "--workers",
                       str(a.workers), "--tests", a.tests, "--gate", "pilot (this is the pilot)"])
        wall[name] = time.time() - t0
        log(f"{name} pilot: exit {rc}, wall {wall[name]:.0f} s, load {_load()}")
    canal = _read_cache(os.path.join(OUT, "canal", "canal_street_cache.jsonl"))
    equity = _read_cache(os.path.join(OUT, "equity", "brand_equity_cache.jsonl"))
    s_c = open(os.path.join(OUT, "canal", "canal_street_summary.md"), encoding="utf-8").read()
    s_e = open(os.path.join(OUT, "equity", "brand_equity_summary.md"), encoding="utf-8").read()
    G["G1"] = {"pass": "## Predictions" in s_c and "## Predictions" in s_e and "READING_PLACEHOLDER" in s_c
               and "## Gate" in s_e, "canal_chains": len(canal), "equity_chains": len(equity)}
    # G2b chains at 0.17.0: brand-equity never chains at seeds 250-252
    g2_jobs = [("never", "-", t, sd, None, E.ROYALTY) for sd in G2B_SEEDS for t in E.VERS]
    g2_runs, _ = CR.run_chains(a, g2_jobs, os.path.join(OUT, "g2_cache.jsonl"), log, E.job, E.key)
    # 0.16.0 digests: canal off cells at 900-902, never at 250-252
    old_jobs = [[t, ds, sd] for sd in SEEDS for t in K.VERS for ds in K.DSS] + [[t, 1.0, sd] for sd in G2B_SEEDS
                                                                               for t in E.VERS]
    old = {(o["t"], float(o["ds"]), o["seed"]): o["digest"] for o in _old_digests(a.ref, old_jobs, log)}
    off = [r for r in canal if r["cond"].startswith("off|")]
    g2a = [{"cond": r["cond"], "seed": r["seed"],
            "equal": r["digest"] == old[(K.parts(r["cond"])[1], K.parts(r["cond"])[2], r["seed"])]} for r in off]
    nev = [r for r in equity if r["arm"] == "never"]
    g2a_e = [{"t": r["t"], "seed": r["seed"], "equal": r["digest"] == old[(r["t"], 1.0, r["seed"])]} for r in nev]
    saved = {}
    with open("runs/licensing_cache.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.startswith('{"key":"never|'):
                r = json.loads(line)
                if r["seed"] in G2B_SEEDS and r["cond"].endswith("ds1.0"):
                    saved[(r["cond"].split("|")[0], r["seed"])] = r
    g2b = []
    for r in g2_runs:
        sv = saved[(r["t"], r["seed"])]
        w = sorted(sv["totals"])
        tot_ok = all(r["totals"][s] == sv["totals"][s] for s in w)
        # day units and ratings of the sampled stalls, from the saved per-day record
        units_ok = all(r["units_daily"][s][d] == sv["days"][d]["units"][s] for s in w for d in range(30))
        rat_ok = all(r["rating"][s][d] == sv["days"][d]["rating"][s] for s in w for d in range(30))
        g2b.append({"t": r["t"], "seed": r["seed"], "totals_equal": tot_ok, "units_equal": units_ok,
                    "ratings_equal": rat_ok, "digest_equal": r["digest"] == old[(r["t"], 1.0, r["seed"])]})
    with gzip.open(os.path.join(OUT, "equity", "brand_equity.json.gz"), "rt", encoding="utf-8") as f:
        eq = json.load(f)
    ident = eq["results"]["identity"]
    G["G2"] = {"pass": all(x["equal"] for x in g2a) and all(x["equal"] for x in g2a_e)
               and all(x["totals_equal"] and x["units_equal"] and x["ratings_equal"] and x["digest_equal"] for x in g2b)
               and ident["J_mismatch"] == 0 and abs(ident["split_resid_max_abs"]) < 1e-6
               and eq["royalty_check"]["pass"],
               "canal_off": g2a, "equity_never_pilot": g2a_e, "equity_never_250": g2b, "J": ident,
               "royalty_check": eq["royalty_check"]["pass"]}
    # G3: projection from the pilot throughput
    proj = {}
    for name, (mod, n_seeds, per_seed) in MAIN.items():
        pilot_chains = G["G1"][f"{name}_chains"]
        main_chains = n_seeds * per_seed + (12 if name == "equity" else 0)
        per = wall[name] / pilot_chains
        h = per * main_chains / 3600
        cut = None
        if h > LIMIT_H:
            main20 = 20 * per_seed + (12 if name == "equity" else 0)
            cut = {"seeds": 20, "chains": main20, "hours": per * main20 / 3600}
        proj[name] = {"pilot_chains": pilot_chains, "pilot_wall_s": wall[name], "per_chain_s": per,
                      "main_chains": main_chains, "hours": h, "cut": cut}
    G["G3"] = {"pass": all(p["hours"] <= LIMIT_H or (p["cut"] and p["cut"]["hours"] <= LIMIT_H) for p in proj.values()),
               "proj": proj, "queue_hours": sum(p["hours"] if p["hours"] <= LIMIT_H else p["cut"]["hours"]
                                                for p in proj.values()), "load": _load()}
    # G4: counterfeits trade
    by = {}
    for r in canal:
        arm, t, ds = K.parts(r["cond"])
        if arm == "off":
            continue
        cfs = list(r["counterfeit_of"])
        units = [r["series"]["units"][s][d] for s in cfs for d in range(1, 30)]
        below = sum(r["below_cost"]) / max(1, len(units))
        by.setdefault((arm, t, ds), []).append({"seed": r["seed"], "units": sum(units), "per_day": float(np.mean(units)),
                                               "below": below})
    g4 = {f"{arm}|{t}|ds{ds!r}": {"seeds_with_sales": sum(x["units"] > 0 for x in v), "seeds": len(v),
                                 "units_per_stall_day": float(np.mean([x["per_day"] for x in v])),
                                 "below_cost_share": float(np.mean([x["below"] for x in v]))}
          for (arm, t, ds), v in sorted(by.items())}
    trade_ok = all(g4[f"phi1.0|t100|ds{ds!r}"]["seeds_with_sales"] == len(SEEDS) for ds in K.DSS)
    G["G4"] = {"pass": trade_ok, "cells": g4,
               "below_cost_over_10pct": [k for k, v in g4.items() if v["below_cost_share"] > 0.10]}
    # G5: guard in every pilot chain
    allr = canal + equity + g2_runs
    bad = [r["key"] for r in allr if r["guard"]["stuck_buyers"] or r["guard"]["parked"] or r["guard"]["idle_choosers"]]
    G["G5"] = {"pass": not bad, "chains": len(allr), "bad": bad,
               "fallbacks": sum(r["guard"]["fallbacks"] for r in allr)}
    json.dump(G, open(os.path.join(OUT, "pilot_gates.json"), "w"), indent=1)
    log("gates: " + ", ".join(f"{k} {'pass' if v['pass'] else 'FAIL'}" for k, v in G.items()))
    return 0 if all(v["pass"] for v in G.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
