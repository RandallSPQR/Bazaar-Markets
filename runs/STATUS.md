# Status: autonomous plan 2026-11-19

Plan: `runs/plan_autonomous_2026-11-19.md`, preregistered at 59e15de (2026-11-19 12:01 EST); deviations D1–D3 (scheduling and machine setup only).

| | |
|---|---|
| Stage | 1: checking vs reading ratings (engine 0.21.0) |
| Running | nothing (STOP: waiting for Randall's G3 decision) |
| Projected finish | Stage 1 main run: 6.1–12.3 h after launch, by design choice (`runs/pilot_check_vs_read.md`) |
| Last gate | Stage 1 pilot: G1, G2, G4, G5 pass; **G3 fails** (7.18 h after both trims, limit 7 h) |
| Next step | Randall chooses the Stage 1 design (full in two 10-seed blocks / no prior_n 0 / the plan's 15-seed trim); then launch, checkpoint C1 |

## Checkpoints

| Checkpoint | When | Result |
|---|---|---|
| C1 | Stage 1 engine and pilot passed; main run launched | – |
| C2 | Stage 1 summary written | – |
| C3 | Stage 2 cross-check done; tag v1.0.0 | – |
| C4 | Stage 3 engine and pilots passed; state bank night 1 launched | – |
| C5 | State bank complete | – |
| C6 | Robustness sweep complete; `runs/REPORT_2026-11.md` | – |

## Log

- 2026-11-19 12:01: plan committed unchanged as the preregistration (59e15de). Author email rewritten to the GitHub noreply address before it (old → new hashes in `docs/commit_map.tsv`).
- 2026-11-19 12:30: engine 0.21.0 built (`buyers.profile_overrides`); `tests/test_v0210.py` passes (174 reference cells at 0.20.0 byte for byte, 22 other tests); full suite running. `analysis/check_vs_read.py` written; smoke chains reproduce G2 (overrides at defaults = none) and G4 (locals that neither read nor inspect = tourists).
- 2026-11-19 12:55: **Decision needed before Stage 2 (Stage 1 continues).** The formal-model cross-check, done early from the frozen 0.21.0 code (draft `runs/formal_model_check.md`, uncommitted), found one item where the code contradicts its own spec (C1): `engine/brands.py:205` builds the name→stall map for counterfeit prices with `licensed_from is None`, which excludes a white-label licensee, the only stall bearing its fresh name. So a counterfeit of a white-label name posts its own rule's price each morning instead of the original's price, against `docs/config_reference.md` ("takes the current price of the stall bearing the original's name") and the `brands.py` docstring. Reachable only with white labels plus counterfeits made by renaming at reopening; no published run and no Stage 1 cell has that combination. Under the plan this is a STOP at Stage 2. Options: (a) fix it in 1.0.0 (keep owner-branded licensees out of the map, let a white label's own stall in) with a test that every reference cell still reproduces; (b) leave the code and document it as a known limitation. Stage 1 is unaffected and keeps running.
- 2026-11-19 13:00: Randall's decision on C1: **(a) fix it in 1.0.0.** Done in Stage 2 as its own commit, with a test that every reference cell still reproduces; Stage 1 runs on engine 0.21.0 unchanged.
- 2026-11-19 13:55: full suite at engine 0.21.0 passes (1,799 passed, 17 skipped, 1 h 25 min; `runs/tests_0210.log`). Engine 0.21.0 and `analysis/check_vs_read.py` committed; Stage 1 pilot launched.
- 2026-11-19 15:05: repo pushed to GitHub (origin/main; regular commits pushed by Claude, releases and tags by Randall). README.md added (74dd1ee). To do at Stage 2: recheck the README against 1.0.0 (status line, links to `runs/BASELINE_1_0_0.md` and `docs/agent_interface.md`, quick start on `configs/reference_1_0.yaml` once the loader reads it).
- 2026-11-19 15:52: **STOP (G3).** Stage 1 pilot (`runs/pilot_check_vs_read.md`): G1, G2, G5 pass; G4 passed after one pipeline fix (the comparison did not relabel the D chains' per-buyer profile labels; 150/150 identical after the fix, negative controls fail); G3 fails: 12.3 h full, 9.6 h without prior_n 0, 7.2 h at 15 seeds, against a 7 h limit. Load during the pilot 5–7.6 with 4 workers. Options in the pilot report; waiting for Randall.
