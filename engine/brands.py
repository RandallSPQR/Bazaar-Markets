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


class BrandBook:
    """Brand state that persists across days: ratings by name, every name ever used, and how
    many times each stall has been renamed (the rename stream index)."""

    def __init__(self, stalls: list):
        self.ratings: dict[str, float | None] = {st.brand: st.rating for st in stalls}
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
        self.used.add(name)
        self.ratings.setdefault(name, None)


# 0.8.0 names, kept so old code and configs still work.
REOPEN_ALIASES = {"lookalike": "counterfeit"}


def canonical_reopen(how: str) -> str:
    """Map the 0.8.0 name "lookalike" to "counterfeit"; anything else is unchanged."""
    return REOPEN_ALIASES.get(how, how)


lookalike_name = counterfeit_name


def tier_factor(cfg, st) -> float:
    pr = cfg.pricing
    return {"genuine": 1.0, "deceptive": pr.deceptive_price_factor, "seconds": pr.seconds_price_factor}[st.stype]


def neutral_price(cfg, st) -> int:
    base = cfg.pricing.base_price_cents[st.category]
    return int(round(base * tier_factor(cfg, st)))


def premium_price(cfg, st, rating: float | None) -> int:
    base = cfg.pricing.base_price_cents[st.category]
    r = 0.5 if rating is None else rating
    return int(round(base * tier_factor(cfg, st) * (1 + cfg.brands.premium * (r - 0.5))))


def morning_prices(cfg, stalls: list, book: BrandBook) -> None:
    """Set every stall's price for the day from its brand's start-of-day rating; counterfeits
    then take the price of the stall bearing the original's name."""
    for st in stalls:
        st.rating = book.rating(st.brand)
        st.price_cents = premium_price(cfg, st, st.rating)
    holder = {st.brand: st for st in stalls if st.counterfeit_of is None and st.licensed_from is None}
    for st in stalls:
        if st.counterfeit_of is not None and st.counterfeit_of in holder:
            st.price_cents = holder[st.counterfeit_of].price_cents


def counterfeit_target(stalls: list, st, book: BrandBook, rng: np.random.Generator):
    """The highest-rated full-price brand on another stall of st's category (counterfeits
    excluded; unrated = 0.5); ties uniformly at random. None if there is no candidate."""
    cands = [s for s in stalls if s.sid != st.sid and s.category == st.category and s.stype != "seconds"
             and s.counterfeit_of is None and s.exited_day is None]
    if not cands:
        return None
    score = {s.sid: (0.5 if book.rating(s.brand) is None else book.rating(s.brand)) for s in cands}
    best = max(score.values())
    top = [s for s in cands if score[s.sid] == best]
    return top[int(rng.integers(len(top)))]


lookalike_target = counterfeit_target


def update_brand_ratings(book: BrandBook, buys: list[dict], memory: float, extra: list | None = None) -> dict:
    """End-of-day rating update by brand name. Each rated unit (the buyer had received at least
    one claim from the stall before buying) is filed under the purchase's `filed_under` name and
    is honest when the stall's true Q met the latest such claim. Same blend as 0.7.0. `extra`
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
        share = honest.get(n, 0) / c
        old = book.ratings.get(n)
        book.ratings[n] = share if old is None else memory * old + (1 - memory) * share
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
