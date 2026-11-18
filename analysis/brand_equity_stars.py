"""Brand Equity speed under displayed ratings (stars): Run A of the task "engine 0.20.0 (displayed ratings), rerun Brand
Equity speed under it, and check whether earlier headline results move" (2026-11-18). Predictions fixed 2026-11-18,
before any run. Background: runs/brand_equity_speed_summary.md (engine 0.19.0): buyers compared ratings unrounded, so a
new brand at 0.999 always lost to a day-1 brand at exactly 1.0, and at t100 the same gap made a white label's price a
cent lower and won price ties; most of E at the slow speeds came from this, not from the catch-up.

Engine 0.20.0. Exactly the brand_equity_speed design (analysis/brand_equity_speed.py: 60 days, ratings.prior_scope new,
contract, arms never / R / W_g, the four calibrated levels prior_n 0, 3.5, 10, 400, t40 and t100, seeds 330-349, the 3
owners of each seed, N 6 from day 10, royalty 0.10), with ratings.display "stars", ratings.display_step 0.02 and
buyers.tie_break "random". Sensitivity cells: display_step 0.1 (half a star) at prior_n 0 and 10, t40 and t100.

Measures as brand_equity_speed (J, E = J(R) - J(W_g), the split, windows by the true rating reaching 0.9, owner's gain,
licensee profit by royalty), plus the displayed catch-up day: the first day (>= 10) at whose end the mean displayed
rating of the owner's W_g white labels (unrated = 0.5) equals the owner's displayed rating; "before" = days 10 through
that day, "after" = the rest of days 10-60 (if never reached, every day is before). The true days to 0.9 are reported
alongside. Analysis: per seed the mean over 3 owners; mean and 95% t over the 20 seeds; unadjusted.

    .venv/bin/python -m analysis.brand_equity_stars --seeds 330-349 --tests "..."                               # main run
    .venv/bin/python -m analysis.brand_equity_stars --pilot --seeds 900-902 --outdir runs/pilot_stars/A
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
from types import SimpleNamespace

import numpy as np

import analysis.brand_equity as E
import analysis.brand_equity_speed as S
import analysis.chainrun as CR
import analysis.liability as LB
import analysis.licensing as L
from analysis.capture import memory_state
from analysis.counterfeit import _ci, _d, _git, _load, _num, _t, _verdict
from cli.sweep import parse_seeds
from engine import ENGINE_VERSION, benchmark
from engine import brands as BR
from engine.bazaar import BazaarEngine
from engine.config import load
from engine.jsonlog import dumps
from engine.metrics import mean_ci

DAYS, SCOPE, VERS = S.DAYS, S.SCOPE, S.VERS
N_LIC, B_DAY, ROYALTY, RATES = S.N_LIC, S.B_DAY, S.ROYALTY, S.RATES
LEVELS, DAYS_TO_TARGET, CURRENT = S.LEVELS, S.DAYS_TO_TARGET, S.CURRENT
MAIN_SEEDS, PILOT_SEEDS = S.MAIN_SEEDS, S.PILOT_SEEDS
STEP = 0.02                                        # the main display step (a tenth of a star)
SENS_STEP = 0.1                                    # sensitivity: half a star
SENS_LEVELS = ("current", "d10")                   # prior_n 0 and 10, at t40 and t100
PT2_LEVEL, PT3_LEVEL = "d20", "d10"                # prior_n 400 and prior_n 10
EXACT = "runs/brand_equity_speed.json.gz"          # the 0.19.0 run, for the exact-vs-stars comparison
PREDICTIONS = [
    "PT1 (confirmatory): t40: E rises with time to reputation (slope of E over the calibrated days to 0.9, per seed, "
    "> 0).",
    "PT2 (confirmatory): t40, prior_n 400: more than half of E is earned before the displayed catch-up day.",
    "PT3 (confirmatory): t40, prior_n 10: E after the displayed catch-up day is less than 20% of E.",
    "PT4 (exploratory): t100: E at each speed; no direction.",
    "PT5 (exploratory): step 0.1 − step 0.02, E at t40 and t100 at both speeds (coarser display should shrink E at the "
    "slow speed).",
    "PT6 (exploratory): shape of E over days to 0.9 at t40 (linear vs saturating), and licensee preference R vs W_g by "
    "speed at royalty 0.05 and 0.10.",
]
STARS_OV = ["ratings.display=stars", "buyers.tie_break=random"]


def _rk(r) -> str:
    return S._rk(r)


def _pk(pn) -> str:
    return S._pk(pn)


def _sk(step) -> str:
    return f"{float(step):g}"


def disp(x, step):
    """The displayed rating at this step (engine 0.20.0's rounding: engine.brands.shown); None stays None."""
    return BR.shown(SimpleNamespace(ratings=SimpleNamespace(display="stars", display_step=float(step))), x)


def config(arm, t, seed, owner, r=ROYALTY, prior_n=0.0, step=STEP):
    """As analysis.brand_equity_speed.config (60 days, scope new), with ratings.display stars at `step` and
    buyers.tie_break random."""
    q = "cheap" if arm == "never" else "contract"
    ov = [*L.overrides(t, 1.0, q, False), f"licensing.royalty={float(r)!r}",
          f"licensing.brand={'white_label' if arm == 'Wg' else 'owner'}",
          f"licensing.white_label_tier={'genuine' if arm == 'Wg' else 'type'}",
          f"ratings.prior_n={float(prior_n)!r}", f"ratings.prior_scope={SCOPE}", f"market.days={DAYS}",
          *STARS_OV, f"ratings.display_step={float(step)!r}", f"seed={seed}"]
    c = load(None, ov, mode="bazaar")
    return benchmark.licence_config(c, None if arm == "never" else owner,
                                    S.NEVER if arm == "never" else (N_LIC, B_DAY))


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ chains: job = (arm, t, seed, owner, r, prior_n, step)

def key(j) -> str:
    arm, t, sd, s, r, pn, step = j
    return f"{arm}|{t}|{sd}|{s}|{_rk(r)}|{_pk(pn)}|{DAYS}|{SCOPE}|stars{_sk(step)}"


def job(j) -> dict:
    """As analysis.brand_equity_speed.job, under stars at `step`. The genuine-tier price check uses the displayed
    start-of-day rating; the owner's and licensees' posted prices are kept by day (the pilot's G4)."""
    arm, t, seed, owner, r, pn, step = j
    D = DAYS
    LB._observe()
    LB._PARKED.clear()
    cfg = config(arm, t, seed, owner, r, pn, step)
    out, snaps, bad = CR.run_with_ledger(cfg)
    sids = sorted(snaps[0])
    owners = L.sample_stalls(seed) if arm == "never" else [owner]
    lic = sorted(s for s in sids if snaps[-1][s]["licensed_from"] == owner) if arm != "never" else []
    keep = sids if arm == "never" else [owner, *lic]
    win = range(B_DAY, D + 1)
    rec = {"key": key(j), "arm": arm, "t": t, "seed": seed, "owner": owner, "royalty": float(r), "prior_n": float(pn),
           "step": float(step), "days": D, "scope": SCOPE, "licensees": lic, "profit_mismatch": bad,
           "win": E._sums(snaps, keep, win), "all": E._sums(snaps, keep, range(1, D + 1)),
           "stype": {s: snaps[0][s]["stype"] for s in keep},
           "totals": {s: benchmark.stall_total(out, s) for s in owners},
           "rating": {s: [out["days"][d]["brand_ratings"].get(out["days"][d]["brands"][s]) for d in range(D)]
                      for s in [*owners, *lic]},
           "white_label": {s: snaps[-1][s]["white_label"] for s in lic}, "guard": CR.guard(out),
           "digest": hashlib.sha256(dumps(out).encode()).hexdigest()}
    if arm != "never":
        rec["daily"] = {s: {f: [int(snaps[d][s][f]) for d in range(D)] for f in S.DF} for s in keep}
        rec["price"] = {s: [int(snaps[d][s]["price"]) for d in range(D)] for s in keep}
    if D >= 20:
        reopened = {x["to"] for d in range(20) for x in out["days"][d]["renames"]}
        held = [out["days"][19]["brands"][s] for s in sids if snaps[19][s]["stype"] == "deceptive"
                and out["days"][19]["brands"][s] in reopened]
        rr = [out["days"][19]["brand_ratings"].get(n) for n in held]
        got = [x for x in rr if x is not None]
        rec["reopen_d20"] = {"held": len(held), "rated": len(got), "mean": float(np.mean(got)) if got else None}
    if arm == "never":
        by = {}
        for st in S.STYPES:
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
    if arm == "Wg":               # base x (1 + premium x (displayed start-of-day rating - 0.5))
        prem = cfg.brands.premium
        cat = {st.sid: st.category for st in BazaarEngine(cfg).stalls}
        miss = 0
        for s in lic:
            base = cfg.pricing.base_price_cents[cat[s]]
            for d in range(B_DAY, D + 1):
                prev = None if d == B_DAY else out["days"][d - 2]["brand_ratings"].get(out["days"][d - 1]["brands"][s])
                if snaps[d - 1][s]["price"] != int(round(base * (1 + prem * (S._r(disp(prev, step)) - 0.5)))):
                    miss += 1
        rec["tier_price_miss"] = miss
        rec["tier_price_checked"] = True
    return rec


def jobs_for(seeds, samples, sens=True) -> list[tuple]:
    out = []
    cells = [(lv, STEP) for lv in LEVELS] + ([(lv, SENS_STEP) for lv in SENS_LEVELS] if sens else [])
    for sd in seeds:
        for t in VERS:
            for lv, step in cells:
                pn = LEVELS[lv]
                out.append(("never", t, sd, None, ROYALTY, pn, step))
                for s in samples[sd]:
                    for arm in ("R", "Wg"):
                        out.append((arm, t, sd, s, ROYALTY, pn, step))
    return out


def check_jobs_for(check_seed, samples) -> list[tuple]:
    """The no-decision replay: R at t100, royalty 0.10 (shared with the run) and 0.05, 0.25; current and slowest."""
    return [("R", "t100", check_seed, s, r, LEVELS[lv], STEP) for lv in (CURRENT, PT2_LEVEL)
            for s in samples[check_seed] for r in (ROYALTY, *S.CHECK_RATES)]


def _as_speed(runs, step):
    """Chains at this step, keyed as analysis.brand_equity_speed keys them, for its royalty_check and analyse."""
    return [dict(r, key=S.key((r["arm"], r["t"], r["seed"], r["owner"], r["royalty"], r["prior_n"], DAYS, SCOPE)))
            for r in runs if _sk(r["step"]) == _sk(step)]


# ------------------------------------------------------------------ analysis

def disp_catch_day(rec, owner, lic, step) -> int | None:
    """The first day (>= 10) at whose end the mean displayed rating of the white labels (unrated = 0.5) equals the
    owner's displayed rating (unrated = 0.5)."""
    for d in range(B_DAY, rec["days"] + 1):
        m = float(np.mean([S._r(disp(rec["rating"][l][d - 1], step)) for l in lic]))
        if abs(m - S._r(disp(rec["rating"][owner][d - 1], step))) < 1e-9:
            return d
    return None


def price_check(rec, owner, lic, step) -> tuple[int, int]:
    """G4: (label-days where a white label and its owner had the same displayed start-of-day rating, of which the posted
    prices differ). Days 11-60 (on day 10 the labels are new)."""
    same = miss = 0
    for d in range(B_DAY + 1, rec["days"] + 1):
        own = S._r(disp(rec["rating"][owner][d - 2], step))
        for l in lic:
            if abs(S._r(disp(rec["rating"][l][d - 2], step)) - own) < 1e-9:
                same += 1
                miss += rec["price"][l][d - 1] != rec["price"][owner][d - 1]
    return same, miss


def extra(runs, seeds, samples, levels, step) -> dict:
    """Per cell: displayed catch-up day (from day 10 = 1), E before and after it, and the G4 price check."""
    idx = {(r["arm"], r["t"], r["seed"], r["owner"], _pk(r["prior_n"])): r for r in runs
           if _sk(r["step"]) == _sk(step) and _rk(r["royalty"]) == _rk(ROYALTY)}
    out, g4 = {}, {"same": 0, "miss": 0}
    for t in VERS:
        for lv in levels:
            pn = levels[lv]
            per = {k: [] for k in ("disp_days", "disp_reached", "E_before", "E_after", "before_minus_after",
                                   "pt3_margin", "E")}
            for sd in seeds:
                acc = {k: [] for k in per}
                for s in samples[sd]:
                    R, Wg = idx[("R", t, sd, s, _pk(pn))], idx[("Wg", t, sd, s, _pk(pn))]
                    lic = R["licensees"]
                    stalls = [s, *lic]
                    cd = disp_catch_day(Wg, s, lic, step)
                    end = DAYS if cd is None else cd
                    bw, aw = range(B_DAY, end + 1), range(end + 1, DAYS + 1)
                    eb = S._jwin(R, stalls, bw) - S._jwin(Wg, stalls, bw)
                    ea = S._jwin(R, stalls, aw) - S._jwin(Wg, stalls, aw)
                    e = S._jwin(R, stalls, range(B_DAY, DAYS + 1)) - S._jwin(Wg, stalls, range(B_DAY, DAYS + 1))
                    acc["disp_days"].append(None if cd is None else cd - B_DAY + 1)
                    acc["disp_reached"].append(0.0 if cd is None else 1.0)
                    acc["E_before"].append(eb); acc["E_after"].append(ea); acc["before_minus_after"].append(eb - ea)
                    acc["pt3_margin"].append(0.2 * e - ea); acc["E"].append(e)
                    sm, ms = price_check(Wg, s, lic, step)
                    g4["same"] += sm
                    g4["miss"] += ms
                for k in per:
                    v = [x for x in acc[k] if x is not None]
                    per[k].append(float(np.mean(v)) if v else None)
            cell = {k: mean_ci(v) for k, v in per.items()}
            cell["per_seed"] = per
            cell["after_share"] = mean_ci([None if not e else a / e for a, e in zip(per["E_after"], per["E"])])
            out[f"{lv}|{t}"] = cell
    return {"cells": out, "g4": g4}


def analyse(runs, seeds, samples, sens=True) -> dict:
    main = S.analyse(_as_speed(runs, STEP), seeds, samples, LEVELS, DAYS_TO_TARGET)
    x = extra(runs, seeds, samples, LEVELS, STEP)
    res = {"seeds": seeds, "main": main, "disp": x["cells"], "g4": x["g4"], "flags": list(main["flags"])}
    if x["g4"]["miss"] or not x["g4"]["same"]:
        res["flags"].append(f"G4 price check: {x['g4']['miss']} of {x['g4']['same']} equal-display label-days differ")
    # predictions
    C, Dc = main["cells"], x["cells"]
    P = {"PT1": {**main["pred"]["PS1"], "label": "t40: slope of E over days to 0.9 ($ per day)"}}
    P["PT2"] = {**Dc[f"{PT2_LEVEL}|t40"]["before_minus_after"], "sign": +1,
                "label": "t40, prior_n 400: E before the displayed catch-up day − E after it (> 0 ⇔ more than half of E "
                         "before)"}
    P["PT3"] = {**Dc[f"{PT3_LEVEL}|t40"]["pt3_margin"], "sign": +1,
                "label": "t40, prior_n 10: 20% of E − E after the displayed catch-up day (> 0 ⇔ E after < 20% of E)"}
    for k in P:
        P[k]["verdict"] = _verdict(P[k], P[k]["sign"])
    res["pred"] = P
    if sens:
        sm = S.analyse(_as_speed(runs, SENS_STEP), seeds, samples, {lv: LEVELS[lv] for lv in SENS_LEVELS},
                       {lv: DAYS_TO_TARGET[lv] for lv in SENS_LEVELS})
        sx = extra(runs, seeds, samples, {lv: LEVELS[lv] for lv in SENS_LEVELS}, SENS_STEP)
        res["sens"], res["sens_disp"] = sm, sx["cells"]
        res["flags"] += [f"step {SENS_STEP:g}: {f}" for f in sm["flags"]]
        if sx["g4"]["miss"]:
            res["flags"].append(f"G4 price check, step {SENS_STEP:g}: {sx['g4']['miss']} of {sx['g4']['same']} differ")
        res["g4_sens"] = sx["g4"]
        pt5 = {}
        for lv in SENS_LEVELS:
            for t in VERS:
                a, b = sm["cells"][f"{lv}|{t}"]["per_seed"]["E"], C[f"{lv}|{t}"]["per_seed"]["E"]
                pt5[f"{lv}|{t}"] = mean_ci([None if u is None or v is None else u - v for u, v in zip(a, b)])
        res["pt5"] = pt5
    # PT6: licensee preference R vs W_g by speed at 0.05 and 0.10
    res["pt6_lic"] = {f"{lv}|{t}|{_rk(r)}": mean_ci([None if a is None or b is None else a - b for a, b in zip(
        C[f"{lv}|{t}"]["per_seed"][f"lic_profit_R_{_rk(r)}"], C[f"{lv}|{t}"]["per_seed"]["lic_profit_Wg"])])
        for lv in LEVELS for t in VERS for r in (0.05, ROYALTY)}
    # exact (0.19.0 run) vs stars, paired by seed, for the seeds both runs have
    res["vs_exact"] = None
    if os.path.exists(EXACT):
        with gzip.open(EXACT, "rt", encoding="utf-8") as f:
            ex = json.load(f)["results"]
        common = [sd for sd in seeds if sd in ex["seeds"]]
        if common:
            vs = {}
            for c in C:
                for k in ("E", "E_after", "composition", "owner_gain_Wg", f"owner_gain_R_{_rk(ROYALTY)}"):
                    a = [C[c]["per_seed"][k][seeds.index(sd)] for sd in common]
                    b = [ex["cells"][c]["per_seed"][k][ex["seeds"].index(sd)] for sd in common]
                    vs[f"{c}|{k}"] = {"exact": mean_ci(b), "stars": mean_ci(a), "diff": mean_ci(
                        [None if u is None or v is None else u - v for u, v in zip(a, b)])}
            res["vs_exact"] = {"seeds": common, "cells": vs}
    return res


# ------------------------------------------------------------------ report

def _lab(c):
    return c.replace("|", ", ")


def report(res: dict, rc: dict, meta: dict) -> str:
    M, C, Dc, P = res["main"], res["main"]["cells"], res["disp"], res["pred"]
    lv, dx = LEVELS, DAYS_TO_TARGET
    sens = "sens" in res
    L_ = ["# Brand Equity speed under displayed ratings (stars)", "",
          "Spec: the task \"engine 0.20.0 (displayed ratings), rerun Brand Equity speed under it, and check whether "
          "earlier headline results move\" (2026-11-18), Run A; predictions fixed 2026-11-18, before any run. "
          "Background: `runs/brand_equity_speed_summary.md`. Pilot gate: `runs/pilot_stars.md`.", "",
          "## Design (prespecified)", "",
          "- Question: with ratings displayed as stars (rounded), so that a new brand at 0.999 shows the same as a day-1 "
          "brand at 1.0, does the reputation effect E still rise with the time new brands take to earn a rating, and "
          "is it earned before the white labels catch up on the display?",
          "- Engine 0.20.0. Exactly the brand_equity_speed design: 60 days (known to sellers), "
          "`ratings.prior_scope` new, the licensing market (detect_scale 1, owner not liable, "
          "`licensing.white_label_tier` genuine, royalty 0.10, N 6 from day 10, 3 owners per seed from "
          "`default_rng([seed, 17])`), quality contract, arms never / R / W_g; with `ratings.display` stars, "
          f"`ratings.display_step` {STEP:g} (a tenth of a star) and `buyers.tie_break` random.",
          "- Speeds (`ratings.prior_n`, calibrated at 0.19.0; days for a W_g white label's true rating to reach 0.9 at "
          "t40): " + "; ".join(f"{k}: prior_n {lv[k]:g}, {dx[k]:.2f} days" for k in lv) + ".",
          "- Verification: t40 (locals inspect) and t100. Seeds " + meta["seeds_txt"] + ", paired across all cells.",
          f"- Sensitivity cells: `ratings.display_step` {SENS_STEP:g} (half a star) at prior_n 0 and 10, t40 and t100" +
          ("." if sens else " — dropped by the timing gate."),
          "- Measures as brand_equity_speed: J = owner + 6 licensees' profit, days 10–60; E = J(R) − J(W_g) with the "
          "five-part split; windows by the true rating (catch-up = days 10 through the day the white labels' mean true "
          "rating first reaches 0.9); owner's gain and licensee profit by royalty. Added: the displayed catch-up day, the "
          "first day (≥ 10) at whose end the mean displayed rating of the owner's white labels (unrated = 0.5) equals "
          "the owner's displayed rating; before = days 10 through that day, after = the rest (if never reached, every "
          "day is before). The true days to 0.9 are reported alongside.",
          "- Predictions (verbatim from the spec):", *[f"  - {p}" for p in PREDICTIONS],
          "- Analysis: per seed the mean over 3 owners; mean and 95% t over seeds; unadjusted. PT1's slope is fitted per "
          "seed over the calibration's days to 0.9 (the same x as PS1). PT2 is tested as E(before) − E(after) > 0; "
          "PT3 as 0.2 × E − E(after) > 0, per seed.", ""]
    L_ += ["## Run record", "",
           f"- Engine `{meta['engine_version']}`; commit `{meta['git']['commit']}`; uncommitted at run time: "
           f"{meta['git']['status_porcelain'] or 'none'}",
           f"- Script sha256 `{meta['script_sha256']}`", f"- Command: `{meta['command']}`", f"- Tests: {meta['tests']}",
           f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
           f"- {meta['chains']} chains × {DAYS} days on {meta['workers']} workers (nice 19); wall clock "
           f"{meta['wall_h']:.2f} h; load average {meta['load_start']} at start, {meta['load_end']} at end; memory at "
           f"start {meta['mem_start']}, at end {meta['mem_end']}; memory-guard pauses: {meta['pauses']}",
           f"- Seeds {meta['seeds_txt']} ({len(res['seeds'])}), paired", ""]
    idn = M["identity"]
    L_ += ["## Gate and checks", "", meta.get("gate", ""), "",
           f"- Genuine-tier prices: every W_g white label's posted price equals base × (1 + 0.4 × (displayed start-of-day "
           f"rating − 0.5)) on every day from 10: {idn['tier_price_miss']} misses in {idn['tier_price_chains']} chains.",
           f"- Equal display, equal price: on {res['g4']['same']:,} label-days (days 11–60) a white label and its owner "
           f"had the same displayed rating; their posted prices differ on {res['g4']['miss']}.",
           f"- J identity: {idn['J_checked'] - idn['J_mismatch']}/{idn['J_checked']} owner-chains to the cent; largest "
           f"split residual {idn['split_resid_max_abs']:.6f} cents; windows add up to E to "
           f"{idn['window_resid_max_abs']:.0f} cents.",
           f"- Royalty no-decision replay (seed {meta.get('check_seed')}, t100, R at 0.05 and 0.25 against 0.10, current "
           f"and slowest speed): **{'pass' if rc['pass'] else 'FAIL'}** ({sum(x['pass'] for x in rc['rows'])}/"
           f"{len(rc['rows'])}).",
           f"- Flags: {'; '.join(res['flags']) if res['flags'] else 'none'}.", ""]
    F = M["fits"]
    L_ += ["## Predictions", "",
           "$ per owner over days 10–60 (per-seed mean of 3 owners). PT1–PT3 confirmatory; PT4–PT6 exploratory.", "",
           *_t(["Prediction", "Estimate ($)", "Verdict"],
               [[f"**{k}**: {P[k]['label']}", _ci(P[k], _d), P[k]["verdict"]] for k in ("PT1", "PT2", "PT3")]), ""]
    c2, c3 = Dc[f"{PT2_LEVEL}|t40"], Dc[f"{PT3_LEVEL}|t40"]
    L_ += [f"PT2 share: E before / E at prior_n 400, t40 = "
           f"{(c2['E_before']['mean'] / c2['E']['mean']) if c2['E']['mean'] else float('nan'):.2f} (ratio of means). "
           f"PT3 share: E after / E at prior_n 10, t40 = "
           f"{(c3['E_after']['mean'] / c3['E']['mean']) if c3['E']['mean'] else float('nan'):.2f} (ratio of means; "
           f"per-seed ratios {_ci(c3['after_share'], _num(2), False)}).", ""]
    rows = []
    for t in VERS:
        for k in lv:
            c, d_ = C[f"{k}|{t}"], Dc[f"{k}|{t}"]
            rows.append([f"{k}, {t}", _ci(c["E"], _d), _num(1)(c["days_label"]["mean"]), _num(1)(c["owner_days"]["mean"]),
                         f"{_num(1)(d_['disp_days']['mean'])} ({d_['disp_reached']['mean']:.2f})",
                         _ci(d_["E_before"], _d), _ci(d_["E_after"], _d)])
    L_ += ["### E by speed, true and displayed catch-up", "",
           "Days counted from day 10 = 1. True days to 0.9: a white label's own rating (mean over labels); owner catch-up "
           "(true): the labels' mean true rating ≥ 0.9; displayed catch-up: the labels' mean displayed rating equals the "
           "owner's (share of owner-chains that reach it in brackets; means over those that do).", "",
           *_t(["Speed, verification", "E ($)", "Label days to 0.9 (true)", "Owner catch-up (true)",
                "Displayed catch-up day (share reached)", "E before displayed catch-up ($)", "E after ($)"], rows), ""]
    L_ += ["**PT4** (t100, exploratory): " + "; ".join(f"{k} {_ci(C[f'{k}|t100']['E'], _d)}" for k in lv) + ".", ""]
    if sens:
        L_ += ["**PT5** (exploratory): E at step 0.1 − E at step 0.02, paired by seed:", "",
               *_t(["Speed, verification", "E step 0.02 ($)", "E step 0.1 ($)", "Difference ($)"],
                   [[_lab(c), _ci(C[c]["E"], _d), _ci(res["sens"]["cells"][c]["E"], _d), _ci(res["pt5"][c], _d)]
                    for c in res["pt5"]]), ""]
    else:
        L_ += ["**PT5**: not run (the step 0.1 cells were dropped by the timing gate).", ""]
    L_ += ["**PT6** (exploratory). Fits of E on days to 0.9 at t40 over the per-seed points "
           f"(n = {F['n']}):", "",
           *_t(["Fit", "Parameters", "R²", "AIC"],
               [["Linear: a + b x", f"a = {_d(F['linear']['a'], True)}, b = {_d(F['linear']['b'], True)} per day",
                 _num(3)(F["linear"]["r2"]), _num(1)(F["linear"]["aic"])],
                ["Saturating: a + A(1 − e^−(x − x0)/τ)",
                 f"a = {_d(F['saturating']['a'], True)}, A = {_d(F['saturating']['A'], True)}, τ = "
                 f"{F['saturating']['tau']:.2f} days" + (" (grid edge)" if F["saturating"]["tau_at_grid_edge"] else ""),
                 _num(3)(F["saturating"]["r2"]), _num(1)(F["saturating"]["aic"])]]), "",
           "Licensee profit under R − under W_g ($ per licensee, days 10–60), by speed and royalty:", "",
           *_t(["Speed", *[f"{t}, royalty {r:.2f}" for t in VERS for r in (0.05, ROYALTY)]],
               [[k, *[_ci(res["pt6_lic"][f"{k}|{t}|{_rk(r)}"], _d) for t in VERS for r in (0.05, ROYALTY)]]
                for k in lv]), ""]
    if res.get("vs_exact"):
        v = res["vs_exact"]
        L_ += ["## Stars against the exact-rating run (0.19.0), paired by seed (exploratory)", "",
               f"Seeds {v['seeds'][0]}–{v['seeds'][-1]} ({len(v['seeds'])}); exact from `{EXACT}`.", "",
               *_t(["Cell", "Measure", "Exact ($)", "Stars ($)", "Stars − exact ($)"],
                   [[_lab(c), k, _ci(v["cells"][f"{c}|{k}"]["exact"], _d), _ci(v["cells"][f"{c}|{k}"]["stars"], _d),
                     _ci(v["cells"][f"{c}|{k}"]["diff"], _d)]
                    for c in C for k in ("E", "E_after", "owner_gain_Wg", f"owner_gain_R_{_rk(ROYALTY)}")]), ""]
    rows = []
    for c in C:
        x = C[c]
        rows.append([_lab(c), _ci(x["J_never"], _d), _ci(x["J_Wg"], _d), _ci(x["J_R"], _d), _ci(x["E"], _d),
                     *[_ci(x[k], _d) for k in E.SPLIT]])
    L_ += ["## All cells", "", *_t(["Cell", "J never", "J W_g", "J R", "E", *E.SPLIT_LAB], rows), "",
           "## Reading (written after the results)", "", "READING_PLACEHOLDER", "",
           "## Caveats", "", "CAVEATS_PLACEHOLDER", ""]
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
    ap.add_argument("--no-sensitivity", action="store_true", help="drop the step 0.1 cells (timing gate)")
    ap.add_argument("--pilot", action="store_true", help="pilot seeds 900-902 into an --outdir other than runs")
    a = ap.parse_args(argv)
    seeds = parse_seeds(a.seeds)
    sens = not a.no_sensitivity
    LB._lower_priority()
    if a.pilot:
        if not set(seeds) <= PILOT_SEEDS or os.path.abspath(a.outdir) == os.path.abspath("runs"):
            raise SystemExit("--pilot uses seeds 900-902 and an outdir other than runs")
    elif not set(seeds) <= MAIN_SEEDS:
        raise SystemExit("the main run uses seeds 330-349 only")
    os.makedirs(a.outdir, exist_ok=True)
    log = CR.file_logger(os.path.join(a.outdir, "brand_equity_stars_run.log"))
    t0 = time.time()
    check_seed = seeds[0]
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
            "command": " ".join(["python -m analysis.brand_equity_stars", *sys.argv[1:]]), "tests": a.tests,
            "gate": a.gate or "Pilot gate: see `runs/pilot_stars.md`.", "check_seed": check_seed, "sensitivity": sens,
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
            "workers": a.workers, "load_start": _load(), "mem_start": memory_state(), "seeds_txt": a.seeds}
    log(f"brand equity stars: engine {ENGINE_VERSION}, commit {meta['git']['commit'][:7]}, seeds {a.seeds}, "
        f"step {STEP:g}, sensitivity {'on' if sens else 'off'}")
    samples = {sd: L.sample_stalls(sd) for sd in seeds}
    meta["samples"] = {str(k): v for k, v in samples.items()}
    cache = os.path.join(a.outdir, "brand_equity_stars_cache.jsonl")
    check_jobs = check_jobs_for(check_seed, samples)
    cr, p0 = CR.run_chains(a, check_jobs, cache, log, job, key)
    lv2 = {CURRENT: LEVELS[CURRENT], PT2_LEVEL: LEVELS[PT2_LEVEL]}
    rc = S.royalty_check(_as_speed(cr, STEP), check_seed, samples, lv2)
    log(f"royalty check: {'pass' if rc['pass'] else 'FAIL'}")
    if not rc["pass"]:
        with open(os.path.join(a.outdir, "brand_equity_stars_royalty_check.json"), "w", encoding="utf-8") as f:
            json.dump(rc, f, indent=1)
        raise SystemExit("royalty check failed: a decision depends on the royalty; stop and report")
    del cr
    runs, pauses = CR.run_chains(a, jobs_for(seeds, samples, sens), cache, log, job, key)
    res = analyse(runs, seeds, samples, sens)
    nx = len([j for j in check_jobs if _rk(j[4]) != _rk(ROYALTY)])
    meta.update(chains=len(runs) + nx, pauses=pauses + p0, wall_h=(time.time() - t0) / 3600, load_end=_load(),
                mem_end=memory_state())
    slim = [{k: v for k, v in r.items() if k not in ("daily", "dig_trade", "price")} for r in runs]
    with gzip.open(os.path.join(a.outdir, "brand_equity_stars.json.gz"), "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "royalty_check": rc, "results": res, "chains": slim}, f, separators=(",", ":"))
    with open(os.path.join(a.outdir, "brand_equity_stars.csv"), "w", encoding="utf-8") as f:
        cols = ["J_never", "J_Wg", "J_R", "E", "composition", *E.SPLIT, "E_catch", "E_after", "owner_days",
                f"owner_gain_R_{_rk(ROYALTY)}", "owner_gain_Wg", f"lic_profit_R_{_rk(ROYALTY)}", "lic_profit_Wg"]
        dcols = ["disp_days", "E_before", "E_after"]
        f.write("step,level,prior_n,verification,seed," + ",".join(cols) + ",disp_days,E_before_disp,E_after_disp\n")
        blocks = [(STEP, res["main"]["cells"], res["disp"])]
        if sens:
            blocks.append((SENS_STEP, res["sens"]["cells"], res["sens_disp"]))
        for step, cells, dcells in blocks:
            for c, v in cells.items():
                lv, t = c.split("|")
                for i, sd in enumerate(seeds):
                    vals = [v["per_seed"][k][i] for k in cols] + [dcells[c]["per_seed"][k][i] for k in dcols]
                    f.write(",".join([f"{step:g}", lv, f"{LEVELS[lv]:g}", t, str(sd),
                                      *["" if x is None else f"{x:.2f}" for x in vals]]) + "\n")
    with open(os.path.join(a.outdir, "brand_equity_stars_summary.md"), "w", encoding="utf-8") as f:
        f.write(report(res, rc, meta))
    log(f"done; {len(res['flags'])} flags; wall {meta['wall_h']:.2f} h")
    return 2 if res["flags"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
