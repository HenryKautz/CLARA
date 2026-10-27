# FourPackage: handoff (2026-10-27, from the laptop to the server)

Everything needed to resume is in git: this repo (CLARA) and FiFO. On the
server, Claude Code should read this file first.

## The dataset

40 problems `gridNxN-K.pddl`, N = 6..15, K = 1..4: two trucks, four packages,
40% of roads knocked out, a 12-way disjunctive goal with preferences. Domain:
`clara-logistics-handling.pddl` (no transfer action). Scripts are in `scripts/`,
results in `results/*.jsonl` (one JSON record per run; a rerun supersedes),
logs `*.log` at this level. `python3 scripts/summarize.py` prints the three
tables (per problem, per size, encoding comparison).

Stages (each resumes; see the docstrings):

1. `run-plans.py --stage general`: each problem as posed (`general/`).
2. `run-plans.py --stage goals`: each goal literal clamped as the hard goal
   (preferences kept), planned at its shortest horizon (`goals/`), then evidence
   `evidence/*-obsK.txt` / `-ordK.txt`, K = 2, 4, 8.
3. `make-formats.py`: `wff/NAME.wff` (self-contained FiFO) and `wcnf/` (MCC 2020
   and 2024 weighted CNF + map) at the recognition horizon.
4. `run-recognize.py`: Ramirez & Geffner recognition (not started at scale).

## The MUTEX encoding (FiFO)

SatPlan's interfering-action mutexes on `(in pkg truck)` were O(n⁴) per slice:
80% of the clauses at 6x6. FiFO now has a general operator
`(mutex (v1 D1 g1 φ1) (v2 D2 g2 φ2))` (README "Mutual Exclusion"): written as a
linear prefix/suffix chain of defined TSEITIN atoms when that is smaller, else
pairwise; `*mutex-pairwise*` forces pairwise. `lisp/satplan.wff` uses it. Same
models, so same optima (count-neutral). Theory size is now about 220·n²·H
clauses (was 25,500·(n/6)⁴·H).

**User rule:** sizes 6..11 keep the ORIGINAL (pairwise) encoding: their records
have no `encoding` field (= "pairs") and `wff/` 6..11 include `wff/satplan.wff`,
the original axioms. 12..15 use MUTEX (`"encoding": "mutex"`;
`wff/satplan-mutex.wff`). `fpcommon.encoding()` reads which encoding the FiFO in
use has (`$FIFO_LISP`, else `~/lib/fifo/lisp`).

`compare-encodings.py` (done, 6x6..11x11, `results/encodings.jsonl`): original,
pairwise and linear all reach the same optimum on all 24 problems; linear is
0.11-0.30x the clauses and ~2x faster. It uses macOS `/usr/bin/time -l`.

## Status

| Stage | 6x6..11x11 | 12x12 | 13x13 | 14x14 | 15x15 |
|---|---|---|---|---|---|
| general (wmaxcdcl) | done | 4/4 | 4/4 | 4/4 | 3/4: **15x15-3 timed out** (1800 s, minimizing at H=23) |
| goals (tt-open-wbo-inc, 300 s solver cap) | 48/48 each | 48/48 | **30/48** | **0/48** | **not started** |
| formats | done | **todo** | **todo** | **todo** | **todo** |
| evidence (`--stage evidence`) | needs rerun (old strict ordK) | | | | |
| recognition | 1 test run only | | | | |

13x13/14x14 goals failed on the laptop for machine reasons, not the encoding:
6 goals at once on 16 GB swapped (SBCL ~2.5 GB each plus ~1 GB per million
clauses; 4 runs died with SBCL "Can't handle sig11"), and the laptop slept
mid-run (the wall-clock limit counts sleep). Goal horizons are long: 26-64 slices
at 12x12-14x14 (general problems: 6-23).

## Resume on the server

```sh
cd ~/Programming/FiFO && git pull && make install     # the MUTEX FiFO into ~/bin, ~/lib/fifo
bash bin/install-solvers.sh                            # if solvers are missing (kissat, wmaxcdcl,
                                                       #   EvalMaxSAT_bin, tt-open-wbo-inc-Glucose4_1)
bash bin/run_regression_tests.sh                       # sanity: all suites pass on the laptop
cd ~/Programming/CLARA && git pull
python3 -c 'import sys; sys.path.insert(0,"FourPackage/scripts"); import fpcommon as F; print(F.encoding())'   # must print mutex
WORKERS=6 nohup bash FourPackage/scripts/resume-mutex.sh > FourPackage/resume.log 2>&1 &
```

`scripts/resume-mutex.sh` does, in order: general 15x15-3 with EvalMaxSAT_bin;
goals 13x13..15x15 (`WORKERS` at once, default 3; `BUDGET` M predicted clauses,
default 2×WORKERS; `LIMIT` s per goal, default 3600 — goals that timed out at
1800 s are rerun); make-formats 12..15; `--stage evidence` for all sizes. It
refuses to run unless the installed FiFO is the MUTEX one. Size WORKERS to RAM:
allow ~6 GB per run (`FP_HEAP_MB` sets SBCL's reserved heap, default 12288).

Scratch goes under `$FP_SCRATCH` (default `/tmp/fourpackage`); its path must
contain no `.`. Paths in this repo are found relative to the scripts; FiFO tools
are found on PATH (`~/bin`).

Not in git (regenerable, too large): `scnf/` (old, 7 GB, 6..11), `wcnf/`
(2.5 GB; `make-formats.py --sizes 6 7 8 9 10 11` rewrites it, but with MUTEX
installed it would write MUTEX wffs for those sizes — to reproduce the originals
set `FIFO_LISP` to a pre-MUTEX FiFO lisp, e.g. `git worktree` of FiFO c5b1d61),
`general/*.wcnf|*.map` (rewritten by a general rerun).

## Traps learned here

- FiFO solvers can escape their process group: after a killed run, look for
  orphaned `sbcl`/solver processes (PPID 1) and kill them; the scripts
  `pkill -f <scratch dir>/` on timeout.
- Exact solvers: EvalMaxSAT_bin proved optima where wmaxcdcl found nothing
  (long horizons); rc2 needs python-sat. Anytime: tt-open-wbo-inc-Glucose4_1.
- R&G (`run-recognize.py`, EvalMaxSAT_bin): a full 6x6-2 obs2 run took 7932 s and
  the true goal tied with 8 others; all 6x6 evidence would be ~600 CPU-h.
- FiFO quirk found (unchanged, user to decide): `parse-not` reads
  `(not (if <false-test> X))` as TRUE.

## Pending decisions for the user

- R&G scope (subset of evidence, which sizes).
- Whether `/code-review high` on FiFO's `parse-mutex` section and these scripts.
- Updating CLARA README's FourPackage section once the tables are final.
