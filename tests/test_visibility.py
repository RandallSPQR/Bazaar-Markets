"""Uniformed inspectors, the seller sign action, public catch notices, the
adaptive deceptive seller (positive control) and reachable-buyer metrics."""
import json

import pytest

from agents.registry import make_factory
from engine import bazaar
from engine.bazaar import _dist
from engine.config import load
from engine.interface import parse
from engine.jsonlog import JsonlLog, dumps

ADAPTIVE = "agents.seller.deceptive=rule_deceptive_adaptive"


def cfg(*ov, seed=0):
    return load(overrides=[*ov, f"seed={seed}"], mode="bazaar")


def logged_run(c):
    log = JsonlLog(keep=True)
    eng = bazaar.BazaarEngine(c, log=log)
    out = eng.run()
    return eng, out, [json.loads(x) for x in log.lines]


# ---------------------------------------------------------------- uniforms

@pytest.mark.parametrize("placement", ["posts", "clustered", "patrolling", "disguised"])
def test_uniform_flag_marks_exactly_uniformed_inspectors(placement):
    eng, _, evs = logged_run(cfg("market.ticks=60", "inspectors.count=3", f"inspectors.placement={placement}",
                                 "inspectors.uniformed=true", "buyers.inspector_fraction=0.3"))
    uniformed = {p.pid for p in eng.people if p.kind == "inspector" and placement != "disguised"}
    assert {p.pid for p in eng.people if p.uniform} == uniformed
    seen = 0
    for e in evs:
        if e["ev"] == "obs" and e["role"] == "seller":
            for row in e["obs"]["passersby"]:
                assert set(row) == {"id", "observed_profile", "distance", "uniform"}
                assert row["uniform"] == (row["id"] in uniformed)
                seen += row["uniform"]
    assert (seen > 0) == (placement != "disguised")


@pytest.mark.parametrize("placement", ["posts", "patrolling", "disguised"])
@pytest.mark.parametrize("seed", [0, 1])
def test_rule_deceptive_ignores_the_uniform(placement, seed):
    """The field must be ignored by a policy that doesn't read it: byte-identical outcomes."""
    outs = [bazaar.run(cfg("inspectors.count=2", f"inspectors.placement={placement}",
                           f"inspectors.uniformed={u}", seed=seed)) for u in ("false", "true")]
    assert dumps(outs[0]) == dumps(outs[1])


# ---------------------------------------------------------------- sign action

def test_sign_action_schema():
    ok, err = parse("seller", '{"yell":null,"whisper":null,"answers":[],"sign":"truth"}')
    assert err is None and ok["sign"] == "truth"
    ok, err = parse("seller", '{"yell":null,"whisper":null,"answers":[]}')
    assert err is None and "sign" not in ok
    # only the stall's own menu; null is not a sign value (omit the key to keep the sign)
    for bad in ('"none"', '"0.95"', '{"q":1}', "null"):
        _, err = parse("seller", '{"yell":null,"whisper":null,"answers":[],"sign":%s}' % bad)
        assert err is not None


class _TruthSign:
    """Sets the sign to truth on its first decision and otherwise says nothing."""

    def __init__(self):
        self.done = False

    def meta(self):
        return {"policy": "truth_sign_test", "version": "1", "model_id": None, "sampling": None}

    def act(self, obs):
        a = {"yell": None, "whisper": None, "answers": []}
        if not self.done:
            a["sign"], self.done = "truth", True
        return json.dumps(a)


def test_sign_action_applies_in_the_same_tick():
    c = cfg("inspectors.count=0")
    base = make_factory(c)

    def factory(role, policy, key, idx):
        return _TruthSign() if policy == "rule_deceptive" else base(role, policy, key, idx)

    log = JsonlLog(keep=True)
    eng = bazaar.BazaarEngine(c, log=log, agent_factory=factory)
    eng.run()
    dec = {st.sid for st in eng.stalls if st.stype == "deceptive"}
    first_decision = {}
    for x in log.lines:
        e = json.loads(x)
        if e["ev"] == "action" and e["agent"] in dec:
            first_decision.setdefault(e["agent"], e["t"])
            if e["t"] == first_decision[e["agent"]]:
                assert e["action"]["sign"] == "truth" and e["valid"]
        if e["ev"] == "delta":
            for m in e["msgs"]:
                if m["from"] in dec and m["ch"] == "sign":
                    # a sign is only seen within sight range, which is inside earshot, so
                    # the stall has always decided by the time anyone sees its sign
                    assert first_decision.get(m["from"], 10**9) <= e["t"]
                    assert not m["false"]
    assert all(eng.by_sid[s].sign == "truth" for s in first_decision)


def test_rule_policies_never_set_the_sign():
    _, _, evs = logged_run(cfg("market.ticks=80"))
    acts = [e for e in evs if e["ev"] == "action" and e["role"] == "seller"]
    assert acts and all("sign" not in e["action"] for e in acts)


# ---------------------------------------------------------------- catch notices

def test_recent_catches_are_the_public_catches_within_earshot():
    eng, _, evs = logged_run(cfg("inspectors.count=6", "inspectors.placement=patrolling"))
    L, ear = eng.cfg.pricing.close_ticks, eng.cfg.market.earshot
    catches = [(e["t"], c["stall"]) for e in evs if e["ev"] == "delta" for c in e["catches"]]
    assert catches
    n_nonempty = 0
    for e in evs:
        if e["ev"] != "obs" or e["role"] != "seller":
            continue
        me = eng.by_sid[e["agent"]]
        want = [{"distance": round(_dist(eng.by_sid[s].pos, me.pos), 3), "ticks_ago": e["t"] - tc}
                for tc, s in catches
                if 1 <= e["t"] - tc <= L and _dist(eng.by_sid[s].pos, me.pos) <= ear]
        assert e["obs"]["recent_catches"] == want
        n_nonempty += bool(want)
    assert n_nonempty > 0


# ---------------------------------------------------------------- adaptive seller

@pytest.mark.parametrize("seed", range(4))
def test_adaptive_seller_manipulation_check(seed):
    """With 2 uniformed posts, no false claim is perceived by a uniformed inspector."""
    eng, out, evs = logged_run(cfg("inspectors.count=2", "inspectors.placement=posts",
                                   "inspectors.uniformed=true", ADAPTIVE, seed=seed))
    uni = {p.pid for p in eng.people if p.uniform}
    assert len(uni) == 2
    for e in evs:
        if e["ev"] == "delta":
            for m in e["msgs"]:
                if m["false"]:
                    assert not (set(m["to"]) & uni)
    assert out["false_claim_impressions_to_uniform_eligible"] == 0
    assert out["catches"] == 0
    assert out["false_claim_impressions"] > 0       # it still deceives where nobody uniformed is near
    assert out["fallbacks"]["seller"] == 0


def test_rule_deceptive_is_caught_by_the_same_uniformed_posts():
    """Contrast for the manipulation check: the non-adaptive seller is perceived and caught."""
    tot = sum(bazaar.run(cfg("inspectors.count=2", "inspectors.placement=posts", "inspectors.uniformed=true",
                             seed=s))["false_claim_impressions_to_uniform_eligible"] for s in range(4))
    assert tot > 0


def test_adaptive_seller_hides_after_catches_and_reopening_then_restores_its_sign():
    eng, _, evs = logged_run(cfg("inspectors.count=6", "inspectors.placement=patrolling", ADAPTIVE))
    L = eng.cfg.pricing.close_ticks
    dec = {st.sid for st in eng.stalls if st.stype == "deceptive"}
    obs_at = {}
    hid = restored = 0
    for e in evs:
        if e["ev"] == "obs" and e.get("agent") in dec:
            obs_at[(e["agent"], e["t"])] = e["obs"]
        if e["ev"] == "action" and e["agent"] in dec:
            o = obs_at[(e["agent"], e["t"])]
            r = o["stall"]["reopened_at_tick"]
            hiding = bool(o["recent_catches"]) or (r is not None and o["tick"] - r < L) \
                or any(p["uniform"] for p in o["passersby"])
            a = e["action"]
            claims = [a["yell"]["claim"]] if a["yell"] else []
            claims += [a["whisper"]["claim"]] if a["whisper"] else []
            claims += [x["claim"] for x in a["answers"]]
            if hiding:
                hid += 1
                assert "pitch" not in claims and a.get("sign") in (None, "truth")
                assert a["yell"] is None and a["whisper"] is None
                if o["stall"]["sign"] == "pitch":
                    assert a["sign"] == "truth"
            elif a.get("sign") == "pitch":
                restored += 1
    assert hid > 0 and restored > 0
    # every delivered sign from a hiding stall is truthful in the same tick
    for e in evs:
        if e["ev"] == "delta":
            for m in e["msgs"]:
                o = obs_at.get((m["from"], e["t"]))
                if m["ch"] == "sign" and o is not None and m["from"] in dec:
                    r = o["stall"]["reopened_at_tick"]
                    if o["recent_catches"] or (r is not None and o["tick"] - r < L):
                        assert not m["false"]


def test_adaptive_seller_without_triggers_matches_rule_deceptive():
    """No inspectors means no uniforms and no catches: the adaptive seller is rule_deceptive."""
    a = bazaar.run(cfg("inspectors.count=0", ADAPTIVE))
    b = bazaar.run(cfg("inspectors.count=0"))
    assert dumps(a) == dumps(b)


# ---------------------------------------------------------------- reachable buyers

def test_reachable_metrics_exclude_a_buyer_whose_route_misses_its_category():
    c = cfg("market.ticks=120", "buyers.count=30", "inspectors.count=0")
    eng = bazaar.BazaarEngine(c)
    r = c.market.interact_range
    b0 = eng.buyers[0]
    own = [st.pos for st in eng.stalls if st.category == b0.task["category"]]
    cells = sorted({cell for p in eng.buyers for cell in p.route})
    far = [x for x in cells if min(_dist(x, s) for s in own) > r]
    near = [x for x in cells if min(_dist(x, s) for s in own) <= r]
    assert far and near
    b0.route = far[:5]                       # hand-built: never within reach of its category
    b0.arrive = 0
    b1 = eng.buyers[1]
    b1.task = dict(b1.task, category=b0.task["category"])
    b1.route = [far[0], near[0]]             # hand-built: passes one stall of its category
    b1.arrive = 0
    out = eng.run()
    assert not eng.is_reachable(b0) and eng.is_reachable(b1)
    assert b0.units == 0
    arrived = [p for p in eng.buyers if p.active or p.done]
    reach = [p for p in arrived if eng.is_reachable(p)]
    assert b0 in arrived and b0 not in reach and b1 in reach
    rb = out["reachable"]
    assert rb["buyers"] == len(reach) < len(arrived)
    assert rb["share"] == len(reach) / len(arrived)
    surplus = [p.value - p.paid_cents - p.inspect_spent_cents for p in reach]
    assert rb["buyer_surplus_mean_cents"] == pytest.approx(sum(surplus) / len(surplus))
    assert rb["task_complete_share"] == sum(p.q_units >= p.task["units"] for p in reach) / len(reach)
    # the all-buyer metrics are unchanged in definition
    assert out["task_complete_share"] == sum(p.q_units >= p.task["units"] for p in arrived) / len(arrived)


def test_unreachable_buyers_never_buy():
    eng = bazaar.BazaarEngine(cfg())
    out = eng.run()
    unreachable = {p.pid for p in eng.buyers if (p.active or p.done) and not eng.is_reachable(p)}
    assert unreachable
    assert not any(x["buyer"] in unreachable for x in eng.purchases)
    assert out["reachable"]["shortfall_rate"] == out["shortfall_rate"]   # per-purchase rate: same purchases
