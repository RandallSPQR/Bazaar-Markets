#!/bin/sh
# Brand Equity at the genuine tier, with rating speed (engine 0.18.0): 4 workers, nice 19, the memory guard (new
# chains paused below 512 MB free swap or 15% free memory), load/memory logged every 50 chains. Run log:
# runs/brand_equity_tier_run.log; stdout runs/brand_equity_tier_stdout.log. The script stops on a failed royalty
# check and exits non-zero on any flag (guard, invalid action, ledger, 0.17.0 identity, genuine-tier price check).
# It resumes from its cache if restarted. Prepared by the pilot gate (runs/pilot_brand_equity_tier.md). Launch
# from the repo root:
#   nohup sh runs/queue_brand_equity_tier.sh > runs/queue_brand_equity_tier.log 2>&1 &
set -e
cd "$(dirname "$0")/.."
TESTS="1261 passed, 17 skipped at 20ee303 (runs/tests_0180.log)"
GATE="Pilot gate G1–G5 passed (runs/pilot_brand_equity_tier.md); levels from runs/calibration_rating_speed.md"
echo "$(date '+%F %T') queue start; commit $(git rev-parse --short HEAD); load $(sysctl -n vm.loadavg)"
nice -n 19 .venv/bin/python -m analysis.brand_equity_tier --seeds 300-329 --workers 4 --tests "$TESTS" --gate "$GATE" \
    > runs/brand_equity_tier_stdout.log 2>&1
echo "$(date '+%F %T') brand equity tier done; queue done; load $(sysctl -n vm.loadavg)"
