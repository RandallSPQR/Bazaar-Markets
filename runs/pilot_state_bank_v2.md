# Bank v2 pilot (plan 2026-11-23, Stage 3)

Engine 1.2.0, commit 78cde4e, `analysis/state_bank_v2.py` sha256 b5a0362f…48760d (unchanged since d56a6f6). nice 19, 4 workers, `caffeinate -i`, `--min-swap-mb 0` (D3). Log: `runs/state_bank_v2/state_bank_v2_run.log`; gates: `runs/state_bank_v2/pilot_gates.json`.

- **Design** (DESIGN_SEED 20261123, attempt 1): 24 distinct markets. Each level appears 8 times (tourist share, detect_scale) or 12 times (local inspection, prior_n, owner_liable, counterfeits); the plan asks for at least 4.
- **Enumeration** (2,400 chains, 3.07 h): 172,800 states. The 12 markets without counterfeits have no states below a 1.0 rating, so 36 strata are non-empty (24 top, 12 below), and the below band comes only from markets with counterfeits.
- **Pilot** (one state per non-empty stratum, 36 states, K 30, 5,400 continuations, 6.11 h): 18 pay, 12 below, 5 close calls.

| Gate | Rule | Result |
|---|---|---|
| G1 | The pipeline runs end to end | Pass |
| G2 | 3 states reproduce on the original streams | Pass, 3 of 3 |
| G3 | ≤ 36 h, blocks ≤ 10 h; cut to 240, then 200 | Pass on total: N 300 projected 29.6 h at K 20. Block limit: see D5 |
| G4 | Expected close calls ≥ 60 | Pass: 139.8 expected at N 300 |
| G5 | Guards 0 | Pass: stuck 0, idle 0, fallbacks 0 |
| G-leak | No single feature above 80% cross-validated accuracy on the full observation set | Pass: best `units_7d` 77.8% (AUC 0.81); n 36, base rate 50%; the reduced set gives the same best feature |

K: the split-half rule picked K 20 (best-option agreement 25/25 at K 10, 26/26 at K 20, 30/31 at K 30).

**Allocation at N 300** (the prespecified rule: greedy on shrunk close-call rates, repaired for the band and pays constraints):
- **Concentrated:** `t40|li1|ds1|pn10|ol0|cf1#below` gets 176 states, `t100|li0.5|ds0.1|pn10|ol1|cf1#top` gets 56, and the other 34 strata get 2 each.
- **Why:** the five strata whose single pilot state was a close call carry a shrunk close-call rate of 0.57; every other stratum carries 0.07.
- **Expected bank:** 40% pays, 66% below, 140 close calls.
- **How estimates are corrected:** estimates use weights = pool / drawn.
- **What it costs:** per-market reading is limited to the two large strata.

**D5 (block limit).** The script groups whole markets into blocks in design order. The concentrated market alone projects 19.7 h, so its block is over the plan's 10 h limit; the script's G3 check tested only the 36 h total. The cache resumes chain by chain, so block 2 runs as two launches of at most 10 h each (the first is stopped at 10 h and the second resumes from the cache). Nothing in the design, states, K or analysis changes. Blocks: 1 (1 market, 2 states, 0.1 h), 2 (1 market, 178 states, 19.7 h, in two launches), 3 (22 markets, 120 states, 9.8 h).
