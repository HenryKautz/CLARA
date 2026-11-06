#!/bin/bash
# make-stubs.sh DIR -- stand-in executables for make-intermediates.py ($CLARA_STUBS):
# one in DIR for every solver/counter/preprocessor name in FiFO's solvers.dat
# (and the executables they need), each printing "SOLVER CALLED: <name> <args>"
# to stderr and exiting 99.  FiFO may discard a solver's stderr, so each also
# appends that line to $CLARA_STUB_TRACE (make-intermediates.py sets it to the
# run's own log), else to DIR/calls.log.  solvers.dat is read from $FIFO_LISP,
# else ~/lib/fifo/lisp.
DIR=${1:?usage: make-stubs.sh DIR}
DAT="${FIFO_LISP:-$HOME/lib/fifo/lisp}/solvers.dat"
[[ -f "$DAT" ]] || { echo "no $DAT" >&2; exit 2; }
mkdir -p "$DIR"
names=$(awk '!/^#/ && NF >= 2 {print $2}' "$DAT")
names="$names $(awk '!/^#/ && NF >= 4 {print $4}' "$DAT" | tr ',' '\n' | sed -n 's/^needs://p')"
names="$names sharpSAT flow_cutter_pace17 maxpre walksat d4 addmc kissat"
for n in $names; do
  printf '#!/bin/sh\necho "SOLVER CALLED: %s $*" >&2\necho "SOLVER CALLED: %s $*" >> "${CLARA_STUB_TRACE:-%s/calls.log}"\nexit 99\n' "$n" "$n" "$DIR" > "$DIR/$n"
  chmod +x "$DIR/$n"
done
ls "$DIR"
