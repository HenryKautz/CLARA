#!/usr/bin/env python3
"""check-plans.py -- sanity-check the shortest plans make-instances.sh saved.

For each cleaned plan goals/*-clean.answer (the one the evidence comes from),
reports one that
  * has two or more actions at one slice (then obsK would hold more than K
    actions), or a slice with no action before its last action (fewer);
  * still loads or unloads a package other than the goal's.
Raw plans (goals/*.answer) that did move the other package -- loads and unloads
cost nothing, so the cost minimisation leaves a spurious one in -- are listed
for information.  Also checks every evidence file's literal count against its
K.  Exit status 1 if anything but the information lines is reported.
Usage: check-plans.py [name-regex]"""
import glob, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
pat = sys.argv[1] if len(sys.argv) > 1 else ""
bad = 0
for raw in sorted(glob.glob(os.path.join(HERE, "goals", "*.answer"))):
    name = os.path.basename(raw)[:-len(".answer")]
    if name.endswith("-clean") or not re.search(pat, name):
        continue
    pkg = re.match(r"grid\d+x\d+-\d+-(pkg\d+)-", name).group(1).upper()
    moved = re.findall(r"^\(OCCURS \(((?:LOAD|UNLOAD) (?!%s )\S+ .*)\) (\d+)\)$" % pkg,
                       open(raw).read(), re.M)
    if moved:
        print(f"info: raw plan {name} moves the other package: {moved}")
for ans in sorted(glob.glob(os.path.join(HERE, "goals", "*-clean.answer"))):
    name = os.path.basename(ans)[:-len("-clean.answer")]
    if not re.search(pat, name):
        continue
    m = re.match(r"(grid\d+x\d+-\d+)-(pkg\d+)-(p\d+-\d+)$", name)
    pkg = m.group(2).upper()
    acts = {}
    for a, s in re.findall(r"^\(OCCURS \((.*)\) (\d+)\)$", open(ans).read(), re.M):
        acts.setdefault(int(s), []).append(a)
    last = max(acts)
    problems = []
    multi = [s for s, a in acts.items() if len(a) > 1]
    gaps = [s for s in range(1, last) if s not in acts]
    if multi:
        problems.append(f"several actions at slices {multi}")
    if gaps:
        problems.append(f"no action at slices {gaps}")
    other = [a for s in acts for a in acts[s]
             if (a.startswith("LOAD") or a.startswith("UNLOAD")) and a.split()[1] != pkg]
    if other:
        problems.append(f"moves another package: {other}")
    if problems:
        bad += 1
        print(f"{name}: " + "; ".join(problems))
for ev in sorted(glob.glob(os.path.join(HERE, "evidence", "*-obs*.txt"))):
    name = os.path.basename(ev)[:-len(".txt")]
    if not re.search(pat, name):
        continue
    k = int(re.search(r"-obs(\d+)$", name).group(1))
    n = len(re.findall(r"\(occurs ", open(ev).read()))
    if n != k:
        bad += 1
        print(f"{name}: {n} observed actions, expected {k}")
print(f"{bad} problem(s)")
sys.exit(1 if bad else 0)
