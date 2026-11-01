# SimpleGrid

Plan-recognition problems in the `clara-logistics` PDDL domain, made with the
[FiFO](https://github.com/HenryKautz/FiFO) tools `ppgen.sh`, `planner.sh` and
`evgen.sh`.  The file types are described in the [top-level README](../README.md).

**Domain name.** These problems were made and solved with the `clara-logistics`
of before 2026-10-30 (free loading and unloading, a `transfer` action).  FiFO's
`clara-logistics` has since changed (handling costs `(handle-cost)`, no
transfer); the old one is FiFO's `pddl/clara-logistics-old.pddl`, and every
problem here now names `(:domain clara-logistics-old)`, as do this directory's
scripts.  Nothing was regenerated: the results and archived theories are those
the old domain produced, and planning these problems now reproduces them.

## Layout

```
gridNxN-K.pddl                    problems
goals/
  <problem>-<place>.pddl          single-goal variants of the problems
  <problem>-<place>.answer        a plan for each variant
evidence/
  <problem>-<place>-obsN.txt      observations from those plans, pinned to time steps
  <problem>-<place>-ordN.txt      the same observations, as an ordering only
wff/<problem>.wff                 FiFO source of each problem's recognition theory
scnf/<problem>.scnf               that theory, instantiated (symbolic CNF)
wcnf/                             its weighted CNF, both dialects, and the solved
                                  examples (see wcnf/README.md)
circuits/                         d4 circuits (see circuits/README.md)
results/                          sweep results, and the tables made from them
                                  (summary-by-grid.md, table-*.md, compile-d4*.md)
```

## Problems

`gridNxN-K.pddl`.  An N×N grid of places named `pR-C` (row, column), with
two-way roads between adjacent places and no airports, airplanes or packages.
A single truck starts at the corner `p1-1`.  The goal is a disjunction: the
truck must reach any one of several possible destinations, all at least a fixed
number of road steps from `p1-1`.  `K` numbers the problems of each size, which
differ in the destinations chosen.  Each file opens with comment lines
recording the `ppgen.sh` settings that generated it, so it can be regenerated
exactly.

## `goals/`

One entry per possible goal of a problem.
- `<problem>-<place>.pddl` is the problem with its goal narrowed to that single
  destination: the truck must end at `<place>`.  Everything else is unchanged.
- `<problem>-<place>.answer` is a shortest plan for it, as written by
  `planner.sh`: `SAT`, the plan's cost as `(*OBJECTIVE* n)`, then the trajectory
  — `(HOLDS fluent t)` for what is true at time step `t`, and `(OCCURS action t)`
  for the action taken at step `t`.  Each plan is one of possibly many shortest
  routes, so it stands for "an agent heading to `<place>`".

## `evidence/`

What an observer sees of such an agent: the first `N` actions of the plan in
`goals/<problem>-<place>.answer`, in two forms.  Only actions are observed, not
the truck's location.  The file's true goal is `<place>`; a recognizer is given
the original problem's possible goals and the evidence, and asked which goal is
being pursued.  Longer prefixes (larger `N`) give more evidence, up to the
length of the plan.
- `<problem>-<place>-obsN.txt` pins each action to its time step: a single
  `(and ...)` of `(occurs (drive truck1 from to) t)` literals, the actions at
  steps 1..N.  This claims the agent started at once and was watched without
  gaps.  Use it with `recognize.sh --evidence-kind fifo`, or
  `planner.sh --evidence-file`.
- `<problem>-<place>-ordN.txt` gives the same actions as an ordering only: a
  single `(occur-in-order a1 ... aN)` — they happened in this order, at time
  steps it does not fix.  This is the Ramírez & Geffner observation model.  Use
  it with `recognize.sh` (its default `--evidence-kind pddl`), or
  `planner.sh --pddl-evidence-file`.
- Each file is one form, which is what `recognize.sh` needs to negate it.  The
  original problems can be given to `recognize.sh` directly: their goal literals
  `(at truck1 <place>)` are the hypotheses, e.g.
  `recognize.sh clara-logistics-old.pddl grid4x4-1.pddl evidence/grid4x4-1-p3-4-ord3.txt`.
- Each file opens with comment lines recording the `evgen.sh` settings that made
  it, with paths relative to `SimpleGrid/`: run `evgen.sh` with those settings
  from `SimpleGrid/` to regenerate it exactly.
