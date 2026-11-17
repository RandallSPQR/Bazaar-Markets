# Calibration: rating speed for Brand Equity speed (ratings.prior_n, prior_scope "new", 60 days)

Engine 0.19.0, commit 8b7884b. Calibration seeds 900–904, before any pilot or main run. Script `analysis/calibrate_brand_equity_speed.py`; 540 chains (420 on the first grid, 120 on the refinement), 0 flagged by the guard, ledger or tier-price checks; wall 114.8 + 27.2 min at nice 19, 4 workers. Log `runs/calibration_brand_equity_speed/calibration_run.log`; data `runs/calibration_brand_equity_speed/calibration.json`.

Commands:

    PYTHONPATH=. .venv/bin/python -m analysis.calibrate_brand_equity_speed --grid 0,1,2,3,5,7,10,15,25,50,100,200,400,800
    PYTHONPATH=. .venv/bin/python -m analysis.calibrate_brand_equity_speed --grid 0,1,2,3,3.25,3.5,4,4.5,5,7,10,15,25,50,100,200,400,800
    PYTHONPATH=. .venv/bin/python -m analysis.calibrate_brand_equity_speed --grid (same) --choose current=0,d5=3.5,d10=10,d20=400

Cell: contract, t40, R and W_g, N 6 white labels from day 10, the 3 sampled owners of each seed, scope "new" (the prior reaches only brands created on day 2 or later), 60 days. Days to 0.9: from day 10 (= 1) until a W_g white label's end-of-day rating first reaches 0.9, pooled over the 6 labels × 3 owners × 5 seeds = 90 labels. The spread rule passes when p10 ≥ 0.5 × mean and p90 ≤ 1.5 × mean. Per-seed: the mean over a seed's labels, then 95% t over the 5 seeds (unadjusted).

| prior_n | Days to 0.9, mean | p10–p90 | Spread | Median (range) | Per-seed mean [95% t] | Owner catch-up day | Reopened deceptive names, day-20 rating (R / W_g) |
|---|---|---|---|---|---|---|---|
| 0 | 1.04 | 1–1 | ok | 1 (1–2) | 1.04 [1.01, 1.08] | 1.0 | 0.000 / 0.000 |
| 1 | 1.64 | 1–4 | wide | 1 (1–6) | 1.64 [1.14, 2.15] | 1.6 | 0.165 / 0.161 |
| 2 | 3.58 | 1–6 | wide | 4 (1–7) | 3.58 [2.93, 4.22] | 5.0 | 0.243 / 0.240 |
| 3 | 5.66 | 1.9–8 | wide | 6 (1–8) | 5.66 [4.68, 6.63] | 6.5 | 0.290 / 0.287 |
| 3.25 | 5.92 | 1.9–8 | wide | 6 (1–9) | 5.92 [4.98, 6.87] | 6.8 | 0.299 / 0.296 |
| **3.5** | **6.36** | **4.7–8** | **ok** | 7 (1–9) | 6.36 [5.46, 7.25] | 7.0 | 0.307 / 0.304 |
| 4 | 7.08 | 6–8 | ok | 7 (1–10) | 7.08 [6.51, 7.64] | 7.5 | 0.322 / 0.319 |
| 4.5 | 7.63 | 7–9 | ok | 8 (1–10) | 7.63 [7.14, 8.12] | 7.8 | 0.334 / 0.331 |
| 5 | 8.11 | 7–9 | ok | 8 (6–11) | 8.11 [7.85, 8.37] | 8.2 | 0.345 / 0.342 |
| 7 | 9.19 | 8–10 | ok | 9 (7–11) | 9.19 [8.78, 9.60] | 9.2 | 0.377 / 0.374 |
| **10** | **10.38** | **9–11.1** | **ok** | 10 (8–13) | 10.38 [10.03, 10.73] | 10.3 | 0.406 / 0.404 |
| 15 | 11.49 | 11–12 | ok | 11 (9–14) | 11.49 [11.13, 11.85] | 11.6 | 0.432 / 0.430 |
| 25 | 12.96 | 12–14 | ok | 13 (11–15) | 12.96 [12.78, 13.13] | 13.0 | 0.456 / 0.455 |
| 50 | 14.83 | 14–16 | ok | 15 (13–16) | 14.83 [14.60, 15.07] | 14.9 | 0.477 / 0.477 |
| 100 | 16.78 | 16–18 | ok | 17 (15–19) | 16.78 [16.60, 16.95] | 16.9 | 0.488 / 0.488 |
| 200 | 18.86 | 18–20 | ok | 19 (18–21) | 18.86 [18.67, 19.04] | 18.9 | 0.494 / 0.494 |
| **400** | **20.76** | **20–22** | **ok** | 21 (19–22) | 20.76 [20.47, 21.04] | 20.8 | 0.497 / 0.497 |
| 800 | 22.66 | 22–24 | ok | 23 (21–25) | 22.66 [22.25, 23.06] | 22.9 | 0.498 / 0.498 |

Every label reached 0.9 by day 60 at every prior_n, and every owner caught up (owner catch-up day: the first day the mean of its 6 labels' ratings is ≥ 0.9, counted from day 10 = 1).

The owner's own rating at the end of day 10 is 1.000 under R and W_g at every prior_n: under scope "new" the owner's brand (created on day 1) gets no prior, as intended (the 0.18.0 slow levels had cut it to 0.79 at prior_n 50).

Reopened deceptive names on day 20 (mean rating of the names deceptive stalls reopen under; unrated not counted): 0 without a prior, rising toward the prior's 0.5 as prior_n grows. A slow dial therefore also slows how fast a reopened deceptive stall is found out; this is part of what the speed levels change, not only the white labels.

## Levels chosen

| Level | prior_n | Days to 0.9 (x of PS1, PS4) | p10–p90 | Target |
|---|---|---|---|---|
| current | 0 | 1.044 | 1–1 | about 1 |
| d5 | 3.5 | 6.356 | 4.7–8 | about 5 |
| d10 | 10 | 10.378 | 9–11.1 | about 10 |
| d20 | 400 | 20.756 | 20–22 | about 20 |

These values are fixed in `analysis/brand_equity_speed.py` (LEVELS, DAYS_TO_TARGET) before the pilot.

Notes:

- **The ~5-day level runs slow, at 6.4 days.** Nothing near 5 days passes the spread rule: prior_n 3 (5.66 days) and 3.25 (5.92) fail it because about a tenth of the labels reach 0.9 on day 1 or 2 while the rest take 6–8, so p10 sits far below half the mean. As before, a label's speed at a small prior depends on how many rated units it sells on its first days. The finer grid found the first passing value at prior_n 3.5, which gives 6.36 days. I kept it as the closest passing level. The alternative, prior_n 3 (closer to 5 days but failing the rule), would have given PS1 a noisier x.
- **prior_n 10 gives 10.4 days; 400 gives 20.8 (200 gives 18.9).** 400 is the closer of the two to 20. The dial is logarithmic at the slow end: each doubling of prior_n adds about 2 days.
- **The four x values are not evenly spaced** (1.0, 6.4, 10.4, 20.8). The PS1 slope is least squares over these values, per seed, as specified.
