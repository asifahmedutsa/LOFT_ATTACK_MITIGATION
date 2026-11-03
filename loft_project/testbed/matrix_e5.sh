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
# Skips runs that already have summary.txt. E5_TAG (default e5) prefixes run names; E5_DEFS
# E5_TOPO=tree3 runs the three-switch tree (run_testbed.py --topo). E5_DEFS
# overrides the defense list of the full matrix, E5_VARS the attacks (default A2 A4) and E5_DOM the
# domain (default T1). A lock stops
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
    for v in ${E5_VARS:-A2 A4}; do
        for def in ${E5_DEFS:-none dms-btt ftmaster ftop rdefender dualguard}; do
            for s in ${E5_SEEDS:-4100 4101 4102}; do specs+=("${E5_DOM:-T1} $v $def $s 300 $TAG"); done
        done
    done
fi
n=0
for sp in "${specs[@]}"; do
    set -- $sp
    n=$((n + 1))
    # A defense written def@local runs with the local (non-federated) models.
    def="${3%@*}"; prefix=""
    [ "$def" != "$3" ] && prefix="--model-prefix ${3#*@}"
    name="$6_$1_$2_${3//[+@]/-}_s$4"
    if [ -f "$RUNS/$name/summary.txt" ]; then continue; fi
    if [ -e "$RUNS/$name" ]; then
        mkdir -p "$RUNS/_failed"
        mv "$RUNS/$name" "$RUNS/_failed/$name.$(date +%s)"
    fi
    # A controller left over from an interrupted run keeps listening on 6653 (eventlet sets
    # SO_REUSEPORT), and the kernel then hands some switches to it: runs look fine but are not.
    if [ -n "$(ss -Hltn 'sport = :6653')" ]; then
        echo "port 6653 already in use before $name; stop leftover ryu-manager and rerun"; exit 1
    fi
    echo "=== [$n/${#specs[@]}] $name $(date +%T)"
    t_start=$(date +%s)
    sudo -n loft-testbed --domains "$1" --variant "$2" --defense "$def" $prefix --seed "$4" \
        --duration "$5" --probe newflow ${E5_TOPO:+--topo $E5_TOPO} --out "$name" > "$RUNS/$name.log" 2>&1
    status=$?
    if [ $status -ne 0 ] || [ ! -f "$RUNS/$name/controller_$1.csv" ]; then
        echo "    FAILED (exit $status); see $RUNS/$name.log"; continue
    fi
    # Valid: the controller logged until near the end (an overloaded controller polls less often,
    # so the row count alone is not a test) and the wall time was not stretched by a suspend.
    last=$(tail -1 "$RUNS/$name/controller_$1.csv" | cut -d, -f1 | cut -d. -f1)
    took=$(( $(date +%s) - t_start ))
    if ! [ "${last:-0}" -ge $(( $5 * 9 / 10 )) ] 2>/dev/null || [ "$took" -gt $(( $5 * 3 / 2 + 60 )) ]; then
        echo "    INVALID (controller log ends at ${last:-none} s, ${took} s wall); moved to _failed"
        mv "$RUNS/$name.log" "$RUNS/$name/runner.log"
        mkdir -p "$RUNS/_failed"; mv "$RUNS/$name" "$RUNS/_failed/$name.$(date +%s)"; continue
    fi
    mv "$RUNS/$name.log" "$RUNS/$name/runner.log"
    python3 testbed/summarize_run.py "$RUNS/$name" > "$RUNS/$name/summary.txt"
    grep -E "benign_harmed_pct|probe_post_success_pct|probe_post_connect_ms_median|decision_ms" \
        "$RUNS/$name/summary.txt" | tr -s ' ' | paste -sd ' '
done
echo "matrix done $(date +%T)"
