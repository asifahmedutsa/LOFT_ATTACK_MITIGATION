#!/bin/bash
# Spoof (A5: forged source addresses) and Pulse (A7: 60 s on / 30 s off) on the testbed, T1B,
# the v5-campaign seeds 4140-4144, so they sit beside the G2 / Mimic / Aware results: no defense,
# FTMaster, DMS-BTT, rDefender and FEVER (ensguard-v6). 50 runs, about 4.5 h. Exploratory.
# Run names v5_T1B_<variant>_<defense>_s<seed>; finished runs are skipped.
cd "$(dirname "$0")/.."
while pgrep -f "^/usr/bin/python3 /opt/loft-testbed/code/testbed/run_testbed.py" > /dev/null; do sleep 10; done
for s in ${SP_SEEDS:-4140 4141 4142 4143 4144}; do
    echo "## spoof/pulse T1B seed $s $(date +%T)"
    E5_TAG=v5 E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5 E5_VARS="${SP_VARS:-A5 A7}" \
        E5_DEFS="${SP_DEFS:-none ftmaster dms-btt rdefender ensguard-v6}" E5_SEEDS=$s bash testbed/matrix_e5.sh
done
echo "## spoof/pulse done $(date +%T)"
