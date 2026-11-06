"""Part A: where does the adaptive sellers' extra profit come from?

Prespecified (2026-11-05). Source design: runs/recognition_sweep.json (engine 0.4.0, commit
463af5d). For each placement x count, compare adaptive sellers (rule_deceptive_adaptive) at
recognition range r = 0, so that they react to catch notices only, with naive sellers
(rule_deceptive). Disguised full-shift inspectors never wear a uniform, so the adaptive cell
there is "catch notices only" by construction and is included as the third placement.

The committed sweep stored only profit per stall, not its parts, so this script re-runs the
same 12 cells x 30 seeds with the same engine and checks every stored value it can against
recognition_sweep.json before using the new fields. No engine change.

Decomposition, per deceptive stall and per seed (integer cents, so it is exact):
    profit = revenue - unit cost - ad spend - penalties
    d profit = d revenue - d unit cost - d ad spend - d penalties      (adaptive - naive)
Paired t-intervals over 30 seeds; unadjusted; descriptive.
Prediction (descriptive): more than half of d profit comes from lower penalties,
i.e. share = (-d penalties) / d profit > 0.5. Share = ratio of the mean parts; a paired
percentile bootstrap over seeds (10,000 resamples, default_rng(20261105)) gives its interval.

    .venv/bin/python -m analysis.profit_decomposition --out runs/profit_decomposition.json
"""
from __future__ import annotations

import argparse
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
from engine.metrics import mean_ci, paired_diff

SOURCE = "runs/recognition_sweep.json"
POLICIES = {"ad": "rule_deceptive_adaptive", "rd": "rule_deceptive"}
CELLS = [(pl, n) for pl in ("posts", "patrolling", "disguised") for n in (2, 6)]
PARTS = ["revenue", "unit_cost", "ad_spend", "penalties"]
EXTRA = ["false_impressions", "catches"]
CHECK = ["profit_per_stall.deceptive", "shortfall_rate", "catches", "false_claims.messages",
         "deceptive_share_sales_units", "inspector_active_ticks.dedicated"]


def source_name(pk: str, pl: str, n: int) -> str:
    """Condition name of the matching cell in recognition_sweep.json. Naive sellers ignore
    uniforms, so the sweep ran them at r = E only; their outcome is the same at every r."""
    if pl == "disguised":
        return f"disguised_fs{n}"
    return f"{pl}{n}_r{0.0 if pk == 'ad' else 1.0:.2f}"


def _overrides(pk: str, pl: str, n: int, seed: int) -> list[str]:
    ov = [f"inspectors.count={n}", f"inspectors.placement={pl}",
          f"agents.seller.deceptive={POLICIES[pk]}", f"seed={seed}"]
    if pl == "disguised":
        ov.append("inspectors.disguised_shift=full_shift")
    else:
        ov += ["inspectors.uniformed=true", f"inspectors.recognition_range={0.0 if pk == 'ad' else 4.0}"]
    return ov


def _job(args) -> dict:
    pk, pl, n, seed = args
    out = BazaarEngine(load(None, _overrides(pk, pl, n, seed), mode="bazaar")).run()
    d = out["seller_by_type"]["deceptive"]
    k = d["stalls"]
    flat = flatten(out)
    vals = {"revenue": d["revenue_cents"] / k, "unit_cost": d["cost_cents"] / k,
            "ad_spend": d["ad_spend_cents"] / k, "penalties": d["penalties_cents"] / k,
            "profit": d["profit_per_stall_cents"],
            "false_impressions": out["false_claim_impressions"] / k, "catches": d["catches"] / k,
            "units": d["units_sold"] / k, "stalls": k}
    assert d["revenue_cents"] - d["cost_cents"] - d["ad_spend_cents"] - d["penalties_cents"] == d["profit_cents"]
    return {"policy": pk, "placement": pl, "count": n, "seed": seed, "values": vals,
            "check": {m: flat.get(m) for m in CHECK}}


def _git() -> dict:
    def g(*a):
        return subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
    return {"commit": g("rev-parse", "HEAD"), "status_porcelain": g("status", "--porcelain").splitlines()}


def _load_avg() -> list[float]:
    return [round(x, 2) for x in os.getloadavg()]


def gate(runs: list[dict]) -> dict:
    with open(SOURCE, encoding="utf-8") as f:
        src = json.load(f)
    idx = {(r["policy"], r["condition"], r["seed"]): r["values"] for r in src["runs"]}
    n_cmp, mism = 0, []
    for r in runs:
        old = idx[(r["policy"], source_name(r["policy"], r["placement"], r["count"]), r["seed"])]
        for m in CHECK:
            if m in old:
                n_cmp += 1
                if old[m] != r["check"][m]:
                    mism.append(f"{r['policy']} {r['placement']}{r['count']} seed {r['seed']}: {m}")
    return {"matches_recognition_sweep": {"passed": not mism, "values_compared": n_cmp,
                                          "n_mismatches": len(mism), "mismatches": mism[:20]},
            "passed": not mism}


def analyse(runs: list[dict], seeds: list[int], n_boot: int, boot_seed: int) -> dict:
    v: dict = {}
    for r in runs:
        v.setdefault((r["policy"], r["placement"], r["count"]), {})[r["seed"]] = r["values"]
    rng = np.random.default_rng(boot_seed)
    boot_idx = rng.integers(0, len(seeds), size=(n_boot, len(seeds)))   # same resamples for every cell
    out = {}
    for pl, n in CELLS:
        a = [v[("ad", pl, n)][s] for s in seeds]
        b = [v[("rd", pl, n)][s] for s in seeds]
        cell: dict = {"naive": {}, "adaptive": {}, "diff": {}}
        for m in ["profit"] + PARTS + EXTRA + ["units"]:
            xa, xb = [x[m] for x in a], [x[m] for x in b]
            cell["naive"][m] = mean_ci(xb)
            cell["adaptive"][m] = mean_ci(xa)
            cell["diff"][m] = paired_diff(xb, xa)          # adaptive - naive
        # contributions to d profit: + d revenue, - d unit cost, - d ad spend, - d penalties
        dp = np.array([x["profit"] - y["profit"] for x, y in zip(a, b)])
        contrib = {"revenue": np.array([x["revenue"] - y["revenue"] for x, y in zip(a, b)]),
                   "unit_cost": -np.array([x["unit_cost"] - y["unit_cost"] for x, y in zip(a, b)]),
                   "ad_spend": -np.array([x["ad_spend"] - y["ad_spend"] for x, y in zip(a, b)]),
                   "penalties": -np.array([x["penalties"] - y["penalties"] for x, y in zip(a, b)])}
        assert np.allclose(sum(contrib.values()), dp)
        cell["contribution"] = {m: mean_ci(list(c)) for m, c in contrib.items()}
        mdp = float(dp.mean())
        shares = {}
        for m, c in contrib.items():
            pt = float(c.mean()) / mdp if mdp else None
            bs = c[boot_idx].mean(1) / dp[boot_idx].mean(1)
            lo, hi = (float(x) for x in np.percentile(bs, [2.5, 97.5]))
            shares[m] = {"share": pt, "lo": lo, "hi": hi}
        cell["share_of_d_profit"] = shares
        cell["prediction_penalty_share_gt_half"] = (shares["penalties"]["share"] is not None
                                                    and shares["penalties"]["share"] > 0.5)
        out[f"{pl}{n}"] = cell
    return out


def _usd(c, signed=False):
    if c is None:
        return "-"
    s = f"{c / 100:+,.0f}" if signed else f"{c / 100:,.0f}"
    return "$" + s if not signed else ("+$" + s[1:] if s[0] == "+" else "-$" + s[1:])


def _ci(st, f=_usd, signed=True):
    if st["mean"] is None:
        return "-"
    return f"{f(st['mean'], signed)} [{f(st['lo'], signed)}, {f(st['hi'], signed)}]"


def _num(x, signed=False):
    return f"{x:+.2f}" if signed else f"{x:.2f}"


def report(meta: dict, res: dict, g: dict) -> str:
    L = ["# Profit decomposition: adaptive (catch notices only) vs naive deceptive sellers", "",
         "Part A of the decomposition / grid-refinement / entry-exit spec (2026-11-05). Analysis only; "
         f"engine {meta['engine_version']}, commit `{meta['git']['commit'][:7]}`.", "",
         "## Design (prespecified)", "",
         "- Source: `runs/recognition_sweep.json` (commit 463af5d). Cells: posts, patrolling and "
         "disguised full-shift inspectors x count {2, 6}.",
         "- Adaptive sellers (`rule_deceptive_adaptive`) at recognition range r = 0 react to public catch "
         "notices (and their own reopening) only. Disguised inspectors never wear a uniform, so that cell is "
         "catch-notices-only by construction. Naive sellers (`rule_deceptive`) ignore uniforms and notices.",
         "- The sweep stored profit per stall but not its parts, so the 12 cells x 30 seeds were re-run with the "
         "same engine; every stored value was checked first (gate below).",
         "- Per deceptive stall: profit = revenue - unit cost - ad spend - penalties (integer cents, exact). "
         "Differences are adaptive - naive, paired over seeds 0-29, 95% t-intervals, unadjusted.",
         "- Prediction (descriptive): more than half of the profit difference comes from lower penalties. "
         "Share = mean contribution / mean profit difference; interval: paired percentile bootstrap over seeds "
         f"({meta['n_boot']:,} resamples, `default_rng({meta['boot_seed']})`).", "",
         "## Gate", "",
         f"- Re-run values match `recognition_sweep.json`: **{'passed' if g['passed'] else 'FAILED'}** "
         f"({g['matches_recognition_sweep']['values_compared']:,} values compared, "
         f"{g['matches_recognition_sweep']['n_mismatches']} mismatches).", ""]
    if not g["passed"]:
        L += ["Gate failed: no results reported.", ""]
        return "\n".join(L)
    L += ["## Results", "",
          "### Profit difference and its parts ($ per deceptive stall, adaptive - naive)", "",
          "Contribution = the part's effect on profit: + revenue, - unit cost, - ad spend, - penalties.", "",
          "| Cell | Naive profit | Adaptive profit | d profit | Revenue | Unit cost | Ad spend | Penalties |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for key, c in res.items():
        L.append(f"| {key} | {_usd(c['naive']['profit']['mean'])} | {_usd(c['adaptive']['profit']['mean'])} | "
                 f"{_ci(c['diff']['profit'])} | " +
                 " | ".join(_ci(c["contribution"][m]) for m in PARTS) + " |")
    L += ["", "### Share of the profit difference from each part (point [95% bootstrap])", "",
          "| Cell | Revenue | Unit cost | Ad spend | Penalties | > half from penalties? |",
          "|---|---:|---:|---:|---:|:---:|"]
    for key, c in res.items():
        sh = c["share_of_d_profit"]
        cells = [f"{sh[m]['share']:.2f} [{sh[m]['lo']:.2f}, {sh[m]['hi']:.2f}]" for m in PARTS]
        L.append(f"| {key} | " + " | ".join(cells) + f" | {'yes' if c['prediction_penalty_share_gt_half'] else 'no'} |")
    L += ["", "### Raw levels per deceptive stall (mean over seeds)", "",
          "| Cell | Policy | Revenue | Unit cost | Ad spend | Penalties | Units | False impressions | Catches |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for key, c in res.items():
        for pol in ("naive", "adaptive"):
            x = c[pol]
            L.append(f"| {key} | {pol} | " + " | ".join(_usd(x[m]["mean"]) for m in PARTS) +
                     f" | {x['units']['mean']:.1f} | {x['false_impressions']['mean']:.1f} | {x['catches']['mean']:.2f} |")
    L += ["", "### False-claim impressions and catches per deceptive stall (adaptive - naive)", "",
          "| Cell | False impressions | Catches |", "|---|---:|---:|"]
    for key, c in res.items():
        fi, ca = c["diff"]["false_impressions"], c["diff"]["catches"]
        L.append(f"| {key} | {fi['mean']:+.1f} [{fi['lo']:+.1f}, {fi['hi']:+.1f}] | "
                 f"{ca['mean']:+.2f} [{ca['lo']:+.2f}, {ca['hi']:+.2f}] |")
    L += ["", "## Verdict", "", "VERDICT_PLACEHOLDER", "", "## Reading (written after the results)", "",
          "READING_PLACEHOLDER", "", "## Run record", "",
          f"- Command: `{meta['command']}`",
          f"- Engine {meta['engine_version']}; commit `{meta['git']['commit']}`; working tree clean: "
          f"{not meta['git']['status_porcelain']}",
          f"- Script sha256 `{meta['script_sha256']}`",
          f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
          f"- {meta['n_runs']} runs on {meta['workers']} workers, wall clock {meta['wall_clock_s']:.0f} s; "
          f"load average {meta['load_at_start']} at start, {meta['load_at_end']} at end", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0-29")
    ap.add_argument("--out", default="runs/profit_decomposition.json")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--n-boot", type=int, default=10_000)
    ap.add_argument("--boot-seed", type=int, default=20261105)
    a = ap.parse_args(argv)
    seeds = parse_seeds(a.seeds)
    with open(__file__, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": sha,
            "command": " ".join([".venv/bin/python -m analysis.profit_decomposition", *(argv or sys.argv[1:])]),
            "load_at_start": _load_avg(), "python": platform.python_version(), "numpy": np.__version__,
            "platform": platform.platform(), "workers": a.workers, "seeds": seeds,
            "n_boot": a.n_boot, "boot_seed": a.boot_seed, "source": SOURCE}
    jobs = [(pk, pl, n, s) for pl, n in CELLS for pk in POLICIES for s in seeds]
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as ex:
        runs = list(ex.map(_job, jobs, chunksize=4))
    meta.update(wall_clock_s=time.time() - t0, load_at_end=_load_avg(), n_runs=len(runs))
    g = gate(runs)
    res = analyse(runs, seeds, a.n_boot, a.boot_seed) if g["passed"] else None
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "gate": g, "results": res, "runs": runs}, f, indent=1, sort_keys=True)
    md = a.out.replace(".json", ".md")
    with open(md, "w", encoding="utf-8") as f:
        f.write(report(meta, res, g))
    print(f"gate passed: {g['passed']}; wrote {a.out} and {md}")
    return 0 if g["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
