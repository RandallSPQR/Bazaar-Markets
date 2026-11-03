# Config reference

Configs are JSON. Any field can be overridden on the command line with
`--set dotted.key=value`, where the value is parsed as JSON when possible, e.g.
`--set inspectors.count=6 --set 'stalls.type_shares={"genuine":0.5,"seconds":0.5}'`.
Nested sections merge with the defaults, except share tables (`type_shares`,
`profile_shares`), which are replaced whole. Share tables are read in sorted
key order, so key order never changes a run.

Source of truth: `engine/config.py`. Full default configs:
`configs/bazaar_default.json`, `configs/m0_baseline.json`, `configs/m0_redraw.json`.

**Status labels**
- **PLACEHOLDER**: a research decision, given a labelled default on 2026-11-03. Revisit.
- **calibration**: set so the default sample run is not degenerate. Not a research claim.
- **prototype**: copied from sim.py.

## Mode `m0`

| key | default | status | meaning |
|---|---|---|---|
| `seed` | 0 | | RNG seed (the replication unit) |
| `n_cust`, `n_adv` | 1000, 100 | prototype | customers, advertisers |
| `f_enf` | 0.05 | prototype | enforcer rate |
| `r_min`, `r_max` | 0.02, 0.7 | prototype | targeting radius bounds (log-uniform initial draw) |
| `d_sale` | 0.1 | prototype | sale happens if the winner is within this distance |
| `m`, `delta`, `P` | 1.0, 0.2, 5.0 | prototype | margin, deceptive margin premium, penalty |
| `gens` | 250 | prototype | generations |
| `T` | null (= 20·n_adv) | prototype | impressions per generation |
| `keep`, `flip` | 0.2, 0.02 | prototype | selection share, type-flip probability |
| `cap_mult` | 3.0 | prototype | budget cap = cap_mult × fair share per generation |
| `enforcer_mode` | `fixed` | | `fixed` = fixed enforcer customers (sim.py); `redraw` = enforcer status drawn per impression from a separate stream (reconstruction; tighten.py unavailable) |
| `summary_last` | 30 | prototype | generations averaged for the headline (221–250) |

## Mode `bazaar`

### `market`
| key | default | status | meaning |
|---|---|---|---|
| `categories` | fish, electronics, designer | | one aisle per category |
| `slots_per_side`, `slot_spacing` | 8, 2 | | stalls per aisle side, spacing in cells (48 stalls) |
| `clustering` | 1.0 | | 0 = similar sellers scattered, 1 = one aisle per category; fixed per run |
| `ticks` | 240 | | |
| `sight_range` / `earshot` / `whisper_range` / `interact_range` | 3 / 4 / 2 / 1 | | channel ranges in grid cells |
| `max_actions_per_stop` | 4 | | stall actions a buyer may take at one stop before the engine moves it on |

### `stalls`
| key | default | status | meaning |
|---|---|---|---|
| `type_shares` | genuine .4, seconds .3, deceptive .3 | | exact per-category counts (largest remainder) |
| `q_high` | [0.70, 0.95] | | genuine true Q; deceptive claimed Q |
| `q_low` | [0.15, 0.45] | | seconds and deceptive true Q |
| `deceptive_sign` | `pitch` | | what a deceptive stall's sign shows |

Q_req (`buyers.q_req`, [0.50, 0.70]) is kept between the low and high ranges,
so genuine always meets the requirement and low-Q never does. The zero-deception
sanity check depends on this separation.

### `pricing` (integer cents; engine-set; agents cannot change)
| key | default | status | meaning |
|---|---|---|---|
| `base_price_cents` | fish 800, electronics 4000, designer 12000 | | genuine posted price; also the "price of genuine Q_req" that budgets refer to |
| `seconds_price_factor` | 0.55 | | seconds are posted and priced as seconds |
| `deceptive_price_factor` | 1.0 | | deceptive stalls price like genuine; < 1 models "bargain" fakes |
| `unit_cost` | [0.30, 0.50] | | unit cost = base × (c0 + c1·Q_true) |
| `yell_cost_frac`, `whisper_cost_frac` | 0.002, 0.004 | calibration | ad spend per yell / whisper, as a fraction of base |
| `penalty_mult` | 1.5 | | P = 1.5 × base ≈ 5× a genuine unit margin (M0's P/m = 5) |
| `close_ticks` | 40 | | closure after a catch |

### `buyers`
| key | default | status | meaning |
|---|---|---|---|
| `count` | 150 | | arrivals spread evenly over the run |
| `profile_shares` | tourist .4, local .4, expert .2 | | |
| `units`, `q_req` | [1, 2], [0.50, 0.70] | | task: acquire X units with Q ≥ Q_req |
| `budget_level` | `at` | | `above` / `at` / `below` / `mixed`: budget = units × base × factor |
| `budget_factors` | 1.25 / 1.0 / 0.8 | | |
| `inspect_cost_frac` | tourist .10, local .05, expert .02 | | inspection cost, as a fraction of base, paid from the budget |
| `aisles_per_route` | [1, 3] | | |
| `profile_noise` | 0.3 | | chance a seller sees a random profile instead of the observable one (stable per seller–person pair) |
| `inspector_fraction` | 0.0 | | share of buyers who are also inspectors (1.0 for the "every buyer an inspector" check) |

### `inspectors`
| key | default | status | meaning |
|---|---|---|---|
| `count` | 2 | calibration | |
| `placement` | `posts` | calibration | `posts` (spread across aisles), `clustered` (all in one aisle), `patrolling` (serpentine loop), `disguised` (walk buyer routes, ask stalls) |
| `disguised_ask_prob` | 0.3 | | chance a disguised inspector asks a stall it passes |
| `feature_correlation` | **0.0** | **PLACEHOLDER** | ρ: with probability ρ an inspector shows as `expert`; otherwise its observable profile comes from the buyer distribution. 0 = no pockets in feature space. |

### `detection`
| key | default | status | meaning |
|---|---|---|---|
| `form` | **`graded`** | **PLACEHOLDER** | `graded`: p = w_ch · prox(d) · min(1, falsity / f_scale). `step`: p = w_ch · prox(d) for any falsity > 0. `hazard`: p = 1 − exp(−k · falsity · w_ch · e^(−d/λ)) |
| `channel_weight` | whisper 1.0, answer 1.0, yell 0.6, sign 0.4 | PLACEHOLDER | private channels reach an inspector only when the inspector is the recipient |
| `f_scale` | 0.3 | PLACEHOLDER | |
| `hazard_k`, `hazard_lam` | 6.0, 2.0 | | |

prox(d) = max(0, 1 − d / channel range) for sign and yell; 1 for whisper and
answer. Falsity = max(0, claimed Q − true Q). True claims are never caught. A
sign is perceived once per person per stall "epoch" (it is perceived again
after the stall reopens).

### `valuation`
| key | default | status | meaning |
|---|---|---|---|
| `form` | **`step_salvage`** | **PLACEHOLDER** | V = V_req if Q ≥ Q_req, else salvage · V_req · Q / Q_req. `linear`: V_req · Q / Q_req. `concave`: V_req · √(Q / Q_req) |
| `value_mult` | 1.3 | PLACEHOLDER | V_req = value_mult × base |
| `salvage` | 0.5 | PLACEHOLDER | |

### `agents`
| key | default | meaning |
|---|---|---|
| `seller` | genuine/seconds → `rule_honest`, deceptive → `rule_deceptive` | |
| `buyer` | `rule_buyer` | also `random_buyer` (floor), `perfect_buyer` (ceiling), `llm` (stub) |
| `params` | {} | per-policy keyword arguments, e.g. `{"rule_deceptive": {"cautious": false}}`, `{"llm": {"model_id": "...", "sampling": {...}, "max_calls": 0}}` |

Policies: `agents/registry.py`.
