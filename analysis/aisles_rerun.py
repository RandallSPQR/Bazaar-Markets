"""Aisles rerun (plan runs/plan_autonomous_2026-11-28.md, preregistered at 9751d0c): Runs A and B with fixed costs
calibrated to a net-margin target, gain as a share of honest revenue, 9 sampled stalls per seed, fresh seeds.

Engine 1.3.1, unchanged. The plan's changes are made here, in the calibration script:
1. Fixed cost targets a net margin. Per (profile, category, stall type), from honest never chains at t40, ds 0, alpha 0
   on seeds 900-904 (no fixed cost, no solvency, no rent):
       F = (sum(revenue - unit cost - ad spend) - m * sum(revenue)) / stall-days, floored at 0 (flagged when it binds),
   m: realistic fish 0.02, electronics 0.03, designer 0.30; Run A thin 0.02, fat 0.30 (PLACEHOLDERs). Charged with the
   1.3.1 keys fixed_cost_share = 1.0 and baseline_gross_by_type_cents = F.
2. Primary estimand: per seed, (sum of gains) / (sum of the same stalls' never-chain revenue over the 30 days), pooled
   over the 9 sampled stalls or per aisle over its 3; then mean and 95% t over seeds, unadjusted. Secondary: base-price
   units; the per-stall mean of ratios (gain / revenue); the D5 ratio to never-chain profit with its count of <= 0.
3. Sample: 3 genuine stalls per aisle per seed from default_rng([seed, 17]).
4. Seeds: Run A 760-779, Run B 780-799. Pilot 900-902.

Deviations of plan 2026-11-28 (logged in runs/STATUS.md before any result; numbered for this plan):
D1 (implementation) Each bust-out chain continues from a copy of its never chain's state after day b - 1 under the
   bust-out config, instead of simulating days 1..b-1 again. The stall behaves as in the never chain before day b, so
   the output is the full chain's; gate G2e checks this, chain for chain, on the pilot.
D2 "Profile" in change 1: in Run A the four synthetic profiles (margin x verifiability), each at its margin's target;
   in Run B the realistic profile per category. Every stall type gets its category's target.
D3 Start cash, the credit limit and the rent tables are calibrated as in plan 2026-11-27 (per scenario: Run A per
   cell, Run B per ds), now on seeds 900-904; only the fixed cost comes from the t40 ds 0 alpha 0 scenario.
D4 The 3 stalls per aisle: rng.choice(n, 3, replace=False) per aisle in the order fish, electronics, designer from one
   default_rng([seed, 17]).
D5 Net margin = (revenue - unit cost - ad spend - fixed cost) / revenue, a ratio of sums over a type's stall-days in
   the market.
D6 Gates. G2 = G2a (1.2.0 defaults reproduce), G2b (cost targets), G2c (calibration rerun and recalculation),
   G2e (D1 continuation identity), G2m (realised genuine net margin within 1 point of target per category in the
   calibration-condition cells A|.|.|t40|ds0 and B|cash20|a0|ds0, pooled over the pilot seeds, or the floor binds).
   G6 confirmatory cells: Run A t40 ds 0 and ds 1, Run B ds 0 alpha 0. G4 (50%) is reported, not a gate.

    PYTHONPATH=. .venv/bin/python -m analysis.aisles_rerun --phase pilot --tests "..."
    PYTHONPATH=. .venv/bin/python -m analysis.aisles_rerun --phase run --runs A,B --max-secs 36000 --tests "..."
    PYTHONPATH=. .venv/bin/python -m analysis.aisles_rerun --phase analyse --runs A,B
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

import numpy as np

import analysis.chainrun as CR
import analysis.liability as LB
from analysis import aisles_1_3 as AS
from analysis.capture import memory_state
from engine import ENGINE_VERSION, benchmark
from engine import bazaar as EB
from engine import categories as CAT
from engine import days as DAYS
from engine.config import load
from engine.jsonlog import JsonlLog
from engine.metrics import mean_ci

REF = AS.REF
NEVER = benchmark.NEVER
CANDS = AS.CANDS                                   # 20, 25, 28, 29, 30
DAYS_N = 30
CATS = AS.CATS
TYPES = AS.TYPES
PER_AISLE = 3
PILOT = [900, 901, 902]
CAL_SEEDS = [900, 901, 902, 903, 904]
SEEDS = {"A": list(range(760, 780)), "B": list(range(780, 800))}
SEEDS_CUT = 15                                     # G3: cut to 15 seeds if the projection is over 14 h
OUT = "runs"
CAL_FILE = f"{OUT}/aisles_r_calibration.json"
CACHE = f"{OUT}/aisles_r_cache.jsonl"
RUN_LOG = f"{OUT}/aisles_r_run.log"
PILOT_DIR = f"{OUT}/pilot_aisles_r"
TIME_LIMIT_H = 14.0
G4B_LIMIT = 0.05
MARGIN_TOL = 0.01
TARGET_REAL = {"fish": 0.02, "electronics": 0.03, "designer": 0.30}
TARGET_SYN = {"thin": 0.02, "fat": 0.30}
CELLS = {"A": AS.CELLS_A, "B": AS.CELLS_B}
cell_name, cell_from, cal_group = AS.cell_name, AS.cell_from, AS.cal_group


def fc_group(c) -> str:
    """The calibration scenario the cell's fixed cost comes from: its profile at t40, ds 0, alpha 0."""
    if c[0] == "A":
        return f"cal|A|{c[1]}|{c[2]}|t40|ds0"
    return "cal|B|ds0"


def target(group: str, cat: str) -> float:
    if group.startswith("cal|A|"):
        return TARGET_SYN[group.split("|")[2]]
    return TARGET_REAL[cat]


def cal_groups(runs) -> list[str]:
    out = []
    for r in runs:
        for c in CELLS[r]:
            for g in (cal_group(c), fc_group(c)):
                if g not in out:
                    out.append(g)
    return out


def cell_config(c, seed: int, cal: dict):
    """The cell as in plan 2026-11-27 (AS._cell_parts), with the fixed cost from change 1 (D3)."""
    P = AS._cell_parts(c)
    g, f = cal[cal_group(c)], cal[fc_group(c)]
    prof = {k: {**{kk: vv for kk, vv in v.items() if kk != "fixed_cost_share"}, "fixed_cost_share": 1.0,
                "baseline_gross_cents": g["baseline"][k], "baseline_gross_by_type_cents": f["fixed_by_type"][k]}
            for k, v in P["prof"].items()}
    ov = [*AS._common(P["t"], P["ds"], P["gamma"], seed), f"categories.profiles={json.dumps(prof)}",
          "sellers.solvency.enabled=true", f"sellers.solvency.start_cash_days={P['cash']!r}"]
    if P["alpha"] > 0:
        ov += [f"market.rent.alpha={P['alpha']!r}", f"market.rent.table={json.dumps(g['rent_table'])}"]
    cfg = load(REF, ov)
    assert cfg.inspectors.detect_scale == P["ds"] and cfg.buyers.profile_shares == AS.SHARES[P["t"]]
    assert cfg.sellers.solvency.enabled and cfg.sellers.solvency.start_cash_days == P["cash"]
    assert float(cfg.market.rent.alpha) == P["alpha"] and cfg.buyers.gamma_by_profile == (P["gamma"] or {})
    return cfg


def sample_stalls(seed: int) -> list[str]:
    """D4: 3 genuine stalls per aisle (fish, electronics, designer), without replacement, from default_rng([seed, 17])."""
    eng = EB.BazaarEngine(load(REF, [f"seed={seed}"]))
    rng = np.random.default_rng([seed, AS.SAMPLE_STREAM])
    out = []
    for c in CATS:
        gen = [st.sid for st in sorted(eng.stalls, key=lambda s: s.idx) if st.stype == "genuine" and st.category == c]
        out += [gen[int(i)] for i in rng.choice(len(gen), PER_AISLE, replace=False)]
    return out


def aisle_of(i: int) -> str:
    return CATS[i // PER_AISLE]


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ worker

_DAYREC: list = []
_INSTALLED = False


def _hooks() -> None:
    """Observer that changes nothing: after each market day, per stall revenue, unit cost, ad spend, units, type,
    in-market flag and overhead; and the day's purchases by (buyer profile, stall, type)."""
    if getattr(EB.BazaarEngine.run, "_aisles_r_seen", False):
        return
    orig = EB.BazaarEngine.run

    def run(self, *a, **k):
        out = orig(self, *a, **k)
        buys: dict = {}
        for b in self.purchases:
            kk = (b["buyer_profile"], b["stall"], b["stype"])
            d = buys.setdefault(kk, [0, 0, 0.0, 0])
            d[0] += b["units"]
            d[1] += b["units"] if b["shortfall"] else 0
            d[2] += float(b["value"])
            d[3] += b["amount_cents"]
        _DAYREC.append({"day": self.day,
                        "stalls": {st.sid: [st.revenue_cents, st.cost_cents, st.ad_spend_cents, st.units_sold, st.stype,
                                            st.exited_day is None or st.exited_day >= self.day, st.overhead_cents]
                                   for st in self.stalls},
                        "buys": [[*kk, *v] for kk, v in sorted(buys.items())]})
        return out

    run._aisles_r_seen = True
    EB.BazaarEngine.run = run


def _install() -> None:
    """Install the two observers once per process (plan 2026-11-27, D4)."""
    global _INSTALLED
    if not _INSTALLED:
        LB._observe()
        _hooks()
        _INSTALLED = True


def _init_worker() -> None:
    """Normal priority: observers only, no renice."""
    _install()


def _copy_state(state: dict) -> dict:
    return {"stalls": copy.deepcopy(state["stalls"]), "book": copy.deepcopy(state["book"]),
            "days": list(state["days"])}


def _stall_agg(eng_stalls) -> tuple[dict, dict, dict]:
    cls = AS.spot_classes(eng_stalls)
    cat = {st.sid: st.category for st in eng_stalls}
    agg: dict = {}
    for d in _DAYREC:
        for s, (rev, cost, ad, units, stype, inm, ovh) in d["stalls"].items():
            a = agg.setdefault(s, {"stype": stype, "revenue": 0, "gross": 0, "ad": 0, "days_in": 0, "units": 0,
                                   "units_dec": 0, "overhead": 0})
            if inm:
                a["revenue"] += rev
                a["gross"] += rev - cost
                a["ad"] += ad
                a["days_in"] += 1
            a["units"] += units
            a["units_dec"] += units if stype == "deceptive" else 0
            a["overhead"] += ovh
            a["stype"] = stype
    harm: dict = {}
    for d in _DAYREC:
        for prof, s, stype, units, short, value, paid in d["buys"]:
            k = f"{prof}|{cat[s]}|{cls[s][1]}|{stype}"
            h = harm.setdefault(k, [0, 0, 0.0, 0])
            h[0] += units
            h[1] += short
            h[2] += value
            h[3] += paid
    return dict(sorted(agg.items())), {s: list(cls[s]) for s in sorted(cls)}, harm


def _exit_reason(out) -> dict:
    insolvent = {s for dd in out["days"] for s in (dd["outcome"].get("solvency") or {}).get("exits", [])}
    return {s: ("insolvency" if s in insolvent else "other") for s in out["liability"]["exited"]}


def _guard_from(out, first: int) -> dict:
    """Guard counts over days first..D of a run (a continuation counts only its own days)."""
    i = first - 1
    return {"stuck_buyers": sum(out["stuck_buyers"]["by_day"][i:]), "idle_choosers": sum(out["idle_choosers"]["by_day"][i:]),
            "parked": int(sum(LB._PARKED)), "buyer_days": sum(d["outcome"]["buyers_arrived"] for d in out["days"][i:]),
            "fallbacks": sum(d["outcome"]["fallbacks"]["buyer"] + d["outcome"]["fallbacks"]["seller"]
                             for d in out["days"][i:])}


def _add_guard(a: dict, b: dict) -> dict:
    return {k: a.get(k, 0) + v for k, v in b.items()}


def never_with_snapshots(cfg):
    """The never chain (no bust-out), run in spans, keeping a copy of its state after day b - 1 for every candidate b."""
    ncfg = benchmark.bust_config(cfg, None, NEVER)
    state = {"stalls": None, "book": None, "days": []}
    snaps, prev = {}, 0
    for b in CANDS:
        if b - 1 > prev:
            DAYS.run_span(ncfg, JsonlLog(keep=False), state, prev + 1, b - 1)
            prev = b - 1
        snaps[b] = _copy_state(state)
    DAYS.run_span(ncfg, JsonlLog(keep=False), state, prev + 1, DAYS_N)
    return DAYS.finish(state), snaps


def continue_bust(cfg, snaps, sid: str, b: int):
    """D1: the bust-out chain (sid busts out on day b) from the never chain's state after day b - 1."""
    st = _copy_state(snaps[b])
    DAYS.run_span(benchmark.bust_config(cfg, sid, b), JsonlLog(keep=False), st, b, DAYS_N)
    return DAYS.finish(st)


def job(j) -> dict:
    """j = (kind, name, seed, extra, cal). kind "cal": a calibration never chain (name = its scenario). kind "bench":
    a cell and seed; the never chain and, for each of the 9 sampled stalls (extra) and each candidate day, the bust-out
    chain (D1). kind "ident": G2e, one stall (extra) of a cell and seed, continued and full chains compared."""
    kind, name, seed, extra, cal = j
    _install()
    t0 = time.time()
    LB._PARKED.clear()
    _DAYREC.clear()
    if kind == "cal":
        cfg = AS.cal_config(name, seed)
        out = EB.run(benchmark.bust_config(cfg, None, NEVER))
        agg, spots, harm = _stall_agg(EB.BazaarEngine(cfg).stalls)
        return {"key": key(j), "kind": kind, "name": name, "seed": seed, "engine_version": ENGINE_VERSION,
                "guard": CR.guard(out), "exited": out["liability"]["exited"], "stall_agg": agg, "spots": spots,
                "ledger_days": len(_DAYREC), "secs": round(time.time() - t0, 2)}
    cfg = cell_config(cell_from(name), seed, cal)
    if kind == "ident":
        sid = extra
        nout, snaps = never_with_snapshots(cfg)
        res = {}
        for b in CANDS:
            c = json.loads(json.dumps(continue_bust(cfg, snaps, sid, b)))
            f = json.loads(json.dumps(EB.run(benchmark.bust_config(cfg, sid, b))))
            res[str(b)] = c == f
        nfull = json.loads(json.dumps(EB.run(benchmark.bust_config(cfg, None, NEVER))))
        res["never"] = json.loads(json.dumps(nout)) == nfull
        return {"key": key(j), "kind": kind, "name": name, "seed": seed, "stall": sid, "identical": res,
                "secs": round(time.time() - t0, 2)}
    watch = list(extra)
    nout, snaps = never_with_snapshots(cfg)
    guard = CR.guard(nout)
    agg, spots, harm = _stall_agg(EB.BazaarEngine(cfg).stalls)
    rec = {"key": key(j), "kind": "bench", "name": name, "seed": seed, "b": str(NEVER), "engine_version": ENGINE_VERSION,
           "watch": watch, "exited": nout["liability"]["exited"], "exit_reason": _exit_reason(nout),
           "stall_agg": agg, "spots": spots, "harm": harm, "ledger_days": len(_DAYREC),
           "never_total": {s: benchmark.stall_total(nout, s) for s in watch},
           "never_revenue": {s: agg[s]["revenue"] for s in watch}, "totals": {}, "busted": {}}
    for s in watch:
        rec["totals"][s], rec["busted"][s] = {}, {}
        for b in CANDS:
            LB._PARKED.clear()
            out = continue_bust(cfg, snaps, s, b)
            rec["totals"][s][str(b)] = benchmark.stall_total(out, s)
            rec["busted"][s][str(b)] = any(x["stall"] == s for dd in out["days"] for x in dd["bust_outs"])
            guard = _add_guard(guard, _guard_from(out, b))
    _DAYREC.clear()
    rec["guard"] = guard
    rec["secs"] = round(time.time() - t0, 2)
    return rec


def key(j) -> str:
    kind, name, seed, extra, cal = j
    if kind == "ident":
        return f"ident|{name}|{seed}|{extra}"
    return f"{kind}|{name}|{seed}"


def bench_jobs(runs, seeds_by_run: dict, cal, samples) -> list[tuple]:
    return [("bench", cell_name(c), sd, tuple(samples[sd]), cal) for r in runs for c in CELLS[r] for sd in seeds_by_run[r]]


def cal_jobs(groups, seeds) -> list[tuple]:
    return [("cal", g, sd, None, None) for g in groups for sd in seeds]


def ident_jobs(runs, cal, samples) -> list[tuple]:
    """G2e: per cell one pilot seed (in turn) and one sampled stall (in turn over the 9)."""
    out, i = [], 0
    for r in runs:
        for c in CELLS[r]:
            sd = PILOT[i % len(PILOT)]
            out.append(("ident", cell_name(c), sd, samples[sd][(i * 4) % len(samples[sd])], cal))
            i += 1
    return out


# ------------------------------------------------------------------ runner (normal priority)

def _load() -> list[float]:
    return [round(x, 2) for x in os.getloadavg()]


def run_chains(a, jobs, cache_path, log, max_secs: float | None = None) -> tuple[list[dict], int, bool]:
    """As aisles_1_3.run_chains (normal priority, memory guard, cache, optional time limit), for this script's jobs."""
    done = {}
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                done[r["key"]] = r
    todo = [j for j in jobs if key(j) not in done]
    log(f"{len(jobs)} jobs, {len(todo)} to run ({len(jobs) - len(todo)} cached); workers {a.workers}; "
        f"load {_load()}; memory {memory_state()}")
    t0, n, pauses, stopped = time.time(), 0, 0, False
    cache = open(cache_path, "a", encoding="utf-8") if cache_path else None
    with ProcessPoolExecutor(a.workers, initializer=_init_worker) as ex:
        it = iter(todo)
        live: set = set()
        exhausted = False
        while live or not exhausted:
            while not exhausted and len(live) < a.workers:
                if max_secs is not None and time.time() - t0 > max_secs:
                    exhausted, stopped = True, True
                    log(f"time limit {max_secs:.0f} s reached: no new jobs; {len(live)} running finish")
                    break
                good, st = LB.memory_ok(a)
                if not good:
                    pauses += 1
                    if not live:
                        log(f"paused (memory {st}); waiting 60 s")
                        time.sleep(60)
                        continue
                    break
                j = next(it, None)
                if j is None:
                    exhausted = True
                    break
                live.add(ex.submit(job, j))
            if not live:
                continue
            fin, live = wait(live, timeout=60, return_when=FIRST_COMPLETED)
            for fu in fin:
                r = fu.result()
                done[r["key"]] = r
                if cache:
                    cache.write(json.dumps(r, separators=(",", ":")) + "\n")
                    cache.flush()
                n += 1
                if n % 10 == 0 or n == len(todo):
                    log(f"{n}/{len(todo)} jobs, {time.time() - t0:.0f} s, load {_load()}, memory {memory_state()}")
    if cache:
        cache.close()
    recs = [done[key(j)] for j in jobs if key(j) in done]
    return recs, pauses, len(recs) == len(jobs) and not stopped


# ------------------------------------------------------------------ calibration

def calibrate(recs: list[dict], groups) -> dict:
    """Per scenario: the genuine baseline gross (start cash, credit), the rent table (as plan 2026-11-27), and per
    (category, type) the sums that set the fixed cost; for the t40 ds 0 scenarios, the fixed cost by type (change 1)."""
    out = {}
    for g in groups:
        rs = [r for r in recs if r["kind"] == "cal" and r["name"] == g]
        num = {c: 0 for c in CATS}
        den = {c: 0 for c in CATS}
        sums = {c: {t: {"revenue": 0, "gross": 0, "ad": 0, "days": 0} for t in TYPES} for c in CATS}
        grp = {}
        for r in rs:
            for s, a in r["stall_agg"].items():
                c, k = r["spots"][s]
                x = sums[c][a["stype"]]
                x["revenue"] += a["revenue"]
                x["gross"] += a["gross"]
                x["ad"] += a["ad"]
                x["days"] += a["days_in"]
                if a["stype"] != "genuine":
                    continue
                num[c] += a["gross"]
                den[c] += a["days_in"]
                y = grp.setdefault((c, k), [0, 0])
                y[0] += a["gross"]
                y[1] += a["days_in"]
        flags = []
        base = {c: round(num[c] / den[c], 2) if den[c] else None for c in CATS}
        adv = {}
        for c in CATS:
            means = {}
            for k in range(4):
                y = grp.get((c, k))
                if y and y[1]:
                    means[k] = y[0] / y[1]
                else:
                    flags.append(f"{g}: no genuine stall-day at ({c}, {k}); advantage set to 0")
            mbar = float(np.mean(list(means.values()))) if means else 0.0
            for k in range(4):
                adv[f"{c}|{k}"] = round(means[k] - mbar, 2) if k in means else 0.0
        spots = rs[0]["spots"] if rs else {}
        table = {s: adv[f"{c}|{k}"] for s, (c, k) in sorted(spots.items())}
        rec = {"baseline": base, "advantage": adv, "rent_table": table, "flags": flags,
               "seeds": sorted({r["seed"] for r in rs}), "sums": sums}
        if g.endswith("|t40|ds0") or g == "cal|B|ds0":
            fixed, floor, pre = {}, [], {}
            for c in CATS:
                m = target(g, c)
                fixed[c], pre[c] = {}, {}
                for t in TYPES:
                    x = sums[c][t]
                    if not x["days"]:
                        fixed[c][t] = 0.0
                        flags.append(f"{g}: no {t} stall-day in {c}; fixed cost 0")
                        continue
                    f = (x["gross"] - x["ad"] - m * x["revenue"]) / x["days"]
                    pre[c][t] = round((x["gross"] - x["ad"]) / x["revenue"], 4) if x["revenue"] else None
                    if f < 0:
                        floor.append(f"{c}|{t}")
                        f = 0.0
                    fixed[c][t] = round(f, 2)
            rec.update({"fixed_by_type": fixed, "floor_binds": floor, "margin_before_fixed": pre,
                        "target": {c: target(g, c) for c in CATS}})
        out[g] = rec
    return out


# ------------------------------------------------------------------ endpoints

def stall_rows(recs, name, seeds) -> dict:
    """{seed: [row per sampled stall, in sample order]}; row: aisle, never, revenue, gain, best, base_units."""
    base_cents = load(REF).pricing.base_price_cents
    out = {}
    for r in recs:
        if r["kind"] != "bench" or r["name"] != name or r["seed"] not in seeds:
            continue
        rows = []
        for i, s in enumerate(r["watch"]):
            tot = {NEVER: r["never_total"][s], **{int(b): v for b, v in r["totals"][s].items()}}
            G = benchmark.gain(tot)
            a = aisle_of(i)
            rows.append({"stall": s, "aisle": a, "never": G["never"], "revenue": r["never_revenue"][s],
                         "gain": G["gain_unfloored"], "best": G["best_day"],
                         "base_units": G["gain_unfloored"] / base_cents[a]})
        out[r["seed"]] = rows
    return out


def per_seed(R, seeds, measure: str, aisle=None) -> list:
    """Per seed over the sampled stalls (all 9, or an aisle's 3):
    revenue: sum(gain) / sum(revenue) (primary); profit: sum(gain) / sum(never) if > 0 (D5 ratio);
    stall_ratio: mean of gain / revenue; base_units: mean of gain / base price."""
    vals = []
    for sd in seeds:
        rows = [x for x in R.get(sd, []) if aisle is None or x["aisle"] == aisle]
        if not rows:
            vals.append(None)
            continue
        g = sum(x["gain"] for x in rows)
        if measure == "revenue":
            den = sum(x["revenue"] for x in rows)
            vals.append(g / den if den > 0 else None)
        elif measure == "profit":
            den = sum(x["never"] for x in rows)
            vals.append(g / den if den > 0 else None)
        elif measure == "stall_ratio":
            xs = [x["gain"] / x["revenue"] for x in rows if x["revenue"] > 0]
            vals.append(float(np.mean(xs)) if xs else None)
        else:
            vals.append(float(np.mean([x["base_units"] for x in rows])))
    return vals


MEASURES = ("revenue", "base_units", "stall_ratio", "profit")


def predictions(run: str, P) -> dict:
    """P(cell name, aisle=None) -> per-seed list. Returns the predictions with stat and verdict."""
    d, V = AS.diff, AS.verdict
    pr = {}
    if run == "A":
        for m in AS.MARGIN:
            st = d(P(f"A|{m}|easy|t40|ds0"), P(f"A|{m}|hard|t40|ds0"))
            pr[f"PA1r|{m}"] = {"what": f"t40 ds0 {m}: hard - easy", "stat": st, "verdict": V(st, +1)}
        for v in AS.VERIF:
            st = d(P(f"A|fat|{v}|t40|ds0"), P(f"A|thin|{v}|t40|ds0"))
            pr[f"PA2r|{v}"] = {"what": f"t40 ds0 {v}: thin - fat", "stat": st, "verdict": V(st, +1)}
        for m in AS.MARGIN:
            for v in AS.VERIF:
                st = mean_ci(P(f"A|{m}|{v}|t40|ds1"))
                pr[f"PA3r|{m}|{v}"] = {"what": f"t40 ds1 {m} {v}: gain", "stat": st, "verdict": V(st, -1)}
        q = [P(f"A|{x}|t40|ds0") for x in ("fat|easy", "fat|hard", "thin|easy", "thin|hard")]
        inter = [None if None in t else (t[3] - t[2]) - (t[1] - t[0]) for t in zip(*q)]
        pr["PA4r|interaction|t40"] = {"what": "(thin hard - thin easy) - (fat hard - fat easy), t40 ds0",
                                      "stat": mean_ci(inter), "verdict": "exploratory"}
        for m in AS.MARGIN:
            pr[f"PA4r|t100|PA1|{m}"] = {"what": f"t100 ds0 {m}: hard - easy", "verdict": "exploratory",
                                        "stat": d(P(f"A|{m}|easy|t100|ds0"), P(f"A|{m}|hard|t100|ds0"))}
        for v in AS.VERIF:
            pr[f"PA4r|t100|PA2|{v}"] = {"what": f"t100 ds0 {v}: thin - fat", "verdict": "exploratory",
                                        "stat": d(P(f"A|fat|{v}|t100|ds0"), P(f"A|thin|{v}|t100|ds0"))}
        for m in AS.MARGIN:
            for v in AS.VERIF:
                pr[f"PA4r|t100|PA3|{m}|{v}"] = {"what": f"t100 ds1 {m} {v}: gain", "verdict": "exploratory",
                                                "stat": mean_ci(P(f"A|{m}|{v}|t100|ds1"))}
        for k in ("PA1r", "PA2r", "PA3r"):
            vs = [x["verdict"] for kk, x in pr.items() if kk.startswith(k + "|")]
            pr[k] = {"verdict": "supported" if all(x == "supported" for x in vs) else
                     ("partly supported" if any(x == "supported" for x in vs) else
                      ("contradicted" if all(x == "contradicted" for x in vs) else "not supported")), "parts": vs}
    else:
        st = d(P("B|cash20|a0|ds0"), P("B|cash2|a0|ds0"))
        pr["PB1r"] = {"what": "ds0 a0: cash 2 - cash 20, pooled", "stat": st, "verdict": V(st, +1)}
        st = d(P("B|cash20|a0|ds0", "fish"), P("B|cash20|a0|ds0", "designer"))
        pr["PB2r"] = {"what": "ds0 cash20 a0: designer - fish", "stat": st, "verdict": V(st, +1)}
        for aisle in CATS:
            pr[f"PB3r|cash|{aisle}"] = {"what": f"ds0 a0 {aisle}: cash 2 - cash 20", "verdict": "exploratory",
                                        "stat": d(P("B|cash20|a0|ds0", aisle), P("B|cash2|a0|ds0", aisle))}
        for cash in ("2", "20"):
            pr[f"PB3r|alpha|cash{cash}"] = {"what": f"ds0 cash {cash}: alpha 1 - alpha 0", "verdict": "exploratory",
                                            "stat": d(P(f"B|cash{cash}|a0|ds0"), P(f"B|cash{cash}|a1|ds0"))}
        pr["PB3r|ds1|PB1"] = {"what": "ds1 a0: cash 2 - cash 20", "verdict": "exploratory",
                              "stat": d(P("B|cash20|a0|ds1"), P("B|cash2|a0|ds1"))}
        pr["PB3r|ds1|PB2"] = {"what": "ds1 cash20 a0: designer - fish", "verdict": "exploratory",
                              "stat": d(P("B|cash20|a0|ds1", "fish"), P("B|cash20|a0|ds1", "designer"))}
    return pr


def net_margins(recs, names, seeds) -> dict:
    """Realised net margin (revenue - unit cost - ad - overhead) / revenue by category and type, ratio of sums over
    stall-days in the market, in the never chains of the named cells."""
    out = {}
    for n in names:
        s = {c: {t: [0, 0] for t in TYPES} for c in CATS}
        for r in recs:
            if r["kind"] != "bench" or r["name"] != n or r["seed"] not in seeds:
                continue
            for sid, a in r["stall_agg"].items():
                c = r["spots"][sid][0]
                x = s[c][a["stype"]]
                x[0] += a["gross"] - a["ad"] - a["overhead"]
                x[1] += a["revenue"]
        out[n] = {c: {t: (round(v[0] / v[1], 4) if v[1] else None) for t, v in s[c].items()} for c in CATS}
    return out


def confirmatory_cells(run: str) -> list[str]:
    if run == "A":
        return [f"A|{m}|{v}|t40|ds{d}" for m in AS.MARGIN for v in AS.VERIF for d in (0, 1)]
    return [f"B|cash{c}|a0|ds0" for c in (2, 20)]


def analyse(recs, runs, seeds_by_run) -> dict:
    res = {}
    for run in runs:
        seeds = seeds_by_run[run]
        rs = [x for x in recs if x["kind"] == "bench" and x["name"].startswith(run + "|") and x["seed"] in seeds]
        out = {"seeds": seeds, "jobs": len(rs), "cells": {}, "predictions": {},
               "guard": {k: sum(x["guard"][k] for x in rs) for k in ("stuck_buyers", "idle_choosers", "parked",
                                                                      "fallbacks", "buyer_days")}}
        Rs = {}
        for c in CELLS[run]:
            n = cell_name(c)
            R = stall_rows(recs, n, seeds)
            Rs[n] = R
            cell = {"exits": AS.exits_summary(recs, n, seeds), "best_day": {},
                    "never_le0": {"pooled": sum(x["never"] <= 0 for sd in R for x in R[sd]),
                                  **{a: sum(x["never"] <= 0 for sd in R for x in R[sd] if x["aisle"] == a) for a in CATS}},
                    "revenue_le0": sum(x["revenue"] <= 0 for sd in R for x in R[sd]),
                    "stall_seeds": sum(len(R[sd]) for sd in R),
                    "busted_share": None}
            for meas in MEASURES:
                cell[meas] = {"pooled": mean_ci(per_seed(R, seeds, meas)),
                              **{a: mean_ci(per_seed(R, seeds, meas, a)) for a in CATS}}
            cell["per_seed_revenue"] = per_seed(R, seeds, "revenue")
            cell["per_seed_revenue_by_aisle"] = {a: per_seed(R, seeds, "revenue", a) for a in CATS}
            cell["never_dollars"] = {a: mean_ci([float(np.mean([x["never"] / 100 for x in R[sd] if x["aisle"] == a]))
                                                 for sd in seeds if sd in R]) for a in CATS}
            cell["revenue_dollars"] = {a: mean_ci([float(np.mean([x["revenue"] / 100 for x in R[sd] if x["aisle"] == a]))
                                                   for sd in seeds if sd in R]) for a in CATS}
            for sd in R:
                for x in R[sd]:
                    cell["best_day"][str(x["best"])] = cell["best_day"].get(str(x["best"]), 0) + 1
            out["cells"][n] = cell
        prim = predictions(run, lambda n, aisle=None: per_seed(Rs[n], seeds, "revenue", aisle))
        for meas in MEASURES[1:]:
            sec = predictions(run, lambda n, aisle=None, _m=meas: per_seed(Rs[n], seeds, _m, aisle))
            for k, v in prim.items():
                v.setdefault("secondary", {})[meas] = {kk: sec[k][kk] for kk in ("stat", "verdict", "parts")
                                                       if kk in sec[k]}
        out["predictions"] = prim
        out["realised_net_margin"] = net_margins(recs, [cell_name(c) for c in CELLS[run]], seeds)
        out["G6_main"] = {n: out["cells"][n]["revenue_le0"] for n in confirmatory_cells(run)}
        res[run] = out
    return res


# ------------------------------------------------------------------ gates

def g2_costs(cal) -> dict:
    bad = []
    for r in "AB":
        for c in CELLS[r]:
            cfg = cell_config(c, PILOT[0], cal)
            for cat in CATS:
                p = CAT.profile(cfg, cat)
                qh, ql = sum(cfg.stalls.q_high) / 2, sum(cfg.stalls.q_low) / 2
                g = p["cost_share"] * CAT.genuine_price_at_top(cfg, cat)
                if abs(CAT.unit_cost(cfg, cat, qh) - g) > 0.5 or \
                        abs(CAT.unit_cost(cfg, cat, ql) - p["cheap_share"] * g) > 0.5:
                    bad.append(f"{cell_name(c)} {cat}")
                gs = p["seconds_cost_share"] * CAT.seconds_price_at_top(cfg, cat)
                if abs(CAT.unit_cost(cfg, cat, ql, "seconds") - gs) > 0.5:
                    bad.append(f"{cell_name(c)} {cat} seconds")
                f = cal[fc_group(c)]["fixed_by_type"][cat]
                for t in TYPES:
                    if CAT.fixed_cost(cfg, cat, t) != CAT._half_up(max(0.0, f[t])):
                        bad.append(f"{cell_name(c)} {cat} fixed {t}")
    return {"bad": bad, "pass": not bad}


def g2_margin(recs, cal) -> dict:
    names = [f"A|{m}|{v}|t40|ds0" for m in AS.MARGIN for v in AS.VERIF] + ["B|cash20|a0|ds0"]
    nm = net_margins(recs, names, PILOT)
    rows, ok = {}, True
    for n in names:
        g = cal[fc_group(cell_from(n))]
        for c in CATS:
            got, want = nm[n][c]["genuine"], g["target"][c]
            binds = f"{c}|genuine" in g["floor_binds"]
            good = got is not None and (abs(got - want) <= MARGIN_TOL or binds)
            rows[f"{n}|{c}"] = {"realised": got, "target": want, "floor_binds": binds, "pass": good}
            ok &= good
    return {"rows": rows, "all_types": nm, "tolerance": MARGIN_TOL, "pass": ok}


# ------------------------------------------------------------------ main

def run_record(a, phase) -> dict:
    dirty = subprocess.run(["git", "status", "--porcelain", "engine", "analysis", "agents"], capture_output=True,
                           text=True).stdout.strip()
    return {"engine": ENGINE_VERSION, "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                                               capture_output=True, text=True).stdout.strip(),
            "code_dirty": bool(dirty), "script_sha256": _script_sha(), "numpy": np.__version__,
            "python": platform.python_version(), "platform": platform.platform(), "phase": phase,
            "command": " ".join(sys.argv), "tests": a.tests, "workers": a.workers,
            "started": time.strftime("%Y-%m-%d %H:%M:%S")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["pilot", "run", "analyse"], required=True)
    ap.add_argument("--runs", default="A,B")
    ap.add_argument("--workers", type=int, default=7)
    ap.add_argument("--min-swap-mb", type=float, default=0.0)
    ap.add_argument("--min-free-pct", type=float, default=10.0)
    ap.add_argument("--max-secs", type=float, default=None)
    ap.add_argument("--seeds-per-run", type=int, default=20, help="20, or 15 if G3 cut")
    ap.add_argument("--tests", default="")
    a = ap.parse_args()
    runs = [r for r in a.runs.split(",") if r]
    seeds = {r: SEEDS[r][:a.seeds_per_run] for r in runs}
    if a.phase == "pilot":
        os.makedirs(PILOT_DIR, exist_ok=True)
        log = CR.file_logger(f"{PILOT_DIR}/aisles_r_run.log")
        log(f"run record {json.dumps(run_record(a, 'pilot'), sort_keys=True)}")
        t0 = time.time()
        groups = cal_groups(runs)
        cache = f"{PILOT_DIR}/aisles_r_pilot_cache.jsonl"
        crec, p1, ok1 = run_chains(a, cal_jobs(groups, CAL_SEEDS), cache, log)
        cal = calibrate(crec, groups)
        cal_again = calibrate(json.loads(json.dumps(crec)), groups)
        with open(CAL_FILE, "w", encoding="utf-8") as f:
            json.dump({"made": time.strftime("%Y-%m-%d %H:%M:%S"), "seeds": CAL_SEEDS, "groups": cal}, f, indent=1,
                      sort_keys=True)
        log(f"calibration: {len(groups)} scenarios on seeds {CAL_SEEDS}, written to {CAL_FILE}; floor binds "
            f"{ {g: v['floor_binds'] for g, v in cal.items() if v.get('floor_binds')} }; flags "
            f"{sum(len(v['flags']) for v in cal.values())}")
        j0 = cal_jobs(groups[:1], CAL_SEEDS[:1])[0]
        _install()
        again = job(j0)
        first = next(r for r in crec if r["key"] == key(j0))
        same = {k: again[k] == first[k] for k in ("stall_agg", "spots", "exited")}
        samples = {sd: sample_stalls(sd) for sd in PILOT}
        bj = bench_jobs(runs, {r: PILOT for r in runs}, cal, samples)
        tb = time.time()
        brec, p2, ok2 = run_chains(a, bj, cache, log)
        wall_b = time.time() - tb
        irec, p3, ok3 = run_chains(a, ident_jobs(runs, cal, samples), cache, log)
        n_main = sum(len(CELLS[r]) * len(SEEDS[r]) for r in runs)
        n_cut = sum(len(CELLS[r]) * SEEDS_CUT for r in runs)
        proj_h = wall_b * n_main / max(len(bj), 1) / 3600
        proj_cut_h = wall_b * n_cut / max(len(bj), 1) / 3600
        allrec = crec + brec
        guard = {k: sum(r["guard"][k] for r in allrec) for k in ("stuck_buyers", "idle_choosers", "parked",
                                                                  "fallbacks", "buyer_days")}
        g4 = {cell_name(c): AS.exits_summary(brec, cell_name(c), PILOT) for r in runs for c in CELLS[r]}
        rev0 = {}
        for r in runs:
            for n in confirmatory_cells(r):
                R = stall_rows(brec, n, PILOT)
                rev0[n] = sum(x["revenue"] <= 0 for sd in R for x in R[sd])
        ident = {r["key"]: r["identical"] for r in irec}
        gates = {
            "G1": {"pass": ok1 and ok2 and ok3 and len(brec) == len(bj), "cal_chains": len(crec), "bench_jobs": len(brec),
                   "ident_jobs": len(irec)},
            "G2a": AS.g2_defaults_reproduce(log),
            "G2b": g2_costs(cal),
            "G2c": {"rerun_identical": same, "recalc_identical": cal == cal_again,
                    "pass": all(same.values()) and cal == cal_again},
            "G2e": {"chains": ident, "compared": sum(len(v) for v in ident.values()),
                    "pass": bool(ident) and all(all(v.values()) for v in ident.values())},
            "G2m": g2_margin(brec, cal),
            "G3": {"projected_h": round(proj_h, 2), "projected_h_15_seeds": round(proj_cut_h, 2),
                   "limit_h": TIME_LIMIT_H, "pass": proj_h <= TIME_LIMIT_H, "main_jobs": n_main,
                   "pilot_bench_jobs": len(bj), "pilot_bench_wall_s": round(wall_b, 1),
                   "job_cpu_s_mean": round(float(np.mean([r["secs"] for r in brec])), 2) if brec else None},
            "G4_reported": {"max_share_before_day10": max(v["share_before_day10"] or 0 for v in g4.values()),
                            "cells": g4},
            "G4b": {"genuine_share_before10": {n: v["by_type_reason"]["genuine"]["share_before10"] for n, v in g4.items()},
                    "limit": G4B_LIMIT,
                    "pass": all((v["by_type_reason"]["genuine"]["share_before10"] or 0) <= G4B_LIMIT
                                for v in g4.values())},
            "G5": {"guard": guard, "pass": not (guard["stuck_buyers"] or guard["idle_choosers"] or guard["parked"]
                                                or guard["fallbacks"])},
            "G6": {"revenue_le0_by_cell": rev0, "pass": not any(rev0.values())},
            "samples": samples, "calibration_flags": {g: v["flags"] for g, v in cal.items() if v["flags"]},
            "floor_binds": {g: v["floor_binds"] for g, v in cal.items() if v.get("floor_binds")},
            "wall_s": round(time.time() - t0, 1), "memory_pauses": p1 + p2 + p3,
        }
        gates["all_pass_except_G3"] = all(gates[g]["pass"] for g in ("G1", "G2a", "G2b", "G2c", "G2e", "G2m", "G4b",
                                                                     "G5", "G6"))
        with open(f"{PILOT_DIR}/aisles_r_pilot_gates.json", "w", encoding="utf-8") as f:
            json.dump(gates, f, indent=1, sort_keys=True, default=str)
        log("pilot: " + ", ".join(f"{g} {gates[g]['pass']}" for g in ("G1", "G2a", "G2b", "G2c", "G2e", "G2m", "G3",
                                                                       "G4b", "G5", "G6"))
            + f"; G3 {proj_h:.2f} h (15 seeds {proj_cut_h:.2f} h, limit {TIME_LIMIT_H}); all pass except G3: "
              f"{gates['all_pass_except_G3']}")
    elif a.phase == "run":
        log = CR.file_logger(RUN_LOG)
        log(f"run record {json.dumps(run_record(a, 'run ' + ','.join(runs)), sort_keys=True)}")
        cal = json.load(open(CAL_FILE, encoding="utf-8"))["groups"]
        samples = {sd: sample_stalls(sd) for r in runs for sd in seeds[r]}
        recs, pauses, complete = run_chains(a, bench_jobs(runs, seeds, cal, samples), CACHE, log, a.max_secs)
        log(f"run {','.join(runs)}: {len(recs)} jobs done, complete {complete}, memory pauses {pauses}")
    else:
        log = CR.file_logger(RUN_LOG)
        recs = {}
        with open(CACHE, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                recs[r["key"]] = r
        recs = list(recs.values())
        log(f"analyse {','.join(runs)}: {len(recs)} jobs in the cache; seeds {seeds}")
        res = analyse(recs, runs, seeds)
        for r in runs:
            res[r]["script_sha256"] = _script_sha()
            with open(f"{OUT}/aisles_r_{r}.json", "w", encoding="utf-8") as f:
                json.dump(res[r], f, indent=1, sort_keys=True, default=str)
        log("analysis written: " + ", ".join(f"{OUT}/aisles_r_{r}.json" for r in runs))


if __name__ == "__main__":
    main()
