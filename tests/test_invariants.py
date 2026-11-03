"""Engine invariants: accounting, determinism, replay, and that no agent
output can change ground truth."""
import json

import numpy as np
import pytest

from agents.llm_stub import SYSTEM_PROMPTS, LLMAgent
from agents.registry import make_factory
from engine import bazaar
from engine.config import load
from engine.interface import parse
from engine.jsonlog import JsonlLog
from engine.runner import compare_logs, replay, run_config

SMALL = ["market.ticks=120", "buyers.count=60"]

CONFIGS = {
    "default": [],
    "mixed_budget_random": ["buyers.budget_level=mixed", "agents.buyer=random_buyer"],
    "disguised": ["inspectors.placement=disguised", "inspectors.count=6"],
    "patrol_scattered": ["inspectors.placement=patrolling", "market.clustering=0.0", "inspectors.count=4"],
    "perfect": ["agents.buyer=perfect_buyer", "buyers.budget_level=below"],
}


def cfg_for(name, seed=0, extra=()):
    return load(overrides=SMALL + CONFIGS[name] + [f"seed={seed}", *extra], mode="bazaar")


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_accounting_identity(name):
    for seed in range(2):
        eng = bazaar.BazaarEngine(cfg_for(name, seed))
        out = eng.run()
        assert out["payments_total_cents"] == out["seller_revenue_total_cents"]
        assert sum(p["amount_cents"] for p in eng.purchases) == out["payments_total_cents"]
        for p in eng.buyers:
            assert p.paid_cents + p.inspect_spent_cents <= p.task["budget_cents"]
            assert p.units <= p.task["units"]
        for st in eng.stalls:
            assert st.revenue_cents == st.units_sold * st.price_cents
            assert st.penalties_cents == st.catches * st.penalty_cents
        assert out["inspection_spend_cents"] == sum(p.inspect_spent_cents for p in eng.buyers)


@pytest.mark.parametrize("name", ["default", "disguised", "mixed_budget_random"])
def test_determinism_byte_identical(name):
    a, b = JsonlLog(), JsonlLog()
    bazaar.run(cfg_for(name, 3), log=a)
    bazaar.run(cfg_for(name, 3), log=b)
    assert a.text() == b.text()
    c = JsonlLog()
    bazaar.run(cfg_for(name, 4), log=c)
    assert c.text() != a.text()


@pytest.mark.parametrize("name", ["default", "disguised", "mixed_budget_random", "perfect"])
def test_replay_reproduces_log(name):
    log = JsonlLog()
    bazaar.run(cfg_for(name, 5), log=log)
    _, new = replay(log.lines)
    res = compare_logs(log.lines, new.lines)
    assert res["identical"], res


def test_replay_detects_tampering():
    log = JsonlLog()
    bazaar.run(cfg_for("default", 1), log=log)
    lines = list(log.lines)
    # Change one buyer's recorded output from move_on to a purchase attempt.
    for i, line in enumerate(lines):
        e = json.loads(line)
        if e["ev"] == "raw" and e["role"] == "buyer" and '"move_on"' in (e["raw"] or ""):
            e["raw"] = json.dumps({"action": "ask", "stall": "s00"})
            lines[i] = json.dumps(e, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            break
    _, new = replay(lines)
    assert not compare_logs(lines, new.lines)["identical"]


def test_replay_cli_roundtrip(tmp_path):
    from cli import replay as replay_cli
    path = tmp_path / "run.jsonl"
    run_config(cfg_for("default", 2), log_path=str(path))
    assert replay_cli.main([str(path)]) == 0


# ---------------------------------------------------------------- ground truth

class Adversary:
    """Emits a rotating set of hostile outputs: attempts to set prices or
    quality, extra fields, malformed JSON, wrong types, unknown targets,
    over-budget purchases, crashes."""

    SELLER = [
        '{"yell":{"claim":"pitch","quality":1.0},"whisper":null,"answers":[]}',
        '{"set_price_cents":1,"yell":null}',
        '{"yell":{"claim":"truth"},"whisper":{"to":"p999","claim":"pitch"},"answers":[]}',
        '{"yell":null,"whisper":null,"answers":[{"to":"p000","claim":"pitch"}]}',
        '{"yell":{"claim":"perfect"}}',
        'not json at all',
        '{"yell":null,"whisper":null,"answers":[],"enforcement":"off"}',
        '{"yell":{"claim":"pitch"},"whisper":null,"answers":[]}',
        None,
        "CRASH",
    ]
    BUYER = [
        '{"action":"buy","stall":"s00","units":1,"price_cents":0}',
        '{"action":"buy","stall":"s99","units":1}',
        '{"action":"buy","stall":"%s","units":100}',
        '{"action":"inspect","stall":"%s","reveal":"all"}',
        '{"action":"set_quality","stall":"%s","q":1}',
        '{"action":"move_on","teleport":[0,0]}',
        '[]',
        '{"action":"ask","stall":"%s"}',
        "CRASH",
        '{"action":"buy","stall":"%s","units":1}',
    ]

    def __init__(self, role, idx):
        self.role, self.i = role, idx

    def meta(self):
        return {"policy": "adversary", "version": "test", "model_id": None, "sampling": None}

    def act(self, obs):
        table = self.SELLER if self.role == "seller" else self.BUYER
        raw = table[self.i % len(table)]
        self.i += 1
        if raw == "CRASH":
            raise RuntimeError("adversary crashed")
        if raw and "%s" in raw:
            here = obs.get("stalls_here") or [{"id": "s00"}]
            raw = raw % here[0]["id"]
        return raw


def truth_snapshot(eng):
    return json.dumps([st.truth() for st in eng.stalls], sort_keys=True)


def test_no_agent_output_changes_ground_truth():
    cfg = cfg_for("disguised", 8, ["buyers.budget_level=above"])
    ref = bazaar.BazaarEngine(cfg)
    before = truth_snapshot(ref)
    ref.run()
    assert truth_snapshot(ref) == before

    log = JsonlLog()
    adv = bazaar.BazaarEngine(cfg, log=log, agent_factory=lambda role, pol, key, idx: Adversary(role, idx))
    assert truth_snapshot(adv) == before          # the world does not depend on who the agents are
    out = adv.run()
    assert truth_snapshot(adv) == before          # and no action changed it
    events = [json.loads(x) for x in log.lines]
    world = next(e for e in events if e["ev"] == "world")
    assert json.dumps(world["stalls"], sort_keys=True) == before
    actions = [e for e in events if e["ev"] == "action"]
    assert any(not a["valid"] for a in actions) and any(a["valid"] for a in actions)
    for a in actions:
        if not a["valid"]:
            assert a["fallback"] and a["error"]
            assert a["action"] in ({"action": "move_on"}, {"yell": None, "whisper": None, "answers": []})
    # Purchases only ever happen at the engine's price, and accounting still holds.
    for p in adv.purchases:
        assert p["amount_cents"] == p["units"] * adv.by_sid[p["stall"]].price_cents
    assert out["payments_total_cents"] == out["seller_revenue_total_cents"]
    # The hostile run replays exactly too (crashes and malformed outputs included).
    _, new = replay(log.lines)
    assert compare_logs(log.lines, new.lines)["identical"]
    # Same world, same detection stream origin: inspectors and routes are unchanged.
    assert [p.route for p in adv.people] == [p.route for p in ref.people]


def test_schema_rejects_fields_that_set_market_facts():
    for raw in ['{"action":"buy","stall":"s01","units":1,"price_cents":0}',
                '{"action":"inspect","stall":"s01","quality":0.9}',
                '{"yell":{"claim":"truth","q":1}}',
                '{"yell":null,"price_cents":5}']:
        role = "buyer" if '"action"' in raw else "seller"
        action, err = parse(role, raw)
        assert action is None and err.startswith("schema"), (raw, err)


def test_only_deceptive_stalls_make_false_claims():
    log = JsonlLog()
    eng = bazaar.BazaarEngine(cfg_for("default", 0), log=log)
    eng.run()
    for line in log.lines:
        e = json.loads(line)
        if e["ev"] == "delta":
            for m in e["msgs"]:
                if m["false"]:
                    assert eng.by_sid[m["from"]].stype == "deceptive"


def test_observations_hide_privileged_facts():
    log = JsonlLog()
    bazaar.run(cfg_for("disguised", 1, ["buyers.inspector_fraction=0.3"]), log=log)
    n_seller = n_buyer = 0
    for line in log.lines:
        e = json.loads(line)
        if e["ev"] != "obs":
            continue
        s = json.dumps(e["obs"])
        assert "inspector" not in s and "q_true" not in s and "stype" not in s
        if e["role"] == "buyer":
            n_buyer += 1
            assert "oracle" not in e["obs"]
            assert "true_quality" not in s and "stall_type" not in s
        else:
            n_seller += 1
            for p in e["obs"]["passersby"]:
                assert set(p) == {"id", "observed_profile", "distance"}
    assert n_seller and n_buyer


def test_oracle_only_for_perfect_reference_buyer():
    log = JsonlLog()
    bazaar.run(cfg_for("perfect", 0), log=log)
    obs = [json.loads(x)["obs"] for x in log.lines if '"ev":"obs"' in x and '"role":"buyer"' in x]
    assert obs and all("oracle" in o for o in obs)


# ---------------------------------------------------------------- LLM stub

def test_llm_stub_requires_pinned_model():
    for bad in (None, "", "latest", "some-model-latest"):
        with pytest.raises(ValueError):
            LLMAgent(role="buyer", model_id=bad)


def test_llm_stub_never_calls_and_falls_back():
    a = LLMAgent(role="buyer", model_id="example-model-2026-01-01", max_calls=0)
    raw = a.act({"tick": 0})
    assert json.loads(raw) == {"action": "move_on"}
    assert a.calls == 0 and a.last_attempts[0]["skipped"]
    b = LLMAgent(role="seller", model_id="example-model-2026-01-01", max_calls=5)
    with pytest.raises(NotImplementedError):
        b.act({"tick": 0})


def test_llm_stub_in_engine_is_logged_as_fallback():
    cfg = load(overrides=SMALL + ["agents.buyer=llm", "market.ticks=60",
                                  'agents.params={"llm":{"model_id":"example-model-2026-01-01","max_calls":3}}'],
               mode="bazaar")
    log = JsonlLog()
    out = bazaar.run(cfg, log=log)
    # Each agent's first max_calls decisions reach the unimplemented call (agent raises ->
    # engine fallback); after that the adapter's kill switch returns move_on without calling.
    assert out["decisions"]["buyer"] > out["fallbacks"]["buyer"] > 0
    acts = [json.loads(x) for x in log.lines if '"ev":"action"' in x and '"role":"buyer"' in x]
    assert all(a["action"] == {"action": "move_on"} for a in acts)
    head = json.loads(log.lines[0])
    meta = head["agents"]["buyer:llm"]
    assert meta["model_id"] == "example-model-2026-01-01" and meta["sampling"]["max_tokens"] == 256
    raws = [json.loads(x) for x in log.lines if '"ev":"raw"' in x and '"role":"buyer"' in x]
    assert all("attempts" in r for r in raws)
    _, new = replay(log.lines)
    assert compare_logs(log.lines, new.lines)["identical"]


def test_system_prompts_carry_no_market_content():
    from engine.world import BRANDS
    for prompt in SYSTEM_PROMPTS.values():
        for names in BRANDS.values():
            assert not any(n in prompt for n in names)
        assert "grade" not in prompt.lower()


def test_agent_streams_are_separate_from_engine():
    # Swapping in random buyers (which draw from their own RNG) must not change
    # the world or routes the engine generates for the same seed.
    a = bazaar.BazaarEngine(cfg_for("default", 9))
    b = bazaar.BazaarEngine(cfg_for("mixed_budget_random", 9, ["buyers.budget_level=at"]))
    assert truth_snapshot(a) == truth_snapshot(b)
    assert [p.route for p in a.people] == [p.route for p in b.people]
    r1 = make_factory(a.cfg)("buyer", "random_buyer", "p000", 0).rng.random(4)
    r2 = make_factory(a.cfg)("buyer", "random_buyer", "p000", 0).rng.random(4)
    assert np.array_equal(r1, r2)
