# Checking vs reading ratings

Spec: `runs/plan_autonomous_2026-11-19.md`, Stage 1 (preregistered at 59e15de, 2026-11-19 12:01 EST). Engine 0.21.0 (`buyers.profile_overrides`).

## Design (prespecified)

- Question: locals both inspect and read ratings, so earlier runs cannot say which behaviour stops switching supply and which pays for reputation. Separate them.
- Buyers: tourist share 0.4; the other 0.6 are all locals (experts 0). Locals: reads_ratings {yes, no} × inspect_prob {1.0, 0}, 4 cells. Reference cell: tourist share 1.0. Bargain hunters 0.2 as in the verification market. Market defaults of the plan: ratings display stars at step 0.02, random tie-break.
- Outcome A, bust-out gain: the verification-run benchmark (3 genuine stalls per seed from `default_rng([seed, 17])`; candidates never, day 20, 25, 28, 29, 30; unfloored gain primary), market B of the verification run (2 patrolling inspectors, not uniformed), collectible fines (penalty lag 0), 30 days, detect_scale 0 and 1.
- Outcome B, reputation effect: E = J(R) − J(W_g) as in `analysis/brand_equity_stars.py` (contract, genuine tier, royalty 0.10, N 6 from day 10, prior_scope new, 60 days, detect_scale 1), at prior_n 0 and 400.
- Seeds 900-902 (3), fresh, paired across all cells.
- Predictions (verbatim from the plan):
  - PC1 (confirmatory): bust-out gain, detect_scale 0: the main effect of inspection (inspect 1.0 − 0, averaged over reads_ratings) is < 0.
  - PC2 (confirmatory): bust-out gain, detect_scale 0: |main effect of reading ratings| < |main effect of inspection|.
  - PC3 (confirmatory): reputation effect, prior_n 400: the main effect of reading ratings (yes − no, averaged over inspection) is > 0.
  - PC4 (confirmatory): reputation effect, prior_n 400: |main effect of inspection| < |main effect of reading ratings|.
  - PC5 (exploratory): both interactions (reading × inspection) for each outcome; the detect_scale 1 analogues of PC1–PC2; the prior_n 0 analogues of PC3–PC4.
  - PC6 (exploratory): harm by profile; deceptive stalls' share of sales by cell; the bust-out decomposition's "rating below threshold" cause by cell.
- Analysis (prespecified): per seed, the mean over sampled stalls or owners; main effects and interactions from the 2×2 per seed; mean and 95% t over seeds, unadjusted. Implementation (fixed before the pilot): main effect of inspection = mean(RI, nI) − mean(Rn, nn); of reading = mean(RI, Rn) − mean(nI, nn); interaction = (RI − Rn) − (nI − nn). PC2 and PC4 compare sizes per seed as sgn(Ī)·I_s − sgn(R̄)·R_s (PC2) and its negative (PC4), whose mean is |Ī| − |R̄|; supported when the interval is above 0.

## Run record

- Engine `0.21.0`; commit `1f96cbb2f8cad8594020c652f7a227929b928d0b`; uncommitted at run time: ['M analysis/check_vs_read.py', ' M docs/formal_model.md', ' M runs/STATUS.md', '?? runs/formal_model_check.md', '?? runs/pilot_check_vs_read/', '?? runs/pilot_check_vs_read_stdout.log']
- Script sha256 `c3cc831903f8117f8753d2755a068e760c50cfcde2bc5a0529d901334bf08911`
- Command: `python -m analysis.check_vs_read --pilot --min-swap-mb 0 --tests full suite at 4a83784: 1799 passed, 17 skipped (runs/tests_0210.log); tests/test_v0210.py passed`
- Tests: full suite at 4a83784: 1799 passed, 17 skipped (runs/tests_0210.log); tests/test_v0210.py passed
- Python 3.12.7, numpy 2.5.4, macOS-27.2.1-arm64-arm-64bit
- 773 chains on 4 workers (nice 19); wall clock 0.00 h; load average [2.52, 4.64, 5.27] at start, [2.52, 4.64, 5.27] at end; memory-guard pauses: 0

## Gate and checks

Pilot: G1 pass, G2 pass, G3 pass, G4 pass, G5 pass

- J identity: 270/270 owner-chains to the cent. Genuine-tier price misses: 0.
- Flags: none.

## Predictions

$ per stall (A) or per owner (B), per-seed means; 95% t over seeds, unadjusted.

| Prediction | Estimate ($) | Verdict |
|---|---|---|
| **PC1**: main effect of inspection, bust-out gain, ds 0 (< 0) | −604.04 [−974.23, −233.85] * | supported |
| **PC2**: |inspection| − |reading|, bust-out gain, ds 0 (> 0) | +250.97 [+80.16, +421.77] * | supported |
| **PC3**: main effect of reading, E, prior_n 400 (> 0) | +14,832.40 [+3,929.64, +25,735.16] * | supported |
| **PC4**: |reading| − |inspection|, E, prior_n 400 (> 0) | +8,783.34 [+728.28, +16,838.40] * | supported |

### Outcome A: bust-out gain, detect_scale 0

| Cell | Unfloored gain ($) | Floored gain ($) | Best day (20/25/28/29/30) |
|---|---|---|---|
| reads, inspects | −91.16 [−169.08, −13.23] * | +5.81 [−19.19, +30.82] | 0 / 0 / 0 / 1 / 8 |
| reads, does not inspect | +212.39 [+86.38, +338.40] * | +212.39 [+86.38, +338.40] * | 0 / 0 / 3 / 3 / 3 |
| does not read, inspects | −38.58 [−102.38, +25.22] | +12.80 [+2.14, +23.46] * | 0 / 0 / 1 / 2 / 6 |
| neither (as a tourist) | +865.95 [+334.90, +1,397.01] * | +865.95 [+334.90, +1,397.01] * | 8 / 1 / 0 / 0 / 0 |
| reference: tourist share 1.0 | +865.95 [+334.90, +1,397.01] * | +865.95 [+334.90, +1,397.01] * | 8 / 1 / 0 / 0 / 0 |

Main effect of inspection −604.04 [−974.23, −233.85] *; of reading −353.07 [−578.25, −127.90] *; interaction +600.99 [+108.80, +1,093.18] *; |inspection| − |reading| +250.97 [+80.16, +421.77] *. Reference − neither +0.00 [+0.00, +0.00].

### Outcome A: bust-out gain, detect_scale 1

| Cell | Unfloored gain ($) | Floored gain ($) | Best day (20/25/28/29/30) |
|---|---|---|---|
| reads, inspects | −641.29 [−1,092.43, −190.15] * | +0.00 [+0.00, +0.00] | 0 / 0 / 0 / 0 / 9 |
| reads, does not inspect | −547.56 [−1,045.42, −49.71] * | +0.00 [+0.00, +0.00] | 0 / 0 / 0 / 0 / 9 |
| does not read, inspects | −641.34 [−1,092.25, −190.43] * | +0.00 [+0.00, +0.00] | 0 / 0 / 0 / 0 / 9 |
| neither (as a tourist) | −579.49 [−974.32, −184.66] * | +0.00 [+0.00, +0.00] | 0 / 0 / 0 / 0 / 9 |
| reference: tourist share 1.0 | −579.49 [−974.32, −184.66] * | +0.00 [+0.00, +0.00] | 0 / 0 / 0 / 0 / 9 |

Main effect of inspection −77.79 [−274.20, +118.62]; of reading +15.99 [−47.48, +79.46]; interaction −31.87 [−158.65, +94.90]; |inspection| − |reading| +61.80 [−95.06, +218.66]. Reference − neither +0.00 [+0.00, +0.00].

### Outcome B: reputation effect E, prior_n 0

| Cell | E ($) | J R ($) | J W_g ($) | J never ($) |
|---|---|---|---|---|
| reads, inspects | +276.72 [−555.49, +1,108.93] | +59,210.09 [+22,335.01, +96,085.17] * | +58,933.37 [+22,408.95, +95,457.79] * | −31,383.46 [−69,038.14, +6,271.22] |
| reads, does not inspect | +616.31 [−519.29, +1,751.92] | +68,693.12 [+26,834.84, +110,551.41] * | +68,076.81 [+26,947.20, +109,206.42] * | −25,934.55 [−56,415.77, +4,546.67] |
| does not read, inspects | +11.63 [−705.05, +728.31] | +57,885.44 [+21,517.91, +94,252.97] * | +57,873.80 [+21,595.27, +94,152.33] * | −29,687.79 [−66,339.91, +6,964.33] |
| neither (as a tourist) | +97.84 [−821.91, +1,017.59] | +61,809.86 [+23,124.21, +100,495.51] * | +61,712.02 [+23,521.02, +99,903.02] * | −18,429.96 [−40,696.39, +3,836.47] |
| reference: tourist share 1.0 | +97.84 [−821.91, +1,017.59] | +61,809.86 [+23,124.21, +100,495.51] * | +61,712.02 [+23,521.02, +99,903.02] * | −18,429.96 [−40,696.39, +3,836.47] |

Main effect of reading +391.78 [+66.07, +717.49] *; of inspection −212.90 [−620.34, +194.54]; interaction −253.39 [−334.97, −171.80] *; |reading| − |inspection| +178.88 [+82.97, +274.80] *. Reference − neither +0.00 [+0.00, +0.00].

### Outcome B: reputation effect E, prior_n 400

| Cell | E ($) | J R ($) | J W_g ($) | J never ($) |
|---|---|---|---|---|
| reads, inspects | +3,046.70 [−121.66, +6,215.07] | +59,072.03 [+21,932.96, +96,211.11] * | +56,025.33 [+21,965.72, +90,084.94] * | −31,186.66 [−69,726.93, +7,353.61] |
| reads, does not inspect | +12,257.47 [+4,236.92, +20,278.03] * | +68,677.74 [+26,817.61, +110,537.87] * | +56,420.27 [+22,567.42, +90,273.12] * | −26,036.39 [−56,832.73, +4,759.95] |
| does not read, inspects | −8,623.99 [−14,647.87, −2,600.11] * | +57,879.77 [+21,531.40, +94,228.15] * | +66,503.76 [+24,954.85, +108,052.67] * | −29,613.82 [−66,279.34, +7,051.71] |
| neither (as a tourist) | −5,736.64 [−11,249.38, −223.89] * | +61,810.54 [+23,161.86, +100,459.21] * | +67,547.17 [+24,387.17, +110,707.17] * | −18,235.07 [−40,115.68, +3,645.55] |
| reference: tourist share 1.0 | −5,736.64 [−11,249.38, −223.89] * | +61,810.54 [+23,161.86, +100,459.21] * | +67,547.17 [+24,387.17, +110,707.17] * | −18,235.07 [−40,115.68, +3,645.55] |

Main effect of reading +14,832.40 [+3,929.64, +25,735.16] *; of inspection −6,049.06 [−8,897.99, −3,200.13] *; interaction −6,323.42 [−10,938.73, −1,708.11] *; |reading| − |inspection| +8,783.34 [+728.28, +16,838.40] *. Reference − neither +0.00 [+0.00, +0.00].

### PC5 (exploratory)

| Quantity | Estimate ($) | Side of 0 (rule of the matching prediction) |
|---|---|---|
| Interaction, bust-out gain, ds 0 | +600.99 [+108.80, +1,093.18] * | – |
| Interaction, bust-out gain, ds 1 | −31.87 [−158.65, +94.90] | – |
| Interaction, E, prior_n 400 | −6,323.42 [−10,938.73, −1,708.11] * | – |
| Interaction, E, prior_n 0 | −253.39 [−334.97, −171.80] * | – |
| PC1 at ds 1: main effect of inspection | −77.79 [−274.20, +118.62] | not supported (interval includes 0) |
| PC2 at ds 1: |inspection| − |reading| | +61.80 [−95.06, +218.66] | not supported (interval includes 0) |
| PC3 at prior_n 0: main effect of reading | +391.78 [+66.07, +717.49] * | supported |
| PC4 at prior_n 0: |reading| − |inspection| | +178.88 [+82.97, +274.80] * | supported |

### PC6 (exploratory)

Never chains of outcome A, detect_scale 0: deceptive stalls' share of units sold, and per profile the shortfall share of purchases and surplus per buyer-day (value − paid − inspection cost).

| Cell | Deceptive share of units | Tourists: shortfall share | Tourists: surplus ($) | Locals: shortfall share | Locals: surplus ($) |
|---|---|---|---|---|---|
| reads, inspects | +0.299 [+0.271, +0.327] * | +0.604 [+0.542, +0.666] * | −14.58 [−21.19, −7.97] * | +0.003 [−0.001, +0.007] | +7.95 [+5.97, +9.94] * |
| reads, does not inspect | +0.302 [+0.274, +0.331] * | +0.604 [+0.542, +0.666] * | −14.56 [−21.04, −8.07] * | +0.017 [+0.011, +0.022] * | +10.15 [+8.18, +12.12] * |
| does not read, inspects | +0.414 [+0.381, +0.447] * | +0.604 [+0.542, +0.666] * | −14.58 [−21.19, −7.97] * | +0.110 [+0.087, +0.133] * | +3.28 [+2.46, +4.10] * |
| neither (as a tourist) | +0.659 [+0.631, +0.687] * | +0.604 [+0.542, +0.666] * | −14.56 [−21.04, −8.07] * | +0.614 [+0.589, +0.638] * | −14.00 [−14.38, −13.62] * |
| reference: tourist share 1.0 | +0.659 [+0.631, +0.687] * | +0.610 [+0.599, +0.621] * | −14.22 [−16.68, −11.76] * | – | – |

Never chains of outcome A, detect_scale 1: deceptive stalls' share of units sold, and per profile the shortfall share of purchases and surplus per buyer-day (value − paid − inspection cost).

| Cell | Deceptive share of units | Tourists: shortfall share | Tourists: surplus ($) | Locals: shortfall share | Locals: surplus ($) |
|---|---|---|---|---|---|
| reads, inspects | +0.140 [+0.121, +0.160] * | +0.266 [+0.235, +0.298] * | −3.54 [−4.58, −2.49] * | +0.013 [+0.004, +0.022] * | +6.77 [+4.33, +9.22] * |
| reads, does not inspect | +0.169 [+0.144, +0.195] * | +0.269 [+0.205, +0.333] * | −3.55 [−4.85, −2.26] * | +0.082 [+0.071, +0.093] * | +7.21 [+5.50, +8.91] * |
| does not read, inspects | +0.162 [+0.132, +0.191] * | +0.265 [+0.226, +0.303] * | −3.61 [−3.83, −3.38] * | +0.039 [+0.029, +0.049] * | +5.74 [+4.01, +7.48] * |
| neither (as a tourist) | +0.293 [+0.250, +0.336] * | +0.272 [+0.222, +0.322] * | −3.68 [−5.19, −2.18] * | +0.273 [+0.229, +0.318] * | −2.24 [−3.70, −0.77] * |
| reference: tourist share 1.0 | +0.293 [+0.250, +0.336] * | +0.273 [+0.230, +0.315] * | −2.82 [−3.12, −2.51] * | – | – |

Bust-out decomposition at detect_scale 0 (each stall's best candidate against never; `analysis/bustout_report.py`), $ per stall:

| Cell | Lost: inspected and walked away | Lost: rating below threshold | Lost: outranked | Cost saved | Premium lost |
|---|---|---|---|---|---|
| reads, inspects | −169.99 [−210.19, −129.80] * | +0.00 [+0.00, +0.00] | −14.21 [−75.34, +46.92] | +82.04 [+18.29, +145.79] * | −3.20 [−16.97, +10.57] |
| reads, does not inspect | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | −42.49 [−147.90, +62.91] | +289.31 [+38.23, +540.38] * | −75.06 [−201.22, +51.10] |
| does not read, inspects | −139.76 [−172.71, −106.81] * | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +89.32 [+22.43, +156.21] * | −9.17 [−33.55, +15.20] |
| neither (as a tourist) | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +1,078.70 [+521.29, +1,636.11] * | −1,177.75 [−1,645.94, −709.56] * |
| reference: tourist share 1.0 | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +1,078.70 [+521.29, +1,636.11] * | −1,177.75 [−1,645.94, −709.56] * |

## Guard

| Kind · cell | Chains | Stuck | Parked | Idle choosers | Fallbacks | Cell settings wrong | Seconds per chain |
|---|---|---|---|---|---|---|---|
| A · RI | 96 | 0 | 0 | 0 | 0 | 0 | 26.9 |
| A · Rn | 96 | 0 | 0 | 0 | 0 | 0 | 27.3 |
| A · nI | 96 | 0 | 0 | 0 | 0 | 0 | 27.4 |
| A · nn | 96 | 0 | 0 | 0 | 0 | 0 | 27.8 |
| A · ref | 96 | 0 | 0 | 0 | 0 | 0 | 27.1 |
| B · RI | 42 | 0 | 0 | 0 | 0 | 0 | 54.0 |
| B · Rn | 42 | 0 | 0 | 0 | 0 | 0 | 56.9 |
| B · nI | 42 | 0 | 0 | 0 | 0 | 0 | 56.5 |
| B · nn | 42 | 0 | 0 | 0 | 0 | 0 | 54.9 |
| B · ref | 42 | 0 | 0 | 0 | 0 | 0 | 54.2 |
| D · RI | 12 | 0 | 0 | 0 | 0 | 0 | 27.7 |
| D · Rn | 12 | 0 | 0 | 0 | 0 | 0 | 28.2 |
| D · nI | 12 | 0 | 0 | 0 | 0 | 0 | 30.1 |
| D · nn | 12 | 0 | 0 | 0 | 0 | 0 | 28.6 |
| D · ref | 12 | 0 | 0 | 0 | 0 | 0 | 27.6 |

## Reading (written after the results)

READING_PLACEHOLDER

## Caveats

CAVEATS_PLACEHOLDER
