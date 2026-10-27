#!/bin/bash
# make-problems.sh [N...]
#
# Generate the FourPackage problems gridNxN-K.pddl, K = 1..4 (seeds 1..4), for
# each grid size N (default 6..15): an N x N grid with no airports, two trucks
# and four packages placed at random, 40% of the roads knocked out (the grid stays
# connected), three possible destinations per package (never its own start), and
# the goal that AT LEAST ONE package reaches one of its destinations (ppgen
# --require some) -- a disjunction of 12 literals (at pkgI place), the
# recognition hypotheses.  Every goal is also a preference of weight 8 (its
# utility), drives cost 2, and the domain clara-logistics-handling.pddl charges 1
# for each load and unload.
#
# 40% rather than 50%: ppgen keeps a spanning tree of the roads, and an N x N
# grid's spanning tree is (N+1)/(2N) of its 2N(N-1) roads -- always more than
# half, 58% at 6x6 -- so no grid survives a 50% knockout.  41% is the most every
# size here allows (6x6 is the binding one).
set -euo pipefail
cd "$(dirname "$0")/.."    # the problems go in FourPackage/, beside scripts/
SIZES=("$@"); [[ ${#SIZES[@]} -gt 0 ]] || SIZES=(6 7 8 9 10 11 12 13 14 15)
for n in "${SIZES[@]}"; do
  for s in 1 2 3 4; do
    p="grid${n}x${n}-$s"
    ppgen.sh --style grid --dimensions "$n" "$n" --airports 0 --airplanes 0 --trucks 2 \
             --packages 4 --destinations 3 --require some --preferences 8 8 \
             --knockout 40 --drive-cost 2 --seed "$s" --name "$p" \
             --domain clara-logistics-handling -o "$p.pddl"
  done
done
