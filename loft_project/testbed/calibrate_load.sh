#!/bin/bash
# Testbed load calibration (gate G0 of docs/testbed_plan.md, rerun after the 2026-11-03 overload):
# benign-only runs with no defense on the tree topology, T1, at several benign scales.
# Step 1: seed 4110 (the heaviest benign trace seen so far) at each scale in SCALES.
# Step 2 (CAL_STEP=2 CAL_SCALE=<s>): the chosen scale on every seed in CAL_SEEDS.
# G0: benign-only lost first packets <= 0.1 % and probe success 100 %.
#
#   bash testbed/calibrate_load.sh                       # step 1
#   CAL_STEP=2 CAL_SCALE=0.5 bash testbed/calibrate_load.sh
set -u
cd "$(dirname "$0")/.."
if [ "${CAL_STEP:-1}" = 1 ]; then
    pre=cal
    for sc in ${SCALES:-1.0 0.75 0.5}; do
        tag="cal$(echo "$sc" | tr -d .)"
        echo "## scale $sc $(date +%T)"
        E5_TAG=$tag E5_DOM=T1 E5_TOPO=tree3 E5_VARS=benign E5_DEFS=none E5_SEEDS=4110 \
            E5_BSCALE=$sc bash testbed/matrix_e5.sh
    done
else
    sc=${CAL_SCALE:?set CAL_SCALE}
    pre=g0
    tag="g0$(echo "$sc" | tr -d .)"
    E5_TAG=$tag E5_DOM=T1 E5_TOPO=tree3 E5_VARS=benign E5_DEFS=none \
        E5_SEEDS="${CAL_SEEDS:-4120 4121 4122 4123 4124}" E5_BSCALE=$sc bash testbed/matrix_e5.sh
fi
for d in ~/loft-runs/${pre}*_T1_benign_none_s*; do
    [ -f "$d/summary.txt" ] || continue
    printf "%-36s lost=%s probe_pre=%s probe_post=%s flows=%s\n" "$(basename "$d")" \
        "$(awk '/benign_packet_in_lost_pct/{print $2}' "$d/summary.txt")" \
        "$(awk '/probe_pre_success_pct/{print $2}' "$d/summary.txt")" \
        "$(awk '/probe_post_success_pct/{print $2}' "$d/summary.txt")" \
        "$(awk '/benign_flows/{print $2}' "$d/summary.txt")"
done
