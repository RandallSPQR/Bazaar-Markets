# Autonomous plan, 2026-11-27 (Week 1 of the Christmas roadmap): engine 1.3.0, making the aisles real

Start this plan only after `runs/plan_autonomous_2026-11-23.md` has reached checkpoint C7 and stopped, with v1.2.0 tagged locally. Before running anything, commit this file unchanged as the preregistration. Do not edit predictions after any result is seen; if something must change, add a dated note under "Deviations" and give the reason.

The operating rules, STOP conditions and record keeping of `runs/plan_autonomous_2026-11-19.md` apply unchanged, together with the scheduling deviations already in force:
- blocks of at most 10 h, run back to back;
- `caffeinate -i`;
- workers = performance cores − 1 (7), at normal priority;
- free-memory guard on.

Keep `runs/STATUS.md` current; commit and ping at each CHECKPOINT. **No LLM API calls.** Randall is away for parts of this plan. When a STOP condition hits, stop, write STATUS.md and ping. Do not work around it.

## Units (fixed now, before any result)

- **Primary estimand** for every gain or effect: its value as a **share of the same stall's honest profit over the same window** (honest = the never chain), computed per stall and then averaged per seed.
- **Reporting:** per aisle (fish, electronics, designer) and pooled. Dollars and base-price units are secondary.
- **Intervals:** 95% t over seeds, unadjusted.

## Stage 1: engine 1.3.0

Defaults must reproduce v1.2.0 byte for byte. Commit with tests before any pilot.

1. **Category profiles.** `categories.profiles.<cat>`: a set of keys per category. With no profile set, behaviour is exactly 1.2.0. Every value below is a PLACEHOLDER, labelled as such in config.

   | Key | Fish | Electronics | Designer |
   |---|---|---|---|
   | Genuine unit cost as a share of the genuine price at rating 1.0 | 0.70 | 0.77 | 0.20 |
   | Cheap-supply unit cost as a share of genuine unit cost | 0.80 | 0.55 | 0.30 |
   | Fixed daily cost per stall, as a share of a genuine stall's baseline daily gross profit (calibrated in the pilot from honest never chains) | 0.90 | 0.85 | 0.50 |
   | Inspection noise: an inspected quality is seen as q + N(0, σ²), clipped to [0, 1] | σ = 0.15 | σ = 0.02 | σ = 0.25 |
   | Inspection cost multiplier on κ | 1 | 0.5 | 3 |
   | Review accuracy: probability a rated unit's honesty is judged correctly (otherwise flipped) | 0.95 | 0.90 | 0.60 |

   Implement costs by rescaling the existing quality → cost relation per category so the targets hold at the type's mean quality. Do not change the price rule. The inspection noise draw comes from `default_rng([seed, 41, day, buyer index, stall])`; the review flip from `default_rng([seed, 43, day, stall])`.
   - **Out of scope** (no inventory or repeat-buyer memory in the engine): spoilage and repeat purchase. Note them as parked.
2. **Solvency.**
   - `sellers.solvency.enabled` (default false).
   - Each stall starts with cash C0 = `start_cash_days` × its baseline daily gross profit (default 10).
   - Each day: cash += profit − fixed cost − rent.
   - If cash ends a day below −`credit_limit_days` × baseline daily gross profit (default 3), the stall exits at the end of that day by the existing exit rule. Its pending fines become uncollectible.
3. **Rent gradient.**
   - `market.rent.alpha` ∈ [0, 1] (default 0).
   - Rent for a spot = α × that spot's traffic advantage, i.e. its expected extra daily gross profit over the mean spot. Measure it in calibration from honest never chains with γ on and α = 0, and store it as a table per spot and per scenario.
   - Also `buyers.gamma_by_profile` (tourist, local, expert; default: everyone uses `market.gamma`).
4. **Formal model.** Update `docs/formal_model.md` with the 1.1.0–1.3.0 keys, in paragraphs labelled "added at 1.3.0, not cross-checked".

**Tests:**
- v1.2.0 reference cells reproduce with defaults.
- Each profile hits its cost targets to the cent at mean quality.
- Inspection noise of 0 reproduces exact inspection.
- Review accuracy of 1 reproduces exact reviews.
- Solvency off reproduces; a forced-exit unit test passes.
- α = 0 reproduces; rent is charged exactly from the table.

Run the full suite. Update the config reference and CHANGELOG.

CHECKPOINT C1.

## Stage 2: runs (`analysis/aisles_1_3.py`, `runs/aisles_*`)

The market is the v1.0.0 reference (choice-set m 3, display stars at step 0.02, random tie-break, lexicographic choice, brands on with premium 0.4, collectible fines), unless stated otherwise. Bust-out benchmark as in the verification run:
- 3 genuine stalls per seed from `default_rng([seed, 17])`;
- candidates: never, day 20, 25, 28, 29, 30;
- the unfloored gain is primary.

### Run A: margin × verifiability, unbundled

- In this run all three aisles share one synthetic profile, so the profile is the treatment.
- **Margin:**
  - thin: cost share 0.70, cheap-supply share 0.80, fixed cost 0.90;
  - fat: cost share 0.20, cheap-supply share 0.30, fixed cost 0.50.
- **Verifiability:**
  - easy: inspection σ 0.02, cost multiplier 0.5, review accuracy 0.95;
  - hard: inspection σ 0.25, cost multiplier 3, review accuracy 0.60.
- Crossed with verification {t40 locals inspect, t100} × detect_scale {0, 1}.
- Solvency is on with defaults; rent α = 0, γ 0.
- 16 cells. Seeds 700–719 (20), paired.

**Predictions** (gain as a share of honest profit):
- PA1 (confirmatory): t40, ds 0. At each margin level, the gain with hard verifiability exceeds the gain with easy verifiability.
- PA2 (confirmatory): t40, ds 0. At each verifiability level, the gain with thin margin exceeds the gain with fat margin. (Cheap supply saves more relative to a thin honest margin.)
- PA3 (confirmatory): ds 1. The gain is below 0 in all four profile cells, at both verification levels.
- PA4 (exploratory): the margin × verifiability interaction; the t100 analogues; exits by cell.

### Run B: realistic aisles, solvency and the rent trap

- Profiles as in the Stage 1 table, per aisle; solvency on; t40 locals inspect.
- Factors:
  - start_cash_days {2, 20};
  - rent α {0, 1}, with γ_tourist 1.0 and γ_local 0.2;
  - detect_scale {0, 1}.
- 8 cells. Seeds 720–739, paired.

**Predictions:**
- PB1 (confirmatory): ds 0, α 0. The gain with start cash 2 exceeds the gain with start cash 20, pooled over aisles. (The rent trap: a stall that may be forced out has less future to protect.)
- PB2 (confirmatory): ds 0, start cash 20, α 0. The gain is ordered designer > fish on the primary unit.
- PB3 (exploratory): every effect per aisle; exits; the α effect; the ds 1 analogues.

### Run C: tourist traps

- Market-level never chains only; no benchmark.
- Realistic profiles, solvency on.
- γ_tourist 1.0, γ_local 0.2.
- α ∈ {0, 0.5, 1} × verification {t40, t100}.
- Seeds 740–759.

**Predictions:**
- PC1 (confirmatory): t40, α 0. The deceptive share of units sold is higher in the entrance spots (the nearest two ranks) than in the rest.
- PC2 (exploratory): the α effects on that gap, exits by spot, and buyer harm by profile and spot.

### Pilot gates (seeds 900–902)

- G1: pipelines run end to end.
- G2: identities hold (defaults reproduce 1.2.0; the cost targets hold; the rent table is reproducible).
- G3: timing ≤ 14 h total. If over, trim in this order:
  1. drop Run A's t100 cells;
  2. then Run B's α factor;
  3. then cut to 15 seeds.

  Otherwise STOP.
- G4: report exits per cell; if any cell exits more than 50% of stalls before day 10, STOP and report (the calibration is too harsh).
- G5: stuck, parked and idle counts are 0.

CHECKPOINTS:
- C2: pilot passed and launch.
- C3: Run A summary.
- C4: Runs B and C summaries.
- C5: `runs/REPORT_2026-12a.md`, BLUF first, with every verdict and open items. Then stop.

## Deviations

(None yet.)
