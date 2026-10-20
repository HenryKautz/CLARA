#!/bin/bash
# make-examples.sh [PROBLEM...] -- (re)generate the solved example files from
# the SimpleGrid theories (../scnf), for the given problems (default: one per
# grid size).  The plain PROBLEM-2020/2024.wcnf and PROBLEM.map of every problem
# come from ../../make-fifo-files.py; this script rewrites them identically and
# adds the evidence variants and the exact marginals.
# For each PROBLEM (e.g. grid5x5-1):
#   PROBLEM.evidence     the 2 pinned observations used: SimpleGrid's
#                        evidence/PROBLEM-<first destination>-obs2.txt
#   PROBLEM-2020.wcnf    PROBLEM-2024.wcnf         the weighted CNF
#   PROBLEM-ev2-2020.wcnf PROBLEM-ev2-2024.wcnf    plus the evidence as unit clauses
#   PROBLEM.map          variable number -> FiFO atom (the same in all four files)
#   PROBLEM.solution     exact marginals of every variable, without/with evidence
# Needs FiFO (FIFO_LISP, default ~/Programming/FiFO/lisp) and SBCL.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SG="$(cd "$HERE/.." && pwd)"
LISP="${FIFO_LISP:-$HOME/Programming/FiFO/lisp}"
problems=("$@")
[ ${#problems[@]} -gt 0 ] || problems=(grid3x3-1 grid4x4-1 grid5x5-1 grid6x6-1 grid7x7-1 grid8x8-1 grid9x9-3)
for p in "${problems[@]}"; do
  ev="$(ls "$SG"/evidence/"$p"-p*-obs2.txt 2>/dev/null | sort | head -1 || true)"
  if [ -z "$ev" ]; then
    echo "$p: no evidence file yet (SimpleGrid/evidence/$p-*-obs2.txt); skipped"
    continue
  fi
  cp "$ev" "$HERE/$p.evidence"
  sbcl --dynamic-space-size 8192 --noinform --non-interactive \
       --eval "(load \"$LISP/FiFO.lisp\")" --eval "(load \"$LISP/wmc.lisp\")" \
       --eval "(defparameter *job* (list \"$SG/scnf/$p.scnf\" \"$HERE/$p\" \"$HERE/$p.evidence\"))" \
       --load "$HERE/make-wcnf.lisp" 2>&1 | grep -E '^/|rror' || true
  python3 "$HERE/exact-marginals.py" "$HERE/$p" "$SG/scnf/$p.scnf" "$HERE/$p.evidence"
done
