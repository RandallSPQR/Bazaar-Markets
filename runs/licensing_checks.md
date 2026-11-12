# Licensing: two checks and a royalty recompute (exploratory)

**Everything in this file is exploratory and was written after the licensing results** (`runs/licensing_summary.md`, engine 0.16.0, ddd6fc2). It changes no prediction or verdict there. Analysis only: no engine change.

<!-- reading -->
## Reading (written after the results)

**BLUF.** At royalty 0.10, owners gain from licensing only through contract licensees. Contract licensees sign (97–100%), add real sales (+72 to +388 units per owner) and leave the owner +$3,443 [2,768, 4,117] at t40 and +$3,804 [2,998, 4,611] at t100. Owner consent changes these gains by an amount not distinguishable from 0. Cheap licensees mostly collect the owner's price on sales they would have made anyway. When enforcement is on and the fines fall on the cheap licensees, almost none would sign (5–16%), so the owners' gain falls to 0. The royalty enters no seller or buyer decision, so every rate below is an exact recompute, not a new run.

- **Royalty.** The code trace and the seed-250 replay (24 chains at 0.05 and 0.25) show identical trading on every stall-day. Only royalties and profit move. All 20 seeds' replays reproduce the saved totals (240 never, 1,440 not-liable, 960 derived liable, 96 replayed liable). The 0.15 column reproduces `runs/licensing_summary.md` exactly.
- **Check (a), cheap licensees.**
  - Units barely change: −16 to +94 per owner over the window, often not distinguishable from 0. Revenue rises because they post the owner's price: about $54–66 a unit against $43–51 under their own name.
  - By the specified measure, 67–80% of royalties are earned on sales the licensee would have made anyway.
  - That measure is a lower bound here. The per-licensee max(0, extra) counts positive noise and ignores negative noise, even though mean extra units are about zero. Pooling extra units with their signs over all licensees gives 80–100%.
  - Where the units come from: at t100, the owner gains +26 to +95 units and the other genuine stalls of the category lose 41–195. At t40 without enforcement, the owner itself loses 11–67 units.
- **Check (a), contract licensees.** These do add sales: +72 to +388 units per owner, with 31–44% of royalties on sales made anyway (31–52% pooled with signs). The units come mostly from the category's other genuine stalls (−29 to −205), and some from the owner (−6 to −43).
- **Check (b), with enforcement on and the owner not liable.** Cheap licensees pay +$866 to +$2,563 more in fines and lose $754–2,239 each against never. 5–16% would accept, and no owner has an option every licensee accepts. The owner's gain falls to 0 at t40 (from +$168 [−52, +387]) and at t100 (from +$2,155 [1,697, 2,613]). This holds at every royalty: at 0.05, 1 of 60 owners has an acceptable option.
- **Check (b), without enforcement (detect_scale 0).** 51–75% of licensees accept, and 0–33 of 60 owners have an option all their licensees accept.
  - t40: the unfloored gain goes from −$51 to −$229 [−409, −49]; the floored gain from +$204 to +$67 [6, 129].
  - t100: the gain goes from +$4,053 to +$200 [40, 359]; 43 of 60 owners are left with never.
- **Check (b), owner liable.** Every licensee signs. Their gain includes the fines they would have paid anyway under their own name ($1,124–2,230 a licensee at t40, $1,772–3,447 at t100), because all fines at a licensee move to the owner. The owner's best option still loses $4,268 (t40) and $5,533 (t100) unfloored, so the floored gain is 0 with or without consent.
- **Across royalties.**
  - A higher royalty raises the owner's unconstrained gain everywhere. In the cheap conditions, it lowers acceptance about as fast. With consent, cheap t100 without enforcement stays at +$200–320 from 0.05 to 0.25, while the unconstrained gain goes from +$1,898 to +$10,594.
  - With consent, contract licensing goes from +$1,191 (t40) and +$1,514 (t100) at 0.05 to +$9,171 and +$9,647 at 0.25. At 0.25, one owner per tourist share has no acceptable option.
<!-- reading -->

## What was done

- **Replay.** Never chains and the licensed chains of the six not-liable conditions were replayed at 0.16.0 with an observer that changes nothing: it wraps `engine.days.reset_for_day` and copies every stall's day ledger (units, revenue, cost, ad spend, fines, switch cost, royalties paid and received, catches, price) before the reset. Owner liable: replayed for seeds 250–251; for every seed the liable ledger is derived from the not-liable one by moving fines at licensees (from the licence day) to the owner.
- **Windows.** Every licensee and every other stall is compared over the licence day b to day 30, licensed chain against the never chain of the same seed, verification level and detect_scale, where the stall trades under its own name and type.
- **Check (a).** Extra units = licensed − never units. Royalty on extra units = royalty × the licensee's mean licensed price × max(0, extra units). Share earned on sales the stall would have made anyway = 1 − (royalty on extra units ÷ royalty paid), per seed over the 3 owners' licensees.
- **Check (b).** A licensee accepts if its profit from day b, licensed (royalties paid and the fines it bears counted), is at least its never-chain profit over the same days. The owner's best option is recomputed over the options every one of its licensees accepts; with none, its alternative is never and its gain is 0.
- **Royalty.** Owner total at royalty r = saved total − royalties received at 0.15 + royalties at r; licensee profit at r = profit at 0.15 + royalties paid at 0.15 − royalties at r. Royalties at r are computed exactly from each licensee's day units and price as the engine charges them (units × round(r × price)); at 0.15 this reproduces every licensee-day's royalty to the cent. This is the spec's gain_0.15 − (0.15 − r) × licensee revenue up to the per-unit rounding.
- Intervals: per-seed mean over the 3 sampled owners (or over their licensees, where marked), 95% t over 20 seeds, unadjusted. Money in $ over the window; units over the window.

## Royalty enters no decision

Code (0.16.0):

- `engine/licensing.py:119` `royalty_cents` is the only use of `licensing.royalty` besides validation (`:43`) and the licence record (`:107`). Its one caller is `BazaarEngine.purchase` (`engine/bazaar.py:698-701`), after the sale is made: it adds to the licensee's `royalty_paid_cents` and the owner's `royalty_received_cents`.
- Those two fields are read only by profit: `engine/days.py:55` `stall_profit`, the outcome's `profit_by_stall_cents` (`engine/bazaar.py:1000`) and `seller_by_type` (`:868-873`), and are zeroed each morning (`engine/days.py:158`).
- Profit reaches decisions in two places only. (1) `engine/days.py:204, 218` passes profits to `revise`, which switches nothing here: brands require `evolution.revise_prob = mutation_prob = 0` (`engine/days.py`, run_days). (2) `reset_for_day` puts yesterday's profit in the stall's `yesterday` ledger, shown to sellers (`engine/bazaar.py:774`); the only policy that reads it is `rule_genuine_rational_v2` (`agents/rule_based.py:238`). These chains run `rule_honest`, `rule_deceptive` and `rule_genuine_bust_at` with nothing scheduled, none of which reads profit or `yesterday` (`agents/rule_based.py:17-110, 254-291`). Buyers never see a royalty.

Replay: seed 250, cheap, tourist share 1.0, detect_scale 1, owner not liable; 3 owners × 4 options at royalty 0.05 and 0.25 against 0.15 (24 comparisons).

| Owner | Option | Royalty | Days identical (all stalls' units, price, revenue, cost, ad, fines, catches) | Window ledgers identical except royalties and profit | Same licensees | Royalties differ |
|---|---|---|---|---|---|---|
| s28 | 2×10 | 0.05 | 30/30 | yes | yes | yes |
| s28 | 2×10 | 0.25 | 30/30 | yes | yes | yes |
| s28 | 2×20 | 0.05 | 30/30 | yes | yes | yes |
| s28 | 2×20 | 0.25 | 30/30 | yes | yes | yes |
| s28 | 6×10 | 0.05 | 30/30 | yes | yes | yes |
| s28 | 6×10 | 0.25 | 30/30 | yes | yes | yes |
| s28 | 6×20 | 0.05 | 30/30 | yes | yes | yes |
| s28 | 6×20 | 0.25 | 30/30 | yes | yes | yes |
| s20 | 2×10 | 0.05 | 30/30 | yes | yes | yes |
| s20 | 2×10 | 0.25 | 30/30 | yes | yes | yes |
| s20 | 2×20 | 0.05 | 30/30 | yes | yes | yes |
| s20 | 2×20 | 0.25 | 30/30 | yes | yes | yes |
| s20 | 6×10 | 0.05 | 30/30 | yes | yes | yes |
| s20 | 6×10 | 0.25 | 30/30 | yes | yes | yes |
| s20 | 6×20 | 0.05 | 30/30 | yes | yes | yes |
| s20 | 6×20 | 0.25 | 30/30 | yes | yes | yes |
| s11 | 2×10 | 0.05 | 30/30 | yes | yes | yes |
| s11 | 2×10 | 0.25 | 30/30 | yes | yes | yes |
| s11 | 2×20 | 0.05 | 30/30 | yes | yes | yes |
| s11 | 2×20 | 0.25 | 30/30 | yes | yes | yes |
| s11 | 6×10 | 0.05 | 30/30 | yes | yes | yes |
| s11 | 6×10 | 0.25 | 30/30 | yes | yes | yes |
| s11 | 6×20 | 0.05 | 30/30 | yes | yes | yes |
| s11 | 6×20 | 0.25 | 30/30 | yes | yes | yes |

Result: **pass**.

## Replay verification

- Never chains: replayed owner totals equal the saved ones in 240/240 stall-seeds.
- Licensed chains, owner not liable: 1440/1440 owner-options equal the saved totals.
- Owner liable, derived: 960/960 owner-options equal the saved totals.
- Owner liable, replayed (seeds 250–251): 96/96 chains trade identically to the not-liable chain on every stall-day; 96/96 have window ledgers equal to the derived ones.
- Licensee-days whose royalty differs from units × round(0.15 × price): 0. Stall-days whose observed profit differs from the engine's: 0.
- Result: **pass**.

## Check (a): extra sales the brand added

Per owner (sum over its licensees), licence day to day 30, licensed − never. Royalty columns at the headline royalty 0.10. Units are not affected by the royalty.

| Condition | Option | Licensee units | Never units | Extra units | Royalty paid ($) | Royalty on extra units ($) | Share earned on sales made anyway |
|---|---|---|---|---|---|---|---|
| cheap, t40, 0, not liable | 2×10 | 105.2 [100.6, 109.9] | 114.5 [102.6, 126.3] | −9.2 [−18.5, −0.0] * | 654.69 [542.77, 766.61] | 129.06 [86.49, 171.62] | 0.787 [0.727, 0.847] |
| cheap, t40, 0, not liable | 2×20 | 55.1 [51.6, 58.7] | 59.9 [53.4, 66.4] | −4.8 [−9.8, +0.3] | 356.41 [287.96, 424.87] | 75.99 [48.14, 103.83] | 0.772 [0.707, 0.837] |
| cheap, t40, 0, not liable | 6×10 | 324.2 [309.7, 338.8] | 340.3 [327.3, 353.3] | −16.1 [−26.7, −5.4] * | 1,842.54 [1,488.60, 2,196.48] | 380.73 [304.95, 456.52] | 0.784 [0.754, 0.814] |
| cheap, t40, 0, not liable | 6×20 | 174.5 [165.8, 183.2] | 178.9 [170.3, 187.5] | −4.4 [−11.2, +2.4] | 1,048.07 [850.92, 1,245.21] | 229.11 [184.05, 274.17] | 0.771 [0.738, 0.804] |
| cheap, t40, 0, owner liable | 2×10 | 105.2 [100.6, 109.9] | 114.5 [102.6, 126.3] | −9.2 [−18.5, −0.0] * | 654.69 [542.77, 766.61] | 129.06 [86.49, 171.62] | 0.787 [0.727, 0.847] |
| cheap, t40, 0, owner liable | 2×20 | 55.1 [51.6, 58.7] | 59.9 [53.4, 66.4] | −4.8 [−9.8, +0.3] | 356.41 [287.96, 424.87] | 75.99 [48.14, 103.83] | 0.772 [0.707, 0.837] |
| cheap, t40, 0, owner liable | 6×10 | 324.2 [309.7, 338.8] | 340.3 [327.3, 353.3] | −16.1 [−26.7, −5.4] * | 1,842.54 [1,488.60, 2,196.48] | 380.73 [304.95, 456.52] | 0.784 [0.754, 0.814] |
| cheap, t40, 0, owner liable | 6×20 | 174.5 [165.8, 183.2] | 178.9 [170.3, 187.5] | −4.4 [−11.2, +2.4] | 1,048.07 [850.92, 1,245.21] | 229.11 [184.05, 274.17] | 0.771 [0.738, 0.804] |
| cheap, t40, 1, not liable | 2×10 | 80.7 [76.2, 85.2] | 84.1 [76.6, 91.6] | −3.4 [−10.1, +3.3] | 526.88 [429.37, 624.40] | 96.66 [61.23, 132.10] | 0.800 [0.732, 0.867] |
| cheap, t40, 1, not liable | 2×20 | 40.9 [37.4, 44.3] | 43.9 [39.6, 48.2] | −3.1 [−6.8, +0.6] | 273.94 [215.43, 332.45] | 55.08 [32.33, 77.83] | 0.779 [0.702, 0.855] |
| cheap, t40, 1, not liable | 6×10 | 260.3 [252.4, 268.2] | 250.2 [240.1, 260.2] | +10.1 [+0.9, +19.3] * | 1,514.74 [1,252.64, 1,776.84] | 292.82 [228.94, 356.70] | 0.798 [0.763, 0.833] |
| cheap, t40, 1, not liable | 6×20 | 134.1 [128.9, 139.4] | 130.4 [123.3, 137.5] | +3.7 [−1.6, +9.0] | 812.89 [671.75, 954.02] | 169.41 [130.31, 208.51] | 0.787 [0.752, 0.821] |
| cheap, t40, 1, owner liable | 2×10 | 80.7 [76.2, 85.2] | 84.1 [76.6, 91.6] | −3.4 [−10.1, +3.3] | 526.88 [429.37, 624.40] | 96.66 [61.23, 132.10] | 0.800 [0.732, 0.867] |
| cheap, t40, 1, owner liable | 2×20 | 40.9 [37.4, 44.3] | 43.9 [39.6, 48.2] | −3.1 [−6.8, +0.6] | 273.94 [215.43, 332.45] | 55.08 [32.33, 77.83] | 0.779 [0.702, 0.855] |
| cheap, t40, 1, owner liable | 6×10 | 260.3 [252.4, 268.2] | 250.2 [240.1, 260.2] | +10.1 [+0.9, +19.3] * | 1,514.74 [1,252.64, 1,776.84] | 292.82 [228.94, 356.70] | 0.798 [0.763, 0.833] |
| cheap, t40, 1, owner liable | 6×20 | 134.1 [128.9, 139.4] | 130.4 [123.3, 137.5] | +3.7 [−1.6, +9.0] | 812.89 [671.75, 954.02] | 169.41 [130.31, 208.51] | 0.787 [0.752, 0.821] |
| cheap, t100, 0, not liable | 2×10 | 233.2 [223.0, 243.5] | 243.3 [206.7, 279.9] | −10.1 [−40.1, +19.9] | 1,381.30 [1,133.93, 1,628.67] | 401.74 [285.62, 517.86] | 0.686 [0.602, 0.770] |
| cheap, t100, 0, not liable | 2×20 | 120.8 [114.1, 127.5] | 128.5 [108.4, 148.5] | −7.7 [−23.6, +8.2] | 734.29 [606.69, 861.90] | 209.67 [148.39, 270.94] | 0.691 [0.607, 0.774] |
| cheap, t100, 0, not liable | 6×10 | 781.2 [745.8, 816.6] | 737.7 [696.5, 778.9] | +43.5 [+21.8, +65.2] * | 4,361.21 [3,523.52, 5,198.90] | 1,380.84 [1,107.62, 1,654.07] | 0.670 [0.625, 0.714] |
| cheap, t100, 0, not liable | 6×20 | 404.5 [384.5, 424.4] | 389.5 [366.5, 412.5] | +15.0 [+3.6, +26.3] * | 2,362.39 [1,907.64, 2,817.14] | 738.88 [592.17, 885.60] | 0.673 [0.625, 0.720] |
| cheap, t100, 0, owner liable | 2×10 | 233.2 [223.0, 243.5] | 243.3 [206.7, 279.9] | −10.1 [−40.1, +19.9] | 1,381.30 [1,133.93, 1,628.67] | 401.74 [285.62, 517.86] | 0.686 [0.602, 0.770] |
| cheap, t100, 0, owner liable | 2×20 | 120.8 [114.1, 127.5] | 128.5 [108.4, 148.5] | −7.7 [−23.6, +8.2] | 734.29 [606.69, 861.90] | 209.67 [148.39, 270.94] | 0.691 [0.607, 0.774] |
| cheap, t100, 0, owner liable | 6×10 | 781.2 [745.8, 816.6] | 737.7 [696.5, 778.9] | +43.5 [+21.8, +65.2] * | 4,361.21 [3,523.52, 5,198.90] | 1,380.84 [1,107.62, 1,654.07] | 0.670 [0.625, 0.714] |
| cheap, t100, 0, owner liable | 6×20 | 404.5 [384.5, 424.4] | 389.5 [366.5, 412.5] | +15.0 [+3.6, +26.3] * | 2,362.39 [1,907.64, 2,817.14] | 738.88 [592.17, 885.60] | 0.673 [0.625, 0.720] |
| cheap, t100, 1, not liable | 2×10 | 124.8 [117.5, 132.0] | 113.4 [102.5, 124.3] | +11.3 [−0.6, +23.3] | 817.58 [667.61, 967.56] | 211.79 [135.92, 287.66] | 0.732 [0.658, 0.806] |
| cheap, t100, 1, not liable | 2×20 | 63.5 [59.4, 67.6] | 60.9 [54.5, 67.4] | +2.6 [−4.2, +9.4] | 435.65 [354.51, 516.79] | 119.80 [77.16, 162.45] | 0.717 [0.637, 0.796] |
| cheap, t100, 1, not liable | 6×10 | 437.5 [423.2, 451.9] | 343.7 [329.5, 357.8] | +93.8 [+75.6, +112.1] * | 2,581.24 [2,137.39, 3,025.08] | 771.63 [622.52, 920.73] | 0.698 [0.668, 0.727] |
| cheap, t100, 1, not liable | 6×20 | 219.7 [210.7, 228.7] | 181.8 [172.3, 191.3] | +37.9 [+26.9, +48.8] * | 1,345.63 [1,106.59, 1,584.66] | 411.39 [330.76, 492.01] | 0.688 [0.654, 0.723] |
| cheap, t100, 1, owner liable | 2×10 | 124.8 [117.5, 132.0] | 113.4 [102.5, 124.3] | +11.3 [−0.6, +23.3] | 817.58 [667.61, 967.56] | 211.79 [135.92, 287.66] | 0.732 [0.658, 0.806] |
| cheap, t100, 1, owner liable | 2×20 | 63.5 [59.4, 67.6] | 60.9 [54.5, 67.4] | +2.6 [−4.2, +9.4] | 435.65 [354.51, 516.79] | 119.80 [77.16, 162.45] | 0.717 [0.637, 0.796] |
| cheap, t100, 1, owner liable | 6×10 | 437.5 [423.2, 451.9] | 343.7 [329.5, 357.8] | +93.8 [+75.6, +112.1] * | 2,581.24 [2,137.39, 3,025.08] | 771.63 [622.52, 920.73] | 0.698 [0.668, 0.727] |
| cheap, t100, 1, owner liable | 6×20 | 219.7 [210.7, 228.7] | 181.8 [172.3, 191.3] | +37.9 [+26.9, +48.8] * | 1,345.63 [1,106.59, 1,584.66] | 411.39 [330.76, 492.01] | 0.688 [0.654, 0.723] |
| contract, t40, 1, not liable | 2×10 | 264.1 [241.9, 286.3] | 84.1 [76.6, 91.6] | +180.0 [+158.7, +201.3] * | 1,940.96 [1,578.83, 2,303.09] | 1,331.09 [1,063.42, 1,598.76] | 0.319 [0.278, 0.359] |
| contract, t40, 1, not liable | 2×20 | 140.4 [128.0, 152.7] | 43.9 [39.6, 48.2] | +96.4 [+84.5, +108.4] * | 1,031.52 [839.02, 1,224.02] | 711.01 [566.51, 855.51] | 0.314 [0.265, 0.363] |
| contract, t40, 1, not liable | 6×10 | 637.6 [598.1, 677.1] | 250.2 [240.1, 260.2] | +387.5 [+348.5, +426.4] * | 4,712.02 [3,817.88, 5,606.16] | 3,049.82 [2,428.03, 3,671.62] | 0.358 [0.333, 0.382] |
| contract, t40, 1, not liable | 6×20 | 334.2 [312.5, 355.9] | 130.4 [123.3, 137.5] | +203.8 [+182.1, +225.6] * | 2,467.55 [2,000.72, 2,934.39] | 1,627.71 [1,291.19, 1,964.23] | 0.346 [0.316, 0.377] |
| contract, t100, 1, not liable | 2×10 | 251.3 [229.1, 273.5] | 113.4 [102.5, 124.3] | +137.9 [+114.7, +161.1] * | 1,851.18 [1,498.77, 2,203.60] | 1,057.18 [820.52, 1,293.85] | 0.435 [0.380, 0.490] |
| contract, t100, 1, not liable | 2×20 | 132.8 [121.0, 144.7] | 60.9 [54.5, 67.4] | +71.9 [+59.0, +84.9] * | 978.29 [798.88, 1,157.70] | 561.52 [438.74, 684.30] | 0.429 [0.370, 0.489] |
| contract, t100, 1, not liable | 6×10 | 652.2 [610.6, 693.9] | 343.7 [329.5, 357.8] | +308.6 [+269.3, +347.8] * | 4,837.42 [3,898.12, 5,776.73] | 2,762.42 [2,178.64, 3,346.20] | 0.435 [0.407, 0.463] |
| contract, t100, 1, not liable | 6×20 | 343.0 [319.6, 366.4] | 181.8 [172.3, 191.3] | +161.1 [+139.1, +183.2] * | 2,537.54 [2,044.41, 3,030.66] | 1,460.78 [1,159.88, 1,761.68] | 0.428 [0.401, 0.455] |

Share of royalties earned on sales the licensees would have made anyway, at each royalty (the share moves with the royalty only through per-unit rounding):

| Condition | Option | 0.05 | 0.10 | 0.15 | 0.25 |
|---|---|---|---|---|---|
| cheap, t40, 0, not liable | 2×10 | 0.787 | 0.787 | 0.787 | 0.787 |
| cheap, t40, 0, not liable | 2×20 | 0.772 | 0.772 | 0.772 | 0.772 |
| cheap, t40, 0, not liable | 6×10 | 0.784 | 0.784 | 0.784 | 0.784 |
| cheap, t40, 0, not liable | 6×20 | 0.771 | 0.771 | 0.771 | 0.771 |
| cheap, t40, 0, owner liable | 2×10 | 0.787 | 0.787 | 0.787 | 0.787 |
| cheap, t40, 0, owner liable | 2×20 | 0.772 | 0.772 | 0.772 | 0.772 |
| cheap, t40, 0, owner liable | 6×10 | 0.784 | 0.784 | 0.784 | 0.784 |
| cheap, t40, 0, owner liable | 6×20 | 0.771 | 0.771 | 0.771 | 0.771 |
| cheap, t40, 1, not liable | 2×10 | 0.800 | 0.800 | 0.800 | 0.800 |
| cheap, t40, 1, not liable | 2×20 | 0.779 | 0.779 | 0.779 | 0.779 |
| cheap, t40, 1, not liable | 6×10 | 0.798 | 0.798 | 0.798 | 0.798 |
| cheap, t40, 1, not liable | 6×20 | 0.787 | 0.787 | 0.787 | 0.787 |
| cheap, t40, 1, owner liable | 2×10 | 0.800 | 0.800 | 0.800 | 0.800 |
| cheap, t40, 1, owner liable | 2×20 | 0.779 | 0.779 | 0.779 | 0.779 |
| cheap, t40, 1, owner liable | 6×10 | 0.798 | 0.798 | 0.798 | 0.798 |
| cheap, t40, 1, owner liable | 6×20 | 0.787 | 0.787 | 0.787 | 0.787 |
| cheap, t100, 0, not liable | 2×10 | 0.686 | 0.686 | 0.686 | 0.686 |
| cheap, t100, 0, not liable | 2×20 | 0.691 | 0.691 | 0.691 | 0.691 |
| cheap, t100, 0, not liable | 6×10 | 0.670 | 0.670 | 0.670 | 0.670 |
| cheap, t100, 0, not liable | 6×20 | 0.673 | 0.673 | 0.673 | 0.673 |
| cheap, t100, 0, owner liable | 2×10 | 0.686 | 0.686 | 0.686 | 0.686 |
| cheap, t100, 0, owner liable | 2×20 | 0.691 | 0.691 | 0.691 | 0.691 |
| cheap, t100, 0, owner liable | 6×10 | 0.670 | 0.670 | 0.670 | 0.670 |
| cheap, t100, 0, owner liable | 6×20 | 0.673 | 0.673 | 0.673 | 0.673 |
| cheap, t100, 1, not liable | 2×10 | 0.732 | 0.732 | 0.732 | 0.732 |
| cheap, t100, 1, not liable | 2×20 | 0.717 | 0.717 | 0.717 | 0.717 |
| cheap, t100, 1, not liable | 6×10 | 0.698 | 0.698 | 0.698 | 0.698 |
| cheap, t100, 1, not liable | 6×20 | 0.688 | 0.688 | 0.688 | 0.688 |
| cheap, t100, 1, owner liable | 2×10 | 0.732 | 0.732 | 0.732 | 0.732 |
| cheap, t100, 1, owner liable | 2×20 | 0.717 | 0.717 | 0.717 | 0.717 |
| cheap, t100, 1, owner liable | 6×10 | 0.698 | 0.698 | 0.698 | 0.698 |
| cheap, t100, 1, owner liable | 6×20 | 0.688 | 0.688 | 0.688 | 0.688 |
| contract, t40, 1, not liable | 2×10 | 0.319 | 0.319 | 0.319 | 0.319 |
| contract, t40, 1, not liable | 2×20 | 0.314 | 0.314 | 0.314 | 0.314 |
| contract, t40, 1, not liable | 6×10 | 0.358 | 0.358 | 0.358 | 0.358 |
| contract, t40, 1, not liable | 6×20 | 0.346 | 0.346 | 0.346 | 0.346 |
| contract, t100, 1, not liable | 2×10 | 0.435 | 0.435 | 0.435 | 0.435 |
| contract, t100, 1, not liable | 2×20 | 0.429 | 0.429 | 0.429 | 0.429 |
| contract, t100, 1, not liable | 6×10 | 0.435 | 0.435 | 0.435 | 0.435 |
| contract, t100, 1, not liable | 6×20 | 0.428 | 0.428 | 0.428 | 0.428 |

Per licensee, licensed − never, licence day to day 30 (mean over the licensees of the 3 owners per seed); profit at royalty 0.10.

| Condition | Option | Units | Revenue ($) | Unit cost licensed / never ($) | Ad spend ($) | Fines ($) | Catches | Profit ($) |
|---|---|---|---|---|---|---|---|---|
| cheap, t40, 0, not liable | 2×10 | −4.6 [−9.2, −0.0] * | +566.90 [+246.60, +887.19] * | 27.08 / 26.82 | −63.76 [−83.30, −44.22] * | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | +432.48 [+231.02, +633.93] * |
| cheap, t40, 0, not liable | 2×20 | −2.4 [−4.9, +0.1] | +354.30 [+162.72, +545.89] * | 27.08 / 26.92 | −33.47 [−43.78, −23.15] * | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | +284.53 [+168.94, +400.13] * |
| cheap, t40, 0, not liable | 6×10 | −2.7 [−4.5, −0.9] * | +404.54 [+266.78, +542.30] * | 27.08 / 26.98 | −63.34 [−75.82, −50.87] * | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | +215.82 [+143.76, +287.87] * |
| cheap, t40, 0, not liable | 6×20 | −0.7 [−1.9, +0.4] | +338.86 [+246.51, +431.22] * | 27.08 / 26.96 | −33.34 [−39.88, −26.79] * | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | +213.07 [+160.03, +266.10] * |
| cheap, t40, 0, owner liable | 2×10 | −4.6 [−9.2, −0.0] * | +566.90 [+246.60, +887.19] * | 27.08 / 26.82 | −63.76 [−83.30, −44.22] * | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | +432.48 [+231.02, +633.93] * |
| cheap, t40, 0, owner liable | 2×20 | −2.4 [−4.9, +0.1] | +354.30 [+162.72, +545.89] * | 27.08 / 26.92 | −33.47 [−43.78, −23.15] * | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | +284.53 [+168.94, +400.13] * |
| cheap, t40, 0, owner liable | 6×10 | −2.7 [−4.5, −0.9] * | +404.54 [+266.78, +542.30] * | 27.08 / 26.98 | −63.34 [−75.82, −50.87] * | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | +215.82 [+143.76, +287.87] * |
| cheap, t40, 0, owner liable | 6×20 | −0.7 [−1.9, +0.4] | +338.86 [+246.51, +431.22] * | 27.08 / 26.96 | −33.34 [−39.88, −26.79] * | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | +213.07 [+160.03, +266.10] * |
| cheap, t40, 1, not liable | 2×10 | −1.7 [−5.0, +1.6] | +382.58 [+99.83, +665.34] * | 27.08 / 26.82 | −108.85 [−142.47, −75.23] * | +1,705.30 [+1,154.21, +2,256.39] * | +19.8 [+14.9, +24.8] * | −1,427.93 [−1,803.98, −1,051.87] * |
| cheap, t40, 1, not liable | 2×20 | −1.5 [−3.4, +0.3] | +178.34 [+2.11, +354.56] * | 27.08 / 26.92 | −56.98 [−74.16, −39.79] * | +896.30 [+618.41, +1,174.19] * | +10.4 [+7.8, +13.1] * | −754.41 [−954.42, −554.40] * |
| cheap, t40, 1, not liable | 6×10 | +1.7 [+0.1, +3.2] * | +303.81 [+186.67, +420.96] * | 27.08 / 26.90 | −109.45 [−131.21, −87.68] * | +1,673.03 [+1,374.86, +1,971.21] * | +20.3 [+18.2, +22.4] * | −1,554.72 [−1,793.57, −1,315.87] * |
| cheap, t40, 1, not liable | 6×20 | +0.6 [−0.3, +1.5] | +199.98 [+121.43, +278.54] * | 27.08 / 26.96 | −56.73 [−68.19, −45.26] * | +866.00 [+709.66, +1,022.34] * | +10.4 [+9.5, +11.3] * | −757.57 [−884.61, −630.53] * |
| cheap, t40, 1, owner liable | 2×10 | −1.7 [−5.0, +1.6] | +382.58 [+99.83, +665.34] * | 27.08 / 26.82 | −108.85 [−142.47, −75.23] * | −2,174.70 [−2,846.18, −1,503.22] * | +19.8 [+14.9, +24.8] * | +2,452.07 [+1,880.12, +3,024.02] * |
| cheap, t40, 1, owner liable | 2×20 | −1.5 [−3.4, +0.3] | +178.34 [+2.11, +354.56] * | 27.08 / 26.92 | −56.98 [−74.16, −39.79] * | −1,123.90 [−1,461.81, −785.99] * | +10.4 [+7.8, +13.1] * | +1,265.79 [+980.96, +1,550.62] * |
| cheap, t40, 1, owner liable | 6×10 | +1.7 [+0.1, +3.2] * | +303.81 [+186.67, +420.96] * | 27.08 / 26.90 | −109.45 [−131.21, −87.68] * | −2,230.10 [−2,695.42, −1,764.78] * | +20.3 [+18.2, +22.4] * | +2,348.42 [+1,899.43, +2,797.40] * |
| cheap, t40, 1, owner liable | 6×20 | +0.6 [−0.3, +1.5] | +199.98 [+121.43, +278.54] * | 27.08 / 26.96 | −56.73 [−68.19, −45.26] * | −1,165.43 [−1,407.77, −923.09] * | +10.4 [+9.5, +11.3] * | +1,273.87 [+1,032.47, +1,515.26] * |
| cheap, t100, 0, not liable | 2×10 | −5.0 [−20.0, +10.0] | +860.40 [−82.42, +1,803.22] | 27.08 / 26.82 | −21.79 [−28.54, −15.05] * | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | +444.97 [−28.75, +918.68] |
| cheap, t100, 0, not liable | 2×20 | −3.9 [−11.8, +4.1] | +471.39 [−23.52, +966.30] | 27.08 / 26.92 | −11.43 [−14.97, −7.89] * | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | +300.43 [+52.56, +548.30] * |
| cheap, t100, 0, not liable | 6×10 | +7.2 [+3.6, +10.9] * | +1,288.58 [+950.81, +1,626.36] * | 27.08 / 26.87 | −21.70 [−26.05, −17.35] * | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | +362.60 [+193.14, +532.06] * |
| cheap, t100, 0, not liable | 6×20 | +2.5 [+0.6, +4.4] * | +772.13 [+574.32, +969.94] * | 27.08 / 26.96 | −11.30 [−13.58, −9.01] * | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | +318.10 [+215.46, +420.74] * |
| cheap, t100, 0, owner liable | 2×10 | −5.0 [−20.0, +10.0] | +860.40 [−82.42, +1,803.22] | 27.08 / 26.82 | −21.79 [−28.54, −15.05] * | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | +444.97 [−28.75, +918.68] |
| cheap, t100, 0, owner liable | 2×20 | −3.9 [−11.8, +4.1] | +471.39 [−23.52, +966.30] | 27.08 / 26.92 | −11.43 [−14.97, −7.89] * | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | +300.43 [+52.56, +548.30] * |
| cheap, t100, 0, owner liable | 6×10 | +7.2 [+3.6, +10.9] * | +1,288.58 [+950.81, +1,626.36] * | 27.08 / 26.87 | −21.70 [−26.05, −17.35] * | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | +362.60 [+193.14, +532.06] * |
| cheap, t100, 0, owner liable | 6×20 | +2.5 [+0.6, +4.4] * | +772.13 [+574.32, +969.94] * | 27.08 / 26.96 | −11.30 [−13.58, −9.01] * | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | +318.10 [+215.46, +420.74] * |
| cheap, t100, 1, not liable | 2×10 | +5.7 [−0.3, +11.7] | +888.12 [+371.66, +1,404.58] * | 27.08 / 26.82 | −110.58 [−143.44, −77.71] * | +2,533.30 [+1,748.68, +3,317.92] * | +30.9 [+23.6, +38.2] * | −2,107.32 [−2,616.97, −1,597.67] * |
| cheap, t100, 1, not liable | 2×20 | +1.3 [−2.1, +4.7] | +452.95 [+156.99, +748.90] * | 27.08 / 26.92 | −59.25 [−76.68, −41.82] * | +1,368.30 [+954.11, +1,782.49] * | +16.9 [+12.8, +20.9] * | −1,134.64 [−1,402.88, −866.41] * |
| cheap, t100, 1, not liable | 6×10 | +15.6 [+12.6, +18.7] * | +1,057.03 [+798.55, +1,315.51] * | 27.08 / 26.87 | −111.42 [−133.44, −89.40] * | +2,562.73 [+2,112.43, +3,013.04] * | +31.1 [+28.3, +34.0] * | −2,238.80 [−2,591.49, −1,886.10] * |
| cheap, t100, 1, not liable | 6×20 | +6.3 [+4.5, +8.1] * | +528.66 [+385.20, +672.13] * | 27.08 / 26.96 | −59.21 [−70.96, −47.47] * | +1,361.47 [+1,124.42, +1,598.51] * | +16.5 [+15.0, +18.1] * | −1,169.35 [−1,358.49, −980.21] * |
| cheap, t100, 1, owner liable | 2×10 | +5.7 [−0.3, +11.7] | +888.12 [+371.66, +1,404.58] * | 27.08 / 26.82 | −110.58 [−143.44, −77.71] * | −3,447.30 [−4,493.44, −2,401.16] * | +30.9 [+23.6, +38.2] * | +3,873.28 [+3,000.34, +4,746.22] * |
| cheap, t100, 1, owner liable | 2×20 | +1.3 [−2.1, +4.7] | +452.95 [+156.99, +748.90] * | 27.08 / 26.92 | −59.25 [−76.68, −41.82] * | −1,772.10 [−2,295.48, −1,248.72] * | +16.9 [+12.8, +20.9] * | +2,005.76 [+1,584.00, +2,427.52] * |
| cheap, t100, 1, owner liable | 6×10 | +15.6 [+12.6, +18.7] * | +1,057.03 [+798.55, +1,315.51] * | 27.08 / 26.87 | −111.42 [−133.44, −89.40] * | −3,413.33 [−4,099.51, −2,727.16] * | +31.1 [+28.3, +34.0] * | +3,737.27 [+3,074.95, +4,399.59] * |
| cheap, t100, 1, owner liable | 6×20 | +6.3 [+4.5, +8.1] * | +528.66 [+385.20, +672.13] * | 27.08 / 26.96 | −59.21 [−70.96, −47.47] * | −1,771.97 [−2,112.72, −1,431.21] * | +16.5 [+15.0, +18.1] * | +1,964.08 [+1,632.98, +2,295.19] * |
| contract, t40, 1, not liable | 2×10 | +90.0 [+79.4, +100.7] * | +7,453.01 [+6,003.22, +8,902.80] * | 42.70 / 26.82 | +145.85 [+103.21, +188.50] * | −2,174.70 [−2,846.18, −1,503.22] * | −23.3 [−28.2, −18.5] * | +3,867.79 [+3,073.81, +4,661.77] * |
| contract, t40, 1, not liable | 2×20 | +48.2 [+42.3, +54.2] * | +3,966.18 [+3,190.98, +4,741.38] * | 42.70 / 26.92 | +76.47 [+54.28, +98.67] * | −1,123.90 [−1,461.81, −785.99] * | −12.3 [−14.9, −9.6] * | +2,022.07 [+1,617.19, +2,426.94] * |
| contract, t40, 1, not liable | 6×10 | +64.6 [+58.1, +71.1] * | +5,632.64 [+4,494.14, +6,771.14] * | 42.70 / 26.90 | +144.49 [+116.93, +172.05] * | −2,230.10 [−2,695.42, −1,764.78] * | −23.6 [−25.5, −21.7] * | +3,381.37 [+2,726.98, +4,035.76] * |
| contract, t40, 1, not liable | 6×20 | +34.0 [+30.3, +37.6] * | +2,957.72 [+2,353.57, +3,561.88] * | 42.83 / 26.96 | +75.96 [+61.50, +90.42] * | −1,165.43 [−1,407.77, −923.09] * | −12.4 [−13.6, −11.2] * | +1,768.57 [+1,422.86, +2,114.28] * |
| contract, t100, 1, not liable | 2×10 | +68.9 [+57.3, +80.5] * | +6,056.25 [+4,757.08, +7,355.41] * | 42.70 / 26.82 | +152.98 [+108.03, +197.93] * | −3,447.30 [−4,493.44, −2,401.16] * | −37.0 [−44.8, −29.2] * | +4,457.56 [+3,492.77, +5,422.35] * |
| contract, t100, 1, not liable | 2×20 | +36.0 [+29.5, +42.4] * | +3,166.12 [+2,500.26, +3,831.98] * | 42.70 / 26.92 | +79.02 [+56.40, +101.64] * | −1,772.10 [−2,295.48, −1,248.72] * | −19.1 [−23.2, −15.0] * | +2,290.24 [+1,840.44, +2,740.05] * |
| contract, t100, 1, not liable | 6×10 | +51.4 [+44.9, +58.0] * | +4,817.34 [+3,777.81, +5,856.87] * | 42.56 / 26.87 | +149.06 [+120.69, +177.43] * | −3,413.33 [−4,099.51, −2,727.16] * | −36.6 [−39.4, −33.7] * | +4,041.88 [+3,284.55, +4,799.21] * |
| contract, t100, 1, not liable | 6×20 | +26.9 [+23.2, +30.5] * | +2,515.18 [+1,976.24, +3,054.13] * | 42.56 / 26.96 | +77.51 [+63.31, +91.72] * | −1,771.97 [−2,112.72, −1,431.21] * | −19.1 [−20.5, −17.6] * | +2,092.85 [+1,724.43, +2,461.28] * |

Whose sales the licensees took: units licensed − never, licence day to day 30, per owner, by group (the owner; the other genuine stalls of its category; the other non-genuine stalls of its category, licensees excluded; every stall of other categories).

| Condition | Option | Licensees | Owner | Same category, genuine | Same category, other | Other categories |
|---|---|---|---|---|---|---|
| cheap, t40, 0, not liable | 2×10 | −9.2 [−18.5, −0.0] * | −38.2 [−48.5, −27.9] * | −12.4 [−21.0, −3.9] * | +33.8 [+28.0, +39.6] * | +0.0 [+0.0, +0.0] |
| cheap, t40, 0, not liable | 2×20 | −4.8 [−9.8, +0.3] | −10.8 [−17.2, −4.5] * | −9.1 [−14.6, −3.5] * | +17.5 [+14.8, +20.1] * | +0.0 [+0.0, +0.0] |
| cheap, t40, 0, not liable | 6×10 | −16.1 [−26.7, −5.4] * | −67.0 [−74.3, −59.8] * | −29.4 [−39.8, −19.0] * | +49.9 [+40.0, +59.7] * | +0.0 [+0.0, +0.0] |
| cheap, t40, 0, not liable | 6×20 | −4.4 [−11.2, +2.4] | −25.7 [−30.0, −21.4] * | −24.4 [−30.3, −18.5] * | +25.4 [+20.5, +30.2] * | +0.0 [−0.0, +0.1] |
| cheap, t40, 0, owner liable | 2×10 | −9.2 [−18.5, −0.0] * | −38.2 [−48.5, −27.9] * | −12.4 [−21.0, −3.9] * | +33.8 [+28.0, +39.6] * | +0.0 [+0.0, +0.0] |
| cheap, t40, 0, owner liable | 2×20 | −4.8 [−9.8, +0.3] | −10.8 [−17.2, −4.5] * | −9.1 [−14.6, −3.5] * | +17.5 [+14.8, +20.1] * | +0.0 [+0.0, +0.0] |
| cheap, t40, 0, owner liable | 6×10 | −16.1 [−26.7, −5.4] * | −67.0 [−74.3, −59.8] * | −29.4 [−39.8, −19.0] * | +49.9 [+40.0, +59.7] * | +0.0 [+0.0, +0.0] |
| cheap, t40, 0, owner liable | 6×20 | −4.4 [−11.2, +2.4] | −25.7 [−30.0, −21.4] * | −24.4 [−30.3, −18.5] * | +25.4 [+20.5, +30.2] * | +0.0 [−0.0, +0.1] |
| cheap, t40, 1, not liable | 2×10 | −3.4 [−10.1, +3.3] | +7.7 [+0.0, +15.4] * | −11.3 [−21.6, −1.1] * | +13.9 [+9.8, +18.1] * | +1.4 [−1.4, +4.2] |
| cheap, t40, 1, not liable | 2×20 | −3.1 [−6.8, +0.6] | +4.8 [−0.0, +9.7] | −5.7 [−11.2, −0.2] * | +8.1 [+5.2, +11.1] * | +1.7 [−0.1, +3.6] |
| cheap, t40, 1, not liable | 6×10 | +10.1 [+0.9, +19.3] * | −36.5 [−43.4, −29.6] * | +13.5 [+2.7, +24.2] * | −14.1 [−19.8, −8.3] * | +3.9 [+1.2, +6.5] * |
| cheap, t40, 1, not liable | 6×20 | +3.7 [−1.6, +9.0] | −9.3 [−13.9, −4.7] * | −2.4 [−8.9, +4.1] | +0.1 [−4.1, +4.3] | +3.2 [+1.2, +5.2] * |
| cheap, t40, 1, owner liable | 2×10 | −3.4 [−10.1, +3.3] | +7.7 [+0.0, +15.4] * | −11.3 [−21.6, −1.1] * | +13.9 [+9.8, +18.1] * | +1.4 [−1.4, +4.2] |
| cheap, t40, 1, owner liable | 2×20 | −3.1 [−6.8, +0.6] | +4.8 [−0.0, +9.7] | −5.7 [−11.2, −0.2] * | +8.1 [+5.2, +11.1] * | +1.7 [−0.1, +3.6] |
| cheap, t40, 1, owner liable | 6×10 | +10.1 [+0.9, +19.3] * | −36.5 [−43.4, −29.6] * | +13.5 [+2.7, +24.2] * | −14.1 [−19.8, −8.3] * | +3.9 [+1.2, +6.5] * |
| cheap, t40, 1, owner liable | 6×20 | +3.7 [−1.6, +9.0] | −9.3 [−13.9, −4.7] * | −2.4 [−8.9, +4.1] | +0.1 [−4.1, +4.3] | +3.2 [+1.2, +5.2] * |
| cheap, t100, 0, not liable | 2×10 | −10.1 [−40.1, +19.9] | +51.5 [+42.8, +60.2] * | −105.1 [−121.2, −89.0] * | +75.5 [+61.8, +89.3] * | +0.0 [+0.0, +0.0] |
| cheap, t100, 0, not liable | 2×20 | −7.7 [−23.6, +8.2] | +26.0 [+21.4, +30.6] * | −50.7 [−60.0, −41.4] * | +38.7 [+31.9, +45.6] * | +0.0 [+0.0, +0.0] |
| cheap, t100, 0, not liable | 6×10 | +43.5 [+21.8, +65.2] * | +63.9 [+52.2, +75.7] * | −195.1 [−209.3, −180.9] * | +110.2 [+89.1, +131.2] * | +0.0 [+0.0, +0.0] |
| cheap, t100, 0, not liable | 6×20 | +15.0 [+3.6, +26.3] * | +32.9 [+27.1, +38.7] * | −92.3 [−100.8, −83.7] * | +56.2 [+45.4, +67.1] * | +0.0 [+0.0, +0.0] |
| cheap, t100, 0, owner liable | 2×10 | −10.1 [−40.1, +19.9] | +51.5 [+42.8, +60.2] * | −105.1 [−121.2, −89.0] * | +75.5 [+61.8, +89.3] * | +0.0 [+0.0, +0.0] |
| cheap, t100, 0, owner liable | 2×20 | −7.7 [−23.6, +8.2] | +26.0 [+21.4, +30.6] * | −50.7 [−60.0, −41.4] * | +38.7 [+31.9, +45.6] * | +0.0 [+0.0, +0.0] |
| cheap, t100, 0, owner liable | 6×10 | +43.5 [+21.8, +65.2] * | +63.9 [+52.2, +75.7] * | −195.1 [−209.3, −180.9] * | +110.2 [+89.1, +131.2] * | +0.0 [+0.0, +0.0] |
| cheap, t100, 0, owner liable | 6×20 | +15.0 [+3.6, +26.3] * | +32.9 [+27.1, +38.7] * | −92.3 [−100.8, −83.7] * | +56.2 [+45.4, +67.1] * | +0.0 [+0.0, +0.0] |
| cheap, t100, 1, not liable | 2×10 | +11.3 [−0.6, +23.3] | +72.2 [+66.7, +77.7] * | −89.7 [−99.2, −80.1] * | +17.5 [+10.0, +25.0] * | +1.0 [−2.5, +4.4] |
| cheap, t100, 1, not liable | 2×20 | +2.6 [−4.2, +9.4] | +34.7 [+31.4, +37.9] * | −41.0 [−47.4, −34.6] * | +8.5 [+3.0, +14.0] * | −2.6 [−4.3, −1.0] * |
| cheap, t100, 1, not liable | 6×10 | +93.8 [+75.6, +112.1] * | +94.7 [+89.9, +99.6] * | −130.7 [−141.7, −119.7] * | −28.0 [−38.9, −17.0] * | +3.7 [−1.9, +9.3] |
| cheap, t100, 1, not liable | 6×20 | +37.9 [+26.9, +48.8] * | +44.9 [+42.0, +47.8] * | −60.5 [−68.3, −52.6] * | −6.7 [−12.3, −1.1] * | −1.2 [−4.8, +2.5] |
| cheap, t100, 1, owner liable | 2×10 | +11.3 [−0.6, +23.3] | +72.2 [+66.7, +77.7] * | −89.7 [−99.2, −80.1] * | +17.5 [+10.0, +25.0] * | +1.0 [−2.5, +4.4] |
| cheap, t100, 1, owner liable | 2×20 | +2.6 [−4.2, +9.4] | +34.7 [+31.4, +37.9] * | −41.0 [−47.4, −34.6] * | +8.5 [+3.0, +14.0] * | −2.6 [−4.3, −1.0] * |
| cheap, t100, 1, owner liable | 6×10 | +93.8 [+75.6, +112.1] * | +94.7 [+89.9, +99.6] * | −130.7 [−141.7, −119.7] * | −28.0 [−38.9, −17.0] * | +3.7 [−1.9, +9.3] |
| cheap, t100, 1, owner liable | 6×20 | +37.9 [+26.9, +48.8] * | +44.9 [+42.0, +47.8] * | −60.5 [−68.3, −52.6] * | −6.7 [−12.3, −1.1] * | −1.2 [−4.8, +2.5] |
| contract, t40, 1, not liable | 2×10 | +180.0 [+158.7, +201.3] * | −14.2 [−20.0, −8.5] * | −81.1 [−99.9, −62.3] * | +18.6 [+13.9, +23.3] * | +0.7 [−2.0, +3.3] |
| contract, t40, 1, not liable | 2×20 | +96.4 [+84.5, +108.4] * | −6.7 [−9.8, −3.7] * | −43.4 [−54.2, −32.6] * | +9.9 [+7.0, +12.8] * | +1.4 [−0.4, +3.3] |
| contract, t40, 1, not liable | 6×10 | +387.5 [+348.5, +426.4] * | −42.6 [−52.9, −32.3] * | −205.3 [−238.2, −172.3] * | +27.2 [+21.4, +33.0] * | +3.8 [+0.0, +7.7] * |
| contract, t40, 1, not liable | 6×20 | +203.8 [+182.1, +225.6] * | −21.5 [−26.3, −16.6] * | −107.6 [−125.7, −89.4] * | +14.1 [+10.9, +17.2] * | +3.4 [+1.2, +5.6] * |
| contract, t100, 1, not liable | 2×10 | +137.9 [+114.7, +161.1] * | −10.8 [−17.4, −4.3] * | −55.7 [−75.8, −35.6] * | +28.5 [+19.7, +37.3] * | +2.3 [−3.1, +7.8] |
| contract, t100, 1, not liable | 2×20 | +71.9 [+59.0, +84.9] * | −5.7 [−9.1, −2.3] * | −28.8 [−40.3, −17.3] * | +13.9 [+6.6, +21.1] * | −0.9 [−3.7, +1.9] |
| contract, t100, 1, not liable | 6×10 | +308.6 [+269.3, +347.8] * | −31.0 [−42.5, −19.4] * | −135.1 [−169.5, −100.7] * | +37.4 [+29.5, +45.3] * | +4.3 [−1.4, +10.0] |
| contract, t100, 1, not liable | 6×20 | +161.1 [+139.1, +183.2] * | −16.1 [−21.5, −10.6] * | −69.1 [−89.0, −49.3] * | +17.7 [+12.0, +23.4] * | −0.4 [−3.5, +2.7] |

## Check (b): would the licensee sign?

At the headline royalty 0.10: share of licensees that would accept (pooled over 60 owners), owners whose licensees all accept, and licensee profit licensed − never (per licensee).

| Condition | Option | Licensees accepting | Owners with every licensee accepting | Licensee profit − never ($) |
|---|---|---|---|---|
| cheap, t40, 0, not liable | 2×10 | 68% of 120 | 26/60 | +432.48 [+231.02, +633.93] * |
| cheap, t40, 0, not liable | 2×20 | 75% of 120 | 33/60 | +284.53 [+168.94, +400.13] * |
| cheap, t40, 0, not liable | 6×10 | 55% of 360 | 0/60 | +215.82 [+143.76, +287.87] * |
| cheap, t40, 0, not liable | 6×20 | 62% of 360 | 1/60 | +213.07 [+160.03, +266.10] * |
| cheap, t40, 0, owner liable | 2×10 | 68% of 120 | 26/60 | +432.48 [+231.02, +633.93] * |
| cheap, t40, 0, owner liable | 2×20 | 75% of 120 | 33/60 | +284.53 [+168.94, +400.13] * |
| cheap, t40, 0, owner liable | 6×10 | 55% of 360 | 0/60 | +215.82 [+143.76, +287.87] * |
| cheap, t40, 0, owner liable | 6×20 | 62% of 360 | 1/60 | +213.07 [+160.03, +266.10] * |
| cheap, t40, 1, not liable | 2×10 | 9% of 120 | 0/60 | −1,427.93 [−1,803.98, −1,051.87] * |
| cheap, t40, 1, not liable | 2×20 | 12% of 120 | 0/60 | −754.41 [−954.42, −554.40] * |
| cheap, t40, 1, not liable | 6×10 | 9% of 360 | 0/60 | −1,554.72 [−1,793.57, −1,315.87] * |
| cheap, t40, 1, not liable | 6×20 | 16% of 360 | 0/60 | −757.57 [−884.61, −630.53] * |
| cheap, t40, 1, owner liable | 2×10 | 100% of 120 | 60/60 | +2,452.07 [+1,880.12, +3,024.02] * |
| cheap, t40, 1, owner liable | 2×20 | 99% of 120 | 59/60 | +1,265.79 [+980.96, +1,550.62] * |
| cheap, t40, 1, owner liable | 6×10 | 100% of 360 | 60/60 | +2,348.42 [+1,899.43, +2,797.40] * |
| cheap, t40, 1, owner liable | 6×20 | 100% of 360 | 60/60 | +1,273.87 [+1,032.47, +1,515.26] * |
| cheap, t100, 0, not liable | 2×10 | 56% of 120 | 16/60 | +444.97 [−28.75, +918.68] |
| cheap, t100, 0, not liable | 2×20 | 57% of 120 | 17/60 | +300.43 [+52.56, +548.30] * |
| cheap, t100, 0, not liable | 6×10 | 51% of 360 | 0/60 | +362.60 [+193.14, +532.06] * |
| cheap, t100, 0, not liable | 6×20 | 54% of 360 | 0/60 | +318.10 [+215.46, +420.74] * |
| cheap, t100, 0, owner liable | 2×10 | 56% of 120 | 16/60 | +444.97 [−28.75, +918.68] |
| cheap, t100, 0, owner liable | 2×20 | 57% of 120 | 17/60 | +300.43 [+52.56, +548.30] * |
| cheap, t100, 0, owner liable | 6×10 | 51% of 360 | 0/60 | +362.60 [+193.14, +532.06] * |
| cheap, t100, 0, owner liable | 6×20 | 54% of 360 | 0/60 | +318.10 [+215.46, +420.74] * |
| cheap, t100, 1, not liable | 2×10 | 8% of 120 | 0/60 | −2,107.32 [−2,616.97, −1,597.67] * |
| cheap, t100, 1, not liable | 2×20 | 5% of 120 | 0/60 | −1,134.64 [−1,402.88, −866.41] * |
| cheap, t100, 1, not liable | 6×10 | 10% of 360 | 0/60 | −2,238.80 [−2,591.49, −1,886.10] * |
| cheap, t100, 1, not liable | 6×20 | 13% of 360 | 0/60 | −1,169.35 [−1,358.49, −980.21] * |
| cheap, t100, 1, owner liable | 2×10 | 100% of 120 | 60/60 | +3,873.28 [+3,000.34, +4,746.22] * |
| cheap, t100, 1, owner liable | 2×20 | 100% of 120 | 60/60 | +2,005.76 [+1,584.00, +2,427.52] * |
| cheap, t100, 1, owner liable | 6×10 | 100% of 360 | 60/60 | +3,737.27 [+3,074.95, +4,399.59] * |
| cheap, t100, 1, owner liable | 6×20 | 100% of 360 | 60/60 | +1,964.08 [+1,632.98, +2,295.19] * |
| contract, t40, 1, not liable | 2×10 | 100% of 120 | 60/60 | +3,867.79 [+3,073.81, +4,661.77] * |
| contract, t40, 1, not liable | 2×20 | 100% of 120 | 60/60 | +2,022.07 [+1,617.19, +2,426.94] * |
| contract, t40, 1, not liable | 6×10 | 98% of 360 | 54/60 | +3,381.37 [+2,726.98, +4,035.76] * |
| contract, t40, 1, not liable | 6×20 | 98% of 360 | 53/60 | +1,768.57 [+1,422.86, +2,114.28] * |
| contract, t100, 1, not liable | 2×10 | 100% of 120 | 60/60 | +4,457.56 [+3,492.77, +5,422.35] * |
| contract, t100, 1, not liable | 2×20 | 100% of 120 | 60/60 | +2,290.24 [+1,840.44, +2,740.05] * |
| contract, t100, 1, not liable | 6×10 | 98% of 360 | 52/60 | +4,041.88 [+3,284.55, +4,799.21] * |
| contract, t100, 1, not liable | 6×20 | 97% of 360 | 49/60 | +2,092.85 [+1,724.43, +2,461.28] * |

Share of licensees accepting at each royalty:

| Condition | Option | 0.05 | 0.10 | 0.15 | 0.25 |
|---|---|---|---|---|---|
| cheap, t40, 0, not liable | 2×10 | 76% | 68% | 58% | 52% |
| cheap, t40, 0, not liable | 2×20 | 81% | 75% | 62% | 52% |
| cheap, t40, 0, not liable | 6×10 | 60% | 55% | 50% | 45% |
| cheap, t40, 0, not liable | 6×20 | 69% | 62% | 56% | 47% |
| cheap, t40, 0, owner liable | 2×10 | 76% | 68% | 58% | 52% |
| cheap, t40, 0, owner liable | 2×20 | 81% | 75% | 62% | 52% |
| cheap, t40, 0, owner liable | 6×10 | 60% | 55% | 50% | 45% |
| cheap, t40, 0, owner liable | 6×20 | 69% | 62% | 56% | 47% |
| cheap, t40, 1, not liable | 2×10 | 16% | 9% | 6% | 2% |
| cheap, t40, 1, not liable | 2×20 | 18% | 12% | 11% | 5% |
| cheap, t40, 1, not liable | 6×10 | 11% | 9% | 7% | 3% |
| cheap, t40, 1, not liable | 6×20 | 19% | 16% | 11% | 4% |
| cheap, t40, 1, owner liable | 2×10 | 100% | 100% | 100% | 100% |
| cheap, t40, 1, owner liable | 2×20 | 99% | 99% | 99% | 99% |
| cheap, t40, 1, owner liable | 6×10 | 100% | 100% | 100% | 100% |
| cheap, t40, 1, owner liable | 6×20 | 100% | 100% | 100% | 100% |
| cheap, t100, 0, not liable | 2×10 | 62% | 56% | 52% | 48% |
| cheap, t100, 0, not liable | 2×20 | 66% | 57% | 52% | 48% |
| cheap, t100, 0, not liable | 6×10 | 56% | 51% | 48% | 46% |
| cheap, t100, 0, not liable | 6×20 | 60% | 54% | 50% | 46% |
| cheap, t100, 0, owner liable | 2×10 | 62% | 56% | 52% | 48% |
| cheap, t100, 0, owner liable | 2×20 | 66% | 57% | 52% | 48% |
| cheap, t100, 0, owner liable | 6×10 | 56% | 51% | 48% | 46% |
| cheap, t100, 0, owner liable | 6×20 | 60% | 54% | 50% | 46% |
| cheap, t100, 1, not liable | 2×10 | 12% | 8% | 5% | 0% |
| cheap, t100, 1, not liable | 2×20 | 11% | 5% | 2% | 1% |
| cheap, t100, 1, not liable | 6×10 | 14% | 10% | 6% | 3% |
| cheap, t100, 1, not liable | 6×20 | 16% | 13% | 11% | 4% |
| cheap, t100, 1, owner liable | 2×10 | 100% | 100% | 100% | 100% |
| cheap, t100, 1, owner liable | 2×20 | 100% | 100% | 100% | 100% |
| cheap, t100, 1, owner liable | 6×10 | 100% | 100% | 100% | 100% |
| cheap, t100, 1, owner liable | 6×20 | 100% | 100% | 100% | 100% |
| contract, t40, 1, not liable | 2×10 | 100% | 100% | 100% | 99% |
| contract, t40, 1, not liable | 2×20 | 100% | 100% | 100% | 99% |
| contract, t40, 1, not liable | 6×10 | 98% | 98% | 98% | 93% |
| contract, t40, 1, not liable | 6×20 | 99% | 98% | 97% | 92% |
| contract, t100, 1, not liable | 2×10 | 100% | 100% | 100% | 98% |
| contract, t100, 1, not liable | 2×20 | 100% | 100% | 100% | 98% |
| contract, t100, 1, not liable | 6×10 | 98% | 98% | 97% | 92% |
| contract, t100, 1, not liable | 6×20 | 98% | 97% | 96% | 91% |

Licensee profit − never per licensee ($) at each royalty:

| Condition | Option | 0.05 | 0.10 | 0.15 | 0.25 |
|---|---|---|---|---|---|
| cheap, t40, 0, not liable | 2×10 | +596.16 [+387.45, +804.86] * | +432.48 [+231.02, +633.93] * | +268.81 [+70.89, +466.73] * | −58.53 [−261.14, +144.07] |
| cheap, t40, 0, not liable | 2×20 | +373.64 [+250.74, +496.54] * | +284.53 [+168.94, +400.13] * | +195.44 [+84.96, +305.92] * | +17.24 [−90.70, +125.17] |
| cheap, t40, 0, not liable | 6×10 | +369.35 [+278.48, +460.22] * | +215.82 [+143.76, +287.87] * | +62.26 [+0.07, +124.44] * | −244.83 [−325.07, −164.60] * |
| cheap, t40, 0, not liable | 6×20 | +300.40 [+235.59, +365.21] * | +213.07 [+160.03, +266.10] * | +125.73 [+81.40, +170.05] * | −48.95 [−92.40, −5.50] * |
| cheap, t40, 0, owner liable | 2×10 | +596.16 [+387.45, +804.86] * | +432.48 [+231.02, +633.93] * | +268.81 [+70.89, +466.73] * | −58.53 [−261.14, +144.07] |
| cheap, t40, 0, owner liable | 2×20 | +373.64 [+250.74, +496.54] * | +284.53 [+168.94, +400.13] * | +195.44 [+84.96, +305.92] * | +17.24 [−90.70, +125.17] |
| cheap, t40, 0, owner liable | 6×10 | +369.35 [+278.48, +460.22] * | +215.82 [+143.76, +287.87] * | +62.26 [+0.07, +124.44] * | −244.83 [−325.07, −164.60] * |
| cheap, t40, 0, owner liable | 6×20 | +300.40 [+235.59, +365.21] * | +213.07 [+160.03, +266.10] * | +125.73 [+81.40, +170.05] * | −48.95 [−92.40, −5.50] * |
| cheap, t40, 1, not liable | 2×10 | −1,296.21 [−1,669.66, −922.75] * | −1,427.93 [−1,803.98, −1,051.87] * | −1,559.64 [−1,939.84, −1,179.45] * | −1,823.08 [−2,216.00, −1,430.16] * |
| cheap, t40, 1, not liable | 2×20 | −685.92 [−887.14, −484.70] * | −754.41 [−954.42, −554.40] * | −822.91 [−1,022.78, −623.03] * | −959.88 [−1,162.66, −757.09] * |
| cheap, t40, 1, not liable | 6×10 | −1,428.48 [−1,653.47, −1,203.49] * | −1,554.72 [−1,793.57, −1,315.87] * | −1,680.94 [−1,934.78, −1,427.10] * | −1,933.39 [−2,219.86, −1,646.91] * |
| cheap, t40, 1, not liable | 6×20 | −689.83 [−809.32, −570.34] * | −757.57 [−884.61, −630.53] * | −825.31 [−960.51, −690.12] * | −960.80 [−1,113.72, −807.88] * |
| cheap, t40, 1, owner liable | 2×10 | +2,583.79 [+1,992.35, +3,175.23] * | +2,452.07 [+1,880.12, +3,024.02] * | +2,320.36 [+1,767.51, +2,873.21] * | +2,056.92 [+1,540.93, +2,572.90] * |
| cheap, t40, 1, owner liable | 2×20 | +1,334.28 [+1,039.59, +1,628.96] * | +1,265.79 [+980.96, +1,550.62] * | +1,197.29 [+921.90, +1,472.69] * | +1,060.32 [+802.34, +1,318.30] * |
| cheap, t40, 1, owner liable | 6×10 | +2,474.65 [+2,006.17, +2,943.13] * | +2,348.42 [+1,899.43, +2,797.40] * | +2,222.20 [+1,792.48, +2,651.91] * | +1,969.74 [+1,577.75, +2,361.74] * |
| cheap, t40, 1, owner liable | 6×20 | +1,341.60 [+1,090.70, +1,592.51] * | +1,273.87 [+1,032.47, +1,515.26] * | +1,206.12 [+974.02, +1,438.22] * | +1,070.63 [+856.41, +1,284.85] * |
| cheap, t100, 0, not liable | 2×10 | +790.29 [+312.74, +1,267.84] * | +444.97 [−28.75, +918.68] | +99.65 [−378.28, +577.58] | −590.99 [−1,100.29, −81.69] * |
| cheap, t100, 0, not liable | 2×20 | +484.01 [+235.04, +732.98] * | +300.43 [+52.56, +548.30] * | +116.86 [−133.99, +367.72] | −250.28 [−518.63, +18.07] |
| cheap, t100, 0, not liable | 6×10 | +726.03 [+521.86, +930.20] * | +362.60 [+193.14, +532.06] * | −0.84 [−160.50, +158.82] | −727.70 [−947.43, −507.96] * |
| cheap, t100, 0, not liable | 6×20 | +514.96 [+388.12, +641.80] * | +318.10 [+215.46, +420.74] * | +121.23 [+32.61, +209.85] * | −272.51 [−377.89, −167.14] * |
| cheap, t100, 0, owner liable | 2×10 | +790.29 [+312.74, +1,267.84] * | +444.97 [−28.75, +918.68] | +99.65 [−378.28, +577.58] | −590.99 [−1,100.29, −81.69] * |
| cheap, t100, 0, owner liable | 2×20 | +484.01 [+235.04, +732.98] * | +300.43 [+52.56, +548.30] * | +116.86 [−133.99, +367.72] | −250.28 [−518.63, +18.07] |
| cheap, t100, 0, owner liable | 6×10 | +726.03 [+521.86, +930.20] * | +362.60 [+193.14, +532.06] * | −0.84 [−160.50, +158.82] | −727.70 [−947.43, −507.96] * |
| cheap, t100, 0, owner liable | 6×20 | +514.96 [+388.12, +641.80] * | +318.10 [+215.46, +420.74] * | +121.23 [+32.61, +209.85] * | −272.51 [−377.89, −167.14] * |
| cheap, t100, 1, not liable | 2×10 | −1,902.91 [−2,405.48, −1,400.34] * | −2,107.32 [−2,616.97, −1,597.67] * | −2,311.69 [−2,831.04, −1,792.35] * | −2,720.48 [−3,266.47, −2,174.49] * |
| cheap, t100, 1, not liable | 2×20 | −1,025.73 [−1,289.95, −761.52] * | −1,134.64 [−1,402.88, −866.41] * | −1,243.56 [−1,517.26, −969.86] * | −1,461.38 [−1,750.01, −1,172.75] * |
| cheap, t100, 1, not liable | 6×10 | −2,023.70 [−2,351.88, −1,695.52] * | −2,238.80 [−2,591.49, −1,886.10] * | −2,453.90 [−2,833.14, −2,074.66] * | −2,884.11 [−3,321.01, −2,447.21] * |
| cheap, t100, 1, not liable | 6×20 | −1,057.21 [−1,234.68, −879.73] * | −1,169.35 [−1,358.49, −980.21] * | −1,281.49 [−1,483.58, −1,079.39] * | −1,505.76 [−1,736.75, −1,274.76] * |
| cheap, t100, 1, owner liable | 2×10 | +4,077.69 [+3,174.94, +4,980.44] * | +3,873.28 [+3,000.34, +4,746.22] * | +3,668.91 [+2,825.17, +4,512.65] * | +3,260.12 [+2,472.66, +4,047.58] * |
| cheap, t100, 1, owner liable | 2×20 | +2,114.67 [+1,676.19, +2,553.14] * | +2,005.76 [+1,584.00, +2,427.52] * | +1,896.84 [+1,491.47, +2,302.20] * | +1,679.02 [+1,305.29, +2,052.75] * |
| cheap, t100, 1, owner liable | 6×10 | +3,952.37 [+3,255.88, +4,648.86] * | +3,737.27 [+3,074.95, +4,399.59] * | +3,522.17 [+2,893.69, +4,150.65] * | +3,091.96 [+2,529.98, +3,653.94] * |
| cheap, t100, 1, owner liable | 6×20 | +2,076.23 [+1,726.83, +2,425.62] * | +1,964.08 [+1,632.98, +2,295.19] * | +1,851.95 [+1,538.94, +2,164.95] * | +1,627.68 [+1,350.12, +1,905.23] * |
| contract, t40, 1, not liable | 2×10 | +4,353.03 [+3,478.00, +5,228.06] * | +3,867.79 [+3,073.81, +4,661.77] * | +3,382.55 [+2,667.35, +4,097.75] * | +2,412.07 [+1,843.81, +2,980.33] * |
| contract, t40, 1, not liable | 2×20 | +2,279.95 [+1,833.35, +2,726.55] * | +2,022.07 [+1,617.19, +2,426.94] * | +1,764.19 [+1,399.46, +2,128.91] * | +1,248.43 [+956.66, +1,540.19] * |
| contract, t40, 1, not liable | 6×10 | +3,774.04 [+3,049.16, +4,498.91] * | +3,381.37 [+2,726.98, +4,035.76] * | +2,988.70 [+2,403.80, +3,573.60] * | +2,203.36 [+1,752.60, +2,654.13] * |
| contract, t40, 1, not liable | 6×20 | +1,974.20 [+1,592.38, +2,356.02] * | +1,768.57 [+1,422.86, +2,114.28] * | +1,562.94 [+1,252.67, +1,873.22] * | +1,151.68 [+909.07, +1,394.29] * |
| contract, t100, 1, not liable | 2×10 | +4,920.36 [+3,881.76, +5,958.96] * | +4,457.56 [+3,492.77, +5,422.35] * | +3,994.77 [+3,101.19, +4,888.34] * | +3,069.17 [+2,307.36, +3,830.99] * |
| contract, t100, 1, not liable | 2×20 | +2,534.82 [+2,048.18, +3,021.45] * | +2,290.24 [+1,840.44, +2,740.05] * | +2,045.67 [+1,631.11, +2,460.23] * | +1,556.53 [+1,205.81, +1,907.25] * |
| contract, t100, 1, not liable | 6×10 | +4,444.99 [+3,614.57, +5,275.42] * | +4,041.88 [+3,284.55, +4,799.21] * | +3,638.76 [+2,953.37, +4,324.14] * | +2,832.52 [+2,285.79, +3,379.25] * |
| contract, t100, 1, not liable | 6×20 | +2,304.31 [+1,897.96, +2,710.67] * | +2,092.85 [+1,724.43, +2,461.28] * | +1,881.39 [+1,550.14, +2,212.64] * | +1,458.47 [+1,198.00, +1,718.94] * |

## Owner's gain with and without the licensee's consent

Per royalty and condition: the owner's gain over all four options (as the licensing run; at 0.15 it reproduces `runs/licensing_summary.md`), and over the options every licensee accepts (none: never, gain 0). Unfloored is primary.


**Royalty 0.05**

| Condition | Gain, all options, unfloored ($) | floored ($) | Gain, accepted options only, unfloored ($) | floored ($) | Accepted − all, unfloored ($) | Owners with no accepted option | Best option with consent (counts) |
|---|---|---|---|---|---|---|---|
| cheap, t40, 0, not liable | −460.39 [−676.71, −244.08] * | +65.99 [−6.02, +138.00] | −350.45 [−578.53, −122.37] * | +63.41 [−9.01, +135.84] | +109.94 [−50.53, +270.41] | 18/60 | 2×10: 5, 2×20: 35, 6×20: 2, never: 18 |
| cheap, t40, 0, owner liable | −460.39 [−676.71, −244.08] * | +65.99 [−6.02, +138.00] | −350.45 [−578.53, −122.37] * | +63.41 [−9.01, +135.84] | +109.94 [−50.53, +270.41] | 18/60 | 2×10: 5, 2×20: 35, 6×20: 2, never: 18 |
| cheap, t40, 1, not liable | −83.63 [−298.85, +131.58] | +221.47 [+62.32, +380.62] * | −46.52 [−143.90, +50.85] | +0.00 [+0.00, +0.00] | +37.11 [−181.98, +256.19] | 59/60 | 2×20: 1, never: 59 |
| cheap, t40, 1, owner liable | −4,252.49 [−4,886.13, −3,618.86] * | +0.00 [+0.00, +0.00] | −4,409.88 [−5,127.70, −3,692.06] * | +0.00 [+0.00, +0.00] | −157.39 [−486.80, +172.03] | 0/60 | 2×10: 1, 2×20: 59 |
| cheap, t100, 0, not liable | +1,897.89 [+1,419.78, +2,376.01] * | +1,906.20 [+1,431.73, +2,380.66] * | +211.42 [+48.63, +374.22] * | +219.43 [+56.65, +382.21] * | −1,686.47 [−2,151.06, −1,221.88] * | 36/60 | 2×10: 11, 2×20: 12, 6×10: 1, never: 36 |
| cheap, t100, 0, owner liable | +1,897.89 [+1,419.78, +2,376.01] * | +1,906.20 [+1,431.73, +2,380.66] * | +211.42 [+48.63, +374.22] * | +219.43 [+56.65, +382.21] * | −1,686.47 [−2,151.06, −1,221.88] * | 36/60 | 2×10: 11, 2×20: 12, 6×10: 1, never: 36 |
| cheap, t100, 1, not liable | +1,130.57 [+807.84, +1,453.30] * | +1,138.69 [+818.04, +1,459.34] * | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | −1,130.57 [−1,453.30, −807.84] * | 60/60 | never: 60 |
| cheap, t100, 1, owner liable | −5,750.96 [−6,563.44, −4,938.49] * | +0.00 [+0.00, +0.00] | −5,750.96 [−6,563.44, −4,938.49] * | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | 0/60 | 2×20: 60 |
| contract, t40, 1, not liable | +1,245.67 [+910.52, +1,580.81] * | +1,248.11 [+914.89, +1,581.32] * | +1,190.99 [+850.60, +1,531.37] * | +1,193.56 [+855.00, +1,532.12] * | −54.68 [−158.53, +49.17] | 0/60 | 2×10: 12, 2×20: 6, 6×10: 40, 6×20: 2 |
| contract, t100, 1, not liable | +1,646.22 [+1,232.19, +2,060.25] * | +1,649.24 [+1,237.54, +2,060.95] * | +1,514.21 [+1,078.65, +1,949.78] * | +1,518.97 [+1,085.96, +1,951.99] * | −132.00 [−313.33, +49.33] | 0/60 | 2×10: 9, 2×20: 3, 6×10: 44, 6×20: 4 |

**Royalty 0.10** (headline)

| Condition | Gain, all options, unfloored ($) | floored ($) | Gain, accepted options only, unfloored ($) | floored ($) | Accepted − all, unfloored ($) | Owners with no accepted option | Best option with consent (counts) |
|---|---|---|---|---|---|---|---|
| cheap, t40, 0, not liable | −51.08 [−250.21, +148.05] | +203.85 [+81.92, +325.78] * | −228.94 [−408.89, −48.99] * | +67.29 [+5.71, +128.87] * | −177.86 [−332.52, −23.20] * | 26/60 | 2×10: 4, 2×20: 29, 6×20: 1, never: 26 |
| cheap, t40, 0, owner liable | −51.08 [−250.21, +148.05] | +203.85 [+81.92, +325.78] * | −228.94 [−408.89, −48.99] * | +67.29 [+5.71, +128.87] * | −177.86 [−332.52, −23.20] * | 26/60 | 2×10: 4, 2×20: 29, 6×20: 1, never: 26 |
| cheap, t40, 1, not liable | +167.51 [−52.44, +387.46] | +343.75 [+150.09, +537.40] * | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | −167.51 [−387.46, +52.44] | 60/60 | never: 60 |
| cheap, t40, 1, owner liable | −4,115.52 [−4,731.26, −3,499.78] * | +0.00 [+0.00, +0.00] | −4,268.47 [−4,968.59, −3,568.35] * | +0.00 [+0.00, +0.00] | −152.95 [−473.07, +167.17] | 0/60 | 2×10: 1, 2×20: 59 |
| cheap, t100, 0, not liable | +4,053.12 [+3,190.88, +4,915.36] * | +4,053.12 [+3,190.88, +4,915.36] * | +199.57 [+40.04, +359.11] * | +199.70 [+40.20, +359.20] * | −3,853.55 [−4,752.50, −2,954.60] * | 43/60 | 2×10: 11, 2×20: 6, never: 43 |
| cheap, t100, 0, owner liable | +4,053.12 [+3,190.88, +4,915.36] * | +4,053.12 [+3,190.88, +4,915.36] * | +199.57 [+40.04, +359.11] * | +199.70 [+40.20, +359.20] * | −3,853.55 [−4,752.50, −2,954.60] * | 43/60 | 2×10: 11, 2×20: 6, never: 43 |
| cheap, t100, 1, not liable | +2,154.71 [+1,696.66, +2,612.76] * | +2,154.71 [+1,696.66, +2,612.76] * | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | −2,154.71 [−2,612.76, −1,696.66] * | 60/60 | never: 60 |
| cheap, t100, 1, owner liable | −5,533.15 [−6,310.26, −4,756.04] * | +0.00 [+0.00, +0.00] | −5,533.15 [−6,310.26, −4,756.04] * | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | 0/60 | 2×20: 60 |
| contract, t40, 1, not liable | +3,553.94 [+2,920.20, +4,187.67] * | +3,553.94 [+2,920.20, +4,187.67] * | +3,442.72 [+2,768.04, +4,117.41] * | +3,442.72 [+2,768.04, +4,117.41] * | −111.21 [−287.39, +64.96] | 0/60 | 2×10: 4, 6×10: 54, 6×20: 2 |
| contract, t100, 1, not liable | +4,047.72 [+3,304.66, +4,790.77] * | +4,047.72 [+3,304.66, +4,790.77] * | +3,804.07 [+2,997.56, +4,610.59] * | +3,804.07 [+2,997.56, +4,610.59] * | −243.64 [−531.14, +43.85] | 0/60 | 2×10: 8, 6×10: 52 |

**Royalty 0.15**

| Condition | Gain, all options, unfloored ($) | floored ($) | Gain, accepted options only, unfloored ($) | floored ($) | Accepted − all, unfloored ($) | Owners with no accepted option | Best option with consent (counts) |
|---|---|---|---|---|---|---|---|
| cheap, t40, 0, not liable | +476.42 [+194.10, +758.75] * | +572.94 [+324.08, +821.81] * | −68.00 [−166.75, +30.76] | +52.69 [−3.58, +108.97] | −544.42 [−786.38, −302.46] * | 35/60 | 2×10: 5, 2×20: 19, 6×20: 1, never: 35 |
| cheap, t40, 0, owner liable | +476.42 [+194.10, +758.75] * | +572.94 [+324.08, +821.81] * | −68.00 [−166.75, +30.76] | +52.69 [−3.58, +108.97] | −544.42 [−786.38, −302.46] * | 35/60 | 2×10: 5, 2×20: 19, 6×20: 1, never: 35 |
| cheap, t40, 1, not liable | +463.92 [+231.46, +696.38] * | +536.64 [+312.53, +760.75] * | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | −463.92 [−696.38, −231.46] * | 60/60 | never: 60 |
| cheap, t40, 1, owner liable | −3,978.53 [−4,577.26, −3,379.80] * | +0.00 [+0.00, +0.00] | −4,127.04 [−4,810.23, −3,443.86] * | +0.00 [+0.00, +0.00] | −148.51 [−459.36, +162.33] | 0/60 | 2×10: 1, 2×20: 59 |
| cheap, t100, 0, not liable | +6,232.92 [+4,967.72, +7,498.13] * | +6,232.92 [+4,967.72, +7,498.13] * | +262.44 [+35.20, +489.67] * | +262.44 [+35.20, +489.67] * | −5,970.48 [−7,278.12, −4,662.85] * | 45/60 | 2×10: 13, 2×20: 2, never: 45 |
| cheap, t100, 0, owner liable | +6,232.92 [+4,967.72, +7,498.13] * | +6,232.92 [+4,967.72, +7,498.13] * | +262.44 [+35.20, +489.67] * | +262.44 [+35.20, +489.67] * | −5,970.48 [−7,278.12, −4,662.85] * | 45/60 | 2×10: 13, 2×20: 2, never: 45 |
| cheap, t100, 1, not liable | +3,439.59 [+2,789.73, +4,089.46] * | +3,439.59 [+2,789.73, +4,089.46] * | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | −3,439.59 [−4,089.46, −2,789.73] * | 60/60 | never: 60 |
| cheap, t100, 1, owner liable | −5,315.31 [−6,057.57, −4,573.05] * | +0.00 [+0.00, +0.00] | −5,315.31 [−6,057.57, −4,573.05] * | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | 0/60 | 2×20: 60 |
| contract, t40, 1, not liable | +5,909.94 [+4,868.62, +6,951.27] * | +5,909.94 [+4,868.62, +6,951.27] * | +5,632.70 [+4,486.52, +6,778.88] * | +5,632.70 [+4,486.52, +6,778.88] * | −277.24 [−606.82, +52.33] | 0/60 | 2×10: 6, 6×10: 52, 6×20: 2 |
| contract, t100, 1, not liable | +6,466.43 [+5,296.70, +7,636.16] * | +6,466.43 [+5,296.70, +7,636.16] * | +6,007.51 [+4,701.52, +7,313.49] * | +6,007.51 [+4,701.52, +7,313.49] * | −458.92 [−893.73, −24.11] * | 0/60 | 2×10: 8, 6×10: 50, 6×20: 2 |

**Royalty 0.25**

| Condition | Gain, all options, unfloored ($) | floored ($) | Gain, accepted options only, unfloored ($) | floored ($) | Accepted − all, unfloored ($) | Owners with no accepted option | Best option with consent (counts) |
|---|---|---|---|---|---|---|---|
| cheap, t40, 0, not liable | +1,865.60 [+1,263.83, +2,467.37] * | +1,866.30 [+1,264.90, +2,467.70] * | +4.59 [−40.78, +49.96] | +42.89 [+5.92, +79.87] * | −1,861.00 [−2,459.10, −1,262.91] * | 44/60 | 2×10: 4, 2×20: 12, never: 44 |
| cheap, t40, 0, owner liable | +1,865.60 [+1,263.83, +2,467.37] * | +1,866.30 [+1,264.90, +2,467.70] * | +4.59 [−40.78, +49.96] | +42.89 [+5.92, +79.87] * | −1,861.00 [−2,459.10, −1,262.91] * | 44/60 | 2×10: 4, 2×20: 12, never: 44 |
| cheap, t40, 1, not liable | +1,449.30 [+1,091.41, +1,807.19] * | +1,449.72 [+1,092.08, +1,807.36] * | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | −1,449.30 [−1,807.19, −1,091.41] * | 60/60 | never: 60 |
| cheap, t40, 1, owner liable | −3,704.58 [−4,272.31, −3,136.86] * | +0.00 [+0.00, +0.00] | −3,844.22 [−4,496.11, −3,192.34] * | +0.00 [+0.00, +0.00] | −139.64 [−431.91, +152.63] | 0/60 | 2×10: 1, 2×20: 59 |
| cheap, t100, 0, not liable | +10,594.07 [+8,503.45, +12,684.69] * | +10,594.07 [+8,503.45, +12,684.69] * | +322.49 [−30.26, +675.23] | +322.49 [−30.26, +675.23] | −10,271.58 [−12,456.44, −8,086.73] * | 49/60 | 2×10: 11, never: 49 |
| cheap, t100, 0, owner liable | +10,594.07 [+8,503.45, +12,684.69] * | +10,594.07 [+8,503.45, +12,684.69] * | +322.49 [−30.26, +675.23] | +322.49 [−30.26, +675.23] | −10,271.58 [−12,456.44, −8,086.73] * | 49/60 | 2×10: 11, never: 49 |
| cheap, t100, 1, not liable | +6,020.86 [+4,951.19, +7,090.54] * | +6,020.86 [+4,951.19, +7,090.54] * | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | −6,020.86 [−7,090.54, −4,951.19] * | 60/60 | never: 60 |
| cheap, t100, 1, owner liable | −4,879.67 [−5,554.17, −4,205.17] * | +0.00 [+0.00, +0.00] | −4,879.67 [−5,554.17, −4,205.17] * | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | 0/60 | 2×20: 60 |
| contract, t40, 1, not liable | +10,621.96 [+8,711.70, +12,532.22] * | +10,621.96 [+8,711.70, +12,532.22] * | +9,170.96 [+6,896.20, +11,445.72] * | +9,170.96 [+6,896.20, +11,445.72] * | −1,451.00 [−2,263.55, −638.45] * | 1/60 | 2×10: 19, 6×10: 40, never: 1 |
| contract, t100, 1, not liable | +11,303.85 [+9,224.44, +13,383.27] * | +11,303.85 [+9,224.44, +13,383.27] * | +9,647.03 [+7,145.11, +12,148.94] * | +9,647.03 [+7,145.11, +12,148.94] * | −1,656.83 [−2,566.30, −747.35] * | 1/60 | 2×10: 18, 2×20: 1, 6×10: 39, 6×20: 1, never: 1 |

## Run record

- engine version: 0.16.0
- commit: 35614d1bcd7d0f4fde0123398e37cf716cf9bd6c
- script sha256: 815d6c074f5be5cbb040e6fb8a694de0f4361a5fda47d3e3d960a78a683c430b
- commands: `nice -n 19 python -m analysis.licensing_checks --royalty-check`, then `--collect`, then `--analyse`
- python: 3.12.7
- numpy: 2.5.4
- platform: macOS-26.6.2-arm64-arm-64bit
- workers: 4
- chains: 1640 replayed
- wall: royalty check: wall 0.08 h; load [8.09, 6.86, 4.85]; memory {'swap_free_mb': 848.31, 'free_pct': 50}; collection: wall 3.59 h; load [5.96, 6.13, 6.3]; memory {'swap_free_mb': 848.31, 'free_pct': 53}
- load: start/end lines in runs/licensing_checks_run.log

## Caveats

- **Exploratory, written after the licensing results.** Nothing here changes a prediction or verdict in `runs/licensing_summary.md`. The intervals are unadjusted, across many tables and four royalties.
- **The royalty recompute is exact only for these policies.** It holds because no policy here reads profit and evolution is off. With `rule_genuine_rational_v2` or evolution on, the royalty would feed back into decisions, and each rate would need its own run.
- **Acceptance is judged with hindsight, on one realisation.** Each licensee compares its realised licensed profit with its realised never profit in the same seed, not expected profit. "Every licensee accepts" means all N draws must be non-negative, which mechanically penalises N = 6. For example, cheap 6×10 without enforcement: mean licensee profit +$216, 55% accept, 0 of 60 owners all-accept.
- **The licensee's only alternative is the never chain.** There is no other owner to sign with, no renegotiation, and no replacing a licensee who declines. As specified, one refusal sends the owner to never (gain 0). An owner whose best option lost money is therefore raised to 0 when no licensee would sign. This is why "accepted − all" can be positive (cheap t40 without enforcement, royalty 0.05).
- **The owner still picks its best option with hindsight**, now among the accepted options, as in the licensing run.
- **Royalty on extra units follows the spec.** It is royalty × the licensee's mean licensed price × max(0, extra units), per licensee. With mean extra units near 0 (cheap), the max(0, ·) term makes it an upper bound on royalty from extra sales, so the "share on sales made anyway" is a lower bound. A pooled, signed version (above) was computed after seeing this; it has no interval. Neither version counts the royalty on the price premium as "extra".
- **Owner liable is derived for 18 of the 20 seeds.** The not-liable ledger is moved, fines at licensees from the licence day going to the owner. This rests on no decision reading who pays. It was checked by replaying seeds 250–251 (96/96 identical) and against the saved owner totals for all seeds (960/960). Under owner liability, a licensee also sheds fines it would have paid anyway, which inflates its acceptance.
- **Licence windows.** The licence-day windows count from day b. Before day b, the licensed and never chains are not compared.
- **Earlier caveats still apply.** Contract licensees were run only at detect_scale 1, owner not liable. Licensees are drawn from non-genuine stalls. The royalty and premium values are placeholders.
- **CSV fix before commit.** `runs/licensing_checks.csv` first wrote royalty paid over the rate column (a key collision). This was fixed before commit: the column is now `rate`, and royalty paid is `royalty_paid`. The tables never used the CSV and did not change.
