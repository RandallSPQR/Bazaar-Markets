# Run B summary: realistic aisles, solvency and the rent trap (plan 2026-11-27, engine 1.3.1), seeds 720–739

**BLUF.**
- **PB1 not supported.** Start cash 2 − start cash 20 at ds 0, α 0, pooled: −0.24 of honest profit [−0.81, +0.33], n 15. The secondary unit and base-price units both give intervals around 0. The rent-trap prediction finds no support.
- **PB2 not supported.** Designer − fish at ds 0, cash 20, α 0: +1.02 [−1.40, +3.45], n 6.
  - Only 6 seeds have both aisles defined, because the fish stall's honest profit is ≤ 0 in 14 of 20 seeds.
  - In base-price units (post hoc) it is +1.21 [−1.36, +3.79], n 20.
- **The same honest-profit problem as Run A, in two aisles.** At ds 0, sampled fish and electronics stalls have never profit ≤ 0 in 9–15 of 20 seeds per cell. Their fixed-cost shares are 0.90 and 0.85, and ad spend is not in the baseline.
- **Exits in the cash-2 cells.** In B|cash2|a0|ds0 and B|cash2|a1|ds0, 21 and 30 of 360 genuine stall-seeds exit before day 10. That is 5.8% and 8.3%, above G4b's 5%.
  - G4b is a pilot gate and passed there (3.7%, seeds 900–902). The main runs were already complete, so this is reported, not a STOP.
- Guards are all 0 over 11,520,000 buyer-days.

Record: as in `runs/aisles_A_summary.md`. Run B used 2,560 chains. Analysis `runs/aisles_B.json`, post hoc contrasts `runs/aisles_secondary_units.json`. Deviations D1–D7 are in force.

## Predictions

| Prediction | Contrast | Primary (D5), n | Verdict | Secondary (mean of ratios), n | Verdict |
|---|---|---|---|---|---|
| PB1 | ds 0, α 0: cash 2 − cash 20, pooled | −0.241 [−0.812, +0.331], 15 | not supported | −0.170 [−0.585, +0.245], 16 | not supported |
| PB2 | ds 0, cash 20, α 0: designer − fish | +1.024 [−1.401, +3.449], 6 | not supported | +1.024 [−1.401, +3.449], 6 | not supported |

Under D2 a per-aisle figure is one stall's own ratio, so the primary and secondary units coincide for PB2.

Post hoc in the plan's secondary units (written after the results), n 20:

| Contrast | Base-price units | Dollars per stall |
|---|---|---|
| PB1: cash 2 − cash 20 | +0.09 [−0.90, +1.08] | −0.45 [−91, +90] |
| PB2: designer − fish | +1.21 [−1.36, +3.79] | +88 [−249, +424] |

## Exploratory (PB3)

| Effect | Primary (D5), n | Base-price units (post hoc), n 20 |
|---|---|---|
| Cash 2 − cash 20, fish (ds 0, α 0) | +0.029 [−0.151, +0.209], 6 | −0.25 [−1.10, +0.61] |
| Cash 2 − cash 20, electronics | +0.053 [−0.205, +0.311], 5 | +0.75 [−0.12, +1.62] |
| Cash 2 − cash 20, designer | −0.368 [−1.211, +0.475], 15 | −0.24 [−2.41, +1.92] |
| α 1 − α 0, cash 2 (ds 0) | +0.076 [+0.010, +0.143], 17 | −0.06 [−1.34, +1.23] |
| α 1 − α 0, cash 20 (ds 0) | −0.194 [−0.722, +0.334], 15 | 0.00 [0.00, 0.00] |
| ds 1: cash 2 − cash 20 (α 0) | +0.374 [−0.012, +0.760], 18 | +0.36 [−1.02, +1.75] |
| ds 1: designer − fish (cash 20, α 0) | +4.97 [−5.76, +15.69], 9 | −3.32 [−5.82, −0.83] |

Rent leaves the gain unchanged when it causes no exit, because it is charged identically in the never and bust-out chains. At cash 20 the α effect on the gain is exactly 0 in every seed. On the primary unit, α acts only through the denominator (honest profit after rent).

Cells, pooled (n 20 seeds unless marked):

| Cell | Primary (D5), n | Stall-seeds with never profit ≤ 0 (of 60) | Gain, base-price units | Never profit, $ per stall (fish / electronics / designer) |
|---|---|---|---|---|
| cash 20, α 0, ds 0 | +0.231 [−0.330, +0.792], 15 | 34 | +0.13 [−1.34, +1.59] | −36 / −463 / +5,934 |
| cash 20, α 1, ds 0 | +0.023 [−0.057, +0.104], 19 | 29 | +0.13 [−1.34, +1.59] | −32 / −341 / +6,181 |
| cash 2, α 0, ds 0 | −0.012 [−0.058, +0.033], 17 | 26 | +0.21 [−0.90, +1.32] | +26 / +142 / +6,766 |
| cash 2, α 1, ds 0 | +0.010 [−0.097, +0.118], 20 | 18 | +0.16 [−0.86, +1.17] | +16 / +380 / +7,182 |
| cash 20, α 0, ds 1 | −0.515 [−0.920, −0.109], 18 | 23 | −8.35 [−9.39, −7.31] | +38 / −91 / +7,279 |
| cash 20, α 1, ds 1 | −0.270 [−0.384, −0.156], 19 | 15 | −8.40 [−9.39, −7.40] | +66 / +69 / +7,541 |
| cash 2, α 0, ds 1 | −0.157 [−0.210, −0.105], 19 | 9 | −7.99 [−9.11, −6.87] | +180 / +698 / +11,642 |
| cash 2, α 1, ds 1 | −0.110 [−0.129, −0.091], 20 | 5 | −8.24 [−9.35, −7.13] | +218 / +893 / +14,591 |

With start cash 2, honest profits are higher. That is because many competitors exit: seconds and deceptive stalls at ds 0, deceptive stalls at ds 1. The survivors' sales rise.

## Exits by type and reason (never chains, exploratory, D7)

Each cell has 360 genuine, 300 seconds and 300 deceptive stall-seeds. Each entry reads before day 10 / by day 30. Every exit is an insolvency.

| Cell | Genuine | Seconds | Deceptive |
|---|---|---|---|
| cash 20, α 0, ds 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| cash 20, α 1, ds 0 | 0 / 1 | 0 / 0 | 0 / 0 |
| cash 20, α 0, ds 1 | 0 / 0 | 0 / 0 | 0 / 205 |
| cash 20, α 1, ds 1 | 0 / 0 | 0 / 0 | 0 / 196 |
| cash 2, α 0, ds 0 | **21** / 98 | 0 / 106 | 2 / 121 |
| cash 2, α 1, ds 0 | **30** / 93 | 4 / 128 | 0 / 65 |
| cash 2, α 0, ds 1 | 8 / 34 | 0 / 85 | 241 / 281 |
| cash 2, α 1, ds 1 | 10 / 25 | 2 / 91 | 235 / 291 |

- Genuine exits before day 10, as a share of genuine stalls: 5.8% and 8.3% in the two cash-2 ds 0 cells (G4b's limit is 5%, applied at the pilot), and 2.2% and 2.8% at ds 1.
- The highest share of all stalls exiting before day 10 is 25.9% (cash 2, α 0, ds 1), under G4's 50%.

## Reading (written after the results)

- **The rent trap does not show.** PB1 predicted that a stall with little cash, more likely to be forced out, has less future to protect and so gains more from busting out. Starting with 2 days of cash instead of 20 doesn't change the bust-out gain detectably on any unit. The gain in base-price units is about 0 in every ds 0 cell, ±1.
  - One reason may be the benchmark itself. It busts out a sampled stall on a fixed day and compares totals over the same 30 days; it doesn't model a stall choosing to bust out when insolvency looms.
  - And genuine stalls rarely exit early in the never chains: 21–30 of 360 exit before day 10.
- **PB2 is too thin on the primary unit (n 6) to read.** In base-price units the designer − fish difference is +1.2 with an interval that includes 0.
- **With detection on, every cell loses about 8 base-price units from busting out.** The ds 1 designer − fish difference in base units is negative (−3.3 [−5.8, −0.8]): designer bust-outs lose more.
- **Thin cash shakes out the market.** It removes about a third of the seconds stalls and many deceptive stalls by day 30, and lifts the honest survivors' profits. Rent at α 1 adds little to that.

## Caveats

- Fish and electronics honest profits are ≤ 0 for many stall-seeds at ds 0. The ratio estimands there rest on fewer seeds and on designer stalls, whose profits are much larger.
- PB2 compares one fish stall with one designer stall per seed (D2).
- The post hoc contrasts use the plan's secondary units but were not preregistered as contrasts. They change no verdict.
- Calibration came from 3 pilot seeds. Realised designer gross in the cash-20 ds 0 cell runs 16% above the calibrated baseline ($533.76 against $458.72 a day).
- Intervals are unadjusted 95% t over seeds.
