# Trapped- and parked-buyer fixes, stuck-buyer guard, Stage B rerun

Spec "Fix the trapped-buyer bug, add a stuck-buyer guard, rerun Stage B" (2026-11-09), with the PI's
decisions of the same day: also fix the parked-buyer trap ("Yes, fix both"); no reruns of earlier
runs; check that parked buyers do not survive 0.14.0 before Stage B; gate Stage B on a 3-seed observer
pre-flight, because the frozen verification script does not record guard counts.

## 1. The fixes (engine 0.14.0, aff9549)

**Trapped buyers** (`runs/honest_profit_diagnostic.md`). Under choice-set demand, a buyer whose set
held a stall that was closed when it walked past never counted that stall as seen. It chose at its
route end, walked back, and the phase reverted to "browse", where it could not buy. It stood at an open
stall it wanted until close. Fix: once in "choose", a buyer stays there until it buys, or finds its
target closed and chooses again from its remaining candidates (`Person.choosing`, `search_decide`).

**Parked buyers** (since 0.10.0, found by the guard). A searching buyer that decided not to buy at the
stall it had chosen (inspection showed less than the claim, or it could no longer afford a unit) kept
the stall as its target and stood there for the rest of the day. Fix: on `move_on` at its target, the
buyer drops the target and walks on, choosing again where it can (`buyer_did`).

**Guard.** Every outcome reports, at the end of the day:
- `stuck_buyers`: buyers in the market, in reach of the open stall they chose, needing units, with
  budget for one there.
- `idle_choosers`: searching buyers in "choose" with an open, affordable stall of their category (and
  set) in reach.

Multi-day results add `{"by_day", "total"}` for both. `compare_logs` ignores the two keys when replaying
a log from an engine before 0.14.0.

## 2. Tests

`tests/test_trapped_buyers.py`, against `tests/reference/outcomes_v0130.json`: 86 cells generated at
56f0574 (engine 0.13.0). These are the 0.12.0 cells plus the verification-run, walk-search and posts
cells.

- **68 cells reproduce 0.13.0 byte for byte** (guard keys removed), including every walk-mode cell
  without a parked buyer and every cell without closures.
- **18 cells change on purpose.** They are checked against their 0.14.0 regeneration
  (`outcomes_v0140.json`):
  - trapped (12): `v0120_choice_default`, `v0120_choice_rent`, `v0120_choice_brands_cf`,
    `v0130_choice_posts_1day`, `v0130_verif_B_t40`, `v0130_verif_B_t100`, each for seeds 0 and 1;
  - parked (6): `v0100_t1_others3_brands|0`, `v0110_bargain|1`, `v0110_bust_at|1`, `v0110_capture|1`,
    `v0110_critics_ties_emb|1`, `v0130_walk_search_insp|1`.
- **The guard reads 0 in all 86 cells.**
- **Regression tests:**
  - The diagnostic's reproduction (s22 closed all day): 0 stuck buyers. Purchases are 147 against 148
    in the control; the one buyer short bought at s22 in the control and has no other set stall whose
    claim meets its Q_req.
  - A parked-buyer test, a guard unit test, and the multi-day guard keys.
- **Older reference tests** compare with the guard keys removed and skip the 18 on-purpose cells (17
  skips).

Full suite at 0.14.0: **752 passed, 17 skipped** (21.5 min, `runs/tests_0140_confirm.log`).

## 3. Certification of earlier runs (f0ea358, `runs/certification_stuck.md`)

Each committed run was replayed at its own commit, 3 seeds × every condition, with an observer counting
stuck, parked and idle buyers after every market day.

| Run | Engine | Buyer-days | Stuck | Parked | Parked share |
|---|---|---:|---:|---:|---:|
| Placement sweep | 0.2.0 | 6,300 | 0 | 0 | 0 |
| Visibility × adaptivity | 0.3.0 | 9,900 | 0 | 0 | 0 |
| Recognition sweep | 0.4.0 | 13,500 | 0 | 0 | 0 |
| Grid refinement | 0.5.0 | 25,200 | 0 | 0 | 0 |
| Search / counterfeit | 0.10.0 | 243,900 | 2 | 30 | 0.012% |
| Dilemma boundary | 0.10.0 | 135,000 | 0 | 86 | 0.064% |
| Capture A | 0.11.0 | 810,000 | 0 | 0 | 0 |
| Capture B | 0.11.0 | 1,620,000 | 0 | 618 | 0.038% |
| Verification A | 0.13.0 | 1,080,000 | 0 | 0 | 0 |

- **The trapped-buyer bug was not possible in any of these runs.** It needs choice-set demand together
  with closures; verification A, the only choice-set run here, had no inspectors.
- **Every flag is the parked-buyer bug.**
- **Search/counterfeit triggered the stop rule** (2 stuck buyer-days of 243,900). The PI waived it as
  negligible.
- **No earlier run was rerun.** Each affected summary carries a certification line (f2c3d8a).

## 4. Parked buyers at 0.14.0 (3357cd9, `runs/parked_check_0140.json`)

The same observer, on the current engine, over the flagged runs, the pilot, and the Stage B design:

| Check | Jobs | Buyer-days | Stuck | Parked | Idle choosers |
|---|---:|---:|---:|---:|---:|
| Pilot P2/P3 (seeds 900–904) | 20 | 46,500 | 0 | 0 | 0 |
| Search / counterfeit (seeds 2–4) | 60 | 243,900 | 0 | 0 | 1 |
| Dilemma boundary (seeds 32–34) | 30 | 135,000 | 0 | 0 | 0 |
| Capture B (seed 52) | 120 | 540,000 | 0 | 0 | 0 |
| Stage B, every condition (seeds 200–202) | 240 | 1,080,000 | 0 | 0 | 0 |

**The parked-buyer behaviour does not survive 0.14.0, so there is no 0.14.1.** Fix 2 above already
drops the target on `move_on`. The flagged runs' own jobs now read 0 parked where they read 30, 86 and
534 at their own engines. The 534 is capture B, seed 52 only, the same 120 jobs.

The single idle chooser (search/counterfeit, budget 1.25, fresh, honest, depth (4, 4, 4), seed 3) is
not a gate item. The observer's idle count does not check Q_req, or whether the buyer had already
inspected and rejected that stall.

Stage B pre-flight by condition (seeds 200–202, 48 chains and 216,000 buyer-days each): 0 stuck and 0
parked in B|t40|l1, B|t40|l0, B|t70|l1, B|t70|l0 and B|t100.

## 5. Choice-set pilot P2/P3 at 0.14.0 (845e9e4, `runs/pilot_recheck_0140.md`)

Both checks pass, as they did at 0.12.0, with the same sign and larger effects. P2 patrolling − posts
on deceptive profit is −$228.09 (was −$201.86), and on shortfall −0.084 (was −0.052). Catches rise
14–26% in P2 and 10–12% in P3, because buyers who were trapped now buy. The guard reads 0 in all 20
runs.

## 6. Stage B rerun (engine 0.14.0, commit 6268c3e)

Same frozen script (sha `fcf2193…`), seeds 200–219, the same sampled stalls and the same analysis;
only the engine changed. 1,600 chains × 30 days on 4 workers at nice 19, 2.99 h (22:03–01:03), no
memory-guard pauses, 0 flags. The old cache was set aside, so nothing was reused. Full record and tables
in `runs/verification_summary.md`; the 0.13.0 Stage B is kept there in a "Superseded (trapped-buyer
bug)" appendix, with its data as `runs/verification_B_v0130.*`.

**PV4 (confirmatory) is supported.** Tourists only: Stage B − Stage A = −$1,001 [−1,212, −790] (it was
−$942 at 0.13.0). The gain falls from +$565 to −$436.

| Condition | Verifying share | Gain at 0.14.0 ($) | Gain at 0.13.0 ($) | B − A at 0.14.0 ($) |
|---|---:|---:|---:|---:|
| t40\|l1 | 0.60 | −494 [−606, −382] | −426 | −383 [−473, −292] |
| t40\|l0 | 0.30 | −462 [−578, −346] | −413 | −464 [−581, −346] |
| t70\|l1 | 0.30 | −491 [−618, −363] | −439 | −527 [−681, −373] |
| t70\|l0 | 0.15 | −460 [−575, −345] | −407 | −566 [−719, −412] |
| t100 | 0.00 | −436 [−537, −335] | −377 | −1,001 [−1,212, −790] |

The qualitative Stage B result is unchanged. A bust-out loses in every condition and every stall-seed,
day 30 is always the least bad day, and the floored gain is $0 everywhere. The verification gradient
nearly vanishes under enforcement: the slope is +$10 per 0.1 [+3, +17], against +$113 in Stage A.

**Corrected never-bust honest profit** (`analysis/never_profit_0140.py`; per seed, the mean of 3
sampled genuine stalls; paired over 20 seeds):

| Condition | Stage A, no inspectors ($) | Stage B, 2 inspectors ($) | B − A ($) | Stage B at 0.13.0, superseded ($) |
|---|---:|---:|---:|---:|
| t40\|l1 | 4,652 [3,528, 5,776] | 5,081 [3,858, 6,304] | +429 [313, 545] | 3,255 |
| t40\|l0 | 4,674 [3,537, 5,810] | 5,322 [4,047, 6,598] | +649 [495, 802] | 3,465 |
| t70\|l1 | 3,227 [2,393, 4,062] | 4,642 [3,489, 5,794] | +1,414 [1,086, 1,742] | 2,446 |
| t70\|l0 | 3,235 [2,392, 4,078] | 4,741 [3,562, 5,919] | +1,506 [1,159, 1,854] | 2,566 |
| t100 | 1,818 [1,296, 2,340] | 4,555 [3,445, 5,665] | +2,737 [2,137, 3,338] | 1,902 |

**Stuck and parked buyers by condition.** The frozen script keeps no guard counts per chain. The 3-seed
observer pre-flight (section 4) read 0 stuck and 0 parked in each of the five Stage B conditions.

## Reading (written after the results)

The trapped-buyer bug was the whole of the "inspectors cut honest profit" puzzle. With it fixed,
inspectors raise the honest stall's never-bust profit in every condition, by about 9% where verifiers
are many and 2.5× in the tourist-only market. A likely mechanism is that catches close deceptive stalls
and their would-be buyers move to genuine ones; this is not decomposed. PV4 survives the fix and the
Stage B − Stage A gap widens slightly. Part of that gap at low verification is now the higher honest
baseline (the gain is measured against never busting out), not only a costlier bust-out. No earlier run
was rerun. Three carry small parked-buyer exposure (0.012–0.064% of buyer-days), recorded in their
summaries.
