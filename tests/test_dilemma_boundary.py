"""The crossover estimator in analysis/dilemma_boundary.py."""
import math

import numpy as np

from analysis.dilemma_boundary import COUNTS, bootstrap_crossing, crossing


def test_crossing_interpolates_the_first_sign_change():
    assert crossing(COUNTS, [10, 5, -5, -10, -20]) == 1.5
    assert crossing(COUNTS, [10, 8, 6, 2, -2]) == 5.0
    assert crossing(COUNTS, [10, 0, 5, -5, -5]) == 1.0          # first time it reaches 0
    assert crossing(COUNTS, [-1, -5, -5, -5, -5]) == -math.inf  # honesty already wins at 0
    assert crossing(COUNTS, [3, 3, 3, 3, 3]) == math.inf        # no crossing in 0-6


def test_bootstrap_is_reproducible_and_brackets_a_clean_crossing():
    rng = np.random.default_rng(0)
    D = np.array([10, 5, 0, -10, -20], float) + rng.normal(0, 1, (20, 5))
    a, b = bootstrap_crossing(D, COUNTS, B=2000), bootstrap_crossing(D, COUNTS, B=2000)
    assert a == b
    assert a["lo"] <= crossing(COUNTS, D.mean(0)) <= a["hi"]
    assert 1.5 < a["lo"] and a["hi"] < 2.6 and a["share_below"] == a["share_above"] == 0


def test_bootstrap_keeps_no_crossing_as_infinite_bounds():
    D = np.tile([1, 1, 1, 1, 1], (10, 1)).astype(float)
    r = bootstrap_crossing(D, COUNTS, B=200)
    assert r["lo"] == r["hi"] == math.inf and r["share_above"] == 1
