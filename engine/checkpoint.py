"""Checkpoint and continue (engine 1.1.0): stop a multi-day run after day d, then run days d+1..D from a copy of
its state, under one of a set of seller options for one stall.

    snap = snapshot(cfg, d)                       # days 1..d, as in the full run
    out = continue_from(snap, k=3)                # days d+1..D on fresh streams, continuation 3
    out = continue_from(snap, original=True)      # days d+1..D on the run's own streams: the full run, bit for bit

(The plan's name `engine.continue` is a Python keyword, so the function is `continue_from`.)

Streams. In continuation k every stochastic stream of days d+1..D is re-seeded with [seed, 31, k] in place of
[seed]: the day streams [seed, 9, day, ...] become [seed, 31, k, 9, day, ...], and the streams keyed on the seed
alone (the tie-break [seed, 29, day, buyer], logit choice [seed, 37, day, buyer], counterfeit entry [seed, 23],
licensing [seed, 19, owner] and [seed, 24, owner], type revision [seed, 10, day, stall]) become [seed, 31, k, ...]. Two fixed stall
attributes are not streams and are kept: each stall's bust-out quality ([seed, 12, stall], its cheap-supply quality)
and the critics' ties drawn on day 1. With original=True no stream changes, so continuing gives the full run.

Seller options (OPTIONS), for one stall `sid`, a genuine stall that has not busted out, from day d + 1:
  honest              nothing changes (the stall stays honest, under its own policy);
  switch_now / _d5 / _d10   cheap supply from day d+1 / d+5 / d+10 (a bust-out under the same name, sign and price
                      policy: rule_genuine_bust_at for this stall only); skipped if that day is past the last day;
  license_contract_6 / license_cheap_6   the stall licenses its name to 6 stalls of its category from day d+1
                      (licensing.schedule, contract or cheap quality, royalty 0.10);
  exit                the stall closes at the end of day d (exited_day = d), keeping its profit so far; fines not yet
                      due become uncollectible.
Each option changes only this stall's actions (and, for a licence, the licensees it takes).
"""
from __future__ import annotations

import copy
import dataclasses

from . import days as DAYS
from .config import BazaarConfig

CONT_STREAM = 31
OPTIONS = ("honest", "switch_now", "switch_d5", "switch_d10", "license_contract_6", "license_cheap_6", "exit")
SWITCH_DELAY = {"switch_now": 1, "switch_d5": 5, "switch_d10": 10}
LICENCE_N, LICENCE_ROYALTY = 6, 0.10


@dataclasses.dataclass
class Snapshot:
    cfg: BazaarConfig
    day: int
    state: dict          # {"stalls", "book", "days"} after day `day` (stalls reset for day + 1)


def snapshot(cfg: BazaarConfig, day: int, log=None, tap=None) -> Snapshot:
    """Run days 1..day and keep the state. tap(day, engine) as in engine.days.run_span."""
    from .jsonlog import JsonlLog
    D = int(cfg.market.days)
    if not 1 <= int(day) < D:
        raise ValueError(f"snapshot day must be in [1, market.days - 1], got {day!r}")
    state = {"stalls": None, "book": None, "days": []}
    DAYS.run_span(cfg, log if log is not None else JsonlLog(keep=False), state, 1, int(day), tap=tap)
    return Snapshot(cfg=cfg, day=int(day), state=state)


def option_day(option: str, d: int) -> int | None:
    """The first day an option acts on (None for honest and exit)."""
    if option in SWITCH_DELAY:
        return d + SWITCH_DELAY[option]
    if option.startswith("license_"):
        return d + 1
    return None


def skipped(option: str, d: int, D: int) -> bool:
    b = option_day(option, d)
    return b is not None and b > D


def option_cfg(cfg: BazaarConfig, option: str, sid: str, d: int) -> BazaarConfig:
    """The config of days d+1..D under an option (only licence and switch options differ from cfg)."""
    if option == "honest" or option == "exit":
        return cfg
    c = copy.deepcopy(cfg)
    if option in SWITCH_DELAY:
        c.agents.params = dict(c.agents.params)
        c.agents.params["rule_genuine_bust_at"] = {"schedule": {sid: option_day(option, d)}}
        return c
    if option in ("license_contract_6", "license_cheap_6"):
        if c.licensing.schedule:
            raise ValueError("a licence option needs a market with no other licences")
        lc = c.licensing
        lc.schedule = {sid: {"day": d + 1, "n": LICENCE_N}}
        lc.quality = "contract" if option == "license_contract_6" else "cheap"
        lc.royalty = LICENCE_ROYALTY
        return c
    raise ValueError(f"unknown option {option!r}; known: {OPTIONS}")


def continue_from(snap: Snapshot, option: str = "honest", sid: str | None = None, k: int | None = None,
                  original: bool = False, log=None, tap=None) -> dict | None:
    """Run days d+1..D from a copy of the snapshot. k: continuation index (streams [seed, 31, k]); original=True:
    the run's own streams. Returns the run's result (days 1..D, as engine.bazaar.run returns it), or None if the
    option is skipped (its day is past the last day). tap(day, engine) as in engine.days.run_span."""
    from .jsonlog import JsonlLog
    if option not in OPTIONS:
        raise ValueError(f"unknown option {option!r}; known: {OPTIONS}")
    if original == (k is not None):
        raise ValueError("give exactly one of k (a continuation index) or original=True")
    cfg, d = snap.cfg, snap.day
    D = int(cfg.market.days)
    if skipped(option, d, D):
        return None
    st0 = snap.state
    state = {"stalls": copy.deepcopy(st0["stalls"]), "book": copy.deepcopy(st0["book"]), "days": list(st0["days"])}
    wrap = None
    if option != "honest":
        if sid is None:
            raise ValueError("an option other than honest needs the stall id")
        st = next((s for s in state["stalls"] if s.sid == sid), None)
        if st is None or st.stype != "genuine" or st.busted_day is not None or st.licensed_from is not None \
                or st.exited_day is not None:
            raise ValueError(f"options apply to a genuine stall still honest and in the market; {sid!r} is not")
        if option == "exit":
            st.exited_day, st.closed_until, st.exit_pending = d, DAYS.EXITED, False
            st.fines_pending = []          # due after the stall left: uncollectible, never charged
        elif option in SWITCH_DELAY:
            def wrap(fac, day, _sid=sid):
                def f(role, policy, key, idx):
                    if role == "seller" and key == _sid:
                        policy = "rule_genuine_bust_at"
                    return fac(role, policy, key, idx)
                return f
    ccfg = option_cfg(cfg, option, sid, d)
    sroot = None if original else (int(cfg.seed), CONT_STREAM, int(k))
    DAYS.run_span(ccfg, log if log is not None else JsonlLog(keep=False), state, d + 1, D, sroot=sroot,
                  factory_wrap=wrap, tap=tap)
    return DAYS.finish(state)
