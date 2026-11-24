#!/bin/sh
# Price-war main run (plan 2026-11-23, Stage 2): seeds 500-519, no cut.
cd "/Users/randallbennington/Bazaar Markets" || exit 1
PYTHONPATH=. caffeinate -i nice -n 19 .venv/bin/python -m analysis.price_war --workers 4 --min-swap-mb 0 \
  --tests "runs/tests_120.log: 1868 passed, 17 skipped, 4 outdated tests updated (8cfaa73), their files 69/69; tests/test_v120.py 28/28"
echo "exit $? main $(date '+%Y-%m-%d %H:%M:%S')"
