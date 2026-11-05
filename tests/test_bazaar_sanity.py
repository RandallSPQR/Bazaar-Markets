"""Bazaar sanity checks and dial behaviour."""
import numpy as np
import pytest

from engine import bazaar
from engine.config import load
from engine.detection import catch_prob
from engine.config import DetectionCfg
from engine.valuation import unit_value
from engine.config import ValuationCfg

NO_DECEPTION = 'stalls.type_shares={"genuine":0.5,"seconds":0.5}'


@pytest.mark.parametrize("buyer", ["rule_buyer", "random_reference", "informed_reference"])
def test_zero_deception_shortfall_only_from_seconds_bought_knowingly(buyer):
    n_short = 0
    for seed in range(3):
        eng = bazaar.BazaarEngine(load(overrides=[f"seed={seed}", NO_DECEPTION, f"agents.buyer={buyer}",
                                                  "buyers.budget_level=mixed"], mode="bazaar"))
        out = eng.run()
        assert out["false_claim_share_impressions"] == 0.0
        for p in eng.purchases:
            assert not p["received_false_claim"]
            if p["shortfall"]:
                n_short += 1
                assert p["stype"] == "seconds"
                # "Knowingly": the buyer had a (truthful) claim or an inspection
                # from this stall showing Q below its requirement before buying.
                known = p["known_claims"] + ([p["inspected_q"]] if p["inspected_q"] is not None else [])
                assert known and all(q < p["q_req"] for q in known)
    if buyer == "random_reference":
        assert n_short > 0   # the check is not vacuous


@pytest.mark.parametrize("form", ["graded", "step", "hazard"])
def test_every_buyer_an_inspector_deception_earns_nothing(form):
    for seed in range(3):
        out = bazaar.run(load(overrides=[f"seed={seed}", "buyers.inspector_fraction=1.0",
                                         f"detection.form={form}"], mode="bazaar"))
        dec = out["seller_by_type"]["deceptive"]
        assert dec["profit_cents"] <= 0
        assert dec["profit_cents"] < out["seller_by_type"]["genuine"]["profit_cents"]


def test_clustering_dial():
    one = bazaar.BazaarEngine(load(overrides=["market.clustering=1.0"], mode="bazaar"))
    for k, y in enumerate(one.layout.aisle_y):
        cats = {st.category for st in one.stalls if abs(st.pos[1] - y) == 1}
        assert cats == {one.cfg.market.categories[k]}
    zero = bazaar.BazaarEngine(load(overrides=["market.clustering=0.0"], mode="bazaar"))
    mixed = [len({st.category for st in zero.stalls if abs(st.pos[1] - y) == 1}) for y in zero.layout.aisle_y]
    assert max(mixed) > 1


def test_inspector_feature_correlation_dial():
    full = bazaar.BazaarEngine(load(overrides=["inspectors.count=20", "inspectors.feature_correlation=1.0"],
                                    mode="bazaar"))
    assert all(p.profile == "expert" for p in full.people if p.kind == "inspector")
    none = bazaar.BazaarEngine(load(overrides=["inspectors.count=40", "inspectors.feature_correlation=0.0"],
                                    mode="bazaar"))
    profs = [p.profile for p in none.people if p.kind == "inspector"]
    assert len(set(profs)) == 3


def test_informed_reference_beats_random_reference_here():
    # Descriptive check on the default world, not a bound: neither reference is an
    # optimum or a floor, and a study buyer may land outside them.
    surplus = {b: [] for b in ("random_reference", "rule_buyer", "informed_reference")}
    for seed in range(4):
        for b in surplus:
            surplus[b].append(bazaar.run(load(overrides=[f"seed={seed}", f"agents.buyer={b}"], mode="bazaar"))
                              ["buyer_surplus_mean_cents"])
    m = {b: np.mean(v) for b, v in surplus.items()}
    assert m["informed_reference"] > m["random_reference"]


def test_old_reference_names_still_resolve():
    a = bazaar.run(load(overrides=["seed=2", "agents.buyer=perfect_buyer"], mode="bazaar"))
    b = bazaar.run(load(overrides=["seed=2", "agents.buyer=informed_reference"], mode="bazaar"))
    assert a["buyer_surplus_mean_cents"] == b["buyer_surplus_mean_cents"]


def test_detection_forms():
    cfg = DetectionCfg()
    assert catch_prob(cfg, 0.0, "whisper", 0.0, 2.0) == 0.0          # true claims are never caught
    assert catch_prob(cfg, 0.6, "whisper", 0.0, 2.0) == 1.0
    assert catch_prob(cfg, 0.15, "whisper", 0.0, 2.0) == pytest.approx(0.5)
    assert catch_prob(cfg, 0.6, "yell", 4.0, 4.0) == 0.0              # at the edge of earshot
    assert catch_prob(cfg, 0.6, "sign", 1.0, 3.0) == pytest.approx(0.4 * 2 / 3)
    step = DetectionCfg(form="step")
    assert catch_prob(step, 0.01, "yell", 0.0, 4.0) == 0.6
    haz = DetectionCfg(form="hazard")
    assert 0 < catch_prob(haz, 0.3, "sign", 1.0, 3.0) < catch_prob(haz, 0.3, "whisper", 1.0, 3.0) < 1


def test_valuation_forms():
    v = ValuationCfg()
    assert unit_value(v, 0.8, 0.6, 1000) == pytest.approx(1300)
    assert unit_value(v, 0.3, 0.6, 1000) == pytest.approx(0.5 * 1300 * 0.5)
    assert unit_value(ValuationCfg(form="linear"), 0.3, 0.6, 1000) == pytest.approx(650)
    assert unit_value(ValuationCfg(form="concave"), 0.6, 0.6, 1000) == pytest.approx(1300)


def test_relative_scores():
    from engine.runner import run_config
    out, _ = run_config(load(overrides=["seed=1"], mode="bazaar"), normalize=True)
    assert out["surplus_rel"] is not None
    assert "surplus_floor" not in out and "surplus_norm" not in out


def test_relative_scores_can_leave_unit_interval_and_never_invent_zero_shortfall():
    from engine.metrics import relative, relative_outcomes
    assert relative(-50.0, 0.0, 100.0) == -0.5        # worse than the random reference
    assert relative(150.0, 0.0, 100.0) == 1.5         # better than the informed reference
    out = {"buyer_surplus_mean_cents": 10.0, "shortfall_rate": 0.2}
    rnd = {"buyer_surplus_mean_cents": 0.0, "shortfall_rate": 0.5}
    inf_none = {"buyer_surplus_mean_cents": 100.0, "shortfall_rate": None}   # no purchases
    r = relative_outcomes(out, rnd, inf_none)
    assert r["shortfall_rel"] is None and r["surplus_rel"] == pytest.approx(0.1)
    r = relative_outcomes({**out, "shortfall_rate": None}, rnd, {**inf_none, "shortfall_rate": 0.0})
    assert r["shortfall_rel"] is None


# ---------------------------------------------------------------- task completion

def test_task_complete_requires_qualifying_quality():
    # Every stall is deceptive, so every unit is below Q_req. Trusting tourists with
    # ample budgets buy the full quantity, yet no task is complete.
    cfg = load(overrides=['stalls.type_shares={"deceptive":1.0}', 'buyers.profile_shares={"tourist":1.0}',
                          "buyers.budget_level=above", "inspectors.count=0"], mode="bazaar")
    eng = bazaar.BazaarEngine(cfg)
    out = eng.run()
    assert out["quantity_fulfilled_share"] > 0
    assert out["task_complete_share"] == 0.0
    full = [p for p in eng.buyers if p.units >= p.task["units"]]
    assert full and all(p.q_units == 0 for p in full)


def test_task_complete_never_exceeds_quantity_fulfilled():
    for seed in range(3):
        out = bazaar.run(load(overrides=[f"seed={seed}", "buyers.budget_level=mixed"], mode="bazaar"))
        assert out["task_complete_share"] <= out["quantity_fulfilled_share"]


# ---------------------------------------------------------------- inspector-buyers

def _insp_buyers(eng):
    return [p for p in eng.buyers if p.is_inspector]


def test_inspector_knowledge_and_enforcement_are_separate():
    # Tourists never inspect, so without knowledge inspector-buyers are fooled like anyone.
    base = ["buyers.inspector_fraction=0.5", "inspectors.count=0", "seed=3",
            'buyers.profile_shares={"tourist":1.0}']
    runs = {}
    for k, e in ((True, True), (True, False), (False, True), (False, False)):
        eng = bazaar.BazaarEngine(load(overrides=base + [f"buyers.inspector_knowledge={str(k).lower()}",
                                                        f"buyers.inspector_enforcement={str(e).lower()}"],
                                       mode="bazaar"))
        out = eng.run()
        ib = {p.pid for p in _insp_buyers(eng)}
        bought = [x for x in eng.purchases if x["buyer"] in ib]
        runs[(k, e)] = dict(catches=out["catches"],
                            insp_short=sum(x["shortfall"] for x in bought) / max(1, len(bought)))
    # enforcement off -> no catches; on -> catches
    assert runs[(True, False)]["catches"] == 0 and runs[(False, False)]["catches"] == 0
    assert runs[(False, True)]["catches"] > 0
    # knowledge -> inspector-buyers never buy below their requirement
    assert runs[(True, False)]["insp_short"] == 0 and runs[(True, True)]["insp_short"] == 0
    assert runs[(False, False)]["insp_short"] > 0


def test_own_assessment_only_for_knowing_inspector_buyers():
    import json
    from engine.jsonlog import JsonlLog
    for know in (True, False):
        log = JsonlLog()
        eng = bazaar.BazaarEngine(load(overrides=["buyers.inspector_fraction=0.3", "seed=1",
                                                  f"buyers.inspector_knowledge={str(know).lower()}"],
                                       mode="bazaar"), log=log)
        eng.run()
        ib = {p.pid for p in _insp_buyers(eng)}
        seen = {True: 0, False: 0}
        for line in log.lines:
            e = json.loads(line)
            if e["ev"] == "obs" and e["role"] == "buyer":
                has = any("own_assessment" in st for st in e["obs"]["stalls_here"])
                seen[e["agent"] in ib] += has
                if e["agent"] not in ib:
                    assert not has
        assert (seen[True] > 0) == know


# ---------------------------------------------------------------- enforcement effort

def test_inspector_active_ticks_reported():
    posts = bazaar.run(load(overrides=["inspectors.count=2", "inspectors.placement=posts"], mode="bazaar"))
    disg = bazaar.run(load(overrides=["inspectors.count=2", "inspectors.placement=disguised"], mode="bazaar"))
    t = posts["inspector_active_ticks"]["dedicated"]
    assert t == 2 * load(mode="bazaar").market.ticks
    assert 0 < disg["inspector_active_ticks"]["dedicated"] < t


def test_equal_detection_given_exposure():
    from engine.config import DetectionCfg
    eq = DetectionCfg(proximity="flat", channel_weight={"whisper": 1.0, "answer": 1.0, "yell": 1.0, "sign": 1.0})
    ps = {ch: catch_prob(eq, 0.3, ch, 1.5, 3.0) for ch in ("whisper", "answer", "yell", "sign")}
    assert len(set(ps.values())) == 1
    out = bazaar.run(load("configs/detection_equal.json", mode="bazaar"))
    assert out["impressions"] > 0


# ---------------------------------------------------------------- pairing

def _population(overrides):
    eng = bazaar.BazaarEngine(load(overrides=overrides, mode="bazaar"))
    return {p.pid: (p.profile, p.task["category"], p.task["units"], p.task["q_req"], tuple(p.route), p.arrive)
            for p in eng.buyers}, eng


@pytest.mark.parametrize("treat", [["buyers.budget_level=mixed"], ["buyers.budget_level=below"],
                                   ["inspectors.count=8"], ["inspectors.count=0"],
                                   ["inspectors.placement=disguised", "inspectors.count=5"],
                                   ["buyers.inspector_fraction=0.4"], ["inspectors.feature_correlation=1.0"],
                                   ["inspectors.uniformed=true", "inspectors.recognition_range=0"],
                                   ["inspectors.uniformed=true", "inspectors.recognition_range=2.0"],
                                   ["inspectors.placement=disguised", "inspectors.count=6",
                                    "inspectors.disguised_shift=full_shift"],
                                   ["inspectors.placement=disguised", "inspectors.count=2",
                                    "inspectors.disguised_shift=full_shift"]])
def test_treatments_preserve_buyer_population(treat):
    base, _ = _population(["seed=4"])
    other, eng = _population(["seed=4"] + treat)
    assert base == other   # same ids, profiles, tasks, routes, arrivals


def test_inspector_fraction_is_nested():
    _, a = _population(["seed=4", "buyers.inspector_fraction=0.2"])
    _, b = _population(["seed=4", "buyers.inspector_fraction=0.5"])
    sa = {p.pid for p in a.buyers if p.is_inspector}
    sb = {p.pid for p in b.buyers if p.is_inspector}
    assert sa <= sb and len(sb) > len(sa)


def test_budget_treatment_changes_only_budgets():
    _, a = _population(["seed=4", "buyers.budget_level=at"])
    _, b = _population(["seed=4", "buyers.budget_level=below"])
    for p, q in zip(a.buyers, b.buyers):
        assert p.pid == q.pid and q.task["budget_cents"] < p.task["budget_cents"]
