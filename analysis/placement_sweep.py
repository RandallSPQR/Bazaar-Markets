"""Inspector placement sweep: the bazaar replication of the M0 pocket result.

Prespecified design (see runs/placement_sweep_summary.md):
  conditions  inspectors.placement in {posts, patrolling, disguised} x inspectors.count in {2, 6},
              plus a no-inspector control (count 0);
  seeds       0-29, the same list in every condition (paired);
  arms        the default bazaar config, and configs/detection_equal.json as a robustness arm.

    .venv/bin/python -m analysis.placement_sweep --out runs/placement_sweep.json

Writes the per-seed values (JSON and CSV) and a Markdown summary next to --out.
This script only reads engine state after a run; it changes nothing in the engine.
"""
from __future__ import annotations

import argparse
import csv
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

ARMS = {"default": None, "detection_equal": "configs/detection_equal.json"}
PLACEMENTS = ["posts", "patrolling", "disguised"]
COUNTS = [2, 6]
CONTROL = ("control", 0, "posts")   # placement is irrelevant with no inspectors
CONDITIONS = [CONTROL] + [(f"{pl}_{n}", n, pl) for n in COUNTS for pl in PLACEMENTS]

PRIMARY = ["shortfall_rate", "task_complete_share", "buyer_surplus_mean_cents", "profit_per_stall.deceptive"]
SECONDARY = ["catches", "deceptive_share_sales_units", "quantity_fulfilled_share", "empty_handed_share",
             "inspector_active_ticks.dedicated"]
DISPLACEMENT = ["stall_ticks_closed", "deceptive_stalls_never_caught", "shortfall_purchases", "never_caught_shortfall_share",
                "displaced_shortfall_purchases", "displaced_deceptive_purchases"]
ALL = PRIMARY + SECONDARY + DISPLACEMENT
CENTS = {"buyer_surplus_mean_cents", "profit_per_stall.deceptive"}
EFFORT_OUTCOMES = PRIMARY + [m for m in SECONDARY if m != "inspector_active_ticks.dedicated"]


def _job(args) -> dict:
    arm, path, name, count, placement, seed = args
    cfg = load(path, [f"inspectors.count={count}", f"inspectors.placement={placement}", f"seed={seed}"],
               mode="bazaar")
    eng = BazaarEngine(cfg)
    out = flatten(eng.run())
    ticks, close = cfg.market.ticks, cfg.pricing.close_ticks
    closed: dict[str, set] = {}
    for ev in eng.catch_events:   # a catch at tick t closes the stall for ticks t+1 .. reopens-1
        closed.setdefault(ev["stall"], set()).update(range(ev["reopens"] - close, min(ev["reopens"], ticks)))
    short_by_stall: dict[str, int] = {}
    dec_by_stall: dict[str, int] = {}
    for x in eng.purchases:
        if x["shortfall"]:
            short_by_stall[x["stall"]] = short_by_stall.get(x["stall"], 0) + 1
        if x["stype"] == "deceptive":
            dec_by_stall[x["stall"]] = dec_by_stall.get(x["stall"], 0) + 1
    row = {m: out.get(m) for m in PRIMARY + SECONDARY}
    row["stall_ticks_closed"] = sum(len(v) for v in closed.values())
    row["shortfall_purchases"] = sum(short_by_stall.values())
    caught_ids = {ev["stall"] for ev in eng.catch_events}
    row["deceptive_stalls_never_caught"] = sum(st.stype == "deceptive" and st.sid not in caught_ids for st in eng.stalls)
    return {"arm": arm, "condition": name, "count": count, "placement": placement, "seed": seed,
            "values": row, "caught_stalls": sorted({ev["stall"] for ev in eng.catch_events}),
            "shortfall_by_stall": short_by_stall, "deceptive_purchases_by_stall": dec_by_stall}


def _displacement(r: dict, ctrl: dict) -> None:
    """Shortfall purchases at stalls this condition never caught, against control.
    The share is 1 in control by construction (nothing is caught there), so the
    paired comparison uses counts at the same stall set: (purchases at the
    never-caught stalls here) - (purchases at those same stalls in control).
    Positive = purchases moved to stalls that escaped inspection."""
    caught = set(r["caught_stalls"])
    sb, sc = r["shortfall_by_stall"], ctrl["shortfall_by_stall"]
    db, dc = r["deceptive_purchases_by_stall"], ctrl["deceptive_purchases_by_stall"]
    total = sum(sb.values())
    never_here = sum(v for k, v in sb.items() if k not in caught)
    v = r["values"]
    v["never_caught_shortfall_share"] = never_here / total if total else None
    v["displaced_shortfall_purchases"] = never_here - sum(n for k, n in sc.items() if k not in caught)
    v["displaced_deceptive_purchases"] = (sum(n for k, n in db.items() if k not in caught)
                                          - sum(n for k, n in dc.items() if k not in caught))


def _git() -> dict:
    def g(*a):
        return subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
    return {"commit": g("rev-parse", "HEAD"), "dirty": bool(g("status", "--porcelain"))}


def _boot_rate(d: np.ndarray, t: np.ndarray, idx: np.ndarray) -> dict:
    """Change per 100 active inspector-ticks: 100 * mean(change) / mean(active ticks),
    with a paired percentile bootstrap over seeds (the same resampled seeds for both)."""
    point = 100 * d.mean() / t.mean()
    bs = 100 * d[idx].mean(1) / t[idx].mean(1)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return {"rate": float(point), "lo": float(lo), "hi": float(hi)}


def analyse(rows: list[dict], seeds: list[int], n_boot: int, boot_seed: int) -> dict:
    res: dict = {}
    for arm in ARMS:
        by = {(r["condition"], r["seed"]): r for r in rows if r["arm"] == arm}
        ctrl_name = CONTROL[0]
        for name, _, _ in CONDITIONS:
            for s in seeds:
                _displacement(by[(name, s)], by[(ctrl_name, s)])
        vals = {name: {m: [by[(name, s)]["values"][m] for s in seeds] for m in ALL} for name, _, _ in CONDITIONS}
        per_cond = {name: {m: mean_ci(vals[name][m]) for m in ALL} for name, _, _ in CONDITIONS}

        contrasts = {}
        for n in COUNTS:   # 2a (confirmatory) and 2b
            for pl, tag in (("patrolling", "2a"), ("disguised", "2b")):
                key = f"{pl}_{n} - posts_{n}"
                contrasts[key] = {"family": tag, "confirmatory": tag == "2a",
                                  "diff": {m: paired_diff(vals[f"posts_{n}"][m], vals[f"{pl}_{n}"][m]) for m in ALL}}
        for name, _, _ in CONDITIONS[1:]:   # 2c
            contrasts[f"{name} - control"] = {"family": "2c", "confirmatory": False,
                                              "diff": {m: paired_diff(vals[ctrl_name][m], vals[name][m]) for m in ALL}}

        rng = np.random.default_rng(boot_seed)
        idx = rng.integers(0, len(seeds), size=(n_boot, len(seeds)))
        effort = {}
        for name, _, _ in CONDITIONS[1:]:
            t = np.array(vals[name]["inspector_active_ticks.dedicated"], float)
            effort[name] = {"mean_active_ticks": float(t.mean()), "per_100_active_ticks": {}}
            for m in EFFORT_OUTCOMES:
                a, b = vals[ctrl_name][m], vals[name][m]
                if any(x is None for x in a + b):
                    effort[name]["per_100_active_ticks"][m] = None   # undefined in some seed
                    continue
                effort[name]["per_100_active_ticks"][m] = _boot_rate(np.array(b, float) - np.array(a, float), t, idx)
        res[arm] = {"per_condition": per_cond, "contrasts": contrasts, "effort_adjusted": effort,
                    "per_seed": vals}
    return res


# ------------------------------------------------------------------ report

def _fmt(m: str, x: float | None, signed: bool = False) -> str:
    if x is None:
        return "–"
    if m in CENTS or m == "buyer_surplus_mean_cents":
        x = x / 100
        return f"{x:+.2f}" if signed else f"{x:.2f}"
    if m.endswith("share") or m.endswith("rate") or m in ("shortfall_rate", "deceptive_share_sales_units"):
        return f"{100 * x:+.1f}" if signed else f"{100 * x:.1f}"
    return f"{x:+.1f}" if signed else f"{x:.1f}"


def _cell(m: str, st: dict, signed: bool = False) -> str:
    if st is None or st.get("mean") is None:
        return "–"
    s = _fmt(m, st["mean"], signed)
    if st.get("lo") is not None:
        s += f" [{_fmt(m, st['lo'], signed)}, {_fmt(m, st['hi'], signed)}]"
    return s


def _excl0(st: dict) -> str:
    if not st or st.get("lo") is None:
        return ""
    return " *" if st["lo"] > 0 or st["hi"] < 0 else ""


LABEL = {
    "shortfall_rate": "shortfall rate (%)", "task_complete_share": "task complete (%)",
    "buyer_surplus_mean_cents": "buyer surplus ($/buyer)", "profit_per_stall.deceptive": "deceptive profit ($/stall)",
    "catches": "catches", "deceptive_share_sales_units": "deceptive share of units (%)",
    "quantity_fulfilled_share": "quantity fulfilled (%)", "empty_handed_share": "empty-handed (%)",
    "inspector_active_ticks.dedicated": "active inspector-ticks", "stall_ticks_closed": "stall-ticks closed",
    "deceptive_stalls_never_caught": "deceptive stalls never caught",
    "shortfall_purchases": "shortfall purchases", "never_caught_shortfall_share": "shortfall at never-caught stalls (%)",
    "displaced_shortfall_purchases": "Δ shortfall purchases at never-caught stalls",
    "displaced_deceptive_purchases": "Δ deceptive purchases at never-caught stalls",
}


def _table(head: list[str], rows: list[list[str]]) -> list[str]:
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(r) + " |" for r in rows]


def report(meta: dict, res: dict) -> str:
    L = ["# Inspector placement sweep", "",
         "Bazaar replication of the M0 pocket result. At equal enforcement effort, does inspector",
         "placement change deceptive sellers' and buyers' outcomes?", "",
         "## Run record", "",
         f"- Engine version: `{meta['engine_version']}`",
         f"- Commit: `{meta['git']['commit']}`" + (" (working tree dirty)" if meta['git']['dirty'] else " (clean working tree)"),
         f"- Command: `{meta['command']}`",
         f"- Wall-clock: {meta['wall_clock_s']:.0f} s for {meta['n_runs']} runs on {meta['workers']} workers",
         f"- Seeds: {meta['seeds'][0]}–{meta['seeds'][-1]} ({len(meta['seeds'])}), the same list in every condition",
         f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
         f"- Bootstrap: {meta['n_boot']} resamples of seeds, numpy default_rng({meta['boot_seed']})", "",
         "## Design (prespecified)", "",
         "- Conditions: `inspectors.placement` ∈ {posts, patrolling, disguised} × `inspectors.count` ∈ {2, 6},",
         "  plus a no-inspector control (count 0). Default bazaar config otherwise.",
         "- Robustness arm: the full grid again with `configs/detection_equal.json`",
         "  (flat proximity, every channel weight 1: equal detection given exposure).",
         "- Primary outcomes: shortfall rate, task-complete share, mean buyer surplus (buyers);",
         "  deceptive profit per stall (sellers). The rest are secondary.",
         "- Confirmatory test: **2a, patrolling − posts at count 2 and at count 6**. Everything else is exploratory.",
         "", f"Notation: mean [95% t-interval over {len(meta['seeds'])} seeds]. Money in dollars, shares in percent.",
         "In contrast tables, `*` marks an interval that excludes 0. Intervals are unadjusted;",
         "the confirmatory family has 2 contrasts × 4 primary outcomes.", ""]
    for arm, r in res.items():
        L += [f"## Arm: {arm}", ""]
        pc = r["per_condition"]
        names = [c[0] for c in CONDITIONS]
        for title, ms in (("Primary outcomes by condition", PRIMARY), ("Secondary outcomes by condition", SECONDARY)):
            L += [f"### {title}", ""]
            L += _table(["condition"] + [LABEL[m] for m in ms], [[n] + [_cell(m, pc[n][m]) for m in ms] for n in names])
            L += [""]
        for fam, title in (("2a", "2a. Patrolling − posts (confirmatory)"), ("2b", "2b. Disguised − posts (exploratory)"),
                           ("2c", "2c. Each placement − control (exploratory)")):
            ks = [k for k, v in r["contrasts"].items() if v["family"] == fam]
            for sub, ms in (("primary", PRIMARY), ("secondary", SECONDARY)):
                L += [f"### {title}, {sub} outcomes", ""]
                L += _table(["paired difference"] + [LABEL[m] for m in ms],
                            [[k] + [_cell(m, r["contrasts"][k]["diff"][m], True) + _excl0(r["contrasts"][k]["diff"][m])
                                    for m in ms] for k in ks])
                L += [""]
        L += ["### Effort-adjusted change vs control (descriptive rate, not a causal estimate)", "",
              "Change vs control per 100 active inspector-ticks = 100 × mean(paired change) / mean(active ticks),",
              "with a paired percentile bootstrap 95% CI. Units as above (dollars, percentage points, catches).", ""]
        ef = r["effort_adjusted"]
        L += _table(["condition", "mean active ticks"] + [LABEL[m] for m in EFFORT_OUTCOMES],
                    [[n, f"{ef[n]['mean_active_ticks']:.0f}"] +
                     [("–" if ef[n]["per_100_active_ticks"][m] is None else
                       f"{_fmt(m, ef[n]['per_100_active_ticks'][m]['rate'], True)} "
                       f"[{_fmt(m, ef[n]['per_100_active_ticks'][m]['lo'], True)}, "
                       f"{_fmt(m, ef[n]['per_100_active_ticks'][m]['hi'], True)}]")
                      for m in EFFORT_OUTCOMES] for n in names[1:]])
        L += ["", "### Displacement check", "",
              "Per condition. \"Never-caught\" stalls are those with no catch in that seed and condition.",
              "Shortfall at never-caught stalls is 100% in control by construction, so the Δ columns compare",
              "purchases at the same never-caught stalls against control in the same seed (paired; positive =",
              "purchases moved to stalls that escaped inspection).", ""]
        dm = ["catches", "stall_ticks_closed", "deceptive_stalls_never_caught", "deceptive_share_sales_units", "shortfall_purchases",
              "never_caught_shortfall_share", "displaced_shortfall_purchases", "displaced_deceptive_purchases"]
        L += _table(["condition"] + [LABEL[m] for m in dm], [[n] + [_cell(m, pc[n][m]) for m in dm] for n in names])
        L += ["", "Trigger for the displacement test (deceptive profit falls vs control while shortfall does not):", ""]
        for n in names[1:]:
            d = r["contrasts"][f"{n} - control"]["diff"]
            p, s = d["profit_per_stall.deceptive"], d["shortfall_rate"]
            trig = p["hi"] is not None and p["hi"] < 0 and not (s["hi"] is not None and s["hi"] < 0)
            L.append(f"- {n}: {'triggered' if trig else 'not triggered'} (Δ deceptive profit "
                     f"{_cell('profit_per_stall.deceptive', p, True)}; Δ shortfall {_cell('shortfall_rate', s, True)}; "
                     f"Δ deceptive purchases at never-caught stalls "
                     f"{_cell('displaced_deceptive_purchases', d['displaced_deceptive_purchases'], True)})")
        L += [""]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", default="0-29")
    ap.add_argument("--out", default="runs/placement_sweep.json")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--boot", type=int, default=10_000)
    ap.add_argument("--boot-seed", type=int, default=20261105)
    args = ap.parse_args(argv)
    seeds = parse_seeds(args.seeds)
    jobs = [(arm, path, name, n, pl, s) for arm, path in ARMS.items() for name, n, pl in CONDITIONS for s in seeds]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as ex:
        rows = list(ex.map(_job, jobs, chunksize=4))
    wall = time.time() - t0
    res = analyse(rows, seeds, args.boot, args.boot_seed)
    meta = {"design": "inspector placement sweep (bazaar replication of the M0 pocket result)",
            "engine_version": ENGINE_VERSION, "git": _git(),
            "command": " ".join([".venv/bin/python -m analysis.placement_sweep"] + (argv if argv is not None else sys.argv[1:])),
            "wall_clock_s": wall, "n_runs": len(jobs), "workers": args.workers, "seeds": seeds,
            "arms": ARMS, "conditions": [{"name": n, "count": c, "placement": p} for n, c, p in CONDITIONS],
            "n_boot": args.boot, "boot_seed": args.boot_seed,
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform()}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": res, "runs": rows}, f, indent=1)
    with open(os.path.splitext(args.out)[0] + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["arm", "condition", "count", "placement", "seed"] + ALL)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in ("arm", "condition", "count", "placement", "seed")} | r["values"])
    with open(os.path.splitext(args.out)[0] + "_summary.md", "w", encoding="utf-8") as f:
        f.write(report(meta, res))
    print(f"wrote {args.out} (+ .csv, _summary.md) in {wall:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
