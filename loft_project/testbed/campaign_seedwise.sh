#!/bin/bash
# The 3-day core campaign (testbed/campaign.sh) in seed-major order: every attack x
# configuration of one seed before the next seed, so complete preliminary tables arrive per
# seed and paired comparisons within a seed run close in time. Same runs, same preregistered
# analysis (results/testbed_prereg); finished runs are skipped.
cd ~/LOFT_ATTACK_MITIGATION/loft_project
FINAL=dualguard+portguard+hostid
run() { echo "## $1 $(date +%T)"; shift; env "$@" E5_TOPO=tree3 bash testbed/matrix_e5.sh; }
# Wait for a run left over from the attack-major script to finish.
while pgrep -f run_testbed.py > /dev/null; do sleep 10; done
for s in 4110 4111 4112 4113 4114; do
    run "T1 seed $s" E5_TAG=t1 E5_DOM=T1 E5_SEEDS=$s E5_VARS="A2 A4 E9P benign" \
        E5_DEFS="none evict sift tableguard dms-btt ftmaster ftop rdefender $FINAL dualguard+portguard portguard+hostid"
done
for s in 4110 4111 4112 4113 4114; do
    run "T1-fed seed $s" E5_TAG=t1f E5_DOM=D1 E5_SEEDS=$s E5_VARS="A2 A6" E5_DEFS="$FINAL $FINAL@local"
done
for s in 4110 4111 4112; do
    run "T4 seed $s" E5_TAG=t4 E5_DOM=T1 E5_SEEDS=$s E5_VARS="LA HA ALA A2M" \
        E5_DEFS="none evict rdefender dms-btt ftmaster $FINAL"
    for c in 2000 4000; do
        run "T2-$c seed $s" E5_TAG=t2c$c E5_CAP=$c E5_DOM=T1 E5_SEEDS=$s E5_VARS="A2" \
            E5_DEFS="none dms-btt ftmaster $FINAL"
    done
    run "T5 seed $s" E5_TAG=t5 E5_DOM=T2 E5_SEEDS=$s E5_VARS="A2 A4" E5_DEFS="none dms-btt sift rdefender $FINAL"
done
echo "## campaign done $(date +%T)"
