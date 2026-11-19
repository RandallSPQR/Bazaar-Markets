# Agent interface

Written against engine 0.21.0, the code to be frozen as 1.0.0. This document describes code; it changes none.

**Summary.**

- Agents act at two kinds of turn: a **seller turn** (one stall, one tick) and a **buyer turn** (one buyer, one tick). At each turn the engine sends a JSON observation and receives one string. It parses the string as JSON, checks it against the role's schema, then checks it against engine state. Any failure replaces the whole action with the role's fallback (seller: do nothing; buyer: move on). The failure is logged and counted in the outcome's `fallbacks`.
- The plan names ten decision points. Seven are agent choices: buyer search, choice and inspect; seller channel (with sign), switch supply, rename and exit. Two are not: **price** is set by the engine from the displayed rating, and **licence** is set by the config schedule. No agent can set a price, a quality, an outcome or an enforcement result (`engine/interface.py:9-13`).
- Every non-privileged policy of a role receives the same observation for the same state. An LLM agent therefore sees nothing a rule-based agent is not given. It can, however, use many fields the rule policies ignore (section 7). Two benchmark rule policies receive privileged blocks that no study agent gets.
- No LLM call is implemented at 1.0.0 (`agents/llm_stub.py:92-95`), and **no response cache keyed by the prompt exists**. Determinism today rests on seeded streams and on log replay. Section 6 states the contract a cache must meet.

## 1. Terms and neutral names

Agent-facing text should use neutral option names. Some wire names in the 1.0.0 schema and observation are not neutral. Renaming them would change log bytes, so this document gives both names (see open point 5).

| Neutral name (use in prompts and prose) | Wire name at 1.0.0 | Where |
|---|---|---|
| switch supply | `"bust_out": true` | seller action (`engine/interface.py:46`) |
| new name | `"rename": "fresh"` | seller action (`engine/interface.py:45`) |
| copied name | `"rename": "counterfeit"` (alias `"lookalike"`) | seller action (`engine/interface.py:45`) |
| leave the market | `"exit": true` | seller action (`engine/interface.py:49`) |
| name copied from | `brand.counterfeit_of` | seller observation (`engine/bazaar.py:818`) |
| day supply was switched | `brand.busted_day` | seller observation (`engine/bazaar.py:821`) |
| unit cost after switching supply | `brand.bust_out_unit_cost_cents` | seller observation (`engine/bazaar.py:822-823`) |
| stall type: genuine, seconds, low-quality pitching | `stall.stall_type`: `genuine`, `seconds`, `deceptive` | seller observation (`engine/bazaar.py:797`) |

A **claim** is one of two menu items: `"truth"` (the stall's true quality) or `"pitch"` (its pitch quality). For genuine and seconds stalls the two are equal. The engine renders the message text; sellers never write free text (`engine/bazaar.py:246-248`).

## 2. When agents are called

One tick runs in a fixed order (`engine/bazaar.py:3-10`, `354-526`): arrivals; seller turns; message delivery and detection; buyer turns; movement; one `delta` log event. All loops run in fixed id order.

| Turn | Who | Called when | Code |
|---|---|---|---|
| Seller | each open stall, in stall order | someone active (buyer or inspector) is within `market.earshot`, or someone who asked last tick is still active | `engine/bazaar.py:370-377` |
| Buyer, walk mode (search depth 1) | each active buyer, in id order | it still needs units, is not held (scale > 1), has at least one open stall of its task category within `market.interact_range` that is in its consideration set, and has actions left at this stop (`market.max_actions_per_stop`, default 4) | `engine/bazaar.py:460-486` |
| Buyer, searching (search depth k > 1, or `buyers.demand_mode` `choice_set`) | as above | as above, or in phase `choose` at its route end or after a chosen stall was found closed (then `stalls_here` may be empty) | `engine/bazaar.py:470-474`, `628-662` |

Every turn goes through one function, `BazaarEngine.decide` (`engine/bazaar.py:287-312`): log `obs`; call `agent.act(obs)`; log `raw`; parse and check; log `action`; return the action applied.

The agent contract is the `Agent` protocol (`engine/interface.py:83-90`): `act(observation: dict) -> str` and `meta() -> dict`. Agents are built by `agents/registry.py:36-52` from the policy names in `agents.seller` (one policy per stall type) and `agents.buyer` (one policy for all buyers). In multi-day runs every agent is rebuilt each morning (`engine/days.py:11-12`, `186-189`), so no agent carries memory across days.

## 3. Seller turn

### 3.1 Observation

Built by `seller_obs` (`engine/bazaar.py:793-834`). Blocks marked "conditional" are absent otherwise.

| Field | Type | Meaning |
|---|---|---|
| `role` | `"seller"` | |
| `tick` | int | current tick (0-based within the day) |
| `stall.id` | str `sNN` | own stall id |
| `stall.category` | str | `fish`, `electronics`, `designer` |
| `stall.brand` | str | the name the stall bears (its actual name, never the copied original's) |
| `stall.stall_type` | str | own type (see section 1 for the neutral wording) |
| `stall.true_quality`, `stall.pitch_quality` | float in [0, 1] | what a `truth` and a `pitch` claim state |
| `stall.truth_text`, `stall.pitch_text` | str | the rendered message for each claim |
| `stall.price_cents` | int | today's posted price (read only) |
| `stall.unit_cost_cents` | int | cost per unit sold |
| `stall.sign` | `truth` \| `pitch` \| `none` | what the sign shows now |
| `stall.reopened_at_tick` | int \| null | tick the last closure ends; null if never caught today |
| `costs.yell_cents`, `costs.whisper_cents` | int | ad cost per yell, per whisper (signs and answers are free) |
| `costs.penalty_cents_if_caught`, `costs.closure_ticks` | int | fine per catch; closure length |
| `ranges.earshot`, `ranges.whisper_range` | float | channel ranges in grid units |
| `ranges.whispers_allowed` | `false` | present only when `market.whispers_allowed` is false |
| `passersby[]` | list | everyone active within earshot, nearest first: `id` (str `pNNNNNN`), `observed_profile` (`tourist`/`local`/`expert`; replaced by a random profile with probability `buyers.profile_noise`, stable per stall-person pair, `engine/bazaar.py:257-265`), `distance` (float, 3 dp), `uniform` (true only for a uniformed inspector within `inspectors.recognition_range`) |
| `recent_catches[]` | list | public notices: catches at stalls within earshot in the last `closure_ticks` ticks: `distance`, `ticks_ago` (`engine/bazaar.py:775-785`) |
| `asks[]` | list of `{id}` | people who asked this stall last tick and are still active |
| `ledger` | object | today so far: `revenue_cents`, `units_sold`, `ad_spend_cents`, `penalties_cents`, `catches` |
| `brand` (conditional: `brands.enabled`) | object | `name`; `counterfeit_of` (str \| null); `rating` (displayed rating of own name, float \| null = unrated); `neutral_price_cents` (price at rating 0.5); `rename_available` (bool); `first_decision_today` (bool); `busted_day` (int \| null); `bust_out_unit_cost_cents` (int, or null unless the stall is genuine and has not switched supply) |
| `horizon` (conditional: `market.horizon_known`) | object | `day`, `days` |
| `yesterday` (conditional: `market.horizon_known`) | object \| null | own previous-day ledger: `units_sold`, `revenue_cents`, `cost_cents`, `ad_spend_cents`, `penalties_cents`, `profit_cents`, `price_cents`, `catches`; null on day 1 (`engine/days.py:163-165`) |
| `privileged` (conditional: brands on and the policy's `meta()` declares `privileged: true`) | object | labelled benchmark input: `deceptive_catch_rate_yesterday`, `premium`, `rating_memory`, `ticks_per_day`, `close_ticks`. Only `rule_genuine_rational_v2` gets it (`engine/bazaar.py:183`, `827-833`) |

The seller is not told: which passersby are inspectors (unless uniformed and in recognition range); any other stall's price, rating or quality; whether it is a licensee or a licence owner; royalties paid or received.

### 3.2 Return

Schema: `SELLER_ACTION_SCHEMA` (`engine/interface.py:24-51`). One JSON object; unknown keys are rejected. Every key is optional, so `{}` is a valid "do nothing".

| Key | Value | Default when omitted | Decision point |
|---|---|---|---|
| `yell` | `null` or `{"claim": "truth" \| "pitch"}` | `null` | channel |
| `whisper` | `null` or `{"to": <passerby id>, "claim": ...}` | `null` | channel |
| `answers` | list (max 32) of `{"to": <asker id>, "claim": ...}` | `[]` | channel |
| `sign` | `"truth"` \| `"pitch"` | sign unchanged | channel |
| `rename` | `"fresh"` \| `"counterfeit"` (\| `"lookalike"`) | no rename | rename |
| `bust_out` | `true` | no switch | switch supply |
| `exit` | `true` | stay | exit |

Example (an honest stall answering one asker, whispering to one passerby, keeping its sign):

```json
{"yell": null, "whisper": {"to": "p043117", "claim": "truth"}, "answers": [{"to": "p810022", "claim": "truth"}]}
```

`parse` normalises a valid seller action to `{yell, whisper, answers}` plus any optional key present (`engine/interface.py:105-108`).

### 3.3 State checks

Applied after the schema check, in this order (`engine/bazaar.py:381-400`). The first failure rejects the whole action.

| Check | Error text (abridged) |
|---|---|
| `rename` only with brands on and a rename pending | "rename is allowed only on the first decision after a reopening" |
| `bust_out` only with brands on, a genuine stall, not yet switched, first decision of the day | "bust_out is allowed only for an honest genuine stall on its first decision of the day" |
| `exit` not already pending | "the stall is already leaving at the end of today" |
| no `whisper` when whispers are disallowed | "whispers are not allowed in this market" |
| `whisper.to` within `whisper_range` (among passersby) | "whisper target ... not within whisper range" |
| no duplicate `answers[].to` | "duplicate answer recipient" |
| every `answers[].to` asked | "answer to ..., who did not ask" |

A yell has no state check. A yell with nobody in earshot is valid, costs its ad spend and reaches no one.

### 3.4 How a valid action is applied

`engine/bazaar.py:402-421`, in this order: rename; switch supply; then (brands on) the rename chance is cleared and `decided_today` set; exit flag; sign; yell (charged, delivered to everyone in earshot); whisper (charged, one recipient); answers (free). Delivery happens after all sellers have decided: signs first, then the queued messages in stall order (`engine/bazaar.py:423-455`). Each perception by an enforcing inspector of a false claim draws detection.

### 3.5 Decision point: channel (and sign)

- **Who, when.** Any open stall, at each seller turn (section 2).
- **Sees.** All of 3.1. The fields that bear on the choice: `passersby` (who is near, noisy profile, uniform), `asks`, `recent_catches`, `stall.reopened_at_tick`, `costs`, `ranges`, own qualities and texts.
- **May return.** `yell`, `whisper`, `answers`, `sign` with a claim each.
- **Invalid output.** Rejected; fallback (section 5). A bad whisper target also discards valid answers in the same action.
- **Rule policies.** `rule_honest` (`agents/rule_based.py:41-62`) reads `tick`, `passersby` (count, `distance`, `id`, `observed_profile`), `ranges.whisper_range`, `ranges.whispers_allowed`, `asks`. `rule_deceptive` adds the `observed_profile == "expert"` caution (`agents/rule_based.py:101-108`). `rule_deceptive_adaptive` adds `uniform`, `recent_catches`, `stall.reopened_at_tick`, `costs.closure_ticks`, `stall.sign` (`agents/rule_based.py:133-156`). No rule seller reads `ledger`, `costs.yell_cents`/`whisper_cents`/`penalty_cents_if_caught`, the quality values or texts, or the price.

### 3.6 Decision point: price (not an agent decision)

No action field sets a price (`engine/interface.py:12-13`). The engine sets it:

| Setting | Price | Code |
|---|---|---|
| brands off | base × tier, fixed at world build; reset by the type rules on a between-day type switch | `engine/world.py:220-226`; `engine/days.py:80-91` |
| brands on, each morning | round(base × tier × (1 + `brands.premium` × (r̃ − 0.5))), r̃ = the displayed start-of-day rating of the stall's name, 0.5 if unrated | `engine/brands.py:193-208` |
| copied name | round(φ × the original's current price), φ = `brands.counterfeit_price_factor` | `engine/brands.py:205-208`, `217-220` |
| licensee under the owner's name | the owner's price | `engine/licensing.py:135-140` |
| after a rename (same day) | new name: neutral price; copied name: φ × original's price | `engine/bazaar.py:579-585` |

Ratings change only between days, so a stall's price is constant within a day except after a rename. The seller sees `stall.price_cents` and, with brands on, `brand.neutral_price_cents`. Stage 3 (engine 1.1.0) plans a market-wide `sellers.price_policy`; that is still a config setting, not an agent decision.

### 3.7 Decision point: switch supply

- **Who, when.** A genuine stall that has not switched, on its first decision of a day, with `brands.enabled`. The observation says so: `brand.first_decision_today` true and `brand.bust_out_unit_cost_cents` not null.
- **Sees.** 3.1, in particular `brand.rating`, `brand.neutral_price_cents`, `brand.bust_out_unit_cost_cents`, `stall.price_cents`, `stall.unit_cost_cents`, and, with `market.horizon_known`, `horizon` and `yesterday`. It does not see the low quality it would switch to, only the unit cost at that quality.
- **May return.** `"bust_out": true` alongside any channel keys.
- **Effect.** Irreversible. True quality drops to the stall's low quality (one draw from `stalls.q_low` on `[seed, 12, stall index]`), unit cost follows, the sign shows `pitch` (the old quality), name and price rule unchanged (`engine/bazaar.py:594-606`; `engine/brands.py:327-332`). On later days the sign resets to `pitch` (`engine/days.py:154-155`). Its claims are now false and can be caught.
- **Invalid output.** Sent at any other time, the whole action is rejected. Note: the first decision of the day uses up the chance even when the action is invalid (`engine/bazaar.py:403-409`; open point 7).
- **Rule policies.** Only the benchmarks decide this: `rule_genuine_rational` (reads `brand`, `horizon`, `yesterday.units_sold`, `stall.price_cents`; `agents/rule_based.py:182-200`), `rule_genuine_rational_v2` (adds `yesterday.profit_cents`, `yesterday.ad_spend_cents`, `costs.penalty_cents_if_caught`, `brand.rating` and the privileged block; `agents/rule_based.py:226-251`), and `rule_genuine_bust_at` (a fixed schedule; `agents/rule_based.py:274-290`). `rule_honest` never switches.
- **Not an agent decision.** With brands off, between-day type switching is engine imitation and mutation (`engine/days.py:94-140`). Brands and imitation cannot be combined (`engine/days.py:181-182`).

### 3.8 Decision point: rename (new name or copied name)

- **Who, when.** With `brands.enabled`, a stall that was caught, on its first decision after the closure ends (that day or the next morning). `brand.rename_available` is true exactly then. A catch sets the chance (`engine/bazaar.py:564-565`); licensees and stalls that took a copied name on a fixed entry day never get it.
- **Sees.** 3.1. It does not see other stalls' names or ratings, so it cannot see which name a copy would take.
- **May return.** `"rename": "fresh"` (new unrated fictional name, neutral price) or `"rename": "counterfeit"` (copied name: a one-edit near-copy of the highest displayed-rated name on another stall of its category that is not seconds, not itself a copy and still in the market; unrated = 0.5; ties at random; price = φ × the original's price). With no eligible original it gets a new name. Draws: `[day root, 11, stall index, rename count]` (`engine/bazaar.py:568-592`; `engine/brands.py:279-291`).
- **Effect on buyers.** Tourists read the original's name on a copied name and file their reviews under it; locals and experts read the actual name (`engine/bazaar.py:250-255`).
- **Invalid output.** A rename at any other time rejects the whole action. The first decision after reopening uses up the chance whether or not the action is valid (`engine/bazaar.py:408`; open point 7).
- **Rule policies.** `rule_deceptive` and `rule_deceptive_adaptive` read only `brand.rename_available` and send the configured `reopen` choice (`agents/rule_based.py:93-99`, `154-155`). The state of the market plays no part.
- **Not an agent decision.** Copied-name entry on a fixed day (`brands.counterfeit_entry` `day`) is applied by the engine to every eligible low-quality stall (`engine/brands.py:241-269`).

### 3.9 Decision point: licence (not an agent decision)

Licences come from `licensing.schedule` (owner stall id → `{day, n}`). At the start of the scheduled day the engine picks the licensees from `[seed, 19, owner index]`, rewrites their name, quality, sign, unit cost and price, and assigns their policy: the configured low-quality policy for `cheap`, `rule_honest` for `contract` (`engine/licensing.py:74-78`, `92-132`). No agent is offered a licence, and none can accept, refuse or end one. The seller observation does not say that a stall is a licensee or an owner, and the ledger omits royalties (open point 11). Stage 3's `license_*` options are applied by the experimenter in continuation runs; they are not agent actions either.

### 3.10 Decision point: exit

- **Who, when.** Any open stall at any seller turn of the day.
- **May return.** `"exit": true`. Valid unless an exit is already pending.
- **Effect.** The stall leaves at the end of the day (`engine/bazaar.py:1001-1008`): closed every later day (`engine/days.py:161-162`), in no consideration set, never a copy target; fines not yet due become uncollectible. In a single-day run the action is accepted and only recorded.
- **Rule policies.** Only `rule_genuine_bust_at` with `exit_at` sends it, on a fixed day (`agents/rule_based.py:274-280`).

## 4. Buyer turn

### 4.1 Observation

Built by `buyer_obs` (`engine/bazaar.py:836-870`) and, for searching buyers, `search_obs` (`engine/bazaar.py:891-913`).

| Field | Type | Meaning |
|---|---|---|
| `role` | `"buyer"` | |
| `tick` | int | |
| `you.id` | str `pNNNNNN` | |
| `you.profile` | str | own true profile |
| `you.inspect_cost_cents` | int | cost of one inspection: round(base × `buyers.inspect_cost_frac[profile]`) (`engine/world.py:395`) |
| `you.task.category` | str | category to buy |
| `you.task.units_needed`, `you.task.units_acquired` | int | units still needed; units bought so far |
| `you.task.q_req` | float | the quality a unit must meet to count |
| `you.task.budget_cents`, `you.task.budget_left_cents` | int | budget; budget minus payments and inspection spend |
| `you.inspect_prob` (conditional: `buyers.profile_overrides` sets it for this buyer) | float in [0, 1] | a policy parameter, not a world fact (open point 13) |
| `stalls_here[]` | list | open stalls of the task category within interact range and in the buyer's consideration set |
| `stalls_here[].id` | str | |
| `stalls_here[].brand` | str | the name as this buyer reads it (a tourist reads the original's name on a copy) |
| `stalls_here[].category`, `.price_cents` | str, int | |
| `stalls_here[].messages[]` | list | every claim this stall delivered to this buyer today, oldest first: `tick`, `channel` (`sign`/`yell`/`whisper`/`answer`), `claimed_quality`, `text` |
| `stalls_here[].inspected_quality` | float \| null | true quality if this buyer inspected the stall today |
| `stalls_here[].ask_pending` | bool | the buyer asked this stall this tick |
| `stalls_here[].own_assessment` (conditional: inspector-buyer with `buyers.inspector_knowledge`) | float | the stall's true quality |
| `stalls_here[].rating` (conditional: buyer sees ratings) | float \| null | displayed rating; null = unrated |
| `stalls_here[].tie_rank` (conditional: `buyers.tie_break` `random`) | int | this buyer's random order of stalls for today; a policy device, not a world fact (open point 13) |
| `actions_left_here` | int | actions left at this stop before the buyer is moved on |
| `search` (conditional: searching buyer) | object | `depth` (k), `seen_count`, `phase` (`browse`/`choose`), `route_end` (bool), `seen_elsewhere[]` |
| `search.seen_elsewhere[]` | list | stalls seen earlier today, not in reach now and not skipped: `id`, `brand`, `price_cents` (current), `messages`, `inspected_quality`, `steps_away` (route steps back or forward), and `own_assessment`, `rating`, `tie_rank` under the same conditions as above |
| `oracle` (conditional: policy `meta()` declares `privileged: true`) | object | `true_quality` here and `route_ahead`; only `informed_reference` gets it (`engine/bazaar.py:866-869`) |

A buyer "sees ratings" when `ratings.mode` is `public` and its profile is in `ratings.visible_to` (default local and expert), unless `buyers.profile_overrides` sets `reads_ratings` for it (`engine/bazaar.py:883-889`). The buyer is not told whether it is an inspector-buyer, whether it is a bargain hunter, how a unit's value is computed, or any stall's true quality (except by inspection or own assessment).

### 4.2 Return

Schema: `BUYER_ACTION_SCHEMA` (`engine/interface.py:57-74`). Exactly one of:

| Action | Shape | Decision point |
|---|---|---|
| move on | `{"action": "move_on"}` | search |
| ask | `{"action": "ask", "stall": id}` | search |
| inspect | `{"action": "inspect", "stall": id}` | inspect |
| buy | `{"action": "buy", "stall": id, "units": 1..100, "candidates": [ids]?}` | choice |
| choose (searching buyers) | `{"action": "choose", "stall": id, "candidates": [ids]?}` | search / choice |

There are no defaults: `action` is required, and `stall`/`units` where shown. `candidates` (up to 64 ids) is optional and has no effect; it is logged in the `action` event and, with `buyers.search_log`, in the search record.

Example (a searching buyer in phase `choose` walking back to a stall seen earlier):

```json
{"action": "choose", "stall": "s07", "candidates": ["s07", "s03"]}
```

### 4.3 State checks

`engine/bazaar.py:677-707`. The first failure rejects the action.

| Action | Valid only if |
|---|---|
| `move_on` | always |
| `choose` | phase is `choose`; the stall was seen today and not found closed when chosen; it is not within reach now |
| `buy` | not in phase `browse`; stall in `stalls_here`; `units` ≤ units needed; `units` × price ≤ budget left |
| `ask` | stall in `stalls_here`; not already asked this tick |
| `inspect` | stall in `stalls_here`; not already inspected today; inspection cost ≤ budget left |

Nothing is clamped. A `buy` of 3 units when 2 are needed is rejected, not cut to 2.

### 4.4 Decision point: search

- **Who, when.** Every buyer turn. What the agent controls is narrow. The route (walk mode) or consideration set and aisle walk (`choice_set`) are drawn by the engine; search depth is fixed by profile (`buyers.search_depth`) or by `buyers.consider`.
- **May return.** `ask` (free; the stall's agent may answer next tick, `engine/bazaar.py:726-727`); `move_on` (end the stop and walk on); for searching buyers, `choose` (the engine walks the buyer to the last route cell where that stall was in reach, one cell per tick, and it decides nothing until it gets there; a chosen stall found closed is skipped for the day, `engine/bazaar.py:628-662`).
- **Phases.** A searching buyer is in `browse` until it has seen k stalls or reached its route end, then in `choose` for the rest of the day. Buying in `browse` is invalid.
- **Each stay uses an action.** `ask`, `inspect` and `buy` keep the buyer at the stop and use one of `actions_left_here`; at zero it is moved on.
- **Rule policy.** `rule_buyer` asks the first affordable stall it has heard nothing from (`agents/rule_based.py:383-387`, `442-445`) and, when searching, browses until phase `choose` (`agents/rule_based.py:446-447`). It reads `search.phase` and the rows; it does not read `steps_away`, `seen_count`, `depth`, `route_end` or `actions_left_here`.

### 4.5 Decision point: inspect

- **Who, when.** Any buyer turn with a stall in reach, if the buyer can pay.
- **Effect.** Costs `you.inspect_cost_cents` from the budget and reveals the stall's true quality exactly in `inspected_quality` for the rest of the day (`engine/bazaar.py:728-733`).
- **Rule policy.** Experts inspect any stall before buying; locals inspect a stall that yelled or whispered at them; tourists never, unless given `you.inspect_prob`, when they follow the local rule. Each with probability θ (`agents.params.rule_buyer.*_inspect_prob` or `you.inspect_prob`), drawn once per stall from the agent's own stream. A buyer inspects only if inspection cost plus price fits the budget (`agents/rule_based.py:321-344`, `374-382`).

### 4.6 Decision point: choice (buy)

- **Who, when.** Walk mode: any buyer turn. Searching: phase `choose`.
- **Effect.** Pays units × price; value is realised from the stall's true quality (`engine/bazaar.py:741-771`). A unit counts toward the task only if true quality ≥ `q_req`. The purchase is rated (enters the name's next rating) only if the buyer had received at least one claim from the stall (`engine/brands.py:297-324`).
- **Rule policy.** Quality estimate = own assessment, else inspection, else the latest claim. A stall is a candidate if the estimate ≥ `q_req`, one unit is affordable and, if the buyer sees ratings, the displayed rating is ≥ `ratings.tau` (unrated passes). Depth 1: it goes through stalls in reach by (price, tie-break) and acts at the first candidate (`agents/rule_based.py:349-388`). Searching: highest displayed rating (unrated = 0.5), then lowest price, then tie-break; buyers who do not see ratings take the lowest price (`agents/rule_based.py:448-464`). It buys min(units needed, units affordable).

## 5. Invalid outputs

| Failure | Detected by | Logged | Result |
|---|---|---|---|
| agent raises | `decide` (`engine/bazaar.py:290-295`) | `raw.raw = null`, `raw.agent_error` | fallback |
| output is not a string | `parse` (`engine/interface.py:95-96`) | `action.error` | fallback |
| invalid JSON | `parse` (`engine/interface.py:97-100`) | `action.error` | fallback |
| schema violation (unknown key, bad enum, `units` outside 1..100, missing key, string too long) | `parse` (`engine/interface.py:101-104`) | `action.error` (first error, by path) | fallback |
| state check fails | section 3.3, 4.3 | `action.error` | fallback |

- **Fallback.** Seller `{"yell": null, "whisper": null, "answers": []}`; buyer `{"action": "move_on"}` (`engine/interface.py:77-78`). The whole output is discarded: there is no partial application, clamping or engine retry.
- **Seller fallback side effects.** No messages; askers get no answer and their asks are spent; the sign is unchanged; with brands on, the rename chance and the day's switch-supply chance are used up (`engine/bazaar.py:403-409`).
- **Buyer fallback side effects.** The buyer leaves the stop. A searching buyer standing at its chosen stall drops that choice (`engine/bazaar.py:710-717`).
- **Logging.** `action` event: `{action, valid, error, fallback}` (`engine/bazaar.py:310-311`; `docs/log_schema.md`).
- **Counting.** Per day, the outcome carries `decisions` and `fallbacks`, each `{seller, buyer}` (`engine/bazaar.py:139-140`, `308`, `987`). The analysis scripts treat any fallback as a guard failure (for example `analysis/licensing.py:386-388`, `analysis/chainrun.py:56`). Rule-based runs are expected to have zero.
- **LLM adapter.** `LLMAgent.act` retries a schema failure up to `max_retries` (default 2), re-asking with the error text, and logs every attempt (`agents/llm_stub.py:77-90`). It does not run the state checks, so a state-invalid action is not retried (open point 3). When `max_calls` is reached it returns the fallback as a *valid* string, so the engine does not count it as a fallback (open point 2).

## 6. Determinism

### 6.1 Engine

Given the config, the seed and every agent's raw output, a run is byte-identical: loops run in fixed id order, money is integer cents, and every random draw comes from a dedicated seeded stream, so that conditions sharing a seed share draws (`engine/bazaar.py:12-14`; `docs/log_schema.md`).

| Stream | Seed sequence | Code |
|---|---|---|
| world, routes, people, detection, treatments, inspectors | `[day root, 0..6]` | `engine/bazaar.py:81-86` |
| observed-profile noise | `[day root, 4, stall index, person index]` | `engine/bazaar.py:262` |
| agent's own stream | `[day root, 7, role (seller 0, buyer 1), index]` | `agents/registry.py:42` |
| person ids | `[day root, 8, kind, k, attempt]` | `engine/world.py:437` |
| day root | `[seed]` on day 1, `[seed, 9, day]` after | `engine/days.py:50-52` |
| type revision (brands off) | `[seed, 10, day, stall index]` | `engine/days.py:106` |
| rename | `[day root, 11, stall index, rename count]` | `engine/bazaar.py:573` |
| switch-supply quality | `[seed, 12, stall index]` | `engine/brands.py:331` |
| critics, critic ties, capture | `[day root, 13, critic]`, `[seed, 14]`, `[seed, 15]` | `engine/critics.py:65-100` |
| bargain hunters, consideration sets | `[day root, 16]`, `[day root, 18, buyer index]` | `engine/world.py:349`, `295` |
| licensing, white labels | `[seed, 19, owner]`, `[seed, 24, owner]` | `engine/licensing.py:104`, `110` |
| copied-name entry | `[seed, 23]` | `engine/brands.py:246` |
| random tie-break | `[seed, 29, day, buyer index]` | `engine/bazaar.py:224` |

An agent's randomness (the rule buyer's inspection draws, the random reference buyer) uses only its own stream and never touches an engine stream (`agents/registry.py:1-5`).

### 6.2 Replay

Every observation, raw output (with retry attempts and crash messages) and applied action is logged. `python -m cli.replay LOG` rebuilds the run from the header config and feeds the logged raw outputs back through `ReplayAgent`, keyed by (day, agent id) (`engine/runner.py:30-72`; `agents/registry.py:63-87`). This makes any finished run reproducible byte for byte, LLM runs included, without calling a model.

### 6.3 LLM agents at 1.0.0

`agents/llm_stub.py` is an adapter without a network call (`_call` raises `NotImplementedError`, `agents/llm_stub.py:92-95`). What is in place:

- a pinned `model_id`; aliases such as `latest` are refused (`agents/llm_stub.py:56-57`);
- sampling settings (`temperature` 0, `top_p` 1, `max_tokens` 256, `seed` passed through if the provider supports it), recorded in the log header with the system prompt (`agents/llm_stub.py:39-44`, `66-69`);
- a static system prompt per role with no market content; the observation goes in the user message as `json.dumps(obs, sort_keys=True)` (`agents/llm_stub.py:23-36`, `71-75`);
- no memory: each call sees only the current observation.

A live LLM run is not reproducible from config and seed alone, since provider outputs can vary. It is reproducible from its log.

### 6.4 Response cache keyed by the prompt: not implemented

There is no response cache in `engine/` or `agents/`. (The cache in `analysis/chainrun.py:60-105` stores finished chain results by job; it is not a model-response cache.) The contract an implementation must meet:

1. **Key.** A hash of the canonical JSON of everything that can change the response: provider, `model_id`, sampling (including `seed`), the system prompt, and the full message list (the observation as serialised by `build_messages`, plus any retry error text). Nothing else: no wall-clock time, run id or object identity.
2. **Hit.** Return the stored text unchanged, without a provider call, and record the hit in the attempt log.
3. **Miss.** Call the provider, write the entry to disk before returning, and never overwrite an entry: the first response wins.
4. **Effect.** The same prompt always gets the same reply, so the LLM becomes a deterministic policy. Observations carry the tick, ids and the stall's own ledger, so identical prompts arise mainly in paired conditions that share a seed, up to the tick where they diverge. There the cache gives both conditions the same replies, the LLM counterpart of shared random draws.
5. **Privilege.** The adapter's `meta()` must never declare `privileged`; the engine grants the oracle and the privileged seller block on that self-declaration (`engine/bazaar.py:183`, `672`).
6. **Spend.** A run-level call and cost ceiling, separate from the per-agent `max_calls` (open point 2).

## 7. Information an agent would see that a rule-based agent does not use

The observation depends on the engine state, the config and one flag from the policy (`privileged`). Every other policy of a role gets the same observation. So at 1.0.0 an LLM agent sees nothing a rule-based agent is not given. The differences are in what each reads.

| # | Decision point | Field(s) | Rule policy | Flag |
|---|---|---|---|---|
| 1 | buyer choice, search | `brand` on `stalls_here` and `seen_elsewhere` | ignored by `rule_buyer` | **Uses more.** A local or expert reads actual names, so an LLM could spot a copied name (one letter edit) of a name it saw earlier the same day. A tourist reads the original's name on a copy and cannot. |
| 2 | buyer choice, inspect | full `messages[]` history (all claims, channels, ticks, texts) | reads only the latest `claimed_quality` and whether any channel was yell or whisper | **Uses more.** A low-quality pitching stall can tell an expert-looking buyer the truth while its sign pitches, so one stall sends two different claims. An LLM can treat that as evidence; the rule buyer cannot. |
| 3 | buyer choice | `rating: null` (unrated) | read as 0.5 in ranking; never skipped by τ | **Uses more.** An LLM may treat a new or copied name (always unrated at first) with suspicion; the rule buyer treats it as neutral. |
| 4 | buyer search | `steps_away`, `seen_count`, `depth`, `route_end`, `actions_left_here`, `units_acquired`, `budget_cents`, `tick`, `you.id`, `category` | ignored | **Uses more** (walk-back distance, stop budget). |
| 5 | buyer inspect, choice | `you.inspect_prob`, `tie_rank` | read as policy parameters | **Policy input in the observation.** These are settings of the rule policy, not facts about the market. An LLM would see them without meaning (open point 13). |
| 6 | seller channel | `uniform`, `recent_catches`, `reopened_at_tick` | read only by `rule_deceptive_adaptive` | **Uses more** than `rule_honest` and `rule_deceptive`. |
| 7 | seller channel | `ledger`, `costs.*`, quality values and texts, `price_cents` | not read by any channel rule (v2 reads the penalty) | **Uses more.** |
| 8 | seller switch supply, exit | `horizon`, `yesterday`, `brand.rating`, `neutral_price_cents`, `bust_out_unit_cost_cents` | read only by the `rule_genuine_*` benchmarks | **Uses more** than the study rule sellers; with `market.horizon_known` every seller policy gets these fields. |
| 9 | seller rename | `brand.counterfeit_of`, `ledger`, `recent_catches` | `rule_deceptive` reads only `rename_available` and a fixed choice | **Uses more.** |
| 10 | seller channel, rename | within-day memory (whom it whispered, last yell, yell cooldown, home sign) | rule sellers keep it in the agent object | **Rule agent has more.** The seller observation carries no history of the stall's own actions; the LLM stub has no memory. |
| 11 | buyer choice; seller switch supply | `oracle`; `privileged` block | given only to `informed_reference` and `rule_genuine_rational_v2` | **Rule agent has more.** No study agent gets them. |
| 12 | seller (licensee or owner) | licence status, royalties | not in the observation | **Nobody sees it** (open point 11). |

No decision point gives an LLM agent information a rule-based agent *cannot* see. Rows 1 to 9 are information a rule agent is given but ignores; comparisons between LLM and rule agents should state that the LLM may use them.

## 8. Known rules of this world

Each is a deliberate design fact at 1.0.0, not an accident of the code.

1. **Lexicographic choice by displayed rating, then price.** A searching rule buyer that sees ratings picks the candidate with the highest displayed rating (unrated = 0.5), then the lowest price, then the tie-break; one that does not see ratings picks the lowest price (`agents/rule_based.py:453-458`; `docs/formal_model.md`, "Tie-break"). At search depth 1 (the engine default) the rule buyer acts at the cheapest candidate and uses ratings only as the τ threshold (`agents/rule_based.py:356-357`). This is a rule of the `rule_buyer` policy; the engine does not enforce it, and an LLM buyer may choose otherwise.
2. **Tourists cannot see ratings.** Their stall rows carry no `rating` key (`ratings.visible_to` defaults to local and expert, `engine/config.py:285`; `engine/bazaar.py:883-889`). The engine enforces it; `buyers.profile_overrides.reads_ratings` can change it per profile. Tourists also read the original's name on a copied name and file reviews under it (`engine/bazaar.py:250-255`).
3. **Prices are set mechanically from displayed ratings.** Each morning, round(base × tier × (1 + premium × (r̃ − 0.5))) from the displayed start-of-day rating; copies and licensees copy prices (`engine/brands.py:193-208`; `engine/licensing.py:135-140`). No agent sets a price. **Under test in Stage 3** (`sellers.price_policy`, engine 1.1.0).
4. **Perfect inspection.** An inspection reveals true quality exactly, at a fixed cost by profile, and never fails (`engine/bazaar.py:728-733`; `engine/world.py:395`).
5. **Star display.** With `ratings.display` `stars`, every rating a buyer, a price or a seller reads is rounded half up to `ratings.display_step` (0.02 = a tenth of a star); the stored rating and the logs stay unrounded (`engine/brands.py:109-118`). The engine default is `exact`; the 1.0.0 reference market uses stars at 0.02 (plan, Stage 2 item 2).
6. **Claims come from a two-item menu and the engine writes the text** (`engine/interface.py:9-13`; `engine/bazaar.py:246-248`).
7. **Unrated reads as 0.5 everywhere**: prices, buyer ranking, copy targets (`engine/brands.py:195`, `287-288`; `agents/rule_based.py:456`).
8. **Buyers are fresh each day and remember nothing across days**; agents are rebuilt each morning (`engine/days.py:5-12`).
9. **Sellers see a noisy profile and cannot tell an inspector from a buyer** unless it wears a uniform within recognition range (`engine/bazaar.py:257-265`, `807-809`).

## 9. Open points for 1.0.0

Found while writing this document. None is fixed here.

1. **No LLM call and no response cache.** The plan's determinism wording assumes a cache keyed by the prompt; none exists (section 6.4). An LLM battery (outside the current plan) needs both.
2. **`max_calls` is per agent-day, not per run.** The stub's docstring says "per run" (`agents/llm_stub.py:8-9`), but agents are rebuilt per stall and per buyer each day (`engine/bazaar.py:127-129`; `engine/days.py:186-189`), so the real ceiling is `max_calls` × agents × days. When the cap is hit, `act` returns the fallback as a valid string (`agents/llm_stub.py:81-83`), so `outcome.fallbacks` does not count it; only `raw.attempts` shows `skipped`. There is no run-level spend ceiling.
3. **LLM retries check the schema only.** State-invalid outputs (whisper out of range, over budget) go straight to fallback (`agents/llm_stub.py:86`).
4. **One `agents.params.llm` block for both roles** (`agents/registry.py:43`, `49-50`): seller and buyer LLMs cannot have different models or sampling.
5. **Loaded words on the wire.** `bust_out`, `rename: "counterfeit"`/`"lookalike"`, `stall_type: "deceptive"`, `counterfeit_of`, `busted_day`, `bust_out_unit_cost_cents`. The seller system prompt embeds the schema verbatim (`agents/llm_stub.py:30-35`), so an LLM would read them. Renaming changes log bytes; an adapter-level alias layer (neutral names in the prompt, mapped to wire names) avoids that.
6. **The seller system prompt describes only yell, whisper and answer** (`agents/llm_stub.py:31-34`); sign, rename, switch supply and exit are in the schema but not explained. The buyer prompt does not explain `choose`, `candidates` or the phases.
7. **An invalid action uses up one-time chances.** With brands on, the rename chance and the day's switch-supply chance are cleared after the turn even when the action fell back (`engine/bazaar.py:403-409`). Decide whether that is intended.
8. **Whole-action rejection.** One bad sub-field (a whisper target out of range) discards valid answers and any rename or exit in the same action (`engine/interface.py:5-7`). Deliberate, but much costlier for an LLM than for a rule agent.
9. **`docs/log_schema.md` observation sections are out of date.** Seller: missing `brand`, `horizon`, `yesterday`, `privileged`, `ranges.whispers_allowed`. Buyer: missing `own_assessment`, `rating`, `tie_rank`, `search`, `you.inspect_prob`; still says "perfect-information reference buyer" (now `informed_reference`).
10. **A copied-name rename with no eligible original** gets a new name but is logged with `how: "counterfeit"` and counted in `renames_by_how.counterfeit` (`engine/bazaar.py:575-590`, `1080`).
11. **Licensees and owners are blind to their licence.** The seller observation has no licence status, royalty rate or royalties, and its `ledger` omits royalties (and unit costs), so a licensee cannot compute its own profit (`engine/bazaar.py:793-834`).
12. **Scope of rule 1.** The plan states lexicographic choice without qualification; in code it holds only for searching buyers (`search_depth` > 1 or `choice_set`). The reference market (choice set m 3) is searching, so it holds there.
13. **Policy parameters in the observation.** `you.inspect_prob` and `tie_rank` steer the rule buyer but would reach an LLM as unexplained numbers. Before LLM buyer runs, either drop them from the LLM's prompt or explain them.
14. **Star display is not the engine default** (`ratings.display` `exact`, `engine/config.py:301`). `configs/reference_1_0.yaml` (Stage 2 item 2) does not exist yet in this checkout; rule 5 depends on it setting `stars` at 0.02.
