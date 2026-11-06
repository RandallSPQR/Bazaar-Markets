"""Policy registry: maps policy names in the config to agent classes.

Agent randomness (e.g. the random reference buyer) uses its own stream,
seeded from (run seed, role, agent index), and never touches engine streams.
"""
from __future__ import annotations

import numpy as np

from engine.scaling import scale_agent_params

from .llm_stub import LLMAgent
from .reference import InformedReferenceBuyer, RandomReferenceBuyer
from .rule_based import AdaptiveDeceptiveSeller, DeceptiveSeller, GenuineRationalSeller, HonestSeller, RuleBuyer

POLICIES = {
    "rule_honest": HonestSeller,
    "rule_deceptive": DeceptiveSeller,
    "rule_deceptive_adaptive": AdaptiveDeceptiveSeller,
    "rule_genuine_rational": GenuineRationalSeller,
    "rule_buyer": RuleBuyer,
    "random_reference": RandomReferenceBuyer,
    "informed_reference": InformedReferenceBuyer,
    # deprecated aliases (pre-rename logs and configs)
    "random_buyer": RandomReferenceBuyer,
    "perfect_buyer": InformedReferenceBuyer,
    "llm": LLMAgent,
}

ROLE_CODE = {"seller": 0, "buyer": 1}


def make_factory(cfg, root: tuple | None = None):
    root = (cfg.seed,) if root is None else tuple(root)

    def factory(role: str, policy: str, key: str, idx: int):
        if policy not in POLICIES:
            raise KeyError(f"unknown policy {policy!r}; known: {sorted(POLICIES)}")
        rng = np.random.default_rng([*root, 7, ROLE_CODE[role], idx])
        params = scale_agent_params(POLICIES[policy], dict(cfg.agents.params.get(policy, {})),
                                    int(cfg.market.scale))
        if policy in ("informed_reference", "perfect_buyer"):
            params.update(valuation=cfg.valuation, base_price_cents=cfg.pricing.base_price_cents)
        if policy == "rule_buyer":
            params.setdefault("rating_tau", cfg.ratings.tau)
        if policy == "llm":
            params.setdefault("role", role)
        return POLICIES[policy](rng, **params)
    return factory


class ReplayedAgentError(RuntimeError):
    """Re-raises a crash recorded in the log, with the logged message."""

    def __init__(self, msg: str):
        super().__init__(msg)
        self.logged_message = msg


class ReplayAgent:
    """Feeds back logged raw outputs in order. Used by the replay CLI."""

    def __init__(self, raws: list, meta: dict, attempts: list | None = None, errors: list | None = None):
        self.raws = list(raws)
        self.errors = errors or [None] * len(self.raws)
        self.attempts = attempts       # per-raw attempt lists, for agents that logged them
        self._meta = meta
        self.i = 0
        if attempts is not None:
            self.last_attempts: list = []

    def meta(self) -> dict:
        return self._meta

    def act(self, obs: dict):
        if self.i >= len(self.raws):
            raise RuntimeError("replay log has no more outputs for this agent")
        raw, err = self.raws[self.i], self.errors[self.i]
        if self.attempts is not None:
            self.last_attempts = self.attempts[self.i]
        self.i += 1
        if err is not None:
            raise ReplayedAgentError(err)
        return raw
