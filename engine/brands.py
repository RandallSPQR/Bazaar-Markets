"""Brands (engine 0.8.0; brands.enabled, off by default). Engine 0.9.0 renamed "look-alike" to
"counterfeit"; "lookalike" is still accepted wherever a rename strategy is named.

The sign is the brand. With brands on:
  * Ratings attach to brand names, not stalls (a BrandBook carries them across days).
  * A stall can change its name only when it reopens after a closure: on its first decision
    after the closure ends (seller action "rename": "fresh" | "counterfeit"). Anyone who could see
    the new sign is within earshot, so the seller decides before any sign is delivered and the
    first decision is, for every observable purpose, the reopening.
      - "fresh": a new fictional name (unrated, so neutral).
      - "counterfeit": a near-copy of the highest-rated full-price brand on another stall of the
        same category (seconds and counterfeit names are never copied; unrated counts as 0.5; ties
        at random). The copy posts the original's price (decided 2026-11-06).
  * Tourists cannot tell a counterfeit from the original: they see the original's name and file
    their review under it. Locals and experts see the actual name and file under it.
  * Reputation premium: each morning a stall's price is
        base x tier x (1 + brands.premium x (rating - 0.5)),
    rating = its brand's rating at the start of the day (0.5 if unrated); tier = 1 (genuine),
    pricing.deceptive_price_factor or pricing.seconds_price_factor. A counterfeit posts the
    current price of the stall bearing the original's name (its own rule if none does).
    Unit costs do not change.

Name draws come from a dedicated stream, [day root, 11, stall index, rename count], so they
never shift any engine stream. Names are fictional.
"""
from __future__ import annotations

import math

import numpy as np

from .world import BRANDS

# Syllables for fresh names. Invented; checked against the existing brand list at draw time.
_FRESH = {
    "fish": (["Brack", "Cove", "Fen", "Harl", "Kell", "Mire", "Nesh", "Rill", "Scarr", "Tarn", "Wend", "Yarr"],
             ["", "a", "e", "o", "ar", "el"],
             ["wick", "mouth", "holm", "ness", "strand", "fleet", "lough", "sound"]),
    "electronics": (["Quell", "Zarn", "Vosk", "Tirr", "Nubel", "Orrik", "Plev", "Skarn", "Yeld", "Cwen"],
                    ["", "a", "e", "i", "o", "ar"],
                    ["ion", "etry", "ax", "ode", "ara", "imet", "wire", "ix"]),
    "designer": (["Maison", "Atelier", "Casa", "Haus"],
                 ["Or", "Ves", "Quen", "Bras", "Lum", "Sev", "Cor", "Il", "Tres", "Vel", "Mar", "Daun"],
                 ["ivre", "ane", "aude", "emont", "quelle", "arde", "ine", "ault"]),
}

_ACCENT = {"a": "àáâä", "e": "èéêë", "i": "ìíîï", "o": "òóôö", "u": "ùúûü",
           "A": "ÀÁÂÄ", "E": "ÈÉÊË", "I": "ÌÍÎÏ", "O": "ÒÓÔÖ", "U": "ÙÚÛÜ"}


def fresh_name(category: str, rng: np.random.Generator, used: set) -> str:
    pre, mid, suf = _FRESH.get(category, _FRESH["fish"])
    for _ in range(500):
        a, b, c = pre[int(rng.integers(len(pre)))], mid[int(rng.integers(len(mid)))], suf[int(rng.integers(len(suf)))]
        name = f"{a} {b}{c}" if category == "designer" else f"{a}{b}{c}"
        if name not in used:
            return name
    n = 2
    while f"{name} {n}" in used:
        n += 1
    return f"{name} {n}"


def _variants(name: str) -> list[tuple[str, int]]:
    """Applicable single edits: ("accent", i), ("swap", i), ("double", i)."""
    out = []
    for i, ch in enumerate(name):
        if ch in _ACCENT:
            out.append(("accent", i))
        if ch.isalpha():
            out.append(("double", i))
        if i + 1 < len(name) and ch.isalpha() and name[i + 1].isalpha() and ch.lower() != name[i + 1].lower():
            out.append(("swap", i))
    return out


def _apply(name: str, edit: tuple[str, int], rng: np.random.Generator) -> str:
    kind, i = edit
    if kind == "accent":
        opts = _ACCENT[name[i]]
        return name[:i] + opts[int(rng.integers(len(opts)))] + name[i + 1:]
    if kind == "double":
        return name[:i + 1] + name[i] + name[i + 1:]
    # swap two neighbouring letters, keeping the capital at the front
    a, b = name[i], name[i + 1]
    if i == 0 and a.isupper():
        a, b = a.lower(), b.upper()
    return name[:i] + b + a + name[i + 2:]


def counterfeit_name(original: str, rng: np.random.Generator, used: set) -> str:
    """A near-copy of `original`: one edit (an accent added, two letters swapped, or a letter
    doubled); two edits if every one-edit copy drawn is taken. Never equals the original."""
    for n_edits in (1, 2, 3):
        for _ in range(100):
            name = original
            for _ in range(n_edits):
                v = _variants(name)
                name = _apply(name, v[int(rng.integers(len(v)))], rng)
            if name != original and name not in used:
                return name
    raise RuntimeError(f"no free counterfeit of {original!r}")


PRIOR_SCOPES = ("all", "new")     # ratings.prior_scope (engine 0.19.0)
DISPLAYS = ("exact", "stars")      # ratings.display (engine 0.20.0)


def shown(cfg, r: float | None) -> float | None:
    """The rating as market participants see it (engine 0.20.0, ratings.display). "exact": r itself (0.19.0).
    "stars": r rounded half up to the nearest ratings.display_step (a step of 0.02 is a tenth of a star on a
    five-star scale). None (unrated) stays None; readers count it as 0.5 as before. The stored rating is never
    changed: only what buyers, prices and seller decisions read."""
    if r is None or cfg.ratings.display == "exact":
        return r
    step = float(cfg.ratings.display_step)
    k = math.floor(r / step + 0.5 + 1e-9)
    return round(k * step, 12)


def validate_display(cfg) -> None:
    r = cfg.ratings
    if r.display not in DISPLAYS:
        raise ValueError(f"ratings.display must be one of {DISPLAYS}, got {r.display!r}")
    st = r.display_step
    if isinstance(st, bool) or not isinstance(st, (int, float)) or not math.isfinite(st) or not 0 < st <= 1 \
            or abs(1 / st - round(1 / st)) > 1e-9:
        raise ValueError(f"ratings.display_step must be in (0, 1] with 1/step an integer, got {st!r}")


class BrandBook:
    """Brand state that persists across days: ratings by name, every name ever used, and how
    many times each stall has been renamed (the rename stream index)."""

    def __init__(self, stalls: list, prior_n: float = 0.0, prior_scope: str = "all", day: int = 1):
        self.ratings: dict[str, float | None] = {st.brand: st.rating for st in stalls}
        # Engine 0.18.0 (ratings.prior_n): pseudo-review weight at 0.5 by brand name; empty when prior_n = 0.
        # Engine 0.19.0 (ratings.prior_scope): "new" gives it only to brands created on day 2 or later; `day` is
        # the current market day, set by the engine each morning.
        self.prior_n = float(prior_n)
        self.prior_scope = prior_scope
        self.day = int(day)
        self.prior_w: dict[str, float] = ({n: self.prior_n for n in self.ratings}
                                          if self.prior_n > 0 and prior_scope == "all" else {})
        self.used: set = {n for names in BRANDS.values() for n in names} | set(self.ratings)
        self.renames: dict[str, int] = {st.sid: 0 for st in stalls}
        # Privileged benchmark input (0.9.0): yesterday's catches per stall making false claims
        # (deceptive type or busted), market-wide. Set by run_days; None on day 1. Shown only to
        # sellers whose policy declares itself privileged (rule_genuine_rational_v2).
        self.catch_rate_yesterday: float | None = None
        # Engine 0.11.0 (engine/critics.py), set only when the features are on.
        self.genuine_origin: list[str] = []         # brands on genuine stalls on day 1, by stall index
        self.critic_ties: set = set()               # {(critic, brand)}
        self.critic_hist: dict = {}                 # {(critic, brand): [positive, ...]} reviews written
        self.critic_pending: list[dict] = []        # written reviews not yet filed
        self.capture_ties: set = set()              # {(inspector ordinal, brand)}

    def rating(self, name: str) -> float | None:
        return self.ratings.get(name)

    def add(self, name: str) -> None:
        is_new = name not in self.ratings
        self.used.add(name)
        self.ratings.setdefault(name, None)
        if self.prior_n > 0 and (self.prior_scope == "all" or (is_new and self.day >= 2)):
            self.prior_w.setdefault(name, self.prior_n)


# 0.8.0 names, kept so old code and configs still work.
REOPEN_ALIASES = {"lookalike": "counterfeit"}


def canonical_reopen(how: str) -> str:
    """Map the 0.8.0 name "lookalike" to "counterfeit"; anything else is unchanged."""
    return REOPEN_ALIASES.get(how, how)


lookalike_name = counterfeit_name


def tier_factor(cfg, st) -> float:
    pr = cfg.pricing
    if st.white_label and cfg.licensing.white_label_tier == "genuine":   # 0.18.0
        return 1.0
    return {"genuine": 1.0, "deceptive": pr.deceptive_price_factor, "seconds": pr.seconds_price_factor}[st.stype]


def neutral_price(cfg, st) -> int:
    base = cfg.pricing.base_price_cents[st.category]
    return int(round(base * tier_factor(cfg, st)))


def premium_price(cfg, st, rating: float | None) -> int:
    base = cfg.pricing.base_price_cents[st.category]
    r = 0.5 if rating is None else rating
    return int(round(base * tier_factor(cfg, st) * (1 + cfg.brands.premium * (r - 0.5))))


# ------------------------------------------------------------------ engine 1.1.0: price policies

PRICE_POLICIES = ("rating_indexed", "cost_plus", "match_rival", "undercut", "promo")
PROMO_OFF = 0.15
PROMO_DAYS = 7
MATCH_BAND = 0.1


def _half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def validate_price_policy(cfg) -> None:
    s = cfg.sellers
    if s.price_policy not in PRICE_POLICIES:
        raise ValueError(f"sellers.price_policy must be one of {PRICE_POLICIES}, got {s.price_policy!r}")
    m = s.markup
    if isinstance(m, bool) or not isinstance(m, (int, float)) or not math.isfinite(m) or m < 0:
        raise ValueError(f"sellers.markup must be a finite number >= 0, got {m!r}")
    if s.price_policy != "rating_indexed" and not cfg.brands.enabled:
        raise ValueError("sellers.price_policy other than rating_indexed needs brands.enabled")


def _shown_or_neutral(cfg, r: float | None) -> float:
    v = shown(cfg, r)
    return 0.5 if v is None else v


def policy_price(cfg, st, stalls: list, rating: float | None) -> int:
    """The stall's own price today under sellers.price_policy (1.1.0), given its start-of-day rating (None after a
    rename). rating_indexed is the 1.0.0 formula. Rivals are read with their start-of-day ratings, so morning_prices
    sets every rating before any price."""
    ri = premium_price(cfg, st, shown(cfg, rating))
    pol = cfg.sellers.price_policy
    if pol == "rating_indexed":
        return ri
    if pol == "cost_plus":
        return _half_up(st.unit_cost_cents * (1 + float(cfg.sellers.markup)))
    if pol == "promo":
        h = st.units_hist
        return _half_up(ri * (1 - PROMO_OFF)) if h and h[-1] < sum(h) / len(h) else ri
    own = _shown_or_neutral(cfg, rating)
    rivals = [s for s in stalls if s.sid != st.sid and s.category == st.category and s.exited_day is None
              and s.yesterday is not None]
    if pol == "match_rival":
        ps = sorted(s.yesterday["price_cents"] for s in rivals
                    if _shown_or_neutral(cfg, s.rating) >= own - MATCH_BAND - 1e-9)
        if not ps:
            return ri
        n = len(ps)
        return ps[n // 2] if n % 2 else _half_up((ps[n // 2 - 1] + ps[n // 2]) / 2)
    ps = [s.yesterday["price_cents"] for s in rivals if _shown_or_neutral(cfg, s.rating) >= own - 1e-9]
    if not ps:                                   # undercut
        return ri
    return max(min(ps) - 1, int(st.unit_cost_cents))


def morning_prices(cfg, stalls: list, book: BrandBook) -> None:
    """Set every stall's price for the day from its brand's start-of-day rating; counterfeits
    then take the price of the stall bearing the original's name. 1.1.0: the own price follows
    sellers.price_policy (policy_price); every rating is set first."""
    for st in stalls:
        st.rating = book.rating(st.brand)
    for st in stalls:
        st.price_cents = policy_price(cfg, st, stalls, st.rating)     # 0.20.0: the displayed rating
    # 1.0.0 (formal-model check C1): a white-label licensee is the only stall bearing its fresh name, so it is the
    # holder; an owner-branded licensee shares its owner's name and stays out (the owner is the holder).
    holder = {st.brand: st for st in stalls
              if st.counterfeit_of is None and (st.licensed_from is None or st.white_label)}
    for st in stalls:
        if st.counterfeit_of is not None and st.counterfeit_of in holder:
            st.price_cents = counterfeit_price(cfg, holder[st.counterfeit_of].price_cents)


# ------------------------------------------------------------------ engine 0.17.0

ENTRIES = ("reopen", "day")
ENTRY_STREAM = 23


def counterfeit_price(cfg, original_cents: int) -> int:
    """A counterfeit's posted price: round(brands.counterfeit_price_factor x the original's price)."""
    phi = float(cfg.brands.counterfeit_price_factor)
    return int(original_cents) if phi == 1.0 else int(round(phi * int(original_cents)))


def validate_counterfeits(cfg) -> None:
    b = cfg.brands
    if b.counterfeit_entry not in ENTRIES:
        raise ValueError(f"brands.counterfeit_entry must be one of {ENTRIES}, got {b.counterfeit_entry!r}")
    phi = b.counterfeit_price_factor
    if isinstance(phi, bool) or not isinstance(phi, (int, float)) or not 0 < phi <= 10:
        raise ValueError(f"brands.counterfeit_price_factor must be in (0, 10], got {phi!r}")
    d = b.counterfeit_day
    if b.counterfeit_entry == "day":
        if isinstance(d, bool) or int(d) != d or not 2 <= d <= int(cfg.market.days):
            raise ValueError(f"brands.counterfeit_day must be an integer in [2, market.days], got {d!r}")


def counterfeit_logging(cfg) -> bool:
    """Whether the day log reports counterfeit prices (only with a 0.17.0 dial off its default)."""
    return cfg.brands.counterfeit_entry == "day" or float(cfg.brands.counterfeit_price_factor) != 1.0


def enter_counterfeits(cfg, stalls: list, book: BrandBook, sroot: tuple | None = None) -> list[dict]:
    """brands.counterfeit_entry "day": every deceptive stall still in the market (licensees excluded)
    copies the name of the top-rated genuine brand of its category (book ratings, i.e. at the end of the
    previous day; unrated = 0.5), in stall order. Ties and the name edits come from default_rng([seed, 23]).
    The stall claims the original's true quality from now on and is never offered a rename."""
    rng = np.random.default_rng([*((cfg.seed,) if sroot is None else sroot), ENTRY_STREAM])   # 1.1.0: sroot
    out = []
    for st in sorted(stalls, key=lambda s: s.idx):
        if st.stype != "deceptive" or st.exited_day is not None or st.licensed_from is not None:
            continue
        cands = [s for s in stalls if s.category == st.category and s.stype == "genuine" and s.exited_day is None
                 and s.counterfeit_of is None and s.licensed_from is None]
        if not cands:
            out.append({"stall": st.sid, "from": st.brand, "to": None, "counterfeit_of": None})
            continue
        score = {s.sid: (0.5 if book.rating(s.brand) is None else shown(cfg, book.rating(s.brand))) for s in cands}
        best = max(score.values())
        top = sorted((s for s in cands if score[s.sid] == best), key=lambda s: s.idx)
        target = top[int(rng.integers(len(top)))] if len(top) > 1 else top[0]
        name = counterfeit_name(target.brand, rng, book.used)
        book.add(name)
        rec = {"stall": st.sid, "from": st.brand, "to": name, "counterfeit_of": target.brand,
               "target_stall": target.sid, "target_rating": book.rating(target.brand), "q_pitch_was": st.q_pitch,
               "q_pitch": target.q_true}
        st.brand, st.rating, st.counterfeit_of = name, None, target.brand
        st.q_pitch = target.q_true
        st.rename_pending, st.counterfeit_fixed = False, True
        out.append(rec)
    return out


def counterfeit_prices(stalls: list) -> dict:
    """Today's counterfeit prices and unit costs, with a flag for a price below unit cost."""
    return {st.sid: {"counterfeit_of": st.counterfeit_of, "price_cents": st.price_cents,
                     "unit_cost_cents": st.unit_cost_cents, "below_cost": st.price_cents < st.unit_cost_cents}
            for st in sorted(stalls, key=lambda s: s.idx) if st.counterfeit_of is not None}


def counterfeit_target(stalls: list, st, book: BrandBook, rng: np.random.Generator, cfg=None):
    """The highest-rated full-price brand on another stall of st's category (counterfeits
    excluded; unrated = 0.5); ties uniformly at random. None if there is no candidate. With cfg given,
    ratings are compared as displayed (0.20.0, ratings.display)."""
    cands = [s for s in stalls if s.sid != st.sid and s.category == st.category and s.stype != "seconds"
             and s.counterfeit_of is None and s.exited_day is None]
    if not cands:
        return None
    score = {s.sid: (0.5 if book.rating(s.brand) is None else
                     (book.rating(s.brand) if cfg is None else shown(cfg, book.rating(s.brand)))) for s in cands}
    best = max(score.values())
    top = [s for s in cands if score[s.sid] == best]
    return top[int(rng.integers(len(top)))]


lookalike_target = counterfeit_target


def update_brand_ratings(book: BrandBook, buys: list[dict], memory: float, extra: list | None = None) -> dict:
    """End-of-day rating update by brand name. Each rated unit (the buyer had received at least
    one claim from the stall before buying) is filed under the purchase's `filed_under` name and
    is honest when the stall's true Q met the latest such claim. Same blend as 0.7.0. With
    ratings.prior_n > 0 (0.18.0) each brand's share also counts its remaining pseudo-reviews at 0.5. `extra`
    (critics, 0.11.0): (name, positive, weight) reviews counted as `weight` rated units each.
    Returns {name: (honest units, claimed units)} for the day."""
    claimed: dict = {}
    honest: dict = {}
    for n, pos, w in extra or []:
        claimed[n] = claimed.get(n, 0) + w
        if pos:
            honest[n] = honest.get(n, 0) + w
    for b in buys:
        if not b["known_claims"]:
            continue
        n = b["filed_under"]
        claimed[n] = claimed.get(n, 0) + b["units"]
        if b["q_true"] >= b["known_claims"][-1] - 1e-12:
            honest[n] = honest.get(n, 0) + b["units"]
    for n, c in claimed.items():
        w = book.prior_w.get(n, 0.0)
        share = (honest.get(n, 0) + 0.5 * w) / (c + w) if w else honest.get(n, 0) / c
        old = book.ratings.get(n)
        book.ratings[n] = share if old is None else memory * old + (1 - memory) * share
    for n in book.prior_w:          # 0.18.0: pseudo-reviews fade at the memory rate, every day end
        book.prior_w[n] *= memory
    return {n: (honest.get(n, 0), c) for n, c in sorted(claimed.items())}


def bust_quality(cfg, st) -> float:
    """The low true quality a genuine stall drops to if it busts out: drawn once per stall from
    q_low on its own stream [seed, 12, stall index]."""
    lo = cfg.stalls.q_low
    u = float(np.random.default_rng([cfg.seed, 12, st.idx]).random())
    return round(lo[0] + (lo[1] - lo[0]) * u, 4)


def unit_cost(cfg, st, q: float) -> int:
    pr = cfg.pricing
    base = pr.base_price_cents[st.category]
    return int(round(base * (pr.unit_cost[0] + pr.unit_cost[1] * float(q))))
