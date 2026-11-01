"""fpcommon.py -- shared by the FourPackage scripts: problem parsing, horizons, paths.

The shortest plan for one goal (at P D) is known exactly from the road map.
Some truck T must drive to P's start, load it, drive to D and unload it: at least
dist(T, P) + dist(P, D) drives plus 2 handling actions.  A truck's actions are
serial in SatPlan's encoding (its drive deletes the (at T loc) its load needs, so
the two are mutex at one slice), and handing P from one truck to another only adds
a load and an unload without shortening P's road distance.  So the shortest plan
has min_T dist(T, P) + dist(P, D) + 2 actions, i.e. one more time slice than that,
and a single truck achieves it.  goal_horizon() returns it; the planner is then
run at exactly that horizon (--numslices), not made to instantiate and SAT-check
every shorter one first.
"""
import collections, functools, os, re, shutil

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
HERE = os.path.dirname(SCRIPTS)    # the FourPackage dataset: problems, evidence, results
DOMAIN = os.path.join(HERE, "clara-logistics-handling.pddl")
KS = (2, 4, 8)                 # evidence lengths
SHIMS = os.path.join(SCRIPTS, "shims")
# Root of every script's scratch directories.  Its path must contain no "." (FiFO
# derives a .satout name from the first dot) and is matched by pkill -f to reap
# solvers that escape their process group.
SCRATCH = os.environ.get("FP_SCRATCH", "/tmp/fourpackage")


@functools.lru_cache(maxsize=None)
def encoding(lisp=None):
    """The SatPlan interfering-action mutex encoding of the FiFO in LISP (default
    $FIFO_LISP, else the installed ~/lib/fifo/lisp -- the one FiFO's scripts use):
    "mutex" when its satplan.wff states them with MUTEX (linear when smaller), else
    "pairs" (one clause per pair, the original)."""
    lisp = lisp or os.environ.get("FIFO_LISP") or os.path.expanduser("~/lib/fifo/lisp")
    return "mutex" if "(mutex" in open(os.path.join(lisp, "satplan.wff")).read() else "pairs"


def predicted_clauses(n, H, enc=None):
    """A theory's size at grid n x n and horizon H, for the mutex encoding ENC
    (default: the installed FiFO's).  "pairs", fitted to the recognition theories
    of 6x6..11x11 (results/formats.jsonl): about 25,500 clauses per slice at 6x6,
    growing as n^4 -- the interfering-action pairs of (in pkg truck) dominate.
    "mutex", fitted to the linear general theories of 6x6..10x10
    (results/encodings.jsonl: clauses / slice / n^2 = 202..212) and the 6x6-2
    recognition theory (217): about 220 n^2 per slice.  SBCL needs about 1 GB of
    heap per million clauses held."""
    if (enc or encoding()) == "mutex":
        return 220 * n * n * H
    return 25500 * (n / 6) ** 4 * H


def env(heap_mb=None):
    """The environment every FiFO run gets: shims/sbcl first on PATH (SBCL's
    default 1 GB heap is too small for these theories).  The heap is reserved, not
    allocated: $FP_HEAP_MB, default 12 GB."""
    heap_mb = heap_mb or int(os.environ.get("FP_HEAP_MB", 12288))
    return dict(os.environ, PATH=SHIMS + ":" + os.environ["PATH"],
                SBCL_REAL=shutil.which("sbcl", path=os.environ["PATH"]),
                SBCL_HEAP_MB=str(heap_mb))


def problems(sizes=None):
    out = []
    for f in os.listdir(HERE):
        m = re.fullmatch(r"grid(\d+)x\1-(\d+)\.pddl", f)
        if m and (not sizes or int(m.group(1)) in sizes):
            out.append((int(m.group(1)), int(m.group(2)), f[:-5]))
    return [name for _, _, name in sorted(out)]


def size_of(name):
    return int(re.match(r"grid(\d+)x", name).group(1))


def parse(path):
    """Roads, starting places and goal literals of a ppgen problem."""
    text = open(path).read()
    roads = collections.defaultdict(set)
    for a, b in re.findall(r"\(road (\S+) (\S+)\)", text):
        roads[a].add(b)
    init = text[text.index("(:init"):text.index("(:goal")]
    at = dict(re.findall(r"\(at (\S+) (\S+)\)", init))
    goal = text[text.index("(:goal"):]
    disj = re.search(r"\(or ((?:\(at \S+ \S+\)\s*)+)\)", goal).group(1)
    goals = re.findall(r"\(at (\S+) (\S+)\)", disj)
    return roads, at, goals


def distances(roads, src):
    d = {src: 0}
    q = collections.deque([src])
    while q:
        u = q.popleft()
        for v in roads[u]:
            if v not in d:
                d[v] = d[u] + 1
                q.append(v)
    return d


def goal_horizon(roads, at, pkg, dest):
    start = at[pkg]
    from_pkg = distances(roads, start)
    trucks = [o for o in at if o.startswith("truck")]
    reach = min(distances(roads, at[t])[start] for t in trucks)
    return reach + from_pkg[dest] + 2 + 1


def horizons(path):
    """{(pkg, dest): shortest horizon} for every goal literal of the problem."""
    roads, at, goals = parse(path)
    return {(p, d): goal_horizon(roads, at, p, d) for p, d in goals}


def recognition_horizon(path):
    """One horizon for every recognition run of a problem: every hypothesis must
    be reachable (the largest goal horizon) and every evidence set must fit (8
    observed actions need 9 slices)."""
    return max(max(horizons(path).values()), max(KS) + 1)


def goal_name(problem, pkg, dest):
    return f"{problem}-{pkg}-{dest}"
