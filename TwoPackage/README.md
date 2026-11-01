# TwoPackage

One truck, two packages, at least one of them delivered; regenerated
2026-10-31 (the version before, with its results, is
[OldVersions/TwoPackage](../OldVersions/TwoPackage/README.md)).  How the
problems were made and solved is in the [top-level README](../README.md) and
[scripts/README.md](../scripts/README.md).

## Problems

`gridNxN-K.pddl`, N = 3..7, K = 1..4 (the seed): an N×N grid with no airports,
one truck and two packages placed at random, two possible destinations per
package (never its own start; the packages may share one), and the goal that
**at least one** package reaches one of its destinations (`ppgen.sh --require
some`): `(or (at pkg1 a) (at pkg1 b) (at pkg2 c) (at pkg2 d))`.  Drives cost 1,
each load and unload 1 (domain `clara-logistics.pddl`).  No preferences.

The **hypotheses** are the four literals, named `at-pkgI-<place>` by
`recognize.sh`; chance is 1/4.

## Layout

```
gridNxN-K.pddl              problems; clara-logistics.pddl, their domain
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
results/                    plans.jsonl, runs.jsonl, compile-d4.jsonl: a record per run
tables.md                   scripts/summarize.py's tables
*.log                       the stages' logs
```

`<goal>` is the problem name followed by the hypothesis's object and place,
e.g. `grid4x4-1-pkg1-p2-3`.  The true hypothesis of `<goal>-obs*.txt` is that
goal's.

## Results

Full tables: [tables.md](tables.md).  Every limit below is wall-clock time
for the whole run; when a run of some kind failed by timeout or memory at a
size, that kind of run was stopped there for that size and every larger one
("killed" in the tables).  Accuracy scores a run 1/k when the true hypothesis
ties with k − 1 others for the highest posterior.

**Planning** (30 minutes per solver run).  Every goal at every size was
planned by tt-open-wbo-inc, and EvalMaxSAT proved every plan optimal; tt's
plans were all already optimal, so the evidence comes from EvalMaxSAT's
plans throughout.  Mean horizon grows from 6.4 (3×3) to 14.2 (7×7).

**Recognition** (30 minutes per run).

- **max-term** solved every run at every size (mean 10 s at 3×3, 600–700 s
  at 7×7).  With 25% of the plan observed its accuracy is 0.41–0.50 (chance
  0.25), mean posterior of the true goal 0.39–0.47; with the whole plan,
  accuracy 1.0 and mean posterior ≥ 0.976.
- **SharpSAT-TD** solved all of 3×3 (accuracy 0.375 at 25%, 1.0 at 100%;
  mean posterior 0.48 and 0.998).  At 4×4 it timed out on one
  evidence-free problem, so it stopped there.
- **MC-SAT** often failed to mix (the chain froze, giving the true goal a
  posterior of 0; status `nomix`, which is a failed estimate, not a timeout):
  at 3×3, 19 of 36 runs.  Where it did mix it agreed with the exact
  methods.  It timed out at 4×4 and stopped there.

**d4** (2 hours per compilation).  Every theory at every size compiled; 7×7
takes 1730 s on average and up to 24 GB.  sharpSAT confirmed the circuit's
model count for 11 of the 20 circuits, all 3×3–6×6; on the other nine the
check ran out of its 30 minutes, so those circuits — including all of 7×7 —
are unverified (d4 is known to miscompile larger theories; see
[OldVersions/SimpleGrid/results/compile-d4.md](../OldVersions/SimpleGrid/results/compile-d4.md)).
No count check disagreed.
