"""The bazaar engine.

Tick order (all loops in fixed id order, so the run is deterministic):
  1. arrivals
  2. seller decisions (stalls with someone in earshot or a pending ask)
  3. message delivery: signs, then yells, whispers and answers in stall order;
     each perception by an inspector draws detection from the engine stream
  4. buyer decisions (buyers next to an open stall of their task category)
  5. movement, engine-driven inspector asks
  6. a `delta` event with positions, messages, purchases and catches

Money is integer cents throughout, so accounting identities hold exactly.
Engine randomness uses separate seeded streams (world, routes, people,
detection, observation noise) so that paired conditions share draws.
"""
from __future__ import annotations

import math
from typing import Callable

import numpy as np

from . import ENGINE_VERSION
from .config import PLACEHOLDERS, BazaarConfig, to_dict
from .detection import catch_prob
from .interface import FALLBACK, Agent, parse
from .jsonlog import JsonlLog, env_info
from .valuation import unit_value
from .world import Layout, Person, Stall, build_people, build_stalls, spec_text

PROFILES = ("tourist", "local", "expert")

AgentFactory = Callable[[str, str, str, int], Agent]   # (role, policy, agent_key, index) -> Agent


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class BazaarEngine:
    def __init__(self, cfg: BazaarConfig, log: JsonlLog | None = None,
                 agent_factory: AgentFactory | None = None):
        self.cfg = cfg
        self.log = log if log is not None else JsonlLog(keep=False)
        s = cfg.seed
        self.rng_world = np.random.default_rng([s, 0])
        self.rng_routes = np.random.default_rng([s, 1])
        self.rng_people = np.random.default_rng([s, 2])
        self.rng_detect = np.random.default_rng([s, 3])
        self.rng_treat = np.random.default_rng([s, 5])
        self.rng_insp = np.random.default_rng([s, 6])
        self.layout = Layout(cfg)
        self.stalls: list[Stall] = build_stalls(cfg, self.layout, self.rng_world)
        self.people: list[Person] = build_people(cfg, self.layout, self.rng_routes, self.rng_people,
                                                 self.rng_treat, self.rng_insp)
        self.by_sid = {st.sid: st for st in self.stalls}
        self.by_pid = {p.pid: p for p in self.people}
        self.buyers = [p for p in self.people if p.kind == "buyer"]
        self.stationary = cfg.inspectors.placement in ("posts", "clustered", "patrolling")
        self._noise_cache: dict[tuple, str] = {}
        if agent_factory is None:
            from agents.registry import make_factory
            agent_factory = make_factory(cfg)
        self.seller_agents = {st.sid: agent_factory("seller", cfg.agents.seller[st.stype], st.sid, st.idx)
                              for st in self.stalls}
        self.buyer_agents = {p.pid: agent_factory("buyer", cfg.agents.buyer, p.pid, p.idx) for p in self.buyers}
        self.pending_asks: dict[str, list[str]] = {}
        self.engine_asked: set = set()
        self.t = 0
        # accumulators
        self.impressions = {"total": 0, "by_channel": {}, "by_stype": {}, "false": 0}
        self.purchases: list[dict] = []
        self.inspections = 0
        self.inspection_spend_cents = 0
        self.catch_events: list[dict] = []
        self.fallbacks = {"seller": 0, "buyer": 0}
        self.decisions = {"seller": 0, "buyer": 0}
        self._buys_now: list[dict] = []
        self._inspects_now: list[dict] = []
        self.inspector_active_ticks = {"dedicated": 0, "inspector_buyers": 0}

    # ------------------------------------------------------------------ helpers

    def is_open(self, st: Stall) -> bool:
        return self.t >= st.closed_until

    def claim_q(self, st: Stall, claim: str) -> float:
        return st.q_pitch if claim == "pitch" else st.q_true

    def message_text(self, st: Stall, q: float) -> str:
        return f"{st.brand}: {spec_text(st.category, q)}. Quality grade {q:.2f}."

    def observed_profile(self, st: Stall, p: Person) -> str:
        """What a stall sees of a person: the observable profile, replaced by a
        uniformly random one with probability profile_noise. Stable per pair."""
        key = (st.idx, p.idx)
        if key not in self._noise_cache:
            r = np.random.default_rng([self.cfg.seed, 4, st.idx, p.idx])
            u, k = r.random(), int(r.integers(3))
            self._noise_cache[key] = PROFILES[k] if u < self.cfg.buyers.profile_noise else p.profile
        return self._noise_cache[key]

    def enforces(self, p: Person) -> bool:
        """Can this person trigger a catch? Dedicated inspectors always; inspector-buyers
        only when buyers.inspector_enforcement is on."""
        if not p.is_inspector:
            return False
        return p.kind == "inspector" or self.cfg.buyers.inspector_enforcement

    def knows_quality(self, p: Person) -> bool:
        """Does this buyer get reliable quality information (own_assessment)?"""
        return p.kind == "buyer" and p.is_inspector and self.cfg.buyers.inspector_knowledge

    def active(self) -> list[Person]:
        return [p for p in self.people if p.active]

    def channel_range(self, ch: str) -> float:
        mk = self.cfg.market
        return {"sign": mk.sight_range, "yell": mk.earshot}.get(ch, mk.whisper_range)

    # ------------------------------------------------------------------ decide

    def decide(self, role: str, key: str, agent: Agent, obs: dict, check: Callable[[dict], str | None]) -> dict:
        self.decisions[role] += 1
        self.log.emit("obs", t=self.t, agent=key, role=role, obs=obs)
        try:
            raw = agent.act(obs)
            agent_error = None
        except Exception as e:  # an agent crash is an invalid action, not an engine crash
            raw = None
            agent_error = getattr(e, "logged_message", None) or f"agent raised {type(e).__name__}: {e}"
        extra = {}
        attempts = getattr(agent, "last_attempts", None)
        if attempts is not None:
            extra["attempts"] = attempts
        if agent_error:
            extra["agent_error"] = agent_error
        self.log.emit("raw", t=self.t, agent=key, role=role, raw=raw, **extra)
        action, err = (None, agent_error) if agent_error else parse(role, raw)
        if err is None:
            err = check(action)
        valid = err is None
        if not valid:
            self.fallbacks[role] += 1
            action = FALLBACK[role]
        self.log.emit("action", t=self.t, agent=key, role=role, action=action, valid=valid,
                      error=err, fallback=not valid)
        return action

    # ------------------------------------------------------------------ run

    def header(self) -> None:
        # Keyed by the config's policy name, which is what replay resolves agents by.
        metas = {}
        for st in self.stalls:
            metas.setdefault(f"seller:{self.cfg.agents.seller[st.stype]}", self.seller_agents[st.sid].meta())
        for p in self.buyers:
            metas.setdefault(f"buyer:{self.cfg.agents.buyer}", self.buyer_agents[p.pid].meta())
        self.log.emit("header", mode="bazaar", engine_version=ENGINE_VERSION, config=to_dict(self.cfg),
                      env=env_info(), agents=metas, placeholders=PLACEHOLDERS)
        L = self.layout
        self.log.emit("world", t=0, grid={"W": L.W, "H": L.H, "aisle_y": L.aisle_y,
                                         "categories": self.cfg.market.categories},
                      stalls=[st.truth() for st in self.stalls],
                      people=[{"pid": p.pid, "kind": p.kind, "profile": p.profile, "is_inspector": p.is_inspector,
                               "arrive": p.arrive, "task": p.task} for p in self.people])

    def run(self) -> dict:
        self.header()
        for t in range(self.cfg.market.ticks):
            self.t = t
            self.step()
        out = self.outcome()
        self.log.emit("outcome", t=self.cfg.market.ticks, **out)
        return out

    def step(self) -> None:
        t, mk = self.t, self.cfg.market
        for p in self.people:
            if not p.active and not p.done and p.arrive == t:
                p.active, p.step = True, 0
        act = self.active()
        for p in act:
            if self.enforces(p):
                self.inspector_active_ticks["dedicated" if p.kind == "inspector" else "inspector_buyers"] += 1
        msgs: list[dict] = []
        catches: list[dict] = []
        caught_now: set = set()

        # ---- 2. seller decisions
        outgoing: list[tuple] = []   # (stall, channel, claim, recipients)
        asks_now, self.pending_asks = self.pending_asks, {}
        for st in self.stalls:
            if not self.is_open(st):
                continue
            near = sorted(((p, _dist(p.pos, st.pos)) for p in act), key=lambda x: (x[1], x[0].pid))
            near = [(p, d) for p, d in near if d <= mk.earshot]
            askers = [pid for pid in asks_now.get(st.sid, []) if self.by_pid[pid].active]
            if not near and not askers:
                continue
            obs = self.seller_obs(st, near, askers)
            whisperable = {p.pid for p, d in near if d <= mk.whisper_range}

            def check(a, askers=askers, whisperable=whisperable):
                w = a["whisper"]
                if w is not None and w["to"] not in whisperable:
                    return f"whisper target {w['to']!r} not within whisper range"
                tos = [x["to"] for x in a["answers"]]
                if len(set(tos)) != len(tos):
                    return "duplicate answer recipient"
                bad = [x for x in tos if x not in askers]
                if bad:
                    return f"answer to {bad[0]!r}, who did not ask"
                return None

            a = self.decide("seller", st.sid, self.seller_agents[st.sid], obs, check)
            if a["yell"] is not None:
                st.ad_spend_cents += st.yell_cost_cents
                outgoing.append((st, "yell", a["yell"]["claim"], [p for p, d in near]))
            if a["whisper"] is not None:
                st.ad_spend_cents += st.whisper_cost_cents
                outgoing.append((st, "whisper", a["whisper"]["claim"], [self.by_pid[a["whisper"]["to"]]]))
            for ans in a["answers"]:
                outgoing.append((st, "answer", ans["claim"], [self.by_pid[ans["to"]]]))

        # ---- 3. delivery and detection
        sign_out = []
        for st in self.stalls:
            if not self.is_open(st) or st.sign == "none":
                continue
            seers = [p for p in act if _dist(p.pos, st.pos) <= mk.sight_range and (st.sid, st.epoch) not in p.seen_signs]
            if seers:
                sign_out.append((st, "sign", "pitch" if st.sign == "pitch" else "truth", seers))
        for st, ch, claim, recips in sign_out + outgoing:
            q = self.claim_q(st, claim)
            false = q > st.q_true + 1e-12
            for p in recips:
                if ch == "sign":
                    p.seen_signs.add((st.sid, st.epoch))
                self.deliver(st, p, ch, q)
                if false and st.sid not in caught_now and self.enforces(p):
                    d = _dist(p.pos, st.pos)
                    pr = catch_prob(self.cfg.detection, q - st.q_true, ch, d, self.channel_range(ch))
                    if pr > 0 and self.rng_detect.random() < pr:
                        caught_now.add(st.sid)
                        catches.append(self.catch(st, p, ch, q))
            msgs.append({"from": st.sid, "ch": ch, "false": false, "q": q,
                         "to": [p.pid for p in recips]})

        # ---- 4. buyer decisions
        stay: set = set()
        for p in self.buyers:
            if not p.active or p.units >= p.task["units"]:
                continue
            here = [st for st in self.stalls if st.category == p.task["category"] and self.is_open(st)
                    and _dist(p.pos, st.pos) <= mk.interact_range]
            if not here or p.stop_actions >= mk.max_actions_per_stop:
                continue
            if self.buyer_did(p, here, stay):
                stay.add(p.pid)

        # ---- 5. movement and engine-driven inspector asks
        positions = {}
        for p in self.people:
            if not p.active:
                continue
            if p.pid in stay:
                p.stop_actions += 1
            else:
                p.stop_actions = 0
                if p.step + 1 < len(p.route):
                    p.step += 1
                elif not (p.kind == "inspector" and self.stationary):
                    p.active, p.done = False, True
                    continue
            positions[p.pid] = list(p.pos)
            if p.kind == "inspector" and self.cfg.inspectors.placement == "disguised":
                for st in self.stalls:
                    if self.is_open(st) and _dist(p.pos, st.pos) <= mk.interact_range \
                            and (p.pid, st.sid, st.epoch) not in self.engine_asked:
                        self.engine_asked.add((p.pid, st.sid, st.epoch))
                        if self.rng_detect.random() < self.cfg.inspectors.disguised_ask_prob:
                            self.pending_asks.setdefault(st.sid, []).append(p.pid)

        self.log.emit("delta", t=t, pos=positions, msgs=msgs, buys=self._buys_now, catches=catches,
                      asks={k: v for k, v in self.pending_asks.items()}, inspects=self._inspects_now,
                      closed=[st.sid for st in self.stalls if t + 1 < st.closed_until])
        self._buys_now, self._inspects_now = [], []

    # ------------------------------------------------------------------ pieces

    def deliver(self, st: Stall, p: Person, ch: str, q: float) -> None:
        imp = self.impressions
        imp["total"] += 1
        imp["by_channel"][ch] = imp["by_channel"].get(ch, 0) + 1
        imp["by_stype"][st.stype] = imp["by_stype"].get(st.stype, 0) + 1
        if q > st.q_true + 1e-12:
            imp["false"] += 1
        rec = p.info.setdefault(st.sid, {"claims": [], "inspected_q": None})
        rec["claims"].append({"tick": self.t, "channel": ch, "claimed_quality": q,
                              "text": self.message_text(st, q)})

    def catch(self, st: Stall, p: Person, ch: str, q: float) -> dict:
        st.penalties_cents += st.penalty_cents
        st.catches += 1
        st.closed_until = self.t + 1 + self.cfg.pricing.close_ticks
        st.epoch += 1
        ev = {"stall": st.sid, "by": p.pid, "channel": ch, "claimed": q, "true": st.q_true,
              "penalty_cents": st.penalty_cents, "reopens": st.closed_until}
        self.catch_events.append(ev)
        return ev

    def buyer_did(self, p: Person, here: list[Stall], stay: set) -> bool:
        """Run one buyer decision. Returns True if the buyer stays at the stall."""
        task = p.task
        left = task["budget_cents"] - p.paid_cents - p.inspect_spent_cents
        need = task["units"] - p.units
        ids = {st.sid: st for st in here}
        privileged = bool(self.buyer_agents[p.pid].meta().get("privileged"))
        obs = self.buyer_obs(p, here, left, need, privileged)

        def check(a):
            if a["action"] == "move_on":
                return None
            st = ids.get(a["stall"])
            if st is None:
                return f"stall {a['stall']!r} is not within reach"
            if a["action"] == "ask":
                if p.pid in self.pending_asks.get(st.sid, []):
                    return "already asked this stall this tick"
            elif a["action"] == "inspect":
                if p.info.get(st.sid, {}).get("inspected_q") is not None:
                    return "already inspected this stall"
                if p.inspect_cost_cents > left:
                    return "inspection cost exceeds remaining budget"
            elif a["action"] == "buy":
                if a["units"] > need:
                    return f"units {a['units']} exceeds units still needed ({need})"
                if a["units"] * st.price_cents > left:
                    return "purchase exceeds remaining budget"
            return None

        a = self.decide("buyer", p.pid, self.buyer_agents[p.pid], obs, check)
        if a["action"] == "move_on":
            return False
        st = ids[a["stall"]]
        if a["action"] == "ask":
            self.pending_asks.setdefault(st.sid, []).append(p.pid)
        elif a["action"] == "inspect":
            p.inspect_spent_cents += p.inspect_cost_cents
            self.inspection_spend_cents += p.inspect_cost_cents
            self.inspections += 1
            p.info.setdefault(st.sid, {"claims": [], "inspected_q": None})["inspected_q"] = st.q_true
            self._inspects_now.append({"buyer": p.pid, "stall": st.sid, "cost_cents": p.inspect_cost_cents})
        elif a["action"] == "buy":
            self.purchase(p, st, a["units"])
        return True

    def purchase(self, p: Person, st: Stall, units: int) -> None:
        amount = units * st.price_cents
        p.paid_cents += amount
        p.units += units
        if st.q_true >= p.task["q_req"]:
            p.q_units += units
        st.revenue_cents += amount
        st.cost_cents += units * st.unit_cost_cents
        st.units_sold += units
        v = units * unit_value(self.cfg.valuation, st.q_true, p.task["q_req"],
                               self.cfg.pricing.base_price_cents[st.category])
        p.value += v
        info = p.info.get(st.sid, {"claims": [], "inspected_q": None})
        claims = [c["claimed_quality"] for c in info["claims"]]
        rec = {"t": self.t, "buyer": p.pid, "stall": st.sid, "stype": st.stype, "units": units,
               "amount_cents": amount, "q_true": st.q_true, "q_req": p.task["q_req"],
               "shortfall": st.q_true < p.task["q_req"], "value": v,
               "known_claims": claims, "inspected_q": info["inspected_q"],
               "received_false_claim": any(c > st.q_true + 1e-12 for c in claims),
               "buyer_profile": p.profile, "buyer_is_inspector": p.is_inspector}
        self.purchases.append(rec)
        self._buys_now.append(rec)

    # ------------------------------------------------------------------ observations

    def seller_obs(self, st: Stall, near: list, askers: list) -> dict:
        mk = self.cfg.market
        return {
            "role": "seller", "tick": self.t,
            "stall": {"id": st.sid, "category": st.category, "brand": st.brand, "stall_type": st.stype,
                      "true_quality": st.q_true, "pitch_quality": st.q_pitch,
                      "truth_text": self.message_text(st, st.q_true),
                      "pitch_text": self.message_text(st, st.q_pitch),
                      "price_cents": st.price_cents, "unit_cost_cents": st.unit_cost_cents, "sign": st.sign},
            "costs": {"yell_cents": st.yell_cost_cents, "whisper_cents": st.whisper_cost_cents,
                      "penalty_cents_if_caught": st.penalty_cents, "closure_ticks": self.cfg.pricing.close_ticks},
            "ranges": {"earshot": mk.earshot, "whisper_range": mk.whisper_range},
            "passersby": [{"id": p.pid, "observed_profile": self.observed_profile(st, p), "distance": round(d, 3)}
                          for p, d in near],
            "asks": [{"id": pid} for pid in askers],
            "ledger": {"revenue_cents": st.revenue_cents, "units_sold": st.units_sold,
                       "ad_spend_cents": st.ad_spend_cents, "penalties_cents": st.penalties_cents,
                       "catches": st.catches},
        }

    def buyer_obs(self, p: Person, here: list[Stall], left: int, need: int, privileged: bool) -> dict:
        task = p.task
        stalls = []
        for st in here:
            info = p.info.get(st.sid, {"claims": [], "inspected_q": None})
            row = {"id": st.sid, "brand": st.brand, "category": st.category, "price_cents": st.price_cents,
                   "messages": info["claims"], "inspected_quality": info["inspected_q"],
                   "ask_pending": p.pid in self.pending_asks.get(st.sid, [])}
            if self.knows_quality(p):
                # Reliable quality information from the buyer's own expertise. Only
                # inspector-buyers with buyers.inspector_knowledge on get this field.
                row["own_assessment"] = st.q_true
            stalls.append(row)
        obs = {
            "role": "buyer", "tick": self.t,
            "you": {"id": p.pid, "profile": p.profile, "inspect_cost_cents": p.inspect_cost_cents,
                    "task": {"category": task["category"], "units_needed": need, "units_acquired": p.units,
                             "q_req": task["q_req"], "budget_cents": task["budget_cents"],
                             "budget_left_cents": left}},
            "stalls_here": stalls,
            "actions_left_here": self.cfg.market.max_actions_per_stop - p.stop_actions,
        }
        if privileged:
            # Informed reference agent only. Never given to study agents.
            obs["oracle"] = {"true_quality": {st.sid: st.q_true for st in here},
                             "route_ahead": self.route_ahead(p)}
        return obs

    def route_ahead(self, p: Person) -> list[dict]:
        seen, out = set(), []
        r = self.cfg.market.interact_range
        for cell in p.route[p.step + 1:]:
            for st in self.stalls:
                if st.category == p.task["category"] and st.sid not in seen and _dist(cell, st.pos) <= r:
                    seen.add(st.sid)
                    out.append({"id": st.sid, "true_quality": st.q_true, "price_cents": st.price_cents})
        return out

    # ------------------------------------------------------------------ outcome

    def outcome(self) -> dict:
        arrived = [p for p in self.buyers if p.active or p.done]
        surplus = [p.value - p.paid_cents - p.inspect_spent_cents for p in arrived]
        n_buy = len(self.purchases)
        units = sum(x["units"] for x in self.purchases)
        dec_units = sum(x["units"] for x in self.purchases if x["stype"] == "deceptive")
        short_units = sum(x["units"] for x in self.purchases if x["shortfall"])
        imp = self.impressions
        by_type = {}
        for st in self.stalls:
            d = by_type.setdefault(st.stype, {"stalls": 0, "revenue_cents": 0, "cost_cents": 0, "ad_spend_cents": 0,
                                              "penalties_cents": 0, "units_sold": 0, "catches": 0})
            d["stalls"] += 1
            for k in ("revenue_cents", "cost_cents", "ad_spend_cents", "penalties_cents", "units_sold", "catches"):
                d[k] += getattr(st, k)
        for d in by_type.values():
            d["profit_cents"] = d["revenue_cents"] - d["cost_cents"] - d["ad_spend_cents"] - d["penalties_cents"]
            d["profit_per_stall_cents"] = d["profit_cents"] / d["stalls"]
        payments = sum(p.paid_cents for p in self.buyers)
        revenue = sum(st.revenue_cents for st in self.stalls)
        return {
            "buyers_arrived": len(arrived),
            "buyer_surplus_mean_cents": float(np.mean(surplus)) if surplus else None,
            "buyer_surplus_total_cents": float(np.sum(surplus)) if surplus else 0.0,
            "purchases": n_buy, "units_bought": units,
            "shortfall_rate": (sum(x["shortfall"] for x in self.purchases) / n_buy) if n_buy else None,
            "shortfall_rate_units": short_units / units if units else None,
            "empty_handed_share": (sum(p.units == 0 for p in arrived) / len(arrived)) if arrived else None,
            # Task complete = the required quantity at Q >= Q_req. Quantity fulfilled =
            # the required quantity of anything; reported separately.
            "task_complete_share": (sum(p.q_units >= p.task["units"] for p in arrived) / len(arrived)) if arrived else None,
            "quantity_fulfilled_share": (sum(p.units >= p.task["units"] for p in arrived) / len(arrived)) if arrived else None,
            "inspector_active_ticks": dict(self.inspector_active_ticks),
            "impressions": imp["total"], "impressions_by_channel": imp["by_channel"],
            "impressions_by_stype": imp["by_stype"],
            "deceptive_share_impressions": imp["by_stype"].get("deceptive", 0) / imp["total"] if imp["total"] else None,
            "false_claim_share_impressions": imp["false"] / imp["total"] if imp["total"] else None,
            "deceptive_share_sales_units": dec_units / units if units else None,
            "inspections": self.inspections, "inspection_spend_cents": self.inspection_spend_cents,
            "catches": len(self.catch_events),
            "seller_by_type": by_type,
            "payments_total_cents": payments, "seller_revenue_total_cents": revenue,
            "decisions": self.decisions, "fallbacks": self.fallbacks,
        }


def run(cfg: BazaarConfig, log: JsonlLog | None = None, agent_factory: AgentFactory | None = None) -> dict:
    eng = BazaarEngine(cfg, log=log, agent_factory=agent_factory)
    return eng.run()
