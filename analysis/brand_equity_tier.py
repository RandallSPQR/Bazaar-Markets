"""Brand Equity at the genuine tier, with rating speed (rule-based only). Spec: the plan in
runs/plan_brand_equity_tier.md (2026-11-13) and the addendum "rating speed as a factor" (2026-11-16); predictions
fixed 2026-11-16, before any run. Prepared by the pilot gate (analysis/pilot_brand_equity_tier.py,
runs/pilot_brand_equity_tier.md); levels chosen by the calibration (analysis/calibrate_rating_speed.py,
runs/calibration_rating_speed.md) before any main run.

Question: what does a reputation earn once the white label may price like the owner (genuine tier), and does it
earn more when reputations form slowly?

Engine 0.18.0. Market, owners and licence option as Brand Equity (analysis/brand_equity.py): the licensing market,
detect_scale 1, owner not liable; 3 owners per seed from default_rng([seed, 17]); N 6 from day 10, royalty 0.10.
Arms per owner: never; R = licensees under the owner's brand; W_g = the same stalls under white labels priced at
the genuine tier (licensing.white_label_tier "genuine"); W_t = white labels at their stall type's tier (the 0.17.0
W). Rating speed = ratings.prior_n (pseudo-reviews at 0.5 fading at the memory rate), three levels chosen by the
calibration to give about 1 (the current market, prior_n 0), 5 and 15 days for a fresh contract white label to
reach a 0.9 rating.
  Current speed: never, R, W_g, W_t x {contract, cheap} x {t40, t100}.
  Slow speeds (5 and 15 days): never, R, W_g x contract x {t40, t100}.
  (The 5-day level was cut by the timing gate; PR1 and PR4 slopes are then over the two remaining levels.)
Seeds 300-329 (30), paired; everything rerun at 0.18.0. Extra gate: at current speed, never, R and W_t equal the
0.17.0 Brand Equity chains (runs/brand_equity_cache.jsonl) to the cent and by full-outcome digest.

Measures, per owner, J = owner profit + its 6 licensees' profit, days 10-30 (royalties cancel):
  reputation effect = J(R) - J(W_g), split as in Brand Equity (owner own sales, licensee sales, licensee prices,
  licensee ad spend, fines); tier effect = J(W_g) - J(W_t) (current speed only); the 0.17.0 name effect
  J(R) - J(W_t) = reputation + tier; composition = J(W_g) - J(never). Each effect is compared within its own
  speed. Never chains across speeds are reported (the dial changes every brand's rating, deceptive stalls'
  included). Owner's gain (30-day profit - never at the same speed) at royalty 0.05-0.25 by the exact recompute,
  after the no-decision check (current speed: seed 300, t100, both qualities; slowest speed: contract).

Predictions (fixed 2026-11-16, before any run; verbatim):
  PR1 (confirmatory): contract, t40: the reputation effect rises with time to reputation. Slope of R - W_g over
      days-to-0.9 (three levels) > 0.
  PR2 (confirmatory): contract, t40, current speed: reputation effect < tier effect.
  PR3 (exploratory): at the slowest speed, the reputation effect at t40 - at t100 > 0 (buyers who read ratings
      become the channel once reputations are slow).
  PR4 (exploratory): the owner's gain at royalty 0.10 rises with time to reputation.
Analysis: per seed the mean over 3 owners; mean and 95% t over seeds; unadjusted. Slopes (PR1, PR4) are fitted
per seed by least squares over the levels' days-to-0.9 from the calibration (fixed before the run), then
averaged; PR4 is evaluated in contract at t40 and at t100.

    .venv/bin/python -m analysis.brand_equity_tier --seeds 300-329 --tests "..."                          # main run
    .venv/bin/python -m analysis.brand_equity_tier --pilot --seeds 900-902 --outdir runs/pilot_brand_equity_tier/run
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

import analysis.brand_equity as E
import analysis.chainrun as CR
import analysis.liability as LB
import analysis.licensing as L
from analysis.capture import PROFILES, ProfileTap, _window, memory_state
from analysis.counterfeit import _ci, _d, _git, _load, _num, _t, _verdict
from cli.sweep import parse_seeds
from engine import ENGINE_VERSION, benchmark
from engine.bazaar import BazaarEngine
from engine.config import load
from engine.jsonlog import dumps
from engine.metrics import mean_ci, paired_diff

DAYS, N_LIC, B_DAY, ROYALTY = E.DAYS, E.N_LIC, E.B_DAY, E.ROYALTY
RATES, QUALS, VERS, WINDOW = E.RATES, E.QUALS, E.VERS, E.WINDOW
NEVER = benchmark.NEVER
MAIN_SEEDS = set(range(300, 330))
PILOT_SEEDS = set(range(900, 903))
CHECK_RATES = (0.05, 0.25)
TARGET = 0.9
# Rating-speed levels: label -> ratings.prior_n. Set from the calibration (runs/calibration_rating_speed.md) before
# any main run; DAYS_TO_TARGET holds the calibration's days for a fresh contract white label to reach 0.9 (t40),
# the x of the PR1 and PR4 slopes.
# The 5-day level (prior_n 2.5, 4.78 days) was cut by the timing gate (projected 6.10 h with it, 4.82 h without;
# runs/pilot_brand_equity_tier.md), as the spec directs: cut the 5-day level before cutting seeds.
LEVELS: dict[str, float] = {"current": 0.0, "slow15": 50.0}
DAYS_TO_TARGET: dict[str, float] = {"current": 1.04, "slow15": 14.91}
CURRENT = "current"
PREDICTIONS = [
    "PR1 (confirmatory): contract, t40: the reputation effect rises with time to reputation. Slope of R − W_g over "
    "days-to-0.9 (three levels) > 0.",
    "PR2 (confirmatory): contract, t40, current speed: reputation effect < tier effect.",
    "PR3 (exploratory): at the slowest speed, the reputation effect at t40 − at t100 > 0 (buyers who read ratings "
    "become the channel once reputations are slow).",
    "PR4 (exploratory): the owner's gain at royalty 0.10 rises with time to reputation.",
]
SPLIT, SPLIT_LAB = E.SPLIT, E.SPLIT_LAB
STYPES = ("genuine", "seconds", "deceptive")


def _rk(r) -> str:
    return f"{float(r):.2f}"


def _pk(pn) -> str:
    return f"{float(pn):g}"


def config(arm, quality, t, seed, owner, r=ROYALTY, prior_n=0.0):
    """arm: "never" | "R" | "Wg" | "Wt"."""
    q = "cheap" if arm == "never" else quality
    ov = [*L.overrides(t, 1.0, q, False), f"licensing.royalty={float(r)!r}",
          f"licensing.brand={'white_label' if arm in ('Wg', 'Wt') else 'owner'}",
          f"licensing.white_label_tier={'genuine' if arm == 'Wg' else 'type'}",
          f"ratings.prior_n={float(prior_n)!r}", f"seed={seed}"]
    c = load(None, ov, mode="bazaar")
    return benchmark.licence_config(c, None if arm == "never" else owner, NEVER if arm == "never" else (N_LIC, B_DAY))


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ chains: job = (arm, quality, t, seed, owner, r, prior_n)

def key(j) -> str:
    arm, q, t, sd, s, r, pn = j
    return f"{arm}|{q}|{t}|{sd}|{s}|{_rk(r)}|{_pk(pn)}"


def old_key(rec) -> str:
    """The 0.17.0 Brand Equity cache key of the same chain (R, W_t and never only)."""
    arm = {"Wt": "W"}.get(rec["arm"], rec["arm"])
    return f"{arm}|{rec['quality']}|{rec['t']}|{rec['seed']}|{rec['owner']}|{_rk(rec['royalty'])}"


def days_to(path, target=TARGET, start=B_DAY) -> int | None:
    """Days from the licence day (day 10 = 1) until the end-of-day rating first reaches `target`; None if never."""
    for d in range(start, DAYS + 1):
        x = path[d - 1]
        if x is not None and x >= target - 1e-12:
            return d - start + 1
    return None


def job(j) -> dict:
    arm, q, t, seed, owner, r, pn = j
    LB._observe()
    LB._PARKED.clear()
    tap = ProfileTap([])
    out, snaps, bad = CR.run_with_ledger(config(arm, q, t, seed, owner, r, pn), log=tap)
    sids = sorted(snaps[0])
    owners = L.sample_stalls(seed) if arm == "never" else [owner]
    lic = sorted(s for s in sids if snaps[-1][s]["licensed_from"] == owner) if arm != "never" else []
    keep = sids if arm == "never" else [owner, *lic]
    rec = {"key": key(j), "arm": arm, "quality": q, "t": t, "seed": seed, "owner": owner, "royalty": float(r),
           "prior_n": float(pn), "licensees": lic, "profit_mismatch": bad,
           "win": E._sums(snaps, keep, WINDOW), "all30": E._sums(snaps, keep, range(1, DAYS + 1)),
           "stype": {s: snaps[0][s]["stype"] for s in keep},
           "totals": {s: benchmark.stall_total(out, s) for s in owners},
           "rating": {s: [out["days"][d]["brand_ratings"].get(out["days"][d]["brands"][s]) for d in range(DAYS)]
                      for s in [*owners, *lic]},
           "white_label": {s: snaps[-1][s]["white_label"] for s in lic},
           "profile": {str(k): v for k, v in sorted(tap.days.items())}, "guard": CR.guard(out),
           "digest": hashlib.sha256(dumps(out).encode()).hexdigest()}
    if arm == "never":   # the speed dial reaches every brand: mean rating by stall type, days 1-30 (rated only)
        by = {}
        for st in STYPES:
            ss = [s for s in sids if snaps[0][s]["stype"] == st]
            row = []
            for d in range(DAYS):
                v = [out["days"][d]["brand_ratings"].get(out["days"][d]["brands"][s]) for s in ss]
                v = [x for x in v if x is not None]
                row.append(float(np.mean(v)) if v else None)
            by[st] = row
        rec["rating_by_type"] = by
        rec["catches"] = int(sum(snaps[d][s]["catches"] for s in sids for d in range(DAYS)))
    rec["roy_at"] = {_rk(x): {s: int(sum(snaps[d - 1][s]["units"] * int(round(float(x) * snaps[d - 1][s]["price"]))
                                         for d in range(1, DAYS + 1) if snaps[d - 1][s]["licensed_from"] == owner))
                              for s in lic} for x in RATES}
    rec["roy_mismatch"] = sum(snaps[d][s]["roy_paid"] != (0 if arm in ("Wg", "Wt") else snaps[d][s]["units"] *
                                                          int(round(float(r) * snaps[d][s]["price"])))
                              for s in lic for d in range(B_DAY - 1, DAYS))
    rec["dig_trade"] = [hashlib.sha1(repr([(s, *(snaps[d][s][f] for f in ("units", "revenue", "cost", "ad", "fines",
                                                                          "switch", "catches", "price")))
                                           for s in sids]).encode()).hexdigest()[:16] for d in range(DAYS)]
    # white labels at the genuine tier: posted price = base x (1 + premium x (start-of-day rating - 0.5)), every day
    if arm == "Wg":
        cfg = config(arm, q, t, seed, owner, r, pn)
        prem = cfg.brands.premium
        cat = {st.sid: st.category for st in BazaarEngine(cfg).stalls}
        miss = 0
        for s in lic:
            base = cfg.pricing.base_price_cents[cat[s]]
            for d in range(B_DAY, DAYS + 1):
                prev = None if d == B_DAY else out["days"][d - 2]["brand_ratings"].get(out["days"][d - 1]["brands"][s])
                rr = 0.5 if prev is None else prev
                if snaps[d - 1][s]["price"] != int(round(base * (1 + prem * (rr - 0.5)))):
                    miss += 1
        rec["tier_price_miss"] = miss
        rec["tier_price_checked"] = True
        # stall-days (days 10-30) priced above unit cost, by licensee stall type (the pilot's G4)
        rec["above_cost"] = {st_: [int(sum(snaps[d - 1][s]["price"] > snaps[d - 1][s]["unit_cost"]
                                           for s in lic if snaps[0][s]["stype"] == st_ for d in WINDOW)),
                                   int(sum(1 for s in lic if snaps[0][s]["stype"] == st_ for d in WINDOW))]
                             for st_ in ("seconds", "deceptive")}
    return rec


def check_jobs_for(check_seed, samples, levels) -> list[tuple]:
    """The no-decision replay: R at t100, royalty 0.10 (shared with the run) and 0.05, 0.25; current speed for both
    qualities, the slowest speed for contract."""
    slow = [k for k in levels if k != CURRENT]
    cells = [(q, levels[CURRENT]) for q in QUALS] + ([("contract", levels[slow[-1]])] if slow else [])
    return [("R", q, "t100", check_seed, s, r, pn) for q, pn in cells for s in samples[check_seed]
            for r in (ROYALTY, *CHECK_RATES)]


def jobs_for(seeds, samples, levels) -> list[tuple]:
    out = []
    for sd in seeds:
        for lv, pn in levels.items():
            for t in VERS:
                out.append(("never", "-", t, sd, None, ROYALTY, pn))
            arms = ("R", "Wg", "Wt") if lv == CURRENT else ("R", "Wg")
            quals = QUALS if lv == CURRENT else ("contract",)
            for q in quals:
                for t in VERS:
                    for s in samples[sd]:
                        for arm in arms:
                            out.append((arm, q, t, sd, s, ROYALTY, pn))
    return out


def royalty_check(runs, check_seed, samples, levels) -> dict:
    idx = {r["key"]: r for r in runs}
    rows, ok = [], True
    slow = [k for k in levels if k != CURRENT]
    cells = [(q, levels[CURRENT], CURRENT) for q in QUALS] + ([("contract", levels[slow[-1]], slow[-1])] if slow else [])
    for q, pn, lv in cells:
        for s in samples[check_seed]:
            base = idx[key(("R", q, "t100", check_seed, s, ROYALTY, pn))]
            for r in CHECK_RATES:
                x = idx[key(("R", q, "t100", check_seed, s, r, pn))]
                same_days = sum(a == b for a, b in zip(base["dig_trade"], x["dig_trade"]))
                same_lic = base["licensees"] == x["licensees"]
                roy_diff = base["all30"][s]["roy_recv"] != x["all30"][s]["roy_recv"]
                exact = x["roy_at"][_rk(r)] == base["roy_at"][_rk(r)] and \
                    sum(x["roy_at"][_rk(r)].values()) == x["all30"][s]["roy_recv"]
                good = same_days == DAYS and same_lic and roy_diff and exact
                ok &= good
                rows.append({"level": lv, "quality": q, "owner": s, "royalty": r, "days_identical": same_days,
                             "same_licensees": same_lic, "royalties_differ": roy_diff, "recompute_exact": exact,
                             "pass": good})
    return {"pass": ok, "rows": rows}


# ------------------------------------------------------------------ analysis

def _r(x):
    return 0.5 if x is None else x


def _slope(xs, ys):
    pts = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pts) < 2:
        return None
    a = np.array(pts, float)
    return float(np.polyfit(a[:, 0], a[:, 1], 1)[0])


def analyse(runs, seeds, samples, levels, days_x, ref=None) -> dict:
    idx = {(r["arm"], r["quality"], r["t"], r["seed"], r["owner"], _rk(r["royalty"]), _pk(r["prior_n"])): r
           for r in runs}
    res: dict = {"seeds": seeds, "levels": levels, "days_x": days_x, "cells": {}, "never": {}, "pred": {},
                 "guard": {}, "flags": [], "identity": {}, "ref": {}}
    jbad = jmax = 0
    tier_miss = tier_checked = 0
    for lv, pn in levels.items():
        quals = QUALS if lv == CURRENT else ("contract",)
        wt = lv == CURRENT
        for q in quals:
            for t in VERS:
                ks = ["J_never", "J_R", "J_Wg", "reputation", "composition", "licensing", *SPLIT, "split_resid",
                      "owner_gain_Wg", *[f"owner_gain_R_{_rk(x)}" for x in RATES],
                      *[f"lic_profit_R_{_rk(x)}" for x in RATES], "lic_profit_Wg", "lic_profit_never",
                      "lic_units_R", "lic_units_Wg", "lic_units_never", "lic_price_R", "lic_price_Wg",
                      "owner_units_R", "owner_units_Wg", "owner_units_never", "days_to_target_Wg",
                      "share_reached_Wg", "owner_rating_day10_never"]
                if wt:
                    ks += ["J_Wt", "tier", "name_old", "owner_gain_Wt", "lic_profit_Wt", "lic_units_Wt", "lic_price_Wt",
                           "owner_units_Wt"]
                per = {k: [] for k in ks}
                paths = {k: [] for k in ("never", "R", "Wg_owner", "Wg_labels", *(("Wt_labels",) if wt else ()))}
                prof = {p: {k: [] for k in ("short", "surplus")} for p in PROFILES}
                for sd in seeds:
                    nv = idx[("never", "-", t, sd, None, _rk(ROYALTY), _pk(pn))]
                    acc = {k: [] for k in per}
                    pacc = {p: {k: [] for k in ("short", "surplus")} for p in PROFILES}
                    for s in samples[sd]:
                        R = idx[("R", q, t, sd, s, _rk(ROYALTY), _pk(pn))]
                        Wg = idx[("Wg", q, t, sd, s, _rk(ROYALTY), _pk(pn))]
                        Wt = idx[("Wt", q, t, sd, s, _rk(ROYALTY), _pk(pn))] if wt else None
                        lic = R["licensees"]
                        for W in [Wg, *([Wt] if wt else [])]:
                            if W["licensees"] != lic or len(lic) != N_LIC or not all(W["white_label"].values()):
                                res["flags"].append(f"{lv}|{q}|{t}|{sd}|{s}: R and {W['arm']} licensees differ or are "
                                                    "not 6 white labels")
                        if Wg.get("tier_price_checked"):
                            tier_checked += 1
                            tier_miss += Wg["tier_price_miss"]
                        stalls = [s, *lic]
                        Jr, Jg, Jn = E._J(R, stalls), E._J(Wg, stalls), E._J(nv, stalls)
                        Js = [Jr, Jg, Jn]
                        if wt:
                            Jt = E._J(Wt, stalls)
                            Js.append(Jt)
                        for a_, b_ in Js:
                            jbad += a_ != b_
                            jmax += 1
                        acc["J_R"].append(Jr[0]); acc["J_Wg"].append(Jg[0]); acc["J_never"].append(Jn[0])
                        acc["reputation"].append(Jr[0] - Jg[0]); acc["composition"].append(Jg[0] - Jn[0])
                        acc["licensing"].append(Jr[0] - Jn[0])
                        if wt:
                            acc["J_Wt"].append(Jt[0]); acc["tier"].append(Jg[0] - Jt[0])
                            acc["name_old"].append(Jr[0] - Jt[0])
                        sp = E._split(R, Wg, s, lic)
                        for k in SPLIT:
                            acc[k].append(sp[k])
                        acc["split_resid"].append(Jr[0] - Jg[0] - sum(sp.values()))
                        never_tot = nv["totals"][s]
                        roy_base = sum(R["roy_at"][_rk(ROYALTY)].values())
                        if roy_base != R["all30"][s]["roy_recv"]:
                            res["flags"].append(f"{lv}|{q}|{t}|{sd}|{s}: recomputed royalties at 0.10 differ from the "
                                                "engine's")
                        for x in RATES:
                            rx = sum(R["roy_at"][_rk(x)].values())
                            acc[f"owner_gain_R_{_rk(x)}"].append(R["totals"][s] - roy_base + rx - never_tot)
                            acc[f"lic_profit_R_{_rk(x)}"].append(float(np.mean(
                                [R["win"][l]["profit"] + R["roy_at"][_rk(ROYALTY)][l] - R["roy_at"][_rk(x)][l]
                                 for l in lic])))
                        arms = [("R", R), ("Wg", Wg), *([("Wt", Wt)] if wt else [])]
                        for arm, rec in arms[1:]:
                            acc[f"owner_gain_{arm}"].append(rec["totals"][s] - never_tot)
                            acc[f"lic_profit_{arm}"].append(float(np.mean([rec["win"][l]["profit"] for l in lic])))
                        acc["lic_profit_never"].append(float(np.mean([nv["win"][l]["profit"] for l in lic])))
                        for arm, rec in [*arms, ("never", nv)]:
                            acc[f"lic_units_{arm}"].append(sum(rec["win"][l]["units"] for l in lic))
                            acc[f"owner_units_{arm}"].append(rec["win"][s]["units"])
                        for arm, rec in arms:
                            u = sum(rec["win"][l]["units"] for l in lic)
                            acc[f"lic_price_{arm}"].append(sum(rec["win"][l]["revenue"] for l in lic) / u if u else None)
                        dd = [days_to(Wg["rating"][l]) for l in lic]
                        reached = [x for x in dd if x is not None]
                        acc["days_to_target_Wg"].append(float(np.mean(reached)) if reached else None)
                        acc["share_reached_Wg"].append(len(reached) / len(dd))
                        acc["owner_rating_day10_never"].append(_r(nv["rating"][s][B_DAY - 1]))
                        paths["never"].append([_r(x) for x in nv["rating"][s]])
                        paths["R"].append([_r(x) for x in R["rating"][s]])
                        paths["Wg_owner"].append([_r(x) for x in Wg["rating"][s]])
                        paths["Wg_labels"].append([float(np.mean([_r(Wg["rating"][l][d]) for l in lic]))
                                                   for d in range(DAYS)])
                        if wt:
                            paths["Wt_labels"].append([float(np.mean([_r(Wt["rating"][l][d]) for l in lic]))
                                                       for d in range(DAYS)])
                        wr, ww = _window(R["profile"], WINDOW), _window(Wg["profile"], WINDOW)
                        for p in PROFILES:
                            for k in ("short", "surplus"):
                                if wr[k][p] is not None and ww[k][p] is not None:
                                    pacc[p][k].append(wr[k][p] - ww[k][p])
                    for k in per:
                        vals = [v for v in acc[k] if v is not None]
                        per[k].append(float(np.mean(vals)) if vals else None)
                    for p in PROFILES:
                        for k in ("short", "surplus"):
                            prof[p][k].append(float(np.mean(pacc[p][k])) if pacc[p][k] else None)
                cell = {k: mean_ci(v) for k, v in per.items()}
                cell["per_seed"] = per
                cell["paths"] = {k: [float(x) for x in np.mean(v, axis=0)] for k, v in paths.items()}
                cell["profile"] = {p: {k: mean_ci(prof[p][k]) for k in ("short", "surplus")} for p in PROFILES}
                res["cells"][f"{lv}|{q}|{t}"] = cell
        # never chains at this speed: whole-market totals by stall type, catches, ratings by type
        for t in VERS:
            nv = {k: [] for k in ("profit_genuine", "profit_seconds", "profit_deceptive", "catches", "owner_total",
                                  *[f"rating_{st}_d{d}" for st in STYPES for d in (10, 30)])}
            for sd in seeds:
                rec = idx[("never", "-", t, sd, None, _rk(ROYALTY), _pk(pn))]
                for st in STYPES:
                    nv[f"profit_{st}"].append(sum(rec["all30"][s]["profit"] for s in rec["all30"] if rec["stype"][s] == st))
                    for d in (10, 30):
                        nv[f"rating_{st}_d{d}"].append(rec["rating_by_type"][st][d - 1])
                nv["catches"].append(rec["catches"])
                nv["owner_total"].append(float(np.mean([rec["totals"][s] for s in samples[sd]])))
            res["never"][f"{lv}|{t}"] = {"per_seed": nv, **{k: mean_ci(v) for k, v in nv.items()}}
    res["identity"] = {"J_checked": jmax, "J_mismatch": jbad,
                       "split_resid_max_abs": max(abs(x) for c in res["cells"].values()
                                                  for x in c["per_seed"]["split_resid"] if x is not None),
                       "tier_price_chains": tier_checked, "tier_price_miss": tier_miss}
    if jbad:
        res["flags"].append(f"J identity fails in {jbad} of {jmax} owner-chains")
    if tier_miss or not tier_checked:
        res["flags"].append(f"genuine-tier price check: {tier_miss} misses in {tier_checked} chains checked")
    # extra gate: current speed never, R and W_t equal the 0.17.0 chains
    if ref is not None:
        n = eq = 0
        for r in runs:
            if _pk(r["prior_n"]) != _pk(levels[CURRENT]) or r["arm"] == "Wg":
                continue
            o = ref.get(old_key(r))
            if o is None:
                continue
            n += 1
            same = (o["digest"] == r["digest"] and o["win"] == r["win"] and o["all30"] == r["all30"]
                    and o["totals"] == r["totals"])
            eq += same
            if not same:
                res["flags"].append(f"0.17.0 identity fails: {r['key']}")
        res["ref"] = {"compared": n, "equal": eq}
    # vs days to the target, from the calibration
    C = res["cells"]
    lvls = list(levels)
    xs = [days_x[lv] for lv in lvls]
    P = {}
    rep = lambda c: C[c]["per_seed"]["reputation"]
    sl = [_slope(xs, [rep(f"{lv}|contract|t40")[i] for lv in lvls]) for i in range(len(seeds))]
    P["PR1"] = {**mean_ci(sl), "sign": +1, "per_seed": sl,
                "label": "contract, t40: slope of R − W_g over days to 0.9 ($ per day)"}
    cur = f"{CURRENT}|contract|t40"
    P["PR2"] = {**paired_diff(C[cur]["per_seed"]["tier"], rep(cur)), "sign": -1,
                "label": "contract, t40, current speed: reputation effect − tier effect"}
    slowest = lvls[-1]
    P["PR3"] = {**paired_diff(rep(f"{slowest}|contract|t100"), rep(f"{slowest}|contract|t40")), "sign": +1,
                "label": f"{slowest}: contract: reputation effect at t40 − at t100 (exploratory)"}
    for t in VERS:
        g = lambda lv: C[f"{lv}|contract|{t}"]["per_seed"][f"owner_gain_R_{_rk(ROYALTY)}"]
        sl = [_slope(xs, [g(lv)[i] for lv in lvls]) for i in range(len(seeds))]
        P[f"PR4 {t}"] = {**mean_ci(sl), "sign": +1, "per_seed": sl,
                         "label": f"contract, {t}: slope of the owner's gain at 0.10 over days to 0.9 ($ per day) "
                                  "(exploratory)"}
    for c in C:
        lv, q, t = c.split("|")
        P[f"rep {c}"] = {**C[c]["reputation"], "sign": 0, "label": f"{lv}, {q}, {t}: reputation effect R − W_g"}
        if lv == CURRENT:
            P[f"tier {c}"] = {**C[c]["tier"], "sign": 0, "label": f"{lv}, {q}, {t}: tier effect W_g − W_t"}
    for v in P.values():
        v["verdict"] = _verdict(v, v["sign"]) if v["sign"] else (
            "interval excludes 0" if v.get("lo") is not None and (v["lo"] > 0 or v["hi"] < 0) else "interval includes 0")
    res["pred"] = P
    groups = {}
    for r in runs:
        groups.setdefault(f"{r['arm']}|{r['quality']}|{r['t']}|p{_pk(r['prior_n'])}", []).append(r)
    for g, rs in sorted(groups.items()):
        gg = {k: sum(r["guard"][k] for r in rs) for k in ("stuck_buyers", "idle_choosers", "parked", "buyer_days",
                                                          "fallbacks")}
        gg["chains"] = len(rs)
        gg["profit_mismatch"] = sum(r["profit_mismatch"] for r in rs)
        gg["roy_mismatch"] = sum(r["roy_mismatch"] for r in rs)
        res["guard"][g] = gg
        for k in ("stuck_buyers", "parked", "idle_choosers", "fallbacks", "profit_mismatch", "roy_mismatch"):
            if gg[k]:
                res["flags"].append(f"{g}: {k} {gg[k]}")
    return res


# ------------------------------------------------------------------ report

def _lab(c):
    return c.replace("|", ", ")


def report(res: dict, rc: dict, meta: dict, old: str | None) -> str:
    lv = res["levels"]
    dx = res["days_x"]
    L_ = ["# Brand Equity at the genuine tier, with rating speed", "",
          "Spec: `runs/plan_brand_equity_tier.md` (2026-11-13) and the addendum \"rating speed as a factor\" "
          "(2026-11-16); predictions fixed 2026-11-16, before any run. Calibration: `runs/calibration_rating_speed.md`. "
          "Pilot gate: `runs/pilot_brand_equity_tier.md`.", "",
          "## Design (prespecified)", "",
          "- Question: what does a reputation earn once a white label may price like the owner, and does it earn more "
          "when reputations form slowly?",
          "- Engine 0.18.0. Market, owners and licence option as Brand Equity: the licensing market, detect_scale 1, "
          "owner not liable; 3 owners per seed from `default_rng([seed, 17])`; N 6 from day 10, royalty 0.10.",
          "- Arms per owner: never; R (licensees under the owner's brand); W_g (the same stalls under white labels at "
          "the genuine tier, `licensing.white_label_tier` genuine); W_t (white labels at their stall type's tier, the "
          "0.17.0 W).",
          "- Rating speed: `ratings.prior_n` (every brand starts with prior_n pseudo-reviews at 0.5, counted in each "
          "day's share and fading by memory 0.7 per day). Levels from the calibration (days for a fresh contract white "
          "label to reach a 0.9 rating, t40): " + "; ".join(f"{k}: prior_n {lv[k]:g}, {dx[k]:.1f} days" for k in lv) + ".",
          "- Current speed: never, R, W_g, W_t × {contract, cheap} × {t40, t100}. Slow speeds: never, R, W_g × "
          "contract × {t40, t100}. Seeds 300–329, paired; everything rerun at 0.18.0. Extra gate: at current speed, "
          "never, R and W_t equal the 0.17.0 Brand Equity chains to the cent.",
          "- Measures, per owner: J = owner + 6 licensees' profit, days 10–30. Reputation effect = J(R) − J(W_g), split "
          "into owner own sales, licensee sales, licensee prices, licensee ad spend and fines. Tier effect = J(W_g) − "
          "J(W_t) (current speed); the 0.17.0 name effect J(R) − J(W_t) = reputation + tier. Composition = J(W_g) − "
          "J(never). Each effect is compared within its own speed; never chains are reported across speeds. Owner's "
          "gain at 0.05–0.25 by the exact recompute after the no-decision check.",
          "- Predictions (verbatim from the spec):", *[f"  - {p}" for p in PREDICTIONS],
          "- Analysis: per seed the mean over 3 owners; mean and 95% t over seeds; unadjusted. Slopes (PR1, PR4) fitted "
          "per seed by least squares over the calibration's days to 0.9, then averaged; PR4 in contract at t40 and at "
          "t100.", ""]
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
           f"- Seeds {meta['seeds_txt']} ({len(res['seeds'])}), paired",
           "- Sampled owners per seed: " + "; ".join(f"{sd}: {', '.join(meta['samples'][str(sd)])}" for sd in res["seeds"]),
           ""]
    idn = res["identity"]
    ref = res.get("ref") or {}
    L_ += ["## Gate", "", meta.get("gate", ""), "",
           f"0.17.0 identity (current speed never, R and W_t against `{meta.get('ref_cache')}`, full-outcome digest and "
           f"every ledger to the cent): {ref.get('equal', '–')}/{ref.get('compared', '–')} chains equal.", "",
           f"Genuine-tier prices: every W_g white label's posted price equals base × (1 + 0.4 × (start-of-day rating − "
           f"0.5)) on every day from 10: {idn['tier_price_miss']} misses in {idn['tier_price_chains']} chains.", "",
           "### The royalty enters no decision", "",
           "Code: as Brand Equity (0.17.0); 0.18.0 adds no reader of `licensing.royalty`, and the prior enters "
           "ratings only (`engine/brands.py` `update_brand_ratings`). Replay at seed "
           f"{meta.get('check_seed')}, t100, R at royalty 0.05 and 0.25 against 0.10:", "",
           *_t(["Speed", "Quality", "Owner", "Royalty", "Days identical", "Same licensees", "Royalties differ",
                "Recompute exact", "Pass"],
               [[x["level"], x["quality"], x["owner"], f"{x['royalty']:.2f}", f"{x['days_identical']}/{DAYS}",
                 "yes" if x["same_licensees"] else "no", "yes" if x["royalties_differ"] else "no",
                 "yes" if x["recompute_exact"] else "no", "yes" if x["pass"] else "**no**"] for x in rc["rows"]]),
           "", f"Result: **{'pass' if rc['pass'] else 'FAIL'}**.", "",
           f"J identity: {idn['J_checked'] - idn['J_mismatch']}/{idn['J_checked']} owner-chains to the cent; largest "
           f"split residual {idn['split_resid_max_abs']:.6f} cents.", ""]
    P = res["pred"]
    main = [k for k in P if k.startswith("PR")]
    L_ += ["## Predictions", "",
           "$ per owner over days 10–30 (per-seed mean of 3 owners); slopes in $ per day to 0.9. PR1–PR2 confirmatory; "
           "the rest exploratory.", "",
           *_t(["Prediction", "Estimate ($)", "Verdict"], [[f"**{k}**: {P[k]['label']}", _ci(P[k], _d), P[k]["verdict"]]
                                                        for k in main]), "",
           "All reputation and tier effects:", "",
           *_t(["Effect", "Estimate ($)", "Interval"], [[P[k]["label"], _ci(P[k], _d), P[k]["verdict"]]
                                                       for k in P if k not in main]), ""]
    C = res["cells"]
    L_ += ["## Joint profit and its parts", "",
           "J per owner and its 6 licensees, days 10–30, $.", "",
           *_t(["Cell", "J never", "J W_t", "J W_g", "J R", "Composition W_g − never", "Tier W_g − W_t",
                "Reputation R − W_g", "Name (0.17.0) R − W_t"],
               [[_lab(c), _ci(v["J_never"], _d), _ci(v.get("J_Wt"), _d), _ci(v["J_Wg"], _d), _ci(v["J_R"], _d),
                 _ci(v["composition"], _d), _ci(v.get("tier"), _d), _ci(v["reputation"], _d), _ci(v.get("name_old"), _d)]
                for c, v in C.items()]), "",
           "Reputation effect split (R − W_g, $; the parts add up to the effect):", "",
           *_t(["Cell", *[SPLIT_LAB[k] for k in SPLIT]], [[_lab(c), *[_ci(v[k], _d) for k in SPLIT]] for c, v in C.items()]),
           "", "Units and prices, days 10–30:", "",
           *_t(["Cell", "Licensee units never / W_t / W_g / R", "Licensee mean price W_t / W_g / R ($)",
                "Owner units never / W_t / W_g / R"],
               [[_lab(c),
                 " / ".join(_num(1)(v[f"lic_units_{a}"]["mean"]) if f"lic_units_{a}" in v else "–"
                            for a in ("never", "Wt", "Wg", "R")),
                 " / ".join(_d(v[f"lic_price_{a}"]["mean"]) if f"lic_price_{a}" in v else "–" for a in ("Wt", "Wg", "R")),
                 " / ".join(_num(1)(v[f"owner_units_{a}"]["mean"]) if f"owner_units_{a}" in v else "–"
                            for a in ("never", "Wt", "Wg", "R"))] for c, v in C.items()]), ""]
    L_ += ["## Owner's gain and licensee profit by royalty", "",
           "Owner's gain = owner's 30-day profit − never at the same speed. R by the exact recompute; white labels pay no "
           "royalty. Licensee profit: per licensee, days 10–30.", "",
           *_t(["Cell", *[f"Owner gain R, {x:.2f}" for x in RATES], "Owner gain W_g", "Owner gain W_t"],
               [[_lab(c), *[_ci(v[f"owner_gain_R_{_rk(x)}"], _d) for x in RATES], _ci(v["owner_gain_Wg"], _d),
                 _ci(v.get("owner_gain_Wt"), _d)] for c, v in C.items()]), "",
           *_t(["Cell", "Licensee profit never", "W_t", "W_g", *[f"R, {x:.2f}" for x in RATES]],
               [[_lab(c), _ci(v["lic_profit_never"], _d), _ci(v.get("lic_profit_Wt"), _d), _ci(v["lic_profit_Wg"], _d),
                 *[_ci(v[f"lic_profit_R_{_rk(x)}"], _d) for x in RATES]] for c, v in C.items()]), ""]
    L_ += ["## Rating speed", "",
           "Days from day 10 (= 1) until a W_g white label's rating first reaches 0.9 (mean over those that reach it), "
           "the share that reach it by day 30, and the owner's own rating at the end of day 10 in the never chain.", "",
           *_t(["Cell", "Days to 0.9", "Share reaching 0.9", "Owner rating day 10 (never)"],
               [[_lab(c), _ci(v["days_to_target_Wg"], _num(1), signed=False), _ci(v["share_reached_Wg"], _num(2), signed=False),
                 _ci(v["owner_rating_day10_never"], _num(3), signed=False)] for c, v in C.items()]), "",
           "Rating paths: mean over owners (unrated = 0.5), end of days 1, 5, 9, 10, 12, 15, 20, 25, 30.", ""]
    rows = []
    for c, v in C.items():
        for k, lab in (("never", "owner, never"), ("R", "owner brand, R"), ("Wg_owner", "owner brand, W_g"),
                       ("Wg_labels", "white labels, W_g"), ("Wt_labels", "white labels, W_t")):
            if k in v["paths"]:
                ys = v["paths"][k]
                rows.append([_lab(c), lab, *[f"{ys[d - 1]:.3f}" for d in (1, 5, 9, 10, 12, 15, 20, 25, 30)]])
    L_ += [*_t(["Cell", "Series", "1", "5", "9", "10", "12", "15", "20", "25", "30"], rows), ""]
    NV = res["never"]
    L_ += ["## Never chains across speeds", "",
           "The prior reaches every brand. Whole-market 30-day profit by stall type ($, all stalls of the type), "
           "catches, the sampled owners' mean 30-day profit, and mean rating of rated brands by type (days 10 and 30). "
           "Differences from the current speed, same seeds.", "",
           *_t(["Never chain", "Genuine profit", "Seconds profit", "Deceptive profit", "Catches", "Owner profit",
                "Rating genuine d10 / d30", "Rating seconds d10 / d30", "Rating deceptive d10 / d30"],
               [[_lab(k), _ci(v["profit_genuine"], _d, False), _ci(v["profit_seconds"], _d, False),
                 _ci(v["profit_deceptive"], _d, False), _ci(v["catches"], _num(0), False), _ci(v["owner_total"], _d, False),
                 *[" / ".join(_num(3)(v[f"rating_{st}_d{d}"]["mean"]) for d in (10, 30)) for st in STYPES]]
                for k, v in NV.items()]), ""]
    diffs = []
    for k, v in NV.items():
        l_, t = k.split("|")
        if l_ == CURRENT:
            continue
        b = NV[f"{CURRENT}|{t}"]["per_seed"]
        diffs.append([f"{l_} − current, {t}", *[_ci(paired_diff(b[f], v["per_seed"][f]), _d)
                                                for f in ("profit_genuine", "profit_seconds", "profit_deceptive")],
                      _ci(paired_diff(b["catches"], v["per_seed"]["catches"]), _num(0)),
                      _ci(paired_diff(b["owner_total"], v["per_seed"]["owner_total"]), _d)])
    if diffs:
        L_ += [*_t(["Difference", "Genuine profit", "Seconds profit", "Deceptive profit", "Catches", "Owner profit"],
                   diffs), ""]
    L_ += ["## Buyers by profile, R − W_g (exploratory)", "",
           "Days 10–30. Shortfall in points of purchases; surplus in $ per buyer of the profile.", "",
           *_t(["Cell", *[f"{p}: shortfall (pts)" for p in PROFILES], *[f"{p}: surplus ($)" for p in PROFILES]],
               [[_lab(c), *[_ci(v["profile"][p]["short"], lambda x, s: _num(1)(100 * x, s)) for p in PROFILES],
                 *[_ci(v["profile"][p]["surplus"], _d) for p in PROFILES]] for c, v in C.items()]), ""]
    L_ += ["## Stuck, parked and idle buyers", "",
           *_t(["Chains", "Count", "Buyer-days", "Stuck", "Parked", "Idle choosers", "Invalid actions"],
               [[g.replace("|", " · "), str(v["chains"]), f"{v['buyer_days']:,}", str(v["stuck_buyers"]), str(v["parked"]),
                 str(v["idle_choosers"]), str(v["fallbacks"])] for g, v in res["guard"].items()]), "",
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

def _read_ref(path):
    out = {}
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                out[r["key"]] = r
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="300-329")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--outdir", default="runs")
    ap.add_argument("--tests", default="")
    ap.add_argument("--gate", default="")
    ap.add_argument("--ref-cache", default="runs/brand_equity_cache.jsonl",
                    help="0.17.0 Brand Equity chains for the identity gate")
    ap.add_argument("--min-swap-mb", type=float, default=512)
    ap.add_argument("--min-free-pct", type=float, default=15)
    ap.add_argument("--pilot", action="store_true", help="pilot seeds 900-902 into an --outdir other than runs")
    a = ap.parse_args(argv)
    if any(v is None for v in LEVELS.values()) or any(v is None for v in DAYS_TO_TARGET.values()):
        raise SystemExit("LEVELS and DAYS_TO_TARGET are not set: run the calibration first")
    seeds = parse_seeds(a.seeds)
    LB._lower_priority()
    if a.pilot:
        if not set(seeds) <= PILOT_SEEDS or os.path.abspath(a.outdir) == os.path.abspath("runs"):
            raise SystemExit("--pilot uses seeds 900-902 and an outdir other than runs")
    elif not set(seeds) <= MAIN_SEEDS:
        raise SystemExit("the main run uses seeds 300-329 only")
    os.makedirs(a.outdir, exist_ok=True)
    log = CR.file_logger(os.path.join(a.outdir, "brand_equity_tier_run.log"))
    t0 = time.time()
    check_seed = seeds[0]
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
            "command": " ".join(["python -m analysis.brand_equity_tier", *sys.argv[1:]]), "tests": a.tests,
            "gate": a.gate or "Pilot gate: see `runs/pilot_brand_equity_tier.md`.", "check_seed": check_seed,
            "ref_cache": a.ref_cache, "levels": LEVELS, "days_x": DAYS_TO_TARGET,
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
            "workers": a.workers, "load_start": _load(), "mem_start": memory_state(), "seeds_txt": a.seeds}
    log(f"brand equity tier: engine {ENGINE_VERSION}, commit {meta['git']['commit'][:7]}, seeds {a.seeds}, "
        f"levels {LEVELS}")
    samples = {sd: L.sample_stalls(sd) for sd in seeds}
    meta["samples"] = {str(k): v for k, v in samples.items()}
    cache = os.path.join(a.outdir, "brand_equity_tier_cache.jsonl")
    # 1. the no-decision check first; stop if it fails
    check_jobs = check_jobs_for(check_seed, samples, LEVELS)
    cr, p0 = CR.run_chains(a, check_jobs, cache, log, job, key)
    rc = royalty_check(cr, check_seed, samples, LEVELS)
    log(f"royalty check: {'pass' if rc['pass'] else 'FAIL'}")
    if not rc["pass"]:
        with open(os.path.join(a.outdir, "brand_equity_tier_royalty_check.json"), "w", encoding="utf-8") as f:
            json.dump(rc, f, indent=1)
        raise SystemExit("royalty check failed: a decision depends on the royalty; stop and report")
    del cr
    # 2. the run
    runs, pauses = CR.run_chains(a, jobs_for(seeds, samples, LEVELS), cache, log, job, key)
    ref = _read_ref(a.ref_cache)
    log(f"0.17.0 reference: {len(ref)} chains from {a.ref_cache}")
    res = analyse(runs, seeds, samples, LEVELS, DAYS_TO_TARGET, ref)
    extra = len([j for j in check_jobs if _rk(j[5]) != _rk(ROYALTY)])
    meta.update(chains=len(runs) + extra, pauses=pauses + p0, wall_h=(time.time() - t0) / 3600, load_end=_load(),
                mem_end=memory_state())
    with gzip.open(os.path.join(a.outdir, "brand_equity_tier.json.gz"), "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "royalty_check": rc, "results": res}, f, separators=(",", ":"))
    with open(os.path.join(a.outdir, "brand_equity_tier.csv"), "w", encoding="utf-8") as f:
        cols = ["J_never", "J_Wg", "J_R", "reputation", "composition", *SPLIT, f"owner_gain_R_{_rk(ROYALTY)}",
                "owner_gain_Wg", "days_to_target_Wg"]
        f.write("level,quality,verification,seed," + ",".join(cols + ["J_Wt", "tier"]) + "\n")
        for c, v in res["cells"].items():
            lv, q, t = c.split("|")
            for i, sd in enumerate(seeds):
                vals = [v["per_seed"][k][i] for k in cols] + [v["per_seed"].get(k, [None] * len(seeds))[i]
                                                               for k in ("J_Wt", "tier")]
                f.write(",".join([lv, q, t, str(sd), *["" if x is None else f"{x:.2f}" for x in vals]]) + "\n")
    sp = os.path.join(a.outdir, "brand_equity_tier_summary.md")
    old = open(sp, encoding="utf-8").read() if os.path.exists(sp) else None
    with open(sp, "w", encoding="utf-8") as f:
        f.write(report(res, rc, meta, old))
    log(f"done; {len(res['flags'])} flags; wall {meta['wall_h']:.2f} h")
    return 2 if res["flags"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
