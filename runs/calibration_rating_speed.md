# Calibration: rating speed (ratings.prior_n)

Engine 0.18.0 (working tree at calibration time; committed unchanged as 20ee303). Pilot seeds 900–902, before any main run. Script `analysis/calibrate_rating_speed.py`; 312 chains; log `runs/calibration_rating_speed/calibration_run.log`; data `runs/calibration_rating_speed/calibration.json`.

For each prior_n: W_g chains (contract white labels at the genuine tier, N 6 from day 10) for the 3 sampled owners of each seed at t40 and t100, and the never chain. Days to 0.9: from day 10 (= 1) until a white label's end-of-day rating first reaches 0.9; mean over labels per owner, then over owners and seeds (95% t over 3 seeds). The owner's own rating builds under the same prior from day 1.

| prior_n | Cell | Days to 0.9 | Median (range) over labels | Share reaching 0.9 by day 30 | Owner rating day 10, never | Owner rating day 10, W_g |
|---|---|---|---|---|---|---|
| 0 | t40 | 1.0 [1.0, 1.1] | 1 (1–2) | 1.00 [1.00, 1.00] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| 1 | t40 | 1.5 [0.2, 2.9] | 1 (1–5) | 1.00 [1.00, 1.00] | 0.987 [0.986, 0.989] | 0.987 [0.986, 0.988] |
| 2 | t40 | 3.5 [1.8, 5.2] | 4 (1–7) | 1.00 [1.00, 1.00] | 0.977 [0.973, 0.980] | 0.976 [0.972, 0.979] |
| 2.5 | t40 | 4.8 [2.2, 7.4] | 5 (1–9) | 1.00 [1.00, 1.00] | 0.971 [0.968, 0.974] | 0.970 [0.967, 0.974] |
| 3 | t40 | 5.6 [2.9, 8.3] | 6 (1–9) | 1.00 [1.00, 1.00] | 0.967 [0.963, 0.970] | 0.965 [0.961, 0.970] |
| 5 | t40 | 8.1 [7.8, 8.4] | 8 (6–10) | 1.00 [1.00, 1.00] | 0.950 [0.946, 0.954] | 0.949 [0.943, 0.954] |
| 7 | t40 | 9.2 [8.5, 10.0] | 9 (7–11) | 1.00 [1.00, 1.00] | 0.936 [0.933, 0.940] | 0.933 [0.929, 0.937] |
| 10 | t40 | 10.6 [10.1, 11.1] | 10 (9–13) | 1.00 [1.00, 1.00] | 0.918 [0.915, 0.921] | 0.914 [0.912, 0.915] |
| 25 | t40 | 13.1 [12.7, 13.4] | 13 (12–15) | 1.00 [1.00, 1.00] | 0.855 [0.846, 0.863] | 0.846 [0.834, 0.859] |
| 50 | t40 | 14.9 [14.6, 15.2] | 15 (14–16) | 1.00 [1.00, 1.00] | 0.787 [0.757, 0.816] | 0.783 [0.761, 0.804] |
| 100 | t40 | 17.0 [16.5, 17.5] | 17 (16–19) | 1.00 [1.00, 1.00] | 0.717 [0.679, 0.755] | 0.710 [0.676, 0.744] |
| 150 | t40 | 18.1 [17.5, 18.7] | 18 (17–20) | 1.00 [1.00, 1.00] | 0.678 [0.639, 0.716] | 0.672 [0.644, 0.700] |
| 200 | t40 | 18.9 [18.2, 19.7] | 19 (18–21) | 1.00 [1.00, 1.00] | 0.649 [0.618, 0.679] | 0.641 [0.623, 0.660] |
| 0 | t100 | 1.0 [1.0, 1.0] | 1 (1–1) | 1.00 [1.00, 1.00] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| 1 | t100 | 1.2 [0.3, 2.2] | 1 (1–5) | 1.00 [1.00, 1.00] | 0.985 [0.985, 0.986] | 0.984 [0.981, 0.987] |
| 2 | t100 | 1.9 [0.9, 3.0] | 1 (1–6) | 1.00 [1.00, 1.00] | 0.973 [0.972, 0.975] | 0.971 [0.966, 0.976] |
| 2.5 | t100 | 2.7 [1.3, 4.1] | 2.5 (1–6) | 1.00 [1.00, 1.00] | 0.967 [0.965, 0.970] | 0.964 [0.955, 0.973] |
| 3 | t100 | 3.7 [2.4, 5.1] | 4 (1–7) | 1.00 [1.00, 1.00] | 0.962 [0.955, 0.970] | 0.958 [0.941, 0.975] |
| 5 | t100 | 6.7 [5.0, 8.4] | 7 (1–8) | 1.00 [1.00, 1.00] | 0.943 [0.929, 0.958] | 0.941 [0.926, 0.956] |
| 7 | t100 | 8.2 [7.3, 9.1] | 8 (7–9) | 1.00 [1.00, 1.00] | 0.930 [0.917, 0.942] | 0.923 [0.903, 0.943] |
| 10 | t100 | 9.4 [8.8, 9.9] | 9 (9–10) | 1.00 [1.00, 1.00] | 0.912 [0.899, 0.924] | 0.900 [0.872, 0.928] |
| 25 | t100 | 12.1 [11.0, 13.1] | 12 (11–13) | 1.00 [1.00, 1.00] | 0.839 [0.813, 0.866] | 0.825 [0.782, 0.868] |
| 50 | t100 | 13.9 [13.6, 14.2] | 14 (13–15) | 1.00 [1.00, 1.00] | 0.779 [0.750, 0.808] | 0.755 [0.698, 0.812] |
| 100 | t100 | 15.9 [15.4, 16.3] | 16 (15–17) | 1.00 [1.00, 1.00] | 0.707 [0.685, 0.729] | 0.678 [0.657, 0.699] |
| 150 | t100 | 17.1 [16.1, 18.0] | 17 (16–19) | 1.00 [1.00, 1.00] | 0.665 [0.637, 0.694] | 0.640 [0.607, 0.672] |
| 200 | t100 | 17.9 [17.4, 18.4] | 18 (17–19) | 1.00 [1.00, 1.00] | 0.644 [0.630, 0.657] | 0.613 [0.592, 0.635] |

## Levels chosen

Targets about 1, 5 and 15 days at t40 (the PR1 cell), chosen from the measurements above:

| Level | prior_n | Days to 0.9, t40 (t100) | Owner rating day 10, never, t40 |
|---|---|---|---|
| current | 0 | 1.04 (1.00) | 1.000 |
| slow5 | 2.5 | 4.78 (2.70) | 0.971 |
| slow15 | 50 | 14.91 (13.93) | 0.787 |

Notes:

- The dial is steep at the low end: prior_n 2 gives 3.5 days, 2.5 gives 4.8, 3 gives 5.6. At 2.5 the labels are spread widely (1 to 9 days at t40, median 5), because a label's speed depends on how many rated units it sells on its first days. At t100 the same prior gives 2.7 days.
- At prior_n 50 the labels are tightly grouped (14 to 16 days at t40).
- The owner's day-10 rating falls with the prior: 1.000, 0.971 and 0.787 at the three levels (t40). Every brand builds under the same prior, so the slow levels also change the never chains.
- The PR1 and PR4 slopes use the t40 days to 0.9 above as x: 1.04, 4.78, 14.91 (fixed in `analysis/brand_equity_tier.py` before any main run).
