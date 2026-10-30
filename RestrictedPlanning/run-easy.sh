#!/bin/bash
#SBATCH --job-name=rp-easy
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=1-00:00:00
#
# run-easy.sh -- compare.py on the easy benchmarks: SimpleGrid 3x3..7x7 and all
# of TwoPackage, at slack 0 and 4, 16 runs at a time.
#     sbatch --export=ALL,RP_DIR=$PWD/RestrictedPlanning -o RestrictedPlanning/easy.log \
#            RestrictedPlanning/run-easy.sh
set -uo pipefail
cd "${RP_DIR:?set RP_DIR to the RestrictedPlanning directory}" || exit 2
export RP_SCRATCH="${TMPDIR:-/tmp}/restricted-planning-$SLURM_JOB_ID"
echo "=== $(date '+%F %T') on $(hostname)"
python3 compare.py SimpleGrid --sizes 3 4 5 6 7 --jobs 16
python3 compare.py TwoPackage --jobs 16
echo "=== $(date '+%F %T') done"
