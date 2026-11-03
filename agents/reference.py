"""Reference buyers: comparison points, not bounds.

RandomReferenceBuyer ("random reference"): ignores all messages; at each stop
buys from a random affordable stall with probability p_buy, as many units as it
can afford. It is not a lower bound: a study buyer that follows false claims can
do worse than random.

InformedReferenceBuyer ("informed reference"): receives the privileged `oracle`
block (true quality here and on the rest of its route) and follows a heuristic:
buy where per-unit surplus V(Q) - price is positive and no better deal lies ahead
on its route. It is not an upper bound either: it can wait for a better offer that
is gone when it arrives (closed stall, spent budget), and it does not solve the
joint quantity/budget problem. It never asks or inspects.

Raw outcomes are primary. Scores relative to these references (engine.metrics)
are comparisons and can fall outside [0, 1].
"""
from __future__ import annotations

import json

import numpy as np

from engine.valuation import unit_value


def _out(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


class RandomReferenceBuyer:
    VERSION = "random_reference-1"

    def __init__(self, rng: np.random.Generator, p_buy: float = 0.3):
        self.rng, self.p_buy = rng, p_buy

    def meta(self) -> dict:
        return {"policy": "random_reference", "version": self.VERSION, "model_id": None, "sampling": None,
                "params": {"p_buy": self.p_buy}, "reference": "random"}

    def act(self, obs: dict) -> str:
        task = obs["you"]["task"]
        left, need = task["budget_left_cents"], task["units_needed"]
        ok = [s for s in obs["stalls_here"] if s["price_cents"] <= left]
        u = self.rng.random()
        if not ok or u >= self.p_buy:
            return _out({"action": "move_on"})
        s = ok[int(self.rng.integers(len(ok)))]
        return _out({"action": "buy", "stall": s["id"], "units": int(min(need, left // s["price_cents"]))})


class InformedReferenceBuyer:
    VERSION = "informed_reference-1"

    def __init__(self, rng: np.random.Generator | None = None, valuation=None, base_price_cents: dict | None = None):
        self.valuation, self.base = valuation, base_price_cents

    def meta(self) -> dict:
        return {"policy": "informed_reference", "version": self.VERSION, "model_id": None, "sampling": None,
                "privileged": True, "reference": "informed"}

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


# Old names, kept so logs written before the rename still replay.
RandomBuyer = RandomReferenceBuyer
PerfectInfoBuyer = InformedReferenceBuyer
