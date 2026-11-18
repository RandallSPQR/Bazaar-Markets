# Brand Equity speed under displayed ratings (stars)

Spec: the task "engine 0.20.0 (displayed ratings), rerun Brand Equity speed under it, and check whether earlier headline results move" (2026-11-18), Run A; predictions fixed 2026-11-18, before any run. Background: `runs/brand_equity_speed_summary.md`. Pilot gate: `runs/pilot_stars.md`.

## Design (prespecified)

- Question: with ratings displayed as stars (rounded), so that a new brand at 0.999 shows the same as a day-1 brand at 1.0, does the reputation effect E still rise with the time new brands take to earn a rating, and is it earned before the white labels catch up on the display?
- Engine 0.20.0. Exactly the brand_equity_speed design: 60 days (known to sellers), `ratings.prior_scope` new, the licensing market (detect_scale 1, owner not liable, `licensing.white_label_tier` genuine, royalty 0.10, N 6 from day 10, 3 owners per seed from `default_rng([seed, 17])`), quality contract, arms never / R / W_g; with `ratings.display` stars, `ratings.display_step` 0.02 (a tenth of a star) and `buyers.tie_break` random.
- Speeds (`ratings.prior_n`, calibrated at 0.19.0; days for a W_g white label's true rating to reach 0.9 at t40): current: prior_n 0, 1.04 days; d5: prior_n 3.5, 6.36 days; d10: prior_n 10, 10.38 days; d20: prior_n 400, 20.76 days.
- Verification: t40 (locals inspect) and t100. Seeds 900-902, paired across all cells.
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

- Engine `0.20.0`; commit `84b7243fc97eabe8b946096cc6b7bd7561695e0b`; uncommitted at run time: ['?? runs/pilot_stars/', '?? runs/pilot_stars_stdout.log', '?? runs/queue_stars.sh']
- Script sha256 `edbd5e3cbdc55fb6961e37f69418bf126237d121730d32e2f9dee6573b58dac6`
- Command: `python -m analysis.brand_equity_stars --tests Engine 0.20.0: full suite 1602 passed, 17 skipped, 1 failed (missing scaling rules, fixed); rerun of test_scale.py and test_v0200.py 222 passed (runs/tests_0200.log)`
- Tests: Engine 0.20.0: full suite 1602 passed, 17 skipped, 1 failed (missing scaling rules, fixed); rerun of test_scale.py and test_v0200.py 222 passed (runs/tests_0200.log)
- Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit
- 264 chains × 60 days on 4 workers (nice 19); wall clock 1.04 h; load average [6.91, 6.59, 5.96] at start, [10.74, 8.48, 7.2] at end; memory at start {'swap_free_mb': 1328.31, 'free_pct': 65}, at end {'swap_free_mb': 1328.31, 'free_pct': 63}; memory-guard pauses: 0
- Seeds 900-902 (3), paired

## Gate and checks

Pilot run (seeds 900–902).

- Genuine-tier prices: every W_g white label's posted price equals base × (1 + 0.4 × (displayed start-of-day rating − 0.5)) on every day from 10: 0 misses in 72 chains.
- Equal display, equal price: on 15,005 label-days (days 11–60) a white label and its owner had the same displayed rating; their posted prices differ on 0.
- J identity: 216/216 owner-chains to the cent; largest split residual 0.000000 cents; windows add up to E to 0 cents.
- Royalty no-decision replay (seed 900, t100, R at 0.05 and 0.25 against 0.10, current and slowest speed): **pass** (12/12).
- Flags: none.

## Predictions

$ per owner over days 10–60 (per-seed mean of 3 owners). PT1–PT3 confirmatory; PT4–PT6 exploratory.

| Prediction | Estimate ($) | Verdict |
|---|---|---|
| **PT1**: t40: slope of E over days to 0.9 ($ per day) | +255.11 [+64.16, +446.06] * | supported |
| **PT2**: t40, prior_n 400: E before the displayed catch-up day − E after it (> 0 ⇔ more than half of E before) | +5,337.55 [+1,100.96, +9,574.14] * | supported |
| **PT3**: t40, prior_n 10: 20% of E − E after the displayed catch-up day (> 0 ⇔ E after < 20% of E) | +353.14 [+58.19, +648.09] * | supported |

PT2 share: E before / E at prior_n 400, t40 = 1.00 (ratio of means). PT3 share: E after / E at prior_n 10, t40 = 0.00 (ratio of means; per-seed ratios 0.00 [−0.01, 0.02]).

### E by speed, true and displayed catch-up

Days counted from day 10 = 1. True days to 0.9: a white label's own rating (mean over labels); owner catch-up (true): the labels' mean true rating ≥ 0.9; displayed catch-up: the labels' mean displayed rating equals the owner's (share of owner-chains that reach it in brackets; means over those that do).

| Speed, verification | E ($) | Label days to 0.9 (true) | Owner catch-up (true) | Displayed catch-up day (share reached) | E before displayed catch-up ($) | E after ($) |
|---|---|---|---|---|---|---|
| current, t40 | +413.36 [−419.03, +1,245.74] | 1.0 | 1.0 | 1.0 (1.00) | +409.08 [−429.28, +1,247.44] | +4.28 [−14.13, +22.69] |
| d5, t40 | +1,188.44 [+290.31, +2,086.57] * | 6.7 | 7.0 | 17.7 (1.00) | +1,184.18 [+268.36, +2,099.99] * | +4.26 [−14.07, +22.59] |
| d10, t40 | +1,800.01 [+235.25, +3,364.78] * | 10.4 | 10.6 | 20.7 (1.00) | +1,793.15 [+247.10, +3,339.21] * | +6.86 [−22.67, +36.39] |
| d20, t40 | +5,337.55 [+1,100.96, +9,574.14] * | 20.7 | 20.8 | 30.9 (1.00) | +5,337.55 [+1,100.96, +9,574.14] * | +0.00 [+0.00, +0.00] |
| current, t100 | +97.84 [−821.91, +1,017.59] | 1.0 | 1.0 | 1.0 (1.00) | +97.84 [−821.91, +1,017.59] | +0.00 [+0.00, +0.00] |
| d5, t100 | −6,543.47 [−10,176.85, −2,910.09] * | 4.9 | 5.4 | 15.4 (1.00) | −6,543.47 [−10,176.85, −2,910.09] * | +0.00 [+0.00, +0.00] |
| d10, t100 | −6,970.22 [−11,049.32, −2,891.12] * | 9.2 | 9.2 | 18.4 (1.00) | −6,970.22 [−11,049.32, −2,891.12] * | +0.00 [+0.00, +0.00] |
| d20, t100 | −5,736.64 [−11,249.38, −223.89] * | 19.8 | 19.9 | 29.1 (1.00) | −5,736.64 [−11,249.38, −223.89] * | +0.00 [+0.00, +0.00] |

**PT4** (t100, exploratory): current +97.84 [−821.91, +1,017.59]; d5 −6,543.47 [−10,176.85, −2,910.09] *; d10 −6,970.22 [−11,049.32, −2,891.12] *; d20 −5,736.64 [−11,249.38, −223.89] *.

**PT5** (exploratory): E at step 0.1 − E at step 0.02, paired by seed:

| Speed, verification | E step 0.02 ($) | E step 0.1 ($) | Difference ($) |
|---|---|---|---|
| current, t40 | +413.36 [−419.03, +1,245.74] | +413.36 [−419.03, +1,245.74] | +0.00 [+0.00, +0.00] |
| current, t100 | +97.84 [−821.91, +1,017.59] | +97.84 [−821.91, +1,017.59] | +0.00 [+0.00, +0.00] |
| d10, t40 | +1,800.01 [+235.25, +3,364.78] * | +1,390.35 [+926.38, +1,854.32] * | −409.66 [−1,595.46, +776.13] |
| d10, t100 | −6,970.22 [−11,049.32, −2,891.12] * | −3,299.89 [−5,251.60, −1,348.18] * | +3,670.33 [+1,542.76, +5,797.90] * |

**PT6** (exploratory). Fits of E on days to 0.9 at t40 over the per-seed points (n = 12):

| Fit | Parameters | R² | AIC |
|---|---|---|---|
| Linear: a + b x | a = −272.73, b = +255.11 per day | 0.819 | 276.8 |
| Saturating: a + A(1 − e^−(x − x0)/τ) | a = −11.33, A = +257,576.87, τ = 1000.00 days (grid edge) | 0.818 | 278.9 |

Licensee profit under R − under W_g ($ per licensee, days 10–60), by speed and royalty:

| Speed | t40, royalty 0.05 | t40, royalty 0.10 | t100, royalty 0.05 | t100, royalty 0.10 |
|---|---|---|---|---|
| current | −1,153.54 [−1,805.60, −501.48] * | −2,369.12 [−3,745.47, −992.76] * | −1,231.66 [−1,935.11, −528.22] * | −2,465.50 [−3,921.55, −1,009.45] * |
| d5 | −1,024.81 [−1,619.78, −429.85] * | −2,240.38 [−3,558.33, −922.44] * | −2,644.86 [−4,118.32, −1,171.41] * | −3,878.75 [−6,106.81, −1,650.69] * |
| d10 | −935.43 [−1,481.16, −389.71] * | −2,151.01 [−3,405.63, −896.38] * | −2,792.96 [−4,363.25, −1,222.67] * | −4,026.84 [−6,348.18, −1,705.51] * |
| d20 | −337.53 [−433.70, −241.36] * | −1,547.66 [−2,346.97, −748.35] * | −2,787.45 [−4,637.67, −937.22] * | −4,020.89 [−6,608.20, −1,433.57] * |

## All cells

| Cell | J never | J W_g | J R | E | owner_sales | licensee_sales | licensee_prices | licensee_ad | fines |
|---|---|---|---|---|---|---|---|---|---|
| current, t40 | −10,660.06 [−25,100.27, +3,780.16] | +60,280.78 [+23,594.00, +96,967.55] * | +60,694.13 [+23,467.21, +97,921.06] * | +413.36 [−419.03, +1,245.74] | +41.18 [−84.79, +167.15] | −228.30 [−428.63, −27.97] * | +600.92 [−63.16, +1,265.00] | −0.44 [−1.24, +0.36] | +0.00 [+0.00, +0.00] |
| d5, t40 | −10,107.40 [−24,313.48, +4,098.67] | +59,505.48 [+22,981.16, +96,029.80] * | +60,693.92 [+23,466.08, +97,921.76] * | +1,188.44 [+290.31, +2,086.57] * | +43.86 [−120.86, +208.59] | −785.25 [−1,528.93, −41.56] * | +1,929.17 [+709.05, +3,149.30] * | +0.64 [−3.12, +4.41] | +0.00 [+0.00, +0.00] |
| d10, t40 | −9,914.86 [−24,028.44, +4,198.73] | +58,893.91 [+22,978.28, +94,809.53] * | +60,693.92 [+23,466.08, +97,921.76] * | +1,800.01 [+235.25, +3,364.78] * | +119.17 [−76.80, +315.15] | −1,433.40 [−2,716.65, −150.14] * | +3,113.82 [+1,338.17, +4,889.47] * | +0.42 [−3.48, +4.32] | +0.00 [+0.00, +0.00] |
| d20, t40 | −9,424.08 [−21,725.34, +2,877.18] | +54,971.58 [+21,521.50, +88,421.67] * | +60,309.13 [+23,093.90, +97,524.36] * | +5,337.55 [+1,100.96, +9,574.14] * | +101.91 [−1,136.99, +1,340.81] | −3,095.71 [−3,964.12, −2,227.30] * | +8,330.49 [+3,521.25, +13,139.73] * | +0.85 [−2.41, +4.11] | +0.00 [+0.00, +0.00] |
| current, t100 | −18,429.96 [−40,696.39, +3,836.47] | +61,712.02 [+23,521.02, +99,903.02] * | +61,809.86 [+23,124.21, +100,495.51] * | +97.84 [−821.91, +1,017.59] | +84.78 [−139.01, +308.57] | −826.69 [−1,364.56, −288.83] * | +840.32 [−8.13, +1,688.77] | −0.57 [−1.73, +0.58] | +0.00 [+0.00, +0.00] |
| d5, t100 | −18,266.70 [−40,270.21, +3,736.82] | +68,349.20 [+26,220.94, +110,477.45] * | +61,805.72 [+23,121.50, +100,489.95] * | −6,543.47 [−10,176.85, −2,910.09] * | +1,922.40 [+825.38, +3,019.43] * | −10,577.96 [−16,368.62, −4,787.30] * | +2,112.08 [+640.99, +3,583.16] * | +0.00 [−5.29, +5.30] | +0.00 [+0.00, +0.00] |
| d10, t100 | −18,210.72 [−40,254.20, +3,832.77] | +68,775.94 [+26,347.12, +111,204.76] * | +61,805.72 [+23,121.50, +100,489.95] * | −6,970.22 [−11,049.32, −2,891.12] * | +2,384.22 [+1,118.21, +3,650.22] * | −12,673.54 [−19,620.77, −5,726.30] * | +3,318.91 [+1,282.51, +5,355.32] * | +0.19 [−2.30, +2.68] | +0.00 [+0.00, +0.00] |
| d20, t100 | −18,235.07 [−40,115.68, +3,645.55] | +67,547.17 [+24,387.17, +110,707.17] * | +61,810.54 [+23,161.86, +100,459.21] * | −5,736.64 [−11,249.38, −223.89] * | +3,587.40 [+1,483.27, +5,691.53] * | −18,053.20 [−29,741.08, −6,365.33] * | +8,729.84 [+3,509.64, +13,950.03] * | −0.67 [−3.87, +2.54] | +0.00 [+0.00, +0.00] |

## Reading (written after the results)

READING_PLACEHOLDER

## Caveats

CAVEATS_PLACEHOLDER
