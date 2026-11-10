"""Pilot gate for the liability run (spec 2026-11-10), on throwaway seeds 910-914 (G1 also checks seed 200
of the committed verification Stage B against its CSV).

G1 defaults reproduce the 0.14.0 Stage B cell at tourist share 1.0: the liability script's collectible
   condition at detect_scale 1.0 (col|t100|ds1.0, which writes out detect_scale 1.0 and lag 0) gives,
   chain by chain, the same 30-day totals of the 3 sampled stalls, catches and units per day as
   analysis/verification.py's B|t100 at engine 0.14.0 (commit 445c654, run in a worktree), on seeds
   910-914 (80 chains each); and seed 200 reproduces the committed runs/verification_B.csv rows.
G2 with lag 3 and an exit benchmark (jp|t100|ds1.0, seed 910), uncollectible fines > 0 in some chain.
G3 time one condition per liability arm at full size on 2 seeds (t40|ds0.1, seeds 910-911, run alone),
   project the main run's total; if over 10 hours, drop detect_scale 0.3 (and say so).

    .venv/bin/python -m analysis.pilot_liability     # writes runs/pilot_liability.md and .json
"""
from __future__ import annotations

import csv
import json
import os
import platform
import subprocess
import sys
import time
from types import SimpleNamespace

import numpy as np

import analysis.liability as L
from analysis.liability import _lower_priority
from analysis.counterfeit import _git, _load
from analysis.capture import memory_state
from engine import ENGINE_VERSION

WT = ".certify_tmp/v0140"
OLD_COMMIT = "445c654"
G1_SEEDS = [910, 911, 912, 913, 914]
G3_SEEDS = [910, 911]
G3_CONDS = ["col|t40|ds0.1", "jp|t40|ds0.1"]
LIMIT_H = 10.0
OLD_JOB = r"""
import json, sys
from concurrent.futures import ProcessPoolExecutor
import analysis.verification as V
seeds = json.loads(sys.argv[1])
samples = {sd: V.sample_stalls(sd) for sd in seeds}
jobs = V.jobs_for(["B|t100"], seeds, samples)

if __name__ == "__main__":
    import os
    try:
        os.nice(19)
    except OSError:
        pass
    out = []
    with ProcessPoolExecutor(4) as ex:
        for r in ex.map(V._job, jobs):
            out.append({"key": f"{r['seed']}|{r['stall']}|{r['b']}", "totals": r["totals"],
                        "catches": [d["catches"] for d in r["days"]], "units": [d["units"] for d in r["days"]]})
    json.dump({"samples": samples, "chains": out}, open(sys.argv[2], "w"))
"""


def _args():
    return SimpleNamespace(workers=4, min_swap_mb=512, min_free_pct=15)


def _log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def _sig(r):
    return {"totals": r["totals"], "catches": [d["catches"] for d in r["days"]], "units": [d["units"] for d in r["days"]]}


def g1(tmp: str) -> dict:
    # (a) seeds 910-914 against engine 0.14.0 in a worktree
    if not os.path.isdir(WT):
        subprocess.run(["git", "worktree", "add", "-f", "--detach", WT, OLD_COMMIT], check=True)
    head = subprocess.run(["git", "-C", WT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert head == OLD_COMMIT, head
    oldp = os.path.abspath(os.path.join(tmp, "g1_old.json"))   # the 0.14.0 job runs in the worktree
    t0 = time.time()
    subprocess.run([sys.executable, "-c", OLD_JOB, json.dumps(G1_SEEDS), oldp], cwd=WT,
                   env={**os.environ, "PYTHONPATH": "."}, check=True)
    t_old = time.time() - t0
    old = json.load(open(oldp))
    samples = {sd: L.sample_stalls(sd) for sd in G1_SEEDS}
    assert {str(k): v for k, v in samples.items()} == old["samples"], "sampled stalls differ"
    t0 = time.time()
    runs, _ = L.run_chains(_args(), L.jobs_for(["col|t100|ds1.0"], G1_SEEDS, samples), None, _log)
    t_new = time.time() - t0
    new = {f"{r['seed']}|{r['stall']}|{r['b']}": _sig(r) for r in runs}
    oldc = {c["key"]: {k: c[k] for k in ("totals", "catches", "units")} for c in old["chains"]}
    diff = sorted(k for k in oldc if new.get(k) != oldc[k])
    a = {"chains": len(oldc), "matched": len(oldc) - len(diff), "differ": diff[:10], "old_wall_s": t_old,
         "new_wall_s": t_new, "guard": {k: sum(r["guard"][k] for r in runs) for k in ("stuck_buyers", "parked", "idle_choosers")},
         "passed": not diff and set(new) == set(oldc)}
    # (b) seed 200 against the committed Stage B CSV
    rows = [r for r in csv.DictReader(open("runs/verification_B.csv")) if r["condition"] == "B|t100" and r["seed"] == "200"]
    s200 = {200: L.sample_stalls(200)}
    assert sorted(s200[200]) == sorted(r["stall"] for r in rows)
    runs, _ = L.run_chains(_args(), L.jobs_for(["col|t100|ds1.0"], [200], s200), None, _log)
    G = L.gains(runs, s200)["col|t100|ds1.0"][200]
    bad = []
    for r in rows:
        g = G[r["stall"]]
        want = {"never": int(r["never_total_cents"]), **{str(b): int(r[f"total_day{b}_cents"]) for b in L.COL_CANDS}}
        got = {"never": g["never"], **{str(b): g["totals"][str(b)] for b in L.COL_CANDS}}
        if want != got or int(r["gain_unfloored_cents"]) != g["gain_unfloored"]:
            bad.append({"stall": r["stall"], "want": want, "got": got})
    b = {"stalls": len(rows), "chains": len(runs), "mismatches": bad, "passed": not bad}
    return {"seeds_910_914_vs_0140": a, "seed_200_vs_csv": b, "passed": a["passed"] and b["passed"]}


def g2() -> dict:
    s = {910: L.sample_stalls(910)}
    runs, _ = L.run_chains(_args(), L.jobs_for(["jp|t100|ds1.0"], [910], s), None, _log)
    per = [{"key": r["key"], "tested_uncollectible_cents": r["fines"][r["stall"]]["uncollectible_cents"],
            "tested_charged_cents": r["fines"][r["stall"]]["charged_cents"],
            "market_uncollectible_cents": r["market_fines"]["fines_uncollectible_cents"],
            "market_outstanding_cents": r["market_fines"]["fines_outstanding_cents"], "exited": r["exited"]}
           for r in runs if r["stall"]]
    n = sum(p["market_uncollectible_cents"] > 0 for p in per)
    return {"chains": len(runs), "bust_chains": len(per), "chains_with_uncollectible": n,
            "tested_charged_cents_total": sum(p["tested_charged_cents"] for p in per),
            "tested_uncollectible_cents_total": sum(p["tested_uncollectible_cents"] for p in per),
            "never_outstanding_cents": [r["market_fines"]["fines_outstanding_cents"] for r in runs if not r["stall"]],
            "guard": {k: sum(r["guard"][k] for r in runs) for k in ("stuck_buyers", "parked", "idle_choosers")},
            "per_chain": per, "passed": n > 0}


def g3() -> dict:
    out = {}
    for cond in G3_CONDS:
        s = {sd: L.sample_stalls(sd) for sd in G3_SEEDS}
        load0, t0 = _load(), time.time()
        runs, pauses = L.run_chains(_args(), L.jobs_for([cond], G3_SEEDS, s), None, _log)
        wall = time.time() - t0
        out[cond] = {"chains": len(runs), "wall_s": wall, "per_chain_s": wall / len(runs), "pauses": pauses,
                     "load_start": load0, "load_end": _load(),
                     "guard": {k: sum(r["guard"][k] for r in runs) for k in ("stuck_buyers", "parked", "idle_choosers")}}
    n = {"col": 20 * 8 * (1 + 3 * len(L.COL_CANDS)), "jp": 20 * 8 * (1 + 3 * len(L.JP_CANDS))}
    proj = sum(out[c]["per_chain_s"] * n[c.split("|")[0]] for c in G3_CONDS) / 3600
    n3 = {k: v * 3 // 4 for k, v in n.items()}
    proj3 = sum(out[c]["per_chain_s"] * n3[c.split("|")[0]] for c in G3_CONDS) / 3600
    return {"timed": out, "chains_full": n, "projected_h_full": proj, "chains_without_0.3": n3,
            "projected_h_without_0.3": proj3, "limit_h": LIMIT_H, "drop_0.3": proj > LIMIT_H,
            "levels": [0.0, 0.1, 1.0] if proj > LIMIT_H else L.DS_ALL}


def rewrite() -> int:
    """Regenerate runs/pilot_liability.md from runs/pilot_liability.json (no runs)."""
    res = json.load(open("runs/pilot_liability.json", encoding="utf-8"))
    with open("runs/pilot_liability.md", "w", encoding="utf-8") as f:
        f.write(report(res))
    return 0


def main() -> int:
    _lower_priority()
    tmp = os.path.join(".certify_tmp", "pilot_liability")
    os.makedirs(tmp, exist_ok=True)
    t0 = time.time()
    meta = {"engine": ENGINE_VERSION, "git": _git(), "python": platform.python_version(), "numpy": np.__version__,
            "platform": platform.platform(), "load_start": _load(), "mem_start": memory_state(),
            "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    res = {"meta": meta}
    _log("G1"); res["G1"] = g1(tmp)
    _log(f"G1 passed: {res['G1']['passed']}")
    _log("G2"); res["G2"] = g2()
    _log(f"G2 passed: {res['G2']['passed']}")
    _log("G3"); res["G3"] = g3()
    _log(f"G3 projection {res['G3']['projected_h_full']:.2f} h; drop 0.3: {res['G3']['drop_0.3']}")
    meta.update(wall_min=(time.time() - t0) / 60, load_end=_load(), mem_end=memory_state(),
                ended=time.strftime("%Y-%m-%d %H:%M:%S"))
    with open("runs/pilot_liability.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    with open("runs/pilot_liability.md", "w", encoding="utf-8") as f:
        f.write(report(res))
    print(report(res))
    return 0 if res["G1"]["passed"] and res["G2"]["passed"] else 1


def report(res) -> str:
    m, g1r, g2r, g3r = res["meta"], res["G1"], res["G2"], res["G3"]
    a, b = g1r["seeds_910_914_vs_0140"], g1r["seed_200_vs_csv"]
    ok = lambda x: "**pass**" if x else "**FAIL**"
    L_ = ["# Pilot gate: enforcement intensity and limited liability", "",
          f"Engine {m['engine']} at {m['git']['commit'][:7]} (uncommitted: {m['git']['status_porcelain'] or 'none'}); "
          f"Python {m['python']}, numpy {m['numpy']}, {m['platform']}. Throwaway seeds 910–914 (G1 also seed 200 of the "
          f"committed Stage B). 4 workers at nice 19. Started {m['started']}, ended {m['ended']} "
          f"({m['wall_min']:.0f} min); load {m['load_start']} at start, {m['load_end']} at end.", "",
          f"## G1 defaults reproduce the 0.14.0 Stage B cell (tourist share 1.0): {ok(g1r['passed'])}", "",
          f"- Seeds 910–914: the liability script's `col|t100|ds1.0` (detect_scale 1.0 and lag 0 written out) against "
          f"`analysis/verification.py` B|t100 at engine 0.14.0 ({OLD_COMMIT}, in a worktree): {a['matched']} of "
          f"{a['chains']} chains identical in the 30-day totals of the 3 sampled stalls, catches per day and units per "
          f"day of each sampled stall.{(' Differ: ' + ', '.join(a['differ'])) if a['differ'] else ''}",
          f"- Seed 200: never and the five bust-out totals of each of the {b['stalls']} sampled stalls, and the gain, "
          f"equal the committed `runs/verification_B.csv` rows to the cent"
          + ("." if b["passed"] else f": {len(b['mismatches'])} mismatches."),
          f"- Guard over the 80 chains at 0.15.0: stuck {a['guard']['stuck_buyers']}, parked {a['guard']['parked']}, "
          f"idle choosers {a['guard']['idle_choosers']}.", "",
          f"## G2 uncollectible fines with lag 3 and exit: {ok(g2r['passed'])}", "",
          f"`jp|t100|ds1.0`, seed 910: {g2r['chains_with_uncollectible']} of {g2r['bust_chains']} bust-and-exit chains "
          f"have uncollectible fines. The tested stalls' fines over those chains: ${g2r['tested_charged_cents_total'] / 100:,.2f} "
          f"charged, ${g2r['tested_uncollectible_cents_total'] / 100:,.2f} uncollectible. The never chain has "
          f"${g2r['never_outstanding_cents'][0] / 100:,.2f} outstanding at close (deceptive stalls caught on days 28–30). "
          f"Guard: stuck {g2r['guard']['stuck_buyers']}, parked {g2r['guard']['parked']}.", "",
          "## G3 timing and projection", "",
          "| Condition | Chains | Wall (s) | Per chain (s) | Load at start | Memory-guard pauses |", "|---|---:|---:|---:|---|---:|"]
    for c, t in g3r["timed"].items():
        L_.append(f"| `{c.replace('|', chr(92) + '|')}` | {t['chains']} | {t['wall_s']:.0f} | {t['per_chain_s']:.2f} | {t['load_start']} | {t['pauses']} |")
    L_ += ["", f"Main run: {g3r['chains_full']['col']:,} collectible and {g3r['chains_full']['jp']:,} judgment-proof chains "
           f"(20 seeds × 8 conditions per arm). Projected wall clock {g3r['projected_h_full']:.1f} h on 4 workers "
           f"({g3r['projected_h_without_0.3']:.1f} h without detect_scale 0.3). Limit {LIMIT_H:g} h: "
           + ("**over, so detect_scale 0.3 is dropped** (levels 0, 0.1, 1.0)." if g3r["drop_0.3"]
              else "under, so all four detect_scale levels run (0, 0.1, 0.3, 1.0).")
           + " The timed conditions are t40 at detect_scale 0.1 (choice made before timing: three of the four levels "
           "catch rarely, and t40 has the most buyer inspections); G1's 80 chains at detect_scale 1.0 took "
           f"{a['new_wall_s'] / a['chains']:.2f} s per chain.", "",
           "## Notes", "",
           "- The pilot was started three times. The first start failed at once (`os.nice` raised EPERM under `nohup`; "
           "both scripts now tolerate it, and the launch command sets nice 19). The second was stopped after 30 s, before "
           "any chain finished, because the 0.14.0 job (run inside the worktree) had a relative output path; its "
           "orphaned pool workers were killed before the third start. Only the third run's results are reported.",
           "- Load averages include the pilot's own 4 workers (G3 started straight after G2); no other jobs of this "
           "project were running.",
           "- Consequence of dropping 0.3 (prespecified rule): PL1's per-seed slope is fitted over detect_scale "
           "0, 0.1 and 1.0, and the crossing points are interpolated between those levels.", ""]
    return "\n".join(L_)


if __name__ == "__main__":
    raise SystemExit(rewrite() if sys.argv[1:] == ["--rewrite"] else main())
