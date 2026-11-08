# Pilot: choice-set demand (engine 0.12.0)

**Pilot, not results.** Throwaway seeds 900–904; never reuse them for confirmatory work. Every number below is a pipeline check.

## Setting

- buyers.demand_mode = choice_set, gamma (position_rent) 0, m (consider) 3; budget 1.25 × base; tourists 0.4 (locals 0.3, experts 0.3); D = 30 known; ratings public, memory 0.7; brands on, premium 0.4; naive deceptive sellers, fresh reopening; genuine stalls honest; bargain hunters at the choice_set default (0.2).
- Engine `0.12.0`, commit `6fb75b76c4226111c63d15be8bc1e973d4533447`; Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit; 4 workers at nice 19; wall clock 11.6 min; load [2.02, 3.33, 5.06] → [5.55, 5.85, 5.63]; memory {'swap_free_mb': 1590.88, 'free_pct': 86} → {'swap_free_mb': 1686.88, 'free_pct': 85}.

## Buyer count

- 150 buyers: genuine stall-seeds with ≥ 1 customer a day over days 1–10 100% (gate ≥ 90%); genuine brands rated by day 10 100% (gate ≥ 80%): **pass**

**Chosen: 150 buyers.**

## P0 demand gate: **pass**

Days 1–10, always-honest market (no bust-out, 0 inspectors), 5 seeds.

| Stall type | Stall-seeds | Mean customers a day | Share with ≥ 1 a day | Lowest |
|---|---|---|---|---|
| genuine | 90 | 4.68 | 100% | 1.90 |
| deceptive | 75 | 2.64 | 100% | 1.10 |
| seconds | 75 | 0.44 | 27% | 0.00 |

## P1 bust-out accounting: **pass**

- Every day before the bust-out identical to the honest chain (whole day record, all stalls), for every stall and candidate day: **True**
- Loss components with the expected signs at the best day (no change before it; revenue down, cost down, no penalties or switch costs): **True**

Per sampled stall: best bust-out day (of 10, 20, 25, 27, 28, 29), unfloored gain, and the profit change from the best day to day 30 by component ($; + = bust-out better). Pipeline check, not a result.

| Seed | Stall | Honest 30-day ($) | Best day | Gain ($) | Revenue | Cost | Ad | Penalties | Units honest → bust | Honest profit from best day ($) |
|---|---|---|---|---|---|---|---|---|---|---|
| 900 | s14 | 328 | 29 | +2 | -12 | +14 | +0.00 | +0 | 4 → 3 | 9 |
| 900 | s27 | 2,784 | 27 | -254 | -823 | +569 | +0.00 | +0 | 25 → 9 | 409 |
| 900 | s41 | 7,777 | 29 | -106 | -648 | +542 | +0.00 | +0 | 10 → 6 | 530 |
| 901 | s33 | 15,181 | 29 | -376 | -1,037 | +660 | +0.00 | +0 | 12 → 5 | 672 |
| 901 | s32 | 14,528 | 29 | -577 | -1,786 | +1,209 | -0.24 | +0 | 17 → 5 | 878 |
| 901 | s09 | 622 | 29 | -42 | -116 | +74 | +0.02 | +0 | 16 → 4 | 60 |
| 902 | s29 | 2,874 | 29 | -324 | -773 | +449 | +0.00 | +0 | 19 → 3 | 376 |
| 902 | s45 | 5,301 | 27 | -72 | -414 | +342 | +0.24 | +0 | 8 → 6 | 404 |
| 902 | s44 | 6,417 | 29 | -500 | -1,584 | +1,084 | +0.00 | +0 | 13 → 2 | 622 |
| 903 | s28 | 3,097 | 29 | -86 | -240 | +154 | +0.00 | +0 | 7 → 2 | 120 |
| 903 | s04 | 931 | 29 | -57 | -173 | +116 | +0.00 | +0 | 22 → 4 | 76 |
| 903 | s06 | 621 | 29 | -59 | -173 | +113 | +0.00 | +0 | 20 → 2 | 68 |
| 904 | s18 | 4,545 | 29 | -268 | -778 | +509 | -0.16 | +0 | 19 → 3 | 320 |
| 904 | s25 | 2,654 | 29 | -139 | -336 | +197 | +0.00 | +0 | 7 → 0 | 109 |
| 904 | s11 | 448 | 29 | -44 | -115 | +71 | +0.00 | +0 | 15 → 3 | 55 |

Mean gain $-194 over 15 stall-seeds (1 positive); best days: 27: 2, 29: 13.

## P2 enforcement regression: **pass**

Single day, naive sellers, 2 inspectors, 5 seeds; patrolling − posts (mean over seeds).

- Deceptive profit per stall: posts $14.18, patrolling $-187.68; difference $-201.86 (per seed, cents: [-22491.266666666663, -20947.533333333333, -14306.000000000002, -15713.133333333335, -27473.8])
- Shortfall rate: posts 0.167, patrolling 0.116; difference -0.052 (per seed: [-0.064, -0.056, -0.01, -0.052, -0.078])
- Catches: posts 8.6, patrolling 35.2

## P3 counterfeit smoke: **pass**

Fresh vs counterfeit reopening, deceptive price factor 0.8, 2 patrolling inspectors, 30 days, 5 seeds.

- fresh: catches 4251, renames {'fresh': 4247, 'counterfeit': 0}, counterfeit units sold 0 (to tourists 0); floors: none
- counterfeit: catches 4219, renames {'fresh': 0, 'counterfeit': 4217}, counterfeit units sold 2243 (to tourists 1922); floors: none

## Surprises

Written after the pilot ran (2026-11-08). Pilot observations, not results.

- **The best bust-out day is still the last candidate.** It is day 29 in 13 of 15 stall-seeds (day 27 in 2), and 14 of 15 lose even by busting out on day 29. Demand is no longer the reason: every genuine stall now has customers. The reason is the one the Step 1 diagnostic found (`runs/loss_diagnostic.txt`). Experts always inspect, and locals inspect stalls that advertise, so they stop buying on the first tick after a bust-out; only tourists keep buying. A bust-out loses the revenue of its inspecting customers and saves only the cost difference on what tourists still buy. The bust-out chains cut units from the best day to day 30 from 4–25 to 0–9. With candidates ending at 29, the benchmark may still be bounded by the candidate set (day 30 is untested).
- **Seconds stalls still barely sell** even with 20% bargain hunters: 0.44 customers a day, and 27% of seconds stall-seeds reach ≥ 1 a day. A bargain hunter's set of 3 holds about one seconds stall on average. Locals and experts pick the highest visible rating first, and an honestly rated genuine stall (rating 1, price 1.2 × base) is within a 1.25 × budget, so they buy genuine. Mostly only tourists, who pick on price, buy seconds. P0 does not gate seconds stalls, but a floor check on seconds sales would still flag some cells.
- **Patrolling inspectors catch a lot.** There were 35 catches a day in the single-day P2 market, against 8.6 at posts, and about 28 a day in P3 (4,251 over 5 seeds × 30 days), with a fresh or counterfeit reopening after nearly every catch. In P2, deceptive profit per stall is −$188 a day under patrolling. Enforcement code did not change in 0.12.0. But in choice_set mode every buyer of a category walks that category's whole aisle, so deceptive stalls make many more false claims within an inspector's earshot. That is a likely reason, not yet checked against walk mode.
- **Counterfeits sell mostly to tourists,** as intended: 1,922 of 2,243 counterfeit units.
- **Honest 30-day profit spans two orders of magnitude** across sampled stalls ($328 to $15,181), by category and by luck of position. Gains in dollars are not comparable across stalls without scaling.
