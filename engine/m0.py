"""M0 compatibility mode: the prototype's unit-square advertising model.

This is a port of the prototype. Two reference versions are bundled:
  tests/reference/sim_prototype.py     v0, original sim.py (idle firms fitness -1e-9)
  tests/reference/sim_prototype_v1.py  v1, corrected idle rule; used for every doc result
With tie_break="numpy_default", the port reproduces each prototype bit for bit on the
same platform: selection="prototype_v0" matches v0 and selection="idle_lowest" matches
v1 (enforcer_mode "fixed" or "redraw_main", cap_mode "batch"). tests/test_m0.py checks
both. The default tie_break="stable" makes results identical across platforms; the
prototypes' default argsort breaks the ties among idle firms differently on different
numpy builds (doc numbers: numpy 2.5.3 on x86 gave 0.695 at baseline; numpy 2.2.6 on
arm64 gives 0.688 for the same code and seeds).

Model, as in the prototype:
  * customers are fixed points in [0,1]^2; a fixed random f_enf of them are enforcers;
  * advertisers have a location, a radius (log-uniform in [r_min, r_max]),
    a bid and a type (deceptive or honest);
  * each generation, T impressions go to uniformly drawn customers in 40
    sequential batches; each is a first-price auction among advertisers whose
    radius covers the customer and who are under the budget cap
    (cap_mult x fair share per generation);
  * a sale happens if the winner is within d_sale; honest earn m, deceptive
    earn m(1+delta) but pay P when the impression reaches an enforcer;
  * selection: the bottom `keep` share copy the top `keep` share with mutation;
    type flips with probability `flip`. Which firms count as "bottom" depends on
    cfg.selection (see config): "idle_lowest" (prototype v1, default) or
    "prototype_v0" (original sim.py, historical compatibility).
  * the impression cap is an impression limit, not a money budget; cfg.cap_mode
    picks the prototypes' soft batch-level check or strict per-impression enforcement.

enforcer_mode="redraw" is the mechanism test: same geometry and rate, but
each impression's enforcer status is drawn fresh at rate f_enf, so no fixed
pockets exist. Its draws come from a separate stream, so paired runs share every
other random number until their populations diverge (the better design).
enforcer_mode="redraw_main" draws from the main stream instead, exactly as
tests/reference/tighten_v1.py did; it exists to reproduce the doc's
mechanism-test numbers bit for bit.
"""
from __future__ import annotations

import numpy as np

from . import ENGINE_VERSION
from .config import M0Config, to_dict
from .jsonlog import JsonlLog, env_info


def break_even(m: float = 1.0, delta: float = 0.2, P: float = 5.0, s: float = 1.0) -> float:
    """Analytic enforcer rate at which deception stops paying when enforcer
    status is independent per impression: e* = s m delta / (s m (1+delta) + P)."""
    return s * m * delta / (s * m * (1 + delta) + P)


def run(cfg: M0Config, log: JsonlLog | None = None, return_state: bool = False):
    if cfg.enforcer_mode not in ("fixed", "redraw", "redraw_main"):
        raise ValueError(f"enforcer_mode must be 'fixed', 'redraw' or 'redraw_main', got {cfg.enforcer_mode!r}")
    if cfg.selection not in ("idle_lowest", "prototype_v0"):
        raise ValueError(f"selection must be 'idle_lowest' or 'prototype_v0', got {cfg.selection!r}")
    if cfg.tie_break not in ("stable", "numpy_default"):
        raise ValueError(f"tie_break must be 'stable' or 'numpy_default', got {cfg.tie_break!r}")
    if cfg.cap_mode not in ("batch", "strict"):
        raise ValueError(f"cap_mode must be 'batch' or 'strict', got {cfg.cap_mode!r}")
    n_cust, n_adv, f_enf = cfg.n_cust, cfg.n_adv, cfg.f_enf
    r_min, r_max, d_sale = cfg.r_min, cfg.r_max, cfg.d_sale
    m, delta, P, keep, flip = cfg.m, cfg.delta, cfg.P, cfg.keep, cfg.flip
    redraw = cfg.enforcer_mode == "redraw"
    redraw_main = cfg.enforcer_mode == "redraw_main"

    if log is not None:
        log.emit("header", mode="m0", engine_version=ENGINE_VERSION, config=to_dict(cfg), env=env_info(),
                 agents={"advertisers": {"policy": "m0_evolutionary", "model_id": None, "sampling": None}},
                 break_even=break_even(m, delta, P))

    # --- prototype code path; keep RNG call order identical to sim.py ---
    rng = np.random.default_rng(cfg.seed)
    rng_e = np.random.default_rng([cfg.seed, 1]) if redraw else None
    T = cfg.T or 20 * n_adv
    cust = rng.random((n_cust, 2)); enf = rng.random(n_cust) < f_enf
    loc = rng.random((n_adv, 2)); bid = rng.random(n_adv) * 0.5
    rad = np.exp(rng.uniform(np.log(r_min), np.log(r_max), n_adv))
    dec = rng.random(n_adv) < 0.5
    hist = []
    for g in range(cfg.gens):
        idx = rng.integers(0, n_cust, T)
        c = cust[idx]
        if redraw_main:
            e = rng.random(T) < f_enf
        else:
            e = (rng_e.random(T) < f_enf) if redraw else enf[idx]
        cap = int(cfg.cap_mult * T / n_adv); used = np.zeros(n_adv, int); overflow = 0
        W = []; D = []; E = []; OK = []
        for ch in np.array_split(np.arange(T), 40):
            cc = c[ch]; ee = e[ch]
            d = np.sqrt(((cc[:, None, :] - loc[None, :, :]) ** 2).sum(-1))
            elig = (d <= rad[None, :]) & (used < cap)[None, :]
            b = np.where(elig, bid[None, :], -1.0)
            if cfg.cap_mode == "strict":
                w, ok = _strict_auction(b, cap - used)
            else:
                w = b.argmax(1); ok = b.max(1) > 0
                won = np.bincount(w[ok], minlength=n_adv)
                overflow += int(np.maximum(0, used + won - cap).sum())
            used += np.bincount(w[ok], minlength=n_adv)
            W.append(w[ok]); D.append(d[ok, w[ok]]); E.append(ee[ok]); OK.append(ok)
        w = np.concatenate(W); d_w = np.concatenate(D); e_w = np.concatenate(E); ok = np.concatenate(OK)
        sale = d_w < d_sale
        dw = dec[w]
        revenue = np.where(dw, np.where(e_w, 0.0, sale * m * (1 + delta)), sale * m)
        penalty = np.where(dw & e_w, P, 0.0)
        gain = np.where(dw, np.where(e_w, -P, sale * m * (1 + delta)), sale * m) - bid[w]
        profit = np.bincount(w, weights=gain, minlength=n_adv)
        wins = np.bincount(w, minlength=n_adv)
        # A realized sale: within sale distance, and not a deceptive impression that
        # reached an enforcer (that one earns no revenue and pays P instead).
        realized = sale & ~(dw & e_w)
        rec = dict(dec_share_imp=dw.mean() if len(dw) else np.nan,
                   dec_pop=dec.mean(),
                   fill=ok.mean())
        hist.append(rec)
        if log is not None:
            n_sales = int(realized.sum())
            log.emit("generation", g=g, **rec,
                     impressions=int(len(w)), sales=n_sales,
                     dec_share_sales=float((dw & realized).sum() / n_sales) if n_sales else None,
                     cap_overflow=overflow,
                     catches=int((dw & e_w).sum()),
                     ad_spend=float(bid[w].sum()), revenue=float(revenue.sum()),
                     penalties=float(penalty.sum()), profit=float(profit.sum()))
        # selection
        if cfg.selection == "prototype_v0":
            fit = np.where(wins > 0, profit, -1e-9)  # v0: idle firms still outrank loss-makers
        else:
            fit = np.where(wins > 0, profit, profit.min() - 1.0)  # v1: idle firms rank lowest
        order = np.argsort(fit, kind="stable") if cfg.tie_break == "stable" else np.argsort(fit)
        k = int(keep * n_adv)
        lose, win = order[:k], order[-k:]
        loc[lose] = np.clip(loc[win] + rng.normal(0, 0.03, (k, 2)), 0, 1)
        bid[lose] = np.clip(bid[win] + rng.normal(0, 0.05, k), 0.001, 1)
        rad[lose] = np.clip(rad[win] * np.exp(rng.normal(0, 0.15, k)), r_min, r_max)
        dec[lose] = dec[win] ^ (rng.random(k) < flip)
    # --- end prototype code path ---

    headline = summary(hist, cfg.summary_last)
    if log is not None:
        log.emit("outcome", mode="m0", dec_share_imp_last=headline, last=cfg.summary_last,
                 final_dec_pop=float(dec.mean()))
    if return_state:
        return hist, dict(loc=loc, bid=bid, rad=rad, dec=dec, wins=wins, profit=profit, cust=cust, enf=enf)
    return hist


def _strict_auction(b: np.ndarray, remaining: np.ndarray):
    """First-price auction for one batch with the impression cap enforced per
    impression, in impression order. b is (impressions x advertisers) with -1 for
    ineligible. A seller that would exceed its remaining capacity keeps its earliest
    wins; the rest go to the next-highest eligible bidder."""
    b = b.copy()
    n, A = b.shape
    w = np.full(n, -1); ok = np.zeros(n, bool)
    rem = remaining.astype(int).copy()
    todo = np.arange(n)
    while len(todo):
        sub = b[todo]
        ww = sub.argmax(1); has = sub.max(1) > 0
        todo, ww = todo[has], ww[has]
        if not len(todo):
            break
        # rank of each impression among this seller's wins, in impression order
        order = np.lexsort((todo, ww))
        ranks = np.empty(len(ww), int)
        sw = ww[order]
        starts = np.r_[0, np.flatnonzero(np.diff(sw)) + 1]
        counts = np.diff(np.r_[starts, len(sw)])
        ranks[order] = np.arange(len(sw)) - np.repeat(starts, counts)
        keep = ranks < rem[ww]
        w[todo[keep]] = ww[keep]; ok[todo[keep]] = True
        rem -= np.bincount(ww[keep], minlength=A)
        full = np.flatnonzero(rem <= 0)
        todo = todo[~keep]
        if len(full):
            b[:, full] = -1.0
        if not len(full) and len(todo):  # cannot happen: overflow implies a full seller
            break
    return w, ok


def summary(h, last: int = 30) -> float:
    x = np.array([r["dec_share_imp"] for r in h[-last:]])
    return float(np.nanmean(x))
