"""Visibility x seller adaptivity: does strategic avoidance erode the patrol advantage?

Prespecified design (2026-11-05; see runs/visibility_adaptivity_summary.md):
  seller policy  {rule_deceptive, rule_deceptive_adaptive} for deceptive stalls
  x conditions   control (no inspectors);
                 posts and patrolling x uniformed {false, true} x count {2, 6};
                 disguised x count {2, 6}
  = 2 x 11 = 22 conditions, seeds 0-29 paired across all, default detection.

    .venv/bin/python -m analysis.visibility_adaptivity --out runs/visibility_adaptivity.json

Positive-control gate first: with adaptive sellers and 2 uniformed posts, the share of
false-claim impressions perceived by uniformed inspectors must be 0 in every seed, and
catches must be lower than with rule_deceptive (paired CI below 0). If the gate fails,
only the gate is reported.

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
from engine.metrics import mean_ci, paired_diff

POLICIES = {"rd": "rule_deceptive", "ad": "rule_deceptive_adaptive"}
COUNTS = [2, 6]


def _conditions() -> list[tuple[str, int, str, bool]]:
    out = [("control", 0, "posts", False)]
    for n in COUNTS:
        for pl in ("posts", "patrolling"):
            for u in (False, True):
                out.append((f"{pl}_{'u' if u else 'n'}{n}", n, pl, u))
        out.append((f"disguised_{n}", n, "disguised", False))
    return out


CONDITIONS = _conditions()
NAMES = [c[0] for c in CONDITIONS]

PRIMARY = ["reachable.shortfall_rate", "reachable.task_complete_share", "reachable.buyer_surplus_mean_cents",
           "profit_per_stall.deceptive"]
SECONDARY = ["shortfall_rate", "task_complete_share", "buyer_surplus_mean_cents", "catches",
             "deceptive_share_sales_units", "quantity_fulfilled_share", "empty_handed_share",
             "inspector_active_ticks.dedicated", "reachable.share"]
DIAG = ["false_claim_impressions", "false_claim_impressions_to_uniform_eligible", "false_share_to_eligible",
        "false_claims.messages", "false_claims.no_eligible_in_earshot", "unwatched_share_pooled",
        "unwatched_share_stall_mean", "stalls_always_unwatched_share"]
ALL = PRIMARY + SECONDARY + DIAG
MONEY = {"reachable.buyer_surplus_mean_cents", "profit_per_stall.deceptive", "buyer_surplus_mean_cents"}
PCT = {"reachable.shortfall_rate", "reachable.task_complete_share", "shortfall_rate", "task_complete_share",
       "deceptive_share_sales_units", "quantity_fulfilled_share", "empty_handed_share", "reachable.share",
       "false_share_to_eligible", "unwatched_share_pooled", "unwatched_share_stall_mean",
       "stalls_always_unwatched_share"}
LABEL = {
    "reachable.shortfall_rate": "shortfall rate, reachable (%)",
    "reachable.task_complete_share": "task complete, reachable (%)",
    "reachable.buyer_surplus_mean_cents": "buyer surplus, reachable ($)",
    "profit_per_stall.deceptive": "deceptive profit ($/stall)",
    "shortfall_rate": "shortfall rate, all (%)", "task_complete_share": "task complete, all (%)",
    "buyer_surplus_mean_cents": "buyer surplus, all ($)", "catches": "catches",
    "deceptive_share_sales_units": "deceptive share of units (%)", "quantity_fulfilled_share": "quantity fulfilled (%)",
    "empty_handed_share": "empty-handed (%)", "inspector_active_ticks.dedicated": "active inspector-ticks",
    "reachable.share": "reachable buyers (%)",
    "false_claim_impressions": "false-claim impressions",
    "false_claim_impressions_to_uniform_eligible": "false impressions to post/patrol inspectors",
    "false_share_to_eligible": "share of false impressions to post/patrol inspectors (%)",
    "false_claims.messages": "false-claim messages",
    "false_claims.no_eligible_in_earshot": "false messages, no post/patrol inspector in earshot",
    "unwatched_share_pooled": "false messages unwatched, pooled (%)",
    "unwatched_share_stall_mean": "false messages unwatched, mean over stalls (%)",
    "stalls_always_unwatched_share": "stalls whose false messages were all unwatched (%)",
}


def _job(args) -> dict:
    pk, cname, count, placement, uniformed, seed = args
    cfg = load(None, [f"inspectors.count={count}", f"inspectors.placement={placement}",
                      f"inspectors.uniformed={'true' if uniformed else 'false'}",
                      f"agents.seller.deceptive={POLICIES[pk]}", f"seed={seed}"], mode="bazaar")
    out = flatten(BazaarEngine(cfg).run())
    row = {m: out.get(m) for m in PRIMARY + SECONDARY + DIAG if m in out}
    fi, fe = out["false_claim_impressions"], out["false_claim_impressions_to_uniform_eligible"]
    row["false_share_to_eligible"] = fe / fi if fi else None
    by = out["false_claims_by_stall"]
    msgs = out["false_claims.messages"]
    row["unwatched_share_pooled"] = out["false_claims.no_eligible_in_earshot"] / msgs if msgs else None
    shares = [v["no_eligible_in_earshot"] / v["messages"] for v in by.values() if v["messages"]]
    row["unwatched_share_stall_mean"] = float(np.mean(shares)) if shares else None
    row["stalls_always_unwatched_share"] = float(np.mean([s == 1.0 for s in shares])) if shares else None
    return {"policy": pk, "condition": cname, "count": count, "placement": placement, "uniformed": uniformed,
            "seed": seed, "values": row, "false_claims_by_stall": by}


def _git() -> dict:
    def g(*a):
        return subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
    return {"commit": g("rev-parse", "HEAD"), "status_porcelain": g("status", "--porcelain").splitlines()}


def _boot_rate(d: np.ndarray, t: np.ndarray, idx: np.ndarray) -> dict:
    point = 100 * d.mean() / t.mean()
    bs = 100 * d[idx].mean(1) / t[idx].mean(1)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return {"rate": float(point), "lo": float(lo), "hi": float(hi)}


def _diff(a: list, b: list) -> list:
    """Per-seed b - a (None where either is undefined)."""
    return [None if x is None or y is None else y - x for x, y in zip(a, b)]


def _interaction(v, outcome: str, hi: str, lo: str) -> list:
    """Per seed: [(hi - lo) | adaptive] - [(hi - lo) | rule_deceptive]."""
    ad = _diff(v["ad"][lo][outcome], v["ad"][hi][outcome])
    rd = _diff(v["rd"][lo][outcome], v["rd"][hi][outcome])
    return _diff(rd, ad)


def _verdict(st: dict, sign: str) -> str:
    if st["lo"] is None:
        return "undefined"
    if (sign == ">" and st["lo"] > 0) or (sign == "<" and st["hi"] < 0):
        return "supported"
    if (sign == ">" and st["hi"] < 0) or (sign == "<" and st["lo"] > 0):
        return "contradicted (interval excludes 0 in the other direction)"
    return "not supported (interval includes 0)"


def analyse(rows: list[dict], seeds: list[int], n_boot: int, boot_seed: int) -> dict:
    by = {(r["policy"], r["condition"], r["seed"]): r for r in rows}
    v = {pk: {c: {m: [by[(pk, c, s)]["values"].get(m) for s in seeds] for m in ALL} for c in NAMES}
         for pk in POLICIES}
    res: dict = {"per_condition": {pk: {c: {m: mean_ci(v[pk][c][m]) for m in ALL} for c in NAMES} for pk in POLICIES}}

    # ---- positive-control gate
    shares = v["ad"]["posts_u2"]["false_share_to_eligible"]
    gate_catch = paired_diff(v["rd"]["posts_u2"]["catches"], v["ad"]["posts_u2"]["catches"])
    g1 = all(x == 0 for x in shares if x is not None) and all(x is not None for x in shares)
    g2 = gate_catch["hi"] is not None and gate_catch["hi"] < 0
    res["gate"] = {"false_share_to_uniformed_by_seed": shares, "condition_1_zero_share": g1,
                   "catches_adaptive_minus_rule": gate_catch, "condition_2_fewer_catches": g2, "passed": g1 and g2}
    if not res["gate"]["passed"]:
        res["per_seed"] = v
        return res

    # ---- P1 (confirmatory) and its exploratory companions
    p1 = {}
    for n in COUNTS:
        for m in PRIMARY + ["catches"]:
            st = mean_ci(_interaction(v, m, f"patrolling_u{n}", f"posts_u{n}"))
            conf = m in ("profit_per_stall.deceptive", "reachable.shortfall_rate")
            p1[f"{m}|{n}"] = {"count": n, "outcome": m, "confirmatory": conf, "I": st,
                              "verdict": _verdict(st, ">") if conf else None}
    p1_unif = {f"{m}|{n}": mean_ci(_interaction(v, m, f"patrolling_n{n}", f"posts_n{n}"))
               for n in COUNTS for m in PRIMARY}
    # the parts of the interaction: patrolling - posts within each policy
    parts = {pk: {f"{u}{n}": {m: paired_diff(v[pk][f"posts_{u}{n}"][m], v[pk][f"patrolling_{u}{n}"][m])
                              for m in PRIMARY + ["catches"]}
                  for n in COUNTS for u in ("u", "n")} for pk in POLICIES}

    # ---- P2 (exploratory): disguised vs uniformed patrolling
    p2 = {}
    for n in COUNTS:
        for m in PRIMARY + ["catches"]:
            st = mean_ci(_interaction(v, m, f"disguised_{n}", f"patrolling_u{n}"))
            p2[f"{m}|{n}"] = {"count": n, "outcome": m, "J": st,
                              "verdict": _verdict(st, "<") if m == "profit_per_stall.deceptive" else None,
                              "parts": {pk: paired_diff(v[pk][f"patrolling_u{n}"][m], v[pk][f"disguised_{n}"][m])
                                        for pk in POLICIES}}

    # ---- P3 (exploratory): uniformed - not uniformed
    p3 = {}
    for pk in POLICIES:
        for n in COUNTS:
            for pl in ("posts", "patrolling"):
                d = {m: paired_diff(v[pk][f"{pl}_n{n}"][m], v[pk][f"{pl}_u{n}"][m]) for m in PRIMARY + ["catches"]}
                exact0 = all(x == 0 for m in PRIMARY + ["catches"]
                             for x in _diff(v[pk][f"{pl}_n{n}"][m], v[pk][f"{pl}_u{n}"][m]) if x is not None)
                p3[f"{pk}|{pl}|{n}"] = {"policy": pk, "placement": pl, "count": n, "diff": d, "exactly_zero": exact0}

    # ---- adaptive - rule_deceptive within each condition, and each condition - control
    adapt = {c: {m: paired_diff(v["rd"][c][m], v["ad"][c][m]) for m in PRIMARY + SECONDARY} for c in NAMES}
    vs_ctrl = {pk: {c: {m: paired_diff(v[pk]["control"][m], v[pk][c][m]) for m in PRIMARY + SECONDARY}
                    for c in NAMES[1:]} for pk in POLICIES}

    # ---- effort-adjusted change vs control (descriptive)
    rng = np.random.default_rng(boot_seed)
    idx = rng.integers(0, len(seeds), size=(n_boot, len(seeds)))
    effort = {}
    for pk in POLICIES:
        effort[pk] = {}
        for c in NAMES[1:]:
            t = np.array(v[pk][c]["inspector_active_ticks.dedicated"], float)
            e = {"mean_active_ticks": float(t.mean()), "per_100_active_ticks": {}}
            for m in PRIMARY + ["catches"]:
                a, b = v[pk]["control"][m], v[pk][c][m]
                e["per_100_active_ticks"][m] = None if any(x is None for x in a + b) else \
                    _boot_rate(np.array(b, float) - np.array(a, float), t, idx)
            effort[pk][c] = e

    # ---- ceiling / floor flags: a metric constant across all seeds in a condition
    flags = []
    ticks, close, n_dec = 240, 40, 15
    max_catches = n_dec * -(-ticks // (close + 1))
    for pk in POLICIES:
        for c in NAMES:
            for m in PRIMARY + SECONDARY:
                xs = [x for x in v[pk][c][m] if x is not None]
                if c == "control" and m in ("catches", "inspector_active_ticks.dedicated"):
                    continue
                if m in ("empty_handed_share", "reachable.share", "inspector_active_ticks.dedicated"):
                    continue   # fixed by design (routes, headcount x ticks); reported separately
                if xs and len(set(xs)) == 1:
                    flags.append(f"{POLICIES[pk]} / {c}: {m} = {xs[0]} in every seed")
            cs = v[pk][c]["catches"]
            if any(x is not None and x >= max_catches for x in cs):
                flags.append(f"{POLICIES[pk]} / {c}: catches reach the maximum {max_catches} "
                             f"(every deceptive stall caught on each reopening) in "
                             f"{sum(x >= max_catches for x in cs)} seeds")
    res.update(p1=p1, p1_not_uniformed=p1_unif, p1_parts=parts, p2=p2, p3=p3, adaptive_minus_rule=adapt,
               vs_control=vs_ctrl, effort_adjusted=effort, flags=flags, per_seed=v)
    return res


# ------------------------------------------------------------------ report

def _f(m: str, x, signed=False) -> str:
    if x is None:
        return "–"
    if m in MONEY:
        x, fmt = x / 100, "{:+.2f}" if signed else "{:.2f}"
    elif m in PCT:
        x, fmt = 100 * x, "{:+.1f}" if signed else "{:.1f}"
    else:
        fmt = "{:+.1f}" if signed else "{:.1f}"
    return fmt.format(x)


def _c(m: str, st: dict | None, signed=False) -> str:
    if not st or st.get("mean") is None:
        return "–"
    s = _f(m, st["mean"], signed)
    if st.get("lo") is not None:
        s += f" [{_f(m, st['lo'], signed)}, {_f(m, st['hi'], signed)}]"
        if signed and (st["lo"] > 0 or st["hi"] < 0):
            s += " *"
    return s


def _t(head, rows) -> list[str]:
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(r) + " |" for r in rows]


def report(meta: dict, res: dict) -> str:
    L = ["# Visibility × seller adaptivity", "",
         "Does strategic avoidance erode the patrol advantage found in the placement sweep?", "",
         "## Run record", "",
         f"- Engine version: `{meta['engine_version']}`",
         f"- Commit: `{meta['git']['commit']}`; uncommitted at run time: "
         + (", ".join(f"`{x.strip()}`" for x in meta['git']['status_porcelain']) or "nothing"),
         f"- Run script: `analysis/visibility_adaptivity.py`, sha256 `{meta['script_sha256'][:16]}…`",
         f"- Command: `{meta['command']}`",
         f"- Wall-clock: {meta['wall_clock_s']:.0f} s for {meta['n_runs']} runs on {meta['workers']} workers "
         f"(load average at start {meta['load_at_start']:.1f})",
         f"- Seeds: {meta['seeds'][0]}–{meta['seeds'][-1]} ({len(meta['seeds'])}), paired across all 22 conditions",
         f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
         f"- Bootstrap: {meta['n_boot']} resamples of seeds, numpy default_rng({meta['boot_seed']})", "",
         "Condition names: `posts_u2` = 2 uniformed inspectors on posts, `posts_n2` = 2 non-uniformed,",
         "`patrolling_u6` = 6 uniformed patrolling, `disguised_2` = 2 disguised (never uniformed).",
         "Policies: `rule_deceptive` (does not read the uniform or catch notices) and",
         "`rule_deceptive_adaptive` (positive control). Notation: mean [95% t-interval over seeds];",
         "money in dollars, shares in percent, differences signed; `*` = interval excludes 0; unadjusted.",
         "\"Post/patrol inspectors\" are the dedicated inspectors on posts or patrolling, who are the",
         "uniformed ones in `_u` conditions.", ""]
    g = res["gate"]
    L += ["## Positive-control gate (checked first)", "",
          f"- Share of false-claim impressions perceived by uniformed inspectors, adaptive sellers, `posts_u2`: "
          f"{'0 in every seed' if g['condition_1_zero_share'] else 'NOT 0 in every seed'} "
          f"(max {max(x for x in g['false_share_to_uniformed_by_seed'] if x is not None):.4f}).",
          f"- Catches, adaptive − rule_deceptive, `posts_u2`: "
          f"{_c('catches', g['catches_adaptive_minus_rule'], True)} "
          f"({'below 0' if g['condition_2_fewer_catches'] else 'NOT below 0'}).",
          f"- **Gate {'passed' if g['passed'] else 'FAILED: nothing else is interpreted'}.**", ""]
    if not g["passed"]:
        return "\n".join(L) + "\n"

    L += ["## P1 (confirmatory): adaptivity shrinks the patrolling advantage, uniformed inspectors", "",
          "I = [(patrolling − posts) | adaptive] − [(patrolling − posts) | rule_deceptive], per seed, uniformed",
          "inspectors. Predicted I > 0 for deceptive profit and for reachable shortfall rate, at count 2 and 6.",
          "The other rows are exploratory.", ""]
    rows = []
    for k, e in res["p1"].items():
        rows.append([f"{e['count']}", LABEL[e["outcome"]] + (" **(confirmatory)**" if e["confirmatory"] else ""),
                     _c(e["outcome"], e["I"], True), e["verdict"] or "exploratory"])
    L += _t(["count", "outcome", "I", "verdict"], rows) + [""]
    L += ["The two halves of I (patrolling − posts within each policy, uniformed):", ""]
    rows = []
    for n in COUNTS:
        for pk in POLICIES:
            pr = res["p1_parts"][pk][f"u{n}"]
            rows.append([f"{n}", POLICIES[pk]] + [_c(m, pr[m], True) for m in PRIMARY + ["catches"]])
    L += _t(["count", "sellers"] + [LABEL[m] for m in PRIMARY + ["catches"]], rows) + [""]
    L += ["Exploratory: the same interaction with non-uniformed inspectors (adaptive sellers can then react",
          "only to catch notices and their own reopening):", ""]
    rows = [[f"{n}"] + [_c(m, res["p1_not_uniformed"][f"{m}|{n}"], True) for m in PRIMARY] for n in COUNTS]
    L += _t(["count"] + [LABEL[m] for m in PRIMARY], rows) + [""]

    L += ["## P2 (exploratory): disguised inspectors gain against adaptive sellers", "",
          "J = [(disguised − uniformed patrolling) | adaptive] − [same | rule_deceptive]. Predicted J < 0",
          "for deceptive profit.", ""]
    rows = []
    for k, e in res["p2"].items():
        rows.append([f"{e['count']}", LABEL[e["outcome"]], _c(e["outcome"], e["J"], True),
                     _c(e["outcome"], e["parts"]["rd"], True), _c(e["outcome"], e["parts"]["ad"], True),
                     e["verdict"] or "–"])
    L += _t(["count", "outcome", "J", "disguised − patrol_u, rule_deceptive", "disguised − patrol_u, adaptive",
             "verdict"], rows) + [""]

    L += ["## P3 (exploratory): the uniform is costly only against adaptive sellers", "",
          "Uniformed − not uniformed, paired. Predicted ~0 under rule_deceptive (exactly 0 is implied by",
          "the byte-identical test) and favouring deceptive sellers under adaptive (profit and shortfall up).", ""]
    rows = []
    for k, e in res["p3"].items():
        rows.append([POLICIES[e["policy"]], e["placement"], f"{e['count']}"] +
                    [_c(m, e["diff"][m], True) for m in PRIMARY + ["catches"]] +
                    ["yes" if e["exactly_zero"] else "no"])
    L += _t(["sellers", "placement", "count"] + [LABEL[m] for m in PRIMARY + ["catches"]] + ["exactly 0 in every seed"],
            rows) + [""]

    for title, ms in (("Primary outcomes by condition", PRIMARY), ("Secondary outcomes by condition", SECONDARY)):
        L += [f"## {title}", ""]
        rows = [[POLICIES[pk], c] + [_c(m, res["per_condition"][pk][c][m]) for m in ms] for pk in POLICIES for c in NAMES]
        L += _t(["sellers", "condition"] + [LABEL[m] for m in ms], rows) + [""]

    L += ["## Adaptive − rule_deceptive within each condition (paired, exploratory)", ""]
    rows = [[c] + [_c(m, res["adaptive_minus_rule"][c][m], True) for m in PRIMARY + ["catches"]] for c in NAMES]
    L += _t(["condition"] + [LABEL[m] for m in PRIMARY + ["catches"]], rows) + [""]

    L += ["## Each condition − control, within policy (paired, exploratory)", ""]
    rows = [[POLICIES[pk], c] + [_c(m, res["vs_control"][pk][c][m], True) for m in PRIMARY]
            for pk in POLICIES for c in NAMES[1:]]
    L += _t(["sellers", "condition"] + [LABEL[m] for m in PRIMARY], rows) + [""]

    L += ["## Effort-adjusted change vs control (descriptive rate, not a causal estimate)", "",
          "100 × mean(paired change vs control, same policy) / mean(active inspector-ticks), with a paired",
          "percentile bootstrap 95% CI.", ""]
    rows = []
    for pk in POLICIES:
        for c in NAMES[1:]:
            e = res["effort_adjusted"][pk][c]
            cells = []
            for m in PRIMARY + ["catches"]:
                r = e["per_100_active_ticks"][m]
                cells.append("–" if r is None else f"{_f(m, r['rate'], True)} [{_f(m, r['lo'], True)}, {_f(m, r['hi'], True)}]")
            rows.append([POLICIES[pk], c, f"{e['mean_active_ticks']:.0f}"] + cells)
    L += _t(["sellers", "condition", "mean active ticks"] + [LABEL[m] for m in PRIMARY + ["catches"]], rows) + [""]

    L += ["## Patrol-timing evidence", "",
          "For each deceptive stall, the share of its false-claim messages sent while no post/patrol inspector",
          "was within earshot (a message = one sign display, yell, whisper or answer). Per run: pooled over",
          "stalls, the mean of the per-stall shares, and the share of stalls whose false messages were all",
          "unwatched. In `_u` conditions those inspectors are uniformed; in `_n` conditions sellers cannot see them.",
          "Not defined for control and disguised (no post/patrol inspectors).", ""]
    dm = ["false_claims.messages", "unwatched_share_pooled", "unwatched_share_stall_mean",
          "stalls_always_unwatched_share", "false_share_to_eligible"]
    rows = [[POLICIES[pk], c] + [_c(m, res["per_condition"][pk][c][m]) for m in dm]
            for pk in POLICIES for c in NAMES if c.startswith(("posts", "patrolling"))]
    L += _t(["sellers", "condition"] + [LABEL[m] for m in dm], rows) + [""]

    L += ["## Ceiling and floor flags", "",
          f"Automatic: any primary or secondary outcome constant across all {len(meta['seeds'])} seeds in a condition, and any",
          "condition whose catch count reaches its maximum (15 deceptive stalls × 6 catches in 240 ticks).", ""]
    L += [f"- {x}" for x in res["flags"]] or ["- none"]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", default="0-29")
    ap.add_argument("--out", default="runs/visibility_adaptivity.json")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--boot", type=int, default=10_000)
    ap.add_argument("--boot-seed", type=int, default=20261105)
    args = ap.parse_args(argv)
    seeds = parse_seeds(args.seeds)
    jobs = [(pk, c, n, pl, u, s) for pk in POLICIES for c, n, pl, u in CONDITIONS for s in seeds]
    load0 = os.getloadavg()[0]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as ex:
        rows = list(ex.map(_job, jobs, chunksize=4))
    wall = time.time() - t0
    res = analyse(rows, seeds, args.boot, args.boot_seed)
    with open(__file__, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    meta = {"design": "visibility x seller adaptivity (does strategic avoidance erode the patrol advantage?)",
            "engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": sha,
            "command": " ".join([".venv/bin/python -m analysis.visibility_adaptivity"] +
                                (argv if argv is not None else sys.argv[1:])),
            "wall_clock_s": wall, "load_at_start": load0, "n_runs": len(jobs), "workers": args.workers,
            "seeds": seeds, "policies": POLICIES,
            "conditions": [{"name": c, "count": n, "placement": pl, "uniformed": u} for c, n, pl, u in CONDITIONS],
            "n_boot": args.boot, "boot_seed": args.boot_seed,
            "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform()}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": res, "runs": rows}, f, indent=1)
    with open(os.path.splitext(args.out)[0] + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["policy", "condition", "count", "placement", "uniformed", "seed"] + ALL)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in ("policy", "condition", "count", "placement", "uniformed", "seed")}
                       | {"policy": POLICIES[r["policy"]]} | r["values"])
    with open(os.path.splitext(args.out)[0] + "_summary.md", "w", encoding="utf-8") as f:
        f.write(report(meta, res))
    print(f"gate {'passed' if res['gate']['passed'] else 'FAILED'}; wrote {args.out} (+ .csv, _summary.md) "
          f"in {wall:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
