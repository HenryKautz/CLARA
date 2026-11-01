#!/bin/bash
# run-followup-2026-10-17.sh -- after stopping run-sweep-2026-10-17.sh during
# 8x8 (every 8x8 sharpsat-td run had failed on FiFO's 600 s per-count limit and
# every mc-sat run had hit the 1200 s run limit):
#   1. max-term on the remaining 8x8 evidence;
#   2. the 7x7 sharpsat-td runs that failed on the 600 s per-count limit (or on
#      FlowCutter killed under load), rerun with recognize.sh --timeout 1200;
#   3. a sample of the capped 8x8 sharpsat-td runs (problem 1, 1 and 7
#      observations), rerun the same way, to see whether any finish.
# Run under nohup caffeinate -i; appends to sweep-2026-10-17.log.
cd "$(dirname "$0")" || exit 1
export FIFO_LISP=/Users/kautz/Programming/FiFO/lisp
LOG=sweep-2026-10-17.log
stamp() { echo "=== $(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

stamp "followup 1: max-term, rest of 8x8"
python3 run-recognize.py --methods max-term --limit 1200 --jobs 8 \
        --match '^evidence/grid8x8-' --work /tmp/sg-rec >> "$LOG" 2>&1 \
  || stamp "run-recognize.py exited $?"

stamp "followup 2: 7x7 sharpsat-td reruns, per-count limit 1200 s"
python3 run-recognize.py --methods sharpsat-td --limit 1200 --jobs 8 \
        --match '^evidence/grid7x7-' --rerun-solver-timeouts --work /tmp/sg-rec >> "$LOG" 2>&1 \
  || stamp "run-recognize.py exited $?"

stamp "followup 3: 8x8 sharpsat-td sample reruns, per-count limit 1200 s"
python3 run-recognize.py --methods sharpsat-td --limit 1200 --jobs 8 \
        --match '^evidence/grid8x8-1-.*-obs(1|7)\.txt$' --rerun-solver-timeouts \
        --work /tmp/sg-rec >> "$LOG" 2>&1 \
  || stamp "run-recognize.py exited $?"

stamp "followup done"
