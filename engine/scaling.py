"""Grid refinement (market.scale = k).

Config values are in real units: one real unit of length is one cell at k = 1, one real
unit of time is one tick at k = 1. At scale k the engine refines space and time together:
a cell is 1/k real units across and a tick 1/k real units long, and people still move one
cell per tick, so real speeds do not change.

How it is done:
  * The world (layout, stalls, posts, people, routes, arrivals) is built at k = 1 from the
    unscaled config, then refined: every coordinate is multiplied by k, every route step is
    split into k one-cell steps (the last cell is held k ticks, as it is held one tick at
    k = 1), and every arrival tick is multiplied by k. So route_k[k t] = k route_1[t]
    exactly, the buyer population is the same in real units, and every hard-coded layout
    offset (aisle pitch, stall rows, corridor columns, post offsets) scales with it.
  * The engine then runs on a scaled copy of the config (`scaled_config`), in which every
    field classified "distance" or "time" below is multiplied by k.
  * Two per-tick rates of the engine and the rule sellers scale too (decided 2026-11-05):
    a buyer action (ask, inspect, buy) holds the buyer k ticks, and rule sellers' cooldowns
    (yell_every, whisper_every) are multiplied by k (AGENT_PARAMS).

Every config field must appear in FIELDS, and every keyword of every registered agent
policy in AGENT_PARAMS; tests/test_scale.py fails otherwise, so a new distance or time
parameter cannot be added without a scaling rule.
"""
from __future__ import annotations

import copy
import dataclasses

DISTANCE, TIME, NONE = "distance", "time", "none"

# rule, and for "none" a reason
FIELDS: dict[str, tuple[str, str]] = {
    "mode": (NONE, "label"),
    "seed": (NONE, "label"),
    # market
    "market.categories": (NONE, "labels"),
    "market.slots_per_side": (NONE, "count"),
    "market.slot_spacing": (DISTANCE, "applied by coordinate refinement of the k = 1 layout"),
    "market.clustering": (NONE, "probability"),
    "market.ticks": (TIME, ""),
    "market.sight_range": (DISTANCE, ""),
    "market.earshot": (DISTANCE, ""),
    "market.whisper_range": (DISTANCE, ""),
    "market.interact_range": (DISTANCE, ""),
    "market.max_actions_per_stop": (NONE, "a count of actions; each action holds the buyer k ticks"),
    "market.scale": (NONE, "the scale itself"),
    "market.days": (NONE, "count of whole runs"),
    "market.whispers_allowed": (NONE, "switch"),
    "market.horizon_known": (NONE, "switch"),
    # stalls
    "stalls.type_shares": (NONE, "shares"),
    "stalls.q_high": (NONE, "quality"),
    "stalls.q_low": (NONE, "quality"),
    "stalls.deceptive_sign": (NONE, "label"),
    # pricing
    "pricing.base_price_cents": (NONE, "money"),
    "pricing.seconds_price_factor": (NONE, "ratio"),
    "pricing.deceptive_price_factor": (NONE, "ratio"),
    "pricing.unit_cost": (NONE, "money ratio"),
    "pricing.yell_cost_frac": (NONE, "money per yell; yells per real time are unchanged"),
    "pricing.whisper_cost_frac": (NONE, "money per whisper"),
    "pricing.penalty_mult": (NONE, "money ratio"),
    "pricing.close_ticks": (TIME, "also the catch-notice window L"),
    "pricing.switch_cost_to_genuine": (NONE, "money ratio, once per switch"),
    "pricing.switch_cost_to_deceptive": (NONE, "money ratio, once per switch"),
    # buyers
    "buyers.count": (NONE, "count"),
    "buyers.profile_shares": (NONE, "shares"),
    "buyers.units": (NONE, "count"),
    "buyers.q_req": (NONE, "quality"),
    "buyers.budget_level": (NONE, "label"),
    "buyers.budget_factors": (NONE, "ratio"),
    "buyers.inspect_cost_frac": (NONE, "money ratio"),
    "buyers.aisles_per_route": (NONE, "count; routes are refined after they are drawn"),
    "buyers.profile_noise": (NONE, "probability per (stall, person) pair"),
    "buyers.inspector_fraction": (NONE, "share"),
    "buyers.inspector_knowledge": (NONE, "switch"),
    "buyers.inspector_enforcement": (NONE, "switch"),
    # inspectors
    "inspectors.count": (NONE, "count"),
    "inspectors.placement": (NONE, "label; post positions are refined with the layout"),
    "inspectors.disguised_ask_prob": (NONE, "probability per (inspector, stall, epoch) encounter"),
    "inspectors.feature_correlation": (NONE, "probability"),
    "inspectors.uniformed": (NONE, "switch"),
    "inspectors.recognition_range": (DISTANCE, "null (= earshot) stays null"),
    "inspectors.disguised_shift": (NONE, "label; full-shift routes are refined"),
    # detection
    "detection.form": (NONE, "label"),
    "detection.proximity": (NONE, "label; proximity is d / range, a ratio of two distances"),
    "detection.channel_weight": (NONE, "probability weights"),
    "detection.f_scale": (NONE, "quality"),
    "detection.hazard_k": (NONE, "rate per unit falsity"),
    "detection.hazard_lam": (DISTANCE, "decay length of the hazard form"),
    # valuation
    "valuation.form": (NONE, "label"),
    "valuation.value_mult": (NONE, "ratio"),
    "valuation.salvage": (NONE, "ratio"),
    # agents
    "agents.seller": (NONE, "policy names"),
    "agents.buyer": (NONE, "policy name"),
    "agents.params": (NONE, "per-policy keywords; their rules are in AGENT_PARAMS"),
    # evolution
    "evolution.revise_prob": (NONE, "probability per stall per day boundary"),
    "evolution.mutation_prob": (NONE, "probability per stall per day boundary"),
    # ratings
    "ratings.mode": (NONE, "label"),
    "ratings.memory": (NONE, "weight per day; ratings update once per day"),
    "ratings.tau": (NONE, "rating threshold"),
    "ratings.visible_to": (NONE, "profiles"),
    "ratings.rugpull_threshold": (NONE, "rating threshold"),
    # brands
    "brands.enabled": (NONE, "switch"),
    "brands.premium": (NONE, "price multiplier per unit of rating"),
}

# Keyword arguments of every registered policy class (rng excluded).
AGENT_PARAMS: dict[str, dict[str, tuple[str, str]]] = {
    "HonestSeller": {"yell_crowd": (NONE, "count"), "yell_every": (TIME, "yell cooldown"),
                     "whisper": (NONE, "switch"), "whisper_every": (TIME, "whisper cooldown")},
    "DeceptiveSeller": {"cautious": (NONE, "switch"), "reopen": (NONE, "label")},
    "GenuineRationalSeller": {},
    "AdaptiveDeceptiveSeller": {},
    "RuleBuyer": {"rating_tau": (NONE, "rating threshold (set from ratings.tau)")},
    "RandomReferenceBuyer": {"p_buy": (NONE, "probability per decision; decisions per stop are unchanged")},
    "InformedReferenceBuyer": {"valuation": (NONE, "engine-supplied"), "base_price_cents": (NONE, "engine-supplied")},
    "LLMAgent": {"role": (NONE, "label"), "model_id": (NONE, "label"), "sampling": (NONE, "sampling settings"),
                 "provider": (NONE, "label"), "max_retries": (NONE, "count per decision"),
                 "max_calls": (NONE, "spend cap; note that at k > 1 sellers get k times as many decision ticks")},
}


def _scale_value(v, k: int):
    if v is None:
        return None
    if isinstance(v, bool):
        raise TypeError("a switch cannot be scaled")
    return v * k


def scaled_config(cfg):
    """A copy of a bazaar config with every distance and time field multiplied by k.
    k = 1 returns an equal copy."""
    k = int(cfg.market.scale)
    if k < 1:
        raise ValueError(f"market.scale must be an integer >= 1, got {cfg.market.scale!r}")
    out = copy.deepcopy(cfg)
    if k == 1:
        return out
    for path, (rule, _) in FIELDS.items():
        if rule == NONE or path == "market.slot_spacing":
            continue
        sec, name = path.split(".")
        node = getattr(out, sec)
        setattr(node, name, _scale_value(getattr(node, name), k))
    return out


def all_config_fields(cfg) -> list[str]:
    """Dotted paths of every field of a bazaar config (one level of sections)."""
    out = []
    for f in dataclasses.fields(cfg):
        v = getattr(cfg, f.name)
        if dataclasses.is_dataclass(v):
            out += [f"{f.name}.{g.name}" for g in dataclasses.fields(v)]
        else:
            out.append(f.name)
    return out


def scale_agent_params(cls, params: dict, k: int) -> dict:
    """Multiply an agent's time keywords by k, taking the class default where the config
    gives none. Rules are looked up along the class's bases, since subclasses pass
    keywords up to them."""
    if k == 1:
        return params
    import inspect
    out = dict(params)
    for c in cls.__mro__:
        if "__init__" not in c.__dict__:
            continue
        sig = inspect.signature(c.__init__)
        for name, (rule, _) in AGENT_PARAMS.get(c.__name__, {}).items():
            if rule == TIME and name in sig.parameters:
                out[name] = params.get(name, sig.parameters[name].default) * k
    return out
