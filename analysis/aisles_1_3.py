"""Stage 2 of runs/plan_autonomous_2026-11-27.md: aisles with real margins, verifiability, solvency and rent
(engine 1.3.0, rule-based only).

Predictions PA1-PA4, PB1-PB3 and PC1-PC2 were fixed in the plan (committed c0add7b, 2026-11-26) before any run.
Choices this script makes that the plan leaves open, written down here before any pilot or main chain (2026-11-26):

  Market: the v1.0.0 reference market (configs/reference_1_0.json: choice set m 3, stars at 0.02, random tie-break,
    lexicographic choice, brands on with premium 0.4, collectible fines, 2 patrolling inspectors, 30 days, rule
    agents) with these overrides only:
      t40 = the reference's shares (tourist 0.4, local 0.3, expert 0.3), locals inspect (local_inspect_prob 1.0);
      t100 = tourist 1.0, local 0, expert 0;
      inspectors.detect_scale per cell (Run C, which the plan gives no detect_scale: the reference's 1.0).
  gamma (the plan's market.gamma) is the engine's buyers.position_rent, 0 in the reference. "gamma_tourist 1.0 and
    gamma_local 0.2" is buyers.gamma_by_profile {"tourist": 1.0, "local": 0.2}; experts keep position_rent 0. In Run B
    gamma is on in all 8 cells (the plan lists it with the rent factor, which it conditions); in Run C in all 6.
  Profiles (categories.profiles): Run A gives all three aisles one synthetic profile (margin keys + verifiability keys);
    Runs B and C give each aisle its Stage 1 profile. baseline_gross_cents per category comes from the calibration.
  Calibration (the plan: "calibrated in the pilot from honest never chains"): on the pilot seeds 900-902, one never
    chain per calibration scenario with the scenario's settings but no fixed cost, solvency off and rent alpha 0:
      Run A: one scenario per cell (margin x verifiability x verification x detect_scale);
      Run B: one per detect_scale (start cash and alpha do not change a chain without fixed cost, solvency or rent);
      Run C: one per verification level.
    baseline_gross_cents[c] = mean daily gross profit (revenue - unit cost) over the genuine stall-days in the market
    of category c, pooled over the 3 seeds. The rent table (Runs B and C): spots are grouped by category and by their
    rank from the nearer end of the aisle, k = min(rank from the left end, rank from the right end) in 0..3 (4 spots
    per group: both ends, both sides); A(c, k) = mean daily gross of the genuine stall-days in group (c, k) minus the
    mean over the four groups of c (the mean spot); every spot of the group gets A(c, k). A group with no genuine
    stall-day gets 0 and is flagged. The calibration is written to runs/aisles_calibration.json and frozen for the main
    runs.
  Benchmark: as the verification run, candidates never and bust-out on day 20, 25, 28, 29, 30, the unfloored gain
    primary. The 3 genuine stalls per seed are drawn from default_rng([seed, 17]), one per aisle in the order fish,
    electronics, designer (uniformly among that aisle's genuine stalls), so every seed has one stall per aisle and the
    per-aisle estimands are paired by seed. (The verification run drew 3 from all genuine stalls; logged as a
    deviation.)
  Primary estimand (plan): a stall's gain as a share of its own honest profit over the same window, the 30 days:
    gain_unfloored / never_total, both net of fixed cost and rent. When never_total <= 0 the share is undefined: the
    stall is left out of that seed's mean and counted. Per seed: pooled = the mean over its defined stalls; per aisle =
    that aisle's stall. Comparisons pair seeds where both sides are defined. Secondary: dollars, and base-price units
    (gain / the category's base price), with the same pairing.
  Verdicts: mean and 95% t interval over seeds, unadjusted; supported if the interval lies on the predicted side of
    0, contradicted if wholly on the other side, else not supported.
    PA1 (t40, ds 0): hard - easy > 0 at thin and at fat margin (two tests; PA1 supported if both are).
    PA2 (t40, ds 0): thin - fat > 0 at easy and at hard verifiability (two tests).
    PA3 (ds 1): gain < 0 in each of the 8 cells (4 profiles x t40, t100).
    PB1 (ds 0, alpha 0): start cash 2 - start cash 20 > 0, pooled over aisles.
    PB2 (ds 0, start cash 20, alpha 0): designer - fish > 0 (paired by seed).
    PC1 (t40, alpha 0): deceptive share of units sold at entrance spots (k <= 1) - at the other spots > 0, per seed
      over all three aisles and 30 days.
  Exploratory: PA4, PB3, PC2 as listed in the plan.

Gates (pilot, seeds 900-902): G1 pipelines end to end; G2 identities (a: 1.3.0 at its defaults reproduces cached
1.2.0 price-war never chains; b: every cell's cost targets hold to the cent; c: the calibration and rent table
reproduce from a second calculation and a rerun chain); G3 timing <= 14 h (if over: Randall's instruction of
2026-11-26, run the full design and log the deviation); G4 exits per cell, STOP if any cell's never chains exit more
than half of all stalls before day 10; G5 stuck, parked and idle counts 0.

Changes after the first pilot (2026-11-26; deviations in runs/STATUS.md, decided by Randall before any main-run result;
the first pilot's outputs are kept as run in runs/pilot_aisles_130/):
  D3  exit_reason (insolvency / other) in every job record, read from the outcome only.
  D4  bug fix: the observers are installed once per process (the first pilot stacked them per job).
  D5  primary estimand: per aisle and seed, (sum of gains) / (sum of never-chain profits) over the sampled stalls
      (pooled: the three stalls of the seed; per aisle: that aisle's stall, one per seed under D2), undefined when the
      sum is <= 0; mean and 95% t over seeds. Reported with the count of stall-seeds whose never-chain profit is <= 0.
      The per-stall mean of ratios above is kept as the secondary figure.
  D6  engine 1.3.1: each stall's fixed cost is fixed_cost_share x its own type's baseline gross (calibrated per
      category and type in the same calibration chains), floored at 0; start cash and credit stay on the genuine
      baseline. Seconds get seconds_cost_share = the genuine cost_share of the profile (PLACEHOLDER).
  D7  gates: G2d, seconds baseline gross > 0 in every category of every calibration scenario; G4b, genuine stalls
      exiting before day 10 <= 5% in every cell (G4 still applies). Exits by type and reason in every cell are an
      exploratory outcome. The thin-margin genuine exits are kept, not calibrated away.

Compute (plan): 7 workers at normal priority, caffeinate, free-memory guard on, blocks of at most 10 h.

    .venv/bin/python -m analysis.aisles_1_3 --phase pilot
    .venv/bin/python -m analysis.aisles_1_3 --phase run --runs A --max-secs 36000
    .venv/bin/python -m analysis.aisles_1_3 --phase analyse --runs A
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

import numpy as np

import analysis.chainrun as CR
import analysis.liability as LB
from analysis.capture import memory_state
from engine import ENGINE_VERSION, benchmark
from engine import bazaar as EB
from engine import categories as CAT
from engine import days as DAYS
from engine.config import load
from engine.metrics import mean_ci
from engine.world import position_ranks

REF = "configs/reference_1_0.json"
NEVER = benchmark.NEVER
CANDS = [20, 25, 28, 29, 30]
CATS = ("fish", "electronics", "designer")
SAMPLE_STREAM = 17
PILOT = [900, 901, 902]
SEEDS = {"A": list(range(700, 720)), "B": list(range(720, 740)), "C": list(range(740, 760))}
OUT = "runs"
CAL_FILE = f"{OUT}/aisles_calibration.json"
CACHE = f"{OUT}/aisles_cache.jsonl"
PILOT_DIR = f"{OUT}/pilot_aisles"
TIME_LIMIT_H = 14.0

# The plan's Stage 1 table (PLACEHOLDER values), per aisle.
# D6 (engine 1.3.1, Randall 2026-11-26): seconds_cost_share = the genuine cost_share of the same profile (PLACEHOLDER).
REAL = {"fish": {"cost_share": 0.70, "cheap_share": 0.80, "fixed_cost_share": 0.90, "inspect_sigma": 0.15,
                 "inspect_cost_mult": 1.0, "review_accuracy": 0.95, "seconds_cost_share": 0.70},
        "electronics": {"cost_share": 0.77, "cheap_share": 0.55, "fixed_cost_share": 0.85, "inspect_sigma": 0.02,
                        "inspect_cost_mult": 0.5, "review_accuracy": 0.90, "seconds_cost_share": 0.77},
        "designer": {"cost_share": 0.20, "cheap_share": 0.30, "fixed_cost_share": 0.50, "inspect_sigma": 0.25,
                     "inspect_cost_mult": 3.0, "review_accuracy": 0.60, "seconds_cost_share": 0.20}}
MARGIN = {"thin": {"cost_share": 0.70, "cheap_share": 0.80, "fixed_cost_share": 0.90, "seconds_cost_share": 0.70},
          "fat": {"cost_share": 0.20, "cheap_share": 0.30, "fixed_cost_share": 0.50, "seconds_cost_share": 0.20}}
TYPES = ("genuine", "seconds", "deceptive")
G4B_LIMIT = 0.05
VERIF = {"easy": {"inspect_sigma": 0.02, "inspect_cost_mult": 0.5, "review_accuracy": 0.95},
         "hard": {"inspect_sigma": 0.25, "inspect_cost_mult": 3.0, "review_accuracy": 0.60}}
SHARES = {"t40": {"tourist": 0.4, "local": 0.3, "expert": 0.3}, "t100": {"tourist": 1.0, "local": 0.0, "expert": 0.0}}
GAMMA = {"tourist": 1.0, "local": 0.2}

CELLS_A = [("A", m, v, t, ds) for m in MARGIN for v in VERIF for t in SHARES for ds in (0.0, 1.0)]
CELLS_B = [("B", cash, al, ds) for cash in (2.0, 20.0) for al in (0.0, 1.0) for ds in (0.0, 1.0)]
CELLS_C = [("C", al, t) for al in (0.0, 0.5, 1.0) for t in SHARES]
CELLS = {"A": CELLS_A, "B": CELLS_B, "C": CELLS_C}


def cell_name(c) -> str:
    if c[0] == "A":
        return f"A|{c[1]}|{c[2]}|{c[3]}|ds{c[4]:g}"
    if c[0] == "B":
        return f"B|cash{c[1]:g}|a{c[2]:g}|ds{c[3]:g}"
    return f"C|a{c[1]:g}|{c[2]}"


def cell_from(name: str):
    for cs in CELLS.values():
        for c in cs:
            if cell_name(c) == name:
                return c
    raise KeyError(name)


def cal_group(c) -> str:
    if c[0] == "A":
        return "cal|" + cell_name(c)
    if c[0] == "B":
        return f"cal|B|ds{c[3]:g}"
    return f"cal|C|{c[2]}"


def cal_groups(runs) -> list[str]:
    out = []
    for r in runs:
        for c in CELLS[r]:
            g = cal_group(c)
            if g not in out:
                out.append(g)
    return out


def _cell_parts(c) -> dict:
    """t, ds, per-aisle profile (without baseline), gamma, solvency, start cash, alpha of a cell."""
    if c[0] == "A":
        p = {**MARGIN[c[1]], **VERIF[c[2]]}
        return {"t": c[3], "ds": c[4], "prof": {k: dict(p) for k in CATS}, "gamma": None, "cash": 10.0, "alpha": 0.0}
    if c[0] == "B":
        return {"t": "t40", "ds": c[3], "prof": {k: dict(v) for k, v in REAL.items()}, "gamma": GAMMA,
                "cash": c[1], "alpha": c[2]}
    return {"t": c[2], "ds": 1.0, "prof": {k: dict(v) for k, v in REAL.items()}, "gamma": GAMMA, "cash": 10.0,
            "alpha": c[1]}


def _common(t: str, ds: float, gamma, seed: int) -> list[str]:
    ov = [f"seed={seed}", f"buyers.profile_shares={json.dumps(SHARES[t])}", f"inspectors.detect_scale={ds!r}"]
    if t == "t40":
        ov.append("agents.params.rule_buyer.local_inspect_prob=1.0")
    if gamma:
        ov.append(f"buyers.gamma_by_profile={json.dumps(gamma)}")
    return ov


def cal_config(group: str, seed: int):
    """Calibration scenario: the cell's settings without fixed cost, solvency or rent."""
    if group.startswith("cal|A|"):
        P = _cell_parts(cell_from(group[4:]))
    elif group.startswith("cal|B|"):
        P = _cell_parts(("B", 20.0, 0.0, float(group.split("ds")[1])))
    else:
        P = _cell_parts(("C", 0.0, group.split("|")[2]))
    prof = {k: {kk: vv for kk, vv in v.items() if kk != "fixed_cost_share"} for k, v in P["prof"].items()}
    return load(REF, [*_common(P["t"], P["ds"], P["gamma"], seed), f"categories.profiles={json.dumps(prof)}"])


def cell_config(c, seed: int, cal: dict):
    P = _cell_parts(c)
    g = cal[cal_group(c)]
    prof = {k: {**v, "baseline_gross_cents": g["baseline"][k],
                "baseline_gross_by_type_cents": g["baseline_by_type"][k]} for k, v in P["prof"].items()}
    ov = [*_common(P["t"], P["ds"], P["gamma"], seed), f"categories.profiles={json.dumps(prof)}",
          "sellers.solvency.enabled=true", f"sellers.solvency.start_cash_days={P['cash']!r}"]
    if P["alpha"] > 0:
        ov += [f"market.rent.alpha={P['alpha']!r}", f"market.rent.table={json.dumps(g['rent_table'])}"]
    cfg = load(REF, ov)
    # the settings this cell must run
    assert cfg.inspectors.detect_scale == P["ds"] and cfg.buyers.profile_shares == SHARES[P["t"]]
    assert cfg.sellers.solvency.enabled and cfg.sellers.solvency.start_cash_days == P["cash"]
    assert float(cfg.market.rent.alpha) == P["alpha"] and cfg.buyers.gamma_by_profile == (P["gamma"] or {})
    return cfg


def sample_stalls(seed: int) -> list[str]:
    """One genuine stall per aisle (fish, electronics, designer), from default_rng([seed, 17])."""
    eng = EB.BazaarEngine(load(REF, [f"seed={seed}"]))
    rng = np.random.default_rng([seed, SAMPLE_STREAM])
    out = []
    for c in CATS:
        gen = [st.sid for st in sorted(eng.stalls, key=lambda s: s.idx) if st.stype == "genuine" and st.category == c]
        out.append(gen[int(rng.integers(len(gen)))])
    return out


def spot_classes(stalls) -> dict:
    """sid -> (category, k), k = rank from the nearer end of the aisle (0..3)."""
    out = {}
    for c in CATS:
        cs = [st for st in stalls if st.category == c]
        r = position_ranks(cs, True)
        top = max(r.values())
        for st in cs:
            out[st.sid] = (c, min(r[st.sid], top - r[st.sid]))
    return out


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ worker

_DAYREC: list = []


def _hooks() -> None:
    """Observer that changes nothing: after each market day, per stall the day's revenue, unit cost, units, type,
    whether it is in the market, its overhead, and the day's purchases aggregated by (buyer profile, stall)."""
    if getattr(EB.BazaarEngine.run, "_aisles_seen", False):
        return
    orig = EB.BazaarEngine.run

    def run(self, *a, **k):
        out = orig(self, *a, **k)
        buys: dict = {}
        for b in self.purchases:
            key = (b["buyer_profile"], b["stall"], b["stype"])
            d = buys.setdefault(key, [0, 0, 0.0, 0])
            d[0] += b["units"]
            d[1] += b["units"] if b["shortfall"] else 0
            d[2] += float(b["value"])
            d[3] += b["amount_cents"]
        _DAYREC.append({"day": self.day,
                        "stalls": {st.sid: [st.revenue_cents, st.cost_cents, st.units_sold, st.stype,
                                            st.exited_day is None or st.exited_day >= self.day, st.overhead_cents]
                                   for st in self.stalls},
                        "buys": [[*k, *v] for k, v in sorted(buys.items())]})
        return out

    run._aisles_seen = True
    EB.BazaarEngine.run = run


_INSTALLED = False


def _install() -> None:
    """D4 (bug fix, 2026-11-26): install the two observers once per process. Each checks only its own flag on the
    outermost BazaarEngine.run, so calling both on every job (as the pilot did) stacked two more layers per job and the
    k-th job in a worker recorded every day k times in _DAYREC (stall_agg, harm, ledger_days) and _PARKED."""
    global _INSTALLED
    if not _INSTALLED:
        LB._observe()
        _hooks()
        _INSTALLED = True


def _init_worker() -> None:
    """Normal priority (plan 2026-11-27): the parked-buyer observer only, no renice."""
    _install()


def _guard(out) -> dict:
    return CR.guard(out)


def job(j) -> dict:
    """j = (kind, name, seed, watch, stall, b, cal): kind "cal" (a calibration never chain; name = its scenario) or
    "bench" (name = a cell; stall None and b NEVER for the never chain); cal = the frozen calibration (None for "cal")."""
    kind, name, seed, watch, stall, b, cal = j
    _install()
    LB._PARKED.clear()
    _DAYREC.clear()
    t0 = time.time()
    if kind == "cal":
        cfg = cal_config(name, seed)
    else:
        cfg = cell_config(cell_from(name), seed, cal)
    c = benchmark.bust_config(cfg, stall, b)
    out = EB.run(c)
    secs = time.time() - t0
    eng_stalls = EB.BazaarEngine(cfg).stalls if kind == "cal" or b == NEVER else None
    rec = {"key": key(j), "kind": kind, "name": name, "seed": seed, "stall": stall, "b": str(b),
           "engine_version": ENGINE_VERSION, "secs": round(secs, 2), "guard": _guard(out),
           "exited": out["liability"]["exited"]}
    # D3 (Randall's G4 decision, 2026-11-26): exit reason, read from the outcome only. "insolvency" if the stall is in
    # some day's solvency exit list (the engine is rebuilt each day, so each day lists that day's exits), else "other".
    insolvent = {s for dd in out["days"] for s in (dd["outcome"].get("solvency") or {}).get("exits", [])}
    rec["exit_reason"] = {s: ("insolvency" if s in insolvent else "other") for s in rec["exited"]}
    if kind == "bench":
        rec["totals"] = {s: benchmark.stall_total(out, s) for s in watch}
        rec["busts"] = [(x["stall"], x["day"]) for dd in out["days"] for x in dd["bust_outs"]]
    if eng_stalls is not None:
        cls = spot_classes(eng_stalls)
        cat = {st.sid: st.category for st in eng_stalls}
        rec["spots"] = {s: list(cls[s]) for s in sorted(cls)}
        # per stall over the run: gross (revenue - unit cost) and stall-days in the market, by type; units by type
        agg: dict = {}
        for d in _DAYREC:
            for s, (rev, cost, units, stype, inm, ovh) in d["stalls"].items():
                a = agg.setdefault(s, {"stype": stype, "gross": 0, "days_in": 0, "units": 0, "units_dec": 0,
                                       "overhead": 0, "gross_by_day": []})
                if inm:
                    a["gross"] += rev - cost
                    a["days_in"] += 1
                a["units"] += units
                a["units_dec"] += units if stype == "deceptive" else 0
                a["overhead"] += ovh
                a["stype"] = stype
        rec["stall_agg"] = {s: {k: v for k, v in a.items() if k != "gross_by_day"} for s, a in sorted(agg.items())}
        harm: dict = {}
        for d in _DAYREC:
            for prof, s, stype, units, short, value, paid in d["buys"]:
                k = f"{prof}|{cat[s]}|{cls[s][1]}|{stype}"
                h = harm.setdefault(k, [0, 0, 0.0, 0])
                h[0] += units
                h[1] += short
                h[2] += value
                h[3] += paid
        rec["harm"] = harm
        rec["ledger_days"] = len(_DAYREC)
    return rec


def key(j) -> str:
    kind, name, seed, watch, stall, b, cal = j
    return f"{name}|{seed}|{stall}|{b}"


def jobs_for(runs, seeds_by_run: dict, cal: dict | None, samples: dict) -> list[tuple]:
    out = []
    for r in runs:
        for c in CELLS[r]:
            n = cell_name(c)
            for sd in seeds_by_run[r]:
                w = tuple(samples[sd])
                out.append(("bench", n, sd, w, None, NEVER, cal))
                if r == "C":
                    continue
                for s in w:
                    for b in CANDS:
                        out.append(("bench", n, sd, w, s, b, cal))
    return out


def cal_jobs(groups, seeds) -> list[tuple]:
    return [("cal", g, sd, (), None, NEVER, None) for g in groups for sd in seeds]


# ------------------------------------------------------------------ runner (normal priority)

def _load() -> list[float]:
    return [round(x, 2) for x in os.getloadavg()]


def run_chains(a, jobs, cache_path, log, max_secs: float | None = None) -> tuple[list[dict], int, bool]:
    """As analysis/chainrun.run_chains, at normal priority, with an optional time limit after which no new chain starts
    (the running ones finish and are cached). Returns (records of the finished jobs, memory pauses, complete)."""
    done = {}
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                done[r["key"]] = r
    todo = [j for j in jobs if key(j) not in done]
    log(f"{len(jobs)} chains, {len(todo)} to run ({len(jobs) - len(todo)} cached); workers {a.workers}; "
        f"load {_load()}; memory {memory_state()}")
    t0, n, pauses = time.time(), 0, 0
    stopped = False
    cache = open(cache_path, "a", encoding="utf-8") if cache_path else None
    with ProcessPoolExecutor(a.workers, initializer=_init_worker) as ex:
        it = iter(todo)
        live: set = set()
        exhausted = False
        while live or not exhausted:
            while not exhausted and len(live) < a.workers:
                if max_secs is not None and time.time() - t0 > max_secs:
                    exhausted, stopped = True, True
                    log(f"time limit {max_secs:.0f} s reached: no new chains; {len(live)} running finish")
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
                if n % 50 == 0 or n == len(todo):
                    log(f"{n}/{len(todo)} chains, {time.time() - t0:.0f} s, load {_load()}, memory {memory_state()}")
    if cache:
        cache.close()
    recs = [done[key(j)] for j in jobs if key(j) in done]
    return recs, pauses, len(recs) == len(jobs) and not stopped


# ------------------------------------------------------------------ calibration

def calibrate(recs: list[dict], groups) -> dict:
    out = {}
    for g in groups:
        rs = [r for r in recs if r["kind"] == "cal" and r["name"] == g]
        num = {c: 0 for c in CATS}
        den = {c: 0 for c in CATS}
        tnum = {c: {t: 0 for t in TYPES} for c in CATS}
        tden = {c: {t: 0 for t in TYPES} for c in CATS}
        grp = {}
        for r in rs:
            for s, a in r["stall_agg"].items():
                c_ = r["spots"][s][0]
                tnum[c_][a["stype"]] += a["gross"]
                tden[c_][a["stype"]] += a["days_in"]
                if a["stype"] != "genuine":
                    continue
                c, k = r["spots"][s]
                num[c] += a["gross"]
                den[c] += a["days_in"]
                x = grp.setdefault((c, k), [0, 0])
                x[0] += a["gross"]
                x[1] += a["days_in"]
        base = {c: round(num[c] / den[c], 2) if den[c] else None for c in CATS}
        # D6: each type's own baseline (mean daily gross over its stall-days in the market), for the fixed cost
        btype = {c: {t: round(tnum[c][t] / tden[c][t], 2) if tden[c][t] else 0.0 for t in TYPES} for c in CATS}
        adv, flags = {}, []
        for c in CATS:
            for t in TYPES:
                if not tden[c][t]:
                    flags.append(f"{g}: no {t} stall-day in {c}; type baseline set to 0")
        for c in CATS:
            means = {}
            for k in range(4):
                x = grp.get((c, k))
                if x and x[1]:
                    means[k] = x[0] / x[1]
                else:
                    flags.append(f"{g}: no genuine stall-day at ({c}, {k}); advantage set to 0")
            mbar = float(np.mean(list(means.values()))) if means else 0.0
            for k in range(4):
                adv[f"{c}|{k}"] = round(means[k] - mbar, 2) if k in means else 0.0
        spots = rs[0]["spots"] if rs else {}
        table = {s: adv[f"{c}|{k}"] for s, (c, k) in sorted(spots.items())}
        out[g] = {"baseline": base, "baseline_by_type": btype, "advantage": adv, "rent_table": table,
                  "flags": flags, "seeds": sorted({r["seed"] for r in rs}), "stall_days": den,
                  "stall_days_by_type": tden}
    return out


# ------------------------------------------------------------------ endpoints

def _bench(recs, name):
    return {(r["seed"], r["stall"], r["b"]): r for r in recs if r["kind"] == "bench" and r["name"] == name}


def gains(recs, name, seeds, samples) -> dict:
    """{seed: {stall: {"never", "gain", "share", "best"}}} for a benchmark cell."""
    idx = _bench(recs, name)
    out = {}
    for sd in seeds:
        nv = idx.get((sd, None, NEVER))
        if nv is None:
            continue
        out[sd] = {}
        for s in samples[sd]:
            tot = {NEVER: nv["totals"][s]}
            for b in CANDS:
                r = idx.get((sd, s, str(b)))
                if r is None:
                    break
                tot[b] = r["totals"][s]
            else:
                G = benchmark.gain(tot)
                never = G["never"]
                out[sd][s] = {"never": never, "gain": G["gain_unfloored"], "best": G["best_day"],
                              "share": G["gain_unfloored"] / never if never > 0 else None}
    return out


def per_seed(G, seeds, samples, field="share", aisle=None) -> list:
    vals = []
    for sd in seeds:
        g = G.get(sd)
        if g is None:
            vals.append(None)
            continue
        idx = range(3) if aisle is None else [CATS.index(aisle)]
        xs = []
        for i in idx:
            s = samples[sd][i]
            xs.append(g[s][field] if s in g else None)
        xs = [x for x in xs if x is not None]
        vals.append(float(np.mean(xs)) if xs else None)
    return vals


def per_seed_ratio(G, seeds, samples, aisle=None) -> list:
    """D5 (Randall, 2026-11-26), the primary estimand: per seed, (sum of gains) / (sum of never-chain profits) over
    the sampled stalls (all three, or the aisle's), None when that sum is <= 0 or a stall is missing."""
    vals = []
    for sd in seeds:
        g = G.get(sd)
        idx = range(3) if aisle is None else [CATS.index(aisle)]
        ss = [samples[sd][i] for i in idx]
        if g is None or any(s not in g for s in ss):
            vals.append(None)
            continue
        den = sum(g[s]["never"] for s in ss)
        vals.append(sum(g[s]["gain"] for s in ss) / den if den > 0 else None)
    return vals


def honest_le0(G, samples, aisle=None) -> int:
    """D5: stall-seeds whose never-chain profit is <= 0 (reported with the estimand)."""
    return sum(1 for sd, g in G.items() for i, s in enumerate(samples[sd])
               if (aisle is None or CATS[i] == aisle) and s in g and g[s]["never"] <= 0)


def base_units(G, samples, cfg_base) -> None:
    for sd, g in G.items():
        for i, s in enumerate(samples[sd]):
            if s in g:
                g[s]["base_units"] = g[s]["gain"] / cfg_base[CATS[i]]
                g[s]["dollars"] = g[s]["gain"] / 100


def diff(a: list, b: list) -> dict:
    """Mean and 95% t interval of b - a over seeds where both are defined (b minus a, explicit)."""
    d = [y - x for x, y in zip(a, b) if x is not None and y is not None]
    return mean_ci(d)


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
    if s == "includes":
        return "not supported"
    return "contradicted"


def exits_summary(recs, name, seeds) -> dict:
    """Never chains of a cell: share of all stalls that left before day 10 and by day 30, and by type."""
    rs = [r for r in recs if r["kind"] == "bench" and r["name"] == name and r["b"] == NEVER and r["seed"] in seeds]
    early, total, n = 0, 0, 0
    by_type: dict = {}
    for r in rs:
        types = {s: a["stype"] for s, a in r["stall_agg"].items()}
        n += len(types)
        for s, d in r["exited"].items():
            total += 1
            early += d < 10
            by_type[types[s]] = by_type.get(types[s], 0) + 1
    # D7: exits by type and reason (exploratory outcome; G4b reads the genuine row)
    tr = {t: {"stalls": 0, "before10": 0, "by30": 0, "before10_insolvency": 0, "by30_insolvency": 0} for t in TYPES}
    for r in rs:
        types = {s: a["stype"] for s, a in r["stall_agg"].items()}
        for t in types.values():
            tr[t]["stalls"] += 1
        for s, d in r["exited"].items():
            x = tr[types[s]]
            ins = r.get("exit_reason", {}).get(s) == "insolvency"
            x["by30"] += 1
            x["before10"] += d < 10
            x["by30_insolvency"] += ins
            x["before10_insolvency"] += ins and d < 10
    for t in TYPES:
        tr[t]["share_before10"] = tr[t]["before10"] / tr[t]["stalls"] if tr[t]["stalls"] else None
    return {"chains": len(rs), "stalls": n, "exit_before_day10": early, "share_before_day10": early / n if n else None,
            "exit_by_day30": total, "share_by_day30": total / n if n else None, "by_type": by_type,
            "by_type_reason": tr}


def entrance_gap(recs, name, seeds) -> dict:
    """Run C: per seed, deceptive share of units at entrance spots (k <= 1) minus at the others, all aisles and per
    aisle; and exits and buyer harm by spot (exploratory)."""
    rs = {r["seed"]: r for r in recs if r["kind"] == "bench" and r["name"] == name and r["b"] == NEVER}
    out = {"gap": [], "entrance": [], "rest": [], **{f"gap_{c}": [] for c in CATS}}
    harm = {}
    for sd in seeds:
        r = rs.get(sd)
        if r is None:
            for k in out:
                out[k].append(None)
            continue
        u = {}
        for s, a in r["stall_agg"].items():
            c, k = r["spots"][s]
            e = "ent" if k <= 1 else "rest"
            for key_ in (("all", e), (c, e)):
                x = u.setdefault(key_, [0, 0])
                x[0] += a["units_dec"]
                x[1] += a["units"]
        sh = {k: (v[0] / v[1] if v[1] else None) for k, v in u.items()}
        ent, rest = sh.get(("all", "ent")), sh.get(("all", "rest"))
        out["entrance"].append(ent)
        out["rest"].append(rest)
        out["gap"].append(ent - rest if ent is not None and rest is not None else None)
        for c in CATS:
            a, b = sh.get((c, "ent")), sh.get((c, "rest"))
            out[f"gap_{c}"].append(a - b if a is not None and b is not None else None)
        for k, (units, short, value, paid) in r["harm"].items():
            prof, c, cls, stype = k.split("|")
            e = "ent" if int(cls) <= 1 else "rest"
            h = harm.setdefault(f"{prof}|{e}", [0, 0, 0.0, 0])
            h[0] += units
            h[1] += short
            h[2] += value
            h[3] += paid
    out["harm"] = {k: {"units": v[0], "short_share": v[1] / v[0] if v[0] else None,
                       "surplus_per_unit_cents": (v[2] - v[3]) / v[0] if v[0] else None} for k, v in sorted(harm.items())}
    return out


# ------------------------------------------------------------------ gates

def g2_defaults_reproduce(log) -> dict:
    """1.3.0 at its defaults against cached 1.2.0 price-war never chains (A|RI|ds0|lex and A|RI|ds1|lex, seed 500)."""
    import analysis.price_war as PW
    cache = f"{OUT}/price_war_cache.jsonl"
    want = {}
    with open(cache, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["cell"] in ("A|RI|ds0|lex", "A|RI|ds1|lex") and r["seed"] == 500 and r["rec"]["b"] == NEVER:
                want[r["key"]] = r
    res = {}
    samples = {500: LB.sample_stalls(500)}
    for k, r in sorted(want.items()):
        c = next(c for c in PW.CELLS if PW.cell_name(c) == r["cell"])
        spec = next(s for s in PW.specs(c, [500], samples) if PW.key((c, s)) == k)
        got = PW.job((c, spec))
        res[k] = got["rec"] == r["rec"]
        log(f"G2a {k}: {'identical' if res[k] else 'DIFFERENT'}")
    return {"chains": res, "pass": bool(res) and all(res.values())}


def g2_costs(cal) -> dict:
    bad = []
    for r in "ABC":
        for c in CELLS[r]:
            cfg = cell_config(c, PILOT[0], cal)
            for cat in CATS:
                p = CAT.profile(cfg, cat)
                qh, ql = sum(cfg.stalls.q_high) / 2, sum(cfg.stalls.q_low) / 2
                g = p["cost_share"] * CAT.genuine_price_at_top(cfg, cat)
                if abs(CAT.unit_cost(cfg, cat, qh) - g) > 0.5 or \
                        abs(CAT.unit_cost(cfg, cat, ql) - p["cheap_share"] * g) > 0.5:
                    bad.append(f"{cell_name(c)} {cat}")
                gs = p["seconds_cost_share"] * CAT.seconds_price_at_top(cfg, cat)        # D6: seconds target
                if abs(CAT.unit_cost(cfg, cat, ql, "seconds") - gs) > 0.5:
                    bad.append(f"{cell_name(c)} {cat} seconds")
    return {"bad": bad, "pass": not bad}


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
    ap.add_argument("--runs", default="A,B,C")
    ap.add_argument("--workers", type=int, default=7)
    ap.add_argument("--min-swap-mb", type=float, default=0.0)
    ap.add_argument("--min-free-pct", type=float, default=10.0)
    ap.add_argument("--max-secs", type=float, default=None)
    ap.add_argument("--tests", default="")
    a = ap.parse_args()
    runs = [r for r in a.runs.split(",") if r]
    os.makedirs(PILOT_DIR, exist_ok=True)
    if a.phase == "pilot":
        log = CR.file_logger(f"{PILOT_DIR}/aisles_run.log")
        log(f"run record {json.dumps(run_record(a, 'pilot'), sort_keys=True)}")
        t0 = time.time()
        groups = cal_groups(runs)
        cache = f"{PILOT_DIR}/aisles_pilot_cache.jsonl"
        crec, p1, ok1 = run_chains(a, cal_jobs(groups, PILOT), cache, log)
        cal = calibrate(crec, groups)
        cal_again = calibrate(json.loads(json.dumps(crec)), groups)
        with open(CAL_FILE, "w", encoding="utf-8") as f:
            json.dump({"made": time.strftime("%Y-%m-%d %H:%M:%S"), "seeds": PILOT, "groups": cal}, f, indent=1,
                      sort_keys=True)
        log(f"calibration: {len(groups)} scenarios, written to {CAL_FILE}; flags "
            f"{sum(len(v['flags']) for v in cal.values())}")
        # G2c: a calibration chain rerun gives the same record
        j0 = cal_jobs(groups[:1], PILOT[:1])[0]
        _init_worker()
        again = job(j0)
        first = next(r for r in crec if r["key"] == key(j0))
        same = {k: again[k] == first[k] for k in ("stall_agg", "spots", "exited", "harm")}
        samples = {sd: sample_stalls(sd) for sd in PILOT}
        tb = time.time()
        brec, p2, ok2 = run_chains(a, jobs_for(runs, {r: PILOT for r in runs}, cal, samples), cache, log)
        wall_b = time.time() - tb
        n_b = len(jobs_for(runs, {r: PILOT for r in runs}, cal, samples))
        allrec = crec + brec
        guard = {k: sum(r["guard"][k] for r in allrec) for k in ("stuck_buyers", "idle_choosers", "parked",
                                                                  "fallbacks", "buyer_days")}
        g4 = {cell_name(c): exits_summary(brec, cell_name(c), PILOT) for r in runs for c in CELLS[r]}
        n_main = len(jobs_for(runs, SEEDS, cal, {sd: ("a", "b", "c") for r in runs for sd in SEEDS[r]}))
        secs = [r["secs"] for r in brec]
        proj_h = wall_b * n_main / max(n_b, 1) / 3600
        gates = {
            "G1": {"pass": ok1 and ok2 and len(brec) == n_b, "cal_chains": len(crec), "bench_chains": len(brec)},
            "G2a": g2_defaults_reproduce(log),
            "G2b": g2_costs(cal),
            "G2c": {"rerun_identical": same, "recalc_identical": cal == cal_again,
                    "pass": all(same.values()) and cal == cal_again},
            "G3": {"projected_h": round(proj_h, 2), "limit_h": TIME_LIMIT_H, "pass": proj_h <= TIME_LIMIT_H,
                   "main_chains": n_main, "pilot_bench_chains": n_b, "pilot_bench_wall_s": round(wall_b, 1),
                   "chain_cpu_s_mean": round(float(np.mean(secs)), 2) if secs else None},
            "G4": {"cells": g4, "max_share_before_day10": max(v["share_before_day10"] or 0 for v in g4.values()),
                   "pass": all((v["share_before_day10"] or 0) <= 0.5 for v in g4.values())},
            # D7 (Randall, 2026-11-26): genuine stalls exiting before day 10 <= 5% in every cell
            "G4b": {"genuine_share_before10": {n: v["by_type_reason"]["genuine"]["share_before10"] for n, v in g4.items()},
                    "limit": G4B_LIMIT,
                    "pass": all((v["by_type_reason"]["genuine"]["share_before10"] or 0) <= G4B_LIMIT
                                for v in g4.values())},
            # D6 test: seconds gross > 0 in every category in the calibration chains
            "G2d": {"seconds_baseline": {g: cal[g]["baseline_by_type"] and {c: cal[g]["baseline_by_type"][c]["seconds"]
                                                                            for c in CATS} for g in cal},
                    "pass": all(cal[g]["baseline_by_type"][c]["seconds"] > 0 for g in cal for c in CATS)},
            "G5": {"guard": guard, "pass": not (guard["stuck_buyers"] or guard["idle_choosers"] or guard["parked"]
                                                or guard["fallbacks"])},
            "samples": samples, "calibration_flags": {g: v["flags"] for g, v in cal.items() if v["flags"]},
            "wall_s": round(time.time() - t0, 1), "memory_pauses": p1 + p2,
        }
        gates["all_pass_except_G3"] = all(gates[g]["pass"] for g in ("G1", "G2a", "G2b", "G2c", "G2d", "G4", "G4b",
                                                                     "G5"))
        with open(f"{PILOT_DIR}/aisles_pilot_gates.json", "w", encoding="utf-8") as f:
            json.dump(gates, f, indent=1, sort_keys=True, default=str)
        log(f"pilot: G1 {gates['G1']['pass']}, G2a {gates['G2a']['pass']}, G2b {gates['G2b']['pass']}, G2c "
            f"{gates['G2c']['pass']}, G2d {gates['G2d']['pass']}, G3 {proj_h:.1f} h (limit {TIME_LIMIT_H}), G4 max "
            f"early-exit share {gates['G4']['max_share_before_day10']:.3f}, G4b {gates['G4b']['pass']}, G5 {guard}; "
            f"all pass except G3: "
            f"{gates['all_pass_except_G3']}")
    elif a.phase == "run":
        log = CR.file_logger(f"{OUT}/aisles_run.log")
        log(f"run record {json.dumps(run_record(a, 'run ' + ','.join(runs)), sort_keys=True)}")
        cal = json.load(open(CAL_FILE, encoding="utf-8"))["groups"]
        samples = {sd: sample_stalls(sd) for r in runs for sd in SEEDS[r]}
        recs, pauses, complete = run_chains(a, jobs_for(runs, SEEDS, cal, samples), CACHE, log, a.max_secs)
        log(f"run {','.join(runs)}: {len(recs)} chains done, complete {complete}, memory pauses {pauses}")
    else:
        log = CR.file_logger(f"{OUT}/aisles_run.log")
        cal = json.load(open(CAL_FILE, encoding="utf-8"))["groups"]
        samples = {sd: sample_stalls(sd) for r in runs for sd in SEEDS[r]}
        jobs = jobs_for(runs, SEEDS, cal, samples)
        done = {}
        with open(CACHE, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                done[r["key"]] = r
        recs = [done[key(j)] for j in jobs if key(j) in done]
        log(f"analyse {','.join(runs)}: {len(recs)} of {len(jobs)} chains in the cache")
        res = analyse(recs, runs, samples, cal)
        for r in runs:
            with open(f"{OUT}/aisles_{r}.json", "w", encoding="utf-8") as f:
                json.dump(res[r], f, indent=1, sort_keys=True, default=str)
        log("analysis written: " + ", ".join(f"{OUT}/aisles_{r}.json" for r in runs))


def analyse(recs, runs, samples, cal) -> dict:
    from engine.config import load as _ld
    base_cents = _ld(REF).pricing.base_price_cents
    res = {}
    for r in runs:
        seeds = SEEDS[r]
        out = {"seeds": seeds, "cells": {}, "predictions": {}, "guard": {}}
        rs = [x for x in recs if x["name"].startswith(r + "|")]
        out["guard"] = {k: sum(x["guard"][k] for x in rs) for k in ("stuck_buyers", "idle_choosers", "parked",
                                                                    "fallbacks", "buyer_days")}
        out["chains"] = len(rs)
        if r in ("A", "B"):
            Gs = {}
            for c in CELLS[r]:
                n = cell_name(c)
                G = gains(recs, n, seeds, samples)
                base_units(G, samples, base_cents)
                Gs[n] = G
                cell = {"exits": exits_summary(recs, n, seeds),
                        "undefined_share": sum(1 for sd in G for s in G[sd] if G[sd][s]["share"] is None),
                        "honest_le0": {"pooled": honest_le0(G, samples), **{c_: honest_le0(G, samples, c_) for c_ in CATS}},
                        "ratio": {"pooled": mean_ci(per_seed_ratio(G, seeds, samples)),
                                  **{c_: mean_ci(per_seed_ratio(G, seeds, samples, c_)) for c_ in CATS}},
                        "per_seed_ratio": per_seed_ratio(G, seeds, samples),
                        "per_seed_ratio_by_aisle": {c_: per_seed_ratio(G, seeds, samples, c_) for c_ in CATS},
                        "best_day": {}}
                for f in ("share", "dollars", "base_units"):
                    cell[f] = {"pooled": mean_ci(per_seed(G, seeds, samples, f)),
                               **{c_: mean_ci(per_seed(G, seeds, samples, f, c_)) for c_ in CATS}}
                for sd in G:
                    for s in G[sd]:
                        b = str(G[sd][s]["best"])
                        cell["best_day"][b] = cell["best_day"].get(b, 0) + 1
                cell["per_seed_share"] = per_seed(G, seeds, samples, "share")
                cell["per_seed_share_by_aisle"] = {c_: per_seed(G, seeds, samples, "share", c_) for c_ in CATS}
                out["cells"][n] = cell
            def predictions(P):
                if r == "A":
                    pr = {}
                    for m in MARGIN:
                        st = diff(P(f"A|{m}|easy|t40|ds0"), P(f"A|{m}|hard|t40|ds0"))
                        pr[f"PA1|{m}"] = {"what": f"t40 ds0 {m}: hard - easy", "stat": st, "verdict": verdict(st, +1)}
                    for v in VERIF:
                        st = diff(P(f"A|fat|{v}|t40|ds0"), P(f"A|thin|{v}|t40|ds0"))
                        pr[f"PA2|{v}"] = {"what": f"t40 ds0 {v}: thin - fat", "stat": st, "verdict": verdict(st, +1)}
                    for m in MARGIN:
                        for v in VERIF:
                            for t in SHARES:
                                st = mean_ci(P(f"A|{m}|{v}|{t}|ds1"))
                                pr[f"PA3|{m}|{v}|{t}"] = {"what": f"ds1 {m} {v} {t}: gain share", "stat": st,
                                                          "verdict": verdict(st, -1)}
                    # PA4 exploratory: interaction at t40 ds0, t100 analogues
                    inter = [None if None in (a_, b_, c_, d_) else (d_ - c_) - (b_ - a_) for a_, b_, c_, d_ in
                             zip(P("A|fat|easy|t40|ds0"), P("A|fat|hard|t40|ds0"), P("A|thin|easy|t40|ds0"),
                                 P("A|thin|hard|t40|ds0"))]
                    pr["PA4|interaction|t40"] = {"what": "(thin hard - thin easy) - (fat hard - fat easy), t40 ds0",
                                                 "stat": mean_ci(inter), "verdict": "exploratory"}
                    for m in MARGIN:
                        st = diff(P(f"A|{m}|easy|t100|ds0"), P(f"A|{m}|hard|t100|ds0"))
                        pr[f"PA4|t100|PA1|{m}"] = {"what": f"t100 ds0 {m}: hard - easy", "stat": st,
                                                   "verdict": "exploratory"}
                    for v in VERIF:
                        st = diff(P(f"A|fat|{v}|t100|ds0"), P(f"A|thin|{v}|t100|ds0"))
                        pr[f"PA4|t100|PA2|{v}"] = {"what": f"t100 ds0 {v}: thin - fat", "stat": st,
                                                   "verdict": "exploratory"}
                    for k in ("PA1", "PA2"):
                        vs = [x["verdict"] for kk, x in pr.items() if kk.startswith(k + "|")]
                        pr[k] = {"verdict": "supported" if all(x == "supported" for x in vs) else
                                 ("partly supported" if any(x == "supported" for x in vs) else
                                  ("contradicted" if all(x == "contradicted" for x in vs) else "not supported")),
                                 "parts": vs}
                    vs = [x["verdict"] for kk, x in pr.items() if kk.startswith("PA3|")]
                    pr["PA3"] = {"verdict": "supported" if all(x == "supported" for x in vs) else
                                 ("partly supported" if any(x == "supported" for x in vs) else "not supported"),
                                 "parts": vs, "supported_cells": sum(x == "supported" for x in vs)}
                else:
                    pr = {}
                    st = diff(P("B|cash20|a0|ds0"), P("B|cash2|a0|ds0"))
                    pr["PB1"] = {"what": "ds0 a0: start cash 2 - start cash 20, pooled", "stat": st,
                                 "verdict": verdict(st, +1)}
                    st = diff(P("B|cash20|a0|ds0", "fish"), P("B|cash20|a0|ds0", "designer"))
                    pr["PB2"] = {"what": "ds0 cash20 a0: designer - fish", "stat": st, "verdict": verdict(st, +1)}
                    for aisle in CATS:
                        st = diff(P("B|cash20|a0|ds0", aisle), P("B|cash2|a0|ds0", aisle))
                        pr[f"PB3|cash|{aisle}"] = {"what": f"ds0 a0 {aisle}: cash 2 - cash 20", "stat": st,
                                                   "verdict": "exploratory"}
                    for cash in ("2", "20"):
                        st = diff(P(f"B|cash{cash}|a0|ds0"), P(f"B|cash{cash}|a1|ds0"))
                        pr[f"PB3|alpha|cash{cash}"] = {"what": f"ds0 cash {cash}: alpha 1 - alpha 0", "stat": st,
                                                       "verdict": "exploratory"}
                    st = diff(P("B|cash20|a0|ds1"), P("B|cash2|a0|ds1"))
                    pr["PB3|ds1|PB1"] = {"what": "ds1 a0: cash 2 - cash 20", "stat": st, "verdict": "exploratory"}
                    st = diff(P("B|cash20|a0|ds1", "fish"), P("B|cash20|a0|ds1", "designer"))
                    pr["PB3|ds1|PB2"] = {"what": "ds1 cash20 a0: designer - fish", "stat": st, "verdict": "exploratory"}
                return pr

            # D5 (Randall, 2026-11-26): primary = per-seed ratio of sums; secondary = per-stall mean of ratios
            pr = predictions(lambda n, aisle=None: per_seed_ratio(Gs[n], seeds, samples, aisle))
            sec = predictions(lambda n, aisle=None: per_seed(Gs[n], seeds, samples, "share", aisle))
            for k, v in pr.items():
                v["secondary_mean_of_ratios"] = {kk: sec[k][kk] for kk in ("stat", "verdict", "parts") if kk in sec[k]}
            out["predictions"] = pr
        else:
            for c in CELLS[r]:
                n = cell_name(c)
                eg = entrance_gap(recs, n, seeds)
                out["cells"][n] = {"exits": exits_summary(recs, n, seeds), "gap": mean_ci(eg["gap"]),
                                   "entrance": mean_ci(eg["entrance"]), "rest": mean_ci(eg["rest"]),
                                   **{f"gap_{c_}": mean_ci(eg[f"gap_{c_}"]) for c_ in CATS},
                                   "per_seed_gap": eg["gap"], "harm": eg["harm"]}
            st = out["cells"]["C|a0|t40"]["gap"]
            out["predictions"] = {"PC1": {"what": "t40 a0: deceptive share of units, entrance - rest",
                                          "stat": st, "verdict": verdict(st, +1)}}
            for al in ("0.5", "1"):
                for t in SHARES:
                    a0 = entrance_gap(recs, f"C|a0|{t}", seeds)["gap"]
                    a1 = entrance_gap(recs, f"C|a{al}|{t}", seeds)["gap"]
                    out["predictions"][f"PC2|alpha{al}|{t}"] = {"what": f"{t}: gap at alpha {al} - gap at alpha 0",
                                                                "stat": diff(a0, a1), "verdict": "exploratory"}
        res[r] = out
    return res


if __name__ == "__main__":
    main()
