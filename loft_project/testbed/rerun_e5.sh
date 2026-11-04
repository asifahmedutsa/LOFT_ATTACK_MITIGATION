#!/bin/bash
# Redo E5 runs whose machine was loaded by something else: the new-connection probe already
# failed before the attack (probe_pre_success_pct < 90). Moves them to _failed with a reason and
# reruns the matrices, which skip runs that still have summary.txt. Repeats until clean or 3
# passes. Waits for any running matrix (the lock in matrix_e5.sh) first.
#
#   bash testbed/rerun_e5.sh [extra run names to redo...]
set -u
cd "$(dirname "$0")/.."
RUNS="$HOME/loft-runs"
exec 8>"$RUNS/.matrix.lock"; flock 8; exec 8>&-     # wait for a running matrix to finish
mkdir -p "$RUNS/_failed"
for name in "$@"; do
    [ -d "$RUNS/$name" ] && mv "$RUNS/$name" "$RUNS/_failed/$name.loaded-machine"
done
for pass in 1 2 3; do
    bad=0
    for s in "$RUNS"/e5c_T1_*/summary.txt; do
        pre=$(awk '/probe_pre_success_pct/{print int($2)}' "$s")
        if [ "${pre:-0}" -lt 90 ]; then
            d=$(dirname "$s"); echo "pass $pass: redo $(basename "$d") (probe before attack ${pre}%)"
            mv "$d" "$RUNS/_failed/$(basename "$d").loaded-machine.$(date +%s)"; bad=1
        fi
    done
    [ $bad -eq 0 ] && [ $pass -gt 1 ] && break
    E5_TAG=e5c bash testbed/matrix_e5.sh
    E5_TAG=e5c E5_DEFS="dualguard+portguard dualguard+hold dualguard+portguard+hold" bash testbed/matrix_e5.sh
done
echo "rerun done $(date +%T)"
