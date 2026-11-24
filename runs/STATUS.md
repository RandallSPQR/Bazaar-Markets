# Status: autonomous plan 2026-11-23

Plan: `runs/plan_autonomous_2026-11-23.md`, preregistered at 326abfa (2026-11-24). Operating rules, STOP conditions and record keeping as in `runs/plan_autonomous_2026-11-19.md` (D1–D3 apply). The previous plan's status is archived in `runs/STATUS_2026-11-19.md`.

| | |
|---|---|
| Stage | 1: engine 1.2.0 |
| Running | full test suite at engine 1.2.0 |
| Last gate | – |
| Next step | C1 when the full suite passes; then the price-war pilot (Stage 2) |

## Checkpoints

| Checkpoint | When | Result |
|---|---|---|
| C1 | Engine 1.2.0 committed, full suite passes | – |
| C2 | Price-war study launched | – |
| C3 | Price-war summary | – |
| C4 | Bank v2 pilot and G-leak result | – |
| C5 | Bank v2 launched | – |
| C6 | Bank v2 complete | – |
| C7 | Release prep; `runs/REPORT_2026-11b.md` | – |

## Log

- 2026-11-24: plan committed unchanged as the preregistration (326abfa) and pushed. Randall (mid-turn): also add the 1.1.0 and 1.2.0 keys to `docs/formal_model.md`, labelled "added at 1.2.0, not cross-checked".
- 2026-11-24: engine 1.2.0 written. It adds `sellers.undercut_floor_markup`, a run-level LLM spend ceiling (`agents.budget`, `engine/budget.py`) and seller option sets. `tests/test_v120.py` passes, 28/28, using a mock LLM agent with no network. Docs updated: config reference, CHANGELOG, agent interface (open point 2 closed) and formal model (new keys, labelled as not cross-checked).
