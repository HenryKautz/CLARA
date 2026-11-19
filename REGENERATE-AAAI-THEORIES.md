# Regenerate the AAAI-2010 theories with FiFO's current encoding, and rerun them

**Why.** FiFO's SatPlan axioms (`lisp/satplan.wff`) now state action
interference with `mutex`, which writes a chain of defined `TSEITIN` atoms
instead of the pairwise clauses whenever the chain is smaller. The committed
AAAI theories in `AAAI-2010-Benchmarks/scnf/` were made with the pairwise
clauses. Checked on this machine with today's FiFO:

- `IntrusionDetectionCosts-obs1` (H = 6) still regenerates **byte-identical**:
  at that size the pairwise clauses are still the smaller choice.
- `BlocksWorldCosts-obs1` (H = 15) **differs**: 45,587 clauses, 25,340 of its
  lines mentioning `TSEITIN` atoms, against the committed 240,551 clauses and no
  `TSEITIN` at all (2.8 MB against 16 MB).

FiFO documents that both encodings have the same models, so plans, costs,
counts and posteriors should not change. But `results/runs.jsonl` and the
README's tables were measured on the old theories. The job: regenerate every
theory that changes, rerun the benchmarks on those, check the numbers that must
not move, and update the README.

Read FiFO's `CLAUDE.md` first; the rules that matter most here are that
differences of MaxSAT minima need an EXACT solver, and that every aux atom must
be defined (count-neutral).

## 0. Before starting

- `git pull` FiFO and CLARA; `make install` from the FiFO checkout. Record
  FiFO's commit (`git -C <FiFO> rev-parse --short HEAD`): it goes into the
  README and the commit message.
- Check `grep -n mutex ~/lib/fifo/lisp/satplan.wff` shows the `mutex` forms;
  if not, the installed FiFO is older than the encoding change.
- Work in `CLARA/AAAI-2010-Benchmarks/`. Every command below runs from there.

## 1. Regenerate the theories (no solving)

```sh
python3 make-fifo-files.py --replace --jobs 7
```

It regenerates all seven theories (`<inst>-obsK`, K = 1, 3, 5, for
IntrusionDetectionCosts and BlocksWorldCosts, plus
`IntrusionDetectionCosts-obs3-H5`) with `recognize.sh --stop-after scnf`,
refreshes `wff/satplan.wff` from FiFO, rewrites `wff/` and `wcnf/`, and checks
that every `.wff` instantiates to its theory's clauses. With `--replace`, a
theory that differs replaces the one in `scnf/`; each line ends
`theory REPLACED` or `theory unchanged`. Any line that does not start `ok` is a
failure: stop and report it.

Then:

- `git status` / `git diff --stat`: list which theories were replaced. Expect
  the three BlocksWorldCosts ones; report whether any IntrusionDetectionCosts
  theory changed too.
- For each replaced theory, check it is the `mutex` change and nothing else: its
  variable count grew by exactly its number of `TSEITIN` atoms, it has no
  other new atom names, and its weighted `(WEIGHT ...)` forms are the same as
  the old theory's (`git show HEAD:AAAI-2010-Benchmarks/scnf/<name>.scnf`).
  Report anything else and stop.

## 2. Rerun the benchmarks on the replaced theories (solving)

`run-benchmarks.py` resumes from `results/runs.jsonl` and skips every
(instance, observations, method) it has a record for. So first take the
replaced theories' old records out:

- Keep the old file for comparison: `cp results/runs.jsonl
  results/runs-pairwise.jsonl` (do not commit it; delete it at the end).
- Write a new `results/runs.jsonl` without the records of the replaced theories
  (match on `instance` and `n_obs`; the H5 theory's records, if any, are in
  `results/crosscheck-intrusion-obs3-h5.txt`, not here). Keep every other record
  untouched and in order.

Then run the methods that were run on them before. For BlocksWorldCosts that is
max-term, sharpsat-td, d4 and d4-project (ddnnf and mc-sat were run on
IntrusionDetectionCosts only):

```sh
python3 run-benchmarks.py --match '^BlocksWorldCosts-' \
    --methods max-term,sharpsat-td,d4,d4-project --limit 3600 --jobs 12
python3 summarize.py
```

Keep `--limit 3600`, so the new results stay comparable with the rest of the
table. If an IntrusionDetectionCosts theory was replaced, rerun all six of its
methods the same way. If `IntrusionDetectionCosts-obs3-H5` was replaced,
recompile its circuit and redo the cross-check as the README's "Checks" section
describes (`circuits/IntrusionDetectionCosts-obs3-H5.dnnf`,
`circuits/query-h5-circuit.lisp`, `results/crosscheck-intrusion-obs3-h5.txt`).

Watch for orphaned solvers between and after runs (`ps -eo pid,ppid,etime,cmd`;
PPID 1 sharpSAT, d4 or sbcl processes), and kill them.

## 3. Check what must not move

Against `results/runs-pairwise.jsonl`, for every run that finished both times:

- **max-term**: the same `c_O` and `c_notO` per hypothesis and the same
  posterior to every printed digit. These are MaxSAT optima with an exact
  solver, so they cannot depend on the encoding. Any difference is a bug:
  stop and report.
- **sharpsat-td**: the same posterior, to the precision recorded. The old sweep
  has only BlocksWorldCosts obs5 (0.644 for hyp16). Equal model counts are
  FiFO's claim for the two encodings, so a difference here is a bug too.
- Runs that timed out before and finish now (or the other way round) are
  expected: the chain makes the theory much smaller. Report each one, with its
  time. A newly finished exact method must agree with every other exact method
  that finished on the same theory (max-term ranks agree; sharpsat-td, d4 and
  d4-project posteriors equal).

## 4. Update the README (`AAAI-2010-Benchmarks/README.md`)

Describe what is there now; no history of the earlier encoding (no dates, no
"previously", no before/after columns).

- **Theory sizes** table: from the `ok` lines of step 1 (variables / clauses of
  each `NAME`, not the `-ev` variant).
- **Results** table and the paragraphs after it ("d4 compilation", "Reading the
  results", any number quoting a BlocksWorldCosts time, status or posterior):
  from `summarize.py`'s output. Reword any sentence the new results contradict,
  e.g. "All twelve compiles ... hit the 60-minute limit" if a BlocksWorld d4
  compile now finishes.
- **"Results recorded in FiFO"** (the MAP and R&G tables near the top): their
  BlockWords rows give Vars and Clauses of the old theories (3,681 / 240,552
  ...). Rerun the MAP command for BlockWords from the "Running" section for 1,
  3 and 5 observations (`planner.sh ... --pddl-evidence-file
  BlocksWorldCosts/evidence-K.txt`, as the table was made) and update Vars,
  Clauses, Time and the MAP cost. The cost and the recognized hypothesis must
  not change; if either does, stop and report.
- Add one sentence where the theories are described ("What is saved here"):
  the theories are made by FiFO <commit>, whose SatPlan axioms write action
  interference with `mutex`.

## 5. Finish

- `python3 make-fifo-files.py` (no `--replace`) must now report every theory
  `ok ... theory unchanged`: the committed files reproduce with this FiFO.
- Delete `results/runs-pairwise.jsonl`, `work/` and `work-fifo-files/` if left.
- Delete this file. Commit with a message listing the replaced theories, their
  old and new clause counts, the reruns and their outcomes (each finished or
  timed out, each check of step 3), and FiFO's commit; push.
