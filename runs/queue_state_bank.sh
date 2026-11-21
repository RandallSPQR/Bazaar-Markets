#!/bin/sh
# Stage 3B state bank (engine 1.1.0): the full 200 states at K 20 (pilot gates passed, runs/pilot_state_bank.md).
# Projected 23.3 h, over the plan's two 10 h blocks; run in full at Randall's instruction (plan deviation D6) as four
# back-to-back blocks, one verification contrast (t40 and t100) per block, then the build phase.
# 4 workers, nice 19, caffeinate -i (D2), free-memory guard on, swap guard off (D3). Each block resumes from
# runs/state_bank/lottery_cache.jsonl if restarted; set -e stops the queue on any failure. Launch from the repo root:
#   nohup sh runs/queue_state_bank.sh > runs/queue_state_bank.log 2>&1 &
set -e
cd "$(dirname "$0")/.."
TESTS="runs/tests_110.log + runs/tests_110_fix.log: 1,836 + fix 67/67"
run() {
  PYTHONPATH=. caffeinate -i nice -n 19 .venv/bin/python analysis/state_bank.py --phase "$1" ${2:+--markets "$2"} \
      --workers 4 --min-swap-mb 0 --tests "$TESTS" >> runs/state_bank/bank.out 2>&1
}
echo "$(date '+%F %T') queue start; commit $(git rev-parse --short HEAD); load $(sysctl -n vm.loadavg)"
for X in "ds0|pn0" "ds0|pn10new" "ds1|pn0" "ds1|pn10new"; do
  run bank "t40|$X,t100|$X"
  echo "$(date '+%F %T') block $X done; load $(sysctl -n vm.loadavg)"
done
run build
echo "$(date '+%F %T') build done; queue done; load $(sysctl -n vm.loadavg)"
