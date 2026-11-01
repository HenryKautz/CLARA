Files for UVA DARPA CLARA: plan-recognition benchmarks, made and solved with
[FiFO](https://github.com/HenryKautz/FiFO).

## Contents

Each benchmark directory has its own README, describing its problems, how they
were made, and its results.

The four grid benchmarks were **regenerated on 2026-10-31** (see
[The 2026-10-31 regeneration](#the-2026-10-31-regeneration)); the versions
before that, with their results, are in `OldVersions/`.

| Directory | What it holds | README |
|---|---|---|
| `SimpleGrid/` | One truck on an N×N grid (3×3–10×10) heading for one of N−1 destinations. | [SimpleGrid/README.md](SimpleGrid/README.md) |
| `TwoPackage/` | One truck, two packages with two destinations each, 3×3–7×7; four hypotheses (at least one package delivered). | [TwoPackage/README.md](TwoPackage/README.md) |
| `ThreePackage/` | One truck, three packages with two destinations each, all to be delivered, 5×5–7×7 with 20% of the roads knocked out; eight hypotheses (destination combinations). | [ThreePackage/README.md](ThreePackage/README.md) |
| `FourPackage/` | Two trucks, four packages with three destinations each, 6×6–15×15 with 40% of the roads knocked out; twelve hypotheses (at least one package delivered). | [FourPackage/README.md](FourPackage/README.md) |
| `scripts/` | The one pipeline that made and solved all four (below). | |
| `AAAI-2010-Benchmarks/` | Ramírez & Geffner's BlockWords and IntrusionDetection, original and as recognition instances, with exact posteriors. | [AAAI-2010-Benchmarks/README.md](AAAI-2010-Benchmarks/README.md) |
| `OldVersions/` | The grid benchmarks as they were before 2026-10-31 (old domain; FourPackage with goal preferences), their results and scripts; `RestrictedPlanning/` (FiFO's experimental `planner.sh --restrict` evaluated on them); and `make-fifo-files.py`/`.lisp`, which wrote the `wff/`, `scnf/` and `wcnf/` files of the old SimpleGrid, TwoPackage and AAAI-2010-Benchmarks (it still has those directories' old paths). | the READMEs inside |

## The 2026-10-31 regeneration

Every problem of SimpleGrid, TwoPackage, ThreePackage and FourPackage was made
again (`scripts/make-problems.py`) with the `ppgen.sh` settings recorded in the
old problem's header, except:

- **domain `clara-logistics`**, FiFO's current one: `load` and `unload` cost
  `(handle-cost)` = 1 each, and there is no `transfer` action.  SimpleGrid and
  TwoPackage used to be planned with what is now `clara-logistics-old` (free
  handling, `transfer`); ThreePackage and FourPackage used a local
  `clara-logistics-handling.pddl`, the same domain under another name.
- **no goal weights or preferences**: the goal is only the hard `(or …)` (or,
  in ThreePackage, `(and (or …) …)`) of the problem.  FourPackage's
  `--preferences 8 8` is gone.

The same seeds give the same grids, roads, starts and destinations; the script
checks that every new problem matches its old one apart from `(handle-cost)` and
the preferences.

The pipeline (`scripts/`, one Slurm job per family, `scripts/run-family.sh`):

1. **`plan-goals.py`** — each hypothesis as a hard goal (`goals/<goal>.pddl`),
   planned at its **shortest horizon** twice: by `tt-open-wbo-inc-Glucose4_1`
   (anytime) and by `EvalMaxSAT_bin` (exact) at the same horizon.  The evidence
   is cut from EvalMaxSAT's plan when it proved its optimum within 30 minutes,
   else from tt-open-wbo-inc's (`goals/<goal>.answer`; both plans are kept as
   `-tt.answer` / `-eval.answer`).  Then `recognition/<problem>.pddl`: the goal
   as one disjunction of the hypotheses, at the **recognition horizon**, the
   largest of their shortest horizons.
2. **Evidence**, pinned to time steps: none (`evidence/<problem>-none.txt`),
   the first 25% of the plan's actions, rounded up (`-obs25.txt`), and all of
   them (`-obs100.txt`).  Counted in actions, not time steps.
3. **`run-recognize.py`** — the posterior of the hypotheses only, by
   `recognize.sh` with `max-term` (EvalMaxSAT), `sharpsat-td` and `mc-sat`,
   30 minutes per run.
4. **`compile-d4.py`** — each problem's evidence-free recognition theory
   compiled by d4, 2 hours per problem; each circuit's count checked against
   SharpSAT-TD.

**Stop rule**, for every solver and method separately: when a run fails by
timeout or by running out of memory at some grid size, its other runs at that
size are killed and nothing is run at that size or larger.

`python3 scripts/summarize.py --family F` writes the tables in each family's
`tables.md`.

**Where each stopped** (details in each family's README):

| Family | Planning (tt / EvalMaxSAT) | max-term | SharpSAT-TD | MC-SAT | d4 compiled |
|---|---|---|---|---|---|
| SimpleGrid | all sizes / all | all sizes | to 6×6 (stopped 7×7) | to 6×6, many `nomix` (stopped 7×7) | all to 9×9; 1 of 4 at 10×10 |
| TwoPackage | all / all | all sizes | 3×3 (stopped 4×4) | 3×3, half `nomix` (stopped 4×4) | all sizes |
| ThreePackage | 5×5 / 5×5 (both stopped 6×6) | stopped 5×5 | stopped 5×5 | stopped 5×5 | 5×5, one 6×6 |
| FourPackage | to 9×9 (stopped 10×10) / stopped 6×6 | stopped 6×6 | stopped 6×6 | stopped 6×6 | none (all 6×6 timed out) |

d4 differs from the stop rule in one way: it finishes the size where a
compilation first fails, then tries nothing larger.  Circuits from SimpleGrid
8×8, TwoPackage 7×7 and some smaller ones are **unverified**: SharpSAT-TD's
count check did not finish in 30 minutes.  No check that finished disagreed.

## File types

The four grid benchmarks share one layout (each family's README lists it):

- **`*.pddl` — problems and domains.**  PDDL, made with FiFO's `ppgen.sh`.  Each
  problem opens with comment lines recording every `ppgen.sh` setting, so it can
  be regenerated exactly.  Its goal is the disjunction of the recognition
  hypotheses (ThreePackage: a conjunction of disjunctions, whose combinations
  are the hypotheses).
- **`goals/<goal>.pddl` — single-goal variants**: the problem with one
  hypothesis as its hard goal.
- **`*.answer` — plans**, as written by `planner.sh`: `SAT`, the cost as
  `(*OBJECTIVE* n)`, then the trajectory — `(HOLDS fluent t)` for what is true
  at time step `t`, and `(OCCURS action t)` for the action taken at step `t`.
- **`evidence/*.txt` — observations pinned to time steps**: one `(and ...)` of
  `(occurs action t)` literals (`<problem>-none.txt`: the empty `(and)`).  Use
  with `recognize.sh --evidence-kind fifo` or `planner.sh --evidence-file`.
  Each is a single form, which is what `recognize.sh` needs to negate it.
- **`recognition/<problem>.pddl` — the recognition problem**, with its
  recognition horizon in the header.
- **`scnf/`, `circuits/` — the evidence-free recognition theory** (FiFO's
  symbolic CNF) at that horizon, and its d4 circuit where d4 succeeded.  A pinned
  observation is a set of unit literals over the theory's atoms, so one theory
  and one circuit serve every evidence file of a problem.
- **`results/*.jsonl` — one JSON record per run**, appended as runs finish; a
  rerun supersedes the earlier record.  `scripts/summarize.py` turns them into
  `tables.md`.

`OldVersions/` keeps the old conventions (also `-ordN.txt` ordering evidence,
and `wff/`/`wcnf/` copies of the theories); see the READMEs there and
`OldVersions/make-fifo-files.py`.
