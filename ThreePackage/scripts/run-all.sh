#!/bin/bash
#SBATCH --job-name=threepackage
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=24
#SBATCH --mem=200G
#SBATCH --time=2-00:00:00
#
# run-all.sh -- the whole ThreePackage pipeline, as one Slurm job:
#     sbatch -o ThreePackage/run-all.log ThreePackage/scripts/run-all.sh
# from the CLARA checkout: sbatch runs a spooled copy of this file, so $0 does
# not lead back here, and the scripts are found from the submit directory --
# or from $TP_SCRIPTS, when submitted from elsewhere:
#     sbatch --export=ALL,TP_SCRIPTS=$PWD/ThreePackage/scripts -o ... run-all.sh
#
#   1. plan-goals.py: plan the 8 goal combinations of every problem (WMaxCDCL,
#      exact), write the evidence (first 4 and 8 actions) and the recognition
#      problems with their recognition horizons.  16 at a time, 3 hours per
#      planner.sh run (it tries every horizon up from its reachability bound;
#      a 5x5 goal at horizon 21 already takes 8 minutes), 1 hour per MaxSAT
#      solve.
#   2. then, side by side:
#      - run-recognize.py: max-term and sharpsat-td on every pinned evidence
#        file, 10 minutes per run, 14 at a time; a method stops (and its other
#        runs at that size are killed) at the first size where it times out;
#      - compile-d4.py: each problem's evidence-free theory compiled by d4,
#        1 hour per problem, 4 at a time; stops after the first size where a
#        compilation times out.
#   3. summarize.py > tables.md
#
# Each stage resumes from results/*.jsonl, so the job can simply be resubmitted.
set -uo pipefail
cd "${TP_SCRIPTS:-${SLURM_SUBMIT_DIR:?submit with sbatch from the CLARA checkout}/ThreePackage/scripts}" || exit 2
export TP_SCRATCH="${TMPDIR:-/tmp}/threepackage-$SLURM_JOB_ID"
mkdir -p "$TP_SCRATCH"
echo "=== $(date '+%F %T') plan-goals on $(hostname), scratch $TP_SCRATCH"
python3 plan-goals.py --jobs 16 --limit 10800 --solver-limit 3600
echo "=== $(date '+%F %T') recognition and d4"
python3 run-recognize.py --methods max-term,sharpsat-td --limit 600 --jobs 14 \
    > ../recognize.log 2>&1 &
rec=$!
python3 compile-d4.py --limit 3600 --jobs 4 --sbcl-heap-mb 16384 --min-free-gb 8 \
    > ../compile-d4.log 2>&1 &
d4=$!
wait "$rec"; echo "=== $(date '+%F %T') recognition exit $?"
wait "$d4";  echo "=== $(date '+%F %T') d4 exit $?"
python3 summarize.py > ../tables.md
echo "=== $(date '+%F %T') done"
