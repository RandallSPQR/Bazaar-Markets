# Status: autonomous plan 2026-11-28

Plan: `runs/plan_autonomous_2026-11-28.md`, preregistered at 9751d0c (2026-11-27) and pushed. Aisles rerun (Runs A and B) with fixed costs calibrated to a net-margin target, gain as a share of honest revenue, 9 sampled stalls per seed, fresh seeds. Rules of `runs/plan_autonomous_2026-11-19.md`: 7 workers at normal priority, `caffeinate -i`, blocks ≤ 10 h, STATUS and a ping at each checkpoint. No LLM API calls; no files of the Week 2 battery touched (this plan writes only `analysis/aisles_rerun.py`, `runs/aisles_r_*`, `runs/pilot_aisles_r/`, its summaries, `runs/REPORT_2026-12b.md` and this file). Randall (2026-11-28): push the result commits and any tag at C3. The previous plan's status is archived in `runs/STATUS_2026-11-27.md`.

| | |
|---|---|
| Stage | pilot |
| Running | – |
| Last gate | – |
| Next step | pilot (calibration on 900–904, gates on 900–902) → launch if all gates pass |

## Checkpoints

| Checkpoint | When | Result |
|---|---|---|
| C1 | Calibration and pilot passed; launch | – |
| C2 | Summaries of A and B | – |
| C3 | `runs/REPORT_2026-12b.md`; push | – |

## Log

- 2026-11-28: engine unchanged at 1.3.1 (no net-margin key needed): the plan's change 1 is made in the calibration script, `analysis/aisles_rerun.py`, with the 1.3.1 keys (fixed_cost_share 1.0, baseline_gross_by_type_cents = the calibrated daily fixed cost by type). Tests: `tests/test_v130.py` and `tests/test_v131.py` 29/29 (the full suite passed at 1.3.1 on 2026-11-26, 9023acf). Smoke test before any result (B|cash20|a0|ds0, seed 900, calibration from seed 900 only): realised genuine net margins 0.0199 / 0.030 / 0.300 against targets 0.02 / 0.03 / 0.30; continued and full chains identical (5 bust days and never).
- 2026-11-28, deviations of plan 2026-11-28, decided before any result of this plan (also in the script's docstring):
  - **D1 (implementation).** Each bust-out chain continues from a copy of its never chain's state after day b − 1, under the bust-out config, instead of simulating days 1..b − 1 again. The output is the full chain's (the stall behaves as in the never chain before day b); checked chain for chain by gate G2e on the pilot, and before any result on 20 chains of 11-27 cells (all identical, including a stall that exited before its bust-out day). It cuts the run from about 37 h to about 7 h.
  - **D2 (profile).** "Per category, profile and type": in Run A each of the four synthetic profiles (margin × verifiability) at its margin's target (thin 2%, fat 30%); in Run B the realistic profile per category (2%, 3%, 30%). Every stall type is calibrated to its category's target, floored at 0.
  - **D3 (other calibration).** Start cash, the credit limit and the rent tables are calibrated as in plan 2026-11-27 (Run A per cell, Run B per ds), on the plan's calibration seeds 900–904; only the fixed cost comes from the t40 ds 0 α 0 scenario of each profile.
  - **D4 (sample).** 3 genuine stalls per aisle drawn without replacement, `rng.choice(n, 3, replace=False)`, per aisle in the order fish, electronics, designer from one `default_rng([seed, 17])`.
  - **D5 (net margin).** (revenue − unit cost − ad spend − fixed cost) ÷ revenue, a ratio of sums over the type's stall-days in the market.
  - **D6 (gates).** G2 = G2a (1.2.0 defaults reproduce), G2b (cost targets and the fixed cost charged as calibrated), G2c (calibration rerun and recalculation identical), G2e (D1 continuation identity, one stall × 5 bust days + never in each of the 24 cells), G2m (realised genuine net margin within ±1 point of target per category in the calibration-condition cells A|·|·|t40|ds0 and B|cash20|a0|ds0, pooled over the pilot seeds, or the floor binds). G6 confirmatory cells: Run A t40 ds 0 and ds 1, Run B ds 0 α 0. G4 (50%) is reported, not a gate.
  - **Noted, not a deviation.** In the smoke calibration, seconds stalls' margin before any fixed cost is negative in fish (−90%) and electronics (−54%) and 4% in designer, so their fixed cost floors at 0 (the plan: "report it and use 0").
