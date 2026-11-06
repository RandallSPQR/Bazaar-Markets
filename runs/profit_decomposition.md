# Profit decomposition: adaptive (catch notices only) vs naive deceptive sellers

Part A of the decomposition / grid-refinement / entry-exit spec (2026-11-05). Analysis only; engine 0.4.0, commit `463af5d`.

## Design (prespecified)

- Source: `runs/recognition_sweep.json` (commit 463af5d). Cells: posts, patrolling and disguised full-shift inspectors x count {2, 6}.
- Adaptive sellers (`rule_deceptive_adaptive`) at recognition range r = 0 react to public catch notices (and their own reopening) only. Disguised inspectors never wear a uniform, so that cell is catch-notices-only by construction. Naive sellers (`rule_deceptive`) ignore uniforms and notices.
- The sweep stored profit per stall but not its parts, so the 12 cells x 30 seeds were re-run with the same engine; every stored value was checked first (gate below).
- Per deceptive stall: profit = revenue - unit cost - ad spend - penalties (integer cents, exact). Differences are adaptive - naive, paired over seeds 0-29, 95% t-intervals, unadjusted.
- Prediction (descriptive): more than half of the profit difference comes from lower penalties. Share = mean contribution / mean profit difference; interval: paired percentile bootstrap over seeds (10,000 resamples, `default_rng(20261105)`).

## Gate

- Re-run values match `recognition_sweep.json`: **passed** (2,160 values compared, 0 mismatches).

## Results

### Profit difference and its parts ($ per deceptive stall, adaptive - naive)

Contribution = the part's effect on profit: + revenue, - unit cost, - ad spend, - penalties.

| Cell | Naive profit | Adaptive profit | d profit | Revenue | Unit cost | Ad spend | Penalties |
|---|---:|---:|---:|---:|---:|---:|---:|
| posts2 | $9 | $20 | +$11 [+$4, +$18] | -$12 [-$20, -$3] | +$5 [+$1, +$9] | +$2 [+$1, +$3] | +$15 [+$9, +$22] |
| posts6 | -$101 | -$37 | +$65 [+$48, +$82] | -$14 [-$23, -$5] | +$6 [+$2, +$10] | +$5 [+$4, +$5] | +$68 [+$52, +$84] |
| patrolling2 | -$173 | -$111 | +$62 [+$45, +$80] | -$53 [-$74, -$33] | +$24 [+$15, +$33] | +$8 [+$8, +$9] | +$84 [+$70, +$98] |
| patrolling6 | -$413 | -$157 | +$256 [+$242, +$270] | -$23 [-$37, -$9] | +$10 [+$4, +$17] | +$3 [+$3, +$3] | +$266 [+$256, +$276] |
| disguised2 | -$198 | -$100 | +$98 [+$80, +$117] | -$51 [-$69, -$32] | +$23 [+$15, +$31] | +$7 [+$6, +$8] | +$119 [+$103, +$136] |
| disguised6 | -$402 | -$154 | +$248 [+$233, +$263] | -$25 [-$37, -$13] | +$11 [+$6, +$17] | +$4 [+$3, +$4] | +$258 [+$247, +$270] |

### Share of the profit difference from each part (point [95% bootstrap])

| Cell | Revenue | Unit cost | Ad spend | Penalties | > half from penalties? |
|---|---:|---:|---:|---:|:---:|
| posts2 | -1.06 [-4.22, -0.33] | 0.49 [0.14, 1.93] | 0.18 [0.10, 0.47] | 1.40 [1.05, 2.79] | yes |
| posts6 | -0.22 [-0.40, -0.09] | 0.09 [0.04, 0.18] | 0.07 [0.06, 0.09] | 1.05 [0.99, 1.14] | yes |
| patrolling2 | -0.85 [-1.47, -0.47] | 0.38 [0.21, 0.65] | 0.13 [0.10, 0.18] | 1.35 [1.15, 1.65] | yes |
| patrolling6 | -0.09 [-0.15, -0.04] | 0.04 [0.02, 0.07] | 0.01 [0.01, 0.01] | 1.04 [1.01, 1.07] | yes |
| disguised2 | -0.51 [-0.81, -0.32] | 0.23 [0.14, 0.36] | 0.07 [0.06, 0.09] | 1.21 [1.11, 1.36] | yes |
| disguised6 | -0.10 [-0.16, -0.06] | 0.05 [0.03, 0.07] | 0.01 [0.01, 0.02] | 1.04 [1.02, 1.07] | yes |

### Raw levels per deceptive stall (mean over seeds)

| Cell | Policy | Revenue | Unit cost | Ad spend | Penalties | Units | False impressions | Catches |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| posts2 | naive | $116 | $52 | $19 | $36 | 2.1 | 233.9 | 0.65 |
| posts2 | adaptive | $104 | $47 | $17 | $21 | 1.9 | 201.8 | 0.37 |
| posts6 | naive | $103 | $46 | $15 | $143 | 2.0 | 190.9 | 1.80 |
| posts6 | adaptive | $89 | $40 | $10 | $75 | 1.6 | 117.8 | 0.96 |
| patrolling2 | naive | $87 | $39 | $12 | $209 | 1.5 | 162.2 | 2.57 |
| patrolling2 | adaptive | $33 | $15 | $4 | $125 | 0.6 | 45.2 | 1.46 |
| patrolling6 | naive | $43 | $19 | $5 | $432 | 0.7 | 86.6 | 5.17 |
| patrolling6 | adaptive | $20 | $9 | $2 | $166 | 0.3 | 22.7 | 1.97 |
| disguised2 | naive | $91 | $41 | $12 | $236 | 1.7 | 164.2 | 2.76 |
| disguised2 | adaptive | $40 | $18 | $5 | $117 | 0.8 | 54.4 | 1.36 |
| disguised6 | naive | $40 | $18 | $6 | $418 | 0.7 | 94.0 | 5.00 |
| disguised6 | adaptive | $15 | $7 | $2 | $160 | 0.3 | 23.4 | 1.89 |

### False-claim impressions and catches per deceptive stall (adaptive - naive)

| Cell | False impressions | Catches |
|---|---:|---:|
| posts2 | -32.1 [-38.1, -26.0] | -0.28 [-0.37, -0.20] |
| posts6 | -73.1 [-80.7, -65.4] | -0.84 [-0.98, -0.71] |
| patrolling2 | -117.0 [-122.7, -111.3] | -1.11 [-1.29, -0.93] |
| patrolling6 | -63.9 [-67.2, -60.6] | -3.20 [-3.31, -3.09] |
| disguised2 | -109.8 [-115.2, -104.3] | -1.40 [-1.54, -1.26] |
| disguised6 | -70.6 [-73.4, -67.8] | -3.11 [-3.21, -3.01] |

## Verdict

**Prediction supported in all 6 cells.** Lower penalties account for more than the whole profit difference: penalty share 1.04 to 1.40, every bootstrap interval above 0.99. Revenue moves the other way in every cell (adaptive sellers sell fewer units, revenue contribution -$12 to -$53 per stall, all intervals below 0); lower unit cost and ad spend recover part of that lost revenue but not all of it.

## Reading (written after the results)

*Written after the results.*

The extra profit is avoided penalties, not better selling. Catch notices make adaptive sellers go quiet after a nearby catch, so they make 14% (posts, 2 inspectors) to 75% (disguised, 6 inspectors) fewer false-claim impressions per stall and have 0.3 to 3.2 fewer catches per stall. Fewer pitches also mean fewer sales: units per deceptive stall fall in every cell, so revenue falls, and the saved unit cost and ad spend give back only part of it. With penalties at about 5x a genuine margin, each avoided catch (one penalty plus a 40-tick closure) is worth far more than the sales lost while hiding, so the net is positive.

So "deceive less, earn more" is a penalty-avoidance effect: an adaptive seller is still deceptive, it just times its deception around enforcement. This matters for Part C: the per-stall profit edge that could pull stalls into deception is exactly the part the enforcement regime is supposed to remove.

Note on the 2-inspector posts cell: the profit difference is small (+$11) and the shares are noisy (penalty share 1.40, interval 1.05 to 2.79) because the denominator is close to 0.

## Run record

- Formatting: negative unsigned dollar amounts were printed as `$-101` by the script; corrected by hand to `-$101` (10 cells). No values changed.
- Machine load: other processes pushed the 1-minute load average to about 200 during the run; it slowed the run (9 minutes, 360 runs) but cannot change results (deterministic engine).

- Command: `.venv/bin/python -m analysis.profit_decomposition --out runs/profit_decomposition.json`
- Engine 0.4.0; commit `463af5d834ff4401481d626bd29c802a84ecad2a`; working tree clean: False
- Script sha256 `d2a671ab012cafe065133e52cf0c45400dbbde30d83c6e5b8526410ec331bdb0`
- Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit
- 360 runs on 8 workers, wall clock 539 s; load average [4.32, 4.3, 4.85] at start, [209.48, 170.78, 94.58] at end
