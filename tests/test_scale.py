"""Grid refinement (market.scale): k = 1 reproduces engine 0.4.0, k = 2 keeps the world the
same in real units, and every config and agent parameter has a scaling rule."""
import hashlib
import inspect
import json
import os

import pytest

from agents.registry import POLICIES, make_factory
from engine import bazaar
from engine.config import BazaarConfig, load
from engine.jsonlog import JsonlLog, dumps
from engine.scaling import AGENT_PARAMS, DISTANCE, FIELDS, NONE, TIME, all_config_fields, scaled_config
from tests.guard_strip import changed_in_0140, strip_lines, strip_out

REF = os.path.join(os.path.dirname(__file__), "reference", "outcomes_v040.json")
ADAPTIVE = "agents.seller.deceptive=rule_deceptive_adaptive"


def cfg(*ov, seed=0):
    return load(overrides=[*ov, f"seed={seed}"], mode="bazaar")


def _ref_cells():
    with open(REF, encoding="utf-8") as f:
        return sorted(json.load(f)["cells"].items())


# ---------------------------------------------------------------- k = 1 is engine 0.4.0

@pytest.mark.parametrize("key,cell", _ref_cells())
def test_scale_one_reproduces_engine_040(key, cell):
    """Outcome and every log line after the header byte-identical to 0.4.0 (commit 3feebcf).
    The header differs only by engine_version and the new market.scale key."""
    if changed_in_0140(cell):
        pytest.skip("changed on purpose by engine 0.14.0; checked in tests/test_trapped_buyers.py")
    log = JsonlLog(keep=True)
    out = bazaar.run(cfg(*cell["overrides"], seed=cell["seed"]), log=log)
    assert dumps(strip_out(out)) == cell["outcome"]
    assert len(log.lines) == cell["log_lines"]
    assert hashlib.sha256("\n".join(strip_lines(log.lines[1:])).encode()).hexdigest() == cell["log_body_sha256"]


def test_explicit_scale_one_equals_default():
    a = bazaar.run(cfg("inspectors.placement=patrolling", "market.ticks=80"))
    b = bazaar.run(cfg("inspectors.placement=patrolling", "market.ticks=80", "market.scale=1"))
    assert dumps(a) == dumps(b)


# ---------------------------------------------------------------- every parameter has a rule

def test_every_config_field_has_a_scaling_rule():
    fields = set(all_config_fields(BazaarConfig()))
    missing = fields - set(FIELDS)
    assert not missing, f"config fields with no scaling rule in engine/scaling.py FIELDS: {sorted(missing)}"
    stale = set(FIELDS) - fields
    assert not stale, f"FIELDS lists fields that no longer exist: {sorted(stale)}"
    assert all(rule in (DISTANCE, TIME, NONE) for rule, _ in FIELDS.values())
    assert all(why for rule, why in FIELDS.values() if rule == NONE), "every 'none' rule needs a reason"


def test_every_agent_keyword_has_a_scaling_rule():
    for name, cls in POLICIES.items():
        for c in cls.__mro__:
            if c is object or "__init__" not in c.__dict__:
                continue
            params = [p for p, v in inspect.signature(c.__init__).parameters.items()
                      if p not in ("self", "rng") and v.kind not in (v.VAR_KEYWORD, v.VAR_POSITIONAL)]
            assert c.__name__ in AGENT_PARAMS, f"policy {name}: class {c.__name__} has no AGENT_PARAMS entry"
            missing = set(params) - set(AGENT_PARAMS[c.__name__])
            assert not missing, f"{c.__name__} keywords with no scaling rule: {sorted(missing)}"


def test_scaled_config_multiplies_exactly_the_distance_and_time_fields():
    base = cfg("inspectors.recognition_range=1.5")
    sc = scaled_config(cfg("inspectors.recognition_range=1.5", "market.scale=3"))
    for path, (rule, _) in FIELDS.items():
        sec, _, name = path.partition(".")
        a = getattr(getattr(base, sec), name) if name else getattr(base, sec)
        b = getattr(getattr(sc, sec), name) if name else getattr(sc, sec)
        if path == "market.scale":
            assert b == 3
        elif rule == NONE or path == "market.slot_spacing":   # slot spacing: refined via coordinates
            assert a == b, path
        else:
            assert b == 3 * a, path
    assert scaled_config(cfg("market.scale=2")).inspectors.recognition_range is None


def test_agent_time_keywords_scale():
    c = cfg("market.scale=2", 'agents.params={"rule_deceptive": {"yell_every": 5}}')
    f = make_factory(c)
    honest, dec = f("seller", "rule_honest", "s00", 0), f("seller", "rule_deceptive", "s01", 1)
    assert (honest.yell_every, honest.whisper_every) == (16, 2)
    assert (dec.yell_every, dec.whisper_every) == (10, 2)
    assert dec.yell_crowd == 3


def test_bad_scale_rejected():
    with pytest.raises(ValueError):
        bazaar.BazaarEngine(cfg("market.scale=0"))


# ---------------------------------------------------------------- k = 2: same world in real units

def _engines(*ov, seed=0):
    e1 = bazaar.BazaarEngine(cfg(*ov, seed=seed))
    e2 = bazaar.BazaarEngine(cfg(*ov, "market.scale=2", seed=seed))
    return e1, e2


@pytest.mark.parametrize("placement", ["posts", "patrolling", "clustered", "disguised"])
def test_scale_two_keeps_population_in_real_units(placement):
    e1, e2 = _engines(f"inspectors.placement={placement}", "inspectors.count=3", seed=4)
    assert len(e1.people) == len(e2.people)
    for a, b in zip(e1.people, e2.people):
        assert (a.pid, a.kind, a.profile, a.task, a.is_inspector, a.uniform, a.inspect_cost_cents) == \
               (b.pid, b.kind, b.profile, b.task, b.is_inspector, b.uniform, b.inspect_cost_cents)
        assert b.arrive == 2 * a.arrive
        assert len(b.route) == 2 * len(a.route)
        for t, cell in enumerate(a.route):
            assert b.route[2 * t] == (2 * cell[0], 2 * cell[1])
            assert b.route[2 * t + 1] in ((2 * cell[0], 2 * cell[1]),          # held last cell
                                          *(((2 * cell[0] + dx, 2 * cell[1] + dy))
                                            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))))
        assert all(abs(x0 - x1) + abs(y0 - y1) <= 1 for (x0, y0), (x1, y1) in zip(b.route, b.route[1:]))
    for s1, s2 in zip(e1.stalls, e2.stalls):
        assert s2.pos == (2 * s1.pos[0], 2 * s1.pos[1])
        assert s1.truth() | {"pos": None} == s2.truth() | {"pos": None}


def test_scale_two_world_event_is_refined():
    l1, l2 = JsonlLog(keep=True), JsonlLog(keep=True)
    bazaar.BazaarEngine(cfg("market.ticks=4"), log=l1).run()
    bazaar.BazaarEngine(cfg("market.ticks=4", "market.scale=2"), log=l2).run()
    w1, w2 = (json.loads(x.lines[1])["grid"] for x in (l1, l2))
    assert w2["W"] == 2 * (w1["W"] - 1) + 1 and w2["H"] == 2 * (w1["H"] - 1) + 1
    assert w2["aisle_y"] == [2 * y for y in w1["aisle_y"]]
    h1, h2 = (json.loads(x.lines[0])["config"]["market"] for x in (l1, l2))
    assert h2 == {**h1, "scale": 2}        # the header records the config as given


@pytest.mark.parametrize("placement,extra", [("posts", []), ("patrolling", []), ("clustered", []),
                                             ("disguised", []), ("disguised", ["inspectors.disguised_shift=full_shift"])])
@pytest.mark.parametrize("k", [2, 3])
def test_inspector_active_ticks_scale_by_exactly_k(placement, extra, k):
    ov = [f"inspectors.placement={placement}", "inspectors.count=4", *extra]
    a = bazaar.run(cfg(*ov, "market.ticks=120"))
    b = bazaar.run(cfg(*ov, "market.ticks=120", f"market.scale={k}"))
    assert b["inspector_active_ticks"]["dedicated"] == k * a["inspector_active_ticks"]["dedicated"]


def test_scale_two_recognition_zero_never_shows_a_uniform():
    log = JsonlLog(keep=True)
    eng = bazaar.BazaarEngine(cfg("market.scale=2", "inspectors.placement=posts", "inspectors.uniformed=true",
                                  "inspectors.recognition_range=0", ADAPTIVE, "market.ticks=120"), log=log)
    eng.run()
    uni = {p.pid for p in eng.people if p.uniform}
    rows = [r for x in log.lines for e in [json.loads(x)] if e["ev"] == "obs" and e["role"] == "seller"
            for r in e["obs"]["passersby"]]
    assert any(r["id"] in uni for r in rows) and not any(r["uniform"] for r in rows)


def _events(*ov):
    log = JsonlLog(keep=True)
    eng = bazaar.BazaarEngine(cfg(*ov), log=log)
    eng.run()
    return eng, [json.loads(x) for x in log.lines]


def test_scale_two_buyer_actions_hold_k_ticks():
    """A buyer that acts at tick t makes no decision at t+1 and is still on the same cell at t+1."""
    eng, ev = _events("market.scale=2", "market.ticks=160")
    acts = {}
    pos = {}
    for e in ev:
        if e["ev"] == "action" and e["role"] == "buyer":
            acts.setdefault(e["agent"], []).append((e["t"], e["action"]["action"]))
        if e["ev"] == "delta":
            for pid, xy in e["pos"].items():
                pos[(pid, e["t"])] = tuple(xy)
    n_stays = 0
    for pid, xs in acts.items():
        ts = [t for t, _ in xs]
        for (t, a), nxt in zip(xs, ts[1:] + [None]):
            if a != "move_on":
                n_stays += 1
                assert nxt is None or nxt >= t + 2
                if (pid, t + 1) in pos:
                    assert pos[(pid, t + 1)] == pos[(pid, t)]
    assert n_stays > 20
    # actions per stop are still capped at max_actions_per_stop
    assert all(st <= eng.cfg.market.max_actions_per_stop for st in [p.stop_actions for p in eng.buyers])


def test_scale_two_whispers_at_most_once_per_k_ticks():
    _, ev = _events("market.scale=2", "market.ticks=160")
    last = {}
    n = 0
    for e in ev:
        if e["ev"] == "action" and e["role"] == "seller" and e["action"]["whisper"] is not None:
            n += 1
            if e["agent"] in last:
                assert e["t"] - last[e["agent"]] >= 2
            last[e["agent"]] = e["t"]
    assert n > 20


def test_scale_two_closure_and_notices_scale():
    eng, ev = _events("market.scale=2", "inspectors.count=6", "inspectors.placement=patrolling", ADAPTIVE)
    catches = [c for e in ev if e["ev"] == "delta" for c in e["catches"]]
    assert catches
    for e in ev:
        if e["ev"] == "delta":
            for c in e["catches"]:
                assert c["reopens"] == e["t"] + 1 + 80
    windows = [rc["ticks_ago"] for e in ev if e["ev"] == "obs" and e["role"] == "seller"
               for rc in e["obs"]["recent_catches"]]
    assert windows and max(windows) <= 80 and max(windows) > 40
