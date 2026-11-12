"""Two exploratory checks on the licensing run (runs/licensing_summary.md, engine 0.16.0, ddd6fc2), plus a
royalty recompute. Written after the licensing results. Analysis only: no engine change.

(a) Extra sales the brand added: for every licensee, its ledger from the licence day to day 30 in the
    licensed chain against the never chain (where it trades under its own name and type); royalties on
    extra units only against royalties paid; what the other stalls gain or lose in units.
(b) Would the licensee sign? It accepts if its profit from the licence day, licensed (royalties paid and
    fines it bears counted), is at least its never-chain profit over the same days. The owner's best
    option and gain are recomputed over options every licensee accepts (none: never, gain 0).
Royalty: the royalty enters only stall profit, which no decision in these chains reads (see the
report); a replay of seed 250, cheap, t100, detect_scale 1, every owner and option at royalty 0.05 and
0.25 must match the 0.15 chains in every stall's units, prices and ledger except royalties and profit.
Then owner gain and licensee profit are recomputed exactly at royalty 0.05, 0.10, 0.15, 0.25 from each
licensee's day-by-day units and price (royalty = units x round(r x price), as the engine charges it).

Replay: never chains, and the licensed chains of the six conditions with the owner not liable, at 0.16.0
with an observer that changes nothing (it snapshots every stall's ledger before the end-of-day reset).
Owner liable: replayed for seeds 250-251 only, to show the chains trade identically and differ only in
who pays fines at licensees; for every seed the liable ledger is derived from the not-liable one by
moving those fines to the owner, and the derived owner totals must equal the saved run's in every
stall-seed. Replayed owner totals (never and licensed) must equal the saved ones in every stall-seed.

    nohup nice -n 19 .venv/bin/python -m analysis.licensing_checks --royalty-check > runs/licensing_checks_stdout.log 2>&1 &
    nohup nice -n 19 .venv/bin/python -m analysis.licensing_checks --collect >> runs/licensing_checks_stdout.log 2>&1 &
    .venv/bin/python -m analysis.licensing_checks --analyse
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

import numpy as np

import analysis.liability as LB
import analysis.licensing as L
from analysis.capture import memory_state
from analysis.counterfeit import _ci, _d, _git, _load, _num
from engine import ENGINE_VERSION, bazaar, benchmark
from engine import days as DAYS
from engine.config import load
from engine.metrics import mean_ci

NEVER = benchmark.NEVER
SEEDS = list(range(250, 270))
RATES = (0.05, 0.10, 0.15, 0.25)
HEADLINE = 0.10
BASE_R = 0.15
FREE_CONDS = [c for c in L.LIC_CONDS if c.endswith("|free")]
LIABLE_CONDS = [c for c in L.LIC_CONDS if c.endswith("|liable")]
LIABLE_SEEDS = (250, 251)
RCHECK = ("cheap|t100|ds1.0|free", 250)
CACHE = "runs/licensing_checks_cache.jsonl"
SAVED = "runs/licensing_cache.jsonl"
RUNLOG = "runs/licensing_checks_run.log"
WINDOWS = (1, 10, 20)
# ledger columns per stall and window
COLS = ("units", "revenue", "cost", "ad", "fines", "switch", "roy_paid", "roy_recv", "catches", "profit")
C = {k: i for i, k in enumerate(COLS)}


def _rk(r: float) -> str:
    return f"{r:.2f}"


# ------------------------------------------------------------------ chains
# job: (kind, cond, seed, stall, option, royalty); kind "never" | "lic"; cond a LIC_CONDS entry for "lic",
# L.base_key(t, ds) for "never".

def _cfg(job):
    kind, cond, seed, stall, opt, r = job
    if kind == "never":
        t, d = cond.split("|")
        ov = L.overrides(t, float(d[2:]))
    else:
        q, t, ds, lia = L.parts(cond)
        ov = L.overrides(t, ds, q, lia)
    ov = [x for x in ov if not x.startswith("licensing.royalty=")] + [f"licensing.royalty={r!r}", f"seed={seed}"]
    c = load(None, ov, mode="bazaar")
    return benchmark.licence_config(c, stall if kind == "lic" else None, opt if kind == "lic" else NEVER)


def _key(j) -> str:
    kind, cond, seed, stall, opt, r = j
    return f"{kind}|{cond}|{seed}|{stall}|{L.ok(opt)}|r{_rk(r)}"


def _profit(st) -> int:
    return DAYS.stall_profit(st)


def _job(job) -> dict:
    kind, cond, seed, stall, opt, r = job
    snaps = []
    orig = DAYS.reset_for_day

    def tap(cfg, stalls):            # observer: reads the day's ledgers, changes nothing
        snaps.append({st.sid: (st.units_sold, st.revenue_cents, st.cost_cents, st.ad_spend_cents, st.penalties_cents,
                               st.switch_cost_cents, st.royalty_paid_cents, st.royalty_received_cents, st.catches,
                               _profit(st), st.price_cents, st.licensed_from, st.category, st.stype)
                      for st in stalls})
        return orig(cfg, stalls)

    DAYS.reset_for_day = tap
    try:
        out = bazaar.run(_cfg(job))
    finally:
        DAYS.reset_for_day = orig
    assert len(snaps) == len(out["days"]) == L.DAYS
    sids = sorted(snaps[0])
    meta = {s: [snaps[0][s][12], snaps[0][s][13]] for s in sids}
    lic = {s: v[11] for s, v in snaps[-1].items() if v[11] is not None}
    win = {str(w): {s: [0] * len(COLS) for s in sids} for w in WINDOWS}
    roy = {s: {_rk(x): 0 for x in RATES} for s in lic}
    roy_mismatch = profit_mismatch = 0
    dig_trade, dig_nonroy = [], []
    for d, snap in enumerate(snaps, start=1):
        prof = out["days"][d - 1]["outcome"]["brands"]["profit_by_stall_cents"]
        for s in sids:
            v = snap[s]
            if v[9] != prof[s]:
                profit_mismatch += 1
            for w in WINDOWS:
                if d >= w:
                    row = win[str(w)][s]
                    for i in range(len(COLS)):
                        row[i] += v[i]
            if s in lic and v[11] is not None:
                if v[6] != v[0] * int(round(float(r) * v[10])):
                    roy_mismatch += 1
                for x in RATES:
                    roy[s][_rk(x)] += v[0] * int(round(float(x) * v[10]))
        dig_trade.append(hashlib.sha1(repr([(s, snap[s][0], snap[s][1], snap[s][2], snap[s][3], snap[s][5],
                                               snap[s][8], snap[s][10]) for s in sids]).encode()).hexdigest()[:16])
        dig_nonroy.append(hashlib.sha1(repr([(s, *snap[s][:6], snap[s][8], snap[s][10]) for s in sids]).encode()
                                       ).hexdigest()[:16])
    watch = L.sample_stalls(seed) if kind == "never" else [stall]
    return {"key": _key(job), "kind": kind, "cond": cond, "seed": seed, "stall": stall, "o": L.ok(opt),
            "royalty": float(r), "meta": meta, "lic": lic, "win": win, "roy": roy,
            "roy_mismatch": roy_mismatch, "profit_mismatch": profit_mismatch,
            "totals": {s: benchmark.stall_total(out, s) for s in watch},
            "dig_trade": dig_trade, "dig_nonroy": dig_nonroy}


def jobs(royalty_check_only=False) -> list[tuple]:
    samples = {sd: L.sample_stalls(sd) for sd in SEEDS}
    out = []
    cond, sd = RCHECK
    for r in (BASE_R, 0.05, 0.25):
        for s in samples[sd]:
            for o in L.LIC_OPTS:
                out.append(("lic", cond, sd, s, o, r))
    if royalty_check_only:
        return out
    for sd in SEEDS:
        for t, ds in L.BASES:
            out.append(("never", L.base_key(t, ds), sd, None, NEVER, BASE_R))
        for cond in FREE_CONDS + (LIABLE_CONDS if sd in LIABLE_SEEDS else []):
            for s in samples[sd]:
                for o in L.LIC_OPTS:
                    j = ("lic", cond, sd, s, o, BASE_R)
                    if j not in out:
                        out.append(j)
    return out


def run_chains(a, js, log) -> dict:
    done = {}
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            for line in f:
                done[json.loads(line)["key"]] = True
    todo = [j for j in js if _key(j) not in done]
    log(f"{len(js)} chains, {len(done)} cached, {len(todo)} to run; workers {a.workers}")
    t0, n = time.time(), 0
    with open(CACHE, "a", encoding="utf-8") as cache, \
            ProcessPoolExecutor(a.workers, initializer=LB._lower_priority) as ex:
        it, live, exhausted = iter(todo), set(), False
        while live or not exhausted:
            while not exhausted and len(live) < a.workers:
                good, st = LB.memory_ok(a)
                if not good:
                    if not live:
                        log(f"paused (memory {st}); waiting 60 s")
                        time.sleep(60)
                        continue
                    break
                j = next(it, None)
                if j is None:
                    exhausted = True
                    break
                live.add(ex.submit(_job, j))
            if not live:
                continue
            fin, live = wait(live, timeout=60, return_when=FIRST_COMPLETED)
            for fu in fin:
                r = fu.result()
                done[r["key"]] = True          # the records stay on disk (low RAM)
                cache.write(json.dumps(r, separators=(",", ":")) + "\n")
                cache.flush()
                n += 1
                if n % 50 == 0 or n == len(todo):
                    log(f"{n}/{len(todo)} chains, {time.time() - t0:.0f} s, load {_load()}, memory {memory_state()}")
    return done


# ------------------------------------------------------------------ checks on the replay

def load_cache() -> dict:
    done = {}
    with open(CACHE, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            done[r["key"]] = r
    return done


def saved_totals() -> dict:
    """{(kind, cond, seed, stall, option): {stall: total}} from the licensing run's cache."""
    out = {}
    with open(SAVED, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["kind"] in ("never", "lic"):
                out[(r["kind"], r["cond"], r["seed"], r["stall"], r["o"])] = r["totals"]
    return out


def royalty_check(done) -> dict:
    cond, sd = RCHECK
    rows = []
    for s in L.sample_stalls(sd):
        for o in L.LIC_OPTS:
            base = done[_key(("lic", cond, sd, s, o, BASE_R))]
            for r in (0.05, 0.25):
                x = done[_key(("lic", cond, sd, s, o, r))]
                days_equal = sum(a == b for a, b in zip(base["dig_nonroy"], x["dig_nonroy"]))
                cols_equal = all(base["win"][w][st][C[c]] == x["win"][w][st][C[c]]
                                 for w in base["win"] for st in base["win"][w]
                                 for c in COLS if c not in ("roy_paid", "roy_recv", "profit"))
                roy_moved = any(base["win"]["1"][st][C["roy_paid"]] != x["win"]["1"][st][C["roy_paid"]]
                                for st in base["lic"])
                rows.append({"owner": s, "option": L.ok(o), "royalty": r, "days_identical": days_equal,
                             "ledger_identical_except_royalty": cols_equal, "royalties_differ": roy_moved,
                             "licensees_same": base["lic"] == x["lic"],
                             "royalty_exact": x["roy_mismatch"] == 0 and base["roy_mismatch"] == 0})
    ok = all(r["days_identical"] == L.DAYS and r["ledger_identical_except_royalty"] and r["licensees_same"]
             and r["royalty_exact"] for r in rows)
    return {"rows": rows, "pass": ok}


def derive_liable(free: dict, cond: str) -> dict:
    """The liable chain's ledger from the not-liable one: fines at licensees from the licence day move to
    the owner (closure still falls on the licensee). Valid because no decision reads who paid."""
    x = json.loads(json.dumps(free))
    x["cond"] = cond
    b = int(free["o"].split("x")[1])
    owner = free["stall"]
    for w in WINDOWS:
        k = str(max(w, b))        # the fines moved in window w are those from day max(w, b) on
        moved = 0
        for s in free["lic"]:
            f = free["win"][k][s][C["fines"]]
            moved += f
            x["win"][str(w)][s][C["fines"]] -= f
            x["win"][str(w)][s][C["profit"]] += f
        x["win"][str(w)][owner][C["fines"]] += moved
        x["win"][str(w)][owner][C["profit"]] -= moved
        if w == 1:
            x["totals"] = {owner: free["totals"][owner] - moved}
    x["derived"] = True
    return x


def verify(done, saved) -> tuple[dict, dict]:
    """Replayed and derived owner totals against the saved run; liable replays against the derived
    chains. Returns (chains by (cond, seed, stall, option) and never by (base, seed), report)."""
    samples = {sd: L.sample_stalls(sd) for sd in SEEDS}
    rep = {"never": [0, 0], "free": [0, 0], "liable_derived": [0, 0], "liable_replay": [0, 0, 0],
           "roy_mismatch": 0, "profit_mismatch": 0, "fails": []}
    nev, ch = {}, {}
    for sd in SEEDS:
        for t, ds in L.BASES:
            bk = L.base_key(t, ds)
            r = done[_key(("never", bk, sd, None, NEVER, BASE_R))]
            sv = saved[("never", bk, sd, None, NEVER)]
            for s in samples[sd]:
                rep["never"][0] += 1
                if r["totals"][s] == sv[s]:
                    rep["never"][1] += 1
                else:
                    rep["fails"].append(("never", bk, sd, s))
            rep["profit_mismatch"] += r["profit_mismatch"]
            nev[(bk, sd)] = r
        for cond in FREE_CONDS:
            for s in samples[sd]:
                for o in L.LIC_OPTS:
                    r = done[_key(("lic", cond, sd, s, o, BASE_R))]
                    rep["free"][0] += 1
                    if r["totals"][s] == saved[("lic", cond, sd, s, L.ok(o))][s]:
                        rep["free"][1] += 1
                    else:
                        rep["fails"].append((cond, sd, s, L.ok(o)))
                    rep["roy_mismatch"] += r["roy_mismatch"]
                    rep["profit_mismatch"] += r["profit_mismatch"]
                    ch[(cond, sd, s, L.ok(o))] = r
        for cond in LIABLE_CONDS:
            fc = cond.replace("|liable", "|free")
            for s in samples[sd]:
                for o in L.LIC_OPTS:
                    x = derive_liable(ch[(fc, sd, s, L.ok(o))], cond)
                    rep["liable_derived"][0] += 1
                    if x["totals"][s] == saved[("lic", cond, sd, s, L.ok(o))][s]:
                        rep["liable_derived"][1] += 1
                    else:
                        rep["fails"].append((cond, sd, s, L.ok(o), "derived"))
                    if sd in LIABLE_SEEDS:
                        rp = done[_key(("lic", cond, sd, s, o, BASE_R))]
                        rep["liable_replay"][0] += 1
                        same_trade = rp["dig_trade"] == ch[(fc, sd, s, L.ok(o))]["dig_trade"]
                        same_win = rp["win"] == x["win"] and rp["lic"] == x["lic"]
                        rep["liable_replay"][1] += same_trade
                        rep["liable_replay"][2] += same_win
                        if not (same_trade and same_win and rp["totals"][s] == x["totals"][s]):
                            rep["fails"].append((cond, sd, s, L.ok(o), "liable replay"))
                    ch[(cond, sd, s, L.ok(o))] = x
    rep["pass"] = not rep["fails"] and rep["roy_mismatch"] == 0 and rep["profit_mismatch"] == 0
    return {"never": nev, "lic": ch, "samples": samples}, rep


# ------------------------------------------------------------------ analysis

def _owner_rows(data, cond, sd, s, o, r):
    """One owner-option at royalty r: licensee rows, others' unit changes, owner total."""
    q, t, ds, lia = L.parts(cond)
    ch = data["lic"][(cond, sd, s, o)]
    nv = data["never"][(L.base_key(t, ds), sd)]
    b = str(int(o.split("x")[1]))
    W, N = ch["win"][b], nv["win"][b]
    rk = _rk(r)
    lic = []
    for l in sorted(ch["lic"]):
        a, z = W[l], N[l]
        roy_r = ch["roy"][l][rk]
        roy_base = ch["roy"][l][_rk(BASE_R)]
        prof_r = a[C["profit"]] + roy_base - roy_r
        extra = a[C["units"]] - z[C["units"]]
        price = a[C["revenue"]] / a[C["units"]] if a[C["units"]] else 0.0
        lic.append({"licensee": l, "stype": ch["meta"][l][1], "units": a[C["units"]], "units_never": z[C["units"]],
                    "extra_units": extra, "revenue": a[C["revenue"]], "revenue_never": z[C["revenue"]],
                    "cost": a[C["cost"]], "cost_never": z[C["cost"]],
                    "unit_cost": a[C["cost"]] / a[C["units"]] if a[C["units"]] else None,
                    "unit_cost_never": z[C["cost"]] / z[C["units"]] if z[C["units"]] else None,
                    "ad": a[C["ad"]], "ad_never": z[C["ad"]], "fines": a[C["fines"]], "fines_never": z[C["fines"]],
                    "catches": a[C["catches"]], "catches_never": z[C["catches"]],
                    "royalty": roy_r, "royalty_extra": r * price * max(0, extra),
                    "profit": prof_r, "profit_never": z[C["profit"]], "accept": prof_r >= z[C["profit"]]})
    cat = ch["meta"][s][0]
    grp = {"owner": 0, "same_genuine": 0, "same_other": 0, "other_categories": 0}
    for st, (c, ty) in ch["meta"].items():
        if st in ch["lic"]:
            continue
        g = "owner" if st == s else ("other_categories" if c != cat else
                                     ("same_genuine" if ty == "genuine" else "same_other"))
        grp[g] += W[st][C["units"]] - N[st][C["units"]]
    roy_recv_base = sum(ch["roy"][l][_rk(BASE_R)] for l in ch["lic"])
    assert roy_recv_base == ch["win"]["1"][s][C["roy_recv"]]
    total_r = ch["totals"][s] - roy_recv_base + sum(ch["roy"][l][rk] for l in ch["lic"])
    return lic, grp, total_r


def analyse(data) -> dict:
    samples = data["samples"]
    conds = L.LIC_CONDS
    opts = [L.ok(o) for o in L.LIC_OPTS]
    res = {"a": {}, "b": {}, "gain": {}, "rows": [], "owner_rows": []}
    for r in RATES:
        rk = _rk(r)
        for cond in conds:
            q, t, ds, lia = L.parts(cond)
            nv_tot = {}
            per = {o: {"lic": {sd: [] for sd in SEEDS}, "grp": {sd: [] for sd in SEEDS}} for o in opts}
            tot = {}
            for sd in SEEDS:
                nv = data["never"][(L.base_key(t, ds), sd)]
                for s in samples[sd]:
                    nv_tot[(sd, s)] = nv["totals"][s]
                    for o in opts:
                        lic, grp, tr = _owner_rows(data, cond, sd, s, o, r)
                        per[o]["lic"][sd].append(lic)
                        per[o]["grp"][sd].append(grp)
                        tot[(sd, s, o)] = (tr, all(x["accept"] for x in lic))
                        for x in lic:
                            res["rows"].append({"royalty": r, "cond": cond, "seed": sd, "owner": s, "option": o, **x})
            # check (a) and (b) per option
            for o in opts:
                A = {}
                L_ = per[o]["lic"]

                def lm(f):
                    return mean_ci([float(np.mean([f(x) for ls in L_[sd] for x in ls])) for sd in SEEDS])

                def om(f):
                    return mean_ci([float(np.mean([f(ls) for ls in L_[sd]])) for sd in SEEDS])
                A["d_units"] = om(lambda ls: sum(x["extra_units"] for x in ls))
                A["units"] = om(lambda ls: sum(x["units"] for x in ls))
                A["units_never"] = om(lambda ls: sum(x["units_never"] for x in ls))
                A["royalty"] = om(lambda ls: sum(x["royalty"] for x in ls))
                A["royalty_extra"] = om(lambda ls: sum(x["royalty_extra"] for x in ls))
                A["share_anyway"] = mean_ci([1 - sum(x["royalty_extra"] for ls in L_[sd] for x in ls)
                                             / max(1, sum(x["royalty"] for ls in L_[sd] for x in ls)) for sd in SEEDS])
                for f in ("revenue", "cost", "ad", "fines", "catches"):
                    A[f"lic_d_{f}"] = lm(lambda x, f=f: x[f] - x[f + "_never"])
                A["lic_d_units"] = lm(lambda x: x["extra_units"])
                A["lic_unit_cost"] = mean_ci([float(np.mean([x["unit_cost"] for ls in L_[sd] for x in ls
                                                             if x["unit_cost"] is not None])) for sd in SEEDS])
                A["lic_unit_cost_never"] = mean_ci([float(np.mean([x["unit_cost_never"] for ls in L_[sd] for x in ls
                                                                   if x["unit_cost_never"] is not None]))
                                                    for sd in SEEDS])
                A["lic_d_profit"] = lm(lambda x: x["profit"] - x["profit_never"])
                for g in ("owner", "same_genuine", "same_other", "other_categories"):
                    A[f"grp_{g}"] = mean_ci([float(np.mean([gg[g] for gg in per[o]["grp"][sd]])) for sd in SEEDS])
                allx = [x for sd in SEEDS for ls in L_[sd] for x in ls]
                A["accept_share"] = float(np.mean([x["accept"] for x in allx]))
                A["n_licensees"] = len(allx)
                A["owners_all_accept"] = sum(all(x["accept"] for x in ls) for sd in SEEDS for ls in L_[sd])
                res["a"][(rk, cond, o)] = A
            # gains: unconstrained and constrained, per owner
            G = {"orig_unf": {}, "orig_fl": {}, "con_unf": {}, "con_fl": {}, "none_ok": 0, "best_orig": {},
                 "best_con": {}}
            for sd in SEEDS:
                for s in samples[sd]:
                    totals = {NEVER: nv_tot[(sd, s)], **{o: tot[(sd, s, o)][0] for o in opts}}
                    g = benchmark.gain(totals)
                    okd = {o: tot[(sd, s, o)][0] for o in opts if tot[(sd, s, o)][1]}
                    if okd:
                        gc = benchmark.gain({NEVER: nv_tot[(sd, s)], **okd})
                        cu, cf, cb = gc["gain_unfloored"], gc["gain_floored"], gc["best_day"]
                    else:
                        cu, cf, cb = 0, 0, NEVER
                        G["none_ok"] += 1
                    G["orig_unf"].setdefault(sd, []).append(g["gain_unfloored"])
                    G["orig_fl"].setdefault(sd, []).append(g["gain_floored"])
                    G["con_unf"].setdefault(sd, []).append(cu)
                    G["con_fl"].setdefault(sd, []).append(cf)
                    G["best_orig"][g["best_day"]] = G["best_orig"].get(g["best_day"], 0) + 1
                    G["best_con"][cb] = G["best_con"].get(cb, 0) + 1
                    res["owner_rows"].append({"royalty": r, "cond": cond, "seed": sd, "owner": s,
                                              "never_total": nv_tot[(sd, s)],
                                              **{f"total_{o}": tot[(sd, s, o)][0] for o in opts},
                                              **{f"all_accept_{o}": int(tot[(sd, s, o)][1]) for o in opts},
                                              "gain_unfloored": g["gain_unfloored"], "gain_floored": g["gain_floored"],
                                              "best": g["best_day"], "gain_unfloored_constrained": cu,
                                              "gain_floored_constrained": cf, "best_constrained": cb})
            out = {k: mean_ci([float(np.mean(G[k][sd])) for sd in SEEDS]) for k in ("orig_unf", "orig_fl",
                                                                                  "con_unf", "con_fl")}
            out["d_con_orig"] = mean_ci([float(np.mean(G["con_unf"][sd]) - np.mean(G["orig_unf"][sd]))
                                         for sd in SEEDS])
            out.update(none_ok=G["none_ok"], best_orig=G["best_orig"], best_con=G["best_con"])
            res["gain"][(rk, cond)] = out
    return res


# ------------------------------------------------------------------ report

def lab(cond: str) -> str:
    q, t, ds, lia = L.parts(cond)
    return f"{q}, {t}, {ds:g}, {'owner liable' if lia else 'not liable'}"


def _pct(x):
    return f"{100 * x:.0f}%"


def _best(d: dict) -> str:
    keys = [L.ok(o) for o in L.LIC_OPTS] + [NEVER]
    return ", ".join(f"{k}: {d.get(k, 0)}" for k in keys if d.get(k, 0))


def report(res, rcheck, rep, meta) -> str:
    u1 = _num(1)
    pc = _num(3)
    opts = [L.ok(o) for o in L.LIC_OPTS]
    hk = _rk(HEADLINE)
    o = []
    o.append("# Licensing: two checks and a royalty recompute (exploratory)\n")
    o.append("**Everything in this file is exploratory and was written after the licensing results** "
             "(`runs/licensing_summary.md`, engine 0.16.0, ddd6fc2). It changes no prediction or verdict there. "
             "Analysis only: no engine change.\n")
    o.append("<!-- reading -->\nREADING_PLACEHOLDER\n<!-- reading -->\n")
    o.append("## What was done\n")
    o.append("- **Replay.** Never chains and the licensed chains of the six not-liable conditions were replayed "
             "at 0.16.0 with an observer that changes nothing: it wraps `engine.days.reset_for_day` and copies every "
             "stall's day ledger (units, revenue, cost, ad spend, fines, switch cost, royalties paid and received, "
             "catches, price) before the reset. Owner liable: replayed for seeds 250–251; for every seed the liable "
             "ledger is derived from the not-liable one by moving fines at licensees (from the licence day) to the owner.")
    o.append("- **Windows.** Every licensee and every other stall is compared over the licence day b to day 30, "
             "licensed chain against the never chain of the same seed, verification level and detect_scale, where "
             "the stall trades under its own name and type.")
    o.append("- **Check (a).** Extra units = licensed − never units. Royalty on extra units = royalty × the "
             "licensee's mean licensed price × max(0, extra units). Share earned on sales the stall would have made "
             "anyway = 1 − (royalty on extra units ÷ royalty paid), per seed over the 3 owners' licensees.")
    o.append("- **Check (b).** A licensee accepts if its profit from day b, licensed (royalties paid and the fines "
             "it bears counted), is at least its never-chain profit over the same days. The owner's best option is "
             "recomputed over the options every one of its licensees accepts; with none, its alternative is never "
             "and its gain is 0.")
    o.append("- **Royalty.** Owner total at royalty r = saved total − royalties received at 0.15 + royalties at r; "
             "licensee profit at r = profit at 0.15 + royalties paid at 0.15 − royalties at r. Royalties at r are "
             "computed exactly from each licensee's day units and price as the engine charges them "
             "(units × round(r × price)); at 0.15 this reproduces every licensee-day's royalty to the cent. "
             "This is the spec's gain_0.15 − (0.15 − r) × licensee revenue up to the per-unit rounding.")
    o.append("- Intervals: per-seed mean over the 3 sampled owners (or over their licensees, where marked), "
             "95% t over 20 seeds, unadjusted. Money in $ over the window; units over the window.\n")

    o.append("## Royalty enters no decision\n")
    o.append("Code (0.16.0):\n")
    o.append("- `engine/licensing.py:119` `royalty_cents` is the only use of `licensing.royalty` besides validation "
             "(`:43`) and the licence record (`:107`). Its one caller is `BazaarEngine.purchase` "
             "(`engine/bazaar.py:698-701`), after the sale is made: it adds to the licensee's `royalty_paid_cents` and "
             "the owner's `royalty_received_cents`.")
    o.append("- Those two fields are read only by profit: `engine/days.py:55` `stall_profit`, the outcome's "
             "`profit_by_stall_cents` (`engine/bazaar.py:1000`) and `seller_by_type` (`:868-873`), and are zeroed "
             "each morning (`engine/days.py:158`).")
    o.append("- Profit reaches decisions in two places only. (1) `engine/days.py:204, 218` passes profits to "
             "`revise`, which switches nothing here: brands require `evolution.revise_prob = mutation_prob = 0` "
             "(`engine/days.py`, run_days). (2) `reset_for_day` puts yesterday's profit in the stall's `yesterday` "
             "ledger, shown to sellers (`engine/bazaar.py:774`); the only policy that reads it is "
             "`rule_genuine_rational_v2` (`agents/rule_based.py:238`). These chains run `rule_honest`, "
             "`rule_deceptive` and `rule_genuine_bust_at` with nothing scheduled, none of which reads profit or "
             "`yesterday` (`agents/rule_based.py:17-110, 254-291`). Buyers never see a royalty.\n")
    rows = rcheck["rows"]
    o.append(f"Replay: seed 250, cheap, tourist share 1.0, detect_scale 1, owner not liable; 3 owners × 4 options "
             f"at royalty 0.05 and 0.25 against 0.15 ({len(rows)} comparisons).\n")
    o.append("| Owner | Option | Royalty | Days identical (all stalls' units, price, revenue, cost, ad, fines, catches) "
             "| Window ledgers identical except royalties and profit | Same licensees | Royalties differ |")
    o.append("|---|---|---|---|---|---|---|")
    for r in rows:
        o.append(f"| {r['owner']} | {r['option']} | {r['royalty']:.2f} | {r['days_identical']}/{L.DAYS} | "
                 f"{'yes' if r['ledger_identical_except_royalty'] else 'NO'} | {'yes' if r['licensees_same'] else 'NO'} "
                 f"| {'yes' if r['royalties_differ'] else 'no'} |")
    o.append(f"\nResult: **{'pass' if rcheck['pass'] else 'FAIL'}**.\n")

    o.append("## Replay verification\n")
    o.append(f"- Never chains: replayed owner totals equal the saved ones in {rep['never'][1]}/{rep['never'][0]} "
             f"stall-seeds.")
    o.append(f"- Licensed chains, owner not liable: {rep['free'][1]}/{rep['free'][0]} owner-options equal the saved "
             f"totals.")
    o.append(f"- Owner liable, derived: {rep['liable_derived'][1]}/{rep['liable_derived'][0]} owner-options equal "
             f"the saved totals.")
    o.append(f"- Owner liable, replayed (seeds 250–251): {rep['liable_replay'][1]}/{rep['liable_replay'][0]} chains "
             f"trade identically to the not-liable chain on every stall-day; {rep['liable_replay'][2]}/"
             f"{rep['liable_replay'][0]} have window ledgers equal to the derived ones.")
    o.append(f"- Licensee-days whose royalty differs from units × round(0.15 × price): {rep['roy_mismatch']}. "
             f"Stall-days whose observed profit differs from the engine's: {rep['profit_mismatch']}.")
    o.append(f"- Result: **{'pass' if rep['pass'] else 'FAIL'}**.\n")

    o.append("## Check (a): extra sales the brand added\n")
    o.append("Per owner (sum over its licensees), licence day to day 30, licensed − never. Royalty columns at "
             f"the headline royalty {HEADLINE:.2f}. Units are not affected by the royalty.\n")
    o.append("| Condition | Option | Licensee units | Never units | Extra units | Royalty paid ($) | Royalty on extra "
             "units ($) | Share earned on sales made anyway |")
    o.append("|---|---|---|---|---|---|---|---|")
    for cond in L.LIC_CONDS:
        for op in opts:
            A = res["a"][(hk, cond, op)]
            o.append(f"| {lab(cond)} | {op} | {_ci(A['units'], u1, False)} | {_ci(A['units_never'], u1, False)} | "
                     f"{_ci(A['d_units'], u1)} | {_ci(A['royalty'], _d, False)} | {_ci(A['royalty_extra'], _d, False)} "
                     f"| {_ci(A['share_anyway'], pc, False)} |")
    o.append("\nShare of royalties earned on sales the licensees would have made anyway, at each royalty "
             "(the share moves with the royalty only through per-unit rounding):\n")
    o.append("| Condition | Option | " + " | ".join(f"{r:.2f}" for r in RATES) + " |")
    o.append("|---|---|" + "---|" * len(RATES))
    for cond in L.LIC_CONDS:
        for op in opts:
            o.append(f"| {lab(cond)} | {op} | " + " | ".join(f"{res['a'][(_rk(r), cond, op)]['share_anyway']['mean']:.3f}"
                                                           for r in RATES) + " |")
    o.append("\nPer licensee, licensed − never, licence day to day 30 (mean over the licensees of the 3 owners per "
             f"seed); profit at royalty {HEADLINE:.2f}.\n")
    o.append("| Condition | Option | Units | Revenue ($) | Unit cost licensed / never ($) | Ad spend ($) | Fines ($) "
             "| Catches | Profit ($) |")
    o.append("|---|---|---|---|---|---|---|---|---|")
    for cond in L.LIC_CONDS:
        for op in opts:
            A = res["a"][(hk, cond, op)]
            o.append(f"| {lab(cond)} | {op} | {_ci(A['lic_d_units'], u1)} | {_ci(A['lic_d_revenue'], _d)} | "
                     f"{_d(A['lic_unit_cost']['mean'])} / {_d(A['lic_unit_cost_never']['mean'])} | "
                     f"{_ci(A['lic_d_ad'], _d)} | {_ci(A['lic_d_fines'], _d)} | {_ci(A['lic_d_catches'], u1)} | "
                     f"{_ci(A['lic_d_profit'], _d)} |")
    o.append("\nWhose sales the licensees took: units licensed − never, licence day to day 30, per owner, by group "
             "(the owner; the other genuine stalls of its category; the other non-genuine stalls of its category, "
             "licensees excluded; every stall of other categories).\n")
    o.append("| Condition | Option | Licensees | Owner | Same category, genuine | Same category, other | "
             "Other categories |")
    o.append("|---|---|---|---|---|---|---|")
    for cond in L.LIC_CONDS:
        for op in opts:
            A = res["a"][(hk, cond, op)]
            o.append(f"| {lab(cond)} | {op} | {_ci(A['d_units'], u1)} | {_ci(A['grp_owner'], u1)} | "
                     f"{_ci(A['grp_same_genuine'], u1)} | {_ci(A['grp_same_other'], u1)} | "
                     f"{_ci(A['grp_other_categories'], u1)} |")

    o.append("\n## Check (b): would the licensee sign?\n")
    o.append(f"At the headline royalty {HEADLINE:.2f}: share of licensees that would accept (pooled over 60 owners), "
             "owners whose licensees all accept, and licensee profit licensed − never (per licensee).\n")
    o.append("| Condition | Option | Licensees accepting | Owners with every licensee accepting | "
             "Licensee profit − never ($) |")
    o.append("|---|---|---|---|---|")
    for cond in L.LIC_CONDS:
        for op in opts:
            A = res["a"][(hk, cond, op)]
            o.append(f"| {lab(cond)} | {op} | {_pct(A['accept_share'])} of {A['n_licensees']} | "
                     f"{A['owners_all_accept']}/60 | {_ci(A['lic_d_profit'], _d)} |")
    o.append("\nShare of licensees accepting at each royalty:\n")
    o.append("| Condition | Option | " + " | ".join(f"{r:.2f}" for r in RATES) + " |")
    o.append("|---|---|" + "---|" * len(RATES))
    for cond in L.LIC_CONDS:
        for op in opts:
            o.append(f"| {lab(cond)} | {op} | " + " | ".join(_pct(res["a"][(_rk(r), cond, op)]["accept_share"])
                                                           for r in RATES) + " |")
    o.append("\nLicensee profit − never per licensee ($) at each royalty:\n")
    o.append("| Condition | Option | " + " | ".join(f"{r:.2f}" for r in RATES) + " |")
    o.append("|---|---|" + "---|" * len(RATES))
    for cond in L.LIC_CONDS:
        for op in opts:
            o.append(f"| {lab(cond)} | {op} | " + " | ".join(_ci(res["a"][(_rk(r), cond, op)]["lic_d_profit"], _d)
                                                           for r in RATES) + " |")

    o.append("\n## Owner's gain with and without the licensee's consent\n")
    o.append("Per royalty and condition: the owner's gain over all four options (as the licensing run; at 0.15 "
             "it reproduces `runs/licensing_summary.md`), and over the options every licensee accepts "
             "(none: never, gain 0). Unfloored is primary.\n")
    for r in RATES:
        rk = _rk(r)
        o.append(f"\n**Royalty {r:.2f}**{' (headline)' if r == HEADLINE else ''}\n")
        o.append("| Condition | Gain, all options, unfloored ($) | floored ($) | Gain, accepted options only, "
                 "unfloored ($) | floored ($) | Accepted − all, unfloored ($) | Owners with no accepted option | "
                 "Best option with consent (counts) |")
        o.append("|---|---|---|---|---|---|---|---|")
        for cond in L.LIC_CONDS:
            g = res["gain"][(rk, cond)]
            o.append(f"| {lab(cond)} | {_ci(g['orig_unf'], _d)} | {_ci(g['orig_fl'], _d)} | {_ci(g['con_unf'], _d)} "
                     f"| {_ci(g['con_fl'], _d)} | {_ci(g['d_con_orig'], _d)} | {g['none_ok']}/60 | "
                     f"{_best(g['best_con'])} |")
    o.append("\n## Run record\n")
    for k in ("engine_version", "commit", "script_sha256", "commands", "python", "numpy", "platform", "workers",
              "chains", "wall", "load", "memory"):
        if k in meta:
            o.append(f"- {k.replace('_', ' ')}: {meta[k]}")
    o.append("\n## Caveats\n")
    o.append("CAVEATS_PLACEHOLDER\n")
    return "\n".join(o)


def write_csv(res):
    rows = [x for x in res["rows"]]
    with open("runs/licensing_checks.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for x in rows:
            w.writerow({k: (round(v, 2) if isinstance(v, float) else v) for k, v in x.items()})
    rows = res["owner_rows"]
    with open("runs/licensing_checks_owners.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--royalty-check", action="store_true")
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--analyse", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--min-swap-mb", type=float, default=512)
    ap.add_argument("--min-free-pct", type=float, default=15)
    a = ap.parse_args(argv)
    LB._lower_priority()
    logf = open(RUNLOG, "a", encoding="utf-8")

    def log(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        logf.write(line + "\n"); logf.flush()

    if a.royalty_check or a.collect:
        t0 = time.time()
        log(f"licensing_checks {'royalty check' if a.royalty_check else 'collect'}: engine {ENGINE_VERSION}, "
            f"commit {_git()['commit'][:7]}, load {_load()}, memory {memory_state()}")
        run_chains(a, jobs(royalty_check_only=a.royalty_check), log)
        rc = royalty_check(load_cache())
        log(f"royalty check: {'pass' if rc['pass'] else 'FAIL'}")
        if not rc["pass"]:
            for r in rc["rows"]:
                log(json.dumps(r))
            return 2
        log(f"done; wall {(time.time() - t0) / 3600:.2f} h; load {_load()}; memory {memory_state()}")
        return 0
    if a.analyse:
        done = load_cache()
        rc = royalty_check(done)
        if not rc["pass"]:
            raise SystemExit("royalty check failed; stop and report")
        data, rep = verify(done, saved_totals())
        print(json.dumps({k: v for k, v in rep.items() if k != "fails"}), rep["fails"][:10])
        if not rep["pass"]:
            raise SystemExit("replay verification failed; stop and report")
        res = analyse(data)
        write_csv(res)
        with open(RUNLOG, encoding="utf-8") as f:
            runlog = f.read()
        meta = {"engine_version": ENGINE_VERSION, "commit": _git()["commit"],
                "script_sha256": hashlib.sha256(open(__file__, "rb").read()).hexdigest(),
                "commands": "`nice -n 19 python -m analysis.licensing_checks --royalty-check`, then `--collect`, "
                            "then `--analyse`",
                "python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
                "workers": a.workers, "chains": f"{len(done)} replayed",
                "wall": "; ".join(l.split(" ", 2)[2] for l in runlog.splitlines() if " done; wall" in l),
                "load": "start/end lines in runs/licensing_checks_run.log"}
        sp = "runs/licensing_checks.md"
        txt = report(res, rc, rep, meta)
        if os.path.exists(sp):          # keep the reading and caveats written by hand
            old = open(sp, encoding="utf-8").read()
            if "CAVEATS_PLACEHOLDER" not in old and "## Caveats\n" in old:
                txt = txt.replace("CAVEATS_PLACEHOLDER", old.split("## Caveats\n", 1)[1].strip())
            if "READING_PLACEHOLDER" not in old and old.count("<!-- reading -->") == 2:
                txt = txt.replace("READING_PLACEHOLDER", old.split("<!-- reading -->")[1].strip())
        with open(sp, "w", encoding="utf-8") as f:
            f.write(txt)
        with open("runs/licensing_checks_results.json", "w", encoding="utf-8") as f:
            json.dump({"verify": {k: v for k, v in rep.items() if k != "fails"}, "royalty_check": rc,
                       "gain": {f"{k[0]}|{k[1]}": v for k, v in res["gain"].items()},
                       "a": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in res["a"].items()}}, f, indent=1)
        print("written", sp)
        return 0
    ap.error("one of --royalty-check, --collect, --analyse")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
