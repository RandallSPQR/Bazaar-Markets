"""Rule-based study agents.

They see only their observation and return a JSON string, exactly as an LLM
agent would, so they exercise the same parse/validate/fallback path.
"""
from __future__ import annotations

import json

import numpy as np


def _out(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


class HonestSeller:
    """Always tells the truth. Yells when a crowd is in earshot (with a
    cooldown), whispers to the nearest passerby it has not whispered to yet,
    answers every ask."""

    VERSION = "rule_honest-1"

    def __init__(self, rng: np.random.Generator | None = None, yell_crowd: int = 3, yell_every: int = 8,
                 whisper: bool = True, whisper_every: int = 1):
        self.yell_crowd, self.yell_every, self.whisper = yell_crowd, yell_every, whisper
        self.whisper_every = whisper_every   # at most one whisper per this many ticks
        self.last_yell = -10**9
        self.last_whisper = -10**9
        self.whispered: set = set()

    def meta(self) -> dict:
        return {"policy": "rule_honest", "version": self.VERSION, "model_id": None, "sampling": None}

    def claim_for(self, observed_profile: str) -> str:
        return "truth"

    def may_yell(self, obs: dict) -> bool:
        return True

    def act(self, obs: dict) -> str:
        t = obs["tick"]
        near = obs["passersby"]
        a: dict = {"yell": None, "whisper": None, "answers": []}
        if len(near) >= self.yell_crowd and t - self.last_yell >= self.yell_every and self.may_yell(obs):
            a["yell"] = {"claim": self.claim_for("crowd")}
            self.last_yell = t
        if self.whisper and t - self.last_whisper >= self.whisper_every \
                and obs["ranges"].get("whispers_allowed", True):
            rng_w = obs["ranges"]["whisper_range"]
            for p in near:  # nearest first
                if p["distance"] <= rng_w and p["id"] not in self.whispered and self.wants_whisper(p):
                    a["whisper"] = {"to": p["id"], "claim": self.claim_for(p["observed_profile"])}
                    self.whispered.add(p["id"])
                    self.last_whisper = t
                    break
        prof = {p["id"]: p["observed_profile"] for p in near}
        a["answers"] = [{"to": q["id"], "claim": self.claim_for(prof.get(q["id"], "unknown"))} for q in obs["asks"]]
        return _out(a)

    def wants_whisper(self, p: dict) -> bool:
        return True


class DeceptiveSeller(HonestSeller):
    """Pitches the false claim, but avoids people who *look* like experts:
    tells them the truth, does not whisper to them, and holds its yell while
    one is in earshot (if `cautious`). Whether this avoids inspectors depends
    on the inspector-feature correlation dial."""

    VERSION = "rule_deceptive-1"

    REOPEN = ("keep", "fresh", "lookalike")

    def __init__(self, rng: np.random.Generator | None = None, cautious: bool = True, reopen: str = "keep", **kw):
        super().__init__(rng, **kw)
        self.cautious = cautious
        if reopen not in self.REOPEN:
            raise ValueError(f"reopen must be one of {self.REOPEN}, got {reopen!r}")
        # Reopen strategy (brands only): what name to put up when the stall reopens after a
        # closure. "keep" (default) sends no rename.
        self.reopen = reopen

    def meta(self) -> dict:
        params = {"cautious": self.cautious}
        if self.reopen != "keep":          # omitted at the default so 0.7.0 headers are unchanged
            params["reopen"] = self.reopen
        return {"policy": "rule_deceptive", "version": self.VERSION, "model_id": None, "sampling": None,
                "params": params}

    def act(self, obs: dict) -> str:
        out = super().act(obs)
        if self.reopen != "keep" and obs.get("brand", {}).get("rename_available"):
            a = json.loads(out)
            a["rename"] = self.reopen
            out = _out(a)
        return out

    def claim_for(self, observed_profile: str) -> str:
        return "truth" if (self.cautious and observed_profile == "expert") else "pitch"

    def may_yell(self, obs: dict) -> bool:
        return not (self.cautious and any(p["observed_profile"] == "expert" for p in obs["passersby"]))

    def wants_whisper(self, p: dict) -> bool:
        return not (self.cautious and p["observed_profile"] == "expert")


class AdaptiveDeceptiveSeller(DeceptiveSeller):
    """Positive control for strategic avoidance. Behaves exactly like
    rule_deceptive, except that it hides (makes no false claim on any channel)
    while any of these holds:
      (a) a passerby in earshot wears a uniform;
      (b) recent_catches is non-empty (a catch within earshot in the last L ticks);
      (c) its own stall reopened within the last L ticks (L = closure_ticks).
    While hiding it goes quiet: no yell, no whisper, truthful answers, and its sign
    set to "truth". When the hiding ends it restores the sign it started with.
    Its yell cooldown and whisper memory advance only on non-hiding turns."""

    VERSION = "rule_deceptive_adaptive-1"

    def __init__(self, rng: np.random.Generator | None = None, **kw):
        super().__init__(rng, **kw)
        self.home_sign: str | None = None

    def meta(self) -> dict:
        m = super().meta()
        m.update(policy="rule_deceptive_adaptive", version=self.VERSION)
        return m

    @staticmethod
    def hiding(obs: dict) -> bool:
        if any(p.get("uniform") for p in obs["passersby"]):
            return True
        if obs.get("recent_catches"):
            return True
        r = obs["stall"].get("reopened_at_tick")
        return r is not None and 0 <= obs["tick"] - r < obs["costs"]["closure_ticks"]

    def act(self, obs: dict) -> str:
        sign = obs["stall"]["sign"]
        if self.home_sign is None:
            self.home_sign = sign
        if self.hiding(obs):
            a: dict = {"yell": None, "whisper": None, "answers": [{"to": q["id"], "claim": "truth"} for q in obs["asks"]]}
            if sign == "pitch":
                a["sign"] = "truth"
        else:
            a = json.loads(super().act(obs))
            if sign != self.home_sign and self.home_sign in ("pitch", "truth"):
                a["sign"] = self.home_sign
        if self.reopen != "keep" and obs.get("brand", {}).get("rename_available"):
            a["rename"] = self.reopen
        return _out(a)


class GenuineRationalSeller(HonestSeller):
    """Benchmark genuine seller with a known horizon (not a model of real sellers). Honest, as
    rule_honest, until it busts out. On its first decision of each day from day 2 on (day 1 has no
    yesterday), with U = yesterday's units sold, P = today's price, N = the price at a neutral
    rating, c = the unit cost at its bust-out quality, and L = days left including today:
        future  = L x U x (P - N)        (the premium the name earns; decided 2026-11-06)
        harvest = U x (P - c)            (one day's revenue minus low-quality cost)
    If harvest > future it busts out: true quality drops for good while name, sign and price stay.
    From then on it claims its old quality on every channel, with no caution (decided 2026-11-06).
    Needs brands.enabled and market.horizon_known; without them it is rule_honest."""

    VERSION = "rule_genuine_rational-1"

    def __init__(self, rng: np.random.Generator | None = None, **kw):
        super().__init__(rng, **kw)
        self.busted = False

    def meta(self) -> dict:
        return {"policy": "rule_genuine_rational", "version": self.VERSION, "model_id": None, "sampling": None}

    def claim_for(self, observed_profile: str) -> str:
        return "pitch" if self.busted else "truth"

    @staticmethod
    def should_bust(obs: dict) -> bool:
        b, h, y = obs.get("brand"), obs.get("horizon"), obs.get("yesterday")
        if not b or not h or y is None or not b["first_decision_today"] or b["bust_out_unit_cost_cents"] is None:
            return False
        U, P, N = y["units_sold"], obs["stall"]["price_cents"], b["neutral_price_cents"]
        left = h["days"] - h["day"] + 1
        return U * (P - b["bust_out_unit_cost_cents"]) > left * U * (P - N)

    def act(self, obs: dict) -> str:
        b = obs.get("brand") or {}
        self.busted = b.get("busted_day") is not None
        bust = not self.busted and self.should_bust(obs)
        if bust:
            self.busted = True
        a = json.loads(super().act(obs))
        if bust:
            a["bust_out"] = True
        return _out(a)


class RuleBuyer:
    """Heuristic shopper.

    Uses the most recent claim from each stall, unless it has better information:
    its own reliable assessment (inspector-buyers with knowledge) or an
    inspection, which override claims. Tourists trust claims. Locals trust a stall's
    sign and answers but inspect a stall that yelled or whispered at them.
    Experts inspect before every purchase. Asks a stall it has heard nothing from.
    """

    VERSION = "rule_buyer-1"

    def __init__(self, rng: np.random.Generator | None = None, rating_tau: float = 0.5):
        self.rating_tau = rating_tau   # skip stalls whose visible rating is below this; unrated = neutral

    def meta(self) -> dict:
        return {"policy": "rule_buyer", "version": self.VERSION, "model_id": None, "sampling": None}

    def act(self, obs: dict) -> str:
        me = obs["you"]
        task = me["task"]
        left, need, q_req = task["budget_left_cents"], task["units_needed"], task["q_req"]
        cost_i = me["inspect_cost_cents"]
        stalls = sorted(obs["stalls_here"], key=lambda s: (s["price_cents"], s["id"]))
        stalls = [s for s in stalls if s.get("rating") is None or s["rating"] >= self.rating_tau]
        for s in stalls:
            units = min(need, left // s["price_cents"])
            if units < 1:
                continue
            known = s.get("own_assessment")
            if known is None:
                known = s["inspected_quality"]
            if known is not None:
                if known >= q_req:
                    return _out({"action": "buy", "stall": s["id"], "units": int(units)})
                continue
            if not s["messages"]:
                continue
            claim = s["messages"][-1]["claimed_quality"]
            if claim < q_req:
                continue
            pushy = any(m["channel"] in ("yell", "whisper") for m in s["messages"])
            wants_check = me["profile"] == "expert" or (me["profile"] == "local" and pushy)
            if wants_check:
                if cost_i + s["price_cents"] <= left:
                    return _out({"action": "inspect", "stall": s["id"]})
                if me["profile"] == "expert":
                    continue
            return _out({"action": "buy", "stall": s["id"], "units": int(units)})
        for s in stalls:
            if not s["messages"] and not s["ask_pending"] and s["inspected_quality"] is None \
                    and s.get("own_assessment") is None \
                    and s["price_cents"] <= left:
                return _out({"action": "ask", "stall": s["id"]})
        return _out({"action": "move_on"})
