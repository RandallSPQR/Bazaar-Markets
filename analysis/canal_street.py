"""Run 1: Canal Street (rule-based only). Spec "Canal Street" (2026-11-12); predictions written 2026-11-12, before
any run. Prepared, not launched: the pilot gate (analysis/pilot_canal_equity.py, runs/pilot_canal_equity.md) gives
the projected wall clock; runs/queue_canal_then_equity.sh launches this run, then Brand Equity.

Question: do counterfeits pay once they undercut the original, and what do they cost the original?

Engine 0.17.0. Market as the licensing run (analysis/licensing.py): choice-set demand (m 3, gamma 0), 150 buyers,
budget 1.25 x base, bargain hunters 0.2 (Q_req 0.15-0.40), D = 30 known, ratings public (memory 0.7), brands on
(premium 0.4), naive deceptive sellers (rule_deceptive, fresh reopening), 2 patrolling inspectors not uniformed,
collectible fines (penalty lag 0, no exit), every genuine stall honest (rule_genuine_bust_at with nothing
scheduled, as the licensing never chain). Licensing off.

Conditions: counterfeits {off; on with phi in {1.0, 0.8, 0.6, 0.4}} x verification {t40: tourist share 0.4 with
locals inspecting; t100: tourist share 1.0} x detect_scale {0, 1}. "off" is the licensing run's never chain:
deceptive stalls keep their own names apart from fresh renames at reopening. "on": brands.counterfeit_entry "day",
counterfeit_day 2 (every deceptive stall copies the top-rated genuine brand of its category at the start of day 2,
claims its quality, keeps the name to day 30, never renames), brands.counterfeit_price_factor phi. Seeds 270-299
(30), paired across all conditions.

Outcomes (30-day totals; also days 21-30): profit per deceptive stall; gap = counterfeit-on - off, per deceptive
stall; for each copied original (a genuine stall copied by at least one counterfeit), its rating at the end of days
10, 20, 30 (unrated = 0.5) and its 30-day profit, on - off (the same stall in the off chain); catches; shortfall
and surplus by buyer profile; price and margin of counterfeits.

Predictions (fixed 2026-11-12, before any run):
  PK1 (confirmatory): tourist share 1.0, detect_scale 1: the gap rises as the price falls. Least-squares slope of
      the gap over (1 - phi), phi in {1.0, 0.8, 0.6, 0.4}, > 0.
  PK2 (confirmatory): tourist share 1.0, detect_scale 1, phi 1.0: gap < 0 (copying the original's price loses, as
      in walk mode).
  PK3 (confirmatory): tourist share 1.0, detect_scale 1, phi 0.6: copied originals' day-30 rating, on - off, < 0.
  PK4 (exploratory): locals inspecting shrinks the gap: gap at t40 < gap at t100 at each phi.
  PK5 (exploratory): the original's 30-day profit, on - off, at each phi; no direction predicted.
Analysis: per seed the mean over deceptive stalls (gap) or copied originals (rating, profit); mean and 95% t over
seeds; unadjusted. PK1: the slope is fitted per seed (least squares over the four phi), then mean and 95% t over
seeds. Primary window: 30-day totals; days 21-30 reported alongside.

    .venv/bin/python -m analysis.canal_street --seeds 270-299 --tests "..."                      # main run
    .venv/bin/python -m analysis.canal_street --pilot --seeds 900-902 --outdir runs/pilot_canal   # pilot
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import platform
import sys
import time

import numpy as np

import analysis.chainrun as CR
import analysis.liability as LB
import analysis.licensing as L
from analysis.capture import PROFILES, ProfileTap, _window, memory_state
from analysis.counterfeit import _ci, _d, _git, _load, _num, _t, _verdict
from cli.sweep import parse_seeds
from engine import ENGINE_VERSION, benchmark
from engine.config import load
from engine.jsonlog import dumps
from engine.metrics import mean_ci, paired_diff

DAYS = 30
NEVER = benchmark.NEVER
PHIS = (1.0, 0.8, 0.6, 0.4)
ARMS = ("off", *[f"phi{p!r}" for p in PHIS])
VERS = ("t40", "t100")
DSS = (0.0, 1.0)
CONDS = [f"{arm}|{t}|ds{ds!r}" for arm in ARMS for t in VERS for ds in DSS]
MAIN_SEEDS = set(range(270, 300))
PILOT_SEEDS = set(range(900, 903))
LATE = range(21, DAYS + 1)
RATING_DAYS = (10, 20, 30)
VLAB = {"t40": "tourist share 0.4, locals inspect", "t100": "tourist share 1.0"}
PREDICTIONS = [
    "PK1 (confirmatory): tourist share 1.0, detect_scale 1: the gap rises as the price falls. Least-squares slope of "
    "the gap over (1 − φ), φ ∈ {1.0, 0.8, 0.6, 0.4}, > 0.",
    "PK2 (confirmatory): tourist share 1.0, detect_scale 1, φ 1.0: gap < 0 (copying the original's price loses, as "
    "in walk mode).",
    "PK3 (confirmatory): tourist share 1.0, detect_scale 1, φ 0.6: copied originals' day-30 rating, on − off, < 0.",
    "PK4 (exploratory): locals inspecting shrinks the gap: gap at t40 < gap at t100 at each φ.",
    "PK5 (exploratory): the original's 30-day profit, on − off, at each φ; no direction predicted.",
]


def parts(cond: str):
    arm, t, d = cond.split("|")
    return arm, t, float(d[2:])


def phi_of(arm: str):
    return None if arm == "off" else float(arm[3:])


def overrides(cond: str) -> list[str]:
    arm, t, ds = parts(cond)
    ov = L.overrides(t, ds)                    # the licensing run's market (licensing dials inert: no schedule)
    if arm != "off":
        ov += ["brands.counterfeit_entry=day", "brands.counterfeit_day=2",
               f"brands.counterfeit_price_factor={phi_of(arm)!r}"]
    return ov


def config(cond: str, seed: int):
    return benchmark.licence_config(load(None, [*overrides(cond), f"seed={seed}"], mode="bazaar"), None, NEVER)


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ chains (job = (cond, seed))

def key(j) -> str:
    return f"{j[0]}|{j[1]}"


def job(j) -> dict:
    cond, seed = j
    LB._observe()
    LB._PARKED.clear()
    tap = ProfileTap([])
    out, snaps, bad = CR.run_with_ledger(config(cond, seed), log=tap)
    sids = sorted(snaps[0])
    day1 = snaps[0]
    st = {s: {"stype": day1[s]["stype"], "category": day1[s]["category"]} for s in sids}
    series = {f: {s: [snaps[d][s][f] for d in range(DAYS)] for s in sids}
              for f in ("units", "revenue", "cost", "fines", "catches", "profit", "price", "unit_cost")}
    genuine = [s for s in sids if st[s]["stype"] == "genuine"]
    rating = {s: [out["days"][d]["brand_ratings"].get(out["days"][d]["brands"][s]) for d in range(DAYS)]
              for s in genuine}
    cf = {s: snaps[-1][s]["counterfeit_of"] for s in sids if snaps[-1][s]["counterfeit_of"] is not None}
    holder = {snaps[0][s]["brand"]: s for s in genuine}
    copied = {s: holder.get(o) for s, o in cf.items()}          # counterfeit -> original stall
    cf_fixed_ok = all(snaps[d][s]["counterfeit_of"] == cf[s] and snaps[d][s]["brand"] == snaps[1][s]["brand"]
                      for s in cf for d in range(1, DAYS))
    below = [out["days"][d].get("counterfeit_below_cost", 0) for d in range(DAYS)]
    renames = [out["days"][d]["outcome"]["brands"]["renames"] for d in range(DAYS)]
    return {"key": key(j), "cond": cond, "seed": seed, "stalls": st, "series": series, "rating": rating,
            "counterfeit_of": cf, "copied": copied, "cf_fixed_ok": cf_fixed_ok, "below_cost": below,
            "renames": renames, "profit_mismatch": bad,
            "digest": hashlib.sha256(dumps(out).encode()).hexdigest(),
            "profile": {str(k): v for k, v in sorted(tap.days.items())}, "guard": CR.guard(out),
            "catches": [out["days"][d]["outcome"]["catches"] for d in range(DAYS)]}


def jobs_for(seeds) -> list[tuple]:
    return [(c, sd) for sd in seeds for c in CONDS]


# ------------------------------------------------------------------ analysis

def _sum(xs, days) -> int:
    return int(sum(xs[d - 1] for d in days))


def _r(x):
    return 0.5 if x is None else x


def analyse(runs, seeds) -> dict:
    idx = {(r["cond"], r["seed"]): r for r in runs}
    res: dict = {"seeds": seeds, "cells": {}, "pred": {}, "guard": {}, "flags": []}
    win = {"30": range(1, DAYS + 1), "late": LATE}
    for t in VERS:
        for ds in DSS:
            base = f"off|{t}|ds{ds!r}"
            cell = {}
            for arm in ARMS:
                cond = f"{arm}|{t}|ds{ds!r}"
                per = {k: [] for k in ("dec_profit_30", "dec_profit_late", "gap_30", "gap_late", "orig_profit_30",
                                       "orig_profit_late", "catches", "catches_off", "dec_catches",
                                       "cf_price", "cf_margin", "cf_units_per_day", "cf_below_share", "n_copied",
                                       *[f"orig_rating_{d}" for d in RATING_DAYS],
                                       *[f"orig_rating_{d}_level" for d in RATING_DAYS])}
                prof = {p: {"short": [], "surplus": []} for p in PROFILES}
                for sd in seeds:
                    r, o = idx[(cond, sd)], idx[(base, sd)]
                    dec = [s for s, v in r["stalls"].items() if v["stype"] == "deceptive"]
                    P, PO = r["series"]["profit"], o["series"]["profit"]
                    for w, days in win.items():
                        per[f"dec_profit_{w}"].append(float(np.mean([_sum(P[s], days) for s in dec])))
                        per[f"gap_{w}"].append(float(np.mean([_sum(P[s], days) - _sum(PO[s], days) for s in dec])))
                    per["catches"].append(sum(r["catches"]))
                    per["catches_off"].append(sum(o["catches"]))
                    per["dec_catches"].append(float(np.mean([sum(r["series"]["catches"][s]) for s in dec])))
                    if arm != "off":
                        orig = sorted({x for x in r["copied"].values() if x is not None})
                        per["n_copied"].append(len(orig))
                        for w, days in win.items():
                            per[f"orig_profit_{w}"].append(float(np.mean([_sum(P[s], days) - _sum(PO[s], days)
                                                                          for s in orig])))
                        for d in RATING_DAYS:
                            per[f"orig_rating_{d}"].append(float(np.mean([_r(r["rating"][s][d - 1]) - _r(o["rating"][s][d - 1])
                                                                          for s in orig])))
                            per[f"orig_rating_{d}_level"].append(float(np.mean([_r(r["rating"][s][d - 1]) for s in orig])))
                        cfs = list(r["counterfeit_of"])
                        pr = [r["series"]["price"][s][d] for s in cfs for d in range(1, DAYS)]
                        uc = [r["series"]["unit_cost"][s][d] for s in cfs for d in range(1, DAYS)]
                        un = [r["series"]["units"][s][d] for s in cfs for d in range(1, DAYS)]
                        per["cf_price"].append(float(np.mean(pr)))
                        per["cf_margin"].append(float(np.mean([p - c for p, c in zip(pr, uc)])))
                        per["cf_units_per_day"].append(float(np.mean(un)))
                        per["cf_below_share"].append(sum(r["below_cost"]) / max(1, len(pr)))
                    wr, wo = _window(r["profile"], range(1, DAYS + 1)), _window(o["profile"], range(1, DAYS + 1))
                    for p in PROFILES:
                        for k in ("short", "surplus"):
                            a_, b_ = wr[k][p], wo[k][p]
                            prof[p][k].append(None if a_ is None or b_ is None else a_ - b_)
                cell[arm] = {k: mean_ci(v) for k, v in per.items() if v}
                cell[arm]["per_seed"] = per
                cell[arm]["profile"] = {p: {k: mean_ci(prof[p][k]) for k in ("short", "surplus")} for p in PROFILES}
            # least-squares slope of the gap over (1 - phi), per seed
            x = np.array([1 - p for p in PHIS])
            for w in ("30", "late"):
                ys = np.array([cell[f"phi{p!r}"]["per_seed"][f"gap_{w}"] for p in PHIS])   # (phi, seed)
                slopes = [float(np.polyfit(x, ys[:, i], 1)[0]) for i in range(ys.shape[1])]
                cell[f"slope_{w}"] = {**mean_ci(slopes), "per_seed": slopes}
            res["cells"][f"{t}|ds{ds!r}"] = cell
    c = res["cells"]["t100|ds1.0"]
    for w, tag in (("30", ""), ("late", " (days 21–30)")):
        P = {}
        P["PK1"] = {**{k: c[f"slope_{w}"][k] for k in ("n", "mean", "lo", "hi")}, "sign": +1,
                    "label": f"t100, ds 1: slope of the gap over (1 − φ){tag}", "unit": "$ per unit of 1 − φ"}
        P["PK2"] = {**c["phi1.0"][f"gap_{w}"], "sign": -1, "label": f"t100, ds 1, φ 1.0: gap{tag}", "unit": "$"}
        if w == "30":
            P["PK3"] = {**c["phi0.6"][f"orig_rating_{RATING_DAYS[-1]}"], "sign": -1,
                        "label": "t100, ds 1, φ 0.6: copied originals' day-30 rating, on − off", "unit": "rating"}
        for ds in DSS:
            for p in PHIS:
                a40 = res["cells"][f"t40|ds{ds!r}"][f"phi{p!r}"]["per_seed"][f"gap_{w}"]
                a100 = res["cells"][f"t100|ds{ds!r}"][f"phi{p!r}"]["per_seed"][f"gap_{w}"]
                P[f"PK4 ds{ds:g} φ{p:g}"] = {**paired_diff(a100, a40), "sign": -1, "unit": "$",
                                             "label": f"ds {ds:g}, φ {p:g}: gap at t40 − gap at t100{tag} (exploratory)"}
        for p in PHIS:
            P[f"PK5 φ{p:g}"] = {**c[f"phi{p!r}"][f"orig_profit_{w}"], "sign": 0, "unit": "$",
                                "label": f"t100, ds 1, φ {p:g}: originals' profit, on − off{tag} (exploratory, no direction)"}
        for v in P.values():
            v["verdict"] = _verdict(v, v["sign"]) if v["sign"] else (
                "interval excludes 0" if v.get("lo") is not None and (v["lo"] > 0 or v["hi"] < 0) else "interval includes 0")
        res["pred"][w] = P
    # guard, invalid actions, identities and counterfeit checks
    for cond in CONDS:
        rs = [idx[(cond, sd)] for sd in seeds]
        g = {k: sum(r["guard"][k] for r in rs) for k in ("stuck_buyers", "idle_choosers", "parked", "buyer_days",
                                                        "fallbacks")}
        g["chains"] = len(rs)
        g["profit_mismatch"] = sum(r["profit_mismatch"] for r in rs)
        res["guard"][cond] = g
        if g["stuck_buyers"] or g["parked"] or g["idle_choosers"]:
            res["flags"].append(f"{cond}: stuck {g['stuck_buyers']}, parked {g['parked']}, idle {g['idle_choosers']}")
        if g["fallbacks"]:
            res["flags"].append(f"{cond}: {g['fallbacks']} invalid actions (fallbacks)")
        if g["profit_mismatch"]:
            res["flags"].append(f"{cond}: {g['profit_mismatch']} stall-days where the observer's profit differs")
        arm = parts(cond)[0]
        for r in rs:
            dec = {s for s, v in r["stalls"].items() if v["stype"] == "deceptive"}
            if arm == "off":
                if r["counterfeit_of"]:
                    res["flags"].append(f"{r['key']}: counterfeits in an off chain")
            else:
                if set(r["counterfeit_of"]) != dec or not r["cf_fixed_ok"] or any(r["renames"][1:]) \
                        or any(v is None for v in r["copied"].values()):
                    res["flags"].append(f"{r['key']}: counterfeit set, name or rename check failed")
    return res


# ------------------------------------------------------------------ report

def _cl(cell: str) -> str:
    t, d = cell.split("|")
    return f"{t}, ds {float(d[2:]):g}"


def _al(arm: str) -> str:
    return "off" if arm == "off" else f"φ {phi_of(arm):g}"


def report(res: dict, meta: dict, old: str | None) -> str:
    L_ = ["# Canal Street: counterfeits that undercut the original", "",
          "Spec \"Canal Street\" (2026-11-12); predictions fixed 2026-11-12, before any run. Pilot gate: "
          "`runs/pilot_canal_equity.md`.", "",
          "## Design (prespecified)", "",
          "- Question: do counterfeits pay once they undercut the original, and what do they cost the original?",
          "- Engine 0.17.0. Market as the licensing run: choice-set demand (m 3, gamma 0), 150 buyers, budget 1.25 × "
          "base, bargain hunters 0.2 (Q_req 0.15–0.40); D = 30 known; ratings public (memory 0.7); brands on (premium "
          "0.4); naive deceptive sellers (fresh reopening); 2 patrolling inspectors, not uniformed; collectible fines; "
          "every genuine stall honest. Licensing off.",
          "- Conditions: counterfeits {off (deceptive stalls keep their own names; the licensing run's never chain, "
          "fresh renames at reopening included), on: φ ∈ {1.0, 0.8, 0.6, 0.4}} × verification {tourist share 0.4 with "
          "locals inspecting; tourist share 1.0} × detect_scale {0, 1}. Entry \"day\", day 2: every deceptive stall "
          "copies the name of the top-rated genuine brand of its category (ratings at the end of day 1; ties from "
          "`default_rng([seed, 23])`), claims its quality, keeps the name to day 30, is never offered a rename, and "
          "posts φ × the original's price.",
          "- Outcomes (30-day totals; also days 21–30): profit per deceptive stall; gap = counterfeit-on − off, per "
          "deceptive stall; for each copied original, its rating on days 10, 20, 30 and its 30-day profit, on − off "
          "(the same stall in the off chain); catches; shortfall and surplus by buyer profile; price and margin of "
          "counterfeits.",
          "- Predictions (verbatim from the spec):", *[f"  - {p}" for p in PREDICTIONS],
          "- Analysis: per seed the mean over deceptive stalls (gap) or copied originals (rating, profit); mean and 95% "
          "t over seeds; unadjusted. PK1's slope is fitted per seed, then averaged.", ""]
    L_ += ["## Run record", "",
           f"- Engine `{meta['engine_version']}`; commit `{meta['git']['commit']}`; uncommitted at run time: "
           f"{meta['git']['status_porcelain'] or 'none'}",
           f"- Script sha256 `{meta['script_sha256']}`",
           f"- Command: `{meta['command']}`",
           f"- Tests: {meta['tests']}",
           f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
           f"- {meta['chains']} chains × {DAYS} days on {meta['workers']} workers (nice 19); wall clock "
           f"{meta['wall_h']:.2f} h; load average {meta['load_start']} at start, {meta['load_end']} at end; memory at "
           f"start {meta['mem_start']}, at end {meta['mem_end']}; memory-guard pauses: {meta['pauses']}",
           f"- Seeds {meta['seeds_txt']} ({len(res['seeds'])}), paired across all conditions", ""]
    L_ += ["## Gate", "", meta.get("gate", "Pilot gate: see `runs/pilot_canal_equity.md`."), ""]
    for w, head in (("30", "30-day totals (primary)"), ("late", "days 21–30")):
        P = res["pred"][w]
        L_ += [f"## Predictions: {head}", "",
               *_t(["Prediction", "Estimate", "Verdict"],
                   [[f"**{k}**: {v['label']}",
                     _ci(v, (lambda x, s: _num(3)(x, s)) if v["unit"] == "rating" else _d), v["verdict"]]
                    for k, v in P.items()]), ""]
    L_ += ["## Deceptive stalls by condition", "",
           "Per deceptive stall, $. Gap = on − off (same stall, same seed).", ""]
    rows = []
    for cell, C in res["cells"].items():
        for arm in ARMS:
            v = C[arm]
            rows.append([_cl(cell), _al(arm), _ci(v["dec_profit_30"], _d), _ci(v["gap_30"], _d) if arm != "off" else "–",
                         _ci(v["dec_profit_late"], _d), _ci(v["gap_late"], _d) if arm != "off" else "–",
                         _ci(v["dec_catches"], _num(1), signed=False)])
        rows.append([_cl(cell), "slope over 1 − φ", "", _ci(C["slope_30"], _d), "", _ci(C["slope_late"], _d), ""])
    L_ += [*_t(["Cell", "Arm", "Profit, 30 days", "Gap, 30 days", "Profit, days 21–30", "Gap, days 21–30",
                "Catches per stall"], rows), ""]
    L_ += ["## Copied originals", "",
           "Per seed the mean over the genuine stalls copied by at least one counterfeit; on − off. Rating unrated = 0.5.",
           ""]
    rows = []
    for cell, C in res["cells"].items():
        for arm in ARMS[1:]:
            v = C[arm]
            rows.append([_cl(cell), _al(arm), _ci(v["n_copied"], _num(1), signed=False),
                         *[_ci(v[f"orig_rating_{d}"], _num(3)) for d in RATING_DAYS],
                         _ci(v[f"orig_rating_{RATING_DAYS[-1]}_level"], _num(3), signed=False),
                         _ci(v["orig_profit_30"], _d), _ci(v["orig_profit_late"], _d)])
    L_ += [*_t(["Cell", "Arm", "Originals copied", "Rating day 10", "Rating day 20", "Rating day 30",
                "Rating day 30 (on, level)", "Profit, 30 days ($)", "Profit, days 21–30 ($)"], rows), ""]
    L_ += ["## Counterfeit prices and sales", "",
           "Days 2–30, per counterfeit stall-day; margin = price − unit cost. Below cost: share of stall-days priced "
           "below unit cost.", ""]
    rows = []
    for cell, C in res["cells"].items():
        for arm in ARMS[1:]:
            v = C[arm]
            rows.append([_cl(cell), _al(arm), _ci(v["cf_price"], _d, signed=False), _ci(v["cf_margin"], _d),
                         _ci(v["cf_units_per_day"], _num(2), signed=False),
                         _ci(v["cf_below_share"], lambda x, s: _num(1)(100 * x, s), signed=False)])
    L_ += [*_t(["Cell", "Arm", "Price ($)", "Margin ($)", "Units per stall-day", "Below cost (%)"], rows), ""]
    L_ += ["## Catches and buyers", "",
           "Catches: market total over 30 days. Shortfall (points of purchases) and surplus ($ per buyer), on − off, "
           "30 days.", ""]
    rows = []
    for cell, C in res["cells"].items():
        for arm in ARMS:
            v = C[arm]
            rows.append([_cl(cell), _al(arm), _ci(v["catches"], _num(0), signed=False),
                         *[_ci(v["profile"][p]["short"], lambda x, s: _num(1)(100 * x, s)) if arm != "off" else "–"
                           for p in PROFILES],
                         *[_ci(v["profile"][p]["surplus"], _d) if arm != "off" else "–" for p in PROFILES]])
    L_ += [*_t(["Cell", "Arm", "Catches", *[f"{p}: shortfall (pts)" for p in PROFILES],
                *[f"{p}: surplus ($)" for p in PROFILES]], rows), ""]
    L_ += ["## Stuck, parked and idle buyers", "",
           *_t(["Condition", "Chains", "Buyer-days", "Stuck", "Parked", "Idle choosers", "Invalid actions"],
               [[c.replace("|", " · "), str(g["chains"]), f"{g['buyer_days']:,}", str(g["stuck_buyers"]), str(g["parked"]),
                 str(g["idle_choosers"]), str(g["fallbacks"])] for c, g in res["guard"].items()]), "",
           "## Flags", "", *([f"- {f}" for f in res["flags"]] or ["- none"]), ""]
    reading, caveats = "READING_PLACEHOLDER", "CAVEATS_PLACEHOLDER"
    if old:
        if "## Reading (written after the results)\n\n" in old:
            reading = old.split("## Reading (written after the results)\n\n", 1)[1].split("\n\n## Caveats", 1)[0]
        if "## Caveats\n\n" in old:
            caveats = old.split("## Caveats\n\n", 1)[1].rstrip()
    L_ += ["## Reading (written after the results)", "", reading, "", "## Caveats", "", caveats, ""]
    return "\n".join(L_)


# ------------------------------------------------------------------ main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="270-299")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--outdir", default="runs")
    ap.add_argument("--tests", default="")
    ap.add_argument("--gate", default="")
    ap.add_argument("--min-swap-mb", type=float, default=512)
    ap.add_argument("--min-free-pct", type=float, default=15)
    ap.add_argument("--pilot", action="store_true", help="pilot seeds 900-902 into an --outdir other than runs")
    a = ap.parse_args(argv)
    seeds = parse_seeds(a.seeds)
    LB._lower_priority()
    if a.pilot:
        if not set(seeds) <= PILOT_SEEDS or os.path.abspath(a.outdir) == os.path.abspath("runs"):
            raise SystemExit("--pilot uses seeds 900-902 and an outdir other than runs")
    elif not set(seeds) <= MAIN_SEEDS:
        raise SystemExit("the main run uses seeds 270-299 only")
    os.makedirs(a.outdir, exist_ok=True)
    log = CR.file_logger(os.path.join(a.outdir, "canal_street_run.log"))
    t0 = time.time()
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
            "command": " ".join(["python -m analysis.canal_street", *sys.argv[1:]]), "tests": a.tests,
            "gate": a.gate or "Pilot gate: see `runs/pilot_canal_equity.md`.",
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
            "workers": a.workers, "load_start": _load(), "mem_start": memory_state(), "seeds_txt": a.seeds}
    log(f"canal street: engine {ENGINE_VERSION}, commit {meta['git']['commit'][:7]}, seeds {a.seeds}, "
        f"{len(CONDS)} conditions")
    runs, pauses = CR.run_chains(a, jobs_for(seeds), os.path.join(a.outdir, "canal_street_cache.jsonl"), log, job, key)
    res = analyse(runs, seeds)
    meta.update(chains=len(runs), pauses=pauses, wall_h=(time.time() - t0) / 3600, load_end=_load(),
                mem_end=memory_state())
    with gzip.open(os.path.join(a.outdir, "canal_street.json.gz"), "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": {k: v for k, v in res.items()}}, f, separators=(",", ":"))
    with open(os.path.join(a.outdir, "canal_street.csv"), "w", encoding="utf-8") as f:
        f.write("verification,detect_scale,arm,seed,dec_profit_30_cents,gap_30_cents,dec_profit_late_cents,"
                "gap_late_cents,orig_rating_30_on_minus_off,orig_profit_30_cents,cf_price_cents,cf_margin_cents\n")
        for cell, C in res["cells"].items():
            t, d = cell.split("|")
            for arm in ARMS:
                ps = C[arm]["per_seed"]
                for i, sd in enumerate(seeds):
                    g = lambda k: (f"{ps[k][i]:.4f}" if ps.get(k) else "")
                    f.write(",".join([t, d[2:], arm, str(sd), g("dec_profit_30"), g("gap_30"), g("dec_profit_late"),
                                      g("gap_late"), g(f"orig_rating_{RATING_DAYS[-1]}"), g("orig_profit_30"), g("cf_price"),
                                      g("cf_margin")]) + "\n")
    sp = os.path.join(a.outdir, "canal_street_summary.md")
    old = open(sp, encoding="utf-8").read() if os.path.exists(sp) else None
    with open(sp, "w", encoding="utf-8") as f:
        f.write(report(res, meta, old))
    log(f"done; {len(res['flags'])} flags; wall {meta['wall_h']:.2f} h")
    return 2 if res["flags"] else 0          # flags stop the queue before Brand Equity


if __name__ == "__main__":
    raise SystemExit(main())
