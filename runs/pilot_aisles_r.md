# Pilot: aisles rerun (plan 2026-11-28), seeds 900–902: STOP at G2m and G4b

**BLUF.**
- **STOP.** Two pilot gates fail: G2m (honest net margins within ±1 point of target) and G4b (genuine stalls exiting before day 10 ≤ 5% in every cell). Every other gate passes, and G3 projects 5.25 h for the full 20-seed design.
- **Neither failure is a pipeline bug.**
  - The calibration hits every target exactly on its own seeds, 900–904.
  - On seeds 900–902 the pilot cells reproduce the calibration chains to 4 decimals.
  - There is nothing in the pipeline to fix, so the plan's STOP applies: "a pilot gate fails after one honest attempt to fix the pipeline (not the design)".
- **G2m fails because of seed-to-seed spread.** Calibration pools seeds 900–904; the gate checks seeds 900–902 only. Per-seed honest net margins spread widely: thin 0.0–4.2%, Run B fish −1.3% to +4.9%, Run B designer 17–40%. So no 5-seed calibration can hold a 3-seed subset within ±1 point. 6 of 15 rows miss the band, by 1.2 to 1.7 points.
- **G4b fails in one cell, A|thin|easy|t100|ds0, which is exploratory.** There 11 of 54 genuine stalls (20.4%) exit before day 10, and all 54 by day 30.
  - The fixed cost comes from the t40 scenario, as the plan specifies. With tourists only (t100), honest revenue falls and honest net margins are −26% to −29%.
  - Every confirmatory cell passes: 0% in Run A at t40, and at most 1.9% in Run B (B|cash2|a1|ds0).
- **Decision needed from Randall** (options at the end). No main-run chain has run.

## Record

| | |
|---|---|
| Plan | `runs/plan_autonomous_2026-11-28.md`, preregistered 9751d0c |
| Engine | 1.3.1, unchanged |
| Commit, script | c256c55; `analysis/aisles_rerun.py` sha256 b67dd1b0…0d0f; code clean |
| Command | `PYTHONPATH=. .venv/bin/python -m analysis.aisles_rerun --phase pilot`, under `nohup caffeinate -i`, 7 workers, normal priority |
| Tests | `tests/test_v130.py` and `tests/test_v131.py` 29 passed; full suite 1,901 passed at 9023acf (1.3.1) |
| Platform | Python 3.12.7, numpy 2.5.4, macOS 27.2.1 arm64 |
| Wall clock | 2026-11-27 21:09 to 22:22 (4,384 s); memory pauses 0 |
| Jobs | 90 calibration chains (18 scenarios × seeds 900–904), 72 bench jobs (24 cells × seeds 900–902; each a never chain plus 9 stalls × 5 bust days), 24 identity jobs |
| Files | `runs/aisles_r_calibration.json`, `runs/pilot_aisles_r/aisles_r_pilot_gates.json`, `runs/pilot_aisles_r/aisles_r_run.log`; cache local and not committed |

## Gates

| Gate | Result | Detail |
|---|---|---|
| G1 pipeline | pass | 90 + 72 + 24 jobs |
| G2a 1.2.0 defaults reproduce | pass | both reference chains identical |
| G2b cost targets, fixed cost charged as calibrated | pass | no bad rows |
| G2c calibration rerun and recalculation | pass | identical |
| G2e continued = full bust-out chains (D1) | pass | 24 cells × (5 bust days + never), all identical |
| **G2m net margin ±1 point** | **fail** | 6 of 15 rows outside the band (table below); no floor binds for a genuine stall |
| G3 timing ≤ 14 h | pass | 5.25 h projected (15 seeds: 3.94 h); 269 CPU-s per bench job |
| **G4b genuine exits before day 10 ≤ 5%** | **fail** | A\|thin\|easy\|t100\|ds0 20.4%; all other cells ≤ 1.9% |
| G5 guards | pass | 0 stuck, idle, parked or fallbacks over 2.96 million buyer-days |
| G6 honest revenue > 0 (confirmatory cells) | pass | 0 sampled stalls with revenue ≤ 0 in all 10 cells |

### G2m: realised genuine net margin, seeds 900–902 (ratio of sums)

| Cell | Fish | Electronics | Designer | Target |
|---|---|---|---|---|
| A\|fat\|easy\|t40\|ds0 | 0.308 | **0.319** | 0.298 | 0.30 |
| A\|fat\|hard\|t40\|ds0 | 0.297 | **0.315** | 0.298 | 0.30 |
| A\|thin\|easy\|t40\|ds0 | 0.028 | **0.032** | 0.020 | 0.02 |
| A\|thin\|hard\|t40\|ds0 | 0.024 | 0.028 | 0.023 | 0.02 |
| B\|cash20\|a0\|ds0 | **0.036** (0.02) | **0.046** (0.03) | **0.283** (0.30) | as shown |

Bold: outside ±0.01.

**Why it fails, checked.** These cells are the calibration scenario plus the fixed cost and solvency. None of their never chains had an exit. Applying the calibrated fixed cost to the calibration chains gives:
- 0.300 / 0.300 / 0.300 (and 0.02 / 0.03 / 0.30 in Run B) on seeds 900–904;
- exactly the realised figures above on seeds 900–902 (for example, B fish 0.036, electronics 0.0461, designer 0.2829).

So the pipeline charges what was calibrated, and the gap is the difference between the 5-seed calibration and its 3-seed subset. Per-seed honest net margins in the calibration chains:

| Scenario | 900 | 901 | 902 | 903 | 904 |
|---|---|---|---|---|---|
| A thin easy: fish / electronics / designer | .022 / .036 / .027 | .040 / .016 / .018 | .024 / .042 / .013 | .013 / .001 / .029 | .002 / .000 / .012 |
| A fat easy | .303 / .328 / .310 | .324 / .298 / .302 | .297 / .330 / .281 | .298 / .251 / .316 | .278 / .285 / .290 |
| B (realistic) | .043 / .052 / .401 | .049 / .030 / .204 | .013 / .059 / .174 | −.013 / .049 / .267 | −.001 / −.052 / .366 |

Seeds 903 and 904 have lower margins than 900–902, which pulls the 900–902 subset above target. On the main-run seeds, expect honest net margins to scatter around the targets by several points per seed. Some thin and Run B fish and electronics stalls will have honest profit ≤ 0 on some seeds; that affects only the D5 secondary, which reports the count. The primary (share of revenue) doesn't divide by profit.

### G4b and exits (never chains, 3 seeds; before day 10 / by day 30, of 54 genuine, 45 seconds, 45 deceptive)

| Cell | Genuine | Seconds | Deceptive |
|---|---|---|---|
| **A\|thin\|easy\|t100\|ds0** | **11 / 54** | 0 / 0 | 0 / 0 |
| A\|thin\|hard\|t100\|ds0 | 0 / 38 | 0 / 11 | 0 / 0 |
| A\|fat\|easy\|t100\|ds0 | 0 / 25 | 0 / 0 | 0 / 0 |
| A\|fat\|hard\|t100\|ds0 | 0 / 3 | 0 / 0 | 0 / 0 |
| A, any t40 ds 0 cell | 0 / 0 | 0 / 0 | 0 / 0 |
| A, ds 1 cells | 0 / 0 | 0 / 0 | 0–45 / 16–45 |
| B\|cash2\|a0\|ds0 | 0 / 6 | 0 / 10 | 1 / 17 |
| B\|cash2\|a1\|ds0 | 1 / 4 | 0 / 12 | 0 / 10 |
| B, cash 20 cells | 0 / 0 | 0 / 0 | 0 / 0–36 |
| B, cash 2, ds 1 | 0 / 0–1 | 0 / 5–8 | 37–42 / 44 |

Every exit is an insolvency. In A|thin|easy|t100|ds0 the honest net margin is −25.7% (fish), −29.4% (electronics) and −25.9% (designer). In that cell the never benchmark is a stall that closes by day 30 in every seed, so the "gain" there compares a bust-out with a closing stall.

## Calibration (seeds 900–904, honest never chains, t40, ds 0, α 0)

Fixed daily cost in cents (genuine / deceptive / seconds) and the honest margin before fixed cost, (revenue − unit cost − ad) ÷ revenue, for genuine stalls:

| Scenario | Fish | Electronics | Designer | Genuine margin before fixed cost |
|---|---|---|---|---|
| A fat easy | 2,893 / 1,349 / 13 | 14,691 / 6,827 / 0 | 42,841 / 21,153 / 2 | .754 / .750 / .760 |
| A fat hard | 2,039 / 1,633 / 0 | 10,346 / 8,365 / 0 | 30,169 / 25,452 / 0 | .715 / .709 / .721 |
| A thin easy | 1,423 / 222 / 0 | 7,148 / 949 / 0 | 21,374 / 3,841 / 0 | .243 / .239 / .250 |
| A thin hard | 589 / 613 / 0 | 2,883 / 3,123 / 0 | 9,010 / 10,054 / 0 | .140 / .134 / .146 |
| B realistic | 1,331 / 267 / 0 | 4,438 / 3,356 / 0 | 25,239 / 30,794 / 0 | .241 / .162 / .711 |

**Where the floor binds.** The seconds stalls' fixed cost floors at 0 in every scenario, and in A fat easy in electronics only. Their margin before fixed cost is below target:
- −0.45 to −0.66 in A thin hard;
- −0.17 to −0.31 in A thin easy;
- −0.20 to −0.40 in Run B fish and electronics.

The floor never binds for a genuine or a deceptive stall.

## Options (Randall's decision)

**G2m.**
1. **Accept, with a deviation logged (recommended).** The gate's purpose, checking that the calibration is applied as computed, is met exactly: the pilot reproduces the calibration chains. The ±1 point band on 3 of the 5 calibration seeds is tighter than the market's seed-to-seed spread allows. Report the realised per-seed margins in the main runs.
2. Calibrate on more seeds (for example 900–919) so that the subset spread shrinks, and re-pilot (about 1.5 h). This still leaves the per-seed spread on the main seeds.

**G4b.**
1. **Accept, with a deviation logged (recommended).** It fails only in the exploratory t100 cells (PA4r), and every confirmatory cell passes. Report the t100 exits as a result: a fixed cost sized for a market where locals inspect bankrupts honest thin-margin stalls when only tourists come.
2. Calibrate the t100 cells' fixed cost on their own t100 scenario. This departs from change 1 ("from honest never chains at t40"), and it changes what the t100 comparison means.
3. Drop A|thin|·|t100|ds0 from the main run, or run them without solvency.

With option 1 for both, the main run can start at once: about 5.3 h for 480 bench jobs on seeds 760–799.
