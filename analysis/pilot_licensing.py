"""Pilot gate for the licensing run (spec "Part 2: licensing", 2026-11-11). Throwaway seeds 915-919.

G1  defaults reproduce engine 0.15.0: full 30-day chains (never, t40 and t100 at detect_scale 0 and 1, and
    one day-30 bust-out at t100, detect_scale 1) on seeds 915-916, run by engine 0.15.0 (worktree at 5b60720)
    and by 0.16.0 with the licensing defaults: outcome and log body identical. (The 94 reference cells are in
    tests/test_licensing.py.)
G2  royalty and liability accounting on full 30-day chains (seed 915, t100 and t40, detect_scale 1, 6
    licensees from day 10): royalties = units x round(0.15 x price) every day; royalties paid = received;
    owner_liable moves exactly the fines from catches at licensees to the owner, changes no trade, and the
    owner's total falls by exactly those fines; reviews land on the brand (the cheap brand's rating ends below
    never's); contract licensees make no false claim and are never caught; guard 0 everywhere.
G3  time one licensing condition at full size on 2 seeds (python -m analysis.licensing --timing ... --seeds
    916-917) and project the main run; over 8 h -> a trimmed option (drop b = 10, or 15 seeds).

    .venv/bin/python -m analysis.pilot_licensing --g1 --g2
    .venv/bin/python -m analysis.pilot_licensing --report --timing-json <file> --pipeline-json <file>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

import analysis.licensing as X
from analysis.counterfeit import _git, _load
from engine import ENGINE_VERSION, bazaar, benchmark
from engine.config import load
from engine.jsonlog import JsonlLog, dumps

OUT_JSON = "runs/pilot_licensing.json"
OUT_MD = "runs/pilot_licensing.md"
OLD_TREE = ".certify_tmp/v0150"
G1_SEEDS = [915, 916]

OLD_JOB = r'''
import hashlib, json, sys
sys.path.insert(0, ".")
try:
    import os; os.nice(19 - os.nice(0))
except OSError:
    pass
from engine import ENGINE_VERSION, bazaar, benchmark
from engine.config import load
from engine.jsonlog import JsonlLog, dumps
from analysis.verification import overrides as vov
VER = {"t40": "B|t40|l1", "t100": "B|t100"}
out = {}
for key, t, ds, seed, stall, b in json.loads(sys.argv[1]):
    c = load(None, [*vov(VER[t]), f"inspectors.detect_scale={ds!r}", "pricing.penalty_lag_days=0", f"seed={seed}"],
             mode="bazaar")
    c = benchmark.bust_config(c, stall, b if b else benchmark.NEVER)
    log = JsonlLog(keep=True)
    o = bazaar.run(c, log=log)
    out[key] = {"engine": ENGINE_VERSION, "outcome_sha": hashlib.sha256(dumps(o).encode()).hexdigest(),
                "log_body_sha": hashlib.sha256("\n".join(log.lines[1:]).encode()).hexdigest(),
                "lines": len(log.lines), "total": benchmark.stall_total(o, stall) if stall else None}
json.dump(out, open(sys.argv[2], "w"))
'''


def g1_cases() -> list:
    cases = []
    for seed in G1_SEEDS:
        for t in X.VER:
            for ds in (0.0, 1.0):
                cases.append([f"never|{t}|ds{ds!r}|{seed}", t, ds, seed, None, None])
    s = X.sample_stalls(915)[0]
    cases.append([f"bust30|t100|ds1.0|915|{s}", "t100", 1.0, 915, s, 30])
    return cases


def _new_one(case) -> dict:
    key, t, ds, seed, stall, b = case
    c = X.config(t, ds, seed)                       # licensing at its defaults (no schedule)
    c = benchmark.bust_config(c, stall, b if b else benchmark.NEVER)
    log = JsonlLog(keep=True)
    o = bazaar.run(c, log=log)
    return {"engine": ENGINE_VERSION, "outcome_sha": hashlib.sha256(dumps(o).encode()).hexdigest(),
            "log_body_sha": hashlib.sha256("\n".join(log.lines[1:]).encode()).hexdigest(),
            "lines": len(log.lines), "total": benchmark.stall_total(o, stall) if stall else None}


def g1() -> dict:
    cases = g1_cases()
    tmp = os.path.abspath("runs/.pilot_licensing_old.json")
    t0 = time.time()
    old = subprocess.Popen([os.path.abspath(".venv/bin/python"), "-c", OLD_JOB, json.dumps(cases), tmp], cwd=OLD_TREE)
    new = {c[0]: _new_one(c) for c in cases}
    if old.wait() != 0:
        raise SystemExit("G1: the 0.15.0 job failed")
    with open(tmp, encoding="utf-8") as f:
        oldr = json.load(f)
    os.remove(tmp)
    rows = {}
    for c in cases:
        k = c[0]
        o, n = oldr[k], new[k]
        rows[k] = {"old_engine": o["engine"], "new_engine": n["engine"],
                   "identical": o["outcome_sha"] == n["outcome_sha"] and o["log_body_sha"] == n["log_body_sha"]
                   and o["lines"] == n["lines"], "lines": n["lines"], "total": n["total"]}
    git_old = subprocess.run(["git", "-C", OLD_TREE, "rev-parse", "--short", "HEAD"], capture_output=True,
                             text=True).stdout.strip()
    return {"cases": rows, "old_commit": git_old, "pass": all(r["identical"] for r in rows.values()),
            "wall_s": time.time() - t0}


class ClaimTap(JsonlLog):
    """False claims and catches at a set of stalls, from day `day` on, without keeping the log."""

    def __init__(self, stalls, day):
        super().__init__(None, keep=False)
        self.stalls, self.day0, self.day = set(stalls), day, 1
        self.false_msgs = self.catches = 0

    def emit(self, ev, **f):
        if ev == "day_start":
            self.day = f["day"]
        elif ev == "delta" and self.day >= self.day0:
            self.false_msgs += sum(1 for m in f["msgs"] if m["from"] in self.stalls and m["false"])
            self.catches += sum(1 for c in f["catches"] if c["stall"] in self.stalls)


def _lic_run(t, quality, liable, seed, owner, opt, tap=None):
    c = benchmark.licence_config(X.config(t, 1.0, seed, quality, liable), owner, opt)
    return bazaar.run(c, log=tap)


def g2() -> dict:
    seed, opt, b = 915, (6, 10), 10
    out = {}
    for t in X.VER:
        owner = X.sample_stalls(seed)[0]
        never = bazaar.run(benchmark.licence_config(X.config(t, 1.0, seed), None, benchmark.NEVER))
        free = _lic_run(t, "cheap", False, seed, owner, opt)
        liab = _lic_run(t, "cheap", True, seed, owner, opt)
        lic = free["days"][b - 1]["outcome"]["licensing"]["owners"][owner]["licensees"]
        tap = ClaimTap(lic, b)
        con = _lic_run(t, "contract", False, seed, owner, opt, tap)
        chk = {}
        roy_ok, paid_ok = True, True
        for d in free["days"][b - 1:]:
            L = d["outcome"]["licensing"]["owners"][owner]
            roy_ok &= L["royalties_cents"] == L["licensee_units"] * round(0.15 * d["prices"][owner])
            bt = d["outcome"]["seller_by_type"]
            paid_ok &= sum(v["royalty_paid_cents"] for v in bt.values()) == sum(v["royalty_received_cents"]
                                                                               for v in bt.values()) == L["royalties_cents"]
        chk["royalties = units x round(0.15 x price), every day"] = roy_ok
        chk["royalties paid = received = owner's royalties, every day"] = paid_ok
        chk["licence from day 10 to 30, 6 licensees"] = all(
            (owner in d["outcome"].get("licensing", {}).get("owners", {})) == (d["day"] >= b) for d in free["days"]) \
            and len(lic) == 6
        chk["owner_liable changes no trade"] = [d["outcome"]["brands"]["units_by_stall"] for d in free["days"]] == \
            [d["outcome"]["brands"]["units_by_stall"] for d in liab["days"]]
        fines = sum(d["outcome"]["licensing"]["owners"][owner]["fines_at_licensees_to_owner_cents"] for d in liab["days"][b - 1:])
        lic_fines_free = sum(d["outcome"]["licensing"]["owners"][owner]["fines_at_licensees_to_licensees_cents"]
                             for d in free["days"][b - 1:])
        chk["liable: owner charged exactly the fines at licensees"] = \
            liab["liability"]["by_stall"].get(owner, {}).get("charged_cents", 0) == fines == lic_fines_free
        chk["not liable: owner charged nothing"] = owner not in free["liability"]["by_stall"]
        chk["liable: owner's total falls by exactly those fines"] = \
            benchmark.stall_total(liab, owner) == benchmark.stall_total(free, owner) - fines
        brand = free["days"][0]["brands"][owner]
        r_free, r_never = free["days"][-1]["brand_ratings"][brand], never["days"][-1]["brand_ratings"][brand]
        r_con = con["days"][-1]["brand_ratings"][brand]
        chk["reviews land on the brand (cheap rating at day 30 below never's)"] = r_free < r_never
        chk["contract licensees: no false claim, no catch"] = tap.false_msgs == 0 and tap.catches == 0 and all(
            d["outcome"]["licensing"]["owners"][owner]["catches_at_licensees"] == 0 for d in con["days"][b - 1:])
        chk["guard 0 (stuck, idle) in every chain"] = all(
            o["stuck_buyers"]["total"] == 0 and o["idle_choosers"]["total"] == 0 for o in (never, free, liab, con))
        chk["no invalid actions"] = all(sum(d["outcome"]["fallbacks"]["buyer"] + d["outcome"]["fallbacks"]["seller"]
                                            for d in o["days"]) == 0 for o in (never, free, liab, con))
        out[t] = {"owner": owner, "licensees": lic, "checks": chk,
                  "numbers": {"royalties_cents": sum(d["outcome"]["licensing"]["owners"][owner]["royalties_cents"]
                                                     for d in free["days"][b - 1:]),
                              "fines_at_licensees_cents": fines,
                              "catches_at_licensees": sum(d["outcome"]["licensing"]["owners"][owner]["catches_at_licensees"]
                                                          for d in free["days"][b - 1:]),
                              "rating_day30": {"never": r_never, "cheap": r_free, "contract": r_con},
                              "owner_total_cents": {"never": benchmark.stall_total(never, owner),
                                                    "cheap_free": benchmark.stall_total(free, owner),
                                                    "cheap_liable": benchmark.stall_total(liab, owner),
                                                    "contract": benchmark.stall_total(con, owner)}}}
    return {"seed": seed, "option": list(opt), "by_ver": out,
            "pass": all(all(v["checks"].values()) for v in out.values())}


# ------------------------------------------------------------------ report

def _t(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + \
           ["| " + " | ".join(str(x).replace("|", "\\|") for x in r) + " |" for r in rows]


def report(P: dict) -> str:
    g1r, g2r, g3 = P.get("g1"), P.get("g2"), P.get("g3")
    L = ["# Pilot gate: licensing run", "",
         f"Spec \"Part 2: licensing\" (2026-11-11). Throwaway seeds 915–919. Engine {P['engine_version']}, "
         f"commit {P['git']['commit'][:7]} (uncommitted: {P['git']['status_porcelain'] or 'none'}); "
         f"{P['platform']}, numpy {P['numpy']}.", ""]
    if P.get("tests"):
        L += [f"Tests: {P['tests']}", ""]
    if g1r:
        L += [f"## G1: defaults reproduce engine 0.15.0 — {'PASS' if g1r['pass'] else 'FAIL'}", "",
              f"Full 30-day chains run by engine 0.15.0 (worktree at {g1r['old_commit']}) and by {P['engine_version']} "
              "with licensing at its defaults; outcome and log body (all lines after the header) compared byte for byte.",
              "", *_t(["Chain", "Identical", "Log lines"],
                      [[k, "yes" if r["identical"] else "NO", f"{r['lines']:,}"] for k, r in g1r["cases"].items()]), ""]
    if g2r:
        L += [f"## G2: royalty and liability accounting on full chains — {'PASS' if g2r['pass'] else 'FAIL'}", "",
              f"Seed {g2r['seed']}, detect_scale 1, licence to 6 from day 10, first sampled owner of the seed.", ""]
        for t, v in g2r["by_ver"].items():
            n = v["numbers"]
            L += [f"**{X.VLAB[t]}** (owner {v['owner']}, licensees {', '.join(v['licensees'])}):", "",
                  *_t(["Check", "Result"], [[k, "pass" if ok else "FAIL"] for k, ok in v["checks"].items()]), "",
                  f"Royalties ${n['royalties_cents'] / 100:,.2f}; catches at licensees {n['catches_at_licensees']}; "
                  f"fines from them ${n['fines_at_licensees_cents'] / 100:,.2f}. Brand rating on day 30: never "
                  f"{n['rating_day30']['never']:.3f}, cheap {n['rating_day30']['cheap']:.3f}, contract "
                  f"{n['rating_day30']['contract']:.3f}. Owner's 30-day total: never "
                  f"${n['owner_total_cents']['never'] / 100:,.2f}, cheap ${n['owner_total_cents']['cheap_free'] / 100:,.2f}, "
                  f"cheap and liable ${n['owner_total_cents']['cheap_liable'] / 100:,.2f}, contract "
                  f"${n['owner_total_cents']['contract'] / 100:,.2f}. These are pilot numbers on one seed, not results.", ""]
    if g3:
        L += ["## G3: timing and projection", ""] + g3["lines"] + [""]
    if P.get("notes"):
        L += ["## Notes", ""] + [f"- {x}" for x in P["notes"]] + [""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--g1", action="store_true")
    ap.add_argument("--g2", action="store_true")
    ap.add_argument("--g3", help="JSON {timing: <--timing output>, pipeline: {...}, lines: [...]} to merge in")
    ap.add_argument("--tests", default="")
    ap.add_argument("--note", action="append", default=[])
    ap.add_argument("--rewrite", action="store_true", help="regenerate the markdown from the JSON")
    a = ap.parse_args(argv)
    X.LB._lower_priority()
    P = json.load(open(OUT_JSON)) if os.path.exists(OUT_JSON) else {}
    P.update(engine_version=ENGINE_VERSION, git=_git(), platform=__import__("platform").platform(),
             numpy=__import__("numpy").__version__)
    if a.tests:
        P["tests"] = a.tests
    if a.note:
        P["notes"] = P.get("notes", []) + a.note
    if a.g1:
        P["g1"] = g1()
        print("G1", P["g1"]["pass"], f"{P['g1']['wall_s']:.0f} s", flush=True)
    if a.g2:
        t0 = time.time()
        P["g2"] = g2()
        print("G2", P["g2"]["pass"], f"{time.time() - t0:.0f} s", flush=True)
        for t, v in P["g2"]["by_ver"].items():
            print(t, json.dumps(v["checks"]), json.dumps(v["numbers"]))
    if a.g3:
        P["g3"] = json.load(open(a.g3))
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(P, f, indent=1, sort_keys=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(report(P))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
