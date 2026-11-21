#!/bin/sh
# Stage 3C robustness sweep (engine 1.1.0): all 15 cells (5 price policies x 3 choice rules), 10 seeds per study,
# no trims, whatever the timing pilot projects (plan deviation D6). The base cell (rating_indexed x lex) runs first so
# its reproduction check can be read early. 4 workers, nice 19, caffeinate -i (D2), free-memory guard on, swap guard
# off (D3). Resumes from runs/robustness_1_1_cache.jsonl if restarted; the script exits 2 on any flag. Launch from
# the repo root:
#   nohup sh runs/queue_robustness_1_1.sh > runs/queue_robustness_1_1.log 2>&1 &
set -e
cd "$(dirname "$0")/.."
TESTS="runs/tests_110.log + runs/tests_110_fix.log: 1,836 + fix 67/67; tests/test_robustness_1_1.py 3/3"
echo "$(date '+%F %T') queue start; commit $(git rev-parse --short HEAD); load $(sysctl -n vm.loadavg)"
PYTHONPATH=. caffeinate -i nice -n 19 .venv/bin/python -m analysis.robustness_1_1 --workers 4 --min-swap-mb 0 \
    --tests "$TESTS" > runs/robustness_1_1_stdout.log 2>&1
echo "$(date '+%F %T') sweep done; load $(sysctl -n vm.loadavg)"
