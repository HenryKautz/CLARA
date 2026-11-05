# Generate CLARA's missing intermediate files -- translation only, no solving

**Goal.** For every planning problem in CLARA, keep the files between the PDDL and
the plan, which the pipeline made in scratch directories and threw away:

1. the FiFO translation (`.wff`, written by pddl2fifo),
2. that theory instantiated at the plan's horizon (`.scnf`),
3. the weighted CNF a MaxSAT solver minimizes (`.wcnf`, with its `.map` giving
   the integer <-> atom correspondence).

Also fill in the recognition theories `scnf/<problem>.scnf` that are missing.

**Do not re-solve anything.** No SAT, MaxSAT or model-counting solver may run. Every
horizon comes from the plans and records CLARA already has. This is translation and
instantiation only.

Families: SimpleGrid, TwoPackage, TwoPackageOneway, ThreePackage, FourPackage (not
AAAI-2010-Benchmarks, which has its own `wff/` and `wcnf/`). Domain: each family's
`clara-logistics.pddl` (load and unload cost `(handle-cost)`, no transfer).

Read FiFO's `CLAUDE.md` first. Keep FiFO current (`git pull`, `make install`).

## 0. Guarantee nothing is solved

Before anything else, put a directory of stand-in solvers FIRST on `PATH` for every
run below: an executable for each name in FiFO's `lisp/solvers.dat` (kissat, the
MaxSAT solvers, rc2-maxsat.py, sharpSAT, addmc, d4, walksat, ...) that prints
"SOLVER CALLED: <name>" to stderr and exits 99. Any accidental solver call then
fails loudly instead of quietly re-solving. Check that every log below is free of
"SOLVER CALLED".

## 1. Which problems, at which horizons

For each family `F`:

- **Original problems** `F/gridNxN-K.pddl`: the plans are `F/gridNxN-K-eval.answer`
  and `-tt.answer`; `F/results/originals.jsonl` records each plan's kept `horizon`
  (stage `eval` / `tt`, status `ok`).
- **Goal problems** `F/goals/<goal>.pddl`: plans `<goal>-eval.answer`,
  `-tt.answer`; `F/results/plans.jsonl` records each plan's `horizon` (stages `eval`
  / `tt`, the last record per goal and stage).
- **Recognition problems** `F/recognition/gridNxN-K.pddl`: the recognition horizon
  is in the file's header; the theory is `F/scnf/gridNxN-K.scnf` where
  `compile-d4.py` already made it.

Take the horizon from the record; cross-check it against the plan file (the
highest slice in its `OCCURS`/`HOLDS` lines). If they disagree, stop and report. A
problem with no plan (planning failed or was stopped) gets the `.wff` only. If the
eval and tt plans of one problem have DIFFERENT horizons, instantiate at each.

## 2. Generate, per planning problem P at horizon H

Run each in its own scratch directory under the family's scratch dir, as
`scripts/plan-goals.py` does: copy P in, run there, copy the results out.

- `.wff`: `planner.sh P.pddl --domain F/clara-logistics.pddl --stop-after wff`
  (translation only). One per problem; the horizon is not in it.
- `.scnf`: `planner.sh P.pddl --domain F/clara-logistics.pddl --numslices H
  --stop-after scnf` (instantiation at H, no horizon search, no solving).
- `.wcnf` + `.map`: propositionalize that `.scnf` in FiFO's Lisp,
  `(propositionalize "P-H.scnf" :cnffile "P-H.wcnf" :mapfile "P-H.map"
  :cnf-format 'wcnf)` (load FiFO.lisp via `$FIFO_LISP`, as `bin/fifo-lisp.sh`
  finds it). Check that format symbol against `propositionalize`'s docstring in
  `lisp/FiFO.lisp` (WCNF = the 2022 'h' format) before running all of them.

For missing recognition theories: `recognize.sh F/clara-logistics.pddl
F/recognition/<p>.pddl F/evidence/<p>-none.txt --evidence-kind fifo --stop-after
scnf --horizon <recognition horizon> --planner-timeout none --out <scratch>`, then
copy `<scratch>/rec-problem.scnf` to `F/scnf/<p>.scnf`, exactly as
`compile-d4.py`'s `prepare()` does. Never overwrite an existing `F/scnf/<p>.scnf`.
Instead, regenerate one or two and check they are byte-identical to the
committed ones; report if not.

## 3. Where they go

```
F/intermediates/<problem>.wff
F/intermediates/<problem>-H<h>.scnf
F/intermediates/<problem>-H<h>.wcnf
F/intermediates/<problem>-H<h>.map
F/goals/intermediates/<goal>.wff          (and -H<h>.scnf/.wcnf/.map)
F/scnf/<problem>.scnf                     (recognition theories, existing layout)
```

Write a short `F/intermediates/README.md` saying what each file is, the command
that made it, and that nothing was solved.

## 4. Checks, without solving

- The `.wff` names `(:domain clara-logistics)`'s translation, never
  `clara-logistics-old` (deleted from FiFO).
- Every action in the plan file appears as an `(OCCURS ...)` atom in that
  horizon's `.map`, at its slice. So the theory at H can express the plan.
- The `.wcnf` header's variable count equals the `.map`'s entries, and its hard
  and soft clause counts match the `.scnf` (hard `(OR ...)` lines; `(WEIGHT ...)`
  lines).
- No log contains "SOLVER CALLED".

## 5. Size, then ask before committing

The larger goal problems (FourPackage up to 15x15, horizons in the 30s and 40s) can
make `.scnf` and `.wcnf` files of hundreds of MB each, and there are ~1,000
planning problems. **Before committing**:

- Generate everything (or the small sizes first), then report to the user: the
  total size per family and per file type, the largest files, and the count over
  100 MB.
- Ask the user how to keep them. The options: commit all, splitting files over 100
  MB with CLARA's `unassemble.sh` (and git-ignoring the whole files, as the
  circuits are); commit only up to some size; commit gzipped files; or keep them on
  the cluster only.

Then commit as the user decides, with a message listing what was generated per
family and that no solver ran, and push.
