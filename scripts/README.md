# scripts/ — the CLARA grid-benchmark pipeline

One set of scripts makes and solves all five grid families (SimpleGrid,
TwoPackage, TwoPackageOneway, ThreePackage, FourPackage).  Each script takes
`--family F` and works in `CLARA/F/`; each one's docstring gives the details.

| Script | Does |
|---|---|
| `common.py` | The family table (sizes, how the goal splits into hypotheses, the old family a family is made from, the `ppgen.sh` flags it drops and adds, and whether the world stays the old one), goal/hypothesis parsing, the process runner (wall limit, kill of the whole process tree, memory watch), and the paths. |
| `make-problems.py` | Remakes F's problems from `OldVersions/<source>` (deleted from the tree in 7731002: restore it with `git checkout ac6aa16 -- OldVersions`, or set `$CLARA_OLD` to a checkout of it) with the old `ppgen.sh` settings, but domain `clara-logistics`, `--handle-cost 1`, `--preferences none` and the family's own changes (ThreePackage and FourPackage drop `--knockout`; TwoPackageOneway is TwoPackage plus `--oneway 25`); checks each against the old one (apart from the roads, in a family that changes them), every settings block for the dropped and added flags, and that no `--oneway` quota fell short; writes `goals/<goal>.pddl`, one per hypothesis.  It refuses to change a problem of a family that already has `results/*.jsonl` (the later stages would reuse those results); `--archive` first moves the family's outputs into `F/superseded-<date-time>/`. |
| `plan-goals.py` | Plans every goal at its shortest horizon with tt-open-wbo-inc and with EvalMaxSAT (the horizon search starts just below the old plan's horizon where the world is unchanged, else from scratch); picks the plan (EvalMaxSAT's if it proved its optimum, else tt's); writes the evidence and `recognition/<problem>.pddl`. |
| `run-recognize.py` | `recognize.sh` with max-term, sharpsat-td and mc-sat on every evidence file, 30 minutes per run. |
| `compile-d4.py` | d4 circuits of the evidence-free recognition theories, 2 hours each, each checked against SharpSAT-TD's count. |
| `summarize.py` | Tables of `results/*.jsonl`, written to `F/tables.md`. |
| `run-family.sh` | The Slurm job: the three stages above side by side, then `summarize.py`. |
| `plan-originals.py` | Plans each ORIGINAL problem `F/gridNxN-K.pddl` (goal = the disjunction) with tt-open-wbo-inc (shortest horizon H0 by kissat, then the cheapest plan over H0..H0+4, `--longer 4`) and EvalMaxSAT (`--numslices H0 --longer 4`, kept only when it proved the optimum at every horizon); writes `F/gridNxN-K-tt.answer` / `-eval.answer` and `results/originals.jsonl`, and checks each plan against the goal plans of `plans.jsonl` (`--check-only` reruns just the checks). Separate from the pipeline above; touches no goal, evidence or recognition file. |
| `run-originals.sh` | Its Slurm job, then `summarize.py`: `sbatch -J orig-F -o F/originals-run.log scripts/run-originals.sh F`. |
| `make-intermediates.py` | Keeps the files between each planning problem's PDDL and its plan (translation and instantiation only, **no solver may run**), for the originals and the goal problems:<br>• `F/intermediates/P.wff` and `F/goals/intermediates/P.wff`, the translation.<br>• `P-H<h>.scnf`, instantiated at the recorded horizon of each eval/tt plan, which is checked against the plan file.<br>• `P-H<h>.wcnf`/`.map`, from FiFO's `propositionalize`.<br>It also makes any missing `F/scnf/<p>.scnf` recognition theory as `compile-d4.py` does, and regenerates `--verify-rec` existing ones to compare byte for byte.<br>`$CLARA_STUBS` must hold stand-ins for every solver in `solvers.dat`, which are put first on PATH. Each stand-in exits 99 and writes "SOLVER CALLED" into the run's own log, and every log is checked for that line.<br>Records go to `results/intermediates.jsonl`. The kept `.scnf`/`.wcnf`/`.map` are committed gzipped (`gzip -k -n`). |
| `make-stubs.sh` | `make-stubs.sh DIR` writes those stand-ins (from FiFO's `solvers.dat`). |
| `run-intermediates.sh` | Its Slurm job, over all five families by default: `CLARA_STUBS=<dir> sbatch --export=ALL -J intermediates -o intermediates-run.log scripts/run-intermediates.sh`. |
| `shims/` | `sbcl` (a larger heap and stack) and `d4` (records d4's time, input and dump), put first on PATH. |

To run a family (FiFO installed in `~/bin`, `~/lib/fifo`):

```sh
cd CLARA
python3 scripts/make-problems.py --family TwoPackage
sbatch -J clara-TwoPackage -o TwoPackage/run.log scripts/run-family.sh TwoPackage
```

`run-family.sh` finds the scripts through `$SLURM_SUBMIT_DIR`, so submit from
`CLARA/`; from anywhere else, add `--chdir=<CLARA> --export=ALL,CLARA_SCRIPTS=<CLARA>/scripts`.

Every stage appends one JSON record per run to `F/results/*.jsonl` and resumes
from it, so a stopped job is simply resubmitted.

**Stop rule** (every stage, per solver or method): when a run fails by timeout
or by memory at grid size s, the runs of that solver/method still going at s
or larger are killed and none is started at s or larger.  Recognition and d4
start a size only once planning has settled it (`plans.jsonl`, stage `size`).

Scratch goes to `$CLARA_SCRATCH` (default `$TMPDIR/clara`); its path must
contain no `.` (FiFO derives `.satout` names from the first dot).
