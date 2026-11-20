# Baseline manifest: engine 1.0.0

**BLUF.** This file lists every finding from the rule-based runs in `runs/`, one row each: the claim, the run file, the engine and commit it ran at, the headline estimate with its interval, and its status. Engine 1.0.0 freezes these results as the baseline that later agents (LLM or otherwise) are compared against. Of 96 rows, 29 are confirmatory and supported, 3 confirmatory and contradicted, 3 confirmatory and not supported, 1 confirmatory and partly supported, 35 exploratory, 19 provisional and 6 superseded. The superseded rows are the verification Stage B run at engine 0.13.0 (trapped-buyer bug) and the exact-rating Brand Equity speed run (replaced by the stars run). The provisional rows are the walk-mode brand, counterfeit, dilemma-boundary and capture runs. The Stage 1 run (checking vs reading ratings, engine 0.21.0) is section 5 (rows K1–K8).

Every number is copied from the run summary named in its row. Intervals are 95% t-intervals over seeds, unadjusted, unless a row says bootstrap. Money is in dollars. "Not reported" means the summary gives no such number.

## 1. Status key

| Status | Meaning |
|---|---|
| Confirmatory, supported | Prespecified as confirmatory; the interval is on the predicted side of 0. |
| Confirmatory, contradicted | Prespecified as confirmatory; the interval is on the opposite side of 0. |
| Confirmatory, not supported | Prespecified as confirmatory; the interval includes 0. |
| Confirmatory, partly supported | Prespecified as confirmatory with two conditions, one met (grid refinement PB2 only). |
| Exploratory | No prediction, or a prediction labelled exploratory, or written after the results. Any verdict is in the note. |
| Provisional | From a run whose summary carries the note "Provisional: demand design flaw (most stalls unreachable) and an unexplained bust-out loss size" (added 2026-11-08), or the walk-mode counterfeit run. The original verdict is in the note. Not to be cited as a baseline result. |
| Superseded | Replaced by a later run. The replacing row is named in the note. Not to be cited. |

"Stars:" in a note gives the result of `runs/stars_sensitivity_summary.md` (engine 0.20.0, 10 seeds per study, stars at step 0.02 with random tie-breaks, paired against the exact-rating chains). Only 13 endpoints were rechecked there. No other row has been rechecked under stars.

Commits are the rewritten hashes (2026-11-19 author-email change). Each row gives the commit named in the summary's run record, mapped through `docs/commit_map.tsv`. The old hashes, and the commits that recorded each result, are in the commit table at the end of section 3.

Abbreviations: t40 = tourist share 0.4; t70 = 0.7; t100 = tourists only; l1 / l0 = locals inspect / do not; ds = `detect_scale`; E = earshot (recognition rows) or the reputation effect (Brand Equity rows); pts = percentage points.

## 2. How to read a row

- **Claim**: what the run tested or found, in one sentence. For a prediction, the claim is the prediction, and the status says whether it held.
- **Estimate**: the summary's primary statistic for that claim. For bust-out runs that is the unfloored gain unless the row says floored.
- A row is a finding of this stylized model with rule-based agents, not a claim about real markets.

## 3. Findings

### 3.1 Verification and enforcement

| ID | Claim | Run file | Engine | Commit | Estimate [95% CI] | Status | Note |
|---|---|---|---|---|---|---|---|
| V1 | Patrolling inspectors beat fixed posts on all four primary outcomes, at 2 and at 6 inspectors (2a). | `placement_sweep_summary.md` | 0.2.0 | 1d08533 | Deceptive profit per stall, patrolling − posts, default arm: count 2 −182.03 [−205.83, −158.22]; count 6 −311.65 [−339.41, −283.88] | Confirmatory, supported | All 8 confirmatory intervals exclude 0 in both detection arms. Closest: surplus at count 2, +2.95 [+1.39, +4.52]. No predictions table; verdicts are in the reading. |
| V2 | Fixed posts leave pockets: with 2 inspectors on posts most deceptive stalls are never caught. | `placement_sweep_summary.md` | 0.2.0 | 1d08533 | Deceptive stalls never caught (of 15): posts_2 11.6 [11.1, 12.2]; patrolling_2 0.3 [0.1, 0.5] | Exploratory | The displacement test's trigger was never met. |
| V3 | Whether disguised inspectors beat posts depends on the detection assumption (2b). | `placement_sweep_summary.md` | 0.2.0 | 1d08533 | Disguised_6 − posts_6, deceptive profit: default arm −73.25 [−103.44, −43.05]; equal-detection arm +45.73 [+10.67, +80.79] | Exploratory | Not equal effort: disguised inspectors are active 80 and 246 ticks against 480 and 1440. |
| V4 | The placement result survives a grid twice as fine (k = 2) (PB1). | `grid_refinement_summary.md` | 0.5.0 | a2e77ad | Patrolling − posts: deceptive profit −162 [−186, −139]; shortfall −7.0 [−10.2, −3.8] pts | Confirmatory, supported | Naive sellers, 2 inspectors. |
| V5 | With buyers who compare two stalls (k = 2), patrolling still beats posts in a single-day bazaar (PR). | `search_counterfeit_summary.md` | 0.10.0 | c73abb3 | Deceptive profit −183.45 [−206.59, −160.31]; shortfall −7.8 [−10.7, −4.9] pts | Provisional | Confirmatory, supported. The file carries the provisional note, though PR is the single-day robustness check (see section 6). |
| V6 | With no inspectors and locals inspecting, the bust-out gain rises with the tourist share (PV1). | `verification_summary.md` (Stage A) | 0.13.0 | 5a0a5ec | +112.71 [+87.65, +137.77] per +0.1 of tourist share | Confirmatory, supported | Stage A has no closures, so the trapped-buyer bug could not occur. Floored: +94.16 [+72.21, +116.10], supported. Stars, on the t40 locals-inspect cell PV1 uses: change −11.65 [−33.73, +10.43], no verdict change. |
| V7 | At tourist share 0.4, switching local inspection off raises the bust-out gain (PV2). | `verification_summary.md` (Stage A) | 0.13.0 | 5a0a5ec | +112.38 [+72.39, +152.37] | Confirmatory, supported | The gain goes from −110.99 [−147.32, −74.66] to +1.39 [−26.05, +28.83]. |
| V8 | In a tourist-only market with no inspectors, busting out pays (PV3). | `verification_summary.md` (Stage A) | 0.13.0 | 5a0a5ec | +565.27 [+433.55, +697.00] per stall over 30 days | Confirmatory, supported | A lower bound: day 20, the earliest candidate, is best in 45 of 60 stall-seeds. Stars: +491.51 exact against +466.72 stars on 10 seeds, change −24.79 [−155.67, +106.09], verdict unchanged. |
| V9 | Without inspectors, the mean bust-out gain crosses 0 at a verifying share of about a third. | `verification_summary.md` (Stage A) | 0.13.0 | 5a0a5ec | About 0.34 (linear interpolation between 0.30 and 0.60); interval not reported | Exploratory | At a verifying share of 0.30 the two conditions give +1.39 [−26.05, +28.83] and +36.61 [−16.42, +89.64]. A loss is shown only at 0.60. |
| V10 | Two patrolling inspectors turn the tourist-only bust-out gain negative (PV4, Stage B − Stage A). | `verification_summary.md` (Stage B rerun) | 0.13.0 (A) / 0.14.0 (B) | 5a0a5ec / 3527b16 | −1,001.02 [−1,212.14, −789.89] | Confirmatory, supported | Replaces V17. Stars: change −12.93 [−139.25, +113.40], still supported. |
| V11 | Under enforcement a bust-out loses in every verification condition, and the verification gradient nearly vanishes. | `verification_summary.md` (Stage B rerun) | 0.14.0 | 3527b16 | Gains −435.74 [−536.62, −334.87] (t100) to −493.75 [−605.59, −381.92] (t40\|l1); slope over tourist share (PV1b) +9.67 [+2.69, +16.65] per +0.1 | Exploratory | Floored gain $0 everywhere. PV3b contradicted. Stars: PV3b change −37.72 [−117.12, +41.68], still contradicted. |
| V12 | Two patrolling inspectors raise an honest stall's never-bust profit in every verification condition. | `verification_summary.md`; `bugfix_trapped_buyers.md` | 0.13.0 (A) / 0.14.0 (B) | 5a0a5ec / 3527b16 | Stage B − Stage A: +429 [313, 545] (t40\|l1) to +2,737 [2,137, 3,338] (t100) | Exploratory | Computed by `analysis/never_profit_0140.py`. The mechanism (closures send buyers to genuine stalls) is called likely and is not decomposed. Replaces V18. |
| V13 | Raising enforcement intensity lowers the tourist-only bust-out gain (PL1). | `liability_summary.md` | 0.15.0 | 320b1bb | −963.90 [−1,189.56, −738.24] per 1.0 of detect_scale | Confirmatory, supported | Collectible fines. Three levels only (0.3 dropped at the pilot's G3). Crossing near 0.60 by interpolation, not located. Stars, two-level analogue: −1,112.13 exact, −1,053.84 stars, change +58.28 [−121.78, +238.34], still supported. |
| V14 | At full enforcement, judgment-proof sellers gain more from a bust-out than collectible ones (PL2). | `liability_summary.md` | 0.15.0 | 320b1bb | +91.90 [+45.92, +137.88] | Confirmatory, supported | Unfloored (primary). Floored +5.39 [−4.31, +15.09], not supported. The judgment-proof arm bundles a 3-day fine lag with mandatory exit. |
| V15 | Judgment-proof sellers profit from a bust-out at full enforcement (PL3). | `liability_summary.md` | 0.15.0 | 320b1bb | −297.14 [−389.92, −204.36] | Confirmatory, contradicted | The loss is closure plus exit (V16). Where locals inspect, the gain is negative at every intensity in both arms. |
| V16 | Where locals inspect, a bust-out loses mainly because inspecting buyers walk away; under full enforcement it loses to closures and fines. | `bustout_decomposition.md` | 0.15.0 (replay) | a7083aa | t40, locals inspect, collectible, ds 0: lost to inspection −131.93 [−165.81, −98.04]. t100, collectible, ds 1: closed after a catch −136.46 [−178.80, −94.12]; fines −277.80 [−343.42, −212.18] | Exploratory | Exact split; identity holds to the cent in 720 stall-seeds. Stars: lost to inspection −166.94 exact, −161.22 stars, change +5.72 [−46.29, +57.73]. The decomposed candidate's gain changes label: −122.41 [−159.87, −84.94] exact, −173.50 [−349.61, +2.61] stars (interval below 0 → includes 0). |
| V17 | Stage B at engine 0.13.0: two patrolling inspectors turn the tourist-only bust-out gain negative (PV4). | `verification_summary.md` (appendix "Superseded") | 0.13.0 | 1187b50 | −942.17 [−1,147.28, −737.06] | Superseded | Trapped-buyer bug. Replaced by V10 and V11. |
| V18 | At engine 0.13.0, inspectors appeared to cut the honest stall's never-bust profit where locals and experts are present. | `verification_summary.md` (appendix "Superseded") | 0.13.0 | 1187b50 | Never-bust total, t40\|l1: Stage A 4,651.82 [3,527.84, 5,775.81]; Stage B 3,255.11 [2,454.17, 4,056.04] | Superseded | The trapped-buyer bug (X1). Replaced by V12. |

### 3.2 Deception tactics: adaptive sellers and catch notices

| ID | Claim | Run file | Engine | Commit | Estimate [95% CI] | Status | Note |
|---|---|---|---|---|---|---|---|
| D1 | Sellers who hide from visible uniforms erase patrolling's advantage over posts (P1). | `visibility_adaptivity_summary.md` | 0.3.0 | d7f8828 | Interaction I, deceptive profit: +198.35 [+172.65, +224.05] (2 inspectors), +308.78 [+283.00, +334.57] (6); reachable shortfall +14.8 [+10.7, +18.9], +14.9 [+10.9, +18.9] pts | Confirmatory, supported | The adaptive seller is a perfect-avoidance positive control, so this is an upper bound. At count 2 the advantage reverses: patrolling − posts +16.32 [+6.24, +26.40]. Analysis script uncommitted at run time. |
| D2 | Visible enforcement deters without catching anyone. | `visibility_adaptivity_summary.md` | 0.3.0 | d7f8828 | Adaptive sellers, 2 uniformed posts: 0 catches; reachable shortfall 19.1 [14.6, 23.6]% against 30.2 [24.4, 36.0]% with no inspectors | Exploratory | Adaptive sellers are never caught in any uniformed cell. |
| D3 | Disguised inspectors lose less to adaptive sellers than uniformed patrols do (P2). | `visibility_adaptivity_summary.md` | 0.3.0 | d7f8828 | J, deceptive profit: −181.52 [−202.08, −160.96] (2), −326.37 [−344.31, −308.44] (6) | Exploratory | Prediction supported at both counts. |
| D4 | Patrolling's advantage shrinks as the range at which sellers recognise a uniform grows (P1). | `recognition_sweep_summary.md` | 0.4.0 | 18fcbf3 | Slope per unit r/E, deceptive profit +169.65 [+145.51, +193.79] (2), +140.49 [+114.17, +166.82] (6); shortfall +27.7 [+21.6, +33.8], +19.3 [+14.5, +24.0] pts | Confirmatory, supported | The reading calls the response a staircase, not a slope. Erratum: eight inspector-stall distances, not nine. |
| D5 | Patrolling stops beating posts at about half earshot on shortfall and three-quarters on profit. | `recognition_sweep_summary.md` | 0.4.0 | 18fcbf3 | Crossover at 2 inspectors (bootstrap): shortfall 0.50E [0.46E, 0.58E]; deceptive profit 0.71E [0.65E, 0.85E] | Exploratory | Interpolated between grid levels; read as "between ½E and ¾E". |
| D6 | At equal effort, full-shift disguised inspectors beat uniformed patrolling against adaptive sellers (P2). | `recognition_sweep_summary.md` | 0.4.0 | 18fcbf3 | Deceptive profit, disguised − patrolling: −147.17 [−164.33, −130.02] (2), −181.49 [−195.99, −167.00] (6) | Exploratory | Prediction supported at both counts. |
| D7 | Catch notices alone let adaptive sellers earn more while deceiving less (P3). | `recognition_sweep_summary.md` | 0.4.0 | 18fcbf3 | Adaptive (r = 0) − naive, deceptive profit: +11.06 [+3.67, +18.45] (posts, 2) to +256.15 [+241.80, +270.50] (patrolling, 6); shortfall −2.9 [−4.3, −1.4] to −11.3 [−14.0, −8.5] pts | Exploratory | No direction predicted. |
| D8 | The crossover moves with the whisper range (PB2). | `grid_refinement_summary.md` | 0.5.0 | a2e77ad | Shortfall crossover, whisper ¾E − ½E: +0.223, bootstrap [+0.197, +0.241] | Confirmatory, partly supported | The interval excludes 0 as predicted but not +0.25. The reading attributes the gap to interpolation across a step. |
| D9 | A finer grid smooths the recognition dose curve (PB3). | `grid_refinement_summary.md` | 0.5.0 | a2e77ad | Largest single step, share of the profit curve's change: 0.76 (k = 2) against 0.33 (k = 1); difference +0.43 [+0.29, +0.46] | Exploratory | Not borne out: the finer grid sharpens the step. |
| D10 | Adaptive sellers' extra profit is avoided penalties, not better selling. | `profit_decomposition.md` | 0.4.0 | 3a3e4f9 | Penalty share of the profit difference 1.04 to 1.40 in all 6 cells; e.g. patrolling 6: 1.04 [1.01, 1.07]; posts 2: 1.40 [1.05, 2.79] (bootstrap) | Confirmatory, supported | Prespecified as a descriptive prediction (more than half from penalties); see section 6. Revenue falls in every cell. |
| D11 | Over 30 days, catch notices pull stalls into deception at posts (PC1). | `entry_exit_summary.md` | 0.6.0 | ec24f90 | Late deceptive share, adaptive − naive: −0.3 [−1.1, +0.6] pts | Confirmatory, not supported | A deceiver still earns less than the genuine stall next to it. |
| D12 | Over 30 days, adaptive sellers' shortfall advantage shrinks at posts (PC2). | `entry_exit_summary.md` | 0.6.0 | ec24f90 | Change −0.6 [−2.5, +1.2] pts | Confirmatory, not supported | Day 1 gap −2.9 [−4.3, −1.4]; days 26–30 −3.5 [−5.0, −1.9]. |
| D13 | Under mobile inspectors, adaptive sellers' shortfall advantage shrinks over time, mostly because naive markets improve (PC3). | `entry_exit_summary.md` | 0.6.0 | ec24f90 | Change in the gap: patrolling +4.3 [+1.4, +7.2], disguised +5.4 [+1.7, +9.1] pts | Exploratory | Late deceptive shares are mutation-selection balances (about 60% of switches are mutations). |

### 3.3 Brands, licensing and counterfeits

| ID | Claim | Run file | Engine | Commit | Estimate [95% CI] | Status | Note |
|---|---|---|---|---|---|---|---|
| B1 | Look-alike reopeners earn more than fresh-name reopeners (PE1). | `brand_summary.md` | 0.8.0 | 02f4967 | −83.00 [−89.19, −76.81] per deceptive stall per day | Provisional | Confirmatory, contradicted. Budgets at 1.0 × base: task completion near 0 (a floor). |
| B2 | The look-alike gap grows with the tourist share (PE2). | `brand_summary.md` | 0.8.0 | 02f4967 | −14.07 [−16.45, −11.68] per +0.2 of tourist share | Provisional | Confirmatory, contradicted. |
| B3 | Look-alikes lower the copied brand's rating (PE3). | `brand_summary.md` | 0.8.0 | 02f4967 | −0.192 [−0.217, −0.166] | Provisional | Confirmatory, supported. |
| B4 | Look-alikes bring rational originals' bust-outs forward (PE4). | `brand_summary.md` | 0.8.0 | 02f4967 | −4.81 [−5.69, −3.94] days | Provisional | Confirmatory, supported. The rational rule ignores penalties. |
| B5 | With budgets at 1.25 × base, the look-alike profit penalty mostly goes away. | `brand_budget125_summary.md` | 0.8.0 | 02f4967 | PE1 contrast −8.25 [−17.70, +1.19] | Provisional | Exploratory throughout. PE3 analogue −0.255 [−0.306, −0.203]. |
| B6 | No buyer count from 150 to 1,000 gets 80% of genuine brands rated by day 10: entrance capture, not thin demand. | `counterfeit_summary.md` | 0.9.0 | d6488e7 | 67.8% to 70.0% rated at every count (target 80%); interval not reported | Provisional | Calibration failed; the main run was not made, so PF1–PF4 were untested here. The diagnostic is exploratory. The file has no provisional note (section 6). |
| B7 | The counterfeit − fresh profit gap rises with buyers' budgets (PF1). | `search_counterfeit_summary.md` | 0.10.0 | c73abb3 | +16.66 [+14.70, +18.63] per +0.1 of budget factor | Provisional | Confirmatory, supported. A step between 1.1× and 1.25×, not a trend. Search depth k* = 2 (82.6% rated). |
| B8 | Counterfeiting pays at budget 1.5 × base (PF2). | `search_counterfeit_summary.md` | 0.10.0 | c73abb3 | −10.72 [−19.78, −1.67] per stall per day | Provisional | Confirmatory, contradicted. |
| B9 | A penalty-aware bust-out rule (v2) beats the penalty-blind one (v1) for genuine sellers (PF3). | `search_counterfeit_summary.md` | 0.10.0 | c73abb3 | +164.48 [+149.88, +179.09] per day | Provisional | Confirmatory, supported. |
| B10 | Counterfeits bring v2's bust-outs forward (PF4). | `search_counterfeit_summary.md` | 0.10.0 | c73abb3 | −0.15 [−0.33, +0.02] days | Provisional | Confirmatory, not supported. |
| B11 | Is honesty irrational? v2 against always-honest. | `search_counterfeit_summary.md` | 0.10.0 | c73abb3 | −17.04 [−26.09, −7.98] per day (fresh reopening) | Provisional | Prespecified two-sided question; interval below 0, so always-honest earns more. |
| B12 | With no inspectors, v2 bust-outs beat honesty (PG1). | `dilemma_boundary_summary.md` | 0.10.0 | 5a76fde | −138.31 [−147.16, −129.47] per stall per day | Provisional | Confirmatory, contradicted. The run carries the provisional note. |
| B13 | The v2 − honest gap falls as inspectors are added (PG2). | `dilemma_boundary_summary.md` | 0.10.0 | 5a76fde | +20.49 [+18.74, +22.24] per inspector | Provisional | Confirmatory, contradicted. The gap reaches 0 at 4–6 inspectors because v2 stops busting out. |
| B14 | Slower-moving ratings (higher memory λ) make a bust-out more profitable (PS1, capture Stage A). | `capture_summary.md` | 0.11.0 | 2f41abc | +16.59 [−0.60, +33.78] per +0.1 of λ | Provisional | Confirmatory, not supported. 29 of 45 sampled stall-seeds never sell from day 10. |
| B15 | More tourists make a bust-out more profitable (PS2). | `capture_summary.md` | 0.11.0 | 2f41abc | +387.95 [+105.60, +670.30] | Provisional | Confirmatory, supported (unfloored). Floored +45.58 [−3.73, +94.89], not supported. |
| B16 | Critics' ties make a bust-out more profitable (PK1, capture Stage B). | `capture_summary.md` | 0.11.0 | 23fa417 | −0.02 [−1.00, +0.97] per +0.1 of tie share | Provisional | Confirmatory, not supported. |
| B17 | A bust-out pays at tie share 0.6 (PK2). | `capture_summary.md` | 0.11.0 | 23fa417 | −1,555.51 [−2,090.22, −1,020.80] | Provisional | Confirmatory, contradicted. |
| B18 | Inspector capture makes a bust-out more profitable (PK3). | `capture_summary.md` | 0.11.0 | 23fa417 | +424.46 [+181.79, +667.14] | Provisional | Confirmatory, supported. A bust-out still loses about $1,133 with capture. |
| B19 | Licensing the brand to cheap licensees pays the owner in a tourist-only market with enforcement (PX1). | `licensing_summary.md` | 0.16.0 | 88ceb7d | +3,439.59 [+2,789.73, +4,089.46] over 30 days | Confirmatory, supported | Royalty 0.15. Licensee participation is not modelled: with licensee consent this cell's gain is +0.00 [+0.00, +0.00], 60 of 60 owners having no accepted option (`licensing_checks.md`). |
| B20 | That licensing gain beats the best bust-out in the same market (PX2). | `licensing_summary.md` | 0.16.0 | 88ceb7d | +3,861.74 [+3,153.24, +4,570.24] | Confirmatory, supported | |
| B21 | Making the owner liable for licensees' fines removes the gain (PX3). | `licensing_summary.md` | 0.16.0 | 88ceb7d | Liable − not liable −8,754.90 [−10,063.08, −7,446.71] | Confirmatory, supported | At detect_scale 0 liability is inert (+0.00). |
| B22 | Cheap licensees earn the owner more than contract (honest) licensees (PC-cheap). | `licensing_summary.md` | 0.16.0 | 88ceb7d | Cheap − contract, t100, ds 1: −3,026.84 [−3,744.98, −2,308.69] | Exploratory | Contradicted: renting the reputation intact pays more. Contract licensees run in two cells only. |
| B23 | With licensee consent, at royalty 0.10 only contract licensing pays the owner. | `licensing_checks.md` | 0.16.0 (replay) | 7cbfc31 | Contract, consent only: +3,442.72 [+2,768.04, +4,117.41] (t40), +3,804.07 [+2,997.56, +4,610.59] (t100); cheap with enforcement: +0.00 [+0.00, +0.00] (60 of 60 owners have no accepted option) | Exploratory | Royalty enters no decision, so rates are exact recomputes. Stars: t40 contract +3,388.00 exact, +3,137.77 stars, change −250.23 [−713.64, +213.18], unchanged. |
| B24 | Counterfeits that undercut the original gain more the lower their price (PK1). | `canal_street_summary.md` | 0.17.0 | de58171 | Slope of the gap over (1 − φ), t100, ds 1: −5,812.24 [−5,958.99, −5,665.50] | Confirmatory, contradicted | The buyer rule ranks by rating, then price, so any φ < 1 wins the same buyers. |
| B25 | A counterfeit at the original's price loses (PK2). | `canal_street_summary.md` | 0.17.0 | de58171 | Gap at φ 1.0, t100, ds 1: −369.83 [−457.80, −281.86] | Confirmatory, supported | Pays only without enforcement. Stars: change −68.56 [−290.23, +153.12], still supported. |
| B26 | Counterfeits lower the copied original's rating (PK3). | `canal_street_summary.md` | 0.17.0 | de58171 | Day-30 rating, on − off, φ 0.6: −0.379 [−0.393, −0.365] | Confirmatory, supported | Stars: change +0.004 [−0.003, +0.011], still supported. |
| B27 | Locals inspecting shrinks the counterfeit gap (PK4). | `canal_street_summary.md` | 0.17.0 | de58171 | Supported in 1 of 8 cells (ds 0, φ 1.0: −294.76 [−353.20, −236.32]) | Exploratory | Contradicted in 7 cells by the signed criterion; smaller in magnitude at t40 in all 8. |
| B28 | The original gains from a full-price copy and loses from a cheaper one (PK5). | `canal_street_summary.md` | 0.17.0 | de58171 | Original's 30-day profit, on − off, t100, ds 1: φ 1.0 +350.98 [+172.76, +529.20]; φ 0.4 −775.52 [−950.23, −600.81] | Exploratory | No direction predicted. |

### 3.4 Reputation and brand equity

| ID | Claim | Run file | Engine | Commit | Estimate [95% CI] | Status | Note |
|---|---|---|---|---|---|---|---|
| R1 | Public ratings raise the late genuine share of stalls (PD1). | `reputation_summary.md` | 0.7.0 | b3a0c18 | +2.3 [+0.6, +4.0] pts | Confirmatory, supported | Shortfall falls 10.6 [8.2, 12.9] pts. Ratings act mainly through buyers. Walk mode, no inspectors. |
| R2 | Ratings raise the genuine share more when whispers are banned (PD2, genuine share). | `reputation_summary.md` | 0.7.0 | b3a0c18 | Interaction +1.3 [−0.2, +2.9] pts | Confirmatory, not supported | |
| R3 | Ratings cut shortfall more when whispers are banned (PD2, shortfall). | `reputation_summary.md` | 0.7.0 | b3a0c18 | Interaction −7.2 [−10.0, −4.5] pts | Confirmatory, supported | Mechanism is a rule-buyer choice: a whisper prompts a local to inspect. |
| R4 | A switching cost into honesty changes the genuine share (PD3). | `reputation_summary.md` | 0.7.0 | b3a0c18 | −0.4 to +0.1 pts; all intervals include 0 | Exploratory | The cost hits only the first day's profit. |
| R5 | A licensee earns more under the owner's name than under a white label (name effect, contract, t40) (PQ1). | `brand_equity_summary.md` | 0.17.0 | de58171 | +14,818.74 [+11,923.40, +17,714.07] per owner, days 10–30 | Confirmatory, supported | Most of it is the white label's stall-type price tier, not reputation (R9). |
| R6 | The name effect is larger where buyers read ratings (PQ2). | `brand_equity_summary.md` | 0.17.0 | de58171 | t40 − t100: −459.83 [−634.25, −285.42] | Confirmatory, contradicted | |
| R7 | Renting a reputation earns more than spending it (PQ3). | `brand_equity_summary.md` | 0.17.0 | de58171 | Contract − cheap, t40: +12,319.39 [+9,755.81, +14,882.97] | Confirmatory, supported | |
| R8 | With tourists only, the name effect is ≤ 0 (PQ4). | `brand_equity_summary.md` | 0.17.0 | de58171 | +15,278.57 [+12,256.37, +18,300.78] | Exploratory | Contradicted. |
| R9 | Once a white label may price like the owner, the owner's reputation earns far less than the stall-type price tier (PR2). | `brand_equity_tier_summary.md` | 0.18.0 | dcac770 | Reputation − tier effect, contract, t40: −14,323.27 [−17,102.62, −11,543.92] | Confirmatory, supported | Reputation effect +247.73 [+172.03, +323.44]; tier effect +14,571.00 [+11,734.08, +17,407.93]. |
| R10 | The reputation effect rises with the time new brands take to earn a rating (PR1). | `brand_equity_tier_summary.md` | 0.18.0 | dcac770 | +284.00 [+231.68, +336.32] per day to 0.9 | Confirmatory, supported | Fitted over two speeds, not three (5-day level cut at the pilot). Exact ratings; the prior slows every brand, the owner's included. Not rechecked under stars (section 6). |
| R11 | At the slow speed, the reputation effect is larger where buyers read ratings (PR3). | `brand_equity_tier_summary.md` | 0.18.0 | dcac770 | t40 − t100: +19,197.49 [+15,822.69, +22,572.30] | Exploratory | Supported in sign; about three quarters is the t100 loss, not the stated mechanism. |
| R12 | The owner's licensing gain rises with time to reputation (PR4). | `brand_equity_tier_summary.md` | 0.18.0 | dcac770 | t40 +19.03 [+0.63, +37.44]; t100 −266.06 [−317.23, −214.89] per day | Exploratory | Supported at t40, contradicted at t100. |
| R13 | With exact ratings over 60 days, the reputation effect rises with time to reputation (PS1). | `brand_equity_speed_summary.md` | 0.19.0 | eb84a43 | +276.95 [+124.37, +429.54] per day | Superseded | Was confirmatory, supported. Driven by new brands rated 0.999 losing to 1.0. Replaced by R17. |
| R14 | More than half of the effect is earned before white labels catch up (PS2). | `brand_equity_speed_summary.md` | 0.19.0 | eb84a43 | +359.07 [−265.74, +983.87] | Superseded | Was confirmatory, not supported. Replaced by R18. |
| R15 | At the current speed the effect is under 10% of the slowest speed's (PS3). | `brand_equity_speed_summary.md` | 0.19.0 | eb84a43 | +450.70 [+156.45, +744.94] | Superseded | Was confirmatory, supported. Replaced by R17–R19. |
| R16 | With tourists only, slow ratings favour white labels (PS5). | `brand_equity_speed_summary.md` | 0.19.0 | eb84a43 | E at t100: −9,961.77 [−13,004.44, −6,919.11] (d5) to −8,904.76 [−12,700.55, −5,108.97] (d20) | Superseded | Was exploratory. Replaced by R20. |
| R17 | Under star ratings, the reputation effect rises with the time new brands take to earn a rating (PT1). | `brand_equity_stars_summary.md` | 0.20.0 | 174cc5e | +192.57 [+153.20, +231.93] per day to 0.9 (t40) | Confirmatory, supported | E +246.70, +1,148.39, +1,547.47, +4,039.98 at 1.0, 6.4, 10.4, 20.8 days. Stars and random tie-breaks change together. |
| R18 | Under stars, more than half of the effect is earned before white labels display the owner's rating (PT2). | `brand_equity_stars_summary.md` | 0.20.0 | 174cc5e | Before − after, prior_n 400, t40: +4,039.98 [+3,214.47, +4,865.48] | Confirmatory, supported | Share before: 1.00. |
| R19 | Under stars, the effect after the displayed catch-up is under 20% of the total (PT3). | `brand_equity_stars_summary.md` | 0.20.0 | 174cc5e | 20% of E − E after, prior_n 10, t40: +310.44 [+225.02, +395.86] | Confirmatory, supported | E after −0.95 [−2.91, +1.02]. |
| R20 | With tourists only, slow ratings favour white labels under stars too (PT4). | `brand_equity_stars_summary.md` | 0.20.0 | 174cc5e | E at t100: d5 −4,482.32 [−5,317.16, −3,647.49]; d10 −4,725.12 [−5,620.34, −3,829.89]; d20 −3,522.70 [−4,205.89, −2,839.51]; current +91.93 [+51.90, +131.96] | Exploratory | About half the exact-rating size. |
| R21 | A coarser star display (half stars) shrinks the effect at the slow speed (PT5). | `brand_equity_stars_summary.md` | 0.20.0 | 174cc5e | Step 0.1 − step 0.02, d10: t40 −260.37 [−414.87, −105.86]; t100 +2,346.67 [+1,900.28, +2,793.07] | Exploratory | Exactly 0 at the current speed. |
| R22 | Licensees prefer a white label to the owner's name at every speed under stars. | `brand_equity_stars_summary.md` | 0.20.0 | 174cc5e | R − W_g per licensee, t40, royalty 0.05: current −807.67 [−958.93, −656.40]; d20 −172.34 [−220.31, −124.37] | Exploratory | Every interval in the table is below 0. |
| R23 | The owner gains from licensing its brand at every speed under stars. | `brand_equity_stars_summary.md` | 0.20.0 | 174cc5e | Owner's gain under R at 0.10, current speed: t40 +7,460.04 [+6,013.09, +8,907.00]; t100 +8,694.91 [+7,052.90, +10,336.93] | Exploratory | White labels cost the owner money in every cell. |

### 3.5 Diagnostics and calibration

| ID | Claim | Run file | Engine | Commit | Estimate [95% CI] | Status | Note |
|---|---|---|---|---|---|---|---|
| X1 | An engine bug trapped choice-set buyers whose set held a closed stall; it explains all of the apparent drop in honest profit under inspectors. | `honest_profit_diagnostic.md` | 0.13.0 | a950141 | t40, locals inspect: bug loss 1,721.1 [1,316.4, 2,125.7] against a drop of 1,396.7 [1,048.2, 1,745.2] (ratio 1.23) | Exploratory | A first-order bound computed on the bugged 0.13.0 chains, not a counterfactual run. Led to the 0.14.0 fix (X2) and the Stage B rerun (V10–V12). |
| X2 | The 0.14.0 fix changes only the trapped and parked cells, and the guard reads 0. | `bugfix_trapped_buyers.md` | 0.14.0 | 2eb4b42 | 68 of 86 reference cells reproduce 0.13.0 byte for byte; 18 change on purpose; guard 0 in all 86; full suite 752 passed, 17 skipped | Exploratory | Engine check, no interval. Choice-set pilot P2/P3 rechecked at 0.14.0: both pass. |
| X3 | The trapped-buyer bug was not possible in any earlier committed run; parked buyers are rare. | `certification_stuck.md` | each run's own (0.2.0–0.13.0) | 1c8dbc8 | Parked share of buyer-days: 0.012% (search/counterfeit), 0.064% (dilemma boundary), 0.038% (capture B), 0 in the other six | Exploratory | Search/counterfeit had 2 stuck buyer-days of 243,900, which met the stop rule; the PI waived it as negligible. No earlier run was rerun. |
| X4 | Rating-speed levels for the tier run (prior on every brand). | `calibration_rating_speed.md` | 0.18.0 | 093f582 | prior_n 0, 2.5, 50 → 1.04, 4.78, 14.91 days to 0.9 (t40) | Exploratory | Calibration, pilot seeds 900–902. The 2.5 level was cut at the tier pilot's timing gate. |
| X5 | Rating-speed levels for the speed and stars runs (prior on new brands only). | `calibration_brand_equity_speed.md` | 0.19.0 | e26fb11 | prior_n 0, 3.5, 10, 400 → 1.044, 6.356, 10.378, 20.756 days to 0.9 (t40) | Exploratory | Calibration, seeds 900–904. No level near 5 days passed the spread rule. Still in use: the stars run (R17–R23) uses these x values. |
| X6 | Earlier headline results do not move under star ratings. | `stars_sensitivity_summary.md` | 0.20.0 | 174cc5e | 13 endpoints in 5 studies: 0 sign changes, 0 verdict changes, every paired difference's interval includes 0; 1 descriptive label change | Exploratory | 10 seeds per study (the first ten of each). Covers V6, V8, V10, V11, V13, V16, B23, B25, B26. |

### 3.6 README headlines and their rows

| README headline | Rows | Supported as worded? |
|---|---|---|
| Verification sets the boundary for cashing in a brand: with no inspectors, busting out gains when no buyer checks and loses once about a third do. | V6–V9, V16 | Partly. The direction is confirmatory (PV1–PV3). "About a third" is the exploratory interpolated crossing (about 0.34, no interval). At a verifying share of 0.30 the gain is not distinguishable from 0; a loss is shown only at 0.60. |
| Enforcement substitutes for verification, and raises honest sellers' profit by closing deceptive stalls. | V10–V13 | Partly. Substitution is confirmatory (PV4, PL1). The rise in honest profit is exploratory (V12), and "by closing deceptive stalls" is the summary's likely mechanism, explicitly not decomposed. |
| Enforcement leaks through gaps in space and time: fixed inspectors leave pockets; visible patrols get waited out. | V1, V2, D1, D2, D4–D6 | Yes. Pockets are descriptive (V2). "Waited out" rests on a perfect-avoidance seller, so it is an upper bound. |
| Catch counts mislead: sellers who dodge inspectors earn more only by paying fewer fines. | D10, D2, D7 | Yes. Penalty share 1.04 to 1.40 in all 6 cells, with revenue lower in every cell. Measured with catch notices only (r = 0). |
| A reputation is worth the head start it gives over rivals still building theirs (provisional): about $190 a day of head start, and nothing once rivals show the same stars. | R17–R20 | Only where buyers read ratings. "About $190" is PT1, +192.57 a day at t40. With tourists only (t100), slow rivals gain instead: E is −3,522.70 to −4,725.12 at the slow speeds (R20). "Nothing once rivals show the same stars" holds (R19). The summary records PT1–PT3 as confirmatory and supported; it does not call them provisional. |

### 3.7 Commit table

Old hashes are as cited in the summaries; new hashes from `docs/commit_map.tsv`. "Run record" is the commit the summary's run record names (in several runs the analysis script was uncommitted at run time, as each record states). "Results" is the commit that first added the summary or result.

| Run file | Run record, old | Run record, new | Results, new |
|---|---|---|---|
| `placement_sweep_summary.md` | 7de6491 | 1d08533 | 8da15ee |
| `visibility_adaptivity_summary.md` | c0cc5db | d7f8828 | 9a2883c |
| `recognition_sweep_summary.md` | b9c88fb | 18fcbf3 | 3a3e4f9 |
| `profit_decomposition.md` | 463af5d | 3a3e4f9 | f633984 |
| `grid_refinement_summary.md` | 43964e6 | a2e77ad | f18d0b3 |
| `entry_exit_summary.md` | e755591 | ec24f90 | 7ee47c0 |
| `reputation_summary.md` | 29ceac5 | b3a0c18 | 66a0fd6 |
| `brand_summary.md`, `brand_budget125_summary.md` | 0a22990 | 02f4967 | 9eb2292 |
| `counterfeit_summary.md` | 3342f39 | d6488e7 | 336bcd0 |
| `search_counterfeit_summary.md` | 063aee5 | c73abb3 | b8c3b4c |
| `dilemma_boundary_summary.md` | 9dd42d0 | 5a76fde | da73047 |
| `capture_summary.md`, Stage A | 690f58c | 2f41abc | 23fa417 |
| `capture_summary.md`, Stage B | 6b286fd | 23fa417 | ac056eb |
| `verification_summary.md`, Stage A | 175e042 | 5a0a5ec | 1187b50 |
| `verification_summary.md`, Stage B at 0.13.0 (superseded) | c8c0407 | 1187b50 | a950141 |
| `verification_summary.md`, Stage B rerun at 0.14.0 | 6268c3e | 3527b16 | 5a6f85f |
| `honest_profit_diagnostic.md` | 2cc1342 | a950141 | 4ca11d6 |
| `bugfix_trapped_buyers.md` (engine 0.14.0) | aff9549 | 2eb4b42 | 5a6f85f |
| `certification_stuck.md` | f0ea358 | 1c8dbc8 | 1c8dbc8 |
| `liability_summary.md` | 32fb832 | 320b1bb | a7083aa |
| `bustout_decomposition.md` | 5b60720 | a7083aa | cef7391 |
| `licensing_summary.md` | ddd6fc2 | 88ceb7d | b75044a |
| `licensing_checks.md` | 35614d1 | 7cbfc31 | da55c04 |
| `canal_street_summary.md`, `brand_equity_summary.md` | 0762786 | de58171 | 31a1a55 |
| `calibration_rating_speed.md` | 20ee303 | 093f582 | 2f3fad4 |
| `brand_equity_tier_summary.md` | 1a39d22 | dcac770 | 3e0c025 |
| `calibration_brand_equity_speed.md` | 8b7884b | e26fb11 | da1f4f3 |
| `brand_equity_speed_summary.md` | 2744a4a | eb84a43 | 81bbc91 |
| `brand_equity_stars_summary.md`, `stars_sensitivity_summary.md` | 47634b0 | 174cc5e | f66984f |

## 4. Superseded and provisional

### Superseded (6 rows)

- **Trapped-buyer bug (V17, V18).** Under choice-set demand, a buyer whose consideration set held a stall closed by a catch could end up standing at an open stall it wanted, unable to buy (`honest_profit_diagnostic.md`, fixed in engine 0.14.0). It needs choice-set demand together with closures. The certification (X3) found it could not occur in any run before verification Stage A, and Stage A had no inspectors. So the only affected published result is verification Stage B at 0.13.0: its PV4 (−942.17) and the apparent fall in honest profit under inspectors. The Stage B rerun at 0.14.0 replaces both (V10, V11, V12). The choice-set pilot's P2/P3 checks were also exposed; they are a pilot, not findings, and pass again at 0.14.0 (`pilot_recheck_0140.md`).
- **Exact-rating Brand Equity speed (R13–R16).** At engine 0.19.0, buyers who read ratings compared them unrounded. A new brand under the prior stays just below 1.0 for the whole run while day-1 brands sit at exactly 1.0, so rating readers never treated a caught-up white label as equal. Most of the slow-speed effect at t40 came from that edge case. The stars run (R17–R23) repeats the design with ratings displayed at a tenth of a star and random tie-breaks. Its t40 effect after the white labels display the owner's rating is about $0, and the t100 effect is about half the exact-rating size.

### Provisional (19 rows)

- **Walk-mode brand and counterfeit runs (V5, B1–B11).** `brand_summary.md`, `brand_budget125_summary.md` and `search_counterfeit_summary.md` carry the note "Provisional: demand design flaw (most stalls unreachable) and an unexplained bust-out loss size; see the redesign run" (added 2026-11-08). In walk mode buyers enter an aisle at one end and stop at the first acceptable stall, so mid-aisle stalls are rarely reached. `counterfeit_summary.md` found this (B6) and is marked provisional here as the walk-mode counterfeit run, though its file has no such note.
- **Dilemma boundary and capture (B12–B18).** Same walk-mode market, same note in both files. They are marked provisional here for consistency with their own banners.
- The redesign is the choice-set market used from the verification run onward (V6–V16, B19–B28, R5–R23).

### Waivers and cuts recorded in pilots and deviations

| Run | What was waived or cut | Source |
|---|---|---|
| Verification | G1 failed (seconds stalls 0.88 customers a day against 1.0); waived by the PI. 20 seeds instead of 30 under the G4 timing rule. | `verification_summary.md`, Deviations |
| Search / counterfeit | Stop rule (stuck buyers > 0) met by 2 of 243,900 buyer-days; waived as negligible. | `certification_stuck.md` |
| Liability | detect_scale 0.3 dropped at G3 (11.7 h projected against 10 h). | `liability_summary.md` |
| Brand Equity tier | The 5-day speed level cut at the timing gate; PR1 and PR4 fitted over two levels. | `brand_equity_tier_summary.md` |
| Stars (Runs A and B) | G3 cut waived by the user: full design, step 0.1 cells on, Run B 10 seeds per study. | `pilot_stars.md` |
| Counterfeit | Calibration failed; the user chose to stop and report. | `counterfeit_summary.md` |
| Stage 1 (checking vs reading) | G3 failed (7.18 h after both trims, limit 7 h); waived by Randall as deviation D4. | `pilot_check_vs_read.md`, `STATUS.md` |

## 5. Stage 1: checking vs reading ratings (engine 0.21.0)

Locals both inspect and read ratings, so earlier runs could not say which behaviour stops bust-outs and which pays for reputation. This run separates them with `buyers.profile_overrides`: tourist share 0.4, the other 0.6 locals, reads_ratings {yes, no} × inspect_prob {1.0, 0}, plus a tourists-only reference cell. Outcome A is the bust-out gain (verification benchmark, detect_scale 0 and 1); outcome B is the reputation effect E (stars, contract, prior_scope new, 60 days, prior_n 0 and 400). Seeds 350–369, paired; 5,000 chains in two blocks (4dd5c2d, 9cb3e67, identical code); G3 waived (D4). Main effects average over the other factor; both outcomes have an interaction about as large as the smaller main effect.

| ID | Claim | Run file | Engine | Commit | Estimate [95% CI] | Status | Note |
|---|---|---|---|---|---|---|---|
| K1 | Without inspectors, locals' inspection lowers the bust-out gain (PC1). | `check_vs_read_summary.md` | 0.21.0 | 4dd5c2d, 9cb3e67 | Main effect of inspection, ds 0: −364.05 [−479.15, −248.94] | Confirmatory, supported | Gain +466.61 when locals neither read nor inspect, −20.27 when they only inspect, +165.42 when they only read. |
| K2 | For the bust-out gain, reading ratings matters less than inspection (PC2). | `check_vs_read_summary.md` | 0.21.0 | 4dd5c2d, 9cb3e67 | \|inspection\| − \|reading\|, ds 0: +185.69 [+121.68, +249.71] | Confirmatory, supported | Reading's main effect −178.35 [−235.01, −121.70]; interaction +245.66 [+157.28, +334.05]. |
| K3 | Locals reading ratings raises the reputation effect (PC3). | `check_vs_read_summary.md` | 0.21.0 | 4dd5c2d, 9cb3e67 | Main effect of reading on E, prior_n 400: +9,987.06 [+7,410.85, +12,563.27] | Confirmatory, supported | E is negative wherever locals do not read (−6,020.85 inspecting, −4,077.21 neither = tourists only). |
| K4 | For the reputation effect, inspection matters less than reading (PC4). | `check_vs_read_summary.md` | 0.21.0 | 4dd5c2d, 9cb3e67 | \|reading\| − \|inspection\|, prior_n 400: +5,902.60 [+4,439.89, +7,365.30] | Confirmatory, supported | Inspection lowers E: main effect −4,084.47 [−5,214.36, −2,954.58]; interaction −4,281.65 [−5,417.73, −3,145.57]. |
| K5 | With inspectors (ds 1), buyer behaviour adds little to the bust-out loss (PC5). | `check_vs_read_summary.md` | 0.21.0 | 4dd5c2d, 9cb3e67 | Inspection −49.34 [−97.42, −1.25]; \|inspection\| − \|reading\| +43.78 [−3.00, +90.56] | Exploratory | Every cell loses (−356.46 to −411.35); the PC2 analogue is not supported. |
| K6 | At prior_n 0 the reputation pattern holds at about a thirtieth of the size (PC5). | `check_vs_read_summary.md` | 0.21.0 | 4dd5c2d, 9cb3e67 | Reading +262.29 [+195.94, +328.64]; \|reading\| − \|inspection\| +108.19 [+69.62, +146.77] | Exploratory | Inspection −154.10 [−197.25, −110.95]; interaction −196.88 [−243.21, −150.54]. |
| K7 | Locals' checking protects locals, not tourists (PC6). | `check_vs_read_summary.md` | 0.21.0 | 4dd5c2d, 9cb3e67 | Tourists' shortfall share, ds 0: 0.613 in every cell (RI 0.613 [0.606, 0.620]); deceptive share of units: neither 0.654 [0.649, 0.659], both 0.296 [0.292, 0.301] | Exploratory | Enforcement does reach tourists: at ds 1 their shortfall share is about 0.28 in every cell. |
| K8 | Where locals only read, a bust-out loses through ranking and the price premium, not the rating threshold (PC6). | `check_vs_read_summary.md` | 0.21.0 | 4dd5c2d, 9cb3e67 | Rn: outranked −30.76 [−41.96, −19.56]; premium −44.27 [−61.18, −27.35]; rating below threshold −1.86 [−5.64, +1.91] | Exploratory | Where locals inspect, the loss is buyers who inspected and walked away (RI −114.86 [−159.17, −70.54]). |

Bearing on the README: K1 and K2 say the verification boundary (headline 1) is set by inspection rather than by reading ratings. K3 and K4 say the reputation effect (headline 5) depends on buyers reading ratings, and shrinks where they inspect.

## 6. Open questions

1. **Brand Equity tier speed rows (R10–R12).** These are also exact-rating speed results, at 0.18.0 with the prior on every brand and a 30-day horizon. The spec names only `brand_equity_speed_summary.md` as superseded, so R10–R12 keep their recorded status. They were not rechecked under stars. Should they also be marked superseded?
2. **Scope of "provisional".** The spec names the walk-mode brand and counterfeit runs. Dilemma boundary and capture carry the same banner, so they are marked provisional too. `counterfeit_summary.md` has no banner but is marked provisional as the walk-mode counterfeit run. The earlier walk-mode runs (placement, visibility, recognition, grid, entry/exit, reputation) carry no banner and keep their status, though the placement summary notes that about 40% of buyers never come within reach of a stall. Is that the intended line?
3. **V5 (search-depth PR).** A confirmatory, single-day robustness check inside a provisional file. It is marked provisional with the file. It may not share the multi-day flaw.
4. **No predictions table.** `placement_sweep_summary.md`, `visibility_adaptivity_summary.md` and `recognition_sweep_summary.md` give verdicts in a reading or verdicts table, not a predictions table. `profit_decomposition.md` calls its prespecified prediction "descriptive"; D10 records it as confirmatory and supported. `stars_sensitivity_summary.md`, `bustout_decomposition.md`, `licensing_checks.md` and `honest_profit_diagnostic.md` have no predictions and are exploratory throughout.
5. **README headline 5 status.** The README calls the reputation head-start finding provisional. Its source rows (R17–R19) are confirmatory and supported. Which label should 1.0.0 use? The headline also holds only where buyers read ratings (section 3.6).
6. **README headline 2 mechanism.** "By closing deceptive stalls" is untested (V12). Reword, or decompose it before the freeze?
7. **Licensing PX1–PX3 (B19–B21).** Supported as specified, but with licensee consent the PX1 cell's gain is 0 (`licensing_checks.md`). Should B19 carry a stronger qualifier?
8. **Brand Equity PQ1/PQ3 (R5, R7).** Supported as specified, but R9 shows the name effect is mostly the price tier. They keep "confirmatory, supported" with a note.
9. **Status vocabulary.** The spec's status list has no "not supported" or "partly supported". Rows D11, D12, R2 (interval includes 0) and D8 (grid PB2) use those two added labels.
10. **Commit choice.** Rows give the run-record commit. For verification Stage A it is 175e042 → 5a0a5ec, the pilot-gate commit, and for Canal Street and Brand Equity it is 0762786 → de58171, the pilot-outputs commit. The results commits are in section 3.7.
11. **Engine stamps.** Verification Stage A ran at 0.13.0, but its plot footers name 0.14.0 (recorded in its Deviations). The manifest uses 0.13.0.
