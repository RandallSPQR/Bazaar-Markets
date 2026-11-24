"""Engine 1.2.0 (plan 2026-11-23, Stage 1): the undercut floor (sellers.undercut_floor_markup), the run-level LLM
spend ceiling (agents.budget, engine/budget.py) and the seller option sets (engine/checkpoint.py OPTION_SETS).
Defaults reproducing 1.1.0 byte for byte is checked by every reference test in the suite, which run at the defaults.
The spend tests use a mock LLM agent: no network, no provider."""
import json
import math

import pytest

import engine.brands as B
from agents.llm_stub import SYSTEM_PROMPTS, LLMAgent
from agents.registry import make_factory
from engine import ENGINE_VERSION, bazaar
from engine import budget as BUDGET
from engine import checkpoint as CP
from engine.config import load
from engine.interface import FALLBACK
from engine.jsonlog import JsonlLog
from engine.runner import run_config

REF = "configs/reference_1_0.json"


def test_version():
    assert ENGINE_VERSION == "1.2.0"


def _ref(*ov, seed=500, days=None):
    cfg = load(REF, list(ov) + ([f"market.days={days}"] if days else []))
    cfg.seed = seed
    return cfg


# ------------------------------------------------------------------ undercut floor

def _half_up(x):
    return int(math.floor(x + 0.5))


@pytest.mark.parametrize("m", [0, 0.1, 0.3])
def test_undercut_posts_its_formula_with_the_floor(m, monkeypatch):
    """Every morning of a 6-day undercut market, each own-name price is min(rivals' yesterday prices at an equal or
    higher displayed rating) - 1, floored at unit cost (m = 0, the 1.1.0 expression) or round half up(unit cost x
    (1 + m)); rating_indexed when there is no such rival."""
    cfg = _ref("sellers.price_policy=undercut", f"sellers.undercut_floor_markup={m}", days=6)
    orig = B.morning_prices
    seen = {"checked": 0, "at_floor": 0}

    def check(c, stalls, book):
        orig(c, stalls, book)
        copies = {s.sid for s in stalls if s.counterfeit_of is not None or (s.licensed_from is not None
                                                                           and not s.white_label)}
        for st in stalls:
            if st.sid in copies:
                continue
            own = B._shown_or_neutral(c, st.rating)
            ps = [s.yesterday["price_cents"] for s in stalls if s is not st and s.category == st.category
                  and s.exited_day is None and s.yesterday is not None and B._shown_or_neutral(c, s.rating) >= own - 1e-9]
            if not ps:
                exp = B.premium_price(c, st, B.shown(c, st.rating))
            else:
                floor = int(st.unit_cost_cents) if m == 0 else _half_up(st.unit_cost_cents * (1 + m))
                exp = max(min(ps) - 1, floor)
                seen["at_floor"] += exp == floor
            assert st.price_cents == exp, (st.sid, st.price_cents, exp)
            seen["checked"] += 1

    monkeypatch.setattr(B, "morning_prices", check)
    import engine.bazaar as BZ
    monkeypatch.setattr(BZ.B, "morning_prices", check)
    bazaar.run(cfg)
    assert seen["checked"] > 100 and seen["at_floor"] > 0


def test_floor_zero_is_the_default_and_reproduces_the_unset_key():
    a = JsonlLog(keep=True)
    bazaar.run(_ref("sellers.price_policy=undercut", days=3), log=a)
    b = JsonlLog(keep=True)
    bazaar.run(_ref("sellers.price_policy=undercut", "sellers.undercut_floor_markup=0", days=3), log=b)
    assert a.lines[1:] == b.lines[1:]
    assert load(REF).sellers.undercut_floor_markup == 0


def test_a_higher_floor_raises_prices(monkeypatch):
    import engine.bazaar as BZ
    orig = B.morning_prices
    pr = {}
    for m in (0, 0.3):
        got = []

        def tap(c, stalls, book):
            orig(c, stalls, book)
            got.extend(st.price_cents for st in stalls)
        monkeypatch.setattr(BZ.B, "morning_prices", tap)
        bazaar.run(_ref("sellers.price_policy=undercut", f"sellers.undercut_floor_markup={m}", days=8))
        pr[m] = sum(got) / len(got)
    assert pr[0.3] > pr[0]


@pytest.mark.parametrize("bad", [-0.1, float("inf"), True, "0.1"])
def test_floor_validation(bad):
    cfg = _ref("sellers.price_policy=undercut")
    cfg.sellers.undercut_floor_markup = bad
    with pytest.raises(ValueError, match="undercut_floor_markup"):
        B.validate_price_policy(cfg)


# ------------------------------------------------------------------ option sets

def test_option_set_v2_leaves_out_the_contract_licence_only():
    assert CP.OPTION_SETS["v1"] == CP.OPTIONS
    assert CP.OPTION_SETS["v2"] == tuple(o for o in CP.OPTIONS if o != "license_contract_6")
    assert "license_contract_6" in CP.OPTIONS        # the engine still supports it


# ------------------------------------------------------------------ spend ceiling: mock agent

class MockLLM(LLMAgent):
    """Replies with the role's fallback action (always valid); usage = the tracker's own estimate for input and the
    request's max_tokens for output, unless fixed, so every limit can be hit at an exact call."""
    made = 0

    def __init__(self, *a, usage=None, **kw):
        super().__init__(*a, **kw)
        self.usage = usage

    def _call(self, system, messages):
        MockLLM.made += 1
        u = self.usage or {"input_tokens": BUDGET.est_tokens(system, messages),
                           "output_tokens": self.sampling.max_tokens}
        return json.dumps(FALLBACK[self.role]), u


PRICES = {"mock-1": {"in": 1.0, "out": 2.0}}


def _budget(cfg, tmp_path, **kw):
    b = cfg.agents.budget
    b.prices = dict(PRICES)
    b.ledger = str(tmp_path / "ledger.jsonl")
    b.max_calls_run, b.max_tokens_run, b.max_usd_run, b.max_usd_day = 10**6, 10**9, 1e6, 1e6
    for k, v in kw.items():
        setattr(b, k, v)
    return cfg


def _agent(role="buyer", **kw):
    return MockLLM(None, role=role, model_id="mock-1", sampling={"max_tokens": 100}, **kw)


def _obs(i=0):
    return {"tick": i, "note": "x" * 40}


def _unit(a, i=0):
    """Worst-case and actual tokens and cost of one mock call on observation i."""
    tin = BUDGET.est_tokens(SYSTEM_PROMPTS[a.role], a.build_messages(_obs(i)))
    tout = a.sampling.max_tokens
    return tin, tout, (tin * 1.0 + tout * 2.0) / 1e6


def _calls_until_refused(cfg, n_max=50, agent=None):
    a = agent or _agent()
    made = 0
    with BUDGET.session(cfg, allow_spend=True) as tr:
        for i in range(n_max):
            try:
                a.act(_obs(i))
            except BUDGET.BudgetExceeded:
                return made, tr
            made += 1
    return made, tr


def test_call_limit_stops_at_exactly_the_right_call(tmp_path):
    made, tr = _calls_until_refused(_budget(_ref(), tmp_path, max_calls_run=7))
    assert made == 7 and tr.calls == 7 and tr.refused == 1 and "max_calls_run" in tr.stopped


def test_token_limit_stops_at_exactly_the_right_call(tmp_path):
    tin, tout, _ = _unit(_agent())
    made, tr = _calls_until_refused(_budget(_ref(), tmp_path, max_tokens_run=4 * (tin + tout) + (tin + tout) - 1))
    assert made == 4 and "max_tokens_run" in tr.stopped
    made, tr = _calls_until_refused(_budget(_ref(), tmp_path, max_tokens_run=5 * (tin + tout)))
    assert made == 5


def test_usd_limit_stops_at_exactly_the_right_call(tmp_path):
    _, _, c = _unit(_agent())
    made, tr = _calls_until_refused(_budget(_ref(), tmp_path, max_usd_run=3 * c + c / 2))
    assert made == 3 and "max_usd_run" in tr.stopped
    assert tr.usd == pytest.approx(3 * c)


def test_per_agent_max_calls_is_a_capped_call(tmp_path):
    made, tr = _calls_until_refused(_budget(_ref(), tmp_path), agent=_agent(max_calls=2))
    assert made == 2 and "per-agent max_calls" in tr.stopped


def test_ledger_adds_up_across_two_runs(tmp_path):
    _, _, c = _unit(_agent())
    cfg = _budget(_ref(), tmp_path, max_calls_run=3)
    for _ in range(2):
        _calls_until_refused(cfg)
    rows = [json.loads(x) for x in open(cfg.agents.budget.ledger)]
    assert len(rows) == 6 and len({r["run_id"] for r in rows}) == 2
    assert sum(r["usd"] for r in rows) == pytest.approx(6 * c)
    assert all(r["model_id"] == "mock-1" and r["output_tokens"] == 100 for r in rows)


def test_day_limit_holds_across_runs(tmp_path):
    _, _, c = _unit(_agent())
    cfg = _budget(_ref(), tmp_path, max_calls_run=2, max_usd_day=3 * c + c / 2)
    with open(cfg.agents.budget.ledger, "w") as f:      # yesterday's spend does not count
        f.write(json.dumps({"date": "2000-01-01", "usd": 99.0}) + "\n")
    made1, _ = _calls_until_refused(cfg)
    made2, tr2 = _calls_until_refused(cfg)
    assert made1 == 2 and made2 == 1 and "max_usd_day" in tr2.stopped
    made3, _ = _calls_until_refused(cfg)
    assert made3 == 0


def test_without_allow_spend_no_call_is_made(tmp_path):
    cfg = _budget(_ref(), tmp_path)
    MockLLM.made = 0
    a = _agent()
    with BUDGET.session(cfg, allow_spend=False) as tr:
        with pytest.raises(BUDGET.BudgetExceeded, match="allow-spend"):
            a.act(_obs())
    assert MockLLM.made == 0 and tr.calls == 0
    assert not (tmp_path / "ledger.jsonl").exists()


def test_default_budget_allows_no_call_even_with_allow_spend(tmp_path):
    cfg = _ref()
    cfg.agents.budget.prices = dict(PRICES)
    cfg.agents.budget.ledger = str(tmp_path / "ledger.jsonl")
    MockLLM.made = 0
    with BUDGET.session(cfg, allow_spend=True):
        with pytest.raises(BUDGET.BudgetExceeded):
            _agent().act(_obs())
    assert MockLLM.made == 0


def test_a_model_without_a_price_cannot_be_called(tmp_path):
    cfg = _budget(_ref(), tmp_path)
    cfg.agents.budget.prices = {}
    with BUDGET.session(cfg, allow_spend=True):
        with pytest.raises(BUDGET.BudgetExceeded, match="no price"):
            _agent().act(_obs())


def test_cache_hits_are_free(tmp_path):
    cfg = _budget(_ref(), tmp_path, max_calls_run=3)
    cfg.agents.budget.response_cache = str(tmp_path / "cache.jsonl")
    made, tr = _calls_until_refused(cfg)
    assert made == 3
    MockLLM.made = 0
    cfg.agents.budget.max_calls_run = 0                 # no new call may be made...
    a = _agent()
    with BUDGET.session(cfg, allow_spend=True) as tr2:
        for i in range(3):                              # ...but the three cached requests are answered
            a.act(_obs(i))
        with pytest.raises(BUDGET.BudgetExceeded):
            a.act(_obs(3))
    assert MockLLM.made == 0 and tr2.cache_hits == 3 and tr2.calls == 0 and tr2.usd == 0
    assert len(open(cfg.agents.budget.ledger).readlines()) == 3


def test_no_tracker_fails_loudly():
    with pytest.raises(BUDGET.BudgetStop):
        _agent().act(_obs())


# ------------------------------------------------------------------ spend ceiling: in the engine

def _llm_buyer_factory(cfg, made):
    base = make_factory(cfg)

    def f(role, policy, key, idx):
        if role == "buyer":
            made.append(key)
            return MockLLM(None, role="buyer", model_id="mock-1", sampling={"max_tokens": 50})
        return base(role, policy, key, idx)
    return f


def test_engine_stops_at_the_next_decision_and_marks_the_run_invalid(tmp_path):
    cfg = _budget(_ref("market.days=1"), tmp_path, max_calls_run=25)
    log = JsonlLog(keep=True)
    with BUDGET.session(cfg, allow_spend=True) as tr:
        out = bazaar.run(cfg, log=log, agent_factory=_llm_buyer_factory(cfg, []))
    assert out["invalid"] == "INVALID: budget" and "max_calls_run" in out["reason"]
    assert tr.calls == 25 and tr.refused == 1
    # 25 paid decisions, then the refused one (a fallback), then the run stops at the next decision
    assert out["stopped_at"]["decisions"]["buyer"] == 26
    assert out["stopped_at"]["fallbacks"]["buyer"] == 1
    evs = [json.loads(x) for x in log.lines]
    assert evs[-1]["ev"] == "stopped" and evs[-1]["invalid"] == "INVALID: budget"
    acts = [e for e in evs if e["ev"] == "action" and e["role"] == "buyer"]
    assert len(acts) == 26 and acts[-1]["fallback"] and not any(a["fallback"] for a in acts[:-1])
    assert "outcome" not in {e["ev"] for e in evs}


def test_multi_day_stop_keeps_completed_days(tmp_path):
    cfg = _budget(_ref("market.days=3"), tmp_path)
    made = []
    with BUDGET.session(cfg, allow_spend=True) as tr:
        full = bazaar.run(_ref("market.days=1"), agent_factory=_llm_buyer_factory(cfg, made))
    per_day = tr.calls
    cfg.agents.budget.max_calls_run = per_day + 5
    with BUDGET.session(cfg, allow_spend=True):
        out = bazaar.run(cfg, day_factories=lambda d: _llm_buyer_factory(cfg, []))
    assert out["invalid"] == "INVALID: budget" and len(out["days"]) == 1
    assert out["stopped_at"]["days_completed"] == 1 and "outcome" in out["days"][0]


def test_run_without_allow_spend_makes_zero_calls(tmp_path):
    cfg = _budget(_ref("market.days=1"), tmp_path)
    MockLLM.made = 0
    out = bazaar.run(cfg, agent_factory=_llm_buyer_factory(cfg, []))     # bazaar.run installs a no-spend tracker
    assert MockLLM.made == 0 and out["invalid"] == "INVALID: budget" and "allow-spend" in out["reason"]
    assert out["stopped_at"]["decisions"]["buyer"] == 1


def test_dry_run_counts_without_calling(tmp_path):
    cfg = _budget(_ref("market.days=1"), tmp_path)
    MockLLM.made = 0
    with BUDGET.session(cfg, dry_run=True) as tr:
        out = bazaar.run(cfg, agent_factory=_llm_buyer_factory(cfg, []))
    s = tr.summary()["dry_run"]
    assert MockLLM.made == 0 and "invalid" not in out
    assert s["calls"] > 0 and s["output_tokens"] == 50 * s["calls"]
    assert s["usd"] == pytest.approx((s["input_tokens"] * 1.0 + s["output_tokens"] * 2.0) / 1e6)
    assert not (tmp_path / "ledger.jsonl").exists()


def test_rule_runs_are_untouched_by_the_tracker():
    """A rule-agent run under an allow-spend tracker logs the same lines as without one."""
    a, b = JsonlLog(keep=True), JsonlLog(keep=True)
    bazaar.run(_ref("market.days=2"), log=a)
    cfg = _ref("market.days=2")
    with BUDGET.session(cfg, allow_spend=True):
        bazaar.run(cfg, log=b)
    strip = lambda L: [x for x in L if '"ev":"header"' not in x]
    assert strip(a.lines) == strip(b.lines)


def test_run_config_reports_spend_only_when_asked(tmp_path):
    out, _ = run_config(_ref("market.days=1"))
    assert "spend" not in out
    out, _ = run_config(_ref("market.days=1"), dry_run_cost=True)
    assert out["spend"]["dry_run"]["calls"] == 0          # rule agents: nothing to estimate
