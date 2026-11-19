# Bazaar Markets: The Agentic Ad Engine

A deterministic market simulator for studying deception, verification and brand value, built as an evaluation environment for AI agents.

**Main result so far:** in this market, deception is bounded by verification. Once about a third of buyers check what they buy, cashing in a good name stops paying, and enforcement does the same job where buyers don't check. A brand's reputation earns money only while rivals are still building theirs.

> Status: engine v1.0.0 is the frozen rule-based baseline. All agents are rule-based. LLM agent experiments are in progress and will be compared against v1.0.0.

## What it is

A bazaar of stalls selling fish, electronics and designer goods. Stalls are genuine, seconds (honestly labelled lower quality) or deceptive. They advertise by sign, yell, whisper and answer. Buyers (tourists, locals, experts, bargain hunters) compare stalls, read star ratings and sometimes inspect before buying. Inspectors patrol, stand on posts or work disguised; a catch fines the stall and closes it. Brands can be built, licensed, copied or cashed in.

The market engine is deterministic. Agents act only at decision points, so any agent (a rule, a human, or an LLM) can be dropped into the same market and compared on paired seeds.

## Findings (v1.0.0, rule-based agents)

Each finding, its run, its estimate and its status (prespecified and supported, exploratory, or provisional) is listed in [`runs/BASELINE_1_0_0.md`](runs/BASELINE_1_0_0.md). The headlines:

- **Verification sets the boundary for cashing in a brand.** With no inspectors, a stall that switches to cheap goods under its good name gains when no buyer checks and loses once about a third do.
- **Enforcement substitutes for verification,** and raises honest sellers' profit by closing deceptive stalls.
- **Enforcement leaks through gaps in space and time.** Fixed inspectors leave pockets; visible patrols get waited out.
- **Catch counts mislead.** Sellers who dodge inspectors earn more only by paying fewer fines.
- **A reputation is worth the head start it gives over rivals still building theirs** (provisional): about $190 for each day of head start here, and nothing once rivals show the same stars.

These are results of one stylized model, not claims about real markets.

## Quick start

    git clone https://github.com/RandallSPQR/Bazaar-Markets.git
    cd Bazaar-Markets
    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[test]"
    pytest                                   # full suite (about 1.5 h; slow reference tests included)
    python -m cli.run --config configs/bazaar_default.json --seed 0 --log runs/s0.jsonl

The last command runs one market and prints its outcome; the event log it writes opens in `viewer/index.html`.

Reproduce a published run, for example verification (stage A, about 7 h on 4 CPU workers; the summary and run record are written to `runs/`):

    python -m analysis.verification --stage A --seeds 200-219

Python 3.12, numpy 2.5. Chains are deterministic per seed; a run's record lists the engine, commit, command and seeds.

## How the research is run

- Every run has a written spec with predictions, committed before any run. The commit history is the preregistration.
- Pilot gates check identities, timing and guards before a main run.
- Results are paired by seed, with 95% intervals over seeds, unadjusted. Only prespecified predictions are confirmatory.
- Each summary in `runs/` has a run record, gates, a predictions table, a reading written after the results, and caveats.

## Repository layout

    engine/      market engine (deterministic)
    agents/      rule-based agents and the agent registry
    analysis/    one script per run
    cli/         run one configuration, sweeps, replay
    configs/     reference config and named variants
    runs/        run summaries, figures, plans, baseline manifest
    docs/        formal model, config reference, log schema, agent interface
    tests/       unit tests and frozen reference digests
    viewer/      browser viewer for engine logs

Large run caches are not in git; they are archived with each release (TODO: Zenodo link).

## For agent builders

See [`docs/agent_interface.md`](docs/agent_interface.md) for every decision point, what an agent sees, what it may return, and the deliberate rules of this world (for example: tourists cannot see ratings; prices follow displayed ratings).

## Origin

Inspired by Don Marti's posts on deceptive advertising and ad reform (blog.zgp.org), and by work on LLMs as simulated economic agents.

## Cite

    TODO: Zenodo DOI after the first public release.

## License

Code: MIT ([`LICENSE`](LICENSE)). TODO: docs and data (CC BY 4.0?).
