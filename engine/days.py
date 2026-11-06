"""Multi-day bazaar with entry and exit (market.days = D > 1).

Each day is a full bazaar run. What persists and what is fresh:
  * Persist: stall locations, categories, brands and the stall list itself; each stall's type
    (genuine / seconds / deceptive) as changed by the between-day revision below.
  * Fresh each day: the buyer population and everything else drawn from engine streams
    (routes, people, treatments, inspectors, detection, observation noise, ids, agents).
    Day 1 uses the single-day streams ([seed, ...]); day d >= 2 uses the same streams under the
    prefix [seed, 9, d] in place of [seed]. So day 1 is exactly the single-day run, and day d's
    buyers are identical across conditions.
  * Reset each day: closures, epochs, catch notices, accounting, signs (to the type's default)
    and seller agents (a fresh agent per stall per day).

Between day d and day d+1 (for d < D), genuine and deceptive stalls may switch type by
pairwise proportional imitation, synchronously (everyone compares against day-d types):
  * with probability evolution.revise_prob a stall compares its day-d profit with a partner drawn
    uniformly from the other genuine and deceptive stalls of its category (decided 2026-11-05);
  * if the partner's type differs and it earned more, the stall switches with probability
    (profit difference) / M, where M = the largest absolute profit difference between genuine or
    deceptive stalls of the same category that day (per-category normaliser, decided 2026-11-05);
  * then mutation: each genuine or deceptive stall flips type with probability
    evolution.mutation_prob (applied to the post-imitation type);
  * seconds stalls never switch and are never partners.
A stall whose type changed gets new Q_true, Q_pitch and price by the type rules (world.py), with
new draws. All revision draws for stall i after day d come from its own stream
[seed, 10, d, i], six draws in a fixed order, so they do not depend on any other stream or stall.
Switching cost: none (PLACEHOLDER, 0).
"""
from __future__ import annotations

import copy

import numpy as np

from .config import BazaarConfig

SWITCHABLE = ("genuine", "deceptive")


def day_root(seed: int, day: int) -> tuple:
    """Stream prefix for a day: [seed] on day 1, [seed, 9, day] after."""
    return (seed,) if day == 1 else (seed, 9, day)


def stall_profit(st) -> int:
    return st.revenue_cents - st.cost_cents - st.ad_spend_cents - st.penalties_cents


def set_type(cfg: BazaarConfig, st, stype: str, hi: float, lo: float) -> None:
    """Rewrite a stall's type-dependent fields by the type rules of world.build_stalls."""
    pr = cfg.pricing
    base = pr.base_price_cents[st.category]
    if stype == "genuine":
        q_true, q_pitch, sign, price = hi, hi, "truth", base
    elif stype == "deceptive":
        q_true, q_pitch, sign, price = lo, hi, cfg.stalls.deceptive_sign, round(base * pr.deceptive_price_factor)
    else:
        raise ValueError(f"stalls cannot switch to {stype!r}")
    st.stype, st.q_true, st.q_pitch, st.sign, st.price_cents = stype, round(float(q_true), 4), round(float(q_pitch), 4), sign, int(price)
    st.unit_cost_cents = int(round(base * (pr.unit_cost[0] + pr.unit_cost[1] * float(q_true))))


def revise(cfg: BazaarConfig, stalls: list, profits: dict, day: int) -> list[dict]:
    """Between-day type revision after `day`. Mutates stalls; returns the switch records."""
    ev = cfg.evolution
    old = {st.sid: st.stype for st in stalls}
    by_cat: dict[str, list] = {}
    for st in stalls:
        if old[st.sid] in SWITCHABLE:
            by_cat.setdefault(st.category, []).append(st)
    norm = {c: (max(profits[s.sid] for s in ss) - min(profits[s.sid] for s in ss)) if ss else 0
            for c, ss in by_cat.items()}
    out = []
    for st in stalls:
        rng = np.random.default_rng([cfg.seed, 10, day, st.idx])
        u_rev, u_partner, u_switch, u_mut, hi_u, lo_u = rng.random(6)
        if old[st.sid] not in SWITCHABLE:
            continue
        new = old[st.sid]
        rec = {"stall": st.sid, "category": st.category, "from": old[st.sid], "profit_cents": profits[st.sid]}
        if u_rev < ev.revise_prob:
            cands = [s for s in by_cat[st.category] if s.sid != st.sid]
            if cands:
                partner = cands[int(u_partner * len(cands))]
                diff = profits[partner.sid] - profits[st.sid]
                rec.update(partner=partner.sid, partner_profit_cents=profits[partner.sid])
                if old[partner.sid] != new and diff > 0 and norm[st.category] > 0:
                    p = diff / norm[st.category]
                    rec["p_switch"] = p
                    if u_switch < p:
                        new = old[partner.sid]
                        rec["imitated"] = True
        if u_mut < ev.mutation_prob:
            new = "deceptive" if new == "genuine" else "genuine"
            rec["mutated"] = True
        if new != old[st.sid]:
            lo_q, hi_q = cfg.stalls.q_low, cfg.stalls.q_high
            set_type(cfg, st, new, hi_q[0] + (hi_q[1] - hi_q[0]) * hi_u, lo_q[0] + (lo_q[1] - lo_q[0]) * lo_u)
            rec["to"] = new
            out.append(rec)
    return out


def reset_for_day(cfg: BazaarConfig, stalls: list) -> list:
    """Fresh copies for a new day: accounting, closure and epoch reset; sign at its type default."""
    out = []
    for st in stalls:
        s = copy.copy(st)
        s.closed_until, s.epoch = -1, 0
        s.revenue_cents = s.cost_cents = s.ad_spend_cents = s.penalties_cents = 0
        s.units_sold = s.catches = 0
        s.sign = "truth" if s.stype != "deceptive" else cfg.stalls.deceptive_sign
        out.append(s)
    return out


def run_days(cfg: BazaarConfig, log=None, day_factories=None) -> dict:
    """Run cfg.market.days days. Log: the header once, then per day a `day_start` event, that
    day's world, ticks and outcome, and a `day_end` event with the day's summary and the switches
    made after it."""
    from .bazaar import BazaarEngine
    from .jsonlog import JsonlLog
    log = log if log is not None else JsonlLog(keep=False)
    D = int(cfg.market.days)
    if D < 1:
        raise ValueError(f"market.days must be >= 1, got {D}")
    stalls = None
    days = []
    for day in range(1, D + 1):
        fac = day_factories(day) if day_factories else None
        eng = BazaarEngine(cfg, log=log, agent_factory=fac, root=day_root(cfg.seed, day), stalls=stalls)
        types = _types(eng.stalls)
        if day == 1:
            eng.header_line()
        log.emit("day_start", day=day, types=types)
        out = eng.run(header=False)
        profits = {st.sid: stall_profit(st) for st in eng.stalls}
        switches = revise(cfg, eng.stalls, profits, day) if day < D else []
        pbt = {t: d["profit_per_stall_cents"] for t, d in sorted(out["seller_by_type"].items())}
        log.emit("day_end", day=day, types=types, profit_by_type=pbt, shortfall_rate=out["shortfall_rate"],
                 catches=out["catches"], switches=switches)
        days.append({"day": day, "types": types, "outcome": out, "switches": switches})
        stalls = reset_for_day(cfg, eng.stalls)
    return {"days": days}


def _types(stalls) -> dict:
    out = {"deceptive": 0, "genuine": 0, "seconds": 0}
    for st in stalls:
        out[st.stype] += 1
    return out
