#!/bin/bash
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=24
#SBATCH --mem=240G
#SBATCH --time=4-00:00:00
#
# run-family.sh FAMILY -- one benchmark family's whole pipeline, as one Slurm job:
#     sbatch -J FAMILY -o FAMILY/run.log scripts/run-family.sh FAMILY
# submitted from the CLARA checkout (sbatch runs a spooled copy of this file, so
# the scripts are found from the submit directory, or from $CLARA_SCRIPTS).
#
# The three stages run side by side; each resumes from results/*.jsonl, so the
# job can simply be resubmitted:
#   plan-goals.py     tt-open-wbo-inc and EvalMaxSAT plans for every goal,
#                     evidence, recognition problems (12 runs at once)
#   run-recognize.py  max-term, sharpsat-td, mc-sat on every evidence file,
#                     30 minutes per run (8 at once), each size once planned
#   compile-d4.py     d4 circuits, 2 hours each (2 at once), each size once planned
# then summarize.py writes FAMILY/tables.md.
set -uo pipefail
FAMILY="${1:?usage: run-family.sh FAMILY}"
cd "${CLARA_SCRIPTS:-${SLURM_SUBMIT_DIR:?submit with sbatch from the CLARA checkout}/scripts}" || exit 2
export CLARA_SCRATCH="${TMPDIR:-/tmp}/clara-${SLURM_JOB_ID:-$$}"
mkdir -p "$CLARA_SCRATCH"
D="../$FAMILY"
echo "=== $(date '+%F %T') $FAMILY on $(hostname), scratch $CLARA_SCRATCH"
python3 plan-goals.py --family "$FAMILY" --jobs "${PLAN_JOBS:-12}" > "$D/plan.log" 2>&1 &
plan=$!
python3 run-recognize.py --family "$FAMILY" --jobs "${REC_JOBS:-8}" > "$D/recognize.log" 2>&1 &
rec=$!
python3 compile-d4.py --family "$FAMILY" --jobs "${D4_JOBS:-2}" > "$D/compile-d4.log" 2>&1 &
d4=$!
wait "$plan"; echo "=== $(date '+%F %T') plan-goals exit $?"
wait "$rec";  echo "=== $(date '+%F %T') run-recognize exit $?"
wait "$d4";   echo "=== $(date '+%F %T') compile-d4 exit $?"
python3 summarize.py --family "$FAMILY" > "$D/tables.md"
echo "=== $(date '+%F %T') done"
rm -rf "$CLARA_SCRATCH"
