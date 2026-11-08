"""Pilot gate for the verification-boundary run (2026-11-08). Throwaway seeds 905-909 only: never reuse
them for confirmatory work. Pilot numbers are pipeline checks, not results.

Settings are the main run's (analysis/verification.py): choice-set demand, m 3, gamma 0, 150 buyers,
budget 1.25 x base, tourists 0.4 (locals 0.3, experts 0.3), D = 30, ratings public, bargain share 0.2 with
bargain Q_req [0.15, 0.40], every genuine stall honest (the never chain).

G1 seconds: seconds stalls average >= 1 customer a day over days 1-10 (mean over seconds stall-seeds;
   the share of seconds stall-seeds at >= 1 is reported too). No inspectors.
G2 demand: the previous pilot's P0 still passes (>= 90% of genuine stall-seeds average >= 1 customer a
   day over days 1-10; >= 80% of genuine brands rated by day 10). No inspectors.
G3 catch rate: 2 patrolling inspectors, choice-set vs walk mode (only buyers.demand_mode differs; walk
   mode uses its default search depth 1), 30 days, same seeds. Reported per mode: catches a day,
   false-claim messages a day, false claims with an inspector in earshot, false-claim impressions
   received by inspectors. Criterion, fixed before G3 ran: the difference is explained if the ratio of
   catches (choice-set / walk) is within 25% of the ratio of false claims made with an inspector in
   earshot (catches per such claim within 25% across modes).
G4 timing: one condition of the main grid at full size (16 chains per seed) for 2 seeds, in each
   stage (tourists 0.4, locals inspect), because the stages run at different speeds (stage B has
   inspectors); project wall clock for both stages at 30 seeds as A rate x A chains + B rate x B chains;
   if over 10 h the main run uses 20 seeds (200-219).

    .venv/bin/python -m analysis.pilot_verification    # writes runs/pilot_verification.md (+ .json.gz)
"""
from __future__ import annotations

import gzip
import json
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from analysis import verification as V
from analysis.capture import memory_state
from engine import ENGINE_VERSION, bazaar
from engine import benchmark as B
from engine.config import load

SEEDS = list(range(905, 910))
TIMING_CONDS, TIMING_SEEDS = ("A|t40|l1", "B|t40|l1"), "905-906"
STAGE_CHAINS = len(V.BASE_CONDS) * 30 * (1 + V.N_SAMPLE * len(V.CANDS))
TOTAL_CHAINS = 2 * STAGE_CHAINS
LIMIT_H = 10.0


def _honest(seed):
    out = bazaar.run(B.bust_config(V.config("A|t40|l1", seed), None, None))
    days = []
    for d in out["days"][:10]:
        o = d["outcome"]
        days.append({"types": d["stall_types"], "customers": o["demand"]["customers"], "ratings": d["ratings"]})
    return {"seed": seed, "days": days}


def _catch(args):
    seed, mode = args
    ov = [*V.overrides("B|t40|l1"), f"buyers.demand_mode={mode}", f"seed={seed}"]
    out = bazaar.run(B.bust_config(load(None, ov, mode="bazaar"), None, None))
    rows = []
    for d in out["days"]:
        o = d["outcome"]
        fc = o["false_claims"]
        rows.append({"catches": o["catches"], "false_msgs": fc["messages"],
                     "false_in_earshot": fc["messages"] - fc["no_eligible_in_earshot"],
                     "false_impr_to_inspectors": o["false_claim_impressions_to_uniform_eligible"],
                     "false_impr": o["false_claim_impressions"], "purchases": o["purchases"],
                     "deceptive_units": o["seller_by_type"].get("deceptive", {}).get("units_sold")})
    return {"seed": seed, "mode": mode, "days": rows}


def g12(runs):
    def per(t):
        return [float(np.mean([d["customers"][s] for d in r["days"]])) for r in runs
                for s, tt in r["days"][0]["types"].items() if tt == t]
    sec, gen = per("seconds"), per("genuine")
    rated = [r["days"][-1]["ratings"][s] is not None for r in runs
             for s, tt in r["days"][0]["types"].items() if tt == "genuine"]
    by_type = {t: {"stalls": len(per(t)), "mean": float(np.mean(per(t))), "share_ge1": float(np.mean([x >= 1 for x in per(t)])),
                   "min": float(np.min(per(t)))} for t in ("genuine", "deceptive", "seconds")}
    g1 = {"mean_seconds": float(np.mean(sec)), "share_seconds_ge1": float(np.mean([x >= 1 for x in sec])),
          "passed": float(np.mean(sec)) >= 1.0}
    g2 = {"share_genuine_ge1": float(np.mean([x >= 1 for x in gen])), "share_genuine_rated_d10": float(np.mean(rated))}
    g2["passed"] = g2["share_genuine_ge1"] >= 0.90 and g2["share_genuine_rated_d10"] >= 0.80
    return g1, g2, by_type


def g3(runs):
    out = {}
    for mode in ("choice_set", "walk"):
        rs = [r for r in runs if r["mode"] == mode]
        tot = lambda k: float(np.mean([sum(d[k] for d in r["days"]) / len(r["days"]) for r in rs]))
        out[mode] = {k: tot(k) for k in ("catches", "false_msgs", "false_in_earshot", "false_impr_to_inspectors",
                                         "false_impr", "purchases", "deceptive_units")}
        out[mode]["catches_per_claim_in_earshot"] = out[mode]["catches"] / out[mode]["false_in_earshot"] \
            if out[mode]["false_in_earshot"] else None
    c, w = out["choice_set"], out["walk"]
    rc = c["catches"] / w["catches"] if w["catches"] else None
    re_ = c["false_in_earshot"] / w["false_in_earshot"] if w["false_in_earshot"] else None
    out["ratio_catches"], out["ratio_claims_in_earshot"] = rc, re_
    out["passed"] = rc is not None and re_ is not None and abs(rc / re_ - 1) <= 0.25
    return out


def main() -> int:
    os.nice(19)
    t0 = time.time()
    log = lambda m: print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {m}", flush=True)
    meta = {"engine": ENGINE_VERSION, "python": platform.python_version(), "numpy": np.__version__,
            "platform": platform.platform(), "load_start": [round(x, 2) for x in os.getloadavg()],
            "mem_start": memory_state(),
            "commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "script_sha256": __import__("hashlib").sha256(open(__file__, "rb").read()).hexdigest(),
            "verification_sha256": V._script_sha()}
    log(f"pilot gate; engine {ENGINE_VERSION}, commit {meta['commit'][:7]}")
    with ProcessPoolExecutor(4) as ex:
        honest = list(ex.map(_honest, SEEDS))
        G1, G2, by_type = g12(honest)
        log(f"G1 {G1}; G2 {G2}")
        catch = list(ex.map(_catch, [(s, m) for s in SEEDS for m in ("choice_set", "walk")]))
    G3 = g3(catch)
    log(f"G3 {G3}")
    # G4: the main script's timing mode, as a separate process (as the run will be)
    tdir = os.path.join(os.environ.get("TMPDIR", "/tmp"), "verification_timing")
    tims = {}
    for cond in TIMING_CONDS:
        r = subprocess.run([sys.executable, "-m", "analysis.verification", "--timing", cond, "--seeds", TIMING_SEEDS,
                            "--outdir", tdir, "--min-swap-mb", "512"], capture_output=True, text=True)
        tims[cond] = json.loads(r.stdout.strip().splitlines()[-1])
        log(f"G4 {cond}: {tims[cond]}")
    proj_h = sum(tm["per_chain_s"] for tm in tims.values()) * STAGE_CHAINS / 3600
    tim = {"chains": sum(tm["chains"] for tm in tims.values()), "wall_s": sum(tm["wall_s"] for tm in tims.values()),
           "by_cond": tims}
    G4 = {**tim, "total_chains_30_seeds": TOTAL_CHAINS, "projected_h_30_seeds": proj_h,
          "projected_h_20_seeds": proj_h * 20 / 30, "seeds_for_main": "200-229" if proj_h <= LIMIT_H else "200-219",
          "passed": True}
    log(f"G4 {G4}")
    meta.update(wall_min=(time.time() - t0) / 60, load_end=[round(x, 2) for x in os.getloadavg()], mem_end=memory_state())
    with gzip.open("runs/pilot_verification.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "G1": G1, "G2": G2, "by_type": by_type, "G3": G3, "G4": G4, "honest": honest,
                   "catch": catch}, f)
    ok = lambda g: "pass" if g["passed"] else "**FAIL**"
    c, w = G3["choice_set"], G3["walk"]
    L = ["# Pilot gate: verification boundary", "",
         "**Pilot, not results.** Throwaway seeds 905–909; never reuse them for confirmatory work.", "",
         "## Setting", "",
         "The main run's settings (`analysis/verification.py`): choice-set demand, m 3, gamma 0, 150 buyers, budget 1.25 × "
         "base, tourists 0.4 (locals 0.3, experts 0.3), D = 30, ratings public (memory 0.7), brands on (premium 0.4), "
         "bargain hunters 0.2 with Q_req 0.15–0.40, naive deceptive sellers, fresh reopening, every genuine stall honest.",
         f"- Engine `{ENGINE_VERSION}`, commit `{meta['commit']}`; script sha256 `{meta['script_sha256']}`; "
         f"verification.py sha256 `{meta['verification_sha256']}`.",
         f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}; 4 workers at nice 19; wall clock "
         f"{meta['wall_min']:.1f} min; load {meta['load_start']} → {meta['load_end']}; memory {meta['mem_start']} → "
         f"{meta['mem_end']}.", "",
         "## Gates", "",
         f"- **G1 seconds** ({ok(G1)}): seconds stalls average {G1['mean_seconds']:.2f} customers a day over days 1–10 "
         f"(gate ≥ 1); {G1['share_seconds_ge1']:.0%} of seconds stall-seeds are at ≥ 1.",
         f"- **G2 demand** ({ok(G2)}): {G2['share_genuine_ge1']:.0%} of genuine stall-seeds average ≥ 1 customer a day "
         f"(gate ≥ 90%); {G2['share_genuine_rated_d10']:.0%} of genuine brands rated by day 10 (gate ≥ 80%).",
         f"- **G3 catch rate** ({ok(G3)}): catches a day choice-set {c['catches']:.1f} vs walk {w['catches']:.1f} "
         f"(ratio {G3['ratio_catches']:.2f}); false claims made with an inspector in earshot a day "
         f"{c['false_in_earshot']:.1f} vs {w['false_in_earshot']:.1f} (ratio {G3['ratio_claims_in_earshot']:.2f}); "
         f"criterion: catch ratio within 25% of the in-earshot claim ratio.",
         f"- **G4 timing**: tourists 0.4 / locals inspect at full size, seeds {TIMING_SEEDS}: "
         + "; ".join(f"{c}: {tm['chains']} chains in {tm['wall_s'] / 60:.1f} min ({tm['per_chain_s']:.1f} s a chain on 4 "
                     f"workers)" for c, tm in tims.items()) + ". Projected for both stages: "
         f"{proj_h:.1f} h at 30 seeds ({TOTAL_CHAINS} chains), {proj_h * 2 / 3:.1f} h at 20. Main run seeds: "
         f"**{G4['seeds_for_main']}**.", "",
         "## Customers a day, days 1–10, no inspectors", "",
         "| Stall type | Stall-seeds | Mean | Share ≥ 1 | Lowest |", "|---|---|---|---|---|",
         *[f"| {t} | {v['stalls']} | {v['mean']:.2f} | {v['share_ge1']:.0%} | {v['min']:.2f} |" for t, v in by_type.items()],
         "", "## G3 detail: per day, mean over 5 seeds × 30 days, 2 patrolling inspectors", "",
         "| | Choice-set | Walk |", "|---|---|---|",
         *[f"| {lab} | {c[k]:.1f} | {w[k]:.1f} |" for k, lab in (
             ("catches", "catches"), ("false_msgs", "false-claim messages"),
             ("false_in_earshot", "… with an inspector in earshot"),
             ("false_impr_to_inspectors", "false-claim impressions received by inspectors"),
             ("false_impr", "false-claim impressions (all)"), ("purchases", "purchases"),
             ("deceptive_units", "units sold by deceptive stalls"))],
         f"| catches per false claim in earshot | {c['catches_per_claim_in_earshot']:.3f} | "
         f"{w['catches_per_claim_in_earshot']:.3f} |", "",
         "## Notes", "", "NOTES_PLACEHOLDER", ""]
    open("runs/pilot_verification.md", "w", encoding="utf-8").write("\n".join(L))
    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
