#!/bin/sh
# Main runs A,B,C in blocks of at most 10 h, back to back, resuming from the cache.
cd "/Users/randallbennington/Bazaar Markets" || exit 1
T="1901 passed, 17 skipped, 0 failed at 9023acf (runs/tests_131.log)"
for i in 1 2 3; do
  echo "block $i start $(date '+%Y-%m-%d %H:%M:%S')"
  PYTHONPATH=. .venv/bin/python -m analysis.aisles_1_3 --phase run --runs A,B,C --max-secs 36000 --tests "$T" || { echo "block $i exited $?"; exit 1; }
  if tail -1 runs/aisles_run.log | grep -q "complete True"; then echo "all runs complete $(date '+%Y-%m-%d %H:%M:%S')"; exit 0; fi
done
echo "not complete after 3 blocks"; exit 2
