"""Reference buyers for normalising outcomes.

RandomBuyer (floor): ignores all messages; at each stop buys from a random
affordable stall with probability p_buy, as many units as it can afford.

PerfectInfoBuyer (ceiling): receives the privileged `oracle` block (true
quality here and on the rest of its route). It buys where per-unit surplus
V(Q) - price is positive and no better deal lies ahead on its route. It never
asks or inspects. This is a myopic, route-aware oracle, not a global
optimum over all routes.
"""
from __future__ import annotations

import json

import numpy as np

from engine.valuation import unit_value


def _out(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


class RandomBuyer:
    VERSION = "random_buyer-1"

    def __init__(self, rng: np.random.Generator, p_buy: float = 0.3):
        self.rng, self.p_buy = rng, p_buy

    def meta(self) -> dict:
        return {"policy": "random_buyer", "version": self.VERSION, "model_id": None, "sampling": None,
                "params": {"p_buy": self.p_buy}, "reference": "floor"}

    def act(self, obs: dict) -> str:
        task = obs["you"]["task"]
        left, need = task["budget_left_cents"], task["units_needed"]
        ok = [s for s in obs["stalls_here"] if s["price_cents"] <= left]
        u = self.rng.random()
        if not ok or u >= self.p_buy:
            return _out({"action": "move_on"})
        s = ok[int(self.rng.integers(len(ok)))]
        return _out({"action": "buy", "stall": s["id"], "units": int(min(need, left // s["price_cents"]))})


class PerfectInfoBuyer:
    VERSION = "perfect_buyer-1"

    def __init__(self, rng: np.random.Generator | None = None, valuation=None, base_price_cents: dict | None = None):
        self.valuation, self.base = valuation, base_price_cents

    def meta(self) -> dict:
        return {"policy": "perfect_buyer", "version": self.VERSION, "model_id": None, "sampling": None,
                "privileged": True, "reference": "ceiling"}

    def surplus(self, q: float, price: int, q_req: float, cat: str) -> float:
        return unit_value(self.valuation, q, q_req, self.base[cat]) - price

    def act(self, obs: dict) -> str:
        task = obs["you"]["task"]
        left, need, q_req, cat = task["budget_left_cents"], task["units_needed"], task["q_req"], task["category"]
        tq = obs["oracle"]["true_quality"]
        here = [(self.surplus(tq[s["id"]], s["price_cents"], q_req, cat), s["id"], s["price_cents"])
                for s in obs["stalls_here"] if s["price_cents"] <= left]
        if not here:
            return _out({"action": "move_on"})
        best_s, best_id, price = max(here, key=lambda x: (x[0], -x[2], x[1]))
        ahead = [self.surplus(r["true_quality"], r["price_cents"], q_req, cat)
                 for r in obs["oracle"]["route_ahead"] if r["price_cents"] <= left]
        if best_s <= 0 or (ahead and max(ahead) > best_s):
            return _out({"action": "move_on"})
        return _out({"action": "buy", "stall": best_id, "units": int(min(need, left // price))})
