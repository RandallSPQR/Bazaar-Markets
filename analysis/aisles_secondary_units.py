"""Aisles study (plan 2026-11-27): the Run A and Run B contrasts in the plan's secondary units (written after the results).

The plan names dollars and base-price units as secondary units, but the frozen script reports them only per cell, not as
the paired contrasts the predictions use. This script adds those contrasts, post hoc:
- Run A: PA1, PA2, PA4 (interaction and t100 analogues).
- Run B: PB1, PB2, PB3.

Each contrast is computed per seed (pooled = the mean over the seed's three sampled stalls) with the same pairing and
the same 95% t interval as the primary. It also reports each cell's mean never-chain (honest) profit, to show why the
D5 ratio is undefined in many ds 0 thin-margin seeds.

Nothing here changes a verdict. Reads the main cache and calibration; writes runs/aisles_secondary_units.json.
"""
import json

from analysis import aisles_1_3 as AS
from engine.config import load

OUT = "runs/aisles_secondary_units.json"


def main():
    base = load(AS.REF).pricing.base_price_cents
    recs = {}
    with open(AS.CACHE, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            recs[r["key"]] = r
    recs = list(recs.values())
    res = {"note": "post hoc (written after the results): paired contrasts in the plan's secondary units",
           "script_sha256": AS._script_sha()}
    for run in ("A", "B"):
        seeds = AS.SEEDS[run]
        samples = {sd: AS.sample_stalls(sd) for sd in seeds}
        Gs = {}
        for c in AS.CELLS[run]:
            n = AS.cell_name(c)
            G = AS.gains(recs, n, seeds, samples)
            AS.base_units(G, samples, base)
            for sd in G:
                for s in G[sd]:
                    G[sd][s]["never_dollars"] = G[sd][s]["never"] / 100
            Gs[n] = G

        def P(n, aisle=None, f="base_units"):
            return AS.per_seed(Gs[n], seeds, samples, f, aisle)

        out = {"cells": {}, "contrasts": {}}
        for n in Gs:
            out["cells"][n] = {"never_dollars": {"pooled": AS.mean_ci(P(n, None, "never_dollars")),
                                                 **{a: AS.mean_ci(P(n, a, "never_dollars")) for a in AS.CATS}},
                               "gain_base_units": AS.mean_ci(P(n)),
                               "gain_dollars": AS.mean_ci(P(n, None, "dollars"))}
        C = out["contrasts"]
        for f in ("base_units", "dollars"):
            if run == "A":
                for m in AS.MARGIN:
                    C[f"PA1|{m}|{f}"] = AS.diff(P(f"A|{m}|easy|t40|ds0", None, f), P(f"A|{m}|hard|t40|ds0", None, f))
                    C[f"PA4|t100|PA1|{m}|{f}"] = AS.diff(P(f"A|{m}|easy|t100|ds0", None, f),
                                                         P(f"A|{m}|hard|t100|ds0", None, f))
                for v in AS.VERIF:
                    C[f"PA2|{v}|{f}"] = AS.diff(P(f"A|fat|{v}|t40|ds0", None, f), P(f"A|thin|{v}|t40|ds0", None, f))
                    C[f"PA4|t100|PA2|{v}|{f}"] = AS.diff(P(f"A|fat|{v}|t100|ds0", None, f),
                                                         P(f"A|thin|{v}|t100|ds0", None, f))
                q = [P(f"A|{x}|t40|ds0", None, f) for x in ("fat|easy", "fat|hard", "thin|easy", "thin|hard")]
                C[f"PA4|interaction|t40|{f}"] = AS.mean_ci([(d - c) - (b - a) for a, b, c, d in zip(*q)])
            else:
                C[f"PB1|{f}"] = AS.diff(P("B|cash20|a0|ds0", None, f), P("B|cash2|a0|ds0", None, f))
                C[f"PB2|{f}"] = AS.diff(P("B|cash20|a0|ds0", "fish", f), P("B|cash20|a0|ds0", "designer", f))
                for a in AS.CATS:
                    C[f"PB3|cash|{a}|{f}"] = AS.diff(P("B|cash20|a0|ds0", a, f), P("B|cash2|a0|ds0", a, f))
                for cash in ("2", "20"):
                    C[f"PB3|alpha|cash{cash}|{f}"] = AS.diff(P(f"B|cash{cash}|a0|ds0", None, f),
                                                             P(f"B|cash{cash}|a1|ds0", None, f))
                C[f"PB3|ds1|PB1|{f}"] = AS.diff(P("B|cash20|a0|ds1", None, f), P("B|cash2|a0|ds1", None, f))
                C[f"PB3|ds1|PB2|{f}"] = AS.diff(P("B|cash20|a0|ds1", "fish", f), P("B|cash20|a0|ds1", "designer", f))
        res[run] = out
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    print(f"written {OUT}")


if __name__ == "__main__":
    main()
