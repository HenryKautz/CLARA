# scripts/ — the CLARA grid-benchmark pipeline

One set of scripts makes and solves all five grid families (SimpleGrid,
TwoPackage, TwoPackageOneway, ThreePackage, FourPackage).  Each script takes
`--family F` and works in `CLARA/F/`; each one's docstring gives the details.

| Script | Does |
|---|---|
| `common.py` | The family table (sizes, how the goal splits into hypotheses, the old family a family is made from, the `ppgen.sh` flags it drops and adds, and whether the world stays the old one), goal/hypothesis parsing, the process runner (wall limit, kill of the whole process tree, memory watch), and the paths. |
| `make-problems.py` | Remakes F's problems from `OldVersions/<source>` with the old `ppgen.sh` settings, but domain `clara-logistics`, `--handle-cost 1`, `--preferences none` and the family's own changes (ThreePackage and FourPackage drop `--knockout`; TwoPackageOneway is TwoPackage plus `--oneway 25`); checks each against the old one where the world is unchanged, and every settings block for the dropped and added flags; writes `goals/<goal>.pddl`, one per hypothesis. |
| `plan-goals.py` | Plans every goal at its shortest horizon with tt-open-wbo-inc and with EvalMaxSAT (the horizon search starts just below the old plan's horizon where the world is unchanged, else from scratch); picks the plan (EvalMaxSAT's if it proved its optimum, else tt's); writes the evidence and `recognition/<problem>.pddl`. |
| `run-recognize.py` | `recognize.sh` with max-term, sharpsat-td and mc-sat on every evidence file, 30 minutes per run. |
| `compile-d4.py` | d4 circuits of the evidence-free recognition theories, 2 hours each, each checked against SharpSAT-TD's count. |
| `summarize.py` | Tables of `results/*.jsonl`, written to `F/tables.md`. |
| `run-family.sh` | The Slurm job: the three stages above side by side, then `summarize.py`. |
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
