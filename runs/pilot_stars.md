# Pilot gate: displayed ratings (engine 0.20.0), Run A and Run B

Engine 0.20.0 (952af31); Run A, Run B and pilot scripts at 84b7243. Seeds 900–902; 4 workers, nice 19. Command:
`PYTHONPATH=. nice -n 19 .venv/bin/python -m analysis.pilot_stars --tests "..."`. Started 2026-11-18 10:25, gates at
13:51 (log `runs/pilot_stars/pilot_run.log`, stdout `runs/pilot_stars_stdout.log`; details
`runs/pilot_stars/pilot_gates.json`). Load average 2.8 at start and 8.9–13 for most of the pilot. Outside processes
used about three cores: `BTLEServer` at about 95% for 10 days, a Safari tab, the Claude renderer, WindowServer and
WebKit GPU.

Tests: full suite at 952af31's working tree, 1602 passed, 17 skipped, 1 failed. The failure was
`test_every_config_field_has_a_scaling_rule`: the three new keys were missing from `engine/scaling.py` FIELDS. After
adding them, `tests/test_scale.py` and `tests/test_v0200.py` were rerun in full: 222 passed (`runs/tests_0200.log`).
All 154 0.19.0 reference cells (`tests/reference/outcomes_v0190_all.json`, made at f39a99e) reproduce bit for bit with
the defaults.

**Result: G1–G5 pass.** The gate's timing rule would cut the run to no step 0.1 cells and 5 seeds per study for Run B
(6.0 h). **You chose the full design instead** (2026-11-18, after the pilot, from the timing alone; no result read
into the decision): step 0.1 cells on, Run B at 10 seeds per study, the machine otherwise idle after a restart.
Prepared, not launched.

| Gate | Result | Detail |
|---|---|---|
| G1 pipelines end to end | pass | A: 264 chains (main design + step 0.1 cells + royalty checks on 3 seeds), exit 0, 0 flags, the summary renders with the predictions verbatim (`runs/pilot_stars/A/brand_equity_stars_summary.md`). B: 636 chains (exact and stars, every study, seeds 900–902), exit 0, 0 flags, summary `runs/pilot_stars/B/stars_sensitivity_summary.md`. B's 13 endpoint definitions recomputed from the saved chains equal the published values |
| G2 defaults reproduce 0.19.0 | pass | Every brand_equity_speed chain of seeds 330 and 331 (both verifications, four levels, never / R / W_g; 112 chains) rerun at 0.20.0 with defaults equals its record in `runs/brand_equity_speed_cache.jsonl` by full-outcome digest, daily trade digests, ledgers, owners' totals and ratings: 112/112. For Run B's pairing, 4 saved exact chains per study (20) rerun at 0.20.0 equal their cache records on every field the caches keep: 20/20 (`runs/pilot_stars/stars_sensitivity_repro.json`, which the full run reads) |
| G3 timing ≤ 7 h | pass with the cut; **waived by you** | 14.2 s per chain for A at 4 workers; B 43–51 s per stars chain per worker. Projections at the pilot's load: full design 9.8 h (A 6.7, B 3.2); no step 0.1, B 10 seeds 7.6 h; no step 0.1, B 5 seeds 6.0 h (the gate's choice) |
| G4 equal display, equal price | pass | Every pilot W_g chain, days 11–60: 15,005 label-days with a white label's displayed rating equal to its owner's at step 0.02 and 9,515 at step 0.1; 0 differ in posted price |
| G5 guard | pass | A, B and the G2 rerun: stuck 0, parked 0, idle choosers 0, invalid actions 0, arm-check failures 0 |

## Choices made in implementing the spec (for confirmation before launch)

1. **Readers of the displayed rating under stars** (engine): the buyers' stall rows (ranking and the tau threshold);
   the posted premium price (`morning_prices`, which licensees and counterfeits copy); the sellers' observation
   `brand.rating` (read by the rule_genuine_rational benchmarks); and the counterfeiters' targeting and entry scoring
   (`counterfeit_target`, `enter_counterfeits`). The stored rating updates unrounded and is logged; days to 0.9 use
   it.
2. **Rounding** is half up, `floor(r/step + 0.5 + 1e-9) × step`. The step must lie in (0, 1] with 1/step an integer.
   Unrated stays 0.5.
3. **Random tie-break** is a per-buyer, per-day permutation of the stalls, `default_rng([seed, 29, day, buyer
   index])`. It replaces the stall id as the last sort key wherever a rule buyer sorts.
4. **Displayed catch-up day** (Run A, PT2 and PT3) is the first day ≥ 10 at whose end the mean displayed rating of an
   owner's W_g labels (unrated counted as 0.5) equals the owner's displayed rating. "Before" is days 10 through that
   day; "after" is the rest of days 10–60. PT2 is tested per seed as E(before) − E(after) > 0 at prior_n 400, and
   PT3 as 0.2 × E − E(after) > 0 at prior_n 10. Both at t40, 95% t over 20 seeds, unadjusted. PT1 is the per-seed
   slope of E over the calibrated days to 0.9 (1.04, 6.36, 10.38, 20.76), as in the exact run.
5. **Run B pairing.** The exact arm is the saved 0.19.0 chains (reproduced at 0.20.0, G2). The stars arm is each
   study's own config and chain functions with the three overrides appended to every config load. Every engine a
   chain builds is checked to run with the intended display and tie-break.
6. **Run B, study by study:**
   - Bust-out decomposition: the stars arm runs each stall's best candidate from the exact run (the same candidate
     in both arms), not its own best.
   - Liability: also reports the ds 1 − ds 0 contrast as a two-level analogue of the dose response.
   - Licensing: the royalty 0.10 gain is recomputed exactly from royalty 0.15 chains, as
     `analysis/licensing_checks.py` does.
   - Verdicts: exact and stars are compared on the same 10 seeds. The published estimate, which uses more seeds,
     is shown alongside for reference.
7. **Run B refuses to pair** against saved chains unless the reproduction file exists and passed. It flags the run
   if the file is missing.

## Launch (full design)

```
nohup sh runs/queue_stars.sh > runs/queue_stars.log 2>&1 &
```

- Run A: seeds 330–349, step 0.02 main design plus the step 0.1 cells; 1,692 chains, projected 6.7 h.
- Run B: 10 seeds per study, 1,000 stars chains, projected 3.2 h.
- Total projected at the pilot's load: **9.8 h**, likely less with the machine idle.
- Logs: run logs `runs/brand_equity_stars_run.log` and `runs/stars_sensitivity_run.log`; stdout
  `runs/brand_equity_stars_stdout.log` and `runs/stars_sensitivity_stdout.log`; queue log `runs/queue_stars.log`.
- Summaries: `runs/brand_equity_stars_summary.md` and `runs/stars_sensitivity_summary.md`. The reading and caveats
  are written after the results.

## Addendum before launch (2026-11-18, 19:45–20:00): macOS update

The machine was restarted and updated from macOS 26.6.2 to 27.2.1 after the pilot. Before launch:

- **Engine reproduces on the new OS.** Run B's reproduction check, rerun (4 saved exact chains per study, 20):
  20/20 (`runs/pilot_stars/os_check/stars_sensitivity_repro_macos27.json`). The first 16 brand_equity_speed chains of
  seed 330, rerun with defaults, equal their 0.19.0 records by full-outcome digest, daily trade digests, ledgers,
  totals and ratings: 16/16 (`runs/pilot_stars/os_check/g2_macos27.json`, script `g2_macos27.py`). The saved exact
  chains therefore stay valid partners for the stars chains.
- **Memory guard.** After a fresh boot macOS has no swap file, so free swap reads 0 MB and the guard (≥ 512 MB) paused
  every chain with 82% of memory free. The queue passes `--min-swap-mb 0` to both runs; the free-memory guard (≥ 15%)
  stays on. The guard only pauses new chains, so it cannot change any result.
