#!/bin/bash
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=24
#SBATCH --mem=240G
#SBATCH --time=4-00:00:00
#
# run-originals.sh FAMILY -- plan FAMILY's original problems (plan-originals.py)
# as one Slurm job, with run-family.sh's conventions:
#     sbatch -J orig-FAMILY -o FAMILY/originals-run.log scripts/run-originals.sh FAMILY
# submitted from the CLARA checkout (or set $CLARA_SCRIPTS).  Resumes from
# FAMILY/results/originals.jsonl, so the job can simply be resubmitted.
set -uo pipefail
FAMILY="${1:?usage: run-originals.sh FAMILY}"
cd "${CLARA_SCRIPTS:-${SLURM_SUBMIT_DIR:?submit with sbatch from the CLARA checkout}/scripts}" || exit 2
export CLARA_SCRATCH="${TMPDIR:-/tmp}/clara-${SLURM_JOB_ID:-$$}"
mkdir -p "$CLARA_SCRATCH"
D="../$FAMILY"
echo "=== $(date '+%F %T') $FAMILY originals on $(hostname), scratch $CLARA_SCRATCH"
python3 plan-originals.py --family "$FAMILY" --jobs "${PLAN_JOBS:-12}" >> "$D/originals.log" 2>&1
echo "=== $(date '+%F %T') plan-originals exit $?"
python3 summarize.py --family "$FAMILY" > "$D/tables.md"
rm -rf "$CLARA_SCRATCH"
