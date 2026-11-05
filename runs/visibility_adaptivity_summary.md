# Visibility × seller adaptivity

Does strategic avoidance erode the patrol advantage found in the placement sweep?

## Run record

- Engine version: `0.3.0`
- Commit: `c0cc5dbe3c4de6e13ce1389189d6e0d82df7e95e`; uncommitted at run time: `?? analysis/visibility_adaptivity.py`
- Run script: `analysis/visibility_adaptivity.py`, sha256 `e79505adcc455be9…`
- Command: `.venv/bin/python -m analysis.visibility_adaptivity --seeds 0-29 --out runs/visibility_adaptivity.json`
- Wall-clock: 1284 s for 660 runs on 8 workers (load average at start 100.0)
- Seeds: 0–29 (30), paired across all 22 conditions
- Python 3.12.7, numpy 2.5.4, macOS-26.6.2-arm64-arm-64bit
- Bootstrap: 10000 resamples of seeds, numpy default_rng(20261105)

Condition names: `posts_u2` = 2 uniformed inspectors on posts, `posts_n2` = 2 non-uniformed,
`patrolling_u6` = 6 uniformed patrolling, `disguised_2` = 2 disguised (never uniformed).
Policies: `rule_deceptive` (does not read the uniform or catch notices) and
`rule_deceptive_adaptive` (positive control). Notation: mean [95% t-interval over seeds];
money in dollars, shares in percent, differences signed; `*` = interval excludes 0; unadjusted.
"Post/patrol inspectors" are the dedicated inspectors on posts or patrolling, who are the
uniformed ones in `_u` conditions.

## Positive-control gate (checked first)

- Share of false-claim impressions perceived by uniformed inspectors, adaptive sellers, `posts_u2`: 0 in every seed (max 0.0000).
- Catches, adaptive − rule_deceptive, `posts_u2`: -9.8 [-11.7, -7.9] * (below 0).
- **Gate passed.**

## Verdicts

| prediction | status | verdict |
|---|---|---|
| P1: I > 0 for deceptive profit, count 2 | confirmatory | **supported**: +$198 [+173, +224] |
| P1: I > 0 for reachable shortfall rate, count 2 | confirmatory | **supported**: +14.8 pts [+10.7, +18.9] |
| P1: I > 0 for deceptive profit, count 6 | confirmatory | **supported**: +$309 [+283, +335] |
| P1: I > 0 for reachable shortfall rate, count 6 | confirmatory | **supported**: +14.9 pts [+10.9, +18.9] |
| P2: J < 0 for deceptive profit (disguised gains vs uniformed patrolling under adaptive sellers) | exploratory | supported at both counts: −$182 [−202, −161] and −$326 [−344, −308] |
| P3: uniform − no uniform ≈ 0 under rule_deceptive | exploratory | supported: exactly 0 in every seed, all four cells |
| P3: the uniform favours deceptive sellers under adaptive | exploratory | **partly supported**: deceptive profit rises in all four cells, but buyers do *better* with uniformed posts (reachable shortfall −4.7 and −4.1 pts) and worse only with uniformed patrolling (+18.5 and +10.8 pts) |

All 4 confirmatory intervals exclude 0. Intervals are unadjusted. The narrowest margin is the shortfall rate
at count 2 (lower bound +10.7 pts).

## Reading (written after the results)

**Avoidance erases the patrol advantage, and at count 2 it reverses it.** Against rule_deceptive sellers,
uniformed patrolling beats uniformed posts by $182 (count 2) and $312 (count 6) in deceptive profit per stall,
as in the placement sweep. Against adaptive sellers the same contrast is +$16 [+6, +26] at count 2
(patrolling is now *worse* than posts) and −$3 [−14, +9] at count 6 (no difference). The buyer outcomes move
the same way: at count 2 reachable shortfall is 6.9 pts higher under patrolling than posts.

**Why: a visible patrol sweeps every stall briefly, and an adaptive seller only has to wait for it to pass.**
Against uniformed patrolling, adaptive sellers earn $47 per stall, statistically the same as with no
inspectors at all ($49; difference −$1.83 [−4.43, +0.77]). Uniformed posts, by contrast, permanently silence the
stalls near them. That still leaves the pockets, but the deception it stops stays stopped. So once sellers can
see enforcement, the fixed-post layout is the better of the two.

**Visible enforcement deters without catching anyone.** With uniformed inspectors, adaptive sellers are never
caught (0 catches in every seed of all four uniformed cells), yet reachable shortfall falls from 30.2% in control
to 19.1% (posts, 2) and 16.2% (posts, 6). Every false message they send is sent with no uniformed inspector in
earshot (100% in every uniformed cell). This is the manipulation working as built, not evidence of learned
timing.

**Hidden enforcement holds up best.** Disguised inspectors lose less to adaptive sellers than uniformed patrols
(P2), and non-uniformed posts and patrols keep catching adaptive sellers (5.5 to 29.6 catches per run), because
those sellers can then react only to public catch notices and their own reopening. Against adaptive sellers,
non-uniformed patrolling at count 6 gives the lowest shortfall of any cell (3.7% reachable).

### Caveats

- **The positive control is perfect avoidance.** The adaptive seller sees every uniform at earshot range (4),
  and inspectors perceive only within that range (signs within 3), so uniformed inspectors can never catch it.
  The erosion measured here is an upper bound for a seller that reads uniforms without error. Detection at
  longer range, partial uniform visibility or noisy recognition would shrink it.
- **The rule is hand-written, not learned.** "Finding the gaps" here is a fixed rule (hide when a uniform or a
  notice is near), not search. Whether learning or LLM sellers find these gaps is a separate question.
- **Reachable shortfall equals all-buyer shortfall by construction.** Unreachable buyers never buy, so the
  per-purchase rate is unchanged by restricting to reachable buyers. The reachable restriction matters for
  task-complete share and surplus (reachable buyers are 66.6% of arrivals, identical in every condition).
- **Calibration.** Detection weights, ad costs, the yell cooldown and the 40-tick closure (which also sets L, the
  catch-notice window) are placeholder or calibration choices, not research claims.
- **Run conditions.** The machine's load average was about 100 at the start (other jobs running), so the
  wall-clock overstates the normal cost. Results do not depend on timing.
- **Consistency check.** Every rule_deceptive cell reproduces the corresponding placement-sweep value (for
  example $8.82 for posts at count 2 and −$413.04 for patrolling at count 6), as engine 0.3.0 was verified to do.

### Choices made where the design left room

- The sign action takes effect in the same tick (agreed before the run). With a one-tick lag, tick-0 and
  reopening signs could not be hidden, and the gate would fail by construction.
- While hiding, the adaptive seller goes quiet: no yell or whisper, truthful answers, sign set to `truth`
  (agreed before the run).
- "Catches within earshot in the last L ticks" counts catches 1 to L ticks ago at stalls whose distance from
  this stall is at most earshot. "Reopened within the last L ticks" means fewer than L ticks since reopening.
- The patrol-timing statistic is computed per false-claim message (one sign display, yell, whisper or answer),
  and "uniformed inspector within earshot" uses the post/patrol inspectors, which are the uniformed ones in
  `_u` cells. In `_n` cells it shows where false claims were made relative to inspectors sellers cannot see.
- The P1 verdict rule: "supported" if the 95% interval is above 0, "contradicted" if below, otherwise "not
  supported".

## P1 (confirmatory): adaptivity shrinks the patrolling advantage, uniformed inspectors

I = [(patrolling − posts) | adaptive] − [(patrolling − posts) | rule_deceptive], per seed, uniformed
inspectors. Predicted I > 0 for deceptive profit and for reachable shortfall rate, at count 2 and 6.
The other rows are exploratory.

| count | outcome | I | verdict |
|---|---|---|---|
| 2 | shortfall rate, reachable (%) **(confirmatory)** | +14.8 [+10.7, +18.9] * | supported |
| 2 | task complete, reachable (%) | -12.4 [-16.0, -8.9] * | exploratory |
| 2 | buyer surplus, reachable ($) | -8.77 [-13.07, -4.46] * | exploratory |
| 2 | deceptive profit ($/stall) **(confirmatory)** | +198.35 [+172.65, +224.05] * | supported |
| 2 | catches | -28.8 [-32.4, -25.2] * | exploratory |
| 6 | shortfall rate, reachable (%) **(confirmatory)** | +14.9 [+10.9, +18.9] * | supported |
| 6 | task complete, reachable (%) | -12.1 [-15.4, -8.7] * | exploratory |
| 6 | buyer surplus, reachable ($) | -9.51 [-13.18, -5.84] * | exploratory |
| 6 | deceptive profit ($/stall) **(confirmatory)** | +308.78 [+283.00, +334.57] * | supported |
| 6 | catches | -50.6 [-53.1, -48.0] * | exploratory |

The two halves of I (patrolling − posts within each policy, uniformed):

| count | sellers | shortfall rate, reachable (%) | task complete, reachable (%) | buyer surplus, reachable ($) | deceptive profit ($/stall) | catches |
|---|---|---|---|---|---|---|
| 2 | rule_deceptive | -7.9 [-10.9, -4.9] * | +6.8 [+4.1, +9.6] * | +4.43 [+2.05, +6.82] * | -182.03 [-205.83, -158.22] * | +28.8 [+25.2, +32.4] * |
| 2 | rule_deceptive_adaptive | +6.9 [+4.1, +9.7] * | -5.6 [-8.0, -3.2] * | -4.33 [-7.20, -1.46] * | +16.32 [+6.24, +26.40] * | +0.0 [+0.0, +0.0] |
| 6 | rule_deceptive | -16.7 [-21.1, -12.2] * | +14.4 [+10.5, +18.2] * | +8.92 [+5.89, +11.95] * | -311.65 [-339.41, -283.88] * | +50.6 [+48.0, +53.1] * |
| 6 | rule_deceptive_adaptive | -1.7 [-5.7, +2.2] | +2.3 [-1.0, +5.6] | -0.59 [-3.76, +2.58] | -2.86 [-14.45, +8.72] | +0.0 [+0.0, +0.0] |

Exploratory: the same interaction with non-uniformed inspectors (adaptive sellers can then react
only to catch notices and their own reopening):

| count | shortfall rate, reachable (%) | task complete, reachable (%) | buyer surplus, reachable ($) | deceptive profit ($/stall) |
|---|---|---|---|---|
| 2 | -8.4 [-10.8, -6.0] * | +7.2 [+5.1, +9.3] * | +6.25 [+3.51, +8.98] * | +51.40 [+35.08, +67.72] * |
| 6 | +0.0 [-2.3, +2.3] | +0.1 [-1.7, +2.0] | +1.28 [-0.62, +3.18] | +191.25 [+176.26, +206.24] * |

## P2 (exploratory): disguised inspectors gain against adaptive sellers

J = [(disguised − uniformed patrolling) | adaptive] − [same | rule_deceptive]. Predicted J < 0
for deceptive profit.

| count | outcome | J | disguised − patrol_u, rule_deceptive | disguised − patrol_u, adaptive | verdict |
|---|---|---|---|---|---|
| 2 | shortfall rate, reachable (%) | -12.6 [-15.8, -9.3] * | +5.7 [+3.7, +7.7] * | -6.8 [-9.2, -4.5] * | – |
| 2 | task complete, reachable (%) | +10.5 [+7.7, +13.3] * | -5.0 [-6.7, -3.3] * | +5.5 [+3.4, +7.6] * | – |
| 2 | buyer surplus, reachable ($) | +7.69 [+4.82, +10.56] * | -3.43 [-5.31, -1.55] * | +4.26 [+2.46, +6.06] * | – |
| 2 | deceptive profit ($/stall) | -181.52 [-202.08, -160.96] * | +122.03 [+102.58, +141.48] * | -59.49 [-70.18, -48.80] * | supported |
| 2 | catches | +29.7 [+26.7, +32.6] * | -20.8 [-23.8, -17.8] * | +8.9 [+7.9, +9.9] * | – |
| 6 | shortfall rate, reachable (%) | -12.3 [-15.8, -8.7] * | +9.7 [+7.4, +11.9] * | -2.6 [-4.6, -0.6] * | – |
| 6 | task complete, reachable (%) | +9.7 [+6.9, +12.6] * | -8.1 [-10.0, -6.1] * | +1.7 [+0.1, +3.3] * | – |
| 6 | buyer surplus, reachable ($) | +7.01 [+4.21, +9.81] * | -5.54 [-7.34, -3.75] * | +1.46 [-0.88, +3.81] | – |
| 6 | deceptive profit ($/stall) | -326.37 [-344.31, -308.44] * | +238.40 [+221.13, +255.67] * | -87.98 [-98.82, -77.13] * | supported |
| 6 | catches | +55.0 [+53.1, +56.9] * | -39.5 [-41.5, -37.5] * | +15.5 [+14.6, +16.4] * | – |

## P3 (exploratory): the uniform is costly only against adaptive sellers

Uniformed − not uniformed, paired. Predicted ~0 under rule_deceptive (exactly 0 is implied by
the byte-identical test) and favouring deceptive sellers under adaptive (profit and shortfall up).

| sellers | placement | count | shortfall rate, reachable (%) | task complete, reachable (%) | buyer surplus, reachable ($) | deceptive profit ($/stall) | catches | exactly 0 in every seed |
|---|---|---|---|---|---|---|---|---|
| rule_deceptive | posts | 2 | +0.0 [+0.0, +0.0] | +0.0 [+0.0, +0.0] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | yes |
| rule_deceptive | patrolling | 2 | +0.0 [+0.0, +0.0] | +0.0 [+0.0, +0.0] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | yes |
| rule_deceptive | posts | 6 | +0.0 [+0.0, +0.0] | +0.0 [+0.0, +0.0] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | yes |
| rule_deceptive | patrolling | 6 | +0.0 [+0.0, +0.0] | +0.0 [+0.0, +0.0] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] | yes |
| rule_deceptive_adaptive | posts | 2 | -4.7 [-6.4, -3.0] * | +4.0 [+2.5, +5.5] * | +2.96 [+1.03, +4.89] * | +11.20 [+4.49, +17.91] * | -5.5 [-6.3, -4.8] * | no |
| rule_deceptive_adaptive | patrolling | 2 | +18.5 [+14.5, +22.6] * | -15.6 [-19.2, -12.1] * | -12.05 [-15.58, -8.53] * | +158.15 [+140.58, +175.72] * | -21.9 [-23.3, -20.4] * | no |
| rule_deceptive_adaptive | posts | 6 | -4.1 [-6.1, -2.1] * | +3.4 [+1.8, +5.1] * | +4.26 [+2.18, +6.34] * | +67.32 [+54.26, +80.37] * | -14.4 [-15.6, -13.1] * | no |
| rule_deceptive_adaptive | patrolling | 6 | +10.8 [+8.0, +13.7] * | -8.8 [-11.1, -6.5] * | -6.53 [-9.46, -3.59] * | +184.85 [+171.51, +198.18] * | -29.6 [-30.5, -28.7] * | no |

## Primary outcomes by condition

| sellers | condition | shortfall rate, reachable (%) | task complete, reachable (%) | buyer surplus, reachable ($) | deceptive profit ($/stall) |
|---|---|---|---|---|---|
| rule_deceptive | control | 30.2 [24.4, 36.0] | 35.3 [30.5, 40.1] | -1.02 [-5.74, 3.70] | 49.24 [30.43, 68.05] |
| rule_deceptive | posts_n2 | 26.7 [20.8, 32.5] | 38.3 [33.4, 43.2] | 0.48 [-4.28, 5.23] | 8.82 [-12.03, 29.68] |
| rule_deceptive | posts_u2 | 26.7 [20.8, 32.5] | 38.3 [33.4, 43.2] | 0.48 [-4.28, 5.23] | 8.82 [-12.03, 29.68] |
| rule_deceptive | patrolling_n2 | 18.8 [14.7, 22.8] | 45.1 [41.8, 48.4] | 4.91 [0.89, 8.93] | -173.20 [-198.06, -148.35] |
| rule_deceptive | patrolling_u2 | 18.8 [14.7, 22.8] | 45.1 [41.8, 48.4] | 4.91 [0.89, 8.93] | -173.20 [-198.06, -148.35] |
| rule_deceptive | disguised_2 | 24.5 [19.7, 29.3] | 40.2 [36.1, 44.2] | 1.48 [-2.61, 5.57] | -51.18 [-71.95, -30.40] |
| rule_deceptive | posts_n6 | 24.9 [19.2, 30.7] | 39.7 [34.8, 44.5] | 2.39 [-2.26, 7.04] | -101.40 [-137.18, -65.62] |
| rule_deceptive | posts_u6 | 24.9 [19.2, 30.7] | 39.7 [34.8, 44.5] | 2.39 [-2.26, 7.04] | -101.40 [-137.18, -65.62] |
| rule_deceptive | patrolling_n6 | 8.3 [6.2, 10.4] | 54.0 [51.9, 56.1] | 11.31 [8.82, 13.80] | -413.04 [-429.59, -396.50] |
| rule_deceptive | patrolling_u6 | 8.3 [6.2, 10.4] | 54.0 [51.9, 56.1] | 11.31 [8.82, 13.80] | -413.04 [-429.59, -396.50] |
| rule_deceptive | disguised_6 | 17.9 [14.4, 21.5] | 46.0 [42.9, 49.1] | 5.77 [2.60, 8.93] | -174.65 [-196.37, -152.93] |
| rule_deceptive_adaptive | control | 30.2 [24.4, 36.0] | 35.3 [30.5, 40.1] | -1.02 [-5.74, 3.70] | 49.24 [30.43, 68.05] |
| rule_deceptive_adaptive | posts_n2 | 23.8 [18.4, 29.2] | 40.9 [36.3, 45.5] | 2.22 [-1.92, 6.36] | 19.89 [2.75, 37.03] |
| rule_deceptive_adaptive | posts_u2 | 19.1 [14.6, 23.6] | 44.9 [41.0, 48.8] | 5.18 [1.59, 8.77] | 31.09 [16.78, 45.39] |
| rule_deceptive_adaptive | patrolling_n2 | 7.5 [5.4, 9.6] | 54.9 [52.6, 57.2] | 12.90 [11.09, 14.72] | -110.74 [-122.55, -98.93] |
| rule_deceptive_adaptive | patrolling_u2 | 26.0 [21.0, 31.0] | 39.3 [35.2, 43.3] | 0.85 [-3.52, 5.22] | 47.41 [29.63, 65.19] |
| rule_deceptive_adaptive | disguised_2 | 19.2 [15.1, 23.2] | 44.8 [41.3, 48.2] | 5.11 [1.76, 8.46] | -12.08 [-27.14, 2.98] |
| rule_deceptive_adaptive | posts_n6 | 20.3 [15.0, 25.7] | 43.7 [39.1, 48.3] | 4.59 [0.50, 8.69] | -36.50 [-58.34, -14.66] |
| rule_deceptive_adaptive | posts_u6 | 16.2 [11.7, 20.8] | 47.1 [43.0, 51.2] | 8.86 [5.43, 12.29] | 30.82 [17.53, 44.10] |
| rule_deceptive_adaptive | patrolling_n6 | 3.7 [2.7, 4.6] | 58.2 [56.6, 59.8] | 14.79 [13.69, 15.90] | -156.89 [-164.26, -149.52] |
| rule_deceptive_adaptive | patrolling_u6 | 14.5 [11.1, 17.9] | 49.4 [46.7, 52.1] | 8.27 [4.82, 11.71] | 27.95 [13.55, 42.35] |
| rule_deceptive_adaptive | disguised_6 | 11.9 [9.4, 14.4] | 51.1 [48.9, 53.3] | 9.73 [7.60, 11.86] | -60.02 [-70.91, -49.14] |

## Secondary outcomes by condition

| sellers | condition | shortfall rate, all (%) | task complete, all (%) | buyer surplus, all ($) | catches | deceptive share of units (%) | quantity fulfilled (%) | empty-handed (%) | active inspector-ticks | reachable buyers (%) |
|---|---|---|---|---|---|---|---|---|---|---|
| rule_deceptive | control | 30.2 [24.4, 36.0] | 23.6 [20.3, 26.9] | -0.66 [-3.81, 2.48] | 0.0 [0.0, 0.0] | 32.7 [26.4, 39.0] | 41.3 [39.8, 42.8] | 40.1 [38.4, 41.8] | 0.0 [0.0, 0.0] | 66.6 [65.3, 68.0] |
| rule_deceptive | posts_n2 | 26.7 [20.8, 32.5] | 25.6 [22.3, 28.9] | 0.33 [-2.82, 3.48] | 9.8 [7.9, 11.7] | 28.8 [22.4, 35.1] | 41.2 [39.7, 42.7] | 40.1 [38.4, 41.8] | 480.0 [480.0, 480.0] | 66.6 [65.3, 68.0] |
| rule_deceptive | posts_u2 | 26.7 [20.8, 32.5] | 25.6 [22.3, 28.9] | 0.33 [-2.82, 3.48] | 9.8 [7.9, 11.7] | 28.8 [22.4, 35.1] | 41.2 [39.7, 42.7] | 40.1 [38.4, 41.8] | 480.0 [480.0, 480.0] | 66.6 [65.3, 68.0] |
| rule_deceptive | patrolling_n2 | 18.8 [14.7, 22.8] | 30.1 [27.8, 32.4] | 3.28 [0.59, 5.97] | 38.5 [34.8, 42.2] | 20.5 [16.1, 24.9] | 41.2 [39.7, 42.6] | 40.1 [38.4, 41.8] | 480.0 [480.0, 480.0] | 66.6 [65.3, 68.0] |
| rule_deceptive | patrolling_u2 | 18.8 [14.7, 22.8] | 30.1 [27.8, 32.4] | 3.28 [0.59, 5.97] | 38.5 [34.8, 42.2] | 20.5 [16.1, 24.9] | 41.2 [39.7, 42.6] | 40.1 [38.4, 41.8] | 480.0 [480.0, 480.0] | 66.6 [65.3, 68.0] |
| rule_deceptive | disguised_2 | 24.5 [19.7, 29.3] | 26.8 [24.0, 29.6] | 1.02 [-1.71, 3.75] | 17.7 [15.3, 20.2] | 26.5 [21.3, 31.6] | 41.2 [39.7, 42.6] | 40.1 [38.4, 41.8] | 79.9 [69.3, 90.5] | 66.6 [65.3, 68.0] |
| rule_deceptive | posts_n6 | 24.9 [19.2, 30.7] | 26.5 [23.2, 29.8] | 1.60 [-1.49, 4.69] | 27.0 [23.9, 30.2] | 27.1 [20.8, 33.4] | 41.2 [39.7, 42.7] | 40.1 [38.4, 41.8] | 1440.0 [1440.0, 1440.0] | 66.6 [65.3, 68.0] |
| rule_deceptive | posts_u6 | 24.9 [19.2, 30.7] | 26.5 [23.2, 29.8] | 1.60 [-1.49, 4.69] | 27.0 [23.9, 30.2] | 27.1 [20.8, 33.4] | 41.2 [39.7, 42.7] | 40.1 [38.4, 41.8] | 1440.0 [1440.0, 1440.0] | 66.6 [65.3, 68.0] |
| rule_deceptive | patrolling_n6 | 8.3 [6.2, 10.4] | 36.0 [34.3, 37.7] | 7.57 [5.90, 9.25] | 77.6 [75.7, 79.5] | 9.3 [6.8, 11.9] | 41.0 [39.5, 42.5] | 40.1 [38.4, 41.8] | 1440.0 [1440.0, 1440.0] | 66.6 [65.3, 68.0] |
| rule_deceptive | patrolling_u6 | 8.3 [6.2, 10.4] | 36.0 [34.3, 37.7] | 7.57 [5.90, 9.25] | 77.6 [75.7, 79.5] | 9.3 [6.8, 11.9] | 41.0 [39.5, 42.5] | 40.1 [38.4, 41.8] | 1440.0 [1440.0, 1440.0] | 66.6 [65.3, 68.0] |
| rule_deceptive | disguised_6 | 17.9 [14.4, 21.5] | 30.6 [28.4, 32.9] | 3.87 [1.76, 5.99] | 38.1 [35.8, 40.5] | 19.7 [15.9, 23.6] | 41.2 [39.8, 42.7] | 40.1 [38.4, 41.8] | 245.8 [227.0, 264.6] | 66.6 [65.3, 68.0] |
| rule_deceptive_adaptive | control | 30.2 [24.4, 36.0] | 23.6 [20.3, 26.9] | -0.66 [-3.81, 2.48] | 0.0 [0.0, 0.0] | 32.7 [26.4, 39.0] | 41.3 [39.8, 42.8] | 40.1 [38.4, 41.8] | 0.0 [0.0, 0.0] | 66.6 [65.3, 68.0] |
| rule_deceptive_adaptive | posts_n2 | 23.8 [18.4, 29.2] | 27.2 [24.1, 30.4] | 1.47 [-1.29, 4.22] | 5.5 [4.8, 6.3] | 25.7 [19.9, 31.6] | 41.2 [39.6, 42.7] | 40.1 [38.4, 41.8] | 480.0 [480.0, 480.0] | 66.6 [65.3, 68.0] |
| rule_deceptive_adaptive | posts_u2 | 19.1 [14.6, 23.6] | 29.9 [27.2, 32.6] | 3.39 [1.00, 5.78] | 0.0 [0.0, 0.0] | 20.4 [15.7, 25.2] | 41.1 [39.5, 42.6] | 40.1 [38.4, 41.8] | 480.0 [480.0, 480.0] | 66.6 [65.3, 68.0] |
| rule_deceptive_adaptive | patrolling_n2 | 7.5 [5.4, 9.6] | 36.6 [34.8, 38.3] | 8.61 [7.36, 9.86] | 21.9 [20.4, 23.3] | 8.6 [6.2, 11.0] | 41.0 [39.5, 42.5] | 40.1 [38.4, 41.8] | 480.0 [480.0, 480.0] | 66.6 [65.3, 68.0] |
| rule_deceptive_adaptive | patrolling_u2 | 26.0 [21.0, 31.0] | 26.2 [23.4, 29.0] | 0.58 [-2.32, 3.48] | 0.0 [0.0, 0.0] | 28.3 [22.8, 33.8] | 41.4 [40.0, 42.9] | 40.1 [38.4, 41.8] | 480.0 [480.0, 480.0] | 66.6 [65.3, 68.0] |
| rule_deceptive_adaptive | disguised_2 | 19.2 [15.1, 23.2] | 29.8 [27.4, 32.3] | 3.42 [1.20, 5.65] | 8.9 [7.9, 9.9] | 20.8 [16.4, 25.2] | 41.2 [39.7, 42.6] | 40.1 [38.4, 41.8] | 79.9 [69.3, 90.5] | 66.6 [65.3, 68.0] |
| rule_deceptive_adaptive | posts_n6 | 20.3 [15.0, 25.7] | 29.2 [26.0, 32.3] | 3.05 [0.32, 5.79] | 14.4 [13.1, 15.6] | 22.2 [16.3, 28.0] | 41.1 [39.6, 42.7] | 40.1 [38.4, 41.8] | 1440.0 [1440.0, 1440.0] | 66.6 [65.3, 68.0] |
| rule_deceptive_adaptive | posts_u6 | 16.2 [11.7, 20.8] | 31.4 [28.6, 34.3] | 5.91 [3.59, 8.24] | 0.0 [0.0, 0.0] | 17.3 [12.5, 22.1] | 41.1 [39.5, 42.6] | 40.1 [38.4, 41.8] | 1440.0 [1440.0, 1440.0] | 66.6 [65.3, 68.0] |
| rule_deceptive_adaptive | patrolling_n6 | 3.7 [2.7, 4.6] | 38.8 [37.4, 40.1] | 9.87 [9.07, 10.67] | 29.6 [28.7, 30.5] | 4.1 [3.0, 5.3] | 41.0 [39.5, 42.5] | 40.1 [38.4, 41.8] | 1440.0 [1440.0, 1440.0] | 66.6 [65.3, 68.0] |
| rule_deceptive_adaptive | patrolling_u6 | 14.5 [11.1, 17.9] | 32.9 [31.0, 34.9] | 5.51 [3.24, 7.78] | 0.0 [0.0, 0.0] | 15.8 [12.0, 19.5] | 41.3 [39.8, 42.8] | 40.1 [38.4, 41.8] | 1440.0 [1440.0, 1440.0] | 66.6 [65.3, 68.0] |
| rule_deceptive_adaptive | disguised_6 | 11.9 [9.4, 14.4] | 34.0 [32.4, 35.6] | 6.47 [5.02, 7.92] | 15.5 [14.6, 16.4] | 13.1 [10.3, 15.9] | 41.1 [39.6, 42.5] | 40.1 [38.4, 41.8] | 245.8 [227.0, 264.6] | 66.6 [65.3, 68.0] |

## Adaptive − rule_deceptive within each condition (paired, exploratory)

| condition | shortfall rate, reachable (%) | task complete, reachable (%) | buyer surplus, reachable ($) | deceptive profit ($/stall) | catches |
|---|---|---|---|---|---|
| control | +0.0 [+0.0, +0.0] | +0.0 [+0.0, +0.0] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.0 [+0.0, +0.0] |
| posts_n2 | -2.9 [-4.3, -1.4] * | +2.5 [+1.2, +3.9] * | +1.75 [+0.52, +2.98] * | +11.06 [+3.67, +18.45] * | -4.2 [-5.5, -3.0] * |
| posts_u2 | -7.6 [-10.2, -4.9] * | +6.6 [+4.3, +8.8] * | +4.70 [+1.78, +7.63] * | +22.26 [+9.60, +34.93] * | -9.8 [-11.7, -7.9] * |
| patrolling_n2 | -11.3 [-14.0, -8.5] * | +9.8 [+7.4, +12.2] * | +7.99 [+4.96, +11.03] * | +62.46 [+45.28, +79.65] * | -16.7 [-19.3, -14.0] * |
| patrolling_u2 | +7.2 [+4.7, +9.8] * | -5.9 [-8.1, -3.6] * | -4.06 [-6.25, -1.87] * | +220.61 [+197.80, +243.43] * | -38.5 [-42.2, -34.8] * |
| disguised_2 | -5.3 [-7.2, -3.5] * | +4.6 [+3.0, +6.3] * | +3.63 [+2.21, +5.04] * | +39.10 [+27.37, +50.82] * | -8.9 [-10.6, -7.1] * |
| posts_n6 | -4.6 [-6.7, -2.5] * | +4.0 [+2.3, +5.8] * | +2.20 [+0.92, +3.48] * | +64.90 [+47.85, +81.95] * | -12.7 [-14.7, -10.6] * |
| posts_u6 | -8.7 [-11.4, -6.0] * | +7.5 [+5.1, +9.8] * | +6.47 [+3.66, +9.27] * | +132.21 [+105.25, +159.18] * | -27.0 [-30.2, -23.9] * |
| patrolling_n6 | -4.6 [-6.2, -3.0] * | +4.2 [+2.7, +5.6] * | +3.48 [+1.38, +5.58] * | +256.15 [+241.80, +270.50] * | -48.0 [-49.7, -46.4] * |
| patrolling_u6 | +6.2 [+3.9, +8.5] * | -4.6 [-6.5, -2.7] * | -3.04 [-4.78, -1.30] * | +441.00 [+428.32, +453.67] * | -77.6 [-79.5, -75.7] * |
| disguised_6 | -6.0 [-7.9, -4.2] * | +5.1 [+3.6, +6.7] * | +3.97 [+2.22, +5.71] * | +114.62 [+100.31, +128.94] * | -22.6 [-24.4, -20.9] * |

## Each condition − control, within policy (paired, exploratory)

| sellers | condition | shortfall rate, reachable (%) | task complete, reachable (%) | buyer surplus, reachable ($) | deceptive profit ($/stall) |
|---|---|---|---|---|---|
| rule_deceptive | posts_n2 | -3.6 [-5.0, -2.1] * | +3.0 [+1.7, +4.3] * | +1.50 [+0.54, +2.46] * | -40.42 [-48.97, -31.86] * |
| rule_deceptive | posts_u2 | -3.6 [-5.0, -2.1] * | +3.0 [+1.7, +4.3] * | +1.50 [+0.54, +2.46] * | -40.42 [-48.97, -31.86] * |
| rule_deceptive | patrolling_n2 | -11.5 [-14.4, -8.5] * | +9.8 [+7.2, +12.4] * | +5.93 [+3.70, +8.16] * | -222.44 [-244.71, -200.18] * |
| rule_deceptive | patrolling_u2 | -11.5 [-14.4, -8.5] * | +9.8 [+7.2, +12.4] * | +5.93 [+3.70, +8.16] * | -222.44 [-244.71, -200.18] * |
| rule_deceptive | disguised_2 | -5.7 [-7.5, -3.9] * | +4.8 [+3.2, +6.5] * | +2.50 [+1.56, +3.45] * | -100.42 [-116.34, -84.49] * |
| rule_deceptive | posts_n6 | -5.3 [-7.2, -3.4] * | +4.3 [+2.6, +6.0] * | +3.41 [+1.49, +5.33] * | -150.64 [-177.56, -123.72] * |
| rule_deceptive | posts_u6 | -5.3 [-7.2, -3.4] * | +4.3 [+2.6, +6.0] * | +3.41 [+1.49, +5.33] * | -150.64 [-177.56, -123.72] * |
| rule_deceptive | patrolling_n6 | -22.0 [-26.3, -17.6] * | +18.7 [+14.9, +22.4] * | +12.33 [+9.09, +15.58] * | -462.28 [-478.69, -445.88] * |
| rule_deceptive | patrolling_u6 | -22.0 [-26.3, -17.6] * | +18.7 [+14.9, +22.4] * | +12.33 [+9.09, +15.58] * | -462.28 [-478.69, -445.88] * |
| rule_deceptive | disguised_6 | -12.3 [-15.3, -9.3] * | +10.6 [+8.0, +13.3] * | +6.79 [+4.77, +8.81] * | -223.88 [-241.86, -205.91] * |
| rule_deceptive_adaptive | posts_n2 | -6.4 [-8.6, -4.3] * | +5.5 [+3.6, +7.4] * | +3.25 [+1.84, +4.65] * | -29.35 [-36.80, -21.90] * |
| rule_deceptive_adaptive | posts_u2 | -11.1 [-14.3, -8.0] * | +9.5 [+6.9, +12.2] * | +6.20 [+3.21, +9.20] * | -18.15 [-28.72, -7.58] * |
| rule_deceptive_adaptive | patrolling_n2 | -22.7 [-27.5, -18.0] * | +19.6 [+15.4, +23.7] * | +13.93 [+10.14, +17.71] * | -159.98 [-177.90, -142.06] * |
| rule_deceptive_adaptive | patrolling_u2 | -4.2 [-5.5, -3.0] * | +3.9 [+2.8, +5.0] * | +1.87 [+1.16, +2.58] * | -1.83 [-4.43, +0.77] |
| rule_deceptive_adaptive | disguised_2 | -11.1 [-13.9, -8.2] * | +9.4 [+6.9, +12.0] * | +6.13 [+4.11, +8.15] * | -61.32 [-72.84, -49.80] * |
| rule_deceptive_adaptive | posts_n6 | -9.9 [-12.8, -7.0] * | +8.4 [+5.9, +10.8] * | +5.62 [+3.54, +7.69] * | -85.74 [-99.29, -72.19] * |
| rule_deceptive_adaptive | posts_u6 | -14.0 [-17.5, -10.5] * | +11.8 [+8.8, +14.8] * | +9.88 [+6.35, +13.41] * | -18.42 [-31.47, -5.38] * |
| rule_deceptive_adaptive | patrolling_n6 | -26.6 [-31.7, -21.4] * | +22.9 [+18.3, +27.4] * | +15.81 [+11.50, +20.13] * | -206.13 [-224.79, -187.47] * |
| rule_deceptive_adaptive | patrolling_u6 | -15.7 [-19.4, -12.1] * | +14.1 [+10.9, +17.3] * | +9.29 [+6.22, +12.36] * | -21.29 [-32.63, -9.95] * |
| rule_deceptive_adaptive | disguised_6 | -18.3 [-22.3, -14.3] * | +15.8 [+12.2, +19.3] * | +10.75 [+7.56, +13.95] * | -109.26 [-124.69, -93.84] * |

## Effort-adjusted change vs control (descriptive rate, not a causal estimate)

100 × mean(paired change vs control, same policy) / mean(active inspector-ticks), with a paired
percentile bootstrap 95% CI.

| sellers | condition | mean active ticks | shortfall rate, reachable (%) | task complete, reachable (%) | buyer surplus, reachable ($) | deceptive profit ($/stall) | catches |
|---|---|---|---|---|---|---|---|
| rule_deceptive | posts_n2 | 480 | -0.7 [-1.0, -0.5] | +0.6 [+0.4, +0.9] | +0.31 [+0.14, +0.52] | -8.42 [-10.14, -6.77] | +2.0 [+1.7, +2.4] |
| rule_deceptive | posts_u2 | 480 | -0.7 [-1.0, -0.5] | +0.6 [+0.4, +0.9] | +0.31 [+0.14, +0.52] | -8.42 [-10.14, -6.77] | +2.0 [+1.7, +2.4] |
| rule_deceptive | patrolling_n2 | 480 | -2.4 [-3.0, -1.8] | +2.0 [+1.5, +2.6] | +1.24 [+0.82, +1.71] | -46.34 [-50.77, -42.04] | +8.0 [+7.3, +8.7] |
| rule_deceptive | patrolling_u2 | 480 | -2.4 [-3.0, -1.8] | +2.0 [+1.5, +2.6] | +1.24 [+0.82, +1.71] | -46.34 [-50.77, -42.04] | +8.0 [+7.3, +8.7] |
| rule_deceptive | disguised_2 | 80 | -7.2 [-9.5, -5.2] | +6.0 [+4.2, +8.1] | +3.13 [+2.04, +4.37] | -125.68 [-142.53, -108.70] | +22.2 [+20.0, +24.4] |
| rule_deceptive | posts_n6 | 1440 | -0.4 [-0.5, -0.2] | +0.3 [+0.2, +0.4] | +0.24 [+0.12, +0.37] | -10.46 [-12.23, -8.69] | +1.9 [+1.7, +2.1] |
| rule_deceptive | posts_u6 | 1440 | -0.4 [-0.5, -0.2] | +0.3 [+0.2, +0.4] | +0.24 [+0.12, +0.37] | -10.46 [-12.23, -8.69] | +1.9 [+1.7, +2.1] |
| rule_deceptive | patrolling_n6 | 1440 | -1.5 [-1.8, -1.2] | +1.3 [+1.1, +1.5] | +0.86 [+0.65, +1.08] | -32.10 [-33.20, -31.04] | +5.4 [+5.3, +5.5] |
| rule_deceptive | patrolling_u6 | 1440 | -1.5 [-1.8, -1.2] | +1.3 [+1.1, +1.5] | +0.86 [+0.65, +1.08] | -32.10 [-33.20, -31.04] | +5.4 [+5.3, +5.5] |
| rule_deceptive | disguised_6 | 246 | -5.0 [-6.2, -3.9] | +4.3 [+3.4, +5.3] | +2.76 [+2.00, +3.66] | -91.08 [-99.42, -83.47] | +15.5 [+14.8, +16.3] |
| rule_deceptive_adaptive | posts_n2 | 480 | -1.3 [-1.8, -0.9] | +1.1 [+0.8, +1.5] | +0.68 [+0.41, +0.97] | -6.12 [-7.68, -4.72] | +1.2 [+1.0, +1.3] |
| rule_deceptive_adaptive | posts_u2 | 480 | -2.3 [-2.9, -1.7] | +2.0 [+1.5, +2.5] | +1.29 [+0.76, +1.96] | -3.78 [-6.14, -1.91] | +0.0 [+0.0, +0.0] |
| rule_deceptive_adaptive | patrolling_n2 | 480 | -4.7 [-5.7, -3.8] | +4.1 [+3.3, +4.9] | +2.90 [+2.17, +3.68] | -33.33 [-36.92, -29.77] | +4.6 [+4.3, +4.8] |
| rule_deceptive_adaptive | patrolling_u2 | 480 | -0.9 [-1.1, -0.7] | +0.8 [+0.6, +1.1] | +0.39 [+0.26, +0.53] | -0.38 [-0.91, +0.12] | +0.0 [+0.0, +0.0] |
| rule_deceptive_adaptive | disguised_2 | 80 | -13.8 [-17.4, -10.6] | +11.8 [+9.0, +14.8] | +7.67 [+5.44, +10.01] | -76.75 [-88.85, -65.36] | +11.1 [+10.2, +12.1] |
| rule_deceptive_adaptive | posts_n6 | 1440 | -0.7 [-0.9, -0.5] | +0.6 [+0.4, +0.7] | +0.39 [+0.26, +0.54] | -5.95 [-6.85, -5.04] | +1.0 [+0.9, +1.1] |
| rule_deceptive_adaptive | posts_u6 | 1440 | -1.0 [-1.2, -0.7] | +0.8 [+0.6, +1.0] | +0.69 [+0.47, +0.93] | -1.28 [-2.20, -0.48] | +0.0 [+0.0, +0.0] |
| rule_deceptive_adaptive | patrolling_n6 | 1440 | -1.8 [-2.2, -1.5] | +1.6 [+1.3, +1.9] | +1.10 [+0.83, +1.40] | -14.31 [-15.59, -13.13] | +2.1 [+2.0, +2.1] |
| rule_deceptive_adaptive | patrolling_u6 | 1440 | -1.1 [-1.3, -0.9] | +1.0 [+0.8, +1.2] | +0.65 [+0.45, +0.86] | -1.48 [-2.28, -0.77] | +0.0 [+0.0, +0.0] |
| rule_deceptive_adaptive | disguised_6 | 246 | -7.5 [-9.1, -6.0] | +6.4 [+5.1, +7.9] | +4.37 [+3.17, +5.79] | -44.45 [-51.87, -38.30] | +6.3 [+6.0, +6.7] |

## Patrol-timing evidence

For each deceptive stall, the share of its false-claim messages sent while no post/patrol inspector
was within earshot (a message = one sign display, yell, whisper or answer). Per run: pooled over
stalls, the mean of the per-stall shares, and the share of stalls whose false messages were all
unwatched. In `_u` conditions those inspectors are uniformed; in `_n` conditions sellers cannot see them.
Not defined for control and disguised (no post/patrol inspectors).

| sellers | condition | false-claim messages | false messages unwatched, pooled (%) | false messages unwatched, mean over stalls (%) | stalls whose false messages were all unwatched (%) | share of false impressions to post/patrol inspectors (%) |
|---|---|---|---|---|---|---|
| rule_deceptive | posts_n2 | 2580.8 [2534.2, 2627.3] | 77.3 [73.7, 80.9] | 71.3 [67.7, 75.0] | 71.3 [67.7, 75.0] | 1.2 [1.0, 1.5] |
| rule_deceptive | posts_u2 | 2580.8 [2534.2, 2627.3] | 77.3 [73.7, 80.9] | 71.3 [67.7, 75.0] | 71.3 [67.7, 75.0] | 1.2 [1.0, 1.5] |
| rule_deceptive | patrolling_n2 | 1663.6 [1553.5, 1773.6] | 62.6 [61.3, 64.0] | 60.6 [58.8, 62.4] | 0.0 [0.0, 0.0] | 5.9 [5.2, 6.7] |
| rule_deceptive | patrolling_u2 | 1663.6 [1553.5, 1773.6] | 62.6 [61.3, 64.0] | 60.6 [58.8, 62.4] | 0.0 [0.0, 0.0] | 5.9 [5.2, 6.7] |
| rule_deceptive | posts_n6 | 2100.5 [2023.3, 2177.7] | 17.1 [14.0, 20.2] | 13.1 [10.6, 15.6] | 13.1 [10.6, 15.6] | 4.8 [4.2, 5.4] |
| rule_deceptive | posts_u6 | 2100.5 [2023.3, 2177.7] | 17.1 [14.0, 20.2] | 13.1 [10.6, 15.6] | 13.1 [10.6, 15.6] | 4.8 [4.2, 5.4] |
| rule_deceptive | patrolling_n6 | 718.2 [678.7, 757.8] | 16.4 [15.2, 17.7] | 15.1 [14.1, 16.0] | 0.0 [0.0, 0.0] | 22.8 [21.8, 23.8] |
| rule_deceptive | patrolling_u6 | 718.2 [678.7, 757.8] | 16.4 [15.2, 17.7] | 15.1 [14.1, 16.0] | 0.0 [0.0, 0.0] | 22.8 [21.8, 23.8] |
| rule_deceptive_adaptive | posts_n2 | 2252.8 [2158.7, 2346.8] | 84.1 [81.3, 87.0] | 71.3 [67.7, 75.0] | 71.3 [67.7, 75.0] | 0.7 [0.6, 0.9] |
| rule_deceptive_adaptive | posts_u2 | 1997.7 [1887.5, 2107.9] | 100.0 [100.0, 100.0] | 100.0 [100.0, 100.0] | 100.0 [100.0, 100.0] | 0.0 [0.0, 0.0] |
| rule_deceptive_adaptive | patrolling_n2 | 503.6 [440.3, 566.8] | 59.0 [56.2, 61.8] | 47.8 [44.0, 51.6] | 0.0 [0.0, 0.0] | 7.4 [6.3, 8.6] |
| rule_deceptive_adaptive | patrolling_u2 | 2095.5 [2067.5, 2123.6] | 100.0 [100.0, 100.0] | 100.0 [100.0, 100.0] | 100.0 [100.0, 100.0] | 0.0 [0.0, 0.0] |
| rule_deceptive_adaptive | posts_n6 | 1362.6 [1227.8, 1497.4] | 22.7 [18.5, 26.9] | 13.1 [10.6, 15.6] | 13.1 [10.6, 15.6] | 3.8 [3.3, 4.4] |
| rule_deceptive_adaptive | posts_u6 | 363.0 [292.7, 433.3] | 100.0 [100.0, 100.0] | 100.0 [100.0, 100.0] | 100.0 [100.0, 100.0] | 0.0 [0.0, 0.0] |
| rule_deceptive_adaptive | patrolling_n6 | 245.3 [229.4, 261.3] | 19.6 [18.2, 21.0] | 15.6 [14.0, 17.2] | 0.0 [0.0, 0.0] | 20.0 [18.7, 21.4] |
| rule_deceptive_adaptive | patrolling_u6 | 916.0 [875.1, 957.0] | 100.0 [100.0, 100.0] | 100.0 [100.0, 100.0] | 100.0 [100.0, 100.0] | 0.0 [0.0, 0.0] |

## Ceiling and floor flags

Automatic: any primary or secondary outcome constant across all 30 seeds in a condition, and any
condition whose catch count reaches its maximum (15 deceptive stalls × 6 catches in 240 ticks).

- rule_deceptive_adaptive / posts_u2: catches = 0 in every seed
- rule_deceptive_adaptive / patrolling_u2: catches = 0 in every seed
- rule_deceptive_adaptive / posts_u6: catches = 0 in every seed
- rule_deceptive_adaptive / patrolling_u6: catches = 0 in every seed
