# Autonomous plan, 2026-11-28: aisles rerun with recalibrated fixed costs (runs alongside Week 2)

Follows `runs/REPORT_2026-12a.md` (plan 2026-11-27). Commit this file unchanged as the preregistration before running anything. Same operating rules, STOP conditions and record keeping as `runs/plan_autonomous_2026-11-19.md`:
- 7 workers;
- `caffeinate -i`;
- blocks of at most 10 h;
- STATUS.md and a ping at each checkpoint.

No LLM API calls in this plan. Other sessions may be making API calls for the Week 2 battery; this plan must not touch their files.

**Why rerun.** In plan 2026-11-27, honest thin-margin stalls lost money, because fixed costs were sized to gross profit and ignored ad spend. The primary unit (gain ÷ honest profit) was then undefined in most margin cells, so PA1 thin, PA2 and PB2 could not be tested. This plan fixes the calibration, the unit and the sample size, and reruns Runs A and B on fresh seeds. Run C is not rerun.

## Changes (decided by Randall before any result of this plan)

1. **Fixed cost targets a net margin.** Calibrate each stall's fixed daily cost so that an honest stall's **net margin** (profit after unit cost, ad spend and fixed cost, ÷ revenue) in the calibration chains hits:
   - realistic profiles: fish **2%**, electronics **3%**, designer **30%**;
   - synthetic profiles in Run A: thin **2%**, fat **30%**.

   Calibrate per category, profile and type, from honest never chains at t40, ds 0, α 0, on seeds 900–904. Floor the fixed cost at 0. If no non-negative fixed cost reaches the target (gross after ads already below it), report it and use 0. All targets are PLACEHOLDERs from published retail margins (grocery ~1.7–2% net, electronics retail ~3%, luxury fashion ~30–35% operating).

   If this needs an engine change (a net-margin target key), make it engine 1.3.2: defaults reproduce 1.3.1, with tests and the full suite. Otherwise do it in the calibration script only.
2. **Primary estimand: gain as a share of honest revenue.** Per aisle and per seed: (Σ gains over the sampled stalls) ÷ (Σ of the same stalls' honest-chain revenue over the same window). Then mean and 95% t over seeds, unadjusted. Read it as "a cash-in adds X% of sales". Secondary figures:
   - base-price units;
   - the per-stall mean of ratios;
   - the D5 ratio to honest profit, with its count of stalls whose honest profit is ≤ 0.
3. **Sample.** 3 benchmark stalls per aisle per seed (9 per seed), from `default_rng([seed, 17])`.
4. **Seeds.** Fresh: Run A uses 760–779 and Run B uses 780–799 (20 each).

## Run A (rerun): margin × verifiability

Design as in plan 2026-11-27, Run A:
- margin {thin, fat};
- verifiability {easy, hard};
- verification {t40 locals inspect, t100};
- detect_scale {0, 1};
- solvency on, α 0.

Fixed costs come from change 1.

**Predictions:**
- PA1r (confirmatory): t40, ds 0. At each margin level, hard − easy > 0.
- PA2r (confirmatory): t40, ds 0. At each verifiability level, thin − fat > 0.
- PA3r (confirmatory): ds 1. The gain is < 0 in every profile cell at t40.
- PA4r (exploratory): the interaction; the t100 cells; exits by type.

## Run B (rerun): realistic aisles and the rent trap

Design as in plan 2026-11-27, Run B:
- realistic profiles;
- t40 locals inspect;
- start_cash_days {2, 20} × α {0, 1} × detect_scale {0, 1}.

Fixed costs come from change 1.

**Predictions:**
- PB1r (confirmatory): ds 0, α 0. Cash 2 − cash 20 > 0, pooled over aisles.
- PB2r (confirmatory): ds 0, cash 20, α 0. Designer − fish > 0.
- PB3r (exploratory): per-aisle effects, exits, the α effect, and the ds 1 analogues.

## Gates (pilot on seeds 900–902)

- G1: pipeline end to end.
- G2: identities, plus calibration verified. The realised honest net margins in the pilot are within ±1 point of target in every category and profile, or the gap is reported where the floor at 0 binds.
- G3: timing ≤ 14 h at 7 workers; if over, cut to 15 seeds, otherwise STOP.
- G4b: genuine stalls exiting before day 10 ≤ 5% in every cell.
- G5: guards 0.
- G6: in every confirmatory cell, honest revenue > 0 for every sampled stall. Expected to hold by construction; STOP if not.

CHECKPOINTS:
- C1: calibration and pilot passed; launch.
- C2: summaries of A and B.
- C3: `runs/REPORT_2026-12b.md`, BLUF first. Then stop.

## Deviations

(None yet.)
