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

- Engine `0.17.0`; commit `54584484b5a1eef8b63c605bb38ae1e6d76b4ae5`; uncommitted at run time: ['?? runs/pilot_canal_equity/', '?? runs/pilot_canal_equity_stdout.log', '?? runs/queue_canal_then_equity.sh']
- Script sha256 `576a56f49a65d6605aab742662bebee05c5815eb40c0bf20416c14645e9cb6fc`
- Command: `python -m analysis.brand_equity --ref 60f1ddf --tests 1109 passed, 17 skipped at e9cdc07 (runs/tests_0170.log)`
- Tests: 1109 passed, 17 skipped at e9cdc07 (runs/tests_0170.log)
- Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit
- 90 chains × 30 days on 4 workers (nice 19); wall clock 0.18 h; load average [6.21, 5.67, 4.51] at start, [6.19, 6.14, 5.38] at end; memory at start {'swap_free_mb': 913.69, 'free_pct': 55}, at end {'swap_free_mb': 913.69, 'free_pct': 56}; memory-guard pauses: 0
- Seeds 900-902 (3), paired
- Sampled owners per seed: 900: s14, s27, s41; 901: s33, s32, s09; 902: s29, s45, s44

## Gate

pilot (this is the pilot)

### The royalty enters no decision

Code (0.17.0): `engine/licensing.py` `royalty_cents` is the only use of `licensing.royalty` besides validation and the licence record; its one caller is `BazaarEngine.purchase` (`engine/bazaar.py`), after the sale, adding to the licensee's `royalty_paid_cents` and the owner's `royalty_received_cents` (skipped for white labels). Those fields are read only by profit (`engine/days.py` `stall_profit`, the outcome's `profit_by_stall_cents` and `seller_by_type`). Profit reaches decisions only through `revise` (off: brands require evolution off) and the `yesterday` ledger, read only by `rule_genuine_rational_v2`, which these chains do not run (rule_honest via rule_genuine_bust_at with nothing scheduled, rule_deceptive). Buyers never see a royalty.

Replay: seed 900, t100, both qualities, 3 owners, R at royalty 0.05 and 0.25 against 0.10.

| Quality | Owner | Royalty | Days identical (all stalls' units, price, revenue, cost, ad, fines, catches) | Same licensees | Royalties differ | Recompute exact | Pass |
|---|---|---|---|---|---|---|---|
| contract | s14 | 0.05 | 30/30 | yes | yes | yes | yes |
| contract | s14 | 0.25 | 30/30 | yes | yes | yes | yes |
| contract | s27 | 0.05 | 30/30 | yes | yes | yes | yes |
| contract | s27 | 0.25 | 30/30 | yes | yes | yes | yes |
| contract | s41 | 0.05 | 30/30 | yes | yes | yes | yes |
| contract | s41 | 0.25 | 30/30 | yes | yes | yes | yes |
| cheap | s14 | 0.05 | 30/30 | yes | yes | yes | yes |
| cheap | s14 | 0.25 | 30/30 | yes | yes | yes | yes |
| cheap | s27 | 0.05 | 30/30 | yes | yes | yes | yes |
| cheap | s27 | 0.25 | 30/30 | yes | yes | yes | yes |
| cheap | s41 | 0.05 | 30/30 | yes | yes | yes | yes |
| cheap | s41 | 0.25 | 30/30 | yes | yes | yes | yes |

Result: **pass**.

J identity (J from stall profit = J from revenue − cost − ad − fines − switch, royalties cancelled): 108/108 owner-chains to the cent; largest split residual 0.000000 cents.

## Predictions

$ per owner over days 10–30 (per-seed mean of 3 owners). PQ1–PQ3 confirmatory; the rest exploratory.

| Prediction | Estimate ($) | Verdict |
|---|---|---|
| **PQ1**: contract, t40: name effect | +21,258.61 [+7,287.18, +35,230.05] * | supported |
| **PQ2**: contract: name effect at t40 − at t100 | −365.87 [−1,230.13, +498.39] | not supported (interval includes 0) |
| **PQ3**: t40: name effect, contract − cheap | +15,880.88 [+3,812.09, +27,949.68] * | supported |
| **PQ4**: contract, t100: name effect ≤ 0 (exploratory) | +21,624.48 [+6,861.88, +36,387.09] * | contradicted (interval on the opposite side of 0) |
| **name contract t40**: contract, t40: name effect (all cells) | +21,258.61 [+7,287.18, +35,230.05] * | interval excludes 0 |
| **composition contract t40**: contract, t40: composition effect | +6,793.09 [−9,180.21, +22,766.38] | interval includes 0 |
| **name contract t100**: contract, t100: name effect (all cells) | +21,624.48 [+6,861.88, +36,387.09] * | interval excludes 0 |
| **composition contract t100**: contract, t100: composition effect | +11,070.02 [−5,959.20, +28,099.23] | interval includes 0 |
| **name cheap t40**: cheap, t40: name effect (all cells) | +5,377.73 [+3,425.19, +7,330.27] * | interval excludes 0 |
| **composition cheap t40**: cheap, t40: composition effect | −19,318.32 [−32,957.62, −5,679.02] * | interval excludes 0 |
| **name cheap t100**: cheap, t100: name effect (all cells) | +13,698.10 [+4,088.19, +23,308.02] * | interval excludes 0 |
| **composition cheap t100**: cheap, t100: composition effect | −29,490.60 [−52,760.93, −6,220.26] * | interval excludes 0 |

## Joint profit and its parts

J per owner and its 6 licensees, days 10–30, $.

| Cell | J never | J W | J R | Composition W − never | Name R − W | Licensing R − never |
|---|---|---|---|---|---|---|
| contract, t40 | −4,625.48 [−13,613.03, +4,362.08] | +2,167.61 [−6,135.79, +10,471.01] | +23,426.23 [+2,472.32, +44,380.14] * | +6,793.09 [−9,180.21, +22,766.38] | +21,258.61 [+7,287.18, +35,230.05] * | +28,051.70 [+2,710.05, +53,393.36] * |
| contract, t100 | −9,079.20 [−17,586.98, −571.43] * | +1,990.81 [−7,256.30, +11,237.93] | +23,615.30 [+1,199.56, +46,031.04] * | +11,070.02 [−5,959.20, +28,099.23] | +21,624.48 [+6,861.88, +36,387.09] * | +32,694.50 [+4,994.86, +60,394.15] * |
| cheap, t40 | −4,625.48 [−13,613.03, +4,362.08] | −23,943.79 [−37,983.11, −9,904.47] * | −18,566.06 [−30,663.00, −6,469.12] * | −19,318.32 [−32,957.62, −5,679.02] * | +5,377.73 [+3,425.19, +7,330.27] * | −13,940.59 [−25,977.55, −1,903.62] * |
| cheap, t100 | −9,079.20 [−17,586.98, −571.43] * | −38,569.80 [−62,930.25, −14,209.36] * | −24,871.70 [−41,584.40, −8,158.99] * | −29,490.60 [−52,760.93, −6,220.26] * | +13,698.10 [+4,088.19, +23,308.02] * | −15,792.49 [−34,430.74, +2,845.75] |

Name effect split (R − W, $; the parts add up to the name effect):

| Cell | Owner own sales | Licensee sales | Licensee prices | Licensee ad spend | Fines |
|---|---|---|---|---|---|
| contract, t40 | +1,495.38 [−3,411.13, +6,401.89] | +4,207.89 [−763.24, +9,179.03] | +15,556.44 [+6,884.10, +24,228.79] * | −1.10 [−3.82, +1.62] | +0.00 [+0.00, +0.00] |
| contract, t100 | +1,641.46 [−4,113.03, +7,395.94] | +4,184.02 [−990.09, +9,358.13] | +15,799.00 [+6,467.70, +25,130.29] * | +0.01 [−4.34, +4.36] | +0.00 [+0.00, +0.00] |
| cheap, t40 | −2,757.13 [−5,357.75, −156.51] * | +204.52 [−616.43, +1,025.48] | +7,162.14 [+3,869.26, +10,455.03] * | +2.86 [−27.08, +32.81] | +765.33 [−252.96, +1,783.63] |
| cheap, t100 | +677.54 [−400.87, +1,755.96] | −150.06 [−1,344.05, +1,043.94] | +12,769.56 [+5,984.60, +19,554.51] * | −16.27 [−80.75, +48.20] | +417.33 [−1,890.32, +2,724.99] |

Units and prices, days 10–30:

| Cell | Licensee units never / W / R | Licensee mean price W / R ($) | Owner units never / W / R |
|---|---|---|---|
| contract, t40 | 237.4 / 972.6 / 606.4 | 58.74 / 92.80 | 125.4 / 50.0 / 79.0 |
| contract, t100 | 318.4 / 984.3 / 611.2 | 58.50 / 92.80 | 114.9 / 48.0 / 80.8 |
| cheap, t40 | 237.4 / 306.8 / 271.0 | 44.69 / 73.78 | 125.4 / 121.0 / 101.2 |
| cheap, t100 | 318.4 / 506.7 / 456.1 | 45.76 / 75.32 | 114.9 / 101.4 / 226.7 |

## Owner's gain and licensee profit by royalty

Owner's gain = owner's 30-day profit − never. R by the exact recompute at each royalty; W has no royalty. Licensee profit: per licensee, days 10–30.

| Cell | Owner gain R, 0.05 | Owner gain R, 0.10 | Owner gain R, 0.15 | Owner gain R, 0.25 | Owner gain W |
|---|---|---|---|---|---|
| contract, t40 | +1,486.36 [−821.37, +3,794.10] | +4,356.66 [+231.63, +8,481.68] * | +7,226.95 [+412.78, +14,041.12] * | +12,967.54 [+379.93, +25,555.15] * | −2,879.31 [−5,228.91, −529.71] * |
| contract, t100 | +2,038.71 [−1,617.21, +5,694.64] | +4,918.45 [−40.54, +9,877.44] | +7,798.18 [+265.19, +15,331.17] * | +13,557.65 [−1.13, +27,116.43] | −2,482.47 [−4,240.14, −724.81] * |
| cheap, t40 | −1,943.80 [−5,251.31, +1,363.72] | −953.65 [−4,368.02, +2,460.72] | +36.54 [−3,608.24, +3,681.33] | +2,017.04 [−2,373.14, +6,407.23] | −176.94 [−1,263.46, +909.58] |
| cheap, t100 | +1,771.83 [−828.71, +4,372.36] | +3,460.70 [−17.76, +6,939.17] | +5,149.57 [+669.76, +9,629.38] * | +8,527.24 [+1,903.75, +15,150.73] * | −594.56 [−1,563.40, +374.28] |

| Cell | Licensee profit never | W | R, 0.05 | R, 0.10 | R, 0.15 | R, 0.25 |
|---|---|---|---|---|---|---|
| contract, t40 | −1,522.85 [−2,459.80, −585.89] * | +89.22 [−1,581.73, +1,760.17] | +2,904.71 [−332.57, +6,141.99] | +2,426.33 [−314.76, +5,167.42] | +1,947.95 [−296.96, +4,192.85] | +991.18 [−261.38, +2,243.74] |
| contract, t100 | −2,193.19 [−3,200.49, −1,185.89] * | +65.56 [−1,832.15, +1,963.27] | +2,916.11 [−644.75, +6,476.96] | +2,436.15 [−585.56, +5,457.87] | +1,956.20 [−526.38, +4,438.77] | +996.29 [−408.02, +2,400.59] |
| cheap, t40 | −1,522.85 [−2,459.80, −585.89] * | −4,713.08 [−7,450.02, −1,976.13] * | −3,522.31 [−5,753.02, −1,291.60] * | −3,687.34 [−6,027.37, −1,347.30] * | −3,852.37 [−6,302.08, −1,402.65] * | −4,182.45 [−6,852.07, −1,512.83] * |
| cheap, t100 | −2,193.19 [−3,200.49, −1,185.89] * | −7,009.19 [−11,415.14, −2,603.25] * | −5,120.58 [−8,464.52, −1,776.64] * | −5,402.05 [−8,883.51, −1,920.60] * | −5,683.53 [−9,307.44, −2,059.62] * | −6,246.48 [−10,167.66, −2,325.29] * |

## Rating paths

Mean over owners (unrated = 0.5), end of days 1, 9, 10, 15, 20, 25, 30: the owner's brand in never, R and W, and the mean of the 6 white labels in W.

| Cell | Series | 1 | 9 | 10 | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|---|---|---|
| contract, t40 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| contract, t40 | owner brand, R | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| contract, t40 | owner brand, W | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| contract, t40 | white labels, W | 0.639 | 0.648 | 0.972 | 1.000 | 1.000 | 1.000 | 1.000 |
| contract, t100 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| contract, t100 | owner brand, R | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| contract, t100 | owner brand, W | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| contract, t100 | white labels, W | 0.593 | 0.630 | 0.991 | 1.000 | 1.000 | 1.000 | 1.000 |
| cheap, t40 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| cheap, t40 | owner brand, R | 1.000 | 1.000 | 0.802 | 0.383 | 0.263 | 0.269 | 0.229 |
| cheap, t40 | owner brand, W | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| cheap, t40 | white labels, W | 0.639 | 0.648 | 0.111 | 0.000 | 0.000 | 0.000 | 0.000 |
| cheap, t100 | owner, never | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| cheap, t100 | owner brand, R | 1.000 | 1.000 | 0.811 | 0.401 | 0.354 | 0.358 | 0.335 |
| cheap, t100 | owner brand, W | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| cheap, t100 | white labels, W | 0.593 | 0.630 | 0.111 | 0.000 | 0.000 | 0.000 | 0.000 |

## PQ5: buyers by profile, R − W (exploratory)

Days 10–30. Shortfall in points of purchases; surplus in $ per buyer of the profile.

| Cell | tourist: shortfall (pts) | local: shortfall (pts) | expert: shortfall (pts) | tourist: surplus ($) | local: surplus ($) | expert: surplus ($) |
|---|---|---|---|---|---|---|
| contract, t40 | +2.7 [+1.7, +3.7] * | +0.0 [−0.1, +0.2] | +0.0 [+0.0, +0.0] | −12.36 [−21.04, −3.67] * | −10.20 [−15.47, −4.92] * | −10.19 [−17.56, −2.83] * |
| contract, t100 | +1.7 [+0.3, +3.1] * | – | – | −11.83 [−18.99, −4.67] * | – | – |
| cheap, t40 | −1.7 [−4.0, +0.6] | +0.4 [+0.1, +0.8] * | +0.0 [+0.0, +0.0] | −4.04 [−5.76, −2.31] * | −0.35 [−0.63, −0.07] * | −0.14 [−0.31, +0.04] |
| cheap, t100 | −1.0 [−2.6, +0.5] | – | – | −2.75 [−3.97, −1.52] * | – | – |

## Stuck, parked and idle buyers

| Chains | Count | Buyer-days | Stuck | Parked | Idle choosers | Invalid actions |
|---|---|---|---|---|---|---|
| R · cheap · t100 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| R · cheap · t40 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| R · contract · t100 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| R · contract · t40 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| W · cheap · t100 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| W · cheap · t40 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| W · contract · t100 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| W · contract · t40 | 9 | 40,500 | 0 | 0 | 0 | 0 |
| never · - · t100 | 3 | 13,500 | 0 | 0 | 0 | 0 |
| never · - · t40 | 3 | 13,500 | 0 | 0 | 0 | 0 |

## Flags

- none

## Reading (written after the results)

READING_PLACEHOLDER

## Caveats

CAVEATS_PLACEHOLDER
