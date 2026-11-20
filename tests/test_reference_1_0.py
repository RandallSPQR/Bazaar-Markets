"""Engine 1.0.0: the reference config (configs/reference_1_0.json), its named variants (one per published run, from
verification on) and the v1_0_0 regression digests (tests/reference/v1_0_0). See analysis/reference_1_0.py."""

import hashlib
import json
import os

import pytest

import analysis.reference_1_0 as R
from engine.config import load

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _json(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def test_reference_file_is_the_reference_market():
    assert _json(R.REF_PATH) == R.reference_dict()
    cfg = load(os.path.join(ROOT, R.REF_PATH))
    assert (cfg.ratings.display, cfg.buyers.tie_break, cfg.inspectors.count, cfg.inspectors.detect_scale,
            cfg.pricing.penalty_lag_days, cfg.brands.premium, cfg.buyers.count) == ("stars", "random", 2, 1.0, 0, 0.4, 150)


def test_every_variant_cell_rebuilds_its_run_config():
    """Each variant cell, built from the reference file, is the config its run's builder made (sha256 of the canonical
    config, recorded when the variants were derived from the run scripts)."""
    os.chdir(ROOT)
    V = _json(R.VAR_PATH)["variants"]
    assert len(V) == 12
    for name, var in V.items():
        for lab in var["cells"]:
            d = R._noseed(R.EC.to_dict(R.build(var, lab, 0)))
            assert hashlib.sha256(R.canon(d).encode()).hexdigest() == var["cell_sha256"][lab], (name, lab)


def _selected(full):
    sel = _json(R.DIG_PATH.replace("digests.json", "selection.json"))
    return [(n, x) for n, xs in sel.items() for x in (xs if full else xs[:1])]


FULL = os.environ.get("BAZAAR_FULL_REGRESSION") == "1"


@pytest.fixture
def engine_restored():
    """The study modules install observers on the engine (engine.bazaar.run, BazaarEngine methods,
    engine.days.reset_for_day) and leave them in place for the life of the process. Some of them expect a
    multi-day output, so tests that run after this one in the same process would break. Restore the engine as found."""
    import engine.bazaar as EB
    import engine.days as DAYS
    saved = [(o, dict(vars(o))) for o in (EB, DAYS, EB.BazaarEngine)]
    yield
    for o, d in saved:
        for k in [k for k in vars(o) if k not in d]:
            delattr(o, k)
        for k, v in d.items():
            if vars(o).get(k) is not v:
                setattr(o, k, v)


@pytest.mark.usefixtures("engine_restored")
@pytest.mark.parametrize("item", _selected(FULL), ids=lambda it: f"{it[0]}:{it[1]['key']}")
def test_v1_0_0_digest(item):
    """A chain of a published run, rerun with every config built from the reference file, gives the digest stored at
    1.0.0 (generated after it matched the run's saved cache record field for field). Default: the first selected chain
    of each run; BAZAAR_FULL_REGRESSION=1 runs all of them (about 1.5 h on 4 workers via
    `python -m analysis.reference_1_0 --check`)."""
    os.chdir(ROOT)
    name, x = item
    R._VARIANTS.update(_json(R.VAR_PATH)["variants"])
    R.studies()
    spec = R._tuple(name, x["spec"])
    assert R.studies()[name]["key"](spec) == x["key"]
    r = R.rerun((name, spec))
    assert r["sha256"] == _json(R.DIG_PATH)["digests"][name][x["key"]]["sha256"]
