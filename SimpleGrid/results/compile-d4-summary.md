## SimpleGrid problems compiled to d-DNNF with d4 (projected, no evidence): means by grid size

| Grid | Problems | Horizon | d4 time (s) | Total time (s) | CNF variables | CNF clauses | Projected variables | Circuit nodes | Circuit edges | Model count | Query with 2 obs. (s) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 3×3 | 4 | 5 | 0.04 | 1.9 | 141 | 818 | 98 | 44 | 84 | 18 | 0.001 |
| 4×4 | 4 | 7 | 0.04 | 1.9 | 400 | 2,609 | 291 | 228 | 451 | 140 | 0.006 |
| 5×5 | 4 | 8.5 | 0.09 | 2.0 | 812 | 5,621 | 604 | 1,108 | 2,210 | 1,017 | 0.075 |
| 6×6 | 4 | 10.75 | 1.37 | 7.1 | 1,557 | 11,191 | 1,175 | 21,140 | 42,296 | 24,171 | 1.31 |
| 7×7 | 4 | 12 | 6.52 | 29.6 | 2,436 | 17,936 | 1,854 | 82,748 | 165,584 | 88,126 | 5.68 |

Each row is the arithmetic mean over that grid size's problems (Problems gives
how many), rounded; the per-problem values are in compile-d4.md. Each problem's
evidence-free recognition theory — the problem at its recognition horizon, with
the goal literals as the hypotheses, as recognize.sh builds it — compiled by
marginals.sh --solver d4 --project. The projection keeps the drive actions and
the final-slice goal atoms, and FiFO first verifies that they determine every
other atom, so the projected circuit gives exact counts; any pinned observations
are unit literals over the kept actions, so one saved circuit answers every
evidence file by conditioning, without recompiling. CNF variables and clauses
are those of the ground theory d4 is given; projected variables are the ones it
keeps. d4 time is the d4 run alone; total time is the whole marginals.sh run
(reading the theory, the projection check, d4, importing and saving the circuit,
and the marginals of the unconditioned circuit). Circuit nodes and edges are
those of d4's decision-DNNF, before FiFO smooths it. Times are wall-clock, 2
compilations at a time, each limited to 30 minutes. SBCL ran with an 8 GB heap
and a 1 GB control stack, d4 with a 64 MB stack (the defaults, 1 GB, 2 MB and 8
MB, are too small for the larger circuits). The circuits were imported by FiFO
with its d4 importer rewritten to use bit-vector scopes and iterative traversal
(branch ddnnf-import-bitvector-scopes); the released importer runs out of memory
on circuits of about a million nodes. Model count (verified) is the number of
models of the compiled circuit (all literals set to 1 in the smoothed circuit),
that is, the number of truck walks the theory allows. Every circuit kept was
checked against an independent count of those walks by dynamic programming over
the grid (H-1 steps, each a drive to a neighbouring cell or a wait, from p1-1 to
a goal cell), which also agrees with sharpSAT on every problem shown; the two
counts were equal for every circuit in the table. Grids larger than 7×7 are
omitted: from 8×8 on, d4 often crashes (bus error or segmentation fault) or
returns a wrong circuit without any error, and repeated runs on the same CNF
give different circuits. Query with 2 obs. is the time to recompute every
marginal of the saved circuit conditioned on two observations — the first two
drives of a shortest plan to the problem's alphabetically first destination,
pinned to steps 1 and 2 (evidence/PROBLEM-DESTINATION-obs2.txt) — as
marginals.sh --circuit --evidence-file does: the observations are unit literals
over kept atoms, so the circuit is clamped and re-evaluated, not recompiled. It
is timed inside SBCL, the median of 5 repetitions, and excludes starting SBCL
and loading FiFO (about 1.2 s) and reading the circuit file (0.001–0.48 s). Each
answer was checked: both observed drives have probability 1, and the final-slice
goal marginals sum to 1. Most of the query time is FiFO's backward pass, which
for an AND node with k children recomputes the k-1 sibling products for each
child (k² multiplications; the largest smoothed AND node of 7×7-4 has 1,007
children), not the circuit size itself.
