# Pilot gate: licensing run

Spec "Part 2: licensing" (2026-11-11). Throwaway seeds 915–919. Engine 0.16.0, commit f85ffdb (uncommitted: ['?? analysis/licensing.py', '?? analysis/pilot_licensing.py', '?? runs/pilot_licensing.json', '?? runs/pilot_licensing.log', '?? runs/pilot_licensing.md', '?? runs/pilot_licensing_timing.log']); macOS-26.6.2-arm64-arm-64bit, numpy 2.5.4.

Tests: 975 passed, 17 skipped at 63c21bc (runs/tests_0160.log)

## G1: defaults reproduce engine 0.15.0 — PASS

Full 30-day chains run by engine 0.15.0 (worktree at 5b60720) and by 0.16.0 with licensing at its defaults; outcome and log body (all lines after the header) compared byte for byte.

| Chain | Identical | Log lines |
|---|---|---|
| bust30\|t100\|ds1.0\|915\|s40 | yes | 805,420 |
| never\|t100\|ds0.0\|915 | yes | 946,882 |
| never\|t100\|ds0.0\|916 | yes | 949,102 |
| never\|t100\|ds1.0\|915 | yes | 806,035 |
| never\|t100\|ds1.0\|916 | yes | 799,630 |
| never\|t40\|ds0.0\|915 | yes | 955,132 |
| never\|t40\|ds0.0\|916 | yes | 959,572 |
| never\|t40\|ds1.0\|915 | yes | 864,430 |
| never\|t40\|ds1.0\|916 | yes | 859,099 |

## G2: royalty and liability accounting on full chains — PASS

Seed 915, detect_scale 1, licence to 6 from day 10, first sampled owner of the seed.

**tourist share 1.0** (owner s40, licensees s39, s42, s43, s45, s46, s47):

| Check | Result |
|---|---|
| contract licensees: no false claim, no catch | pass |
| guard 0 (stuck, idle) in every chain | pass |
| liable: owner charged exactly the fines at licensees | pass |
| liable: owner's total falls by exactly those fines | pass |
| licence from day 10 to 30, 6 licensees | pass |
| no invalid actions | pass |
| not liable: owner charged nothing | pass |
| owner_liable changes no trade | pass |
| reviews land on the brand (cheap rating at day 30 below never's) | pass |
| royalties = units x round(0.15 x price), every day | pass |
| royalties paid = received = owner's royalties, every day | pass |

Royalties $7,026.81; catches at licensees 394; fines from them $70,920.00. Brand rating on day 30: never 1.000, cheap 0.333, contract 1.000. Owner's 30-day total: never $7,624.43, cheap $17,001.34, cheap and liable $-53,918.66, contract $13,591.96. These are pilot numbers on one seed, not results.

**tourist share 0.4, locals inspect** (owner s40, licensees s39, s42, s43, s45, s46, s47):

| Check | Result |
|---|---|
| contract licensees: no false claim, no catch | pass |
| guard 0 (stuck, idle) in every chain | pass |
| liable: owner charged exactly the fines at licensees | pass |
| liable: owner's total falls by exactly those fines | pass |
| licence from day 10 to 30, 6 licensees | pass |
| no invalid actions | pass |
| not liable: owner charged nothing | pass |
| owner_liable changes no trade | pass |
| reviews land on the brand (cheap rating at day 30 below never's) | pass |
| royalties = units x round(0.15 x price), every day | pass |
| royalties paid = received = owner's royalties, every day | pass |

Royalties $3,737.49; catches at licensees 282; fines from them $50,760.00. Brand rating on day 30: never 1.000, cheap 0.265, contract 1.000. Owner's 30-day total: never $8,991.47, cheap $10,537.74, cheap and liable $-40,222.26, contract $15,604.45. These are pilot numbers on one seed, not results.

## G3: timing and projection

- **Timing** (`python -m analysis.licensing --timing "cheap|t100|ds1.0|free" --seeds 916-917`, 4 workers, nice 19, machine otherwise idle apart from its usual load, load average about 5–6): 26 chains (2 never, 24 licensing) in 181 s, **6.98 s per chain**. Guard: 0 stuck, 0 parked, 0 idle choosers; 0 invalid actions.
- **Pipeline check** (`--pipeline-check --seeds 919-919`, scratch outdir, outputs discarded): every chain of one seed, 184 chains (4 never, 120 licensing, 60 bust-out), 1,359 s, **7.39 s per chain**; analysis, CSV, plots and summary written; 0 flags; guard 0 in every chain group. Two plot fixes and one table fix were made after it (axis range without intervals, label placement, `|` in table cells), before the script was frozen; the analysis itself did not change.
- **Projection**: 3,680 chains (80 never, 2,400 licensing, 1,200 bust-out) × 6.98–7.39 s = **7.1–7.6 h**, under 8 h. The full design runs; no trim needed.
- Trimmed options, if wanted: `--drop-b10` (licensing options from day 20 only) gives 2,480 chains, about 4.8–5.1 h; 15 seeds (`--seeds 250-264`) gives 2,760 chains, about 5.4–5.7 h. Either must be decided before launch.

## Launch command (not run)

From a clean tree at the pilot commit, frozen script `analysis/licensing.py` sha256 `117ae5f8c3b93aec7ff38ef2d36978aaafa88667f7ac75361f9cc647e721ff08`:

```bash
nohup nice -n 19 .venv/bin/python -m analysis.licensing --seeds 250-269 --tests "975 passed, 17 skipped at 63c21bc (runs/tests_0160.log)" > runs/licensing_stdout.log 2>&1 &
```

Progress log: `runs/licensing_run.log` (a line every 50 chains); cache `runs/licensing_cache.jsonl` (a rerun of the same command resumes from it). Outputs: `runs/licensing_summary.md`, `licensing.csv`, `licensing.json.gz`, `licensing_gain.svg`, `licensing_rating.svg`. Nothing billable: local CPU only.

## Notes

- Commit order: the engine commit (63c21bc) came before the Part 1 decomposition commit (f85ffdb), so G1 and G2 ran at 63c21bc with the analysis scripts uncommitted; neither touches the engine.
- Licensing gain uses the standing convention: unfloored (primary) = the best of the 4 licensing options minus never; floored also reported. PX2 compares it with the best bust-out gain (candidates day 20, 25, 28, 29, 30, no licence) in the same market (verification level and detect_scale), since bust-out chains do not depend on licensee quality or owner liability; one never chain per seed, verification level and detect_scale serves both (the licensing dials are inert without a schedule: tests/test_licensing.py).
- G1 used the engine 0.15.0 worktree .certify_tmp/v0150 (5b60720), the one that generated tests/reference/outcomes_v0150_all.json.
- Pilot numbers (seeds 915-919) are throwaway: they are not results and are not reported anywhere else.
