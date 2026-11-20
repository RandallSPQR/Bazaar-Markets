"""Stage 3C: robustness sweep at engine 1.1.0 (rule-based only). Plan: runs/plan_autonomous_2026-11-19.md, 3C.
Predictions PX1-PX4 (confirmatory) and PX5 (exploratory) were fixed in the plan on 2026-11-19, before any run; the
verdict rule, the cell definitions below and the trims were written down here on 2026-11-20, before any sweep chain
was run.

Question: do the headline results of the earlier runs survive other seller pricing rules and a noisier buyer choice?

Cells: price policy (sellers.price_policy) x buyer choice:
  policies  rating_indexed (the 1.0.0 rule), cost_plus (markup 0.5), match_rival, undercut, promo
  choices   lex = lexicographic (the 1.0.0 rule); soft = logit (rating weight 5, price weight 5);
            sharp = logit (20, 20)
Base market: each study's own market as its run built it, with the market defaults of operating rule 6 on top
(ratings.display stars, display_step 0.02, buyers.tie_break random), then the cell's policy and choice. The overrides
are appended to every engine.config.load call the study's config builder makes (as analysis/stars_sensitivity.py);
every engine a chain builds is checked to run with the intended display, step, tie-break, policy and choice.
rating_indexed x lex is therefore the 1.0.0 market under stars: the "1.0.0" column for PX5.

Headline cells (seeds: the first 10 of each original run; chains as each study builds them):
  verification  analysis/verification.py, seeds 200-209, Stage A (no inspectors): A|t100 and A|t40|l1; per seed and
                condition 1 never chain + 3 sampled stalls x 5 bust-out days. Endpoints: the bust-out gain
                (unfloored, per-seed mean over the 3 stalls) at t100 and at t40|l1.
  liability     analysis/liability.py, seeds 230-239, col|t100|ds1.0 (2 patrolling inspectors, detect_scale 1,
                collectible fines); the same 16 chains per seed. Endpoint: the bust-out gain under enforcement.
  licensing     analysis/brand_equity.py, seeds 300-309, t40, detect_scale 1, owner not liable, N 6 from day 10,
                royalty 0.10, owner's brand (arm R), contract and cheap quality, and the never chain. The plan's
                "joint profit (R - never)" is brand_equity's J: owner + its 6 licensees' profit, days 10-30 (royalties
                cancel), R - never over the same 7 stalls; per seed the mean over the 3 owners.
  canal         analysis/canal_street.py, seeds 270-279, t100, ds 1: off and phi 1.0, 0.8, 0.6, 0.4. Endpoints: PK1
                (per-seed least-squares slope of the gap over 1 - phi; gap = deceptive stalls' 30-day profit, on -
                off), PK3 (copied originals' day-30 rating, on - off, phi 0.6), PK2 (gap at phi 1.0, context).
  brand equity  analysis/brand_equity_stars.py, seeds 330-339, 60 days, t40, contract, N 6 from day 10, royalty
                0.10, prior_n 0 and 400 (scope new): never, R and W_g per owner. Endpoint: E = J(R) - J(W_g),
                days 10-60, per seed the mean over the 3 owners.

Predictions (plan 3C):
  PX1 (confirmatory) in every policy x choice cell, the bust-out gain under enforcement (liability) is < 0.
  PX2 (confirmatory) in every cell, the t100 gain without inspectors exceeds the t40|l1 gain (paired by seed).
  PX3 (confirmatory) in every cell, contract licensing's joint gain (R - never) exceeds cheap licensing's (paired).
  PX4 (confirmatory) under logit sharp with rating_indexed, Canal Street's PK1 slope is > 0.
  PX5 (exploratory) every other estimate in every cell, with sign and verdict changes against rating_indexed x lex
      flagged; this includes whether E at prior_n 400 stays positive under each price policy.
Verdict rule (fixed before any run). Each cell's 95% t interval over the 10 seeds, unadjusted. For PX1-PX3: supported
if every cell's interval is on the predicted side of 0; contradicted if any cell's interval is on the opposite side;
otherwise not supported. Each cell's own verdict is reported. PX4 is one cell, by the same rule. PX5 has no verdicts;
a "change" is a cell whose point estimate has the other sign from rating_indexed x lex, or whose interval sits on a
different side of 0 (above / includes / below).

Trims (plan 3C): the run must fit in 10 h. If the timing pilot projects more, drop promo, then match_rival, then logit
soft, in that order, until it fits; decided from the timing alone, before launch, with --policies / --choices.

Checks built in: rating_indexed x lex chains are compared with the saved stars chains of the same seeds (verification
and liability totals, canal profits and day-30 ratings: runs/stars_sensitivity_cache.jsonl; brand equity full-outcome
digests: runs/brand_equity_stars_cache.jsonl), which engine 1.1.0 at its defaults must reproduce; the per-seed
endpoints of those chains must equal the saved runs'. Guard counts (stuck, parked, idle choosers, invalid actions),
each engine's settings, J identities and licence sizes are checked; exit 2 on any flag.

    .venv/bin/python -m analysis.robustness_1_1 --timing                                    # seconds per chain
    .venv/bin/python -m analysis.robustness_1_1 --seeds 900 --outdir runs/pilot_robustness   # smoke
    .venv/bin/python -m analysis.robustness_1_1 --tests "..." [--policies ... --choices ...]  # main run
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

import numpy as np

import analysis.brand_equity as E
import analysis.brand_equity_speed as S
import analysis.brand_equity_stars as ES
import analysis.canal_street as CS
import analysis.chainrun as CR
import analysis.liability as LB
import analysis.licensing as L
import analysis.licensing_checks as LC
import analysis.verification as V
from analysis.capture import memory_state
from analysis.counterfeit import _load
from cli.sweep import parse_seeds
from engine import ENGINE_VERSION, benchmark
from engine import bazaar as EB
from engine.metrics import mean_ci, paired_diff

NEVER = benchmark.NEVER
POLICIES = ("rating_indexed", "cost_plus", "match_rival", "undercut", "promo")
CHOICES = {"lex": ("lexicographic", 5.0, 5.0), "soft": ("logit", 5.0, 5.0), "sharp": ("logit", 20.0, 20.0)}
BASE_CELL = ("rating_indexed", "lex")
TRIM_ORDER = ("promo", "match_rival", "soft")
MARKET_DEFAULTS = ["ratings.display=stars", "ratings.display_step=0.02", "buyers.tie_break=random"]
STUDIES = ("verification", "liability", "licensing", "canal", "equity")
ORIG_SEEDS = {"verification": list(range(200, 220)), "liability": list(range(230, 250)),
              "licensing": list(range(300, 330)), "canal": list(range(270, 300)), "equity": list(range(330, 350))}
VER_CONDS = ["A|t100", "A|t40|l1"]
LIAB_COND = "col|t100|ds1.0"
CANAL_ARMS = CS.ARMS                                   # off, phi1.0, phi0.8, phi0.6, phi0.4
CANAL_T, CANAL_DS = "t100", 1.0
LIC_T = "t40"
EQ_T, EQ_LEVELS = "t40", {"pn0": 0.0, "pn400": 400.0}
EQ_STEP = ES.STEP
PATCHED = [m for m in (V, LB, L, CS, LC, E, S, ES) if hasattr(m, "load")]
STARS_CACHE = "runs/stars_sensitivity_cache.jsonl"
EQ_CACHE = "runs/brand_equity_stars_cache.jsonl"
OUT = "runs"


def cell_name(cell) -> str:
    return f"{cell[0]}|{cell[1]}"


def cell_overrides(cell) -> list[str]:
    pol, ch = cell
    rule, wr, wp = CHOICES[ch]
    return [*MARKET_DEFAULTS, f"sellers.price_policy={pol}", f"buyers.choice={rule}",
            f"buyers.logit_rating_weight={wr!r}", f"buyers.logit_price_weight={wp!r}"]


def cell_seen(cell) -> tuple:
    pol, ch = cell
    rule, wr, wp = CHOICES[ch]
    return ("stars", 0.02, "random", pol, rule, wr, wp)


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ specs per study

def specs(study, seeds, samples) -> list[tuple]:
    if study == "verification":
        return V.jobs_for(VER_CONDS, seeds, samples)
    if study == "liability":
        return LB.jobs_for([LIAB_COND], seeds, samples)
    if study == "canal":
        return [(f"{arm}|{CANAL_T}|ds{CANAL_DS!r}", sd) for sd in seeds for arm in CANAL_ARMS]
    if study == "licensing":
        out = []
        for sd in seeds:
            out.append(("never", "-", LIC_T, sd, None, E.ROYALTY))
            out += [("R", q, LIC_T, sd, s, E.ROYALTY) for q in E.QUALS for s in samples[sd]]
        return out
    out = []
    for sd in seeds:
        for pn in EQ_LEVELS.values():
            out.append(("never", EQ_T, sd, None, ES.ROYALTY, pn, EQ_STEP))
            out += [(arm, EQ_T, sd, s, ES.ROYALTY, pn, EQ_STEP) for s in samples[sd] for arm in ("R", "Wg")]
    return out


def skey(study, spec) -> str:
    return {"verification": V._key, "liability": LB._key, "canal": CS.key, "licensing": E.key,
            "equity": ES.key}[study](spec)


def seed_of(study, spec) -> int:
    return int(spec[{"verification": 2, "liability": 1, "canal": 1, "licensing": 3, "equity": 2}[study]])


def _jobfn(study):
    return {"verification": V._job, "liability": LB._job, "canal": CS.job, "licensing": E.job, "equity": ES.job}[study]


def slim(study, r: dict) -> dict:
    if study in ("verification", "liability"):
        return {k: r[k] for k in ("key", "cond", "seed", "stall", "b", "totals", "busts", "fallbacks") if k in r}
    if study == "canal":
        return {"key": r["key"], "cond": r["cond"], "seed": r["seed"],
                "stype": {s: v["stype"] for s, v in r["stalls"].items()},
                "profit30": {s: int(sum(v)) for s, v in r["series"]["profit"].items()},
                "rating30": {s: v[CS.DAYS - 1] for s, v in r["rating"].items()},
                "copied": r["copied"], "profit_mismatch": r.get("profit_mismatch", 0)}
    keep = ("key", "arm", "seed", "owner", "licensees", "win", "white_label", "profit_mismatch", "roy_mismatch",
            "digest", "totals")
    return {k: r[k] for k in keep if k in r}


# ------------------------------------------------------------------ worker

_ENG: list = []
_GUARD: list = []


def _hooks() -> None:
    """Observers that change nothing: each engine's settings, and each run's guard counts."""
    if getattr(EB.BazaarEngine.__init__, "_rob_seen", False):
        return
    oi, orun = EB.BazaarEngine.__init__, EB.run

    def init(self, cfg, *a, **k):
        b = cfg.buyers
        _ENG.append((cfg.ratings.display, float(cfg.ratings.display_step), b.tie_break, cfg.sellers.price_policy,
                     b.choice, float(b.logit_rating_weight), float(b.logit_price_weight)))
        return oi(self, cfg, *a, **k)

    def run(cfg, *a, **k):
        out = orun(cfg, *a, **k)
        _GUARD.append(CR.guard(out))
        return out

    init._rob_seen = True
    EB.BazaarEngine.__init__ = init
    EB.run = run


@contextlib.contextmanager
def _arm(cell):
    orig = {m: m.load for m in PATCHED}
    ov = cell_overrides(cell)
    for m in PATCHED:
        base = orig[m]
        m.load = lambda path=None, overrides=None, mode=None, _b=base: _b(path, [*(overrides or []), *ov], mode=mode)
    try:
        yield
    finally:
        for m, f in orig.items():
            m.load = f


def key(j) -> str:
    study, cell, spec = j
    return f"{study}|{cell_name(cell)}|{skey(study, spec)}"


def job(j) -> dict:
    study, cell, spec = j
    _hooks()
    LB._PARKED.clear()
    _ENG.clear()
    _GUARD.clear()
    t0 = time.time()
    with _arm(cell):
        rec = _jobfn(study)(spec)
    secs = time.time() - t0
    rec = json.loads(json.dumps(rec))
    seen = sorted(set(_ENG))
    g = {k: sum(x[k] for x in _GUARD) for k in ("stuck_buyers", "idle_choosers", "parked", "buyer_days", "fallbacks")}
    return {"key": key(j), "study": study, "cell": cell_name(cell), "seed": seed_of(study, spec),
            "skey": skey(study, spec), "engine_version": ENGINE_VERSION, "rec": slim(study, rec),
            "secs": round(secs, 2), "engines": len(_ENG), "seen": [list(x) for x in seen],
            "arm_ok": bool(_ENG) and seen == [cell_seen(cell)] and len(_GUARD) == 1, "guard": g}


# ------------------------------------------------------------------ endpoints

def _r05(x):
    return 0.5 if x is None else x


def endpoints(study, idx: dict, seeds, samples) -> tuple[dict, list]:
    """({endpoint: per-seed values}, flags) for one cell; idx = {study key: slim record}."""
    fl = []
    if study == "verification":
        G = V.gains([r for r in idx.values() if r["seed"] in seeds], samples)
        a, b = (V.seed_mean(G, c, seeds, "gain_unfloored") for c in VER_CONDS)
        return {"ver_t100": a, "ver_t40l1": b, "ver_t100_minus_t40l1": [x - y for x, y in zip(a, b)]}, fl
    if study == "liability":
        G = LB.gains([r for r in idx.values() if r["seed"] in seeds], samples)
        return {"liab_t100_ds1": LB.seed_mean(G, LIAB_COND, seeds, "gain_unfloored")}, fl
    if study == "canal":
        x = np.array([1 - p for p in CS.PHIS])
        slope, pk3, pk2, gaps = [], [], [], {p: [] for p in CS.PHIS}
        for sd in seeds:
            o = idx[f"off|{CANAL_T}|ds{CANAL_DS!r}|{sd}"]
            dec = [s for s, t in o["stype"].items() if t == "deceptive"]
            for p in CS.PHIS:
                r = idx[f"phi{p!r}|{CANAL_T}|ds{CANAL_DS!r}|{sd}"]
                gaps[p].append(float(np.mean([r["profit30"][s] - o["profit30"][s] for s in dec])))
            slope.append(float(np.polyfit(x, np.array([gaps[p][-1] for p in CS.PHIS]), 1)[0]))
            r6 = idx[f"phi0.6|{CANAL_T}|ds{CANAL_DS!r}|{sd}"]
            orig = sorted({v for v in r6["copied"].values() if v is not None})
            pk3.append(float(np.mean([_r05(r6["rating30"][s]) - _r05(o["rating30"][s]) for s in orig]))
                       if orig else None)
            if not orig:
                fl.append(f"canal seed {sd}: no copied original at phi 0.6")
            pk2.append(gaps[1.0][-1])
        return {"PK1_slope": slope, "PK3_rating": pk3, "PK2_gap": pk2,
                **{f"gap_phi{p:g}": gaps[p] for p in CS.PHIS}}, fl
    if study == "licensing":
        per = {q: [] for q in E.QUALS}
        for sd in seeds:
            nv = idx[E.key(("never", "-", LIC_T, sd, None, E.ROYALTY))]
            for q in E.QUALS:
                vals = []
                for s in samples[sd]:
                    R = idx[E.key(("R", q, LIC_T, sd, s, E.ROYALTY))]
                    lic = R["licensees"]
                    if len(lic) != E.N_LIC:
                        fl.append(f"licensing {q}|{sd}|{s}: {len(lic)} licensees, not {E.N_LIC}")
                    st = [s, *lic]
                    jr, jn = E._J(R, st), E._J(nv, st)
                    if jr[0] != jr[1] or jn[0] != jn[1]:
                        fl.append(f"licensing {q}|{sd}|{s}: J identity fails")
                    vals.append(jr[0] - jn[0])
                per[q].append(float(np.mean(vals)))
        return {"lic_contract": per["contract"], "lic_cheap": per["cheap"],
                "lic_contract_minus_cheap": [a - b for a, b in zip(per["contract"], per["cheap"])]}, fl
    out = {}
    for lab, pn in EQ_LEVELS.items():
        vals = []
        for sd in seeds:
            v = []
            for s in samples[sd]:
                R = idx[ES.key(("R", EQ_T, sd, s, ES.ROYALTY, pn, EQ_STEP))]
                W = idx[ES.key(("Wg", EQ_T, sd, s, ES.ROYALTY, pn, EQ_STEP))]
                lic = R["licensees"]
                if W["licensees"] != lic or len(lic) != ES.N_LIC or not all(W["white_label"].values()):
                    fl.append(f"equity {lab}|{sd}|{s}: R and W_g licensees differ or are not 6 white labels")
                st = [s, *lic]
                jr, jg = E._J(R, st), E._J(W, st)
                if jr[0] != jr[1] or jg[0] != jg[1]:
                    fl.append(f"equity {lab}|{sd}|{s}: J identity fails")
                v.append(jr[0] - jg[0])
            vals.append(float(np.mean(v)))
        out[f"E_{lab}"] = vals
    return out, fl


# Every endpoint: (study, id, label, unit, prediction sign for PX1-PX4 or None, prediction id)
ENDPOINTS = [
    ("liability", "liab_t100_ds1", "Bust-out gain under enforcement (t100, ds 1)", "$", -1, "PX1"),
    ("verification", "ver_t100_minus_t40l1", "No inspectors: t100 gain − t40|l1 gain", "$", +1, "PX2"),
    ("licensing", "lic_contract_minus_cheap", "t40: joint gain R − never, contract − cheap", "$", +1, "PX3"),
    ("canal", "PK1_slope", "Canal Street PK1: slope of the gap over 1 − φ (t100, ds 1)", "$/unit", +1, "PX4"),
    ("verification", "ver_t100", "No inspectors, t100: bust-out gain", "$", None, None),
    ("verification", "ver_t40l1", "No inspectors, t40|l1: bust-out gain", "$", None, None),
    ("licensing", "lic_contract", "t40, contract: joint gain R − never", "$", None, None),
    ("licensing", "lic_cheap", "t40, cheap: joint gain R − never", "$", None, None),
    ("canal", "PK3_rating", "Canal Street PK3: copied originals' day-30 rating, on − off (φ 0.6)", "rating", None,
     None),
    ("canal", "PK2_gap", "Canal Street PK2: gap at φ 1.0", "$", None, None),
    ("equity", "E_pn0", "Brand equity E, t40, prior_n 0", "$", None, None),
    ("equity", "E_pn400", "Brand equity E, t40, prior_n 400", "$", None, None),
]
PX = {"PX1": "In every cell, the bust-out gain under enforcement is < 0.",
      "PX2": "In every cell, the tourist-only gain without inspectors exceeds the t40|l1 gain.",
      "PX3": "In every cell, contract licensing's joint gain exceeds cheap licensing's.",
      "PX4": "Under logit sharp with rating_indexed, Canal Street's PK1 slope is > 0."}


def side(st) -> str:
    if st["lo"] is None:
        return "n/a"
    return "above" if st["lo"] > 0 else "below" if st["hi"] < 0 else "includes"


def cell_verdict(st, sign) -> str:
    s = side(st)
    if s == "n/a":
        return "not testable"
    if (sign > 0 and s == "above") or (sign < 0 and s == "below"):
        return "supported"
    if (sign > 0 and s == "below") or (sign < 0 and s == "above"):
        return "contradicted"
    return "not supported"


def analyse(per: dict, cells: list, eps: list) -> dict:
    """per[cell name][endpoint id] = per-seed values; eps: the ENDPOINTS rows of the studies run."""
    res = {"cells": [cell_name(c) for c in cells], "est": {}, "pred": {}, "changes": [], "endpoints": eps}
    base = cell_name(BASE_CELL)
    for study, eid, lab, unit, sign, pid in eps:
        res["est"][eid] = {c: {**mean_ci(per[c][eid]), "per_seed": per[c][eid]} for c in res["cells"]}
    for study, eid, lab, unit, sign, pid in eps:
        if pid is None:
            continue
        cs = [cell_name(("rating_indexed", "sharp"))] if pid == "PX4" else res["cells"]
        cs = [c for c in cs if c in res["est"][eid]]
        v = {c: cell_verdict(res["est"][eid][c], sign) for c in cs}
        if not v:
            overall = "not run (cell trimmed)"
        elif any(x == "contradicted" for x in v.values()):
            overall = "contradicted"
        elif all(x == "supported" for x in v.values()):
            overall = "supported"
        else:
            overall = "not supported"
        res["pred"][pid] = {"text": PX[pid], "endpoint": eid, "cells": v, "verdict": overall}
    if base in res["cells"]:
        for study, eid, lab, unit, sign, pid in eps:
            b = res["est"][eid][base]
            for c in res["cells"]:
                if c == base:
                    continue
                x = res["est"][eid][c]
                sign_ch = b["mean"] is not None and x["mean"] is not None and np.sign(b["mean"]) != np.sign(x["mean"])
                side_ch = side(b) != side(x)
                if sign_ch or side_ch:
                    res["changes"].append({"endpoint": eid, "cell": c, "sign_change": bool(sign_ch),
                                           "side_change": bool(side_ch), "base_side": side(b), "side": side(x)})
    return res


# ------------------------------------------------------------------ checks

def _read_cache(path, prefix=None) -> dict:
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if prefix is None or r["key"].startswith(prefix):
                out[r["key"]] = r
    return out


def repro_check(recs_base: list) -> dict:
    """rating_indexed x lex chains against the saved stars chains of the same seeds."""
    st = _read_cache(STARS_CACHE)
    eq = _read_cache(EQ_CACHE)
    rows = {"compared": 0, "matched": 0, "missing": 0, "bad": []}
    for r in recs_base:
        s, rec = r["study"], r["rec"]
        if s in ("verification", "liability", "canal"):
            k = f"{s}|stars|{r['skey']}"
            if k not in st:
                rows["missing"] += 1
                continue
            old = st[k]["rec"]
            if s == "canal":
                ok = old["profit30"] == rec["profit30"] and \
                    {x: v[CS.DAYS - 1] for x, v in old["rating"].items()} == rec["rating30"]
            else:
                ok = old["totals"] == rec["totals"]
        elif s == "equity":
            if r["skey"] not in eq:
                rows["missing"] += 1
                continue
            ok = eq[r["skey"]]["digest"] == rec["digest"]
        else:
            continue
        rows["compared"] += 1
        rows["matched"] += ok
        if not ok:
            rows["bad"].append(r["key"])
    rows["pass"] = rows["compared"] > 0 and rows["matched"] == rows["compared"]
    return rows


def checks(recs: list, flags_ep: list) -> tuple[dict, list]:
    flags = list(flags_ep)
    guard = {}
    for r in recs:
        g = guard.setdefault(f"{r['study']}|{r['cell']}", {"chains": 0, "stuck_buyers": 0, "idle_choosers": 0,
                                                          "parked": 0, "fallbacks": 0, "buyer_days": 0})
        g["chains"] += 1
        for k in ("stuck_buyers", "idle_choosers", "parked", "fallbacks", "buyer_days"):
            g[k] += r["guard"][k]
        if not r["arm_ok"]:
            flags.append(f"{r['key']}: engine settings {r['seen']} (runs {r['engines']}), not the cell's")
        if r["rec"].get("profit_mismatch") or r["rec"].get("roy_mismatch"):
            flags.append(f"{r['key']}: ledger or royalty mismatch")
    for k, g in guard.items():
        if g["stuck_buyers"] or g["parked"] or g["fallbacks"]:
            flags.append(f"{k}: stuck {g['stuck_buyers']}, parked {g['parked']}, invalid actions {g['fallbacks']}")
    return guard, flags


# ------------------------------------------------------------------ report

def _fmt(v, unit) -> str:
    if v is None:
        return "–"
    if unit == "rating":
        return f"{v:+.3f}".replace("-", "−")
    return f"{v / 100:+,.2f}".replace("-", "−")


def _ci(st, unit) -> str:
    if st["mean"] is None:
        return "–"
    s = _fmt(st["mean"], unit)
    if st["lo"] is None:
        return s
    star = " *" if st["lo"] > 0 or st["hi"] < 0 else ""
    return f"{s} [{_fmt(st['lo'], unit)}, {_fmt(st['hi'], unit)}]{star}"


def plot_svg(res: dict) -> str:
    """Small multiples, one panel per endpoint: each cell's mean and 95% interval, cells down the page in policy
    order, the 0 line, the rating_indexed x lex cell darker. Tufte style."""
    eps = res["endpoints"]
    cells = res["cells"]
    W, ph, pw, cols = 960, 18 * len(cells) + 60, 300, 3
    rows = (len(eps) + cols - 1) // cols
    H = rows * ph + 70
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Palatino, Georgia, serif">',
           f'<rect width="{W}" height="{H}" fill="#fffff8"/>',
           '<text x="10" y="24" font-size="18" fill="#111">Headline estimates by price policy × buyer choice</text>',
           '<text x="10" y="44" font-size="12" fill="#666">mean and 95% t interval over 10 seeds, unadjusted; '
           'dark = rating_indexed × lex (the 1.0.0 market under stars); dollars except PK3 (rating)</text>']
    for i, (study, eid, lab, unit, sign, pid) in enumerate(eps):
        cx, cy = 10 + (i % cols) * (pw + 15), 60 + (i // cols) * ph
        est = res["est"][eid]
        vals = [v for c in cells for v in (est[c]["lo"], est[c]["hi"], est[c]["mean"]) if v is not None] + [0]
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1
        x0, x1 = cx + 120, cx + pw - 10
        X = lambda v: x0 + (v - lo) / span * (x1 - x0)
        out.append(f'<text x="{cx}" y="{cy + 14}" font-size="12" fill="#111">{(pid + ": ") if pid else ""}'
                   f'{lab[:52]}</text>')
        out.append(f'<line x1="{X(0):.1f}" y1="{cy + 22}" x2="{X(0):.1f}" y2="{cy + 22 + 18 * len(cells)}" '
                   'stroke="#ccc" stroke-width="0.5"/>')
        for j, c in enumerate(cells):
            y = cy + 32 + 18 * j
            st = est[c]
            col = "#111" if c == cell_name(BASE_CELL) else "#888"
            out.append(f'<text x="{cx}" y="{y + 4}" font-size="10" fill="#999" font-family="sans-serif">'
                       f'{c.replace("rating_indexed", "rating_idx")}</text>')
            if st["lo"] is not None:
                out.append(f'<line x1="{X(st["lo"]):.1f}" y1="{y}" x2="{X(st["hi"]):.1f}" y2="{y}" stroke="{col}" '
                           'stroke-width="1"/>')
            if st["mean"] is not None:
                out.append(f'<circle cx="{X(st["mean"]):.1f}" cy="{y}" r="2.2" fill="{col}"/>')
        f = (lambda v: f"{v:+.2f}") if unit == "rating" else (lambda v: f"{v / 100:+,.0f}")
        out.append(f'<text x="{x0}" y="{cy + 40 + 18 * len(cells)}" font-size="9" fill="#999" '
                   f'font-family="sans-serif">{f(lo)}</text>')
        out.append(f'<text x="{x1}" y="{cy + 40 + 18 * len(cells)}" font-size="9" fill="#999" text-anchor="end" '
                   f'font-family="sans-serif">{f(hi)}</text>')
    out.append(f'<text x="10" y="{H - 8}" font-size="10" fill="#aaa" font-family="sans-serif">Bazaar engine '
               f'{ENGINE_VERSION}; analysis/robustness_1_1.py; first 10 seeds of each original run.</text></svg>')
    return "\n".join(out)


def report(res, meta, guard, flags, rep) -> str:
    L_ = ["# Robustness sweep at engine 1.1.0 (Stage 3C)", "",
          f"Engine {meta['engine_version']}, commit {meta['commit']}, script sha256 {meta['script_sha256'][:12]}; "
          f"{meta['chains']} chains, {meta['wall_h']:.2f} h on {meta['workers']} workers. Cells: "
          f"{', '.join(res['cells'])}. Seeds: {meta['seeds_txt']}. Intervals: 95% t over seeds, unadjusted.", "",
          "## Predictions", "", "| | Prediction | Verdict | Cells supported / not supported / contradicted |",
          "|---|---|---|---|"]
    for pid, p in res["pred"].items():
        v = list(p["cells"].values())
        L_.append(f"| {pid} | {p['text']} | **{p['verdict']}** | {v.count('supported')} / {v.count('not supported')}"
                  f" / {v.count('contradicted')} |")
    L_ += ["", "Rule (fixed before the run): supported if every cell's interval is on the predicted side of 0; "
           "contradicted if any cell's interval is on the opposite side; otherwise not supported.", ""]
    for study, eid, lab, unit, sign, pid in res["endpoints"]:
        L_ += [f"## {(pid + ': ') if pid else 'PX5 (exploratory): '}{lab}", "", "| Cell | Estimate | Side of 0 |"
               + (" Verdict |" if pid else ""), "|---|---|---|" + ("---|" if pid else "")]
        for c in res["cells"]:
            st = res["est"][eid][c]
            row = f"| {c} | {_ci(st, unit)} | {side(st)} |"
            if pid:
                row += f" {res['pred'][pid]['cells'].get(c, '–')} |"
            L_.append(row)
        L_.append("")
    L_ += ["## Changes against rating_indexed × lex (PX5 flags)", ""]
    if res["changes"]:
        L_ += ["| Endpoint | Cell | Sign change | Side of 0: base → cell |", "|---|---|---|---|"]
        L_ += [f"| {x['endpoint']} | {x['cell']} | {'yes' if x['sign_change'] else 'no'} | {x['base_side']} → "
               f"{x['side']} |" for x in res["changes"]]
    else:
        L_.append("None.")
    L_ += ["", "## Checks", "",
           f"- Reproduction of the saved stars chains by rating_indexed × lex: {rep['matched']} of {rep['compared']} "
           f"match ({rep['missing']} without a saved chain); {'pass' if rep['pass'] else 'FAIL'}.",
           f"- Guard (stuck, parked, invalid actions) summed over {sum(g['chains'] for g in guard.values())} chains: "
           f"{sum(g['stuck_buyers'] for g in guard.values())}, {sum(g['parked'] for g in guard.values())}, "
           f"{sum(g['fallbacks'] for g in guard.values())}.",
           f"- Flags: {len(flags)}." + ("" if not flags else " " + "; ".join(flags[:20])), "",
           "![Headline estimates by cell](robustness_1_1.svg)", ""]
    return "\n".join(L_)


# ------------------------------------------------------------------ main

def _git_commit() -> tuple[str, bool]:
    c = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    d = subprocess.run(["git", "status", "--porcelain", "--", "engine", "agents", "analysis"], capture_output=True,
                       text=True).stdout.strip()
    return c, bool(d)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policies", default=",".join(POLICIES))
    ap.add_argument("--choices", default=",".join(CHOICES))
    ap.add_argument("--studies", default=",".join(STUDIES))
    ap.add_argument("--seeds-per-study", type=int, default=10)
    ap.add_argument("--seeds", default=None, help="the same seeds for every study (smoke: 900)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--outdir", default=OUT)
    ap.add_argument("--tests", default="")
    ap.add_argument("--timing", action="store_true", help="time 2 chains per study in 3 cells; project the run")
    ap.add_argument("--min-swap-mb", type=float, default=512)
    ap.add_argument("--min-free-pct", type=float, default=15)
    a = ap.parse_args(argv)
    pols = [p for p in a.policies.split(",") if p]
    chs = [c for c in a.choices.split(",") if c]
    studies = [s for s in a.studies.split(",") if s]
    if any(p not in POLICIES for p in pols) or any(c not in CHOICES for c in chs) or \
            any(s not in STUDIES for s in studies):
        raise SystemExit("unknown policy, choice or study")
    cells = [(p, c) for p in POLICIES if p in pols for c in CHOICES if c in chs]
    if a.seeds and os.path.abspath(a.outdir) == os.path.abspath(OUT) and not a.timing:
        raise SystemExit("--seeds is for a smoke run: use an --outdir other than runs")
    LB._lower_priority()
    os.makedirs(a.outdir, exist_ok=True)
    log = CR.file_logger(os.path.join(a.outdir, "robustness_1_1_run.log"))
    commit, dirty = _git_commit()
    meta = {"engine_version": ENGINE_VERSION, "commit": commit, "code_dirty": dirty, "script_sha256": _script_sha(),
            "command": " ".join(["python -m analysis.robustness_1_1", *sys.argv[1:]]), "tests": a.tests,
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
            "workers": a.workers, "load_start": _load(), "mem_start": memory_state(),
            "cells": [cell_name(c) for c in cells], "market_defaults": MARKET_DEFAULTS,
            "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    log(f"run record {json.dumps(meta, sort_keys=True)}")
    if dirty and not a.timing and not a.seeds:
        raise SystemExit("engine, agents or analysis has uncommitted changes: commit before a main run")
    given = ([int(a.seeds)] if a.seeds and a.seeds.strip().isdigit() else parse_seeds(a.seeds)) if a.seeds else None
    seeds = {st: (given if given else ORIG_SEEDS[st][:a.seeds_per_study]) for st in studies}
    _smp: dict = {}

    def samples_for(sds):
        for sd in sds:
            if sd not in _smp:
                _smp[sd] = V.sample_stalls(sd)
        return {sd: _smp[sd] for sd in sds}

    if a.timing:
        tcells = [BASE_CELL, ("undercut", "soft"), ("match_rival", "sharp")]
        jobs = []
        for st in studies:
            sd = seeds[st][:1]
            sp = specs(st, sd, samples_for(sd))
            pick = sorted({int(round(x)) for x in np.linspace(0, len(sp) - 1, 2)})
            jobs += [(st, c, sp[i]) for c in tcells for i in pick]
        recs, _ = CR.run_chains(a, jobs, None, log, job, key)
        tot = 0.0
        per_cell = {}
        for st in studies:
            rs = [r for r in recs if r["study"] == st]
            sec = float(np.mean([r["secs"] for r in rs]))
            n = len(specs(st, seeds[st], samples_for(seeds[st])))
            per_cell[st] = n * sec / a.workers / 3600
            tot += per_cell[st]
            bad = [r["key"] for r in rs if not r["arm_ok"] or any(r["guard"][k] for k in
                                                                    ("stuck_buyers", "parked", "fallbacks"))]
            log(f"timing {st}: {len(rs)} chains, {sec:.1f} s per chain (by cell: "
                f"{ {cell_name(c): round(float(np.mean([r['secs'] for r in rs if r['cell'] == cell_name(c)])), 1) for c in tcells} }), "
                f"{n} chains per cell, {per_cell[st]:.2f} h per cell at {a.workers} workers"
                + (f"; FLAGGED {bad}" if bad else ""))
        proj = {"per_cell_h": tot, "cells": len(cells), "total_h": tot * len(cells)}
        for k in range(len(TRIM_ORDER) + 1):
            drop = TRIM_ORDER[:k]
            n = sum(1 for p, c in [(p, c) for p in POLICIES for c in CHOICES] if p not in drop and c not in drop)
            proj[f"after dropping {', '.join(drop) or 'nothing'}"] = {"cells": n, "hours": round(tot * n, 2)}
        log(f"timing: {json.dumps(proj)}; load {_load()}")
        with open(os.path.join(a.outdir, "robustness_1_1_timing.json"), "w", encoding="utf-8") as f:
            json.dump({"meta": meta, "projection": proj, "chains": [{k: r[k] for k in ("key", "secs", "arm_ok",
                                                                                       "guard", "seen")} for r in recs]},
                      f, indent=1)
        return 0

    t0 = time.time()
    cache = os.path.join(a.outdir, "robustness_1_1_cache.jsonl")
    jobs = []
    for st in studies:          # the base cell first, so its reproduction check can be read early
        sm = samples_for(seeds[st])
        jobs += [(st, c, x) for c in cells for x in specs(st, seeds[st], sm)]
    jobs.sort(key=lambda j: j[1] != BASE_CELL)          # stable: study order kept within each group
    recs, pauses = CR.run_chains(a, jobs, cache, log, job, key)
    want = {key(j) for j in jobs}
    recs = [r for r in recs if r["key"] in want]
    per, fl_ep = {}, []
    for c in cells:
        cn = cell_name(c)
        per[cn] = {}
        for st in studies:
            idx = {r["skey"]: r["rec"] for r in recs if r["study"] == st and r["cell"] == cn}
            ep, fl = endpoints(st, idx, seeds[st], samples_for(seeds[st]))
            per[cn].update(ep)
            fl_ep += [f"{cn}: {x}" for x in fl]
    res = analyse(per, cells, [e for e in ENDPOINTS if e[0] in studies])
    rep = repro_check([r for r in recs if r["cell"] == cell_name(BASE_CELL)]) if BASE_CELL in cells else \
        {"compared": 0, "matched": 0, "missing": 0, "bad": [], "pass": False}
    guard, flags = checks(recs, fl_ep)
    if not rep["pass"] and not a.seeds:
        flags.append(f"reproduction of saved stars chains: {rep['matched']} of {rep['compared']} match")
    meta.update(chains=len(recs), pauses=pauses, wall_h=(time.time() - t0) / 3600, load_end=_load(),
                mem_end=memory_state(), seeds_txt=", ".join(f"{k} {v[0]}-{v[-1]}" for k, v in seeds.items()))
    with gzip.open(os.path.join(a.outdir, "robustness_1_1.json.gz"), "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": res, "guard": guard, "flags": flags, "repro": rep,
                   "samples": {str(k): v for k, v in _smp.items()}}, f, indent=1, default=str)
    with open(os.path.join(a.outdir, "robustness_1_1.svg"), "w", encoding="utf-8") as f:
        f.write(plot_svg(res))
    with open(os.path.join(a.outdir, "robustness_1_1_summary.md"), "w", encoding="utf-8") as f:
        f.write(report(res, meta, guard, flags, rep))
    for pid, p in res["pred"].items():
        log(f"{pid}: {p['verdict']} ({p['cells']})")
    log(f"done; {len(flags)} flags; wall {meta['wall_h']:.2f} h; load {_load()}")
    for x in flags:
        log(f"FLAG: {x}")
    return 2 if flags else 0


if __name__ == "__main__":
    raise SystemExit(main())
