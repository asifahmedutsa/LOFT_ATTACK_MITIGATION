#!/bin/bash
# One-host flash crowd on more seeds (docs/crowdseeds_prereg.md): round 2's F2H case (tables of 2,000
# entries), no defense and FEVER x seeds 4200-4209 = 20 runs, by seed then method, and a second pass
# that reruns once every run that failed or was invalid. Run names fc3_T1B_F2H_<method>_s<seed>.
#   bash testbed/campaign_crowdseeds.sh
set -u
cd "$(dirname "$0")/.."
grep -q "^DRAFT" docs/crowdseeds_prereg.md && { echo "docs/crowdseeds_prereg.md is still a draft"; exit 1; }
OUT=results/testbed_crowdseeds
mkdir -p "$OUT"
RUNS="$HOME/loft-runs"
K=$(cat results/testbed_flash2/selected_k.txt)
[ "$K" = 2 ] || { echo "round 2's selected k is $K, not 2"; exit 1; }

run() {   # traffic seed methods tag
    while pgrep -x chrome >/dev/null || pgrep -x zoom >/dev/null; do sleep 60; done
    E5_TAG=$4 E5_DUR=300 E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5 E5_CAP=2000 \
        E5_VARS="$1" E5_DEFS="$3" E5_SEEDS="$2" bash testbed/matrix_e5.sh
}

for pass in 1 2; do
    echo "## pass $pass start $(date '+%F %T')"
    for s in $(seq 4200 4209); do
        run "F${K}H" "$s" "none fever-fl-ll" fc3 || exit 1
    done
done
{ echo "# One-host crowd reruns (runs invalid or failed once; a run listed twice is missing)"; echo
  ls "$RUNS/_failed" 2>/dev/null | grep -E '^fc3_T1B_' | sed 's/^/- /'; } > "$OUT/reruns.md"
echo "## one-host crowd seeds done $(date '+%F %T')"
