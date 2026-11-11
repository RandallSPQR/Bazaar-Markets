"""Licensing (engine 0.16.0; licensing.*, off while licensing.schedule is empty).

A genuine brand owner licenses its name to N licensee stalls: non-genuine stalls (seconds or deceptive)
of its category, drawn from the dedicated stream [seed, 19, owner index] (a permutation of the
candidates in stall order, so the first 2 licensees are the same whether N is 2 or 6; then one quality
draw per candidate, in permutation order). Decided 2026-11-11:
  * The licence takes effect at the start of day b, before prices are set and agents are made, and
    binds to the last day: a licensee never renames (it is not offered a rename after a catch).
  * From day b a licensee bears the brand's name, posts the price of the owner's stall and claims the
    owner's true quality. "cheap": its true quality is drawn from stalls.q_low, its sign shows the
    claim ("pitch" per stalls.deceptive_sign) and it is run by agents.seller.deceptive's policy.
    "contract": its true quality is the owner's, its sign "truth", and it is run by rule_honest.
    Unit cost follows its true quality. Its type (stype) is unchanged.
  * Each unit a licensee sells pays the owner round(royalty x price) (licensee cost, owner income).
  * Buyers file reviews of licensee sales under the brand (the licensee bears the name), so licensee
    sales move the brand's rating; inspection reveals the licensee's true quality.
  * licensing.owner_liable: a fine from a catch at a licensee is charged to its owner (closure still
    falls on the licensee). Otherwise the licensee pays, as anyone does.
Stall profit = revenue - cost - ad spend - penalties - switch cost - royalties paid + royalties received.
"""
from __future__ import annotations

import numpy as np

from . import brands as B

QUALITIES = ("cheap", "contract")
STREAM = 19


def on(cfg) -> bool:
    return bool(cfg.licensing.schedule)


def validate(cfg, stalls: list) -> None:
    lc = cfg.licensing
    if not lc.schedule:
        return
    if not cfg.brands.enabled or int(cfg.market.days) < 2:
        raise ValueError("licensing needs brands.enabled and market.days >= 2")
    if lc.quality not in QUALITIES:
        raise ValueError(f"licensing.quality must be one of {QUALITIES}, got {lc.quality!r}")
    r = lc.royalty
    if isinstance(r, bool) or not isinstance(r, (int, float)) or not 0 <= r <= 1:
        raise ValueError(f"licensing.royalty must be in [0, 1], got {r!r}")
    by = {st.sid: st for st in stalls}
    for sid, spec in lc.schedule.items():
        st = by.get(sid)
        if st is None or st.stype != "genuine":
            raise ValueError(f"licensing owner {sid!r} must be a genuine stall")
        if set(spec) != {"day", "n"}:
            raise ValueError(f"licensing.schedule[{sid!r}] must be {{\"day\": b, \"n\": N}}, got {spec!r}")
        d, n = spec["day"], spec["n"]
        if any(isinstance(x, bool) or int(x) != x for x in (d, n)) or not 2 <= d <= int(cfg.market.days) or n < 1:
            raise ValueError(f"licensing.schedule[{sid!r}]: day must be in [2, market.days] and n >= 1, got {spec!r}")
        pool = [s for s in stalls if s.category == st.category and s.stype != "genuine"]
        if n > len(pool):
            raise ValueError(f"licensing.schedule[{sid!r}]: n = {n} but only {len(pool)} non-genuine stalls")


def policy(cfg, st) -> str:
    """The seller policy that runs a stall: its type's, or the licence's for a licensee."""
    if st.licensed_from is None:
        return cfg.agents.seller[st.stype]
    return cfg.agents.seller["deceptive"] if st.licence == "cheap" else "rule_honest"


def policies(cfg) -> list[str]:
    """Licence policies a run may use (for the log header)."""
    if not on(cfg):
        return []
    return [cfg.agents.seller["deceptive"] if cfg.licensing.quality == "cheap" else "rule_honest"]


def sign(cfg, st) -> str:
    return "truth" if st.licence == "contract" else cfg.stalls.deceptive_sign


def apply(cfg, stalls: list, day: int) -> list[dict]:
    """Grant the licences scheduled for `day` (start of the day). Mutates the stalls; returns records."""
    out = []
    lc = cfg.licensing
    for sid in sorted(lc.schedule, key=lambda s: next(st.idx for st in stalls if st.sid == s)):
        spec = lc.schedule[sid]
        if int(spec["day"]) != day:
            continue
        owner = next(st for st in stalls if st.sid == sid)
        pool = sorted((s for s in stalls if s.category == owner.category and s.stype != "genuine"),
                      key=lambda s: s.idx)
        rng = np.random.default_rng([cfg.seed, STREAM, owner.idx])
        order = [pool[int(i)] for i in rng.permutation(len(pool))]
        u = rng.random(len(order))
        lo = cfg.stalls.q_low
        chosen = []
        for st, ui in list(zip(order, u))[:int(spec["n"])]:
            if st.licensed_from is not None or st.exited_day is not None:
                raise ValueError(f"stall {st.sid} cannot take a licence (already licensed or exited)")
            q = owner.q_true if lc.quality == "contract" else round(lo[0] + (lo[1] - lo[0]) * float(ui), 4)
            rec = {"stall": st.sid, "stype": st.stype, "from_brand": st.brand, "q_was": st.q_true, "q_true": q}
            st.licensed_from, st.licence = owner.sid, lc.quality
            st.brand, st.counterfeit_of, st.rename_pending = owner.brand, None, False
            st.q_true, st.q_pitch = q, owner.q_true
            st.sign = sign(cfg, st)
            st.unit_cost_cents = B.unit_cost(cfg, st, q)
            chosen.append(rec)
        out.append({"day": day, "owner": owner.sid, "brand": owner.brand, "quality": lc.quality,
                    "royalty": float(lc.royalty), "owner_liable": bool(lc.owner_liable), "licensees": chosen})
    return out


def prices(stalls: list) -> None:
    """A licensee posts its owner's price (after morning prices)."""
    by = {st.sid: st for st in stalls}
    for st in stalls:
        if st.licensed_from is not None:
            st.price_cents = by[st.licensed_from].price_cents


def royalty_cents(cfg, st, units: int) -> int:
    return int(units) * int(round(float(cfg.licensing.royalty) * st.price_cents))


def outcome(eng) -> dict:
    """Today, per owner with licensees: royalties, licensee sales and quality, catches at licensees,
    fines by payer, and the owner's own sales."""
    by = {}
    fines_to = {}
    for ev in eng.catch_events:
        if ev.get("licensee_of"):
            d = fines_to.setdefault(ev["licensee_of"], {"catches": 0, "owner_cents": 0, "licensee_cents": 0})
            d["catches"] += 1
            d["owner_cents" if ev["fined"] != ev["stall"] else "licensee_cents"] += ev["penalty_cents"]
    for owner in eng.stalls:
        lic = [st for st in eng.stalls if st.licensed_from == owner.sid]
        if not lic:
            continue
        f = fines_to.get(owner.sid, {"catches": 0, "owner_cents": 0, "licensee_cents": 0})
        by[owner.sid] = {
            "brand": owner.brand, "licensees": [st.sid for st in lic],
            "licensee_q": {st.sid: st.q_true for st in lic},
            "royalties_cents": owner.royalty_received_cents,
            "licensee_units": sum(st.units_sold for st in lic),
            "licensee_revenue_cents": sum(st.revenue_cents for st in lic),
            "licensee_units_by_stall": {st.sid: st.units_sold for st in lic},
            "catches_at_licensees": f["catches"],
            "fines_at_licensees_to_owner_cents": f["owner_cents"],
            "fines_at_licensees_to_licensees_cents": f["licensee_cents"],
            "owner_units": owner.units_sold, "owner_revenue_cents": owner.revenue_cents,
        }
    return {"owners": by}
