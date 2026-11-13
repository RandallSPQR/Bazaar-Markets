# Pilot gate: Canal Street and Brand Equity

Engine 0.17.0 (e9cdc07); run scripts at 5458448. Seeds 900–902, both runs, every condition; 4 workers, nice 19.
Command: `PYTHONPATH=. .venv/bin/python -m analysis.pilot_canal_equity --ref 60f1ddf --tests "1109 passed, 17 skipped at e9cdc07 (runs/tests_0170.log)"`.
Started 2026-11-12 23:15, gates at 23:35 (log `runs/pilot_canal_equity/pilot_run.log`; details
`runs/pilot_canal_equity/pilot_gates.json`). Load average 2.7 at start, 6.2–6.5 during (other work on the machine).

Tests: 1109 passed, 17 skipped at e9cdc07 (`runs/tests_0170.log`). Every 0.16.0 reference cell (110, at 60f1ddf)
reproduces byte for byte with the new keys at their defaults.

**Result: G1–G5 pass.** The main runs are prepared, not launched.

| Gate | Result | Detail |
|---|---|---|
| G1 pipeline end to end | pass | Canal Street 60 chains, Brand Equity 90 (78 + 12 royalty-check chains); both summaries render (`runs/pilot_canal_equity/canal/canal_street_summary.md`, `runs/pilot_canal_equity/equity/brand_equity_summary.md`); 0 flags in each |
| G2 identities | pass | (a) Canal Street counterfeits-off chains = 0.16.0 never chains (60f1ddf, git worktree), full-outcome digest: 12/12; Brand Equity pilot never chains: 6/6. (b) Brand Equity never chains at seeds 250–252 = the licensing run's never chains: totals, day units and day ratings of the 3 sampled stalls equal `runs/licensing_cache.jsonl`, and full-outcome digest equal to 0.16.0, 6/6. (c) J identity to the cent in 108/108 owner-chains; name-effect split residual ≤ 5e-10 cents. Royalty no-decision check (seed 900, t100, both qualities, 3 owners, 0.05 and 0.25 against 0.10): 12/12 identical on all 30 days except royalties and profit; recompute exact |
| G3 timing | pass | Projected on 4 workers at nice 19 from the pilot's throughput (load ≈ 6): Canal Street 600 chains × 6.7 s = **1.12 h**; Brand Equity 792 chains × 7.1 s = **1.56 h**; queue **≈ 2.7 h**. Both ≤ 5.5 h; no seed cut |
| G4 counterfeits trade | pass | At φ 1.0, t100, every seed has counterfeit sales (3/3 at detect_scale 0 and 1). **Reported, design unchanged:** every φ 0.4 cell has counterfeits priced below unit cost on more than 10% of stall-days (t100 ds0 94%, t100 ds1 70%, t40 ds0 80%, t40 ds1 65%); φ 0.6: 0–4%; φ 0.8 and 1.0: 0% |
| G5 guard | pass | 156 pilot chains (both runs and the G2 chains): stuck 0, parked 0, idle choosers 0; invalid actions 0 |

Units per counterfeit stall-day, days 2–30 (mean over 3 seeds):

| φ | t40, ds 0 | t40, ds 1 | t100, ds 0 | t100, ds 1 |
|---|---|---|---|---|
| 1.0 | 3.01 | 1.83 | 7.39 | 3.03 |
| 0.8 | 3.93 | 2.38 | 9.86 | 3.95 |
| 0.6 | 4.22 | 2.47 | 10.61 | 4.21 |
| 0.4 | 4.27 | 2.56 | 10.66 | 4.29 |

## Choices made in implementing the spec (for confirmation before launch)

1. **White-label prices use the stall type's tier.** As specified ("prices from that brand's own rating by the
   existing rule"), a white label posts base × its type's tier × (1 + premium × (rating − 0.5)). Licensees are
   seconds or deceptive stalls, so a seconds-type white label prices at 0.55 × base (unrated: $4.40 for fish)
   where the same stall in R posts the owner's price ($9.60 for a well-rated owner). The name effect's
   "licensee prices" part therefore includes this tier gap as well as the rating premium. The alternative (white
   labels priced at the genuine tier) needs a new engine key.
2. **"Off" = the licensing never chain.** Deceptive stalls carry no counterfeit name but still rename fresh at
   reopening, as in the licensing market; this is what G2 requires (off equals the 0.16.0 never chain). In "on",
   counterfeits never rename.
3. **Day-entry counterfeits claim the original's true quality** (their pitch quality is set to it), as for
   licensees. Reopen-mode counterfeits are unchanged (they keep their own pitch quality).
4. **Target = the top-rated genuine brand of the category**, unrated counting 0.5 (the existing convention); ties
   and the near-copy name edits come from `default_rng([seed, 23])`.
5. **Price acts by rank in the buyer rule.** Buyers take the qualifying stall with the highest visible rating, then
   the lowest price (tourists: lowest price). So any φ < 1 wins the same buyers from the original; lower φ adds
   units only through budgets. PK1's least-squares slope is fitted over that response as specified.
6. **Copied originals** = genuine stalls copied by at least one counterfeit (fixed on day 2 by day-1 ratings, so
   the same set at every φ). PK4 is evaluated at both detect_scales (ds 1 is the cell of the confirmatory
   predictions).
7. **Name-effect split.** Owner own sales (revenue − cost − ad spend), licensee sales ((units R − units W) × (mean
   price W − unit cost)), licensee prices (units R × (mean price R − mean price W)), licensee ad spend, fines; the
   parts add up exactly (an ad-spend part was added so they do).
8. **Royalty check seed** = the first main seed (300), as the licensing checks used one seed.
9. **The queue stops on flags.** Canal Street exits non-zero on any flag (guard, invalid action, counterfeit or
   ledger check) and Brand Equity on a failed royalty check, so neither result is built on a failed check.

## Launch

```
nohup sh runs/queue_canal_then_equity.sh > runs/queue_canal_then_equity.log 2>&1 &
```

Canal Street runs first (seeds 270–299), then Brand Equity (seeds 300–329). Run logs: `runs/canal_street_run.log`,
`runs/brand_equity_run.log`; stdout `runs/canal_street_stdout.log`, `runs/brand_equity_stdout.log`; queue log
`runs/queue_canal_then_equity.log`. Summaries: `runs/canal_street_summary.md`, `runs/brand_equity_summary.md`
(reading and caveats to be written after the results).
