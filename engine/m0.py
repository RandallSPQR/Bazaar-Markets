"""M0 compatibility mode: the prototype's unit-square advertising model.

This is a port of the prototype sim.py (tests/reference/sim_prototype.py,
sha256 2b40ab7e...). In enforcer_mode="fixed" it consumes the RNG in exactly
the same order as the prototype and reproduces its per-generation history
bit for bit; tests/test_m0.py checks that.

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
  * selection: the bottom `keep` share (idle firms rank lowest) copy the top
    `keep` share with mutation; type flips with probability `flip`.

enforcer_mode="redraw" is the mechanism test: same geometry and rate, but
each impression's enforcer status is drawn fresh at rate f_enf, so no fixed
pockets exist. The draws come from a separate stream so that paired runs share
every other random number until their populations diverge. tighten.py, which
held the original redraw code, was not available; treat this as a reconstruction.
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
    if cfg.enforcer_mode not in ("fixed", "redraw"):
        raise ValueError(f"enforcer_mode must be 'fixed' or 'redraw', got {cfg.enforcer_mode!r}")
    n_cust, n_adv, f_enf = cfg.n_cust, cfg.n_adv, cfg.f_enf
    r_min, r_max, d_sale = cfg.r_min, cfg.r_max, cfg.d_sale
    m, delta, P, keep, flip = cfg.m, cfg.delta, cfg.P, cfg.keep, cfg.flip
    redraw = cfg.enforcer_mode == "redraw"

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
        e = (rng_e.random(T) < f_enf) if redraw else enf[idx]
        cap = int(cfg.cap_mult * T / n_adv); used = np.zeros(n_adv, int)
        W = []; D = []; E = []; OK = []
        for ch in np.array_split(np.arange(T), 40):
            cc = c[ch]; ee = e[ch]
            d = np.sqrt(((cc[:, None, :] - loc[None, :, :]) ** 2).sum(-1))
            elig = (d <= rad[None, :]) & (used < cap)[None, :]
            b = np.where(elig, bid[None, :], -1.0)
            w = b.argmax(1); ok = b.max(1) > 0
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
        rec = dict(dec_share_imp=dw.mean() if len(dw) else np.nan,
                   dec_pop=dec.mean(),
                   fill=ok.mean())
        hist.append(rec)
        if log is not None:
            n_sales = int(sale.sum())
            log.emit("generation", g=g, **rec,
                     impressions=int(len(w)), sales=n_sales,
                     dec_share_sales=float((dw & sale).sum() / n_sales) if n_sales else None,
                     catches=int((dw & e_w).sum()),
                     ad_spend=float(bid[w].sum()), revenue=float(revenue.sum()),
                     penalties=float(penalty.sum()), profit=float(profit.sum()))
        # selection
        fit = np.where(wins > 0, profit, -1e-9)  # idle firms exit before profitable ones
        order = np.argsort(fit); k = int(keep * n_adv)
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


def summary(h, last: int = 30) -> float:
    x = np.array([r["dec_share_imp"] for r in h[-last:]])
    return float(np.nanmean(x))
