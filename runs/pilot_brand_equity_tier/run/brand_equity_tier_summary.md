# Brand Equity at the genuine tier, with rating speed

Spec: `runs/plan_brand_equity_tier.md` (2026-11-13) and the addendum "rating speed as a factor" (2026-11-16); predictions fixed 2026-11-16, before any run. Calibration: `runs/calibration_rating_speed.md`. Pilot gate: `runs/pilot_brand_equity_tier.md`.

## Design (prespecified)

- Question: what does a reputation earn once a white label may price like the owner, and does it earn more when reputations form slowly?
- Engine 0.18.0. Market, owners and licence option as Brand Equity: the licensing market, detect_scale 1, owner not liable; 3 owners per seed from `default_rng([seed, 17])`; N 6 from day 10, royalty 0.10.
- Arms per owner: never; R (licensees under the owner's brand); W_g (the same stalls under white labels at the genuine tier, `licensing.white_label_tier` genuine); W_t (white labels at their stall type's tier, the 0.17.0 W).
- Rating speed: `ratings.prior_n` (every brand starts with prior_n pseudo-reviews at 0.5, counted in each day's share and fading by memory 0.7 per day). Levels from the calibration (days for a fresh contract white label to reach a 0.9 rating, t40): current: prior_n 0, 1.0 days; slow5: prior_n 2.5, 4.8 days; slow15: prior_n 50, 14.9 days.
- Current speed: never, R, W_g, W_t × {contract, cheap} × {t40, t100}. Slow speeds: never, R, W_g × contract × {t40, t100}. Seeds 300–329, paired; everything rerun at 0.18.0. Extra gate: at current speed, never, R and W_t equal the 0.17.0 Brand Equity chains to the cent.
- Measures, per owner: J = owner + 6 licensees' profit, days 10–30. Reputation effect = J(R) − J(W_g), split into owner own sales, licensee sales, licensee prices, licensee ad spend and fines. Tier effect = J(W_g) − J(W_t) (current speed); the 0.17.0 name effect J(R) − J(W_t) = reputation + tier. Composition = J(W_g) − J(never). Each effect is compared within its own speed; never chains are reported across speeds. Owner's gain at 0.05–0.25 by the exact recompute after the no-decision check.
- Predictions (verbatim from the spec):
  - PR1 (confirmatory): contract, t40: the reputation effect rises with time to reputation. Slope of R − W_g over days-to-0.9 (three levels) > 0.
  - PR2 (confirmatory): contract, t40, current speed: reputation effect < tier effect.
  - PR3 (exploratory): at the slowest speed, the reputation effect at t40 − at t100 > 0 (buyers who read ratings become the channel once reputations are slow).
  - PR4 (exploratory): the owner's gain at royalty 0.10 rises with time to reputation.
- Analysis: per seed the mean over 3 owners; mean and 95% t over seeds; unadjusted. Slopes (PR1, PR4) fitted per seed by least squares over the calibration's days to 0.9, then averaged; PR4 in contract at t40 and at t100.

## Run record

- Engine `0.18.0`; commit `7e77afd2c9ba61fa72ba7716e01e89d60b3930b4`; uncommitted at run time: ['?? runs/pilot_brand_equity_tier/', '?? runs/pilot_brand_equity_tier_stdout.log']
- Script sha256 `3fb3a6de30b5a7af2a32e024f40e15b54766605224bb698ca347bce71b030778`
- Command: `python -m analysis.brand_equity_tier --tests 1261 passed, 17 skipped at 20ee303 (runs/tests_0180.log)`
- Tests: 1261 passed, 17 skipped at 20ee303 (runs/tests_0180.log)
- Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit
- 216 chains × 30 days on 4 workers (nice 19); wall clock 0.66 h; load average [4.11, 4.98, 5.71] at start, [7.17, 8.03, 8.05] at end; memory at start {'swap_free_mb': 794.19, 'free_pct': 70}, at end {'swap_free_mb': 818.19, 'free_pct': 71}; memory-guard pauses: 0
- Seeds 900-902 (3), paired
- Sampled owners per seed: 900: s14, s27, s41; 901: s33, s32, s09; 902: s29, s45, s44

## Gate

pilot (this is the pilot)

0.17.0 identity (current speed never, R and W_t against `runs/pilot_canal_equity/equity/brand_equity_cache.jsonl`, full-outcome digest and every ledger to the cent): 78/78 chains equal.

Genuine-tier prices: every W_g white label's posted price equals base × (1 + 0.4 × (start-of-day rating − 0.5)) on every day from 10: 0 misses in 72 chains.

### The royalty enters no decision

Code: as Brand Equity (0.17.0); 0.18.0 adds no reader of `licensing.royalty`, and the prior enters ratings only (`engine/brands.py` `update_brand_ratings`). Replay at seed 900, t100, R at royalty 0.05 and 0.25 against 0.10:

| Speed | Quality | Owner | Royalty | Days identical | Same licensees | Royalties differ | Recompute exact | Pass |
|---|---|---|---|---|---|---|---|---|
| current | contract | s14 | 0.05 | 30/30 | yes | yes | yes | yes |
| current | contract | s14 | 0.25 | 30/30 | yes | yes | yes | yes |
| current | contract | s27 | 0.05 | 30/30 | yes | yes | yes | yes |
| current | contract | s27 | 0.25 | 30/30 | yes | yes | yes | yes |
| current | contract | s41 | 0.05 | 30/30 | yes | yes | yes | yes |
| current | contract | s41 | 0.25 | 30/30 | yes | yes | yes | yes |
| current | cheap | s14 | 0.05 | 30/30 | yes | yes | yes | yes |
| current | cheap | s14 | 0.25 | 30/30 | yes | yes | yes | yes |
| current | cheap | s27 | 0.05 | 30/30 | yes | yes | yes | yes |
| current | cheap | s27 | 0.25 | 30/30 | yes | yes | yes | yes |
| current | cheap | s41 | 0.05 | 30/30 | yes | yes | yes | yes |
| current | cheap | s41 | 0.25 | 30/30 | yes | yes | yes | yes |
| slow15 | contract | s14 | 0.05 | 30/30 | yes | yes | yes | yes |
| slow15 | contract | s14 | 0.25 | 30/30 | yes | yes | yes | yes |
| slow15 | contract | s27 | 0.05 | 30/30 | yes | yes | yes | yes |
| slow15 | contract | s27 | 0.25 | 30/30 | yes | yes | yes | yes |
| slow15 | contract | s41 | 0.05 | 30/30 | yes | yes | yes | yes |
| slow15 | contract | s41 | 0.25 | 30/30 | yes | yes | yes | yes |

Result: **pass**.

J identity: 252/252 owner-chains to the cent; largest split residual 0.000000 cents.

## Predictions

$ per owner over days 10–30 (per-seed mean of 3 owners); slopes in $ per day to 0.9. PR1–PR2 confirmatory; the rest exploratory.

| Prediction | Estimate ($) | Verdict |
|---|---|---|
| **PR1**: contract, t40: slope of R − W_g over days to 0.9 ($ per day) | +366.79 [+18.65, +714.93] * | supported |
| **PR2**: contract, t40, current speed: reputation effect − tier effect | −20,721.63 [−33,870.47, −7,572.78] * | supported |
| **PR3**: slow15: contract: reputation effect at t40 − at t100 (exploratory) | +26,957.71 [+7,902.05, +46,013.37] * | supported |
| **PR4 t40**: contract, t40: slope of the owner's gain at 0.10 over days to 0.9 ($ per day) (exploratory) | +40.11 [−207.77, +287.98] | not supported (interval includes 0) |
| **PR4 t100**: contract, t100: slope of the owner's gain at 0.10 over days to 0.9 ($ per day) (exploratory) | −305.30 [−527.82, −82.77] * | contradicted (interval on the opposite side of 0) |

All reputation and tier effects:

| Effect | Estimate ($) | Interval |
|---|---|---|
| current, contract, t40: reputation effect R − W_g | +268.49 [−385.83, +922.81] | interval includes 0 |
| current, contract, t40: tier effect W_g − W_t | +20,990.12 [+7,439.54, +34,540.71] * | interval excludes 0 |
| current, contract, t100: reputation effect R − W_g | −32.32 [−498.05, +433.41] | interval includes 0 |
| current, contract, t100: tier effect W_g − W_t | +21,656.80 [+7,234.41, +36,079.20] * | interval excludes 0 |
| current, cheap, t40: reputation effect R − W_g | −220.51 [−2,965.19, +2,524.17] | interval includes 0 |
| current, cheap, t40: tier effect W_g − W_t | +5,598.25 [+1,838.70, +9,357.79] * | interval excludes 0 |
| current, cheap, t100: reputation effect R − W_g | +5,194.40 [−2,560.16, +12,948.96] | interval includes 0 |
| current, cheap, t100: tier effect W_g − W_t | +8,503.71 [+3,524.75, +13,482.66] * | interval excludes 0 |
| slow5, contract, t40: reputation effect R − W_g | +3,779.70 [−1,459.55, +9,018.96] | interval includes 0 |
| slow5, contract, t100: reputation effect R − W_g | −23,505.12 [−38,284.53, −8,725.72] * | interval excludes 0 |
| slow15, contract, t40: reputation effect R − W_g | +5,925.46 [−226.21, +12,077.14] | interval includes 0 |
| slow15, contract, t100: reputation effect R − W_g | −21,032.24 [−33,941.00, −8,123.49] * | interval excludes 0 |

## Joint profit and its parts

J per owner and its 6 licensees, days 10–30, $.

| Cell | J never | J W_t | J W_g | J R | Composition W_g − never | Tier W_g − W_t | Reputation R − W_g | Name (0.17.0) R − W_t |
|---|---|---|---|---|---|---|---|---|
| current, contract, t40 | −4,625.48 [−13,613.03, +4,362.08] | +2,167.61 [−6,135.79, +10,471.01] | +23,157.73 [+2,744.02, +43,571.45] * | +23,426.23 [+2,472.32, +44,380.14] * | +27,783.21 [+3,075.23, +52,491.19] * | +20,990.12 [+7,439.54, +34,540.71] * | +268.49 [−385.83, +922.81] | +21,258.61 [+7,287.18, +35,230.05] * |
| current, contract, t100 | −9,079.20 [−17,586.98, −571.43] * | +1,990.81 [−7,256.30, +11,237.93] | +23,647.62 [+1,649.35, +45,645.88] * | +23,615.30 [+1,199.56, +46,031.04] * | +32,726.82 [+5,484.72, +59,968.93] * | +21,656.80 [+7,234.41, +36,079.20] * | −32.32 [−498.05, +433.41] | +21,624.48 [+6,861.88, +36,387.09] * |
| current, cheap, t40 | −4,625.48 [−13,613.03, +4,362.08] | −23,943.79 [−37,983.11, −9,904.47] * | −18,345.55 [−30,334.55, −6,356.54] * | −18,566.06 [−30,663.00, −6,469.12] * | −13,720.07 [−23,719.96, −3,720.18] * | +5,598.25 [+1,838.70, +9,357.79] * | −220.51 [−2,965.19, +2,524.17] | +5,377.73 [+3,425.19, +7,330.27] * |
| current, cheap, t100 | −9,079.20 [−17,586.98, −571.43] * | −38,569.80 [−62,930.25, −14,209.36] * | −30,066.10 [−49,967.49, −10,164.70] * | −24,871.70 [−41,584.40, −8,158.99] * | −20,986.89 [−39,288.56, −2,685.22] * | +8,503.71 [+3,524.75, +13,482.66] * | +5,194.40 [−2,560.16, +12,948.96] | +13,698.10 [+4,088.19, +23,308.02] * |
| slow5, contract, t40 | −4,916.27 [−10,037.19, +204.64] | – | +22,884.86 [+9,110.23, +36,659.49] * | +26,664.57 [+7,809.38, +45,519.75] * | +27,801.13 [+10,557.65, +45,044.62] * | – | +3,779.70 [−1,459.55, +9,018.96] | – |
| slow5, contract, t100 | −8,633.08 [−14,346.50, −2,919.66] * | – | +35,861.72 [+12,748.10, +58,975.34] * | +12,356.60 [+3,992.61, +20,720.59] * | +44,494.81 [+18,336.07, +70,653.55] * | – | −23,505.12 [−38,284.53, −8,725.72] * | – |
| slow15, contract, t40 | −4,601.13 [−7,073.55, −2,128.71] * | – | +20,054.57 [+8,291.34, +31,817.79] * | +25,980.03 [+8,279.82, +43,680.24] * | +24,655.70 [+10,865.10, +38,446.30] * | – | +5,925.46 [−226.21, +12,077.14] | – |
| slow15, contract, t100 | −8,882.76 [−14,105.14, −3,660.39] * | – | +30,905.37 [+10,806.40, +51,004.34] * | +9,873.13 [+2,105.92, +17,640.33] * | +39,788.13 [+15,378.53, +64,197.74] * | – | −21,032.24 [−33,941.00, −8,123.49] * | – |

Reputation effect split (R − W_g, $; the parts add up to the effect):

| Cell | Owner own sales | Licensee sales | Licensee prices | Licensee ad spend | Fines |
|---|---|---|---|---|---|
| current, contract, t40 | +42.44 [−229.39, +314.28] | −371.31 [−661.18, −81.44] * | +597.28 [−104.49, +1,299.05] | +0.08 [−1.05, +1.22] | +0.00 [+0.00, +0.00] |
| current, contract, t100 | +88.69 [−211.66, +389.04] | −901.72 [−1,324.17, −479.28] * | +781.18 [−100.95, +1,663.30] | −0.47 [−1.71, +0.78] | +0.00 [+0.00, +0.00] |
| current, cheap, t40 | −2,750.81 [−5,328.57, −173.05] * | −982.33 [−3,016.91, +1,052.24] | +2,922.78 [+1,348.85, +4,496.71] * | +3.19 [−29.59, +35.97] | +586.67 [−983.45, +2,156.78] |
| current, cheap, t100 | +692.07 [−520.10, +1,904.24] | −1,399.02 [−5,079.56, +2,281.52] | +5,610.09 [+2,129.13, +9,091.06] * | −14.08 [−57.17, +29.02] | +305.33 [−1,539.12, +2,149.79] |
| slow5, contract, t40 | +201.72 [−4,551.54, +4,954.97] | +1,842.94 [−3,477.80, +7,163.68] | +1,738.71 [+228.29, +3,249.13] * | −3.66 [−6.53, −0.79] * | +0.00 [+0.00, +0.00] |
| slow5, contract, t100 | +944.41 [−4,104.76, +5,993.58] | −25,135.80 [−40,634.37, −9,637.23] * | +687.56 [−10.61, +1,385.73] | −1.29 [−2.81, +0.23] | +0.00 [+0.00, +0.00] |
| slow15, contract, t40 | +440.86 [−4,144.64, +5,026.36] | +1,085.83 [−2,693.13, +4,864.78] | +4,399.91 [+1,113.15, +7,686.66] * | −1.13 [−11.47, +9.21] | +0.00 [+0.00, +0.00] |
| slow15, contract, t100 | +613.77 [−2,769.33, +3,996.86] | −23,206.44 [−37,055.87, −9,357.02] * | +1,559.32 [+184.40, +2,934.25] * | +1.11 [−10.03, +12.24] | +0.00 [+0.00, +0.00] |

Units and prices, days 10–30:

| Cell | Licensee units never / W_t / W_g / R | Licensee mean price W_t / W_g / R ($) | Owner units never / W_t / W_g / R |
|---|---|---|---|
| current, contract, t40 | 237.4 / 972.6 / 618.2 / 606.4 | 58.74 / 91.82 / 92.80 | 125.4 / 50.0 / 78.4 / 79.0 |
| current, contract, t100 | 318.4 / 984.3 / 636.7 / 611.2 | 58.50 / 91.50 / 92.80 | 114.9 / 48.0 / 78.7 / 80.8 |
| current, cheap, t40 | 237.4 / 306.8 / 300.7 / 271.0 | 44.69 / 62.81 / 73.78 | 125.4 / 121.0 / 120.9 / 101.2 |
| current, cheap, t100 | 318.4 / 506.7 / 501.9 / 456.1 | 45.76 / 62.71 / 75.32 | 114.9 / 101.4 / 100.7 / 226.7 |
| slow5, contract, t40 | 209.6 / – / 629.7 / 705.3 | – / 90.16 / 92.63 | 140.6 / – / 107.8 / 99.6 |
| slow5, contract, t100 | 317.9 / – / 1049.9 / 392.9 | – / 90.71 / 92.55 | 133.6 / – / 39.6 / 54.1 |
| slow15, contract, t40 | 207.6 / – / 653.3 / 709.0 | – / 85.27 / 91.51 | 152.1 / – / 108.4 / 100.6 |
| slow15, contract, t100 | 317.4 / – / 1056.8 / 329.4 | – / 86.04 / 90.87 | 137.2 / – / 39.3 / 46.0 |

## Owner's gain and licensee profit by royalty

Owner's gain = owner's 30-day profit − never at the same speed. R by the exact recompute; white labels pay no royalty. Licensee profit: per licensee, days 10–30.

| Cell | Owner gain R, 0.05 | Owner gain R, 0.10 | Owner gain R, 0.15 | Owner gain R, 0.25 | Owner gain W_g | Owner gain W_t |
|---|---|---|---|---|---|---|
| current, contract, t40 | +1,486.36 [−821.37, +3,794.10] | +4,356.66 [+231.63, +8,481.68] * | +7,226.95 [+412.78, +14,041.12] * | +12,967.54 [+379.93, +25,555.15] * | −1,426.37 [−4,532.32, +1,679.57] | −2,879.31 [−5,228.91, −529.71] * |
| current, contract, t100 | +2,038.71 [−1,617.21, +5,694.64] | +4,918.45 [−40.54, +9,877.44] | +7,798.18 [+265.19, +15,331.17] * | +13,557.65 [−1.13, +27,116.43] | −929.71 [−5,447.24, +3,587.81] | −2,482.47 [−4,240.14, −724.81] * |
| current, cheap, t40 | −1,943.80 [−5,251.31, +1,363.72] | −953.65 [−4,368.02, +2,460.72] | +36.54 [−3,608.24, +3,681.33] | +2,017.04 [−2,373.14, +6,407.23] | −183.26 [−1,294.39, +927.88] | −176.94 [−1,263.46, +909.58] |
| current, cheap, t100 | +1,771.83 [−828.71, +4,372.36] | +3,460.70 [−17.76, +6,939.17] | +5,149.57 [+669.76, +9,629.38] * | +8,527.24 [+1,903.75, +15,150.73] * | −609.09 [−1,485.13, +266.96] | −594.56 [−1,563.40, +374.28] |
| slow5, contract, t40 | +2,086.50 [−1,508.91, +5,681.91] | +5,298.89 [+794.88, +9,802.90] * | +8,510.94 [+2,215.10, +14,806.78] * | +14,935.63 [+4,245.23, +25,626.02] * | −1,327.90 [−2,263.57, −392.24] * | – |
| slow5, contract, t100 | −1,221.06 [−3,712.74, +1,270.61] | +461.66 [−940.31, +1,863.63] | +2,144.19 [+825.01, +3,463.38] * | +5,509.48 [+1,857.54, +9,161.41] * | −3,848.24 [−6,784.65, −911.84] * | – |
| slow15, contract, t40 | +1,930.15 [−2,838.76, +6,699.06] | +5,123.87 [+93.94, +10,153.79] * | +8,317.11 [+2,077.23, +14,556.99] * | +14,704.22 [+4,729.25, +24,679.19] * | −1,704.48 [−3,272.35, −136.62] * | – |
| slow15, contract, t100 | −1,669.21 [−2,622.77, −715.64] * | −198.63 [−1,105.26, +708.01] | +1,271.53 [−873.72, +3,416.78] | +4,212.27 [−661.60, +9,086.13] | −3,753.46 [−5,463.43, −2,043.50] * | – |

| Cell | Licensee profit never | W_t | W_g | R, 0.05 | R, 0.10 | R, 0.15 | R, 0.25 |
|---|---|---|---|---|---|---|---|
| current, contract, t40 | −1,522.85 [−2,459.80, −585.89] * | +89.22 [−1,581.73, +1,760.17] | +3,345.42 [−255.95, +6,946.78] | +2,904.71 [−332.57, +6,141.99] | +2,426.33 [−314.76, +5,167.42] | +1,947.95 [−296.96, +4,192.85] | +991.18 [−261.38, +2,243.74] |
| current, contract, t100 | −2,193.19 [−3,200.49, −1,185.89] * | +65.56 [−1,832.15, +1,963.27] | +3,416.23 [−587.06, +7,419.52] | +2,916.11 [−644.75, +6,476.96] | +2,436.15 [−585.56, +5,457.87] | +1,956.20 [−526.38, +4,438.77] | +996.29 [−408.02, +2,400.59] |
| current, cheap, t40 | −1,522.85 [−2,459.80, −585.89] * | −4,713.08 [−7,450.02, −1,976.13] * | −3,778.98 [−6,033.97, −1,524.00] * | −3,522.31 [−5,753.02, −1,291.60] * | −3,687.34 [−6,027.37, −1,347.30] * | −3,852.37 [−6,302.08, −1,402.65] * | −4,182.45 [−6,852.07, −1,512.83] * |
| current, cheap, t100 | −2,193.19 [−3,200.49, −1,185.89] * | −7,009.19 [−11,415.14, −2,603.25] * | −5,589.49 [−9,196.05, −1,982.93] * | −5,120.58 [−8,464.52, −1,776.64] * | −5,402.05 [−8,883.51, −1,920.60] * | −5,683.53 [−9,307.44, −2,059.62] * | −6,246.48 [−10,167.66, −2,325.29] * |
| slow5, contract, t40 | −1,599.87 [−2,714.29, −485.46] * | – | +3,254.97 [+1,244.97, +5,264.96] * | +3,315.85 [+701.96, +5,929.74] * | +2,780.45 [+573.70, +4,987.20] * | +2,245.11 [+445.26, +4,044.95] * | +1,174.33 [+185.30, +2,163.36] * |
| slow5, contract, t100 | −2,228.80 [−3,263.33, −1,194.27] * | – | +5,828.37 [+2,078.35, +9,578.40] * | +1,472.99 [+82.02, +2,863.96] * | +1,192.54 [+37.66, +2,347.41] * | +912.11 [−6.83, +1,831.06] | +351.23 [−96.29, +798.76] |
| slow15, contract, t40 | −1,558.40 [−2,461.45, −655.35] * | – | +2,834.96 [+1,097.67, +4,572.26] * | +3,216.77 [+767.65, +5,665.89] * | +2,684.48 [+626.89, +4,742.07] * | +2,152.28 [+485.57, +3,818.98] * | +1,087.76 [+199.46, +1,976.05] * |
| slow15, contract, t100 | −2,242.61 [−3,224.22, −1,261.00] * | – | +5,014.32 [+1,794.31, +8,234.33] * | +1,161.57 [−110.87, +2,434.02] | +916.48 [−124.39, +1,957.34] | +671.45 [−137.96, +1,480.86] | +181.33 [−166.38, +529.03] |

## Rating speed

Days from day 10 (= 1) until a W_g white label's rating first reaches 0.9 (mean over those that reach it), the share that reach it by day 30, and the owner's own rating at the end of day 10 in the never chain.

| Cell | Days to 0.9 | Share reaching 0.9 | Owner rating day 10 (never) |
|---|---|---|---|
| current, contract, t40 | 1.0 [1.0, 1.1] | 1.00 [1.00, 1.00] | 1.000 [1.000, 1.000] |
| current, contract, t100 | 1.0 [1.0, 1.0] | 1.00 [1.00, 1.00] | 1.000 [1.000, 1.000] |
| current, cheap, t40 | – | 0.00 [0.00, 0.00] | 1.000 [1.000, 1.000] |
| current, cheap, t100 | – | 0.00 [0.00, 0.00] | 1.000 [1.000, 1.000] |
| slow5, contract, t40 | 4.8 [2.2, 7.4] | 1.00 [1.00, 1.00] | 0.971 [0.968, 0.974] |
| slow5, contract, t100 | 2.7 [1.3, 4.1] | 1.00 [1.00, 1.00] | 0.967 [0.965, 0.970] |
| slow15, contract, t40 | 14.9 [14.6, 15.2] | 1.00 [1.00, 1.00] | 0.787 [0.757, 0.816] |
| slow15, contract, t100 | 13.9 [13.6, 14.2] | 1.00 [1.00, 1.00] | 0.779 [0.750, 0.808] |

Rating paths: mean over owners (unrated = 0.5), end of days 1, 5, 9, 10, 12, 15, 20, 25, 30.

| Cell | Series | 1 | 5 | 9 | 10 | 12 | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|---|---|---|---|---|
| current, contract, t40 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t40 | owner brand, R | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t40 | owner brand, W_g | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t40 | white labels, W_g | 0.639 | 0.648 | 0.648 | 0.981 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t40 | white labels, W_t | 0.639 | 0.648 | 0.648 | 0.972 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t100 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t100 | owner brand, R | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t100 | owner brand, W_g | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t100 | white labels, W_g | 0.593 | 0.685 | 0.630 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, contract, t100 | white labels, W_t | 0.593 | 0.685 | 0.630 | 0.991 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, cheap, t40 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, cheap, t40 | owner brand, R | 1.000 | 1.000 | 1.000 | 0.802 | 0.549 | 0.383 | 0.263 | 0.269 | 0.229 |
| current, cheap, t40 | owner brand, W_g | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, cheap, t40 | white labels, W_g | 0.639 | 0.648 | 0.648 | 0.102 | 0.019 | 0.000 | 0.000 | 0.000 | 0.000 |
| current, cheap, t40 | white labels, W_t | 0.639 | 0.648 | 0.648 | 0.111 | 0.009 | 0.000 | 0.000 | 0.000 | 0.000 |
| current, cheap, t100 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, cheap, t100 | owner brand, R | 1.000 | 1.000 | 1.000 | 0.811 | 0.585 | 0.401 | 0.354 | 0.358 | 0.335 |
| current, cheap, t100 | owner brand, W_g | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| current, cheap, t100 | white labels, W_g | 0.593 | 0.685 | 0.630 | 0.111 | 0.019 | 0.000 | 0.000 | 0.000 | 0.000 |
| current, cheap, t100 | white labels, W_t | 0.593 | 0.685 | 0.630 | 0.111 | 0.009 | 0.000 | 0.000 | 0.000 | 0.000 |
| slow5, contract, t40 | owner, never | 0.860 | 0.915 | 0.963 | 0.971 | 0.983 | 0.993 | 0.998 | 1.000 | 1.000 |
| slow5, contract, t40 | owner brand, R | 0.860 | 0.915 | 0.963 | 0.974 | 0.987 | 0.995 | 0.999 | 1.000 | 1.000 |
| slow5, contract, t40 | owner brand, W_g | 0.860 | 0.915 | 0.963 | 0.970 | 0.979 | 0.991 | 0.998 | 1.000 | 1.000 |
| slow5, contract, t40 | white labels, W_g | 0.555 | 0.571 | 0.624 | 0.822 | 0.861 | 0.912 | 0.969 | 0.992 | 0.998 |
| slow5, contract, t100 | owner, never | 0.848 | 0.903 | 0.958 | 0.967 | 0.980 | 0.991 | 0.998 | 1.000 | 1.000 |
| slow5, contract, t100 | owner brand, R | 0.848 | 0.903 | 0.958 | 0.970 | 0.984 | 0.994 | 0.999 | 1.000 | 1.000 |
| slow5, contract, t100 | owner brand, W_g | 0.848 | 0.903 | 0.958 | 0.964 | 0.972 | 0.983 | 0.992 | 0.997 | 0.999 |
| slow5, contract, t100 | white labels, W_g | 0.529 | 0.594 | 0.625 | 0.872 | 0.888 | 0.932 | 0.979 | 0.995 | 0.999 |
| slow15, contract, t40 | owner, never | 0.562 | 0.626 | 0.757 | 0.787 | 0.846 | 0.923 | 0.981 | 0.995 | 0.999 |
| slow15, contract, t40 | owner brand, R | 0.562 | 0.626 | 0.757 | 0.821 | 0.905 | 0.963 | 0.993 | 0.999 | 1.000 |
| slow15, contract, t40 | owner brand, W_g | 0.562 | 0.626 | 0.757 | 0.783 | 0.815 | 0.906 | 0.974 | 0.994 | 0.999 |
| slow15, contract, t40 | white labels, W_g | 0.505 | 0.512 | 0.535 | 0.548 | 0.564 | 0.621 | 0.792 | 0.927 | 0.978 |
| slow15, contract, t100 | owner, never | 0.556 | 0.613 | 0.738 | 0.779 | 0.837 | 0.917 | 0.976 | 0.994 | 0.999 |
| slow15, contract, t100 | owner brand, R | 0.556 | 0.613 | 0.738 | 0.808 | 0.885 | 0.950 | 0.989 | 0.998 | 1.000 |
| slow15, contract, t100 | owner brand, W_g | 0.556 | 0.613 | 0.738 | 0.755 | 0.783 | 0.847 | 0.921 | 0.974 | 0.992 |
| slow15, contract, t100 | white labels, W_g | 0.502 | 0.514 | 0.541 | 0.575 | 0.592 | 0.663 | 0.832 | 0.946 | 0.986 |

## Never chains across speeds

The prior reaches every brand. Whole-market 30-day profit by stall type ($, all stalls of the type), catches, the sampled owners' mean 30-day profit, and mean rating of rated brands by type (days 10 and 30). Differences from the current speed, same seeds.

| Never chain | Genuine profit | Seconds profit | Deceptive profit | Catches | Owner profit | Rating genuine d10 / d30 | Rating seconds d10 / d30 | Rating deceptive d10 / d30 |
|---|---|---|---|---|---|---|---|---|
| current, t40 | 97,965.88 [89,039.45, 106,892.32] | −2,946.53 [−4,642.59, −1,250.46] | −52,068.53 [−58,044.26, −46,092.80] | 929 [855, 1002] | 6,502.64 [−1,869.08, 14,874.37] | 1.000 / 1.000 | 1.000 / 1.000 | 0.000 / 0.000 |
| current, t100 | 89,570.26 [80,647.34, 98,493.19] | −2,949.57 [−4,434.24, −1,464.89] | −72,861.18 [−86,511.24, −59,211.13] | 1445 [1311, 1579] | 5,808.03 [−2,012.51, 13,628.57] | 1.000 / 1.000 | 1.000 / 1.000 | 0.000 / 0.000 |
| slow5, t40 | 100,029.16 [93,089.99, 106,968.34] | −4,985.31 [−5,743.04, −4,227.57] | −52,311.75 [−60,916.70, −43,706.80] | 936 [826, 1045] | 6,711.62 [2,607.75, 10,815.50] | 0.974 / 1.000 | 0.858 / 0.982 | 0.271 / 0.231 |
| slow5, t100 | 86,760.81 [75,429.62, 98,092.01] | −3,437.78 [−4,851.29, −2,024.28] | −73,696.91 [−88,253.47, −59,140.34] | 1444 [1293, 1596] | 6,538.65 [2,079.16, 10,998.14] | 0.968 / 1.000 | 0.878 / 0.984 | 0.191 / 0.188 |
| slow15, t40 | 91,965.04 [86,227.67, 97,702.41] | −5,907.30 [−6,590.74, −5,223.86] | −51,372.52 [−58,038.42, −44,706.62] | 934 [841, 1027] | 6,357.81 [2,193.23, 10,522.39] | 0.801 / 0.999 | 0.591 / 0.943 | 0.471 / 0.466 |
| slow15, t100 | 77,911.95 [69,092.65, 86,731.26] | −4,413.30 [−5,504.48, −3,322.11] | −73,536.62 [−85,196.81, −61,876.43] | 1443 [1298, 1587] | 5,886.58 [3,313.48, 8,459.68] | 0.780 / 0.999 | 0.618 / 0.950 | 0.461 / 0.447 |

| Difference | Genuine profit | Seconds profit | Deceptive profit | Catches | Owner profit |
|---|---|---|---|---|---|
| slow5 − current, t40 | +2,063.28 [+69.34, +4,057.22] * | −2,038.78 [−3,012.26, −1,065.30] * | −243.22 [−3,535.51, +3,049.07] | +7 [−34, +48] | +208.98 [−6,891.53, +7,309.50] |
| slow5 − current, t100 | −2,809.45 [−5,568.66, −50.24] * | −488.22 [−625.89, −350.55] * | −835.72 [−2,555.59, +884.14] | −1 [−32, +30] | +730.62 [−4,725.05, +6,186.29] |
| slow15 − current, t40 | −6,000.84 [−9,372.26, −2,629.42] * | −2,960.77 [−4,361.70, −1,559.84] * | +696.01 [−3,400.71, +4,792.73] | +5 [−30, +40] | −144.83 [−8,604.46, +8,314.79] |
| slow15 − current, t100 | −11,658.31 [−13,401.02, −9,915.60] * | −1,463.73 [−1,947.52, −979.94] * | −675.44 [−3,476.27, +2,125.40] | −2 [−61, +57] | +78.55 [−5,911.39, +6,068.50] |

## Buyers by profile, R − W_g (exploratory)

Days 10–30. Shortfall in points of purchases; surplus in $ per buyer of the profile.

| Cell | tourist: shortfall (pts) | local: shortfall (pts) | expert: shortfall (pts) | tourist: surplus ($) | local: surplus ($) | expert: surplus ($) |
|---|---|---|---|---|---|---|
| current, contract, t40 | +0.2 [−0.1, +0.6] | +0.0 [−0.0, +0.1] | +0.0 [+0.0, +0.0] | −0.46 [−1.21, +0.28] | −0.17 [−0.38, +0.05] | −0.10 [−0.22, +0.01] |
| current, contract, t100 | +0.0 [−0.1, +0.2] | – | – | −0.32 [−0.76, +0.12] | – | – |
| current, cheap, t40 | −1.6 [−3.7, +0.4] | +0.4 [+0.1, +0.7] * | +0.0 [+0.0, +0.0] | +0.18 [−1.20, +1.55] | −0.29 [−0.50, −0.09] * | −0.12 [−0.34, +0.09] |
| current, cheap, t100 | −1.1 [−2.8, +0.6] | – | – | −0.07 [−1.91, +1.78] | – | – |
| slow5, contract, t40 | +0.1 [−0.2, +0.5] | +0.0 [−0.2, +0.3] | +0.0 [+0.0, +0.0] | −0.91 [−1.43, −0.39] * | −0.57 [−1.08, −0.06] * | −0.42 [−0.60, −0.24] * |
| slow5, contract, t100 | −0.1 [−0.8, +0.7] | – | – | −0.52 [−1.42, +0.39] | – | – |
| slow15, contract, t40 | +0.3 [−0.2, +0.7] | +0.1 [−0.2, +0.4] | +0.0 [+0.0, +0.0] | −1.94 [−2.97, −0.92] * | −1.33 [−1.87, −0.79] * | −1.06 [−1.71, −0.40] * |
| slow15, contract, t100 | −0.0 [−0.8, +0.8] | – | – | −1.76 [−2.30, −1.22] * | – | – |

## Stuck, parked and idle buyers

| Chains | Count | Buyer-days | Stuck | Parked | Idle choosers | Invalid actions |
|---|---|---|---|---|---|---|
| R · cheap · t100 · p0 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| R · cheap · t40 · p0 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| R · contract · t100 · p0 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| R · contract · t100 · p2.5 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| R · contract · t100 · p50 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| R · contract · t40 · p0 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| R · contract · t40 · p2.5 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| R · contract · t40 · p50 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| Wg · cheap · t100 · p0 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| Wg · cheap · t40 · p0 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| Wg · contract · t100 · p0 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| Wg · contract · t100 · p2.5 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| Wg · contract · t100 · p50 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| Wg · contract · t40 · p0 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| Wg · contract · t40 · p2.5 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| Wg · contract · t40 · p50 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| Wt · cheap · t100 · p0 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| Wt · cheap · t40 · p0 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| Wt · contract · t100 · p0 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| Wt · contract · t40 · p0 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| never · - · t100 · p0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| never · - · t100 · p2.5 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| never · - · t100 · p50 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| never · - · t40 · p0 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| never · - · t40 · p2.5 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| never · - · t40 · p50 | 3 | 13,500 | 0 | 0 | 0 | 0 |

## Flags

- none

## Reading (written after the results)

READING_PLACEHOLDER

## Caveats

CAVEATS_PLACEHOLDER
