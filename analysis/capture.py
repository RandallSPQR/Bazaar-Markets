"""Reputation speed and capture: the brand dilemma's real boundary (rule-based only).

Prespecified design (spec and predictions written 2026-11-07, before any run). Engine 0.11.0.
Decisions taken 2026-11-07 before any run: engine numbered 0.11.0 (there was no 0.11.0; defaults
reproduce 0.10.0); primary outcome = the unfloored gain; tourists keep not seeing ratings and their
learning is measured by a sales proxy; a critic review scores true Q against the posted claim.

Common: D = 30 known to sellers; ratings public (visible to locals and experts); brands on, premium
0.4 (placeholder); budget 1.25 x base; search depth 2 for all profiles; 150 buyers; fresh
reopening; naive deceptive sellers (rule_deceptive); imitation off; genuine stalls always honest
(rule_honest; the benchmark switches the sampled stall to rule_genuine_bust_at).
  Stage A (speed): 0 inspectors, 0 critics; ratings.memory (lambda) {0.7, 0.9, 0.97} x tourist
    share {0.4, 0.8} (locals and experts split the rest evenly).
  Stage B (capture): 2 patrolling inspectors, not uniformed; 4 critics (sample 6, weight 5, tie
    delay 10, emb_max 10: placeholders); lambda 0.7; tourists 0.4; critics.tie_share {0, 0.3, 0.6}
    x embarrassment {off, on} x inspectors.capture {0, 0.5} (capture_effect 0.8, placeholder).
Seeds 52-66 (15), paired. Per seed, 3 genuine stalls drawn from numpy default_rng([seed, 17])
(the same stalls in every condition). Chains per seed and condition: one with nobody busting out
("never", shared by the 3 stalls) and one per stall and bust-out day b in {10, 20, 27}: 10.

Outcome: best-response gain per sampled stall over the 30-day total profit (engine/benchmark.py),
averaged over the 3 stalls per seed; paired by seed; unadjusted 95% t-intervals.
  Primary: gain_unfloored = max over b in {10, 20, 27} of total(b) - total(never) (can be < 0).
  Also reported for every prediction: the spec's gain_floored = max over {never, 10, 20, 27} - never.
  PS1 (confirmatory): at tourists 0.4, per-seed OLS slope of the gain over lambda > 0.
  PS2 (confirmatory): at lambda 0.9, gain(tourists 0.8) - gain(tourists 0.4) > 0.
  PK1 (confirmatory): embarrassment off, capture 0: per-seed slope of the gain over tie share > 0.
  PK2 (confirmatory): tie share 0.6, embarrassment off, capture 0: gain > 0.
  PK3 (confirmatory): tie share 0.3, embarrassment off: gain(capture 0.5) - gain(capture 0) > 0.
  Exploratory: embarrassment's added effect; best bust-out day by condition; harm by buyer profile
  when the sampled stall busts out at its best day (bust chain - never chain, days b..30:
  shortfall share of purchases; purchase surplus per buyer net of inspection costs); how long
  negative information stays semi-private (days from bust-out to the first negative critic review
  written and filed, to the first end-of-day rating below tau, and to the first day the stall's
  tourist units fall below half their mean over the 5 days before the bust-out).
Gates: Stage A - in lambda 0.7 / tourists 0.4 the mean unfloored gain is <= 0 (the sign of the
e5d7818 result; the interval may include 0). Stage B - with tie share 0, embarrassment off,
capture 0, no critic review is ever held (checked on every chain of that condition, and reported
for seed 52's never chain).

Run (one stage at a time; nothing else may change between stages):
    .venv/bin/python -m analysis.capture --stage A --tests "<result>"
    .venv/bin/python -m analysis.capture --stage B --tests "<result>"
Workers run at nice 19. Before each new chain the runner checks free swap and the memory-pressure
free share and waits while either is below its floor (--min-swap-mb, --min-free-pct). Finished
chains go to runs/capture_cache_<stage>.jsonl as they finish, so a stopped run resumes where it
stopped (the cache is not committed). Seeds used by earlier runs are refused; 400-401 are reserved
for this script's pipeline check (--pipeline-check), whose outputs are not kept.

This script only reads engine outputs; it changes nothing in the engine.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

import numpy as np

from analysis.counterfeit import STYLE, _ci, _d, _git, _load, _num, _pct, _t, _verdict, mean_ci, paired_diff
from analysis.floors import floor_flags, floor_series
from cli.sweep import parse_seeds
from engine import ENGINE_VERSION, bazaar, benchmark
from engine.config import load
from engine.jsonlog import JsonlLog

DAYS = 30
CANDS = [10, 20, 27]
NEVER = benchmark.NEVER
N_SAMPLE = 3
SAMPLE_STREAM = 17
TAU = 0.5
PROFILES = ["tourist", "local", "expert"]
LAMBDAS = [0.7, 0.9, 0.97]
TOURISTS = {"t40": '{"tourist":0.4,"local":0.3,"expert":0.3}', "t80": '{"tourist":0.8,"local":0.1,"expert":0.1}'}
TIES = [0.0, 0.3, 0.6]
EMB = [False, True]
CAPS = [0.0, 0.5]
USED = set(range(0, 52)) | set(range(100, 105)) | {200, 201, 300, 301}
PIPELINE = {400, 401}
COMMON = ["ratings.mode=public", "brands.enabled=true", "brands.premium=0.4", "market.horizon_known=true",
          "evolution.revise_prob=0", "evolution.mutation_prob=0", "buyers.count=150",
          "buyers.budget_factor_override=1.25", f"market.days={DAYS}", "agents.seller.deceptive=rule_deceptive",
          "agents.params.rule_deceptive.reopen=fresh", "agents.seller.genuine=rule_honest",
          'buyers.search_depth={"tourist":2,"local":2,"expert":2}']


def a_cond(lam, t) -> str:
    return f"A|lam{lam:g}|{t}"


def b_cond(tie, emb, cap) -> str:
    return f"B|tie{tie:g}|emb{int(emb)}|cap{cap:g}"


CONDS = {"A": [a_cond(lam, t) for t in TOURISTS for lam in LAMBDAS],
         "B": [b_cond(tie, e, c) for c in CAPS for e in EMB for tie in TIES]}


def overrides(cond: str) -> list[str]:
    parts = cond.split("|")
    if parts[0] == "A":
        lam, t = float(parts[1][3:]), parts[2]
        return [*COMMON, "inspectors.count=0", "inspectors.placement=patrolling", f"ratings.memory={lam}",
                f"buyers.profile_shares={TOURISTS[t]}"]
    tie, emb, cap = float(parts[1][3:]), parts[2] == "emb1", float(parts[3][3:])
    return [*COMMON, "inspectors.count=2", "inspectors.placement=patrolling", "inspectors.uniformed=false",
            "ratings.memory=0.7", f"buyers.profile_shares={TOURISTS['t40']}", "critics.count=4", "critics.sample=6",
            "critics.weight=5", "critics.tie_delay=10", "critics.emb_max=10", f"critics.tie_share={tie}",
            f"critics.embarrassment={'true' if emb else 'false'}", f"inspectors.capture={cap}",
            "inspectors.capture_effect=0.8"]


def config(cond: str, seed: int):
    return load(None, [*overrides(cond), f"seed={seed}"], mode="bazaar")


def sample_stalls(seed: int) -> list[str]:
    """3 genuine stalls from [seed, 17]. Stall types come from the world stream alone, so the draw
    is the same in every condition."""
    eng = bazaar.BazaarEngine(config(CONDS["A"][0], seed))
    gen = [st.sid for st in sorted(eng.stalls, key=lambda s: s.idx) if st.stype == "genuine"]
    pick = np.random.default_rng([seed, SAMPLE_STREAM]).choice(len(gen), size=N_SAMPLE, replace=False)
    return [gen[int(i)] for i in pick]


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ chains

class ProfileTap(JsonlLog):
    """Per day and buyer profile: buyers, purchases, shortfall purchases, value, spend and
    inspection costs; units each watched stall sold to each profile."""

    def __init__(self, watch):
        super().__init__(None, keep=False)
        self.watch = list(watch)
        self.day = 1
        self.prof: dict = {}
        self.days: dict = {}

    def _d(self):
        if self.day not in self.days:
            self.days[self.day] = {"buyers": {p: 0 for p in PROFILES}, "purchases": {p: 0 for p in PROFILES},
                                   "short": {p: 0 for p in PROFILES}, "value": {p: 0.0 for p in PROFILES},
                                   "paid": {p: 0 for p in PROFILES}, "inspect": {p: 0 for p in PROFILES},
                                   "units": {s: {p: 0 for p in PROFILES} for s in self.watch}}
        return self.days[self.day]

    def emit(self, ev, **f):
        if ev == "day_start":
            self.day = f["day"]
        elif ev == "world":
            d = self._d()
            self.prof = {}
            for p in f["people"]:
                if p["kind"] == "buyer":
                    self.prof[p["pid"]] = p["profile"]
                    d["buyers"][p["profile"]] += 1
        elif ev == "delta":
            if not f["buys"] and not f["inspects"]:
                return
            d = self._d()
            for b in f["buys"]:
                pr = b["buyer_profile"]
                d["purchases"][pr] += 1
                d["short"][pr] += bool(b["shortfall"])
                d["value"][pr] += b["value"]
                d["paid"][pr] += b["amount_cents"]
                if b["stall"] in d["units"]:
                    d["units"][b["stall"]][pr] += b["units"]
            for x in f["inspects"]:
                pr = self.prof.get(x["buyer"])
                if pr is not None:
                    d["inspect"][pr] += x["cost_cents"]


def _job(args) -> dict:
    stage, cond, seed, watch, stall, b = args
    c = benchmark.bust_config(config(cond, seed), stall, b)
    tap = ProfileTap(watch)
    out = bazaar.run(c, log=tap)
    days, delayed, crit = [], 0, {s: [] for s in watch}
    for dd in out["days"]:
        o = dd["outcome"]
        pt = o["seller_by_type"]
        cr = dd.get("critic_reviews")
        if cr is not None:
            delayed += sum(r["delay"] > 0 for r in cr["written"])
            for r in cr["written"]:
                if r["stall"] in crit:
                    crit[r["stall"]].append([r["day"], r["critic"], int(r["positive"]), r["delay"], r["file_day"]])
        days.append({"genuine_profit": pt["genuine"]["profit_per_stall_cents"] if "genuine" in pt else None,
                     "deceptive_profit": pt["deceptive"]["profit_per_stall_cents"] if "deceptive" in pt else None,
                     "shortfall_rate": o["shortfall_rate"], "surplus": o["buyer_surplus_mean_cents"],
                     "catches": o["catches"], "busted": o["brands"]["busted_stalls"], **floor_series(o),
                     "rating": {s: dd["brand_ratings"].get(dd["brands"][s]) for s in watch}})
    busts = [(x["stall"], x["day"]) for dd in out["days"] for x in dd["bust_outs"]]
    return {"key": f"{cond}|{seed}|{stall}|{b}", "stage": stage, "cond": cond, "seed": seed, "stall": stall, "b": b,
            "totals": {s: benchmark.stall_total(out, s) for s in watch}, "days": days, "busts": busts,
            "profile": {str(k): v for k, v in sorted(tap.days.items())}, "critic": crit,
            "delayed_reviews": delayed, "fallbacks": sum(x["outcome"]["fallbacks"]["buyer"] for x in out["days"])}


def jobs_for(stage: str, seeds: list[int], samples: dict) -> list[tuple]:
    out = []
    for seed in seeds:
        w = samples[seed]
        for cond in CONDS[stage]:
            out.append((stage, cond, seed, w, None, NEVER))
            for s in w:
                for b in CANDS:
                    out.append((stage, cond, seed, w, s, b))
    return out


def _key(j) -> str:
    return f"{j[1]}|{j[2]}|{j[4]}|{j[5]}"


# ------------------------------------------------------------------ memory guard

def memory_state() -> dict:
    sw = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout
    m = re.search(r"free = ([\d.]+)M", sw)
    mp = subprocess.run(["memory_pressure"], capture_output=True, text=True).stdout
    f = re.search(r"free percentage: (\d+)%", mp)
    return {"swap_free_mb": float(m.group(1)) if m else None, "free_pct": int(f.group(1)) if f else None}


def memory_ok(a) -> tuple[bool, dict]:
    s = memory_state()
    ok = (s["swap_free_mb"] is None or s["swap_free_mb"] >= a.min_swap_mb) and \
         (s["free_pct"] is None or s["free_pct"] >= a.min_free_pct)
    return ok, s


def run_chains(a, jobs, cache_path, log) -> list[dict]:
    done = {}
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                done[r["key"]] = r
    todo = [j for j in jobs if _key(j) not in done]
    log(f"{len(jobs)} chains, {len(done)} cached, {len(todo)} to run; workers {a.workers}")
    t0, n = time.time(), 0
    with ProcessPoolExecutor(a.workers) as ex, open(cache_path, "a", encoding="utf-8") as cache:
        it = iter(todo)
        live: set = set()
        exhausted = False
        while live or not exhausted:
            while not exhausted and len(live) < a.workers:
                ok, st = memory_ok(a)
                if not ok:
                    if not live:
                        log(f"paused (memory {st}); waiting 60 s")
                        time.sleep(60)
                        continue
                    break
                j = next(it, None)
                if j is None:
                    exhausted = True
                    break
                live.add(ex.submit(_job, j))
            if not live:
                continue
            fin, live = wait(live, timeout=60, return_when=FIRST_COMPLETED)
            for fu in fin:
                r = fu.result()
                done[r["key"]] = r
                cache.write(json.dumps(r, separators=(",", ":")) + "\n")
                cache.flush()
                n += 1
                if n % 25 == 0 or n == len(todo):
                    log(f"{n}/{len(todo)} chains, {time.time() - t0:.0f} s, load {_load()}, memory {memory_state()}")
    return [done[_key(j)] for j in jobs]


# ------------------------------------------------------------------ analysis

def _slope(xs, G):
    x = np.array(xs, float)
    xc = x - x.mean()
    return (G * xc).sum(1) / (xc ** 2).sum()


def _lst(a):
    return [None if (x is None or (isinstance(x, float) and np.isnan(x))) else float(x) for x in a]


def gains(runs, seeds, samples) -> dict:
    """{cond: {seed: {stall: gain dict}}}"""
    idx = {(r["cond"], r["seed"], r["stall"], r["b"]): r for r in runs}
    out: dict = {}
    for r in runs:
        if r["b"] != NEVER:
            continue
        cond, seed = r["cond"], r["seed"]
        for s in samples[seed]:
            tot = {NEVER: r["totals"][s], **{b: idx[(cond, seed, s, b)]["totals"][s] for b in CANDS}}
            out.setdefault(cond, {}).setdefault(seed, {})[s] = benchmark.gain(tot)
    return out


def seed_mean(G, cond, seeds, field) -> np.ndarray:
    return np.array([np.mean([G[cond][sd][s][field] for s in G[cond][sd]]) for sd in seeds], float)


def _window(prof: dict, days) -> dict:
    agg = {k: {p: 0.0 for p in PROFILES} for k in ("buyers", "purchases", "short", "value", "paid", "inspect")}
    for d in days:
        x = prof.get(str(d))
        if x is None:
            continue
        for k in agg:
            for p in PROFILES:
                agg[k][p] += x[k][p]
    return {"short": {p: (agg["short"][p] / agg["purchases"][p]) if agg["purchases"][p] else None for p in PROFILES},
            "surplus": {p: ((agg["value"][p] - agg["paid"][p] - agg["inspect"][p]) / agg["buyers"][p])
                        if agg["buyers"][p] else None for p in PROFILES}}


def _timing(rb, s, b) -> dict:
    """Days from bust-out (day b) to: first negative critic review written / filed; first
    end-of-day rating below tau; first day the stall's tourist units fall below half their mean
    over days b-5..b-1. None = not by day 30."""
    neg = [x for x in rb["critic"].get(s, []) if x[0] >= b and not x[2]]
    written = min((x[0] for x in neg), default=None)
    filed = min((x[4] for x in neg if x[4] <= DAYS), default=None)
    rate = next((d for d in range(b, DAYS + 1) if (rb["days"][d - 1]["rating"][s] is not None
                                                     and rb["days"][d - 1]["rating"][s] < TAU)), None)
    tu = lambda d: rb["profile"].get(str(d), {}).get("units", {}).get(s, {}).get("tourist", 0)
    pre = [tu(d) for d in range(b - 5, b)]
    base = float(np.mean(pre)) if pre else 0.0
    tour = next((d for d in range(b, DAYS + 1) if tu(d) < 0.5 * base), None) if base > 0 else "no tourist sales before"
    f = lambda x: x - b if isinstance(x, int) else x
    return {"critic_written": f(written), "critic_filed": f(filed), "rating_below_tau": f(rate), "tourist_drop": f(tour)}


def analyse(stage, runs, seeds, samples) -> dict:
    G = gains(runs, seeds, samples)
    idx = {(r["cond"], r["seed"], r["stall"], r["b"]): r for r in runs}
    res: dict = {"stage": stage, "by_cond": {}, "harm": {}, "timing": {}, "best_day": {}}
    for cond in CONDS[stage]:
        U, F = seed_mean(G, cond, seeds, "gain_unfloored"), seed_mean(G, cond, seeds, "gain_floored")
        allg = [G[cond][sd][s] for sd in seeds for s in G[cond][sd]]
        res["by_cond"][cond] = {"unfloored": mean_ci(_lst(U)), "floored": mean_ci(_lst(F)),
                                "share_positive": float(np.mean([g["gain_unfloored"] > 0 for g in allg])),
                                "never_total": mean_ci(_lst(seed_mean(G, cond, seeds, "never")))}
        res["best_day"][cond] = {str(b): sum(g["best_day"] == b for g in allg) for b in CANDS}
        harm = {p: {"short": [], "surplus": []} for p in PROFILES}
        tim = []
        for sd in seeds:
            per = {p: {"short": [], "surplus": []} for p in PROFILES}
            for s, g in G[cond][sd].items():
                b = g["best_day"]
                rb, rn = idx[(cond, sd, s, b)], idx[(cond, sd, None, NEVER)]
                wb, wn = _window(rb["profile"], range(b, DAYS + 1)), _window(rn["profile"], range(b, DAYS + 1))
                for p in PROFILES:
                    for k in ("short", "surplus"):
                        if wb[k][p] is not None and wn[k][p] is not None:
                            per[p][k].append(wb[k][p] - wn[k][p])
                tim.append(_timing(rb, s, b))
            for p in PROFILES:
                for k in ("short", "surplus"):
                    harm[p][k].append(float(np.mean(per[p][k])) if per[p][k] else None)
        res["harm"][cond] = {p: {k: mean_ci(harm[p][k]) for k in ("short", "surplus")} for p in PROFILES}
        res["timing"][cond] = {k: {"n": len(tim), "reached": sum(isinstance(t[k], int) for t in tim),
                                   "median": (float(np.median([t[k] for t in tim if isinstance(t[k], int)]))
                                              if any(isinstance(t[k], int) for t in tim) else None),
                                   "mean": mean_ci([t[k] for t in tim if isinstance(t[k], int)])}
                               for k in ("critic_written", "critic_filed", "rating_below_tau", "tourist_drop")}
    # pooled harm over the stage's conditions (per seed: mean over conditions)
    res["harm_pooled"] = {}
    for p in PROFILES:
        res["harm_pooled"][p] = {}
        for k in ("short", "surplus"):
            per_seed = []
            for sd in seeds:
                xs = []
                for cond in CONDS[stage]:
                    for s, g in G[cond][sd].items():
                        b = g["best_day"]
                        wb = _window(idx[(cond, sd, s, b)]["profile"], range(b, DAYS + 1))
                        wn = _window(idx[(cond, sd, None, NEVER)]["profile"], range(b, DAYS + 1))
                        if wb[k][p] is not None and wn[k][p] is not None:
                            xs.append(wb[k][p] - wn[k][p])
                per_seed.append(float(np.mean(xs)) if xs else None)
            res["harm_pooled"][p][k] = mean_ci(per_seed)
    # predictions and gates
    def pv(field):
        return {c: seed_mean(G, c, seeds, field) for c in CONDS[stage]}
    res["pred"] = {}
    for field in ("gain_unfloored", "gain_floored"):
        V = pv(field)
        P = {}
        if stage == "A":
            S = _slope(LAMBDAS, np.stack([V[a_cond(l, "t40")] for l in LAMBDAS], 1)) * 0.1
            P["PS1"] = {**mean_ci(_lst(S)), "unit": "per +0.1 of lambda", "sign": +1}
            P["PS2"] = {**paired_diff(_lst(V[a_cond(0.9, "t40")]), _lst(V[a_cond(0.9, "t80")])), "sign": +1}
        else:
            S = _slope(TIES, np.stack([V[b_cond(t, False, 0.0)] for t in TIES], 1)) * 0.1
            P["PK1"] = {**mean_ci(_lst(S)), "unit": "per +0.1 of tie share", "sign": +1}
            P["PK2"] = {**mean_ci(_lst(V[b_cond(0.6, False, 0.0)])), "sign": +1}
            P["PK3"] = {**paired_diff(_lst(V[b_cond(0.3, False, 0.0)]), _lst(V[b_cond(0.3, False, 0.5)])), "sign": +1}
            P["emb"] = {f"tie{t:g}|cap{c:g}": paired_diff(_lst(V[b_cond(t, False, c)]), _lst(V[b_cond(t, True, c)]))
                        for t in TIES for c in CAPS}
        for k, v in P.items():
            if "sign" in v:
                v["verdict"] = _verdict(v, v["sign"])
        res["pred"][field] = P
    if stage == "A":
        g = res["by_cond"][a_cond(0.7, "t40")]["unfloored"]
        res["gate"] = {"label": "lambda 0.7 / tourists 0.4: mean unfloored gain <= 0 (sign of the e5d7818 result)",
                       "passed": g["mean"] is not None and g["mean"] <= 0, "detail": f"mean {_d(g['mean'], True)}"}
    else:
        base = [r for r in runs if r["cond"] == b_cond(0.0, False, 0.0)]
        n_del = sum(r["delayed_reviews"] for r in base)
        one = next(r for r in base if r["seed"] == seeds[0] and r["b"] == NEVER)
        res["gate"] = {"label": "tie share 0, embarrassment off, capture 0: no critic review is ever held",
                       "passed": n_del == 0,
                       "detail": f"held reviews: {n_del} over {len(base)} chains; seed {seeds[0]} never chain: "
                                 f"{one['delayed_reviews']}"}
    # floors on the never chains
    v = {}
    for r in runs:
        if r["b"] == NEVER:
            v.setdefault(r["cond"], []).append(r)
    flags = floor_flags(v, list(range(26, DAYS + 1)), list(range(1, DAYS + 1)))
    for cond in CONDS[stage]:
        fb = sum(r["fallbacks"] for r in runs if r["cond"] == cond)
        if fb:
            flags.append(f"{cond}: {fb} invalid buyer actions (fallbacks)")
        wrong = [r["key"] for r in runs if r["cond"] == cond and r["b"] != NEVER
                 and [list(x) for x in r["busts"]] != [[r["stall"], r["b"]]]]
        if wrong:
            flags.append(f"{cond}: {len(wrong)} bust chains where the scheduled stall did not bust out exactly on its day")
        extra = [r["key"] for r in runs if r["cond"] == cond and r["b"] == NEVER and r["busts"]]
        if extra:
            flags.append(f"{cond}: {len(extra)} never chains with a bust-out")
    res["flags"] = flags
    return res


# ------------------------------------------------------------------ plots

def _frame(title, sub, notes, W=900, H=600, desc=""):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" aria-labelledby="t d">',
            STYLE, f'<rect class="bg" x="0" y="0" width="{W}" height="{H}"/>', f'<title id="t">{title}</title>',
            f'<desc id="d">{desc} The summary gives every value.</desc>',
            f'<text class="t" x="30" y="44" font-size="20">{title}</text>',
            f'<text class="s" x="30" y="70" font-size="14">{sub}</text>'] + \
           [f'<text class="n" x="30" y="{H - 24 - 16 * (len(notes) - 1 - i)}">{n}</text>' for i, n in enumerate(notes)]


def _yrange(stats):
    lo = min([0] + [s["lo"] / 100 for s in stats if s.get("lo") is not None])
    hi = max([0] + [s["hi"] / 100 for s in stats if s.get("hi") is not None])
    pad = (hi - lo) * 0.1 or 1
    return lo - pad, hi + pad


def _nice(x):
    e = 10 ** np.floor(np.log10(x))
    for m in (1, 2, 2.5, 5, 10):
        if m * e >= x:
            return m * e
    return 10 * e


def _yaxis(out, Y, lo, hi, x0, label, top, ph):
    out.append(f'<line class="ax" x1="{x0}" y1="{Y(lo):.1f}" x2="{x0}" y2="{Y(hi):.1f}"/>')
    step = _nice((hi - lo) / 5)
    y = np.ceil(lo / step) * step
    while y <= hi + 1e-9:
        lab = "0" if abs(y) < 1e-9 else f"{y:+,.0f}".replace("-", "−")
        out.append(f'<text class="k" x="{x0 - 6}" y="{Y(y) + 4:.1f}" text-anchor="end">{lab}</text>')
        y += step
    out.append(f'<text class="k" x="{x0 - 60}" y="{top + ph / 2}" text-anchor="middle" '
               f'transform="rotate(-90 {x0 - 60} {top + ph / 2})">{label}</text>')


def _series(out, X, Y, xs, stats, cls, dx, label, ldy=4, anchor="start"):
    pts = [(X(x) + dx, Y(s["mean"] / 100)) for x, s in zip(xs, stats) if s.get("mean") is not None]
    out.append(f'<polyline class="{"ln" if cls == "pt" else "hlc"}" fill="none" points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}"/>')
    for (px, py), s in zip(pts, stats):
        if s.get("lo") is not None:
            out.append(f'<line class="{"ci" if cls == "pt" else "hlc"}" x1="{px:.1f}" y1="{Y(s["lo"] / 100):.1f}" '
                       f'x2="{px:.1f}" y2="{Y(s["hi"] / 100):.1f}"/>')
        out.append(f'<circle class="{cls}" cx="{px:.1f}" cy="{py:.1f}" r="3.5"/>')
    if pts and label:
        lx = pts[-1][0] + (10 if anchor == "start" else -10)
        out.append(f'<text class="lb" x="{lx:.1f}" y="{pts[-1][1] + ldy:.1f}" text-anchor="{anchor}">{label}</text>')


NOTE2 = ("Bazaar engine {v}. Seeds 52–66 paired; 95% t-intervals, unadjusted; 3 sampled genuine stalls per seed; "
         "bust-out days 10, 20, 27; 30 days.")


def plot_lambda_svg(res, version=ENGINE_VERSION) -> str:
    W, H, left, top, pw, ph = 900, 600, 130, 110, 600, 340
    st = {t: [res["by_cond"][a_cond(l, t)]["unfloored"] for l in LAMBDAS] for t in TOURISTS}
    lo, hi = _yrange(st["t40"] + st["t80"])
    X = lambda x: left + (x - 0.7) / (0.97 - 0.7) * pw
    Y = lambda y: top + ph - (y - lo) / (hi - lo) * ph
    p1 = res["pred"]["gain_unfloored"]["PS1"]
    out = _frame("Best bust-out gain against rating memory, by tourist share",
                 f"Stage A, no inspectors or critics; PS1 slope {_ci(p1, _d)} per +0.1 of λ",
                 [NOTE2.format(v=version), "Gain = the sampled stall's 30-day profit at its best bust-out day minus "
                  "never busting out. Budget 1.25 × base, 150 buyers, search depth 2, fresh reopening,",
                  "naive deceptive sellers, premium 0.4 (placeholder). Ratings visible to locals and experts only."],
                 desc="Mean gain with paired intervals at lambda 0.7, 0.9, 0.97 for tourist shares 0.4 and 0.8.")
    out.insert(-2, f'<line class="zero" x1="{X(0.7):.1f}" y1="{Y(0):.1f}" x2="{X(0.97):.1f}" y2="{Y(0):.1f}"/>')
    _series(out, X, Y, LAMBDAS, st["t40"], "pt", -4, "tourists 40%")
    _series(out, X, Y, LAMBDAS, st["t80"], "hl", 4, "tourists 80%")
    _yaxis(out, Y, lo, hi, left - 14, "gain, $ per stall over 30 days", top, ph)
    out.append(f'<line class="ax" x1="{X(0.7):.1f}" y1="{top + ph + 14}" x2="{X(0.97):.1f}" y2="{top + ph + 14}"/>')
    for l in LAMBDAS:
        out.append(f'<text class="k" x="{X(l):.1f}" y="{top + ph + 30}" text-anchor="middle">{l:g}</text>')
    out.append(f'<text class="k" x="{left + pw / 2}" y="{top + ph + 50}" text-anchor="middle">rating memory λ '
               f'(higher = slower ratings)</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def plot_ties_svg(res, version=ENGINE_VERSION) -> str:
    W, H, top, ph, pw = 900, 600, 120, 340, 300
    lefts = [140, 540]
    allst = [res["by_cond"][b_cond(t, e, c)]["unfloored"] for t in TIES for e in EMB for c in CAPS]
    lo, hi = _yrange(allst)
    Y = lambda y: top + ph - (y - lo) / (hi - lo) * ph
    p1 = res["pred"]["gain_unfloored"]["PK1"]
    out = _frame("Best bust-out gain against critics' ties, with and without embarrassment",
                 f"Stage B: 2 patrolling inspectors, 4 critics; panels by inspector capture; PK1 slope "
                 f"{_ci(p1, _d)} per +0.1 tie share",
                 [NOTE2.format(v=version), "Critics: 6 stalls a day, weight 5, tie delay 10, emb_max 10; capture "
                  "effect 0.8 (placeholders). λ 0.7, tourists 40%, budget 1.25 × base."],
                 desc="Mean gain with paired intervals at tie shares 0, 0.3, 0.6, embarrassment off and on, "
                      "for inspector capture 0 and 0.5.")
    for left, cap in zip(lefts, CAPS):
        X = lambda x, left=left: left + x / 0.6 * pw
        out.append(f'<text class="t" x="{left}" y="{top - 16}" font-size="15">inspector capture {cap:g}</text>')
        out.append(f'<line class="zero" x1="{X(0):.1f}" y1="{Y(0):.1f}" x2="{X(0.6):.1f}" y2="{Y(0):.1f}"/>')
        first = cap == CAPS[0]
        _series(out, X, Y, TIES, [res["by_cond"][b_cond(t, False, cap)]["unfloored"] for t in TIES], "pt", -4,
                "embarrassment off" if first else None, ldy=-12, anchor="end")
        _series(out, X, Y, TIES, [res["by_cond"][b_cond(t, True, cap)]["unfloored"] for t in TIES], "hl", 4,
                "embarrassment on" if first else None, ldy=20, anchor="end")
        out.append(f'<line class="ax" x1="{X(0):.1f}" y1="{top + ph + 14}" x2="{X(0.6):.1f}" y2="{top + ph + 14}"/>')
        for t in TIES:
            out.append(f'<text class="k" x="{X(t):.1f}" y="{top + ph + 30}" text-anchor="middle">{t:g}</text>')
        out.append(f'<text class="k" x="{left + pw / 2}" y="{top + ph + 50}" text-anchor="middle">critic tie share</text>')
    _yaxis(out, Y, lo, hi, lefts[0] - 14, "gain, $ per stall over 30 days", top, ph)
    out.append("</svg>")
    return "\n".join(out) + "\n"


def plot_harm_svg(results: dict, version=ENGINE_VERSION) -> str:
    """Per profile: change in shortfall share (points) and surplus per buyer ($) when the sampled
    stall busts out at its best day, pooled over each stage's conditions."""
    W, H, top, rowh = 900, 560, 130, 90
    panels = [("short", "shortfall share of purchases, points", 100.0, 150), ("surplus", "surplus per buyer, $", 0.01, 540)]
    pw = 280
    out = _frame("Who pays when a brand cashes out: change by buyer profile",
                 "Sampled stall busting out at its best day minus nobody busting out, days from the bust-out to 30; "
                 "pooled over each stage's conditions",
                 [NOTE2.format(v=version), "Surplus = value − price − inspection costs, per buyer of the profile "
                  "present those days. Gray: stage A; accent: stage B."], H=H,
                 desc="Dots with paired intervals per profile and stage.")
    stages = [s for s in ("A", "B") if s in results]
    for key, label, mult, left in panels:
        vals = [results[s]["harm_pooled"][p][key] for s in stages for p in PROFILES]
        lo = min([0] + [v["lo"] * mult for v in vals if v.get("lo") is not None])
        hi = max([0] + [v["hi"] * mult for v in vals if v.get("hi") is not None])
        pad = (hi - lo) * 0.1 or 1
        lo, hi = lo - pad, hi + pad
        X = lambda x, left=left, lo=lo, hi=hi: left + (x - lo) / (hi - lo) * pw
        out.append(f'<text class="t" x="{left}" y="{top - 20}" font-size="15">{label}</text>')
        out.append(f'<line class="zero" x1="{X(0):.1f}" y1="{top}" x2="{X(0):.1f}" y2="{top + rowh * 3}"/>')
        for i, p in enumerate(PROFILES):
            y0 = top + rowh * i + rowh / 2
            if key == "short":
                out.append(f'<text class="lb" x="{left - 12}" y="{y0 + 4:.1f}" text-anchor="end">{p}s</text>')
            for j, s in enumerate(stages):
                v = results[s]["harm_pooled"][p][key]
                if v.get("mean") is None:
                    continue
                y = y0 + (j - 0.5) * 16
                cls = "pt" if s == "A" else "hl"
                if v.get("lo") is not None:
                    out.append(f'<line class="{"ci" if s == "A" else "hlc"}" x1="{X(v["lo"] * mult):.1f}" y1="{y:.1f}" '
                               f'x2="{X(v["hi"] * mult):.1f}" y2="{y:.1f}"/>')
                out.append(f'<circle class="{cls}" cx="{X(v["mean"] * mult):.1f}" cy="{y:.1f}" r="3.5"/>')
                xr = X((v["hi"] if v.get("hi") is not None else v["mean"]) * mult) + 6
                lab = ("%+.1f" % (v["mean"] * mult)).replace("-", "−")
                out.append(f'<text class="k" x="{xr:.1f}" y="{y + 4:.1f}">{s} {lab}</text>')
        out.append(f'<line class="ax" x1="{left}" y1="{top + rowh * 3 + 8}" x2="{left + pw}" y2="{top + rowh * 3 + 8}"/>')
        step = _nice((hi - lo) / 4)
        x = np.ceil(lo / step) * step
        while x <= hi + 1e-9:
            lab = "0" if abs(x) < 1e-9 else f"{x:+,.{0 if step >= 1 else 1}f}".replace("-", "−")
            out.append(f'<text class="k" x="{X(x):.1f}" y="{top + rowh * 3 + 24}" text-anchor="middle">{lab}</text>')
            x += step
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ report

def _stage_lines(stage, meta, res) -> list[str]:
    P = res["pred"]
    L = [f"## Stage {stage}: {'speed' if stage == 'A' else 'capture'}", "", "### Run record", "",
         f"- Engine `{meta['engine_version']}`; commit `{meta['git']['commit']}`; uncommitted at run time: "
         f"{meta['git']['status_porcelain'] or 'none'}",
         f"- Script sha256 `{meta['script_sha256']}`", f"- Command: `{meta['command']}`",
         f"- Tests: {meta.get('tests') or 'not recorded'}",
         f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
         f"- {meta['n_chains']} chains × {DAYS} days on {meta['workers']} workers (nice 19); wall clock "
         f"{meta['wall_clock_s'] / 3600:.2f} h; load average {meta['load_at_start']} at start, {meta['load_at_end']} at end; "
         f"memory at start {meta['memory_at_start']}, at end {meta['memory_at_end']}; memory-guard pauses: "
         f"{meta['pauses']}",
         f"- Seeds {meta['seeds'][0]}–{meta['seeds'][-1]} ({len(meta['seeds'])}), paired; sampled stalls per seed: "
         + "; ".join(f"{sd}: {', '.join(meta['samples'][str(sd)])}" for sd in meta["seeds"]), "",
         "### Gate", "",
         f"- {res['gate']['label']}: **{'passed' if res['gate']['passed'] else 'FAILED'}** ({res['gate']['detail']})", ""]
    if not res["gate"]["passed"]:
        L += [f"**Gate failed: Stage {stage} results are not reported" + (" and Stage B was not run.**" if stage == "A" else ".**"), ""]
        return L
    names = ["PS1", "PS2"] if stage == "A" else ["PK1", "PK2", "PK3"]
    text = {"PS1": "at tourists 0.4, slope of the gain over λ (per +0.1)", "PS2": "at λ 0.9, tourists 0.8 − 0.4",
            "PK1": "embarrassment off, capture 0: slope over tie share (per +0.1)",
            "PK2": "tie share 0.6, embarrassment off, capture 0: gain", "PK3": "tie share 0.3, embarrassment off: capture 0.5 − 0"}
    L += ["### Confirmatory", "", "Prediction > 0 for each. Gain in $ per sampled stall over 30 days.", ""]
    L += _t(["Prediction", "Unfloored gain (primary)", "Verdict", "Floored gain (spec)", "Verdict"],
            [[f"**{n}**: {text[n]}", _ci(P["gain_unfloored"][n], _d), P["gain_unfloored"][n]["verdict"],
              _ci(P["gain_floored"][n], _d), P["gain_floored"][n]["verdict"]] for n in names])
    L += ["", "### Gain by condition", ""]
    L += _t(["Condition", "Unfloored gain ($)", "Floored gain ($)", "Stall-seeds with a positive gain (%)",
             "Never-bust total ($)", f"Best day {CANDS[0]} / {CANDS[1]} / {CANDS[2]} (count)"],
            [[c, _ci(res["by_cond"][c]["unfloored"], _d), _ci(res["by_cond"][c]["floored"], _d, False),
              f"{100 * res['by_cond'][c]['share_positive']:.0f}", _ci(res["by_cond"][c]["never_total"], _d, False),
              " / ".join(str(res["best_day"][c][str(b)]) for b in CANDS)] for c in CONDS[stage]])
    if stage == "B":
        L += ["", "Embarrassment's added effect (exploratory), on − off, unfloored gain ($):", ""]
        L += _t(["Tie share", "Capture 0", "Capture 0.5"],
                [[f"{t:g}", _ci(P["gain_unfloored"]["emb"][f"tie{t:g}|cap0"], _d),
                  _ci(P["gain_unfloored"]["emb"][f"tie{t:g}|cap0.5"], _d)] for t in TIES])
    L += ["", "### Harm by buyer profile at the best bust-out day (exploratory)", "",
          "Bust chain at the stall's best day minus the never chain, days from the bust-out to 30; per seed the "
          "mean over the 3 stalls. Shortfall in points of purchases; surplus in $ per buyer of the profile.", ""]
    L += _t(["Condition"] + [f"{p}: shortfall (pts)" for p in PROFILES] + [f"{p}: surplus ($)" for p in PROFILES],
            [[c] + [_ci(res["harm"][c][p]["short"], _pct) for p in PROFILES]
             + [_ci(res["harm"][c][p]["surplus"], _d) for p in PROFILES] for c in CONDS[stage]]
            + [["pooled"] + [_ci(res["harm_pooled"][p]["short"], _pct) for p in PROFILES]
               + [_ci(res["harm_pooled"][p]["surplus"], _d) for p in PROFILES]])
    L += ["", "### How long bad news stays semi-private (exploratory)", "",
          "Days from the bust-out (at the best day) to each event; reached = stall-seeds where it happened by day 30, "
          "of 45.", ""]
    keys = [("critic_written", "first negative critic review written"), ("critic_filed", "… filed"),
            ("rating_below_tau", "rating below τ = 0.5"), ("tourist_drop", "tourist units below half the pre-bust mean")]
    L += _t(["Condition"] + [f"{lab}: median (reached)" for _, lab in keys],
            [[c] + [("–" if res["timing"][c][k]["median"] is None else f"{res['timing'][c][k]['median']:g}")
                    + f" ({res['timing'][c][k]['reached']})" for k, _ in keys] for c in CONDS[stage]])
    L += ["", "### Floors, invalid actions and schedule checks", ""] + ([f"- {x}" for x in res["flags"]] or ["- none"])
    L += [""]
    return L


def report(results: dict, metas: dict, svgs: dict) -> str:
    L = ["# Reputation speed and capture: the brand dilemma's boundary", "",
         "Run spec \"reputation speed and capture, the brand dilemma's real boundary (rule-based only)\"; predictions "
         "written 2026-11-07, before any run.", "",
         "## Design (prespecified)", "",
         "- Common: D = 30 known to sellers; ratings public (locals and experts see them); brands on, premium 0.4 "
         "(placeholder); budget 1.25 × base; search depth 2; 150 buyers; fresh reopening; naive deceptive sellers; "
         "genuine stalls always honest except the sampled stall in a bust chain.",
         "- Stage A (speed): no inspectors or critics; rating memory λ ∈ {0.7, 0.9, 0.97} × tourist share ∈ {0.4, 0.8}.",
         "- Stage B (capture): 2 patrolling inspectors (not uniformed), 4 critics (6 stalls a day, weight 5, tie delay 10, "
         "emb_max 10: placeholders), λ 0.7, tourists 0.4; tie share ∈ {0, 0.3, 0.6} × embarrassment ∈ {off, on} × "
         "inspector capture ∈ {0, 0.5} (capture effect 0.8, placeholder).",
         "- Benchmark (engine/benchmark.py): per seed, 3 genuine stalls from `default_rng([seed, 17])`, the same in every "
         "condition; each busts out on day 10, 20 or 27 (rule_genuine_bust_at, on its first decision of the day), all "
         "other genuine stalls honest; one shared never chain. Gain = the stall's 30-day profit at the best bust-out "
         "day minus never (**unfloored, primary**, decided 2026-11-07) and the spec's floored version (best of never "
         "and the three days, never below 0).",
         "- Decided 2026-11-07 before any run: engine 0.11.0 on 0.10.0 (the spec said 0.12.0 on 0.11.0, which did not "
         "exist); tourists keep not seeing ratings, and their learning is proxied by the stall's tourist sales; a critic "
         "review is positive when true Q meets the posted claim.",
         "- Paired by seed; 95% t-intervals, unadjusted. Confirmatory: PS1, PS2 (stage A), PK1–PK3 (stage B). "
         "Everything else exploratory.", ""]
    for stage in ("A", "B"):
        if stage in results:
            L += _stage_lines(stage, metas[stage], results[stage])
            if results[stage]["gate"]["passed"] and stage in svgs:
                L += [f"![{svgs[stage][1]}]({svgs[stage][0]})", ""]
    if "harm" in svgs:
        L += [f"![harm by buyer profile]({svgs['harm']})", ""]
    L += ["## Reading (written after the results)", "", "READING_PLACEHOLDER", "", "## Caveats", "",
          "CAVEATS_PLACEHOLDER", ""]
    return "\n".join(L)


# ------------------------------------------------------------------ main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["A", "B"], required=True)
    ap.add_argument("--seeds", default="52-66")
    ap.add_argument("--outdir", default="runs")
    ap.add_argument("--tests", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--min-swap-mb", type=float, default=1024)
    ap.add_argument("--min-free-pct", type=float, default=15)
    ap.add_argument("--pipeline-check", action="store_true")
    a = ap.parse_args(argv)
    os.nice(19)
    seeds = parse_seeds(a.seeds)
    if a.pipeline_check:
        if not set(seeds) <= PIPELINE or os.path.abspath(a.outdir).startswith(os.path.abspath("runs")):
            raise SystemExit("pipeline check: seeds must be within 400-401 and --outdir outside runs/")
    elif set(seeds) & (USED | PIPELINE):
        raise SystemExit("seeds overlap seeds used by earlier runs or the pipeline check")
    os.makedirs(a.outdir, exist_ok=True)
    stage = a.stage
    base = os.path.join(a.outdir, f"capture_{stage}")
    if stage == "B":
        pa = os.path.join(a.outdir, "capture_A.json.gz")
        if not os.path.exists(pa):
            raise SystemExit("stage B needs stage A's results (capture_A.json.gz)")
        with gzip.open(pa, "rt", encoding="utf-8") as f:
            if not json.load(f)["results"]["gate"]["passed"]:
                raise SystemExit("stage A's gate failed; stage B is not run")
    logf = open(base + "_run.log", "a", encoding="utf-8")

    def log(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()
    samples = {sd: sample_stalls(sd) for sd in seeds}
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
            "command": " ".join([".venv/bin/python -m analysis.capture", *(argv or sys.argv[1:])]),
            "tests": a.tests, "load_at_start": _load(), "memory_at_start": memory_state(),
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
            "workers": a.workers, "seeds": seeds, "days": DAYS, "conditions": CONDS[stage],
            "samples": {str(k): v for k, v in samples.items()}, "overrides": {c: overrides(c) for c in CONDS[stage]}}
    jobs = jobs_for(stage, seeds, samples)
    t0 = time.time()
    pauses: list = []

    def log2(msg):
        if msg.startswith("paused"):
            pauses.append(time.strftime("%H:%M:%S"))
        log(msg)
    runs = run_chains(a, jobs, base.replace("capture_", "capture_cache_") + ".jsonl", log2)
    meta.update(wall_clock_s=time.time() - t0, load_at_end=_load(), memory_at_end=memory_state(),
                n_chains=len(runs), pauses=len(pauses))
    res = analyse(stage, runs, seeds, samples)
    with gzip.open(base + ".json.gz", "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": res, "runs": runs}, f, sort_keys=True, separators=(",", ":"))
    with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["stage", "condition", "seed", "stall", "gain_unfloored_cents", "gain_floored_cents", "best_day",
                    "never_total_cents"] + [f"total_day{b}_cents" for b in CANDS])
        G = gains(runs, seeds, samples)
        for cond in CONDS[stage]:
            for sd in seeds:
                for s, g in G[cond][sd].items():
                    w.writerow([stage, cond, sd, s, g["gain_unfloored"], g["gain_floored"], g["best_day"], g["never"]]
                               + [g["totals"][b] for b in CANDS])
    # report over every stage present
    results, metas = {}, {}
    for s in ("A", "B"):
        p = os.path.join(a.outdir, f"capture_{s}.json.gz")
        if os.path.exists(p):
            with gzip.open(p, "rt", encoding="utf-8") as f:
                d = json.load(f)
            results[s], metas[s] = d["results"], d["meta"]
    svgs: dict = {}
    if results.get("A", {}).get("gate", {}).get("passed"):
        path = os.path.join(a.outdir, "capture_gain_by_lambda.svg")
        open(path, "w", encoding="utf-8").write(plot_lambda_svg(results["A"]))
        svgs["A"] = (os.path.basename(path), "gain by rating memory and tourist share")
    if results.get("B", {}).get("gate", {}).get("passed"):
        path = os.path.join(a.outdir, "capture_gain_by_ties.svg")
        open(path, "w", encoding="utf-8").write(plot_ties_svg(results["B"]))
        svgs["B"] = (os.path.basename(path), "gain by critic ties, embarrassment and capture")
    passed = {s: r for s, r in results.items() if r["gate"]["passed"]}
    if passed:
        path = os.path.join(a.outdir, "capture_harm_by_profile.svg")
        open(path, "w", encoding="utf-8").write(plot_harm_svg(passed))
        svgs["harm"] = os.path.basename(path)
    with open(os.path.join(a.outdir, "capture_summary.md"), "w", encoding="utf-8") as f:
        f.write(report(results, metas, svgs))
    log(f"stage {stage} done; gate passed: {res['gate']['passed']} ({res['gate']['detail']}); flags: {len(res['flags'])}")
    return 0 if res["gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
