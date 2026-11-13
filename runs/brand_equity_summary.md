# Brand Equity: what a reputation earns

Spec "Brand Equity" (2026-11-12); predictions fixed 2026-11-12, before any run. Pilot gate: `runs/pilot_canal_equity.md`.

## Design (prespecified)

- Question: what does a reputation earn, apart from the extra stalls and the quality behind it?
- Engine 0.17.0. Market as the licensing run, detect_scale 1, owner not liable: choice-set demand (m 3, gamma 0), 150 buyers, budget 1.25 × base, bargain hunters 0.2; D = 30 known; ratings public (memory 0.7); brands on (premium 0.4); naive deceptive sellers (fresh reopening); 2 patrolling inspectors, not uniformed; collectible fines; every genuine stall honest.
- Owners: 3 per seed from `default_rng([seed, 17])`. Licence option fixed: N 6 from day 10. Arms per owner: never; R = licensees under the owner's brand (royalty 0.10); W = the same stalls under white labels (one fresh unrated brand each, no royalty, priced from its own rating by the morning rule).
- Conditions: licence quality {contract, cheap} × verification {t40 locals inspect, t100}. Seeds 300–329, paired.
- Primary measure, per owner: J = owner profit + its 6 licensees' profit, day 10 to 30 (royalties cancel). Name effect = J(R) − J(W). Composition effect = J(W) − J(never). The name effect is split into owner own sales, licensee sales, licensee prices, licensee ad spend and fines (they add up exactly). Owner's gain at royalty 0.05, 0.10, 0.15, 0.25 by the exact recompute, after the no-decision check below.
- Predictions (verbatim from the spec):
  - PQ1 (confirmatory): contract, t40: name effect > 0.
  - PQ2 (confirmatory): contract: name effect at t40 − at t100 > 0 (the reputation earns through buyers who read ratings).
  - PQ3 (confirmatory): t40: name effect, contract − cheap > 0 (renting a reputation earns more than spending it).
  - PQ4 (exploratory): contract, t100: name effect ≤ 0 (tourists see the premium price, not the rating).
  - PQ5 (exploratory): harm and benefit by buyer profile, R − W.
- Analysis: per seed the mean over 3 owners; mean and 95% t over seeds; unadjusted.

## Run record

- Engine `0.17.0`; commit `0762786ef51751bc3dd68cab47cc14ad9574e82c`; uncommitted at run time: ['?? runs/brand_equity_run.log', '?? runs/brand_equity_stdout.log', '?? runs/canal_street.csv', '?? runs/canal_street.json.gz', '?? runs/canal_street_run.log', '?? runs/canal_street_stdout.log', '?? runs/canal_street_summary.md', '?? runs/queue_canal_then_equity.log']
- Script sha256 `576a56f49a65d6605aab742662bebee05c5815eb40c0bf20416c14645e9cb6fc`
- Command: `python -m analysis.brand_equity --seeds 300-329 --workers 4 --tests 1109 passed, 17 skipped at e9cdc07 (runs/tests_0170.log) --gate Pilot gate G1–G5 passed at 5458448 (runs/pilot_canal_equity.md)`
- Tests: 1109 passed, 17 skipped at e9cdc07 (runs/tests_0170.log)
- Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit
- 792 chains × 30 days on 4 workers (nice 19); wall clock 1.72 h; load average [8.3, 7.44, 6.89] at start, [7.38, 6.72, 6.5] at end; memory at start {'swap_free_mb': 913.69, 'free_pct': 51}, at end {'swap_free_mb': 913.69, 'free_pct': 52}; memory-guard pauses: 0
- Seeds 300-329 (30), paired
- Sampled owners per seed: 300: s12, s14, s46; 301: s10, s08, s39; 302: s17, s45, s31; 303: s13, s31, s06; 304: s40, s38, s10; 305: s31, s01, s04; 306: s06, s36, s31; 307: s38, s30, s02; 308: s36, s11, s19; 309: s08, s05, s26; 310: s31, s19, s00; 311: s31, s08, s38; 312: s14, s44, s13; 313: s47, s05, s45; 314: s28, s45, s16; 315: s44, s02, s05; 316: s41, s29, s35; 317: s35, s42, s11; 318: s13, s40, s24; 319: s12, s15, s11; 320: s45, s23, s13; 321: s34, s40, s09; 322: s08, s05, s33; 323: s30, s41, s37; 324: s41, s45, s20; 325: s44, s04, s42; 326: s23, s16, s19; 327: s16, s06, s21; 328: s29, s23, s37; 329: s12, s15, s17

## Gate

Pilot gate G1–G5 passed at 5458448 (runs/pilot_canal_equity.md)

### The royalty enters no decision

Code (0.17.0): `engine/licensing.py` `royalty_cents` is the only use of `licensing.royalty` besides validation and the licence record; its one caller is `BazaarEngine.purchase` (`engine/bazaar.py`), after the sale, adding to the licensee's `royalty_paid_cents` and the owner's `royalty_received_cents` (skipped for white labels). Those fields are read only by profit (`engine/days.py` `stall_profit`, the outcome's `profit_by_stall_cents` and `seller_by_type`). Profit reaches decisions only through `revise` (off: brands require evolution off) and the `yesterday` ledger, read only by `rule_genuine_rational_v2`, which these chains do not run (rule_honest via rule_genuine_bust_at with nothing scheduled, rule_deceptive). Buyers never see a royalty.

Replay: seed 300, t100, both qualities, 3 owners, R at royalty 0.05 and 0.25 against 0.10.

| Quality | Owner | Royalty | Days identical (all stalls' units, price, revenue, cost, ad, fines, catches) | Same licensees | Royalties differ | Recompute exact | Pass |
|---|---|---|---|---|---|---|---|
| contract | s12 | 0.05 | 30/30 | yes | yes | yes | yes |
| contract | s12 | 0.25 | 30/30 | yes | yes | yes | yes |
| contract | s14 | 0.05 | 30/30 | yes | yes | yes | yes |
| contract | s14 | 0.25 | 30/30 | yes | yes | yes | yes |
| contract | s46 | 0.05 | 30/30 | yes | yes | yes | yes |
| contract | s46 | 0.25 | 30/30 | yes | yes | yes | yes |
| cheap | s12 | 0.05 | 30/30 | yes | yes | yes | yes |
| cheap | s12 | 0.25 | 30/30 | yes | yes | yes | yes |
| cheap | s14 | 0.05 | 30/30 | yes | yes | yes | yes |
| cheap | s14 | 0.25 | 30/30 | yes | yes | yes | yes |
| cheap | s46 | 0.05 | 30/30 | yes | yes | yes | yes |
| cheap | s46 | 0.25 | 30/30 | yes | yes | yes | yes |

Result: **pass**.

J identity (J from stall profit = J from revenue − cost − ad − fines − switch, royalties cancelled): 1080/1080 owner-chains to the cent; largest split residual 0.000000 cents.

## Predictions

$ per owner over days 10–30 (per-seed mean of 3 owners). PQ1–PQ3 confirmatory; the rest exploratory.

| Prediction | Estimate ($) | Verdict |
|---|---|---|
| **PQ1**: contract, t40: name effect | +14,818.74 [+11,923.40, +17,714.07] * | supported |
| **PQ2**: contract: name effect at t40 − at t100 | −459.83 [−634.25, −285.42] * | contradicted (interval on the opposite side of 0) |
| **PQ3**: t40: name effect, contract − cheap | +12,319.39 [+9,755.81, +14,882.97] * | supported |
| **PQ4**: contract, t100: name effect ≤ 0 (exploratory) | +15,278.57 [+12,256.37, +18,300.78] * | contradicted (interval on the opposite side of 0) |
| **name contract t40**: contract, t40: name effect (all cells) | +14,818.74 [+11,923.40, +17,714.07] * | interval excludes 0 |
| **composition contract t40**: contract, t40: composition effect | +6,813.34 [+4,857.38, +8,769.31] * | interval excludes 0 |
| **name contract t100**: contract, t100: name effect (all cells) | +15,278.57 [+12,256.37, +18,300.78] * | interval excludes 0 |
| **composition contract t100**: contract, t100: composition effect | +9,877.15 [+7,468.60, +12,285.70] * | interval excludes 0 |
| **name cheap t40**: cheap, t40: name effect (all cells) | +2,499.35 [+1,999.92, +2,998.78] * | interval excludes 0 |
| **composition cheap t40**: cheap, t40: composition effect | −12,777.96 [−14,991.78, −10,564.14] * | interval excludes 0 |
| **name cheap t100**: cheap, t100: name effect (all cells) | +8,694.45 [+7,138.42, +10,250.48] * | interval excludes 0 |
| **composition cheap t100**: cheap, t100: composition effect | −19,787.03 [−23,264.73, −16,309.34] * | interval excludes 0 |

## Joint profit and its parts

J per owner and its 6 licensees, days 10–30, $.

| Cell | J never | J W | J R | Composition W − never | Name R − W | Licensing R − never |
|---|---|---|---|---|---|---|
| contract, t40 | −3,716.67 [−4,609.45, −2,823.89] * | +3,096.68 [+1,712.15, +4,481.21] * | +17,915.41 [+14,427.21, +21,403.62] * | +6,813.34 [+4,857.38, +8,769.31] * | +14,818.74 [+11,923.40, +17,714.07] * | +21,632.08 [+17,587.04, +25,677.13] * |
| contract, t100 | −6,750.70 [−8,207.17, −5,294.22] * | +3,126.45 [+1,698.51, +4,554.39] * | +18,405.02 [+14,794.91, +22,015.13] * | +9,877.15 [+7,468.60, +12,285.70] * | +15,278.57 [+12,256.37, +18,300.78] * | +25,155.72 [+20,660.78, +29,650.66] * |
| cheap, t40 | −3,716.67 [−4,609.45, −2,823.89] * | −16,494.62 [−19,311.61, −13,677.64] * | −13,995.28 [−16,443.73, −11,546.82] * | −12,777.96 [−14,991.78, −10,564.14] * | +2,499.35 [+1,999.92, +2,998.78] * | −10,278.61 [−12,129.71, −8,427.51] * |
| cheap, t100 | −6,750.70 [−8,207.17, −5,294.22] * | −26,537.73 [−30,840.07, −22,235.40] * | −17,843.28 [−20,680.75, −15,005.81] * | −19,787.03 [−23,264.73, −16,309.34] * | +8,694.45 [+7,138.42, +10,250.48] * | −11,092.58 [−13,192.57, −8,992.60] * |

Name effect split (R − W, $; the parts add up to the name effect):

| Cell | Owner own sales | Licensee sales | Licensee prices | Licensee ad spend | Fines |
|---|---|---|---|---|---|
| contract, t40 | +696.30 [+460.83, +931.78] * | +3,616.21 [+2,793.03, +4,439.39] * | +10,506.10 [+7,998.35, +13,013.85] * | +0.13 [−0.56, +0.82] | +0.00 [+0.00, +0.00] |
| contract, t100 | +799.01 [+534.06, +1,063.96] * | +3,595.14 [+2,746.54, +4,443.75] * | +10,884.63 [+8,235.20, +13,534.06] * | −0.21 [−0.72, +0.30] | +0.00 [+0.00, +0.00] |
| cheap, t40 | −2,322.81 [−2,823.59, −1,822.03] * | +198.54 [+46.51, +350.57] * | +4,719.60 [+3,867.58, +5,571.61] * | +2.82 [−0.57, +6.21] | −98.80 [−235.15, +37.55] |
| cheap, t100 | +135.65 [−87.49, +358.78] | +16.52 [−153.08, +186.12] | +8,455.85 [+6,903.48, +10,008.23] * | −0.10 [−4.79, +4.59] | +86.53 [−60.51, +233.58] |

Units and prices, days 10–30:

| Cell | Licensee units never / W / R | Licensee mean price W / R ($) | Owner units never / W / R |
|---|---|---|---|
| contract, t40 | 245.6 / 962.9 / 664.6 | 43.25 / 65.49 | 148.1 / 66.8 / 94.7 |
| contract, t100 | 339.0 / 984.1 / 681.1 | 43.27 / 65.49 | 135.7 / 64.0 / 95.8 |
| cheap, t40 | 245.6 / 298.7 / 261.8 | 32.84 / 52.61 | 148.1 / 147.0 / 110.0 |
| cheap, t100 | 339.0 / 505.7 / 446.7 | 33.32 / 53.25 | 135.7 / 117.6 / 232.1 |

## Owner's gain and licensee profit by royalty

Owner's gain = owner's 30-day profit − never. R by the exact recompute at each royalty; W has no royalty. Licensee profit: per licensee, days 10–30.

| Cell | Owner gain R, 0.05 | Owner gain R, 0.10 | Owner gain R, 0.15 | Owner gain R, 0.25 | Owner gain W |
|---|---|---|---|---|---|
| contract, t40 | +744.97 [+475.39, +1,014.55] * | +2,980.27 [+2,393.10, +3,567.44] * | +5,215.57 [+4,217.00, +6,214.13] * | +9,686.16 [+7,830.73, +11,541.59] * | −2,186.62 [−2,634.26, −1,738.98] * |
| contract, t100 | +1,164.05 [+821.61, +1,506.49] * | +3,458.91 [+2,760.78, +4,157.04] * | +5,753.76 [+4,628.81, +6,878.71] * | +10,343.47 [+8,332.04, +12,354.90] * | −1,929.81 [−2,321.57, −1,538.04] * |
| cheap, t40 | −1,668.72 [−2,085.41, −1,252.03] * | −973.83 [−1,307.43, −640.23] * | −278.98 [−560.31, +2.34] | +1,110.80 [+786.14, +1,435.47] * | −40.80 [−107.96, +26.36] |
| cheap, t100 | +835.16 [+536.64, +1,133.68] * | +2,037.36 [+1,594.70, +2,480.03] * | +3,239.61 [+2,607.13, +3,872.10] * | +5,643.96 [+4,595.08, +6,692.83] * | −502.65 [−643.74, −361.56] * |

| Cell | Licensee profit never | W | R, 0.05 | R, 0.10 | R, 0.15 | R, 0.25 |
|---|---|---|---|---|---|---|
| contract, t40 | −1,231.13 [−1,460.02, −1,002.25] * | +268.86 [+65.73, +472.00] * | +2,250.05 [+1,797.20, +2,702.90] * | +1,877.50 [+1,496.23, +2,258.77] * | +1,504.95 [+1,194.76, +1,815.15] * | +759.86 [+587.74, +931.97] * |
| contract, t100 | −1,679.14 [−1,984.33, −1,373.94] * | +288.69 [+74.45, +502.93] * | +2,319.47 [+1,848.76, +2,790.19] * | +1,937.00 [+1,540.46, +2,333.53] * | +1,554.52 [+1,231.66, +1,877.38] * | +789.57 [+610.02, +969.13] * |
| cheap, t40 | −1,231.13 [−1,460.02, −1,002.25] * | −3,353.99 [−3,923.61, −2,784.37] * | −2,666.11 [−3,125.79, −2,206.44] * | −2,781.93 [−3,260.52, −2,303.34] * | −2,897.74 [−3,395.37, −2,400.10] * | −3,129.37 [−3,665.41, −2,593.33] * |
| cheap, t100 | −1,679.14 [−1,984.33, −1,373.94] * | −4,893.20 [−5,688.44, −4,097.96] * | −3,667.09 [−4,253.23, −3,080.96] * | −3,867.46 [−4,488.39, −3,246.53] * | −4,067.84 [−4,723.78, −3,411.90] * | −4,468.56 [−5,195.04, −3,742.08] * |

## Rating paths

Mean over owners (unrated = 0.5), end of days 1, 9, 10, 15, 20, 25, 30: the owner's brand in never, R and W, and the mean of the 6 white labels in W.

| Cell | Series | 1 | 9 | 10 | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|---|---|---|
| contract, t40 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| contract, t40 | owner brand, R | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| contract, t40 | owner brand, W | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| contract, t40 | white labels, W | 0.509 | 0.583 | 0.983 | 1.000 | 1.000 | 1.000 | 1.000 |
| contract, t100 | owner, never | 0.994 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| contract, t100 | owner brand, R | 0.994 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| contract, t100 | owner brand, W | 0.994 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| contract, t100 | white labels, W | 0.540 | 0.621 | 0.996 | 1.000 | 1.000 | 1.000 | 1.000 |
| cheap, t40 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| cheap, t40 | owner brand, R | 1.000 | 1.000 | 0.824 | 0.446 | 0.302 | 0.255 | 0.256 |
| cheap, t40 | owner brand, W | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| cheap, t40 | white labels, W | 0.509 | 0.583 | 0.139 | 0.001 | 0.000 | 0.000 | 0.000 |
| cheap, t100 | owner, never | 0.994 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| cheap, t100 | owner brand, R | 0.994 | 1.000 | 0.801 | 0.429 | 0.361 | 0.348 | 0.351 |
| cheap, t100 | owner brand, W | 0.994 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| cheap, t100 | white labels, W | 0.540 | 0.621 | 0.115 | 0.000 | 0.000 | 0.000 | 0.000 |

## PQ5: buyers by profile, R − W (exploratory)

Days 10–30. Shortfall in points of purchases; surplus in $ per buyer of the profile.

| Cell | tourist: shortfall (pts) | local: shortfall (pts) | expert: shortfall (pts) | tourist: surplus ($) | local: surplus ($) | expert: surplus ($) |
|---|---|---|---|---|---|---|
| contract, t40 | +2.5 [+2.2, +2.9] * | +0.0 [+0.0, +0.0] * | +0.0 [+0.0, +0.0] | −8.32 [−9.74, −6.89] * | −6.81 [−8.03, −5.59] * | −6.64 [−7.85, −5.43] * |
| contract, t100 | +1.7 [+1.4, +1.9] * | – | – | −7.81 [−9.19, −6.44] * | – | – |
| cheap, t40 | −1.4 [−1.7, −1.2] * | +0.5 [+0.5, +0.6] * | +0.0 [+0.0, +0.0] | −2.95 [−3.46, −2.45] * | −0.31 [−0.38, −0.24] * | −0.07 [−0.09, −0.04] * |
| cheap, t100 | −1.1 [−1.3, −1.0] * | – | – | −1.73 [−2.06, −1.40] * | – | – |

## Stuck, parked and idle buyers

| Chains | Count | Buyer-days | Stuck | Parked | Idle choosers | Invalid actions |
|---|---|---|---|---|---|---|
| R · cheap · t100 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| R · cheap · t40 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| R · contract · t100 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| R · contract · t40 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| W · cheap · t100 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| W · cheap · t40 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| W · contract · t100 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| W · contract · t40 | 90 | 405,000 | 0 | 0 | 0 | 0 |
| never · - · t100 | 30 | 135,000 | 0 | 0 | 0 | 0 |
| never · - · t40 | 30 | 135,000 | 0 | 0 | 0 | 0 |

## Flags

- none

## Reading (written after the results)

- **PQ1 and PQ3 are supported, PQ2 is contradicted, and PQ4 (exploratory) is contradicted. Most of the measured name effect comes from the white-label pricing rule, not from the owner's reputation.**
  - **PQ1:** contract, t40: the name effect is +$14,819 [+11,923, +17,714] per owner over days 10–30.
  - **PQ3:** at t40 it is $12,319 [9,756, 14,883] larger with contract licensees than with cheap ones.
  - **PQ2:** the name effect is $460 [285, 634] *smaller* at t40 than at t100.
  - **PQ4:** at contract, t100 the name effect is +$15,279 [+12,256, +18,301], not ≤ 0.
- **The licensee-price part dominates the name effect, and seconds-type licensees carry it.** In the frozen split (contract, t40), licensee prices account for +$10,506 of +$14,819, licensee sales +$3,616 and the owner's own sales +$696.
  - The following were computed after the run from the cache (days 10–30, paired by seed, same intervals). By licensee type, seconds-type licensees carry +$11,505 [8,875, 14,134] of the name effect and deceptive-type licensees +$2,618 [1,922, 3,313].
  - Under white labels, contract seconds-type stalls post $35.69 against a unit cost of $38.87, a loss on every unit, and sell 2.2 times their R volume. Under R they post the owner's $67.78.
  - Deceptive-type white labels price at the genuine tier and post $66.96, the same as R's $66.75.
  - Contract white labels reach a rating of 0.98 by day 10 and 1.00 by day 15. After the first few days, the R–W price gap is the stall-type tier, not the rating.
  - What the owner's rating itself earns is therefore at most roughly the deceptive-type and owner parts, about $3,300 of $14,800. Those parts are themselves affected by competition from the below-cost seconds-type white labels.
- **Why PQ2 and PQ4 fail.** The name effect works through the price the licensee may post, not through buyers who read ratings. R licensees sell about the same at t40 and t100 (665 and 681 units per owner), and tourists buy them at the owner's price.
- **Cheap licensees spend the owner's rating, and a white label's.**
  - Under R the owner's rating falls from 1.0 to 0.26 by day 30 at t40 and to 0.35 at t100. Cheap white labels fall to 0 by day 15.
  - The owner's own sales part of the name effect is −$2,323 [−2,824, −1,822] at t40 (locals read the fallen rating) and +$136 [−87, +359] at t100.
  - The cheap name effect is +$2,499 at t40 and +$8,694 at t100, again mostly from seconds-type licensees (+$3,553 and +$6,455, post hoc).
- **Composition matters as much as the name.** Composition (W − never) is +$6,813 and +$9,877 with contract licensees (t40, t100), and −$12,778 and −$19,787 with cheap ones. Licensing as a whole (R − never) is +$21,632 and +$25,156 for contract and −$10,279 and −$11,093 for cheap.
- **Owners gain from contract licensing at every royalty tested; with cheap licensees and locals they need 0.25.**
  - Contract: +$745 at 0.05 to +$9,686 at 0.25 (t40), and similar at t100.
  - White labels cost the owner money: −$2,187 at contract, t40. They take its buyers without paying, and its own units fall from 148 to 67.
  - Cheap, t40: −$1,669 at 0.05 and −$974 at 0.10, −$279 [−560, +2] at 0.15, and +$1,111 only at 0.25.
  - Cheap, t100: positive at every royalty (+$835 to +$5,644).
- **Licensees would sign contract licences but not cheap ones.**
  - Contract licensees earn +$760 to +$2,250 each under R, depending on the royalty, against −$1,231 never and +$269 as white labels (t40). So they prefer R at every royalty tested.
  - Cheap licensees lose more under R at every royalty (−$2,666 to −$3,129 at t40) than if they never licensed (−$1,231). This repeats the licensing-checks finding.
- **Buyers pay for the name** (PQ5, exploratory).
  - Contract R against W: every profile loses $6.6–$8.3 of surplus per buyer at R's higher prices. Tourist shortfall rises 2.5 points (t40) and 1.7 points (t100).
  - Cheap: tourist shortfall falls 1.4 and 1.1 points under R, and tourist surplus falls $3.0 and $1.7.

## Caveats

- **The name effect includes the stall-type price tier.** As specified, a white label is priced from its own rating at its stall type's tier, so seconds-type white labels post 0.55 × base. This choice was confirmed before launch.
  - At contract quality that is below unit cost on every unit, so W is not a policy these stalls would choose. It understates their real alternative to licensing the name.
  - With white labels priced at the genuine tier, the name effect would likely be much smaller. That is untested and would need a new engine key.
  - PQ1 and PQ3 hold as specified, but "what a reputation earns" is not identified apart from the tier.
- **Reputations are cheap to build in this market.** With ratings public and memory 0.7, contract white labels rate 0.98 at the end of their first day (day 10) and 1.0 by day 15. The owner's rating advantage over a new brand is short-lived, and a market with slower rating formation could give a larger rating premium.
- **Post-hoc figures.** The figures by licensee stall type in the reading were computed after the run from `runs/brand_equity_cache.jsonl`, not by the frozen script: the name effect by part, licensee prices, unit costs and units. The interval method is the same (`engine.metrics.mean_ci` over per-seed means), and they reproduce the frozen totals exactly.
- **Licensees are drawn from non-genuine stalls.** A contract licence turns a deceptive or seconds stall into an honest one at the owner's quality. The composition effect therefore includes that change to the market, not only the extra stalls.
- **One option and one market.** N = 6 from day 10, owner not liable, detect_scale 1, brand premium 0.4. The royalty affects no decision (checked by replay and by code), so the owner's gain at other rates is an exact recompute, but only within this option.
- **Owners differ widely,** and owner draws repeat across seeds (for example s31 is drawn in 6 of 30 seeds). The intervals treat the per-seed mean of 3 owners as the unit.
- 95% intervals, unadjusted. Only PQ1–PQ3 are confirmatory; every other row, including PQ4 and PQ5, is exploratory.
