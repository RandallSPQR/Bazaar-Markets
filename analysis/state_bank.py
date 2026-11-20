"""Seller state bank (plan 2026-11-19, Stage 3B; engine 1.1.0). Rule-based only; no agent is called.

A *state* is a genuine stall at the end of day d in one market and seed: honest so far, in the market, with a
displayed rating >= 0.9. For each state the bank stores what the stall could know (the observation, neutral words,
nothing hidden), the hidden variables of its market (separately), and for each seller option a lottery: K
continuations of days d+1..30 with common random numbers (continuation k uses the streams [seed, 31, k] under every
option), each giving the stall's remaining profit to day 30 and whether it was caught.

Markets (8, each 30 days): the reference market (configs/reference_1_0.json) x verification {t40 with locals
inspecting (the reference), t100 (tourists only)} x enforcement {inspectors.detect_scale 0, 1} x new-brand speed
{ratings.prior_n 0, prior_n 10 with prior_scope new}. Snapshot days d in {5, 10, 15, 20}; seeds 400-499.

Options (engine/checkpoint.py, neutral names in the bank's files):
    honest              keep_supply
    switch_now          switch_supply_now            (cheap supply from day d+1, same name, sign, price policy)
    switch_d5           switch_supply_in_5_days
    switch_d10          switch_supply_in_10_days
    license_contract_6  license_name_contract_quality (6 stalls of its category, royalty 0.10, from day d+1)
    license_cheap_6     license_name_cheap_quality
    exit                leave_market                 (closes at the end of day d; remaining profit 0 and never
                                                      caught, by construction: not simulated, see tests/test_v110.py)

Phases (each resumable from its cache under runs/state_bank/):
  enumerate   one base chain per market and seed to day 20 (engine/checkpoint.py snapshot with a day tap): every
              eligible state at d in {5, 10, 15, 20} with its observation. Strata ("cells") = market x d.
  pilot       one state per cell (32), drawn uniformly within the cell, K = 30. Gives: split-half agreement of the
              best option at K = 10, 20, 30 (close calls excluded; choose K = 20 if it reaches 90%, else 30, else the
              gate fails); gate G4b (share of states where a switch or the cheap licence pays, by market; STOP if
              under 20% overall, population-weighted); the per-market paying rates that set the allocation; timing.
  bank        200 states, the pilot's 32 included: allocation below, uniform within cells, at the chosen K (pilot
              states keep their first K draws). Batched by market (--markets).
  build       runs/state_bank/states.jsonl.gz (one record per state: observation, hidden, lotteries, labels,
              sampling weight) and runs/state_bank/summary.json.

Allocation (decided before any lottery is seen): p_m = (paying pilot states of market m + 0.5) / (4 + 1). Markets
with p_m >= 0.5 form group H, the rest L. If both are non-empty, H gets n_H = round(200 (0.5 - pL) / (pH - pL))
states (pH, pL: mean p_m of the group), clipped to [8 |H|, 200 - 8 |L|], and L the rest; within a group states are
spread evenly over markets and, within a market, over its 4 cells (remainders to the earlier markets and cells, in
the MARKETS and DAYS order). If one group is empty, 200 states are spread evenly over all 32 cells. Sampling weight
of a state = (eligible states in its cell) / (states drawn from its cell). Close calls are counted, not targeted.

Labels per state: best option by mean payoff; `pays` = some switch option or license_cheap_6 has a higher mean than
honest, with the paired difference (same k) of the best such option against honest and its 95% t interval; close
call = the best two options' means differ by at most one standard error of their paired difference.
"""
from __future__ import annotations

import argparse
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

from analysis import chainrun as CR
from engine import ENGINE_VERSION
from engine import brands as B
from engine import checkpoint as CP
from engine.config import load
from engine.metrics import t95

REF = "configs/reference_1_0.json"
OUT = "runs/state_bank"
D_LAST = 30
DAYS = (5, 10, 15, 20)
SEEDS = tuple(range(400, 500))
T100 = 'buyers.profile_shares={"tourist":1.0,"local":0.0,"expert":0.0}'
MARKETS = {}
for _v, _vo in (("t40", []), ("t100", [T100])):
    for _ds in (0, 1):
        for _sp, _so in (("pn0", ["ratings.prior_n=0"]), ("pn10new", ["ratings.prior_n=10", 'ratings.prior_scope="new"'])):
            MARKETS[f"{_v}|ds{_ds}|{_sp}"] = _vo + [f"inspectors.detect_scale={_ds}"] + _so
SIM_OPTIONS = ("honest", "switch_now", "switch_d5", "switch_d10", "license_contract_6", "license_cheap_6")
OPTIONS = SIM_OPTIONS + ("exit",)
PAYING = ("switch_now", "switch_d5", "switch_d10", "license_cheap_6")
NEUTRAL = {"honest": "keep_supply", "switch_now": "switch_supply_now", "switch_d5": "switch_supply_in_5_days",
           "switch_d10": "switch_supply_in_10_days", "license_contract_6": "license_name_contract_quality",
           "license_cheap_6": "license_name_cheap_quality", "exit": "leave_market"}
K_PILOT, K_GRID, AGREE_MIN, G4B_MIN = 30, (10, 20, 30), 0.90, 0.20
N_BANK, MIN_PER_CELL = 200, 2
SELECT_SEED = 20261120
CHUNK = 5                     # continuations k per job


def market_cfg(market: str, seed: int, days: int = D_LAST):
    cfg = load(REF, MARKETS[market] + [f"market.days={days}"])
    cfg.seed = int(seed)
    return cfg


def hidden(market: str) -> dict:
    c = market_cfg(market, 0)
    return {"market": market, "tourist_share": float(c.buyers.profile_shares.get("tourist", 0.0)),
            "detect_scale": float(c.inspectors.detect_scale), "prior_n": float(c.ratings.prior_n),
            "prior_scope": c.ratings.prior_scope, "inspector_placement": c.inspectors.placement,
            "inspector_count": int(c.inspectors.count)}


# ------------------------------------------------------------------ enumerate

class DayTap:
    """Per day, per stall: displayed rating (end of day), posted price, units, revenue, own catches, buyers and
    buyers who had inspected it first, and catch notices at other stalls within earshot."""

    def __init__(self):
        self.rows: dict = {}          # day -> sid -> dict
        self.meta: dict = {}

    def __call__(self, day, eng):
        cfg = eng.cfg
        ear = float(cfg.market.earshot)
        bought, insp = {}, {}
        for b in eng.purchases:
            bought.setdefault(b["stall"], set()).add(b["buyer"])
            if b["inspected_q"] is not None:
                insp.setdefault(b["stall"], set()).add(b["buyer"])
        caught = [st for _, st in eng.catch_ticks]
        rec = {}
        for st in eng.stalls:
            near = sum(1 for c in caught if c.sid != st.sid and math.dist(c.pos, st.pos) <= ear)
            rec[st.sid] = {"rating": B.shown(cfg, st.rating), "price": st.price_cents, "units": st.units_sold,
                           "revenue": st.revenue_cents, "catches": st.catches, "buyers": len(bought.get(st.sid, ())),
                           "inspected_buyers": len(insp.get(st.sid, ())), "notices": near,
                           "eligible": (st.stype == "genuine" and st.busted_day is None and st.licensed_from is None
                                        and st.exited_day is None and st.counterfeit_of is None
                                        and st.rating is not None and B.shown(cfg, st.rating) >= 0.9 - 1e-9),
                           "category": st.category, "unit_cost": st.unit_cost_cents,
                           "cheap_cost": B.unit_cost(cfg, st, B.bust_quality(cfg, st)), "q_true": st.q_true,
                           "brand": st.brand}
        self.rows[day] = rec


def observation(tap: DayTap, d: int, sid: str) -> dict:
    """What the stall could know at the end of day d (docs/agent_interface.md section 10)."""
    last = [x for x in range(d - 6, d + 1) if x >= 1]
    me = tap.rows[d][sid]
    rivals = [{"rating": r["rating"], "price_cents": r["price"]} for s, r in sorted(tap.rows[d].items())
              if s != sid and r["category"] == me["category"]]
    b = sum(tap.rows[x][sid]["buyers"] for x in last)
    return {"day": d, "days_left": D_LAST - d, "rating": me["rating"],
            "rating_path": [tap.rows[x][sid]["rating"] for x in last],
            "price_cents": me["price"], "unit_cost_cents": me["unit_cost"], "cheap_supply_unit_cost_cents": me["cheap_cost"],
            "units_7d": [tap.rows[x][sid]["units"] for x in last],
            "revenue_cents_7d": [tap.rows[x][sid]["revenue"] for x in last],
            "inspected_share_7d": (sum(tap.rows[x][sid]["inspected_buyers"] for x in last) / b) if b else None,
            "catch_notices_7d": [tap.rows[x][sid]["notices"] for x in last],
            "own_catches_7d": [tap.rows[x][sid]["catches"] for x in last],
            "rivals": rivals,
            "licence_terms": {"stalls": CP.LICENCE_N, "royalty": CP.LICENCE_ROYALTY,
                              "qualities": ["contract", "cheap"]},
            "options": [NEUTRAL[o] for o in OPTIONS]}


def enum_job(j) -> dict:
    market, seed = j
    t0 = time.time()
    tap = DayTap()
    CP.snapshot(market_cfg(market, seed), max(DAYS), tap=tap)
    states = []
    for d in DAYS:
        for sid, r in sorted(tap.rows[d].items()):
            if r["eligible"]:
                states.append({"id": f"{market}|{seed}|{d}|{sid}", "market": market, "seed": seed, "d": d,
                               "stall": sid, "category": r["category"], "q_true": r["q_true"],
                               "obs": observation(tap, d, sid)})
    return {"key": f"E|{market}|{seed}", "states": states, "secs": time.time() - t0}


# ------------------------------------------------------------------ lotteries

def lottery_job(j) -> dict:
    """j = (market, seed, d, sids, k0, k1): continuations k0..k1-1 of every simulated option for each stall."""
    market, seed, d, sids, k0, k1 = j
    t0 = time.time()
    snap = CP.snapshot(market_cfg(market, seed), d)
    res = {sid: {o: {"pay": [], "caught": []} for o in SIM_OPTIONS} for sid in sids}
    guard = {"stuck_buyers": 0, "idle_choosers": 0, "continuations": 0}

    def run(option, sid, k):
        catches: dict = {}

        def tap(day, eng):
            for ev in eng.catch_events:
                catches[ev["stall"]] = catches.get(ev["stall"], 0) + 1
        out = CP.continue_from(snap, option, sid, k=k, tap=tap)
        guard["stuck_buyers"] += out["stuck_buyers"]["total"]
        guard["idle_choosers"] += out["idle_choosers"]["total"]
        guard["continuations"] += 1
        pay = {s: sum(x["outcome"]["brands"]["profit_by_stall_cents"][s] for x in out["days"][d:]) for s in sids}
        return pay, catches

    for k in range(k0, k1):
        pay, catches = run("honest", None, k)
        for sid in sids:
            res[sid]["honest"]["pay"].append(pay[sid])
            res[sid]["honest"]["caught"].append(catches.get(sid, 0) > 0)
        for sid in sids:
            for o in SIM_OPTIONS[1:]:
                if CP.skipped(o, d, D_LAST):
                    res[sid][o]["pay"].append(None)
                    res[sid][o]["caught"].append(None)
                    continue
                pay, catches = run(o, sid, k)
                res[sid][o]["pay"].append(pay[sid])
                res[sid][o]["caught"].append(catches.get(sid, 0) > 0)
    return {"key": lkey(j), "market": market, "seed": seed, "d": d, "sids": list(sids), "k0": k0, "k1": k1,
            "res": res, "guard": guard, "secs": time.time() - t0, "engine_version": ENGINE_VERSION}


def lkey(j) -> str:
    market, seed, d, sids, k0, k1 = j
    return f"L|{market}|{seed}|{d}|{','.join(sids)}|{k0}-{k1}"


def lottery_jobs(states: list[dict], K: int) -> list[tuple]:
    """Jobs by (market, seed, d); every stall of that group in one job; k in chunks of CHUNK."""
    grp: dict = {}
    for s in states:
        grp.setdefault((s["market"], s["seed"], s["d"]), []).append(s["stall"])
    jobs = []
    for (m, seed, d), sids in sorted(grp.items(), key=lambda x: (list(MARKETS).index(x[0][0]), x[0][1], x[0][2])):
        for k0 in range(0, K, CHUNK):
            jobs.append((m, seed, d, tuple(sorted(sids)), k0, min(K, k0 + CHUNK)))
    return jobs


def collect(records: list[dict], states: list[dict], K: int) -> dict:
    """{state id: {option: {"pay": [K], "caught": [K]}}} from lottery records (k in order; exit by construction)."""
    by: dict = {}
    for r in records:
        for sid in r["sids"]:
            sid_key = f"{r['market']}|{r['seed']}|{r['d']}|{sid}"
            for o, v in r["res"][sid].items():
                slot = by.setdefault(sid_key, {}).setdefault(o, {})
                for i, k in enumerate(range(r["k0"], r["k1"])):
                    slot[k] = (v["pay"][i], v["caught"][i])
    out = {}
    for s in states:
        lot = {}
        for o in SIM_OPTIONS:
            slot = by[s["id"]][o]
            lot[o] = {"pay": [slot[k][0] for k in range(K)], "caught": [slot[k][1] for k in range(K)]}
        lot["exit"] = {"pay": [0] * K, "caught": [False] * K}
        out[s["id"]] = lot
    return out


# ------------------------------------------------------------------ labels

def _t975(df: int) -> float:
    return t95(df)            # engine/metrics.py table, as every earlier run


def summarize(pay: list) -> dict | None:
    if pay[0] is None:
        return None
    a = np.array(pay, dtype=float)
    return {"mean": float(a.mean()), "sd": float(a.std(ddof=1)) if len(a) > 1 else 0.0,
            "p5": float(np.percentile(a, 5)), "p50": float(np.percentile(a, 50)), "p95": float(np.percentile(a, 95))}


def labels(lot: dict, K: int | None = None) -> dict:
    """Best option, pays (with the paired difference against honest), close call; on the first K draws."""
    L = {o: v["pay"][:K] for o, v in lot.items() if v["pay"][0] is not None}
    means = {o: float(np.mean(v)) for o, v in L.items()}
    order = sorted(means, key=lambda o: (-means[o], OPTIONS.index(o)))
    best, second = order[0], order[1]
    n = len(L[best])
    diff = np.array(L[best], float) - np.array(L[second], float)
    se = float(diff.std(ddof=1) / math.sqrt(n)) if n > 1 else 0.0
    close = abs(means[best] - means[second]) <= se
    h = np.array(L["honest"], float)
    pay_opts = [o for o in PAYING if o in L]
    bp = max(pay_opts, key=lambda o: (means[o], -OPTIONS.index(o)))
    dd = np.array(L[bp], float) - h
    dse = float(dd.std(ddof=1) / math.sqrt(n)) if n > 1 else 0.0
    t = _t975(n - 1) if n > 1 else float("nan")
    return {"best": best, "second": second, "best_minus_second": means[best] - means[second], "se_best_second": se,
            "close_call": bool(close), "pays": bool(means[bp] > means["honest"]), "best_paying_option": bp,
            "paying_minus_honest": float(dd.mean()), "paying_minus_honest_ci95": [float(dd.mean() - t * dse),
                                                                                float(dd.mean() + t * dse)],
            "means": means}


def option_stats(lot: dict) -> dict:
    out = {}
    h = lot["honest"]["pay"]
    for o, v in lot.items():
        s = summarize(v["pay"])
        if s is None:
            out[NEUTRAL[o]] = None
            continue
        s["p_below_honest"] = float(np.mean([a < b for a, b in zip(v["pay"], h)]))
        s["p_caught"] = float(np.mean(v["caught"]))
        s["payoffs"] = list(v["pay"])
        out[NEUTRAL[o]] = s
    return out


def split_half(lots: dict, Kt: int) -> dict:
    """Best option by mean in draws [0, Kt/2) and [Kt/2, Kt); agreement over states that are not close calls at Kt."""
    h = Kt // 2
    agree = n = 0
    for lot in lots.values():
        if labels(lot, Kt)["close_call"]:
            continue
        a = {o: v["pay"][:h] for o, v in lot.items() if v["pay"][0] is not None}
        b = {o: v["pay"][h:Kt] for o, v in lot.items() if v["pay"][0] is not None}
        ba = max(a, key=lambda o: (np.mean(a[o]), -OPTIONS.index(o)))
        bb = max(b, key=lambda o: (np.mean(b[o]), -OPTIONS.index(o)))
        n += 1
        agree += ba == bb
    return {"K": Kt, "states": n, "agree": agree, "share": agree / n if n else None}


# ------------------------------------------------------------------ sampling

def cells(states: list[dict]) -> dict:
    c: dict = {}
    for s in states:
        c.setdefault((s["market"], s["d"]), []).append(s)
    return c


def pilot_states(states: list[dict]) -> list[dict]:
    out = []
    C = cells(states)
    for i, m in enumerate(MARKETS):
        for j, d in enumerate(DAYS):
            pool = sorted(C.get((m, d), []), key=lambda s: s["id"])
            if not pool:
                continue
            rng = np.random.default_rng([SELECT_SEED, i, j])
            out.append(pool[int(rng.integers(len(pool)))])
    return out


def allocation(pilot_lab: dict, pstates: list[dict], C: dict) -> dict:
    """{(market, d): n} by the rule in the module docstring."""
    p = {}
    for m in MARKETS:
        xs = [pilot_lab[s["id"]]["pays"] for s in pstates if s["market"] == m]
        p[m] = (sum(xs) + 0.5) / (len(xs) + 1)
    H = [m for m in MARKETS if p[m] >= 0.5]
    L = [m for m in MARKETS if p[m] < 0.5]
    cell_list = [(m, d) for m in MARKETS for d in DAYS if C.get((m, d))]

    def spread(n, ms):
        out, cl = {}, [(m, d) for m in ms for d in DAYS if C.get((m, d))]
        if not cl:
            return out
        q, r = divmod(n, len(cl))
        for i, c in enumerate(cl):
            out[c] = q + (1 if i < r else 0)
        return out
    if H and L:
        pH, pL = float(np.mean([p[m] for m in H])), float(np.mean([p[m] for m in L]))
        nH = int(round(N_BANK * (0.5 - pL) / (pH - pL)))
        nH = max(MIN_PER_CELL * 4 * len(H), min(N_BANK - MIN_PER_CELL * 4 * len(L), nH))
        alloc = {**spread(nH, H), **spread(N_BANK - nH, L)}
        rule = {"H": H, "L": L, "pH": pH, "pL": pL, "nH": nH}
    else:
        alloc = spread(N_BANK, list(MARKETS))
        rule = {"H": H, "L": L, "note": "one group empty: even over all cells; the half target cannot be aimed at"}
    for c in cell_list:                         # a cell cannot give more states than it has
        alloc[c] = min(alloc.get(c, 0), len(C[c]))
    return {"p_market": p, "rule": rule, "alloc": {f"{m}|{d}": n for (m, d), n in alloc.items()}}


def bank_states(states: list[dict], pstates: list[dict], alloc: dict) -> list[dict]:
    """Uniform within each cell; the cell's pilot state first. Weight = cell size / states drawn."""
    C = cells(states)
    pid = {s["id"] for s in pstates}
    out = []
    for i, m in enumerate(MARKETS):
        for j, d in enumerate(DAYS):
            n = alloc.get(f"{m}|{d}", 0)
            pool = sorted(C.get((m, d), []), key=lambda s: s["id"])
            if not n or not pool:
                continue
            first = [s for s in pool if s["id"] in pid]
            rest = [s for s in pool if s["id"] not in pid]
            rng = np.random.default_rng([SELECT_SEED, 1, i, j])
            pick = first + [rest[int(x)] for x in rng.permutation(len(rest))[:max(0, n - len(first))]]
            for s in pick:
                out.append({**s, "cell_size": len(pool), "cell_drawn": len(pick), "weight": len(pool) / len(pick),
                            "pilot": s["id"] in pid})
    return out


# ------------------------------------------------------------------ io

def read_cache(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f]


def all_states() -> list[dict]:
    recs = read_cache(f"{OUT}/enumerate_cache.jsonl")
    keys = {r["key"] for r in recs}
    missing = [f"E|{m}|{s}" for m in MARKETS for s in SEEDS if f"E|{m}|{s}" not in keys]
    if missing:
        raise SystemExit(f"enumeration incomplete: {len(missing)} chains missing (run --phase enumerate)")
    return [s for r in sorted(recs, key=lambda r: r["key"]) for s in r["states"]]


def run_record(a, phase: str) -> dict:
    sha = hashlib.sha256(open(__file__, "rb").read()).hexdigest()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "engine", "agents", "analysis/state_bank.py"],
                           capture_output=True, text=True).stdout.strip()
    return {"phase": phase, "engine": ENGINE_VERSION, "commit": commit, "code_dirty": bool(dirty),
            "script_sha256": sha, "python": platform.python_version(), "numpy": np.__version__,
            "platform": platform.platform(), "command": " ".join(sys.argv), "tests": a.tests, "workers": a.workers,
            "started": time.strftime("%Y-%m-%d %H:%M:%S")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True, choices=["enumerate", "pilot", "bank", "build"])
    ap.add_argument("--markets", default="", help="bank: comma-separated market names (default: all)")
    ap.add_argument("--K", type=int, default=None, help="bank: K chosen by the pilot (read from pilot_gates.json)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tests", default="")
    ap.add_argument("--min-swap-mb", type=float, default=512)
    ap.add_argument("--min-free-pct", type=float, default=15)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    log = CR.file_logger(f"{OUT}/state_bank_run.log")
    rec = run_record(a, a.phase)
    log(f"run record {json.dumps(rec, sort_keys=True)}")
    if rec["code_dirty"]:
        raise SystemExit("engine, agents or analysis/state_bank.py has uncommitted changes: commit first")
    t0 = time.time()
    if a.phase == "enumerate":
        jobs = [(m, s) for m in MARKETS for s in SEEDS]
        CR.run_chains(a, jobs, f"{OUT}/enumerate_cache.jsonl", log, enum_job, lambda j: f"E|{j[0]}|{j[1]}")
        st = all_states()
        C = cells(st)
        log(f"enumerated {len(st)} states; per cell: " +
            json.dumps({f"{m}|{d}": len(C.get((m, d), [])) for m in MARKETS for d in DAYS}))
    elif a.phase == "pilot":
        st = all_states()
        ps = pilot_states(st)
        jobs = lottery_jobs(ps, K_PILOT)
        recs, pauses = CR.run_chains(a, jobs, f"{OUT}/lottery_cache.jsonl", log, lottery_job, lkey)
        lots = collect(recs, ps, K_PILOT)
        lab = {i: labels(l) for i, l in lots.items()}
        sh = [split_half(lots, Kt) for Kt in K_GRID]
        ok = {r["K"]: r["share"] is not None and r["share"] >= AGREE_MIN for r in sh}
        K = 20 if ok[20] else (30 if ok[30] else None)
        C = cells(st)
        by_m = {}
        for m in MARKETS:
            xs = [lab[s["id"]]["pays"] for s in ps if s["market"] == m]
            by_m[m] = {"states": len(xs), "pays": sum(xs)}
        wsum = sum(len(C[(s["market"], s["d"])]) for s in ps)
        g4b = sum(len(C[(s["market"], s["d"])]) * lab[s["id"]]["pays"] for s in ps) / wsum
        g4b_unw = float(np.mean([lab[s["id"]]["pays"] for s in ps]))
        alloc = allocation(lab, ps, C)
        secs = [r["secs"] / max(1, r["guard"]["continuations"]) for r in recs]
        guard = {k: sum(r["guard"][k] for r in recs) for k in ("stuck_buyers", "idle_choosers", "continuations")}
        bank_n = sum(alloc["alloc"].values())
        spc = float(np.mean(secs))
        proj = {Kt: (bank_n - len(ps)) * len(SIM_OPTIONS) * Kt * spc / a.workers / 3600 for Kt in (20, 30)}
        gates = {"run": rec, "K_split_half": sh, "K_chosen": K, "G4b_weighted": g4b, "G4b_unweighted": g4b_unw,
                 "G4b_pass": g4b >= G4B_MIN, "pays_by_market": by_m, "allocation": alloc, "bank_states": bank_n,
                 "close_calls_pilot": sum(lab[i]["close_call"] for i in lab), "guard": guard,
                 "secs_per_continuation_job_mean": spc, "bank_projected_hours": proj, "pauses": pauses,
                 "wall_secs": time.time() - t0, "labels": lab}
        with open(f"{OUT}/pilot_gates.json", "w", encoding="utf-8") as f:
            json.dump(gates, f, indent=1, sort_keys=True)
        log(f"pilot: K split-half {sh}; K chosen {K}; G4b {g4b:.3f} (unweighted {g4b_unw:.3f}); guard {guard}")
    elif a.phase == "bank":
        g = json.load(open(f"{OUT}/pilot_gates.json", encoding="utf-8"))
        K = a.K or g["K_chosen"]
        if not K or not g["G4b_pass"]:
            raise SystemExit("pilot gates did not pass")
        st = all_states()
        ps = pilot_states(st)
        bs = bank_states(st, ps, g["allocation"]["alloc"])
        want = set(a.markets.split(",")) if a.markets else set(MARKETS)
        todo = [s for s in bs if s["market"] in want and not s["pilot"]]     # pilot states: drawn in the pilot
        jobs = lottery_jobs(todo, K)
        CR.run_chains(a, jobs, f"{OUT}/lottery_cache.jsonl", log, lottery_job, lkey)
        log(f"bank: {len(todo)} states of {len(bs)} ({sorted(want)}), K {K}, {len(jobs)} jobs")
    else:
        g = json.load(open(f"{OUT}/pilot_gates.json", encoding="utf-8"))
        K = g["K_chosen"]
        st = all_states()
        ps = pilot_states(st)
        bs = bank_states(st, ps, g["allocation"]["alloc"])
        recs = read_cache(f"{OUT}/lottery_cache.jsonl")
        bank_jobs = {lkey(j) for j in lottery_jobs([s for s in bs if not s["pilot"]], K)}
        pil_jobs = {lkey(j) for j in lottery_jobs(ps, K_PILOT)}
        use = [r for r in recs if r["key"] in bank_jobs or r["key"] in pil_jobs]
        lots = collect(use, bs, K)
        out = []
        for s in bs:
            lot = lots[s["id"]]
            lab = labels(lot)
            out.append({"id": s["id"], "observation": s["obs"], "hidden": {**hidden(s["market"]), "seed": s["seed"],
                        "stall": s["stall"], "category": s["category"], "q_true": s["q_true"]},
                        "lotteries": option_stats(lot), "labels": {**lab, "best": NEUTRAL[lab["best"]],
                                                                    "second": NEUTRAL[lab["second"]],
                                                                    "best_paying_option": NEUTRAL[lab["best_paying_option"]],
                                                                    "means": {NEUTRAL[o]: v for o, v in lab["means"].items()}},
                        "sampling": {"cell": f"{s['market']}|{s['d']}", "cell_size": s["cell_size"],
                                     "cell_drawn": s["cell_drawn"], "weight": s["weight"], "pilot": s["pilot"]},
                        "K": K})
        with gzip.open(f"{OUT}/states.jsonl.gz", "wt", encoding="utf-8") as f:
            for r in out:
                f.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")
        guard = {k: sum(r["guard"][k] for r in use) for k in ("stuck_buyers", "idle_choosers", "continuations")}
        summ = {"run": rec, "K": K, "states": len(out), "guard": guard,
                "pays": sum(r["labels"]["pays"] for r in out), "close_calls": sum(r["labels"]["close_call"] for r in out),
                "pays_weighted": float(sum(r["sampling"]["weight"] * r["labels"]["pays"] for r in out)
                                       / sum(r["sampling"]["weight"] for r in out)),
                "by_market": {m: {"states": sum(r["hidden"]["market"] == m for r in out),
                                  "pays": sum(r["labels"]["pays"] for r in out if r["hidden"]["market"] == m),
                                  "close_calls": sum(r["labels"]["close_call"] for r in out if r["hidden"]["market"] == m),
                                  "best": {NEUTRAL[o]: sum(r["labels"]["best"] == NEUTRAL[o] for r in out
                                                           if r["hidden"]["market"] == m) for o in OPTIONS}}
                              for m in MARKETS}}
        with open(f"{OUT}/summary.json", "w", encoding="utf-8") as f:
            json.dump(summ, f, indent=1, sort_keys=True)
        log(f"build: {len(out)} states, pays {summ['pays']}, close calls {summ['close_calls']}, guard {guard}")
    log(f"phase {a.phase} done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
