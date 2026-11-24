# Changelog

Engine versions. A version is bumped whenever a change can alter the log for the same config, seed and agent outputs. New behaviour
is off by default. From 0.11.0 on, each version reproduces the previous one at its defaults, with two exceptions: 0.14.0
fixes two search bugs (runs where neither occurs reproduce 0.13.0) and, like 0.15.0, adds outcome keys. Commits are
the post-2026-11-19 hashes (old hashes map through `docs/commit_map.tsv`). The full notes for each version are in
`engine/__init__.py`.

| Version | Date | Commit | Change |
|---|---|---|---|
| 1.2.0 | 2026-11-24 | (this commit) | Plan 2026-11-23, Stage 1. `sellers.undercut_floor_markup` (undercut's floor at round half up(unit cost × (1 + m)); 0 = 1.1.0). A run-level LLM spend ceiling (`agents.budget`, `engine/budget.py`): calls, tokens and dollars per run, dollars per day across runs through `runs/llm_ledger.jsonl`, a per-model price table (placeholders), every limit 0 and no call without `--allow-spend`; free response-cache hits; a refused or capped call counts as a fallback and stops the run, marked INVALID: budget; `--dry-run-cost`. Seller option sets (`engine/checkpoint.py` `OPTION_SETS`; v2 leaves out the contract licence). Defaults reproduce 1.1.0 byte for byte. |
| 1.1.0 | 2026-11-20 | 9f99d3b | Stage 3A. Seller price policies (`sellers.price_policy`: rating_indexed, cost_plus, match_rival, undercut, promo; `sellers.markup`), logit buyer choice (`buyers.choice`, `logit_rating_weight`, `logit_price_weight`), checkpoint and continue (`engine/checkpoint.py`: snapshot after day d, continue on fresh streams [seed, 31, k] or the original ones, bit for bit) and seller options for one stall (switch now / +5 / +10, licence 6 contract or cheap, exit). Defaults reproduce 1.0.0 byte for byte. Scaling rules for the new fields added after the full suite (no behaviour change). |
| 1.0.0 | 2026-11-20 | fad17c6 | Frozen rule-based baseline. One fix: a counterfeit of a white label's name follows the white label's price (formal-model check C1; no published run reaches it). `configs/reference_1_0.json` (the reference market) with one named variant per published run since verification (`configs/reference_1_0_variants.json`); `tests/reference/v1_0_0` digests of 576 chains of every published run since 0.14.0, each matching its saved record; formal model cross-checked against the code (`runs/formal_model_check.md`); `docs/agent_interface.md`; `runs/BASELINE_1_0_0.md`. |
| 0.21.0 | 2026-11-19 | 4a83784 | `buyers.profile_overrides`: per profile or for bargain hunters, whether buyers read ratings and how often they inspect. |
| 0.20.0 | 2026-11-18 | bc54ac0 | Star display (`ratings.display`, `display_step`) and random tie-break among equal (rating, price) stalls (`buyers.tie_break`). |
| 0.19.0 | 2026-11-17 | e26fb11 | `ratings.prior_scope`: the rating prior can reach only names created after day 1; 60-day markets checked end to end. |
| 0.18.0 | 2026-11-16 | 093f582 | `licensing.white_label_tier` and `ratings.prior_n` (pseudo-reviews at 0.5 that fade with rating memory). |
| 0.17.0 | 2026-11-12 | b309936 | Counterfeit entry by day (`brands.counterfeit_entry`), counterfeit price factor, white-label licensing. |
| 0.16.0 | 2026-11-11 | 6e0b3b2 | Licensing: owners license their name to other stalls (cheap or contract quality), royalties, optional owner liability. |
| 0.15.0 | 2026-11-10 | 88d88d6 | Liability dials: `inspectors.detect_scale`, penalty lag, uncollectible fines, seller exit. |
| 0.14.0 | 2026-11-09 | 2eb4b42 | Fixes for trapped and parked searching buyers; stuck and idle-chooser guards in the outcome. |
| 0.13.0 | 2026-11-08 | c4645bd | Verification dial: local and expert inspection probabilities; validated benchmark candidates. |
| 0.12.0 | 2026-11-08 | 7c25ddd | Choice-set demand with position rent; bust-out benchmark candidate days. |
| 0.11.0 | 2026-11-07 | 2f41abc | Critics, inspector capture, bargain hunters, ex-post best bust-out benchmark. |
| 0.10.0 | 2026-11-06 | c73abb3 | Buyer search depth (browse k stalls, then choose) and search logs. |
| 0.9.0 | 2026-11-06 | d6488e7 | "Look-alike" renamed "counterfeit"; budget override; penalty-aware benchmark seller. |
| 0.8.0 | 2026-11-06 | 02f4967 | Brands: ratings by name, renames at reopening, copied names, reputation premium; bust-out action. |
| 0.7.0 | 2026-11-05 | b3a0c18 | Public ratings, switching costs, whisper switch, rug-pull logging. |
| 0.6.0 | 2026-11-05 | ec24f90 | Multi-day markets with entry and exit by imitation; per-day seed streams. |
| 0.5.0 | 2026-11-05 | a2e77ad | Grid refinement (`market.scale`); whisper cooldown for rule sellers. |
| 0.4.0 | 2026-11-05 | 18fcbf3 | Inspector recognition range and disguised full-shift option. |
| 0.3.0 | 2026-11-05 | d7f8828 | Uniformed inspectors, seller signs, public catch notices, reach diagnostics. |
| 0.2.0 | 2026-11-03 | c166a9a | Selection, tie-break and cap options; treatment-stable populations and ids. |
| 0.1.0 | 2026-11-03 | 31a2a25 | First engine: M0 regression mode and the bazaar. |
