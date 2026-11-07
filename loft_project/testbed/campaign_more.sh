#!/bin/bash
# More published methods on the v5 test traffic (T1B, tree3, benign scale 0.5): FTOP and FloRa
# (retrained on T1A, loftbench.v5 baselines2) on seeds 4140-4144, and rDefender's two missing
# seeds 4143-4144; A2, A4, E9P and benign. 48 runs, about 4 h 15 min. Run names
# v5_T1B_<variant>_<defense>_s<seed>; finished runs are skipped.
cd "$(dirname "$0")/.."
while pgrep -f "^/usr/bin/python3 /opt/loft-testbed/code/testbed/run_testbed.py" > /dev/null; do sleep 10; done
for s in 4140 4141 4142 4143 4144; do
    defs="ftop flora"
    [ "$s" -ge 4143 ] && defs="ftop flora rdefender"
    echo "## more T1B seed $s ($defs) $(date +%T)"
    E5_TAG=v5 E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5 E5_VARS="A2 A4 E9P benign" E5_DEFS="$defs" \
        E5_SEEDS=$s bash testbed/matrix_e5.sh
done
echo "## more done $(date +%T)"
