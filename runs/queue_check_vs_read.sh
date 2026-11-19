#!/bin/sh
# Stage 1 main run: checking vs reading ratings (engine 0.21.0). Full prespecified design (G3 waived by Randall, plan
# deviation D4): seeds 350-369 in two back-to-back blocks of 10 (D1), then a final pass over all 20 from the cache.
# 4 workers, nice 19, caffeinate -i (D2), free-memory guard on, swap guard off (D3). Each block resumes from the cache if
# restarted and exits non-zero on any flag, which stops the queue. Launch from the repo root:
#   nohup sh runs/queue_check_vs_read.sh > runs/queue_check_vs_read.log 2>&1 &
set -e
cd "$(dirname "$0")/.."
TESTS="Engine 0.21.0 (4a83784): full suite 1799 passed, 17 skipped (runs/tests_0210.log); 174 0.20.0 reference cells reproduce byte for byte"
GATE="Pilot G1, G2, G4, G5 pass (G4 after one comparison fix); G3 failed (7.18 h after trims) and was waived by Randall for the full design (runs/pilot_check_vs_read.md, plan deviation D4)"
run() {
  PYTHONPATH=. caffeinate -i nice -n 19 .venv/bin/python -m analysis.check_vs_read --seeds "$1" --workers 4 --min-swap-mb 0 \
      --tests "$TESTS" --gate "$GATE" > "runs/check_vs_read_stdout_$2.log" 2>&1
}
echo "$(date '+%F %T') queue start; commit $(git rev-parse --short HEAD); load $(sysctl -n vm.loadavg)"
run 350-359 block1
echo "$(date '+%F %T') block 1 (350-359) done; load $(sysctl -n vm.loadavg)"
run 360-369 block2
echo "$(date '+%F %T') block 2 (360-369) done; load $(sysctl -n vm.loadavg)"
run 350-369 final
echo "$(date '+%F %T') final pass (350-369) done; queue done; load $(sysctl -n vm.loadavg)"
