# Weighted CNF: SimpleGrid plan recognition

The weighted CNF of **every** SimpleGrid problem (`../gridNxN-K.pddl`, 32 of
them), as weighted model counting problems: the evidence-free recognition
theory `../scnf/P.scnf` that the experiments used, written by FiFO's own writer
(`../../make-fifo-files.py`). Seven of them, one per grid size from 3×3 to 9×9,
also come **solved**: with a version conditioned on two observations, and the
exact marginal of every variable with and without them, for testing weighted
samplers and counters. (These seven were the top-level `WcnfExamples/`
directory until 2026-10-20.)

The FiFO source of each theory is `../wff/P.wff`.

## The problems

A truck starts at the corner cell p1-1 of an N×N grid of places and moves for
H−1 steps (H = the problem's horizon); at each step it drives to a neighbouring
cell or waits.  It must end, at slice H, on one of the problem's possible goal
cells.  Each drive costs 1, so a plan with d drives has weight w^d, w = e^−1.
The marginals are the plan-recognition quantities: the probability that the
truck is at each place at each time, takes each drive, and ends at each goal.

| Problem | Grid | Horizon H | Goals | Variables | Clauses |
|---|---|---|---|---|---|
The seven solved ones:

| Problem | Grid | Horizon H | Goals | Variables | Clauses |
|---|---|---|---|---|---|
| grid3x3-1 | 3×3 | 5 | 2 | 141 | 818 |
| grid4x4-1 | 4×4 | 7 | 3 | 400 | 2,609 |
| grid5x5-1 | 5×5 | 9 | 4 | 865 | 5,994 |
| grid6x6-1 | 6×6 | 11 | 5 | 1,596 | 11,477 |
| grid7x7-1 | 7×7 | 12 | 6 | 2,436 | 17,936 |
| grid8x8-1 | 8×8 | 14 | 7 | 3,808 | 28,561 |
| grid9x9-3 | 9×9 | 16 | 8 | 5,616 | 42,712 |

The other problems are the same model on the same grids (and 10×10, up to
7,920 variables and 60,893 clauses) with other goal sets, so other horizons.

## Files

For **every** problem P:

| File | What |
|---|---|
| `P-2020.wcnf` | the weighted CNF, MCC 2020 format (ADDMC's) |
| `P-2024.wcnf` | the same, MCC 2024 format (Model Counting Competition 2021 on; SharpSAT-TD's) |
| `P.map` | variable number → atom, e.g. `89 (OCCURS (DRIVE TRUCK1 P1-1 P2-1) 1)` |

For the seven solved problems, also:

| File | What |
|---|---|
| `P-ev2-2020.wcnf`, `P-ev2-2024.wcnf` | the same plus 2 pieces of evidence, as 2 unit clauses |
| `P.evidence` | that evidence: the first two drives of a shortest plan to one goal, pinned to steps 1 and 2 |
| `P.solution` | the exact marginal of every variable, without and with the evidence |

Any other observation in `../evidence/` (`P-<goal>-obsN.txt`, pinned drives)
conditions a problem the same way: each of its `(occurs ...)` literals is one
atom of `P.map`, to be added as a unit clause.

The variable numbering is the same in all four `.wcnf` files of a problem.  The
atoms are `(HOLDS (AT TRUCK1 Pr-c) t)` — the truck is at row r, column c at
slice t (1..H) — and `(OCCURS (DRIVE TRUCK1 Pa Pb) t)` — it drives from a to b
between slices t and t+1 (1..H−1).

### The two formats

They are not interchangeable:

- **MCC 2020** (`p wcnf V C`): one `w <literal> <weight>` line per charged
  literal — here each drive variable, `w v 0.36787944117144233` — and every
  literal not listed has weight 1.
- **MCC 2024** (`p cnf V C`): weights are comment lines
  `c p weight <literal> <weight> 0`, so the file is also a plain DIMACS CNF.  A
  reader that ignores comments therefore counts it UNWEIGHTED.  Both polarities
  of every variable are listed (1 for a drive's false literal and for every
  position literal), because readers of this format infer a missing polarity
  differently (SharpSAT-TD takes 1 − w).

In both, a model's weight is the product of its literals' weights, so the
weighted count Z is the sum over plans of e^−(number of drives).

## The solution files

```
c Z0 ...   (log Z0 ...)      the weighted count without evidence
c Z2 ...   (log Z2 ...)      with the 2 pieces of evidence
c var P0 P2 atom
1 0 0 (HOLDS (AT TRUCK1 P3-3) 1)
...
```

P0 is the marginal P(variable = true) in `P-2020.wcnf` / `P-2024.wcnf`, P2 in the
`-ev2` files.  Values are given to 15 significant digits.

**How they were computed.** The theory's models correspond one to one with the
truck's walks (the drives determine every other variable; FiFO checks this, and
every model count we compiled equals the number of walks), so `exact-marginals.py`
runs a forward/backward dynamic program over the walks, with the drive weight
read from the `.wcnf` itself and the evidence restricting the pinned steps.

**How they were checked.** For 3×3 to 8×8 the weighted counts Z0 and Z2 agree
with those of FiFO's d4-compiled circuits for the same problem and evidence; the
marginals of the drive and final-goal variables agree with the circuits' (to the
6 decimals FiFO prints).  For grid9x9-3 the circuit was queried directly, at
full precision: Z0 and Z2 agree to a relative 8e−16, and the marginals of all
4,328 atoms the circuit keeps (the 4,320 drives and the 8 final-slice goal
atoms) to 3e−14, without and with the evidence.  For 3×3 and 4×4 every variable's marginal agrees
with FiFO + SharpSAT-TD's exact marginals to 3e−15.  For 5×5 and 6×6 the goal
atoms also agree with the SimpleGrid sweep's SharpSAT-TD recognition runs on the
same evidence (to the 4 decimals recorded).  For 5×5 and up, the marginals of
the position atoms before the final slice have been checked by no general
method; they are determined by the drives, whose marginals were checked.

`timing.md` summarizes the run times of the specialized method, SharpSAT-TD and
MC-SAT on these problems so far, and what each computed.

## Regenerating

`../../make-fifo-files.py` writes `P-2020.wcnf`, `P-2024.wcnf` and `P.map` for
every problem, with `../wff/P.wff` and `../scnf/P.scnf` (see the top-level
README).  `make-examples.sh [PROBLEM...]` rebuilds the solved examples from the
theories (`../scnf/P.scnf`) with FiFO's own weighted-CNF writer
(`make-wcnf.lisp`) and `exact-marginals.py`; it rewrites the plain files
identically.  Both need FiFO and SBCL.
