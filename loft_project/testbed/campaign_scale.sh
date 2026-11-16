#!/bin/bash
# More colluding attackers (docs/scale_prereg.md): FEVER, FTMaster, FTODefender and DMS-BTT on T1B
# G2 and EVX with 4 and 8 attackers, and no defense with 8, seeds 4184-4186 (54 runs), by seed, then
# attacker count, attack and method, and a second pass that reruns once every run that failed or was
# invalid. Run names sc<n>_T1B_<attack>_<method>_s<seed>.
#   bash testbed/campaign_scale.sh
set -u
cd "$(dirname "$0")/.."
grep -q "preregistration (draft)" docs/scale_prereg.md && { echo "docs/scale_prereg.md is still a draft"; exit 1; }
OUT=results/testbed_scale
mkdir -p "$OUT"
RUNS="$HOME/loft-runs"
METHODS="fever-fl-ll ftmaster ftodefender dms-btt-h1"

run() {   # attackers traffic seed methods
    while pgrep -x chrome >/dev/null || pgrep -x zoom >/dev/null; do sleep 60; done
    E5_TAG="sc$1" E5_DUR=300 E5_DOM=T1B E5_TOPO=tree3 E5_BSCALE=0.5 E5_EXTRA="--attackers $1" \
        E5_VARS="$2" E5_DEFS="$4" E5_SEEDS="$3" bash testbed/matrix_e5.sh
}

for pass in 1 2; do
    echo "## pass $pass start $(date '+%F %T')"
    for s in 4184 4185 4186; do
        for n in 4 8; do
            for v in A2 EVX; do
                ms="$METHODS"
                [ "$n" = 8 ] && ms="none $METHODS"
                run "$n" "$v" "$s" "$ms" || exit 1
            done
        done
    done
done
{ echo "# Scalability reruns (runs invalid or failed once; a run listed twice is missing)"; echo
  ls "$RUNS/_failed" 2>/dev/null | grep -E '^sc[48]_T1B_' | sed 's/^/- /'; } > "$OUT/reruns.md"
echo "## scalability done $(date '+%F %T')"
