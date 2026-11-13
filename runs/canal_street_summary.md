# Canal Street: counterfeits that undercut the original

Spec "Canal Street" (2026-11-12); predictions fixed 2026-11-12, before any run. Pilot gate: `runs/pilot_canal_equity.md`.

## Design (prespecified)

- Question: do counterfeits pay once they undercut the original, and what do they cost the original?
- Engine 0.17.0. Market as the licensing run: choice-set demand (m 3, gamma 0), 150 buyers, budget 1.25 × base, bargain hunters 0.2 (Q_req 0.15–0.40); D = 30 known; ratings public (memory 0.7); brands on (premium 0.4); naive deceptive sellers (fresh reopening); 2 patrolling inspectors, not uniformed; collectible fines; every genuine stall honest. Licensing off.
- Conditions: counterfeits {off (deceptive stalls keep their own names; the licensing run's never chain, fresh renames at reopening included), on: φ ∈ {1.0, 0.8, 0.6, 0.4}} × verification {tourist share 0.4 with locals inspecting; tourist share 1.0} × detect_scale {0, 1}. Entry "day", day 2: every deceptive stall copies the name of the top-rated genuine brand of its category (ratings at the end of day 1; ties from `default_rng([seed, 23])`), claims its quality, keeps the name to day 30, is never offered a rename, and posts φ × the original's price.
- Outcomes (30-day totals; also days 21–30): profit per deceptive stall; gap = counterfeit-on − off, per deceptive stall; for each copied original, its rating on days 10, 20, 30 and its 30-day profit, on − off (the same stall in the off chain); catches; shortfall and surplus by buyer profile; price and margin of counterfeits.
- Predictions (verbatim from the spec):
  - PK1 (confirmatory): tourist share 1.0, detect_scale 1: the gap rises as the price falls. Least-squares slope of the gap over (1 − φ), φ ∈ {1.0, 0.8, 0.6, 0.4}, > 0.
  - PK2 (confirmatory): tourist share 1.0, detect_scale 1, φ 1.0: gap < 0 (copying the original's price loses, as in walk mode).
  - PK3 (confirmatory): tourist share 1.0, detect_scale 1, φ 0.6: copied originals' day-30 rating, on − off, < 0.
  - PK4 (exploratory): locals inspecting shrinks the gap: gap at t40 < gap at t100 at each φ.
  - PK5 (exploratory): the original's 30-day profit, on − off, at each φ; no direction predicted.
- Analysis: per seed the mean over deceptive stalls (gap) or copied originals (rating, profit); mean and 95% t over seeds; unadjusted. PK1's slope is fitted per seed, then averaged.

## Run record

- Engine `0.17.0`; commit `0762786ef51751bc3dd68cab47cc14ad9574e82c`; uncommitted at run time: ['?? runs/canal_street_run.log', '?? runs/canal_street_stdout.log', '?? runs/queue_canal_then_equity.log']
- Script sha256 `4960f127f646b0d459c005ef34892a1583f40e2de976211daca2d6cb71015746`
- Command: `python -m analysis.canal_street --seeds 270-299 --workers 4 --tests 1109 passed, 17 skipped at e9cdc07 (runs/tests_0170.log) --gate Pilot gate G1–G5 passed at 5458448 (runs/pilot_canal_equity.md)`
- Tests: 1109 passed, 17 skipped at e9cdc07 (runs/tests_0170.log)
- Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit
- 600 chains × 30 days on 4 workers (nice 19); wall clock 1.28 h; load average [1.81, 2.14, 2.28] at start, [8.3, 7.44, 6.89] at end; memory at start {'swap_free_mb': 913.69, 'free_pct': 55}, at end {'swap_free_mb': 913.69, 'free_pct': 51}; memory-guard pauses: 0
- Seeds 270-299 (30), paired across all conditions

## Gate

Pilot gate G1–G5 passed at 5458448 (runs/pilot_canal_equity.md)

## Predictions: 30-day totals (primary)

| Prediction | Estimate | Verdict |
|---|---|---|
| **PK1**: t100, ds 1: slope of the gap over (1 − φ) | −5,812.24 [−5,958.99, −5,665.50] * | contradicted (interval on the opposite side of 0) |
| **PK2**: t100, ds 1, φ 1.0: gap | −369.83 [−457.80, −281.86] * | supported |
| **PK3**: t100, ds 1, φ 0.6: copied originals' day-30 rating, on − off | −0.379 [−0.393, −0.365] * | supported |
| **PK4 ds0 φ1**: ds 0, φ 1: gap at t40 − gap at t100 (exploratory) | −294.76 [−353.20, −236.32] * | supported |
| **PK4 ds0 φ0.8**: ds 0, φ 0.8: gap at t40 − gap at t100 (exploratory) | +926.27 [+880.51, +972.03] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds0 φ0.6**: ds 0, φ 0.6: gap at t40 − gap at t100 (exploratory) | +2,557.52 [+2,505.63, +2,609.41] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds0 φ0.4**: ds 0, φ 0.4: gap at t40 − gap at t100 (exploratory) | +4,355.10 [+4,293.88, +4,416.33] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds1 φ1**: ds 1, φ 1: gap at t40 − gap at t100 (exploratory) | +118.07 [+27.48, +208.67] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds1 φ0.8**: ds 1, φ 0.8: gap at t40 − gap at t100 (exploratory) | +442.65 [+354.88, +530.41] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds1 φ0.6**: ds 1, φ 0.6: gap at t40 − gap at t100 (exploratory) | +972.38 [+878.65, +1,066.11] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds1 φ0.4**: ds 1, φ 0.4: gap at t40 − gap at t100 (exploratory) | +1,567.74 [+1,454.47, +1,681.00] * | contradicted (interval on the opposite side of 0) |
| **PK5 φ1**: t100, ds 1, φ 1: originals' profit, on − off (exploratory, no direction) | +350.98 [+172.76, +529.20] * | interval excludes 0 |
| **PK5 φ0.8**: t100, ds 1, φ 0.8: originals' profit, on − off (exploratory, no direction) | −713.46 [−889.92, −537.00] * | interval excludes 0 |
| **PK5 φ0.6**: t100, ds 1, φ 0.6: originals' profit, on − off (exploratory, no direction) | −758.92 [−934.24, −583.60] * | interval excludes 0 |
| **PK5 φ0.4**: t100, ds 1, φ 0.4: originals' profit, on − off (exploratory, no direction) | −775.52 [−950.23, −600.81] * | interval excludes 0 |

## Predictions: days 21–30

| Prediction | Estimate | Verdict |
|---|---|---|
| **PK1**: t100, ds 1: slope of the gap over (1 − φ) (days 21–30) | −2,000.87 [−2,069.96, −1,931.78] * | contradicted (interval on the opposite side of 0) |
| **PK2**: t100, ds 1, φ 1.0: gap (days 21–30) | −158.55 [−200.19, −116.92] * | supported |
| **PK4 ds0 φ1**: ds 0, φ 1: gap at t40 − gap at t100 (days 21–30) (exploratory) | −87.17 [−115.74, −58.61] * | supported |
| **PK4 ds0 φ0.8**: ds 0, φ 0.8: gap at t40 − gap at t100 (days 21–30) (exploratory) | +378.82 [+356.99, +400.65] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds0 φ0.6**: ds 0, φ 0.6: gap at t40 − gap at t100 (days 21–30) (exploratory) | +935.63 [+911.22, +960.03] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds0 φ0.4**: ds 0, φ 0.4: gap at t40 − gap at t100 (days 21–30) (exploratory) | +1,545.96 [+1,515.69, +1,576.24] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds1 φ1**: ds 1, φ 1: gap at t40 − gap at t100 (days 21–30) (exploratory) | +56.47 [+5.97, +106.97] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds1 φ0.8**: ds 1, φ 0.8: gap at t40 − gap at t100 (days 21–30) (exploratory) | +169.92 [+118.43, +221.41] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds1 φ0.6**: ds 1, φ 0.6: gap at t40 − gap at t100 (days 21–30) (exploratory) | +365.92 [+309.61, +422.23] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds1 φ0.4**: ds 1, φ 0.4: gap at t40 − gap at t100 (days 21–30) (exploratory) | +573.53 [+506.91, +640.15] * | contradicted (interval on the opposite side of 0) |
| **PK5 φ1**: t100, ds 1, φ 1: originals' profit, on − off (days 21–30) (exploratory, no direction) | +72.92 [+6.34, +139.50] * | interval excludes 0 |
| **PK5 φ0.8**: t100, ds 1, φ 0.8: originals' profit, on − off (days 21–30) (exploratory, no direction) | −301.79 [−369.79, −233.78] * | interval excludes 0 |
| **PK5 φ0.6**: t100, ds 1, φ 0.6: originals' profit, on − off (days 21–30) (exploratory, no direction) | −323.76 [−391.27, −256.25] * | interval excludes 0 |
| **PK5 φ0.4**: t100, ds 1, φ 0.4: originals' profit, on − off (days 21–30) (exploratory, no direction) | −327.93 [−395.89, −259.97] * | interval excludes 0 |

## Deceptive stalls by condition

Per deceptive stall, $. Gap = on − off (same stall, same seed).

| Cell | Arm | Profit, 30 days | Gap, 30 days | Profit, days 21–30 | Gap, days 21–30 | Catches per stall |
|---|---|---|---|---|---|---|
| t40, ds 0 | off | +1,903.91 [+1,852.53, +1,955.30] * | – | +626.80 [+599.57, +654.04] * | – | 0.0 [0.0, 0.0] |
| t40, ds 0 | φ 1 | +2,545.19 [+2,486.04, +2,604.33] * | +641.27 [+603.66, +678.89] * | +774.08 [+741.70, +806.46] * | +147.28 [+135.53, +159.03] * | 0.0 [0.0, 0.0] |
| t40, ds 0 | φ 0.8 | +1,793.10 [+1,719.66, +1,866.53] * | −110.82 [−156.31, −65.32] * | +496.90 [+464.71, +529.08] * | −129.91 [−149.57, −110.25] * | 0.0 [0.0, 0.0] |
| t40, ds 0 | φ 0.6 | +576.93 [+519.99, +633.87] * | −1,326.98 [−1,365.13, −1,288.84] * | +104.38 [+81.66, +127.10] * | −522.42 [−542.01, −502.84] * | 0.0 [0.0, 0.0] |
| t40, ds 0 | φ 0.4 | −756.55 [−802.26, −710.85] * | −2,660.47 [−2,704.18, −2,616.75] * | −330.81 [−347.71, −313.90] * | −957.61 [−983.53, −931.69] * | 0.0 [0.0, 0.0] |
| t40, ds 0 | slope over 1 − φ |  | −5,560.70 [−5,664.98, −5,456.41] * |  | −1,853.59 [−1,903.52, −1,803.66] * |  |
| t40, ds 1 | off | −3,424.05 [−3,586.13, −3,261.98] * | – | −1,166.66 [−1,261.69, −1,071.64] * | – | 63.8 [62.3, 65.4] |
| t40, ds 1 | φ 1 | −3,675.81 [−3,855.61, −3,496.01] * | −251.76 [−307.86, −195.66] * | −1,268.75 [−1,367.29, −1,170.22] * | −102.09 [−133.71, −70.47] * | 64.0 [62.4, 65.6] |
| t40, ds 1 | φ 0.8 | −4,017.18 [−4,200.26, −3,834.11] * | −593.13 [−650.12, −536.14] * | −1,396.85 [−1,496.78, −1,296.92] * | −230.18 [−272.06, −188.31] * | 64.2 [62.6, 65.9] |
| t40, ds 1 | φ 0.6 | −4,806.29 [−4,973.17, −4,639.41] * | −1,382.24 [−1,438.59, −1,325.88] * | −1,647.53 [−1,739.85, −1,555.22] * | −480.87 [−521.86, −439.88] * | 64.1 [62.6, 65.7] |
| t40, ds 1 | φ 0.4 | −5,661.36 [−5,812.03, −5,510.68] * | −2,237.31 [−2,300.44, −2,174.17] * | −1,936.70 [−2,020.65, −1,852.76] * | −770.04 [−813.17, −726.91] * | 64.1 [62.5, 65.6] |
| t40, ds 1 | slope over 1 − φ |  | −3,372.88 [−3,480.71, −3,265.04] * |  | −1,127.27 [−1,181.82, −1,072.72] * |  |
| t100, ds 0 | off | +5,175.91 [+5,070.70, +5,281.12] * | – | +1,723.84 [+1,682.42, +1,765.26] * | – | 0.0 [0.0, 0.0] |
| t100, ds 0 | φ 1 | +6,111.95 [+5,998.75, +6,225.15] * | +936.04 [+856.52, +1,015.56] * | +1,958.29 [+1,914.62, +2,001.96] * | +234.45 [+206.94, +261.96] * | 0.0 [0.0, 0.0] |
| t100, ds 0 | φ 0.8 | +4,138.82 [+4,032.50, +4,245.15] * | −1,037.09 [−1,076.43, −997.74] * | +1,215.11 [+1,176.99, +1,253.23] * | −508.73 [−529.39, −488.07] * | 0.0 [0.0, 0.0] |
| t100, ds 0 | φ 0.6 | +1,291.40 [+1,192.36, +1,390.44] * | −3,884.51 [−3,935.75, −3,833.27] * | +265.79 [+230.00, +301.58] * | −1,458.05 [−1,487.94, −1,428.16] * | 0.0 [0.0, 0.0] |
| t100, ds 0 | φ 0.4 | −1,839.66 [−1,931.89, −1,747.44] * | −7,015.57 [−7,080.87, −6,950.27] * | −779.74 [−814.48, −745.00] * | −2,503.57 [−2,542.82, −2,464.33] * | 0.0 [0.0, 0.0] |
| t100, ds 0 | slope over 1 − φ |  | −13,351.13 [−13,526.21, −13,176.04] * |  | −4,581.70 [−4,664.16, −4,499.24] * |  |
| t100, ds 1 | off | −4,586.32 [−4,728.52, −4,444.12] * | – | −1,501.25 [−1,575.11, −1,427.39] * | – | 95.7 [94.9, 96.4] |
| t100, ds 1 | φ 1 | −4,956.15 [−5,078.62, −4,833.68] * | −369.83 [−457.80, −281.86] * | −1,659.80 [−1,724.32, −1,595.28] * | −158.55 [−200.19, −116.92] * | 95.6 [94.9, 96.4] |
| t100, ds 1 | φ 0.8 | −5,622.10 [−5,744.66, −5,499.54] * | −1,035.77 [−1,122.65, −948.90] * | −1,901.35 [−1,965.72, −1,836.99] * | −400.11 [−439.72, −360.49] * | 95.8 [95.1, 96.6] |
| t100, ds 1 | φ 0.6 | −6,940.94 [−7,043.27, −6,838.61] * | −2,354.62 [−2,437.10, −2,272.13] * | −2,348.04 [−2,402.30, −2,293.77] * | −846.79 [−890.63, −802.94] * | 95.7 [95.0, 96.5] |
| t100, ds 1 | φ 0.4 | −8,391.37 [−8,480.74, −8,301.99] * | −3,805.04 [−3,904.96, −3,705.12] * | −2,844.82 [−2,889.76, −2,799.88] * | −1,343.57 [−1,399.09, −1,288.06] * | 95.7 [94.9, 96.4] |
| t100, ds 1 | slope over 1 − φ |  | −5,812.24 [−5,958.99, −5,665.50] * |  | −2,000.87 [−2,069.96, −1,931.78] * |  |

## Copied originals

Per seed the mean over the genuine stalls copied by at least one counterfeit; on − off. Rating unrated = 0.5.

| Cell | Arm | Originals copied | Rating day 10 | Rating day 20 | Rating day 30 | Rating day 30 (on, level) | Profit, 30 days ($) | Profit, days 21–30 ($) |
|---|---|---|---|---|---|---|---|---|
| t40, ds 0 | φ 1 | 10.8 [10.4, 11.3] | −0.315 [−0.328, −0.303] * | −0.358 [−0.377, −0.340] * | −0.362 [−0.381, −0.343] * | 0.638 [0.619, 0.657] | −1,092.55 [−1,271.09, −914.01] * | −522.16 [−590.36, −453.95] * |
| t40, ds 0 | φ 0.8 | 10.8 [10.4, 11.3] | −0.457 [−0.471, −0.444] * | −0.519 [−0.538, −0.499] * | −0.534 [−0.551, −0.516] * | 0.466 [0.449, 0.484] | −2,362.00 [−2,544.56, −2,179.44] * | −985.72 [−1,068.74, −902.70] * |
| t40, ds 0 | φ 0.6 | 10.8 [10.4, 11.3] | −0.478 [−0.493, −0.464] * | −0.561 [−0.582, −0.540] * | −0.589 [−0.604, −0.574] * | 0.411 [0.396, 0.426] | −2,545.28 [−2,727.81, −2,362.74] * | −1,087.10 [−1,175.36, −998.83] * |
| t40, ds 0 | φ 0.4 | 10.8 [10.4, 11.3] | −0.486 [−0.501, −0.471] * | −0.569 [−0.590, −0.547] * | −0.598 [−0.614, −0.582] * | 0.402 [0.386, 0.418] | −2,576.54 [−2,756.81, −2,396.26] * | −1,097.42 [−1,184.67, −1,010.17] * |
| t40, ds 1 | φ 1 | 10.9 [10.5, 11.4] | −0.204 [−0.214, −0.194] * | −0.215 [−0.229, −0.201] * | −0.211 [−0.223, −0.200] * | 0.789 [0.777, 0.800] | −406.76 [−554.37, −259.15] * | −229.03 [−287.50, −170.56] * |
| t40, ds 1 | φ 0.8 | 10.9 [10.5, 11.4] | −0.283 [−0.294, −0.271] * | −0.299 [−0.314, −0.283] * | −0.295 [−0.308, −0.281] * | 0.705 [0.692, 0.719] | −1,239.66 [−1,386.56, −1,092.76] * | −531.70 [−594.53, −468.88] * |
| t40, ds 1 | φ 0.6 | 10.9 [10.5, 11.4] | −0.293 [−0.305, −0.281] * | −0.315 [−0.333, −0.298] * | −0.312 [−0.327, −0.296] * | 0.688 [0.673, 0.704] | −1,306.44 [−1,450.54, −1,162.35] * | −571.64 [−634.93, −508.36] * |
| t40, ds 1 | φ 0.4 | 10.9 [10.5, 11.4] | −0.299 [−0.312, −0.287] * | −0.320 [−0.337, −0.303] * | −0.319 [−0.334, −0.304] * | 0.681 [0.666, 0.696] | −1,334.81 [−1,475.20, −1,194.43] * | −578.45 [−642.86, −514.04] * |
| t100, ds 0 | φ 1 | 10.3 [9.8, 10.8] | −0.532 [−0.543, −0.521] * | −0.562 [−0.576, −0.548] * | −0.559 [−0.574, −0.544] * | 0.441 [0.426, 0.456] | +495.75 [+284.22, +707.27] * | +62.18 [−8.32, +132.68] |
| t100, ds 0 | φ 0.8 | 10.3 [9.8, 10.8] | −0.718 [−0.725, −0.710] * | −0.746 [−0.755, −0.737] * | −0.750 [−0.758, −0.742] * | 0.250 [0.242, 0.258] | −1,100.44 [−1,245.98, −954.89] * | −450.32 [−501.56, −399.08] * |
| t100, ds 0 | φ 0.6 | 10.3 [9.8, 10.8] | −0.732 [−0.739, −0.725] * | −0.761 [−0.770, −0.752] * | −0.765 [−0.772, −0.757] * | 0.235 [0.228, 0.243] | −1,128.92 [−1,274.36, −983.47] * | −462.29 [−513.55, −411.02] * |
| t100, ds 0 | φ 0.4 | 10.3 [9.8, 10.8] | −0.733 [−0.740, −0.726] * | −0.761 [−0.770, −0.752] * | −0.764 [−0.772, −0.757] * | 0.236 [0.228, 0.243] | −1,130.51 [−1,275.99, −985.03] * | −462.29 [−513.55, −411.04] * |
| t100, ds 1 | φ 1 | 10.9 [10.4, 11.3] | −0.261 [−0.271, −0.251] * | −0.267 [−0.282, −0.253] * | −0.272 [−0.282, −0.262] * | 0.728 [0.718, 0.738] | +350.98 [+172.76, +529.20] * | +72.92 [+6.34, +139.50] * |
| t100, ds 1 | φ 0.8 | 10.9 [10.4, 11.3] | −0.348 [−0.360, −0.336] * | −0.366 [−0.380, −0.351] * | −0.364 [−0.377, −0.352] * | 0.636 [0.623, 0.648] | −713.46 [−889.92, −537.00] * | −301.79 [−369.79, −233.78] * |
| t100, ds 1 | φ 0.6 | 10.9 [10.4, 11.3] | −0.359 [−0.370, −0.349] * | −0.381 [−0.396, −0.366] * | −0.379 [−0.393, −0.365] * | 0.621 [0.607, 0.635] | −758.92 [−934.24, −583.60] * | −323.76 [−391.27, −256.25] * |
| t100, ds 1 | φ 0.4 | 10.9 [10.4, 11.3] | −0.366 [−0.376, −0.356] * | −0.385 [−0.400, −0.370] * | −0.382 [−0.396, −0.369] * | 0.618 [0.604, 0.631] | −775.52 [−950.23, −600.81] * | −327.93 [−395.89, −259.97] * |

## Counterfeit prices and sales

Days 2–30, per counterfeit stall-day; margin = price − unit cost. Below cost: share of stall-days priced below unit cost.

| Cell | Arm | Price ($) | Margin ($) | Units per stall-day | Below cost (%) |
|---|---|---|---|---|---|
| t40, ds 0 | φ 1 | 58.63 [57.85, 59.41] | +33.21 [+32.32, +34.11] * | 3.10 [3.03, 3.16] | 0.0 [0.0, 0.0] |
| t40, ds 0 | φ 0.8 | 44.52 [44.11, 44.94] | +19.10 [+18.57, +19.64] * | 3.90 [3.85, 3.95] | 0.0 [0.0, 0.0] |
| t40, ds 0 | φ 0.6 | 33.01 [32.72, 33.31] | +7.59 [+7.16, +8.02] * | 4.24 [4.19, 4.28] | 2.8 [1.9, 3.8] |
| t40, ds 0 | φ 0.4 | 21.97 [21.77, 22.16] | −3.45 [−3.82, −3.09] * | 4.30 [4.25, 4.34] | 81.0 [78.5, 83.4] |
| t40, ds 1 | φ 1 | 61.71 [61.01, 62.41] | +36.29 [+35.47, +37.10] * | 1.84 [1.79, 1.88] | 0.0 [0.0, 0.0] |
| t40, ds 1 | φ 0.8 | 47.99 [47.48, 48.49] | +22.57 [+21.96, +23.17] * | 2.37 [2.32, 2.42] | 0.0 [0.0, 0.0] |
| t40, ds 1 | φ 0.6 | 35.82 [35.43, 36.21] | +10.40 [+9.90, +10.91] * | 2.49 [2.44, 2.54] | 0.1 [−0.0, 0.2] |
| t40, ds 1 | φ 0.4 | 23.83 [23.57, 24.08] | −1.59 [−1.99, −1.19] * | 2.57 [2.52, 2.63] | 64.3 [60.0, 68.6] |
| t100, ds 0 | φ 1 | 55.09 [54.71, 55.48] | +29.67 [+29.16, +30.18] * | 7.66 [7.52, 7.80] | 0.0 [0.0, 0.0] |
| t100, ds 0 | φ 0.8 | 41.40 [41.30, 41.50] | +15.98 [+15.68, +16.28] * | 9.76 [9.68, 9.83] | 0.0 [0.0, 0.0] |
| t100, ds 0 | φ 0.6 | 30.91 [30.83, 30.98] | +5.49 [+5.20, +5.78] * | 10.53 [10.49, 10.58] | 2.5 [1.4, 3.6] |
| t100, ds 0 | φ 0.4 | 20.60 [20.55, 20.65] | −4.82 [−5.11, −4.53] * | 10.58 [10.54, 10.63] | 94.4 [93.7, 95.0] |
| t100, ds 1 | φ 1 | 60.70 [60.23, 61.17] | +35.28 [+34.69, +35.87] * | 3.08 [3.01, 3.15] | 0.0 [0.0, 0.0] |
| t100, ds 1 | φ 0.8 | 47.20 [46.90, 47.50] | +21.78 [+21.35, +22.22] * | 4.00 [3.94, 4.07] | 0.0 [0.0, 0.0] |
| t100, ds 1 | φ 0.6 | 35.27 [35.03, 35.50] | +9.85 [+9.46, +10.24] * | 4.26 [4.19, 4.32] | 0.0 [0.0, 0.0] |
| t100, ds 1 | φ 0.4 | 23.48 [23.32, 23.63] | −1.94 [−2.28, −1.60] * | 4.34 [4.27, 4.40] | 70.0 [65.7, 74.3] |

## Catches and buyers

Catches: market total over 30 days. Shortfall (points of purchases) and surplus ($ per buyer), on − off, 30 days.

| Cell | Arm | Catches | tourist: shortfall (pts) | local: shortfall (pts) | expert: shortfall (pts) | tourist: surplus ($) | local: surplus ($) | expert: surplus ($) |
|---|---|---|---|---|---|---|---|---|
| t40, ds 0 | off | 0 [0, 0] | – | – | – | – | – | – |
| t40, ds 0 | φ 1 | 0 [0, 0] | −12.7 [−13.6, −11.8] * | +1.0 [+0.9, +1.1] * | +0.0 [+0.0, +0.0] | +0.49 [−0.10, +1.09] | +0.97 [+0.73, +1.21] * | +1.36 [+1.12, +1.60] * |
| t40, ds 0 | φ 0.8 | 0 [0, 0] | −0.8 [−0.9, −0.6] * | +0.9 [+0.8, +1.0] * | +0.0 [+0.0, +0.0] | +4.48 [+4.05, +4.90] * | +1.19 [+0.90, +1.48] * | +1.37 [+1.10, +1.63] * |
| t40, ds 0 | φ 0.6 | 0 [0, 0] | +1.5 [+1.2, +1.7] * | +1.0 [+0.9, +1.0] * | +0.0 [+0.0, +0.0] | +14.11 [+13.70, +14.53] * | +1.25 [+0.99, +1.50] * | +1.26 [+1.02, +1.50] * |
| t40, ds 0 | φ 0.4 | 0 [0, 0] | +1.7 [+1.4, +2.0] * | +0.9 [+0.8, +0.9] * | +0.0 [+0.0, +0.0] | +25.05 [+24.60, +25.50] * | +1.43 [+1.15, +1.70] * | +1.30 [+1.04, +1.56] * |
| t40, ds 1 | off | 958 [934, 981] | – | – | – | – | – | – |
| t40, ds 1 | φ 1 | 960 [936, 984] | −8.6 [−9.2, −8.0] * | −1.0 [−1.1, −0.8] * | +0.0 [+0.0, +0.0] | +4.80 [+4.37, +5.23] * | +3.00 [+2.78, +3.23] * | +1.90 [+1.72, +2.07] * |
| t40, ds 1 | φ 0.8 | 963 [939, 988] | −0.1 [−0.3, +0.1] | −1.1 [−1.2, −0.9] * | +0.0 [+0.0, +0.0] | +6.87 [+6.46, +7.28] * | +3.50 [+3.21, +3.80] * | +2.32 [+2.04, +2.59] * |
| t40, ds 1 | φ 0.6 | 962 [938, 986] | +0.5 [+0.3, +0.8] * | −1.0 [−1.2, −0.9] * | +0.0 [+0.0, +0.0] | +13.44 [+13.01, +13.87] * | +3.65 [+3.35, +3.94] * | +2.33 [+2.05, +2.60] * |
| t40, ds 1 | φ 0.4 | 961 [937, 985] | +1.0 [+0.7, +1.3] * | −1.1 [−1.2, −0.9] * | +0.0 [+0.0, +0.0] | +20.42 [+19.95, +20.88] * | +3.88 [+3.58, +4.17] * | +2.44 [+2.15, +2.73] * |
| t100, ds 0 | off | 0 [0, 0] | – | – | – | – | – | – |
| t100, ds 0 | φ 1 | 0 [0, 0] | −12.5 [−13.3, −11.7] * | – | – | +3.71 [+3.09, +4.33] * | – | – |
| t100, ds 0 | φ 0.8 | 0 [0, 0] | +0.0 [−0.1, +0.1] | – | – | +7.50 [+7.29, +7.70] * | – | – |
| t100, ds 0 | φ 0.6 | 0 [0, 0] | +1.6 [+1.4, +1.8] * | – | – | +16.87 [+16.53, +17.22] * | – | – |
| t100, ds 0 | φ 0.4 | 0 [0, 0] | +1.7 [+1.5, +2.0] * | – | – | +27.30 [+26.92, +27.68] * | – | – |
| t100, ds 1 | off | 1435 [1424, 1447] | – | – | – | – | – | – |
| t100, ds 1 | φ 1 | 1435 [1423, 1446] | −6.0 [−6.5, −5.5] * | – | – | +5.63 [+5.28, +5.99] * | – | – |
| t100, ds 1 | φ 0.8 | 1438 [1426, 1449] | +0.1 [−0.1, +0.2] | – | – | +7.59 [+7.37, +7.81] * | – | – |
| t100, ds 1 | φ 0.6 | 1436 [1424, 1447] | +0.6 [+0.4, +0.8] * | – | – | +12.09 [+11.79, +12.40] * | – | – |
| t100, ds 1 | φ 0.4 | 1435 [1424, 1446] | +0.8 [+0.6, +1.1] * | – | – | +16.99 [+16.61, +17.37] * | – | – |

## Stuck, parked and idle buyers

| Condition | Chains | Buyer-days | Stuck | Parked | Idle choosers | Invalid actions |
|---|---|---|---|---|---|---|
| off · t40 · ds0.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| off · t40 · ds1.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| off · t100 · ds0.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| off · t100 · ds1.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| phi1.0 · t40 · ds0.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| phi1.0 · t40 · ds1.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| phi1.0 · t100 · ds0.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| phi1.0 · t100 · ds1.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| phi0.8 · t40 · ds0.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| phi0.8 · t40 · ds1.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| phi0.8 · t100 · ds0.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| phi0.8 · t100 · ds1.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| phi0.6 · t40 · ds0.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| phi0.6 · t40 · ds1.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| phi0.6 · t100 · ds0.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| phi0.6 · t100 · ds1.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| phi0.4 · t40 · ds0.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| phi0.4 · t40 · ds1.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| phi0.4 · t100 · ds0.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| phi0.4 · t100 · ds1.0 | 30 | 135,000 | 0 | 0 | 0 | 0 |

## Flags

- none

## Reading (written after the results)

- **Undercutting the original never pays here; the lower the price, the bigger the loss.** PK1 is contradicted. At tourist share 1.0 with detect_scale 1, the slope of the gap over (1 − φ) is −$5,812 [−5,959, −5,666]. The gap falls at every step:
  - φ 1.0: −$370;
  - φ 0.8: −$1,036;
  - φ 0.6: −$2,355;
  - φ 0.4: −$3,805.

  The slope is negative in all four markets (−$3,373 to −$13,351).
- **A cheaper counterfeit wins only the buyers the deceptive stall already had under its own name.** The figures below are days 2–30, per copied-name stall, mean over seeds, at t100, ds 1. They were computed from the cache after the run, not by the frozen script.
  - In the off arm, these stalls post $56.0 under their own names and sell 116 units.
  - As counterfeits at φ 1.0 they post the original's $60.7 and sell 89.
  - At φ 0.8 they post $47.2 and sell 116, the same as off, at a lower price.
  - Below φ 0.8 units barely move: 4.00, 4.26 and 4.34 per stall-day at φ 0.8, 0.6 and 0.4, while the margin falls from +$21.78 to −$1.94.
  - The buyer rule ranks by rating, then price. So every φ < 1 wins the same buyers, and a lower φ adds units only through budgets.
- **Copying the original's price loses too, whenever there is enforcement.** PK2 is supported: −$370 [−458, −282] at t100, ds 1. Counterfeiting at φ 1.0 pays only without enforcement: +$936 at t100 and +$641 at t40 (ds 0).
  - Even then, undercutting by 20% already loses: −$1,037 at t100, −$111 at t40.
  - Catches per stall are the same as off in every cell (95.7 at t100, ds 1). The copied name changes what the stall earns per sale, not how often it is caught.
- **Counterfeits damage the copied brand's rating at every price.** PK3 is supported: at φ 0.6 the original's day-30 rating is −0.379 [−0.393, −0.365] against off (0.62 against 1.0).
  - The damage is −0.27 at φ 1.0 and grows to −0.38 at φ 0.4.
  - It is largest without enforcement: −0.56 to −0.76 at t100, ds 0.
  - Most of it is in place by day 10.
- **The original gains from a full-price copy and loses from a cheaper one** (PK5, exploratory). At t100, ds 1:
  - φ 1.0: +$351 [+173, +529] over 30 days;
  - φ 0.8 to 0.4: −$713 to −$776, nearly flat across φ.

  From the cache (days 2–30, t100, ds 1), the copied originals sell 266 units at φ 1.0 against 192 off. A counterfeit at the original's price no longer undercuts it, so tourists who take the cheapest stall move to the original, though its rating falls. At φ < 1 the counterfeit undercuts it under its own name, and the original's price falls with its rating.
- **Locals reduce the size of the gap but not its sign** (PK4, exploratory). By the prespecified criterion (gap at t40 < gap at t100), PK4 is supported in only 1 of 8 cells: ds 0, φ 1.0, −$295.
  - In the other 7 the gaps are negative and smaller at t40, so the signed difference is positive and the verdict is "contradicted".
  - In magnitude, the gap is smaller at t40 in all 8 cells. Counterfeits sell fewer units with fewer tourists (1.8–2.6 against 3.1–4.3 per stall-day at ds 1), which scales gains and losses alike.
  - The prespecified verdicts stand.
- **Tourists gain from cheap counterfeits** (exploratory). At t100, ds 1:
  - Their surplus rises $5.6 (φ 1.0) to $17.0 (φ 0.4) per tourist against off. Counterfeits sold near or below cost pass the stall's loss to buyers.
  - At φ 1.0 their shortfall falls 6.0 points (−12.5 at ds 0), and the shortfall changes little at lower φ (−0.8 to +1.7 points across all cells).
  - Locals and experts move by less than $4 in surplus and about 1 point in shortfall.

## Caveats

- **Price acts by rank in the buyer rule.** Among stalls that qualify, buyers take the highest visible rating, then the lowest price (tourists take the lowest price). Any φ < 1 therefore wins the same buyers, and PK1's straight-line slope is fitted over a step-shaped response. Under a demand rule where a cut in price wins share among equally rated stalls, undercutting could pay. That is untested.
- **The off arm keeps fresh renames; the on arms have none.** In off, a caught deceptive stall reopens under a fresh name. In on, a counterfeit keeps the copied name to day 30. The gap therefore combines taking the original's name with losing the fresh-name reset. Catches are equal across arms, so the reset does not change how often stalls are caught.
- **Counterfeits are a fixed policy, not a choice.** Every deceptive stall copies on day 2 and holds its φ for 29 days, even at φ 0.4, where it prices below unit cost on 64–94% of stall-days. No seller in this market would choose that price; the run compares fixed policies.
- **Day-entry counterfeits claim the original's true quality,** and they target the top-rated genuine brand by day-1 ratings (unrated counts 0.5). These follow from the spec, not from any data.
- **The mechanism figures in the reading** (posted prices and units of the copied-name stalls and originals, on against off) were computed after the run from `runs/canal_street_cache.jsonl`, not by the frozen script. They are seed means without intervals.
- **One market, one horizon:** the licensing market, 30 days known, 150 buyers, brand premium 0.4. Seeds 270–299.
- 95% intervals, unadjusted. Only PK1–PK3 are confirmatory; every other row, including all of PK4 and PK5, is exploratory.
