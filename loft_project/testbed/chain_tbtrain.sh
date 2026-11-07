#!/bin/bash
# The whole of docs/testbed_training_plan.md up to the detector choice, unattended: waits for the
# univ2 calibration (record_tbtrain.sh cal), applies gate G0, confirms on two more seeds, records
# the training and T1B test runs, then builds the rows and trains and evaluates every detector.
#
#   systemd-run --user --unit=tbt-chain bash testbed/chain_tbtrain.sh
#
# G0 (benign only): lost first packets <= 0.1 % and probe success 100 %. If univ2 fails at
# 1,000 pps it is recorded at 500 pps (scale 0.5) under the tag tbt5, after G0 at that rate.
set -u
cd "$(dirname "$0")/.."
RUNS="$HOME/loft-runs"
while systemctl --user is-active -q tbt-cal2; do sleep 30; done
wait_chrome() { while pgrep -x chrome >/dev/null || pgrep -x zoom >/dev/null; do sleep 30; done; }

rec() {   # tag, domain, attacks, seeds, benign scale
    wait_chrome
    E5_TAG=$1 E5_DOM=$2 E5_TOPO=tree3 E5_BSCALE=$5 E5_VARS="$3" E5_DEFS=none E5_SEEDS="$4" \
        E5_EXTRA=--entry-log bash testbed/matrix_e5.sh
}
g0() {    # run names -> prints "pass <worst domain>" or "fail"
    worst=""; wl=-1; ok=1
    for n in "$@"; do
        s="$RUNS/$n/summary.txt"
        [ -f "$s" ] || { ok=0; continue; }
        lost=$(awk '/benign_packet_in_lost_pct/{print $2}' "$s")
        pre=$(awk '/probe_pre_success_pct/{print $2}' "$s")
        post=$(awk '/probe_post_success_pct/{print $2}' "$s")
        echo "  G0 $n lost=$lost probe_pre=$pre probe_post=$post" >&2
        awk -v l="$lost" -v a="$pre" -v b="$post" 'BEGIN{exit !(l<=0.1 && a>=100 && b>=100)}' || ok=0
        if awk -v l="$lost" -v w="$wl" 'BEGIN{exit !(l>w)}'; then wl=$lost; worst=$(echo "$n" | cut -d_ -f2); fi
    done
    [ $ok = 1 ] && echo "pass $worst" || echo fail
}

TAG=tbt; U=1.0
r=$(g0 tbt_U1t_benign_none_s4190 tbt_U2t_benign_none_s4190 tbt_UHt_benign_none_s4190)
echo "## G0 at 1,000 pps: $r $(date +%T)"
if [ "${r%% *}" = pass ]; then
    w=${r#* }
    rec tbt "$w" benign "4191 4192" 1.0
    r2=$(g0 tbt_${w}_benign_none_s4191 tbt_${w}_benign_none_s4192)
    echo "## G0 confirmation on $w: $r2 $(date +%T)"
    [ "${r2%% *}" = pass ] || { TAG=tbt5; U=0.5; }
else
    TAG=tbt5; U=0.5
fi
if [ $TAG = tbt5 ]; then
    for d in U1t U2t UHt; do rec tbt5 $d benign 4190 0.5; done
    r=$(g0 tbt5_U1t_benign_none_s4190 tbt5_U2t_benign_none_s4190 tbt5_UHt_benign_none_s4190)
    echo "## G0 at 500 pps: $r $(date +%T)"
    [ "${r%% *}" = pass ] || { echo "## G0 fails at 500 pps too: stopped for a decision"; exit 1; }
fi
echo "## recording with tag $TAG, univ2 scale $U $(date +%T)"
rec $TAG U1t "A1 A4 benign" "4170 4171 4172" $U
rec $TAG U2t "A2 A5 benign" "4170 4171 4172" $U
rec $TAG T1A "A3 A7 benign" "4170 4171 4172" 0.5
rec $TAG T1A benign "4173 4174 4175" 0.5
rec $TAG T1B "A1 A2 A3 A4 A5 A6 A7 E9P benign" "4176 4177 4178" 0.5
echo "## recordings done $(date +%T)"
ls -d "$RUNS"/${TAG}_*_s417[0-8] 2>/dev/null | while read d; do [ -f "$d/summary.txt" ] || echo "## missing summary: $d"; done
n=$(ls -d "$RUNS"/${TAG}_*_s417[0-8] 2>/dev/null | wc -l); echo "## $n of 57 recordings present"

# Offline: rows, central models, Flower bagging, FedProx, lossless, evaluation (no testbed running).
export TBFL_TAG=$TAG FL_OUT=results/tbfl
PYTHONPATH=. nice -n 10 ~/.venvs/loft/bin/python -m loftbench.tbfl rows || exit 1
PYTHONPATH=. nice -n 10 ~/.venvs/loft/bin/python -m loftbench.tbfl central || exit 1
nice -n 10 ~/.venvs/fl/bin/python fl/run_fedxgb.py > results/tbfl/fedxgb_run.log 2>&1 || exit 1
PYTHONPATH=. nice -n 10 ~/.venvs/fl/bin/python fl/run_fedprox.py > results/tbfl/fedprox_run.log 2>&1 || exit 1
nice -n 10 ~/.venvs/fl/bin/python fl/run_fedxgb_hist.py > results/tbfl/fedxgb_hist_run.log 2>&1 || exit 1
PYTHONPATH=. nice -n 10 ~/.venvs/loft/bin/python -m loftbench.tbfl evaluate || exit 1
echo "## chain done $(date +%T)"
