#!/bin/bash
# Amendment 3 of docs/final_campaign_prereg.md: DMS-BTT evicting above H1 as its paper does
# (dms-btt-h1, dms-btt-h1-pool), in every cell DMS-BTT ran in the final campaign; 64 runs, the same
# loop and order as campaign_final.sh (by seed, then trace and traffic), and a second pass that reruns
# once every run that failed or was invalid. Run names fin_<trace>_<traffic>_<method>_s<seed>.
#   bash testbed/campaign_am3.sh            # the campaign
#   bash testbed/campaign_am3.sh smoke      # one run first: T1B Spoof, seed 4161, tag smoke
set -u
cd "$(dirname "$0")/.."
grep -q "### Amendment 3" docs/final_campaign_prereg.md || { echo "amendment 3 not recorded"; exit 1; }

run() {   # trace traffic seed methods [tag]
    while pgrep -x chrome >/dev/null || pgrep -x zoom >/dev/null; do sleep 60; done
    E5_TAG=${5:-fin} E5_DUR=300 E5_DOM=$1 E5_TOPO=tree3 E5_BSCALE=$([ "$1" = UHt ] && echo 1.0 || echo 0.5) \
        E5_VARS="$2" E5_DEFS="$4" E5_SEEDS="$3" bash testbed/matrix_e5.sh
}

if [ "${1:-}" = smoke ]; then
    run T1B A5 4161 dms-btt-h1 smoke
    exit $?
fi

methods() {   # trace traffic seed -> the methods of that cell (empty if the seed is not in it)
    local tr=$1 v=$2 s=$3
    if [ "$tr" = UHt ]; then
        case $v in A2|A4|E9P|benign) [ "$s" -le 4162 ] && echo dms-btt-h1 ;; esac
        return
    fi
    case $v in
        A2|A5|A7|benign) [ "$s" -le 4162 ] && echo dms-btt-h1 ;;
        A4|E9P|A6|EVX) echo "dms-btt-h1 dms-btt-h1-pool" ;;
    esac
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
done
{ echo "# Amendment 3 reruns (runs invalid or failed once; a run listed twice is missing)"; echo
  ls ~/loft-runs/_failed 2>/dev/null | grep -E '^fin_.*_dms-btt-h1' | sed 's/^/- /'; } \
    > results/testbed_prereg_final/reruns_am3.md
echo "## amendment 3 done $(date '+%F %T')"
