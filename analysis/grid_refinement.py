"""Part B: grid refinement and the warning-margin test.

Prespecified design (2026-11-05; see runs/grid_refinement_summary.md). E = market.earshot = 4.
All at count 2, seeds 0-29 paired, default detection.
  k = 2 (market.scale=2):
    adaptive sellers (rule_deceptive_adaptive), uniformed posts and patrolling,
      recognition r/E in {0, 1/8, ..., 8/8} x whisper range in {0.5E (default), 0.75E}      (36)
    naive sellers (rule_deceptive), posts and patrolling, the placement-sweep cells          (2)
  k = 1, exploratory comparator for PB3 (agreed 2026-11-05):
    adaptive, uniformed posts and patrolling, the same 9 levels, whisper 0.5E               (18)

    .venv/bin/python -m analysis.grid_refinement --out runs/grid_refinement.json

Gate: (a) at k = 2, dedicated inspector-active ticks equal across placements (= k x count x ticks);
(b) at r = 0, no seller observation shows "uniform": true (one full seed's logs, k = 2, both
whisper settings, both placements); (c) the k = 1 comparator's levels shared with the committed
recognition sweep (r/E = 0, 1/4, 1/2, 3/4, 1) equal those values exactly. If the gate fails,
only the gate is reported.

Predictions:
  PB1 (confirmatory): at k = 2, patrolling - posts (naive, count 2) < 0 for deceptive profit
      and for shortfall, 95% paired t-intervals excluding 0.
  PB2 (confirmatory): crossover(0.75E) - crossover(0.5E) for adaptive sellers at k = 2, where the
      crossover is the interpolated r/E at which patrolling - posts on shortfall first reaches 0
      (from below: patrolling better). Paired percentile bootstrap over seeds, 10,000 resamples,
      default_rng(20261105); resamples where either curve does not cross are counted and
      excluded. Prediction: the 95% interval excludes 0 and contains +0.25.
  PB3 (exploratory): k = 2 dose curves smoother than k = 1. Reported: distinct inspector-stall
      distances within earshot at each k, and per curve the largest single step between
      adjacent levels as a share of the curve's total variation (sum of absolute steps).

This script only reads engine outputs; it changes nothing in the engine.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from cli.sweep import flatten, parse_seeds
from engine import ENGINE_VERSION
from engine.bazaar import BazaarEngine
from engine.config import load
from engine.jsonlog import JsonlLog
from engine.metrics import mean_ci, paired_diff

E = 4.0
TICKS = 240
COUNT = 2
FRACS = [i / 8 for i in range(9)]
WHISPERS = {"w50": 2.0, "w75": 3.0}
POLICIES = {"ad": "rule_deceptive_adaptive", "rd": "rule_deceptive"}
PRIOR = "runs/recognition_sweep.json"
METRICS = ["profit_per_stall.deceptive", "shortfall_rate", "catches", "reachable.buyer_surplus_mean_cents",
           "reachable.task_complete_share", "deceptive_share_sales_units", "inspector_active_ticks.dedicated",
           "false_claims.messages", "impressions_by_channel.whisper", "false_claim_impressions_to_uniform_eligible"]
PRIMARY = ["profit_per_stall.deceptive", "shortfall_rate"]
MONEY = {"profit_per_stall.deceptive", "reachable.buyer_surplus_mean_cents"}
PCT = {"shortfall_rate", "reachable.task_complete_share", "deceptive_share_sales_units"}


def cname(k: int, pl: str, w: str, f: float | None) -> str:
    return f"k{k}_{pl}_{w}" + ("" if f is None else f"_r{round(f * 8)}of8")


def _conditions() -> list[dict]:
    out = []
    for w in WHISPERS:
        for pl in ("posts", "patrolling"):
            for f in FRACS:
                out.append({"policy": "ad", "k": 2, "placement": pl, "whisper": w, "frac": f, "role": "dose"})
    for pl in ("posts", "patrolling"):
        out.append({"policy": "rd", "k": 2, "placement": pl, "whisper": "w50", "frac": None, "role": "pb1"})
    for pl in ("posts", "patrolling"):
        for f in FRACS:
            out.append({"policy": "ad", "k": 1, "placement": pl, "whisper": "w50", "frac": f, "role": "k1_comparator"})
    for c in out:
        c["name"] = cname(c["k"], c["placement"], c["whisper"], c["frac"])
    return out


CONDITIONS = _conditions()


def _overrides(c: dict, seed: int) -> list[str]:
    ov = [f"market.scale={c['k']}", f"inspectors.count={COUNT}", f"inspectors.placement={c['placement']}",
          f"agents.seller.deceptive={POLICIES[c['policy']]}", f"market.whisper_range={WHISPERS[c['whisper']]}",
          f"seed={seed}"]
    if c["policy"] == "ad":
        ov += ["inspectors.uniformed=true", f"inspectors.recognition_range={c['frac'] * E}"]
    return ov


def _job(args) -> dict:
    c, seed = args
    out = flatten(BazaarEngine(load(None, _overrides(c, seed), mode="bazaar")).run())
    return {"policy": c["policy"], "condition": c["name"], "seed": seed,
            "values": {m: out.get(m, 0 if m.startswith("impressions_by_channel") else None) for m in METRICS}}


def _git() -> dict:
    def g(*a):
        return subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
    return {"commit": g("rev-parse", "HEAD"), "status_porcelain": g("status", "--porcelain").splitlines()}


def _load() -> list[float]:
    return [round(x, 2) for x in os.getloadavg()]


# ------------------------------------------------------------------ geometry (PB3)

def distinct_distances(k: int, seed: int = 0) -> dict:
    """Distinct inspector-stall distances within earshot, in real units, over every cell an
    inspector can stand on (every cell of every buyer, patrol and post route) and every stall."""
    cells = set()
    for pl in ("posts", "patrolling", "disguised"):
        eng = BazaarEngine(load(None, [f"market.scale={k}", "inspectors.count=6", f"inspectors.placement={pl}",
                                       "inspectors.disguised_shift=full_shift", f"seed={seed}"], mode="bazaar"))
        for p in eng.people:
            cells.update(p.route)
        posts = {p.route[0] for p in eng.people if p.kind == "inspector" and pl == "posts"}
        stalls = [st.pos for st in eng.stalls]
        if pl == "posts":
            post_d = sorted({round(math.hypot(a[0] - s[0], a[1] - s[1]) / k, 6) for a in posts for s in stalls
                             if math.hypot(a[0] - s[0], a[1] - s[1]) <= E * k})
    ds = sorted({round(math.hypot(a[0] - s[0], a[1] - s[1]) / k, 6) for a in cells for s in stalls
                 if math.hypot(a[0] - s[0], a[1] - s[1]) <= E * k})
    return {"k": k, "walkable_cells": len(cells), "n_distinct": len(ds), "distances": ds,
            "post_distances": post_d}


# ------------------------------------------------------------------ gate

def _gate(v: dict, seeds: list[int]) -> dict:
    g: dict = {}
    bad = []
    for c in CONDITIONS:
        want = c["k"] * COUNT * TICKS
        got = v[c["name"]]["inspector_active_ticks.dedicated"]
        if any(x != want for x in got):
            bad.append(f"{c['name']}: {sorted(set(got))} (want {want})")
    g["equal_effort"] = {"passed": not bad, "violations": bad,
                         "want_k2": 2 * COUNT * TICKS, "want_k1": COUNT * TICKS}
    rows = trues = uni_rows = 0
    for w in WHISPERS:
        for pl in ("posts", "patrolling"):
            c = {"policy": "ad", "k": 2, "placement": pl, "whisper": w, "frac": 0.0}
            log = JsonlLog(keep=True)
            eng = BazaarEngine(load(None, _overrides(c, seeds[0]), mode="bazaar"), log=log)
            eng.run()
            uni = {p.pid for p in eng.people if p.uniform}
            for line in log.lines:
                e = json.loads(line)
                if e["ev"] == "obs" and e["role"] == "seller":
                    for r in e["obs"]["passersby"]:
                        rows += 1
                        trues += r["uniform"] is True
                        uni_rows += r["id"] in uni
    g["no_uniform_at_r0"] = {"passed": trues == 0 and uni_rows > 0, "seed": seeds[0], "passerby_rows": rows,
                             "rows_of_uniformed_inspectors": uni_rows, "rows_with_uniform_true": trues}
    with open(PRIOR, encoding="utf-8") as f:
        prior = json.load(f)
    pidx = {(r["policy"], r["condition"], r["seed"]): r["values"] for r in prior["runs"]}
    shared = ["profit_per_stall.deceptive", "shortfall_rate", "catches", "reachable.buyer_surplus_mean_cents",
              "reachable.task_complete_share", "deceptive_share_sales_units", "inspector_active_ticks.dedicated",
              "false_claims.messages", "false_claim_impressions_to_uniform_eligible"]
    mism, n_cmp = [], 0
    for pl in ("posts", "patrolling"):
        for f in (0.0, 0.25, 0.5, 0.75, 1.0):
            for i, s in enumerate(seeds):
                old = pidx[("ad", f"{pl}{COUNT}_r{f:.2f}", s)]
                for m in shared:
                    n_cmp += 1
                    if v[cname(1, pl, "w50", f)][m][i] != old[m]:
                        mism.append(f"{cname(1, pl, 'w50', f)} seed {s}: {m}")
    g["k1_matches_recognition_sweep"] = {"passed": not mism, "values_compared": n_cmp,
                                         "n_mismatches": len(mism), "mismatches": mism[:20]}
    g["passed"] = all(g[x]["passed"] for x in ("equal_effort", "no_uniform_at_r0", "k1_matches_recognition_sweep"))
    return g


# ------------------------------------------------------------------ analysis

def _crossing(curve: np.ndarray, xs: list[float]) -> tuple[str, float | None]:
    """First r/E at which the advantage A (positive = patrolling better) stops being positive."""
    if curve[0] <= 0:
        return "never_ahead", None
    for i in range(len(xs) - 1):
        a0, a1 = curve[i], curve[i + 1]
        if a0 > 0 >= a1:
            return "cross", xs[i] + (xs[i + 1] - xs[i]) * a0 / (a0 - a1)
    return "always_ahead", None


def _D(v, k, w, m) -> np.ndarray:
    """seeds x levels: patrolling - posts."""
    return np.array([[np.nan if a is None or b is None else b - a
                      for a, b in zip(v[cname(k, "posts", w, f)][m], v[cname(k, "patrolling", w, f)][m])]
                     for f in FRACS]).T


def _roughness(curve: np.ndarray) -> float | None:
    steps = np.abs(np.diff(curve))
    tv = steps.sum()
    return float(steps.max() / tv) if tv > 0 else None


def analyse(v: dict, seeds: list[int], n_boot: int, boot_seed: int) -> dict:
    res: dict = {"per_condition": {c["name"]: {m: mean_ci(v[c["name"]][m]) for m in METRICS} for c in CONDITIONS}}
    # PB1
    pb1 = {m: paired_diff(v[cname(2, "posts", "w50", None)][m], v[cname(2, "patrolling", "w50", None)][m])
           for m in METRICS}
    res["pb1"] = {"diff": pb1, "verdict": {m: ("supported" if pb1[m]["hi"] < 0 else
                                              "contradicted (interval above 0)" if pb1[m]["lo"] > 0 else
                                              "not supported (interval includes 0)") for m in PRIMARY}}
    # dose curves
    curves = {(2, "w50"), (2, "w75"), (1, "w50")}
    rng = np.random.default_rng(boot_seed)
    idx = rng.integers(0, len(seeds), size=(n_boot, len(seeds)))
    dose, cross, rough = {}, {}, {}
    sign = {"profit_per_stall.deceptive": -1, "shortfall_rate": -1, "catches": 1,
            "reachable.buyer_surplus_mean_cents": 1, "reachable.task_complete_share": 1}
    Ds = {}
    for k, w in sorted(curves):
        for m in sign:
            D = _D(v, k, w, m)
            Ds[(k, w, m)] = D
            key = f"k{k}|{w}|{m}"
            dose[key] = {"levels": [mean_ci(list(D[:, j])) for j in range(len(FRACS))],
                         "posts": [mean_ci(v[cname(k, "posts", w, f)][m]) for f in FRACS],
                         "patrolling": [mean_ci(v[cname(k, "patrolling", w, f)][m]) for f in FRACS]}
            kind, val = _crossing(sign[m] * np.nanmean(D, 0), FRACS)
            cross[key] = {"kind": kind, "r_over_E": val}
            if m in PRIMARY:
                rough[key] = {"max_step_share": _roughness(np.nanmean(D, 0))}
    # bootstrap: crossovers, PB2 difference, PB3 roughness difference (same resamples throughout)
    boot = {key: [] for key in cross}
    kinds = {key: [] for key in cross}
    pb2_vals, pb2_kinds = [], {"both_cross": 0, "not_both": 0}
    rough_boot = {m: [] for m in PRIMARY}
    for b in range(n_boot):
        I = idx[b]
        xb = {}
        for (k, w, m), D in Ds.items():
            curve = np.nanmean(D[I], 0)
            kd, xv = _crossing(sign[m] * curve, FRACS)
            key = f"k{k}|{w}|{m}"
            kinds[key].append(kd)
            if kd == "cross":
                boot[key].append(xv)
            xb[key] = (kd, xv)
            if (k, w) == (2, "w50") and m in PRIMARY:
                r2 = _roughness(curve)
                r1 = _roughness(np.nanmean(Ds[(1, "w50", m)][I], 0))
                if r1 is not None and r2 is not None:
                    rough_boot[m].append(r2 - r1)
        a, c = xb["k2|w50|shortfall_rate"], xb["k2|w75|shortfall_rate"]
        if a[0] == "cross" and c[0] == "cross":
            pb2_vals.append(c[1] - a[1])
            pb2_kinds["both_cross"] += 1
        else:
            pb2_kinds["not_both"] += 1
    for key in cross:
        cross[key]["boot_ci"] = ([float(np.percentile(boot[key], 2.5)), float(np.percentile(boot[key], 97.5))]
                                 if boot[key] else None)
        cross[key]["boot_share"] = {x: kinds[key].count(x) / n_boot for x in ("cross", "always_ahead", "never_ahead")}
    a, c = cross["k2|w50|shortfall_rate"], cross["k2|w75|shortfall_rate"]
    point = (c["r_over_E"] - a["r_over_E"]) if a["kind"] == c["kind"] == "cross" else None
    ci = [float(np.percentile(pb2_vals, 2.5)), float(np.percentile(pb2_vals, 97.5))] if pb2_vals else None
    if ci is None or point is None:
        verdict = "not testable (a curve does not cross)"
    else:
        excl0, has25 = ci[0] > 0 or ci[1] < 0, ci[0] <= 0.25 <= ci[1]
        verdict = ("supported" if excl0 and has25 else
                   "partly supported (interval excludes 0 but not +0.25)" if excl0 else
                   "not supported (interval includes 0)")
    res["pb2"] = {"crossover_w50": a, "crossover_w75": c, "diff": point, "boot_ci": ci, "boot_counts": pb2_kinds,
                  "verdict": verdict}
    # exploratory: same difference for profit
    a2, c2 = cross["k2|w50|profit_per_stall.deceptive"], cross["k2|w75|profit_per_stall.deceptive"]
    res["pb2_profit_exploratory"] = {"diff": (c2["r_over_E"] - a2["r_over_E"])
                                     if a2["kind"] == c2["kind"] == "cross" else None}
    for m in PRIMARY:
        rough[f"diff|{m}"] = {"k2_minus_k1": (rough[f"k2|w50|{m}"]["max_step_share"] -
                                              rough[f"k1|w50|{m}"]["max_step_share"]),
                              "boot_ci": [float(np.percentile(rough_boot[m], 2.5)),
                                          float(np.percentile(rough_boot[m], 97.5))] if rough_boot[m] else None}
    res.update(dose=dose, crossover=cross, roughness=rough)
    # flags: outcomes constant across seeds
    flags = []
    for c in CONDITIONS:
        for m in PRIMARY + ["catches"]:
            xs = [x for x in v[c["name"]][m] if x is not None]
            if xs and len(set(xs)) == 1:
                flags.append(f"{c['name']}: {m} = {xs[0]} in every seed")
    res["flags"] = flags
    return res


# ------------------------------------------------------------------ formatting

def _f(m, x, signed=False):
    if x is None:
        return "–"
    if m in MONEY:
        x, fmt = x / 100, "{:+.0f}" if signed else "{:.0f}"
    elif m in PCT:
        x, fmt = 100 * x, "{:+.1f}" if signed else "{:.1f}"
    else:
        fmt = "{:+.2f}" if signed else "{:.2f}"
    return fmt.format(x).replace("-", "−")


def _c(m, st, signed=True):
    if not st or st.get("mean") is None:
        return "–"
    s = _f(m, st["mean"], signed)
    if st.get("lo") is not None:
        s += f" [{_f(m, st['lo'], signed)}, {_f(m, st['hi'], signed)}]"
        if signed and (st["lo"] > 0 or st["hi"] < 0):
            s += " *"
    return s


def _t(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(r) + " |" for r in rows]


def _x(x):
    return "–" if x is None else f"{x:+.3f}"


def _ci2(ci):
    return "–" if not ci else f"[{ci[0]:+.3f}, {ci[1]:+.3f}]"


FRAC_LAB = ["0", "⅛", "¼", "⅜", "½", "⅝", "¾", "⅞", "1"]


def plot_svg(res: dict, n_seeds: int) -> str:
    rows = [("profit_per_stall.deceptive", "Deceptive profit per stall", "$", 0.01),
            ("shortfall_rate", "Shortfall rate, all buyers", "pts", 100.0)]
    cols = [("w50", "whisper range ½E (default)"), ("w75", "whisper range ¾E")]
    W, H = 960, 700
    left, top, pw, ph, gx, gy = 110, 160, 330, 170, 90, 100
    serif = '"ET Book", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" '
           f'aria-labelledby="t d">', "<style>"
           f".bg{{fill:#fffff8}} .t{{font-family:{serif};fill:#111}} .s{{font-family:{serif};fill:#666}} "
           ".k{font-family:system-ui,-apple-system,sans-serif;fill:#999;font-size:11px} "
           ".n{font-family:system-ui,-apple-system,sans-serif;fill:#aaa;font-size:10.5px} "
           f".a{{font-family:{serif};fill:#333;font-style:italic;font-size:12px}} "
           f".lb{{font-family:{serif};font-size:12px}} "
           ".ax{stroke:#ccc;stroke-width:1} .z{stroke:#bbb;stroke-width:1;stroke-dasharray:3 3} "
           ".ln{stroke:#333;stroke-width:1.75;fill:none} .ci{stroke:#333;stroke-width:1.1} .pt{fill:#333} "
           ".g{stroke:#999;stroke-width:1.5;fill:none;stroke-dasharray:5 3} .gp{fill:#999} .gt{fill:#888} "
           ".mk{stroke:#e41a1c;stroke-width:1.5} .mt{fill:#e41a1c} "
           "@media (prefers-color-scheme: dark){.bg{fill:#151515} .t{fill:#ddd} .s{fill:#999} .k{fill:#888} "
           ".n{fill:#666} .a{fill:#bbb} .ax{stroke:#444} .z{stroke:#555} .ln{stroke:#ddd} .ci{stroke:#ddd} "
           ".pt{fill:#ddd} .g{stroke:#777} .gp{fill:#777} .gt{fill:#888} .mk{stroke:#fc8d62} .mt{fill:#fc8d62}}"
           "</style>", f'<rect class="bg" x="0" y="0" width="{W}" height="{H}"/>']
    pb2 = res["pb2"]
    title = "On a finer grid, patrolling’s edge over posts still falls with recognition range"
    sub = ("Adaptive sellers, 2 uniformed inspectors, grid scale k = 2. Shortfall crossover: "
           + (f"{pb2['crossover_w50']['r_over_E']:.2f}E at whisper ½E, {pb2['crossover_w75']['r_over_E']:.2f}E at ¾E"
              if pb2["diff"] is not None else "not defined for both whisper ranges"))
    out += [f'<title id="t">{title}</title>',
            f'<desc id="d">Small multiples of patrolling minus posts at nine recognition ranges, k = 2 with 95% intervals '
            f'over {n_seeds} paired seeds; dashed: the k = 1 comparator. The summary tables give every value.</desc>',
            f'<text class="t" x="{left - 80}" y="40" font-size="20">{title}</text>',
            f'<text class="s" x="{left - 80}" y="64" font-size="14">{sub}</text>']
    for ri, (m, rlabel, unit, k) in enumerate(rows):
        vals = [0.0]
        for w, _ in cols:
            vals += [x for st in res["dose"][f"k2|{w}|{m}"]["levels"] for x in (st["lo"], st["hi"])]
        vals += [st["mean"] for st in res["dose"][f"k1|w50|{m}"]["levels"]]
        lo, hi = min(vals) * k, max(vals) * k
        pad = 0.06 * (hi - lo)
        lo, hi = lo - pad, hi + pad
        y0 = top + ri * (ph + gy)
        out.append(f'<text class="s" x="{left - 80}" y="{y0 - 20}" font-size="14">{rlabel}, patrolling − posts ({unit})</text>')
        for ci, (w, clabel) in enumerate(cols):
            x0 = left + ci * (pw + gx)
            d = res["dose"][f"k2|{w}|{m}"]

            def X(f):
                return x0 + f * pw

            def Y(val):
                return y0 + ph - (val * k - lo) / (hi - lo) * ph
            if ri == 0:
                out.append(f'<text class="t" x="{x0}" y="{top - 62}" font-size="15">{clabel}</text>')
            ys = [st["lo"] for st in d["levels"]] + [st["hi"] for st in d["levels"]] + [0.0]
            if w == "w50":
                ys += [st["mean"] for st in res["dose"][f"k1|w50|{m}"]["levels"]]
            dmin, dmax = min(ys), max(ys)
            out.append(f'<line class="ax" x1="{x0 - 8}" y1="{Y(dmin):.1f}" x2="{x0 - 8}" y2="{Y(dmax):.1f}"/>')
            out.append(f'<line class="ax" x1="{X(0):.1f}" y1="{y0 + ph + 8}" x2="{X(1):.1f}" y2="{y0 + ph + 8}"/>')
            for f, lab in zip(FRACS, FRAC_LAB):
                if lab in ("0", "¼", "½", "¾", "1"):
                    out.append(f'<text class="k" x="{X(f):.1f}" y="{y0 + ph + 24}" text-anchor="middle">'
                               f'{lab if lab != "1" else ""}{"E" if lab != "0" else ""}</text>')
            span = (dmax - dmin) * k
            ticks = [dmin * k, dmax * k] + ([0.0] if min(abs(dmin), abs(dmax)) * k > 0.15 * span else [])
            for tv in ticks:
                txt = "0" if tv == 0 else (f"{tv:+.0f}" if span >= 10 else f"{tv:+.1f}")
                out.append(f'<text class="k" x="{x0 - 13}" y="{Y(tv / k) + 4:.1f}" text-anchor="end">'
                           f'{txt.replace("-", "−")}</text>')
            out.append(f'<line class="z" x1="{X(0):.1f}" y1="{Y(0):.1f}" x2="{X(1):.1f}" y2="{Y(0):.1f}"/>')
            if w == "w50":
                g = res["dose"][f"k1|w50|{m}"]["levels"]
                out.append('<polyline class="g" points="' +
                           " ".join(f"{X(f):.1f},{Y(st['mean']):.1f}" for f, st in zip(FRACS, g)) + '"/>')
                for f, st in zip(FRACS, g):
                    out.append(f'<circle class="gp" cx="{X(f):.1f}" cy="{Y(st["mean"]):.1f}" r="1.8"/>')
                out.append(f'<text class="lb gt" x="{X(1) + 6:.1f}" y="{Y(g[-1]["mean"]) + 14:.1f}">k = 1</text>')
            out.append('<polyline class="ln" points="' +
                       " ".join(f"{X(f):.1f},{Y(st['mean']):.1f}" for f, st in zip(FRACS, d["levels"])) + '"/>')
            for f, st in zip(FRACS, d["levels"]):
                out.append(f'<line class="ci" x1="{X(f):.1f}" y1="{Y(st["lo"]):.1f}" x2="{X(f):.1f}" y2="{Y(st["hi"]):.1f}"/>')
                out.append(f'<circle class="pt" cx="{X(f):.1f}" cy="{Y(st["mean"]):.1f}" r="2.4"/>')
            out.append(f'<text class="lb t" x="{X(1) + 6:.1f}" y="{Y(d["levels"][-1]["mean"]) - 4:.1f}">k = 2</text>')
            cr = res["crossover"][f"k2|{w}|{m}"]
            if cr["kind"] == "cross":
                xc_ = X(cr["r_over_E"])
                out.append(f'<line class="mk" x1="{xc_:.1f}" y1="{Y(0) - 7:.1f}" x2="{xc_:.1f}" y2="{Y(0) + 7:.1f}"/>')
                out.append(f'<text class="a mt" x="{xc_:.1f}" y="{Y(0) - 11:.1f}" text-anchor="middle">'
                           f'equal at {cr["r_over_E"]:.2f}E</text>')
        if ri == 0:
            out.append(f'<text class="a" x="{left}" y="{y0 + ph + 48}">Below the dotted line, patrolling does better.</text>')
    yb = top + 2 * ph + gy + 48
    out.append(f'<text class="k" x="{left + pw + gx / 2:.1f}" y="{yb}" text-anchor="middle">'
               f'recognition range r (E = earshot = 4 real units; levels in eighths of E)</text>')
    out.append(f'<text class="n" x="{left - 80}" y="{yb + 30}">Bazaar engine {ENGINE_VERSION}, default detection. '
               f'Solid: k = 2, mean over {n_seeds} paired seeds, bars 95% t-interval. Dashed: k = 1 comparator '
               f'(means only), whisper ½E.</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def report(meta: dict, res: dict | None, gate: dict, geo: dict, svg_name: str) -> str:
    L = ["# Grid refinement and the warning-margin test", "",
         "Part B of the decomposition / grid-refinement / entry-exit spec (2026-11-05).", "",
         "## Run record", "",
         f"- Engine `{meta['engine_version']}`; commit `{meta['git']['commit']}`; uncommitted at run time: "
         f"{meta['git']['status_porcelain'] or 'none'}",
         f"- Script sha256 `{meta['script_sha256']}`",
         f"- Command: `{meta['command']}`",
         f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
         f"- {meta['n_runs']} runs on {meta['workers']} workers; wall clock {meta['wall_clock_s'] / 60:.1f} min; "
         f"load average {meta['load_at_start']} at start, {meta['load_at_end']} at end",
         f"- Seeds {meta['seeds'][0]}-{meta['seeds'][-1]}, paired; bootstrap {meta['n_boot']:,} resamples, "
         f"`default_rng({meta['boot_seed']})`", "",
         "## Design (prespecified)", "",
         "- Grid scale k = 2 (`market.scale=2`): cells and ticks half as large, real speeds unchanged; every distance "
         "and time parameter scaled (list in `docs/config_reference.md`). Buyer actions hold a buyer k ticks and rule "
         "sellers' yell and whisper cooldowns scale with k (decided 2026-11-05).",
         "- Adaptive sellers (`rule_deceptive_adaptive`), 2 uniformed inspectors on posts or patrolling, recognition "
         "range r/E in eighths 0 … 1, whisper range ½E (default, 2 units) or ¾E (3 units): 36 conditions.",
         "- PB1 cells: naive sellers (`rule_deceptive`), posts vs patrolling, 2 inspectors, k = 2: 2 conditions.",
         "- k = 1 comparator (exploratory, for PB3): the adaptive dose cells at whisper ½E: 18 conditions.",
         "- Crossover: the interpolated r/E at which patrolling − posts first stops favouring patrolling. "
         "Intervals: 95% paired t over seeds unless marked bootstrap; unadjusted. Confirmatory: PB1 (two outcomes), "
         "PB2 (one test).", "",
         "## Gate", ""]
    ee, nu, km = gate["equal_effort"], gate["no_uniform_at_r0"], gate["k1_matches_recognition_sweep"]
    L += [f"- Equal effort: **{'passed' if ee['passed'] else 'FAILED'}**: dedicated inspector-active ticks = "
          f"{ee['want_k2']} in every k = 2 run and {ee['want_k1']} in every k = 1 run" +
          ("" if ee["passed"] else f"; violations: {ee['violations'][:5]}"),
          f"- No uniform at r = 0: **{'passed' if nu['passed'] else 'FAILED'}**: {nu['rows_with_uniform_true']} of "
          f"{nu['passerby_rows']:,} seller passer-by rows show a uniform (seed {nu['seed']}, k = 2, both placements and "
          f"whisper ranges; {nu['rows_of_uniformed_inspectors']:,} rows were uniformed inspectors)",
          f"- k = 1 comparator equals the committed recognition sweep at the five shared levels: "
          f"**{'passed' if km['passed'] else 'FAILED'}** ({km['values_compared']:,} values, {km['n_mismatches']} mismatches)",
          ""]
    if res is None:
        L += ["**Gate failed: results not reported.**", ""]
        return "\n".join(L)
    pb1 = res["pb1"]
    L += ["## PB1 (confirmatory): the placement result at k = 2", "",
          "Naive sellers, 2 inspectors, k = 2. Patrolling − posts; prediction: below 0 for both outcomes.", ""]
    L += _t(["Outcome", "Posts", "Patrolling", "Patrolling − posts", "Verdict"],
            [[m, _c(m, res["per_condition"][cname(2, "posts", "w50", None)][m], False),
              _c(m, res["per_condition"][cname(2, "patrolling", "w50", None)][m], False),
              _c(m, pb1["diff"][m]), pb1["verdict"].get(m, "(secondary)")]
             for m in PRIMARY + ["catches", "reachable.task_complete_share"]])
    p = res["pb2"]
    L += ["", "## PB2 (confirmatory): does the crossover move with the whisper range?", "",
          f"- Shortfall crossover at whisper ½E: **{p['crossover_w50']['r_over_E']:.3f}E**"
          if p["crossover_w50"]["kind"] == "cross" else f"- Shortfall at whisper ½E: {p['crossover_w50']['kind']}",
          f"- Shortfall crossover at whisper ¾E: **{p['crossover_w75']['r_over_E']:.3f}E**"
          if p["crossover_w75"]["kind"] == "cross" else f"- Shortfall at whisper ¾E: {p['crossover_w75']['kind']}",
          f"- Difference (¾E − ½E): **{_x(p['diff'])}**, 95% bootstrap {_ci2(p['boot_ci'])} "
          f"(both curves cross in {p['boot_counts']['both_cross']:,} of {meta['n_boot']:,} resamples)",
          f"- Prediction: interval excludes 0 and contains +0.25. **Verdict: {p['verdict']}.**",
          f"- Exploratory, same difference on deceptive profit: {_x(res['pb2_profit_exploratory']['diff'])}", "",
          "### Crossovers (r/E), all curves", ""]
    rows = []
    for key, cr in sorted(res["crossover"].items()):
        if key.split("|")[2] in PRIMARY + ["catches"]:
            rows.append([key, cr["kind"], "–" if cr["r_over_E"] is None else f"{cr['r_over_E']:.3f}",
                         "–" if not cr["boot_ci"] else f"[{cr['boot_ci'][0]:.3f}, {cr['boot_ci'][1]:.3f}]",
                         f"{cr['boot_share']['cross']:.3f}"])
    L += _t(["Curve (k | whisper | outcome)", "Kind", "Crossover", "95% bootstrap", "Share of resamples crossing"], rows)
    L += ["", "## PB3 (exploratory): smoother dose curves on the finer grid", "",
          f"- Distinct inspector-stall distances within earshot (real units, every cell an inspector can stand on): "
          f"**{geo[1]['n_distinct']} at k = 1, {geo[2]['n_distinct']} at k = 2**. Posts stand at the same "
          f"{len(geo[1]['post_distances'])} distances at both scales ({', '.join(f'{d:.2f}' for d in geo[1]['post_distances'])}): "
          f"refinement adds positions only for moving inspectors and buyers.",
          "- Roughness = largest step between adjacent levels / total variation of the mean curve "
          "(1 = all change in one step; 1/8 = evenly spread).", ""]
    rows = []
    for m in PRIMARY:
        r1, r2, dd = res["roughness"][f"k1|w50|{m}"], res["roughness"][f"k2|w50|{m}"], res["roughness"][f"diff|{m}"]
        rows.append([m, f"{r1['max_step_share']:.3f}", f"{r2['max_step_share']:.3f}",
                     f"{dd['k2_minus_k1']:+.3f} [{dd['boot_ci'][0]:+.3f}, {dd['boot_ci'][1]:+.3f}]"])
    L += _t(["Outcome (whisper ½E)", "k = 1", "k = 2", "k = 2 − k = 1 (95% bootstrap)"], rows)
    L += ["", f"![dose curves]({svg_name})", "", "## Dose tables (patrolling − posts, mean [95% CI])", ""]
    for k, w in ((2, "w50"), (2, "w75"), (1, "w50")):
        L += [f"### k = {k}, whisper {'½E' if w == 'w50' else '¾E'}", ""]
        L += _t(["r/E"] + [m for m in PRIMARY + ["catches"]],
                [[FRAC_LAB[j]] + [_c(m, res["dose"][f"k{k}|{w}|{m}"]["levels"][j]) for m in PRIMARY + ["catches"]]
                 for j in range(len(FRACS))])
        L += [""]
    L += ["### Levels by placement (k = 2)", ""]
    for w in WHISPERS:
        L += _t([f"r/E ({w})", "posts profit", "patrol profit", "posts shortfall", "patrol shortfall",
                 "posts catches", "patrol catches"],
                [[FRAC_LAB[j]] + [_c(m, res["dose"][f"k2|{w}|{m}"][pl][j], False)
                                  for m in PRIMARY + ["catches"] for pl in ("posts", "patrolling")]
                 for j in range(len(FRACS))])
        L += [""]
    L += ["## Flags", ""] + ([f"- {x}" for x in res["flags"]] or ["- none"])
    L += ["", "## Verdicts", "", "VERDICTS_PLACEHOLDER", "", "## Reading (written after the results)", "",
          "READING_PLACEHOLDER", "", "## Caveats", "",
          "- Changing the whisper range also changes whom sellers can whisper to (buyers as well as inspectors), not "
          "only how close an inspector must be to receive a whisper. The PB2 shift mixes both.",
          "CAVEATS_PLACEHOLDER", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0-29")
    ap.add_argument("--out", default="runs/grid_refinement.json")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--n-boot", type=int, default=10_000)
    ap.add_argument("--boot-seed", type=int, default=20261105)
    a = ap.parse_args(argv)
    seeds = parse_seeds(a.seeds)
    with open(__file__, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": sha,
            "command": " ".join([".venv/bin/python -m analysis.grid_refinement", *(argv or sys.argv[1:])]),
            "load_at_start": _load(), "python": platform.python_version(), "numpy": np.__version__,
            "platform": platform.platform(), "workers": a.workers, "seeds": seeds, "n_boot": a.n_boot,
            "boot_seed": a.boot_seed, "conditions": CONDITIONS}
    # k = 2 jobs first (slowest), largest chunks interleaved
    jobs = [(c, s) for c in sorted(CONDITIONS, key=lambda c: -c["k"]) for s in seeds]
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as ex:
        runs = []
        for i, r in enumerate(ex.map(_job, jobs, chunksize=2)):
            runs.append(r)
            if (i + 1) % 60 == 0:
                print(f"{i + 1}/{len(jobs)} runs, {time.time() - t0:.0f} s, load {_load()}", flush=True)
    meta.update(wall_clock_s=time.time() - t0, load_at_end=_load(), n_runs=len(runs))
    v = {c["name"]: {m: [None] * len(seeds) for m in METRICS} for c in CONDITIONS}
    pos = {s: i for i, s in enumerate(seeds)}
    for r in runs:
        for m in METRICS:
            v[r["condition"]][m][pos[r["seed"]]] = r["values"][m]
    gate = _gate(v, seeds)
    geo = {k: distinct_distances(k) for k in (1, 2)}
    res = analyse(v, seeds, a.n_boot, a.boot_seed) if gate["passed"] else None
    base = a.out[:-5]
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "gate": gate, "geometry": {str(k): g for k, g in geo.items()}, "results": res,
                   "runs": runs}, f, indent=1, sort_keys=True)
    with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["policy", "condition", "seed"] + METRICS)
        for r in runs:
            w.writerow([r["policy"], r["condition"], r["seed"]] + [r["values"][m] for m in METRICS])
    svg = base + "_dose.svg"
    if res is not None:
        with open(svg, "w", encoding="utf-8") as f:
            f.write(plot_svg(res, len(seeds)))
    with open(base + "_summary.md", "w", encoding="utf-8") as f:
        f.write(report(meta, res, gate, geo, os.path.basename(svg)))
    print(f"gate passed: {gate['passed']}; wrote {a.out}, {base}.csv, {base}_summary.md" +
          (f", {svg}" if res else ""))
    return 0 if gate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
