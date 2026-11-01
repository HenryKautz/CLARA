#!/usr/bin/env python3
"""exact-marginals.py BASE SCNF EVIDENCE -- exact marginals of every variable of
BASE-2020.wcnf, without and with EVIDENCE, written to BASE.solution.

A SimpleGrid theory's models are exactly the truck's walks: it starts at p1-1 and
takes H-1 steps, each a drive to a grid neighbour or a wait, ending on a goal
cell at slice H.  (FiFO verified that the drive actions and final-slice goal
atoms determine every other atom, and every compiled circuit's model count
equals the number of such walks.)  A model's weight is w^(number of drives),
w the weight of a true drive literal -- read here from BASE-2020.wcnf, which
must give every drive variable the same weight and nothing else a weight.  So a
forward/backward dynamic program over the walks gives Z and every marginal:
  P(HOLDS (AT TRUCK1 p) t)          = alpha_t(p) beta_t(p) / Z
  P(OCCURS (DRIVE TRUCK1 a b) t)    = alpha_t(a) w beta_{t+1}(b) / Z
The evidence is pinned drives, (occurs (drive truck1 a b) t): at step t only
that drive is allowed.  Every variable in BASE.map must be one of those two
kinds of atom, at a slice the horizon allows, or the script stops."""
import math, re, sys

base, scnf, evfile = sys.argv[1:4]
head = "".join(l for l, _ in zip(open(scnf), range(5)))
H = int(re.search(r"fifo-projection-horizon: (\d+)", head).group(1))
goals = {(int(a), int(b)) for a, b in
         re.findall(r"P(\d+)-(\d+)", re.search(r"fifo-projection-goal: (.*)", head).group(1))}
N = int(re.search(r"grid(\d+)x", scnf).group(1))

atoms = {}
for line in open(base + ".map"):
    v, a = line.rstrip("\n").split(" ", 1)
    atoms[int(v)] = a
weights = {}
for line in open(base + "-2020.wcnf"):
    if line.startswith("w "):
        f = line.split()
        weights[int(f[1])] = float(f[2])
drive_re = re.compile(r"\(OCCURS \(DRIVE TRUCK1 P(\d+)-(\d+) P(\d+)-(\d+)\) (\d+)\)$")
at_re = re.compile(r"\(HOLDS \(AT TRUCK1 P(\d+)-(\d+)\) (\d+)\)$")
ws = set()
for v, w in weights.items():
    if v < 0 or not drive_re.match(atoms[v]):
        sys.exit(f"unexpected weighted literal {v} {atoms.get(abs(v))}")
    ws.add(w)
if len(ws) != 1:
    sys.exit(f"drive weights differ: {ws}")
w = ws.pop()
if sum(1 for a in atoms.values() if drive_re.match(a)) != len(weights):
    sys.exit("not every drive variable has a weight")

pinned = {}
for a, b, c, d, t in re.findall(r"\(occurs \(drive truck1 p(\d+)-(\d+) p(\d+)-(\d+)\) (\d+)\)",
                                open(evfile).read()):
    pinned[int(t)] = ((int(a), int(b)), (int(c), int(d)))
if len(pinned) != 2:
    sys.exit(f"expected 2 pinned drives in {evfile}, found {len(pinned)}")

cells = [(r, c) for r in range(1, N + 1) for c in range(1, N + 1)]


def moves(p, t, ev):
    """(q, weight) for the steps allowed from cell p at step t."""
    if ev and t in pinned:
        a, b = pinned[t]
        return [(b, w)] if p == a else []
    r, c = p
    out = [(p, 1.0)]
    for q in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
        if 1 <= q[0] <= N and 1 <= q[1] <= N:
            out.append((q, w))
    return out


def solve(ev):
    alpha = {1: {p: (1.0 if p == (1, 1) else 0.0) for p in cells}}
    for t in range(1, H):
        nxt = {p: 0.0 for p in cells}
        for p in cells:
            for q, wt in moves(p, t, ev):
                nxt[q] += alpha[t][p] * wt
        alpha[t + 1] = nxt
    beta = {H: {p: (1.0 if p in goals else 0.0) for p in cells}}
    for t in range(H - 1, 0, -1):
        beta[t] = {p: sum(wt * beta[t + 1][q] for q, wt in moves(p, t, ev)) for p in cells}
    Z = beta[1][(1, 1)]
    marg = {}
    for v, a in atoms.items():
        m = at_re.match(a)
        if m:
            p, t = (int(m.group(1)), int(m.group(2))), int(m.group(3))
            if not 1 <= t <= H:
                sys.exit(f"atom outside the horizon: {a}")
            marg[v] = alpha[t][p] * beta[t][p] / Z
            continue
        m = drive_re.match(a)
        if m:
            p, q, t = ((int(m.group(1)), int(m.group(2))), (int(m.group(3)), int(m.group(4))),
                       int(m.group(5)))
            if not 1 <= t < H:
                sys.exit(f"atom outside the horizon: {a}")
            wt = dict(moves(p, t, ev)).get(q, 0.0) if p != q else 0.0
            marg[v] = alpha[t][p] * wt * beta[t + 1][q] / Z
            continue
        sys.exit(f"atom of an unexpected kind: {a}")
    return Z, marg


Z0, m0 = solve(False)
Z1, m1 = solve(True)
name = base.rsplit("/", 1)[-1]
with open(base + ".solution", "w") as f:
    f.write(f"c Exact marginals for {name}: every variable of {name}-2020.wcnf / -2024.wcnf\n"
            f"c (column P0) and of {name}-ev2-2020.wcnf / -ev2-2024.wcnf (column P2, with\n"
            f"c the 2 pinned drives of {name}.evidence).  The variable numbering is the same\n"
            f"c in all four files; {name}.map names each variable.\n"
            f"c Computed by exact-marginals.py: a forward/backward dynamic program over the\n"
            f"c truck's walks (see README.md), each drive weighted {w!r}.\n"
            f"c Z0 {Z0!r}   (log Z0 {math.log(Z0)!r})\n"
            f"c Z2 {Z1!r}   (log Z2 {math.log(Z1)!r})\n"
            f"c var P0 P2 atom\n")
    for v in sorted(atoms):
        f.write(f"{v} {m0[v]:.15g} {m1[v]:.15g} {atoms[v]}\n")
print(f"{name}: {len(atoms)} variables, Z0 {Z0:.6g}, Z2 {Z1:.6g}")
