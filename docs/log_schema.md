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
| `engine_version` | string | `engine.ENGINE_VERSION` |
| `config` | object | the full resolved config, defaults included. Replay rebuilds the run from it. |
| `env` | object | `python` and `numpy` versions. Replay reports a mismatch here as a warning only. |
| `agents` | object | keyed `"<role>:<policy>"` by the config's policy name. Each value is that agent's `meta()`: `policy`, `version`, `model_id`, `sampling`, and for LLM agents also `provider`, `max_retries`, `max_calls`, `system_prompt`. Reference agents also carry `reference` (`random`/`informed`), and the informed reference `privileged: true`. |
| `placeholders` | object | bazaar only: which defaults are placeholders still awaiting a research decision |
| `break_even` | number | M0 only: analytic e\* for the configured m, delta, P |

## `world` (bazaar, second line): ground truth

| field | meaning |
|---|---|
| `grid` | `W`, `H`, `aisle_y` (row of each aisle), `categories` |
| `stalls[]` | `sid`, `category`, `stype` (`genuine`/`seconds`/`deceptive`), `pos` [x, y], `brand` (fictional), `q_true`, `q_pitch` (the claim the stall makes when it pitches; equals `q_true` unless deceptive), `sign` (`truth`/`pitch`/`none`), `price_cents`, `unit_cost_cents` |
| `people[]` | `pid`, `kind` (`buyer`/`inspector`), `profile` (true profile for buyers; observable profile for inspectors), `is_inspector` (also true for buyers who are inspectors), `arrive`, `task` (buyers: `category`, `units`, `q_req`, `budget_cents`, `budget_level`) |

Agents never receive this event. It exists for analysis and the viewer.

## `obs`: observation sent to an agent

`{ev, t, agent, role, obs}`. `agent` is a stall id (`sNN`) or person id (`pNNN`).
`obs` is exactly what the agent received.

**Seller observation** (`role: "seller"`):

```jsonc
{
  "role": "seller", "tick": 12,
  "stall": {"id", "category", "brand", "stall_type", "true_quality", "pitch_quality",
            "truth_text", "pitch_text", "price_cents", "unit_cost_cents", "sign"},
  "costs": {"yell_cents", "whisper_cents", "penalty_cents_if_caught", "closure_ticks"},
  "ranges": {"earshot", "whisper_range"},
  "passersby": [{"id", "observed_profile", "distance"}],   // nearest first; profile is noisy; no inspector flag
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
  `{"yell":null,"whisper":null,"answers":[]}`).
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
`payments_total_cents`, `seller_revenue_total_cents` (always equal), `decisions`, `fallbacks`.

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

## `generation` (M0)

`g`, `dec_share_imp`, `dec_pop`, `fill` (these three exactly as in the
prototype's history), `impressions`, `sales`, `dec_share_sales`, `catches`,
`ad_spend`, `revenue`, `penalties`, `profit` (= revenue − penalties − ad_spend),
`cap_overflow` (impressions won beyond the cap under `cap_mode=batch`; always 0
under `strict`). `sales` counts realized sales only, the same definition the
accounting uses: within sale distance, excluding deceptive impressions that
reached an enforcer (those earn no revenue and pay P).
