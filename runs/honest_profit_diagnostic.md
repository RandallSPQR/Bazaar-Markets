# Diagnostic: why do inspectors cut honest-stall profit?

Spec "Diagnostic: why do inspectors cut honest-stall profit? (no engine change unless a bug is found)", 2026-11-08/09. No engine change was made. Script: `analysis/honest_profit_diagnostic.py`. It wraps `BazaarEngine.run`, `search_decide`, `decide` and `step` to record every buyer decision, every set-member stall a buyer came within reach of (open or closed), and the sampled stalls' seller actions and accounting. Engine 0.13.0 at commit 2cc1342. Seed 200, sampled stalls s42, s41 and s01, the never-bust-out chain.

## Finding: an engine bug (stop rule applies; not fixed)

**A choice-set buyer that walks back to the stall it chose can be barred from buying for the rest of the day.**

`BazaarEngine.search_decide` (`engine/bazaar.py:529–559`) sets
`phase = "choose" if (len(p.seen) >= p.search_k or route_end) else "browse"`, where `route_end = p.step >= len(p.route) - 1`. `p.seen` records only stalls that were open when in reach (lines 538–542). The bug fires like this:

1. A buyer's consideration set (m = 3) holds a stall that is closed when the buyer walks past. In this run that is a deceptive stall closed after a catch.
2. The closed stall never enters `p.seen`, so the buyer has seen 2 stalls and stays in "browse" until the end of its aisle.
3. At the aisle end `route_end` is true, the phase is "choose", and the buyer chooses the best stall it saw (`p.target`) and walks back towards it.
4. One step back from the aisle end, `route_end` is false again and `len(p.seen)` is still 2, so the phase reverts to "browse".
5. At the chosen stall the buyer may not buy: the engine rejects `buy` in "browse" (lines 586–587), and `rule_buyer.act_search` answers `move_on` in "browse". Movement keeps it at its target (`goal == p.step`).
6. It decides `move_on` about 200 times and is still standing at an open stall it wants to buy from when the day closes.

The failure is silent. No invalid actions are logged, because `move_on` is valid.

### Minimal reproduction (no inspectors, no catches)

`.venv/bin/python -m analysis.honest_profit_diagnostic repro`: one day, tourists only, choice-set demand (m 3), seed 200, Stage A settings. One deceptive stall (s22, in 17 buyers' sets) is closed by hand for the whole day (`closed_until = ticks`).

| | Purchases | Buyers stuck at an open chosen stall | of them with s22 in their set | Invalid buyer actions |
|---|---|---|---|---|
| Control (s22 open) | 148 | 0 | 0 | 0 |
| s22 closed all day | 131 | 16 | 16 | 0 |

Example: buyer p587233 has set {s17, s19, s22}.
- It saw s17 and s19; s22 was closed.
- At tick 26, at the end of its aisle, it chose s19.
- At close it stands at step 8 of 19, in reach of s19, which is open. Its seen count is 2 against search_k 3.

### Who it affects

- **Any choice-set run where set stalls can be closed.** That means any run with catches, so Stage B of the verification run, and the choice-set pilot conditions with inspectors (`runs/pilot_choice_set.md` P2/P3; not rechecked).
- **Not Stage A of the verification run.** With no inspectors nothing closes. Seed 200 had 0 stuck buyers on every day of both Stage A conditions. PV1–PV3 are not affected.
- **Walk-mode search runs (capture, dilemma boundary, search/counterfeit).** These are possible in principle (the same phase rule) but not observed: a 3-day spot check on seed 200 of capture Stage B, dilemma boundary (honest, 2 inspectors) and search/counterfeit (k 3) found 0 stuck buyers. There are 8 stalls per category in reach, so a buyer reaches k open stalls before its aisle ends.

## How much of the drop it explains

All 20 seeds (200–219), never-bust-out chains of Stage B, 30 days, from `analysis.honest_profit_diagnostic summary`. The per-stall totals reproduce `runs/verification_B.json.gz` exactly (0 mismatches in 180 stall-seeds).

"Bug loss" is a first-order estimate. Every stuck buyer whose chosen stall is a sampled stall would have bought its remaining units there, at that stall's price minus unit cost. The rule had chosen that stall and it was open and in reach, so this is what a fixed engine would do at that moment. The estimate ignores knock-on effects, such as the reviews those sales would have earned. Per sampled stall over 30 days; mean [95% t-interval] across seeds.

| Tourist share (locals inspect) | Honest profit, no inspectors ($) | Honest profit, 2 inspectors ($) | Drop ($) | Bug loss ($) | Bug loss ÷ drop | Stuck buyers per day (of 150) | Purchases per day, 2 inspectors |
|---|---|---|---|---|---|---|---|
| 0.4 | 4,651.8 [3,527.8, 5,775.8] | 3,255.1 [2,454.2, 4,056.0] | 1,396.7 [1,048.2, 1,745.2] | 1,721.1 [1,316.4, 2,125.7] | 1.23 | 31.0 [30.0, 32.0] | 94.6 |
| 0.7 | 3,227.4 [2,393.2, 4,061.6] | 2,445.9 [1,798.2, 3,093.5] | 781.5 [578.6, 984.4] | 1,976.4 [1,517.2, 2,435.6] | 2.53 | 37.2 [36.3, 38.2] | 93.3 |
| 1.0 (tourists only) | 1,817.9 [1,296.1, 2,339.7] | 1,901.9 [1,360.5, 2,443.3] | −84.0 [−123.4, −44.6] | 2,378.1 [1,842.5, 2,913.6] | – | 46.6 [46.0, 47.3] | 86.6 |

**The bug explains all of the drop, and more.** At tourist share 0.4 the estimated bug loss, $1,721 per stall, exceeds the observed drop of $1,397. The rest of what enforcement does is a net gain for honest stalls, of the order of +$300 (+$1,200 at 0.7). That fits the expectation that enforcement helps honest sellers: closures of caught deceptive stalls send their buyers to honest ones. Across all stuck buyers, 83% of the stalls they were stuck at are genuine (15,434 of 18,607 buyer-days at tourist share 0.4).

**Why the tourist-only market shows no drop.** The bug is worst there (47 stuck buyers a day), but closures are also most valuable there. In Stage A deceptive stalls take 65% of sales with tourists only, against 29% at tourist share 0.4, so closing them redirects the most demand to honest stalls. The two effects roughly cancel: a $2,378 bug loss against an observed +$84. The unchanged profit hides two large effects of opposite sign, not an absence of effect.

The share is a first-order bound, not a counterfactual run. Measuring it exactly needs the fix and a rerun.

## Candidate mechanisms checked

- **a. Inspectors in sellers' passerby lists. Holds, small, a modelling effect rather than a bug.** Inspectors count towards the crowd of 3 that triggers a yell, and each gets whispered to once per stall per day.
  - Seed 200, days 1–5, the $120 sampled stalls: yells rose from 20 to 28 a day per stall, and ad spend from $28.8 to $31.5 a day.
  - That is about $80 over 30 days, under 6% of the drop. It is an upper bound for this mechanism, because stuck buyers standing at a stall also make crowds.
  - Whispers to inspectors were 2 of about 50 a day per stall.
  - Inspectors take no buyer slots: `max_actions_per_stop` and asks are per buyer.
- **b. Closures remove options. Holds only through the bug.**
  - Buyers whose every set stall in reach was closed: 0–2 a day.
  - Buyers whose chosen stall closed before they got back: 0–16 a day. They choose again, as designed.
  - The large effect is the bug. A closed set member stops the buyer from reaching the "choose" phase except at the aisle end, and then traps it.
  - Without the bug, closures would send buyers to their other set members. That is the positive effect inferred above.
- **c. More inspection by locals and experts. Does not hold.**
  - Inspections per local fell slightly on day 1 (2.04 against 2.14) and were higher on days 2–5 (1.1–1.8 against 0.95–1.2). Re-inspection of freshly renamed reopened stalls is the likely reason.
  - Inspection spending is 2–6% of a buyer's budget in both stages.
  - Buyers who end without a candidate partly because of budget: 0–2 a day without inspectors, 4–7 a day with them. That is small next to 11–39 stuck buyers a day.
- **d. Delivery and detection order. Holds, but small, and not a bug.** Catches are made in delivery (step 3), before buyer decisions (step 4) in the same tick. A buyer walking to a stall caught that tick finds it closed and chooses again: 0–16 buyers a day at seed 200 (both stage B conditions), against 11–52 stuck. The trap itself is a phase rule (step 4), not an ordering effect.

## Consequences for the verification run (not acted on)

- **Stage A (PV1–PV3): unaffected.** Nothing closes, so no buyer is trapped.
- **Stage B and PV4: affected.** About 21% of buyers at tourist share 0.4 (31 of 150 a day), and 31% at 1.0, end each day trapped. Mostly at genuine stalls. The bust-out chains were not instrumented, but they share the mechanism.
  - The never-bust-out baseline is biased.
  - The bust-out chains are affected too, so the size of PV4 (−$942) cannot be cited until Stage B is rerun on a fixed engine.
  - The sign of PV4 is plausibly robust: a single day of busting out on day 30 costs $377–439 in penalties and closure, and the bug does not create penalties. That is a judgement, not a measurement.
- **The B − A gap by verification level** and the "unexplained" note in `runs/verification_summary.md` are superseded by this finding.
- **The choice-set pilot** (`runs/pilot_choice_set.md`) P2/P3 had inspectors and may be affected. Not rechecked.

## A fix to decide on (not made)

**Recommended.** Treat "at or walking back from the aisle end" as part of the "choose" phase. Two ways to do it:
- `route_end` becomes "has reached the end of its route at least once" (a sticky flag on the person), or
- a buyer with a target is always in "choose".

**Alternative.** Count a set member found closed as seen, as `p.skipped` already does for a chosen stall found closed.

Either is an engine change: version bump, tests (including this reproduction as a regression test), and new reference cells. Defaults and walk mode are unaffected unless a search buyer reaches its aisle end with fewer than k open stalls seen. Then Stage B would need rerunning; Stage A would not.

## Day by day, seed 200, tourist share 0.4, locals inspect, days 1–5

"Reached (open)" counts buyers with the stall in their set who came within reach of it (of whom, while it was open). "Left without buying" covers those who reached it open but did not buy there; "bought elsewhere (task complete)" means the buyer finished its task at another stall. "Stuck at this stall" means the buyer chose it and was barred from buying there by the bug. Inspections are those made at the stall by buyers.

**A|t40|l1** (no inspectors)

| Day | Stall | Units | In set | Reached (open) | Left without buying: why | Inspections | Profit ($) | Ad spend ($) |
|---|---|---|---|---|---|---|---|---|
| 1 | s42 | 6 | 5 | 5 (5) | 2: bought elsewhere (task complete) 2 | 5 | 169.74 | 28.32 |
| 1 | s41 | 14 | 11 | 11 (11) | 2: bought elsewhere (task complete) 2 | 8 | 363.46 | 27.84 |
| 1 | s01 | 14 | 11 | 11 (11) | 2: bought elsewhere (task complete) 2 | 7 | 36.27 | 1.81 |
| 2 | s42 | 4 | 10 | 10 (10) | 6: bought elsewhere (task complete) 6 | 5 | 198.52 | 29.52 |
| 2 | s41 | 7 | 10 | 10 (10) | 6: bought elsewhere (task complete) 6 | 4 | 334.37 | 29.28 |
| 2 | s01 | 6 | 9 | 9 (9) | 4: bought elsewhere (task complete) 4 | 2 | 24.11 | 1.81 |
| 3 | s42 | 14 | 18 | 18 (18) | 9: bought elsewhere (task complete) 9 | 12 | 766.46 | 31.68 |
| 3 | s41 | 5 | 8 | 8 (8) | 4: bought elsewhere (task complete) 4 | 5 | 228.31 | 31.44 |
| 3 | s01 | 10 | 10 | 10 (10) | 4: bought elsewhere (task complete) 4 | 6 | 41.36 | 1.84 |
| 4 | s42 | 6 | 13 | 13 (13) | 9: bought elsewhere (task complete) 9 | 3 | 313.74 | 28.32 |
| 4 | s41 | 5 | 7 | 7 (7) | 3: bought elsewhere (task complete) 3 | 3 | 231.43 | 28.32 |
| 4 | s01 | 4 | 5 | 5 (5) | 3: bought elsewhere (task complete) 3 | 2 | 15.59 | 1.69 |
| 5 | s42 | 4 | 9 | 9 (9) | 6: bought elsewhere (task complete) 5; budget 1 | 5 | 201.16 | 26.88 |
| 5 | s41 | 5 | 10 | 10 (10) | 6: bought elsewhere (task complete) 5; budget 1 | 6 | 233.11 | 26.64 |
| 5 | s01 | 10 | 13 | 13 (13) | 6: bought elsewhere (task complete) 6 | 8 | 41.16 | 2.04 |

**B|t40|l1** (2 patrolling inspectors)

| Day | Stall | Units | In set | Reached (open) | Left without buying: why | Inspections | Profit ($) | Ad spend ($) |
|---|---|---|---|---|---|---|---|---|
| 1 | s42 | 6 | 5 | 5 (5) | 2: bought elsewhere (task complete) 2 | 5 | 167.34 | 30.72 |
| 1 | s41 | 12 | 11 | 11 (11) | 3: bought elsewhere (task complete) 2; stuck at this stall (chose it, may not buy) 1 | 8 | 305.88 | 29.52 |
| 1 | s01 | 14 | 11 | 11 (11) | 2: stuck at another chosen stall 1; bought elsewhere (task complete) 1 | 7 | 36.15 | 1.93 |
| 2 | s42 | 4 | 10 | 10 (10) | 7: bought elsewhere (task complete) 4; stuck at this stall (chose it, may not buy) 3 | 6 | 195.64 | 32.40 |
| 2 | s41 | 7 | 10 | 10 (10) | 6: bought elsewhere (task complete) 5; stuck at another chosen stall 1 | 4 | 331.49 | 32.16 |
| 2 | s01 | 3 | 9 | 9 (9) | 7: stuck at this stall (chose it, may not buy) 3; bought elsewhere (task complete) 3; budget 1 | 2 | 10.93 | 2.03 |
| 3 | s42 | 11 | 18 | 18 (18) | 11: bought elsewhere (task complete) 8; stuck at this stall (chose it, may not buy) 2; budget 1 | 11 | 592.79 | 34.32 |
| 3 | s41 | 5 | 8 | 8 (8) | 4: bought elsewhere (task complete) 4 | 5 | 225.19 | 34.56 |
| 3 | s01 | 8 | 10 | 10 (10) | 5: bought elsewhere (task complete) 3; stuck at this stall (chose it, may not buy) 1; budget 1 | 6 | 32.46 | 2.10 |
| 4 | s42 | 5 | 13 | 13 (13) | 10: bought elsewhere (task complete) 8; stuck at this stall (chose it, may not buy) 2 | 3 | 253.85 | 31.20 |
| 4 | s41 | 3 | 7 | 7 (7) | 5: bought elsewhere (task complete) 3; stuck at this stall (chose it, may not buy) 2 | 3 | 124.41 | 31.44 |
| 4 | s01 | 3 | 5 | 5 (5) | 3: bought elsewhere (task complete) 2; stuck at another chosen stall 1 | 2 | 11.03 | 1.93 |
| 5 | s42 | 4 | 9 | 9 (9) | 6: bought elsewhere (task complete) 3; stuck at this stall (chose it, may not buy) 1; budget 1; stuck at another chosen stall 1 | 5 | 198.04 | 30.00 |
| 5 | s41 | 4 | 10 | 10 (10) | 6: bought elsewhere (task complete) 5; budget 1 | 6 | 179.00 | 28.80 |
| 5 | s01 | 3 | 13 | 13 (13) | 10: bought elsewhere (task complete) 6; stuck at this stall (chose it, may not buy) 4 | 7 | 10.72 | 2.24 |

### Market level, seed 200, days 1–5

| Condition | Day | Purchases | Task complete | Stuck at a chosen stall | Other not complete | Catches | Set stalls closed at first reach (of 450) | Targets found closed | Inspections per local / expert |
|---|---|---|---|---|---|---|---|---|---|
| A|t40|l1 | 1 | 128 | 128 | 0 | 22 | 0 | 0 | 0 | 2.14 / 2.12 |
| A|t40|l1 | 2 | 131 | 130 | 0 | 20 | 0 | 0 | 0 | 1.20 / 1.53 |
| A|t40|l1 | 3 | 127 | 127 | 0 | 23 | 0 | 0 | 0 | 1.08 / 1.23 |
| A|t40|l1 | 4 | 133 | 133 | 0 | 17 | 0 | 0 | 0 | 0.95 / 1.28 |
| A|t40|l1 | 5 | 136 | 135 | 0 | 15 | 0 | 0 | 0 | 1.17 / 1.37 |
| B|t40|l1 | 1 | 115 | 115 | 11 | 24 | 9 | 17 | 0 | 2.04 / 2.06 |
| B|t40|l1 | 2 | 84 | 82 | 39 | 29 | 31 | 72 | 2 | 1.47 / 1.69 |
| B|t40|l1 | 3 | 106 | 102 | 21 | 27 | 17 | 38 | 1 | 1.45 / 1.68 |
| B|t40|l1 | 4 | 94 | 93 | 32 | 25 | 35 | 70 | 4 | 1.14 / 1.55 |
| B|t40|l1 | 5 | 112 | 108 | 19 | 23 | 16 | 31 | 1 | 1.76 / 1.86 |
| A|t100 | 1 | 148 | 148 | 0 | 2 | 0 | 0 | 0 | – |
| A|t100 | 2 | 148 | 148 | 0 | 2 | 0 | 0 | 0 | – |
| A|t100 | 3 | 148 | 148 | 0 | 2 | 0 | 0 | 0 | – |
| A|t100 | 4 | 149 | 149 | 0 | 1 | 0 | 0 | 0 | – |
| A|t100 | 5 | 149 | 149 | 0 | 1 | 0 | 0 | 0 | – |
| B|t100 | 1 | 83 | 83 | 52 | 15 | 40 | 81 | 3 | – |
| B|t100 | 2 | 86 | 86 | 50 | 14 | 35 | 85 | 4 | – |
| B|t100 | 3 | 105 | 105 | 34 | 11 | 36 | 65 | 7 | – |
| B|t100 | 4 | 89 | 89 | 44 | 17 | 40 | 81 | 16 | – |
| B|t100 | 5 | 101 | 101 | 38 | 11 | 38 | 68 | 4 | – |

## Run record

- Engine 0.13.0 at 2cc1342, unchanged. numpy 2.5.4, Python 3.12.7, macOS 26.6.2 arm64.
- Commands:
  - `.venv/bin/python -m analysis.honest_profit_diagnostic detail <file>`: seed 200, 5 days, 4 conditions; about 16 s.
  - `... repro`
  - `... summary 200-219 "B|t40|l1,B|t70|l1,B|t100" <file>`: 60 chains on 4 workers at nice 19; about 12 min; peak resident memory under 100 MB per worker.
- Spot check of the earlier walk-mode search runs: 3 days, seed 200 (inline, not saved).
- Per-seed results: `runs/honest_profit_diagnostic_seeds.json.gz`.
- Written after the results. Exploratory; no prespecified hypotheses.
