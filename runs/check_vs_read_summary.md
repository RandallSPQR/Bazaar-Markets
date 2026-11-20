# Checking vs reading ratings

Spec: `runs/plan_autonomous_2026-11-19.md`, Stage 1 (preregistered at 59e15de, 2026-11-19 12:01 EST). Engine 0.21.0 (`buyers.profile_overrides`).

## Design (prespecified)

- Question: locals both inspect and read ratings, so earlier runs cannot say which behaviour stops switching supply and which pays for reputation. Separate them.
- Buyers: tourist share 0.4; the other 0.6 are all locals (experts 0). Locals: reads_ratings {yes, no} × inspect_prob {1.0, 0}, 4 cells. Reference cell: tourist share 1.0. Bargain hunters 0.2 as in the verification market. Market defaults of the plan: ratings display stars at step 0.02, random tie-break.
- Outcome A, bust-out gain: the verification-run benchmark (3 genuine stalls per seed from `default_rng([seed, 17])`; candidates never, day 20, 25, 28, 29, 30; unfloored gain primary), market B of the verification run (2 patrolling inspectors, not uniformed), collectible fines (penalty lag 0), 30 days, detect_scale 0 and 1.
- Outcome B, reputation effect: E = J(R) − J(W_g) as in `analysis/brand_equity_stars.py` (contract, genuine tier, royalty 0.10, N 6 from day 10, prior_scope new, 60 days, detect_scale 1), at prior_n 0 and 400.
- Seeds 350-369 (20), fresh, paired across all cells.
- Predictions (verbatim from the plan):
  - PC1 (confirmatory): bust-out gain, detect_scale 0: the main effect of inspection (inspect 1.0 − 0, averaged over reads_ratings) is < 0.
  - PC2 (confirmatory): bust-out gain, detect_scale 0: |main effect of reading ratings| < |main effect of inspection|.
  - PC3 (confirmatory): reputation effect, prior_n 400: the main effect of reading ratings (yes − no, averaged over inspection) is > 0.
  - PC4 (confirmatory): reputation effect, prior_n 400: |main effect of inspection| < |main effect of reading ratings|.
  - PC5 (exploratory): both interactions (reading × inspection) for each outcome; the detect_scale 1 analogues of PC1–PC2; the prior_n 0 analogues of PC3–PC4.
  - PC6 (exploratory): harm by profile; deceptive stalls' share of sales by cell; the bust-out decomposition's "rating below threshold" cause by cell.
- Analysis (prespecified): per seed, the mean over sampled stalls or owners; main effects and interactions from the 2×2 per seed; mean and 95% t over seeds, unadjusted. Implementation (fixed before the pilot): main effect of inspection = mean(RI, nI) − mean(Rn, nn); of reading = mean(RI, Rn) − mean(nI, nn); interaction = (RI − Rn) − (nI − nn). PC2 and PC4 compare sizes per seed as sgn(Ī)·I_s − sgn(R̄)·R_s (PC2) and its negative (PC4), whose mean is |Ī| − |R̄|; supported when the interval is above 0.

## Run record

- Engine `0.21.0`; commit `9cb3e670ca069672a5f2baee8046aef9d099f8e0`; uncommitted at run time: ['?? runs/check_vs_read.json.gz', '?? runs/check_vs_read_run.log', '?? runs/check_vs_read_stdout_block1.log', '?? runs/check_vs_read_stdout_block2.log', '?? runs/check_vs_read_stdout_final.log', '?? runs/check_vs_read_summary.md', '?? runs/queue_check_vs_read.log']
- Script sha256 `c3cc831903f8117f8753d2755a068e760c50cfcde2bc5a0529d901334bf08911`
- Command: `python -m analysis.check_vs_read --seeds 350-369 --workers 4 --min-swap-mb 0 --tests Engine 0.21.0 (4a83784): full suite 1799 passed, 17 skipped (runs/tests_0210.log); 174 0.20.0 reference cells reproduce byte for byte --gate Pilot G1, G2, G4, G5 pass (G4 after one comparison fix); G3 failed (7.18 h after trims) and was waived by Randall for the full design (runs/pilot_check_vs_read.md, plan deviation D4)`
- Tests: Engine 0.21.0 (4a83784): full suite 1799 passed, 17 skipped (runs/tests_0210.log); 174 0.20.0 reference cells reproduce byte for byte
- Python 3.12.7, numpy 2.5.4, macOS-27.2.1-arm64-arm-64bit
- 5000 chains on 4 workers (nice 19); wall clock 0.00 h (final pass; the chains ran in two blocks, 5.97 h at 4dd5c2d and 5.79 h at 9cb3e67, see Caveats); load average [4.74, 5.4, 5.59] at start, [4.52, 5.34, 5.56] at end; memory-guard pauses: 0

## Gate and checks

Pilot G1, G2, G4, G5 pass (G4 after one comparison fix); G3 failed (7.18 h after trims) and was waived by Randall for the full design (runs/pilot_check_vs_read.md, plan deviation D4)

- J identity: 1800/1800 owner-chains to the cent. Genuine-tier price misses: 0.
- Flags: none.

## Predictions

$ per stall (A) or per owner (B), per-seed means; 95% t over seeds, unadjusted.

| Prediction | Estimate ($) | Verdict |
|---|---|---|
| **PC1**: main effect of inspection, bust-out gain, ds 0 (< 0) | −364.05 [−479.15, −248.94] * | supported |
| **PC2**: |inspection| − |reading|, bust-out gain, ds 0 (> 0) | +185.69 [+121.68, +249.71] * | supported |
| **PC3**: main effect of reading, E, prior_n 400 (> 0) | +9,987.06 [+7,410.85, +12,563.27] * | supported |
| **PC4**: |reading| − |inspection|, E, prior_n 400 (> 0) | +5,902.60 [+4,439.89, +7,365.30] * | supported |

### Outcome A: bust-out gain, detect_scale 0

| Cell | Unfloored gain ($) | Floored gain ($) | Best day (20/25/28/29/30) |
|---|---|---|---|
| reads, inspects | −75.79 [−116.13, −35.46] * | +2.93 [+0.58, +5.29] * | 0 / 0 / 3 / 8 / 49 |
| reads, does not inspect | +165.42 [+110.40, +220.45] * | +165.42 [+110.40, +220.45] * | 0 / 2 / 22 / 23 / 13 |
| does not read, inspects | −20.27 [−50.03, +9.49] | +19.23 [+6.12, +32.35] * | 0 / 0 / 11 / 10 / 39 |
| neither (as a tourist) | +466.61 [+320.45, +612.77] * | +466.61 [+320.45, +612.77] * | 53 / 7 / 0 / 0 / 0 |
| reference: tourist share 1.0 | +466.61 [+320.45, +612.77] * | +466.61 [+320.45, +612.77] * | 53 / 7 / 0 / 0 / 0 |

Main effect of inspection −364.05 [−479.15, −248.94] *; of reading −178.35 [−235.01, −121.70] *; interaction +245.66 [+157.28, +334.05] *; |inspection| − |reading| +185.69 [+121.68, +249.71] *. Reference − neither +0.00 [+0.00, +0.00].

### Outcome A: bust-out gain, detect_scale 1

| Cell | Unfloored gain ($) | Floored gain ($) | Best day (20/25/28/29/30) |
|---|---|---|---|
| reads, inspects | −411.35 [−503.07, −319.62] * | +0.00 [+0.00, +0.00] | 0 / 0 / 0 / 0 / 60 |
| reads, does not inspect | −361.45 [−452.51, −270.38] * | +0.00 [+0.00, +0.00] | 0 / 0 / 0 / 0 / 60 |
| does not read, inspects | −405.23 [−503.92, −306.53] * | +0.00 [+0.00, +0.00] | 0 / 0 / 0 / 0 / 60 |
| neither (as a tourist) | −356.46 [−456.03, −256.89] * | +0.00 [+0.00, +0.00] | 0 / 0 / 0 / 0 / 60 |
| reference: tourist share 1.0 | −356.46 [−456.03, −256.89] * | +0.00 [+0.00, +0.00] | 0 / 0 / 0 / 0 / 60 |

Main effect of inspection −49.34 [−97.42, −1.25] *; of reading −5.55 [−26.17, +15.07]; interaction −1.13 [−45.17, +42.91]; |inspection| − |reading| +43.78 [−3.00, +90.56]. Reference − neither +0.00 [+0.00, +0.00].

### Outcome B: reputation effect E, prior_n 0

| Cell | E ($) | J R ($) | J W_g ($) | J never ($) |
|---|---|---|---|---|
| reads, inspects | +134.03 [+76.56, +191.50] * | +38,586.77 [+28,639.81, +48,533.72] * | +38,452.74 [+28,536.71, +48,368.77] * | −21,633.50 [−27,019.81, −16,247.20] * |
| reads, does not inspect | +386.57 [+290.22, +482.92] * | +44,896.95 [+33,204.26, +56,589.63] * | +44,510.38 [+32,892.52, +56,128.24] * | −19,068.95 [−23,848.16, −14,289.74] * |
| does not read, inspects | −29.82 [−77.74, +18.09] | +37,920.90 [+28,115.00, +47,726.79] * | +37,950.72 [+28,130.94, +47,770.50] * | −20,741.40 [−25,869.30, −15,613.50] * |
| neither (as a tourist) | +25.84 [−19.99, +71.67] | +40,407.14 [+29,958.24, +50,856.04] * | +40,381.30 [+29,937.35, +50,825.25] * | −13,648.91 [−16,931.92, −10,365.90] * |
| reference: tourist share 1.0 | +25.84 [−19.99, +71.67] | +40,407.14 [+29,958.24, +50,856.04] * | +40,381.30 [+29,937.35, +50,825.25] * | −13,648.91 [−16,931.92, −10,365.90] * |

Main effect of reading +262.29 [+195.94, +328.64] *; of inspection −154.10 [−197.25, −110.95] *; interaction −196.88 [−243.21, −150.54] *; |reading| − |inspection| +108.19 [+69.62, +146.77] *. Reference − neither +0.00 [+0.00, +0.00].

### Outcome B: reputation effect E, prior_n 400

| Cell | E ($) | J R ($) | J W_g ($) | J never ($) |
|---|---|---|---|---|
| reads, inspects | +1,825.39 [+1,357.67, +2,293.11] * | +38,537.15 [+28,610.07, +48,464.23] * | +36,711.76 [+27,128.93, +46,294.59] * | −21,454.15 [−26,745.64, −16,162.66] * |
| reads, does not inspect | +8,050.68 [+6,022.73, +10,078.62] * | +44,894.93 [+33,196.42, +56,593.43] * | +36,844.25 [+27,153.06, +46,535.44] * | −18,956.82 [−23,729.89, −14,183.75] * |
| does not read, inspects | −6,020.85 [−7,725.33, −4,316.37] * | +37,924.92 [+28,118.94, +47,730.89] * | +43,945.77 [+32,472.73, +55,418.80] * | −20,649.18 [−25,747.30, −15,551.07] * |
| neither (as a tourist) | −4,077.21 [−5,232.32, −2,922.10] * | +40,408.39 [+29,958.66, +50,858.11] * | +44,485.60 [+32,935.60, +56,035.60] * | −13,479.90 [−16,735.74, −10,224.05] * |
| reference: tourist share 1.0 | −4,077.21 [−5,232.32, −2,922.10] * | +40,408.39 [+29,958.66, +50,858.11] * | +44,485.60 [+32,935.60, +56,035.60] * | −13,479.90 [−16,735.74, −10,224.05] * |

Main effect of reading +9,987.06 [+7,410.85, +12,563.27] *; of inspection −4,084.47 [−5,214.36, −2,954.58] *; interaction −4,281.65 [−5,417.73, −3,145.57] *; |reading| − |inspection| +5,902.60 [+4,439.89, +7,365.30] *. Reference − neither +0.00 [+0.00, +0.00].

### PC5 (exploratory)

| Quantity | Estimate ($) | Side of 0 (rule of the matching prediction) |
|---|---|---|
| Interaction, bust-out gain, ds 0 | +245.66 [+157.28, +334.05] * | – |
| Interaction, bust-out gain, ds 1 | −1.13 [−45.17, +42.91] | – |
| Interaction, E, prior_n 400 | −4,281.65 [−5,417.73, −3,145.57] * | – |
| Interaction, E, prior_n 0 | −196.88 [−243.21, −150.54] * | – |
| PC1 at ds 1: main effect of inspection | −49.34 [−97.42, −1.25] * | supported |
| PC2 at ds 1: |inspection| − |reading| | +43.78 [−3.00, +90.56] | not supported (interval includes 0) |
| PC3 at prior_n 0: main effect of reading | +262.29 [+195.94, +328.64] * | supported |
| PC4 at prior_n 0: |reading| − |inspection| | +108.19 [+69.62, +146.77] * | supported |

### PC6 (exploratory)

Never chains of outcome A, detect_scale 0: deceptive stalls' share of units sold, and per profile the shortfall share of purchases and surplus per buyer-day (value − paid − inspection cost).

| Cell | Deceptive share of units | Tourists: shortfall share | Tourists: surplus ($) | Locals: shortfall share | Locals: surplus ($) |
|---|---|---|---|---|---|
| reads, inspects | +0.296 [+0.292, +0.301] * | +0.613 [+0.606, +0.620] * | −15.36 [−16.60, −14.13] * | +0.002 [+0.002, +0.002] * | +8.06 [+7.72, +8.41] * |
| reads, does not inspect | +0.299 [+0.295, +0.303] * | +0.613 [+0.606, +0.620] * | −15.32 [−16.55, −14.08] * | +0.015 [+0.014, +0.016] * | +10.46 [+10.11, +10.80] * |
| does not read, inspects | +0.412 [+0.406, +0.418] * | +0.613 [+0.606, +0.620] * | −15.37 [−16.60, −14.14] * | +0.109 [+0.106, +0.111] * | +3.11 [+2.59, +3.62] * |
| neither (as a tourist) | +0.654 [+0.649, +0.659] * | +0.613 [+0.606, +0.620] * | −15.32 [−16.56, −14.09] * | +0.608 [+0.602, +0.614] * | −15.09 [−16.32, −13.85] * |
| reference: tourist share 1.0 | +0.654 [+0.649, +0.659] * | +0.610 [+0.605, +0.615] * | −15.18 [−16.35, −14.00] * | – | – |

Never chains of outcome A, detect_scale 1: deceptive stalls' share of units sold, and per profile the shortfall share of purchases and surplus per buyer-day (value − paid − inspection cost).

| Cell | Deceptive share of units | Tourists: shortfall share | Tourists: surplus ($) | Locals: shortfall share | Locals: surplus ($) |
|---|---|---|---|---|---|
| reads, inspects | +0.145 [+0.142, +0.148] * | +0.284 [+0.279, +0.289] * | −4.12 [−4.84, −3.39] * | +0.013 [+0.012, +0.014] * | +6.70 [+6.34, +7.07] * |
| reads, does not inspect | +0.171 [+0.168, +0.175] * | +0.282 [+0.276, +0.289] * | −4.12 [−4.92, −3.32] * | +0.081 [+0.078, +0.084] * | +7.22 [+6.78, +7.67] * |
| does not read, inspects | +0.168 [+0.164, +0.172] * | +0.285 [+0.279, +0.290] * | −4.15 [−4.87, −3.44] * | +0.038 [+0.037, +0.040] * | +5.59 [+5.18, +6.00] * |
| neither (as a tourist) | +0.299 [+0.293, +0.304] * | +0.281 [+0.274, +0.287] * | −4.07 [−4.86, −3.29] * | +0.276 [+0.271, +0.282] * | −3.70 [−4.48, −2.92] * |
| reference: tourist share 1.0 | +0.299 [+0.293, +0.304] * | +0.278 [+0.273, +0.283] * | −3.85 [−4.57, −3.13] * | – | – |

Bust-out decomposition at detect_scale 0 (each stall's best candidate against never; `analysis/bustout_report.py`), $ per stall:

| Cell | Lost: inspected and walked away | Lost: rating below threshold | Lost: outranked | Cost saved | Premium lost |
|---|---|---|---|---|---|
| reads, inspects | −114.86 [−159.17, −70.54] * | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +33.70 [+19.58, +47.82] * | −3.43 [−6.41, −0.45] * |
| reads, does not inspect | +0.00 [+0.00, +0.00] | −1.86 [−5.64, +1.91] | −30.76 [−41.96, −19.56] * | +200.81 [+135.66, +265.97] * | −44.27 [−61.18, −27.35] * |
| does not read, inspects | −91.21 [−130.92, −51.50] * | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +56.10 [+32.02, +80.19] * | −10.58 [−16.59, −4.58] * |
| neither (as a tourist) | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +681.69 [+469.54, +893.85] * | −723.09 [−934.46, −511.72] * |
| reference: tourist share 1.0 | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +681.69 [+469.54, +893.85] * | −723.09 [−934.46, −511.72] * |

## Guard

| Kind · cell | Chains | Stuck | Parked | Idle choosers | Fallbacks | Cell settings wrong | Seconds per chain |
|---|---|---|---|---|---|---|---|
| A · RI | 640 | 0 | 0 | 0 | 0 | 0 | 26.3 |
| A · Rn | 640 | 0 | 0 | 0 | 0 | 0 | 26.2 |
| A · nI | 640 | 0 | 0 | 0 | 0 | 0 | 26.5 |
| A · nn | 640 | 0 | 0 | 0 | 0 | 0 | 26.3 |
| A · ref | 640 | 0 | 0 | 0 | 0 | 0 | 26.3 |
| B · RI | 280 | 0 | 0 | 0 | 0 | 0 | 53.1 |
| B · Rn | 280 | 0 | 0 | 0 | 0 | 0 | 52.7 |
| B · nI | 280 | 0 | 0 | 0 | 0 | 0 | 53.4 |
| B · nn | 280 | 0 | 0 | 0 | 0 | 0 | 52.6 |
| B · ref | 280 | 0 | 0 | 0 | 0 | 0 | 52.0 |
| D · RI | 80 | 0 | 0 | 0 | 0 | 0 | 27.2 |
| D · Rn | 80 | 0 | 0 | 0 | 0 | 0 | 27.2 |
| D · nI | 80 | 0 | 0 | 0 | 0 | 0 | 27.6 |
| D · nn | 80 | 0 | 0 | 0 | 0 | 0 | 27.3 |
| D · ref | 80 | 0 | 0 | 0 | 0 | 0 | 27.2 |

## Reading (written after the results)

**Bottom line: inspection, not reading ratings, is what stops a stall from cashing in its good name. Reading ratings, not inspection, is what makes a reputation pay, and inspection shrinks what a reputation is worth.** All four confirmatory predictions are supported (PC1–PC4).

Simple effects (one factor within one level of the other) are computed after the results from the per-seed values in `runs/check_vs_read.json.gz`, paired, 95% t over 20 seeds, unadjusted. They are exploratory.

1. **Cashing in, no inspectors (PC1, PC2).** A genuine stall that switches to cheap goods under its name gains +$466.61 per stall when locals neither read nor inspect. It gains −$20.27 when locals only inspect, +$165.42 when they only read, and −$75.79 when they do both. Inspection's main effect (−$364.05) is about twice reading's (−$178.35). The two overlap (interaction +$245.66). Reading cuts the gain by $301.19 [$203.61, $398.76] when locals do not inspect, but by only $55.52 [$27.16, $83.89] when they do. Locals who inspect leave little for ratings to catch. The best day to cash in moves with this. Where nobody checks, 53 of 60 stalls do best by cashing in at day 20, the earliest candidate. Where locals inspect, most do best at day 30, the candidate with the shortest period of cheap goods.
2. **How cashing in loses (PC6 decomposition, exploratory).** Where locals inspect, the loss is buyers who inspected and walked away: −$114.86 with reading, −$91.21 without. Where locals only read, it comes through ranking: the stall is outranked (−$30.76) and loses its price premium (−$44.27). Ratings falling below the buyers' threshold contribute nothing distinguishable from 0 (−$1.86 [−$5.64, +$1.91]). The summary's decomposition table leaves out one component, buyers gained after the bust-out, and two terms near 0 (ad and fines, at most $0.01). Buyers gained are +$8.79 in RI, +$41.49 in Rn, +$25.43 in nI, and +$508.00 in nn and the reference. With these included, the components sum to the unfloored gain in every cell. For nn: 681.69 + 508.00 − 723.09 = 466.60.
3. **With inspectors (detect_scale 1).** Cashing in loses in every cell (−$356.46 to −$411.35 per stall), and no stall's floored gain is above 0. Buyer behaviour adds little on top. Inspection's main effect is −$49.34 [−$97.42, −$1.25]. Reading's is −$5.55, and the interaction −$1.13, both with intervals that include 0. PC2's analogue is not supported. Enforcement alone holds the boundary here, as in the verification run.
4. **Reputation (PC3, PC4).** At prior_n 400, E is +$8,050.68 per owner when locals read and do not inspect, and +$1,825.39 when they read and inspect. It is negative when they do not read: −$6,020.85 when they inspect, −$4,077.21 when they do neither. Reading's main effect (+$9,987.06) is about 2.4 times inspection's (−$4,084.47). Among readers, inspection lowers E by $6,225.29 [$4,533.20, $7,917.38]: buyers who check quality themselves lean less on the name. For the seller, buyers' own verification and a reputation are substitutes. At prior_n 0 the signs are the same at about a thirtieth of the size: reading +$262.29, inspection −$154.10, interaction −$196.88, all with intervals excluding 0. The all-tourist reference reproduces, on fresh seeds, the earlier reversal where nobody reads ratings: a slow-rated rival gains (E −$4,077.21 [−$5,232.32, −$2,922.10]).
5. **Who is protected (PC6, exploratory).** Locals' checking protects locals, not tourists. Without inspectors, tourists' shortfall share stays at 0.613, and their surplus at about −$15.3 per buyer-day, in every cell. Meanwhile deceptive stalls' share of units falls from 0.654 (neither) to 0.412 (inspect only), 0.299 (read only) and 0.296 (both). Deceptive stalls lose locals' purchases and keep tourists'. Enforcement is what reaches tourists: at detect_scale 1 their shortfall share is about 0.28 in every cell. Locals do best when they read and do not inspect: surplus +$10.46 per buyer-day, against +$8.06 with both and +$3.11 inspecting only (shortfall share 0.109). Reading lowers deceptive stalls' share of units more than inspection does, yet inspection lowers the cash-in gain more. The two measure different things: the first is market-wide sales of stalls that are deceptive from the start; the second is the gain to a genuine stall that switches.

## Caveats

- **One stylized market.** Tourist share is 0.4, there are no experts, and each local behaviour is all or nothing: inspect_prob 1.0 or 0, reads ratings yes or no. Intermediate rates and mixes within the locals are not tested. Sizes, and which factor is larger, may depend on these settings.
- **Main effects average over a large interaction.** In both outcomes the interaction is about as large as the smaller main effect. "Inspection matters more for cashing in" and "reading matters more for reputation" are statements averaged over the other factor. Within inspecting locals, reading still lowers the cash-in gain ($55.52) and raises E ($7,846.24).
- **The neither cell is the all-tourist market.** Reference − neither is exactly 0.00 in every outcome, so G4 holds in the main run, chain for chain. The nn cell is a tourist-only market, not a separate population.
- **detect_scale 1 leaves little room.** Every cell loses there, so the null for PC2's analogue may reflect that floor rather than an absence of buyer effects.
- **Multiplicity.** Many intervals are shown, none adjusted. Only PC1–PC4 are confirmatory.
- **Run record correction.** The run record above was written by the final pass, so it shows commit 9cb3e67 and 0.00 h. The chains were run as follows:
  - Block 1 (seeds 350–359) at commit 4dd5c2d, 5.97 h.
  - Block 2 (seeds 360–369) at commit 9cb3e67, 5.79 h.
  - Total 11.76 h, against 12.3 h projected from the pilot (deviation D4: the G3 timing gate was waived).
  - The commits between 4dd5c2d and 9cb3e67 changed only docs and run notes: `git diff 4dd5c2d 9cb3e67` over `engine/ agents/ analysis/ cli/ configs/ tests/` is empty, so both blocks ran identical code.
  - The load average was 5–6 throughout with 4 workers. Outside processes (the desktop app and browser) used the rest.
  - Logs: `runs/check_vs_read_run.log`, `runs/check_vs_read_stdout_{block1,block2,final}.log`, `runs/queue_check_vs_read.log`.
