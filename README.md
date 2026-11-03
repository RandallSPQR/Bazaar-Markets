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
agents/    rule_based.py, reference.py (random floor, perfect-information ceiling), llm_stub.py, registry.py
cli/       run.py, sweep.py, replay.py, m0_regression.py
tests/     test_m0.py, test_invariants.py, test_bazaar_sanity.py, reference/sim_prototype.py
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

About 70 s. The suite covers:
- an exact port check against the prototype;
- the M0 regression;
- the accounting identity;
- determinism and byte-identical replay;
- hostile agents unable to change ground truth;
- the bazaar sanity checks;
- the LLM stub's guards.

## M0 regression

```bash
.venv/bin/python -m cli.m0_regression           # baseline + redraw at 5%, seeds 0-5
.venv/bin/python -m cli.m0_regression --sweep   # plus the enforcer-rate sweep
```

In `enforcer_mode=fixed`, M0 consumes random numbers in the same order as the
prototype and reproduces its per-generation history exactly
(`tests/test_m0.py`). Results, seeds 0–5, mean over generations 221–250, 95% t-interval:

| condition | this repo | prototype |
|---|---|---|
| fixed enforcers, 5%, r_min 0.02 | 74.7% [65.3, 84.1] | 70% [60, 79] |
| redraw per impression, 5% | 0.6% [−0.2, 1.4] | ~0% |
| redraw 1% / 2% / 3% / 4% | 79% / 41% / 2.7% / 0.7% | majority ends between 2% and 3% |

Notes:
- **Baseline seeds.** Seeds 0–5 happen to land high. Over 20 seeds the
  prototype averages about 69%, and seeds 12–17 give 70.0% [60.1, 79.9]. The
  pass rule is: the 6-seed mean lies inside [60, 79], and the intervals overlap.
- **Redraw is a reconstruction.** `tighten.py` was not available, so redraw
  draws each impression's enforcer status from a separate stream (seed, 1).
  This keeps the main stream paired with the baseline. It reproduces ~0% at 5%.
  It places the 50% crossing between 1% and 2% (41% at 2%), slightly below
  the reported 2–3%. The analytic break-even is e\* = 3.2%. If `tighten.py`
  turns up, diff its redraw against `engine/m0.py`.

## A sample bazaar run

```bash
.venv/bin/python -m cli.run --mode bazaar --seed 0 --log runs/sample_bazaar_s0.jsonl --normalize
.venv/bin/python -m cli.replay runs/sample_bazaar_s0.jsonl      # -> REPLAY OK: N lines identical
```

`--normalize` reruns the same world and seed twice more: once with the random
buyer (floor) and once with the perfect-information buyer (ceiling). It adds
`surplus_norm` and `shortfall_norm`, where 0 = random and 1 = perfect.

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
  from its own menu (`truth` or `pitch`). It cannot write free text or set a
  price.
- **Buyers.** Buyers walk seeded routes with a task (X units at Q ≥ Q_req
  within budget B). At stalls of their category they ask, inspect (costly;
  reveals Q), buy, or move on. Sellers see a noisy profile and never an
  inspector flag.
- **Inspectors.** Count, placement and feature correlation are dials. When an
  inspector perceives a false claim (including a whisper or answer to a
  disguised inspector or an inspector-buyer), the engine draws detection from
  `detection.form`. A catch charges penalty P and closes the stall for
  `close_ticks`.
- **Money.** Money is integer cents, so Σ payments = Σ seller revenue holds exactly.

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
