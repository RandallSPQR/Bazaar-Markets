"""Engine 0.19.0: ratings.prior_scope ("all" = 0.18.0; "new": the prior reaches only brands created on day 2 or
later) and a 60-day horizon.

Reference: outcomes_v0180_all.json (142 cells at engine 0.18.0, 4bcfaac): every cell of outcomes_v0170_all.json
plus white labels at the genuine tier, the same with ratings.prior_n 50, and ratings.prior_n 5 without licensing.
The new key at its default must reproduce every cell byte for byte (outcome and log body), with nothing stripped.

The horizon (market.horizon_known: day number and market.days in sellers' observations) is read by the
rule_genuine_rational benchmark sellers only (agents/rule_based.py, GenuineRationalSeller and V2); no other
decision reads it, so in markets without those sellers a 60-day chain must reproduce the first 30 days of a
30-day chain."""
import hashlib
import json
import os

import pytest

from analysis.verification import overrides as vov
from engine import bazaar, benchmark
from engine.bazaar import BazaarEngine
from engine.brands import BrandBook
from engine.config import load
from engine.jsonlog import JsonlLog, dumps
from engine.runner import compare_logs, replay

HERE = os.path.join(os.path.dirname(__file__), "reference")
with open(os.path.join(HERE, "outcomes_v0180_all.json"), encoding="utf-8") as f:
    REF = json.load(f)
CELLS = REF["cells"]


def _run(ov, seed):
    log = JsonlLog(keep=True)
    return bazaar.run(load(overrides=[*ov, f"seed={seed}"], mode="bazaar"), log=log), log.lines


def _check(o, lines, c):
    assert dumps(o) == c["outcome"]
    assert len(lines) == c["log_lines"]
    assert hashlib.sha256("\n".join(lines[1:]).encode()).hexdigest() == c["log_body_sha256"]


def test_reference_is_0180():
    assert REF["engine_version"] == "0.18.0" and REF["commit"] == "4bcfaac" and len(CELLS) == 142


@pytest.mark.parametrize("key", sorted(CELLS))
def test_defaults_reproduce_0180(key):
    c = CELLS[key]
    o, lines = _run(c["overrides"], c["seed"])
    _check(o, lines, c)


@pytest.mark.parametrize("key", ["v0180_prior50_wlg_contract_t40|0", "v0180_prior5_t100|1", "v0180_wlg_cheap_t40|1",
                                 "v0170_cf_day_0.6_t40|0", "v0160_lic_contract_t100|1"])
def test_scope_all_set_explicitly_changes_nothing(key):
    c = CELLS[key]
    o, lines = _run([*c["overrides"], "ratings.prior_scope=all"], c["seed"])
    _check(o, lines, c)


@pytest.mark.parametrize("key", ["v0180_wlg_contract_t40|0", "v0170_cf_day_1.0_t100|1", "v0150_jp_t100|0"])
def test_scope_new_without_a_prior_changes_nothing(key):
    c = CELLS[key]
    o, lines = _run([*c["overrides"], "ratings.prior_scope=new"], c["seed"])
    _check(o, lines, c)


# ------------------------------------------------------------------ helpers

def _base(seed=900, days=6, cond="B|t40|l1", extra=()):
    return [*vov(cond), f"market.days={days}", "inspectors.detect_scale=1.0", *extra, f"seed={seed}"]


def _owner(cfg):
    return next(st.sid for st in sorted(BazaarEngine(cfg).stalls, key=lambda s: s.idx) if st.stype == "genuine")


def _wl(extra=(), cond="B|t40|l1", days=6, seed=900, n=3, b=3, brand="white_label"):
    cfg = load(overrides=_base(seed, days, cond, ["licensing.quality=contract", f"licensing.brand={brand}",
                                                  "licensing.royalty=0.1", "licensing.white_label_tier=genuine",
                                                  *extra]), mode="bazaar")
    return benchmark.licence_config(cfg, _owner(cfg), (n, b))


def _born(o):
    """{brand name: the day it was created}: the first day whose day-end book lists it (a name enters the book when
    it is created)."""
    born = {}
    for d in o["days"]:
        for n in d["brand_ratings"]:
            born.setdefault(n, d["day"])
    return born


# ------------------------------------------------------------------ prior_scope "new"

@pytest.mark.parametrize("pn", [5, 50])
@pytest.mark.parametrize("cond", ["B|t40|l1", "B|t100"])
def test_scope_new_follows_the_rule_by_hand(pn, cond):
    """Every rating is the blend of yesterday's and (honest + 0.5 w) / (rated + w), with w = 0 for brands born on
    day 1 and w = pn x memory^(days since creation) for brands born on day 2 or later."""
    cfg = _wl([f"ratings.prior_n={pn}", "ratings.prior_scope=new"], cond=cond)
    o = bazaar.run(cfg)
    m = cfg.ratings.memory
    born = _born(o)
    assert any(d == 1 for d in born.values()) and any(d >= 2 for d in born.values())
    w = {n: (0.0 if d == 1 else float(pn)) for n, d in born.items()}
    rating, seen_new, seen_old = {}, 0, 0
    for d in o["days"]:
        for name, (h, c) in d["reviews"].items():
            share = (h + 0.5 * w[name]) / (c + w[name]) if w[name] else h / c
            old = rating.get(name)
            rating[name] = share if old is None else m * old + (1 - m) * share
            seen_new += born[name] >= 2
            seen_old += born[name] == 1
        for name in w:
            if born[name] <= d["day"]:
                w[name] *= m
        for name, r in d["brand_ratings"].items():
            if r is not None:
                assert r == rating[name]
    assert seen_new and seen_old


def test_day1_brands_rate_as_without_a_prior_until_the_first_new_brand():
    """Under scope "new", every day-1 brand's rating path equals the prior_n 0 chain's exactly through the end of the
    day the first new brand is created (white labels on day 3, or an earlier reopening rename)."""
    a = bazaar.run(_wl(["ratings.prior_n=0"]))
    b = bazaar.run(_wl(["ratings.prior_n=50", "ratings.prior_scope=new"]))
    born = _born(b)
    first = min(d for d in born.values() if d >= 2)
    assert first == min(d for d in _born(a).values() if d >= 2)
    old = [n for n, d in born.items() if d == 1]
    for d in range(first):
        assert dumps({n: a["days"][d]["brand_ratings"].get(n) for n in old}) == \
            dumps({n: b["days"][d]["brand_ratings"].get(n) for n in old})
    for d in range(first - 1):                      # before that day the chains are identical
        assert dumps(a["days"][d]) == dumps(b["days"][d])
    # the prior does act on the new brands, and the "all" scope moves the day-1 brands from day 1
    new = [n for n, d in born.items() if d >= 2]
    assert any(a["days"][-1]["brand_ratings"].get(n) != b["days"][-1]["brand_ratings"].get(n) for n in new)
    c = bazaar.run(_wl(["ratings.prior_n=50", "ratings.prior_scope=all"]))
    assert any(a["days"][0]["brand_ratings"].get(n) != c["days"][0]["brand_ratings"].get(n) for n in old)


def test_brand_created_on_day_d_gets_the_prior():
    """A white label created on day 4 starts with prior_n pseudo-reviews under scope "new"; the owner does not."""
    cfg = _wl(["ratings.prior_n=50", "ratings.prior_scope=new"], b=4, days=5)
    log = JsonlLog(keep=True)
    o = bazaar.run(cfg, log=log)
    lic = next(json.loads(x)["licences"] for x in log.lines if '"ev":"day_start"' in x and json.loads(x)["day"] == 4)
    names = [x["brand"] for x in lic[0]["licensees"]]
    owner = lic[0]["owner"]
    rev = o["days"][3]["reviews"]
    rated = [n for n in names if n in rev]
    assert rated
    for n in rated:
        h, c = rev[n]
        assert o["days"][3]["brand_ratings"][n] == (h + 0.5 * 50.0) / (c + 50.0)
    own = o["days"][0]["brands"][owner]
    first = next(d for d in o["days"] if own in d["reviews"])
    h, c = first["reviews"][own]
    assert first["brand_ratings"][own] == h / c


def test_book_gives_the_prior_by_creation_day():
    class S:                                        # a minimal stall
        def __init__(self, sid, brand):
            self.sid, self.brand, self.rating = sid, brand, None
    bk = BrandBook([S("s00", "A"), S("s01", "B")], prior_n=10, prior_scope="new")
    assert bk.prior_w == {}
    bk.add("C")                                     # created on day 1
    bk.day = 2
    bk.add("D")
    bk.add("A")                                     # an existing name is not new
    assert bk.prior_w == {"D": 10.0}
    al = BrandBook([S("s00", "A")], prior_n=10, prior_scope="all")
    al.add("C")
    assert al.prior_w == {"A": 10.0, "C": 10.0}


def test_scope_new_is_deterministic_and_replays():
    c = _wl(["ratings.prior_n=50", "ratings.prior_scope=new"], days=4)
    la, lb = JsonlLog(keep=True), JsonlLog(keep=True)
    a, b = bazaar.run(c, log=la), bazaar.run(c, log=lb)
    assert dumps(a) == dumps(b) and la.lines == lb.lines
    _, new = replay(la.lines)
    assert compare_logs(la.lines, new.lines)["identical"]


def test_bad_scope_rejected():
    with pytest.raises(ValueError):
        bazaar.run(load(overrides=_base(900, 3, "B|t100", ["ratings.prior_scope=old"]), mode="bazaar"))


# ------------------------------------------------------------------ market.days 60

def test_sellers_see_a_60_day_horizon():
    cfg = load(overrides=_base(900, 60, "B|t40|l1"), mode="bazaar")
    assert cfg.market.horizon_known
    eng = BazaarEngine(cfg, day=45)
    for st in eng.stalls:
        assert eng.seller_obs(st, [], [])["horizon"] == {"day": 45, "days": 60}


@pytest.mark.parametrize("extra", [["ratings.prior_n=0"], ["ratings.prior_n=50", "ratings.prior_scope=new"]])
def test_60_days_reproduce_the_first_30(extra):
    """No decision in this market reads the horizon (rule_honest genuine sellers, rule_deceptive, licensees,
    rule_buyer), so the first 30 days of a 60-day chain equal a 30-day chain: white labels from day 10."""
    a = bazaar.run(_wl(extra, days=30, n=6, b=10))
    b = bazaar.run(_wl(extra, days=60, n=6, b=10))
    assert len(b["days"]) == 60
    for d in range(30):
        assert dumps(a["days"][d]) == dumps(b["days"][d])
