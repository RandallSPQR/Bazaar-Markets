"""Run configuration.

Two modes:
  * "m0"     - the prototype's unit-square ad-auction model (port of sim.py).
  * "bazaar" - the hawkers' bazaar world.

Fields marked PLACEHOLDER are defaults that still need a research decision;
see docs/config_reference.md. Configs load from JSON and accept dotted
overrides such as `detection.form=step` or `inspectors.count=12`.
"""
from __future__ import annotations

import copy
import dataclasses
import json
from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- M0

@dataclass
class M0Config:
    mode: str = "m0"
    seed: int = 0
    n_cust: int = 1000
    n_adv: int = 100
    f_enf: float = 0.05
    r_min: float = 0.02
    r_max: float = 0.7
    d_sale: float = 0.1
    m: float = 1.0
    delta: float = 0.2
    P: float = 5.0
    gens: int = 250
    T: int | None = None          # impressions per generation; None -> 20 * n_adv
    keep: float = 0.2
    flip: float = 0.02
    cap_mult: float = 3.0
    # "fixed": enforcer status is a fixed property of each customer (sim.py).
    # "redraw": enforcer status is drawn fresh for every impression at rate f_enf
    #           (mechanism test; reconstructed - tighten.py was not available).
    enforcer_mode: str = "fixed"
    #   "redraw_main": as "redraw", but the draws come from the main stream right after
    #           the impression draw, exactly as tests/reference/tighten_v1.py did. Use it
    #           only to reproduce the doc's mechanism-test numbers bit for bit.
    # Selection rule (which firms are replaced each generation):
    #   "idle_lowest"  : firms that won nothing rank below every active firm, loss-makers
    #                    included (prototype v1; every result in the research doc).
    #   "prototype_v0" : idle firms get fitness -1e-9, so they still outrank loss-makers
    #                    (original sim.py). Historical compatibility only.
    selection: str = "idle_lowest"
    # Impression capacity (not a money budget): each advertiser may win at most
    # int(cap_mult * T / n_adv) impressions per generation.
    #   "batch"  : eligibility is checked once per batch of T/40 impressions, so a seller
    #              can overshoot within a batch (soft limit; both prototypes).
    #   "strict" : enforced per impression; overflow impressions go to the next-highest
    #              eligible bidder.
    cap_mode: str = "batch"
    # Tie-breaking when ranking firms for selection (idle firms all tie):
    #   "stable"        : stable sort; identical results on every platform (default).
    #   "numpy_default" : np.argsort's default, as both prototypes used. Its tie order
    #                     varies with numpy version and CPU, so exact prototype
    #                     agreement holds only on the same platform.
    tie_break: str = "stable"
    summary_last: int = 30        # generations averaged for the headline number


# ----------------------------------------------------------------------- Bazaar

@dataclass
class MarketCfg:
    categories: list[str] = field(default_factory=lambda: ["fish", "electronics", "designer"])
    slots_per_side: int = 8       # stalls on each side of an aisle; one aisle per category
    slot_spacing: int = 2         # grid cells between neighbouring stalls
    clustering: float = 1.0       # 0 = similar sellers scattered, 1 = one aisle per category
    ticks: int = 240
    sight_range: float = 3.0      # signs are seen within this distance
    earshot: float = 4.0          # yells are heard within this distance
    whisper_range: float = 2.0    # a whisper target must be within this distance
    interact_range: float = 1.0   # ask / inspect / buy require a stall within this distance
    max_actions_per_stop: int = 4 # stall actions a buyer may take before being moved on
    # Grid refinement: at scale k a cell is 1/k real units and a tick 1/k real units long.
    # Every other distance and time value in the config stays in real units (k = 1 cells
    # and ticks); the engine converts them. See engine/scaling.py and docs/config_reference.md.
    scale: int = 1
    # Number of days. Each day is a full bazaar run with a fresh buyer population; between
    # days genuine and deceptive stalls may switch type (see `evolution`, engine/days.py).
    days: int = 1
    # Medium restriction: when false, sellers can use only signs, yells and answers (a public
    # medium). Sellers are told (ranges.whispers_allowed = false) and a whisper is an invalid action.
    whispers_allowed: bool = True


@dataclass
class StallsCfg:
    type_shares: dict = field(default_factory=lambda: {"genuine": 0.4, "seconds": 0.3, "deceptive": 0.3})
    q_high: list = field(default_factory=lambda: [0.70, 0.95])   # genuine true Q; deceptive claimed Q
    q_low: list = field(default_factory=lambda: [0.15, 0.45])    # seconds and deceptive true Q
    deceptive_sign: str = "pitch"  # what a deceptive stall's sign shows: "pitch" | "truth" | "none"


@dataclass
class PricingCfg:
    # Engine-set prices, in integer cents. Price depends on the *posted* tier, not true Q.
    base_price_cents: dict = field(default_factory=lambda: {"fish": 800, "electronics": 4000, "designer": 12000})
    seconds_price_factor: float = 0.55   # honest seconds are posted (and priced) as seconds
    deceptive_price_factor: float = 1.0  # deceptive stalls price like genuine; <1 = "bargain" fakes
    unit_cost: list = field(default_factory=lambda: [0.30, 0.50])  # cost = base * (c0 + c1 * Q_true)
    yell_cost_frac: float = 0.002        # ad spend per yell, as a fraction of base price
    whisper_cost_frac: float = 0.004     # ad spend per whisper
    penalty_mult: float = 1.5            # penalty P = penalty_mult * base (~5x genuine margin, as in M0)
    close_ticks: int = 40                # stall closed for this long after a catch
    # Switching costs (multi-day runs): charged once, as a fraction of base price, in the stall's
    # accounts on its first day in the new type.
    switch_cost_to_genuine: float = 0.0
    switch_cost_to_deceptive: float = 0.0


@dataclass
class BuyersCfg:
    count: int = 150
    profile_shares: dict = field(default_factory=lambda: {"tourist": 0.4, "local": 0.4, "expert": 0.2})
    units: list = field(default_factory=lambda: [1, 2])           # units needed, uniform integer range
    q_req: list = field(default_factory=lambda: [0.50, 0.70])     # kept <= q_high[0]: see docs
    budget_level: str = "at"     # "above" | "at" | "below" | "mixed": budget vs genuine price at Q_req
    budget_factors: dict = field(default_factory=lambda: {"above": 1.25, "at": 1.0, "below": 0.8})
    inspect_cost_frac: dict = field(default_factory=lambda: {"tourist": 0.10, "local": 0.05, "expert": 0.02})
    aisles_per_route: list = field(default_factory=lambda: [1, 3])
    profile_noise: float = 0.3   # chance a seller sees a uniformly random profile instead of the true one
    inspector_fraction: float = 0.0  # share of buyers who are also inspectors ("inspector-buyers")
    # What an inspector-buyer has. Knowledge and enforcement are separate switches so
    # they can be tested apart:
    #   knowledge   : reliable quality information about each stall it reaches
    #                 (obs field "own_assessment"), which its purchasing policy can use;
    #   enforcement : perceiving a false claim can trigger a catch.
    # Both on = a well-informed buyer who also reports; enforcement only = an automatic
    # auditor with ordinary shopping; knowledge only = an expert shopper who never reports.
    inspector_knowledge: bool = True
    inspector_enforcement: bool = True


@dataclass
class InspectorsCfg:
    count: int = 2
    placement: str = "posts"       # "posts" | "clustered" | "patrolling" | "disguised"
    disguised_ask_prob: float = 0.3
    # PLACEHOLDER (default 0): correlation between being an inspector and showing
    # as "expert". 0 = inspectors' observable profiles are drawn from the buyer
    # distribution (no pockets in feature space); 1 = every inspector shows as expert.
    feature_correlation: float = 0.0
    # Uniformed inspectors: when true, inspectors on posts, clustered or patrolling
    # placement wear a visible uniform (sellers see "uniform": true on their passerby
    # row). Disguised inspectors are never uniformed.
    uniformed: bool = False
    # How far away a seller can recognize a uniform, in grid units. null = market.earshot
    # (every uniformed inspector in earshot is recognized; engine 0.3.0 behaviour).
    # Uniformed inspectors farther away show "uniform": false, like any passer-by.
    recognition_range: float | None = None
    # Disguised inspectors' presence: "single_trip" (one buyer-like route, then leave;
    # 0.3.0 behaviour) or "full_shift" (present from t=0 to the end, walking random
    # routes back to back, so active ticks = count x ticks, as for posts and patrols).
    disguised_shift: str = "single_trip"


@dataclass
class DetectionCfg:
    # PLACEHOLDER (default "graded"): p = w_channel * proximity(d) * min(1, falsity / f_scale)
    form: str = "graded"           # "graded" | "step" | "hazard"
    # How detection depends on distance for broadcast channels (sign, yell).
    #   "linear": proximity = 1 - d / range (default); private channels always 1.
    #   "flat"  : proximity = 1 for every channel. With equal channel weights this is the
    #             equal-detection-given-exposure condition (configs/detection_equal.json):
    #             channels then differ only in who perceives them.
    proximity: str = "linear"
    channel_weight: dict = field(default_factory=lambda: {"whisper": 1.0, "answer": 1.0, "yell": 0.6, "sign": 0.4})
    f_scale: float = 0.3           # graded: falsity at which detection saturates
    hazard_k: float = 6.0          # hazard: p = 1 - exp(-k * falsity * w * exp(-d / lam))
    hazard_lam: float = 2.0


@dataclass
class ValuationCfg:
    # PLACEHOLDER (default "step_salvage"): per-unit V = V_req if Q >= Q_req,
    # else salvage * V_req * Q / Q_req.  V_req = value_mult * base price.
    form: str = "step_salvage"     # "step_salvage" | "linear" | "concave"
    value_mult: float = 1.3
    salvage: float = 0.5


@dataclass
class AgentsCfg:
    # Policy names resolve through agents.registry.
    seller: dict = field(default_factory=lambda: {"genuine": "rule_honest", "seconds": "rule_honest",
                                                  "deceptive": "rule_deceptive"})
    buyer: str = "rule_buyer"
    params: dict = field(default_factory=dict)  # per-policy keyword arguments


@dataclass
class EvolutionCfg:
    # Between-day type revision (market.days > 1 only): pairwise proportional imitation.
    revise_prob: float = 0.2     # chance a genuine/deceptive stall compares itself with a partner
    mutation_prob: float = 0.02  # chance a genuine/deceptive stall flips type anyway
    # Switching costs: pricing.switch_cost_to_genuine / switch_cost_to_deceptive (default 0).


@dataclass
class RatingsCfg:
    # Public stall ratings (multi-day runs). A rating is updated at the end of each day from that
    # day's purchases: the share of units whose true Q met the latest claim the stall made to the
    # buyer before the sale, blended with yesterday's rating (memory). A first rating is that day's
    # share; a day with no claimed units leaves the rating unchanged. Ratings persist across days
    # and type switches.
    #   "off"    : not computed (default; engine 0.6.0 behaviour)
    #   "hidden" : computed and logged, shown to no one (a control that counts rugpulls)
    #   "public" : buyers whose profile is in visible_to see each stall's rating ("rating" on
    #              their stalls_here rows; null = unrated)
    mode: str = "off"
    memory: float = 0.7            # PLACEHOLDER (lambda)
    tau: float = 0.5               # PLACEHOLDER: the rule buyer skips stalls rated below this
    visible_to: list = field(default_factory=lambda: ["expert", "local"])
    rugpull_threshold: float = 0.8 # genuine -> deceptive while rated >= this is logged as a rugpull


@dataclass
class BazaarConfig:
    mode: str = "bazaar"
    seed: int = 0
    market: MarketCfg = field(default_factory=MarketCfg)
    stalls: StallsCfg = field(default_factory=StallsCfg)
    pricing: PricingCfg = field(default_factory=PricingCfg)
    buyers: BuyersCfg = field(default_factory=BuyersCfg)
    inspectors: InspectorsCfg = field(default_factory=InspectorsCfg)
    detection: DetectionCfg = field(default_factory=DetectionCfg)
    valuation: ValuationCfg = field(default_factory=ValuationCfg)
    agents: AgentsCfg = field(default_factory=AgentsCfg)
    evolution: EvolutionCfg = field(default_factory=EvolutionCfg)
    ratings: RatingsCfg = field(default_factory=RatingsCfg)


PLACEHOLDERS = {
    "detection.form": "graded (chosen as placeholder 2026-11-03)",
    "inspectors.feature_correlation": "0.0 (chosen as placeholder 2026-11-03)",
    "valuation.form": "step_salvage (chosen as placeholder 2026-11-03)",
    "ratings.memory": "0.7 (placeholder 2026-11-05)",
    "ratings.tau": "0.5 (placeholder 2026-11-05)",
}


# ---------------------------------------------------------------- load / dump

def to_dict(cfg) -> dict:
    return dataclasses.asdict(cfg)


def _from_dict(cls, d: dict):
    kwargs = {}
    known = {f.name: f for f in dataclasses.fields(cls)}
    for k, v in d.items():
        if k not in known:
            raise KeyError(f"unknown config key {cls.__name__}.{k}")
        sub = _SUBSECTIONS.get((cls, k))
        kwargs[k] = _from_dict(sub, v) if sub is not None else copy.deepcopy(v)
    return cls(**kwargs)


_SUBSECTIONS = {(BazaarConfig, "market"): MarketCfg, (BazaarConfig, "stalls"): StallsCfg,
                (BazaarConfig, "pricing"): PricingCfg, (BazaarConfig, "buyers"): BuyersCfg,
                (BazaarConfig, "inspectors"): InspectorsCfg, (BazaarConfig, "detection"): DetectionCfg,
                (BazaarConfig, "valuation"): ValuationCfg, (BazaarConfig, "agents"): AgentsCfg,
                (BazaarConfig, "evolution"): EvolutionCfg, (BazaarConfig, "ratings"): RatingsCfg}


def from_dict(d: dict):
    mode = d.get("mode", "bazaar")
    if mode == "m0":
        return _from_dict(M0Config, d)
    if mode == "bazaar":
        return _from_dict(BazaarConfig, d)
    raise ValueError(f"unknown mode {mode!r}")


def _parse_value(s: str) -> Any:
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return s


def apply_overrides(d: dict, overrides: list[str]) -> dict:
    """Apply `a.b.c=value` overrides to a config dict (values parsed as JSON when possible)."""
    d = copy.deepcopy(d)
    for ov in overrides or []:
        key, _, val = ov.partition("=")
        parts = key.strip().split(".")
        node = d
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = _parse_value(val)
    return d


def load(path: str | None = None, overrides: list[str] | None = None, mode: str | None = None):
    d: dict = {}
    if path:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    if mode:
        d.setdefault("mode", mode)
    d = apply_overrides(d, overrides or [])
    # Fill defaults, then re-apply so partial nested sections merge with defaults.
    base = to_dict(from_dict({"mode": d.get("mode", "bazaar")}))
    return from_dict(_deep_merge(base, d))


def _deep_merge(a: dict, b: dict) -> dict:
    out = copy.deepcopy(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k not in _OPAQUE_DICTS:
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


# Dict-valued fields that are replaced wholesale rather than merged key by key
# (a partial share table should not silently keep default categories).
_OPAQUE_DICTS = {"type_shares", "profile_shares"}
