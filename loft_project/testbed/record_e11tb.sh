#!/bin/bash
# Recordings for E11 on the testbed (testbed/e11_testbed.py): T1, tree3, benign scale 0.5 as in
# preregistration v3, defense none (nothing changes the traffic, so every detector is scored on
# the same rows), every entry's counters logged at every poll (--entry-log).
#
#   bash testbed/record_e11tb.sh --smoke   # one A4 run on development seed 4139, then check it
#   bash testbed/record_e11tb.sh           # A2, A4, E9P, benign x seeds 4131-4133 = 12 runs, ~80 min
#
# Needs the snapshot reinstalled with the entry log (sudo bash testbed/root/install.sh).
cd "$(dirname "$0")/.."
if [ "${1:-}" = "--smoke" ]; then
    tag=e11smoke; vars="A4"; seeds=4139
else
    tag=e11tb; vars="A2 A4 E9P benign"; seeds="${E11TB_SEEDS:-4131 4132 4133}"
fi
E5_TAG=$tag E5_DOM=T1 E5_TOPO=tree3 E5_BSCALE=0.5 E5_VARS="$vars" E5_DEFS=none E5_SEEDS="$seeds" \
    E5_EXTRA=--entry-log bash testbed/matrix_e5.sh
echo "## recordings done $(date +%T)"
