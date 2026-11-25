#!/bin/sh
# Bank v2 (plan 2026-11-23, Stage 3): design, enumerate, pilot, in order; each stops the queue if it fails.
cd "/Users/randallbennington/Bazaar Markets" || exit 1
T="runs/tests_120.log: 1868 passed, 17 skipped, 4 outdated tests updated (8cfaa73), their files 69/69; tests/test_v120.py 28/28"
for ph in design enumerate pilot; do
  PYTHONPATH=. caffeinate -i nice -n 19 .venv/bin/python -m analysis.state_bank_v2 --phase $ph --workers 4 --min-swap-mb 0 --tests "$T"
  rc=$?; echo "exit $rc $ph $(date '+%Y-%m-%d %H:%M:%S')"
  [ $rc -eq 0 ] || exit $rc
done
