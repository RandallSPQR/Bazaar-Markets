# Inspector placement sweep

Bazaar replication of the M0 pocket result. At equal enforcement effort, does inspector
placement change deceptive sellers' and buyers' outcomes?

## Run record

- Engine version: `0.2.0`
- Commit: `7de649141c3463332e117e5dafe4bc741c962a2c` (clean working tree)
- Command: `.venv/bin/python -m analysis.placement_sweep --seeds 0-29 --out runs/placement_sweep.json`
- Wall-clock: 1088 s for 420 runs on 8 workers
- Seeds: 0–29 (30), the same list in every condition
- Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit
- Bootstrap: 10000 resamples of seeds, numpy default_rng(20261105)
- Machine load: other jobs were running and macOS was throttling the CPU (kernel_task above 200%) for most
  of this run, so the wall-clock overstates the normal cost (a 3-seed smoke run took 32 s for 42 runs).
- Analysis code: `analysis/placement_sweep.py` at the commit above. No engine code changed in this run.

## Reading (written after the results; everything except 2a is exploratory)

**Confirmatory (2a): patrolling beat fixed posts on all four primary outcomes, at both counts and in both arms.**
Every one of the 8 confirmatory intervals excludes 0 in the default arm and in the robustness arm.
Default arm, patrolling − posts, paired over 30 seeds:

| count | shortfall rate | task complete | buyer surplus | deceptive profit per stall |
|---|---|---|---|---|
| 2 | −7.9 pts [−10.9, −4.9] | +4.5 pts [+2.7, +6.3] | +$2.95 [+1.39, +4.52] | −$182 [−206, −158] |
| 6 | −16.7 pts [−21.1, −12.2] | +9.5 pts [+7.0, +12.1] | +$5.98 [+3.89, +8.06] | −$312 [−339, −284] |

The pocket mechanism shows up directly. With 2 inspectors on posts, 11.6 of the 15 deceptive stalls are
never caught in a run; with 2 patrolling, 0.3 are. With 6, the counts are 6.0 and 0.0.

**Disguised vs posts (2b) depends on the detection assumption.** Under default detection, disguised beats posts
at both counts. Under equal detection given exposure, disguised loses its edge at count 2 (only deceptive
profit differs, by −$45 [−76, −14]), and at count 6 deceptive sellers earn *more* than under posts
(+$46 [+11, +81]) even though buyers still do better. Disguised inspectors are active for far fewer ticks
(80 and 246 vs 480 and 1440), so these are not equal-effort comparisons. Per active inspector-tick,
disguised has the largest effect of any placement in both arms (descriptive, not causal).

**Displacement: the test's trigger was never met.** Shortfall fell with deceptive profit in every condition.
The only sign of displacement is small: with 2 inspectors on posts, never-caught deceptive stalls gained
+1.0 [+0.1, +1.9] purchases per run relative to the same stalls in control (disguised_2: +0.7 [+0.1, +1.4]).

### Caveats

- **Empty-handed share cannot respond to inspection in this setup.** It is identical in every seed across all
  conditions of both arms. A diagnostic on seeds 0–2 (not part of the design) found that 60/72, 44/61 and 54/68
  empty-handed buyers never come within reach of a stall of their own category, and every buyer who bought
  anything did. Route coverage, not enforcement, sets this outcome. About 40% of buyers are therefore outside
  enforcement's reach, which dilutes every buyer-level effect.
- **Every shortfall purchase in this sweep was at a deceptive stall** (the rule buyer never buys seconds below
  Q_req), so the two displacement Δ columns are identical.
- **Ceiling in the robustness arm.** Patrolling under equal detection catches exactly 90 times in every seed: each
  of the 15 deceptive stalls is caught on reopening, about every 41 ticks, 6 times in 240 ticks. Deceptive
  profit there (≈ −$503) is at its floor of about 6 penalties per stall, so contrasts involving that cell are
  bounded and understate what more patrolling could do.
- **Calibration.** Inspector count, ad costs, yell cooldown and the detection defaults are placeholders or
  calibration choices (see `docs/config_reference.md`), not research claims.
- **No multiplicity adjustment.** Intervals are unadjusted, as prespecified. The confirmatory intervals all exclude
  0 by wide margins (the closest is +$1.39 for surplus at count 2 in the default arm).

### Analysis choices made where the design left room

- *Stall-ticks closed*: ticks in which a stall was closed after a catch (t+1 … reopen−1, clipped at the end of the
  run), summed over stalls.
- *Shortfall share at never-caught stalls* is 100% in control by construction, so the literal "vs control"
  comparison is degenerate. The Δ columns instead compare purchases at the same never-caught stall set against
  control in the same seed. "Deceptive stalls never caught" was added to give context.
- The displacement statistics are reported for every condition, not only when the trigger was met.
- *Effort-adjusted rate*: 100 × mean(paired change vs control) / mean(active inspector-ticks), with a percentile
  bootstrap that resamples the same seeds for both numerator and denominator.

## Design (prespecified)

- Conditions: `inspectors.placement` ∈ {posts, patrolling, disguised} × `inspectors.count` ∈ {2, 6},
  plus a no-inspector control (count 0). Default bazaar config otherwise.
- Robustness arm: the full grid again with `configs/detection_equal.json`
  (flat proximity, every channel weight 1: equal detection given exposure).
- Primary outcomes: shortfall rate, task-complete share, mean buyer surplus (buyers);
  deceptive profit per stall (sellers). The rest are secondary.
- Confirmatory test: **2a, patrolling − posts at count 2 and at count 6**. Everything else is exploratory.

Notation: mean [95% t-interval over 30 seeds]. Money in dollars, shares in percent.
In contrast tables, `*` marks an interval that excludes 0. Intervals are unadjusted;
the confirmatory family has 2 contrasts × 4 primary outcomes.

## Arm: default

### Primary outcomes by condition

| condition | shortfall rate (%) | task complete (%) | buyer surplus ($/buyer) | deceptive profit ($/stall) |
|---|---|---|---|---|
| control | 30.2 [24.4, 36.0] | 23.6 [20.3, 26.9] | -0.66 [-3.81, 2.48] | 49.24 [30.43, 68.05] |
| posts_2 | 26.7 [20.8, 32.5] | 25.6 [22.3, 28.9] | 0.33 [-2.82, 3.48] | 8.82 [-12.03, 29.68] |
| patrolling_2 | 18.8 [14.7, 22.8] | 30.1 [27.8, 32.4] | 3.28 [0.59, 5.97] | -173.20 [-198.06, -148.35] |
| disguised_2 | 24.5 [19.7, 29.3] | 26.8 [24.0, 29.6] | 1.02 [-1.71, 3.75] | -51.18 [-71.95, -30.40] |
| posts_6 | 24.9 [19.2, 30.7] | 26.5 [23.2, 29.8] | 1.60 [-1.49, 4.69] | -101.40 [-137.18, -65.62] |
| patrolling_6 | 8.3 [6.2, 10.4] | 36.0 [34.3, 37.7] | 7.57 [5.90, 9.25] | -413.04 [-429.59, -396.50] |
| disguised_6 | 17.9 [14.4, 21.5] | 30.6 [28.4, 32.9] | 3.87 [1.76, 5.99] | -174.65 [-196.37, -152.93] |

### Secondary outcomes by condition

| condition | catches | deceptive share of units (%) | quantity fulfilled (%) | empty-handed (%) | active inspector-ticks |
|---|---|---|---|---|---|
| control | 0.0 [0.0, 0.0] | 32.7 [26.4, 39.0] | 41.3 [39.8, 42.8] | 40.1 [38.4, 41.8] | 0.0 [0.0, 0.0] |
| posts_2 | 9.8 [7.9, 11.7] | 28.8 [22.4, 35.1] | 41.2 [39.7, 42.7] | 40.1 [38.4, 41.8] | 480.0 [480.0, 480.0] |
| patrolling_2 | 38.5 [34.8, 42.2] | 20.5 [16.1, 24.9] | 41.2 [39.7, 42.6] | 40.1 [38.4, 41.8] | 480.0 [480.0, 480.0] |
| disguised_2 | 17.7 [15.3, 20.2] | 26.5 [21.3, 31.6] | 41.2 [39.7, 42.6] | 40.1 [38.4, 41.8] | 79.9 [69.3, 90.5] |
| posts_6 | 27.0 [23.9, 30.2] | 27.1 [20.8, 33.4] | 41.2 [39.7, 42.7] | 40.1 [38.4, 41.8] | 1440.0 [1440.0, 1440.0] |
| patrolling_6 | 77.6 [75.7, 79.5] | 9.3 [6.8, 11.9] | 41.0 [39.5, 42.5] | 40.1 [38.4, 41.8] | 1440.0 [1440.0, 1440.0] |
| disguised_6 | 38.1 [35.8, 40.5] | 19.7 [15.9, 23.6] | 41.2 [39.8, 42.7] | 40.1 [38.4, 41.8] | 245.8 [227.0, 264.6] |

### 2a. Patrolling − posts (confirmatory), primary outcomes

| paired difference | shortfall rate (%) | task complete (%) | buyer surplus ($/buyer) | deceptive profit ($/stall) |
|---|---|---|---|---|
| patrolling_2 - posts_2 | -7.9 [-10.9, -4.9] * | +4.5 [+2.7, +6.3] * | +2.95 [+1.39, +4.52] * | -182.03 [-205.83, -158.22] * |
| patrolling_6 - posts_6 | -16.7 [-21.1, -12.2] * | +9.5 [+7.0, +12.1] * | +5.98 [+3.89, +8.06] * | -311.65 [-339.41, -283.88] * |

### 2a. Patrolling − posts (confirmatory), secondary outcomes

| paired difference | catches | deceptive share of units (%) | quantity fulfilled (%) | empty-handed (%) | active inspector-ticks |
|---|---|---|---|---|---|
| patrolling_2 - posts_2 | +28.8 [+25.2, +32.4] * | -8.3 [-11.6, -5.0] * | -0.1 [-0.3, +0.1] | +0.0 [+0.0, +0.0] | +0.0 [+0.0, +0.0] |
| patrolling_6 - posts_6 | +50.6 [+48.0, +53.1] * | -17.7 [-22.5, -13.0] * | -0.2 [-0.5, +0.1] | +0.0 [+0.0, +0.0] | +0.0 [+0.0, +0.0] |

### 2b. Disguised − posts (exploratory), primary outcomes

| paired difference | shortfall rate (%) | task complete (%) | buyer surplus ($/buyer) | deceptive profit ($/stall) |
|---|---|---|---|---|
| disguised_2 - posts_2 | -2.1 [-4.0, -0.3] * | +1.2 [+0.2, +2.3] * | +0.70 [-0.15, +1.54] | -60.00 [-77.28, -42.72] * |
| disguised_6 - posts_6 | -7.0 [-10.6, -3.5] * | +4.2 [+2.1, +6.2] * | +2.27 [+0.68, +3.86] * | -73.25 [-103.44, -43.05] * |

### 2b. Disguised − posts (exploratory), secondary outcomes

| paired difference | catches | deceptive share of units (%) | quantity fulfilled (%) | empty-handed (%) | active inspector-ticks |
|---|---|---|---|---|---|
| disguised_2 - posts_2 | +8.0 [+5.2, +10.7] * | -2.3 [-4.4, -0.2] * | -0.0 [-0.2, +0.1] | +0.0 [+0.0, +0.0] | -400.1 [-410.7, -389.5] * |
| disguised_6 - posts_6 | +11.1 [+7.7, +14.5] * | -7.3 [-11.1, -3.6] * | +0.0 [-0.1, +0.2] | +0.0 [+0.0, +0.0] | -1194.2 [-1213.0, -1175.4] * |

### 2c. Each placement − control (exploratory), primary outcomes

| paired difference | shortfall rate (%) | task complete (%) | buyer surplus ($/buyer) | deceptive profit ($/stall) |
|---|---|---|---|---|
| posts_2 - control | -3.6 [-5.0, -2.1] * | +2.0 [+1.1, +2.8] * | +0.99 [+0.37, +1.61] * | -40.42 [-48.97, -31.86] * |
| patrolling_2 - control | -11.5 [-14.4, -8.5] * | +6.5 [+4.8, +8.2] * | +3.94 [+2.47, +5.41] * | -222.44 [-244.71, -200.18] * |
| disguised_2 - control | -5.7 [-7.5, -3.9] * | +3.2 [+2.1, +4.3] * | +1.68 [+1.03, +2.34] * | -100.42 [-116.34, -84.49] * |
| posts_6 - control | -5.3 [-7.2, -3.4] * | +2.9 [+1.7, +4.1] * | +2.26 [+1.00, +3.53] * | -150.64 [-177.56, -123.72] * |
| patrolling_6 - control | -22.0 [-26.3, -17.6] * | +12.4 [+9.9, +14.9] * | +8.24 [+6.03, +10.45] * | -462.28 [-478.69, -445.88] * |
| disguised_6 - control | -12.3 [-15.3, -9.3] * | +7.0 [+5.3, +8.8] * | +4.53 [+3.18, +5.89] * | -223.88 [-241.86, -205.91] * |

### 2c. Each placement − control (exploratory), secondary outcomes

| paired difference | catches | deceptive share of units (%) | quantity fulfilled (%) | empty-handed (%) | active inspector-ticks |
|---|---|---|---|---|---|
| posts_2 - control | +9.8 [+7.9, +11.7] * | -3.9 [-5.5, -2.4] * | -0.1 [-0.2, +0.1] | +0.0 [+0.0, +0.0] | +480.0 [+480.0, +480.0] * |
| patrolling_2 - control | +38.5 [+34.8, +42.2] * | -12.2 [-15.4, -9.0] * | -0.1 [-0.3, +0.1] | +0.0 [+0.0, +0.0] | +480.0 [+480.0, +480.0] * |
| disguised_2 - control | +17.7 [+15.3, +20.2] * | -6.2 [-8.3, -4.2] * | -0.1 [-0.2, +0.0] | +0.0 [+0.0, +0.0] | +79.9 [+69.3, +90.5] * |
| posts_6 - control | +27.0 [+23.9, +30.2] * | -5.6 [-7.7, -3.5] * | -0.1 [-0.2, +0.1] | +0.0 [+0.0, +0.0] | +1440.0 [+1440.0, +1440.0] * |
| patrolling_6 - control | +77.6 [+75.7, +79.5] * | -23.4 [-28.0, -18.7] * | -0.3 [-0.5, -0.0] * | +0.0 [+0.0, +0.0] | +1440.0 [+1440.0, +1440.0] * |
| disguised_6 - control | +38.1 [+35.8, +40.5] * | -13.0 [-16.2, -9.7] * | -0.0 [-0.2, +0.1] | +0.0 [+0.0, +0.0] | +245.8 [+227.0, +264.6] * |

### Effort-adjusted change vs control (descriptive rate, not a causal estimate)

Change vs control per 100 active inspector-ticks = 100 × mean(paired change) / mean(active ticks),
with a paired percentile bootstrap 95% CI. Units as above (dollars, percentage points, catches).

| condition | mean active ticks | shortfall rate (%) | task complete (%) | buyer surplus ($/buyer) | deceptive profit ($/stall) | catches | deceptive share of units (%) | quantity fulfilled (%) | empty-handed (%) |
|---|---|---|---|---|---|---|---|---|---|
| posts_2 | 480 | -0.7 [-1.0, -0.5] | +0.4 [+0.2, +0.6] | +0.21 [+0.10, +0.34] | -8.42 [-10.14, -6.77] | +2.0 [+1.7, +2.4] | -0.8 [-1.1, -0.5] | -0.0 [-0.0, +0.0] | +0.0 [+0.0, +0.0] |
| patrolling_2 | 480 | -2.4 [-3.0, -1.8] | +1.4 [+1.0, +1.7] | +0.82 [+0.54, +1.13] | -46.34 [-50.77, -42.04] | +8.0 [+7.3, +8.7] | -2.5 [-3.2, -1.9] | -0.0 [-0.1, +0.0] | +0.0 [+0.0, +0.0] |
| disguised_2 | 80 | -7.2 [-9.5, -5.2] | +4.0 [+2.8, +5.3] | +2.11 [+1.36, +2.96] | -125.68 [-142.53, -108.70] | +22.2 [+20.0, +24.4] | -7.8 [-10.4, -5.6] | -0.1 [-0.3, +0.0] | +0.0 [+0.0, +0.0] |
| posts_6 | 1440 | -0.4 [-0.5, -0.2] | +0.2 [+0.1, +0.3] | +0.16 [+0.08, +0.25] | -10.46 [-12.23, -8.69] | +1.9 [+1.7, +2.1] | -0.4 [-0.5, -0.3] | -0.0 [-0.0, +0.0] | +0.0 [+0.0, +0.0] |
| patrolling_6 | 1440 | -1.5 [-1.8, -1.2] | +0.9 [+0.7, +1.0] | +0.57 [+0.43, +0.73] | -32.10 [-33.20, -31.04] | +5.4 [+5.3, +5.5] | -1.6 [-1.9, -1.3] | -0.0 [-0.0, -0.0] | +0.0 [+0.0, +0.0] |
| disguised_6 | 246 | -5.0 [-6.2, -3.9] | +2.9 [+2.2, +3.5] | +1.84 [+1.33, +2.44] | -91.08 [-99.42, -83.47] | +15.5 [+14.8, +16.3] | -5.3 [-6.5, -4.1] | -0.0 [-0.1, +0.0] | +0.0 [+0.0, +0.0] |

### Displacement check

Per condition. "Never-caught" stalls are those with no catch in that seed and condition.
Shortfall at never-caught stalls is 100% in control by construction, so the Δ columns compare
purchases at the same never-caught stalls against control in the same seed (paired; positive =
purchases moved to stalls that escaped inspection).

| condition | catches | stall-ticks closed | deceptive stalls never caught | deceptive share of units (%) | shortfall purchases | shortfall at never-caught stalls (%) | Δ shortfall purchases at never-caught stalls | Δ deceptive purchases at never-caught stalls |
|---|---|---|---|---|---|---|---|---|
| control | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 15.0 [15.0, 15.0] | 32.7 [26.4, 39.0] | 27.2 [22.0, 32.3] | 100.0 [100.0, 100.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| posts_2 | 9.8 [7.9, 11.7] | 370.4 [299.3, 441.5] | 11.6 [11.1, 12.2] | 28.8 [22.4, 35.1] | 23.9 [18.8, 29.0] | 74.4 [63.1, 85.6] | 1.0 [0.1, 1.9] | 1.0 [0.1, 1.9] |
| patrolling_2 | 38.5 [34.8, 42.2] | 1496.6 [1356.0, 1637.3] | 0.3 [0.1, 0.5] | 20.5 [16.1, 24.9] | 16.9 [13.3, 20.5] | 4.8 [-0.5, 10.2] | 0.5 [-0.2, 1.2] | 0.5 [-0.2, 1.2] |
| disguised_2 | 17.7 [15.3, 20.2] | 709.3 [611.1, 807.5] | 2.5 [1.5, 3.5] | 26.5 [21.3, 31.6] | 22.0 [17.8, 26.1] | 28.3 [14.5, 42.0] | 0.7 [0.1, 1.4] | 0.7 [0.1, 1.4] |
| posts_6 | 27.0 [23.9, 30.2] | 1021.1 [905.2, 1137.0] | 6.0 [5.2, 6.8] | 27.1 [20.8, 33.4] | 22.4 [17.3, 27.5] | 72.3 [61.9, 82.8] | 0.6 [-0.0, 1.1] | 0.6 [-0.0, 1.1] |
| patrolling_6 | 77.6 [75.7, 79.5] | 2875.7 [2817.0, 2934.5] | 0.0 [0.0, 0.0] | 9.3 [6.8, 11.9] | 7.5 [5.6, 9.4] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| disguised_6 | 38.1 [35.8, 40.5] | 1506.4 [1419.9, 1592.8] | 0.2 [-0.0, 0.4] | 19.7 [15.9, 23.6] | 16.2 [13.0, 19.4] | 2.7 [-1.2, 6.7] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |

Trigger for the displacement test (deceptive profit falls vs control while shortfall does not):

- posts_2: not triggered (Δ deceptive profit -40.42 [-48.97, -31.86]; Δ shortfall -3.6 [-5.0, -2.1]; Δ deceptive purchases at never-caught stalls +1.0 [+0.1, +1.9])
- patrolling_2: not triggered (Δ deceptive profit -222.44 [-244.71, -200.18]; Δ shortfall -11.5 [-14.4, -8.5]; Δ deceptive purchases at never-caught stalls +0.5 [-0.2, +1.2])
- disguised_2: not triggered (Δ deceptive profit -100.42 [-116.34, -84.49]; Δ shortfall -5.7 [-7.5, -3.9]; Δ deceptive purchases at never-caught stalls +0.7 [+0.1, +1.4])
- posts_6: not triggered (Δ deceptive profit -150.64 [-177.56, -123.72]; Δ shortfall -5.3 [-7.2, -3.4]; Δ deceptive purchases at never-caught stalls +0.6 [-0.0, +1.1])
- patrolling_6: not triggered (Δ deceptive profit -462.28 [-478.69, -445.88]; Δ shortfall -22.0 [-26.3, -17.6]; Δ deceptive purchases at never-caught stalls +0.0 [+0.0, +0.0])
- disguised_6: not triggered (Δ deceptive profit -223.88 [-241.86, -205.91]; Δ shortfall -12.3 [-15.3, -9.3]; Δ deceptive purchases at never-caught stalls +0.0 [+0.0, +0.0])

## Arm: detection_equal

### Primary outcomes by condition

| condition | shortfall rate (%) | task complete (%) | buyer surplus ($/buyer) | deceptive profit ($/stall) |
|---|---|---|---|---|
| control | 30.2 [24.4, 36.0] | 23.6 [20.3, 26.9] | -0.66 [-3.81, 2.48] | 49.24 [30.43, 68.05] |
| posts_2 | 19.2 [14.6, 23.8] | 29.8 [27.1, 32.6] | 3.34 [0.90, 5.78] | -65.49 [-93.12, -37.86] |
| patrolling_2 | 1.3 [0.7, 1.9] | 40.2 [38.7, 41.7] | 11.09 [10.48, 11.71] | -501.23 [-503.55, -498.90] |
| disguised_2 | 21.0 [16.8, 25.2] | 28.8 [26.3, 31.4] | 2.92 [0.50, 5.35] | -110.57 [-133.53, -87.62] |
| posts_6 | 17.2 [12.5, 21.9] | 31.0 [28.1, 33.9] | 5.00 [2.50, 7.51] | -299.63 [-337.01, -262.25] |
| patrolling_6 | 0.7 [0.3, 1.0] | 40.5 [39.0, 42.0] | 11.51 [10.86, 12.17] | -503.51 [-504.88, -502.14] |
| disguised_6 | 11.8 [9.0, 14.7] | 34.0 [32.1, 36.0] | 6.56 [5.14, 7.98] | -253.90 [-271.61, -236.18] |

### Secondary outcomes by condition

| condition | catches | deceptive share of units (%) | quantity fulfilled (%) | empty-handed (%) | active inspector-ticks |
|---|---|---|---|---|---|
| control | 0.0 [0.0, 0.0] | 32.7 [26.4, 39.0] | 41.3 [39.8, 42.8] | 40.1 [38.4, 41.8] | 0.0 [0.0, 0.0] |
| posts_2 | 22.3 [19.3, 25.2] | 20.6 [15.7, 25.5] | 41.1 [39.5, 42.6] | 40.1 [38.4, 41.8] | 480.0 [480.0, 480.0] |
| patrolling_2 | 90.0 [90.0, 90.0] | 1.5 [0.9, 2.2] | 41.0 [39.5, 42.4] | 40.1 [38.4, 41.8] | 480.0 [480.0, 480.0] |
| disguised_2 | 26.8 [24.0, 29.5] | 22.5 [18.0, 27.0] | 41.2 [39.7, 42.6] | 40.1 [38.4, 41.8] | 79.9 [69.3, 90.5] |
| posts_6 | 59.6 [56.1, 63.1] | 18.4 [13.3, 23.4] | 41.1 [39.5, 42.6] | 40.1 [38.4, 41.8] | 1440.0 [1440.0, 1440.0] |
| patrolling_6 | 90.0 [90.0, 90.0] | 0.8 [0.4, 1.2] | 40.9 [39.4, 42.4] | 40.1 [38.4, 41.8] | 1440.0 [1440.0, 1440.0] |
| disguised_6 | 51.0 [48.9, 53.2] | 12.8 [9.8, 15.7] | 41.1 [39.6, 42.6] | 40.1 [38.4, 41.8] | 245.8 [227.0, 264.6] |

### 2a. Patrolling − posts (confirmatory), primary outcomes

| paired difference | shortfall rate (%) | task complete (%) | buyer surplus ($/buyer) | deceptive profit ($/stall) |
|---|---|---|---|---|
| patrolling_2 - posts_2 | -17.9 [-22.3, -13.5] * | +10.4 [+7.8, +12.9] * | +7.75 [+5.27, +10.24] * | -435.74 [-462.47, -409.01] * |
| patrolling_6 - posts_6 | -16.5 [-21.2, -11.8] * | +9.5 [+6.9, +12.1] * | +6.51 [+3.89, +9.13] * | -203.88 [-241.15, -166.61] * |

### 2a. Patrolling − posts (confirmatory), secondary outcomes

| paired difference | catches | deceptive share of units (%) | quantity fulfilled (%) | empty-handed (%) | active inspector-ticks |
|---|---|---|---|---|---|
| patrolling_2 - posts_2 | +67.7 [+64.8, +70.7] * | -19.0 [-23.7, -14.3] * | -0.1 [-0.3, +0.1] | +0.0 [+0.0, +0.0] | +0.0 [+0.0, +0.0] |
| patrolling_6 - posts_6 | +30.4 [+26.9, +33.9] * | -17.6 [-22.6, -12.6] * | -0.2 [-0.4, +0.0] | +0.0 [+0.0, +0.0] | +0.0 [+0.0, +0.0] |

### 2b. Disguised − posts (exploratory), primary outcomes

| paired difference | shortfall rate (%) | task complete (%) | buyer surplus ($/buyer) | deceptive profit ($/stall) |
|---|---|---|---|---|
| disguised_2 - posts_2 | +1.8 [-1.1, +4.7] | -1.0 [-2.6, +0.6] | -0.42 [-2.03, +1.20] | -45.09 [-75.77, -14.40] * |
| disguised_6 - posts_6 | -5.3 [-9.1, -1.6] * | +3.1 [+0.9, +5.2] * | +1.56 [-0.21, +3.32] | +45.73 [+10.67, +80.79] * |

### 2b. Disguised − posts (exploratory), secondary outcomes

| paired difference | catches | deceptive share of units (%) | quantity fulfilled (%) | empty-handed (%) | active inspector-ticks |
|---|---|---|---|---|---|
| disguised_2 - posts_2 | +4.5 [+0.4, +8.6] * | +1.9 [-1.2, +5.0] | +0.1 [-0.1, +0.2] | +0.0 [+0.0, +0.0] | -400.1 [-410.7, -389.5] * |
| disguised_6 - posts_6 | -8.6 [-12.4, -4.7] * | -5.6 [-9.6, -1.6] * | +0.0 [-0.2, +0.2] | +0.0 [+0.0, +0.0] | -1194.2 [-1213.0, -1175.4] * |

### 2c. Each placement − control (exploratory), primary outcomes

| paired difference | shortfall rate (%) | task complete (%) | buyer surplus ($/buyer) | deceptive profit ($/stall) |
|---|---|---|---|---|
| posts_2 - control | -11.0 [-14.1, -7.9] * | +6.2 [+4.6, +7.9] * | +4.00 [+2.07, +5.93] * | -114.73 [-140.10, -89.35] * |
| patrolling_2 - control | -28.9 [-34.4, -23.5] * | +16.6 [+13.5, +19.7] * | +11.75 [+8.66, +14.85] * | -550.47 [-567.62, -533.31] * |
| disguised_2 - control | -9.2 [-11.6, -6.9] * | +5.2 [+3.8, +6.6] * | +3.59 [+2.35, +4.82] * | -159.81 [-180.00, -139.63] * |
| posts_6 - control | -13.1 [-16.5, -9.6] * | +7.4 [+5.4, +9.3] * | +5.67 [+3.44, +7.89] * | -348.87 [-381.06, -316.67] * |
| patrolling_6 - control | -29.6 [-35.3, -23.9] * | +16.9 [+13.6, +20.1] * | +12.18 [+8.87, +15.48] * | -552.75 [-571.08, -534.42] * |
| disguised_6 - control | -18.4 [-22.3, -14.5] * | +10.4 [+8.2, +12.7] * | +7.22 [+5.11, +9.33] * | -303.13 [-322.22, -284.05] * |

### 2c. Each placement − control (exploratory), secondary outcomes

| paired difference | catches | deceptive share of units (%) | quantity fulfilled (%) | empty-handed (%) | active inspector-ticks |
|---|---|---|---|---|---|
| posts_2 - control | +22.3 [+19.3, +25.2] * | -12.1 [-15.5, -8.8] * | -0.2 [-0.4, -0.1] * | +0.0 [+0.0, +0.0] | +480.0 [+480.0, +480.0] * |
| patrolling_2 - control | +90.0 [+90.0, +90.0] * | -31.2 [-37.2, -25.2] * | -0.3 [-0.5, -0.1] * | +0.0 [+0.0, +0.0] | +480.0 [+480.0, +480.0] * |
| disguised_2 - control | +26.8 [+24.0, +29.5] * | -10.3 [-13.0, -7.5] * | -0.1 [-0.3, -0.0] * | +0.0 [+0.0, +0.0] | +79.9 [+69.3, +90.5] * |
| posts_6 - control | +59.6 [+56.1, +63.1] * | -14.3 [-18.1, -10.5] * | -0.2 [-0.4, -0.1] * | +0.0 [+0.0, +0.0] | +1440.0 [+1440.0, +1440.0] * |
| patrolling_6 - control | +90.0 [+90.0, +90.0] * | -31.9 [-38.2, -25.7] * | -0.4 [-0.7, -0.2] * | +0.0 [+0.0, +0.0] | +1440.0 [+1440.0, +1440.0] * |
| disguised_6 - control | +51.0 [+48.9, +53.2] * | -19.9 [-24.3, -15.6] * | -0.2 [-0.4, -0.0] * | +0.0 [+0.0, +0.0] | +245.8 [+227.0, +264.6] * |

### Effort-adjusted change vs control (descriptive rate, not a causal estimate)

Change vs control per 100 active inspector-ticks = 100 × mean(paired change) / mean(active ticks),
with a paired percentile bootstrap 95% CI. Units as above (dollars, percentage points, catches).

| condition | mean active ticks | shortfall rate (%) | task complete (%) | buyer surplus ($/buyer) | deceptive profit ($/stall) | catches | deceptive share of units (%) | quantity fulfilled (%) | empty-handed (%) |
|---|---|---|---|---|---|---|---|---|---|
| posts_2 | 480 | -2.3 [-2.9, -1.7] | +1.3 [+1.0, +1.6] | +0.83 [+0.49, +1.27] | -23.90 [-29.11, -19.14] | +4.6 [+4.1, +5.2] | -2.5 [-3.2, -1.9] | -0.0 [-0.1, -0.0] | +0.0 [+0.0, +0.0] |
| patrolling_2 | 480 | -6.0 [-7.1, -5.0] | +3.5 [+2.9, +4.1] | +2.45 [+1.86, +3.09] | -114.68 [-118.24, -111.40] | +18.8 [+18.8, +18.8] | -6.5 [-7.7, -5.3] | -0.1 [-0.1, -0.0] | +0.0 [+0.0, +0.0] |
| disguised_2 | 80 | -11.6 [-14.1, -9.1] | +6.5 [+5.1, +8.1] | +4.49 [+3.15, +5.89] | -200.02 [-216.01, -185.53] | +33.5 [+32.0, +35.3] | -12.8 [-15.7, -10.1] | -0.2 [-0.3, -0.1] | +0.0 [+0.0, +0.0] |
| posts_6 | 1440 | -0.9 [-1.1, -0.7] | +0.5 [+0.4, +0.6] | +0.39 [+0.25, +0.55] | -24.23 [-26.24, -22.04] | +4.1 [+3.9, +4.4] | -1.0 [-1.3, -0.8] | -0.0 [-0.0, -0.0] | +0.0 [+0.0, +0.0] |
| patrolling_6 | 1440 | -2.1 [-2.4, -1.7] | +1.2 [+1.0, +1.4] | +0.85 [+0.63, +1.08] | -38.39 [-39.66, -37.23] | +6.2 [+6.2, +6.2] | -2.2 [-2.6, -1.8] | -0.0 [-0.0, -0.0] | +0.0 [+0.0, +0.0] |
| disguised_6 | 246 | -7.5 [-9.0, -6.1] | +4.2 [+3.4, +5.1] | +2.94 [+2.16, +3.83] | -123.33 [-132.92, -115.21] | +20.8 [+19.8, +21.8] | -8.1 [-9.8, -6.5] | -0.1 [-0.2, -0.0] | +0.0 [+0.0, +0.0] |

### Displacement check

Per condition. "Never-caught" stalls are those with no catch in that seed and condition.
Shortfall at never-caught stalls is 100% in control by construction, so the Δ columns compare
purchases at the same never-caught stalls against control in the same seed (paired; positive =
purchases moved to stalls that escaped inspection).

| condition | catches | stall-ticks closed | deceptive stalls never caught | deceptive share of units (%) | shortfall purchases | shortfall at never-caught stalls (%) | Δ shortfall purchases at never-caught stalls | Δ deceptive purchases at never-caught stalls |
|---|---|---|---|---|---|---|---|---|
| control | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 15.0 [15.0, 15.0] | 32.7 [26.4, 39.0] | 27.2 [22.0, 32.3] | 100.0 [100.0, 100.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| posts_2 | 22.3 [19.3, 25.2] | 866.7 [751.7, 981.7] | 11.1 [10.6, 11.6] | 20.6 [15.7, 25.5] | 17.3 [13.1, 21.5] | 99.8 [99.2, 100.3] | 0.7 [-0.3, 1.7] | 0.7 [-0.3, 1.7] |
| patrolling_2 | 90.0 [90.0, 90.0] | 3334.6 [3328.6, 3340.7] | 0.0 [0.0, 0.0] | 1.5 [0.9, 2.2] | 1.2 [0.6, 1.7] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| disguised_2 | 26.8 [24.0, 29.5] | 1070.7 [961.5, 1179.8] | 0.9 [0.4, 1.4] | 22.5 [18.0, 27.0] | 18.9 [15.1, 22.6] | 13.1 [2.7, 23.6] | 0.2 [-0.1, 0.5] | 0.2 [-0.1, 0.5] |
| posts_6 | 59.6 [56.1, 63.1] | 2309.3 [2173.7, 2445.0] | 4.3 [3.7, 4.9] | 18.4 [13.3, 23.4] | 15.4 [11.2, 19.6] | 98.0 [94.8, 101.2] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| patrolling_6 | 90.0 [90.0, 90.0] | 3444.8 [3439.5, 3450.1] | 0.0 [0.0, 0.0] | 0.8 [0.4, 1.2] | 0.6 [0.3, 0.9] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| disguised_6 | 51.0 [48.9, 53.2] | 2015.5 [1939.1, 2091.8] | 0.0 [0.0, 0.0] | 12.8 [9.8, 15.7] | 10.7 [8.1, 13.3] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |

Trigger for the displacement test (deceptive profit falls vs control while shortfall does not):

- posts_2: not triggered (Δ deceptive profit -114.73 [-140.10, -89.35]; Δ shortfall -11.0 [-14.1, -7.9]; Δ deceptive purchases at never-caught stalls +0.7 [-0.3, +1.7])
- patrolling_2: not triggered (Δ deceptive profit -550.47 [-567.62, -533.31]; Δ shortfall -28.9 [-34.4, -23.5]; Δ deceptive purchases at never-caught stalls +0.0 [+0.0, +0.0])
- disguised_2: not triggered (Δ deceptive profit -159.81 [-180.00, -139.63]; Δ shortfall -9.2 [-11.6, -6.9]; Δ deceptive purchases at never-caught stalls +0.2 [-0.1, +0.5])
- posts_6: not triggered (Δ deceptive profit -348.87 [-381.06, -316.67]; Δ shortfall -13.1 [-16.5, -9.6]; Δ deceptive purchases at never-caught stalls +0.0 [+0.0, +0.0])
- patrolling_6: not triggered (Δ deceptive profit -552.75 [-571.08, -534.42]; Δ shortfall -29.6 [-35.3, -23.9]; Δ deceptive purchases at never-caught stalls +0.0 [+0.0, +0.0])
- disguised_6: not triggered (Δ deceptive profit -303.13 [-322.22, -284.05]; Δ shortfall -18.4 [-22.3, -14.5]; Δ deceptive purchases at never-caught stalls +0.0 [+0.0, +0.0])

