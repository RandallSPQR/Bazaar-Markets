"""Brands, look-alikes and bust-out (rule-based only).

Prespecified design (2026-11-06; see runs/brand_summary.md).
  Ratings public; 2 patrolling inspectors, not uniformed; naive deceptive sellers (rule_deceptive);
  D = 30 days, known to sellers; imitation off; brands on with premium pi = 0.4 (placeholder).
  Seeds 0-29, paired. Factorial (18 conditions):
    reopen strategy in {keep, fresh, lookalike}
    x tourist share in {0.2, 0.4, 0.6} (locals and experts split the rest evenly)
    x genuine policy in {rule_genuine (= rule_honest, always honest), rule_genuine_rational}

    .venv/bin/python -m analysis.brands --ref070 runs/brand_day1_v070.json --out runs/brand.json
    .venv/bin/python -m analysis.brands --budget above --ref070 runs/brand_day1_v070_budget125.json \
        --out runs/brand_budget125.json

Budget: the prespecified, confirmatory run uses the default buyers.budget_level ("at": budget =
units x base price). The smoke test (2 seeds, 2026-11-06) showed that premium prices above base
then price out buyers rather than earn a margin, so a second run with budget_level "above"
(1.25 x base, enough for every price up to 1.2 x base) was added as exploratory (decided
2026-11-06, before either full run).

Gate: (a) calibration: rule_genuine_rational, fresh, tourist share 0.4: median bust-out day over
all genuine stalls and seeds (never = D + 1) >= 25; (b) every day-1 outcome (minus the 0.8.0
"brands" block) equals the 0.7.0 engine's single-day outcome for the same condition (from
--ref070, made with --make-ref070 in a 0.7.0 worktree). If the gate fails, only the gate is
reported.

Late = mean over days 26-30. Paired by seed; 95% t-intervals, unadjusted.
  PE1 (confirmatory): late profit per deceptive stall, lookalike - fresh (tourist 0.4, rule_genuine) > 0.
  PE2 (confirmatory): per-seed OLS slope of the PE1 gap over tourist shares 0.2, 0.4, 0.6 > 0.
  PE3 (confirmatory): late rating of brands copied at least once (in the lookalike chain),
      lookalike - fresh, same names and seed (tourist 0.4, rule_genuine) < 0.
  PE4 (confirmatory): rule_genuine_rational, tourist 0.4: per-seed mean bust-out day over genuine
      stalls (never = 31), lookalike - fresh < 0. Also the share that bust out.
  Exploratory: the same at the other tourist shares; keep against fresh and lookalike; shortfall
  and buyer surplus by condition; rating and premium trajectories; bust-outs on copied brands.

This script only reads engine outputs; it changes nothing in the engine.
"""
from __future__ import annotations

import argparse
import csv
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
from engine.jsonlog import dumps
from engine.metrics import mean_ci, paired_diff

DAYS = 30
LATE = list(range(26, 31))
STRATS = ["keep", "fresh", "lookalike"]
TOURIST = {"t20": 0.2, "t40": 0.4, "t60": 0.6}
SHARES = {"t20": '{"tourist":0.2,"local":0.4,"expert":0.4}',
          "t40": '{"tourist":0.4,"local":0.3,"expert":0.3}',
          "t60": '{"tourist":0.6,"local":0.2,"expert":0.2}'}
GEN = {"honest": "rule_honest", "rational": "rule_genuine_rational"}
CONDS = [(s, t, g) for g in GEN for t in TOURIST for s in STRATS]
SERIES = ["deceptive_profit", "genuine_profit", "seconds_profit", "shortfall_rate", "surplus", "task_complete",
          "catches", "renames", "lookalike_stalls", "busted", "genuine_premium", "deceptive_premium",
          "rating_genuine", "rating_deceptive_current"]
LABEL = {"keep": "keep name", "fresh": "fresh name", "lookalike": "look-alike", "t20": "tourists 20%",
         "t40": "tourists 40%", "t60": "tourists 60%", "honest": "rule_genuine", "rational": "rule_genuine_rational"}
COMMON = ["ratings.mode=public", "inspectors.count=2", "inspectors.placement=patrolling", "inspectors.uniformed=false",
          "agents.seller.deceptive=rule_deceptive"]


def cname(s, t, g) -> str:
    return f"{s}|{t}|{g}"


def _overrides(s, t, g, seed, budget="at") -> list[str]:
    return [*COMMON, f"buyers.budget_level={budget}", "brands.enabled=true", "brands.premium=0.4", f"market.days={DAYS}", "market.horizon_known=true",
            "evolution.revise_prob=0", "evolution.mutation_prob=0", f"agents.params.rule_deceptive.reopen={s}",
            f"buyers.profile_shares={SHARES[t]}", f"agents.seller.genuine={GEN[g]}", f"seed={seed}"]


def _ref_overrides(t, seed, budget="at") -> list[str]:
    """The same condition for the 0.7.0 engine: single day, none of the 0.8.0 switches."""
    return [*COMMON, f"buyers.budget_level={budget}", f"buyers.profile_shares={SHARES[t]}", "agents.seller.genuine=rule_honest", f"seed={seed}"]


def _sha(o: dict) -> str:
    return hashlib.sha256(dumps(o).encode()).hexdigest()


def _per_stall(pt, k):
    return pt[k]["profit_per_stall_cents"] if k in pt else None


def _job(args) -> dict:
    s, t, g, seed, budget = args
    c = load(None, _overrides(s, t, g, seed, budget), mode="bazaar")
    out = bazaar.run(c)
    d1 = out["days"][0]
    stype = d1["stall_types"]
    # day-1 names = names at the start of day 1 (before any rename)
    first = {}
    for d in out["days"]:
        for r in d["renames"]:
            first.setdefault(r["stall"], r["from"])
    orig_name = {sid: first.get(sid, out["days"][0]["brands"][sid]) for sid in stype}
    base = c.pricing.base_price_cents
    tier = {"genuine": 1.0, "deceptive": c.pricing.deceptive_price_factor, "seconds": c.pricing.seconds_price_factor}
    cat = {st.sid: st.category for st in bazaar.BazaarEngine(c).stalls}
    orig = {n: [] for n in orig_name.values()}
    copied: dict = {}
    bust = {sid: None for sid, ty in stype.items() if ty == "genuine"}
    days = []
    for d in out["days"]:
        o = d["outcome"]
        pt = o["seller_by_type"]
        for r in d["renames"]:
            if r["lookalike_of"] is not None:
                copied.setdefault(r["lookalike_of"], d["day"])
        for b in d["bust_outs"]:
            bust[b["stall"]] = b["day"]
        for n in orig:
            v = d["brand_ratings"].get(n)
            orig[n].append(None if v is None else round(v, 4))
        prem = {ty: [d["prices"][sid] / (base[cat[sid]] * tier[ty]) - 1 for sid, t_ in stype.items() if t_ == ty]
                for ty in ("genuine", "deceptive")}
        rg = [d["brand_ratings"].get(orig_name[sid]) for sid, ty in stype.items() if ty == "genuine"]
        rd = [d["ratings"].get(sid) for sid, ty in stype.items() if ty == "deceptive"]
        rg = [x for x in rg if x is not None]
        rd = [x for x in rd if x is not None]
        days.append({"deceptive_profit": _per_stall(pt, "deceptive"), "genuine_profit": _per_stall(pt, "genuine"),
                     "seconds_profit": _per_stall(pt, "seconds"), "shortfall_rate": o["shortfall_rate"],
                     "surplus": o["buyer_surplus_mean_cents"], "task_complete": o["task_complete_share"],
                     "catches": o["catches"], "renames": o["brands"]["renames"],
                     "lookalike_stalls": o["brands"]["lookalike_stalls"], "busted": o["brands"]["busted_stalls"],
                     "genuine_premium": float(np.mean(prem["genuine"])), "deceptive_premium": float(np.mean(prem["deceptive"])),
                     "rating_genuine": float(np.mean(rg)) if rg else None,
                     "rating_deceptive_current": float(np.mean(rd)) if rd else None})
    o1 = dict(d1["outcome"])
    o1.pop("brands", None)
    return {"cond": cname(s, t, g), "seed": seed, "days": days, "orig": orig,
            "orig_type": {orig_name[sid]: ty for sid, ty in stype.items()},
            "genuine_names": {sid: orig_name[sid] for sid in bust}, "copied": copied, "bust": bust,
            "day1_sha": _sha(o1)}


def _ref_job(args) -> dict:
    t, seed, budget = args
    return {"key": f"{t}|{seed}", "sha": _sha(bazaar.run(load(None, _ref_overrides(t, seed, budget), mode="bazaar")))}


def _git() -> dict:
    def g(*a):
        return subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
    return {"commit": g("rev-parse", "HEAD"), "status_porcelain": g("status", "--porcelain").splitlines()}


def _load() -> list[float]:
    return [round(x, 2) for x in os.getloadavg()]


# ------------------------------------------------------------------ analysis

def _arr(v, cond, m) -> np.ndarray:
    return np.array([[np.nan if x[m] is None else x[m] for x in r["days"]] for r in v[cond]], float)


def _late(a) -> np.ndarray:
    with np.errstate(all="ignore"):
        return np.nanmean(a[:, [d - 1 for d in LATE]], 1)


def _lst(a) -> list:
    return [None if np.isnan(x) else float(x) for x in a]


def _verdict(st, sign=+1):
    if st["lo"] is None:
        return "not testable"
    if (sign > 0 and st["lo"] > 0) or (sign < 0 and st["hi"] < 0):
        return "supported"
    if (sign > 0 and st["hi"] < 0) or (sign < 0 and st["lo"] > 0):
        return "contradicted (interval on the opposite side of 0)"
    return "not supported (interval includes 0)"


def _late_rating(series) -> float | None:
    xs = [x for x in series[LATE[0] - 1:LATE[-1]] if x is not None]
    return float(np.mean(xs)) if xs else None


def _copied_rating(v, t, g, arm, days=None):
    """Per seed: mean over names copied at least once in the lookalike chain (same t, g, seed)
    of that name's rating in `arm` (late mean, or per day if days is given)."""
    out = []
    for rl, ra in zip(v[cname("lookalike", t, g)], v[cname(arm, t, g)]):
        names = [n for n in rl["copied"] if n in ra["orig"]]
        if days is None:
            vals = [_late_rating(ra["orig"][n]) for n in names]
            vals = [x for x in vals if x is not None]
            out.append(float(np.mean(vals)) if vals else None)
        else:
            row = []
            for d in range(days):
                xs = [ra["orig"][n][d] for n in names if ra["orig"][n][d] is not None]
                row.append(float(np.mean(xs)) if xs else None)
            out.append(row)
    return out


def _copied_pairs(v, t, g):
    """Per seed: (fresh, lookalike) late ratings of the copied names, over names rated in both."""
    a, b = [], []
    for rl, rf in zip(v[cname("lookalike", t, g)], v[cname("fresh", t, g)]):
        xs, ys = [], []
        for n in rl["copied"]:
            x, y = _late_rating(rf["orig"].get(n, [])), _late_rating(rl["orig"].get(n, []))
            if x is not None and y is not None:
                xs.append(x)
                ys.append(y)
        a.append(float(np.mean(xs)) if xs else None)
        b.append(float(np.mean(ys)) if ys else None)
    return a, b


def _bust_days(r) -> list[int]:
    return [DAYS + 1 if b is None else b for b in r["bust"].values()]


def _mean_bust(v, cond):
    return [float(np.mean(_bust_days(r))) for r in v[cond]]


def _share_bust(v, cond):
    return [float(np.mean([b is not None for b in r["bust"].values()])) for r in v[cond]]


def analyse(v: dict) -> dict:
    res: dict = {"trajectory": {}, "late": {}}
    for cond in v:
        for m in SERIES:
            a = _arr(v, cond, m)
            res["trajectory"][f"{cond}|{m}"] = [mean_ci(_lst(a[:, j])) for j in range(DAYS)]
            res["late"][f"{cond}|{m}"] = mean_ci(_lst(_late(a)))
    L = {(cond, m): _late(_arr(v, cond, m)) for cond in v for m in SERIES}

    # PE1 / PE2: deceptive profit gap
    gap = {}
    for g in GEN:
        for t in TOURIST:
            gap[(t, g)] = L[(cname("lookalike", t, g), "deceptive_profit")] - L[(cname("fresh", t, g), "deceptive_profit")]
    res["profit_gap"] = {f"{t}|{g}": mean_ci(_lst(gap[(t, g)])) for t in TOURIST for g in GEN}
    pe1 = res["profit_gap"]["t40|honest"]
    res["pe1"] = {**pe1, "verdict": _verdict(pe1, +1)}
    x = np.array([TOURIST[t] for t in TOURIST])
    xc = x - x.mean()
    slope = {}
    for g in GEN:
        G = np.stack([gap[(t, g)] for t in TOURIST], 1)          # seeds x 3
        sl = (G * xc).sum(1) / (xc ** 2).sum() * 0.2              # per +0.2 of tourist share
        slope[g] = mean_ci(_lst(sl))
    res["pe2"] = {**slope["honest"], "verdict": _verdict(slope["honest"], +1), "unit": "cents per +0.2 tourist share"}
    res["pe2_rational"] = slope["rational"]

    # PE3: copied brands' ratings
    pe3 = {}
    for g in GEN:
        for t in TOURIST:
            a, b = _copied_pairs(v, t, g)
            pe3[f"{t}|{g}"] = {"diff": paired_diff(a, b), "fresh": mean_ci(a), "lookalike": mean_ci(b),
                               "n_copied": mean_ci([len(r["copied"]) for r in v[cname("lookalike", t, g)]])}
    res["pe3_all"] = pe3
    res["pe3"] = {**pe3["t40|honest"]["diff"], "verdict": _verdict(pe3["t40|honest"]["diff"], -1)}
    # genuine-only copied brands (exploratory)
    gen_only = {}
    for g in GEN:
        for t in TOURIST:
            a, b = [], []
            for rl, rf in zip(v[cname("lookalike", t, g)], v[cname("fresh", t, g)]):
                xs, ys = [], []
                for n in rl["copied"]:
                    if rl["orig_type"].get(n) != "genuine":
                        continue
                    x_, y_ = _late_rating(rf["orig"][n]), _late_rating(rl["orig"][n])
                    if x_ is not None and y_ is not None:
                        xs.append(x_)
                        ys.append(y_)
                a.append(float(np.mean(xs)) if xs else None)
                b.append(float(np.mean(ys)) if ys else None)
            gen_only[f"{t}|{g}"] = paired_diff(a, b)
    res["pe3_genuine_only"] = gen_only
    res["copied_types"] = {f"{t}|{g}": {ty: int(sum(r["orig_type"][n] == ty for r in v[cname("lookalike", t, g)]
                                                  for n in r["copied"])) for ty in ("genuine", "deceptive")}
                           for t in TOURIST for g in GEN}
    res["copied_rating_trajectory"] = {}
    for g in GEN:
        for t in TOURIST:
            for arm in ("fresh", "lookalike"):
                rows = _copied_rating(v, t, g, arm, days=DAYS)
                res["copied_rating_trajectory"][f"{t}|{g}|{arm}"] = [mean_ci([r[d] for r in rows]) for d in range(DAYS)]

    # PE4: bust-out timing
    pe4 = {}
    for t in TOURIST:
        for s in STRATS:
            cond = cname(s, t, "rational")
            days_all = [b for r in v[cond] for b in _bust_days(r)]
            pe4[f"{t}|{s}"] = {"mean_day": mean_ci(_mean_bust(v, cond)), "share_bust": mean_ci(_share_bust(v, cond)),
                               "median_day_pooled": float(np.median(days_all)),
                               "hist": [int(sum(1 for b in days_all if b == d)) for d in range(1, DAYS + 2)]}
        pe4[f"{t}|look-fresh"] = paired_diff(_mean_bust(v, cname("fresh", t, "rational")),
                                             _mean_bust(v, cname("lookalike", t, "rational")))
        pe4[f"{t}|share look-fresh"] = paired_diff(_share_bust(v, cname("fresh", t, "rational")),
                                                   _share_bust(v, cname("lookalike", t, "rational")))
        pe4[f"{t}|keep-fresh"] = paired_diff(_mean_bust(v, cname("fresh", t, "rational")),
                                             _mean_bust(v, cname("keep", t, "rational")))
    res["pe4_all"] = pe4
    res["pe4"] = {**pe4["t40|look-fresh"], "verdict": _verdict(pe4["t40|look-fresh"], -1)}

    # Bust-outs on copied brands (exploratory): per seed, mean bust day of genuine stalls whose
    # name was copied on or before their bust-out day (any day if they never busted) minus the rest
    clus = {}
    for t in TOURIST:
        diffs, nc, nn = [], 0, 0
        for r in v[cname("lookalike", t, "rational")]:
            cp, rest = [], []
            for sid, b in r["bust"].items():
                n = r["genuine_names"][sid]
                cday = r["copied"].get(n)
                bd = DAYS + 1 if b is None else b
                (cp if cday is not None and cday <= bd else rest).append(bd)
            nc += len(cp)
            nn += len(rest)
            if cp and rest:
                diffs.append(float(np.mean(cp) - np.mean(rest)))
        clus[t] = {"copied_minus_not": mean_ci(diffs), "n_copied_stalls": nc, "n_other_stalls": nn,
                   "seeds_with_both": len(diffs)}
    res["bust_on_copied"] = clus

    # keep vs others (exploratory), shortfall and surplus contrasts
    ex = {}
    for g in GEN:
        for t in TOURIST:
            for m in ("deceptive_profit", "shortfall_rate", "surplus", "genuine_profit"):
                for a_, b_ in (("keep", "fresh"), ("keep", "lookalike"), ("fresh", "lookalike")):
                    ex[f"{t}|{g}|{m}|{b_}-{a_}"] = paired_diff(_lst(L[(cname(a_, t, g), m)]), _lst(L[(cname(b_, t, g), m)]))
            for s in STRATS:
                for m in ("shortfall_rate", "surplus", "deceptive_profit", "genuine_profit"):
                    ex[f"{t}|{s}|{m}|rational-honest"] = paired_diff(_lst(L[(cname(s, t, "honest"), m)]),
                                                                     _lst(L[(cname(s, t, "rational"), m)]))
    res["contrasts"] = ex

    # floors and ceilings
    flags = []
    for cond in v:
        for m in ("shortfall_rate", "rating_genuine", "rating_deceptive_current", "task_complete"):
            st = res["late"][f"{cond}|{m}"]
            if st["mean"] is not None and (st["mean"] <= 0.01 or st["mean"] >= 0.99):
                flags.append(f"{cond} {m}: late mean {st['mean']:.3f}")
        if cond.endswith("rational"):
            sh = mean_ci(_share_bust(v, cond))["mean"]
            if sh <= 0.01 or sh >= 0.99:
                flags.append(f"{cond} share of genuine stalls that bust out: {sh:.3f}")
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
         f".lb{{font-family:{SERIF};font-size:12px}} .ax{{stroke:#ccc;stroke-width:1}} "
         ".of{stroke:#666;stroke-width:1.6;fill:none} .ofb{fill:#666;fill-opacity:.12} .oft{fill:#666} "
         ".on{stroke:#e15759;stroke-width:1.6;fill:none} .onb{fill:#e15759;fill-opacity:.14} .ont{fill:#e15759} "
         ".bar{fill:#7a7a7a} .bar31{fill:#bbb} .med{stroke:#e15759;stroke-width:1.4} .medt{fill:#e15759} "
         f".an{{font-family:{SERIF};font-style:italic;font-size:11.5px;fill:#333}} "
         "@media (prefers-color-scheme: dark){.bg{fill:#151515} .t{fill:#ddd} .s{fill:#999} .k{fill:#888} .n{fill:#666} "
         ".ax{stroke:#444} .of{stroke:#aaa} .ofb{fill:#aaa} .oft{fill:#aaa} .on{stroke:#fc8d62} .onb{fill:#fc8d62} "
         ".ont{fill:#fc8d62} .bar{fill:#999} .bar31{fill:#555} .med{stroke:#fc8d62} .medt{fill:#fc8d62} .an{fill:#bbb}}</style>")


def plot_ratings_svg(res: dict, n_seeds: int, version: str = ENGINE_VERSION) -> str:
    """Small multiples: rating of copied original brands over days, fresh vs look-alike, one panel
    per tourist share (rule_genuine)."""
    W, H = 1060, 580
    left, top, pw, ph, gx = 80, 150, 255, 250, 45
    pe3 = res["pe3"]
    title = "Brands copied by look-alikes lose rating as tourists misfile reviews"
    sub = (f"Late rating of copied brands, look-alike − fresh (tourists 40%): {_num(3)(pe3['mean'], True)} "
           f"[{_num(3)(pe3['lo'], True)}, {_num(3)(pe3['hi'], True)}]")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" aria-labelledby="t d">',
           STYLE, f'<rect class="bg" x="0" y="0" width="{W}" height="{H}"/>',
           f'<title id="t">{title}</title>',
           f'<desc id="d">Three panels by tourist share; per-day mean rating of the brands copied at least once in the '
           f'look-alike chain, in that chain and in the fresh-name chain with the same seed; 95% bands over {n_seeds} '
           f'paired seeds. The summary gives every value.</desc>',
           f'<text class="t" x="{left - 60}" y="40" font-size="20">{title}</text>',
           f'<text class="s" x="{left - 60}" y="64" font-size="14">{sub}</text>']
    tr = res["copied_rating_trajectory"]
    vals = [x for t in TOURIST for arm in ("fresh", "lookalike") for st in tr[f"{t}|honest|{arm}"]
            for x in (st["lo"], st["hi"]) if x is not None]
    lo, hi = min(vals), max(vals)
    pad = 0.04 * (hi - lo)
    lo, hi = lo - pad, hi + pad
    days = np.arange(1, DAYS + 1)
    out.append(f'<text class="s" x="{left - 60}" y="{top - 52}" font-size="14">Rating of copied brands (0–1; '
               f'price premium = 0.4 × (rating − 0.5))</text>')
    for ci, t in enumerate(TOURIST):
        x0 = left + ci * (pw + gx)

        def X(d):
            return x0 + (d - 1) / (DAYS - 1) * pw

        def Y(val):
            return top + ph - (val - lo) / (hi - lo) * ph
        out.append(f'<text class="t" x="{x0}" y="{top - 20}" font-size="13">{LABEL[t]}</text>')
        out.append(f'<line class="ax" x1="{X(1):.1f}" y1="{top + ph + 6}" x2="{X(DAYS):.1f}" y2="{top + ph + 6}"/>')
        for d in (1, 10, 20, 30):
            out.append(f'<text class="k" x="{X(d):.1f}" y="{top + ph + 20}" text-anchor="middle">{d}</text>')
        if ci == 0:
            tv = [np.ceil((lo + pad) * 10) / 10, np.floor((hi - pad) * 10) / 10]
            # range frame: the spine spans the data (band) range; ticks at tenths inside it
            out.append(f'<line class="ax" x1="{x0 - 6}" y1="{Y(lo + pad):.1f}" x2="{x0 - 6}" y2="{Y(hi - pad):.1f}"/>')
            for v_ in np.arange(tv[0], tv[1] + 1e-9, 0.1):
                out.append(f'<text class="k" x="{x0 - 10}" y="{Y(v_) + 4:.1f}" text-anchor="end">{v_:.1f}</text>')
        ends = {}
        for arm, cls in (("fresh", "of"), ("lookalike", "on")):
            s_ = tr[f"{t}|honest|{arm}"]
            pts = [(d, st) for d, st in zip(days, s_) if st["mean"] is not None]
            bp = [(d, st) for d, st in pts if st["lo"] is not None]
            if bp:
                band = [f"{X(d):.1f},{Y(st['hi']):.1f}" for d, st in bp] + \
                       [f"{X(d):.1f},{Y(st['lo']):.1f}" for d, st in reversed(bp)]
                out.append(f'<polygon class="{cls}b" points="{" ".join(band)}"/>')
            out.append(f'<polyline class="{cls}" points="' + " ".join(f"{X(d):.1f},{Y(st['mean']):.1f}" for d, st in pts) + '"/>')
            ends[arm] = Y(pts[-1][1]["mean"])
        if ci == len(TOURIST) - 1:
            ya, yn = ends["lookalike"], ends["fresh"]
            if abs(ya - yn) < 13:
                ya, yn = (ya - 7, yn + 7) if ya < yn else (ya + 7, yn - 7)
            out.append(f'<text class="lb ont" x="{X(DAYS) + 5:.1f}" y="{ya + 4:.1f}">look-alike</text>')
            out.append(f'<text class="lb oft" x="{X(DAYS) + 5:.1f}" y="{yn + 4:.1f}">fresh name</text>')
    yb = top + ph + 44
    out.append(f'<text class="k" x="{left + 1.5 * pw + gx:.1f}" y="{yb}" text-anchor="middle">day</text>')
    out.append(f'<text class="n" x="{left - 60}" y="{yb + 28}">Bazaar engine {version}; 2 patrolling inspectors, naive '
               f'deceptive sellers, always-honest genuine sellers. Copied = copied at least once in the look-alike chain;</text>')
    out.append(f'<text class="n" x="{left - 60}" y="{yb + 44}">the fresh line is the same names in the fresh-name chain '
               f'with the same seed. Lines: mean over {n_seeds} paired seeds of the per-seed mean end-of-day rating '
               f'(rated brands only);</text>')
    out.append(f'<text class="n" x="{left - 60}" y="{yb + 60}">bands: 95% t-interval per day. Ratings memory 0.7, skip '
               f'threshold 0.5, premium 0.4 (placeholders).</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def plot_bust_svg(res: dict, n_seeds: int, version: str = ENGINE_VERSION) -> str:
    """Small multiples: distribution of bust-out days (rule_genuine_rational), tourist share (rows)
    x reopen strategy (columns). Day 31 = never."""
    W, H = 1000, 790
    left, top, pw, ph, gx, gy = 80, 140, 270, 130, 40, 70
    pe4 = res["pe4"]
    title = "When honest originals bust out, by reopen strategy and tourist share"
    sub = (f"Mean bust-out day, look-alike − fresh (tourists 40%): {_num(2)(pe4['mean'], True)} days "
           f"[{_num(2)(pe4['lo'], True)}, {_num(2)(pe4['hi'], True)}]")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" aria-labelledby="t d">',
           STYLE, f'<rect class="bg" x="0" y="0" width="{W}" height="{H}"/>',
           f'<title id="t">{title}</title>',
           f'<desc id="d">Nine histograms of bust-out day over all genuine stalls and {n_seeds} seeds; the last bar is '
           f'stalls that never bust out; the vertical line is the median. The summary gives every value.</desc>',
           f'<text class="t" x="{left - 60}" y="40" font-size="20">{title}</text>',
           f'<text class="s" x="{left - 60}" y="64" font-size="14">{sub}</text>']
    a = res["pe4_all"]
    ymax = max(max(a[f"{t}|{s}"]["hist"]) for t in TOURIST for s in STRATS)
    for ri, t in enumerate(TOURIST):
        y0 = top + ri * (ph + gy)
        for ci, s in enumerate(STRATS):
            x0 = left + ci * (pw + gx)
            bw = pw / (DAYS + 1)
            h = a[f"{t}|{s}"]["hist"]
            if ri == 0:
                out.append(f'<text class="t" x="{x0}" y="{top - 30}" font-size="13">{LABEL[s]}</text>')
            if ci == 0:
                out.append(f'<text class="s" x="{left - 60}" y="{y0 + ph / 2:.1f}" font-size="12" '
                           f'transform="rotate(-90 {left - 60} {y0 + ph / 2:.1f})" text-anchor="middle">{LABEL[t]}</text>')
            for d, n in enumerate(h, start=1):
                bh = n / ymax * ph
                cls = "bar31" if d == DAYS + 1 else "bar"
                out.append(f'<rect class="{cls}" x="{x0 + (d - 1) * bw + 0.5:.1f}" y="{y0 + ph - bh:.1f}" '
                           f'width="{bw - 1:.1f}" height="{bh:.1f}"/>')
            med = a[f"{t}|{s}"]["median_day_pooled"]
            xm = x0 + (med - 0.5) * bw
            out.append(f'<line class="med" x1="{xm:.1f}" y1="{y0 - 18}" x2="{xm:.1f}" y2="{y0 + ph}"/>')
            share = a[f"{t}|{s}"]["share_bust"]["mean"]
            out.append(f'<text class="lb medt" x="{xm - 4:.1f}" y="{y0 - 8}" text-anchor="end">median {med:g}</text>')
            early = sum(h[1:5])
            if s == "lookalike" and early:
                out.append(f'<text class="an" x="{x0 + 5.5 * bw:.1f}" y="{y0 + ph - 40}">{early} on days 2–5, nearly all</text>')
                out.append(f'<text class="an" x="{x0 + 5.5 * bw:.1f}" y="{y0 + ph - 26}">rated ≤ 0.5 the day before</text>')
            out.append(f'<text class="k" x="{x0 + 2}" y="{y0 + 8}">{100 * share:.0f}% bust out</text>')
            out.append(f'<line class="ax" x1="{x0}" y1="{y0 + ph + 3}" x2="{x0 + pw}" y2="{y0 + ph + 3}"/>')
            for d in (1, 10, 20, 30):
                out.append(f'<text class="k" x="{x0 + (d - 0.5) * bw:.1f}" y="{y0 + ph + 16}" text-anchor="middle">{d}</text>')
            out.append(f'<text class="k" x="{x0 + (DAYS + 0.5) * bw:.1f}" y="{y0 + ph + 16}" text-anchor="middle">∞</text>')
    yb = top + 3 * ph + 2 * gy + 40
    out.append(f'<text class="k" x="{left + 1.5 * pw + gx:.1f}" y="{yb}" text-anchor="middle">bust-out day (∞ = never)</text>')
    out.append(f'<text class="n" x="{left - 60}" y="{yb + 26}">Bazaar engine {version}; rule_genuine_rational '
               f'(benchmark): bust out when one day\'s harvest exceeds days left × yesterday\'s units × today\'s premium.</text>')
    out.append(f'<text class="n" x="{left - 60}" y="{yb + 42}">Bars share one count scale (max {ymax} stalls). All genuine '
               f'stalls in {n_seeds} seeds per panel; 2 patrolling inspectors, naive deceptive sellers,</text>')
    out.append(f'<text class="n" x="{left - 60}" y="{yb + 58}">30 days known to sellers, premium 0.4 (placeholder).</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def report(meta, res, gate, svgs) -> str:
    exploratory = meta.get("budget", "at") != "at"
    L = ["# Brands, look-alikes and bust-out" + (" — budgets 1.25 × base (exploratory)" if exploratory else ""), "",
         "Run spec \"brands, look-alikes and bust-out (rule-based only)\", predictions written 2026-11-06 before any run.",
         ""]
    if exploratory:
        L += ["**Exploratory run.** Identical to the prespecified run (`runs/brand_summary.md`) except buyers' budgets: "
              "`buyers.budget_level=above`, 1.25 × base price per unit instead of 1.0 ×. Added 2026-11-06, before either "
              "full run, because the 2-seed smoke test showed that with budgets at base price the reputation premium "
              "(up to 1.2 × base) prices buyers out instead of earning a margin. The PE labels below mark the same "
              "contrasts as the prespecified run, but nothing in this run is confirmatory.", ""]
    else:
        L += ["Prespecified, confirmatory run (buyers' budgets at the default, 1.0 × base price per unit). A companion "
              "exploratory run with budgets at 1.25 × base is in `runs/brand_budget125_summary.md`.", ""]
    L += ["## Run record", "",
          f"- Buyers' budget level: `{meta.get('budget', 'at')}`",
         f"- Engine `{meta['engine_version']}`; commit `{meta['git']['commit']}`; uncommitted at run time: "
         f"{meta['git']['status_porcelain'] or 'none'}",
         f"- Script sha256 `{meta['script_sha256']}`", f"- Command: `{meta['command']}`",
         f"- Day-1 reference: engine 0.7.0 (`{meta.get('ref070_commit')}`), file `{meta.get('ref070')}`",
         f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
         f"- {meta['n_chains']} chains x {DAYS} days on {meta['workers']} workers; wall clock "
         f"{meta['wall_clock_s'] / 60:.1f} min; load average {meta['load_at_start']} at start, {meta['load_at_end']} at end",
         f"- Seeds {meta['seeds'][0]}-{meta['seeds'][-1]}, paired", "",
         "## Design (prespecified)", "",
         "- Ratings public (memory 0.7, skip threshold 0.5; locals and experts see them); 2 patrolling inspectors, not "
         "uniformed; naive deceptive sellers (`rule_deceptive`); 30 days, known to sellers; imitation off; brands on, "
         "premium pi = 0.4 (placeholder).",
         "- Factorial: reopen strategy (keep / fresh / look-alike) x tourist share (0.2 / 0.4 / 0.6; locals and experts "
         "split the rest evenly, so 0.4 is not the default 0.4 / 0.4 / 0.2 mix) x genuine policy (`rule_genuine` = "
         "`rule_honest`, always honest; `rule_genuine_rational`): 18 conditions.",
         "- Decided 2026-11-06 before the run: the rational seller's \"future\" is the premium its name earns (days "
         "left including today x yesterday's units x today's price above the neutral-rating price); day 1 has no "
         "yesterday, so day 2 is the first decision day. Look-alikes copy the highest-rated full-price brand (genuine "
         "or deceptive tier, never a look-alike) on another stall of the category; unrated = 0.5; ties at random. A "
         "busted-out stall keeps claiming its old quality on every channel, with no caution, and keeps its name if "
         "caught.",
         "- Late = mean of days 26–30. Intervals 95% paired t over seeds, unadjusted. "
         + ("Exploratory throughout." if exploratory else "Confirmatory: PE1, PE2, PE3, PE4."),
         "", "## Gate", ""]
    for k, g in gate.items():
        if k != "passed":
            L.append(f"- {g['label']}: **{'passed' if g['passed'] else 'FAILED'}** ({g['detail']})")
    L.append("")
    if res is None:
        return "\n".join(L + ["**Gate failed: results not reported.**", ""])
    dol = _d
    p1, p2, p3, p4 = res["pe1"], res["pe2"], res["pe3"], res["pe4"]
    a4 = res["pe4_all"]
    L += ["## Prespecified contrasts (exploratory in this run)" if exploratory else "## Confirmatory", "",
          f"- **PE1**: late profit per deceptive stall, look-alike − fresh (tourists 40%, rule_genuine): "
          f"${_ci(p1, dol)} per day. Prediction > 0. **Verdict: {p1['verdict']}.**",
          f"- **PE2**: per-seed slope of that gap over tourist share: ${_ci(p2, dol)} per +0.2 of tourist share. "
          f"Prediction > 0. **Verdict: {p2['verdict']}.**",
          f"- **PE3**: late rating of brands copied at least once, look-alike − fresh (same names and seeds; tourists "
          f"40%, rule_genuine): {_ci(p3, _num(3))}. Prediction < 0. **Verdict: {p3['verdict']}.**",
          f"- **PE4**: mean bust-out day of genuine stalls (never = 31), look-alike − fresh (tourists 40%, "
          f"rule_genuine_rational): {_ci(p4, _num(2))} days. Prediction < 0. **Verdict: {p4['verdict']}.** "
          f"Share that bust out: fresh {_ci(a4['t40|fresh']['share_bust'], _pct, False)}%, look-alike "
          f"{_ci(a4['t40|lookalike']['share_bust'], _pct, False)}%; difference "
          f"{_ci(a4['t40|share look-fresh'], _pct)} points.", "",
          "## By tourist share (all exploratory)" if exploratory else
          "## By tourist share (exploratory except the 40% cells above)", "",
          "### Deceptive profit gap and copied-brand ratings", ""]
    L += _t(["Tourists", "Genuine policy", "Deceptive profit/stall/day, look-alike − fresh ($)",
             "Copied brands' late rating: fresh", "look-alike", "look-alike − fresh", "genuine originals only",
             "Brands copied per seed"],
            [[LABEL[t], LABEL[g], _ci(res["profit_gap"][f"{t}|{g}"], dol),
              _ci(res["pe3_all"][f"{t}|{g}"]["fresh"], _num(3), False),
              _ci(res["pe3_all"][f"{t}|{g}"]["lookalike"], _num(3), False),
              _ci(res["pe3_all"][f"{t}|{g}"]["diff"], _num(3)), _ci(res["pe3_genuine_only"][f"{t}|{g}"], _num(3)),
              _ci(res["pe3_all"][f"{t}|{g}"]["n_copied"], _num(1), False)] for g in GEN for t in TOURIST])
    L += ["", f"Slope of the profit gap with rule_genuine_rational: ${_ci(res['pe2_rational'], dol)} per +0.2 of "
          f"tourist share.", "", "Copied originals by type (count over seeds):", ""]
    L += [f"- {LABEL[t]}, {LABEL[g]}: {res['copied_types'][f'{t}|{g}']}" for g in GEN for t in TOURIST]
    L += ["", f"![copied-brand ratings]({svgs[0]})", "", "### Bust-out timing (rule_genuine_rational)", ""]
    L += _t(["Tourists", "Strategy", "Mean bust-out day (never = 31)", "Median (pooled)", "Share bust out (%)"],
            [[LABEL[t], LABEL[s], _ci(a4[f"{t}|{s}"]["mean_day"], _num(2), False), f"{a4[f'{t}|{s}']['median_day_pooled']:g}",
              _ci(a4[f"{t}|{s}"]["share_bust"], _pct, False)] for t in TOURIST for s in STRATS])
    L += ["", "Paired contrasts in mean bust-out day (days):", ""]
    L += _t(["Tourists", "look-alike − fresh", "keep − fresh", "share busting, look-alike − fresh (pts)"],
            [[LABEL[t], _ci(a4[f"{t}|look-fresh"], _num(2)), _ci(a4[f"{t}|keep-fresh"], _num(2)),
              _ci(a4[f"{t}|share look-fresh"], _pct)] for t in TOURIST])
    L += ["", "Do bust-outs cluster on copied brands? Per seed, mean bust-out day of genuine stalls whose name was "
          "copied on or before their bust-out day (any day if they never busted) minus the other genuine stalls "
          "(look-alike chains):", ""]
    L += _t(["Tourists", "Copied − not copied (days)", "Copied stalls", "Other stalls", "Seeds with both"],
            [[LABEL[t], _ci(res["bust_on_copied"][t]["copied_minus_not"], _num(2)), str(res["bust_on_copied"][t]["n_copied_stalls"]),
              str(res["bust_on_copied"][t]["n_other_stalls"]), str(res["bust_on_copied"][t]["seeds_with_both"])]
             for t in TOURIST])
    L += ["", f"![bust-out days]({svgs[1]})", "", "## Keep against fresh and look-alike (exploratory)", ""]
    ex = res["contrasts"]
    L += _t(["Tourists", "Genuine policy", "Deceptive profit: fresh − keep ($)", "look-alike − keep ($)",
             "Shortfall: fresh − keep (pts)", "look-alike − keep (pts)", "look-alike − fresh (pts)"],
            [[LABEL[t], LABEL[g], _ci(ex[f"{t}|{g}|deceptive_profit|fresh-keep"], dol),
              _ci(ex[f"{t}|{g}|deceptive_profit|lookalike-keep"], dol),
              _ci(ex[f"{t}|{g}|shortfall_rate|fresh-keep"], _pct), _ci(ex[f"{t}|{g}|shortfall_rate|lookalike-keep"], _pct),
              _ci(ex[f"{t}|{g}|shortfall_rate|lookalike-fresh"], _pct)] for g in GEN for t in TOURIST])
    L += ["", "Buyer surplus per arrived buyer, late ($), paired contrasts:", ""]
    L += _t(["Tourists", "Genuine policy", "fresh − keep", "look-alike − keep", "look-alike − fresh"],
            [[LABEL[t], LABEL[g], _ci(ex[f"{t}|{g}|surplus|fresh-keep"], dol), _ci(ex[f"{t}|{g}|surplus|lookalike-keep"], dol),
              _ci(ex[f"{t}|{g}|surplus|lookalike-fresh"], dol)] for g in GEN for t in TOURIST])
    L += ["", "Rational − always-honest genuine sellers, late:", ""]
    L += _t(["Tourists", "Strategy", "Shortfall (pts)", "Buyer surplus ($)", "Genuine profit/stall ($)"],
            [[LABEL[t], LABEL[s], _ci(ex[f"{t}|{s}|shortfall_rate|rational-honest"], _pct),
              _ci(ex[f"{t}|{s}|surplus|rational-honest"], dol), _ci(ex[f"{t}|{s}|genuine_profit|rational-honest"], dol)]
             for t in TOURIST for s in STRATS])
    L += ["", "## Late levels (days 26–30)", ""]
    lt = res["late"]

    def g_(c, m, f, signed=False):
        return _ci(lt[f"{c}|{m}"], f, signed)
    L += _t(["Genuine policy", "Tourists", "Strategy", "Deceptive profit ($)", "Genuine profit ($)", "Shortfall (%)",
             "Buyer surplus ($)", "Genuine premium (%)", "Deceptive premium (%)", "Rating, genuine originals",
             "Rating, deceptive (current name)", "Catches/day", "Renames/day", "Look-alike stalls", "Busted stalls"],
            [[LABEL[g], LABEL[t], LABEL[s], g_(cname(s, t, g), "deceptive_profit", dol), g_(cname(s, t, g), "genuine_profit", dol),
              g_(cname(s, t, g), "shortfall_rate", _pct), g_(cname(s, t, g), "surplus", dol),
              g_(cname(s, t, g), "genuine_premium", _pct), g_(cname(s, t, g), "deceptive_premium", _pct),
              g_(cname(s, t, g), "rating_genuine", _num(3)), g_(cname(s, t, g), "rating_deceptive_current", _num(3)),
              g_(cname(s, t, g), "catches", _num(1)), g_(cname(s, t, g), "renames", _num(2)),
              g_(cname(s, t, g), "lookalike_stalls", _num(1)), g_(cname(s, t, g), "busted", _num(1))]
             for s, t, g in CONDS])
    L += ["", "## Day 1 levels", ""]
    tr = res["trajectory"]
    L += _t(["Genuine policy", "Tourists", "Strategy", "Deceptive profit ($)", "Shortfall (%)", "Catches", "Renames"],
            [[LABEL[g], LABEL[t], LABEL[s], _ci(tr[f"{cname(s, t, g)}|deceptive_profit"][0], dol, False),
              _ci(tr[f"{cname(s, t, g)}|shortfall_rate"][0], _pct, False), _ci(tr[f"{cname(s, t, g)}|catches"][0], _num(1), False),
              _ci(tr[f"{cname(s, t, g)}|renames"][0], _num(2), False)] for s, t, g in CONDS])
    L += ["", "## Floors and ceilings", ""] + ([f"- {x}" for x in res["flags"]] or ["- none"])
    L += ["", "## Verdicts", "", "VERDICTS_PLACEHOLDER", "", "## Reading (written after the results)", "",
          "READING_PLACEHOLDER", "", "## Caveats", "", "CAVEATS_PLACEHOLDER", ""]
    return "\n".join(L)


def _write_plots(base, res, n, version):
    names = [base + "_copied_ratings.svg", base + "_bust_days.svg"]
    with open(names[0], "w", encoding="utf-8") as f:
        f.write(plot_ratings_svg(res, n, version))
    with open(names[1], "w", encoding="utf-8") as f:
        f.write(plot_bust_svg(res, n, version))
    return [os.path.basename(x) for x in names]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0-29")
    ap.add_argument("--out", default="runs/brand.json")
    ap.add_argument("--ref070", default="runs/brand_day1_v070.json")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--budget", default="at", choices=["at", "above"],
                    help="buyers.budget_level: at (prespecified) or above (exploratory, 1.25 x base)")
    ap.add_argument("--make-ref070", action="store_true",
                    help="write day-1 reference outcomes to --ref070 (run with a 0.7.0 engine on PYTHONPATH)")
    ap.add_argument("--replot", action="store_true", help="redraw the SVGs from --out, without running anything")
    a = ap.parse_args(argv)
    seeds = parse_seeds(a.seeds)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    if a.make_ref070:
        jobs = [(t, s, a.budget) for t in TOURIST for s in seeds]
        with ProcessPoolExecutor(a.workers) as ex:
            got = {r["key"]: r["sha"] for r in ex.map(_ref_job, jobs)}
        with open(a.ref070, "w", encoding="utf-8") as f:
            json.dump({"engine_version": ENGINE_VERSION, "git": _git(), "budget": a.budget, "numpy": np.__version__,
                       "platform": platform.platform(), "day1_sha": got}, f, indent=1, sort_keys=True)
        print(f"engine {ENGINE_VERSION}: wrote {len(got)} reference outcomes to {a.ref070}")
        return 0
    if a.replot:
        with open(a.out, encoding="utf-8") as f:
            d = json.load(f)
        print(_write_plots(a.out[:-5], d["results"], len(d["meta"]["seeds"]), d["meta"]["engine_version"]))
        return 0
    with open(a.ref070, encoding="utf-8") as f:
        ref = json.load(f)
    if ref.get("budget", "at") != a.budget:
        raise SystemExit(f"--ref070 was made with budget {ref.get('budget', 'at')!r}, not {a.budget!r}")
    with open(__file__, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": sha,
            "command": " ".join([".venv/bin/python -m analysis.brands", *(argv or sys.argv[1:])]),
            "ref070": a.ref070, "ref070_commit": ref["git"]["commit"], "ref070_engine": ref["engine_version"],
            "load_at_start": _load(), "python": platform.python_version(), "numpy": np.__version__,
            "platform": platform.platform(), "workers": a.workers, "seeds": seeds, "days": DAYS, "budget": a.budget}
    jobs = [(s, t, g, sd, a.budget) for sd in seeds for s, t, g in CONDS]
    t0 = time.time()
    runs = []
    with ProcessPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(_job, jobs)):
            runs.append(r)
            if (i + 1) % 18 == 0:
                print(f"{i + 1}/{len(jobs)} chains, {time.time() - t0:.0f} s, load {_load()}", flush=True)
    meta.update(wall_clock_s=time.time() - t0, load_at_end=_load(), n_chains=len(runs))
    pos = {s: i for i, s in enumerate(seeds)}
    v = {cname(*c): [None] * len(seeds) for c in CONDS}
    for r in runs:
        v[r["cond"]][pos[r["seed"]]] = r
    cal = [b for r in v[cname("fresh", "t40", "rational")] for b in _bust_days(r)]
    med = float(np.median(cal))
    n_ok = sum(r["day1_sha"] == ref["day1_sha"][f"{r['cond'].split('|')[1]}|{r['seed']}"] for r in runs)
    gate = {"calibration": {"label": "Calibration: median bust-out day >= 25 (rational, fresh, tourists 40%)",
                            "passed": med >= 25,
                            "detail": f"median {med:g} over {len(cal)} genuine stalls x seeds; never = {DAYS + 1}; "
                                      f"{np.mean([b <= DAYS for b in cal]):.1%} bust out; "
                                      f"{np.mean([b < 25 for b in cal]):.1%} before day 25"},
            "day1_070": {"label": "Day-1 outcomes equal engine 0.7.0 for the same conditions", "passed": n_ok == len(runs),
                         "detail": f"{n_ok} of {len(runs)} chains (outcome minus the 0.8.0 brands block, byte for byte)"}}
    gate["passed"] = all(g["passed"] for k, g in gate.items() if k != "passed")
    res = analyse(v) if gate["passed"] else None
    base = a.out[:-5]
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "gate": gate, "results": res, "runs": runs}, f, sort_keys=True, separators=(",", ":"))
    with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "tourists", "genuine_policy", "seed", "day"] + SERIES)
        for r in runs:
            for d, x in enumerate(r["days"], start=1):
                w.writerow(r["cond"].split("|") + [r["seed"], d] + [x[m] for m in SERIES])
    svgs = _write_plots(base, res, len(seeds), ENGINE_VERSION) if res is not None else ["", ""]
    with open(base + "_summary.md", "w", encoding="utf-8") as f:
        f.write(report(meta, res, gate, svgs))
    print(f"gate passed: {gate['passed']}; {gate}; wrote {a.out}, {base}.csv, {base}_summary.md")
    return 0 if gate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
