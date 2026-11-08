#!/bin/bash
# Deployment check of docs/testbed_training_plan.md: FEVER with the detector trained on testbed
# rows (fever-fl, ens_config_fl.json) against FEVER v6 (fever), T1B at 600 pps, A2 / A4 / E9P /
# benign, development seeds 4181-4182 (16 runs, about 2 h). Waits until the snapshot carries
# ens_config_fl.json (sudo bash testbed/root/install.sh), then runs; analysis in analyze_flcheck.py.
set -u
cd "$(dirname "$0")/.."
until [ -f /opt/loft-testbed/code/results/v21/exported/ens_config_fl.json ] && ! pgrep -x chrome >/dev/null; do sleep 30; done
echo "## flcheck start $(date +%T)"
E5_TAG=flc E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5 E5_VARS="A2 A4 E9P benign" E5_DEFS="fever fever-fl" \
    E5_SEEDS="4181 4182" bash testbed/matrix_e5.sh
python3 testbed/analyze_flcheck.py
echo "## flcheck done $(date +%T)"
