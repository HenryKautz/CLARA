#!/bin/bash
#SBATCH --job-name=tp-d4fix
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=6
#SBATCH --mem=96G
#SBATCH --time=12:00:00
#
# run-d4-fixed.sh -- grid5x5-3 and grid5x5-4 again, with the FiFO checkout whose
# d4 importer drops the implied literals d4 leaks onto its arcs in a projected
# compile (discussion.md, "d4's projected dump leaks implied literals"), instead
# of refusing the circuit.  Each circuit's count is checked for up to an hour.
#     sbatch --export=ALL,TP_SCRIPTS=$PWD/ThreePackage/scripts,FIFO_LISP=$HOME/Programming/FiFO/lisp \
#            -o ThreePackage/d4-fixed.log ThreePackage/scripts/run-d4-fixed.sh
set -uo pipefail
cd "${TP_SCRIPTS:?set TP_SCRIPTS to ThreePackage/scripts}" || exit 2
: "${FIFO_LISP:?set FIFO_LISP to the lisp directory of the FiFO checkout}"
export TP_SCRATCH="${TMPDIR:-/tmp}/threepackage-$SLURM_JOB_ID"
echo "=== $(date '+%F %T') d4 (FIFO_LISP=$FIFO_LISP) on $(hostname)"
python3 compile-d4.py --sizes 5x5 --limit 3600 --jobs 2 --attempts 6 --sbcl-heap-mb 32768 \
    --min-free-gb 16 --node-limit 20000000 --verify-limit 3600 >> ../compile-d4.log 2>&1
echo "=== $(date '+%F %T') d4 exit $?"
