# Brand Equity at the genuine tier, with rating speed

Spec: `runs/plan_brand_equity_tier.md` (2026-11-13) and the addendum "rating speed as a factor" (2026-11-16); predictions fixed 2026-11-16, before any run. Calibration: `runs/calibration_rating_speed.md`. Pilot gate: `runs/pilot_brand_equity_tier.md`.

## Design (prespecified)

- Question: what does a reputation earn once a white label may price like the owner, and does it earn more when reputations form slowly?
- Engine 0.18.0. Market, owners and licence option as Brand Equity: the licensing market, detect_scale 1, owner not liable; 3 owners per seed from `default_rng([seed, 17])`; N 6 from day 10, royalty 0.10.
- Arms per owner: never; R (licensees under the owner's brand); W_g (the same stalls under white labels at the genuine tier, `licensing.white_label_tier` genuine); W_t (white labels at their stall type's tier, the 0.17.0 W).
- Rating speed: `ratings.prior_n` (every brand starts with prior_n pseudo-reviews at 0.5, counted in each day's share and fading by memory 0.7 per day). Levels from the calibration (days for a fresh contract white label to reach a 0.9 rating, t40): current: prior_n 0, 1.0 days; slow15: prior_n 50, 14.9 days.
- Current speed: never, R, W_g, W_t × {contract, cheap} × {t40, t100}. Slow speeds: never, R, W_g × contract × {t40, t100}. Seeds 300–329, paired; everything rerun at 0.18.0. Extra gate: at current speed, never, R and W_t equal the 0.17.0 Brand Equity chains to the cent.
- Measures, per owner: J = owner + 6 licensees' profit, days 10–30. Reputation effect = J(R) − J(W_g), split into owner own sales, licensee sales, licensee prices, licensee ad spend and fines. Tier effect = J(W_g) − J(W_t) (current speed); the 0.17.0 name effect J(R) − J(W_t) = reputation + tier. Composition = J(W_g) − J(never). Each effect is compared within its own speed; never chains are reported across speeds. Owner's gain at 0.05–0.25 by the exact recompute after the no-decision check.
- Predictions (verbatim from the spec):
  - PR1 (confirmatory): contract, t40: the reputation effect rises with time to reputation. Slope of R − W_g over days-to-0.9 (three levels) > 0.
  - PR2 (confirmatory): contract, t40, current speed: reputation effect < tier effect.
  - PR3 (exploratory): at the slowest speed, the reputation effect at t40 − at t100 > 0 (buyers who read ratings become the channel once reputations are slow).
  - PR4 (exploratory): the owner's gain at royalty 0.10 rises with time to reputation.
- Analysis: per seed the mean over 3 owners; mean and 95% t over seeds; unadjusted. Slopes (PR1, PR4) fitted per seed by least squares over the calibration's days to 0.9, then averaged; PR4 in contract at t40 and at t100.

## Run record

- Engine `0.18.0`; commit `1a39d229b9c6be2268e5eabb0a002d01c694981a`; uncommitted at run time: ['?? runs/brand_equity_tier_run.log', '?? runs/brand_equity_tier_stdout.log', '?? runs/queue_brand_equity_tier.log']
- Script sha256 `394f94ddb75017c2e26aebf22b12a5534c274f38ec4ae8c9957fc6b6672ef14a`
- Command: `python -m analysis.brand_equity_tier --seeds 300-329 --workers 4 --tests 1261 passed, 17 skipped at 20ee303 (runs/tests_0180.log) --gate Pilot gate G1–G5 passed (runs/pilot_brand_equity_tier.md); levels from runs/calibration_rating_speed.md`
- Tests: 1261 passed, 17 skipped at 20ee303 (runs/tests_0180.log)
- Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit
- 1578 chains × 30 days on 4 workers (nice 19); wall clock 3.19 h; load average [6.57, 3.63, 2.62] at start, [6.7, 6.51, 6.36] at end; memory at start {'swap_free_mb': 1248.31, 'free_pct': 77}, at end {'swap_free_mb': 1264.31, 'free_pct': 64}; memory-guard pauses: 0
- Seeds 300-329 (30), paired
- Sampled owners per seed: 300: s12, s14, s46; 301: s10, s08, s39; 302: s17, s45, s31; 303: s13, s31, s06; 304: s40, s38, s10; 305: s31, s01, s04; 306: s06, s36, s31; 307: s38, s30, s02; 308: s36, s11, s19; 309: s08, s05, s26; 310: s31, s19, s00; 311: s31, s08, s38; 312: s14, s44, s13; 313: s47, s05, s45; 314: s28, s45, s16; 315: s44, s02, s05; 316: s41, s29, s35; 317: s35, s42, s11; 318: s13, s40, s24; 319: s12, s15, s11; 320: s45, s23, s13; 321: s34, s40, s09; 322: s08, s05, s33; 323: s30, s41, s37; 324: s41, s45, s20; 325: s44, s04, s42; 326: s23, s16, s19; 327: s16, s06, s21; 328: s29, s23, s37; 329: s12, s15, s17

## Gate

Pilot gate G1–G5 passed (runs/pilot_brand_equity_tier.md); levels from runs/calibration_rating_speed.md

0.17.0 identity (current speed never, R and W_t against `runs/brand_equity_cache.jsonl`, full-outcome digest and every ledger to the cent): 780/780 chains equal.

Genuine-tier prices: every W_g white label's posted price equals base × (1 + 0.4 × (start-of-day rating − 0.5)) on every day from 10: 0 misses in 540 chains.

### The royalty enters no decision

Code: as Brand Equity (0.17.0); 0.18.0 adds no reader of `licensing.royalty`, and the prior enters ratings only (`engine/brands.py` `update_brand_ratings`). Replay at seed 300, t100, R at royalty 0.05 and 0.25 against 0.10:

| Speed | Quality | Owner | Royalty | Days identical | Same licensees | Royalties differ | Recompute exact | Pass |
|---|---|---|---|---|---|---|---|---|
| current | contract | s12 | 0.05 | 30/30 | yes | yes | yes | yes |
| current | contract | s12 | 0.25 | 30/30 | yes | yes | yes | yes |
| current | contract | s14 | 0.05 | 30/30 | yes | yes | yes | yes |
| current | contract | s14 | 0.25 | 30/30 | yes | yes | yes | yes |
| current | contract | s46 | 0.05 | 30/30 | yes | yes | yes | yes |
| current | contract | s46 | 0.25 | 30/30 | yes | yes | yes | yes |
| current | cheap | s12 | 0.05 | 30/30 | yes | yes | yes | yes |
| current | cheap | s12 | 0.25 | 30/30 | yes | yes | yes | yes |
| current | cheap | s14 | 0.05 | 30/30 | yes | yes | yes | yes |
| current | cheap | s14 | 0.25 | 30/30 | yes | yes | yes | yes |
| current | cheap | s46 | 0.05 | 30/30 | yes | yes | yes | yes |
| current | cheap | s46 | 0.25 | 30/30 | yes | yes | yes | yes |
| slow15 | contract | s12 | 0.05 | 30/30 | yes | yes | yes | yes |
| slow15 | contract | s12 | 0.25 | 30/30 | yes | yes | yes | yes |
| slow15 | contract | s14 | 0.05 | 30/30 | yes | yes | yes | yes |
| slow15 | contract | s14 | 0.25 | 30/30 | yes | yes | yes | yes |
| slow15 | contract | s46 | 0.05 | 30/30 | yes | yes | yes | yes |
| slow15 | contract | s46 | 0.25 | 30/30 | yes | yes | yes | yes |

Result: **pass**.

J identity: 1980/1980 owner-chains to the cent; largest split residual 0.000000 cents.

## Predictions

$ per owner over days 10–30 (per-seed mean of 3 owners); slopes in $ per day to 0.9. PR1–PR2 confirmatory; the rest exploratory.

| Prediction | Estimate ($) | Verdict |
|---|---|---|
| **PR1**: contract, t40: slope of R − W_g over days to 0.9 ($ per day) | +284.00 [+231.68, +336.32] * | supported |
| **PR2**: contract, t40, current speed: reputation effect − tier effect | −14,323.27 [−17,102.62, −11,543.92] * | supported |
| **PR3**: slow15: contract: reputation effect at t40 − at t100 (exploratory) | +19,197.49 [+15,822.69, +22,572.30] * | supported |
| **PR4 t40**: contract, t40: slope of the owner's gain at 0.10 over days to 0.9 ($ per day) (exploratory) | +19.03 [+0.63, +37.44] * | supported |
| **PR4 t100**: contract, t100: slope of the owner's gain at 0.10 over days to 0.9 ($ per day) (exploratory) | −266.06 [−317.23, −214.89] * | contradicted (interval on the opposite side of 0) |

All reputation and tier effects:

| Effect | Estimate ($) | Interval |
|---|---|---|
| current, contract, t40: reputation effect R − W_g | +247.73 [+172.03, +323.44] * | interval excludes 0 |
| current, contract, t40: tier effect W_g − W_t | +14,571.00 [+11,734.08, +17,407.93] * | interval excludes 0 |
| current, contract, t100: reputation effect R − W_g | +101.37 [+32.32, +170.41] * | interval excludes 0 |
| current, contract, t100: tier effect W_g − W_t | +15,177.20 [+12,201.27, +18,153.14] * | interval excludes 0 |
| current, cheap, t40: reputation effect R − W_g | −824.13 [−1,171.63, −476.64] * | interval excludes 0 |
| current, cheap, t40: tier effect W_g − W_t | +3,323.48 [+2,736.85, +3,910.11] * | interval excludes 0 |
| current, cheap, t100: reputation effect R − W_g | +3,194.65 [+2,567.05, +3,822.25] * | interval excludes 0 |
| current, cheap, t100: tier effect W_g − W_t | +5,499.80 [+4,484.14, +6,515.47] * | interval excludes 0 |
| slow15, contract, t40: reputation effect R − W_g | +4,186.76 [+3,422.24, +4,951.27] * | interval excludes 0 |
| slow15, contract, t100: reputation effect R − W_g | −15,010.73 [−17,656.14, −12,365.33] * | interval excludes 0 |

## Joint profit and its parts

J per owner and its 6 licensees, days 10–30, $.

| Cell | J never | J W_t | J W_g | J R | Composition W_g − never | Tier W_g − W_t | Reputation R − W_g | Name (0.17.0) R − W_t |
|---|---|---|---|---|---|---|---|---|
| current, contract, t40 | −3,716.67 [−4,609.45, −2,823.89] * | +3,096.68 [+1,712.15, +4,481.21] * | +17,667.68 [+14,232.57, +21,102.79] * | +17,915.41 [+14,427.21, +21,403.62] * | +21,384.35 [+17,388.47, +25,380.22] * | +14,571.00 [+11,734.08, +17,407.93] * | +247.73 [+172.03, +323.44] * | +14,818.74 [+11,923.40, +17,714.07] * |
| current, contract, t100 | −6,750.70 [−8,207.17, −5,294.22] * | +3,126.45 [+1,698.51, +4,554.39] * | +18,303.65 [+14,734.21, +21,873.10] * | +18,405.02 [+14,794.91, +22,015.13] * | +25,054.35 [+20,593.46, +29,515.24] * | +15,177.20 [+12,201.27, +18,153.14] * | +101.37 [+32.32, +170.41] * | +15,278.57 [+12,256.37, +18,300.78] * |
| current, cheap, t40 | −3,716.67 [−4,609.45, −2,823.89] * | −16,494.62 [−19,311.61, −13,677.64] * | −13,171.14 [−15,501.93, −10,840.36] * | −13,995.28 [−16,443.73, −11,546.82] * | −9,454.48 [−11,148.89, −7,760.06] * | +3,323.48 [+2,736.85, +3,910.11] * | −824.13 [−1,171.63, −476.64] * | +2,499.35 [+1,999.92, +2,998.78] * |
| current, cheap, t100 | −6,750.70 [−8,207.17, −5,294.22] * | −26,537.73 [−30,840.07, −22,235.40] * | −21,037.93 [−24,436.26, −17,639.59] * | −17,843.28 [−20,680.75, −15,005.81] * | −14,287.23 [−16,841.42, −11,733.04] * | +5,499.80 [+4,484.14, +6,515.47] * | +3,194.65 [+2,567.05, +3,822.25] * | +8,694.45 [+7,138.42, +10,250.48] * |
| slow15, contract, t40 | −3,903.03 [−4,777.28, −3,028.79] * | – | +14,131.17 [+11,612.58, +16,649.76] * | +18,317.93 [+15,088.72, +21,547.14] * | +18,034.20 [+14,765.16, +21,303.25] * | – | +4,186.76 [+3,422.24, +4,951.27] * | – |
| slow15, contract, t100 | −7,062.53 [−8,468.64, −5,656.42] * | – | +21,484.05 [+17,684.05, +25,284.06] * | +6,473.32 [+5,287.94, +7,658.70] * | +28,546.58 [+23,573.58, +33,519.59] * | – | −15,010.73 [−17,656.14, −12,365.33] * | – |

Reputation effect split (R − W_g, $; the parts add up to the effect):

| Cell | Owner own sales | Licensee sales | Licensee prices | Licensee ad spend | Fines |
|---|---|---|---|---|---|
| current, contract, t40 | −9.45 [−34.13, +15.23] | −147.24 [−214.43, −80.04] * | +404.32 [+334.15, +474.48] * | +0.10 [−0.08, +0.28] | +0.00 [+0.00, +0.00] |
| current, contract, t100 | +72.01 [+42.47, +101.56] * | −515.81 [−605.73, −425.89] * | +545.15 [+456.11, +634.20] * | +0.01 [−0.09, +0.11] | +0.00 [+0.00, +0.00] |
| current, cheap, t40 | −2,319.03 [−2,819.41, −1,818.64] * | −542.54 [−675.67, −409.41] * | +2,155.65 [+1,776.04, +2,535.26] * | +2.71 [−0.73, +6.15] | −120.93 [−259.48, +17.61] |
| current, cheap, t100 | +135.29 [−88.04, +358.63] | −969.45 [−1,214.38, −724.52] * | +4,016.41 [+3,296.80, +4,736.02] * | +0.66 [−3.38, +4.71] | +11.73 [−119.09, +142.56] |
| slow15, contract, t40 | −213.36 [−562.34, +135.62] | +1,188.19 [+839.64, +1,536.74] * | +3,211.06 [+2,652.04, +3,770.07] * | +0.87 [−0.12, +1.86] | +0.00 [+0.00, +0.00] |
| slow15, contract, t100 | +72.00 [−109.26, +253.25] | −16,252.05 [−19,093.65, −13,410.46] * | +1,168.75 [+965.31, +1,372.19] * | +0.57 [−0.71, +1.84] | +0.00 [+0.00, +0.00] |

Units and prices, days 10–30:

| Cell | Licensee units never / W_t / W_g / R | Licensee mean price W_t / W_g / R ($) | Owner units never / W_t / W_g / R |
|---|---|---|---|
| current, contract, t40 | 245.6 / 962.9 / 671.4 / 664.6 | 43.25 / 64.86 / 65.49 | 148.1 / 66.8 / 94.7 / 94.7 |
| current, contract, t100 | 339.0 / 984.1 / 703.1 / 681.1 | 43.27 / 64.65 / 65.49 | 135.7 / 64.0 / 92.9 / 95.8 |
| current, cheap, t40 | 245.6 / 298.7 / 290.6 / 261.8 | 32.84 / 44.37 / 52.61 | 148.1 / 147.0 / 146.8 / 110.0 |
| current, cheap, t100 | 339.0 / 505.7 / 495.9 / 446.7 | 33.32 / 44.27 / 53.25 | 135.7 / 117.6 / 117.7 / 232.1 |
| slow15, contract, t40 | 216.3 / – / 653.0 / 712.5 | – / 60.10 / 64.59 | 163.8 / – / 119.2 / 109.6 |
| slow15, contract, t100 | 337.6 / – / 1066.6 / 335.5 | – / 60.63 / 64.30 | 136.9 / – / 42.1 / 48.0 |

## Owner's gain and licensee profit by royalty

Owner's gain = owner's 30-day profit − never at the same speed. R by the exact recompute; white labels pay no royalty. Licensee profit: per licensee, days 10–30.

| Cell | Owner gain R, 0.05 | Owner gain R, 0.10 | Owner gain R, 0.15 | Owner gain R, 0.25 | Owner gain W_g | Owner gain W_t |
|---|---|---|---|---|---|---|
| current, contract, t40 | +744.97 [+475.39, +1,014.55] * | +2,980.27 [+2,393.10, +3,567.44] * | +5,215.57 [+4,217.00, +6,214.13] * | +9,686.16 [+7,830.73, +11,541.59] * | −1,480.88 [−1,891.76, −1,069.99] * | −2,186.62 [−2,634.26, −1,738.98] * |
| current, contract, t100 | +1,164.05 [+821.61, +1,506.49] * | +3,458.91 [+2,760.78, +4,157.04] * | +5,753.76 [+4,628.81, +6,878.71] * | +10,343.47 [+8,332.04, +12,354.90] * | −1,202.81 [−1,582.83, −822.80] * | −1,929.81 [−2,321.57, −1,538.04] * |
| current, cheap, t40 | −1,668.72 [−2,085.41, −1,252.03] * | −973.83 [−1,307.43, −640.23] * | −278.98 [−560.31, +2.34] | +1,110.80 [+786.14, +1,435.47] * | −44.59 [−111.70, +22.53] | −40.80 [−107.96, +26.36] |
| current, cheap, t100 | +835.16 [+536.64, +1,133.68] * | +2,037.36 [+1,594.70, +2,480.03] * | +3,239.61 [+2,607.13, +3,872.10] * | +5,643.96 [+4,595.08, +6,692.83] * | −502.30 [−640.37, −364.22] * | −502.65 [−643.74, −361.56] * |
| slow15, contract, t40 | +942.03 [+570.00, +1,314.07] * | +3,244.28 [+2,599.53, +3,889.02] * | +5,546.36 [+4,538.41, +6,554.32] * | +10,150.96 [+8,366.17, +11,935.76] * | −1,147.24 [−1,370.03, −924.44] * | – |
| slow15, contract, t100 | −1,263.87 [−1,547.24, −980.49] * | −231.37 [−430.49, −32.24] * | +801.22 [+546.79, +1,055.65] * | +2,866.32 [+2,307.74, +3,424.89] * | −2,368.59 [−2,767.79, −1,969.40] * | – |

| Cell | Licensee profit never | W_t | W_g | R, 0.05 | R, 0.10 | R, 0.15 | R, 0.25 |
|---|---|---|---|---|---|---|---|
| current, contract, t40 | −1,231.13 [−1,460.02, −1,002.25] * | +268.86 [+65.73, +472.00] * | +2,579.74 [+2,064.80, +3,094.67] * | +2,250.05 [+1,797.20, +2,702.90] * | +1,877.50 [+1,496.23, +2,258.77] * | +1,504.95 [+1,194.76, +1,815.15] * | +759.86 [+587.74, +931.97] * |
| current, contract, t100 | −1,679.14 [−1,984.33, −1,373.94] * | +288.69 [+74.45, +502.93] * | +2,697.06 [+2,157.91, +3,236.20] * | +2,319.47 [+1,848.76, +2,790.19] * | +1,937.00 [+1,540.46, +2,333.53] * | +1,554.52 [+1,231.66, +1,877.38] * | +789.57 [+610.02, +969.13] * |
| current, cheap, t40 | −1,231.13 [−1,460.02, −1,002.25] * | −3,353.99 [−3,923.61, −2,784.37] * | −2,799.45 [−3,284.41, −2,314.48] * | −2,666.11 [−3,125.79, −2,206.44] * | −2,781.93 [−3,260.52, −2,303.34] * | −2,897.74 [−3,395.37, −2,400.10] * | −3,129.37 [−3,665.41, −2,593.33] * |
| current, cheap, t100 | −1,679.14 [−1,984.33, −1,373.94] * | −4,893.20 [−5,688.44, −4,097.96] * | −3,976.63 [−4,619.46, −3,333.79] * | −3,667.09 [−4,253.23, −3,080.96] * | −3,867.46 [−4,488.39, −3,246.53] * | −4,067.84 [−4,723.78, −3,411.90] * | −4,468.56 [−5,195.04, −3,742.08] * |
| slow15, contract, t40 | −1,278.03 [−1,523.31, −1,032.75] * | – | +1,918.88 [+1,574.90, +2,262.86] * | +2,268.46 [+1,864.38, +2,672.54] * | +1,884.75 [+1,546.29, +2,223.22] * | +1,501.07 [+1,227.57, +1,774.57] * | +733.64 [+584.61, +882.66] * |
| slow15, contract, t100 | −1,679.42 [−1,984.70, −1,374.14] * | – | +3,473.11 [+2,860.00, +4,086.22] * | +787.20 [+637.40, +937.00] * | +615.12 [+494.22, +736.02] * | +443.02 [+350.18, +535.86] * | +98.84 [+53.01, +144.66] * |

## Rating speed

Days from day 10 (= 1) until a W_g white label's rating first reaches 0.9 (mean over those that reach it), the share that reach it by day 30, and the owner's own rating at the end of day 10 in the never chain.

| Cell | Days to 0.9 | Share reaching 0.9 | Owner rating day 10 (never) |
|---|---|---|---|
| current, contract, t40 | 1.0 [1.0, 1.0] | 1.00 [1.00, 1.00] | 1.000 [1.000, 1.000] |
| current, contract, t100 | 1.0 [1.0, 1.0] | 1.00 [1.00, 1.00] | 1.000 [1.000, 1.000] |
| current, cheap, t40 | – | 0.00 [0.00, 0.00] | 1.000 [1.000, 1.000] |
| current, cheap, t100 | – | 0.00 [0.00, 0.00] | 1.000 [1.000, 1.000] |
| slow15, contract, t40 | 15.0 [15.0, 15.1] | 1.00 [1.00, 1.00] | 0.802 [0.798, 0.806] |
| slow15, contract, t100 | 14.0 [13.9, 14.0] | 1.00 [1.00, 1.00] | 0.776 [0.772, 0.780] |

Rating paths: mean over owners (unrated = 0.5), end of days 1, 5, 9, 10, 12, 15, 20, 25, 30.

| Cell | Series | 1 | 5 | 9 | 10 | 12 | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|---|---|---|---|---|
| current, contract, t40 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t40 | owner brand, R | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t40 | owner brand, W_g | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t40 | white labels, W_g | 0.509 | 0.547 | 0.583 | 0.985 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t40 | white labels, W_t | 0.509 | 0.547 | 0.583 | 0.983 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t100 | owner, never | 0.994 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t100 | owner brand, R | 0.994 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t100 | owner brand, W_g | 0.994 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t100 | white labels, W_g | 0.540 | 0.594 | 0.621 | 0.996 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t100 | white labels, W_t | 0.540 | 0.594 | 0.621 | 0.996 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, cheap, t40 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, cheap, t40 | owner brand, R | 1.000 | 1.000 | 1.000 | 0.824 | 0.615 | 0.446 | 0.302 | 0.255 | 0.256 |
| current, cheap, t40 | owner brand, W_g | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, cheap, t40 | white labels, W_g | 0.509 | 0.547 | 0.583 | 0.152 | 0.020 | 0.003 | 0.000 | 0.000 | 0.000 |
| current, cheap, t40 | white labels, W_t | 0.509 | 0.547 | 0.583 | 0.139 | 0.008 | 0.001 | 0.000 | 0.000 | 0.000 |
| current, cheap, t100 | owner, never | 0.994 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, cheap, t100 | owner brand, R | 0.994 | 1.000 | 1.000 | 0.801 | 0.581 | 0.429 | 0.361 | 0.348 | 0.351 |
| current, cheap, t100 | owner brand, W_g | 0.994 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, cheap, t100 | white labels, W_g | 0.540 | 0.594 | 0.621 | 0.114 | 0.012 | 0.004 | 0.001 | 0.000 | 0.000 |
| current, cheap, t100 | white labels, W_t | 0.540 | 0.594 | 0.621 | 0.115 | 0.010 | 0.000 | 0.000 | 0.000 | 0.000 |
| slow15, contract, t40 | owner, never | 0.566 | 0.629 | 0.766 | 0.802 | 0.864 | 0.931 | 0.981 | 0.995 | 0.999 |
| slow15, contract, t40 | owner brand, R | 0.566 | 0.629 | 0.766 | 0.828 | 0.908 | 0.965 | 0.993 | 0.999 | 1.000 |
| slow15, contract, t40 | owner brand, W_g | 0.566 | 0.629 | 0.766 | 0.794 | 0.849 | 0.918 | 0.974 | 0.993 | 0.999 |
| slow15, contract, t40 | white labels, W_g | 0.500 | 0.507 | 0.531 | 0.544 | 0.560 | 0.617 | 0.796 | 0.926 | 0.978 |
| slow15, contract, t100 | owner, never | 0.562 | 0.616 | 0.742 | 0.776 | 0.839 | 0.916 | 0.976 | 0.994 | 0.999 |
| slow15, contract, t100 | owner brand, R | 0.562 | 0.616 | 0.742 | 0.808 | 0.887 | 0.951 | 0.989 | 0.998 | 1.000 |
| slow15, contract, t100 | owner brand, W_g | 0.562 | 0.616 | 0.742 | 0.751 | 0.781 | 0.845 | 0.935 | 0.975 | 0.992 |
| slow15, contract, t100 | white labels, W_g | 0.499 | 0.510 | 0.542 | 0.573 | 0.592 | 0.664 | 0.834 | 0.945 | 0.985 |

## Never chains across speeds

The prior reaches every brand. Whole-market 30-day profit by stall type ($, all stalls of the type), catches, the sampled owners' mean 30-day profit, and mean rating of rated brands by type (days 10 and 30). Differences from the current speed, same seeds.

| Never chain | Genuine profit | Seconds profit | Deceptive profit | Catches | Owner profit | Rating genuine d10 / d30 | Rating seconds d10 / d30 | Rating deceptive d10 / d30 |
|---|---|---|---|---|---|---|---|---|
| current, t40 | 95,262.21 [94,199.67, 96,324.75] | −2,972.68 [−3,304.14, −2,641.23] | −49,213.12 [−51,008.33, −47,417.91] | 943 [926, 961] | 5,161.61 [4,174.06, 6,149.17] | 1.000 / 1.000 | 1.000 / 1.000 | 0.000 / 0.000 |
| current, t100 | 85,908.80 [84,802.87, 87,014.74] | −2,957.58 [−3,291.82, −2,623.35] | −68,200.61 [−70,515.88, −65,885.35] | 1444 [1432, 1455] | 4,697.97 [3,783.23, 5,612.71] | 1.000 / 1.000 | 1.000 / 1.000 | 0.000 / 0.000 |
| slow15, t40 | 89,942.37 [88,929.86, 90,954.89] | −6,096.55 [−6,343.07, −5,850.02] | −48,241.98 [−50,034.21, −46,449.75] | 942 [924, 959] | 4,922.06 [4,065.76, 5,778.35] | 0.802 / 0.999 | 0.605 / 0.945 | 0.470 / 0.469 |
| slow15, t100 | 73,636.34 [72,604.88, 74,667.79] | −4,441.96 [−4,734.09, −4,149.83] | −67,818.28 [−69,962.75, −65,673.81] | 1443 [1431, 1455] | 3,953.79 [3,274.41, 4,633.16] | 0.775 / 0.999 | 0.633 / 0.962 | 0.454 / 0.453 |

| Difference | Genuine profit | Seconds profit | Deceptive profit | Catches | Owner profit |
|---|---|---|---|---|---|
| slow15 − current, t40 | −5,319.84 [−5,817.94, −4,821.74] * | −3,123.86 [−3,273.75, −2,973.97] * | +971.13 [+304.97, +1,637.29] * | −2 [−7, +3] | −239.56 [−681.65, +202.53] |
| slow15 − current, t100 | −12,272.47 [−12,746.95, −11,797.99] * | −1,484.38 [−1,557.92, −1,410.84] * | +382.33 [−1,019.44, +1,784.11] | −0 [−6, +6] | −744.19 [−1,203.62, −284.76] * |

## Buyers by profile, R − W_g (exploratory)

Days 10–30. Shortfall in points of purchases; surplus in $ per buyer of the profile.

| Cell | tourist: shortfall (pts) | local: shortfall (pts) | expert: shortfall (pts) | tourist: surplus ($) | local: surplus ($) | expert: surplus ($) |
|---|---|---|---|---|---|---|
| current, contract, t40 | +0.1 [+0.1, +0.1] * | −0.0 [−0.0, +0.0] | +0.0 [+0.0, +0.0] | −0.24 [−0.28, −0.20] * | −0.12 [−0.14, −0.10] * | −0.08 [−0.10, −0.06] * |
| current, contract, t100 | +0.1 [+0.0, +0.1] * | – | – | −0.22 [−0.26, −0.18] * | – | – |
| current, cheap, t40 | −1.3 [−1.6, −1.1] * | +0.5 [+0.5, +0.6] * | +0.0 [+0.0, +0.0] | −0.32 [−0.44, −0.20] * | −0.29 [−0.36, −0.22] * | −0.06 [−0.08, −0.04] * |
| current, cheap, t100 | −1.1 [−1.2, −1.0] * | – | – | +0.01 [−0.06, +0.09] | – | – |
| slow15, contract, t40 | +0.2 [+0.1, +0.3] * | +0.0 [−0.0, +0.0] | +0.0 [+0.0, +0.0] | −1.40 [−1.63, −1.17] * | −0.96 [−1.14, −0.78] * | −0.75 [−0.89, −0.62] * |
| slow15, contract, t100 | +0.2 [+0.0, +0.3] * | – | – | −1.38 [−1.64, −1.12] * | – | – |

## Stuck, parked and idle buyers

| Chains | Count | Buyer-days | Stuck | Parked | Idle choosers | Invalid actions |
|---|---|---|---|---|---|---|
| R · cheap · t100 · p0 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| R · cheap · t40 · p0 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| R · contract · t100 · p0 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| R · contract · t100 · p50 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| R · contract · t40 · p0 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| R · contract · t40 · p50 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| Wg · cheap · t100 · p0 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| Wg · cheap · t40 · p0 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| Wg · contract · t100 · p0 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| Wg · contract · t100 · p50 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| Wg · contract · t40 · p0 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| Wg · contract · t40 · p50 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| Wt · cheap · t100 · p0 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| Wt · cheap · t40 · p0 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| Wt · contract · t100 · p0 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| Wt · contract · t40 · p0 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| never · - · t100 · p0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| never · - · t100 · p50 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| never · - · t40 · p0 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| never · - · t40 · p50 | 30 | 135,000 | 0 | 0 | 0 | 0 |

## Flags

- none

## Reading (written after the results)

- **Both confirmatory predictions are supported. Of the exploratory ones, PR3 is supported in sign but not by the mechanism it names, PR4 is supported at t40 and contradicted at t100. At the current speed a reputation earns almost nothing once a white label may price like the owner. When reputations form slowly it earns about $4,200 per owner with buyers who read ratings, and costs about $15,000 when no buyer reads them.**
  - **PR2:** contract, t40, current speed: the reputation effect is +$248 [+172, +323] and the tier effect +$14,571 [+11,734, +17,408]. The difference is −$14,323 [−17,103, −11,544]. Of the 0.17.0 name effect (+$14,819), the owner's reputation accounts for about 2% and the stall-type tier for the rest.
  - **PR1:** contract, t40: the reputation effect is +$248 at 1.0 day to 0.9 and +$4,187 [+3,422, +4,951] at 14.9 days. The slope is +$284 [+232, +336] per day. It is fitted over two levels, not three (see Caveats).
  - **PR3:** slow15, contract: the reputation effect is +$4,187 at t40 and −$15,011 [−17,656, −12,365] at t100, a difference of +$19,197 [+15,823, +22,572]. About three quarters of it is the t100 loss.
  - **PR4:** the owner's gain at royalty 0.10 rises from +$2,980 to +$3,244 at t40 (slope +$19 [+1, +37] per day; the interval only just excludes 0). At t100 it falls from +$3,459 to −$231 [−430, −32] (slope −$266 [−317, −215]).
- **With slow ratings, a white label's low rating is a low price, and only buyers who read ratings punish it.** Tourists see no ratings and buy the cheapest candidate (`agents/rule_based.py`, `act_search`). Locals and experts rank by rating first. The mechanism below is read from the frozen tables and the buyer rule; it was not separately tested.
  - At the slow speed a white label's rating stays near 0.5–0.6 until about day 15 and reaches 0.9 around day 24. Its premium price is correspondingly low: $60.1–60.6 mean against R licensees' $64.3–64.6, which carry the owner's 0.8–1.0 rating.
  - At t40, 60% of buyers read ratings, prefer the owner's brand, and R licensees sell more (713 units against 653) at higher prices. The licensee-price part is +$3,211 and the licensee-sales part +$1,188.
  - At t100 no buyer reads ratings, so the cheap white labels win on price. W_g licensees sell 1,067 units against R's 336, which is no more than these stalls sold before licensing (338). The licensee-sales part is −$16,252.
  - At the current speed the gap closes on day 10: white labels rate 0.98–1.00 at the end of their first day, post the owner's price within a day, and the reputation effect is small at both t40 (+$248) and t100 (+$101).
- **The rise in PR1 comes mostly from the white labels doing worse, not the owner's brand doing better.** These are point estimates across speeds, without intervals. From current to slow15 (contract, t40), J(W_g) falls by about $3,540 (+$17,668 to +$14,131) and J(R) rises by about $400 (+$17,915 to +$18,318).
- **PR3's direction holds, but its stated mechanism covers only the smaller part.** Buyers who read ratings do make the name pay at the slow speed (+$4,187 at t40 against +$248 at the current speed). The larger part of the t40 − t100 difference is the t100 loss, where no buyer reads ratings and the owner's high rating only raises the licensees' price.
- **Contract licensees would rather be white labels at the current speed.** At t40 each earns +$2,580 as a white label at the genuine tier against +$2,250 under R at royalty 0.05 and +$1,878 at 0.10. In 0.17.0, with white labels at their type's tier (+$269), R was preferred at every royalty. At slow15, t40 the two are about equal at 0.10 (+$1,885 R, +$1,919 W_g). At slow15, t100, white labels earn +$3,473 against +$615 under R.
- **The owner still gains from licensing its brand, except with slow ratings and no rating readers.**
  - Owner's gain under R at 0.10: +$2,980 (current, t40), +$3,459 (current, t100), +$3,244 (slow15, t40), −$231 (slow15, t100).
  - White labels cost the owner money in every cell (−$1,147 to −$2,369), because they take the owner's buyers without paying a royalty.
- **Slow ratings change the whole market, not only the licensees** (never chains, slow15 − current). Genuine stalls earn $5,320 [4,822, 5,818] less at t40 and $12,272 [11,798, 12,747] less at t100, because they price from ratings of 0.78–0.80 instead of 1.0 at day 10. Seconds-type stalls earn $3,124 less at t40. New deceptive brands hold a rating near 0.47 instead of falling to 0, and deceptive stalls earn +$971 [+305, +1,637] more at t40. Catches do not change.
- **Cheap licensees at the current speed** (exploratory). The reputation effect is −$824 [−1,172, −477] at t40, where the owner's brand falls to a rating of 0.26 and the owner's own sales part is −$2,319. It is +$3,195 [+2,567, +3,822] at t100, where R licensees price from the owner's fallen 0.35 rating against white labels at 0. The tier effect is +$3,323 and +$5,500.
- **Buyers pay for the name mostly when reputations are slow.** Per buyer, R − W_g surplus is −$0.08 to −$0.24 at the current speed (contract) and −$0.75 to −$1.40 at slow15.

## Caveats

- **Two speeds, not three.** The pilot projected 6.10 h for three levels, above the 5.5 h limit, so the 5-day level (prior_n 2.5) was cut before any seed, as the spec directs. PR1 says "three levels", but its slope, and PR4's, are fitted over two: 1.04 and 14.91 days to 0.9. A two-point slope is the difference divided by the days. It cannot show whether the effect grows steadily, has a threshold, or levels off. The calibration found the dial steep at the low end, with the 5-day level spread from 1 to 9 days across labels.
- **The prior slows every brand, not only the white label.** At slow15 the owner's own rating is 0.80 at the end of day 10 (1.00 at the current speed). Rival genuine brands are slowed too, and new deceptive brands hold near 0.47 instead of falling to 0. "Time to reputation" therefore changes the whole market. Each effect is compared within its own speed as specified, but the slow-speed reputation effect is measured in a slower market, not with only the licensee slowed.
- **The 30-day horizon truncates the slow arm.** At slow15 a white label reaches 0.9 around day 24 (14–15 days after day 10), leaving about 6 days at a full reputation. Over a longer market the gap between R and W_g would likely shrink at both t40 and t100. Untested.
- **t100 means no buyer reads ratings.** Tourists see no ratings (`ratings.visible_to`), so at t100 ratings act only through the premium in the posted price. The t100 results, PR3 and PR4 at t100 among them, describe a market where reputation can only raise a price. The account of the mechanism in the reading is inferred from the frozen tables and the buyer rule, not tested separately.
- **The price rule is mechanical.** White labels and licensees post base × (1 + 0.4 × (rating − 0.5)) at the genuine tier, from the start-of-day rating (checked: 0 misses in 540 chains). No stall chooses its price. A white label that priced up to the owner's level, or an owner that cut its premium, is not modelled.
- **Days to 0.9 in the run differ slightly from the calibration.** At slow15 they are 15.0 at t40 and 14.0 at t100, against the calibration's 14.91 (t40). The slopes use the calibration's values as specified. With the run's own t40 value, PR1's slope would be about +$281 instead of +$284.
- **Cheap licensees were run only at the current speed,** by design, so nothing here says how rating speed interacts with cheap quality.
- **One option and one market,** as in Brand Equity: N = 6 from day 10, owner not liable, detect_scale 1, premium 0.4, memory 0.7. The royalty affects no decision (replay passed in 18 of 18 checks, including the slow speed), so the owner's gain at other royalty rates is an exact recompute within this option.
- **Load.** Other work kept the machine's load average at 6–9 throughout the run (4 workers, nice 19). This affects the wall clock only. Chains are deterministic, and the 0.17.0 identity (780/780) and J identity (1,980/1,980) hold.
- 95% intervals over 30 seeds (the per-seed mean of 3 owners), unadjusted. Only PR1 and PR2 are confirmatory. Every other row, including PR3, PR4 and the reading's figures, is exploratory.
