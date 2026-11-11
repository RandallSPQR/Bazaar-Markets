"""Bust-out decomposition (exploratory; spec "Part 1: bust-out decomposition", 2026-11-11, written after
the liability run's results). Analysis only: no engine change.

For every condition of the liability run (runs/liability_summary.md, 5b60720: 2 liability arms x 2
verification levels x detect_scale {0, 0.1, 1}) and every sampled stall-seed (seeds 230-249, 3 stalls),
replay the never chain and the chain of the stall's best candidate (runs/liability.csv) with an
observer that changes nothing: it wraps BazaarEngine.purchase, .decide (buyers) and .search_decide and
records, per day and per buyer who had a watched stall in its consideration set, what happened between
the buyer and that stall (units, price and unit cost of each purchase; inspections; meeting the stall
closed; seeing its rating below the threshold; the stall among the buyer's candidates but another one
chosen). The stall's 30-day totals must equal the saved run to the cent.

    nohup nice -n 19 .venv/bin/python -m analysis.bustout_decomp --collect > runs/bustout_stdout.log 2>&1 &
    .venv/bin/python -m analysis.bustout_decomp --analyse
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

import numpy as np

import analysis.liability as L
from analysis.capture import memory_state
from analysis.counterfeit import _git, _load
from engine import ENGINE_VERSION, bazaar, benchmark

NEVER = benchmark.NEVER
CSV_IN = "runs/liability.csv"
CACHE = "runs/bustout_cache.jsonl"
RUNLOG = "runs/bustout_run.log"
LEVELS = [0.0, 0.1, 1.0]
SEEDS = list(range(230, 250))


def parse_cand(s: str):
    if s == NEVER:
        return NEVER
    if "h" in s:
        b, h = s.split("h")
        return (int(b), int(h))
    return int(s)


def best_table() -> dict:
    """{(arm, t, ds, seed, stall): best candidate key} from the saved run, plus the saved totals."""
    out = {}
    with open(CSV_IN, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            k = (r["liability"], r["verification"], float(r["detect_scale"]), int(r["seed"]), r["stall"])
            out[k] = {"best": r["best"], "never_total_cents": int(r["never_total_cents"]),
                      "best_total_cents": int(r[f"total_{r['best']}_cents"]),
                      "best_fines_charged_cents": int(r["best_fines_charged_cents"]),
                      "best_fines_uncollectible_cents": int(r["best_fines_uncollectible_cents"])}
    return out


# ------------------------------------------------------------------ observer

_OBS: dict = {"watch": (), "days": []}


def _patch() -> None:
    from engine.bazaar import BazaarEngine
    if getattr(BazaarEngine, "_decomp_observer", False):
        return
    o_run, o_purchase, o_decide, o_search = (BazaarEngine.run, BazaarEngine.purchase, BazaarEngine.decide,
                                             BazaarEngine.search_decide)

    def day_rec(eng):
        d = getattr(eng, "_dc", None)
        if d is None:
            d = eng._dc = {"day": eng.day, "stalls": {}, "buyers": {}}
            for sid in _OBS["watch"]:
                st = eng.by_sid[sid]
                d["stalls"][sid] = {"price_cents": st.price_cents, "unit_cost_morning": st.unit_cost_cents,
                                    "rating": st.rating, "exited": st.exited_day is not None,
                                    "brand": st.brand}
            for p in eng.buyers:
                w = [sid for sid in _OBS["watch"] if p.consider is None or sid in p.consider]
                if w:
                    d["buyers"][p.pid] = {"profile": p.profile, "q_req": p.task["q_req"], "need": p.task["units"],
                                          "budget": p.task["budget_cents"], "w": {sid: {} for sid in w}}
        return d

    def flag(eng, pid, sid, k, v=True):
        b = day_rec(eng)["buyers"].get(pid)
        if b is not None and sid in b["w"]:
            b["w"][sid].setdefault(k, v)

    def run(self, *a, **k):
        day_rec(self)
        out = o_run(self, *a, **k)
        d = self._dc
        for sid in _OBS["watch"]:
            st = self.by_sid[sid]
            d["stalls"][sid].update(revenue_cents=st.revenue_cents, cost_cents=st.cost_cents,
                                    ad_spend_cents=st.ad_spend_cents, penalties_cents=st.penalties_cents,
                                    units_sold=st.units_sold, catches=st.catches, busted_day=st.busted_day,
                                    unit_cost_evening=st.unit_cost_cents, exit_pending_done=st.exited_day,
                                    switch_cost_cents=st.switch_cost_cents)
        _OBS["days"].append(d)
        return out

    def purchase(self, p, st, units):
        if st.sid in _OBS["watch"]:
            b = day_rec(self)["buyers"].get(p.pid)
            if b is not None and st.sid in b["w"]:
                b["w"][st.sid].setdefault("buys", []).append([units, st.price_cents, st.unit_cost_cents, st.q_true])
        return o_purchase(self, p, st, units)

    def decide(self, role, key, agent, obs, check):
        a = o_decide(self, role, key, agent, obs, check)
        if role != "buyer":
            return a
        rows = list(obs.get("stalls_here", [])) + list((obs.get("search") or {}).get("seen_elsewhere", []))
        tau = self.cfg.ratings.tau
        for r in rows:
            if r["id"] in _OBS["watch"] and r.get("rating") is not None and r["rating"] < tau:
                flag(self, key, r["id"], "rated_below_tau")
        for r in obs.get("stalls_here", []):
            if r["id"] in _OBS["watch"]:
                flag(self, key, r["id"], "saw_open")
        if a["action"] == "inspect" and a["stall"] in _OBS["watch"]:
            st = self.by_sid[a["stall"]]
            flag(self, key, a["stall"], "inspected_q", st.q_true)
        if a["action"] in ("buy", "choose"):
            cands = a.get("candidates") or []
            for sid in _OBS["watch"]:
                if sid in cands and a["stall"] != sid:
                    flag(self, key, sid, "outranked")
        return a

    def search_decide(self, p, stay):
        if _OBS["watch"] and p.units < p.task["units"]:
            cat = p.task["category"]
            for st in self.reach(p.pos):
                if st.sid in _OBS["watch"] and st.category == cat and self.considers(p, st) and not self.is_open(st):
                    flag(self, p.pid, st.sid, "met_closed")
        return o_search(self, p, stay)

    BazaarEngine.run, BazaarEngine.purchase, BazaarEngine.decide, BazaarEngine.search_decide = \
        run, purchase, decide, search_decide
    BazaarEngine._decomp_observer = True


def _init() -> None:
    L._lower_priority()
    _patch()


def _key(j) -> str:
    cond, seed, watch, stall, b = j
    return f"{cond}|{seed}|{stall}|{L.ck(b)}"


def _job(args) -> dict:
    cond, seed, watch, stall, b = args
    _patch()
    _OBS["watch"], _OBS["days"] = tuple(watch), []
    c = benchmark.bust_config(L.config(cond, seed), stall, b)
    out = bazaar.run(c)
    days = _OBS["days"]
    _OBS["watch"], _OBS["days"] = (), []
    return {"key": _key(args), "cond": cond, "seed": seed, "stall": stall, "b": L.ck(b), "watch": list(watch),
            "totals": {s: benchmark.stall_total(out, s) for s in watch},
            "fines": {s: out["liability"]["by_stall"].get(s, {}) for s in watch},
            "exited": out["liability"]["exited"], "days": days}


def jobs(best: dict) -> list[tuple]:
    out = []
    samples = {s: L.sample_stalls(s) for s in SEEDS}
    for cond in L.conds(LEVELS):
        arm, t, ds = L.parts(cond)
        for seed in SEEDS:
            w = samples[seed]
            out.append((cond, seed, w, None, NEVER))
            for s in w:
                out.append((cond, seed, [s], s, parse_cand(best[(arm, t, ds, seed, s)]["best"])))
    return out


def collect(a) -> None:
    def log(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        with open(RUNLOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    best = best_table()
    js = jobs(best)
    log(f"bustout_decomp collect: engine {ENGINE_VERSION}, commit {_git()}, numpy {np.__version__}, "
        f"{platform.platform()}, python {sys.version.split()[0]}; load {_load()}, memory {memory_state()}")
    done = set()
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            done = {json.loads(x)["key"] for x in f}
    todo = [j for j in js if _key(j) not in done]
    log(f"{len(js)} chains, {len(done)} cached, {len(todo)} to run; workers {a.workers}")
    t0, n = time.time(), 0
    with open(CACHE, "a", encoding="utf-8") as cache, ProcessPoolExecutor(a.workers, initializer=_init) as ex:
        it, live, exhausted = iter(todo), set(), False
        while live or not exhausted:
            while not exhausted and len(live) < a.workers:
                j = next(it, None)
                if j is None:
                    exhausted = True
                    break
                live.add(ex.submit(_job, j))
            if not live:
                continue
            fin, live = wait(live, timeout=60, return_when=FIRST_COMPLETED)
            for fu in fin:
                cache.write(json.dumps(fu.result(), separators=(",", ":")) + "\n")
                cache.flush()
                n += 1
                if n % 40 == 0 or n == len(todo):
                    log(f"{n}/{len(todo)} chains, {time.time() - t0:.0f} s, load {_load()}, memory {memory_state()}")
    log(f"done; wall {(time.time() - t0) / 3600:.2f} h; load {_load()}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--analyse", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    if a.collect:
        collect(a)
    if a.analyse:
        from analysis.bustout_report import analyse_and_report
        analyse_and_report()


if __name__ == "__main__":
    main()
