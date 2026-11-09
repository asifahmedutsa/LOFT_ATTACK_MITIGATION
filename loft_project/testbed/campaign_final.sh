#!/bin/bash
# Final testbed campaign (docs/final_campaign_prereg.md, section 5): seeds 4160-4164, one run at a
# time, by seed, then trace and traffic, then method; the 600 s check last. A second pass reruns once,
# with the same seed, every run that failed or was invalid in the first (matrix_e5.sh skips finished
# runs and moves invalid ones to ~/loft-runs/_failed); a run invalid twice stays missing.
# Run names fin_<trace>_<traffic>_<method>_s<seed> (fin600_ for the 600 s check), as
# testbed/analyze_final.py reads them. Start only after the preregistration is fixed (hashed).
set -u
cd "$(dirname "$0")/.."
[ -f results/testbed_prereg_final/preregistration.json ] || { echo "preregistration not fixed"; exit 1; }
FEV=fever-fl-ll
SIX="ftmaster ftop ftodefender flora dms-btt rdefender"
POOL="ftmaster-pool ftop-pool ftodefender-pool flora-pool dms-btt-pool"
ABL="fever-ll-local fever-ll-novol fever-noml fever-fl-ll-noing"
UH="none ftmaster dms-btt rdefender $FEV"

methods() {   # trace traffic seed -> the methods of that cell (empty if the seed is not in it)
    local tr=$1 v=$2 s=$3 base="none $SIX $FEV"
    if [ "$tr" = UHt ]; then
        case $v in A2|A4|E9P|benign) [ "$s" -le 4162 ] && echo "$UH" ;; esac
        return
    fi
    case $v in
        A5|A7|benign) [ "$s" -le 4162 ] && echo "$base" ;;
        A2)  [ "$s" -le 4162 ] && echo "$base $ABL" ;;
        A4|E9P) echo "$base $POOL $ABL" ;;
        A6|EVX) echo "$base $POOL" ;;
    esac
}

run() {   # trace traffic seed methods [duration tag]
    while pgrep -x chrome >/dev/null || pgrep -x zoom >/dev/null; do sleep 60; done
    E5_TAG=${6:-fin} E5_DUR=${5:-300} E5_DOM=$1 E5_TOPO=tree3 E5_BSCALE=$([ "$1" = UHt ] && echo 1.0 || echo 0.5) \
        E5_VARS="$2" E5_DEFS="$4" E5_SEEDS="$3" bash testbed/matrix_e5.sh
}

for pass in 1 2; do
    echo "## pass $pass start $(date '+%F %T')"
    for s in 4160 4161 4162 4163 4164; do
        for tr in T1B UHt; do
            for v in A2 A5 A7 A4 E9P A6 EVX benign; do
                ms=$(methods "$tr" "$v" "$s")
                [ -n "$ms" ] || continue
                run "$tr" "$v" "$s" "$ms" || exit 1
            done
        done
    done
    for v in A4 E9P; do run T1B "$v" 4160 "$FEV dms-btt ftmaster" 600 fin600 || exit 1; done
done
mkdir -p results/testbed_prereg_final
{ echo "# Reruns (runs invalid or failed once; a run listed twice is missing)"; echo
  ls ~/loft-runs/_failed 2>/dev/null | grep -E '^fin(600)?_' | sed 's/^/- /'; } > results/testbed_prereg_final/reruns.md
python3 testbed/analyze_final.py > /dev/null
echo "## campaign done $(date '+%F %T')"
