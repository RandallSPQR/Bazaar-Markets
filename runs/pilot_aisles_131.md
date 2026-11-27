# Pilot: aisles study (plan 2026-11-27, Stage 2), seeds 900–902 (second pilot, engine 1.3.1)

**BLUF. Every gate passes; the main runs launched at 21:05 on 2026-11-26.**
- G1, G2a–d, G3, G4, G4b and G5 all pass.
- G3 projects 13.0 h, under the 14 h limit.
- No genuine stall exits before day 10 in more than 3.7% of a cell's genuine stalls (G4b limit 5%).
- Seconds baseline gross is positive in every category of every calibration scenario. The lowest is fish, A|thin|hard|t40|ds0, at $0.68 a day (G2d).
- **One point for Randall before the analysis runs (about 13 h from launch).** Under D5, a per-seed ratio is undefined when the sum of the sampled never-chain profits is ≤ 0. In the pilot this happened often in the ds 0 thin-margin cells:
  - A|thin|hard|t100|ds0: all 3 seeds undefined.
  - Several other ds 0 cells: 1 seed of 3 undefined.
  - Per-aisle figures (one stall per aisle per seed, D2) are undefined even more often. PB2 (designer − fish, ds 0, cash 20, α 0) had no seed where both aisles were defined.

  So some predictions may come out with reduced n, or as "not testable", in the main runs. Nothing about it was changed, and nothing in the pilot is a result.

Engine 1.3.1 (3c4bd3b). Script `analysis/aisles_1_3.py` (sha256 16f8c60a…03cb) at commit 4f66849, clean tree. Full suite at 9023acf: 1,901 passed, 17 skipped, 0 failed (`runs/tests_131.log`). numpy 2.5.4, Python 3.12.7, macOS 27.2.1 arm64. Workers 7, normal priority, `caffeinate -i`.
- Started 2026-11-26 18:59:38, gates written 21:04:02. Calibration 60 chains, then 1,170 benchmark chains in 7,032 s; total 2.07 h.
- Memory pauses 0.
- Load averages ran 8–11 during the benchmark chains (7 workers plus the desktop).

Command:

```
PYTHONPATH=. .venv/bin/python -m analysis.aisles_1_3 --phase pilot --tests '1901 passed, 17 skipped, 0 failed at 9023acf (runs/tests_131.log)'
```

Files:
- Record: `runs/pilot_aisles/aisles_run.log`.
- Gates: `runs/pilot_aisles/aisles_pilot_gates.json`.
- Calibration: `runs/aisles_calibration.json` (made 19:05:50). The main runs read this file.
- The chain cache `runs/pilot_aisles/aisles_pilot_cache.jsonl` is kept locally, not committed, as for the first pilot.

The first pilot (engine 1.3.0, STOP at G4) is in `runs/pilot_aisles.md` and `runs/pilot_aisles_130/`.

## Gates

| Gate | Result | Pass |
|---|---|---|
| G1 | Pipeline end to end: 60 calibration chains (20 scenarios × 3 seeds), 1,170 benchmark chains | yes |
| G2a | Defaults reproduce 1.2.0: price-war never chains A\|RI\|ds0\|lex and A\|RI\|ds1\|lex, seed 500, identical | yes |
| G2b | Cost targets hold to the cent in every cell and category, the seconds target included | yes |
| G2c | A calibration chain reruns identically (exits, harm, spots, stall aggregates); the calibration recomputes identically | yes |
| G2d | Seconds baseline gross > 0 in every category of every calibration scenario; minimum $0.68/day (fish, A\|thin\|hard\|t40\|ds0) | yes |
| G3 | Projected main run 13.02 h (7,800 chains at the pilot's 7,032 s for 1,170; limit 14 h) | yes |
| G4 | Max share of all stalls exiting before day 10: 0.306 (A\|thin\|hard\|t100\|ds1 and A\|thin\|hard\|t40\|ds1; limit 0.5) | yes |
| G4b | Max share of genuine stalls exiting before day 10: 0.037 (B\|cash2\|a0\|ds0 and B\|cash2\|a1\|ds0, 2 of 54; limit 0.05) | yes |
| G5 | Stuck, idle, parked, fallbacks: all 0 over 5,535,000 buyer-days | yes |

The calibration raised no flags. Every (category, spot class) group and every (category, type) group had data.

## Calibration: baseline gross per stall-day by type (D6)

Each stall's fixed cost is fixed_cost_share × max(0, its type's baseline in that category and scenario). Start cash and credit stay on the genuine baseline.

The values below are pilot calibration means in dollars a day over seeds 900–902 for a few scenarios; the full table is in the calibration file.

| Scenario | Fish g / s / d | Electronics g / s / d | Designer g / s / d |
|---|---|---|---|
| A\|fat\|easy\|t40\|ds0 | 51.06 / 4.29 / 22.30 | 270.89 / 18.02 / 121.20 | 743.69 / 63.93 / 357.87 |
| A\|thin\|hard\|t40\|ds0 | 9.45 / 0.68 / 8.45 | 52.45 / 2.90 / 47.20 | 146.91 / 8.23 / 137.92 |
| B\|ds0 | 17.95 / 1.40 / 4.72 | 76.97 / 4.15 / 46.67 | 458.72 / 31.40 / 505.24 |
| C\|t100 | 17.53 / 1.84 / 12.49 | 68.82 / 4.84 / 75.93 | 506.80 / 51.26 / 506.94 |

(g genuine, s seconds, d deceptive.) Seconds gross is now positive everywhere; at 1.3.0 it was negative in fish (−$0.47). It is still about 5–25% of the genuine figure, so fixed costs sized to it are small.

## Exits by type and reason (never chains, 3 seeds; exploratory outcome, D7)

Each cell has 54 genuine, 45 seconds and 45 deceptive stall-seeds. Each entry reads before day 10 / by day 30. Every exit in every cell is insolvency; no stall exits for any other reason.

| Cell | Genuine | Seconds | Deceptive | All stalls, before day 10 |
|---|---|---|---|---|
| A\|fat\|easy\|t100\|ds0 | 0 / 0 | 0 / 0 | 0 / 0 | 0.000 |
| A\|fat\|easy\|t100\|ds1 | 0 / 0 | 0 / 0 | 0 / 28 | 0.000 |
| A\|fat\|easy\|t40\|ds0 | 0 / 0 | 0 / 0 | 0 / 0 | 0.000 |
| A\|fat\|easy\|t40\|ds1 | 0 / 0 | 0 / 0 | 0 / 2 | 0.000 |
| A\|fat\|hard\|t100\|ds0 | 0 / 0 | 0 / 0 | 0 / 0 | 0.000 |
| A\|fat\|hard\|t100\|ds1 | 0 / 0 | 0 / 0 | 0 / 37 | 0.000 |
| A\|fat\|hard\|t40\|ds0 | 0 / 0 | 0 / 0 | 0 / 0 | 0.000 |
| A\|fat\|hard\|t40\|ds1 | 0 / 0 | 0 / 0 | 0 / 15 | 0.000 |
| A\|thin\|easy\|t100\|ds0 | 0 / 14 | 0 / 10 | 0 / 7 | 0.000 |
| A\|thin\|easy\|t100\|ds1 | 0 / 0 | 0 / 0 | 42 / 45 | 0.292 |
| A\|thin\|easy\|t40\|ds0 | 0 / 0 | 0 / 0 | 0 / 0 | 0.000 |
| A\|thin\|easy\|t40\|ds1 | 0 / 0 | 0 / 0 | 12 / 45 | 0.083 |
| A\|thin\|hard\|t100\|ds0 | 0 / 20 | 0 / 27 | 4 / 14 | 0.028 |
| A\|thin\|hard\|t100\|ds1 | 0 / 1 | 0 / 0 | 44 / 45 | 0.306 |
| A\|thin\|hard\|t40\|ds0 | 0 / 4 | 0 / 0 | 0 / 0 | 0.000 |
| A\|thin\|hard\|t40\|ds1 | 0 / 0 | 0 / 0 | 44 / 45 | 0.306 |
| B\|cash20\|a0\|ds0 | 0 / 0 | 0 / 0 | 0 / 0 | 0.000 |
| B\|cash20\|a0\|ds1 | 0 / 0 | 0 / 0 | 0 / 30 | 0.000 |
| B\|cash20\|a1\|ds0 | 0 / 0 | 0 / 0 | 0 / 0 | 0.000 |
| B\|cash20\|a1\|ds1 | 0 / 0 | 0 / 0 | 0 / 32 | 0.000 |
| B\|cash2\|a0\|ds0 | 2 / 12 | 0 / 16 | 2 / 18 | 0.028 |
| B\|cash2\|a0\|ds1 | 0 / 2 | 0 / 12 | 34 / 42 | 0.236 |
| B\|cash2\|a1\|ds0 | 2 / 11 | 0 / 16 | 1 / 12 | 0.021 |
| B\|cash2\|a1\|ds1 | 1 / 3 | 0 / 10 | 40 / 43 | 0.285 |
| C\|a0\|t40 | 0 / 0 | 0 / 0 | 18 / 36 | 0.125 |
| C\|a0\|t100 | 0 / 12 | 0 / 0 | 26 / 36 | 0.181 |
| C\|a0.5\|t40 | 0 / 0 | 0 / 0 | 18 / 38 | 0.125 |
| C\|a0.5\|t100 | 0 / 13 | 0 / 8 | 28 / 39 | 0.194 |
| C\|a1\|t40 | 0 / 1 | 0 / 3 | 16 / 41 | 0.111 |
| C\|a1\|t100 | 0 / 11 | 0 / 9 | 32 / 42 | 0.222 |

Compared with the first pilot, the two G4 failures (B|cash2|·|ds1) fall from 52.1% and 51.4% to 23.6% and 28.5% before day 10. At ds 0, cash 2, seconds exits by day 30 fall from 44/45 and 42/45 to 16/45 in both cells.

The thin-margin t100 ds 0 genuine exits are kept, as Randall decided: 14 (easy) and 20 (hard) of 54 by day 30, against 48–50 at 1.3.0. Deceptive stalls in the ds 1 cells now account for most exits.

## Analysis dry run

As a code check, `analyse` was run in memory on the 1,170 pilot records with the seed lists set to the pilot seeds; nothing was written to the main output paths. It completed for Runs A, B and C. Every prediction produced a D5 primary and a secondary per-stall mean of ratios. Each cell carries `honest_le0`, `ratio`, `per_seed_ratio` and `per_seed_ratio_by_aisle`.

What it showed about the estimand (a property of D5 on these data, not a result). These are counts of the 9 sampled stall-seeds per cell whose never-chain profit is ≤ 0:

| Cell (ds 0) | Stall-seeds ≤ 0 (of 9) | Seeds with undefined pooled ratio (of 3) |
|---|---|---|
| A\|thin\|hard\|t100\|ds0 | 9 | 3 |
| A\|thin\|easy\|t100\|ds0 | 7 | 2 |
| A\|thin\|hard\|t40\|ds0 | 6 | 1 |
| A\|thin\|easy\|t40\|ds0 | 5 | 1 |
| B\|cash20\|a0\|ds0 | 5 | 1 |
| B\|cash2\|a0\|ds0 | 4 | 1 |
| A\|fat\|hard\|t100\|ds0 | 2 | 0 |
| A\|fat\|·\|t40\|ds0 | 0 | 0 |

In the ds 1 cells the count is 0–3 of 9, and every pooled ratio is defined.
- The confirmatory PA1 and PA2 contrasts use t40 ds 0. On the thin side, 1 of 3 pilot seeds dropped out, so the confirmatory contrasts may be estimated on fewer than 20 seeds.
- The exploratory t100 thin-margin contrasts (PA4) may not be estimable at all.
- Per-aisle figures depend on one stall each and drop out more often. PB2 was "not testable" in the pilot.

The main-run code is as frozen. Randall can decide before the analysis phase whether the undefined seeds need a different rule; that is not needed for the runs to proceed.

## Launch

The gates passed and the projection is ≤ 14 h, so the main runs started without waiting, as instructed. They run as blocks of at most 10 h, back to back, each resuming from the cache (`analysis/aisles_main_driver.sh`, commit e4bed1c):

```
nohup caffeinate -i sh analysis/aisles_main_driver.sh > runs/aisles_main_stdout.log 2>&1 &
```

- Block 1 started 2026-11-26 21:05:21 with 7,800 chains and none cached.
- Log: `runs/aisles_run.log`; driver output: `runs/aisles_main_stdout.log`; cache: `runs/aisles_cache.jsonl`.
- Expected finish is around 10:00 on 2026-11-27: block 1 ends at its 10 h limit, and block 2 needs about 3 more hours.
