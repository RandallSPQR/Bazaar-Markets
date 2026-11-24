# Price-war pilot (plan 2026-11-23, Stage 2)

Engine 1.2.0, commit 8cfaa73, `analysis/price_war.py` sha256 ae1ac5b2…4c077f (unchanged since 7b4c05c). nice 19, 4 workers, `caffeinate -i`, `--min-swap-mb 0` (D3). Log: `runs/pilot_price_war/pilot.log`.

| Gate | Rule | Result |
|---|---|---|
| G1 | The pipeline runs end to end | Pass: 516 of 516 chains on seeds 900–902, analysis flags none |
| G2 | m = 0 reproduces the 1.1.0 undercut chains bit for bit | Pass: 60 of 60 matched (liability totals on seeds 230–231, equity digests on seeds 330–331 at prior_n 0 and 400), 10 min |
| G3 | Projected main run ≤ 12 h | Pass: 8.3 h for 20 seeds (6.2 h for 15), from 17,833 chain-CPU seconds on 3 seeds; pilot wall clock 1.24 h |
| G4 | Guards 0 | Pass: stuck buyers, idle choosers, parked and fallbacks all 0 in every cell |

All gates pass, so the main run (seeds 500–519, no cut) is launched. The pilot's estimates (`price_war_pilot_gates.json`) are not read as results: three seeds, outside the main seed set.
