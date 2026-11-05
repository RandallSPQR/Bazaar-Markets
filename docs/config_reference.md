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
| `cap_mult` | 3.0 | prototype | impression cap (not a money budget) = int(cap_mult × T / n_adv) impressions per advertiser per generation, reset each generation |
| `cap_mode` | `batch` | prototype | `batch`: cap checked once per batch of T/40 impressions, so a seller can overshoot within a batch (soft limit; generation events log `cap_overflow`). `strict`: enforced per impression, overflow goes to the next-highest eligible bidder |
| `selection` | `idle_lowest` | | `idle_lowest`: firms that won nothing rank below every active firm, loss-makers included (prototype v1; all doc results). `prototype_v0`: idle fitness −1e-9, so idle firms outrank loss-makers (original sim.py; historical compatibility only). Both are selection assumptions; see the doc's sensitivity table |
| `tie_break` | `stable` | | `stable`: stable sort, identical on every platform. `numpy_default`: the prototypes' sort, whose tie order varies by numpy build; needed only for bit-exact prototype comparison |
| `enforcer_mode` | `fixed` | | `fixed` = fixed enforcer customers; `redraw` = enforcer status drawn per impression from a separate stream (paired design); `redraw_main` = drawn from the main stream, exactly as tests/reference/tighten_v1.py (reproduces the doc's mechanism numbers) |
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
| `close_ticks` | 40 | | closure after a catch; also L, the window for public catch notices (`recent_catches`) |

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
| `inspector_fraction` | 0.0 | | share of buyers who are also inspectors ("inspector-buyers"; 1.0 for the "every buyer an inspector" check) |
| `inspector_knowledge` | true | | inspector-buyers see reliable quality (`own_assessment`) and their policy can use it |
| `inspector_enforcement` | true | | inspector-buyers can trigger catches; set false for knowledge without enforcement |

### `inspectors`
| key | default | status | meaning |
|---|---|---|---|
| `count` | 2 | calibration | |
| `placement` | `posts` | calibration | `posts` (spread across aisles), `clustered` (all in one aisle), `patrolling` (serpentine loop), `disguised` (walk buyer routes, ask stalls) |
| `disguised_ask_prob` | 0.3 | | chance a disguised inspector asks a stall it passes |
| `feature_correlation` | **0.0** | **PLACEHOLDER** | ρ: with probability ρ an inspector shows as `expert`; otherwise its observable profile comes from the buyer distribution. 0 = no pockets in feature space. |
| `uniformed` | false | | inspectors on `posts`, `clustered` or `patrolling` wear a visible uniform (`"uniform": true` on sellers' passerby rows). Disguised inspectors are never uniformed |
| `recognition_range` | null (= `market.earshot`) | | how far away a seller recognizes a uniform, in grid units. Uniformed inspectors farther away show `"uniform": false`, like any passer-by. 0 = never recognized |
| `disguised_shift` | `single_trip` | | `single_trip`: each disguised inspector walks one buyer-like route at a staggered arrival, then leaves (far fewer active ticks than posts). `full_shift`: present from t=0 to the end, walking random routes back to back (active ticks = count × ticks, as for posts and patrols). Full-shift routes come from inspector j's own stream `[seed, 6, 1, j]`, so buyers and other draws are unchanged |

### `detection`
| key | default | status | meaning |
|---|---|---|---|
| `form` | **`graded`** | **PLACEHOLDER** | `graded`: p = w_ch · prox(d) · min(1, falsity / f_scale). `step`: p = w_ch · prox(d) for any falsity > 0. `hazard`: p = 1 − exp(−k · falsity · w_ch · e^(−d/λ)) |
| `channel_weight` | whisper 1.0, answer 1.0, yell 0.6, sign 0.4 | PLACEHOLDER | private channels reach an inspector only when the inspector is the recipient |
| `f_scale` | 0.3 | PLACEHOLDER | |
| `hazard_k`, `hazard_lam` | 6.0, 2.0 | | |
| `proximity` | `linear` | | `linear`: prox(d) as below. `flat`: prox = 1 for every channel |

The defaults make private channels easier to detect than broadcast ones *given*
that an inspector perceives the message, so channel comparisons mix exposure
with detection. For channel claims, also run `configs/detection_equal.json`
(equal weights, flat proximity: equal detection given exposure), and compare
`inspector_active_ticks`, since disguised inspectors make one trip while posts
and patrols stay all run.

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
| `buyer` | `rule_buyer` | also `random_reference`, `informed_reference` (comparison points, not bounds; old names `random_buyer`, `perfect_buyer` still accepted), `llm` (stub) |
| `params` | {} | per-policy keyword arguments, e.g. `{"rule_deceptive": {"cautious": false}}`, `{"llm": {"model_id": "...", "sampling": {...}, "max_calls": 0}}` |

Seller policies: `rule_honest`, `rule_deceptive`, `rule_deceptive_adaptive`, `llm`. Set a
type's policy with e.g. `--set agents.seller.deceptive=rule_deceptive_adaptive`.
`rule_deceptive_adaptive` (positive control for strategic avoidance) behaves like
`rule_deceptive`, but goes quiet (no yell or whisper, truthful answers, sign set to
`truth`) while a uniformed passerby is in earshot, while `recent_catches` is non-empty,
or for `close_ticks` ticks after its own stall reopens. It then restores its sign.

Policies: `agents/registry.py`.
