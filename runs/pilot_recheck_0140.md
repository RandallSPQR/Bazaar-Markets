# Choice-set pilot P2 and P3, rechecked at engine 0.14.0

Engine 0.14.0 at f0ea358 (trapped- and parked-buyer fixes) against the committed pilot at engine 0.12.0 (6fb75b7). Throwaway seeds 900–904, 150 buyers, the pilot's own job and check functions. Pipeline checks, not results.

## P2 enforcement regression: **pass** (was pass)

Single day, naive sellers, 2 inspectors; mean over 5 seeds.

| | Engine 0.12.0 | Engine 0.14.0 |
|---|---|---|
| Deceptive profit per stall, posts ($) | 14.18 | 11.86 |
| Deceptive profit per stall, patrolling ($) | -187.68 | -216.22 |
| Shortfall rate, posts | 0.167 | 0.164 |
| Shortfall rate, patrolling | 0.116 | 0.080 |
| Catches, posts | 8.6 | 10.8 |
| Catches, patrolling | 35.2 | 40.2 |
| Patrolling − posts, deceptive profit ($) | -201.86 | -228.09 |
| Patrolling − posts, shortfall | -0.052 | -0.084 |

## P3 counterfeit smoke: **pass** (was pass)

Fresh vs counterfeit reopening, deceptive price factor 0.8, 2 patrolling inspectors, 30 days, 5 seeds (totals).

| Arm | Engine | Catches | Renames | Counterfeit units sold (to tourists) | Floors |
|---|---|---|---|---|---|
| fresh | 0.12.0 | 4,251 | 4,247 | 0 (0) | none |
| fresh | 0.14.0 | 4,694 | 4,693 | 0 (0) | none |
| counterfeit | 0.12.0 | 4,219 | 4,217 | 2,243 (1,922) | none |
| counterfeit | 0.14.0 | 4,727 | 4,725 | 2,556 (2,215) | none |

## Stuck-buyer guard

Across all 20 runs: stuck_buyers 0, idle_choosers 0.

Wall clock 2.3 min on 4 workers at nice 19; Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit.
## Reading (written after the results; added by hand, not by the script)

Both gates pass as before, with the same sign and a larger size. With the fixes, buyers who were
trapped or parked go on to buy, so more purchases reach deceptive stalls. Catches rise by 14–26%
(P2) and 10–12% (P3), and counterfeit units sold rise by 14%. Patrolling now cuts deceptive profit
and the shortfall rate by more than it did at 0.12.0. These are pipeline checks on throwaway seeds,
not results.
