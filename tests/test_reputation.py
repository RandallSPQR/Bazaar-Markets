"""Engine 0.7.0: public ratings, switching costs, whisper ban, rugpull logging."""
import hashlib
import json
import os

import pytest

from engine import bazaar
from engine.config import load
from engine.days import update_ratings
from engine.jsonlog import JsonlLog, dumps
from engine.runner import compare_logs, replay
from tests.guard_strip import changed_in_0140, strip_lines, strip_out

REF = os.path.join(os.path.dirname(__file__), "reference", "outcomes_v060.json")


def cfg(*ov, seed=0):
    return load(overrides=[*ov, f"seed={seed}"], mode="bazaar")


def _ref_cells():
    with open(REF, encoding="utf-8") as f:
        return sorted(json.load(f)["cells"].items())


@pytest.mark.parametrize("key,cell", _ref_cells())
def test_defaults_reproduce_engine_060(key, cell):
    if changed_in_0140(cell):
        pytest.skip("changed on purpose by engine 0.14.0; checked in tests/test_trapped_buyers.py")
    log = JsonlLog(keep=True)
    out = bazaar.run(cfg(*cell["overrides"], seed=cell["seed"]), log=log)
    assert dumps(strip_out(out)) == cell["outcome"]
    assert len(log.lines) == cell["log_lines"]
    assert hashlib.sha256("\n".join(strip_lines(log.lines[1:])).encode()).hexdigest() == cell["log_body_sha256"]


# ---------------------------------------------------------------- ratings

def _events(c):
    log = JsonlLog(keep=True)
    out = bazaar.run(c, log=log)
    return out, [json.loads(x) for x in log.lines]


def test_ratings_move_only_from_realized_purchases():
    """Each day's rating change is exactly the blend of the previous rating with that day's
    share of claimed units whose true Q met the latest claim; stalls with no such units keep
    their rating."""
    c = cfg("market.days=4", "market.ticks=120", "ratings.mode=public", "inspectors.count=0")
    out, ev = _events(c)
    lam = c.ratings.memory
    prev: dict = {}
    day = 0
    buys_by_day: dict = {}
    for e in ev:
        if e["ev"] == "day_start":
            day = e["day"]
        elif e["ev"] == "delta":
            buys_by_day.setdefault(day, []).extend(e["buys"])
    for e in ev:
        if e["ev"] != "day_end":
            continue
        claimed, honest = {}, {}
        for b in buys_by_day.get(e["day"], []):
            if b["known_claims"]:
                claimed[b["stall"]] = claimed.get(b["stall"], 0) + b["units"]
                honest[b["stall"]] = honest.get(b["stall"], 0) + (b["units"] if b["q_true"] >= b["known_claims"][-1] - 1e-12 else 0)
        for sid, r in e["ratings"].items():
            if sid in claimed:
                share = honest[sid] / claimed[sid]
                want = share if prev.get(sid) is None else lam * prev[sid] + (1 - lam) * share
                assert r == pytest.approx(want)
            else:
                assert r == prev.get(sid)
        prev = dict(e["ratings"])
    assert any(v is not None for v in prev.values())


def test_update_ratings_rule():
    class S:
        def __init__(self, sid, q, rating=None):
            self.sid, self.q_true, self.rating = sid, q, rating
    a, b, c_ = S("a", 0.3), S("b", 0.9, 0.5), S("c", 0.9, 0.8)
    buys = [{"stall": "a", "units": 2, "q_true": 0.3, "known_claims": [0.3, 0.9]},   # lied: 0 of 2
            {"stall": "a", "units": 1, "q_true": 0.3, "known_claims": [0.3]},        # truthful: 1 of 1
            {"stall": "b", "units": 1, "q_true": 0.9, "known_claims": [0.9]},
            {"stall": "c", "units": 1, "q_true": 0.9, "known_claims": []}]            # no claim: not rated
    update_ratings([a, b, c_], buys, 0.7)
    assert a.rating == pytest.approx(1 / 3)
    assert b.rating == pytest.approx(0.7 * 0.5 + 0.3 * 1.0)
    assert c_.rating == 0.8


def test_tourists_never_see_ratings_and_others_do():
    out, ev = _events(cfg("market.days=3", "market.ticks=120", "ratings.mode=public", "inspectors.count=0"))
    seen = {"tourist": 0, "local": 0, "expert": 0}
    for e in ev:
        if e["ev"] == "obs" and e["role"] == "buyer":
            prof = e["obs"]["you"]["profile"]
            for row in e["obs"]["stalls_here"]:
                if "rating" in row:
                    seen[prof] += 1
            if prof == "tourist":
                assert "rating" not in json.dumps(e["obs"])
    assert seen["tourist"] == 0 and seen["local"] > 0 and seen["expert"] > 0


def test_hidden_ratings_are_computed_but_never_shown():
    out, ev = _events(cfg("market.days=3", "market.ticks=120", "ratings.mode=hidden", "inspectors.count=0"))
    assert not any(e["ev"] == "obs" and "rating" in json.dumps(e["obs"]) for e in ev)
    ends = [e for e in ev if e["ev"] == "day_end"]
    assert any(v is not None for v in ends[-1]["ratings"].values())


def test_hidden_and_public_identical_on_day_one():
    a = bazaar.run(cfg("market.days=2", "market.ticks=120", "ratings.mode=hidden", "inspectors.count=0"))
    b = bazaar.run(cfg("market.days=2", "market.ticks=120", "ratings.mode=public", "inspectors.count=0"))
    assert dumps(a["days"][0]["outcome"]) == dumps(b["days"][0]["outcome"])


def test_rule_buyer_skips_low_rated_stalls():
    from agents.rule_based import RuleBuyer
    b = RuleBuyer(rating_tau=0.5)
    obs = {"you": {"profile": "local", "inspect_cost_cents": 10,
                   "task": {"units_needed": 1, "budget_left_cents": 10_000, "q_req": 0.6}},
           "stalls_here": [{"id": "s1", "price_cents": 100, "messages": [{"claimed_quality": 0.9, "channel": "sign"}],
                            "inspected_quality": None, "ask_pending": False, "rating": 0.2}]}
    assert json.loads(b.act(obs))["action"] == "move_on"
    obs["stalls_here"][0]["rating"] = None          # unrated: neutral
    assert json.loads(b.act(obs))["action"] == "buy"
    obs["stalls_here"][0]["rating"] = 0.5
    assert json.loads(b.act(obs))["action"] == "buy"


# ---------------------------------------------------------------- medium

def test_no_whisper_is_ever_delivered_when_whispers_are_banned():
    out, ev = _events(cfg("market.whispers_allowed=false", "market.days=2", "market.ticks=160"))
    assert not any(m["ch"] == "whisper" for e in ev if e["ev"] == "delta" for m in e["msgs"])
    for d in out["days"]:
        assert d["outcome"]["impressions_by_channel"].get("whisper", 0) == 0
        assert d["outcome"]["fallbacks"]["seller"] == 0
    assert any(e["ev"] == "obs" and e["role"] == "seller" and e["obs"]["ranges"].get("whispers_allowed") is False
               for e in ev)


def test_whisper_attempt_under_ban_is_invalid():
    from engine.interface import FALLBACK

    class Whisperer:
        def meta(self):
            return {"policy": "test"}

        def act(self, obs):
            ps = [p for p in obs["passersby"] if p["distance"] <= 2]
            w = {"to": ps[0]["id"], "claim": "pitch"} if ps else None
            return json.dumps({"yell": None, "whisper": w, "answers": []})

    def factory(role, policy, key, idx):
        from agents.registry import make_factory
        return Whisperer() if role == "seller" else make_factory(c)(role, policy, key, idx)
    c = cfg("market.whispers_allowed=false", "market.ticks=80")
    out = bazaar.run(c, agent_factory=factory)
    assert out["fallbacks"]["seller"] > 0
    assert out["impressions_by_channel"].get("whisper", 0) == 0


# ---------------------------------------------------------------- switching costs and rugpulls

def test_switch_cost_is_charged_once_on_the_first_day_in_the_new_type():
    c = cfg("market.days=4", "market.ticks=100", "evolution.mutation_prob=0.5", "inspectors.count=0",
            "pricing.switch_cost_to_genuine=0.5", "pricing.switch_cost_to_deceptive=0.25")
    log = JsonlLog(keep=True)
    eng_out = bazaar.run(c, log=log)
    days = eng_out["days"]
    for a, b in zip(days, days[1:]):
        want = 0
        for s in a["switches"]:
            base = c.pricing.base_price_cents[s["category"]]
            frac = c.pricing.switch_cost_to_genuine if s["to"] == "genuine" else c.pricing.switch_cost_to_deceptive
            want += int(round(base * frac))
            assert s["switch_cost_cents"] == int(round(base * frac))
        got = sum(t["switch_cost_cents"] for t in b["outcome"]["seller_by_type"].values())
        assert got == want
    assert sum(t["switch_cost_cents"] for t in days[0]["outcome"]["seller_by_type"].values()) == 0
    for d in days:
        for t in d["outcome"]["seller_by_type"].values():
            assert t["profit_cents"] == (t["revenue_cents"] - t["cost_cents"] - t["ad_spend_cents"]
                                         - t["penalties_cents"] - t["switch_cost_cents"])


def test_rugpull_logged_exactly_for_high_rated_genuine_to_deceptive():
    out, ev = _events(cfg("market.days=6", "market.ticks=120", "ratings.mode=hidden", "inspectors.count=0",
                          "evolution.mutation_prob=0.3"))
    ends = {e["day"]: e for e in ev if e["ev"] == "day_end"}
    n = 0
    for d, e in ends.items():
        for s in e["switches"]:
            r = e["ratings"].get(s["stall"])
            want = s["from"] == "genuine" and s["to"] == "deceptive" and r is not None and r >= 0.8
            assert s["rugpull"] is want
            n += want
        assert e["rugpulls"] == sum(s["rugpull"] for s in e["switches"])
    assert n > 0


def test_ratings_persist_through_type_switches():
    out, ev = _events(cfg("market.days=5", "market.ticks=120", "ratings.mode=hidden", "inspectors.count=0",
                          "evolution.mutation_prob=0.5"))
    ends = [e for e in ev if e["ev"] == "day_end"]
    starts = {e["day"]: e for e in ev if e["ev"] == "day_start"}
    for e in ends[:-1]:
        assert starts[e["day"] + 1]["ratings"] == e["ratings"]


def test_reputation_log_replays():
    log = JsonlLog(keep=True)
    bazaar.run(cfg("market.days=3", "market.ticks=60", "ratings.mode=public", "market.whispers_allowed=false",
                   "pricing.switch_cost_to_genuine=0.5", "evolution.mutation_prob=0.3"), log=log)
    _, new = replay(log.lines)
    assert compare_logs(log.lines, new.lines)["identical"]
