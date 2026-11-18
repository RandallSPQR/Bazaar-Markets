"""Engine 0.20.0: ratings.display ("exact" = 0.19.0; "stars": what buyers, prices and seller decisions read is the rating
rounded half up to ratings.display_step) and buyers.tie_break ("stall_id" = 0.19.0; "random": a per-buyer, per-day random
order of the stalls from default_rng([seed, 29, day, buyer index])).

Reference: outcomes_v0190_all.json (154 cells at engine 0.19.0, generated at f39a99e, whose engine files are those of
8b7884b): every cell of outcomes_v0180_all.json plus white labels under ratings.prior_scope "new" at prior_n 3.5 and
400 and the owner-brand arm at prior_n 10. The new keys at their defaults must reproduce every cell byte for byte
(outcome and log body), with nothing stripped."""
import hashlib
import json
import os

import numpy as np
import pytest

from agents.rule_based import RuleBuyer
from analysis import chainrun as CR
from analysis.verification import overrides as vov
from engine import bazaar, benchmark
from engine import brands as B
from engine.bazaar import BazaarEngine
from engine.config import load
from engine.jsonlog import JsonlLog, dumps
from engine.runner import compare_logs, replay

HERE = os.path.join(os.path.dirname(__file__), "reference")
with open(os.path.join(HERE, "outcomes_v0190_all.json"), encoding="utf-8") as f:
    REF = json.load(f)
CELLS = REF["cells"]
STARS = ["ratings.display=stars", "buyers.tie_break=random"]


def _run(ov, seed):
    log = JsonlLog(keep=True)
    return bazaar.run(load(overrides=[*ov, f"seed={seed}"], mode="bazaar"), log=log), log.lines


def _check(o, lines, c):
    assert dumps(o) == c["outcome"]
    assert len(lines) == c["log_lines"]
    assert hashlib.sha256("\n".join(lines[1:]).encode()).hexdigest() == c["log_body_sha256"]


def test_reference_is_0190():
    assert REF["engine_version"] == "0.19.0" and REF["commit"] == "f39a99e" and len(CELLS) == 154


@pytest.mark.parametrize("key", sorted(CELLS))
def test_defaults_reproduce_0190(key):
    c = CELLS[key]
    o, lines = _run(c["overrides"], c["seed"])
    _check(o, lines, c)


@pytest.mark.parametrize("key", ["v0190_new400_wlg_t40|0", "v0190_new3.5_wlg_t100|1", "v0190_new10_R_t40|1",
                                 "v0170_cf_day_0.6_t40|0", "v0150_jp_t100|0"])
def test_defaults_set_explicitly_change_nothing(key):
    c = CELLS[key]
    o, lines = _run([*c["overrides"], "ratings.display=exact", "ratings.display_step=0.1",
                     "buyers.tie_break=stall_id"], c["seed"])
    _check(o, lines, c)


# ------------------------------------------------------------------ helpers

class _Cfg:
    def __init__(self, display="stars", step=0.02, premium=0.4):
        self.ratings = type("R", (), {"display": display, "display_step": step})()
        self.brands = type("Br", (), {"premium": premium})()


def _wl(extra=(), cond="B|t40|l1", days=6, seed=900, n=3, b=3, brand="white_label"):
    base = [*vov(cond), f"market.days={days}", "inspectors.detect_scale=1.0", "licensing.quality=contract",
            f"licensing.brand={brand}", "licensing.royalty=0.1", "licensing.white_label_tier=genuine",
            "ratings.prior_scope=new", *extra, f"seed={seed}"]
    cfg = load(overrides=base, mode="bazaar")
    owner = next(st.sid for st in sorted(BazaarEngine(cfg).stalls, key=lambda s: s.idx) if st.stype == "genuine")
    return benchmark.licence_config(cfg, owner, (n, b)), owner


# ------------------------------------------------------------------ display rounding

def test_rounding_half_up_to_the_step():
    c = _Cfg()
    assert B.shown(c, None) is None
    assert B.shown(c, 0.9991) == B.shown(c, 1.0) == 1.0
    assert B.shown(c, 0.99) == 1.0                 # exactly half a step: up
    assert B.shown(c, 0.9899) == 0.98
    assert B.shown(c, 0.5) == 0.5 and B.shown(c, 0.0) == 0.0 and B.shown(c, 0.01) == 0.02
    assert B.shown(c, 0.73) == 0.74 and B.shown(c, 0.7299) == 0.72
    h = _Cfg(step=0.1)
    assert B.shown(h, 0.95) == 1.0 and B.shown(h, 0.9499) == 0.9 and B.shown(h, 0.05) == 0.1
    e = _Cfg(display="exact")
    assert B.shown(e, 0.9991) == 0.9991 and B.shown(e, None) is None
    for r in np.linspace(0, 1, 1001):            # every displayed value is on the grid and within half a step
        v = B.shown(c, float(r))
        assert abs(v / 0.02 - round(v / 0.02)) < 1e-9 and abs(v - r) <= 0.01 + 1e-12


def test_display_and_price_identical_at_09991_and_1():
    """Under stars a brand at 0.9991 and one at 1.0 display identically and post the same price."""
    c = _Cfg()

    class S:
        white_label, stype, category = True, "genuine", "fish"
    cfg = load(overrides=["brands.enabled=true", "brands.premium=0.4", "licensing.white_label_tier=genuine",
                          "ratings.display=stars"], mode="bazaar")
    a, b = B.premium_price(cfg, S(), B.shown(cfg, 0.9991)), B.premium_price(cfg, S(), B.shown(cfg, 1.0))
    assert a == b
    assert B.shown(c, 0.9991) == B.shown(c, 1.0)
    ex = load(overrides=["brands.enabled=true", "brands.premium=0.4", "licensing.white_label_tier=genuine"], mode="bazaar")
    base = ex.pricing.base_price_cents["fish"]
    # exact display: the price follows the unrounded rating (it can differ by a cent near a rounding boundary)
    assert B.premium_price(ex, S(), B.shown(ex, 0.9991)) == int(round(base * (1 + 0.4 * (0.9991 - 0.5))))


def test_counterfeit_target_compares_displayed_ratings():
    class S:
        def __init__(self, sid, brand):
            self.sid, self.brand, self.category, self.stype = sid, brand, "fish", "genuine"
            self.counterfeit_of, self.exited_day, self.rating = None, None, None
    me, x, y = S("s00", "M"), S("s01", "X"), S("s02", "Y")
    book = B.BrandBook([me, x, y])
    book.ratings.update({"M": 0.2, "X": 0.9991, "Y": 1.0})
    stalls = [me, x, y]
    got_exact = {B.counterfeit_target(stalls, me, book, np.random.default_rng(i), _Cfg("exact")).sid for i in range(40)}
    got_none = {B.counterfeit_target(stalls, me, book, np.random.default_rng(i)).sid for i in range(40)}
    got_stars = {B.counterfeit_target(stalls, me, book, np.random.default_rng(i), _Cfg()).sid for i in range(40)}
    assert got_exact == got_none == {"s02"}
    assert got_stars == {"s01", "s02"}


@pytest.mark.parametrize("cond", ["B|t40|l1", "B|t100"])
def test_stored_ratings_stay_unrounded(cond):
    """Display rounding never changes the stored rating: under stars every day-end rating is the by-hand blend of the
    unrounded rule, and some are off the display grid."""
    cfg, _ = _wl(["ratings.prior_n=10", *STARS], cond=cond, days=8)
    o = bazaar.run(cfg)
    m = cfg.ratings.memory
    born = {}
    for d in o["days"]:
        for n in d["brand_ratings"]:
            born.setdefault(n, d["day"])
    w = {n: (0.0 if d == 1 else 10.0) for n, d in born.items()}
    rating, off_grid = {}, 0
    for d in o["days"]:
        for name, (h, c) in d["reviews"].items():
            share = (h + 0.5 * w[name]) / (c + w[name]) if w[name] else h / c
            old = rating.get(name)
            rating[name] = share if old is None else m * old + (1 - m) * share
        for name in w:
            if born[name] <= d["day"]:
                w[name] *= m
        for name, r in d["brand_ratings"].items():
            if r is not None:
                assert r == rating[name]
                off_grid += abs(r / 0.02 - round(r / 0.02)) > 1e-6
    assert off_grid > 0


@pytest.mark.parametrize("cond", ["B|t40|l1", "B|t100"])
def test_equal_displayed_rating_equal_price(cond):
    """Under stars a white label (genuine tier) and its owner with the same displayed start-of-day rating post the same
    price, every day; and every white label's price is base x (1 + 0.4 x (displayed rating - 0.5))."""
    cfg, owner = _wl(["ratings.prior_n=3.5", *STARS], cond=cond, days=20)
    out, snaps, bad = CR.run_with_ledger(cfg)
    assert not bad
    D = len(snaps)
    lic = [s for s in snaps[-1] if snaps[-1][s]["licensed_from"] == owner]
    assert lic
    cat = {st.sid: st.category for st in BazaarEngine(cfg).stalls}
    pairs = 0
    for d in range(3, D + 1):
        shown = lambda s: B.shown(cfg, None if d == 1 else out["days"][d - 2]["brand_ratings"].get(
            out["days"][d - 1]["brands"][s]))
        own = shown(owner)
        for s in lic:
            r = shown(s)
            base = cfg.pricing.base_price_cents[cat[s]]
            assert snaps[d - 1][s]["price"] == int(round(base * (1 + 0.4 * ((0.5 if r is None else r) - 0.5))))
            if r == own:
                pairs += 1
                assert snaps[d - 1][s]["price"] == snaps[d - 1][owner]["price"]
    assert pairs > 0


# ------------------------------------------------------------------ what buyers and sellers see

def test_buyers_and_sellers_see_displayed_ratings():
    cfg, _ = _wl(["ratings.prior_n=10", *STARS], days=3)
    eng = BazaarEngine(cfg)
    for st in eng.stalls:
        st.rating = 0.9991 if st.idx % 2 else 0.7377
    seen = 0
    for p in eng.buyers[:40]:
        for row in eng.buyer_obs(p, eng.stalls, 10 ** 6, 1, False)["stalls_here"]:
            assert "tie_rank" in row
            if "rating" in row:
                assert row["rating"] in (1.0, 0.74)
                seen += 1
    assert seen
    st = eng.stalls[1]
    assert eng.seller_obs(st, [], [])["brand"]["rating"] == 1.0
    assert eng.seller_obs(eng.stalls[0], [], [])["brand"]["rating"] == 0.74


def test_exact_display_rows_unchanged():
    cfg, _ = _wl(["ratings.prior_n=10"], days=3)
    eng = BazaarEngine(cfg)
    for st in eng.stalls:
        st.rating = 0.9991
    for p in eng.buyers[:20]:
        for row in eng.buyer_obs(p, eng.stalls, 10 ** 6, 1, False)["stalls_here"]:
            assert "tie_rank" not in row
            if "rating" in row:
                assert row["rating"] == 0.9991


# ------------------------------------------------------------------ random tie-break

def test_tie_rank_is_deterministic_and_splits_a_two_way_tie():
    cfg, _ = _wl(STARS, days=3)
    a, b = BazaarEngine(cfg), BazaarEngine(cfg)
    x, y = a.stalls[0], a.stalls[1]
    first, n = 0, 0
    for day in range(1, 21):
        for e in (a, b):
            e.day, e._tie_rank = day, {}
        for p, q in zip(a.buyers, b.buyers):
            assert a.tie_rank(p, x) == b.tie_rank(q, x) and a.tie_rank(p, y) == b.tie_rank(q, y)
            first += a.tie_rank(p, x) < a.tie_rank(p, y)
            n += 1
    assert n >= 2000
    assert abs(first / n - 0.5) < 3 * 0.5 / np.sqrt(n)
    # the order comes from default_rng([seed, 29, day, buyer index])
    p = a.buyers[7]
    a.day, a._tie_rank = 5, {}
    perm = np.random.default_rng([int(cfg.seed), 29, 5, 7]).permutation(len(a.stalls))
    assert [a.tie_rank(p, st) for st in a.stalls] == [int(perm[st.idx]) for st in a.stalls]


def test_rule_buyer_breaks_ties_by_tie_rank():
    def obs(r1, r2):
        rows = [{"id": sid, "price_cents": 500, "rating": 1.0, "messages": [{"claimed_quality": 0.9, "channel": "say"}],
                 "inspected_quality": 0.9, "ask_pending": False, "tie_rank": r} for sid, r in (("s01", r1), ("s02", r2))]
        return {"you": {"profile": "local", "inspect_cost_cents": 10,
                        "task": {"budget_left_cents": 5000, "units_needed": 1, "q_req": 0.6}},
                "stalls_here": rows, "search": {"phase": "choose", "seen_elsewhere": []}}
    pick = lambda o: json.loads(RuleBuyer().act(o))["stall"]
    assert pick(obs(0, 5)) == "s01" and pick(obs(5, 0)) == "s02"
    o = obs(5, 0)
    for r in o["stalls_here"]:
        del r["tie_rank"]
    assert pick(o) == "s01"                      # no tie_rank: by stall id, as before
    o = obs(5, 0)
    del o["search"]
    assert pick(o) == "s02"                      # walk-mode buyers too


@pytest.mark.parametrize("cond", ["B|t40|l1", "B|t100"])
def test_stars_is_deterministic_and_replays(cond):
    cfg, _ = _wl(["ratings.prior_n=10", *STARS], cond=cond, days=4)
    la, lb = JsonlLog(keep=True), JsonlLog(keep=True)
    a, b = bazaar.run(cfg, log=la), bazaar.run(cfg, log=lb)
    assert dumps(a) == dumps(b) and la.lines == lb.lines
    _, new = replay(la.lines)
    assert compare_logs(la.lines, new.lines)["identical"]


def test_stars_changes_the_market():
    ex, _ = _wl(["ratings.prior_n=10"], cond="B|t100", days=12)
    st, _ = _wl(["ratings.prior_n=10", *STARS], cond="B|t100", days=12)
    assert dumps(bazaar.run(ex)) != dumps(bazaar.run(st))


@pytest.mark.parametrize("ov", ["ratings.display=stars5", "ratings.display_step=0.03", "ratings.display_step=0",
                                "ratings.display_step=1.5", "buyers.tie_break=coin"])
def test_bad_values_rejected(ov):
    with pytest.raises(ValueError):
        bazaar.run(load(overrides=[*vov("B|t100"), "market.days=2", ov, "seed=900"], mode="bazaar"))
