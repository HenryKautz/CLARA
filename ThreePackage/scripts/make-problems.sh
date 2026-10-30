#!/bin/bash
# make-problems.sh [N...]
#
# Generate the ThreePackage problems gridNxN-K.pddl, K = 1..4 (seeds 1..4), for
# each grid size N (default 5 6 7): an N x N grid with no airports, ONE truck and
# THREE packages placed at random, 20% of the roads knocked out (the grid stays
# connected), two possible destinations per package (never its own start), and
# the goal that EVERY package reaches one of its destinations (ppgen --require
# all): a conjunction of three binary disjunctions
#     (and (or (at pkg1 a) (at pkg1 b)) (or (at pkg2 c) (at pkg2 d)) (or ...))
# No preferences.  Drives cost 2, and the domain clara-logistics-handling.pddl
# charges 1 for each load and unload.
#
# The recognition hypotheses are the goal's 2^3 = 8 combinations -- one
# destination per package; plan-goals.py writes them out.
set -euo pipefail
cd "$(dirname "$0")/.."    # the problems go in ThreePackage/, beside scripts/
SIZES=("$@"); [[ ${#SIZES[@]} -gt 0 ]] || SIZES=(5 6 7)
for n in "${SIZES[@]}"; do
  for s in 1 2 3 4; do
    p="grid${n}x${n}-$s"
    ppgen.sh --style grid --dimensions "$n" "$n" --airports 0 --airplanes 0 --trucks 1 \
             --packages 3 --destinations 2 --require all --preferences none \
             --knockout 20 --drive-cost 2 --seed "$s" --name "$p" \
             --domain clara-logistics-handling -o "$p.pddl"
  done
done
