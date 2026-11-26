# Status: autonomous plan 2026-11-23

Plan: `runs/plan_autonomous_2026-11-23.md`, preregistered at 326abfa (2026-11-24). Operating rules, STOP conditions and record keeping as in `runs/plan_autonomous_2026-11-19.md` (D1–D3 apply). The previous plan's status is archived in `runs/STATUS_2026-11-19.md`.

| | |
|---|---|
| Stage | 3: bank v2 |
| Running | bank v2 block 2c (the last 105 chains of block 2), 7 workers, launched 2026-11-26 09:34; stdout `runs/state_bank_v2_bank_stdout.log` |
| Last gate | C4: bank v2 pilot G1–G5 and G-leak passed (`runs/pilot_state_bank_v2.md`) |
| Next step | build and summary (C6) |

## Checkpoints

| Checkpoint | When | Result |
|---|---|---|
| C1 | Engine 1.2.0 committed, full suite passes | Passed 2026-11-24. Engine f7f49a0; full suite 1868 passed, 17 skipped, 4 failed (outdated tests, updated in the C1 commit; their files rerun 69/69) |
| C2 | Price-war study launched | 2026-11-24 18:09, commit 030e7cb, all 20 seeds (no cut) |
| C3 | Price-war summary | 2026-11-25 02:12. PW1–PW4 supported; `runs/price_war_summary.md` (a2bee13); deviation D4 (PW5 sign fix) |
| C4 | Bank v2 pilot and G-leak result | 2026-11-25 11:26. All gates pass; G-leak best single feature `units_7d` 77.8% (limit 80%); N 300, K 20, 29.6 h projected |
| C5 | Bank v2 launched | 2026-11-25 11:28: blocks 1 and 2a; 2b and 3 follow, each ≤ 10 h |
| C6 | Bank v2 complete | – |
| C7 | Release prep; `runs/REPORT_2026-11b.md` | – |

## Log

- 2026-11-24: plan committed unchanged as the preregistration (326abfa) and pushed. Randall (mid-turn): also add the 1.1.0 and 1.2.0 keys to `docs/formal_model.md`, labelled "added at 1.2.0, not cross-checked".
- 2026-11-24: engine 1.2.0 written. It adds `sellers.undercut_floor_markup`, a run-level LLM spend ceiling (`agents.budget`, `engine/budget.py`) and seller option sets. `tests/test_v120.py` passes, 28/28, using a mock LLM agent with no network. Docs updated: config reference, CHANGELOG, agent interface (open point 2 closed) and formal model (new keys, labelled as not cross-checked).
- 2026-11-24: full suite at f7f49a0 (`runs/tests_120.log`, 1 h 45 min): 1868 passed, 17 skipped, 4 failed. The four failures were tests that asserted 1.1.0 behaviour that 1.2.0 changes by design, with obvious, local fixes in the tests only (no engine change):
  - `tests/test_reference_1_0.py` (2 tests): the reference comparison strips keys added after 1.0.0 at their defaults; it now also strips the 1.2.0 keys (`sellers.undercut_floor_markup` 0, `agents.budget` at its defaults), and any other value still fails.
  - `tests/test_invariants.py` (2 tests): the LLM stub used to skip its calls and fall back silently. At 1.2.0 a request goes through the spend tracker, so with the default budget it is refused, counted as a fallback, and the run stops at the next decision, marked INVALID: budget. The tests now check that.
  The three affected files were rerun: 69 passed. Reference cells (rule agents) are unaffected. C1 passed.
- 2026-11-24: price-war G2 passed, 60 of 60 undercut chains at m = 0 bit for bit with the 1.1.0 sweep. Pilot on seeds 900–902: G1 516/516 chains, G3 projected 8.3 h for 20 seeds (limit 12 h), G4 guards 0. Record `runs/pilot_price_war.md` (030e7cb).
- 2026-11-24 18:09: C2. Main run launched, seeds 500–519, no cut, via `runs/price_war_queue.sh` (nohup, caffeinate, nice 19, 4 workers).
- 2026-11-25 02:12: price-war main run done, 3,440 chains in 8.05 h, guards 0, flags 0. PW1 +$227 [+$175, +$280], PW2 slope −$775 per unit of m, PW3 slope +$11,826 per unit of m, PW4 −$327 [−$406, −$249]: all supported.
- 2026-11-25: **D4.** The PW5 paired differences in `analysis/price_war.py` had their arguments reversed (`paired_diff(a, b)` returns b − a), so the as-run tables showed RI − U0 under a U0 − RI label. It is an exploratory reporting bug with an obvious, local fix and no STOP condition applies. The as-run outputs were committed first (cdc8119, kept in `runs/price_war_as_run/`), then the order was fixed (db0abba) and the tables regenerated from the cache with no new chains. Checked: PW1–PW4 and every other table identical; all 20 PW5 differences flip sign exactly. `analysis/state_bank_v2.py` does not use `paired_diff`.
- 2026-11-25: C3. Reading and caveats written (a2bee13).
- 2026-11-25 05:19: bank v2 design (24 markets, attempt 1) and enumeration done: 2,400 chains, 172,800 states, 3.07 h. Markets without counterfeits have no states below 1.0, so 36 strata are non-empty.
- 2026-11-25 11:26: C4. Pilot of 36 states at K 30 (6.11 h): G1–G5 pass, G-leak passes (best `units_7d` 77.8%). K 20 chosen; N 300 projected 29.6 h with 139.8 expected close calls. The prespecified allocation is concentrated: 176 states in one stratum, 56 in another, 2 in each of the other 34. Flagged for Randall, not changed (frozen design).
- 2026-11-25: **D5.** The script's blocks are whole markets, and the concentrated market projects 19.7 h, over the plan's 10 h block limit (the script's G3 checked only the 36 h total). Block 2 runs as two launches of at most 10 h, resuming from the chain cache. No change to the design, states, K or analysis.
- 2026-11-25 11:28: C5. Bank launched with `runs/state_bank_v2_block.sh`: block 1, then block 2a with a 10 h limit.
- 2026-11-25: Randall: "keep going with the allocation as is." The concentrated N 300 allocation stands. He will free the full CPU after finishing two other projects; later blocks may then use more workers. Chains are seeded per job, so the worker count changes wall clock only, not results.
- 2026-11-25 15:02: **D6.** Randall freed the CPU and asked for 7 workers. Block 1 had finished at 11:36 (220 chains). Block 2a was stopped by hand after 100 of block 2's 560 chains (3.4 h); the 4 chains in flight were lost and are rerun, and the cache's last line parses (320 lines). `runs/state_bank_v2_block.sh` takes an optional fourth argument, the worker count (default 4). Block 2b and then block 3 run on 7 workers, each with the 10 h limit. Chains are seeded per job, so this changes wall clock only: no change to the design, states, K, seeds or analysis. Each launch's run record states its worker count.
- 2026-11-26 01:03: block 2b reached its 10 h limit after 355 more chains (675 cached in all). Block 3 then ran its 332 chains in 8.49 h, ending 09:32; the cache's last line parses (1,007 lines). On 7 workers a chain took about 101 s of wall clock, against 116 s on 4: the three extra workers run on efficiency cores.
- 2026-11-26 09:34: block 2c launched for block 2's last 105 chains (7 workers, 10 h limit).
