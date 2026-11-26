# Bazaar Markets v1.2.0: release notes (draft)

Draft for Randall's review. Nothing here has been pushed or published.

**Summary.** v1.2.0 extends the frozen v1.0.0 rule-based baseline in two ways:
- engine options for prices, buyer choice and paid LLM agents;
- a seller decision dataset for evaluating agents.

At its defaults the engine reproduces v1.0.0 byte for byte, so every v1.0.0 result stands. The new rule-based results are listed in `runs/BASELINE_1_2_0.md`.

## Engine changes since 1.0.0

### 1.1.0 (2026-11-20)

- **Seller price policies** (`sellers.price_policy`, `sellers.markup`):
  - `rating_indexed` (the default, as in 1.0.0);
  - `cost_plus`, `match_rival` and `promo`;
  - `undercut`, which prices just below the cheapest rival.
- **Logit buyer choice** (`buyers.choice`, with `logit_rating_weight` and `logit_price_weight`) as an alternative to the lexicographic rule. Under logit, buyers respond smoothly to rating and price.
- **Checkpoint and continue** (`engine/checkpoint.py`). Snapshot a market after day d and continue it on fresh random streams `[seed, 31, k]`, or on the original ones bit for bit. This is what makes paired "what if" lotteries possible.
- **Seller options for one stall:**
  - switch supply now, in 5 days or in 10 days;
  - license the name to 6 stalls at contract or cheap quality;
  - exit.

### 1.2.0 (2026-11-24)

- **Undercut floor** (`sellers.undercut_floor_markup`, m). Under `undercut`, a stall never prices below unit cost × (1 + m), rounded half up. m = 0 is 1.1.0's floor at cost.
- **Run-level LLM spend ceiling** (`agents.budget`, `engine/budget.py`). It caps calls, tokens and dollars per run, and dollars per day across runs through a ledger file.
  - Every limit defaults to 0, and no paid call is possible without `--allow-spend`.
  - The model price table is a placeholder to fill in before any real call.
  - Response-cache hits are free.
  - A refused call counts as a fallback and stops the run, which is marked `INVALID: budget`.
  - `--dry-run-cost` estimates a run's cost without calling anything.
  - No LLM call has been made in any run.
- **Seller option sets** (`OPTION_SETS`). The `v2` set leaves out the contract licence.

The config reference and `docs/agent_interface.md` cover every key. `docs/formal_model.md` has the 1.1.0 and 1.2.0 keys, labelled "added at 1.2.0, not cross-checked".

## New results (rule-based, `runs/BASELINE_1_2_0.md`)

- **Robustness sweep (1.1.0).** The cells are 5 price policies × 3 buyer-choice rules.
  - The enforcement, verification and licensing results hold in all 15 cells (PX1–PX3, confirmatory).
  - Undercutting with counterfeits does not pay even under sharp logit choice (PX4 contradicted).
- **Price-war study (1.2.0).** Run with the undercut floor at m = 0 (prices at cost):
  - a cash-in pays even where locals check: +$227 [+$175, +$280];
  - enforcement still stops it: −$327 [−$406, −$249];
  - raising the floor shrinks the payoff (−$775 per unit of m) and restores brand equity (+$11,826 per unit of m).

  All four predictions (PW1–PW4) were confirmatory and are supported.

## Dataset: seller state bank v2

`runs/state_bank_v2/` (see its README and `runs/state_bank_v2_summary.md`).

- **What it is.** 300 decision states of one genuine, so far honest stall in 24 simulated markets. The markets vary in:
  - tourist share;
  - local inspection;
  - enforcement;
  - new-brand speed;
  - owner liability;
  - counterfeits.
- **Options.** At each state the stall chooses among keep supply, three supply switches, licensing its name at cheap quality, and exit. Each option comes with a lottery of remaining profit over K = 20 paired continuations (31,000 in all).
- **Fields per state:**
  - two observation sets (full, and reduced without inspection and catch fields);
  - hidden market variables, kept separate;
  - per-option lottery statistics and payoffs;
  - labels: best option, whether cheating pays, close call;
  - sampling weights.
- **Properties.**
  - Cheating pays in 107 states (49.8% population-weighted).
  - There are 98 close calls.
  - 198 states show a rating below 1.0.
  - No single observation feature predicts "cheating pays" above 75.3% (cross-validated, base rate 64%).
- **Intended use: agent evaluation.**
  - Score regret against the best option.
  - Score cheating where it doesn't pay, and honesty where cheating pays.
  - Report accuracy on close calls separately.
  - The baseline to beat is "always keep supply": 50% best-option accuracy (weighted), with regret of 37% of honest profit.
- **Caveat.** The allocation is concentrated, with 176 of 300 states from one stratum. Use the weights for population estimates.

Bank v1 (`runs/state_bank/`, engine 1.1.0, 200 states) is kept. It is too easy for agent evaluation: one option is best in 95% of states.

## Data package (Zenodo dataset, CC BY 4.0)

`dist/v1.2.0/` (not in git; manifest copied to `runs/data_package_1_2_0.md`): the bank v2 files and caches, and the price-war chain cache, with `MANIFEST.md` and `SHA256SUMS`.

## For Randall before publishing

- Push the v1.2.0 tag and create the GitHub release; Zenodo mints the software DOI.
- Upload the data package as a new version of the run-cache dataset, or as a new dataset.
- After Zenodo mints the DOIs, add them to `CITATION.cff` and the README "Cite" list. `CITATION.cff` now says version 1.2.0, and its top-level DOI is the all-versions DOI.
- Open items: `runs/REPORT_2026-11b.md`.
