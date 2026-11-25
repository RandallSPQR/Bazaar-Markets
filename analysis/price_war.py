"""Stage 2 of runs/plan_autonomous_2026-11-23.md: the price-war study (engine 1.2.0, rule-based only).

Question: in the robustness sweep (exploratory), the undercut price policy drove prices to unit cost, brand equity
vanished and cashing in a name paid even where locals inspect. Does removing the margin above cost make quality fraud
pay, and does enforcement still stop it?

Predictions PW1-PW5 were fixed in the plan (committed 326abfa, 2026-11-24) before any run. Choices this script makes
that the plan leaves open, written down here before any pilot or main chain (2026-11-24):

  Policy levels (sellers.price_policy, sellers.undercut_floor_markup):
    RI = rating_indexed;  U0 = undercut, m 0;  U0.1 = undercut, m 0.1;  U0.3 = undercut, m 0.3.
  Buyer choice: lexicographic, except the sensitivity cell (logit sharp: rating and price weights 20, 20, as the
    robustness sweep).
  Market defaults (plan): ratings.display stars, display_step 0.02, buyers.tie_break random, appended to every config
    a study's own builder makes (as analysis/robustness_1_1.py). Each outcome's market is the reference market's named
    variant for the run whose design the plan cites (configs/reference_1_0_variants.json): the liability run for
    outcome A, the stars brand-equity run for outcome B.
  Outcome A (bust-out gain): the liability run's collectible arm (analysis/liability.py), conditions col|t40|ds0.0
    and col|t40|ds1.0: the verification market at tourist share 0.4 with locals inspecting, 2 patrolling inspectors,
    detect_scale 0 or 1, fines collectible (penalty lag 0, no exit), D = 30. That arm's benchmark is the plan's:
    3 genuine stalls per seed from default_rng([seed, 17]), candidates never and bust-out on day 20, 25, 28, 29, 30,
    gain = best candidate's 30-day profit - never's (unfloored, primary). Per seed, the mean over the 3 stalls.
  Outcome B (brand equity): analysis/brand_equity_stars.py at t40, prior_n 400 (prior_scope new), contract, genuine
    tier, royalty 0.10, N 6 from day 10, 60 days, detect_scale 1 (that market's setting): E = J(R) - J(W_g) over
    days 10-60, per seed the mean over the 3 owners (the same 3 sampled stalls).
  Sensitivity cell (exploratory): outcome A at U0, detect_scale 0, logit sharp.
  Seeds 500-519, paired across every cell (pilot 900-902).

  PW1 (confirmatory) A, U0, ds 0: gain > 0.
  PW2 (confirmatory) A, ds 0: per-seed least-squares slope of the gain over m in {0, 0.1, 0.3} (U0, U0.1, U0.3) < 0.
  PW3 (confirmatory) B: per-seed least-squares slope of E over m in {0, 0.1, 0.3} > 0.
  PW4 (confirmatory) A, U0, ds 1: gain < 0.
  Verdict rule (as the robustness sweep): mean and 95% t interval over the 20 seeds, unadjusted; supported if the
  interval lies on the predicted side of 0, contradicted if it lies on the other side, otherwise not supported.
  PW5 (exploratory): RI against U0 on each outcome (paired by seed); posted prices and margins (each chain's own-name
  stalls, every morning; share of undercut stall-days at the floor); buyer surplus (value - paid - inspection cost)
  and shortfall rate by profile, in the never chains (the market with no bust-out); whether a price war's lower
  prices outweigh its fraud for buyers (buyer surplus per buyer, U0 - RI, paired, never chains, ds 0 and ds 1); the
  logit sharp cell.

Gates (plan): pilot on seeds 900-902. G1 the pipeline runs end to end; G2 m = 0 reproduces the 1.1.0 undercut
chains bit for bit (--repro: the robustness sweep's undercut x lex liability chains for seeds 230-231 and its
equity chains at prior_n 0 and 400 for seeds 330-331, runs/robustness_1_1_cache.jsonl); G3 projected main run
<= 12 h, else cut to 15 seeds (500-514), else STOP; G4 stuck, parked and idle-chooser counts 0 (and no invalid
actions). Every chain also checks that each engine it builds runs the cell's settings; exit 2 on any flag.

    .venv/bin/python -m analysis.price_war --repro --outdir runs/pilot_price_war            # G2
    .venv/bin/python -m analysis.price_war --seeds 900-902 --outdir runs/pilot_price_war    # pilot: G1, G3, G4
    .venv/bin/python -m analysis.price_war --tests "..."                                    # main run
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time

import numpy as np

import analysis.brand_equity as E
import analysis.brand_equity_speed as S
import analysis.brand_equity_stars as ES
import analysis.chainrun as CR
import analysis.liability as LB
import analysis.verification as V
from analysis.capture import PROFILES, memory_state
from analysis.counterfeit import _load
from cli.sweep import parse_seeds
from engine import ENGINE_VERSION, benchmark
from engine import bazaar as EB
from engine import brands as BR
from engine.metrics import mean_ci, paired_diff

NEVER = benchmark.NEVER
LEVELS = {"RI": ("rating_indexed", 0.0), "U0": ("undercut", 0.0), "U0.1": ("undercut", 0.1),
          "U0.3": ("undercut", 0.3)}
SLOPE_LEVELS = ("U0", "U0.1", "U0.3")
CHOICES = {"lex": ("lexicographic", 5.0, 5.0), "sharp": ("logit", 20.0, 20.0)}
MARKET_DEFAULTS = ["ratings.display=stars", "ratings.display_step=0.02", "buyers.tie_break=random"]
A_CONDS = {0.0: "col|t40|ds0.0", 1.0: "col|t40|ds1.0"}
B_T, B_PN = "t40", 400.0
MAIN_SEEDS = list(range(500, 520))
CUT_SEEDS = list(range(500, 515))
PILOT_SEEDS = [900, 901, 902]
TIME_LIMIT_H = 12.0
PATCHED = [m for m in (V, LB, E, S, ES) if hasattr(m, "load")]
SWEEP_CACHE = "runs/robustness_1_1_cache.jsonl"
OUT = "runs"

# Cells: ("A", level, detect_scale, choice) and ("B", level, choice)
CELLS_A = [("A", lv, ds, "lex") for lv in LEVELS for ds in (0.0, 1.0)] + [("A", "U0", 0.0, "sharp")]
CELLS_B = [("B", lv, "lex") for lv in LEVELS]
CELLS = CELLS_A + CELLS_B


def cell_name(c) -> str:
    return f"A|{c[1]}|ds{c[2]:g}|{c[3]}" if c[0] == "A" else f"B|{c[1]}|{c[2]}"


def cell_overrides(c) -> list[str]:
    lv, ch = c[1], c[-1]
    pol, m = LEVELS[lv]
    rule, wr, wp = CHOICES[ch]
    return [*MARKET_DEFAULTS, f"sellers.price_policy={pol}", f"sellers.undercut_floor_markup={m!r}",
            f"buyers.choice={rule}", f"buyers.logit_rating_weight={wr!r}", f"buyers.logit_price_weight={wp!r}"]


def cell_seen(c) -> tuple:
    lv, ch = c[1], c[-1]
    pol, m = LEVELS[lv]
    rule, wr, wp = CHOICES[ch]
    return ("stars", 0.02, "random", pol, float(m), rule, wr, wp)


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ specs

def specs(c, seeds, samples) -> list[tuple]:
    if c[0] == "A":
        return LB.jobs_for([A_CONDS[c[2]]], seeds, samples)
    out = []
    for sd in seeds:
        out.append(("never", B_T, sd, None, ES.ROYALTY, B_PN, ES.STEP))
        out += [(arm, B_T, sd, s, ES.ROYALTY, B_PN, ES.STEP) for s in samples[sd] for arm in ("R", "Wg")]
    return out


def skey(c, spec) -> str:
    return LB._key(spec) if c[0] == "A" else ES.key(spec)


def seed_of(c, spec) -> int:
    return int(spec[1] if c[0] == "A" else spec[2])


def key(j) -> str:
    c, spec = j
    return f"{cell_name(c)}|{skey(c, spec)}"


# ------------------------------------------------------------------ worker

_ENG: list = []
_GUARD: list = []
_PRICES: list = []


def _hooks() -> None:
    """Observers that change nothing: each engine's settings, each run's guard counts, and every morning's posted
    prices of own-name stalls (after the policy and the copy rules)."""
    if getattr(EB.BazaarEngine.__init__, "_pw_seen", False):
        return
    oi, orun, omp = EB.BazaarEngine.__init__, EB.run, BR.morning_prices

    def init(self, cfg, *a, **k):
        b = cfg.buyers
        _ENG.append((cfg.ratings.display, float(cfg.ratings.display_step), b.tie_break, cfg.sellers.price_policy,
                     float(cfg.sellers.undercut_floor_markup), b.choice, float(b.logit_rating_weight),
                     float(b.logit_price_weight)))
        return oi(self, cfg, *a, **k)

    def run(cfg, *a, **k):
        out = orun(cfg, *a, **k)
        _GUARD.append(CR.guard(out))
        return out

    def mp(cfg, stalls, book):
        omp(cfg, stalls, book)
        pol, m = cfg.sellers.price_policy, float(cfg.sellers.undercut_floor_markup)
        for st in stalls:
            if st.exited_day is not None or st.counterfeit_of is not None or \
                    (st.licensed_from is not None and not st.white_label):
                continue
            p, k = st.price_cents, st.unit_cost_cents
            fl = (int(k) if m == 0 else BR._half_up(k * (1 + m))) if pol == "undercut" else None
            _PRICES.append((st.stype, p, (p - k) / p if p else 0.0, fl is not None and p == fl))

    init._pw_seen = True
    EB.BazaarEngine.__init__ = init
    EB.run = run
    BR.morning_prices = mp


def _price_summary() -> dict:
    out = {}
    for t in ("genuine", "seconds", "deceptive", "all"):
        xs = [x for x in _PRICES if t == "all" or x[0] == t]
        if xs:
            out[t] = {"n": len(xs), "price": float(np.mean([x[1] for x in xs])),
                      "margin": float(np.mean([x[2] for x in xs])), "at_floor": float(np.mean([x[3] for x in xs]))}
    return out


@contextlib.contextmanager
def _arm(c):
    orig = {m: m.load for m in PATCHED}
    ov = cell_overrides(c)
    for m in PATCHED:
        base = orig[m]
        m.load = lambda path=None, overrides=None, mode=None, _b=base: _b(path, [*(overrides or []), *ov], mode=mode)
    try:
        yield
    finally:
        for m, f in orig.items():
            m.load = f


def _profile_sums(prof: dict) -> dict:
    tot = {k: {p: 0.0 for p in PROFILES} for k in ("buyers", "purchases", "short", "value", "paid", "inspect")}
    for d in prof.values():
        for k in tot:
            for p in PROFILES:
                tot[k][p] += d[k][p]
    return tot


def slim(c, r: dict) -> dict:
    if c[0] == "A":
        out = {k: r[k] for k in ("key", "cond", "seed", "stall", "b", "totals", "busts", "fallbacks", "dec_catches",
                                 "dec_stall_days") if k in r}
        out["profile"] = _profile_sums(r["profile"])
        return out
    keep = ("key", "arm", "seed", "owner", "licensees", "win", "white_label", "profit_mismatch", "roy_mismatch",
            "digest", "totals")
    return {k: r[k] for k in keep if k in r}


def job(j) -> dict:
    c, spec = j
    _hooks()
    LB._PARKED.clear()
    _ENG.clear()
    _GUARD.clear()
    _PRICES.clear()
    t0 = time.time()
    with _arm(c):
        rec = (LB._job if c[0] == "A" else ES.job)(spec)
    secs = time.time() - t0
    rec = json.loads(json.dumps(rec))
    seen = sorted(set(_ENG))
    g = {k: sum(x[k] for x in _GUARD) for k in ("stuck_buyers", "idle_choosers", "parked", "buyer_days", "fallbacks")}
    return {"key": key(j), "cell": cell_name(c), "seed": seed_of(c, spec), "skey": skey(c, spec),
            "engine_version": ENGINE_VERSION, "rec": slim(c, rec), "prices": _price_summary(),
            "secs": round(secs, 2), "engines": len(_ENG), "seen": [list(x) for x in seen],
            "arm_ok": bool(_ENG) and seen == [cell_seen(c)] and len(_GUARD) == 1, "guard": g}


# ------------------------------------------------------------------ endpoints

def gain_per_seed(recs: list, cond: str, seeds, samples) -> list:
    G = LB.gains([r for r in recs if r["seed"] in seeds], samples)
    return LB.seed_mean(G, cond, seeds, "gain_unfloored")


def equity_per_seed(idx: dict, seeds, samples, fl: list, cn: str) -> list:
    vals = []
    for sd in seeds:
        v = []
        for s in samples[sd]:
            R = idx[ES.key(("R", B_T, sd, s, ES.ROYALTY, B_PN, ES.STEP))]
            W = idx[ES.key(("Wg", B_T, sd, s, ES.ROYALTY, B_PN, ES.STEP))]
            lic = R["licensees"]
            if W["licensees"] != lic or len(lic) != ES.N_LIC or not all(W["white_label"].values()):
                fl.append(f"{cn} {sd}|{s}: R and W_g licensees differ or are not 6 white labels")
            st = [s, *lic]
            jr, jg = E._J(R, st), E._J(W, st)
            if jr[0] != jr[1] or jg[0] != jg[1]:
                fl.append(f"{cn} {sd}|{s}: J identity fails")
            if R.get("profit_mismatch") or W.get("profit_mismatch") or R.get("roy_mismatch") or W.get("roy_mismatch"):
                fl.append(f"{cn} {sd}|{s}: ledger or royalty mismatch")
            v.append(jr[0] - jg[0])
        vals.append(float(np.mean(v)))
    return vals


def buyer_stats(recs: list, seeds) -> dict:
    """Never chains of an outcome-A cell: per seed, buyer surplus per buyer (cents) and shortfall rate, overall and
    by profile; and per seed the posted-price summary."""
    by = {r["seed"]: r for r in recs if r["rec"]["b"] == NEVER}
    out = {"surplus": {p: [] for p in (*PROFILES, "all")}, "shortfall": {p: [] for p in (*PROFILES, "all")},
           "price_genuine": [], "margin_genuine": [], "price_all": [], "margin_all": [], "at_floor_all": []}
    for sd in seeds:
        r = by[sd]
        P = r["rec"]["profile"]
        for p in (*PROFILES, "all"):
            ps = PROFILES if p == "all" else (p,)
            nb = sum(P["buyers"][q] for q in ps)
            npur = sum(P["purchases"][q] for q in ps)
            sur = sum(P["value"][q] - P["paid"][q] - P["inspect"][q] for q in ps)
            out["surplus"][p].append(sur / nb if nb else None)
            out["shortfall"][p].append(sum(P["short"][q] for q in ps) / npur if npur else None)
        pr = r["prices"]
        out["price_genuine"].append(pr.get("genuine", {}).get("price"))
        out["margin_genuine"].append(pr.get("genuine", {}).get("margin"))
        out["price_all"].append(pr["all"]["price"])
        out["margin_all"].append(pr["all"]["margin"])
        out["at_floor_all"].append(pr["all"]["at_floor"])
    return out


def slope(xs, ys_by_level: list[list]) -> list:
    """Per-seed least-squares slope of y over x; ys_by_level[i] = per-seed values at xs[i]."""
    x = np.array(xs, dtype=float)
    return [float(np.polyfit(x, np.array([ys[i] for ys in ys_by_level], dtype=float), 1)[0])
            for i in range(len(ys_by_level[0]))]


def side(st) -> str:
    if st["lo"] is None:
        return "n/a"
    return "above" if st["lo"] > 0 else "below" if st["hi"] < 0 else "includes"


def verdict(st, sign) -> str:
    s = side(st)
    if s == "n/a":
        return "not testable"
    if (sign > 0 and s == "above") or (sign < 0 and s == "below"):
        return "supported"
    if (sign > 0 and s == "below") or (sign < 0 and s == "above"):
        return "contradicted"
    return "not supported"


PW = {"PW1": ("Outcome A, undercut m = 0, detect_scale 0: the bust-out gain is > 0.", +1),
      "PW2": ("Outcome A, detect_scale 0: the slope of the gain over m ∈ {0, 0.1, 0.3} is < 0.", -1),
      "PW3": ("Outcome B: the slope of brand equity E over m ∈ {0, 0.1, 0.3} is > 0.", +1),
      "PW4": ("Outcome A, undercut m = 0, detect_scale 1: the bust-out gain is < 0.", -1)}


def analyse(recs: list, seeds, samples) -> tuple[dict, list]:
    fl = []
    by_cell: dict = {}
    for r in recs:
        by_cell.setdefault(r["cell"], []).append(r)
    gain, eq, buyers = {}, {}, {}
    for c in CELLS:
        cn = cell_name(c)
        rs = by_cell.get(cn, [])
        if c[0] == "A":
            gain[cn] = gain_per_seed([r["rec"] for r in rs], A_CONDS[c[2]], seeds, samples)
            buyers[cn] = buyer_stats(rs, seeds)
        else:
            eq[cn] = equity_per_seed({r["skey"]: r["rec"] for r in rs}, seeds, samples, fl, cn)
    ms = [LEVELS[lv][1] for lv in SLOPE_LEVELS]
    pw2 = slope(ms, [gain[cell_name(("A", lv, 0.0, "lex"))] for lv in SLOPE_LEVELS])
    pw3 = slope(ms, [eq[cell_name(("B", lv, "lex"))] for lv in SLOPE_LEVELS])
    vals = {"PW1": gain["A|U0|ds0|lex"], "PW2": pw2, "PW3": pw3, "PW4": gain["A|U0|ds1|lex"]}
    pred = {}
    for pid, (txt, sign) in PW.items():
        st = mean_ci(vals[pid])
        pred[pid] = {"text": txt, "est": st, "per_seed": vals[pid], "side": side(st), "verdict": verdict(st, sign)}
    est = {"gain": {cn: {**mean_ci(v), "per_seed": v} for cn, v in gain.items()},
           "E": {cn: {**mean_ci(v), "per_seed": v} for cn, v in eq.items()}}
    # D4 (2026-11-25, after the main run): engine.metrics.paired_diff(a, b) is b - a; the arguments were in the
    # wrong order, so the PW5 differences printed as RI - U0 (and lex - sharp). Order fixed; PW1-PW4 do not use it.
    pw5 = {"U0_minus_RI": {
        "gain_ds0": paired_diff(gain["A|RI|ds0|lex"], gain["A|U0|ds0|lex"]),
        "gain_ds1": paired_diff(gain["A|RI|ds1|lex"], gain["A|U0|ds1|lex"]),
        "E": paired_diff(eq["B|RI|lex"], eq["B|U0|lex"])},
        "sharp_minus_lex_U0_ds0": paired_diff(gain["A|U0|ds0|lex"], gain["A|U0|ds0|sharp"]),
        "slope_ds1": mean_ci(slope(ms, [gain[cell_name(("A", lv, 1.0, "lex"))] for lv in SLOPE_LEVELS])),
        "buyers": {}, "buyer_U0_minus_RI": {}}
    for cn, b in buyers.items():
        pw5["buyers"][cn] = {k: ({p: mean_ci([x for x in v if x is not None]) for p, v in b[k].items()}
                                 if isinstance(b[k], dict) else mean_ci([x for x in b[k] if x is not None]))
                             for k in b}
    for ds in (0, 1):
        u, r = buyers[f"A|U0|ds{ds}|lex"], buyers[f"A|RI|ds{ds}|lex"]
        pw5["buyer_U0_minus_RI"][f"ds{ds}"] = {
            "surplus": {p: paired_diff(r["surplus"][p], u["surplus"][p]) for p in (*PROFILES, "all")},
            "shortfall": {p: paired_diff(r["shortfall"][p], u["shortfall"][p]) for p in (*PROFILES, "all")}}
    return {"pred": pred, "est": est, "pw5": pw5, "cells": [cell_name(c) for c in CELLS]}, fl


def checks(recs: list) -> tuple[dict, list]:
    flags, guard = [], {}
    for r in recs:
        g = guard.setdefault(r["cell"], {"chains": 0, "stuck_buyers": 0, "idle_choosers": 0, "parked": 0,
                                         "fallbacks": 0, "buyer_days": 0})
        g["chains"] += 1
        for k in ("stuck_buyers", "idle_choosers", "parked", "fallbacks", "buyer_days"):
            g[k] += r["guard"][k]
        if not r["arm_ok"]:
            flags.append(f"{r['key']}: engine settings {r['seen']} (runs {r['engines']}), not the cell's")
    for cn, g in guard.items():
        if g["stuck_buyers"] or g["parked"] or g["idle_choosers"] or g["fallbacks"]:
            flags.append(f"{cn}: stuck {g['stuck_buyers']}, parked {g['parked']}, idle {g['idle_choosers']}, "
                         f"invalid actions {g['fallbacks']}")
    return guard, flags


# ------------------------------------------------------------------ G2: reproduce the 1.1.0 undercut chains

def repro(a, log) -> dict:
    """Engine 1.2.0, undercut with m = 0 set explicitly, against the robustness sweep's undercut x lex chains
    (engine 1.1.0): liability col|t100|ds1.0 totals, seeds 230-231; brand-equity digests at prior_n 0 and 400,
    seeds 330-331."""
    import analysis.robustness_1_1 as R
    old = {}
    with open(SWEEP_CACHE, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["cell"] == "undercut|lex" and r["study"] in ("liability", "equity") and r["seed"] in (230, 231, 330,
                                                                                                       331):
                old[(r["study"], r["skey"])] = r["rec"]
    smp = {sd: V.sample_stalls(sd) for sd in (230, 231, 330, 331)}
    jobs = [("liability", s) for s in LB.jobs_for([R.LIAB_COND], [230, 231], smp)]
    for sd in (330, 331):
        for pn in (0.0, 400.0):
            jobs.append(("equity", ("never", "t40", sd, None, ES.ROYALTY, pn, ES.STEP)))
            jobs += [("equity", (arm, "t40", sd, s, ES.ROYALTY, pn, ES.STEP)) for s in smp[sd] for arm in ("R", "Wg")]
    rj = [(("R", "U0", "lex"), j) for j in jobs]       # a pseudo-cell carrying the U0 x lex overrides
    recs, _ = CR.run_chains(a, rj, None, log, _repro_job, lambda x: f"{x[1][0]}|{_rk(x[1])}")
    out = {"compared": 0, "matched": 0, "missing": 0, "bad": []}
    for r in recs:
        o = old.get((r["study"], r["skey"]))
        if o is None:
            out["missing"] += 1
            continue
        ok = (o["totals"] == r["rec"]["totals"]) if r["study"] == "liability" else (o["digest"] == r["rec"]["digest"])
        out["compared"] += 1
        out["matched"] += ok
        if not ok:
            out["bad"].append(r["skey"])
    out["pass"] = out["compared"] > 0 and out["matched"] == out["compared"] and out["missing"] == 0
    return out


def _rk(x) -> str:
    st, spec = x
    return LB._key(spec) if st == "liability" else ES.key(spec)


def _repro_job(j) -> dict:
    c, (st, spec) = j
    _hooks()
    LB._PARKED.clear()
    _ENG.clear()
    with _arm(c):
        rec = (LB._job if st == "liability" else ES.job)(spec)
    rec = json.loads(json.dumps(rec))
    return {"key": f"{st}|{_rk((st, spec))}", "study": st, "skey": _rk((st, spec)),
            "rec": {"totals": rec.get("totals"), "digest": rec.get("digest")}, "seen": sorted(set(_ENG))}


# ------------------------------------------------------------------ report

def _d(v, unit="$") -> str:
    if v is None:
        return "–"
    if unit == "%":
        return f"{100 * v:.1f}%"
    if unit == "x":
        return f"{v:+.3f}".replace("-", "−")
    return f"{v / 100:+,.2f}".replace("-", "−")


def _ci(st, unit="$") -> str:
    if st.get("mean") is None:
        return "–"
    s = _d(st["mean"], unit)
    if st.get("lo") is None:
        return s
    star = " *" if st["lo"] > 0 or st["hi"] < 0 else ""
    return f"{s} [{_d(st['lo'], unit)}, {_d(st['hi'], unit)}]{star}"


def plot_svg(res: dict, seeds_txt: str) -> str:
    """Three panels sharing the policy axis (RI, U0, U0.1, U0.3): the bust-out gain at detect_scale 0 and 1, and E.
    Mean and 95% t interval per level; the logit sharp cell as an open circle beside U0 in the ds 0 panel."""
    panels = [("Bust-out gain, no enforcement (ds 0)", "gain", "A|{}|ds0|lex"),
              ("Bust-out gain, enforcement (ds 1)", "gain", "A|{}|ds1|lex"),
              ("Brand equity E, prior_n 400", "E", "B|{}|lex")]
    W, H, pw = 900, 470, 270
    SER, SANS = '"ET Book",Palatino,Georgia,serif', "-apple-system,Helvetica,Arial,sans-serif"
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="Bust-out gain and '
         f'brand equity by price policy">', f'<rect width="{W}" height="{H}" fill="#fffff8"/>',
         f'<text x="20" y="30" font-family=\'{SER}\' font-size="19" fill="#111">Price war: bust-out gain and brand '
         f'equity by price policy</text>',
         f'<text x="20" y="52" font-family=\'{SER}\' font-size="13" fill="#666">RI = rating-indexed prices; U0, U0.1, '
         f'U0.3 = undercut with a floor at unit cost × (1 + m); dollars, mean and 95% t interval over seeds</text>']
    lv = list(LEVELS)
    for i, (title, kind, pat) in enumerate(panels):
        x0, y0, y1 = 30 + i * (pw + 20), 90, H - 80
        est = res["est"][kind]
        sts = [est[pat.format(l)] for l in lv]
        extra = est.get("A|U0|ds0|sharp") if i == 0 else None
        vals = [v for st in sts + ([extra] if extra else []) for v in (st["lo"], st["hi"], st["mean"]) if v is not None]
        lo, hi = min(vals + [0]), max(vals + [0])
        pad = (hi - lo) * 0.08 or 1
        lo, hi = lo - pad, hi + pad
        Y = lambda v: y1 - (v - lo) / (hi - lo) * (y1 - y0)
        X = lambda k: x0 + 50 + k * (pw - 70) / (len(lv) - 1)
        o.append(f'<text x="{x0}" y="{y0 - 14}" font-family=\'{SER}\' font-size="14" fill="#111">{title}</text>')
        o.append(f'<line x1="{x0 + 40}" y1="{Y(0):.1f}" x2="{x0 + pw}" y2="{Y(0):.1f}" stroke="#ccc" '
                 f'stroke-width="1"/>')
        for t in (lo + pad, 0, hi - pad):
            o.append(f'<text x="{x0 + 34}" y="{Y(t) + 4:.1f}" text-anchor="end" font-family="{SANS}" font-size="10" '
                     f'fill="#999">{_d(t).replace(".00", "") if t else "0"}</text>')
        for k, (l, st) in enumerate(zip(lv, sts)):
            if st["lo"] is not None:
                o.append(f'<line x1="{X(k):.1f}" y1="{Y(st["lo"]):.1f}" x2="{X(k):.1f}" y2="{Y(st["hi"]):.1f}" '
                         f'stroke="#666" stroke-width="1.5"/>')
            if st["mean"] is not None:
                col = "#e41a1c" if l == "U0" else "#333"
                o.append(f'<circle cx="{X(k):.1f}" cy="{Y(st["mean"]):.1f}" r="3.5" fill="{col}"/>')
            o.append(f'<text x="{X(k):.1f}" y="{y1 + 18}" text-anchor="middle" font-family="{SANS}" font-size="11" '
                     f'fill="#666">{l}</text>')
        if extra and extra["mean"] is not None:
            xs = X(1) + 18
            if extra["lo"] is not None:
                o.append(f'<line x1="{xs:.1f}" y1="{Y(extra["lo"]):.1f}" x2="{xs:.1f}" y2="{Y(extra["hi"]):.1f}" '
                         f'stroke="#999" stroke-width="1" stroke-dasharray="2,2"/>')
            o.append(f'<circle cx="{xs:.1f}" cy="{Y(extra["mean"]):.1f}" r="3.5" fill="#fffff8" stroke="#666"/>')
            o.append(f'<text x="{xs + 6:.1f}" y="{Y(extra["mean"]) + 4:.1f}" font-family=\'{SER}\' font-size="11" '
                     f'font-style="italic" fill="#666">logit</text>')
    o.append(f'<text x="20" y="{H - 30}" font-family="{SANS}" font-size="10" fill="#aaa">Bazaar engine '
             f'{ENGINE_VERSION}, analysis/price_war.py; seeds {seeds_txt}, paired. Gain: best bust-out day (20–30) '
             f'minus never, 30 days, tourist share 0.4 with locals inspecting,</text>')
    o.append(f'<text x="20" y="{H - 16}" font-family="{SANS}" font-size="10" fill="#aaa">mean of 3 genuine stalls '
             f'per seed. E: J(R) − J(W_g), days 10–60, t40, 6 licensees. Red: U0 (floor at unit cost). Intervals '
             f'unadjusted.</text>')
    o.append("</svg>")
    return "\n".join(o)


def report(res, meta, guard, flags, rep) -> str:
    P = res["pred"]
    L_ = ["# Price-war study (Stage 2, engine 1.2.0)", "",
          f"Engine {meta['engine_version']}, commit {meta['commit']}, script sha256 {meta['script_sha256'][:12]}; "
          f"{meta['chains']} chains, {meta['wall_h']:.2f} h on {meta['workers']} workers; seeds {meta['seeds_txt']}, "
          f"paired. Intervals: 95% t over seeds, unadjusted.", "",
          "## Predictions", "", "| | Prediction | Estimate [95% CI] | Verdict |", "|---|---|---|---|"]
    for pid, p in P.items():
        L_.append(f"| {pid} | {p['text']} | {_ci(p['est'])}{' per unit of m' if pid in ('PW2', 'PW3') else ''} | "
                  f"**{p['verdict']}** |")
    L_ += ["", "Rule (fixed before the run): supported if the interval lies on the predicted side of 0; "
           "contradicted if on the other side; otherwise not supported. Slopes are in dollars per unit of m "
           "(per seed, least squares over m = 0, 0.1, 0.3).", "",
           "## Outcome A: bust-out gain by cell", "", "| Cell | Gain [95% CI] |", "|---|---|"]
    for cn, st in res["est"]["gain"].items():
        L_.append(f"| {cn} | {_ci(st)} |")
    L_ += ["", "## Outcome B: brand equity E by cell", "", "| Cell | E [95% CI] |", "|---|---|"]
    for cn, st in res["est"]["E"].items():
        L_.append(f"| {cn} | {_ci(st)} |")
    w = res["pw5"]
    L_ += ["", "## PW5 (exploratory)", "", "### Undercut m = 0 against rating-indexed (paired)", "",
           "| Outcome | U0 − RI [95% CI] |", "|---|---|",
           f"| Gain, ds 0 | {_ci(w['U0_minus_RI']['gain_ds0'])} |",
           f"| Gain, ds 1 | {_ci(w['U0_minus_RI']['gain_ds1'])} |",
           f"| E, prior_n 400 | {_ci(w['U0_minus_RI']['E'])} |",
           f"| Gain slope over m, ds 1 | {_ci(w['slope_ds1'])} |",
           f"| Logit sharp − lex, U0, ds 0 | {_ci(w['sharp_minus_lex_U0_ds0'])} |", "",
           "### Prices, margins and buyers (never chains, outcome A market)", "",
           "Posted prices: own-name stalls every morning; margin = (price − unit cost) / price; at floor = share of "
           "stall-days posting exactly the undercut floor. Buyer surplus = value − paid − inspection cost, per buyer "
           "who arrived, dollars; shortfall = share of purchases below the buyer's quality requirement.", "",
           "| Cell | Genuine price | Genuine margin | All margin | At floor | Surplus per buyer | Shortfall |",
           "|---|---|---|---|---|---|---|"]
    for cn, b in w["buyers"].items():
        L_.append(f"| {cn} | {_d(b['price_genuine']['mean']).lstrip('+')} | {_d(b['margin_genuine']['mean'], '%')} | "
                  f"{_d(b['margin_all']['mean'], '%')} | {_d(b['at_floor_all']['mean'], '%')} | "
                  f"{_ci(b['surplus']['all'])} | {_d(b['shortfall']['all']['mean'], '%')} |")
    L_ += ["", "### Do the price war's lower prices outweigh its fraud for buyers? U0 − RI, never chains (paired)", "",
           "| | Profile | Surplus per buyer [95% CI] | Shortfall rate [95% CI] |", "|---|---|---|---|"]
    for ds, d in w["buyer_U0_minus_RI"].items():
        for p in (*PROFILES, "all"):
            L_.append(f"| {ds} | {p} | {_ci(d['surplus'][p])} | {_ci(d['shortfall'][p], 'x')} |")
    L_ += ["", "## Checks", "",
           f"- G2, reproduction of the 1.1.0 undercut chains with m = 0: {rep.get('matched', '–')} of "
           f"{rep.get('compared', '–')} match ({'pass' if rep.get('pass') else 'see pilot'}).",
           f"- Guard (stuck, parked, idle, invalid actions) summed over {sum(g['chains'] for g in guard.values())} "
           f"chains: {sum(g['stuck_buyers'] for g in guard.values())}, {sum(g['parked'] for g in guard.values())}, "
           f"{sum(g['idle_choosers'] for g in guard.values())}, {sum(g['fallbacks'] for g in guard.values())}.",
           f"- Flags: {len(flags)}." + ("" if not flags else " " + "; ".join(flags[:20])), "",
           "![Bust-out gain and brand equity by price policy](price_war.svg)", ""]
    return "\n".join(L_)


# ------------------------------------------------------------------ main

def _git_commit() -> tuple[str, bool]:
    c = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    d = subprocess.run(["git", "status", "--porcelain", "--", "engine", "agents", "analysis"], capture_output=True,
                       text=True).stdout.strip()
    return c, bool(d)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=None, help="pilot seeds (900-902); default the main seeds 500-519")
    ap.add_argument("--cut", action="store_true", help="G3 cut: seeds 500-514")
    ap.add_argument("--repro", action="store_true", help="G2 only")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--outdir", default=OUT)
    ap.add_argument("--tests", default="")
    ap.add_argument("--min-swap-mb", type=float, default=512)
    ap.add_argument("--min-free-pct", type=float, default=15)
    a = ap.parse_args(argv)
    LB._lower_priority()
    os.makedirs(a.outdir, exist_ok=True)
    pilot = a.seeds is not None
    if (pilot or a.repro) and os.path.abspath(a.outdir) == os.path.abspath(OUT):
        raise SystemExit("--seeds and --repro write to a pilot --outdir, not runs")
    log = CR.file_logger(os.path.join(a.outdir, "price_war_run.log"))
    commit, dirty = _git_commit()
    meta = {"engine_version": ENGINE_VERSION, "commit": commit, "code_dirty": dirty, "script_sha256": _script_sha(),
            "command": " ".join(["python -m analysis.price_war", *sys.argv[1:]]), "tests": a.tests,
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
            "workers": a.workers, "load_start": _load(), "mem_start": memory_state(),
            "cells": [cell_name(c) for c in CELLS], "market_defaults": MARKET_DEFAULTS,
            "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    log(f"run record {json.dumps(meta, sort_keys=True)}")
    if dirty:
        raise SystemExit("engine, agents or analysis has uncommitted changes: commit before running")
    if a.repro:
        t0 = time.time()
        rep = repro(a, log)
        rep["wall_h"] = (time.time() - t0) / 3600
        log(f"G2 reproduction: {json.dumps(rep)}")
        with open(os.path.join(a.outdir, "price_war_repro.json"), "w", encoding="utf-8") as f:
            json.dump({"meta": meta, "repro": rep}, f, indent=1)
        return 0 if rep["pass"] else 2
    seeds = parse_seeds(a.seeds) if pilot else (CUT_SEEDS if a.cut else MAIN_SEEDS)
    samples = {sd: V.sample_stalls(sd) for sd in seeds}
    jobs = [(c, s) for c in CELLS for s in specs(c, seeds, samples)]
    t0 = time.time()
    cache = os.path.join(a.outdir, "price_war_cache.jsonl")
    recs, pauses = CR.run_chains(a, jobs, cache, log, job, key)
    want = {key(j) for j in jobs}
    recs = [r for r in recs if r["key"] in want]
    res, fl = analyse(recs, seeds, samples)
    guard, flags = checks(recs)
    flags = fl + flags
    wall = time.time() - t0
    meta.update(chains=len(recs), pauses=pauses, wall_h=wall / 3600, load_end=_load(), mem_end=memory_state(),
                seeds_txt=f"{seeds[0]}–{seeds[-1]}")
    rep = {}
    rp = os.path.join(a.outdir if pilot else "runs/pilot_price_war", "price_war_repro.json")
    if os.path.exists(rp):
        with open(rp, encoding="utf-8") as f:
            rep = json.load(f)["repro"]
    if pilot:
        secs = float(np.sum([r["secs"] for r in recs]))
        proj = {n: secs / len(seeds) * n / a.workers / 3600 for n in (len(MAIN_SEEDS), len(CUT_SEEDS))}
        gates = {"G1": {"pass": len(recs) == len(jobs) and not fl, "chains": len(recs), "jobs": len(jobs),
                        "analysis_flags": fl},
                 "G3": {"pass": proj[len(MAIN_SEEDS)] <= TIME_LIMIT_H, "projected_h_20_seeds": proj[len(MAIN_SEEDS)],
                        "projected_h_15_seeds": proj[len(CUT_SEEDS)], "limit_h": TIME_LIMIT_H,
                        "chain_cpu_s": secs, "wall_h": wall / 3600},
                 "G4": {"pass": not flags, "guard": guard, "flags": flags}}
        log(f"pilot gates {json.dumps(gates)}")
        with open(os.path.join(a.outdir, "price_war_pilot_gates.json"), "w", encoding="utf-8") as f:
            json.dump({"meta": meta, "gates": gates, "results": res}, f, indent=1, default=str)
        return 0 if all(g["pass"] for g in gates.values()) else 2
    with gzip.open(os.path.join(a.outdir, "price_war.json.gz"), "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": res, "guard": guard, "flags": flags, "repro": rep,
                   "samples": {str(k): v for k, v in samples.items()}}, f, indent=1, default=str)
    with open(os.path.join(a.outdir, "price_war.svg"), "w", encoding="utf-8") as f:
        f.write(plot_svg(res, meta["seeds_txt"]))
    with open(os.path.join(a.outdir, "price_war_summary.md"), "w", encoding="utf-8") as f:
        f.write(report(res, meta, guard, flags, rep))
    for pid, p in res["pred"].items():
        log(f"{pid}: {p['verdict']} {json.dumps({k: p['est'][k] for k in ('mean', 'lo', 'hi')})}")
    log(f"done; {len(flags)} flags; wall {meta['wall_h']:.2f} h; load {_load()}")
    for x in flags:
        log(f"FLAG: {x}")
    return 2 if flags else 0


if __name__ == "__main__":
    raise SystemExit(main())
