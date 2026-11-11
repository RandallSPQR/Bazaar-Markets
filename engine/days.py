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
Switching costs: pricing.switch_cost_to_genuine / _to_deceptive (0.7.0; default 0).

Brands (0.8.0, brands.enabled; engine/brands.py): a BrandBook carries ratings by brand name
across days; each morning prices are set from the brand's start-of-day rating; at the end of the
day reviews are filed by brand (tourists' reviews of a counterfeit go to the original). Brands
cannot be combined with imitation (evolution.revise_prob and mutation_prob must be 0): a type
switch would rewrite a busted stall's quality and sign, and that combination is untested.
"""
from __future__ import annotations

import copy

import numpy as np

from . import brands as B
from . import critics as C
from . import licensing as LIC
from .config import BazaarConfig

SWITCHABLE = ("genuine", "deceptive")
EXITED = 1 << 40        # closed_until of a stall that has left the market (0.15.0)


def day_root(seed: int, day: int) -> tuple:
    """Stream prefix for a day: [seed] on day 1, [seed, 9, day] after."""
    return (seed,) if day == 1 else (seed, 9, day)


def stall_profit(st) -> int:
    return (st.revenue_cents - st.cost_cents - st.ad_spend_cents - st.penalties_cents - st.switch_cost_cents
            - st.royalty_paid_cents + st.royalty_received_cents)


def update_ratings(stalls: list, buys: list[dict], memory: float) -> None:
    """End-of-day rating update from the day's purchases. A unit is rated when the buyer had
    received at least one claim from the stall before buying; it is honest when the stall's true Q
    met the latest such claim. rating = share (first rating) or memory * rating + (1 - memory) *
    share; a stall with no rated units that day keeps its rating."""
    claimed: dict = {}
    honest: dict = {}
    for b in buys:
        if not b["known_claims"]:
            continue
        sid = b["stall"]
        claimed[sid] = claimed.get(sid, 0) + b["units"]
        if b["q_true"] >= b["known_claims"][-1] - 1e-12:
            honest[sid] = honest.get(sid, 0) + b["units"]
    for st in stalls:
        if claimed.get(st.sid):
            share = honest.get(st.sid, 0) / claimed[st.sid]
            st.rating = share if st.rating is None else memory * st.rating + (1 - memory) * share


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
            frac = cfg.pricing.switch_cost_to_genuine if new == "genuine" else cfg.pricing.switch_cost_to_deceptive
            if frac:
                st.switch_cost_due = int(round(cfg.pricing.base_price_cents[st.category] * frac))
                rec["switch_cost_cents"] = st.switch_cost_due
            if cfg.ratings.mode != "off":
                rec["rating"] = st.rating
                rec["rugpull"] = bool(old[st.sid] == "genuine" and new == "deceptive" and st.rating is not None
                                      and st.rating >= cfg.ratings.rugpull_threshold)
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
        s.switch_cost_cents = st.switch_cost_due   # charged on the first day in the new type
        s.switch_cost_due = 0
        s.sign = "truth" if s.stype != "deceptive" else cfg.stalls.deceptive_sign
        if s.busted_day is not None:
            s.sign = "pitch"                       # a busted stall keeps showing its old quality
        if s.licensed_from is not None:            # 0.16.0: a licensee shows the licence's sign
            s.sign = LIC.sign(cfg, s)
        s.royalty_paid_cents = s.royalty_received_cents = 0
        s.decided_today = False
        s.fines_pending = list(st.fines_pending)   # 0.15.0: lagged fines carry over
        if s.exited_day is not None:               # 0.15.0: a stall that left never reopens
            s.closed_until = EXITED
        s.yesterday = {"units_sold": st.units_sold, "revenue_cents": st.revenue_cents, "cost_cents": st.cost_cents,
                       "ad_spend_cents": st.ad_spend_cents, "penalties_cents": st.penalties_cents,
                       "profit_cents": stall_profit(st), "price_cents": st.price_cents, "catches": st.catches}
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
    brands = bool(cfg.brands.enabled)
    if brands and (cfg.evolution.revise_prob or cfg.evolution.mutation_prob):
        raise ValueError("brands.enabled requires evolution.revise_prob = evolution.mutation_prob = 0")
    stalls = None
    book = None
    days = []
    for day in range(1, D + 1):
        fac = day_factories(day) if day_factories else None
        eng = BazaarEngine(cfg, log=log, agent_factory=fac, root=day_root(cfg.seed, day), stalls=stalls,
                           day=day, book=book)
        book = eng.book
        types = _types(eng.stalls)
        rated = cfg.ratings.mode != "off"
        stall_types = {st.sid: st.stype for st in eng.stalls}
        if day == 1:
            eng.header_line()
        extra = {"ratings": {st.sid: st.rating for st in eng.stalls}} if rated else {}
        if brands:
            extra.update(brands={st.sid: st.brand for st in eng.stalls},
                         prices={st.sid: st.price_cents for st in eng.stalls})
        if eng.licensing_on:
            extra["licences"] = eng.licence_log
        log.emit("day_start", day=day, types=types, **extra)
        out = eng.run(header=False)
        profits = {st.sid: stall_profit(st) for st in eng.stalls}
        reviews = None
        crit = C.critics_day(cfg, book, eng.stalls, day_root(cfg.seed, day), day) if C.critics_on(cfg) else None
        if rated and brands:
            reviews = B.update_brand_ratings(book, eng.purchases, cfg.ratings.memory,
                                             extra=None if crit is None else
                                             [(r["brand"], r["positive"], float(cfg.critics.weight)) for r in crit["filed"]])
            for st in eng.stalls:
                st.rating = book.rating(st.brand)
        elif rated:
            update_ratings(eng.stalls, eng.purchases, cfg.ratings.memory)
        if brands:
            liars = sum(st.stype == "deceptive" or st.busted_day is not None for st in eng.stalls)
            book.catch_rate_yesterday = out["catches"] / liars if liars else 0.0
        switches = revise(cfg, eng.stalls, profits, day) if day < D else []
        pbt = {t: d["profit_per_stall_cents"] for t, d in sorted(out["seller_by_type"].items())}
        extra = {}
        if rated:
            extra = {"ratings": {st.sid: st.rating for st in eng.stalls},
                     "rugpulls": sum(s["rugpull"] for s in switches)}
        if brands:
            extra.update(brand_ratings=dict(sorted(book.ratings.items())),
                         brands={st.sid: st.brand for st in eng.stalls},
                         counterfeit_of={st.sid: st.counterfeit_of for st in eng.stalls if st.counterfeit_of},
                         prices={st.sid: st.price_cents for st in eng.stalls},
                         renames=eng.rename_log, bust_outs=eng.bust_log,
                         busted={st.sid: st.busted_day for st in eng.stalls if st.busted_day is not None},
                         **({"reviews": {n: list(v) for n, v in reviews.items()}} if reviews is not None else {}))
        if crit is not None:
            extra["critic_reviews"] = crit
        log.emit("day_end", day=day, types=types, profit_by_type=pbt, shortfall_rate=out["shortfall_rate"],
                 catches=out["catches"], switches=switches, **extra)
        if rated:
            extra["stall_types"] = stall_types
        days.append({"day": day, "types": types, "outcome": out, "switches": switches, **extra})
        stalls = reset_for_day(cfg, eng.stalls)
    guard = {k: {"by_day": [d["outcome"][k] for d in days], "total": sum(d["outcome"][k] for d in days)}
             for k in ("stuck_buyers", "idle_choosers")}
    return {"days": days, **guard, "liability": liability_total(days, stalls)}


def liability_total(days: list, stalls: list) -> dict:
    """Run totals of the daily liability outcomes (0.15.0). Outstanding = fines not yet due at the
    end of the last day, of stalls still in the market (due after the horizon: never charged).
    exited: {stall: the day at whose end it left}."""
    L = [d["outcome"]["liability"] for d in days]
    out = {k: sum(x[k] for x in L) for k in ("fines_charged", "fines_charged_cents", "fines_uncollectible",
                                             "fines_uncollectible_cents", "deceptive_catches")}
    out["fines_outstanding"] = L[-1]["fines_outstanding"]
    out["fines_outstanding_cents"] = L[-1]["fines_outstanding_cents"]
    out["deceptive_stall_days"] = sum(x["deceptive_stalls"] for x in L)
    out["catches_per_deceptive_stall_day"] = (out["deceptive_catches"] / out["deceptive_stall_days"]
                                              if out["deceptive_stall_days"] else None)
    by: dict = {}
    for x in L:
        for sid, v in x["by_stall"].items():
            d = by.setdefault(sid, {"charged_cents": 0, "uncollectible_cents": 0, "outstanding_cents": 0})
            d["charged_cents"] += v["charged_cents"]
            d["uncollectible_cents"] += v["uncollectible_cents"]
    for st in stalls:
        if st.fines_pending:
            by.setdefault(st.sid, {"charged_cents": 0, "uncollectible_cents": 0, "outstanding_cents": 0})
            by[st.sid]["outstanding_cents"] = sum(f["cents"] for f in st.fines_pending)
    out["by_stall"] = dict(sorted(by.items()))
    out["exited"] = {st.sid: st.exited_day for st in sorted(stalls, key=lambda s: s.idx) if st.exited_day is not None}
    return out


def _types(stalls) -> dict:
    out = {"deceptive": 0, "genuine": 0, "seconds": 0}
    for st in stalls:
        out[st.stype] += 1
    return out
