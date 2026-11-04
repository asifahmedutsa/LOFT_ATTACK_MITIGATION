#!/bin/bash
# T1 campaign of preregistration v3 (results/testbed_prereg_v3): seed-major, so each seed's
# table is complete before the next seed starts. Finished runs (with summary.txt) are skipped,
# so the script can be restarted. Waits for any running testbed run first (by the root runner's
# own command line, which this script's does not contain).
cd "$(dirname "$0")/.."
FINAL=ensguard
DEFS="none evict sift tableguard dms-btt ftmaster ftop rdefender dualguard+portguard+hostid $FINAL"
while pgrep -f "^/usr/bin/python3 /opt/loft-testbed/code/testbed/run_testbed.py" > /dev/null; do sleep 10; done
for s in ${V3_SEEDS:-4120 4121 4122 4123 4124}; do
    echo "## T1 seed $s $(date +%T)"
    E5_TAG=v3 E5_DOM=T1 E5_TOPO=tree3 E5_BSCALE=0.5 E5_VARS="A2 A4 E9P benign" E5_DEFS="$DEFS" \
        E5_SEEDS=$s bash testbed/matrix_e5.sh
done
echo "## campaign done $(date +%T)"
