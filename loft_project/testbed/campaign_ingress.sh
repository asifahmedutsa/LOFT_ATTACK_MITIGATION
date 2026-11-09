#!/bin/bash
# Development check of docs/ingress_plan.md: FEVER with ingress blocking (fever-fl-ll) against the
# old block (fever-fl-ll-noing), T1B at 600 pps, A2 / A4 / E9P / benign, seeds 4181-4182 (16 runs),
# plus FTMaster on E9P (2 runs, its source blocks now in the switch); about 2.3 h. Waits until the
# snapshot carries the change (sudo bash testbed/root/install.sh); analysis in analyze_ingress.py.
set -u
cd "$(dirname "$0")/.."
until grep -q "fever-fl-ll-noing" /opt/loft-testbed/code/testbed/loft_ryu_app.py 2>/dev/null \
        && ! pgrep -x chrome >/dev/null; do sleep 30; done
echo "## ingress start $(date +%T)"
E5_TAG=ing E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5 E5_VARS="A2 A4 E9P benign" \
    E5_DEFS="fever-fl-ll fever-fl-ll-noing" E5_SEEDS="4181 4182" bash testbed/matrix_e5.sh
E5_TAG=ing E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5 E5_VARS="E9P" E5_DEFS="ftmaster" \
    E5_SEEDS="4181 4182" bash testbed/matrix_e5.sh
python3 testbed/analyze_ingress.py
echo "## ingress done $(date +%T)"
