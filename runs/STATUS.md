# Status: autonomous plan 2026-11-27

Plan: `runs/plan_autonomous_2026-11-27.md`, preregistered at c0add7b (2026-11-26 12:22). Operating rules, STOP conditions and record keeping as in `runs/plan_autonomous_2026-11-19.md`, with the plan's scheduling rules: blocks ≤ 10 h back to back, `caffeinate -i`, 7 workers at normal priority, free-memory guard on. The previous plan's status is archived in `runs/STATUS_2026-11-23.md`.

Randall (2026-11-26, before dinner): push nothing; he pushes v1.2.0 and later tags when back. If the pilot projects over 14 h (G3), run the full design and log the deviation (no trims).

| | |
|---|---|
| Stage | 2: second pilot (engine 1.3.1) |
| Running | second pilot, seeds 900–902 (`runs/pilot_aisles/aisles_run.log`), started 18:59 |
| Last gate | **STOP at pilot G4**: B\|cash2\|a1\|ds1 and B\|cash2\|a0\|ds1 exit 52.1% and 51.4% of stalls before day 10 (limit 50%); G1, G2, G3 (11.95 h), G5 pass |
| Next step | pilot gates (G1, G2a–d, G3 ≤ 14 h, G4, G4b, G5) → launch if they pass |

## Checkpoints

| Checkpoint | When | Result |
|---|---|---|
| C1 | 2026-11-26 14:19 | Engine 1.3.0 (494d1bd); full suite 1,889 passed, 17 skipped, 0 failed, 1:43 h (`runs/tests_130.log`) |
| C1 (1.3.1) | 2026-11-26 18:59 | Engine 1.3.1 (3c4bd3b, script 4f66849); full suite 1,901 passed, 17 skipped, 0 failed, 1:43 h (`runs/tests_131.log`) |
| C2 | Pilot passed and launch | **not reached**: STOP at G4 (2026-11-26 16:14) |
| C3 | Run A summary | – |
| C4 | Runs B and C summaries | – |
| C5 | `runs/REPORT_2026-12a.md` | – |

## Log

- 2026-11-26 12:22: plan committed unchanged as the preregistration (c0add7b). Not pushed (Randall's instruction).
- 2026-11-26 12:35: engine 1.3.0 committed (494d1bd): `engine/categories.py` (category profiles: rescaled unit cost, fixed cost from a calibrated baseline, inspection noise and cost multiplier, review accuracy), `sellers.solvency`, `market.rent`, `buyers.gamma_by_profile`. `tests/test_v130.py` 17/17; the v1_0_0 reference digests pass with the 1.3.0 keys stripped at their defaults (14/14). One outdated test updated: `tests/test_v120.py` asserted ENGINE_VERSION == "1.2.0" (now ≥ 1.2.0). Full suite running.
- 2026-11-26: config reference, CHANGELOG and formal model updated. The 1.1.0 and 1.2.0 keys were already in the formal model, labelled "added at 1.2.0, not cross-checked"; they keep that label, and the 1.3.0 keys are added labelled "added at 1.3.0, not cross-checked".
- 2026-11-26: Stage 2 script `analysis/aisles_1_3.py` written before any pilot chain. Choices the plan leaves open are in its docstring (market overrides, calibration scenarios and rent-table grouping, estimand rules). Two are logged as deviations:
  - **D1 (naming).** The plan's `market.gamma` is the engine's existing `buyers.position_rent` (0 in the reference market). `buyers.gamma_by_profile` overrides it per profile, as the plan specifies.
  - **D2 (stall sampling).** The 3 benchmark stalls per seed come from `default_rng([seed, 17])` as in the verification run, but one per aisle (fish, electronics, designer), so the plan's per-aisle reporting and PB2 (designer vs fish) are paired by seed. Same count and stream; decided before any chain.
  - **Estimand rule (not a deviation; fixed before any chain).** A stall's share is gain ÷ its never-chain profit when that profit is > 0, else undefined (left out and counted). Seeds are paired where both sides are defined. A ratio-of-sums version is reported as a sensitivity check.
- 2026-11-26 14:19: **C1.** Full suite at 494d1bd: 1,889 passed, 17 skipped, 0 failed, 1 h 43 min. Pilot launched on seeds 900–902 (7 workers, normal priority, `caffeinate -i`).
- 2026-11-26 16:14: pilot done (1.90 h, 1,230 chains, memory pauses 0). G1, G2a, G2b, G2c, G5 pass; G3 projects 11.95 h (limit 14). **G4 fails: STOP.** Two Run B cells with start cash 2 and ds 1 exit 75 and 74 of 144 stalls before day 10 (52.1%, 51.4%; limit 72), 24–26 of 48 on every seed; early leavers are seconds and deceptive stalls, at most 1 genuine per seed. Main runs not launched. Report and options: `runs/pilot_aisles.md`. Calibration `runs/aisles_calibration.json` (no flags).
- 2026-11-26 (evening), Randall's G4 decision, made before any main-run result: report exits by type × cell × day with reasons; if seconds exits by day 30 at ds 0, cash 2 are < 25% waive G4 for the two cash-2, ds-1 cells, add G4b (genuine before day 10 ≤ 5%) and launch; otherwise STOP and propose scaling the fixed cost to each type's own baseline.
  - **D3 (instrumentation).** `exit_reason` (insolvency / other) added to the aisles job record, read from the outcome only; `analysis/aisles_g4_exits.py` reran the 90 pilot never chains (1213d2c, 8819f33). Output `runs/pilot_aisles/exits_by_type.json`.
  - **D4 (bug fix, 8819f33).** The pilot script stacked its two observers on every job, so the k-th job in a worker recorded each day k times: `stall_agg`, `harm` and `ledger_days` were k ×, and the calibration weighted seeds by k (baselines off by ≤ 1.8%, rent advantages by ≤ $6.70 a day). Outcome fields (exits, totals, busts, guards) are unaffected: all 90 reruns match the pilot outcome exactly, with observer fields exactly k ×, and in-process sequences now equal fresh processes. The pilot calibration must be remade before any launch.
  - **Result: rule 2b, STOP.** Every exit is insolvency; calibration chains (no fixed cost) have none. Seconds exiting by day 30 at ds 0, cash 2: 44/45 (α 0) and 42/45 (α 1). Seconds gross per day is about 8% of the genuine baseline the fixed cost is sized to (fish −$0.47 vs $18.03). Also reported: genuine stalls in A|thin|·|t100|ds0 exit 48 and 50 of 54 by day 30. Proposal and open points in `runs/pilot_aisles.md`; nothing changed in the engine.
- 2026-11-26 (evening), Randall approved the proposal with two additions and these deviations, all decided before any main-run result:
  - **D5 (estimand, decided by Randall).** The primary estimand becomes a ratio of means: per aisle and seed, (sum of gains) / (sum of never-chain profits) over the sampled stalls, then mean and 95% t over seeds; reported with the number of stall-seeds whose never-chain profit is ≤ 0; the per-stall mean of ratios is kept as the secondary figure. Reason (Randall): thin-margin honest profits near or below 0 make per-stall ratios unstable and bias the thin-vs-fat comparison. Note: under D2 each aisle has one sampled stall per seed, so the per-aisle figure is that stall's own ratio (undefined when its never profit is ≤ 0); the pooled figure sums the seed's three stalls.
  - **D6 (engine 1.3.1, decided by Randall; 3c4bd3b).** Each stall's fixed cost = fixed_cost_share × max(0, its own type's baseline gross), the type baselines calibrated per category and type in fresh calibration chains; start cash and credit stay on the genuine baseline. Seconds get a per-category cost target, `seconds_cost_share` = the genuine cost share (PLACEHOLDER: fish 0.70, electronics 0.77, designer 0.20; Run A's thin 0.70, fat 0.20): a seconds stall's unit cost at the cheap mean quality is that share of the seconds price at rating 1.0. Genuine and deceptive costs, bust-outs included, are unchanged. `tests/test_v131.py` 12/12 (with test_v130 and the reference digests, 43/43). Fixed cost is charged by the stall's type that morning; a bust-out keeps the stall's type (genuine), so its fixed cost does not change.
  - **D7 (gates and outcome, decided by Randall).** G2d: seconds baseline gross > 0 in every category of every calibration scenario. G4b: genuine stalls exiting before day 10 ≤ 5% in every cell. G4 still applies. Exits by type and reason in every cell are an exploratory outcome. The thin-margin genuine exits are kept, not calibrated away.
  - The first pilot's outputs moved to `runs/pilot_aisles_130/` (the chain cache is keyed without the engine version, so it must not be reused).
- 2026-11-26 18:59: **C1 (1.3.1).** Full suite at 9023acf: 1,901 passed, 17 skipped, 0 failed, 1 h 43 min (`runs/tests_131.log`). Second pilot launched: fresh calibration with the D4-fixed script, seeds 900–902, 7 workers, normal priority, `caffeinate -i`.
