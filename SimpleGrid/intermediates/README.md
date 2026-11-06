# SimpleGrid intermediates

The files between each planning problem's PDDL and its plan, which the pipeline
made in scratch directories and threw away.  Made 2026-11-05 by
`scripts/make-intermediates.py` (FiFO e0dcb59), as one Slurm job
(`scripts/run-intermediates.sh`).  **Nothing was solved**: stand-ins for every
solver in FiFO's `lisp/solvers.dat` were first on `PATH`, each exiting 99 with
"SOLVER CALLED"; no log contains that line.

This directory holds the original problems `gridNxN-K`; `../goals/intermediates/`
holds the same files for the goal problems `goals/<goal>.pddl`.  The `.scnf`, `.wcnf` and
`.map` are committed gzipped (`gzip -n`; `gunzip -k` restores them, and the raw
files are git-ignored); the script writes them uncompressed.

| file | what it is | made by |
|---|---|---|
| `P.wff` | pddl2fifo's FiFO translation of `P.pddl` (domain `clara-logistics`); no horizon in it | `planner.sh P.pddl --domain ../clara-logistics.pddl --stop-after wff` |
| `P-H<h>.scnf.gz` | that theory instantiated at `h` time slices, `h` the horizon of P's plan | `planner.sh P.pddl --domain ../clara-logistics.pddl --numslices h --stop-after scnf` |
| `P-H<h>.wcnf.gz` | the weighted CNF a MaxSAT solver minimizes (2022 `h` format: hard clauses start `h`, soft ones with their weight) | `(propositionalize "P.scnf" :cnffile "P-H<h>.wcnf" :mapfile "P-H<h>.map" :cnf-format 'wcnf)` |
| `P-H<h>.map.gz` | `map N`, then one `i atom` line per variable of the `.wcnf` | the same call |
| `satplan.wff` | a copy of FiFO's `lisp/satplan.wff`, which every `.wff` here includes | |

The horizon `h` is the `horizon` of the plan's last record in
`results/originals.jsonl` / `results/plans.jsonl` (stages `eval` and `tt`), checked
against the highest slice of the plan file (`P-eval.answer`, `P-tt.answer`).  The
eval and tt plans of every problem have the same horizon, so there is one `-H<h>`
set per problem.  A problem with no plan has only its `.wff`.

Each `.wff` includes `"satplan.wff"`, resolved against the `.wff`'s own directory
(planner.sh wrote a path relative to its scratch directory; that one line is
rewritten).  Instantiating it with `*satplan-numslices*` = h gives the `.scnf`'s
clauses; the `.scnf` also has three `; fifo-projection-...` comment lines that
planner.sh adds.

Checks, all passed (per-job records in `results/intermediates.jsonl`): the `.wff`
is the `clara-logistics` translation; every action of the plan(s) is an `OCCURS`
atom of the `.map` at its slice; the `.wcnf`'s largest variable equals the `.map`'s
count; its hard and soft clause counts equal the `.scnf`'s `(OR ...)` and
`(WEIGHT ...)` forms.

Here: 32 original problems and 176 goal problems, all with plans; horizons 4 to 18.
