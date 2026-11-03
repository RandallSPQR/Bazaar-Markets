"""Policy registry: maps policy names in the config to agent classes.

Agent randomness (e.g. the random reference buyer) uses its own stream,
seeded from (run seed, role, agent index), and never touches engine streams.
"""
from __future__ import annotations

import numpy as np

from .llm_stub import LLMAgent
from .reference import PerfectInfoBuyer, RandomBuyer
from .rule_based import DeceptiveSeller, HonestSeller, RuleBuyer

POLICIES = {
    "rule_honest": HonestSeller,
    "rule_deceptive": DeceptiveSeller,
    "rule_buyer": RuleBuyer,
    "random_buyer": RandomBuyer,
    "perfect_buyer": PerfectInfoBuyer,
    "llm": LLMAgent,
}

ROLE_CODE = {"seller": 0, "buyer": 1}


def make_factory(cfg):
    def factory(role: str, policy: str, key: str, idx: int):
        if policy not in POLICIES:
            raise KeyError(f"unknown policy {policy!r}; known: {sorted(POLICIES)}")
        rng = np.random.default_rng([cfg.seed, 7, ROLE_CODE[role], idx])
        params = dict(cfg.agents.params.get(policy, {}))
        if policy == "perfect_buyer":
            params.update(valuation=cfg.valuation, base_price_cents=cfg.pricing.base_price_cents)
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
