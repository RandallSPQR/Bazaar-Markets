#!/bin/sh
# Brand Equity speed (engine 0.19.0, ratings.prior_scope new, 60 days): 4 workers, nice 19, the memory guard (new
# chains paused below 512 MB free swap or 15% free memory), load/memory logged every 50 chains. Run log:
# runs/brand_equity_speed_run.log; stdout runs/brand_equity_speed_stdout.log. The script stops on a failed royalty
# check and exits non-zero on any flag (guard, invalid action, ledger, J or window identity, genuine-tier price
# check). It resumes from its cache if restarted. Prepared by the pilot gate (runs/pilot_brand_equity_speed.md).
# NOT LAUNCHED. Launch from the repo root:
#   nohup sh runs/queue_brand_equity_speed.sh > runs/queue_brand_equity_speed.log 2>&1 &
set -e
cd "$(dirname "$0")/.."
TESTS="Full suite at engine 0.19.0 (8b7884b): 1424 passed, 17 skipped (runs/tests_0190.log)"
GATE="Pilot gate G1–G5 passed (runs/pilot_brand_equity_speed.md); levels from runs/calibration_brand_equity_speed.md"
echo "$(date '+%F %T') queue start; commit $(git rev-parse --short HEAD); load $(sysctl -n vm.loadavg)"
nice -n 19 .venv/bin/python -m analysis.brand_equity_speed --seeds 330-349 --workers 4 --tests "$TESTS" \
    --gate "$GATE" > runs/brand_equity_speed_stdout.log 2>&1
echo "$(date '+%F %T') brand equity speed done; queue done; load $(sysctl -n vm.loadavg)"
