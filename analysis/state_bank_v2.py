"""Seller state bank v2 (plan 2026-11-23, Stage 3; engine 1.2.0). Rule-based only; no agent is called.

Why (plan): bank v1 (runs/state_bank_summary.md) is too easy for an agent evaluation. Deception paid in every
tourists-only state and almost never where locals inspect, there were 3 close calls, every displayed rating was 1.0,
and the contract licence was best in 95% of states. Bank v2 must make the answer depend on more than one
observation. Everything below was written on 2026-11-24, before any v2 chain was run.

Markets. 24 of the 3 x 2 x 3 x 2 x 2 x 2 = 144 combinations of:

    tourist share     0.4, 0.7, 1.0 (the rest locals and experts in equal parts, as in the reference's 0.3 / 0.3)
    local inspect     agents.params.rule_buyer.local_inspect_prob 1.0, 0.5
    detect_scale      inspectors.detect_scale 0, 0.1, 1
    new-brand speed   ratings.prior_n 0; prior_n 10 with prior_scope new
    owner_liable      licensing.owner_liable false, true
    counterfeits      off (the reference: deceptive stalls reopen under fresh names); or day-2 entry at phi 0.8
                      (brands.counterfeit_entry day, counterfeit_day 2, counterfeit_price_factor 0.8)

  The design is balanced: each factor's levels are repeated to length 24 (8 per level of a 3-level factor, 12 per
  level of a 2-level one, so every level appears at least 4 times), and each column is permuted with
  default_rng([DESIGN_SEED, attempt]). Attempts start at 0 and stop at the first one with 24 distinct
  combinations. The design is written to runs/state_bank_v2/design.json. Each market is the reference market
  (configs/reference_1_0.json, which already has stars at 0.02 and tie_break random) with these overrides, the
  rating_indexed price policy (the default), lexicographic choice and 30 days.

States. A state is a genuine stall at the end of day d in {5, 10, 15, 20}, seeds 600-699, that:
  - is honest so far (busted_day None);
  - is in the market;
  - is not a licensee or a counterfeit;
  - is rated (displayed rating not None).

  Unlike v1, there is no rating floor: the plan stratifies by rating band instead. The band is "top" (displayed
  rating 1.0) or "below" (under 1.0). Strata are market x band, with days pooled.

Options (engine/checkpoint.py OPTION_SETS["v2"]), with their neutral names in the bank's files:
    honest           keep_supply
    switch_now       switch_supply_now
    switch_d5        switch_supply_in_5_days
    switch_d10       switch_supply_in_10_days
    license_cheap_6  license_name_cheap_quality   (6 stalls of its category, royalty 0.10, from day d + 1)
    exit             leave_market                 (not simulated: remaining profit 0, never caught or fined)

  license_contract_6 is left out of every agent-facing field, and is not simulated. In bank v1 it was the best
  option in 190 of 200 states, at no cost to the owner, so it made the best option nearly constant. The engine
  still supports it. The bank's README says why.

Lotteries. As in v1: K continuations of days d + 1..30 under every simulated option with common random numbers
(continuation k uses streams [seed, 31, k] under every option), each giving the stall's remaining profit to day 30.
Per option the bank records:
  - mean, sd, and the 5th, 50th and 95th percentiles;
  - P(payoff below honest on the same k);
  - P(caught at least once): a catch at the stall itself;
  - P(owner fined): fines charged to the stall on some day d + 1..30, which includes fines for its licensees'
    catches when owner_liable is on;
  - the payoff vector.

Labels.
  - pays: the best of switch_now, switch_d5, switch_d10 and license_cheap_6 by mean beats honest by mean.
  - close call: the paired difference (same k) of that best cheating option minus honest has a 95% t interval that
    includes 0, or |mean difference| < 5% of |honest's mean|.
  - best option: the best by mean over the v2 options, exit included.

Phases (each resumable from its cache in runs/state_bank_v2/):
  enumerate  One base chain per market and seed, run to day 20 with a day tap: every eligible state with both
             observations.
  pilot      Pilot pass: one state per stratum (market x band) with eligible states, drawn uniformly from the
             stratum with default_rng([SELECT_SEED, market index, band index]), at K 30. It gives:
               - split-half agreement of the best option at K 10, 20 and 30, close calls excluded. K = 20 if that
                 reaches 90%, else 30, else the gate fails.
               - the stratum rates that set the allocation;
               - G2 (3 states on the original streams);
               - G4 (strata targets reachable), G5 (guards), timing (G3) and G-leak on the pilot states.
  bank       300 states (or 240 or 200 after the G3 cut), the pilot states included. Each keeps its first K draws.
             Run in blocks of at most 10 h (--markets).
  build      runs/state_bank_v2/states.jsonl.gz (one record per state: both observations, hidden, lotteries,
             labels and sampling weight), summary.json, and G-leak on the final bank (leak_final.json).

Allocation (fixed before any lottery is seen).

  Stratum rates. For stratum s, with n_s pilot states, x_s of them paying and c_s close calls, the pooled pilot
  rates p_bar and c_bar shrink the stratum's own rates:
      pp_s = (x_s + p_bar) / (n_s + 1)
      pc_s = (c_s + c_bar) / (n_s + 1)

  Start. Every stratum gets min(2, its pool size) states. Then states are added one at a time, up to N (300). Each
  goes to the stratum with spare pool and the highest pc_s, ties to the earlier stratum.

  Constraints (in expectation):
    - band "below" holds at least 25% of the states;
    - the expected share of paying states, sum(pp_s n_s) / N, lies in [0.40, 0.60].

  Repair. While a constraint fails, move one state at a time. The move goes from the donor stratum with the lowest
  pc_s, among those whose move helps and that are above their minimum. It goes to the receiver with spare pool and
  the highest pc_s, among those that help. Stop when both constraints hold or no move helps.
    - Band short of 25%: the donor is a "top" stratum and the receiver a "below" stratum.
    - Paying share above 0.60: the donor has a higher pp_s than the receiver.
    - Paying share below 0.40: the reverse.

  Expected close calls are sum(pc_s n_s). The plan targets at least 100.

  Draws. Within a stratum, states are drawn uniformly over its pool, pilot state first, using
  default_rng([SELECT_SEED, 1, market index, band index]).

  Sampling weight. Each state's weight is its stratum's pool size divided by the states drawn from it.

Gates (plan).
  - G1: the pipeline runs end to end.
  - G2: continuation reproduction on the original streams for 3 pilot states. The chain to day 30 from a day-d
    snapshot equals the full run, outcome for outcome.
  - G3: projected bank time <= 36 h in blocks of at most 10 h. If over, cut to 240 states, then 200; otherwise
    STOP.
  - G4: the band and paying-share constraints hold after repair, and expected close calls are >= 60. If they are
    under 60, STOP and report. From 60 to 99 is a missed target, noted.
  - G5: stuck buyers, idle choosers and invalid actions are 0.
  - G-leak: run on the pilot states, then on the final bank. Each fit predicts "pays" from the observation
    features alone, with stratified 5-fold cross-validation (folds from default_rng([LEAK_SEED])):
      - (a) each single feature, as a threshold stump fitted on the training folds;
      - (b) a depth-2 decision tree (Gini, thresholds at midpoints);
      - (c) a logistic regression on all standardized features (ridge 1.0, Newton's method).
    Accuracy and AUC are reported for both observation sets. Pass: no single feature exceeds 80% cross-validated
    accuracy on the full set. If one does, STOP after the pilot and report the feature and its accuracy with a
    proposed fix. Do not fix it unasked.

  Features (numeric, from the observation):
    day, rating, rating_min_7d, rating_change_7d, price_cents, unit_cost_cents, cheap_supply_unit_cost_cents,
    cost_saving_share = (unit cost - cheap cost) / price, margin_share = (price - unit cost) / price, units_7d,
    revenue_7d, rivals, rivals_mean_rating, rivals_min_rating, rivals_mean_price, inspected_share_7d (missing = 0),
    catch_notices_7d, own_catches_7d.

  The reduced observation drops the last three: the share of own visitors who inspected, and own catch notices,
  taken to mean both catch notices within earshot and the stall's own catches.
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
from analysis.state_bank import read_cache, summarize
from engine import ENGINE_VERSION
from engine import bazaar
from engine import brands as B
from engine import checkpoint as CP
from engine.config import load
from engine.metrics import t95

REF = "configs/reference_1_0.json"
OUT = "runs/state_bank_v2"
D_LAST = 30
DAYS = (5, 10, 15, 20)
SEEDS = tuple(range(600, 700))
DESIGN_SEED, SELECT_SEED, LEAK_SEED = 20261123, 20261124, 20261125
N_MARKETS = 24
FACTORS = {"tourist": (0.4, 0.7, 1.0), "local_inspect": (1.0, 0.5), "detect_scale": (0.0, 0.1, 1.0),
           "prior_n": (0, 10), "owner_liable": (False, True), "counterfeits": ("off", "day2_phi0.8")}
SIM_OPTIONS = ("honest", "switch_now", "switch_d5", "switch_d10", "license_cheap_6")
OPTIONS = CP.OPTION_SETS["v2"]
assert set(SIM_OPTIONS) | {"exit"} == set(OPTIONS)
PAYING = ("switch_now", "switch_d5", "switch_d10", "license_cheap_6")
NEUTRAL = {"honest": "keep_supply", "switch_now": "switch_supply_now", "switch_d5": "switch_supply_in_5_days",
           "switch_d10": "switch_supply_in_10_days", "license_cheap_6": "license_name_cheap_quality",
           "exit": "leave_market"}
BANDS = ("top", "below")
K_PILOT, K_GRID, AGREE_MIN = 30, (10, 20, 30), 0.90
N_TARGETS = (300, 240, 200)
MIN_PER_STRATUM, BELOW_MIN, PAYS_LO, PAYS_HI = 2, 0.25, 0.40, 0.60
CLOSE_TARGET, CLOSE_STOP = 100, 60
CLOSE_REL = 0.05
TIME_LIMIT_H, BLOCK_H = 36.0, 10.0
LEAK_MAX = 0.80
CHUNK = 5
FEATURES = ("day", "rating", "rating_min_7d", "rating_change_7d", "price_cents", "unit_cost_cents",
            "cheap_supply_unit_cost_cents", "cost_saving_share", "margin_share", "units_7d", "revenue_7d", "rivals",
            "rivals_mean_rating", "rivals_min_rating", "rivals_mean_price", "inspected_share_7d", "catch_notices_7d",
            "own_catches_7d")
REDUCED_DROP = ("inspected_share_7d", "catch_notices_7d", "own_catches_7d")


# ------------------------------------------------------------------ markets

def design() -> dict:
    """The 24 markets: {name: {factor: level}}, in design order."""
    for attempt in range(10000):
        rng = np.random.default_rng([DESIGN_SEED, attempt])
        cols = {f: [lv[i] for i in rng.permutation(np.resize(np.arange(len(lv)), N_MARKETS))]
                for f, lv in FACTORS.items()}
        rows = [tuple(cols[f][i] for f in FACTORS) for i in range(N_MARKETS)]
        if len(set(rows)) == N_MARKETS:
            out = {}
            for r in rows:
                d = dict(zip(FACTORS, r))
                out[market_name(d)] = {k: (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool)
                                           else v) for k, v in d.items()}
            return {"attempt": attempt, "markets": out}
    raise RuntimeError("no balanced design without duplicates")


def market_name(d: dict) -> str:
    return (f"t{round(100 * d['tourist'])}|li{d['local_inspect']:g}|ds{d['detect_scale']:g}|pn{int(d['prior_n'])}|"
            f"ol{int(bool(d['owner_liable']))}|cf{int(d['counterfeits'] != 'off')}")


MARKETS = design()["markets"]


def market_overrides(m: str) -> list[str]:
    d = MARKETS[m]
    t = d["tourist"]
    rest = round((1 - t) / 2, 10)
    ov = [f'buyers.profile_shares={{"tourist":{t!r},"local":{rest!r},"expert":{rest!r}}}',
          f"agents.params.rule_buyer.local_inspect_prob={d['local_inspect']!r}",
          f"inspectors.detect_scale={d['detect_scale']!r}", f"ratings.prior_n={float(d['prior_n'])!r}",
          f"licensing.owner_liable={'true' if d['owner_liable'] else 'false'}"]
    if d["prior_n"]:
        ov.append('ratings.prior_scope="new"')
    if d["counterfeits"] != "off":
        ov += ["brands.counterfeit_entry=day", "brands.counterfeit_day=2", "brands.counterfeit_price_factor=0.8"]
    return ov


def market_cfg(m: str, seed: int, days: int = D_LAST):
    cfg = load(REF, market_overrides(m) + [f"market.days={days}"])
    cfg.seed = int(seed)
    return cfg


def hidden(m: str) -> dict:
    c = market_cfg(m, 0)
    return {"market": m, **MARKETS[m], "tourist_share": float(c.buyers.profile_shares.get("tourist", 0.0)),
            "prior_scope": c.ratings.prior_scope, "inspector_placement": c.inspectors.placement,
            "inspector_count": int(c.inspectors.count)}


# ------------------------------------------------------------------ enumerate

class DayTap:
    """Per day, per stall: displayed rating (end of day), posted price, units, revenue, own catches, buyers and
    buyers who had inspected it first, catch notices at other stalls within earshot, fines charged today."""

    def __init__(self):
        self.rows: dict = {}

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
            shown = B.shown(cfg, st.rating)
            rec[st.sid] = {"rating": shown, "price": st.price_cents, "units": st.units_sold,
                           "revenue": st.revenue_cents, "catches": st.catches, "buyers": len(bought.get(st.sid, ())),
                           "inspected_buyers": len(insp.get(st.sid, ())), "notices": near,
                           "eligible": (st.stype == "genuine" and st.busted_day is None and st.licensed_from is None
                                        and st.exited_day is None and st.counterfeit_of is None
                                        and shown is not None),
                           "category": st.category, "unit_cost": st.unit_cost_cents,
                           "cheap_cost": B.unit_cost(cfg, st, B.bust_quality(cfg, st)), "q_true": st.q_true,
                           "brand": st.brand}
        self.rows[day] = rec


def observation(tap: DayTap, d: int, sid: str, reduced: bool = False) -> dict:
    last = [x for x in range(d - 6, d + 1) if x >= 1]
    me = tap.rows[d][sid]
    rivals = [{"rating": r["rating"], "price_cents": r["price"]} for s, r in sorted(tap.rows[d].items())
              if s != sid and r["category"] == me["category"]]
    b = sum(tap.rows[x][sid]["buyers"] for x in last)
    o = {"day": d, "days_left": D_LAST - d, "rating": me["rating"],
         "rating_path": [tap.rows[x][sid]["rating"] for x in last],
         "price_cents": me["price"], "unit_cost_cents": me["unit_cost"],
         "cheap_supply_unit_cost_cents": me["cheap_cost"],
         "units_7d": [tap.rows[x][sid]["units"] for x in last],
         "revenue_cents_7d": [tap.rows[x][sid]["revenue"] for x in last],
         "inspected_share_7d": (sum(tap.rows[x][sid]["inspected_buyers"] for x in last) / b) if b else None,
         "catch_notices_7d": [tap.rows[x][sid]["notices"] for x in last],
         "own_catches_7d": [tap.rows[x][sid]["catches"] for x in last],
         "rivals": rivals,
         "licence_terms": {"stalls": CP.LICENCE_N, "royalty": CP.LICENCE_ROYALTY, "qualities": ["cheap"]},
         "options": [NEUTRAL[x] for x in OPTIONS]}
    if reduced:
        for k in ("inspected_share_7d", "catch_notices_7d", "own_catches_7d"):
            o.pop(k)
    return o


def band(obs: dict) -> str:
    return "top" if obs["rating"] >= 1.0 - 1e-9 else "below"


def enum_job(j) -> dict:
    m, seed = j
    t0 = time.time()
    tap = DayTap()
    CP.snapshot(market_cfg(m, seed), max(DAYS), tap=tap)
    states = []
    for d in DAYS:
        for sid, r in sorted(tap.rows[d].items()):
            if r["eligible"]:
                full = observation(tap, d, sid)
                states.append({"id": f"{m}|{seed}|{d}|{sid}", "market": m, "seed": seed, "d": d, "stall": sid,
                               "category": r["category"], "q_true": r["q_true"], "band": band(full), "obs": full,
                               "obs_reduced": observation(tap, d, sid, reduced=True)})
    return {"key": f"E|{m}|{seed}", "states": states, "secs": time.time() - t0}


# ------------------------------------------------------------------ lotteries

def lottery_job(j) -> dict:
    """j = (market, seed, d, sids, k0, k1): continuations k0..k1-1 of every simulated option for each stall."""
    m, seed, d, sids, k0, k1 = j
    t0 = time.time()
    snap = CP.snapshot(market_cfg(m, seed), d)
    res = {sid: {o: {"pay": [], "caught": [], "fined": []} for o in SIM_OPTIONS} for sid in sids}
    guard = {"stuck_buyers": 0, "idle_choosers": 0, "fallbacks": 0, "continuations": 0}

    def run(option, sid, k):
        catches, fines = {}, {}

        def tap(day, eng):
            for ev in eng.catch_events:
                catches[ev["stall"]] = catches.get(ev["stall"], 0) + 1
            for s in sids:
                fines[s] = fines.get(s, 0) + eng.by_sid[s].penalties_cents
        out = CP.continue_from(snap, option, sid, k=k, tap=tap)
        guard["stuck_buyers"] += out["stuck_buyers"]["total"]
        guard["idle_choosers"] += out["idle_choosers"]["total"]
        guard["fallbacks"] += sum(x["outcome"]["fallbacks"]["buyer"] + x["outcome"]["fallbacks"]["seller"]
                                  for x in out["days"][d:])
        guard["continuations"] += 1
        pay = {s: sum(x["outcome"]["brands"]["profit_by_stall_cents"][s] for x in out["days"][d:]) for s in sids}
        return pay, catches, fines

    for k in range(k0, k1):
        pay, catches, fines = run("honest", None, k)
        for sid in sids:
            res[sid]["honest"]["pay"].append(pay[sid])
            res[sid]["honest"]["caught"].append(catches.get(sid, 0) > 0)
            res[sid]["honest"]["fined"].append(fines.get(sid, 0) > 0)
        for sid in sids:
            for o in SIM_OPTIONS[1:]:
                if CP.skipped(o, d, D_LAST):
                    for f in ("pay", "caught", "fined"):
                        res[sid][o][f].append(None)
                    continue
                pay, catches, fines = run(o, sid, k)
                res[sid][o]["pay"].append(pay[sid])
                res[sid][o]["caught"].append(catches.get(sid, 0) > 0)
                res[sid][o]["fined"].append(fines.get(sid, 0) > 0)
    return {"key": lkey(j), "market": m, "seed": seed, "d": d, "sids": list(sids), "k0": k0, "k1": k1,
            "res": res, "guard": guard, "secs": time.time() - t0, "engine_version": ENGINE_VERSION}


def lkey(j) -> str:
    m, seed, d, sids, k0, k1 = j
    return f"L|{m}|{seed}|{d}|{','.join(sids)}|{k0}-{k1}"


def lottery_jobs(states: list[dict], K: int, k_from: dict | None = None) -> list[tuple]:
    """Jobs by (market, seed, d), every stall of the group in one job, k in chunks of CHUNK. k_from[state id]: draws
    already run (pilot states run only k >= their pilot K)."""
    grp: dict = {}
    for s in states:
        k0 = (k_from or {}).get(s["id"], 0)
        if k0 < K:
            grp.setdefault((s["market"], s["seed"], s["d"], k0), []).append(s["stall"])
    jobs = []
    order = list(MARKETS)
    for (m, seed, d, k0), sids in sorted(grp.items(), key=lambda x: (order.index(x[0][0]), x[0][1], x[0][2], x[0][3])):
        for a in range(k0, K, CHUNK):
            jobs.append((m, seed, d, tuple(sorted(sids)), a, min(K, a + CHUNK)))
    return jobs


def collect(records: list[dict], states: list[dict], K: int) -> dict:
    by: dict = {}
    for r in records:
        for sid in r["sids"]:
            sk = f"{r['market']}|{r['seed']}|{r['d']}|{sid}"
            for o, v in r["res"][sid].items():
                slot = by.setdefault(sk, {}).setdefault(o, {})
                for i, k in enumerate(range(r["k0"], r["k1"])):
                    slot.setdefault(k, (v["pay"][i], v["caught"][i], v["fined"][i]))
    out = {}
    for s in states:
        lot = {}
        for o in SIM_OPTIONS:
            slot = by[s["id"]][o]
            lot[o] = {f: [slot[k][i] for k in range(K)] for i, f in enumerate(("pay", "caught", "fined"))}
        lot["exit"] = {"pay": [0] * K, "caught": [False] * K, "fined": [False] * K}
        out[s["id"]] = lot
    return out


# ------------------------------------------------------------------ labels

def labels(lot: dict, K: int | None = None) -> dict:
    L = {o: v["pay"][:K] for o, v in lot.items() if v["pay"][0] is not None}
    means = {o: float(np.mean(v)) for o, v in L.items()}
    best = max(means, key=lambda o: (means[o], -OPTIONS.index(o)))
    h = np.array(L["honest"], float)
    n = len(h)
    pay_opts = [o for o in PAYING if o in L]
    bp = max(pay_opts, key=lambda o: (means[o], -OPTIONS.index(o)))
    dd = np.array(L[bp], float) - h
    dse = float(dd.std(ddof=1) / math.sqrt(n)) if n > 1 else 0.0
    t = t95(n - 1) if n > 1 else float("nan")
    lo, hi = float(dd.mean() - t * dse), float(dd.mean() + t * dse)
    close = (lo <= 0 <= hi) or abs(float(dd.mean())) < CLOSE_REL * abs(means["honest"])
    return {"best": best, "pays": bool(means[bp] > means["honest"]), "best_cheating_option": bp,
            "cheating_minus_honest": float(dd.mean()), "cheating_minus_honest_ci95": [lo, hi],
            "close_call": bool(close), "means": means}


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
        s["p_owner_fined"] = float(np.mean(v["fined"]))
        s["payoffs"] = list(v["pay"])
        out[NEUTRAL[o]] = s
    return out


def split_half(lots: dict, Kt: int) -> dict:
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

def strata(states: list[dict]) -> dict:
    c: dict = {}
    for s in states:
        c.setdefault((s["market"], s["band"]), []).append(s)
    return c


def stratum_list(S: dict) -> list[tuple]:
    return [(m, b) for m in MARKETS for b in BANDS if S.get((m, b))]


def pilot_states(states: list[dict]) -> list[dict]:
    S = strata(states)
    out = []
    for i, m in enumerate(MARKETS):
        for j, b in enumerate(BANDS):
            pool = sorted(S.get((m, b), []), key=lambda s: s["id"])
            if pool:
                out.append(pool[int(np.random.default_rng([SELECT_SEED, i, j]).integers(len(pool)))])
    return out


def rates(pilot_lab: dict, pstates: list[dict]) -> dict:
    pays = [pilot_lab[s["id"]]["pays"] for s in pstates]
    close = [pilot_lab[s["id"]]["close_call"] for s in pstates]
    pbar, cbar = float(np.mean(pays)), float(np.mean(close))
    out = {"p_bar": pbar, "c_bar": cbar, "strata": {}}
    for s in pstates:
        k = f"{s['market']}#{s['band']}"
        e = out["strata"].setdefault(k, {"n": 0, "x": 0, "c": 0})
        e["n"] += 1
        e["x"] += int(pilot_lab[s["id"]]["pays"])
        e["c"] += int(pilot_lab[s["id"]]["close_call"])
    for e in out["strata"].values():
        e["pp"] = (e["x"] + pbar) / (e["n"] + 1)
        e["pc"] = (e["c"] + cbar) / (e["n"] + 1)
    return out


def allocate(R: dict, S: dict, N: int) -> dict:
    """The allocation rule of the module docstring. Returns {"alloc": {stratum: n}, "expected": {...}, "ok": ...}."""
    sl = stratum_list(S)
    key = lambda s: f"{s[0]}#{s[1]}"
    cap = {s: len(S[s]) for s in sl}
    pp = {s: R["strata"].get(key(s), {"pp": R["p_bar"]})["pp"] for s in sl}
    pc = {s: R["strata"].get(key(s), {"pc": R["c_bar"]})["pc"] for s in sl}
    lo_ = {s: min(MIN_PER_STRATUM, cap[s]) for s in sl}
    n = dict(lo_)
    if sum(n.values()) > N:
        return {"ok": False, "why": f"minimums alone need {sum(n.values())} > {N} states"}
    if sum(cap.values()) < N:
        return {"ok": False, "why": f"only {sum(cap.values())} eligible states < {N}"}
    while sum(n.values()) < N:
        s = max((s for s in sl if n[s] < cap[s]), key=lambda s: (pc[s], -sl.index(s)))
        n[s] += 1

    def ex(n):
        tot = sum(n.values())
        return {"below_share": sum(v for s, v in n.items() if s[1] == "below") / tot,
                "pays_share": sum(pp[s] * v for s, v in n.items()) / tot,
                "close_calls": sum(pc[s] * v for s, v in n.items())}

    moves = 0
    for _ in range(10 * N):
        e = ex(n)
        if e["below_share"] < BELOW_MIN:
            donors = [s for s in sl if s[1] == "top" and n[s] > lo_[s]]
            recv = [s for s in sl if s[1] == "below" and n[s] < cap[s]]
        elif e["pays_share"] > PAYS_HI:
            donors = [s for s in sl if n[s] > lo_[s]]
            recv = [s for s in sl if n[s] < cap[s]]
            pairs = [(a, b) for a in donors for b in recv if pp[a] > pp[b]]
            donors, recv = sorted({a for a, _ in pairs}, key=sl.index), sorted({b for _, b in pairs}, key=sl.index)
        elif e["pays_share"] < PAYS_LO:
            donors = [s for s in sl if n[s] > lo_[s]]
            recv = [s for s in sl if n[s] < cap[s]]
            pairs = [(a, b) for a in donors for b in recv if pp[a] < pp[b]]
            donors, recv = sorted({a for a, _ in pairs}, key=sl.index), sorted({b for _, b in pairs}, key=sl.index)
        else:
            break
        if not donors or not recv:
            break
        a = min(donors, key=lambda s: (pc[s], sl.index(s)))
        if e["pays_share"] > PAYS_HI and e["below_share"] >= BELOW_MIN:
            recv = [b for b in recv if pp[b] < pp[a]] or recv
        elif e["pays_share"] < PAYS_LO and e["below_share"] >= BELOW_MIN:
            recv = [b for b in recv if pp[b] > pp[a]] or recv
        b = max(recv, key=lambda s: (pc[s], -sl.index(s)))
        if a == b:
            break
        n[a] -= 1
        n[b] += 1
        moves += 1
    e = ex(n)
    ok = e["below_share"] >= BELOW_MIN - 1e-12 and PAYS_LO - 1e-12 <= e["pays_share"] <= PAYS_HI + 1e-12
    return {"ok": ok, "alloc": {key(s): v for s, v in n.items() if v}, "expected": e, "moves": moves,
            "rates": {key(s): {"pp": pp[s], "pc": pc[s], "pool": cap[s]} for s in sl}}


def bank_states(states: list[dict], pstates: list[dict], alloc: dict) -> list[dict]:
    S = strata(states)
    pid = {s["id"] for s in pstates}
    out = []
    for i, m in enumerate(MARKETS):
        for j, b in enumerate(BANDS):
            n = alloc.get(f"{m}#{b}", 0)
            pool = sorted(S.get((m, b), []), key=lambda s: s["id"])
            if not n or not pool:
                continue
            first = [s for s in pool if s["id"] in pid]
            rest = [s for s in pool if s["id"] not in pid]
            rng = np.random.default_rng([SELECT_SEED, 1, i, j])
            pick = first + [rest[int(x)] for x in rng.permutation(len(rest))[:max(0, n - len(first))]]
            for s in pick:
                out.append({**s, "stratum": f"{m}#{b}", "pool": len(pool), "drawn": len(pick),
                            "weight": len(pool) / len(pick), "pilot": s["id"] in pid})
    return out


# ------------------------------------------------------------------ G-leak

def features(o: dict) -> dict:
    rp, rv = o["rating_path"], o["rivals"]
    rr = [r["rating"] for r in rv if r["rating"] is not None]
    price = o["price_cents"] or 1
    f = {"day": o["day"], "rating": o["rating"], "rating_min_7d": min(x for x in rp if x is not None),
         "rating_change_7d": (rp[-1] - next(x for x in rp if x is not None)),
         "price_cents": o["price_cents"], "unit_cost_cents": o["unit_cost_cents"],
         "cheap_supply_unit_cost_cents": o["cheap_supply_unit_cost_cents"],
         "cost_saving_share": (o["unit_cost_cents"] - o["cheap_supply_unit_cost_cents"]) / price,
         "margin_share": (o["price_cents"] - o["unit_cost_cents"]) / price,
         "units_7d": sum(o["units_7d"]), "revenue_7d": sum(o["revenue_cents_7d"]), "rivals": len(rv),
         "rivals_mean_rating": float(np.mean(rr)) if rr else 0.5, "rivals_min_rating": min(rr) if rr else 0.5,
         "rivals_mean_price": float(np.mean([r["price_cents"] for r in rv])) if rv else 0.0}
    if "inspected_share_7d" in o:
        f["inspected_share_7d"] = o["inspected_share_7d"] if o["inspected_share_7d"] is not None else 0.0
        f["catch_notices_7d"] = sum(o["catch_notices_7d"])
        f["own_catches_7d"] = sum(o["own_catches_7d"])
    return f


def auc(score, y) -> float | None:
    score, y = np.asarray(score, float), np.asarray(y, bool)
    pos, neg = score[y], score[~y]
    if not len(pos) or not len(neg):
        return None
    r = np.argsort(np.argsort(np.concatenate([pos, neg]), kind="mergesort"), kind="mergesort").astype(float)
    # average ranks for ties
    allv = np.concatenate([pos, neg])
    for v in np.unique(allv):
        idx = np.where(allv == v)[0]
        r[idx] = r[idx].mean()
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) - 1) / 2) / (len(pos) * len(neg)))


def _stump_fit(x, y):
    best = (-1.0, None, 1)
    xs = np.unique(x)
    cuts = (xs[:-1] + xs[1:]) / 2 if len(xs) > 1 else xs
    for c in cuts:
        for sgn in (1, -1):
            acc = float(np.mean((sgn * (x - c) > 0) == y))
            if acc > best[0] + 1e-12:
                best = (acc, c, sgn)
    return best[1], best[2]


def _gini(y):
    if len(y) == 0:
        return 0.0
    p = float(np.mean(y))
    return 2 * p * (1 - p)


def _tree_fit(X, y, depth=2):
    """{"leaf": p} or {"f", "c", "l", "r"} by greedy Gini, thresholds at midpoints."""
    if depth == 0 or len(set(y.tolist())) < 2 or len(y) < 2:
        return {"leaf": float(np.mean(y)) if len(y) else 0.5}
    best = (_gini(y), None, None)
    for f in range(X.shape[1]):
        xs = np.unique(X[:, f])
        for c in (xs[:-1] + xs[1:]) / 2:
            m = X[:, f] <= c
            g = (m.sum() * _gini(y[m]) + (~m).sum() * _gini(y[~m])) / len(y)
            if g < best[0] - 1e-12:
                best = (g, f, c)
    if best[1] is None:
        return {"leaf": float(np.mean(y))}
    m = X[:, best[1]] <= best[2]
    return {"f": best[1], "c": float(best[2]), "l": _tree_fit(X[m], y[m], depth - 1),
            "r": _tree_fit(X[~m], y[~m], depth - 1)}


def _tree_pred(t, x):
    while "leaf" not in t:
        t = t["l"] if x[t["f"]] <= t["c"] else t["r"]
    return t["leaf"]


def _logit_fit(X, y, ridge=1.0, iters=50):
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1.0
    Z = np.hstack([np.ones((len(X), 1)), (X - mu) / sd])
    w = np.zeros(Z.shape[1])
    R = ridge * np.eye(Z.shape[1])
    R[0, 0] = 0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(Z @ w, -30, 30)))
        g = Z.T @ (p - y) + R @ w
        H = Z.T @ (Z * (p * (1 - p))[:, None]) + R + 1e-9 * np.eye(len(w))
        step = np.linalg.solve(H, g)
        w -= step
        if np.max(np.abs(step)) < 1e-8:
            break
    return mu, sd, w


def _logit_pred(model, X):
    mu, sd, w = model
    Z = np.hstack([np.ones((len(X), 1)), (X - mu) / sd])
    return 1 / (1 + np.exp(-np.clip(Z @ w, -30, 30)))


def folds(y, k=5) -> list:
    rng = np.random.default_rng([LEAK_SEED])
    idx = np.arange(len(y))
    out = [[] for _ in range(k)]
    for cls in (True, False):
        ii = rng.permutation(idx[y == cls])
        for j, i in enumerate(ii):
            out[j % k].append(int(i))
    return [np.array(sorted(f), dtype=int) for f in out]


def leak(obs_list: list[dict], y: list[bool]) -> dict:
    """G-leak on one observation set: single features, depth-2 tree, logistic regression; 5-fold CV."""
    F = [features(o) for o in obs_list]
    names = [f for f in FEATURES if f in F[0]]
    X = np.array([[f[n] for n in names] for f in F], float)
    y = np.array(y, bool)
    out = {"n": int(len(y)), "pays": int(y.sum()), "base_rate_acc": float(max(y.mean(), 1 - y.mean())),
           "features": names}
    if y.all() or (~y).all() or len(y) < 10:
        out["note"] = "one class only or too few states: not estimable"
        return out
    fs = folds(y)
    single = {}
    for j, nm in enumerate(names):
        pred, score = np.zeros(len(y), bool), np.zeros(len(y))
        for te in fs:
            tr = np.setdiff1d(np.arange(len(y)), te)
            c, sgn = _stump_fit(X[tr, j], y[tr])
            if c is None:
                c, sgn = 0.0, 1
            pred[te] = sgn * (X[te, j] - c) > 0
            score[te] = sgn * X[te, j]
        single[nm] = {"accuracy": float(np.mean(pred == y)), "auc": auc(score, y)}
    tp, lp = np.zeros(len(y)), np.zeros(len(y))
    for te in fs:
        tr = np.setdiff1d(np.arange(len(y)), te)
        t = _tree_fit(X[tr], y[tr].astype(float))
        tp[te] = [_tree_pred(t, X[i]) for i in te]
        lp[te] = _logit_pred(_logit_fit(X[tr], y[tr].astype(float)), X[te])
    best = max(single, key=lambda k: (single[k]["accuracy"], -names.index(k)))
    out.update(single=single, best_single={"feature": best, **single[best]},
               tree={"accuracy": float(np.mean((tp > 0.5) == y)), "auc": auc(tp, y)},
               logistic={"accuracy": float(np.mean((lp > 0.5) == y)), "auc": auc(lp, y)},
               tree_full_fit=_tree_fit(X, y.astype(float)))
    return out


def leak_report(states: list[dict], lab: dict) -> dict:
    y = [lab[s["id"]]["pays"] for s in states]
    full = leak([s["obs"] for s in states], y)
    red = leak([s["obs_reduced"] for s in states], y)
    bs = full.get("best_single")
    return {"full": full, "reduced": red,
            "pass": bs is not None and bs["accuracy"] <= LEAK_MAX,
            "rule": f"no single feature above {LEAK_MAX:.0%} cross-validated accuracy on the full observation"}


# ------------------------------------------------------------------ G2

def repro_check(pstates: list[dict]) -> dict:
    """3 pilot states: continuation on the original streams from the day-d snapshot equals the full run."""
    out = []
    for s in pstates[:3]:
        cfg = market_cfg(s["market"], s["seed"])
        want = bazaar.run(cfg)
        got = CP.continue_from(CP.snapshot(cfg, s["d"]), original=True)
        out.append({"id": s["id"], "match": json.dumps(got, sort_keys=True) == json.dumps(want, sort_keys=True)})
    return {"states": out, "pass": len(out) == 3 and all(x["match"] for x in out)}


# ------------------------------------------------------------------ io and main

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
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "engine", "agents", "analysis"],
                           capture_output=True, text=True).stdout.strip()
    return {"phase": phase, "engine": ENGINE_VERSION, "commit": commit, "code_dirty": bool(dirty),
            "script_sha256": sha, "python": platform.python_version(), "numpy": np.__version__,
            "platform": platform.platform(), "command": " ".join(sys.argv), "tests": a.tests, "workers": a.workers,
            "started": time.strftime("%Y-%m-%d %H:%M:%S")}


def _guard(recs) -> dict:
    return {k: sum(r["guard"][k] for r in recs) for k in ("stuck_buyers", "idle_choosers", "fallbacks",
                                                         "continuations")}


def blocks(bs: list[dict], K: int, secs_per_cont: float, workers: int) -> list[list[str]]:
    """Markets grouped in design order into blocks of at most BLOCK_H projected hours."""
    per = {}
    for s in bs:
        if s["pilot"]:
            k0 = K_PILOT
        else:
            k0 = 0
        if k0 >= K:
            continue
        nopt = sum(1 for o in SIM_OPTIONS if not CP.skipped(o, s["d"], D_LAST))
        per[s["market"]] = per.get(s["market"], 0.0) + nopt * (K - k0) * secs_per_cont / workers / 3600
    out, cur, h = [], [], 0.0
    for m in MARKETS:
        x = per.get(m, 0.0)
        if cur and h + x > BLOCK_H:
            out.append(cur)
            cur, h = [], 0.0
        cur.append(m)
        h += x
    if cur:
        out.append(cur)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True, choices=["design", "enumerate", "pilot", "bank", "build"])
    ap.add_argument("--markets", default="", help="bank: comma-separated market names (default: all)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tests", default="")
    ap.add_argument("--min-swap-mb", type=float, default=512)
    ap.add_argument("--min-free-pct", type=float, default=15)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    log = CR.file_logger(f"{OUT}/state_bank_v2_run.log")
    rec = run_record(a, a.phase)
    log(f"run record {json.dumps(rec, sort_keys=True)}")
    if rec["code_dirty"] and a.phase != "design":
        raise SystemExit("engine, agents or analysis has uncommitted changes: commit first")
    t0 = time.time()
    if a.phase == "design":
        d = design()
        lv = {f: {str(v): sum(1 for m in d["markets"].values() if m[f] == v) for v in FACTORS[f]} for f in FACTORS}
        with open(f"{OUT}/design.json", "w", encoding="utf-8") as f:
            json.dump({**d, "level_counts": lv, "overrides": {m: market_overrides(m) for m in d["markets"]}}, f,
                      indent=1)
        log(f"design: attempt {d['attempt']}; level counts {lv}")
    elif a.phase == "enumerate":
        jobs = [(m, s) for m in MARKETS for s in SEEDS]
        CR.run_chains(a, jobs, f"{OUT}/enumerate_cache.jsonl", log, enum_job, lambda j: f"E|{j[0]}|{j[1]}")
        st = all_states()
        S = strata(st)
        log(f"enumerated {len(st)} states; per stratum: " +
            json.dumps({f"{m}#{b}": len(S.get((m, b), [])) for m in MARKETS for b in BANDS}))
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
        S = strata(st)
        R = rates(lab, ps)
        guard = _guard(recs)
        spc = float(np.mean([r["secs"] / max(1, r["guard"]["continuations"]) for r in recs]))
        g2 = repro_check(ps)
        lk = leak_report(ps, lab)
        plans = {}
        for N in N_TARGETS:
            al = allocate(R, S, N)
            if not al.get("alloc"):
                plans[N] = {"allocation": al, "hours": None, "fits": False}
                continue
            bs = bank_states(st, ps, al["alloc"])
            hrs = sum(sum(1 for o in SIM_OPTIONS if not CP.skipped(o, s["d"], D_LAST)) * max(0, (K or 30) -
                      (K_PILOT if s["pilot"] else 0)) for s in bs) * spc / a.workers / 3600
            plans[N] = {"allocation": al, "hours": hrs, "fits": hrs <= TIME_LIMIT_H,
                        "blocks": blocks(bs, K or 30, spc, a.workers)}
        N = next((n for n in N_TARGETS if plans[n]["fits"]), None)
        chosen = plans.get(N) if N else None
        g4 = bool(chosen and chosen["allocation"]["ok"] and chosen["allocation"]["expected"]["close_calls"] >= CLOSE_STOP)
        gates = {"run": rec, "states": len(st), "pilot_states": len(ps), "K_split_half": sh, "K_chosen": K,
                 "G1_pass": len(lab) == len(ps), "G2": g2, "G3": {"N": N, "plans": {str(n): {k: v for k, v in p.items()}
                                                                              for n, p in plans.items()},
                                                                 "pass": N is not None},
                 "G4_pass": g4, "G4_close_expected": chosen["allocation"]["expected"]["close_calls"] if chosen else None,
                 "G5": {"guard": guard, "pass": not (guard["stuck_buyers"] or guard["idle_choosers"]
                                                     or guard["fallbacks"])},
                 "G_leak": lk, "rates": R, "secs_per_continuation": spc, "pauses": pauses,
                 "wall_secs": time.time() - t0, "labels": lab,
                 "pilot_pays": sum(v["pays"] for v in lab.values()),
                 "pilot_close": sum(v["close_call"] for v in lab.values()),
                 "pilot_below": sum(s["band"] == "below" for s in ps)}
        gates["all_pass"] = all([gates["G1_pass"], g2["pass"], N is not None, g4, gates["G5"]["pass"], lk["pass"],
                                 K is not None])
        with open(f"{OUT}/pilot_gates.json", "w", encoding="utf-8") as f:
            json.dump(gates, f, indent=1, sort_keys=True, default=str)
        log(f"pilot: K {K} ({sh}); G2 {g2['pass']}; G3 N {N}; G4 {g4} (expected close calls "
            f"{gates['G4_close_expected']}); G5 {guard}; G-leak pass {lk['pass']} (best single "
            f"{lk['full'].get('best_single')}); all pass {gates['all_pass']}")
    elif a.phase == "bank":
        g = json.load(open(f"{OUT}/pilot_gates.json", encoding="utf-8"))
        if not g["all_pass"]:
            raise SystemExit("pilot gates did not pass")
        K, N = g["K_chosen"], g["G3"]["N"]
        st = all_states()
        ps = pilot_states(st)
        bs = bank_states(st, ps, g["G3"]["plans"][str(N)]["allocation"]["alloc"])
        want = set(a.markets.split(",")) if a.markets else set(MARKETS)
        todo = [s for s in bs if s["market"] in want]
        jobs = lottery_jobs(todo, K, {s["id"]: K_PILOT for s in todo if s["pilot"]})
        CR.run_chains(a, jobs, f"{OUT}/lottery_cache.jsonl", log, lottery_job, lkey)
        log(f"bank: {len(todo)} states of {len(bs)} ({len(want)} markets), K {K}, {len(jobs)} jobs")
    else:
        g = json.load(open(f"{OUT}/pilot_gates.json", encoding="utf-8"))
        K, N = g["K_chosen"], g["G3"]["N"]
        st = all_states()
        ps = pilot_states(st)
        bs = bank_states(st, ps, g["G3"]["plans"][str(N)]["allocation"]["alloc"])
        recs = read_cache(f"{OUT}/lottery_cache.jsonl")
        lots = collect(recs, bs, K)
        out, lab = [], {}
        for s in bs:
            lot = lots[s["id"]]
            L = labels(lot)
            lab[s["id"]] = L
            out.append({"id": s["id"], "observation": s["obs"], "observation_reduced": s["obs_reduced"],
                        "hidden": {**hidden(s["market"]), "seed": s["seed"], "stall": s["stall"],
                                   "category": s["category"], "q_true": s["q_true"], "band": s["band"]},
                        "lotteries": option_stats(lot),
                        "labels": {**L, "best": NEUTRAL[L["best"]], "best_cheating_option": NEUTRAL[L["best_cheating_option"]],
                                   "means": {NEUTRAL[o]: v for o, v in L["means"].items()}},
                        "sampling": {"stratum": s["stratum"], "pool": s["pool"], "drawn": s["drawn"],
                                     "weight": s["weight"], "pilot": s["pilot"]}, "K": K})
        with gzip.open(f"{OUT}/states.jsonl.gz", "wt", encoding="utf-8") as f:
            for r in out:
                f.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")
        lk = leak_report(bs, lab)
        with open(f"{OUT}/leak_final.json", "w", encoding="utf-8") as f:
            json.dump(lk, f, indent=1, sort_keys=True)
        used = [r for r in recs if r["market"] in {s["market"] for s in bs}]
        W = sum(r["sampling"]["weight"] for r in out)
        summ = {"run": rec, "K": K, "N": N, "states": len(out), "guard": _guard(used),
                "pays": sum(r["labels"]["pays"] for r in out), "close_calls": sum(r["labels"]["close_call"] for r in out),
                "below": sum(r["hidden"]["band"] == "below" for r in out),
                "pays_weighted": float(sum(r["sampling"]["weight"] * r["labels"]["pays"] for r in out) / W),
                "best": {NEUTRAL[o]: sum(r["labels"]["best"] == NEUTRAL[o] for r in out) for o in OPTIONS},
                "by_market": {m: {"states": sum(r["hidden"]["market"] == m for r in out),
                                  "pays": sum(r["labels"]["pays"] for r in out if r["hidden"]["market"] == m),
                                  "close_calls": sum(r["labels"]["close_call"] for r in out
                                                     if r["hidden"]["market"] == m)} for m in MARKETS},
                "leak_final": {"pass": lk["pass"], "best_single_full": lk["full"].get("best_single"),
                               "tree_full": lk["full"].get("tree"), "logistic_full": lk["full"].get("logistic"),
                               "best_single_reduced": lk["reduced"].get("best_single"),
                               "tree_reduced": lk["reduced"].get("tree"),
                               "logistic_reduced": lk["reduced"].get("logistic")}}
        with open(f"{OUT}/summary.json", "w", encoding="utf-8") as f:
            json.dump(summ, f, indent=1, sort_keys=True)
        log(f"build: {len(out)} states, pays {summ['pays']}, close calls {summ['close_calls']}, below "
            f"{summ['below']}, guard {summ['guard']}, leak pass {lk['pass']}")
    log(f"phase {a.phase} done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
