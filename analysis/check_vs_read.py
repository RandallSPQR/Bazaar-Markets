"""Stage 1 of the 2026-11-19 plan (runs/plan_autonomous_2026-11-19.md): checking vs reading ratings, engine 0.21.0.

Locals both inspect and read ratings, so earlier runs cannot say which behaviour stops switching supply (bust-outs) and
which pays for reputation. Buyers: tourist share 0.4, the other 0.6 all locals (experts 0); locals' reads_ratings
{yes, no} x inspect_prob {1.0, 0} (buyers.profile_overrides), 4 cells; reference cell: tourist share 1.0. Market
defaults of the plan: ratings.display stars, display_step 0.02, buyers.tie_break random.

  Outcome A, bust-out gain: the verification-run benchmark as in analysis/liability.py (market B: 2 patrolling
    inspectors, not uniformed; collectible fines, penalty lag 0; 3 genuine stalls per seed from default_rng([seed, 17]);
    candidates never, day 20, 25, 28, 29, 30; unfloored gain primary). 30 days, detect_scale 0 and 1.
  Outcome B, reputation effect: E = J(R) - J(W_g) as in analysis/brand_equity_stars.py (contract, genuine tier, royalty
    0.10, N 6 from day 10, prior_scope new, 60 days, detect_scale 1), at prior_n 0 and 400.
  PC6 decomposition: for detect_scale 0, each stall's best candidate (by the unfloored gain) and the never chain rerun
    with buyer-level records (analysis/bustout_decomp.py), decomposed as analysis/bustout_report.py.

Seeds 350-369, paired across all cells. Pilot: seeds 900-902 into runs/pilot_check_vs_read/ with gates G1-G5.

    PYTHONPATH=. .venv/bin/python -m analysis.check_vs_read --pilot --tests "..."
    PYTHONPATH=. .venv/bin/python -m analysis.check_vs_read --tests "..." --gate "..."
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import json
import os
import platform
import sys
import time
from types import SimpleNamespace

import numpy as np

import analysis.brand_equity as E
import analysis.brand_equity_stars as BES
import analysis.bustout_decomp as BD
import analysis.bustout_report as BR
import analysis.chainrun as CR
import analysis.liability as LB
import analysis.licensing as L
from analysis.counterfeit import _git, _load
from cli.sweep import parse_seeds
from engine import ENGINE_VERSION, bazaar as EB, benchmark
from engine.metrics import mean_ci

NEVER = benchmark.NEVER
MAIN_SEEDS = "350-369"
PILOT_SEEDS = "900-902"
CELLS = {"RI": (True, 1.0), "Rn": (True, 0.0), "nI": (False, 1.0), "nn": (False, 0.0)}
REF = "ref"
ALL_CELLS = [*CELLS, REF]
CLAB = {"RI": "reads, inspects", "Rn": "reads, does not inspect", "nI": "does not read, inspects",
        "nn": "neither (as a tourist)", REF: "reference: tourist share 1.0"}
DS = (0.0, 1.0)
PN = (0.0, 400.0)
STARS = ["ratings.display=stars", "ratings.display_step=0.02", "buyers.tie_break=random"]
SHARES = {"locals": '{"tourist":0.4,"local":0.6,"expert":0.0}', REF: '{"tourist":1.0,"local":0.0,"expert":0.0}'}
LIMIT_H = 7.0
OUT_MAIN, OUT_PILOT = "runs", "runs/pilot_check_vs_read"
NOOV = "noov"     # pilot only (G2): the locals market with no overrides at all

PREDICTIONS = [
    ("PC1", "confirmatory", "bust-out gain, detect_scale 0: the main effect of inspection (inspect 1.0 − 0, averaged "
                            "over reads_ratings) is < 0."),
    ("PC2", "confirmatory", "bust-out gain, detect_scale 0: |main effect of reading ratings| < |main effect of "
                            "inspection|."),
    ("PC3", "confirmatory", "reputation effect, prior_n 400: the main effect of reading ratings (yes − no, averaged over "
                            "inspection) is > 0."),
    ("PC4", "confirmatory", "reputation effect, prior_n 400: |main effect of inspection| < |main effect of reading "
                            "ratings|."),
    ("PC5", "exploratory", "both interactions (reading × inspection) for each outcome; the detect_scale 1 analogues of "
                           "PC1–PC2; the prior_n 0 analogues of PC3–PC4."),
    ("PC6", "exploratory", "harm by profile; deceptive stalls' share of sales by cell; the bust-out decomposition's "
                           "\"rating below threshold\" cause by cell."),
]


def cell_ov(c: str) -> list[str]:
    if c == REF:
        return [f"buyers.profile_shares={SHARES[REF]}", *STARS]
    if c == NOOV:
        return [f"buyers.profile_shares={SHARES['locals']}", *STARS]
    r, i = CELLS[c]
    ov = json.dumps({"local": {"reads_ratings": r, "inspect_prob": i}}, separators=(",", ":"))
    return [f"buyers.profile_shares={SHARES['locals']}", f"buyers.profile_overrides={ov}", *STARS]


def _script_sha() -> str:
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ chains
# jobs: ("A", cell, ds, seed, watch, stall, b) | ("B", cell, pn, seed, arm, owner) | ("D", cell, seed, watch, stall, b)

_CAP: list = []
_ENG: list = []


def _hooks() -> None:
    """Observers that change nothing: each run's output (for the guard and deceptive share), each engine's buyer
    settings (to check the cell is the one asked for)."""
    if getattr(EB.run, "_cvr", False):
        return
    orun, oinit = EB.run, EB.BazaarEngine.__init__

    def run(cfg, *a, **k):
        out = orun(cfg, *a, **k)
        _CAP.append(out)
        return out

    def init(self, cfg, *a, **k):
        _ENG.append((json.dumps(cfg.buyers.profile_shares, sort_keys=True),
                     json.dumps(cfg.buyers.profile_overrides, sort_keys=True), cfg.ratings.display,
                     float(cfg.ratings.display_step), cfg.buyers.tie_break))
        return oinit(self, cfg, *a, **k)

    run._cvr = True
    EB.run = run
    EB.BazaarEngine.__init__ = init


@contextlib.contextmanager
def _cell(c):
    """The cell's buyer settings and the plan's market defaults appended to every load() of the studies' config
    builders (later keys win)."""
    mods = (LB, BES)
    orig = {m: m.load for m in mods}
    extra = cell_ov(c)
    for m in mods:
        m.load = lambda path=None, overrides=None, mode=None, _b=orig[m]: _b(path, [*(overrides or []), *extra],
                                                                              mode=mode)
    try:
        yield
    finally:
        for m, f in orig.items():
            m.load = f


def key(j) -> str:
    if j[0] == "A":
        _, c, ds, sd, _w, s, b = j
        return f"A|{c}|ds{ds:g}|{sd}|{s}|{LB.ck(b)}"
    if j[0] == "B":
        _, c, pn, sd, arm, o = j
        return f"B|{c}|pn{pn:g}|{sd}|{arm}|{o}"
    _, c, sd, _w, s, b = j
    return f"D|{c}|{sd}|{s}|{LB.ck(b)}"


def _want(c) -> tuple:
    ov = {} if c in (REF, NOOV) else {"local": {"reads_ratings": CELLS[c][0], "inspect_prob": CELLS[c][1]}}
    sh = json.loads(SHARES[REF if c == REF else "locals"])
    return (json.dumps(sh, sort_keys=True), json.dumps(ov, sort_keys=True), "stars", 0.02, "random")


def job(j) -> dict:
    _hooks()
    _CAP.clear()
    _ENG.clear()
    LB._observe()
    t0 = time.time()
    kind, c = j[0], j[1]
    with _cell(c):
        if kind == "A":
            _, _, ds, sd, w, s, b = j
            rec = LB._job((f"col|t40|ds{ds!r}", sd, list(w), s, b))
            out = _CAP[-1]
            rec["dec_share"] = [d["outcome"]["deceptive_share_sales_units"] for d in out["days"]]
        elif kind == "B":
            _, _, pn, sd, arm, o = j
            rec = BES.job((arm, "t40", sd, o, BES.ROYALTY, pn, BES.STEP))
        else:
            _, _, sd, w, s, b = j
            BD._patch()
            rec = BD._job((f"col|t40|ds0.0", sd, list(w), s, b))
            rec["guard"] = CR.guard(_CAP[-1])
    rec = json.loads(json.dumps(rec))
    seen = sorted(set(_ENG))
    # every engine runs the cell's settings, except the stall-sampling engine some jobs build (default market, exact
    # display: analysis.verification.sample_stalls), which only lists stalls
    other = [e for e in seen if e != _want(c)]
    ok = _want(c) in seen and all(e[1] == "{}" and e[2] == "exact" for e in other)
    rec.update(key=key(j), kind=kind, cell=c, secs=round(time.time() - t0, 2), cell_ok=ok,
               engine_version=ENGINE_VERSION)
    return rec


def jobs_main(seeds, samples, cells=ALL_CELLS, pns=PN) -> list[tuple]:
    out = []
    for sd in seeds:
        w = tuple(samples[sd])
        for c in cells:
            for ds in DS:
                out.append(("A", c, ds, sd, w, None, NEVER))
                for s in w:
                    for b in LB.COL_CANDS:
                        out.append(("A", c, ds, sd, w, s, b))
            for pn in pns:
                out.append(("B", c, pn, sd, "never", None))
                for s in w:
                    for arm in ("R", "Wg"):
                        out.append(("B", c, pn, sd, arm, s))
    return out


def jobs_g2(seed, samples) -> list[tuple]:
    """G2: the locals market with no overrides, seed `seed`, every A chain at detect_scale 0 and every B chain at
    prior_n 400; compared with cell RI (overrides = the profile defaults)."""
    w = tuple(samples[seed])
    out = [("A", NOOV, 0.0, seed, w, None, NEVER)] + [("A", NOOV, 0.0, seed, w, s, b) for s in w for b in LB.COL_CANDS]
    out += [("B", NOOV, 400.0, seed, "never", None)] + [("B", NOOV, 400.0, seed, arm, s) for s in w for arm in ("R", "Wg")]
    return out


def gains_by(runs, seeds, samples) -> dict:
    """{(cell, ds): {seed: {stall: benchmark.gain}}}"""
    idx = {(r["cell"], r["cond"], r["seed"], r["stall"], r["b"]): r for r in runs if r["kind"] == "A"}
    G: dict = {}
    for (c, cond, sd, st, b), r in idx.items():
        if b != NEVER:
            continue
        ds = float(cond.split("|ds")[1])
        for s in samples[sd]:
            tot = {NEVER: r["totals"][s], **{LB.ck(x): idx[(c, cond, sd, s, LB.ck(x))]["totals"][s] for x in LB.COL_CANDS}}
            G.setdefault((c, ds), {}).setdefault(sd, {})[s] = benchmark.gain(tot)
    return G


def jobs_decomp(G, seeds, samples) -> list[tuple]:
    out = []
    for c in ALL_CELLS:
        for sd in seeds:
            w = tuple(samples[sd])
            out.append(("D", c, sd, w, None, NEVER))
            for s in w:
                b = G[(c, 0.0)][sd][s]["best_day"]
                out.append(("D", c, sd, (s,), s, int(b)))
    return out


# ------------------------------------------------------------------ analysis

def _st(xs) -> dict:
    return mean_ci(list(xs))


def _verdict(st, sign) -> str:
    if st["lo"] is None:
        return "not testable"
    if (sign > 0 and st["lo"] > 0) or (sign < 0 and st["hi"] < 0):
        return "supported"
    if (sign > 0 and st["hi"] < 0) or (sign < 0 and st["lo"] > 0):
        return "contradicted (interval on the opposite side of 0)"
    return "not supported (interval includes 0)"


def effects(y: dict) -> dict:
    """y: {cell: [per-seed value]} for the four cells. Per seed: inspection = mean(RI, nI) - mean(Rn, nn); reading =
    mean(RI, Rn) - mean(nI, nn); interaction = (RI - Rn) - (nI - nn), the inspection effect among readers minus among
    non-readers. Comparisons of size: per seed sgn(mean I) I_s - sgn(mean R) R_s, whose mean is |mean I| - |mean R|."""
    n = len(y["RI"])
    I = [(y["RI"][k] + y["nI"][k]) / 2 - (y["Rn"][k] + y["nn"][k]) / 2 for k in range(n)]
    R = [(y["RI"][k] + y["Rn"][k]) / 2 - (y["nI"][k] + y["nn"][k]) / 2 for k in range(n)]
    X = [(y["RI"][k] - y["Rn"][k]) - (y["nI"][k] - y["nn"][k]) for k in range(n)]
    sI, sR = np.sign(np.mean(I)) or 1.0, np.sign(np.mean(R)) or 1.0
    i_minus_r = [sI * I[k] - sR * R[k] for k in range(n)]
    return {"inspection": _st(I), "reading": _st(R), "interaction": _st(X),
            "absI_minus_absR": _st(i_minus_r), "absR_minus_absI": _st([-v for v in i_minus_r]),
            "per_seed": {"I": I, "R": R, "X": X}}


def analyse(runs, seeds, samples) -> dict:
    res: dict = {"seeds": seeds, "flags": [], "A": {}, "B": {}, "D": {}, "pc6": {}, "pred": {}, "guard": {},
                 "identity": {}}
    # guard and cell checks
    for r in runs:
        g = r.get("guard", {})
        k = f"{r['kind']} · {r['cell']}"
        acc = res["guard"].setdefault(k, {"chains": 0, "stuck_buyers": 0, "parked": 0, "idle_choosers": 0,
                                          "fallbacks": 0, "cell_bad": 0, "secs": 0.0})
        acc["chains"] += 1
        acc["secs"] += r["secs"]
        acc["cell_bad"] += not r["cell_ok"]
        for f in ("stuck_buyers", "parked", "idle_choosers"):
            acc[f] += int(g.get(f, 0))
        acc["fallbacks"] += int(r.get("fallbacks", g.get("fallbacks", 0)) or 0)
    # outcome A
    G = gains_by(runs, seeds, samples)
    for ds in DS:
        y = {c: [float(np.mean([G[(c, ds)][sd][s]["gain_unfloored"] for s in samples[sd]])) for sd in seeds]
             for c in ALL_CELLS}
        yf = {c: [float(np.mean([G[(c, ds)][sd][s]["gain_floored"] for s in samples[sd]])) for sd in seeds]
              for c in ALL_CELLS}
        best = {c: {str(b): sum(G[(c, ds)][sd][s]["best_day"] == str(b) for sd in seeds for s in samples[sd])
                    for b in LB.COL_CANDS} for c in ALL_CELLS}
        res["A"][f"ds{ds:g}"] = {"cells": {c: _st(y[c]) for c in ALL_CELLS},
                                 "floored": {c: _st(yf[c]) for c in ALL_CELLS}, "best_day": best,
                                 "eff": effects(y), "ref_minus_nn": _st([y[REF][k] - y["nn"][k] for k in range(len(seeds))]),
                                 "per_seed": y}
    # outcome B
    idx = {(r["cell"], r["prior_n"], r["seed"], r["arm"], r["owner"]): r for r in runs if r["kind"] == "B"}
    jbad = jn = miss = 0
    for pn in PN:
        y, parts = {}, {}
        for c in ALL_CELLS:
            ys, pr = [], {"J_R": [], "J_Wg": [], "J_never": []}
            for sd in seeds:
                nv = idx[(c, pn, sd, "never", None)]
                es, jr, jg, jv = [], [], [], []
                for s in samples[sd]:
                    R, W = idx[(c, pn, sd, "R", s)], idx[(c, pn, sd, "Wg", s)]
                    lic = R["licensees"]
                    if W["licensees"] != lic or len(lic) != BES.N_LIC or not all(W["white_label"].values()):
                        res["flags"].append(f"B|{c}|{pn:g}|{sd}|{s}: R and W_g licensees differ or not 6 white labels")
                    stalls = [s, *lic]
                    a, b, n = E._J(R, stalls), E._J(W, stalls), E._J(nv, stalls)
                    for p_, q_ in (a, b, n):
                        jbad += p_ != q_
                        jn += 1
                    miss += W.get("tier_price_miss", 0)
                    es.append(a[0] - b[0]); jr.append(a[0]); jg.append(b[0]); jv.append(n[0])
                ys.append(float(np.mean(es)))
                pr["J_R"].append(float(np.mean(jr))); pr["J_Wg"].append(float(np.mean(jg)))
                pr["J_never"].append(float(np.mean(jv)))
            y[c], parts[c] = ys, {k: _st(v) for k, v in pr.items()}
        res["B"][f"pn{pn:g}"] = {"cells": {c: _st(y[c]) for c in ALL_CELLS}, "J": parts, "eff": effects(y),
                                 "ref_minus_nn": _st([y[REF][k] - y["nn"][k] for k in range(len(seeds))]),
                                 "per_seed": y}
    res["identity"] = {"J_pairs": jn, "J_mismatch": jbad, "tier_price_miss": miss}
    if jbad:
        res["flags"].append(f"J identity fails in {jbad} of {jn} owner-chains")
    if miss:
        res["flags"].append(f"genuine-tier price misses: {miss}")
    # PC6: harm by profile and deceptive share (never chains of outcome A), decomposition (D)
    for ds in DS:
        out = {}
        for c in ALL_CELLS:
            nv = [r for r in runs if r["kind"] == "A" and r["cell"] == c and r["b"] == NEVER
                  and r["cond"].endswith(f"ds{ds!r}")]
            dec = [float(np.mean(r["dec_share"])) for r in sorted(nv, key=lambda r: r["seed"])]
            prof = {}
            for p in ("tourist", "local"):
                sh, sur = [], []
                for r in sorted(nv, key=lambda r: r["seed"]):
                    days = r["profile"].values()
                    pu = sum(d["purchases"][p] for d in days)
                    bu = sum(d["buyers"][p] for d in days)
                    sh.append(sum(d["short"][p] for d in days) / pu if pu else None)
                    sur.append((sum(d["value"][p] for d in days) - sum(d["paid"][p] for d in days)
                                - sum(d["inspect"][p] for d in days)) / bu if bu else None)
                prof[p] = {"shortfall_share": mean_ci(sh), "surplus_per_buyer_cents": mean_ci(sur)}
            out[c] = {"deceptive_share": _st(dec), "profile": prof}
        res["pc6"][f"ds{ds:g}"] = out
    D = {r["key"]: r for r in runs if r["kind"] == "D"}
    if D:
        comp = {}
        for c in ALL_CELLS:
            per = {k: [] for k in BR.COMP}
            units_rb = []
            for sd in seeds:
                N = D[f"D|{c}|{sd}|None|{NEVER}"]
                acc = {k: [] for k in BR.COMP}
                ur = []
                for s in samples[sd]:
                    b = G[(c, 0.0)][sd][s]["best_day"]
                    B_ = D[f"D|{c}|{sd}|{s}|{LB.ck(b)}"]
                    if B_["totals"][s] != G[(c, 0.0)][sd][s]["totals"][LB.ck(b)] or \
                            N["totals"][s] != G[(c, 0.0)][sd][s]["never"]:
                        res["flags"].append(f"D|{c}|{sd}|{s}: decomposition chain totals differ from the run's")
                    d = BR.decompose(N, B_, s, int(b), None)
                    for k in BR.COMP:
                        acc[k].append(d["comp"][k])
                    ur.append(d["lost_units"].get("rated_below", 0))
                    if d["pre_bust_differences"]:
                        res["flags"].append(f"D|{c}|{sd}|{s}: buyer records differ before the bust-out")
                for k in BR.COMP:
                    per[k].append(float(np.mean(acc[k])))
                units_rb.append(float(np.mean(ur)))
            comp[c] = {k: _st(v) for k, v in per.items()}
            comp[c]["units_rated_below"] = _st(units_rb)
        res["D"] = comp
    # predictions
    a0, a1 = res["A"]["ds0"]["eff"], res["A"]["ds1"]["eff"]
    b4 = res["B"]["pn400"]["eff"]
    na = {"n": 0, "mean": None, "lo": None, "hi": None}
    b0 = res["B"]["pn0"]["eff"] if "pn0" in res["B"] else {"reading": na, "absR_minus_absI": na, "interaction": na}
    P = {"PC1": (a0["inspection"], -1), "PC2": (a0["absI_minus_absR"], +1),
         "PC3": (b4["reading"], +1), "PC4": (b4["absR_minus_absI"], +1)}
    for k, (st, sg) in P.items():
        res["pred"][k] = {**st, "sign": sg, "verdict": _verdict(st, sg)}
    res["pc5"] = {"A_ds0_interaction": a0["interaction"], "A_ds1_interaction": a1["interaction"],
                  "B_pn400_interaction": b4["interaction"], "B_pn0_interaction": b0["interaction"],
                  "PC1_ds1": {**a1["inspection"], "direction": _verdict(a1["inspection"], -1)},
                  "PC2_ds1": {**a1["absI_minus_absR"], "direction": _verdict(a1["absI_minus_absR"], +1)},
                  "PC3_pn0": {**b0["reading"], "direction": _verdict(b0["reading"], +1)},
                  "PC4_pn0": {**b0["absR_minus_absI"], "direction": _verdict(b0["absR_minus_absI"], +1)}}
    for k, g in res["guard"].items():
        bad = g["stuck_buyers"] + g["parked"] + g["idle_choosers"] + g["cell_bad"]
        if bad:
            res["flags"].append(f"{k}: stuck {g['stuck_buyers']}, parked {g['parked']}, idle {g['idle_choosers']}, "
                                f"cell settings wrong {g['cell_bad']}")
    return res


# ------------------------------------------------------------------ report

def _d(x, unit="$"):
    if x is None:
        return "–"
    v = x / 100 if unit == "$" else x
    s = f"{abs(v):,.2f}" if unit == "$" else f"{abs(v):.3f}"
    return ("−" if v < 0 else "+") + s


def _ci(st, unit="$"):
    if st.get("mean") is None:
        return "–"
    if st.get("lo") is None:
        return _d(st["mean"], unit)
    star = " *" if (st["lo"] > 0 or st["hi"] < 0) else ""
    return f"{_d(st['mean'], unit)} [{_d(st['lo'], unit)}, {_d(st['hi'], unit)}]{star}"


def _tab(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head), *["| " + " | ".join(r) + " |" for r in rows]]


def report(res: dict, meta: dict, gate: str) -> str:
    seeds = res["seeds"]
    L_ = ["# Checking vs reading ratings", "",
          "Spec: `runs/plan_autonomous_2026-11-19.md`, Stage 1 (preregistered at 59e15de, 2026-11-19 12:01 EST). "
          "Engine 0.21.0 (`buyers.profile_overrides`).", "", "## Design (prespecified)", "",
          "- Question: locals both inspect and read ratings, so earlier runs cannot say which behaviour stops switching "
          "supply and which pays for reputation. Separate them.",
          "- Buyers: tourist share 0.4; the other 0.6 are all locals (experts 0). Locals: reads_ratings {yes, no} × "
          "inspect_prob {1.0, 0}, 4 cells. Reference cell: tourist share 1.0. Bargain hunters 0.2 as in the "
          "verification market. Market defaults of the plan: ratings display stars at step 0.02, random tie-break.",
          "- Outcome A, bust-out gain: the verification-run benchmark (3 genuine stalls per seed from "
          "`default_rng([seed, 17])`; candidates never, day 20, 25, 28, 29, 30; unfloored gain primary), market B of the "
          "verification run (2 patrolling inspectors, not uniformed), collectible fines (penalty lag 0), 30 days, "
          "detect_scale 0 and 1.",
          "- Outcome B, reputation effect: E = J(R) − J(W_g) as in `analysis/brand_equity_stars.py` (contract, genuine "
          "tier, royalty 0.10, N 6 from day 10, prior_scope new, 60 days, detect_scale 1), at prior_n 0 and 400.",
          f"- Seeds {meta['seeds_txt']} ({len(seeds)}), fresh, paired across all cells.",
          "- Predictions (verbatim from the plan):",
          *[f"  - {k} ({kind}): {txt}" for k, kind, txt in PREDICTIONS],
          "- Analysis (prespecified): per seed, the mean over sampled stalls or owners; main effects and interactions "
          "from the 2×2 per seed; mean and 95% t over seeds, unadjusted. Implementation (fixed before the pilot): main "
          "effect of inspection = mean(RI, nI) − mean(Rn, nn); of reading = mean(RI, Rn) − mean(nI, nn); interaction = "
          "(RI − Rn) − (nI − nn). PC2 and PC4 compare sizes per seed as sgn(Ī)·I_s − sgn(R̄)·R_s (PC2) and its negative "
          "(PC4), whose mean is |Ī| − |R̄|; supported when the interval is above 0.", "",
          "## Run record", "",
          f"- Engine `{meta['engine_version']}`; commit `{meta['git']['commit']}`; uncommitted at run time: "
          f"{meta['git']['status_porcelain']}",
          f"- Script sha256 `{meta['script_sha256']}`",
          f"- Command: `{meta['command']}`", f"- Tests: {meta['tests']}",
          f"- Python {meta['python']}, numpy {meta['numpy']}, {meta['platform']}",
          f"- {meta['chains']} chains on {meta['workers']} workers (nice 19); wall clock {meta['wall_h']:.2f} h; load "
          f"average {meta['load_start']} at start, {meta['load_end']} at end; memory-guard pauses: {meta['pauses']}",
          "", "## Gate and checks", "", gate or "–", "",
          f"- J identity: {res['identity']['J_pairs'] - res['identity']['J_mismatch']}/{res['identity']['J_pairs']} "
          f"owner-chains to the cent. Genuine-tier price misses: {res['identity']['tier_price_miss']}.",
          f"- Flags: {'; '.join(res['flags']) if res['flags'] else 'none'}.", "",
          "## Predictions", "", "$ per stall (A) or per owner (B), per-seed means; 95% t over seeds, unadjusted.", ""]
    rows = []
    lab = {"PC1": "main effect of inspection, bust-out gain, ds 0", "PC2": "|inspection| − |reading|, bust-out gain, ds 0",
           "PC3": "main effect of reading, E, prior_n 400", "PC4": "|reading| − |inspection|, E, prior_n 400"}
    for k in ("PC1", "PC2", "PC3", "PC4"):
        p = res["pred"][k]
        rows.append([f"**{k}**: {lab[k]} ({'< 0' if p['sign'] < 0 else '> 0'})", _ci(p), p["verdict"]])
    L_ += _tab(["Prediction", "Estimate ($)", "Verdict"], rows) + [""]
    for ds in DS:
        A = res["A"][f"ds{ds:g}"]
        L_ += [f"### Outcome A: bust-out gain, detect_scale {ds:g}", ""]
        L_ += _tab(["Cell", "Unfloored gain ($)", "Floored gain ($)", "Best day (20/25/28/29/30)"],
                   [[CLAB[c], _ci(A["cells"][c]), _ci(A["floored"][c]),
                     " / ".join(str(A["best_day"][c][str(b)]) for b in LB.COL_CANDS)] for c in ALL_CELLS])
        e = A["eff"]
        L_ += ["", f"Main effect of inspection {_ci(e['inspection'])}; of reading {_ci(e['reading'])}; interaction "
                   f"{_ci(e['interaction'])}; |inspection| − |reading| {_ci(e['absI_minus_absR'])}. Reference − "
                   f"neither {_ci(A['ref_minus_nn'])}.", ""]
    for pn in PN:
        B_ = res["B"][f"pn{pn:g}"]
        L_ += [f"### Outcome B: reputation effect E, prior_n {pn:g}", ""]
        L_ += _tab(["Cell", "E ($)", "J R ($)", "J W_g ($)", "J never ($)"],
                   [[CLAB[c], _ci(B_["cells"][c]), _ci(B_["J"][c]["J_R"]), _ci(B_["J"][c]["J_Wg"]),
                     _ci(B_["J"][c]["J_never"])] for c in ALL_CELLS])
        e = B_["eff"]
        L_ += ["", f"Main effect of reading {_ci(e['reading'])}; of inspection {_ci(e['inspection'])}; interaction "
                   f"{_ci(e['interaction'])}; |reading| − |inspection| {_ci(e['absR_minus_absI'])}. Reference − "
                   f"neither {_ci(B_['ref_minus_nn'])}.", ""]
    p5 = res["pc5"]
    L_ += ["### PC5 (exploratory)", "",
           *_tab(["Quantity", "Estimate ($)", "Side of 0 (rule of the matching prediction)"],
                 [["Interaction, bust-out gain, ds 0", _ci(p5["A_ds0_interaction"]), "–"],
                  ["Interaction, bust-out gain, ds 1", _ci(p5["A_ds1_interaction"]), "–"],
                  ["Interaction, E, prior_n 400", _ci(p5["B_pn400_interaction"]), "–"],
                  ["Interaction, E, prior_n 0", _ci(p5["B_pn0_interaction"]), "–"],
                  ["PC1 at ds 1: main effect of inspection", _ci(p5["PC1_ds1"]), p5["PC1_ds1"]["direction"]],
                  ["PC2 at ds 1: |inspection| − |reading|", _ci(p5["PC2_ds1"]), p5["PC2_ds1"]["direction"]],
                  ["PC3 at prior_n 0: main effect of reading", _ci(p5["PC3_pn0"]), p5["PC3_pn0"]["direction"]],
                  ["PC4 at prior_n 0: |reading| − |inspection|", _ci(p5["PC4_pn0"]), p5["PC4_pn0"]["direction"]]]),
           "", "### PC6 (exploratory)", ""]
    for ds in DS:
        P6 = res["pc6"][f"ds{ds:g}"]
        L_ += [f"Never chains of outcome A, detect_scale {ds:g}: deceptive stalls' share of units sold, and per profile the "
               "shortfall share of purchases and surplus per buyer-day (value − paid − inspection cost).", ""]
        L_ += _tab(["Cell", "Deceptive share of units", "Tourists: shortfall share", "Tourists: surplus ($)",
                    "Locals: shortfall share", "Locals: surplus ($)"],
                   [[CLAB[c], _ci(P6[c]["deceptive_share"], "x"),
                     _ci(P6[c]["profile"]["tourist"]["shortfall_share"], "x"),
                     _ci(P6[c]["profile"]["tourist"]["surplus_per_buyer_cents"]),
                     _ci(P6[c]["profile"]["local"]["shortfall_share"], "x"),
                     _ci(P6[c]["profile"]["local"]["surplus_per_buyer_cents"])] for c in ALL_CELLS]) + [""]
    if res["D"]:
        L_ += ["Bust-out decomposition at detect_scale 0 (each stall's best candidate against never; "
               "`analysis/bustout_report.py`), $ per stall:", ""]
        L_ += _tab(["Cell", "Lost: inspected and walked away", "Lost: rating below threshold", "Lost: outranked",
                    "Cost saved", "Premium lost"],
                   [[CLAB[c], _ci(res["D"][c]["lost_inspected"]), _ci(res["D"][c]["lost_rated_below"]),
                     _ci(res["D"][c]["lost_outranked"]), _ci(res["D"][c]["cost_saved"]), _ci(res["D"][c]["premium"])]
                    for c in ALL_CELLS]) + [""]
    L_ += ["## Guard", ""]
    L_ += _tab(["Kind · cell", "Chains", "Stuck", "Parked", "Idle choosers", "Fallbacks", "Cell settings wrong",
                "Seconds per chain"],
               [[k, str(g["chains"]), str(g["stuck_buyers"]), str(g["parked"]), str(g["idle_choosers"]),
                 str(g["fallbacks"]), str(g["cell_bad"]), f"{g['secs'] / max(1, g['chains']):.1f}"]
                for k, g in sorted(res["guard"].items())])
    L_ += ["", "## Reading (written after the results)", "", "READING_PLACEHOLDER", "", "## Caveats", "",
           "CAVEATS_PLACEHOLDER", ""]
    return "\n".join(L_)


# ------------------------------------------------------------------ pilot gates

def _same(a, b, relabel=False) -> bool:
    """Records equal but for their key, cell and timing. relabel (G4): the per-profile tally ("profile", outcome A)
    is compared summed over profiles, since the same buyers are labelled local in one cell and tourist in the other."""
    drop = {"key", "cell", "secs", "cell_ok", *(("profile",) if relabel else ())}
    if relabel and isinstance(a.get("days"), list):
        # D chains store each buyer's profile label: map the nn cell's locals to tourists, then require equality
        a = json.loads(json.dumps(a))
        for d in a["days"]:
            for bu in d.get("buyers", {}).values():
                if bu.get("profile") == "local":
                    bu["profile"] = "tourist"
    if {k: v for k, v in a.items() if k not in drop} != {k: v for k, v in b.items() if k not in drop}:
        return False
    if relabel and "profile" in a:
        def tot(r):
            out = {}
            for day, d in r["profile"].items():
                # float tallies (value) summed in a different order: equal to 1e-6 cents
                out[day] = {f: (round(sum(v.values()), 6) if f != "units" else {s: sum(u.values()) for s, u in v.items()})
                            for f, v in d.items()}
            return out
        return tot(a) == tot(b)
    return True


def gates(runs, g2runs, res, wall, n_full, log) -> dict:
    by = {r["key"]: r for r in runs}
    # G2: overrides at the profile defaults (cell RI) = no overrides
    same = sum(_same(r, by[r["key"].replace(f"|{NOOV}|", "|RI|")]) for r in g2runs)
    g2 = {"pass": same == len(g2runs) and res["identity"]["J_mismatch"] == 0, "chains": len(g2runs), "identical": same,
          "J": res["identity"]}
    # G4: locals that neither read nor inspect = tourists, chain for chain
    nn = [r for r in runs if r["cell"] == "nn"]
    eq = sum(_same(r, by[r["key"].replace("|nn|", f"|{REF}|")], relabel=True) for r in nn)
    g4 = {"pass": eq == len(nn) and len(nn) > 0, "chains": len(nn), "identical": eq}
    # G5
    bad = {k: sum(g[k] for g in res["guard"].values()) for k in ("stuck_buyers", "parked", "idle_choosers", "cell_bad")}
    g5 = {"pass": sum(bad.values()) == 0, **bad}
    # G3: projection from the pilot's throughput (effective seconds per chain by kind)
    secs = {}
    for kind in ("A", "B", "D"):
        rs = [r for r in runs if r["kind"] == kind]
        secs[kind] = float(np.mean([r["secs"] for r in rs])) if rs else 0.0
    eff = wall / max(1e-9, sum(r["secs"] for r in [*runs, *g2runs]) / 4)     # wall per unit of 4-worker work
    proj = {}
    for name, (nseeds, pns) in {"full": (20, 2), "no_pn0": (20, 1), "no_pn0_15seeds": (15, 1)}.items():
        nA, nB, nD = n_full["A"] * nseeds, n_full["B"] * nseeds * pns // 2, n_full["D"] * nseeds
        h = (nA * secs["A"] + nB * secs["B"] + nD * secs["D"]) / 4 * eff / 3600
        proj[name] = {"chains": nA + nB + nD, "hours": h}
    choice = next((k for k in ("full", "no_pn0", "no_pn0_15seeds") if proj[k]["hours"] <= LIMIT_H), None)
    g3 = {"pass": choice is not None, "limit_h": LIMIT_H, "secs_per_chain": secs, "efficiency": eff,
          "projections": proj, "choice": choice}
    g1 = {"pass": not [f for f in res["flags"] if "J identity" in f or "decomposition" in f]}
    return {"G1": g1, "G2": g2, "G3": g3, "G4": g4, "G5": g5}


# ------------------------------------------------------------------ main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=None)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--no-pn0", action="store_true", help="G3 trim 1: drop outcome B's prior_n 0 level")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tests", default="")
    ap.add_argument("--gate", default="")
    ap.add_argument("--min-swap-mb", type=float, default=512)
    ap.add_argument("--min-free-pct", type=float, default=15)
    a = ap.parse_args(argv)
    seeds_txt = a.seeds or (PILOT_SEEDS if a.pilot else MAIN_SEEDS)
    seeds = sorted(parse_seeds(seeds_txt))
    outdir = OUT_PILOT if a.pilot else OUT_MAIN
    os.makedirs(outdir, exist_ok=True)
    log = CR.file_logger(os.path.join(outdir, "check_vs_read_run.log"))
    cache = os.path.join(outdir, "check_vs_read_cache.jsonl")
    meta = {"engine_version": ENGINE_VERSION, "git": _git(), "script_sha256": _script_sha(),
            "command": "python -m analysis.check_vs_read " + " ".join(argv if argv is not None else sys.argv[1:]),
            "tests": a.tests, "python": platform.python_version(), "numpy": np.__version__,
            "platform": platform.platform(), "workers": a.workers, "load_start": _load(), "seeds_txt": seeds_txt,
            "start": time.strftime("%F %T")}
    log(f"check vs read: engine {ENGINE_VERSION}, commit {meta['git']['commit'][:7]}, seeds {seeds_txt}, "
        f"pilot {a.pilot}, no_pn0 {a.no_pn0}; load {meta['load_start']}")
    t0 = time.time()
    samples = {sd: L.sample_stalls(sd) for sd in seeds}
    pns = (400.0,) if a.no_pn0 else PN
    jobs = jobs_main(seeds, samples, pns=pns)
    g2jobs = jobs_g2(seeds[0], samples) if a.pilot else []
    ns = SimpleNamespace(workers=a.workers, min_swap_mb=a.min_swap_mb, min_free_pct=a.min_free_pct)
    runs, p1 = CR.run_chains(ns, [*jobs, *g2jobs], cache, log, job, key)
    main_runs = [r for r in runs if r["cell"] != NOOV]
    g2runs = [r for r in runs if r["cell"] == NOOV]
    G = gains_by(main_runs, seeds, samples)
    djobs = jobs_decomp(G, seeds, samples)
    druns, p2 = CR.run_chains(ns, djobs, cache, log, job, key)
    allruns = [*main_runs, *druns]
    res = analyse_pn(allruns, seeds, samples, pns)
    wall = time.time() - t0
    meta.update(end=time.strftime("%F %T"), load_end=_load(), wall_h=wall / 3600, chains=len(runs) + len(druns),
                pauses=p1 + p2)
    gate_txt = a.gate
    if a.pilot:
        per_seed = {"A": len(ALL_CELLS) * len(DS) * 16, "B": len(ALL_CELLS) * len(PN) * 7, "D": len(ALL_CELLS) * 4}
        gt = gates(allruns, g2runs, res, wall, per_seed, log)
        gt["meta"] = meta
        with open(os.path.join(outdir, "pilot_gates.json"), "w", encoding="utf-8") as f:
            json.dump(gt, f, indent=1, default=str)
        gate_txt = "Pilot: " + ", ".join(f"{g} {'pass' if gt[g]['pass'] else 'FAIL'}" for g in ("G1", "G2", "G3", "G4", "G5"))
        log(gate_txt + f"; G3 choice {gt['G3']['choice']}; projections {json.dumps(gt['G3']['projections'])}")
    with gzip.open(os.path.join(outdir, "check_vs_read.json.gz"), "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": res}, f, default=str)
    with open(os.path.join(outdir, "check_vs_read_summary.md"), "w", encoding="utf-8") as f:
        f.write(report(res, meta, gate_txt))
    log(f"done; {len(res['flags'])} flags; wall {wall / 3600:.2f} h")
    if a.pilot:
        return 0 if all(gt[g]["pass"] for g in ("G1", "G2", "G3", "G4", "G5")) else 2
    return 2 if res["flags"] else 0


def analyse_pn(runs, seeds, samples, pns) -> dict:
    """analyse() with outcome B restricted to the prior_n levels run (G3 trim 1 drops prior_n 0)."""
    global PN
    keep = PN
    PN = tuple(pns)
    try:
        res = analyse(runs, seeds, samples)
    finally:
        PN = keep
    return res


if __name__ == "__main__":
    raise SystemExit(main())
