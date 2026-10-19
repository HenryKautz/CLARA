#!/bin/bash
# run-sweep.sh -- the TwoPackage experiments, 3x3-7x7: d4 compilation with
# evidence queries, then recognition (marginal inference) with max-term,
# sharpsat-td and mc-sat.  Each method gets a first pass at 5 minutes per run
# and a second at 20 minutes, and stops at the first size where it times out
# (see compile-d4.py and run-recognize.py), so the second pass takes each
# method on from the size where its first pass stopped.
#
# Run it detached and kept awake, from TwoPackage/:
#   nohup caffeinate -i bash run-sweep.sh > sweep.log 2>&1 &
# Every stage appends one JSON record per run the moment it ends and skips runs
# already recorded, so after an interruption the script can be started again.
#
# Instances (make-instances.sh 3 .. 7) must exist first; check-plans.py must
# pass on them.
set -uo pipefail
cd "$(dirname "$0")" || exit 2
stamp() { echo "=== $(date '+%Y-%m-%d %H:%M:%S') $*"; }
METHODS=max-term,sharpsat-td,mc-sat

python3 check-plans.py || { stamp "check-plans.py failed; not running"; exit 1; }

for LIMIT in 300 1200; do
  stamp "compile, ${LIMIT}s per problem"
  python3 compile-d4.py --limit "$LIMIT" --jobs 2 --attempts 3 --sbcl-heap-mb 12288 \
          --node-limit 50000000 || stamp "compile-d4.py exited $?"
  stamp "evidence queries on new circuits"
  # only circuits with no query record yet
  new=()
  for c in circuits/*.dnnf; do
    [[ -e "$c" ]] || continue
    n="$(basename "$c" .dnnf)"
    grep -q "\"instance\": \"$n\"" results/query-evidence.jsonl 2>/dev/null || new+=("$n")
  done
  if [[ ${#new[@]} -gt 0 ]]; then
    python3 query-evidence.py "${new[@]}" || stamp "query-evidence.py exited $?"
  fi
  stamp "recognition, ${LIMIT}s per run"
  python3 run-recognize.py --methods "$METHODS" --limit "$LIMIT" --jobs 8 \
          --work /tmp/tp-rec || stamp "run-recognize.py exited $?"
done
stamp "done"
