"""Bust-out decomposition: analysis and report (exploratory, written after the liability run's results;
decisions of 2026-11-11: lost sales valued at the honest margin; per buyer-day causes in the priority exit >
closed > inspected and rejected > rating below the threshold > outranked > other; buyers gained shown as
an offsetting line). Data: runs/bustout_cache.jsonl from analysis/bustout_decomp.py --collect.

For a stall s, its best candidate chain B and the never chain N (same seed and condition), with c_h the
honest unit cost, p_N(d) the never chain's price of s on day d, and for each unit sold in B its price p and
unit cost c:
    gain = profit_B - profit_N
         = sum_B (c_h - c)                                  a. cost saved (units sold after the bust-out)
         + sum_d (U_B(d) - U_N(d)) x (p_N(d) - c_h)          b. sales lost or gained, at the honest margin,
                                                               split per buyer-day by cause
         + sum_B (p - p_N(d))                                c. reputation premium lost (price effect)
         - (ad_B - ad_N)                                      ad spend (yells and whispers)
         - (fines_B - fines_N)                               d. fines charged
         + e                                                 e. left over (0 by construction; reported)
Fines escaped (judgment-proof arm) are reported as a memo: they are not in profit.
"""
from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict

import numpy as np

import analysis.liability as L
from analysis.bustout_decomp import CACHE, LEVELS, NEVER, SEEDS, best_table
from analysis.capture import _frame
from analysis.counterfeit import _ci, _d, _num, _t
from engine import ENGINE_VERSION
from engine.metrics import mean_ci

CAUSES = ["exit", "closed", "inspected", "rated_below", "outranked", "other"]
CAUSE_LAB = {"exit": "after exit", "closed": "closed after a catch", "inspected": "inspected and walked away",
             "rated_below": "rating below threshold", "outranked": "outranked by another stall",
             "other": "other (no recorded cause)"}
COMP = ["cost_saved", *[f"lost_{c}" for c in CAUSES], "gained", "premium", "ad", "fines"]
COMP_LAB = {"cost_saved": "a. cost saved on units sold after the bust-out",
            **{f"lost_{c}": f"b. lost: {CAUSE_LAB[c]}" for c in CAUSES},
            "gained": "b. buyers gained", "premium": "c. reputation premium lost (price)",
            "ad": "ad spend (yells, whispers)", "fines": "d. fines charged"}
SHORT = {"cost_saved": "cost saved", "lost_exit": "lost: after exit", "lost_closed": "lost: closed",
         "lost_inspected": "lost: inspected", "lost_rated_below": "lost: rating &lt; τ", "lost_outranked": "lost: outranked",
         "lost_other": "lost: other", "gained": "buyers gained", "premium": "premium lost", "ad": "ad spend",
         "fines": "fines"}
OUT_MD, OUT_CSV = "runs/bustout_decomposition.md", "runs/bustout_decomposition.csv"


def _units(w) -> int:
    return sum(b[0] for b in w.get("buys", []))


def cause(wb, q_req, exited_or_absent) -> str:
    if exited_or_absent:
        return "exit"
    if wb.get("met_closed"):
        return "closed"
    if wb.get("inspected_q") is not None and wb["inspected_q"] < q_req:
        return "inspected"
    if wb.get("rated_below_tau"):
        return "rated_below"
    if wb.get("outranked"):
        return "outranked"
    return "other"


def decompose(N: dict, B: dict, s: str, bust_day: int, exit_day: int | None) -> dict:
    comp = defaultdict(float)
    lost_units = defaultdict(int)
    gained_units = 0
    c_h = N["days"][0]["stalls"][s]["unit_cost_morning"]
    prof = {"N": 0, "B": 0}
    win = {"U_N": 0, "U_B": 0, "U_B_trading": 0, "U_N_trading": 0, "m_N": 0.0, "m_B": 0.0, "base": None}
    pre_diff = 0
    for dn, db in zip(N["days"], B["days"]):
        d = dn["day"]
        sn, sb = dn["stalls"][s], db["stalls"][s]
        for k, st in (("N", sn), ("B", sb)):
            prof[k] += st["revenue_cents"] - st["cost_cents"] - st["ad_spend_cents"] - st["penalties_cents"] \
                - st["switch_cost_cents"]
        pN = sn["price_cents"]
        comp["ad"] -= sb["ad_spend_cents"] - sn["ad_spend_cents"]
        comp["fines"] -= sb["penalties_cents"] - sn["penalties_cents"]
        for b in (x for v in db["buyers"].values() if s in v["w"] for x in v["w"][s].get("buys", [])):
            u, p, c, _ = b
            comp["cost_saved"] += u * (c_h - c)
            comp["premium"] += u * (p - pN)
            if d >= bust_day:
                win["m_B"] += u * (p - c)
        margin = pN - c_h
        pids = {pid for pid, v in dn["buyers"].items() if s in v["w"]} | \
               {pid for pid, v in db["buyers"].items() if s in v["w"]}
        for pid in sorted(pids):
            vn, vb = dn["buyers"].get(pid), db["buyers"].get(pid)
            wn = vn["w"].get(s, {}) if vn else {}
            wb = vb["w"].get(s) if vb else None
            un, ub = _units(wn), _units(wb or {})
            if d < bust_day and (un != ub or (wn != (wb or {}))):
                pre_diff += 1
            delta = ub - un
            if delta < 0:
                if wb is None and not sb["exited"]:
                    comp["_absent_not_exited"] += 1
                cz = cause(wb or {}, (vn or vb)["q_req"], sb["exited"] or wb is None)
                lost_units[cz] += -delta
                comp[f"lost_{cz}"] += delta * margin
            elif delta > 0:
                gained_units += delta
                comp["gained"] += delta * margin
        if d >= bust_day:
            un_d = sum(_units(v["w"][s]) for v in dn["buyers"].values() if s in v["w"])
            ub_d = sum(_units(v["w"][s]) for v in db["buyers"].values() if s in v["w"])
            win["U_N"] += un_d
            win["U_B"] += ub_d
            win["m_N"] += un_d * (pN - c_h)
            if exit_day is None or d <= exit_day:
                win["U_B_trading"] += ub_d
                win["U_N_trading"] += un_d
    gain = prof["B"] - prof["N"]
    e = gain - sum(comp[k] for k in COMP)
    absent = int(comp.pop("_absent_not_exited", 0))
    honest_m = win["m_N"] / win["U_N"] if win["U_N"] else None
    bust_m = win["m_B"] / win["U_B"] if win["U_B"] else None
    return {"gain": gain, "profit_N": prof["N"], "profit_B": prof["B"], "comp": {k: comp[k] for k in COMP}, "e": e,
            "lost_units": dict(lost_units), "gained_units": gained_units, "pre_bust_differences": pre_diff,
            "absent_not_exited": absent,
            "kept": win["U_B"] / win["U_N"] if win["U_N"] else None,
            "kept_trading": win["U_B_trading"] / win["U_N_trading"] if win["U_N_trading"] else None,
            "honest_margin": honest_m, "bust_margin": bust_m,
            "break_even": honest_m / bust_m if honest_m is not None and bust_m else None,
            "U_N": win["U_N"], "U_B": win["U_B"]}


def load_cache() -> dict:
    out = {}
    with open(CACHE, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            out[r["key"]] = r
    return out


def analyse() -> tuple[dict, list]:
    best = best_table()
    C = load_cache()
    rows, checks = [], {"totals_match": 0, "totals_mismatch": [], "never_match": 0, "pre_bust_differences": 0}
    samples = {sd: L.sample_stalls(sd) for sd in SEEDS}
    for cond in L.conds(LEVELS):
        arm, t, ds = L.parts(cond)
        for sd in SEEDS:
            N = C[f"{cond}|{sd}|None|never"]
            for s in samples[sd]:
                bt = best[(arm, t, ds, sd, s)]
                cand = bt["best"]
                B = C[f"{cond}|{sd}|{s}|{cand}"]
                if N["totals"][s] == bt["never_total_cents"]:
                    checks["never_match"] += 1
                if B["totals"][s] == bt["best_total_cents"]:
                    checks["totals_match"] += 1
                else:
                    checks["totals_mismatch"].append(B["key"])
                b0 = int(cand.split("h")[0])
                ex = b0 + int(cand.split("h")[1]) - 1 if "h" in cand else None
                r = decompose(N, B, s, b0, ex)
                checks["pre_bust_differences"] += r["pre_bust_differences"]
                rows.append({"arm": arm, "t": t, "ds": ds, "seed": sd, "stall": s, "best": cand,
                             "fines_escaped": bt["best_fines_uncollectible_cents"],
                             "base": B["days"][0]["stalls"][s]["price_cents"], **r})
    return checks, rows


def by_cond(rows) -> dict:
    out = {}
    for cond in L.conds(LEVELS):
        arm, t, ds = L.parts(cond)
        rs = [r for r in rows if (r["arm"], r["t"], r["ds"]) == (arm, t, ds)]
        per_seed = lambda f: [float(np.mean([f(r) for r in rs if r["seed"] == sd])) for sd in SEEDS]
        ok = lambda f: [float(np.mean(v)) for sd in SEEDS if (v := [f(r) for r in rs if r["seed"] == sd and f(r) is not None])]
        out[cond] = {"gain": mean_ci(per_seed(lambda r: r["gain"])),
                     "comp": {k: mean_ci(per_seed(lambda r, k=k: r["comp"][k])) for k in COMP},
                     "e": max(abs(r["e"]) for r in rs),
                     "fines_escaped": mean_ci(per_seed(lambda r: r["fines_escaped"])),
                     "kept": mean_ci(ok(lambda r: r["kept"])),
                     "kept_trading": mean_ci(ok(lambda r: r["kept_trading"])),
                     "break_even": mean_ci(ok(lambda r: r["break_even"])),
                     "honest_margin_base": mean_ci(ok(lambda r: r["honest_margin"] / r["base"]
                                                      if r["honest_margin"] is not None else None)),
                     "bust_margin_base": mean_ci(ok(lambda r: r["bust_margin"] / r["base"]
                                                    if r["bust_margin"] is not None else None)),
                     "above_break_even": sum(1 for r in rs if r["kept"] is not None and r["break_even"] is not None
                                             and r["kept"] > r["break_even"]),
                     "pre_fines_positive": sum(1 for r in rs if r["gain"] - r["comp"]["fines"] > 0),
                     "n": len(rs),
                     "lost_units": {c: float(np.mean([r["lost_units"].get(c, 0) for r in rs])) for c in CAUSES},
                     "gained_units": float(np.mean([r["gained_units"] for r in rs])),
                     "U_N": float(np.mean([r["U_N"] for r in rs])), "U_B": float(np.mean([r["U_B"] for r in rs]))}
    return out


# ------------------------------------------------------------------ plot

def plot_waterfall_svg(res: dict, t: str) -> str:
    """Small multiples (liability arm x detect_scale): a horizontal waterfall of the mean components, from 0 to
    the mean gain. One shared x scale."""
    conds = [c for c in L.conds(LEVELS) if L.parts(c)[1] == t]
    steps = COMP + ["gain"]
    vals = []
    for c in conds:
        run = 0.0
        for k in COMP:
            m = res[c]["comp"][k]["mean"] / 100
            vals += [run, run + m]
            run += m
        vals.append(res[c]["gain"]["mean"] / 100)
    lo, hi = min(vals + [0]), max(vals + [0])
    pad = (hi - lo) * 0.06
    lo, hi = lo - pad, hi + pad
    rowh, pw, gapx, gapy = 15, 215, 40, 56
    labw = 150
    top = 132
    ph = rowh * len(steps)
    W = labw + 3 * (pw + gapx) + 20
    H = top + 2 * (ph + gapy) + 70
    out = _frame(f"Where the bust-out's gain goes: {L.VLAB[t]}",
                 "Mean over stall-seeds at each stall's best candidate, $ per stall over 30 days; bars run from the "
                 "running total",
                 ["Bazaar engine 0.15.0 (the liability run, 5b60720, replayed with an observer). Seeds 230–249, 3 "
                  "sampled stalls per seed; exploratory, written after the results.",
                  "Lost sales at the honest margin (never chain's price − honest unit cost); causes per buyer-day in the "
                  "order exit, closed, inspected, rating below τ, outranked, other."],
                 W=W, H=H, desc="Waterfall of the bust-out gain's components by liability arm and detect_scale.")
    for i, arm in enumerate(L.ARMS):
        for j, ds in enumerate(LEVELS):
            c = f"{arm}|{t}|ds{ds!r}"
            x0 = labw + j * (pw + gapx)
            y0 = top + i * (ph + gapy)
            X = lambda v, x0=x0: x0 + (v - lo) / (hi - lo) * pw
            out.append(f'<text class="lb" x="{x0}" y="{y0 - 10}">{L.ARMS[arm]}, scale {ds:g}</text>')
            out.append(f'<line class="zero" x1="{X(0):.1f}" y1="{y0}" x2="{X(0):.1f}" y2="{y0 + ph}"/>')
            run = 0.0
            for r, k in enumerate(steps):
                y = y0 + r * rowh
                if j == 0:
                    out.append(f'<text class="k" x="{x0 - 8}" y="{y + rowh - 4}" text-anchor="end">'
                               f'{SHORT.get(k, "= gain")}</text>')
                if k == "gain":
                    g = res[c]["gain"]["mean"] / 100
                    a, b = sorted((0, g))
                    out.append(f'<rect class="hlb" x="{X(a):.1f}" y="{y + 2}" width="{max(X(b) - X(a), 0.8):.1f}" '
                               f'height="{rowh - 4}"/>')
                    tx = X(b) + 4 if g >= 0 else X(a) - 4
                    out.append(f'<text class="k" x="{tx:.1f}" y="{y + rowh - 4}" '
                               f'text-anchor="{"start" if g >= 0 else "end"}">{_d(res[c]["gain"]["mean"], True)}</text>')
                    continue
                m = res[c]["comp"][k]["mean"] / 100
                a, b = sorted((run, run + m))
                cls = "barp" if m >= 0 else "barn"
                out.append(f'<rect class="{cls}" x="{X(a):.1f}" y="{y + 3}" width="{max(X(b) - X(a), 0.6):.1f}" '
                           f'height="{rowh - 6}"/>')
                run += m
            # x axis
            ya = y0 + ph + 6
            out.append(f'<line class="ax" x1="{x0}" y1="{ya}" x2="{x0 + pw}" y2="{ya}"/>')
            step = _step(hi - lo)
            v = math.ceil(lo / step) * step
            while v <= hi + 1e-9:
                lab = "0" if abs(v) < 1e-9 else f"{v:+,.0f}".replace("-", "−")
                out.append(f'<text class="k" x="{X(v):.1f}" y="{ya + 14}" text-anchor="middle">{lab}</text>')
                v += step
    out.append("</svg>")
    s = "\n".join(out) + "\n"
    return s.replace("</style>", " .barp{fill:#7a7a7a} .barn{fill:#bbb} .hlb{fill:#e15759} "
                                 "@media (prefers-color-scheme: dark){.barp{fill:#999} .barn{fill:#555} "
                                 ".hlb{fill:#fc8d62}}</style>", 1)


def _step(span):
    raw = span / 4
    e = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if m * e >= raw:
            return m * e
    return 10 * e


# ------------------------------------------------------------------ report

def _cl(c):
    arm, t, ds = L.parts(c)
    return f"{L.ARMS[arm]}, {t}, {ds:g}"


def write(checks, rows, res, meta) -> None:
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["liability", "verification", "detect_scale", "seed", "stall", "best", "gain_cents",
                    *[f"{k}_cents" for k in COMP], "residual_cents", "fines_escaped_cents", "units_never_window",
                    "units_bust_window", "kept_share", "kept_share_trading_days", "honest_margin_cents",
                    "bust_margin_cents", "break_even_share", *[f"lost_units_{c}" for c in CAUSES], "gained_units"])
        for r in rows:
            w.writerow([r["arm"], r["t"], f"{r['ds']:g}", r["seed"], r["stall"], r["best"], r["gain"],
                        *[round(r["comp"][k]) for k in COMP], round(r["e"]), r["fines_escaped"], r["U_N"], r["U_B"],
                        "" if r["kept"] is None else f"{r['kept']:.4f}",
                        "" if r["kept_trading"] is None else f"{r['kept_trading']:.4f}",
                        "" if r["honest_margin"] is None else f"{r['honest_margin']:.1f}",
                        "" if r["bust_margin"] is None else f"{r['bust_margin']:.1f}",
                        "" if r["break_even"] is None else f"{r['break_even']:.4f}",
                        *[r["lost_units"].get(c, 0) for c in CAUSES], r["gained_units"]])
    svgs = []
    for t in L.VER:
        name = f"bustout_waterfall_{t}.svg"
        with open(os.path.join("runs", name), "w", encoding="utf-8") as f:
            f.write(plot_waterfall_svg(res, t))
        svgs.append((name, f"waterfall of the bust-out gain, {L.VLAB[t]}"))
    old = open(OUT_MD, encoding="utf-8").read() if os.path.exists(OUT_MD) else None
    M = ["# Bust-out decomposition (exploratory)", "",
         "Spec \"Part 1: bust-out decomposition\" (2026-11-11). **Exploratory, written after the results** of the "
         "liability run (`runs/liability_summary.md`, 5b60720). Analysis only: no engine change.", "",
         "## Method", "",
         "- Every condition of the liability run (2 liability arms × 2 verification levels × detect_scale {0, 0.1, 1}), "
         "every sampled stall-seed (seeds 230–249, 3 stalls): the never chain and the chain of the stall's best "
         "candidate (from `runs/liability.csv`) were replayed at engine 0.15.0 with an observer that wraps "
         "`purchase`, `decide` (buyers) and `search_decide` and changes nothing (`analysis/bustout_decomp.py`).",
         "- Gain = profit(best) − profit(never), split exactly (decided 2026-11-11):",
         "  - a. cost saved: for each unit sold in the best chain, honest unit cost − its unit cost;",
         "  - b. sales lost or gained, valued at the honest margin (the never chain's price that day − honest unit "
         "cost), per buyer-day: a buyer who bought fewer units from the stall than in the never chain is lost, its cause "
         "the first that applies of: the stall had exited; the buyer met it closed after a catch; inspected it and "
         "found it below its Q_req; saw its rating below τ = 0.5; it was among the buyer's candidates and another "
         "stall was chosen; other. A buyer who bought more is gained;",
         "  - c. reputation premium lost: for each unit sold, its price − the never chain's price that day;",
         "  - ad spend difference, and d. fines charged; e. anything left over (0 by construction: reported).",
         "- Kept share = units sold in the best chain from the bust-out day to day 30 ÷ units in the never chain over "
         "the same days (judgment-proof: also over the days before the exit). Break-even = honest margin ÷ busted margin "
         "from the actual prices and costs (units-weighted, same window): a bust-out pays before fines only if the kept "
         "share exceeds it.",
         "- Per condition: per seed the mean over its 3 stalls; mean and 95% t-interval over the 20 seeds, unadjusted.",
         ""]
    M += ["## Run record and checks", "",
          f"- Replay: {meta['chains']} chains (one never chain and the best-candidate chain per stall-seed, every "
          f"condition), engine 0.15.0 at 5b60720, {meta['workers']} workers at nice 19, wall clock {meta['wall']}; log "
          "`runs/bustout_run.log`.",
          f"- The stall's 30-day total in the replayed best chain equals the saved run in "
          f"{checks['totals_match']} of {len(rows)} stall-seeds; the never total in {checks['never_match']} of {len(rows)}.",
          f"- Buyer records before the bust-out day that differ between the two chains: {checks['pre_bust_differences']} "
          "(should be 0: the chains are identical until the bust-out).",
          f"- Largest |e| (left over) in any stall-seed: {max(abs(r['e']) for r in rows):.0f} cents.", ""]
    M += ["## Decomposition by condition ($ per stall over 30 days)", ""]
    head = ["Component", *[_cl(c) for c in L.conds(LEVELS)]]
    for t in L.VER:
        cs = [c for c in L.conds(LEVELS) if L.parts(c)[1] == t]
        M += [f"**{L.VLAB[t]}**", "",
              *_t(["Component", *[f"{L.ARMS[L.parts(c)[0]]}, {L.parts(c)[2]:g}" for c in cs]],
                  [[COMP_LAB[k], *[_ci(res[c]["comp"][k], _d) for c in cs]] for k in COMP] +
                  [["**= gain**", *[f"**{_ci(res[c]['gain'], _d)}**" for c in cs]],
                   ["e. left over (largest, cents)", *[f"{res[c]['e']:.0f}" for c in cs]],
                   ["memo: fines escaped (uncollectible)", *[_ci(res[c]["fines_escaped"], _d, signed=False) for c in cs]]]),
              ""]
    M += ["## Units lost by cause (mean per stall-seed)", "",
          *_t(["Condition", "Units, never (window)", "Units, best (window)", *[CAUSE_LAB[c] for c in CAUSES], "gained"],
              [[_cl(c), f"{res[c]['U_N']:.1f}", f"{res[c]['U_B']:.1f}",
                *[f"{res[c]['lost_units'][k]:.1f}" for k in CAUSES], f"{res[c]['gained_units']:.1f}"]
               for c in L.conds(LEVELS)]), ""]
    M += ["## Kept share against break-even", "",
          "The back-of-envelope said: honest margin ≈ 0.29 × base, busted margin ≈ 0.55 × base, so a bust-out pays only "
          "if it keeps more than ≈ 52% of its sales, before fines. Margins below are in units of the base price.", "",
          *_t(["Condition", "Honest margin (× base)", "Busted margin (× base)", "Break-even share", "Kept share",
               "Kept share, trading days", "Stall-seeds above break-even", "Stall-seeds with gain before fines > 0"],
              [[_cl(c), _ci(res[c]["honest_margin_base"], _num(3), signed=False),
                _ci(res[c]["bust_margin_base"], _num(3), signed=False),
                _ci(res[c]["break_even"], _num(3), signed=False), _ci(res[c]["kept"], _num(3), signed=False),
                _ci(res[c]["kept_trading"], _num(3), signed=False),
                f"{res[c]['above_break_even']} of {res[c]['n']}", f"{res[c]['pre_fines_positive']} of {res[c]['n']}"]
               for c in L.conds(LEVELS)]), ""]
    for path, alt in svgs:
        M += [f"![{alt}]({path})", ""]
    reading = "READING_PLACEHOLDER"
    if old and "## Reading (written after the results)\n\n" in old:
        reading = old.split("## Reading (written after the results)\n\n", 1)[1].rstrip()
    M += ["## Reading (written after the results)", "", reading, ""]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(M))


def analyse_and_report() -> None:
    checks, rows = analyse()
    res = by_cond(rows)
    meta = {"chains": len(load_cache()), "workers": 4, "wall": "see runs/bustout_run.log"}
    if os.path.exists("runs/bustout_run.log"):
        lines = open("runs/bustout_run.log", encoding="utf-8").read().splitlines()
        done = [x for x in lines if " done; wall " in x]
        if done:
            meta["wall"] = done[-1].split(" done; wall ")[1].split(";")[0]
    write(checks, rows, res, meta)
    print(json.dumps({"checks": {k: (v if not isinstance(v, list) else len(v)) for k, v in checks.items()},
                      "rows": len(rows)}))


if __name__ == "__main__":
    analyse_and_report()
