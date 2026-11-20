"""Rule-based study agents.

They see only their observation and return a JSON string, exactly as an LLM
agent would, so they exercise the same parse/validate/fallback path.
"""
from __future__ import annotations

import json
import math

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

    REOPEN = ("keep", "fresh", "counterfeit")
    REOPEN_ALIASES = {"lookalike": "counterfeit"}   # 0.8.0 name

    def __init__(self, rng: np.random.Generator | None = None, cautious: bool = True, reopen: str = "keep", **kw):
        super().__init__(rng, **kw)
        self.cautious = cautious
        reopen = self.REOPEN_ALIASES.get(reopen, reopen)
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


class GenuineRationalSellerV2(GenuineRationalSeller):
    """Penalty-aware benchmark (engine 0.9.0; not a model of real sellers). As
    rule_genuine_rational, but on its first decision of each day from day 2 on it compares, over
    the L days left including today:
        honest value  = L x yesterday's profit
        bust-out value = sum over k = 0..L-1 of
            U x (P_k - c) - A - E x F - min(1, E x close_ticks / ticks) x U x (P_k - c)
    with U = yesterday's units, c = unit cost at its bust-out quality, A = yesterday's ad spend,
    F = the penalty per catch, E = expected catches per deceptive stall-day (yesterday's market-wide
    rate, a privileged input labelled as such in its observation), and P_k the price at the
    rating r_k it would have after k days of bad reviews: r_0 = today's start-of-day rating, then
    the engine's update with every rated unit dishonest (share 0): r_{k+1} = 0 if r_k is unrated,
    else memory x r_k; unchanged when U = 0. P_k = N x (1 + premium x (r_k - 0.5)), unrated = 0.5,
    rounded to a cent as the engine does. The last term is the margin lost while closed after the
    expected catches. Busts out if bust-out value > honest value, and claims its old quality on
    every channel afterwards (as v1). Decided 2026-11-06."""

    VERSION = "rule_genuine_rational_v2-1"

    def meta(self) -> dict:
        return {"policy": "rule_genuine_rational_v2", "version": self.VERSION, "model_id": None, "sampling": None,
                "privileged": True}

    @staticmethod
    def values(obs: dict) -> tuple[float, float] | None:
        """(honest value, bust-out value) in cents, or None when the rule does not apply today."""
        b, h, y, pv = obs.get("brand"), obs.get("horizon"), obs.get("yesterday"), obs.get("privileged")
        if not b or not h or y is None or not pv or not b["first_decision_today"] \
                or b["bust_out_unit_cost_cents"] is None or pv.get("deceptive_catch_rate_yesterday") is None:
            return None
        L = h["days"] - h["day"] + 1
        U, c, A = y["units_sold"], b["bust_out_unit_cost_cents"], y["ad_spend_cents"]
        N, F = b["neutral_price_cents"], obs["costs"]["penalty_cents_if_caught"]
        E = float(pv["deceptive_catch_rate_yesterday"])
        closed = min(1.0, E * pv["close_ticks"] / pv["ticks_per_day"])
        honest = L * y["profit_cents"]
        r, bust = b["rating"], 0.0
        for _ in range(L):
            P = int(round(N * (1 + pv["premium"] * ((0.5 if r is None else r) - 0.5))))
            margin = U * (P - c)
            bust += margin - A - E * F - closed * margin
            if U > 0:
                r = 0.0 if r is None else pv["rating_memory"] * r
        return float(honest), float(bust)

    @classmethod
    def should_bust(cls, obs: dict) -> bool:
        v = cls.values(obs)
        return v is not None and v[1] > v[0]


class GenuineBustAtSeller(GenuineRationalSeller):
    """Benchmark tool (engine 0.11.0), not a model of sellers: honest, as rule_honest, until a
    scheduled day; it busts out on its first decision of that day (or of the first later day with
    a decision) and from then on behaves as a busted rule_genuine_rational (claims its old quality
    on every channel). `schedule` maps stall ids to bust-out days; a stall not listed never busts
    out. Needs brands.enabled and market.horizon_known; without them it is rule_honest.

    Exit (engine 0.15.0): `exit_at` maps stall ids to a day; on its first decision of that day (or of
    the first later day with a decision) the stall asks to leave the market at the end of the day
    (seller action "exit"). Empty by default, which is the 0.14.0 behaviour."""

    VERSION = "rule_genuine_bust_at-1"

    def __init__(self, rng: np.random.Generator | None = None, schedule: dict | None = None,
                 exit_at: dict | None = None, **kw):
        super().__init__(rng, **kw)
        self.schedule = {str(k): int(v) for k, v in (schedule or {}).items()}
        self.exit_at = {str(k): int(v) for k, v in (exit_at or {}).items()}
        self.exit_sent = False          # agents are fresh each day, so this is per day

    def act(self, obs: dict) -> str:
        a = json.loads(super().act(obs))
        day, h = self.exit_at.get(obs["stall"]["id"]), obs.get("horizon")
        if day is not None and h and h["day"] >= day and not self.exit_sent:
            self.exit_sent = True
            a["exit"] = True
        return _out(a)

    def meta(self) -> dict:
        return {"policy": "rule_genuine_bust_at", "version": self.VERSION, "model_id": None, "sampling": None}

    def should_bust(self, obs: dict) -> bool:
        b, h = obs.get("brand"), obs.get("horizon")
        if not b or not h or not b["first_decision_today"] or b["bust_out_unit_cost_cents"] is None:
            return False
        day = self.schedule.get(obs["stall"]["id"])
        return day is not None and h["day"] >= day


class RuleBuyer:
    """Heuristic shopper.

    Uses the most recent claim from each stall, unless it has better information:
    its own reliable assessment (inspector-buyers with knowledge) or an
    inspection, which override claims. Tourists trust claims. Locals trust a stall's
    sign and answers but inspect a stall that yelled or whispered at them.
    Experts inspect before every purchase. Asks a stall it has heard nothing from.

    Verification dial (engine 0.13.0): a local inspects an advertising stall with probability
    local_inspect_prob, an expert inspects before buying with probability expert_inspect_prob
    (defaults 1.0 = the rule above). The choice is drawn once per stall, from the buyer's own agent
    stream, the first time it matters, and only when the probability is strictly between 0 and 1. A
    buyer who decides not to inspect a stall trusts its latest claim, as a tourist does.
    """

    VERSION = "rule_buyer-1"

    def __init__(self, rng: np.random.Generator | None = None, rating_tau: float = 0.5,
                 local_inspect_prob: float = 1.0, expert_inspect_prob: float = 1.0):
        self.rating_tau = rating_tau   # skip stalls whose visible rating is below this; unrated = neutral
        for name, v in (("local_inspect_prob", local_inspect_prob), ("expert_inspect_prob", expert_inspect_prob)):
            if not 0.0 <= float(v) <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {v!r}")
        self.inspect_prob = {"local": float(local_inspect_prob), "expert": float(expert_inspect_prob)}
        self.rng = rng
        self._checks: dict = {}

    @staticmethod
    def check_rule(me: dict):
        """Which inspection rule the buyer follows: "expert" (any stall before buying), "local" (a stall that
        yelled or whispered at it) or None (tourists: never). A tourist given you.inspect_prob
        (buyers.profile_overrides, engine 0.21.0) follows the local rule."""
        if me["profile"] == "expert":
            return "expert"
        if me["profile"] == "local" or me.get("inspect_prob") is not None:
            return "local"
        return None

    def checks(self, profile: str, sid: str, p: float | None = None) -> bool:
        """Whether this buyer verifies stall sid when its rule calls for it (locals: an advertising
        stall; experts: any stall before buying). p: the buyer's own probability (you.inspect_prob, engine
        0.21.0), replacing the profile's default when given."""
        if p is None:
            p = self.inspect_prob.get(profile, 1.0)
        if p >= 1.0:
            return True
        if p <= 0.0:
            return False
        if sid not in self._checks:
            self._checks[sid] = bool(self.rng.random() < p)
        return self._checks[sid]

    def meta(self) -> dict:
        return {"policy": "rule_buyer", "version": self.VERSION, "model_id": None, "sampling": None}

    def act(self, obs: dict) -> str:
        if "search" in obs:
            return self.act_search(obs)
        me = obs["you"]
        task = me["task"]
        left, need, q_req = task["budget_left_cents"], task["units_needed"], task["q_req"]
        cost_i = me["inspect_cost_cents"]
        stalls = sorted(obs["stalls_here"], key=lambda s: (s["price_cents"], _tie(s)))
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
            rule = self.check_rule(me)
            wants_check = rule == "expert" or (rule == "local" and pushy)
            if wants_check and self.checks(rule, s["id"], me.get("inspect_prob")):
                if cost_i + s["price_cents"] <= left:
                    return _out({"action": "inspect", "stall": s["id"]})
                if rule == "expert":
                    continue
            return _out({"action": "buy", "stall": s["id"], "units": int(units)})
        for s in stalls:
            if not s["messages"] and not s["ask_pending"] and s["inspected_quality"] is None \
                    and s.get("own_assessment") is None \
                    and s["price_cents"] <= left:
                return _out({"action": "ask", "stall": s["id"]})
        return _out({"action": "move_on"})

    # ---------------------------------------------------------------- search (engine 0.10.0)

    def _visible_ok(self, s: dict) -> bool:
        return s.get("rating") is None or s["rating"] >= self.rating_tau

    def _candidate(self, s: dict, me: dict, left: int, q_req: float) -> bool:
        """Would the 0.9.0 rule buy from this stall now? (Seen stalls are judged on what the buyer
        learned there.)"""
        if left // s["price_cents"] < 1 or not self._visible_ok(s):
            return False
        known = s.get("own_assessment")
        if known is None:
            known = s["inspected_quality"]
        if known is not None:
            return known >= q_req
        if not s["messages"] or s["messages"][-1]["claimed_quality"] < q_req:
            return False
        rule, ip = self.check_rule(me), me.get("inspect_prob")
        if rule == "expert" and self.checks("expert", s["id"], ip):
            return False                                   # experts buy only what they inspected
        pushy = any(m["channel"] in ("yell", "whisper") for m in s["messages"])
        if rule == "local" and pushy and self.checks("local", s["id"], ip):
            # a local inspects a pushy stall first; it buys uninspected only if it cannot afford to
            return me["inspect_cost_cents"] + s["price_cents"] > left
        return True

    def act_search(self, obs: dict) -> str:
        """Searching buyer (buyers.search_depth > 1; decided 2026-11-06). At each stop it learns as
        the 0.9.0 rule would before buying (inspects where that rule inspects, asks stalls it has
        heard nothing from), but buys only in phase "choose": then, among stalls here and stalls
        seen earlier that it believes meet Q_req, pass the rating threshold and fit its budget,
        it picks the highest visible rating (unrated = 0.5), then the lowest price (tourists, who
        see no ratings: lowest price), ties by stall id (or, with buyers.tie_break "random", by the row's
        tie_rank, engine 0.20.0); buys if that stall is here, else walks
        back to it ("choose"). No candidate: move on."""
        me = obs["you"]
        task = me["task"]
        left, need, q_req = task["budget_left_cents"], task["units_needed"], task["q_req"]
        cost_i = me["inspect_cost_cents"]
        here = sorted(obs["stalls_here"], key=lambda s: (s["price_cents"], s["id"]))
        for s in here:                                     # learn first, as the 0.9.0 rule does
            if not self._visible_ok(s) or left // s["price_cents"] < 1:
                continue
            if s.get("own_assessment") is not None or s["inspected_quality"] is not None or not s["messages"]:
                continue
            if s["messages"][-1]["claimed_quality"] < q_req:
                continue
            pushy = any(m["channel"] in ("yell", "whisper") for m in s["messages"])
            rule = self.check_rule(me)
            if (rule == "expert" or (rule == "local" and pushy)) and cost_i + s["price_cents"] <= left \
                    and self.checks(rule, s["id"], me.get("inspect_prob")):
                return _out({"action": "inspect", "stall": s["id"]})
        for s in here:
            if not s["messages"] and not s["ask_pending"] and s["inspected_quality"] is None \
                    and s.get("own_assessment") is None and s["price_cents"] <= left:
                return _out({"action": "ask", "stall": s["id"]})
        if obs["search"]["phase"] != "choose":
            return _out({"action": "move_on"})
        pool = [(s, True) for s in here] + [(s, False) for s in obs["search"]["seen_elsewhere"]]
        cands = [(s, h) for s, h in pool if self._candidate(s, me, left, q_req)]
        if not cands:
            return _out({"action": "move_on"})

        def key(x):
            s = x[0]
            if "rating" in s:
                return (-(0.5 if s["rating"] is None else s["rating"]), s["price_cents"], _tie(s))
            return (s["price_cents"], _tie(s))
        cands.sort(key=key)
        best, is_here = cands[0]
        rule = obs["search"].get("choice")
        if rule is not None and rule.get("rule") == "logit":     # engine 1.1.0: buyers.choice logit
            best, is_here = cands[logit_pick([s for s, _ in cands], rule)]
        ids = [s["id"] for s, _ in cands]
        if is_here:
            return _out({"action": "buy", "stall": best["id"], "units": int(min(need, left // best["price_cents"])),
                         "candidates": ids})
        return _out({"action": "choose", "stall": best["id"], "candidates": ids})


def logit_pick(rows: list[dict], rule: dict) -> int:
    """Engine 1.1.0, buyers.choice logit: the index of the row picked with probability proportional to
    exp(w_r x rating - w_p x price / base), by inverse CDF of the buyer's uniform rule["u"] over the rows in the given
    (lexicographic) order. w_r = rule["rating_weight"] for rows that carry a rating (unrated = 0.5), else 0."""
    base = float(rule["base_price_cents"])
    v = []
    for s in rows:
        wr = float(rule["rating_weight"]) if "rating" in s else 0.0
        r = 0.5 if s.get("rating") is None else float(s["rating"])
        v.append(wr * r - float(rule["price_weight"]) * s["price_cents"] / base)
    m = max(v)
    w = [math.exp(x - m) for x in v]
    target, c = float(rule["u"]) * sum(w), 0.0
    for i, x in enumerate(w):
        c += x
        if target < c:
            return i
    return len(w) - 1


def _tie(s: dict):
    """Tie-break key for a stall row: its tie_rank under buyers.tie_break "random" (engine 0.20.0), else its id."""
    r = s.get("tie_rank")
    return s["id"] if r is None else r
