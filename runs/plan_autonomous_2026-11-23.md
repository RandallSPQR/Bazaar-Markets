# Autonomous plan, 2026-11-23: engine 1.2.0 → price-war study → seller bank v2 → release prep

This file is the preregistration for everything below. Commit it, unchanged, before running anything. Do not edit predictions after any result is seen; if something must change, add a dated note under "Deviations" and say why.

Run the stages in order, unattended, and continue on your own whenever every gate passes. The operating rules, STOP conditions and record keeping of `runs/plan_autonomous_2026-11-19.md` apply unchanged, including D1–D3: blocks of at most 10 h run back to back, `caffeinate -i`, and the free-memory guard. Keep `runs/STATUS.md` current, and commit and ping at each CHECKPOINT. **No LLM API calls in this plan.**

Market defaults unless a stage says otherwise: the v1.0.0 reference market (`configs/reference_1_0.json`), with display stars at step 0.02, tie_break random and lexicographic choice.

---

## Stage 1: engine 1.2.0

Defaults must reproduce 1.1.0 byte for byte. Commit with tests before any pilot.

1. **Undercut floor.** `sellers.undercut_floor_markup` m ≥ 0, default 0 (the 1.1.0 behaviour). Under `price_policy` undercut, the floor becomes unit cost × (1 + m) instead of unit cost.
2. **Run-level spend ceiling for LLM agents** (open item 7 of `runs/REPORT_2026-11.md`):
   - **Budget keys.** `agents.budget.max_calls_run`, `max_tokens_run` and `max_usd_run`, plus `agents.budget.max_usd_day`, which is enforced across runs through a ledger file at `runs/llm_ledger.jsonl`.
   - **Prices.** A price table per model in config, in $ per million input and output tokens. Its values are placeholders, to be filled in by Randall before any real call.
   - **Defaults.** Every budget defaults to 0. No call is possible unless the run is started with `--allow-spend` and a positive budget.
   - **Cache hits.** Calls answered from the response cache cost nothing and do not count against the budget.
   - **Hitting a limit:**
     - Stop the run cleanly at the next decision point.
     - Write partial outputs.
     - Mark the run record `INVALID: budget`.
     - Count every capped call as a fallback.
     - Never fall back silently to the rule agent for the rest of the run.
   - **Dry run.** `--dry-run-cost` estimates calls, tokens and dollars from the prompts without calling anything.
   - **Tests.** Use a mock LLM agent, with no network. Check that:
     - each limit stops the run at exactly the right call;
     - the ledger adds up across two runs;
     - the day limit holds across runs;
     - a run without `--allow-spend` makes 0 calls;
     - cache hits are free.
   - Update `docs/agent_interface.md` (open point 2 closed).
3. **Bank v2 support,** if not already present: a seller option set that excludes `license_contract_6` from agent-facing files, while the engine still supports it. Also any keys needed for the Stage 3 markets.

Full suite. Update the config reference and CHANGELOG.

CHECKPOINT C1.

---

## Stage 2: price-war study (`analysis/price_war.py`, `runs/price_war_*`)

**Question.** In the robustness sweep (exploratory), the undercut policy drove prices to unit cost, brand equity vanished, and cashing in a name paid even where locals inspect. Does removing the margin above cost make quality fraud pay, and does enforcement still stop it?

**Design.**
- Price policy: rating_indexed, or undercut with floor markup m ∈ {0, 0.1, 0.3}. That makes 4 policy levels.
- Outcome A, the bust-out gain:
  - the verification benchmark (3 genuine stalls per seed from `default_rng([seed, 17])`; candidates never, day 20, 25, 28, 29, 30; the unfloored gain is primary);
  - 30 days;
  - tourist share 0.4 with locals inspecting (experts and locals as in the reference);
  - detect_scale 0 and 1.
- Outcome B, brand equity E = J(R) − J(W_g): as in `analysis/brand_equity_stars.py` (contract, genuine tier, royalty 0.10, N 6 from day 10, prior_scope new, 60 days), at prior_n 400, t40, detect_scale 1.
- Sensitivity cell (exploratory): outcome A at m = 0, detect_scale 0, under logit sharp.
- Seeds 500–519 (20), fresh, paired across all cells.

**Predictions.**
- PW1 (confirmatory): outcome A, undercut m = 0, detect_scale 0: the gain is > 0. A replication on fresh seeds of the sweep's exploratory +$169–198.
- PW2 (confirmatory): outcome A, detect_scale 0: the least-squares slope of the gain over m ∈ {0, 0.1, 0.3} is < 0. A margin above cost restores verification's protection.
- PW3 (confirmatory): outcome B: the slope of E over m ∈ {0, 0.1, 0.3} is > 0. A margin above cost restores the value of a reputation.
- PW4 (confirmatory): outcome A, undercut m = 0, detect_scale 1: the gain is < 0. Enforcement still works in a price war.
- PW5 (exploratory):
  - rating_indexed against undercut m = 0 on each outcome;
  - posted prices and margins;
  - buyer surplus and shortfall by profile;
  - whether a price war's lower prices outweigh its fraud for buyers;
  - the logit sharp cell.

**Analysis.** Per seed, the mean over sampled stalls or owners. Mean and 95% t over seeds, unadjusted.

**Pilot gates (seeds 900–902).**
- G1: the pipeline runs end to end.
- G2: m = 0 reproduces the 1.1.0 undercut chains bit for bit (two sweep seeds).
- G3: timing ≤ 12 h. If over, cut to 15 seeds; otherwise STOP.
- G4: stuck, parked and idle counts are 0.

CHECKPOINTS C2 (launch) and C3 (summary).

---

## Stage 3: seller state bank v2 (`analysis/state_bank_v2.py`, `runs/state_bank_v2/`)

**Why.** Bank v1 (`runs/state_bank_summary.md`) is too easy for an agent evaluation:
- deception pays in every tourist-only state and almost never where locals inspect;
- there are 3 close calls;
- every rating is exactly 1.0;
- the contract licence is best in 95% of states.

Bank v2 must make the answer depend on more than one observation.

**Markets.** Sample 24 markets from the following factors, stratified so that each level of each factor appears at least 4 times. Record the design.

| Factor | Levels |
|---|---|
| Tourist share (the rest locals and experts as in the reference) | 0.4, 0.7, 1.0 |
| Local inspect_prob | 1.0, 0.5 |
| detect_scale | 0, 0.1, 1 |
| New-brand speed (prior_scope new) | prior_n 0, 10 |
| owner_liable | false, true |
| Counterfeits | off, or day-2 entry at φ 0.8 |

Counterfeits are included so that some owners' ratings fall below 1.0. Use the rating_indexed price policy and 30 days.

**States.**
- Snapshot days d ∈ {5, 10, 15, 20}.
- Genuine stalls from seeds 600–699.
- Target 300 states, stratified by:
  - **rating band.** Displayed rating 1.0 vs below 1.0, with at least 25% below.
  - **whether cheating pays.** "Pays" means the best of switch_now, switch_d5, switch_d10 and license_cheap_6 beats honest by mean. Aim for 40–60% of states.
  - **close calls.** The paired difference, best cheating option − honest, has a 95% interval that includes 0, or its absolute value is under 5% of honest's mean. Target at least 100 close calls, chosen by a pilot pass, not by counting afterwards.
- Record the sampling weights.

**Options.** honest, switch_now, switch_d5, switch_d10, license_cheap_6 and exit. `license_contract_6` is excluded; note why in the bank's README.

**Lotteries.** As in bank v1: K continuations with common random numbers; K from split-half stability (≥ 90% agreement excluding close calls; start at 20). Record per option the mean, sd, percentiles, P(below honest on the same k), P(caught at least once), P(owner fined), and the payoff vector.

**Observations.** Store two observation sets per state, in neutral wording:
- **full:** as in bank v1;
- **reduced:** without the share of own visitors who inspected and without own catch notices.

Store the hidden variables separately, as in bank v1.

**Leakage gate G-leak** (on the pilot pass, then on the final bank). Fit three classifiers that predict "cheating pays" from the observation features alone, using 5-fold cross-validation:
- each single feature;
- a depth-2 decision tree;
- a logistic regression on all features.

Report accuracy and AUC for both observation sets. The target: no single feature exceeds 80% accuracy on the full set. If one does, STOP after the pilot and report which feature it is and its accuracy, with a proposed fix. Do not fix it unasked.

**Other gates.**
- G1: the pipeline runs end to end.
- G2: continuation reproduction holds for 3 states on the original streams.
- G3: projected time ≤ 36 h in blocks of at most 10 h. If over, cut to 240 states, then 200; otherwise STOP.
- G4: the strata targets are reachable in the pilot. If the close-call target can't reach 60, STOP and report.
- G5: stuck, parked and idle counts are 0.

CHECKPOINTS C4 (pilot and G-leak result), C5 (launch), C6 (bank complete).

---

## Stage 4: release prep (nothing pushed)

1. **BASELINE.** Add section 7 to `runs/BASELINE_1_0_0.md`, or start `runs/BASELINE_1_2_0.md` if cleaner. Give rows for Stage 3 of the last plan (bank v1, PX1–PX4), the price-war study and bank v2, each with its status.
2. **README headlines:**
   - Headline 1: say "once enough buyers check (about a third in this market)", labelled exploratory.
   - Headline 2: say "likely by closing deceptive stalls".
   - Headline 5: add "where buyers read ratings".
   - Add one line on the robustness sweep (PX1–PX3, 15 cells).
3. **Release notes.** Draft notes for v1.2.0 in `docs/release_notes_1_2_0.md`: engine changes since 1.0.0, the bank v2 dataset description, and its intended use (agent evaluation: regret, cheating where it doesn't pay, honesty where cheating pays).
4. **Data package.** Prepare the bank v2 files and the price-war caches for a Zenodo dataset (CC BY 4.0), with a manifest and checksums.
5. **Tag.** Tag v1.2.0 locally. Do not push; Randall pushes and publishes.

CHECKPOINT C7, with `runs/REPORT_2026-11b.md` (BLUF first, every verdict, open items). Then stop.

---

## Deviations

(None yet.)
