#!/bin/bash
# Deployment check of docs/testbed_training_plan.md (amendment 1): FEVER with the detectors trained
# on testbed rows by Flower XGBoost bagging (fever-fl-bag) and lossless federated XGBoost
# (fever-fl-ll) against FEVER v6 (fever), T1B at 600 pps, A2 / A4 / E9P / benign, development seeds
# 4181-4182 (24 runs, about 3 h). Waits until the snapshot carries both configs
# (sudo bash testbed/root/install.sh), then runs; analysis in analyze_flcheck.py.
set -u
cd "$(dirname "$0")/.."
X=/opt/loft-testbed/code/results/v21/exported
until [ -f $X/ens_config_fl_bag.json ] && [ -f $X/ens_config_fl_ll.json ] && ! pgrep -x chrome >/dev/null; do sleep 30; done
echo "## flcheck start $(date +%T)"
E5_TAG=flc E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5 E5_VARS="A2 A4 E9P benign" E5_DEFS="fever fever-fl-bag fever-fl-ll" \
    E5_SEEDS="4181 4182" bash testbed/matrix_e5.sh
python3 testbed/analyze_flcheck.py
echo "## flcheck done $(date +%T)"
