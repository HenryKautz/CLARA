# ThreePackage

One truck, three packages, every package delivered; regenerated 2026-10-31
(the version before, with its results, is
[OldVersions/ThreePackage](../OldVersions/ThreePackage/README.md)).  How the
problems were made and solved is in the [top-level README](../README.md) and
[scripts/README.md](../scripts/README.md).

## Problems

`gridNxN-K.pddl`, N = 5, 6, 7, K = 1..4 (the seed): an N×N grid with no
airports, 20% of the roads knocked out (a random spanning tree is kept, so every
place stays reachable), one truck and three packages placed at random, two
possible destinations per package (never its own start), and the goal that
**every** package reaches one of its own (`ppgen.sh --require all`):
`(and (or (at pkg1 a) (at pkg1 b)) (or (at pkg2 c) (at pkg2 d)) (or (at pkg3 e) (at pkg3 f)))`.
Drives cost 2, each load and unload 1 (domain `clara-logistics.pddl`, the same
actions and costs as the old `clara-logistics-handling.pddl`).  No preferences.

The **hypotheses** are the goal's 2³ = 8 combinations, one destination per
package.  `recognition/<problem>.pddl` writes the goal as `(or (and …) … (and
…))` over them — the same plans — and `recognize.sh` scores combination I
through a derived atom `rechypI` (the header lists which is which); chance is
1/8.

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

`<goal>` is the problem name followed by one destination per package, e.g.
`grid5x5-1-pkg1-p2-4-pkg2-p3-4-pkg3-p4-3`.  The true hypothesis of
`<goal>-obs*.txt` is that combination's `rechypI`.

## Results

Full tables: [tables.md](tables.md).  Every limit below is wall-clock time
for the whole run; when a run of some kind failed by timeout or memory at a
size, that kind of run was stopped there for that size and every larger one
("killed" in the tables).

**Planning** (30 minutes per solver run).  At 5×5 tt-open-wbo-inc planned all
32 goals and EvalMaxSAT proved every plan optimal; tt's plans were all
already optimal.  At 6×6 tt-open-wbo-inc found no plan at all within 30
minutes for `grid6x6-2-pkg1-p2-5-pkg2-p1-2-pkg3-p6-5` at its shortest horizon
(29), although kissat had found one, and EvalMaxSAT timed out on another 6×6
goal, so both stopped at 6×6.  One 6×6 problem had all its goals planned
before that; 7×7 was not planned.

**Recognition** (30 minutes per run).  Every method stopped at 5×5, the
smallest size: with no evidence max-term finished one problem (781 s) and
timed out on another; SharpSAT-TD and MC-SAT timed out on their first.  No
run with evidence was reached.

**d4** (2 hours per compilation).  All four 5×5 theories compiled (mean
1048 s), as did the one 6×6 problem with a recognition problem (3134 s,
1.4 M nodes).  sharpSAT confirmed the circuit's model count for two of the
5×5 circuits; on the others the check ran out of its 30 minutes, so those
circuits are unverified (d4 is known to miscompile larger theories; see
[OldVersions/SimpleGrid/results/compile-d4.md](../OldVersions/SimpleGrid/results/compile-d4.md)).
