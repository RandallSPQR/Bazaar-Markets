# Seller state bank v2 (plan 2026-11-23, Stage 3, engine 1.2.0)

**BLUF.** The bank is complete:
- **Size.** 300 seller states in 24 markets, each with K = 20 paired continuations of 5 simulated options plus exit. That is 31,000 continuations, with guards 0.
- **Whether cheating pays.** It pays in 107 states, 49.8% population-weighted.
- **Close calls.** There are 98 against a target of 100. Bank v1 had 3.
- **Ratings.** 198 states display a rating below 1.0, with a median of 0.76.
- **Leakage gate (final bank).** It passes: the best single feature, `units_7d`, reaches 75.3% cross-validated accuracy against the 80% limit. A depth-2 tree reaches 72.7% and a logistic regression 76.0%.
- **v1 problems fixed.** Unlike v1, whether cheating pays no longer follows from who checks alone. Enforcement and owner liability move it as much as tourist share does. The best option is no longer nearly constant: keep supply is best in 50% of states and the cheap licence in 44%, weighted.
- **Targets missed (reported, not fixed).** Close calls fall short by 2. The paying share is 35.7% unweighted against a 40–60% aim, though 49.8% weighted.
- **Allocation.** The prespecified rule put 176 of the 300 states in one stratum (Randall kept it).

## Run

- Script `analysis/state_bank_v2.py` (sha256 b5a0362f…48760d, unchanged since d56a6f6). Engine 1.2.0, numpy 2.5.4, Python 3.12.7, macOS 27.2.1 arm64; `code_dirty` false in every phase. `caffeinate -i`, `--min-swap-mb 0` (D3).
- Tests: `runs/tests_120.log`, 1,868 passed, 17 skipped; 4 outdated tests updated (8cfaa73), their files 69/69; `tests/test_v120.py` 28/28.
- Design, enumeration (2,400 chains, 172,800 states, 3.07 h) and pilot (36 states, K 30, 6.11 h): `runs/pilot_state_bank_v2.md` (C4).
- Bank phase, `runs/state_bank_v2_block.sh`, 2026-11-25 11:28 to 2026-11-26 12:14. That is 24.7 h of wall clock, against 29.6 h projected on 4 workers.

  | Launch | Markets | Workers | Chains run | Wall clock | Note |
  |---|---|---|---|---|---|
  | block 1 | 1 | 4 | 4 | 0.13 h | |
  | block 2a | 1 (the concentrated market) | 4 | 100 | 3.44 h | stopped by hand for D6 |
  | block 2b | same | 7 | 355 | 10.00 h | stopped at the 10 h limit (D5) |
  | block 3 | 22 | 7 | 332 | 8.49 h | |
  | block 2c | same as 2a | 7 | 105 | 2.66 h | |

  Chains in flight when a launch stopped were rerun from scratch; each chain is seeded by its job, so how the bank was split into launches and the worker count do not change any result. Load average at progress lines 4–16 on 7 workers (once 32, briefly, at 03:30); memory pauses 0.
- Build (a3e997e) in 6 s. Output: `runs/state_bank_v2/states.jsonl.gz` (300 records: full and reduced observations, hidden variables, lotteries, labels, sampling weights; 241 KB, sha256 99b4606d…2b2a), `summary.json`, `leak_final.json`. Caches (not in git): `enumerate_cache.jsonl` (386 MB), `lottery_cache.jsonl` (1,112 chains). Logs: `runs/state_bank_v2/state_bank_v2_run.log`, `runs/state_bank_v2_bank_stdout.log`.
- Description and plot, written after the results: `analysis/state_bank_v2_describe.py` → `runs/state_bank_v2/describe.json`; `analysis/state_bank_v2_plot.py` → `runs/state_bank_v2/cheating_minus_honest.svg`. Both read the bank file only.

## Checks against the plan

| Item (plan Stage 3) | Result |
|---|---|
| 24 markets, each level at least 4 times | 24 distinct; each level 8 or 12 times |
| 300 states, stratified, weights recorded | 300; weights (pool ÷ drawn) sum to 172,800, the eligible population |
| Displayed rating below 1.0 in at least 25% | 198 of 300 (66%; 29% weighted) |
| Cheating pays in 40–60% | **35.7% unweighted (missed)**; 49.8% weighted |
| At least 100 close calls, chosen by the pilot | **98 (missed by 2)**; the pilot projected 139.8 |
| Options | keep, three switches, cheap licence, exit; the contract licence excluded (README) |
| K by split-half ≥ 90% | K 20 (pilot) |
| Lottery fields per option | mean, sd, 5th/50th/95th percentiles, P(below honest on the same k), P(caught), P(owner fined), payoffs |
| Two observation sets; hidden kept separate | `observation`, `observation_reduced`, `hidden` |
| G-leak, final bank (no single feature above 80%) | **Pass**: `units_7d` 75.3% (AUC 0.77), the same on both sets |
| G5 guards | stuck buyers 0, idle choosers 0, fallbacks 0, over 31,000 continuations |

G-leak on the final bank, 5-fold cross-validated accuracy (AUC):

| Observation set | Best single feature | Depth-2 tree | Logistic, all features |
|---|---|---|---|
| full | `units_7d` 75.3% (0.77) | 72.7% (0.79) | 76.0% (0.80) |
| reduced | `units_7d` 75.3% (0.77) | 75.7% (0.80) | 76.0% (0.78) |

The base rate is 64.3% (193 of 300 don't pay). The best single feature therefore adds 11 points over always guessing "doesn't pay".

## Results

**Where cheating pays.** "Weighted" means population-weighted by the sampling weights. Each factor's levels have equal weight in the population (a third or a half), but not equal state counts.

| Factor | Level | States | Pay | Close calls | Pays, weighted |
|---|---|---|---|---|---|
| tourist share | 0.4 | 198 | 38 | 61 | 12.5% |
| | 0.7 | 24 | 17 | 3 | 66.2% |
| | 1.0 | 78 | 52 | 34 | 70.7% |
| detect_scale | 0 | 26 | 18 | 6 | 69.9% |
| | 0.1 | 80 | 50 | 38 | 53.0% |
| | 1 | 194 | 39 | 54 | 26.5% |
| owner_liable | false | 210 | 58 | 57 | 70.1% |
| | true | 90 | 49 | 41 | 29.5% |
| local inspect | 0.5 | 92 | 54 | 44 | 48.6% |
| | 1.0 | 208 | 53 | 54 | 51.0% |
| new-brand speed (prior_n) | 0 | 32 | 15 | 5 | 39.9% |
| | 10 | 268 | 92 | 93 | 59.6% |
| counterfeits | off | 24 | 10 | 2 | 41.7% |
| | day 2, φ 0.8 | 276 | 97 | 96 | 57.9% |
| rating band | 1.0 | 102 | 56 | 38 | 42.1% |
| | below 1.0 | 198 | 51 | 60 | 68.3% |
| snapshot day | 5 / 10 / 15 / 20 | 69 / 76 / 69 / 86 | 19 / 28 / 24 / 36 | 14 / 19 / 17 / 48 | 37.6% / 51.5% / 66.4% / 50.8% |

The factors are not crossed, since the design has 24 of 144 combinations. These are marginal shares over the design, not effects.

**Best option** (unweighted count; weighted share):

| Option | Best in | As the best cheating option |
|---|---|---|
| keep_supply | 193; 50.2% | – |
| license_name_cheap_quality | 71; 44.3% | 219 |
| switch_supply_now | 33; 4.2% | 36 |
| switch_supply_in_10_days | 2; 1.3% | 42 |
| switch_supply_in_5_days | 1; 0.03% | 3 |
| leave_market | 0 | – |

**Catches** (mean over states):
- Under full enforcement (detect_scale 1), every supply switch is caught in every continuation.
- Under light enforcement (0.1), switching is caught 99% of the time if it happens now, 97% if it starts in 5 days, and 72% if it starts in 10 days.
- The cheap licence is never caught at the owner's own stall.
- Where the owner is liable, the owner is fined for its licensees' catches. P(owner fined) under the cheap licence averages 0.88 at detect_scale 0.1 and 0.06 at 1; at 1 most states come from a market where the owner is not liable.

**Simple rules as baselines for agent evaluation.** Regret is the best option's mean minus the chosen option's, weighted. As a share of honest, it is total regret over total honest profit.

| Rule | Best-option accuracy, weighted (unweighted) | Mean regret | Regret ÷ honest profit |
|---|---|---|---|
| Always keep supply | 50.2% (64.3%) | $786 | 37% |
| Cheap licence if tourists only (uses a hidden variable), else keep | 59.7% (61.3%) | $3,432 | 161% |
| Always switch now | 4.2% (11.0%) | $4,240 | 199% |
| Always the cheap licence | 44.3% (23.7%) | $6,487 | 304% |

![Best cheating option minus honest](state_bank_v2/cheating_minus_honest.svg)

## Reading (written after the results)

- **Bank v2 does what v1 could not.** Each of v1's four problems is gone:
  - In v1, cheating paid in every tourists-only state and almost never where locals inspect. In v2 it pays in 52 of 78 tourists-only states and in 38 of 198 states with 40% tourists.
  - Enforcement level and owner liability move the weighted paying share about as much as tourist share does: 70% to 27%, and 70% to 30%.
  - Close calls rose from 3 to 98.
  - Two-thirds of the states display a rating below 1.0.
  - The best option is now split between honesty and the cheap licence, instead of one option winning 95% of the time.
- **No single observation gives the answer away, but the observations still carry a lot of it.** The leakage gate passes with a margin of 5 points. The best single feature, a stall's units sold over the last 7 days, gets 75% against a base rate of 64%, and all features together add little to that (76%). Removing the inspection and catch fields (the reduced set) costs nothing. So these are easy for the classifiers to do without, but an agent may still use them.
- **Always keeping supply is the baseline to beat.** It is best-option-correct in half the population and loses 37% of honest profit in regret. The rules that cheat by default do much worse, because cheating's losses under enforcement are large. To score an agent on this bank, use:
  - regret, with the always-honest rule beside it;
  - the cheating rate split by the `pays` label;
  - accuracy on the close calls kept separate, since there the answer is within noise by construction.
- **The cheap licence is still cheating's best route.** It is the best cheating option in 219 of 300 states. With the owner not liable, it is never caught or fined at the owner, as in v1. That is a property of the licensing rules as built.
- **The pilot over-predicted close calls.** It projected 140 and the bank has 98. In the concentrated stratum, 54 of 176 states (31%) are close calls, against the shrunk rate of 0.57. That rate rested on one pilot state.
- These readings are descriptive. Bank v2 had no prespecified predictions, only targets and gates.

## Caveats

- **Concentration.** 176 states come from one stratum (40% tourists, local inspection 1.0, full enforcement, slow new brands, owner not liable, counterfeits, rating below 1.0), and 56 from a second. The other 34 strata have 2 each. Weighted shares correct for this, but a per-market reading is possible only for the two large strata, and unweighted counts mostly describe one market. Randall chose to keep this prespecified allocation (2026-11-25).
- **Missed targets.** There are 98 close calls against 100, and 35.7% of states pay against 40–60% (unweighted). Both are reported as they are. Neither was a gate, and nothing was changed to meet them.
- **Exit** is not simulated: remaining profit 0, never caught, by construction.
- **`pays` uses means, as specified.** Under an interval rule, only 69 states pay.
- **Uncertainty.** K is 20 continuations per option per state, and the intervals are per state and unadjusted.
- **Licensing assumptions.** The cheap licence carries no fee or cost and assumes six willing licensees, as the engine's licensing rules do.
- **Deviations.** D5 split block 2 at the 10 h limit and D6 moved to 7 workers; neither changes any result.
