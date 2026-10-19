Files for UVA DARPA CLARA.

## Layout

```
SimpleGrid/
  gridNxN-K.pddl                    problems
  goals/
    <problem>-<place>.pddl          single-goal variants of the problems
    <problem>-<place>.answer        a plan for each variant
  evidence/
    <problem>-<place>-obsN.txt      observations from those plans, pinned to time steps
    <problem>-<place>-ordN.txt      the same observations, as an ordering only
TwoPackage/
  gridNxN-K.pddl                    problems
  goals/
    <problem>-<pkg>-<place>.pddl    single-goal variants of the problems
    <problem>-<pkg>-<place>.answer  a plan for each variant
    <problem>-<pkg>-<place>-clean.answer  the same plan without the other package's loads/unloads
  evidence/
    <problem>-<pkg>-<place>-obsN.txt   observations from the cleaned plans, pinned to time steps
    <problem>-<pkg>-<place>-ordN.txt   the same observations, as an ordering only
  results/                          sweep results (compile-d4, query-evidence, recognition runs)
  circuits/                         theories and d4 circuits (see circuits/README.md)
```

## SimpleGrid

Plan-recognition problems in the `clara-logistics` PDDL domain, made with the
[FiFO](https://github.com/HenryKautz/FiFO) tools `ppgen.sh`, `planner.sh` and
`evgen.sh`.

**Problems** — `gridNxN-K.pddl`.  An N×N grid of places named `pR-C` (row,
column), with two-way roads between adjacent places and no airports, airplanes
or packages.  A single truck starts at the corner `p1-1`.  The goal is a
disjunction: the truck must reach any one of several possible destinations, all
at least a fixed number of road steps from `p1-1`.  `K` numbers the problems of
each size, which differ in the destinations chosen.  Each file opens with
comment lines recording the `ppgen.sh` settings that generated it, so it can be
regenerated exactly.

**`goals/`** — one entry per possible goal of a problem.
- `<problem>-<place>.pddl` is the problem with its goal narrowed to that single
  destination: the truck must end at `<place>`.  Everything else is unchanged.
- `<problem>-<place>.answer` is a shortest plan for it, as written by
  `planner.sh`: `SAT`, the plan's cost as `(*OBJECTIVE* n)`, then the trajectory
  — `(HOLDS fluent t)` for what is true at time step `t`, and `(OCCURS action t)`
  for the action taken at step `t`.  Each plan is one of possibly many shortest
  routes, so it stands for "an agent heading to `<place>`".

**`evidence/`** — what an observer sees of such an agent: the first `N` actions
of the plan in `goals/<problem>-<place>.answer`, in two forms.  Only actions are
observed, not the truck's location.  The file's true goal is `<place>`; a
recognizer is given the original problem's possible goals and the evidence, and
asked which goal is being pursued.  Longer prefixes (larger `N`) give more
evidence, up to the length of the plan.
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
  `recognize.sh clara-logistics.pddl grid4x4-1.pddl evidence/grid4x4-1-p3-4-ord3.txt`.
- Each file opens with comment lines recording the `evgen.sh` settings that made
  it, with paths relative to `SimpleGrid/`: run `evgen.sh` with those settings
  from `SimpleGrid/` to regenerate it exactly.

## TwoPackage

Harder plan-recognition problems in the same domain, made the same way
(`TwoPackage/make-instances.sh N`).

**Problems** — `gridNxN-K.pddl`, N = 3..7, four per size.  An N×N grid with no
airports, one truck and two packages, all placed at random.  Each package has
two possible destinations, never its own starting place (the two packages may
share one).  The goal is that **at least one** package reaches one of its
destinations (`ppgen.sh --require some`), so the goal is a disjunction of four
literals `(at pkgI <place>)` — the recognition hypotheses.  The truck must
drive to a package, load it, drive on and unload it, so plans include `load`
and `unload` actions, not just drives.

**`goals/`** — one entry per goal literal: `<problem>-<pkg>-<place>.pddl`
narrows the goal to `(at <pkg> <place>)`, and `.answer` is a shortest plan for
it.  Loads and unloads cost nothing, so a cost-minimising planner may leave in a
pointless load of the *other* package; `-clean.answer` is the same plan without
any load or unload of the other package (still a valid plan), and the evidence
is taken from it.

**`evidence/`** — as for SimpleGrid, the first `N` actions of the cleaned plan,
now any of `drive`, `load` and `unload`, for N = 1 up to the smaller of
gridsize − 2 and the plan's length.  The true goal of
`<problem>-<pkg>-<place>-obsN.txt` is the hypothesis `at-<pkg>-<place>`, e.g.
`recognize.sh clara-logistics.pddl grid4x4-1.pddl evidence/grid4x4-1-pkg1-p2-3-obs2.txt --evidence-kind fifo`.
