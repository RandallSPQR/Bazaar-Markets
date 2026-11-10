"""Stuck-buyer certification of earlier runs (spec 2026-11-09; observer only, no behaviour change).

For each committed run, check out the commit it was run at (its engine version) in a temporary git
worktree, run 3 seeds x every condition with that version's own job function, and count at the end of
every market day, with an observer patched onto BazaarEngine.run (it reads state after the day and
changes nothing):
  stuck_buyers   in the market at close, within reach of the open stall it chose (p.target), units
                 still needed, budget for one unit there (the 0.14.0 guard; trapped-buyer bug)
  parked         in the market at close, within reach of the stall it chose, units still needed,
                 whatever the stall's state or price (parked-buyer bug; includes stuck_buyers)
  idle_choosers  searching buyer in the market at close in phase "choose" (k stalls seen or at its
                 route end), units still needed, an open affordable stall of its category (and set)
                 in reach (the 0.14.0 guard's second count)
Engines before 0.10.0 have no buyer search (no chosen stall, no phases): all three are 0 by
construction there, and the observer confirms it.

    .venv/bin/python -m analysis.certify_stuck --out runs/certification_stuck.json      # all runs
    (internally: python certify_stuck.py --worker RUN OUT, run inside the worktree)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

RUNS = {   # name: (commit the run was made at, module, seeds: the first 3 the run used)
    "placement_sweep": ("3de5fc8", "placement_sweep", [0, 1, 2]),
    "visibility_adaptivity": ("c7cf7fe", "visibility_adaptivity", [0, 1, 2]),
    "recognition_sweep": ("463af5d", "recognition_sweep", [0, 1, 2]),
    "grid_refinement": ("e514cea", "grid_refinement", [0, 1, 2]),
    "search_counterfeit": ("14f341c", "search_counterfeit", [2, 3, 4]),
    "dilemma_boundary": ("e5d7818", "dilemma_boundary", [32, 33, 34]),
    "capture_A": ("6b286fd", "capture", [52, 53, 54]),
    "capture_B": ("b833b2f", "capture", [52, 53, 54]),
    "verification_A": ("c8c0407", "verification", [200, 201, 202]),
}
# --here (2026-11-09, PI decision 2): the same observer on the current working tree, to check whether
# the parked-buyer behaviour survives engine 0.14.0. The three flagged runs, the pilot recheck, and
# the Stage B design (3 seeds) before the Stage B rerun.
HERE_RUNS = {
    "search_counterfeit": ("search_counterfeit", [2, 3, 4]),
    "dilemma_boundary": ("dilemma_boundary", [32, 33, 34]),
    "capture_B": ("capture", [52]),
    "pilot_recheck": ("pilot_choice_set", [900, 901, 902, 903, 904]),
    "verification_B": ("verification", [200, 201, 202]),
}

_COUNTS: list = []


def _observe():
    """Patch BazaarEngine.run to record the guard counts after each market day."""
    from engine.bazaar import BazaarEngine
    orig = BazaarEngine.run

    def run(self, *a, **k):
        out = orig(self, *a, **k)
        r = self.cfg.market.interact_range
        is_open = (lambda st: self.is_open(st)) if hasattr(self, "is_open") else (lambda st: self.t >= st.closed_until)
        buyers = [p for p in self.people if p.kind == "buyer"]
        stuck = parked = idle = 0
        for p in buyers:
            if not p.active or p.done or p.units >= p.task["units"]:
                continue
            left = p.task["budget_cents"] - p.paid_cents - p.inspect_spent_cents
            tgt = getattr(p, "target", None)
            if tgt is not None:
                st = next(s for s in self.stalls if s.sid == tgt)
                if math.dist(p.pos, st.pos) <= r:
                    parked += 1
                    if is_open(st) and st.price_cents <= left:
                        stuck += 1
            k = getattr(p, "search_k", 1)
            if k > 1:
                choose = getattr(p, "choosing", False) or len(p.seen) >= k or p.step >= len(p.route) - 1
                cons = getattr(p, "consider", None)
                if choose and any(st.category == p.task["category"] and (cons is None or st.sid in cons) and is_open(st)
                                  and st.price_cents <= left and math.dist(p.pos, st.pos) <= r for st in self.stalls):
                    idle += 1
        _COUNTS.append({"buyers": len(buyers), "searching": sum(getattr(p, "search_k", 1) > 1 for p in buyers),
                        "stuck_buyers": stuck, "parked": parked, "idle_choosers": idle,
                        "day": getattr(self, "day", 1)})
        return out

    BazaarEngine.run = run


def _init():
    cur = os.nice(0)
    if cur < 19:
        os.nice(19 - cur)
    _observe()


def _call(args):
    fn_name, job = args
    import importlib
    mod_name, fn = fn_name.rsplit(".", 1)
    f = getattr(importlib.import_module(mod_name), fn)
    _COUNTS.clear()
    f(job)
    days = list(_COUNTS)
    return {"job": repr(job)[:200], "days": len(days), "buyer_days": sum(d["buyers"] for d in days),
            "searching_buyer_days": sum(d["searching"] for d in days),
            **{k: sum(d[k] for d in days) for k in ("stuck_buyers", "parked", "idle_choosers")},
            "max_stuck_day": max((d["stuck_buyers"] for d in days), default=0),
            "max_parked_day": max((d["parked"] for d in days), default=0)}


def worker_jobs(name: str, seeds: list[int]) -> list[tuple]:
    import importlib
    modname = RUNS[name][1] if name in RUNS else HERE_RUNS[name][0]
    M = importlib.import_module(f"analysis.{modname}")
    fn = f"analysis.{modname}._job"
    if name == "placement_sweep":
        return [(fn, (arm, path, c, n, pl, s)) for arm, path in M.ARMS.items() for c, n, pl in M.CONDITIONS for s in seeds]
    if name == "visibility_adaptivity":
        return [(fn, (pk, c, n, pl, u, s)) for pk in M.POLICIES for c, n, pl, u in M.CONDITIONS for s in seeds]
    if name in ("recognition_sweep", "grid_refinement"):
        return [(fn, (c, s)) for c in M.CONDITIONS for s in seeds]
    if name == "search_counterfeit":
        with open("runs/search_calibration.json", encoding="utf-8") as f:
            k = json.load(f)["chosen_k"]
        conds = M.conditions(k)[3]
        return [(fn, (*c, s)) for s in seeds for c in conds] + \
               [(f"analysis.{modname}._rob_job", (pl, k, s)) for s in seeds for pl in ("posts", "patrolling")]
    if name == "dilemma_boundary":
        return [(fn, (g, n, s)) for s in seeds for g in M.POLICIES for n in M.COUNTS]
    if name in ("capture_A", "capture_B"):
        samples = {s: M.sample_stalls(s) for s in seeds}
        return [(fn, j) for j in M.jobs_for(name[-1], seeds, samples)]
    if name in ("verification_A", "verification_B"):
        samples = {s: M.sample_stalls(s) for s in seeds}
        return [(fn, j) for j in M.jobs_for(M.CONDS[name[-1]], seeds, samples)]
    if name == "pilot_recheck":
        return [(fn, ("p2", 150, s, pl)) for s in seeds for pl in ("posts", "patrolling")] + \
               [(fn, ("p3", 150, s, ro)) for s in seeds for ro in ("fresh", "counterfeit")]
    raise ValueError(name)


def worker(name: str, out: str, workers: int, here: bool = False) -> None:
    sys.path.insert(0, os.getcwd())
    from engine import ENGINE_VERSION
    seeds = HERE_RUNS[name][1] if here else RUNS[name][2]
    jobs = worker_jobs(name, seeds)
    t0 = time.time()
    with ProcessPoolExecutor(workers, initializer=_init) as ex:
        res = list(ex.map(_call, jobs))
    tot = {k: sum(r[k] for r in res) for k in ("buyer_days", "searching_buyer_days", "stuck_buyers", "parked",
                                                 "idle_choosers")}
    with open(out, "w", encoding="utf-8") as f:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() \
            if here else RUNS[name][0]
        json.dump({"run": name, "commit": commit, "engine_version": ENGINE_VERSION, "seeds": seeds,
                   "jobs": len(jobs), "wall_s": round(time.time() - t0, 1), "totals": tot,
                   "jobs_with_stuck": sum(r["stuck_buyers"] > 0 for r in res),
                   "jobs_with_parked": sum(r["parked"] > 0 for r in res),
                   "max_stuck_day": max(r["max_stuck_day"] for r in res),
                   "max_parked_day": max(r["max_parked_day"] for r in res), "per_job": res}, f)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", nargs=2, metavar=("RUN", "OUT"))
    ap.add_argument("--runs", default=",".join(RUNS))
    ap.add_argument("--out", default="runs/certification_stuck.json")
    ap.add_argument("--scratch", required=False)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--here", action="store_true", help="observe HERE_RUNS on the current working tree")
    a = ap.parse_args(argv)
    if a.worker:
        worker(a.worker[0], a.worker[1], a.workers)
        return 0
    if a.here:
        _init()   # the parent too: nice 19
        results = {}
        if os.path.exists(a.out):
            with open(a.out, encoding="utf-8") as f:
                results = json.load(f).get("runs", {})
        names = a.runs.split(",") if a.runs != ",".join(RUNS) else list(HERE_RUNS)
        for name in names:
            if name in results:
                continue
            part = a.out + f".{name}.part"
            t0 = time.time()
            print(time.strftime("%H:%M:%S"), "start", name, flush=True)
            worker(name, part, a.workers, here=True)
            with open(part, encoding="utf-8") as f:
                results[name] = json.load(f)
            os.remove(part)
            r = results[name]
            print(time.strftime("%H:%M:%S"), "done", name, r["engine_version"], r["jobs"], "jobs", r["totals"],
                  f"{time.time() - t0:.0f} s", flush=True)
            with open(a.out, "w", encoding="utf-8") as f:
                json.dump({"meta": {"python": platform.python_version(), "platform": platform.platform(),
                                    "script": "analysis/certify_stuck.py --here"}, "runs": results}, f, indent=1)
        return 0
    repo = os.getcwd()
    scratch = a.scratch or os.path.join(repo, ".certify_tmp")
    os.makedirs(scratch, exist_ok=True)
    py = os.path.join(repo, ".venv", "bin", "python")
    results = {}
    if os.path.exists(a.out):
        with open(a.out, encoding="utf-8") as f:
            results = json.load(f).get("runs", {})
    for name in a.runs.split(","):
        if name in results:
            continue
        commit = RUNS[name][0]
        wt = os.path.join(scratch, f"wt_{name}")
        if os.path.exists(wt):
            subprocess.run(["git", "worktree", "remove", "--force", wt], check=False)
        subprocess.run(["git", "worktree", "add", "-q", "--detach", wt, commit], check=True)
        try:
            shutil.copy(os.path.abspath(__file__), os.path.join(wt, "certify_stuck_worker.py"))
            part = os.path.join(scratch, f"{name}.json")
            t0 = time.time()
            print(time.strftime("%H:%M:%S"), "start", name, commit, flush=True)
            subprocess.run([py, "certify_stuck_worker.py", "--worker", name, part, "--workers", str(a.workers)],
                           cwd=wt, env={**os.environ, "PYTHONPATH": wt}, check=True)
            with open(part, encoding="utf-8") as f:
                results[name] = json.load(f)
            r = results[name]
            print(time.strftime("%H:%M:%S"), "done", name, r["engine_version"], r["jobs"], "jobs",
                  r["totals"], f"{time.time() - t0:.0f} s", flush=True)
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", wt], check=False)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump({"meta": {"python": platform.python_version(), "platform": platform.platform(),
                                "script": "analysis/certify_stuck.py"}, "runs": results}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
