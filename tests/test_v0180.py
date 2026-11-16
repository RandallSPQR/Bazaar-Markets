"""Engine 0.18.0: white labels priced at the genuine tier (licensing.white_label_tier) and rating speed
(ratings.prior_n: pseudo-reviews at 0.5 that fade at the memory rate).

Reference: outcomes_v0170_all.json (126 cells at engine 0.17.0, 1c0ed96): every cell of outcomes_v0160_all.json
plus counterfeit day-entry cells (phi 1.0 and 0.6) and white-label cells (cheap, contract). The new keys at their
defaults must reproduce every cell byte for byte (outcome and log body), with nothing stripped."""
import hashlib
import json
import os

import pytest

from analysis.verification import overrides as vov
from engine import bazaar, benchmark
from engine.bazaar import BazaarEngine
from engine.config import load
from engine.jsonlog import JsonlLog, dumps
from engine.runner import compare_logs, replay

HERE = os.path.join(os.path.dirname(__file__), "reference")
with open(os.path.join(HERE, "outcomes_v0170_all.json"), encoding="utf-8") as f:
    REF = json.load(f)
CELLS = REF["cells"]
DEFAULTS = ["licensing.white_label_tier=type", "ratings.prior_n=0"]


def _run(ov, seed):
    log = JsonlLog(keep=True)
    return bazaar.run(load(overrides=[*ov, f"seed={seed}"], mode="bazaar"), log=log), log.lines


def _check(o, lines, c):
    assert dumps(o) == c["outcome"]
    assert len(lines) == c["log_lines"]
    assert hashlib.sha256("\n".join(lines[1:]).encode()).hexdigest() == c["log_body_sha256"]


def test_reference_is_0170():
    assert REF["engine_version"] == "0.17.0" and REF["commit"] == "1c0ed96" and len(CELLS) == 126


@pytest.mark.parametrize("key", sorted(CELLS))
def test_defaults_reproduce_0170(key):
    c = CELLS[key]
    o, lines = _run(c["overrides"], c["seed"])
    _check(o, lines, c)


@pytest.mark.parametrize("key", ["v0170_wl_contract_t40|0", "v0170_wl_cheap_t100|1", "v0160_lic_contract_t100|1",
                                 "v0170_cf_day_0.6_t40|0", "v0150_jp_t100|0"])
def test_new_keys_set_to_their_defaults_change_nothing(key):
    c = CELLS[key]
    o, lines = _run([*c["overrides"], *DEFAULTS], c["seed"])
    _check(o, lines, c)


@pytest.mark.parametrize("key", ["v0160_lic_contract_t40|0", "v0160_lic_cheap_t100|1", "v0160_lic_liable_t40|1"])
def test_genuine_tier_leaves_owner_branded_licensing_unchanged(key):
    c = CELLS[key]
    o, lines = _run([*c["overrides"], "licensing.white_label_tier=genuine"], c["seed"])
    _check(o, lines, c)


# ------------------------------------------------------------------ helpers

def _base(seed=900, days=4, cond="B|t40|l1", extra=()):
    return [*vov(cond), f"market.days={days}", "inspectors.detect_scale=1.0", *extra, f"seed={seed}"]


def _owner(cfg):
    return next(st.sid for st in sorted(BazaarEngine(cfg).stalls, key=lambda s: s.idx) if st.stype == "genuine")


def _wl(quality="contract", tier="genuine", extra=(), cond="B|t40|l1", days=4, seed=900, n=3, b=2):
    cfg = load(overrides=_base(seed, days, cond, [f"licensing.quality={quality}", "licensing.brand=white_label",
                                                  "licensing.royalty=0.1", f"licensing.white_label_tier={tier}",
                                                  *extra]), mode="bazaar")
    sid = _owner(cfg)
    return benchmark.licence_config(cfg, sid, (n, b)), sid


def _worlds(lines):
    out, day = {}, 0
    for x in lines:
        if '"ev":"day_start"' in x:
            day = json.loads(x)["day"]
        elif '"ev":"world"' in x:
            out[day] = {s["sid"]: s for s in json.loads(x)["stalls"]}
    return out


def _licences(lines, day):
    return next(json.loads(x)["licences"] for x in lines if '"ev":"day_start"' in x and json.loads(x)["day"] == day)


# ------------------------------------------------------------------ white_label_tier

@pytest.mark.parametrize("quality", ["contract", "cheap"])
@pytest.mark.parametrize("cond", ["B|t40|l1", "B|t100"])
def test_genuine_tier_posts_the_owners_formula(quality, cond):
    cfg, sid = _wl(quality, cond=cond, days=5)
    log = JsonlLog(keep=True)
    w = bazaar.run(cfg, log=log)
    W = _worlds(log.lines)
    L = _licences(log.lines, 2)[0]["licensees"]
    assert any(x["stype"] == "seconds" for x in L)
    for i, d in enumerate(w["days"][1:], start=1):
        prev = w["days"][i - 1]
        for x in L:
            s = x["stall"]
            rating = None if d["day"] == 2 else prev["brand_ratings"].get(x["brand"])
            base = cfg.pricing.base_price_cents[W[d["day"]][s]["category"]]
            r_ = 0.5 if rating is None else rating
            assert d["prices"][s] == int(round(base * 1.0 * (1 + cfg.brands.premium * (r_ - 0.5))))
            own = None if d["day"] == 1 else prev["brand_ratings"].get(prev["brands"][sid])
            if rating == own:                      # same rating as the owner: exactly the owner's price
                assert d["prices"][s] == d["prices"][sid]


def test_genuine_tier_changes_only_seconds_type_white_labels():
    """With the seconds tier set to 1.0 (deceptive's is already 1.0) the two settings must agree byte for byte."""
    for q in ("contract", "cheap"):
        a, _ = _wl(q, "genuine", ["pricing.seconds_price_factor=1.0"], days=4)
        b, _ = _wl(q, "type", ["pricing.seconds_price_factor=1.0"], days=4)
        la, lb = JsonlLog(keep=True), JsonlLog(keep=True)
        oa, ob = bazaar.run(a, log=la), bazaar.run(b, log=lb)
        assert dumps(oa) == dumps(ob) and la.lines[1:] == lb.lines[1:]
    # and at the default seconds tier they differ (the key does something)
    a, _ = _wl("contract", "genuine")
    b, _ = _wl("contract", "type")
    assert dumps(bazaar.run(a)) != dumps(bazaar.run(b))


def test_genuine_tier_keeps_unit_cost():
    a, sid = _wl("cheap", "genuine", cond="B|t100", days=4)
    b, _ = _wl("cheap", "type", cond="B|t100", days=4)
    la, lb = JsonlLog(keep=True), JsonlLog(keep=True)
    bazaar.run(a, log=la), bazaar.run(b, log=lb)
    Wa, Wb = _worlds(la.lines), _worlds(lb.lines)
    for d in Wa:
        for s in Wa[d]:
            assert Wa[d][s]["unit_cost_cents"] == Wb[d][s]["unit_cost_cents"]


def test_genuine_tier_is_deterministic_and_replays():
    c, _ = _wl("cheap", "genuine", days=3)
    la, lb = JsonlLog(keep=True), JsonlLog(keep=True)
    a, b = bazaar.run(c, log=la), bazaar.run(c, log=lb)
    assert dumps(a) == dumps(b) and la.lines == lb.lines
    _, new = replay(la.lines)
    assert compare_logs(la.lines, new.lines)["identical"]


# ------------------------------------------------------------------ ratings.prior_n

def _prior(pn, cond="B|t40|l1", days=5, seed=900, extra=()):
    log = JsonlLog(keep=True)
    cfg = load(overrides=_base(seed, days, cond, [f"ratings.prior_n={pn}", *extra]), mode="bazaar")
    return bazaar.run(cfg, log=log), log.lines, cfg


@pytest.mark.parametrize("pn", [5, 40.5])
def test_prior_follows_the_rule_by_hand(pn):
    """Each day's rating is the blend of yesterday's and (honest + 0.5 w) / (rated + w), w = pn x memory^(age)."""
    o, lines, cfg = _prior(pn)
    m = cfg.ratings.memory
    w = {}                                          # brand -> remaining pseudo-review weight
    rating = {}
    for d in o["days"]:
        for name in d["brands"].values():
            w.setdefault(name, float(pn))
        for name in d["brand_ratings"]:
            w.setdefault(name, float(pn))
        for name, (h, c) in d["reviews"].items():
            share = (h + 0.5 * w[name]) / (c + w[name])
            old = rating.get(name)
            rating[name] = share if old is None else m * old + (1 - m) * share
        for name in w:
            w[name] *= m
        for name, r in d["brand_ratings"].items():
            if r is not None:
                assert r == pytest.approx(rating[name], abs=1e-12)


def test_prior_slows_a_new_brand_and_never_overshoots():
    o0, _, _ = _prior(0)
    o1, _, _ = _prior(200)
    r0 = [r for r in o0["days"][0]["brand_ratings"].values() if r is not None]
    r1 = [r for r in o1["days"][0]["brand_ratings"].values() if r is not None]
    assert max(abs(r - 0.5) for r in r1) < max(abs(r - 0.5) for r in r0)
    assert all(0.0 <= r <= 1.0 for d in o1["days"] for r in d["brand_ratings"].values() if r is not None)


def test_prior_enters_ratings_only():
    """With ratings hidden (no buyer reads them) and no reputation premium (no price reads them), and no rule
    that reads ratings, a prior changes the ratings and nothing else."""
    ex = ["ratings.mode=hidden", "brands.premium=0"]
    a, la, _ = _prior(0, extra=ex)
    b, lb, _ = _prior(150, extra=ex)
    assert dumps(a) != dumps(b)                      # ratings differ

    def strip(o):
        o = json.loads(dumps(o))
        for d in o["days"]:
            d.pop("brand_ratings", None)
            d.pop("ratings", None)
            d["outcome"].pop("rugpulls", None)
        return o
    assert strip(a) == strip(b)
    trades = lambda L: [x for x in L if '"ev":"delta"' in x]
    assert trades(la) == trades(lb)


def test_prior_reaches_white_labels_and_owner_alike():
    c0, _ = _wl("contract", "genuine", days=6)
    c1, _ = _wl("contract", "genuine", ["ratings.prior_n=300"], days=6)
    la, lb = JsonlLog(keep=True), JsonlLog(keep=True)
    a, b = bazaar.run(c0, log=la), bazaar.run(c1, log=lb)
    names = [x["brand"] for x in _licences(lb.lines, 2)[0]["licensees"]]
    assert [x["brand"] for x in _licences(la.lines, 2)[0]["licensees"]] == names
    ra, rb = a["days"][2]["brand_ratings"], b["days"][2]["brand_ratings"]
    rated = [n for n in names if ra.get(n) is not None and rb.get(n) is not None]
    assert rated and all(rb[n] < ra[n] for n in rated if ra[n] > 0.5)


def test_prior_is_deterministic_and_replays():
    c, _ = _wl("cheap", "genuine", ["ratings.prior_n=50"], days=3)
    la, lb = JsonlLog(keep=True), JsonlLog(keep=True)
    a, b = bazaar.run(c, log=la), bazaar.run(c, log=lb)
    assert dumps(a) == dumps(b) and la.lines == lb.lines
    _, new = replay(la.lines)
    assert compare_logs(la.lines, new.lines)["identical"]


# ------------------------------------------------------------------ validation

@pytest.mark.parametrize("extra", [["ratings.prior_n=-1"], ["ratings.prior_n=5", "brands.enabled=false"],
                                   ["ratings.prior_n=5", "ratings.mode=off", "brands.enabled=false"]])
def test_bad_prior_rejected(extra):
    with pytest.raises(ValueError):
        bazaar.run(load(overrides=_base(900, 3, "B|t100", extra), mode="bazaar"))


def test_bad_tier_rejected():
    c, _ = _wl("contract", "seconds")
    with pytest.raises(ValueError):
        bazaar.run(c)
