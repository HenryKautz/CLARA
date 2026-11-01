"""parallel-evidence.py SCRIPTS_DIR WORKERS -- run-plans.py --stage evidence, per goal
in parallel, for the goals that still need it: planned ok, but not on this server
run (resume.log / retry.log ok lines, whose goals stage wrote current evidence) and
not already logged ok in evidence-N.log by the per-size job this replaces."""
import concurrent.futures as cf, importlib.util, json, os, re, sys

scripts, workers = sys.argv[1], int(sys.argv[2])
sys.path.insert(0, scripts)
spec = importlib.util.spec_from_file_location("run_plans", os.path.join(scripts, "run-plans.py"))
RP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RP)
here = RP.F.HERE

recs = {}
for line in open(RP.RESULTS):
    r = json.loads(line)
    if r["stage"] == "goals" and r["status"] == "ok":
        recs[r["name"]] = r

done = set()
ok_line = re.compile(r"^  (\S+): (?:ok |K=\[[0-9, ]*\] ok$)")
for f in ["resume.log", "retry.log"] + [f"evidence-{n}.log" for n in range(6, 16)]:
    p = os.path.join(here, f)
    if os.path.exists(p):
        for line in open(p):
            m = ok_line.match(line.rstrip("\n"))
            if m:
                done.add(m.group(1))

todo = sorted(g for g in recs if g not in done)
print(f"{len(recs)} goals ok, {len(done & set(recs))} with current evidence, "
      f"{len(todo)} to write, {workers} at a time", flush=True)
if workers == 0:                 # dry run: show the selection by size, write nothing
    import collections
    print(sorted(collections.Counter(recs[g]["size"] for g in todo).items()))
    sys.exit(0)


def one(g):
    return g, RP.write_evidence(g, recs[g]["actions"])


with cf.ThreadPoolExecutor(workers) as ex:
    for g, (ks, err) in ex.map(one, todo):
        print(f"  {g}: K={ks} {'failed: ' + ' | '.join(err[-2:]) if err else 'ok'}", flush=True)
print("done", flush=True)
