# Brand Equity speed: reputation with slow new brands, 60 days

Spec: the task "engine 0.19.0 (two keys), calibration, pilot, sizing" (2026-11-17); predictions fixed 2026-11-17, before any run. Background: `runs/brand_equity_tier_summary.md`. Calibration: `runs/calibration_brand_equity_speed.md`. Pilot gate: `runs/pilot_brand_equity_speed.md`.

## Design (prespecified)

- Question: what does the owner's reputation earn over a market long enough for new brands to catch up, when only new brands' ratings form slowly?
- Engine 0.19.0. Market as the 0.18.0 run: the licensing market, detect_scale 1, owner not liable, `licensing.white_label_tier` genuine, royalty 0.10, N 6 from day 10, 3 owners per seed from `default_rng([seed, 17])`; but `market.days` 60 (D 60, known to sellers) and `ratings.prior_scope` new: the prior reaches only brands created on day 2 or later (white labels, reopening names); the owner and every original stall rate as with prior_n 0.
- Arms: never, R (licensees under the owner's brand), W_g (white labels at the genuine tier). Quality: contract only.
- Speeds (`ratings.prior_n`, from the calibration; days for a W_g white label to reach 0.9 at t40): current: prior_n 0, 1.04 days; d5: prior_n 3.5, 6.36 days; d10: prior_n 10, 10.38 days; d20: prior_n 400, 20.76 days.
- Verification: t40 (locals inspect) and t100. Seeds 330-349, fresh, paired across all cells.
- Measures per owner: J = owner + 6 licensees' profit, days 10–60. Reputation effect E = J(R) − J(W_g), with the five-part split. E by window: catch-up = days 10 through the day the owner's white labels first reach a mean rating of 0.9 (end of day, unrated = 0.5), after = the rest. Days to 0.9 per owner from W_g. Owner's gain at 0.05–0.25 by the exact recompute, after the no-decision replay check. Licensee profit under R and W_g at each royalty. Never chains across speeds.
- Predictions (verbatim from the spec):
  - PS1 (confirmatory): t40: E rises with time to reputation. Least-squares slope of E over the calibrated days to 0.9 (four levels), fitted per seed, > 0.
  - PS2 (confirmatory): t40, slowest level: more than half of E is earned during the catch-up window (before the white labels reach 0.9).
  - PS3 (confirmatory): t40, current speed (prior_n 0): E over days 10–60 is less than 10% of E at the slowest level.
  - PS4 (exploratory): shape. Compare a linear and a saturating fit of E against days to 0.9 at t40; report both, no prediction.
  - PS5 (exploratory): t100: E at each speed; no direction predicted.
  - PS6 (exploratory): the slowest speed at which licensees earn more under R than under W_g at royalty 0.10, at t40.
- Analysis: per seed the mean over 3 owners; mean and 95% t over seeds; unadjusted. PS1's slope is fitted per seed over the calibration's days to 0.9. PS2 is tested as E(catch-up) − E(after) > 0, which is the same as more than half of E in catch-up; PS3 as 0.1 × E(slowest) − E(current) > 0, per seed.

## Run record

- Engine `0.19.0`; commit `2744a4a5d8972eb7e3e4443e6443f21b65525fa3`; uncommitted at run time: ['?? runs/brand_equity_speed_run.log', '?? runs/brand_equity_speed_stdout.log', '?? runs/queue_brand_equity_speed.log']
- Script sha256 `64347583a606fc05bf7047966a1a6c89fbf779fbc0806c129f9fca01a8535df9`
- Command: `python -m analysis.brand_equity_speed --seeds 330-349 --workers 4 --tests Full suite at engine 0.19.0 (8b7884b): 1424 passed, 17 skipped (runs/tests_0190.log) --gate Pilot gate G1–G5 passed (runs/pilot_brand_equity_speed.md); levels from runs/calibration_brand_equity_speed.md`
- Tests: Full suite at engine 0.19.0 (8b7884b): 1424 passed, 17 skipped (runs/tests_0190.log)
- Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit
- 1132 chains × 60 days on 4 workers (nice 19); wall clock 4.33 h; load average [2.07, 2.14, 2.12] at start, [5.04, 5.99, 6.13] at end; memory at start {'swap_free_mb': 1320.31, 'free_pct': 66}, at end {'swap_free_mb': 1320.31, 'free_pct': 65}; memory-guard pauses: 0
- Seeds 330-349 (20), paired
- Sampled owners per seed: 330: s25, s47, s26; 331: s12, s07, s32; 332: s46, s34, s25; 333: s14, s22, s20; 334: s18, s46, s04; 335: s27, s14, s42; 336: s46, s01, s30; 337: s31, s15, s36; 338: s37, s12, s34; 339: s04, s23, s16; 340: s01, s38, s31; 341: s38, s22, s20; 342: s24, s13, s19; 343: s34, s21, s23; 344: s38, s08, s23; 345: s44, s23, s17; 346: s23, s06, s32; 347: s06, s14, s12; 348: s09, s32, s40; 349: s09, s25, s29

## Gate

Pilot gate G1–G5 passed (runs/pilot_brand_equity_speed.md); levels from runs/calibration_brand_equity_speed.md

Genuine-tier prices: every W_g white label's posted price equals base × (1 + 0.4 × (start-of-day rating − 0.5)) on every day from 10: 0 misses in 480 chains.

### The royalty enters no decision

Code: as Brand Equity; 0.19.0 adds no reader of `licensing.royalty`, and the prior enters ratings only. Replay at seed 330, t100, R at royalty 0.05 and 0.25 against 0.10:

| Speed | Owner | Royalty | Days identical | Same licensees | Royalties differ | Recompute exact | Pass |
|---|---|---|---|---|---|---|---|
| current | s25 | 0.05 | 60/60 | yes | yes | yes | yes |
| current | s25 | 0.25 | 60/60 | yes | yes | yes | yes |
| current | s47 | 0.05 | 60/60 | yes | yes | yes | yes |
| current | s47 | 0.25 | 60/60 | yes | yes | yes | yes |
| current | s26 | 0.05 | 60/60 | yes | yes | yes | yes |
| current | s26 | 0.25 | 60/60 | yes | yes | yes | yes |
| d20 | s25 | 0.05 | 60/60 | yes | yes | yes | yes |
| d20 | s25 | 0.25 | 60/60 | yes | yes | yes | yes |
| d20 | s47 | 0.05 | 60/60 | yes | yes | yes | yes |
| d20 | s47 | 0.25 | 60/60 | yes | yes | yes | yes |
| d20 | s26 | 0.05 | 60/60 | yes | yes | yes | yes |
| d20 | s26 | 0.25 | 60/60 | yes | yes | yes | yes |

Result: **pass**.

J identity: 1440/1440 owner-chains to the cent; largest split residual 0.000000 cents; catch-up + after = E to 0 cents.

## Predictions

$ per owner over days 10–60 (per-seed mean of 3 owners). PS1–PS3 confirmatory; PS4–PS6 exploratory.

| Prediction | Estimate ($) | Verdict |
|---|---|---|
| **PS1**: t40: slope of E over days to 0.9 ($ per day) | +276.95 [+124.37, +429.54] * | supported |
| **PS2**: t40, d20: E in the catch-up window − E after it (> 0 ⇔ more than half of E in catch-up) | +359.07 [−265.74, +983.87] | not supported (interval includes 0) |
| **PS3**: t40: 10% of E at d20 − E at the current speed (> 0 ⇔ E current < 10% of E slowest) | +450.70 [+156.45, +744.94] * | supported |

PS2 share: E in catch-up / E at d20, t40 = −0.05 [−1.11, 1.01] (per-seed ratios; ratio of means 0.53).
PS3 ratio: E current / E d20 at t40 = 0.036 (ratio of means).

**PS4** (exploratory): fits of E on days to 0.9 at t40, over the per-seed points (n = 80):

| Fit | Parameters | RSS ($²) | R² | AIC |
|---|---|---|---|---|
| Linear: a + b x | a = +2,581.45, b = +276.95 per day | 3,491,210,505 | 0.084 | 2148.1 |
| Saturating: a + A (1 − exp(−(x − x₀)/τ)) | a = +249.82, A = +6,666.15, τ = 0.25 days, x₀ = 1.04 (τ at the grid edge) | 3,144,914,172 | 0.175 | 2141.8 |

**PS5** (exploratory): E at t100 by speed:

| Speed | Days to 0.9 (calibration, t40) | E at t100 ($) |
|---|---|---|
| current | 1.04 | +101.08 [−4.59, +206.75] |
| d5 | 6.36 | −9,961.77 [−13,004.44, −6,919.11] * |
| d10 | 10.38 | −10,139.40 [−13,393.10, −6,885.70] * |
| d20 | 20.76 | −8,904.76 [−12,700.55, −5,108.97] * |

**PS6** (exploratory): licensee profit under R at 0.10 − under W_g, per licensee, days 10–60, t40:

| Speed | R at 0.10 − W_g ($) |
|---|---|
| current | −1,650.75 [−1,999.79, −1,301.71] * |
| d5 | −390.42 [−782.98, +2.15] |
| d10 | −462.88 [−872.61, −53.14] * |
| d20 | −509.93 [−964.53, −55.34] * |

Slowest speed with the interval above 0: none; slowest with the mean above 0: none; fastest with the interval above 0: none.

## Joint profit and its parts

J per owner and its 6 licensees, days 10–60, $.

| Cell | J never | J W_g | J R | Composition W_g − never | E = R − W_g | E catch-up | E after |
|---|---|---|---|---|---|---|---|
| current, t40 | −8,580.14 [−11,007.34, −6,152.93] * | +40,303.18 [+31,579.59, +49,026.77] * | +40,553.00 [+31,744.18, +49,361.83] * | +48,883.32 [+38,746.74, +59,019.90] * | +249.82 [+137.80, +361.85] * | +246.28 [+137.39, +355.18] * | +3.54 [−6.05, +13.14] |
| d5, t40 | −8,268.82 [−10,657.32, −5,880.33] * | +33,547.15 [+26,930.25, +40,164.05] * | +40,552.89 [+31,744.05, +49,361.73] * | +41,815.97 [+33,687.20, +49,944.75] * | +7,005.74 [+3,671.51, +10,339.97] * | +608.82 [−10.57, +1,228.21] | +6,396.92 [+3,659.05, +9,134.79] * |
| d10, t40 | −8,151.76 [−10,528.33, −5,775.19] * | +33,815.90 [+27,189.08, +40,442.73] * | +40,552.89 [+31,744.05, +49,361.73] * | +41,967.67 [+33,848.68, +50,086.66] * | +6,736.98 [+3,337.04, +10,136.93] * | +994.69 [+134.89, +1,854.49] * | +5,742.29 [+3,188.29, +8,296.29] * |
| d20, t40 | −8,024.10 [−10,386.89, −5,661.30] * | +33,547.69 [+27,035.00, +40,060.38] * | +40,552.89 [+31,744.05, +49,361.74] * | +41,571.78 [+33,589.07, +49,554.50] * | +7,005.20 [+3,323.59, +10,686.82] * | +3,682.13 [+1,903.05, +5,461.22] * | +3,323.07 [+1,371.87, +5,274.27] * |
| current, t100 | −15,788.22 [−19,529.52, −12,046.93] * | +41,208.35 [+32,210.14, +50,206.56] * | +41,309.43 [+32,243.49, +50,375.37] * | +56,996.57 [+45,050.44, +68,942.71] * | +101.08 [−4.59, +206.75] | +101.90 [−4.09, +207.89] | −0.82 [−3.60, +1.96] |
| d5, t100 | −15,704.18 [−19,424.89, −11,983.46] * | +51,271.70 [+41,242.99, +61,300.40] * | +41,309.92 [+32,243.57, +50,376.28] * | +66,975.88 [+53,842.66, +80,109.10] * | −9,961.77 [−13,004.44, −6,919.11] * | −1,000.55 [−1,458.28, −542.83] * | −8,961.22 [−11,607.04, −6,315.39] * |
| d10, t100 | −15,658.51 [−19,372.50, −11,944.51] * | +51,449.32 [+41,465.83, +61,432.81] * | +41,309.92 [+32,243.57, +50,376.28] * | +67,107.83 [+54,019.31, +80,196.34] * | −10,139.40 [−13,393.10, −6,885.70] * | −1,327.27 [−2,105.06, −549.48] * | −8,812.13 [−11,367.42, −6,256.83] * |
| d20, t100 | −15,575.24 [−19,250.61, −11,899.87] * | +50,214.68 [+40,608.00, +59,821.36] * | +41,309.92 [+32,243.57, +50,376.27] * | +65,789.92 [+53,096.05, +78,483.79] * | −8,904.76 [−12,700.55, −5,108.97] * | −255.44 [−1,842.67, +1,331.78] | −8,649.32 [−11,128.81, −6,169.82] * |

E split (R − W_g, $; the parts add up to E):

| Cell | Owner own sales | Licensee sales | Licensee prices | Licensee ad spend | Fines |
|---|---|---|---|---|---|
| current, t40 | +21.51 [+1.82, +41.20] * | −180.81 [−283.17, −78.45] * | +409.28 [+325.21, +493.35] * | −0.15 [−0.36, +0.07] | +0.00 [+0.00, +0.00] |
| d5, t40 | −784.57 [−1,479.63, −89.51] * | +6,260.10 [+2,906.94, +9,613.25] * | +1,529.70 [+1,217.99, +1,841.40] * | +0.52 [−0.71, +1.75] | +0.00 [+0.00, +0.00] |
| d10, t40 | −618.54 [−1,342.71, +105.63] | +4,959.68 [+1,661.07, +8,258.29] * | +2,395.62 [+1,906.56, +2,884.68] * | +0.22 [−0.83, +1.28] | +0.00 [+0.00, +0.00] |
| d20, t40 | −68.00 [−904.28, +768.27] | +976.63 [−2,129.88, +4,083.13] | +6,095.77 [+4,830.17, +7,361.37] * | +0.81 [−0.16, +1.78] | +0.00 [+0.00, +0.00] |
| current, t100 | +95.14 [+53.36, +136.92] * | −568.62 [−723.58, −413.65] * | +574.58 [+453.12, +696.04] * | −0.03 [−0.30, +0.24] | +0.00 [+0.00, +0.00] |
| d5, t100 | +2,710.23 [+1,806.60, +3,613.85] * | −13,849.79 [−17,469.90, −10,229.68] * | +1,177.84 [+937.04, +1,418.64] * | −0.05 [−1.29, +1.19] | +0.00 [+0.00, +0.00] |
| d10, t100 | +3,007.63 [+2,008.57, +4,006.70] * | −14,997.71 [−18,889.32, −11,106.10] * | +1,850.95 [+1,469.02, +2,232.87] * | −0.27 [−1.74, +1.21] | +0.00 [+0.00, +0.00] |
| d20, t100 | +3,990.47 [+2,664.61, +5,316.32] * | −18,006.39 [−22,646.97, −13,365.81] * | +5,111.30 [+4,024.21, +6,198.39] * | −0.14 [−1.82, +1.55] | +0.00 [+0.00, +0.00] |

Units and prices, days 10–60:

| Cell | Licensee units never / W_g / R | Licensee mean price W_g / R ($) | Owner units never / W_g / R |
|---|---|---|---|
| current, t40 | 590.1 / 1521.8 / 1513.9 | 65.00 / 65.28 | 355.1 / 251.3 / 252.0 |
| d5, t40 | 590.1 / 1281.2 / 1513.9 | 64.20 / 65.28 | 355.1 / 298.2 / 252.0 |
| d10, t40 | 590.1 / 1331.7 / 1513.9 | 63.61 / 65.28 | 355.1 / 292.7 / 252.0 |
| d20, t40 | 590.0 / 1495.6 / 1513.9 | 61.23 / 65.28 | 355.0 / 273.4 / 252.0 |
| current, t100 | 814.3 / 1558.1 / 1535.3 | 64.88 / 65.28 | 323.7 / 252.6 / 256.0 |
| d5, t100 | 814.1 / 2066.3 / 1535.4 | 64.42 / 65.28 | 323.7 / 170.7 / 255.9 |
| d10, t100 | 814.1 / 2129.9 / 1535.4 | 63.94 / 65.28 | 323.7 / 160.7 / 255.9 |
| d20, t100 | 814.1 / 2339.8 / 1535.4 | 61.78 / 65.28 | 323.8 / 127.8 / 255.9 |

## Owner's gain and licensee profit by royalty

Owner's gain = owner's 60-day profit − never at the same speed. R by the exact recompute; white labels pay no royalty. Licensee profit: per licensee, days 10–60.

| Cell | Owner gain R, 0.05 | Owner gain R, 0.10 | Owner gain R, 0.15 | Owner gain R, 0.25 | Owner gain W_g |
|---|---|---|---|---|---|
| current, t40 | +2,754.49 [+1,867.26, +3,641.72] * | +7,820.90 [+5,989.16, +9,652.64] * | +12,887.31 [+10,010.14, +15,764.47] * | +23,020.12 [+18,001.39, +28,038.86] * | −2,333.42 [−3,083.87, −1,582.98] * |
| d5, t40 | +2,754.47 [+1,867.22, +3,641.72] * | +7,820.87 [+5,989.11, +9,652.63] * | +12,887.27 [+10,010.09, +15,764.45] * | +23,020.07 [+18,001.32, +28,038.83] * | −1,527.36 [−1,870.46, −1,184.26] * |
| d10, t40 | +2,754.47 [+1,867.22, +3,641.72] * | +7,820.87 [+5,989.11, +9,652.63] * | +12,887.27 [+10,010.09, +15,764.45] * | +23,020.07 [+18,001.32, +28,038.83] * | −1,693.39 [−2,077.19, −1,309.58] * |
| d20, t40 | +2,754.58 [+1,867.40, +3,641.75] * | +7,820.98 [+5,989.32, +9,652.64] * | +12,887.38 [+10,010.30, +15,764.46] * | +23,020.18 [+18,001.52, +28,038.83] * | −2,243.82 [−2,740.44, −1,747.19] * |
| current, t100 | +3,862.35 [+2,771.05, +4,953.66] * | +9,002.75 [+6,959.94, +11,045.57] * | +14,143.15 [+11,039.25, +17,247.05] * | +24,423.95 [+19,133.08, +29,714.83] * | −1,373.19 [−2,187.82, −558.55] * |
| d5, t100 | +3,860.82 [+2,769.32, +4,952.32] * | +9,001.32 [+6,958.23, +11,044.42] * | +14,141.83 [+11,037.58, +17,246.08] * | +24,422.84 [+19,131.48, +29,714.19] * | −3,989.91 [−4,747.69, −3,232.14] * |
| d10, t100 | +3,860.82 [+2,769.32, +4,952.32] * | +9,001.32 [+6,958.23, +11,044.42] * | +14,141.83 [+11,037.58, +17,246.08] * | +24,422.84 [+19,131.48, +29,714.19] * | −4,287.32 [−5,104.13, −3,470.50] * |
| d20, t100 | +3,858.75 [+2,769.63, +4,947.87] * | +8,999.25 [+6,958.99, +11,039.52] * | +14,139.76 [+11,038.40, +17,241.12] * | +24,420.77 [+19,132.31, +29,709.22] * | −5,272.22 [−6,317.04, −4,227.40] * |

| Cell | Licensee profit never | W_g | R, 0.05 | R, 0.10 | R, 0.15 | R, 0.25 |
|---|---|---|---|---|---|---|
| current, t40 | −2,851.90 [−3,409.96, −2,293.85] * | +5,684.22 [+4,408.09, +6,960.35] * | +4,877.87 [+3,767.51, +5,988.23] * | +4,033.47 [+3,101.45, +4,965.49] * | +3,189.07 [+2,434.20, +3,943.94] * | +1,500.27 [+1,089.91, +1,910.62] * |
| d5, t40 | −2,800.02 [−3,346.74, −2,253.30] * | +4,423.87 [+3,546.58, +5,301.16] * | +4,877.86 [+3,767.50, +5,988.22] * | +4,033.46 [+3,101.44, +4,965.47] * | +3,189.06 [+2,434.19, +3,943.92] * | +1,500.26 [+1,089.90, +1,910.61] * |
| d10, t40 | −2,780.51 [−3,323.38, −2,237.63] * | +4,496.34 [+3,611.44, +5,381.23] * | +4,877.86 [+3,767.50, +5,988.22] * | +4,033.46 [+3,101.44, +4,965.47] * | +3,189.06 [+2,434.19, +3,943.92] * | +1,500.26 [+1,089.90, +1,910.61] * |
| d20, t40 | −2,759.21 [−3,297.80, −2,220.62] * | +4,543.39 [+3,661.09, +5,425.69] * | +4,877.86 [+3,767.50, +5,988.22] * | +4,033.46 [+3,101.44, +4,965.48] * | +3,189.06 [+2,434.19, +3,943.93] * | +1,500.26 [+1,089.91, +1,910.61] * |
| current, t100 | −3,909.99 [−4,716.41, −3,103.57] * | +5,818.30 [+4,497.46, +7,139.15] * | +4,962.56 [+3,816.94, +6,108.18] * | +4,105.83 [+3,143.23, +5,068.43] * | +3,249.09 [+2,468.32, +4,029.87] * | +1,535.63 [+1,108.77, +1,962.48] * |
| d5, t100 | −3,896.19 [−4,698.52, −3,093.87] * | +7,931.44 [+6,384.45, +9,478.43] * | +4,962.69 [+3,817.00, +6,108.37] * | +4,105.93 [+3,143.28, +5,068.59] * | +3,249.18 [+2,468.37, +4,030.00] * | +1,535.68 [+1,108.80, +1,962.56] * |
| d10, t100 | −3,888.58 [−4,689.52, −3,087.65] * | +8,010.61 [+6,461.11, +9,560.11] * | +4,962.69 [+3,817.00, +6,108.37] * | +4,105.93 [+3,143.28, +5,068.59] * | +3,249.18 [+2,468.37, +4,030.00] * | +1,535.68 [+1,108.80, +1,962.56] * |
| d20, t100 | −3,875.05 [−4,669.56, −3,080.54] * | +7,968.64 [+6,449.44, +9,487.84] * | +4,962.68 [+3,817.00, +6,108.37] * | +4,105.93 [+3,143.28, +5,068.59] * | +3,249.18 [+2,468.36, +4,030.00] * | +1,535.68 [+1,108.80, +1,962.56] * |

## Rating speed

Per owner: days from day 10 (= 1) until its W_g white labels' mean rating first reaches 0.9 (the end of the catch-up window) and the share of owners whose labels reach it by day 60; per label: mean days to 0.9 over the labels that reach it and the share that do; the owner's own rating at the end of day 10 (never).

| Cell | Owner: days to 0.9 | Owners reaching | Label: days to 0.9 | Labels reaching | Owner rating day 10 |
|---|---|---|---|---|---|
| current, t40 | 1.0 [1.0, 1.0] | 1.00 [1.00, 1.00] | 1.0 [1.0, 1.1] | 1.00 [1.00, 1.00] | 1.000 [1.000, 1.000] |
| d5, t40 | 7.0 [6.9, 7.1] | 1.00 [1.00, 1.00] | 6.6 [6.4, 6.7] | 1.00 [1.00, 1.00] | 1.000 [1.000, 1.000] |
| d10, t40 | 10.3 [10.1, 10.4] | 1.00 [1.00, 1.00] | 10.3 [10.2, 10.4] | 1.00 [1.00, 1.00] | 1.000 [1.000, 1.000] |
| d20, t40 | 20.9 [20.8, 21.0] | 1.00 [1.00, 1.00] | 20.8 [20.7, 20.9] | 1.00 [1.00, 1.00] | 1.000 [1.000, 1.000] |
| current, t100 | 1.0 [1.0, 1.0] | 1.00 [1.00, 1.00] | 1.0 [1.0, 1.0] | 1.00 [1.00, 1.00] | 1.000 [1.000, 1.000] |
| d5, t100 | 5.6 [5.4, 5.8] | 1.00 [1.00, 1.00] | 4.7 [4.5, 5.0] | 1.00 [1.00, 1.00] | 1.000 [1.000, 1.000] |
| d10, t100 | 9.1 [9.0, 9.2] | 1.00 [1.00, 1.00] | 9.2 [9.1, 9.3] | 1.00 [1.00, 1.00] | 1.000 [1.000, 1.000] |
| d20, t100 | 19.9 [19.8, 20.0] | 1.00 [1.00, 1.00] | 19.8 [19.7, 19.9] | 1.00 [1.00, 1.00] | 1.000 [1.000, 1.000] |

Rating paths: mean over owners (unrated = 0.5), end of days 1, 9, 10, 12, 15, 20, 30, 40, 50, 60.

| Cell | Series | 1 | 9 | 10 | 12 | 15 | 20 | 30 | 40 | 50 | 60 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| current, t40 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, t40 | owner brand, R | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, t40 | owner brand, W_g | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, t40 | white labels, W_g | 0.501 | 0.567 | 0.982 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d5, t40 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d5, t40 | owner brand, R | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d5, t40 | owner brand, W_g | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d5, t40 | white labels, W_g | 0.501 | 0.656 | 0.788 | 0.825 | 0.890 | 0.961 | 0.997 | 1.000 | 1.000 | 1.000 |
| d10, t40 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d10, t40 | owner brand, R | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d10, t40 | owner brand, W_g | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d10, t40 | white labels, W_g | 0.501 | 0.690 | 0.675 | 0.709 | 0.798 | 0.920 | 0.994 | 1.000 | 1.000 | 1.000 |
| d20, t40 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d20, t40 | owner brand, R | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d20, t40 | owner brand, W_g | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d20, t40 | white labels, W_g | 0.501 | 0.726 | 0.508 | 0.510 | 0.525 | 0.605 | 0.912 | 0.993 | 1.000 | 1.000 |
| current, t100 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, t100 | owner brand, R | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, t100 | owner brand, W_g | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, t100 | white labels, W_g | 0.543 | 0.599 | 0.996 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d5, t100 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d5, t100 | owner brand, R | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d5, t100 | owner brand, W_g | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d5, t100 | white labels, W_g | 0.543 | 0.668 | 0.834 | 0.861 | 0.915 | 0.973 | 0.998 | 1.000 | 1.000 | 1.000 |
| d10, t100 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d10, t100 | owner brand, R | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d10, t100 | owner brand, W_g | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d10, t100 | white labels, W_g | 0.543 | 0.698 | 0.719 | 0.750 | 0.832 | 0.940 | 0.996 | 1.000 | 1.000 | 1.000 |
| d20, t100 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d20, t100 | owner brand, R | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d20, t100 | owner brand, W_g | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| d20, t100 | white labels, W_g | 0.543 | 0.737 | 0.511 | 0.514 | 0.534 | 0.632 | 0.932 | 0.996 | 1.000 | 1.000 |

## Never chains across speeds

The prior reaches every new brand, reopened deceptive names included. Whole-market 60-day profit by stall type ($, all stalls of the type), catches, the sampled owners' mean 60-day profit, the mean day-20 rating of deceptive stalls' reopened names, and the mean rating of rated brands by type (days 10, 30, 60).

| Never chain | Genuine profit | Seconds profit | Deceptive profit | Catches | Owner profit | Reopened d20 | Genuine d10/30/60 | Seconds d10/30/60 | Deceptive d10/30/60 |
|---|---|---|---|---|---|---|---|---|---|
| current, t40 | 188,269.00 [186,037.68, 190,500.33] | −5,251.64 [−6,381.65, −4,121.63] | −96,993.71 [−103,708.83, −90,278.59] | 1876 [1825, 1927] | 9,966.96 [7,788.87, 12,145.04] | 0.000 [0.000, 0.000] | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | 0.000 / 0.000 / 0.000 |
| d5, t40 | 188,269.02 [186,037.73, 190,500.31] | −5,251.60 [−6,381.66, −4,121.54] | −95,359.93 [−102,224.25, −88,495.61] | 1876 [1825, 1927] | 9,966.96 [7,788.89, 12,145.03] | 0.282 [0.270, 0.295] | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | 0.290 / 0.272 / 0.276 |
| d10, t40 | 188,269.02 [186,037.73, 190,500.31] | −5,251.60 [−6,381.66, −4,121.54] | −94,738.00 [−101,663.89, −87,812.11] | 1876 [1825, 1927] | 9,966.96 [7,788.89, 12,145.03] | 0.386 [0.377, 0.395] | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | 0.392 / 0.380 / 0.381 |
| d20, t40 | 188,268.80 [186,037.62, 190,499.98] | −5,251.56 [−6,381.63, −4,121.49] | −94,064.22 [−101,061.49, −87,066.94] | 1876 [1825, 1927] | 9,966.85 [7,788.67, 12,145.03] | 0.496 [0.495, 0.496] | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | 0.496 / 0.496 / 0.496 |
| current, t100 | 169,962.32 [167,144.60, 172,780.04] | −5,257.08 [−6,372.56, −4,141.60] | −134,138.82 [−138,111.07, −130,166.56] | 2868 [2851, 2885] | 8,964.33 [6,921.34, 11,007.31] | 0.000 [0.000, 0.000] | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | 0.000 / 0.000 / 0.000 |
| d5, t100 | 169,986.40 [167,155.24, 172,817.56] | −5,256.94 [−6,372.42, −4,141.46] | −133,590.88 [−137,627.91, −129,553.86] | 2868 [2851, 2885] | 8,965.61 [6,922.92, 11,008.30] | 0.242 [0.227, 0.258] | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | 0.229 / 0.260 / 0.235 |
| d10, t100 | 169,986.40 [167,155.24, 172,817.56] | −5,256.94 [−6,372.42, −4,141.46] | −133,305.45 [−137,369.87, −129,241.03] | 2868 [2851, 2885] | 8,965.61 [6,922.92, 11,008.30] | 0.353 [0.339, 0.366] | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | 0.342 / 0.366 / 0.347 |
| d20, t100 | 169,992.77 [167,156.26, 172,829.27] | −5,256.95 [−6,372.42, −4,141.47] | −132,958.90 [−137,085.26, −128,832.55] | 2868 [2851, 2885] | 8,967.68 [6,923.20, 11,012.15] | 0.494 [0.493, 0.495] | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | 0.493 / 0.495 / 0.494 |

| Difference | Genuine profit | Seconds profit | Deceptive profit | Catches | Owner profit |
|---|---|---|---|---|---|
| d5 − current, t40 | +0.02 [−0.35, +0.39] | +0.04 [−0.36, +0.44] | +1,633.78 [+1,412.16, +1,855.40] * | +0 [+0, +0] | +0.01 [−0.05, +0.06] |
| d10 − current, t40 | +0.02 [−0.35, +0.39] | +0.04 [−0.36, +0.44] | +2,255.71 [+1,955.69, +2,555.73] * | +0 [+0, +0] | +0.01 [−0.05, +0.06] |
| d20 − current, t40 | −0.20 [−1.02, +0.61] | +0.08 [−0.32, +0.48] | +2,929.49 [+2,540.98, +3,318.00] * | +0 [+0, +0] | −0.10 [−0.35, +0.15] |
| d5 − current, t100 | +24.08 [−13.59, +61.75] | +0.14 [−0.03, +0.32] | +547.93 [+369.42, +726.44] * | +0 [−0, +0] | +1.28 [−0.60, +3.16] |
| d10 − current, t100 | +24.08 [−13.59, +61.75] | +0.14 [−0.03, +0.32] | +833.37 [+603.91, +1,062.82] * | +0 [−0, +0] | +1.28 [−0.60, +3.16] |
| d20 − current, t100 | +30.45 [−8.61, +69.50] | +0.14 [−0.03, +0.30] | +1,179.91 [+866.19, +1,493.64] * | +0 [−0, +1] | +3.35 [−1.22, +7.92] |

## Stuck, parked and idle buyers

| Chains | Count | Buyer-days | Stuck | Parked | Idle choosers | Invalid actions |
|---|---|---|---|---|---|---|
| R · t100 · p0 · 60d · new | 60 | 540,000 | 0 | 0 | 0 | 0 |
| R · t100 · p10 · 60d · new | 60 | 540,000 | 0 | 0 | 0 | 0 |
| R · t100 · p3.5 · 60d · new | 60 | 540,000 | 0 | 0 | 0 | 0 |
| R · t100 · p400 · 60d · new | 60 | 540,000 | 0 | 0 | 0 | 0 |
| R · t40 · p0 · 60d · new | 60 | 540,000 | 0 | 0 | 0 | 0 |
| R · t40 · p10 · 60d · new | 60 | 540,000 | 0 | 0 | 0 | 0 |
| R · t40 · p3.5 · 60d · new | 60 | 540,000 | 0 | 0 | 0 | 0 |
| R · t40 · p400 · 60d · new | 60 | 540,000 | 0 | 0 | 0 | 0 |
| Wg · t100 · p0 · 60d · new | 60 | 540,000 | 0 | 0 | 0 | 0 |
| Wg · t100 · p10 · 60d · new | 60 | 540,000 | 0 | 0 | 0 | 0 |
| Wg · t100 · p3.5 · 60d · new | 60 | 540,000 | 0 | 0 | 0 | 0 |
| Wg · t100 · p400 · 60d · new | 60 | 540,000 | 0 | 0 | 0 | 0 |
| Wg · t40 · p0 · 60d · new | 60 | 540,000 | 0 | 0 | 0 | 0 |
| Wg · t40 · p10 · 60d · new | 60 | 540,000 | 0 | 0 | 0 | 0 |
| Wg · t40 · p3.5 · 60d · new | 60 | 540,000 | 0 | 0 | 0 | 0 |
| Wg · t40 · p400 · 60d · new | 60 | 540,000 | 0 | 0 | 0 | 0 |
| never · t100 · p0 · 60d · new | 20 | 180,000 | 0 | 0 | 0 | 0 |
| never · t100 · p10 · 60d · new | 20 | 180,000 | 0 | 0 | 0 | 0 |
| never · t100 · p3.5 · 60d · new | 20 | 180,000 | 0 | 0 | 0 | 0 |
| never · t100 · p400 · 60d · new | 20 | 180,000 | 0 | 0 | 0 | 0 |
| never · t40 · p0 · 60d · new | 20 | 180,000 | 0 | 0 | 0 | 0 |
| never · t40 · p10 · 60d · new | 20 | 180,000 | 0 | 0 | 0 | 0 |
| never · t40 · p3.5 · 60d · new | 20 | 180,000 | 0 | 0 | 0 | 0 |
| never · t40 · p400 · 60d · new | 20 | 180,000 | 0 | 0 | 0 | 0 |

## Flags

- none

## Reading (written after the results)

- **PS1 and PS3 are supported; PS2 is not. With buyers who read ratings (t40), the reputation effect jumps from +$250 when new brands rate at once to about +$7,000 once they take 6 days or more, and does not grow from 6 to 21 days. Most of that $7,000 is not earned while the white labels catch up. It comes from a white-label rating that ends at 0.999 instead of the owner's exact 1.0, which these buyers rank strictly. With no rating readers (t100), slow ratings help the white labels instead, by about $9,000–10,000 per owner.**
  - **PS1:** E at t40 is +$250 [+138, +362], +$7,006 [+3,672, +10,340], +$6,737 [+3,337, +10,137] and +$7,005 [+3,324, +10,687] at 1.0, 6.4, 10.4 and 20.8 days to 0.9. The slope is +$277 [+124, +430] per day. It is positive, but it comes from the step between the current speed and the rest; E does not rise across the three slow levels.
  - **PS3:** E at the current speed is 3.6% of E at d20 (ratio of means); the test is +$451 [+156, +745].
  - **PS2:** at d20, E in the catch-up window is +$3,682 [+1,903, +5,461] and after it +$3,323 [+1,372, +5,274]. The difference is +$359 [−266, +984], so "more than half" is not shown (ratio of means 0.53). At the faster slow levels even less is earned in the window: 9% of E at d5, 15% at d10 (ratios of means).
  - **PS4:** the saturating fit has the lower AIC (2141.8 against 2148.1), with τ at the grid's lower edge (0.25 days). That is a step between 1.0 and 6.4 days; with no level in between, its shape cannot be seen. Both fits explain little of the per-seed spread (R² 0.08 and 0.18).
  - **PS5:** E at t100 is +$101 [−5, +207] at the current speed and −$9,962, −$10,139 and −$8,905 at d5, d10 and d20 (intervals all below 0).
  - **PS6:** no speed. At royalty 0.10 and t40 each licensee earns less under R than as a white label at every speed: −$1,651 [−2,000, −1,302] at the current speed, −$390 [−783, +2] at d5, −$463 and −$510 at d10 and d20. At royalty 0.05 the point estimates favour R at the three slow speeds ($4,878 against $4,424–4,543); no interval was computed for that difference.
- **After the catch-up, the t40 effect comes from ratings of 0.999 losing to 1.0.** This mechanism was found after the results, from the run's cache (days 41–60, computed post hoc; exploratory).
  - Locals and experts take the stall with the highest visible rating, then the lowest price, comparing ratings exactly (`agents/rule_based.py`, `act_search`). Displayed ratings are not rounded.
  - Under the prior, a white label's rating approaches 1 without reaching it: at every slow level, every white label ends day 60 between 0.99909 and 0.99999995, never at 1.0. The owner's brand and the other day-1 genuine brands carry no prior and sit at exactly 1.0. So rating readers rank every white label below the R licensees and the owner for the whole run.
  - Days 41–60 at d5, t40: every white label is above 0.9987 at the end of day 40, and both arms post $65.28. W_g licensees still sell 199 [170, 229] fewer units than R licensees, and E over those 20 days is +$4,560 [+3,345, +5,775], about two thirds of d5's E. At d10 it is +$4,235 [+3,026, +5,445]; at d20, +$2,679 [+1,369, +3,989].
  - The flat E from d5 to d20 and PS2's result therefore reflect how buyers rank near the top of the scale more than how long the catch-up takes.
- **At t100 the same gap works through the price.** Tourists see no ratings and buy the cheapest candidate, and the posted price rises with the rating, so a white label rated just below 1.0 posts a cent or more below the owner's licensees and wins their price ties.
  - Over days 10–60, W_g licensees sell 2,066–2,340 units against R's 1,535, and the owner sells 128–171 against 256.
  - Late in the run this lasts only while the rating gap is large enough to move the rounded price. E over days 41–60 is −$4 [−14, +5] at d5 (both arms post $65.28), −$561 [−781, −341] at d10 and −$4,487 [−5,790, −3,185] at d20, where W_g sells 172 more units.
- **The speeds change only the white-label arm.** J(R) is the same at every speed to within $0.11 (t40) and $0.49 (t100), because under scope "new" the owner's brand gets no prior and R creates no brands. All of E's change across speeds is J(W_g):
  - at t40 it falls from +$40,303 at the current speed to +$33,547–33,816;
  - at t100 it rises from +$41,208 to +$50,215–51,449.
- **The owner gains from licensing its brand at every speed.** Under R at 0.10 its gain is +$7,821 at t40 and +$9,001 at t100, the same at every speed. White labels cost the owner money everywhere: −$1,527 to −$2,333 at t40, and at t100 −$1,373 at the current speed and −$3,990 to −$5,272 at the slow speeds.
- **Scope "new" kept the slowdown on new brands.** Across the never chains, the slow speeds change only deceptive stalls' profit: +$1,634 to +$2,929 at t40 and +$548 to +$1,180 at t100, because their reopened names hold ratings of 0.24–0.50 on day 20 instead of 0. Genuine and seconds-type profit, the owner's profit and catches do not change. In 0.18.0, where the prior reached every brand, genuine stalls lost $5,320 at t40.

## Caveats

- **The slow-speed results rest on an exact comparison at the top of the rating scale.** Buyers who read ratings rank by the unrounded rating. Under any prior, a new brand stays just below 1.0 for the whole 60 days, while day-1 genuine brands sit at exactly 1.0, so rating readers never treat a caught-up white label as equal to the owner. If buyers saw rounded ratings (stars, or two decimals), E after the catch-up would likely be much smaller at t40, and PS1, PS2 and PS4 could read differently. This is untested. The days 41–60 figures in the reading were computed from the run's cache after the results were seen; they were not prespecified.
- **There is no speed between 1.0 and 6.4 days.** The ~5-day level runs at 6.4 days, because nothing nearer to 5 passed the calibration's spread rule. So the run cannot show where between 1 and 6.4 days the step in E happens, and PS4's τ sits at the grid's edge.
- **Days to 0.9 in the run differ a little from the calibration.** For white labels at t40 they are 6.6, 10.3 and 20.8 days (calibration: 6.36, 10.38, 20.76); at t100 they are 4.7, 9.2 and 19.8. PS1 and PS4 use the calibration's t40 values, as specified.
- **At t100 no buyer reads ratings.** Tourists see no ratings (`ratings.visible_to`), so at t100 ratings act only through the posted price. The t100 results (PS5) describe a market where a low rating can only make a stall cheaper.
- **The price rule is mechanical.** Licensees and white labels post base × (1 + 0.4 × (rating − 0.5)) at the genuine tier, from the start-of-day rating (0 misses in 480 chains), rounded to the cent. No stall chooses its price.
- **The prior also reaches reopened deceptive names.** At the slow speeds deceptive stalls earn more (never chains, +$548 to +$2,929), because the prior is applied to every brand created after day 1. "Time to reputation" here means time for every new brand, not only white labels.
- **This is one option in one market,** as in Brand Equity: N = 6 from day 10, owner not liable, detect_scale 1, premium 0.4, memory 0.7, now 60 days. The royalty affects no decision (the replay passed 12 of 12 checks, at the current and slowest speeds), so the owner's gain at other royalty rates is an exact recompute.
- **Load.** The load average was 2.1 at start and 5–6 during the run, which affects only the wall clock (4.33 h). Chains are deterministic, the J identity holds in 1,440 of 1,440 owner-chains, and the pilot reproduced the 0.18.0 chains 28 of 28.
- **Intervals.** 95% intervals are over 20 seeds (the per-seed mean of 3 owners), unadjusted. Only PS1–PS3 are confirmatory; every other figure, including the mechanism in the reading, is exploratory.
