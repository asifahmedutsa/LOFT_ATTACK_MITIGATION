#!/bin/bash
# Test campaign of preregistration v5 (results/testbed_prereg_v5/preregistration.json): T1B (the
# part of bigFlows no model or threshold was trained or calibrated on), tree3, benign scale 0.5;
# 6 defenses x A2/A4/E9P/benign x fresh seeds 4140-4144 = 120 runs, seed-major. Finished runs
# are skipped, so the script can be restarted.
cd "$(dirname "$0")/.."
DEFS="none ensguard ensguard-v4lite ensguard-v5 dms-btt ftmaster"
while pgrep -f "^/usr/bin/python3 /opt/loft-testbed/code/testbed/run_testbed.py" > /dev/null; do sleep 10; done
for s in ${V5_SEEDS:-4140 4141 4142 4143 4144}; do
    echo "## T1B seed $s $(date +%T)"
    E5_TAG=v5 E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5 E5_VARS="A2 A4 E9P benign" E5_DEFS="$DEFS" \
        E5_SEEDS=$s bash testbed/matrix_e5.sh
done
echo "## campaign done $(date +%T)"
