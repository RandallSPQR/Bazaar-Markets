# Pilot gate: Brand Equity at the genuine tier, with rating speed

Engine 0.18.0 (20ee303); scripts and calibration at 7e77afd. Seeds 900–902, every arm, condition and level
(prior_n 0, 2.5, 50); 4 workers, nice 19. Command: `PYTHONPATH=. .venv/bin/python -m analysis.pilot_brand_equity_tier
--tests "1261 passed, 17 skipped at 20ee303 (runs/tests_0180.log)"`. Started 2026-11-16 12:15, gates at 12:55 (log
`runs/pilot_brand_equity_tier/pilot_run.log`; details `runs/pilot_brand_equity_tier/pilot_gates.json`). Load average
4.1 at start, 7.2–8.1 at the end (other work on the machine).

Tests: 1261 passed, 17 skipped at 20ee303 (`runs/tests_0180.log`). Every 0.17.0 reference cell (126, at 1c0ed96)
reproduces byte for byte with the new keys at their defaults. Calibration: `runs/calibration_rating_speed.md`.

**Result: G1–G5 pass, with the 5-day level cut by G3 as the spec directs.** The main run is prepared, not launched.

| Gate | Result | Detail |
|---|---|---|
| G1 pipeline end to end | pass | 216 chains; the summary renders (`runs/pilot_brand_equity_tier/run/brand_equity_tier_summary.md`); 0 flags |
| G2 identities | pass | (a) Current speed never, R and W_t chains = the 0.17.0 Brand Equity pilot chains (full-outcome digest, every day-10–30 and 30-day ledger, owners' totals): 78/78. (b) J identity to the cent in 252/252 owner-chains; reputation split residual ≤ 2.3e-10 cents. (c) Royalty no-decision replay (seed 900, t100, R at 0.05 and 0.25 against 0.10; current speed both qualities, prior_n 50 contract): 18/18 pass. (d) Every W_g white label posts base × (1 + 0.4 × (start-of-day rating − 0.5)) on every day 10–30: 0 misses in 72 chains |
| G3 timing | pass after the cut | Projected on 4 workers at nice 19 from the pilot's throughput (11.0 s per chain at load ≈ 7–8): all three levels 1,998 chains = **6.10 h**, over 5.5 h. Cut the 5-day level (prior_n 2.5): 1,578 chains = **4.82 h**. Seeds stay at 30 |
| G4 seconds-type white labels above cost | pass | Contract seconds-type W_g white labels priced above unit cost on 100% of stall-days in every cell (both verification levels, all three priors). Every W_g cell, both stall types, both qualities: 100% |
| G5 guard | pass | 216 pilot chains: stuck 0, parked 0, idle choosers 0; invalid actions 0 |

## The cut

The spec: "If it's over 5.5 h, cut the 5-day level before cutting seeds." With three levels the projection is
6.10 h, so the 5-day level is removed from `analysis/brand_equity_tier.py` (`LEVELS` = current
prior_n 0, slow15 prior_n 50; `DAYS_TO_TARGET` 1.04 and 14.91 days). PR1 and PR4 are then slopes over two levels
(the prediction text, fixed before any run, still says "three levels"; it is copied verbatim). The pilot's
cached chains re-rendered with two levels: royalty check pass, 0 flags. The pilot was measured at load 7–8; at the
load of the last Brand Equity run (about 7.8 s per chain) three levels would have projected about 4.3 h, but the
rule is applied as written.

## Choices made in implementing the spec (for confirmation before launch)

1. **The prior's rule** (confirmed 2026-11-16): pseudo-reviews at 0.5 enter each day's share, share = (honest +
   0.5 w) / (rated + w), with w = prior_n at the brand's creation × memory (0.7) per day end; then the existing
   blend. Brands only (prior_n > 0 needs brands on and ratings not off).
2. **Days to 0.9** count from the licence day (day 10 = 1) to the first end-of-day rating ≥ 0.9, mean over the
   labels that reach it (all reached it in the calibration). The PR1/PR4 x values are the calibration's t40 means
   (fixed before any run), not the main run's measurement; the main run reports its own days to 0.9 by cell.
3. **The owner's gain** at a slow speed is measured against the never chain at the same speed.
4. **The 0.17.0 identity gate** compares never, R and W_t at current speed with `runs/brand_equity_cache.jsonl` by
   full-outcome digest, both ledgers and owners' totals; any mismatch is a flag, and the run exits non-zero.
5. **The royalty no-decision replay** also runs at the slowest speed (contract), as the prior changes ratings and
   so the trading the royalty is replayed against.
6. **PR4** is evaluated in contract at t40 and at t100 (the spec names no cell).
7. **The 5-day level's calibration** spread widely (1 to 9 days at t40, median 5); it is not in the main run.

## Launch

```
nohup sh runs/queue_brand_equity_tier.sh > runs/queue_brand_equity_tier.log 2>&1 &
```

Seeds 300–329, levels current (prior_n 0) and slow15 (prior_n 50). Run log `runs/brand_equity_tier_run.log`; stdout
`runs/brand_equity_tier_stdout.log`; queue log `runs/queue_brand_equity_tier.log`. Summary
`runs/brand_equity_tier_summary.md` (reading and caveats to be written after the results).
