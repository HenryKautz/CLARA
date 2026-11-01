#!/usr/bin/env python3
"""make-problems.py --family F

Regenerate family F's problems from OldVersions/F: each old gridNxN-K.pddl
records every ppgen.sh setting it was made with; it is made again with those
settings, except

  --domain clara-logistics   (load and unload cost handle-cost; no transfer)
  --handle-cost 1
  --preferences none         (FourPackage had --preferences 8 8: every goal
                              literal was also a weighted preference)

so the only goal is the hard (or ...) / (and (or ...) ...) the old problem had.
The same seed gives the same grid, roads, starts and destinations: each new
problem is checked to have exactly the old one's objects, :init (apart from the
new (= (handle-cost) 1)) and goal literals.

Also written: F/clara-logistics.pddl (a copy of FiFO's library domain) and
goals/<goal>.pddl, one per hypothesis (common.Family.hypotheses).
"""
import argparse, os, re, shutil, subprocess, sys
import common as C


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


def new_flags(flags):
    out = [(f, a) for f, a in flags if f not in ("--preferences", "--handle-cost", "--domain")]
    out += [("--handle-cost", ["1"]), ("--preferences", ["none"])]
    return out


def body_without(text, drop):
    """The problem from (:objects up to (:goal, without comment lines and the
    lines in DROP."""
    body = text[text.index("(:objects"):text.index("(:goal")]
    lines = [l.strip() for l in body.split("\n")]
    return [l for l in lines if l and not l.startswith(";") and not any(re.search(d, l) for d in drop)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", required=True)
    a = ap.parse_args()
    fam = C.Family(a.family)
    os.makedirs(fam.path("goals"), exist_ok=True)
    lib = os.path.join(os.path.expanduser(os.environ.get("FIFO_LISP", "~/lib/fifo/lisp")),
                       "..", "pddl", C.DOMAIN_NAME + ".pddl")
    shutil.copy(lib, fam.domain)
    n_goals = 0
    for f in sorted(os.listdir(fam.old)):
        m = re.fullmatch(r"grid(\d+)x\1-(\d+)\.pddl", f)
        if not m or int(m.group(1)) not in fam.sizes:
            continue
        name = f[:-5]
        old = os.path.join(fam.old, f)
        cmd = ["ppgen.sh"]
        for flag, args in new_flags(old_flags(old)):
            cmd += [flag] + args
        cmd += ["--domain", C.DOMAIN_NAME, "--name", name, "-o", fam.path(f)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"ppgen failed on {name}:\n{r.stdout}{r.stderr}")
        # same world as the old problem?  (goal: compare the literal sets)
        drop = [r"\(= \(handle-cost\)"]
        old_t, new_t = open(old).read(), open(fam.path(f)).read()
        ob = [l.rstrip(")") for l in body_without(old_t, drop)]
        nb = [l.rstrip(")") for l in body_without(new_t, drop)]
        og = sorted(set(re.findall(r"\(at \S+ [^\s()]+\)", C.goal_text(old).split("(preference")[0])))
        ng = sorted(set(re.findall(r"\(at \S+ [^\s()]+\)", C.goal_text(fam.path(f)))))
        if ob != nb or og != ng:
            sys.exit(f"{name}: the regenerated problem differs from the old one beyond "
                     f"handle-cost and preferences")
        if "(= (handle-cost) 1)" not in new_t or "preference" in C.goal_text(fam.path(f)):
            sys.exit(f"{name}: expected (= (handle-cost) 1) and no preferences")
        for h in fam.hypotheses(name):
            open(fam.path("goals", h.goal + ".pddl"), "w").write(C.goal_problem_text(fam, name, h))
            n_goals += 1
        print(f"{name}: ok, {len(fam.hypotheses(name))} hypotheses", flush=True)
    print(f"{fam.name}: {len(fam.problems())} problems, {n_goals} goals")


if __name__ == "__main__":
    main()
