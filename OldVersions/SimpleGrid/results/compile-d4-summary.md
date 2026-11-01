## SimpleGrid problems compiled to d-DNNF with d4 (projected, no evidence): means by grid size

| Grid | Problems | Horizon | d4 time (s) | Total time (s) | CNF variables | CNF clauses | Projected variables | Circuit nodes | Circuit edges | Model count | Query with 2 obs. (s) |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 8×8 | 4 | 14.75 | 104.14 | 142.5 | 4,024 | 30,205 | 3,087 | 785,660 | 1,573,583 | 5,431,088 | 0.244 |
| 9×9 | 4 | 16 | 417.69 | 499.7 | 5,616 | 42,712 | 4,328 | 2,525,681 | 5,058,475 | 13,330,206 | 0.450 |
| 3×3 | 4 | 5 | 0.04 | – | 141 | 818 | 98 | 44 | 84 | 18 | – |
| 4×4 | 4 | 7 | 0.04 | – | 400 | 2,609 | 291 | 228 | 451 | 140 | – |
| 5×5 | 4 | 8.5 | 0.09 | – | 812 | 5,621 | 604 | 1,108 | 2,210 | 1,017 | – |
| 6×6 | 4 | 10.75 | 1.36 | – | 1,557 | 11,191 | 1,175 | 21,140 | 42,296 | 24,171 | – |
| 7×7 | 4 | 12 | 6.78 | – | 2,436 | 17,936 | 1,854 | 82,748 | 165,584 | 88,126 | – |

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
those of d4's decision-DNNF, before FiFO smooths it. Runs: 1 compilation at a
time, each limited to 30 minutes (3×3–7×7) or 20 minutes (8×8–9×9). SBCL ran
with an 8 GB heap (3×3–7×7) or a 12 GB heap (8×8–9×9) and a 1 GB control stack,
d4 with a 64 MB stack (the defaults, 1 GB, 2 MB and 8 MB, are too small for the
larger circuits). The 8×8–9×9 runs were timed on the awake clock
(CLOCK_UPTIME_RAW), which stops while the computer sleeps, so a suspend neither
lengthens a time nor times a run out; their records also hold wall-clock time
and CPU time (grid9x9-1, grid9x9-2: the computer slept during the run). The
circuits were imported by FiFO's d4 importer as rewritten to use bit-vector
scopes and iterative traversal (FiFO fd0d0b9); the earlier importer ran out of
memory on circuits of about a million nodes. grid9x9-1, grid9x9-2 were imported
by its successor, which builds the circuit in one pass into packed typed arrays;
with fd0d0b9, SBCL's garbage collector crashed while importing them, after d4
had finished. Model count (verified) is the number of models of the compiled
circuit (all literals set to 1 in the smoothed circuit), that is, the number of
truck walks the theory allows. Every circuit kept was checked against an
independent count of those walks by dynamic programming over the grid (H-1
steps, each a drive to a neighbouring cell or a wait, from p1-1 to a goal cell),
which agrees with sharpSAT on every problem up to 7×7 (sharpSAT did not finish
an 8×8 problem in 2.5 hours); the two counts were equal for every circuit in the
table. Until d4v2 commit c11210d (2026-10-16), d4 had a heap overflow
(ListLit::setListLit) that from 8×8 on made it crash, or silently return a wrong
circuit, at random. The 8×8–9×9 rows are from the fixed d4; the 3×3–7×7 circuits
were compiled before the fix, which did not affect them (every one passed the
count check). The 3×3–7×7 rows give the run whose circuit passed the model-count
check (grid3x3-1: correct on 2 of 2; grid3x3-2: correct on 2 of 2; grid3x3-3:
correct on 2 of 2; grid3x3-4: correct on 2 of 2; grid4x4-1: correct on 2 of 2;
grid4x4-2: correct on 2 of 2; grid4x4-3: correct on 2 of 2; grid4x4-4: correct
on 2 of 2; grid5x5-1: correct on 2 of 2; grid5x5-2: correct on 2 of 2;
grid5x5-3: correct on 2 of 2; grid5x5-4: correct on 2 of 2; grid6x6-1: correct
on 2 of 2; grid6x6-2: correct on 2 of 2; grid6x6-3: correct on 2 of 2;
grid6x6-4: correct on 2 of 2; grid7x7-1: correct on 2 of 2; grid7x7-2: correct
on 2 of 2; grid7x7-3: correct on 2 of 2; grid7x7-4: correct on 2 of 2 runs); its
d4 time is that run's alone, not counting failed runs. Their total time is not
shown: it was measured with FiFO's earlier, quadratic evaluator (and partly two
compilations at a time); and no queries were timed on them. Query with 2 obs. is
the time to recompute every marginal of the saved circuit conditioned on two
observations — the first two drives of a shortest plan to the problem's
alphabetically first destination, pinned to steps 1 and 2 (evidence/PROBLEM-
DESTINATION-obs2.txt) — as marginals.sh --circuit --evidence-file does: the
observations are unit literals over kept atoms, so the circuit is clamped and
re-evaluated, not recompiled. It is timed inside SBCL, the median of 5
repetitions, and excludes starting SBCL and loading FiFO (about 1.2 s) and
reading the circuit file (0.001–8.80 s). Each answer was checked: both observed
drives have probability 1, and the final-slice goal marginals sum to 1. FiFO
evaluates the circuit in two linear passes; its backward pass through an AND
node of k children uses prefix and suffix products (an earlier version
recomputed each child's k-1 sibling products, k² multiplications, and took up to
7 s on 7×7 — smoothed AND nodes here have up to 1,007 children). FiFO's circuit-
size cap (*ddnnf-node-limit*, 2,000,000 nodes by default) was raised to
50,000,000 for 8×8–9×9, since a smoothed import of a large d4 circuit exceeds
the default. No 10×10 problem compiled within the limit, so larger grids were
not tried.
