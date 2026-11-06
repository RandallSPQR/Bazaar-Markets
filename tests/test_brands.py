"""Engine 0.8.0: brands, renames at reopening, look-alikes, reputation premium, known horizon,
bust-outs (rule_genuine_rational)."""
import hashlib
import json
import os

import numpy as np
import pytest

from engine import bazaar
from engine import brands as B
from engine.config import load
from engine.jsonlog import JsonlLog, dumps
from engine.runner import compare_logs, replay
from engine.world import BRANDS

REF = os.path.join(os.path.dirname(__file__), "reference", "outcomes_v070.json")

BR = ["brands.enabled=true", "brands.premium=0.4", "ratings.mode=public", "inspectors.placement=patrolling",
      "evolution.revise_prob=0", "evolution.mutation_prob=0", "market.horizon_known=true"]
LOOK = "agents.params.rule_deceptive.reopen=lookalike"
FRESH = "agents.params.rule_deceptive.reopen=fresh"
RATIONAL = "agents.seller.genuine=rule_genuine_rational"


def cfg(*ov, seed=0):
    return load(overrides=[*ov, f"seed={seed}"], mode="bazaar")


def _ref_cells():
    with open(REF, encoding="utf-8") as f:
        return sorted(json.load(f)["cells"].items())


@pytest.mark.parametrize("key,cell", _ref_cells())
def test_defaults_reproduce_engine_070(key, cell):
    log = JsonlLog(keep=True)
    out = bazaar.run(cfg(*cell["overrides"], seed=cell["seed"]), log=log)
    assert dumps(out) == cell["outcome"]
    assert len(log.lines) == cell["log_lines"]
    assert hashlib.sha256("\n".join(log.lines[1:]).encode()).hexdigest() == cell["log_body_sha256"]


def _events(c):
    log = JsonlLog(keep=True)
    out = bazaar.run(c, log=log)
    return out, [json.loads(x) for x in log.lines]


# ---------------------------------------------------------------- names

def test_lookalike_names_never_equal_the_original():
    used = {n for ns in BRANDS.values() for n in ns}
    for names in BRANDS.values():
        for n in names:
            for s in range(40):
                x = B.lookalike_name(n, np.random.default_rng([s, 11]), used)
                assert x != n and x not in used
                assert len(x) >= len(n)
    # many copies of one name stay distinct
    got = set()
    for s in range(60):
        x = B.lookalike_name("Kelpmoor", np.random.default_rng([s]), used | got)
        assert x not in got
        got.add(x)


def test_fresh_names_are_new():
    used = {n for ns in BRANDS.values() for n in ns}
    rng = np.random.default_rng(0)
    for c in BRANDS:
        for _ in range(200):
            n = B.fresh_name(c, rng, used)
            assert n not in used
            used.add(n)


def test_renames_in_a_run_are_unique_and_lookalikes_differ():
    out, ev = _events(cfg(*BR, LOOK, "inspectors.count=6", "market.days=4", "market.ticks=160"))
    recs = [r for d in out["days"] for r in d["renames"]]
    assert len(recs) > 5 and all(r["how"] == "lookalike" for r in recs)
    names = [r["to"] for r in recs]
    assert len(set(names)) == len(names)
    originals = {n for ns in BRANDS.values() for n in ns}
    assert not set(names) & originals
    for r in recs:
        assert r["lookalike_of"] is not None and r["to"] != r["lookalike_of"]


# ---------------------------------------------------------------- renames only at reopening

@pytest.mark.parametrize("how", ["fresh", "lookalike"])
def test_names_change_only_at_reopening(how):
    out, ev = _events(cfg(*BR, f"agents.params.rule_deceptive.reopen={how}", "inspectors.count=6",
                          "market.days=3", "market.ticks=160"))
    day, brand, reopen_at, decided_since = 1, {}, {}, {}
    n_ren = 0
    for e in ev:
        if e["ev"] == "day_start":
            day = e["day"]
            if brand:
                assert e["brands"] == brand              # nothing renames between days
            brand = dict(e["brands"])
            decided_since = {s: True for s in brand}       # a new day: only a pending rename survives
            for s in reopen_at:
                decided_since[s] = False
                reopen_at[s] = 0                           # closures end overnight
        elif e["ev"] == "obs" and e["role"] == "seller":
            sid = e["agent"]
            avail = e["obs"]["brand"]["rename_available"]
            assert avail == (sid in reopen_at and not decided_since[sid] and e["t"] >= reopen_at[sid])
        elif e["ev"] == "action" and e["role"] == "seller":
            decided_since[e["agent"]] = True
            if e["agent"] in reopen_at and e["t"] >= reopen_at[e["agent"]]:
                del reopen_at[e["agent"]]
        elif e["ev"] == "delta":
            for r in e["renames"]:
                n_ren += 1
                assert r["how"] == how and r["from"] == brand[r["stall"]]
                brand[r["stall"]] = r["to"]
            for c in e["catches"]:
                reopen_at[c["stall"]] = c["reopens"]
                decided_since[c["stall"]] = False
        elif e["ev"] == "day_end":
            assert e["brands"] == brand
    assert n_ren > 3


def test_keep_never_renames_and_genuine_never_renames():
    out, _ = _events(cfg(*BR, "inspectors.count=6", "market.days=3", "market.ticks=160"))
    assert all(not d["renames"] for d in out["days"])
    out, _ = _events(cfg(*BR, LOOK, "inspectors.count=6", "market.days=3", "market.ticks=160"))
    types = {st: t for st, t in out["days"][0]["stall_types"].items()}
    assert all(types[r["stall"]] == "deceptive" for d in out["days"] for r in d["renames"])


def test_rename_without_reopening_is_invalid():
    class Renamer:
        def meta(self):
            return {"policy": "test"}

        def act(self, obs):
            return json.dumps({"yell": None, "whisper": None, "answers": [], "rename": "fresh"})

    c = cfg(*BR, "inspectors.count=0", "market.ticks=60")

    def factory(role, policy, key, idx):
        from agents.registry import make_factory
        return Renamer() if role == "seller" else make_factory(c)(role, policy, key, idx)
    out = bazaar.run(c, agent_factory=factory)
    assert out["fallbacks"]["seller"] == out["decisions"]["seller"] > 0
    assert out["brands"]["renames"] == 0


# ---------------------------------------------------------------- look-alikes and reviews

def test_tourist_reviews_of_a_lookalike_land_on_the_original():
    c = cfg(*BR, LOOK, "inspectors.count=6", "market.days=4", "market.ticks=160")
    out, ev = _events(c)
    by_day: dict = {}
    day = 1
    for e in ev:
        if e["ev"] == "day_start":
            day = e["day"]
        elif e["ev"] == "delta":
            by_day.setdefault(day, []).extend(e["buys"])
    n_tourist_look = 0
    prev = None
    lam = c.ratings.memory
    for d in out["days"]:
        for b in by_day.get(d["day"], []):
            orig = None
            # the stall's look-alike status at purchase time
            for r in d["renames"]:
                if r["stall"] == b["stall"] and r["to"] == b["brand"]:
                    orig = r["lookalike_of"]
            if orig is None and prev is not None:
                orig = prev["lookalike_of"].get(b["stall"]) if prev["brands"].get(b["stall"]) == b["brand"] else None
            if orig is not None and b["buyer_profile"] == "tourist":
                assert b["filed_under"] == orig
                n_tourist_look += 1
            else:
                assert b["filed_under"] == b["brand"]
        # brand ratings are exactly the 0.7.0 blend, by filed name
        claimed, honest = {}, {}
        for b in by_day.get(d["day"], []):
            if b["known_claims"]:
                n = b["filed_under"]
                claimed[n] = claimed.get(n, 0) + b["units"]
                honest[n] = honest.get(n, 0) + (b["units"] if b["q_true"] >= b["known_claims"][-1] - 1e-12 else 0)
        for n, r in d["brand_ratings"].items():
            old = None if prev is None else prev["brand_ratings"].get(n)
            if n in claimed:
                share = honest[n] / claimed[n]
                assert r == pytest.approx(share if old is None else lam * old + (1 - lam) * share)
            else:
                assert r == old
        prev = d
    assert n_tourist_look > 0


def test_tourists_read_the_original_name_and_others_the_actual():
    c = cfg(*BR, LOOK, "inspectors.count=6", "market.days=3", "market.ticks=160")
    out, ev = _events(c)
    seen = {"tourist": 0, "other": 0}
    day, look0 = 1, {}

    def name_at(sid, t):
        """(actual name, original if a look-alike) at tick t: renames act in the seller step,
        before buyers decide in the same tick."""
        cur = (out["days"][day - 1]["brands_start"][sid], look0.get(sid))
        for r in out["days"][day - 1]["renames"]:
            if r["stall"] == sid and r["t"] <= t:
                cur = (r["to"], r["lookalike_of"])
        return cur
    for d, e in enumerate(out["days"]):
        e["brands_start"] = [x for x in ev if x["ev"] == "day_start"][d]["brands"]
    for e in ev:
        if e["ev"] == "day_start":
            day = e["day"]
            look0 = out["days"][day - 2]["lookalike_of"] if day > 1 else {}
        if e["ev"] == "obs" and e["role"] == "buyer":
            prof = e["obs"]["you"]["profile"]
            for row in e["obs"]["stalls_here"]:
                name, orig = name_at(row["id"], e["t"])
                if orig is None:
                    assert row["brand"] == name
                    continue
                assert row["brand"] == (orig if prof == "tourist" else name)
                for m in row["messages"]:
                    if m["tick"] >= next((r["t"] for r in out["days"][day - 1]["renames"]
                                          if r["stall"] == row["id"] and r["to"] == name), 0):
                        assert m["text"].startswith((orig if prof == "tourist" else name) + ":")
                seen["tourist" if prof == "tourist" else "other"] += 1
                if prof == "tourist":
                    assert "rating" not in row
    assert seen["tourist"] > 0 and seen["other"] > 0


def test_lookalike_copies_the_top_rated_full_price_brand_and_posts_its_price():
    out, _ = _events(cfg(*BR, LOOK, "inspectors.count=6", "market.days=4", "market.ticks=160"))
    for i, d in enumerate(out["days"]):
        start = out["days"][i - 1]["brand_ratings"] if i else {}
        types = d["stall_types"]
        brands = out["days"][i - 1]["brands"] if i else None
        for r in d["renames"]:
            assert r["target_stall"] is not None
            assert types[r["target_stall"]] != "seconds"
            score = 0.5 if r["target_rating"] is None else r["target_rating"]
            assert r["target_rating"] == start.get(r["lookalike_of"])
            if brands is not None:      # no full-price, non-look-alike brand in the category rated higher
                for sid, name in brands.items():
                    if sid == r["stall"] or types[sid] == "seconds" or sid in out["days"][i - 1]["lookalike_of"]:
                        continue
                    if _cat(sid) == _cat(r["stall"]):
                        v = start.get(name)
                        assert (0.5 if v is None else v) <= score + 1e-12
    assert any(d["renames"] for d in out["days"])


def _cat(sid):
    return int(sid[1:]) // 16          # default layout: one aisle of 16 stalls per category


def test_premium_prices_follow_start_of_day_brand_ratings():
    c = cfg(*BR, LOOK, "inspectors.count=6", "market.days=4", "market.ticks=160")
    out, ev = _events(c)
    starts = [e for e in ev if e["ev"] == "day_start"]
    eng = bazaar.BazaarEngine(c)
    tier = {st.sid: B.tier_factor(c, st) for st in eng.stalls}
    base = {st.sid: c.pricing.base_price_cents[st.category] for st in eng.stalls}
    for i, s in enumerate(starts):
        if i == 0:
            for st in eng.stalls:
                assert s["prices"][st.sid] == st.price_cents   # day 1: all unrated, neutral
            continue
        prev = out["days"][i - 1]
        for sid, name in s["brands"].items():
            if sid in prev["lookalike_of"]:
                orig = prev["lookalike_of"][sid]
                holder = [x for x, n in s["brands"].items() if n == orig and x not in prev["lookalike_of"]]
                if holder:
                    assert s["prices"][sid] == s["prices"][holder[0]]
                    continue
            r = prev["brand_ratings"].get(name)
            r = 0.5 if r is None else r
            assert s["prices"][sid] == int(round(base[sid] * tier[sid] * (1 + 0.4 * (r - 0.5))))


# ---------------------------------------------------------------- horizon and bust-outs

def test_horizon_and_yesterday_in_seller_observations():
    _, ev = _events(cfg(*BR, "market.days=3", "market.ticks=80"))
    day = 1
    for e in ev:
        if e["ev"] == "day_start":
            day = e["day"]
        if e["ev"] == "obs" and e["role"] == "seller":
            assert e["obs"]["horizon"] == {"day": day, "days": 3}
            assert (e["obs"]["yesterday"] is None) == (day == 1)


def test_with_no_premium_rational_sellers_bust_out_on_the_first_decision_day():
    """pi = 0: a name earns nothing, so its reputation is worth less than one day's harvest.
    Day 1 has no yesterday, so every genuine stall that sold on day 1 busts out on day 2."""
    c = cfg(*[x for x in BR if not x.startswith("brands.premium")], "brands.premium=0", RATIONAL,
            "inspectors.count=0", "market.days=4")
    out = bazaar.run(c)
    d1 = out["days"][0]
    gen = [s for s, t in d1["stall_types"].items() if t == "genuine"]
    sold = [s for s in gen if d1["outcome"]["brands"]["units_by_stall"][s] > 0]
    assert len(sold) >= 5
    assert not d1["bust_outs"]
    busted_day2 = {b["stall"] for b in out["days"][1]["bust_outs"]}
    assert set(sold) <= busted_day2
    assert all(b["day"] == 2 for b in out["days"][1]["bust_outs"])


def test_with_a_premium_rational_sellers_wait_and_all_bust_by_the_last_day():
    c = cfg(*BR, RATIONAL, FRESH, "inspectors.count=0", "market.days=8", "market.ticks=160")
    out = bazaar.run(c)
    first = {}
    for d in out["days"]:
        for b in d["bust_outs"]:
            first[b["stall"]] = b["day"]
    # rating 1: premium 0.2 base per unit, harvest (1.2 - 0.375..0.525) base, so busting waits until
    # 3-4 days are left (day 5 or later of 8)
    assert first and min(first.values()) >= 5
    last = out["days"][-1]
    gen = [s for s, t in last["stall_types"].items() if t == "genuine"]
    assert set(gen) == set(last["busted"]) | {s for s in gen if out["days"][-2]["outcome"]["brands"]["units_by_stall"][s] == 0}


def test_bust_out_drops_quality_keeps_name_price_and_claims():
    c = cfg(*[x for x in BR if not x.startswith("brands.premium")], "brands.premium=0", RATIONAL,
            "inspectors.count=0", "market.days=3", "market.ticks=160")
    log = JsonlLog(keep=True)
    out = bazaar.run(c, log=log)
    ev = [json.loads(x) for x in log.lines]
    busts = {b["stall"]: b for b in out["days"][1]["bust_outs"]}
    assert busts
    worlds = [e for e in ev if e["ev"] == "world"]
    w2 = {s["sid"]: s for s in worlds[1]["stalls"]}
    w3 = {s["sid"]: s for s in worlds[2]["stalls"]}
    for sid, b in busts.items():
        assert b["q_true"] < b["q_was"] and c.stalls.q_low[0] <= b["q_true"] <= c.stalls.q_low[1]
        assert b["q_true"] == B.bust_quality(c, bazaar.BazaarEngine(c).by_sid[sid])
        assert w2[sid]["q_true"] == b["q_was"]
        assert w3[sid]["q_true"] == b["q_true"] and w3[sid]["q_pitch"] == b["q_was"] and w3[sid]["sign"] == "pitch"
        assert w3[sid]["brand"] == w2[sid]["brand"]
        assert out["days"][2]["prices"][sid] == out["days"][1]["prices"][sid]
    # after busting out, every message from the stall claims the old quality
    day = 0
    for e in ev:
        if e["ev"] == "day_start":
            day = e["day"]
        if e["ev"] == "delta" and day == 3:
            for m in e["msgs"]:
                if m["from"] in busts:
                    assert m["q"] == busts[m["from"]]["q_was"] and m["false"]


def test_bust_out_invalid_for_deceptive_and_after_first_decision():
    class Buster:
        def meta(self):
            return {"policy": "test"}

        def act(self, obs):
            return json.dumps({"yell": None, "whisper": None, "answers": [], "bust_out": True})

    c = cfg(*BR, "inspectors.count=0", "market.ticks=60")

    def factory(role, policy, key, idx):
        from agents.registry import make_factory
        return Buster() if role == "seller" else make_factory(c)(role, policy, key, idx)
    eng = bazaar.BazaarEngine(c, agent_factory=factory)
    out = eng.run()
    gen = [st for st in eng.stalls if st.stype == "genuine"]
    decided = {st.sid for st in gen if st.decided_today}
    assert out["brands"]["bust_outs"] == len(decided) > 0
    assert out["fallbacks"]["seller"] == out["decisions"]["seller"] - len(decided)


# ---------------------------------------------------------------- day 1 and switches

@pytest.mark.parametrize("ov", [[LOOK, RATIONAL], [FRESH], [LOOK, 'buyers.profile_shares={"tourist":0.6,"local":0.2,"expert":0.2}']])
def test_day_one_matches_brands_off(ov):
    on = bazaar.run(cfg(*BR, *ov, "market.days=2", "market.ticks=200", seed=4))["days"][0]["outcome"]
    off_ov = [x for x in BR + ov if not x.startswith(("brands.", "market.horizon", "agents.params"))]
    off_ov = [x.replace("rule_genuine_rational", "rule_honest") for x in off_ov]
    off = bazaar.run(cfg(*off_ov, "market.ticks=200", seed=4))
    on = dict(on)
    assert on.pop("brands")["renames"] > 0 or ov == [FRESH]
    assert dumps(on) == dumps(off)


def test_brands_refuse_imitation():
    with pytest.raises(ValueError):
        bazaar.run(cfg("brands.enabled=true", "market.days=2", "market.ticks=40"))


def test_brands_log_replays():
    log = JsonlLog(keep=True)
    bazaar.run(cfg(*BR, LOOK, RATIONAL, "inspectors.count=6", "market.days=4", "market.ticks=120"), log=log)
    _, new = replay(log.lines)
    assert compare_logs(log.lines, new.lines)["identical"]
