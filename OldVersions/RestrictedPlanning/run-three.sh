#!/bin/bash
#SBATCH --job-name=rp-three
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=96G
#SBATCH --time=2-00:00:00
#
# run-three.sh [SIZE...] -- compare.py on the ThreePackage goals planned so far
# (results/plans.jsonl of ../ThreePackage), at slack 0 and 4, 16 runs at a time.
# Resubmit once more goals are planned: finished runs are skipped.
#     sbatch --export=ALL,RP_DIR=$PWD/RestrictedPlanning -o RestrictedPlanning/three.log \
#            RestrictedPlanning/run-three.sh 5 6 7
set -uo pipefail
cd "${RP_DIR:?set RP_DIR to the RestrictedPlanning directory}" || exit 2
export RP_SCRATCH="${TMPDIR:-/tmp}/restricted-planning-$SLURM_JOB_ID"
echo "=== $(date '+%F %T') on $(hostname)"
[ $# -gt 0 ] || set -- 5 6 7
python3 compare.py ThreePackage --sizes "$@" --jobs 16
echo "=== $(date '+%F %T') done"
