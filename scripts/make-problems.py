#!/usr/bin/env python3
"""make-problems.py --family F [--only NAME ...] [--check] [--archive]

Make family F's problems with ppgen.sh: gridNxN-K for every size N of the
family and K in common.SEEDS, with the settings common.Family.ppgen_flags gives
(the family table in common.py), domain clara-logistics.  Each problem's
header records every setting, so a problem can always be made again from it.

Each problem is checked: (= (handle-cost) 1), no preferences, domain
clara-logistics, and no --oneway shortfall (ppgen could not make the asked
share one-way without cutting a place off).  Also written: F/clara-logistics.pddl
(a copy of FiFO's library domain) and goals/<goal>.pddl, one per hypothesis
(common.Family.hypotheses).

--check   make everything in a scratch directory and compare it, byte for byte,
          with the files on disk; write nothing.  Exit status 1 if any file
          differs or is missing, or a goal file on disk has no hypothesis.
--only    just these problems (e.g. grid3x3-1).

Existing outputs: the later stages resume from F/results/*.jsonl by goal and
evidence name, so results for a problem would be reused for a changed problem
of the same name.  When F already has results and a problem would change, this
script stops before writing anything; --archive first moves F's outputs
(results/, goals/, evidence/, recognition/, scnf/, circuits/, tables.md, *.log)
into F/superseded-<date-time>/.
"""
import argparse, glob, os, re, shutil, subprocess, sys, tempfile, time
import common as C

OUTPUTS = ("results", "goals", "evidence", "recognition", "scnf", "circuits", "tables.md")


def make_one(fam, name, tmp):
    """Make problem NAME of family FAM into directory TMP and check it; returns
    the path written."""
    m = re.fullmatch(r"grid(\d+)x\1-(\d+)", name)
    n, seed = int(m.group(1)), int(m.group(2))
    out = os.path.join(tmp, name + ".pddl")
    cmd = ["ppgen.sh"] + fam.ppgen_flags(n, seed) + ["--domain", C.DOMAIN_NAME, "--name", name, "-o", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ppgen failed on {name}:\n{r.stdout}{r.stderr}")
    notes = [l for l in r.stderr.strip().split("\n") if l and not l.startswith("Wrote ")]
    # --oneway's shortfall ("--oneway N asked for K one-way roads but made M"):
    # the problem would be labelled N% one-way without being so
    short = [l for l in notes if "--oneway" in l and "asked for" in l]
    if short:
        sys.exit(f"{name}: {' / '.join(short)}")
    if notes:
        print(f"{name}: ppgen says: {' / '.join(notes)}", flush=True)
    text = open(out).read()
    if "(= (handle-cost) 1)" not in text or "preference" in C.goal_text(out) \
            or f"(:domain {C.DOMAIN_NAME})" not in text:
        sys.exit(f"{name}: expected (= (handle-cost) 1), no preferences and domain {C.DOMAIN_NAME}")
    return out


def goal_files(fam, name, made):
    """{goal file name: text} of problem NAME, made from the problem file MADE."""
    return {h.goal + ".pddl": C.goal_problem_text(fam, name, h, src=made)
            for h in C.hypotheses(made, name, fam.kind)}


def archive(fam):
    """Move FAM's outputs into FAM/superseded-<date-time>/."""
    dest = fam.path("superseded-" + time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(dest)
    moved = [x for x in OUTPUTS if os.path.exists(fam.path(x))]
    moved += [x for x in os.listdir(fam.dir) if x.endswith(".log")]
    for x in moved:
        shutil.move(fam.path(x), os.path.join(dest, x))
    print(f"moved {', '.join(moved)} into {os.path.relpath(dest, C.CLARA)}", flush=True)


def same(path, text):
    return os.path.exists(path) and open(path).read() == text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", required=True)
    ap.add_argument("--only", nargs="+", metavar="NAME", help="just these problems")
    ap.add_argument("--check", action="store_true",
                    help="compare with the files on disk; write nothing")
    ap.add_argument("--archive", action="store_true",
                    help="move F's outputs into F/superseded-<date-time>/ first")
    a = ap.parse_args()
    fam = C.Family(a.family)
    names = [f"grid{n}x{n}-{k}" for n in fam.sizes for k in C.SEEDS]
    if a.only:
        bad = [x for x in a.only if x not in names]
        if bad:
            sys.exit(f"not problems of {fam.name}: {', '.join(bad)}")
        names = [x for x in names if x in a.only]
    lib = os.path.join(os.path.expanduser(os.environ.get("FIFO_LISP", "~/lib/fifo/lisp")),
                       "..", "pddl", C.DOMAIN_NAME + ".pddl")
    domain = open(lib).read()

    with tempfile.TemporaryDirectory(prefix="make-problems-") as tmp:
        # {path on disk: text} of every file this run makes
        files = {fam.domain: domain}
        per_problem = {}
        for name in names:
            made = make_one(fam, name, tmp)
            goals = goal_files(fam, name, made)
            per_problem[name] = (made, goals)
            files[fam.path(name + ".pddl")] = open(made).read()
            files.update({fam.path("goals", g): t for g, t in goals.items()})
        changed = [p for p, t in files.items() if not same(p, t)]

        if a.check:
            stale = []
            for name, (_, goals) in per_problem.items():
                for p in glob.glob(fam.path("goals", name + "-*.pddl")):
                    if os.path.basename(p) not in goals:
                        stale.append(p)
            for name, (_, goals) in per_problem.items():
                ps = [fam.path(name + ".pddl")] + [fam.path("goals", g) for g in goals]
                bad = [os.path.relpath(p, fam.dir) for p in ps if p in changed]
                print(f"{name}: {'identical' if not bad else 'DIFFERS: ' + ', '.join(bad)}"
                      f" ({len(goals)} goals)", flush=True)
            if fam.domain in changed:
                print(f"{os.path.relpath(fam.domain, C.CLARA)}: DIFFERS from {lib}")
            for p in stale:
                print(f"{os.path.relpath(p, C.CLARA)}: on disk, but no hypothesis has it")
            n_bad = len(changed) + len(stale)
            print(f"{fam.name}: {len(names)} problems, {len(files)} files compared, "
                  f"{n_bad} {'problem' if n_bad == 1 else 'problems'}")
            sys.exit(1 if n_bad else 0)

        has_results = os.path.isdir(fam.results) and any(
            x.endswith(".jsonl") for x in os.listdir(fam.results))
        if a.archive:
            archive(fam)
        elif has_results and changed:
            sys.exit(f"{fam.name} has results (results/*.jsonl), and these files would change: "
                     f"{', '.join(os.path.relpath(p, fam.dir) for p in changed)}.\n"
                     f"The later stages would reuse the existing results for them.  "
                     f"Rerun with --archive to move the outputs aside first.  Nothing was written.")
        os.makedirs(fam.path("goals"), exist_ok=True)
        for p, t in files.items():
            if not same(p, t):
                open(p, "w").write(t)
        for name, (_, goals) in per_problem.items():
            print(f"{name}: ok, {len(goals)} hypotheses"
                  f"{' (changed)' if fam.path(name + '.pddl') in changed else ''}", flush=True)
    print(f"{fam.name}: {len(names)} problems, {len(files) - 1 - len(names)} goals, "
          f"{len(changed)} files changed")


if __name__ == "__main__":
    main()
