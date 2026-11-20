"""analysis/robustness_1_1.py on synthetic per-seed values: cells, overrides, the verdict rule and PX5 flags."""
import analysis.robustness_1_1 as R
from engine.config import load


def test_cells_and_overrides_load():
    c = load(None, R.cell_overrides(("undercut", "sharp")), mode="bazaar")
    assert (c.ratings.display, c.ratings.display_step, c.buyers.tie_break, c.sellers.price_policy, c.buyers.choice,
            c.buyers.logit_rating_weight, c.buyers.logit_price_weight) == R.cell_seen(("undercut", "sharp"))
    c = load(None, R.cell_overrides(R.BASE_CELL), mode="bazaar")
    assert (c.sellers.price_policy, c.buyers.choice) == ("rating_indexed", "lexicographic")


def test_cell_verdict():
    assert R.cell_verdict({"lo": 1, "hi": 2}, +1) == "supported"
    assert R.cell_verdict({"lo": -2, "hi": -1}, +1) == "contradicted"
    assert R.cell_verdict({"lo": -1, "hi": 1}, -1) == "not supported"
    assert R.cell_verdict({"lo": -2, "hi": -1}, -1) == "supported"


def _per(cells, vals):
    eps = [e[1] for e in R.ENDPOINTS]
    return {R.cell_name(c): {e: list(vals[R.cell_name(c)].get(e, [2.0, 3.0, 2.5])) for e in eps} for c in cells}


def test_analyse_rule_and_changes():
    cells = [R.BASE_CELL, ("rating_indexed", "sharp"), ("undercut", "lex")]
    neg, pos, mixed = [-3.0, -2.0, -2.5], [2.0, 3.0, 2.5], [-1.0, 1.0, 0.5]
    vals = {"rating_indexed|lex": {"liab_t100_ds1": neg, "PK1_slope": mixed},
            "rating_indexed|sharp": {"liab_t100_ds1": neg, "PK1_slope": pos},
            "undercut|lex": {"liab_t100_ds1": mixed, "ver_t100_minus_t40l1": neg}}
    res = R.analyse(_per(cells, vals), cells, R.ENDPOINTS)
    assert res["pred"]["PX1"]["verdict"] == "not supported"              # one cell includes 0
    assert res["pred"]["PX2"]["verdict"] == "contradicted"               # one cell below 0
    assert res["pred"]["PX3"]["verdict"] == "supported"
    assert list(res["pred"]["PX4"]["cells"]) == ["rating_indexed|sharp"]
    assert res["pred"]["PX4"]["verdict"] == "supported"
    ch = {(x["endpoint"], x["cell"]) for x in res["changes"]}
    assert ("liab_t100_ds1", "undercut|lex") in ch and ("ver_t100_minus_t40l1", "undercut|lex") in ch
    assert ("PK1_slope", "rating_indexed|sharp") in ch and ("liab_t100_ds1", "rating_indexed|sharp") not in ch
