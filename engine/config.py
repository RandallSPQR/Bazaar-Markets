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
    # Known horizon (engine 0.8.0): sellers' observations carry the day number and market.days
    # ("horizon") and their own previous day's ledger ("yesterday").
    horizon_known: bool = False


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
    # Penalty lag (engine 0.15.0), in days. 0 = the fine is charged at the catch (0.14.0). L > 0: a
    # catch still closes the stall at once, but its fine falls due L days later and is charged in the
    # stall's accounts that day; a fine falling due after the stall has exited is uncollectible
    # (logged, never charged); one falling due after the last day is outstanding at close.
    penalty_lag_days: int = 0
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
    # Budget as a dial (engine 0.9.0): when set, every buyer's budget = units x base x this factor,
    # whatever budget_level says (the "mixed" draws are still consumed). null = off (0.8.0).
    budget_factor_override: float | None = None
    # Search depth (engine 0.10.0), per profile. A buyer with depth k > 1 browses: it collects what
    # it learns at open stalls of its category within reach (asking and inspecting as it goes) and
    # may buy only once it has seen k of them or reached the end of its route; it then buys here or
    # walks back along its route to a stall it saw (seller action 'choose'). k = 1 is the 0.9.0
    # behaviour, byte for byte. See engine/bazaar.py and docs/config_reference.md.
    search_depth: dict = field(default_factory=lambda: {"tourist": 1, "local": 1, "expert": 1})
    # Diagnostics (0.10.0): add a `search` block to the outcome (per buyer: stalls seen, choices,
    # walking ticks; per stall: buyers of its category that came within reach). Off = 0.9.0 bytes.
    search_log: bool = False
    # Tie-break (engine 0.20.0) when a rule buyer ranks stalls to buy from: "stall_id" (default) = 0.19.0, ties on
    # (visible rating, price) go to the lower stall id. "random": each buyer gets, per day, a random order of the
    # stalls from default_rng([seed, 29, day, buyer index]) (stall rows carry "tie_rank"), used in place of the id.
    tie_break: str = "stall_id"
    # Profile overrides (engine 0.21.0; default {} = 0.20.0 bytes). Per profile ("tourist", "local", "expert") or
    # "bargain" (bargain hunters, whatever their profile; their keys win over their profile's), optional:
    #   reads_ratings (bool): whether the buyer sees ratings (stall rows carry "rating"), replacing
    #     `ratings.visible_to` for it. False: it ranks candidates as a tourist does (lowest price) and never sees
    #     ratings. True: it sees them (ratings.mode "public" only).
    #   inspect_prob (0-1): the probability it inspects before buying, replacing the profile's default (the
    #     rule_buyer local_inspect_prob / expert_inspect_prob params). Locals and tourists inspect an advertising
    #     (yelling or whispering) stall; experts any stall before buying. Given to the buyer as you.inspect_prob.
    # Unset means current behaviour. Nothing else changes (budgets, Q_req, search, inspection cost, what sellers see).
    profile_overrides: dict = field(default_factory=dict)
    # Bargain hunters (engine 0.11.0; default 0 = off, 0.10.0 bytes): this share of buyers draw
    # Q_req from bargain_q_req instead of q_req. Two draws per buyer from the dedicated stream
    # [day root, 16], consumed only when the share is > 0, so nothing else shifts.
    # null (default) = the demand mode's default: 0 in "walk" (0.10.0 bytes), 0.2 in "choice_set".
    bargain_share: float | None = None
    bargain_q_req: list = field(default_factory=lambda: [0.30, 0.45])
    # Demand (engine 0.12.0). "walk" (default) = 0.11.0 bytes: a buyer considers the stalls of its
    # category that its random route passes. "choice_set": each buyer draws a consideration set of
    # `consider` stalls of its category from all of them, without replacement, with weight
    # exp(-position_rent x position rank), position rank = the stall's order of distance from the
    # buyer's entrance (0 = nearest; stalls facing each other share a rank). The entrance is one end
    # of the category's aisle, drawn with the set from the dedicated stream [day root, 18, buyer
    # index]. The buyer walks that aisle end to end from its entrance (so it passes every set member
    # in walking order, hears yells and whispers and meets inspectors on the way) and chooses among
    # its set only, with the search rule at depth = consider (buyers.search_depth is not used).
    # Needs market.clustering = 1 (one aisle per category).
    demand_mode: str = "walk"
    consider: int = 3
    position_rent: float = 0.0
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
    # Buyer choice (engine 1.1.0). "lexicographic" (default, 1.0.0 bytes): a searching buyer picks, among its
    # candidates (stalls it believes meet Q_req, that pass the rating threshold and fit its budget), the highest
    # displayed rating, then the lowest price, then the tie-break. "logit": it picks candidate j with probability
    # proportional to exp(w_r x displayed rating_j - w_p x price_j / base price), unrated = 0.5, with
    # w_r = logit_rating_weight for a buyer whose rows carry ratings and 0 for one whose rows do not (tourists, and
    # buyers.profile_overrides reads_ratings false), w_p = logit_price_weight. The draw is one uniform per buyer and
    # day from default_rng([seed, 37, day, buyer index]), reused for every choice that day (so a buyer walking to
    # its choice picks it again on arrival), by inverse CDF over the candidates in their lexicographic order.
    # Inspection, asking and the Q_req rule are unchanged: logit replaces only the ranking. Named settings:
    # soft (5, 5) and sharp (20, 20), both PLACEHOLDER.
    choice: str = "lexicographic"
    logit_rating_weight: float = 5.0
    logit_price_weight: float = 5.0


@dataclass
class SellersCfg:
    # Price policy (engine 1.1.0), market-wide; brands.enabled only, applied every morning (and at a rename) to
    # every stall's own price, before the copy rules (a counterfeit takes counterfeit_price_factor x the holder's
    # price, an owner-branded licensee its owner's price). "rating_indexed" (default, 1.0.0 bytes): base x tier x
    # (1 + premium x (displayed rating - 0.5)). "cost_plus": round(unit cost x (1 + markup)). "match_rival":
    # the median of yesterday's posted prices of the other same-category stalls still in the market whose
    # displayed rating is at least the stall's own - 0.1 (unrated = 0.5; median of an even count = the mean of
    # the middle two, rounded half up), else rating_indexed. "undercut": the lowest of yesterday's posted prices of
    # the other same-category stalls still in the market with an equal or higher displayed rating, minus 1 cent,
    # floored at the stall's unit cost, else rating_indexed. "promo": rating_indexed, 15% off (rounded half up)
    # on a day after the stall's units sold yesterday fell below the mean of its units over the last 7 days
    # (fewer at the start), yesterday included. Day 1 has no yesterday: match_rival, undercut and promo post
    # rating_indexed.
    price_policy: str = "rating_indexed"
    markup: float = 0.5


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
    # Capture (engine 0.11.0; needs brands.enabled). Each dedicated inspector j is tied to each
    # genuine-origin brand (a brand on a genuine stall on day 1) with probability `capture`, drawn
    # once per run from [seed, 15]. A tied inspector's catch probability for a stall bearing that
    # brand is multiplied by (1 - capture_effect). 0 = off (0.10.0 bytes).
    capture: float = 0.0
    capture_effect: float = 0.8    # PLACEHOLDER
    # Enforcement intensity (engine 0.15.0): multiplies every catch probability (dedicated
    # inspectors and inspector-buyers). 1.0 = 0.14.0; 0 = inspectors present but never catch. The
    # detection draw is consumed whenever the unscaled probability is > 0, so levels share draws.
    detect_scale: float = 1.0


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
    # Engine 0.18.0, rating speed (brands on, ratings not off). Every brand starts with prior_n pseudo-reviews
    # at 0.5: on a day with rated units, share = (honest + 0.5 w) / (rated + w), then the blend above; w starts
    # at prior_n when the brand is created and is multiplied by `memory` at every day end. 0 = 0.17.0.
    prior_n: float = 0.0
    # Engine 0.19.0: which brands get the prior. "all" (default) = 0.18.0. "new": only brands created on day 2 or
    # later (white labels, fresh or counterfeit names at reopening, counterfeit entry); brands that exist on day 1
    # (every original stall's name, and any name taken on day 1) rate as with prior_n 0.
    prior_scope: str = "all"
    # Engine 0.20.0: what market participants see. "exact" (default) = 0.19.0, the unrounded rating. "stars": every
    # rating a buyer, a price or a seller decision reads is rounded half up to the nearest display_step (0.02 = a
    # tenth of a star on a five-star scale); unrated stays unrated (0.5). The stored rating keeps updating unrounded
    # and is what the logs report. Readers: buyers' stall rows (ranking and the tau threshold), the posted price
    # (premium formula; licensees and counterfeits copy it), the seller observation's brand.rating (read by the
    # rule_genuine_rational benchmarks), and counterfeit target choice (reopening and counterfeit entry).
    display: str = "exact"
    display_step: float = 0.02


@dataclass
class BrandsCfg:
    # Brands (engine 0.8.0; see engine/brands.py). When enabled: ratings attach to brand names,
    # a stall may rename itself when it reopens after a closure ("fresh" or "counterfeit"; 0.9.0
    # renamed "lookalike", still accepted), tourists cannot tell a counterfeit from its original (they see and review the original's
    # name), and prices carry a reputation premium. Off by default (0.7.0 behaviour).
    enabled: bool = False
    # PLACEHOLDER (0.4 in the 2026-11-06 run): price = base x tier x (1 + premium x (rating - 0.5)),
    # rating = the brand's start-of-day rating, 0.5 if unrated. 0 = no premium.
    premium: float = 0.0
    # Counterfeit entry (engine 0.17.0). "reopen" (default): a stall can take a counterfeit name only when
    # it reopens after a closure (seller action rename, as before). "day": at the start of day
    # counterfeit_day every deceptive stall copies the name of the top-rated genuine brand of its category
    # (ratings at the end of the previous day, unrated = 0.5; ties and name edits drawn from
    # default_rng([seed, 23])), claims that brand's true quality, keeps the name to the last day and is
    # never offered a rename.
    counterfeit_entry: str = "reopen"
    counterfeit_day: int = 2
    # A counterfeit posts round(counterfeit_price_factor x the original's posted price) each day (both entry
    # modes). Claims are unchanged by the price: a day-entry counterfeit claims the original's true quality (set
    # at entry); one made by renaming at reopening keeps its own pitched quality. Unit cost is unchanged. 1.0 = the
    # original's price.
    counterfeit_price_factor: float = 1.0


@dataclass
class CriticsCfg:
    # Critics (engine 0.11.0; needs brands.enabled and ratings.mode != "off"; count 0 = off,
    # 0.10.0 bytes). At the end of each day each critic visits `sample` stalls (without
    # replacement, from [day root, 13, critic]), observes true Q, and writes a review: positive
    # when true Q meets the stall's posted claim (its sign: "pitch" -> Q_pitch, "truth" -> Q_true;
    # no review of a stall with no sign), negative otherwise (decided 2026-11-07). A filed review
    # enters that day's rating update of the stall's brand as `weight` rated units. Positive
    # reviews are filed the day they are written. A negative review is held for
    #   max(tie_delay if the (critic, brand) pair is tied else 0,
    #       round_half_up(emb_max x p) if embarrassment else 0)
    # days, p = the share of that critic's earlier reviews of the brand that were positive (0 with
    # none). Ties: round_half_up(tie_share x pairs) of the (critic, genuine-origin brand) pairs,
    # drawn once per run from [seed, 14]. A review due after the last day is never filed.
    count: int = 0                 # PLACEHOLDER
    sample: int = 6                # PLACEHOLDER
    weight: float = 5.0            # PLACEHOLDER
    tie_share: float = 0.0
    tie_delay: int = 10            # PLACEHOLDER
    embarrassment: bool = False
    emb_max: int = 10              # PLACEHOLDER


@dataclass
class LicensingCfg:
    # Licensing (engine 0.16.0; engine/licensing.py; needs brands.enabled and market.days > 1). Off while
    # `schedule` is empty (0.15.0 bytes). schedule: {owner stall id: {"day": b, "n": N}}: at the start of
    # day b (before prices are set) the genuine owner licenses its brand to N non-genuine stalls of its
    # category, drawn from the dedicated stream [seed, 19, owner index]. From then to the last day each
    # licensee bears the brand's name, posts its price and claims its quality, never renames, and pays
    # the owner `royalty` x price per unit sold.
    schedule: dict = field(default_factory=dict)
    # "cheap": licensee true quality drawn from stalls.q_low (as for deceptive stalls), sign "pitch",
    # run by agents.seller.deceptive's policy. "contract": the owner's true quality, sign "truth",
    # run by rule_honest (honest licensing).
    quality: str = "cheap"
    royalty: float = 0.15          # PLACEHOLDER (rho)
    # Fines from catches at a licensee are charged to the owner instead of the licensee.
    owner_liable: bool = False
    # Engine 0.17.0. "owner" (default): licensees bear the owner's brand, as above. "white_label": the
    # licensees switch to the licence quality, sign and policy on day b exactly as above, but each under
    # one fresh unrated brand of its own (names from default_rng([seed, 24, owner index])): no tie to the
    # owner, no royalty, owner_liable does not apply, reviews are filed under the fresh brand, and its
    # price follows that brand's own rating by the morning rule (base x its type's tier x premium).
    brand: str = "owner"
    # Engine 0.18.0, white labels only. "type" (default, 0.17.0): a white label's price uses its stall type's
    # tier (seconds: pricing.seconds_price_factor). "genuine": tier 1.0, so it posts base x (1 + premium x
    # (rating - 0.5)) from its own brand's rating, the owner's formula. Ignored unless brand = "white_label".
    white_label_tier: str = "type"


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
    brands: BrandsCfg = field(default_factory=BrandsCfg)
    critics: CriticsCfg = field(default_factory=CriticsCfg)
    licensing: LicensingCfg = field(default_factory=LicensingCfg)
    sellers: SellersCfg = field(default_factory=SellersCfg)


PLACEHOLDERS = {
    "detection.form": "graded (chosen as placeholder 2026-11-03)",
    "inspectors.feature_correlation": "0.0 (chosen as placeholder 2026-11-03)",
    "valuation.form": "step_salvage (chosen as placeholder 2026-11-03)",
    "ratings.memory": "0.7 (placeholder 2026-11-05)",
    "ratings.tau": "0.5 (placeholder 2026-11-05)",
    "critics.count": "0 off; 4 in the 2026-11-07 capture run (placeholder)",
    "critics.sample": "6 (placeholder 2026-11-07)",
    "critics.weight": "5 (placeholder 2026-11-07)",
    "critics.tie_delay": "10 days (placeholder 2026-11-07)",
    "critics.emb_max": "10 days (placeholder 2026-11-07)",
    "inspectors.capture_effect": "0.8 (placeholder 2026-11-07)",
    "licensing.royalty": "0.15 (placeholder 2026-11-11)",
    "sellers.markup": "0.5 (placeholder 2026-11-19 plan, Stage 3)",
    "buyers.logit_rating_weight": "5 soft / 20 sharp (placeholder 2026-11-19 plan, Stage 3)",
    "buyers.logit_price_weight": "5 soft / 20 sharp (placeholder 2026-11-19 plan, Stage 3)",
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
                (BazaarConfig, "evolution"): EvolutionCfg, (BazaarConfig, "ratings"): RatingsCfg,
                (BazaarConfig, "brands"): BrandsCfg, (BazaarConfig, "critics"): CriticsCfg,
                (BazaarConfig, "licensing"): LicensingCfg, (BazaarConfig, "sellers"): SellersCfg}


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
_OPAQUE_DICTS = {"type_shares", "profile_shares", "search_depth"}
