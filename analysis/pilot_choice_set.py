"""Pilot of choice-set demand (engine 0.12.0), 2026-11-08. Throwaway seeds 900-904 only: never
reuse them for confirmatory work. Pilot numbers are pipeline checks, not results.

Setting: buyers.demand_mode = choice_set, position_rent (gamma) 0, consider (m) 3, budget 1.25 x base,
tourists 0.4 (locals 0.3, experts 0.3), D = 30 known, ratings public (memory 0.7), brands on
(premium 0.4), naive deceptive sellers with fresh reopening, genuine stalls honest. Bargain hunters at
the choice_set default (0.2).

Buyer count: the smallest of {150, 200, 300} that passes the demand gate P0.
P0 demand gate: in an always-honest market (genuine stalls never bust out; 0 inspectors), >= 90% of
   genuine stall-seeds average >= 1 customer a day over days 1-10, and >= 80% of genuine brands are
   rated by the end of day 10.
P1 bust-out accounting: the benchmark at lambda 0.7, 0 inspectors, 3 sampled genuine stalls per seed
   (default_rng([seed, 17]), as in the capture run), candidates {never, 10, 20, 25, 27, 28, 29}.
   Pass if every day before the bust-out is identical to the honest chain (whole day record) and the
   loss decomposes into components with the expected signs (revenue down, cost down, ad spend and
   penalties unchanged with no inspectors).
P2 enforcement regression: single-day market, naive sellers, 2 inspectors at posts vs patrolling,
   5 seeds; pass if patrolling - posts is negative for deceptive profit and for shortfall (direction).
P3 counterfeit smoke: fresh vs counterfeit reopening, deceptive price factor 0.8, 2 patrolling
   inspectors, 30 days; pass if both run, counterfeits sell to tourists at all, and no floor is hit.

    .venv/bin/python -m analysis.pilot_choice_set      # writes runs/pilot_choice_set.md (+ .json.gz)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import platform
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from analysis.capture import memory_state
from analysis.floors import floor_flags, floor_series
from engine import ENGINE_VERSION, bazaar
from engine import benchmark as B
from engine.bazaar import BazaarEngine
from engine.config import load
from engine.jsonlog import dumps

SEEDS = list(range(900, 905))
COUNTS = [150, 200, 300]
DAYS = 30
SAMPLE_STREAM, N_SAMPLE = 17, 3
BASE = ["buyers.demand_mode=choice_set", "buyers.consider=3", "buyers.position_rent=0",
        "ratings.mode=public", "ratings.memory=0.7", "brands.enabled=true", "brands.premium=0.4",
        "market.horizon_known=true", "evolution.revise_prob=0", "evolution.mutation_prob=0",
        "buyers.budget_factor_override=1.25", 'buyers.profile_shares={"tourist":0.4,"local":0.3,"expert":0.3}',
        "agents.seller.deceptive=rule_deceptive", "agents.seller.genuine=rule_honest"]
COMP = ("revenue_cents", "cost_cents", "ad_spend_cents", "penalties_cents", "switch_cost_cents")


def cfg(count, seed, *extra, days=DAYS, reopen="fresh"):
    return load(None, [*BASE, f"buyers.count={count}", f"market.days={days}",
                       f"agents.params.rule_deceptive.reopen={reopen}", *extra, f"seed={seed}"], mode="bazaar")


def honest_cfg(count, seed):
    return cfg(count, seed, "inspectors.count=0", "inspectors.placement=patrolling")


class Tap:
    """Per day: every stall's accounting, and purchases by (stall, buyer profile, counterfeit)."""

    def __init__(self):
        self.days, self._orig = [], BazaarEngine.run

    def __enter__(self):
        tap = self

        def run(eng, *a, **k):
            out = tap._orig(eng, *a, **k)
            acct = {st.sid: {c: getattr(st, c) for c in COMP} | {"units": st.units_sold} for st in eng.stalls}
            cf = {st.sid for st in eng.stalls if st.counterfeit_of}
            prof: dict = {}
            for b in eng.purchases:
                key = f"{b['buyer_profile']}|{'counterfeit' if b['stall'] in cf else b['stype']}"
                prof[key] = prof.get(key, 0) + b["units"]
            tap.days.append({"acct": acct, "units_by_profile_type": prof})
            return out

        BazaarEngine.run = run
        return self

    def __exit__(self, *exc):
        BazaarEngine.run = self._orig


def sample_stalls(count, seed):
    eng = BazaarEngine(honest_cfg(count, seed))
    gen = [st.sid for st in sorted(eng.stalls, key=lambda s: s.idx) if st.stype == "genuine"]
    pick = np.random.default_rng([seed, SAMPLE_STREAM]).choice(len(gen), size=N_SAMPLE, replace=False)
    return [gen[int(i)] for i in pick]


def _chain(c):
    with Tap() as tap:
        out = bazaar.run(c)
    return out, tap.days


def _job(j):
    kind = j[0]
    if kind == "p0":                        # always-honest chain (also P1's never chain)
        _, count, seed = j
        out, tap = _chain(B.bust_config(honest_cfg(count, seed), None, None))
        days = []
        for d, rec in zip(out["days"], tap):
            o = d["outcome"]
            days.append({"types": d["stall_types"], "customers": o["demand"]["customers"],
                         "inclusion": o["demand"]["inclusion"], "ratings": d["ratings"], "acct": rec["acct"],
                         "hash": hashlib.sha256(dumps(d).encode()).hexdigest(),
                         "units_by_profile_type": rec["units_by_profile_type"], **floor_series(o)})
        return {"key": j, "days": days}
    if kind == "p1":
        _, count, seed, sid, b = j
        out, tap = _chain(B.bust_config(honest_cfg(count, seed), sid, b))
        return {"key": j, "hash": [hashlib.sha256(dumps(d).encode()).hexdigest() for d in out["days"]],
                "acct": [rec["acct"][sid] for rec in tap], "total": B.stall_total(out, sid),
                "busted": [d.get("busted", {}).get(sid) for d in out["days"]]}
    if kind == "p2":
        _, count, seed, placement = j
        o = bazaar.run(cfg(count, seed, "inspectors.count=2", f"inspectors.placement={placement}", days=1))
        o = o["days"][0]["outcome"] if "days" in o else o
        dec = o["seller_by_type"].get("deceptive", {})
        return {"key": j, "dec_profit": dec.get("profit_per_stall_cents"), "shortfall": o["shortfall_rate"],
                "catches": o["catches"], "purchases": o["purchases"]}
    if kind == "p3":
        _, count, seed, reopen = j
        c = cfg(count, seed, "inspectors.count=2", "inspectors.placement=patrolling",
                "pricing.deceptive_price_factor=0.8", reopen=reopen)
        out, tap = _chain(c)
        days = [{**floor_series(d["outcome"]), "units_by_profile_type": rec["units_by_profile_type"],
                 "renames": d["outcome"]["brands"]["renames_by_how"], "catches": d["outcome"]["catches"]}
                for d, rec in zip(out["days"], tap)]
        return {"key": j, "days": days}
    raise ValueError(kind)


def run_jobs(jobs, workers, log):
    t0 = time.time()
    res = []
    with ProcessPoolExecutor(workers) as ex:
        for i, r in enumerate(ex.map(_job, jobs), 1):
            res.append(r)
            if i % 10 == 0 or i == len(jobs):
                log(f"  {i}/{len(jobs)} chains, {time.time() - t0:.0f} s, memory {memory_state()}")
    return res


# ------------------------------------------------------------------ checks

def check_p0(runs):
    gen_cust, rated, n_gen = [], [], 0
    for r in runs:
        d10 = r["days"][:10]
        gen = [s for s, t in d10[0]["types"].items() if t == "genuine"]
        n_gen += len(gen)
        for s in gen:
            gen_cust.append(np.mean([d["customers"][s] for d in d10]))
            rated.append(d10[-1]["ratings"][s] is not None)
    by_type = {}
    for t in ("genuine", "deceptive", "seconds"):
        xs = [np.mean([d["customers"][s] for d in r["days"][:10]]) for r in runs
              for s, tt in r["days"][0]["types"].items() if tt == t]
        by_type[t] = {"stalls": len(xs), "mean_customers_per_day": float(np.mean(xs)),
                      "share_ge1": float(np.mean([x >= 1 for x in xs])), "min": float(np.min(xs))}
    share_cust = float(np.mean([x >= 1 for x in gen_cust]))
    share_rated = float(np.mean(rated))
    return {"share_genuine_ge1_customer": share_cust, "share_genuine_rated_day10": share_rated,
            "passed": share_cust >= 0.90 and share_rated >= 0.80, "genuine_stall_seeds": n_gen,
            "by_type": by_type}


def comp_diff(ab, ah, rng):
    sign = {"revenue_cents": 1, "cost_cents": -1, "ad_spend_cents": -1, "penalties_cents": -1, "switch_cost_cents": -1}
    out = {c: sum(sign[c] * (ab[d][c] - ah[d][c]) for d in rng) / 100 for c in COMP}
    out["units_honest"] = sum(ah[d]["units"] for d in rng)
    out["units_bust"] = sum(ab[d]["units"] for d in rng)
    out["total"] = sum(out[c] for c in COMP)
    return out


def check_p1(never, busts, samples):
    rows, ident_fail, sign_fail = [], [], []
    for seed, sids in samples.items():
        nv = never[seed]
        for sid in sids:
            ah = [d["acct"][sid] for d in nv["days"]]
            never_total = sum(a["revenue_cents"] - sum(a[c] for c in COMP[1:]) for a in ah)
            totals = {B.NEVER: never_total}
            per_b = {}
            for b in B.CANDIDATES[1:]:
                r = busts[(seed, sid, b)]
                totals[b] = r["total"]
                per_b[b] = r
                if r["hash"][:b - 1] != [d["hash"] for d in nv["days"][:b - 1]]:
                    ident_fail.append((seed, sid, b))
                if r["busted"][b - 1] != b:
                    ident_fail.append((seed, sid, b, "not busted on its day"))
            g = B.gain(totals)
            b = g["best_day"]
            ab = per_b[b]["acct"]
            pre = comp_diff(ab, ah, range(0, b - 1))
            post = comp_diff(ab, ah, range(b - 1, DAYS))
            ok = (all(abs(pre[c]) < 1e-9 for c in COMP) and post["revenue_cents"] <= 0 and post["cost_cents"] >= 0
                  and post["penalties_cents"] == 0 and post["switch_cost_cents"] == 0)
            if not ok:
                sign_fail.append((seed, sid))
            h_late = sum(ah[d]["revenue_cents"] - sum(ah[d][c] for c in COMP[1:]) for d in range(b - 1, DAYS)) / 100
            rows.append({"seed": seed, "stall": sid, "best_day": b, "gain_unfloored": g["gain_unfloored"] / 100,
                         "never_total": never_total / 100, "totals": {str(k): v / 100 for k, v in totals.items()},
                         "pre": pre, "post": post, "honest_profit_from_best_day": h_late,
                         "honest_units_d1_10": sum(ah[d]["units"] for d in range(10))})
    return {"rows": rows, "identical_before_bust": not ident_fail, "ident_fail": ident_fail,
            "signs_ok": not sign_fail, "sign_fail": sign_fail, "passed": not ident_fail and not sign_fail}


def check_p2(runs):
    by = {}
    for r in runs:
        _, _, seed, pl = r["key"]
        by.setdefault(seed, {})[pl] = r
    dp = [by[s]["patrolling"]["dec_profit"] - by[s]["posts"]["dec_profit"] for s in sorted(by)]
    ds = [by[s]["patrolling"]["shortfall"] - by[s]["posts"]["shortfall"] for s in sorted(by)]
    return {"seeds": sorted(by), "dec_profit_diff_cents": dp, "shortfall_diff": ds,
            "mean_dec_profit_diff": float(np.mean(dp)) / 100, "mean_shortfall_diff": float(np.mean(ds)),
            "posts": {k: float(np.mean([by[s]["posts"][k] for s in by])) for k in ("dec_profit", "shortfall", "catches")},
            "patrolling": {k: float(np.mean([by[s]["patrolling"][k] for s in by])) for k in ("dec_profit", "shortfall", "catches")},
            "passed": float(np.mean(dp)) < 0 and float(np.mean(ds)) < 0}


def check_p3(runs):
    arms = {}
    for r in runs:
        arms.setdefault(r["key"][3], []).append(r)
    out = {"arms": {}}
    for arm, rs in arms.items():
        cf_t = sum(d["units_by_profile_type"].get("tourist|counterfeit", 0) for r in rs for d in r["days"])
        cf_all = sum(v for r in rs for d in r["days"] for k, v in d["units_by_profile_type"].items()
                     if k.endswith("|counterfeit"))
        ren = {h: sum(d["renames"].get(h, 0) for r in rs for d in r["days"]) for h in ("fresh", "counterfeit")}
        out["arms"][arm] = {"counterfeit_units_to_tourists": cf_t, "counterfeit_units_all": cf_all, "renames": ren,
                            "catches": sum(d["catches"] for r in rs for d in r["days"]),
                            "flags": floor_flags({arm: rs}, list(range(26, 31)), list(range(1, 31)))}
    out["passed"] = (set(out["arms"]) == {"fresh", "counterfeit"}
                     and out["arms"]["counterfeit"]["counterfeit_units_to_tourists"] > 0
                     and not any(a["flags"] for a in out["arms"].values()))
    return out


# ------------------------------------------------------------------ report

def fmt_report(meta, sel, p0s, p1, p2, p3) -> str:
    L = ["# Pilot: choice-set demand (engine 0.12.0)", "",
         "**Pilot, not results.** Throwaway seeds 900–904; never reuse them for confirmatory work. Every "
         "number below is a pipeline check.", "",
         "## Setting", "",
         "- buyers.demand_mode = choice_set, gamma (position_rent) 0, m (consider) 3; budget 1.25 × base; "
         "tourists 0.4 (locals 0.3, experts 0.3); D = 30 known; ratings public, memory 0.7; brands on, premium "
         "0.4; naive deceptive sellers, fresh reopening; genuine stalls honest; bargain hunters at the "
         "choice_set default (0.2).",
         f"- Engine `{meta['engine']}`, commit `{meta['commit']}`; Python {meta['python']}, numpy "
         f"{meta['numpy']}, {meta['platform']}; {meta['workers']} workers at nice 19; wall clock "
         f"{meta['wall_min']:.1f} min; load {meta['load_start']} → {meta['load_end']}; memory {meta['mem_start']} → "
         f"{meta['mem_end']}.", "",
         "## Buyer count", ""]
    for n, p in p0s.items():
        L.append(f"- {n} buyers: genuine stall-seeds with ≥ 1 customer a day over days 1–10 "
                 f"{p['share_genuine_ge1_customer']:.0%} (gate ≥ 90%); genuine brands rated by day 10 "
                 f"{p['share_genuine_rated_day10']:.0%} (gate ≥ 80%): **{'pass' if p['passed'] else 'fail'}**")
    L += ["", f"**Chosen: {sel} buyers.**" if sel else "**No buyer count passed P0; stopped.**", ""]
    if not sel:
        return "\n".join(L)
    p0 = p0s[sel]
    L += ["## P0 demand gate: **pass**" if p0["passed"] else "## P0 demand gate: **fail**", "",
          "Days 1–10, always-honest market (no bust-out, 0 inspectors), 5 seeds.", "",
          "| Stall type | Stall-seeds | Mean customers a day | Share with ≥ 1 a day | Lowest |",
          "|---|---|---|---|---|"]
    for t, v in p0["by_type"].items():
        L.append(f"| {t} | {v['stalls']} | {v['mean_customers_per_day']:.2f} | {v['share_ge1']:.0%} | {v['min']:.2f} |")
    L += ["", f"## P1 bust-out accounting: **{'pass' if p1['passed'] else 'fail'}**", "",
          f"- Every day before the bust-out identical to the honest chain (whole day record, all stalls), for every "
          f"stall and candidate day: **{p1['identical_before_bust']}**"
          + ("" if p1["identical_before_bust"] else f" (failures: {p1['ident_fail'][:5]})"),
          f"- Loss components with the expected signs at the best day (no change before it; revenue down, "
          f"cost down, no penalties or switch costs): **{p1['signs_ok']}**"
          + ("" if p1["signs_ok"] else f" (failures: {p1['sign_fail']})"), "",
          "Per sampled stall: best bust-out day (of 10, 20, 25, 27, 28, 29), unfloored gain, and the profit change "
          "from the best day to day 30 by component ($; + = bust-out better). Pipeline check, not a result.", "",
          "| Seed | Stall | Honest 30-day ($) | Best day | Gain ($) | Revenue | Cost | Ad | Penalties | Units honest → bust | Honest profit from best day ($) |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in p1["rows"]:
        po = r["post"]
        L.append(f"| {r['seed']} | {r['stall']} | {r['never_total']:,.0f} | {r['best_day']} | {r['gain_unfloored']:+,.0f} | "
                 f"{po['revenue_cents']:+,.0f} | {po['cost_cents']:+,.0f} | {po['ad_spend_cents']:+,.2f} | "
                 f"{po['penalties_cents']:+,.0f} | {po['units_honest']} → {po['units_bust']} | "
                 f"{r['honest_profit_from_best_day']:,.0f} |")
    gains = [r["gain_unfloored"] for r in p1["rows"]]
    days = [r["best_day"] for r in p1["rows"]]
    L += ["", f"Mean gain ${np.mean(gains):+,.0f} over {len(gains)} stall-seeds ({sum(g > 0 for g in gains)} positive); "
          f"best days: " + ", ".join(f"{d}: {days.count(d)}" for d in B.CANDIDATES[1:] if days.count(d)) + ".", "",
          f"## P2 enforcement regression: **{'pass' if p2['passed'] else 'fail'}**", "",
          "Single day, naive sellers, 2 inspectors, 5 seeds; patrolling − posts (mean over seeds).", "",
          f"- Deceptive profit per stall: posts ${p2['posts']['dec_profit'] / 100:,.2f}, patrolling "
          f"${p2['patrolling']['dec_profit'] / 100:,.2f}; difference ${p2['mean_dec_profit_diff']:+,.2f} "
          f"(per seed, cents: {p2['dec_profit_diff_cents']})",
          f"- Shortfall rate: posts {p2['posts']['shortfall']:.3f}, patrolling {p2['patrolling']['shortfall']:.3f}; "
          f"difference {p2['mean_shortfall_diff']:+.3f} (per seed: {[round(x, 3) for x in p2['shortfall_diff']]})",
          f"- Catches: posts {p2['posts']['catches']:.1f}, patrolling {p2['patrolling']['catches']:.1f}", "",
          f"## P3 counterfeit smoke: **{'pass' if p3['passed'] else 'fail'}**", "",
          "Fresh vs counterfeit reopening, deceptive price factor 0.8, 2 patrolling inspectors, 30 days, 5 seeds.", ""]
    for arm, a in p3["arms"].items():
        L.append(f"- {arm}: catches {a['catches']}, renames {a['renames']}, counterfeit units sold "
                 f"{a['counterfeit_units_all']} (to tourists {a['counterfeit_units_to_tourists']}); floors: "
                 f"{'; '.join(a['flags']) if a['flags'] else 'none'}")
    L += ["", "## Surprises", "", "SURPRISES_PLACEHOLDER", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--outdir", default="runs")
    a = ap.parse_args(argv)
    os.nice(19)
    logp = os.path.join(a.outdir, "pilot_choice_set_run.log")
    logf = open(logp, "a", encoding="utf-8")

    def log(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        logf.write(line + "\n"); logf.flush()

    t0 = time.time()
    meta = {"engine": ENGINE_VERSION,
            "commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
            "workers": a.workers, "load_start": [round(x, 2) for x in os.getloadavg()], "mem_start": memory_state()}
    log(f"pilot start; engine {ENGINE_VERSION}, commit {meta['commit'][:7]}, seeds {SEEDS}")
    p0s, p0runs, sel = {}, {}, None
    for n in COUNTS:
        log(f"P0 at {n} buyers")
        runs = run_jobs([("p0", n, s) for s in SEEDS], a.workers, log)
        p0s[n], p0runs[n] = check_p0(runs), runs
        log(f"P0 at {n}: {p0s[n]['share_genuine_ge1_customer']:.3f} / {p0s[n]['share_genuine_rated_day10']:.3f} "
            f"-> {'pass' if p0s[n]['passed'] else 'fail'}")
        if p0s[n]["passed"]:
            sel = n
            break
    p1 = p2 = p3 = None
    if sel:
        samples = {s: sample_stalls(sel, s) for s in SEEDS}
        log(f"P1: samples {samples}")
        jobs = [("p1", sel, s, sid, b) for s in SEEDS for sid in samples[s] for b in B.CANDIDATES[1:]]
        busts = {(r["key"][2], r["key"][3], r["key"][4]): r for r in run_jobs(jobs, a.workers, log)}
        never = {r["key"][2]: r for r in p0runs[sel]}
        p1 = check_p1(never, busts, samples)
        log(f"P1: {'pass' if p1['passed'] else 'fail'}")
        p2 = check_p2(run_jobs([("p2", sel, s, pl) for s in SEEDS for pl in ("posts", "patrolling")], a.workers, log))
        log(f"P2: {'pass' if p2['passed'] else 'fail'}")
        p3 = check_p3(run_jobs([("p3", sel, s, ro) for s in SEEDS for ro in ("fresh", "counterfeit")], a.workers, log))
        log(f"P3: {'pass' if p3['passed'] else 'fail'}")
    meta.update(wall_min=(time.time() - t0) / 60, load_end=[round(x, 2) for x in os.getloadavg()],
                mem_end=memory_state())
    with gzip.open(os.path.join(a.outdir, "pilot_choice_set.json.gz"), "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "selected": sel, "p0": {str(k): v for k, v in p0s.items()}, "p1": p1, "p2": p2,
                   "p3": p3}, f, default=str)
    with open(os.path.join(a.outdir, "pilot_choice_set.md"), "w", encoding="utf-8") as f:
        f.write(fmt_report(meta, sel, p0s, p1, p2, p3))
    log("pilot done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
