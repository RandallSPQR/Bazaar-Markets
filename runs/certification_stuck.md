# Stuck-buyer certification of earlier runs

Run 2026-11-09 for the trapped-buyer fix (engine 0.14.0, aff9549). Observer only: nothing was rerun at
0.14.0, and no committed result changes. Script `analysis/certify_stuck.py`; raw counts
`runs/certification_stuck.json`.

## Method

For each committed run, the script checked out the commit the run was made at in a temporary git
worktree, so each run used its own engine version and its own job function. It ran the first 3 seeds the
run used across every condition. An observer patched onto `BazaarEngine.run` read the state after each
market day and changed nothing. It counted three things among buyers still in the market at close who
needed more units:

- **stuck_buyers**: within reach of the stall it had chosen (`target`), with that stall open and budget
  for one unit there. This is the 0.14.0 guard.
- **parked**: within reach of the stall it had chosen, whatever that stall's state or price. This is the
  parked-buyer bug, and it includes stuck_buyers.
- **idle_choosers**: a searching buyer (k > 1) in the "choose" phase, with an open, affordable stall of
  its category (and of its set, under choice-set demand) in reach. This is the guard's second count.

Engines before 0.10.0 have no buyer search, so they have no chosen stall and no phases. All three counts
are 0 there by construction, and the observer confirms it. The trapped-buyer bug needs choice-set demand
(0.12.0). The only certified run with choice-set demand is verification Stage A, which had no inspectors
and no closures. So every flag below is the parked-buyer bug, not the trapped one. The two "stuck" buyers
in search/counterfeit are parked buyers whose stall happened to be open and affordable when the day
closed.

Shares are per buyer-day, because each buyer gets a new task each day.

## Results

| Run | Commit | Engine | Jobs | Buyer-days | Stuck | Parked | Parked share | Jobs with parked | Worst job | Flag |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Placement sweep | 3de5fc8 | 0.2.0 | 42 | 6,300 | 0 | 0 | 0 | 0 | 0 | none |
| Visibility × adaptivity | c7cf7fe | 0.3.0 | 66 | 9,900 | 0 | 0 | 0 | 0 | 0 | none |
| Recognition sweep | 463af5d | 0.4.0 | 90 | 13,500 | 0 | 0 | 0 | 0 | 0 | none |
| Grid refinement | e514cea | 0.5.0 | 168 | 25,200 | 0 | 0 | 0 | 0 | 0 | none |
| Search / counterfeit | 14f341c | 0.10.0 | 60 | 243,900 | **2** | 30 | 0.012% | 9 | 10 / 4,500 (0.22%) | **stuck > 0** |
| Dilemma boundary | e5d7818 | 0.10.0 | 30 | 135,000 | 0 | 86 | 0.064% | 21 | 12 / 4,500 (0.27%) | parked |
| Capture A | 6b286fd | 0.11.0 | 180 | 810,000 | 0 | 0 | 0 | 0 | 0 | none |
| Capture B | b833b2f | 0.11.0 | 360 | 1,620,000 | 0 | 618 | 0.038% | 204 | 6 / 4,500 (0.13%) | parked |
| Verification A | c8c0407 | 0.13.0 | 240 | 1,080,000 | 0 | 0 | 0 | 0 | 0 | none |

The idle_choosers counts for the same runs are 29 (search/counterfeit), 46 (dilemma boundary) and 486
(capture B); every other run reads 0. Almost all of these are the same parked buyers seen from the other
count. In search/counterfeit, all 30 parked buyers are in the budget-factor 1.25 cells, and 22 of
them are in the search-depth cell where every buyer type searches 4 stalls (twice the calibrated k). In capture B, parked buyers appear
in every capture condition at about 4–5 per 4,500 buyer-days. Capture A has 0, which suggests the
mechanism is a buyer rejecting its chosen stall after a Stage B event (an inspection, or a price rise
past its remaining budget).

## Reading (written after the results)

Five of the nine runs are clean. In the three runs with flags, at most 0.06% of buyer-days, and at most
0.27% in any single job, ended with a buyer parked at a stall it had decided against. The spec's
criterion (stuck_buyers > 0) is met by one run, search/counterfeit, with 2 buyer-days out of 243,900.
How much the flagged runs would move after a rerun at 0.14.0 is not estimated here. A parked buyer loses
at most the rest of that day's purchases, and these are small shares, but they sit in the runs where
inspectors act. Per the spec, rerunning search/counterfeit, dilemma boundary and capture B is a decision
for the user.

Environment: Python 3 in `.venv`, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit. 4 workers at nice 19, run
alongside other work: the first seven runs ran in one pass (interrupted once for a pause), and capture B
and verification A ran 19:09–20:23. Wall-clock times per run are in the JSON (`wall_s`).
