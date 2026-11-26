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
