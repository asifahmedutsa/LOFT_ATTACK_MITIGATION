#!/bin/bash
# Recordings for v5's volume block (docs/v5_plan.md, section 3), T1A only (the trace part every
# T1 model and threshold is trained or calibrated on), defense none, entry log, tree3, benign
# scale 0.5 as the test campaign:
#   calibration  benign x seeds 4150-4152 (X = 1.5 x the largest benign host per switch)
#   check        A2, A4, E9P x seed 4153 (would both attackers be blocked?)
# 6 runs, about 35 min. Needs the snapshot reinstalled after the T1A/T1B code.
cd "$(dirname "$0")/.."
E5_TAG=v5vol E5_DOM=T1A E5_TOPO=tree3 E5_BSCALE=0.5 E5_VARS="benign" E5_DEFS=none \
    E5_SEEDS="4150 4151 4152" E5_EXTRA=--entry-log bash testbed/matrix_e5.sh
E5_TAG=v5vol E5_DOM=T1A E5_TOPO=tree3 E5_BSCALE=0.5 E5_VARS="A2 A4 E9P" E5_DEFS=none \
    E5_SEEDS="4153" E5_EXTRA=--entry-log bash testbed/matrix_e5.sh
echo "## v5 volume recordings done $(date +%T)"
