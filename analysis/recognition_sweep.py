"""Recognition-range dose-response, with equal-effort disguised inspectors.

Prespecified design (2026-11-05; see runs/recognition_sweep_summary.md). E = market.earshot.
  adaptive sellers (rule_deceptive_adaptive):
      posts and patrolling, uniformed, recognition r in {0, .25E, .5E, .75E, E} x count {2, 6}  (20)
      disguised, full_shift x count                                                               (2)
      control (count 0)                                                                           (1)
  naive sellers (rule_deceptive; they ignore uniforms, so r = E only):
      posts and patrolling, uniformed, r = E x count (4); disguised full_shift x count (2); control (1)
  30 conditions x seeds 0-29, paired; default detection.

    .venv/bin/python -m analysis.recognition_sweep --out runs/recognition_sweep.json

Gate first: equal dedicated inspector-active ticks for every placement at each count; adaptive
r = E cells equal to the committed c7cf7fe values; no "uniform": true in any seller observation
at r = 0 (one full seed's logs). If the gate fails, only the gate is reported.

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

from cli.sweep import flatten, parse_seeds
from engine import ENGINE_VERSION
from engine.bazaar import BazaarEngine
from engine.config import load
from engine.jsonlog import JsonlLog
from engine.metrics import mean_ci, paired_diff

POLICIES = {"ad": "rule_deceptive_adaptive", "rd": "rule_deceptive"}
COUNTS = [2, 6]
FRACS = [0.0, 0.25, 0.5, 0.75, 1.0]
TICKS = 240
PRIOR = "runs/visibility_adaptivity.json"   # the committed c7cf7fe run


def rname(pl: str, n: int, f: float) -> str:
    return f"{pl}{n}_r{f:.2f}"


def _conditions() -> list[dict]:
    out = []
    for pk in POLICIES:
        out.append({"policy": pk, "name": "control", "count": 0, "placement": "posts", "frac": None})
        for n in COUNTS:
            for pl in ("posts", "patrolling"):
                for f in (FRACS if pk == "ad" else [1.0]):
                    out.append({"policy": pk, "name": rname(pl, n, f), "count": n, "placement": pl, "frac": f})
            out.append({"policy": pk, "name": f"disguised_fs{n}", "count": n, "placement": "disguised", "frac": None})
    return out


CONDITIONS = _conditions()

PRIMARY = ["profit_per_stall.deceptive", "shortfall_rate"]
SECONDARY = ["reachable.buyer_surplus_mean_cents", "reachable.task_complete_share", "catches",
             "deceptive_share_sales_units", "buyer_surplus_mean_cents", "task_complete_share",
             "inspector_active_ticks.dedicated"]
DIAG = ["false_claim_impressions_to_uniform_eligible", "false_claims.messages", "unwatched_share_pooled"]
ALL = PRIMARY + SECONDARY + DIAG
DOSE = PRIMARY + ["reachable.buyer_surplus_mean_cents", "reachable.task_complete_share", "catches"]
# +1: a larger (patrolling - posts) means patrolling does better; -1: a smaller one does
ADV_SIGN = {"profit_per_stall.deceptive": -1, "shortfall_rate": -1, "reachable.buyer_surplus_mean_cents": 1,
            "reachable.task_complete_share": 1, "catches": 1}
MONEY = {"profit_per_stall.deceptive", "reachable.buyer_surplus_mean_cents", "buyer_surplus_mean_cents"}
PCT = {"shortfall_rate", "reachable.task_complete_share", "deceptive_share_sales_units", "task_complete_share",
       "unwatched_share_pooled"}
LABEL = {
    "profit_per_stall.deceptive": "deceptive profit ($/stall)", "shortfall_rate": "shortfall rate, all buyers (%)",
    "reachable.buyer_surplus_mean_cents": "buyer surplus, reachable ($)",
    "reachable.task_complete_share": "task complete, reachable (%)", "catches": "catches",
    "deceptive_share_sales_units": "deceptive share of units (%)", "buyer_surplus_mean_cents": "buyer surplus, all ($)",
    "task_complete_share": "task complete, all (%)", "inspector_active_ticks.dedicated": "active inspector-ticks",
    "false_claim_impressions_to_uniform_eligible": "false impressions to post/patrol inspectors",
    "false_claims.messages": "false-claim messages", "unwatched_share_pooled": "false messages, no post/patrol inspector in earshot (%)",
}


def _overrides(c: dict, seed: int) -> list[str]:
    ov = [f"inspectors.count={c['count']}", f"inspectors.placement={c['placement']}",
          f"agents.seller.deceptive={POLICIES[c['policy']]}", f"seed={seed}"]
    if c["placement"] in ("posts", "patrolling") and c["count"]:
        ov += ["inspectors.uniformed=true", f"inspectors.recognition_range={c['frac'] * 4.0}"]
    if c["placement"] == "disguised":
        ov += ["inspectors.disguised_shift=full_shift"]
    return ov


def _job(args) -> dict:
    c, seed = args
    cfg = load(None, _overrides(c, seed), mode="bazaar")
    assert c["frac"] is None or cfg.inspectors.recognition_range == c["frac"] * cfg.market.earshot
    out = flatten(BazaarEngine(cfg).run())
    row = {m: out.get(m) for m in ALL if m in out}
    msgs = out["false_claims.messages"]
    row["unwatched_share_pooled"] = out["false_claims.no_eligible_in_earshot"] / msgs if msgs else None
    return {"policy": c["policy"], "condition": c["name"], "seed": seed, "values": row}


def _git() -> dict:
    def g(*a):
        return subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
    return {"commit": g("rev-parse", "HEAD"), "status_porcelain": g("status", "--porcelain").splitlines()}


# ------------------------------------------------------------------ gate

def _gate(v: dict, seeds: list[int]) -> dict:
    g: dict = {}
    # (a) equal effort
    bad = []
    for c in CONDITIONS:
        if c["count"]:
            want = c["count"] * TICKS
            got = v[c["policy"]][c["name"]]["inspector_active_ticks.dedicated"]
            if any(x != want for x in got):
                bad.append(f"{POLICIES[c['policy']]} / {c['name']}: {sorted(set(got))} (want {want})")
    g["equal_effort"] = {"passed": not bad, "violations": bad}
    # (b) r = E cells against the committed c7cf7fe values
    with open(PRIOR, encoding="utf-8") as f:
        prior = json.load(f)
    pidx = {(r["policy"], r["condition"], r["seed"]): r["values"] for r in prior["runs"]}
    shared = ["profit_per_stall.deceptive", "shortfall_rate", "catches", "reachable.buyer_surplus_mean_cents",
              "reachable.task_complete_share", "deceptive_share_sales_units", "buyer_surplus_mean_cents",
              "task_complete_share", "inspector_active_ticks.dedicated"]
    mism, n_cmp = [], 0
    for pk in POLICIES:
        for n in COUNTS:
            for pl in ("posts", "patrolling"):
                for i, s in enumerate(seeds):
                    old = pidx[(pk, f"{pl}_u{n}", s)]
                    for m in shared:
                        n_cmp += 1
                        if v[pk][rname(pl, n, 1.0)][m][i] != old[m]:
                            mism.append(f"{POLICIES[pk]} / {rname(pl, n, 1.0)} seed {s}: {m}")
    g["matches_c7cf7fe"] = {"passed": not mism, "values_compared": n_cmp, "mismatches": mism[:20],
                            "n_mismatches": len(mism)}
    # (c) r = 0: scan one full seed's seller observations
    rows = trues = uni_rows = 0
    for n in COUNTS:
        for pl in ("posts", "patrolling"):
            c = {"policy": "ad", "name": rname(pl, n, 0.0), "count": n, "placement": pl, "frac": 0.0}
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
    g["no_uniform_at_r0"] = {"passed": trues == 0, "seed": seeds[0], "passerby_rows": rows,
                             "rows_of_uniformed_inspectors": uni_rows, "rows_with_uniform_true": trues}
    g["passed"] = all(g[k]["passed"] for k in ("equal_effort", "matches_c7cf7fe", "no_uniform_at_r0"))
    return g


# ------------------------------------------------------------------ analysis

def _sub(a: list, b: list) -> list:
    return [None if x is None or y is None else y - x for x, y in zip(a, b)]


def _crossing(curve: np.ndarray) -> tuple[str, float | None]:
    """First r/E where the advantage A(r) (positive = patrolling better) stops being positive."""
    if curve[0] <= 0:
        return "never_ahead", None
    for i in range(len(FRACS) - 1):
        a0, a1 = curve[i], curve[i + 1]
        if a0 > 0 >= a1:
            return "cross", FRACS[i] + (FRACS[i + 1] - FRACS[i]) * a0 / (a0 - a1)
    return "always_ahead", None


def analyse(v: dict, seeds: list[int], n_boot: int, boot_seed: int) -> dict:
    res: dict = {"per_condition": {pk: {c["name"]: {m: mean_ci(v[pk][c["name"]][m]) for m in ALL}
                                        for c in CONDITIONS if c["policy"] == pk} for pk in POLICIES}}
    x = np.array(FRACS)
    xc = x - x.mean()
    dose, slopes, cross = {}, {}, {}
    rng = np.random.default_rng(boot_seed)
    idx = rng.integers(0, len(seeds), size=(n_boot, len(seeds)))
    for n in COUNTS:
        for m in DOSE:
            D = np.array([[np.nan if d is None else d for d in
                           _sub(v["ad"][rname("posts", n, f)][m], v["ad"][rname("patrolling", n, f)][m])]
                          for f in FRACS]).T                                   # seeds x levels
            naive = paired_diff(v["rd"][rname("posts", n, 1.0)][m], v["rd"][rname("patrolling", n, 1.0)][m])
            dose[f"{m}|{n}"] = {"levels": [mean_ci(list(D[:, j])) for j in range(len(FRACS))], "naive": naive,
                                "posts": [mean_ci(v["ad"][rname("posts", n, f)][m]) for f in FRACS],
                                "patrolling": [mean_ci(v["ad"][rname("patrolling", n, f)][m]) for f in FRACS]}
            per_seed = (D * xc).sum(1) / (xc ** 2).sum()
            conf = m in PRIMARY
            st = mean_ci(list(per_seed))
            slopes[f"{m}|{n}"] = {"count": n, "outcome": m, "confirmatory": conf, "slope": st,
                                  "per_seed": [float(s) for s in per_seed],
                                  "verdict": (("supported" if st["lo"] > 0 else
                                               "contradicted (interval below 0)" if st["hi"] < 0 else
                                               "not supported (interval includes 0)") if conf else None)}
            s = ADV_SIGN[m]
            kind, val = _crossing(s * D.mean(0))
            kinds, vals = [], []
            for b in range(n_boot):
                k, xv = _crossing(s * D[idx[b]].mean(0))
                kinds.append(k)
                if k == "cross":
                    vals.append(xv)
            cross[f"{m}|{n}"] = {"kind": kind, "r_over_E": val,
                                 "boot_ci": [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]
                                 if vals else None,
                                 "boot_share": {k: kinds.count(k) / n_boot for k in ("cross", "always_ahead", "never_ahead")}}
    # P2: disguised full shift vs uniformed patrolling, full recognition, adaptive sellers
    p2 = {}
    for n in COUNTS:
        for pk in POLICIES:
            for ref in ("patrolling", "posts"):
                p2[f"{pk}|{ref}|{n}"] = {m: paired_diff(v[pk][rname(ref, n, 1.0)][m], v[pk][f"disguised_fs{n}"][m])
                                         for m in DOSE}
    p2_verdict = {}
    for n in COUNTS:
        d = p2[f"ad|patrolling|{n}"]
        ok = all(d[m]["hi"] is not None and d[m]["hi"] < 0 for m in PRIMARY)
        p2_verdict[n] = "supported" if ok else (
            "partly supported" if any(d[m]["hi"] is not None and d[m]["hi"] < 0 for m in PRIMARY) else "not supported")
    # P3: adaptive at r = 0 vs naive, same placement and count (naive is unaffected by r)
    p3 = {f"{pl}|{n}": {m: paired_diff(v["rd"][rname(pl, n, 1.0)][m], v["ad"][rname(pl, n, 0.0)][m])
                        for m in DOSE + ["deceptive_share_sales_units"]}
          for n in COUNTS for pl in ("posts", "patrolling")}
    p3_full = {f"{pl}|{n}": {m: paired_diff(v["rd"][rname(pl, n, 1.0)][m], v["ad"][rname(pl, n, 1.0)][m])
                             for m in DOSE + ["deceptive_share_sales_units"]}
               for n in COUNTS for pl in ("posts", "patrolling")}
    vs_ctrl = {pk: {c["name"]: {m: paired_diff(v[pk]["control"][m], v[pk][c["name"]][m]) for m in DOSE}
                    for c in CONDITIONS if c["policy"] == pk and c["count"]} for pk in POLICIES}
    flags = []
    max_catches = 15 * -(-TICKS // 41)
    for c in CONDITIONS:
        for m in PRIMARY + SECONDARY:
            if m == "inspector_active_ticks.dedicated" or (c["name"] == "control" and m == "catches"):
                continue
            xs = [x for x in v[c["policy"]][c["name"]][m] if x is not None]
            if xs and len(set(xs)) == 1:
                flags.append(f"{POLICIES[c['policy']]} / {c['name']}: {m} = {xs[0]} in every seed")
        cs = v[c["policy"]][c["name"]]["catches"]
        if any(x >= max_catches for x in cs):
            flags.append(f"{POLICIES[c['policy']]} / {c['name']}: catches reach the maximum {max_catches} in "
                         f"{sum(x >= max_catches for x in cs)} seeds")
    res.update(dose=dose, slopes=slopes, crossover=cross, p2=p2, p2_verdict=p2_verdict, p3=p3,
               p3_full_recognition=p3_full, vs_control=vs_ctrl, flags=flags)
    return res


# ------------------------------------------------------------------ formatting

def _f(m, x, signed=False):
    if x is None:
        return "–"
    if m in MONEY:
        x, fmt = x / 100, "{:+.2f}" if signed else "{:.2f}"
    elif m in PCT:
        x, fmt = 100 * x, "{:+.1f}" if signed else "{:.1f}"
    else:
        fmt = "{:+.1f}" if signed else "{:.1f}"
    return fmt.format(x).replace("-", "−")


def _c(m, st, signed=False):
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


def _slope_txt(m, st):
    """Slope per unit r/E, i.e. the change in (patrolling - posts) from r = 0 to r = E."""
    return _c(m, st, True)


# ------------------------------------------------------------------ plot (hand-written SVG)

def plot_svg(res: dict, n_seeds: int) -> str:
    rows = [("profit_per_stall.deceptive", "Deceptive profit per stall", "$", 0.01),
            ("shortfall_rate", "Shortfall rate, all buyers", "pts", 100.0)]
    W, H = 960, 660
    left, top, pw, ph, gx, gy = 110, 150, 330, 165, 80, 95
    serif = '"ET Book", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" '
           f'aria-labelledby="t d">',
           "<style>"
           f".bg{{fill:#fffff8}} .t{{font-family:{serif};fill:#111}} .s{{font-family:{serif};fill:#666}} "
           ".k{font-family:system-ui,-apple-system,sans-serif;fill:#999;font-size:11px} "
           ".n{font-family:system-ui,-apple-system,sans-serif;fill:#aaa;font-size:10.5px} "
           f".a{{font-family:{serif};fill:#333;font-style:italic;font-size:12px}} "
           ".ax{stroke:#ccc;stroke-width:1} .z{stroke:#bbb;stroke-width:1;stroke-dasharray:3 3} "
           ".ln{stroke:#555;stroke-width:1.75;fill:none} .ci{stroke:#555;stroke-width:1.25} .pt{fill:#555} "
           ".nv{stroke:#e41a1c;stroke-width:1.25;stroke-opacity:.55;stroke-dasharray:6 3} .nvt{fill:#e41a1c;fill-opacity:.8} "
           "@media (prefers-color-scheme: dark){.bg{fill:#151515} .t{fill:#ddd} .s{fill:#999} .k{fill:#888} "
           ".n{fill:#666} .a{fill:#bbb} .ax{stroke:#444} .z{stroke:#555} .ln{stroke:#bbb} .ci{stroke:#bbb} "
           ".pt{fill:#bbb} .nv{stroke:#fc8d62} .nvt{fill:#fc8d62}}"
           "</style>",
           f'<rect class="bg" x="0" y="0" width="{W}" height="{H}"/>']
    s2 = {n: res["slopes"][f"profit_per_stall.deceptive|{n}"]["slope"] for n in COUNTS}
    title = "Patrolling’s edge over fixed posts, by how far sellers can recognize a uniform"
    def usd(x):
        return ("+" if x >= 0 else "−") + f"${abs(x) / 100:,.0f}"
    sub = (f"Adaptive sellers, uniformed inspectors. From r = 0 to r = E the deceptive-profit gap moves by "
           f"{usd(s2[2]['mean'])} per stall (2 inspectors) and {usd(s2[6]['mean'])} (6)")
    out += [f'<title id="t">{title}</title>',
            f'<desc id="d">Small multiples: patrolling minus posts at five recognition ranges, with 95% intervals over '
            f'{n_seeds} paired seeds; the table in the summary gives every value.</desc>',
            f'<text class="t" x="{left - 80}" y="40" font-size="20">{title}</text>',
            f'<text class="s" x="{left - 80}" y="64" font-size="14">{sub}</text>']
    for ri, (m, rlabel, unit, k) in enumerate(rows):
        vals = []
        for n in COUNTS:
            d = res["dose"][f"{m}|{n}"]
            vals += [x for st in d["levels"] for x in (st["lo"], st["hi"])] + [d["naive"]["mean"], 0.0]
        lo, hi = min(vals) * k, max(vals) * k
        pad = 0.06 * (hi - lo)
        lo, hi = lo - pad, hi + pad
        y0 = top + ri * (ph + gy)
        out.append(f'<text class="s" x="{left - 80}" y="{y0 - 18}" font-size="14">{rlabel}, patrolling − posts ({unit})</text>')
        for ci, n in enumerate(COUNTS):
            x0 = left + ci * (pw + gx)
            d = res["dose"][f"{m}|{n}"]

            def X(f):
                return x0 + f * pw

            def Y(val):
                return y0 + ph - (val * k - lo) / (hi - lo) * ph
            if ri == 0:
                out.append(f'<text class="t" x="{x0}" y="{top - 56}" font-size="15">{n} inspectors</text>')
            # range-frame axes
            dmin = min(min(st["lo"] for st in d["levels"]), 0.0, d["naive"]["mean"])
            dmax = max(max(st["hi"] for st in d["levels"]), 0.0, d["naive"]["mean"])
            out.append(f'<line class="ax" x1="{x0 - 8}" y1="{Y(dmin):.1f}" x2="{x0 - 8}" y2="{Y(dmax):.1f}"/>')
            out.append(f'<line class="ax" x1="{X(0):.1f}" y1="{y0 + ph + 8}" x2="{X(1):.1f}" y2="{y0 + ph + 8}"/>')
            for f in FRACS:
                lab = {0.0: "0", 0.25: "¼E", 0.5: "½E", 0.75: "¾E", 1.0: "E"}[f]
                out.append(f'<text class="k" x="{X(f):.1f}" y="{y0 + ph + 24}" text-anchor="middle">{lab}</text>')
            # ticks at the data extremes and at 0 (range frame), skipping 0 if it crowds an end
            span = (dmax - dmin) * k
            ticks = [dmin * k, dmax * k] + ([0.0] if min(abs(dmin), abs(dmax)) * k > 0.12 * span else [])
            for tv in ticks:
                txt = "0" if tv == 0 else (f"{tv:+.0f}" if span >= 10 else f"{tv:+.1f}")
                out.append(f'<text class="k" x="{x0 - 13}" y="{Y(tv / k) + 4:.1f}" text-anchor="end">'
                           f'{txt.replace("-", "−")}</text>')
            # reference: zero (patrolling = posts) and naive sellers
            out.append(f'<line class="z" x1="{X(0):.1f}" y1="{Y(0):.1f}" x2="{X(1):.1f}" y2="{Y(0):.1f}"/>')
            yn = Y(d["naive"]["mean"])
            out.append(f'<line class="nv" x1="{X(0):.1f}" y1="{yn:.1f}" x2="{X(1):.1f}" y2="{yn:.1f}"/>')
            if ci == 1:
                out.append(f'<text class="k" x="{X(1) + 6:.1f}" y="{Y(0) + 4:.1f}">equal</text>')
                out.append(f'<text class="k nvt" x="{X(1) + 6:.1f}" y="{yn + 4:.1f}">naive sellers</text>')
            pts = " ".join(f"{X(f):.1f},{Y(st['mean']):.1f}" for f, st in zip(FRACS, d["levels"]))
            out.append(f'<polyline class="ln" points="{pts}"/>')
            for f, st in zip(FRACS, d["levels"]):
                out.append(f'<line class="ci" x1="{X(f):.1f}" y1="{Y(st["lo"]):.1f}" x2="{X(f):.1f}" y2="{Y(st["hi"]):.1f}"/>')
                out.append(f'<circle class="pt" cx="{X(f):.1f}" cy="{Y(st["mean"]):.1f}" r="2.6"/>')
            cr = res["crossover"][f"{m}|{n}"]
            if cr["kind"] == "cross":
                xc_ = X(cr["r_over_E"])
                out.append(f'<line class="ax" x1="{xc_:.1f}" y1="{Y(0) - 6:.1f}" x2="{xc_:.1f}" y2="{Y(0) + 6:.1f}"/>')
                out.append(f'<text class="a" x="{xc_:.1f}" y="{Y(0) - 10:.1f}" text-anchor="middle">'
                           f'equal at {cr["r_over_E"]:.2f}E</text>')
        if ri == 0:
            out.append(f'<text class="a" x="{left}" y="{y0 + ph + 46}">Below the gray “equal” line, '
                       f'patrolling does better.</text>')
    yb = top + 2 * ph + gy + 46
    out.append(f'<text class="k" x="{left + pw + gx / 2:.1f}" y="{yb}" text-anchor="middle">'
               f'recognition range r: how far away a seller recognizes a uniform (E = earshot = 4 cells)</text>')
    out.append(f'<text class="n" x="{left - 80}" y="{yb + 34}">Bazaar engine {ENGINE_VERSION}, default detection. '
               f'Points: mean over {n_seeds} paired seeds; bars: 95% t-interval. Red dashed line: naive '
               f'(rule_deceptive) sellers, who ignore uniforms.</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ report

def report(meta: dict, res: dict, gate: dict, svg_name: str) -> str:
    L = ["# Recognition-range dose-response", "",
         "How far away must a seller recognize a uniform for adaptivity to erase patrolling's advantage?", "",
         "## Run record", "",
         f"- Engine version: `{meta['engine_version']}`",
         f"- Commit: `{meta['git']['commit']}`; uncommitted at run time: "
         + (", ".join(f"`{x.strip()}`" for x in meta["git"]["status_porcelain"]) or "nothing"),
         f"- Run script: `analysis/recognition_sweep.py`, sha256 `{meta['script_sha256'][:16]}…`",
         f"- Command: `{meta['command']}`",
         f"- Wall-clock: {meta['wall_clock_s']:.0f} s for {meta['n_runs']} runs on {meta['workers']} workers; "
         f"load average {meta['load_at_start']:.1f} at start, {meta['load_at_end']:.1f} at end",
         f"- Seeds: {meta['seeds'][0]}–{meta['seeds'][-1]} ({len(meta['seeds'])}), paired across all 30 conditions",
         f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
         f"- Bootstrap: {meta['n_boot']} resamples of seeds, numpy default_rng({meta['boot_seed']})", "",
         "E = market.earshot = 4 cells. Condition names: `posts2_r0.50` = 2 uniformed posts, recognized within 0.5E;",
         "`disguised_fs6` = 6 full-shift disguised inspectors; naive cells use r = E (naive sellers ignore uniforms).",
         "Notation: mean [95% t-interval over seeds]; money in dollars, shares in percent; signed differences;",
         "`*` = interval excludes 0; unadjusted.", ""]
    ee, mc, nu = gate["equal_effort"], gate["matches_c7cf7fe"], gate["no_uniform_at_r0"]
    L += ["## Gate (checked first)", "",
          f"- Equal effort: {'every placement has count × 240 dedicated inspector-active ticks in every seed' if ee['passed'] else 'FAILED: ' + '; '.join(ee['violations'][:5])}.",
          f"- r = E cells against c7cf7fe: {mc['values_compared']} per-seed values compared (adaptive and naive, posts and "
          f"patrolling, both counts, 9 outcomes), {mc['n_mismatches']} mismatches.",
          f"- r = 0, seed {nu['seed']}, full logs of all four adaptive r = 0 cells: {nu['passerby_rows']} passer-by rows, "
          f"{nu['rows_of_uniformed_inspectors']} of them uniformed inspectors, {nu['rows_with_uniform_true']} showing "
          f"`uniform: true`.",
          f"- **Gate {'passed' if gate['passed'] else 'FAILED: nothing else is interpreted'}.**", ""]
    if not gate["passed"]:
        return "\n".join(L) + "\n"

    L += ["## P1 (confirmatory): the patrolling advantage shrinks as recognition range grows", "",
          "Per seed, the OLS slope of D(r) = patrolling − posts on r/E over the five levels (adaptive sellers,",
          "uniformed inspectors). The slope is the change in D from r = 0 to r = E. Predicted > 0 for deceptive profit",
          "and for all-buyer shortfall rate at both counts. The other rows are exploratory; for surplus, task",
          "completion and catches, a shrinking advantage means a slope < 0.", ""]
    rows = []
    for k, e in res["slopes"].items():
        rows.append([str(e["count"]), LABEL[e["outcome"]] + (" **(confirmatory)**" if e["confirmatory"] else ""),
                     _slope_txt(e["outcome"], e["slope"]), e["verdict"] or "exploratory"])
    L += _t(["count", "outcome", "slope (per unit r/E)", "verdict"], rows) + [""]

    L += ["## Dose-response", "", f"![Patrolling minus posts by recognition range]({svg_name})", "",
          "D(r) = patrolling − posts, adaptive sellers, paired over seeds. The last column is the same contrast for naive",
          "sellers (independent of r).", ""]
    for n in COUNTS:
        rows = []
        for m in DOSE:
            d = res["dose"][f"{m}|{n}"]
            rows.append([LABEL[m]] + [_c(m, st, True) for st in d["levels"]] + [_c(m, d["naive"], True)])
        L += [f"**{n} inspectors**", ""]
        L += _t(["outcome"] + [f"r = {f:g}E" for f in FRACS] + ["naive sellers"], rows) + [""]
    L += ["Levels by placement (adaptive sellers):", ""]
    for n in COUNTS:
        rows = []
        for m in PRIMARY:
            d = res["dose"][f"{m}|{n}"]
            for pl in ("posts", "patrolling"):
                rows.append([LABEL[m], pl] + [_c(m, st) for st in d[pl]])
        L += [f"**{n} inspectors**", ""]
        L += _t(["outcome", "placement"] + [f"r = {f:g}E" for f in FRACS], rows) + [""]

    L += ["## Crossover (descriptive)", "",
          "The interpolated r/E at which the mean of D(r) over seeds reaches 0 (patrolling no longer ahead), with a",
          "paired percentile bootstrap CI over seeds. Shares give how often a resample crossed, never crossed",
          "(patrolling ahead at every level) or started at or past 0 (patrolling not ahead even at r = 0).", ""]
    rows = []
    for k, cr in res["crossover"].items():
        m, n = k.split("|")
        point = (f"{cr['r_over_E']:.2f}E" if cr["kind"] == "cross" else
                 "none: ahead at every level" if cr["kind"] == "always_ahead" else "none: not ahead even at r = 0")
        ci = f"[{cr['boot_ci'][0]:.2f}E, {cr['boot_ci'][1]:.2f}E]" if cr["boot_ci"] else "–"
        sh = cr["boot_share"]
        rows.append([n, LABEL[m], point, ci, f"{100 * sh['cross']:.0f}% / {100 * sh['always_ahead']:.0f}% / "
                                               f"{100 * sh['never_ahead']:.0f}%"])
    L += _t(["count", "outcome", "crossover", "bootstrap 95% CI (crossing resamples)",
             "resamples: cross / always ahead / never ahead"], rows) + [""]

    L += ["## P2 (exploratory): equal-effort disguised vs uniformed patrolling, full recognition", "",
          "Disguised full-shift − uniformed patrolling (and − uniformed posts), r = E, paired. Predicted for adaptive",
          "sellers: deceptive profit lower and shortfall lower.", ""]
    rows = []
    for n in COUNTS:
        for pk in POLICIES:
            for ref in ("patrolling", "posts"):
                d = res["p2"][f"{pk}|{ref}|{n}"]
                rows.append([str(n), POLICIES[pk], f"disguised − {ref}"] + [_c(m, d[m], True) for m in DOSE])
    L += _t(["count", "sellers", "contrast"] + [LABEL[m] for m in DOSE], rows) + [""]
    L += [f"Verdict: count 2 {res['p2_verdict'][2]}; count 6 {res['p2_verdict'][6]}.", ""]

    L += ["## P3 (exploratory): catch notices alone", "",
          "Adaptive sellers at r = 0 can respond only to public catch notices and their own reopening.",
          "Adaptive (r = 0) − naive, same placement and count, paired. For comparison, the same contrast at r = E.", ""]
    rows = []
    for n in COUNTS:
        for pl in ("posts", "patrolling"):
            for lab, src in (("r = 0", res["p3"]), ("r = E", res["p3_full_recognition"])):
                d = src[f"{pl}|{n}"]
                rows.append([str(n), pl, lab] + [_c(m, d[m], True) for m in DOSE + ["deceptive_share_sales_units"]])
    L += _t(["count", "placement", "recognition"] + [LABEL[m] for m in DOSE + ["deceptive_share_sales_units"]], rows) + [""]

    L += ["## Outcomes by condition", ""]
    for title, ms in (("Primary and buyer outcomes", PRIMARY + ["reachable.buyer_surplus_mean_cents",
                                                                 "reachable.task_complete_share"]),
                      ("Enforcement and diagnostics", ["catches", "deceptive_share_sales_units",
                                                       "inspector_active_ticks.dedicated",
                                                       "false_claim_impressions_to_uniform_eligible",
                                                       "unwatched_share_pooled"])):
        L += [f"### {title}", ""]
        rows = [[POLICIES[c["policy"]], c["name"]] + [_c(m, res["per_condition"][c["policy"]][c["name"]][m]) for m in ms]
                for c in CONDITIONS]
        L += _t(["sellers", "condition"] + [LABEL[m] for m in ms], rows) + [""]

    L += ["## Each condition − control, within policy (paired, exploratory)", ""]
    rows = [[POLICIES[pk], name] + [_c(m, st, True) for m, st in d.items()]
            for pk in POLICIES for name, d in res["vs_control"][pk].items()]
    L += _t(["sellers", "condition"] + [LABEL[m] for m in DOSE], rows) + [""]

    L += ["## Ceiling and floor flags", "",
          "Automatic: any primary or secondary outcome constant across all seeds in a condition, and any condition",
          "whose catch count reaches its maximum (15 deceptive stalls × 6 catches in 240 ticks).", ""]
    L += [f"- {x}" for x in res["flags"]] or ["- none"]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", default="0-29")
    ap.add_argument("--out", default="runs/recognition_sweep.json")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--boot", type=int, default=10_000)
    ap.add_argument("--boot-seed", type=int, default=20261105)
    args = ap.parse_args(argv)
    seeds = parse_seeds(args.seeds)
    jobs = [(c, s) for c in CONDITIONS for s in seeds]
    load0 = os.getloadavg()[0]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as ex:
        rows = list(ex.map(_job, jobs, chunksize=4))
    wall = time.time() - t0
    by = {(r["policy"], r["condition"], r["seed"]): r["values"] for r in rows}
    v = {pk: {c["name"]: {m: [by[(pk, c["name"], s)].get(m) for s in seeds] for m in ALL}
              for c in CONDITIONS if c["policy"] == pk} for pk in POLICIES}
    gate = _gate(v, seeds)
    res = analyse(v, seeds, args.boot, args.boot_seed) if gate["passed"] else {}
    with open(__file__, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    meta = {"design": "recognition-range dose-response with equal-effort disguised inspectors",
            "engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": sha,
            "command": " ".join([".venv/bin/python -m analysis.recognition_sweep"] +
                                (argv if argv is not None else sys.argv[1:])),
            "wall_clock_s": wall, "load_at_start": load0, "load_at_end": os.getloadavg()[0],
            "n_runs": len(jobs), "workers": args.workers, "seeds": seeds, "policies": POLICIES,
            "recognition_fracs": FRACS, "earshot": 4.0, "conditions": CONDITIONS,
            "n_boot": args.boot, "boot_seed": args.boot_seed,
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform()}
    base = os.path.splitext(args.out)[0]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "gate": gate, "results": res, "runs": rows}, f, indent=1)
    with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["policy", "condition", "seed"] + ALL)
        w.writeheader()
        for r in rows:
            w.writerow({"policy": POLICIES[r["policy"]], "condition": r["condition"], "seed": r["seed"]} | r["values"])
    svg_name = os.path.basename(base) + "_dose.svg"
    if gate["passed"]:
        with open(base + "_dose.svg", "w", encoding="utf-8") as f:
            f.write(plot_svg(res, len(seeds)))
    with open(base + "_summary.md", "w", encoding="utf-8") as f:
        f.write(report(meta, res, gate, svg_name))
    print(f"gate {'passed' if gate['passed'] else 'FAILED'}; wrote {args.out} (+ .csv, _summary.md"
          f"{', _dose.svg' if gate['passed'] else ''}) in {wall:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
