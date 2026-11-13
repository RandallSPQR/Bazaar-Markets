"""Bazaar world generation: layout, stalls, products, people, routes.

All randomness comes from engine-owned streams passed in by the caller.

Layout: one aisle per category (by default). Aisle k runs along row y = 3k+1;
stalls face it from rows 3k and 3k+2 at x = 2, 4, ..., and cross corridors
run along x = 0 and x = W-1. Walkable cells are aisle rows and the corridors.

Brands and specs are fictional. Spec values are mapped from Q into plausible
ranges; they are not copied from any real product.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import math

import numpy as np

from .config import BazaarConfig

BRANDS = {
    "fish": ["Kelpmoor", "Brindlewave", "Saltquay", "Orrin Bay", "Tidelace", "Murrowfin",
             "Gullhaven", "Skerrow", "Pebblemarsh", "Wrackton", "Selkie Row", "Dunmere"],
    "electronics": ["Voltaine", "Quillex", "Nembrik", "Arcsona", "Plinth-9", "Zerovane",
                    "Hollowbit", "Tessarine", "Corvalt", "Ionwick", "Fennac", "Glimmerline"],
    "designer": ["Maison Velquier", "Atelier Dunsore", "Casa Ombrielle", "Vantreau", "Lissoné",
                 "Haus Kerrowin", "Brumelle", "Oriane Vasq", "Stellacourt", "Domaine Frisk",
                 "Corvane & Lisle", "Verrault"],
}


def spec_text(category: str, q: float) -> str:
    """Render a claimed quality as a category-appropriate spec line."""
    if category == "fish":
        return f"caught {round(72 - 70 * q)} hours ago"
    if category == "electronics":
        return f"battery life {round(4 + 16 * q)} h, {round(200 + 1800 * q)} charge cycles"
    if category == "designer":
        return f"{round(6 + 8 * q)} stitches per inch, full-grain grade {round(1 + 4 * q)}/5"
    return f"grade {q:.2f}"


# Inspector placements that can wear a uniform (inspectors.uniformed). Disguised never can.
UNIFORMABLE = ("posts", "clustered", "patrolling")


@dataclass
class Stall:
    sid: str
    idx: int
    category: str
    stype: str           # "genuine" | "seconds" | "deceptive"
    pos: tuple
    brand: str
    q_true: float
    q_pitch: float       # what the stall claims when it pitches (== q_true unless deceptive)
    sign: str            # "pitch" | "truth" | "none"
    price_cents: int
    unit_cost_cents: int
    yell_cost_cents: int
    whisper_cost_cents: int
    penalty_cents: int
    # mutable accounting
    closed_until: int = -1
    epoch: int = 0
    revenue_cents: int = 0
    cost_cents: int = 0
    ad_spend_cents: int = 0
    penalties_cents: int = 0
    units_sold: int = 0
    catches: int = 0
    switch_cost_cents: int = 0     # charged on the first day in a new type (multi-day runs)
    switch_cost_due: int = 0       # set by a switch, moved into switch_cost_cents the next day
    rating: float | None = None    # public rating (ratings.mode != "off"); persists across days
    # brands (brands.enabled only; engine/brands.py)
    counterfeit_of: str | None = None  # the original's name, if the current name is a counterfeit
    rename_pending: bool = False     # set by a catch; the first decision after reopening may rename
    busted_day: int | None = None    # day a genuine stall busted out (rule_genuine_rational)
    decided_today: bool = False      # has the stall made a decision yet today
    yesterday: dict | None = None    # previous day's ledger (multi-day runs)
    # liability (engine 0.15.0)
    fines_pending: list = field(default_factory=list)  # lagged fines not yet due: {catch_day, due_day, cents}
    exit_pending: bool = False       # the stall chose to exit at the end of today
    exited_day: int | None = None    # the day at whose end the stall left the market
    # licensing (engine 0.16.0; engine/licensing.py)
    licensed_from: str | None = None  # the owner's stall id, for a licensee
    licence: str | None = None        # "cheap" | "contract", for a licensee
    royalty_paid_cents: int = 0       # today's royalties paid (licensee) ...
    royalty_received_cents: int = 0   # ... and received (owner)
    # engine 0.17.0
    counterfeit_fixed: bool = False   # took a counterfeit name by brands.counterfeit_entry "day": never renames
    white_label: bool = False         # a licensee under its own fresh brand (licensing.brand "white_label")

    def truth(self) -> dict:
        return {"sid": self.sid, "category": self.category, "stype": self.stype, "pos": list(self.pos),
                "brand": self.brand, "q_true": self.q_true, "q_pitch": self.q_pitch, "sign": self.sign,
                "price_cents": self.price_cents, "unit_cost_cents": self.unit_cost_cents}


@dataclass
class Person:
    pid: str
    idx: int
    kind: str              # "buyer" | "inspector"
    profile: str           # true profile (buyers); observable profile (inspectors)
    route: list            # list of (x, y)
    arrive: int
    is_inspector: bool
    task: dict | None = None
    inspect_cost_cents: int = 0
    uniform: bool = False  # visible to sellers; only uniformed (non-disguised) inspectors
    # mutable
    step: int = 0
    active: bool = False
    done: bool = False
    stop_actions: int = 0
    units: int = 0
    q_units: int = 0       # units bought with Q >= Q_req
    paid_cents: int = 0
    inspect_spent_cents: int = 0
    value: float = 0.0
    info: dict = field(default_factory=dict)   # sid -> {"claims": [...], "inspected_q": float|None}
    seen_signs: set = field(default_factory=set)
    hold_until: int = 0    # a buyer action holds the buyer until this tick (market.scale ticks)
    # search (engine 0.10.0; buyers.search_depth > 1 for this buyer's profile only)
    search_k: int = 1
    seen: dict = field(default_factory=dict)     # sid -> route index where it was last within reach
    target: str | None = None                    # stall the buyer is walking to
    skipped: set = field(default_factory=set)    # chosen stalls found closed; not offered again
    walk_ticks: int = 0                          # ticks spent walking to a chosen stall
    search_rec: dict | None = None               # per-buyer search record (buyers.search_log)
    consider: frozenset | None = None            # consideration set (buyers.demand_mode "choice_set")
    choosing: bool = False                       # in the "choose" phase for good (0.14.0)

    @property
    def pos(self) -> tuple:
        return self.route[min(self.step, len(self.route) - 1)]


class Layout:
    def __init__(self, cfg: BazaarConfig):
        mk = cfg.market
        self.scale = 1
        self.n_aisles = len(mk.categories)
        self.W = 2 + mk.slot_spacing * mk.slots_per_side + 1
        self.H = 3 * self.n_aisles
        self.aisle_y = [3 * k + 1 for k in range(self.n_aisles)]
        self.slot_x = [2 + mk.slot_spacing * i for i in range(mk.slots_per_side)]
        # slots ordered aisle by aisle, so a sorted assignment puts one category per aisle
        self.slots = [(x, y) for k in range(self.n_aisles) for y in (3 * k, 3 * k + 2) for x in self.slot_x]

    def walk(self, a: tuple, b: tuple) -> list:
        """Cells from a (exclusive) to b (inclusive), moving along x then y.
        Only used between points on the same aisle row or the same corridor column."""
        out = []
        x, y = a
        while x != b[0]:
            x += 1 if b[0] > x else -1
            out.append((x, y))
        while y != b[1]:
            y += 1 if b[1] > y else -1
            out.append((x, y))
        return out

    def route_through(self, aisles: list[int], start_left: bool) -> list:
        """Enter at a corridor, traverse each listed aisle end to end, exit at a corridor."""
        left, right = 0, self.W - 1
        side = left if start_left else right
        path = [(side, self.aisle_y[aisles[0]])]
        for k in aisles:
            y = self.aisle_y[k]
            path += self.walk(path[-1], (side, y))
            side = right if side == left else left
            path += self.walk(path[-1], (side, y))
        return path

    def patrol_loop(self) -> list:
        """A serpentine loop through every aisle and back."""
        order = list(range(self.n_aisles)) + list(range(self.n_aisles - 2, 0, -1))
        loop = self.route_through(order if order else [0], True)
        return loop + self.walk(loop[-1], loop[0])[:-1] if loop[-1] != loop[0] else loop


def build_stalls(cfg: BazaarConfig, layout: Layout, rng: np.random.Generator) -> list[Stall]:
    mk, st, pr = cfg.market, cfg.stalls, cfg.pricing
    per_cat = 2 * mk.slots_per_side
    # Sorted assignment: category c fills aisle c. Clustering dial: each slot
    # joins a shuffle pool with probability (1 - clustering); the pool is permuted.
    assign = [c for c in mk.categories for _ in range(per_cat)]
    in_pool = rng.random(len(assign)) >= mk.clustering
    pool_idx = np.flatnonzero(in_pool)
    perm = rng.permutation(pool_idx)
    shuffled = list(assign)
    for dst, src in zip(pool_idx, perm):
        shuffled[dst] = assign[src]
    # Stall types: exact counts per category from type_shares, positions shuffled.
    # Share tables are iterated in sorted key order: dict order must never change a run
    # (logged configs are written with sorted keys).
    types = sorted(st.type_shares)
    stalls: list[Stall] = []
    by_cat_slots = {c: [i for i, cc in enumerate(shuffled) if cc == c] for c in mk.categories}
    slot_type: dict[int, str] = {}
    for c in mk.categories:
        slots = by_cat_slots[c]
        counts = _apportion([st.type_shares[t] for t in types], len(slots))
        labels = [t for t, n in zip(types, counts) for _ in range(n)]
        labels = [labels[i] for i in rng.permutation(len(labels))]
        for s, lab in zip(slots, labels):
            slot_type[s] = lab
    brand_left = {c: list(BRANDS[c]) for c in mk.categories}
    for i, (pos, c) in enumerate(zip(layout.slots, shuffled)):
        stype = slot_type[i]
        hi = float(rng.uniform(*st.q_high)); lo = float(rng.uniform(*st.q_low))
        if stype == "genuine":
            q_true, q_pitch, sign = hi, hi, "truth"
        elif stype == "seconds":
            q_true, q_pitch, sign = lo, lo, "truth"
        else:
            q_true, q_pitch, sign = lo, hi, st.deceptive_sign
        base = pr.base_price_cents[c]
        if stype == "seconds":
            price = round(base * pr.seconds_price_factor)
        elif stype == "deceptive":
            price = round(base * pr.deceptive_price_factor)
        else:
            price = base
        names = brand_left[c]
        brand = names.pop(int(rng.integers(len(names)))) if names else f"{c.title()} Stall {i}"
        stalls.append(Stall(
            sid=f"s{i:02d}", idx=i, category=c, stype=stype, pos=pos, brand=brand,
            q_true=round(q_true, 4), q_pitch=round(q_pitch, 4), sign=sign, price_cents=int(price),
            unit_cost_cents=int(round(base * (pr.unit_cost[0] + pr.unit_cost[1] * q_true))),
            yell_cost_cents=int(round(base * pr.yell_cost_frac)),
            whisper_cost_cents=int(round(base * pr.whisper_cost_frac)),
            penalty_cents=int(round(base * pr.penalty_mult))))
    return stalls


def _apportion(shares: list[float], n: int) -> list[int]:
    """Largest-remainder apportionment of n items to the given shares."""
    tot = sum(shares)
    raw = [s / tot * n for s in shares]
    out = [int(np.floor(r)) for r in raw]
    rem = sorted(range(len(shares)), key=lambda i: (-(raw[i] - out[i]), i))
    for i in rem[: n - sum(out)]:
        out[i] += 1
    return out


def _choice(rng: np.random.Generator, table: dict) -> str:
    keys = sorted(table)
    p = np.array([table[k] for k in keys], float)
    return keys[int(rng.choice(len(keys), p=p / p.sum()))]


DEMAND_MODES = ("walk", "choice_set")


def bargain_share(bc) -> float:
    """buyers.bargain_share, or its demand-mode default when null: 0 ("walk"), 0.2 ("choice_set")."""
    if bc.bargain_share is None:
        return 0.2 if bc.demand_mode == "choice_set" else 0.0
    return float(bc.bargain_share)


def validate_demand(cfg: BazaarConfig) -> None:
    bc = cfg.buyers
    if bc.demand_mode not in DEMAND_MODES:
        raise ValueError(f"buyers.demand_mode must be one of {DEMAND_MODES}, got {bc.demand_mode!r}")
    if int(bc.consider) != bc.consider or bc.consider < 1:
        raise ValueError(f"buyers.consider must be an integer >= 1, got {bc.consider!r}")
    g = float(bc.position_rent)
    if not (g >= 0 and math.isfinite(g)):
        raise ValueError(f"buyers.position_rent must be a finite number >= 0, got {bc.position_rent!r}")
    if bc.demand_mode == "choice_set" and float(cfg.market.clustering) != 1.0:
        raise ValueError("buyers.demand_mode = choice_set needs market.clustering = 1 (one aisle per category)")


def position_ranks(cat_stalls: list, from_left: bool) -> dict:
    """Rank of each stall by distance from an entrance at one end of its aisle: 0 = nearest; stalls
    at the same distance (facing each other across the aisle) share a rank."""
    xs = sorted({st.pos[0] for st in cat_stalls}, reverse=not from_left)
    r = {x: i for i, x in enumerate(xs)}
    return {st.sid: r[st.pos[0]] for st in cat_stalls}


def consideration_set(cfg: BazaarConfig, root: tuple, i: int, cat_stalls: list) -> tuple[bool, list]:
    """Entrance end and consideration set of buyer i (buyers.demand_mode "choice_set"), from the
    stream [root, 18, i]: one draw for the entrance (left end with probability 1/2), then
    buyers.consider draws for the set, always all consumed. Successive sampling without
    replacement with weight exp(-position_rent x position rank); position_rent = 0 is uniform.
    Returns (enters from the left, set members in walking order)."""
    bc = cfg.buyers
    rng = np.random.default_rng([*root, 18, i])
    left = bool(rng.random() < 0.5)
    u = rng.random(int(bc.consider))
    ranks = position_ranks(cat_stalls, left)
    g = float(bc.position_rent)
    pool = sorted(cat_stalls, key=lambda st: st.idx)
    chosen = []
    for k in range(min(int(bc.consider), len(pool))):
        w = np.array([math.exp(-g * ranks[st.sid]) for st in pool])
        cum = np.cumsum(w) / w.sum()
        j = min(int(np.searchsorted(cum, u[k], side="right")), len(pool) - 1)
        chosen.append(pool.pop(j))
    chosen.sort(key=lambda st: (ranks[st.sid], st.idx))
    return left, [st.sid for st in chosen]


def build_people(cfg: BazaarConfig, layout: Layout, rng_routes: np.random.Generator,
                 rng_people: np.random.Generator, rng_treat: np.random.Generator | None = None,
                 rng_insp: np.random.Generator | None = None, root: tuple | None = None,
                 stalls: list | None = None) -> list[Person]:
    """Build the population in a treatment-stable way.

    The buyer population (profile, category, units, Q_req, route, arrival, id) is
    drawn first, with a fixed number of draws per buyer, from streams no treatment
    touches. Treatment assignments (mixed budget level, inspector-buyer status) use
    rng_treat, with exactly one draw of each kind per buyer whether or not the
    treatment is on. Dedicated inspectors use rng_insp and come after every buyer.
    Ids are stable hashes of (seed, kind, index), so buyer ids do not change when the
    number of inspectors does; kinds share one id space, so ids reveal nothing.
    """
    mk, bc, ic = cfg.market, cfg.buyers, cfg.inspectors
    root = (cfg.seed,) if root is None else tuple(root)   # stream prefix; per day in multi-day runs
    if rng_treat is None:
        rng_treat = np.random.default_rng([*root, 5])
    if rng_insp is None:
        rng_insp = np.random.default_rng([*root, 6])
    people: list[Person] = []
    longest = layout.route_through(list(range(layout.n_aisles)), True)
    last_arrival = max(1, mk.ticks - len(longest) - 5)
    base_cat = cfg.pricing.base_price_cents

    def random_route() -> list:
        lo, hi = bc.aisles_per_route
        n = int(rng_routes.integers(lo, min(hi, layout.n_aisles) + 1))
        aisles = [int(a) for a in rng_routes.permutation(layout.n_aisles)[:n]]
        return layout.route_through(aisles, bool(rng_routes.random() < 0.5))

    # Bargain hunters (0.11.0): a dedicated stream, used only when the share is > 0.
    bargain = bargain_share(bc)
    if not 0 <= bargain <= 1:
        raise ValueError(f"buyers.bargain_share must be in [0, 1], got {bargain}")
    lo_b, hi_b = (float(x) for x in bc.bargain_q_req)
    if not 0.0 <= lo_b <= hi_b <= 1.0:
        raise ValueError(f"buyers.bargain_q_req must be [lo, hi] with 0 <= lo <= hi <= 1, got {bc.bargain_q_req!r}")
    rng_bargain = np.random.default_rng([*root, 16]) if bargain > 0 else None

    # Demand (0.12.0): in "choice_set" mode the random route is still drawn (so every other draw
    # on the route stream is unchanged) and then replaced by a walk along the category's aisle.
    choice = bc.demand_mode == "choice_set"
    if choice:
        if stalls is None:
            raise ValueError("buyers.demand_mode = choice_set needs the stalls")
        # 0.15.0: a stall that has left the market is in no consideration set
        by_cat = {c: [st for st in stalls if st.category == c and st.exited_day is None] for c in mk.categories}

    # Buyers.
    for i in range(bc.count):
        profile = _choice(rng_people, bc.profile_shares)
        cat = mk.categories[int(rng_people.integers(len(mk.categories)))]
        units = int(rng_people.integers(bc.units[0], bc.units[1] + 1))
        q_req = round(float(rng_people.uniform(*bc.q_req)), 4)
        is_bargain = False
        if rng_bargain is not None:
            u_b, q_b = float(rng_bargain.random()), float(rng_bargain.uniform(*bc.bargain_q_req))
            if u_b < bargain:
                q_req, is_bargain = round(q_b, 4), True
        # Treatment draws: always consumed, so turning a treatment on or off never
        # shifts any other buyer's attributes.
        u_level = int(rng_treat.integers(3))
        u_insp = float(rng_treat.random())
        level = bc.budget_level
        if level == "mixed":
            level = ["above", "at", "below"][u_level]
        # Reference price: what a genuine unit meeting Q_req costs (the genuine posted price).
        factor = bc.budget_factors[level] if bc.budget_factor_override is None else float(bc.budget_factor_override)
        budget = int(round(units * base_cat[cat] * factor))
        is_insp = bool(u_insp < bc.inspector_fraction)
        arrive = int(round(i * last_arrival / max(1, bc.count)))
        route, consider = random_route(), None
        if choice:
            left, members = consideration_set(cfg, root, i, by_cat[cat])
            route = layout.route_through([mk.categories.index(cat)], left)
            consider = members
        people.append(Person(
            pid="", idx=0, kind="buyer", profile=profile, route=route, arrive=arrive,
            is_inspector=is_insp,
            task={"category": cat, "units": units, "q_req": q_req, "budget_cents": budget, "budget_level": level,
                  **({} if bc.budget_factor_override is None else {"budget_factor": factor}),
                  **({"bargain": True} if is_bargain else {}),
                  **({"consider": consider} if choice else {})},
            inspect_cost_cents=int(round(base_cat[cat] * bc.inspect_cost_frac[profile])),
            consider=None if consider is None else frozenset(consider)))

    # Inspectors. Observable profile follows the feature-correlation dial.
    posts = _inspector_posts(cfg, layout, rng_routes)
    loop = layout.patrol_loop()
    for j in range(ic.count):
        if rng_insp.random() < ic.feature_correlation:
            profile = "expert"
        else:
            profile = _choice(rng_insp, bc.profile_shares)
        if ic.placement in ("posts", "clustered"):
            route, arrive = [posts[j]], 0
        elif ic.placement == "patrolling":
            off = (j * len(loop)) // max(1, ic.count)
            reps = mk.ticks // len(loop) + 2
            route, arrive = (loop[off:] + loop * reps)[: mk.ticks + 1], 0
        elif ic.placement == "disguised" and ic.disguised_shift == "full_shift":
            route, arrive = _full_shift_route(cfg, layout, j, root), 0
        elif ic.placement == "disguised":
            if ic.disguised_shift != "single_trip":
                raise ValueError(f"unknown inspectors.disguised_shift {ic.disguised_shift!r}")
            route = random_route()
            arrive = int(round((j + 0.5) * last_arrival / max(1, ic.count)))
        else:
            raise ValueError(f"unknown inspector placement {ic.placement!r}")
        people.append(Person(pid="", idx=0, kind="inspector", profile=profile, route=route,
                             arrive=arrive, is_inspector=True,
                             uniform=bool(ic.uniformed and ic.placement in UNIFORMABLE)))

    # Seller-facing ids: stable hashes of (seed, kind, index within kind), in one shared
    # id space, so neither kind nor order can be read from them and buyer ids do not
    # depend on how many inspectors there are. Buyers are assigned first, so a
    # collision is always resolved on the inspector's side.
    used: set = set()
    counters = {"buyer": 0, "inspector": 0}
    for i, p in enumerate(people):
        p.idx = i
        k = counters[p.kind]; counters[p.kind] += 1
        code = 0 if p.kind == "buyer" else 1
        attempt = 0
        while True:
            n = int(np.random.default_rng([*root, 8, code, k, attempt]).integers(10**6))
            pid = f"p{n:06d}"
            if pid not in used:
                break
            attempt += 1
        used.add(pid)
        p.pid = pid
    return people


def refine_route(route: list, k: int) -> list:
    """Refine a k = 1 route to scale k: coordinates times k, each one-cell step split into
    k steps, and the last cell held k ticks (it is held one tick at k = 1). Then
    out[k t] = k route[t] for every t, and len(out) = k len(route)."""
    if k == 1:
        return route
    out = [(k * route[0][0], k * route[0][1])]
    for a, b in zip(route, route[1:]):
        if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
            raise ValueError(f"route step {a} -> {b} is not one cell")
        for i in range(1, k + 1):
            out.append((k * a[0] + i * (b[0] - a[0]), k * a[1] + i * (b[1] - a[1])))
    return out + [out[-1]] * (k - 1)


def refine_world(layout: "Layout", stalls: list, people: list, k: int) -> None:
    """Refine a world built at k = 1 to scale k, in place. Pass stalls=[] for stalls that
    are already refined (later days of a multi-day run)."""
    if k == 1:
        return
    layout.scale = k
    layout.W, layout.H = k * (layout.W - 1) + 1, k * (layout.H - 1) + 1
    layout.aisle_y = [k * y for y in layout.aisle_y]
    layout.slot_x = [k * x for x in layout.slot_x]
    layout.slots = [(k * x, k * y) for x, y in layout.slots]
    for st in stalls:
        st.pos = (k * st.pos[0], k * st.pos[1])
    for p in people:
        p.route = refine_route(p.route, k)
        p.arrive *= k


def _full_shift_route(cfg: BazaarConfig, layout: Layout, j: int, root: tuple | None = None) -> list:
    """Random buyer-like routes back to back, joined through the corridors, long
    enough to last the whole run. Drawn from inspector j's own stream in the
    inspector family ([seed, 6, 1, j]), so buyer routes, other inspectors' draws and
    inspector j's route at a different headcount are all unchanged."""
    rng = np.random.default_rng([*((cfg.seed,) if root is None else root), 6, 1, j])
    lo, hi = cfg.buyers.aisles_per_route
    need = cfg.market.ticks + 1
    path: list = []
    while len(path) < need:
        n = int(rng.integers(lo, min(hi, layout.n_aisles) + 1))
        aisles = [int(a) for a in rng.permutation(layout.n_aisles)[:n]]
        leg = layout.route_through(aisles, bool(rng.random() < 0.5))
        path = leg if not path else path + layout.walk(path[-1], leg[0]) + leg[1:]
    return path[:need]


def _inspector_posts(cfg: BazaarConfig, layout: Layout, rng: np.random.Generator) -> list:
    n = cfg.inspectors.count
    xs = layout.slot_x
    if cfg.inspectors.placement == "clustered":
        k = int(rng.integers(layout.n_aisles))
        return [(xs[(i * len(xs)) // max(1, n)] + 1, layout.aisle_y[k]) for i in range(n)]
    out = []
    for i in range(n):
        k = i % layout.n_aisles
        slot = (i // layout.n_aisles) * len(xs) // max(1, -(-n // layout.n_aisles))
        out.append((xs[min(slot, len(xs) - 1)] + 1, layout.aisle_y[k]))
    return out
