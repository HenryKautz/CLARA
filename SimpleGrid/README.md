# SimpleGrid

One truck heading for one of several destinations; regenerated 2026-10-31 (the
version before, with its results, is
[OldVersions/SimpleGrid](https://github.com/HenryKautz/CLARA/tree/ac6aa16/OldVersions/SimpleGrid), deleted from the tree in 7731002).  How the
problems were made and solved is in the [top-level README](../README.md) and
[scripts/README.md](../scripts/README.md).

## Problems

`gridNxN-K.pddl`, N = 3..10, K = 1..4 (the seed): an N×N grid of places `pR-C`
with two-way roads between neighbours and no airports, airplanes or packages.
One truck starts at the corner `p1-1`; the goal is that it reaches any one of
N−1 destinations (2 at 3×3), all at least N+1 road steps from `p1-1` (3 at
3×3): `(or (at truck1 a) (at truck1 b) …)`.  Drives cost 1 (domain
`clara-logistics.pddl`; with no packages, the new handling cost never applies,
so these problems plan exactly as before).  No preferences.

The **hypotheses** are the destinations, named `at-truck1-<place>` by
`recognize.sh`; chance is 1/(N−1).

## Layout

```
gridNxN-K.pddl              problems; clara-logistics.pddl, their domain
gridNxN-K-tt.answer         the problem's own plan (its goal, any one hypothesis) by
                            tt-open-wbo-inc, cheapest over horizons H0..H0+4
gridNxN-K-eval.answer       EvalMaxSAT's, where it proved the optimum at all five
goals/
  <goal>.pddl               the problem with one hypothesis as its hard goal
  <goal>-tt.answer          tt-open-wbo-inc's plan at the goal's shortest horizon
  <goal>-eval.answer        EvalMaxSAT's, when it proved its optimum within 30 minutes
  <goal>.answer             the plan the evidence was cut from (EvalMaxSAT's, else tt's)
evidence/
  <problem>-none.txt        no observations: (and)
  <goal>-obs25.txt          the first 25% of the plan's actions (rounded up), pinned
  <goal>-obs100.txt         all of the plan's actions, pinned
recognition/<problem>.pddl  the goal as one disjunction of the hypotheses; its header
                            lists them, their shortest horizons, and the
                            RECOGNITION HORIZON (the largest), which every run uses
scnf/<problem>.scnf         the evidence-free recognition theory (compile-d4.py)
circuits/<problem>.dnnf     its d4 circuit, where d4 succeeded; one over 100 MB is
                            committed as .part-* pieces: cat <problem>.dnnf.part-* > <problem>.dnnf
results/                    plans.jsonl, originals.jsonl, runs.jsonl, compile-d4.jsonl:
                            a record per run
tables.md                   scripts/summarize.py's tables
*.log                       the stages' logs
```

`<goal>` is the problem name followed by the hypothesis's object and place,
e.g. `grid4x4-1-truck1-p3-4` (the old version named it `grid4x4-1-p3-4`).  The
true hypothesis of `<goal>-obs*.txt` is that goal's.

## Results

Full tables: [tables.md](tables.md).  Every limit below is wall-clock time
for the whole run; when a run of some kind failed by timeout or memory at a
size, that kind of run was stopped there for that size and every larger one
("killed" in the tables).  Accuracy scores a run 1/k when the true hypothesis
ties with k − 1 others for the highest posterior.

**Planning** (30 minutes per solver run).  Every goal at every size was
planned by tt-open-wbo-inc in seconds, and EvalMaxSAT proved every plan
optimal; tt's plans were all already optimal, so the evidence comes from
EvalMaxSAT's plans throughout.

**Original problems** (2026-11-02, `scripts/plan-originals.py`, no evidence).
Each `gridNxN-K.pddl` was also planned as it is, its goal the disjunction (any
one destination).  tt-open-wbo-inc found the shortest feasible horizon H0
with kissat (`--maxslices 200`); then tt-open-wbo-inc, and EvalMaxSAT at
`--numslices H0`, minimised cost at each of H0..H0+4 (`--longer 4`) and kept
the cheapest plan.  30 minutes per solver call, 24 hours per run; an
EvalMaxSAT plan counts only when it proved the optimum at all five horizons.
Both solvers planned all 32 problems and EvalMaxSAT proved every optimum (at
most 3 minutes per run at 10×10); H0 runs from 4 (3×3) to 12 (10×10), and the
kept plan's horizon was H0 every time: no longer horizon was cheaper.  tt's
plans were all optimal.  Checked against the goal plans (any goal plan also
solves the original): H0 equals the smallest shortest horizon among each
problem's goals, and every optimum equals the cheapest goal plan within
H0..H0+4 — all 32 problems pass.  Plans: `gridNxN-K-tt.answer`,
`gridNxN-K-eval.answer`; records: `results/originals.jsonl`.

**Recognition** (30 minutes per run).

- **max-term** solved every run at every size (mean 6 s at 3×3, 700–970 s at
  10×10).
- **SharpSAT-TD** solved everything through 6×6.  At 7×7 it timed out on one
  run with 25% evidence and stopped (5 runs with full evidence were killed).
- **MC-SAT** failed to mix on many runs from 5×5 on (status `nomix`: the
  chain froze, so the estimate is unusable; this is not a timeout, so it did
  not stop MC-SAT), e.g. 24 of 44 runs at 6×6, each taking about 25 minutes.
  At 7×7 it timed out on an evidence-free run and stopped.

With 25% of the plan observed no method does much better than chance: the
observed prefix is compatible with most destinations.  Even the **whole
plan** does not identify the goal: max-term's accuracy is 0.75 at 3×3,
falling to about 0.5 at 9×9 and 10×10 (chance 1/(N−1)).  Every run uses the
problem's recognition horizon, the longest of its goals' shortest plans, and a
hypothesis is scored at the final slice; after a shorter plan reaches its
destination, the truck can still drive on to another destination in the
remaining slices, so those destinations keep posterior mass.  SharpSAT-TD's
exact posterior, which counts every such continuation, puts even less on the
true goal than max-term's (accuracy 0.25–0.5 with full evidence).

**d4** (2 hours per compilation).  Every theory through 9×9 compiled; at
10×10 only `grid10x10-3` did (2404 s, 2.8 M nodes, 12 GB peak), the other
three timed out.  sharpSAT confirmed the circuit's model count for every
circuit through 6×6 and three of four at 7×7; from 8×8 on every check ran out
of its 30 minutes, so those circuits are unverified (d4 is known to
miscompile larger theories; see
[OldVersions/SimpleGrid/results/compile-d4.md](https://github.com/HenryKautz/CLARA/blob/ac6aa16/OldVersions/SimpleGrid/results/compile-d4.md)).
No count check disagreed.
