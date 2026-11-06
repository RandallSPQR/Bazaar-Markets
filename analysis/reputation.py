"""Part D: reputation, switching costs and the medium.

Prespecified design (2026-11-05; see runs/reputation_summary.md). Rule-based only.
  No inspectors (market discipline only), naive deceptive sellers (rule_deceptive), D = 30 days,
  seeds 0-29 paired. Factorial (8 conditions):
    ratings in {off, public}  x  whispers_allowed in {true, false}  x  switch_cost_to_genuine in {0, 0.5}
  (switch_cost_to_deceptive = 0). "off" runs use ratings.mode=hidden: ratings are computed and
  logged (so rugpulls can be counted) but no one sees them, so buyers and sellers behave exactly
  as with ratings off.

    .venv/bin/python -m analysis.reputation --out runs/reputation.json

Gate: (a) with ratings hidden, day 1 equals the single-day engine (byte for byte);
(b) public and hidden runs are identical on day 1 (ratings start unrated); (c) no whisper is
delivered in any whispers_allowed=false run. If the gate fails, only the gate is reported.

Late = mean over days 26-30. Genuine share = genuine stalls / 48.
  PD1 (confirmatory): genuine share, public - off, at whispers allowed, cost 0; CI excludes 0 (> 0).
  PD2 (confirmatory, two tests): interaction per seed at cost 0,
      I = [(public - off) | whispers banned] - [(public - off) | whispers allowed];
      genuine share: I > 0; shortfall: I < 0 (sign reversed). Each CI must exclude 0.
  PD3 (exploratory): cost effect (0.5 - 0) on late genuine share, with and without ratings, and
      its difference; rugpulls per stall-day (rugpulls / (48 x 30)) by condition.
  Stability flag: per seed OLS slope over days 21-30 x 9; flagged if its CI excludes 0.
Intervals: 95% paired t over seeds, unadjusted. Confirmatory family: PD1, PD2 (genuine), PD2 (shortfall).

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
N_STALLS = 48
RATINGS = {"off": "hidden", "public": "public"}
WHISPERS = {"wy": True, "wn": False}
COSTS = {"c0": 0.0, "c50": 0.5}
CONDS = [(r, w, c) for r in RATINGS for w in WHISPERS for c in COSTS]
SERIES = ["genuine_share", "shortfall_rate", "deceptive_profit", "genuine_profit", "rugpulls", "switches",
          "mean_rating_genuine", "mean_rating_deceptive"]
LABEL = {"off": "ratings off", "public": "ratings public", "wy": "whispers allowed", "wn": "whispers banned",
         "c0": "no switch cost", "c50": "cost into honesty 0.5"}


def cname(r, w, c) -> str:
    return f"{r}|{w}|{c}"


def _overrides(r, w, c, seed, days=DAYS) -> list[str]:
    return ["inspectors.count=0", "agents.seller.deceptive=rule_deceptive", f"market.days={days}",
            f"ratings.mode={RATINGS[r]}", f"market.whispers_allowed={'true' if WHISPERS[w] else 'false'}",
            f"pricing.switch_cost_to_genuine={COSTS[c]}", "pricing.switch_cost_to_deceptive=0.0", f"seed={seed}"]


def _mean_rating(ratings: dict, types: dict, t: str):
    xs = [v for sid, v in ratings.items() if v is not None and types.get(sid) == t]
    return float(np.mean(xs)) if xs else None


def _job(args) -> dict:
    r, w, c, seed = args
    out = bazaar.run(load(None, _overrides(r, w, c, seed), mode="bazaar"))
    days = []
    for d in out["days"]:
        o, t = d["outcome"], d["types"]
        pt = o["seller_by_type"]
        stype = d["stall_types"]
        days.append({"genuine_share": t["genuine"] / N_STALLS, "shortfall_rate": o["shortfall_rate"],
                     "deceptive_profit": pt["deceptive"]["profit_per_stall_cents"] if "deceptive" in pt else None,
                     "genuine_profit": pt["genuine"]["profit_per_stall_cents"] if "genuine" in pt else None,
                     "rugpulls": d["rugpulls"], "switches": len(d["switches"]),
                     "mean_rating_genuine": _mean_rating(d["ratings"], stype, "genuine"),
                     "mean_rating_deceptive": _mean_rating(d["ratings"], stype, "deceptive"),
                     "whispers": o["impressions_by_channel"].get("whisper", 0)})
    gate = {}
    if r == "off":
        single = bazaar.run(load(None, _overrides(r, w, c, seed, days=1), mode="bazaar"))
        gate["day1_matches_single_day"] = dumps(out["days"][0]["outcome"]) == dumps(single)
    gate["day1_outcome_sha"] = hashlib.sha256(dumps(out["days"][0]["outcome"]).encode()).hexdigest()
    return {"cond": cname(r, w, c), "seed": seed, "days": days, "gate": gate}


def _git() -> dict:
    def g(*a):
        return subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
    return {"commit": g("rev-parse", "HEAD"), "status_porcelain": g("status", "--porcelain").splitlines()}


def _load() -> list[float]:
    return [round(x, 2) for x in os.getloadavg()]


def _arr(v, cond, m) -> np.ndarray:
    return np.array([[np.nan if x[m] is None else x[m] for x in r] for r in v[cond]], float)


def _late(a) -> np.ndarray:
    return np.nanmean(a[:, [d - 1 for d in LATE]], 1)


def _stab(a) -> dict:
    x = np.array(STAB, float)
    xc = x - x.mean()
    Y = a[:, [d - 1 for d in STAB]]
    ok = ~np.isnan(Y).any(1)
    st = mean_ci(list((Y[ok] * xc).sum(1) / (xc ** 2).sum() * (STAB[-1] - STAB[0])))
    st["flag"] = st["lo"] is not None and (st["lo"] > 0 or st["hi"] < 0)
    return st


def _verdict(st, sign=+1):
    if st["lo"] is None:
        return "not testable"
    if (sign > 0 and st["lo"] > 0) or (sign < 0 and st["hi"] < 0):
        return "supported"
    if (sign > 0 and st["hi"] < 0) or (sign < 0 and st["lo"] > 0):
        return "contradicted (interval on the opposite side of 0)"
    return "not supported (interval includes 0)"


def analyse(v: dict) -> dict:
    res: dict = {"trajectory": {}, "late": {}, "stability": {}}
    for cond in v:
        for m in SERIES:
            a = _arr(v, cond, m)
            res["trajectory"][f"{cond}|{m}"] = [mean_ci(list(a[:, j])) for j in range(DAYS)]
            res["late"][f"{cond}|{m}"] = mean_ci(list(_late(a)))
            if m in ("genuine_share", "shortfall_rate"):
                res["stability"][f"{cond}|{m}"] = _stab(a)
    L = {(cond, m): _late(_arr(v, cond, m)) for cond in v for m in ("genuine_share", "shortfall_rate")}
    eff = {}
    for w in WHISPERS:
        for c in COSTS:
            for m in ("genuine_share", "shortfall_rate"):
                eff[f"{w}|{c}|{m}"] = paired_diff(list(L[(cname("off", w, c), m)]), list(L[(cname("public", w, c), m)]))
    res["ratings_effect"] = eff
    pd1 = eff["wy|c0|genuine_share"]
    res["pd1"] = {**pd1, "verdict": _verdict(pd1, +1)}
    pd2 = {}
    for m, sign in (("genuine_share", +1), ("shortfall_rate", -1)):
        on_off_wn = L[(cname("public", "wn", "c0"), m)] - L[(cname("off", "wn", "c0"), m)]
        on_off_wy = L[(cname("public", "wy", "c0"), m)] - L[(cname("off", "wy", "c0"), m)]
        st = mean_ci(list(on_off_wn - on_off_wy))
        pd2[m] = {**st, "verdict": _verdict(st, sign)}
    res["pd2"] = pd2
    pd3 = {}
    for r in RATINGS:
        for w in WHISPERS:
            pd3[f"{r}|{w}"] = paired_diff(list(L[(cname(r, w, "c0"), "genuine_share")]),
                                          list(L[(cname(r, w, "c50"), "genuine_share")]))
    for w in WHISPERS:
        ce_off = L[(cname("off", w, "c50"), "genuine_share")] - L[(cname("off", w, "c0"), "genuine_share")]
        ce_on = L[(cname("public", w, "c50"), "genuine_share")] - L[(cname("public", w, "c0"), "genuine_share")]
        pd3[f"interaction|{w}"] = mean_ci(list(ce_on - ce_off))   # > 0: the cost hurts less with ratings
    res["pd3_cost"] = pd3
    rug = {}
    for cond in v:
        tot = np.nansum(_arr(v, cond, "rugpulls"), 1) / (N_STALLS * DAYS)
        rug[cond] = mean_ci(list(tot))
    res["rugpulls_per_stall_day"] = rug
    res["flags"] = [f"{k.rsplit('|', 1)[0]} / {k.rsplit('|', 1)[1]}: change over days 21-30 {st['mean']:+.4f} "
                    f"[{st['lo']:+.4f}, {st['hi']:+.4f}]" for k, st in res["stability"].items() if st["flag"]]
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


def _cu(st):
    if st is None or st.get("mean") is None:
        return "–"
    return f"{st['mean'] / 100:,.0f}".replace("-", "−")


def _t(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(r) + " |" for r in rows]


def plot_svg(res: dict, n_seeds: int, version: str = ENGINE_VERSION) -> str:
    rows = [("genuine_share", "Genuine share of stalls (%)"), ("shortfall_rate", "Shortfall rate (%)")]
    cols = [(w, c) for c in COSTS for w in WHISPERS]
    W, H = 1080, 690
    left, top, pw, ph, gx, gy = 80, 150, 200, 165, 34, 95
    serif = '"ET Book", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" aria-labelledby="t d">',
           "<style>"
           f".bg{{fill:#fffff8}} .t{{font-family:{serif};fill:#111}} .s{{font-family:{serif};fill:#666}} "
           ".k{font-family:system-ui,-apple-system,sans-serif;fill:#999;font-size:11px} "
           ".n{font-family:system-ui,-apple-system,sans-serif;fill:#aaa;font-size:10.5px} "
           f".lb{{font-family:{serif};font-size:12px}} .ax{{stroke:#ccc;stroke-width:1}} "
           ".of{stroke:#666;stroke-width:1.6;fill:none} .ofb{fill:#666;fill-opacity:.12} .oft{fill:#666} "
           ".on{stroke:#4e79a7;stroke-width:1.6;fill:none} .onb{fill:#4e79a7;fill-opacity:.14} .ont{fill:#4e79a7} "
           "@media (prefers-color-scheme: dark){.bg{fill:#151515} .t{fill:#ddd} .s{fill:#999} .k{fill:#888} .n{fill:#666} "
           ".ax{stroke:#444} .of{stroke:#aaa} .ofb{fill:#aaa} .oft{fill:#aaa} .on{stroke:#8fb3d9} .onb{fill:#8fb3d9} "
           ".ont{fill:#8fb3d9}}</style>", f'<rect class="bg" x="0" y="0" width="{W}" height="{H}"/>']
    pd1 = res["pd1"]
    title = "Public ratings and the genuine share of stalls, over 30 days without inspectors"
    sub = (f"Ratings effect on late genuine share (whispers allowed, no switch cost): {_pct(pd1['mean'], True)} points "
           f"[{_pct(pd1['lo'], True)}, {_pct(pd1['hi'], True)}]")
    out += [f'<title id="t">{title}</title>',
            f'<desc id="d">Small multiples by whisper rule and switching cost; per-day means over {n_seeds} paired seeds '
            f'with 95% bands, ratings public versus off. The summary gives every value.</desc>',
            f'<text class="t" x="{left - 60}" y="40" font-size="20">{title}</text>',
            f'<text class="s" x="{left - 60}" y="64" font-size="14">{sub}</text>']
    days = np.arange(1, DAYS + 1)
    for ri, (m, label) in enumerate(rows):
        vals = [x for (w, c) in cols for r in RATINGS for st in res["trajectory"][f"{cname(r, w, c)}|{m}"]
                for x in (st["lo"], st["hi"]) if x is not None]
        lo, hi = 100 * min(vals), 100 * max(vals)
        pad = 0.05 * (hi - lo)
        lo, hi = lo - pad, hi + pad
        y0 = top + ri * (ph + gy)
        out.append(f'<text class="s" x="{left - 60}" y="{y0 - 22}" font-size="14">{label}</text>')
        for ci, (w, c) in enumerate(cols):
            x0 = left + ci * (pw + gx)

            def X(d):
                return x0 + (d - 1) / (DAYS - 1) * pw

            def Y(val):
                return y0 + ph - (100 * val - lo) / (hi - lo) * ph
            if ri == 0:
                out.append(f'<text class="t" x="{x0}" y="{top - 70}" font-size="13">{LABEL[w]}</text>')
                out.append(f'<text class="s" x="{x0}" y="{top - 54}" font-size="12">{LABEL[c]}</text>')
            out.append(f'<line class="ax" x1="{X(1):.1f}" y1="{y0 + ph + 6}" x2="{X(DAYS):.1f}" y2="{y0 + ph + 6}"/>')
            for d in (1, 10, 20, 30):
                out.append(f'<text class="k" x="{X(d):.1f}" y="{y0 + ph + 20}" text-anchor="middle">{d}</text>')
            if ci == 0:
                tv = [lo + pad, hi - pad]
                out.append(f'<line class="ax" x1="{x0 - 6}" y1="{Y(tv[0] / 100):.1f}" x2="{x0 - 6}" y2="{Y(tv[1] / 100):.1f}"/>')
                for v_ in tv:
                    out.append(f'<text class="k" x="{x0 - 10}" y="{Y(v_ / 100) + 4:.1f}" text-anchor="end">{v_:.0f}</text>')
            for r, cls in (("off", "of"), ("public", "on")):
                tr = res["trajectory"][f"{cname(r, w, c)}|{m}"]
                band = [f"{X(d):.1f},{Y(st['hi']):.1f}" for d, st in zip(days, tr)] + \
                       [f"{X(d):.1f},{Y(st['lo']):.1f}" for d, st in reversed(list(zip(days, tr)))]
                out.append(f'<polygon class="{cls}b" points="{" ".join(band)}"/>')
                out.append(f'<polyline class="{cls}" points="' +
                           " ".join(f"{X(d):.1f},{Y(st['mean']):.1f}" for d, st in zip(days, tr)) + '"/>')
            if ci == len(cols) - 1:
                ya = Y(res["trajectory"][f"{cname('public', w, c)}|{m}"][-1]["mean"])
                yn = Y(res["trajectory"][f"{cname('off', w, c)}|{m}"][-1]["mean"])
                if abs(ya - yn) < 13:
                    ya, yn = (ya - 7, yn + 7) if ya < yn else (ya + 7, yn - 7)
                out.append(f'<text class="lb ont" x="{X(DAYS) + 5:.1f}" y="{ya + 4:.1f}">public</text>')
                out.append(f'<text class="lb oft" x="{X(DAYS) + 5:.1f}" y="{yn + 4:.1f}">off</text>')
    yb = top + 2 * ph + gy + 44
    out.append(f'<text class="k" x="{left + 2 * (pw + gx) - gx / 2:.1f}" y="{yb}" text-anchor="middle">day</text>')
    out.append(f'<text class="n" x="{left - 60}" y="{yb + 28}">Bazaar engine {version}; no inspectors, naive '
               f'deceptive sellers. Lines: mean over {n_seeds} paired seeds; bands: 95% t-interval per day.</text>')
    out.append(f'<text class="n" x="{left - 60}" y="{yb + 44}">Ratings: memory 0.7, skip threshold 0.5 (placeholders); '
               f'locals and experts see them. Imitation between days: revise 0.2, mutation 0.02.</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def report(meta, res, gate, svg_name) -> str:
    L = ["# Reputation, switching costs and the medium", "",
         "Part D of the decomposition / grid-refinement / entry-exit spec (2026-11-05).", "", "## Run record", "",
         f"- Engine `{meta['engine_version']}`; commit `{meta['git']['commit']}`; uncommitted at run time: "
         f"{meta['git']['status_porcelain'] or 'none'}",
         f"- Script sha256 `{meta['script_sha256']}`", f"- Command: `{meta['command']}`",
         f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
         f"- {meta['n_chains']} chains x {DAYS} days on {meta['workers']} workers; wall clock "
         f"{meta['wall_clock_s'] / 60:.1f} min; load average {meta['load_at_start']} at start, {meta['load_at_end']} at end",
         f"- Seeds {meta['seeds'][0]}-{meta['seeds'][-1]}, paired", "",
         "## Design (prespecified)", "",
         "- No inspectors; naive deceptive sellers (`rule_deceptive`); 30 days; between-day imitation as in Part C.",
         "- Factorial: ratings off / public x whispers allowed / banned x switch cost into honesty 0 / 0.5 of base "
         "price (cost into deception 0): 8 conditions. \"Off\" runs compute ratings but show them to no one "
         "(`ratings.mode=hidden`), so rugpulls are counted in every condition.",
         "- Ratings (decided 2026-11-05): each day, a stall's rating blends yesterday's (memory 0.7) with the share of "
         "that day's units whose true Q met the latest claim the stall made to the buyer before the sale; a first "
         "rating is that day's share; days with no claimed units leave it unchanged; unrated stalls are neutral. "
         "Locals and experts see ratings; the rule buyer skips stalls rated below 0.5. Switching cost is charged in "
         "the stall's accounts on its first day in the new type. Whisper ban: sellers are told, and rule sellers do "
         "not whisper.",
         "- Late = mean of days 26–30. Intervals 95% paired t over 30 seeds, unadjusted; confirmatory: PD1, PD2 "
         "(genuine share), PD2 (shortfall).", "", "## Gate", ""]
    for k, g in gate.items():
        if k != "passed":
            L.append(f"- {g['label']}: **{'passed' if g['passed'] else 'FAILED'}** ({g['detail']})")
    L.append("")
    if res is None:
        return "\n".join(L + ["**Gate failed: results not reported.**", ""])
    p1, p2 = res["pd1"], res["pd2"]
    L += ["## Confirmatory", "",
          f"- **PD1**: late genuine share, ratings public − off (whispers allowed, no switch cost): {_cp(p1)} points. "
          f"Prediction > 0. **Verdict: {p1['verdict']}.**",
          f"- **PD2, genuine share**: [(public − off) | whispers banned] − [(public − off) | whispers allowed] = "
          f"{_cp(p2['genuine_share'])} points. Prediction > 0. **Verdict: {p2['genuine_share']['verdict']}.**",
          f"- **PD2, shortfall**: the same interaction on shortfall = {_cp(p2['shortfall_rate'])} points. Prediction < 0. "
          f"**Verdict: {p2['shortfall_rate']['verdict']}.**", "",
          "### Ratings effect (public − off) on late outcomes, by cell", ""]
    L += _t(["Whispers", "Switch cost", "Genuine share (pts)", "Shortfall (pts)"],
            [[LABEL[w], LABEL[c], _cp(res["ratings_effect"][f"{w}|{c}|genuine_share"]),
              _cp(res["ratings_effect"][f"{w}|{c}|shortfall_rate"])] for w in WHISPERS for c in COSTS])
    L += ["", "## PD3 (exploratory): switching cost into honesty", ""]
    L += _t(["Ratings", "Whispers", "Cost effect on late genuine share (0.5 − 0, pts)"],
            [[LABEL[r], LABEL[w], _cp(res["pd3_cost"][f"{r}|{w}"])] for r in RATINGS for w in WHISPERS])
    L += ["", "Does the cost hurt less with ratings? (cost effect with ratings − without; > 0 = less):", ""]
    L += [f"- {LABEL[w]}: {_cp(res['pd3_cost'][f'interaction|{w}'])} points" for w in WHISPERS]
    L += ["", "Rugpulls (genuine → deceptive while rated ≥ 0.8) per stall-day (rugpulls / (48 × 30)), per thousand:", ""]
    L += _t(["Condition", "Rugpulls per 1,000 stall-days"],
            [[f"{LABEL[r]}, {LABEL[w]}, {LABEL[c]}",
              (lambda st: f"{1000 * st['mean']:.2f} [{1000 * st['lo']:.2f}, {1000 * st['hi']:.2f}]".replace("-", "−"))(
                  res["rugpulls_per_stall_day"][cname(r, w, c)])] for r, w, c in CONDS])
    L += ["", f"![trajectories]({svg_name})", "", "## Late levels (days 26–30)", ""]
    L += _t(["Ratings", "Whispers", "Switch cost", "Genuine share (%)", "Shortfall (%)", "Genuine profit/stall ($)",
             "Deceptive profit/stall ($)", "Mean rating, genuine", "Mean rating, deceptive", "Switches/day"],
            [[LABEL[r], LABEL[w], LABEL[c], _cp(res["late"][f"{cname(r, w, c)}|genuine_share"], False),
              _cp(res["late"][f"{cname(r, w, c)}|shortfall_rate"], False),
              _cu(res["late"][f"{cname(r, w, c)}|genuine_profit"]), _cu(res["late"][f"{cname(r, w, c)}|deceptive_profit"]),
              f"{res['late'][f'{cname(r, w, c)}|mean_rating_genuine']['mean']:.2f}"
              if res['late'][f'{cname(r, w, c)}|mean_rating_genuine']['mean'] is not None else "–",
              f"{res['late'][f'{cname(r, w, c)}|mean_rating_deceptive']['mean']:.2f}"
              if res['late'][f'{cname(r, w, c)}|mean_rating_deceptive']['mean'] is not None else "–",
              f"{res['late'][f'{cname(r, w, c)}|switches']['mean']:.2f}"] for r, w, c in CONDS])
    L += ["", "## Day 1 levels", ""]
    L += _t(["Ratings", "Whispers", "Switch cost", "Genuine share (%)", "Shortfall (%)"],
            [[LABEL[r], LABEL[w], LABEL[c], _cp(res["trajectory"][f"{cname(r, w, c)}|genuine_share"][0], False),
              _cp(res["trajectory"][f"{cname(r, w, c)}|shortfall_rate"][0], False)] for r, w, c in CONDS])
    L += ["", "## Stability (change over days 21–30, per-seed OLS slope × 9)", ""]
    L += _t(["Condition", "Genuine share (pts)", "Shortfall (pts)"],
            [[f"{LABEL[r]}, {LABEL[w]}, {LABEL[c]}", _cp(res["stability"][f"{cname(r, w, c)}|genuine_share"]),
              _cp(res["stability"][f"{cname(r, w, c)}|shortfall_rate"])] for r, w, c in CONDS])
    L += ["", "Still trending over days 21–30 (interval excludes 0):", ""] + ([f"- {x}" for x in res["flags"]] or ["- none"])
    L += ["", "## Verdicts", "", "VERDICTS_PLACEHOLDER", "", "## Reading (written after the results)", "",
          "READING_PLACEHOLDER", "", "## Caveats", "", "CAVEATS_PLACEHOLDER", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0-29")
    ap.add_argument("--out", default="runs/reputation.json")
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
            "command": " ".join([".venv/bin/python -m analysis.reputation", *(argv or sys.argv[1:])]),
            "load_at_start": _load(), "python": platform.python_version(), "numpy": np.__version__,
            "platform": platform.platform(), "workers": a.workers, "seeds": seeds, "days": DAYS}
    jobs = [(r, w, c, s) for s in seeds for r, w, c in CONDS]
    t0 = time.time()
    runs = []
    with ProcessPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(_job, jobs)):
            runs.append(r)
            if (i + 1) % 8 == 0:
                print(f"{i + 1}/{len(jobs)} chains, {time.time() - t0:.0f} s, load {_load()}", flush=True)
    meta.update(wall_clock_s=time.time() - t0, load_at_end=_load(), n_chains=len(runs))
    pos = {s: i for i, s in enumerate(seeds)}
    v = {cname(*c): [None] * len(seeds) for c in CONDS}
    for r in runs:
        v[r["cond"]][pos[r["seed"]]] = r["days"]
    g1 = [r for r in runs if "day1_matches_single_day" in r["gate"]]
    n1 = sum(r["gate"]["day1_matches_single_day"] for r in g1)
    sha = {(r["cond"], r["seed"]): r["gate"]["day1_outcome_sha"] for r in runs}
    pairs = [(w, c, s) for w in WHISPERS for c in COSTS for s in seeds]
    n2 = sum(sha[(cname("off", w, c), s)] == sha[(cname("public", w, c), s)] for w, c, s in pairs)
    banned = [r for r in runs if "|wn|" in r["cond"]]
    n3 = sum(all(d["whispers"] == 0 for d in r["days"]) for r in banned)
    gate = {"day1_single": {"label": "Day 1 equals the single-day engine (ratings hidden)", "passed": n1 == len(g1),
                            "detail": f"{n1} of {len(g1)} chains"},
            "day1_public_hidden": {"label": "Day 1 identical with ratings public and hidden", "passed": n2 == len(pairs),
                                   "detail": f"{n2} of {len(pairs)} pairs"},
            "no_whispers": {"label": "No whisper delivered when whispers are banned", "passed": n3 == len(banned),
                            "detail": f"{n3} of {len(banned)} chains with zero whispers on every day"}}
    gate["passed"] = all(g["passed"] for k, g in gate.items() if k != "passed")
    res = analyse(v) if gate["passed"] else None
    base = a.out[:-5]
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "gate": gate, "results": res, "runs": runs}, f, indent=1, sort_keys=True)
    with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ratings", "whispers", "switch_cost", "seed", "day"] + SERIES + ["whispers_delivered"])
        for r in runs:
            for d, x in enumerate(r["days"], start=1):
                w.writerow(r["cond"].split("|") + [r["seed"], d] + [x[m] for m in SERIES] + [x["whispers"]])
    svg = base + "_trajectories.svg"
    if res is not None:
        with open(svg, "w", encoding="utf-8") as f:
            f.write(plot_svg(res, len(seeds)))
    with open(base + "_summary.md", "w", encoding="utf-8") as f:
        f.write(report(meta, res, gate, os.path.basename(svg)))
    print(f"gate passed: {gate['passed']}; wrote {a.out}, {base}.csv, {base}_summary.md")
    return 0 if gate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
