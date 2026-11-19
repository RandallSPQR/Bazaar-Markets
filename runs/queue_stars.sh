#!/bin/sh
# Displayed ratings (engine 0.20.0): Run A (Brand Equity speed under stars) then Run B (rounding sensitivity of earlier
# headlines). 4 workers, nice 19, the memory guard; each run resumes from its cache if restarted and exits non-zero on
# any flag. Prepared by the pilot gate (runs/pilot_stars.md). --min-swap-mb 0: after a fresh boot macOS has no swap file
# (free swap reads 0), which the swap guard took as a shortage; the free-memory guard (>= 15%) stays on.
# Full design, about 9.8 h at the pilot's load. NOT LAUNCHED. Launch from the repo root:
#   nohup sh runs/queue_stars.sh > runs/queue_stars.log 2>&1 &
set -e
cd "$(dirname "$0")/.."
TESTS="Engine 0.20.0 (952af31): full suite 1602 passed, 17 skipped, 1 failed (missing scaling rules, fixed); rerun of test_scale.py and test_v0200.py 222 passed (runs/tests_0200.log)"
GATE="Pilot gate G1–G5 passed (runs/pilot_stars.md); G3 cut waived by the user for the full design (step 0.1 cells on, Run B 10 seeds per study)"
echo "$(date '+%F %T') queue start; commit $(git rev-parse --short HEAD); load $(sysctl -n vm.loadavg)"
nice -n 19 .venv/bin/python -m analysis.brand_equity_stars --seeds 330-349 --workers 4 --min-swap-mb 0 --tests "$TESTS" \
    --gate "$GATE" > runs/brand_equity_stars_stdout.log 2>&1
echo "$(date '+%F %T') run A done; load $(sysctl -n vm.loadavg)"
nice -n 19 .venv/bin/python -m analysis.stars_sensitivity --repro-file runs/pilot_stars/stars_sensitivity_repro.json --seeds-per-study 10 --workers 4 --min-swap-mb 0 --tests "$TESTS" \
    --gate "$GATE" > runs/stars_sensitivity_stdout.log 2>&1
echo "$(date '+%F %T') run B done; queue done; load $(sysctl -n vm.loadavg)"
