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
from .scaling import scaled_config
from . import brands as B
from . import critics as C
from .world import (UNIFORMABLE, Layout, Person, Stall, build_people, build_stalls, refine_world, spec_text,
                    validate_demand)

PROFILES = ("tourist", "local", "expert")

AgentFactory = Callable[[str, str, str, int], Agent]   # (role, policy, agent_key, index) -> Agent


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class BazaarEngine:
    def __init__(self, cfg: BazaarConfig, log: JsonlLog | None = None,
                 agent_factory: AgentFactory | None = None, root: tuple | None = None,
                 stalls: list[Stall] | None = None, day: int = 1, book: "B.BrandBook | None" = None):
        # root: stream prefix ([seed] by default; [seed, 9, day] on later days of a multi-day
        # run). stalls: an existing, already-refined stall list to use instead of building one
        # (later days of a multi-day run). day: the day number (multi-day runs). book: brand state
        # carried across days (brands.enabled only).
        # The world is built from the config as given (real units = k = 1 cells and ticks)
        # and refined to scale k; the engine then runs on the scaled config. The log
        # header records the config as given.
        self.cfg_given = cfg
        self.k = int(cfg.market.scale)
        self.log = log if log is not None else JsonlLog(keep=False)
        self.root = r = (cfg.seed,) if root is None else tuple(root)
        self.rng_world = np.random.default_rng([*r, 0])
        self.rng_routes = np.random.default_rng([*r, 1])
        self.rng_people = np.random.default_rng([*r, 2])
        self.rng_detect = np.random.default_rng([*r, 3])
        self.rng_treat = np.random.default_rng([*r, 5])
        self.rng_insp = np.random.default_rng([*r, 6])
        self.layout = Layout(cfg)
        built = stalls is None
        self.stalls: list[Stall] = build_stalls(cfg, self.layout, self.rng_world) if built else stalls
        validate_demand(cfg)
        self.people: list[Person] = build_people(cfg, self.layout, self.rng_routes, self.rng_people,
                                                 self.rng_treat, self.rng_insp, root=r, stalls=self.stalls)
        refine_world(self.layout, self.stalls if built else [], self.people, self.k)
        cfg = self.cfg = scaled_config(cfg)
        self.by_sid = {st.sid: st for st in self.stalls}
        self.by_pid = {p.pid: p for p in self.people}
        self.buyers = [p for p in self.people if p.kind == "buyer"]
        # Search depth (0.10.0): fixed by profile, so buyer populations do not depend on it.
        depth = cfg.buyers.search_depth
        if set(depth) - set(PROFILES) or any(int(v) != v or v < 1 for v in depth.values()):
            raise ValueError(f"buyers.search_depth must map profiles to integers >= 1, got {depth!r}")
        self.choice_set = cfg.buyers.demand_mode == "choice_set"
        for p in self.buyers:
            # choice_set (0.12.0): search depth = the size of the buyer's consideration set
            p.search_k = len(p.consider) if self.choice_set else int(depth.get(p.profile, 1))
        self.search_log = bool(cfg.buyers.search_log)
        if self.search_log:
            for p in self.buyers:
                p.search_rec = {"profile": p.profile, "k": p.search_k, "seen": [], "chosen": [], "bought": [],
                                "candidates": None, "walk_ticks": 0, "skipped_closed": []}
        self._reach: dict = {}
        self.exposure: dict = {}
        self.stationary = cfg.inspectors.placement in ("posts", "clustered", "patrolling")
        self._noise_cache: dict[tuple, str] = {}
        if agent_factory is None:
            from agents.registry import make_factory
            agent_factory = make_factory(self.cfg_given, self.root)
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
        # Uniform-eligible inspectors: dedicated inspectors on a placement that can wear a
        # uniform. They are the uniformed ones when inspectors.uniformed is true. The
        # diagnostics below are keyed on eligibility, not on the uniform itself, so the
        # outcome of a policy that ignores the uniform does not depend on the flag.
        self.uniform_eligible = {p.pid for p in self.people
                                 if p.kind == "inspector" and cfg.inspectors.placement in UNIFORMABLE}
        self.false_impressions_to_eligible = 0
        self.false_claims_by_stall = {st.sid: {"messages": 0, "no_eligible_in_earshot": 0}
                                      for st in self.stalls if st.stype == "deceptive"}
        self.catch_ticks: list[tuple[int, Stall]] = []   # (tick, stall), for public catch notices
        rr = cfg.inspectors.recognition_range
        self.recognition_range = cfg.market.earshot if rr is None else float(rr)
        # 0.7.0 switches. Outcome and observation fields they add appear only when they are on,
        # so default runs are byte-identical to 0.6.0.
        self.switch_costs_on = bool(cfg.pricing.switch_cost_to_genuine or cfg.pricing.switch_cost_to_deceptive)
        if cfg.ratings.mode not in ("off", "hidden", "public"):
            raise ValueError(f"unknown ratings.mode {cfg.ratings.mode!r}")
        # 0.8.0 switches (brands, known horizon), also off by default.
        self.day = int(day)
        self.brands_on = bool(cfg.brands.enabled)
        self.book = None
        self.rename_log: list[dict] = []
        self.bust_log: list[dict] = []
        self._renames_now: list[dict] = []
        self._busts_now: list[dict] = []
        self.seller_privileged = {sid: bool(a.meta().get("privileged")) for sid, a in self.seller_agents.items()}
        C.validate(cfg)
        if self.brands_on:
            self.book = book if book is not None else B.BrandBook(self.stalls)
            if book is None and (C.critics_on(cfg) or C.capture_on(cfg)):
                C.init_ties(cfg, self.book, self.stalls)
            B.morning_prices(cfg, self.stalls, self.book)
        # Inspector capture (0.11.0): each dedicated inspector's order among inspectors.
        self.capture_effect = float(cfg.inspectors.capture_effect) if C.capture_on(cfg) else None
        self.insp_ord = {p.pid: j for j, p in enumerate(x for x in self.people if x.kind == "inspector")}
        # Liability (0.15.0): enforcement intensity, penalty lag, exit.
        ds, lag = cfg.inspectors.detect_scale, cfg.pricing.penalty_lag_days
        if isinstance(ds, bool) or not isinstance(ds, (int, float)) or not math.isfinite(ds) or ds < 0:
            raise ValueError(f"inspectors.detect_scale must be a finite number >= 0, got {ds!r}")
        if isinstance(lag, bool) or int(lag) != lag or lag < 0:
            raise ValueError(f"pricing.penalty_lag_days must be an integer >= 0, got {lag!r}")
        self.detect_scale, self.lag = float(ds), int(lag)
        self.fines = {"charged": [], "deferred": [], "uncollectible": []}   # today's fines: (sid, cents)
        for st in self.stalls:                    # lagged fines falling due today are charged today
            if st.fines_pending and st.exited_day is None:
                due = [f for f in st.fines_pending if f["due_day"] <= self.day]
                st.fines_pending = [f for f in st.fines_pending if f["due_day"] > self.day]
                for f in due:
                    st.penalties_cents += f["cents"]
                    self.fines["charged"].append((st.sid, f["cents"]))

    # ------------------------------------------------------------------ helpers

    def capture_factor(self, p: Person, st: Stall) -> float:
        """1, or (1 - capture_effect) when a dedicated inspector is tied to the stall's brand."""
        if self.capture_effect is None or p.kind != "inspector":
            return 1.0
        return 1.0 - self.capture_effect if (self.insp_ord[p.pid], st.brand) in self.book.capture_ties else 1.0

    @staticmethod
    def considers(p: Person, st: Stall) -> bool:
        """Whether a buyer may consider a stall: always in "walk" demand; in "choice_set" demand
        (0.12.0) only the stalls of its consideration set."""
        return p.consider is None or st.sid in p.consider

    def is_open(self, st: Stall) -> bool:
        return self.t >= st.closed_until

    def claim_q(self, st: Stall, claim: str) -> float:
        return st.q_pitch if claim == "pitch" else st.q_true

    def message_text(self, st: Stall, q: float, p: Person | None = None) -> str:
        brand = st.brand if p is None else self.perceived_brand(st, p)
        return f"{brand}: {spec_text(st.category, q)}. Quality grade {q:.2f}."

    def perceived_brand(self, st: Stall, p: Person) -> str:
        """The name a person reads on the stall: tourists cannot tell a counterfeit from its
        original, so they read the original's name (brands only)."""
        if st.counterfeit_of is not None and p.profile == "tourist":
            return st.counterfeit_of
        return st.brand

    def observed_profile(self, st: Stall, p: Person) -> str:
        """What a stall sees of a person: the observable profile, replaced by a
        uniformly random one with probability profile_noise. Stable per pair."""
        key = (st.idx, p.idx)
        if key not in self._noise_cache:
            r = np.random.default_rng([*self.root, 4, st.idx, p.idx])
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
        self.header_line()
        self.world_event()

    def header_line(self) -> None:
        # Keyed by the config's policy name, which is what replay resolves agents by.
        metas = {}
        for st in self.stalls:
            metas.setdefault(f"seller:{self.cfg.agents.seller[st.stype]}", self.seller_agents[st.sid].meta())
        for p in self.buyers:
            metas.setdefault(f"buyer:{self.cfg.agents.buyer}", self.buyer_agents[p.pid].meta())
        self.log.emit("header", mode="bazaar", engine_version=ENGINE_VERSION, config=to_dict(self.cfg_given),
                      env=env_info(), agents=metas, placeholders=PLACEHOLDERS)

    def world_event(self) -> None:
        L = self.layout
        self.log.emit("world", t=0, grid={"W": L.W, "H": L.H, "aisle_y": L.aisle_y,
                                         "categories": self.cfg.market.categories},
                      stalls=[st.truth() for st in self.stalls],
                      people=[{"pid": p.pid, "kind": p.kind, "profile": p.profile, "is_inspector": p.is_inspector,
                               "arrive": p.arrive, "task": p.task} for p in self.people])

    def run(self, header: bool = True) -> dict:
        if header:
            self.header()
        else:
            self.world_event()
        for t in range(self.cfg.market.ticks):
            self.t = t
            self.step()
        self.close_day()
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

            def check(a, askers=askers, whisperable=whisperable, st=st):
                if "rename" in a and not (self.brands_on and st.rename_pending):
                    return "rename is allowed only on the first decision after a reopening"
                if "bust_out" in a and not (self.brands_on and st.stype == "genuine" and st.busted_day is None
                                            and not st.decided_today):
                    return "bust_out is allowed only for an honest genuine stall on its first decision of the day"
                if "exit" in a and st.exit_pending:
                    return "the stall is already leaving at the end of today"
                w = a["whisper"]
                if w is not None and not mk.whispers_allowed:
                    return "whispers are not allowed in this market"
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
            if self.brands_on:
                if "rename" in a:
                    self.rename(st, a["rename"])
                if a.get("bust_out"):
                    self.bust_out(st)
                st.rename_pending = False
                st.decided_today = True
            if a.get("exit"):              # 0.15.0: leaves at the end of today
                st.exit_pending = True
            if a.get("sign") is not None:   # takes effect in this tick's delivery
                st.sign = a["sign"]
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
        watched: dict[str, bool] = {}
        for st, ch, claim, recips in sign_out + outgoing:
            q = self.claim_q(st, claim)
            false = q > st.q_true + 1e-12
            if false and st.sid in self.false_claims_by_stall:
                if st.sid not in watched:
                    watched[st.sid] = any(p.pid in self.uniform_eligible and _dist(p.pos, st.pos) <= mk.earshot
                                          for p in act)
                fc = self.false_claims_by_stall[st.sid]
                fc["messages"] += 1
                fc["no_eligible_in_earshot"] += not watched[st.sid]
            for p in recips:
                if false and p.pid in self.uniform_eligible:
                    self.false_impressions_to_eligible += 1
                if ch == "sign":
                    p.seen_signs.add((st.sid, st.epoch))
                self.deliver(st, p, ch, q)
                if false and st.sid not in caught_now and self.enforces(p):
                    d = _dist(p.pos, st.pos)
                    pr = catch_prob(self.cfg.detection, q - st.q_true, ch, d, self.channel_range(ch))
                    if pr > 0 and self.rng_detect.random() < pr * self.capture_factor(p, st) * self.detect_scale:
                        caught_now.add(st.sid)
                        catches.append(self.catch(st, p, ch, q))
            msgs.append({"from": st.sid, "ch": ch, "false": false, "q": q,
                         "to": [p.pid for p in recips]})

        # ---- 4. buyer decisions
        stay: set = set()
        held: set = set()
        for p in self.buyers:
            if not p.active:
                continue
            if self.search_log:
                self.expose(p)
            if t < p.hold_until:          # still busy with its last action (scale > 1 only)
                held.add(p.pid)
                continue
            if p.units >= p.task["units"]:
                continue
            if p.search_k > 1:
                if self.search_decide(p, stay):
                    stay.add(p.pid)
                    p.hold_until = t + self.k
                continue
            here = [st for st in self.stalls if st.category == p.task["category"] and self.is_open(st)
                    and _dist(p.pos, st.pos) <= mk.interact_range and self.considers(p, st)]
            if self.search_log:
                for st in here:
                    if st.sid not in p.seen:
                        p.search_rec["seen"].append(st.sid)
                    p.seen[st.sid] = p.step
            if not here or p.stop_actions >= mk.max_actions_per_stop:
                continue
            if self.buyer_did(p, here, stay):
                stay.add(p.pid)
                p.hold_until = t + self.k

        # ---- 5. movement and engine-driven inspector asks
        positions = {}
        for p in self.people:
            if not p.active:
                continue
            if p.pid in stay:
                p.stop_actions += 1
            elif p.pid in held:
                pass
            elif p.target is not None:   # a searching buyer walking to the stall it chose
                p.stop_actions = 0
                goal = p.seen[p.target]
                if goal != p.step:
                    p.step += 1 if goal > p.step else -1
                    p.walk_ticks += 1
                    if p.search_rec is not None:
                        p.search_rec["walk_ticks"] += 1
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

        extra = {"renames": self._renames_now, "bust_outs": self._busts_now} if self.brands_on else {}
        self.log.emit("delta", t=t, pos=positions, msgs=msgs, buys=self._buys_now, catches=catches,
                      asks={k: v for k, v in self.pending_asks.items()}, inspects=self._inspects_now,
                      closed=[st.sid for st in self.stalls if t + 1 < st.closed_until], **extra)
        self._buys_now, self._inspects_now = [], []
        self._renames_now, self._busts_now = [], []

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
                              "text": self.message_text(st, q, p)})

    def catch(self, st: Stall, p: Person, ch: str, q: float) -> dict:
        if self.lag:                    # 0.15.0: the fine falls due lag days later
            due = self.day + self.lag
            st.fines_pending.append({"catch_day": self.day, "due_day": due, "cents": st.penalty_cents})
            self.fines["deferred"].append((st.sid, st.penalty_cents))
        else:
            st.penalties_cents += st.penalty_cents
            self.fines["charged"].append((st.sid, st.penalty_cents))
        st.catches += 1
        st.closed_until = self.t + 1 + self.cfg.pricing.close_ticks
        st.epoch += 1
        ev = {"stall": st.sid, "by": p.pid, "channel": ch, "claimed": q, "true": st.q_true,
              "penalty_cents": st.penalty_cents, "reopens": st.closed_until}
        if self.lag:
            ev["due_day"] = due
        self.catch_events.append(ev)
        self.catch_ticks.append((self.t, st))
        if self.brands_on:
            st.rename_pending = True
        return ev

    def rename(self, st: Stall, how: str) -> None:
        """Rename a reopened stall (brands only). Draws from [day root, 11, stall, rename count]."""
        book = self.book
        n = book.renames[st.sid]
        book.renames[st.sid] = n + 1
        rng = np.random.default_rng([*self.root, 11, st.idx, n])
        old, target = st.brand, None
        how = B.canonical_reopen(how)
        if how == "counterfeit":
            target = B.counterfeit_target(self.stalls, st, book, rng)
        if target is None:
            name = B.fresh_name(st.category, rng, book.used)
            st.counterfeit_of = None
            st.price_cents = B.premium_price(self.cfg, st, None)
        else:
            name = B.counterfeit_name(target.brand, rng, book.used)
            st.counterfeit_of = target.brand
            st.price_cents = target.price_cents
        book.add(name)
        st.brand, st.rating = name, None
        rec = {"t": self.t, "day": self.day, "stall": st.sid, "how": how, "from": old, "to": name,
               "counterfeit_of": st.counterfeit_of, "target_stall": target.sid if target else None,
               "target_rating": book.rating(target.brand) if target else None, "price_cents": st.price_cents}
        self.rename_log.append(rec)
        self._renames_now.append(rec)

    def bust_out(self, st: Stall) -> None:
        """A genuine stall harvests its reputation (brands only): its true quality drops to its
        low quality for good; name, price and claimed quality (its sign now shows the old quality,
        "pitch") are unchanged, so its claims become false."""
        was = st.q_true
        st.q_true = B.bust_quality(self.cfg, st)
        st.unit_cost_cents = B.unit_cost(self.cfg, st, st.q_true)
        st.sign = "pitch"
        st.busted_day = self.day
        rec = {"t": self.t, "day": self.day, "stall": st.sid, "brand": st.brand, "q_was": was, "q_true": st.q_true,
               "rating": st.rating, "price_cents": st.price_cents, "unit_cost_cents": st.unit_cost_cents}
        self.bust_log.append(rec)
        self._busts_now.append(rec)

    def reach(self, pos: tuple) -> list[Stall]:
        """Stalls (open or not) within interact range of a cell; cached per cell."""
        key = tuple(pos)
        if key not in self._reach:
            r = self.cfg.market.interact_range
            self._reach[key] = [st for st in self.stalls if _dist(key, st.pos) <= r]
        return self._reach[key]

    def expose(self, p: Person) -> None:
        """Diagnostics (buyers.search_log): which buyers of each stall's category came within
        reach of it, and which of them still needed units then."""
        shopping = p.units < p.task["units"]
        for st in self.reach(p.pos):
            if st.category != p.task["category"]:
                continue
            e = self.exposure.setdefault(st.sid, {"in_reach": set(), "in_reach_shopping": set()})
            e["in_reach"].add(p.pid)
            if shopping:
                e["in_reach_shopping"].add(p.pid)

    def search_decide(self, p: Person, stay: set) -> bool:
        """One step of a searching buyer (search_k > 1). Records the open stalls of its category
        within reach as seen; while walking to a chosen stall it decides nothing until it gets
        there (a closed chosen stall is skipped and the buyer chooses again). It may buy only once
        it has seen search_k stalls or is at the end of its route (phase "choose"). Returns True
        if the buyer stays."""
        mk = self.cfg.market
        cat = p.task["category"]
        near = [st for st in self.reach(p.pos) if st.category == cat and self.considers(p, st)]
        here = [st for st in near if self.is_open(st)]
        for st in here:
            if st.sid not in p.seen and p.search_rec is not None:
                p.search_rec["seen"].append(st.sid)
            p.seen[st.sid] = p.step
        skipped = False
        if p.target is not None:
            tst = self.by_sid[p.target]
            if tst not in near:
                return False
            if not self.is_open(tst):
                if p.search_rec is not None:
                    p.search_rec["skipped_closed"].append(tst.sid)
                p.skipped.add(tst.sid)
                p.target, skipped = None, True
        route_end = p.step >= len(p.route) - 1
        phase = "choose" if (p.choosing or len(p.seen) >= p.search_k or route_end) else "browse"
        # 0.14.0: once in "choose" a buyer stays there. Before, a buyer that chose at its route end
        # with fewer than search_k stalls seen (a stall closed when passed) and walked back reverted
        # to "browse" one step later and could not buy at the stall it chose (trapped-buyer bug).
        p.choosing = phase == "choose"
        if not here and not (phase == "choose" and (route_end or skipped)):
            return False
        if p.stop_actions >= mk.max_actions_per_stop:
            return False
        return self.buyer_did(p, here, stay, phase=phase, route_end=route_end)

    def buyer_did(self, p: Person, here: list[Stall], stay: set, phase: str | None = None,
                  route_end: bool = False) -> bool:
        """Run one buyer decision. Returns True if the buyer stays at the stall. phase is set for
        searching buyers only ("browse" or "choose")."""
        task = p.task
        left = task["budget_cents"] - p.paid_cents - p.inspect_spent_cents
        need = task["units"] - p.units
        ids = {st.sid: st for st in here}
        privileged = bool(self.buyer_agents[p.pid].meta().get("privileged"))
        obs = self.buyer_obs(p, here, left, need, privileged)
        if phase is not None:
            obs["search"] = self.search_obs(p, here, phase, route_end)

        def check(a):
            if a["action"] == "move_on":
                return None
            if a["action"] == "choose":
                if phase != "choose":
                    return ("choose is only for a searching buyer that has seen enough stalls"
                            if phase else "choose is only for searching buyers (buyers.search_depth > 1)")
                if a["stall"] not in p.seen or a["stall"] in p.skipped:
                    return f"stall {a['stall']!r} has not been seen (or was found closed)"
                if a["stall"] in ids:
                    return f"stall {a['stall']!r} is within reach: buy, ask or inspect instead"
                return None
            if a["action"] == "buy" and phase == "browse":
                return f"a searching buyer may buy only after seeing {p.search_k} stalls or at the end of its route"
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
            if phase is not None and p.target is not None and p.target in ids:
                # 0.14.0: a searching buyer that decides not to buy at the stall it chose (it learned
                # more there, or can no longer afford it) drops the target and carries on, as when it
                # finds the target closed. Before, it kept the target and stood there all day
                # (parked-buyer bug, since 0.10.0).
                p.target = None
            return False
        if a["action"] == "choose":
            p.target = a["stall"]
            if p.search_rec is not None:
                p.search_rec["chosen"].append(a["stall"])
                if "candidates" in a:
                    p.search_rec["candidates"] = list(a["candidates"])
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
            p.target = None
            if p.search_rec is not None and "candidates" in a:
                p.search_rec["candidates"] = list(a["candidates"])
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
        if self.brands_on:
            rec["brand"] = st.brand
            rec["filed_under"] = self.perceived_brand(st, p)   # where the buyer's review goes
        self.purchases.append(rec)
        self._buys_now.append(rec)
        if p.search_rec is not None:
            p.search_rec["bought"].append(st.sid)

    # ------------------------------------------------------------------ observations

    def recent_catches(self, st: Stall) -> list[dict]:
        """Public catch notices: catches at stalls within earshot of this one in the
        last L = close_ticks ticks (ticks_ago 1..L), oldest first."""
        L, out = self.cfg.pricing.close_ticks, []
        for tc, cst in self.catch_ticks:
            ago = self.t - tc
            if 1 <= ago <= L:
                d = _dist(cst.pos, st.pos)
                if d <= self.cfg.market.earshot:
                    out.append({"distance": round(d, 3), "ticks_ago": ago})
        return out

    def is_reachable(self, p: Person) -> bool:
        """Does this buyer's route pass within interact_range of a stall of its category?"""
        r = self.cfg.market.interact_range
        own = [st.pos for st in self.stalls if st.category == p.task["category"]]
        return any(_dist(c, s) <= r for c in p.route for s in own)

    def seller_obs(self, st: Stall, near: list, askers: list) -> dict:
        mk = self.cfg.market
        obs = {
            "role": "seller", "tick": self.t,
            "stall": {"id": st.sid, "category": st.category, "brand": st.brand, "stall_type": st.stype,
                      "true_quality": st.q_true, "pitch_quality": st.q_pitch,
                      "truth_text": self.message_text(st, st.q_true),
                      "pitch_text": self.message_text(st, st.q_pitch),
                      "price_cents": st.price_cents, "unit_cost_cents": st.unit_cost_cents, "sign": st.sign,
                      "reopened_at_tick": st.closed_until if st.catches else None},
            "costs": {"yell_cents": st.yell_cost_cents, "whisper_cents": st.whisper_cost_cents,
                      "penalty_cents_if_caught": st.penalty_cents, "closure_ticks": self.cfg.pricing.close_ticks},
            "ranges": {"earshot": mk.earshot, "whisper_range": mk.whisper_range,
                       **({} if mk.whispers_allowed else {"whispers_allowed": False})},
            "passersby": [{"id": p.pid, "observed_profile": self.observed_profile(st, p), "distance": round(d, 3),
                           "uniform": p.uniform and d <= self.recognition_range}
                          for p, d in near],
            "recent_catches": self.recent_catches(st),
            "asks": [{"id": pid} for pid in askers],
            "ledger": {"revenue_cents": st.revenue_cents, "units_sold": st.units_sold,
                       "ad_spend_cents": st.ad_spend_cents, "penalties_cents": st.penalties_cents,
                       "catches": st.catches},
        }
        if self.brands_on:
            honest = st.stype == "genuine" and st.busted_day is None
            obs["brand"] = {"name": st.brand, "counterfeit_of": st.counterfeit_of, "rating": st.rating,
                            "neutral_price_cents": B.neutral_price(self.cfg, st),
                            "rename_available": st.rename_pending,
                            "first_decision_today": not st.decided_today, "busted_day": st.busted_day,
                            "bust_out_unit_cost_cents": (B.unit_cost(self.cfg, st, B.bust_quality(self.cfg, st))
                                                         if honest else None)}
        if mk.horizon_known:
            obs["horizon"] = {"day": self.day, "days": int(mk.days)}
            obs["yesterday"] = st.yesterday
        if self.brands_on and self.seller_privileged.get(st.sid):
            # Benchmark-only inputs (0.9.0), labelled as such: not something a real seller knows.
            obs["privileged"] = {"note": "privileged benchmark input, not observable by a real seller",
                                 "deceptive_catch_rate_yesterday": self.book.catch_rate_yesterday,
                                 "premium": float(self.cfg.brands.premium),
                                 "rating_memory": float(self.cfg.ratings.memory),
                                 "ticks_per_day": int(mk.ticks), "close_ticks": int(self.cfg.pricing.close_ticks)}
        return obs

    def buyer_obs(self, p: Person, here: list[Stall], left: int, need: int, privileged: bool) -> dict:
        task = p.task
        stalls = []
        for st in here:
            info = p.info.get(st.sid, {"claims": [], "inspected_q": None})
            row = {"id": st.sid, "brand": self.perceived_brand(st, p), "category": st.category,
                   "price_cents": st.price_cents,
                   "messages": info["claims"], "inspected_quality": info["inspected_q"],
                   "ask_pending": p.pid in self.pending_asks.get(st.sid, [])}
            if self.knows_quality(p):
                # Reliable quality information from the buyer's own expertise. Only
                # inspector-buyers with buyers.inspector_knowledge on get this field.
                row["own_assessment"] = st.q_true
            if self.cfg.ratings.mode == "public" and p.profile in self.cfg.ratings.visible_to:
                row["rating"] = st.rating
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

    def search_obs(self, p: Person, here: list[Stall], phase: str, route_end: bool) -> dict:
        """What a searching buyer remembers: every stall of its category it has seen and is not
        at now (except chosen stalls it found closed), with what it learned (the stall's current price and, if visible, rating) and how
        many route steps back it is."""
        ids = {st.sid for st in here}
        rows = []
        for sid, idx in p.seen.items():
            if sid in ids or sid in p.skipped:
                continue
            st = self.by_sid[sid]
            info = p.info.get(sid, {"claims": [], "inspected_q": None})
            row = {"id": sid, "brand": self.perceived_brand(st, p), "price_cents": st.price_cents,
                   "messages": info["claims"], "inspected_quality": info["inspected_q"],
                   "steps_away": abs(p.step - idx)}
            if self.knows_quality(p):
                row["own_assessment"] = st.q_true
            if self.cfg.ratings.mode == "public" and p.profile in self.cfg.ratings.visible_to:
                row["rating"] = st.rating
            rows.append(row)
        return {"depth": p.search_k, "seen_count": len(p.seen), "phase": phase, "route_end": route_end,
                "seen_elsewhere": rows}

    def route_ahead(self, p: Person) -> list[dict]:
        seen, out = set(), []
        r = self.cfg.market.interact_range
        for cell in p.route[p.step + 1:]:
            for st in self.stalls:
                if st.category == p.task["category"] and st.sid not in seen and _dist(cell, st.pos) <= r \
                        and self.considers(p, st):
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
            if self.switch_costs_on:
                d["switch_cost_cents"] = d.get("switch_cost_cents", 0) + st.switch_cost_cents
        for d in by_type.values():
            d["profit_cents"] = (d["revenue_cents"] - d["cost_cents"] - d["ad_spend_cents"] - d["penalties_cents"]
                                 - d.get("switch_cost_cents", 0))
            d["profit_per_stall_cents"] = d["profit_cents"] / d["stalls"]
        reach = [p for p in arrived if self.is_reachable(p)]
        r_surplus = [p.value - p.paid_cents - p.inspect_spent_cents for p in reach]
        reachable = {
            "share": len(reach) / len(arrived) if arrived else None,
            "buyers": len(reach),
            "task_complete_share": (sum(p.q_units >= p.task["units"] for p in reach) / len(reach)) if reach else None,
            "buyer_surplus_mean_cents": float(np.mean(r_surplus)) if r_surplus else None,
        }
        fc_msgs = sum(v["messages"] for v in self.false_claims_by_stall.values())
        fc_free = sum(v["no_eligible_in_earshot"] for v in self.false_claims_by_stall.values())
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
            "reachable": reachable,
            "false_claim_impressions": imp["false"],
            "false_claim_impressions_to_uniform_eligible": self.false_impressions_to_eligible,
            "false_claims": {"messages": fc_msgs, "no_eligible_in_earshot": fc_free},
            "false_claims_by_stall": {k: dict(v) for k, v in self.false_claims_by_stall.items()},
            **({"brands": self.brand_outcome()} if self.brands_on else {}),
            **({"demand": self.demand_outcome()} if self.choice_set else {}),
            **({"search": self.search_outcome()} if self.search_log else {}),
            **self.stuck_guard(),
            "liability": self.liability_outcome(),
        }

    def close_day(self) -> None:
        """End of the day (0.15.0): stalls that chose to exit leave the market; their fines not yet
        due are uncollectible (logged in the outcome, never charged)."""
        for st in self.stalls:
            if st.exit_pending and st.exited_day is None:
                st.exited_day, st.exit_pending = self.day, False
                self.fines["uncollectible"] += [(st.sid, f["cents"]) for f in st.fines_pending]
                st.fines_pending = []

    def liability_outcome(self) -> dict:
        """Fines and enforcement intensity today (0.15.0). charged: fines charged in today's accounts
        (today's catches at lag 0, earlier catches falling due today otherwise); deferred: today's
        catches whose fine falls due later; uncollectible: fines not yet due of stalls that left the
        market at the end of today; outstanding: fines not yet due of stalls still in the market.
        Catches per deceptive stall: catches at deceptive-type stalls / deceptive stalls (busted
        genuine stalls are not deceptive-type)."""
        f = self.fines
        by: dict = {}
        for k in ("charged", "deferred", "uncollectible"):
            for sid, c in f[k]:
                d = by.setdefault(sid, {"charged_cents": 0, "deferred_cents": 0, "uncollectible_cents": 0})
                d[f"{k}_cents"] += c
        dec = [st for st in self.stalls if st.stype == "deceptive" and st.exited_day in (None, self.day)]
        n_c = sum(st.catches for st in dec)
        pend = [x for st in self.stalls for x in st.fines_pending]
        return {"fines_charged": len(f["charged"]), "fines_charged_cents": sum(c for _, c in f["charged"]),
                "fines_deferred": len(f["deferred"]), "fines_deferred_cents": sum(c for _, c in f["deferred"]),
                "fines_uncollectible": len(f["uncollectible"]),
                "fines_uncollectible_cents": sum(c for _, c in f["uncollectible"]),
                "fines_outstanding": len(pend), "fines_outstanding_cents": sum(x["cents"] for x in pend),
                "by_stall": dict(sorted(by.items())),
                "exits": sorted(st.sid for st in self.stalls if st.exited_day == self.day),
                "deceptive_stalls": len(dec), "deceptive_catches": n_c,
                "catches_per_deceptive_stall": n_c / len(dec) if dec else None}

    def stuck_guard(self) -> dict:
        """End-of-day stuck-buyer guard (0.14.0), an observer only. stuck_buyers: buyers still in the
        market within reach of the open stall they chose (p.target), with units still needed and
        budget for one unit there. idle_choosers: searching buyers still in the market in the
        "choose" phase with units still needed and an open, affordable stall of their consideration
        set (their category) within reach, which they did not buy from."""
        stuck = idle = 0
        r = self.cfg.market.interact_range
        for p in self.buyers:
            if not p.active or p.done or p.units >= p.task["units"]:
                continue
            left = p.task["budget_cents"] - p.paid_cents - p.inspect_spent_cents
            if p.target is not None:
                tst = self.by_sid[p.target]
                if self.is_open(tst) and _dist(p.pos, tst.pos) <= r and tst.price_cents <= left:
                    stuck += 1
            if p.search_k > 1 and (p.choosing or len(p.seen) >= p.search_k or p.step >= len(p.route) - 1):
                if any(st.category == p.task["category"] and self.considers(p, st) and self.is_open(st)
                       and st.price_cents <= left for st in self.reach(p.pos)):
                    idle += 1
        return {"stuck_buyers": stuck, "idle_choosers": idle}

    def search_outcome(self) -> dict:
        exp = {st.sid: {"in_reach": len(self.exposure.get(st.sid, {}).get("in_reach", ())),
                        "in_reach_shopping": len(self.exposure.get(st.sid, {}).get("in_reach_shopping", ()))}
               for st in self.stalls}
        return {"buyers": {p.pid: p.search_rec for p in self.buyers}, "exposure": exp}

    def demand_outcome(self) -> dict:
        """choice_set demand (0.12.0): per stall, how many of the day's buyers had it in their
        consideration set, and how many distinct buyers bought from it."""
        inc = {st.sid: 0 for st in self.stalls}
        for p in self.buyers:
            for sid in p.consider:
                inc[sid] += 1
        cust = {st.sid: set() for st in self.stalls}
        for b in self.purchases:
            cust[b["stall"]].add(b["buyer"])
        return {"inclusion": inc, "customers": {k: len(v) for k, v in cust.items()}}

    def brand_outcome(self) -> dict:
        prof = {st.sid: st.revenue_cents - st.cost_cents - st.ad_spend_cents - st.penalties_cents
                - st.switch_cost_cents for st in self.stalls}
        return {"renames": len(self.rename_log),
                "renames_by_how": {h: sum(r["how"] == h for r in self.rename_log) for h in ("fresh", "counterfeit")},
                "bust_outs": len(self.bust_log),
                "busted_stalls": sum(st.busted_day is not None for st in self.stalls),
                "counterfeit_stalls": sum(st.counterfeit_of is not None for st in self.stalls),
                "profit_by_stall_cents": prof,
                "units_by_stall": {st.sid: st.units_sold for st in self.stalls}}


def run(cfg: BazaarConfig, log: JsonlLog | None = None, agent_factory: AgentFactory | None = None,
        day_factories: Callable[[int], AgentFactory | None] | None = None) -> dict:
    """One run; with market.days > 1, the multi-day run (engine/days.py), whose result is
    {"days": [...]}. day_factories(day) gives a day's agent factory (replay)."""
    if cfg.market.days > 1:
        from .days import run_days
        return run_days(cfg, log=log, day_factories=day_factories)
    eng = BazaarEngine(cfg, log=log, agent_factory=agent_factory)
    return eng.run()
