"""Search depth, then counterfeits and bust-outs (rule-based only).

Prespecified design (2026-11-06; see runs/search_counterfeit_summary.md). Engine 0.10.0.
  As the counterfeit run (analysis/counterfeit.py), with buyers.count = 150 and buyer search depth
  k (buyers.search_depth, equal for all profiles unless stated).

Calibration (seeds 100-104 only):
    .venv/bin/python -m analysis.search_counterfeit --calibrate --out runs/search_calibration.json
  Condition: budget 1.25, tourist share 0.4, fresh reopening, always-honest originals, 10 days.
  Every k in {1, 2, 3, 4, 6, 8} is run (for the table); k* = the smallest with >= 80% of genuine
  brands rated at the end of day 10 (pooled over genuine stalls and seeds). None: stop and report.

Main run (seeds 2-31; seeds 0-1 were seen in a pipeline check; paired; D = 30):
    .venv/bin/python -m analysis.search_counterfeit --calibration runs/search_calibration.json \\
        --tests "<result>" --out runs/search_counterfeit.json
  Grid 1: budget {1.0, 1.1, 1.25, 1.5} x reopen {fresh, counterfeit}; tourists 0.4; always-honest; k*.
  Grid 2: original policy {rule_genuine, rational v1, rational v2} x reopen; budget 1.25; k*.
  Grid 3 (exploratory): budget 1.25, always-honest, reopen x depth {all 1, all k*, all 2k*,
    tourists 1 with others k*}.
  Robustness: single-day bazaar, default config (naive sellers, default detection), 2 inspectors,
    posts vs patrolling, depth k* for all, seeds 2-31.
  Each distinct condition runs once; shared cells are reported in every grid that uses them.

Gate: (a) in the calibration condition at k* on the main-run seeds, >= 80% of genuine brands rated
by day 10 (pooled); (b) the test suite passes (defaults reproduce 0.9.0; --tests).

Late = days 26-30. Paired by seed; 95% t-intervals, unadjusted.
  PF1-PF4 and the two-sided v2 - always-honest question: as in analysis/counterfeit.py.
  PR (confirmatory, robustness): at k*, patrolling - posts < 0 for deceptive profit per stall and
     for shortfall (both intervals exclude 0).
  Exploratory: Grid 3 (tourists searching less; position rent by k); exposure and sales by aisle
  position (entrance = the end slot on each side of an aisle, 4 of 16 stalls; mid-aisle = the rest).

This script only reads engine outputs; it changes nothing in the engine.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from analysis.counterfeit import (BUDGETS, DAYS, GEN, LATE, LABEL, PROFILES, REOPEN, SHARES, STYLE, TOURIST, Tap,
                                  _ci, _d, _direction, _git, _load, _num, _pct, _t,
                                  _verdict, mean_ci, paired_diff)
from cli.sweep import parse_seeds
from engine import ENGINE_VERSION, bazaar
from engine.config import load

COUNT = 150
CAL_KS = [1, 2, 3, 4, 6, 8]
CAL_SEEDS = list(range(100, 105))
CAL_DAY = 10
CAL_TARGET = 0.80
COMMON = ["ratings.mode=public", "inspectors.count=2", "inspectors.placement=patrolling", "inspectors.uniformed=false",
          "agents.seller.deceptive=rule_deceptive", "brands.enabled=true", "brands.premium=0.4",
          "market.horizon_known=true", "evolution.revise_prob=0", "evolution.mutation_prob=0",
          f"buyers.count={COUNT}", "buyers.search_log=true"]
SERIES = ["deceptive_profit", "genuine_profit", "seconds_profit", "shortfall_rate", "surplus", "task_complete",
          "catches", "renames", "counterfeit_stalls", "busted", "rated_share_genuine", "rating_genuine",
          "genuine_premium", "entrance_unit_share", "mid_exposed_share", "walk_ticks", "seen_mean"]


def depth_label(d) -> str:
    t, lo, ex = d
    return f"all {lo}" if t == lo == ex else f"tourists {t}, others {lo}"


def cname(f, s, t, g, d) -> str:
    return f"{f:g}|{s}|{t}|{g}|{d[0]}-{d[1]}-{d[2]}"


def _overrides(f, s, t, g, d, seed, days=DAYS) -> list[str]:
    return [*COMMON, f"buyers.budget_factor_override={f}", f"market.days={days}",
            f"agents.params.rule_deceptive.reopen={s}", f"buyers.profile_shares={SHARES[t]}",
            f"agents.seller.genuine={GEN[g]}", f'buyers.search_depth={{"tourist":{d[0]},"local":{d[1]},"expert":{d[2]}}}',
            f"seed={seed}"]


def conditions(k):
    K, K2, T1 = (k, k, k), (2 * k, 2 * k, 2 * k), (1, k, k)
    g1 = [(f, s, "t40", "honest", K) for f in BUDGETS for s in REOPEN]
    g2 = [(1.25, s, "t40", g, K) for g in GEN for s in REOPEN]
    g3 = [(1.25, s, "t40", "honest", d) for d in ((1, 1, 1), K, K2, T1) for s in REOPEN]
    return g1, g2, g3, list(dict.fromkeys(g1 + g2 + g3))


def _positions(eng):
    """entrance: the end slot on each side of each aisle (lowest and highest x of the stalls on
    that side); mid-aisle: the rest."""
    side: dict = {}
    for st in eng.stalls:
        side.setdefault((st.category, st.pos[1]), []).append(st.pos[0])
    return {st.sid: "entrance" if st.pos[0] in (min(side[(st.category, st.pos[1])]), max(side[(st.category, st.pos[1])]))
            else "mid" for st in eng.stalls}


def _day_stats(d, gen, posn):
    o = d["outcome"]
    units = o["brands"]["units_by_stall"]
    tot = sum(units.values())
    ex = o["search"]["exposure"]
    mids = [sid for sid, p in posn.items() if p == "mid"]
    bs = [r for r in o["search"]["buyers"].values() if r["seen"] or r["bought"]]
    rated = sum(d["brand_ratings"].get(d["brands"][s]) is not None for s in gen)
    return {"entrance_unit_share": (sum(u for sid, u in units.items() if posn[sid] == "entrance") / tot) if tot else None,
            "mid_exposed_share": sum(ex[s]["in_reach_shopping"] > 0 for s in mids) / len(mids),
            "walk_ticks": float(np.mean([r["walk_ticks"] for r in bs])) if bs else None,
            "seen_mean": float(np.mean([len(r["seen"]) for r in bs])) if bs else None,
            "rated_share_genuine": rated / len(gen),
            "units_entrance": sum(u for sid, u in units.items() if posn[sid] == "entrance"),
            "units_mid": sum(u for sid, u in units.items() if posn[sid] == "mid"),
            "exposed_entrance": sum(ex[s]["in_reach_shopping"] > 0 for s, p in posn.items() if p == "entrance"),
            "exposed_mid": sum(ex[s]["in_reach_shopping"] > 0 for s in mids)}


# ------------------------------------------------------------------ calibration

def _cal_job(args) -> dict:
    k, seed = args
    c = load(None, _overrides(1.25, "fresh", "t40", "honest", (k, k, k), seed, days=CAL_DAY), mode="bazaar")
    eng = bazaar.BazaarEngine(c)
    posn = _positions(eng)
    out = bazaar.run(c)
    gen = [sid for sid, ty in out["days"][0]["stall_types"].items() if ty == "genuine"]
    days = [_day_stats(d, gen, posn) for d in out["days"]]
    gen_pos = {"entrance": sum(posn[s] == "entrance" for s in gen), "mid": sum(posn[s] == "mid" for s in gen)}
    last = out["days"][CAL_DAY - 1]
    rated_by_pos = {p: sum(last["brand_ratings"].get(last["brands"][s]) is not None for s in gen if posn[s] == p)
                    for p in ("entrance", "mid")}
    return {"k": k, "seed": seed, "rated": round(days[-1]["rated_share_genuine"] * len(gen)), "genuine": len(gen),
            "genuine_by_position": gen_pos, "rated_by_position": rated_by_pos, "days": days,
            "fallbacks": sum(d["outcome"]["fallbacks"]["buyer"] for d in out["days"])}


def calibrate(a) -> int:
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as ex:
        rs = list(ex.map(_cal_job, [(k, sd) for k in CAL_KS for sd in CAL_SEEDS]))
    table = []
    for k in CAL_KS:
        r = [x for x in rs if x["k"] == k]
        rated, tot = sum(x["rated"] for x in r), sum(x["genuine"] for x in r)
        agg = lambda key: float(np.mean([np.mean([d[key] for d in x["days"]]) for x in r]))
        table.append({"k": k, "rated": rated, "genuine": tot, "share": rated / tot,
                      "per_seed": {x["seed"]: [x["rated"], x["genuine"]] for x in r},
                      "rated_by_position": {p: [sum(x["rated_by_position"][p] for x in r),
                                                sum(x["genuine_by_position"][p] for x in r)] for p in ("entrance", "mid")},
                      "entrance_unit_share": agg("entrance_unit_share"),
                      "units_per_stall_day": {"entrance": agg("units_entrance") / 12, "mid": agg("units_mid") / 36},
                      "exposed_share": {"entrance": agg("exposed_entrance") / 12, "mid": agg("exposed_mid") / 36},
                      "walk_ticks": agg("walk_ticks"), "seen_mean": agg("seen_mean"),
                      "buyer_fallbacks": sum(x["fallbacks"] for x in r)})
        print(f"k {k}: {rated}/{tot} = {rated / tot:.1%} rated by day {CAL_DAY}", flush=True)
    ok = [row["k"] for row in table if row["share"] >= CAL_TARGET]
    chosen = min(ok) if ok else None
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
            "command": " ".join([".venv/bin/python -m analysis.search_counterfeit", *sys.argv[1:]]),
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
            "seeds": CAL_SEEDS, "day": CAL_DAY, "target": CAL_TARGET, "ks": CAL_KS, "count": COUNT,
            "wall_clock_s": time.time() - t0, "load_at_end": _load(), "workers": a.workers}
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "table": table, "chosen_k": chosen, "runs": rs}, fh, indent=1, sort_keys=True)
    print(f"chosen k: {chosen}; wrote {a.out}")
    return 0 if chosen is not None else 1


def _script_sha() -> str:
    import hashlib
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ main run

def _job(args) -> dict:
    f, s, t, g, d, seed = args
    c = load(None, _overrides(f, s, t, g, d, seed), mode="bazaar")
    eng0 = bazaar.BazaarEngine(c)
    posn = _positions(eng0)
    cat = {st.sid: st.category for st in eng0.stalls}
    tap = Tap()
    out = bazaar.run(c, log=tap)
    stype = out["days"][0]["stall_types"]
    base = c.pricing.base_price_cents
    gen = [sid for sid, ty in stype.items() if ty == "genuine"]
    dec = [sid for sid, ty in stype.items() if ty == "deceptive"]
    bust = {sid: None for sid in gen}
    cf_names: set = set()
    days = []
    for dd in out["days"]:
        o = dd["outcome"]
        pt = o["seller_by_type"]
        for r in dd["renames"]:
            if r["how"] == "counterfeit" and r["counterfeit_of"] is not None:
                cf_names.add(r["to"])
        for b in dd["bust_outs"]:
            bust[b["stall"]] = b["day"]
        rg = [dd["brand_ratings"][dd["brands"][sid]] for sid in gen if dd["brand_ratings"].get(dd["brands"][sid]) is not None]
        prem = [dd["prices"][sid] / base[cat[sid]] - 1 for sid in gen]
        ds = _day_stats(dd, gen, posn)
        days.append({"deceptive_profit": pt["deceptive"]["profit_per_stall_cents"] if "deceptive" in pt else None,
                     "genuine_profit": pt["genuine"]["profit_per_stall_cents"] if "genuine" in pt else None,
                     "seconds_profit": pt["seconds"]["profit_per_stall_cents"] if "seconds" in pt else None,
                     "shortfall_rate": o["shortfall_rate"], "surplus": o["buyer_surplus_mean_cents"],
                     "task_complete": o["task_complete_share"], "catches": o["catches"],
                     "renames": o["brands"]["renames"], "counterfeit_stalls": o["brands"]["counterfeit_stalls"],
                     "busted": o["brands"]["busted_stalls"], "rating_genuine": float(np.mean(rg)) if rg else None,
                     "genuine_premium": float(np.mean(prem)),
                     **{k: ds[k] for k in ("entrance_unit_share", "mid_exposed_share", "walk_ticks", "seen_mean",
                                           "rated_share_genuine")}})
    # deceptive-type stalls' late profit by buyer profile (per stall-day)
    sd = len(dec) * len(LATE)
    acc = {f"{k}_{p}": 0.0 for k in ("units", "revenue", "cf_units") for p in PROFILES}
    dset = set(dec)
    for day in LATE:
        for b in tap.buys.get(day, []):
            if b["stall"] in dset:
                p = b["buyer_profile"]
                acc[f"units_{p}"] += b["units"]
                acc[f"revenue_{p}"] += b["amount_cents"]
                if b["brand"] in cf_names:
                    acc[f"cf_units_{p}"] += b["units"]
    comp = {k: 0.0 for k in ("revenue_cents", "cost_cents", "ad_spend_cents", "penalties_cents", "catches")}
    for day in LATE:
        dd = out["days"][day - 1]["outcome"]["seller_by_type"].get("deceptive", {})
        for k in comp:
            comp[k] += dd.get(k, 0)
    decomp = {**{k: v / sd for k, v in acc.items()}, **{f"{k}_per_stall_day": v / sd for k, v in comp.items()}}
    return {"cond": cname(f, s, t, g, d), "seed": seed, "days": days, "bust": bust, "decomp": decomp,
            "n_genuine": len(gen), "fallbacks": sum(x["outcome"]["fallbacks"]["buyer"] for x in out["days"])}


def _rob_job(args) -> dict:
    placement, k, seed = args
    c = load(None, ["inspectors.count=2", f"inspectors.placement={placement}",
                    f'buyers.search_depth={{"tourist":{k},"local":{k},"expert":{k}}}', f"seed={seed}"], mode="bazaar")
    o = bazaar.run(c)
    return {"placement": placement, "seed": seed, "deceptive_profit": o["seller_by_type"]["deceptive"]["profit_per_stall_cents"],
            "shortfall_rate": o["shortfall_rate"], "surplus": o["buyer_surplus_mean_cents"],
            "task_complete": o["task_complete_share"], "catches": o["catches"], "fallbacks": o["fallbacks"]["buyer"]}


# ------------------------------------------------------------------ analysis

def _arr(v, cond, m):
    return np.array([[np.nan if x[m] is None else x[m] for x in r["days"]] for r in v[cond]], float)


def _late(a):
    with np.errstate(all="ignore"):
        return np.nanmean(a[:, [d - 1 for d in LATE]], 1)


def _lst(a):
    return [None if (x is None or np.isnan(x)) else float(x) for x in a]


def _bust_days(r):
    return [DAYS + 1 if b is None else b for b in r["bust"].values()]


def _slope(xs, G):
    x = np.array(xs, float)
    xc = x - x.mean()
    return (G * xc).sum(1) / (xc ** 2).sum()


def analyse(v: dict, k: int, rob: list) -> dict:
    g1, g2, g3, conds = conditions(k)
    K, K2, T1, D1 = (k, k, k), (2 * k,) * 3, (1, k, k), (1, 1, 1)
    res: dict = {"trajectory": {}, "late": {}}
    for cond in v:
        for m in SERIES:
            a = _arr(v, cond, m)
            res["trajectory"][f"{cond}|{m}"] = [mean_ci(_lst(a[:, j])) for j in range(DAYS)]
            res["late"][f"{cond}|{m}"] = mean_ci(_lst(_late(a)))
    L = {(cond, m): _late(_arr(v, cond, m)) for cond in v for m in SERIES}

    def diff(ca, cb, m):
        return paired_diff(_lst(L[(ca, m)]), _lst(L[(cb, m)]))
    gap = {f: L[(cname(f, "counterfeit", "t40", "honest", K), "deceptive_profit")]
           - L[(cname(f, "fresh", "t40", "honest", K), "deceptive_profit")] for f in BUDGETS}
    res["gap_by_budget"] = {f"{f:g}": mean_ci(_lst(gap[f])) for f in BUDGETS}
    res["pf1"] = {**mean_ci(_lst(_slope(BUDGETS, np.stack([gap[f] for f in BUDGETS], 1)) * 0.1)),
                  "unit": "cents per +0.1 of budget factor"}
    res["pf1"]["verdict"] = _verdict(res["pf1"], +1)
    res["pf2"] = {**res["gap_by_budget"]["1.5"], "verdict": _verdict(res["gap_by_budget"]["1.5"], +1)}
    for s in REOPEN:
        res[f"v2_v1_{s}"] = diff(cname(1.25, s, "t40", "v1", K), cname(1.25, s, "t40", "v2", K), "genuine_profit")
        res[f"v2_honest_{s}"] = diff(cname(1.25, s, "t40", "honest", K), cname(1.25, s, "t40", "v2", K), "genuine_profit")
        res[f"v1_honest_{s}"] = diff(cname(1.25, s, "t40", "honest", K), cname(1.25, s, "t40", "v1", K), "genuine_profit")
    res["pf3"] = {**res["v2_v1_fresh"], "verdict": _verdict(res["v2_v1_fresh"], +1)}
    res["q_honesty"] = {**res["v2_honest_fresh"], "direction": _direction(res["v2_honest_fresh"])}
    bt = {}
    for g in ("v1", "v2"):
        for s in REOPEN:
            cond = cname(1.25, s, "t40", g, K)
            pooled = [b for r in v[cond] for b in _bust_days(r)]
            bt[f"{g}|{s}"] = {"mean_day": mean_ci([float(np.mean(_bust_days(r))) for r in v[cond]]),
                              "share_bust": mean_ci([float(np.mean([b is not None for b in r["bust"].values()])) for r in v[cond]]),
                              "median_day_pooled": float(np.median(pooled)),
                              "hist": [int(sum(1 for b in pooled if b == dd)) for dd in range(1, DAYS + 2)]}
        f_, c_ = cname(1.25, "fresh", "t40", g, K), cname(1.25, "counterfeit", "t40", g, K)
        bt[f"{g}|cf-fresh"] = paired_diff([float(np.mean(_bust_days(r))) for r in v[f_]],
                                          [float(np.mean(_bust_days(r))) for r in v[c_]])
        bt[f"{g}|share cf-fresh"] = paired_diff([float(np.mean([b is not None for b in r["bust"].values()])) for r in v[f_]],
                                                [float(np.mean([b is not None for b in r["bust"].values()])) for r in v[c_]])
    for s in REOPEN:
        a_, b_ = cname(1.25, s, "t40", "v1", K), cname(1.25, s, "t40", "v2", K)
        bt[f"v2-v1|{s}"] = paired_diff([float(np.mean(_bust_days(r))) for r in v[a_]], [float(np.mean(_bust_days(r))) for r in v[b_]])
    res["bust"] = bt
    res["pf4"] = {**bt["v2|cf-fresh"], "verdict": _verdict(bt["v2|cf-fresh"], -1)}
    res["cf_fresh"] = {}
    for f, s, t, g, d in conds:
        if s != "fresh":
            continue
        for m in ("deceptive_profit", "genuine_profit", "shortfall_rate", "surplus", "rated_share_genuine"):
            res["cf_fresh"][f"{cname(f, '*', t, g, d)}|{m}"] = diff(cname(f, "fresh", t, g, d), cname(f, "counterfeit", t, g, d), m)
    res["policy_contrasts"] = {}
    for s in REOPEN:
        for g in ("v1", "v2"):
            for m in ("shortfall_rate", "surplus", "genuine_profit", "deceptive_profit"):
                res["policy_contrasts"][f"{s}|{g}-honest|{m}"] = diff(cname(1.25, s, "t40", "honest", K),
                                                                      cname(1.25, s, "t40", g, K), m)
    # Grid 3: depth contrasts
    depths = list(dict.fromkeys([D1, K, K2, T1]))
    res["depths"] = [list(d) for d in depths]
    res["depth_gap"] = {}
    for d in depths:
        gd = L[(cname(1.25, "counterfeit", "t40", "honest", d), "deceptive_profit")] \
            - L[(cname(1.25, "fresh", "t40", "honest", d), "deceptive_profit")]
        res["depth_gap"][depth_label(d)] = gd
    res["depth_gap_ci"] = {lab: mean_ci(_lst(x)) for lab, x in res["depth_gap"].items()}
    if T1 != K:
        res["tourist_search_gap_diff"] = paired_diff(_lst(res["depth_gap"][depth_label(K)]),
                                                     _lst(res["depth_gap"][depth_label(T1)]))
    res["depth_gap"] = {lab: _lst(x) for lab, x in res["depth_gap"].items()}
    res["depth_contrasts"] = {}
    for s in REOPEN:
        for d in depths:
            if d == K:
                continue
            for m in ("deceptive_profit", "genuine_profit", "shortfall_rate", "surplus", "entrance_unit_share",
                      "rated_share_genuine"):
                res["depth_contrasts"][f"{s}|{depth_label(d)}|{m}"] = diff(cname(1.25, s, "t40", "honest", K),
                                                                           cname(1.25, s, "t40", "honest", d), m)
    keys = list(next(iter(v.values()))[0]["decomp"].keys())
    res["decomp"] = {}
    for d in depths:
        for s in REOPEN:
            res["decomp"][f"{depth_label(d)}|{s}"] = {kk: mean_ci([r["decomp"][kk] for r in v[cname(1.25, s, "t40", "honest", d)]])
                                                      for kk in keys}
        rf, rc = v[cname(1.25, "fresh", "t40", "honest", d)], v[cname(1.25, "counterfeit", "t40", "honest", d)]
        res["decomp"][f"{depth_label(d)}|cf-fresh"] = {kk: paired_diff([r["decomp"][kk] for r in rf], [r["decomp"][kk] for r in rc])
                                                       for kk in keys}
    # position rent by depth (fresh, always-honest): day 1 and late
    res["position"] = {}
    for d in sorted(set(depths), key=lambda x: (x[1], x[0])):
        cond = cname(1.25, "fresh", "t40", "honest", d)
        a = _arr(v, cond, "entrance_unit_share")
        res["position"][depth_label(d)] = {"k": list(d), "day1": mean_ci(_lst(a[:, 0])), "late": mean_ci(_lst(_late(a))),
                                           "mid_exposed_day1": mean_ci(_lst(_arr(v, cond, "mid_exposed_share")[:, 0]))}
    # robustness
    by = {pl: sorted([r for r in rob if r["placement"] == pl], key=lambda r: r["seed"]) for pl in ("posts", "patrolling")}
    res["rob"] = {}
    for m in ("deceptive_profit", "shortfall_rate", "surplus", "task_complete", "catches"):
        res["rob"][m] = {"posts": mean_ci([r[m] for r in by["posts"]]), "patrolling": mean_ci([r[m] for r in by["patrolling"]]),
                         "diff": paired_diff([r[m] for r in by["posts"]], [r[m] for r in by["patrolling"]])}
    res["pr"] = {m: {**res["rob"][m]["diff"], "verdict": _verdict(res["rob"][m]["diff"], -1)}
                 for m in ("deceptive_profit", "shortfall_rate")}
    flags = []
    for cond in v:
        sb = res["late"][f"{cond}|shortfall_rate"]["mean"]
        if sb is not None and (sb < 0.02 or sb > 0.98):
            flags.append(f"{cond}: late shortfall {sb:.3f}")
        fb = sum(r["fallbacks"] for r in v[cond])
        if fb:
            flags.append(f"{cond}: {fb} invalid buyer actions (fallbacks)")
    res["flags"] = flags
    return res


# ------------------------------------------------------------------ plots

def plot_gap_svg(res, n, k, version=ENGINE_VERSION) -> str:
    from analysis.counterfeit import plot_gap_svg as base
    svg = base(res, n, COUNT, version)
    return svg.replace("2 patrolling inspectors, naive deceptive sellers, 30 days",
                       f"search depth {k}, 2 patrolling inspectors, naive deceptive sellers, 30 days")


def plot_bust_svg(res, n, k, version=ENGINE_VERSION) -> str:
    from analysis.counterfeit import plot_bust_svg as base
    svg = base(res, n, COUNT, version)
    return svg.replace("150 buyers a day, 2 patrolling", f"150 buyers a day, search depth {k}, 2 patrolling")


def plot_position_svg(res, cal, n, k, version=ENGINE_VERSION) -> str:
    """Share of units sold at aisle-entrance stalls against search depth: calibration (10 days,
    seeds 100-104, k = 1..8, mean over days) and main run (fresh, always-honest; day 1 and late)."""
    W, H = 900, 600
    left, top, pw, ph = 110, 120, 680, 360
    ks = [row["k"] for row in cal["table"]]
    kmax = max(ks + [2 * k])

    def X(x):
        return left + (x - 0.5) / (kmax + 0.5 - 0.5) * pw

    def Y(y):
        return top + ph - min(1.0, max(0.0, y)) * ph
    title = "Where buyers buy: share of units sold at aisle-entrance stalls, by search depth"
    sub = "Entrance = the end stall on each side of an aisle (4 of 16 stalls, 25%); budget 1.25 × base, tourists 40%"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" aria-labelledby="t d">',
           STYLE, f'<rect class="bg" x="0" y="0" width="{W}" height="{H}"/>', f'<title id="t">{title}</title>',
           '<desc id="d">Lines: calibration seeds (mean over 10 days) by depth; points: main run, day 1 and days 26–30. '
           'The summary gives every value.</desc>',
           f'<text class="t" x="30" y="44" font-size="20">{title}</text>',
           f'<text class="s" x="30" y="70" font-size="14">{sub}</text>']
    out.append(f'<line class="zero" x1="{X(0.7):.1f}" y1="{Y(0.25):.1f}" x2="{X(kmax + 0.3):.1f}" y2="{Y(0.25):.1f}"/>')
    out.append(f'<text class="k" x="{X(0.7):.1f}" y="{Y(0.25) - 6:.1f}">25%: no position rent</text>')
    pts = " ".join(f"{X(row['k']):.1f},{Y(row['entrance_unit_share']):.1f}" for row in cal["table"])
    out.append(f'<polyline class="ln" points="{pts}"/>')
    for row in cal["table"]:
        out.append(f'<circle class="pt" cx="{X(row["k"]):.1f}" cy="{Y(row["entrance_unit_share"]):.1f}" r="3"/>')
    mid = cal["table"][len(cal["table"]) // 2 + 1]
    out.append(f'<text class="lb" x="{X(mid["k"]) + 6:.1f}" y="{Y(mid["entrance_unit_share"]) - 12:.1f}">calibration seeds, days 1–10</text>')
    for lab, pos in res["position"].items():
        kk = pos["k"]
        if kk[0] != kk[1]:
            continue
        for key, cls, dx in (("day1", "pt", -6), ("late", "hl", 6)):
            st = pos[key]
            x = X(kk[1]) + dx
            out.append(f'<line class="{"ci" if cls == "pt" else "hlc"}" x1="{x:.1f}" y1="{Y(st["lo"]):.1f}" x2="{x:.1f}" y2="{Y(st["hi"]):.1f}"/>')
            out.append(f'<rect class="{cls}" x="{x - 3:.1f}" y="{Y(st["mean"]) - 3:.1f}" width="6" height="6"/>')
    out.append(f'<text class="an" x="{X(kmax) - 4:.1f}" y="{top + 16}" text-anchor="end">main run, 95% intervals: '
               f'■ day 1, <tspan class="hl">■</tspan> days 26–30</text>')
    out.append(f'<line class="ax" x1="{left - 12}" y1="{Y(0):.1f}" x2="{left - 12}" y2="{Y(1):.1f}"/>')
    for y in (0, 0.25, 0.5, 0.75, 1.0):
        out.append(f'<text class="k" x="{left - 18}" y="{Y(y) + 4:.1f}" text-anchor="end">{100 * y:.0f}%</text>')
    out.append(f'<line class="ax" x1="{X(1):.1f}" y1="{top + ph + 12}" x2="{X(kmax):.1f}" y2="{top + ph + 12}"/>')
    for x in sorted(set(ks + [2 * k])):
        out.append(f'<text class="k" x="{X(x):.1f}" y="{top + ph + 28}" text-anchor="middle">{x}</text>')
    out.append(f'<text class="k" x="{left + pw / 2}" y="{top + ph + 48}" text-anchor="middle">search depth k (stalls seen '
               f'before choosing), all profiles</text>')
    out.append(f'<text class="n" x="30" y="{H - 40}">Bazaar engine {version}. Calibration: seeds 100–104, fresh reopening, '
               f'always-honest originals. Main run: {n} paired seeds, 95% t-intervals, fresh reopening,</text>')
    out.append(f'<text class="n" x="30" y="{H - 24}">always-honest originals; 150 buyers a day, 2 patrolling inspectors, '
               f'premium 0.4 (placeholder). k* = {k} from calibration.</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def _write_plots(base, res, cal, n, k, version):
    names = [base + "_gap_by_budget.svg", base + "_bust_days.svg", base + "_position_by_depth.svg"]
    for path, svg in zip(names, (plot_gap_svg(res, n, k, version), plot_bust_svg(res, n, k, version),
                                 plot_position_svg(res, cal, n, k, version))):
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
    return [os.path.basename(x) for x in names]


# ------------------------------------------------------------------ report

def report(meta, res, gate, svgs) -> str:
    cal = meta["calibration"]
    k = cal["chosen_k"]
    K = (k, k, k)
    L = ["# Search depth, then counterfeits and bust-outs", "",
         "Run spec \"search depth, then counterfeits and bust-outs (rule-based only)\"; predictions written "
         "2026-11-06, before any run.", "", "## Run record", "",
         f"- Engine `{meta['engine_version']}`; commit `{meta['git']['commit']}`; uncommitted at run time: "
         f"{meta['git']['status_porcelain'] or 'none'}",
         f"- Script sha256 `{meta['script_sha256']}`", f"- Command: `{meta['command']}`",
         f"- Tests at the engine commit: {meta.get('tests') or 'not recorded'}",
         f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
         f"- {meta['n_chains']} chains × {DAYS} days + {meta['n_rob']} single-day robustness runs on {meta['workers']} "
         f"workers; wall clock {meta['wall_clock_s'] / 60:.1f} min; load average {meta['load_at_start']} at start, "
         f"{meta['load_at_end']} at end",
         f"- Seeds {meta['seeds'][0]}–{meta['seeds'][-1]}, paired; buyers.count = {COUNT}; search depth k* = {k}",
         "", "## Calibration (seeds 100–104)", "",
         f"Budget 1.25, tourists 40%, fresh reopening, always-honest originals, {COUNT} buyers, {CAL_DAY} days; equal "
         f"depth for all profiles. Criterion: ≥ 80% of genuine brands rated at the end of day 10, pooled. All six "
         f"depths were run for the table. Calibration commit `{cal['meta']['git']['commit']}`, "
         f"{cal['meta']['wall_clock_s'] / 60:.1f} min. Entrance = the end stall on each side of an aisle (12 of 48 "
         f"stalls); mid-aisle = the other 36. Units, exposure, walking and stalls seen are means over the 10 days.", ""]
    L += _t(["k", "Genuine rated by day 10", "Share", "Rated: entrance", "Rated: mid-aisle", "Units at entrance (%)",
             "Units/stall-day: entrance", "mid-aisle", "Exposed (%): entrance", "mid-aisle", "Stalls seen per buyer",
             "Walking ticks per buyer"],
            [[str(r["k"]), f"{r['rated']}/{r['genuine']}", f"{100 * r['share']:.1f}%",
              "{}/{}".format(*r["rated_by_position"]["entrance"]), "{}/{}".format(*r["rated_by_position"]["mid"]),
              f"{100 * r['entrance_unit_share']:.1f}", f"{r['units_per_stall_day']['entrance']:.2f}",
              f"{r['units_per_stall_day']['mid']:.2f}", f"{100 * r['exposed_share']['entrance']:.0f}",
              f"{100 * r['exposed_share']['mid']:.0f}", f"{r['seen_mean']:.2f}", f"{r['walk_ticks']:.2f}"]
             for r in cal["table"]])
    L += ["", f"**k* = {k}.**", "", "## Gate", ""]
    for kk, g in gate.items():
        if kk != "passed":
            L.append(f"- {g['label']}: **{'passed' if g['passed'] else 'FAILED'}** ({g['detail']})")
    L.append("")
    if res is None:
        return "\n".join(L + ["**Gate failed: results not reported.**", ""])
    dol = _d
    p1, p2, p3, p4, q = res["pf1"], res["pf2"], res["pf3"], res["pf4"], res["q_honesty"]
    bt, lt = res["bust"], res["late"]
    pr = res["pr"]
    L += ["## Design (prespecified)", "",
          f"- As the counterfeit run (`runs/counterfeit_summary.md`): ratings public (memory 0.7, threshold 0.5; locals "
          f"and experts see them); 2 patrolling inspectors, not uniformed; naive deceptive sellers; 30 days known to "
          f"sellers; imitation off; brands on, premium 0.4 (placeholder); tourists 40% = 0.4 / 0.3 / 0.3. "
          f"buyers.count = {COUNT}; depth k* = {k} for all profiles unless stated.",
          "- Search (decided 2026-11-06): a buyer with depth k records open stalls of its category within reach, "
          "learns as the 0.9.0 rule does (asks, inspects), and buys only after k stalls or at the end of its route, "
          "choosing among stalls it believes meet Q_req, pass the rating threshold and fit its budget: highest "
          "visible rating (unrated = 0.5) then lowest price; tourists lowest price; ties by stall id. It walks back "
          "to a stall seen earlier; a chosen stall found closed is skipped. After buying it walks on.",
          "- Grids as listed in the script docstring; robustness: single-day default bazaar, 2 inspectors, posts vs "
          f"patrolling, depth {k}, seeds 2–31.",
          "- Late = days 26–30; 95% paired t-intervals, unadjusted. Confirmatory: PF1–PF4, PR. Two-sided question: "
          "v2 − always-honest. Everything else exploratory.", "",
          "## Confirmatory", "",
          f"- **PF1**: slope of the late counterfeit − fresh gap in profit per deceptive stall over budget 1.0–1.5: "
          f"${_ci(p1, dol)} per +0.1 of budget factor. Prediction > 0. **Verdict: {p1['verdict']}.**",
          f"- **PF2**: the gap at budget 1.5: ${_ci(p2, dol)} per stall per day. Prediction > 0. **Verdict: {p2['verdict']}.**",
          f"- **PF3**: late genuine profit per stall, v2 − v1 (fresh): ${_ci(p3, dol)} per day. Prediction > 0. "
          f"**Verdict: {p3['verdict']}.**",
          f"- **PF4**: under v2, mean bust-out day (never = 31), counterfeit − fresh: {_ci(p4, _num(2))} days. "
          f"Prediction < 0. **Verdict: {p4['verdict']}.** Share busting out: fresh "
          f"{_ci(bt['v2|fresh']['share_bust'], _pct, False)}%, counterfeit {_ci(bt['v2|counterfeit']['share_bust'], _pct, False)}%.",
          f"- **PR** (single-day robustness at k = {k}): patrolling − posts, deceptive profit per stall "
          f"${_ci(pr['deceptive_profit'], dol)} (**{pr['deceptive_profit']['verdict']}**); shortfall "
          f"{_ci(pr['shortfall_rate'], _pct)} points (**{pr['shortfall_rate']['verdict']}**). Prediction < 0 for both.",
          "", "## Two-sided question: is honesty irrational?", "",
          f"Late genuine profit per stall, v2 − always-honest (fresh): ${_ci(q, dol)} per day; **{q['direction']}**. "
          f"Counterfeit reopening (exploratory): ${_ci(res['v2_honest_counterfeit'], dol)}. v1 − always-honest: fresh "
          f"${_ci(res['v1_honest_fresh'], dol)}, counterfeit ${_ci(res['v1_honest_counterfeit'], dol)}.", "",
          "## Grid 1: counterfeit economics by budget", ""]
    cf = res["cf_fresh"]
    L += _t(["Budget", "Deceptive profit: fresh ($)", "counterfeit ($)", "counterfeit − fresh ($)",
             "Genuine profit, cf − fresh ($)", "Shortfall, cf − fresh (pts)", "Surplus, cf − fresh ($)"],
            [[f"{f:g}×", _ci(lt[f"{cname(f, 'fresh', 't40', 'honest', K)}|deceptive_profit"], dol, False),
              _ci(lt[f"{cname(f, 'counterfeit', 't40', 'honest', K)}|deceptive_profit"], dol, False),
              _ci(res["gap_by_budget"][f"{f:g}"], dol),
              _ci(cf[f"{cname(f, '*', 't40', 'honest', K)}|genuine_profit"], dol),
              _ci(cf[f"{cname(f, '*', 't40', 'honest', K)}|shortfall_rate"], _pct),
              _ci(cf[f"{cname(f, '*', 't40', 'honest', K)}|surplus"], dol)] for f in BUDGETS])
    L += ["", f"![counterfeit − fresh gap by budget]({svgs[0]})", "", "## Grid 2: bust-out rules", ""]
    L += _t(["Rule", "Reopen", "Mean bust-out day", "Median (pooled)", "Share bust out (%)", "Genuine profit ($)",
             "Shortfall (%)", "Surplus ($)"],
            [[LABEL[g], LABEL[s], _ci(bt[f"{g}|{s}"]["mean_day"], _num(2), False) if g != "honest" else "–",
              f"{bt[f'{g}|{s}']['median_day_pooled']:g}" if g != "honest" else "–",
              _ci(bt[f"{g}|{s}"]["share_bust"], _pct, False) if g != "honest" else "–",
              _ci(lt[f"{cname(1.25, s, 't40', g, K)}|genuine_profit"], dol, False),
              _ci(lt[f"{cname(1.25, s, 't40', g, K)}|shortfall_rate"], _pct, False),
              _ci(lt[f"{cname(1.25, s, 't40', g, K)}|surplus"], dol, False)] for g in GEN for s in REOPEN])
    pc = res["policy_contrasts"]
    L += ["", "Paired contrasts:", ""]
    L += _t(["Reopen", "Contrast", "Genuine profit ($)", "Deceptive profit ($)", "Shortfall (pts)", "Surplus ($)"],
            [[LABEL[s], f"{LABEL[g]} − rule_genuine", _ci(pc[f"{s}|{g}-honest|genuine_profit"], dol),
              _ci(pc[f"{s}|{g}-honest|deceptive_profit"], dol), _ci(pc[f"{s}|{g}-honest|shortfall_rate"], _pct),
              _ci(pc[f"{s}|{g}-honest|surplus"], dol)] for s in REOPEN for g in ("v1", "v2")]
            + [[LABEL[s], "v2 − v1", _ci(res[f"v2_v1_{s}"], dol), "", "", ""] for s in REOPEN])
    L += ["", "Bust-out timing (days; share in points):", ""]
    L += _t(["Contrast", "Mean bust-out day", "Share bust out"],
            [["v1: counterfeit − fresh", _ci(bt["v1|cf-fresh"], _num(2)), _ci(bt["v1|share cf-fresh"], _pct)],
             ["v2: counterfeit − fresh", _ci(bt["v2|cf-fresh"], _num(2)), _ci(bt["v2|share cf-fresh"], _pct)],
             ["v2 − v1, fresh", _ci(bt["v2-v1|fresh"], _num(2)), ""],
             ["v2 − v1, counterfeit", _ci(bt["v2-v1|counterfeit"], _num(2)), ""]])
    L += ["", f"![bust-out days]({svgs[1]})", "", "## Grid 3: search depth and tourists (exploratory)", "",
          "Counterfeit − fresh gap in late profit per deceptive stall, by depth (budget 1.25, always-honest):", ""]
    L += _t(["Depth", "Gap ($/stall/day)"], [[lab, _ci(st, dol)] for lab, st in res["depth_gap_ci"].items()])
    if "tourist_search_gap_diff" in res:
        L += ["", f"Gap with tourists at depth 1 (others {k}) minus gap with everyone at {k}: "
              f"${_ci(res['tourist_search_gap_diff'], dol)}."]
    L += ["", f"Contrasts against everyone at depth {k} (late):", ""]
    dcx = res["depth_contrasts"]
    rows = []
    for s in REOPEN:
        for d in res["depths"]:
            if tuple(d) == K:
                continue
            lab = depth_label(d)
            rows.append([LABEL[s], f"{lab} − all {k}", _ci(dcx[f"{s}|{lab}|deceptive_profit"], dol),
                         _ci(dcx[f"{s}|{lab}|genuine_profit"], dol), _ci(dcx[f"{s}|{lab}|shortfall_rate"], _pct),
                         _ci(dcx[f"{s}|{lab}|surplus"], dol), _ci(dcx[f"{s}|{lab}|entrance_unit_share"], _pct),
                         _ci(dcx[f"{s}|{lab}|rated_share_genuine"], _pct)])
    L += _t(["Reopen", "Contrast", "Deceptive profit ($)", "Genuine profit ($)", "Shortfall (pts)", "Surplus ($)",
             "Entrance unit share (pts)", "Genuine rated (pts)"], rows)
    L += ["", "Deceptive stalls' late revenue by buyer profile, counterfeit − fresh ($ per stall-day):", ""]
    dc = res["decomp"]
    L += _t(["Depth", "Tourists", "Locals", "Experts", "Penalties", "Catches"],
            [[depth_label(d)] + [_ci(dc[f"{depth_label(d)}|cf-fresh"][f"revenue_{p}"], dol) for p in PROFILES]
             + [_ci(dc[f"{depth_label(d)}|cf-fresh"]["penalties_cents_per_stall_day"], dol),
                _ci(dc[f"{depth_label(d)}|cf-fresh"]["catches_per_stall_day"], _num(2))] for d in res["depths"]])
    L += ["", "Position rent (fresh, always-honest): share of units sold at entrance stalls (25% = none):", ""]
    L += _t(["Depth", "Day 1 (%)", "Days 26–30 (%)", "Mid-aisle stalls exposed on day 1 (%)"],
            [[lab, _ci(p["day1"], _pct, False), _ci(p["late"], _pct, False), _ci(p["mid_exposed_day1"], _pct, False)]
             for lab, p in res["position"].items()])
    L += ["", f"![position rent by depth]({svgs[2]})", "", "## Robustness: single-day bazaar (PR)", ""]
    rb = res["rob"]
    L += _t(["Outcome", "Posts", "Patrolling", "Patrolling − posts"],
            [[m, _ci(rb[m]["posts"], f, False), _ci(rb[m]["patrolling"], f, False), _ci(rb[m]["diff"], f)]
             for m, f in (("deceptive_profit", dol), ("shortfall_rate", _pct), ("surplus", dol),
                          ("task_complete", _pct), ("catches", _num(1)))])
    L += ["", "## Late levels (days 26–30)", ""]

    def g_(c, m, f):
        return _ci(lt[f"{c}|{m}"], f, False)
    L += _t(["Condition", "Deceptive profit ($)", "Genuine profit ($)", "Shortfall (%)", "Surplus ($)",
             "Task complete (%)", "Genuine premium (%)", "Genuine rated (%)", "Entrance units (%)", "Catches/day",
             "Counterfeit stalls", "Busted stalls", "Walking ticks/buyer"],
            [[c, g_(c, "deceptive_profit", dol), g_(c, "genuine_profit", dol), g_(c, "shortfall_rate", _pct),
              g_(c, "surplus", dol), g_(c, "task_complete", _pct), g_(c, "genuine_premium", _pct),
              g_(c, "rated_share_genuine", _pct), g_(c, "entrance_unit_share", _pct), g_(c, "catches", _num(1)),
              g_(c, "counterfeit_stalls", _num(1)), g_(c, "busted", _num(1)), g_(c, "walk_ticks", _num(2))]
             for c in meta["conditions"]])
    L += ["", "Condition key: budget factor | reopen | tourist share | original policy | depth tourist-local-expert.",
          "", "## Floors, ceilings and invalid actions", ""] + ([f"- {x}" for x in res["flags"]] or ["- none"])
    L += ["", "## Verdicts", "", "VERDICTS_PLACEHOLDER", "", "## Reading (written after the results)", "",
          "READING_PLACEHOLDER", "", "## Caveats", "", "CAVEATS_PLACEHOLDER", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="2-31")
    ap.add_argument("--out", default="runs/search_counterfeit.json")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--calibration", default="runs/search_calibration.json")
    ap.add_argument("--tests", default=None)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--replot", action="store_true")
    a = ap.parse_args(argv)
    if a.calibrate:
        return calibrate(a)
    base = a.out[:-5] if a.out.endswith(".json") else a.out
    if a.replot:
        with gzip.open(base + ".json.gz", "rt", encoding="utf-8") as f:
            d = json.load(f)
        m = d["meta"]
        print(_write_plots(base, d["results"], m["calibration"], len(m["seeds"]), m["calibration"]["chosen_k"],
                           m["engine_version"]))
        return 0
    seeds = parse_seeds(a.seeds)
    with open(a.calibration, encoding="utf-8") as f:
        cal = json.load(f)
    if set(seeds) & set(cal["meta"]["seeds"]) or set(seeds) & {0, 1}:
        raise SystemExit("main-run seeds overlap the calibration seeds or the pipeline-check seeds 0-1")
    k = cal["chosen_k"]
    if k is None:
        raise SystemExit("calibration found no depth that meets the target; nothing to run")
    g1, g2, g3, conds = conditions(k)
    cal_small = {kk: v for kk, v in cal.items() if kk != "runs"}
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
            "command": " ".join([".venv/bin/python -m analysis.search_counterfeit", *(argv or sys.argv[1:])]),
            "tests": a.tests, "load_at_start": _load(), "python": platform.python_version(), "numpy": np.__version__,
            "platform": platform.platform(), "workers": a.workers, "seeds": seeds, "days": DAYS, "count": COUNT,
            "conditions": [cname(*c) for c in conds], "calibration": cal_small}
    jobs = [(*c, sd) for sd in seeds for c in conds]
    rjobs = [(pl, k, sd) for sd in seeds for pl in ("posts", "patrolling")]
    t0 = time.time()
    runs, rob = [], []
    with ProcessPoolExecutor(a.workers) as ex:
        for r in ex.map(_rob_job, rjobs):
            rob.append(r)
        print(f"robustness: {len(rob)} runs, {time.time() - t0:.0f} s", flush=True)
        for i, r in enumerate(ex.map(_job, jobs)):
            runs.append(r)
            if (i + 1) % len(conds) == 0:
                print(f"{i + 1}/{len(jobs)} chains, {time.time() - t0:.0f} s, load {_load()}", flush=True)
    meta.update(wall_clock_s=time.time() - t0, load_at_end=_load(), n_chains=len(runs), n_rob=len(rob))
    pos = {s: i for i, s in enumerate(seeds)}
    v = {cname(*c): [None] * len(seeds) for c in conds}
    for r in runs:
        v[r["cond"]][pos[r["seed"]]] = r
    calr = v[cname(1.25, "fresh", "t40", "honest", (k, k, k))]
    rated = sum(round(r["days"][CAL_DAY - 1]["rated_share_genuine"] * r["n_genuine"]) for r in calr)
    tot = sum(r["n_genuine"] for r in calr)
    gate = {"calibration": {"label": f"Calibration met on the main-run seeds: >= 80% of genuine brands rated by day "
                                     f"{CAL_DAY} (budget 1.25, tourists 40%, fresh, always-honest, depth {k})",
                            "passed": rated / tot >= CAL_TARGET, "detail": f"{rated}/{tot} = {rated / tot:.1%} over {len(calr)} seeds"},
            "tests": {"label": "Defaults reproduce 0.9.0 (test suite)", "passed": bool(a.tests) and "failed" not in a.tests,
                      "detail": a.tests or "not recorded"}}
    gate["passed"] = all(g["passed"] for kk, g in gate.items() if kk != "passed")
    res = analyse(v, k, rob) if gate["passed"] else None
    with gzip.open(base + ".json.gz", "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "gate": gate, "results": res, "runs": runs, "robustness": rob}, f, sort_keys=True,
                  separators=(",", ":"))
    with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["budget_factor", "reopen", "tourists", "original_policy", "depth", "seed", "day"] + SERIES)
        for r in runs:
            for dd, x in enumerate(r["days"], start=1):
                w.writerow(r["cond"].split("|") + [r["seed"], dd] + [x[m] for m in SERIES])
    svgs = _write_plots(base, res, cal, len(seeds), k, ENGINE_VERSION) if res is not None else ["", "", ""]
    with open(base + "_summary.md", "w", encoding="utf-8") as f:
        f.write(report(meta, res, gate, svgs))
    print(f"gate passed: {gate['passed']}; {gate}; wrote {base}.json.gz, {base}.csv, {base}_summary.md")
    return 0 if gate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
