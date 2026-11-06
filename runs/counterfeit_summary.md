# Counterfeits, budgets and a penalty-aware bust-out rule — stopped at calibration

Run spec "counterfeits, budgets and a penalty-aware bust-out rule (rule-based only)"; predictions
PF1–PF4 written 2026-11-06, before any run.

**Status: the calibration step failed, so the main run was not made.** No buyer count from 150 to
1000 gets 80% of genuine brands rated by day 10; every count gives 68–70%. On 2026-11-06 you chose
to stop and report rather than run anyway or lower the target. PF1–PF4 and the v2 − always-honest
question are **untested**.

## Run record

- Engine `0.9.0`, commit `3342f39` (engine commit, with tests; no engine change since).
- Calibration: `.venv/bin/python -m analysis.counterfeit --calibrate --out runs/counterfeit_calibration.json`.
  Wall clock 24.8 min on 5 workers. Load average at the end was 315, because the full test suite
  and an exploratory diagnostic run were sharing the machine. That affects timing only, not results.
- Diagnostic: `.venv/bin/python -m analysis.counterfeit --diagnose --out runs/counterfeit_calibration_diagnosis.json`
  (calibration seeds 100–104 only, counts 150 and 600).
- Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit.
- Script `analysis/counterfeit.py`. I added the `--diagnose` mode while calibration was running.
  The calibration code path did not change. The recorded script sha256 (`cfc212eb…`) is that of the
  file at the end of calibration, which is the committed file.
- Tests at `3342f39`: full suite, 354 passed (43.8 min, sharing the machine with calibration), including every 0.7.0 and 0.8.0 reference cell (gate (b) passed).
- No main-run seed (0–29) was used for calibration. Seeds 0–1 were used once, for a pipeline smoke test before calibration (see caveats).

## Engine 0.9.0 (committed before any run)

- "Look-alike" is now called "counterfeit" in the rename action, the agent parameter, and the log
  and outcome fields. `lookalike` is still accepted as an alias. 0.8.0 logs still replay: the
  comparison maps the old word to the new one, and fills config keys added since with their
  defaults.
- `buyers.budget_factor_override`: when set, every buyer's budget is units × base × the factor.
- `rule_genuine_rational_v2` is a penalty-aware benchmark. It receives the market-wide catch rate
  as a labelled privileged input. v1 is unchanged.
- Tests check:
  - all 0.7.0 and 0.8.0 reference cells, outcomes and log bodies; brands cells are compared with
    the word mapped back;
  - that a 0.8.0 brands log replays;
  - the alias;
  - the budget override;
  - a hand calculation of v2;
  - that v2 never busts out when the expected penalty exceeds the harvest gain on every remaining
    day, both in a constructed case and in a run;
  - that only v2 sees the privileged input.
- The spec's test "v2 equals v1 when the penalty is 0" was replaced by the hand-calculation test
  (decided 2026-11-06). The two rules decide differently even at zero penalty.

## Calibration (seeds 100–104)

Condition:
- budget 1.25 × base;
- tourists 40% (0.4 / 0.3 / 0.3);
- fresh reopening;
- always-honest originals;
- otherwise as the main-run design.

Ten days per chain. The criterion is the pooled share of genuine brands (18 per seed) rated at the
end of day 10. Counts were searched in ascending order: 150 to 600 in steps of 50, then 700 to
1000 in steps of 100 (decided 2026-11-06).

| buyers.count | Rated by day 10 | Share | Per seed (rated/18) |
|---|---|---|---|
| 150 | 62/90 | 68.9% | 14, 15, 12, 10, 11 |
| 200 | 62/90 | 68.9% | 14, 15, 11, 10, 12 |
| 250 | 63/90 | 70.0% | 16, 15, 11, 10, 11 |
| 300 | 62/90 | 68.9% | 14, 15, 12, 10, 11 |
| 350 | 62/90 | 68.9% | 15, 15, 11, 10, 11 |
| 400 | 62/90 | 68.9% | 14, 15, 12, 10, 11 |
| 450 | 61/90 | 67.8% | 14, 15, 11, 10, 11 |
| 500 | 62/90 | 68.9% | 14, 15, 11, 10, 12 |
| 550 | 61/90 | 67.8% | 14, 15, 11, 10, 11 |
| 600 | 62/90 | 68.9% | 14, 16, 11, 10, 11 |
| 700 | 62/90 | 68.9% | 14, 15, 11, 10, 12 |
| 800 | 63/90 | 70.0% | 14, 15, 11, 11, 12 |
| 900 | 63/90 | 70.0% | 15, 15, 11, 10, 12 |
| 1000 | 63/90 | 70.0% | 15, 15, 12, 10, 11 |

**Chosen: none.** The share does not move with the buyer count. Within each count it rises from
33% after day 1 to about 61% after day 4, and plateaus near 69% by day 7.

## Why (diagnostic, calibration seeds only; written after the calibration results)

The 28 unrated genuine stalls (of 90) are the same at 150 and at 600 buyers:

- **Distribution:** 10 fish, 4 electronics, 14–15 designer.
- **Sales:** every one of them sold **zero units** in ten days.
- **Reach:** on day 1, not one of them was ever within reach of a buyer of its category who still
  needed units.
- **Position:** all are mid-aisle (positions 4–14 on the 2–16 aisle). Every genuine stall at an
  aisle end (positions 2 and 16) is rated. Any genuine stall that sells at all gets rated: the
  smallest sellers have 1 unit.

The mechanism comes from three parts of the design:
- Buyers enter an aisle at one end.
- Each buyer needs only 1–2 units.
- Stalls never run out.

A buyer finishes at the first acceptable stall near the entrance and leaves. Stalls deeper in the
aisle are only reached by buyers who found nothing acceptable earlier, and that never happens when
a genuine or a believable deceptive stall sits near the entrance. More buyers only add sales at the
same entrance stalls. On seed 100, the two designer end stalls sold 184 and 248 units in ten days
at 150 buyers, and 618 and 1,061 at 600.

This also reinterprets one caveat from the 2026-11-06 brands run. "About half of genuine stalls
are never rated at 1.25 × base" is not thin demand. It is entrance capture, and buyer count cannot
fix it.

## What this leaves open

The spec assumed the market was thin. It is not: it is captured at the aisle entrances. Any route
to the counterfeit questions needs a new, prespecified design. The levers that act on the mechanism
are listed below for a new spec, not chosen here:

- a stock limit per stall per day;
- buyers who compare several stalls before buying;
- spreading buyers' entry points along the aisle;
- reshuffling stall positions between days.

Each changes the market the 0.8.0 results came from. Each would need an engine change, its own
tests and a new calibration.

## Caveats

- **Diagnostic timing:** the diagnostic was run and written after the calibration failed. It
  explains the failure and is exploratory.
- **Fixed horizon:** calibration chains ran 10 days. With these policies (rule_honest and
  rule_deceptive ignore the horizon), days 1–10 do not depend on D = 30.
- **Unexercised code:** the main-run analysis code (`analysis/counterfeit.py`, grids, PF
  contrasts, plots) was smoke-tested on 2 main-run seeds, 0–1. That run used the default 150 buyers and stopped at its own gate (69.4% rated). I saw
  its 2-seed contrasts while checking the code; they are not reported and they did not inform any
  decision here.
