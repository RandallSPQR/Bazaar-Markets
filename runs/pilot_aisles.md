# Pilot: aisles study (plan 2026-11-27, Stage 2), seeds 900–902

**BLUF. STOP at G4.**
- Gates G1, G2 (all three parts), G3 and G5 pass.
- G4 fails in two Run B cells, both with start cash 2 and enforcement on (ds 1). They lose 52.1% and 51.4% of all stalls before day 10; the plan's limit is 50%.
- Per the plan ("STOP and report (the calibration is too harsh)"), the main runs were **not** launched.
- Randall decides how to proceed. The options are at the end.

Engine 1.3.0. Script `analysis/aisles_1_3.py` (sha256 811a54ee…b1ad) at commit 876829e. Workers 7, normal priority, `caffeinate -i`. Started 2026-11-26 14:20:14, done 16:14:13 (1.90 h). Memory pauses 0. Full record: `runs/pilot_aisles/aisles_run.log`; gates: `runs/pilot_aisles/aisles_pilot_gates.json`.

## Gates

| Gate | Result | Pass |
|---|---|---|
| G1 | Pipeline end to end: 60 calibration chains (20 scenarios × 3 seeds), 1,170 benchmark chains | yes |
| G2a | Defaults reproduce 1.2.0: price-war never chains A\|RI\|ds0\|lex and A\|RI\|ds1\|lex, seed 500, identical | yes |
| G2b | Cost targets hold to the cent in every cell and category | yes |
| G2c | A calibration chain reruns identically; the calibration recomputes identically | yes |
| G3 | Projected main run 11.95 h (7,800 chains; limit 14 h) | yes |
| G4 | Max share of stalls exiting before day 10: **0.521** (limit 0.5) | **no** |
| G5 | Stuck, idle, parked, fallbacks: all 0 over 5,535,000 buyer-days | yes |

The calibration raised no flags: every (category, spot class) group had data.

## G4: exits per cell (never chains, 3 seeds × 48 stalls = 144)

| Cell | Before day 10 | Share | By day 30 | Share |
|---|---|---|---|---|
| **B\|cash2\|a1\|ds1** | 75 | **0.521** | 88 | 0.611 |
| **B\|cash2\|a0\|ds1** | 74 | **0.514** | 88 | 0.611 |
| B\|cash2\|a0\|ds0 | 55 | 0.382 | 75 | 0.521 |
| A\|thin\|hard\|t100\|ds1 | 52 | 0.361 | 102 | 0.708 |
| B\|cash2\|a1\|ds0 | 52 | 0.361 | 70 | 0.486 |
| A\|thin\|hard\|t40\|ds1 | 46 | 0.319 | 90 | 0.625 |
| A\|thin\|easy\|t100\|ds1 | 44 | 0.306 | 105 | 0.729 |
| A\|thin\|easy\|t40\|ds1 | 44 | 0.306 | 90 | 0.625 |
| C\|a1\|t100 | 43 | 0.299 | 77 | 0.535 |
| B\|cash20\|a0\|ds1 | 2 | 0.014 | 64 | 0.444 |
| B\|cash20\|a1\|ds1 | 2 | 0.014 | 65 | 0.451 |

The other 19 cells are under 0.27 before day 10; every cell is in the gates file.

**Per seed, the two failing cells** (exits before day 10, of 48):
- B|cash2|a1|ds1: 26, 24, 25 (seeds 900, 901, 902)
- B|cash2|a0|ds1: 26, 24, 24

So the breach holds on every seed, not just one. It is a small breach: 75 and 74 exits against a limit of 72.

**Who exits.** In the failing cells the early leavers are almost all seconds (10–12 per seed) and deceptive stalls (12–15 per seed). At most 1 genuine stall per seed leaves early.

The same cells with start cash 20 lose only 2 stalls before day 10. That points to insolvency, not enforcement closures, as the cause of the early exits. The pilot records do not tag each exit's cause, so this rests on the cash 2 against cash 20 contrast.

Reading (written after the results): start cash of 2 days' baseline gross is enough to wipe out about half of the non-genuine stalls in the first week once fines are charged against cash. The genuine stalls the study measures mostly survive (1 of 48 per seed at most). The rule as written counts all stalls, though, and the plan says to stop.

## Options for Randall (none taken)

1. **Run as preregistered anyway** and log G4 as a deviation. Every other gate passes and the main run projects 11.95 h.
2. **Soften the low-cash level**, for example start cash 3 or 5 days instead of 2, and rerun the Run B pilot cells. This changes a design level, so it is a deviation made after seeing the pilot.
3. **Count only genuine stalls in G4**, since they are the stalls the estimand is about; that share is ≤ 2%. This reinterprets the gate after seeing the result, which is also a deviation.

Nothing has been pushed. Nothing is running.

## G4 decision (Randall, 2026-11-26, before any main-run result): result

Randall's rule:
1. Report exits by type × cell × day from the pilot chains.
2. If seconds stalls exiting by day 30 in the ds 0, start-cash-2 cells are under 25% of seconds stalls, waive G4 for the two cash-2, ds-1 cells, add G4b and launch.
3. Otherwise STOP and propose scaling the fixed cost to each type's own baseline.

**Outcome: 2b, STOP.** In B|cash2|a0|ds0, 44 of 45 seconds stalls exit by day 30 (97.8%); in B|cash2|a1|ds0, 42 of 45 (93.3%). The main runs are not launched.

### How the exits were measured (D3, D4)

- **D3 (instrumentation).** The pilot records had no exit reason. `analysis/aisles_1_3.py` now adds `exit_reason` (insolvency / other), read from the outcome only: a stall is "insolvency" if it appears in some day's `solvency.exits`. `analysis/aisles_g4_exits.py` reran the 90 pilot never chains (every cell × seeds 900–902; the bust chains are not needed for exits) in 498 s. Output: `runs/pilot_aisles/exits_by_type.json`.
- **D4 (bug in the pilot script, found by the digest check).** The script installed its two observers (the parked-buyer counter and the day ledger) on every job. Each checks only its own flag on the outermost `BazaarEngine.run`, so every job stacked two more layers, and the k-th job in a worker recorded each day k times.
  - **Not affected:** anything read from the engine outcome (exits, totals, busts, guards, spots); the engine itself; and G1, G2a, G2b, G4 and G5. G5's parked count is 0 either way, since 0 × k = 0.
  - **Affected:**
    - `stall_agg`, `harm` and `ledger_days` were multiplied by k (1 to 66 per chain);
    - the calibration weighted seeds by k: baselines are off by up to 1.8%, and rent advantages by up to $6.70 per day;
    - G3 timing is slightly affected; the never chains reran at about the same speed, so the 11.95 h projection roughly stands.
  - **Fix (8819f33).** Install the observers once per process. Checks:
    - all 90 rerun chains have the same engine outcome as the pilot, with the cached observer fields exactly k × the rerun's;
    - three jobs run in sequence in one process equal the same jobs each run in a fresh process.
  - The calibration file from the pilot is mis-weighted and must be remade. Any relaunch needs a fresh pilot.
- **Reading the earlier "other" tags.** The engine rebuilds itself each day, so `solvency.exits` lists that day's exits only. The first version of the field read the last day only; it was fixed before this table.

### Exits by type, before day 10 / by day 30 (all insolvency)

Every exit in every cell is an insolvency exit: the rule-based sellers never choose to exit. The calibration chains (no fixed cost, solvency off, α 0) have **no exits at all**. Per cell: 54 genuine, 45 seconds and 45 deceptive stalls (3 seeds).

| Cell | Genuine | Seconds | Deceptive |
|---|---|---|---|
| A\|fat\|easy\|t100\|ds0 | 0 / 0 | 0 / 16 | 0 / 0 |
| A\|fat\|easy\|t100\|ds1 | 0 / 0 | 0 / 22 | 0 / 39 |
| A\|fat\|easy\|t40\|ds0 | 0 / 0 | 0 / 30 | 0 / 0 |
| A\|fat\|easy\|t40\|ds1 | 0 / 0 | 0 / 31 | 0 / 43 |
| A\|fat\|hard\|t100\|ds0 | 0 / 0 | 0 / 17 | 0 / 0 |
| A\|fat\|hard\|t100\|ds1 | 0 / 0 | 0 / 21 | 0 / 41 |
| A\|fat\|hard\|t40\|ds0 | 0 / 0 | 0 / 34 | 0 / 0 |
| A\|fat\|hard\|t40\|ds1 | 0 / 0 | 0 / 32 | 0 / 42 |
| A\|thin\|easy\|t100\|ds0 | 0 / **48** | 6 / 45 | 0 / 0 |
| A\|thin\|easy\|t100\|ds1 | 0 / 15 | 0 / 45 | 44 / 45 |
| A\|thin\|easy\|t40\|ds0 | 0 / 0 | 0 / 45 | 0 / 39 |
| A\|thin\|easy\|t40\|ds1 | 0 / 0 | 0 / 45 | 44 / 45 |
| A\|thin\|hard\|t100\|ds0 | 0 / **50** | 38 / 45 | 0 / 1 |
| A\|thin\|hard\|t100\|ds1 | 0 / 12 | 8 / 45 | 44 / 45 |
| A\|thin\|hard\|t40\|ds0 | 0 / 3 | 2 / 45 | 0 / 0 |
| A\|thin\|hard\|t40\|ds1 | 0 / 0 | 1 / 45 | 45 / 45 |
| B\|cash20\|a0\|ds0 | 0 / 0 | 0 / 30 | 0 / 13 |
| B\|cash20\|a0\|ds1 | 0 / 0 | 0 / 30 | 2 / 34 |
| B\|cash20\|a1\|ds0 | 0 / 0 | 0 / 30 | 0 / 7 |
| B\|cash20\|a1\|ds1 | 0 / 0 | 0 / 30 | 2 / 35 |
| **B\|cash2\|a0\|ds0** | 2 / 7 | 36 / **44** | 17 / 24 |
| B\|cash2\|a0\|ds1 | 0 / 1 | 34 / 44 | 40 / 43 |
| **B\|cash2\|a1\|ds0** | 2 / 6 | 34 / **42** | 16 / 22 |
| B\|cash2\|a1\|ds1 | 1 / 1 | 33 / 42 | 41 / 45 |
| C\|a0\|t40 | 0 / 0 | 0 / 42 | 26 / 40 |
| C\|a0\|t100 | 0 / 14 | 0 / 41 | 27 / 39 |
| C\|a0.5\|t40 | 0 / 0 | 0 / 37 | 26 / 43 |
| C\|a0.5\|t100 | 0 / 14 | 7 / 32 | 30 / 38 |
| C\|a1\|t40 | 0 / 1 | 2 / 34 | 28 / 43 |
| C\|a1\|t100 | 0 / 10 | 8 / 25 | 35 / 42 |

### Why seconds go bust

The fixed cost is fixed_cost_share × the category's baseline, and that baseline is the mean **genuine** stall-day gross. Seconds earn a small fraction of that. Gross per stall-day in the calibration chains for Run B at ds 0 (no fixed cost; corrected for D4):

| Category | Genuine | Seconds | Deceptive | Fixed cost in Run B | Start cash at 2 days |
|---|---|---|---|---|---|
| fish | $18.03 | −$0.47 | $4.72 | $16.22 (share 0.90) | $36.05 |
| electronics | $77.31 | $4.16 | $47.07 | $65.71 (0.85) | $154.61 |
| designer | $455.49 | $37.29 | $513.26 | $227.75 (0.50) | $910.98 |

A seconds stall therefore loses roughly 0.5–0.9 of a genuine day's gross every day. With 2 days of cash and 3 days of credit it is gone by about day 5 to 6, which is when the cash-2 exits happen. With 20 days of cash, 30 of 45 seconds stalls are still gone by day 30.

### A second finding the rule does not cover: genuine stalls in thin-margin t100 cells

The proposed G4b (genuine stalls exiting before day 10 ≤ 5% in every cell) would pass: the maximum is 2 of 54 (3.7%). By day 30, however, A|thin|easy|t100|ds0 loses 48 of 54 genuine stalls and A|thin|hard|t100|ds0 loses 50 of 54, all to insolvency. These t100 cells feed only exploratory outcomes (PA4). The confirmatory PA1–PA3 use t40, where genuine exits by day 30 are 0–3 of 54.

Reading (written after the results): at a thin margin with all-tourist buyers, the average genuine stall's gross barely covers a fixed cost sized to that same average. The below-average half runs down its cash and leaves within the 30-day window.

### Proposal (not implemented; Randall decides)

Scale the fixed cost to each stall type's own baseline gross profit: fixed cost = fixed_cost_share × the mean stall-day gross of that (category, type), measured in the same calibration chains. Points to settle:

1. **Negative baselines.** Seconds fish gross −$0.47 a day with no fixed cost, so their scaled fixed cost needs a floor of 0. They then lose $0.47 a day and still run down their cash slowly.
2. **Which baseline cash and credit use.** If start cash and the credit limit also move to the type baseline, seconds fish start with negative cash and exit on day 1. The suggestion is to keep cash and credit on the category's genuine baseline and scale only the fixed cost.
3. **Engine change.** Fixed cost by stall type is not in engine 1.3.0. It needs a key (for example `categories.profiles.<cat>.fixed_cost_by_type` or a type-scaled baseline), tests, the full suite (a new C1), a fresh calibration (also needed for D4), and a fresh pilot.
4. **The genuine exits at thin margin and t100** (above) are untouched by this change. They may need their own decision (keep them as part of the finding, or lower the thin-margin fixed-cost share).
