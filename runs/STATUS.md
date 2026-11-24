# Status: autonomous plan 2026-11-23

Plan: `runs/plan_autonomous_2026-11-23.md`, preregistered at 326abfa (2026-11-24). Operating rules, STOP conditions and record keeping as in `runs/plan_autonomous_2026-11-19.md` (D1–D3 apply). The previous plan's status is archived in `runs/STATUS_2026-11-19.md`.

| | |
|---|---|
| Stage | 2: price-war study |
| Running | price-war main run, seeds 500–519, 3,440 chains, started 2026-11-24 18:09, projected 8.3 h (about 02:30 on 11-25); log `runs/price_war_run.log`, stdout `runs/price_war_stdout.log` |
| Last gate | price-war pilot G1–G4 passed (`runs/pilot_price_war.md`) |
| Next step | C3: summary, reading and plot when the main run ends; then Stage 3 (bank v2) |

## Checkpoints

| Checkpoint | When | Result |
|---|---|---|
| C1 | Engine 1.2.0 committed, full suite passes | Passed 2026-11-24. Engine f7f49a0; full suite 1868 passed, 17 skipped, 4 failed (outdated tests, updated in the C1 commit; their files rerun 69/69) |
| C2 | Price-war study launched | 2026-11-24 18:09, commit 030e7cb, all 20 seeds (no cut) |
| C3 | Price-war summary | – |
| C4 | Bank v2 pilot and G-leak result | – |
| C5 | Bank v2 launched | – |
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
