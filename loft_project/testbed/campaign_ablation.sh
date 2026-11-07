#!/bin/bash
# FEVER ablation on the testbed (docs/fever_ablation_plan.md): FEVER without the detector
# (ensguard-v5-noml: volume block + PortGuard only) and rDefender (the closest published
# per-port occupancy defense) on T1B, A2/A4/E9P/benign, seeds 4140-4142
# by default (ABL_SEEDS overrides). FEVER (ensguard-v5) and FEVER without the volume block
# (ensguard-v4lite) already ran on these seeds in the v5 campaign, with the same code, and are
# reused. Run names v5_T1B_<variant>_ensguard-v5-noml_s<seed>; finished runs are skipped.
cd "$(dirname "$0")/.."
while pgrep -f "^/usr/bin/python3 /opt/loft-testbed/code/testbed/run_testbed.py" > /dev/null; do sleep 10; done
for s in ${ABL_SEEDS:-4140 4141 4142}; do
    echo "## ablation T1B seed $s $(date +%T)"
    E5_TAG=v5 E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5 E5_VARS="A2 A4 E9P benign" E5_DEFS="ensguard-v5-noml rdefender" \
        E5_SEEDS=$s bash testbed/matrix_e5.sh
done
echo "## ablation done $(date +%T)"
