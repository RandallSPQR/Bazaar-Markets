# Bazaar Markets: the agentic ad engine

A deterministic market simulation for research on deceptive advertising and AI
agents. It extends Don Marti's 2018 model of honest vs deceptive advertisers.
The engine owns ground truth and accounting. Agents (rule-based now, LLMs
later) act only at decision points, through a role-specific JSON observation
and a schema-validated JSON action.

This phase contains:
- the M0 compatibility mode (an exact port of the prototype `sim.py`) and its regression;
- the bazaar world;
- rule-based and reference agents, and an LLM adapter stub that makes no calls;
- replayable JSONL logs;
- a playback viewer.

## Layout

```
engine/    m0.py (prototype port), bazaar.py (engine loop), world.py, detection.py, valuation.py,
           interface.py (action schemas, parse/fallback), config.py, jsonlog.py, metrics.py, runner.py
agents/    rule_based.py, reference.py (random and informed reference buyers), llm_stub.py, registry.py
cli/       run.py, sweep.py, replay.py, m0_regression.py
tests/     test_m0.py, test_invariants.py, test_bazaar_sanity.py, test_visibility.py, test_recognition.py,
           reference/ (prototype copies, 0.3.0 outcomes)
analysis/  run scripts (placement_sweep.py, visibility_adaptivity.py, ...); outputs in runs/
docs/      log_schema.md, config_reference.md
viewer/    index.html (canvas playback of engine logs, plus a demo mode)
configs/   m0_baseline.json, m0_redraw.json, bazaar_default.json
```

## Setup

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python numpy jsonschema pytest
```

All commands below run from the repo root with `.venv/bin/python` (or an activated venv).

## Tests

```bash
.venv/bin/python -m pytest -q
```

About 100 s. The suite covers:
- exact port checks against both prototype versions;
- pinned M0 regression values (default config);
- the accounting identity;
- determinism and byte-identical replay;
- hostile agents unable to change ground truth;
- the bazaar sanity checks;
- the LLM stub's guards.

## M0 regression

```bash
.venv/bin/python -m cli.m0_regression                # compatibility + scientific check (30 seeds)
.venv/bin/python -m cli.m0_regression --compat-only  # exact prototype agreement only
```

Two separate checks:

1. **Compatibility (exact).** With `tie_break=numpy_default`, the port reproduces
   each bundled prototype's per-generation history bit for bit:
   `tests/reference/sim_prototype.py` (v0, the original idle rule, via
   `selection=prototype_v0`) and `tests/reference/sim_prototype_v1.py` (v1, the
   corrected idle rule that every doc result used; the default `selection`).
   `enforcer_mode=redraw_main` reproduces `tests/reference/tighten_v1.py`'s
   mechanism test exactly. Exactness holds on one platform only: the
   prototypes' default `argsort` breaks ties among idle firms differently on
   different numpy builds.
2. **Scientific check (tolerance).** The default config (stable ties, so
   identical on every platform; separate-stream redraw) is compared with the
   published numbers. Rule, prespecified: the 30-seed mean must be within 0.05
   of 0.695, and the redraw mean must be below 0.05. 0.05 is the smallest
   difference treated as substantive; with an across-seed SD of about 0.10, 30
   seeds give a 95% half-width of about 0.04, so the rule is testable. The
   published 0.695 is itself a 6-seed estimate.

Current result (seeds 0–29, generations 221–250, 95% t-interval):

| condition | this repo (default) | published |
|---|---|---|
| fixed enforcers, 5%, r_min 0.02 | 70.3% [66.4, 74.1] | 69.5% [60, 79] (6 seeds) |
| redraw per impression, 5% | 1.0% [0.6, 1.4] | ~0% |

Sensitivity of the baseline (paired seeds):
- tie order, stable vs numpy default: +4.1 points [−0.5, +8.6], 30 seeds;
- cap enforcement, strict vs batch: +4.5 points [−0.6, +9.7], 20 seeds.

Notes on M0 definitions:
- **Selection rule.** `idle_lowest` ranks firms that won nothing below every
  active firm, loss-makers included. This favors participation even when it
  loses money; it is a selection assumption, tested in the doc's sensitivity
  table, not a neutral default. `prototype_v0` is kept for historical comparison.
- **Impression cap.** `cap_mult` sets an impression limit, not a money budget.
  The prototypes check it once per batch of T/40 impressions (`cap_mode=batch`,
  a soft limit whose overshoot is logged as `cap_overflow`); `cap_mode=strict`
  enforces it per impression.
- **Realized sales.** Logged `sales` use the accounting definition: within sale
  distance, excluding deceptive impressions that reached an enforcer.

## A sample bazaar run

```bash
.venv/bin/python -m cli.run --mode bazaar --seed 0 --log runs/sample_bazaar_s0.jsonl --normalize
.venv/bin/python -m cli.replay runs/sample_bazaar_s0.jsonl      # -> REPLAY OK: N lines identical
```

`--normalize` reruns the same world and seed twice more: once with the random
reference buyer and once with the informed reference buyer. It adds
`surplus_rel` and `shortfall_rel`, where 0 = random reference and 1 = informed
reference. These are comparison points, not bounds: scores can fall below 0 or
above 1, and raw outcomes stay primary.

Compare conditions over seeds. Seeds are paired across conditions:

```bash
.venv/bin/python -m cli.sweep --mode bazaar --grid inspectors.count=0,2,6 --seeds 6 --normalize --out runs/insp.json
.venv/bin/python -m cli.sweep --mode m0 --grid enforcer_mode=fixed,redraw --grid f_enf=0.02,0.03,0.05 --seeds 6
```

Bazaar outcomes vary a lot between seeds, because each seed is a different
world. Read the paired differences ("diff vs first"), not overlapping
per-condition intervals.

## Viewer

Open `viewer/index.html` in a browser (or serve the repo:
`.venv/bin/python -m http.server` and visit `/viewer/`). The page:
- starts in demo mode, which uses its own illustrative JS rules (not the engine);
- loads any engine log through **Load engine log**;
- plays bazaar logs on the market grid;
- shows M0 logs as a deceptive-share-over-generations chart.

The original `bazaar.html` was not available, so this is a new page with
both modes drawn by one renderer.

## How the bazaar works (short)

- **Stalls.** 48 stalls in three aisles (fish, electronics, designer).
  `market.clustering` sets how strictly categories keep to their own aisle.
  Each stall is genuine (high Q, truthful), honest seconds (low Q, truthful,
  cheaper), or deceptive (low Q, claims high Q, priced like genuine). Brands
  and spec lines are fictional.
- **Messages.** A sign is seen once by passers-by in sight range. A yell is a
  broadcast to everyone in earshot. A whisper is private to one passer-by. An
  answer replies to an ask. A seller picks a channel, a target, and a claim
  from its own menu (`truth` or `pitch`). It can also set its sign to `truth` or `pitch`.
  It sees passers-by (a uniform if one is worn, never an inspector flag) and public
  notices of recent catches nearby. It cannot write free text or set a
  price.
- **Buyers.** Buyers walk seeded routes with a task (X units at Q ≥ Q_req
  within budget B). At stalls of their category they ask, inspect (costly;
  reveals Q), buy, or move on. Sellers see a noisy profile and never an
  inspector flag.
- **Inspectors.** Count, placement, feature correlation, visibility
  (`inspectors.uniformed`, `inspectors.recognition_range`) and, for disguised
  inspectors, shift length (`inspectors.disguised_shift`) are dials. When an
  inspector perceives a false claim (including a whisper or answer to a
  disguised inspector or an inspector-buyer), the engine draws detection from
  `detection.form`. A catch charges penalty P and closes the stall for
  `close_ticks`.
- **Money.** Money is integer cents, so Σ payments = Σ seller revenue holds exactly.
- **Grid scale.** `market.scale = k` refines space and time together (cells and ticks 1/k
  as large, real speeds unchanged); config values stay in real units. See
  `docs/config_reference.md` for the list of scaled parameters.
- **Days.** `market.days = D` runs D bazaar days with fresh buyers each day; between
  days genuine and deceptive stalls switch type by pairwise proportional imitation
  (`evolution`; `engine/days.py`). Multi-day logs replay like single-day ones.
- **Reputation and medium.** Optional public ratings (`ratings`), switching costs
  (`pricing.switch_cost_to_*`) and a whisper ban (`market.whispers_allowed`); all off by default.

## Agents and the LLM stub

Rule-based agents return JSON strings and go through the same
parse/validate/fallback path an LLM would.

`agents/llm_stub.py` has the full wrapper:
- a pinned `model_id` (aliases refused);
- sampling settings, logged in the header;
- retries that send the validation error back to the model;
- every attempt logged;
- hard caps (`max_tokens`, and a `max_calls` kill switch).

`_call` raises `NotImplementedError`: no LLM calls in this phase. Before
enabling it, set a provider-side spend limit and a per-run budget.

## Open decisions

The three research choices below have labelled placeholder defaults (see
`docs/config_reference.md`):

| choice | default |
|---|---|
| detection form | `graded` |
| inspector–feature correlation | 0 |
| value function V(Q) | `step_salvage` |

Calibration choices made only so the sample run isn't degenerate:
- 2 inspectors on fixed posts;
- ad costs of 0.2% and 0.4% of base price;
- sellers yell at most every 8 ticks.
