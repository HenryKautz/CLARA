#!/bin/bash
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=24
#SBATCH --mem=240G
#SBATCH --time=2-00:00:00
#
# run-intermediates.sh [FAMILY...] -- make-intermediates.py for each family (all
# five grid families by default), one after another, as one Slurm job:
#     sbatch -J intermediates -o intermediates-run.log scripts/run-intermediates.sh
# submitted from the CLARA checkout (or set $CLARA_SCRIPTS).  Translation and
# instantiation only: $CLARA_STUBS (stand-ins that exit 99 and say "SOLVER
# CALLED") is first on PATH, so no solver can run.  Resumes: a job whose files
# all exist is skipped, so the job can simply be resubmitted.
set -uo pipefail
cd "${CLARA_SCRIPTS:-${SLURM_SUBMIT_DIR:?submit with sbatch from the CLARA checkout}/scripts}" || exit 2
: "${CLARA_STUBS:?set CLARA_STUBS to the stand-in solver directory}"
export CLARA_STUBS
export CLARA_SCRATCH="${CLARA_SCRATCH:-${TMPDIR:-/tmp}/clara-${SLURM_JOB_ID:-$$}}"
mkdir -p "$CLARA_SCRATCH"
FAMILIES=("$@")
[[ ${#FAMILIES[@]} -gt 0 ]] || FAMILIES=(SimpleGrid TwoPackage TwoPackageOneway ThreePackage FourPackage)
for F in "${FAMILIES[@]}"; do
  echo "=== $(date '+%F %T') $F on $(hostname), scratch $CLARA_SCRATCH"
  python3 make-intermediates.py --family "$F" --jobs "${INTER_JOBS:-12}" >> "../$F/intermediates.log" 2>&1
  echo "=== $(date '+%F %T') $F exit $?"
done
