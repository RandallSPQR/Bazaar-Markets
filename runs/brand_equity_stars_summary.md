# Brand Equity speed under displayed ratings (stars)

Spec: the task "engine 0.20.0 (displayed ratings), rerun Brand Equity speed under it, and check whether earlier headline results move" (2026-11-18), Run A; predictions fixed 2026-11-18, before any run. Background: `runs/brand_equity_speed_summary.md`. Pilot gate: `runs/pilot_stars.md`.

## Design (prespecified)

- Question: with ratings displayed as stars (rounded), so that a new brand at 0.999 shows the same as a day-1 brand at 1.0, does the reputation effect E still rise with the time new brands take to earn a rating, and is it earned before the white labels catch up on the display?
- Engine 0.20.0. Exactly the brand_equity_speed design: 60 days (known to sellers), `ratings.prior_scope` new, the licensing market (detect_scale 1, owner not liable, `licensing.white_label_tier` genuine, royalty 0.10, N 6 from day 10, 3 owners per seed from `default_rng([seed, 17])`), quality contract, arms never / R / W_g; with `ratings.display` stars, `ratings.display_step` 0.02 (a tenth of a star) and `buyers.tie_break` random.
- Speeds (`ratings.prior_n`, calibrated at 0.19.0; days for a W_g white label's true rating to reach 0.9 at t40): current: prior_n 0, 1.04 days; d5: prior_n 3.5, 6.36 days; d10: prior_n 10, 10.38 days; d20: prior_n 400, 20.76 days.
- Verification: t40 (locals inspect) and t100. Seeds 330-349, paired across all cells.
- Sensitivity cells: `ratings.display_step` 0.1 (half a star) at prior_n 0 and 10, t40 and t100.
- Measures as brand_equity_speed: J = owner + 6 licensees' profit, days 10–60; E = J(R) − J(W_g) with the five-part split; windows by the true rating (catch-up = days 10 through the day the white labels' mean true rating first reaches 0.9); owner's gain and licensee profit by royalty. Added: the displayed catch-up day, the first day (≥ 10) at whose end the mean displayed rating of the owner's white labels (unrated = 0.5) equals the owner's displayed rating; before = days 10 through that day, after = the rest (if never reached, every day is before). The true days to 0.9 are reported alongside.
- Predictions (verbatim from the spec):
  - PT1 (confirmatory): t40: E rises with time to reputation (slope of E over the calibrated days to 0.9, per seed, > 0).
  - PT2 (confirmatory): t40, prior_n 400: more than half of E is earned before the displayed catch-up day.
  - PT3 (confirmatory): t40, prior_n 10: E after the displayed catch-up day is less than 20% of E.
  - PT4 (exploratory): t100: E at each speed; no direction.
  - PT5 (exploratory): step 0.1 − step 0.02, E at t40 and t100 at both speeds (coarser display should shrink E at the slow speed).
  - PT6 (exploratory): shape of E over days to 0.9 at t40 (linear vs saturating), and licensee preference R vs W_g by speed at royalty 0.05 and 0.10.
- Analysis: per seed the mean over 3 owners; mean and 95% t over seeds; unadjusted. PT1's slope is fitted per seed over the calibration's days to 0.9 (the same x as PS1). PT2 is tested as E(before) − E(after) > 0; PT3 as 0.2 × E − E(after) > 0, per seed.

## Run record

- Engine `0.20.0`; commit `47634b06fb2109efdca31041bcf2a99a29ee5144`; uncommitted at run time: ['?? runs/brand_equity_stars_run.log', '?? runs/brand_equity_stars_stdout.log', '?? runs/pilot_stars/A/brand_equity_stars_cache.jsonl', '?? runs/pilot_stars/B/stars_sensitivity_cache.jsonl', '?? runs/pilot_stars/g2_cache.jsonl', '?? runs/pilot_stars/os_check/g2_macos27_cache.jsonl', '?? runs/queue_stars.log']
- Script sha256 `edbd5e3cbdc55fb6961e37f69418bf126237d121730d32e2f9dee6573b58dac6`
- Command: `python -m analysis.brand_equity_stars --seeds 330-349 --workers 4 --min-swap-mb 0 --tests Engine 0.20.0 (952af31): full suite 1602 passed, 17 skipped, 1 failed (missing scaling rules, fixed); rerun of test_scale.py and test_v0200.py 222 passed (runs/tests_0200.log) --gate Pilot gate G1–G5 passed (runs/pilot_stars.md); G3 cut waived by the user for the full design (step 0.1 cells on, Run B 10 seeds per study)`
- Tests: Engine 0.20.0 (952af31): full suite 1602 passed, 17 skipped, 1 failed (missing scaling rules, fixed); rerun of test_scale.py and test_v0200.py 222 passed (runs/tests_0200.log)
- Python 3.12.7, numpy 2.5.4, macOS-27.2.1-arm64-arm-64bit
- 1692 chains × 60 days on 4 workers (nice 19); wall clock 6.50 h; load average [5.8, 4.97, 3.84] at start, [5.27, 5.6, 5.6] at end; memory at start {'swap_free_mb': 0.0, 'free_pct': 82}, at end {'swap_free_mb': 0.0, 'free_pct': 82}; memory-guard pauses: 0
- Seeds 330-349 (20), paired

## Gate and checks

Pilot gate G1–G5 passed (runs/pilot_stars.md); G3 cut waived by the user for the full design (step 0.1 cells on, Run B 10 seeds per study)

- Genuine-tier prices: every W_g white label's posted price equals base × (1 + 0.4 × (displayed start-of-day rating − 0.5)) on every day from 10: 0 misses in 480 chains.
- Equal display, equal price: on 100,106 label-days (days 11–60) a white label and its owner had the same displayed rating; their posted prices differ on 0.
- J identity: 1440/1440 owner-chains to the cent; largest split residual 0.000000 cents; windows add up to E to 0 cents.
- Royalty no-decision replay (seed 330, t100, R at 0.05 and 0.25 against 0.10, current and slowest speed): **pass** (12/12).
- Flags: none.

## Predictions

$ per owner over days 10–60 (per-seed mean of 3 owners). PT1–PT3 confirmatory; PT4–PT6 exploratory.

| Prediction | Estimate ($) | Verdict |
|---|---|---|
| **PT1**: t40: slope of E over days to 0.9 ($ per day) | +192.57 [+153.20, +231.93] * | supported |
| **PT2**: t40, prior_n 400: E before the displayed catch-up day − E after it (> 0 ⇔ more than half of E before) | +4,039.98 [+3,214.47, +4,865.48] * | supported |
| **PT3**: t40, prior_n 10: 20% of E − E after the displayed catch-up day (> 0 ⇔ E after < 20% of E) | +310.44 [+225.02, +395.86] * | supported |

PT2 share: E before / E at prior_n 400, t40 = 1.00 (ratio of means). PT3 share: E after / E at prior_n 10, t40 = -0.00 (ratio of means; per-seed ratios −0.00 [−0.00, 0.00]).

### E by speed, true and displayed catch-up

Days counted from day 10 = 1. True days to 0.9: a white label's own rating (mean over labels); owner catch-up (true): the labels' mean true rating ≥ 0.9; displayed catch-up: the labels' mean displayed rating equals the owner's (share of owner-chains that reach it in brackets; means over those that do).

| Speed, verification | E ($) | Label days to 0.9 (true) | Owner catch-up (true) | Displayed catch-up day (share reached) | E before displayed catch-up ($) | E after ($) |
|---|---|---|---|---|---|---|
| current, t40 | +246.70 [+188.72, +304.69] * | 1.0 | 1.0 | 1.0 (1.00) | +244.12 [+186.29, +301.94] * | +2.59 [−2.75, +7.92] |
| d5, t40 | +1,148.39 [+821.37, +1,475.42] * | 6.8 | 7.0 | 17.6 (1.00) | +1,147.36 [+820.89, +1,473.82] * | +1.04 [−1.00, +3.08] |
| d10, t40 | +1,547.47 [+1,121.83, +1,973.11] * | 10.3 | 10.3 | 20.7 (1.00) | +1,548.41 [+1,122.50, +1,974.33] * | −0.95 [−2.91, +1.02] |
| d20, t40 | +4,039.98 [+3,214.47, +4,865.48] * | 20.9 | 20.9 | 31.0 (1.00) | +4,039.98 [+3,214.47, +4,865.48] * | +0.00 [+0.00, +0.00] |
| current, t100 | +91.93 [+51.90, +131.96] * | 1.0 | 1.0 | 1.0 (1.00) | +91.90 [+51.89, +131.92] * | +0.03 [−0.03, +0.10] |
| d5, t100 | −4,482.32 [−5,317.16, −3,647.49] * | 4.8 | 5.4 | 15.6 (1.00) | −4,481.43 [−5,316.16, −3,646.70] * | −0.89 [−2.75, +0.97] |
| d10, t100 | −4,725.12 [−5,620.34, −3,829.89] * | 9.1 | 9.1 | 18.6 (1.00) | −4,725.12 [−5,620.34, −3,829.90] * | +0.00 [−0.00, +0.01] |
| d20, t100 | −3,522.70 [−4,205.89, −2,839.51] * | 19.8 | 19.9 | 28.9 (1.00) | −3,522.70 [−4,205.89, −2,839.51] * | +0.00 [+0.00, +0.00] |

**PT4** (t100, exploratory): current +91.93 [+51.90, +131.96] *; d5 −4,482.32 [−5,317.16, −3,647.49] *; d10 −4,725.12 [−5,620.34, −3,829.89] *; d20 −3,522.70 [−4,205.89, −2,839.51] *.

**PT5** (exploratory): E at step 0.1 − E at step 0.02, paired by seed:

| Speed, verification | E step 0.02 ($) | E step 0.1 ($) | Difference ($) |
|---|---|---|---|
| current, t40 | +246.70 [+188.72, +304.69] * | +246.70 [+188.72, +304.69] * | +0.00 [+0.00, +0.00] |
| current, t100 | +91.93 [+51.90, +131.96] * | +91.93 [+51.90, +131.96] * | +0.00 [+0.00, +0.00] |
| d10, t40 | +1,547.47 [+1,121.83, +1,973.11] * | +1,287.10 [+946.49, +1,627.71] * | −260.37 [−414.87, −105.86] * |
| d10, t100 | −4,725.12 [−5,620.34, −3,829.89] * | −2,378.44 [−2,860.69, −1,896.20] * | +2,346.67 [+1,900.28, +2,793.07] * |

**PT6** (exploratory). Fits of E on days to 0.9 at t40 over the per-seed points (n = 80):

| Fit | Parameters | R² | AIC |
|---|---|---|---|
| Linear: a + b x | a = −109.43, b = +192.57 per day | 0.638 | 1853.4 |
| Saturating: a + A(1 − e^−(x − x0)/τ) | a = +87.46, A = +194,479.11, τ = 1000.00 days (grid edge) | 0.638 | 1855.5 |

Licensee profit under R − under W_g ($ per licensee, days 10–60), by speed and royalty:

| Speed | t40, royalty 0.05 | t40, royalty 0.10 | t100, royalty 0.05 | t100, royalty 0.10 |
|---|---|---|---|---|
| current | −807.67 [−958.93, −656.40] * | −1,655.72 [−1,965.48, −1,345.96] * | −861.75 [−1,022.01, −701.49] * | −1,725.51 [−2,045.52, −1,405.49] * |
| d5 | −645.44 [−765.58, −525.30] * | −1,493.53 [−1,768.37, −1,218.69] * | −1,819.66 [−2,151.06, −1,488.26] * | −2,683.49 [−3,173.98, −2,193.00] * |
| d10 | −582.38 [−692.88, −471.88] * | −1,430.47 [−1,693.53, −1,167.40] * | −1,907.50 [−2,257.81, −1,557.20] * | −2,771.33 [−3,280.82, −2,261.85] * |
| d20 | −172.34 [−220.31, −124.37] * | −1,016.95 [−1,202.84, −831.06] * | −1,848.95 [−2,185.29, −1,512.62] * | −2,712.72 [−3,206.23, −2,219.21] * |

## Stars against the exact-rating run (0.19.0), paired by seed (exploratory)

Seeds 330–349 (20); exact from `runs/brand_equity_speed.json.gz`.

| Cell | Measure | Exact ($) | Stars ($) | Stars − exact ($) |
|---|---|---|---|---|
| current, t40 | E | +249.82 [+137.80, +361.85] * | +246.70 [+188.72, +304.69] * | −3.12 [−82.47, +76.24] |
| current, t40 | E_after | +3.54 [−6.05, +13.14] | +5.28 [−2.44, +13.00] | +1.74 [−11.93, +15.41] |
| current, t40 | owner_gain_Wg | −2,333.42 [−3,083.87, −1,582.98] * | −2,720.97 [−3,246.93, −2,195.02] * | −387.55 [−1,096.34, +321.24] |
| current, t40 | owner_gain_R_0.10 | +7,820.90 [+5,989.16, +9,652.64] * | +7,460.04 [+6,013.09, +8,907.00] * | −360.86 [−1,253.55, +531.83] |
| d5, t40 | E | +7,005.74 [+3,671.51, +10,339.97] * | +1,148.39 [+821.37, +1,475.42] * | −5,857.35 [−9,035.76, −2,678.93] * |
| d5, t40 | E_after | +6,396.92 [+3,659.05, +9,134.79] * | +684.46 [+476.46, +892.46] * | −5,712.47 [−8,384.43, −3,040.50] * |
| d5, t40 | owner_gain_Wg | −1,527.36 [−1,870.46, −1,184.26] * | −2,648.18 [−3,144.11, −2,152.26] * | −1,120.82 [−1,352.85, −888.79] * |
| d5, t40 | owner_gain_R_0.10 | +7,820.87 [+5,989.11, +9,652.63] * | +7,461.38 [+6,014.04, +8,908.72] * | −359.49 [−1,251.45, +532.47] |
| d10, t40 | E | +6,736.98 [+3,337.04, +10,136.93] * | +1,547.47 [+1,121.83, +1,973.11] * | −5,189.52 [−8,402.90, −1,976.14] * |
| d10, t40 | E_after | +5,742.29 [+3,188.29, +8,296.29] * | +704.50 [+473.32, +935.68] * | −5,037.79 [−7,491.73, −2,583.86] * |
| d10, t40 | owner_gain_Wg | −1,693.39 [−2,077.19, −1,309.58] * | −2,668.89 [−3,171.04, −2,166.75] * | −975.51 [−1,200.77, −750.25] * |
| d10, t40 | owner_gain_R_0.10 | +7,820.87 [+5,989.11, +9,652.63] * | +7,461.37 [+6,014.04, +8,908.71] * | −359.50 [−1,251.45, +532.46] |
| d20, t40 | E | +7,005.20 [+3,323.59, +10,686.82] * | +4,039.98 [+3,214.47, +4,865.48] * | −2,965.23 [−6,432.50, +502.05] |
| d20, t40 | E_after | +3,323.07 [+1,371.87, +5,274.27] * | +716.99 [+521.03, +912.95] * | −2,606.08 [−4,605.34, −606.83] * |
| d20, t40 | owner_gain_Wg | −2,243.82 [−2,740.44, −1,747.19] * | −2,674.41 [−3,156.53, −2,192.29] * | −430.60 [−653.84, −207.35] * |
| d20, t40 | owner_gain_R_0.10 | +7,820.98 [+5,989.32, +9,652.64] * | +7,467.29 [+6,013.29, +8,921.28] * | −353.69 [−1,246.90, +539.51] |
| current, t100 | E | +101.08 [−4.59, +206.75] | +91.93 [+51.90, +131.96] * | −9.15 [−101.21, +82.92] |
| current, t100 | E_after | −0.82 [−3.60, +1.96] | +0.03 [−0.03, +0.10] | +0.85 [−1.93, +3.63] |
| current, t100 | owner_gain_Wg | −1,373.19 [−2,187.82, −558.55] * | −1,750.06 [−2,117.51, −1,382.61] * | −376.87 [−1,236.49, +482.74] |
| current, t100 | owner_gain_R_0.10 | +9,002.75 [+6,959.94, +11,045.57] * | +8,694.91 [+7,052.90, +10,336.93] * | −307.84 [−1,305.25, +689.57] |
| d5, t100 | E | −9,961.77 [−13,004.44, −6,919.11] * | −4,482.32 [−5,317.16, −3,647.49] * | +5,479.45 [+2,854.34, +8,104.56] * |
| d5, t100 | E_after | −8,961.22 [−11,607.04, −6,315.39] * | −3,405.68 [−4,023.34, −2,788.03] * | +5,555.54 [+3,284.01, +7,827.07] * |
| d5, t100 | owner_gain_Wg | −3,989.91 [−4,747.69, −3,232.14] * | −2,921.70 [−3,452.88, −2,390.52] * | +1,068.21 [+691.09, +1,445.33] * |
| d5, t100 | owner_gain_R_0.10 | +9,001.32 [+6,958.23, +11,044.42] * | +8,696.91 [+7,053.91, +10,339.92] * | −304.41 [−1,300.03, +691.21] |
| d10, t100 | E | −10,139.40 [−13,393.10, −6,885.70] * | −4,725.12 [−5,620.34, −3,829.89] * | +5,414.28 [+2,574.15, +8,254.41] * |
| d10, t100 | E_after | −8,812.13 [−11,367.42, −6,256.83] * | −3,242.71 [−3,829.76, −2,655.66] * | +5,569.42 [+3,361.48, +7,777.35] * |
| d10, t100 | owner_gain_Wg | −4,287.32 [−5,104.13, −3,470.50] * | −3,205.96 [−3,780.52, −2,631.40] * | +1,081.36 [+704.00, +1,458.72] * |
| d10, t100 | owner_gain_R_0.10 | +9,001.32 [+6,958.23, +11,044.42] * | +8,696.91 [+7,053.91, +10,339.92] * | −304.41 [−1,300.03, +691.21] |
| d20, t100 | E | −8,904.76 [−12,700.55, −5,108.97] * | −3,522.70 [−4,205.89, −2,839.51] * | +5,382.06 [+1,795.79, +8,968.33] * |
| d20, t100 | E_after | −8,649.32 [−11,128.81, −6,169.82] * | −3,094.13 [−3,646.03, −2,542.23] * | +5,555.19 [+3,385.34, +7,725.04] * |
| d20, t100 | owner_gain_Wg | −5,272.22 [−6,317.04, −4,227.40] * | −4,057.63 [−4,795.82, −3,319.43] * | +1,214.59 [+776.42, +1,652.76] * |
| d20, t100 | owner_gain_R_0.10 | +8,999.25 [+6,958.99, +11,039.52] * | +8,696.00 [+7,056.47, +10,335.53] * | −303.26 [−1,297.18, +690.67] |

## All cells

| Cell | J never | J W_g | J R | E | owner_sales | licensee_sales | licensee_prices | licensee_ad | fines |
|---|---|---|---|---|---|---|---|---|---|
| current, t40 | −9,055.42 [−11,321.45, −6,789.39] * | +39,896.42 [+32,389.42, +47,403.42] * | +40,143.13 [+32,593.92, +47,692.33] * | +246.70 [+188.72, +304.69] * | +4.38 [−10.85, +19.60] | −162.15 [−233.79, −90.52] * | +404.69 [+319.74, +489.63] * | −0.20 [−0.44, +0.04] | +0.00 [+0.00, +0.00] |
| d5, t40 | −8,747.99 [−10,960.98, −6,535.00] * | +38,996.21 [+31,680.19, +46,312.24] * | +40,144.61 [+32,594.96, +47,694.26] * | +1,148.39 [+821.37, +1,475.42] * | −67.48 [−155.33, +20.38] | −159.10 [−407.84, +89.64] | +1,375.02 [+1,117.90, +1,632.15] * | −0.05 [−0.73, +0.62] | +0.00 [+0.00, +0.00] |
| d10, t40 | −8,630.41 [−10,824.10, −6,436.73] * | +38,597.15 [+31,372.01, +45,822.29] * | +40,144.62 [+32,594.97, +47,694.27] * | +1,547.47 [+1,121.83, +1,973.11] * | −46.77 [−136.69, +43.15] | −613.74 [−909.23, −318.26] * | +2,208.01 [+1,796.87, +2,619.14] * | −0.02 [−0.95, +0.90] | +0.00 [+0.00, +0.00] |
| d20, t40 | −8,556.39 [−10,795.91, −6,316.87] * | +35,916.50 [+29,204.14, +42,628.85] * | +39,956.47 [+32,455.10, +47,457.85] * | +4,039.98 [+3,214.47, +4,865.48] * | +6.32 [−95.83, +108.48] | −1,836.21 [−2,227.29, −1,445.13] * | +5,869.90 [+4,779.84, +6,959.97] * | −0.04 [−0.98, +0.89] | +0.00 [+0.00, +0.00] |
| current, t100 | −16,312.76 [−20,077.39, −12,548.13] * | +40,913.70 [+33,282.08, +48,545.31] * | +41,005.63 [+33,357.95, +48,653.31] * | +91.93 [+51.90, +131.96] * | +79.87 [+57.49, +102.25] * | −568.50 [−701.99, −435.01] * | +580.41 [+459.23, +701.60] * | +0.15 [−0.09, +0.39] | +0.00 [+0.00, +0.00] |
| d5, t100 | −16,177.99 [−19,903.83, −12,452.16] * | +45,491.37 [+37,028.19, +53,954.55] * | +41,009.05 [+33,357.06, +48,661.04] * | −4,482.32 [−5,317.16, −3,647.49] * | +1,252.66 [+1,033.14, +1,472.19] * | −7,208.91 [−8,523.06, −5,894.76] * | +1,473.40 [+1,197.99, +1,748.82] * | +0.52 [−0.25, +1.30] | +0.00 [+0.00, +0.00] |
| d10, t100 | −16,121.80 [−19,834.39, −12,409.21] * | +45,734.17 [+37,201.38, +54,266.95] * | +41,009.05 [+33,357.06, +48,661.04] * | −4,725.12 [−5,620.34, −3,829.89] * | +1,536.92 [+1,270.52, +1,803.33] * | −8,600.76 [−10,183.47, −7,018.05] * | +2,337.92 [+1,904.34, +2,771.50] * | +0.80 [−0.04, +1.64] | +0.00 [+0.00, +0.00] |
| d20, t100 | −16,101.61 [−19,819.87, −12,383.35] * | +44,530.22 [+36,273.00, +52,787.44] * | +41,007.52 [+33,360.05, +48,655.00] * | −3,522.70 [−4,205.89, −2,839.51] * | +2,388.43 [+1,943.92, +2,832.93] * | −12,125.21 [−14,340.55, −9,909.88] * | +6,213.42 [+5,056.24, +7,370.59] * | +0.67 [−0.51, +1.85] | +0.00 [+0.00, +0.00] |

## Reading (written after the results)

- **PT1, PT2 and PT3 are supported. When buyers see star ratings, the reputation effect at t40 grows steadily with the time new brands take to earn a rating: +$247, +$1,148, +$1,547 and +$4,040 at 1.0, 6.4, 10.4 and 20.8 days to 0.9, about +$193 a day. All of it is earned before the white labels display the same rating as the owner; after that, E is about $0. Under exact ratings this E was about $7,000 at every slow speed. Most of that came from white labels rated 0.999 losing to the owner's 1.0, and stars remove it. With no rating readers (t100), slow ratings still favour the white labels, by about half as much as before.**
  - **PT1:** the slope of E over days to 0.9 is +$192.57 [+153.20, +231.93] per day. Under exact ratings it was +$277 [+124, +430], almost all from the step between the current speed and the rest. Here E rises between every pair of neighbouring speeds.
  - **PT2:** at prior_n 400, E before the displayed catch-up day is +$4,039.98 [+3,214.47, +4,865.48] and after it $0.00. The test, before − after, is +$4,039.98 [+3,214.47, +4,865.48], so more than half of E is earned before. The share is 1.00. Under exact ratings, PS2 (the same claim with the true-rating window) was not supported, with a share of 0.53.
  - **PT3:** at prior_n 10, E after the displayed catch-up day is −$0.95 [−2.91, +1.02], against E of +$1,547.47. The test, 20% of E − E after, is +$310.44 [+225.02, +395.86]. E after is 0% of E.
  - **PT6, shape:** the linear and saturating fits explain the same share of the per-seed spread (R² 0.638 each). The saturating fit's τ runs to the grid's upper edge (1,000 days), which makes it a straight line, and linear has the lower AIC (1,853.4 against 1,855.5). Under exact ratings the saturating fit won with τ at the lower edge, a step, and R² was 0.08–0.18.
- **Under stars the t40 effect works through the white label's price, not through which stall buyers choose.**
  - From the split: at t40, E is licensee prices +$405, +$1,375, +$2,208 and +$5,870 at the four speeds, with licensee sales slightly negative (−$159 to −$1,836). A white label posts from its displayed rating, so while it displays below the owner it posts below the R licensees, who copy the owner's displayed rating. Its mean price is $65.02, $64.40, $63.86 and $61.49 against R's $65.28.
  - It sells about as many units as an R licensee, or slightly more: 1,564–1,637 against 1,551–1,558 per owner's six. Under exact ratings it sold 1,281–1,332 against 1,514 at d5 and d10, because rating readers ranked every white label below 1.0 for the whole run. That sales component was +$6,260 and +$4,960 at d5 and d10. Under stars it is gone.
  - The labels' display catches up with the owner's about 10 days after their true rating reaches 0.9: on day 17.6, 20.7 and 31.0 (counted from day 10 = 1) against 7.0, 10.3 and 20.9. To display 1.00 at step 0.02 a rating must reach 0.99. In the true-rating windows of the exact run, this shows as about $700 of E after the true catch-up (+$684, +$705, +$717 at d5, d10, d20), all of it before the display catches up.
- **At t100, E is negative at every slow speed, about half its exact size.** It is −$4,482, −$4,725 and −$3,523 at d5, d10 and d20 (PT4), against −$9,962, −$10,139 and −$8,905 exact. The paired differences are +$5,479, +$5,414 and +$5,382, all intervals above 0.
  - Tourists buy the cheapest candidate, and a white label displaying below the owner posts cheaper. So W_g licensees sell 1,879–2,144 units against R's 1,589, and the owner sells 171–214 against 263.
  - Under stars, prices tie once the display catches up, and the random tie-break shares those buyers. Under exact ratings, a label just below 1.0 stayed a cent cheaper late into the run.
- **A coarser display (step 0.1, PT5) shrinks E at the slow speed and leaves the current speed unchanged.**
  - At d10, E changes by −$260.37 [−414.87, −105.86] at t40, and by +$2,346.67 [+1,900.28, +2,793.07] at t100, halving the white labels' t100 advantage.
  - At the current speed the difference is exactly $0: labels reach 1.0 on day 1, so a half-star and a tenth-star display show the same.
- **Licensees prefer a white label to an R licence at every speed, both verifications and both royalties.** Every interval in the table is below 0. At t40 and royalty 0.05 the gap is −$808 at the current speed and −$645, −$582 and −$172 at d5, d10 and d20. Under exact ratings the point estimates at royalty 0.05 favoured R at the three slow speeds; no interval was computed then. Under stars that preference is gone, because a white label no longer loses sales to rating readers.
- **The owner still gains from licensing its brand, and white labels cost it slightly more than before at t40.**
  - Under R at 0.10 the owner's gain is +$7,460 at t40 and +$8,695 at t100, the same at every speed. Against exact, the change is −$360 [−1,254, +532] at t40.
  - Under W_g the owner loses −$2,648 to −$2,721 at t40, about the same at every speed, against −$1,527 to −$2,333 exact. Exact ratings gave the owner extra sales at the slow speeds (rating readers ranked it above its own white labels). With stars that advantage is gone.

## Caveats

- **One display rule, and the tie-break changed with it.** Stars here round to 0.02 (a tenth of a star); PT5 shows that E depends on the step (−$260 at d10, t40 with half stars). The run also switched buyers' tie-breaks from stall id to random. The stars − exact comparisons therefore measure both changes together; this run cannot separate them. The current speed, where display changes nothing, gives a rough guide to the tie-break alone: E at t40 changed by −$3 [−82, +76], J(R) by about −$400 at t40.
- **The displayed catch-up day is defined against the owner's display.** The owner's brand carries no prior and displays 1.00 all run, so the labels' display catches up when their mean rating reaches about 0.99, not 0.9. PT1 and PT6 still use the calibration's true days to 0.9 as x; the displayed day is about 10 days later at each slow speed.
- **There is still no speed between 1.0 and 6.4 days,** for the same calibration reason as before, so the linear shape is fitted over four speeds with a gap at the low end.
- **At t100 no buyer reads ratings.** Tourists see no ratings, so at t100 ratings act only through the posted price.
- **The exact comparison spans an OS update.** The exact chains were run at engine 0.19.0 under macOS 26.6; this run at 0.20.0 under macOS 27.2. The pilot reproduced 112 of 112 exact chains at 0.20.0 on the old OS, and 16 of 16 on the new OS before launch, by full digest. The comparison table is exploratory.
- **The full design ran because you waived the timing gate's cut** (G3 projected 9.8 h against a 7 h limit). The choice was made after the pilot, from the timing alone. The run took 6.50 h for Run A, at a load average of about 5–6, which affects only the wall clock.
- **This is one option in one market,** as in Brand Equity speed: N = 6 from day 10, owner not liable, detect_scale 1, premium 0.4, memory 0.7, 60 days. The royalty affects no decision under stars (replay 12 of 12), so the owner's gain at other royalties is an exact recompute.
- **Intervals.** 95% intervals are over 20 seeds (the per-seed mean of 3 owners), unadjusted. Only PT1–PT3 are confirmatory. Every other figure is exploratory, including the mechanism in the reading (read from the prespecified split, units and prices) and the comparison with the exact run.
