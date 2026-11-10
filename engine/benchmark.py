"""Ex-post best bust-out benchmark (engine 0.11.0). An analysis tool, not a policy.

For a genuine stall s and a set of candidate bust-out days, run the same market once per
candidate with s on rule_genuine_bust_at (busting out on its first decision of day b) and every
other genuine stall honest (rule_genuine_bust_at with nothing scheduled, which is rule_honest),
then compare s's total profit over all days:
    gain_floored   = max over all candidates (including "never") - total if it never busts out
                     (the spec's definition; never below 0)
    gain_unfloored = max over the bust-out days only - total if it never busts out
                     (primary outcome of the 2026-11-07 capture run; can be negative)
The "never" run is the same for every stall of a seed and condition, so callers may run it once.
"""
from __future__ import annotations

import copy

from . import bazaar

NEVER = "never"
# Candidate bust-out days (0.12.0; was never, 10, 20, 27).
CANDIDATES = (NEVER, 10, 20, 25, 27, 28, 29)
POLICY = "rule_genuine_bust_at"


def bust_config(cfg, sid: str | None, day):
    """A copy of cfg in which genuine stalls run rule_genuine_bust_at, stall `sid` scheduled to
    bust out on `day` (None or NEVER: nobody busts out). day may be an exit candidate (b, h) (0.15.0):
    bust out on day b and leave the market at the end of day b + h - 1."""
    if not cfg.brands.enabled or not cfg.market.horizon_known or int(cfg.market.days) < 2:
        raise ValueError("the bust-out benchmark needs brands.enabled, market.horizon_known and market.days >= 2")
    if cfg.agents.seller.get("genuine") not in ("rule_honest", POLICY):
        raise ValueError("the bust-out benchmark compares against always-honest genuine stalls")
    c = copy.deepcopy(cfg)
    c.agents.seller = {**c.agents.seller, "genuine": POLICY}
    exit_at = {}
    if isinstance(day, (tuple, list)):
        b, h = (int(x) for x in day)
        if h < 1 or b + h - 1 > int(cfg.market.days):
            raise ValueError(f"exit candidate {tuple(day)!r} must have h >= 1 and b + h - 1 <= market.days")
        sched, exit_at = ({}, {}) if sid is None else ({sid: b}, {sid: b + h - 1})
    else:
        sched = {} if sid is None or day in (None, NEVER) else {sid: int(day)}
    p = {**c.agents.params.get(POLICY, {}), "schedule": sched}
    if exit_at:
        p["exit_at"] = exit_at
    c.agents.params = {**c.agents.params, POLICY: p}
    return c


def stall_total(out: dict, sid: str) -> int:
    """Total profit of one stall over every day of a multi-day run (cents)."""
    return int(sum(d["outcome"]["brands"]["profit_by_stall_cents"][sid] for d in out["days"]))


def gain(totals: dict) -> dict:
    """totals: {NEVER: cents, day: cents, ...}. Best day and both gains (cents)."""
    if NEVER not in totals:
        raise ValueError("totals need the never-bust-out run")
    never = totals[NEVER]
    days = {k: v for k, v in totals.items() if k != NEVER}
    best_any = max(totals.values())
    out = {"never": never, "totals": dict(totals), "gain_floored": best_any - never,
           "best_day": None, "gain_unfloored": None}
    if days:
        b = max(sorted(days), key=lambda k: days[k])     # earliest day on a tie
        out.update(best_day=b, gain_unfloored=days[b] - never)
    return out


def candidates(days, horizon: int) -> tuple:
    """A candidate list (0.13.0): NEVER plus the given bust-out days, which must be distinct
    integers in [2, horizon] (day 1 has no yesterday). Returned sorted, NEVER first."""
    ds = [d for d in days if d != NEVER]
    if any(int(d) != d for d in ds) or len(set(ds)) != len(ds) or any(not 2 <= d <= horizon for d in ds):
        raise ValueError(f"bust-out days must be distinct integers in [2, {horizon}], got {list(days)!r}")
    return (NEVER, *sorted(int(d) for d in ds))


def exit_candidates(bs, hs, horizon: int) -> tuple:
    """Bust-out-and-exit candidates (0.15.0): NEVER plus (b, h) for every b in bs and h in hs: bust
    out on day b, leave at the end of day b + h - 1. Needs 2 <= b and b + h - 1 <= horizon, h >= 1."""
    out = []
    for b in sorted(set(int(x) for x in bs)):
        for h in sorted(set(int(x) for x in hs)):
            if not 2 <= b or h < 1 or b + h - 1 > horizon:
                raise ValueError(f"exit candidate ({b}, {h}) does not fit a {horizon}-day horizon")
            out.append((b, h))
    return (NEVER, *out)


def best_response(cfg, sid: str, candidates=CANDIDATES, run=bazaar.run) -> dict:
    """Run every candidate for stall `sid` and return gain(totals). candidates: any list made of
    NEVER and bust-out days (see candidates())."""
    totals = {}
    for b in candidates:
        out = run(bust_config(cfg, None if b == NEVER else sid, b))
        totals[b] = stall_total(out, sid)
    return gain(totals)
