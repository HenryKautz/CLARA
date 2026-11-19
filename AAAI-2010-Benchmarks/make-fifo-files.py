#!/usr/bin/env python3
"""make-fifo-files.py -- the FiFO source, theory and weighted CNF of every
AAAI-2010-Benchmarks theory.

For each NAME = <instance>-obsK (K = 1, 3, 5), the theory with the ordering
evidence <instance>/evidence-K.txt, plus IntrusionDetectionCosts-obs3-H5 (the
H = 5 cross-check theory), it writes, in this directory:

  wff/NAME.wff    the FiFO SatPlan encoding (pddl2fifo's translation of the
                  recognition problem), self-contained: it sets its own horizon,
                  (option *satplan-numslices* H), and includes wff/satplan.wff, a
                  copy of FiFO's SatPlan axioms.  The evidence's observation
                  monitor axioms are appended as a FiFO formula.  Instantiating it
                  alone gives the clauses of scnf/NAME.scnf -- checked every time.
  scnf/NAME.scnf  the instantiated (symbolic) CNF -- the theory the runs used --
                  and scnf/NAME-assertion.txt, the literal to condition on.
  wcnf/NAME-2020.wcnf, wcnf/NAME-2024.wcnf
                  its weighted CNF in the MCC 2020 (ADDMC) and MCC 2024
                  (SharpSAT-TD) dialects, and wcnf/NAME.map, variable -> atom --
                  FiFO's own writer (wmc-write-wcnf).  Also NAME-ev-2020.wcnf and
                  NAME-ev-2024.wcnf, with the observation literal as a unit clause.

Nothing is solved.  Each theory is REGENERATED -- recognize.sh --stop-after scnf
at the instance's horizon (recognize.sh's default --evidence-kind pddl folds the
monitor axioms into the theory) -- and must be byte-identical to the one in
scnf/, which is what makes the wff, written by the same run, its true source.

Every file of a theory is written in the job's scratch directory first and
copied here only once all of its checks have passed -- each SBCL step exited 0
and said DONE, the wff instantiates to the theory's clauses, every expected file
exists -- so a failing rerun leaves the files as they were.

Usage: make-fifo-files.py [--jobs N] [--match REGEX]   (from anywhere; needs FiFO
installed: ~/bin/recognize.sh and ~/lib/fifo/lisp, or FIFO_LISP).  --jobs defaults
to what the available memory allows (about 6 GB a job), at most 8.
"""
import argparse, concurrent.futures as cf, filecmp, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RECOGNIZE = os.path.expanduser("~/bin/recognize.sh")
LISP = os.environ.get("FIFO_LISP", os.path.expanduser("~/lib/fifo/lisp"))
HELPER = os.path.join(HERE, "make-fifo-files.lisp")
WORK = os.path.join(HERE, "work-fifo-files")
BENCH = "AAAI-2010-Benchmarks"
AAAI = {  # instance: (domain file, horizon)
    "IntrusionDetectionCosts": ("intrusion-detection-costs.pddl", 6),
    "BlocksWorldCosts": ("block-words-costs.pddl", 15),
}
GB_PER_JOB = 6   # a recognize.sh instantiation plus the checking SBCL, big theories


def jobs():
    out = []
    for inst, (dom, H) in AAAI.items():
        for k in (1, 3, 5):
            out.append(dict(name=f"{inst}-obs{k}", inst=inst, k=k, H=H))
    out.append(dict(name="IntrusionDetectionCosts-obs3-H5", inst="IntrusionDetectionCosts", k=3, H=5))
    for j in out:
        f = os.path.join(HERE, "scnf", j["name"] + ".scnf")
        j["old"] = f if os.path.exists(f) else None
        j["size"] = os.path.getsize(f) if j["old"] else 0
    return out


def default_jobs():
    try:
        with open("/proc/meminfo") as f:
            gb = int(re.search(r"^MemAvailable:\s+(\d+) kB", f.read(), re.M).group(1)) / 2**20
    except (OSError, AttributeError):
        return 2   # not Linux: be modest
    return max(1, min(8, int(gb // GB_PER_JOB)))


def sync_satplan():
    """wff/satplan.wff = FiFO's current satplan.wff.  Done once, before any
    worker starts (so no job reads a half-written copy), and refreshed when
    FiFO's has changed -- the wff checks would otherwise test the new
    instantiation against stale axioms."""
    src = os.path.join(LISP, "satplan.wff")
    dst = os.path.join(HERE, "wff", "satplan.wff")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not (os.path.exists(dst) and filecmp.cmp(src, dst, shallow=False)):
        print(f"wff/satplan.wff: {'refreshed' if os.path.exists(dst) else 'written'} from FiFO",
              flush=True)
        shutil.copy(src, dst)


def sbcl(evals, cwd, log):
    """Run the helper's EVALS in one SBCL; each is wrapped in cf-run, so an error
    exits non-zero.  Returns (ok, stdout): ok needs exit 0 and one DONE per eval."""
    cmd = ["sbcl", "--dynamic-space-size", "16000", "--noinform", "--non-interactive"]
    for f in ("FiFO.lisp", "maxent.lisp", "wmc.lisp", "pddl2fifo.lisp", "planner.lisp"):
        cmd += ["--eval", f'(load "{LISP}/{f}")']
    cmd += ["--eval", f'(load "{HELPER}")']
    for e in evals:
        cmd += ["--eval", f"(cf-run {e})"]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    with open(log, "a") as f:
        f.write(r.stdout + r.stderr)
    ok = r.returncode == 0 and len(re.findall(r"^DONE$", r.stdout, re.M)) == len(evals)
    return ok, r.stdout


def header(j, H):
    src = f"{j['inst']}/problem.pddl"
    ev = f", with the ordering evidence {j['inst']}/evidence-{j['k']}.txt"
    return (f";; {j['name']}: FiFO encoding of {src}{ev}, as the CLARA experiments built it\n"
            f";; (recognize.sh --stop-after scnf; regenerated by make-fifo-files.py).\n"
            f";; Self-contained: instantiating this file alone gives the clauses of\n"
            f";; ../scnf/{j['name']}.scnf.  The horizon:\n"
            f"(option *satplan-numslices* {H})\n\n")


def one(j):
    name = j["name"]
    B = HERE
    work = os.path.join(WORK, name)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    log = os.path.join(work, "log.txt")
    if not j["old"]:
        return name, "no theory in scnf/ to compare with"
    # 1. regenerate the theory
    dom, _ = AAAI[j["inst"]]
    H = j["H"]
    I = os.path.join(B, j["inst"])
    domain, problem, ev = os.path.join(I, dom), os.path.join(I, "problem.pddl"), \
        os.path.join(I, f"evidence-{j['k']}.txt")
    cmd = ["bash", RECOGNIZE, domain, problem, ev, "--horizon", str(H),
           "--stop-after", "scnf", "--out", os.path.join(work, "rec")]
    r = subprocess.run(cmd, cwd=work, capture_output=True, text=True)
    open(log, "a").write(r.stdout + r.stderr)
    rec = os.path.join(work, "rec")
    new = os.path.join(rec, "rec-problem.scnf")
    if r.returncode != 0 or not os.path.exists(new):
        return name, f"recognize.sh failed (see {log})"
    if not filecmp.cmp(new, j["old"], shallow=False):
        return name, f"regenerated theory DIFFERS from {os.path.relpath(j['old'], HERE)}"
    # 2. the wff, staged in work/wff beside a copy of the benchmark's satplan.wff
    W = os.path.join(work, "wff")
    os.makedirs(W)
    shutil.copy(os.path.join(B, "wff", "satplan.wff"), os.path.join(W, "satplan.wff"))
    p = os.path.join(work, "pddl")
    os.makedirs(p)
    shutil.copy(os.path.join(rec, "rec-problem.pddl"), os.path.join(p, name + ".pddl"))
    ok, out = sbcl([f'(cf-pddl-wff "{p}/{name}.pddl" "{domain}" "{ev}")'], p, log)
    if not ok or "PDDL-WFF" not in out:
        return name, f"pddl2fifo failed (see {log})"
    body = open(os.path.join(p, name + ".wff")).read()
    body, n = re.subn(r'^\(include "[^"]*satplan\.wff"\)$', '(include "satplan.wff")', body, flags=re.M)
    if n != 1:
        return name, "the wff has no single satplan.wff include"
    wff = os.path.join(W, name + ".wff")
    open(wff, "w").write(header(j, H) + body)
    # 3. the wff alone must give the theory's clauses; the weighted CNFs
    C = os.path.join(work, "wcnf")
    os.makedirs(C)
    lit = open(os.path.join(rec, "rec-problem-assertion.txt")).read().strip()
    evforms = f' :evidence-forms (list (let ((*read-eval* nil)) (read-from-string "{lit}"))) :evtag "-ev"'
    ok, out = sbcl([f'(cf-check-wff "{wff}" "{new}" "{work}/check.scnf")',
                    f'(cf-write-wcnf "{new}" "{C}/{name}"{evforms})'], work, log)
    m = re.search(r"WFF-CHECK (\S+) (\d+) (\d+)", out)
    if not m or m.group(1) not in ("OK", "OK-REORDERED"):
        return name, f"wff check: {m.group(0) if m else 'no result'} (see {log})"
    variants = ["", "-ev"]
    expected = [f"{name}{v}-{d}.wcnf" for v in variants for d in ("2020", "2024")] + [f"{name}.map"]
    missing = [f for f in expected if not os.path.exists(os.path.join(C, f))]
    if not ok or missing:
        return name, f"wcnf failed{' (missing ' + ', '.join(missing) + ')' if missing else ''} (see {log})"
    # 4. all checks passed: into the benchmark (scnf/NAME.scnf is byte-identical
    # already, so it is left as it is)
    for d in ("wff", "scnf", "wcnf"):
        os.makedirs(os.path.join(B, d), exist_ok=True)
    shutil.copy(wff, os.path.join(B, "wff", name + ".wff"))
    shutil.copy(os.path.join(rec, "rec-problem-assertion.txt"),
                os.path.join(B, "scnf", name + "-assertion.txt"))
    for f in expected:
        shutil.copy(os.path.join(C, f), os.path.join(B, "wcnf", f))
    sizes = re.findall(r"^WCNF (\S+) (\d+) (\d+)$", out, re.M)
    shutil.rmtree(work, ignore_errors=True)
    order = "" if m.group(1) == "OK" else " (wff clauses in another order)"
    return name, "ok " + " ".join(f"{n}:{v}v/{c}c" for n, v, c in sizes) + order


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=None)
    ap.add_argument("--match", default="")
    a = ap.parse_args()
    njobs = a.jobs or default_jobs()
    todo = [j for j in jobs() if re.search(a.match, j["name"])]
    todo.sort(key=lambda j: -j["size"])   # the big ones first, to balance
    os.makedirs(WORK, exist_ok=True)
    sync_satplan()
    print(f"{len(todo)} theories, {njobs} at a time", flush=True)
    bad = 0
    with cf.ThreadPoolExecutor(njobs) as ex:
        futs = {ex.submit(one, j): j for j in todo}
        for f in cf.as_completed(futs):
            j = futs[f]
            try:
                name, status = f.result()
            except Exception as e:   # report, keep going
                name, status = j["name"], f"exception: {e!r}"
            bad += not status.startswith("ok")
            print(f"{name}: {status}", flush=True)
    print(f"done, {bad} failed", flush=True)
    if not bad:
        shutil.rmtree(WORK, ignore_errors=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
