"""Shared machinery for the Canal Street and Brand Equity runs (engine 0.17.0): a stall-ledger observer and the
chain runner of the licensing run (analysis/licensing.py run_chains), generalised to any job function.

The observer wraps engine.days.reset_for_day, which run_days calls after every day (the last included), and
copies each stall's day ledger before the reset. It changes nothing: it returns what the original returns.
The observer's profit is checked against the engine's profit_by_stall_cents on every stall-day."""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

import analysis.liability as LB
from analysis.capture import memory_state
from analysis.counterfeit import _load
from engine import bazaar
from engine import days as DAYS

FIELDS = ("units", "revenue", "cost", "ad", "fines", "switch", "roy_paid", "roy_recv", "catches", "profit", "price",
          "unit_cost")


def run_with_ledger(cfg, log=None) -> tuple[dict, list[dict], int]:
    """(outcome, ledgers, profit mismatches). ledgers[d - 1] = {sid: {field: int, brand, counterfeit_of,
    licensed_from, white_label, stype, category}} for day d."""
    snaps = []
    orig = DAYS.reset_for_day

    def tap(c, stalls):
        snaps.append({st.sid: {"units": st.units_sold, "revenue": st.revenue_cents, "cost": st.cost_cents,
                               "ad": st.ad_spend_cents, "fines": st.penalties_cents, "switch": st.switch_cost_cents,
                               "roy_paid": st.royalty_paid_cents, "roy_recv": st.royalty_received_cents,
                               "catches": st.catches, "profit": DAYS.stall_profit(st), "price": st.price_cents,
                               "unit_cost": st.unit_cost_cents, "brand": st.brand, "counterfeit_of": st.counterfeit_of,
                               "licensed_from": st.licensed_from, "white_label": st.white_label, "stype": st.stype,
                               "category": st.category}
                      for st in stalls})
        return orig(c, stalls)

    DAYS.reset_for_day = tap
    try:
        out = bazaar.run(cfg, log=log)
    finally:
        DAYS.reset_for_day = orig
    if len(snaps) != len(out["days"]):
        raise RuntimeError("ledger observer missed a day")
    bad = sum(snaps[d][s]["profit"] != out["days"][d]["outcome"]["brands"]["profit_by_stall_cents"][s]
              for d in range(len(snaps)) for s in snaps[d])
    return out, snaps, bad


def guard(out) -> dict:
    return {"stuck_buyers": out["stuck_buyers"]["total"], "idle_choosers": out["idle_choosers"]["total"],
            "parked": int(sum(LB._PARKED)), "buyer_days": sum(d["outcome"]["buyers_arrived"] for d in out["days"]),
            "fallbacks": sum(d["outcome"]["fallbacks"]["buyer"] + d["outcome"]["fallbacks"]["seller"]
                             for d in out["days"])}


def run_chains(a, jobs, cache_path, log, job_fn, key_fn) -> tuple[list[dict], int]:
    """a.workers processes at nice 19; new chains paused while memory is short (a.min_swap_mb, a.min_free_pct);
    every finished chain appended to the cache (a rerun resumes from it); load and memory logged every 50."""
    done = {}
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                done[r["key"]] = r
    todo = [j for j in jobs if key_fn(j) not in done]
    log(f"{len(jobs)} chains, {len(done)} cached, {len(todo)} to run; workers {a.workers}; load {_load()}; "
        f"memory {memory_state()}")
    t0, n, pauses = time.time(), 0, 0
    cache = open(cache_path, "a", encoding="utf-8") if cache_path else None
    with ProcessPoolExecutor(a.workers, initializer=LB._init) as ex:
        it = iter(todo)
        live: set = set()
        exhausted = False
        while live or not exhausted:
            while not exhausted and len(live) < a.workers:
                good, st = LB.memory_ok(a)
                if not good:
                    pauses += 1
                    if not live:
                        log(f"paused (memory {st}); waiting 60 s")
                        time.sleep(60)
                        continue
                    break
                j = next(it, None)
                if j is None:
                    exhausted = True
                    break
                live.add(ex.submit(job_fn, j))
            if not live:
                continue
            fin, live = wait(live, timeout=60, return_when=FIRST_COMPLETED)
            for fu in fin:
                r = fu.result()
                done[r["key"]] = r
                if cache:
                    cache.write(json.dumps(r, separators=(",", ":")) + "\n")
                    cache.flush()
                n += 1
                if n % 50 == 0 or n == len(todo):
                    log(f"{n}/{len(todo)} chains, {time.time() - t0:.0f} s, load {_load()}, memory {memory_state()}")
    if cache:
        cache.close()
    return [done[key_fn(j)] for j in jobs], pauses


def file_logger(path):
    logf = open(path, "a", encoding="utf-8")

    def log(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()
    return log
