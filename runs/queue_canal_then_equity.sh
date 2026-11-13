#!/bin/sh
# Canal Street, then Brand Equity (engine 0.17.0), one after the other: 4 workers, nice 19, the memory guard
# (new chains paused below 512 MB free swap or 15% free memory) and load/memory logged every 50 chains, as in the
# licensing run. Each run writes its own run log: runs/canal_street_run.log, runs/brand_equity_run.log.
# Canal Street exits non-zero on any flag (guard, invalid action, counterfeit or ledger check), and Brand Equity
# on a failed royalty check: either stops the queue (set -e). Both resume from their caches if restarted.
# Prepared by the pilot gate (runs/pilot_canal_equity.md). Launch from the repo root:
#   nohup sh runs/queue_canal_then_equity.sh > runs/queue_canal_then_equity.log 2>&1 &
set -e
cd "$(dirname "$0")/.."
TESTS="1109 passed, 17 skipped at e9cdc07 (runs/tests_0170.log)"
GATE="Pilot gate G1–G5 passed at 5458448 (runs/pilot_canal_equity.md)"
echo "$(date '+%F %T') queue start; commit $(git rev-parse --short HEAD); load $(sysctl -n vm.loadavg)"
nice -n 19 .venv/bin/python -m analysis.canal_street --seeds 270-299 --workers 4 --tests "$TESTS" --gate "$GATE" \
    > runs/canal_street_stdout.log 2>&1
echo "$(date '+%F %T') canal street done; load $(sysctl -n vm.loadavg)"
nice -n 19 .venv/bin/python -m analysis.brand_equity --seeds 300-329 --workers 4 --tests "$TESTS" --gate "$GATE" \
    > runs/brand_equity_stdout.log 2>&1
echo "$(date '+%F %T') brand equity done; queue done; load $(sysctl -n vm.loadavg)"
