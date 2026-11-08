# Pilot gate: verification boundary

**Pilot, not results.** Throwaway seeds 905–909; never reuse them for confirmatory work.

## Setting

The main run's settings (`analysis/verification.py`): choice-set demand, m 3, gamma 0, 150 buyers, budget 1.25 × base, tourists 0.4 (locals 0.3, experts 0.3), D = 30, ratings public (memory 0.7), brands on (premium 0.4), bargain hunters 0.2 with Q_req 0.15–0.40, naive deceptive sellers, fresh reopening, every genuine stall honest.
- Engine `0.13.0`, commit `64dd293d1f19f9c3a61a99774ff5f02e2459c5e6`; script sha256 `6063aa3fcd9d298d0e6775e8eab18048a09a1c3b4de0efcc9de3359874f3903d`; verification.py sha256 `fcf2193baccc12f63142069dcef3410859dc300c9d1e12cab650e1b76a245822`.
- Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit; 4 workers at nice 19; wall clock 10.2 min; load [4.02, 4.53, 4.33] → [6.05, 5.63, 5.0]; memory {'swap_free_mb': 1041.69, 'free_pct': 85} → {'swap_free_mb': 1041.69, 'free_pct': 85}.

## Gates

- **G1 seconds** (**FAIL**): seconds stalls average 0.88 customers a day over days 1–10 (gate ≥ 1); 48% of seconds stall-seeds are at ≥ 1.
- **G2 demand** (pass): 100% of genuine stall-seeds average ≥ 1 customer a day (gate ≥ 90%); 100% of genuine brands rated by day 10 (gate ≥ 80%).
- **G3 catch rate** (pass): catches a day choice-set 28.6 vs walk 32.1 (ratio 0.89); false claims made with an inspector in earshot a day 504.8 vs 645.5 (ratio 0.78); criterion: catch ratio within 25% of the in-earshot claim ratio.
- **G4 timing**: tourists 0.4 / locals inspect at full size, seeds 905-906: A|t40|l1: 32 chains in 3.2 min (6.0 s a chain on 4 workers); B|t40|l1: 32 chains in 5.0 min (9.3 s a chain on 4 workers). Projected for both stages: 10.2 h at 30 seeds (4800 chains), 6.8 h at 20. Main run seeds: **200-219**.

## Customers a day, days 1–10, no inspectors

| Stall type | Stall-seeds | Mean | Share ≥ 1 | Lowest |
|---|---|---|---|---|
| genuine | 90 | 4.52 | 100% | 1.50 |
| deceptive | 75 | 2.54 | 100% | 1.10 |
| seconds | 75 | 0.88 | 48% | 0.00 |

## G3 detail: per day, mean over 5 seeds × 30 days, 2 patrolling inspectors

| | Choice-set | Walk |
|---|---|---|
| catches | 28.6 | 32.1 |
| false-claim messages | 1290.5 | 1782.2 |
| … with an inspector in earshot | 504.8 | 645.5 |
| false-claim impressions received by inspectors | 97.4 | 115.1 |
| false-claim impressions (all) | 1766.5 | 2485.8 |
| purchases | 95.0 | 99.3 |
| units sold by deceptive stalls | 35.5 | 24.7 |
| catches per false claim in earshot | 0.057 | 0.050 |

## Notes

Written after the pilot ran (2026-11-08). Pilot observations, not results.

- **G1 failed, so the main run was not started** (spec: "If any gate fails, stop and report"). Seconds stalls average 0.88 customers a day over days 1–10; the gate is 1.0. Only 48% of seconds stall-seeds reach 1 a day.
- **Why G1 fails.** This is a post-hoc check on seeds 905–906, days 1–10. Regular buyers (Q_req 0.50–0.70) never accept a seconds stall, since seconds quality is 0.16–0.43. Bargain hunters accept one when its quality meets their Q_req (0.15–0.40), and then they buy from it often: 256 of the 324 times it was acceptable and in their set. So the limit is how many bargain hunters reach a seconds stall. With 150 buyers, 20% bargain hunters, 3 stalls in a set from 16 per category, 5 seconds stalls per category and an acceptable-quality share of about 57%, that comes to roughly 0.85 customers per seconds stall per day, which matches the 0.88 measured. Any of these would likely clear the gate: a bargain share of about 0.3; a bargain Q_req range of about [0.15, 0.30], so more seconds qualify; or more buyers. Each is a design change for you to decide, so none was made.
- **G3: the high catch rate is not a choice-set effect.** Walk mode catches slightly more (32.1 a day against 28.6). Catches per false claim made within an inspector's earshot are similar: 0.050 in walk mode, 0.057 in choice-set mode. About 28–32 catches a day is what 2 patrolling inspectors do in this market under either demand mode. Deceptive stalls sell more in choice-set mode (35.5 units a day against 24.7) while making fewer false claims, because buyers consider them only when they are in the set.
- **G4: projected 10.2 h for both stages at 30 seeds**, so the rule would cut the main run to 20 seeds (200–219, about 6.8 h). Stage B runs at about 1.5× stage A's time per chain. G4 timed one condition in each stage rather than one condition overall, because timing only a stage B condition would have overstated stage A's time.
- **Memory guard.** macOS had shrunk total swap to 2 GB, with about 1 GB of old pages in it, while 85% of memory was free. The guard's 1,024 MB free-swap floor then paused a pipeline check for no reason. `analysis/verification.py` now defaults to a 512 MB floor and keeps the 15% free-memory floor.
- **Pipeline check (not in this report's numbers).** `analysis/verification.py` ran end to end on seed 905, both stages, 160 chains, in a scratch directory, and its outputs were discarded. The only fix afterwards was the gain plot's y range, which ignored the means when there was a single seed. After a bust-out, brand ratings now do fall (every day-20 bust in that check), unlike in walk mode.
