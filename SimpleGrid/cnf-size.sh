#!/bin/bash
# cnf-size.sh <evidence/...-obsN.txt> : print "<evidence> <horizon> <vars> <clauses>"
# for the propositional CNF recognize.sh builds for that pinned evidence file --
# the instantiated problem plus the evidence, as every --counter method receives
# it (they all start from the same rec-problem.scnf; max-term then adds its own
# soft clauses for scoring hypotheses).  Run from SimpleGrid/.
set -u
ev="$1"
name="$(basename "$ev" .txt)"
prob="${name%-p*-obs*}.pddl"
out="/tmp/sg-cnf-size/$name"
rm -rf "$out"; mkdir -p "$out"
bash ~/bin/recognize.sh clara-logistics.pddl "$prob" "$ev" --evidence-kind fifo --out "$out" >"$out.log" 2>&1
h="$(sed -n 's/^Horizon H = \([0-9]*\).*/\1/p' "$out.log")"
cat "$out/rec-problem.scnf" "$out/rec-problem-evidence.scnf" > "$out/both.scnf"
(cd "$out" && sbcl --noinform --non-interactive --eval '(load "~/lib/fifo/lisp/FiFO.lisp")' \
                --eval '(propositionalize "both.scnf")' >/dev/null 2>&1)
read -r _ _ v c < <(grep -m1 '^p ' "$out/both.cnf")
echo "$ev ${h:-?} ${v:-?} ${c:-?}"
rm -rf "$out" "$out".log "$out"-*
