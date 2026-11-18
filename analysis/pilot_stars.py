"""Pilot gate for the displayed-ratings runs (engine 0.20.0): Run A (analysis/brand_equity_stars.py) and Run B
(analysis/stars_sensitivity.py). Seeds 900-902. Writes runs/pilot_stars/pilot_gates.json; the gate report is
runs/pilot_stars.md.

  G1: both pipelines run end to end on seeds 900-902 and their summaries render (B pairs stars against exact chains it
      runs itself, since the pilot seeds have no saved chains).
  G2: the defaults reproduce 0.19.0 chains bit for bit: every brand_equity_speed chain of seeds 330 and 331 (both
      verifications, all four levels, never / R / W_g) rerun at engine 0.20.0 equals its record in
      runs/brand_equity_speed_cache.jsonl by full-outcome digest, daily trade digests and ledgers. Also, for Run B's
      pairing: 4 saved exact chains per study rerun at 0.20.0 equal their cache records (stars_sensitivity --repro).
  G3: timing, 4 workers, nice 19: A and B together <= 7 h, projected from the pilot's throughput. If over: drop the
      step 0.1 cells first, then cut B to 5 seeds per study, then stop and report.
  G4: under stars, no white label and owner with equal displayed rating ever differ in posted price (every pilot W_g
      chain, days 11-60).
  G5: stuck / parked / idle choosers / invalid actions 0 in every pilot chain (A, B and G2).

    PYTHONPATH=. .venv/bin/python -m analysis.pilot_stars --tests "..."
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import sys
import time
from types import SimpleNamespace

import analysis.brand_equity_speed as S
import analysis.brand_equity_stars as A
import analysis.chainrun as CR
import analysis.licensing as L
from analysis.counterfeit import _git, _load
from engine import ENGINE_VERSION

SEEDS = "900-902"
LIMIT_H = 7.0
OUT = "runs/pilot_stars"
MAIN_SEEDS = 20
G2_SEEDS = (330, 331)
G2_CACHE = "runs/brand_equity_speed_cache.jsonl"
B_FULL_SEEDS, B_CUT_SEEDS = 10, 5


def a_chains(sens: bool) -> int:
    samples = {sd: ["x", "y", "z"] for sd in range(MAIN_SEEDS)}
    return len(A.jobs_for(list(range(MAIN_SEEDS)), samples, sens)) + len(A.S.CHECK_RATES) * 2 * 3


def g2(a, log) -> dict:
    samples = {sd: L.sample_stalls(sd) for sd in G2_SEEDS}
    jobs = S.jobs_for(list(G2_SEEDS), samples, S.LEVELS)
    old = {}
    want = {S.key(j) for j in jobs}
    with open(G2_CACHE, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["key"] in want:
                old[r["key"]] = r
    t0 = time.time()
    runs, _ = CR.run_chains(a, jobs, os.path.join(OUT, "g2_cache.jsonl"), log, S.job, S.key)
    same = 0
    rows = []
    for r in runs:
        o = old.get(r["key"])
        ok = o is not None and all(r[k] == o[k] for k in ("digest", "dig_trade", "all", "win", "totals", "rating"))
        ok = ok and r.get("daily") == o.get("daily")
        same += ok
        if not ok:
            rows.append(r["key"])
    guard = {k: sum(r["guard"][k] for r in runs) for k in ("stuck_buyers", "idle_choosers", "parked", "fallbacks")}
    return {"pass": same == len(jobs) == len(old), "chains": len(jobs), "found": len(old), "identical": same,
            "differ": rows[:20], "guard": guard, "wall_s": time.time() - t0}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", default="")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--skip-g2", action="store_true")
    a = ap.parse_args(argv)
    os.makedirs(OUT, exist_ok=True)
    log = CR.file_logger(os.path.join(OUT, "pilot_run.log"))
    ns = SimpleNamespace(workers=a.workers, min_swap_mb=512, min_free_pct=15)
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "load_start": _load(), "start": time.strftime("%F %T"),
            "tests": a.tests}
    log(f"pilot stars: engine {ENGINE_VERSION}, commit {meta['git']['commit'][:7]}, load {meta['load_start']}")
    gates: dict = {"meta": meta}
    # G2 first: the defaults reproduce 0.19.0
    if not a.skip_g2:
        gates["G2"] = g2(ns, log)
        log(f"G2: {gates['G2']['identical']}/{gates['G2']['chains']} identical")
    gates["B_repro"] = b_repro(a)
    log(f"B reproduction check: {'pass' if gates['B_repro']['pass'] else 'FAIL'}")
    # G1 A
    t0 = time.time()
    rc_a = A.main(["--pilot", "--seeds", SEEDS, "--outdir", os.path.join(OUT, "A"), "--workers", str(a.workers),
                   "--tests", a.tests, "--gate", "Pilot run (seeds 900–902)."])
    wall_a = time.time() - t0
    with gzip.open(os.path.join(OUT, "A", "brand_equity_stars.json.gz"), "rt", encoding="utf-8") as f:
        ra = json.load(f)
    res_a = ra["results"]
    n_a = ra["meta"]["chains"]
    gates["A"] = {"exit": rc_a, "chains": n_a, "wall_s": wall_a, "s_per_chain": wall_a / n_a, "flags": res_a["flags"],
                  "summary": os.path.exists(os.path.join(OUT, "A", "brand_equity_stars_summary.md")),
                  "pred": {k: {x: v[x] for x in ("mean", "lo", "hi", "verdict")} for k, v in res_a["pred"].items()}}
    log(f"A: exit {rc_a}, {n_a} chains, {wall_a / n_a:.1f} s per chain")
    # G1 B
    t0 = time.time()
    cmd = [sys.executable, "-m", "analysis.stars_sensitivity", *B_PILOT_ARGS, "--workers", str(a.workers),
           "--outdir", os.path.join(OUT, "B"), "--tests", a.tests, "--gate", "Pilot run (seeds 900–902)."]
    rc_b = subprocess.run(cmd, env={**os.environ, "PYTHONPATH": "."}).returncode
    wall_b = time.time() - t0
    gates["B"] = {"exit": rc_b, "cmd": " ".join(cmd), "wall_s": wall_b, **b_pilot_stats(os.path.join(OUT, "B"))}
    log(f"B: exit {rc_b}, wall {wall_b / 3600:.2f} h")
    # G1
    gates["G1"] = {"pass": gates["A"]["summary"] and gates["B"]["summary"] and rc_a in (0, 2) and rc_b in (0, 2)}
    # G3: projection
    s_a = gates["A"]["s_per_chain"]
    proj = {}
    for sens in (True, False):
        for nb in (B_FULL_SEEDS, B_CUT_SEEDS):
            ha = a_chains(sens) * s_a / 3600
            hb = b_hours(gates["B"], nb)
            proj[f"sens={sens}|B={nb}"] = {"A_h": ha, "B_h": hb, "total_h": ha + hb}
    choice = next((k for k in ("sens=True|B=10", "sens=False|B=10", "sens=False|B=5")
                   if proj[k]["total_h"] <= LIMIT_H), None)
    gates["G3"] = {"pass": choice is not None, "limit_h": LIMIT_H, "projections": proj, "choice": choice}
    # G4
    g4 = res_a["g4"]
    g4s = res_a.get("g4_sens", {"same": 0, "miss": 0})
    gates["G4"] = {"pass": g4["miss"] == 0 and g4s["miss"] == 0 and g4["same"] > 0, "step_0.02": g4, "step_0.1": g4s}
    # G5
    ga = res_a["main"]["guard"]
    bad_a = {k: sum(g[k] for g in ga.values()) for k in ("stuck_buyers", "parked", "idle_choosers", "fallbacks")}
    if "sens" in res_a:
        for k in bad_a:
            bad_a[k] += sum(g[k] for g in res_a["sens"]["guard"].values())
    bad_g2 = gates.get("G2", {}).get("guard", {})
    bad_b = gates["B"].get("guard", {})
    tot = sum(bad_a.values()) + sum(bad_g2.values()) + sum(v for v in bad_b.values() if isinstance(v, (int, float)))
    gates["G5"] = {"pass": tot == 0, "A": bad_a, "G2": bad_g2, "B": bad_b}
    meta.update(end=time.strftime("%F %T"), load_end=_load())
    with open(os.path.join(OUT, "pilot_gates.json"), "w", encoding="utf-8") as f:
        json.dump(gates, f, indent=1, default=str)
    ok = all(gates[g]["pass"] for g in ("G1", "G3", "G4", "G5", "B_repro")) and gates.get("G2", {"pass": True})["pass"]
    log(f"gates: " + ", ".join(f"{g} {'pass' if gates[g]['pass'] else 'FAIL'}" for g in ("G1", "G2", "G3", "G4", "G5")
                               if g in gates) + f"; G3 choice {choice}")
    return 0 if ok else 2


# ------------------------------------------------------------------ Run B hooks (analysis/stars_sensitivity.py)

B_PILOT_ARGS: list[str] = ["--seeds", "900-902", "--exact", "run"]
B_REPRO_N = 4
B_REPRO_FILE = os.path.join(OUT, "stars_sensitivity_repro.json")


def b_repro(a) -> dict:
    """Pairing check for Run B: B_REPRO_N saved exact chains per study rerun at engine 0.20.0 with defaults must equal
    their cache records. Written to B_REPRO_FILE, which the full run reads (--repro-file)."""
    cmd = [sys.executable, "-m", "analysis.stars_sensitivity", "--repro", str(B_REPRO_N), "--repro-file", B_REPRO_FILE,
           "--outdir", os.path.join(OUT, "B_repro"), "--workers", str(a.workers)]
    rc = subprocess.run(cmd, env={**os.environ, "PYTHONPATH": "."}).returncode
    with open(B_REPRO_FILE, encoding="utf-8") as f:
        rep = json.load(f)
    return {"pass": rc == 0 and bool(rep.get("pass")), "exit": rc, "cmd": " ".join(cmd), "file": B_REPRO_FILE,
            "detail": rep}


def b_pilot_stats(outdir: str) -> dict:
    p = os.path.join(outdir, "stars_sensitivity_results.json")
    with open(p, encoding="utf-8") as f:
        r = json.load(f)
    g = r["guard"]
    sec = {}
    for k, v in g.items():
        st, arm = k.split(" · ")
        if arm == "stars" and v["chains"]:
            sec[st] = v["secs"] / v["chains"]
    bad = {k: sum(v[k] for v in g.values()) for k in ("stuck_buyers", "parked", "idle_choosers", "fallbacks",
                                                       "arm_bad")}
    return {"summary": os.path.exists(os.path.join(outdir, "stars_sensitivity_summary.md")), "flags": r["flags"],
            "chains": r["meta"]["chains_run"], "s_per_stars_chain": sec, "guard": bad}


def b_hours(b: dict, seeds_per_study: int, workers: int = 4) -> float:
    """Full Run B (stars arm only; exact chains are saved): per study, the pilot's mean seconds per stars chain (one
    worker's wall clock) x chains per seed x seeds, over `workers` workers."""
    import analysis.stars_sensitivity as SS
    tot = 0.0
    for st, sec in b["s_per_stars_chain"].items():
        n = SS.PER_SEED["bustout_saved" if st == "bustout" else st] * seeds_per_study
        tot += n * sec / workers
    return tot / 3600


if __name__ == "__main__":
    raise SystemExit(main())
