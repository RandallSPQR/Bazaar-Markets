"""Brand Equity speed: what a reputation earns when new brands' ratings form slowly and the owner's does not
(rule-based only). Spec: the task "engine 0.19.0 (two keys), calibration, pilot, sizing" (2026-11-17); predictions
fixed 2026-11-17, before any run. Background: runs/brand_equity_tier_summary.md (engine 0.18.0). Levels chosen by
the calibration (analysis/calibrate_brand_equity_speed.py, runs/calibration_brand_equity_speed.md); pilot gate
analysis/pilot_brand_equity_speed.py, runs/pilot_brand_equity_speed.md.

Engine 0.19.0. Market as the 0.18.0 run (the licensing market, detect_scale 1, owner not liable, white_label_tier
genuine, royalty 0.10, N 6 from day 10, 3 owners per seed from default_rng([seed, 17])), but market.days 60 (D 60,
known to sellers) and ratings.prior_scope "new": the prior reaches only brands created on day 2 or later (white
labels, reopening names); the owner and every original stall rate as with prior_n 0.
  Arms: never, R (licensees under the owner's brand), W_g (white labels at the genuine tier). Quality contract.
  Speeds: four levels of ratings.prior_n from the calibration (days for a W_g white label to reach 0.9 at t40:
  about 1, 5, 10 and 20). Verification: t40 (locals inspect) and t100.
  Seeds 330-349 (20), paired across all cells.

Measures, per owner, J = owner + 6 licensees' profit, days 10-60 (royalties cancel). E = J(R) - J(W_g), split into
owner own sales, licensee sales, licensee prices, licensee ad spend and fines. E by window: catch-up = days 10
through the day the owner's W_g white labels first reach a mean end-of-day rating of 0.9 (unrated = 0.5), after =
the days after it (if never reached, every day is catch-up). Days to 0.9 per owner from W_g. Owner's gain (60-day
profit - never at the same speed) at royalty 0.05-0.25 by the exact recompute, after the no-decision replay check.
Licensee profit under R and W_g at each royalty. Never chains across speeds.

Predictions (fixed 2026-11-17, before any run; verbatim): see PREDICTIONS.
Analysis: per seed the mean over 3 owners; mean and 95% t over seeds; unadjusted. PS1's slope is fitted per seed by
least squares over the calibration's days to 0.9 (DAYS_TO_TARGET, fixed before the run), then averaged.

    .venv/bin/python -m analysis.brand_equity_speed --seeds 330-349 --tests "..."                         # main run
    .venv/bin/python -m analysis.brand_equity_speed --pilot --seeds 900-902 --outdir runs/pilot_brand_equity_speed/run
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import platform
import sys
import time

import numpy as np

import analysis.brand_equity as E
import analysis.chainrun as CR
import analysis.liability as LB
import analysis.licensing as L
from analysis.capture import memory_state
from analysis.counterfeit import _ci, _d, _git, _load, _num, _t, _verdict
from cli.sweep import parse_seeds
from engine import ENGINE_VERSION, benchmark
from engine.bazaar import BazaarEngine
from engine.config import load
from engine.jsonlog import dumps
from engine.metrics import mean_ci, paired_diff

DAYS = 60
N_LIC, B_DAY, ROYALTY, RATES = E.N_LIC, E.B_DAY, E.ROYALTY, E.RATES
VERS = ("t40", "t100")
SCOPE = "new"
NEVER = benchmark.NEVER
MAIN_SEEDS = set(range(330, 350))
PILOT_SEEDS = set(range(900, 903))
CHECK_RATES = (0.05, 0.25)
TARGET = 0.9
# Rating-speed levels: label -> ratings.prior_n, and the calibration's mean days for a W_g white label to reach 0.9
# at t40 (the x of PS1 and PS4). Set from runs/calibration_brand_equity_speed.md before any pilot or main run.
LEVELS: dict[str, float | None] = {"current": 0.0, "d5": 3.5, "d10": 10.0, "d20": 400.0}
DAYS_TO_TARGET: dict[str, float | None] = {"current": 1.0444444444444445, "d5": 6.355555555555555,
                                           "d10": 10.377777777777778, "d20": 20.755555555555556}
# Levels run at t100 (None = all). The timing gate may cut t100 to the current and slowest levels.
T100_LEVELS: list[str] | None = None
CURRENT = "current"
PREDICTIONS = [
    "PS1 (confirmatory): t40: E rises with time to reputation. Least-squares slope of E over the calibrated days to "
    "0.9 (four levels), fitted per seed, > 0.",
    "PS2 (confirmatory): t40, slowest level: more than half of E is earned during the catch-up window (before the "
    "white labels reach 0.9).",
    "PS3 (confirmatory): t40, current speed (prior_n 0): E over days 10–60 is less than 10% of E at the slowest level.",
    "PS4 (exploratory): shape. Compare a linear and a saturating fit of E against days to 0.9 at t40; report both, no "
    "prediction.",
    "PS5 (exploratory): t100: E at each speed; no direction predicted.",
    "PS6 (exploratory): the slowest speed at which licensees earn more under R than under W_g at royalty 0.10, at t40.",
]
SPLIT, SPLIT_LAB = E.SPLIT, E.SPLIT_LAB
STYPES = ("genuine", "seconds", "deceptive")
DF = ("units", "revenue", "cost", "ad", "fines", "switch", "profit")     # daily ledger fields kept for windows
OLD_CACHE = "runs/brand_equity_tier_cache.jsonl"                       # 0.18.0 chains for the pilot's G2


def _rk(r) -> str:
    return f"{float(r):.2f}"


def _pk(pn) -> str:
    return f"{float(pn):g}"


def config(arm, t, seed, owner, r=ROYALTY, prior_n=0.0, days=DAYS, scope=SCOPE):
    """arm: "never" | "R" | "Wg". As analysis.brand_equity_tier.config (contract) with market.days and
    ratings.prior_scope."""
    q = "cheap" if arm == "never" else "contract"
    ov = [*L.overrides(t, 1.0, q, False), f"licensing.royalty={float(r)!r}",
          f"licensing.brand={'white_label' if arm == 'Wg' else 'owner'}",
          f"licensing.white_label_tier={'genuine' if arm == 'Wg' else 'type'}",
          f"ratings.prior_n={float(prior_n)!r}", f"ratings.prior_scope={scope}", f"market.days={int(days)}",
          f"seed={seed}"]
    c = load(None, ov, mode="bazaar")
    return benchmark.licence_config(c, None if arm == "never" else owner, NEVER if arm == "never" else (N_LIC, B_DAY))


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ chains: job = (arm, t, seed, owner, r, prior_n, days, scope)

def key(j) -> str:
    arm, t, sd, s, r, pn, days, scope = j
    return f"{arm}|{t}|{sd}|{s}|{_rk(r)}|{_pk(pn)}|{int(days)}|{scope}"


def old_key(rec) -> str:
    """The 0.18.0 Brand Equity tier cache key of the same chain."""
    q = "-" if rec["arm"] == "never" else "contract"
    return f"{rec['arm']}|{q}|{rec['t']}|{rec['seed']}|{rec['owner']}|{_rk(rec['royalty'])}|{_pk(rec['prior_n'])}"


def days_to(path, target=TARGET, start=B_DAY) -> int | None:
    """Days from the licence day (day 10 = 1) until the end-of-day rating first reaches `target`; None if never."""
    for d in range(start, len(path) + 1):
        x = path[d - 1]
        if x is not None and x >= target - 1e-12:
            return d - start + 1
    return None


def _r(x):
    return 0.5 if x is None else x


def catch_day(rec, lic, target=TARGET) -> int | None:
    """The first day (>= 10) at whose end the mean rating of the white labels (unrated = 0.5) is >= target."""
    D = rec["days"]
    for d in range(B_DAY, D + 1):
        if float(np.mean([_r(rec["rating"][l][d - 1]) for l in lic])) >= target - 1e-12:
            return d
    return None


def job(j) -> dict:
    arm, t, seed, owner, r, pn, D, scope = j
    D = int(D)
    LB._observe()
    LB._PARKED.clear()
    cfg = config(arm, t, seed, owner, r, pn, D, scope)
    out, snaps, bad = CR.run_with_ledger(cfg)
    sids = sorted(snaps[0])
    owners = L.sample_stalls(seed) if arm == "never" else [owner]
    lic = sorted(s for s in sids if snaps[-1][s]["licensed_from"] == owner) if arm != "never" else []
    keep = sids if arm == "never" else [owner, *lic]
    win = range(B_DAY, D + 1)
    rec = {"key": key(j), "arm": arm, "t": t, "seed": seed, "owner": owner, "royalty": float(r), "prior_n": float(pn),
           "days": D, "scope": scope, "licensees": lic, "profit_mismatch": bad,
           "win": E._sums(snaps, keep, win), "all": E._sums(snaps, keep, range(1, D + 1)),
           "stype": {s: snaps[0][s]["stype"] for s in keep},
           "totals": {s: benchmark.stall_total(out, s) for s in owners},
           "rating": {s: [out["days"][d]["brand_ratings"].get(out["days"][d]["brands"][s]) for d in range(D)]
                      for s in [*owners, *lic]},
           "white_label": {s: snaps[-1][s]["white_label"] for s in lic}, "guard": CR.guard(out),
           "digest": hashlib.sha256(dumps(out).encode()).hexdigest()}
    if arm != "never":            # daily ledgers of the owner and its licensees, for the catch-up windows
        rec["daily"] = {s: {f: [int(snaps[d][s][f]) for d in range(D)] for f in DF} for s in keep}
    # day-1 brands' ratings, days 1-10 (the pilot's G4): names in the book at the end of day 1
    d1 = sorted(out["days"][0]["brand_ratings"])
    rec["d1_ratings"] = {n: [out["days"][d]["brand_ratings"].get(n) for d in range(min(B_DAY, D))] for n in d1}
    # reopened deceptive brands on day 20: deceptive-type stalls whose day-20 name came from a reopening rename
    if D >= 20:
        reopened = {x["to"] for d in range(20) for x in out["days"][d]["renames"]}
        held = [out["days"][19]["brands"][s] for s in sids if snaps[19][s]["stype"] == "deceptive"
                and out["days"][19]["brands"][s] in reopened]
        rr = [out["days"][19]["brand_ratings"].get(n) for n in held]
        rec["reopen_d20"] = {"held": len(held), "rated": sum(x is not None for x in rr),
                             "mean": float(np.mean([x for x in rr if x is not None])) if any(x is not None for x in rr)
                             else None}
    if arm == "never":            # the dial reaches new brands of every type: mean rating by stall type (rated only)
        by = {}
        for st in STYPES:
            ss = [s for s in sids if snaps[0][s]["stype"] == st]
            row = []
            for d in range(D):
                v = [out["days"][d]["brand_ratings"].get(out["days"][d]["brands"][s]) for s in ss]
                v = [x for x in v if x is not None]
                row.append(float(np.mean(v)) if v else None)
            by[st] = row
        rec["rating_by_type"] = by
        rec["catches"] = int(sum(snaps[d][s]["catches"] for s in sids for d in range(D)))
    rec["roy_at"] = {_rk(x): {s: int(sum(snaps[d - 1][s]["units"] * int(round(float(x) * snaps[d - 1][s]["price"]))
                                         for d in range(1, D + 1) if snaps[d - 1][s]["licensed_from"] == owner))
                              for s in lic} for x in RATES}
    rec["roy_mismatch"] = sum(snaps[d][s]["roy_paid"] != (0 if arm == "Wg" else snaps[d][s]["units"] *
                                                          int(round(float(r) * snaps[d][s]["price"])))
                              for s in lic for d in range(B_DAY - 1, D))
    rec["dig_trade"] = [hashlib.sha1(repr([(s, *(snaps[d][s][f] for f in ("units", "revenue", "cost", "ad", "fines",
                                                                          "switch", "catches", "price")))
                                           for s in sids]).encode()).hexdigest()[:16] for d in range(D)]
    if arm == "Wg":               # white labels at the genuine tier: base x (1 + premium x (start-of-day rating - 0.5))
        prem = cfg.brands.premium
        cat = {st.sid: st.category for st in BazaarEngine(cfg).stalls}
        miss = 0
        for s in lic:
            base = cfg.pricing.base_price_cents[cat[s]]
            for d in range(B_DAY, D + 1):
                prev = None if d == B_DAY else out["days"][d - 2]["brand_ratings"].get(out["days"][d - 1]["brands"][s])
                if snaps[d - 1][s]["price"] != int(round(base * (1 + prem * (_r(prev) - 0.5)))):
                    miss += 1
        rec["tier_price_miss"] = miss
        rec["tier_price_checked"] = True
    return rec


def levels_at(t, levels):
    if t == "t100" and T100_LEVELS is not None:
        return [lv for lv in levels if lv in T100_LEVELS]
    return list(levels)


def check_jobs_for(check_seed, samples, levels) -> list[tuple]:
    """The no-decision replay: R at t100, royalty 0.10 (shared with the run) and 0.05, 0.25; the current and the
    slowest level."""
    lv = list(levels)
    cells = [levels[lv[0]], levels[lv[-1]]]
    return [("R", "t100", check_seed, s, r, pn, DAYS, SCOPE) for pn in cells for s in samples[check_seed]
            for r in (ROYALTY, *CHECK_RATES)]


def jobs_for(seeds, samples, levels) -> list[tuple]:
    out = []
    for sd in seeds:
        for t in VERS:
            for lv in levels_at(t, levels):
                pn = levels[lv]
                out.append(("never", t, sd, None, ROYALTY, pn, DAYS, SCOPE))
                for s in samples[sd]:
                    for arm in ("R", "Wg"):
                        out.append((arm, t, sd, s, ROYALTY, pn, DAYS, SCOPE))
    return out


def royalty_check(runs, check_seed, samples, levels) -> dict:
    idx = {r["key"]: r for r in runs}
    rows, ok = [], True
    lv = list(levels)
    for name in (lv[0], lv[-1]):
        pn = levels[name]
        for s in samples[check_seed]:
            base = idx[key(("R", "t100", check_seed, s, ROYALTY, pn, DAYS, SCOPE))]
            for r in CHECK_RATES:
                x = idx[key(("R", "t100", check_seed, s, r, pn, DAYS, SCOPE))]
                same_days = sum(a == b for a, b in zip(base["dig_trade"], x["dig_trade"]))
                same_lic = base["licensees"] == x["licensees"]
                roy_diff = base["all"][s]["roy_recv"] != x["all"][s]["roy_recv"]
                exact = x["roy_at"][_rk(r)] == base["roy_at"][_rk(r)] and \
                    sum(x["roy_at"][_rk(r)].values()) == x["all"][s]["roy_recv"]
                good = same_days == DAYS and same_lic and roy_diff and exact
                ok &= good
                rows.append({"level": name, "owner": s, "royalty": r, "days_identical": same_days,
                             "same_licensees": same_lic, "royalties_differ": roy_diff, "recompute_exact": exact,
                             "pass": good})
    return {"pass": ok, "rows": rows}


# ------------------------------------------------------------------ analysis

def _slope(xs, ys):
    pts = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pts) < 2:
        return None
    a = np.array(pts, float)
    return float(np.polyfit(a[:, 0], a[:, 1], 1)[0])


def _jwin(rec, stalls, days) -> int:
    return int(sum(rec["daily"][s]["profit"][d - 1] for s in stalls for d in days))


def fits(xs, ys) -> dict:
    """PS4: least-squares fits of E (cents) on days to 0.9 over the per-seed points. Linear: a + b x. Saturating:
    a + A (1 - exp(-(x - x0) / tau)), x0 = the smallest x (the current speed), tau on a log grid, a and A by least
    squares. RSS, R^2 and AIC = n ln(RSS / n) + 2k."""
    x, y = np.array(xs, float), np.array(ys, float)
    n = len(y)
    tss = float(((y - y.mean()) ** 2).sum())
    b, a = np.polyfit(x, y, 1)
    rss_l = float(((y - (a + b * x)) ** 2).sum())
    x0 = float(x.min())
    best = None
    for tau in np.geomspace(0.25, 1000, 600):
        X = np.column_stack([np.ones(n), 1 - np.exp(-(x - x0) / tau)])
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        rss = float(((y - X @ coef) ** 2).sum())
        if best is None or rss < best[0]:
            best = (rss, float(tau), float(coef[0]), float(coef[1]))
    aic = lambda rss, k: n * math.log(rss / n) + 2 * k if rss > 0 else None
    return {"n": n, "linear": {"a": float(a), "b": float(b), "rss": rss_l, "r2": 1 - rss_l / tss if tss else None,
                               "aic": aic(rss_l, 2)},
            "saturating": {"a": best[2], "A": best[3], "tau": best[1], "x0": x0, "rss": best[0],
                           "r2": 1 - best[0] / tss if tss else None, "aic": aic(best[0], 3),
                           "tau_at_grid_edge": best[1] in (0.25, 1000.0)}}


def analyse(runs, seeds, samples, levels, days_x) -> dict:
    idx = {(r["arm"], r["t"], r["seed"], r["owner"], _rk(r["royalty"]), _pk(r["prior_n"])): r for r in runs
           if r["days"] == DAYS and r["scope"] == SCOPE}
    res: dict = {"seeds": seeds, "levels": levels, "days_x": days_x, "cells": {}, "never": {}, "pred": {},
                 "guard": {}, "flags": [], "identity": {}}
    jbad = jmax = 0
    tier_miss = tier_checked = 0
    wresid = 0.0
    for t in VERS:
        for lv in levels_at(t, levels):
            pn = levels[lv]
            ks = ["J_never", "J_R", "J_Wg", "E", "composition", "licensing", *SPLIT, "split_resid", "E_catch", "E_after",
                  "catch_minus_after", "catch_share", "owner_days", "owner_reached", "days_label", "share_label_reached",
                  "owner_gain_Wg", *[f"owner_gain_R_{_rk(x)}" for x in RATES],
                  *[f"lic_profit_R_{_rk(x)}" for x in RATES], "lic_profit_Wg", "lic_profit_never",
                  "lic_R_minus_Wg_0.10", "lic_units_R", "lic_units_Wg", "lic_units_never", "lic_price_R", "lic_price_Wg",
                  "owner_units_R", "owner_units_Wg", "owner_units_never", "owner_rating_day10_never"]
            per = {k: [] for k in ks}
            paths = {k: [] for k in ("never", "R", "Wg_owner", "Wg_labels")}
            for sd in seeds:
                nv = idx[("never", t, sd, None, _rk(ROYALTY), _pk(pn))]
                acc = {k: [] for k in per}
                for s in samples[sd]:
                    R = idx[("R", t, sd, s, _rk(ROYALTY), _pk(pn))]
                    Wg = idx[("Wg", t, sd, s, _rk(ROYALTY), _pk(pn))]
                    lic = R["licensees"]
                    if Wg["licensees"] != lic or len(lic) != N_LIC or not all(Wg["white_label"].values()):
                        res["flags"].append(f"{lv}|{t}|{sd}|{s}: R and W_g licensees differ or are not 6 white labels")
                    tier_checked += 1
                    tier_miss += Wg["tier_price_miss"]
                    stalls = [s, *lic]
                    Jr, Jg, Jn = E._J(R, stalls), E._J(Wg, stalls), E._J(nv, stalls)
                    for a_, b_ in (Jr, Jg, Jn):
                        jbad += a_ != b_
                        jmax += 1
                    acc["J_R"].append(Jr[0]); acc["J_Wg"].append(Jg[0]); acc["J_never"].append(Jn[0])
                    acc["E"].append(Jr[0] - Jg[0]); acc["composition"].append(Jg[0] - Jn[0])
                    acc["licensing"].append(Jr[0] - Jn[0])
                    sp = E._split(R, Wg, s, lic)
                    for k in SPLIT:
                        acc[k].append(sp[k])
                    acc["split_resid"].append(Jr[0] - Jg[0] - sum(sp.values()))
                    # catch-up window: days 10 .. the day the white labels' mean rating first reaches 0.9
                    cd = catch_day(Wg, lic)
                    end = DAYS if cd is None else cd
                    cw, aw = range(B_DAY, end + 1), range(end + 1, DAYS + 1)
                    ec = _jwin(R, stalls, cw) - _jwin(Wg, stalls, cw)
                    ea = _jwin(R, stalls, aw) - _jwin(Wg, stalls, aw)
                    wresid = max(wresid, abs(ec + ea - (Jr[0] - Jg[0])))
                    acc["E_catch"].append(ec); acc["E_after"].append(ea); acc["catch_minus_after"].append(ec - ea)
                    acc["owner_days"].append(None if cd is None else cd - B_DAY + 1)
                    acc["owner_reached"].append(0.0 if cd is None else 1.0)
                    dd = [days_to(Wg["rating"][l]) for l in lic]
                    got = [x for x in dd if x is not None]
                    acc["days_label"].append(float(np.mean(got)) if got else None)
                    acc["share_label_reached"].append(len(got) / len(dd))
                    never_tot = nv["totals"][s]
                    roy_base = sum(R["roy_at"][_rk(ROYALTY)].values())
                    if roy_base != R["all"][s]["roy_recv"]:
                        res["flags"].append(f"{lv}|{t}|{sd}|{s}: recomputed royalties at 0.10 differ from the engine's")
                    for x in RATES:
                        rx = sum(R["roy_at"][_rk(x)].values())
                        acc[f"owner_gain_R_{_rk(x)}"].append(R["totals"][s] - roy_base + rx - never_tot)
                        acc[f"lic_profit_R_{_rk(x)}"].append(float(np.mean(
                            [R["win"][l]["profit"] + R["roy_at"][_rk(ROYALTY)][l] - R["roy_at"][_rk(x)][l] for l in lic])))
                    acc["owner_gain_Wg"].append(Wg["totals"][s] - never_tot)
                    acc["lic_profit_Wg"].append(float(np.mean([Wg["win"][l]["profit"] for l in lic])))
                    acc["lic_profit_never"].append(float(np.mean([nv["win"][l]["profit"] for l in lic])))
                    acc["lic_R_minus_Wg_0.10"].append(acc[f"lic_profit_R_{_rk(ROYALTY)}"][-1] - acc["lic_profit_Wg"][-1])
                    for arm, rec in (("R", R), ("Wg", Wg), ("never", nv)):
                        acc[f"lic_units_{arm}"].append(sum(rec["win"][l]["units"] for l in lic))
                        acc[f"owner_units_{arm}"].append(rec["win"][s]["units"])
                    for arm, rec in (("R", R), ("Wg", Wg)):
                        u = sum(rec["win"][l]["units"] for l in lic)
                        acc[f"lic_price_{arm}"].append(sum(rec["win"][l]["revenue"] for l in lic) / u if u else None)
                    acc["owner_rating_day10_never"].append(_r(nv["rating"][s][B_DAY - 1]))
                    paths["never"].append([_r(x) for x in nv["rating"][s]])
                    paths["R"].append([_r(x) for x in R["rating"][s]])
                    paths["Wg_owner"].append([_r(x) for x in Wg["rating"][s]])
                    paths["Wg_labels"].append([float(np.mean([_r(Wg["rating"][l][d]) for l in lic])) for d in range(DAYS)])
                for k in per:
                    if k == "catch_share":
                        continue
                    vals = [v for v in acc[k] if v is not None]
                    per[k].append(float(np.mean(vals)) if vals else None)
                e, c_ = per["E"][-1], per["E_catch"][-1]
                per["catch_share"].append(c_ / e if e else None)
            cell = {k: mean_ci(v) for k, v in per.items()}
            cell["per_seed"] = per
            cell["paths"] = {k: [float(x) for x in np.mean(v, axis=0)] for k, v in paths.items()}
            res["cells"][f"{lv}|{t}"] = cell
            # never chains at this speed
            nvk = ("profit_genuine", "profit_seconds", "profit_deceptive", "catches", "owner_total", "reopen_d20",
                   *[f"rating_{st}_d{d}" for st in STYPES for d in (10, 30, 60)])
            nvd = {k: [] for k in nvk}
            for sd in seeds:
                rec = idx[("never", t, sd, None, _rk(ROYALTY), _pk(pn))]
                for st in STYPES:
                    nvd[f"profit_{st}"].append(sum(rec["all"][s]["profit"] for s in rec["all"] if rec["stype"][s] == st))
                    for d in (10, 30, 60):
                        nvd[f"rating_{st}_d{d}"].append(rec["rating_by_type"][st][d - 1])
                nvd["catches"].append(rec["catches"])
                nvd["owner_total"].append(float(np.mean([rec["totals"][s] for s in samples[sd]])))
                nvd["reopen_d20"].append(rec["reopen_d20"]["mean"])
            res["never"][f"{lv}|{t}"] = {"per_seed": nvd, **{k: mean_ci(v) for k, v in nvd.items()}}
    res["identity"] = {"J_checked": jmax, "J_mismatch": jbad,
                       "split_resid_max_abs": max(abs(x) for c in res["cells"].values()
                                                  for x in c["per_seed"]["split_resid"] if x is not None),
                       "window_resid_max_abs": wresid, "tier_price_chains": tier_checked, "tier_price_miss": tier_miss}
    if jbad:
        res["flags"].append(f"J identity fails in {jbad} of {jmax} owner-chains")
    if wresid:
        res["flags"].append(f"catch-up and after windows do not add up to E (largest residual {wresid} cents)")
    if tier_miss or not tier_checked:
        res["flags"].append(f"genuine-tier price check: {tier_miss} misses in {tier_checked} chains checked")
    # predictions
    C = res["cells"]
    lv40 = levels_at("t40", levels)
    slowest = lv40[-1]
    xs = [days_x[lv] for lv in lv40]
    Ep = lambda c: C[c]["per_seed"]["E"]
    P = {}
    sl = [_slope(xs, [Ep(f"{lv}|t40")[i] for lv in lv40]) for i in range(len(seeds))]
    P["PS1"] = {**mean_ci(sl), "sign": +1, "per_seed": sl, "label": "t40: slope of E over days to 0.9 ($ per day)"}
    c_s = f"{slowest}|t40"
    P["PS2"] = {**C[c_s]["catch_minus_after"], "sign": +1,
                "label": f"t40, {slowest}: E in the catch-up window − E after it (> 0 ⇔ more than half of E in catch-up)"}
    e_cur, e_slow = Ep(f"{CURRENT}|t40"), Ep(c_s)
    ps3 = [None if a is None or b is None else 0.1 * b - a for a, b in zip(e_cur, e_slow)]
    P["PS3"] = {**mean_ci(ps3), "sign": +1, "per_seed": ps3,
                "label": f"t40: 10% of E at {slowest} − E at the current speed (> 0 ⇔ E current < 10% of E slowest)"}
    for k in P:
        P[k]["verdict"] = _verdict(P[k], P[k]["sign"])
    ptx, pty = [], []
    for lv in lv40:
        for v in Ep(f"{lv}|t40"):
            if v is not None:
                ptx.append(days_x[lv])
                pty.append(v)
    res["fits"] = fits(ptx, pty)
    res["ps5"] = {lv: C[f"{lv}|t100"]["E"] for lv in levels_at("t100", levels)}
    ps6 = {lv: C[f"{lv}|t40"]["lic_R_minus_Wg_0.10"] for lv in lv40}
    above = [lv for lv in lv40 if ps6[lv]["lo"] is not None and ps6[lv]["lo"] > 0]
    pos = [lv for lv in lv40 if ps6[lv]["mean"] is not None and ps6[lv]["mean"] > 0]
    res["ps6"] = {"by_level": ps6, "slowest_interval_above_0": above[-1] if above else None,
                  "slowest_mean_above_0": pos[-1] if pos else None,
                  "fastest_interval_above_0": above[0] if above else None}
    res["pred"] = P
    groups = {}
    for r in runs:
        groups.setdefault(f"{r['arm']}|{r['t']}|p{_pk(r['prior_n'])}|{r['days']}d|{r['scope']}", []).append(r)
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
    lv, dx = res["levels"], res["days_x"]
    L_ = ["# Brand Equity speed: reputation with slow new brands, 60 days", "",
          "Spec: the task \"engine 0.19.0 (two keys), calibration, pilot, sizing\" (2026-11-17); predictions fixed "
          "2026-11-17, before any run. Background: `runs/brand_equity_tier_summary.md`. Calibration: "
          "`runs/calibration_brand_equity_speed.md`. Pilot gate: `runs/pilot_brand_equity_speed.md`.", "",
          "## Design (prespecified)", "",
          "- Question: what does the owner's reputation earn over a market long enough for new brands to catch up, when "
          "only new brands' ratings form slowly?",
          "- Engine 0.19.0. Market as the 0.18.0 run: the licensing market, detect_scale 1, owner not liable, "
          "`licensing.white_label_tier` genuine, royalty 0.10, N 6 from day 10, 3 owners per seed from "
          "`default_rng([seed, 17])`; but `market.days` 60 (D 60, known to sellers) and `ratings.prior_scope` new: the "
          "prior reaches only brands created on day 2 or later (white labels, reopening names); the owner and every "
          "original stall rate as with prior_n 0.",
          "- Arms: never, R (licensees under the owner's brand), W_g (white labels at the genuine tier). Quality: "
          "contract only.",
          "- Speeds (`ratings.prior_n`, from the calibration; days for a W_g white label to reach 0.9 at t40): " +
          "; ".join(f"{k}: prior_n {lv[k]:g}, {dx[k]:.2f} days" for k in lv) + ".",
          "- Verification: t40 (locals inspect) and t100" + ("" if T100_LEVELS is None else
                                                           f" (t100 at {', '.join(T100_LEVELS)} only, cut by the timing "
                                                           "gate)") + ". Seeds " + meta["seeds_txt"] +
          ", fresh, paired across all cells.",
          "- Measures per owner: J = owner + 6 licensees' profit, days 10–60. Reputation effect E = J(R) − J(W_g), with "
          "the five-part split. E by window: catch-up = days 10 through the day the owner's white labels first reach a "
          "mean rating of 0.9 (end of day, unrated = 0.5), after = the rest. Days to 0.9 per owner from W_g. Owner's "
          "gain at 0.05–0.25 by the exact recompute, after the no-decision replay check. Licensee profit under R and "
          "W_g at each royalty. Never chains across speeds.",
          "- Predictions (verbatim from the spec):", *[f"  - {p}" for p in PREDICTIONS],
          "- Analysis: per seed the mean over 3 owners; mean and 95% t over seeds; unadjusted. PS1's slope is fitted per "
          "seed over the calibration's days to 0.9. PS2 is tested as E(catch-up) − E(after) > 0, which is the same as "
          "more than half of E in catch-up; PS3 as 0.1 × E(slowest) − E(current) > 0, per seed.", ""]
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
    L_ += ["## Gate", "", meta.get("gate", ""), "",
           f"Genuine-tier prices: every W_g white label's posted price equals base × (1 + 0.4 × (start-of-day rating − "
           f"0.5)) on every day from 10: {idn['tier_price_miss']} misses in {idn['tier_price_chains']} chains.", "",
           "### The royalty enters no decision", "",
           "Code: as Brand Equity; 0.19.0 adds no reader of `licensing.royalty`, and the prior enters ratings only. "
           f"Replay at seed {meta.get('check_seed')}, t100, R at royalty 0.05 and 0.25 against 0.10:", "",
           *_t(["Speed", "Owner", "Royalty", "Days identical", "Same licensees", "Royalties differ", "Recompute exact",
                "Pass"],
               [[x["level"], x["owner"], f"{x['royalty']:.2f}", f"{x['days_identical']}/{DAYS}",
                 "yes" if x["same_licensees"] else "no", "yes" if x["royalties_differ"] else "no",
                 "yes" if x["recompute_exact"] else "no", "yes" if x["pass"] else "**no**"] for x in rc["rows"]]),
           "", f"Result: **{'pass' if rc['pass'] else 'FAIL'}**.", "",
           f"J identity: {idn['J_checked'] - idn['J_mismatch']}/{idn['J_checked']} owner-chains to the cent; largest "
           f"split residual {idn['split_resid_max_abs']:.6f} cents; catch-up + after = E to "
           f"{idn['window_resid_max_abs']:.0f} cents.", ""]
    P, C = res["pred"], res["cells"]
    F = res["fits"]
    L_ += ["## Predictions", "",
           "$ per owner over days 10–60 (per-seed mean of 3 owners). PS1–PS3 confirmatory; PS4–PS6 exploratory.", "",
           *_t(["Prediction", "Estimate ($)", "Verdict"],
               [[f"**{k}**: {P[k]['label']}", _ci(P[k], _d), P[k]["verdict"]] for k in ("PS1", "PS2", "PS3")]), ""]
    lv40 = levels_at("t40", lv)
    sl_ = lv40[-1]
    e_c, e_s = C[f"{CURRENT}|t40"]["E"]["mean"], C[f"{sl_}|t40"]["E"]["mean"]
    cs = C[f"{sl_}|t40"]
    L_ += [f"PS2 share: E in catch-up / E at {sl_}, t40 = {_ci(cs['catch_share'], _num(2), False)} (per-seed ratios; "
           f"ratio of means {cs['E_catch']['mean'] / cs['E']['mean']:.2f})." if cs["E"]["mean"] else "",
           f"PS3 ratio: E current / E {sl_} at t40 = {e_c / e_s:.3f} (ratio of means)." if e_s else "", "",
           "**PS4** (exploratory): fits of E on days to 0.9 at t40, over the per-seed points "
           f"(n = {F['n']}):", "",
           *_t(["Fit", "Parameters", "RSS ($²)", "R²", "AIC"],
               [["Linear: a + b x", f"a = {_d(F['linear']['a'], True)}, b = {_d(F['linear']['b'], True)} per day",
                 f"{F['linear']['rss'] / 1e4:,.0f}", _num(3)(F["linear"]["r2"]), _num(1)(F["linear"]["aic"])],
                ["Saturating: a + A (1 − exp(−(x − x₀)/τ))",
                 f"a = {_d(F['saturating']['a'], True)}, A = {_d(F['saturating']['A'], True)}, τ = "
                 f"{F['saturating']['tau']:.2f} days, x₀ = {F['saturating']['x0']:.2f}"
                 + (" (τ at the grid edge)" if F["saturating"]["tau_at_grid_edge"] else ""),
                 f"{F['saturating']['rss'] / 1e4:,.0f}", _num(3)(F["saturating"]["r2"]), _num(1)(F["saturating"]["aic"])]]),
           "", "**PS5** (exploratory): E at t100 by speed:", "",
           *_t(["Speed", "Days to 0.9 (calibration, t40)", "E at t100 ($)"],
               [[k, f"{dx[k]:.2f}", _ci(v, _d)] for k, v in res["ps5"].items()]), "",
           "**PS6** (exploratory): licensee profit under R at 0.10 − under W_g, per licensee, days 10–60, t40:", "",
           *_t(["Speed", "R at 0.10 − W_g ($)"], [[k, _ci(v, _d)] for k, v in res["ps6"]["by_level"].items()]), "",
           f"Slowest speed with the interval above 0: {res['ps6']['slowest_interval_above_0'] or 'none'}; slowest with "
           f"the mean above 0: {res['ps6']['slowest_mean_above_0'] or 'none'}; fastest with the interval above 0: "
           f"{res['ps6']['fastest_interval_above_0'] or 'none'}.", ""]
    L_ += ["## Joint profit and its parts", "",
           "J per owner and its 6 licensees, days 10–60, $.", "",
           *_t(["Cell", "J never", "J W_g", "J R", "Composition W_g − never", "E = R − W_g", "E catch-up", "E after"],
               [[_lab(c), _ci(v["J_never"], _d), _ci(v["J_Wg"], _d), _ci(v["J_R"], _d), _ci(v["composition"], _d),
                 _ci(v["E"], _d), _ci(v["E_catch"], _d), _ci(v["E_after"], _d)] for c, v in C.items()]), "",
           "E split (R − W_g, $; the parts add up to E):", "",
           *_t(["Cell", *[SPLIT_LAB[k] for k in SPLIT]], [[_lab(c), *[_ci(v[k], _d) for k in SPLIT]] for c, v in C.items()]),
           "", "Units and prices, days 10–60:", "",
           *_t(["Cell", "Licensee units never / W_g / R", "Licensee mean price W_g / R ($)", "Owner units never / W_g / R"],
               [[_lab(c), " / ".join(_num(1)(v[f"lic_units_{a}"]["mean"]) for a in ("never", "Wg", "R")),
                 " / ".join(_d(v[f"lic_price_{a}"]["mean"]) for a in ("Wg", "R")),
                 " / ".join(_num(1)(v[f"owner_units_{a}"]["mean"]) for a in ("never", "Wg", "R"))] for c, v in C.items()]),
           ""]
    L_ += ["## Owner's gain and licensee profit by royalty", "",
           "Owner's gain = owner's 60-day profit − never at the same speed. R by the exact recompute; white labels pay no "
           "royalty. Licensee profit: per licensee, days 10–60.", "",
           *_t(["Cell", *[f"Owner gain R, {x:.2f}" for x in RATES], "Owner gain W_g"],
               [[_lab(c), *[_ci(v[f"owner_gain_R_{_rk(x)}"], _d) for x in RATES], _ci(v["owner_gain_Wg"], _d)]
                for c, v in C.items()]), "",
           *_t(["Cell", "Licensee profit never", "W_g", *[f"R, {x:.2f}" for x in RATES]],
               [[_lab(c), _ci(v["lic_profit_never"], _d), _ci(v["lic_profit_Wg"], _d),
                 *[_ci(v[f"lic_profit_R_{_rk(x)}"], _d) for x in RATES]] for c, v in C.items()]), ""]
    L_ += ["## Rating speed", "",
           "Per owner: days from day 10 (= 1) until its W_g white labels' mean rating first reaches 0.9 (the end of the "
           "catch-up window) and the share of owners whose labels reach it by day 60; per label: mean days to 0.9 over "
           "the labels that reach it and the share that do; the owner's own rating at the end of day 10 (never).", "",
           *_t(["Cell", "Owner: days to 0.9", "Owners reaching", "Label: days to 0.9", "Labels reaching",
                "Owner rating day 10"],
               [[_lab(c), _ci(v["owner_days"], _num(1), signed=False), _ci(v["owner_reached"], _num(2), signed=False),
                 _ci(v["days_label"], _num(1), signed=False), _ci(v["share_label_reached"], _num(2), signed=False),
                 _ci(v["owner_rating_day10_never"], _num(3), signed=False)] for c, v in C.items()]), "",
           "Rating paths: mean over owners (unrated = 0.5), end of days 1, 9, 10, 12, 15, 20, 30, 40, 50, 60.", ""]
    rows = []
    marks = (1, 9, 10, 12, 15, 20, 30, 40, 50, 60)
    for c, v in C.items():
        for k, lab in (("never", "owner, never"), ("R", "owner brand, R"), ("Wg_owner", "owner brand, W_g"),
                       ("Wg_labels", "white labels, W_g")):
            ys = v["paths"][k]
            rows.append([_lab(c), lab, *[f"{ys[d - 1]:.3f}" for d in marks]])
    L_ += [*_t(["Cell", "Series", *[str(d) for d in marks]], rows), ""]
    NV = res["never"]
    L_ += ["## Never chains across speeds", "",
           "The prior reaches every new brand, reopened deceptive names included. Whole-market 60-day profit by stall "
           "type ($, all stalls of the type), catches, the sampled owners' mean 60-day profit, the mean day-20 rating of "
           "deceptive stalls' reopened names, and the mean rating of rated brands by type (days 10, 30, 60).", "",
           *_t(["Never chain", "Genuine profit", "Seconds profit", "Deceptive profit", "Catches", "Owner profit",
                "Reopened d20", "Genuine d10/30/60", "Seconds d10/30/60", "Deceptive d10/30/60"],
               [[_lab(k), _ci(v["profit_genuine"], _d, False), _ci(v["profit_seconds"], _d, False),
                 _ci(v["profit_deceptive"], _d, False), _ci(v["catches"], _num(0), False), _ci(v["owner_total"], _d, False),
                 _ci(v["reopen_d20"], _num(3), False),
                 *[" / ".join(_num(3)(v[f"rating_{st}_d{d}"]["mean"]) for d in (10, 30, 60)) for st in STYPES]]
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

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="330-349")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--outdir", default="runs")
    ap.add_argument("--tests", default="")
    ap.add_argument("--gate", default="")
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
        raise SystemExit("the main run uses seeds 330-349 only")
    os.makedirs(a.outdir, exist_ok=True)
    log = CR.file_logger(os.path.join(a.outdir, "brand_equity_speed_run.log"))
    t0 = time.time()
    check_seed = seeds[0]
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
            "command": " ".join(["python -m analysis.brand_equity_speed", *sys.argv[1:]]), "tests": a.tests,
            "gate": a.gate or "Pilot gate: see `runs/pilot_brand_equity_speed.md`.", "check_seed": check_seed,
            "levels": LEVELS, "days_x": DAYS_TO_TARGET, "t100_levels": T100_LEVELS,
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
            "workers": a.workers, "load_start": _load(), "mem_start": memory_state(), "seeds_txt": a.seeds}
    log(f"brand equity speed: engine {ENGINE_VERSION}, commit {meta['git']['commit'][:7]}, seeds {a.seeds}, "
        f"levels {LEVELS}, t100 levels {T100_LEVELS or 'all'}")
    samples = {sd: L.sample_stalls(sd) for sd in seeds}
    meta["samples"] = {str(k): v for k, v in samples.items()}
    cache = os.path.join(a.outdir, "brand_equity_speed_cache.jsonl")
    check_jobs = check_jobs_for(check_seed, samples, LEVELS)
    cr, p0 = CR.run_chains(a, check_jobs, cache, log, job, key)
    rc = royalty_check(cr, check_seed, samples, LEVELS)
    log(f"royalty check: {'pass' if rc['pass'] else 'FAIL'}")
    if not rc["pass"]:
        with open(os.path.join(a.outdir, "brand_equity_speed_royalty_check.json"), "w", encoding="utf-8") as f:
            json.dump(rc, f, indent=1)
        raise SystemExit("royalty check failed: a decision depends on the royalty; stop and report")
    del cr
    runs, pauses = CR.run_chains(a, jobs_for(seeds, samples, LEVELS), cache, log, job, key)
    res = analyse(runs, seeds, samples, LEVELS, DAYS_TO_TARGET)
    extra = len([j for j in check_jobs if _rk(j[4]) != _rk(ROYALTY)])
    meta.update(chains=len(runs) + extra, pauses=pauses + p0, wall_h=(time.time() - t0) / 3600, load_end=_load(),
                mem_end=memory_state())
    slim = [{k: v for k, v in r.items() if k not in ("daily", "dig_trade", "d1_ratings")} for r in runs]
    with gzip.open(os.path.join(a.outdir, "brand_equity_speed.json.gz"), "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "royalty_check": rc, "results": res, "chains": slim}, f, separators=(",", ":"))
    with open(os.path.join(a.outdir, "brand_equity_speed.csv"), "w", encoding="utf-8") as f:
        cols = ["J_never", "J_Wg", "J_R", "E", "composition", *SPLIT, "E_catch", "E_after", "owner_days",
                f"owner_gain_R_{_rk(ROYALTY)}", "owner_gain_Wg", f"lic_profit_R_{_rk(ROYALTY)}", "lic_profit_Wg"]
        f.write("level,prior_n,verification,seed," + ",".join(cols) + "\n")
        for c, v in res["cells"].items():
            lv, t = c.split("|")
            for i, sd in enumerate(seeds):
                vals = [v["per_seed"][k][i] for k in cols]
                f.write(",".join([lv, f"{LEVELS[lv]:g}", t, str(sd),
                                  *["" if x is None else f"{x:.2f}" for x in vals]]) + "\n")
    sp = os.path.join(a.outdir, "brand_equity_speed_summary.md")
    old = open(sp, encoding="utf-8").read() if os.path.exists(sp) else None
    with open(sp, "w", encoding="utf-8") as f:
        f.write(report(res, rc, meta, old))
    log(f"done; {len(res['flags'])} flags; wall {meta['wall_h']:.2f} h")
    return 2 if res["flags"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
