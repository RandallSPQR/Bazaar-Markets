"""Buyer value function V(Q), per unit, in cents.

PLACEHOLDER default ("step_salvage", chosen 2026-11-03):
    V = V_req                          if Q >= Q_req
    V = salvage * V_req * Q / Q_req    otherwise
with V_req = value_mult * category base price.

Alternatives: "linear" V = V_req * Q / Q_req; "concave" V = V_req * sqrt(Q / Q_req).
"""
from __future__ import annotations

import math

from .config import ValuationCfg


def unit_value(cfg: ValuationCfg, q: float, q_req: float, base_price_cents: int) -> float:
    v_req = cfg.value_mult * base_price_cents
    if cfg.form == "step_salvage":
        return v_req if q >= q_req else cfg.salvage * v_req * q / q_req
    if cfg.form == "linear":
        return v_req * q / q_req
    if cfg.form == "concave":
        return v_req * math.sqrt(q / q_req)
    raise ValueError(f"unknown valuation form {cfg.form!r}")
