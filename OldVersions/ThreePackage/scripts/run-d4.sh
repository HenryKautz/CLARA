#!/bin/bash
#SBATCH --job-name=tp-d4
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=12
#SBATCH --mem=200G
#SBATCH --time=2-00:00:00
#
# run-d4.sh -- compile-d4.py alone, resuming from results/compile-d4.jsonl:
#     sbatch --export=ALL,TP_SCRIPTS=$PWD/ThreePackage/scripts -o ThreePackage/d4.log \
#            ThreePackage/scripts/run-d4.sh
# It replaced run-all.sh's d4 stage after grid5x5-3's circuit (1.87M nodes from
# d4) overflowed FiFO's default 2,000,000-node import cap: --node-limit raises the
# cap to 20M (with a 32 GB SBCL heap), and each circuit's count check gets 30
# minutes instead of 2.  Still 1 hour per compilation, 4 at a time, stopping
# after the first size where one times out.
set -uo pipefail
cd "${TP_SCRIPTS:?set TP_SCRIPTS to ThreePackage/scripts}" || exit 2
export TP_SCRATCH="${TMPDIR:-/tmp}/threepackage-$SLURM_JOB_ID"
echo "=== $(date '+%F %T') d4 on $(hostname)"
python3 compile-d4.py --limit 3600 --jobs 4 --sbcl-heap-mb 32768 --min-free-gb 16 \
    --node-limit 20000000 --verify-limit 1800 >> ../compile-d4.log 2>&1
echo "=== $(date '+%F %T') d4 exit $?"
python3 summarize.py > ../tables.md
echo "=== $(date '+%F %T') done"
