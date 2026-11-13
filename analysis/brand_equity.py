"""Run 2: Brand Equity (rule-based only). Spec "Brand Equity" (2026-11-12); predictions written 2026-11-12, before
any run. Prepared, not launched: the pilot gate (analysis/pilot_canal_equity.py, runs/pilot_canal_equity.md) gives
the projected wall clock; runs/queue_canal_then_equity.sh runs this after Canal Street.

Question: what does a reputation earn, apart from the extra stalls and the quality behind it?

Engine 0.17.0. Market as the licensing run (analysis/licensing.py), detect_scale 1, owner not liable. Owners: 3 per
seed from default_rng([seed, 17]) (verification.sample_stalls), as before. Licence option fixed: N 6 from day 10.
Arms per owner: never; R = licensees under the owner's brand (licensing.brand "owner", royalty 0.10); W = the same
stalls under white labels (licensing.brand "white_label": one fresh unrated brand per licensee, no royalty).
Conditions: licence quality {contract, cheap} x verification {t40: tourist share 0.4 with locals inspecting; t100}.
Seeds 300-329 (30), paired. One never chain per seed and verification level serves both qualities and all owners
(licensing dials are inert without a schedule).

Primary measure, per owner: joint profit J = owner profit + its 6 licensees' profit, day 10 to 30 (royalties
cancel). Name effect = J(R) - J(W). Composition effect = J(W) - J(never), the same 6 stalls in the never chain.
The name effect is split exactly into: owner own sales (owner revenue - cost - ad spend, R - W), licensee sales
((units R - units W) x (mean price W - unit cost), summed over licensees), licensee prices (units R x (mean price R
- mean price W)), licensee ad spend (-(ad R - ad W)) and fines (-(fines R - fines W), owner and licensees).
Owner's gain (owner's 30-day profit - never) at royalty 0.05, 0.10, 0.15, 0.25 by the exact recompute
(owner profit_r = profit_0.10 - royalties received at 0.10 + sum over licensee-days of units x round(r x price)),
after the same no-decision check as the licensing checks (seed 300, t100, both qualities, 3 owners, R at royalty
0.05 and 0.25 against 0.10: every stall's day ledger except royalties and profit must be identical).
Rating paths of R (the owner's brand) and of the white labels.

Predictions (fixed 2026-11-12, before any run):
  PQ1 (confirmatory): contract, t40: name effect > 0.
  PQ2 (confirmatory): contract: name effect at t40 - at t100 > 0 (the reputation earns through buyers who read
      ratings).
  PQ3 (confirmatory): t40: name effect, contract - cheap > 0 (renting a reputation earns more than spending it).
  PQ4 (exploratory): contract, t100: name effect <= 0 (tourists see the premium price, not the rating).
  PQ5 (exploratory): harm and benefit by buyer profile, R - W.
Analysis: per seed the mean over 3 owners; mean and 95% t over seeds; unadjusted.

    .venv/bin/python -m analysis.brand_equity --seeds 300-329 --tests "..."                     # main run
    .venv/bin/python -m analysis.brand_equity --pilot --seeds 900-902 --outdir runs/pilot_equity # pilot
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
N_LIC, B_DAY = 6, 10
ROYALTY = 0.10
RATES = (0.05, 0.10, 0.15, 0.25)
QUALS = ("contract", "cheap")
VERS = ("t40", "t100")
WINDOW = range(B_DAY, DAYS + 1)
MAIN_SEEDS = set(range(300, 330))
PILOT_SEEDS = set(range(900, 903))
CHECK_RATES = (0.05, 0.25)
VLAB = L.VLAB
PREDICTIONS = [
    "PQ1 (confirmatory): contract, t40: name effect > 0.",
    "PQ2 (confirmatory): contract: name effect at t40 − at t100 > 0 (the reputation earns through buyers who read "
    "ratings).",
    "PQ3 (confirmatory): t40: name effect, contract − cheap > 0 (renting a reputation earns more than spending it).",
    "PQ4 (exploratory): contract, t100: name effect ≤ 0 (tourists see the premium price, not the rating).",
    "PQ5 (exploratory): harm and benefit by buyer profile, R − W.",
]
SPLIT = ("owner_sales", "licensee_sales", "licensee_prices", "licensee_ad", "fines")
SPLIT_LAB = {"owner_sales": "Owner own sales", "licensee_sales": "Licensee sales", "licensee_prices": "Licensee prices",
             "licensee_ad": "Licensee ad spend", "fines": "Fines"}


def _rk(r) -> str:
    return f"{float(r):.2f}"


def config(arm, quality, t, seed, owner, r=ROYALTY):
    """arm: "never" | "R" | "W"."""
    q = "cheap" if arm == "never" else quality
    ov = [*L.overrides(t, 1.0, q, False), f"licensing.royalty={float(r)!r}",
          f"licensing.brand={'white_label' if arm == 'W' else 'owner'}", f"seed={seed}"]
    c = load(None, ov, mode="bazaar")
    return benchmark.licence_config(c, None if arm == "never" else owner, NEVER if arm == "never" else (N_LIC, B_DAY))


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ chains: job = (arm, quality, t, seed, owner, r)

def key(j) -> str:
    arm, q, t, sd, s, r = j
    return f"{arm}|{q}|{t}|{sd}|{s}|{_rk(r)}"


def _sums(snaps, sids, days) -> dict:
    return {s: {f: int(sum(snaps[d - 1][s][f] for d in days)) for f in CR.FIELDS[:10]} for s in sids}


def job(j) -> dict:
    arm, q, t, seed, owner, r = j
    LB._observe()
    LB._PARKED.clear()
    tap = ProfileTap([])
    out, snaps, bad = CR.run_with_ledger(config(arm, q, t, seed, owner, r), log=tap)
    sids = sorted(snaps[0])
    owners = L.sample_stalls(seed) if arm == "never" else [owner]
    lic = sorted(s for s in sids if snaps[-1][s]["licensed_from"] == owner) if arm != "never" else []
    keep = sids if arm == "never" else [owner, *lic]
    rec = {"key": key(j), "arm": arm, "quality": q, "t": t, "seed": seed, "owner": owner, "royalty": float(r),
           "licensees": lic, "profit_mismatch": bad,
           "win": _sums(snaps, keep, WINDOW), "all30": _sums(snaps, keep, range(1, DAYS + 1)),
           "stype": {s: snaps[0][s]["stype"] for s in keep},
           "totals": {s: benchmark.stall_total(out, s) for s in owners},
           "rating": {s: [out["days"][d]["brand_ratings"].get(out["days"][d]["brands"][s]) for d in range(DAYS)]
                      for s in [*owners, *lic]},
           "brands_day30": {s: out["days"][-1]["brands"][s] for s in [*owners, *lic]},
           "units_daily": {s: [snaps[d][s]["units"] for d in range(DAYS)] for s in owners},
           "white_label": {s: snaps[-1][s]["white_label"] for s in lic},
           "profile": {str(k): v for k, v in sorted(tap.days.items())}, "guard": CR.guard(out),
           "digest": hashlib.sha256(dumps(out).encode()).hexdigest()}
    # royalties per licensee at every rate, from the licensee-day ledgers (units x round(r x price))
    rec["roy_at"] = {_rk(x): {s: int(sum(snaps[d - 1][s]["units"] * int(round(float(x) * snaps[d - 1][s]["price"]))
                                         for d in range(1, DAYS + 1) if snaps[d - 1][s]["licensed_from"] == owner))
                              for s in lic} for x in RATES}
    rec["roy_mismatch"] = sum(snaps[d][s]["roy_paid"] != (0 if arm == "W" else snaps[d][s]["units"] *
                                                          int(round(float(r) * snaps[d][s]["price"])))
                              for s in lic for d in range(B_DAY - 1, DAYS))
    # per-day trading digest (everything but royalties and profit) for the no-decision check
    rec["dig_trade"] = [hashlib.sha1(repr([(s, *(snaps[d][s][f] for f in ("units", "revenue", "cost", "ad", "fines",
                                                                          "switch", "catches", "price")))
                                           for s in sids]).encode()).hexdigest()[:16] for d in range(DAYS)]
    rec["licensee_q_pitch_price_day10"] = {s: snaps[B_DAY - 1][s]["price"] for s in lic}
    return rec


def jobs_for(seeds, samples, check_seed=None) -> list[tuple]:
    out = []
    if check_seed is not None:
        for q in QUALS:
            for s in samples[check_seed]:
                for r in CHECK_RATES:
                    out.append(("R", q, "t100", check_seed, s, r))
    for sd in seeds:
        for t in VERS:
            out.append(("never", "-", t, sd, None, ROYALTY))
        for q in QUALS:
            for t in VERS:
                for s in samples[sd]:
                    for arm in ("R", "W"):
                        out.append((arm, q, t, sd, s, ROYALTY))
    return out


# ------------------------------------------------------------------ the no-decision check

def royalty_check(runs, check_seed, samples) -> dict:
    idx = {r["key"]: r for r in runs}
    rows, ok = [], True
    for q in QUALS:
        for s in samples[check_seed]:
            base = idx[key(("R", q, "t100", check_seed, s, ROYALTY))]
            for r in CHECK_RATES:
                x = idx[key(("R", q, "t100", check_seed, s, r))]
                same_days = sum(a == b for a, b in zip(base["dig_trade"], x["dig_trade"]))
                same_lic = base["licensees"] == x["licensees"]
                win_ok = all(base["win"][st][f] == x["win"][st][f] for st in base["win"]
                             for f in ("units", "revenue", "cost", "ad", "fines", "switch", "catches"))
                roy_diff = base["all30"][s]["roy_recv"] != x["all30"][s]["roy_recv"]
                exact = x["roy_at"][_rk(r)] == base["roy_at"][_rk(r)] and \
                    sum(x["roy_at"][_rk(r)].values()) == x["all30"][s]["roy_recv"]
                good = same_days == DAYS and same_lic and win_ok and roy_diff and exact
                ok &= good
                rows.append({"quality": q, "owner": s, "royalty": r, "days_identical": same_days, "same_licensees": same_lic,
                             "windows_identical": win_ok, "royalties_differ": roy_diff, "recompute_exact": exact,
                             "pass": good})
    return {"pass": ok, "rows": rows}


# ------------------------------------------------------------------ analysis

def _J(rec, stalls) -> tuple[int, int]:
    """(J from stall profit, J from revenue - cost - ad - fines - switch): equal when royalties cancel."""
    a = sum(rec["win"][s]["profit"] for s in stalls)
    b = sum(rec["win"][s]["revenue"] - rec["win"][s]["cost"] - rec["win"][s]["ad"] - rec["win"][s]["fines"]
            - rec["win"][s]["switch"] for s in stalls)
    return a, b


def _split(R, W, owner, lic) -> dict:
    o_r, o_w = R["win"][owner], W["win"][owner]
    out = {"owner_sales": (o_r["revenue"] - o_r["cost"] - o_r["ad"]) - (o_w["revenue"] - o_w["cost"] - o_w["ad"]),
           "licensee_sales": 0.0, "licensee_prices": 0.0, "licensee_ad": 0.0,
           "fines": -((o_r["fines"] - o_w["fines"]) + sum(R["win"][s]["fines"] - W["win"][s]["fines"] for s in lic))
           - ((o_r["switch"] - o_w["switch"]) + sum(R["win"][s]["switch"] - W["win"][s]["switch"] for s in lic))}
    for s in lic:
        a, b = R["win"][s], W["win"][s]
        ua, ub = a["units"], b["units"]
        c = (a["cost"] / ua) if ua else ((b["cost"] / ub) if ub else 0.0)
        pa = a["revenue"] / ua if ua else None
        pb = b["revenue"] / ub if ub else pa
        if pa is None:
            pa = pb if pb is not None else 0.0
        if pb is None:
            pb = pa
        out["licensee_sales"] += (ua - ub) * (pb - c)
        out["licensee_prices"] += ua * (pa - pb)
        out["licensee_ad"] += -(a["ad"] - b["ad"])
    return out


def _r(x):
    return 0.5 if x is None else x


def analyse(runs, seeds, samples) -> dict:
    idx = {(r["arm"], r["quality"], r["t"], r["seed"], r["owner"], _rk(r["royalty"])): r for r in runs}
    res: dict = {"seeds": seeds, "cells": {}, "pred": {}, "guard": {}, "flags": [], "identity": {}}
    jbad = jmax = 0
    for q in QUALS:
        for t in VERS:
            per = {k: [] for k in ("J_never", "J_R", "J_W", "name", "composition", "licensing", *SPLIT, "split_resid",
                                   "owner_gain_W", *[f"owner_gain_R_{_rk(x)}" for x in RATES],
                                   *[f"lic_profit_R_{_rk(x)}" for x in RATES], "lic_profit_W", "lic_profit_never",
                                   "lic_units_R", "lic_units_W", "lic_units_never", "lic_price_R", "lic_price_W",
                                   "owner_units_R", "owner_units_W", "owner_units_never")}
            paths = {k: [] for k in ("never", "R", "W_owner", "W_labels")}
            prof = {p: {k: [] for k in ("short", "surplus")} for p in PROFILES}
            for sd in seeds:
                nv = idx[("never", "-", t, sd, None, _rk(ROYALTY))]
                acc = {k: [] for k in per}
                pacc = {p: {k: [] for k in ("short", "surplus")} for p in PROFILES}
                for s in samples[sd]:
                    R, W = idx[("R", q, t, sd, s, _rk(ROYALTY))], idx[("W", q, t, sd, s, _rk(ROYALTY))]
                    lic = R["licensees"]
                    if W["licensees"] != lic or len(lic) != N_LIC or not all(W["white_label"].values()):
                        res["flags"].append(f"{q}|{t}|{sd}|{s}: R and W licensees differ or are not 6 white labels")
                    stalls = [s, *lic]
                    Jr, Jw, Jn = _J(R, stalls), _J(W, stalls), _J(nv, stalls)
                    for a_, b_ in (Jr, Jw, Jn):
                        jbad += a_ != b_
                        jmax += 1
                    acc["J_R"].append(Jr[0]); acc["J_W"].append(Jw[0]); acc["J_never"].append(Jn[0])
                    acc["name"].append(Jr[0] - Jw[0]); acc["composition"].append(Jw[0] - Jn[0])
                    acc["licensing"].append(Jr[0] - Jn[0])
                    sp = _split(R, W, s, lic)
                    for k in SPLIT:
                        acc[k].append(sp[k])
                    acc["split_resid"].append(Jr[0] - Jw[0] - sum(sp.values()))
                    never_tot = nv["totals"][s]
                    roy_base = sum(R["roy_at"][_rk(ROYALTY)].values())
                    if roy_base != R["all30"][s]["roy_recv"]:
                        res["flags"].append(f"{q}|{t}|{sd}|{s}: recomputed royalties at 0.10 differ from the engine's")
                    for x in RATES:
                        rx = sum(R["roy_at"][_rk(x)].values())
                        acc[f"owner_gain_R_{_rk(x)}"].append(R["totals"][s] - roy_base + rx - never_tot)
                        acc[f"lic_profit_R_{_rk(x)}"].append(float(np.mean(
                            [R["win"][l]["profit"] + R["roy_at"][_rk(ROYALTY)][l] - R["roy_at"][_rk(x)][l] for l in lic])))
                    acc["owner_gain_W"].append(W["totals"][s] - never_tot)
                    acc["lic_profit_W"].append(float(np.mean([W["win"][l]["profit"] for l in lic])))
                    acc["lic_profit_never"].append(float(np.mean([nv["win"][l]["profit"] for l in lic])))
                    for arm, rec in (("R", R), ("W", W), ("never", nv)):
                        acc[f"lic_units_{arm}"].append(sum(rec["win"][l]["units"] for l in lic))
                        acc[f"owner_units_{arm}"].append(rec["win"][s]["units"])
                    for arm, rec in (("R", R), ("W", W)):
                        u = sum(rec["win"][l]["units"] for l in lic)
                        acc[f"lic_price_{arm}"].append(sum(rec["win"][l]["revenue"] for l in lic) / u if u else None)
                    paths["never"].append([_r(x) for x in nv["rating"][s]])
                    paths["R"].append([_r(x) for x in R["rating"][s]])
                    paths["W_owner"].append([_r(x) for x in W["rating"][s]])
                    paths["W_labels"].append([float(np.mean([_r(W["rating"][l][d]) for l in lic])) for d in range(DAYS)])
                    wr, ww = _window(R["profile"], WINDOW), _window(W["profile"], WINDOW)
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
            res["cells"][f"{q}|{t}"] = cell
    res["identity"] = {"J_checked": jmax, "J_mismatch": jbad,
                       "split_resid_max_abs": max(abs(x) for c in res["cells"].values()
                                                  for x in c["per_seed"]["split_resid"])}
    if jbad:
        res["flags"].append(f"J identity fails in {jbad} of {jmax} owner-chains")
    C = res["cells"]
    ps = lambda c: C[c]["per_seed"]["name"]
    P = {"PQ1": {**C["contract|t40"]["name"], "sign": +1, "label": "contract, t40: name effect"},
         "PQ2": {**paired_diff(ps("contract|t100"), ps("contract|t40")), "sign": +1,
                 "label": "contract: name effect at t40 − at t100"},
         "PQ3": {**paired_diff(ps("cheap|t40"), ps("contract|t40")), "sign": +1,
                 "label": "t40: name effect, contract − cheap"},
         "PQ4": {**C["contract|t100"]["name"], "sign": -1, "label": "contract, t100: name effect ≤ 0 (exploratory)"}}
    for c in C:
        q, t = c.split("|")
        P[f"name {q} {t}"] = {**C[c]["name"], "sign": 0, "label": f"{q}, {t}: name effect (all cells)"}
        P[f"composition {q} {t}"] = {**C[c]["composition"], "sign": 0, "label": f"{q}, {t}: composition effect"}
    for v in P.values():
        v["verdict"] = _verdict(v, v["sign"]) if v["sign"] else (
            "interval excludes 0" if v.get("lo") is not None and (v["lo"] > 0 or v["hi"] < 0) else "interval includes 0")
    res["pred"] = P
    groups = {}
    for r in runs:
        groups.setdefault(f"{r['arm']}|{r['quality']}|{r['t']}", []).append(r)
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

def report(res: dict, rc: dict, meta: dict, old: str | None) -> str:
    L_ = ["# Brand Equity: what a reputation earns", "",
          "Spec \"Brand Equity\" (2026-11-12); predictions fixed 2026-11-12, before any run. Pilot gate: "
          "`runs/pilot_canal_equity.md`.", "",
          "## Design (prespecified)", "",
          "- Question: what does a reputation earn, apart from the extra stalls and the quality behind it?",
          "- Engine 0.17.0. Market as the licensing run, detect_scale 1, owner not liable: choice-set demand (m 3, "
          "gamma 0), 150 buyers, budget 1.25 × base, bargain hunters 0.2; D = 30 known; ratings public (memory 0.7); "
          "brands on (premium 0.4); naive deceptive sellers (fresh reopening); 2 patrolling inspectors, not uniformed; "
          "collectible fines; every genuine stall honest.",
          "- Owners: 3 per seed from `default_rng([seed, 17])`. Licence option fixed: N 6 from day 10. Arms per owner: "
          "never; R = licensees under the owner's brand (royalty 0.10); W = the same stalls under white labels (one "
          "fresh unrated brand each, no royalty, priced from its own rating by the morning rule).",
          "- Conditions: licence quality {contract, cheap} × verification {t40 locals inspect, t100}. Seeds 300–329, "
          "paired.",
          "- Primary measure, per owner: J = owner profit + its 6 licensees' profit, day 10 to 30 (royalties cancel). "
          "Name effect = J(R) − J(W). Composition effect = J(W) − J(never). The name effect is split into owner own "
          "sales, licensee sales, licensee prices, licensee ad spend and fines (they add up exactly). Owner's gain at "
          "royalty 0.05, 0.10, 0.15, 0.25 by the exact recompute, after the no-decision check below.",
          "- Predictions (verbatim from the spec):", *[f"  - {p}" for p in PREDICTIONS],
          "- Analysis: per seed the mean over 3 owners; mean and 95% t over seeds; unadjusted.", ""]
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
    L_ += ["## Gate", "", meta.get("gate", "Pilot gate: see `runs/pilot_canal_equity.md`."), "",
           "### The royalty enters no decision", "",
           "Code (0.17.0): `engine/licensing.py` `royalty_cents` is the only use of `licensing.royalty` besides validation "
           "and the licence record; its one caller is `BazaarEngine.purchase` (`engine/bazaar.py`), after the sale, "
           "adding to the licensee's `royalty_paid_cents` and the owner's `royalty_received_cents` (skipped for white "
           "labels). Those fields are read only by profit (`engine/days.py` `stall_profit`, the outcome's "
           "`profit_by_stall_cents` and `seller_by_type`). Profit reaches decisions only through `revise` (off: brands "
           "require evolution off) and the `yesterday` ledger, read only by `rule_genuine_rational_v2`, which these "
           "chains do not run (rule_honest via rule_genuine_bust_at with nothing scheduled, rule_deceptive). Buyers never "
           "see a royalty.", "",
           f"Replay: seed {meta.get('check_seed')}, t100, both qualities, 3 owners, R at royalty 0.05 and 0.25 against "
           "0.10.", "",
           *_t(["Quality", "Owner", "Royalty", "Days identical (all stalls' units, price, revenue, cost, ad, fines, "
                "catches)", "Same licensees", "Royalties differ", "Recompute exact", "Pass"],
               [[x["quality"], x["owner"], f"{x['royalty']:.2f}", f"{x['days_identical']}/{DAYS}",
                 "yes" if x["same_licensees"] else "no", "yes" if x["royalties_differ"] else "no",
                 "yes" if x["recompute_exact"] else "no", "yes" if x["pass"] else "**no**"] for x in rc["rows"]]),
           "", f"Result: **{'pass' if rc['pass'] else 'FAIL'}**.", "",
           f"J identity (J from stall profit = J from revenue − cost − ad − fines − switch, royalties cancelled): "
           f"{res['identity']['J_checked'] - res['identity']['J_mismatch']}/{res['identity']['J_checked']} owner-chains "
           f"to the cent; largest split residual {res['identity']['split_resid_max_abs']:.6f} cents.", ""]
    P = res["pred"]
    L_ += ["## Predictions", "",
           "$ per owner over days 10–30 (per-seed mean of 3 owners). PQ1–PQ3 confirmatory; the rest exploratory.", "",
           *_t(["Prediction", "Estimate ($)", "Verdict"], [[f"**{k}**: {v['label']}", _ci(v, _d), v["verdict"]]
                                                        for k, v in P.items()]), ""]
    C = res["cells"]
    L_ += ["## Joint profit and its parts", "",
           "J per owner and its 6 licensees, days 10–30, $.", "",
           *_t(["Cell", "J never", "J W", "J R", "Composition W − never", "Name R − W", "Licensing R − never"],
               [[c.replace("|", ", "), _ci(v["J_never"], _d), _ci(v["J_W"], _d), _ci(v["J_R"], _d),
                 _ci(v["composition"], _d), _ci(v["name"], _d), _ci(v["licensing"], _d)] for c, v in C.items()]), "",
           "Name effect split (R − W, $; the parts add up to the name effect):", "",
           *_t(["Cell", *[SPLIT_LAB[k] for k in SPLIT]],
               [[c.replace("|", ", "), *[_ci(v[k], _d) for k in SPLIT]] for c, v in C.items()]), "",
           "Units and prices, days 10–30:", "",
           *_t(["Cell", "Licensee units never / W / R", "Licensee mean price W / R ($)", "Owner units never / W / R"],
               [[c.replace("|", ", "),
                 " / ".join(_num(1)(v[f"lic_units_{a}"]["mean"]) for a in ("never", "W", "R")),
                 " / ".join(_d(v[f"lic_price_{a}"]["mean"]) for a in ("W", "R")),
                 " / ".join(_num(1)(v[f"owner_units_{a}"]["mean"]) for a in ("never", "W", "R"))] for c, v in C.items()]),
           ""]
    L_ += ["## Owner's gain and licensee profit by royalty", "",
           "Owner's gain = owner's 30-day profit − never. R by the exact recompute at each royalty; W has no royalty. "
           "Licensee profit: per licensee, days 10–30.", "",
           *_t(["Cell", *[f"Owner gain R, {x:.2f}" for x in RATES], "Owner gain W"],
               [[c.replace("|", ", "), *[_ci(v[f"owner_gain_R_{_rk(x)}"], _d) for x in RATES], _ci(v["owner_gain_W"], _d)]
                for c, v in C.items()]), "",
           *_t(["Cell", "Licensee profit never", "W", *[f"R, {x:.2f}" for x in RATES]],
               [[c.replace("|", ", "), _ci(v["lic_profit_never"], _d), _ci(v["lic_profit_W"], _d),
                 *[_ci(v[f"lic_profit_R_{_rk(x)}"], _d) for x in RATES]] for c, v in C.items()]), ""]
    L_ += ["## Rating paths", "",
           "Mean over owners (unrated = 0.5), end of days 1, 9, 10, 15, 20, 25, 30: the owner's brand in never, R and W, "
           "and the mean of the 6 white labels in W.", ""]
    rows = []
    for c, v in C.items():
        for k, lab in (("never", "owner, never"), ("R", "owner brand, R"), ("W_owner", "owner brand, W"),
                       ("W_labels", "white labels, W")):
            ys = v["paths"][k]
            rows.append([c.replace("|", ", "), lab, *[f"{ys[d - 1]:.3f}" if d <= len(ys) else "–" for d in (1, 9, 10, 15, 20, 25, 30)]])
    L_ += [*_t(["Cell", "Series", "1", "9", "10", "15", "20", "25", "30"], rows), ""]
    L_ += ["## PQ5: buyers by profile, R − W (exploratory)", "",
           "Days 10–30. Shortfall in points of purchases; surplus in $ per buyer of the profile.", "",
           *_t(["Cell", *[f"{p}: shortfall (pts)" for p in PROFILES], *[f"{p}: surplus ($)" for p in PROFILES]],
               [[c.replace("|", ", "), *[_ci(v["profile"][p]["short"], lambda x, s: _num(1)(100 * x, s)) for p in PROFILES],
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

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="300-329")
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
        raise SystemExit("the main run uses seeds 300-329 only")
    os.makedirs(a.outdir, exist_ok=True)
    log = CR.file_logger(os.path.join(a.outdir, "brand_equity_run.log"))
    t0 = time.time()
    check_seed = seeds[0]
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
            "command": " ".join(["python -m analysis.brand_equity", *sys.argv[1:]]), "tests": a.tests,
            "gate": a.gate or "Pilot gate: see `runs/pilot_canal_equity.md`.", "check_seed": check_seed,
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
            "workers": a.workers, "load_start": _load(), "mem_start": memory_state(), "seeds_txt": a.seeds}
    log(f"brand equity: engine {ENGINE_VERSION}, commit {meta['git']['commit'][:7]}, seeds {a.seeds}")
    samples = {sd: L.sample_stalls(sd) for sd in seeds}
    meta["samples"] = {str(k): v for k, v in samples.items()}
    cache = os.path.join(a.outdir, "brand_equity_cache.jsonl")
    # 1. the no-decision check first; stop if it fails
    check_jobs = [j for j in jobs_for([check_seed], samples, check_seed) if j[0] == "R" and j[2] == "t100"]
    cr, p0 = CR.run_chains(a, check_jobs, cache, log, job, key)
    rc = royalty_check(cr, check_seed, samples)
    log(f"royalty check: {'pass' if rc['pass'] else 'FAIL'}")
    if not rc["pass"]:
        with open(os.path.join(a.outdir, "brand_equity_royalty_check.json"), "w", encoding="utf-8") as f:
            json.dump(rc, f, indent=1)
        raise SystemExit("royalty check failed: a decision depends on the royalty; stop and report")
    del cr
    # 2. the run
    runs, pauses = CR.run_chains(a, jobs_for(seeds, samples), cache, log, job, key)
    res = analyse(runs, seeds, samples)
    meta.update(chains=len(runs) + len(check_jobs) - len([j for j in check_jobs if _rk(j[5]) == _rk(ROYALTY)]),
                pauses=pauses + p0, wall_h=(time.time() - t0) / 3600, load_end=_load(), mem_end=memory_state())
    with gzip.open(os.path.join(a.outdir, "brand_equity.json.gz"), "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "royalty_check": rc, "results": res}, f, separators=(",", ":"))
    with open(os.path.join(a.outdir, "brand_equity.csv"), "w", encoding="utf-8") as f:
        cols = ["J_never", "J_W", "J_R", "name", "composition", *SPLIT, *[f"owner_gain_R_{_rk(x)}" for x in RATES],
                "owner_gain_W"]
        f.write("quality,verification,seed," + ",".join(f"{c}_cents" for c in cols) + "\n")
        for c, v in res["cells"].items():
            q, t = c.split("|")
            for i, sd in enumerate(seeds):
                f.write(",".join([q, t, str(sd), *[f"{v['per_seed'][k][i]:.2f}" for k in cols]]) + "\n")
    sp = os.path.join(a.outdir, "brand_equity_summary.md")
    old = open(sp, encoding="utf-8").read() if os.path.exists(sp) else None
    with open(sp, "w", encoding="utf-8") as f:
        f.write(report(res, rc, meta, old))
    log(f"done; {len(res['flags'])} flags; wall {meta['wall_h']:.2f} h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
