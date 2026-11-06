"""Counterfeits, budgets and a penalty-aware bust-out rule (rule-based only).

Prespecified design (2026-11-06; see runs/counterfeit_summary.md). Engine 0.9.0.
  As the 2026-11-06 brands run: ratings public; 2 patrolling inspectors, not uniformed; naive
  deceptive sellers (rule_deceptive); D = 30 days, known to sellers; imitation off; brands on with
  premium pi = 0.4 (placeholder). New: buyers' budget as a dial (buyers.budget_factor_override),
  buyers.count from a calibration step, and rule_genuine_rational_v2.

Calibration (separate seeds 100-104, never the main-run seeds):
    .venv/bin/python -m analysis.counterfeit --calibrate --out runs/counterfeit_calibration.json
  Condition: budget 1.25, tourist share 0.4, fresh reopening, always-honest originals. Candidate
  counts 150, 200, ..., 600, 700, ..., 1000 in ascending order (decided 2026-11-06); the chosen
  count is the smallest whose pooled share of genuine brands rated at the end of day 10 (over all
  genuine stalls and the 5 seeds) is >= 80%. If none is, stop and report. Calibration chains run
  10 days: with these policies nothing in days 1-10 depends on D (rule_honest and rule_deceptive
  ignore the horizon), and the main-run gate re-measures the share with D = 30.

Main run (seeds 0-29, paired):
    .venv/bin/python -m analysis.counterfeit --calibration runs/counterfeit_calibration.json \\
        --out runs/counterfeit.json
  Grid 1 (counterfeit economics): budget factor {1.0, 1.1, 1.25, 1.5} x reopen {fresh, counterfeit};
    tourist share 0.4; always-honest originals (rule_genuine = rule_honest).
  Grid 2 (bust-out): original policy {rule_genuine, rational_v1, rational_v2} x reopen; budget 1.25;
    tourist share 0.4.
  Grid 3 (tourist puzzle): tourist share {0.2, 0.6} x reopen; budget 1.25; always-honest.
  Each distinct condition runs once (16); shared cells are reported in every grid that uses them.
  Tourist shares: locals and experts split the rest evenly (0.4 -> 0.4 / 0.3 / 0.3).

Gate: (a) in the calibration condition on the main-run seeds, >= 80% of genuine brands are rated
by the end of day 10 (pooled); (b) the engine test suite passes (defaults reproduce 0.8.0;
recorded with --tests). If the gate fails, only the gate is reported.

Late = mean over days 26-30. Paired by seed; 95% t-intervals, unadjusted.
  PF1 (confirmatory): per-seed OLS slope over the four budget factors of the late deceptive profit
      per stall gap, counterfeit - fresh (grid 1), > 0.
  PF2 (confirmatory): that gap at budget 1.5 > 0.
  PF3 (confirmatory): late genuine profit per stall, v2 - v1 (fresh reopening), > 0.
  PF4 (confirmatory): under v2, mean bust-out day of genuine stalls (never = 31), counterfeit -
      fresh, < 0.
  Two-sided, no prediction: late genuine profit per stall, v2 - always-honest (fresh reopening).
  Exploratory: the tourist puzzle (decomposition of deceptive profit by buyer profile, price paid
  and review effects, at tourist shares 0.2 / 0.4 / 0.6); share of genuine brands rated over time;
  shortfall and buyer surplus throughout.

This script only reads engine outputs; it changes nothing in the engine.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from cli.sweep import parse_seeds
from engine import ENGINE_VERSION, bazaar
from engine.config import load
from engine.jsonlog import JsonlLog
from engine.metrics import mean_ci, paired_diff

DAYS = 30
LATE = list(range(26, 31))
BUDGETS = [1.0, 1.1, 1.25, 1.5]
REOPEN = ["fresh", "counterfeit"]
SHARES = {"t20": '{"tourist":0.2,"local":0.4,"expert":0.4}',
          "t40": '{"tourist":0.4,"local":0.3,"expert":0.3}',
          "t60": '{"tourist":0.6,"local":0.2,"expert":0.2}'}
TOURIST = {"t20": 0.2, "t40": 0.4, "t60": 0.6}
GEN = {"honest": "rule_honest", "v1": "rule_genuine_rational", "v2": "rule_genuine_rational_v2"}
GRID1 = [(f, s, "t40", "honest") for f in BUDGETS for s in REOPEN]
GRID2 = [(1.25, s, "t40", g) for g in GEN for s in REOPEN]
GRID3 = [(1.25, s, t, "honest") for t in ("t20", "t60") for s in REOPEN]
CONDS = list(dict.fromkeys(GRID1 + GRID2 + GRID3))
CAL_COND = (1.25, "fresh", "t40", "honest")
CAL_COUNTS = list(range(150, 601, 50)) + list(range(700, 1001, 100))
CAL_SEEDS = list(range(100, 105))
CAL_DAY = 10
CAL_TARGET = 0.80
PROFILES = ["tourist", "local", "expert"]
SERIES = ["deceptive_profit", "genuine_profit", "seconds_profit", "shortfall_rate", "surplus", "task_complete",
          "catches", "renames", "counterfeit_stalls", "busted", "rated_share_genuine", "rating_genuine",
          "genuine_premium", "deceptive_premium"]
LABEL = {"fresh": "fresh name", "counterfeit": "counterfeit", "t20": "tourists 20%", "t40": "tourists 40%",
         "t60": "tourists 60%", "honest": "rule_genuine", "v1": "rational v1", "v2": "rational v2"}
COMMON = ["ratings.mode=public", "inspectors.count=2", "inspectors.placement=patrolling", "inspectors.uniformed=false",
          "agents.seller.deceptive=rule_deceptive", "brands.enabled=true", "brands.premium=0.4",
          "market.horizon_known=true", "evolution.revise_prob=0", "evolution.mutation_prob=0"]


def cname(f, s, t, g) -> str:
    return f"{f:g}|{s}|{t}|{g}"


def _overrides(f, s, t, g, seed, count, days=DAYS) -> list[str]:
    return [*COMMON, f"buyers.count={count}", f"buyers.budget_factor_override={f}", f"market.days={days}",
            f"agents.params.rule_deceptive.reopen={s}", f"buyers.profile_shares={SHARES[t]}",
            f"agents.seller.genuine={GEN[g]}", f"seed={seed}"]


class Tap(JsonlLog):
    """Keeps only what the decomposition needs: each day's purchases and catches, by day."""

    def __init__(self):
        super().__init__(None, keep=False)
        self.day = 1
        self.buys: dict = {}
        self.catches: dict = {}

    def emit(self, ev, **f):
        if ev == "day_start":
            self.day = f["day"]
        elif ev == "delta" and self.day in LATE:
            if f["buys"]:
                self.buys.setdefault(self.day, []).extend(f["buys"])
            if f["catches"]:
                self.catches.setdefault(self.day, []).extend(f["catches"])


def _genuine_rated(d, gen_sids) -> tuple[int, int]:
    return sum(d["brand_ratings"].get(d["brands"][s]) is not None for s in gen_sids), len(gen_sids)


# ------------------------------------------------------------------ calibration

def _cal_job(args) -> dict:
    count, seed = args
    f, s, t, g = CAL_COND
    out = bazaar.run(load(None, _overrides(f, s, t, g, seed, count, days=CAL_DAY), mode="bazaar"))
    d = out["days"][CAL_DAY - 1]
    gen = [sid for sid, ty in out["days"][0]["stall_types"].items() if ty == "genuine"]
    rated, n = _genuine_rated(d, gen)
    by_day = [_genuine_rated(x, gen)[0] / n for x in out["days"]]
    return {"count": count, "seed": seed, "rated": rated, "genuine": n, "rated_share_by_day": by_day}


def calibrate(a) -> int:
    t0 = time.time()
    table = []
    chosen = None
    with ProcessPoolExecutor(min(a.workers, len(CAL_SEEDS))) as ex:
        for n in CAL_COUNTS:
            rs = list(ex.map(_cal_job, [(n, sd) for sd in CAL_SEEDS]))
            rated, tot = sum(r["rated"] for r in rs), sum(r["genuine"] for r in rs)
            row = {"count": n, "rated": rated, "genuine": tot, "share": rated / tot,
                   "per_seed": {r["seed"]: [r["rated"], r["genuine"]] for r in rs},
                   "mean_share_by_day": [float(np.mean([r["rated_share_by_day"][d] for r in rs])) for d in range(CAL_DAY)],
                   "elapsed_s": round(time.time() - t0, 1)}
            table.append(row)
            print(f"count {n}: {rated}/{tot} = {rated / tot:.1%} rated by day {CAL_DAY} ({time.time() - t0:.0f} s)",
                  flush=True)
            if rated / tot >= CAL_TARGET:
                chosen = n
                break
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
            "command": " ".join([".venv/bin/python -m analysis.counterfeit", *sys.argv[1:]]),
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
            "condition": cname(*CAL_COND), "seeds": CAL_SEEDS, "day": CAL_DAY, "target": CAL_TARGET,
            "candidates": CAL_COUNTS, "wall_clock_s": time.time() - t0, "load_at_end": _load()}
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "table": table, "chosen_count": chosen}, fh, indent=1, sort_keys=True)
    print(f"chosen count: {chosen}; wrote {a.out}")
    return 0 if chosen is not None else 1


def _diag_job(args) -> dict:
    """Why genuine brands stay unrated (calibration seeds only): units each genuine stall sells
    over the calibration days, and on day 1 how often each stall is within reach of a buyer of
    its category who still needs units."""
    count, seed = args
    f, s, t, g = CAL_COND
    c = load(None, _overrides(f, s, t, g, seed, count, days=CAL_DAY), mode="bazaar")
    out = bazaar.run(c)
    gen = [sid for sid, ty in out["days"][0]["stall_types"].items() if ty == "genuine"]
    d = out["days"][CAL_DAY - 1]
    units = {sid: sum(x["outcome"]["brands"]["units_by_stall"][sid] for x in out["days"]) for sid in gen}
    log = JsonlLog(keep=True)
    bazaar.run(load(None, _overrides(f, s, t, g, seed, count, days=1), mode="bazaar"), log=log)
    world, reach = None, {}
    for line in log.lines:
        e = json.loads(line)
        if e["ev"] == "world":
            world = e
            cat = {x["sid"]: x["category"] for x in e["stalls"]}
        elif e["ev"] == "obs" and e["role"] == "buyer" and e["obs"]["you"]["task"]["units_needed"] > 0:
            for r in e["obs"]["stalls_here"]:
                if cat[r["id"]] == e["obs"]["you"]["task"]["category"]:
                    reach[r["id"]] = reach.get(r["id"], 0) + 1
    stalls = {x["sid"]: {"category": x["category"], "type": x["stype"], "pos": x["pos"]} for x in world["stalls"]}
    return {"count": count, "seed": seed,
            "genuine": {sid: {**stalls[sid], "units_10d": units[sid],
                              "rated_day10": d["brand_ratings"].get(d["brands"][sid]) is not None,
                              "day1_reach_while_shopping": reach.get(sid, 0)} for sid in gen},
            "day1_reach_while_shopping_all": {sid: reach.get(sid, 0) for sid in stalls}, "stalls": stalls}


def diagnose(a) -> int:
    jobs = [(n, sd) for n in (150, 600) for sd in CAL_SEEDS]
    with ProcessPoolExecutor(a.workers) as ex:
        rs = list(ex.map(_diag_job, jobs))
    summ = {}
    for n in (150, 600):
        rows = [g_ for r in rs if r["count"] == n for g_ in r["genuine"].values()]
        un = [g_ for g_ in rows if not g_["rated_day10"]]
        summ[n] = {"genuine": len(rows), "unrated": len(un),
                   "unrated_with_zero_units": sum(g_["units_10d"] == 0 for g_ in un),
                   "unrated_never_in_reach_day1": sum(g_["day1_reach_while_shopping"] == 0 for g_ in un),
                   "unrated_by_category": {c: sum(g_["category"] == c for g_ in un) for c in ("fish", "electronics", "designer")}}
        print(n, summ[n], flush=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"meta": {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
                            "command": " ".join([".venv/bin/python -m analysis.counterfeit", *sys.argv[1:]]),
                            "seeds": CAL_SEEDS, "condition": cname(*CAL_COND)},
                   "summary": summ, "runs": rs}, fh, indent=1, sort_keys=True)
    return 0


# ------------------------------------------------------------------ main run

def _job(args) -> dict:
    f, s, t, g, seed, count = args
    c = load(None, _overrides(f, s, t, g, seed, count), mode="bazaar")
    tap = Tap()
    out = bazaar.run(c, log=tap)
    stype = out["days"][0]["stall_types"]
    eng0 = bazaar.BazaarEngine(c)
    cat = {st.sid: st.category for st in eng0.stalls}
    pen = {st.sid: st.penalty_cents for st in eng0.stalls}
    base = c.pricing.base_price_cents
    tier = {"genuine": 1.0, "deceptive": c.pricing.deceptive_price_factor, "seconds": c.pricing.seconds_price_factor}
    gen = [sid for sid, ty in stype.items() if ty == "genuine"]
    dec = [sid for sid, ty in stype.items() if ty == "deceptive"]
    bust = {sid: None for sid in gen}
    cf_names: set = set()
    days = []
    for d in out["days"]:
        o = d["outcome"]
        pt = o["seller_by_type"]
        for r in d["renames"]:
            if r["how"] == "counterfeit" and r["counterfeit_of"] is not None:
                cf_names.add(r["to"])
        for b in d["bust_outs"]:
            bust[b["stall"]] = b["day"]
        rated, n = _genuine_rated(d, gen)
        rg = [d["brand_ratings"][d["brands"][sid]] for sid in gen if d["brand_ratings"].get(d["brands"][sid]) is not None]
        prem = {ty: [d["prices"][sid] / (base[cat[sid]] * tier[ty]) - 1 for sid, t_ in stype.items() if t_ == ty]
                for ty in ("genuine", "deceptive")}
        days.append({"deceptive_profit": pt["deceptive"]["profit_per_stall_cents"] if "deceptive" in pt else None,
                     "genuine_profit": pt["genuine"]["profit_per_stall_cents"] if "genuine" in pt else None,
                     "seconds_profit": pt["seconds"]["profit_per_stall_cents"] if "seconds" in pt else None,
                     "shortfall_rate": o["shortfall_rate"], "surplus": o["buyer_surplus_mean_cents"],
                     "task_complete": o["task_complete_share"], "catches": o["catches"],
                     "renames": o["brands"]["renames"], "counterfeit_stalls": o["brands"]["counterfeit_stalls"],
                     "busted": o["brands"]["busted_stalls"], "rated_share_genuine": rated / n,
                     "rating_genuine": float(np.mean(rg)) if rg else None,
                     "genuine_premium": float(np.mean(prem["genuine"])),
                     "deceptive_premium": float(np.mean(prem["deceptive"]))})
    # decomposition of deceptive-type stalls' late profit (sums over days 26-30, per stall-day)
    sd = len(dec) * len(LATE)
    acc = {f"{k}_{p}": 0.0 for k in ("units", "revenue", "cf_units", "rated_units", "base_value") for p in PROFILES}
    misfiled = 0
    dset = set(dec)
    for day in LATE:
        for b in tap.buys.get(day, []):
            if b["stall"] not in dset:
                continue
            p = b["buyer_profile"]
            acc[f"units_{p}"] += b["units"]
            acc[f"revenue_{p}"] += b["amount_cents"]
            acc[f"base_value_{p}"] += b["units"] * base[cat[b["stall"]]]
            if b["brand"] in cf_names:
                acc[f"cf_units_{p}"] += b["units"]
            if b["known_claims"]:
                acc[f"rated_units_{p}"] += b["units"]
                if b["filed_under"] != b["brand"]:
                    misfiled += b["units"]
    comp = {k: 0.0 for k in ("revenue_cents", "cost_cents", "ad_spend_cents", "penalties_cents", "profit_cents",
                             "catches", "units_sold")}
    low_rated, cur_rating = [], []
    for day in LATE:
        d = out["days"][day - 1]
        dd = d["outcome"]["seller_by_type"].get("deceptive", {})
        for k in comp:
            comp[k] += dd.get(k, 0)
        prev = out["days"][day - 2]          # start of day = end of the day before
        for sid in dec:
            r = prev["brand_ratings"].get(prev["brands"][sid])
            low_rated.append(r is not None and r < c.ratings.tau)
            if r is not None:
                cur_rating.append(r)
    decomp = {**{k: v / sd for k, v in acc.items()}, **{f"{k}_per_stall_day": v / sd for k, v in comp.items()},
              "misfiled_units_per_stall_day": misfiled / sd,
              "share_low_rated_stall_days": float(np.mean(low_rated)),
              "mean_rating_current": float(np.mean(cur_rating)) if cur_rating else None,
              "penalty_per_catch_cents": float(np.mean([pen[s] for s in dec]))}
    return {"cond": cname(f, s, t, g), "seed": seed, "days": days, "bust": bust, "decomp": decomp,
            "n_genuine": len(gen), "n_deceptive": len(dec)}


def _git() -> dict:
    def g(*a):
        return subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
    return {"commit": g("rev-parse", "HEAD"), "status_porcelain": g("status", "--porcelain").splitlines()}


def _load() -> list[float]:
    return [round(x, 2) for x in os.getloadavg()]


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ analysis

def _arr(v, cond, m) -> np.ndarray:
    return np.array([[np.nan if x[m] is None else x[m] for x in r["days"]] for r in v[cond]], float)


def _late(a) -> np.ndarray:
    with np.errstate(all="ignore"):
        return np.nanmean(a[:, [d - 1 for d in LATE]], 1)


def _lst(a) -> list:
    return [None if (x is None or np.isnan(x)) else float(x) for x in a]


def _verdict(st, sign=+1):
    if st["lo"] is None:
        return "not testable"
    if (sign > 0 and st["lo"] > 0) or (sign < 0 and st["hi"] < 0):
        return "supported"
    if (sign > 0 and st["hi"] < 0) or (sign < 0 and st["lo"] > 0):
        return "contradicted (interval on the opposite side of 0)"
    return "not supported (interval includes 0)"


def _direction(st):
    if st["lo"] is None:
        return "not testable"
    if st["lo"] > 0:
        return "positive (interval above 0)"
    if st["hi"] < 0:
        return "negative (interval below 0)"
    return "interval includes 0"


def _bust_days(r) -> list[int]:
    return [DAYS + 1 if b is None else b for b in r["bust"].values()]


def _mean_bust(v, cond):
    return [float(np.mean(_bust_days(r))) for r in v[cond]]


def _share_bust(v, cond):
    return [float(np.mean([b is not None for b in r["bust"].values()])) for r in v[cond]]


def _slope(xs, G):
    x = np.array(xs, float)
    xc = x - x.mean()
    return (G * xc).sum(1) / (xc ** 2).sum()


def analyse(v: dict) -> dict:
    res: dict = {"trajectory": {}, "late": {}}
    for cond in v:
        for m in SERIES:
            a = _arr(v, cond, m)
            res["trajectory"][f"{cond}|{m}"] = [mean_ci(_lst(a[:, j])) for j in range(DAYS)]
            res["late"][f"{cond}|{m}"] = mean_ci(_lst(_late(a)))
    L = {(cond, m): _late(_arr(v, cond, m)) for cond in v for m in SERIES}

    def diff(c_a, c_b, m):          # paired, b - a
        return paired_diff(_lst(L[(c_a, m)]), _lst(L[(c_b, m)]))

    # PF1 / PF2: counterfeit - fresh deceptive profit gap over budget factors
    gap = {f: L[(cname(f, "counterfeit", "t40", "honest"), "deceptive_profit")]
           - L[(cname(f, "fresh", "t40", "honest"), "deceptive_profit")] for f in BUDGETS}
    res["gap_by_budget"] = {f"{f:g}": mean_ci(_lst(gap[f])) for f in BUDGETS}
    sl = _slope(BUDGETS, np.stack([gap[f] for f in BUDGETS], 1)) * 0.1
    res["pf1"] = {**mean_ci(_lst(sl)), "unit": "cents per +0.1 of budget factor"}
    res["pf1"]["verdict"] = _verdict(res["pf1"], +1)
    res["pf2"] = {**res["gap_by_budget"]["1.5"], "verdict": _verdict(res["gap_by_budget"]["1.5"], +1)}
    # PF3 and the two-sided question
    for s in REOPEN:
        res[f"v2_v1_{s}"] = diff(cname(1.25, s, "t40", "v1"), cname(1.25, s, "t40", "v2"), "genuine_profit")
        res[f"v2_honest_{s}"] = diff(cname(1.25, s, "t40", "honest"), cname(1.25, s, "t40", "v2"), "genuine_profit")
        res[f"v1_honest_{s}"] = diff(cname(1.25, s, "t40", "honest"), cname(1.25, s, "t40", "v1"), "genuine_profit")
    res["pf3"] = {**res["v2_v1_fresh"], "verdict": _verdict(res["v2_v1_fresh"], +1)}
    res["q_honesty"] = {**res["v2_honest_fresh"], "direction": _direction(res["v2_honest_fresh"])}
    # PF4 and bust-out timing
    bt = {}
    for g in ("v1", "v2"):
        for s in REOPEN:
            cond = cname(1.25, s, "t40", g)
            pooled = [b for r in v[cond] for b in _bust_days(r)]
            bt[f"{g}|{s}"] = {"mean_day": mean_ci(_mean_bust(v, cond)), "share_bust": mean_ci(_share_bust(v, cond)),
                              "median_day_pooled": float(np.median(pooled)),
                              "hist": [int(sum(1 for b in pooled if b == d)) for d in range(1, DAYS + 2)]}
        f_, c_ = cname(1.25, "fresh", "t40", g), cname(1.25, "counterfeit", "t40", g)
        bt[f"{g}|cf-fresh"] = paired_diff(_mean_bust(v, f_), _mean_bust(v, c_))
        bt[f"{g}|share cf-fresh"] = paired_diff(_share_bust(v, f_), _share_bust(v, c_))
    for s in REOPEN:
        bt[f"v2-v1|{s}"] = paired_diff(_mean_bust(v, cname(1.25, s, "t40", "v1")), _mean_bust(v, cname(1.25, s, "t40", "v2")))
        bt[f"share v2-v1|{s}"] = paired_diff(_share_bust(v, cname(1.25, s, "t40", "v1")),
                                             _share_bust(v, cname(1.25, s, "t40", "v2")))
    res["bust"] = bt
    res["pf4"] = {**bt["v2|cf-fresh"], "verdict": _verdict(bt["v2|cf-fresh"], -1)}
    # contrasts for every pair of fresh / counterfeit cells (exploratory)
    res["cf_fresh"] = {}
    for f, s, t, g in CONDS:
        if s != "fresh":
            continue
        a, b = cname(f, "fresh", t, g), cname(f, "counterfeit", t, g)
        for m in ("deceptive_profit", "genuine_profit", "shortfall_rate", "surplus", "rating_genuine",
                  "rated_share_genuine", "catches"):
            res["cf_fresh"][f"{f:g}|{t}|{g}|{m}"] = diff(a, b, m)
    res["policy_contrasts"] = {}
    for s in REOPEN:
        for g in ("v1", "v2"):
            for m in ("shortfall_rate", "surplus", "genuine_profit", "deceptive_profit"):
                res["policy_contrasts"][f"{s}|{g}-honest|{m}"] = diff(cname(1.25, s, "t40", "honest"),
                                                                      cname(1.25, s, "t40", g), m)
    # tourist puzzle: gap by tourist share at budget 1.25 and its slope; decomposition
    tg = {t: L[(cname(1.25, "counterfeit", t, "honest"), "deceptive_profit")]
          - L[(cname(1.25, "fresh", t, "honest"), "deceptive_profit")] for t in TOURIST}
    res["gap_by_tourist"] = {t: mean_ci(_lst(tg[t])) for t in TOURIST}
    res["gap_tourist_slope"] = {**mean_ci(_lst(_slope([TOURIST[t] for t in TOURIST],
                                                       np.stack([tg[t] for t in TOURIST], 1)) * 0.2)),
                                "unit": "cents per +0.2 of tourist share"}
    keys = list(next(iter(v.values()))[0]["decomp"].keys())
    res["decomp"] = {}
    for t in TOURIST:
        for s in REOPEN:
            rows = v[cname(1.25, s, t, "honest")]
            res["decomp"][f"{t}|{s}"] = {k: mean_ci([r["decomp"][k] for r in rows]) for k in keys}
        rf, rc = v[cname(1.25, "fresh", t, "honest")], v[cname(1.25, "counterfeit", t, "honest")]
        res["decomp"][f"{t}|cf-fresh"] = {k: paired_diff([r["decomp"][k] for r in rf], [r["decomp"][k] for r in rc])
                                          for k in keys}
    # floors and ceilings
    flags = []
    for cond in v:
        sb = res["late"][f"{cond}|shortfall_rate"]["mean"]
        if sb is not None and (sb < 0.02 or sb > 0.98):
            flags.append(f"{cond}: late shortfall {sb:.3f}")
        if cond.endswith("|v1") or cond.endswith("|v2"):
            share = float(np.mean(_share_bust(v, cond)))
            if share in (0.0, 1.0):
                flags.append(f"{cond}: share busting out = {share:g}")
    res["flags"] = flags
    return res


# ------------------------------------------------------------------ formatting

def _d(x, signed=False):
    if x is None:
        return "–"
    return (f"{x / 100:+,.2f}" if signed else f"{x / 100:,.2f}").replace("-", "−")


def _ci(st, f, signed=True):
    if st is None or st.get("mean") is None:
        return "–"
    s = f(st["mean"], signed)
    if st.get("lo") is not None:
        s += f" [{f(st['lo'], signed)}, {f(st['hi'], signed)}]"
        if signed and (st["lo"] > 0 or st["hi"] < 0):
            s += " *"
    return s


def _pct(x, signed=False):
    if x is None:
        return "–"
    return (f"{100 * x:+.1f}" if signed else f"{100 * x:.1f}").replace("-", "−")


def _num(dp):
    def f(x, signed=False):
        if x is None:
            return "–"
        return (f"{x:+.{dp}f}" if signed else f"{x:.{dp}f}").replace("-", "−")
    return f


def _t(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(r) + " |" for r in rows]


SERIF = '"ET Book", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
STYLE = ("<style>"
         f".bg{{fill:#fffff8}} .t{{font-family:{SERIF};fill:#111}} .s{{font-family:{SERIF};fill:#666}} "
         ".k{font-family:system-ui,-apple-system,sans-serif;fill:#999;font-size:11px} "
         ".n{font-family:system-ui,-apple-system,sans-serif;fill:#aaa;font-size:10.5px} "
         f".lb{{font-family:{SERIF};font-size:12.5px;fill:#333}} .ax{{stroke:#ccc;stroke-width:1}} "
         ".zero{stroke:#bbb;stroke-width:1;stroke-dasharray:3 3} .ln{stroke:#666;stroke-width:1.6;fill:none} "
         ".ci{stroke:#666;stroke-width:1.2} .pt{fill:#666} .hl{fill:#e15759} .hlc{stroke:#e15759;stroke-width:1.4} "
         ".bar{fill:#7a7a7a} .bar31{fill:#bbb} .med{stroke:#e15759;stroke-width:1.4} .medt{fill:#e15759} "
         f".an{{font-family:{SERIF};font-style:italic;font-size:12px;fill:#333}} "
         "@media (prefers-color-scheme: dark){.bg{fill:#151515} .t{fill:#ddd} .s{fill:#999} .k{fill:#888} .n{fill:#666} "
         ".lb{fill:#bbb} .ax{stroke:#444} .zero{stroke:#555} .ln{stroke:#aaa} .ci{stroke:#aaa} .pt{fill:#aaa} "
         ".hl{fill:#fc8d62} .hlc{stroke:#fc8d62} .bar{fill:#999} .bar31{fill:#555} .med{stroke:#fc8d62} "
         ".medt{fill:#fc8d62} .an{fill:#bbb}}</style>")


def plot_gap_svg(res: dict, n_seeds: int, count: int, version: str = ENGINE_VERSION) -> str:
    """Counterfeit − fresh deceptive profit gap (late, $/stall/day) against budget factor, with
    paired 95% intervals; zero line for reference."""
    W, H = 900, 600
    left, top, pw, ph = 110, 120, 700, 360
    g = res["gap_by_budget"]
    vals = [g[f"{f:g}"] for f in BUDGETS]
    lo = min(min(x["lo"] for x in vals), 0) / 100
    hi = max(max(x["hi"] for x in vals), 0) / 100
    pad = (hi - lo) * 0.08
    lo, hi = lo - pad, hi + pad

    def X(f):
        return left + (f - 0.975) / (1.525 - 0.975) * pw

    def Y(y):
        return top + ph - (y - lo) / (hi - lo) * ph
    p1 = res["pf1"]
    title = "Counterfeit − fresh-name profit per deceptive stall, by buyers' budget"
    sub = (f"Late days 26–30, $ per stall per day; slope {_num(2)(p1['mean'] / 100, True)} "
           f"[{_num(2)(p1['lo'] / 100, True)}, {_num(2)(p1['hi'] / 100, True)}] per +0.1 of budget factor")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" aria-labelledby="t d">',
           STYLE, f'<rect class="bg" x="0" y="0" width="{W}" height="{H}"/>', f'<title id="t">{title}</title>',
           f'<desc id="d">Mean paired gap at budget factors 1.0, 1.1, 1.25 and 1.5 with 95% intervals over {n_seeds} '
           f'seeds: ' + "; ".join(f"{f:g}: {_d(x['mean'], True)}" for f, x in zip(BUDGETS, vals)) + '.</desc>',
           f'<text class="t" x="30" y="44" font-size="20">{title}</text>',
           f'<text class="s" x="30" y="70" font-size="14">{sub}</text>']
    out.append(f'<line class="zero" x1="{left}" y1="{Y(0):.1f}" x2="{left + pw}" y2="{Y(0):.1f}"/>')
    pts = " ".join(f"{X(f):.1f},{Y(x['mean'] / 100):.1f}" for f, x in zip(BUDGETS, vals))
    out.append(f'<polyline class="ln" points="{pts}"/>')
    for f, x in zip(BUDGETS, vals):
        cls, ccls = ("hl", "hlc") if f == 1.5 else ("pt", "ci")
        out.append(f'<line class="{ccls}" x1="{X(f):.1f}" y1="{Y(x["lo"] / 100):.1f}" x2="{X(f):.1f}" y2="{Y(x["hi"] / 100):.1f}"/>')
        out.append(f'<circle class="{cls}" cx="{X(f):.1f}" cy="{Y(x["mean"] / 100):.1f}" r="3.5"/>')
        out.append(f'<text class="lb" x="{X(f) + 8:.1f}" y="{Y(x["mean"] / 100) - 8:.1f}">{_d(x["mean"], True)}</text>')
    # axes: range frame
    yl, yh = min(x["lo"] for x in vals) / 100, max(x["hi"] for x in vals) / 100
    out.append(f'<line class="ax" x1="{left - 12}" y1="{Y(yl):.1f}" x2="{left - 12}" y2="{Y(yh):.1f}"/>')
    step = _nice((hi - lo) / 5)
    y = np.ceil(lo / step) * step
    while y <= hi:
        out.append(f'<text class="k" x="{left - 18}" y="{Y(y) + 4:.1f}" text-anchor="end">{_num(0)(y, y != 0)}</text>')
        y += step
    out.append(f'<line class="ax" x1="{X(1.0):.1f}" y1="{top + ph + 12}" x2="{X(1.5):.1f}" y2="{top + ph + 12}"/>')
    for f in BUDGETS:
        out.append(f'<text class="k" x="{X(f):.1f}" y="{top + ph + 28}" text-anchor="middle">{f:g}×</text>')
    out.append(f'<text class="k" x="{left + pw / 2}" y="{top + ph + 48}" text-anchor="middle">buyers\' budget per unit, '
               f'× base price</text>')
    out.append(f'<text class="k" x="{left - 70}" y="{top + ph / 2}" transform="rotate(-90 {left - 70} {top + ph / 2})" '
               f'text-anchor="middle">$ per deceptive stall per day</text>')
    out.append(f'<text class="n" x="30" y="{H - 40}">Bazaar engine {version}. Paired by seed ({n_seeds} seeds), 95% t-intervals, '
               f'unadjusted. Tourists 40%, always-honest originals, {count} buyers a day,</text>')
    out.append(f'<text class="n" x="30" y="{H - 24}">2 patrolling inspectors, naive deceptive sellers, 30 days, premium 0.4 '
               f'(placeholder). A counterfeit posts the original\'s price (up to 1.2 × base).</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def _nice(x):
    e = 10 ** np.floor(np.log10(x))
    for m in (1, 2, 2.5, 5, 10):
        if m * e >= x:
            return m * e
    return 10 * e


def plot_bust_svg(res: dict, n_seeds: int, count: int, version: str = ENGINE_VERSION) -> str:
    """Small multiples: bust-out day distributions, rule (rows: v1, v2) x reopen (columns). 31 = never."""
    W, H = 900, 640
    left, top, pw, ph, gx, gy = 90, 140, 360, 150, 50, 80
    bt = res["bust"]
    p4 = res["pf4"]
    title = "When honest originals bust out: penalty-blind v1 against penalty-aware v2"
    sub = (f"v2 mean bust-out day, counterfeit − fresh: {_num(2)(p4['mean'], True)} days "
           f"[{_num(2)(p4['lo'], True)}, {_num(2)(p4['hi'], True)}]")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" aria-labelledby="t d">',
           STYLE, f'<rect class="bg" x="0" y="0" width="{W}" height="{H}"/>', f'<title id="t">{title}</title>',
           f'<desc id="d">Four histograms of bust-out day over all genuine stalls and {n_seeds} seeds; the last bar is '
           f'stalls that never bust out; the vertical line is the median. The summary gives every value.</desc>',
           f'<text class="t" x="30" y="44" font-size="20">{title}</text>',
           f'<text class="s" x="30" y="70" font-size="14">{sub}</text>']
    ymax = max(max(bt[f"{g}|{s}"]["hist"]) for g in ("v1", "v2") for s in REOPEN)
    for ri, g in enumerate(("v1", "v2")):
        y0 = top + ri * (ph + gy)
        for ci, s in enumerate(REOPEN):
            x0 = left + ci * (pw + gx)
            bw = pw / (DAYS + 1)
            cell = bt[f"{g}|{s}"]
            if ri == 0:
                out.append(f'<text class="t" x="{x0}" y="{top - 34}" font-size="14">{LABEL[s]}</text>')
            if ci == 0:
                out.append(f'<text class="s" x="{left - 50}" y="{y0 + ph / 2:.1f}" font-size="13" '
                           f'transform="rotate(-90 {left - 50} {y0 + ph / 2:.1f})" text-anchor="middle">{LABEL[g]}</text>')
            for d, n in enumerate(cell["hist"], start=1):
                bh = n / ymax * ph
                cls = "bar31" if d == DAYS + 1 else "bar"
                out.append(f'<rect class="{cls}" x="{x0 + (d - 1) * bw + 0.5:.1f}" y="{y0 + ph - bh:.1f}" '
                           f'width="{bw - 1:.1f}" height="{bh:.1f}"/>')
            med = cell["median_day_pooled"]
            xm = x0 + (med - 0.5) * bw
            out.append(f'<line class="med" x1="{xm:.1f}" y1="{y0 - 18}" x2="{xm:.1f}" y2="{y0 + ph}"/>')
            lab = "median: never" if med == DAYS + 1 else f"median {med:g}"
            out.append(f'<text class="lb medt" x="{xm - 4:.1f}" y="{y0 - 8}" text-anchor="end">{lab}</text>')
            out.append(f'<text class="k" x="{x0 + 2}" y="{y0 + 8}">{100 * cell["share_bust"]["mean"]:.0f}% bust out; '
                       f'mean day {cell["mean_day"]["mean"]:.1f}</text>')
            out.append(f'<line class="ax" x1="{x0}" y1="{y0 + ph + 3}" x2="{x0 + pw}" y2="{y0 + ph + 3}"/>')
            for d in (1, 10, 20):
                out.append(f'<text class="k" x="{x0 + (d - 0.5) * bw:.1f}" y="{y0 + ph + 17}" text-anchor="middle">{d}</text>')
            out.append(f'<text class="k" x="{x0 + (DAYS + 0.5) * bw:.1f}" y="{y0 + ph + 17}" text-anchor="middle">∞</text>')
    yb = top + 2 * ph + gy + 44
    out.append(f'<text class="k" x="{left + pw + gx / 2:.1f}" y="{yb}" text-anchor="middle">bust-out day (∞ = never)</text>')
    out.append(f'<text class="n" x="30" y="{yb + 30}">Bazaar engine {version}. Benchmarks: v1 busts out when one day\'s harvest '
               f'exceeds days left × the premium; v2 compares the whole remaining horizon,</text>')
    out.append(f'<text class="n" x="30" y="{yb + 46}">net of expected penalties and closures (privileged catch-rate input). '
               f'Shared count scale (max {ymax}); all genuine stalls in {n_seeds} seeds per panel;</text>')
    out.append(f'<text class="n" x="30" y="{yb + 62}">budget 1.25 × base, tourists 40%, {count} buyers a day, 2 patrolling '
               f'inspectors, 30 days, premium 0.4 (placeholder).</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def report(meta, res, gate, svgs) -> str:
    cal = meta["calibration"]
    L = ["# Counterfeits, budgets and a penalty-aware bust-out rule", "",
         "Run spec \"counterfeits, budgets and a penalty-aware bust-out rule (rule-based only)\"; predictions "
         "written 2026-11-06, before any run.", "", "## Run record", "",
         f"- Engine `{meta['engine_version']}`; commit `{meta['git']['commit']}`; uncommitted at run time: "
         f"{meta['git']['status_porcelain'] or 'none'}",
         f"- Script sha256 `{meta['script_sha256']}`", f"- Command: `{meta['command']}`",
         f"- Tests at the engine commit: {meta.get('tests') or 'not recorded'}",
         f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
         f"- {meta['n_chains']} chains × {DAYS} days on {meta['workers']} workers; wall clock "
         f"{meta['wall_clock_s'] / 60:.1f} min; load average {meta['load_at_start']} at start, {meta['load_at_end']} at end",
         f"- Seeds {meta['seeds'][0]}–{meta['seeds'][-1]}, paired; buyers.count = {meta['count']} (calibrated)",
         "", "## Calibration (seeds 100–104)", "",
         f"Condition: budget 1.25, tourists 40%, fresh reopening, always-honest originals; {cal['meta']['day']} days per "
         f"chain. Smallest count with ≥ {100 * cal['meta']['target']:.0f}% of genuine brands rated at the end of day "
         f"{cal['meta']['day']} (pooled over genuine stalls and seeds), searched in ascending order. Calibration run: "
         f"commit `{cal['meta']['git']['commit']}`, {cal['meta']['wall_clock_s'] / 60:.1f} min.", ""]
    L += _t(["buyers.count", "Rated by day 10", "Share", "Per seed (rated/genuine)"],
            [[str(r["count"]), f"{r['rated']}/{r['genuine']}", f"{100 * r['share']:.1f}%",
              ", ".join(f"{a}/{b}" for a, b in r["per_seed"].values())] for r in cal["table"]])
    L += ["", f"**Chosen: {cal['chosen_count']}.**", "", "## Design (prespecified)", "",
          "- As the 2026-11-06 brands run: ratings public (memory 0.7, skip threshold 0.5; locals and experts see "
          "them); 2 patrolling inspectors, not uniformed; naive deceptive sellers (`rule_deceptive`); 30 days, known to "
          "sellers; imitation off; brands on, premium 0.4 (placeholder). Tourist share 0.4 means 0.4 / 0.3 / 0.3.",
          "- Grid 1: budget factor {1.0, 1.1, 1.25, 1.5} × reopen {fresh, counterfeit}; tourists 40%; always-honest "
          "originals. Grid 2: original policy {rule_genuine, rational v1, rational v2} × reopen; budget 1.25; tourists "
          "40%. Grid 3: tourists {20%, 60%} × reopen; budget 1.25; always-honest. 16 distinct conditions, each run "
          "once; shared cells appear in every grid that uses them.",
          "- `rule_genuine_rational_v2` (decided 2026-11-06, before any run): each morning from day 2 it compares "
          "days left × yesterday's profit with the sum over the remaining days of expected deceptive profit: "
          "yesterday's units at the price its rating would carry after k days of bad reviews (every rated unit "
          "dishonest, so rating × 0.7 a day), minus low-quality unit cost, yesterday's ad spend, expected catches × "
          "penalty, and the margin lost while closed (expected catches × 40/240 of the day). Expected catches = "
          "yesterday's market-wide catches per stall making false claims (deceptive or busted), given to this "
          "policy only, as a labelled privileged input. v1 unchanged.",
          "- Late = mean of days 26–30. Intervals: 95% paired t over seeds, unadjusted. Confirmatory: PF1–PF4. "
          "The v2 − always-honest question is two-sided with no prediction. Everything else is exploratory.",
          "", "## Gate", ""]
    for k, g in gate.items():
        if k != "passed":
            L.append(f"- {g['label']}: **{'passed' if g['passed'] else 'FAILED'}** ({g['detail']})")
    L.append("")
    if res is None:
        return "\n".join(L + ["**Gate failed: results not reported.**", ""])
    dol = _d
    p1, p2, p3, p4, q = res["pf1"], res["pf2"], res["pf3"], res["pf4"], res["q_honesty"]
    bt = res["bust"]
    L += ["## Confirmatory", "",
          f"- **PF1**: per-seed slope of the late counterfeit − fresh gap in profit per deceptive stall over budget "
          f"factors 1.0–1.5: ${_ci(p1, dol)} per +0.1 of budget factor. Prediction > 0. **Verdict: {p1['verdict']}.**",
          f"- **PF2**: that gap at budget 1.5: ${_ci(p2, dol)} per stall per day. Prediction > 0. "
          f"**Verdict: {p2['verdict']}.**",
          f"- **PF3**: late genuine profit per stall, v2 − v1 (fresh reopening): ${_ci(p3, dol)} per day. "
          f"Prediction > 0. **Verdict: {p3['verdict']}.**",
          f"- **PF4**: under v2, mean bust-out day (never = 31), counterfeit − fresh: {_ci(p4, _num(2))} days. "
          f"Prediction < 0. **Verdict: {p4['verdict']}.** Share that bust out: fresh "
          f"{_ci(bt['v2|fresh']['share_bust'], _pct, False)}%, counterfeit "
          f"{_ci(bt['v2|counterfeit']['share_bust'], _pct, False)}%; difference {_ci(bt['v2|share cf-fresh'], _pct)} points.",
          "", "## Two-sided question: is honesty irrational?", "",
          f"Late genuine profit per stall, v2 − always-honest (fresh reopening): ${_ci(q, dol)} per day; "
          f"**{q['direction']}**. With counterfeit reopening (exploratory): ${_ci(res['v2_honest_counterfeit'], dol)}. "
          f"For comparison, v1 − always-honest: fresh ${_ci(res['v1_honest_fresh'], dol)}, counterfeit "
          f"${_ci(res['v1_honest_counterfeit'], dol)}.", "",
          "## Grid 1: counterfeit economics by budget (exploratory beyond PF1–PF2)", ""]
    cf = res["cf_fresh"]
    lt = res["late"]
    L += _t(["Budget", "Deceptive profit: fresh ($)", "counterfeit ($)", "counterfeit − fresh ($)",
             "Genuine profit, cf − fresh ($)", "Shortfall, cf − fresh (pts)", "Surplus, cf − fresh ($)",
             "Genuine brands rated (late), cf − fresh (pts)"],
            [[f"{f:g}×", _ci(lt[f"{cname(f, 'fresh', 't40', 'honest')}|deceptive_profit"], dol, False),
              _ci(lt[f"{cname(f, 'counterfeit', 't40', 'honest')}|deceptive_profit"], dol, False),
              _ci(res["gap_by_budget"][f"{f:g}"], dol), _ci(cf[f"{f:g}|t40|honest|genuine_profit"], dol),
              _ci(cf[f"{f:g}|t40|honest|shortfall_rate"], _pct), _ci(cf[f"{f:g}|t40|honest|surplus"], dol),
              _ci(cf[f"{f:g}|t40|honest|rated_share_genuine"], _pct)] for f in BUDGETS])
    L += ["", f"![counterfeit − fresh gap by budget]({svgs[0]})", "",
          "## Grid 2: bust-out rules (exploratory beyond PF3–PF4)", ""]
    L += _t(["Rule", "Reopen", "Mean bust-out day (never = 31)", "Median (pooled)", "Share bust out (%)",
             "Genuine profit ($)", "Shortfall (%)", "Surplus ($)"],
            [[LABEL[g], LABEL[s], _ci(bt[f"{g}|{s}"]["mean_day"], _num(2), False) if g != "honest" else "–",
              f"{bt[f'{g}|{s}']['median_day_pooled']:g}" if g != "honest" else "–",
              _ci(bt[f"{g}|{s}"]["share_bust"], _pct, False) if g != "honest" else "–",
              _ci(lt[f"{cname(1.25, s, 't40', g)}|genuine_profit"], dol, False),
              _ci(lt[f"{cname(1.25, s, 't40', g)}|shortfall_rate"], _pct, False),
              _ci(lt[f"{cname(1.25, s, 't40', g)}|surplus"], dol, False)] for g in GEN for s in REOPEN])
    pc = res["policy_contrasts"]
    L += ["", "Paired contrasts:", ""]
    L += _t(["Reopen", "Contrast", "Genuine profit ($)", "Deceptive profit ($)", "Shortfall (pts)", "Surplus ($)"],
            [[LABEL[s], f"{LABEL[g]} − rule_genuine", _ci(pc[f"{s}|{g}-honest|genuine_profit"], dol),
              _ci(pc[f"{s}|{g}-honest|deceptive_profit"], dol), _ci(pc[f"{s}|{g}-honest|shortfall_rate"], _pct),
              _ci(pc[f"{s}|{g}-honest|surplus"], dol)] for s in REOPEN for g in ("v1", "v2")]
            + [[LABEL[s], "v2 − v1", _ci(res[f"v2_v1_{s}"], dol), "", "", ""] for s in REOPEN])
    L += ["", "Bust-out timing contrasts (days; share in points):", ""]
    L += _t(["Contrast", "Mean bust-out day", "Share bust out"],
            [["v1: counterfeit − fresh", _ci(bt["v1|cf-fresh"], _num(2)), _ci(bt["v1|share cf-fresh"], _pct)],
             ["v2: counterfeit − fresh", _ci(bt["v2|cf-fresh"], _num(2)), _ci(bt["v2|share cf-fresh"], _pct)],
             ["v2 − v1, fresh", _ci(bt["v2-v1|fresh"], _num(2)), _ci(bt["share v2-v1|fresh"], _pct)],
             ["v2 − v1, counterfeit", _ci(bt["v2-v1|counterfeit"], _num(2)), _ci(bt["share v2-v1|counterfeit"], _pct)]])
    L += ["", f"![bust-out days]({svgs[1]})", "", "## Grid 3: the tourist puzzle (exploratory)", "",
          "Counterfeit − fresh gap in late profit per deceptive stall, by tourist share (budget 1.25, always-honest "
          "originals; the 40% cell is shared with grids 1 and 2):", ""]
    L += _t(["Tourists", "Gap ($/stall/day)", "Genuine profit, cf − fresh ($)", "Shortfall, cf − fresh (pts)",
             "Surplus, cf − fresh ($)"],
            [[LABEL[t], _ci(res["gap_by_tourist"][t], dol), _ci(cf[f"1.25|{t}|honest|genuine_profit"], dol),
              _ci(cf[f"1.25|{t}|honest|shortfall_rate"], _pct), _ci(cf[f"1.25|{t}|honest|surplus"], dol)]
             for t in TOURIST])
    L += ["", f"Slope of the gap: ${_ci(res['gap_tourist_slope'], dol)} per +0.2 of tourist share.", "",
          "Decomposition of deceptive-type stalls' late profit, per stall per day (dollars unless stated), "
          "counterfeit − fresh:", ""]
    dc = res["decomp"]
    rows = []
    for t in TOURIST:
        x = dc[f"{t}|cf-fresh"]
        rows.append([LABEL[t]] + [_ci(x[f"revenue_{p}"], dol) for p in PROFILES]
                    + [_ci(x[k], dol) for k in ("cost_cents_per_stall_day", "ad_spend_cents_per_stall_day",
                                                "penalties_cents_per_stall_day", "profit_cents_per_stall_day")]
                    + [_ci(x["catches_per_stall_day"], _num(2))])
    L += _t(["Tourists", "Revenue: tourists", "locals", "experts", "Unit cost", "Ad spend", "Penalties", "Profit",
             "Catches"], rows)
    L += ["", "Units, prices and reviews (levels; fresh → counterfeit):", ""]
    rows = []
    for t in TOURIST:
        f_, c_ = dc[f"{t}|fresh"], dc[f"{t}|counterfeit"]

        def pr(d, p):
            u, b = d[f"revenue_{p}"]["mean"], d[f"base_value_{p}"]["mean"]
            return f"{u / b:.3f}" if b else "–"
        rows.append([LABEL[t]]
                    + [f"{f_[f'units_{p}']['mean']:.2f} → {c_[f'units_{p}']['mean']:.2f}" for p in PROFILES]
                    + [f"{pr(f_, p)} → {pr(c_, p)}" for p in PROFILES]
                    + [f"{c_[f'cf_units_{p}']['mean']:.2f}" for p in PROFILES]
                    + [f"{f_['misfiled_units_per_stall_day']['mean']:.2f} → {c_['misfiled_units_per_stall_day']['mean']:.2f}",
                       f"{100 * f_['share_low_rated_stall_days']['mean']:.0f} → {100 * c_['share_low_rated_stall_days']['mean']:.0f}"])
    L += _t(["Tourists", "Units: tourists", "locals", "experts", "Price / base: tourists", "locals", "experts",
             "Units under a counterfeit name: tourists", "locals", "experts", "Units reviewed under another name",
             "Stall-days rated < 0.5 (%)"], rows)
    L += ["", "## Share of genuine brands rated over time (exploratory)", ""]
    tr = res["trajectory"]
    L += _t(["Condition", "Day 1", "Day 5", "Day 10", "Day 20", "Day 30"],
            [[c] + [_pct(tr[f"{c}|rated_share_genuine"][d - 1]["mean"]) for d in (1, 5, 10, 20, 30)]
             for c in (cname(*x) for x in CONDS)])
    L += ["", "## Late levels (days 26–30)", ""]

    def g_(c, m, f, signed=False):
        return _ci(lt[f"{c}|{m}"], f, signed)
    L += _t(["Condition", "Deceptive profit ($)", "Genuine profit ($)", "Seconds profit ($)", "Shortfall (%)",
             "Buyer surplus ($)", "Task complete (%)", "Genuine premium (%)", "Rating, genuine (rated)",
             "Genuine rated (%)", "Catches/day", "Renames/day", "Counterfeit stalls", "Busted stalls"],
            [[c, g_(c, "deceptive_profit", dol), g_(c, "genuine_profit", dol), g_(c, "seconds_profit", dol),
              g_(c, "shortfall_rate", _pct), g_(c, "surplus", dol), g_(c, "task_complete", _pct),
              g_(c, "genuine_premium", _pct), g_(c, "rating_genuine", _num(3)), g_(c, "rated_share_genuine", _pct),
              g_(c, "catches", _num(1)), g_(c, "renames", _num(2)), g_(c, "counterfeit_stalls", _num(1)),
              g_(c, "busted", _num(1))] for c in (cname(*x) for x in CONDS)])
    L += ["", "Condition key: budget factor | reopen | tourist share | original policy.", "",
          "## Floors and ceilings", ""] + ([f"- {x}" for x in res["flags"]] or ["- none"])
    L += ["", "## Verdicts", "", "VERDICTS_PLACEHOLDER", "", "## Reading (written after the results)", "",
          "READING_PLACEHOLDER", "", "## Caveats", "", "CAVEATS_PLACEHOLDER", ""]
    return "\n".join(L)


def _write_plots(base, res, n, count, version):
    names = [base + "_gap_by_budget.svg", base + "_bust_days.svg"]
    with open(names[0], "w", encoding="utf-8") as f:
        f.write(plot_gap_svg(res, n, count, version))
    with open(names[1], "w", encoding="utf-8") as f:
        f.write(plot_bust_svg(res, n, count, version))
    return [os.path.basename(x) for x in names]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0-29")
    ap.add_argument("--out", default="runs/counterfeit.json")
    ap.add_argument("--calibrate", action="store_true", help="run the calibration step (seeds 100-104)")
    ap.add_argument("--diagnose", action="store_true", help="why genuine brands stay unrated (calibration seeds)")
    ap.add_argument("--calibration", default="runs/counterfeit_calibration.json")
    ap.add_argument("--tests", default=None, help="test-suite result at the engine commit, for the run record")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--replot", action="store_true", help="redraw the SVGs from --out (.json.gz)")
    a = ap.parse_args(argv)
    if a.calibrate:
        return calibrate(a)
    if a.diagnose:
        return diagnose(a)
    base = a.out[:-5] if a.out.endswith(".json") else a.out
    if a.replot:
        with gzip.open(base + ".json.gz", "rt", encoding="utf-8") as f:
            d = json.load(f)
        print(_write_plots(base, d["results"], len(d["meta"]["seeds"]), d["meta"]["count"], d["meta"]["engine_version"]))
        return 0
    seeds = parse_seeds(a.seeds)
    with open(a.calibration, encoding="utf-8") as f:
        cal = json.load(f)
    if set(seeds) & set(cal["meta"]["seeds"]):
        raise SystemExit("main-run seeds overlap the calibration seeds")
    count = cal["chosen_count"]
    if count is None:
        raise SystemExit("calibration found no count that meets the target; nothing to run")
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
            "command": " ".join([".venv/bin/python -m analysis.counterfeit", *(argv or sys.argv[1:])]),
            "tests": a.tests, "load_at_start": _load(), "python": platform.python_version(), "numpy": np.__version__,
            "platform": platform.platform(), "workers": a.workers, "seeds": seeds, "days": DAYS, "count": count,
            "conditions": [cname(*c) for c in CONDS], "calibration": cal}
    jobs = [(*c, sd, count) for sd in seeds for c in CONDS]
    t0 = time.time()
    runs = []
    with ProcessPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(_job, jobs)):
            runs.append(r)
            if (i + 1) % len(CONDS) == 0:
                print(f"{i + 1}/{len(jobs)} chains, {time.time() - t0:.0f} s, load {_load()}", flush=True)
    meta.update(wall_clock_s=time.time() - t0, load_at_end=_load(), n_chains=len(runs))
    pos = {s: i for i, s in enumerate(seeds)}
    v = {cname(*c): [None] * len(seeds) for c in CONDS}
    for r in runs:
        v[r["cond"]][pos[r["seed"]]] = r
    calr = v[cname(*CAL_COND)]
    rated = sum(round(r["days"][CAL_DAY - 1]["rated_share_genuine"] * r["n_genuine"]) for r in calr)
    tot = sum(r["n_genuine"] for r in calr)
    gate = {"calibration": {"label": f"Calibration met on the main run: >= 80% of genuine brands rated by day {CAL_DAY} "
                                     f"(budget 1.25, tourists 40%, fresh, always-honest)",
                            "passed": rated / tot >= CAL_TARGET,
                            "detail": f"{rated}/{tot} = {rated / tot:.1%} over {len(calr)} seeds"},
            "tests": {"label": "Defaults reproduce 0.8.0 (test suite)", "passed": bool(a.tests) and "failed" not in a.tests,
                      "detail": a.tests or "not recorded"}}
    gate["passed"] = all(g["passed"] for k, g in gate.items() if k != "passed")
    res = analyse(v) if gate["passed"] else None
    with gzip.open(base + ".json.gz", "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "gate": gate, "results": res, "runs": runs}, f, sort_keys=True, separators=(",", ":"))
    with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["budget_factor", "reopen", "tourists", "original_policy", "seed", "day"] + SERIES)
        for r in runs:
            for d, x in enumerate(r["days"], start=1):
                w.writerow(r["cond"].split("|") + [r["seed"], d] + [x[m] for m in SERIES])
    svgs = _write_plots(base, res, len(seeds), count, ENGINE_VERSION) if res is not None else ["", ""]
    with open(base + "_summary.md", "w", encoding="utf-8") as f:
        f.write(report(meta, res, gate, svgs))
    print(f"gate passed: {gate['passed']}; {gate}; wrote {base}.json.gz, {base}.csv, {base}_summary.md")
    return 0 if gate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
