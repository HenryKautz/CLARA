"""common.py -- shared by the CLARA benchmark scripts in this directory.

The grid benchmarks (SimpleGrid, TwoPackage, TwoPackageOneway, ThreePackage,
FourPackage) were regenerated on 2026-10-31/11-01 with one set of scripts: this module holds the
family table, problem/goal/hypothesis parsing, paths, the environment FiFO runs
in, and the process runner with the stop-at-first-failure rule that every stage
shares.

A FAMILY is a directory CLARA/<Family>/ holding:
  gridNxN-K.pddl            the problems (ppgen.sh), domain clara-logistics.pddl
  goals/<goal>.pddl         one per hypothesis: the problem with that hypothesis
                            as its hard goal
  goals/<goal>.answer       the plan the evidence is cut from
  recognition/gridNxN-K.pddl  the problem whose goal is the disjunction of the
                            hypotheses, with its recognition horizon in the header
  evidence/                 pinned observations
  results/*.jsonl           one JSON record per run
"""
import itertools, json, math, os, re, shutil, signal, subprocess, sys, threading, time

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
CLARA = os.path.dirname(SCRIPTS)
OLD = os.path.join(CLARA, "OldVersions")
SHIMS = os.path.join(SCRIPTS, "shims")

# sizes and how the goal is split into hypotheses, per family.  "literals": the
# goal is (or l1 ... ln) and each literal is a hypothesis; "combos": the goal is
# (and (or ...) (or ...) ...) and each choice of one literal per disjunction is a
# hypothesis (ThreePackage: 2^3 = 8).
#
# How make-problems.py makes a family from OldVersions/<source>: it replays each
# old problem's recorded ppgen settings, dropping the flags in "drop" and
# appending those in "add".  "same_world": the result must have exactly the old
# problem's objects, :init and goal literals (checked), so the old plans'
# horizons are valid hints for plan-goals.py; False when the roads change
# (knockout dropped, one-way roads added), which can move the starts and
# destinations too.
FAMILIES = {
    "SimpleGrid":   dict(sizes=list(range(3, 11)), kind="literals", source="SimpleGrid",
                         drop=(), add=(), same_world=True),
    "TwoPackage":   dict(sizes=list(range(3, 8)),  kind="literals", source="TwoPackage",
                         drop=(), add=(), same_world=True),
    # 2026-11-01: ThreePackage and FourPackage remade without --knockout (the
    # full grid of two-way roads); TwoPackageOneway is TwoPackage with 25% of
    # the roads one-way
    "TwoPackageOneway": dict(sizes=list(range(3, 8)), kind="literals", source="TwoPackage",
                             drop=(), add=(("--oneway", ["25"]),), same_world=False),
    "ThreePackage": dict(sizes=[5, 6, 7],          kind="combos", source="ThreePackage",
                         drop=("--knockout",), add=(), same_world=False),
    "FourPackage":  dict(sizes=list(range(6, 16)), kind="literals", source="FourPackage",
                         drop=("--knockout",), add=(), same_world=False),
}
DOMAIN_NAME = "clara-logistics"
EVIDENCE_FRACTIONS = (25, 100)     # percent of the plan's actions; plus "none"

TT = "tt-open-wbo-inc-Glucose4_1"
EVAL = "EvalMaxSAT_bin"
METHODS = ("max-term", "sharpsat-td", "mc-sat")


class Family:
    def __init__(self, name):
        if name not in FAMILIES:
            sys.exit(f"unknown family {name}; one of {', '.join(FAMILIES)}")
        self.name = name
        self.sizes = FAMILIES[name]["sizes"]
        self.kind = FAMILIES[name]["kind"]
        self.drop = FAMILIES[name]["drop"]
        self.add = FAMILIES[name]["add"]
        self.same_world = FAMILIES[name]["same_world"]
        self.dir = os.path.join(CLARA, name)
        self.old = os.path.join(OLD, FAMILIES[name]["source"])
        self.domain = os.path.join(self.dir, DOMAIN_NAME + ".pddl")
        self.results = os.path.join(self.dir, "results")
        # scratch: its path must contain no "." (FiFO derives .satout from the
        # first dot); runs are killed by pkill -f on their directory under it
        base = os.environ.get("CLARA_SCRATCH") or os.path.join(os.environ.get("TMPDIR", "/tmp"), "clara")
        self.scratch = os.path.join(base, name.lower())
        assert "." not in self.scratch, self.scratch

    def path(self, *p):
        return os.path.join(self.dir, *p)

    def problems(self, sizes=None):
        out = []
        for f in os.listdir(self.dir):
            m = re.fullmatch(r"grid(\d+)x\1-(\d+)\.pddl", f)
            if m and (not sizes or int(m.group(1)) in sizes):
                out.append((int(m.group(1)), int(m.group(2)), f[:-5]))
        return [n for _, _, n in sorted(out)]

    def hypotheses(self, problem):
        """[Hyp] of PROBLEM, in recognize.sh's order."""
        return hypotheses(self.path(problem + ".pddl"), problem, self.kind)

    def recognition_problem(self, problem):
        return self.path("recognition", problem + ".pddl")

    def recognition_horizon(self, problem):
        m = re.search(r"^;; Recognition horizon: (\d+)",
                      open(self.recognition_problem(problem)).read(), re.M)
        return int(m.group(1))

    def load(self, fname):
        return load_jsonl(os.path.join(self.results, fname))


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def append_jsonl(path, rec):
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")


def size_of(name):
    return int(re.match(r"grid(\d+)x", name).group(1))


def problem_of(name):
    return re.match(r"grid\d+x\d+-\d+", name).group(0)


# --- goals and hypotheses ----------------------------------------------------

class Hyp:
    """One hypothesis: its index, recognize.sh's name for it, its literals
    [(obj, place)] (all (at obj place)), and its goal-variant name."""
    def __init__(self, index, name, lits, goal):
        self.index, self.name, self.lits, self.goal = index, name, lits, goal

    def formula(self):
        ls = [f"(at {o} {p})" for o, p in self.lits]
        return ls[0] if len(ls) == 1 else "(and " + " ".join(ls) + ")"

    def __repr__(self):
        return f"Hyp({self.index}, {self.name}, {self.formula()})"


def goal_text(path):
    text = open(path).read()
    return text[text.index("(:goal"):text.index("(:metric")]


def hypotheses(path, problem, kind):
    goal = goal_text(path)
    if kind == "literals":
        ors = re.findall(r"\(or ((?:\(at [^\s()]+ [^\s()]+\)\s*)+)\)", goal)
        assert len(ors) == 1, f"{path}: expected one (or ...) of literals"
        lits = re.findall(r"\(at ([^\s()]+) ([^\s()]+)\)", ors[0])
        return [Hyp(i, f"at-{o}-{p}", [(o, p)], f"{problem}-{o}-{p}")
                for i, (o, p) in enumerate(lits)]
    groups = []
    for body in re.findall(r"\(or ((?:\(at [^\s()]+ [^\s()]+\)\s*)+)\)", goal):
        groups.append(re.findall(r"\(at ([^\s()]+) ([^\s()]+)\)", body))
    out = []
    for i, combo in enumerate(itertools.product(*groups)):
        out.append(Hyp(i, f"rechyp{i}", list(combo),
                       problem + "-" + "-".join(f"{o}-{p}" for o, p in combo)))
    return out


def with_goal(src, new_name, header, goal_lines):
    """SRC's problem text renamed NEW_NAME, its comment header replaced by
    HEADER, and its (:goal ...) by GOAL_LINES."""
    text = open(src).read()
    body = text[text.index("(define (problem "):]
    body = re.sub(r"^\(define \(problem \S+\)", f"(define (problem {new_name})", body, count=1)
    g, m = body.index("  (:goal"), body.index("  (:metric")
    body = body[:g] + "\n".join(goal_lines) + "\n\n" + body[m:]
    return "\n".join(";; " + h if h else ";;" for h in header) + "\n\n" + body


def goal_problem_text(fam, problem, hyp):
    header = [hyp.goal,
              f"Single-goal variant of {fam.name}/{problem}.pddl: the hard goal is",
              f"{hyp.formula()} -- hypothesis {hyp.name} of the recognition problem.",
              "No preferences or weights.  Written by scripts/make-problems.py."]
    if len(hyp.lits) == 1:
        goal = [f"  (:goal {hyp.formula()})"]
    else:
        goal = ["  (:goal (and"] + [f"        (at {o} {p})" for o, p in hyp.lits[:-1]] + \
               [f"        (at {hyp.lits[-1][0]} {hyp.lits[-1][1]})))"]
    return with_goal(fam.path(problem + ".pddl"), hyp.goal, header, goal)


def recognition_text(fam, problem, horizon, horizons, hyps):
    header = [f"{problem}: the recognition problem",
              f"{fam.name}/{problem}.pddl with its goal written as ONE disjunction of its",
              f"{len(hyps)} hypotheses (the same set of plans).  recognize.sh's names:"]
    for h in hyps:
        header.append(f"  {h.name:16s} {h.formula()}   shortest horizon {horizons[h.goal]}")
    header += [f"Recognition horizon: {horizon}",
               "  (the largest shortest horizon: every hypothesis is achievable at it)",
               "Written by scripts/plan-goals.py."]
    goal = ["  (:goal (or"]
    for i, h in enumerate(hyps):
        goal.append("        " + h.formula() + ("))" if i == len(hyps) - 1 else ""))
    return with_goal(fam.path(problem + ".pddl"), problem, header, goal)


def plan_actions(answer):
    """[(slice, action)] of an answer file's OCCURS lines in time order (ties in
    file order), lower case."""
    acts = []
    for line in open(answer):
        m = re.match(r"\(OCCURS (\(.*\)) (\d+)\)\s*$", line)
        if m:
            acts.append((int(m.group(2)), m.group(1).lower()))
    return sorted(acts, key=lambda a: a[0])


def answer_horizon(answer):
    """The number of time slices of a plan: its largest HOLDS slice."""
    hs = [int(m.group(1)) for m in re.finditer(r"^\(HOLDS .* (\d+)\)\s*$", open(answer).read(), re.M)]
    return max(hs) if hs else None


def evidence_count(n_actions, pct):
    return max(1, math.ceil(n_actions * pct / 100))


# --- the environment and processes -------------------------------------------

def env(heap_mb=None, extra=None):
    """shims/sbcl first on PATH, with an SBCL heap of $CLARA_HEAP_MB (default
    16 GB, reserved, not allocated)."""
    heap_mb = heap_mb or int(os.environ.get("CLARA_HEAP_MB", 16384))
    path = os.environ["PATH"].split(os.pathsep)
    real = shutil.which("sbcl", path=os.pathsep.join(p for p in path if p != SHIMS))
    e = dict(os.environ, PATH=SHIMS + os.pathsep + os.environ["PATH"],
             SBCL_REAL=real, SBCL_HEAP_MB=str(heap_mb))
    if extra:
        e.update(extra)
    return e


def _cgroup_dir():
    try:
        for line in open("/proc/self/cgroup"):
            parts = line.strip().split(":", 2)
            if parts[0] == "0":
                return "/sys/fs/cgroup" + parts[2]
            if "memory" in parts[1].split(","):
                return "/sys/fs/cgroup/memory" + parts[2]
    except OSError:
        pass
    return None


def available_bytes():
    """Memory still available to this job: the smaller of the machine's
    MemAvailable and what is left under the (Slurm) cgroup's limit."""
    with open("/proc/meminfo") as f:
        avail = int(re.search(r"^MemAvailable:\s+(\d+) kB", f.read(), re.M).group(1)) * 1024
    d = _cgroup_dir()
    if d:
        # walk up: the limit may be set on a parent (the job, not the step)
        while d.startswith("/sys/fs/cgroup") and len(d) > len("/sys/fs/cgroup"):
            for lim, cur in (("memory.max", "memory.current"),
                             ("memory.limit_in_bytes", "memory.usage_in_bytes")):
                try:
                    mx = open(os.path.join(d, lim)).read().strip()
                    cu = int(open(os.path.join(d, cur)).read().strip())
                except OSError:
                    continue
                if mx != "max" and int(mx) < 2**60:
                    avail = min(avail, int(mx) - cu)
            d = os.path.dirname(d)
    return avail


def process_table():
    """{pid: (ppid, rss_kb, comm)}"""
    out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,rss=,comm="],
                         capture_output=True, text=True).stdout
    t = {}
    for line in out.split("\n"):
        f = line.split(None, 3)
        if len(f) == 4:
            t[int(f[0])] = (int(f[1]), int(f[2]), f[3])
    return t


def descendants(pid, table=None):
    table = table or process_table()
    kids = {}
    for p, (pp, _r, _c) in table.items():
        kids.setdefault(pp, []).append(p)
    found, todo = [], [pid]
    while todo:
        for c in kids.get(todo.pop(), []):
            found.append(c)
            todo.append(c)
    return found


def tree_rss_kb(pid, table):
    return sum(table[p][1] for p in [pid] + descendants(pid, table) if p in table)


MEMOUT_PATTERNS = ("Heap exhausted", "heap exhausted", "bad_alloc", "out of memory",
                   "Out of memory", "Cannot allocate memory", "MemoryError",
                   "Can't handle sig11", "exhausted during garbage collection")


class Run:
    """A subprocess in its own session, in its own work directory, with a wall
    limit.  status after it ends: ok, failed, timeout, memout, killed."""

    def __init__(self, task, cmd, cwd, limit, env_=None, log=None):
        self.task, self.cwd, self.limit = task, cwd, limit
        self.log_path = log or os.path.join(cwd, "run.log")
        self.logf = open(self.log_path, "w")
        self.t0 = time.monotonic()
        self.started = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.proc = subprocess.Popen(cmd, cwd=cwd, stdout=self.logf, stderr=subprocess.STDOUT,
                                     start_new_session=True, env=env_ or env())
        self.rusage = None
        self.wall = None
        self.peak_kb = 0
        # the waiter notes the exact moment the process ends, so wall times do
        # not depend on how often the caller polls
        self._waiter = threading.Thread(target=self._wait, daemon=True)
        self._waiter.start()

    def _wait(self):
        pid, status, ru = os.wait4(self.proc.pid, 0)
        self.wall = time.monotonic() - self.t0
        self.proc.returncode = os.waitstatus_to_exitcode(status)
        self.rusage = ru

    def poll(self):
        if self.rusage is not None:
            if not self.logf.closed:
                self.logf.close()
            return True
        return False

    def over(self):
        return time.monotonic() - self.t0 > self.limit

    def kill(self):
        pids = [self.proc.pid] + descendants(self.proc.pid)
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for p in pids:
                try:
                    os.kill(p, sig)
                except ProcessLookupError:
                    pass
            if sig == signal.SIGTERM:
                time.sleep(3)
                pids += descendants(self.proc.pid)
        # a solver FiFO started in a process group of its own and orphaned: it is
        # still in the run's session (start_new_session: sid = the run's pid), and
        # its command line may name a file in the run's directory
        subprocess.run(["pkill", "-KILL", "-s", str(self.proc.pid)])
        subprocess.run(["pkill", "-KILL", "-f", self.cwd.rstrip("/") + "/"])
        self._waiter.join()
        if not self.logf.closed:
            self.logf.close()

    def output(self):
        try:
            return open(self.log_path, errors="replace").read()
        except OSError:
            return ""

    def classify(self):
        """ok / failed / memout for a run that ended by itself."""
        if self.proc.returncode == 0:
            return "ok"
        out = self.output()
        if any(p in out for p in MEMOUT_PATTERNS) or self.proc.returncode in (-9, 137):
            return "memout"
        return "failed"

    def base_record(self):
        ru = self.rusage
        return dict(limit_s=self.limit, wall_s=round(self.wall, 2),
                    cpu_s=round(ru.ru_utime + ru.ru_stime, 2) if ru else None,
                    exit_code=self.proc.returncode, started=self.started,
                    peak_rss_mb=round(self.peak_kb / 1024))


def log_tail(text, n=12):
    return text.strip().split("\n")[-n:]


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def say(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)
