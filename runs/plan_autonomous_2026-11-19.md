# Autonomous plan, 2026-11-19: checking vs reading ratings → engine 1.0.0 → engine 1.1.0 (state bank, robustness)

This file is the preregistration for everything below. Commit it, unchanged, before running anything. The commit time is the record that the predictions came first. Do not edit predictions after any result is seen; if something must change, add a dated "Deviation" note at the bottom and say why.

Run the stages in order, unattended. Continue on your own whenever every gate passes. Stop only at the STOP conditions below.

## Operating rules

1. **Status and pings.** Keep `runs/STATUS.md` current: the stage, what is running, the projected finish time, the last gate result, and the next step. At each CHECKPOINT, update it, commit it, and send a push notification if you have that tool (one line: the stage, the result, and whether you are continuing). If you have no notification tool, the commit is enough.
2. **Machine.** 4 workers, nice 19, with the memory guard and load logging as in earlier runs. Never run two main runs at once. Batch long runs so that each night's output is usable on its own.
3. **Record keeping.** Same as every earlier run: a run record (engine, commit, script sha256, command, tests, Python/numpy/OS, wall clock, load, seeds), gates, a predictions table with verdicts, a reading written after the results (BLUF first), and caveats. Mark everything not prespecified here as exploratory.
4. **No rescues.** Never change a design, a seed set or an analysis after seeing results in order to change a verdict. The trimming rules in each stage are the only design changes allowed, and they are decided from timing alone, before launch.
5. **Files.** Delete nothing in the repo. Commit after each stage. Use neutral option names in all agent-facing files ("switch supply", not "bust-out"; "copied name", not "counterfeit").
6. **Market defaults from now on:** `ratings.display` stars, `ratings.display_step` 0.02 and `buyers.tie_break` random, unless a stage says otherwise.

## STOP conditions (stop, update STATUS.md, ping, wait for Randall)

- A test fails and the fix is not obvious and local.
- A code change made in this plan alters any reference cell from an earlier engine, except where a stage explicitly expects it.
- The formal-model cross-check (Stage 2) finds the code wrong, as opposed to the doc.
- A pilot gate fails after one honest attempt to fix the pipeline (not the design).
- Projected wall clock exceeds the stage's limit after its trimming rules are applied.
- Anything that would require changing a prediction, a seed set or a confirmatory analysis.
- A free-disk or memory problem that the guard cannot handle.

## CHECKPOINTS (ping and continue)

- C1: Stage 1 engine and pilot passed; main run launched (with ETA).
- C2: Stage 1 summary written.
- C3: Stage 2 cross-check done (the summary table); tag v1.0.0 made.
- C4: Stage 3 engine and pilots passed; state bank night 1 launched.
- C5: State bank complete.
- C6: Robustness sweep complete. Final report: a one-page `runs/REPORT_2026-11.md` with every verdict from Stages 1–3, BLUF first.

---

## Stage 1: checking vs reading ratings (engine 0.21.0)

**Question.** Locals both inspect and read ratings, so the model cannot say which behaviour stops bust-outs and which pays for reputation. Separate them.

**Engine 0.21.0** (commit with tests before any pilot):
- `buyers.profile_overrides`: per profile (tourist, local, expert, bargain), optional `reads_ratings` (bool) and `inspect_prob` (0–1). Unset means current behaviour. With `reads_ratings` false, the buyer ranks candidates as a tourist does and never sees ratings. `inspect_prob` is the probability it inspects an advertising stall before buying, replacing the profile's default.
- Tests: every 0.20.0 reference cell reproduces bit for bit with no overrides. A local with reads_ratings false and inspect_prob 0 behaves exactly as a tourist in a fixed choice set. Overrides change nothing else (budgets, Q_req, search). Full suite.

**Design** (`analysis/check_vs_read.py`, `runs/check_vs_read_*`):
- Buyers: tourist share 0.4. The other 0.6 are all locals (experts share 0). Locals: reads_ratings {yes, no} × inspect_prob {1.0, 0}, giving 4 cells. Reference cell: tourist share 1.0.
- Outcome A, bust-out gain: the verification-run benchmark (3 genuine stalls per seed from `default_rng([seed, 17])`; candidates never, day 20, 25, 28, 29, 30; unfloored gain primary). 30-day market, detect_scale 0 and 1.
- Outcome B, reputation effect: E = J(R) − J(W_g) as in `analysis/brand_equity_stars.py` (contract, genuine tier, royalty 0.10, N 6 from day 10, prior_scope new, 60 days), at prior_n 0 and prior_n 400. detect_scale 1.
- Seeds 350–369 (20), fresh, paired across all cells.

**Predictions:**
- PC1 (confirmatory): bust-out gain, detect_scale 0: the main effect of inspection (inspect 1.0 − 0, averaged over reads_ratings) is < 0.
- PC2 (confirmatory): bust-out gain, detect_scale 0: |main effect of reading ratings| < |main effect of inspection|.
- PC3 (confirmatory): reputation effect, prior_n 400: the main effect of reading ratings (yes − no, averaged over inspection) is > 0.
- PC4 (confirmatory): reputation effect, prior_n 400: |main effect of inspection| < |main effect of reading ratings|.
- PC5 (exploratory): both interactions (reading × inspection) for each outcome; the detect_scale 1 analogues of PC1–PC2; the prior_n 0 analogues of PC3–PC4.
- PC6 (exploratory): harm by profile; deceptive stalls' share of sales by cell; the bust-out decomposition's "rating below threshold" cause by cell.

**Analysis.** Per seed, the mean over sampled stalls or owners. Main effects and interactions from the 2×2 per seed. Mean and 95% t over seeds, unadjusted.

**Pilot gates (seeds 900–902).** G1: pipeline end to end. G2: overrides set to the profile defaults reproduce the no-override chains bit for bit; J identity to the cent. G3: timing limit 7 h; if over, drop the prior_n 0 level of outcome B first, then cut to 15 seeds; otherwise STOP. G4: the tourist-equivalence test passes in the pilot market. G5: stuck/parked/idle 0.

CHECKPOINT C1 at launch, C2 when the summary is written.

---

## Stage 2: lock the engine as 1.0.0

No behaviour changes, except fixes the cross-check forces in docs. If any code fix would change a reference cell, STOP.

1. **Formal-model cross-check.** Compare `docs/formal_model.md` against the code, equation by equation: prices, costs, demand and the choice rule, inspection, ratings (memory, prior, scope, display), detection and catches, fines, closures and lag, liability, licensing, counterfeits (entry and price factor), white-label tier, exit. The doc was written at 0.15.0. For keys added since, write the missing equations into the doc from the code, and label them "added at the 1.0.0 cross-check". For each item, record: matches / doc wrong (fixed) / code wrong (STOP), with file and line. Write `runs/formal_model_check.md`.
2. **Reference config.** `configs/reference_1_0.yaml`: the licensing market (choice-set m 3, gamma 0, 150 buyers, budget 1.25, bargain 0.2, ratings public, memory 0.7, display stars at step 0.02, tie_break random, brands on with premium 0.4, 2 patrolling inspectors not uniformed, detect_scale 1, collectible fines). Add named variants for every published run from verification onward. Each variant must reproduce its run's chains for two seeds bit for bit, on that run's engine settings.
3. **Regression suite.** `tests/reference/v1_0_0`: outcome digests for 2–3 seeds of every cell in every published run since engine 0.14.0, generated at 1.0.0 and checked against the saved runs. The suite fails if any digest moves.
4. **Baseline manifest.** `runs/BASELINE_1_0_0.md`: one row per finding, giving the claim in one sentence, run file, engine and commit, headline estimate with interval, and status (confirmatory supported / contradicted, exploratory, provisional, superseded). Mark as superseded: everything affected by the trapped-buyer bug, and the exact-rating brand-equity speed results (replaced by the stars run). Mark the walk-mode brand and counterfeit runs provisional.
5. **Agent interface (document only).** `docs/agent_interface.md`: every decision point (buyer search, choice, inspect; seller channel, price, switch supply, rename, licence, exit); what the agent sees at each; what it may return; invalid outputs and how the engine handles them; and how determinism is kept (seed streams, a response cache keyed by the prompt). Also add a "known rules of this world" list, stating each as a deliberate design fact: lexicographic choice by displayed rating then price; tourists cannot see ratings; prices set mechanically from displayed ratings (flagged as under test in Stage 3); perfect inspection; star display. Flag any decision point where an agent would see information a rule-based agent does not.
6. **Version and tag.** Bump to 1.0.0, write CHANGELOG.md (0.1 → 1.0, one line per version), run the full suite, commit, tag v1.0.0.

CHECKPOINT C3.

---

## Stage 3: engine 1.1.0, state bank and robustness sweep

Rule-based only; no API calls. Defaults reproduce v1.0.0 bit for bit.

### 3A. Engine 1.1.0
1. `sellers.price_policy`, market-wide, one of:
   - `rating_indexed` (default): the 1.0.0 formula, from the displayed rating.
   - `cost_plus`: unit cost × (1 + `sellers.markup`), markup default 0.5 (PLACEHOLDER).
   - `match_rival`: yesterday's median posted price among same-category stalls whose displayed rating is at least the stall's own − 0.1. Falls back to the stall's own rating_indexed price if there are none.
   - `undercut`: yesterday's lowest posted price among same-category stalls with an equal or higher displayed rating, minus $0.01, floored at unit cost.
   - `promo`: rating_indexed, but 15% off on any day after the stall's sales fell below its 7-day average.
   List every reader of price that each policy touches.
2. `buyers.choice`: `lexicographic` (default) | `logit`. Under logit, among qualifying stalls in the choice set, the buyer picks stall j with probability ∝ exp(w_r × displayed rating_j − w_p × price_j / base), drawn from `default_rng([seed, 37, day, buyer index])`. Rating readers use w_r = `buyers.logit_rating_weight`; tourists use w_r = 0. w_p = `buyers.logit_price_weight`. Inspection and the Q_req rule work as now; logit replaces only the ranking. There are two named settings, soft (5, 5) and sharp (20, 20), both PLACEHOLDER. In the pilot, report the share of sales a stall gains from a 5% price cut against an equal rival under each setting.
3. Checkpoint and continue: `engine.snapshot(day)` and `engine.continue(snapshot, option, k)`. From day + 1, every stochastic stream is re-seeded as `default_rng([seed, 31, k, stream id])`. A flag continues on the original streams, and that continuation must reproduce the original chain bit for bit.
4. Seller options applied to one stall at the snapshot day d: `honest`; `switch_now`; `switch_d5`; `switch_d10` (cheap supply from d+1 / d+5 / d+10, same name and price policy; skipped if past the last day); `license_contract_6`; `license_cheap_6` (N 6 from d+1, royalty 0.10); `exit` (close at the end of day d, keeping profit so far).
5. Tests: the v1.0.0 suite passes with defaults; each price policy posts its formula exactly; logit with both weights 0 picks uniformly; continuation reproduction holds for 5 seeds at days 5, 10 and 20; every option changes only the chosen stall's actions. Run the full suite. Update the config reference and agent_interface (the seller's view at a state, per 3B).

### 3B. Seller state bank (`analysis/state_bank.py`, `runs/state_bank/`)
- **Markets:** reference_1_0 × verification {t40 locals inspect, t100} × enforcement {detect_scale 0, 1} × new-brand speed {prior_n 0, prior_n 10 with prior_scope new}. That is 8 markets, each 30 days.
- **Days and sampling.** Snapshot days d ∈ {5, 10, 15, 20}. Sample genuine stalls with a displayed rating ≥ 0.9 from seeds 400–499. Target 200 states, stratified so that about half have some option (switch_*, license_cheap_6) with a higher mean payoff than honest, and at least 30 are close calls (the best two options within one standard error). Draw the strata from a pilot pass and record the sampling weights.
- **Observation per state** (JSON, neutral wording):
  - day and days left;
  - own displayed rating and its 7-day path;
  - own price, unit cost and the cheap-supply unit cost;
  - own units and revenue over the last 7 days;
  - share of own visitors who inspected before buying (last 7 days);
  - catch notices seen in the market and own catches (last 7 days);
  - same-category rivals' displayed ratings and prices;
  - licensing terms.

  Nothing hidden goes in. Store the hidden variables (tourist share, detect_scale, prior_n, inspector placement) separately for analysis.
- **Lotteries.** For each state × option, run K continuations with common random numbers (the same k streams for every option). Record per option: remaining profit to day 30, mean, sd, 5th/50th/95th percentiles, P(payoff below honest on the same k), P(caught at least once), and the full payoff vector.
- **Stability.** Choose K by split-half in the pilot: the best option by mean must agree between halves in ≥ 90% of states, excluding close calls. Start at K = 20 and report agreement at 10, 20 and 30.
- **Labels per state:** the best option; whether any switch or cheap-licence option beats honest (with the paired-difference interval); the close-call flag.
- **Gate G4b:** report the share of candidate states where switching or cheap licensing pays, by market. If it is under 20% overall, STOP and propose a market change; do not force it.
- **Time:** may span two nights, each ≤ 10 h, batched by market.

CHECKPOINT C4 at the night-1 launch; C5 when the bank is complete.

### 3C. Robustness sweep (`analysis/robustness_1_1.py`)
Use the first 10 seeds of each original run. Re-run these headline cells under each price policy (5) × buyer choice {lexicographic, logit soft, logit sharp}:
- Verification gradient endpoints, no inspectors: the tourist share 1.0 gain and the t40|l1 gain.
- Bust-out under enforcement: the gain at t100, detect_scale 1.
- Licensing: contract against cheap joint profit (R − never), t40.
- Canal Street: the PK1 slope and PK3 rating damage (t100, ds 1).
- Brand equity under stars: E at t40, prior_n 0 and prior_n 400.

**Predictions:**
- PX1 (confirmatory): in every policy × choice cell, the bust-out gain under enforcement is < 0.
- PX2 (confirmatory): in every cell, the tourist-only gain without inspectors exceeds the t40|l1 gain.
- PX3 (confirmatory): in every cell, contract licensing's joint gain exceeds cheap licensing's.
- PX4 (confirmatory): under logit sharp with rating_indexed, Canal Street's PK1 slope (the gap over 1 − φ) is > 0.
- PX5 (exploratory): every other estimate, with sign and verdict changes against 1.0.0 flagged. This includes whether E at prior_n 400 stays positive under each price policy.

**Time:** ≤ 10 h. If over, trim in this order: drop `promo`, then `match_rival`, then `logit soft`. Decide from the pilot timing, before launch.

CHECKPOINT C6 with `runs/REPORT_2026-11.md`. Then stop. The LLM battery is not part of this plan.

---

## Deviations

(None yet. Add dated notes here if anything in the plan has to change, with the reason.)

- **2026-11-19 (D1), "nights" are blocks, run back to back.** At Randall's instruction, "night" in this plan means a block of at most 10 h of wall clock, each usable on its own; stages and batches run back to back, not only overnight. Workers stay at 4, nice 19, so the machine remains usable. Reason: scheduling only; no design change. Every time limit in the plan (7 h, 10 h) applies as written.
- **2026-11-19 (D2), every queue runs under `caffeinate -i`.** This prevents idle sleep mid-run. Reason: scheduling only; no design change.
- **2026-11-19 (D3), the memory guard's swap test is off; the free-memory test stays on.** Since the macOS 27.2 restart the machine has no swap file, so free swap reads 0 MB, and the guard (≥ 512 MB free swap) would pause every chain forever. Runs pass `--min-swap-mb 0` and keep the free-memory guard (≥ 15% free); this was first used, and its reproduction checks recorded, in `runs/pilot_stars.md`. The guard only pauses new chains, so it cannot change a result. Reason: machine setup only; no design change.
- **2026-11-19 (D4), Stage 1's G3 timing gate waived; full design.** The Stage 1 pilot projected 12.3 h for the full design and 7.18 h after both trims, over the 7 h limit (`runs/pilot_check_vs_read.md`). Randall (15:55): "Ignore the timing gate. Just keep running." The main run uses the full prespecified design (20 seeds, 350–369; outcome B at prior_n 0 and 400), with no trims. Per D1 it runs as two back-to-back blocks of 10 seeds (350–359, then 360–369; about 6.1 h each), each usable on its own; a final pass analyses all 20 seeds from the cache. Decided from the pilot's timing alone, before any main-run result. Reason: scheduling only; no change to the design, seeds, predictions or analysis.
- **2026-11-20 (D5), Stage 2 steps 2–3 as built.** (a) The reference config is `configs/reference_1_0.json`, not `.yaml`: the engine's loader reads JSON, and adding a YAML dependency to the frozen engine would be a change for no gain. The file is the full config of the specified market, which also fixes the two settings the plan's list leaves open, from the licensing run's headline cell: tourist share 0.4 (locals and experts 0.3 each), and locals inspect. (b) Variants (`configs/reference_1_0_variants.json`) are derived from the configs each run's own builder makes, and must rebuild each of them exactly from the reference file; chain-level bust-out and licensing schedules stay with the run scripts, as before. (c) "Two seeds bit for bit" and the regression suite share one rerun (`analysis/reference_1_0.py`). For every published run since verification, it takes the first 2 seeds of the main run. For each seed it takes the first chain of every chain kind × market cell, builds every config from the reference file, and compares the result with the saved cache record field for field (timing and the engine stamp excluded). Only then are the digests written (`tests/reference/v1_0_0/digests.json`). The default pytest run checks one chain per run; `BAZAAR_FULL_REGRESSION=1`, or `python -m analysis.reference_1_0 --check`, checks all of them. Reason: engineering only; no design, seed or analysis of any run changes.
- **2026-11-20 (D6), Stage 3 runs in full; time limits and trims waived.** The state bank pilot projected 23.3 h for the 200-state bank at K 20, over the two 10 h blocks (`runs/pilot_state_bank.md`). Randall (2026-11-20): "Whatever the timing, just keep going. I want the whole thing. do not wait for me." and "I need this final validation." So (a) the bank runs all 200 states at K 20 as four back-to-back blocks of 5.5–6.4 h, one verification contrast (t40 and t100 at the same detect_scale and new-brand speed) per block, each usable on its own (D1), then the build phase (`runs/queue_state_bank.sh`); (b) the Stage 3C robustness sweep runs all 15 cells (5 price policies × 3 choice rules) with no trims, whatever its timing pilot projects. Decided from the state bank pilot's timing alone, before any bank lottery beyond the pilot and before any sweep chain other than the smoke checks. Reason: scheduling only; no change to the design, seeds, options, labels, predictions or analysis. Research gates (G4b, guards, the sweep's built-in checks) and bug stops still apply.
- **2026-11-21 (D7, logged late), state bank close calls counted, not targeted.** The plan's 3B asks for at least 30 close calls among the 200 states. `analysis/state_bank.py` (e757d47, written before any lottery) counts close calls but does not stratify on them: a state's close-call status is known only after its lotteries are run, and the pilot found 0 of 32. This choice was made in the script's docstring at e757d47 but not entered here as a deviation at the time; it is logged now, after the bank results. Outcome: 3 close calls of 200 (`runs/state_bank_summary.md`), far below the target. Reason: the target cannot be reached by sampling on observables in these markets, where one option (the contract licence) dominates; meeting it would need a different market or option set, which the plan's G4b clause reserves for Randall.
