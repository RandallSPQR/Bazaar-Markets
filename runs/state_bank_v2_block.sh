#!/bin/sh
# Bank v2 bank phase for one block (plan 2026-11-23, Stage 3). Usage: state_bank_v2_block.sh LABEL MARKETS [MAX_SECS]
# MAX_SECS (D5): stop the launch after this many seconds; the chain cache lets the next launch resume.
cd "/Users/randallbennington/Bazaar Markets" || exit 1
T="runs/tests_120.log: 1868 passed, 17 skipped, 4 outdated tests updated (8cfaa73), their files 69/69; tests/test_v120.py 28/28"
echo "start $1 $(date '+%Y-%m-%d %H:%M:%S')"
PYTHONPATH=. nice -n 19 .venv/bin/python -m analysis.state_bank_v2 --phase bank --markets "$2" --workers 4 --min-swap-mb 0 --tests "$T" &
pid=$!
if [ -n "$3" ]; then ( sleep "$3"; echo "time limit $3 s reached $(date '+%Y-%m-%d %H:%M:%S')"; pkill -TERM -P $pid; kill -TERM $pid ) & w=$!; fi
wait $pid; rc=$?
[ -n "$3" ] && kill $w 2>/dev/null
echo "exit $rc $1 $(date '+%Y-%m-%d %H:%M:%S')"
