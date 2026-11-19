# Pilot gate: checking vs reading ratings (Stage 1, engine 0.21.0)

Engine 0.21.0 and `analysis/check_vs_read.py` at 4a83784. Seeds 900–902; 4 workers, nice 19, under `caffeinate -i`.
Command: `PYTHONPATH=. nice -n 19 .venv/bin/python -m analysis.check_vs_read --pilot --min-swap-mb 0 --tests "..."`.
Started 2026-11-19 13:55, ended 15:49 (1.90 h; 773 chains: 713 for outcomes A and B and the G2 check, then 60 for the
PC6 decomposition). Log `runs/pilot_check_vs_read/check_vs_read_run.log`, stdout `runs/pilot_check_vs_read_stdout.log`,
gates `runs/pilot_check_vs_read/pilot_gates.json` (first attempt kept as `pilot_gates_attempt1.json`). Load average
2.8 at start and 5.0–7.6 during the run: outside processes used about 1.5–2.5 cores (the desktop app, two browser
tabs, and from 15:12 to 15:20 the README GIF capture at nice 19).

Tests: full suite at 4a83784, 1799 passed, 17 skipped (`runs/tests_0210.log`). All 174 0.20.0 reference cells
(`tests/reference/outcomes_v0200_all.json`) reproduce byte for byte.

**Result: G1, G2, G4 and G5 pass; G3 fails.** The projected main run is 7.18 h after both of the plan's trims (drop
outcome B's prior_n 0 level, then 15 seeds), over the 7 h limit. Under the plan this is a STOP: the main run waits for
your decision. G4 failed on the first attempt because of a bug in the comparison, fixed once (below).

| Gate | Result | Detail |
|---|---|---|
| G1 pipeline end to end | pass | 773 chains, exit 0, 0 flags; summary renders with the predictions verbatim (`runs/pilot_check_vs_read/check_vs_read_summary.md`) |
| G2 overrides at the defaults = no overrides | pass | 23 locals-market chains with no overrides (NOOV) equal the RI cell (overrides at the profile defaults) chain for chain: 23/23. J identity to the cent: 270 pairs, 0 mismatches, 0 tier-price misses |
| G3 timing ≤ 7 h | **fail** | Seconds per chain at 4 workers: A 27.3, B 55.3, D 28.4; wall-clock efficiency 1.00. Projections: full design 12.3 h (5,000 chains); no prior_n 0 9.6 h (4,300); no prior_n 0 and 15 seeds 7.2 h (3,225) |
| G4 locals that neither read nor inspect = tourists | pass (after one pipeline fix) | 150 nn chains equal the all-tourist reference chain for chain: 150/150 (A 96, B 42, D 12) |
| G5 guard | pass | stuck 0, parked 0, idle choosers 0, cells with an unexpected engine 0 |

## G4: the one pipeline fix

First attempt: 138/150. All 12 misses were D chains (the PC6 decomposition), and all differed only in the profile
label stored per buyer: the same buyers are "local" in the nn cell and "tourist" in the reference cell. The comparison
already relabelled outcome A's per-profile tally but not D's per-buyer labels. Fix (`_same` in
`analysis/check_vs_read.py`): for D chains, map the nn cell's "local" labels to "tourist", then require exact equality
of the whole record. Negative controls fail as they should: the same chain against another seed's reference, with one
buyer's quality requirement changed by 1e-4, and with one label changed to "expert". The gates were recomputed from
the cached chains (no chain re-run). That recomputation has no wall clock, so G3 comes from the timed first attempt.

## G3: options (your decision)

Projected hours at the pilot's rates, and at the smoke test's rates on a quieter machine (A 26 s, B 47 s per chain)
for comparison:

| Design | Chains | Pilot rates | Smoke rates | What is lost |
|---|---|---|---|---|
| Full (20 seeds, prior_n 0 and 400) | 5,000 | 12.3 h | 11.2 h | nothing |
| No prior_n 0, 20 seeds | 4,300 | 9.6 h | 8.9 h | PC5's prior_n 0 analogues (exploratory) |
| No prior_n 0, 15 seeds (the plan's last trim) | 3,225 | 7.2 h | 6.7 h | the above, and a quarter of the seeds for PC1–PC4 |

The 7 h limit was set for one night. Deviation D1 replaced nights with back-to-back blocks of ≤ 10 h, each usable on
its own, which the full design meets as two blocks of 10 seeds (seeds 350–359, then 360–369; about 6.1 h each at the
pilot's rates). The second block adds seeds to the same cache; the final analysis runs on all 20.

## Choices made in implementing the spec

1. **Effects, per seed:** inspection I = mean(RI, nI) − mean(Rn, nn); reading R = mean(RI, Rn) − mean(nI, nn);
   interaction X = (RI − Rn) − (nI − nn). PC1 and PC3 are one-sided t tests over seeds, 95%, unadjusted.
2. **PC2 and PC4 (size comparisons):** per seed, sgn(Ī)·I_s − sgn(R̄)·R_s (PC2: > 0 supports |R| < |I|) and its
   negative (PC4), so each is a paired test of the absolute sizes oriented by the mean signs.
3. **G4 comparison:** records equal except key, cell and timing; profile tallies summed over profiles, float values to
   1e-6 cents (summation order differs); D chains' per-buyer labels mapped local → tourist (above).
4. **D phase (PC6 decomposition):** run at detect_scale 0 after phase 1, for each watched stall's best bust-out day
   from phase 1, in every cell.
5. **Cell check:** every engine a chain builds runs with the cell's overrides and the stars display; the stall-sampling
   engine (no overrides, exact display) is the only other engine allowed.

## Launch (after your decision)

Each block is wrapped in `caffeinate -i`, at nice 19 with 4 workers:

    PYTHONPATH=. nohup caffeinate -i nice -n 19 .venv/bin/python -m analysis.check_vs_read --min-swap-mb 0 \
        --seeds 350-359 --tests "..." > runs/check_vs_read_stdout.log 2>&1

with `--no-pn0` and the seed range set by the chosen design.
