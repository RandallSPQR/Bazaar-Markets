# Pilot gate: enforcement intensity and limited liability

Engine 0.15.0 at 9dfd2f0 (uncommitted: ['?? analysis/liability.py', '?? analysis/pilot_liability.py', '?? runs/pilot_liability.log']); Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit. Throwaway seeds 910–914 (G1 also seed 200 of the committed Stage B). 4 workers at nice 19. Started 2026-11-10 12:58:01, ended 2026-11-10 13:28:07 (30 min); load [4.11, 3.23, 3.14] at start, [5.44, 6.01, 5.91] at end.

## G1 defaults reproduce the 0.14.0 Stage B cell (tourist share 1.0): **pass**

- Seeds 910–914: the liability script's `col|t100|ds1.0` (detect_scale 1.0 and lag 0 written out) against `analysis/verification.py` B|t100 at engine 0.14.0 (445c654, in a worktree): 80 of 80 chains identical in the 30-day totals of the 3 sampled stalls, catches per day and units per day of each sampled stall.
- Seed 200: never and the five bust-out totals of each of the 3 sampled stalls, and the gain, equal the committed `runs/verification_B.csv` rows to the cent.
- Guard over the 80 chains at 0.15.0: stuck 0, parked 0, idle choosers 0.

## G2 uncollectible fines with lag 3 and exit: **pass**

`jp|t100|ds1.0`, seed 910: 18 of 18 bust-and-exit chains have uncollectible fines. The tested stalls' fines over those chains: $0.00 charged, $11,928.00 uncollectible. The never chain has $12,912.00 outstanding at close (deceptive stalls caught on days 28–30). Guard: stuck 0, parked 0.

## G3 timing and projection

| Condition | Chains | Wall (s) | Per chain (s) | Load at start | Memory-guard pauses |
|---|---:|---:|---:|---|---:|
| `col\|t40\|ds0.1` | 32 | 237 | 7.41 | [5.35, 6.43, 5.87] | 0 |
| `jp\|t40\|ds0.1` | 38 | 289 | 7.61 | [6.16, 6.31, 5.95] | 0 |

Main run: 2,560 collectible and 3,040 judgment-proof chains (20 seeds × 8 conditions per arm). Projected wall clock 11.7 h on 4 workers (8.8 h without detect_scale 0.3). Limit 10 h: **over, so detect_scale 0.3 is dropped** (levels 0, 0.1, 1.0). The timed conditions are t40 at detect_scale 0.1 (choice made before timing: three of the four levels catch rarely, and t40 has the most buyer inspections); G1's 80 chains at detect_scale 1.0 took 6.74 s per chain.

## Notes

- The pilot was started three times. The first start failed at once (`os.nice` raised EPERM under `nohup`; both scripts now tolerate it, and the launch command sets nice 19). The second was stopped after 30 s, before any chain finished, because the 0.14.0 job (run inside the worktree) had a relative output path; its orphaned pool workers were killed before the third start. Only the third run's results are reported.
- Load averages include the pilot's own 4 workers (G3 started straight after G2); no other jobs of this project were running.
- Consequence of dropping 0.3 (prespecified rule): PL1's per-seed slope is fitted over detect_scale 0, 0.1 and 1.0, and the crossing points are interpolated between those levels.
