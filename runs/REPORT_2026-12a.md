# Report: autonomous plan 2026-11-27 (checkpoint C5)

Plan `runs/plan_autonomous_2026-11-27.md`, preregistered at c0add7b (2026-11-26 12:22). Deviations D1–D7, all decided before any main-run result (D5–D7 by Randall). Run 2026-11-26 to 2026-11-27. This report closes the plan.

**BLUF.** Both stages are done.
- **Engines 1.3.0 and 1.3.1.**
  - 1.3.0 adds category profiles, solvency, position rent and γ by buyer profile. 1.3.1 adds a seconds cost target and fixed cost by stall type.
  - At their defaults both reproduce 1.2.0, and the full suite passes.
- **The first pilot stopped at G4.** Seconds stalls were bankrupted by fixed costs sized to the genuine baseline. Randall approved the 1.3.1 fix, and the second pilot passed every gate. All 7,800 main chains ran in 12.5 h.
- **Verdicts.**
  - Supported: PA3 (detection makes bust-outs lose in every Run A cell) and PC1 (deceptive stalls sell a larger share at the entrance spots, +10 points).
  - Partly supported: PA1 (fat margins only).
  - Not supported: PA2, PB1 (no rent trap) and PB2.
- **The main problem is a calibration property, not a code bug.** In thin-margin cells, and in the fish and electronics aisles of the realistic profiles, honest stalls lose money at ds 0. The fixed cost is 85–90% of gross profit, and ad spend is not in that baseline.
  - So the preregistered unit, gain as a share of honest profit, is undefined for most of those seeds.
  - That makes PA1 thin and PA2 hard untestable, and leaves PA2 easy and PB2 on 4 and 6 seeds.
  - In base-price units (a preregistered secondary unit; the contrasts are post hoc), PA1 and PA2 point the predicted way in all four parts.
- **Nothing has been pushed.** Every commit since a3e997e, and the v1.2.0 tag, are local.

## Checkpoints

| | When | Result |
|---|---|---|
| C1 | 2026-11-26 14:19 | Engine 1.3.0 (494d1bd): full suite 1,889 passed, 17 skipped |
| C2 (first) | 2026-11-26 16:14 | First pilot: **STOP at G4** (B\|cash2\|·\|ds1 lost 52.1% and 51.4% of stalls before day 10) |
| | 2026-11-26 evening | Randall's G4 decision (D3, D4), then the 1.3.1 proposal approved with additions (D5–D7) |
| C1 (1.3.1) | 2026-11-26 18:59 | Engine 1.3.1 (3c4bd3b), script 4f66849: full suite 1,901 passed, 17 skipped |
| C2 | 2026-11-26 21:05 | Second pilot: all gates pass (G3 13.0 h); main runs launched (`runs/pilot_aisles_131.md`) |
| C3 | 2026-11-27 | Run A summary (`runs/aisles_A_summary.md`) |
| C4 | 2026-11-27 | Runs B and C summaries (`runs/aisles_B_summary.md`, `runs/aisles_C_summary.md`) |
| C5 | 2026-11-27 | This report |

## Stage 1: engines 1.3.0 and 1.3.1

**1.3.0 (494d1bd)** added:
- category profiles: rescaled unit cost to cost-share targets, a fixed daily cost as a share of a calibrated baseline gross profit, inspection noise and cost multiplier, and review accuracy;
- `sellers.solvency`: start cash, a credit limit and exit;
- `market.rent`: α × a calibrated position-advantage table;
- `buyers.gamma_by_profile`.

Tests: `tests/test_v130.py` 17/17, and the reference digests with the new keys at their defaults.

**1.3.1 (3c4bd3b)**, D6, decided by Randall:
- Each stall's fixed cost is the share × max(0, its own type's baseline gross).
- `seconds_cost_share` sets a seconds stall's unit cost at the cheap mean quality as a share of the seconds price at rating 1.0 (PLACEHOLDER: the genuine cost share).
- Start cash and credit stay on the genuine baseline.
- Without the new keys, 1.3.1 is 1.3.0 exactly. `tests/test_v131.py` 12/12.

The docs are updated: config reference, formal model ("added at 1.3.1, not cross-checked") and CHANGELOG.

## Stage 2: aisles study

Engine 1.3.1. Script `analysis/aisles_1_3.py` (sha256 16f8c60a…03cb).
- Calibration from the second pilot (seeds 900–902).
- 7,800 chains: Run A 5,120, Run B 2,560, Run C 120.
- 2026-11-26 21:05 to 2026-11-27 09:35, two blocks of at most 10 h, 7 workers.
- Memory pauses 0. Guards 0 in every run (stuck, idle, parked and fallbacks, over 35.1 million buyer-days).

### Verdicts

The primary is D5: per seed, Σ gains ÷ Σ honest profits over the sampled stalls (one per aisle, D2), then the mean and 95% t interval over seeds. n is the number of seeds where the ratio is defined.

| Prediction | Estimate [95% CI], n | Verdict | Base-price units, post hoc, n 20 |
|---|---|---|---|
| PA1 fat: t40 ds 0, hard − easy | +0.026 [+0.011, +0.041], 20 | supported | +3.31 [+2.27, +4.34] |
| PA1 thin | −1.21, 1 | not testable | +2.19 [+1.64, +2.74] |
| **PA1** | | **partly supported** | |
| PA2 easy: t40 ds 0, thin − fat | −0.38 [−0.86, +0.11], 4 | not supported | +3.25 [+2.66, +3.84] |
| PA2 hard | −1.98, 1 | not testable | +2.12 [+1.64, +2.61] |
| **PA2** | | **not supported** (frozen rule; in substance, untestable) | |
| **PA3**: ds 1 gain < 0 in all 8 cells | −0.11 to −2.47, every interval below 0, n 18–20 | **supported** (8/8) | −5.4 to −11.4 |
| **PB1**: ds 0, α 0, cash 2 − cash 20 | −0.24 [−0.81, +0.33], 15 | **not supported** | +0.09 [−0.90, +1.08] |
| **PB2**: ds 0, cash 20, α 0, designer − fish | +1.02 [−1.40, +3.45], 6 | **not supported** | +1.21 [−1.36, +3.79] |
| **PC1**: t40, α 0, deceptive share entrance − rest | +0.100 [+0.061, +0.140], 20 | **supported** | (a share; no gain) |

The secondary unit (per-stall mean of ratios) gives the same verdicts, with one exception: PA3 thin hard t100 has an interval that includes 0 (7 of 8 cells).

### Exploratory, in brief

- **t100, ds 0 (tourists only, no detection):** bust-outs pay in every Run A cell, +5 to +38 base-price units, mostly on day 20.
- **PA4 interaction (base units):** −1.12 [−1.79, −0.46]. The hard-verifiability effect is larger for fat margins in absolute terms.
- **Rent (Run B):**
  - Rent changes the gain only through exits, because it is charged identically in the never and bust-out chains. At cash 20 the α effect on the gain is exactly 0.
  - On the primary unit, α acts through the denominator: +0.076 [+0.010, +0.143] at cash 2.
- **Rent (Run C):** rent narrows the entrance gap. With tourists only it goes from +0.100 at α 0 to −0.002 at α 1.
- **Tourists bear the harm at the entrance.** At t40, α 0, 25.7% of tourists' entrance units are short, against 16.2% elsewhere, and their surplus is $1.27 a unit against $4.90.
- **Exits (D7):**
  - Every exit in every cell is an insolvency.
  - Genuine stalls exiting before day 10 are 0 in Run A, at most 2.5% in Run C, and 5.8% and 8.3% in Run B's two cash-2 ds 0 cells. That is above G4b's 5%, which is a pilot gate and passed at 3.7%.
  - Thin cash and detection clear out most deceptive stalls, and thin cash about a third of the seconds stalls.

## Deviations

All are logged in `runs/STATUS.md` with dates.

| | What | Decided |
|---|---|---|
| D1 | The plan's `market.gamma` is the engine's `buyers.position_rent`; `buyers.gamma_by_profile` overrides it per profile | before any chain |
| D2 | The 3 benchmark stalls per seed from `default_rng([seed, 17])`, one per aisle | before any chain |
| D3 | `exit_reason` instrumentation (insolvency / other), checked to change no outcome | Randall, after the first pilot |
| D4 | Bug fix: the pilot script stacked its observers on every job (observer fields k ×; calibration off by ≤ 1.8%) | after the first pilot; calibration remade |
| D5 | Primary estimand: ratio of sums per seed; count of honest ≤ 0; per-stall mean of ratios as secondary | Randall, before any main-run result |
| D6 | Engine 1.3.1: fixed cost by type, floored at 0; seconds cost share = genuine cost share (PLACEHOLDER) | Randall, before any main-run result |
| D7 | Gates G2d and G4b; exits by type × reason as an exploratory outcome | Randall, before any main-run result |

Post hoc additions, labelled, which change no verdict:
- paired contrasts in the plan's secondary units (`analysis/aisles_secondary_units.py`);
- the plots (`analysis/aisles_plots.py`).

## Open items

1. **Honest margin net of ad spend.** The fixed cost is sized to gross profit (revenue − unit cost), as the plan specifies, but honest profit also pays ad spend. Ad spend is flat by aisle at about $2.4, $16 and $39 a day, which is 14–34% of a thin stall's gross. At fixed-cost shares of 0.85–0.90 this makes honest profit negative.
   - Options:
     - size the fixed cost to gross minus ad spend;
     - lower the PLACEHOLDER shares;
     - use a primary unit that doesn't divide by honest profit, such as base-price units.
   - Randall's decision. No result here depends on it beyond the testability of PA1 thin, PA2 and PB2.
2. **D5 with one stall per aisle.** Per-aisle figures are a single stall's ratio, and undefined whenever its honest profit is ≤ 0 (PB2 n 6).
3. **G4b in the main runs.** 8.3% of genuine stalls exit before day 10 in B|cash2|a1|ds0. G4b was checked at the pilot only.
4. **Exits by spot (PC2)** were not computed by the frozen script.
5. **PLACEHOLDERs:** the cost shares, fixed-cost shares and seconds cost shares.
6. **Push.** Nothing has been pushed. Randall pushes v1.2.0 and later tags.

## Files

- Summaries: `runs/pilot_aisles_131.md`, `runs/aisles_A_summary.md`, `runs/aisles_B_summary.md`, `runs/aisles_C_summary.md`.
- First pilot: `runs/pilot_aisles.md` and `runs/pilot_aisles_130/`.
- Data: `runs/aisles_{A,B,C}.json`, `runs/aisles_secondary_units.json`, `runs/aisles_calibration.json`.
- Logs: `runs/aisles_run.log`, `runs/aisles_main_stdout.log`.
- The chain cache `runs/aisles_cache.jsonl` (10 MB) is local and not committed.
- Plots: `runs/aisles_A_cells.svg`, `runs/aisles_C_entrance.svg`.
