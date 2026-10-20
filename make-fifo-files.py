#!/usr/bin/env python3
"""make-fifo-files.py -- the FiFO source, theory and weighted CNF of every benchmark.

For every problem of SimpleGrid, TwoPackage and AAAI-2010-Benchmarks it writes, in
that benchmark's directory:

  wff/NAME.wff    the FiFO SatPlan encoding (pddl2fifo's translation of the
                  recognition problem), self-contained: it sets its own horizon,
                  (option *satplan-numslices* H), and includes wff/satplan.wff, a
                  copy of FiFO's SatPlan axioms.  Instantiating it alone gives the
                  clauses of scnf/NAME.scnf -- checked for every problem.
  scnf/NAME.scnf  the instantiated (symbolic) CNF -- the theory every experiment
                  used.  For AAAI-2010-Benchmarks also NAME-assertion.txt.
  wcnf/NAME-2020.wcnf, wcnf/NAME-2024.wcnf
                  its weighted CNF in the MCC 2020 (ADDMC) and MCC 2024
                  (SharpSAT-TD) dialects, and wcnf/NAME.map, variable -> atom.
                  For AAAI-2010-Benchmarks also NAME-ev-2020.wcnf and
                  NAME-ev-2024.wcnf, with the observation literal as a unit clause.

Nothing is solved.  Each theory is REGENERATED -- recognize.sh --stop-after scnf
at the problem's horizon, as the experiments made it -- and must be byte-identical
to the archived one in scnf/ (circuits/ or AAAI theories/ before 2026-10-20),
which is what makes the wff, written by the same run, its true source.

  SimpleGrid, TwoPackage: NAME = gridNxN-K, the evidence-free recognition theory
      (recognize.sh --evidence-kind fifo: pinned evidence is kept apart), at the
      horizon recorded in the archived theory's header.
  AAAI-2010-Benchmarks: NAME = <instance>-obsK, the theory with the ordering
      evidence evidence-K.txt (recognize.sh's default --evidence-kind pddl): the
      observation monitor's axioms are folded into the theory, so the wff carries
      them too, as a FiFO formula at its end.  Plus IntrusionDetectionCosts-obs3-H5,
      the H = 5 cross-check theory.

Usage: make-fifo-files.py [--jobs N] [--match REGEX]   (from anywhere; needs FiFO
installed: ~/bin/recognize.sh and ~/lib/fifo/lisp, or FIFO_LISP)
"""
import argparse, concurrent.futures as cf, filecmp, glob, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RECOGNIZE = os.path.expanduser("~/bin/recognize.sh")
LISP = os.environ.get("FIFO_LISP", os.path.expanduser("~/lib/fifo/lisp"))
HELPER = os.path.join(HERE, "make-fifo-files.lisp")
WORK = os.path.join(HERE, "work-fifo-files")
AAAI = {  # instance: (domain file, horizon)
    "IntrusionDetectionCosts": ("intrusion-detection-costs.pddl", 6),
    "BlocksWorldCosts": ("block-words-costs.pddl", 15),
}


def jobs():
    out = []
    for bench in ("SimpleGrid", "TwoPackage"):
        for p in sorted(glob.glob(os.path.join(HERE, bench, "grid*.pddl"))):
            name = os.path.basename(p)[:-5]
            old = archived(bench, name)
            if old:
                out.append(dict(bench=bench, name=name, problem=p, old=old,
                                size=os.path.getsize(old)))
    for inst, (dom, H) in AAAI.items():
        for k in (1, 3, 5):
            name = f"{inst}-obs{k}"
            out.append(dict(bench="AAAI-2010-Benchmarks", name=name, inst=inst, k=k, H=H,
                            old=archived("AAAI-2010-Benchmarks", name)))
    out.append(dict(bench="AAAI-2010-Benchmarks", name="IntrusionDetectionCosts-obs3-H5",
                    inst="IntrusionDetectionCosts", k=3, H=5,
                    old=archived("AAAI-2010-Benchmarks", "IntrusionDetectionCosts-obs3-H5")))
    for j in out:
        j.setdefault("size", os.path.getsize(j["old"]) if j["old"] else 0)
    return out


def archived(bench, name):
    """The archived theory: its new home if already moved, else the old one."""
    old = "theories" if bench == "AAAI-2010-Benchmarks" else "circuits"
    for d in ("scnf", old):
        f = os.path.join(HERE, bench, d, name + ".scnf")
        if os.path.exists(f):
            return f
    return None


def sbcl(evals, cwd, log):
    cmd = ["sbcl", "--dynamic-space-size", "16000", "--noinform", "--non-interactive"]
    for f in ("FiFO.lisp", "maxent.lisp", "wmc.lisp", "pddl2fifo.lisp", "planner.lisp"):
        cmd += ["--eval", f'(load "{LISP}/{f}")']
    cmd += ["--eval", f'(load "{HELPER}")']
    for e in evals:
        cmd += ["--eval", e]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    with open(log, "a") as f:
        f.write(r.stdout + r.stderr)
    return r


def header(j, H):
    src = os.path.relpath(j["problem"] if "problem" in j else
                          os.path.join(HERE, j["bench"], j["inst"], "problem.pddl"),
                          os.path.join(HERE, j["bench"]))
    ev = "" if j["bench"] != "AAAI-2010-Benchmarks" else \
        f", with the ordering evidence {j['inst']}/evidence-{j['k']}.txt"
    return (f";; {j['name']}: FiFO encoding of {src}{ev}, as the CLARA experiments built it\n"
            f";; (recognize.sh --stop-after scnf; regenerated by make-fifo-files.py).\n"
            f";; Self-contained: instantiating this file alone gives the clauses of\n"
            f";; ../scnf/{j['name']}.scnf.  The horizon:\n"
            f"(option *satplan-numslices* {H})\n\n")


def one(j):
    bench, name = j["bench"], j["name"]
    B = os.path.join(HERE, bench)
    work = os.path.join(WORK, f"{bench}-{name}")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    log = os.path.join(work, "log.txt")
    if not j["old"]:
        return name, "no archived theory"
    # 1. regenerate the theory
    if bench == "AAAI-2010-Benchmarks":
        dom, _ = AAAI[j["inst"]]
        H = j["H"]
        I = os.path.join(B, j["inst"])
        domain, problem, ev = os.path.join(I, dom), os.path.join(I, "problem.pddl"), \
            os.path.join(I, f"evidence-{j['k']}.txt")
        cmd = ["bash", RECOGNIZE, domain, problem, ev, "--horizon", str(H),
               "--stop-after", "scnf", "--out", os.path.join(work, "rec")]
    else:
        H = int(re.search(r"fifo-projection-horizon: (\d+)", open(j["old"]).read(4000)).group(1))
        evs = sorted(glob.glob(os.path.join(B, "evidence", name + "-*-obs1.txt")))
        if evs:
            ev = evs[0]
        else:   # as compile-d4.py: any legal first drive; the theory ignores it
            ev = os.path.join(work, "first-drive.txt")
            open(ev, "w").write("(and\n  (occurs (drive truck1 p1-1 p2-1) 1))\n")
        cmd = ["bash", RECOGNIZE, "clara-logistics.pddl", j["problem"], ev,
               "--evidence-kind", "fifo", "--horizon", str(H),
               "--stop-after", "scnf", "--out", os.path.join(work, "rec")]
    r = subprocess.run(cmd, cwd=work, capture_output=True, text=True)
    open(log, "a").write(r.stdout + r.stderr)
    rec = os.path.join(work, "rec")
    new = os.path.join(rec, "rec-problem.scnf")
    if r.returncode != 0 or not os.path.exists(new):
        return name, f"recognize.sh failed (see {log})"
    if not filecmp.cmp(new, j["old"], shallow=False):
        return name, f"regenerated theory DIFFERS from {os.path.relpath(j['old'], HERE)}"
    # 2. the wff
    if bench == "AAAI-2010-Benchmarks":
        w = os.path.join(work, "w")
        os.makedirs(w)
        shutil.copy(os.path.join(rec, "rec-problem.pddl"), os.path.join(w, name + ".pddl"))
        r = sbcl([f'(cf-pddl-wff "{w}/{name}.pddl" "{domain}" "{ev}")'], w, log)
        if "PDDL-WFF" not in r.stdout:
            return name, f"pddl2fifo failed (see {log})"
        body = open(os.path.join(w, name + ".wff")).read()
    else:
        body = open(os.path.join(rec, "rec-problem.wff")).read()
    body, n = re.subn(r'^\(include "[^"]*satplan\.wff"\)$', '(include "satplan.wff")', body, flags=re.M)
    if n != 1:
        return name, "the wff has no single satplan.wff include"
    for d in ("wff", "scnf", "wcnf"):
        os.makedirs(os.path.join(B, d), exist_ok=True)
    if not os.path.exists(os.path.join(B, "wff", "satplan.wff")):
        shutil.copy(os.path.join(LISP, "satplan.wff"), os.path.join(B, "wff", "satplan.wff"))
    wff = os.path.join(B, "wff", name + ".wff")
    open(wff, "w").write(header(j, H) + body)
    # 3. the theory, in scnf/ (byte-identical to the archived one)
    scnf = os.path.join(B, "scnf", name + ".scnf")
    if os.path.abspath(j["old"]) != os.path.abspath(scnf):
        shutil.copy(new, scnf)
    evforms = ""
    if bench == "AAAI-2010-Benchmarks":
        shutil.copy(os.path.join(rec, "rec-problem-assertion.txt"),
                    os.path.join(B, "scnf", name + "-assertion.txt"))
        lit = open(os.path.join(rec, "rec-problem-assertion.txt")).read().strip()
        evforms = f' :evidence-forms (list (let ((*read-eval* nil)) (read-from-string "{lit}"))) :evtag "-ev"'
    # 4. the wff alone must give the theory's clauses; 5. the weighted CNFs
    r = sbcl([f'(cf-check-wff "{wff}" "{scnf}" "{work}/check.scnf")',
              f'(cf-write-wcnf "{scnf}" "{B}/wcnf/{name}"{evforms})'], work, log)
    m = re.search(r"WFF-CHECK (\S+) (\d+) (\d+)", r.stdout)
    if not m or m.group(1) not in ("OK", "OK-REORDERED"):
        return name, f"wff check: {m.group(0) if m else 'no result'} (see {log})"
    if "WCNF" not in r.stdout:
        return name, f"wcnf failed (see {log})"
    sizes = re.findall(r"^WCNF (\S+) (\d+) (\d+)$", r.stdout, re.M)
    shutil.rmtree(work, ignore_errors=True)
    order = "" if m.group(1) == "OK" else " (wff clauses in another order)"
    return name, "ok " + " ".join(f"{n}:{v}v/{c}c" for n, v, c in sizes) + order


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--match", default="")
    a = ap.parse_args()
    todo = [j for j in jobs() if re.search(a.match, f"{j['bench']}/{j['name']}")]
    todo.sort(key=lambda j: -j["size"])   # the big ones first, to balance
    os.makedirs(WORK, exist_ok=True)
    print(f"{len(todo)} problems, {a.jobs} at a time", flush=True)
    bad = 0
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        futs = {ex.submit(one, j): j for j in todo}
        for f in cf.as_completed(futs):
            j = futs[f]
            try:
                name, status = f.result()
            except Exception as e:   # report, keep going
                name, status = j["name"], f"exception: {e!r}"
            bad += not status.startswith("ok")
            print(f"{j['bench']}/{name}: {status}", flush=True)
    print(f"done, {bad} failed", flush=True)
    if not bad:
        shutil.rmtree(WORK, ignore_errors=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
