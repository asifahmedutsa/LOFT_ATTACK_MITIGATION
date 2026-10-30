#!/bin/bash
# Local vs federated detector on Mininet/Ryu: 18 runs of 300 s, one at a time.
# Each controller is attacked with variants it never saw in training: the first-listed
# exposure of each other controller, and A6 (unseen by all). Same v2.1 policy; only the
# model differs (--model-prefix local | v21). Simulator reference: testbed/fl_sim_reference.py.
#
#   bash testbed/matrix_fl.sh            # skips runs that already have summary.txt
set -u
cd "$(dirname "$0")/.."
RUNS="$HOME/loft-runs"
specs=()
for cell in "D1 A2" "D1 A3" "D1 A6" "D2 A1" "D2 A3" "D2 A6" "D3 A1" "D3 A2" "D3 A6"; do
    for m in local v21; do specs+=("$cell $m"); done
done
n=0
for sp in "${specs[@]}"; do
    set -- $sp
    n=$((n + 1))
    name="fl_$1_$2_$3_s4000"
    if [ -f "$RUNS/$name/summary.txt" ]; then continue; fi
    if [ -e "$RUNS/$name" ]; then
        mkdir -p "$RUNS/_failed"
        mv "$RUNS/$name" "$RUNS/_failed/$name.$(date +%s)"
    fi
    echo "=== [$n/${#specs[@]}] $name $(date +%T)"
    sudo -n loft-testbed --domains "$1" --variant "$2" --defense dualguard --model-prefix "$3" \
        --seed 4000 --duration 300 --out "$name" > "$RUNS/$name.log" 2>&1
    status=$?
    if [ $status -ne 0 ] || [ ! -f "$RUNS/$name/controller_$1.csv" ]; then
        echo "    FAILED (exit $status); see $RUNS/$name.log"; continue
    fi
    mv "$RUNS/$name.log" "$RUNS/$name/runner.log"
    python3 testbed/summarize_run.py "$RUNS/$name" > "$RUNS/$name/summary.txt"
    grep -E "benign_harmed_pct|benign_packet_in_lost_pct|table_full " "$RUNS/$name/summary.txt" \
        | tr -s ' ' | paste -sd ' '
done
echo "matrix done $(date +%T)"
