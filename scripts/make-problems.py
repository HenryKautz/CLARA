#!/usr/bin/env python3
"""make-problems.py --family F

Regenerate family F's problems from OldVersions/F (deleted from the tree in
7731002; restore it first, see common.OLD_COMMIT): each old gridNxN-K.pddl
records every ppgen.sh setting it was made with; it is made again with those
settings, except

  --domain clara-logistics   (load and unload cost handle-cost; no transfer)
  --handle-cost 1
  --preferences none         (FourPackage had --preferences 8 8: every goal
                              literal was also a weighted preference)

so the only goal is the hard (or ...) / (and (or ...) ...) the old problem had,
and with the family's own changes (common.FAMILIES "drop"/"add"): ThreePackage
and FourPackage drop --knockout; TwoPackageOneway is made from OldVersions/
TwoPackage with --oneway 25.  The same seed gives the same grid, starts and
destinations (ppgen draws the knockout and the one-way roads from their own
random states): each new problem is checked to have exactly the old one's
objects, :init (apart from the new (= (handle-cost) 1), and, in a family that
drops or adds flags, the road facts) and goal literals.  Every new problem's
settings block is checked to show the dropped and added flags as intended, and
a --oneway shortfall (ppgen could not make the asked share one-way without
cutting a place off) is an error, not a note.

Old outputs: the later stages resume from F/results/*.jsonl by goal and
evidence name, so results of an earlier version of a problem would be reused
for a changed one with the same name.  When F already has results and a
regenerated problem differs from the one on disk, this script stops before
writing anything; --archive first moves F's outputs (results/, goals/,
evidence/, recognition/, scnf/, circuits/, tables.md, *.log) into
F/superseded-<date-time>/.

Also written: F/clara-logistics.pddl (a copy of FiFO's library domain) and
goals/<goal>.pddl, one per hypothesis (common.Family.hypotheses).
"""
import argparse, os, re, shutil, subprocess, sys, tempfile, time
import common as C

OUTPUTS = ("results", "goals", "evidence", "recognition", "scnf", "circuits", "tables.md")


def old_flags(path):
    """[(flag, [args])] from the ppgen settings block of an old problem."""
    flags, on = [], False
    for line in open(path):
        if line.startswith(";; Every setting used"):
            on = True
            continue
        if on:
            m = re.match(r";;   (--\S+)(.*)$", line.rstrip("\n"))
            if m:
                flags.append((m.group(1), m.group(2).split()))
            elif line.strip() not in (";;",) and not line.startswith(";; "):
                break
    if not flags:
        sys.exit(f"{path}: no ppgen settings block")
    return flags


def new_flags(flags, fam):
    gone = ("--preferences", "--handle-cost", "--domain") + tuple(fam.drop) + tuple(f for f, _ in fam.add)
    out = [(f, a) for f, a in flags if f not in gone]
    out += [("--handle-cost", ["1"]), ("--preferences", ["none"])] + [(f, list(a)) for f, a in fam.add]
    return out


def body_without(text, drop):
    """The problem from (:objects up to (:goal, without comment lines and the
    lines in DROP."""
    body = text[text.index("(:objects"):text.index("(:goal")]
    lines = [l.strip() for l in body.split("\n")]
    return [l for l in lines if l and not l.startswith(";") and not any(re.search(d, l) for d in drop)]


def make_one(fam, f, tmp):
    """Make problem F of family FAM into directory TMP and check it; returns
    the path written."""
    name = f[:-5]
    old = os.path.join(fam.old, f)
    out = os.path.join(tmp, f)
    cmd = ["ppgen.sh"]
    for flag, args in new_flags(old_flags(old), fam):
        cmd += [flag] + args
    cmd += ["--domain", C.DOMAIN_NAME, "--name", name, "-o", out]
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
    old_t, new_t = open(old).read(), open(out).read()
    # the old world, apart from handle-cost and (when the family changes the
    # roads) the road facts; goal: compare the literal sets
    drop = [r"\(= \(handle-cost\)"] + ([] if fam.same_world else [r"\(road "])
    ob = [l.rstrip(")") for l in body_without(old_t, drop)]
    nb = [l.rstrip(")") for l in body_without(new_t, drop)]
    og = sorted(set(re.findall(r"\(at \S+ [^\s()]+\)", C.goal_text(old).split("(preference")[0])))
    ng = sorted(set(re.findall(r"\(at \S+ [^\s()]+\)", C.goal_text(out))))
    if ob != nb or og != ng:
        sys.exit(f"{name}: the regenerated problem differs from the old one beyond "
                 f"handle-cost, preferences{'' if fam.same_world else ' and roads'}")
    # the settings block must show the flags as intended
    got = dict(old_flags(out))
    for flag in fam.drop:
        if got.get(flag, ["0"]) != ["0"]:
            sys.exit(f"{name}: {flag} {got[flag]} still in effect")
    for flag, args in fam.add:
        if got.get(flag) != list(args):
            sys.exit(f"{name}: expected {flag} {' '.join(args)}, got {got.get(flag)}")
    if "(= (handle-cost) 1)" not in new_t or "preference" in C.goal_text(out):
        sys.exit(f"{name}: expected (= (handle-cost) 1) and no preferences")
    return out


def archive(fam):
    """Move FAM's outputs into FAM/superseded-<date-time>/."""
    dest = fam.path("superseded-" + time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(dest)
    moved = [x for x in OUTPUTS if os.path.exists(fam.path(x))]
    moved += [x for x in os.listdir(fam.dir) if x.endswith(".log")]
    for x in moved:
        shutil.move(fam.path(x), os.path.join(dest, x))
    print(f"moved {', '.join(moved)} into {os.path.relpath(dest, C.CLARA)}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", required=True)
    ap.add_argument("--archive", action="store_true",
                    help="move F's outputs into F/superseded-<date-time>/ first")
    a = ap.parse_args()
    fam = C.Family(a.family)
    files = sorted(f for f in os.listdir(C.require_old(fam.old))
                   if (m := re.fullmatch(r"grid(\d+)x\1-(\d+)\.pddl", f)) and int(m.group(1)) in fam.sizes)
    with tempfile.TemporaryDirectory(prefix="make-problems-") as tmp:
        made = [(f, make_one(fam, f, tmp)) for f in files]
        changed = [f[:-5] for f, p in made
                   if not os.path.exists(fam.path(f)) or open(p).read() != open(fam.path(f)).read()]
        has_results = os.path.isdir(fam.results) and any(
            x.endswith(".jsonl") for x in os.listdir(fam.results))
        if a.archive:
            archive(fam)
        elif has_results and changed:
            sys.exit(f"{fam.name} has results (results/*.jsonl), and these problems would change: "
                     f"{', '.join(changed)}.\nThe later stages would reuse the old results for them.  "
                     f"Rerun with --archive to move the old outputs aside first.  Nothing was written.")
        os.makedirs(fam.path("goals"), exist_ok=True)
        lib = os.path.join(os.path.expanduser(os.environ.get("FIFO_LISP", "~/lib/fifo/lisp")),
                           "..", "pddl", C.DOMAIN_NAME + ".pddl")
        shutil.copy(lib, fam.domain)
        n_goals = 0
        for f, p in made:
            name = f[:-5]
            shutil.copy(p, fam.path(f))
            for h in fam.hypotheses(name):
                open(fam.path("goals", h.goal + ".pddl"), "w").write(C.goal_problem_text(fam, name, h))
                n_goals += 1
            print(f"{name}: ok, {len(fam.hypotheses(name))} hypotheses"
                  f"{' (changed)' if name in changed else ''}", flush=True)
    print(f"{fam.name}: {len(fam.problems())} problems, {n_goals} goals, {len(changed)} changed")


if __name__ == "__main__":
    main()
