#!/bin/bash
# Testbed recordings for FEVER's training data (docs/testbed_training_plan.md): defense none,
# tree topology, every entry's counters at every poll (--entry-log). One run at a time, 300 s each;
# finished runs are skipped, so a stage can be restarted.
#
#   bash testbed/record_tbtrain.sh cal      # G0 for univ2 at 1,000 pps: U1t, U2t, UHt benign, seed 4190 (3 runs)
#   CAL_DOM=U2t bash testbed/record_tbtrain.sh cal2   # the worst of them on seeds 4191-4192 (2 runs)
#   bash testbed/record_tbtrain.sh train    # C1-C3 x (2 attacks + benign) x 4170-4172, threshold runs (30 runs)
#   bash testbed/record_tbtrain.sh test     # T1B x 8 attacks + benign x 4176-4178 (27 runs)
#   bash testbed/record_tbtrain.sh uh       # UHt x 8 attacks + benign x 4176-4178 (27 runs, optional)
#
# UNIV_SCALE (default 1.0) multiplies the univ2 rate if G0 fails at 1,000 pps (0.5 = 500 pps).
# Needs the snapshot reinstalled with the univ2 parts (sudo bash testbed/root/install.sh).
set -u
cd "$(dirname "$0")/.."
U=${UNIV_SCALE:-1.0}
rec() {   # domain, attacks, seeds, benign scale
    E5_TAG=tbt E5_DOM=$1 E5_TOPO=tree3 E5_BSCALE=$4 E5_VARS="$2" E5_DEFS=none E5_SEEDS="$3" \
        E5_EXTRA=--entry-log bash testbed/matrix_e5.sh || exit 1
}
ALL="A1 A2 A3 A4 A5 A6 A7 E9P benign"
case "${1:-}" in
    cal)   for d in U1t U2t UHt; do rec $d benign 4190 "$U"; done ;;
    cal2)  rec "${CAL_DOM:?set CAL_DOM}" benign "4191 4192" "$U" ;;
    train) rec U1t "A1 A4 benign" "4170 4171 4172" "$U"
           rec U2t "A2 A5 benign" "4170 4171 4172" "$U"
           rec T1A "A3 A7 benign" "4170 4171 4172" 0.5
           rec T1A benign "4173 4174 4175" 0.5 ;;
    test)  rec T1B "$ALL" "4176 4177 4178" 0.5 ;;
    uh)    rec UHt "$ALL" "4176 4177 4178" "$U" ;;
    *) echo "usage: $0 cal|cal2|train|test|uh"; exit 2 ;;
esac
for d in ~/loft-runs/tbt_*; do
    [ -f "$d/summary.txt" ] || continue
    printf "%-34s lost=%s probe_post=%s\n" "$(basename "$d")" \
        "$(awk '/benign_packet_in_lost_pct/{print $2}' "$d/summary.txt")" \
        "$(awk '/probe_post_success_pct/{print $2}' "$d/summary.txt")"
done
echo "## record_tbtrain $1 done $(date +%T)"
