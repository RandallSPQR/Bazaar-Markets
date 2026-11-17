# Pilot gate: Brand Equity speed (engine 0.19.0, prior_scope "new", 60 days)

Engine 0.19.0 (8b7884b); scripts, calibration and levels at 950f745. Seeds 900–902, every arm, verification and
level (prior_n 0, 3.5, 10, 400); 4 workers, nice 19. Command: `PYTHONPATH=. .venv/bin/python -m
analysis.pilot_brand_equity_speed --tests "Full suite at engine 0.19.0 (8b7884b): 1424 passed, 17 skipped
(runs/tests_0190.log)"`. Started 2026-11-17 16:27, gates at 17:14 (log `runs/pilot_brand_equity_speed/pilot_run.log`;
details `runs/pilot_brand_equity_speed/pilot_gates.json`). Load average 4.1 at start, 6.2 at the end (other work on
the machine).

Tests: 1424 passed, 17 skipped at 8b7884b (`runs/tests_0190.log`). Every 0.18.0 reference cell (142, at 4bcfaac)
reproduces byte for byte with the new key at its default. Calibration: `runs/calibration_brand_equity_speed.md`.

**Result: G1–G5 pass, no cut.** The main run is prepared, not launched.

| Gate | Result | Detail |
|---|---|---|
| G1 pipeline end to end | pass | 180 chains of 60 days (162 cells + 18 royalty-check chains); exit 0; the summary renders with the predictions verbatim (`runs/pilot_brand_equity_speed/run/brand_equity_speed_summary.md`); 0 flags |
| G2 identities | pass | (a) Scope "all", 30 days, prior_n 50: never, R and W_g chains for seeds 300–301, both verifications, the 3 owners of each = the 0.18.0 slow15 chains (`runs/brand_equity_tier_cache.jsonl`) by full-outcome digest, ledgers and owners' totals: 28/28. (b) J identity to the cent in 216/216 owner-chains; five-part split residual ≤ 5.5e-10 cents; catch-up + after = E exactly. (c) Genuine-tier prices: 0 misses in 72 W_g chains. (d) Royalty no-decision replay (seed 900, t100, R at 0.05 and 0.25 against 0.10, current and slowest speed): 12/12 pass |
| G3 timing | pass | 14.6 s per chain on 4 workers at nice 19 (load ≈ 5–6). Full design, all four levels at t40 and t100, 20 seeds: 1,132 chains = **4.58 h**, under 6 h. No cut (the fallbacks would have been 3.45 h and 2.60 h) |
| G4 day-1 brands under "new" | pass | In 132 pilot chains at prior_n 3.5, 10 and 400, every day-1 brand's rating equals the prior_n 0 chain's (same arm, verification, seed, owner) on every day 1–10 |
| G5 guard | pass | 208 chains (pilot + G2): stuck 0, parked 0, idle choosers 0, invalid actions 0 |

## Choices made in implementing the spec (for confirmation before launch)

1. **Levels** (from the calibration, fixed before the pilot): current prior_n 0 (1.04 days to 0.9), d5 3.5 (6.36), d10
   10 (10.38), d20 400 (20.76). No prior_n near 5 days passes the spread rule; 3.5 is the closest that does. The PS1
   and PS4 x values are these calibration means, not the main run's own measurement (the run reports its own by
   cell).
2. **The catch-up window** runs from day 10 through the first day at whose end the mean rating of an owner's W_g
   white labels (unrated counted as 0.5) is ≥ 0.9; "after" is the rest of days 10–60. If the labels never get
   there, the whole span is catch-up.
3. **PS2** is tested per seed as E(catch-up) − E(after) > 0 (more than half of E in the window); **PS3** as
   0.1 × E(slowest) − E(current) > 0. Both at t40, 95% t over 20 seeds, unadjusted.
4. **PS4** fits, over the per-seed points at t40: linear, and saturating a + A(1 − exp(−(x − x0)/τ)) with τ on a
   grid; RSS, R² and AIC reported, no verdict.
5. **The never chains** are run at every speed, and the owner's gain at each speed is measured against the never
   chain at that speed.
6. **Under scope "new"** the prior also reaches names deceptive stalls reopen under (created after day 1), so a
   slow speed slows how fast those are found out (reopened names' day-20 rating 0.31 at prior_n 3.5, 0.50 at
   400; 0 at prior_n 0). This is part of what the speed levels change.

## Launch

```
nohup sh runs/queue_brand_equity_speed.sh > runs/queue_brand_equity_speed.log 2>&1 &
```

Seeds 330–349, four levels at t40 and t100, 1,132 chains, projected 4.6 h at the pilot's load (likely less overnight).
Run log `runs/brand_equity_speed_run.log`; stdout `runs/brand_equity_speed_stdout.log`; queue log
`runs/queue_brand_equity_speed.log`. Summary `runs/brand_equity_speed_summary.md` (reading and caveats to be written
after the results).
