# Star ratings: sensitivity of five earlier results (Run B)

**Exploratory. No predictions. Intervals are 95% t over seeds, unadjusted.**

## Design

- Engine 0.20.0: `ratings.display` stars rounds every rating a buyer, a posted price or a seller decision reads half up to `ratings.display_step`; `buyers.tie_break` random breaks ties on (visible rating, price) by a per-buyer, per-day random order of the stalls. Defaults reproduce 0.19.0 byte for byte. Background: `runs/brand_equity_speed_summary.md`.
- Stars arm: each study's own config plus `ratings.display=stars`, `ratings.display_step=0.02`, `buyers.tie_break=random`; everything else identical. The studies' own config builders and chain functions are used by import; the overrides are appended to every `load` call the study's config builder makes, and every engine a chain builds was checked to run with display stars, step 0.02, tie-break random (exact arm: exact, stall_id).
- Exact arm: run fresh by this script at engine 0.20.0. Paired by seed: the stars chain for seed s has the same seed, stalls under test, candidates and options as the exact chain.
- Seeds: verification 900-902 (3); liability 900-902 (3); bustout 900-902 (3); canal 900-902 (3); licensing 900-902 (3).
- Chains per seed: verification 48 (A|t100, A|t40|l1, B|t100: never + 3 stalls × 5 bust-out days); liability 32 (collectible, t100, ds 0 and 1: never + 3 × 5); bust-out decomposition 4 (collectible, t40, ds 0: never + each stall's best candidate of the exact run, the same candidate in both arms; the exact arm runs all 5 candidates to find it); Canal Street 3 (off, φ 0.6, φ 1.0 at t100, ds 1); licensing 13 (never at t40, ds 1 + contract × 3 owners × 4 options at royalty 0.15, recomputed exactly at 0.10 as `analysis/licensing_checks.py` does).
- Endpoints and their sources are listed per study. Per seed as each study (mean over its 3 stalls, owners, deceptive stalls or copied originals); exact, stars and stars − exact paired by seed.
- Sign change: the means of exact and stars on opposite sides of 0. Verdict: the original rule applied to the 10-seed estimate (for endpoints without a prediction, the side of 0 the interval is on); verdict change compares exact and stars on the same seeds. The published estimate (more seeds) is shown for reference.

## Run record

- Engine `0.20.0`; commit `84b7243fc97eabe8b946096cc6b7bd7561695e0b`; uncommitted at run time: ['?? runs/pilot_stars/', '?? runs/pilot_stars_stdout.log', '?? runs/queue_stars.sh']
- Script sha256 `f9dbd83be46d8fbde6dd7824d13a510b23aa4d8595f697a4dfbe1efce3dc1ce0`
- Command: `python -m analysis.stars_sensitivity --seeds 900-902 --exact run --workers 4 --outdir runs/pilot_stars/B --tests Engine 0.20.0: full suite 1602 passed, 17 skipped, 1 failed (missing scaling rules, fixed); rerun of test_scale.py and test_v0200.py 222 passed (runs/tests_0200.log) --gate Pilot run (seeds 900–902).`
- Tests: Engine 0.20.0: full suite 1602 passed, 17 skipped, 1 failed (missing scaling rules, fixed); rerun of test_scale.py and test_v0200.py 222 passed (runs/tests_0200.log)
- Gate: Pilot run (seeds 900–902).
- Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit
- Chains run by this script: 636 (0 of them from its cache); saved exact chains used: 0; 4 workers (nice 19); wall clock 1.93 h; load average [10.74, 8.48, 7.2] at start, [8.88, 9.5, 9.79] at end; memory at start {'swap_free_mb': 1328.31, 'free_pct': 63}, at end {'swap_free_mb': 1360.31, 'free_pct': 56}; memory-guard pauses: 0
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

## Verification

Original: `runs/verification_summary.md` (engine 0.13.0 (stage A) and 0.14.0 (stage B), seeds 200-219). Seeds here: 900-902 (3).

| Endpoint | Published (original seeds) | Exact | Stars | Stars − exact [95% t] | Sign change | Verdict: exact → stars | Verdict change |
|---|---|---|---|---|---|---|---|
| Stage A, tourists 1.0 (t100): gain (PV3) | +565.27 [+433.55, +697.00] *; PV3: supported | +1,060.80 [−413.66, +2,535.26] | +866.01 [+334.70, +1,397.33] * | −194.79 [−1,181.56, +791.99] | no | not supported (interval includes 0) → supported | **yes** |
| Stage A, tourists 0.4, locals inspect: gain (an endpoint of PV1) | −110.99 [−147.32, −74.66] *; no prediction on this cell (interval below 0); PV1, which uses it, supported | −115.31 [−211.12, −19.50] * | −142.15 [−191.13, −93.17] * | −26.84 [−164.81, +111.13] | no | interval below 0 → interval below 0 | no |
| Stage B, t100: gain (PV3b, exploratory analogue) | −435.74 [−536.62, −334.87] *; PV3b: contradicted (interval on the opposite side of 0) | −636.94 [−998.54, −275.33] * | −579.49 [−974.32, −184.66] * | +57.45 [+23.87, +91.02] * | no | contradicted (interval on the opposite side of 0) → contradicted (interval on the opposite side of 0) | no |
| t100: Stage B − Stage A (PV4) | −1,001.02 [−1,212.14, −789.89] *; PV4: supported | −1,697.74 [−3,001.68, −393.80] * | −1,445.50 [−2,010.96, −880.05] * | +252.23 [−761.63, +1,266.10] | no | supported → supported | no |

Sources: A_t100: analysis/verification.py:206 gains, :220 seed_mean, :304 PV3; runs/verification_summary.md:34, :44; A_t40l1: analysis/verification.py:206, :220, :253; runs/verification_summary.md:30, :42; B_t100: analysis/verification.py:206, :220, :304; runs/verification_summary.md:109, :119; PV4: analysis/verification.py:330 cross_stage; runs/verification_summary.md:165.

## Liability

Original: `runs/liability_summary.md` (engine 0.15.0, seeds 230-249). Seeds here: 900-902 (3).

| Endpoint | Published (original seeds) | Exact | Stars | Stars − exact [95% t] | Sign change | Verdict: exact → stars | Verdict change |
|---|---|---|---|---|---|---|---|
| Collectible, t100, detect_scale 0: gain | +564.45 [+434.09, +694.81] *; no prediction on this cell (interval above 0) | +1,060.70 [−413.50, +2,534.91] | +865.95 [+334.90, +1,397.01] * | −194.75 [−1,181.48, +791.98] | no | interval includes 0 → interval above 0 | **yes** |
| Collectible, t100, detect_scale 1: gain | −389.04 [−492.70, −285.38] *; no prediction on this cell (interval below 0) | −636.94 [−998.54, −275.33] * | −579.49 [−974.32, −184.66] * | +57.45 [+23.87, +91.02] * | no | interval below 0 → interval below 0 | no |
| Collectible, t100: gain at ds 1 − gain at ds 0 (two-level analogue of PL1; PL1 is a slope over {0, 0.1, 1}) | not published (PL1 slope: −963.90 [−1,189.56, −738.24] * per 1.0 of detect_scale); PL1: supported (a different statistic) | −1,697.64 [−3,001.31, −393.97] * | −1,445.44 [−2,010.66, −880.23] * | +252.20 [−761.62, +1,266.01] | no | supported → supported | no |

Sources: col_t100_ds0: analysis/liability.py:263 gains, :277 seed_mean, :297; runs/liability_summary.md:31; col_t100_ds1: analysis/liability.py:263, :277, :297; runs/liability_summary.md:33; col_t100_ds1_minus_ds0: per-seed difference of the two rows above; PL1 at analysis/liability.py:359, runs/liability_summary.md:47.

## Bustout

Original: `runs/bustout_decomposition.md` (engine 0.15.0 replay, seeds 230-249). Seeds here: 900-902 (3).

| Endpoint | Published (original seeds) | Exact | Stars | Stars − exact [95% t] | Sign change | Verdict: exact → stars | Verdict change |
|---|---|---|---|---|---|---|---|
| Collectible, t40, ds 0: b. lost: inspected and walked away | −131.93 [−165.81, −98.04] *; no prediction (interval below 0); the reading: the main cause of the loss | −215.58 [−298.60, −132.56] * | −246.95 [−321.45, −172.45] * | −31.37 [−188.05, +125.31] | no | interval below 0 → interval below 0 | no |
| Collectible, t40, ds 0: b. lost: rating below threshold | −14.35 [−42.50, +13.79]; no prediction (interval includes 0); the reading: "add little" | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | no | interval includes 0 → interval includes 0 | no |
| Collectible, t40, ds 0: gain of the decomposed candidate (context) | −93.57 [−122.56, −64.59] *; no prediction (interval below 0) | −115.29 [−211.07, −19.50] * | −171.69 [−244.77, −98.62] * | −56.41 [−154.81, +42.00] | no | interval below 0 → interval below 0 | no |

Sources: lost_inspected: analysis/bustout_report.py:56 cause, :70 decompose, :175 by_cond; runs/bustout_decomposition.md:32; lost_rated_below: analysis/bustout_report.py:56, :70, :175; runs/bustout_decomposition.md:33; gain: analysis/bustout_report.py:70, :175; runs/bustout_decomposition.md:40.

Units lost per stall-seed (exact / stars): inspected and walked away 5.8 / 6.9; rating below threshold 0.0 / 0.0. Largest |e| 0 / 0 cents; buyer records differing before the bust-out 0 / 0.

## Canal

Original: `runs/canal_street_summary.md` (engine 0.17.0, seeds 270-299). Seeds here: 900-902 (3).

| Endpoint | Published (original seeds) | Exact | Stars | Stars − exact [95% t] | Sign change | Verdict: exact → stars | Verdict change |
|---|---|---|---|---|---|---|---|
| t100, ds 1, φ 0.6: copied originals' day-30 rating, on − off (PK3) | −0.379 [−0.393, −0.365] *; PK3: supported | −0.383 [−0.435, −0.332] * | −0.386 [−0.437, −0.336] * | −0.003 [−0.045, +0.039] | no | supported → supported | no |
| t100, ds 1, φ 1.0: gap, 30-day (PK2) | −369.83 [−457.80, −281.86] *; PK2: supported | −255.11 [−699.21, +188.99] | −257.91 [−351.82, −164.01] * | −2.80 [−528.68, +523.08] | no | not supported (interval includes 0) → supported | **yes** |

Sources: PK3: analysis/canal_street.py:190, :196, :229; runs/canal_street_summary.md:39; PK2: analysis/canal_street.py:185, :227; runs/canal_street_summary.md:38.

## Licensing

Original: `runs/licensing_checks.md` (engine 0.16.0 replay, seeds 250-269). Seeds here: 900-902 (3).

| Endpoint | Published (original seeds) | Exact | Stars | Stars − exact [95% t] | Sign change | Verdict: exact → stars | Verdict change |
|---|---|---|---|---|---|---|---|
| Contract, t40, ds 1, not liable: owner's gain over the options every licensee accepts, royalty 0.10, unfloored | +3,442.72 [+2,768.04, +4,117.41] *; no prediction (interval above 0); the BLUF's headline | +4,046.13 [−11.21, +8,103.47] | +4,434.48 [+987.49, +7,881.46] * | +388.34 [−356.89, +1,133.57] | no | interval includes 0 → interval above 0 | **yes** |

Sources: con_unf_0.10: analysis/licensing_checks.py:339 _owner_rows, :443-452, :463; runs/licensing_checks.md:8, :435.

Share of licensees accepting at 0.10 (exact / stars): 0.972 / 1.000.

## Stuck, parked and idle buyers; invalid actions

Chains run by this script.

| Study · arm | Chains | Buyer-days | Stuck | Parked | Idle choosers | Invalid actions | Display/tie-break wrong | Schedule or identity fails | Seconds per chain |
|---|---|---|---|---|---|---|---|---|---|
| verification · exact | 144 | 648,000 | 0 | 0 | 0 | 0 | 0 | 0 | 39.9 |
| liability · exact | 96 | 432,000 | 0 | 0 | 0 | 0 | 0 | 0 | 43.1 |
| bustout · exact | 48 | 216,000 | 0 | 0 | 0 | 0 | 0 | 0 | 42.8 |
| canal · exact | 9 | 40,500 | 0 | 0 | 0 | 0 | 0 | 0 | 34.7 |
| licensing · exact | 39 | 175,500 | 0 | 0 | 0 | 0 | 0 | 0 | 42.2 |
| verification · stars | 144 | 648,000 | 0 | 0 | 0 | 0 | 0 | 0 | 43.1 |
| liability · stars | 96 | 432,000 | 0 | 0 | 0 | 0 | 0 | 0 | 48.0 |
| bustout · stars | 12 | 54,000 | 0 | 0 | 0 | 0 | 0 | 0 | 50.9 |
| canal · stars | 9 | 40,500 | 0 | 0 | 0 | 0 | 0 | 0 | 43.1 |
| licensing · stars | 39 | 175,500 | 0 | 0 | 0 | 0 | 0 | 0 | 46.2 |

## Flags

- none

## Reading (written after the results)

READING_PLACEHOLDER

## Caveats

CAVEATS_PLACEHOLDER
