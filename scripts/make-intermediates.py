#!/usr/bin/env python3
"""make-intermediates.py --family F [--jobs N] [--sizes ...] [--survey]

Keep the files between each planning problem's PDDL and its plan, which the
pipeline made in scratch directories and threw away -- TRANSLATION AND
INSTANTIATION ONLY: no SAT, MaxSAT or model-counting solver runs.  Every
horizon is the one the existing plans were found at (GENERATE-INTERMEDIATES.md).

For each planning problem P of family F -- the originals F/gridNxN-K.pddl
(results/originals.jsonl) and the goal problems F/goals/<goal>.pddl
(results/plans.jsonl) -- and each distinct horizon H of its eval/tt plans:

  <dir>/intermediates/P.wff        planner.sh P.pddl --domain F/clara-logistics.pddl
                                   --stop-after wff
  <dir>/intermediates/P-H<H>.scnf  planner.sh P.pddl --domain ... --numslices H
                                   --stop-after scnf
  <dir>/intermediates/P-H<H>.wcnf  (propositionalize "P.scnf" :cnffile ... :mapfile ...
  <dir>/intermediates/P-H<H>.map    :cnf-format 'wcnf)   (2022 'h' format)

<dir> is F for the originals and F/goals for the goal problems.  The kept .wff
includes "satplan.wff", a copy of FiFO's lisp/satplan.wff put in each
intermediates directory (planner.sh's include names the scratch directory's
relative path to it, and FiFO resolves an include against the .wff's own
directory), so instantiating it at H gives the kept .scnf.  A problem with
no plan gets its .wff only.  Missing recognition theories F/scnf/<p>.scnf are
made as compile-d4.py's prepare() makes them (recognize.sh --stop-after scnf);
an existing one is never overwritten, but --verify-rec of them are regenerated
in scratch and compared byte for byte.

The horizon of a plan is the "horizon" of the LAST record of its name and stage
(eval / tt) when that record is ok; it must equal the plan file's highest
OCCURS/HOLDS slice, and a plan file must exist exactly when the record is ok.
Any disagreement stops the run before anything is generated.

Nothing can be solved by accident: $CLARA_STUBS must be a directory of
stand-ins for every solver name in FiFO's solvers.dat (each prints "SOLVER
CALLED: <name>" to stderr and to $CLARA_STUB_TRACE, set to each run's log, and
exits 99), and it is put FIRST on PATH; every name is checked to resolve to it
before starting, and every log is checked for "SOLVER CALLED".

Checks per instantiated horizon: the .wff is the clara-logistics translation
(never clara-logistics-old); every action of the plan(s) at that horizon is an
OCCURS atom of the .map at its slice; the .wcnf's largest variable equals the
.map's entry count, and its hard ('h') and soft clause counts equal the .scnf's
(OR ...) and (WEIGHT ...) forms.

Records: F/results/intermediates.jsonl (one per job).  A job whose outputs all
exist is not run again.  The .scnf, .wcnf and .map are committed gzipped (gzip
-k -n, run afterwards; the raw files are git-ignored), so a fresh clone needs
gunzip -k, or this script remakes them.  Logs: $CLARA_SCRATCH/<family>/intermediates/logs.
"""
import argparse, glob, os, re, shutil, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import common as C

ap = argparse.ArgumentParser()
ap.add_argument("--family", required=True)
ap.add_argument("--jobs", type=int, default=8)
ap.add_argument("--sizes", type=int, nargs="*")
ap.add_argument("--heap-mb", type=int, default=65536, help="SBCL heap per run (reserved)")
ap.add_argument("--limit", type=float, default=12 * 3600, help="wall seconds per command")
ap.add_argument("--verify-rec", type=int, default=2,
                help="existing recognition theories to regenerate and compare")
ap.add_argument("--survey", action="store_true", help="list the jobs and stop")
A = ap.parse_args()

FAM = C.Family(A.family)
SIZES = A.sizes or FAM.sizes
STUBS = os.environ.get("CLARA_STUBS")
FIFO_LISP = os.environ.get("FIFO_LISP") or os.path.expanduser("~/lib/fifo/lisp")
RECORDS = os.path.join(FAM.results, "intermediates.jsonl")
WORK = os.path.join(FAM.scratch, "intermediates")
LOGS = os.path.join(WORK, "logs")
LOCK = threading.Lock()


# --- what to make -------------------------------------------------------------

def last_records(path):
    last = {}
    for r in C.load_jsonl(path):
        if r.get("stage") in ("eval", "tt"):
            last[(r["name"], r["stage"])] = r
    return last


def plan_slices(answer):
    """(highest OCCURS/HOLDS slice, [(OCCURS ...) atom text])"""
    hi, acts = 0, []
    for line in open(answer):
        m = re.match(r"\((OCCURS|HOLDS) (.*) (\d+)\)\s*$", line)
        if m:
            hi = max(hi, int(m.group(3)))
            if m.group(1) == "OCCURS":
                acts.append(line.strip())
    return hi, acts


class Problem:
    def __init__(self, kind, name, pddl, outdir, answers, last):
        self.kind, self.name, self.pddl, self.outdir = kind, name, pddl, outdir
        self.size = C.size_of(name)
        self.plans = {}          # stage -> (H, answer path)
        self.errors = []
        for stage in ("eval", "tt"):
            ans = answers[stage]
            r = last.get((name, stage))
            ok = r is not None and r.get("status") == "ok"
            if ok and not os.path.exists(ans):
                self.errors.append(f"{stage}: record ok (horizon {r.get('horizon')}) but no {ans}")
            elif not ok and os.path.exists(ans):
                self.errors.append(f"{stage}: {ans} exists but the last record is "
                                   f"{r.get('status') if r else 'missing'}")
            elif ok:
                hi, _ = plan_slices(ans)
                if hi != r["horizon"]:
                    self.errors.append(f"{stage}: record horizon {r['horizon']}, plan's highest slice {hi}")
                else:
                    self.plans[stage] = (r["horizon"], ans)

    def horizons(self):
        hs = {}
        for stage, (h, ans) in sorted(self.plans.items()):
            hs.setdefault(h, []).append((stage, ans))
        return hs


def collect():
    probs = []
    last = last_records(os.path.join(FAM.results, "originals.jsonl"))
    for p in FAM.problems(SIZES):
        probs.append(Problem("original", p, FAM.path(p + ".pddl"), FAM.path("intermediates"),
                             {s: FAM.path(f"{p}-{s}.answer") for s in ("eval", "tt")}, last))
    last = last_records(os.path.join(FAM.results, "plans.jsonl"))
    for p in FAM.problems(SIZES):
        for h in FAM.hypotheses(p):
            g = h.goal
            probs.append(Problem("goal", g, FAM.path("goals", g + ".pddl"),
                                 FAM.path("goals", "intermediates"),
                                 {s: FAM.path("goals", f"{g}-{s}.answer") for s in ("eval", "tt")}, last))
    rec_missing, rec_present = [], []
    for p in FAM.problems(SIZES):
        if os.path.exists(FAM.recognition_problem(p)):
            (rec_present if os.path.exists(FAM.path("scnf", p + ".scnf")) else rec_missing).append(p)
    return probs, rec_missing, rec_present


# --- running ------------------------------------------------------------------

def env(trace=None):
    """The stand-ins first on PATH.  They print to stderr, which FiFO may
    discard, so they also append to CLARA_STUB_TRACE: each run's own log."""
    e = C.env(heap_mb=A.heap_mb)
    e["PATH"] = STUBS + os.pathsep + e["PATH"]
    e["FIFO_LISP"] = FIFO_LISP
    if trace:
        e["CLARA_STUB_TRACE"] = trace
    return e


def check_stubs():
    if not STUBS or not os.path.isdir(STUBS):
        sys.exit("set CLARA_STUBS to the directory of stand-in solvers")
    path = env()["PATH"]
    dat = os.path.join(FIFO_LISP, "solvers.dat")
    names = set()
    for line in open(dat):
        f = line.split()
        if f and not f[0].startswith("#") and len(f) >= 4:
            names.add(f[1])
            names.update(x[6:] for x in f[3].split(",") if x.startswith("needs:"))
    names.update(["sharpSAT", "flow_cutter_pace17", "maxpre", "walksat", "d4", "addmc", "kissat"])
    bad = []
    for n in sorted(names):
        w = shutil.which(n, path=path)
        if not w or os.path.dirname(os.path.realpath(w)) != os.path.realpath(STUBS):
            bad.append(f"{n} -> {w}")
    if bad:
        sys.exit("these do not resolve to the stand-ins:\n  " + "\n  ".join(bad))
    return sorted(names)


def run(cmd, cwd, log):
    t0 = time.monotonic()
    with open(log, "a") as f:
        f.write(f"$ {' '.join(cmd)}\n")
        f.flush()
        try:
            p = subprocess.run(cmd, cwd=cwd, env=env(trace=log), stdout=f, stderr=subprocess.STDOUT,
                               timeout=A.limit, start_new_session=True)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
        f.write(f"[exit {rc}, {time.monotonic() - t0:.1f}s]\n")
    return rc, time.monotonic() - t0


def log_text(log):
    return open(log, errors="replace").read()


def publish(src, dest):
    """Copy SRC to DEST through a temporary name, so DEST exists only complete."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    shutil.copyfile(src, tmp)
    os.replace(tmp, dest)


def record(rec):
    with LOCK:
        rec["finished"] = C.now()
        C.append_jsonl(RECORDS, rec)
        extra = " ".join(f"{k}={rec[k]}" for k in ("horizon", "wall_s", "bytes") if k in rec)
        C.say(f"{rec['job']:5s} {rec['status']:7s} {rec['name']} {extra}"
              + ("" if rec["status"] == "ok" else f"  {rec.get('error', '')}"))


def scratch(tag):
    d = os.path.join(WORK, tag)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    return d


def finish_log(rec, log):
    text = log_text(log)
    rec["solver_called"] = "SOLVER CALLED" in text
    if rec["solver_called"]:
        rec["status"] = "failed"
        rec["error"] = "SOLVER CALLED in " + log
    return text


def wff_job(pb):
    dest = os.path.join(pb.outdir, pb.name + ".wff")
    rec = dict(job="wff", name=pb.name, kind=pb.kind, size=pb.size, wff=os.path.relpath(dest, FAM.dir))
    if os.path.exists(dest):
        return None
    d = scratch(f"{pb.name}-wff")
    log = os.path.join(LOGS, f"{pb.name}-wff.log")
    open(log, "w").close()
    shutil.copy(pb.pddl, d)
    rc, secs = run(["planner.sh", pb.name + ".pddl", "--domain", FAM.domain, "--stop-after", "wff"], d, log)
    rec.update(wall_s=round(secs, 1), status="ok")
    out = os.path.join(d, pb.name + ".wff")
    if rc != 0 or not os.path.exists(out):
        rec.update(status="failed", error=f"planner.sh exit {rc}")
    else:
        head = open(out).read(2000)
        m = re.search(r"^;; Domain (\S+) from", head, re.M)
        if not m or m.group(1) != C.DOMAIN_NAME:
            rec.update(status="failed", error=f"wff names domain {m.group(1) if m else '?'}")
    finish_log(rec, log)
    if rec["status"] == "ok":
        # planner.sh writes the include of satplan.wff relative to the scratch
        # directory; FiFO resolves an include against the .wff's own directory,
        # so the kept .wff includes the copy of satplan.wff beside it
        text = open(out).read()
        text, n = re.subn(r'^\(include "[^"]*satplan\.wff"\)$', '(include "satplan.wff")', text, flags=re.M)
        if n != 1:
            rec.update(status="failed", error=f"{n} satplan.wff includes, expected 1")
        else:
            open(out, "w").write(text)
            publish(out, dest)
            rec["bytes"] = os.path.getsize(dest)
    shutil.rmtree(d, ignore_errors=True)
    record(rec)
    return rec


def scnf_counts(path):
    """(OR forms, WEIGHT forms): FiFO writes every top-level form at column 0
    and continuation lines indented; anything else at column 0 is an error."""
    ors = ws = 0
    with open(path) as f:
        for line in f:
            if line.startswith("(OR"):
                ors += 1
            elif line.startswith("(WEIGHT"):
                ws += 1
            elif line.startswith(("(OPTION", ";", " ", "\t", "\n")):
                pass
            else:
                raise ValueError(f"unexpected top-level line in {path}: {line[:80]!r}")
    return ors, ws


def wcnf_counts(path):
    """(largest variable, hard clauses, soft clauses) of a 2022-format WCNF."""
    hi = hard = soft = 0
    with open(path) as f:
        for line in f:
            if not line or line[0] == "c" or line == "\n":
                continue
            t = line.split()
            if t[0] == "h":
                hard += 1
            else:
                soft += 1
            assert t[-1] == "0", line
            for x in t[1:-1]:
                v = abs(int(x))
                if v > hi:
                    hi = v
    return hi, hard, soft


def map_atoms(path):
    """(declared count, {atom text}) of a .map: 'map N' then 'i atom' lines."""
    atoms, n = set(), None
    with open(path) as f:
        first = f.readline().split()
        assert first[0] == "map", first
        n = int(first[1])
        for line in f:
            i, atom = line.rstrip("\n").split(" ", 1)
            atoms.add(atom)
    return n, atoms


def scnf_job(pb, h, plans):
    base = os.path.join(pb.outdir, f"{pb.name}-H{h}")
    outs = {x: f"{base}.{x}" for x in ("scnf", "wcnf", "map")}
    if all(os.path.exists(p) for p in outs.values()):
        return None
    rec = dict(job="scnf", name=pb.name, kind=pb.kind, size=pb.size, horizon=h,
               plans=[s for s, _ in plans], files=[os.path.relpath(p, FAM.dir) for p in outs.values()])
    d = scratch(f"{pb.name}-H{h}")
    log = os.path.join(LOGS, f"{pb.name}-H{h}.log")
    open(log, "w").close()
    shutil.copy(pb.pddl, d)
    t0 = time.monotonic()
    rc, _ = run(["planner.sh", pb.name + ".pddl", "--domain", FAM.domain,
                 "--numslices", str(h), "--stop-after", "scnf"], d, log)
    scnf = os.path.join(d, pb.name + ".scnf")
    wcnf, mp = os.path.join(d, f"{pb.name}-H{h}.wcnf"), os.path.join(d, f"{pb.name}-H{h}.map")
    rec["status"] = "ok"
    if rc != 0 or not os.path.exists(scnf) or f"at {h} time slices" not in log_text(log):
        rec.update(status="failed", error=f"planner.sh exit {rc}")
    else:
        lisp = os.path.join(FIFO_LISP, "FiFO.lisp")
        rc, _ = run(["sbcl", "--non-interactive", "--eval", f'(load "{lisp}")', "--eval",
                     f'(propositionalize "{pb.name}.scnf" :cnffile "{os.path.basename(wcnf)}"'
                     f' :mapfile "{os.path.basename(mp)}" :cnf-format (quote wcnf))'], d, log)
        if rc != 0 or not (os.path.exists(wcnf) and os.path.exists(mp)):
            rec.update(status="failed", error=f"propositionalize exit {rc}")
    rec["wall_s"] = round(time.monotonic() - t0, 1)
    if rec["status"] == "ok":
        try:
            ors, ws = scnf_counts(scnf)
            hi, hard, soft = wcnf_counts(wcnf)
            n, atoms = map_atoms(mp)
            rec.update(scnf_or=ors, scnf_weight=ws, wcnf_vars=hi, wcnf_hard=hard, wcnf_soft=soft,
                       map_entries=n, map_lines=len(atoms))
            errs = []
            if not (hi == n == len(atoms)):
                errs.append(f"wcnf largest var {hi}, map declares {n}, has {len(atoms)}")
            if (hard, soft) != (ors, ws):
                errs.append(f"wcnf hard/soft {hard}/{soft}, scnf OR/WEIGHT {ors}/{ws}")
            for stage, ans in plans:
                _, acts = plan_slices(ans)
                missing = [a for a in acts if a not in atoms]
                rec[f"{stage}_actions"] = len(acts)
                if missing:
                    errs.append(f"{stage} plan actions not in map: {missing[:3]} ({len(missing)})")
            if errs:
                rec.update(status="failed", error="; ".join(errs))
        except Exception as e:                      # a malformed file is a failure, not a crash
            rec.update(status="failed", error=f"check: {e}")
    finish_log(rec, log)
    if rec["status"] == "ok":
        publish(scnf, outs["scnf"])
        publish(wcnf, outs["wcnf"])
        publish(mp, outs["map"])
        rec["bytes"] = sum(os.path.getsize(p) for p in outs.values())
    shutil.rmtree(d, ignore_errors=True)
    record(rec)
    return rec


def rec_job(p, verify):
    dest = FAM.path("scnf", p + ".scnf")
    if not verify and os.path.exists(dest):
        return None
    d = scratch(f"{p}-rec")
    out = os.path.join(d, "rec")
    os.makedirs(out)
    log = os.path.join(LOGS, f"{p}-rec{'-verify' if verify else ''}.log")
    open(log, "w").close()
    h = FAM.recognition_horizon(p)
    rec = dict(job="verify" if verify else "rec", name=p, kind="recognition", size=C.size_of(p),
               horizon=h, status="ok")
    t0 = time.monotonic()
    rc, _ = run(["bash", shutil.which("recognize.sh", path=env()["PATH"]), FAM.domain,
                 FAM.recognition_problem(p), FAM.path("evidence", p + "-none.txt"),
                 "--evidence-kind", "fifo", "--stop-after", "scnf", "--out", out,
                 "--horizon", str(h), "--planner-timeout", "none"], d, log)
    rec["wall_s"] = round(time.monotonic() - t0, 1)
    made = os.path.join(out, "rec-problem.scnf")
    m = re.search(r"^Horizon H = (\d+)", log_text(log), re.M)
    if rc != 0 or not os.path.exists(made):
        rec.update(status="failed", error=f"recognize.sh exit {rc}")
    elif not m or int(m.group(1)) != h:
        rec.update(status="failed", error=f"recognize.sh horizon {m.group(1) if m else '?'}, header {h}")
    finish_log(rec, log)
    if rec["status"] == "ok":
        if verify:
            same = open(made, "rb").read() == open(dest, "rb").read()
            rec["identical"] = same
            if not same:
                rec.update(status="differs", error=f"regenerated {p}.scnf differs from scnf/{p}.scnf")
        else:
            publish(made, dest)
            rec["bytes"] = os.path.getsize(dest)
    shutil.rmtree(d, ignore_errors=True)
    record(rec)
    return rec


def main():
    names = check_stubs()
    probs, rec_missing, rec_present = collect()
    errors = [(pb.kind, pb.name, e) for pb in probs for e in pb.errors]
    jobs = []        # (cost estimate, kind, args)
    for pb in probs:
        jobs.append((0, "wff", (pb,)))
        for h, plans in pb.horizons().items():
            jobs.append((pb.size ** 2 * h, "scnf", (pb, h, plans)))
    for p in rec_missing:
        jobs.append((C.size_of(p) ** 2 * FAM.recognition_horizon(p), "rec", (p, False)))
    for p in rec_present[:A.verify_rec]:
        jobs.append((C.size_of(p) ** 2 * FAM.recognition_horizon(p), "rec", (p, True)))
    nplan = sum(1 for pb in probs if pb.plans)
    C.say(f"{FAM.name}: {len(probs)} planning problems ({nplan} with a plan), "
          f"{sum(1 for j in jobs if j[1] == 'scnf')} horizons to instantiate, "
          f"{len(rec_missing)} recognition theories missing, {min(A.verify_rec, len(rec_present))} to verify; "
          f"stand-ins for {len(names)} names in {STUBS}")
    hs = [j[2][1] for j in jobs if j[1] == "scnf"]
    if hs:
        C.say(f"  horizons {min(hs)}..{max(hs)}; no plan: "
              f"{', '.join(pb.name for pb in probs if not pb.plans) or 'none'}")
    two = [pb.name for pb in probs if len(pb.horizons()) > 1]
    C.say(f"  eval and tt at different horizons: {len(two)} {' '.join(two[:20])}")
    if errors:
        for e in errors:
            C.say("  DISAGREE", *e)
        sys.exit(f"{len(errors)} plan/record disagreements: stopping before generating anything")
    if A.survey:
        return
    os.makedirs(LOGS, exist_ok=True)
    os.makedirs(FAM.results, exist_ok=True)
    for d in {pb.outdir for pb in probs}:
        publish(os.path.join(FIFO_LISP, "satplan.wff"), os.path.join(d, "satplan.wff"))
    jobs.sort(key=lambda j: j[0])
    fns = {"wff": wff_job, "scnf": scnf_job, "rec": rec_job}
    failed = 0
    with ThreadPoolExecutor(A.jobs) as ex:
        futs = [ex.submit(fns[k], *args) for _, k, args in jobs]
        for f in as_completed(futs):
            try:
                r = f.result()
            except Exception as e:
                C.say("CRASH", repr(e))
                failed += 1
                continue
            if r and r["status"] != "ok":
                failed += 1
    C.say(f"done: {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
