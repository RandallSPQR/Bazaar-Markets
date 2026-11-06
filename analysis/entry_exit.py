"""Part C: multi-day entry and exit.

Prespecified design (2026-11-05; see runs/entry_exit_summary.md). Rule-based only.
  seller policy for deceptive stalls in {naive (rule_deceptive), adaptive (rule_deceptive_adaptive)}
  x inspector placement in {posts, patrolling, disguised full-shift} at count 2, plus a no-inspector
  control per policy (8 conditions); uniformed = true, recognition range r = 0, so adaptive sellers
  react to catch notices (and their own reopening) only; market.days = 30; seeds 0-29, paired.
  Between days, genuine and deceptive stalls switch type by pairwise proportional imitation
  (revise 0.2, mutation 0.02, per-category normaliser, genuine/deceptive partners; engine/days.py).

    .venv/bin/python -m analysis.entry_exit --out runs/entry_exit.json

Gate: day-1 outcomes equal the single-day engine for the same conditions (every seed, full
outcome, byte for byte). If it fails, only the gate is reported.

Outcomes per day: deceptive share of stalls (deceptive / 48), shortfall rate, catches, profit per
stall by type, switches. "Late" = mean over days 26-30.
  PC1 (confirmatory): at posts, late deceptive share, adaptive - naive > 0 (paired CI excludes 0).
  PC2 (confirmatory): at posts, G_d = shortfall(adaptive) - shortfall(naive) on day d;
      late G - G_1 > 0 (paired CI of the per-seed change excludes 0).
  PC3 (exploratory): the PC1 and PC2 contrasts at patrolling, disguised and control; which
      placement holds the late deceptive share lowest (per policy), with paired differences.
  Stability flag: per seed, OLS slope of the outcome on day over days 21-30, times 9 (the fitted
  change from day 21 to day 30); flagged when its 95% t-interval excludes 0.
Intervals: 95% paired t over seeds, unadjusted. Confirmatory family: PC1, PC2.

This script only reads engine outputs; it changes nothing in the engine.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from cli.sweep import parse_seeds
from engine import ENGINE_VERSION, bazaar
from engine.config import load
from engine.jsonlog import dumps
from engine.metrics import mean_ci, paired_diff

DAYS = 30
LATE = list(range(26, 31))
STAB = list(range(21, 31))
POLICIES = {"rd": "rule_deceptive", "ad": "rule_deceptive_adaptive"}
PLACEMENTS = ["control", "posts", "patrolling", "disguised"]
PL_LABEL = {"control": "no inspectors", "posts": "posts", "patrolling": "patrolling",
            "disguised": "disguised (full shift)"}
SERIES = ["deceptive_share", "shortfall_rate", "catches", "profit_genuine", "profit_deceptive", "switches"]


def _overrides(pk: str, pl: str, seed: int, days: int = DAYS) -> list[str]:
    ov = [f"agents.seller.deceptive={POLICIES[pk]}", f"seed={seed}", f"market.days={days}"]
    if pl == "control":
        ov += ["inspectors.count=0"]
    else:
        ov += ["inspectors.count=2", f"inspectors.placement={pl}", "inspectors.uniformed=true",
               "inspectors.recognition_range=0"]
        if pl == "disguised":
            ov += ["inspectors.disguised_shift=full_shift"]
    return ov


def _series(day: dict) -> dict:
    o, t = day["outcome"], day["types"]
    pt = o["seller_by_type"]
    return {"deceptive_share": t["deceptive"] / sum(t.values()), "shortfall_rate": o["shortfall_rate"],
            "catches": o["catches"],
            "profit_genuine": pt["genuine"]["profit_per_stall_cents"] if "genuine" in pt else None,
            "profit_deceptive": pt["deceptive"]["profit_per_stall_cents"] if "deceptive" in pt else None,
            "switches": len(day["switches"]), "n_deceptive": t["deceptive"], "n_genuine": t["genuine"]}


def _job(args) -> dict:
    pk, pl, seed = args
    out = bazaar.run(load(None, _overrides(pk, pl, seed), mode="bazaar"))
    single = bazaar.run(load(None, _overrides(pk, pl, seed, days=1), mode="bazaar"))
    days = [_series(d) for d in out["days"]]
    to_dec = sum(1 for d in out["days"] for s in d["switches"] if s["to"] == "deceptive")
    to_gen = sum(1 for d in out["days"] for s in d["switches"] if s["to"] == "genuine")
    return {"policy": pk, "placement": pl, "seed": seed, "days": days,
            "day1_matches_single_day": dumps(out["days"][0]["outcome"]) == dumps(single),
            "switches_to_deceptive": to_dec, "switches_to_genuine": to_gen,
            "mutations": sum(1 for d in out["days"] for s in d["switches"] if s.get("mutated"))}


def _git() -> dict:
    def g(*a):
        return subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
    return {"commit": g("rev-parse", "HEAD"), "status_porcelain": g("status", "--porcelain").splitlines()}


def _load() -> list[float]:
    return [round(x, 2) for x in os.getloadavg()]


def _arr(v, pk, pl, m) -> np.ndarray:
    """seeds x days"""
    return np.array([[np.nan if x[m] is None else x[m] for x in r] for r in v[(pk, pl)]], float)


def _late(a: np.ndarray) -> list:
    return list(np.nanmean(a[:, [d - 1 for d in LATE]], 1))


def _stab(a: np.ndarray) -> dict:
    x = np.array(STAB, float)
    xc = x - x.mean()
    Y = a[:, [d - 1 for d in STAB]]
    ok = ~np.isnan(Y).any(1)
    slopes = (Y[ok] * xc).sum(1) / (xc ** 2).sum() * (STAB[-1] - STAB[0])
    st = mean_ci(list(slopes))
    st["flag"] = st["lo"] is not None and (st["lo"] > 0 or st["hi"] < 0)
    return st


def analyse(v: dict, seeds: list[int]) -> dict:
    res: dict = {"trajectory": {}, "late": {}, "stability": {}}
    for pk in POLICIES:
        for pl in PLACEMENTS:
            for m in SERIES:
                a = _arr(v, pk, pl, m)
                key = f"{pk}|{pl}|{m}"
                res["trajectory"][key] = [mean_ci(list(a[:, j])) for j in range(DAYS)]
                res["late"][key] = mean_ci(_late(a))
                if m in ("deceptive_share", "shortfall_rate"):
                    res["stability"][key] = _stab(a)
    contrasts = {}
    for pl in PLACEMENTS:
        ds_a, ds_n = _arr(v, "ad", pl, "deceptive_share"), _arr(v, "rd", pl, "deceptive_share")
        sf_a, sf_n = _arr(v, "ad", pl, "shortfall_rate"), _arr(v, "rd", pl, "shortfall_rate")
        G = sf_a - sf_n
        c = {"late_deceptive_share": paired_diff(_late(ds_n), _late(ds_a)),
             "day1_shortfall_gap": mean_ci(list(G[:, 0])),
             "late_shortfall_gap": mean_ci(_late(G)),
             "shortfall_gap_change": mean_ci([l - g1 for l, g1 in zip(_late(G), G[:, 0])])}
        contrasts[pl] = c
    def verdict(st):
        """Both confirmatory predictions are "> 0"."""
        if st["lo"] is None:
            return "not testable"
        if st["lo"] > 0:
            return "supported"
        return "contradicted (interval below 0)" if st["hi"] < 0 else "not supported (interval includes 0)"
    res["pc1"] = {**contrasts["posts"]["late_deceptive_share"],
                  "verdict": verdict(contrasts["posts"]["late_deceptive_share"])}
    res["pc2"] = {**contrasts["posts"]["shortfall_gap_change"],
                  "verdict": verdict(contrasts["posts"]["shortfall_gap_change"])}
    res["contrasts"] = contrasts
    # PC3: which placement holds the late deceptive share lowest, per policy
    rank = {}
    for pk in POLICIES:
        late = {pl: _late(_arr(v, pk, pl, "deceptive_share")) for pl in PLACEMENTS}
        order = sorted(PLACEMENTS, key=lambda pl: float(np.mean(late[pl])))
        best = order[0]
        rank[pk] = {"order": order, "means": {pl: float(np.mean(late[pl])) for pl in PLACEMENTS},
                    "best_minus_others": {pl: paired_diff(late[pl], late[best]) for pl in PLACEMENTS if pl != best},
                    "day30": {pl: float(np.mean(_arr(v, pk, pl, "deceptive_share")[:, -1])) for pl in PLACEMENTS}}
    res["pc3_rank"] = rank
    res["flags"] = [f"{POLICIES[k.split('|')[0]]} / {k.split('|')[1]} / {k.split('|')[2]}: change over days 21-30 "
                    f"{st['mean']:+.4f} [{st['lo']:+.4f}, {st['hi']:+.4f}]"
                    for k, st in res["stability"].items() if st["flag"]]
    return res


# ------------------------------------------------------------------ formatting

def _pct(x, signed=False):
    if x is None:
        return "–"
    return (f"{100 * x:+.1f}" if signed else f"{100 * x:.1f}").replace("-", "−")


def _cp(st, signed=True):
    if st is None or st.get("mean") is None:
        return "–"
    s = _pct(st["mean"], signed)
    if st.get("lo") is not None:
        s += f" [{_pct(st['lo'], signed)}, {_pct(st['hi'], signed)}]"
        if signed and (st["lo"] > 0 or st["hi"] < 0):
            s += " *"
    return s


def _cu(st, signed=False):
    if st is None or st.get("mean") is None:
        return "–"
    f = (lambda x: f"{x / 100:+,.0f}") if signed else (lambda x: f"{x / 100:,.0f}")
    s = f(st["mean"])
    if st.get("lo") is not None:
        s += f" [{f(st['lo'])}, {f(st['hi'])}]"
    return s.replace("-", "−")


def _t(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(r) + " |" for r in rows]


def plot_svg(res: dict, n_seeds: int, version: str = ENGINE_VERSION) -> str:
    rows = [("deceptive_share", "Deceptive share of stalls (%)"), ("shortfall_rate", "Shortfall rate, all buyers (%)")]
    W, H = 1080, 690
    left, top, pw, ph, gx, gy = 80, 150, 200, 165, 34, 95
    serif = '"ET Book", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" aria-labelledby="t d">',
           "<style>"
           f".bg{{fill:#fffff8}} .t{{font-family:{serif};fill:#111}} .s{{font-family:{serif};fill:#666}} "
           ".k{font-family:system-ui,-apple-system,sans-serif;fill:#999;font-size:11px} "
           ".n{font-family:system-ui,-apple-system,sans-serif;fill:#aaa;font-size:10.5px} "
           f".lb{{font-family:{serif};font-size:12px}} "
           ".ax{stroke:#ccc;stroke-width:1} "
           ".nv{stroke:#666;stroke-width:1.6;fill:none} .nvb{fill:#666;fill-opacity:.12} .nvt{fill:#666} "
           ".ad{stroke:#e41a1c;stroke-width:1.6;fill:none} .adb{fill:#e41a1c;fill-opacity:.12} .adt{fill:#e41a1c} "
           "@media (prefers-color-scheme: dark){.bg{fill:#151515} .t{fill:#ddd} .s{fill:#999} .k{fill:#888} .n{fill:#666} "
           ".ax{stroke:#444} .nv{stroke:#aaa} .nvb{fill:#aaa} .nvt{fill:#aaa} .ad{stroke:#fc8d62} .adb{fill:#fc8d62} "
           ".adt{fill:#fc8d62}}</style>", f'<rect class="bg" x="0" y="0" width="{W}" height="{H}"/>']
    pc1 = res["pc1"]
    title = "Thirty days of imitation: deceptive share and shortfall by enforcement and seller policy"
    sub = (f"At posts, adaptive − naive deceptive share over days 26–30: {_pct(pc1['mean'], True)} points "
           f"[{_pct(pc1['lo'], True)}, {_pct(pc1['hi'], True)}]")
    out += [f'<title id="t">{title}</title>',
            f'<desc id="d">Small multiples by placement of the per-day mean over {n_seeds} paired seeds with 95% bands, '
            f'naive versus adaptive sellers. The summary gives every value.</desc>',
            f'<text class="t" x="{left - 60}" y="40" font-size="20">{title}</text>',
            f'<text class="s" x="{left - 60}" y="64" font-size="14">{sub}</text>']
    days = np.arange(1, DAYS + 1)
    for ri, (m, label) in enumerate(rows):
        vals = []
        for pk in POLICIES:
            for pl in PLACEMENTS:
                vals += [x for st in res["trajectory"][f"{pk}|{pl}|{m}"] for x in (st["lo"], st["hi"])]
        lo, hi = 100 * min(vals), 100 * max(vals)
        pad = 0.05 * (hi - lo)
        lo, hi = lo - pad, hi + pad
        y0 = top + ri * (ph + gy)
        out.append(f'<text class="s" x="{left - 60}" y="{y0 - 22}" font-size="14">{label}</text>')
        for ci, pl in enumerate(PLACEMENTS):
            x0 = left + ci * (pw + gx)

            def X(d):
                return x0 + (d - 1) / (DAYS - 1) * pw

            def Y(val):
                return y0 + ph - (100 * val - lo) / (hi - lo) * ph
            if ri == 0:
                out.append(f'<text class="t" x="{x0}" y="{top - 60}" font-size="14">{PL_LABEL[pl]}</text>')
            out.append(f'<line class="ax" x1="{X(1):.1f}" y1="{y0 + ph + 6}" x2="{X(DAYS):.1f}" y2="{y0 + ph + 6}"/>')
            for d in (1, 10, 20, 30):
                out.append(f'<text class="k" x="{X(d):.1f}" y="{y0 + ph + 20}" text-anchor="middle">{d}</text>')
            if ci == 0:
                tv = [lo + pad, hi - pad]
                out.append(f'<line class="ax" x1="{x0 - 6}" y1="{Y(tv[0] / 100):.1f}" x2="{x0 - 6}" y2="{Y(tv[1] / 100):.1f}"/>')
                for v_ in tv:
                    out.append(f'<text class="k" x="{x0 - 10}" y="{Y(v_ / 100) + 4:.1f}" text-anchor="end">{v_:.0f}</text>')
            for pk, cls in (("rd", "nv"), ("ad", "ad")):
                tr = res["trajectory"][f"{pk}|{pl}|{m}"]
                band = [f"{X(d):.1f},{Y(st['hi']):.1f}" for d, st in zip(days, tr)] + \
                       [f"{X(d):.1f},{Y(st['lo']):.1f}" for d, st in reversed(list(zip(days, tr)))]
                out.append(f'<polygon class="{cls}b" points="{" ".join(band)}"/>')
                out.append(f'<polyline class="{cls}" points="' +
                           " ".join(f"{X(d):.1f},{Y(st['mean']):.1f}" for d, st in zip(days, tr)) + '"/>')
            if ci == len(PLACEMENTS) - 1:
                ya, yn = Y(res["trajectory"][f"ad|{pl}|{m}"][-1]["mean"]), Y(res["trajectory"][f"rd|{pl}|{m}"][-1]["mean"])
                if abs(ya - yn) < 13:
                    ya, yn = (ya - 7, yn + 7) if ya < yn else (ya + 7, yn - 7)
                out.append(f'<text class="lb adt" x="{X(DAYS) + 5:.1f}" y="{ya + 4:.1f}">adaptive</text>')
                out.append(f'<text class="lb nvt" x="{X(DAYS) + 5:.1f}" y="{yn + 4:.1f}">naive</text>')
    yb = top + 2 * ph + gy + 44
    out.append(f'<text class="k" x="{left + 2 * (pw + gx) - gx / 2:.1f}" y="{yb}" text-anchor="middle">day</text>')
    out.append(f'<text class="n" x="{left - 60}" y="{yb + 28}">Bazaar engine {version}; 2 uniformed inspectors, '
               f'recognition range 0 (adaptive sellers react to catch notices only). Lines: mean over {n_seeds} paired '
               f'seeds; bands: 95% t-interval per day.</text>')
    out.append(f'<text class="n" x="{left - 60}" y="{yb + 44}">Imitation between days: revise 0.2, mutation 0.02, '
               f'per-category normaliser; switching cost 0 (placeholder).</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def report(meta: dict, res: dict | None, gate: dict, svg_name: str, extra: dict) -> str:
    L = ["# Multi-day entry and exit", "", "Part C of the decomposition / grid-refinement / entry-exit spec (2026-11-05).", "",
         "## Run record", "",
         f"- Engine `{meta['engine_version']}`; commit `{meta['git']['commit']}`; uncommitted at run time: "
         f"{meta['git']['status_porcelain'] or 'none'}",
         f"- Script sha256 `{meta['script_sha256']}`", f"- Command: `{meta['command']}`",
         f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
         f"- {meta['n_chains']} chains x {DAYS} days on {meta['workers']} workers (plus one single-day run per chain for "
         f"the gate); wall clock {meta['wall_clock_s'] / 60:.1f} min; load average {meta['load_at_start']} at start, "
         f"{meta['load_at_end']} at end", f"- Seeds {meta['seeds'][0]}-{meta['seeds'][-1]}, paired", "",
         "## Design (prespecified)", "",
         "- Deceptive-stall policy naive (`rule_deceptive`) or adaptive (`rule_deceptive_adaptive`) x 2 uniformed "
         "inspectors on posts, patrolling or disguised full-shift, plus a no-inspector control per policy: 8 conditions. "
         "Recognition range 0, so adaptive sellers react to public catch notices and their own reopening only.",
         "- 30 days. Each day is a full bazaar run with a fresh buyer population (streams `[seed, 9, day]` for days ≥ 2, "
         "identical across conditions). Stall locations and categories persist; closures and catch notices reset.",
         "- Between days: each genuine or deceptive stall revises with probability 0.2, comparing its profit with a "
         "random other genuine/deceptive stall of its category; if that stall's type differs and earned more, it "
         "switches with probability Δprofit / (largest profit difference among genuine/deceptive stalls of the category "
         "that day). Then mutation 0.02. Seconds never switch. Switching cost 0 (PLACEHOLDER). Normaliser and partner "
         "pool decided 2026-11-05.",
         "- Late = mean of days 26–30. Intervals 95% paired t over 30 seeds, unadjusted; confirmatory: PC1, PC2.", "",
         "## Gate", "",
         f"- Day-1 outcome equals the single-day engine, byte for byte, in every chain: "
         f"**{'passed' if gate['passed'] else 'FAILED'}** ({gate['n_match']} of {gate['n']} chains)", ""]
    if res is None:
        return "\n".join(L + ["**Gate failed: results not reported.**", ""])
    pc1, pc2 = res["pc1"], res["pc2"]
    c = res["contrasts"]["posts"]
    L += ["## Confirmatory", "",
          f"- **PC1** (posts): late deceptive share, adaptive − naive = {_cp(pc1)} points. Prediction > 0. "
          f"**Verdict: {pc1['verdict']}.**",
          f"- **PC2** (posts): shortfall gap adaptive − naive was {_cp(c['day1_shortfall_gap'])} points on day 1 and "
          f"{_cp(c['late_shortfall_gap'])} over days 26–30; change {_cp(pc2)}. Prediction > 0 (the honesty gain "
          f"shrinks). **Verdict: {pc2['verdict']}.**", "",
          "## PC3 (exploratory): every placement", ""]
    L += _t(["Placement", "Late deceptive share, naive", "adaptive", "adaptive − naive", "Shortfall gap day 1",
             "Gap days 26–30", "Change"],
            [[PL_LABEL[pl], _cp(res["late"][f"rd|{pl}|deceptive_share"], False),
              _cp(res["late"][f"ad|{pl}|deceptive_share"], False), _cp(res["contrasts"][pl]["late_deceptive_share"]),
              _cp(res["contrasts"][pl]["day1_shortfall_gap"]), _cp(res["contrasts"][pl]["late_shortfall_gap"]),
              _cp(res["contrasts"][pl]["shortfall_gap_change"])] for pl in PLACEMENTS])
    L += ["", "Which placement holds the late deceptive share lowest:", ""]
    for pk, r in res["pc3_rank"].items():
        best = r["order"][0]
        L.append(f"- {POLICIES[pk]}: **{PL_LABEL[best]}** ({_pct(r['means'][best])}%); others: " +
                 "; ".join(f"{PL_LABEL[pl]} {_pct(r['means'][pl])}% (vs best {_cp(r['best_minus_others'][pl])})"
                           for pl in r["order"][1:]) +
                 f". Day 30 alone: " + ", ".join(f"{PL_LABEL[pl]} {_pct(r['day30'][pl])}%" for pl in r["order"]))
    L += ["", f"![trajectories]({svg_name})", "", "## Late levels (days 26–30)", ""]
    L += _t(["Policy", "Placement", "Deceptive share (%)", "Shortfall (%)", "Catches/day", "Genuine profit/stall ($)",
             "Deceptive profit/stall ($)", "Switches/day"],
            [[POLICIES[pk], PL_LABEL[pl], _cp(res["late"][f"{pk}|{pl}|deceptive_share"], False),
              _cp(res["late"][f"{pk}|{pl}|shortfall_rate"], False),
              f"{res['late'][f'{pk}|{pl}|catches']['mean']:.1f}",
              _cu(res["late"][f"{pk}|{pl}|profit_genuine"]), _cu(res["late"][f"{pk}|{pl}|profit_deceptive"]),
              f"{res['late'][f'{pk}|{pl}|switches']['mean']:.2f}"] for pk in POLICIES for pl in PLACEMENTS])
    L += ["", "## Day 1 levels", ""]
    L += _t(["Policy", "Placement", "Deceptive share (%)", "Shortfall (%)", "Genuine profit/stall ($)",
             "Deceptive profit/stall ($)"],
            [[POLICIES[pk], PL_LABEL[pl], _cp(res["trajectory"][f"{pk}|{pl}|deceptive_share"][0], False),
              _cp(res["trajectory"][f"{pk}|{pl}|shortfall_rate"][0], False),
              _cu(res["trajectory"][f"{pk}|{pl}|profit_genuine"][0]),
              _cu(res["trajectory"][f"{pk}|{pl}|profit_deceptive"][0])] for pk in POLICIES for pl in PLACEMENTS])
    L += ["", "## Switching totals over 29 revisions (mean per chain)", ""]
    L += _t(["Policy", "Placement", "to deceptive", "to genuine", "of which mutations"],
            [[POLICIES[pk], PL_LABEL[pl], f"{extra[(pk, pl)]['to_dec']:.1f}", f"{extra[(pk, pl)]['to_gen']:.1f}",
              f"{extra[(pk, pl)]['mut']:.1f}"] for pk in POLICIES for pl in PLACEMENTS])
    L += ["", "## Stability (change over days 21–30, per-seed OLS slope × 9)", ""]
    L += _t(["Policy", "Placement", "Deceptive share (pts)", "Shortfall (pts)"],
            [[POLICIES[pk], PL_LABEL[pl], _cp(res["stability"][f"{pk}|{pl}|deceptive_share"]),
              _cp(res["stability"][f"{pk}|{pl}|shortfall_rate"])] for pk in POLICIES for pl in PLACEMENTS])
    L += ["", "Not stabilized by day 30 (interval excludes 0):", ""] + ([f"- {x}" for x in res["flags"]] or ["- none"])
    L += ["", "## Verdicts", "", "VERDICTS_PLACEHOLDER", "", "## Reading (written after the results)", "",
          "READING_PLACEHOLDER", "", "## Caveats", "", "CAVEATS_PLACEHOLDER", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0-29")
    ap.add_argument("--out", default="runs/entry_exit.json")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--replot", action="store_true",
                    help="redraw the SVG from the results in --out, without running anything")
    a = ap.parse_args(argv)
    if a.replot:
        with open(a.out, encoding="utf-8") as f:
            d = json.load(f)
        svg = a.out[:-5] + "_trajectories.svg"
        with open(svg, "w", encoding="utf-8") as f:
            f.write(plot_svg(d["results"], len(d["meta"]["seeds"]), d["meta"]["engine_version"]))
        print(f"redrew {svg}")
        return 0
    seeds = parse_seeds(a.seeds)
    with open(__file__, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": sha,
            "command": " ".join([".venv/bin/python -m analysis.entry_exit", *(argv or sys.argv[1:])]),
            "load_at_start": _load(), "python": platform.python_version(), "numpy": np.__version__,
            "platform": platform.platform(), "workers": a.workers, "seeds": seeds, "days": DAYS}
    jobs = [(pk, pl, s) for s in seeds for pk in POLICIES for pl in PLACEMENTS]
    t0 = time.time()
    runs = []
    with ProcessPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(_job, jobs)):
            runs.append(r)
            if (i + 1) % 8 == 0:
                print(f"{i + 1}/{len(jobs)} chains, {time.time() - t0:.0f} s, load {_load()}", flush=True)
    meta.update(wall_clock_s=time.time() - t0, load_at_end=_load(), n_chains=len(runs))
    pos = {s: i for i, s in enumerate(seeds)}
    v = {(pk, pl): [None] * len(seeds) for pk in POLICIES for pl in PLACEMENTS}
    extra = {}
    for r in runs:
        v[(r["policy"], r["placement"])][pos[r["seed"]]] = r["days"]
    for k in v:
        rs = [r for r in runs if (r["policy"], r["placement"]) == k]
        extra[k] = {"to_dec": float(np.mean([r["switches_to_deceptive"] for r in rs])),
                    "to_gen": float(np.mean([r["switches_to_genuine"] for r in rs])),
                    "mut": float(np.mean([r["mutations"] for r in rs]))}
    n_match = sum(r["day1_matches_single_day"] for r in runs)
    gate = {"passed": n_match == len(runs), "n_match": n_match, "n": len(runs),
            "failed": [f"{r['policy']} {r['placement']} seed {r['seed']}" for r in runs if not r["day1_matches_single_day"]]}
    res = analyse(v, seeds) if gate["passed"] else None
    base = a.out[:-5]
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "gate": gate, "results": res, "runs": runs}, f, indent=1, sort_keys=True)
    with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["policy", "placement", "seed", "day"] + SERIES + ["n_deceptive", "n_genuine"])
        for r in runs:
            for d, x in enumerate(r["days"], start=1):
                w.writerow([r["policy"], r["placement"], r["seed"], d] + [x[m] for m in SERIES] +
                           [x["n_deceptive"], x["n_genuine"]])
    svg = base + "_trajectories.svg"
    if res is not None:
        with open(svg, "w", encoding="utf-8") as f:
            f.write(plot_svg(res, len(seeds)))
    with open(base + "_summary.md", "w", encoding="utf-8") as f:
        f.write(report(meta, res, gate, os.path.basename(svg), extra))
    print(f"gate passed: {gate['passed']}; wrote {a.out}, {base}.csv, {base}_summary.md")
    return 0 if gate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
