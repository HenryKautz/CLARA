#!/usr/bin/env python3
"""make-formats.py [--sizes N...] [--limit S] [--max-clauses C] -- each FourPackage
problem in FiFO and weighted-CNF form, as its recognition runs use it.

For each problem gridNxN-K, at its recognition horizon H (fpcommon.recognition_horizon):

  wff/NAME.wff    the FiFO SatPlan encoding (pddl2fifo's translation, planner.sh
                  --stop-after wff), self-contained: it sets (option
                  *satplan-numslices* H) and includes a copy of FiFO's SatPlan
                  axioms -- wff/satplan.wff (interfering-action mutexes as explicit
                  pairs, the FiFO these wffs were first made with) or
                  wff/satplan-mutex.wff (FiFO's MUTEX), per the installed FiFO;
                  the record's "encoding" says which.  Written for EVERY problem,
                  first: it needs no instantiation, so it exists even where nothing
                  else can be made.
  wcnf/NAME-2020.wcnf, wcnf/NAME-2024.wcnf, wcnf/NAME.map
                  the instantiated theory's weighted CNF in the MCC 2020 (ADDMC) and
                  MCC 2024 (SharpSAT-TD) dialects, and the variable -> atom map, by
                  FiFO's own writer.  Pinned evidence (evidence/*-obsK.txt) is unit
                  literals over the map's atoms.

The theory comes from recognize.sh --stop-after scnf, so it is exactly the one the
recognition runs score; instantiating wff/NAME.wff alone must give the same clauses,
which is checked for every problem (line by line, comments aside -- FiFO's
instantiation is deterministic -- so neither theory is held in memory).  The scnf
itself is NOT kept: it is 5-6x the size of a WCNF and disk is short; its size is
recorded, and instantiating the wff regenerates it.

A problem whose predicted theory exceeds --max-clauses (fpcommon.predicted_clauses)
gets its wff and the status too-big: FiFO's WCNF writer holds the whole theory in
memory, about 1 GB of SBCL heap per million clauses.  One record per problem goes to
results/formats.jsonl.  Every size is tried (no stopping at a timeout).
"""
import argparse, json, os, re, shutil, signal, subprocess, sys, time
import fpcommon as F

RECOGNIZE = shutil.which("recognize.sh") or os.path.expanduser("~/bin/recognize.sh")
LISP = os.environ.get("FIFO_LISP", os.path.expanduser("~/lib/fifo/lisp"))
HELPER = os.path.join(os.path.dirname(F.HERE), "make-fifo-files.lisp")
WORK = os.path.join(F.SCRATCH, "fp-formats")
RESULTS = os.path.join(F.HERE, "results", "formats.jsonl")
# The SatPlan axioms each wff includes, by the FiFO's mutex encoding: the original
# pairwise axioms stay wff/satplan.wff, which the wffs written before MUTEX include;
# MUTEX's go beside them, so neither set of wffs changes meaning.
ENCODING = F.encoding(LISP)
AXIOMS = {"pairs": "satplan.wff", "mutex": "satplan-mutex.wff"}


def run(cmd, cwd, limit, log):
    t = time.time()
    p = subprocess.Popen(cmd, cwd=cwd, env=F.env(), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        out, _ = p.communicate(timeout=limit)
        status = "ok" if p.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        out, _ = p.communicate()
        # A solver FiFO started is in a process group of its own; it reads from CWD.
        subprocess.run(["pkill", "-KILL", "-f", cwd + "/"])
        status = "timeout"
    open(log, "a").write(out)
    return status, time.time() - t, out


def sbcl(evals, cwd, limit, log):
    cmd = ["sbcl", "--noinform", "--non-interactive"]
    for f in ("FiFO.lisp", "maxent.lisp", "wmc.lisp", "pddl2fifo.lisp", "planner.lisp"):
        cmd += ["--eval", f'(load "{LISP}/{f}")']
    cmd += ["--eval", f'(load "{HELPER}")']
    for e in evals:
        cmd += ["--eval", f"(cf-run {e})"]
    status, _, out = run(cmd, cwd, limit, log)
    ok = status == "ok" and len(re.findall(r"^DONE$", out, re.M)) == len(evals)
    return ok, status, out


def same_clauses(a, b):
    """True when scnf files A and B agree line for line, comment lines aside."""
    with open(a) as fa, open(b) as fb:
        la = (l for l in fa if not l.startswith(";"))
        lb = (l for l in fb if not l.startswith(";"))
        sentinel = object()
        for x in la:
            if x != next(lb, sentinel):
                return False
        return next(lb, sentinel) is sentinel


def write_wff(name, H, work, limit, log):
    """wff/NAME.wff (and wff/satplan.wff): (path, None) or (None, error lines)."""
    src = os.path.join(F.HERE, name + ".pddl")
    shutil.copy(src, work)
    status, _, out = run(["planner.sh", name + ".pddl", "--domain", F.DOMAIN,
                          "--numslices", str(H), "--stop-after", "wff"], work, limit, log)
    made = os.path.join(work, name + ".wff")
    if status != "ok" or not os.path.exists(made):
        return None, out.splitlines()[-8:]
    axioms = AXIOMS[ENCODING]
    body, n = re.subn(r'^\(include "[^"]*satplan\.wff"\)$', f'(include "{axioms}")',
                      open(made).read(), flags=re.M)
    if n != 1:
        return None, ["the wff has no single satplan.wff include"]
    header = (f";; {name}: FiFO encoding of ../{name}.pddl as its recognition runs use it\n"
              f";; (planner.sh --stop-after wff; written by make-formats.py).\n"
              f";; Self-contained: instantiating this file alone gives the theory whose\n"
              f";; weighted CNF is ../wcnf/{name}-2024.wcnf.  SatPlan's interfering-action\n"
              f";; mutexes: {ENCODING} ({axioms}).  The horizon:\n"
              f"(option *satplan-numslices* {H})\n\n")
    os.makedirs(os.path.join(F.HERE, "wff"), exist_ok=True)
    shutil.copy(os.path.join(LISP, "satplan.wff"), os.path.join(F.HERE, "wff", axioms))
    wff = os.path.join(F.HERE, "wff", name + ".wff")
    open(wff, "w").write(header + body)
    return wff, None


def one(name, limit, max_clauses):
    src = os.path.join(F.HERE, name + ".pddl")
    H = F.recognition_horizon(src)
    n = F.size_of(name)
    work = os.path.join(WORK, name)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    log = os.path.join(work, "log.txt")
    rec = dict(name=name, size=n, horizon=H, limit_s=limit, encoding=ENCODING,
               predicted_clauses=round(F.predicted_clauses(n, H)), pddl_bytes=os.path.getsize(src))
    wff, err = write_wff(name, H, work, limit, log)
    if err:
        rec.update(status="failed", stage="wff", log_tail=err)
        return rec
    rec["wff_bytes"] = os.path.getsize(wff)
    if max_clauses and F.predicted_clauses(n, H) > max_clauses:
        rec["status"] = "too-big"
        shutil.rmtree(work, ignore_errors=True)
        return rec
    # any legal pinned observation will do: --stop-after scnf keeps fifo evidence
    # apart from the theory, so the theory does not depend on it
    ev = os.path.join(work, "ev.txt")
    roads, at, _ = F.parse(src)
    t1 = sorted(o for o in at if o.startswith("truck"))[0]
    nxt = sorted(roads[at[t1]])[0]
    open(ev, "w").write(f"(and\n  (occurs (drive {t1} {at[t1]} {nxt}) 1))\n")
    # --planner-timeout: recognize.sh's own watchdog was a fixed 900 s, which killed
    # the 15x15 instantiations at 54-79 slices however large LIMIT was
    status, wall, out = run(["bash", RECOGNIZE, F.DOMAIN, src, ev, "--evidence-kind", "fifo",
                             "--horizon", str(H), "--stop-after", "scnf",
                             "--planner-timeout", str(limit),
                             "--out", os.path.join(work, "rec")], work, limit, log)
    rec["instantiate_s"] = round(wall, 2)
    theory = os.path.join(work, "rec", "rec-problem.scnf")
    if status != "ok" or not os.path.exists(theory):
        rec.update(status=status if status != "ok" else "failed", stage="instantiate",
                   log_tail=out.splitlines()[-8:])
        shutil.rmtree(work, ignore_errors=True)
        return rec
    rec["scnf_bytes"] = os.path.getsize(theory)
    check = os.path.join(work, "check.scnf")
    ok, status, out = sbcl([f'(unless (instantiate "{wff}" :scnfile "{check}") '
                            f'(error "instantiating {wff} failed"))'], work, limit, log)
    if not ok:
        rec.update(status=status if status == "timeout" else "failed", stage="wff-check",
                   log_tail=out.splitlines()[-8:])
        shutil.rmtree(work, ignore_errors=True)
        return rec
    rec["wff_check"] = "OK" if same_clauses(check, theory) else "MISMATCH"
    os.remove(check)
    if rec["wff_check"] != "OK":
        rec["status"] = "failed"
        shutil.rmtree(work, ignore_errors=True)
        return rec
    C = os.path.join(work, "wcnf")
    os.makedirs(C)
    ok, status, out = sbcl([f'(cf-write-wcnf "{theory}" "{C}/{name}")'], work, limit, log)
    w = re.search(rf"^WCNF {re.escape(name)} (\d+) (\d+)$", out, re.M)
    if not ok or not w:
        rec.update(status=status if status == "timeout" else "failed", stage="wcnf",
                   log_tail=out.splitlines()[-8:])
        shutil.rmtree(work, ignore_errors=True)
        return rec
    rec.update(status="ok", wcnf_vars=int(w.group(1)), wcnf_clauses=int(w.group(2)))
    os.makedirs(os.path.join(F.HERE, "wcnf"), exist_ok=True)
    for f in (f"{name}-2020.wcnf", f"{name}-2024.wcnf", f"{name}.map"):
        shutil.copy(os.path.join(C, f), os.path.join(F.HERE, "wcnf", f))
    for key, f in (("wcnf2020_bytes", f"{name}-2020.wcnf"), ("wcnf2024_bytes", f"{name}-2024.wcnf")):
        rec[key] = os.path.getsize(os.path.join(F.HERE, "wcnf", f))
    shutil.rmtree(work, ignore_errors=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="*")
    ap.add_argument("--limit", type=int, default=1800)
    ap.add_argument("--max-clauses", type=float, default=16e6)
    a = ap.parse_args()
    os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
    done = set()
    if os.path.exists(RESULTS):
        done = {json.loads(l)["name"] for l in open(RESULTS) if json.loads(l)["status"] == "ok"}
    for p in F.problems(a.sizes):
        if p in done:
            continue
        r = one(p, a.limit, a.max_clauses)
        with open(RESULTS, "a") as f:
            f.write(json.dumps(r) + "\n")
        print(f"{time.strftime('%H:%M:%S')} {p}: {r['status']} H={r['horizon']} "
              f"~{r['predicted_clauses'] / 1e6:.1f}M predicted, {r.get('wcnf_clauses', '-')} clauses "
              f"{' | '.join(r.get('log_tail', [])[-2:])}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
