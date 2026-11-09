"""Honest-profit diagnostic (2026-11-08; no engine change).

Stage B of the verification run (runs/verification_summary.md, 2cc1342): with 2 patrolling inspectors an
honest genuine stall that never busts out earns about 30% less over 30 days at tourist share 0.4, and total
sales fall from about 198 to 140 a day; in the tourist-only market honest profit is unchanged. This script
instruments the never-bust-out chains (0 vs 2 inspectors) without changing the engine: it wraps
BazaarEngine methods to record, per day, every buyer decision, every set-member stall a buyer came within
reach of (open or closed), seller actions of the sampled stalls, inspector presence, and the stalls'
accounting.

    .venv/bin/python -m analysis.honest_profit_diagnostic detail          # seed 200, t40|l1 and t100
    .venv/bin/python -m analysis.honest_profit_diagnostic repro           # minimal reproduction, no inspectors
    .venv/bin/python -m analysis.honest_profit_diagnostic summary 200-219 "B|t40|l1,B|t70|l1,B|t100" out.json
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np

from analysis.verification import CONDS, config, sample_stalls
from cli.sweep import parse_seeds
from engine import bazaar, benchmark
from engine.bazaar import BazaarEngine

TAU = 0.5


def _reason(s: dict, me: dict, left: int, q_req: float) -> str:
    """Why rule_buyer's search rule would not buy from a stall it knows of (mirrors RuleBuyer._candidate,
    local and expert inspection probability 1)."""
    if left // s["price_cents"] < 1:
        return "budget"
    if not (s.get("rating") is None or s["rating"] >= TAU):
        return "rating below tau"
    known = s.get("own_assessment")
    if known is None:
        known = s["inspected_quality"]
    if known is not None:
        return "candidate" if known >= q_req else "inspected below Q_req"
    if not s["messages"]:
        return "no claim heard"
    if s["messages"][-1]["claimed_quality"] < q_req:
        return "claim below Q_req"
    if me["profile"] == "expert":
        return "expert: not inspected"
    pushy = any(m["channel"] in ("yell", "whisper") for m in s["messages"])
    if me["profile"] == "local" and pushy:
        return "candidate" if me["inspect_cost_cents"] + s["price_cents"] > left else "local: not inspected"
    return "candidate"


class Recorder:
    """Wraps BazaarEngine.run / search_decide / decide / step for one multi-day run."""

    def __init__(self, watch: list[str]):
        self.watch = set(watch)
        self.days: list[dict] = []
        self.cur: dict | None = None
        self._orig = {k: getattr(BazaarEngine, k) for k in ("run", "search_decide", "decide", "step")}

    def __enter__(self):
        rec, o = self, self._orig

        def run(eng, *a, **k):
            rec.cur = {"day": eng.day, "reach": defaultdict(dict), "decisions": defaultdict(list),
                       "seller": defaultdict(Counter), "insp_near": Counter(), "skipped": Counter(),
                       "closed_ticks": Counter(), "last_choose": {}}
            out = o["run"](eng, *a, **k)
            rec.finish(eng, out)
            return out

        def search_decide(eng, p, stay):
            d = rec.cur
            for st in eng.reach(p.pos):
                if st.category == p.task["category"] and eng.considers(p, st):
                    r = d["reach"][p.pid].setdefault(st.sid, {"first_t": eng.t, "open_first": eng.is_open(st),
                                                             "ever_open": False, "closed_ticks": 0})
                    if eng.is_open(st):
                        r["ever_open"] = True
                    else:
                        r["closed_ticks"] += 1
            before = set(p.skipped)
            res = o["search_decide"](eng, p, stay)
            for sid in p.skipped - before:
                d["skipped"][p.pid] += 1
            return res

        def decide(eng, role, key, agent, obs, check):
            a = o["decide"](eng, role, key, agent, obs, check)
            d = rec.cur
            if role == "buyer":
                act = a["action"]
                d["decisions"][key].append((eng.t, act, a.get("stall")))
                if "search" in obs and obs["search"]["phase"] == "choose" and act == "move_on":
                    me = obs["you"]
                    t = me["task"]
                    pool = list(obs["stalls_here"]) + list(obs["search"]["seen_elsewhere"])
                    d["last_choose"][key] = {
                        "t": eng.t, "left": t["budget_left_cents"],
                        "reasons": {s["id"]: _reason(s, me, t["budget_left_cents"], t["q_req"]) for s in pool}}
            elif role == "seller" and key in rec.watch:
                c = d["seller"][key]
                if a["yell"] is not None:
                    c["yells"] += 1
                    c["yell_crowd_inspectors"] += sum(1 for x in obs["passersby"]
                                                     if eng.by_pid[x["id"]].kind == "inspector")
                if a["whisper"] is not None:
                    c["whispers"] += 1
                    c["whispers_to_inspector"] += eng.by_pid[a["whisper"]["to"]].kind == "inspector"
                c["answers"] += len(a["answers"])
                c["decisions"] += 1
            return a

        def step(eng):
            d = rec.cur
            for st in eng.stalls:
                if not eng.is_open(st):
                    d["closed_ticks"][st.stype] += 1
                if st.sid in rec.watch:
                    for p in eng.people:
                        if p.active and p.kind == "inspector" and np.hypot(p.pos[0] - st.pos[0], p.pos[1] - st.pos[1]) \
                                <= eng.cfg.market.earshot:
                            d["insp_near"][st.sid] += 1
            return o["step"](eng)

        for k, f in (("run", run), ("search_decide", search_decide), ("decide", decide), ("step", step)):
            setattr(BazaarEngine, k, f)
        return self

    def __exit__(self, *exc):
        for k, f in self._orig.items():
            setattr(BazaarEngine, k, f)

    def finish(self, eng, out):
        d = self.cur
        stype = {st.sid: st.stype for st in eng.stalls}
        buyers = []
        for p in eng.buyers:
            reach = d["reach"].get(p.pid, {})
            decs = d["decisions"].get(p.pid, [])
            need = p.task["units"]
            bought = [b for b in eng.purchases if b["buyer"] == p.pid]
            if p.units >= need:
                status = "complete"
            elif p.units > 0:
                status = "partial"
            else:
                status = "empty"
            if p.active and not p.done:
                end = "still in market at close"
            elif p.done:
                end = "finished route"
            else:
                end = "never arrived"
            lc = d["last_choose"].get(p.pid)
            tst = eng.by_sid.get(p.target) if p.target else None
            stuck = bool(p.active and not p.done and tst is not None and p.units < need
                         and tst in eng.reach(p.pos) and eng.is_open(tst) and len(p.seen) < p.search_k
                         and p.step < len(p.route) - 1)
            buyers.append({
                "pid": p.pid, "profile": p.profile, "bargain": bool(p.task.get("bargain")), "need": need,
                "units": p.units, "status": status, "end": end, "arrive": p.arrive,
                "set": sorted(p.consider or ()), "set_types": [stype[s] for s in sorted(p.consider or ())],
                "reach": reach, "inspect_spent": p.inspect_spent_cents, "paid": p.paid_cents,
                "budget": p.task["budget_cents"], "n_decisions": len(decs),
                "actions": dict(Counter(x[1] for x in decs)),
                "inspected": sorted({x[2] for x in decs if x[1] == "inspect"}),
                "asked": sorted({x[2] for x in decs if x[1] == "ask"}),
                "bought_from": [b["stall"] for b in bought], "skipped": d["skipped"].get(p.pid, 0),
                "last_choose": lc, "target": p.target, "stuck": stuck, "n_seen": len(p.seen),
                "search_k": p.search_k, "step": p.step, "route_len": len(p.route),
                "target_price": tst.price_cents if tst else None,
                "target_unit_cost": tst.unit_cost_cents if tst else None})
        stalls = {}
        for st in eng.stalls:
            if st.sid in self.watch:
                stalls[st.sid] = {"units": st.units_sold, "revenue": st.revenue_cents, "cost": st.cost_cents,
                                  "ad_spend": st.ad_spend_cents, "penalties": st.penalties_cents,
                                  "price": st.price_cents, "rating": st.rating, "unit_cost": st.unit_cost_cents,
                                  "seller": dict(d["seller"].get(st.sid, {})), "insp_near_ticks": d["insp_near"][st.sid]}
        self.days.append({"day": d["day"], "buyers": buyers, "stalls": stalls, "stall_types": stype,
                          "closed_ticks": dict(d["closed_ticks"]), "catches": len(eng.catch_events),
                          "n_stalls": dict(Counter(stype.values())), "ticks": eng.cfg.market.ticks,
                          "purchases": len(eng.purchases),
                          "sales_by_type": dict(Counter(b["stype"] for b in eng.purchases))})


def run_chain(cond: str, seed: int, days: int | None = None) -> tuple[list[str], list[dict]]:
    watch = sample_stalls(seed)
    c = benchmark.bust_config(config(cond, seed), None, benchmark.NEVER)
    if days is not None:
        c.market.days = days
    with Recorder(watch) as rec:
        bazaar.run(c)
    return watch, rec.days


def stall_day(watch, day, sid):
    """Per-stall day row: units, buyers with it in their set, reached it open, left without buying."""
    inc = reached = reached_open = left_without = 0
    why = Counter()
    insp = 0
    for b in day["buyers"]:
        if sid not in b["set"]:
            continue
        inc += 1
        r = b["reach"].get(sid)
        if r is None:
            why["never came within reach"] += 1
            continue
        reached += 1
        if not r["ever_open"]:
            why["closed whenever in reach"] += 1
            continue
        reached_open += 1
        insp += sid in b["inspected"]
        if sid in b["bought_from"]:
            continue
        left_without += 1
        if b["units"] >= b["need"]:
            why["bought elsewhere (task complete)"] += 1
        elif b["stuck"] and b["target"] == sid:
            why["stuck at this stall (chose it, may not buy)"] += 1
        elif b["stuck"]:
            why["stuck at another chosen stall"] += 1
        elif b["end"] == "still in market at close":
            why["day ended before choosing"] += 1
        elif b["last_choose"] and sid in b["last_choose"]["reasons"]:
            why[b["last_choose"]["reasons"][sid]] += 1
        else:
            why["other"] += 1
    s = day["stalls"][sid]
    return {"units": s["units"], "in_set": inc, "reached": reached, "reached_open": reached_open,
            "left_without": left_without, "inspections": insp, "why": dict(why),
            "profit": (s["revenue"] - s["cost"] - s["ad_spend"] - s["penalties"]) / 100,
            "ad_spend": s["ad_spend"] / 100, "seller": s["seller"], "insp_near_ticks": s["insp_near_ticks"],
            "price": s["price"] / 100, "rating": s["rating"]}


def market_day(day):
    bs = day["buyers"]
    st = Counter(b["status"] for b in bs)
    empty = [b for b in bs if b["status"] != "complete"]
    why = Counter()
    for b in empty:
        sets = b["reach"]
        open_seen = [s for s, r in sets.items() if r["ever_open"]]
        if b["stuck"]:
            why["stuck at its chosen stall (phase reverted to browse)"] += 1
        elif b["end"] == "still in market at close":
            why["day ended while still shopping"] += 1
        elif not sets:
            why["no set stall within reach"] += 1
        elif not open_seen:
            why["every set stall in reach was closed"] += 1
        elif b["last_choose"]:
            rs = [r for s, r in b["last_choose"]["reasons"].items()]
            if not rs:
                why["chose with nothing seen"] += 1
            else:
                why["no candidate: " + "/".join(sorted(set(rs)))] += 1
        else:
            why["never reached the choose phase"] += 1
    closed_at_arrival = Counter()
    for b in bs:
        for s, r in b["reach"].items():
            closed_at_arrival["set stalls reached"] += 1
            closed_at_arrival["closed at first reach"] += not r["open_first"]
            closed_at_arrival["closed whenever in reach"] += not r["ever_open"]
    prof = Counter(b["profile"] for b in bs)
    insp = {p: float(np.mean([len(b["inspected"]) for b in bs if b["profile"] == p])) for p in prof}
    spent = {p: float(np.mean([b["inspect_spent"] / max(1, b["budget"]) for b in bs if b["profile"] == p]))
             for p in prof}
    status_by_profile = {p: dict(Counter(b["status"] for b in bs if b["profile"] == p)) for p in prof}
    return {"purchases": day["purchases"], "sales_by_type": day["sales_by_type"], "status": dict(st),
            "why_not_complete": dict(why.most_common()), "closed": dict(closed_at_arrival),
            "inspections_per_buyer": insp, "inspect_share_of_budget": spent,
            "status_by_profile": status_by_profile, "catches": day["catches"],
            "closed_stall_ticks": day["closed_ticks"], "n_stalls": day["n_stalls"],
            "skipped_targets": sum(b["skipped"] for b in bs)}


def detail():
    seed = 200
    out = {}
    for cond in ("A|t40|l1", "B|t40|l1", "A|t100", "B|t100"):
        watch, days = run_chain(cond, seed, days=5)
        out[cond] = {"watch": watch,
                     "stalls": {d["day"]: {s: stall_day(watch, d, s) for s in watch} for d in days},
                     "market": {d["day"]: market_day(d) for d in days},
                     "buyers": {d["day"]: d["buyers"] for d in days}}
        print(cond, "done", file=sys.stderr, flush=True)
    return out


def repro(seed: int = 200):
    """Minimal reproduction, with no inspectors and no catches: one day, tourists only, choice-set demand
    (m 3). Close one deceptive stall for the whole day by hand and count buyers who end the day standing
    at a stall they chose, unable to buy."""
    import copy
    from engine.config import load
    from analysis.verification import overrides
    cfg = load(None, [*overrides("A|t100"), "market.days=1", f"seed={seed}"], mode="bazaar")
    res = {}
    for close in (False, True):
        eng = BazaarEngine(copy.deepcopy(cfg))
        dec = [st for st in eng.stalls if st.stype == "deceptive"]
        target = max(dec, key=lambda st: sum(st.sid in p.consider for p in eng.buyers))
        if close:
            target.closed_until = eng.cfg.market.ticks
        trace = {}
        orig = BazaarEngine.search_decide

        def sd(e, p, stay):
            route_end = p.step >= len(p.route) - 1
            phase = "choose" if (len(p.seen) >= p.search_k or route_end) else "browse"
            out = orig(e, p, stay)
            if target.sid in p.consider and p.pid not in trace and p.target is not None and phase == "choose":
                trace[p.pid] = {"t": e.t, "chose": p.target, "at_route_end": route_end, "seen": sorted(p.seen)}
            return out
        BazaarEngine.search_decide = sd
        try:
            out = eng.run()
        finally:
            BazaarEngine.search_decide = orig
        stuck = [p for p in eng.buyers if p.active and not p.done and p.target is not None
                 and p.units < p.task["units"]]
        ex = None
        if stuck:
            p = stuck[0]
            tst = eng.by_sid[p.target]
            ex = {"buyer": p.pid, "set": sorted(p.consider), "closed_stall": target.sid, "seen": sorted(p.seen),
                  "search_k": p.search_k, "step": p.step, "route_len": len(p.route), "target": p.target,
                  "target_open": eng.is_open(tst), "target_in_reach": tst in eng.reach(p.pos),
                  "chose_at": trace.get(p.pid)}
        res["closed" if close else "control"] = {
            "closed_stall": target.sid, "buyers_with_it_in_set": sum(target.sid in p.consider for p in eng.buyers),
            "purchases": out["purchases"], "stuck": len(stuck),
            "stuck_with_closed_stall_in_set": sum(target.sid in p.consider for p in stuck),
            "invalid_buyer_actions": out["fallbacks"]["buyer"], "example": ex}
    return res


def _summary_job(args):
    cond, seed = args
    watch, days = run_chain(cond, seed)
    rows = []
    for d in days:
        bs = d["buyers"]
        lost = {s: 0 for s in watch}
        lost_units = {s: 0 for s in watch}
        for b in bs:
            if b["stuck"] and b["target"] in lost:
                u = b["need"] - b["units"]
                lost_units[b["target"]] += u
                lost[b["target"]] += u * (b["target_price"] - b["target_unit_cost"])
        rows.append({"day": d["day"], "purchases": d["purchases"], "stuck": sum(b["stuck"] for b in bs),
                     "still_in_market": sum(b["end"] == "still in market at close" for b in bs),
                     "stuck_units": sum(b["need"] - b["units"] for b in bs if b["stuck"]),
                     "stuck_target_types": dict(Counter(d["stall_types"].get(b["target"]) for b in bs if b["stuck"])),
                     "profit": {s: d["stalls"][s]["revenue"] - d["stalls"][s]["cost"] - d["stalls"][s]["ad_spend"]
                                - d["stalls"][s]["penalties"] for s in watch},
                     "units": {s: d["stalls"][s]["units"] for s in watch},
                     "lost_profit_stuck": lost, "lost_units_stuck": lost_units,
                     "sales_by_type": d["sales_by_type"], "catches": d["catches"]})
    return {"cond": cond, "seed": seed, "watch": watch, "days": rows}


def summary(seeds, conds, workers=4):
    from concurrent.futures import ProcessPoolExecutor
    jobs = [(c, s) for c in conds for s in seeds]
    with ProcessPoolExecutor(workers, initializer=os.nice, initargs=(19,)) as ex:
        out = []
        for i, r in enumerate(ex.map(_summary_job, jobs)):
            out.append(r)
            print(f"{i + 1}/{len(jobs)} {r['cond']} {r['seed']}", file=sys.stderr, flush=True)
    return out


if __name__ == "__main__":
    os.nice(19)
    what = sys.argv[1]
    if what == "detail":
        res = detail()
        path = sys.argv[2] if len(sys.argv) > 2 else "honest_detail.json"   # detail(): 5 days
        with open(path, "w") as f:
            json.dump(res, f, default=list)
        print("wrote", path)
    elif what == "repro":
        print(json.dumps(repro(), indent=1, default=list))
    elif what == "summary":
        seeds = parse_seeds(sys.argv[2])
        conds = sys.argv[3].split(",")
        res = summary(seeds, conds)
        with open(sys.argv[4], "w") as f:
            json.dump(res, f)
        print("wrote", sys.argv[4])
