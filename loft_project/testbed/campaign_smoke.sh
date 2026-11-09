#!/bin/bash
# Smoke runs before the final campaign (docs/final_campaign_prereg.md, section 5): one run per new or
# retrained defense on development seed 4183 (A2), EVX with FEVER, and FEVER on UHt (its new
# thresholds); checks that each loads, blocks and logs, not results. 13 runs, about 70 min.
set -u
cd "$(dirname "$0")/.."
while pgrep -x chrome >/dev/null; do sleep 30; done
echo "## smoke start $(date +%T)"
E5_TAG=smk E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5 E5_VARS="A2" E5_SEEDS="4183" \
    E5_DEFS="flora dms-btt ftodefender ftmaster-pool ftop-pool ftodefender-pool flora-pool dms-btt-pool fever-ll-local fever-ll-novol fever-noml" \
    bash testbed/matrix_e5.sh
E5_TAG=smk E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5 E5_VARS="EVX" E5_DEFS="fever-fl-ll" E5_SEEDS="4183" bash testbed/matrix_e5.sh
E5_TAG=smk E5_DOM=UHt E5_TOPO=tree3 E5_BSCALE=1.0 E5_VARS="A2" E5_DEFS="fever-fl-ll" E5_SEEDS="4183" bash testbed/matrix_e5.sh
python3 testbed/check_smoke.py
echo "## smoke done $(date +%T)"
