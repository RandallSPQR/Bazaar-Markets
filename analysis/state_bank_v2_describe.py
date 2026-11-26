"""Descriptive tables for runs/state_bank_v2_summary.md (written after the bank results; exploratory, no new simulation).

Reads runs/state_bank_v2/states.jsonl.gz and writes runs/state_bank_v2/describe.json:
  - pays and close calls by market factor, band and snapshot day (unweighted counts and weighted shares);
  - the best option, unweighted and weighted;
  - simple-rule baselines for agent evaluation: best-option accuracy and mean regret (best option's mean minus the
    chosen option's mean, dollars, and as weighted total regret over weighted total |keep_supply mean|), weighted
    by the sampling weights;
  - displayed ratings in the below band; P(caught) and P(owner fined) per option by detect_scale.
Money in the bank file is in cents; this script reports dollars.
"""
import gzip
import json
from collections import defaultdict

import numpy as np

SRC = "runs/state_bank_v2/states.jsonl.gz"
OUT = "runs/state_bank_v2/describe.json"
OPTS = ["keep_supply", "switch_supply_now", "switch_supply_in_5_days", "switch_supply_in_10_days",
        "license_name_cheap_quality", "leave_market"]


def load():
    return [json.loads(x) for x in gzip.open(SRC, "rt", encoding="utf-8")]


def wshare(rows, f):
    w = np.array([r["sampling"]["weight"] for r in rows], float)
    v = np.array([bool(f(r)) for r in rows], float)
    return float((w * v).sum() / w.sum()) if len(rows) else None


def by(rows, key):
    g = defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    return {str(k): {"states": len(v), "pays": sum(r["labels"]["pays"] for r in v),
                     "close_calls": sum(r["labels"]["close_call"] for r in v),
                     "pays_weighted": wshare(v, lambda r: r["labels"]["pays"]),
                     "weight_share": float(sum(r["sampling"]["weight"] for r in v))}
            for k, v in sorted(g.items(), key=lambda kv: str(kv[0]))}


def rule_scores(rows, choose):
    """Weighted best-option accuracy and regret of a rule mapping a record to an option name."""
    W = sum(r["sampling"]["weight"] for r in rows)
    acc = reg = hon = 0.0
    n_acc = 0
    for r in rows:
        m = r["labels"]["means"]
        c = choose(r)
        best = r["labels"]["best"]
        w = r["sampling"]["weight"]
        g = (m[best] - m[c]) / 100
        acc += w * (c == best)
        n_acc += c == best
        reg += w * g
        hon += w * abs(m["keep_supply"]) / 100
    return {"accuracy_weighted": acc / W, "accuracy_unweighted": n_acc / len(rows), "regret_usd_weighted": reg / W,
            "regret_share_of_honest_weighted": reg / hon}


def main():
    rows = load()
    W = sum(r["sampling"]["weight"] for r in rows)
    out = {"states": len(rows), "weight_total": W}
    L = lambda r: r["labels"]
    H = lambda r: r["hidden"]
    out["pays"] = {"unweighted": sum(L(r)["pays"] for r in rows), "weighted": wshare(rows, lambda r: L(r)["pays"])}
    out["pays_interval_rule"] = sum(L(r)["cheating_minus_honest_ci95"][0] > 0 for r in rows)
    ci0 = [r for r in rows if L(r)["cheating_minus_honest_ci95"][0] <= 0 <= L(r)["cheating_minus_honest_ci95"][1]]
    rel = [r for r in rows if abs(L(r)["cheating_minus_honest"]) < 0.05 * abs(L(r)["means"]["keep_supply"])]
    out["close_calls"] = {"total": sum(L(r)["close_call"] for r in rows), "interval_includes_0": len(ci0),
                          "within_5pct": len(rel), "both": len({r["id"] for r in ci0} & {r["id"] for r in rel}),
                          "weighted": wshare(rows, lambda r: L(r)["close_call"]),
                          "pays_among_close": sum(L(r)["pays"] for r in rows if L(r)["close_call"])}
    out["by"] = {"tourist_share": by(rows, lambda r: H(r)["tourist_share"]),
                 "local_inspect": by(rows, lambda r: H(r)["local_inspect"]),
                 "detect_scale": by(rows, lambda r: H(r)["detect_scale"]),
                 "prior_n": by(rows, lambda r: H(r)["prior_n"]),
                 "owner_liable": by(rows, lambda r: H(r)["owner_liable"]),
                 "counterfeits": by(rows, lambda r: H(r)["counterfeits"]),
                 "band": by(rows, lambda r: H(r)["band"]),
                 "day": by(rows, lambda r: r["observation"]["day"]),
                 "category": by(rows, lambda r: H(r)["category"])}
    out["best"] = {o: {"unweighted": sum(L(r)["best"] == o for r in rows),
                       "weighted": wshare(rows, lambda r, o=o: L(r)["best"] == o)} for o in OPTS}
    out["best_cheating_option"] = {o: sum(L(r)["best_cheating_option"] == o for r in rows) for o in OPTS}
    best_cheat = lambda r: L(r)["best_cheating_option"]
    out["rules"] = {
        "always_keep_supply": rule_scores(rows, lambda r: "keep_supply"),
        "always_cheap_licence": rule_scores(rows, lambda r: "license_name_cheap_quality"),
        "always_switch_now": rule_scores(rows, lambda r: "switch_supply_now"),
        "oracle_pays_label": rule_scores(rows, lambda r: best_cheat(r) if L(r)["pays"] else "keep_supply"),
        "hidden_tourists_only": rule_scores(rows, lambda r: "license_name_cheap_quality"
                                            if H(r)["tourist_share"] == 1.0 else "keep_supply"),
    }
    below = [r["observation"]["rating"] for r in rows if H(r)["band"] == "below"]
    out["below_ratings"] = {"n": len(below), "min": min(below), "median": float(np.median(below)),
                            "max": max(below), "share_under_0.9": float(np.mean([b < 0.9 for b in below]))}
    caught = {}
    for ds in sorted({H(r)["detect_scale"] for r in rows}):
        sub = [r for r in rows if H(r)["detect_scale"] == ds]
        caught[str(ds)] = {o: {"p_caught_mean": float(np.mean([r["lotteries"][o]["p_caught"] for r in sub
                                                                 if r["lotteries"][o]])),
                               "p_owner_fined_mean": float(np.mean([r["lotteries"][o]["p_owner_fined"] for r in sub
                                                                     if r["lotteries"][o]]))}
                           for o in OPTS[:5]}
    out["caught_by_detect_scale"] = caught
    d = np.array([L(r)["cheating_minus_honest"] / 100 for r in rows])
    out["cheating_minus_honest_usd"] = {"p5": float(np.percentile(d, 5)), "median": float(np.median(d)),
                                        "p95": float(np.percentile(d, 95))}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(OUT)


if __name__ == "__main__":
    main()
