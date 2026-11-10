"""Run: enforcement intensity and limited liability (rule-based only). Spec "Core model: enforcement
intensity and limited liability" (2026-11-10); predictions written 2026-11-10, before any run.

Engine 0.15.0. Market as the verification run (analysis/verification.py): choice-set demand (m 3,
gamma 0, 150 buyers, budget 1.25 x base, bargain share 0.2 with Q_req [0.15, 0.40]), D = 30 known,
ratings public (memory 0.7), brands on (premium 0.4), naive deceptive sellers with fresh reopening,
every genuine stall honest except the stall under test; 2 patrolling inspectors, not uniformed.

Conditions: verification {tourist share 0.4 with locals inspecting (t40), tourist share 1.0 (t100)}
x inspectors.detect_scale {0, 0.1, 0.3, 1.0} x liability {collectible (col): penalty lag 0, no exit;
judgment-proof (jp): penalty lag 3 days, exit candidates} = 16 conditions.

Benchmark: per seed 3 genuine stalls from default_rng([seed, 17]) (verification.sample_stalls, the
same in every condition) and one shared never chain per seed and condition.
  col candidates: bust out on day 20, 25, 28, 29 or 30 (no exit)
  jp candidates:  (b, h) for b in {20, 25, 28}, h in {1, 3}: bust out on day b, exit at the end of
                  day b + h - 1 (keys "20h1" ...)
  gain_unfloored = max over the candidates - never   (primary, decided 2026-11-10 with the PI)
  gain_floored   = max over never and the candidates - never   (also reported)
Gain = the stall's collected 30-day profit (fines charged in its accounts by day 30).

Predictions (per-seed mean over the 3 stalls; paired by seed; unadjusted 95% t-intervals):
  PL1 (confirmatory) col, t100: the gain falls as detect_scale rises (per-seed OLS slope over the
      detect_scale levels < 0)
  PL2 (confirmatory) t100, detect_scale 1.0: jp gain - col gain > 0
  PL3 (confirmatory) jp, t100, detect_scale 1.0: gain > 0
Exploratory: detect_scale where the gain crosses 0 in each arm; the same questions at t40; best
candidate by condition; uncollectible fines as a share of fines; catches per deceptive stall-day by
detect_scale (calibration anchor); honest-stall (never) profit by condition; harm by buyer profile.
Every chain also records the stuck-buyer guard (engine) and parked buyers (observer).

    .venv/bin/python -m analysis.liability --seeds 230-249 --tests "..."          # main run
    .venv/bin/python -m analysis.liability --timing col|t40|ds1.0 --seeds 910-911  # pilot G3
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import platform
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

import numpy as np

import analysis.verification as V
from analysis.capture import PROFILES, ProfileTap, _frame, _series, _window, _yaxis, memory_state
from analysis.counterfeit import _ci, _d, _git, _load, _num, _t, _verdict
from analysis.floors import floor_flags, floor_series
from cli.sweep import parse_seeds
from engine import ENGINE_VERSION, bazaar, benchmark
from engine.config import load
from engine.metrics import mean_ci, paired_diff

DAYS = 30
NEVER = benchmark.NEVER
COL_CANDS = list(benchmark.candidates([20, 25, 28, 29, 30], DAYS)[1:])
JP_CANDS = list(benchmark.exit_candidates([20, 25, 28], [1, 3], DAYS)[1:])
DS_ALL = [0.0, 0.1, 0.3, 1.0]
VER = {"t40": "B|t40|l1", "t100": "B|t100"}       # verification-run conditions with 2 patrolling inspectors
VLAB = {"t40": "tourist share 0.4, locals inspect", "t100": "tourist share 1.0"}
ARMS = {"col": "collectible", "jp": "judgment-proof"}
LAG = {"col": 0, "jp": 3}
MAIN_SEEDS = set(range(230, 250))
PILOT_SEEDS = set(range(910, 915))


def conds(levels) -> list[str]:
    return [f"{arm}|{t}|ds{ds!r}" for arm in ARMS for t in VER for ds in levels]


def parts(cond: str):
    arm, t, d = cond.split("|")
    return arm, t, float(d[2:])


def ck(b) -> str:
    """JSON key of a candidate: NEVER, "20" (bust out on day 20) or "20h3" (bust out on 20, exit after 22)."""
    if b == NEVER:
        return NEVER
    return f"{b[0]}h{b[1]}" if isinstance(b, (tuple, list)) else str(int(b))


def cands(cond: str) -> list:
    return COL_CANDS if parts(cond)[0] == "col" else JP_CANDS


def bust_day(b) -> int:
    return int(b[0]) if isinstance(b, (tuple, list)) else int(b)


def overrides(cond: str) -> list[str]:
    arm, t, ds = parts(cond)
    return [*V.overrides(VER[t]), f"inspectors.detect_scale={ds!r}", f"pricing.penalty_lag_days={LAG[arm]}"]


def config(cond: str, seed: int):
    return load(None, [*overrides(cond), f"seed={seed}"], mode="bazaar")


sample_stalls = V.sample_stalls


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ chains

_PARKED: list = []


def _observe() -> None:
    """Parked-buyer observer (as analysis/certify_stuck.py): after each market day, buyers still in the
    market needing units within reach of the stall they chose (p.target), whatever its state."""
    from engine.bazaar import BazaarEngine
    if getattr(BazaarEngine.run, "_parked_observer", False):
        return
    orig = BazaarEngine.run

    def run(self, *a, **k):
        out = orig(self, *a, **k)
        r = self.cfg.market.interact_range
        _PARKED.append(sum(1 for p in self.buyers if p.active and not p.done and p.units < p.task["units"]
                           and p.target is not None and math.dist(p.pos, self.by_sid[p.target].pos) <= r))
        return out

    run._parked_observer = True
    BazaarEngine.run = run


def _lower_priority() -> None:
    """Run at nice 19. os.nice can raise EPERM on macOS when the process was started at nice 19 under
    nohup; the launch command sets nice 19 in that case."""
    try:
        cur = os.nice(0)
        if cur < 19:
            os.nice(19 - cur)
    except OSError:
        pass


def _init() -> None:
    _lower_priority()
    _observe()


def _job(args) -> dict:
    cond, seed, watch, stall, b = args
    _observe()
    c = benchmark.bust_config(config(cond, seed), stall, b)
    tap = ProfileTap(watch)
    _PARKED.clear()
    out = bazaar.run(c, log=tap)
    days = []
    for dd in out["days"]:
        o = dd["outcome"]
        L = o["liability"]
        days.append({"catches": o["catches"], "shortfall_rate": o["shortfall_rate"], **floor_series(o),
                     "rating": {s: dd["brand_ratings"].get(dd["brands"][s]) for s in watch},
                     "units": {s: o["brands"]["units_by_stall"][s] for s in watch},
                     "false_claims": o["false_claims"]["messages"],
                     "dec_stalls": L["deceptive_stalls"], "dec_catches": L["deceptive_catches"],
                     "fines_charged_cents": L["fines_charged_cents"],
                     "fines_uncollectible_cents": L["fines_uncollectible_cents"]})
    L = out["liability"]
    busts = [(x["stall"], x["day"]) for dd in out["days"] for x in dd["bust_outs"]]
    return {"key": f"{cond}|{seed}|{stall}|{ck(b)}", "cond": cond, "seed": seed, "stall": stall, "b": ck(b),
            "totals": {s: benchmark.stall_total(out, s) for s in watch}, "days": days, "busts": busts,
            "exited": L["exited"],
            "fines": {s: L["by_stall"].get(s, {"charged_cents": 0, "uncollectible_cents": 0, "outstanding_cents": 0})
                      for s in watch},
            "market_fines": {k: L[k] for k in ("fines_charged", "fines_charged_cents", "fines_uncollectible",
                                               "fines_uncollectible_cents", "fines_outstanding",
                                               "fines_outstanding_cents")},
            "dec_catches": L["deceptive_catches"], "dec_stall_days": L["deceptive_stall_days"],
            "guard": {"stuck_buyers": out["stuck_buyers"]["total"], "idle_choosers": out["idle_choosers"]["total"],
                      "parked": int(sum(_PARKED)), "buyer_days": sum(d["outcome"]["buyers_arrived"] for d in out["days"])},
            "profile": {str(k): v for k, v in sorted(tap.days.items())},
            "fallbacks": sum(x["outcome"]["fallbacks"]["buyer"] for x in out["days"])}


def jobs_for(cs: list[str], seeds: list[int], samples: dict) -> list[tuple]:
    out = []
    for seed in seeds:
        w = samples[seed]
        for cond in cs:
            out.append((cond, seed, w, None, NEVER))
            for s in w:
                for b in cands(cond):
                    out.append((cond, seed, w, s, b))
    return out


def _key(j) -> str:
    return f"{j[0]}|{j[1]}|{j[3]}|{ck(j[4])}"


def memory_ok(a) -> tuple[bool, dict]:
    s = memory_state()
    ok = (s["swap_free_mb"] is None or s["swap_free_mb"] >= a.min_swap_mb) and \
         (s["free_pct"] is None or s["free_pct"] >= a.min_free_pct)
    return ok, s


def run_chains(a, jobs, cache_path, log) -> tuple[list[dict], int]:
    """As verification.run_chains: a.workers processes at nice 19, new chains paused while memory is
    short, every finished chain appended to the cache (a rerun resumes from it)."""
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
    with ProcessPoolExecutor(a.workers, initializer=_init) as ex:
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
    """{cond: {seed: {stall: gain dict}}}; candidate keys as ck()."""
    idx = {(r["cond"], r["seed"], r["stall"], r["b"]): r for r in runs}
    out: dict = {}
    for r in runs:
        if r["b"] != NEVER:
            continue
        cond, seed = r["cond"], r["seed"]
        for s in samples[seed]:
            tot = {NEVER: r["totals"][s], **{ck(b): idx[(cond, seed, s, ck(b))]["totals"][s] for b in cands(cond)}}
            out.setdefault(cond, {}).setdefault(seed, {})[s] = benchmark.gain(tot)
    return out


def seed_mean(G, cond, seeds, field) -> list:
    return [float(np.mean([G[cond][sd][s][field] for s in G[cond][sd]])) for sd in seeds]


def _slope(xs, rows) -> list:
    return V._slope(xs, rows)


def _share(num, den):
    return num / den if den else None


def analyse(runs, seeds, samples, levels) -> dict:
    CS = conds(levels)
    G = gains(runs, samples)
    idx = {(r["cond"], r["seed"], r["stall"], r["b"]): r for r in runs}
    res: dict = {"levels": levels, "conds": CS, "seeds": seeds, "by_cond": {}, "harm": {}, "best": {},
                 "guard": {}, "fines": {}, "anchor": {}}
    for cond in CS:
        allg = [G[cond][sd][s] for sd in seeds for s in G[cond][sd]]
        res["by_cond"][cond] = {"unfloored": mean_ci(seed_mean(G, cond, seeds, "gain_unfloored")),
                                "floored": mean_ci(seed_mean(G, cond, seeds, "gain_floored")),
                                "share_positive": float(np.mean([g["gain_unfloored"] > 0 for g in allg])),
                                "never_total": mean_ci(seed_mean(G, cond, seeds, "never")),
                                "per_seed": seed_mean(G, cond, seeds, "gain_unfloored"),
                                "per_seed_floored": seed_mean(G, cond, seeds, "gain_floored")}
        res["best"][cond] = {ck(b): sum(g["best_day"] == ck(b) for g in allg) for b in cands(cond)}
        res["best"][cond]["never (floored)"] = sum(g["gain_floored"] == 0 for g in allg)
        # enforcement anchor and market fines, from the never chains
        nev = [idx[(cond, sd, None, NEVER)] for sd in seeds]
        res["anchor"][cond] = {"catches_per_dec_stall_day": mean_ci([_share(r["dec_catches"], r["dec_stall_days"])
                                                                      for r in nev]),
                               "catches_per_day": mean_ci([sum(d["catches"] for d in r["days"]) / DAYS for r in nev])}
        mf = {k: sum(r["market_fines"][k] for r in nev) for k in nev[0]["market_fines"]}
        # the tested stall at its best candidate
        tc = tu = 0
        for sd in seeds:
            for s, g in G[cond][sd].items():
                f = idx[(cond, sd, s, g["best_day"])]["fines"][s]
                tc += f["charged_cents"]
                tu += f["uncollectible_cents"]
        res["fines"][cond] = {"market_never": mf,
                              "market_uncollectible_share": _share(mf["fines_uncollectible_cents"],
                                                                   mf["fines_charged_cents"] + mf["fines_uncollectible_cents"]
                                                                   + mf["fines_outstanding_cents"]),
                              "market_outstanding_share": _share(mf["fines_outstanding_cents"],
                                                                 mf["fines_charged_cents"] + mf["fines_uncollectible_cents"]
                                                                 + mf["fines_outstanding_cents"]),
                              "tested_best_charged_cents": tc, "tested_best_uncollectible_cents": tu,
                              "tested_best_uncollectible_share": _share(tu, tc + tu)}
        # guard and parked, every chain of the condition
        rs = [r for r in runs if r["cond"] == cond]
        res["guard"][cond] = {k: sum(r["guard"][k] for r in rs)
                              for k in ("stuck_buyers", "parked", "idle_choosers", "buyer_days")}
        res["guard"][cond]["chains"] = len(rs)
        # harm by buyer profile at the best candidate, from its bust-out day to 30
        harm = {p: {"short": [], "surplus": []} for p in PROFILES}
        for sd in seeds:
            per = {p: {"short": [], "surplus": []} for p in PROFILES}
            rn = idx[(cond, sd, None, NEVER)]
            for s, g in G[cond][sd].items():
                b = g["best_day"]
                rb = idx[(cond, sd, s, b)]
                b0 = int(b.split("h")[0])
                wb, wn = _window(rb["profile"], range(b0, DAYS + 1)), _window(rn["profile"], range(b0, DAYS + 1))
                for p in PROFILES:
                    for k in ("short", "surplus"):
                        if wb[k][p] is not None and wn[k][p] is not None:
                            per[p][k].append(wb[k][p] - wn[k][p])
            for p in PROFILES:
                for k in ("short", "surplus"):
                    harm[p][k].append(float(np.mean(per[p][k])) if per[p][k] else None)
        res["harm"][cond] = {p: {k: mean_ci([x for x in harm[p][k] if x is not None]) for k in ("short", "surplus")}
                             for p in PROFILES}
    # predictions
    res["pred"] = {}
    dsl = [f"ds{x!r}" for x in levels]
    for name, field in (("gain_unfloored", "per_seed"), ("gain_floored", "per_seed_floored")):
        P = {}
        for t, sfx, conf in (("t100", "", True), ("t40", "b", False)):
            tag = "" if conf else " (exploratory)"
            rows = list(zip(*[res["by_cond"][f"col|{t}|{d}"][field] for d in dsl]))
            P[f"PL1{sfx}"] = {**mean_ci(_slope(levels, rows)), "sign": -1, "unit": "per 1.0 of detect_scale",
                              "label": f"collectible, {VLAB[t]}: slope of the gain over detect_scale{tag}"}
            P[f"PL2{sfx}"] = {**paired_diff(res["by_cond"][f"col|{t}|ds1.0"][field],
                                            res["by_cond"][f"jp|{t}|ds1.0"][field]), "sign": +1,
                              "label": f"{VLAB[t]}, detect_scale 1.0: judgment-proof − collectible{tag}"}
            P[f"PL3{sfx}"] = {**mean_ci(res["by_cond"][f"jp|{t}|ds1.0"][field]), "sign": +1,
                              "label": f"judgment-proof, {VLAB[t]}, detect_scale 1.0: gain{tag}"}
            rows = list(zip(*[res["by_cond"][f"jp|{t}|{d}"][field] for d in dsl]))
            P[f"PL1{sfx}-jp"] = {**mean_ci(_slope(levels, rows)), "sign": -1, "unit": "per 1.0 of detect_scale",
                                 "label": f"judgment-proof, {VLAB[t]}: slope of the gain over detect_scale (exploratory)"}
        for v in P.values():
            v["verdict"] = _verdict(v, v["sign"])
        res["pred"][name] = P
    res["crossing"] = {f"{arm}|{t}": crossing([res["by_cond"][f"{arm}|{t}|{d}"]["unfloored"]["mean"] for d in dsl], levels)
                       for arm in ARMS for t in VER}
    # flags: floors (never chains), invalid actions, schedules, guard
    v = {}
    for r in runs:
        if r["b"] == NEVER:
            v.setdefault(r["cond"], []).append(r)
    flags = floor_flags(v, list(range(26, DAYS + 1)), list(range(1, DAYS + 1)))
    for cond in CS:
        rs = [r for r in runs if r["cond"] == cond]
        fb = sum(r["fallbacks"] for r in rs)
        if fb:
            flags.append(f"{cond}: {fb} invalid buyer actions (fallbacks)")
        wrong = [r["key"] for r in rs if r["b"] != NEVER
                 and [list(x) for x in r["busts"]] != [[r["stall"], int(r["b"].split("h")[0])]]]
        if wrong:
            flags.append(f"{cond}: {len(wrong)} bust chains where the scheduled stall did not bust out exactly on its day")
        bad_exit = []
        for r in rs:
            want = {}
            if r["b"] != NEVER and "h" in r["b"]:
                b0, h = (int(x) for x in r["b"].split("h"))
                want = {r["stall"]: b0 + h - 1}
            if r["exited"] != want:
                bad_exit.append(r["key"])
        if bad_exit:
            flags.append(f"{cond}: {len(bad_exit)} chains whose exits differ from the schedule")
        extra = [r["key"] for r in rs if r["b"] == NEVER and r["busts"]]
        if extra:
            flags.append(f"{cond}: {len(extra)} never chains with a bust-out")
        g = res["guard"][cond]
        if g["stuck_buyers"] or g["parked"]:
            flags.append(f"{cond}: stuck buyers {g['stuck_buyers']}, parked buyers {g['parked']} (gate: both must be 0)")
    res["flags"] = flags
    return res


def crossing(ys, xs) -> dict:
    """detect_scale where the mean gain crosses 0, by linear interpolation between adjacent levels."""
    for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if y0 == 0:
            return {"at": x0, "between": [x0, x0]}
        if (y0 > 0) != (y1 > 0):
            return {"at": x0 + (0 - y0) * (x1 - x0) / (y1 - y0), "between": [x0, x1]}
    return {"at": None, "points": list(zip(xs, ys))}


# ------------------------------------------------------------------ plots

NOTE = ("Bazaar engine {v}. Seeds {s} paired; 95% t-intervals, unadjusted; 3 sampled genuine stalls per seed; "
        "30 days; 2 patrolling inspectors.")


def _yr(stats):
    vals = [0.0] + [s[k] / 100 for s in stats for k in ("mean", "lo", "hi") if s.get(k) is not None]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.1 or 1
    return lo - pad, hi + pad


def plot_gain_svg(res: dict, seeds_txt: str, version=ENGINE_VERSION) -> str:
    """Gain against detect_scale (square-root scale) by liability arm; one panel per verification level."""
    levels = res["levels"]
    dsl = [f"ds{x!r}" for x in levels]
    W, H, top, ph, pw = 900, 620, 120, 340, 280
    lefts = [130, 490]
    lo, hi = _yr([res["by_cond"][c]["unfloored"] for c in res["conds"]])
    Y = lambda y: top + ph - (y - lo) / (hi - lo) * ph
    out = _frame("Best bust-out gain against enforcement intensity, collectible and judgment-proof",
                 "Collectible: fined at the catch, no exit. Judgment-proof: fines due 3 days later; the stall exits "
                 "1 or 3 days after busting out.",
                 [NOTE.format(v=version, s=seeds_txt),
                  "Gain = the sampled stall's collected 30-day profit at its best candidate minus never busting out "
                  "(unfloored). detect_scale multiplies every catch probability;",
                  "x on a square-root scale. Choice-set demand (m 3), 150 buyers, budget 1.25 × base, bargain hunters "
                  "0.2, naive deceptive sellers, fresh reopening, premium 0.4."],
                 W=W, H=H, desc="Mean gain with intervals at detect_scale 0 to 1, by liability arm and verification level.")
    for k, t in enumerate(VER):
        left = lefts[k]
        X = lambda x, left=left: left + math.sqrt(x) * pw
        out.append(f'<text class="lb" x="{left}" y="{top - 12}">{VLAB[t]}</text>')
        out.append(f'<line class="zero" x1="{X(0):.1f}" y1="{Y(0):.1f}" x2="{X(1.0):.1f}" y2="{Y(0):.1f}"/>')
        col = [res["by_cond"][f"col|{t}|{d}"]["unfloored"] for d in dsl]
        jp = [res["by_cond"][f"jp|{t}|{d}"]["unfloored"] for d in dsl]
        _series(out, X, Y, levels, col, "pt", -4, "collectible" if k == 1 else "", ldy=14)
        _series(out, X, Y, levels, jp, "hl", 4, "judgment-proof" if k == 1 else "", ldy=-8)
        out.append(f'<line class="ax" x1="{X(0):.1f}" y1="{top + ph + 14}" x2="{X(1.0):.1f}" y2="{top + ph + 14}"/>')
        for x in levels:
            out.append(f'<text class="k" x="{X(x):.1f}" y="{top + ph + 30}" text-anchor="middle">{x:g}</text>')
        out.append(f'<text class="k" x="{left + pw / 2}" y="{top + ph + 50}" text-anchor="middle">detect_scale</text>')
        if k == 0:
            _yaxis(out, Y, lo, hi, left - 14, "gain, $ per stall over 30 days", top, ph)
    out.append("</svg>")
    return "\n".join(out) + "\n"


def plot_best_svg(res: dict, seeds_txt: str, version=ENGINE_VERSION) -> str:
    levels = res["levels"]
    rows = [(t, ds) for t in VER for ds in levels]
    W, top, rowh = 980, 120, 64
    H = top + rowh * len(rows) + 90
    left0, colw, bw = 210, 380, 34
    out = _frame("Which bust-out candidate is best, by condition",
                 "Stall-seeds whose best candidate (unfloored) is each one; “never” = how many would rather not bust out",
                 [NOTE.format(v=version, s=seeds_txt),
                  "Collectible: bust-out day. Judgment-proof: b/h = bust out on day b, exit at the end of day b + h − 1. "
                  "Bars count stall-seeds (3 per seed)."],
                 W=W, H=H, desc="Counts of best candidates per condition and liability arm.")
    n_max = max(max(res["best"][c][ck(b)] for b in cands(c)) for c in res["conds"]) or 1
    for k, arm in enumerate(ARMS):
        x0 = left0 + k * colw
        out.append(f'<text class="lb" x="{x0}" y="{top - 14}">{ARMS[arm]}</text>')
        for i, (t, ds) in enumerate(rows):
            c = f"{arm}|{t}|ds{ds!r}"
            y0 = top + i * rowh
            if k == 0:
                out.append(f'<text class="lb" x="{left0 - 14}" y="{y0 + 30}" text-anchor="end">'
                           f'{"tourists 0.4" if t == "t40" else "tourists 1.0"}, scale {ds:g}</text>')
            cs = cands(c)
            for j, b in enumerate(cs):
                n = res["best"][c][ck(b)]
                h = 40 * n / n_max
                bx = x0 + j * (bw + 8)
                out.append(f'<rect class="bar" x="{bx}" y="{y0 + 42 - h:.1f}" width="{bw}" height="{h:.1f}"/>')
                out.append(f'<text class="k" x="{bx + bw / 2}" y="{y0 + 38 - h:.1f}" text-anchor="middle">{n}</text>')
                if i == len(rows) - 1:
                    lab = ck(b).replace("h", "/")
                    out.append(f'<text class="k" x="{bx + bw / 2}" y="{y0 + 58}" text-anchor="middle">{lab}</text>')
            out.append(f'<text class="k" x="{x0 + len(cs) * (bw + 8) + 2}" y="{y0 + 38}">never: '
                       f'{res["best"][c]["never (floored)"]}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ report

def _cl(c):
    arm, t, ds = parts(c)
    return f"{ARMS[arm]}, {'t40' if t == 't40' else 't100'}, {ds:g}"


def _pct(x):
    return "–" if x is None else f"{100 * x:.1f}%"


def report(res: dict, meta: dict, svgs: list, old: str | None) -> str:
    levels = res["levels"]
    L = ["# Enforcement intensity and limited liability", "",
         "Run spec \"Core model: enforcement intensity and limited liability (rule-based only)\"; predictions written "
         "2026-11-10, before any run. Pilot gate: `runs/pilot_liability.md`.", "",
         "## Design (prespecified)", "",
         "- Engine 0.15.0. Market as the verification run: choice-set demand (m 3, gamma 0), 150 buyers, budget 1.25 × "
         "base, bargain hunters 0.2 (Q_req 0.15–0.40); D = 30 known; ratings public (memory 0.7); brands on (premium "
         "0.4, placeholder); naive deceptive sellers, fresh reopening; 2 patrolling inspectors, not uniformed; every "
         "genuine stall honest except the stall under test.",
         "- Conditions: verification {tourist share 0.4 with locals inspecting; tourist share 1.0} × detect_scale "
         f"{{{', '.join(f'{x:g}' for x in levels)}}} × liability {{collectible: fined at the catch, no exit; "
         "judgment-proof: fines due 3 days after the catch, exit candidates}}. A catch closes the stall at once in both arms.",
         "- Benchmark: per seed 3 genuine stalls from `default_rng([seed, 17])` (the verification sample), one shared "
         "never chain per seed and condition. Collectible candidates: bust out on day 20, 25, 28, 29 or 30. "
         "Judgment-proof candidates: bust out on day b ∈ {20, 25, 28} and exit at the end of day b + h − 1, h ∈ {1, 3}. "
         "Gain = the stall's collected 30-day profit at its best candidate minus never (**unfloored, primary**, decided "
         "2026-11-10); floored also reported.",
         "- Fines falling due after the stall has exited are uncollectible; fines falling due after day 30 at a stall "
         "still in the market are outstanding at close (decided 2026-11-10). Neither is in 30-day profit.",
         "- Paired by seed; 95% t-intervals, unadjusted. Confirmatory: PL1–PL3. Everything else exploratory.", ""]
    L += ["## Run record", "",
          f"- Engine `{meta['engine_version']}`; commit `{meta['git']['commit']}`; uncommitted at run time: "
          f"{meta['git']['status_porcelain'] or 'none'}",
          f"- Script sha256 `{meta['script_sha256']}`",
          f"- Command: `{meta['command']}`",
          f"- Tests: {meta['tests']}",
          f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
          f"- {meta['chains']} chains × {DAYS} days on {meta['workers']} workers (nice 19); wall clock "
          f"{meta['wall_h']:.2f} h; load average {meta['load_start']} at start, {meta['load_end']} at end; memory at "
          f"start {meta['mem_start']}, at end {meta['mem_end']}; memory-guard pauses: {meta['pauses']}",
          f"- Seeds {meta['seeds_txt']} ({len(res['seeds'])}), paired, fresh",
          "- Sampled stalls per seed: " + "; ".join(f"{sd}: {', '.join(meta['samples'][str(sd)])}" for sd in res["seeds"]),
          ""]
    L += ["## Gain by condition", "",
          *_t(["Liability", "Verification", "detect_scale", "Unfloored gain ($)", "Floored gain ($)",
               "Stall-seeds with a positive gain", "Never-bust total ($)"],
              [[ARMS[parts(c)[0]], VLAB[parts(c)[1]], f"{parts(c)[2]:g}", _ci(v["unfloored"], _d), _ci(v["floored"], _d),
                f"{100 * v['share_positive']:.0f}%", _ci(v["never_total"], _d, signed=False)]
               for c, v in res["by_cond"].items()]), ""]
    P, PF = res["pred"]["gain_unfloored"], res["pred"]["gain_floored"]
    L += ["## Predictions", "",
          "Gain in $ per sampled stall over 30 days (per-seed mean of 3 stalls). PL1–PL3 are confirmatory; the rows "
          "marked exploratory are the same questions at tourist share 0.4, and the judgment-proof slopes.", "",
          *_t(["Prediction", "Unfloored gain (primary)", "Verdict", "Floored gain", "Verdict"],
              [[f"**{k}**: {v['label']}" + (f" ({v['unit']})" if "unit" in v else ""), _ci(v, _d), v["verdict"],
                _ci(PF[k], _d), PF[k]["verdict"]] for k, v in P.items()]), ""]
    L += ["## Where the gain crosses 0 (exploratory)", ""]
    for key, cr in res["crossing"].items():
        arm, t = key.split("|")
        L.append(f"- {ARMS[arm]}, {VLAB[t]}: " + (
            f"the mean unfloored gain crosses 0 at detect_scale ≈ {cr['at']:.2f} (linear interpolation between "
            f"{cr['between'][0]:g} and {cr['between'][1]:g})." if cr.get("at") is not None else
            "no sign change (" + ", ".join(f"{x:g}: {_d(y, True)}" for x, y in cr["points"]) + ")."))
    L += [""]
    L += ["## Enforcement intensity: catches per deceptive stall-day (exploratory, calibration anchor)", "",
          "From the never chains (every genuine stall honest): catches at deceptive-type stalls divided by "
          "deceptive stall-days over the 30 days, per seed; and all catches per market day.", "",
          *_t(["Liability", "Verification", "detect_scale", "Catches per deceptive stall-day", "Catches per market day"],
              [[ARMS[parts(c)[0]], VLAB[parts(c)[1]], f"{parts(c)[2]:g}",
                _ci(a["catches_per_dec_stall_day"], _num(3), signed=False), _ci(a["catches_per_day"], _num(1), signed=False)]
               for c, a in res["anchor"].items()]), ""]
    L += ["## Fines: charged, uncollectible, outstanding (exploratory)", "",
          "Market: never chains, all seeds, all stalls. Tested stall: the sampled stall in the chain of its best "
          "candidate, all stall-seeds. Shares are of all fines from catches in the 30 days.", "",
          *_t(["Liability", "Verification", "detect_scale", "Market charged ($)", "Market outstanding at close",
               "Tested stall: charged ($)", "Tested stall: uncollectible ($)", "Tested stall: uncollectible share"],
              [[ARMS[parts(c)[0]], VLAB[parts(c)[1]], f"{parts(c)[2]:g}",
                _d(f["market_never"]["fines_charged_cents"]), _pct(f["market_outstanding_share"]),
                _d(f["tested_best_charged_cents"]), _d(f["tested_best_uncollectible_cents"]),
                _pct(f["tested_best_uncollectible_share"])] for c, f in res["fines"].items()]), ""]
    L += ["## Best candidate (exploratory)", "",
          *_t(["Condition", "Counts by candidate", "never best (floored)"],
              [[_cl(c), ", ".join(f"{k.replace('h', '/')}: {n}" for k, n in b.items() if k != "never (floored)"),
                str(b["never (floored)"])] for c, b in res["best"].items()]), ""]
    L += ["## Harm by buyer profile at the best candidate (exploratory)", "",
          "Bust chain at the stall's best candidate minus the never chain, days from the bust-out to 30; per seed the "
          "mean over the 3 stalls. Shortfall in points of purchases; surplus in $ per buyer of the profile.", "",
          *_t(["Condition", *[f"{p}: shortfall (pts)" for p in PROFILES], *[f"{p}: surplus ($)" for p in PROFILES]],
              [[_cl(c), *[_ci(h[p]["short"], lambda x, s: _num(1)(100 * x, s)) for p in PROFILES],
                *[_ci(h[p]["surplus"], _d) for p in PROFILES]] for c, h in res["harm"].items()]), ""]
    L += ["## Stuck and parked buyers by condition", "",
          "Every chain of the condition: the engine's end-of-day guard (stuck_buyers, idle_choosers) and the "
          "parked-buyer observer (a buyer still in the market needing units, within reach of the stall it chose).", "",
          *_t(["Condition", "Chains", "Buyer-days", "Stuck", "Parked", "Idle choosers"],
              [[_cl(c), str(g["chains"]), f"{g['buyer_days']:,}", str(g["stuck_buyers"]), str(g["parked"]),
                str(g["idle_choosers"])] for c, g in res["guard"].items()]), ""]
    L += ["## Floors, invalid actions, schedules and guard", ""]
    L += [f"- {f}" for f in res["flags"]] or ["- none"]
    L += [""]
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
    ap.add_argument("--timing", help="run one condition at full size (pilot G3) and print the wall clock")
    ap.add_argument("--seeds", default="230-249")
    ap.add_argument("--levels", default="0,0.1,0.3,1.0", help="detect_scale levels (pilot G3 may drop 0.3)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--outdir", default="runs")
    ap.add_argument("--tests", default="")
    ap.add_argument("--min-swap-mb", type=float, default=512)
    ap.add_argument("--min-free-pct", type=float, default=15)
    ap.add_argument("--pipeline-check", action="store_true",
                    help="pilot seeds 910-914 only, into an --outdir other than runs; outputs are discarded")
    a = ap.parse_args(argv)
    seeds = parse_seeds(a.seeds)
    levels = [float(x) for x in a.levels.split(",")]
    if not set(levels) <= set(DS_ALL) or 1.0 not in levels or 0.0 not in levels or levels != sorted(levels):
        raise SystemExit(f"levels must be a sorted subset of {DS_ALL} with 0 and 1.0")
    _lower_priority()
    os.makedirs(a.outdir, exist_ok=True)
    if a.timing:
        if not set(seeds) <= PILOT_SEEDS:
            raise SystemExit("timing runs use pilot seeds 910-914 only")
        t0 = time.time()
        samples = {sd: sample_stalls(sd) for sd in seeds}
        runs, pauses = run_chains(a, jobs_for([a.timing], seeds, samples), None, print)
        wall = time.time() - t0
        unc = sum(r["fines"][r["stall"]]["uncollectible_cents"] for r in runs if r["stall"])
        print(json.dumps({"cond": a.timing, "seeds": seeds, "chains": len(runs), "wall_s": wall,
                          "per_chain_s": wall / len(runs), "pauses": pauses, "load": _load(), "memory": memory_state(),
                          "tested_uncollectible_cents": unc,
                          "chains_with_uncollectible": sum(r["market_fines"]["fines_uncollectible"] > 0 for r in runs),
                          "guard": {k: sum(r["guard"][k] for r in runs) for k in ("stuck_buyers", "parked", "idle_choosers")}}))
        return 0
    if a.pipeline_check:
        if not set(seeds) <= PILOT_SEEDS or os.path.abspath(a.outdir) == os.path.abspath("runs"):
            raise SystemExit("--pipeline-check uses pilot seeds 910-914 and an outdir other than runs")
    elif not set(seeds) <= MAIN_SEEDS:
        raise SystemExit("the main run uses seeds 230-249 only")
    logp = os.path.join(a.outdir, "liability_run.log")
    logf = open(logp, "a", encoding="utf-8")

    def log(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        logf.write(line + "\n"); logf.flush()

    t0 = time.time()
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
            "command": " ".join(["python -m analysis.liability", *sys.argv[1:]]), "tests": a.tests,
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
            "workers": a.workers, "load_start": _load(), "mem_start": memory_state(), "seeds_txt": a.seeds,
            "levels": levels}
    log(f"liability: engine {ENGINE_VERSION}, commit {meta['git']['commit'][:7]}, seeds {a.seeds}, levels {levels}")
    samples = {sd: sample_stalls(sd) for sd in seeds}
    meta["samples"] = {str(k): v for k, v in samples.items()}
    CS = conds(levels)
    jobs = jobs_for(CS, seeds, samples)
    runs, pauses = run_chains(a, jobs, os.path.join(a.outdir, "liability_cache.jsonl"), log)
    res = analyse(runs, seeds, samples, levels)
    meta.update(chains=len(runs), pauses=pauses, wall_h=(time.time() - t0) / 3600, load_end=_load(),
                mem_end=memory_state())
    G = gains(runs, samples)
    allc = [ck(b) for b in COL_CANDS] + [ck(b) for b in JP_CANDS]
    idx = {(r["cond"], r["seed"], r["stall"], r["b"]): r for r in runs}
    with open(os.path.join(a.outdir, "liability.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["liability", "verification", "detect_scale", "seed", "stall", "gain_unfloored_cents",
                    "gain_floored_cents", "best", "never_total_cents", "best_fines_charged_cents",
                    "best_fines_uncollectible_cents", *[f"total_{c}_cents" for c in allc]])
        for cond in CS:
            arm, t, ds = parts(cond)
            for sd in seeds:
                for s, g in G[cond][sd].items():
                    fb = idx[(cond, sd, s, g["best_day"])]["fines"][s]
                    w.writerow([arm, t, f"{ds:g}", sd, s, g["gain_unfloored"], g["gain_floored"], g["best_day"], g["never"],
                                fb["charged_cents"], fb["uncollectible_cents"], *[g["totals"].get(c, "") for c in allc]])
    with gzip.open(os.path.join(a.outdir, "liability.json.gz"), "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": res, "runs": runs}, f, separators=(",", ":"))
    del runs, G, idx
    svgs = []
    for name, fn, alt in (("liability_gain.svg", plot_gain_svg, "gain against detect_scale by liability arm"),
                          ("liability_best.svg", plot_best_svg, "best bust-out candidate by condition")):
        with open(os.path.join(a.outdir, name), "w", encoding="utf-8") as f:
            f.write(fn(res, a.seeds))
        svgs.append((name, alt))
    sp = os.path.join(a.outdir, "liability_summary.md")
    old = open(sp, encoding="utf-8").read() if os.path.exists(sp) else None
    with open(sp, "w", encoding="utf-8") as f:
        f.write(report(res, meta, svgs, old))
    log(f"done; {len(res['flags'])} flags; wall {meta['wall_h']:.2f} h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
