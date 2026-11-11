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
| `whispers_allowed` | true | | false = a public medium: sellers can use only signs, yells and answers. Sellers see `ranges.whispers_allowed: false`; a whisper is an invalid action (fallback), so none is ever delivered. Rule sellers do not try |
| `days` | 1 | | number of days; each day a full run with fresh buyers, and type switches between days (`evolution`, below) |
| `horizon_known` | false | | 0.8.0: seller observations carry `horizon` (`day`, `days`) and `yesterday` (the stall's previous-day ledger; null on day 1) |
| `scale` | 1 | | grid refinement k (integer ≥ 1): cells 1/k as large, ticks 1/k as long; every other distance and time value stays in real units (k = 1 cells and ticks). See below |

### Grid refinement (`market.scale` = k)

Config values are in real units: a length of 1 is one cell at k = 1, a duration of 1 is one tick at k = 1. At scale k the engine builds the world at k = 1, then refines it: every coordinate × k, each one-cell route step split into k one-cell steps (a route's last cell held k ticks), every arrival tick × k. People still move one cell per tick, so real speeds are unchanged and `route_k[k·t] = k · route_1[t]`. The engine then runs on a copy of the config in which every field marked distance or time below is multiplied by k. The log header records the config as given; the `world` event's grid is the refined one. Source of truth: `engine/scaling.py`; `tests/test_scale.py` fails if a config field or agent keyword has no rule.

Two per-tick rates scale as well (decided 2026-11-05): a buyer action (ask, inspect, buy) holds the buyer k ticks, so a stop lasts as long in real time; and rule sellers' cooldowns `yell_every` and `whisper_every` are multiplied by k. Engine rates that are per event, not per tick, need no rule: a sign is perceived once per person per stall epoch, a disguised inspector asks a stall at most once per epoch, each person is whispered to at most once per seller, and detection is drawn per perceived message. Residual differences at k > 1 are the refinement itself: people pass through intermediate cells, so they enter a range at a finer distance and sellers decide on k times as many ticks.

**Multiplied by k (distance, in cells):** `market.slot_spacing`, `market.sight_range`, `market.earshot`, `market.whisper_range`, `market.interact_range`, `inspectors.recognition_range`, `detection.hazard_lam`, plus every hard-coded layout offset (aisle pitch, stall rows, corridor columns, post positions next to stalls), which scale through the coordinate refinement.

**Multiplied by k (time, in ticks):** `market.ticks`, `pricing.close_ticks` (so the closure and the catch-notice window L), arrivals, and the agent keywords `HonestSeller.yell_every`, `HonestSeller.whisper_every`.

**Not scaled:**

| key | why |
|---|---|
| `mode` | label |
| `seed` | label |
| `market.categories` | labels |
| `market.slots_per_side` | count |
| `market.clustering` | probability |
| `market.max_actions_per_stop` | a count of actions; each action holds the buyer k ticks |
| `market.scale` | the scale itself |
| `stalls.type_shares` | shares |
| `stalls.q_high` | quality |
| `stalls.q_low` | quality |
| `stalls.deceptive_sign` | label |
| `pricing.base_price_cents` | money |
| `pricing.seconds_price_factor` | ratio |
| `pricing.deceptive_price_factor` | ratio |
| `pricing.unit_cost` | money ratio |
| `pricing.yell_cost_frac` | money per yell; yells per real time are unchanged |
| `pricing.whisper_cost_frac` | money per whisper |
| `pricing.penalty_mult` | money ratio |
| `buyers.count` | count |
| `buyers.profile_shares` | shares |
| `buyers.units` | count |
| `buyers.q_req` | quality |
| `buyers.budget_level` | label |
| `buyers.budget_factors` | ratio |
| `buyers.budget_factor_override` | ratio |
| `buyers.search_depth` | count |
| `buyers.search_log` | label |
| `buyers.bargain_share` | share |
| `buyers.bargain_q_req` | quality range |
| `buyers.demand_mode` | label |
| `buyers.consider` | stalls per buyer |
| `buyers.position_rent` | per position rank |
| `buyers.inspect_cost_frac` | money ratio |
| `buyers.aisles_per_route` | count; routes are refined after they are drawn |
| `buyers.profile_noise` | probability per (stall, person) pair |
| `buyers.inspector_fraction` | share |
| `buyers.inspector_knowledge` | switch |
| `buyers.inspector_enforcement` | switch |
| `inspectors.count` | count |
| `inspectors.placement` | label; post positions are refined with the layout |
| `inspectors.disguised_ask_prob` | probability per (inspector, stall, epoch) encounter |
| `inspectors.feature_correlation` | probability |
| `inspectors.uniformed` | switch |
| `inspectors.disguised_shift` | label; full-shift routes are refined |
| `inspectors.capture` | probability per (inspector, brand) pair |
| `inspectors.capture_effect` | multiplier on catch probability |
| `critics.count`, `critics.sample` | count; critics act between days |
| `critics.weight` | rated units per review |
| `critics.tie_share` | share of pairs |
| `critics.tie_delay`, `critics.emb_max` | days; critics act between days |
| `critics.embarrassment` | switch |
| `detection.form` | label |
| `detection.proximity` | label; proximity is d / range, a ratio of two distances |
| `detection.channel_weight` | probability weights |
| `detection.f_scale` | quality |
| `detection.hazard_k` | rate per unit falsity |
| `valuation.form` | label |
| `valuation.value_mult` | ratio |
| `valuation.salvage` | ratio |
| `agents.seller` | policy names |
| `agents.buyer` | policy name |
| `agents.params` | per-policy keywords; their rules are in AGENT_PARAMS |
| agent `HonestSeller.yell_crowd` | count |
| agent `HonestSeller.whisper` | switch |
| agent `DeceptiveSeller.cautious` | switch |
| agent `RandomReferenceBuyer.p_buy` | probability per decision; decisions per stop are unchanged |
| agent `InformedReferenceBuyer.valuation` | engine-supplied |
| agent `InformedReferenceBuyer.base_price_cents` | engine-supplied |
| agent `LLMAgent.role` | label |
| agent `LLMAgent.model_id` | label |
| agent `LLMAgent.sampling` | sampling settings |
| agent `LLMAgent.provider` | label |
| agent `LLMAgent.max_retries` | count per decision |
| agent `LLMAgent.max_calls` | spend cap; note that at k > 1 sellers get k times as many decision ticks |

### `evolution` (multi-day runs only: `market.days` > 1)
| key | default | status | meaning |
|---|---|---|---|
| `revise_prob` | 0.2 | | chance a genuine or deceptive stall revises between days |
| `mutation_prob` | 0.02 | | chance a genuine or deceptive stall flips type anyway, after imitation |
| switching cost | 0 | | see `pricing.switch_cost_to_genuine` / `switch_cost_to_deceptive` (0.7.0) |

Each day is a full bazaar run. Stall locations, categories, brands and types persist; buyers,
inspectors' routes and every other engine draw are fresh, from the single-day streams on day 1
and the same streams under the prefix `[seed, 9, day]` on day ≥ 2 (so day-d buyers are identical
across conditions). Closures, catch notices, accounting, signs and seller agents reset each day.

Between day d and d + 1 (decided 2026-11-05): a revising stall compares its day-d profit with a
partner drawn uniformly from the other genuine and deceptive stalls of its category; if the
partner's type differs and it earned more, it switches with probability Δprofit / M, where M is
the largest absolute profit difference among the genuine and deceptive stalls of its category that
day. Revision is synchronous (all compare day-d types). Seconds stalls never switch and are never
partners. A stall whose type changes gets new Q_true, Q_pitch and price by the type rules. All
revision draws for stall i after day d come from its own stream `[seed, 10, d, i]` (six draws, fixed
order). Source: `engine/days.py`.

### `ratings` (multi-day runs)
| key | default | status | meaning |
|---|---|---|---|
| `mode` | `off` | | `off`: not computed. `hidden`: computed and logged, shown to no one. `public`: buyers whose profile is in `visible_to` see each stall's rating on their `stalls_here` rows (`rating`, null = unrated) |
| `memory` | **0.7** | **PLACEHOLDER** | λ: rating = λ · yesterday + (1 − λ) · today's share |
| `tau` | **0.5** | **PLACEHOLDER** | the rule buyer skips stalls rated below τ; unrated stalls are neutral (not skipped) |
| `visible_to` | expert, local | | profiles that consult the ratings board (tourists do not) |
| `rugpull_threshold` | 0.8 | | a genuine → deceptive switch while rated ≥ this is logged as a rugpull |

A day's share is computed from that day's realized purchases only: the share of units whose true
Q met the latest claim the stall made to the buyer before the sale. Units bought with no claim from
the stall are not rated. A stall's first rating is that day's share; a day with no rated units
leaves it unchanged (decided 2026-11-05). Ratings update at the end of each day, before type
revision, and persist across days and type switches (the brand keeps its name).

### `brands` (0.8.0; off by default)
| key | default | status | meaning |
|---|---|---|---|
| `enabled` | false | | ratings attach to brand names; renames at reopening; counterfeits (called look-alikes before 0.9.0); reputation premium; bust-out action. Requires `evolution.revise_prob = mutation_prob = 0` in multi-day runs |
| `premium` | 0.0 | **PLACEHOLDER** (0.4 in the 2026-11-06 run) | price = base × tier × (1 + premium × (rating − 0.5)) |

With brands on (source: `engine/brands.py`):
- **Ratings by name.** Reviews are filed by brand name and updated as in `ratings` (same share,
  blend and first-rating rule). A tourist's review of a counterfeit is filed under the original's
  name; locals' and experts' reviews under the actual name. Ratings persist with the name.
- **Renames only at reopening.** A catch sets the stall's `rename_pending`; its first decision
  after the closure ends (that day, or the next morning) may carry `"rename": "fresh" |
  "counterfeit"` (`"lookalike"`, the 0.8.0 name, is still accepted); afterwards the chance is gone until the next catch. `fresh` = a new fictional name
  (unrated). `counterfeit` = a near-copy (an accent added, two neighbouring letters swapped, or a
  letter doubled; never equal to the original or any name used before) of the highest-rated
  full-price brand (genuine or deceptive tier, not a counterfeit) on another stall of the same
  category; unrated counts as 0.5; ties uniformly at random (decided 2026-11-06). The counterfeit
  posts the original's price. Draws: `[day root, 11, stall index, rename count]`.
- **Perception.** Tourists read the original's name on a counterfeit (its `brand` on their
  `stalls_here` rows and in message texts); locals and experts read the actual name and see its
  own rating.
- **Premium.** Each morning, price = round(base × tier × (1 + premium × (r − 0.5))), r = the
  brand's start-of-day rating (0.5 if unrated), tier = 1 (genuine), `deceptive_price_factor` or
  `seconds_price_factor`; a counterfeit then takes the current price of the stall bearing the
  original's name. Unit costs do not change. A rename resets the price (fresh: neutral; counterfeit:
  the original's).
- **Bust-out.** A genuine stall that has not busted out may send `"bust_out": true` on its first
  decision of a day: its true quality drops for good to its low quality (one draw from `q_low` on
  `[seed, 12, stall index]`), its unit cost follows, and its sign shows its old quality (`pitch`);
  name and price rule are unchanged. Seller observations carry a `brand` block (`name`,
  `counterfeit_of`, `rating`, `neutral_price_cents`, `rename_available`, `first_decision_today`,
  `busted_day`, `bust_out_unit_cost_cents`).
- **Exit** (0.15.0). Any stall may send `"exit": true` (once a day): it leaves the market for good at
  the end of that day. On every later day it is closed, in no consideration set and no counterfeit
  target, and sells, spends and is fined nothing; its fines not yet due become uncollectible. Every
  outcome carries `liability`: fines charged, deferred, uncollectible and outstanding (counts and
  cents, by stall), the day's exits, and catches at deceptive-type stalls per deceptive stall;
  multi-day results add run totals (`catches_per_deceptive_stall_day`, `exited`, `by_stall`).

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
| `penalty_lag_days` | 0 | | 0.15.0: 0 = the fine is charged at the catch. L > 0: the catch still closes the stall at once, but the fine falls due L days later and is charged in the stall's accounts that day; a fine falling due after the stall has exited is uncollectible (outcome `liability`, never charged); one falling due after the last day at a stall still in the market is outstanding at close |
| `switch_cost_to_genuine`, `switch_cost_to_deceptive` | 0, 0 | | multi-day: a stall that switches type pays this fraction of its base price once, in its accounts on its first day in the new type (outcome field `switch_cost_cents` per type, shown only when either is non-zero) |

### `buyers`
| key | default | status | meaning |
|---|---|---|---|
| `count` | 150 | | arrivals spread evenly over the run |
| `profile_shares` | tourist .4, local .4, expert .2 | | |
| `units`, `q_req` | [1, 2], [0.50, 0.70] | | task: acquire X units with Q ≥ Q_req |
| `budget_level` | `at` | | `above` / `at` / `below` / `mixed`: budget = units × base × factor |
| `budget_factors` | 1.25 / 1.0 / 0.8 | | |
| `search_depth` | 1 / 1 / 1 | | 0.10.0: per-profile search depth k (see below); 1 = 0.9.0 behaviour |
| `search_log` | false | | 0.10.0: adds the outcome's `search` block (per-buyer search records, per-stall exposure) |
| `bargain_share` | null | | null = the demand mode's default (0 in `walk`, 0.11.0 bytes; 0.2 in `choice_set`, 0.12.0). 0.11.0: this share of buyers ("bargain hunters") draw Q_req from `bargain_q_req` instead of `q_req`; their `task` carries `bargain: true`. Two draws per buyer from `[day root, 16]`, consumed only when the share is > 0 |
| `bargain_q_req` | [0.30, 0.45] | | 0.11.0: bargain hunters' Q_req range |
| `demand_mode` | "walk" | | 0.12.0: `walk` = 0.11.0 (a buyer considers the stalls of its category its random route passes); `choice_set`: see below |
| `consider` | 3 | | 0.12.0, `choice_set` only: consideration-set size m (fewer if the category has fewer stalls); also the buyer's search depth |
| `position_rent` | 0.0 | | 0.12.0, `choice_set` only: gamma; set members drawn with weight exp(-gamma × position rank); 0 = uniform |
| `budget_factor_override` | null | | 0.9.0: when set, every buyer's budget = units × base × this factor, whatever `budget_level` says (the `mixed` draws are still consumed; the buyer's `task` then carries `budget_factor`) |
| `inspect_cost_frac` | tourist .10, local .05, expert .02 | | inspection cost, as a fraction of base, paid from the budget |
| `aisles_per_route` | [1, 3] | | |
| `profile_noise` | 0.3 | | chance a seller sees a random profile instead of the observable one (stable per seller–person pair) |
| `inspector_fraction` | 0.0 | | share of buyers who are also inspectors ("inspector-buyers"; 1.0 for the "every buyer an inspector" check) |
| `inspector_knowledge` | true | | inspector-buyers see reliable quality (`own_assessment`) and their policy can use it |
| `inspector_enforcement` | true | | inspector-buyers can trigger catches; set false for knowledge without enforcement |

**Search depth** (0.10.0; decided 2026-11-06). A buyer whose profile has depth k > 1 walks its
route as before, but at each stop with open stalls of its category in reach it records them as
seen and may ask and inspect; it may buy only once it has seen k stalls or is at the last cell of
its route (phase `choose`; buying in phase `browse` is invalid). Then it buys from a stall here or
sends `{"action": "choose", "stall": id}` for a stall it saw earlier: the engine walks it back (or
forward) along its route, one cell per tick, to the last cell where that stall was in reach, and
it decides there. A chosen stall that is closed on arrival is skipped for the rest of the day and
the buyer chooses again. Once in phase `choose` a buyer stays there for the rest of the day (0.14.0;
before, a buyer that reached `choose` only at its route end, with fewer than k open stalls seen, went
back to `browse` on walking back and could not buy: the trapped-buyer bug). A buyer that moves on
at the stall it chose (it learned more there, or can no longer afford it) drops the choice and walks
on along its route, choosing again where it can (0.14.0; before, it stood at that stall for the rest
of the day: the parked-buyer bug). After buying, a buyer that still needs units chooses again or browses on;
once done it walks on along its route from where it is, as today. Buyer observations carry a
`search` block (`depth`, `seen_count`, `phase`, `route_end`, `seen_elsewhere`: rows like
`stalls_here` for seen stalls not in reach, with the current price, visible rating and
`steps_away`); `buy` and `choose` may carry `candidates` (stall ids, logged as given). The rule
buyer browses as the 0.9.0 rule learns (inspecting where that rule would inspect before buying,
asking silent stalls) and in phase `choose` picks among the stalls it believes meet Q_req, pass
the rating threshold and fit its budget: highest visible rating (unrated = 0.5), then lowest price;
tourists (no ratings) lowest price; ties by stall id. With no candidate it moves on (and leaves at
the end of its route). Depths are fixed by profile, so buyer populations do not depend on them.

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
| `capture` | 0.0 | | 0.11.0 (needs `brands.enabled`): each dedicated inspector j (its order among inspectors) is tied to each genuine-origin brand (a brand on a genuine stall on day 1) with this probability, drawn once per run from `[seed, 15]` |
| `capture_effect` | 0.8 | **PLACEHOLDER** | a tied inspector's catch probability for a stall bearing that brand is multiplied by (1 − capture_effect). The detection draw is consumed as before, so draws stay aligned across capture settings |
| `detect_scale` | 1.0 | | 0.15.0, enforcement intensity: multiplies every catch probability (dedicated inspectors and inspector-buyers); 0 = inspectors present but never catch. The detection draw is consumed whenever the unscaled probability is > 0, so draws stay aligned across levels |

### `critics` (0.11.0; off by default)
| key | default | status | meaning |
|---|---|---|---|
| `count` | 0 | **PLACEHOLDER** (4 in the 2026-11-07 capture run) | number of critics; 0 = off. Needs `brands.enabled` and `ratings.mode` ≠ `off` |
| `sample` | 6 | **PLACEHOLDER** | stalls each critic visits each day (without replacement, `[day root, 13, critic]`) |
| `weight` | 5 | **PLACEHOLDER** | a filed review counts as this many rated units in that day's brand rating update |
| `tie_share` | 0.0 | | share of (critic, genuine-origin brand) pairs that are tied: round-half-up(share × pairs) pairs drawn from `[seed, 14]`, fixed for the run |
| `tie_delay` | 10 | **PLACEHOLDER** | days a tied critic holds a negative review of that brand |
| `embarrassment` | false | | when on, a negative review is also held round-half-up(`emb_max` × p) days, p = the share of that critic's earlier reviews of the brand that were positive (0 with none); the hold is the larger of the two delays |
| `emb_max` | 10 | **PLACEHOLDER** | |

Critics act at the end of each day, after trading and before the rating update. A critic observes
the true Q of each stall it visits and writes a review: positive when true Q meets the stall's
posted claim (sign `pitch` → Q_pitch, `truth` → Q_true), negative otherwise; a stall showing no
sign gets no review (decided 2026-11-07). Reviews are filed under the stall's actual name. Positive
reviews are filed at once; a review written on day d with delay k is filed at the end of day d + k
and one due after the last day is never filed. Source: `engine/critics.py`.

### `licensing` (0.16.0; off while `schedule` is empty)
| key | default | status | meaning |
|---|---|---|---|
| `schedule` | {} | | `{owner stall id: {"day": b, "n": N}}`: at the start of day b (2 ≤ b ≤ `market.days`) the genuine owner licenses its brand to N non-genuine stalls (seconds or deceptive) of its category. Needs `brands.enabled` and `market.days` > 1 |
| `quality` | "cheap" | | `cheap`: licensee true quality drawn from `stalls.q_low`, sign shows the brand's quality (`stalls.deceptive_sign`), run by `agents.seller.deceptive`'s policy. `contract`: the owner's true quality, sign `truth`, run by `rule_honest` |
| `royalty` | 0.15 | **PLACEHOLDER** | the licensee pays the owner round(royalty × price) per unit sold |
| `owner_liable` | false | | fines from catches at a licensee are charged to its owner instead (the licensee is still closed) |

Licensees are drawn from `[seed, 19, owner index]`: a permutation of the category's non-genuine stalls in
stall order (the first 2 of 6 are the 2 of 2), then one quality draw per candidate. From day b a licensee
bears the brand's name, posts the owner's price (after morning prices) and claims the owner's true quality
until the last day; it is never offered a rename after a catch (decided 2026-11-11), and its type (`stype`)
does not change. Buyers file reviews of licensee sales under the brand, so licensee sales move the brand's
rating; inspection reveals the licensee's true quality. Stall profit becomes revenue − cost − ad spend −
penalties − switch cost − royalties paid + royalties received. With a schedule the outcome adds
`licensing` (per owner: licensees, their quality, royalties, licensee and owner sales, catches at
licensees, fines by payer), `seller_by_type` adds royalty fields, and `day_start` logs the day's
licences. `benchmark.licence_config(cfg, sid, (N, b))` and `benchmark.licence_options(ns, bs, D)` build
the licensing benchmark. Source: `engine/licensing.py`.

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
| `params` | {} | per-policy keyword arguments, e.g. `{"rule_deceptive": {"cautious": false}}`, `{"llm": {"model_id": "...", "sampling": {...}, "max_calls": 0}}`. Rule sellers (`rule_honest`, `rule_deceptive`, `rule_deceptive_adaptive`) take `yell_crowd` (3), `yell_every` (8 ticks), `whisper` (true), `whisper_every` (1 tick: at most one whisper per this many ticks) |

`rule_deceptive` and `rule_deceptive_adaptive` also take `reopen` (`keep` default, `fresh`,
`counterfeit`; `lookalike` still accepted): the name they put up on reopening when brands are on.

Seller policies: `rule_honest`, `rule_deceptive`, `rule_deceptive_adaptive`,
`rule_genuine_rational`, `rule_genuine_rational_v2`, `rule_genuine_bust_at`, `llm`.
`rule_genuine_bust_at` (0.11.0; a benchmark tool, not a model of sellers) takes `schedule`
({stall id: day}); a listed stall busts out on its first decision of that day (or of the first later
day with a decision) and then claims its old quality on every channel, as a busted
`rule_genuine_rational`; any other stall is `rule_honest`. `engine/benchmark.py` uses it for the
ex-post best bust-out benchmark: the stall's total profit over all days with a bust-out on each
candidate day, against its total if it never busts out (all other genuine stalls honest).
0.15.0: `rule_genuine_bust_at` also takes `exit_at` ({stall id: day}; the stall sends `exit` on its
first decision of that day or a later one), and `benchmark.exit_candidates(bs, hs, D)` gives (b, h)
candidates: bust out on day b and exit at the end of day b + h − 1.
`rule_genuine_rational` (0.8.0; a benchmark, not a model of real sellers) is `rule_honest` until it
busts out. On its first decision of each day from day 2 (day 1 has no yesterday), with U =
yesterday's units sold, P = today's price, N = the neutral-rating price, c = its bust-out unit
cost and L = days left including today, it busts out if U(P − c) > L·U(P − N): one day's harvest
against the premium its name would still earn (decided 2026-11-06). After busting out it claims its
old quality on every channel, with no caution. It needs `brands.enabled` and
`market.horizon_known`. Set a
type's policy with e.g. `--set agents.seller.deceptive=rule_deceptive_adaptive`.
`rule_deceptive_adaptive` (positive control for strategic avoidance) behaves like
`rule_deceptive`, but goes quiet (no yell or whisper, truthful answers, sign set to
`truth`) while a uniformed passerby is in earshot, while `recent_catches` is non-empty,
or for `close_ticks` ticks after its own stall reopens. It then restores its sign.

`rule_genuine_rational_v2` (0.9.0; penalty-aware benchmark, not a model of real sellers) is
`rule_honest` until it busts out. On its first decision of each day from day 2 it compares, over
the L days left including today, honest value = L × yesterday's profit with bust-out value =
Σ_k [U(P_k − c) − A − E·F − min(1, E·close_ticks/ticks)·U(P_k − c)], where U = yesterday's units,
c = its bust-out unit cost, A = yesterday's ad spend, F = the penalty per catch, E = yesterday's
market-wide catches per stall making false claims (deceptive or busted), and P_k = the price at
the rating after k days of bad reviews (r_0 = today's rating; then 0 if unrated, else
`ratings.memory` × r; unchanged if U = 0). It busts out if bust-out value > honest value and
claims its old quality afterwards, as v1. E (with the premium, memory, ticks and closure length)
reaches it as a labelled privileged input: its `meta` has `privileged: true`, and with brands on
its seller observations carry a `privileged` block (`deceptive_catch_rate_yesterday`, null on day
1, `premium`, `rating_memory`, `ticks_per_day`, `close_ticks`). No other seller sees that block.

Policies: `agents/registry.py`.

## Demand: consideration sets (engine 0.12.0)

`buyers.demand_mode = "choice_set"` separates where a buyer walks (its exposure to yells, whispers
and inspectors) from which stalls it considers (demand). For each buyer, on the dedicated stream
`[day root, 18, buyer index]`: one draw picks the entrance (the left or right end of its category's
aisle, each with probability 1/2), then `buyers.consider` draws (always all consumed) pick its
consideration set: m = `consider` stalls of its category, from all of them (any type), by successive
sampling without replacement with weight exp(-`position_rent` × position rank). Position rank is the
stall's order of distance from the entrance: 0 for the nearest pair of facing stalls, then 1, ...
(stalls facing each other share a rank). The buyer's random route is still drawn (so every other draw
on the route stream is unchanged) and then replaced by a walk along its category's aisle from the
entrance to the other end, which passes every set member in walking order. It buys only from set
members, with the search rule at depth = m (`buyers.search_depth` is not used). Bargain hunters are on
by default in this mode (`bargain_share` null = 0.2). Needs `market.clustering = 1`. The outcome adds
`demand`: per stall, `inclusion` (buyers whose set includes it) and `customers` (distinct buyers who
bought from it); the world event's buyer `task` adds `consider` (the set in walking order).

The bust-out benchmark (`engine/benchmark.py`) tries the days {never, 10, 20, 25, 27, 28, 29} by
default since 0.12.0.

## Verification dial (engine 0.13.0)

`agents.params.rule_buyer.local_inspect_prob` and `expert_inspect_prob` (defaults 1.0 = the rule as
before): a local inspects an advertising stall (one that yelled or whispered at it) with probability
`local_inspect_prob`; an expert inspects before buying with probability `expert_inspect_prob`. The
choice is made once per (buyer, stall), the first time the rule calls for it, by a draw from the
buyer's own agent stream `[day root, 7, 1, buyer index]`, and only when the probability is strictly
between 0 and 1, so 0 and 1 use no draws and no engine stream is touched. A buyer who does not
inspect a stall trusts its latest claim, as a tourist does. `buyers.bargain_q_req` must be [lo, hi]
with 0 <= lo <= hi <= 1. `engine/benchmark.py` `candidates(days, horizon)` builds a validated
candidate list (NEVER plus distinct bust-out days in [2, horizon]) for `best_response`.
