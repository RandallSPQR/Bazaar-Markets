"""Run: licensing (rule-based only). Spec "Part 2: licensing" (2026-11-11); predictions written 2026-11-11,
before any run. Prepared, not launched: the pilot gate (analysis/pilot_licensing.py, runs/pilot_licensing.md)
gives the projected wall clock and the launch command.

Question: does licensing the brand (licensees cut quality, the owner collects royalties, the brand burns
down, enforcement catches the licensee, not the owner) make harvesting brand equity pay where busting out
does not?

Engine 0.16.0 (engine/licensing.py). Market as the liability run (analysis/liability.py): choice-set
demand (m 3, gamma 0, 150 buyers, budget 1.25 x base, bargain share 0.2 with Q_req [0.15, 0.40]), D = 30
known, ratings public (memory 0.7), brands on (premium 0.4), naive deceptive sellers with fresh reopening,
every genuine stall honest except the owner under test (who is always honest itself); 2 patrolling
inspectors, not uniformed; collectible fines (penalty lag 0, no exit). Royalty rho = 0.15 (placeholder).

Conditions:
  cheap licensees:    verification {t40: tourist share 0.4 with locals inspecting; t100: tourist share 1.0}
                      x detect_scale {0, 1} x owner_liable {free: no; liable: yes}       (8 conditions)
  contract licensees: verification {t40, t100}, detect_scale 1, owner not liable      (2 conditions)
Benchmark: per seed the 3 genuine stalls of default_rng([seed, 17]) (verification.sample_stalls, the same
in every condition), one never chain per seed, verification level and detect_scale (the licensing dials
are inert without a schedule, so it serves every licensing condition and the bust-out). Licensing
options (N, b): license to N in {2, 6} stalls from day b in {10, 20}. Bust-out candidates as the
liability run's collectible arm: day 20, 25, 28, 29 or 30 (bust-out chains have no licence, so they
depend only on verification and detect_scale).
  owner gain (unfloored, primary, as the standing convention) = max over the licensing options of the
      owner's 30-day profit (own sales + royalties - fines charged to it) - never
  floored = max over never and the options - never (also reported)
  bust-out gain: the same over the bust-out candidates

Predictions (per-seed mean over the 3 stalls; paired by seed; unadjusted 95% t-intervals):
  PX1 (confirmatory) cheap, t100, detect_scale 1, owner not liable: licensing gain > 0
  PX2 (confirmatory) same cell: licensing gain - best bust-out gain (t100, detect_scale 1) > 0
  PX3 (confirmatory) cheap, t100, detect_scale 1: liable - not liable < 0
Exploratory: everything at t40; detect_scale 0; contract licensing as honest growth; how fast the brand
rating falls; who bears the harm by buyer profile; fines by payer; best option.
Every chain records the stuck-buyer guard (engine) and parked buyers (observer).

    .venv/bin/python -m analysis.licensing --seeds 250-269 --tests "..."                   # main run
    .venv/bin/python -m analysis.licensing --timing "cheap|t100|ds1.0|free" --seeds 916-917  # pilot G3
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

import analysis.liability as LB
import analysis.verification as V
from analysis.capture import PROFILES, ProfileTap, _frame, _window, _yaxis, memory_state
from analysis.counterfeit import _ci, _d, _git, _load, _num, _t, _verdict
from analysis.floors import floor_flags, floor_series
from cli.sweep import parse_seeds
from engine import ENGINE_VERSION, bazaar, benchmark
from engine.config import load
from engine.metrics import mean_ci, paired_diff

DAYS = 30
NEVER = benchmark.NEVER
LIC_OPTS = list(benchmark.licence_options([2, 6], [10, 20], DAYS)[1:])
BUST_CANDS = list(benchmark.candidates([20, 25, 28, 29, 30], DAYS)[1:])
ROYALTY = 0.15
VER = {"t40": "B|t40|l1", "t100": "B|t100"}
VLAB = {"t40": "tourist share 0.4, locals inspect", "t100": "tourist share 1.0"}
MAIN_SEEDS = set(range(250, 270))
PILOT_SEEDS = set(range(915, 920))
LIC_CONDS = [f"cheap|{t}|ds{ds!r}|{lia}" for t in VER for ds in (0.0, 1.0) for lia in ("free", "liable")] + \
            [f"contract|{t}|ds1.0|free" for t in VER]
BASES = [(t, ds) for t in VER for ds in (0.0, 1.0)]       # never and bust-out chains


def parts(cond: str):
    q, t, d, lia = cond.split("|")
    return q, t, float(d[2:]), lia == "liable"


def base_key(t, ds) -> str:
    return f"{t}|ds{ds!r}"


def ok(o) -> str:
    """JSON key of an option: NEVER, "6x10" (licence to 6 from day 10) or "b20" (bust out on day 20)."""
    if o == NEVER:
        return NEVER
    return f"{o[0]}x{o[1]}" if isinstance(o, (tuple, list)) else f"b{int(o)}"


def overrides(t, ds, quality="cheap", liable=False) -> list[str]:
    return [*V.overrides(VER[t]), f"inspectors.detect_scale={ds!r}", "pricing.penalty_lag_days=0",
            f"licensing.quality={quality}", f"licensing.royalty={ROYALTY!r}",
            f"licensing.owner_liable={'true' if liable else 'false'}"]


def config(t, ds, seed, quality="cheap", liable=False):
    return load(None, [*overrides(t, ds, quality, liable), f"seed={seed}"], mode="bazaar")


sample_stalls = V.sample_stalls


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ chains
# A job: (kind, cond, seed, watch, stall, option); kind "never" | "lic" | "bust"; cond is a LIC_CONDS
# entry for "lic" and base_key(t, ds) otherwise.

def _cfg(job):
    kind, cond, seed, watch, stall, opt = job
    if kind == "lic":
        q, t, ds, lia = parts(cond)
        return benchmark.licence_config(config(t, ds, seed, q, lia), stall, opt)
    t, d = cond.split("|")
    c = config(t, float(d[2:]), seed)
    return benchmark.licence_config(c, None, NEVER) if kind == "never" else benchmark.bust_config(c, stall, opt)


def _key(j) -> str:
    return f"{j[0]}|{j[1]}|{j[2]}|{j[4]}|{ok(j[5])}"


def _job(args) -> dict:
    kind, cond, seed, watch, stall, opt = args
    LB._observe()
    tap = ProfileTap(watch)
    LB._PARKED.clear()
    out = bazaar.run(_cfg(args), log=tap)
    days = []
    for dd in out["days"]:
        o = dd["outcome"]
        lic = o.get("licensing", {}).get("owners", {})
        days.append({"catches": o["catches"], "shortfall_rate": o["shortfall_rate"], **floor_series(o),
                     "rating": {s: dd["brand_ratings"].get(dd["brands"][s]) for s in watch},
                     "units": {s: o["brands"]["units_by_stall"][s] for s in watch},
                     "lic": {s: lic[s] for s in watch if s in lic}})
    L = out["liability"]
    licences = sorted({(s, dd["day"]) for dd in out["days"] for s in dd["outcome"].get("licensing", {}).get("owners", {})})
    first = {}
    for s, d in licences:
        first.setdefault(s, d)
    return {"key": _key(args), "kind": kind, "cond": cond, "seed": seed, "stall": stall, "o": ok(opt),
            "totals": {s: benchmark.stall_total(out, s) for s in watch},
            "days": days, "busts": [(x["stall"], x["day"]) for dd in out["days"] for x in dd["bust_outs"]],
            "licence_start": first,
            "n_licensees": {s: len(next(d["lic"][s]["licensees"] for d in days if s in d["lic"])) for s in first},
            "fines": {s: L["by_stall"].get(s, {"charged_cents": 0}) for s in watch},
            "guard": {"stuck_buyers": out["stuck_buyers"]["total"], "idle_choosers": out["idle_choosers"]["total"],
                      "parked": int(sum(LB._PARKED)),
                      "buyer_days": sum(d["outcome"]["buyers_arrived"] for d in out["days"])},
            "profile": {str(k): v for k, v in sorted(tap.days.items())},
            "fallbacks": sum(x["outcome"]["fallbacks"]["buyer"] + x["outcome"]["fallbacks"]["seller"]
                             for x in out["days"])}


def jobs_for(lic_conds, bases, seeds, samples) -> list[tuple]:
    out = []
    for seed in seeds:
        w = samples[seed]
        for t, ds in bases:
            out.append(("never", base_key(t, ds), seed, w, None, NEVER))
        for cond in lic_conds:
            for s in w:
                for o in LIC_OPTS:
                    out.append(("lic", cond, seed, [s], s, o))
        for t, ds in bases:
            for s in w:
                for b in BUST_CANDS:
                    out.append(("bust", base_key(t, ds), seed, [s], s, b))
    return out


def run_chains(a, jobs, cache_path, log) -> tuple[list[dict], int]:
    """As liability.run_chains: a.workers processes at nice 19, new chains paused while memory is short,
    every finished chain appended to the cache (a rerun resumes from it)."""
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
    with ProcessPoolExecutor(a.workers, initializer=LB._init) as ex:
        it = iter(todo)
        live: set = set()
        exhausted = False
        while live or not exhausted:
            while not exhausted and len(live) < a.workers:
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

def _gain(totals: dict) -> dict:
    g = benchmark.gain(totals)
    return {"never": g["never"], "best": g["best_day"], "gain_unfloored": g["gain_unfloored"],
            "gain_floored": g["gain_floored"], "totals": totals}


def gains(runs, seeds, samples) -> tuple[dict, dict]:
    """({lic cond: {seed: {stall: gain}}}, {base key: {seed: {stall: gain}}}); option keys as ok()."""
    idx = {(r["kind"], r["cond"], r["seed"], r["stall"], r["o"]): r for r in runs}
    GL, GB = {}, {}
    for cond in sorted({r["cond"] for r in runs if r["kind"] == "lic"}, key=LIC_CONDS.index):
        q, t, ds, lia = parts(cond)
        for sd in seeds:
            nev = idx[("never", base_key(t, ds), sd, None, NEVER)]
            for s in samples[sd]:
                tot = {NEVER: nev["totals"][s], **{ok(o): idx[("lic", cond, sd, s, ok(o))]["totals"][s] for o in LIC_OPTS}}
                GL.setdefault(cond, {}).setdefault(sd, {})[s] = _gain(tot)
    for bk in sorted({r["cond"] for r in runs if r["kind"] == "bust"}):
        for sd in seeds:
            nev = idx[("never", bk, sd, None, NEVER)]
            for s in samples[sd]:
                tot = {NEVER: nev["totals"][s], **{ok(b): idx[("bust", bk, sd, s, ok(b))]["totals"][s] for b in BUST_CANDS}}
                GB.setdefault(bk, {}).setdefault(sd, {})[s] = _gain(tot)
    return GL, GB


def seed_mean(G, cond, seeds, field) -> list:
    return [float(np.mean([G[cond][sd][s][field] for s in G[cond][sd]])) for sd in seeds]


def _summ(G, cond, seeds, opts) -> dict:
    allg = [G[cond][sd][s] for sd in seeds for s in G[cond][sd]]
    return {"unfloored": mean_ci(seed_mean(G, cond, seeds, "gain_unfloored")),
            "floored": mean_ci(seed_mean(G, cond, seeds, "gain_floored")),
            "share_positive": float(np.mean([g["gain_unfloored"] > 0 for g in allg])),
            "never_total": mean_ci(seed_mean(G, cond, seeds, "never")),
            "per_seed": seed_mean(G, cond, seeds, "gain_unfloored"),
            "per_seed_floored": seed_mean(G, cond, seeds, "gain_floored"),
            "best": {**{ok(o): sum(g["best"] == ok(o) for g in allg) for o in opts},
                     "never (floored)": sum(g["gain_floored"] == 0 for g in allg)}}


def _option_day(o: str) -> int:
    return int(o.split("x")[1]) if "x" in o else int(o[1:])


def analyse(runs, seeds, samples) -> dict:
    GL, GB = gains(runs, seeds, samples)
    idx = {(r["kind"], r["cond"], r["seed"], r["stall"], r["o"]): r for r in runs}
    lconds = list(GL)
    res: dict = {"seeds": seeds, "lic_conds": lconds, "bases": list(GB), "lic": {}, "bust": {}, "rating": {},
                 "licence": {}, "harm": {}, "guard": {}}
    for c in lconds:
        res["lic"][c] = _summ(GL, c, seeds, LIC_OPTS)
    for bk in GB:
        res["bust"][bk] = _summ(GB, bk, seeds, BUST_CANDS)
    # brand rating trajectory by option (mean over stall-seeds), never included; licence accounting
    for c in lconds:
        q, t, ds, lia = parts(c)
        bk = base_key(t, ds)
        traj = {}
        for o in [NEVER, *map(ok, LIC_OPTS)]:
            rows = []
            for sd in seeds:
                for s in samples[sd]:
                    r = idx[("never", bk, sd, None, NEVER)] if o == NEVER else idx[("lic", c, sd, s, o)]
                    rows.append([d["rating"][s] if d["rating"][s] is not None else 0.5 for d in r["days"]])
            traj[o] = [float(x) for x in np.mean(rows, axis=0)]
        res["rating"][c] = traj
        acc = {}
        for o in map(ok, LIC_OPTS):
            per = {k: [] for k in ("royalties", "licensee_units", "owner_units_minus_never", "catches_at_licensees",
                                   "fines_to_owner", "fines_to_licensees", "licensee_q")}
            for sd in seeds:
                rn = idx[("never", bk, sd, None, NEVER)]
                acc_s = {k: [] for k in per}
                for s in samples[sd]:
                    r = idx[("lic", c, sd, s, o)]
                    b = _option_day(o)
                    L = [d["lic"][s] for d in r["days"] if s in d["lic"]]
                    acc_s["royalties"].append(sum(x["royalties_cents"] for x in L))
                    acc_s["licensee_units"].append(sum(x["licensee_units"] for x in L))
                    acc_s["owner_units_minus_never"].append(sum(x["owner_units"] for x in L)
                                                            - sum(d["units"][s] for d in rn["days"][b - 1:]))
                    acc_s["catches_at_licensees"].append(sum(x["catches_at_licensees"] for x in L))
                    acc_s["fines_to_owner"].append(sum(x["fines_at_licensees_to_owner_cents"] for x in L))
                    acc_s["fines_to_licensees"].append(sum(x["fines_at_licensees_to_licensees_cents"] for x in L))
                    qs = list(L[0]["licensee_q"].values()) if L else []
                    acc_s["licensee_q"].append(float(np.mean(qs)) if qs else float("nan"))
                for k in per:
                    per[k].append(float(np.nanmean(acc_s[k])))
            acc[o] = {k: mean_ci(v) for k, v in per.items() if v}
        res["licence"][c] = acc
        # harm by buyer profile at the best option, licence day to 30
        harm = {p: {"short": [], "surplus": []} for p in PROFILES}
        for sd in seeds:
            per = {p: {"short": [], "surplus": []} for p in PROFILES}
            rn = idx[("never", bk, sd, None, NEVER)]
            for s, g in GL[c][sd].items():
                o = g["best"]
                rb = idx[("lic", c, sd, s, o)]
                w = range(_option_day(o), DAYS + 1)
                wb, wn = _window(rb["profile"], w), _window(rn["profile"], w)
                for p in PROFILES:
                    for k in ("short", "surplus"):
                        if wb[k][p] is not None and wn[k][p] is not None:
                            per[p][k].append(wb[k][p] - wn[k][p])
            for p in PROFILES:
                for k in ("short", "surplus"):
                    harm[p][k].append(float(np.mean(per[p][k])) if per[p][k] else None)
        res["harm"][c] = {p: {k: mean_ci([x for x in harm[p][k] if x is not None]) for k in ("short", "surplus")}
                          for p in PROFILES}
    # guard, every chain of each kind and condition
    groups = {}
    for r in runs:
        groups.setdefault(f"{r['kind']}|{r['cond']}", []).append(r)
    for g, rs in groups.items():
        res["guard"][g] = {k: sum(r["guard"][k] for r in rs) for k in ("stuck_buyers", "parked", "idle_choosers",
                                                                        "buyer_days")}
        res["guard"][g]["chains"] = len(rs)
    # predictions
    res["pred"] = {}
    for name, field in (("gain_unfloored", "per_seed"), ("gain_floored", "per_seed_floored")):
        P = {}
        for t, sfx, conf in (("t100", "", True), ("t40", "b", False)):
            tag = "" if conf else " (exploratory)"
            for ds, dsx in ((1.0, ""), (0.0, "-ds0")):
                free, liab = f"cheap|{t}|ds{ds!r}|free", f"cheap|{t}|ds{ds!r}|liable"
                ex = tag if not dsx else " (exploratory)"
                bust = res["bust"][base_key(t, ds)][field]
                P[f"PX1{sfx}{dsx}"] = {**mean_ci(res["lic"][free][field]), "sign": +1,
                                       "label": f"cheap, {VLAB[t]}, detect_scale {ds:g}, owner not liable: licensing gain{ex}"}
                P[f"PX2{sfx}{dsx}"] = {**paired_diff(bust, res["lic"][free][field]), "sign": +1,
                                       "label": f"same cell: licensing gain − best bust-out gain{ex}"}
                P[f"PX3{sfx}{dsx}"] = {**paired_diff(res["lic"][free][field], res["lic"][liab][field]), "sign": -1,
                                       "label": f"cheap, {VLAB[t]}, detect_scale {ds:g}: liable − not liable{ex}"}
            con = f"contract|{t}|ds1.0|free"
            P[f"PC{sfx}"] = {**mean_ci(res["lic"][con][field]), "sign": +1,
                             "label": f"contract, {VLAB[t]}, detect_scale 1, owner not liable: licensing gain (exploratory)"}
            P[f"PC{sfx}-cheap"] = {**paired_diff(res["lic"][con][field], res["lic"][f"cheap|{t}|ds1.0|free"][field]),
                                   "sign": +1, "label": f"{VLAB[t]}, detect_scale 1: cheap − contract (exploratory)"}
        for v in P.values():
            v["verdict"] = _verdict(v, v["sign"])
        res["pred"][name] = P
    # flags
    flags = []
    v = {}
    for r in runs:
        if r["kind"] == "never":
            v.setdefault(r["cond"], []).append(r)
    flags += floor_flags(v, list(range(26, DAYS + 1)), list(range(1, DAYS + 1)))
    for g, rs in groups.items():
        fb = sum(r["fallbacks"] for r in rs)
        if fb:
            flags.append(f"{g}: {fb} invalid actions (fallbacks)")
        kind = g.split("|")[0]
        if kind == "lic":
            bad = [r["key"] for r in rs if r["busts"] or r["licence_start"] != {r["stall"]: _option_day(r["o"])}
                   or r["n_licensees"] != {r["stall"]: int(r["o"].split("x")[0])}]
            if bad:
                flags.append(f"{g}: {len(bad)} licensing chains whose licence differs from the option (or with a bust-out)")
        elif kind == "bust":
            bad = [r["key"] for r in rs if r["licence_start"] or [list(x) for x in r["busts"]] != [[r["stall"], int(r["o"][1:])]]]
            if bad:
                flags.append(f"{g}: {len(bad)} bust chains that did not bust out exactly on their day (or licensed)")
        else:
            bad = [r["key"] for r in rs if r["licence_start"] or r["busts"]]
            if bad:
                flags.append(f"{g}: {len(bad)} never chains with a licence or a bust-out")
        gg = res["guard"][g]
        if gg["stuck_buyers"] or gg["parked"]:
            flags.append(f"{g}: stuck buyers {gg['stuck_buyers']}, parked buyers {gg['parked']} (gate: both must be 0)")
    res["flags"] = flags
    return res


# ------------------------------------------------------------------ plots

NOTE = ("Bazaar engine {v}. Seeds {s} paired; 95% t-intervals, unadjusted; 3 sampled genuine owners per seed; "
        "30 days; 2 patrolling inspectors; royalty 0.15.")


def _cl(c):
    q, t, ds, lia = parts(c)
    return f"{q}, {t}, {ds:g}, {'owner liable' if lia else 'owner not liable'}"


def plot_gain_svg(res: dict, seeds_txt: str, version=ENGINE_VERSION) -> str:
    """Dot-and-interval rows per verification level: licensing (each condition) and bust-out gains."""
    rows_by_t = {t: [] for t in VER}
    for c in res["lic_conds"]:
        q, t, ds, lia = parts(c)
        lab = (f"license, cheap, scale {ds:g}, " + ("owner liable" if lia else "owner not liable")) if q == "cheap" \
            else "license, contract, scale 1"
        rows_by_t[t].append((lab, res["lic"][c]["unfloored"], "hl" if (q == "cheap" and ds == 1.0 and not lia) else "pt"))
    for bk in res["bases"]:
        t, d = bk.split("|")
        rows_by_t[t].append((f"bust out, scale {float(d[2:]):g}", res["bust"][bk]["unfloored"], "pt"))
    stats = [s for rs in rows_by_t.values() for _, s, _ in rs]
    vals = [0.0] + [s[k] / 100 for s in stats for k in ("mean", "lo", "hi") if s.get(k) is not None]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad
    W, top, rowh, left, pw = 900, 120, 26, 330, 480
    n = max(len(r) for r in rows_by_t.values())
    ph = rowh * n
    H = top + 2 * (ph + 60) + 120
    X = lambda x: left + (x - lo) / (hi - lo) * pw
    out = _frame("Owner's gain from licensing the brand, against busting out",
                 "Best option minus never (unfloored); licensing options N ∈ {2, 6} licensees from day 10 or 20",
                 [NOTE.format(v=version, s=seeds_txt),
                  "Cheap licensees: low true quality, claim the brand's quality, deceptive policy. Contract licensees: the "
                  "owner's quality. Bust-out candidates: day 20, 25, 28, 29, 30.",
                  "Highlighted: the confirmatory cell (PX1, PX2). Choice-set demand (m 3), 150 buyers, budget 1.25 × base, "
                  "premium 0.4, naive deceptive sellers, fresh reopening."],
                 W=W, H=H, desc="Mean owner gain with intervals per condition, licensing and bust-out, by verification level.")
    y0 = top
    for t in VER:
        out.append(f'<text class="lb" x="{left}" y="{y0 - 10}">{VLAB[t]}</text>')
        out.append(f'<line class="zero" x1="{X(0):.1f}" y1="{y0}" x2="{X(0):.1f}" y2="{y0 + ph}"/>')
        for i, (lab, s, cls) in enumerate(rows_by_t[t]):
            y = y0 + i * rowh + rowh / 2
            out.append(f'<text class="k" x="{left - 12}" y="{y + 4:.1f}" text-anchor="end">{lab}</text>')
            if s.get("lo") is not None:
                out.append(f'<line class="{"ci" if cls == "pt" else "hlc"}" x1="{X(s["lo"] / 100):.1f}" y1="{y:.1f}" '
                           f'x2="{X(s["hi"] / 100):.1f}" y2="{y:.1f}"/>')
            if s.get("mean") is not None:
                out.append(f'<circle class="{cls}" cx="{X(s["mean"] / 100):.1f}" cy="{y:.1f}" r="3.5"/>')
                out.append(f'<text class="k" x="{left + pw + 12}" y="{y + 4:.1f}">{_d(s["mean"], True)}</text>')
        out.append(f'<line class="ax" x1="{left}" y1="{y0 + ph + 8}" x2="{left + pw}" y2="{y0 + ph + 8}"/>')
        step = _nice_step(hi - lo)
        x = math.ceil(lo / step) * step
        while x <= hi + 1e-9:
            lab = "0" if abs(x) < 1e-9 else f"{x:+,.0f}".replace("-", "−")
            out.append(f'<text class="k" x="{X(x):.1f}" y="{y0 + ph + 24}" text-anchor="middle">{lab}</text>')
            x += step
        out.append(f'<text class="k" x="{left + pw / 2}" y="{y0 + ph + 42}" text-anchor="middle">'
                   f'gain, $ per owner over 30 days</text>')
        y0 += ph + 60 + 40
    out.append("</svg>")
    return "\n".join(out) + "\n"


def _nice_step(span):
    raw = span / 6
    e = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for m in (1, 2, 2.5, 5, 10):
        if m * e >= raw:
            return m * e
    return 10 * e


def plot_rating_svg(res: dict, seeds_txt: str, version=ENGINE_VERSION) -> str:
    """Brand rating by day for each licensing option (cheap, detect_scale 1, owner not liable) and contract
    (6 licensees from day 10), never as the reference; one panel per verification level."""
    W, H, top, ph, pw = 960, 620, 120, 330, 290
    lefts = [110, 560]
    Y = lambda r: top + ph - r * ph
    out = _frame("How fast the brand's rating falls after licensing",
                 "Mean brand rating by day over the sampled owners; cheap licensees, detect_scale 1, owner not liable",
                 [NOTE.format(v=version, s=seeds_txt),
                  "Rating = memory-weighted share of rated units whose true quality met the claim (memory 0.7); "
                  "unrated drawn at 0.5.",
                  "Grey: never licensing. Dashed: contract licensees (6 from day 10). N×b = N licensees from day b."],
                 W=W, H=H, desc="Brand rating by day, by licensing option and verification level.")
    styles = {"2x10": "ln", "6x10": "hl2", "2x20": "ln", "6x20": "hl2"}
    for k, t in enumerate(VER):
        left = lefts[k]
        X = lambda d, left=left: left + (d - 1) / (DAYS - 1) * pw
        c = f"cheap|{t}|ds1.0|free"
        con = f"contract|{t}|ds1.0|free"
        out.append(f'<text class="lb" x="{left}" y="{top - 12}">{VLAB[t]}</text>')
        tr = res["rating"][c]
        lines = [(NEVER, tr[NEVER], "never", "nev")] + [(o, tr[o], o.replace("x", "×"), styles[o]) for o in tr if o != NEVER]
        if con in res["rating"]:
            lines.append(("contract", res["rating"][con]["6x10"], "contract", "dash"))
        ends = []
        for o, ys, lab, cls in lines:
            pts = " ".join(f"{X(d + 1):.1f},{Y(y):.1f}" for d, y in enumerate(ys))
            out.append(f'<polyline class="{cls}" fill="none" points="{pts}"/>')
            ends.append([Y(ys[-1]), lab])
        ends.sort()
        for i in range(1, len(ends)):
            ends[i][0] = max(ends[i][0], ends[i - 1][0] + 13)
        for y, lab in ends:
            out.append(f'<text class="k" x="{X(DAYS) + 8:.1f}" y="{y + 4:.1f}">{lab}</text>')
        out.append(f'<line class="ax" x1="{X(1):.1f}" y1="{top + ph + 10}" x2="{X(DAYS):.1f}" y2="{top + ph + 10}"/>')
        for d in (1, 10, 20, 30):
            out.append(f'<text class="k" x="{X(d):.1f}" y="{top + ph + 26}" text-anchor="middle">{d}</text>')
        out.append(f'<text class="k" x="{left + pw / 2}" y="{top + ph + 44}" text-anchor="middle">day</text>')
        out.append(f'<line class="ax" x1="{left - 12}" y1="{Y(0):.1f}" x2="{left - 12}" y2="{Y(1):.1f}"/>')
        for r in (0, 0.5, 1):
            out.append(f'<text class="k" x="{left - 18}" y="{Y(r) + 4:.1f}" text-anchor="end">{r:g}</text>')
    out.append("</svg>")
    s = "\n".join(out) + "\n"
    return s.replace("</style>", " .hl2{stroke:#e15759;stroke-width:1.6} .nev{stroke:#bbb;stroke-width:1.2} "
                                 ".dash{stroke:#666;stroke-width:1.2;stroke-dasharray:4 3} "
                                 "@media (prefers-color-scheme: dark){.hl2{stroke:#fc8d62} .nev{stroke:#555} "
                                 ".dash{stroke:#aaa}}</style>", 1)


# ------------------------------------------------------------------ report

def report(res: dict, meta: dict, svgs: list, old: str | None) -> str:
    L = ["# Licensing: harvesting brand equity through licensees", "",
         "Spec \"Part 2: licensing\" (2026-11-11); predictions written 2026-11-11, before any run. Pilot gate: "
         "`runs/pilot_licensing.md`.", "",
         "## Design (prespecified)", "",
         "- Engine 0.16.0. Market as the liability run: choice-set demand (m 3, gamma 0), 150 buyers, budget 1.25 × "
         "base, bargain hunters 0.2 (Q_req 0.15–0.40); D = 30 known; ratings public (memory 0.7); brands on (premium "
         "0.4, placeholder); naive deceptive sellers, fresh reopening; 2 patrolling inspectors, not uniformed; "
         "collectible fines; every genuine stall honest, the owner under test included.",
         "- Licensing (decided 2026-11-11): from the start of day b the owner's brand is borne by N non-genuine stalls "
         "of its category (dedicated stream); they post its price, claim its quality, never rename, and pay a royalty "
         "of 0.15 × price per unit (placeholder). Cheap licensees: true quality drawn from the low range, deceptive "
         "policy; contract licensees: the owner's quality, honest policy. Reviews of licensee sales go to the brand. "
         "Owner liable: fines from catches at licensees are charged to the owner.",
         "- Conditions: cheap licensees × verification {tourist share 0.4 with locals inspecting; 1.0} × detect_scale "
         "{0, 1} × owner liable {no, yes}; contract licensees × verification, detect_scale 1, owner not liable.",
         "- Benchmark: per seed 3 genuine owners from `default_rng([seed, 17])`; one never chain per seed, verification "
         "level and detect_scale. Options: N ∈ {2, 6} from day b ∈ {10, 20}. Gain = owner's 30-day profit (own sales + "
         "royalties − fines charged to it) at its best option minus never (**unfloored, primary**); floored also "
         "reported. Bust-out gain in the same markets: candidates day 20, 25, 28, 29, 30.",
         "- Paired by seed; 95% t-intervals, unadjusted. Confirmatory: PX1–PX3. Everything else exploratory.", ""]
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
          "- Sampled owners per seed: " + "; ".join(f"{sd}: {', '.join(meta['samples'][str(sd)])}" for sd in res["seeds"]),
          ""]
    L += ["## Owner's gain by condition", "",
          *_t(["Condition", "Unfloored gain ($)", "Floored gain ($)", "Owners with a positive gain", "Never total ($)",
               "Best option (counts)"],
              [[_cl(c), _ci(v["unfloored"], _d), _ci(v["floored"], _d), f"{100 * v['share_positive']:.0f}%",
                _ci(v["never_total"], _d, signed=False),
                ", ".join(f"{k.replace('x', '×')}: {n}" for k, n in v["best"].items())]
               for c, v in res["lic"].items()]),
          "", "Bust-out in the same markets (no licence):", "",
          *_t(["Verification, detect_scale", "Unfloored gain ($)", "Floored gain ($)", "Owners with a positive gain",
               "Best candidate (counts)"],
              [[f"{VLAB[bk.split('|')[0]]}, {float(bk.split('|')[1][2:]):g}", _ci(v["unfloored"], _d),
                _ci(v["floored"], _d), f"{100 * v['share_positive']:.0f}%",
                ", ".join(f"{k.lstrip('b')}: {n}" for k, n in v["best"].items())] for bk, v in res["bust"].items()]), ""]
    P, PF = res["pred"]["gain_unfloored"], res["pred"]["gain_floored"]
    L += ["## Predictions", "",
          "Gain in $ per sampled owner over 30 days (per-seed mean of 3 owners). PX1–PX3 are confirmatory; every row "
          "marked exploratory is not.", "",
          *_t(["Prediction", "Unfloored gain (primary)", "Verdict", "Floored gain", "Verdict"],
              [[f"**{k}**: {v['label']}", _ci(v, _d), v["verdict"], _ci(PF[k], _d), PF[k]["verdict"]]
               for k, v in P.items()]), ""]
    L += ["## Brand rating by day (exploratory)", "",
          "Mean brand rating over the sampled owners (unrated = 0.5), at days 1, 10, 15, 20, 25 and 30.", ""]
    rows = []
    for c, tr in res["rating"].items():
        for o, ys in tr.items():
            rows.append([_cl(c), o.replace("x", "×"), *[f"{ys[d - 1]:.3f}" for d in (1, 10, 15, 20, 25, 30)]])
    L += [*_t(["Condition", "Option", "Day 1", "10", "15", "20", "25", "30"], rows), ""]
    L += ["## Licence accounting by option (exploratory)", "",
          "Per seed the mean over the 3 owners, from the licence day to 30. Owner units: the owner's own sales minus "
          "never's over the same days. Fines by payer: fines from catches at licensees.", ""]
    rows = []
    for c, acc in res["licence"].items():
        for o, a in acc.items():
            rows.append([_cl(c), o.replace("x", "×"), _ci(a["royalties"], _d, signed=False),
                         _ci(a["licensee_units"], _num(1), signed=False), _ci(a["owner_units_minus_never"], _num(1)),
                         _ci(a["catches_at_licensees"], _num(1), signed=False), _ci(a["fines_to_owner"], _d, signed=False),
                         _ci(a["fines_to_licensees"], _d, signed=False), _ci(a["licensee_q"], _num(3), signed=False)])
    L += [*_t(["Condition", "Option", "Royalties ($)", "Licensee units", "Owner units − never", "Catches at licensees",
               "Fines to owner ($)", "Fines to licensees ($)", "Licensee mean quality"], rows), ""]
    L += ["## Harm by buyer profile at the best option (exploratory)", "",
          "Licensing chain at the owner's best option minus the never chain, licence day to 30; per seed the mean over "
          "the 3 owners. Shortfall in points of purchases; surplus in $ per buyer of the profile.", "",
          *_t(["Condition", *[f"{p}: shortfall (pts)" for p in PROFILES], *[f"{p}: surplus ($)" for p in PROFILES]],
              [[_cl(c), *[_ci(h[p]["short"], lambda x, s: _num(1)(100 * x, s)) for p in PROFILES],
                *[_ci(h[p]["surplus"], _d) for p in PROFILES]] for c, h in res["harm"].items()]), ""]
    L += ["## Stuck and parked buyers", "",
          "Every chain: the engine's end-of-day guard (stuck_buyers, idle_choosers) and the parked-buyer observer.", "",
          *_t(["Chains", "Count", "Buyer-days", "Stuck", "Parked", "Idle choosers"],
              [[g.replace("|", " · "), str(v["chains"]), f"{v['buyer_days']:,}", str(v["stuck_buyers"]), str(v["parked"]),
                str(v["idle_choosers"])] for g, v in res["guard"].items()]), ""]
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
    ap.add_argument("--timing", help="run one licensing condition at full size (pilot G3) and print the wall clock")
    ap.add_argument("--seeds", default="250-269")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--outdir", default="runs")
    ap.add_argument("--tests", default="")
    ap.add_argument("--min-swap-mb", type=float, default=512)
    ap.add_argument("--min-free-pct", type=float, default=15)
    ap.add_argument("--drop-b10", action="store_true", help="trimmed option: licensing options from day 20 only")
    ap.add_argument("--pipeline-check", action="store_true",
                    help="pilot seeds 915-919 only, into an --outdir other than runs; outputs are discarded")
    a = ap.parse_args(argv)
    global LIC_OPTS
    if a.drop_b10:
        LIC_OPTS = [o for o in LIC_OPTS if o[1] != 10]
    seeds = parse_seeds(a.seeds)
    LB._lower_priority()
    os.makedirs(a.outdir, exist_ok=True)
    if a.timing:
        if not set(seeds) <= PILOT_SEEDS or a.timing not in LIC_CONDS:
            raise SystemExit("timing runs use pilot seeds 915-919 and one of LIC_CONDS")
        t0 = time.time()
        samples = {sd: sample_stalls(sd) for sd in seeds}
        q, t, ds, lia = parts(a.timing)
        js = [j for j in jobs_for([a.timing], [(t, ds)], seeds, samples) if j[0] != "bust"]
        runs, pauses = run_chains(a, js, None, print)
        wall = time.time() - t0
        print(json.dumps({"cond": a.timing, "seeds": seeds, "chains": len(runs), "wall_s": wall,
                          "per_chain_s": wall / len(runs), "pauses": pauses, "load": _load(), "memory": memory_state(),
                          "guard": {k: sum(r["guard"][k] for r in runs) for k in ("stuck_buyers", "parked", "idle_choosers")},
                          "fallbacks": sum(r["fallbacks"] for r in runs)}))
        return 0
    if a.pipeline_check:
        if not set(seeds) <= PILOT_SEEDS or os.path.abspath(a.outdir) == os.path.abspath("runs"):
            raise SystemExit("--pipeline-check uses pilot seeds 915-919 and an outdir other than runs")
    elif not set(seeds) <= MAIN_SEEDS:
        raise SystemExit("the main run uses seeds 250-269 only")
    logp = os.path.join(a.outdir, "licensing_run.log")
    logf = open(logp, "a", encoding="utf-8")

    def log(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        logf.write(line + "\n"); logf.flush()

    t0 = time.time()
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
            "command": " ".join(["python -m analysis.licensing", *sys.argv[1:]]), "tests": a.tests,
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
            "workers": a.workers, "load_start": _load(), "mem_start": memory_state(), "seeds_txt": a.seeds,
            "licence_options": [ok(o) for o in LIC_OPTS]}
    log(f"licensing: engine {ENGINE_VERSION}, commit {meta['git']['commit'][:7]}, seeds {a.seeds}, "
        f"options {meta['licence_options']}")
    samples = {sd: sample_stalls(sd) for sd in seeds}
    meta["samples"] = {str(k): v for k, v in samples.items()}
    jobs = jobs_for(LIC_CONDS, BASES, seeds, samples)
    runs, pauses = run_chains(a, jobs, os.path.join(a.outdir, "licensing_cache.jsonl"), log)
    res = analyse(runs, seeds, samples)
    meta.update(chains=len(runs), pauses=pauses, wall_h=(time.time() - t0) / 3600, load_end=_load(),
                mem_end=memory_state())
    GL, GB = gains(runs, seeds, samples)
    with open(os.path.join(a.outdir, "licensing.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        lo, bo = [ok(o) for o in LIC_OPTS], [ok(b) for b in BUST_CANDS]
        w.writerow(["kind", "quality", "verification", "detect_scale", "owner_liable", "seed", "stall",
                    "gain_unfloored_cents", "gain_floored_cents", "best", "never_total_cents",
                    *[f"total_{c}_cents" for c in lo + bo]])
        for c, G in GL.items():
            q, t, ds, lia = parts(c)
            for sd in seeds:
                for s, g in G[sd].items():
                    w.writerow(["licence", q, t, f"{ds:g}", int(lia), sd, s, g["gain_unfloored"], g["gain_floored"],
                                g["best"], g["never"], *[g["totals"].get(k, "") for k in lo + bo]])
        for bk, G in GB.items():
            t, d = bk.split("|")
            for sd in seeds:
                for s, g in G[sd].items():
                    w.writerow(["bust", "", t, f"{float(d[2:]):g}", "", sd, s, g["gain_unfloored"], g["gain_floored"],
                                g["best"], g["never"], *[g["totals"].get(k, "") for k in lo + bo]])
    with gzip.open(os.path.join(a.outdir, "licensing.json.gz"), "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": res, "runs": runs}, f, separators=(",", ":"))
    del runs, GL, GB
    svgs = []
    for name, fn, alt in (("licensing_gain.svg", plot_gain_svg, "owner's gain from licensing against busting out"),
                          ("licensing_rating.svg", plot_rating_svg, "brand rating by day after licensing")):
        with open(os.path.join(a.outdir, name), "w", encoding="utf-8") as f:
            f.write(fn(res, a.seeds))
        svgs.append((name, alt))
    sp = os.path.join(a.outdir, "licensing_summary.md")
    old = open(sp, encoding="utf-8").read() if os.path.exists(sp) else None
    with open(sp, "w", encoding="utf-8") as f:
        f.write(report(res, meta, svgs, old))
    log(f"done; {len(res['flags'])} flags; wall {meta['wall_h']:.2f} h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
