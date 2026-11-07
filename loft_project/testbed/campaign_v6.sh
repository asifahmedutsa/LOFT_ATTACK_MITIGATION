#!/bin/bash
# FEVER v6 (permanent blocking, docs/v6_plan.md) on the testbed: T1B, A2/A4/E9P/benign, seeds
# 4140-4144, the seeds of the v5 campaign so v6 and v5 pair run by run. Run names
# v5_T1B_<variant>_ensguard-v6_s<seed>; finished runs are skipped.
cd "$(dirname "$0")/.."
while pgrep -f "^/usr/bin/python3 /opt/loft-testbed/code/testbed/run_testbed.py" > /dev/null; do sleep 10; done
for s in ${V6_SEEDS:-4140 4141 4142 4143 4144}; do
    echo "## v6 T1B seed $s $(date +%T)"
    E5_TAG=v5 E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5 E5_VARS="A2 A4 E9P benign" E5_DEFS="ensguard-v6" \
        E5_SEEDS=$s bash testbed/matrix_e5.sh
done
echo "## v6 done $(date +%T)"
