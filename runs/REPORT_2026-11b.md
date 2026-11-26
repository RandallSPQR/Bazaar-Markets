# Report: autonomous plan 2026-11-23 (checkpoint C7)

Plan `runs/plan_autonomous_2026-11-23.md`, preregistered at 326abfa (2026-11-24). Deviations D4–D6 (D1–D3 carried over from plan 2026-11-19). Run from 2026-11-24 to 2026-11-26. This report closes the plan.

**BLUF.** All four stages are done.
- **Engine 1.2.0.** It adds an undercut price floor, a run-level LLM spend ceiling and seller option sets. At its defaults it reproduces 1.1.0 byte for byte.
- **Price war.** At prices equal to cost, cashing in a good name pays even where locals check (+$227). Enforcement still stops it (−$327). Raising the floor above cost shrinks the payoff and restores brand equity. All four confirmatory predictions are supported.
- **State bank v2** is a much harder agent test than v1: 300 states, cheating pays in 49.8% (weighted), 98 close calls, two-thirds of states rated below 1.0, and no single observation predicts the answer above 75%.
- **Release.** v1.2.0 is tagged locally and the data package is built. **Nothing has been pushed** (Randall's instruction of 2026-11-26).

## Checkpoints

| | When | Result |
|---|---|---|
| C1 | 2026-11-24 | Engine 1.2.0 (f7f49a0); full suite 1,868 passed, 17 skipped, 4 outdated tests updated (their files 69/69) |
| C2 | 2026-11-24 18:09 | Price-war study launched, all 20 seeds |
| C3 | 2026-11-25 02:12 | Price-war summary: PW1–PW4 supported (a2bee13); D4 |
| C4 | 2026-11-25 11:26 | Bank v2 pilot: all gates pass; G-leak best single feature 77.8% (limit 80%) |
| C5 | 2026-11-25 11:28 | Bank v2 launched (D5, D6 later) |
| C6 | 2026-11-26 12:18 | Bank v2 complete (54c57c4) |
| C7 | 2026-11-26 | Release prep; v1.2.0 tagged locally; this report |

## Stage 1: engine 1.2.0

- **`sellers.undercut_floor_markup` m.** Under `undercut`, a stall never prices below unit cost × (1 + m). m = 0 is 1.1.0.
- **`agents.budget` and `engine/budget.py`.** These cap calls, tokens and dollars per run, and dollars per day across runs through a ledger.
  - Every limit is 0 by default, and no call happens without `--allow-spend`.
  - The price table is a placeholder.
  - A refused call stops the run, which is marked `INVALID: budget`.
  - `--dry-run-cost` estimates cost without calling.
- **Seller option sets.** `v2` leaves out the contract licence.
- **Tests.** `tests/test_v120.py` 28/28, with a mock agent and no network. Full suite 1,868 passed, 17 skipped, 4 failed. The 4 failures were tests asserting 1.1.0 behaviour that 1.2.0 changes by design: the reference comparison now strips the 1.2.0 keys, and the LLM stub is now refused by the budget. The tests were updated and their files rerun 69/69. Reference cells are unaffected.
- **Docs.** Config reference, CHANGELOG, agent interface (open point 2 closed) and the formal model (new keys labelled "added at 1.2.0, not cross-checked").

## Stage 2: price-war study

`runs/price_war_summary.md`. 3,440 chains, seeds 500–519 paired, 8.05 h, guards 0. G2: m = 0 reproduces the 1.1.0 undercut chains, 60 of 60.

| | Prediction | Estimate [95% CI] | Verdict |
|---|---|---|---|
| PW1 | Undercut m = 0, ds 0: bust-out gain > 0 | +$227.47 [+174.75, +280.20] | supported |
| PW2 | ds 0: slope of the gain over m < 0 | −$775.07 [−942.20, −607.94] per unit of m | supported |
| PW3 | Slope of brand equity E over m > 0 | +$11,825.51 [+8,644.22, +15,006.79] per unit of m | supported |
| PW4 | Undercut m = 0, ds 1: gain < 0 | −$327.37 [−406.06, −248.68] | supported |

Reading (written after the results, as in the summary):
- A price war at cost removes the margin that verification protects. The cheap-supply saving is then the only profit left, so cashing in pays even where locals inspect. Under rating_indexed the same cell loses $85.
- A floor of 10% above cost cuts the gain to +$52, and 30% to −$25.
- E is about $0 at m = 0 and climbs back to $3,549 at m = 0.3, against $3,992 under rating_indexed.
- Enforcement works in a price war as it does elsewhere.
- Exploratory (PW5): buyers gain $27 to $31 of surplus per buyer from the lower prices in chains where nobody busts out. The choice rule barely matters (sharp − lex −$10).

## Stage 3: seller state bank v2

`runs/state_bank_v2_summary.md`, README `runs/state_bank_v2/README.md`, data `runs/state_bank_v2/states.jsonl.gz`.

- **Scale and time.** 24 markets; 172,800 eligible states; 300 drawn, with weights. K 20 paired continuations of 5 options plus exit, 31,000 continuations, guards 0. Wall clock: enumeration 3.07 h, pilot 6.11 h, bank 24.7 h.
- **Plan targets.**

  | Target | Result | Met? |
  |---|---|---|
  | At least 25% of states rated below 1.0 | 66% | yes |
  | At least 100 close calls | 98 | **no, missed by 2** |
  | Cheating pays in 40–60% of states | 35.7% unweighted, 49.8% weighted | **no, unweighted** |

  Neither missed target is a gate, and nothing was changed to meet them.
- **Final G-leak passes.** Best single feature `units_7d` 75.3% (base rate 64.3%), depth-2 tree 72.7%, logistic regression 76.0%. The reduced observation set gives the same best feature.
- **What changed from v1.** Whether cheating pays now depends on several factors at once:
  - weighted, it pays in 70% of markets without enforcement and in 27% under full enforcement;
  - in 70% where the owner is not liable and in 30% where it is;
  - in 71% where buyers are tourists only and in 12.5% with 40% tourists.

  The best option is split: keep supply 50%, cheap licence 44%, weighted. Always keeping supply gets 50% best-option accuracy, with a regret of 37% of honest profit. That is the baseline for agents.
- **Concentration.** The prespecified allocation put 176 states in one stratum. Randall kept it (2026-11-25).

## Stage 4: release prep (nothing pushed)

| Item | File | Status |
|---|---|---|
| Baseline rows: robustness PX1–PX4 (X1–X4), price war PW1–PW5 (P1–P5), banks v1 and v2 (S1, S2), headline check | `runs/BASELINE_1_2_0.md` (new, section 7) | done |
| README headlines: "once enough buyers check (about a third in this market)" (exploratory); "likely by closing deceptive stalls"; "where buyers read ratings"; one line on the sweep (PX1–PX3, 15 cells); status line updated | `README.md` | done, for review |
| Release notes | `docs/release_notes_1_2_0.md` | draft |
| Citation metadata: version 1.2.0, date 2026-11-26, top-level DOI set to the all-versions DOI | `CITATION.cff` | done, for review |
| Data package, CC BY 4.0: bank v2 files and caches, price-war caches; 25 files, 17.1 MB; checksums verified after extraction | `dist/v1.2.0/` (not in git); manifest `runs/data_package_1_2_0.md` | built, not uploaded |
| Tag | `v1.2.0`, local, annotated | made, **not pushed** |

## Deviations

None changed a design, seed, prediction or confirmatory analysis.
- **D4.** The PW5 paired differences had their sign reversed (`paired_diff(a, b)` returns b − a). The as-run outputs were committed first and kept in `runs/price_war_as_run/`. The tables were then regenerated from the cache, with no new chains. PW1–PW4 are identical, and all 20 PW5 differences flip sign exactly.
- **D5.** The bank's concentrated market projected 19.7 h, over the 10 h block limit; the script's G3 checked only the 36 h total. Block 2 ran as several launches of at most 10 h each, resuming from the chain cache.
- **D6.** Randall freed the CPU on 2026-11-25. Block 2a was stopped by hand, and the bank finished on 7 workers. The block script now takes a worker count. Chains are seeded per job, so this changes wall clock only.

## Open items for Randall

1. **Push and publish.** The local commits since a3e997e and the v1.2.0 tag are not pushed. To do:
   - create the GitHub release;
   - let Zenodo mint the software DOI;
   - upload `dist/v1.2.0/` as a dataset;
   - add the new DOIs to `CITATION.cff` and the README.
2. **Review the wording.** README headlines, the `CITATION.cff` abstract and the release notes are drafts written by Claude. `runs/BASELINE_1_2_0.md` section 7.4 treats 1.0.0 open questions 5 and 6 (headlines 5 and 2) as addressed by the new wording. Please confirm.
3. **Bank v2 limits.**
   - The allocation is concentrated (176 of 300 states in one stratum).
   - Close calls are 98 of 100, and the pilot's shrunk rates over-predicted them (140).
   - The leakage margin is 5 points.
   - A later bank could allocate from a larger pilot.
4. **The cheap licence is still cheating's best route.** It is the best cheating option in 219 of 300 states, and is never caught or fined at the owner unless the owner is liable. Open item 2 of the previous report (an `owner_liable` study) still stands.
5. **Not in the data package.** The engine 1.1.0 caches (state bank v1 and the robustness sweep) are in neither the v1.0.0 dataset nor this one. Add them if the dataset should cover every published run.
6. **LLM prices.** `agents.budget.prices` is an empty placeholder. Fill it in before any paid run.
7. **Still open from earlier.** The 11 questions in BASELINE section 6 (1.0.0), and the Zenodo creator name lacking its final period.

## Compute

Everything ran on the local CPU only. There were no LLM calls and nothing billable; no GPU pods or watchdogs were touched.

| Run | Wall clock | Workers |
|---|---|---|
| Full suite | 1.75 h | – |
| Price war (pilot and main) | 1.24 h + 8.05 h | 4 |
| Bank v2: enumeration, pilot, bank | 3.07 h + 6.11 h + 24.7 h | 4, then 7 from 2026-11-25 15:03 |

All runs used nice 19 and `caffeinate -i`, with memory pauses 0.

## Next

Per Randall (2026-11-26): commit `runs/plan_autonomous_2026-11-27.md` unchanged as its preregistration, then follow it. Push nothing.
