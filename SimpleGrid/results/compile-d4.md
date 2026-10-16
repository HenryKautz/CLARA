## SimpleGrid problems compiled to d-DNNF with d4 (projected, no evidence)

| Instance | Horizon | Circuit file | d4 time (s) | Total time (s) | CNF variables | CNF clauses | Projected variables | Circuit nodes | Circuit edges | Model count (verified) | Query with 2 obs. (s) |
|:--|--:|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| grid3x3-1 | 5 | grid3x3-1.dnnf | 0.04 | 2.1 | 141 | 818 | 98 | 43 | 81 | 18 | 0.001 |
| grid3x3-2 | 5 | grid3x3-2.dnnf | 0.03 | 2.0 | 141 | 818 | 98 | 45 | 85 | 18 | 0.001 |
| grid3x3-3 | 5 | grid3x3-3.dnnf | 0.04 | 1.9 | 141 | 818 | 98 | 45 | 85 | 18 | 0.001 |
| grid3x3-4 | 5 | grid3x3-4.dnnf | 0.03 | 1.9 | 141 | 818 | 98 | 45 | 85 | 18 | 0.001 |
| grid4x4-1 | 7 | grid4x4-1.dnnf | 0.04 | 2.1 | 400 | 2,609 | 291 | 228 | 451 | 140 | 0.003 |
| grid4x4-2 | 7 | grid4x4-2.dnnf | 0.04 | 2.0 | 400 | 2,609 | 291 | 228 | 451 | 140 | 0.003 |
| grid4x4-3 | 7 | grid4x4-3.dnnf | 0.04 | 1.9 | 400 | 2,609 | 291 | 228 | 451 | 140 | 0.003 |
| grid4x4-4 | 7 | grid4x4-4.dnnf | 0.04 | 1.8 | 400 | 2,609 | 291 | 228 | 451 | 140 | 0.003 |
| grid5x5-1 | 9 | grid5x5-1.dnnf | 0.14 | 2.2 | 865 | 5,994 | 644 | 2,606 | 5,208 | 2,100 | 0.007 |
| grid5x5-2 | 8 | grid5x5-2.dnnf | 0.06 | 2.0 | 760 | 5,248 | 564 | 393 | 781 | 315 | 0.006 |
| grid5x5-3 | 9 | grid5x5-3.dnnf | 0.10 | 2.0 | 865 | 5,994 | 644 | 1,032 | 2,059 | 1,372 | 0.007 |
| grid5x5-4 | 8 | grid5x5-4.dnnf | 0.05 | 2.0 | 760 | 5,248 | 564 | 399 | 793 | 280 | 0.006 |
| grid6x6-1 | 11 | grid6x6-1.dnnf | 1.52 | 4.5 | 1,596 | 11,477 | 1,205 | 24,754 | 49,539 | 36,510 | 0.018 |
| grid6x6-2 | 11 | grid6x6-2.dnnf | 2.00 | 4.8 | 1,596 | 11,477 | 1,205 | 29,556 | 59,122 | 28,302 | 0.019 |
| grid6x6-3 | 10 | grid6x6-3.dnnf | 0.29 | 2.3 | 1,440 | 10,333 | 1,085 | 3,860 | 7,717 | 3,570 | 0.013 |
| grid6x6-4 | 11 | grid6x6-4.dnnf | 1.64 | 4.3 | 1,596 | 11,477 | 1,205 | 26,389 | 52,808 | 28,302 | 0.019 |
| grid7x7-1 | 12 | grid7x7-1.dnnf | 6.78 | 11.7 | 2,436 | 17,936 | 1,854 | 73,184 | 146,525 | 96,558 | 0.035 |
| grid7x7-2 | 12 | grid7x7-2.dnnf | 4.49 | 8.5 | 2,436 | 17,936 | 1,854 | 57,227 | 114,500 | 65,472 | 0.033 |
| grid7x7-3 | 12 | grid7x7-3.dnnf | 6.62 | 11.5 | 2,436 | 17,936 | 1,854 | 91,315 | 182,661 | 86,856 | 0.035 |
| grid7x7-4 | 12 | grid7x7-4.dnnf | 9.21 | 14.9 | 2,436 | 17,936 | 1,854 | 109,265 | 218,648 | 103,620 | 0.039 |

Each problem's evidence-free recognition theory — the problem at its recognition
horizon, with the goal literals as the hypotheses, as recognize.sh builds it —
compiled by marginals.sh --solver d4 --project. The projection keeps the drive
actions and the final-slice goal atoms, and FiFO first verifies that they
determine every other atom, so the projected circuit gives exact counts; any
pinned observations are unit literals over the kept actions, so one saved
circuit answers every evidence file by conditioning, without recompiling. CNF
variables and clauses are those of the ground theory d4 is given; projected
variables are the ones it keeps. d4 time is the d4 run alone; total time is the
whole marginals.sh run (reading the theory, the projection check, d4, importing
and saving the circuit, and the marginals of the unconditioned circuit). Circuit
nodes and edges are those of d4's decision-DNNF, before FiFO smooths it. Times
are wall-clock, 1 compilation at a time, each limited to 30 minutes. SBCL ran
with an 8 GB heap and a 1 GB control stack, d4 with a 64 MB stack (the defaults,
1 GB, 2 MB and 8 MB, are too small for the larger circuits). The circuits were
imported by FiFO with its d4 importer rewritten to use bit-vector scopes and
iterative traversal (branch ddnnf-import-bitvector-scopes); the released
importer runs out of memory on circuits of about a million nodes. Model count
(verified) is the number of models of the compiled circuit (all literals set to
1 in the smoothed circuit), that is, the number of truck walks the theory
allows. Every circuit kept was checked against an independent count of those
walks by dynamic programming over the grid (H-1 steps, each a drive to a
neighbouring cell or a wait, from p1-1 to a goal cell), which also agrees with
sharpSAT on every problem shown; the two counts were equal for every circuit in
the table. Grids larger than 7×7 are omitted: from 8×8 on, d4 often crashes (bus
error or segmentation fault) or returns a wrong circuit without any error, and
repeated runs on the same CNF give different circuits. Query with 2 obs. is the
time to recompute every marginal of the saved circuit conditioned on two
observations — the first two drives of a shortest plan to the problem's
alphabetically first destination, pinned to steps 1 and 2 (evidence/PROBLEM-
DESTINATION-obs2.txt) — as marginals.sh --circuit --evidence-file does: the
observations are unit literals over kept atoms, so the circuit is clamped and
re-evaluated, not recompiled. It is timed inside SBCL, the median of 5
repetitions, and excludes starting SBCL and loading FiFO (about 1.2 s) and
reading the circuit file (0.001–0.45 s). Each answer was checked: both observed
drives have probability 1, and the final-slice goal marginals sum to 1. FiFO
evaluates the circuit in two linear passes; its backward pass through an AND
node of k children uses prefix and suffix products (an earlier version
recomputed each child's k-1 sibling products, k² multiplications, and took up to
7 s on 7×7 — smoothed AND nodes here have up to 1,007 children).
