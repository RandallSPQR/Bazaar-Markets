"""Where does the brand dilemma appear? (rule-based only; no engine change)

Prespecified design (spec and predictions written 2026-11-07, before any run). Engine 0.10.0.
  As the always-honest / v2 cells of the 2026-11-06 search-depth run (analysis/search_counterfeit.py):
  ratings public; fresh reopening; naive deceptive sellers; D = 30 known to sellers; budget factor
  1.25; tourist share 0.4; search depth 2 for all profiles; 150 buyers; brands on, premium 0.4;
  inspectors patrolling, not uniformed.
  Grid: original policy {rule_genuine (= rule_honest), rule_genuine_rational_v2}
        x inspector count {0, 1, 2, 4, 6} = 10 conditions; seeds 32-51 (20), paired.

    .venv/bin/python -m analysis.dilemma_boundary --tests "<result>" --out runs/dilemma_boundary.json

Late = days 26-30. Paired by seed; 95% t-intervals, unadjusted.
  PG1 (confirmatory): at 0 inspectors, late genuine profit per stall, v2 - always-honest > 0.
  PG2 (confirmatory): per-seed OLS slope of (v2 - honest) over the five counts < 0 (per inspector).
  Descriptive: crossover count = where the mean v2 - honest curve first goes from > 0 to <= 0,
    linearly interpolated between adjacent counts; "below 0" when it is already <= 0 at 0 inspectors,
    "above 6" when it stays > 0. 95% CI from a paired bootstrap over seeds (10,000 resamples,
    numpy default_rng(20261107)), percentiles by inverted CDF, with "below"/"above" kept as -inf/+inf.
    Bust-out day distributions and shares by count (v2); buyer shortfall by condition.
  Floors: analysis/floors.py (task completion, purchases, sales by seller type) plus invalid actions.

Seeds already used elsewhere are refused: 0-31, 100-104, 200-201; 300-301 are reserved for this
script's pipeline check (--pipeline-check), whose outputs are not kept.

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
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from analysis.counterfeit import DAYS, LATE, SHARES, STYLE, _ci, _d, _git, _load, _num, _pct, _t, _verdict, mean_ci, paired_diff
from analysis.floors import floor_flags, floor_series
from cli.sweep import parse_seeds
from engine import ENGINE_VERSION, bazaar
from engine.config import load

COUNTS = [0, 1, 2, 4, 6]
POLICIES = {"honest": "rule_honest", "v2": "rule_genuine_rational_v2"}
LABEL = {"honest": "always-honest", "v2": "rational v2"}
K = 2
BUYERS = 150
BOOT = 10_000
BOOT_SEED = 20261107
USED = set(range(0, 32)) | set(range(100, 105)) | {200, 201}
PIPELINE = {300, 301}
COMMON = ["ratings.mode=public", "inspectors.placement=patrolling", "inspectors.uniformed=false",
          "agents.seller.deceptive=rule_deceptive", "brands.enabled=true", "brands.premium=0.4",
          "market.horizon_known=true", "evolution.revise_prob=0", "evolution.mutation_prob=0",
          f"buyers.count={BUYERS}", "buyers.budget_factor_override=1.25", f"market.days={DAYS}",
          "agents.params.rule_deceptive.reopen=fresh", f"buyers.profile_shares={SHARES['t40']}",
          f'buyers.search_depth={{"tourist":{K},"local":{K},"expert":{K}}}']
SERIES = ["genuine_profit", "deceptive_profit", "shortfall_rate", "surplus", "task_complete", "catches", "busted",
          "purchases", "sales_genuine", "sales_deceptive"]
BINS = [("1–20", 1, 20), ("21–25", 21, 25), ("26", 26, 26), ("27", 27, 27), ("28", 28, 28), ("29", 29, 29),
        ("30", 30, 30), ("never", 31, 31)]


def cname(g, n) -> str:
    return f"{g}|{n}"


def overrides(g, n, seed) -> list[str]:
    return [*COMMON, f"inspectors.count={n}", f"agents.seller.genuine={POLICIES[g]}", f"seed={seed}"]


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ runs

def _job(args) -> dict:
    g, n, seed = args
    c = load(None, overrides(g, n, seed), mode="bazaar")
    out = bazaar.run(c)
    stype = out["days"][0]["stall_types"]
    gen = [sid for sid, ty in stype.items() if ty == "genuine"]
    bust = {sid: None for sid in gen}
    days = []
    for dd in out["days"]:
        o = dd["outcome"]
        pt = o["seller_by_type"]
        for b in dd["bust_outs"]:
            bust[b["stall"]] = b["day"]
        days.append({"genuine_profit": pt["genuine"]["profit_per_stall_cents"] if "genuine" in pt else None,
                     "deceptive_profit": pt["deceptive"]["profit_per_stall_cents"] if "deceptive" in pt else None,
                     "shortfall_rate": o["shortfall_rate"], "surplus": o["buyer_surplus_mean_cents"],
                     "catches": o["catches"], "busted": o["brands"]["busted_stalls"], **floor_series(o)})
    return {"cond": cname(g, n), "policy": g, "inspectors": n, "seed": seed, "days": days, "bust": bust,
            "n_genuine": len(gen), "fallbacks": sum(x["outcome"]["fallbacks"]["buyer"] for x in out["days"])}


# ------------------------------------------------------------------ analysis

def _late_vals(runs, m) -> np.ndarray:
    a = np.array([[np.nan if x[m] is None else x[m] for x in r["days"]] for r in runs], float)
    with np.errstate(all="ignore"):
        return np.nanmean(a[:, [d - 1 for d in LATE]], 1)


def _lst(a):
    return [None if (x is None or np.isnan(x)) else float(x) for x in a]


def crossing(xs, ys) -> float:
    """First count where the curve goes from > 0 to <= 0, linearly interpolated.
    -inf: already <= 0 at the first count. +inf: > 0 at every count."""
    if ys[0] <= 0:
        return float("-inf")
    for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if y1 <= 0:
            return float(x0 + y0 * (x1 - x0) / (y0 - y1))
    return float("inf")


def bootstrap_crossing(D: np.ndarray, xs, B=BOOT, seed=BOOT_SEED) -> dict:
    """D: seeds x counts matrix of per-seed v2 - honest. Paired bootstrap over seeds."""
    rng = np.random.default_rng(seed)
    n = D.shape[0]
    idx = rng.integers(0, n, size=(B, n))
    curves = D[idx].mean(1)
    c = np.array([crossing(xs, row) for row in curves])
    lo, hi = np.quantile(c, [0.025, 0.975], method="inverted_cdf")
    return {"lo": float(lo), "hi": float(hi), "B": B, "rng_seed": seed,
            "share_below": float(np.mean(c == -np.inf)), "share_above": float(np.mean(c == np.inf)),
            "median": float(np.quantile(c, 0.5, method="inverted_cdf"))}


def _slope(xs, G):
    x = np.array(xs, float)
    xc = x - x.mean()
    return (G * xc).sum(1) / (xc ** 2).sum()


def analyse(v: dict) -> dict:
    res: dict = {"late": {}}
    L = {(c, m): _late_vals(v[c], m) for c in v for m in SERIES}
    for c in v:
        for m in SERIES:
            res["late"][f"{c}|{m}"] = mean_ci(_lst(L[(c, m)]))
    D = np.stack([L[(cname("v2", n), "genuine_profit")] - L[(cname("honest", n), "genuine_profit")] for n in COUNTS], 1)
    res["diff_by_count"] = {str(n): mean_ci(_lst(D[:, i])) for i, n in enumerate(COUNTS)}
    res["contrasts"] = {f"{n}|{m}": paired_diff(_lst(L[(cname("honest", n), m)]), _lst(L[(cname("v2", n), m)]))
                        for n in COUNTS for m in SERIES}
    res["pg1"] = {**res["diff_by_count"]["0"], "verdict": _verdict(res["diff_by_count"]["0"], +1)}
    res["pg2"] = {**mean_ci(_lst(_slope(COUNTS, D))), "unit": "cents per inspector"}
    res["pg2"]["verdict"] = _verdict(res["pg2"], -1)
    if np.isnan(D).any():
        res["crossover"] = {"point": None, "note": "undefined: missing values"}
    else:
        res["crossover"] = {"point": crossing(COUNTS, D.mean(0)), **bootstrap_crossing(D, COUNTS)}
    res["bust"] = {}
    for n in COUNTS:
        runs = v[cname("v2", n)]
        days = [31 if b is None else b for r in runs for b in r["bust"].values()]
        res["bust"][str(n)] = {
            "share": mean_ci([float(np.mean([b is not None for b in r["bust"].values()])) for r in runs]),
            "mean_day": mean_ci([float(np.mean([31 if b is None else b for b in r["bust"].values()])) for r in runs]),
            "median_pooled": float(np.median(days)), "n_stalls": len(days),
            "bins": {lab: int(sum(lo <= d <= hi for d in days)) for lab, lo, hi in BINS}}
    flags = floor_flags(v, LATE, list(range(1, DAYS + 1)))
    for c in v:
        fb = sum(r["fallbacks"] for r in v[c])
        if fb:
            flags.append(f"{c}: {fb} invalid buyer actions (fallbacks)")
    res["flags"] = flags
    return res


# ------------------------------------------------------------------ plot

def _fmt_x(x) -> str:
    if x == float("-inf"):
        return "below 0"
    if x == float("inf"):
        return "above 6"
    return f"{x:.2f}"


def plot_svg(res, n, version=ENGINE_VERSION) -> str:
    """v2 − always-honest late genuine profit per stall against inspector count, paired 95%
    intervals, zero line, crossover with its bootstrap interval on the zero line."""
    W, H = 900, 600
    left, top, pw, ph = 110, 120, 680, 360
    st = [res["diff_by_count"][str(c)] for c in COUNTS]
    lo = min(min(s["lo"] for s in st), 0) / 100
    hi = max(max(s["hi"] for s in st), 0) / 100
    pad = (hi - lo) * 0.1
    lo, hi = lo - pad, hi + pad

    def X(x):
        return left + (x - COUNTS[0]) / (COUNTS[-1] - COUNTS[0]) * pw

    def Y(y):
        return top + ph - (y - lo) / (hi - lo) * ph
    cx = res["crossover"]
    title = "Penalty-aware bust-out (v2) minus always-honest, by number of inspectors"
    sub = (f"Late days 26–30, genuine profit, $ per stall per day; slope {_ci(res['pg2'], _d)} per inspector; "
           f"crossover {_fmt_x(cx['point'])} [{_fmt_x(cx['lo'])}, {_fmt_x(cx['hi'])}]")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" aria-labelledby="t d">',
           STYLE, f'<rect class="bg" x="0" y="0" width="{W}" height="{H}"/>', f'<title id="t">{title}</title>',
           f'<desc id="d">Mean paired difference with 95% intervals at 0, 1, 2, 4 and 6 patrolling inspectors. '
           f'Crossover count {_fmt_x(cx["point"])}, bootstrap interval {_fmt_x(cx["lo"])} to {_fmt_x(cx["hi"])}. '
           f'The summary gives every value.</desc>',
           f'<text class="t" x="30" y="44" font-size="20">{title}</text>',
           f'<text class="s" x="30" y="70" font-size="14">{sub}</text>',
           f'<line class="zero" x1="{X(0):.1f}" y1="{Y(0):.1f}" x2="{X(6):.1f}" y2="{Y(0):.1f}"/>']
    # crossover interval on the zero line
    if cx.get("point") is not None:
        a = max(cx["lo"], COUNTS[0])
        b = min(cx["hi"], COUNTS[-1])
        if a <= b:
            out.append(f'<line class="hlc" x1="{X(a):.1f}" y1="{Y(0):.1f}" x2="{X(b):.1f}" y2="{Y(0):.1f}" stroke-width="3"/>')
        if np.isfinite(cx["point"]):
            out.append(f'<circle class="hl" cx="{X(cx["point"]):.1f}" cy="{Y(0):.1f}" r="4"/>')
            out.append(f'<text class="an" x="{X(cx["point"]):.1f}" y="{Y(0) + 22:.1f}" text-anchor="middle">'
                       f'crossover {cx["point"]:.2f} inspectors</text>')
        else:
            out.append(f'<text class="an" x="{X(6):.1f}" y="{top - 8}" text-anchor="end">'
                       f'no crossover in 0–6 ({_fmt_x(cx["point"])})</text>')
    pts = " ".join(f"{X(c):.1f},{Y(s['mean'] / 100):.1f}" for c, s in zip(COUNTS, st))
    out.append(f'<polyline class="ln" points="{pts}"/>')
    for c, s in zip(COUNTS, st):
        out.append(f'<line class="ci" x1="{X(c):.1f}" y1="{Y(s["lo"] / 100):.1f}" x2="{X(c):.1f}" y2="{Y(s["hi"] / 100):.1f}"/>')
        out.append(f'<circle class="pt" cx="{X(c):.1f}" cy="{Y(s["mean"] / 100):.1f}" r="3.5"/>')
        dy = -10 if s["mean"] >= 0 else 18
        out.append(f'<text class="lb" x="{X(c) + 8:.1f}" y="{Y(s["mean"] / 100) + dy:.1f}">{_d(s["mean"], True)}</text>')
    out.append(f'<line class="ax" x1="{left - 14}" y1="{Y(lo):.1f}" x2="{left - 14}" y2="{Y(hi):.1f}"/>')
    step = _nice((hi - lo) / 5)
    y = np.ceil(lo / step) * step
    while y <= hi + 1e-9:
        lab = "0" if abs(y) < 1e-9 else f"{y:+,.0f}".replace("-", "−")
        out.append(f'<text class="k" x="{left - 20}" y="{Y(y) + 4:.1f}" text-anchor="end">{lab}</text>')
        y += step
    out.append(f'<line class="ax" x1="{X(0):.1f}" y1="{top + ph + 14}" x2="{X(6):.1f}" y2="{top + ph + 14}"/>')
    for c in COUNTS:
        out.append(f'<text class="k" x="{X(c):.1f}" y="{top + ph + 30}" text-anchor="middle">{c}</text>')
    out.append(f'<text class="k" x="{left + pw / 2}" y="{top + ph + 50}" text-anchor="middle">patrolling inspectors '
               f'(not uniformed)</text>')
    out.append(f'<text class="k" x="{left - 70}" y="{top + ph / 2}" text-anchor="middle" '
               f'transform="rotate(-90 {left - 70} {top + ph / 2})">v2 − honest, $ per stall per day</text>')
    out.append(f'<text class="n" x="30" y="{H - 40}">Bazaar engine {version}. Paired by seed ({n} seeds), 95% t-intervals, '
               f'unadjusted; crossover interval: paired bootstrap, {BOOT:,} resamples. Fresh reopening,</text>')
    out.append(f'<text class="n" x="30" y="{H - 24}">naive deceptive sellers, budget 1.25 × base, tourists 40%, {BUYERS} buyers '
               f'a day, search depth {K}, 30 days, premium 0.4 (placeholder); v2 sees the catch rate.</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def _nice(x):
    e = 10 ** np.floor(np.log10(x))
    for m in (1, 2, 2.5, 5, 10):
        if m * e >= x:
            return m * e
    return 10 * e


# ------------------------------------------------------------------ report

def report(meta, res, svg) -> str:
    lt, ct, cx, bt = res["late"], res["contrasts"], res["crossover"], res["bust"]
    p1, p2 = res["pg1"], res["pg2"]
    L = ["# Where does the brand dilemma appear?", "",
         "Run spec \"where does the brand dilemma appear? (no engine change; rule-based)\"; predictions written "
         "2026-11-07, before any run.", "", "## Run record", "",
         f"- Engine `{meta['engine_version']}`; commit `{meta['git']['commit']}`; uncommitted at run time: "
         f"{meta['git']['status_porcelain'] or 'none'}",
         f"- Script sha256 `{meta['script_sha256']}`", f"- Command: `{meta['command']}`",
         f"- Tests: {meta.get('tests') or 'not recorded'}",
         f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
         f"- {meta['n_chains']} chains × {DAYS} days on {meta['workers']} workers; wall clock "
         f"{meta['wall_clock_s'] / 60:.1f} min; load average {meta['load_at_start']} at start, {meta['load_at_end']} at end",
         f"- Seeds {meta['seeds'][0]}–{meta['seeds'][-1]} ({len(meta['seeds'])}), paired", "",
         "## Design (prespecified)", "",
         f"- As the always-honest and v2 cells of the 2026-11-06 search-depth run: ratings public; fresh reopening; "
         f"naive deceptive sellers; D = 30 known to sellers; budget 1.25 × base; tourists 40% (0.4 / 0.3 / 0.3); "
         f"search depth {K} for all profiles; {BUYERS} buyers; brands on, premium 0.4 (placeholder); inspectors "
         f"patrolling, not uniformed.",
         f"- Grid: original policy {{always-honest, rational v2}} × inspector count {{{', '.join(map(str, COUNTS))}}}.",
         "- Late = days 26–30. Paired by seed; 95% t-intervals, unadjusted. Confirmatory: PG1, PG2. Crossover, "
         "bust-out distributions and shortfall are descriptive.",
         f"- Crossover: where the mean v2 − honest curve first goes from > 0 to ≤ 0, interpolated linearly between "
         f"adjacent counts. 95% interval from a paired bootstrap over seeds ({BOOT:,} resamples, numpy "
         f"default_rng({BOOT_SEED}), inverted-CDF percentiles; a resample with no crossing counts as below 0 or "
         f"above 6).", "",
         "## Confirmatory", "",
         f"- **PG1**: at 0 inspectors, late genuine profit per stall, v2 − always-honest: ${_ci(p1, _d)} per day. "
         f"Prediction > 0. **Verdict: {p1['verdict']}.**",
         f"- **PG2**: per-seed slope of v2 − always-honest over 0, 1, 2, 4, 6 inspectors: ${_ci(p2, _d)} per "
         f"inspector. Prediction < 0. **Verdict: {p2['verdict']}.**", "",
         "## v2 − always-honest by inspector count", ""]
    L += _t(["Inspectors", "Genuine profit ($)", "Deceptive profit ($)", "Shortfall (pts)", "Surplus ($)",
             "Catches/day"],
            [[str(n), _ci(ct[f"{n}|genuine_profit"], _d), _ci(ct[f"{n}|deceptive_profit"], _d),
              _ci(ct[f"{n}|shortfall_rate"], _pct), _ci(ct[f"{n}|surplus"], _d), _ci(ct[f"{n}|catches"], _num(1))]
             for n in COUNTS])
    L += ["", f"**Crossover** (descriptive): {_fmt_x(cx['point'])} inspectors; 95% bootstrap interval "
          f"[{_fmt_x(cx['lo'])}, {_fmt_x(cx['hi'])}]; bootstrap median {_fmt_x(cx['median'])}. Share of resamples "
          f"with no crossing: below 0 {100 * cx['share_below']:.1f}%, above 6 {100 * cx['share_above']:.1f}%.",
          "", f"![v2 − always-honest by inspector count]({svg})", "",
          "## Bust-outs under v2 by inspector count", ""]
    L += _t(["Inspectors", "Share busting out (%)", "Mean bust-out day (never = 31)", "Median (pooled)"]
            + [f"Day {lab}" if lab != "never" else "Never" for lab, _, _ in BINS],
            [[str(n), _ci(bt[str(n)]["share"], _pct, False), _ci(bt[str(n)]["mean_day"], _num(2), False),
              f"{bt[str(n)]['median_pooled']:g}"] + [str(bt[str(n)]["bins"][lab]) for lab, _, _ in BINS]
             for n in COUNTS])
    L += ["", f"Day columns count genuine stalls pooled over seeds ({bt['0']['n_stalls']} per count).", "",
          "## Late levels (days 26–30)", ""]

    def g_(c, m, f):
        return _ci(lt[f"{c}|{m}"], f, False)
    L += _t(["Policy", "Inspectors", "Genuine profit ($)", "Deceptive profit ($)", "Shortfall (%)", "Surplus ($)",
             "Task complete (%)", "Catches/day", "Busted stalls"],
            [[LABEL[g], str(n), g_(cname(g, n), "genuine_profit", _d), g_(cname(g, n), "deceptive_profit", _d),
              g_(cname(g, n), "shortfall_rate", _pct), g_(cname(g, n), "surplus", _d),
              g_(cname(g, n), "task_complete", _pct), g_(cname(g, n), "catches", _num(1)),
              g_(cname(g, n), "busted", _num(1))] for g in POLICIES for n in COUNTS])
    L += ["", "## Floors and invalid actions", ""] + ([f"- {x}" for x in res["flags"]] or ["- none"])
    L += ["", "## Reading (written after the results)", "", "READING_PLACEHOLDER", "", "## Caveats", "",
          "CAVEATS_PLACEHOLDER", ""]
    return "\n".join(L)


# ------------------------------------------------------------------ main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="32-51")
    ap.add_argument("--out", default="runs/dilemma_boundary.json")
    ap.add_argument("--tests", default=None)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--pipeline-check", action="store_true")
    a = ap.parse_args(argv)
    seeds = parse_seeds(a.seeds)
    if a.pipeline_check:
        if not set(seeds) <= PIPELINE or os.path.abspath(a.out).startswith(os.path.abspath("runs")):
            raise SystemExit("pipeline check: seeds must be within 300-301 and --out outside runs/")
    elif set(seeds) & (USED | PIPELINE):
        raise SystemExit("seeds overlap seeds used by earlier runs or the pipeline check")
    base = a.out[:-5] if a.out.endswith(".json") else a.out
    conds = [(g, n) for g in POLICIES for n in COUNTS]
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
            "command": " ".join([".venv/bin/python -m analysis.dilemma_boundary", *(argv or sys.argv[1:])]),
            "tests": a.tests, "load_at_start": _load(), "python": platform.python_version(), "numpy": np.__version__,
            "platform": platform.platform(), "workers": a.workers, "seeds": seeds, "days": DAYS,
            "conditions": [cname(*c) for c in conds], "common_overrides": COMMON}
    jobs = [(*c, sd) for sd in seeds for c in conds]
    t0 = time.time()
    runs = []
    with ProcessPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(_job, jobs)):
            runs.append(r)
            if (i + 1) % len(conds) == 0:
                print(f"{i + 1}/{len(jobs)} chains, {time.time() - t0:.0f} s, load {_load()}", flush=True)
    meta.update(wall_clock_s=time.time() - t0, load_at_end=_load(), n_chains=len(runs))
    pos = {s: i for i, s in enumerate(seeds)}
    v = {cname(*c): [None] * len(seeds) for c in conds}
    for r in runs:
        v[r["cond"]][pos[r["seed"]]] = r
    res = analyse(v)
    with gzip.open(base + ".json.gz", "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": res, "runs": runs}, f, sort_keys=True, separators=(",", ":"))
    with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["policy", "inspectors", "seed", "day"] + SERIES)
        for r in runs:
            for dd, x in enumerate(r["days"], start=1):
                w.writerow([r["policy"], r["inspectors"], r["seed"], dd] + [x[m] for m in SERIES])
    svg = base + "_v2_minus_honest.svg"
    with open(svg, "w", encoding="utf-8") as f:
        f.write(plot_svg(res, len(seeds)))
    with open(base + "_summary.md", "w", encoding="utf-8") as f:
        f.write(report(meta, res, os.path.basename(svg)))
    print(f"done; flags: {res['flags'] or 'none'}; wrote {base}.json.gz, {base}.csv, {svg}, {base}_summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
