"""Engine 0.17.0: counterfeit entry on a fixed day (brands.counterfeit_entry "day"), a counterfeit price factor
(brands.counterfeit_price_factor) and white-label licensing (licensing.brand "white_label").

Reference: outcomes_v0160_all.json (110 cells at engine 0.16.0, 60f1ddf): every cell of outcomes_v0150_all.json
plus licensing cells (cheap, contract, owner liable) and counterfeit-reopening cells. The new keys at their
defaults must reproduce every cell byte for byte (outcome and log body), with nothing stripped."""
import hashlib
import json
import os

import pytest

from analysis.verification import overrides as vov
from engine import bazaar, benchmark
from engine import brands as B
from engine.bazaar import BazaarEngine
from engine.config import load
from engine.jsonlog import JsonlLog, dumps
from engine.runner import compare_logs, replay

HERE = os.path.join(os.path.dirname(__file__), "reference")
with open(os.path.join(HERE, "outcomes_v0160_all.json"), encoding="utf-8") as f:
    REF = json.load(f)
CELLS = REF["cells"]
DEFAULTS = ["brands.counterfeit_entry=reopen", "brands.counterfeit_day=2", "brands.counterfeit_price_factor=1.0",
            "licensing.brand=owner"]


def _run(ov, seed):
    log = JsonlLog(keep=True)
    return bazaar.run(load(overrides=[*ov, f"seed={seed}"], mode="bazaar"), log=log), log.lines


def _check(o, lines, c):
    assert dumps(o) == c["outcome"]
    assert len(lines) == c["log_lines"]
    assert hashlib.sha256("\n".join(lines[1:]).encode()).hexdigest() == c["log_body_sha256"]


def test_reference_is_0160():
    assert REF["engine_version"] == "0.16.0" and REF["commit"] == "60f1ddf" and len(CELLS) == 110


@pytest.mark.parametrize("key", sorted(CELLS))
def test_defaults_reproduce_0160(key):
    c = CELLS[key]
    o, lines = _run(c["overrides"], c["seed"])
    _check(o, lines, c)


@pytest.mark.parametrize("key", ["v0160_lic_cheap_t40|0", "v0160_lic_contract_t100|1", "v0160_cf_reopen_t100|0",
                                 "v0150_jp_t100|0"])
def test_new_keys_set_to_their_defaults_change_nothing(key):
    c = CELLS[key]
    o, lines = _run([*c["overrides"], *DEFAULTS], c["seed"])
    _check(o, lines, c)


# ------------------------------------------------------------------ helpers

def _base(seed=900, days=4, cond="B|t100", extra=()):
    return [*vov(cond), f"market.days={days}", "inspectors.detect_scale=1.0", *extra, f"seed={seed}"]


def _day_run(phi=1.0, cond="B|t100", seed=900, days=4, day=2):
    log = JsonlLog(keep=True)
    cfg = load(overrides=_base(seed, days, cond, ["brands.counterfeit_entry=day", f"brands.counterfeit_day={day}",
                                                  f"brands.counterfeit_price_factor={phi}"]), mode="bazaar")
    return bazaar.run(cfg, log=log), log.lines, cfg


def _worlds(lines):
    """{day: {sid: stall truth}} from each day's world event."""
    out, day = {}, 0
    for x in lines:
        if '"ev":"day_start"' in x:
            day = json.loads(x)["day"]
        elif '"ev":"world"' in x:
            out[day] = {s["sid"]: s for s in json.loads(x)["stalls"]}
    return out


# ------------------------------------------------------------------ counterfeit entry

@pytest.mark.parametrize("cond", ["B|t100", "B|t40|l1"])
def test_day_entry_with_phi_1_posts_exactly_the_originals_price(cond):
    o, lines, cfg = _day_run(1.0, cond)
    W = _worlds(lines)
    for d in o["days"]:
        cf = d.get("counterfeit_of", {})
        if d["day"] < 2:
            assert not cf
            continue
        dec = [s for s, st in W[d["day"]].items() if st["stype"] == "deceptive"]
        assert set(cf) == set(dec) and dec                       # every deceptive stall is a counterfeit
        holder = {d["brands"][s]: s for s in d["brands"] if s not in cf}
        for s, orig in cf.items():
            assert d["prices"][s] == d["prices"][holder[orig]]
            assert W[d["day"]][s]["price_cents"] == W[d["day"]][holder[orig]]["price_cents"]
            assert W[d["day"]][s]["q_pitch"] == W[d["day"]][holder[orig]]["q_true"]   # claims the original's Q
            assert W[d["day"]][holder[orig]]["stype"] == "genuine"
        assert d["counterfeit_below_cost"] == sum(v["below_cost"] for v in d["counterfeit_prices"].values())


def test_price_factor_scales_the_originals_price_and_flags_below_cost():
    o, lines, cfg = _day_run(0.4)
    for d in o["days"][1:]:
        cf = d["counterfeit_of"]
        holder = {d["brands"][s]: s for s in d["brands"] if s not in cf}
        for s, orig in cf.items():
            p = d["counterfeit_prices"][s]
            assert p["price_cents"] == int(round(0.4 * d["prices"][holder[orig]])) == d["prices"][s]
            assert p["below_cost"] == (p["price_cents"] < p["unit_cost_cents"])


def test_entry_copies_the_top_rated_genuine_brand_and_never_renames_after():
    o, lines, cfg = _day_run(1.0, "B|t40|l1", days=5, day=3)
    entry = next(json.loads(x)["counterfeit_entry"] for x in lines if '"ev":"day_start"' in x
                 and json.loads(x)["day"] == 3)
    prev = o["days"][1]                                          # ratings at the end of day 2
    W = _worlds(lines)[3]
    for rec in entry:
        cat = W[rec["stall"]]["category"]
        gen = [s for s, st in W.items() if st["category"] == cat and st["stype"] == "genuine"]
        score = {s: (0.5 if prev["brand_ratings"].get(prev["brands"][s]) is None
                     else prev["brand_ratings"][prev["brands"][s]]) for s in gen}
        assert score[rec["target_stall"]] == max(score.values())
        assert rec["counterfeit_of"] == prev["brands"][rec["target_stall"]] != rec["to"]
    assert [d["outcome"]["brands"]["renames"] for d in o["days"]][2:] == [0, 0, 0]
    assert sum(d["outcome"]["catches"] for d in o["days"][2:]) > 0            # caught, yet no rename
    for d in o["days"][2:]:
        assert all(o["days"][2]["brands"][s] == d["brands"][s] for s in o["days"][2]["counterfeit_of"])


def test_tourists_file_counterfeit_reviews_under_the_original():
    o, lines, cfg = _day_run(0.6, "B|t40|l1")
    cf = o["days"][1]["counterfeit_of"]
    names = o["days"][1]["brands"]
    seen = set()
    day = 0
    for x in lines:
        if '"ev":"day_start"' in x:
            day = json.loads(x)["day"]
        if day >= 2 and '"ev":"delta"' in x:
            for b in json.loads(x)["buys"]:
                if b["stall"] in cf:
                    exp = cf[b["stall"]] if b["buyer_profile"] == "tourist" else names[b["stall"]]
                    assert b["filed_under"] == exp
                    seen.add(b["buyer_profile"])
    assert "tourist" in seen and len(seen) >= 2


def test_day_entry_is_deterministic_and_replays():
    o1, l1, cfg = _day_run(0.8, days=3)
    o2, l2, _ = _day_run(0.8, days=3)
    assert dumps(o1) == dumps(o2) and l1 == l2
    _, new = replay(l1)
    assert compare_logs(l1, new.lines)["identical"]


# ------------------------------------------------------------------ white label

def _owner(cfg):
    return next(st.sid for st in sorted(BazaarEngine(cfg).stalls, key=lambda s: s.idx) if st.stype == "genuine")


def _lic_cfg(quality="contract", brand="white_label", n=3, b=2, liable=False, cond="B|t40|l1", days=4, seed=900):
    cfg = load(overrides=_base(seed, days, cond, [f"licensing.quality={quality}", f"licensing.brand={brand}",
                                                  f"licensing.owner_liable={'true' if liable else 'false'}",
                                                  "licensing.royalty=0.1"]), mode="bazaar")
    sid = _owner(cfg)
    return benchmark.licence_config(cfg, sid, (n, b)), benchmark.licence_config(cfg, sid, benchmark.NEVER), sid


def _licences(lines, day):
    return next(json.loads(x)["licences"] for x in lines if '"ev":"day_start"' in x and json.loads(x)["day"] == day)


def _strip(o):
    o = json.loads(dumps(o))
    for d in o["days"]:
        d.pop("licences", None)
        d["outcome"].pop("licensing", None)
        for v in d["outcome"]["seller_by_type"].values():
            v.pop("royalty_paid_cents", None)
            v.pop("royalty_received_cents", None)
    return o


@pytest.mark.parametrize("brand", ["white_label", "owner"])
def test_n_0_equals_never(brand):
    c, nv, sid = _lic_cfg(brand=brand, n=0)
    a, b = bazaar.run(c), bazaar.run(nv)
    assert all(not d["outcome"]["licensing"]["owners"] for d in a["days"])
    assert _strip(a) == _strip(b)


@pytest.mark.parametrize("quality", ["contract", "cheap"])
def test_white_label_licensees_take_quality_and_policy_but_a_fresh_brand(quality):
    c, nv, sid = _lic_cfg(quality=quality)
    co, _, _ = _lic_cfg(quality=quality, brand="owner")
    log, logr = JsonlLog(keep=True), JsonlLog(keep=True)
    w, r = bazaar.run(c, log=log), bazaar.run(co, log=logr)
    L, Lr = _licences(log.lines, 2), _licences(logr.lines, 2)
    assert [x["stall"] for x in L[0]["licensees"]] == [x["stall"] for x in Lr[0]["licensees"]]   # same stalls
    assert [x["q_true"] for x in L[0]["licensees"]] == [x["q_true"] for x in Lr[0]["licensees"]]  # same quality
    owner_brand = w["days"][0]["brands"][sid]
    names = [x["brand"] for x in L[0]["licensees"]]
    assert len(set(names)) == len(names) and owner_brand not in names
    W = _worlds(log.lines)
    for d in w["days"][1:]:
        assert d["outcome"]["licensing"]["owners"][sid]["royalties_cents"] == 0
        for x in L[0]["licensees"]:
            s = x["stall"]
            assert d["brands"][s] == x["brand"]
            st = W[d["day"]][s]
            assert st["q_true"] == x["q_true"] and st["q_pitch"] == W[d["day"]][sid]["q_true"]
    # prices: each white label follows its own brand's start-of-day rating by the morning rule
    cfg = load(overrides=_base(900, 4, "B|t40|l1"), mode="bazaar")
    for i, d in enumerate(w["days"][1:], start=1):
        prev = w["days"][i - 1]
        for x in L[0]["licensees"]:
            s = x["stall"]
            st = W[d["day"]][s]
            rating = None if d["day"] == 2 else prev["brand_ratings"].get(x["brand"])
            tier = {"genuine": 1.0, "deceptive": cfg.pricing.deceptive_price_factor,
                    "seconds": cfg.pricing.seconds_price_factor}[x["stype"]]
            base = cfg.pricing.base_price_cents[st["category"]]
            r_ = 0.5 if rating is None else rating
            assert d["prices"][s] == int(round(base * tier * (1 + cfg.brands.premium * (r_ - 0.5))))


def test_white_label_reviews_never_touch_the_owners_rating():
    c, nv, sid = _lic_cfg(quality="cheap", cond="B|t40|l1", days=5)
    log = JsonlLog(keep=True)
    w = bazaar.run(c, log=log)
    lic = {x["stall"]: x["brand"] for x in _licences(log.lines, 2)[0]["licensees"]}
    owner_brand = w["days"][0]["brands"][sid]
    seen = set()
    owner_filed = {}
    day = 0
    for x in log.lines:
        if '"ev":"day_start"' in x:
            day = json.loads(x)["day"]
        if '"ev":"delta"' in x:
            for b in json.loads(x)["buys"]:
                if day >= 2 and b["stall"] in lic:
                    assert b["brand"] == lic[b["stall"]] and b["filed_under"] == lic[b["stall"]] != owner_brand
                    seen.add(b["buyer_profile"])
                if b["filed_under"] == owner_brand and b["known_claims"]:
                    assert b["stall"] == sid
                    owner_filed[day] = owner_filed.get(day, 0) + b["units"]
    assert len(seen) >= 2
    for d in w["days"]:
        assert d["reviews"].get(owner_brand, [0, 0])[1] == owner_filed.get(d["day"], 0)


def test_white_label_ignores_owner_liable():
    c, nv, sid = _lic_cfg(quality="cheap", liable=True, cond="B|t100", days=5)
    w = bazaar.run(c)
    L = [d["outcome"]["licensing"]["owners"][sid] for d in w["days"][1:]]
    assert sum(x["catches_at_licensees"] for x in L) > 0
    assert sum(x["fines_at_licensees_to_owner_cents"] for x in L) == 0
    assert sum(x["fines_at_licensees_to_licensees_cents"] for x in L) > 0


def test_white_label_is_deterministic_and_replays():
    c, nv, sid = _lic_cfg(quality="cheap", days=3)
    la, lb = JsonlLog(keep=True), JsonlLog(keep=True)
    a, b = bazaar.run(c, log=la), bazaar.run(c, log=lb)
    assert dumps(a) == dumps(b) and la.lines == lb.lines
    _, new = replay(la.lines)
    assert compare_logs(la.lines, new.lines)["identical"]


# ------------------------------------------------------------------ validation

@pytest.mark.parametrize("ov", ["brands.counterfeit_entry=always", "brands.counterfeit_price_factor=0",
                                "brands.counterfeit_price_factor=-0.5", "brands.counterfeit_day=1",
                                "brands.counterfeit_day=9", "licensing.brand=generic"])
def test_bad_settings_rejected(ov):
    extra = [ov]
    if ov.startswith("brands.counterfeit_day"):
        extra.append("brands.counterfeit_entry=day")
    cfg = load(overrides=_base(900, 4, "B|t100", extra), mode="bazaar")
    if ov.startswith("licensing"):
        cfg = benchmark.licence_config(cfg, _owner(load(overrides=_base(900, 4), mode="bazaar")), (2, 2))
    with pytest.raises(ValueError):
        bazaar.run(cfg)
