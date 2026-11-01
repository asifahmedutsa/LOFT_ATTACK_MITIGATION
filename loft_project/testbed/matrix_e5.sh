#!/bin/bash
# E5 (docs/other_papers_run_plan.md): service-level harm on Mininet/Ryu, as LOFT and ALFO-Guard
# measure it. While the bigFlows trace (T1) is replayed under attack, a benign host opens a new
# TCP connection to the server every 0.5 s (testbed/probe_newflow.py); we report the share that
# succeed and their setup time, next to the usual benign harm. One run at a time, 300 s each.
#
#   bash testbed/matrix_e5.sh --smoke    # first: each new defense once, 60 s, D1 A2 (7 runs, ~10 min)
#   bash testbed/matrix_e5.sh            # 6 defenses x A2, A4 x seeds 4100-4102 = 36 runs, ~4 h
#
# Needs the snapshot reinstalled after the E5 code (sudo bash testbed/root/install.sh).
# Skips runs that already have summary.txt. E5_TAG (default e5) prefixes run names. A lock stops
# two matrices from running at once (each run starts with mn -c, which tears down any other run).
set -u
cd "$(dirname "$0")/.."
RUNS="$HOME/loft-runs"
mkdir -p "$RUNS"
exec 9>"$RUNS/.matrix.lock"
flock -n 9 || { echo "another testbed matrix is running"; exit 1; }
TAG="${E5_TAG:-e5}"
specs=()
if [ "${1:-}" = "--smoke" ]; then
    for def in ftmaster ftop flora rdefender dualguard+floodguard dualguard none; do
        specs+=("D1 A2 $def 4100 60 smoke")
    done
else
    for v in A2 A4; do
        for def in none dms-btt ftmaster ftop rdefender dualguard; do
            for s in 4100 4101 4102; do specs+=("T1 $v $def $s 300 $TAG"); done
        done
    done
fi
n=0
for sp in "${specs[@]}"; do
    set -- $sp
    n=$((n + 1))
    name="$6_$1_$2_${3//+/-}_s$4"
    if [ -f "$RUNS/$name/summary.txt" ]; then continue; fi
    if [ -e "$RUNS/$name" ]; then
        mkdir -p "$RUNS/_failed"
        mv "$RUNS/$name" "$RUNS/_failed/$name.$(date +%s)"
    fi
    echo "=== [$n/${#specs[@]}] $name $(date +%T)"
    sudo -n loft-testbed --domains "$1" --variant "$2" --defense "$3" --seed "$4" \
        --duration "$5" --probe newflow --out "$name" > "$RUNS/$name.log" 2>&1
    status=$?
    if [ $status -ne 0 ] || [ ! -f "$RUNS/$name/controller_$1.csv" ]; then
        echo "    FAILED (exit $status); see $RUNS/$name.log"; continue
    fi
    mv "$RUNS/$name.log" "$RUNS/$name/runner.log"
    python3 testbed/summarize_run.py "$RUNS/$name" > "$RUNS/$name/summary.txt"
    grep -E "benign_harmed_pct|probe_post_success_pct|probe_post_connect_ms_median|decision_ms" \
        "$RUNS/$name/summary.txt" | tr -s ' ' | paste -sd ' '
done
echo "matrix done $(date +%T)"
