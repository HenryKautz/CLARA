#!/bin/bash
# resume-mutex.sh -- finish FourPackage 12x12-15x15 under FiFO's MUTEX encoding
# (see ../HANDOFF.md).  Every stage resumes from results/*.jsonl, so rerunning
# this script after an interruption repeats nothing already recorded ok.
#
# Needs the installed FiFO (make install) to be the MUTEX one: fpcommon.encoding()
# must say "mutex", or the 12x12+ records would be mixed with the pairwise ones.
#
#   WORKERS  goal runs at once (default 3).  Each SBCL needs ~2.5 GB plus ~1 GB per
#            million clauses; a 15x15 goal is ~2-4M clauses, so allow ~6 GB a run.
#   BUDGET   millions of predicted clauses planned at once (default 2 x WORKERS).
#   LIMIT    wall-clock seconds per goal (default 3600); a goal that timed out at a
#            smaller limit is rerun.
set -u
cd "$(dirname "$0")"
WORKERS=${WORKERS:-3}
BUDGET=${BUDGET:-$((2 * WORKERS))}
LIMIT=${LIMIT:-3600}
KEEP=""
command -v caffeinate >/dev/null && KEEP="caffeinate -dims"     # macOS only

enc=$(python3 -c 'import fpcommon as F; print(F.encoding())')
if [ "$enc" != mutex ]; then
    echo "the FiFO in use writes '$enc' mutexes; make install the MUTEX FiFO first" >&2
    exit 1
fi

echo "=== $(date '+%F %T') general grid15x15-3 with EvalMaxSAT_bin (wmaxcdcl timed out)"
$KEEP python3 run-plans.py --stage general --solver EvalMaxSAT_bin --limit "$LIMIT" --sizes 15 \
      --redo-other-encoding --keep-going
echo "=== $(date '+%F %T') clamped goals 13x13-15x15: $WORKERS at once, budget ${BUDGET}M, ${LIMIT}s"
$KEEP python3 run-plans.py --stage goals --solver tt-open-wbo-inc-Glucose4_1 --limit "$LIMIT" \
      --solver-limit 300 --keep-going --redo-other-encoding \
      --workers "$WORKERS" --budget "$BUDGET" --sizes 13 14 15
echo "=== $(date '+%F %T') FiFO and weighted-CNF files 12x12-15x15"
$KEEP python3 make-formats.py --sizes 12 13 14 15 --limit "$LIMIT"
echo "=== $(date '+%F %T') evidence for every goal planned ok"
python3 run-plans.py --stage evidence
echo "=== $(date '+%F %T') done"
