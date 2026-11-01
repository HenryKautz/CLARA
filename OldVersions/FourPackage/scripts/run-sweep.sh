#!/bin/bash
# run-sweep.sh -- the whole FourPackage pipeline, each stage resumable (a rerun
# skips what is already recorded in ../results/).  Generation first:
#   1. the general problems planned (run-plans.py --stage general; wmaxcdcl, exact,
#      chosen by choose-solver.py)
#   2. each goal clamped, planned and its evidence written (--stage goals).  The
#      anytime tt-open-wbo-inc, stopped at 300 s with its best plan: the exact
#      solvers could not prove optimality at horizons past ~22 within 30 min.
#      A goal predicted too big for the heap is written but not planned (too-big).
#   3. the FiFO and weighted-CNF files (make-formats.py; wff for every problem)
#   4. Ramirez & Geffner recognition (run-recognize.py --methods max-term,
#      EvalMaxSAT), smallest size first, stopping at the size where it times out.
# Run under caffeinate.
set -u
cd "$(dirname "$0")"       # scripts/; every script finds the data in ..
LIMIT=${LIMIT:-1800}
echo "=== $(date '+%F %T') general problems, ${LIMIT}s per run"
python3 run-plans.py --stage general --solver wmaxcdcl --limit "$LIMIT"
echo "=== $(date '+%F %T') clamped goals and evidence, ${LIMIT}s per run"
python3 run-plans.py --stage goals --solver tt-open-wbo-inc-Glucose4_1 --limit "$LIMIT" \
        --solver-limit 300 --keep-going --max-clauses 17e6
echo "=== $(date '+%F %T') FiFO and weighted-CNF files"
python3 make-formats.py --limit 3600
echo "=== $(date '+%F %T') recognition (max-term), ${LIMIT}s per run"
python3 run-recognize.py --methods max-term --limit "$LIMIT" --jobs 6 --reserve-gb 3 \
        --work "${FP_SCRATCH:-/tmp/fourpackage}/fp-rec"
echo "=== $(date '+%F %T') done"
