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


@pytest.mark.parametrize("buyer", ["rule_buyer", "random_buyer", "perfect_buyer"])
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
    if buyer == "random_buyer":
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


def test_reference_buyers_bracket_study_buyer():
    surplus = {b: [] for b in ("random_buyer", "rule_buyer", "perfect_buyer")}
    for seed in range(4):
        for b in surplus:
            surplus[b].append(bazaar.run(load(overrides=[f"seed={seed}", f"agents.buyer={b}"], mode="bazaar"))
                              ["buyer_surplus_mean_cents"])
    m = {b: np.mean(v) for b, v in surplus.items()}
    assert m["perfect_buyer"] > m["random_buyer"]
    assert m["perfect_buyer"] >= m["rule_buyer"]


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


def test_normalization_bounds():
    from engine.runner import run_config
    out, _ = run_config(load(overrides=["seed=1"], mode="bazaar"), normalize=True)
    assert out["surplus_floor"] < out["surplus_ceiling"]
    assert out["surplus_norm"] is not None
