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

- Engine `0.17.0`; commit `54584484b5a1eef8b63c605bb38ae1e6d76b4ae5`; uncommitted at run time: ['?? runs/pilot_canal_equity/', '?? runs/pilot_canal_equity_stdout.log', '?? runs/queue_canal_then_equity.sh']
- Script sha256 `4960f127f646b0d459c005ef34892a1583f40e2de976211daca2d6cb71015746`
- Command: `python -m analysis.canal_street --ref 60f1ddf --tests 1109 passed, 17 skipped at e9cdc07 (runs/tests_0170.log)`
- Tests: 1109 passed, 17 skipped at e9cdc07 (runs/tests_0170.log)
- Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit
- 60 chains × 30 days on 4 workers (nice 19); wall clock 0.11 h; load average [2.65, 3.72, 3.41] at start, [6.21, 5.67, 4.51] at end; memory at start {'swap_free_mb': 913.69, 'free_pct': 54}, at end {'swap_free_mb': 913.69, 'free_pct': 55}; memory-guard pauses: 0
- Seeds 900-902 (3), paired across all conditions

## Gate

pilot (this is the pilot)

## Predictions: 30-day totals (primary)

| Prediction | Estimate | Verdict |
|---|---|---|
| **PK1**: t100, ds 1: slope of the gap over (1 − φ) | −5,724.11 [−6,322.75, −5,125.48] * | contradicted (interval on the opposite side of 0) |
| **PK2**: t100, ds 1, φ 1.0: gap | −255.11 [−699.21, +188.99] | not supported (interval includes 0) |
| **PK3**: t100, ds 1, φ 0.6: copied originals' day-30 rating, on − off | −0.383 [−0.435, −0.332] * | supported |
| **PK4 ds0 φ1**: ds 0, φ 1: gap at t40 − gap at t100 (exploratory) | −187.53 [−336.25, −38.80] * | supported |
| **PK4 ds0 φ0.8**: ds 0, φ 0.8: gap at t40 − gap at t100 (exploratory) | +870.20 [+665.89, +1,074.51] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds0 φ0.6**: ds 0, φ 0.6: gap at t40 − gap at t100 (exploratory) | +2,470.51 [+2,179.25, +2,761.78] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds0 φ0.4**: ds 0, φ 0.4: gap at t40 − gap at t100 (exploratory) | +4,242.92 [+3,928.20, +4,557.63] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds1 φ1**: ds 1, φ 1: gap at t40 − gap at t100 (exploratory) | +81.65 [−771.45, +934.76] | not supported (interval includes 0) |
| **PK4 ds1 φ0.8**: ds 1, φ 0.8: gap at t40 − gap at t100 (exploratory) | +364.91 [−246.25, +976.07] | not supported (interval includes 0) |
| **PK4 ds1 φ0.6**: ds 1, φ 0.6: gap at t40 − gap at t100 (exploratory) | +865.81 [+420.27, +1,311.34] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds1 φ0.4**: ds 1, φ 0.4: gap at t40 − gap at t100 (exploratory) | +1,418.14 [+672.91, +2,163.38] * | contradicted (interval on the opposite side of 0) |
| **PK5 φ1**: t100, ds 1, φ 1: originals' profit, on − off (exploratory, no direction) | +292.30 [−431.26, +1,015.86] | interval includes 0 |
| **PK5 φ0.8**: t100, ds 1, φ 0.8: originals' profit, on − off (exploratory, no direction) | −784.23 [−1,783.73, +215.27] | interval includes 0 |
| **PK5 φ0.6**: t100, ds 1, φ 0.6: originals' profit, on − off (exploratory, no direction) | −844.00 [−1,846.42, +158.43] | interval includes 0 |
| **PK5 φ0.4**: t100, ds 1, φ 0.4: originals' profit, on − off (exploratory, no direction) | −845.19 [−1,896.41, +206.03] | interval includes 0 |

## Predictions: days 21–30

| Prediction | Estimate | Verdict |
|---|---|---|
| **PK1**: t100, ds 1: slope of the gap over (1 − φ) (days 21–30) | −2,064.59 [−3,107.89, −1,021.29] * | contradicted (interval on the opposite side of 0) |
| **PK2**: t100, ds 1, φ 1.0: gap (days 21–30) | −129.95 [−547.66, +287.76] | not supported (interval includes 0) |
| **PK4 ds0 φ1**: ds 0, φ 1: gap at t40 − gap at t100 (days 21–30) (exploratory) | −43.32 [−130.41, +43.77] | not supported (interval includes 0) |
| **PK4 ds0 φ0.8**: ds 0, φ 0.8: gap at t40 − gap at t100 (days 21–30) (exploratory) | +370.46 [+259.78, +481.14] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds0 φ0.6**: ds 0, φ 0.6: gap at t40 − gap at t100 (days 21–30) (exploratory) | +902.30 [+680.55, +1,124.04] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds0 φ0.4**: ds 0, φ 0.4: gap at t40 − gap at t100 (days 21–30) (exploratory) | +1,515.15 [+1,269.70, +1,760.60] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds1 φ1**: ds 1, φ 1: gap at t40 − gap at t100 (days 21–30) (exploratory) | +4.89 [−622.96, +632.74] | not supported (interval includes 0) |
| **PK4 ds1 φ0.8**: ds 1, φ 0.8: gap at t40 − gap at t100 (days 21–30) (exploratory) | +103.24 [−40.52, +247.00] | not supported (interval includes 0) |
| **PK4 ds1 φ0.6**: ds 1, φ 0.6: gap at t40 − gap at t100 (days 21–30) (exploratory) | +285.75 [+19.70, +551.81] * | contradicted (interval on the opposite side of 0) |
| **PK4 ds1 φ0.4**: ds 1, φ 0.4: gap at t40 − gap at t100 (days 21–30) (exploratory) | +475.47 [+228.77, +722.17] * | contradicted (interval on the opposite side of 0) |
| **PK5 φ1**: t100, ds 1, φ 1: originals' profit, on − off (days 21–30) (exploratory, no direction) | +56.15 [−310.91, +423.21] | interval includes 0 |
| **PK5 φ0.8**: t100, ds 1, φ 0.8: originals' profit, on − off (days 21–30) (exploratory, no direction) | −305.36 [−694.37, +83.64] | interval includes 0 |
| **PK5 φ0.6**: t100, ds 1, φ 0.6: originals' profit, on − off (days 21–30) (exploratory, no direction) | −325.79 [−641.97, −9.60] * | interval excludes 0 |
| **PK5 φ0.4**: t100, ds 1, φ 0.4: originals' profit, on − off (days 21–30) (exploratory, no direction) | −329.19 [−654.03, −4.35] * | interval excludes 0 |

## Deceptive stalls by condition

Per deceptive stall, $. Gap = on − off (same stall, same seed).

| Cell | Arm | Profit, 30 days | Gap, 30 days | Profit, days 21–30 | Gap, days 21–30 | Catches per stall |
|---|---|---|---|---|---|---|
| t40, ds 0 | off | +1,985.11 [+1,787.16, +2,183.06] * | – | +699.23 [+629.86, +768.61] * | – | 0.0 [0.0, 0.0] |
| t40, ds 0 | φ 1 | +2,628.32 [+2,394.88, +2,861.76] * | +643.21 [+564.73, +721.69] * | +882.35 [+818.74, +945.96] * | +183.12 [+175.63, +190.60] * | 0.0 [0.0, 0.0] |
| t40, ds 0 | φ 0.8 | +1,816.46 [+1,561.97, +2,070.96] * | −168.64 [−330.61, −6.68] * | +554.90 [+437.91, +671.88] * | −144.33 [−213.41, −75.26] * | 0.0 [0.0, 0.0] |
| t40, ds 0 | φ 0.6 | +576.71 [+372.90, +780.51] * | −1,408.40 [−1,508.67, −1,308.13] * | +119.52 [+90.19, +148.86] * | −579.71 [−623.39, −536.03] * | 0.0 [0.0, 0.0] |
| t40, ds 0 | φ 0.4 | −774.93 [−1,036.81, −513.05] * | −2,760.04 [−2,929.19, −2,590.88] * | −341.09 [−387.74, −294.44] * | −1,040.32 [−1,108.65, −971.99] * | 0.0 [0.0, 0.0] |
| t40, ds 0 | slope over 1 − φ |  | −5,724.75 [−5,999.14, −5,450.35] * |  | −2,052.85 [−2,195.35, −1,910.34] * |  |
| t40, ds 1 | off | −3,471.24 [−3,869.62, −3,072.85] * | – | −1,000.14 [−1,200.82, −799.46] * | – | 61.9 [57.0, 66.8] |
| t40, ds 1 | φ 1 | −3,644.69 [−4,452.46, −2,836.93] * | −173.46 [−592.33, +245.42] | −1,125.19 [−1,508.26, −742.12] * | −125.05 [−343.93, +93.82] | 62.7 [56.3, 69.1] |
| t40, ds 1 | φ 0.8 | −4,071.97 [−4,744.74, −3,399.20] * | −600.74 [−932.60, −268.88] * | −1,295.73 [−1,497.22, −1,094.23] * | −295.59 [−384.81, −206.37] * | 63.0 [56.6, 69.4] |
| t40, ds 1 | φ 0.6 | −4,844.80 [−5,445.51, −4,244.09] * | −1,373.56 [−1,599.80, −1,147.33] * | −1,566.58 [−1,726.50, −1,406.65] * | −566.44 [−611.53, −521.35] * | 62.7 [55.5, 70.0] |
| t40, ds 1 | φ 0.4 | −5,699.70 [−6,170.27, −5,229.13] * | −2,228.47 [−2,326.36, −2,130.58] * | −1,879.89 [−2,031.92, −1,727.86] * | −879.75 [−939.15, −820.35] * | 62.8 [56.0, 69.7] |
| t40, ds 1 | slope over 1 − φ |  | −3,468.93 [−4,040.95, −2,896.91] * |  | −1,267.47 [−1,616.67, −918.28] * |  |
| t100, ds 0 | off | +5,233.69 [+5,020.93, +5,446.45] * | – | +1,800.04 [+1,699.92, +1,900.16] * | – | 0.0 [0.0, 0.0] |
| t100, ds 0 | φ 1 | +6,064.42 [+5,879.35, +6,249.50] * | +830.74 [+628.54, +1,032.94] * | +2,026.48 [+1,848.41, +2,204.55] * | +226.44 [+132.00, +320.87] * | 0.0 [0.0, 0.0] |
| t100, ds 0 | φ 0.8 | +4,194.84 [+3,984.35, +4,405.34] * | −1,038.84 [−1,081.41, −996.28] * | +1,285.25 [+1,278.00, +1,292.49] * | −514.79 [−607.68, −421.91] * | 0.0 [0.0, 0.0] |
| t100, ds 0 | φ 0.6 | +1,354.77 [+907.87, +1,801.67] * | −3,878.92 [−4,248.12, −3,509.71] * | +318.03 [+205.76, +430.31] * | −1,482.01 [−1,678.15, −1,285.87] * | 0.0 [0.0, 0.0] |
| t100, ds 0 | φ 0.4 | −1,769.27 [−2,302.59, −1,235.94] * | −7,002.95 [−7,468.27, −6,537.64] * | −755.43 [−903.73, −607.13] * | −2,555.47 [−2,786.79, −2,324.16] * | 0.0 [0.0, 0.0] |
| t100, ds 0 | slope over 1 − φ |  | −13,170.57 [−13,848.33, −12,492.82] * |  | −4,656.47 [−5,115.16, −4,197.78] * |  |
| t100, ds 1 | off | −4,857.41 [−5,767.42, −3,947.41] * | – | −1,476.07 [−1,730.58, −1,221.56] * | – | 96.3 [87.4, 105.3] |
| t100, ds 1 | φ 1 | −5,112.52 [−5,661.76, −4,563.29] * | −255.11 [−699.21, +188.99] | −1,606.02 [−2,162.19, −1,049.85] * | −129.95 [−547.66, +287.76] | 95.9 [85.9, 105.8] |
| t100, ds 1 | φ 0.8 | −5,823.06 [−6,475.54, −5,170.58] * | −965.65 [−1,322.81, −608.48] * | −1,874.90 [−2,185.13, −1,564.66] * | −398.82 [−622.34, −175.30] * | 96.4 [87.0, 105.8] |
| t100, ds 1 | φ 0.6 | −7,096.79 [−7,786.73, −6,406.85] * | −2,239.37 [−2,459.44, −2,019.31] * | −2,328.27 [−2,468.43, −2,188.11] * | −852.19 [−1,078.86, −625.53] * | 96.2 [86.3, 106.0] |
| t100, ds 1 | φ 0.4 | −8,504.02 [−8,773.87, −8,234.18] * | −3,646.61 [−4,296.96, −2,996.27] * | −2,831.29 [−2,955.78, −2,706.80] * | −1,355.22 [−1,544.09, −1,166.34] * | 96.2 [87.3, 105.1] |
| t100, ds 1 | slope over 1 − φ |  | −5,724.11 [−6,322.75, −5,125.48] * |  | −2,064.59 [−3,107.89, −1,021.29] * |  |

## Copied originals

Per seed the mean over the genuine stalls copied by at least one counterfeit; on − off. Rating unrated = 0.5.

| Cell | Arm | Originals copied | Rating day 10 | Rating day 20 | Rating day 30 | Rating day 30 (on, level) | Profit, 30 days ($) | Profit, days 21–30 ($) |
|---|---|---|---|---|---|---|---|---|
| t40, ds 0 | φ 1 | 11.3 [7.5, 15.1] | −0.276 [−0.371, −0.182] * | −0.336 [−0.458, −0.215] * | −0.308 [−0.399, −0.217] * | 0.692 [0.601, 0.783] | −1,298.67 [−2,601.44, +4.11] | −560.03 [−874.25, −245.82] * |
| t40, ds 0 | φ 0.8 | 11.3 [7.5, 15.1] | −0.439 [−0.537, −0.341] * | −0.485 [−0.621, −0.350] * | −0.482 [−0.544, −0.421] * | 0.518 [0.456, 0.579] | −2,553.57 [−4,317.69, −789.45] * | −967.79 [−1,422.27, −513.30] * |
| t40, ds 0 | φ 0.6 | 11.3 [7.5, 15.1] | −0.446 [−0.532, −0.359] * | −0.541 [−0.709, −0.372] * | −0.549 [−0.643, −0.454] * | 0.451 [0.357, 0.546] | −2,750.97 [−4,623.81, −878.14] * | −1,078.10 [−1,619.92, −536.27] * |
| t40, ds 0 | φ 0.4 | 11.3 [7.5, 15.1] | −0.451 [−0.525, −0.377] * | −0.558 [−0.700, −0.416] * | −0.551 [−0.624, −0.478] * | 0.449 [0.376, 0.522] | −2,825.07 [−4,741.52, −908.62] * | −1,100.25 [−1,581.53, −618.97] * |
| t40, ds 1 | φ 1 | 11.3 [7.5, 15.1] | −0.165 [−0.182, −0.147] * | −0.195 [−0.291, −0.098] * | −0.205 [−0.277, −0.134] * | 0.795 [0.723, 0.866] | −522.41 [−1,759.01, +714.19] | −221.93 [−632.15, +188.28] |
| t40, ds 1 | φ 0.8 | 11.3 [7.5, 15.1] | −0.224 [−0.252, −0.196] * | −0.276 [−0.368, −0.184] * | −0.306 [−0.410, −0.201] * | 0.694 [0.590, 0.799] | −1,260.95 [−2,567.68, +45.78] | −514.29 [−931.39, −97.19] * |
| t40, ds 1 | φ 0.6 | 11.3 [7.5, 15.1] | −0.225 [−0.255, −0.194] * | −0.281 [−0.375, −0.187] * | −0.319 [−0.411, −0.226] * | 0.681 [0.589, 0.774] | −1,325.62 [−2,497.63, −153.61] * | −561.35 [−887.63, −235.08] * |
| t40, ds 1 | φ 0.4 | 11.3 [7.5, 15.1] | −0.230 [−0.265, −0.195] * | −0.292 [−0.372, −0.212] * | −0.329 [−0.418, −0.239] * | 0.671 [0.582, 0.761] | −1,358.15 [−2,554.38, −161.91] * | −571.15 [−911.39, −230.90] * |
| t100, ds 0 | φ 1 | 11.3 [7.5, 15.1] | −0.499 [−0.557, −0.442] * | −0.543 [−0.684, −0.402] * | −0.529 [−0.617, −0.441] * | 0.471 [0.383, 0.559] | +675.61 [−63.96, +1,415.18] | +125.98 [−72.88, +324.83] |
| t100, ds 0 | φ 0.8 | 11.3 [7.5, 15.1] | −0.710 [−0.727, −0.693] * | −0.745 [−0.822, −0.667] * | −0.755 [−0.776, −0.734] * | 0.245 [0.224, 0.266] | −1,064.59 [−2,142.60, +13.41] | −428.31 [−771.24, −85.37] * |
| t100, ds 0 | φ 0.6 | 11.3 [7.5, 15.1] | −0.724 [−0.741, −0.706] * | −0.763 [−0.839, −0.687] * | −0.767 [−0.786, −0.748] * | 0.233 [0.214, 0.252] | −1,094.05 [−2,185.48, −2.62] * | −437.90 [−780.30, −95.50] * |
| t100, ds 0 | φ 0.4 | 11.3 [7.5, 15.1] | −0.725 [−0.740, −0.709] * | −0.762 [−0.837, −0.688] * | −0.768 [−0.788, −0.748] * | 0.232 [0.212, 0.252] | −1,095.07 [−2,188.32, −1.82] * | −437.86 [−780.45, −95.28] * |
| t100, ds 1 | φ 1 | 11.3 [7.5, 15.1] | −0.226 [−0.243, −0.208] * | −0.238 [−0.252, −0.223] * | −0.282 [−0.314, −0.250] * | 0.718 [0.686, 0.750] | +292.30 [−431.26, +1,015.86] | +56.15 [−310.91, +423.21] |
| t100, ds 1 | φ 0.8 | 11.3 [7.5, 15.1] | −0.321 [−0.375, −0.268] * | −0.315 [−0.355, −0.275] * | −0.369 [−0.397, −0.340] * | 0.631 [0.603, 0.660] | −784.23 [−1,783.73, +215.27] | −305.36 [−694.37, +83.64] |
| t100, ds 1 | φ 0.6 | 11.3 [7.5, 15.1] | −0.329 [−0.393, −0.266] * | −0.327 [−0.372, −0.283] * | −0.383 [−0.435, −0.332] * | 0.617 [0.565, 0.668] | −844.00 [−1,846.42, +158.43] | −325.79 [−641.97, −9.60] * |
| t100, ds 1 | φ 0.4 | 11.3 [7.5, 15.1] | −0.328 [−0.390, −0.266] * | −0.333 [−0.381, −0.284] * | −0.385 [−0.438, −0.332] * | 0.615 [0.562, 0.668] | −845.19 [−1,896.41, +206.03] | −329.19 [−654.03, −4.35] * |

## Counterfeit prices and sales

Days 2–30, per counterfeit stall-day; margin = price − unit cost. Below cost: share of stall-days priced below unit cost.

| Cell | Arm | Price ($) | Margin ($) | Units per stall-day | Below cost (%) |
|---|---|---|---|---|---|
| t40, ds 0 | φ 1 | 58.61 [56.56, 60.67] | +33.30 [+31.48, +35.12] * | 3.01 [2.54, 3.48] | 0.0 [0.0, 0.0] |
| t40, ds 0 | φ 0.8 | 44.34 [42.69, 45.98] | +19.03 [+18.08, +19.97] * | 3.93 [3.62, 4.24] | 0.0 [0.0, 0.0] |
| t40, ds 0 | φ 0.6 | 32.79 [31.86, 33.72] | +7.48 [+6.55, +8.41] * | 4.22 [3.92, 4.52] | 3.6 [−3.6, 10.8] |
| t40, ds 0 | φ 0.4 | 21.77 [21.36, 22.17] | −3.55 [−4.78, −2.31] * | 4.27 [3.98, 4.56] | 80.2 [72.7, 87.6] |
| t40, ds 1 | φ 1 | 61.89 [60.11, 63.68] | +36.58 [+35.37, +37.80] * | 1.83 [1.62, 2.04] | 0.0 [0.0, 0.0] |
| t40, ds 1 | φ 0.8 | 48.28 [46.48, 50.09] | +22.97 [+21.55, +24.40] * | 2.38 [2.16, 2.61] | 0.0 [0.0, 0.0] |
| t40, ds 1 | φ 0.6 | 36.01 [34.35, 37.67] | +10.70 [+8.89, +12.51] * | 2.47 [2.18, 2.75] | 0.1 [−0.3, 0.4] |
| t40, ds 1 | φ 0.4 | 23.95 [22.83, 25.08] | −1.36 [−2.90, +0.19] | 2.56 [2.20, 2.92] | 65.1 [57.3, 72.8] |
| t100, ds 0 | φ 1 | 55.26 [53.54, 56.99] | +29.95 [+28.27, +31.63] * | 7.39 [6.92, 7.86] | 0.0 [0.0, 0.0] |
| t100, ds 0 | φ 0.8 | 41.37 [41.09, 41.64] | +16.06 [+14.67, +17.44] * | 9.86 [9.40, 10.32] | 0.0 [0.0, 0.0] |
| t100, ds 0 | φ 0.6 | 30.87 [30.61, 31.13] | +5.56 [+4.21, +6.90] * | 10.61 [10.56, 10.66] | 3.1 [−1.1, 7.3] |
| t100, ds 0 | φ 0.4 | 20.58 [20.40, 20.75] | −4.74 [−6.15, −3.32] * | 10.66 [10.59, 10.73] | 93.6 [90.8, 96.5] |
| t100, ds 1 | φ 1 | 61.01 [59.76, 62.25] | +35.70 [+33.57, +37.82] * | 3.03 [2.69, 3.37] | 0.0 [0.0, 0.0] |
| t100, ds 1 | φ 0.8 | 47.30 [45.83, 48.76] | +21.99 [+19.31, +24.66] * | 3.95 [3.19, 4.70] | 0.0 [0.0, 0.0] |
| t100, ds 1 | φ 0.6 | 35.32 [34.24, 36.40] | +10.01 [+7.70, +12.32] * | 4.21 [3.31, 5.11] | 0.0 [0.0, 0.0] |
| t100, ds 1 | φ 0.4 | 23.53 [22.86, 24.19] | −1.78 [−3.74, +0.18] | 4.29 [3.43, 5.15] | 70.0 [67.4, 72.5] |

## Catches and buyers

Catches: market total over 30 days. Shortfall (points of purchases) and surplus ($ per buyer), on − off, 30 days.

| Cell | Arm | Catches | tourist: shortfall (pts) | local: shortfall (pts) | expert: shortfall (pts) | tourist: surplus ($) | local: surplus ($) | expert: surplus ($) |
|---|---|---|---|---|---|---|---|---|
| t40, ds 0 | off | 0 [0, 0] | – | – | – | – | – | – |
| t40, ds 0 | φ 1 | 0 [0, 0] | −14.4 [−16.6, −12.2] * | +1.0 [+0.7, +1.2] * | +0.0 [+0.0, +0.0] | +0.68 [−2.36, +3.71] | +0.81 [−0.57, +2.19] | +1.37 [+1.22, +1.52] * |
| t40, ds 0 | φ 0.8 | 0 [0, 0] | −0.7 [−1.5, +0.1] | +0.8 [+0.4, +1.2] * | +0.0 [+0.0, +0.0] | +5.17 [+3.82, +6.52] * | +1.10 [−0.99, +3.19] | +1.46 [−0.01, +2.94] |
| t40, ds 0 | φ 0.6 | 0 [0, 0] | +1.4 [−0.1, +3.0] | +0.8 [+0.4, +1.2] * | +0.0 [+0.0, +0.0] | +14.78 [+12.56, +17.00] * | +1.11 [−0.36, +2.58] | +1.46 [+0.50, +2.42] * |
| t40, ds 0 | φ 0.4 | 0 [0, 0] | +1.7 [−0.1, +3.5] | +0.7 [+0.4, +1.1] * | +0.0 [+0.0, +0.0] | +25.85 [+23.51, +28.19] * | +1.15 [−0.16, +2.45] | +1.40 [+0.79, +2.02] * |
| t40, ds 1 | off | 929 [855, 1002] | – | – | – | – | – | – |
| t40, ds 1 | φ 1 | 941 [845, 1037] | −8.6 [−9.7, −7.6] * | −0.9 [−1.5, −0.2] * | +0.0 [+0.0, +0.0] | +3.64 [+1.22, +6.07] * | +2.75 [+2.27, +3.24] * | +2.01 [+1.75, +2.27] * |
| t40, ds 1 | φ 0.8 | 945 [849, 1042] | +0.0 [−0.9, +0.9] | −1.0 [−1.5, −0.6] * | +0.0 [+0.0, +0.0] | +6.44 [+4.86, +8.02] * | +3.30 [+1.93, +4.66] * | +2.38 [+1.74, +3.02] * |
| t40, ds 1 | φ 0.6 | 941 [832, 1050] | +0.6 [−0.5, +1.7] | −1.0 [−1.5, −0.4] * | +0.0 [+0.0, +0.0] | +12.90 [+11.96, +13.83] * | +3.36 [+2.15, +4.58] * | +2.28 [+1.38, +3.18] * |
| t40, ds 1 | φ 0.4 | 943 [840, 1046] | +1.2 [−0.4, +2.7] | −1.0 [−1.5, −0.4] * | +0.0 [+0.0, +0.0] | +19.79 [+18.48, +21.11] * | +3.60 [+2.30, +4.90] * | +2.42 [+1.57, +3.27] * |
| t100, ds 0 | off | 0 [0, 0] | – | – | – | – | – | – |
| t100, ds 0 | φ 1 | 0 [0, 0] | −14.8 [−16.7, −13.0] * | – | – | +4.44 [+1.94, +6.93] * | – | – |
| t100, ds 0 | φ 0.8 | 0 [0, 0] | +0.0 [−0.2, +0.2] | – | – | +7.50 [+6.69, +8.31] * | – | – |
| t100, ds 0 | φ 0.6 | 0 [0, 0] | +1.7 [+0.0, +3.3] * | – | – | +16.76 [+14.39, +19.12] * | – | – |
| t100, ds 0 | φ 0.4 | 0 [0, 0] | +1.8 [+0.1, +3.5] * | – | – | +27.14 [+24.39, +29.88] * | – | – |
| t100, ds 1 | off | 1445 [1311, 1579] | – | – | – | – | – | – |
| t100, ds 1 | φ 1 | 1438 [1289, 1587] | −6.3 [−8.7, −3.8] * | – | – | +5.22 [+3.73, +6.70] * | – | – |
| t100, ds 1 | φ 0.8 | 1446 [1304, 1588] | −0.3 [−1.1, +0.5] | – | – | +7.50 [+6.03, +8.97] * | – | – |
| t100, ds 1 | φ 0.6 | 1442 [1294, 1591] | +0.4 [−0.1, +0.9] | – | – | +11.71 [+9.43, +13.99] * | – | – |
| t100, ds 1 | φ 0.4 | 1443 [1309, 1576] | +0.6 [+0.1, +1.1] * | – | – | +16.41 [+13.26, +19.56] * | – | – |

## Stuck, parked and idle buyers

| Condition | Chains | Buyer-days | Stuck | Parked | Idle choosers | Invalid actions |
|---|---|---|---|---|---|---|
| off · t40 · ds0.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| off · t40 · ds1.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| off · t100 · ds0.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| off · t100 · ds1.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| phi1.0 · t40 · ds0.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| phi1.0 · t40 · ds1.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| phi1.0 · t100 · ds0.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| phi1.0 · t100 · ds1.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| phi0.8 · t40 · ds0.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| phi0.8 · t40 · ds1.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| phi0.8 · t100 · ds0.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| phi0.8 · t100 · ds1.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| phi0.6 · t40 · ds0.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| phi0.6 · t40 · ds1.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| phi0.6 · t100 · ds0.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| phi0.6 · t100 · ds1.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| phi0.4 · t40 · ds0.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| phi0.4 · t40 · ds1.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| phi0.4 · t100 · ds0.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| phi0.4 · t100 · ds1.0 | 3 | 13,500 | 0 | 0 | 0 | 0 |

## Flags

- none

## Reading (written after the results)

READING_PLACEHOLDER

## Caveats

CAVEATS_PLACEHOLDER
