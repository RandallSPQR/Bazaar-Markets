# Baseline manifest: engine 1.2.0 (additions to the 1.0.0 baseline)

**BLUF.** This file adds the rule-based results obtained after engine 1.0.0 to the baseline in `runs/BASELINE_1_0_0.md`, whose rows, status key and conventions all still apply. It has 12 new rows:
- **Robustness sweep (1.1.0).** PX1–PX3 are confirmatory and supported in all 15 price-policy × buyer-choice cells; PX4 is contradicted.
- **Price-war study (1.2.0).** PW1–PW4 are confirmatory and supported; PW5 is exploratory.
- **Datasets.** The two seller state banks, v1 (1.1.0) and v2 (1.2.0), are datasets for agent evaluation, with descriptive findings only.

So the release adds 7 confirmatory rows supported, 1 confirmatory row contradicted and 4 exploratory or descriptive rows. Engine 1.2.0 reproduces 1.0.0 at its defaults (`runs/tests_120.log`), so the 1.0.0 rows stand unchanged.

Every number is copied from the run summary named in its row. Intervals are 95% t-intervals over seeds, unadjusted. Money is in dollars. Abbreviations as in `runs/BASELINE_1_0_0.md` (t40, t100, l1, ds), plus: RI = rating_indexed price policy; U0, U0.1, U0.3 = undercut with floor markup m 0, 0.1, 0.3; lex = lexicographic choice; sharp = logit choice, w 20.

## 7. Engine 1.1.0 and 1.2.0 results

### 7.1 Robustness sweep (engine 1.1.0, plan 2026-11-19 Stage 3C)

5 price policies × 3 buyer-choice rules (lexicographic, logit w 5, logit w 20) = 15 cells, the first 10 seeds of each original run, 11,100 chains, 0 flags, guards 0. The base cell reproduces the saved 1.0.0 stars chains (650 of 650 identical).

| ID | Claim | Run file | Engine | Commit (run record; results) | Estimate | Status | Note |
|---|---|---|---|---|---|---|---|
| X1 | In every cell, the bust-out gain under enforcement is < 0 (PX1). | `robustness_1_1_summary.md` | 1.1.0 | 8d2bfe9; ae7ea9d | 15 of 15 cells below 0; −285 to −459 | Confirmatory, supported | Robustness for README headline 2 and rows V10–V13. |
| X2 | In every cell, the tourists-only gain without inspectors exceeds the t40\|l1 gain (PX2). | `robustness_1_1_summary.md` | 1.1.0 | 8d2bfe9; ae7ea9d | 15 of 15; +243 to +1,034 | Confirmatory, supported | Robustness for README headline 1. Under `undercut` the t40\|l1 gain is itself positive (+169 to +198); see P1. |
| X3 | In every cell, contract licensing's joint gain exceeds cheap licensing's at t40 (PX3). | `robustness_1_1_summary.md` | 1.1.0 | 8d2bfe9; ae7ea9d | 15 of 15; +15,111 to +27,641 | Confirmatory, supported | Robustness for B19–B21. |
| X4 | Under logit sharp with rating_indexed, Canal Street's PK1 slope is > 0 (PX4). | `robustness_1_1_summary.md` | 1.1.0 | 8d2bfe9; ae7ea9d | −5,358 [−5,607, −5,108]; every cell −3,461 to −5,605 | Confirmatory, contradicted | Smooth price response does not rescue undercutting with counterfeits: the margin given up outweighs the share won. |

### 7.2 Price-war study (engine 1.2.0, plan 2026-11-23 Stage 2)

Undercut with a floor markup m above unit cost (`sellers.undercut_floor_markup`, new in 1.2.0) against rating_indexed. Outcome A is the bust-out gain at t40 with locals inspecting. Outcome B is brand equity E at prior_n 400. Seeds 500–519, paired. 3,440 chains, guards 0. G2: m = 0 reproduces the 1.1.0 undercut chains (60 of 60).

| ID | Claim | Run file | Engine | Commit (chains; tables) | Estimate [95% CI] | Status | Note |
|---|---|---|---|---|---|---|---|
| P1 | Undercut m = 0, ds 0: the bust-out gain is > 0 (PW1). | `price_war_summary.md` | 1.2.0 | 030e7cb; db0abba | +227.47 [+174.75, +280.20] | Confirmatory, supported | Replicates on fresh seeds the sweep's exploratory +169 to +198. Under RI the same cell loses (−85). |
| P2 | ds 0: the slope of the gain over m ∈ {0, 0.1, 0.3} is < 0 (PW2). | `price_war_summary.md` | 1.2.0 | 030e7cb; db0abba | −775.07 [−942.20, −607.94] per unit of m | Confirmatory, supported | Gain at U0.1 +52, at U0.3 −25. |
| P3 | The slope of E over m is > 0 (PW3). | `price_war_summary.md` | 1.2.0 | 030e7cb; db0abba | +11,825.51 [+8,644.22, +15,006.79] per unit of m | Confirmatory, supported | E +0.88 [−0.55, +2.30] at U0; +1,185 at U0.1; +3,549 at U0.3; +3,992 under RI. |
| P4 | Undercut m = 0, ds 1: the bust-out gain is < 0 (PW4). | `price_war_summary.md` | 1.2.0 | 030e7cb; db0abba | −327.37 [−406.06, −248.68] | Confirmatory, supported | Enforcement still works in a price war; under RI the same cell is −518. |
| P5 | Exploratory comparisons: U0 − RI, buyers, logit sharp (PW5). | `price_war_summary.md` | 1.2.0 | 030e7cb; db0abba | U0 − RI gain, ds 0: +312.36 [+243.71, +381.02]; ds 1: +190.17 [+132.33, +248.02]; E: −3,990.86 [−4,891.16, −3,090.57]; buyers +27 to +31 surplus per buyer in never chains; sharp − lex −10.38 [−20.72, −0.05] | Exploratory | 21 paired differences; some intervals excluding 0 are expected by chance. D4: the as-run PW5 tables had reversed signs (fixed and regenerated from the cache; as-run files kept in `runs/price_war_as_run/`). |

### 7.3 Seller state banks (datasets)

Each bank is a set of seller decision states with simulated lotteries over options, for evaluating agents. Neither bank had prespecified predictions; their rows are descriptive.

| ID | Claim | Run file | Engine | Commit | Estimate | Status | Note |
|---|---|---|---|---|---|---|---|
| S1 | Bank v1: 200 states, 8 markets; deception pays in every tourists-only state and in 4 of 114 states where locals inspect (each within noise). | `state_bank_summary.md` | 1.1.0 | 1455315, 7d1395c; d75e3f0 | Pays 90/200 (51.8% weighted); close calls 3 (target 30, D7) | Exploratory | Too easy for agent evaluation: the contract licence is best in 190 states, and every rating is 1.0. Superseded for that use by S2, not withdrawn. |
| S2 | Bank v2: 300 states, 24 markets; whether cheating pays depends on tourist share, enforcement and owner liability together, and no single observation feature predicts it above 80%. | `state_bank_v2_summary.md` | 1.2.0 | d56a6f6 (script), a3e997e (build); 54c57c4 | Pays 107/300 (49.8% weighted); close calls 98 (target 100); 198 below a 1.0 rating; best single feature `units_7d` 75.3% | Exploratory | Always keeping supply: 50% best-option accuracy (weighted), regret $786 (37% of honest profit). 176 states come from one stratum (prespecified allocation, kept by Randall). |

### 7.4 README headlines after 1.2.0

| README headline (as reworded at 1.2.0) | Rows | Supported as worded? |
|---|---|---|
| Verification sets the boundary: a cash-in gains when no buyer checks and loses once enough buyers check (about a third in this market, exploratory). | V6–V9, V16, K1, K2, X2 | Yes as worded. The direction is confirmatory, and "about a third" is labelled exploratory. Holds across 15 price × choice cells (X2), but not in a price war at unit cost (P1). |
| Enforcement substitutes for verification, and raises honest sellers' profit, likely by closing deceptive stalls. | V10–V13, X1, P4 | Yes as worded: "likely" marks the untested mechanism (V12). Holds in every sweep cell (X1) and in a price war (P4). |
| A reputation is worth the head start it gives over rivals still building theirs, where buyers read ratings (provisional). | R17–R20, K3, K4, P3 | Yes as worded (K3, K4). In a price war at unit cost E is about 0 (P3). The provisional label is still open (section 6, item 5 of the 1.0.0 manifest). |

Section 6 of the 1.0.0 manifest keeps its open questions. Items 5 and 6 (headlines 5 and 2) are addressed by the 1.2.0 wording above, pending Randall's review.
