#!/bin/bash
# E4 on the testbed: E5's runs (T1, A2/A4, 300 s, seeds 4100-4102) completed with A1, A3, the
# adaptive attack E9P and benign-only, and the two eviction defenses; reuses finished runs.
cd ~/LOFT_ATTACK_MITIGATION/loft_project
while systemctl --user is-active -q chain2 || systemctl --user is-active -q tb-feq2; do sleep 60; done
echo "E4 start $(date +%T)"
E5_TAG=e5c E5_DOM=T1 E5_VARS="A2 A4 A1 A3 E9P benign" \
E5_DEFS="none dms-btt ftmaster ftop rdefender dualguard dualguard+portguard dualguard+evict dualguard+fairevict" \
  bash testbed/matrix_e5.sh > ~/loft-runs/e4_matrix.log 2>&1
echo "E4 done $(date +%T)"
