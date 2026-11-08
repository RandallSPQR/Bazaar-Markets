"""Run: the verification boundary (rule-based only). Spec 2026-11-08; predictions written 2026-11-08,
before any run.

Engine 0.13.0, choice-set demand (m 3, gamma 0, 150 buyers, budget 1.25 x base, bargain share 0.2 with
bargain Q_req [0.15, 0.40]), D = 30 known, ratings public (memory 0.7), brands on (premium 0.4), naive
deceptive sellers with fresh reopening, every genuine stall honest except the stall under test.

Benchmark: per seed 3 genuine stalls from default_rng([seed, 17]) (the same in every condition; stall
types come from the world stream alone), each busting out on day 20, 25, 28, 29 or 30
(rule_genuine_bust_at), plus one shared never chain per seed and condition.
  gain_unfloored = max over the bust-out days - never   (primary, as decided 2026-11-07 for the
                                                          capture run and kept here)
  gain_floored   = max over never and the bust-out days - never   (also reported)

Conditions (tourist share x local inspection probability; locals and experts split the rest evenly;
experts always inspect):
  t40|l1, t40|l0, t70|l1, t70|l0, t100 (tourists only)
Stage A: no inspectors. Stage B: 2 patrolling inspectors, not uniformed.

Predictions (confirmatory; per-seed mean over the 3 stalls; paired by seed; unadjusted 95% t-intervals):
  PV1 stage A, local 1.0: slope of the gain over tourist share (0.4, 0.7, 1.0) > 0
  PV2 stage A, tourists 0.4: gain(local 0.0) - gain(local 1.0) > 0
  PV3 stage A, tourists 1.0: gain > 0
  PV4 tourists 1.0: gain(stage B) - gain(stage A) < 0
Exploratory: verification level where the gain crosses 0; best day; harvest length; ratings after a
bust-out; harm by buyer profile; stage B - stage A gap by verification level.

    .venv/bin/python -m analysis.verification --stage A --seeds 200-229 --tests "..."
    .venv/bin/python -m analysis.verification --stage B --seeds 200-229 --tests "..."
    .venv/bin/python -m analysis.verification --timing B|t40|l1 --seeds 905-906 --outdir <scratch>
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import platform
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

import numpy as np

from analysis.capture import PROFILES, TAU, ProfileTap, _frame, _nice, _series, _window, _yaxis, memory_state
from analysis.counterfeit import STYLE, _ci, _d, _git, _load, _num, _t, _verdict
from analysis.floors import floor_flags, floor_series
from cli.sweep import parse_seeds
from engine import ENGINE_VERSION, bazaar, benchmark
from engine.config import load
from engine.metrics import mean_ci, paired_diff

DAYS = 30
NEVER = benchmark.NEVER
CANDS = list(benchmark.candidates([20, 25, 28, 29, 30], DAYS)[1:])
SAMPLE_STREAM, N_SAMPLE = 17, 3
MAIN_SEEDS = set(range(200, 230))
PILOT_SEEDS = set(range(905, 910))
COMMON = ["buyers.demand_mode=choice_set", "buyers.consider=3", "buyers.position_rent=0", "buyers.count=150",
          "buyers.budget_factor_override=1.25", "buyers.bargain_share=0.2", "buyers.bargain_q_req=[0.15,0.40]",
          "ratings.mode=public", "ratings.memory=0.7", "brands.enabled=true", "brands.premium=0.4",
          "market.horizon_known=true", f"market.days={DAYS}", "evolution.revise_prob=0", "evolution.mutation_prob=0",
          "agents.seller.deceptive=rule_deceptive", "agents.params.rule_deceptive.reopen=fresh",
          "agents.seller.genuine=rule_honest"]
SHARES = {"t40": '{"tourist":0.4,"local":0.3,"expert":0.3}', "t70": '{"tourist":0.7,"local":0.15,"expert":0.15}',
          "t100": '{"tourist":1.0,"local":0.0,"expert":0.0}'}
TSHARE = {"t40": 0.4, "t70": 0.7, "t100": 1.0}
BASE_CONDS = ["t40|l1", "t40|l0", "t70|l1", "t70|l0", "t100"]
CONDS = {s: [f"{s}|{c}" for c in BASE_CONDS] for s in ("A", "B")}


def parts(cond: str):
    xs = cond.split("|")
    stage, t = xs[0], xs[1]
    local = 1.0 if len(xs) < 3 else (1.0 if xs[2] == "l1" else 0.0)
    return stage, t, local


def verification(cond: str) -> float:
    """Share of buyers who verify an advertising stall: experts + locals x local inspection prob."""
    _, t, local = parts(cond)
    sh = json.loads(SHARES[t])
    return sh["expert"] + sh["local"] * local


def overrides(cond: str) -> list[str]:
    stage, t, local = parts(cond)
    ins = ["inspectors.count=0"] if stage == "A" else ["inspectors.count=2", "inspectors.uniformed=false"]
    return [*COMMON, f"buyers.profile_shares={SHARES[t]}", "inspectors.placement=patrolling", *ins,
            f"agents.params.rule_buyer.local_inspect_prob={local}"]


def config(cond: str, seed: int):
    return load(None, [*overrides(cond), f"seed={seed}"], mode="bazaar")


def sample_stalls(seed: int) -> list[str]:
    eng = bazaar.BazaarEngine(config(CONDS["A"][0], seed))
    gen = [st.sid for st in sorted(eng.stalls, key=lambda s: s.idx) if st.stype == "genuine"]
    pick = np.random.default_rng([seed, SAMPLE_STREAM]).choice(len(gen), size=N_SAMPLE, replace=False)
    return [gen[int(i)] for i in pick]


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ chains

def _job(args) -> dict:
    stage, cond, seed, watch, stall, b = args
    c = benchmark.bust_config(config(cond, seed), stall, b)
    tap = ProfileTap(watch)
    out = bazaar.run(c, log=tap)
    days = []
    for dd in out["days"]:
        o = dd["outcome"]
        days.append({"catches": o["catches"], "shortfall_rate": o["shortfall_rate"], **floor_series(o),
                     "rating": {s: dd["brand_ratings"].get(dd["brands"][s]) for s in watch},
                     "units": {s: o["brands"]["units_by_stall"][s] for s in watch},
                     "false_claims": o["false_claims"]["messages"]})
    busts = [(x["stall"], x["day"]) for dd in out["days"] for x in dd["bust_outs"]]
    return {"key": f"{cond}|{seed}|{stall}|{b}", "stage": stage, "cond": cond, "seed": seed, "stall": stall, "b": b,
            "totals": {s: benchmark.stall_total(out, s) for s in watch}, "days": days, "busts": busts,
            "profile": {str(k): v for k, v in sorted(tap.days.items())},
            "fallbacks": sum(x["outcome"]["fallbacks"]["buyer"] for x in out["days"])}


def jobs_for(conds: list[str], seeds: list[int], samples: dict) -> list[tuple]:
    out = []
    for seed in seeds:
        w = samples[seed]
        for cond in conds:
            out.append((cond[0], cond, seed, w, None, NEVER))
            for s in w:
                for b in CANDS:
                    out.append((cond[0], cond, seed, w, s, b))
    return out


def _key(j) -> str:
    return f"{j[1]}|{j[2]}|{j[4]}|{j[5]}"


def memory_ok(a) -> tuple[bool, dict]:
    s = memory_state()
    ok = (s["swap_free_mb"] is None or s["swap_free_mb"] >= a.min_swap_mb) and \
         (s["free_pct"] is None or s["free_pct"] >= a.min_free_pct)
    return ok, s


def run_chains(a, jobs, cache_path, log) -> tuple[list[dict], int]:
    """Runs jobs on a.workers processes, pausing new chains while memory is short; every finished
    chain is appended to the cache, which a rerun resumes from. Returns (runs, pauses)."""
    done = {}
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                done[r["key"]] = r
    todo = [j for j in jobs if _key(j) not in done]
    log(f"{len(jobs)} chains, {len(done)} cached, {len(todo)} to run; workers {a.workers}")
    t0, n, pauses = time.time(), 0, 0
    cache = open(cache_path, "a", encoding="utf-8") if cache_path else None
    with ProcessPoolExecutor(a.workers) as ex:
        it = iter(todo)
        live: set = set()
        exhausted = False
        while live or not exhausted:
            while not exhausted and len(live) < a.workers:
                ok, st = memory_ok(a)
                if not ok:
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
                live.add(ex.submit(_job, j))
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
    return [done[_key(j)] for j in jobs], pauses


# ------------------------------------------------------------------ analysis

def gains(runs, samples) -> dict:
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


def seed_mean(G, cond, seeds, field) -> list:
    return [float(np.mean([G[cond][sd][s][field] for s in G[cond][sd]])) for sd in seeds]


def _slope(xs, rows) -> list:
    x = np.array(xs, float)
    xc = x - x.mean()
    return [float((np.array(r, float) * xc).sum() / (xc ** 2).sum()) for r in rows]


def _harvest(rb, rn, s, b) -> dict:
    """From the chain where stall s busts out on day b: days from b until the stall's daily units
    first fall below half their mean over days b-5..b-1 (0 = on the bust-out day itself; None = not
    by day 30); the brand's rating before the bust-out (end of day b-1), its lowest rating from day
    b to 30 and at day 30, and the never chain's rating at day 30."""
    u = lambda r, d: r["days"][d - 1]["units"][s]
    pre = [u(rb, d) for d in range(max(1, b - 5), b)]
    base = float(np.mean(pre)) if pre else 0.0
    drop = next((d - b for d in range(b, DAYS + 1) if u(rb, d) < 0.5 * base), None) if base > 0 else "no sales before"
    rt = lambda r, d: r["days"][d - 1]["rating"][s]
    after = [rt(rb, d) for d in range(b, DAYS + 1) if rt(rb, d) is not None]
    return {"collapse_days": drop, "rating_pre": rt(rb, b - 1), "rating_min_after": min(after) if after else None,
            "rating_d30": rt(rb, DAYS), "rating_d30_never": rt(rn, DAYS),
            "below_tau": any(x < TAU for x in after), "base_units": base}


def analyse(stage, runs, seeds, samples) -> dict:
    G = gains(runs, samples)
    idx = {(r["cond"], r["seed"], r["stall"], r["b"]): r for r in runs}
    res: dict = {"stage": stage, "by_cond": {}, "harm": {}, "harvest": {}, "best_day": {}, "seeds": seeds}
    for cond in CONDS[stage]:
        allg = [G[cond][sd][s] for sd in seeds for s in G[cond][sd]]
        res["by_cond"][cond] = {"verification": verification(cond),
                                "unfloored": mean_ci(seed_mean(G, cond, seeds, "gain_unfloored")),
                                "floored": mean_ci(seed_mean(G, cond, seeds, "gain_floored")),
                                "share_positive": float(np.mean([g["gain_unfloored"] > 0 for g in allg])),
                                "never_total": mean_ci(seed_mean(G, cond, seeds, "never")),
                                "per_seed": seed_mean(G, cond, seeds, "gain_unfloored")}
        res["best_day"][cond] = {str(b): sum(g["best_day"] == b for g in allg) for b in CANDS}
        res["best_day"][cond]["never (floored)"] = sum(g["gain_floored"] == 0 for g in allg)
        harm = {p: {"short": [], "surplus": []} for p in PROFILES}
        hv = {b: [] for b in CANDS}
        for sd in seeds:
            per = {p: {"short": [], "surplus": []} for p in PROFILES}
            rn = idx[(cond, sd, None, NEVER)]
            for s, g in G[cond][sd].items():
                b = g["best_day"]
                rb = idx[(cond, sd, s, b)]
                wb, wn = _window(rb["profile"], range(b, DAYS + 1)), _window(rn["profile"], range(b, DAYS + 1))
                for p in PROFILES:
                    for k in ("short", "surplus"):
                        if wb[k][p] is not None and wn[k][p] is not None:
                            per[p][k].append(wb[k][p] - wn[k][p])
                for bb in CANDS:
                    hv[bb].append(_harvest(idx[(cond, sd, s, bb)], rn, s, bb))
            for p in PROFILES:
                for k in ("short", "surplus"):
                    harm[p][k].append(float(np.mean(per[p][k])) if per[p][k] else None)
        res["harm"][cond] = {p: {k: mean_ci(harm[p][k]) for k in ("short", "surplus")} for p in PROFILES}
        H = {}
        for bb, hs in hv.items():
            col = [h["collapse_days"] for h in hs if isinstance(h["collapse_days"], int)]
            H[str(bb)] = {"n": len(hs), "collapsed": len(col), "same_day": sum(c == 0 for c in col),
                          "median_days": float(np.median(col)) if col else None,
                          "rating_moved": sum(h["rating_min_after"] is not None and h["rating_pre"] is not None
                                              and h["rating_min_after"] < h["rating_pre"] - 1e-9 for h in hs),
                          "below_tau": sum(h["below_tau"] for h in hs),
                          "rating_d30": mean_ci([h["rating_d30"] for h in hs]),
                          "rating_d30_never": mean_ci([h["rating_d30_never"] for h in hs])}
        res["harvest"][cond] = H
    # predictions
    V = {c: seed_mean(G, c, seeds, "gain_unfloored") for c in CONDS[stage]}
    VF = {c: seed_mean(G, c, seeds, "gain_floored") for c in CONDS[stage]}
    res["pred"] = {}
    for name, VV in (("gain_unfloored", V), ("gain_floored", VF)):
        P = {}
        s = stage
        rows = list(zip(VV[f"{s}|t40|l1"], VV[f"{s}|t70|l1"], VV[f"{s}|t100"]))
        sl = [x * 0.1 for x in _slope([0.4, 0.7, 1.0], rows)]
        tag = "" if stage == "A" else " (stage B analogue, exploratory)"
        P["PV1" + ("" if stage == "A" else "b")] = {**mean_ci(sl), "unit": "per +0.1 of tourist share", "sign": +1,
                                                    "label": "local 1.0: slope of the gain over tourist share" + tag}
        P["PV2" + ("" if stage == "A" else "b")] = {**paired_diff(VV[f"{s}|t40|l1"], VV[f"{s}|t40|l0"]), "sign": +1,
                                                    "label": "tourists 0.4: local inspection off − on" + tag}
        P["PV3" + ("" if stage == "A" else "b")] = {**mean_ci(VV[f"{s}|t100"]), "sign": +1,
                                                    "label": "tourists 1.0: gain" + tag}
        for v in P.values():
            v["verdict"] = _verdict(v, v["sign"])
        res["pred"][name] = P
    # floors and schedule checks (never chains for floors)
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


def cross_stage(resA, resB) -> dict:
    """PV4 and the stage B - stage A gap by condition (paired by seed)."""
    out = {"gap": {}}
    for c in BASE_CONDS:
        a, b = resA["by_cond"][f"A|{c}"]["per_seed"], resB["by_cond"][f"B|{c}"]["per_seed"]
        out["gap"][c] = {**paired_diff(a, b), "verification": verification(f"A|{c}")}
    pv4 = dict(out["gap"]["t100"])
    pv4.update(sign=-1, label="tourists 1.0: stage B − stage A")
    pv4["verdict"] = _verdict(pv4, -1)
    out["PV4"] = pv4
    return out


def crossing(res) -> dict:
    """Verification share where the mean unfloored gain crosses 0, by linear interpolation between
    adjacent verification levels (conditions sorted by verification; ties averaged)."""
    pts: dict = {}
    for c, v in res["by_cond"].items():
        if v["unfloored"]["mean"] is not None:
            pts.setdefault(round(v["verification"], 4), []).append(v["unfloored"]["mean"])
    xs = sorted(pts)
    ys = [float(np.mean(pts[x])) for x in xs]
    for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if y0 == 0:
            return {"at": x0, "between": [x0, x0]}
        if (y0 > 0) != (y1 > 0):
            return {"at": x0 + (0 - y0) * (x1 - x0) / (y1 - y0), "between": [x0, x1]}
    return {"at": None, "points": list(zip(xs, ys))}


# ------------------------------------------------------------------ plots

def _yrange(stats):
    """y range in $ covering 0, every mean and every interval end."""
    vals = [0.0] + [s[k] / 100 for s in stats for k in ("mean", "lo", "hi") if s.get(k) is not None]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.1 or 1
    return lo - pad, hi + pad


NOTE = ("Bazaar engine {v}. Seeds {s} paired; 95% t-intervals, unadjusted; 3 sampled genuine stalls per seed; "
        "bust-out days 20, 25, 28, 29, 30; 30 days.")


def plot_gain_svg(results: dict, seeds_txt: str, version=ENGINE_VERSION) -> str:
    stages = [s for s in ("A", "B") if s in results]
    W, H, top, ph, pw = 900, 620, 120, 340, 300
    lefts = [130, 520][:len(stages)]
    allst = [results[s]["by_cond"][c]["unfloored"] for s in stages for c in CONDS[s]]
    lo, hi = _yrange(allst)
    Y = lambda y: top + ph - (y - lo) / (hi - lo) * ph
    out = _frame("Best bust-out gain against tourist share, with and without local inspection",
                 "Stage A: no inspectors; stage B: 2 patrolling inspectors. Experts always inspect.",
                 [NOTE.format(v=version, s=seeds_txt),
                  "Gain = the sampled stall's 30-day profit at its best bust-out day minus never busting out. Choice-set "
                  "demand (m 3, gamma 0), 150 buyers, budget 1.25 × base,",
                  "bargain hunters 0.2 (Q_req 0.15–0.40), naive deceptive sellers, fresh reopening, premium 0.4 "
                  "(placeholder). Locals and experts split the non-tourists evenly."],
                 W=W, H=H, desc="Mean gain with intervals at tourist shares 0.4, 0.7 and 1.0, local inspection on and off.")
    for k, s in enumerate(stages):
        left = lefts[k]
        X = lambda x, left=left: left + (x - 0.4) / 0.6 * pw
        res = results[s]
        out.append(f'<text class="lb" x="{left}" y="{top - 12}">{"stage A: no inspectors" if s == "A" else "stage B: 2 patrolling inspectors"}</text>')
        out.append(f'<line class="zero" x1="{X(0.4):.1f}" y1="{Y(0):.1f}" x2="{X(1.0):.1f}" y2="{Y(0):.1f}"/>')
        on = [res["by_cond"][f"{s}|t40|l1"]["unfloored"], res["by_cond"][f"{s}|t70|l1"]["unfloored"],
              res["by_cond"][f"{s}|t100"]["unfloored"]]
        off = [res["by_cond"][f"{s}|t40|l0"]["unfloored"], res["by_cond"][f"{s}|t70|l0"]["unfloored"],
               res["by_cond"][f"{s}|t100"]["unfloored"]]
        _series(out, X, Y, [0.4, 0.7, 1.0], on, "pt", -4, "locals inspect" if k == 0 else "", ldy=-8)
        _series(out, X, Y, [0.4, 0.7, 1.0], off, "hl", 4, "locals don't" if k == 0 else "", ldy=14)
        out.append(f'<line class="ax" x1="{X(0.4):.1f}" y1="{top + ph + 14}" x2="{X(1.0):.1f}" y2="{top + ph + 14}"/>')
        for t in (0.4, 0.7, 1.0):
            out.append(f'<text class="k" x="{X(t):.1f}" y="{top + ph + 30}" text-anchor="middle">{t:g}</text>')
        out.append(f'<text class="k" x="{left + pw / 2}" y="{top + ph + 50}" text-anchor="middle">tourist share</text>')
        if k == 0:
            _yaxis(out, Y, lo, hi, left - 14, "gain, $ per stall over 30 days", top, ph)
    out.append("</svg>")
    return "\n".join(out) + "\n"


def plot_bestday_svg(results: dict, seeds_txt: str, version=ENGINE_VERSION) -> str:
    stages = [s for s in ("A", "B") if s in results]
    W, H = 900, 640
    top, rowh, colw, left0 = 120, 82, 330, 200
    out = _frame("Which bust-out day is best, by condition",
                 "Stall-seeds whose best bust-out day (unfloored) is each candidate; \u201cnever\u201d = how many would rather not bust out",
                 [NOTE.format(v=version, s=seeds_txt),
                  "Bars count stall-seeds (3 per seed). The grey count is the floored best response (never) among them."],
                 W=W, H=H, desc="Counts of best bust-out days per condition and stage.")
    n_max = max(max(results[s]["best_day"][c][str(b)] for b in CANDS) for s in stages for c in CONDS[s]) or 1
    for k, s in enumerate(stages):
        x0 = left0 + k * colw
        out.append(f'<text class="lb" x="{x0}" y="{top - 14}">{"stage A" if s == "A" else "stage B"}</text>')
        for i, c in enumerate(BASE_CONDS):
            y0 = top + i * rowh
            bd = results[s]["best_day"][f"{s}|{c}"]
            if k == 0:
                _, t, loc = parts(f"A|{c}")
                lab = f"tourists {TSHARE[t]:g}" + ("" if c == "t100" else (", locals inspect" if loc else ", locals don't"))
                out.append(f'<text class="lb" x="{left0 - 14}" y="{y0 + 34}" text-anchor="end">{lab}</text>')
            bw = 40
            for j, b in enumerate(CANDS):
                n = bd[str(b)]
                h = 50 * n / n_max
                bx = x0 + j * (bw + 12)
                out.append(f'<rect class="bar" x="{bx}" y="{y0 + 52 - h:.1f}" width="{bw}" height="{h:.1f}"/>')
                out.append(f'<text class="k" x="{bx + bw / 2}" y="{y0 + 48 - h:.1f}" text-anchor="middle">{n}</text>')
                if i == len(BASE_CONDS) - 1:
                    out.append(f'<text class="k" x="{bx + bw / 2}" y="{y0 + 68}" text-anchor="middle">day {b}</text>')
            out.append(f'<text class="k" x="{x0 + len(CANDS) * (bw + 12) + 4}" y="{y0 + 48}">never: '
                       f'{bd["never (floored)"]}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ report

def _stage_lines(stage, meta, res) -> list[str]:
    L = [f"## Stage {stage}: {'no inspectors' if stage == 'A' else '2 patrolling inspectors'}", "", "### Run record", "",
         f"- Engine `{meta['engine_version']}`; commit `{meta['git']['commit']}`; uncommitted at run time: "
         f"{meta['git']['status_porcelain'] or 'none'}",
         f"- Script sha256 `{meta['script_sha256']}`",
         f"- Command: `{meta['command']}`",
         f"- Tests: {meta['tests']}",
         f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
         f"- {meta['chains']} chains × {DAYS} days on {meta['workers']} workers (nice 19); wall clock "
         f"{meta['wall_h']:.2f} h; load average {meta['load_start']} at start, {meta['load_end']} at end; memory at start "
         f"{meta['mem_start']}, at end {meta['mem_end']}; memory-guard pauses: {meta['pauses']}",
         f"- Seeds {meta['seeds_txt']} ({len(res['seeds'])}), paired{'; ' + meta['seed_note'] if meta.get('seed_note') else ''}",
         "- Sampled stalls per seed: " + "; ".join(f"{sd}: {', '.join(meta['samples'][str(sd)])}" for sd in res["seeds"]), ""]
    L += ["### Gain by condition", "",
          *_t(["Condition", "Verifying share", "Unfloored gain ($)", "Floored gain ($)", "Stall-seeds with a positive gain",
               "Never-bust total ($)"],
              [[c.split("|", 1)[1], f"{v['verification']:.2f}", _ci(v["unfloored"], _d), _ci(v["floored"], _d),
                f"{100 * v['share_positive']:.0f}%", _ci(v["never_total"], _d, signed=False)]
               for c, v in res["by_cond"].items()]), ""]
    L += ["### Predictions" + (" (confirmatory)" if stage == "A" else " (stage B analogues: exploratory)"), "",
          "Gain in $ per sampled stall over 30 days (per-seed mean of 3 stalls).", "",
          *_t(["Prediction", "Unfloored gain (primary)", "Verdict", "Floored gain", "Verdict"],
              [[f"**{k}**: {v['label']}" + (f" ({v['unit']})" if "unit" in v else ""), _ci(v, _d), v["verdict"],
                _ci(res["pred"]["gain_floored"][k], _d), res["pred"]["gain_floored"][k]["verdict"]]
               for k, v in res["pred"]["gain_unfloored"].items()]), ""]
    cr = res.get("crossing", {})
    L += ["### Where the gain crosses 0 (exploratory)", "",
          (f"Mean unfloored gain crosses 0 at a verifying share of about {cr['at']:.2f} "
           f"(linear interpolation between {cr['between'][0]:.2f} and {cr['between'][1]:.2f})."
           if cr.get("at") is not None else "The mean unfloored gain does not change sign across the verifying shares "
           f"tested ({', '.join(f'{x:.2f}: {_d(y, True)}' for x, y in cr.get('points', []))})."), ""]
    L += ["### Best bust-out day (exploratory)", "",
          *_t(["Condition", *[f"day {b}" for b in CANDS], "never best (floored)"],
              [[c.split("|", 1)[1], *[str(res["best_day"][c][str(b)]) for b in CANDS],
                str(res["best_day"][c]["never (floored)"])] for c in CONDS[stage]]), ""]
    L += ["### Harvest and ratings after a bust-out (exploratory)", "",
          "From the chain where each sampled stall busts out on day 20 (the longest harvest window). Collapse = the "
          "stall's daily units first below half its mean over the 5 days before; 0 days = on the bust-out day. Rating "
          "moved = its brand rating fell below its pre-bust value at some point by day 30.", "",
          *_t(["Condition", "Collapsed by day 30", "Same day", "Median days to collapse", "Rating moved",
               "Rating below τ", "Rating at day 30 (bust)", "Rating at day 30 (never)"],
              [[c.split("|", 1)[1], f"{h['collapsed']}/{h['n']}", str(h["same_day"]),
                "–" if h["median_days"] is None else f"{h['median_days']:g}", f"{h['rating_moved']}/{h['n']}",
                f"{h['below_tau']}/{h['n']}", _ci(h["rating_d30"], _num(2), signed=False),
                _ci(h["rating_d30_never"], _num(2), signed=False)]
               for c, H in res["harvest"].items() for h in [H["20"]]]), ""]
    L += ["### Harm by buyer profile at the best bust-out day (exploratory)", "",
          "Bust chain at the stall's best day minus the never chain, days from the bust-out to 30; per seed the mean over "
          "the 3 stalls. Shortfall in points of purchases; surplus in $ per buyer of the profile.", "",
          *_t(["Condition", *[f"{p}: shortfall (pts)" for p in PROFILES], *[f"{p}: surplus ($)" for p in PROFILES]],
              [[c.split("|", 1)[1], *[_ci(h[p]["short"], lambda x, s: _num(1)(100 * x, s)) for p in PROFILES],
                *[_ci(h[p]["surplus"], _d) for p in PROFILES]] for c, h in res["harm"].items()]), ""]
    L += ["### Floors, invalid actions and schedule checks", ""]
    L += [f"- {f}" for f in res["flags"]] or ["- none"]
    L += [""]
    return L


def report(results: dict, metas: dict, cross: dict | None, svgs: list, old: str | None) -> str:
    L = ["# The verification boundary", "",
         "Run spec \"fixes, pilot gate, then the verification boundary (rule-based only)\"; predictions written "
         "2026-11-08, before any run. Pilot gate: `runs/pilot_verification.md`.", "",
         "## Design (prespecified)", "",
         "- Engine 0.13.0, choice-set demand: m 3, gamma 0, 150 buyers, budget 1.25 × base, bargain hunters 0.2 with "
         "Q_req 0.15–0.40; D = 30 known; ratings public (memory 0.7); brands on (premium 0.4, placeholder); naive "
         "deceptive sellers, fresh reopening; every genuine stall honest except the stall under test.",
         "- Conditions: tourist share {0.4, 0.7} × local inspection probability {1.0, 0.0}, plus tourist share 1.0; locals "
         "and experts split the non-tourists evenly; experts always inspect. Stage A: no inspectors. Stage B: 2 "
         "patrolling inspectors, not uniformed.",
         "- Benchmark: per seed 3 genuine stalls from `default_rng([seed, 17])`, the same in every condition, each busting "
         "out on day 20, 25, 28, 29 or 30; one shared never chain per seed and condition. Gain = the stall's 30-day "
         "profit at the best bust-out day minus never (**unfloored, primary**, the convention decided 2026-11-07); the "
         "floored version (best of never and the bust-out days) is also reported.",
         "- Verifying share = experts + locals × local inspection probability (the share of buyers who inspect an "
         "advertising stall): 0.60, 0.30, 0.30, 0.15, 0.",
         "- Paired by seed; 95% t-intervals, unadjusted. Confirmatory: PV1–PV3 (stage A), PV4 (stage B − stage A at "
         "tourist share 1.0). Everything else exploratory.", ""]
    seeds_txt = None
    for s in ("A", "B"):
        if s in results:
            L += _stage_lines(s, metas[s], results[s])
            seeds_txt = metas[s]["seeds_txt"]
    if cross:
        p = cross["PV4"]
        L += ["## Stage B − stage A", "",
              f"**PV4** (confirmatory): {p['label']}: {_ci(p, _d)} — {p['verdict']}.", "",
              "Gap by condition (exploratory): does enforcement matter more when verification is low?", "",
              *_t(["Condition", "Verifying share", "Stage B − stage A, unfloored gain ($)"],
                  [[c, f"{v['verification']:.2f}", _ci(v, _d)] for c, v in cross["gap"].items()]), ""]
    for path, alt in svgs:
        L += [f"![{alt}]({path})", ""]
    reading, caveats = "READING_PLACEHOLDER", "CAVEATS_PLACEHOLDER"
    if old:
        if "## Reading (written after the results)\n\n" in old:
            reading = old.split("## Reading (written after the results)\n\n", 1)[1].split("\n\n## Caveats", 1)[0]
        if "## Caveats\n\n" in old:
            caveats = old.split("## Caveats\n\n", 1)[1].rstrip()
    L += ["## Reading (written after the results)", "", reading, "", "## Caveats", "", caveats, ""]
    return "\n".join(L)


# ------------------------------------------------------------------ main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["A", "B"])
    ap.add_argument("--timing", help="run one condition at full size (pilot G4) and print the wall clock")
    ap.add_argument("--seeds", default="200-229")
    ap.add_argument("--seed-note", default="")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--outdir", default="runs")
    ap.add_argument("--tests", default="")
    ap.add_argument("--min-swap-mb", type=float, default=512)   # macOS shrinks total swap; see pilot notes
    ap.add_argument("--min-free-pct", type=float, default=15)
    ap.add_argument("--pipeline-check", action="store_true",
                    help="pilot seeds 905-909 only, into an --outdir other than runs; outputs are discarded")
    a = ap.parse_args(argv)
    seeds = parse_seeds(a.seeds)
    os.nice(19)
    os.makedirs(a.outdir, exist_ok=True)
    if a.timing:
        if not set(seeds) <= PILOT_SEEDS:
            raise SystemExit("timing runs use pilot seeds 905-909 only")
        t0 = time.time()
        samples = {sd: sample_stalls(sd) for sd in seeds}
        runs, pauses = run_chains(a, jobs_for([a.timing], seeds, samples), None, print)
        wall = time.time() - t0
        print(json.dumps({"cond": a.timing, "seeds": seeds, "chains": len(runs), "wall_s": wall,
                          "per_chain_s": wall / len(runs), "pauses": pauses, "load": _load(), "memory": memory_state()}))
        return 0
    if not a.stage:
        raise SystemExit("--stage or --timing")
    if a.pipeline_check:
        if not set(seeds) <= PILOT_SEEDS or os.path.abspath(a.outdir) == os.path.abspath("runs"):
            raise SystemExit("--pipeline-check uses pilot seeds 905-909 and an outdir other than runs")
    elif not set(seeds) <= MAIN_SEEDS:
        raise SystemExit("the main run uses seeds 200-229 only")
    logp = os.path.join(a.outdir, f"verification_{a.stage}_run.log")
    logf = open(logp, "a", encoding="utf-8")

    def log(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        logf.write(line + "\n"); logf.flush()

    t0 = time.time()
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
            "command": " ".join(["python -m analysis.verification", *sys.argv[1:]]), "tests": a.tests,
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
            "workers": a.workers, "load_start": _load(), "mem_start": memory_state(), "seeds_txt": a.seeds,
            "seed_note": a.seed_note}
    log(f"stage {a.stage}: engine {ENGINE_VERSION}, commit {meta['git']['commit'][:7]}, seeds {a.seeds}")
    samples = {sd: sample_stalls(sd) for sd in seeds}
    meta["samples"] = {str(k): v for k, v in samples.items()}
    jobs = jobs_for(CONDS[a.stage], seeds, samples)
    runs, pauses = run_chains(a, jobs, os.path.join(a.outdir, f"verification_cache_{a.stage}.jsonl"), log)
    res = analyse(a.stage, runs, seeds, samples)
    res["crossing"] = crossing(res)
    meta.update(chains=len(runs), pauses=pauses, wall_h=(time.time() - t0) / 3600, load_end=_load(),
                mem_end=memory_state())
    G = gains(runs, samples)
    with open(os.path.join(a.outdir, f"verification_{a.stage}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["stage", "condition", "verifying_share", "seed", "stall", "gain_unfloored_cents", "gain_floored_cents",
                    "best_day", "never_total_cents", *[f"total_day{b}_cents" for b in CANDS]])
        for cond in CONDS[a.stage]:
            for sd in seeds:
                for s, g in G[cond][sd].items():
                    w.writerow([a.stage, cond, f"{verification(cond):.2f}", sd, s, g["gain_unfloored"], g["gain_floored"],
                                g["best_day"], g["never"], *[g["totals"][b] for b in CANDS]])
    with gzip.open(os.path.join(a.outdir, f"verification_{a.stage}.json.gz"), "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": res, "runs": runs}, f, separators=(",", ":"))
    del runs, G
    # report over every stage present
    results, metas = {}, {}
    for s in ("A", "B"):
        p = os.path.join(a.outdir, f"verification_{s}.json.gz")
        if os.path.exists(p):
            with gzip.open(p, "rt", encoding="utf-8") as f:
                d = json.load(f)
            results[s], metas[s] = d["results"], d["meta"]
            del d
    cross = cross_stage(results["A"], results["B"]) if {"A", "B"} <= set(results) else None
    if cross:
        results["B"]["cross"] = cross
    seeds_txt = metas[a.stage]["seeds_txt"]
    svgs = []
    for name, fn, alt in (("verification_gain.svg", plot_gain_svg, "gain against tourist share by local inspection"),
                          ("verification_best_day.svg", plot_bestday_svg, "best bust-out day by condition")):
        with open(os.path.join(a.outdir, name), "w", encoding="utf-8") as f:
            f.write(fn(results, seeds_txt))
        svgs.append((name, alt))
    sp = os.path.join(a.outdir, "verification_summary.md")
    old = open(sp, encoding="utf-8").read() if os.path.exists(sp) else None
    with open(sp, "w", encoding="utf-8") as f:
        f.write(report(results, metas, cross, svgs, old))
    flags = results[a.stage]["flags"]
    log(f"stage {a.stage} done; {len(flags)} flags; wall {meta['wall_h']:.2f} h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
