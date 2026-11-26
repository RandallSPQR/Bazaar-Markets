# Status: autonomous plan 2026-11-27

Plan: `runs/plan_autonomous_2026-11-27.md`, preregistered at c0add7b (2026-11-26 12:22). Operating rules, STOP conditions and record keeping as in `runs/plan_autonomous_2026-11-19.md`, with the plan's scheduling rules: blocks ≤ 10 h back to back, `caffeinate -i`, 7 workers at normal priority, free-memory guard on. The previous plan's status is archived in `runs/STATUS_2026-11-23.md`.

Randall (2026-11-26, before dinner): push nothing; he pushes v1.2.0 and later tags when back. If the pilot projects over 14 h (G3), run the full design and log the deviation (no trims).

| | |
|---|---|
| Stage | 2: aisles pilot |
| Running | pilot (seeds 900–902), `runs/pilot_aisles/stdout.log` |
| Last gate | C1 passed (full suite 1,889 passed, 17 skipped) |
| Next step | pilot gates G1–G5, then C2 (launch Runs A, B, C) |

## Checkpoints

| Checkpoint | When | Result |
|---|---|---|
| C1 | 2026-11-26 14:19 | Engine 1.3.0 (494d1bd); full suite 1,889 passed, 17 skipped, 0 failed, 1:43 h (`runs/tests_130.log`) |
| C2 | Pilot passed and launch | – |
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
