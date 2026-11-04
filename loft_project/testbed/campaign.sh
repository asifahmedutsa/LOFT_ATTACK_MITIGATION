#!/bin/bash
# The 3-day core testbed campaign (docs/testbed_plan.md, section 0b), run after T0 passed.
# Three-switch tree, one controller, fresh seeds; blocks run one after another and each skips
# finished runs, so the script can be restarted. Final system: dualguard+portguard+hostid.
cd ~/LOFT_ATTACK_MITIGATION/loft_project
FINAL=dualguard+portguard+hostid
run() { echo "## $1 $(date +%T)"; shift; env "$@" E5_TOPO=tree3 bash testbed/matrix_e5.sh; }
S5="4110 4111 4112 4113 4114"; S3="4110 4111 4112"
run T1 E5_TAG=t1 E5_DOM=T1 E5_SEEDS="$S5" E5_VARS="A2 A4 E9P benign" \
    E5_DEFS="none evict sift tableguard dms-btt ftmaster ftop rdefender $FINAL dualguard+portguard portguard+hostid"
run T1-fed E5_TAG=t1f E5_DOM=D1 E5_SEEDS="$S5" E5_VARS="A2 A6" E5_DEFS="$FINAL $FINAL@local"
run T4 E5_TAG=t4 E5_DOM=T1 E5_SEEDS="$S3" E5_VARS="LA HA ALA A2M" \
    E5_DEFS="none evict rdefender dms-btt ftmaster $FINAL"
for c in 2000 4000; do
    run T2-$c E5_TAG=t2c$c E5_CAP=$c E5_DOM=T1 E5_SEEDS="$S3" E5_VARS="A2" E5_DEFS="none dms-btt ftmaster $FINAL"
done
run T5 E5_TAG=t5 E5_DOM=T2 E5_SEEDS="$S3" E5_VARS="A2 A4" E5_DEFS="none dms-btt sift rdefender $FINAL"
echo "## campaign done $(date +%T)"
