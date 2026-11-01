"""tpcommon.py -- shared by the ThreePackage scripts: paths, problem parsing, the
goal combinations (hypotheses) and the recognition horizon.

A ThreePackage goal is a conjunction of one binary disjunction per package.  A
HYPOTHESIS is one combination: a destination for each package, so 2^3 = 8 per
problem, in itertools.product order over the goal's disjunctions as written.
recognition/NAME.pddl states the goal in that order as
    (or (and (at pkg1 a) (at pkg2 c) (at pkg3 e)) (and ...) ...)
-- the same set of plans -- and recognize.sh scores the I-th disjunct through a
derived atom it names rechypI (lisp/recognition-goal.lisp), so combination I is
hypothesis rechypI.
"""
import itertools, json, os, re, shutil

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
HERE = os.path.dirname(SCRIPTS)    # the ThreePackage dataset
DOMAIN = os.path.join(HERE, "clara-logistics-handling.pddl")
KS = (4, 8)                        # evidence lengths: the plan's first K actions
SIZES = (5, 6, 7)
SHIMS = os.path.join(SCRIPTS, "shims")
RESULTS = os.path.join(HERE, "results")
# Root of the scripts' scratch directories.  Its path must contain no "." (FiFO
# derives a .satout name from the first dot); pkill -f matches it to reap solvers
# that escape their process group.
SCRATCH = os.environ.get("TP_SCRATCH", "/tmp/threepackage")


def env(heap_mb=None):
    """The environment every FiFO run gets: shims/sbcl first on PATH, with an SBCL
    heap of $TP_HEAP_MB (default 8 GB, reserved, not allocated)."""
    heap_mb = heap_mb or int(os.environ.get("TP_HEAP_MB", 8192))
    path = os.environ["PATH"].split(os.pathsep)
    real = shutil.which("sbcl", path=os.pathsep.join(p for p in path if p != SHIMS))
    return dict(os.environ, PATH=SHIMS + os.pathsep + os.environ["PATH"],
                SBCL_REAL=real, SBCL_HEAP_MB=str(heap_mb))


def problems(sizes=None):
    out = []
    for f in os.listdir(HERE):
        m = re.fullmatch(r"grid(\d+)x\1-(\d+)\.pddl", f)
        if m and (not sizes or int(m.group(1)) in sizes):
            out.append((int(m.group(1)), int(m.group(2)), f[:-5]))
    return [name for _, _, name in sorted(out)]


def size_of(name):
    return int(re.match(r"grid(\d+)x", name).group(1))


def problem_of(name):
    """gridNxN-K of a goal, evidence or problem name."""
    return re.match(r"grid\d+x\d+-\d+", name).group(0)


def goal_groups(path):
    """The goal's disjunctions, in order: [(pkg, [dest, dest]), ...]."""
    text = open(path).read()
    goal = text[text.index("(:goal"):]
    groups = []
    for body in re.findall(r"\(or ((?:\(at [^\s()]+ [^\s()]+\)\s*)+)\)", goal):
        lits = re.findall(r"\(at ([^\s()]+) ([^\s()]+)\)", body)
        pkgs = {p for p, _ in lits}
        assert len(pkgs) == 1, f"{path}: a disjunction names several packages: {body}"
        groups.append((lits[0][0], [d for _, d in lits]))
    return groups


def combos(path):
    """The hypotheses: [((pkg, dest), (pkg, dest), (pkg, dest)), ...], combination
    I being rechypI."""
    groups = goal_groups(path)
    return [tuple(zip([p for p, _ in groups], ds))
            for ds in itertools.product(*[d for _, d in groups])]


def combo_name(problem, combo):
    return problem + "-" + "-".join(f"{p}-{d}" for p, d in combo)


def hypothesis(i):
    return f"rechyp{i}"


def recognition_problem(name):
    return os.path.join(HERE, "recognition", name + ".pddl")


def recognition_horizon(name):
    """The horizon written into recognition/NAME.pddl by plan-goals.py."""
    m = re.search(r"^;; Recognition horizon: (\d+)", open(recognition_problem(name)).read(), re.M)
    return int(m.group(1))


def load(fname):
    path = os.path.join(RESULTS, fname)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]
