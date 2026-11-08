# Log schema

Each run writes one JSONL file: one JSON object per line, one event per object.
Lines are canonical JSON (keys sorted, no whitespace, `NaN`/`Inf` written as
`null`), so two runs with the same config, seed and agent outputs produce
byte-identical files. `python -m cli.replay LOG` checks this.

Every event has an `ev` field naming its type. Bazaar events also carry `t`,
the tick.

## Event order

Bazaar mode:

```
header
world
( obs, raw, action )*  delta      # repeated each tick: zero or more decisions, then one delta
...
outcome
```

Bazaar mode with `market.days` = D > 1 (one file for all days):

```
header
( day_start  world  (obs, raw, action)* delta ...  outcome  day_end )   # once per day, D times
```

M0 mode:

```
header
generation        # one per generation
...
outcome
```

## `header` (both modes, first line)

| field | type | meaning |
|---|---|---|
| `mode` | `"bazaar"` \| `"m0"` | |
| `engine_version` | string | `engine.ENGINE_VERSION`, bumped whenever a change can alter the log for the same inputs. Replay reports a different version as a warning; the rest of the log decides, and a mismatch names the version difference as the likely cause. |
| `config` | object | the full resolved config, defaults included. Replay rebuilds the run from it. |
| `env` | object | `python` and `numpy` versions. Replay reports a mismatch here as a warning only. |
| `agents` | object | keyed `"<role>:<policy>"` by the config's policy name. Each value is that agent's `meta()`: `policy`, `version`, `model_id`, `sampling`, and for LLM agents also `provider`, `max_retries`, `max_calls`, `system_prompt`. Reference agents also carry `reference` (`random`/`informed`), and the informed reference `privileged: true`. |
| `placeholders` | object | bazaar only: which defaults are placeholders still awaiting a research decision |
| `break_even` | number | M0 only: analytic e\* for the configured m, delta, P |

## `world` (bazaar, second line): ground truth

| field | meaning |
|---|---|
| `grid` | `W`, `H`, `aisle_y` (row of each aisle), `categories`. At `market.scale` = k these are the refined grid (cells 1/k real units); the header's `config` is the config as given, in real units |
| `stalls[]` | `sid`, `category`, `stype` (`genuine`/`seconds`/`deceptive`), `pos` [x, y], `brand` (fictional), `q_true`, `q_pitch` (the claim the stall makes when it pitches; equals `q_true` unless deceptive), `sign` (`truth`/`pitch`/`none`), `price_cents`, `unit_cost_cents` |
| `people[]` | `pid`, `kind` (`buyer`/`inspector`), `profile` (true profile for buyers; observable profile for inspectors), `is_inspector` (also true for buyers who are inspectors), `arrive`, `task` (buyers: `category`, `units`, `q_req`, `budget_cents`, `budget_level`, and `budget_factor` when `buyers.budget_factor_override` is set) |

Agents never receive this event. It exists for analysis and the viewer.

## `obs`: observation sent to an agent

`{ev, t, agent, role, obs}`. `agent` is a stall id (`sNN`) or person id (`pNNN`).
`obs` is exactly what the agent received.

**Seller observation** (`role: "seller"`):

```jsonc
{
  "role": "seller", "tick": 12,
  "stall": {"id", "category", "brand", "stall_type", "true_quality", "pitch_quality",
            "truth_text", "pitch_text", "price_cents", "unit_cost_cents", "sign",
            "reopened_at_tick"},                            // last reopening after a catch; null if never caught
  "costs": {"yell_cents", "whisper_cents", "penalty_cents_if_caught", "closure_ticks"},
  "ranges": {"earshot", "whisper_range"},
  "passersby": [{"id", "observed_profile", "distance", "uniform"}],
      // nearest first; profile is noisy; no inspector flag. "uniform" is present for
      // everyone and true only for a uniformed inspector (inspectors.uniformed) within
      // inspectors.recognition_range (default: earshot), so non-uniformed inspectors, and
      // uniformed ones beyond recognition range, look exactly like buyers.
  "recent_catches": [{"distance", "ticks_ago"}],            // public notices: catches at stalls within
      // earshot of this one in the last L = closure_ticks ticks (ticks_ago 1..L), oldest first
  "asks": [{"id"}],                                         // people who asked last tick
  "ledger": {"revenue_cents", "units_sold", "ad_spend_cents", "penalties_cents", "catches"}
}
```

**Buyer observation** (`role: "buyer"`):

```jsonc
{
  "role": "buyer", "tick": 12,
  "you": {"id", "profile", "inspect_cost_cents",
          "task": {"category", "units_needed", "units_acquired", "q_req", "budget_cents", "budget_left_cents"}},
  "stalls_here": [{"id", "brand", "category", "price_cents",
                   "messages": [{"tick", "channel", "claimed_quality", "text"}],  // everything this stall has told you
                   "inspected_quality",                                            // null until you inspect
                   "ask_pending"}],
  "actions_left_here": 3,
  "oracle": {...}   // ONLY for the perfect-information reference buyer: true_quality here, route_ahead
}
```

Commercial content reaches a buyer only through `messages` (sign, yell,
whisper, answer), which are world events. The harness instructions (the LLM
system prompt) are static per role and contain no market content.

## `raw`: what the agent returned

`{ev, t, agent, role, raw}`. `raw` is the agent's output string, or `null` if
the agent raised.
Optional fields:
- `agent_error`: the crash message, if the agent raised. Replay re-raises it.
- `attempts`: for agents that retry (the LLM adapter), every attempt as
  `{attempt, raw, error}` or `{attempt, skipped}`.

## `action`: what the engine did with it

`{ev, t, agent, role, action, valid, error, fallback}`.
- `action` is the action applied: the parsed action if valid, otherwise the
  role's fallback (buyer `{"action":"move_on"}`; seller
  `{"yell":null,"whisper":null,"answers":[]}`). A seller action may also carry
  `"sign": "pitch" | "truth"`, which sets the stall's sign. It takes effect in the
  same tick's delivery (seller decisions come before delivery) and stays until
  changed. The key is omitted when the action does not set the sign, and the
  fallback never sets it. Because sight range (3) is inside earshot (4), anyone
  who can see a sign triggers a seller decision first.
- `error` says why the output was rejected (bad JSON, schema violation, or an
  engine-state check such as out of range, over budget, or answering someone
  who did not ask). It is `null` when the output was valid.

Action schemas: `engine/interface.py` (`SELLER_ACTION_SCHEMA`, `BUYER_ACTION_SCHEMA`).
Both reject unknown fields, and no field can set a price, a quality, an
outcome or enforcement.

## `delta`: engine state change for one tick

| field | meaning |
|---|---|
| `pos` | `{pid: [x, y]}` for every person present after movement |
| `msgs[]` | `{from, ch, q, false, to[]}`: each message delivered this tick. `ch` is `sign`/`yell`/`whisper`/`answer`, `q` is the claimed quality, `false` means q > true Q, `to` lists the recipients (one impression each). |
| `buys[]` | purchase records: `buyer`, `stall`, `stype`, `units`, `amount_cents`, `q_true`, `q_req`, `shortfall`, `value` (V delivered), `known_claims` (claims this buyer had received from that stall), `inspected_q`, `received_false_claim`, `buyer_profile`, `buyer_is_inspector` |
| `catches[]` | `stall`, `by` (pid), `channel`, `claimed`, `true`, `penalty_cents`, `reopens` (tick) |
| `inspects[]` | `buyer`, `stall`, `cost_cents` |
| `asks` | `{sid: [pid]}`: asks to be answered next tick (buyers' and disguised inspectors') |
| `closed` | stalls closed during the next tick |

## `outcome` (last line)

Bazaar: `buyers_arrived`, `buyer_surplus_mean_cents`, `buyer_surplus_total_cents`,
`purchases`, `units_bought`, `shortfall_rate` (share of purchases with Q < Q_req),
`shortfall_rate_units`, `empty_handed_share`, `task_complete_share` (required quantity at Q ≥ Q_req), `quantity_fulfilled_share` (required quantity of anything), `inspector_active_ticks.{dedicated, inspector_buyers}` (enforcing person-ticks; equal headcounts are not equal effort), `impressions`,
`impressions_by_channel`, `impressions_by_stype`, `deceptive_share_impressions`,
`false_claim_share_impressions`, `deceptive_share_sales_units`, `inspections`,
`inspection_spend_cents`, `catches`,
`seller_by_type.{genuine,seconds,deceptive}.{stalls, revenue_cents, cost_cents, ad_spend_cents, penalties_cents, units_sold, catches, profit_cents, profit_per_stall_cents}`,
`payments_total_cents`, `seller_revenue_total_cents` (always equal), `decisions`, `fallbacks`,
`reachable.{share, buyers, task_complete_share, buyer_surplus_mean_cents}`
(the same metrics over reachable buyers: those whose route passes within `interact_range` of a
stall of their category. Unreachable buyers never buy, so a reachable shortfall rate would equal
`shortfall_rate`; engine 0.3.0 reported it as `reachable.shortfall_rate`, and 0.4.0 drops it),
`false_claim_impressions`, `false_claim_impressions_to_uniform_eligible`,
`false_claims.{messages, no_eligible_in_earshot}` and
`false_claims_by_stall.{sid}.{messages, no_eligible_in_earshot}` (deceptive stalls only).
A false-claim *message* is one delivery event (a sign shown to its viewers that tick, a
yell, a whisper or an answer); `no_eligible_in_earshot` counts those sent while no
uniform-eligible inspector was within earshot of the stall. *Uniform-eligible* means a
dedicated inspector on a posts, clustered or patrolling placement: these are the
uniformed inspectors when `inspectors.uniformed` is true. The diagnostics are keyed on
eligibility, not on the uniform, so a policy that ignores the uniform has a
byte-identical outcome with the switch on or off.

Buyer surplus = V(Q delivered) − price paid − inspection costs, averaged over
buyers who arrived. Relative scores are not in the log, because they need two
extra reference runs: `cli.run --normalize` and `cli.sweep --normalize` add
`surplus_rel` and `shortfall_rel` (0 = random reference, 1 = informed reference;
comparisons, not bounds, so they can fall outside [0, 1]; `shortfall_rel` is null
whenever any of the three runs made no purchases) and the raw reference values
`surplus_random_ref`, `surplus_informed_ref`, `shortfall_random_ref`,
`shortfall_informed_ref`. Raw outcomes are primary.

M0: `dec_share_imp_last` (mean deceptive share of filled impressions over the
last `last` generations), `final_dec_pop`.

## `day_start`, `day_end` (multi-day bazaar only)

`day_start`: `day` (1 … D) and `types` (stall counts by type that day); with `ratings.mode` other
than `off`, also `ratings` (stall id → rating at the start of the day, null = unrated). The day's `world`,
ticks and `outcome` follow; `t` restarts at 0 each day. Day 1 uses the single-day streams,
so with the same config and seed its events are the single-day run's events.

`day_end`: `day`, `types`, `profit_by_type` (profit per stall in cents, by type),
`shortfall_rate`, `catches`, and `switches`: the type switches made after this day (empty after
the last day). Each switch: `stall`, `category`, `from`, `to`, `profit_cents` (its day profit),
and when it revised: `partner`, `partner_profit_cents`, `p_switch` (when the partner's type
differed and it earned more), `imitated`, `mutated`; with switching costs, `switch_cost_cents`
(charged on the next day); with ratings computed, `rating` and `rugpull`. With ratings computed,
`day_end` also has `ratings` (after the day's update) and `rugpulls` (count among `switches`).

With `brands.enabled` (0.8.0): `day_start` adds `brands` (stall id → name) and `prices` (the
morning prices); `day_end` adds `brand_ratings` (every name ever used → rating after the update),
`brands`, `counterfeit_of` (counterfeit stall → original name), `prices`, `renames` and `bust_outs`
(that day's records, as in `delta`), `busted` (stall → bust-out day) and `reviews` (name →
[honest units, rated units] filed that day). `delta` adds `renames[]` (`t`, `day`, `stall`, `how`,
`from`, `to`, `counterfeit_of`, `target_stall`, `target_rating`, `price_cents`) and `bust_outs[]`
(`t`, `day`, `stall`, `brand`, `q_was`, `q_true`, `rating`, `price_cents`, `unit_cost_cents`);
purchase records add `brand` (actual name) and `filed_under` (where the review goes); the outcome
adds `brands` (`renames`, `renames_by_how`, `bust_outs`, `busted_stalls`, `counterfeit_stalls`,
`profit_by_stall_cents`, `units_by_stall`). Seller actions may carry `rename` and `bust_out`;
seller observations carry the `brand` block and, with `market.horizon_known`, `horizon` and
`yesterday`; a privileged seller policy (`rule_genuine_rational_v2`) also gets a `privileged` block.
With `buyers.search_log` (0.10.0) the outcome adds `search`: `buyers` (buyer id → `profile`, `k`,
`seen` (stall ids in the order first seen), `chosen` (each `choose`), `bought`, `candidates` (the
list sent with the last `buy` or `choose`, or null), `walk_ticks`, `skipped_closed`) and
`exposure` (stall id → `in_reach`: buyers of its category that came within interact range;
`in_reach_shopping`: those that still needed units then). Searching buyers' observations carry a
`search` block and their actions may be `choose`.

With `buyers.demand_mode = "choice_set"` (0.12.0) the outcome adds `demand`: `inclusion` (stall id →
number of buyers whose consideration set includes it) and `customers` (stall id → distinct buyers who
bought from it), and each buyer's `task` in the world event adds `consider` (its set, in walking order).

With `critics.count` > 0 (0.11.0), `day_end` and the day's record add `critic_reviews`:
`written` (reviews written that day) and `filed` (reviews entering that day's rating update), each a
list of {`day` (written), `critic`, `stall`, `brand`, `stype`, `busted`, `q_true`, `claim`,
`positive`, `delay`, `file_day`, `tied`}; filed reviews are also counted in `reviews`. With
`buyers.bargain_share` > 0 a bargain hunter's `task` carries `bargain: true`.

Engine 0.9.0 renamed "look-alike" to "counterfeit" in all these fields (`how` is `fresh` or
`counterfeit`); 0.8.0 logs still replay, compared with `lookalike` mapped to `counterfeit`.

Ratings also add `rating` to the `stalls_here` rows of buyers who can see them (`ratings.mode =
public`, profile in `ratings.visible_to`). With `market.whispers_allowed = false`, seller
observations carry `ranges.whispers_allowed: false`.

## `generation` (M0)

`g`, `dec_share_imp`, `dec_pop`, `fill` (these three exactly as in the
prototype's history), `impressions`, `sales`, `dec_share_sales`, `catches`,
`ad_spend`, `revenue`, `penalties`, `profit` (= revenue − penalties − ad_spend),
`cap_overflow` (impressions won beyond the cap under `cap_mode=batch`; always 0
under `strict`). `sales` counts realized sales only, the same definition the
accounting uses: within sale distance, excluding deceptive impressions that
reached an enforcer (those earn no revenue and pay P).
