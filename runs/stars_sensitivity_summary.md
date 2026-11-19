# Star ratings: sensitivity of five earlier results (Run B)

**Exploratory. No predictions. Intervals are 95% t over seeds, unadjusted.**

## Design

- Engine 0.20.0: `ratings.display` stars rounds every rating a buyer, a posted price or a seller decision reads half up to `ratings.display_step`; `buyers.tie_break` random breaks ties on (visible rating, price) by a per-buyer, per-day random order of the stalls. Defaults reproduce 0.19.0 byte for byte. Background: `runs/brand_equity_speed_summary.md`.
- Stars arm: each study's own config plus `ratings.display=stars`, `ratings.display_step=0.02`, `buyers.tie_break=random`; everything else identical. The studies' own config builders and chain functions are used by import; the overrides are appended to every `load` call the study's config builder makes, and every engine a chain builds was checked to run with display stars, step 0.02, tie-break random (exact arm: exact, stall_id).
- Exact arm: saved chains (the original run's engine; reproduction at 0.20.0 checked below). Paired by seed: the stars chain for seed s has the same seed, stalls under test, candidates and options as the exact chain.
- Seeds: verification 200-209 (10); liability 230-239 (10); bustout 230-239 (10); canal 270-279 (10); licensing 250-259 (10).
- Chains per seed: verification 48 (A|t100, A|t40|l1, B|t100: never + 3 stalls × 5 bust-out days); liability 32 (collectible, t100, ds 0 and 1: never + 3 × 5); bust-out decomposition 4 (collectible, t40, ds 0: never + each stall's best candidate of the exact run, the same candidate in both arms); Canal Street 3 (off, φ 0.6, φ 1.0 at t100, ds 1); licensing 13 (never at t40, ds 1 + contract × 3 owners × 4 options at royalty 0.15, recomputed exactly at 0.10 as `analysis/licensing_checks.py` does).
- Endpoints and their sources are listed per study. Per seed as each study (mean over its 3 stalls, owners, deceptive stalls or copied originals); exact, stars and stars − exact paired by seed.
- Sign change: the means of exact and stars on opposite sides of 0. Verdict: the original rule applied to the 10-seed estimate (for endpoints without a prediction, the side of 0 the interval is on); verdict change compares exact and stars on the same seeds. The published estimate (more seeds) is shown for reference.

## Run record

- Engine `0.20.0`; commit `47634b06fb2109efdca31041bcf2a99a29ee5144`; uncommitted at run time: ['?? runs/brand_equity_stars.csv', '?? runs/brand_equity_stars.json.gz', '?? runs/brand_equity_stars_run.log', '?? runs/brand_equity_stars_stdout.log', '?? runs/brand_equity_stars_summary.md', '?? runs/pilot_stars/A/brand_equity_stars_cache.jsonl', '?? runs/pilot_stars/B/stars_sensitivity_cache.jsonl', '?? runs/pilot_stars/g2_cache.jsonl', '?? runs/pilot_stars/os_check/g2_macos27_cache.jsonl', '?? runs/queue_stars.log', '?? runs/stars_sensitivity_run.log', '?? runs/stars_sensitivity_stdout.log']
- Script sha256 `f9dbd83be46d8fbde6dd7824d13a510b23aa4d8595f697a4dfbe1efce3dc1ce0`
- Command: `python -m analysis.stars_sensitivity --repro-file runs/pilot_stars/stars_sensitivity_repro.json --seeds-per-study 10 --workers 4 --min-swap-mb 0 --tests Engine 0.20.0 (952af31): full suite 1602 passed, 17 skipped, 1 failed (missing scaling rules, fixed); rerun of test_scale.py and test_v0200.py 222 passed (runs/tests_0200.log) --gate Pilot gate G1–G5 passed (runs/pilot_stars.md); G3 cut waived by the user for the full design (step 0.1 cells on, Run B 10 seeds per study)`
- Tests: Engine 0.20.0 (952af31): full suite 1602 passed, 17 skipped, 1 failed (missing scaling rules, fixed); rerun of test_scale.py and test_v0200.py 222 passed (runs/tests_0200.log)
- Gate: Pilot gate G1–G5 passed (runs/pilot_stars.md); G3 cut waived by the user for the full design (step 0.1 cells on, Run B 10 seeds per study)
- Python 3.12.7, numpy 2.5.4, macOS-27.2.1-arm64-arm-64bit
- Chains run by this script: 1000 (0 of them from its cache); saved exact chains used: 1000; 4 workers (nice 19); wall clock 1.90 h; load average [5.27, 5.6, 5.6] at start, [5.14, 5.69, 5.8] at end; memory at start {'swap_free_mb': 0.0, 'free_pct': 82}, at end {'swap_free_mb': 0.0, 'free_pct': 79}; memory-guard pauses: 0
- Flags: 0

## Checks

**Endpoint definitions.** Each endpoint recomputed by this script from the saved chains over the study's full original seed set, against the published value:

| Study | Endpoint | Seeds | Recomputed | Published | Equal |
|---|---|---|---|---|---|
| verification | A_t100 | 200-219 | +565.27 [+433.55, +697.00] * | +565.27 [+433.55, +697.00] * | yes |
| verification | A_t40l1 | 200-219 | −110.99 [−147.32, −74.66] * | −110.99 [−147.32, −74.66] * | yes |
| verification | B_t100 | 200-219 | −435.74 [−536.62, −334.87] * | −435.74 [−536.62, −334.87] * | yes |
| verification | PV4 | 200-219 | −1,001.02 [−1,212.14, −789.89] * | −1,001.02 [−1,212.14, −789.89] * | yes |
| liability | col_t100_ds0 | 230-249 | +564.45 [+434.09, +694.81] * | +564.45 [+434.09, +694.81] * | yes |
| liability | col_t100_ds1 | 230-249 | −389.04 [−492.70, −285.38] * | −389.04 [−492.70, −285.38] * | yes |
| liability | col_t100_ds1_minus_ds0 | 230-249 | −953.49 [−1,170.68, −736.30] * | not published (PL1 slope: −963.90 [−1,189.56, −738.24] * per 1.0 of detect_scale) | – |
| bustout | lost_inspected | 230-249 | −131.93 [−165.81, −98.04] * | −131.93 [−165.81, −98.04] * | yes |
| bustout | lost_rated_below | 230-249 | −14.35 [−42.50, +13.79] | −14.35 [−42.50, +13.79] | yes |
| bustout | gain | 230-249 | −93.57 [−122.56, −64.59] * | −93.57 [−122.56, −64.59] * | yes |
| canal | PK3 | 270-299 | −0.379 [−0.393, −0.365] * | −0.379 [−0.393, −0.365] * | yes |
| canal | PK2 | 270-299 | −369.83 [−457.80, −281.86] * | −369.83 [−457.80, −281.86] * | yes |
| licensing | con_unf_0.10 | 250-269 | +3,442.72 [+2,768.04, +4,117.41] * | +3,442.72 [+2,768.04, +4,117.41] * | yes |

**Reproduction of the saved exact chains at engine 0.20.0** (`--repro 4`, 2026-11-18 10:50:32, commit 84b7243): each chain rerun with defaults and compared with its cache record field by field (canal: including the sha256 of the full outcome).

| Study | Chains | Reproduced | Fields compared | Not in the saved record |
|---|---|---|---|---|
| verification | 4 | 4 | b, busts, cond, days, fallbacks, key, profile, seed, stage, stall, totals | – |
| liability | 4 | 4 | b, busts, cond, days, dec_catches, dec_stall_days, exited, fallbacks, fines, guard, key, market_fines, profile, seed, stall, totals | – |
| bustout | 4 | 4 | b, cond, days, exited, fines, key, seed, stall, totals, watch | – |
| canal | 4 | 4 | below_cost, catches, cf_fixed_ok, cond, copied, counterfeit_of, digest, guard, key, profile, profit_mismatch, rating, renames, seed, series, stalls | – |
| licensing | 4 | 4 | cond, dig_nonroy, dig_trade, key, kind, lic, meta, o, profit_mismatch, roy, roy_mismatch, royalty, seed, stall, totals, win | – |

## Verification

Original: `runs/verification_summary.md` (engine 0.13.0 (stage A) and 0.14.0 (stage B), seeds 200-219). Seeds here: 200-209 (10).

| Endpoint | Published (original seeds) | Exact | Stars | Stars − exact [95% t] | Sign change | Verdict: exact → stars | Verdict change |
|---|---|---|---|---|---|---|---|
| Stage A, tourists 1.0 (t100): gain (PV3) | +565.27 [+433.55, +697.00] *; PV3: supported | +491.51 [+305.75, +677.27] * | +466.72 [+311.48, +621.96] * | −24.79 [−155.67, +106.09] | no | supported → supported | no |
| Stage A, tourists 0.4, locals inspect: gain (an endpoint of PV1) | −110.99 [−147.32, −74.66] *; no prediction on this cell (interval below 0); PV1, which uses it, supported | −109.21 [−160.21, −58.21] * | −120.86 [−186.35, −55.37] * | −11.65 [−33.73, +10.43] | no | interval below 0 → interval below 0 | no |
| Stage B, t100: gain (PV3b, exploratory analogue) | −435.74 [−536.62, −334.87] *; PV3b: contradicted (interval on the opposite side of 0) | −435.32 [−602.92, −267.73] * | −473.04 [−626.62, −319.46] * | −37.72 [−117.12, +41.68] | no | contradicted (interval on the opposite side of 0) → contradicted (interval on the opposite side of 0) | no |
| t100: Stage B − Stage A (PV4) | −1,001.02 [−1,212.14, −789.89] *; PV4: supported | −926.84 [−1,260.63, −593.04] * | −939.76 [−1,238.61, −640.92] * | −12.93 [−139.25, +113.40] | no | supported → supported | no |

Sources: A_t100: analysis/verification.py:206 gains, :220 seed_mean, :304 PV3; runs/verification_summary.md:34, :44; A_t40l1: analysis/verification.py:206, :220, :253; runs/verification_summary.md:30, :42; B_t100: analysis/verification.py:206, :220, :304; runs/verification_summary.md:109, :119; PV4: analysis/verification.py:330 cross_stage; runs/verification_summary.md:165.

## Liability

Original: `runs/liability_summary.md` (engine 0.15.0, seeds 230-249). Seeds here: 230-239 (10).

| Endpoint | Published (original seeds) | Exact | Stars | Stars − exact [95% t] | Sign change | Verdict: exact → stars | Verdict change |
|---|---|---|---|---|---|---|---|
| Collectible, t100, detect_scale 0: gain | +564.45 [+434.09, +694.81] *; no prediction on this cell (interval above 0) | +642.09 [+426.09, +858.09] * | +606.73 [+440.29, +773.17] * | −35.36 [−195.81, +125.10] | no | interval above 0 → interval above 0 | no |
| Collectible, t100, detect_scale 1: gain | −389.04 [−492.70, −285.38] *; no prediction on this cell (interval below 0) | −470.04 [−649.47, −290.60] * | −447.11 [−590.53, −303.70] * | +22.92 [−45.16, +91.01] | no | interval below 0 → interval below 0 | no |
| Collectible, t100: gain at ds 1 − gain at ds 0 (two-level analogue of PL1; PL1 is a slope over {0, 0.1, 1}) | not published (PL1 slope: −963.90 [−1,189.56, −738.24] * per 1.0 of detect_scale); PL1: supported (a different statistic) | −1,112.13 [−1,485.42, −738.83] * | −1,053.84 [−1,344.18, −763.51] * | +58.28 [−121.78, +238.34] | no | supported → supported | no |

Sources: col_t100_ds0: analysis/liability.py:263 gains, :277 seed_mean, :297; runs/liability_summary.md:31; col_t100_ds1: analysis/liability.py:263, :277, :297; runs/liability_summary.md:33; col_t100_ds1_minus_ds0: per-seed difference of the two rows above; PL1 at analysis/liability.py:359, runs/liability_summary.md:47.

## Bustout

Original: `runs/bustout_decomposition.md` (engine 0.15.0 replay, seeds 230-249). Seeds here: 230-239 (10).

| Endpoint | Published (original seeds) | Exact | Stars | Stars − exact [95% t] | Sign change | Verdict: exact → stars | Verdict change |
|---|---|---|---|---|---|---|---|
| Collectible, t40, ds 0: b. lost: inspected and walked away | −131.93 [−165.81, −98.04] *; no prediction (interval below 0); the reading: the main cause of the loss | −166.94 [−219.51, −114.38] * | −161.22 [−237.20, −85.24] * | +5.72 [−46.29, +57.73] | no | interval below 0 → interval below 0 | no |
| Collectible, t40, ds 0: b. lost: rating below threshold | −14.35 [−42.50, +13.79]; no prediction (interval includes 0); the reading: "add little" | −26.93 [−87.85, +33.99] | −66.43 [−216.69, +83.83] | −39.50 [−128.84, +49.85] | no | interval includes 0 → interval includes 0 | no |
| Collectible, t40, ds 0: gain of the decomposed candidate (context) | −93.57 [−122.56, −64.59] *; no prediction (interval below 0) | −122.41 [−159.87, −84.94] * | −173.50 [−349.61, +2.61] | −51.10 [−207.19, +105.00] | no | interval below 0 → interval includes 0 | **yes** |

Sources: lost_inspected: analysis/bustout_report.py:56 cause, :70 decompose, :175 by_cond; runs/bustout_decomposition.md:32; lost_rated_below: analysis/bustout_report.py:56, :70, :175; runs/bustout_decomposition.md:33; gain: analysis/bustout_report.py:70, :175; runs/bustout_decomposition.md:40.

Units lost per stall-seed (exact / stars): inspected and walked away 6.6 / 6.4; rating below threshold 0.5 / 1.2. Largest |e| 0 / 0 cents; buyer records differing before the bust-out 0 / 0.

## Canal

Original: `runs/canal_street_summary.md` (engine 0.17.0, seeds 270-299). Seeds here: 270-279 (10).

| Endpoint | Published (original seeds) | Exact | Stars | Stars − exact [95% t] | Sign change | Verdict: exact → stars | Verdict change |
|---|---|---|---|---|---|---|---|
| t100, ds 1, φ 0.6: copied originals' day-30 rating, on − off (PK3) | −0.379 [−0.393, −0.365] *; PK3: supported | −0.371 [−0.395, −0.346] * | −0.367 [−0.392, −0.341] * | +0.004 [−0.003, +0.011] | no | supported → supported | no |
| t100, ds 1, φ 1.0: gap, 30-day (PK2) | −369.83 [−457.80, −281.86] *; PK2: supported | −303.63 [−458.51, −148.74] * | −372.19 [−547.61, −196.76] * | −68.56 [−290.23, +153.12] | no | supported → supported | no |

Sources: PK3: analysis/canal_street.py:190, :196, :229; runs/canal_street_summary.md:39; PK2: analysis/canal_street.py:185, :227; runs/canal_street_summary.md:38.

## Licensing

Original: `runs/licensing_checks.md` (engine 0.16.0 replay, seeds 250-269). Seeds here: 250-259 (10).

| Endpoint | Published (original seeds) | Exact | Stars | Stars − exact [95% t] | Sign change | Verdict: exact → stars | Verdict change |
|---|---|---|---|---|---|---|---|
| Contract, t40, ds 1, not liable: owner's gain over the options every licensee accepts, royalty 0.10, unfloored | +3,442.72 [+2,768.04, +4,117.41] *; no prediction (interval above 0); the BLUF's headline | +3,388.00 [+2,502.73, +4,273.26] * | +3,137.77 [+2,400.78, +3,874.76] * | −250.23 [−713.64, +213.18] | no | interval above 0 → interval above 0 | no |

Sources: con_unf_0.10: analysis/licensing_checks.py:339 _owner_rows, :443-452, :463; runs/licensing_checks.md:8, :435.

Share of licensees accepting at 0.10 (exact / stars): 0.990 / 1.000.

## Stuck, parked and idle buyers; invalid actions

Chains run by this script.

| Study · arm | Chains | Buyer-days | Stuck | Parked | Idle choosers | Invalid actions | Display/tie-break wrong | Schedule or identity fails | Seconds per chain |
|---|---|---|---|---|---|---|---|---|---|
| verification · stars | 480 | 2,160,000 | 0 | 0 | 0 | 0 | 0 | 0 | 27.6 |
| liability · stars | 320 | 1,440,000 | 0 | 0 | 0 | 0 | 0 | 0 | 27.1 |
| bustout · stars | 40 | 180,000 | 0 | 0 | 0 | 0 | 0 | 0 | 27.8 |
| canal · stars | 30 | 135,000 | 0 | 0 | 0 | 0 | 0 | 0 | 25.4 |
| licensing · stars | 130 | 585,000 | 0 | 0 | 0 | 0 | 0 | 0 | 26.5 |

## Flags

- none

## Reading (written after the results)

- **No earlier headline moves. Across 13 endpoints from five studies, stars change no sign and no prediction's verdict, and every paired difference's interval includes 0. One descriptive label changes: the bust-out decomposition's context gain goes from "interval below 0" to "interval includes 0". That comes from a wider interval, not a shift the paired difference can tell from 0. The rounding edge case that moved Brand Equity speed did not drive these results.**
  - **Verification:** PV3 (Stage A, t100) +$492 exact against +$467 stars, a difference of −$25 [−156, +106]. The PV1 cell (t40, locals inspect) −$12 [−34, +10]. PV3b (Stage B, t100) −$38 [−117, +42], still contradicted. PV4 (B − A) −$13 [−139, +113], still supported.
  - **Liability:** at t100, the gain at detect_scale 0 changes by −$35 [−196, +125] and at detect_scale 1 by +$23 [−45, +91]. The ds 1 − ds 0 contrast, a two-level analogue of PL1, is −$1,112 exact and −$1,054 stars, a difference of +$58 [−122, +238].
  - **Bust-out decomposition (t40, ds 0):** "inspected and walked away" remains the main cause of the loss: −$167 exact, −$161 stars, a difference of +$6 [−46, +58]. "Rated below threshold" grows from −$27 to −$66 (0.5 to 1.2 units per stall-seed), but the difference, −$40 [−129, +50], includes 0, and both intervals include 0. The decomposed candidate's gain is −$122 [−160, −85] exact and −$174 [−350, +3] stars. The difference is −$51 [−207, +105]; the label change is the stars interval widening past 0.
  - **Canal Street:** PK3, the copied originals' rating damage, is −0.371 exact and −0.367 stars, a difference of +0.004 [−0.003, +0.011]. PK2, the φ 1.0 gap, is −$304 exact and −$372 stars, a difference of −$69 [−290, +153]. Both are still supported.
  - **Licensing:** the owner's gain at royalty 0.10, the earlier BLUF's headline, is +$3,388 exact and +$3,138 stars, a difference of −$250 [−714, +213]. 99.0% of licensees accept under exact and 100% under stars.
- **A plausible reason, not tested here:** these results turn on what buyers see once a stall's rating falls (deceptive and bust-out stalls, copied originals) or on prices well below the top of the scale. Brand Equity speed's effect came from near-ties at 0.999 against 1.0, which is where rounding to 0.02 matters most.

## Caveats

- **Ten seeds per study, the first ten of each original run.** "No change" means none at this resolution. The paired differences' intervals are up to ±$130 for verification, ±$180 for the liability contrast, ±$150 for the bust-out gain and ±$460 for the licensing gain. Changes smaller than those cannot be ruled out. On these seeds the exact estimates differ from the published ones, for example +$492 against +$565 for PV3, so verdicts are compared on the same ten seeds.
- **Stars and the random tie-break are tested together,** at one step (0.02), as in Run A. The run does not separate them.
- **The exact arm is saved chains from older engines (0.13.0–0.17.0).** Four per study were rerun at 0.20.0 and match on every field their caches keep: 20 of 20 at the pilot, and 20 of 20 again on macOS 27.2 before launch. Only Canal Street's records hold a full-outcome digest; the other studies' records are compared field by field. The other saved chains are assumed to reproduce the same way.
- **Some endpoints are stand-ins for the original statistics.**
  - The bust-out stars arm runs the exact run's best candidate for each stall. It measures the same bust-out under stars, not whether stars would change which bust-out day is best.
  - The liability contrast has two levels, not PL1's slope over {0, 0.1, 1}.
  - The licensing gain at royalty 0.10 is recomputed exactly from royalty 0.15 chains, as the original did. That assumes the royalty affects no decision under stars, which Run A's replay supports (12 of 12) in the same licensing market.
- **Thirteen endpoints, unadjusted.** One descriptive label change in 13 is about what noise alone would give. Everything in this run is exploratory.
