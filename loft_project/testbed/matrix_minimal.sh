#!/bin/bash
# Minimal Mininet/Ryu confirmation matrix (results_v2.md 18): 48 runs of 300 s, one at a time,
# through the passwordless runner (testbed/root/install.sh). The simulator carries the
# statistics; this matrix confirms it cell by cell on the real controller loop.
#
#   bash testbed/matrix_minimal.sh            # runs whatever is not done yet; safe to rerun
#   bash testbed/matrix_minimal.sh --list     # print the runs and exit
#
# Run names: m1_<domain>_<variant>_<defense>_s<seed> in ~/loft-runs/. A run whose directory
# has a summary.txt is complete and skipped; a directory without one (an interrupted run) is
# moved to ~/loft-runs/_failed/ and the run repeated. Do not run simulator jobs at the same time.
set -u
cd "$(dirname "$0")/.."
RUNS="$HOME/loft-runs"
DEF4="none dms-btt dualguard dualguard+portguard"

specs=()
for d in D1 D2 D3 T1; do                      # main table
    for v in A2 A4; do
        for f in $DEF4; do specs+=("$d $v $f 4000"); done
    done
done
for d in D1 T1; do                                                        # false alarms
    for f in dualguard dualguard+portguard; do specs+=("$d benign $f 4000"); done
done
for s in 4001 4002; do                                                    # seed check
    for v in A2 A4; do
        for f in dms-btt dualguard+portguard; do specs+=("D1 $v $f $s"); done
    done
done

# Fast refresh last: on this machine it saturates Ryu (about 500 Packet-Ins/s) whatever the
# defense (results_v2.md 16.8); these runs record that limit.
for f in $DEF4; do specs+=("D1 X1 $f 4000"); done

name_of() { echo "m1_$1_$2_${3//+/_}_s$4"; }

if [ "${1:-}" = "--list" ]; then
    for sp in "${specs[@]}"; do set -- $sp; name_of "$@"; done
    echo "${#specs[@]} runs"; exit 0
fi

n=0
for sp in "${specs[@]}"; do
    set -- $sp
    n=$((n + 1))
    name="$(name_of "$@")"
    if [ -f "$RUNS/$name/summary.txt" ]; then continue; fi
    if [ -e "$RUNS/$name" ]; then
        mkdir -p "$RUNS/_failed"
        mv "$RUNS/$name" "$RUNS/_failed/$name.$(date +%s)"
    fi
    echo "=== [$n/${#specs[@]}] $name $(date +%T)"
    sudo -n loft-testbed --domains "$1" --variant "$2" --defense "$3" --seed "$4" \
        --duration 300 --out "$name" > "$RUNS/$name.log" 2>&1
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
